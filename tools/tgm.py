#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read the TGM model family stored in EHP archives: TGMS (.tms, mesh), TGMT (.tmt / .tmt.gz, node
animation) and TGMA (.tma, texture animation). See docs/formats/tgm.md.

Examples (write exports outside the repository, for example under extracted/tgm/):
    python3 -I tools/tgm.py list USRDIR/database/cardalbum.ehp
    python3 -I tools/tgm.py inspect USRDIR/database/cardalbum.ehp album_cover00.tms
    python3 -I tools/tgm.py check USRDIR                      # every TGM member on the disc
    python3 -I tools/tgm.py obj USRDIR/shop/all_s.ehp pack_in_card00.tms -o extracted/tgm/pack
"""

import argparse
import gzip
import importlib.util
import math
import struct
import sys
from collections import Counter
from pathlib import Path

TOOLS = Path(__file__).resolve().parent


def _load(name):
    spec = importlib.util.spec_from_file_location("re_" + name, TOOLS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ehp = _load("ehp")

TGMS, TGMT, TGMA = b"TGMS", b"TGMT", b"TGMA"
EXTENSIONS = {".tms": TGMS, ".tmt": TGMT, ".vtmt": TGMT, ".tma": TGMA}  # .vtmt only as gzip, in duel/

# --- TGMS ----------------------------------------------------------------------------------------
TMS_HEADER = struct.Struct("<4sI8I7I6fI")  # magic, header size, 8 offsets, 7 counts, bbox, zero
TMS_HEADER_SIZE = 0x60
PRIM = struct.Struct("<III")  # GE primitive type, vertex count, byte offset into the vertex block
MATERIAL_SIZE = 0xA4
TEXTURE_SIZE = 0x28
BATCH = struct.Struct("<8hIHH")  # bone palette, GE vertex type, primitive count, first primitive
BONE = struct.Struct("<hhhH")  # parent, first child, next sibling, zero
MATRIX = struct.Struct("<16f")
PRIM_TYPES = {0: "points", 1: "lines", 2: "line_strip", 3: "triangles", 4: "triangle_strip",
              5: "triangle_fan", 6: "sprites"}

# --- TGMT ----------------------------------------------------------------------------------------
TMT_HEADER = struct.Struct("<4sI5I7I")  # magic, header size, 5 offsets, 7 counts
TMT_HEADER_SIZE = 0x38
TMT_NODE = struct.Struct("<HhhH")  # translation track base, rotation track, scale track base, zero
TRACK = struct.Struct("<II")  # key count, first key
SCALAR_KEY = struct.Struct("<Ifff")  # frame, value, Bezier handle 1, Bezier handle 2
TMT_FLAG_CAMERA = 2  # "-etc" files: leading camera/scene parameter tracks
TMT_FLAG_SHORT_QUAT = 4  # rotation keys are 4 x s16 / 32767 instead of 4 x f32

# --- TGMA ----------------------------------------------------------------------------------------
TMA_HEADER = struct.Struct("<4sI2I4II")  # magic, header size, 2 offsets, 4 counts, zero
TMA_HEADER_SIZE = 0x24
TMA_ENTRY = struct.Struct("<16hI")  # track base per channel slot, texture index in the TGMS
TMA_SLOTS = {0: ("uv_offset", 2), 1: ("uv_scale", 2), 2: ("scalar", 1)}


def align(value, boundary):
    return (value + boundary - 1) // boundary * boundary


def check_tracks(tracks, total):
    """Tracks are (key count, first key) and their keys follow each other in track order; a track
    without keys stores first key 0."""
    problems, first = [], 0
    for count, start in tracks:
        if count and start != first or not count and start not in (0, first):
            problems.append("tracks not contiguous")
            break
        first += count
    if first != total:
        problems.append(f"key count {total} vs tracks {first}")
    return problems


def cstring(data, offset):
    end = data.index(b"\0", offset)
    return data[offset:end].decode("cp932", "replace")


# --- GE vertex format ----------------------------------------------------------------------------

def vertex_layout(vtype):
    """Decode a GE vertex type word (as passed to sceGuDrawArray) into component offsets.

    Returns a dict: size, and for each present component (weights, uv, color, normal, position) a
    tuple (offset, format code, element count). Order and alignment follow the GE: weights, texture,
    colour, normal, position; every component is aligned to its element size and the vertex to the
    largest one."""
    tc, col, nrm, pos, wt = vtype & 3, vtype >> 2 & 7, vtype >> 5 & 3, vtype >> 7 & 3, vtype >> 9 & 3
    if vtype >> 11 & 3:
        raise ValueError(f"indexed vertex type {vtype:#x} not supported")
    if vtype >> 18 & 7 or vtype >> 23 & 1:
        raise ValueError(f"morph or through-mode vertex type {vtype:#x} not supported")
    weights = (vtype >> 14 & 7) + 1
    sizes = {0: 0, 1: 1, 2: 2, 3: 4}
    col_size = {0: 0, 4: 2, 5: 2, 6: 2, 7: 4}.get(col)
    if col_size is None:
        raise ValueError(f"invalid colour format in vertex type {vtype:#x}")
    layout, offset, largest = {}, 0, 1
    for name, code, element, count in (("weights", wt, sizes[wt], weights), ("uv", tc, sizes[tc], 2),
                                       ("color", col, col_size, 1), ("normal", nrm, sizes[nrm], 3),
                                       ("position", pos, sizes[pos], 3)):
        if not code:
            continue
        offset = align(offset, element)
        layout[name] = (offset, code, count)
        offset += element * count
        largest = max(largest, element)
    layout["size"] = align(offset, largest)
    return layout


def describe_vtype(vtype):
    names = {1: "8", 2: "16", 3: "f32"}
    lay = vertex_layout(vtype)
    parts = []
    if "weights" in lay:
        parts.append(f"w{names[lay['weights'][1]]}x{lay['weights'][2]}")
    if "uv" in lay:
        parts.append(f"uv{names[lay['uv'][1]]}")
    if "color" in lay:
        parts.append({4: "c5650", 5: "c5551", 6: "c4444", 7: "c8888"}[lay["color"][1]])
    if "normal" in lay:
        parts.append(f"n{names[lay['normal'][1]]}")
    if "position" in lay:
        parts.append(f"p{names[lay['position'][1]]}")
    return "+".join(parts) + f" ({lay['size']}B)"


def _read_elements(data, offset, code, count, signed=True):
    """Read GE elements normalised like the GE does outside through mode."""
    if code == 3:
        return list(struct.unpack_from(f"<{count}f", data, offset))
    if code == 2:
        return [v / 32768.0 for v in struct.unpack_from(f"<{count}{'h' if signed else 'H'}", data, offset)]
    return [v / 128.0 for v in struct.unpack_from(f"<{count}{'b' if signed else 'B'}", data, offset)]


def decode_vertex(data, offset, layout):
    out = {}
    if "weights" in layout:
        o, code, n = layout["weights"]
        out["weights"] = _read_elements(data, offset + o, code, n, signed=False)
    if "uv" in layout:
        o, code, n = layout["uv"]
        out["uv"] = _read_elements(data, offset + o, code, n, signed=False)
    if "color" in layout:
        o, code, _ = layout["color"]
        if code == 7:
            out["color"] = tuple(data[offset + o:offset + o + 4])
        else:
            out["color"] = struct.unpack_from("<H", data, offset + o)[0]
    if "normal" in layout:
        o, code, n = layout["normal"]
        out["normal"] = _read_elements(data, offset + o, code, n)
    if "position" in layout:
        o, code, n = layout["position"]
        out["position"] = _read_elements(data, offset + o, code, n)
    return out


def transform(matrix, point):
    """PSP matrices are four column vectors (x axis, y axis, z axis, translation), 4 floats each."""
    x, y, z = point
    return [matrix[i] * x + matrix[4 + i] * y + matrix[8 + i] * z + matrix[12 + i] for i in range(3)]


def mat_mul(a, b):
    """a x b for matrices stored as four column vectors (b is applied first)."""
    return [sum(a[4 * k + i] * b[4 * j + k] for k in range(4)) for j in range(4) for i in range(4)]


def trs_matrix(t, q, s):
    """Translation x rotation (unit quaternion x, y, z, w) x scale, as four column vectors."""
    x, y, z, w = q
    columns = ((1 - 2 * (y * y + z * z), 2 * (x * y + z * w), 2 * (x * z - y * w)),
               (2 * (x * y - z * w), 1 - 2 * (x * x + z * z), 2 * (y * z + x * w)),
               (2 * (x * z + y * w), 2 * (y * z - x * w), 1 - 2 * (x * x + y * y)))
    out = []
    for column, factor in zip(columns, s):
        out += [c * factor for c in column] + [0.0]
    return out + [t[0], t[1], t[2], 1.0]


def pose_matrices(tms, tmt, frame=0):
    """Node world matrices of a TGMS skeleton posed by a TGMT at `frame` (node i animates bone i;
    parents come from the TGMS bone table)."""
    if tmt.node_count != tms.bone_count:
        raise ValueError("TGMT node count differs from the TGMS bone count")
    world = [None] * tms.bone_count
    pending = list(range(tms.bone_count))
    while pending:
        left = []
        for i in pending:
            parent = tms.bones[i][0]
            if parent == -1:
                world[i] = tmt.local_matrix(i, frame)
            elif world[parent] is not None:
                world[i] = mat_mul(world[parent], tmt.local_matrix(i, frame))
            else:
                left.append(i)
        if len(left) == len(pending):
            raise ValueError("bone hierarchy has a cycle")
        pending = left
    return world


# --- TGMS parser ---------------------------------------------------------------------------------

class Tms:
    """A parsed TGMS mesh. All offsets in the file are relative to the start of the member."""

    def __init__(self, data):
        fields = TMS_HEADER.unpack_from(data, 0)
        self.magic, self.header_size = fields[0], fields[1]
        if self.magic != TGMS:
            raise ValueError("not a TGMS file")
        (self.prim_offset_end, self.materials_offset, self.textures_offset, self.batches_offset,
         self.bones_offset, self.bone_matrices_offset, self.root_matrix_offset, self.names_offset) = fields[2:10]
        self.vertices_offset = self.prim_offset_end  # the vertex block starts where the primitive table ends
        (self.material_count, self.animated_texture_count, self.unknown_count_2, self.texture_count,
         self.animated_texture_count_2, self.bone_count, self.root_bone) = fields[10:17]
        self.bbox_min, self.bbox_max = fields[17:20], fields[20:23]
        self.reserved = fields[23]
        self.data = data
        self.materials = [self._material(i) for i in range(self.material_count)]
        self.batch_count = sum(m["batch_count"] for m in self.materials)
        self.batches = [self._batch(i) for i in range(self.batch_count)]
        self.prim_count = sum(b["prim_count"] for b in self.batches)
        self.prims = [PRIM.unpack_from(data, self.header_size + PRIM.size * i) for i in range(self.prim_count)]
        self.textures = [self._texture(i) for i in range(self.texture_count)]
        self.bones = [BONE.unpack_from(data, self.bones_offset + BONE.size * i) for i in range(self.bone_count)]
        self.bone_matrices = [MATRIX.unpack_from(data, self.bone_matrices_offset + MATRIX.size * i)
                              for i in range(self.bone_count)]
        self.root_matrix = MATRIX.unpack_from(data, self.root_matrix_offset)

    def _material(self, index):
        base = self.materials_offset + MATERIAL_SIZE * index
        raw = self.data[base:base + MATERIAL_SIZE]
        layers = []
        for k in range(4):
            o = 0x1C + 0x20 * k
            texture, unknown, color = struct.unpack_from("<iI4s", raw, o)
            layers.append({"texture": texture, "unknown_04": unknown, "color": color,
                           "state": raw[o + 0x0C:o + 0x10], "blend": raw[o + 0x10:o + 0x14],
                           "blend_fix": (raw[o + 0x14:o + 0x18], raw[o + 0x18:o + 0x1C])})
        count, first = struct.unpack_from("<HH", raw, 0x9C)
        return {"unknown_00": struct.unpack_from("<I", raw, 0)[0], "emissive": raw[4:8], "diffuse": raw[8:12],
                "ambient": raw[12:16], "specular": raw[16:20], "shininess": struct.unpack_from("<f", raw, 0x14)[0],
                "flags": struct.unpack_from("<I", raw, 0x18)[0], "layers": layers,
                "unknown_98": struct.unpack_from("<I", raw, 0x98)[0], "batch_count": count, "first_batch": first,
                "unknown_a0": struct.unpack_from("<I", raw, 0xA0)[0], "raw": raw}

    def _texture(self, index):
        base = self.textures_offset + TEXTURE_SIZE * index
        name_offset, zero, mode, minus_one, unknown, u_off, v_off, u_scale, v_scale, anim = struct.unpack_from(
            "<II4siIffffi", self.data, base)
        return {"name_offset": name_offset, "name": cstring(self.data, self.names_offset + name_offset),
                "zero": zero, "mode": mode, "minus_one": minus_one, "unknown_10": unknown,
                "uv_offset": (u_off, v_off), "uv_scale": (u_scale, v_scale), "animation": anim}

    def _batch(self, index):
        fields = BATCH.unpack_from(self.data, self.batches_offset + BATCH.size * index)
        return {"palette": fields[:8], "vtype": fields[8], "prim_count": fields[9], "first_prim": fields[10]}

    def vertices_of(self, prim, vtype):
        """Decode the vertices of one primitive entry."""
        _, count, offset = prim
        layout = vertex_layout(vtype)
        base = self.vertices_offset + offset
        return [decode_vertex(self.data, base + layout["size"] * i, layout) for i in range(count)]

    def world_position(self, vertex, batch, node_world=None):
        """Model-space position of a vertex. Without bones: root matrix x position. With bones: blend over
        the batch palette of node_world[bone] x bone_matrices[bone] x position, by vertex weight.
        node_world are the animated node matrices (see pose_matrices); without them the bone matrices
        are applied alone, which is not a meaningful pose (they are offset matrices)."""
        p = vertex["position"]
        palette = [b for b in batch["palette"] if b >= 0]
        if not palette:
            return transform(self.root_matrix, p)
        weights = vertex.get("weights", [1.0])
        acc = [0.0, 0.0, 0.0]
        for w, bone in zip(weights, palette):
            m = self.bone_matrices[bone]
            if node_world is not None:
                m = mat_mul(node_world[bone], m)
            q = transform(m, p)
            acc = [a + w * c for a, c in zip(acc, q)]
        return acc

    def check(self):
        """Structural checks; returns a list of problems (empty if the file follows every rule)."""
        p, d = [], self.data
        if self.header_size != TMS_HEADER_SIZE:
            p.append(f"header size {self.header_size:#x}")
        if self.reserved:
            p.append("reserved header word is not zero")
        if self.vertices_offset != self.header_size + PRIM.size * self.prim_count:
            p.append("primitive table does not end at the vertex block")
        if self.textures_offset != self.materials_offset + MATERIAL_SIZE * self.material_count:
            p.append("material table size")
        if self.batches_offset != self.textures_offset + TEXTURE_SIZE * self.texture_count:
            p.append("texture table size")
        batches_end = self.batches_offset + BATCH.size * self.batch_count
        if self.bone_count:
            if self.bones_offset != batches_end:
                p.append("bone table does not follow the batches")
            if self.bone_matrices_offset != align(self.bones_offset + BONE.size * self.bone_count, 16):
                p.append("bone matrices offset")
            if self.root_matrix_offset != self.bone_matrices_offset + MATRIX.size * self.bone_count:
                p.append("root matrix does not follow the bone matrices")
            roots = [i for i, b in enumerate(self.bones) if b[0] == -1]
            if not roots or self.root_bone != roots[0]:
                p.append("root bone field is not the first bone without parent")
            for i, (parent, child, sibling, zero) in enumerate(self.bones):
                if zero or not -1 <= parent < self.bone_count:
                    p.append(f"bone {i}: bad record")
                if child != -1 and (child >= self.bone_count or self.bones[child][0] != i):
                    p.append(f"bone {i}: first child does not point back")
                if sibling != -1 and (sibling >= self.bone_count or self.bones[sibling][0] != parent):
                    p.append(f"bone {i}: sibling has another parent")
        else:
            if self.bones_offset or self.bone_matrices_offset:
                p.append("bone offsets set without bones")
            if self.root_bone != 0xFFFF:
                p.append("root bone field is not 0xffff without bones")
            if self.root_matrix_offset != align(batches_end, 16):
                p.append("root matrix does not follow the batches")
        if self.names_offset != self.root_matrix_offset + MATRIX.size:
            p.append("name table does not follow the root matrix")
        if self.animated_texture_count != self.animated_texture_count_2:
            p.append("the two animated-texture counts differ")
        anims = sorted(t["animation"] for t in self.textures if t["animation"] >= 0)
        if anims != list(range(self.animated_texture_count)):
            p.append("texture animation indices are not 0..n-1")
        if self.texture_count and not d.endswith(b"\0"):
            p.append("name table is not NUL-terminated")
        first = 0
        for i, m in enumerate(self.materials):
            if m["first_batch"] != first:
                p.append(f"material {i}: batches not contiguous")
            first += m["batch_count"]
            for k, layer in enumerate(m["layers"]):
                if not -1 <= layer["texture"] < self.texture_count:
                    p.append(f"material {i} layer {k}: texture index out of range")
        owner = [None] * self.prim_count  # batch layout per primitive entry
        for i, b in enumerate(self.batches):
            used = [x for x in b["palette"] if x >= 0]
            if any(x >= self.bone_count for x in used) or b["palette"][:len(used)] != tuple(used):
                p.append(f"batch {i}: bad bone palette")
            try:
                layout = vertex_layout(b["vtype"])
            except ValueError as error:
                p.append(f"batch {i}: {error}")
                continue
            if used and "weights" in layout and layout["weights"][2] > len(used):
                p.append(f"batch {i}: more weights than palette entries")
            for k in range(b["first_prim"], b["first_prim"] + b["prim_count"]):
                if owner[k] is not None:
                    p.append(f"primitive {k} used by two batches")
                owner[k] = layout
        if None in owner:
            p.append("primitive entry not used by any batch")
            return p
        ranges = []
        for k, (kind, count, offset) in enumerate(self.prims):
            if kind not in (3, 4):
                p.append(f"primitive {k}: type {kind}")
            ranges.append((offset, offset + count * owner[k]["size"]))
        vertex_end = 0
        for start, end in sorted(ranges):  # vertex runs tile the block without gaps or overlaps
            if start != vertex_end:
                p.append("vertex runs do not tile the vertex block")
                break
            vertex_end = end
        block = self.materials_offset - self.vertices_offset
        if not 0 <= block - vertex_end < 4:
            p.append(f"vertex block size {block:#x} vs used {vertex_end:#x}")
        return p

    def bbox_error(self, node_world=None):
        """Largest distance of a vertex outside the header bounding box (0 if all inside)."""
        worst = 0.0
        for b in self.batches:
            for prim in self.prims[b["first_prim"]:b["first_prim"] + b["prim_count"]]:
                for v in self.vertices_of(prim, b["vtype"]):
                    w = self.world_position(v, b, node_world)
                    for axis in range(3):
                        worst = max(worst, self.bbox_min[axis] - w[axis], w[axis] - self.bbox_max[axis])
        return worst


# --- TGMT parser ---------------------------------------------------------------------------------

class Tmt:
    """A parsed TGMT node animation."""

    def __init__(self, data):
        fields = TMT_HEADER.unpack_from(data, 0)
        self.magic, self.header_size = fields[0], fields[1]
        if self.magic != TGMT:
            raise ValueError("not a TGMT file")
        (self.tracks_offset, self.keys_offset, self.rot_tracks_offset, self.rot_times_offset,
         self.rot_keys_offset) = fields[2:7]
        (self.node_count, self.track_count, self.key_count, self.rot_track_count, self.rot_key_count,
         self.frame_count, self.flags) = fields[7:14]
        self.data = data
        self.nodes = [TMT_NODE.unpack_from(data, self.header_size + TMT_NODE.size * i) for i in range(self.node_count)]
        self.tracks = [TRACK.unpack_from(data, self.tracks_offset + TRACK.size * i) for i in range(self.track_count)]
        self.rot_tracks = [TRACK.unpack_from(data, self.rot_tracks_offset + TRACK.size * i)
                           for i in range(self.rot_track_count)]

    @property
    def rot_key_size(self):
        return 8 if self.flags & TMT_FLAG_SHORT_QUAT else 16

    def sample_scalar(self, track, frame, default):
        """Value of a scalar track at `frame`: each segment is a cubic Bezier in value with control points
        (value_k, handle1_k, handle2_k, value_k+1), its parameter linear in frame time (hypothesis)."""
        keys = self.scalar_keys(track)
        if not keys:
            return default
        if frame <= keys[0][0]:
            return keys[0][1]
        for (t0, v0, h1, h2), (t1, v1, _, _) in zip(keys, keys[1:]):
            if frame < t1:
                u = (frame - t0) / (t1 - t0)
                return ((1 - u) ** 3 * v0 + 3 * (1 - u) ** 2 * u * h1 + 3 * (1 - u) * u * u * h2 + u ** 3 * v1)
        return keys[-1][1]

    def sample_rotation(self, track, frame):
        """Quaternion (x, y, z, w) of a rotation track at `frame`, normalised linear blend of the two keys
        around it (the game's exact interpolation is not established)."""
        keys = self.rotation_keys(track)
        if not keys:
            return (0.0, 0.0, 0.0, 1.0)
        if frame <= keys[0][0]:
            return keys[0][1]
        for (t0, q0), (t1, q1) in zip(keys, keys[1:]):
            if frame < t1:
                u = (frame - t0) / (t1 - t0)
                sign = 1 if sum(a * b for a, b in zip(q0, q1)) >= 0 else -1
                q = [a * (1 - u) + sign * b * u for a, b in zip(q0, q1)]
                n = math.sqrt(sum(c * c for c in q)) or 1.0
                return tuple(c / n for c in q)
        return keys[-1][1]

    def local_matrix(self, node, frame):
        tbase, rot, sbase, _ = self.nodes[node]
        t = [0.0] * 3 if tbase == 0xFFFF else [self.sample_scalar(tbase + k, frame, 0.0) for k in range(3)]
        s = [1.0] * 3 if sbase == -1 else [self.sample_scalar(sbase + k, frame, 1.0) for k in range(3)]
        q = (0.0, 0.0, 0.0, 1.0) if rot == -1 else self.sample_rotation(rot, frame)
        return trs_matrix(t, q, s)

    def scalar_keys(self, track):
        count, first = self.tracks[track]
        return [SCALAR_KEY.unpack_from(self.data, self.keys_offset + SCALAR_KEY.size * k)
                for k in range(first, first + count)]

    def rotation_keys(self, track):
        count, first = self.rot_tracks[track]
        out = []
        for k in range(first, first + count):
            frame = struct.unpack_from("<I", self.data, self.rot_times_offset + 4 * k)[0]
            if self.rot_key_size == 8:
                quat = tuple(v / 32767.0 for v in struct.unpack_from("<4h", self.data, self.rot_keys_offset + 8 * k))
            else:
                quat = struct.unpack_from("<4f", self.data, self.rot_keys_offset + 16 * k)
            out.append((frame, quat))
        return out

    def check(self):
        p, d = [], self.data
        if self.header_size != TMT_HEADER_SIZE:
            p.append(f"header size {self.header_size:#x}")
        expect = [self.header_size + TMT_NODE.size * self.node_count]
        expect.append(expect[-1] + TRACK.size * self.track_count)
        expect.append(expect[-1] + SCALAR_KEY.size * self.key_count)
        expect.append(expect[-1] + TRACK.size * self.rot_track_count)
        expect.append(align(expect[-1] + 4 * self.rot_key_count, 16))
        got = [self.tracks_offset, self.keys_offset, self.rot_tracks_offset, self.rot_times_offset,
               self.rot_keys_offset]
        for name, a, b in zip(("tracks", "keys", "rotation tracks", "rotation times", "rotation keys"), got, expect):
            if a != b:
                p.append(f"{name} offset {a:#x}, expected {b:#x}")
        if len(d) != self.rot_keys_offset + self.rot_key_size * self.rot_key_count:
            p.append("file size does not match the rotation keys")
        if self.flags not in (0, TMT_FLAG_CAMERA, TMT_FLAG_SHORT_QUAT):
            p.append(f"flags {self.flags:#x}")
        rotation_used = []
        for i, (tbase, rot, sbase, zero) in enumerate(self.nodes):
            if zero:
                p.append(f"node {i}: last field not zero")
            for base in (tbase if tbase != 0xFFFF else -1, sbase):
                if base != -1 and base + 3 > self.track_count:
                    p.append(f"node {i}: track base out of range")
            if rot != -1:
                rotation_used.append(rot)
        if rotation_used != list(range(len(rotation_used))) or len(rotation_used) != self.rot_track_count:
            p.append("rotation tracks are not used once each, in node order")
        for name, tracks, total in (("scalar", self.tracks, self.key_count),
                                    ("rotation", self.rot_tracks, self.rot_key_count)):
            p += [f"{name} {issue}" for issue in check_tracks(tracks, total)]
        for i in range(self.track_count):
            frames = [k[0] for k in self.scalar_keys(i)]
            if any(a >= b for a, b in zip(frames, frames[1:])) or (frames and frames[-1] >= self.frame_count):
                p.append(f"scalar track {i}: frames not increasing within the frame count")
                break
        for i in range(self.rot_track_count):
            keys = self.rotation_keys(i)
            frames = [k[0] for k in keys]
            if any(a >= b for a, b in zip(frames, frames[1:])) or (frames and frames[-1] >= self.frame_count):
                p.append(f"rotation track {i}: frames not increasing within the frame count")
                break
            if any(abs(math.sqrt(sum(c * c for c in q)) - 1) > 0.01 for _, q in keys):
                p.append(f"rotation track {i}: key is not a unit quaternion")
                break
        return p


# --- TGMA parser ---------------------------------------------------------------------------------

class Tma:
    """A parsed TGMA texture animation (one entry per animated texture of the matching TGMS)."""

    def __init__(self, data):
        (self.magic, self.header_size, self.tracks_offset, self.keys_offset, self.entry_count, self.track_count,
         self.key_count, self.frame_count, self.reserved) = TMA_HEADER.unpack_from(data, 0)
        if self.magic != TGMA:
            raise ValueError("not a TGMA file")
        self.data = data
        self.entries = [TMA_ENTRY.unpack_from(data, self.header_size + TMA_ENTRY.size * i)
                        for i in range(self.entry_count)]
        self.tracks = [TRACK.unpack_from(data, self.tracks_offset + TRACK.size * i) for i in range(self.track_count)]

    def scalar_keys(self, track):
        count, first = self.tracks[track]
        return [SCALAR_KEY.unpack_from(self.data, self.keys_offset + SCALAR_KEY.size * k)
                for k in range(first, first + count)]

    def check(self):
        p = []
        if self.header_size != TMA_HEADER_SIZE or self.reserved:
            p.append("header")
        if self.tracks_offset != self.header_size + TMA_ENTRY.size * self.entry_count:
            p.append("track table offset")
        if self.keys_offset != self.tracks_offset + TRACK.size * self.track_count:
            p.append("key table offset")
        if len(self.data) != self.keys_offset + SCALAR_KEY.size * self.key_count:
            p.append("file size")
        p += check_tracks(self.tracks, self.key_count)
        bases = []
        for i, entry in enumerate(self.entries):
            slots = entry[:16]
            if any(s != -1 for s in slots[len(TMA_SLOTS):]):
                p.append(f"entry {i}: unknown channel slot used")
            for slot, (_, width) in TMA_SLOTS.items():
                if slots[slot] != -1:
                    if not 0 <= slots[slot] <= self.track_count - width:
                        p.append(f"entry {i}: track base out of range")
                    bases.append(slots[slot])
        if bases != sorted(bases) or len(set(bases)) != len(bases):
            p.append("channel track bases are not increasing")
        for i in range(self.track_count):
            frames = [k[0] for k in self.scalar_keys(i)]
            if any(a >= b for a, b in zip(frames, frames[1:])) or (frames and frames[-1] >= self.frame_count):
                p.append(f"track {i}: frames not increasing within the frame count")
                break
        return p


def parse(data):
    kind = data[:4]
    if kind == TGMS:
        return Tms(data)
    if kind == TGMT:
        return Tmt(data)
    if kind == TGMA:
        return Tma(data)
    raise ValueError(f"not a TGM file: {kind!r}")


# --- Archive walking -----------------------------------------------------------------------------

def tgm_name(name):
    """Return the member name without '.gz' if it is a TGM member, else None."""
    low = name.lower()
    if low.endswith(".gz"):
        low = low[:-3]
    return name[:len(low)] if Path(low).suffix in EXTENSIONS else None


def archive_members(data):
    """Yield (prefix, members, offsets) for an EHP archive and every archive nested inside it.
    offsets maps a member name to its data offset in that archive."""
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    members = ehp.parse(data)
    offsets = {}
    for i, (name, _) in enumerate(members):
        offsets[name] = struct.unpack_from("<I", data, ehp.TABLE + ehp.ENTRY.size * i + 4)[0]
    yield "", members, offsets
    for name, blob in members:
        if blob[:4] == ehp.MAGIC:
            for prefix, inner, inner_offsets in archive_members(blob):
                yield name + ":" + prefix, inner, inner_offsets


def tgm_members(members):
    """Yield (name, raw member name, TGM bytes) for every TGM member; gzip members are inflated."""
    for name, blob in members:
        base = tgm_name(name)
        if base is None:
            continue
        if blob[:2] == b"\x1f\x8b":
            blob = gzip.decompress(blob)
        yield base, name, blob


def iter_archives(paths):
    for path in paths:
        if path.is_dir():
            for sub in sorted(path.rglob("*")):
                if sub.is_file():
                    head = sub.open("rb").read(4)
                    if head[:4] == ehp.MAGIC or head[:2] == b"\x1f\x8b":
                        yield sub
        else:
            yield path


def summary(obj):
    if isinstance(obj, Tms):
        vtypes = sorted({b["vtype"] for b in obj.batches})
        return (f"TGMS materials={obj.material_count} textures={obj.texture_count} batches={obj.batch_count} "
                f"prims={obj.prim_count} bones={obj.bone_count} vtypes={','.join(hex(v) for v in vtypes)}")
    if isinstance(obj, Tmt):
        return (f"TGMT nodes={obj.node_count} tracks={obj.track_count} keys={obj.key_count} "
                f"rot_tracks={obj.rot_track_count} rot_keys={obj.rot_key_count} frames={obj.frame_count} "
                f"flags={obj.flags}")
    return (f"TGMA entries={obj.entry_count} tracks={obj.track_count} keys={obj.key_count} "
            f"frames={obj.frame_count}")


def check_pointer_lists(members, offsets):
    """Classify every *ptrs.txt list: each non-zero entry must be the data offset of a member.
    Returns Counter of outcomes (kind of member pointed at, or 'bad')."""
    starts = {offset: name for name, offset in offsets.items()}
    result = Counter()
    for name, blob in members:
        if not name.lower().endswith("ptrs.txt"):
            continue
        values = struct.unpack_from(f"<{len(blob) // 4}I", blob)
        if not values or values[-1] != 0xFFFFFFFF:
            result["unterminated"] += 1
        for value in values[:-1]:
            if value == 0:
                result["null"] += 1
            elif value in starts:
                target = starts[value]
                base = tgm_name(target)
                result[(Path(base).suffix.lower() + (".gz" if target.lower().endswith(".gz") else "")) if base
                       else Path(target).suffix.lower()] += 1
            else:
                result["bad"] += 1
    return result


def tma_entry_matches(tms, index, material):
    """TGMA entry `index` names a material; that material's first texture layer must be the texture whose
    animation index is `index`."""
    if not 0 <= material < tms.material_count:
        return False
    texture = tms.materials[material]["layers"][0]["texture"]
    return 0 <= texture < tms.texture_count and tms.textures[texture]["animation"] == index


def record_bbox(stats, kind, tms, node_world, label, tolerance=0.01):
    """Count whether every posed vertex lies inside the header bounding box (tolerance relative to its extent)."""
    extent = max(max(abs(v) for v in tms.bbox_min + tms.bbox_max), 1e-6)
    stats[(kind, tms.bbox_error(node_world) <= tolerance * extent)] += 1


def run_check(paths, verbose):
    counts, problems, pointers = Counter(), Counter(), Counter()
    pairs = Counter()
    bbox = Counter()
    failures = 0
    for path in iter_archives(paths):
        try:
            data = path.read_bytes()
            archives = list(archive_members(data))
        except (OSError, ValueError, EOFError) as error:
            print(f"error: {path}: {error}", file=sys.stderr)
            failures += 1
            continue
        for prefix, members, offsets in archives:
            parsed = {}
            for name, raw_name, blob in tgm_members(members):
                label = f"{path}:{prefix}{raw_name}"
                try:
                    obj = parse(blob)
                    issues = obj.check()
                    if isinstance(obj, Tms) and not issues and not obj.bone_count:
                        record_bbox(bbox, 'unskinned', obj, None, label)
                except (ValueError, struct.error, IndexError) as error:
                    issues = [f"parse error: {error}"]
                    obj = None
                kind = blob[:4].decode("latin1") + (" (gz)" if raw_name.lower().endswith(".gz") else "")
                counts[kind] += 1
                if issues:
                    failures += 1
                    for issue in issues:
                        problems[issue] += 1
                    if verbose:
                        print(f"FAIL {label}: {'; '.join(issues)}")
                parsed[name] = obj
            # pairs by base name in one archive
            for name, obj in parsed.items():
                if isinstance(obj, Tma):
                    tms = parsed.get(name[:-4] + ".tms")
                    if not isinstance(tms, Tms):
                        pairs["tma without same-name tms"] += 1
                        continue
                    ok = tms.animated_texture_count == obj.entry_count and all(
                        tma_entry_matches(tms, i, e[16]) for i, e in enumerate(obj.entries))
                    pairs["tma entries match tms animated textures" if ok else "tma/tms mismatch"] += 1
                elif isinstance(obj, Tmt) and not obj.flags & TMT_FLAG_CAMERA:
                    tms = parsed.get(name[:-4] + ".tms")
                    if isinstance(tms, Tms):
                        same = tms.bone_count == obj.node_count
                        pairs["tmt nodes == same-name tms bones" if same else "tmt nodes != same-name tms bones"] += 1
                        if same and tms.bone_count and not tms.check():
                            record_bbox(bbox, 'skinned, same-name TGMT frame 0', tms, pose_matrices(tms, obj, 0),
                                        f'{path}:{prefix}{name}')
            if parsed:
                pointers.update(check_pointer_lists(members, offsets))
    for kind, n in sorted(counts.items()):
        print(f"{kind:10} {n:6}")
    print(f"total      {sum(counts.values()):6}  failing: {failures}")
    for issue, n in problems.most_common():
        print(f"  {n:6}  {issue}")
    for key, n in sorted(pairs.items()):
        print(f"pairs: {key}: {n}")
    print("pointer lists in archives with TGM members:", dict(sorted(pointers.items(), key=str)))
    for (kind, inside), n in sorted(bbox.items(), key=lambda x: str(x[0])):
        if kind != 'worst':
            print(f"bounding box ({kind}): {'inside' if inside else 'OUTSIDE'} (1% of extent): {n}")
    return 1 if failures else 0


# --- Export --------------------------------------------------------------------------------------

def find_member(path, member):
    for prefix, members, _ in archive_members(path.read_bytes()):
        for name, blob in members:
            if prefix + name == member or (tgm_name(prefix + name) == member):
                if blob[:2] == b"\x1f\x8b":
                    blob = gzip.decompress(blob)
                return blob, dict(members)
    raise KeyError(member)


def texture_member(texture_name, members):
    """The GIM member for a texture name: same base name, extension replaced by .gim (case-insensitive)."""
    stem = texture_name.rsplit(".", 1)[0].lower()
    for name, blob in members.items():
        if name.lower() == stem + ".gim":
            return name, blob
    return None, None


def export_obj(tms, members, out_dir, stem, node_world=None):
    out_dir.mkdir(parents=True, exist_ok=True)
    cip = _load("cip")
    lines = [f"mtllib {stem}.mtl"]
    mtl = []
    written = {}
    for t, tex in enumerate(tms.textures):
        gim_name, gim = texture_member(tex["name"], members)
        if gim is None:
            continue
        try:
            image, palette = cip.read_gim(gim)
            rgba = cip.decode_surface(image, palette, opaque=False)
            png = f"{stem}_tex{t:02d}_{Path(gim_name).stem}.png"
            cip.write_png(out_dir / png, image["width"], image["height"], rgba)
            written[t] = png
        except (ValueError, KeyError, struct.error) as error:
            print(f"texture {tex['name']}: {error}", file=sys.stderr)
    for i, m in enumerate(tms.materials):
        mtl.append(f"newmtl mat{i:03d}")
        r, g, b, a = m["diffuse"]
        mtl.append(f"Kd {r / 255:.4f} {g / 255:.4f} {b / 255:.4f}")
        mtl.append(f"d {a / 255:.4f}")
        tex = m["layers"][0]["texture"]
        if tex in written:
            mtl.append(f"map_Kd {written[tex]}")
    vcount = 0
    for i, m in enumerate(tms.materials):
        lines.append(f"o mat{i:03d}")
        lines.append(f"usemtl mat{i:03d}")
        for b in tms.batches[m["first_batch"]:m["first_batch"] + m["batch_count"]]:
            for prim in tms.prims[b["first_prim"]:b["first_prim"] + b["prim_count"]]:
                verts = tms.vertices_of(prim, b["vtype"])
                for v in verts:
                    x, y, z = tms.world_position(v, b, node_world)
                    lines.append(f"v {x:.6f} {y:.6f} {z:.6f}")
                    u, w = v.get("uv", (0.0, 0.0))
                    lines.append(f"vt {u:.6f} {1 - w:.6f}")
                start = vcount + 1
                if prim[0] == 3:
                    tris = [(k, k + 1, k + 2) for k in range(0, len(verts) - 2, 3)]
                else:
                    tris = [(k, k + 1, k + 2) if k % 2 == 0 else (k + 1, k, k + 2) for k in range(len(verts) - 2)]
                for a, b2, c in tris:
                    pa, pb, pc = (verts[n]["position"] for n in (a, b2, c))
                    if pa == pb or pb == pc or pa == pc:
                        continue  # degenerate strip joint
                    lines.append(f"f {start + a}/{start + a} {start + b2}/{start + b2} {start + c}/{start + c}")
                vcount += len(verts)
    (out_dir / f"{stem}.obj").write_text("\n".join(lines) + "\n", encoding="ascii")
    (out_dir / f"{stem}.mtl").write_text("\n".join(mtl) + "\n", encoding="ascii")
    return vcount, len(written)


def inspect(obj, out):
    print(summary(obj), file=out)
    if isinstance(obj, Tms):
        print(f"bbox {tuple(round(v, 4) for v in obj.bbox_min)} .. {tuple(round(v, 4) for v in obj.bbox_max)}"
              f" root_bone={obj.root_bone:#x} unknown_count_2={obj.unknown_count_2}", file=out)
        for i, t in enumerate(obj.textures):
            print(f"  texture {i}: {t['name']!r} mode={t['mode'].hex()} uv_offset={t['uv_offset']} "
                  f"uv_scale={t['uv_scale']} animation={t['animation']}", file=out)
        for i, m in enumerate(obj.materials):
            layers = [(l["texture"], l["blend"].hex()) for l in m["layers"] if l["texture"] != -1]
            print(f"  material {i}: flags={m['flags']:#x} diffuse={m['diffuse'].hex()} batches={m['first_batch']}"
                  f"+{m['batch_count']} layers={layers}", file=out)
        for i, b in enumerate(obj.batches):
            palette = [x for x in b["palette"] if x >= 0]
            print(f"  batch {i}: vtype={b['vtype']:#x} {describe_vtype(b['vtype'])} palette={palette} "
                  f"prims={b['first_prim']}+{b['prim_count']}", file=out)
        for i, (parent, child, sibling, _) in enumerate(obj.bones):
            print(f"  bone {i}: parent={parent} child={child} sibling={sibling}", file=out)
    elif isinstance(obj, Tmt):
        for i, (t, r, s, _) in enumerate(obj.nodes):
            print(f"  node {i}: translate={'-' if t == 0xFFFF else t} rotate={r} scale={s}", file=out)
    else:
        for i, e in enumerate(obj.entries):
            slots = {TMA_SLOTS[k][0]: e[k] for k in TMA_SLOTS if e[k] != -1}
            print(f"  entry {i}: material={e[16]} {slots}", file=out)


def main(argv=None):
    parser = argparse.ArgumentParser(description="List, check and export TGM members (.tms/.tmt/.tma) of EHP archives.")
    sub = parser.add_subparsers(dest="command", required=True)
    lister = sub.add_parser("list", help="one line per TGM member")
    lister.add_argument("paths", type=Path, nargs="+", help="EHP files or directories")
    insp = sub.add_parser("inspect", help="print the tables of one member")
    insp.add_argument("archive", type=Path)
    insp.add_argument("member", help="member name ('.gz' optional); nested archives as outer.ehp:inner")
    chk = sub.add_parser("check", help="structural validation of every TGM member under the given paths")
    chk.add_argument("paths", type=Path, nargs="+")
    chk.add_argument("-v", "--verbose", action="store_true", help="print each failing member")
    obj = sub.add_parser("obj", help="export a TGMS to OBJ/MTL with PNG textures (keep out of git)")
    obj.add_argument("archive", type=Path)
    obj.add_argument("member")
    obj.add_argument("--tmt", help="TGMT member that poses a skinned mesh (default: same name as the .tms)")
    obj.add_argument("--frame", type=float, default=0, help="animation frame for the pose (default 0)")
    obj.add_argument("-o", "--output", type=Path, required=True, help="output directory")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if args.command == "check":
        return run_check(args.paths, args.verbose)
    if args.command == "list":
        for path in iter_archives(args.paths):
            for prefix, members, _ in archive_members(path.read_bytes()):
                for name, raw_name, blob in tgm_members(members):
                    try:
                        text = summary(parse(blob))
                    except (ValueError, struct.error) as error:
                        text = f"error: {error}"
                    print(f"{path}:{prefix}{raw_name}  {len(blob)}  {text}")
        return 0
    blob, members = find_member(args.archive, args.member)
    item = parse(blob)
    if args.command == "inspect":
        inspect(item, sys.stdout)
        return 0
    if not isinstance(item, Tms):
        print("error: obj export needs a .tms member", file=sys.stderr)
        return 1
    stem = Path(tgm_name(args.member) or args.member).stem
    node_world = None
    if item.bone_count:
        tmt_name = args.tmt or args.member.rsplit(".", 1)[0] + ".tmt"
        try:
            node_world = pose_matrices(item, Tmt(find_member(args.archive, tmt_name)[0]), args.frame)
        except (KeyError, ValueError) as error:
            print(f"warning: no pose from {tmt_name} ({error}); skinned vertices use the offset matrices alone",
                  file=sys.stderr)
    verts, textures = export_obj(item, members, args.output, stem, node_world)
    print(f"{args.output / (stem + '.obj')}: {verts} vertices, {textures} textures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
