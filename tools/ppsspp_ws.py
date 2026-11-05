#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Hybrid PPSSPP runs: the maintainer plays, this client watches through the WebSocket debugger.

  ppsspp_ws.py check                     connect, print version, game id and loaded modules
  ppsspp_ws.py list [--check]            available tests (--check: validate against re/functions.csv)
  ppsspp_ws.py run TEST [--allow-edits]  arm a test while its module is loaded, log, summarise
  ppsspp_ws.py watch-modules             log every module load (name, base) until stopped
  ppsspp_ws.py summary LOG               short summary of a run log

Runs on the standard library, so it works under `python -I`. It speaks RFC 6455 to
ws://127.0.0.1:<port>/debugger, subprotocol debugger.ppsspp.org (PPSSPP v1.20.4, Core/Debugger/
WebSocket/*.cpp). Test definitions are data: tools/ppsspp_tests/*.json. Everything the client writes
goes to build/ppsspp-runs/ (git-ignored). Set-up and limits: docs/verification/ppsspp-plan.md,
"Hybrid runs".

Three rules are enforced at one choke point (check_request), whatever a definition asks for:
  - nothing presses buttons or navigates: only the events in ALLOWED_EVENTS are ever sent;
  - the game's save key at 0x08879068 is never read or used: any request that touches it is refused;
  - memory is written only with --allow-edits, and every edit is logged (address, old, new).

Not yet tried against a live PPSSPP: written from the source of v1.20.4 and tested on a fake server.
"""

import argparse
import ast
import base64
import bisect
import collections
import csv
import hashlib
import json
import os
import queue
import re
import signal
import socket
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = Path(__file__).resolve().parent / "ppsspp_tests"
DEFAULT_OUT = REPO_ROOT / "build" / "ppsspp-runs"
INI_RELATIVE = Path("external/ppsspp/memstick/PSP/SYSTEM/ppsspp.ini")

SUBPROTOCOL = "debugger.ppsspp.org"
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
EXPECTED_VERSION_PREFIX = "v1.20"
GAME_ID = "ULES01183"
LOG_TAG = "tf3"

# The 16-byte key the game hands to the savedata utility (docs/platform-api.md). Never read or used.
SAVE_KEY_START = 0x08879068
SAVE_KEY_END = SAVE_KEY_START + 16

# S = save-state address (ppsspp-plan.md, M2): 0x08aa5794 + 4 * [0x08ac18c0].
STATE_BASE = 0x08AA5794
STATE_SHIFT_WORD = 0x08AC18C0
SNAPSHOT_DEPTH = 0x09E27FEE  # u16: non-zero while the AI simulates (ppsspp-plan.md, policy rule 3)

MEMORY_WRITE_EVENTS = {"memory.write_u8": 1, "memory.write_u16": 2, "memory.write_u32": 4}
# Deliberately absent: memory.read* (stops the core, and spins forever if the core is not running;
# reads go through cpu.evaluate), input.* and game.reset (navigation), cpu.setReg.
ALLOWED_EVENTS = {
    "version", "game.status", "cpu.status", "cpu.evaluate", "cpu.stepping", "cpu.resume",
    "cpu.breakpoint.add", "cpu.breakpoint.update", "cpu.breakpoint.remove", "cpu.breakpoint.list",
    "memory.breakpoint.add", "memory.breakpoint.remove", "memory.breakpoint.list",
    "hle.module.list", "hle.backtrace", "gpu.stats.get",
} | set(MEMORY_WRITE_EVENTS)

REFERENCES = set(
    "zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 "
    "gp sp fp ra pc hi lo usec ticks threadid".split())

# Module-info name -> file. Not always mod<name>: see modules.py list. modtemplate is shared.
MODULE_FILES = {
    "modblackjack": "rel_blackjack", "modcardalbum": "rel_cardalbum", "modcharalist": "rel_charalist",
    "modconnection": "rel_connection", "modconv_machine": "rel_conv_machine",
    "moddebug_menu": "rel_debug_menu", "moddeck": "rel_deck", "moddeck_swap": "rel_deckswap",
    "moddeck_tutorial": "rel_decktutorial", "moddodge": "rel_dodge", "modduel_draw": "rel_duel_draw",
    "modduel_eng": "rel_duel_eng", "modduel_mgr": "rel_duel_mgr", "modduelrecord": "rel_duelrecord",
    "modfield": "rel_field", "modgallery": "rel_gallery", "module_htmlview": "rel_html_view",
    "modlabo": "rel_labo", "modlimitlist": "rel_limitlist", "modpassword": "rel_password",
    "modquiz": "rel_quiz", "modrecipe_viewer": "rel_recipeviewer", "modreversi": "rel_reversi",
    "modselect_card": "rel_select_card", "modshop": "rel_shop", "modstory": "rel_story",
    "modthrow": "rel_throw", "modthrow_starter": "rel_throw_starter", "modtitle": "rel_title",
    "modtutorial": "rel_tutorial", "modtutoriallist": "rel_tutoriallist",
    "modumd_replace": "rel_umd_replace", "modunderground": "rel_underground",
    "modusb_connect": "rel_usb_connect",
}
MODTEMPLATE_SPLIT = 10_000_000  # memory size: rel_cutin_viewer 14,950,864; rel_movie_viewer 4,765,824

# Bases of docs/subsystems/modules.md, "Runtime bases". Addresses in the definitions assume them.
DOCUMENTED_BASES = {
    "rel_duel_eng": 0x09BE1400, "rel_duel_draw": 0x0983FB00, "rel_duel_mgr": 0x08E9AA00,
    "rel_story": 0x08E9AA00, "rel_title": 0x08E9AA00, "rel_deck": 0x08E9AA00,
    "rel_field": 0x090CED00, "rel_shop": 0x090CED00, "rel_charalist": 0x09EEE400,
}

ALWAYS = "BOOT"  # a breakpoint or sample with this module stays armed for the whole run
DEFAULT_MAX_PER_SECOND = 20  # raw log lines per breakpoint and second, repeats beyond it are counted
HARD_MAX_PER_SECOND = 200  # same, for hits that differ from the previous one
DEFAULT_MAX_DISTINCT = 2000  # distinct value sets kept per breakpoint
DEFAULT_MAX_PAUSES = 20  # a pausing breakpoint turns log-only after this many hits
SUMMARY_MAX_LINES = 100
SUMMARY_LINE_WIDTH = 170
SEQUENCE_CAP = 4000
VALUE_CAP = 4096

ITEM_TYPES = {
    "hits", "hit_rate", "field_in", "field_seen", "field_any", "field_absent", "tuple_seen",
    "field_record", "pairs_record", "bits_seen", "sequence", "sample_rate", "sample_range",
    "sample_constant", "sample_final", "sample_changed", "sample_record", "modules_record", "manual",
}


class Refused(Exception):
    """The request breaks one of the tool's rules. Nothing was sent."""


class DebuggerError(Exception):
    """PPSSPP answered with an error event."""


class ConnectionClosed(Exception):
    """The WebSocket is gone."""


def parse_int(value):
    return value if isinstance(value, int) else int(str(value), 0)


# ---------------------------------------------------------------------------------------------
# Guard: everything sent to PPSSPP passes check_request.
# ---------------------------------------------------------------------------------------------

def overlaps_save_key(address, size=1):
    """True if [address, address + size) touches the key, in any of the PSP's RAM mirrors."""
    start = address & 0x3FFFFFFF
    return start < SAVE_KEY_END and start + max(size, 1) > SAVE_KEY_START


TOKEN_RE = re.compile(
    r"\s*(0[xX][0-9a-fA-F]+|[0-9]+|[A-Za-z_@$][A-Za-z0-9_.]*|<<|>>|>=|<=|==|!=|&&|\|\||"
    r"[-+*/%~!&|^<>?:()\[\],])")


def tokenize(expression):
    tokens, position = [], 0
    text = expression.rstrip()
    while position < len(text):
        match = TOKEN_RE.match(text, position)
        if not match:
            raise Refused(f"cannot parse expression {expression!r} at {text[position:position + 12]!r}")
        tokens.append(match.group(1))
        position = match.end()
    return tokens


def _fold_node(node):
    if isinstance(node, ast.Expression):
        return _fold_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    if isinstance(node, ast.UnaryOp):
        value = _fold_node(node.operand)
        if isinstance(node.op, ast.Invert):
            return ~value
        if isinstance(node.op, ast.USub):
            return -value
        if isinstance(node.op, ast.UAdd):
            return value
    if isinstance(node, ast.BinOp):
        left, right = _fold_node(node.left), _fold_node(node.right)
        operators = {ast.Add: lambda: left + right, ast.Sub: lambda: left - right,
                     ast.Mult: lambda: left * right, ast.Div: lambda: left // right,
                     ast.Mod: lambda: left % right, ast.LShift: lambda: left << right,
                     ast.RShift: lambda: left >> right, ast.BitAnd: lambda: left & right,
                     ast.BitOr: lambda: left | right, ast.BitXor: lambda: left ^ right}
        if type(node.op) in operators:
            return operators[type(node.op)]()
    raise ValueError("not a constant expression")


def const_eval(expression):
    """Value of an expression made of numbers and arithmetic only, as a u32."""
    tokens = expression if isinstance(expression, list) else tokenize(expression)
    if any(t[0].isalpha() or t[0] in "_@$" for t in tokens):
        raise ValueError(f"not constant: {' '.join(tokens)}")
    try:
        return _fold_node(ast.parse(" ".join(tokens), mode="eval")) & 0xFFFFFFFF
    except (SyntaxError, ValueError, ZeroDivisionError) as error:
        raise ValueError(f"not constant: {' '.join(tokens)}") from error


