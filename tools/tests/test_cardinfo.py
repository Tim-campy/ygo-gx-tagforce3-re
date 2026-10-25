#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/cardinfo.py on a hand-built two-card archive. Run with: python3 -I tools/tests/test_cardinfo.py"""

import contextlib
import importlib.util
import io
import json
import struct
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_cardinfo", Path(__file__).resolve().parents[1] / "cardinfo.py")
cardinfo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cardinfo)


def u16s(*values):
    return struct.pack(f"<{len(values)}H", *values)


# Huffman tree as the game stores it: internal nodes are (left, right) byte offsets, leaves are (0, 0, symbol).
# Codes: 'A' = 0, 'B' = 10, end = 11.
HUFF = u16s(4, 10, 0, 0, ord("A"), 14, 20, 0, 0, ord("B"), 0, 0, 0)
# Card 1 "AB" (01011), card 2 "BA" (10011), packed MSB first: 0101110011 -> 0x5C 0xC0; 10 bits used.
DESC = bytes([0x5C, 0xC0])
NAMES = bytes(8) + "Ab".encode("utf-16-le") + bytes(2) + bytes(2) + "C".encode("utf-16-le") + bytes(2)
INDX = struct.pack("<8I", 4, 0, 8, 0, 16, 5, 20, 10)


def prop(card_id, atk, dfn, kind, attribute, level, race, icon=0):
    w0 = card_id | (atk // 10) << 14 | (dfn // 10) << 23
    w1 = kind | attribute << 6 | level << 10 | icon << 14 | race << 17
    return struct.pack("<II", w0, w1)


PROP = bytes(8) + prop(0xE88, 3000, 2500, 1, 1, 8, 1) + prop(0xE8A, 0, 0, 27, 8, 0, 23, icon=5)
DICT = struct.pack("<4I", 1, 12, 16, 0) + "%c3722".encode("utf-16-le") + bytes(2)


def archive():
    members = {
        "CARD_Desc_E.bin": DESC, "CARD_Huff_E.bin": HUFF, "CARD_Indx_E.bin": INDX,
        "CARD_IntID.bin": u16s(1, 0, 2), "CARD_Name_E.bin": NAMES,
        "CARD_Pass.bin": struct.pack("<3I", 0, 12345678, 0), "CARD_Prop.bin": PROP, "DICT_E.bin": DICT,
    }
    return cardinfo.ehp.build(sorted(members.items(), key=lambda item: item[0].lower()))


class CardInfoTest(unittest.TestCase):
    def setUp(self):
        self.info = cardinfo.CardInfo(archive(), "E")

    def test_properties_and_lookup(self):
        self.assertEqual(self.info.index_of(0xE88), 1)
        self.assertEqual(self.info.index_of(0xE89), 0)
        self.assertEqual(self.info.index_of(0xE00), 0)
        self.assertEqual(self.info.properties(1), {"id": 0xE88, "atk": 3000, "def": 2500, "kind": 1, "attribute": 1,
                                                   "level": 8, "icon": 0, "race": 1, "unknown_22": 0})
        self.assertEqual(self.info.properties(2)["icon"], 5)

    def test_names_and_descriptions(self):
        self.assertEqual([self.info.name(i) for i in (0, 1, 2)], ["", "Ab", "C"])
        self.assertEqual(self.info.huffman(0), ("AB", 5))
        self.assertEqual(self.info.huffman(5), ("BA", 10))

    def test_dictionary_and_escapes(self):
        self.assertEqual(self.info.expand("x$d000y"), "xCy")
        self.assertEqual(self.info.expand("$d0$z"), "C")  # atoi stops at '$'; five characters are always skipped
        self.assertEqual(self.info.expand("$C3red$C0"), "$C3red$C0")

    def test_check_and_export(self):
        self.assertEqual(self.info.check(), [])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cardinfo_eng.ehp"
            path.write_bytes(archive())
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(cardinfo.main([str(path), "--format", "json"]), 0)
        rows = json.loads(out.getvalue())
        self.assertEqual([(r["name"], r["description"], r["passcode"]) for r in rows],
                         [("Ab", "AB", 12345678), ("C", "BA", 0)])


if __name__ == "__main__":
    unittest.main()
