#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/tgm_gltf.py (glTF export of TGM models) on synthetic data built here.
Run with: python3 -I tools/tests/test_tgm_gltf.py"""

import gzip
import importlib.util
import io
import json
import math
import struct
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]


def load(name, folder=TOOLS):
    spec = importlib.util.spec_from_file_location("re_" + name, folder / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tgm = load("tgm")
conv = load("tgm_gltf")
ehp = load("ehp")
fixtures = load("test_tgm", TOOLS / "tests")  # build_tms / build_tmt / build_tma


def align(value, boundary):
    return (value + boundary - 1) // boundary * boundary


def build_tmt(nodes, scalar_tracks, rotation_tracks, frames, flags=0):
    """nodes: [(translation base or 0xFFFF, rotation track or -1, scale base or -1)]; scalar_tracks: [[(frame, value,
    h1, h2)]]; rotation_tracks: [[(frame, (x, y, z, w))]] (f32 unless flags & 4)."""
    node_table = b"".join(struct.pack("<HhhH", t, r, s, 0) for t, r, s in nodes)
    tracks, keys, first = bytearray(), bytearray(), 0
    for track in scalar_tracks:
        tracks += struct.pack("<II", len(track), first if track else 0)
        for key in track:
            keys += struct.pack("<Ifff", *key)
        first += len(track)
    rot_tracks, times, values, rfirst = bytearray(), bytearray(), bytearray(), 0
    for track in rotation_tracks:
        rot_tracks += struct.pack("<II", len(track), rfirst if track else 0)
        for frame, q in track:
            times += struct.pack("<I", frame)
            values += (struct.pack("<4h", *(round(c * 32760) for c in q)) if flags & 4 else struct.pack("<4f", *q))
        rfirst += len(track)
    o_tracks = 0x38 + len(node_table)
    o_keys = o_tracks + len(tracks)
    o_rot_tracks = o_keys + len(keys)
    o_times = o_rot_tracks + len(rot_tracks)
    o_values = align(o_times + len(times), 16)
    header = struct.pack("<4sI5I7I", b"TGMT", 0x38, o_tracks, o_keys, o_rot_tracks, o_times, o_values, len(nodes),
                         len(scalar_tracks), first, len(rotation_tracks), rfirst, frames, flags)
    return header + node_table + tracks + keys + rot_tracks + times + bytes(o_values - o_times - len(times)) + values


def const(value):
    return [(0, value, value, value)]


def curve(*points):
    """Keys with Bezier handles that ease in and out (not linear)."""
    out = []
    for k, (frame, value) in enumerate(points):
        nxt = points[k + 1][1] if k + 1 < len(points) else value
        out.append((frame, value, value, nxt))  # handles at the ends: ease-in-out
    return out


def skeleton_tmt():
    """Two nodes: node 0 translates on x with keys at 0/10/20, on y with keys at 0/15 (independent key frames),
    node 1 rotates 0 -> 90 -> 180 degrees about z and scales."""
    half = math.sqrt(0.5)
    tracks = [curve((0, 0.0), (10, 2.0), (20, 1.0)), curve((0, 0.0), (15, 3.0)), const(0.5),
              const(0.0), const(1.0), const(0.0),
              curve((0, 1.0), (20, 2.0)), const(1.0), const(1.0)]
    rotations = [[(0, (0.0, 0.0, 0.0, 1.0)), (10, (0.0, 0.0, half, half)), (20, (0.0, 0.0, 1.0, 0.0))]]
    return build_tmt([(0, -1, -1), (3, 0, 6)], tracks, rotations, 21)


def etc_tmt(lead=42, focal=35.0, visible=None):
    """A camera/scene file: `lead` leading tracks (0 focal length, 1 aperture 1.0, 2 near 0.01, 3 far 1000), then
    the camera node's translation."""
    tracks = [const(focal), const(1.0), const(0.01), const(1000.0)] + [const(0.0)] * (lead - 4)
    for i, value in (visible or {}).items():
        tracks[10 + i] = const(value)
    tracks += [curve((0, 0.0), (30, 5.0)), const(1.0), const(10.0)]
    half = math.sqrt(0.5)
    return build_tmt([(lead, 0, -1)], tracks, [[(0, (0.0, half, 0.0, half))]], 31, flags=2)


