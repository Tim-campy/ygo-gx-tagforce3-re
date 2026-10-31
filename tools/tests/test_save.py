#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/save.py on a synthetic save. Run with: python3 -I tools/tests/test_save.py"""

import contextlib
import importlib.util
import io
import json
import struct
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_save", Path(__file__).resolve().parents[1] / "save.py")
save = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(save)


def synthetic():
    data = bytearray(save.SAVE_SIZE)
    struct.pack_into("<I", data, 0, save.VERSION)
    base = save.DECK_BASE + save.DECK_SIZE  # slot 1
    struct.pack_into("<3I", data, base, 2, 1, 7)
    data[base + 0x0C:base + 0x0C + 8] = "Test".encode("utf-16-le")
    struct.pack_into("<3I", data, base + save.COUNTS, 3, 1, 1)
    struct.pack_into("<3H", data, base + 0x58, 0xE88, 0xE88, 0xE89)
    struct.pack_into("<H", data, base + 0xD0, 0xE8A)
    struct.pack_into("<H", data, base + 0xEE, 0xE8B)
    struct.pack_into("<I2H", data, base + save.KEY_CARDS, 2, 0xE88, 0xE89)
    for index in range(save.CARD_RECORDS):
        data[save.COLLECTION_BASE + 4 * index + 2] = 3
    data[save.COLLECTION_BASE + 4 * 5:save.COLLECTION_BASE + 4 * 5 + 4] = bytes([4, 2, 1, 0])
    struct.pack_into("<H", data, save.RECIPE_BASE + 2 * 11, 1 | 3 << 1)  # recipe 11 unlocked, owner 3
    struct.pack_into("<7I", data, save.DUEL_BASE, 5, 2, 1, 3, 4, 0, 1)
    struct.pack_into("<3H", data, save.DUEL_BASE + 0x1C + 8 * 3, 2, 1, 0)
    struct.pack_into("<H", data, 0x16E12, 3 << 4 | 1 << 12 | 2 << 1)
    data[0x1B0FC] = 0b110  # pictures 1 and 2
    data[0x1A3C4] = 0b1  # sandwich 1
    return bytes(data)


class MapTest(unittest.TestCase):
    def test_map_is_gap_free(self):
        self.assertEqual(save.check_map(), [])
        self.assertEqual(sum(save.coverage().values()), save.SAVE_SIZE)
        self.assertEqual(save.MAP[-1][0], save.STATE_SIZE)

    def test_check_map_reports_gaps_and_overlaps(self):
        regions = [(0, 4, "a", "H", ""), (8, 4, "b", "H", "")]
        self.assertIn("gap", save.check_map(regions, 0, 12, "t")[0])
        regions = [(0, 8, "a", "H", ""), (4, 8, "b", "H", "")]
        self.assertIn("overlap", save.check_map(regions, 0, 12, "t")[0])
        self.assertIn("ends", save.check_map([(0, 4, "a", "H", "")], 0, 8, "t")[0])

    def test_map_rows(self):
        rows = list(save.map_rows())
        self.assertEqual(rows[0]["key"], "version")
        self.assertTrue(any(r["parent"] == "story_block" for r in rows))


class SaveTest(unittest.TestCase):
    def test_decks(self):
        slots = list(save.decks(synthetic()))
        self.assertEqual(len(slots), 127)
        self.assertEqual(slots[1], {"slot": 1, "owner": 2, "variant": 1, "recipe": 7, "name": "Test",
                                    "main": [0xE88, 0xE88, 0xE89], "side": [0xE8A], "extra": [0xE8B]})
        self.assertEqual(slots[0]["main"], [])
        self.assertEqual(save.DECK_BASE + save.DECK_SIZE * save.DECK_COUNT, 0xFD5C)
        self.assertEqual(save.STORED_BASE + save.STORED_SIZE * save.STORED_COUNT, save.DECK_BASE)

    def test_collection(self):
        records = list(save.collection(synthetic()))
        self.assertEqual(len(records), 3554)
        self.assertEqual(records[5], (5, 4, 2, 1, 0))
        self.assertEqual(records[6], (6, 0, 0, 3, 0))

    def test_decode(self):
        out = save.decode(synthetic())
        self.assertEqual(out["version"], "0x30000")
        self.assertEqual(out["deck_slots"][0]["key_cards"], [0xE88, 0xE89])
        self.assertEqual(out["recipes"], [{"recipe": 11, "owner": 3}])
        self.assertEqual(out["duel_record"]["wins"], 5)
        self.assertEqual(out["duel_record"]["per_character"], [{"character": 3, "wins": 2, "losses": 1, "draws": 0}])
        self.assertEqual(out["partner"], {"flag": 0, "cycle": 2, "character": 3, "variant": 1})
        self.assertEqual(out["picture_bits"], [1, 2])
        self.assertEqual(out["story_block"]["sandwiches_seen"]["bits"], [1])
        self.assertEqual(out["buffer_tail_nonzero_bytes"], 0)
        json.dumps(out)

    def test_check(self):
        self.assertEqual(save.check(synthetic(), {0xE88, 0xE89, 0xE8A, 0xE8B}), [])
        self.assertTrue(save.check(synthetic(), {0xE88}))
        self.assertTrue(save.check(synthetic() + bytes(16)))
        self.assertTrue(save.check(bytes(save.SAVE_SIZE)))  # wrong version
        bad = bytearray(synthetic())
        struct.pack_into("<I", bad, save.DECK_BASE + save.COUNTS, 61)
        with self.assertRaises(ValueError):
            save.check(bytes(bad))

    def test_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "DATA0"
            path.write_bytes(synthetic())
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(save.main(["decks", str(path)]), 0)
            self.assertEqual(len(out.getvalue().splitlines()), 1 + 5)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(save.main([str(path), "--check"]), 0)
            self.assertIn("1 non-empty deck slots, 1 cards owned", out.getvalue())
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(save.main(["--check"]), 0)
            self.assertIn("ok: map covers 0x20000 bytes", out.getvalue())
            target = Path(tmp) / "save.json"
            self.assertEqual(save.main(["json", str(path), "-o", str(target)]), 0)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["dp"], 0)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(save.main(["map"]), 0)
            self.assertIn("buffer_tail", out.getvalue())


if __name__ == "__main__":
    unittest.main()
