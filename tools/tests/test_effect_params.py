#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/effect_params.py on a synthetic module. Run with: python3 -I tools/tests/test_effect_params.py"""

import contextlib
import csv
import importlib.util
import io
import struct
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_effect_params",
                                              Path(__file__).resolve().parents[1] / "effect_params.py")
ep = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ep)

BASE = ep.BASE
ZERO, V0, A0, A2, A3, S0, S2, SP, RA = 0, 2, 4, 6, 7, 16, 18, 29, 31


def itype(op, rs, rt, imm):
    return op << 26 | rs << 21 | rt << 16 | (imm & 0xFFFF)


def addiu(rt, rs, imm):
    return itype(9, rs, rt, imm)


def ori(rt, rs, imm):
    return itype(0x0D, rs, rt, imm)


def lui(rt, imm):
    return itype(0x0F, 0, rt, imm)


def lhu(rt, base, off):
    return itype(0x25, base, rt, off)


def addu(rd, rs, rt):
    return rs << 21 | rt << 16 | rd << 11 | 0x21


def jump(op, target):
    return op << 26 | (target - BASE) >> 2


def branch(op, rs, rt, pc, target):
    return itype(op, rs, rt, (target - pc - 4) >> 2)


JR_RA = RA << 21 | 8
STUB_A = 0x09C34000  # j filter; addiu a3,zero,0x1092
STUB_B = 0x09C34010  # lui v0,0x8; j filter; ori a3,v0,0x412
OTHER = 0x09C34020   # a handler that is not a stub
CALLER = 0x09C34100  # a function that calls the filter with a constant


class Image:
    def __init__(self):
        self.size = 0x09E01E10 - BASE
        self.buf = bytearray(self.size)

    def put(self, address, *words):
        struct.pack_into(f"<{len(words)}I", self.buf, address - BASE, *words)

    def elf(self):
        header = bytearray(0x54)
        header[0:4] = b"\x7fELF"
        struct.pack_into("<I", header, 0x1C, 0x34)
        struct.pack_into("<H", header, 0x2C, 1)
        struct.pack_into("<6I", header, 0x34, 1, 0x54, 0, 0, self.size, self.size)
        return bytes(header) + bytes(self.buf)


def build():
    img = Image()
    for name, address, count in ep.TABLES:
        for i in range(count):
            img.put(address + 24 * i, 0x1300 + 2 * i, 0, 0, 0, 0, 0)
    st = ep.TABLES[0][1]
    img.put(st, 0x12EC, 0, STUB_A - BASE, 0, 0, 0)          # record 0: addiu stub
    img.put(st + 24, 0x12ED, 0, STUB_B - BASE, 0, 0, 0)     # record 1: lui+ori stub
    img.put(st + 48, 0x12EE, 0, OTHER - BASE, 0, 0, 0)      # record 2: own function
    m1 = ep.TABLES[1][1]
    img.put(m1, 0x0E90, CALLER - BASE, 0, 0, 0, 0)          # CALLER is a slot +04 handler
    # the filter itself: prologue with `andi s1,s2,3`, epilogue at the documented size
    f = ep.TARGET_FILTER
    img.put(f, addiu(SP, SP, -64), itype(0x0C, S2, 17, 3))
    img.put(f + ep.TARGET_FILTER_SIZE - 8, JR_RA, addiu(SP, SP, 64))
    img.put(STUB_A, jump(2, f), addiu(A3, ZERO, 0x1092))
    img.put(STUB_B, lui(V0, 0x8), jump(2, f), ori(A3, V0, 0x412))
    img.put(OTHER, JR_RA, addiu(V0, ZERO, 1))
    img.put(CALLER, addiu(SP, SP, -16), jump(3, f), addiu(A3, ZERO, 0x4410), jump(3, ep.DRAW_COUNT), 0,
            JR_RA, addiu(SP, SP, 16))
    # the draw-count chain
    d = ep.DRAW_COUNT
    end = d + ep.DRAW_COUNT_SIZE - 12
    block = end - 0x40
    code = [addiu(SP, SP, -16), addu(S2, A0, ZERO), lhu(A2, S2, 0)]
    pc = d + 4 * len(code)
    for cid, op, target, delay in [(0x12EC, 0x14, end, addiu(S0, ZERO, 2)),
                                   (0x1300, 4, block, 0),
                                   (0x1301, 0x14, end, lhu(S0, S2, 0x12))]:
        code += [addiu(V0, ZERO, cid), branch(op, A2, V0, pc + 4, target), delay]
        pc += 12
    code += [branch(4, ZERO, ZERO, pc, end), 0]
    img.put(d, *code)
    img.put(block, addiu(S0, ZERO, -1), branch(4, ZERO, ZERO, block + 4, end), 0)
    img.put(end, addu(V0, S0, ZERO), JR_RA, addiu(SP, SP, 16))
    return img.elf()


class EffectParamsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = ep.Module(build())

    def test_check_passes(self):
        self.assertEqual(ep.check(self.module), [])

    def test_check_fails_on_other_data(self):
        img = Image()
        self.assertTrue(ep.check(ep.Module(img.elf())))

    def test_target_filter_stubs(self):
        rows = ep.target_filters(self.module)
        self.assertEqual([(r["card_id"], r["form"], r["flags"]) for r in rows],
                         [("0x12ec", "addiu", "0x01092"), ("0x12ed", "lui+ori", "0x80412")])
        self.assertEqual(rows[0]["side"], "opponent")
        self.assertEqual(rows[0]["zone"], "monster")
        self.assertEqual(rows[0]["position"], "attack")
        self.assertEqual(rows[0]["actions"], "destroy")
        self.assertEqual(rows[1]["actions"], "targeted return")

    def test_negative_addiu_is_sign_extended(self):
        img = bytearray(build())
        struct.pack_into("<I", img, STUB_A - BASE + 0x54 + 4, addiu(A3, ZERO, -2))
        self.assertEqual(ep.filter_stub(ep.Module(bytes(img)), STUB_A), ("addiu", 0xFFFFFFFE))

    def test_decode_flags(self):
        self.assertEqual(ep.decode_flags(0x1410), {"side": "any", "zone": "monster", "face": "", "position": "",
                                                   "actions": "targeted destroy"})
        d = ep.decode_flags(0x20000 | 0x200 | 0x8 | 0x3 | 0x100)
        self.assertEqual((d["side"], d["face"], d["position"]), ("tributable", "face_down", "defense"))
        self.assertEqual(d["actions"], "not_self unknown_0x200")

    def test_filter_calls(self):
        functions = ep.function_starts(self.module)
        users = ep.handler_users(self.module)
        rows = ep.target_filter_calls(self.module, functions, users)
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["function"], rows[0]["flags"], rows[0]["referenced_by"]),
                         (f"{CALLER:#010x}", "0x04410", "M1:+04:0xe90"))

    def test_draw_counts(self):
        rows = {r["card_id"]: r for r in ep.draw_counts(self.module)}
        self.assertEqual(rows["0x12ec"]["value"], 2)
        self.assertEqual(rows["0x1300"]["value"], -1)
        self.assertEqual(rows["0x1301"]["kind"], "computed")
        self.assertIn("ctx+0x12 u16", rows["0x1301"]["summary"])

    def test_compare_chains(self):
        functions = ep.function_starts(self.module)
        rows, cases = ep.compare_chains(self.module, functions, ep.handler_users(self.module), min_cases=3)
        draw = [r for r in rows if r["function"] == f"{ep.DRAW_COUNT:#010x}"]
        self.assertEqual(len(draw), 1)
        self.assertEqual((draw[0]["cases"], draw[0]["constant_cases"], draw[0]["class"]), (3, 2, "parameter"))
        self.assertEqual(len([c for c in cases if c["function"] == draw[0]["function"]]), 3)

    def test_evaluate_branches(self):
        img = Image()
        a = 0x09C40000
        img.put(a, addiu(V0, ZERO, 5), branch(5, V0, ZERO, a + 4, a + 20), addiu(V0, V0, 1),
                addiu(V0, ZERO, 0), JR_RA, JR_RA, 0)
        self.assertEqual(ep.evaluate(ep.Module(img.elf()), a), 6)

    def test_main_writes_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            prx = Path(tmp) / "rel_duel_eng.prx"
            prx.write_bytes(build())
            out = Path(tmp) / "out"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ep.main([str(prx), "-o", str(out)]), 0)
                self.assertEqual(ep.main([str(prx), "--check"]), 0)
            with open(out / "target_filters.csv", encoding="utf-8") as f:
                self.assertEqual(len(list(csv.DictReader(f))), 2)
            for name in ("target_filter_calls", "draw_counts", "compare_chains", "chain_cases"):
                self.assertTrue((out / f"{name}.csv").exists())


if __name__ == "__main__":
    unittest.main()
