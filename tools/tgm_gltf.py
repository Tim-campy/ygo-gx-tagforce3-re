#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Convert TGM models (TGMS) and their animations (TGMT, TGMA) to glTF 2.0 plus a JSON side file, with the
standard library only. See docs/formats/tgm.md, "glTF export". Used by `tools/tgm.py gltf`.

What goes where:
- glTF (`<stem>.gltf` + `<stem>.bin` + PNG textures): meshes (triangle lists, de-stripped), materials, the
  skeleton (one node per bone, hierarchy from the TGMS bone table), the skin (inverse bind matrices = the TGMS
  bone offset matrices, which include the s16 de-quantisation), node animations (translation/scale as exact
  CUBICSPLINE conversions of the Bezier tracks, rotation as LINEAR = slerp, which is what the game does), and
  the camera of an `-etc` TGMT.
- Side file (`<stem>.tgm.json`): everything glTF cannot hold without extensions: the raw tracks as stored,
  the decoded scene block of `-etc` files (camera lens, fog, ambient, lights, visibility groups), texture
  animation (TGMA), material render state, and every field whose meaning is not established.
"""

import importlib.util
import json
import math
import struct
import zlib
from collections import Counter
from pathlib import Path

TOOLS = Path(__file__).resolve().parent


def _load(name):
    spec = importlib.util.spec_from_file_location("re_" + name, TOOLS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tgm = _load("tgm")
gim = _load("gim")

SCHEMA = "tf3-tgm-scene"
SCHEMA_VERSION = 1
DEFAULT_FPS = 30.0  # assumption: one animation frame per update call; the update rate is not established
ASPECT = 480.0 / 272.0  # rel_duel_draw +0x86490 (perspective aspect used with the -etc camera)
MM_PER_INCH = 25.4  # rel_duel_draw +0x86494 / +0x85184 hold 0.03937 = 1 / 25.4
LINEAR_EPS = 1e-5

# GL / glTF enums
FLOAT, USHORT, UINT, UBYTE = 5126, 5123, 5125, 5121
ARRAY_BUFFER, ELEMENT_ARRAY_BUFFER = 34962, 34963
REPEAT, CLAMP = 10497, 33071
GE_COLOR_TO_GIM = {4: 0, 5: 1, 6: 2}  # GE vertex colour code -> GIM pixel format code used by cip.color

# Leading scalar tracks of -etc TGMT files (rel_duel_draw 0x098a093c and 0x0985b504 / 0x09842900).
CAMERA_TRACKS = {0: "focal_length_mm", 1: "film_aperture_in", 2: "near", 3: "far"}
SCENE84_TRACKS = {4: "fog_enable", 5: "fog_color_r", 6: "fog_color_g", 7: "fog_color_b", 8: "fog_near",
                  9: "fog_far", 10: "ambient_r", 11: "ambient_g", 12: "ambient_b"}
LIGHT_TRACKS = ("type", "enabled", "ambient_r", "ambient_g", "ambient_b", "diffuse_r", "diffuse_g", "diffuse_b",
                "specular_r", "specular_g", "specular_b", "attenuation_constant", "attenuation_linear",
                "attenuation_quadratic", "spot_cutoff_angle", "spot_exponent")
VISIBILITY_FIRST, VISIBILITY_COUNT = 10, 32  # 42-track files: track 10 + i == 0 hides visibility group i


# --- Bezier tracks -> glTF samplers ------------------------------------------------------------------

def bezier_split(seg, u):
    """De Casteljau split of a cubic Bezier (v0, h1, h2, v1) at parameter u; returns (left, right)."""
    p0, p1, p2, p3 = seg
    a, b, c = p0 + (p1 - p0) * u, p1 + (p2 - p1) * u, p2 + (p3 - p2) * u
    d, e = a + (b - a) * u, b + (c - b) * u
    f = d + (e - d) * u
    return (p0, a, d, f), (f, e, c, p3)


def bezier_sub(seg, u0, u1):
    """The part of a cubic Bezier between parameters u0 < u1, as a cubic Bezier (exact)."""
    if u1 < 1.0:
        seg = bezier_split(seg, u1)[0]
        u0 = u0 / u1 if u1 else 0.0
    if u0 > 0.0:
        seg = bezier_split(seg, u0)[1]
    return seg


def bezier_eval(seg, u):
    v0, h1, h2, v1 = seg
    w = 1 - u
    return w * w * w * v0 + 3 * w * w * u * h1 + 3 * w * u * u * h2 + u * u * u * v1


def track_segment(keys, f0, f1):
    """The game's curve of one scalar track restricted to frames [f0, f1], which contain no key strictly inside,
    as a Bezier in the local parameter (f - f0) / (f1 - f0)."""
    if not keys:
        return (0.0,) * 4
    if f1 <= keys[0][0]:
        return (keys[0][1],) * 4
    if f0 >= keys[-1][0]:
        return (keys[-1][1],) * 4
    for (t0, v0, h1, h2), (t1, v1, _, _) in zip(keys, keys[1:]):
        if t0 <= f0 and f1 <= t1:
            return bezier_sub((v0, h1, h2, v1), (f0 - t0) / (t1 - t0), (f1 - t0) / (t1 - t0))
    raise ValueError("a key lies inside the requested frame range")


def merge_tracks(key_lists):
    """Combine scalar tracks (one per component) with independent key frames into one keyed vector curve.

    Returns (frames, values, segments): frames = sorted union of the key frames; values[j] = vector at frames[j];
    segments[j][c] = the Bezier of component c from frames[j] to frames[j+1]. The result reproduces the game's
    curves exactly: splitting a cubic Bezier at an intermediate frame is exact because the parameter is linear in
    time."""
    frames = sorted({k[0] for keys in key_lists for k in keys}) or [0]
    segments = [[track_segment(keys, a, b) for keys in key_lists] for a, b in zip(frames, frames[1:])]
    values = []
    for j, frame in enumerate(frames):
        if j < len(segments):
            values.append([seg[0] for seg in segments[j]])
        elif segments:
            values.append([seg[3] for seg in segments[-1]])
        else:
            values.append([track_segment(keys, frame, frame)[0] for keys in key_lists])
    return frames, values, segments


def is_linear(segments):
    for parts in segments:
        for v0, h1, h2, v1 in parts:
            scale = 1.0 + abs(v0) + abs(v1)
            if abs(h1 - (2 * v0 + v1) / 3) > LINEAR_EPS * scale or abs(h2 - (v0 + 2 * v1) / 3) > LINEAR_EPS * scale:
                return False
    return True


def cubic_output(frames, values, segments, fps):
    """glTF CUBICSPLINE output: per key [in tangent, value, out tangent], tangents in units per second.
    Bezier (v0, h1, h2, v1) over dt seconds = Hermite with out tangent 3 (h1 - v0) / dt, in tangent
    3 (v1 - h2) / dt."""
    n, width = len(frames), len(values[0])
    tin = [[0.0] * width for _ in range(n)]
    tout = [[0.0] * width for _ in range(n)]
    for j, parts in enumerate(segments):
        dt = (frames[j + 1] - frames[j]) / fps
        for c, (v0, h1, h2, v1) in enumerate(parts):
            tout[j][c] = 3 * (h1 - v0) / dt
            tin[j + 1][c] = 3 * (v1 - h2) / dt
    out = []
    for j in range(n):
        out += [tin[j], values[j], tout[j]]
    return out


def quaternion_keys(tmt, track):
    """Rotation keys of a track, normalised, with signs chosen so consecutive keys have a non-negative dot product
    (the game's slerp takes the shortest path; this makes any glTF slerp do the same)."""
    out, previous = [], None
    for frame, q in tmt.rotation_keys(track):
        n = math.sqrt(sum(c * c for c in q)) or 1.0
        q = [c / n for c in q]
        if previous is not None and sum(a * b for a, b in zip(previous, q)) < 0:
            q = [-c for c in q]
        out.append((frame, q))
        previous = q
    return out


# --- glTF document builder ------------------------------------------------------------------------

class Gltf:
    """Accumulates a glTF document with one binary buffer."""

    def __init__(self):
        self.doc = {"asset": {"version": "2.0", "generator": "ygo-tf3-re tools/tgm_gltf.py"},
                    "scene": 0, "scenes": [{"nodes": []}], "nodes": [], "buffers": [], "bufferViews": [],
                    "accessors": []}
        self.bin = bytearray()
        self.used = set()

    def add(self, key, item):
        self.doc.setdefault(key, []).append(item)
        return len(self.doc[key]) - 1

    def view(self, data, target=None):
        while len(self.bin) % 4:
            self.bin.append(0)
        view = {"buffer": 0, "byteOffset": len(self.bin), "byteLength": len(data)}
        if target:
            view["target"] = target
        self.bin += data
        return self.add("bufferViews", view)

    def accessor(self, values, kind, component=FLOAT, normalized=False, target=None, minmax=False):
        """values: list of scalars or of equal-length lists. kind: SCALAR, VEC2, VEC3, VEC4, MAT4."""
        width = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}[kind]
        flat = values if width == 1 else [c for v in values for c in v]
        code = {FLOAT: "f", USHORT: "H", UINT: "I", UBYTE: "B"}[component]
        data = struct.pack(f"<{len(flat)}{code}", *flat)
        accessor = {"bufferView": self.view(data, target), "componentType": component, "count": len(values),
                    "type": kind}
        if normalized:
            accessor["normalized"] = True
        if minmax:
            columns = [values] if width == 1 else list(zip(*values))
            if component == FLOAT:  # bounds of the stored f32 values
                columns = [[struct.unpack("<f", struct.pack("<f", c))[0] for c in col] for col in columns]
            accessor["min"] = [min(col) for col in columns]
            accessor["max"] = [max(col) for col in columns]
        return self.add("accessors", accessor)

    def finish(self, bin_name):
        while len(self.bin) % 4:
            self.bin.append(0)
        self.doc["buffers"] = [{"byteLength": len(self.bin), "uri": bin_name}]
        if self.used:
            self.doc["extensionsUsed"] = sorted(self.used)
        return self.doc, bytes(self.bin)