def _check_memory_operand(tokens):
    size, operand = 4, tokens
    if "," in tokens:
        split = tokens.index(",")
        operand = tokens[:split]
        try:
            size = const_eval(tokens[split + 1:])
        except ValueError as error:
            raise Refused(f"memory read size must be constant: {' '.join(tokens)}") from error
    try:
        address = const_eval(operand)
    except ValueError as error:
        raise Refused(f"memory read with a computed address, which cannot be checked before PPSSPP "
                      f"runs it: [{' '.join(tokens)}]. Use a constant address.") from error
    if overlaps_save_key(address, size):
        raise Refused(f"refused: {address:#010x} touches the save key at {SAVE_KEY_START:#010x}")


def check_expression(expression):
    """Refuse anything that could read the save key, or that PPSSPP would read differently."""
    tokens = tokenize(expression)
    depth_start = None
    for index, token in enumerate(tokens):
        if token[0].isdigit():
            if not token.lower().startswith("0x") and len(token) > 1:
                raise Refused(f"bare number {token} in {expression!r}: PPSSPP reads it as hexadecimal; "
                              f"write 0x{token} or the decimal value in hex")
            if overlaps_save_key(int(token, 0)):
                raise Refused(f"refused: {token} is the save key at {SAVE_KEY_START:#010x}")
        elif token[0].isalpha() or token[0] in "_@$":
            if token.lower() not in REFERENCES:
                raise Refused(f"unknown name {token!r} in {expression!r}: only registers are allowed")
        elif token == "[":
            if depth_start is not None:
                raise Refused(f"nested memory read in {expression!r}")
            depth_start = index
        elif token == "]":
            if depth_start is None:
                raise Refused(f"unbalanced ] in {expression!r}")
            _check_memory_operand(tokens[depth_start + 1:index])
            depth_start = None
    if depth_start is not None:
        raise Refused(f"unbalanced [ in {expression!r}")


def check_log_format(text):
    position = 0
    while True:
        opening = text.find("{", position)
        if opening < 0:
            return
        closing = text.find("}", opening)
        if closing < 0:
            raise Refused(f"unbalanced {{ in log format {text!r}")
        inner = text[opening + 1:closing]
        if len(inner) > 2 and inner[-2] == ":":
            if inner[-1] in "sp":
                raise Refused(f"log format {{{inner}}} reads memory through a pointer; not allowed")
            if inner[-1] in "xdf":
                inner = inner[:-2]
        if inner:
            check_expression(inner)
        position = closing + 1


def check_request(event, params, allow_edits=False):
    """The single point every outgoing request passes. Raises Refused; nothing is sent then."""
    if event not in ALLOWED_EVENTS:
        raise Refused(f"event {event} is not allowed: this tool does not press buttons, navigate "
                      f"or read memory blocks")
    if event in MEMORY_WRITE_EVENTS and not allow_edits:
        raise Refused(f"{event}: memory edits are off; pass --allow-edits")
    if "address" in params:
        size = MEMORY_WRITE_EVENTS.get(event, parse_int(params.get("size", 4)))
        if overlaps_save_key(parse_int(params["address"]), size):
            raise Refused(f"refused: {parse_int(params['address']):#010x} touches the save key at "
                          f"{SAVE_KEY_START:#010x}")
    for key in ("expression", "condition"):
        if params.get(key):
            check_expression(str(params[key]))
    if params.get("logFormat"):
        check_log_format(str(params["logFormat"]))


# ---------------------------------------------------------------------------------------------
# RFC 6455 client
# ---------------------------------------------------------------------------------------------

class WebSocket:
    """Minimal client: masked text frames out; text, fragments, ping and close in."""

    def __init__(self, host, port, timeout=3.0, path="/debugger"):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.buffer = bytearray()
        self.parts = None
        self.closed = False
        try:
            self._handshake(host, port, path, timeout)
        except Exception:
            self.sock.close()
            raise

    def _handshake(self, host, port, path, timeout):
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\n"
                   f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
                   f"Sec-WebSocket-Protocol: {SUBPROTOCOL}\r\n\r\n")
        self.sock.sendall(request.encode("ascii"))
        self.sock.settimeout(timeout)
        while b"\r\n\r\n" not in self.buffer:
            data = self.sock.recv(4096)
            if not data:
                raise ConnectionClosed("closed during the handshake")
            self.buffer += data
        header, _, rest = bytes(self.buffer).partition(b"\r\n\r\n")
        self.buffer = bytearray(rest)
        lines = header.decode("latin-1").split("\r\n")
        if " 101 " not in lines[0] + " ":
            raise ConnectionClosed(f"not a WebSocket answer: {lines[0]!r} (is 'Allow remote debugger' on?)")
        fields = {k.strip().lower(): v.strip() for k, _, v in (l.partition(":") for l in lines[1:])}
        accept = base64.b64encode(hashlib.sha1((key + WS_GUID).encode("ascii")).digest()).decode("ascii")
        if fields.get("sec-websocket-accept") != accept:
            raise ConnectionClosed("bad Sec-WebSocket-Accept")

    def _send_frame(self, opcode, payload):
        header = bytearray([0x80 | opcode])
        if len(payload) < 126:
            header.append(0x80 | len(payload))
        elif len(payload) < 0x10000:
            header += struct.pack(">BH", 0x80 | 126, len(payload))
        else:
            header += struct.pack(">BQ", 0x80 | 127, len(payload))
        mask = os.urandom(4)
        masked = bytes(byte ^ mask[index & 3] for index, byte in enumerate(payload))
        try:
            self.sock.settimeout(5.0)
            self.sock.sendall(bytes(header) + mask + masked)
        except OSError as error:
            self.closed = True
            raise ConnectionClosed(str(error)) from error

    def send_text(self, text):
        if self.closed:
            raise ConnectionClosed("socket closed")
        self._send_frame(1, text.encode("utf-8"))

    def _next_frame(self):
        data = self.buffer
        if len(data) < 2:
            return None
        fin, opcode = data[0] & 0x80, data[0] & 0x0F
        masked, length, offset = data[1] & 0x80, data[1] & 0x7F, 2
        if length == 126:
            if len(data) < 4:
                return None
            length, offset = struct.unpack_from(">H", data, 2)[0], 4
        elif length == 127:
            if len(data) < 10:
                return None
            length, offset = struct.unpack_from(">Q", data, 2)[0], 10
        mask = None
        if masked:
            if len(data) < offset + 4:
                return None
            mask, offset = bytes(data[offset:offset + 4]), offset + 4
        if len(data) < offset + length:
            return None
        payload = bytes(data[offset:offset + length])
        del data[:offset + length]
        if mask:
            payload = bytes(byte ^ mask[index & 3] for index, byte in enumerate(payload))
        return bool(fin), opcode, payload

    def recv(self, timeout):
        """One text message, or None when `timeout` seconds pass without one."""
        deadline = time.monotonic() + timeout
        while True:
            frame = self._next_frame()
            if frame is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                if self.closed:
                    raise ConnectionClosed("socket closed")
                self.sock.settimeout(max(remaining, 0.001))
                try:
                    data = self.sock.recv(65536)
                except socket.timeout:
                    return None
                except OSError as error:
                    self.closed = True
                    raise ConnectionClosed(str(error)) from error
                if not data:
                    self.closed = True
                    raise ConnectionClosed("PPSSPP closed the connection")
                self.buffer += data
                continue
            fin, opcode, payload = frame
            if opcode == 8:
                self.closed = True
                try:
                    self._send_frame(8, payload[:2])
                except ConnectionClosed:
                    pass
                raise ConnectionClosed("PPSSPP closed the connection")
            if opcode == 9:
                self._send_frame(10, payload)
            elif opcode in (0, 1):
                self.parts = bytearray(payload) if opcode == 1 else (self.parts or bytearray()) + payload
                if fin:
                    text = bytes(self.parts).decode("utf-8", "replace")
                    self.parts = None
                    return text

    def close(self):
        if not self.closed:
            try:
                self._send_frame(8, struct.pack(">H", 1000))
            except ConnectionClosed:
                pass
        self.closed = True
        try:
            self.sock.close()
        except OSError:
            pass


class Debugger:
    """Tickets, broadcasts and the guard on top of a WebSocket."""

    def __init__(self, ws, allow_edits=False, timeout=5.0):
        self.ws = ws
        self.allow_edits = allow_edits
        self.timeout = timeout
        self.next_ticket = 1
        self.replies = {}
        self.waiting = set()
        self.events = collections.deque()

    def pump(self, timeout):
        text = self.ws.recv(timeout)
        if text is None:
            return False
        try:
            message = json.loads(text, strict=False)
        except ValueError:
            return True
        ticket = message.get("ticket")
        if ticket is not None:
            if ticket in self.waiting:
                self.replies[ticket] = message
        else:
            self.events.append(message)
        return True

    def send(self, event, **params):
        """For events that answer with a broadcast or nothing (cpu.stepping, cpu.resume)."""
        check_request(event, params, self.allow_edits)
        self.ws.send_text(json.dumps({"event": event, **params}))

    def call(self, event, timeout=None, **params):
        check_request(event, params, self.allow_edits)
        ticket = f"t{self.next_ticket}"
        self.next_ticket += 1
        self.waiting.add(ticket)
        try:
            self.ws.send_text(json.dumps({"event": event, "ticket": ticket, **params}))
            deadline = time.monotonic() + (self.timeout if timeout is None else timeout)
            while ticket not in self.replies:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"{event}: no answer from PPSSPP")
                self.pump(min(remaining, 0.25))
            reply = self.replies.pop(ticket)
        finally:
            self.waiting.discard(ticket)
        if reply.get("event") == "error":
            raise DebuggerError(reply.get("message", "unknown error"))
        return reply

    def evaluate(self, expression):
        return self.call("cpu.evaluate", expression=expression)["uintValue"]

    def read(self, address, size=4):
        """A memory read that does not stop the core (memory.read_* does)."""
        return self.evaluate(f"[{address:#x},{size}]")


