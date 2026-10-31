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

    def test_embedded_in_elf(self):
        # A minimal ELF: header with one PT_LOAD program header (p_offset 0x54, p_vaddr 0), then data that
        # holds two archives, the way BOOT.BIN carries its six.
        first = ehp.build([("a.bin", b"first")])
        second = ehp.build([("RCP000.ydc", b"\1" * 20), ("b.bin", b"")])
        body = b"\0" * 12 + first + b"EHP\x03junk" + second
        header = bytearray(0x54)
        header[:4] = b"\x7fELF"
        struct.pack_into("<I", header, 0x1C, 0x34)  # e_phoff
        struct.pack_into("<HH", header, 0x2A, 0x20, 1)  # e_phentsize, e_phnum
        struct.pack_into("<5I", header, 0x34, 1, 0x54, 0, 0, len(body))
        elf = bytes(header) + body
        report = ehp.embedded_report(elf)
        self.assertEqual([(offset, module) for offset, module, _, _ in report],
                         [(0x54 + 12, 12), (0x54 + 12 + len(first) + 8, 12 + len(first) + 8)])
        self.assertEqual([len(members) for *_, members in report], [1, 2])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "BOOT.BIN"
            path.write_bytes(elf)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(ehp.main([str(path), "--check"]), 0)
                self.assertEqual(ehp.main([str(path), "--base", "08804000"]), 0)
                self.assertEqual(ehp.main([str(path), "-x", str(Path(tmp) / "out")]), 0)
            self.assertIn("ok: BOOT.BIN: 2 embedded archives, 3 members", out.getvalue())
            self.assertIn("(+0xc, 0x0880400c)", out.getvalue())
            self.assertEqual((Path(tmp) / "out" / f"BOOT.BIN@{0x54 + 12:#x}.d" / "a.bin").read_bytes(), b"first")
            path.write_bytes(bytes(header) + b"\0" * len(body))
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(ehp.main([str(path), "--check"]), 1)  # no archive at all

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
