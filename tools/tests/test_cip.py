#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/cip.py on synthetic data. Run with: python3 -I tools/tests/test_cip.py"""

import importlib.util
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_cip", Path(__file__).resolve().parents[1] / "cip.py")
cip = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cip)

SECTOR = 0x800


def build_cip(magic, first_id, images, sectors_per_image=1):
    """images: {card_id: number of artworks}; ids in between get no image. Mirrors the disc layout:
    header, id table, alternative-artwork lists, 0xff terminator, then slots in id order."""
    last_id = max(images)
    count = last_id - first_id + 1
    lists_start = 0x30 + 8 * count
    dir_end = lists_start + 8 * sum(n for n in images.values() if n > 1) + 8
    sector = (dir_end + SECTOR - 1) // SECTOR
    table, lists = [], bytearray()
    for card_id in range(first_id, last_id + 1):
        arts = images.get(card_id, 0)
        if arts == 0:
            table.append(0)
        elif arts == 1:
            table.append(sector)
            sector += sectors_per_image
        else:
            table.append(0x80000000 | (lists_start + len(lists)))
            for art in range(arts):
                lists += struct.pack("<II", sector | (0x80000000 if art == arts - 1 else 0), 0)
                sector += sectors_per_image
    size = sector * SECTOR
    head = struct.pack("<4sIIIIIIII", magic, size, 0, 0, dir_end, first_id, last_id, 0x30, sectors_per_image)
    directory = head.ljust(0x30, b"\0") + b"".join(struct.pack("<II", v, 0) for v in table) + lists + b"\xff" * 8
    return directory.ljust(size, b"\0")