# ---------------------------------------------------------------------------------------------
# Finding PPSSPP
# ---------------------------------------------------------------------------------------------

def find_ini(explicit=None):
    if explicit:
        return Path(explicit)
    roots = [REPO_ROOT]
    if ".claude" in REPO_ROOT.parts:  # agent worktree: the local PPSSPP is in the main checkout
        roots.append(Path(*REPO_ROOT.parts[:REPO_ROOT.parts.index(".claude")]))
    for root in roots:
        if (root / INI_RELATIVE).is_file():
            return root / INI_RELATIVE
    return None


def read_ini(path):
    """The settings the client cares about, from ppsspp.ini (written by PPSSPP when it exits)."""
    values = {}
    if path and Path(path).is_file():
        for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() in ("RemoteISOPort", "RemoteDebuggerOnStartup", "Enable Logging"):
                values[key.strip()] = value.strip()
    return values


def parse_netstat(text, pids):
    """Listening TCP ports of the given process ids, from `netstat -ano` output."""
    ports = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) >= 5 and fields[0].upper() == "TCP" and fields[3].upper() == "LISTENING" \
                and fields[4] in pids:
            port = int(fields[1].rsplit(":", 1)[1])
            if port not in ports:
                ports.append(port)
    return ports


def parse_tasklist(text):
    pids = set()
    for row in csv.reader(text.splitlines()):
        if len(row) >= 2 and row[0].lower().startswith("ppsspp"):
            pids.add(row[1])
    return pids


def netstat_ports():
    if os.name != "nt":
        return []
    try:
        tasks = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True, timeout=10)
        pids = parse_tasklist(tasks.stdout)
        if not pids:
            return []
        netstat = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=15)
        return parse_netstat(netstat.stdout, pids)
    except (OSError, subprocess.SubprocessError):
        return []


def candidate_ports(port=None, ini=None):
    """(port, where it came from), best first. --port wins and is the only one tried."""
    if port:
        return [(port, "--port")]
    candidates = []
    text = read_ini(find_ini(ini)).get("RemoteISOPort", "0")
    ini_port = int(text) if text.isdigit() else 0
    if ini_port:
        candidates.append((ini_port, "RemoteISOPort in ppsspp.ini"))
    candidates += [(p, "netstat") for p in netstat_ports() if p != ini_port]
    return candidates


def connect(args, allow_edits=False):
    tried = []
    for port, source in candidate_ports(args.port, args.ini):
        try:
            ws = WebSocket(args.host, port)
        except (OSError, ConnectionClosed) as error:
            tried.append(f"{port} ({source}): {error}")
            continue
        print(f"connected: ws://{args.host}:{port}/debugger (port from {source})")
        return Debugger(ws, allow_edits=allow_edits)
    detail = "; ".join(tried) or "no candidate port (ppsspp.ini not found, PPSSPP not listening)"
    raise SystemExit(f"could not reach the PPSSPP debugger: {detail}\n"
                     "Is PPSSPP open with Settings > Tools > Developer tools > 'Allow remote debugger' "
                     "on? Use --port N to force a port.")


def module_file(name, size):
    if name == "modtemplate":
        return "rel_cutin_viewer" if size > MODTEMPLATE_SPLIT else "rel_movie_viewer"
    return MODULE_FILES.get(name, name)


def active_modules(debugger):
    """{file name: {name, base, size}} of the modules loaded now. PPSSPP also lists unloaded ones."""
    try:
        listing = debugger.call("hle.module.list").get("modules", [])
    except DebuggerError:
        return {}
    active = {}
    for entry in listing:
        if entry.get("isActive"):
            active[module_file(entry["name"], entry["size"])] = {
                "name": entry["name"], "base": entry["address"], "size": entry["size"]}
    return active


def read_state_address(debugger):
    shift = debugger.read(STATE_SHIFT_WORD)
    return shift, STATE_BASE + 4 * shift


# ---------------------------------------------------------------------------------------------
# Test definitions
# ---------------------------------------------------------------------------------------------

def substitute(text, env):
    """$name -> parameter, S -> the save-state address."""
    def parameter(match):
        if match.group(1) not in env:
            raise ValueError(f"unknown parameter ${match.group(1)} in {text!r}")
        return f"{parse_int(env[match.group(1)]):#x}"
    text = re.sub(r"\$(\w+)", parameter, str(text))
    return re.sub(r"(?<!\w)S(?!\w)", f"{env.get('S', STATE_BASE):#x}", text)


def gate_of(item, test):
    """Modules that must be loaded for this breakpoint or sample; [] means always."""
    module = item.get("module", test.get("required_module", ALWAYS))
    if module == ALWAYS:
        return []
    return [module] if isinstance(module, str) else list(module)


def uses_state_address(test):
    """True if any address or expression of the test depends on S."""
    texts = [bp["address"] for bp in test["breakpoints"]]
    texts += [bp.get("condition", "") for bp in test["breakpoints"]]
    texts += [expr for bp in test["breakpoints"] for expr in bp.get("record", {}).values()]
    texts += [sample.get("address", "") for sample in test["samples"]]
    texts += [edit["address"] for edit in test.get("edits", [])]
    return any(re.search(r"(?<!\w)S(?!\w)", str(text)) for text in texts)


def build_log_format(test, bp, env):
    parts = [f"{LOG_TAG} {test['id']}.{bp['id']} us={{usec}}"]
    parts += [f"{name}={{{substitute(expr, env)}}}" for name, expr in bp.get("record", {}).items()]
    return " ".join(parts)


def validate_test(test):
    """Raises ValueError or Refused. Everything a definition asks for is checked before a run."""
    for key in ("id", "title", "plan", "instructions_pt", "breakpoints", "samples", "expected", "not_possible"):
        if key not in test:
            raise ValueError(f"{test.get('id', '?')}: missing {key}")
    env = dict(test.get("params", {}), S=STATE_BASE)
    ids = set()
    for bp in test["breakpoints"]:
        if bp["id"] in ids:
            raise ValueError(f"{test['id']}: duplicate breakpoint {bp['id']}")
        ids.add(bp["id"])
        if bp.get("kind") not in ("exec", "memory"):
            raise ValueError(f"{test['id']}.{bp['id']}: kind must be exec or memory")
        if bp["kind"] == "memory" and bp.get("pause"):
            raise ValueError(f"{test['id']}.{bp['id']}: pausing memory breakpoints are not supported")
        address = const_eval(substitute(bp["address"], env))
        size = parse_int(bp.get("size", 4))
        check_request("cpu.breakpoint.add" if bp["kind"] == "exec" else "memory.breakpoint.add",
                      {"address": address, "size": size, "condition": bp.get("condition"),
                       "logFormat": build_log_format(test, bp, env)})
    samples = set()
    for sample in test["samples"]:
        if sample.get("kind") == "gpu_fps":
            samples.add(sample["id"])
            continue
        address = const_eval(substitute(sample["address"], env))
        count, stride = sample.get("count", 1), sample.get("stride", sample.get("size", 4))
        if sample.get("size", 4) not in (1, 2, 4):
            raise ValueError(f"{test['id']}.{sample['id']}: size must be 1, 2 or 4")
        for index in range(count):
            check_request("cpu.evaluate", {"expression": f"[{address + index * stride:#x},{sample.get('size', 4)}]"})
            samples.add(sample["id"] if count == 1 else f"{sample['id']}[{index}]")
        samples.add(sample["id"])
    for edit in test.get("edits", []):
        address = const_eval(substitute(edit["address"], env))
        if overlaps_save_key(address, edit["size"]):
            raise Refused(f"{test['id']}.{edit['id']}: touches the save key")
    for item in test["expected"]:
        if item.get("type") not in ITEM_TYPES:
            raise ValueError(f"{test['id']}: unknown expected type {item.get('type')}")
        if "bp" in item and item["bp"] not in ids:
            raise ValueError(f"{test['id']}: expected item names unknown breakpoint {item['bp']}")
        if "sample" in item and item["sample"] not in samples:
            raise ValueError(f"{test['id']}: expected item names unknown sample {item['sample']}")


def load_tests(directory=TESTS_DIR):
    tests = {}
    for path in sorted(Path(directory).glob("*.json")):
        test = json.loads(path.read_text(encoding="utf-8"))
        validate_test(test)
        tests[test["id"]] = test
    return tests


def load_registry(path=REPO_ROOT / "re" / "functions.csv"):
    registry = {}
    with open(path, encoding="utf-8", newline="") as handle:
        for row in csv.reader(line for line in handle if not line.startswith("#")):
            if len(row) >= 2 and row[0] != "id":
                size = row[4] if len(row) > 4 and row[4] else "0"
                registry[row[0].lower()] = (row[1], parse_int(size))
    return registry