class BezierTest(unittest.TestCase):
    def test_split_is_exact(self):
        seg = (1.0, 4.0, -2.0, 3.0)
        for u in (0.1, 0.5, 0.8):
            left, right = conv.bezier_split(seg, u)
            for s in (0.0, 0.3, 1.0):
                self.assertAlmostEqual(conv.bezier_eval(left, s), conv.bezier_eval(seg, s * u))
                self.assertAlmostEqual(conv.bezier_eval(right, s), conv.bezier_eval(seg, u + s * (1 - u)))
        sub = conv.bezier_sub(seg, 0.25, 0.75)
        self.assertAlmostEqual(conv.bezier_eval(sub, 0.5), conv.bezier_eval(seg, 0.5))

    def test_merge_reproduces_each_track(self):
        tmt = tgm.Tmt(skeleton_tmt())
        keys = [tmt.scalar_keys(k) for k in range(3)]
        frames, values, segments = conv.merge_tracks(keys)
        self.assertEqual(frames, [0, 10, 15, 20])
        for j, (a, b) in enumerate(zip(frames, frames[1:])):
            for s in (0.0, 0.4, 1.0):
                for c in range(3):
                    self.assertAlmostEqual(conv.bezier_eval(segments[j][c], s), tmt.sample_scalar(c, a + s * (b - a)),
                                           places=5)

    def test_linear_detection(self):
        self.assertTrue(conv.is_linear([[(0.0, 1.0, 2.0, 3.0)]]))
        self.assertFalse(conv.is_linear([[(0.0, 0.0, 3.0, 3.0)]]))


class SamplerTest(unittest.TestCase):
    def test_game_sampler_rules(self):
        tmt = tgm.Tmt(skeleton_tmt())
        self.assertEqual(tmt.sample_scalar(0, -5), 0.0)  # before the first key: first value
        self.assertEqual(tmt.sample_scalar(0, 99), 1.0)  # after the last key: last value
        q = tmt.sample_rotation(0, 5)  # halfway to 90 degrees: slerp gives exactly 45 degrees
        self.assertAlmostEqual(q[2], math.sin(math.radians(22.5)), places=6)
        self.assertAlmostEqual(q[3], math.cos(math.radians(22.5)), places=6)

    def test_short_quaternion_scale(self):
        data = build_tmt([(0xFFFF, 0, -1)], [], [[(0, (0.0, 0.0, 0.0, 1.0))]], 2, flags=4)
        self.assertEqual(tgm.Tmt(data).rotation_keys(0)[0][1][3], 1.0)  # 32760 / 32760