def swizzle(linear, byte_width, rows):
    out = bytearray()
    for tile_y in range(0, rows, 8):
        for tile_x in range(byte_width // 16):
            for y in range(tile_y, tile_y + 8):
                start = y * byte_width + tile_x * 16
                out += linear[start:start + 16]
    return bytes(out)


def build_gim(fmt, order, width, height, pixels, palette=None):
    def surface(block_id, fmt, order, width, height, bpp, pitch_align, height_align, data):
        head = struct.pack("<9H", 0x30, 0, fmt, order, width, height, bpp, pitch_align, height_align)
        head = head.ljust(0x1C, b"\0") + struct.pack("<II", 0x40, 0x40 + len(data))
        body = head.ljust(0x40, b"\0") + data
        return struct.pack("<HHIII", block_id, 0, 0x10 + len(body), 0x10 + len(body), 0x10) + body

    blocks = b""
    if palette is not None:
        blocks += surface(5, 3, 0, len(palette) // 4, 1, 32, 16, 1, palette)
    blocks += surface(4, fmt, order, width, height, 8, 16, 8, pixels)
    picture = struct.pack("<HHIII", 3, 0, 0x10 + len(blocks), 0x10, 0x10) + blocks
    root = struct.pack("<HHIII", 2, 0, 0x10 + len(picture), 0x10, 0x10) + picture
    return cip.GIM_MAGIC + bytes(4) + root


class DirectoryTest(unittest.TestCase):
    def setUp(self):
        self.data = build_cip(b"CIP\x1a", 100, {100: 1, 102: 3, 103: 1}, sectors_per_image=2)
        self.cip = cip.Cip(self.data)

    def test_header(self):
        self.assertEqual((self.cip.kind, self.cip.first_id, self.cip.last_id, self.cip.count), ("cardh", 100, 103, 4))
        self.assertEqual(self.cip.size, len(self.data))

    def test_plain_empty_and_list_entries(self):
        self.assertEqual(self.cip.sectors(100), [1])
        self.assertEqual(self.cip.sectors(101), [])
        self.assertEqual(self.cip.sectors(102), [3, 5, 7])
        self.assertEqual(self.cip.sectors(103), [9])
        self.assertEqual(self.cip.ids(), [100, 102, 103])

    def test_check_passes_and_detects_gaps(self):
        self.assertEqual(self.cip.check(len(self.data)), [])
        broken = bytearray(self.data)
        struct.pack_into("<I", broken, 0x30 + 8 * 3, 10)  # id 103 points one sector too far
        self.assertTrue(cip.Cip(bytes(broken)).check(len(broken)))

    def test_rejects_unknown_magic(self):
        with self.assertRaises(ValueError):
            cip.Cip(b"XYZ\x1a" + self.data[4:])

    def test_out_of_range_id(self):
        with self.assertRaises(KeyError):
            self.cip.sectors(99)


class PixelTest(unittest.TestCase):
    def test_unswizzle_inverts_swizzle(self):
        linear = bytes(range(256)) * 2  # 32 bytes wide, 16 rows
        self.assertEqual(cip.unswizzle(swizzle(linear, 32, 16), 32, 16), linear)

    def test_dxt1_block_layout(self):
        # Indices first (2 bits per pixel, pixel 0 in the low bits), then two RGB565 endpoints, red high.
        red, blue = 0xF800, 0x001F
        block = struct.pack("<IHH", 0b01, red, blue)  # pixel 0 -> colour 1, the rest -> colour 0
        rgba = cip.decode_dxt1(block, 4, 4)
        self.assertEqual(rgba[0:4], bytes((0, 0, 255, 255)))
        self.assertEqual(rgba[4:8], bytes((255, 0, 0, 255)))

    def test_dxt1_three_colour_mode_is_transparent(self):
        block = struct.pack("<IHH", 0xFFFFFFFF, 0x0000, 0xFFFF)  # c0 <= c1: index 3 is transparent
        self.assertEqual(cip.decode_dxt1(block, 4, 4)[3], 0)

    def test_indexed_swizzled_gim(self):
        width, height = 32, 8
        linear = bytes((x + y) % 4 for y in range(height) for x in range(width))
        palette = b"".join(bytes((i * 10, i * 20, i * 30, 0)) for i in range(4))
        gim = build_gim(5, 1, width, height, swizzle(linear, width, height), palette)
        image, pal = cip.read_gim(gim)
        self.assertEqual((image["format"], image["width"], image["height"]), (5, 32, 8))
        rgba = cip.decode_surface(image, pal)
        x, y = 5, 3
        offset = (y * width + x) * 4
        self.assertEqual(rgba[offset:offset + 4], bytes((0, 0, 0, 255)))  # index (5 + 3) % 4 == 0
        x = 6
        offset = (y * width + x) * 4
        self.assertEqual(rgba[offset:offset + 4], bytes((10, 20, 30, 255)))

    def test_decode_slot_pads_truncated_gim(self):
        pixels = struct.pack("<IHH", 0, 0xFFFF, 0xFFFF) * 4  # 8x8 DXT1, all white
        gim = build_gim(8, 0, 8, 8, pixels)
        container = cip.Cip(build_cip(b"CIP\x1a", 1, {1: 1}))
        width, height, rgba = cip.decode_slot(container, gim[:-8])  # last block cut off
        self.assertEqual((width, height), (8, 8))
        self.assertEqual(rgba[:4], b"\xff\xff\xff\xff")

    def test_png_writer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.png"
            cip.write_png(path, 2, 1, bytes((1, 2, 3, 4, 5, 6, 7, 8)))
            data = path.read_bytes()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack(">II", data[16:24]), (2, 1))
            idat = data.index(b"IDAT")
            length = struct.unpack(">I", data[idat - 4:idat])[0]
            self.assertEqual(zlib.decompress(data[idat + 4:idat + 4 + length]), b"\0" + bytes(range(1, 9)))

    def test_cpj_is_refused(self):
        container = cip.Cip(build_cip(b"CPJ\x1a", 1, {1: 1}))
        with self.assertRaises(ValueError):
            cip.decode_slot(container, bytes(SECTOR))


if __name__ == "__main__":
    unittest.main()