def check_registry(test, registry):
    """Problems of a test's exec breakpoints against re/functions.csv (the registry is the truth)."""
    problems = []
    for bp in test["breakpoints"]:
        if bp["kind"] != "exec":
            continue
        address, function = parse_int(bp["address"]), bp.get("function")
        gate = bp.get("registry_module") or ""
        prefix = f"{gate}:" if gate else ""
        candidates = {name: (parse_int(key.split(":")[-1]), size) for key, (name, size) in registry.items()
                      if name == function and (key.startswith(prefix) if prefix else ":" not in key)}
        if function not in candidates:
            problems.append(f"{test['id']}.{bp['id']}: {function} not in the registry ({prefix or 'plain ids'})")
            continue
        start, size = candidates[function]
        if address != start and not (bp.get("inside") and start <= address < start + size):
            problems.append(f"{test['id']}.{bp['id']}: {address:#x} is not {function} at {start:#x}")
    return problems


# ---------------------------------------------------------------------------------------------
# A run
# ---------------------------------------------------------------------------------------------

HIT_RE = re.compile(
    r"^(?:BKP PC=(?P<pc>[0-9a-fA-F]{8})|CHK (?P<access>Read|Write)(?P<bits>\d+)\([^)]*\) at "
    r"(?P<address>[0-9a-fA-F]{8})): " + LOG_TAG + r" (?P<test>[^.\s]+)\.(?P<bp>\S+)(?P<rest>.*)$", re.S)


def parse_log_message(message):
    """A breakpoint log line of ours as {test, bp, us, f}, or None."""
    match = HIT_RE.match(message.strip())
    if not match:
        return None
    fields = {}
    for token in match.group("rest").split():
        name, _, value = token.partition("=")
        try:
            fields[name] = int(value, 16)
        except ValueError:
            continue
    hit = {"test": match.group("test"), "bp": match.group("bp"), "us": fields.pop("us", None), "f": fields}
    if match.group("access"):
        hit["access"] = f"{match.group('access')}{match.group('bits')}"
        hit["at"] = int(match.group("address"), 16)
    return hit


class Stats:
    """Rate limiter and deduplicator of one breakpoint. Every distinct value set reaches the log."""

    def __init__(self, bp):
        self.volatile = set(bp.get("volatile", []))
        self.max_per_second = bp.get("max_per_second", DEFAULT_MAX_PER_SECOND)
        self.max_distinct = bp.get("max_distinct", DEFAULT_MAX_DISTINCT)
        self.seen = set()
        self.last_key = None
        self.window = None
        self.written = 0
        self.repeats = collections.Counter()
        self.overflow = 0
        self.last_hit = None
        self.pauses = 0

    def key(self, fields):
        return tuple(sorted((k, v) for k, v in fields.items() if k not in self.volatile))

    def admit(self, hit, now):
        """True: write this hit to the log. False: it was only counted."""
        key = self.key(hit["f"])
        second = int(now)
        if second != self.window:
            self.window, self.written = second, 0
        new = key not in self.seen
        changed = key != self.last_key
        self.last_key, self.last_hit = key, hit
        if new and len(self.seen) >= self.max_distinct:
            self.overflow += 1
            return False
        if new:
            self.seen.add(key)
        limit = HARD_MAX_PER_SECOND if new or changed else self.max_per_second
        if self.written < limit:
            self.written += 1
            return True
        if new:
            self.seen.discard(key)
            self.overflow += 1
        else:
            self.repeats[key] += 1
        return False


