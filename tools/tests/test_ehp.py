#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/ehp.py. Run with: python3 -I tools/tests/test_ehp.py"""

import contextlib
import gzip
import importlib.util
import io
import struct
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_ehp", Path(__file__).resolve().parents[1] / "ehp.py")
ehp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ehp)

# Hand-built archive with two members whose names leave the size fields unaligned (0x32 and 0x3f),
# the case seen on the disc. Layout: header 0x10, table 0x10, pad 8, names 0x28-0x42, data at 0x50.
NAMES = b"icon0.png\0" + struct.pack("<I", 3) + b"pic1.png\0" + struct.pack("<I", 17)
DATA = b"abc".ljust(16, b"\0") + bytes(range(17))
TOTAL = 0x80
SAMPLE = (struct.pack("<4sI4sI", b"EHP\x03", TOTAL, b"NOT ", 2) + struct.pack("<4I", 0x28, 0x50, 0x36, 0x60)
          + bytes(8) + NAMES).ljust(0x50, b"\0") + DATA.ljust(TOTAL - 0x50, b"\0")


class EhpTest(unittest.TestCase):
    def test_parse_reads_unaligned_size_fields(self):
        self.assertEqual(ehp.parse(SAMPLE), [("icon0.png", b"abc"), ("pic1.png", bytes(range(17)))])

    def test_build_is_inverse_of_parse(self):
        self.assertEqual(ehp.build(ehp.parse(SAMPLE)), SAMPLE)

    def test_build_round_trips_nested_and_empty(self):
        inner = ehp.build([("a.bin", b"x" * 33)])
        outer = ehp.build([("inner.ehp", inner), ("empty.txt", b"")])
        self.assertEqual(ehp.parse(outer), [("inner.ehp", inner), ("empty.txt", b"")])
        self.assertEqual(len(outer) % 16, 0)

    def test_parse_rejects_bad_header(self):
        with self.assertRaises(ValueError):
            ehp.parse(b"EHQ\x03" + SAMPLE[4:])
        with self.assertRaises(ValueError):
            ehp.parse(SAMPLE + b"\0" * 16)

    def test_extract_recursive_gunzip(self):
        inner = ehp.build([("model.tmt.gz", gzip.compress(b"TGMT body"))])
        archive = ehp.build([("pack.ehp", inner), ("note.txt", b"hi")])
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "field.ehp.gz"
            source.write_bytes(gzip.compress(archive))
            out = Path(tmp) / "out"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ehp.main([str(source), "-x", str(out), "-r", "-z"]), 0)
                self.assertEqual(ehp.main([str(source), "--verify"]), 0)
            root = out / "field.ehp.gz.d"
            self.assertEqual((root / "pack.ehp.d" / "model.tmt").read_bytes(), b"TGMT body")
            self.assertEqual((root / "note.txt").read_bytes(), b"hi")


if __name__ == "__main__":
    unittest.main()
