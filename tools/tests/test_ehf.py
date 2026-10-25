#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/ehf.py on synthetic data. Run with: python3 -I tools/tests/test_ehf.py"""

import contextlib
import importlib.util
import io
import struct
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("re_ehf", TOOLS / "ehf.py")
ehf = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ehf)


def align(data, boundary=16):
    return data + bytes(-len(data) % boundary)


def track(base=(1, 0, 0, 1, 0, 0), steps=(0, 0, 0), flags=0, keys=()):
    """keys: list of bytes, each a full key record (frame first)."""
    stride = 2 + 4 * bin(flags & 0x1F).count("1") if keys else 0
    return struct.pack("<9f4H", *base, *steps, flags, len(keys), stride, 0) + b"".join(keys)


def anim(*tracks):
    table = 16
    offsets, body = [], b""
    for t in tracks:
        offsets.append(table + len(body))
        body += t
    return struct.pack("<4I", *(offsets + [0] * (4 - len(offsets)))) + body


def shape(anim_block, texture=0x0000, anchor=(-100.0, -50.0), scale=0.1):
    """One textured 4-vertex strip: quad 0..2000 x 0..1000 vertex units, uv 0..2047."""
    if texture is None:
        dl = struct.pack("<6I", 0x55FFFFFF, 0x580000FF, 0x12000100, 0, 0, 0x04040004)
        verts = b"".join(struct.pack("<3h", x, y, 0x4000) for x, y in ((0, 0), (2000, 0), (0, 1000), (2000, 1000)))
    else:
        dl = struct.pack("<6I", 0x55FFFFFF, 0x580000FF, 0x12000102, 0xFFFF0000 | texture, 0, 0x04040004)
        verts = b"".join(struct.pack("<2H3h", u, v, x, y, 0x4000) for u, v, x, y in
                         ((0, 0, 0, 0), (2047, 0, 2000, 0), (0, 2047, 0, 1000), (2047, 2047, 2000, 1000)))
    vtx_off = 0x30 + len(dl)
    anim_off = vtx_off + len(verts)
    head = struct.pack("<I3f6I", 0, *anchor, scale, 0x30, len(dl), vtx_off, len(verts), anim_off, len(anim_block))
    return align(head.ljust(0x30, b"\0") + dl + verts + anim_block)


def clip(frames, nodes, anim_block):
    timeline = b"".join(struct.pack("<iHHHH", *n) for n in nodes)
    head = struct.pack("<6I", 3, frames, 0x20, len(timeline), 0x20 + len(timeline), len(anim_block))
    return align(head.ljust(0x20, b"\0") + timeline + anim_block)


