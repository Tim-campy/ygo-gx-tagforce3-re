#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/ai_tables.py on a synthetic module. Run with: python3 -I tools/tests/test_ai_tables.py"""

import contextlib
import csv
import importlib.util
import io
import struct
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_ai_tables", Path(__file__).resolve().parents[1] / "ai_tables.py")
at = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(at)

BASE = at.BASE
START, END = 0x09D2F000, 0x09E00900  # the synthetic segment covers the consumers and the tables
HANDLER = 0x09D6B6B8
V0 = 2


def itype(op, rs, rt, imm):
    return op << 26 | rs << 21 | rt << 16 | (imm & 0xFFFF)


def load_address(address):
    """lui v0,HI; addiu v0,v0,LO building the module offset of `address` (as relocated code does)."""
    value = address - BASE
    return [itype(0x0F, 0, V0, (value + 0x8000) >> 16), itype(0x09, V0, V0, value & 0xFFFF)]


class Image:
    def __init__(self):
        self.buf = bytearray(END - START)

    def put(self, address, *words):
        struct.pack_into(f"<{len(words)}I", self.buf, address - START, *words)

    def half(self, address, *values):
        struct.pack_into(f"<{len(values)}H", self.buf, address - START, *values)

    def elf(self):
        header = bytearray(0x54)
        header[0:4] = b"\x7fELF"
        struct.pack_into("<I", header, 0x1C, 0x34)
        struct.pack_into("<H", header, 0x2C, 1)
        struct.pack_into("<6I", header, 0x34, 1, 0x54, START - BASE, 0, len(self.buf), len(self.buf))
        return bytes(header) + bytes(self.buf)


def build(skip_constant=None):
    img = Image()
    card = 0x1000
    for key, _, address, count, _ in at.TABLES:
        for i in range(count):
            img.put(address + 8 * i, card, HANDLER - BASE)
            card += 1
    for start, count in ((at.GAP[0], 14), (at.TABLES_END, 4)):
        img.put(start, *[HANDLER - BASE] * count)
    for key, address, count, _, _ in at.LISTS:
        img.half(address, *range(0x1100, 0x1100 + count))
    r1 = at.table_by_key("R1")
    img.half(r1[1] + 2 * (r1[2] - 1), at.R1_SENTINEL)
    for address, _, size, keys, constants in at.CONSUMERS:
        code = []
        for key in keys.split():
            t = at.table_by_key(key)
            code += load_address(t[2] if key[0] != "R" else t[1])
        code += [itype(0x09, 0, V0, c) for c in constants if c != skip_constant]
        assert 4 * len(code) <= size
        img.put(address, *code)
    return img


class AiTablesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = at.Module(build().elf())

    def test_layout_is_contiguous(self):
        self.assertEqual(sum(t[3] for t in at.TABLES), 1648)
        self.assertEqual(at.TABLES[0][2] + 8 * sum(t[3] for t in at.TABLES) + (at.GAP[1] - at.GAP[0]),
                         at.TABLES_END)
        self.assertEqual(at.LISTS[-1][1] + 4, at.TABLES[0][2])

    def test_check_passes(self):
        self.assertEqual(at.check(self.module), [])

    def test_check_detects_missing_length_constant(self):
        problems = at.check(at.Module(build(skip_constant=0x2A9).elf()))
        self.assertTrue(any("ai_table_length" in p and "0x2a9" in p for p in problems), problems)

    def test_check_detects_bad_entries(self):
        img = build()
        img.put(0x09E004E0, 5, 0)  # table G entry 0: id out of range, handler not a pointer
        img.half(0x09DFD2DC + 2 * 142, 0x1300)  # R1 no longer ends with its sentinel
        problems = at.check(at.Module(img.elf()))
        self.assertTrue(any("G entry" in p and "out of range" in p for p in problems), problems)
        self.assertTrue(any("G entry" in p and "handler" in p for p in problems), problems)
        self.assertTrue(any("R1 does not end" in p for p in problems), problems)

    def test_check_detects_missing_reference(self):
        img = build()
        img.put(0x09D8C1E8, 0, 0)  # ai_try_summon_enablers no longer builds table C's address
        problems = at.check(at.Module(img.elf()))
        self.assertTrue(any("does not reference table C" in p for p in problems), problems)

    def test_list_rows(self):
        rows = at.list_rows(self.module, {0x1000: "First"}, {HANDLER: "ai_cond_always"})
        self.assertEqual(len(rows), 1648 + 143 + 36 + 1)
        self.assertEqual((rows[0]["table"], rows[0]["card_id"], rows[0]["card"], rows[0]["handler_name"]),
                         ("T1", "0x1000", "First", "ai_cond_always"))
        a = next(r for r in rows if r["table"] == "A")
        self.assertEqual((a["index"], a["address"]), (0, "0x09dfe500"))
        r3 = [r for r in rows if r["table"] == "R3"]
        self.assertEqual([(r["address"], r["handler"]) for r in r3], [("0x09dfd444", "0x09d27348")])

    def test_cards_and_missing(self):
        rows = at.card_rows(self.module)
        sentinel = next(r for r in rows if r["card_id"] == "0x1935")
        self.assertEqual(sentinel["tables"], "R1:142")
        both = next(r for r in rows if r["card_id"] == "0x1100")  # first entry of T1 and of every list
        self.assertEqual(both["count"], 4)
        missing = at.missing_cards(self.module, set(range(0x1000, 0x1000 + 1648)))
        self.assertEqual(dict(missing), {0x1935: 1})

    def test_main(self):
        with tempfile.TemporaryDirectory() as tmp:
            prx = Path(tmp) / "rel_duel_eng.prx"
            prx.write_bytes(build().elf())
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(at.main([str(prx), "--check"]), 0)
            self.assertIn("pair tables: 1648 entries", out.getvalue())
            self.assertTrue(out.getvalue().rstrip().endswith("ok"))
            target = Path(tmp) / "cards.csv"
            self.assertEqual(at.main([str(prx), "cards", "-o", str(target)]), 0)
            with open(target, newline="", encoding="utf-8") as f:
                self.assertEqual(len(list(csv.DictReader(f))), 1648 + 1)  # list ids repeat table ids except the sentinel


if __name__ == "__main__":
    unittest.main()
