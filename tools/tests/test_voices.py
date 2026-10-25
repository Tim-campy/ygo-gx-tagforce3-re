#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/voices.py on hand-built tables (no game data). Run with: python3 -I tools/tests/test_voices.py"""

import importlib.util
import struct
import types
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_voices", Path(__file__).resolve().parents[1] / "voices.py")
voices = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(voices)


def change_table(*subtables):
    """A *_voiceidchgtbl.bin: 16 u32 offsets, then the u16 sub-tables; unused heads point at the end."""
    body, heads, position = b"", [], 64
    for table in subtables:
        heads.append(position)
        blob = struct.pack(f"<{len(table)}H", *table)
        body += blob
        position += len(blob)
    heads += [position] * (16 - len(heads))
    return struct.pack("<16I", *heads) + body


def bank(targets):
    cues = [types.SimpleNamespace(index=i, kind="riff", target=t) for i, t in enumerate(targets)]
    return types.SimpleNamespace(cues=cues)


class FakeElf:
    """Enough of prx_imports.Elf for Character: identity mapping from module offsets to the buffer."""

    def __init__(self, data):
        self.data = data

    def offset(self, pointer):
        return pointer

    def string(self, pointer):
        return self.data[pointer:self.data.index(b"\0", pointer)].decode()


class VoicesTest(unittest.TestCase):
    def test_change_table(self):
        tables = voices.parse_change_table(change_table([5, 6, 5], [5, 5, 5], [5, 5, 5], [1, 2], [7], [8], [9]))
        self.assertEqual(tables[:7], [[5, 6, 5], [5, 5, 5], [5, 5, 5], [1, 2], [7], [8], [9]])
        self.assertEqual(tables[7:], [[]] * 9)

    def test_string_table(self):
        strings = ["", "Duel!", "My turn!"]
        pool, offsets = b"", []
        for text in strings:
            offsets.append(len(pool))
            pool += text.encode("utf-16-le") + b"\0\0"
        blob = struct.pack("<III", 3, 12, 24) + struct.pack("<3I", *offsets) + pool
        self.assertEqual(voices.string_table(blob), strings)

    def test_sound_ids(self):
        # 2 music banks, then banks of 3, 2 and 1 cues: ids 0, 1, then from 5 (the bank count) on.
        counts = [1, 1, 3, 2, 1]
        ids = voices.expected_first_ids(counts, music_banks=2)
        self.assertEqual(ids, [0, 1, 5, 8, 10])
        self.assertEqual(voices.locate(ids, counts, 9), (3, 1))
        self.assertEqual(voices.locate(ids, counts, 1), (1, 0))
        self.assertIsNone(voices.locate(ids, counts, 11))

    def test_voice_sound_id(self):
        first_ids = {10: 100, 13: 400}
        character = types.SimpleNamespace(voice_bank=10, extra_bank=13)
        self.assertEqual(voices.voice_sound_id(character, 0, first_ids), 400)
        self.assertEqual(voices.voice_sound_id(character, 4, first_ids), 404)  # spills into banks 14-16
        self.assertEqual(voices.voice_sound_id(character, 5, first_ids), 100)
        self.assertEqual(voices.voice_sound_id(character, 9, first_ids), 104)

    def test_character_record(self):
        record = bytearray(voices.CHARACTER_SIZE)
        record[0:2] = b"\x07\x01"
        names = b"ASUKA_1\0cutin_aska01.ehp\0ASUKA\0"
        base = voices.CHARACTER_SIZE
        struct.pack_into("<I", record, 4, base)
        struct.pack_into("<I", record, 0x24, base + 8)
        struct.pack_into("<I", record, 0x38, base + 25)
        struct.pack_into("<II", record, 0x30, 48, 51)
        elf = FakeElf(bytes(record) + names)
        character = voices.Character(elf, voices.BOOT_BASE)
        self.assertEqual((character.character, character.variant, character.name, character.key),
                         (7, 1, "ASUKA_1", "ASUKA"))
        self.assertEqual((character.voice_bank, character.extra_bank), (48, 51))
        self.assertEqual(character.table_name, "chrcutin_aska01_voiceidchgtbl.bin")
        self.assertEqual(voices.set_banks(character), [48, 49, 50, 51, 52, 53, 54])

    def test_check_banks(self):
        banks = {0: bank([0, 16, 0]), 1: bank([0, 0, 0]), 2: bank([0, 0, 0]),
                 3: bank([0, 8]), 4: bank([0]), 5: bank([0]), 6: bank([0])}
        good = voices.parse_change_table(change_table([5, 6, 5], [5, 5, 5], [5, 5, 5], [1, 2], [7], [8], [9]))
        self.assertEqual(voices.check_banks("x", list(range(7)), good, banks, captions=["c"] * 10), [])
        bad = voices.parse_change_table(change_table([5, 6, 7], [5, 5], [5, 5, 5], [1, 2], [7], [8], [9]))
        problems = voices.check_banks("x", list(range(7)), bad, banks, captions=["c"] * 8)
        # cues 0 and 2 share a wave but not a caption; sub-table 1 is short; captions 8 and 9 of 8
        self.assertEqual(len(problems), 4)
        self.assertEqual(voices.check_banks("x", list(range(7)), bad[:1] + good[1:], banks, layout=False), [])

    def test_zako_banks(self):
        self.assertEqual(voices.zako_banks(50)[0], 478)
        self.assertEqual(voices.zako_banks(82), list(range(702, 709)))


if __name__ == "__main__":
    unittest.main()
