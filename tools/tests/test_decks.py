#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/decks.py on hand-built data. Run with: python3 -I tools/tests/test_decks.py"""

import contextlib
import importlib.util
import io
import struct
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_decks", Path(__file__).resolve().parents[1] / "decks.py")
decks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(decks)

HEADER = bytes([1, 0xCC, 0xCC, 0xCC, 0x12, 0x34, 0x56, 0x78])


def ydc(main, extra, side, header=HEADER):
    out = bytearray(header)
    for ids in (main, extra, side):
        out += struct.pack(f"<H{len(ids)}H", len(ids), *ids)
    return bytes(out)


def string_table(strings):
    blobs = [s.encode("utf-16-le") + b"\0\0" for s in strings]
    offsets, position = [], 0
    for blob in blobs:
        offsets.append(position)
        position += len(blob)
    head = struct.pack("<3I", len(strings), 12, 12 + 4 * len(strings)) + struct.pack(f"<{len(strings)}I", *offsets)
    return head + b"".join(blobs)


class YdcTest(unittest.TestCase):
    def test_parse_and_round_trip(self):
        blob = ydc([0xE88] * 3 + [0xE89] * 37, [0x1000], [0xE8A, 0xE8B])
        deck = decks.ydc_parse(blob)
        self.assertEqual(deck["header"], HEADER)
        self.assertEqual(len(deck["main"]), 40)
        self.assertEqual(deck["extra"], [0x1000])
        self.assertEqual(deck["side"], [0xE8A, 0xE8B])
        self.assertEqual(decks.ydc_build(deck), blob)
        self.assertEqual(decks.ydc_check(deck, {0xE88, 0xE89, 0xE8A, 0xE8B, 0x1000}), [])

    def test_rejects_bad_sizes(self):
        with self.assertRaises(ValueError):
            decks.ydc_parse(ydc([0xE88], [], []) + b"\0\0")  # trailing bytes
        with self.assertRaises(ValueError):
            decks.ydc_parse(ydc([0xE88], [], [])[:-2])  # side count missing

    def test_loader_limits_and_unknown_ids(self):
        deck = decks.ydc_parse(ydc([0xE88] * 61, [0xE88] * 16, [], header=bytes(8)))
        problems = decks.ydc_check(deck, {0xE89})
        self.assertEqual(len(problems), 5)  # version byte, main > 60, extra > 15, unknown ids in main and extra


class TablesTest(unittest.TestCase):
    def test_string_table(self):
        self.assertEqual(decks.string_table(string_table(["Starting Deck", "", "Owner 01"])),
                         ["Starting Deck", "", "Owner 01"])

    def test_find_recipe_archive(self):
        archive = decks.ehp.build([("RCP000.ydc", ydc([0xE88], [], [])),
                                   ("recipe_name_e.bin", string_table(["A"]))])
        other = decks.ehp.build([("loading.ehf", b"EHF")])
        data = b"\0" * 32 + other + b"\0" * 16 + archive
        offset, members = decks.find_recipe_archive(data)
        self.assertEqual(offset, 48 + len(other))
        self.assertEqual([name for name, _ in members], ["RCP000.ydc", "recipe_name_e.bin"])

    def test_owner_table_checks(self):
        recipes = {
            "decks": [decks.ydc_parse(ydc([0xE88], [], [])) for _ in range(4)],
            "names": {"e": ["S", "A 01", "A 02", ""]},
            "member_count": 5,
            "owners": [(1, 0, 1, 0), (2, 1, 2, 0)],
            "levels": [3, 4, 6],
            "variants": [(1, 0, 0), (2, 1, 1)],
        }
        self.assertEqual(decks.check_recipes(recipes), [])
        self.assertEqual(decks.owner_of(recipes["owners"]), {0: 1, 1: 2, 2: 2})
        recipes["variants"].append((2, 2, 2))  # owner 2 has only two recipes
        self.assertEqual(len(decks.check_recipes(recipes)), 1)
        recipes["owners"] = [(2, 0, 1, 0), (1, 1, 2, 0)]  # not sorted; owner 2 now has one recipe
        self.assertEqual(len(decks.check_recipes(recipes)), 3)


class SameCardTest(unittest.TestCase):
    def test_same_card_and_file_table(self):
        pairs = [(4007, 1), (4007, 2), (4007, 3), (4021, 1)]
        blob = struct.pack("<I", len(pairs)) + b"".join(struct.pack("<HH", *p) for p in pairs)
        self.assertEqual(decks.read_same_card(blob), pairs)
        problems, runs = decks.check_same_card(pairs, {4007: 3, 4021: 1, 4764: 1})
        self.assertEqual((problems, runs), ([], {4007: 3, 4021: 1}))
        problems, _ = decks.check_same_card([(4007, 2)], {4007: 2})
        self.assertEqual(len(problems), 1)  # numbering must start at 1
        files = struct.pack("<4H", 3, 0, 3720, 3721)
        self.assertEqual(decks.read_file_table(files), [0, 3720, 3721])
        with self.assertRaises(ValueError):
            decks.read_file_table(files + b"\0\0")

    def test_command_line(self):
        pairs = [(4007, 1), (4007, 2)]
        same = struct.pack("<I", 2) + b"".join(struct.pack("<HH", *p) for p in pairs)
        files = struct.pack("<3H", 2, 0, 4007)
        archive = decks.ehp.build([("fileTbl.dat", files), ("sameCardTbl.dat", same)])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "all_e.ehp"
            path.write_bytes(archive)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(decks.main(["samecard", str(path), "--check"]), 0)
        self.assertIn("2 alternative artworks for 1 cards", out.getvalue())


class TutorialTest(unittest.TestCase):
    SCRIPT = bytes.fromhex(
        "01 04 00 3c 00 60 00 68 01"  # message: string 4, x 60, y 96, width 360
        "0b cb 0f"  # card 4043
        "0f 00 00 07 00 08 00 00 00"  # string 7 in the second argument
        "0a 00 00 1e 00"
        "13 02 00"  # caption: string 2
        "06 17")

    def test_parse(self):
        ops = decks.tutorial_parse(self.SCRIPT)
        self.assertEqual([op for _, op, _ in ops], [0x01, 0x0B, 0x0F, 0x0A, 0x13, 0x06, 0x17])
        self.assertEqual(decks.tutorial_strings(ops), [4, 7, 2])
        self.assertEqual(ops[1], (9, 0x0B, bytes.fromhex("cb 0f")))

    def test_rejects(self):
        with self.assertRaises(ValueError):
            decks.tutorial_parse(self.SCRIPT[:-1])  # no end opcode
        with self.assertRaises(ValueError):
            decks.tutorial_parse(self.SCRIPT + b"\x06")  # bytes after the end opcode
        with self.assertRaises(ValueError):
            decks.tutorial_parse(b"\x40\x17")  # unknown opcode


if __name__ == "__main__":
    unittest.main()