class Session:
    """Arms and disarms by module, writes the raw log, cleans up whatever happens."""

    def __init__(self, debugger, test, log_path, params=None, poll=0.1, commands=None, clock=time.monotonic,
                 echo=print):
        self.dbg = debugger
        self.test = test
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log = open(self.log_path, "w", encoding="utf-8", newline="\n")
        self.env = dict(test.get("params", {}))
        self.env.update(params or {})
        self.poll = poll
        self.commands = commands if commands is not None else queue.Queue()
        self.clock = clock
        self.echo = echo
        self.start = clock()
        self.bps = {bp["id"]: bp for bp in test["breakpoints"]}
        self.stats = {bp_id: Stats(bp) for bp_id, bp in self.bps.items()}
        self.samples = [dict(s, next_due=0.0, last={}) for s in test["samples"]]
        self.edits = {e["id"]: e for e in test.get("edits", [])}
        self.active = {}
        self.armed = {}  # breakpoint id -> ("exec", address) or ("memory", address, size)
        self.foreign = set()
        self.pending = []  # hits waiting for the next module poll
        self.last_fields = {}
        self.pause_addresses = {}
        self.holding_pause = False
        self.warned = set()
        self.loads = {}  # (module, base) -> {name, size, loads, first}
        self.next_poll = 0.0
        self.next_flush = 0.0
        self.next_state_check = 0.0
        self.stop_reason = None
        self.uses_state = uses_state_address(test)
        self.checked_game = False

    # ---- output ------------------------------------------------------------------------------
    def now(self):
        return round(self.clock() - self.start, 3)

    def write(self, kind, **fields):
        self.log.write(json.dumps({"k": kind, "t": self.now(), **fields}, ensure_ascii=False) + "\n")
        self.log.flush()

    def warn(self, text, once=None):
        if once is not None:
            if once in self.warned:
                return
            self.warned.add(once)
        self.write("warn", text=text)
        self.echo(f"WARNING: {text}")

    # ---- modules and arming ------------------------------------------------------------------
    def poll_modules(self):
        active = active_modules(self.dbg)
        for name, info in active.items():
            before = self.active.get(name)
            if before is None or before["base"] != info["base"]:
                self.write("module", ev="load", module=name, name=info["name"], base=info["base"], size=info["size"])
                self.echo(f"+ {name} at {info['base']:#010x}")
                self.record_load(name, info)
                expected = DOCUMENTED_BASES.get(name)
                if expected is not None and expected != info["base"]:
                    self.warn(f"{name} loaded at {info['base']:#x}, documented {expected:#x}: addresses "
                              f"of this module are shifted for this run", once=("base", name, info["base"]))
        for name, info in self.active.items():
            if name not in active:
                self.write("module", ev="unload", module=name, base=info["base"])
                self.echo(f"- {name}")
        if active and not self.active:  # a game (re)started: whatever we armed before may be gone
            self.armed.clear()
            self.pause_addresses.clear()
        self.active = active
        self.commit_pending()
        self.check_game()
        if self.uses_state and "S" not in self.env:
            self.check_state_address()
        self.sync_arming()

    def record_load(self, name, info):
        entry = self.loads.setdefault((name, info["base"]), {
            "name": info["name"], "size": info["size"], "loads": 0, "first": time.strftime("%Y-%m-%d %H:%M:%S")})
        entry["loads"] += 1
        entry["last"] = time.strftime("%Y-%m-%d %H:%M:%S")

    def check_game(self):
        if self.checked_game or not self.active:
            return
        self.checked_game = True
        game = self.dbg.call("game.status").get("game") or {}
        self.write("game", id=game.get("id"), version=game.get("version"))
        if game.get("id") not in (None, GAME_ID):
            self.stop_reason = f"wrong game {game.get('id')}: the addresses are for {GAME_ID}"
            return
        self.read_foreign()

    def rebase_text(self, text, gate):
        """Shift literals inside a module's documented range when it loaded somewhere else."""
        for module in gate:
            info, documented = self.active.get(module), DOCUMENTED_BASES.get(module)
            if info is None or documented is None or documented == info["base"]:
                continue
            delta, size = info["base"] - documented, info["size"]

            def shift(match):
                value = int(match.group(0), 16)
                return f"{value + delta:#x}" if documented <= value < documented + size else match.group(0)
            return re.sub(r"0[xX][0-9a-fA-F]+", shift, text)
        return text

    def resolve(self, text, gate):
        return const_eval(self.rebase_text(substitute(text, self.env), gate))

    def wanted(self, item):
        gate = gate_of(item, self.test)
        return bool(self.active) and (not gate or any(module in self.active for module in gate))

    def read_foreign(self):
        """Breakpoints already in PPSSPP: keep the maintainer's, drop leftovers of a killed run."""
        for event, kind in (("cpu.breakpoint.list", "exec"), ("memory.breakpoint.list", "memory")):
            try:
                existing = self.dbg.call(event).get("breakpoints", [])
            except DebuggerError:
                continue
            for bp in existing:
                if (bp.get("logFormat") or "").startswith(LOG_TAG + " "):
                    params = {"address": bp["address"]}
                    if kind == "memory":
                        params["size"] = bp["size"]
                    self.dbg.call(event.replace(".list", ".remove"), **params)
                    self.write("stale", address=bp["address"])
                elif kind == "exec":
                    self.foreign.add(("exec", bp["address"]))
                else:
                    self.foreign.add(("memory", bp["address"], bp["size"]))

    def state_ready(self):
        return not self.uses_state or "S" in self.env

    def sync_arming(self):
        if not self.state_ready():
            return
        for bp_id, bp in self.bps.items():
            want = self.wanted(bp)
            if want and bp_id not in self.armed:
                self.arm(bp)
            elif not want and bp_id in self.armed:
                self.disarm(bp_id)

    def arm(self, bp):
        gate = gate_of(bp, self.test)
        try:
            address = self.resolve(bp["address"], gate)
            log_format = self.rebase_text(build_log_format(self.test, bp, self.env), gate)
            params = {"address": address, "log": True, "enabled": bool(bp.get("pause")), "logFormat": log_format}
            if bp.get("condition"):
                params["condition"] = self.rebase_text(substitute(bp["condition"], self.env), gate)
            if bp["kind"] == "exec":
                key, event = ("exec", address), "cpu.breakpoint.add"
            else:
                size = parse_int(bp.get("size", 4))
                access = bp.get("access", "write")
                params.update(size=size, read=access == "read", write=access in ("write", "change"),
                              change=access == "change")
                key, event = ("memory", address, size), "memory.breakpoint.add"
            if key in self.foreign:
                self.warn(f"{bp['id']}: a breakpoint of yours is at {address:#x}; not replacing it, so "
                          f"this breakpoint stays off", once=("foreign", bp["id"]))
                return
            self.check_format(log_format, bp["id"])
            self.dbg.call(event, **params)
        except (DebuggerError, ValueError, TimeoutError) as error:
            self.warn(f"{bp['id']}: could not arm: {error}", once=("arm", bp["id"]))
            return
        self.armed[bp["id"]] = key
        if bp.get("pause"):
            self.pause_addresses[address] = bp["id"]
        self.write("arm", bp=bp["id"], address=address, module=self.module_tag(gate))

    def check_format(self, log_format, bp_id):
        """PPSSPP does not validate logFormat when adding; a bad one would cut every line short."""
        for expression in re.findall(r"\{([^{}]*)\}", log_format):
            self.dbg.call("cpu.evaluate", expression=re.sub(r":[xdf]$", "", expression))

    def disarm(self, bp_id):
        key = self.armed[bp_id]
        params = {"address": key[1]}
        if key[0] == "memory":
            params["size"] = key[2]
        event = "cpu.breakpoint.remove" if key[0] == "exec" else "memory.breakpoint.remove"
        try:
            self.dbg.call(event, **params)
        except (DebuggerError, TimeoutError) as error:
            self.warn(f"{bp_id}: could not remove: {error}", once=("remove", bp_id))
            return False
        del self.armed[bp_id]
        self.pause_addresses.pop(key[1], None)
        self.write("disarm", bp=bp_id, address=key[1])
        return True

    def module_tag(self, gate):
        loaded = [m for m in gate if m in self.active] if gate else sorted(self.active)
        return "+".join(loaded) or ALWAYS

    # ---- hits --------------------------------------------------------------------------------
    def on_log(self, message):
        hit = parse_log_message(message.get("message", ""))
        if hit is None or hit["test"] != self.test["id"] or hit["bp"] not in self.bps:
            return
        hit["t"] = self.now()
        joined = self.bps[hit["bp"]].get("join")
        if joined:  # the arguments are gone at a return: take them from the entry hit just before
            hit["f"] = {**self.last_fields.get(joined, {}), **hit["f"]}
        self.last_fields[hit["bp"]] = hit["f"]
        gate = gate_of(self.bps[hit["bp"]], self.test)
        hit["mod"] = self.module_tag(gate)
        if gate:
            # The module may already be gone: a hit is only trusted once the next poll confirms it.
            self.pending.append((hit, gate, self.module_key(gate)))
        else:
            self.commit(hit, False)

    def module_key(self, gate):
        return tuple((m, self.active[m]["base"]) for m in gate if m in self.active)

    def commit_pending(self):
        pending, self.pending = self.pending, []
        for hit, gate, key in pending:
            self.commit(hit, self.module_key(gate) != key or not key)

    def commit(self, hit, suspect):
        record = {"bp": hit["bp"], "us": hit["us"], "mod": hit["mod"], "f": hit["f"]}
        if "access" in hit:
            record.update(access=hit["access"], at=hit["at"])
        if suspect:
            record["suspect"] = True
            self.log.write(json.dumps({"k": "hit", "t": hit["t"], **record}) + "\n")
            return
        if self.stats[hit["bp"]].admit(hit, hit["t"]):
            self.log.write(json.dumps({"k": "hit", "t": hit["t"], **record}) + "\n")

    def flush_repeats(self):
        for bp_id, stats in self.stats.items():
            if stats.repeats or stats.overflow:
                last = stats.last_hit
                self.write("dup", bp=bp_id, overflow=stats.overflow,
                           items=[{"f": dict(key), "n": count} for key, count in stats.repeats.items()],
                           last={"t": last["t"], "f": last["f"], "mod": last["mod"]} if last else None)
                stats.repeats.clear()
                stats.overflow = 0
        self.log.flush()

    # ---- pausing breakpoints -----------------------------------------------------------------
    def on_stepping(self, event):
        address = event.get("relatedAddress")
        if event.get("reason") != "cpu.breakpoint" or address not in self.pause_addresses:
            return  # the maintainer's break, a savestate, the pause key: not ours to resume
        bp_id = self.pause_addresses[address]
        bp = self.bps[bp_id]
        self.holding_pause = True
        started = self.clock()
        try:
            fields = {name: self.dbg.evaluate(substitute(expr, self.env)) for name, expr in bp.get("record", {}).items()}
            frames = []
            if bp.get("backtrace"):
                frames = [frame.get("pc") for frame in self.dbg.call("hle.backtrace").get("frames", [])[:8]]
            self.write("pause", bp=bp_id, f=fields, frames=frames, ms=round((self.clock() - started) * 1000))
        except (DebuggerError, TimeoutError) as error:
            self.warn(f"{bp_id}: reading during the pause failed: {error}", once=("pause", bp_id))
        finally:
            self.dbg.send("cpu.resume")
            self.holding_pause = False
        stats = self.stats[bp_id]
        stats.pauses += 1
        if stats.pauses >= bp.get("max_pauses", DEFAULT_MAX_PAUSES):
            self.pause_addresses.pop(address, None)
            self.dbg.call("cpu.breakpoint.update", address=address, enabled=False, log=True)
            self.warn(f"{bp_id}: {stats.pauses} pauses reached, now log-only")

    # ---- samples -----------------------------------------------------------------------------
    def run_samples(self, now):
        for sample in self.samples:
            if now < sample["next_due"] or not self.wanted(sample) or not self.state_ready():
                continue
            sample["next_due"] = now + sample.get("every_s", 0.5)
            try:
                if sample.get("kind") == "gpu_fps":
                    self.store_sample(sample, sample["id"], 0, round(
                        self.dbg.call("gpu.stats.get", timeout=2.0)["fps"]["actual"], 2))
                    continue
                gate = gate_of(sample, self.test)
                address = self.resolve(sample["address"], gate)
                size = sample.get("size", 4)
                count = sample.get("count", 1)
                stride = sample.get("stride", size)
                for index in range(count):
                    name = sample["id"] if count == 1 else f"{sample['id']}[{index}]"
                    self.store_sample(sample, name, index, self.dbg.read(address + index * stride, size))
            except (DebuggerError, TimeoutError) as error:
                self.warn(f"sample {sample['id']}: {error}", once=("sample", sample["id"]))

    def store_sample(self, sample, name, index, value):
        if sample.get("always") or sample["last"].get(index) != value:
            sample["last"][index] = value
            self.write("sample", id=name, v=value, mod=self.module_tag(gate_of(sample, self.test)))

    def check_state_address(self):
        if not self.uses_state or not self.active:
            return
        try:
            shift, state = read_state_address(self.dbg)
        except DebuggerError:
            return
        if shift > 15:
            self.warn(f"[0x08ac18c0] = {shift}, expected 0-15: S is not valid yet", once=("shift", shift))
            return
        if self.env.get("S") != state:
            changed = "S" in self.env
            self.env["S"] = state
            self.write("state", r=shift, S=state)
            if changed:  # a fresh boot or a savestate of another boot
                self.warn(f"S changed to {state:#x}: re-arming")
                for bp_id in list(self.armed):
                    self.disarm(bp_id)

    # ---- memory edits ------------------------------------------------------------------------
    def apply_edit(self, edit_id, overrides):
        if not self.dbg.allow_edits:
            self.echo("memory edits are off: restart with --allow-edits")
            return
        edit = self.edits.get(edit_id)
        if edit is None:
            self.echo(f"unknown edit {edit_id}; this test defines: {', '.join(self.edits) or 'none'}")
            return
        if not self.state_ready():
            self.echo("edit not made: S is not known yet")
            return
        env = {**self.env, **edit.get("params", {}), **overrides}
        address = const_eval(substitute(edit["address"], env))
        size = edit["size"]
        value = parse_int(substitute(edit["value"], env))
        paused_here = False
        try:
            if not self.dbg.call("cpu.status").get("stepping"):
                self.dbg.send("cpu.stepping")  # policy rule 3: edits only while paused
                paused_here = self.wait_stepping()
                if not paused_here:
                    self.echo("edit not made: emulation did not pause")
                    return
            if "rel_duel_eng" in self.active and self.dbg.read(SNAPSHOT_DEPTH, 2):
                self.echo("edit not made: the AI is simulating (snapshot depth is not 0), try later")
                return
            old = self.dbg.read(address, size)
            self.dbg.call(f"memory.write_u{size * 8}", address=address, value=value)
            new = self.dbg.read(address, size)
            self.write("edit", id=edit_id, address=address, size=size, old=old, new=new,
                       purpose=edit.get("purpose", ""), modules=sorted(self.active))
            self.echo(f"edit {edit_id}: {address:#010x} {old:#x} -> {new:#x}")
        except (DebuggerError, TimeoutError, Refused) as error:
            self.echo(f"edit not made: {error}")
        finally:
            if paused_here:
                self.dbg.send("cpu.resume")

    def wait_stepping(self):
        deadline = self.clock() + 2.0
        while self.clock() < deadline:
            if self.dbg.call("cpu.status").get("stepping"):
                return True
            self.dbg.pump(0.02)
        return False

    # ---- console commands --------------------------------------------------------------------
    def on_command(self, line):
        command, _, rest = line.strip().partition(" ")
        if command in ("q", "quit"):
            self.stop_reason = "stopped by the maintainer"
        elif command == "m" and rest:
            self.write("mark", text=rest)
            self.echo(f"marked at {self.now():.1f} s")
        elif command == "edit" and rest:
            words = rest.split()
            overrides = dict(word.split("=", 1) for word in words[1:] if "=" in word)
            self.apply_edit(words[0], overrides)
        elif command:
            self.echo("comandos: m <texto> (anota) | edit <id> [nome=valor] | q (termina)")

    # ---- main loop ---------------------------------------------------------------------------
    def drain_events(self):
        while self.dbg.events:
            event = self.dbg.events.popleft()
            name = event.get("event")
            if name == "log":
                self.on_log(event)
            elif name == "cpu.stepping":
                self.on_stepping(event)
            elif name == "game.quit":
                self.write("game_quit")

    def step(self):
        self.dbg.pump(0.02)
        self.drain_events()
        now = self.clock()
        if now >= self.next_poll:
            self.next_poll = now + self.poll
            self.poll_modules()
            self.run_samples(now)
        if now >= self.next_state_check:
            self.next_state_check = now + 1.0
            self.check_state_address()
        if now >= self.next_flush:
            self.next_flush = now + 1.0
            self.flush_repeats()
        while True:
            try:
                self.on_command(self.commands.get_nowait())
            except queue.Empty:
                break

    def begin(self):
        self.write("meta", format=1, test=self.test, env=self.env,
                   started=time.strftime("%Y-%m-%d %H:%M:%S"), ppsspp=self.ppsspp_version())

    def run(self, duration=None):
        self.begin()
        try:
            while self.stop_reason is None:
                if duration is not None and self.clock() - self.start >= duration:
                    self.stop_reason = "duration reached"
                    break
                self.step()
        except KeyboardInterrupt:
            self.stop_reason = "Ctrl+C"
        except ConnectionClosed as error:
            self.stop_reason = f"connection lost: {error}"
        except (TimeoutError, DebuggerError) as error:
            self.stop_reason = f"PPSSPP stopped answering: {error}"
        finally:
            self.cleanup()
        return self.stop_reason

    def ppsspp_version(self):
        try:
            return self.dbg.call("version", name="tf3-ppsspp-ws", version="1").get("version")
        except (DebuggerError, TimeoutError, ConnectionClosed):
            return None

    def cleanup(self):
        """Removes every breakpoint this client made. Runs on every exit path; ignores a second Ctrl+C."""
        previous = {}
        if threading.current_thread() is threading.main_thread():
            for name in ("SIGINT", "SIGBREAK", "SIGTERM"):
                if hasattr(signal, name):
                    number = getattr(signal, name)
                    previous[number] = signal.signal(number, signal.SIG_IGN)
        try:
            self.commit_pending()
            failed = []
            try:
                if self.holding_pause:
                    self.dbg.send("cpu.resume")
                    self.holding_pause = False
                for bp_id in list(self.armed):
                    if not self.disarm(bp_id):
                        failed.append(bp_id)
            except (ConnectionClosed, OSError) as error:
                failed = sorted(self.armed)
                self.warn(f"cleanup: {error}; breakpoints still in PPSSPP: {', '.join(failed) or 'none'} "
                          f"(log-only; they go away when PPSSPP closes)")
            self.flush_repeats()
            self.write("end", reason=self.stop_reason or "exception", not_removed=failed)
        finally:
            self.log.close()
            for number, handler in previous.items():
                signal.signal(number, handler)


