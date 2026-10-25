#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/iso9660.py. Run with: python3 -I tools/tests/test_iso9660.py"""

import contextlib
import importlib.util
import io
import struct
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_iso9660", Path(__file__).resolve().parents[1] / "iso9660.py")
iso9660 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(iso9660)

S = iso9660.SECTOR


def record(name, lba, size, is_dir):
    body = b"\x00" + struct.pack("<I", lba) + struct.pack(">I", lba)
    body += struct.pack("<I", size) + struct.pack(">I", size) + bytes(7)
    body += bytes([2 if is_dir else 0, 0, 0]) + struct.pack("<HH", 1, 1) + bytes([len(name)]) + name
    if len(name) % 2 == 0:
        body += b"\x00"
    return bytes([len(body) + 1]) + body


def directory(own, parent, children, sectors=1):
    """Build a directory extent; with sectors=2 the second child is pushed into the next sector."""
    data = record(b"\x00", own, S * sectors, True) + record(b"\x01", parent, S, True)
    for index, child in enumerate(children):
        if sectors == 2 and index == 1:
            data += bytes(S - len(data))
        data += child
    return data.ljust(S * sectors, b"\x00")


def build_image(path):
    # Layout: 16 system sectors, PVD at 16, terminator at 17, root at 18, SUB/ at 19-20, data at 21+.
    sectors = {}
    pvd = bytearray(S)
    pvd[0:6] = b"\x01CD001"
    pvd[156:190] = record(b"\x00", 18, S, True)
    sectors[16] = bytes(pvd)
    sectors[17] = b"\xffCD001".ljust(S, b"\x00")
    sectors[18] = directory(18, 18, [record(b"A.BIN;1", 21, 5, False), record(b"SUB", 19, 2 * S, True)])
    sub = directory(19, 18, [record(b"B.DAT;1", 22, S + 3, False), record(b"C.TXT;1", 24, 0, False)], sectors=2)
    sectors[19], sectors[20] = sub[:S], sub[S:]
    sectors[21] = b"hello".ljust(S, b"\x00")
    big = bytes(range(256)) * 8 + b"end"
    sectors[22], sectors[23] = big[:S], big[S:].ljust(S, b"\x00")
    image = b"".join(sectors.get(i, bytes(S)) for i in range(25))
    path.write_bytes(image)
    return big


class Iso9660Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.image = self.root / "test.iso"
        self.big = build_image(self.image)

    def tearDown(self):
        self.tmp.cleanup()

    def test_walk_lists_nested_entries_across_sectors(self):
        with iso9660.Image(self.image) as image:
            entries = [(e.path, e.lba, e.size, e.is_dir) for e in image.walk()]
        self.assertEqual(entries, [("A.BIN", 21, 5, False), ("SUB", 19, 2 * S, True),
                                   ("SUB/B.DAT", 22, S + 3, False), ("SUB/C.TXT", 24, 0, False)])

    def test_extract_writes_exact_bytes(self):
        out = self.root / "out"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(iso9660.main([str(self.image), "sub", "-x", str(out)]), 0)
        self.assertEqual((out / "SUB" / "B.DAT").read_bytes(), self.big)
        self.assertEqual((out / "SUB" / "C.TXT").read_bytes(), b"")
        self.assertFalse((out / "A.BIN").exists())

    def test_rejects_non_iso(self):
        bad = self.root / "bad.iso"
        bad.write_bytes(bytes(S * 17))
        with self.assertRaises(ValueError):
            iso9660.Image(bad)


if __name__ == "__main__":
    unittest.main()