def build(frames, nodes, objects, names, instances=1, rect=(0, 9600, 0, 5440), background=b"\x33\x33\x33\xff"):
    stage = struct.pack("<I4sIIiiii", frames, background, 2, 0, *rect)
    work = bytes((0x78 + 0x28 * instances + 15) // 16 * 16)  # 0x28 per peak live instance
    timeline = b"".join(struct.pack("<iHHHH", *n) for n in nodes)
    body = b"".join(objects)
    name_block = b"".join(n.encode().ljust(16, b"\0") for n in names)
    sections, pos, out = [], 0x40, b""
    for part in (stage, work, timeline, body, name_block):
        pos = (pos + 15) // 16 * 16
        out = out.ljust(pos - 0x40, b"\0")
        sections.append((pos, len(part)))
        out += part
        pos += len(part)
    header = b"EHF\x1a" + bytes(12) + b"".join(struct.pack("<II", *s) for s in sections) + bytes(8)
    return header.ljust(0x40, b"\0") + out


# A layout: depth 1 = a static textured shape at the stage centre; depth 2 = a clip that cycles a
# moving shape (translate key) and nothing; then depth 2 is removed. 30 frames in total.
MOVE = track(base=(1, 0, 0, 1, 1000, 1000), steps=(1.0, 0, 0), flags=0b1001,
             keys=[struct.pack("<Hhh4B", 0, -100, 0, 128, 128, 128, 128),
                   struct.pack("<Hhh4B", 10, 100, 0, 128, 128, 128, 0)])
SHAPE0 = shape(anim(track(base=(1, 0, 0, 1, 4800, 2720))), texture=0x0000)
SHAPE1 = shape(anim(MOVE, track()), texture=0x0010, anchor=(0.0, 0.0), scale=1.0)
CLIP_AT = len(SHAPE0) + len(SHAPE1)
CLIP2 = clip(4, [(len(SHAPE0) // 16, 0, 1, 0, 2), (-1, 0, 1, 0, 2)], anim(track()))
SAMPLE = build(30, [(0, 0, 1, 0, 0), (CLIP_AT // 16, 0, 2, 0, 20), (-1, 0, 2, 0, 10)],
               [SHAPE0, SHAPE1, CLIP2], ["tex_a", "tex_b"], instances=3)


class EhfParseTest(unittest.TestCase):
    def test_parse_sections_and_stage(self):
        layout = ehf.parse(SAMPLE)
        self.assertEqual(layout["frames"], 30)
        self.assertEqual(layout["rect"], (0, 9600, 0, 5440))
        self.assertEqual(layout["background"], (0x33, 0x33, 0x33, 0xFF))
        self.assertEqual(layout["names"], {0: "tex_a", 16: "tex_b"})
        self.assertEqual(layout["slots"], 2)
        self.assertTrue(layout["work_zero"])

    def test_objects_and_timeline(self):
        layout = ehf.parse(SAMPLE)
        self.assertEqual(sorted(layout["objects"]), [0, len(SHAPE0), CLIP_AT])
        shape0 = layout["objects"][0]
        self.assertEqual(shape0["type"], ehf.SHAPE)
        prim = shape0["prims"][0]
        self.assertEqual((prim["texture"], prim["prim"], len(prim["vertices"])), (0, 4, 4))
        self.assertEqual(prim["vertices"][3], ((2047, 2047), (2000, 1000, 0x4000)))
        clip_obj = layout["objects"][CLIP_AT]
        self.assertEqual(clip_obj["type"], ehf.CLIP)
        self.assertEqual(clip_obj["timeline"][1]["object"], None)
        self.assertEqual(layout["timeline"][1]["object"], CLIP_AT)
        moving = layout["objects"][len(SHAPE0)]["tracks"][0]
        self.assertEqual(moving["keys"][1], {"frame": 10, "translate": (100, 0), "multiply": (128, 128, 128, 0)})
        self.assertEqual(ehf.check(layout, {"tex_a.gim", "tex_b.gim"}), [])

    def test_untextured_shape(self):
        data = build(1, [(0, 0, 1, 0, 1)], [shape(anim(track()), texture=None)], [])
        prim = ehf.parse(data)["objects"][0]["prims"][0]
        self.assertIsNone(prim["texture"])
        self.assertEqual(prim["vertices"][1], (None, (2000, 0, 0x4000)))

    def test_check_reports_problems(self):
        bad = build(31, [(0, 0, 1, 0, 30), (7, 0, 2, 0, 0)], [SHAPE0], ["tex_a"])
        problems = ehf.check(ehf.parse(bad), {"other.gim"})
        self.assertTrue(any("waits add up to 30" in p for p in problems))
        self.assertTrue(any("missing object 0x70" in p for p in problems))
        self.assertTrue(any("tex_a.gim not in the archive" in p for p in problems))

    def test_rejects_malformed(self):
        with self.assertRaises(ehf.EhfError):
            ehf.parse(b"EHG" + SAMPLE[3:])
        with self.assertRaises(ehf.EhfError):
            ehf.parse(SAMPLE + bytes(16))
        broken = bytearray(SAMPLE)
        objects = struct.unpack_from("<I", SAMPLE, 0x28)[0]
        struct.pack_into("<I", broken, objects, 7)  # unknown object type
        with self.assertRaises(ehf.EhfError):
            ehf.parse(bytes(broken))

    def test_tmf(self):
        layout = ehf.parse(SAMPLE)
        self.assertTrue(ehf.tmf_matches(layout, b"\x00\x11"))
        self.assertFalse(ehf.tmf_matches(layout, b"\x00"))
        self.assertEqual(ehf.parse_tmf(b"\x01\x10"), [1, 16])


class EhfEvalTest(unittest.TestCase):
    def test_track_interpolation_and_hold(self):
        moving = ehf.parse(SAMPLE)["objects"][len(SHAPE0)]["tracks"][0]
        m, mul, _ = ehf.track_state(moving, 5)
        self.assertAlmostEqual(m[4], 1000.0)
        self.assertAlmostEqual(mul[3], 0.5)
        self.assertAlmostEqual(ehf.track_state(moving, -3)[0][4], 900.0)
        self.assertAlmostEqual(ehf.track_state(moving, 99)[0][4], 1100.0)

    def test_compose_and_apply(self):
        rot = (0.0, 1.0, -1.0, 0.0, 10.0, 0.0)  # x' = -y + 10, y' = x
        self.assertEqual(ehf.apply(rot, 2.0, 3.0), (7.0, 2.0))
        both = ehf.compose(rot, (2.0, 0.0, 0.0, 2.0, 1.0, 0.0))
        self.assertEqual(ehf.apply(both, 2.0, 3.0), ehf.apply(rot, *ehf.apply((2.0, 0.0, 0.0, 2.0, 1.0, 0.0), 2, 3)))

    def test_placements_follow_waits(self):
        timeline = ehf.parse(SAMPLE)["timeline"]
        self.assertEqual(sorted(ehf.placements(timeline, 0)), [1, 2])
        self.assertEqual(sorted(ehf.placements(timeline, 19)), [1, 2])
        self.assertEqual(sorted(ehf.placements(timeline, 20)), [1])

    def test_clip_cycles(self):
        layout = ehf.parse(SAMPLE)
        self.assertEqual(len(ehf.draw_list(layout, 0)), 2)  # shape + clip child
        self.assertEqual(len(ehf.draw_list(layout, 2)), 1)  # clip child removed at clip frame 2
        self.assertEqual(len(ehf.draw_list(layout, 4)), 2)  # clip loops after 4 frames

    def test_render(self):
        layout = ehf.parse(SAMPLE)
        red = (2, 2, bytes([255, 0, 0, 255]) * 4, 2, 2)
        width, height, rgba = ehf.render(layout, 25, {0: red})
        self.assertEqual((width, height), (480, 272))
        # Shape 0: anchor (-100,-50) + 0.1 * (2000, 1000) -> 200x100 twips (10x5 px) centred on (240, 136).
        centre = (136 * 480 + 240) * 4
        self.assertEqual(rgba[centre:centre + 4], bytes([255, 0, 0, 255]))
        outside = (130 * 480 + 240) * 4
        self.assertEqual(rgba[outside:outside + 4], bytes(4))

    def test_render_cli_refuses_output_outside_extracted(self):
        archive = ehf.ehp.build([("lay.ehf", SAMPLE)])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.ehp"
            path.write_bytes(archive)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(ehf.main(["render", str(path), "lay.ehf", "-o", str(Path(tmp) / "x.png")]), 1)
                out = Path(tmp) / "extracted" / "x.png"
                self.assertEqual(ehf.main(["render", str(path), "lay.ehf", "--frame", "0", "-o", str(out)]), 0)
            self.assertEqual(out.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_check_cli(self):
        archive = ehf.ehp.build([("lay.ehf", SAMPLE), ("lay.tmf", b"\x00\x01"), ("tex_a.gim", b""),
                                 ("tex_b.gim", b"")])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.ehp"
            path.write_bytes(archive)
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                self.assertEqual(ehf.main(["check", tmp]), 0)
            self.assertIn("ok 1", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