def merge_module_bases(path, loads):
    """Accumulate (module, base) rows across runs. Input for imports at the right base in re/ later."""
    columns = ["module", "info_name", "base", "size", "loads", "first_seen", "last_seen", "documented_base"]
    rows = {}
    path = Path(path)
    if path.is_file():
        with open(path, encoding="utf-8", newline="") as handle:
            rows = {(r["module"], r["base"]): r for r in csv.DictReader(handle)}
    for (module, base), info in loads.items():
        row = rows.setdefault((module, f"{base:#010x}"), {
            "module": module, "info_name": info["name"], "base": f"{base:#010x}", "size": f"{info['size']:#x}",
            "loads": "0", "first_seen": info["first"], "last_seen": info["last"],
            "documented_base": f"{DOCUMENTED_BASES[module]:#010x}" if module in DOCUMENTED_BASES else ""})
        row["loads"] = str(int(row["loads"]) + info["loads"])
        row["last_seen"] = info["last"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows[key] for key in sorted(rows))


# ---------------------------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------------------------

class Aggregate:
    """Everything the summary needs, built in one pass over the log, in bounded memory."""

    def __init__(self):
        self.meta = {}
        self.end = None
        self.duration = 0.0
        self.bps = collections.defaultdict(lambda: {
            "count": 0, "suspect": 0, "first": None, "last": None, "mods": collections.Counter(),
            "values": collections.defaultdict(collections.Counter), "tuples": collections.Counter(),
            "seq": collections.defaultdict(list), "overflow": 0, "pauses": []})
        self.samples = collections.defaultdict(lambda: {
            "first": None, "last": None, "n": 0, "values": collections.Counter(), "seq": [], "changes": []})
        self.modules = {}
        self.marks = []
        self.edits = []
        self.warnings = []
        self.lines = 0
        self.corrupt = 0
        self.volatile = {}

    def add_values(self, bp, bp_id, fields, count):
        for name, value in fields.items():
            values = bp["values"][name]
            if value in values or len(values) < VALUE_CAP:
                values[value] += count
            sequence = bp["seq"][name]
            if (not sequence or sequence[-1] != value) and len(sequence) < SEQUENCE_CAP:
                sequence.append(value)
        volatile = self.volatile.get(bp_id, ())
        key = tuple(sorted((k, v) for k, v in fields.items() if k not in volatile))
        if key in bp["tuples"] or len(bp["tuples"]) < VALUE_CAP:
            bp["tuples"][key] += count

    def feed(self, record):
        kind = record.get("k")
        self.duration = max(self.duration, record.get("t", 0))
        if kind == "meta":
            self.meta = record
            self.volatile = {bp["id"]: set(bp.get("volatile", [])) for bp in record["test"]["breakpoints"]}
        elif kind == "hit":
            bp = self.bps[record["bp"]]
            if record.get("suspect"):
                bp["suspect"] += 1
                return
            bp["count"] += 1
            bp["mods"][record.get("mod", "?")] += 1
            bp["first"] = bp["first"] or record
            bp["last"] = record
            self.add_values(bp, record["bp"], record["f"], 1)
        elif kind == "dup":
            bp = self.bps[record["bp"]]
            for item in record.get("items", []):
                bp["count"] += item["n"]
                self.add_values(bp, record["bp"], item["f"], item["n"])
            bp["count"] += record.get("overflow", 0)
            bp["overflow"] += record.get("overflow", 0)
            if record.get("last"):
                bp["last"] = record["last"]
        elif kind == "pause":
            pauses = self.bps[record["bp"]]["pauses"]
            if len(pauses) < 10:
                pauses.append(record)
        elif kind == "sample":
            sample = self.samples[record["id"]]
            sample["first"] = sample["first"] or record
            sample["n"] += 1
            if sample["last"] is not None and sample["last"]["v"] != record["v"] and len(sample["changes"]) < 200:
                sample["changes"].append((record["t"], sample["last"]["v"], record["v"], record.get("mod")))
            sample["last"] = record
            if record["v"] in sample["values"] or len(sample["values"]) < VALUE_CAP:
                sample["values"][record["v"]] += 1
            if (not sample["seq"] or sample["seq"][-1] != record["v"]) and len(sample["seq"]) < SEQUENCE_CAP:
                sample["seq"].append(record["v"])
        elif kind == "module" and record.get("ev") == "load":
            entry = self.modules.setdefault((record["module"], record["base"]), {"loads": 0, "size": record.get("size")})
            entry["loads"] += 1
        elif kind == "mark":
            self.marks.append(record)
        elif kind == "edit":
            self.edits.append(record)
        elif kind == "warn":
            self.warnings.append(record["text"])
        elif kind == "end":
            self.end = record

    def sample_group(self, name):
        if name in self.samples:
            return [name]
        return sorted(k for k in self.samples if k.startswith(name + "["))


def read_log(path):
    aggregate = Aggregate()
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            aggregate.lines += 1
            try:
                aggregate.feed(json.loads(line))
            except (ValueError, KeyError, TypeError):
                aggregate.corrupt += 1  # a run that died mid-line
    return aggregate


class FunctionNames:
    def __init__(self):
        self.entries = []
        try:
            registry = load_registry()
        except OSError:
            return
        for key, (name, size) in registry.items():
            module, _, address = key.rpartition(":")
            if name.startswith("thunk_"):
                continue
            self.entries.append((parse_int(address), size, name, module))
        self.entries.sort()
        self.starts = [entry[0] for entry in self.entries]

    def lookup(self, address, modules=""):
        if not self.entries:
            return ""
        index = bisect.bisect_right(self.starts, address) - 1
        for candidate in range(index, max(index - 400, -1), -1):  # shared slots repeat addresses
            start, size, name, module = self.entries[candidate]
            if start <= address < start + size and (not module or module in modules):
                return name
        return ""


def hexlist(values, limit=12):
    values = list(values)
    text = ", ".join(f"{v:#x}" if isinstance(v, int) else str(v) for v in values[:limit])
    return text + (f", ... ({len(values)} in all)" if len(values) > limit else "")