class ConvertTest(unittest.TestCase):
    def setUp(self):
        self.tms = tgm.Tms(fixtures.build_tms(bones=2, animated=True))
        self.tmt = tgm.Tmt(skeleton_tmt())

    def convert(self, **kw):
        return conv.convert(self.tms, {}, [("m.tmt", self.tmt)], stem="m", **kw)

    def test_document_is_valid_and_skinned(self):
        doc, binary, images, side, stats = self.convert()
        self.assertEqual(conv.validate(doc, binary), [])
        self.assertEqual(len(doc["skins"][0]["joints"]), 2)
        ibm = conv.accessor_data(doc, binary, doc["skins"][0]["inverseBindMatrices"])
        self.assertEqual(ibm[0], list(self.tms.bone_matrices[0]))  # PSP column order == glTF column-major
        self.assertEqual(doc["nodes"][0]["children"], [1])
        self.assertEqual(stats["triangles"], 3)  # strip of 4 (2 triangles) + 1 triangle
        json.dumps(doc), json.dumps(side)

    def test_default_fps_is_the_game_rate(self):
        self.assertEqual(conv.DEFAULT_FPS, 30.0)  # one frame per game frame at the 30 Hz cap
        _, _, _, side, _ = self.convert()
        self.assertEqual(side["fps"], 30.0)
        self.assertEqual(side["fps_note"], conv.FPS_NOTE)
        _, _, _, side, _ = self.convert(fps=60.0)
        self.assertEqual(side["fps"], 60.0)
        self.assertTrue(side["fps_note"].startswith("user-chosen"))

    def test_animation_matches_game_sampler(self):
        doc, binary, _, side, _ = self.convert(fps=30.0)
        frames = [0, 3.3, 10, 12.5, 15, 17.25, 20, 25]
        worst = conv.compare_animation(doc, binary, side["animations"][0]["gltf_animation"], self.tmt,
                                       {0: 0, 1: 1}, 30.0, frames)
        self.assertLess(max(worst.values()), 1e-5)
        modes = {s["interpolation"] for s in doc["animations"][0]["samplers"]}
        self.assertIn("CUBICSPLINE", modes)
        self.assertIn("LINEAR", modes)

    def test_uv_flip_and_texture_transform(self):
        doc, binary, _, _, _ = self.convert()
        prim = doc["meshes"][0]["primitives"][0]
        uv = conv.accessor_data(doc, binary, prim["attributes"]["TEXCOORD_0"])
        self.assertEqual(uv[0], [0.0, 1.0 - 0x7FFF / 0x8000])  # stored (0, 0x7fff) -> (u, 1 - v)
        tex = {"uv_offset": (0.25, 0.5), "uv_scale": (2.0, 1.0), "name": "t", "animation": -1}
        mat = conv.material_json(type("T", (), {"textures": [tex]})(), 0, self.tms.materials[0], {0: 0})
        transform = mat["pbrMetallicRoughness"]["baseColorTexture"]["extensions"]["KHR_texture_transform"]
        self.assertEqual(transform, {"offset": [0.25, 1.0 - 0.5 - 1.0], "scale": [2.0, 1.0]})

    def test_rest_pose_and_default_channels(self):
        other = tgm.Tmt(build_tmt([(0xFFFF, -1, -1), (0xFFFF, -1, -1)], [], [], 5))
        doc, binary, _, side, _ = conv.convert(self.tms, {}, [("m.tmt", self.tmt), ("n.tmt", other)], stem="m")
        self.assertEqual(doc["nodes"][1]["scale"], [1.0, 1.0, 1.0])
        second = doc["animations"][side["animations"][1]["gltf_animation"]]
        targets = {(c["target"]["node"], c["target"]["path"]) for c in second["channels"]}
        self.assertIn((0, "translation"), targets)  # node 0 rests at (0, 0, 0.5): reset to the game default 0
        self.assertNotIn((1, "scale"), targets)  # rest scale is the default already

    def test_texture_animation_and_material_state(self):
        tma = tgm.Tma(fixtures.build_tma())
        _, _, _, side, _ = self.convert(tma=("m.tma", tma))
        entry = side["texture_animation"]["entries"][0]
        self.assertEqual(entry["layers"][0]["layer"], 0)
        self.assertEqual(len(entry["layers"][0]["uv_offset"]["keys"]), 2)
        state = side["model"]["materials"][0]
        self.assertTrue(state["layers"][0]["lighting"])  # flags 3 = enabled + lighting
        self.assertEqual(state["layers"][0]["texture_name"], "tex.tga")

    def test_camera_and_visibility_tracks(self):
        etc = tgm.Tmt(etc_tmt(visible={3: 1.0}))
        doc, binary, _, side, _ = self.convert(etc=("m-etc.tmt", etc))
        camera = doc["cameras"][0]["perspective"]
        self.assertAlmostEqual(camera["yfov"], 2 * math.atan(0.5 * 25.4 / 35.0))
        self.assertEqual(camera["znear"], 1.0)  # near 0.01 is clamped to 1 by the game
        roles = {t["track"]: t["role"] for t in side["scene"]["tracks"]}
        self.assertEqual(roles[13], "visible_group3")
        camera_node = [i for i, n in enumerate(doc["nodes"]) if "camera" in n][0]
        anim = doc["animations"][0]
        self.assertIn((camera_node, "translation"), {(c["target"]["node"], c["target"]["path"])
                                                     for c in anim["channels"]})
        self.assertEqual(conv.validate(doc, binary), [])

    def test_scene_block_84(self):
        scene, camera = conv.scene_block(tgm.Tmt(etc_tmt(lead=84)))
        self.assertEqual(scene["leading_tracks"], 84)
        self.assertEqual({t["track"]: t["role"] for t in scene["tracks"]}[36], "light1.type")
        self.assertEqual(len(scene["lights"]), 4)

    def test_validate_catches_bad_indices(self):
        doc, binary, _, _, _ = self.convert()
        prim = doc["meshes"][0]["primitives"][0]
        view = doc["bufferViews"][doc["accessors"][prim["indices"]]["bufferView"]]
        broken = bytearray(binary)
        struct.pack_into("<H", broken, view["byteOffset"], 999)
        self.assertTrue(any("index out of range" in p for p in conv.validate(doc, bytes(broken))))


class CommandTest(unittest.TestCase):
    def archive(self):
        tms = fixtures.build_tms(bones=2, animated=True)
        members = {"m.tms": tms, "m.tmt": skeleton_tmt(), "m.tma": fixtures.build_tma(),
                   "m-etc.tmt.gz": gzip.compress(etc_tmt()), "lone.tmt.gz": gzip.compress(skeleton_tmt())}
        return ehp.build([(n, members[n]) for n in sorted(members)])

    def test_check_and_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.ehp"
            path.write_bytes(self.archive())
            out = io.StringIO()
            with redirect_stdout(out):
                status = tgm.main(["gltf", "--check", str(path)])
            self.assertEqual(status, 0, out.getvalue())
            self.assertIn("failing: 0", out.getvalue())
            self.assertIn("models: 1", out.getvalue())
            with redirect_stdout(io.StringIO()):
                status = tgm.main(["gltf", str(path), "--member", "m.tms", "-o", str(Path(tmp) / "out")])
            self.assertEqual(status, 0)
            doc = json.loads((Path(tmp) / "out" / "m.gltf").read_text(encoding="utf-8"))
            self.assertEqual(len(doc["animations"]), 1)  # the lone TGMT is only added with --all-tmt
            side = json.loads((Path(tmp) / "out" / "m.tgm.json").read_text(encoding="utf-8"))
            self.assertEqual(side["source"]["etc"], "m-etc.tmt")
            self.assertEqual(side["texture_animation"]["member"], "m.tma")

    def test_output_inside_repository_is_refused(self):
        self.assertFalse(conv.output_allowed(TOOLS / "out"))
        self.assertTrue(conv.output_allowed(TOOLS.parent / "extracted" / "tgm"))


if __name__ == "__main__":
    unittest.main()
