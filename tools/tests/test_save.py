#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/save.py on a synthetic save. Run with: python3 -I tools/tests/test_save.py"""

import contextlib
import importlib.util
import io
import struct
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_save", Path(__file__).resolve().parents[1] / "save.py")
save = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(save)


def synthetic():
    data = bytearray(save.SAVE_SIZE)
    base = save.DECK_BASE + save.DECK_SIZE  # slot 1
    struct.pack_into("<4I", data, base, 0, 2, 0, 1)
    data[base + 0x10:base + 0x10 + 8] = "Test".encode("utf-16-le")
    struct.pack_into("<3I", data, base + save.COUNTS, 3, 1, 1)
    struct.pack_into("<3H", data, base + 0x5C, 0xE88, 0xE88, 0xE89)
    struct.pack_into("<H", data, base + 0xD4, 0xE8A)
    struct.pack_into("<H", data, base + 0xF2, 0xE8B)
    for index in range(save.CARD_RECORDS):
        data[save.COLLECTION_BASE + 4 * index + 2] = 3
    data[save.COLLECTION_BASE + 4 * 5:save.COLLECTION_BASE + 4 * 5 + 4] = bytes([4, 2, 1, 0])
    return bytes(data)


class SaveTest(unittest.TestCase):
    def test_decks(self):
        slots = list(save.decks(synthetic()))
        self.assertEqual(len(slots), 127)
        self.assertEqual(slots[1], {"slot": 1, "owner": 2, "recipe": 1, "name": "Test",
                                    "main": [0xE88, 0xE88, 0xE89], "side": [0xE8A], "extra": [0xE8B]})
        self.assertEqual(slots[0]["main"], [])

    def test_collection(self):
        records = list(save.collection(synthetic()))
        self.assertEqual(len(records), 3554)
        self.assertEqual(records[5], (5, 4, 2, 1, 0))
        self.assertEqual(records[6], (6, 0, 0, 3, 0))

    def test_check(self):
        self.assertEqual(save.check(synthetic(), {0xE88, 0xE89, 0xE8A, 0xE8B}), [])
        self.assertTrue(save.check(synthetic(), {0xE88}))
        self.assertTrue(save.check(synthetic() + bytes(16)))
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


if __name__ == "__main__":
    unittest.main()
