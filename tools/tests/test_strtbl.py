#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/strtbl.py on synthetic tables. Run with: python3 -I tools/tests/test_strtbl.py"""

import contextlib
import importlib.util
import io
import json
import struct
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]


def _load(name):
    spec = importlib.util.spec_from_file_location(f"re_{name}", TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


strtbl = _load("strtbl")
ehp = _load("ehp")

WORDS = ["", "Alpha %s!", "Line one\nline two", "Ünïcödé ✓"]


class ParseTest(unittest.TestCase):
    def test_headed_table_with_end_offset(self):
        blob = strtbl.build(WORDS)
        count, table, base = struct.unpack_from("<3I", blob)
        self.assertEqual((count, table, base), (5, 12, 32))  # four strings plus the end offset
        parsed = strtbl.parse(blob)
        self.assertEqual(parsed["strings"], WORDS)
        self.assertEqual((parsed["layout"], parsed["has_end_offset"], parsed["contiguous"]), ("strtbl", True, True))
        self.assertEqual(parsed["offsets"][-1], len(blob) - base)

    def test_headed_table_without_end_offset(self):
        blob = strtbl.build(WORDS, end_offset=False)
        parsed = strtbl.parse(blob)
        self.assertEqual(parsed["strings"], WORDS)
        self.assertFalse(parsed["has_end_offset"])

    def test_offset_list_layout(self):
        blob = strtbl.build(WORDS[1:], layout=strtbl.LISTED)
        self.assertEqual(struct.unpack_from("<II", blob), (4 + 4 * 4, 0))
        parsed = strtbl.parse(blob)
        self.assertEqual((parsed["layout"], parsed["strings"]), ("offset_list", WORDS[1:]))
        self.assertEqual(strtbl.build(parsed["strings"], parsed["layout"], parsed["has_end_offset"]), blob)

    def test_gap_after_offsets_is_accepted(self):
        # DICT_<l>.bin keeps 4 bytes between the offsets and the strings.
        body = "ab".encode("utf-16-le") + b"\0\0"
        blob = struct.pack("<3I", 1, 12, 20) + struct.pack("<I", 0) + bytes(4) + body
        self.assertEqual(strtbl.parse(blob)["strings"], ["ab"])

    def test_non_tables_are_rejected(self):
        for blob in (b"", bytes(16), struct.pack("<3I", 2, 12, 20) + struct.pack("<2I", 4, 0) + bytes(8),
                     struct.pack("<3I", 1, 12, 16) + struct.pack("<I", 0) + b"a\0b\0",  # not terminated
                     struct.pack("<3I", 1, 12, 16) + struct.pack("<I", 0) + b"\x00\xd8\0\0"):  # lone surrogate
            with self.assertRaises(strtbl.TableError):
                strtbl.parse(blob)

    def test_family_normalises_language_and_digits(self):
        self.assertEqual(strtbl.family("a.ehp/chrzakov003_wordstbl_e.bin"), "chrzakovN_wordstbl_<l>.bin")
        self.assertEqual(strtbl.family("field_strtbl_mapname.bin"), "field_strtbl_mapname.bin")
        self.assertEqual(strtbl.family("x/SysMsgIe.bin"), "SysMsgI<l>.bin")


class CommandTest(unittest.TestCase):
    def run_main(self, argv):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = strtbl.main(argv)
        return code, out.getvalue()

    def make_disc(self, root):
        inner = ehp.build([("strTbl_e.bin", strtbl.build(["A", "B"])), ("data.bin", b"\1\2\3\4" * 4)])
        archive = ehp.build([("menu.ehp", inner), ("title_msg_e.bin", strtbl.build(WORDS)),
                             ("CARD_Name_E.bin", bytes(32))])
        (root / "menu").mkdir(parents=True)
        (root / "menu" / "all_e.ehp").write_bytes(archive)

    def test_check_dump_and_show(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "disc"
            self.make_disc(root)
            code, text = self.run_main(["check", str(root)])
            self.assertEqual(code, 0, text)
            self.assertIn(".bin files 4: string tables 2 (6 strings, 2 rebuilt byte for byte), text in other layouts 1, "
                          "other data 1", text)
            self.assertIn("CARD_Name_<l>.bin  (cardinfo.md)", text)
            out = Path(tmp) / "dump"
            code, _ = self.run_main(["dump", str(root), "-o", str(out)])
            self.assertEqual(code, 0)
            record = json.loads((out / "menu" / "all_e.ehp" / "menu.ehp" / "strTbl_e.json").read_text("utf-8"))
            self.assertEqual(record["strings"], ["A", "B"])
            code, text = self.run_main(["show", str(root / "menu" / "all_e.ehp"), "title_msg_e.bin"])
            self.assertEqual(code, 0)
            self.assertIn("2\tLine one\\nline two", text)

    def test_check_fails_on_broken_text_member(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = ehp.build([("option_msg_e.bin", struct.pack("<3I", 9, 12, 4))])
            (Path(tmp) / "a.ehp").write_bytes(archive)
            code, text = self.run_main(["check", tmp])
            self.assertEqual(code, 1)
            self.assertIn("UNMATCHED 1 x option_msg_<l>.bin", text)

    def test_dump_refuses_repository_paths(self):
        code = strtbl.main(["dump", str(TOOLS), "-o", str(TOOLS / "dump")])
        self.assertEqual(code, 1)


class WalkTest(unittest.TestCase):
    def test_walk_blob_nested_gzip_and_elf(self):
        import gzip
        inner = ehp.build([("x.bin", b"inner")])
        archive = ehp.build([("inner.ehp", inner), ("y.tmt.gz", gzip.compress(b"payload"))])
        elf = b"\x7fELF" + bytes(12) + archive + bytes(8)
        self.assertEqual(list(ehp.walk_blob("BOOT.BIN", elf)),
                         [("BOOT.BIN@0x10/inner.ehp/x.bin", b"inner"), ("BOOT.BIN@0x10/y.tmt", b"payload")])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.ehp.gz"
            path.write_bytes(gzip.compress(archive))
            self.assertEqual(ehp.find_leaf(path, "INNER.EHP:x.bin"), ("a.ehp.gz/inner.ehp/x.bin", b"inner"))
            with self.assertRaises(KeyError):
                ehp.find_leaf(path, "missing.bin")


if __name__ == "__main__":
    unittest.main()
