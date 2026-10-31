#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/tgm.py on synthetic data. Run with: python3 -I tools/tests/test_tgm.py"""

import gzip
import importlib.util
import io
import math
import struct
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location("re_" + name, TOOLS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tgm = load("tgm")
ehp = load("ehp")

IDENTITY = [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]


def align(value, boundary):
    return (value + boundary - 1) // boundary * boundary


def scale_matrix(factor, translate=(0.0, 0.0, 0.0)):
    return [factor, 0, 0, 0, 0, factor, 0, 0, 0, 0, factor, 0, translate[0], translate[1], translate[2], 1.0]


def build_tms(bones=0, animated=False, scale=2.0):
    """One textured quad as a 4-vertex triangle strip plus one triangle (two primitive entries),
    vertex type 0x542 (weight16 x1, uv16, normal16, position16; 18 bytes)."""
    vtype = 0x542
    positions = [(-1, -1, 0), (1, -1, 0), (-1, 1, 0), (1, 1, 0), (0, 0, 0), (1, 0, 0), (0, 1, 0)]
    verts = bytearray()
    for x, y, z in positions:
        verts += struct.pack("<H2H3h3h", 0x7FFF, 0, 0x7FFF, 0, 0, 0x7FFF,
                             int(x * 0x7FFF), int(y * 0x7FFF), int(z * 0x7FFF))
    verts += bytes(align(len(verts), 4) - len(verts))
    prims = struct.pack("<III", 4, 4, 0) + struct.pack("<III", 3, 3, 4 * 18)
    header_size = 0x60
    o_vertices = header_size + len(prims)
    o_materials = o_vertices + len(verts)
    material = bytearray(tgm.MATERIAL_SIZE)
    struct.pack_into("<4s4s4s4sfI", material, 4, b"\0\0\0\xff", b"\xff" * 4, b"\xff" * 4, b"\x80\x80\x80\0", 20.0, 3)
    for k in range(4):
        struct.pack_into("<i", material, 0x1C + 0x20 * k, 0 if k == 0 else -1)
    struct.pack_into("<HH", material, 0x9C, 1, 0)
    o_textures = o_materials + len(material)
    texture = struct.pack("<II4siIffffi", 0, 0, b"\x01\x01\0\0", -1, 0, 0.0, 0.0, 1.0, 1.0, 0 if animated else -1)
    o_batches = o_textures + len(texture)
    palette = [0] + [-1] * 7 if bones else [-1] * 8
    batch = struct.pack("<8hIHH", *palette, vtype, 2, 0)
    end = o_batches + len(batch)
    if bones:
        o_bones = end
        bone_table = bytearray()
        for i in range(bones):
            bone_table += struct.pack("<hhhH", i - 1, i + 1 if i + 1 < bones else -1, -1, 0)
        o_matrices = align(o_bones + len(bone_table), 16)
        tail = bone_table + bytes(o_matrices - o_bones - len(bone_table))
        tail += b"".join(struct.pack("<16f", *scale_matrix(scale)) for _ in range(bones))
        o_root = o_matrices + 64 * bones
    else:
        o_bones = o_matrices = 0
        o_root = align(end, 16)
        tail = bytes(o_root - end)
    root = struct.pack("<16f", *scale_matrix(scale))
    o_names = o_root + 64
    names = b"tex.tga\0"
    extent = scale
    header = struct.pack("<4sI8I7I6fI", b"TGMS", header_size, o_vertices, o_materials, o_textures, o_batches,
                         o_bones, o_matrices, o_root, o_names, 1, int(animated), 1, 1, int(animated), bones,
                         0 if bones else 0xFFFF, -extent, -extent, -extent, extent, extent, extent, 0)
    return header + prims + verts + material + texture + batch + tail + root + names


def build_tmt(translation=(1.0, 0.0, 0.0), short=False, nodes=1):
    """Node 0: three translation tracks (two keys each, linear Bezier handles) and one rotation track."""
    node_table = b"".join(struct.pack("<HhhH", 3 * i, i, -1, 0) for i in range(nodes))
    tracks, keys = bytearray(), bytearray()
    for i in range(3 * nodes):
        value = translation[i % 3]
        tracks += struct.pack("<II", 2, 2 * i)
        keys += struct.pack("<Ifff", 0, value, value, value) + struct.pack("<Ifff", 10, value, 0.0, 0.0)
    rot_tracks = b"".join(struct.pack("<II", 2, 2 * i) for i in range(nodes))
    times = b"".join(struct.pack("<II", 0, 10) for _ in range(nodes))
    half = math.sqrt(0.5)
    quats = [(0.0, 0.0, 0.0, 1.0), (0.0, 0.0, half, half)] * nodes
    if short:
        rot_keys = b"".join(struct.pack("<4h", *(round(c * 32760) for c in q)) for q in quats)
    else:
        rot_keys = b"".join(struct.pack("<4f", *q) for q in quats)
    o_tracks = 0x38 + len(node_table)
    o_keys = o_tracks + len(tracks)
    o_rot_tracks = o_keys + len(keys)
    o_times = o_rot_tracks + len(rot_tracks)
    o_rot_keys = align(o_times + len(times), 16)
    header = struct.pack("<4sI5I7I", b"TGMT", 0x38, o_tracks, o_keys, o_rot_tracks, o_times, o_rot_keys,
                         nodes, 3 * nodes, 6 * nodes, nodes, 2 * nodes, 11, 4 if short else 0)
    return (header + node_table + tracks + keys + rot_tracks + times + bytes(o_rot_keys - o_times - len(times))
            + rot_keys)


def build_tma(material=0):
    """One entry: UV offset on tracks 0 (u, 0 -> 1) and 1 (v, constant), then one empty track."""
    entry = struct.pack("<16hI", 0, *([-1] * 15), material)
    tracks = struct.pack("<II", 2, 0) + struct.pack("<II", 1, 2) + struct.pack("<II", 0, 0)
    keys = (struct.pack("<Ifff", 0, 0.0, 1 / 3, 2 / 3) + struct.pack("<Ifff", 30, 1.0, 0.0, 0.0)
            + struct.pack("<Ifff", 0, 0.0, 0.0, 0.0))
    o_tracks = 0x24 + len(entry)
    o_keys = o_tracks + len(tracks)
    header = struct.pack("<4sI2I4II", b"TGMA", 0x24, o_tracks, o_keys, 1, 3, 3, 31, 0)
    return header + entry + tracks + keys


class VertexLayoutTest(unittest.TestCase):
    def test_sizes_of_vertex_types_seen_on_the_disc(self):
        expected = {0x502: 12, 0x542: 18, 0x543: 24, 0x55F: 28, 0x15F: 24, 0x143: 20, 0x51E: 20,
                    0x4502: 14, 0x8502: 16, 0xC502: 18, 0x1C502: 26, 0x8543: 28}
        for vtype, size in expected.items():
            self.assertEqual(tgm.vertex_layout(vtype)["size"], size, hex(vtype))

    def test_component_offsets(self):
        layout = tgm.vertex_layout(0x55F)  # weight16, uv f32, colour 8888, normal16, position16
        self.assertEqual(layout["weights"][0], 0)
        self.assertEqual(layout["uv"][0], 4)
        self.assertEqual(layout["color"][0], 12)
        self.assertEqual(layout["normal"][0], 16)
        self.assertEqual(layout["position"][0], 22)

    def test_rejects_indexed_vertices(self):
        with self.assertRaises(ValueError):
            tgm.vertex_layout(0x542 | 0x800)


class TmsTest(unittest.TestCase):
    def test_unskinned_mesh_passes_and_uses_root_matrix(self):
        tms = tgm.Tms(build_tms())
        self.assertEqual(tms.check(), [])
        self.assertEqual((tms.material_count, tms.batch_count, tms.prim_count), (1, 1, 2))
        self.assertEqual(tms.textures[0]["name"], "tex.tga")
        vertex = tms.vertices_of(tms.prims[0], 0x542)[3]
        self.assertAlmostEqual(tms.world_position(vertex, tms.batches[0])[0], 2.0 * 0x7FFF / 0x8000)
        self.assertEqual(tms.bbox_error(), 0.0)

    def test_skinned_mesh_passes(self):
        tms = tgm.Tms(build_tms(bones=2))
        self.assertEqual(tms.check(), [])
        self.assertEqual(tms.bones[1][0], 0)

    def test_animated_texture_counts(self):
        tms = tgm.Tms(build_tms(animated=True))
        self.assertEqual(tms.check(), [])
        self.assertEqual(tms.animated_texture_count, 1)

    def test_detects_broken_tables(self):
        data = bytearray(build_tms())
        struct.pack_into("<I", data, 0x28, 2)  # claim two materials
        with self.assertRaises((ValueError, struct.error, IndexError)):
            problems = tgm.Tms(bytes(data)).check()
            if problems:
                raise ValueError(problems)
        data = bytearray(build_tms())
        struct.pack_into("<I", data, 0x60 + 12 + 4, 4)  # second primitive claims an extra vertex
        self.assertTrue(tgm.Tms(bytes(data)).check())


class TmtTest(unittest.TestCase):
    def test_float_and_short_quaternions(self):
        for short in (False, True):
            tmt = tgm.Tmt(build_tmt(short=short, nodes=2))
            self.assertEqual(tmt.check(), [], short)
            self.assertEqual(tmt.rot_key_size, 8 if short else 16)
            q = tmt.rotation_keys(0)[1][1]
            self.assertAlmostEqual(q[3], math.sqrt(0.5), places=3)

    def test_bezier_sampling(self):
        tmt = tgm.Tmt(build_tmt(translation=(3.0, 0.0, 0.0)))
        self.assertAlmostEqual(tmt.sample_scalar(0, 5), 3.0)
        tma = tgm.Tma(build_tma())
        # TGMA keys use the same Bezier keys: 0 -> 1 over 30 frames with linear handles
        keys = tma.scalar_keys(0)
        self.assertEqual([k[0] for k in keys], [0, 30])

    def test_pose_moves_skinned_vertices(self):
        tms = tgm.Tms(build_tms(bones=1, scale=1.0))
        tmt = tgm.Tmt(build_tmt(translation=(1.0, 0.0, 0.0)))
        world = tgm.pose_matrices(tms, tmt, 0)
        vertex = tms.vertices_of(tms.prims[0], 0x542)[0]  # (-1, -1, 0)
        x, y, _ = tms.world_position(vertex, tms.batches[0], world)
        self.assertAlmostEqual(x, 1.0 - 0x7FFF / 0x8000, places=3)
        self.assertAlmostEqual(y, -0x7FFF / 0x8000, places=3)
        rotated = tgm.pose_matrices(tms, tmt, 10)  # 90 degrees about z at the last key
        x, y, _ = tms.world_position(vertex, tms.batches[0], rotated)
        self.assertAlmostEqual(x, 1.0 + 0x7FFF / 0x8000, places=3)
        self.assertAlmostEqual(y, -0x7FFF / 0x8000, places=3)

    def test_detects_wrong_size(self):
        self.assertTrue(tgm.Tmt(build_tmt() + bytes(16)).check())


class TmaTest(unittest.TestCase):
    def test_passes_and_pairs_with_material(self):
        tma = tgm.Tma(build_tma())
        self.assertEqual(tma.check(), [])
        tms = tgm.Tms(build_tms(animated=True))
        self.assertTrue(tgm.tma_entry_matches(tms, 0, tma.entries[0][16]))
        self.assertFalse(tgm.tma_entry_matches(tms, 0, 5))

    def test_unread_slot_is_reported(self):
        data = bytearray(build_tma())
        struct.pack_into("<h", data, 0x24 + 2 * 3, 1)  # layer 0, slot 3: never read by the game
        self.assertTrue(tgm.Tma(bytes(data)).check())

    def test_second_layer_slots_are_accepted(self):
        data = bytearray(build_tma())
        struct.pack_into("<h", data, 0x24 + 2 * 4, 1)  # layer 1 UV offset on tracks 1-2
        self.assertEqual(tgm.Tma(bytes(data)).check(), [])


class ArchiveTest(unittest.TestCase):
    def make_archive(self):
        tms, tmt, tma = build_tms(animated=True), build_tmt(), build_tma()
        members = [("m.tma", tma), ("m.tms", tms), ("m.tmt", tmt), ("x.tmt.gz", gzip.compress(tmt))]
        names = sorted(n for n, _ in members)
        blob = ehp.build([(n, dict(members)[n]) for n in names])
        offsets = {}
        for i, name in enumerate(names):
            offsets[name] = struct.unpack_from("<I", blob, 0x10 + 8 * i + 4)[0]
        ptrs = struct.pack("<5I", offsets["m.tms"], offsets["m.tmt"], offsets["m.tma"], 0, 0xFFFFFFFF)
        members.append(("m-ptrs.txt", ptrs))
        names = sorted((n for n, _ in members), key=str.lower)
        # the pointer list sorts before the models, so offsets shift; rebuild with corrected values
        blob = ehp.build([(n, dict(members)[n]) for n in names])
        offsets = {n: struct.unpack_from("<I", blob, 0x10 + 8 * i + 4)[0] for i, n in enumerate(names)}
        members[-1] = ("m-ptrs.txt", struct.pack("<5I", offsets["m.tms"], offsets["m.tmt"], offsets["m.tma"], 0,
                                                 0xFFFFFFFF))
        return ehp.build([(n, dict(members)[n]) for n in names])

    def test_walk_and_pointer_lists(self):
        data = self.make_archive()
        (prefix, members, offsets), = list(tgm.archive_members(data))
        found = sorted(name for name, _, _ in tgm.tgm_members(members))
        self.assertEqual(found, ["m.tma", "m.tms", "m.tmt", "x.tmt"])
        result = tgm.check_pointer_lists(members, offsets)
        self.assertEqual(result, {".tms": 1, ".tmt": 1, ".tma": 1, "null": 1})

    def test_check_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.ehp"
            path.write_bytes(self.make_archive())
            out = io.StringIO()
            with redirect_stdout(out):
                status = tgm.main(["check", str(path)])
            self.assertEqual(status, 0, out.getvalue())
            self.assertIn("failing: 0", out.getvalue())
            self.assertIn("tma entries match tms animated textures: 1", out.getvalue())

    def test_vtmt_extension(self):
        self.assertEqual(tgm.tgm_name("voice01.vtmt.gz"), "voice01.vtmt")
        self.assertIsNone(tgm.tgm_name("a-ptrs.txt"))


if __name__ == "__main__":
    unittest.main()