def counted(counter, limit=10):
    pairs = counter.most_common()
    text = ", ".join(f"{v:#x} x{n}" if isinstance(v, int) else f"{v} x{n}" for v, n in pairs[:limit])
    return text + (f", ... ({len(pairs)} distinct)" if len(pairs) > limit else "")


def series(aggregate, item):
    """(distinct-value counter, consecutive sequence, seen?) of an item's source."""
    if "bp" in item:
        bp = aggregate.bps.get(item["bp"])
        if not bp or not bp["count"]:
            return collections.Counter(), [], False
        return bp["values"][item["field"]], bp["seq"][item["field"]], True
    group = aggregate.sample_group(item["sample"])
    values, sequence = collections.Counter(), []
    for name in group:
        values.update(aggregate.samples[name]["values"])
        sequence += aggregate.samples[name]["seq"]
    return values, sequence, bool(group)


def is_subsequence(needle, haystack):
    iterator = iter(haystack)
    return all(value in iterator for value in needle)


def item_value(value, env):
    return parse_int(substitute(value, env)) if isinstance(value, str) else value


def evaluate_item(item, aggregate, names, env):
    """(status, detail). PASS, FAIL, NOT SEEN, RECORDED (no expected value) or MANUAL."""
    kind = item["type"]
    wanted = [item_value(v, env) for v in item.get("values", [])]
    if kind == "manual":
        return "MANUAL", item.get("note", "")
    if kind == "modules_record":
        loaded = sorted({module for module, _ in aggregate.modules})
        return ("RECORDED", hexlist(loaded, 16)) if loaded else ("NOT SEEN", "no module load")
    if kind in ("hits", "hit_rate"):
        bp = aggregate.bps.get(item["bp"])
        if not bp or not bp["count"]:
            return "NOT SEEN", "no hit"
        count = bp["count"]
        if kind == "hits":
            low, high = item.get("min", 1), item.get("max")
            good = count >= low and (high is None or count <= high)
            return ("PASS" if good else "FAIL"), f"{count} hits"
        span = (bp["last"] or {}).get("t", 0) - bp["first"]["t"]
        if span < item.get("min_seconds", 10):
            return "NOT SEEN", f"only {span:.1f} s of hits"
        rate = (count - 1) / span
        good = item["min"] <= rate <= item["max"]
        return ("PASS" if good else "FAIL"), f"{rate:.2f} per second over {span:.0f} s (expected {item['min']}-{item['max']})"
    if kind == "sample_rate":
        sample = aggregate.samples.get(item["sample"])
        if not sample or sample["n"] < 2:
            return "NOT SEEN", "no samples"
        span = sample["last"]["t"] - sample["first"]["t"]
        if span < item.get("min_seconds", 10):
            return "NOT SEEN", f"only {span:.1f} s of samples"
        rate = (sample["last"]["v"] - sample["first"]["v"]) / span
        good = item["min"] <= rate <= item["max"]
        return ("PASS" if good else "FAIL"), f"{rate:.2f} per second over {span:.0f} s (expected {item['min']}-{item['max']})"
    if kind == "tuple_seen":
        bp = aggregate.bps.get(item["bp"])
        if not bp or not bp["count"]:
            return "NOT SEEN", "no hit"
        want = {name: item_value(value, env) for name, value in item["fields"].items()}
        seen = any(want.items() <= dict(key).items() for key in bp["tuples"])
        return ("PASS" if seen else "FAIL"), hexlist(want.values())
    if kind == "pairs_record":
        bp = aggregate.bps.get(item["bp"])
        if not bp or not bp["count"]:
            return "NOT SEEN", "no hit"
        pairs = collections.Counter()
        condition = item.get("filter", {}).items()
        for key, count in bp["tuples"].items():
            fields = dict(key)
            if condition <= fields.items():
                pairs[tuple(fields.get(name) for name in item["fields"])] += count
        shown = []
        for pair, count in pairs.most_common(item.get("limit", 14)):
            text = " ".join(f"{name}={value:#x}" for name, value in zip(item["fields"], pair) if value is not None)
            if item.get("names"):
                caller = names.lookup(pair[-1] or 0, " ".join(bp["mods"]))
                text += f" {caller}" if caller else ""
            shown.append(f"{text} x{count}")
        more = f"; {len(pairs) - len(shown)} more" if len(pairs) > len(shown) else ""
        return "RECORDED", "; ".join(shown) + more
    values, sequence, seen = series(aggregate, item)
    if not seen and kind != "sample_record":
        return "NOT SEEN", "no data"
    if kind == "field_in":
        strays = [v for v in values if v not in set(wanted)]
        return ("FAIL", f"outside the expected set: {hexlist(strays)}") if strays else ("PASS", f"{len(values)} distinct, all expected")
    if kind == "field_seen":
        missing = [v for v in wanted if v not in values]
        return ("FAIL", f"missing {hexlist(missing)}; seen {counted(values)}") if missing else ("PASS", counted(collections.Counter({v: values[v] for v in wanted})))
    if kind == "field_any":
        found = [v for v in wanted if v in values]
        return ("PASS", f"seen {hexlist(found)}") if found else ("FAIL", f"none of {hexlist(wanted)}; seen {counted(values)}")
    if kind == "field_absent":
        found = [v for v in wanted if v in values]
        return ("FAIL", f"seen {hexlist(found)}") if found else ("PASS", f"absent; seen {counted(values)}")
    if kind == "field_record":
        return ("RECORDED", counted(values, item.get("limit", 12))) if seen else ("NOT SEEN", "no data")
    if kind == "bits_seen":
        merged = 0
        for value in values:
            merged |= value
        missing = [bit for bit in item["bits"] if not merged >> bit & 1]
        detail = f"all values OR {merged:#x}"
        return ("FAIL", f"bits {missing} never set; {detail}") if missing else ("PASS", detail)
    if kind == "sequence":
        good = is_subsequence(wanted, sequence)
        return ("PASS" if good else "FAIL"), f"seen {hexlist(sequence, 16)}"
    if kind == "sample_range":
        numbers = [v for v, n in values.items() for _ in range(min(n, 1000))]
        mean = sum(numbers) / len(numbers)
        good = item["min"] <= mean <= item["max"]
        return ("PASS" if good else "FAIL"), f"mean {mean:.2f} (expected {item['min']}-{item['max']})"
    if kind == "sample_constant":
        expected = item_value(item["value"], env) if "value" in item else None
        distinct = list(values)
        good = len(distinct) == 1 and expected in (None, distinct[0])
        return ("PASS" if good else "FAIL"), f"values {hexlist(distinct)}"
    if kind == "sample_final":
        names_in_group = aggregate.sample_group(item["sample"])
        final = aggregate.samples[names_in_group[0]]["last"]["v"]
        good = final == item_value(item["value"], env)
        return ("PASS" if good else "FAIL"), f"last value {final:#x}"
    if kind == "sample_changed":
        changed = [(name, aggregate.samples[name]["changes"]) for name in aggregate.sample_group(item["sample"])
                   if aggregate.samples[name]["changes"]]
        if not changed:
            return "FAIL", "never changed"
        texts = [f"{name} {c[0][1]:#x}->{c[-1][2]:#x} ({c[-1][3]})" for name, c in changed]
        return "PASS", "; ".join(texts[:6]) + (f"; {len(texts) - 6} more" if len(texts) > 6 else "")
    if kind == "sample_record":
        return ("RECORDED", f"sequence {hexlist(sequence, 16)}") if seen else ("NOT SEEN", "no data")
    raise ValueError(kind)


