#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/gim.py on synthetic GIM files. Run with: python3 -I tools/tests/test_gim.py"""

import contextlib
import gzip
import importlib.util
import io
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]


def _load(name):
    spec = importlib.util.spec_from_file_location(f"re_{name}", TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gim = _load("gim")
ehp = _load("ehp")


def swizzle(linear, byte_width, rows):
    out = bytearray()
    for tile_y in range(0, rows, 8):
        for tile_x in range(byte_width // 16):
            for y in range(tile_y, tile_y + 8):
                out += linear[y * byte_width + tile_x * 16:y * byte_width + tile_x * 16 + 16]
    return bytes(out)


def surface(block_id, fmt, order, width, height, bpp, pitch_align, height_align, planes,
            levels=1, frames=1, level_type=1, index_start=0x30):
    """An image/palette block whose planes follow an offset table at `index_start` (as on the disc)."""
    data_start = index_start + 4 * len(planes)
    data_start = (data_start + 15) // 16 * 16
    offsets, position = [], data_start
    for plane in planes:
        offsets.append(position)
        position += len(plane)
    head = struct.pack("<10H2H4I4H", 0x30, 0, fmt, order, width, height, bpp, pitch_align, height_align, 2, 0, 0,
                       index_start, data_start, position, 0, level_type, levels, 3, frames)
    body = (head.ljust(index_start, b"\0") + struct.pack(f"<{len(planes)}I", *offsets)).ljust(data_start, b"\0")
    body += b"".join(planes)
    return struct.pack("<HHIII", block_id, 0, 0x10 + len(body), 0x10 + len(body), 0x10) + body


def build_gim(image, palette=None, palette_first=True):
    blocks = (palette or b"") + image if palette_first else image + (palette or b"")
    picture = struct.pack("<HHIII", 3, 0, 0x10 + len(blocks), 0x10, 0x10) + blocks
    root = struct.pack("<HHIII", 2, 0, 0x10 + len(picture), 0x10, 0x10) + picture
    return gim.MAGIC + bytes(4) + root


def rgba_palette(colours, levels=1, frames=1, pad_to=None):
    plane = b"".join(bytes(c) for c in colours)
    if pad_to:
        plane = plane.ljust(4 * pad_to, b"\0")
    return [plane] * (levels * frames)


def read_png(path):
    """Minimal reader for the RGBA8 PNGs the tool writes (filter 0 only)."""
    data = Path(path).read_bytes()
    pos, idat, width = 8, b"", 0
    while pos < len(data):
        length, kind = struct.unpack_from(">I4s", data, pos)
        body = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            width, height = struct.unpack_from(">II", body)
        elif kind == b"IDAT":
            idat += body
        pos += 12 + length
    raw = zlib.decompress(idat)
    stride = width * 4 + 1
    return width, height, b"".join(raw[y * stride + 1:(y + 1) * stride] for y in range(height))


class DecodeTest(unittest.TestCase):
    def test_index8_swizzled(self):
        width, height = 32, 16
        linear = bytes((x * 3 + y) % 5 for y in range(height) for x in range(width))
        colours = [(i * 40, 255 - i * 40, i, 200 + i) for i in range(5)]
        image = surface(4, 5, 1, width, height, 8, 16, 8, [swizzle(linear, width, height)])
        palette = surface(5, 3, 0, 5, 1, 32, 16, 1, rgba_palette(colours), level_type=2)
        w, h, rgba, notes = gim.decode(*gim.parse(build_gim(image, palette)))
        self.assertEqual((w, h, notes), (width, height, []))
        expected = b"".join(bytes(colours[i]) for i in linear)
        self.assertEqual(rgba, expected)

    def test_index4_linear_odd_width_low_nibble_first(self):
        width, height = 5, 2  # pitch 3 bytes -> aligned to 16
        indices = [[1, 2, 3, 0, 1], [3, 3, 2, 1, 0]]
        rows = b""
        for row in indices:
            padded = row + [0]
            rows += bytes(padded[i] | padded[i + 1] << 4 for i in range(0, 6, 2)).ljust(16, b"\0")
        colours = [(i, i, i, 255) for i in range(16)]
        image = surface(4, 4, 0, width, height, 4, 16, 1, [rows], index_start=0x40)
        palette = surface(5, 3, 0, 16, 1, 32, 16, 1, rgba_palette(colours), level_type=2)
        _, _, rgba, _ = gim.decode(*gim.parse(build_gim(image, palette, palette_first=False)))
        self.assertEqual(list(rgba[0::4]), [v for row in indices for v in row])

    def test_palette_levels_select_alternative_colours(self):
        width, height = 32, 8  # index4: 16 bytes per row, one tile wide
        pixels = bytes(width * height // 2)  # index 0 everywhere
        planes = [bytes((level * 10, 0, 0, 255)).ljust(64, b"\0") for level in range(3)]
        image = surface(4, 4, 1, width, height, 4, 16, 8, [pixels])
        palette = surface(5, 3, 0, 15, 1, 32, 16, 1, planes, levels=3, level_type=2)
        img, pal = gim.parse(build_gim(image, palette))
        self.assertEqual(pal["levels"], 3)
        self.assertEqual(list(gim.planes(img, pal)), [(0, 0, 0), (0, 0, 1), (0, 0, 2)])
        self.assertEqual(gim.plane_suffix(img, pal, 0, 0, 2), "_c2")
        self.assertEqual(gim.decode(img, pal, clut_level=2)[2][:4], bytes((20, 0, 0, 255)))

    def test_frames_pair_image_and_palette_planes(self):
        width, height = 16, 8
        frames = [bytes([f]) * (width * height) for f in range(3)]
        image = surface(4, 5, 1, width, height, 8, 16, 8, frames, frames=3)
        colours = [(i, 2 * i, 3 * i, 255) for i in range(3)]
        forward, backward = b"".join(map(bytes, colours)), b"".join(map(bytes, colours[::-1]))
        pal_planes = [forward, forward, backward]
        palette = surface(5, 3, 0, 3, 1, 32, 16, 1, pal_planes, frames=3, level_type=2)
        img, pal = gim.parse(build_gim(image, palette))
        self.assertEqual(gim.plane_suffix(img, pal, 1, 0, 0), "_f1")
        self.assertEqual(gim.decode(img, pal, frame=1)[2][:4], bytes((1, 2, 3, 255)))
        self.assertEqual(gim.decode(img, pal, frame=2)[2][:4], bytes((0, 0, 0, 255)))  # reversed palette, index 2

    def test_rgba8888_swizzled(self):
        width, height = 8, 8  # 32 bytes per row
        linear = bytes(range(256))
        image = surface(4, 3, 1, width, height, 32, 16, 8, [swizzle(linear, 32, 8)])
        _, _, rgba, _ = gim.decode(*gim.parse(build_gim(image)))
        self.assertEqual(rgba, linear)

    def test_dxt1(self):
        block = struct.pack("<IHH", 0, 0xF800, 0x001F)  # every pixel colour 0 = red
        image = surface(4, 8, 0, 4, 4, 4, 4, 4, [block])
        _, _, rgba, _ = gim.decode(*gim.parse(build_gim(image)))
        self.assertEqual(rgba[:4], bytes((255, 0, 0, 255)))

    def test_index_past_palette_is_transparent_and_noted(self):
        image = surface(4, 5, 0, 16, 1, 8, 16, 1, [bytes([7] * 16)])
        palette = surface(5, 3, 0, 4, 1, 32, 16, 1, rgba_palette([(9, 9, 9, 255)] * 4), level_type=2)
        _, _, rgba, notes = gim.decode(*gim.parse(build_gim(image, palette)))
        self.assertEqual(rgba[:4], b"\0\0\0\0")
        self.assertTrue(notes)

    def test_short_plane_is_an_error(self):
        image = surface(4, 3, 0, 8, 8, 32, 16, 1, [bytes(100)])
        with self.assertRaises(gim.GimError):
            gim.decode(*gim.parse(build_gim(image)))

    def test_indexed_without_palette_is_an_error(self):
        image = surface(4, 5, 0, 16, 1, 8, 16, 1, [bytes(16)])
        with self.assertRaises(gim.GimError):
            gim.parse(build_gim(image))


class CommandTest(unittest.TestCase):
    def setUp(self):
        width, height = 32, 8
        image = surface(4, 4, 1, width, height, 4, 16, 8, [bytes([0x10]) * (width * height // 2)])
        planes = [b"".join(bytes((level, 100 + c, 0, 255)) for c in range(16)) for level in range(2)]
        palette = surface(5, 3, 0, 16, 1, 32, 16, 1, planes, levels=2, level_type=2)
        self.gim = build_gim(image, palette)
        inner = ehp.build([("tex.gim", self.gim), ("other.bin", b"x")])
        self.archive = gzip.compress(ehp.build([("inner.ehp", inner), ("top.gim", self.gim)]))

    def run_main(self, argv):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = gim.main(argv)
        return code, out.getvalue()

    def test_png_batch_and_check_on_nested_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src" / "pack.ehp.gz"
            source.parent.mkdir()
            source.write_bytes(self.archive)
            out = Path(tmp) / "one.png"
            code, _ = self.run_main(["png", str(source), "inner.ehp:tex.gim", "--clut", "1", "-o", str(out)])
            self.assertEqual(code, 0)
            width, height, rgba = read_png(out)
            self.assertEqual((width, height), (32, 8))
            self.assertEqual(rgba[:8], bytes((1, 100, 0, 255, 1, 101, 0, 255)))  # low nibble 0, high nibble 1
            code, text = self.run_main(["batch", str(source.parent), "-o", str(Path(tmp) / "all")])
            self.assertEqual(code, 0)
            names = sorted(p.relative_to(Path(tmp) / "all").as_posix() for p in (Path(tmp) / "all").rglob("*.png"))
            self.assertEqual(names, ["pack.ehp.gz/inner.ehp/tex_c0.png", "pack.ehp.gz/inner.ehp/tex_c1.png",
                                     "pack.ehp.gz/top_c0.png", "pack.ehp.gz/top_c1.png"])
            code, text = self.run_main(["check", str(source.parent)])
            self.assertEqual(code, 0)
            self.assertIn("gim 2, ok 2, planes decoded 4", text)

    def test_check_reports_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "bad.gim").write_bytes(self.gim[:-40])
            code, text = self.run_main(["check", tmp])
            self.assertEqual(code, 1)
            self.assertIn("FAIL bad.gim", text)

    def test_refuses_output_inside_repository(self):
        self.assertFalse(gim.output_allowed(TOOLS / "x.png"))
        self.assertTrue(gim.output_allowed(TOOLS.parent / "extracted" / "x.png"))
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(gim.output_allowed(Path(tmp) / "x.png"))


if __name__ == "__main__":
    unittest.main()
