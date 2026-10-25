#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/stat_mods.py on a synthetic module. Run with: python3 -I tools/tests/test_stat_mods.py"""

import contextlib
import csv
import importlib.util
import io
import struct
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_stat_mods", Path(__file__).resolve().parents[1] / "stat_mods.py")
sm = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sm)
ep = sm.ep

BASE = ep.BASE
ZERO, V0, V1, A0, A2, SP, RA = 0, 2, 3, 4, 6, 29, 31
JR_RA = RA << 21 | 8


def itype(op, rs, rt, imm):
    return op << 26 | rs << 21 | rt << 16 | (imm & 0xFFFF)


def addiu(rt, rs, imm):
    return itype(9, rs, rt, imm)


def jal(target):
    return 3 << 26 | (target - BASE) >> 2


def branch(op, rs, rt, pc, target):
    return itype(op, rs, rt, (target - pc - 4) >> 2)


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


def case(img, at, cid, body_at, body):
    """`li v0,cid; beq a0,v0,body; nop` at `at`, and the body followed by `b +0`."""
    img.put(at, addiu(V0, ZERO, cid), branch(4, A0, V0, at + 4, body_at), 0)
    img.put(body_at, *body, branch(4, ZERO, ZERO, body_at + 4 * len(body), body_at + 4 * len(body) + 8), 0)


def build(anchors=True):
    img = Image()
    for start, size, _, _, _ in sm.FUNCTIONS:
        img.put(start, addiu(SP, SP, -16))
        img.put(start + size - 8, JR_RA, addiu(SP, SP, 16))
    if anchors:
        case(img, 0x09C03B60, 0x10F3, 0x09C03C00, [addiu(V1, ZERO, 200)])      # field spell
        case(img, 0x09C04AD0, 0x1E46, 0x09C04B00, [addiu(V1, ZERO, 2400)])     # base
        case(img, 0x09C08B00, 0x10E0, 0x09C08C00, [addiu(V1, V1, 700), jal(0x09BE9168), 0])  # equip
        case(img, 0x09C07600, 0x1C5F, 0x09C07700, [addiu(V1, ZERO, -500)])    # attached
        img.put(0x09C05600, jal(0x09BE9168), addiu(A2, ZERO, 0x1257))           # call in the delay slot
        case(img, 0x09DD1CA0, 0x1B40, 0x09DD1D00, [])                          # damage step
        img.put(0x09C05700, addiu(7, ZERO, 0x1300), 0)                          # a3 never used: other
    return img.elf()


class StatModsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = ep.Module(build())

    def test_check_passes(self):
        self.assertEqual(sm.check(self.module), [])

    def test_check_fails_without_anchors(self):
        problems = sm.check(ep.Module(build(anchors=False)))
        self.assertEqual(len(problems), len(sm.ANCHORS))

    def test_check_fails_on_other_data(self):
        self.assertTrue(sm.check(ep.Module(Image().elf())))

    def test_uses(self):
        rows = {(r["card_id"], r["use"]): r for r in sm.stat_uses(self.module)}
        equip = rows[("0x10e0", "test")]
        self.assertEqual((equip["section"], equip["values"], equip["calls"]), ("equip_spell", "700", "slot_has_effect"))
        self.assertEqual(equip["target"], "0x09c08c00")
        self.assertEqual(rows[("0x1c5f", "test")]["section"], "attached")
        self.assertEqual(rows[("0x1c5f", "test")]["values"], "-500")
        self.assertEqual(rows[("0x10f3", "test")]["layer"], "field_spell")
        self.assertEqual(rows[("0x1e46", "test")]["values"], "2400")
        call = rows[("0x1257", "call")]
        self.assertEqual((call["section"], call["helper"]), ("self", "slot_has_effect"))
        self.assertIn(("0x1300", "other"), rows)

    def test_bne_case_body_is_the_fall_through(self):
        img = Image()
        a = 0x09C04198
        img.put(a, addiu(V0, ZERO, 0x1207), branch(5, A0, V0, a + 4, a + 0x40), 0, addiu(V1, ZERO, 500), JR_RA, 0)
        rows = list(sm.card_id_uses(ep.Module(img.elf()), a, a + 0x40))
        self.assertEqual(rows[0][1:3], (0x1207, "test"))
        self.assertEqual(sm.case_body(ep.Module(img.elf()), rows[0][3]), ([500], []))

    def test_coverage(self):
        rows = sm.stat_uses(self.module)
        cards = {0x10E0: ("Equip", True), 0x0E90: ("Other", True), 0x0E91: ("Plain", False)}
        cov = {r["card_id"]: r for r in sm.coverage(rows, cards)}
        self.assertEqual(cov["0x10e0"]["sections"], "equip_spell")
        self.assertEqual(cov["0xe90"]["sections"], "")
        self.assertNotIn("0xe91", cov)

    def test_main_writes_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            prx = Path(tmp) / "rel_duel_eng.prx"
            prx.write_bytes(build())
            out = Path(tmp) / "out"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(sm.main([str(prx), "--check"]), 0)
                self.assertEqual(sm.main([str(prx), "-o", str(out)]), 0)
            with open(out / "stat_mods.csv", encoding="utf-8") as f:
                self.assertEqual(len(list(csv.DictReader(f))), 7)


if __name__ == "__main__":
    unittest.main()
