#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/ppsspp_ws.py against an in-process fake of PPSSPP's WebSocket debugger.

Run with: python3 -I tools/tests/test_ppsspp_ws.py

The fake is a real TCP server speaking RFC 6455, and copies the behaviour of PPSSPP v1.20.4 read from
Core/Debugger/WebSocket/*.cpp: breakpoints pause unless enabled=false, cpu.resume has no ticketed
reply, hle.module.list keeps unloaded modules with isActive=false, bad requests get an error event
carrying the ticket. It is a model, not PPSSPP: the tool has not been tried against the real thing.
"""

import base64
import contextlib
import hashlib
import importlib.util
import io
import json
import queue
import os
import re
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("ppsspp_ws", TOOLS / "ppsspp_ws.py")
ws = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ws)

SLOT = 0x08E9AA00
STORY = {"name": "modstory", "address": SLOT, "size": 0x234300, "isActive": True}
TITLE = {"name": "modtitle", "address": SLOT, "size": 0x1053980, "isActive": True}
DUEL_MGR = {"name": "modduel_mgr", "address": SLOT, "size": 0x20100, "isActive": True}
ENGINE = {"name": "modduel_eng", "address": 0x09BE1400, "size": 0x24BF80, "isActive": True}
SHIFT_WORD = 0x08AC18C0
STATE = 0x08AA5794 + 4  # r = 1


def inactive(module):
    return dict(module, isActive=False)


class FakePPSSPP:
    """One client at a time. Tests push work through `outbox`; the server thread owns the socket."""

    def __init__(self, handshake_status="101 Switching Protocols"):
        self.listener = socket.socket()
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(4)
        self.listener.settimeout(0.05)
        self.port = self.listener.getsockname()[1]
        self.handshake_status = handshake_status
        self.modules = []
        self.memory = {SHIFT_WORD: 1}
        self.registers = {}
        self.cpu_bps = {}
        self.mem_bps = {}
        self.received = []
        self.violations = []
        self.pongs = []
        self.protocols = []
        self.stepping = False
        self.cpu_alive = True
        self.fragment_replies = False
        self.drop_on = None
        self.silent = False
        self.frames = [{"pc": 0x09C00000}]
        self.outbox = queue.Queue()
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        self.listener.close()
        self.thread.join(2)

    def serve(self):
        while not self.stop.is_set():
            try:
                conn, _ = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with conn:
                try:
                    self.session(conn)
                except OSError:
                    pass

    def session(self, conn):
        conn.settimeout(2)
        request = b""
        while b"\r\n\r\n" not in request:
            request += conn.recv(4096)
        headers = dict(l.split(": ", 1) for l in request.decode().split("\r\n")[1:] if ": " in l)
        self.protocols.append(headers.get("Sec-WebSocket-Protocol"))
        accept = base64.b64encode(hashlib.sha1((headers["Sec-WebSocket-Key"] + ws.WS_GUID).encode()).digest()).decode()
        conn.sendall(f"HTTP/1.1 {self.handshake_status}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                     f"Sec-WebSocket-Accept: {accept}\r\nSec-WebSocket-Protocol: {ws.SUBPROTOCOL}\r\n\r\n".encode())
        if not self.handshake_status.startswith("101"):
            return
        conn.settimeout(0.005)
        buffer = bytearray()
        while not self.stop.is_set():
            while True:
                try:
                    item = self.outbox.get_nowait()
                except queue.Empty:
                    break
                if item is None:
                    return
                if callable(item):
                    item(conn)
                else:
                    self.send(conn, item)
            try:
                data = conn.recv(65536)
                if not data:
                    return
                buffer += data
            except socket.timeout:
                pass
            while True:
                frame = self.read_frame(buffer)
                if frame is None:
                    break
                opcode, payload = frame
                if opcode == 8:
                    conn.sendall(self.frame(8, payload[:2]))
                    return
                if opcode == 10:
                    self.pongs.append(payload)
                if opcode == 1:
                    if self.handle(conn, json.loads(payload)) == "drop":
                        return

    def read_frame(self, data):
        if len(data) < 2:
            return None
        opcode, length, offset = data[0] & 15, data[1] & 127, 2
        if not data[1] & 0x80:
            self.violations.append("client frame not masked")
        if length == 126:
            if len(data) < 4:
                return None
            length, offset = struct.unpack_from(">H", data, 2)[0], 4
        if len(data) < offset + 4 + length:
            return None
        mask = data[offset:offset + 4]
        payload = bytes(b ^ mask[i & 3] for i, b in enumerate(data[offset + 4:offset + 4 + length]))
        del data[:offset + 4 + length]
        return opcode, payload

    @staticmethod
    def frame(opcode, payload, fin=True):
        header = bytes([(0x80 if fin else 0) | opcode])
        if len(payload) < 126:
            return header + bytes([len(payload)]) + payload
        return header + struct.pack(">BH", 126, len(payload)) + payload

    def send(self, conn, message):
        text = (message if isinstance(message, str) else json.dumps(message)).encode()
        conn.sendall(self.frame(1, text))

    def reply(self, conn, request, **fields):
        message = {"event": request["event"], **fields}
        if "ticket" in request:
            message["ticket"] = request["ticket"]
        if self.fragment_replies:  # memory.read comes in several frames in the real server
            text = json.dumps(message).encode()
            cut = len(text) // 2
            conn.sendall(self.frame(1, text[:cut], fin=False) + self.frame(9, b"hi") + self.frame(0, text[cut:]))
        else:
            self.send(conn, message)

    def error(self, conn, request, text):
        message = {"event": "error", "message": text, "level": 2}
        if "ticket" in request:
            message["ticket"] = request["ticket"]
        self.send(conn, message)

    def evaluate(self, expression):
        expression = expression.strip()
        match = re.fullmatch(r"\[\s*(0x[0-9a-fA-F]+)\s*(?:,\s*(\d))?\s*\]", expression)
        if match:
            return self.memory.get(int(match.group(1), 16), 0)
        if expression in self.registers:
            return self.registers[expression]
        if re.fullmatch(r"0x[0-9a-f]+", expression):
            return int(expression, 16)
        return 0

    def handle(self, conn, request):
        event = request["event"]
        self.received.append(request)
        if event.startswith("memory.read"):
            self.violations.append(f"{event} stops the core in PPSSPP")
        if event == self.drop_on:
            return "drop"
        if self.silent:
            return None
        needs_cpu = event.startswith(("cpu.breakpoint", "memory.breakpoint", "cpu.evaluate"))
        if needs_cpu and not self.cpu_alive:
            self.error(conn, request, "CPU not started")
        elif event == "version":
            self.reply(conn, request, name="PPSSPP", version="v1.20.4")
        elif event == "game.status":
            self.reply(conn, request, game={"id": "ULES01183", "version": "1.00", "title": "fake"}, paused=False)
        elif event == "cpu.status":
            self.reply(conn, request, stepping=self.stepping, paused=False, pc=0, ticks=0)
        elif event == "cpu.evaluate":
            if "BAD" in request["expression"]:
                self.error(conn, request, "Could not parse expression syntax")
            else:
                self.reply(conn, request, uintValue=self.evaluate(request["expression"]), floatValue="0")
        elif event == "hle.module.list":
            self.reply(conn, request, modules=self.modules)
        elif event == "hle.backtrace":
            if self.stepping:
                self.reply(conn, request, frames=self.frames)
            else:
                self.error(conn, request, "CPU currently running (cpu.stepping first)")
        elif event == "gpu.stats.get":
            self.reply(conn, request, fps={"actual": 30.0, "target": 30.0})
        elif event == "cpu.breakpoint.add":
            self.cpu_bps[request["address"]] = dict(request)
            self.reply(conn, request)
        elif event == "cpu.breakpoint.update":
            self.cpu_bps[request["address"]].update(request)
            self.reply(conn, request)
        elif event == "cpu.breakpoint.remove":
            self.cpu_bps.pop(request["address"], None)
            self.reply(conn, request)
        elif event == "cpu.breakpoint.list":
            self.reply(conn, request, breakpoints=[
                {"address": a, "enabled": b.get("enabled", True), "log": b.get("log", False),
                 "condition": b.get("condition"), "logFormat": b.get("logFormat")} for a, b in self.cpu_bps.items()])
        elif event == "memory.breakpoint.add":
            self.mem_bps[(request["address"], request["size"])] = dict(request)
            self.reply(conn, request)
        elif event == "memory.breakpoint.remove":
            self.mem_bps.pop((request["address"], request["size"]), None)
            self.reply(conn, request)
        elif event == "memory.breakpoint.list":
            self.reply(conn, request, breakpoints=[
                {"address": a, "size": s, "logFormat": b.get("logFormat")} for (a, s), b in self.mem_bps.items()])
        elif event.startswith("memory.write_u"):
            if not self.stepping:
                self.violations.append("memory write while running")
            self.memory[request["address"]] = request["value"]
            self.reply(conn, request, value=request["value"])
        elif event == "cpu.stepping":  # no direct reply: the state change is the answer
            self.stepping = True
        elif event == "cpu.resume":
            if not self.stepping:
                self.error(conn, request, "CPU not stepping")
            else:
                self.stepping = False
                self.send(conn, {"event": "cpu.resume"})
        else:
            self.error(conn, request, "Bad message: unknown event")

    def format_log(self, text):
        def expand(match):
            return f"{self.evaluate(match.group(1)):08x}"
        return re.sub(r"\{([^{}]*)\}", expand, text)

    def fire(self, address):
        """A breakpoint trips: the log line, and a stepping broadcast if it pauses."""
        bp = self.cpu_bps.get(address)
        if bp is None:
            return False
        self.outbox.put({"event": "log", "timestamp": "00:00", "header": "x", "level": 1, "channel": "JIT",
                         "message": f"BKP PC={address:08x}: {self.format_log(bp['logFormat'])}\n"})
        if bp.get("enabled", True):
            self.stepping = True
            self.outbox.put({"event": "cpu.stepping", "pc": address, "ticks": 1.0,
                             "reason": "cpu.breakpoint", "relatedAddress": address})
        return True

    def fire_memory(self, address, size):
        bp = self.mem_bps[(address, size)]
        self.outbox.put({"event": "log", "timestamp": "00:00", "header": "x", "level": 1, "channel": "MEMMAP",
                         "message": f"CHK Write32(CPU) at {address:08x}: {self.format_log(bp['logFormat'])}\n"})


def make_test(**extra):
    test = {"id": "T1", "title": "fake", "plan": "none", "instructions_pt": ["jogue"], "required_module": "rel_story",
            "breakpoints": [{"id": "story_fn", "kind": "exec", "address": "0x08ea5d18", "record": {"x": "a0", "ra": "ra"}}],
            "samples": [], "expected": [{"type": "hits", "bp": "story_fn", "what": "hits"}], "not_possible": []}
    test.update(extra)
    return test


class Harness(unittest.TestCase):
    def setUp(self):
        self.fake = FakePPSSPP()
        self.addCleanup(self.fake.close)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.log_path = Path(self.temp.name) / "run.jsonl"

    def client(self, allow_edits=False):
        socket_ = ws.WebSocket("127.0.0.1", self.fake.port)
        self.addCleanup(socket_.close)
        return ws.Debugger(socket_, allow_edits=allow_edits, timeout=2.0)

    def session(self, test=None, allow_edits=False, **kwargs):
        self.echoed = []
        session = ws.Session(self.client(allow_edits), test or make_test(), self.log_path, poll=0.01,
                             echo=self.echoed.append, **kwargs)
        return session

    def stepped(self, test=None, **kwargs):
        """A session driven by step(), as run() would after begin()."""
        session = self.session(test, **kwargs)
        session.begin()
        return session

    def until(self, session, predicate, timeout=3.0):
        deadline = time.monotonic() + timeout
        while not predicate():
            self.assertLess(time.monotonic(), deadline, "condition not reached")
            session.step()

    def settle(self, session, seconds=0.06):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            session.step()

    def records(self, kind=None):
        rows = [json.loads(line) for line in self.log_path.read_text(encoding="utf-8").splitlines()]
        return [row for row in rows if kind is None or row["k"] == kind]

    def assertNoViolations(self):
        self.assertEqual(self.fake.violations, [])


class FrameTests(Harness):
    def test_handshake_offers_the_subprotocol(self):
        self.client()
        deadline = time.monotonic() + 2
        while not self.fake.protocols and time.monotonic() < deadline:
            time.sleep(0.005)
        self.assertEqual(self.fake.protocols, ["debugger.ppsspp.org"])

    def test_a_server_that_does_not_upgrade_is_refused(self):
        fake = FakePPSSPP("404 Not Found")
        self.addCleanup(fake.close)
        with self.assertRaises(ws.ConnectionClosed):
            ws.WebSocket("127.0.0.1", fake.port)

    def test_masked_frames_tickets_and_interleaved_broadcasts(self):
        client = self.client()
        self.fake.outbox.put({"event": "log", "message": "before"})
        self.assertEqual(client.call("version", name="x", version="1")["version"], "v1.20.4")
        client.pump(0.05)
        self.assertEqual(client.events[0]["message"], "before")
        self.assertNoViolations()

    def test_fragmented_reply_with_a_ping_inside(self):
        client = self.client()
        self.fake.fragment_replies = True
        self.assertEqual(client.call("game.status")["game"]["id"], "ULES01183")
        deadline = time.monotonic() + 2
        while not self.fake.pongs and time.monotonic() < deadline:
            client.pump(0.01)
        self.assertEqual(self.fake.pongs, [b"hi"])

    def test_long_frame(self):
        client = self.client()
        self.fake.outbox.put({"event": "log", "message": "x" * 60000})
        while not client.events:
            client.pump(0.05)
        self.assertEqual(len(client.events[0]["message"]), 60000)

    def test_error_event_with_ticket_raises(self):
        client = self.client()
        self.fake.cpu_alive = False
        with self.assertRaisesRegex(ws.DebuggerError, "CPU not started"):
            client.evaluate("a0")

    def test_answerless_request_times_out(self):
        client = self.client()
        self.fake.silent = True
        with self.assertRaises(TimeoutError):
            client.call("cpu.status", timeout=0.05)

    def test_disconnect_during_a_call(self):
        client = self.client()
        self.fake.drop_on = "cpu.status"
        with self.assertRaises(ws.ConnectionClosed):
            client.call("cpu.status")

    def test_close_frame(self):
        client = self.client()
        self.fake.outbox.put(lambda conn: conn.sendall(FakePPSSPP.frame(8, struct.pack(">H", 1001))))
        with self.assertRaises(ws.ConnectionClosed):
            for _ in range(100):
                client.pump(0.02)


class GuardTests(Harness):
    KEY = 0x08879068

    def test_save_key_range_and_mirrors(self):
        for address, size in ((self.KEY, 1), (self.KEY + 15, 1), (self.KEY - 2, 4), (self.KEY - 0x100, 0x200),
                              (0x48879068, 4), (0x88879068, 4), (0xC8879070, 1)):
            self.assertTrue(ws.overlaps_save_key(address, size), hex(address))
        for address, size in ((self.KEY - 4, 4), (self.KEY + 16, 4), (0x08804000, 0x1000)):
            self.assertFalse(ws.overlaps_save_key(address, size), hex(address))

    def test_every_way_of_naming_the_key_is_refused(self):
        requests = [
            ("cpu.evaluate", {"expression": "[0x08879068]"}),
            ("cpu.evaluate", {"expression": "[0x08879068,1]"}),
            ("cpu.evaluate", {"expression": "[0x08879060 + 0x8]"}),
            ("cpu.evaluate", {"expression": "[0x48879068]"}),
            ("cpu.evaluate", {"expression": "[0x08879066]"}),  # a word that straddles the start
            ("cpu.evaluate", {"expression": "a0 == 0x08879068"}),
            ("cpu.breakpoint.add", {"address": self.KEY}),
            ("memory.breakpoint.add", {"address": self.KEY - 0x10, "size": 0x20}),
            ("memory.breakpoint.remove", {"address": self.KEY, "size": 1}),
            ("cpu.breakpoint.add", {"address": 0x08804000, "condition": "[0x08879068] == 1"}),
            ("cpu.breakpoint.add", {"address": 0x08804000, "logFormat": "k {[0x08879068]}"}),
            ("memory.write_u8", {"address": self.KEY, "value": 0}),
        ]
        for event, params in requests:
            with self.assertRaises(ws.Refused, msg=(event, params)):
                ws.check_request(event, params, allow_edits=True)

    def test_the_client_sends_nothing_when_refused(self):
        client = self.client()
        with self.assertRaises(ws.Refused):
            client.call("cpu.evaluate", expression="[0x08879068]")
        with self.assertRaises(ws.Refused):
            client.send("memory.breakpoint.add", address=self.KEY, size=4)
        client.call("cpu.status")
        self.assertEqual([r["event"] for r in self.fake.received], ["cpu.status"])

    def test_reads_that_cannot_be_checked_are_refused(self):
        for expression in ("[a0]", "[a2+0x18]", "[[0x08ac18c0]+0x10]", "[0x08879000+a0]", "[some_symbol]",
                           "z_un_08879068", "[0x10 ? 0x08879068 : 0]"):
            with self.assertRaises(ws.Refused, msg=expression):
                ws.check_expression(expression)
        for text in ("{a0:s}", "{a0:p}", "{[a0]}"):
            with self.assertRaises(ws.Refused, msg=text):
                ws.check_log_format(text)

    def test_bare_decimals_are_refused_because_ppsspp_reads_hex(self):
        with self.assertRaisesRegex(ws.Refused, "hexadecimal"):
            ws.check_expression("a0 == 46")
        ws.check_expression("a0 == 0x2e && a1 == 1")

    def test_ordinary_requests_pass(self):
        ws.check_request("cpu.evaluate", {"expression": "[0x09e27fee,2] == 0"})
        ws.check_log_format("tf3 G1.ev us={usec} code={a0} n={[0x09e2d1e0]:d} {}")

    def test_only_listed_events_can_be_sent(self):
        for event in ("input.buttons.send", "input.buttons.press", "input.analog.send", "game.reset", "memory.read",
                      "memory.read_u32", "memory.readString", "memory.write", "cpu.setReg", "hle.thread.stop"):
            with self.assertRaises(ws.Refused, msg=event):
                ws.check_request(event, {}, allow_edits=True)

    def test_a_definition_on_the_key_does_not_load(self):
        bad = make_test(breakpoints=[{"id": "k", "kind": "memory", "address": "0x08879068", "size": 16}])
        with self.assertRaises(ws.Refused):
            ws.validate_test(bad)
        bad = make_test(samples=[{"id": "k", "address": "0x08879060", "size": 4, "count": 4}])
        with self.assertRaises(ws.Refused):
            ws.validate_test(bad)
        bad = make_test(breakpoints=[{"id": "k", "kind": "exec", "address": "0x08804000", "record": {"k": "[0x08879068]"}}])
        with self.assertRaises(ws.Refused):
            ws.validate_test(bad)

    def test_a_parameter_cannot_reach_the_key_at_run_time(self):
        test = make_test(params={"p": "0x0"}, required_module="BOOT",
                         samples=[{"id": "s", "address": "0x08879000+$p", "size": 4, "module": "BOOT"}])
        ws.validate_test(test)
        session = self.session(test, params={"p": "0x68"})
        self.fake.modules = [STORY]
        with self.assertRaises(ws.Refused):
            session.run(5)
        self.assertEqual(self.records("end")[0]["reason"], "exception")
        self.assertFalse([r for r in self.fake.received if "08879068" in json.dumps(r).lower()])


class ArmingTests(Harness):
    ADDRESS = 0x08EA5D18

    def test_shared_base_arms_only_for_the_required_module(self):
        session = self.session()
        self.fake.modules = [TITLE, inactive(STORY)]  # PPSSPP keeps unloaded modules in the list
        self.settle(session)
        self.assertNotIn(self.ADDRESS, self.fake.cpu_bps)
        self.fake.modules = [inactive(TITLE), STORY]
        self.until(session, lambda: self.ADDRESS in self.fake.cpu_bps)
        bp = self.fake.cpu_bps[self.ADDRESS]
        self.assertIs(bp["enabled"], False)
        self.assertIs(bp["log"], True)
        self.fake.modules = [inactive(TITLE), inactive(STORY), DUEL_MGR]
        self.until(session, lambda: self.ADDRESS not in self.fake.cpu_bps)
        self.settle(session)
        self.assertNotIn(self.ADDRESS, self.fake.cpu_bps)
        session.cleanup()

    def test_hits_are_tagged_with_the_module(self):
        session = self.session()
        self.fake.modules = [STORY]
        self.until(session, lambda: self.ADDRESS in self.fake.cpu_bps)
        self.fake.registers["a0"] = 7
        self.fake.fire(self.ADDRESS)
        self.settle(session)
        session.cleanup()
        hit = self.records("hit")[0]
        self.assertEqual((hit["mod"], hit["f"]["x"], hit.get("suspect")), ("rel_story", 7, None))

    def test_a_hit_after_the_module_left_is_suspect_and_not_counted(self):
        session = self.stepped()
        self.fake.modules = [STORY]
        self.until(session, lambda: self.ADDRESS in self.fake.cpu_bps)
        session.next_poll = float("inf")  # the unload happens between two polls
        self.fake.fire(self.ADDRESS)
        self.settle(session)
        self.assertEqual(len(session.pending), 1)
        self.fake.modules = [inactive(STORY), DUEL_MGR]
        session.next_poll = 0
        self.until(session, lambda: self.ADDRESS not in self.fake.cpu_bps)
        session.cleanup()
        hit = self.records("hit")[0]
        self.assertTrue(hit["suspect"])
        lines = ws.summarize(self.log_path)
        self.assertTrue(any(line.lstrip().startswith("NOT SEEN") for line in lines), lines)
        self.assertTrue(any("1 suspect" in line for line in lines), lines)

    def test_boot_breakpoints_stay_armed_across_scenes(self):
        test = make_test(breakpoints=[
            {"id": "boot", "kind": "exec", "address": "0x08854ba0", "module": "BOOT"},
            {"id": "story_fn", "kind": "exec", "address": "0x08ea5d18"}])
        session = self.session(test)
        self.fake.modules = [STORY]
        self.until(session, lambda: self.ADDRESS in self.fake.cpu_bps)
        self.fake.modules = [inactive(STORY), DUEL_MGR]
        self.until(session, lambda: self.ADDRESS not in self.fake.cpu_bps)
        self.assertIn(0x08854BA0, self.fake.cpu_bps)
        session.cleanup()

    def test_any_of_several_modules(self):
        test = make_test(required_module=["rel_quiz", "rel_throw"])
        session = self.session(test)
        self.fake.modules = [{"name": "modthrow", "address": 0x09000000, "size": 0x1000, "isActive": True}]
        self.until(session, lambda: self.ADDRESS in self.fake.cpu_bps)
        session.cleanup()

    def test_memory_breakpoint_parameters(self):
        test = make_test(required_module="rel_duel_eng", breakpoints=[
            {"id": "w", "kind": "memory", "address": "S+0x10", "size": 2, "access": "write", "condition": "a0 != 0", "record": {"pc": "pc"}},
            {"id": "c", "kind": "memory", "address": "0x09e2d1e8", "access": "change"}])
        session = self.session(test)
        self.fake.modules = [ENGINE]
        self.until(session, lambda: len(self.fake.mem_bps) == 2)
        write = self.fake.mem_bps[(STATE + 0x10, 2)]
        self.assertEqual((write["enabled"], write["log"], write["read"], write["write"], write["change"]),
                         (False, True, False, True, False))
        self.assertEqual(write["condition"], "a0 != 0")
        change = self.fake.mem_bps[(0x09E2D1E8, 4)]
        self.assertEqual((change["write"], change["change"]), (True, True))
        self.fake.registers["pc"] = 0x09DBC400
        self.fake.fire_memory(STATE + 0x10, 2)
        self.settle(session)
        session.cleanup()
        hit = self.records("hit")[0]
        self.assertEqual((hit["f"]["pc"], hit["access"], hit["at"]), (0x09DBC400, "Write32", STATE + 0x10))
        self.assertEqual(self.fake.mem_bps, {})

    def test_a_module_at_another_base_is_shifted_with_a_warning(self):
        test = make_test(breakpoints=[{"id": "story_fn", "kind": "exec", "address": "0x08ea5d18",
                                       "record": {"state": "[0x08ecd978]"}}])
        session = self.session(test)
        self.fake.modules = [dict(STORY, address=SLOT + 0x1000)]
        self.until(session, lambda: self.ADDRESS + 0x1000 in self.fake.cpu_bps)
        self.assertIn("[0x8ece978]", self.fake.cpu_bps[self.ADDRESS + 0x1000]["logFormat"])
        session.cleanup()
        self.assertTrue(any("shifted" in row["text"] for row in self.records("warn")))

    def test_the_maintainers_breakpoint_is_left_alone(self):
        self.fake.cpu_bps[self.ADDRESS] = {"address": self.ADDRESS, "enabled": True, "log": False}
        session = self.session()
        session.read_foreign()
        self.fake.modules = [STORY]
        self.settle(session)
        session.cleanup()
        self.assertEqual(self.fake.cpu_bps[self.ADDRESS]["enabled"], True)
        self.assertTrue(any("not replacing" in row["text"] for row in self.records("warn")))

    def test_leftovers_of_a_killed_run_are_removed(self):
        self.fake.cpu_bps[0x09000000] = {"address": 0x09000000, "logFormat": "tf3 G1.ev us={usec}"}
        self.fake.mem_bps[(0x09000010, 4)] = {"logFormat": "tf3 G5.slot0 us={usec}"}
        session = self.session()
        session.read_foreign()
        session.cleanup()
        self.assertEqual((self.fake.cpu_bps, self.fake.mem_bps), ({}, {}))

    def test_a_restarted_game_is_armed_again(self):
        session = self.session()
        self.fake.modules = [STORY]
        self.until(session, lambda: self.ADDRESS in self.fake.cpu_bps)
        self.fake.modules = []
        self.fake.cpu_bps.clear()  # whatever PPSSPP does to them when the game closes
        self.fake.cpu_alive = False
        self.settle(session)
        self.fake.cpu_alive = True
        self.fake.modules = [STORY]
        self.until(session, lambda: self.ADDRESS in self.fake.cpu_bps)
        session.cleanup()

    def test_another_game_stops_the_run(self):
        original = self.fake.handle

        def other_game(conn, request):
            if request["event"] == "game.status":
                self.fake.received.append(request)
                self.fake.reply(conn, request, game={"id": "ULUS00000"}, paused=False)
                return None
            return original(conn, request)
        self.fake.handle = other_game
        self.fake.modules = [STORY]
        session = self.session()
        self.assertIn("wrong game", session.run(3))
        self.assertEqual(self.fake.cpu_bps, {})

    def test_module_names_that_are_not_mod_plus_name(self):
        self.assertEqual(ws.module_file("moddeck_swap", 1), "rel_deckswap")
        self.assertEqual(ws.module_file("module_htmlview", 1), "rel_html_view")
        self.assertEqual(ws.module_file("modtemplate", 14950864), "rel_cutin_viewer")
        self.assertEqual(ws.module_file("modtemplate", 4765824), "rel_movie_viewer")
        self.assertEqual(ws.module_file("sceSomething", 1), "sceSomething")

    def test_a_bad_condition_warns_instead_of_stopping(self):
        test = make_test(breakpoints=[{"id": "b", "kind": "exec", "address": "0x08ea5d18", "record": {"x": "a0"}}])
        session = self.session(test)
        self.fake.cpu_alive = False
        self.fake.modules = [STORY]
        self.settle(session)
        self.assertEqual(session.armed, {})
        session.cleanup()
        self.assertTrue(any("could not arm" in row["text"] for row in self.records("warn")))


class CleanupTests(Harness):
    def full_test(self):
        return make_test(breakpoints=[
            {"id": "e", "kind": "exec", "address": "0x08ea5d18"},
            {"id": "boot", "kind": "exec", "address": "0x08854ba0", "module": "BOOT"},
            {"id": "m", "kind": "memory", "address": "0x08ecd978", "size": 4}])

    def assertClean(self):
        self.assertEqual((self.fake.cpu_bps, self.fake.mem_bps), ({}, {}))

    def test_normal_end_removes_everything(self):
        self.fake.modules = [STORY]
        session = self.session(self.full_test())
        reason = session.run(0.15)
        self.assertEqual(reason, "duration reached")
        self.assertClean()
        self.assertEqual(self.records("end")[0]["not_removed"], [])

    def test_quit_command(self):
        self.fake.modules = [STORY]
        commands = queue.Queue()
        commands.put("m hello\n")
        commands.put("q\n")
        session = self.session(self.full_test(), commands=commands)
        self.assertEqual(session.run(3), "stopped by the maintainer")
        self.assertClean()
        self.assertEqual(self.records("mark")[0]["text"], "hello")

    def test_ctrl_c_removes_everything(self):
        self.fake.modules = [STORY]
        armed = threading.Event()
        real = time.monotonic

        def clock():
            if armed.is_set():
                armed.clear()
                raise KeyboardInterrupt
            return real()
        session = self.session(self.full_test(), clock=clock)
        original = session.arm

        def arm_then_interrupt(bp):
            original(bp)
            if len(session.armed) == 3:
                armed.set()
        session.arm = arm_then_interrupt
        self.assertEqual(session.run(5), "Ctrl+C")
        self.assertClean()
        self.assertEqual(self.records("end")[0]["reason"], "Ctrl+C")

    def test_a_held_pause_is_released_on_exit(self):
        self.fake.modules = [STORY]
        session = self.session(self.full_test())
        self.until(session, lambda: len(session.armed) == 3)
        self.fake.stepping = True
        session.holding_pause = True
        session.cleanup()
        deadline = time.monotonic() + 1
        while self.fake.stepping and time.monotonic() < deadline:
            time.sleep(0.005)
        self.assertFalse(self.fake.stepping)

    def test_disconnect_ends_the_run_and_says_what_stayed(self):
        self.fake.modules = [STORY]
        session = self.stepped(self.full_test())
        self.until(session, lambda: len(session.armed) == 3)
        self.fake.outbox.put(None)
        with contextlib.suppress(ws.ConnectionClosed):
            self.until(session, lambda: False, timeout=1)
        session.stop_reason = "connection lost"
        session.cleanup()
        end = self.records("end")[0]
        self.assertEqual(sorted(end["not_removed"]), ["boot", "e", "m"])
        self.assertTrue(any("NOT REMOVED" in line for line in ws.summarize(self.log_path)))

    def test_run_reports_a_lost_connection(self):
        self.fake.modules = [STORY]
        session = self.session(self.full_test())
        threading.Timer(0.1, lambda: self.fake.outbox.put(None)).start()
        self.assertIn("connection lost", session.run(3))

    def test_remove_failure_after_the_game_closed_is_reported(self):
        self.fake.modules = [STORY]
        session = self.session(self.full_test())
        self.until(session, lambda: len(session.armed) == 3)
        self.fake.cpu_alive = False
        session.cleanup()
        self.assertEqual(sorted(self.records("end")[0]["not_removed"]), ["boot", "e", "m"])


class PauseTests(Harness):
    ADDRESS = 0x08EA3AE8

    def pause_test(self, **extra):
        return make_test(breakpoints=[{"id": "p", "kind": "exec", "address": "0x08ea3ae8", "pause": True,
                                       "backtrace": True, "record": {"ra": "ra"}, **extra}])

    def test_pause_reads_and_resumes(self):
        self.fake.modules = [STORY]
        session = self.session(self.pause_test())
        self.until(session, lambda: self.ADDRESS in self.fake.cpu_bps)
        self.assertIs(self.fake.cpu_bps[self.ADDRESS]["enabled"], True)
        self.fake.registers["ra"] = 0x08EA0000
        self.fake.fire(self.ADDRESS)
        self.until(session, lambda: not self.fake.stepping and session.stats["p"].pauses == 1)
        session.cleanup()
        pause = self.records("pause")[0]
        self.assertEqual((pause["f"]["ra"], pause["frames"]), (0x08EA0000, [0x09C00000]))

    def test_someone_elses_stop_is_not_resumed(self):
        self.fake.modules = [STORY]
        session = self.session(self.pause_test())
        self.until(session, lambda: self.ADDRESS in self.fake.cpu_bps)
        self.fake.stepping = True
        for reason, address in (("ui.pause", 0), ("savestate.load", 0), ("cpu.breakpoint", 0x09000000), ("memory.access", self.ADDRESS)):
            self.fake.outbox.put({"event": "cpu.stepping", "pc": 0, "ticks": 1.0, "reason": reason, "relatedAddress": address})
        self.settle(session)
        self.assertTrue(self.fake.stepping)
        self.assertFalse([r for r in self.fake.received if r["event"] == "cpu.resume"])
        session.cleanup()

    def test_a_pausing_breakpoint_turns_log_only(self):
        self.fake.modules = [STORY]
        session = self.session(self.pause_test(max_pauses=2))
        self.until(session, lambda: self.ADDRESS in self.fake.cpu_bps)
        for count in (1, 2):
            self.fake.fire(self.ADDRESS)
            self.until(session, lambda: session.stats["p"].pauses == count)
        self.until(session, lambda: self.fake.cpu_bps[self.ADDRESS]["enabled"] is False)
        self.assertIs(self.fake.cpu_bps[self.ADDRESS]["log"], True)
        session.cleanup()


class RateLimitTests(Harness):
    def session_with(self, **bp):
        test = make_test(breakpoints=[{"id": "f", "kind": "exec", "address": "0x08854ba0", "module": "BOOT", **bp}])
        return self.session(test)

    @staticmethod
    def message(**fields):
        body = " ".join(f"{k}={v:08x}" for k, v in fields.items())
        return {"message": f"BKP PC=08854ba0: tf3 T1.f us=00000001 {body}\n"}

    def test_a_per_frame_function_is_counted_exactly_but_barely_logged(self):
        session = self.session_with(record={"x": "a0"}, max_per_second=5)
        session.begin()
        started = time.monotonic()
        for _ in range(100000):
            session.on_log(self.message(x=1))
        session.cleanup()
        self.assertLessEqual(len(self.records("hit")), 5 * (time.monotonic() - started + 2))
        lines = ws.summarize(self.log_path)
        self.assertTrue(any("f: 100000," in line for line in lines), lines)

    def test_every_distinct_value_reaches_the_log(self):
        session = self.session_with(record={"x": "a0"}, max_per_second=1)
        for value in range(150):
            session.on_log(self.message(x=value))
            session.on_log(self.message(x=value))
        session.cleanup()
        kept = {row["f"]["x"] for row in self.records("hit")}
        self.assertEqual(kept, set(range(150)))

    def test_transitions_survive_the_limit(self):
        session = self.session_with(record={"x": "a0"}, max_per_second=1)
        for value in (46, 46, 46, 49, 49, 48, 48, 49, 50):
            session.on_log(self.message(x=value))
        session.cleanup()
        self.assertEqual([row["f"]["x"] for row in self.records("hit")], [46, 49, 48, 49, 50])

    def test_volatile_fields_do_not_make_hits_distinct(self):
        session = self.session_with(record={"x": "a0", "frame": "a1"}, volatile=["frame"], max_per_second=1)
        for frame in range(1000):
            session.on_log(self.message(x=1, frame=frame))
        session.cleanup()
        self.assertEqual(len(self.records("hit")), 1)
        dup = self.records("dup")[0]
        self.assertEqual(dup["items"], [{"f": {"x": 1}, "n": 999}])
        self.assertEqual(dup["last"]["f"]["frame"], 999)

    def test_too_many_distinct_values_are_counted_as_lost(self):
        session = self.session_with(record={"x": "a0"}, max_distinct=10)
        session.begin()
        for value in range(100):
            session.on_log(self.message(x=value))
        session.cleanup()
        self.assertEqual(len(self.records("hit")), 10)
        self.assertTrue(any("90 values not kept" in line for line in ws.summarize(self.log_path)))

    def test_other_log_lines_and_other_tests_are_ignored(self):
        session = self.session_with(record={"x": "a0"})
        session.on_log({"message": "something else entirely"})
        session.on_log({"message": "BKP PC=08854ba0: tf3 G1.ev us=00000001 x=00000001"})
        session.on_log({"message": "BKP PC=08854ba0 (z_un_08854ba0)"})
        session.cleanup()
        self.assertEqual(self.records("hit"), [])


class SampleTests(Harness):
    def test_reads_use_evaluate_and_the_state_address(self):
        test = make_test(required_module="BOOT", breakpoints=[], expected=[],
                         samples=[{"id": "frame", "address": "S+0x0c", "size": 4, "every_s": 0.01},
                                  {"id": "bytes", "address": "S+0x20", "size": 1, "count": 2, "every_s": 0.01},
                                  {"id": "fps", "kind": "gpu_fps", "every_s": 0.01, "always": True}])
        self.fake.memory[STATE + 0x0C] = 100
        self.fake.memory[STATE + 0x21] = 5
        self.fake.modules = [STORY]
        session = self.session(test)
        self.until(session, lambda: "S" in session.env and session.samples[0]["last"])
        self.fake.memory[STATE + 0x0C] = 130
        self.until(session, lambda: session.samples[0]["last"].get(0) == 130)
        session.cleanup()
        rows = self.records("sample")
        self.assertEqual([r["v"] for r in rows if r["id"] == "frame"], [100, 130])
        self.assertIn(5, [r["v"] for r in rows if r["id"] == "bytes[1]"])
        self.assertIn(30.0, [r["v"] for r in rows if r["id"] == "fps"])
        self.assertNoViolations()

    def test_nothing_is_armed_until_the_state_address_is_valid(self):
        test = make_test(breakpoints=[{"id": "m", "kind": "memory", "address": "S+0x10", "size": 2, "module": "BOOT"}])
        self.fake.memory[SHIFT_WORD] = 99
        self.fake.modules = [STORY]
        session = self.session(test)
        self.settle(session)
        self.assertEqual(self.fake.mem_bps, {})
        self.fake.memory[SHIFT_WORD] = 1
        session.next_state_check = 0
        self.until(session, lambda: (STATE + 0x10, 2) in self.fake.mem_bps)
        session.cleanup()

    def test_a_new_boot_moves_the_memory_breakpoints(self):
        test = make_test(breakpoints=[{"id": "m", "kind": "memory", "address": "S+0x10", "size": 2, "module": "BOOT"}])
        self.fake.modules = [STORY]
        session = self.session(test)
        self.until(session, lambda: (STATE + 0x10, 2) in self.fake.mem_bps)
        self.fake.memory[SHIFT_WORD] = 3
        session.next_state_check = 0
        self.until(session, lambda: (STATE + 8 + 0x10, 2) in self.fake.mem_bps)
        self.assertEqual(len(self.fake.mem_bps), 1)
        session.cleanup()


class EditTests(Harness):
    ADDRESS = STATE + 0x0FE52

    def edit_test(self):
        return make_test(params={"c": "0x2"}, edits=[{
            "id": "E-X1", "address": "S+0x0fe0c+$c*0x18+0x16", "size": 2, "value": "$value",
            "params": {"value": "0x3de"}, "purpose": "test"}])

    def test_edits_are_off_by_default(self):
        self.fake.modules = [STORY]
        session = self.session(self.edit_test())
        self.until(session, lambda: "S" in session.env)
        session.on_command("edit E-X1")
        session.cleanup()
        self.assertTrue(any("--allow-edits" in text for text in self.echoed))
        self.assertFalse([r for r in self.fake.received if r["event"].startswith("memory.write")])
        self.assertEqual(self.records("edit"), [])
        with self.assertRaises(ws.Refused):
            session.dbg.call("memory.write_u16", address=self.ADDRESS, value=1)

    def test_an_edit_pauses_writes_logs_and_resumes(self):
        self.fake.modules = [STORY]
        self.fake.memory[self.ADDRESS] = 200
        session = self.stepped(self.edit_test(), allow_edits=True)
        self.until(session, lambda: "S" in session.env)
        session.on_command("edit E-X1")
        deadline = time.monotonic() + 1
        while self.fake.stepping and time.monotonic() < deadline:
            session.dbg.pump(0.01)
        session.cleanup()
        edit = self.records("edit")[0]
        self.assertEqual((edit["address"], edit["size"], edit["old"], edit["new"]), (self.ADDRESS, 2, 200, 990))
        self.assertFalse(self.fake.stepping)
        self.assertNoViolations()  # the fake flags a write while running
        self.assertTrue(any("E-X1" in line and "0xc8 -> 0x3de" in line for line in ws.summarize(self.log_path)))

    def test_parameters_and_unknown_ids(self):
        self.fake.modules = [STORY]
        session = self.session(self.edit_test(), allow_edits=True)
        self.until(session, lambda: "S" in session.env)
        session.on_command("edit E-X9")
        self.assertTrue(any("unknown edit" in text for text in self.echoed))
        session.on_command("edit E-X1 c=3 value=0x7c6")
        session.cleanup()
        edit = self.records("edit")[0]
        self.assertEqual((edit["address"], edit["new"]), (STATE + 0x0FE0C + 3 * 0x18 + 0x16, 0x7C6))

    def test_no_edit_while_the_ai_simulates(self):
        self.fake.modules = [STORY, ENGINE]
        self.fake.memory[ws.SNAPSHOT_DEPTH] = 1
        session = self.session(self.edit_test(), allow_edits=True)
        self.until(session, lambda: "S" in session.env)
        session.on_command("edit E-X1")
        session.cleanup()
        self.assertEqual(self.records("edit"), [])
        self.assertFalse([r for r in self.fake.received if r["event"].startswith("memory.write")])
        deadline = time.monotonic() + 1
        while self.fake.stepping and time.monotonic() < deadline:
            time.sleep(0.005)
        self.assertFalse(self.fake.stepping)


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "log.jsonl"

    def write(self, test, rows, env=None):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"k": "meta", "t": 0, "format": 1, "test": test, "env": env or {}, "ppsspp": "v1.20.4", "started": "now"}) + "\n")
            for row in rows:
                handle.write(json.dumps(row) + "\n")

    def status(self, item, rows, env=None):
        test = make_test(expected=[item], breakpoints=[{"id": "b", "kind": "exec", "address": "0x1000"}])
        self.write(test, rows, env)
        lines = ws.summarize(self.path)
        return next(line.split()[0] + (" SEEN" if line.split()[:2] == ["NOT", "SEEN"] else "")
                    for line in lines[lines.index("items:") + 1:])

    @staticmethod
    def hit(t, **fields):
        return {"k": "hit", "t": t, "bp": "b", "mod": "rel_story", "us": 1, "f": fields}

    @staticmethod
    def sample(t, name, value):
        return {"k": "sample", "t": t, "id": name, "v": value, "mod": "rel_story"}

    def test_statuses(self):
        h = [self.hit(1, x=0x16), self.hit(2, x=0x1C)]
        cases = [
            ({"type": "hits", "bp": "b"}, h, "PASS"),
            ({"type": "hits", "bp": "b", "min": 5}, h, "FAIL"),
            ({"type": "hits", "bp": "b"}, [], "NOT SEEN"),
            ({"type": "field_seen", "bp": "b", "field": "x", "values": ["0x16", "0x1c"]}, h, "PASS"),
            ({"type": "field_seen", "bp": "b", "field": "x", "values": ["0x99"]}, h, "FAIL"),
            ({"type": "field_seen", "bp": "b", "field": "x", "values": ["0x16"]}, [], "NOT SEEN"),
            ({"type": "field_in", "bp": "b", "field": "x", "values": ["0x16", "0x1c"]}, h, "PASS"),
            ({"type": "field_in", "bp": "b", "field": "x", "values": ["0x16"]}, h, "FAIL"),
            ({"type": "field_any", "bp": "b", "field": "x", "values": ["0x16", "0x77"]}, h, "PASS"),
            ({"type": "field_absent", "bp": "b", "field": "x", "values": ["0x16"]}, h, "FAIL"),
            ({"type": "field_record", "bp": "b", "field": "x"}, h, "RECORDED"),
            ({"type": "pairs_record", "bp": "b", "fields": ["x"]}, h, "RECORDED"),
            ({"type": "tuple_seen", "bp": "b", "fields": {"x": "0x16"}}, h, "PASS"),
            ({"type": "tuple_seen", "bp": "b", "fields": {"x": 1}}, h, "FAIL"),
            ({"type": "bits_seen", "bp": "b", "field": "x", "bits": [1, 2, 3]}, h, "PASS"),
            ({"type": "bits_seen", "bp": "b", "field": "x", "bits": [9]}, h, "FAIL"),
            ({"type": "sequence", "bp": "b", "field": "x", "values": ["0x16", "0x1c"]}, h, "PASS"),
            ({"type": "sequence", "bp": "b", "field": "x", "values": ["0x1c", "0x16"]}, h, "FAIL"),
            ({"type": "manual", "note": "look"}, [], "MANUAL"),
            ({"type": "hit_rate", "bp": "b", "min": 1, "max": 2, "min_seconds": 100}, h, "NOT SEEN"),
        ]
        for item, rows, expected in cases:
            self.assertEqual(self.status(item, rows), expected, item)

    def test_sample_statuses(self):
        rows = [self.sample(0, "s", 100), self.sample(60, "s", 1908)]
        self.assertEqual(self.status({"type": "sample_rate", "sample": "s", "min": 29, "max": 31}, rows), "PASS")
        self.assertEqual(self.status({"type": "sample_rate", "sample": "s", "min": 1, "max": 2}, rows), "FAIL")
        self.assertEqual(self.status({"type": "sample_rate", "sample": "s", "min": 1, "max": 2}, []), "NOT SEEN")
        self.assertEqual(self.status({"type": "sample_changed", "sample": "s"}, rows), "PASS")
        self.assertEqual(self.status({"type": "sample_changed", "sample": "s"}, rows[:1]), "FAIL")
        self.assertEqual(self.status({"type": "sample_constant", "sample": "s", "value": 100}, rows[:1]), "PASS")
        self.assertEqual(self.status({"type": "sample_constant", "sample": "s"}, rows), "FAIL")
        self.assertEqual(self.status({"type": "sample_final", "sample": "s", "value": "$v"}, rows, {"v": "0x774"}), "PASS")
        self.assertEqual(self.status({"type": "sample_final", "sample": "s", "value": 1}, rows), "FAIL")
        self.assertEqual(self.status({"type": "sample_range", "sample": "f", "min": 29, "max": 31},
                                     [self.sample(0, "f", 30.0), self.sample(5, "f", 29.9)]), "PASS")
        group = [self.sample(0, "g[0]", 1), self.sample(0, "g[1]", 0), self.sample(1, "g[1]", 9)]
        self.assertEqual(self.status({"type": "sample_changed", "sample": "g"}, group), "PASS")
        self.assertEqual(self.status({"type": "sample_record", "sample": "nothing"}, []), "NOT SEEN")

    def test_an_unfinished_log_can_still_be_read(self):
        self.write(make_test(), [self.hit(1, x=1)])
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write('{"k": "hit", "t": 2, "bp": "st')
        lines = ws.summarize(self.path)
        self.assertTrue(any("the run died" in line for line in lines))
        self.assertTrue(any("1 log lines could not be read" in line for line in lines))

    def test_summary_stays_short_whatever_the_log(self):
        test = make_test(
            breakpoints=[{"id": f"b{i}", "kind": "exec", "address": f"{0x1000 + 4 * i:#x}"} for i in range(60)],
            expected=[{"type": "field_record", "bp": f"b{i}", "field": "x", "what": "x" * 300} for i in range(60)],
            not_possible=[f"reason {i}" for i in range(20)], mark_field="x")
        rows = []
        for i in range(200000):
            rows.append({"k": "hit", "t": i / 100, "bp": f"b{i % 60}", "mod": "rel_story", "us": i, "f": {"x": i}})
        rows += [self.sample(i, f"s{i}", i) for i in range(300)]
        rows += [{"k": "sample", "t": i + 1, "id": f"s{i}", "v": i + 1, "mod": "m"} for i in range(300)]
        rows += [{"k": "mark", "t": i, "text": "note " * 80} for i in range(500)]
        rows += [{"k": "warn", "t": i, "text": "warning " * 80} for i in range(500)]
        rows += [{"k": "module", "t": i, "ev": "load", "module": f"rel_{i}", "base": 0x08800000 + i * 256, "size": 1} for i in range(300)]
        rows += [{"k": "edit", "t": i, "id": "E", "address": 16, "size": 2, "old": 1, "new": 2} for i in range(100)]
        self.write(test, rows)
        self.assertGreater(self.path.stat().st_size, 15_000_000)
        lines = ws.summarize(self.path)
        self.assertLessEqual(len(lines), 100)
        self.assertLessEqual(max(map(len, lines)), ws.SUMMARY_LINE_WIDTH)
        joined = "\n".join(lines)
        self.assertIn("warnings (500)", joined)  # the short sections come before the long ones
        self.assertIn("memory edits", joined)

    def test_marks_list_the_values_since_the_previous_mark(self):
        test = make_test(mark_field="x", breakpoints=[{"id": "b", "kind": "exec", "address": "0x1000"}])
        self.write(test, [self.hit(1, x=0x16), {"k": "mark", "t": 2, "text": "battle"},
                          self.hit(3, x=0x1C), {"k": "mark", "t": 4, "text": "effect"}])
        lines = ws.summarize(self.path)
        self.assertTrue(any("battle <- 0x16" in line for line in lines), lines)
        self.assertTrue(any("effect <- 0x1c" in line for line in lines), lines)


class LogLineTests(unittest.TestCase):
    def test_execute_line(self):
        hit = ws.parse_log_message("BKP PC=09ccaae4: tf3 G1.ev us=0000abcd code=00000016 ra=09c15864\n")
        self.assertEqual((hit["test"], hit["bp"], hit["us"], hit["f"]["code"], hit["f"]["ra"]),
                         ("G1", "ev", 0xABCD, 0x16, 0x09C15864))

    def test_memory_line(self):
        hit = ws.parse_log_message("CHK Write16(CPU) at 08ac0000: tf3 G2.stage_step us=00000001 pc=08800000")
        self.assertEqual((hit["access"], hit["at"], hit["f"]["pc"]), ("Write16", 0x08AC0000, 0x08800000))

    def test_foreign_lines(self):
        self.assertIsNone(ws.parse_log_message("BKP PC=09ccaae4: cmd op=1"))
        self.assertIsNone(ws.parse_log_message("CHK Write32(CPU) at 08ac0000 (x), PC=08800000 (y)"))


class PortTests(unittest.TestCase):
    NETSTAT = ("  Proto  Local Address          Foreign Address        State           PID\n"
               "  TCP    0.0.0.0:135            0.0.0.0:0              LISTENING       1000\n"
               "  TCP    [::]:58366             [::]:0                 LISTENING       4242\n"
               "  TCP    127.0.0.1:50000        127.0.0.1:50001        ESTABLISHED     4242\n"
               "  TCP    0.0.0.0:51000          0.0.0.0:0              LISTENING       4242\n"
               "  UDP    0.0.0.0:53             *:*                                    4242\n")

    def test_netstat_keeps_the_listening_ports_of_ppsspp(self):
        self.assertEqual(ws.parse_netstat(self.NETSTAT, {"4242"}), [58366, 51000])

    def test_tasklist(self):
        text = '"System","4","Services","0","24 K"\n"PPSSPPWindows64.exe","4242","Console","1","400,000 K"\n'
        self.assertEqual(ws.parse_tasklist(text), {"4242"})

    def test_ini(self):
        with tempfile.TemporaryDirectory() as temp:
            ini = Path(temp) / "ppsspp.ini"
            ini.write_text("[General]\nEnable Logging = True\nRemoteISOPort = 58366\nRemoteDebuggerOnStartup = False\nOther = 1\n", encoding="utf-8")
            values = ws.read_ini(ini)
            self.assertEqual(values, {"Enable Logging": "True", "RemoteISOPort": "58366", "RemoteDebuggerOnStartup": "False"})
            self.assertEqual(ws.candidate_ports(1234, ini), [(1234, "--port")])
            ports = [port for port, _ in ws.candidate_ports(None, ini)]
            self.assertEqual(ports[0], 58366)

    def test_missing_ini(self):
        self.assertEqual(ws.read_ini(None), {})


class ModuleBaseTests(unittest.TestCase):
    def test_bases_accumulate_across_runs(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "module-bases.csv"
            first = {("rel_quiz", 0x09000000): {"name": "modquiz", "size": 0x1000, "loads": 2, "first": "a", "last": "b"}}
            second = {("rel_quiz", 0x09000000): {"name": "modquiz", "size": 0x1000, "loads": 1, "first": "c", "last": "d"},
                      ("rel_story", 0x08E9AA00): {"name": "modstory", "size": 0x2000, "loads": 1, "first": "c", "last": "d"}}
            ws.merge_module_bases(path, first)
            ws.merge_module_bases(path, second)
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[0], "module,info_name,base,size,loads,first_seen,last_seen,documented_base")
            self.assertEqual(lines[1], "rel_quiz,modquiz,0x09000000,0x1000,3,a,d,")
            self.assertEqual(lines[2], "rel_story,modstory,0x08e9aa00,0x2000,1,c,d,0x08e9aa00")


class DefinitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tests = ws.load_tests()

    def test_the_requested_tests_exist(self):
        self.assertEqual(set(self.tests), {"E7", "G1", "E23", "G2", "G3", "E15", "G5", "G6", "G7"})

    def test_addresses_match_the_registry(self):
        registry = ws.load_registry()
        for test in self.tests.values():
            self.assertEqual(ws.check_registry(test, registry), [])

    def test_instructions_are_written_and_limits_stated(self):
        for test in self.tests.values():
            self.assertTrue(test["instructions_pt"], test["id"])
            self.assertTrue(test["not_possible"], test["id"])

    def test_no_definition_presses_or_navigates(self):
        text = json.dumps(self.tests).lower()
        for word in ("input.", "buttons.send", "game.reset"):
            self.assertNotIn(word, text)

    def test_e7_expects_what_the_hand_run_found(self):
        items = {item["type"]: item for item in self.tests["E7"]["expected"]}
        self.assertTrue(items["sample_rate"]["min"] <= 1808 / 60 <= items["sample_rate"]["max"])
        self.assertEqual(items["sample_constant"]["value"], 0)
        self.assertTrue(items["sample_range"]["min"] <= 30 <= items["sample_range"]["max"])

    def test_g1_lists_the_52_call_sites(self):
        item = next(i for i in self.tests["G1"]["expected"] if i["type"] == "field_in")
        self.assertEqual(len(set(item["values"])), 52)

    def test_edits_only_where_the_plan_names_them(self):
        self.assertEqual([t["id"] for t in self.tests.values() if t.get("edits")], ["G2"])

    def test_the_tool_never_sends_a_memory_read(self):
        self.assertFalse([event for event in ws.ALLOWED_EVENTS if event.startswith("memory.read")])


class CommandTests(Harness):
    def run_main(self, *argv):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = ws.main(["--port", str(self.fake.port), *argv])
        return code, output.getvalue()

    def test_check(self):
        self.fake.modules = [STORY, inactive(TITLE), dict(ENGINE, address=0x09BE1500)]
        code, text = self.run_main("check")
        self.assertEqual(code, 0)
        for expected in ("PPSSPP: v1.20.4", "ULES01183", "r=1", "rel_story", "= documented", "!= documented 0x09be1400"):
            self.assertIn(expected, text)
        self.assertNotIn("rel_title", text)

    def test_run_and_summary(self):
        self.fake.modules = [STORY]
        code, text = self.run_main("run", "E7", "--duration", "0.2", "--out", self.temp.name)
        self.assertEqual(code, 0)
        self.assertIn("O que fazer", text)
        self.assertIn("result:", text)
        log = next(Path(self.temp.name).glob("*-E7.jsonl"))
        self.assertTrue(log.with_suffix(".summary.txt").is_file())
        self.assertTrue((Path(self.temp.name) / "module-bases.csv").is_file())
        self.assertEqual((self.fake.cpu_bps, self.fake.mem_bps), ({}, {}))
        code, text = self.run_main("summary", str(log))
        self.assertIn("E7", text)

    def test_watch_modules(self):
        self.fake.modules = [STORY, {"name": "modquiz", "address": 0x09100000, "size": 0x1000, "isActive": True}]
        code, text = self.run_main("watch-modules", "--duration", "0.15", "--out", self.temp.name)
        self.assertEqual(code, 0)
        self.assertIn("rel_quiz at 0x09100000", text)
        csv_text = (Path(self.temp.name) / "module-bases.csv").read_text(encoding="utf-8")
        self.assertIn("rel_quiz,modquiz,0x09100000", csv_text)

    def test_a_real_process_interrupted_removes_its_breakpoints(self):
        """Real signal, real blocked stdin thread: what an in-process test cannot show."""
        self.fake.modules = [STORY]
        creation = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        process = subprocess.Popen(
            [sys.executable, "-I", str(TOOLS / "ppsspp_ws.py"), "--port", str(self.fake.port), "run", "E7",
             "--out", self.temp.name], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            creationflags=creation)
        try:
            deadline = time.monotonic() + 15
            while 0x088359F4 not in self.fake.cpu_bps:
                self.assertLess(time.monotonic(), deadline, "the process never armed")
                time.sleep(0.02)
            process.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)
            output, _ = process.communicate(timeout=15)
        finally:
            process.kill()
        self.assertEqual(process.returncode, 0, output)
        self.assertEqual((self.fake.cpu_bps, self.fake.mem_bps), ({}, {}))
        self.assertIn(b"ended: Ctrl+C", output)

    def test_unreachable_port(self):
        port = self.fake.port
        self.fake.close()
        with self.assertRaises(SystemExit) as caught:
            ws.main(["--port", str(port), "check"])
        self.assertIn("Allow remote debugger", str(caught.exception))

    def test_list(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(ws.main(["list", "--check"]), 0)
        self.assertIn("G1", output.getvalue())
        self.assertNotIn("PROBLEM", output.getvalue())


if __name__ == "__main__":
    unittest.main()
