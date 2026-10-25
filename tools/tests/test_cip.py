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


def fake_jpeg(entropy=b"\x12\xff\x00\x34\xff\xd0\x56"):
    """A syntactically plausible JPEG (not decodable): SOI, JFIF APP0, a filler DQT, SOF0 at 0x9e, SOS,
    entropy data with a stuffed byte and a restart marker, EOI."""
    app0 = b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    dqt_body = bytes(range(0x9e - 2 - len(app0) - 4))
    dqt = b"\xff\xdb" + struct.pack(">H", 2 + len(dqt_body)) + dqt_body
    sof = b"\xff\xc0\x00\x0b\x08\x00\x10\x00\x10\x01\x01\x11\x00"
    sos = b"\xff\xda\x00\x08\x01\x01\x00\x00\x3f\x00"
    out = b"\xff\xd8" + app0 + dqt + sof + sos + entropy + b"\xff\xd9"
    assert out[0x9e:0xa0] == b"\xff\xc0"
    return out


def fake_elf(payload, addr=0x1000):
    """Minimal ELF with one allocated section at module address `addr` holding `payload`."""
    names = b"\0.data\0.shstrtab\0"
    data_off = 0x34
    names_off = data_off + len(payload)
    shoff = (names_off + len(names) + 3) & ~3
    head = bytearray(b"\x7fELF".ljust(0x34, b"\0"))
    struct.pack_into("<I", head, 0x20, shoff)
    struct.pack_into("<HHH", head, 0x2E, 40, 3, 2)
    sections = bytes(40)
    sections += struct.pack("<IIIIII", 1, 1, 2, addr, data_off, len(payload)).ljust(40, b"\0")
    sections += struct.pack("<IIIIII", 7, 3, 0, 0, names_off, len(names)).ljust(40, b"\0")
    return (bytes(head) + payload + names).ljust(shoff, b"\0") + sections


class CpjTest(unittest.TestCase):
    def test_generator_vectors(self):
        # seed 0: s = 0xd0f >> 1 = 0x687, byte = 0x687 >> 2 & 0xff = 0xa1
        self.assertEqual(cip.cpj_mask(0, 4), bytes.fromhex("a13e9dd4"))
        self.assertEqual(cip.cpj_mask(0xFFFF, 4), bytes.fromhex("cd94280a"))
        self.assertEqual(cip.cpj_mask(0x1234, 300)[:10], cip.cpj_mask(0x1234, 10))

    def test_round_trip(self):
        jpeg = fake_jpeg()
        slot_content = jpeg.ljust(0x1000, b"\xaa")
        stored = bytes(b ^ 0x5C for b in jpeg[:160])
        for seed in (0, 1, 0xBEEF, 0xFFFF):
            slot = cip.cpj_mask_slot(slot_content, seed, filler=bytes(range(160)))
            self.assertEqual(slot[0x9E:0xA0], struct.pack(">H", seed))
            self.assertNotEqual(slot[160:len(jpeg)], jpeg[160:])
            self.assertEqual(cip.cpj_unmask(slot, stored), slot_content)

    def test_jpeg_length_skips_stuffing_and_restarts(self):
        jpeg = fake_jpeg()
        self.assertEqual(cip.jpeg_length(jpeg + b"\xff\xd9junk"), len(jpeg))
        with self.assertRaises(ValueError):
            cip.jpeg_length(b"\0" + jpeg)

    def test_stored_head_from_elf(self):
        stored = bytes(b ^ 0x5C for b in fake_jpeg()[:160])
        elf = fake_elf(b"\x11" * 8 + stored, addr=0x2000)
        self.assertEqual(cip.elf_offset(elf, 0x2008), 0x34 + 8)
        self.assertEqual(cip.cpj_stored_head(elf), stored)  # found by search (not at CPJ_HEAD_ADDRESS)
        with self.assertRaises(ValueError):
            cip.cpj_stored_head(fake_elf(bytes(200)))

    def test_jpeg_command(self):
        jpeg = fake_jpeg()
        stored = bytes(b ^ 0x5C for b in jpeg[:160])
        data = bytearray(build_cip(b"CPJ\x1a", 10, {10: 1, 12: 2}))
        container = cip.Cip(bytes(data))
        slots = [(10, 0), (12, 0), (12, 1)]
        for (card_id, art), seed in zip(slots, (7, 0x8001, 0xFFFE)):
            sector = container.sectors(card_id)[art]
            data[sector * SECTOR:(sector + 1) * SECTOR] = cip.cpj_mask_slot(jpeg.ljust(SECTOR, b"\x5a"), seed)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "card.cip").write_bytes(bytes(data))
            (tmp / "BOOT.BIN").write_bytes(fake_elf(stored))
            self.assertEqual(cip.main(["jpeg", str(tmp / "card.cip"), str(tmp / "out"), "--boot", str(tmp / "BOOT.BIN")]), 0)
            self.assertEqual(sorted(p.name for p in (tmp / "out").iterdir()), ["00010.jpg", "00012.jpg", "00012_1.jpg"])
            for name in ("00010.jpg", "00012_1.jpg"):
                self.assertEqual((tmp / "out" / name).read_bytes(), jpeg)
            self.assertEqual(cip.main(["jpeg", str(tmp / "card.cip"), str(tmp / "full"), "--boot", str(tmp / "BOOT.BIN"),
                                       "--ids", "12", "--limit", "1", "--full"]), 0)
            self.assertEqual((tmp / "full" / "00012.jpg").read_bytes(), jpeg.ljust(SECTOR, b"\x5a"))
            self.assertEqual(len(list((tmp / "full").iterdir())), 1)


if __name__ == "__main__":
    unittest.main()