def png_bytes(width, height, rgba):
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

    raw = b"".join(b"\0" + rgba[y * width * 4:(y + 1) * width * 4] for y in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def rgba_factor(color):
    return [round(c / 255.0, 6) for c in color]


def vertex_color(vertex):
    color = vertex["color"]
    if isinstance(color, tuple):
        return list(color)
    return list(gim.cip.color(color, GE_COLOR_TO_GIM[vertex["color_code"]]))


# --- Scene (-etc) block ------------------------------------------------------------------------------

def leading_tracks(tmt):
    used = [base for node in tmt.nodes for base in (node[0], node[2]) if base not in (0xFFFF, -1)]
    return min(used) if used else tmt.track_count


def keys_json(keys):
    return [list(k) for k in keys]


def scene_block(tmt):
    """Decode the leading scalar tracks of an -etc TGMT (flag 2). Returns (scene dict, camera at frame 0)."""
    lead = leading_tracks(tmt)
    tracks = {i: tmt.scalar_keys(i) for i in range(lead)}
    roles = dict(CAMERA_TRACKS)
    if lead >= 84:
        roles.update(SCENE84_TRACKS)
        for light in range(4):
            for k, name in enumerate(LIGHT_TRACKS):
                roles[20 + 16 * light + k] = f"light{light}.{name}"
    elif lead >= VISIBILITY_FIRST + VISIBILITY_COUNT:
        for i in range(VISIBILITY_COUNT):
            roles[VISIBILITY_FIRST + i] = f"visible_group{i}"
    entries = [{"track": i, "role": roles.get(i), "keys": keys_json(tracks[i])} for i in range(lead)]

    def value(i):
        return tmt.sample_scalar(i, 0) if i < lead else None

    camera = None
    if lead >= 4:
        focal, aperture, near, far = (value(i) for i in range(4))
        yfov = 2 * math.atan(0.5 * aperture * MM_PER_INCH / focal) if focal else None
        camera = {"yfov": yfov, "znear": max(near, 1.0), "zfar": far, "aspectRatio": ASPECT}
    layout = "84-track (camera, fog, ambient, 4 lights)" if lead >= 84 else (
        "42-track (camera, 32 visibility groups)" if lead >= 42 else f"{lead} leading tracks")
    lights = []
    if lead >= 84:
        for light in range(4):
            base = 20 + 16 * light
            lights.append({"light": light, "node": light + 1, "tracks": base,
                           "type_at_frame0": {0: "directional", 1: "point", 2: "spot"}.get(int(value(base)),
                                                                                           int(value(base))),
                           "enabled_at_frame0": int(value(base + 1)) != 0})
    return {"leading_tracks": lead, "layout": layout, "tracks": entries, "lights": lights,
            "camera_at_frame0": camera}, camera


# --- Model conversion ---------------------------------------------------------------------------------

def _batch_groups(tms, material):
    """Group a material's batches by attribute signature and skinning."""
    groups = {}
    for b in tms.batches[material["first_batch"]:material["first_batch"] + material["batch_count"]]:
        layout = tgm.vertex_layout(b["vtype"])
        palette = [x for x in b["palette"] if x >= 0]
        skinned = bool(palette) and bool(tms.bone_count)
        sig = (skinned, "uv" in layout, "color" in layout, "normal" in layout)
        groups.setdefault(sig, []).append((b, layout, palette))
    return groups


def _primitive(gl, tms, sig, batches, material_index, flip):
    skinned, has_uv, has_color, has_normal = sig
    pos, nrm, uv, col, joints, weights, idx = [], [], [], [], [], [], []
    width = 4
    for b, layout, palette in batches:
        if skinned:
            width = max(width, 8 if layout.get("weights", (0, 0, 1))[2] > 4 else 4)
    for b, layout, palette in batches:
        for prim in tms.prims[b["first_prim"]:b["first_prim"] + b["prim_count"]]:
            verts = tms.vertices_of(prim, b["vtype"])
            base = len(pos)
            for v in verts:
                pos.append(v["position"])
                if has_normal:
                    n = v["normal"]
                    length = math.sqrt(sum(c * c for c in n))
                    nrm.append([c / length for c in n] if length > 1e-9 else [0.0, 0.0, 1.0])
                if has_uv:
                    u, w = v["uv"]
                    uv.append([u, 1.0 - w])  # the game draws with v' = (1 - v_offset) - v_scale * v
                if has_color:
                    if "color" in layout and layout["color"][1] != 7:
                        v["color_code"] = layout["color"][1]
                    col.append(vertex_color(v))
                if skinned:
                    ws = v.get("weights", [1.0])
                    total = sum(ws)
                    ws = [w / total for w in ws] if total > 0 else [1.0] + [0.0] * (len(ws) - 1)
                    js = palette[:len(ws)]
                    joints.append(js + [0] * (width - len(js)))
                    weights.append(ws + [0.0] * (width - len(ws)))
            if prim[0] == 3:
                tris = [(k, k + 1, k + 2) for k in range(0, len(verts) - 2, 3)]
            else:
                tris = [(k, k + 1, k + 2) if k % 2 == 0 else (k + 1, k, k + 2) for k in range(len(verts) - 2)]
            for a, b2, c in tris:
                pa, pb, pc = (verts[n]["position"] for n in (a, b2, c))
                if pa == pb or pb == pc or pa == pc:
                    continue  # degenerate strip joint
                idx += [base + a, base + c, base + b2] if flip else [base + a, base + b2, base + c]
    if not idx:
        return None, 0
    attributes = {"POSITION": gl.accessor(pos, "VEC3", target=ARRAY_BUFFER, minmax=True)}
    if has_normal:
        attributes["NORMAL"] = gl.accessor(nrm, "VEC3", target=ARRAY_BUFFER)
    if has_uv:
        attributes["TEXCOORD_0"] = gl.accessor(uv, "VEC2", target=ARRAY_BUFFER)
    if has_color:
        attributes["COLOR_0"] = gl.accessor(col, "VEC4", UBYTE, normalized=True, target=ARRAY_BUFFER)
    if skinned:
        for set_index in range(width // 4):
            sl = slice(4 * set_index, 4 * set_index + 4)
            attributes[f"JOINTS_{set_index}"] = gl.accessor([j[sl] for j in joints], "VEC4", USHORT,
                                                            target=ARRAY_BUFFER)
            attributes[f"WEIGHTS_{set_index}"] = gl.accessor([w[sl] for w in weights], "VEC4",
                                                             target=ARRAY_BUFFER)
    component = USHORT if len(pos) < 65536 else UINT
    primitive = {"attributes": attributes, "indices": gl.accessor(idx, "SCALAR", component,
                                                                  target=ELEMENT_ARRAY_BUFFER),
                 "material": material_index, "mode": 4}
    return primitive, len(idx) // 3


def material_json(tms, i, m, texture_ids):
    """glTF material plus the full render state as extras."""
    layer = m["layers"][0]
    color = layer["color"] if layer["flags"] & tgm.LAYER_ENABLED else m["diffuse"]
    out = {"name": f"mat{i:03d}", "pbrMetallicRoughness": {"baseColorFactor": rgba_factor(color),
                                                           "metallicFactor": 0.0, "roughnessFactor": 1.0},
           "doubleSided": bool(m["flags"] & tgm.MAT_DOUBLE_SIDED)}
    tex = layer["texture"]
    if layer["flags"] & tgm.LAYER_ENABLED and tex in texture_ids:
        info = {"index": texture_ids[tex]}
        t = tms.textures[tex]
        (ou, ov), (su, sv) = t["uv_offset"], t["uv_scale"]
        if (ou, ov, su, sv) != (0.0, 0.0, 1.0, 1.0):  # v' = (1 - ov - sv) + sv * (1 - v) in glTF terms
            info["extensions"] = {"KHR_texture_transform": {"offset": [ou, 1.0 - ov - sv], "scale": [su, sv]}}
        out["pbrMetallicRoughness"]["baseColorTexture"] = info
    if m["flags"] & tgm.MAT_TRANSLUCENT or layer["flags"] & tgm.LAYER_BLEND:
        out["alphaMode"] = "BLEND"
    elif layer["flags"] & tgm.LAYER_ALPHA_TEST and layer["alpha_func"] in (6, 7):  # GU_GREATER, GU_GEQUAL
        out["alphaMode"] = "MASK"
        out["alphaCutoff"] = round(layer["alpha_ref"] / 255.0, 6)
    if not layer["flags"] & tgm.LAYER_LIGHTING:
        out.setdefault("extensions", {})["KHR_materials_unlit"] = {}
    return out


def material_state(tms, m):
    def layer_json(layer):
        return {"flags": layer["flags"], "enabled": bool(layer["flags"] & tgm.LAYER_ENABLED),
                "lighting": bool(layer["flags"] & tgm.LAYER_LIGHTING),
                "alpha_test": bool(layer["flags"] & tgm.LAYER_ALPHA_TEST),
                "blend": bool(layer["flags"] & tgm.LAYER_BLEND),
                "depth_write": not layer["flags"] & tgm.LAYER_NO_DEPTH_WRITE,
                "alpha_write": not layer["flags"] & tgm.LAYER_MASK_ALPHA,
                "texture": layer["texture"],
                "texture_name": tms.textures[layer["texture"]]["name"] if 0 <= layer["texture"] < tms.texture_count
                else None,
                "map_type": layer["map_type"], "color_rgba": list(layer["color"]),
                "alpha_func": layer["alpha_func"], "alpha_ref": layer["alpha_ref"],
                "alpha_mask": layer["alpha_mask"], "depth_func": layer["depth_func"],
                "blend_op_src_dst_pad": list(layer["blend"]),
                "blend_fix_a": list(layer["blend_fix"][0]), "blend_fix_b": list(layer["blend_fix"][1])}

    return {"flags": m["flags"], "translucent_pass": bool(m["flags"] & tgm.MAT_TRANSLUCENT),
            "double_sided": bool(m["flags"] & tgm.MAT_DOUBLE_SIDED),
            "animated_entry": m["anim_entry"] if m["flags"] & tgm.MAT_ANIMATED else None,
            "visibility_group": m["group"] if m["flags"] & tgm.MAT_GROUPED else None,
            "emissive_rgba": list(m["emissive"]), "ambient_rgba": list(m["ambient"]),
            "diffuse_rgba": list(m["diffuse"]), "specular_rgba": list(m["specular"]),
            "shininess": m["shininess"], "layers": [layer_json(l) for l in m["layers"]],
            "batches": [m["first_batch"], m["batch_count"]]}


def texture_state(t):
    return {"name": t["name"], "tex_func": t["tex_func"], "tex_alpha": t["tex_alpha"],
            "mode_bytes_8_9": list(t["mode"][:2]), "env_color_rgba": list(t["env_color"]),
            "wrap_u": t["wrap"][0], "wrap_v": t["wrap"][1], "wrap_bytes_2_3": list(t["wrap"][2:]),
            "uv_offset": list(t["uv_offset"]), "uv_scale": list(t["uv_scale"]), "animation": t["animation"]}


def node_tracks_json(tmt, node):
    tbase, rot, sbase, pad = tmt.nodes[node]
    return {"node": node,
            "translation": None if tbase == 0xFFFF else [keys_json(tmt.scalar_keys(tbase + k)) for k in range(3)],
            "rotation": None if rot == -1 else [[f, *q] for f, q in tmt.rotation_keys(rot)],
            "scale": None if sbase == -1 else [keys_json(tmt.scalar_keys(sbase + k)) for k in range(3)],
            "translation_track": None if tbase == 0xFFFF else tbase, "rotation_track": None if rot == -1 else rot,
            "scale_track": None if sbase == -1 else sbase}


def tma_json(tma):
    entries = []
    for i, e in enumerate(tma.entries):
        layers = []
        for layer in range(tgm.TMA_LAYERS):
            channels = {}
            for slot, (name, width) in tgm.TMA_SLOTS.items():
                base = e[4 * layer + slot]
                if base != -1:
                    channels[name] = {"track": base, "keys": [keys_json(tma.scalar_keys(base + k))
                                                              for k in range(width)]}
            if channels:
                layers.append({"layer": layer, **channels})
        entries.append({"entry": i, "material": e[16], "layers": layers})
    return {"frame_count": tma.frame_count, "entries": entries,
            "apply": "per frame: texture uv_offset = (u, v) tracks, uv_scale = (u, v) tracks (default 1), layer "
                     "colour alpha = clamp(trunc(255 * alpha), 0, 255); GE coordinate = (u * su + ou, "
                     "(1 - ov) - sv * v) (BOOT.BIN 0x08832428, 0x0882e720)"}


def pose_trs(tmt, node, frame):
    tbase, rot, sbase, _ = tmt.nodes[node]
    t = [0.0] * 3 if tbase == 0xFFFF else [tmt.sample_scalar(tbase + k, frame) for k in range(3)]
    r = [0.0, 0.0, 0.0, 1.0] if rot == -1 else list(tmt.sample_rotation(rot, frame))
    s = [1.0] * 3 if sbase == -1 else [tmt.sample_scalar(sbase + k, frame) for k in range(3)]
    return t, r, s


def animation_channels(gl, tmt, node_ids, fps, rest):
    """Samplers and channels for every node of a TGMT; node_ids[i] is the glTF node animated by TGMT node i.
    A node path without a track gets a constant channel with the game's default when the glTF rest value
    differs (the game resets absent tracks to 0 / identity / 1, not to a rest pose)."""
    samplers, channels = [], []
    defaults = {"translation": [0.0] * 3, "rotation": [0.0, 0.0, 0.0, 1.0], "scale": [1.0] * 3}

    def add(node, path, frames, output, interpolation):
        times = [f / fps for f in frames]
        kind = "VEC4" if path == "rotation" else "VEC3"
        sampler = {"input": gl.accessor(times, "SCALAR", minmax=True), "output": gl.accessor(output, kind),
                   "interpolation": interpolation}
        samplers.append(sampler)
        channels.append({"sampler": len(samplers) - 1, "target": {"node": node, "path": path}})

    for i, (tbase, rot, sbase, _) in enumerate(tmt.nodes):
        node = node_ids.get(i)
        if node is None:
            continue
        for path, base in (("translation", tbase if tbase != 0xFFFF else None), ("scale", sbase if sbase != -1
                                                                                  else None)):
            if base is None:
                if rest.get(node, {}).get(path, defaults[path]) != defaults[path]:
                    add(node, path, [0], [defaults[path]], "STEP")
                continue
            frames, values, segments = merge_tracks([tmt.scalar_keys(base + k) for k in range(3)])
            if is_linear(segments):
                add(node, path, frames, values, "LINEAR")
            else:
                add(node, path, frames, cubic_output(frames, values, segments, fps), "CUBICSPLINE")
        if rot == -1:
            if rest.get(node, {}).get("rotation", defaults["rotation"]) != defaults["rotation"]:
                add(node, "rotation", [0], [defaults["rotation"]], "STEP")
        else:
            keys = quaternion_keys(tmt, rot)
            if keys:
                add(node, "rotation", [k[0] for k in keys], [k[1] for k in keys], "LINEAR")
    return samplers, channels


def convert(tms, members=None, animations=(), etc=None, tma=None, fps=DEFAULT_FPS, flip=False, stem="model",
            textures=True, source=None):
    """Build (gltf dict, bin bytes, {png name: png bytes}, side dict, stats).

    tms: tgm.Tms; members: {name: bytes} of the archive (for textures); animations: [(name, tgm.Tmt)] node
    animations of the skeleton (the first one gives the rest pose); etc: (name, tgm.Tmt) camera/scene file or
    None; tma: (name, tgm.Tma) or None."""
    gl = Gltf()
    members = members or {}
    side = {"format": SCHEMA, "version": SCHEMA_VERSION, "source": source or {}, "fps": fps,
            "fps_note": "assumed; the game advances one frame per update call (BOOT.BIN 0x0882fa94)",
            "model": {}, "animations": [], "texture_animation": None, "unknown": []}
    stats = Counter()
    images = {}

    # textures and materials
    texture_ids, image_ids, sampler_ids = {}, {}, {}
    for t_index, t in enumerate(tms.textures):
        gim_name, blob = tgm.texture_member(t["name"], members)
        if blob is None:
            stats["texture without gim"] += 1
            continue
        if gim_name not in image_ids:
            try:
                image, palette = gim.parse(blob)
                width, height, rgba, _ = gim.decode(image, palette)
            except (ValueError, KeyError, struct.error) as error:
                stats["texture decode error"] += 1
                side["unknown"].append({"kind": "texture_decode_error", "where": f"texture {t_index}",
                                        "raw": str(error)})
                continue
            png = f"{stem}_{Path(gim_name).stem}.png"
            if textures:
                images[png] = png_bytes(width, height, rgba)
            image_ids[gim_name] = gl.add("images", {"uri": png, "name": gim_name})
        wrap = (CLAMP if t["wrap"][0] else REPEAT, CLAMP if t["wrap"][1] else REPEAT)
        if wrap not in sampler_ids:
            sampler_ids[wrap] = gl.add("samplers", {"wrapS": wrap[0], "wrapT": wrap[1]})
        texture_ids[t_index] = gl.add("textures", {"source": image_ids[gim_name], "sampler": sampler_ids[wrap],
                                                   "name": t["name"]})
    for i, m in enumerate(tms.materials):
        mat = material_json(tms, i, m, texture_ids)
        for ext in mat.get("extensions", {}):
            gl.used.add(ext)
        if "extensions" in mat.get("pbrMetallicRoughness", {}).get("baseColorTexture", {}):
            gl.used.add("KHR_texture_transform")
        gl.add("materials", mat)

    # skeleton
    bone_nodes = {}
    rest = {}
    primary = animations[0][1] if animations else None
    if tms.bone_count:
        for i in range(tms.bone_count):
            node = {"name": f"bone{i:03d}", "extras": {"tgm_bone": i}}
            if primary is not None:
                t, r, s = pose_trs(primary, i, 0)
                node.update({"translation": t, "rotation": r, "scale": s})
                rest[i] = {"translation": t, "rotation": r, "scale": s}
            bone_nodes[i] = gl.add("nodes", node)
        for i, (parent, child, sibling, _) in enumerate(tms.bones):
            if parent == -1:
                gl.doc["scenes"][0]["nodes"].append(bone_nodes[i])
            else:
                gl.doc["nodes"][bone_nodes[parent]].setdefault("children", []).append(bone_nodes[i])
        ibm = gl.accessor([list(m) for m in tms.bone_matrices], "MAT4")
        skin = gl.add("skins", {"joints": [bone_nodes[i] for i in range(tms.bone_count)], "inverseBindMatrices": ibm,
                                "skeleton": bone_nodes[tms.root_bone], "name": "skeleton"})

    # meshes: skinned primitives in one mesh, unskinned ones (root matrix) in another
    skinned_prims, static_prims = [], []
    for i, m in enumerate(tms.materials):
        for sig, batches in _batch_groups(tms, m).items():
            prim, tris = _primitive(gl, tms, sig, batches, i, flip)
            if prim is None:
                continue
            stats["triangles"] += tris
            (skinned_prims if sig[0] else static_prims).append(prim)
    if skinned_prims:
        mesh = gl.add("meshes", {"name": f"{stem}_skinned", "primitives": skinned_prims})
        gl.doc["scenes"][0]["nodes"].append(gl.add("nodes", {"name": f"{stem}_skinned", "mesh": mesh,
                                                             "skin": skin}))
    if static_prims:
        mesh = gl.add("meshes", {"name": f"{stem}_static", "primitives": static_prims})
        gl.doc["scenes"][0]["nodes"].append(gl.add("nodes", {"name": f"{stem}_static", "mesh": mesh,
                                                             "matrix": list(tms.root_matrix)}))

    side["model"] = {
        "bbox_min": list(tms.bbox_min), "bbox_max": list(tms.bbox_max), "root_bone": tms.root_bone,
        "opaque_material_count": tms.unknown_count_2,
        "bones": [{"bone": i, "parent": p, "first_child": c, "next_sibling": s, "gltf_node": bone_nodes.get(i)}
                  for i, (p, c, s, _) in enumerate(tms.bones)],
        "root_matrix": list(tms.root_matrix),
        "materials": [material_state(tms, m) for m in tms.materials],
        "textures": [dict(texture_state(t), gltf_texture=texture_ids.get(k)) for k, t in enumerate(tms.textures)],
    }

    # camera (and light placeholders) of the -etc file
    etc_nodes = {}
    scene = None
    if etc is not None:
        scene, camera = scene_block(etc[1])
        if camera and camera["yfov"]:
            cam = gl.add("cameras", {"type": "perspective", "name": "camera", "perspective": {
                "yfov": camera["yfov"], "znear": camera["znear"], "zfar": camera["zfar"],
                "aspectRatio": camera["aspectRatio"]}})
            t, r, _ = pose_trs(etc[1], 0, 0)
            etc_nodes[0] = gl.add("nodes", {"name": "camera", "camera": cam, "translation": t, "rotation": r})
            gl.doc["scenes"][0]["nodes"].append(etc_nodes[0])
        for light in scene["lights"]:
            if light["node"] < etc[1].node_count:
                t, r, _ = pose_trs(etc[1], light["node"], 0)
                etc_nodes[light["node"]] = gl.add("nodes", {"name": f"light{light['light']}", "translation": t,
                                                            "rotation": r, "extras": {"tgm_light": light["light"]}})
                gl.doc["scenes"][0]["nodes"].append(etc_nodes[light["node"]])
                light["gltf_node"] = etc_nodes[light["node"]]

    # animations
    gl_rest = {bone_nodes[i]: v for i, v in rest.items()}
    for k, (name, tmt) in enumerate(animations):
        samplers, channels = animation_channels(gl, tmt, bone_nodes, fps, gl_rest)
        entry = {"name": Path(name).stem, "samplers": samplers, "channels": channels}
        if k == 0 and etc is not None and etc_nodes:
            more_s, more_c = animation_channels(gl, etc[1], etc_nodes, fps, {})
            offset = len(samplers)
            samplers += more_s
            channels += [{"sampler": c["sampler"] + offset, "target": c["target"]} for c in more_c]
        index = gl.add("animations", entry) if channels else None  # glTF needs at least one channel
        stats["animation channels"] += len(channels)
        side["animations"].append({"name": Path(name).stem, "member": name, "gltf_animation": index,
                                   "flags": tmt.flags,
                                   "frame_count": tmt.frame_count, "loop_length": tmt.frame_count - 1,
                                   "nodes": [node_tracks_json(tmt, i) for i in range(tmt.node_count)]})
    if etc is not None:
        if not animations and etc_nodes:
            samplers, channels = animation_channels(gl, etc[1], etc_nodes, fps, {})
            if channels:
                gl.add("animations", {"name": Path(etc[0]).stem, "samplers": samplers, "channels": channels})
        side["scene"] = dict(scene, member=etc[0], frame_count=etc[1].frame_count,
                             nodes=[node_tracks_json(etc[1], i) for i in range(etc[1].node_count)])
    if tma is not None:
        side["texture_animation"] = dict(tma_json(tma[1]), member=tma[0])
    side["unknown"] += unknown_fields(tms, [t for _, t in animations] + ([etc[1]] if etc else []),
                                      tma[1] if tma else None)
    doc, binary = gl.finish(f"{stem}.bin")
    return doc, binary, images, side, stats


# --- Unknown-field census -------------------------------------------------------------------------

UNKNOWN_KINDS = {
    "texture.mode_bytes_8_9": "texture +0x08/+0x09 (01 01 on every file); not read by the texture setup 0x0882e720",
    "texture.wrap_bytes_2_3": "texture +0x12/+0x13 (zero on this disc)",
    "texture.zero_04": "texture +0x04: zero in the file, the game stores a texture handle there at bind time",
    "layer.map_type": "layer +0x08: 1 installs the GE texture-mapping callback 0x0882ef50, 2 installs 0x0882f050",
    "layer.blend_pad": "layer +0x17 (fourth blend byte, zero on this disc)",
    "layer.flags_high": "layer flag bits above bit 5 (none set on this disc)",
    "material.flags_high": "material flag bits above bit 3 (none set on this disc)",
    "tmt.node_pad": "TGMT node record +0x06 (zero on this disc)",
    "etc.unassigned_track": "-etc leading scalar track without an established role",
}


COMMON_VALUES = {"texture.mode_bytes_8_9": "0101"}


def is_set(item):
    """Census: does an unknown-field instance differ from zero (or from the value every file has)?"""
    raw = item["raw"]
    if isinstance(raw, list):  # raw keys of a scalar track
        return any(value for key in raw for value in key[1:])
    return raw not in (0, "", "0000", "00", COMMON_VALUES.get(item["kind"]))


def unknown_fields(tms, tmts, tma):
    out = []

    def note(kind, where, raw):
        out.append({"kind": kind, "where": where, "raw": raw})

    for i, t in enumerate(tms.textures if tms else ()):
        note("texture.mode_bytes_8_9", f"texture {i}", t["mode"][:2].hex())
        note("texture.wrap_bytes_2_3", f"texture {i}", t["wrap"][2:].hex())
        note("texture.zero_04", f"texture {i}", t["zero"])
    for i, m in enumerate(tms.materials if tms else ()):
        note("material.flags_high", f"material {i}", m["flags"] >> 4)
        for k, layer in enumerate(m["layers"]):
            note("layer.map_type", f"material {i} layer {k}", layer["map_type"])
            note("layer.blend_pad", f"material {i} layer {k}", layer["blend"][3])
            note("layer.flags_high", f"material {i} layer {k}", layer["flags"] >> 6)
    for tmt in tmts:
        for n, node in enumerate(tmt.nodes):
            note("tmt.node_pad", f"node {n}", node[3])
        if tmt.flags & tgm.TMT_FLAG_CAMERA:
            scene, _ = scene_block(tmt)
            for entry in scene["tracks"]:
                if entry["role"] is None:
                    note("etc.unassigned_track", f"track {entry['track']}", entry["keys"])
    return out


# --- Structural validation of the produced glTF -----------------------------------------------------

def validate(doc, binary):
    """Check the produced document against the glTF rules this exporter relies on. Returns problems."""
    p = []
    views, accessors = doc.get("bufferViews", []), doc.get("accessors", [])
    if doc["buffers"][0]["byteLength"] != len(binary):
        p.append("buffer length")
    sizes = {FLOAT: 4, UINT: 4, USHORT: 2, UBYTE: 1}
    widths = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
    data = []
    for i, a in enumerate(accessors):
        v = views[a["bufferView"]]
        need = a["count"] * widths[a["type"]] * sizes[a["componentType"]]
        if v["byteOffset"] + v["byteLength"] > len(binary) or need > v["byteLength"] or v["byteOffset"] % 4:
            p.append(f"accessor {i}: outside its view")
            data.append(None)
            continue
        code = {FLOAT: "f", UINT: "I", USHORT: "H", UBYTE: "B"}[a["componentType"]]
        flat = struct.unpack_from(f"<{a['count'] * widths[a['type']]}{code}", binary, v["byteOffset"])
        w = widths[a["type"]]
        data.append(flat if w == 1 else [flat[k:k + w] for k in range(0, len(flat), w)])
        if any(isinstance(x, float) and not math.isfinite(x) for x in flat):
            p.append(f"accessor {i}: non-finite value")
    parents = Counter(c for n in doc["nodes"] for c in n.get("children", []))
    if any(n > 1 for n in parents.values()):
        p.append("node with two parents")
    for skin in doc.get("skins", []):
        for m in data[skin["inverseBindMatrices"]]:
            if abs(m[3]) + abs(m[7]) + abs(m[11]) > 1e-6 or abs(m[15] - 1) > 1e-6:
                p.append("inverse bind matrix is not affine")
                break
    for mi, mesh in enumerate(doc.get("meshes", [])):
        for prim in mesh["primitives"]:
            count = accessors[prim["attributes"]["POSITION"]]["count"]
            if any(ix >= count for ix in data[prim["indices"]]):
                p.append(f"mesh {mi}: index out of range")
            if "JOINTS_0" in prim["attributes"]:
                skins = [doc["skins"][n["skin"]] for n in doc["nodes"] if n.get("mesh") == mi and "skin" in n]
                joint_count = len(skins[0]["joints"]) if skins else 0
                sums = [0.0] * count
                for k in range(2):
                    if f"WEIGHTS_{k}" not in prim["attributes"]:
                        continue
                    for vi, (js, ws) in enumerate(zip(data[prim["attributes"][f"JOINTS_{k}"]],
                                                      data[prim["attributes"][f"WEIGHTS_{k}"]])):
                        sums[vi] += sum(ws)
                        if any(j >= joint_count for j, w in zip(js, ws) if w):
                            p.append(f"mesh {mi}: joint index out of range")
                            break
                if any(abs(s - 1.0) > 2e-6 * 8 for s in sums):
                    p.append(f"mesh {mi}: weights do not sum to 1")
            if "NORMAL" in prim["attributes"]:
                if any(abs(math.sqrt(sum(c * c for c in n)) - 1) > 1e-4 for n in data[prim["attributes"]["NORMAL"]]):
                    p.append(f"mesh {mi}: normal not unit length")
    for ai, anim in enumerate(doc.get("animations", [])):
        for s in anim["samplers"]:
            times = data[s["input"]]
            if any(a >= b for a, b in zip(times, times[1:])):
                p.append(f"animation {ai}: input not increasing")
            factor = 3 if s["interpolation"] == "CUBICSPLINE" else 1
            if accessors[s["output"]]["count"] != factor * len(times):
                p.append(f"animation {ai}: output count")
        targets = Counter((c["target"]["node"], c["target"]["path"]) for c in anim["channels"])
        if any(n > 1 for n in targets.values()):
            p.append(f"animation {ai}: two channels for one node path")
    return p


def to_files(doc, binary, images, side, out_dir, stem):
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{stem}.gltf").write_text(json.dumps(doc, indent=1), encoding="utf-8")
    (out_dir / f"{stem}.bin").write_bytes(binary)
    for name, data in images.items():
        (out_dir / name).write_bytes(data)
    (out_dir / f"{stem}.tgm.json").write_text(json.dumps(side, indent=1, ensure_ascii=False), encoding="utf-8")


# --- glTF animation evaluation (used to prove the conversion against the game's sampler) -------------

def accessor_data(doc, binary, index):
    a = doc["accessors"][index]
    v = doc["bufferViews"][a["bufferView"]]
    width = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}[a["type"]]
    code = {FLOAT: "f", UINT: "I", USHORT: "H", UBYTE: "B"}[a["componentType"]]
    flat = struct.unpack_from(f"<{a['count'] * width}{code}", binary, v["byteOffset"])
    return list(flat) if width == 1 else [list(flat[k:k + width]) for k in range(0, len(flat), width)]


def sample_channel(doc, binary, sampler, time):
    """Evaluate a glTF animation sampler at `time` (seconds) following the glTF 2.0 rules."""
    times = accessor_data(doc, binary, sampler["input"])
    out = accessor_data(doc, binary, sampler["output"])
    mode = sampler["interpolation"]
    cubic = mode == "CUBICSPLINE"
    value = (lambda k: out[3 * k + 1]) if cubic else (lambda k: out[k])
    if time <= times[0]:
        return value(0)
    if time >= times[-1]:
        return value(len(times) - 1)
    k = max(j for j in range(len(times)) if times[j] <= time)
    t0, t1 = times[k], times[k + 1]
    u = (time - t0) / (t1 - t0)
    if mode == "STEP":
        return value(k)
    if cubic:
        dt = t1 - t0
        p0, m0, p1, m1 = out[3 * k + 1], out[3 * k + 2], out[3 * (k + 1) + 1], out[3 * (k + 1)]
        h = (2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u, -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2)
        return [h[0] * a + h[1] * dt * b + h[2] * c + h[3] * dt * d for a, b, c, d in zip(p0, m0, p1, m1)]
    if len(out[0]) == 4:  # rotation: slerp
        return list(tgm.slerp(out[k], out[k + 1], u))
    return [a + (b - a) * u for a, b in zip(out[k], out[k + 1])]


def compare_animation(doc, binary, anim_index, tmt, node_ids, fps, frames):
    """Largest difference between the glTF animation and the game's sampler over `frames`, per path."""
    anim = doc["animations"][anim_index]
    by_target = {(c["target"]["node"], c["target"]["path"]): anim["samplers"][c["sampler"]] for c in anim["channels"]}
    worst = Counter()
    for i in range(tmt.node_count):
        node = node_ids.get(i)
        if node is None:
            continue
        for frame in frames:
            want = dict(zip(("translation", "rotation", "scale"), pose_trs(tmt, i, frame)))
            for path, value in want.items():
                sampler = by_target.get((node, path))
                if sampler is None:
                    got = doc["nodes"][node].get(path, [0.0, 0.0, 0.0, 1.0] if path == "rotation" else
                                                 [0.0] * 3 if path == "translation" else [1.0] * 3)
                else:
                    got = sample_channel(doc, binary, sampler, frame / fps)
                if path == "rotation":
                    norm = math.sqrt(sum(a * a for a in got) * sum(b * b for b in value)) or 1.0
                    dot = abs(sum(a * b for a, b in zip(got, value))) / norm  # game keys are not quite unit
                    error = math.sqrt(max(0.0, 2 * (1 - min(dot, 1.0))))
                else:
                    error = max(abs(a - b) / (1.0 + abs(b)) for a, b in zip(got, value))
                worst[path] = max(worst[path], error)
    return worst


# --- Pairing models with their animations -------------------------------------------------------------

def bundles(members, offsets):
    """<anim>-ptrs.txt lists of four entries (mesh, node animation, texture animation, -etc): {tms: names}."""
    by_offset = {offset: name for name, offset in offsets.items()}
    out = {}
    for name, blob in members:
        if not name.lower().endswith("-ptrs.txt") or len(blob) != 20:
            continue
        values = struct.unpack("<5I", blob)
        if values[4] != 0xFFFFFFFF:
            continue
        names = [tgm.tgm_name(by_offset[v]) if v in by_offset else None for v in values[:4]]
        if names[0] and names[0].lower().endswith(".tms"):
            out[names[0]] = names
    return out


def companions(name, parsed, bundle=None, all_tmt=False):
    """(animations, etc, tma) for TGMS `name` among the parsed TGM members of one archive level:
    same-stem .tmt / -etc.tmt / .tma, or the pointer-list bundle naming the mesh; with all_tmt also every other
    non-camera TGMT whose node count equals the bone count (the cut-in archives hold one mesh and ~100 animations)."""
    tms = parsed[name]
    stem = name[:-4]
    want = {"tmt": stem + ".tmt", "etc": stem + "-etc.tmt", "tma": stem + ".tma"}
    if bundle:
        for key, member in zip(("tmt", "tma", "etc"), bundle[1:]):
            if member:
                want[key] = member

    def fits(obj):
        return isinstance(obj, tgm.Tmt) and not obj.flags & tgm.TMT_FLAG_CAMERA and obj.node_count == tms.bone_count \
            and tms.bone_count > 0

    animations = []
    if fits(parsed.get(want["tmt"])):
        animations.append((want["tmt"], parsed[want["tmt"]]))
    if all_tmt:
        animations += [(n, o) for n, o in sorted(parsed.items()) if fits(o) and n != want["tmt"]]
    etc = parsed.get(want["etc"])
    etc = (want["etc"], etc) if isinstance(etc, tgm.Tmt) and etc.flags & tgm.TMT_FLAG_CAMERA else None
    tma = parsed.get(want["tma"])
    tma = (want["tma"], tma) if isinstance(tma, tgm.Tma) else None
    return animations, etc, tma


def archive_levels(path):
    """Yield (prefix, {raw name: bytes}, {tgm name: parsed object}, bundles) for each archive level of a file."""
    for prefix, members, offsets in tgm.archive_members(path.read_bytes()):
        parsed = {}
        for name, raw_name, blob in tgm.tgm_members(members):
            parsed[name] = tgm.parse(blob)
        if parsed:
            yield prefix, dict(members), parsed, bundles(members, offsets)


def standalone_animation(tmt, fps):
    """Convert a TGMT without a model (node i -> node i) to check that every track converts."""
    gl = Gltf()
    ids = {i: gl.add("nodes", {"name": f"node{i}"}) for i in range(tmt.node_count)}
    samplers, channels = animation_channels(gl, tmt, ids, fps, {})
    if channels:
        gl.add("animations", {"name": "a", "samplers": samplers, "channels": channels})
    doc, binary = gl.finish("a.bin")
    return doc, binary, ids


def run_check(paths, fps=DEFAULT_FPS, verbose=False, compare_frames=5):
    """Convert every TGMS (with all its animations) and every other TGMT/TGMA on the given paths in memory,
    validate the glTF, compare the converted curves with the game's sampler, and print the unknown-field census."""
    counts, problems, unknown, nonzero = Counter(), Counter(), Counter(), Counter()
    worst = Counter()
    failures = 0
    for path in tgm.iter_archives(paths):
        try:
            levels = list(archive_levels(path))
        except (OSError, ValueError, EOFError, struct.error) as error:
            print(f"error: {path}: {error}")
            failures += 1
            continue
        for prefix, members, parsed, bundle_map in levels:
            used = set()
            for name, obj in sorted(parsed.items()):
                if not isinstance(obj, tgm.Tms):
                    continue
                label = f"{path}:{prefix}{name}"
                try:
                    animations, etc, tma = companions(name, parsed, bundle_map.get(name), all_tmt=True)
                    doc, binary, images, side, stats = convert(obj, members, animations, etc, tma, fps,
                                                               stem=Path(name).stem, textures=False)
                    issues = validate(doc, binary)
                    json.dumps(doc), json.dumps(side)
                    counts["models"] += 1
                    counts["models with skin"] += bool(doc.get("skins"))
                    counts["animations converted with a model"] += len(animations)
                    counts["textures decoded"] += len(doc.get("images", []))
                    counts["textures without a same-archive gim"] += stats["texture without gim"]
                    counts["triangles"] += stats["triangles"]
                    used.update(n for n, _ in animations)
                    if etc:
                        used.add(etc[0])
                        counts["-etc scenes converted with a model"] += 1
                    if tma:
                        used.add(tma[0])
                        counts["tma converted with a model"] += 1
                    for entry, (aname, tmt) in list(zip(side["animations"], animations))[:3]:
                        if entry["gltf_animation"] is None:
                            continue
                        frames = sorted({0, tmt.frame_count - 1, *(tmt.frame_count * j / compare_frames + 0.37
                                                                     for j in range(compare_frames))})
                        node_ids = {i: i for i in range(obj.bone_count)}  # bones are the first glTF nodes
                        for path_name, error in compare_animation(doc, binary, entry["gltf_animation"], tmt,
                                                                  node_ids, fps, frames).items():
                            worst[path_name] = max(worst[path_name], error)
                    for item in side["unknown"]:
                        unknown[item["kind"]] += 1
                        nonzero[item["kind"]] += is_set(item)
                except (ValueError, KeyError, IndexError, ZeroDivisionError, struct.error) as error:
                    issues = [f"conversion error: {error!r}"]
                if issues:
                    failures += 1
                    for issue in issues:
                        problems[issue] += 1
                    if verbose:
                        print(f"FAIL {label}: {'; '.join(issues)}")
            for name, obj in sorted(parsed.items()):
                if name in used or isinstance(obj, tgm.Tms):
                    continue
                try:
                    if isinstance(obj, tgm.Tmt):
                        doc, binary, ids = standalone_animation(obj, fps)
                        issues = validate(doc, binary)
                        if obj.flags & tgm.TMT_FLAG_CAMERA:
                            scene_block(obj)
                            counts["-etc / .vtmt converted without a model"] += 1
                            for item in unknown_fields(None, [obj], None):
                                unknown[item["kind"]] += 1
                                nonzero[item["kind"]] += is_set(item)
                        else:
                            counts["animations converted without a model"] += 1
                        if doc.get("animations"):
                            frames = [0, obj.frame_count / 2 + 0.37, obj.frame_count - 1]
                            for path_name, error in compare_animation(doc, binary, 0, obj, ids, fps, frames).items():
                                worst[path_name] = max(worst[path_name], error)
                    else:
                        json.dumps(tma_json(obj))
                        counts["tma converted without a model"] += 1
                        issues = []
                except (ValueError, KeyError, IndexError, ZeroDivisionError, struct.error) as error:
                    issues = [f"conversion error: {error!r}"]
                if issues:
                    failures += 1
                    for issue in issues:
                        problems[issue] += 1
                    if verbose:
                        print(f"FAIL {path}:{prefix}{name}: {'; '.join(issues)}")
    for key, n in counts.items():
        print(f"{key}: {n}")
    print(f"failing: {failures}")
    for issue, n in problems.most_common():
        print(f"  {n:6}  {issue}")
    print("largest difference glTF vs game sampler (translation/scale relative, rotation chord): "
          + ", ".join(f"{k} {v:.2e}" for k, v in sorted(worst.items())))
    print("unknown fields (instances, of which not zero / not the common value):")
    for kind in UNKNOWN_KINDS:
        print(f"  {kind}: {unknown[kind]} ({nonzero[kind]})  {UNKNOWN_KINDS[kind]}")
    return 1 if failures else 0


def output_allowed(path):
    """Derived model data goes outside the repository or under an extracted/ directory."""
    resolved = Path(path).resolve()
    if "extracted" in (part.lower() for part in resolved.parts):
        return True
    try:
        resolved.relative_to(TOOLS.parent.resolve())
    except ValueError:
        return True
    return False


def export(archive, member, out_dir, extra_tmt=(), all_tmt=False, fps=DEFAULT_FPS, flip=False):
    """Export one TGMS of an archive (nested archives as outer.ehp:inner) with its animations."""
    for prefix, members, parsed, bundle_map in archive_levels(archive):
        for name, obj in parsed.items():
            if isinstance(obj, tgm.Tms) and prefix + name in (member, member.removesuffix(".gz")):
                animations, etc, tma = companions(name, parsed, bundle_map.get(name), all_tmt)
                for extra in extra_tmt:
                    extra = extra.removesuffix(".gz")
                    tmt = parsed.get(extra)
                    if not isinstance(tmt, tgm.Tmt):
                        raise KeyError(extra)
                    if tmt.flags & tgm.TMT_FLAG_CAMERA:
                        etc = (extra, tmt)
                    elif extra not in [n for n, _ in animations]:
                        animations.insert(0, (extra, tmt))
                stem = Path(name).stem
                source = {"archive": str(archive), "member": prefix + name, "animations": [n for n, _ in animations],
                          "etc": etc[0] if etc else None, "tma": tma[0] if tma else None}
                doc, binary, images, side, stats = convert(obj, members, animations, etc, tma, fps, flip, stem,
                                                           source=source)
                problems = validate(doc, binary)
                to_files(doc, binary, images, side, out_dir, stem)
                return stem, doc, stats, problems
    raise KeyError(member)