def summarize(path, max_lines=SUMMARY_MAX_LINES):
    """A short text for the agent: never over max_lines, however large the log is."""
    aggregate = read_log(path)
    meta = aggregate.meta
    test = meta.get("test", {})
    names = FunctionNames() if any(item.get("names") for item in test.get("expected", [])) else None
    lines = [f"PPSSPP hybrid run {test.get('id', '?')}: {test.get('title', '')}",
             f"log {Path(path).name}: {aggregate.lines} lines, {aggregate.duration:.0f} s, PPSSPP {meta.get('ppsspp')}, "
             f"started {meta.get('started')}"]
    end = aggregate.end
    if end is None:
        lines.append("no end record: the run died; breakpoints may still be in PPSSPP (log-only)")
    else:
        extra = f"; NOT REMOVED: {hexlist(end['not_removed'])}" if end.get("not_removed") else ""
        lines.append(f"ended: {end.get('reason')}; breakpoints removed{extra}")
    env = meta.get("env", {})
    results = [(item, *evaluate_item(item, aggregate, names, env)) for item in test.get("expected", [])]
    tally = collections.Counter(status for _, status, _ in results)
    lines.append("result: " + ", ".join(f"{count} {status}" for status, count in sorted(tally.items())))
    lines.append("items:")
    for item, status, detail in results[:30]:
        lines.append(f"  {status:<8} {item.get('what', item['type'])}: {detail}")
    if len(results) > 30:
        lines.append(f"  ... {len(results) - 30} more items")
    lines += [f"not done by this tool: {text}" for text in test.get("not_possible", [])[:5]]
    if aggregate.marks:
        lines.append("marks by the maintainer:")
        field = test.get("mark_field")
        previous = 0.0
        for mark in aggregate.marks[:10]:
            suffix = ""
            if field:
                suffix = " <- " + hexlist(marked_values(path, field, previous, mark["t"]), 8)
            lines.append(f"  {mark['t']:.1f} s: {mark['text']}{suffix}")
            previous = mark["t"]
        if len(aggregate.marks) > 10:
            lines.append(f"  ... {len(aggregate.marks) - 10} more")
    if aggregate.edits:
        lines.append("memory edits (record these in the results file):")
        for edit in aggregate.edits[:6]:
            lines.append(f"  {edit['id']} {edit['address']:#010x} {edit['old']:#x} -> {edit['new']:#x} at {edit['t']:.1f} s: {edit.get('purpose', '')}")
    if aggregate.warnings:
        lines.append(f"warnings ({len(aggregate.warnings)}):")
        lines += [f"  {text}" for text in aggregate.warnings[:6]]
    if aggregate.bps:
        lines.append("breakpoints (id, hits, suspect, modules, first and last):")
    for bp_id, bp in list(sorted(aggregate.bps.items()))[:14]:
        first, last = bp["first"], bp["last"]
        span = f"{first['t']:.1f}-{last['t']:.1f} s" if first and last else "-"
        overflow = f", {bp['overflow']} values not kept" if bp["overflow"] else ""
        lines.append(f"  {bp_id}: {bp['count']}, {bp['suspect']} suspect, {hexlist(bp['mods'], 3)}, {span}{overflow}")
        for pause in bp["pauses"][:1]:
            lines.append(f"    paused {len(bp['pauses'])}x, {pause['ms']} ms, frames {hexlist(pause.get('frames', []), 6)}")
    if aggregate.samples:
        lines.append("samples (id: first -> last, changes):")
        changing = [(k, s) for k, s in sorted(aggregate.samples.items()) if s["changes"]] or sorted(aggregate.samples.items())
        for name, sample in changing[:12]:
            lines.append(f"  {name}: {sample['first']['v']:#x} -> {sample['last']['v']:#x}, {len(sample['changes'])} changes"
                         if isinstance(sample["first"]["v"], int) else f"  {name}: {sample['first']['v']} -> {sample['last']['v']}")
        if len(changing) > 12:
            lines.append(f"  ... {len(changing) - 12} more")
    if aggregate.modules:
        lines.append("modules (name, base, loads):")
        for (module, base), info in sorted(aggregate.modules.items())[:12]:
            lines.append(f"  {module} {base:#010x} x{info['loads']}")
        if len(aggregate.modules) > 12:
            lines.append(f"  ... {len(aggregate.modules) - 12} more (module-bases.csv has them all)")
    if aggregate.corrupt:
        lines.append(f"{aggregate.corrupt} log lines could not be read")
    lines = [line[:SUMMARY_LINE_WIDTH] for line in lines]
    if len(lines) > max_lines:
        lines = lines[:max_lines - 1] + [f"... {len(lines) - max_lines + 1} lines cut; the log has everything"]
    return lines


def marked_values(path, field, start, end):
    """Distinct values of a field logged between two marks, in order."""
    found = []
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if '"k": "hit"' not in line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if start < record["t"] <= end and field in record["f"] and record["f"][field] not in found:
                found.append(record["f"][field])
    return found


# ---------------------------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------------------------

def console_reader(commands):
    try:
        for line in sys.stdin:
            commands.put(line)
    except (OSError, ValueError):
        pass


def install_signals():
    """Ctrl+Break and a closing console window end a run the same way as Ctrl+C."""
    def interrupt(signum, frame):
        raise KeyboardInterrupt
    for name in ("SIGBREAK", "SIGTERM"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), interrupt)


def stamp():
    return time.strftime("%Y%m%d-%H%M%S")


def print_instructions(test, allow_edits):
    print(f"\n=== {test['id']}: {test['title']} ===")
    print("O que fazer (você joga; a ferramenta só observa):")
    for number, line in enumerate(test["instructions_pt"], 1):
        print(f"  {number}. {line}")
    print("Comandos nesta janela: m <texto> = anotar o que aconteceu | q ou Ctrl+C = terminar")
    if test.get("edits"):
        state = "ligadas" if allow_edits else "desligadas (use --allow-edits)"
        print(f"Edições de memória {state}: " + ", ".join(e["id"] for e in test["edits"]))
    if any(bp.get("pause") for bp in test["breakpoints"]):
        print("Aviso: este teste tem breakpoints que pausam um instante; o jogo pode engasgar nesses pontos.")
    print()


def cmd_check(args):
    debugger = connect(args)
    try:
        version = debugger.call("version", name="tf3-ppsspp-ws", version="1")
        print(f"PPSSPP: {version.get('version')}")
        if not str(version.get("version", "")).startswith(EXPECTED_VERSION_PREFIX):
            print(f"WARNING: this client was written for {EXPECTED_VERSION_PREFIX}.x")
        status = debugger.call("game.status")
        game = status.get("game")
        if not game:
            print("game: none running")
            return 0
        print(f"game: {game.get('id')} version {game.get('version')} ({game.get('title')}), paused={status.get('paused')}")
        if game.get("id") != GAME_ID:
            print(f"WARNING: expected {GAME_ID}")
        cpu = debugger.call("cpu.status")
        print(f"cpu: stepping={cpu.get('stepping')} pc={cpu.get('pc', 0):#010x}")
        shift, state = read_state_address(debugger)
        print(f"save state: r={shift} S={state:#010x}")
        active = active_modules(debugger)
        print(f"modules loaded: {len(active)}")
        for name, info in sorted(active.items(), key=lambda item: item[1]["base"]):
            documented = DOCUMENTED_BASES.get(name)
            note = "" if documented is None else (" = documented" if documented == info["base"] else f" != documented {documented:#010x}")
            print(f"  {name:<20} {info['base']:#010x} size {info['size']:#x}{note}")
        return 0
    finally:
        debugger.ws.close()


def cmd_list(args):
    tests = load_tests()
    problems = []
    if args.check:
        registry = load_registry()
        for test in tests.values():
            problems += check_registry(test, registry)
    for test in tests.values():
        module = test.get("required_module", ALWAYS)
        module = module if isinstance(module, str) else f"any of {len(module)} modules"
        optional = " (optional)" if test.get("optional") else ""
        print(f"{test['id']:<4} {test['title']}{optional} [{module}; {len(test['breakpoints'])} breakpoints, "
              f"{len(test['samples'])} samples, {len(test['expected'])} checks]")
    for problem in problems:
        print(f"PROBLEM: {problem}")
    return 1 if problems else 0


def parse_params(pairs):
    return dict(pair.split("=", 1) for pair in pairs or [])


def run_session(args, test, label, allow_edits=False, params=None, instructions=True):
    out = Path(args.out)
    debugger = connect(args, allow_edits=allow_edits)
    log_path = out / f"{stamp()}-{label}.jsonl"
    commands = queue.Queue()
    threading.Thread(target=console_reader, args=(commands,), daemon=True).start()
    session = Session(debugger, test, log_path, params=params, poll=args.poll, commands=commands)
    if instructions:
        print_instructions(test, allow_edits)
    reason = session.run(args.duration)
    debugger.ws.close()
    merge_module_bases(out / "module-bases.csv", session.loads)
    print(f"\nended: {reason}\nlog: {log_path}\nmodule bases: {out / 'module-bases.csv'}\n")
    lines = summarize(log_path)
    summary_path = log_path.with_suffix(".summary.txt")
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nsummary: {summary_path}\nMande para o agente só esse arquivo de resumo.")
    return 0


def cmd_run(args):
    tests = load_tests()
    if args.test not in tests:
        raise SystemExit(f"unknown test {args.test}; available: {', '.join(tests)}")
    return run_session(args, tests[args.test], args.test, args.allow_edits, parse_params(args.set))


def cmd_watch(args):
    test = {"id": "watch-modules", "title": "Module load observer", "plan": "", "breakpoints": [],
            "samples": [], "not_possible": [],
            "instructions_pt": ["Jogue normalmente e entre nas cenas cujos módulos você quer mapear.",
                                "Cada carga aparece aqui com o nome e a base. Termine com q ou Ctrl+C."],
            "expected": [{"type": "modules_record", "what": "modules loaded"}]}
    return run_session(args, test, "watch-modules")


def cmd_summary(args):
    print("\n".join(summarize(args.log)))
    return 0


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description="Hybrid PPSSPP runs through the WebSocket debugger.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, help="debugger port (default: ppsspp.ini, then netstat)")
    parser.add_argument("--ini", help="path of ppsspp.ini (default: external/ppsspp/...)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="connect, print version, game id and loaded modules")
    listing = commands.add_parser("list", help="available tests")
    listing.add_argument("--check", action="store_true", help="validate addresses against re/functions.csv")
    run = commands.add_parser("run", help="run one test")
    run.add_argument("test")
    run.add_argument("--allow-edits", action="store_true", help="allow the memory edits the test defines")
    run.add_argument("--set", action="append", metavar="NAME=VALUE", help="override a test parameter")
    watch = commands.add_parser("watch-modules", help="log every module load until stopped")
    for sub in (run, watch):
        sub.add_argument("--out", default=str(DEFAULT_OUT), help="output directory (git-ignored by default)")
        sub.add_argument("--duration", type=float, help="stop after this many seconds")
        sub.add_argument("--poll", type=float, default=0.1, help="module poll period in seconds")
    summary = commands.add_parser("summary", help="summary of a run log")
    summary.add_argument("log")
    args = parser.parse_args(argv)
    install_signals()
    handlers = {"check": cmd_check, "list": cmd_list, "run": cmd_run, "watch-modules": cmd_watch, "summary": cmd_summary}
    try:
        return handlers[args.command](args)
    except Refused as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)  # the console reader thread may be blocked on stdin; sys.exit could abort on it
