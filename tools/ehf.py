#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""List, inspect, check and render the 2D layouts `.ehf` (magic "EHF\\x1a") and their `.tmf` companions.
See docs/formats/ehf.md.

An .ehf is a converted vector-animation timeline: a stage in twips (1/20 pixel), a main timeline of
placement records, shapes (textured quads as PSP GE display lists) and nested clips (own timelines),
and per-placement keyframe tracks (affine matrix and colour transform).

Examples (archives are EHP files; an ELF such as BOOT.BIN is scanned for embedded archives):
    python3 -I tools/ehf.py list USRDIR/title_menu/title_menu_e.ehp
    python3 -I tools/ehf.py inspect USRDIR/title_menu/title_menu_e.ehp press_start.ehf
    python3 -I tools/ehf.py check USRDIR SYSDIR/BOOT.BIN
    python3 -I tools/ehf.py render SYSDIR/BOOT.BIN loading.ehf --frame 10 -o extracted/ehf/loading.png
"""

import argparse
import gzip
import importlib.util
import struct
import sys
from collections import Counter
from pathlib import Path

TOOLS = Path(__file__).resolve().parent


def _load(name):
    spec = importlib.util.spec_from_file_location(f"re_{name}", TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ehp = _load("ehp")

MAGIC = b"EHF\x1a"
SECTIONS = 5  # stage, work area, main timeline, objects, texture names; a sixth (offset, size) pair is zero
TWIPS = 20  # layout units per pixel
NODE = struct.Struct("<iHHHH")  # object offset / 16 (-1: remove), track index, depth, clip depth, frames to wait
STAGE = struct.Struct("<I4sIIiiii")  # frames, background RGBA, rate?, 0, xmin, xmax, ymin, ymax
TRACK_HEAD = struct.Struct("<9f4H")  # a b c d tx ty, 3 dequantisation steps, flags, keys, stride, 0
SHAPE, CLIP = 0, 3
CHANNELS = ("translate", "scale", "skew", "multiply", "add")  # flag bits 0-4, 4 bytes each per key
UV_ONE = 2048  # 16-bit texture coordinates: 2047 is the far edge of the (power-of-two) texture
PRIMS = {0: "points", 1: "lines", 2: "line_strip", 3: "triangles", 4: "triangle_strip", 5: "triangle_fan",
         6: "sprites"}


class EhfError(ValueError):
    pass


def _u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def _cstr(data, offset):
    end = data.index(b"\0", offset)
    return data[offset:end].decode("cp932")


# --- Parsing --------------------------------------------------------------------------------------

def parse_nodes(data, offset, size):
    if size % NODE.size:
        raise EhfError(f"timeline size {size:#x} is not a multiple of {NODE.size}")
    nodes = []
    for pos in range(offset, offset + size, NODE.size):
        obj, track, depth, clip, wait = NODE.unpack_from(data, pos)
        nodes.append({"object": None if obj == -1 else obj * 16, "track": track, "depth": depth,
                      "clip": clip, "wait": wait})
    return nodes


def parse_track(data, offset, limit):
    """One keyframe track: base transform, dequantisation steps and keys."""
    *floats, flags, count, stride, pad = TRACK_HEAD.unpack_from(data, offset)
    if flags & ~0x3F:
        raise EhfError(f"track at {offset:#x}: unknown channel flags {flags:#x}")
    expected = 2 + 4 * bin(flags & 0x1F).count("1")  # bit 5 (seen twice) adds no key data
    if count and stride != expected:
        raise EhfError(f"track at {offset:#x}: stride {stride} for flags {flags:#x}, expected {expected}")
    start = offset + TRACK_HEAD.size
    if start + count * stride > limit:
        raise EhfError(f"track at {offset:#x}: keys run past the animation block")
    keys = []
    for index in range(count):
        pos = start + index * stride
        key = {"frame": struct.unpack_from("<H", data, pos)[0]}
        pos += 2
        for bit, name in enumerate(CHANNELS):
            if flags >> bit & 1:
                if bit < 3:
                    key[name] = struct.unpack_from("<hh", data, pos)
                elif bit == 3:
                    key[name] = tuple(data[pos:pos + 4])
                else:
                    key[name] = struct.unpack_from("<4b", data, pos)
                pos += 4
        keys.append(key)
    return {"base": tuple(floats[:6]), "steps": tuple(floats[6:]), "flags": flags, "pad": pad, "keys": keys,
            "end": start + count * stride}


def parse_tracks(data, offset, size):
    """Animation block: a table of u32 offsets (relative to the block; 0 = unused) followed by tracks."""
    if size < 4:
        return []
    first = _u32(data, offset)
    if first % 4 or not 4 <= first <= size:
        raise EhfError(f"animation block at {offset:#x}: bad first track offset {first:#x}")
    table = struct.unpack_from(f"<{first // 4}I", data, offset)
    return [parse_track(data, offset + rel, offset + size) if rel else None for rel in table]


def vertex_size(vtype):
    if vtype & ~0x183 or vtype >> 7 & 3 != 2 or vtype & 3 not in (0, 2):
        raise EhfError(f"unsupported vertex type {vtype:#x}")
    return 6 + (4 if vtype & 3 else 0)


def parse_shape(data, base, head):
    anchor_x, anchor_y, scale = struct.unpack_from("<3f", data, base + 4)
    dl_off, dl_size, vtx_off, vtx_size, anim_off, anim_size = struct.unpack_from("<6I", data, base + 16)
    words = struct.unpack_from(f"<{dl_size // 4}I", data, base + dl_off)
    if len(words) % 6:
        raise EhfError(f"shape at {head:#x}: display list of {len(words)} words is not a multiple of 6")
    prims = []
    for i in range(0, len(words), 6):
        cmds = [w >> 24 for w in words[i:i + 6]]
        if cmds[:3] != [0x55, 0x58, 0x12] or cmds[3] not in (0x00, 0xFF) or cmds[4] != 0 or cmds[5] != 0x04:
            raise EhfError(f"shape at {head:#x}: unexpected display-list commands {cmds}")
        ambient, alpha, vtype, texture, vaddr, prim = (w & 0xFFFFFF for w in words[i:i + 6])
        if cmds[3] == 0xFF and texture >> 16 != 0xFF:
            raise EhfError(f"shape at {head:#x}: texture word {words[i + 3]:#x}")
        size = vertex_size(vtype)
        kind, count = prim >> 16 & 7, prim & 0xFFFF
        if vaddr + size * count > vtx_size:
            raise EhfError(f"shape at {head:#x}: vertices run past the vertex block")
        verts = []
        for v in range(count):
            pos = base + vtx_off + vaddr + v * size
            uv = struct.unpack_from("<HH", data, pos) if vtype & 3 else None
            xyz = struct.unpack_from("<3h", data, pos + (4 if uv else 0))
            verts.append((uv, xyz))
        prims.append({"ambient": (ambient & 0xFF, ambient >> 8 & 0xFF, ambient >> 16 & 0xFF),
                      "alpha": alpha & 0xFF, "vtype": vtype,
                      "texture": (texture & 0xFFFF) if cmds[3] == 0xFF else None,
                      "vaddr": vaddr, "prim": kind, "vertices": verts})
    return {"type": SHAPE, "anchor": (anchor_x, anchor_y), "scale": scale, "prims": prims,
            "tracks": parse_tracks(data, base + anim_off, anim_size),
            "size": max(dl_off + dl_size, vtx_off + vtx_size, anim_off + anim_size)}


def parse_clip(data, base, head):
    frames, tl_off, tl_size, anim_off, anim_size = struct.unpack_from("<5I", data, base + 4)
    return {"type": CLIP, "frames": frames, "timeline": parse_nodes(data, base + tl_off, tl_size),
            "tracks": parse_tracks(data, base + anim_off, anim_size),
            "size": max(tl_off + tl_size, anim_off + anim_size)}


def parse(data):
    """Parse an .ehf. Object offsets (dict keys and node references) are relative to the object section."""
    if data[:4] != MAGIC:
        raise EhfError("not an EHF file")
    if any(data[4:16]):
        raise EhfError("non-zero bytes in header padding")
    sections = [struct.unpack_from("<II", data, 0x10 + 8 * i) for i in range(SECTIONS + 1)]
    if sections[SECTIONS] != (0, 0):
        raise EhfError("sixth section entry is not empty")
    pos = 0x40
    for index, (offset, size) in enumerate(sections[:SECTIONS]):
        if offset != (pos + 15) // 16 * 16:
            raise EhfError(f"section {index} at {offset:#x}, expected {(pos + 15) // 16 * 16:#x}")
        pos = offset + size
    if pos != len(data):
        raise EhfError(f"sections end at {pos:#x}, file is {len(data):#x} bytes")
    (stage_off, _), (work_off, work_size), (tl_off, tl_size), (obj_off, obj_size), (names_off, names_size) = \
        sections[:SECTIONS]
    frames, background, rate, zero, *rect = STAGE.unpack_from(data, stage_off)
    objects = {}
    rel = 0
    while rel < obj_size:
        base = obj_off + rel
        kind = _u32(data, base)
        if kind == SHAPE:
            obj = parse_shape(data, base, rel)
        elif kind == CLIP:
            obj = parse_clip(data, base, rel)
        else:
            raise EhfError(f"object at {rel:#x}: unknown type {kind}")
        objects[rel] = obj
        rel += (obj["size"] + 15) // 16 * 16
    if rel != obj_size:
        raise EhfError("objects do not fill their section")
    names = {}
    for offset in range(0, names_size, 16):
        if data[names_off + offset]:
            names[offset] = _cstr(data, names_off + offset)
            if len(names[offset].encode("cp932")) > 15:
                raise EhfError(f"texture name at slot {offset:#x} does not fit 16 bytes")
    return {"frames": frames, "background": tuple(background), "rate": rate, "zero": zero, "rect": tuple(rect),
            "work_size": work_size, "work_zero": not any(data[work_off:work_off + work_size]),
            "timeline": parse_nodes(data, tl_off, tl_size), "objects": objects, "names": names,
            "slots": names_size // 16,
            "sections": sections[:SECTIONS]}


def parse_tmf(data):
    """.tmf: one flag byte per texture-name slot of the paired .ehf (values 0x00, 0x01, 0x10, 0x11 seen)."""
    return list(data)


# --- Consistency checks ---------------------------------------------------------------------------

WORK_HEAD, WORK_INSTANCE = 0x78, 0x28


def peak_instances(layout, timeline=None):
    """Largest number of live display instances of a timeline, sampled at every frame boundary (node with a
    non-zero wait); a clip instance counts 1 plus the peak of its own timeline."""
    objects = layout["objects"]
    best, stage = 0, {}
    for node in layout["timeline"] if timeline is None else timeline:
        if node["object"] is None:
            stage.pop(node["depth"], None)
        else:
            stage[node["depth"]] = objects[node["object"]]
        if node["wait"]:
            best = max(best, sum(1 + (peak_instances(layout, o["timeline"]) if o["type"] == CLIP else 0)
                                 for o in stage.values()))
    return best


def work_size(layout):
    """Size of the zero-filled work area: 0x78 + 0x28 per peak instance, rounded up to 16 (all disc files)."""
    return (WORK_HEAD + WORK_INSTANCE * peak_instances(layout) + 15) // 16 * 16


def check(layout, members=None):
    """Return a list of problems (empty if the layout is consistent)."""
    problems = []
    objects, names = layout["objects"], layout["names"]
    if not layout["work_zero"]:
        problems.append("work area is not zero")
    try:
        if work_size(layout) != layout["work_size"]:
            problems.append(f"work area {layout['work_size']:#x}, expected {work_size(layout):#x}")
    except KeyError:
        pass  # a missing object is reported below

    def check_timeline(timeline, frames, where):
        if sum(n["wait"] for n in timeline) != frames:
            problems.append(f"{where}: waits add up to {sum(n['wait'] for n in timeline)}, not {frames}")
        for node in timeline:
            obj = node["object"]
            if obj is None:
                continue
            if obj not in objects:
                problems.append(f"{where}: node refers to missing object {obj:#x}")
                continue
            tracks = objects[obj]["tracks"]
            if node["track"] >= len(tracks) or tracks[node["track"]] is None:
                problems.append(f"{where}: node uses missing track {node['track']} of object {obj:#x}")

    check_timeline(layout["timeline"], layout["frames"], "main timeline")
    for rel, obj in objects.items():
        for track in obj["tracks"]:
            if track and [k["frame"] for k in track["keys"]] != sorted(k["frame"] for k in track["keys"]):
                problems.append(f"object {rel:#x}: key frames not sorted")
        if obj["type"] == CLIP:
            check_timeline(obj["timeline"], obj["frames"], f"clip {rel:#x}")
        else:
            for prim in obj["prims"]:
                if prim["texture"] is not None:
                    name = names.get(prim["texture"])
                    if name is None:
                        problems.append(f"object {rel:#x}: texture slot {prim['texture']:#x} is empty")
                    elif members is not None and (name + ".gim").lower() not in members:
                        problems.append(f"object {rel:#x}: texture {name}.gim not in the archive")
    return problems


def tmf_matches(layout, tmf):
    """True if the .tmf has one byte per texture-name slot. A few localised archives carry a .tmf that
    was not regenerated after a texture slot was added (or an empty layout with a 1-byte .tmf)."""
    return len(tmf) == layout["slots"]


# --- Archives -------------------------------------------------------------------------------------

def archives_in(path):
    """Yield (label, archive bytes) for an EHP file (gzip accepted), nested EHPs, or EHPs embedded in an ELF."""
    data = path.read_bytes()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    if data[:4] == b"\x7fELF":
        pos = data.find(ehp.MAGIC)
        while pos >= 0:
            if data[pos + 8:pos + 12] == ehp.TAG:
                size = _u32(data, pos + 4)
                yield from _with_nested(f"{path}@{pos:#x}", data[pos:pos + size])
            pos = data.find(ehp.MAGIC, pos + 4)
        return
    if data[:4] == ehp.MAGIC:
        yield from _with_nested(str(path), data)


def _with_nested(label, data):
    members = ehp.parse(data)
    yield label, members
    for name, blob in members:
        if blob[:4] == ehp.MAGIC:
            yield from _with_nested(f"{label}/{name}", blob)


def layouts(members):
    """Yield (name, ehf bytes, tmf bytes or None) for every .ehf member of an archive."""
    by_name = {name.lower(): blob for name, blob in members}
    for name, blob in members:
        if name.lower().endswith(".ehf"):
            yield name, blob, by_name.get(name[:-4].lower() + ".tmf")


def find_member(path, member):
    for label, members in archives_in(path):
        for name, blob in members:
            if name.lower() == member.lower():
                return label, members, blob
    raise EhfError(f"{member} not found in {path}")


# --- Evaluation and rendering ---------------------------------------------------------------------

def track_state(track, frame):
    """Transform (a, b, c, d, tx, ty), colour multiply (4 floats) and add (4 ints) of a track at a frame.
    Keys are linearly interpolated (hypothesis) and held before the first and after the last key."""
    a, b, c, d, tx, ty = track["base"]
    s_t, s_scale, s_skew = track["steps"]
    mul, add = [1.0, 1.0, 1.0, 1.0], [0, 0, 0, 0]
    keys = track["keys"]
    if not keys:
        return (a, b, c, d, tx, ty), mul, add
    if frame <= keys[0]["frame"]:
        k0 = k1 = keys[0]
    elif frame >= keys[-1]["frame"]:
        k0 = k1 = keys[-1]
    else:
        k1 = next(k for k in keys if k["frame"] > frame)
        k0 = keys[keys.index(k1) - 1]
    span = k1["frame"] - k0["frame"]
    w = (frame - k0["frame"]) / span if span else 0.0

    def lerp(name):
        return [p + (q - p) * w for p, q in zip(k0[name], k1[name])]

    if "translate" in k0:
        qx, qy = lerp("translate")
        tx, ty = tx + qx * s_t, ty + qy * s_t
    if "scale" in k0:
        qa, qd = lerp("scale")
        a, d = a + qa * s_scale, d + qd * s_scale
    if "skew" in k0:
        qb, qc = lerp("skew")
        b, c = b + qb * s_skew, c + qc * s_skew
    if "multiply" in k0:
        mul = [v / 128 for v in lerp("multiply")]
    if "add" in k0:
        add = [v * 2 for v in lerp("add")]
    return (a, b, c, d, tx, ty), mul, add


def apply(matrix, x, y):
    """(a, b, c, d, tx, ty) maps x' = a*x + c*y + tx, y' = b*x + d*y + ty (column order, as in a
    Flash MATRIX: a = ScaleX, b = RotateSkew0, c = RotateSkew1, d = ScaleY). Chosen because the other
    order visibly breaks rotated multi-part sprites in loading.ehf."""
    a, b, c, d, tx, ty = matrix
    return a * x + c * y + tx, b * x + d * y + ty


def compose(parent, child):
    pa, pb, pc, pd, ptx, pty = parent
    a, b, c, d, tx, ty = child
    return (pa * a + pc * b, pb * a + pd * b, pa * c + pc * d, pb * c + pd * d,
            pa * tx + pc * ty + ptx, pb * tx + pd * ty + pty)


def placements(timeline, frame):
    """Objects on stage at `frame` of a timeline: {depth: (node, frame placed)}."""
    stage, time = {}, 0
    for node in timeline:
        if time > frame:
            break
        if node["object"] is None:
            stage.pop(node["depth"], None)
        else:
            stage[node["depth"]] = (node, time)
        time += node["wait"]
    return stage


def draw_list(layout, frame):
    """Flatten the layout at a frame into [(depth path, clip depth, object, matrix, mul, add)] in draw order."""
    out = []

    def walk(timeline, local, parent, pmul, padd, path):
        for depth, (node, placed) in sorted(placements(timeline, local).items()):
            obj = layout["objects"][node["object"]]
            track = obj["tracks"][node["track"]]
            matrix, mul, add = track_state(track, local - placed)
            matrix = compose(parent, matrix)
            mul = [p * m for p, m in zip(pmul, mul)]
            add = [p + a for p, a in zip(padd, add)]
            if obj["type"] == CLIP:
                frames = max(obj["frames"], 1)
                walk(obj["timeline"], (local - placed) % frames, matrix, mul, add, path + (depth,))
            else:
                out.append((path + (depth,), node["clip"], obj, matrix, mul, add))

    walk(layout["timeline"], frame, (1.0, 0.0, 0.0, 1.0, 0.0, 0.0), [1.0] * 4, [0] * 4, ())
    return out


def _triangles(prim):
    verts = prim["vertices"]
    if prim["prim"] == 4:
        return [verts[i:i + 3] for i in range(len(verts) - 2)]
    if prim["prim"] == 3:
        return [verts[i:i + 3] for i in range(0, len(verts) - 2, 3)]
    if prim["prim"] == 5:
        return [(verts[0], verts[i], verts[i + 1]) for i in range(1, len(verts) - 1)]
    return []  # points and lines are not drawn


def render(layout, frame, textures, background=None, tmf=None):
    """Rasterise one frame to (width, height, RGBA bytes). `textures` maps texture slot offset to
    (width, height, rgba, pow2 width, pow2 height); a missing slot is drawn magenta. Nearest sampling,
    src-over blending, or additive blending for slots whose .tmf byte has bit 0 set (hypothesis)."""
    xmin, xmax, ymin, ymax = layout["rect"]
    width, height = (xmax - xmin) // TWIPS, (ymax - ymin) // TWIPS
    canvas = [list(background) if background else [0, 0, 0, 0] for _ in range(width * height)]
    masks = []  # (path prefix, depth, clip depth, coverage set)
    for path, clip, obj, matrix, mul, add in draw_list(layout, frame):
        ax, ay = obj["anchor"]
        scale = obj["scale"]
        covered = set() if clip else None
        active = [m[3] for m in masks if m[0] == path[:-1] and m[1] < path[-1] <= m[2]]
        for prim in obj["prims"]:
            tex = textures.get(prim["texture"]) if prim["texture"] is not None else None
            base_rgb = [v / 255 for v in prim["ambient"]] + [prim["alpha"] / 255]
            slot = prim["texture"]
            additive = bool(tmf and slot is not None and slot // 16 < len(tmf) and tmf[slot // 16] & 1)
            for tri in _triangles(prim):
                pts = []
                for uv, (vx, vy, _) in tri:
                    x, y = vx * scale + ax, vy * scale + ay
                    sx, sy = apply(matrix, x, y)
                    pts.append(((sx - xmin) / TWIPS, (sy - ymin) / TWIPS, uv))
                _raster(pts, tex, prim["texture"] is not None, base_rgb, mul, add, canvas, width, height,
                        covered, active, additive)
        if clip:
            masks.append((path[:-1], path[-1], clip, covered))
    rgba = bytearray()
    for px in canvas:
        rgba += bytes(max(0, min(255, int(round(v)))) for v in px)
    return width, height, bytes(rgba)


def _raster(pts, tex, textured, base, mul, add, canvas, width, height, covered, active, additive=False):
    (x0, y0, t0), (x1, y1, t1), (x2, y2, t2) = pts
    area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
    if abs(area) < 1e-9:
        return
    left, right = max(0, int(min(x0, x1, x2))), min(width - 1, int(max(x0, x1, x2)) + 1)
    top, bottom = max(0, int(min(y0, y1, y2))), min(height - 1, int(max(y0, y1, y2)) + 1)
    for py in range(top, bottom + 1):
        cy = py + 0.5
        for px in range(left, right + 1):
            cx = px + 0.5
            w1 = ((cx - x0) * (y2 - y0) - (x2 - x0) * (cy - y0)) / area
            w2 = ((x1 - x0) * (cy - y0) - (cx - x0) * (y1 - y0)) / area
            w0 = 1 - w1 - w2
            if w0 < -1e-6 or w1 < -1e-6 or w2 < -1e-6:
                continue
            index = py * width + px
            if covered is not None:
                covered.add(index)
                continue
            if active and not all(index in m for m in active):
                continue
            if textured:
                if tex is None:
                    src = [255, 0, 255, 255]
                else:
                    tw, th, data, pw, ph = tex
                    u = (w0 * t0[0] + w1 * t1[0] + w2 * t2[0]) / UV_ONE * pw
                    v = (w0 * t0[1] + w1 * t1[1] + w2 * t2[1]) / UV_ONE * ph
                    iu, iv = int(u), int(v)
                    if not (0 <= iu < tw and 0 <= iv < th):
                        continue
                    o = (iv * tw + iu) * 4
                    src = list(data[o:o + 4])
                src = [s * bv for s, bv in zip(src, base)]
            else:
                src = [bv * 255 for bv in base]
            src = [s * m + ad for s, m, ad in zip(src, mul, add)]
            alpha = max(0.0, min(1.0, src[3] / 255))
            dst = canvas[index]
            if additive:
                for ch in range(3):
                    dst[ch] = min(255.0, dst[ch] + max(0.0, src[ch]) * alpha)
                continue
            for ch in range(3):
                dst[ch] = max(0.0, min(255.0, src[ch])) * alpha + dst[ch] * (1 - alpha)
            dst[3] = alpha * 255 + dst[3] * (1 - alpha)


def load_textures(layout, members):
    """Decode the GIM named by each texture slot (`<name>.gim` in the same archive)."""
    cip = _load("cip")
    by_name = {name.lower(): blob for name, blob in members}
    textures = {}
    for slot, name in layout["names"].items():
        blob = by_name.get(name.lower() + ".gim")
        if blob is None:
            continue
        image, palette = cip.read_gim(blob)
        rgba = cip.decode_surface(image, palette, opaque=False)
        pw = 1 << max(0, image["width"] - 1).bit_length()
        ph = 1 << max(0, image["height"] - 1).bit_length()
        textures[slot] = (image["width"], image["height"], rgba, pw, ph)
    return textures


# --- Command line ---------------------------------------------------------------------------------

def summary(name, layout, tmf):
    shapes = sum(o["type"] == SHAPE for o in layout["objects"].values())
    clips = len(layout["objects"]) - shapes
    xmin, xmax, ymin, ymax = layout["rect"]
    return (f"{name}: {layout['frames']} frames, stage {(xmax - xmin) / TWIPS:g}x{(ymax - ymin) / TWIPS:g}, "
            f"{len(layout['timeline'])} nodes, {shapes} shapes, {clips} clips, {len(layout['names'])} textures"
            f"{'' if tmf is None else ', tmf ' + bytes(tmf).hex()}")


def inspect(name, layout, tmf, out=print):
    out(summary(name, layout, tmf))
    out(f"  background #{bytes(layout['background']).hex()}  rate? {layout['rate']}  rect {layout['rect']}")
    for slot, tex in layout["names"].items():
        out(f"  texture {slot:#06x} {tex}" + ("" if tmf is None else (f"  tmf {tmf[slot // 16]:#04x}" if slot // 16 < len(tmf) else "  tmf (missing)")))

    def show_timeline(timeline, indent):
        time = 0
        for node in timeline:
            what = "remove" if node["object"] is None else f"place object {node['object']:#x} track {node['track']}"
            clip = f" clip<= {node['clip']}" if node["clip"] else ""
            out(f"{indent}frame {time:4}: depth {node['depth']:3} {what}{clip}, wait {node['wait']}")
            time += node["wait"]

    out("  main timeline:")
    show_timeline(layout["timeline"], "    ")
    for rel, obj in layout["objects"].items():
        if obj["type"] == SHAPE:
            out(f"  object {rel:#x}: shape, anchor {obj['anchor']}, scale {obj['scale']:.6g}, {len(obj['prims'])} prims")
            for prim in obj["prims"]:
                tex = layout["names"].get(prim["texture"], "-") if prim["texture"] is not None else "-"
                out(f"    {PRIMS.get(prim['prim'], prim['prim'])} x{len(prim['vertices'])} tex {tex} "
                    f"colour #{bytes(prim['ambient']).hex()}{prim['alpha']:02x} vtype {prim['vtype']:#x}")
        else:
            out(f"  object {rel:#x}: clip, {obj['frames']} frames")
            show_timeline(obj["timeline"], "    ")
        for index, track in enumerate(obj["tracks"]):
            if track:
                base = " ".join(f"{v:.6g}" for v in track["base"])
                chans = ",".join(n for bit, n in enumerate(CHANNELS) if track["flags"] >> bit & 1) or "static"
                out(f"    track {index}: base [{base}] steps {[f'{s:.4g}' for s in track['steps']]} "
                    f"{chans}, {len(track['keys'])} keys")


def iter_paths(paths):
    for path in paths:
        if path.is_dir():
            yield from (p for p in sorted(path.rglob("*")) if p.is_file())
        else:
            yield path


def run_check(paths):
    stats = Counter()
    failures = 0
    for path in iter_paths(paths):
        try:
            archives = list(archives_in(path))
        except (OSError, ValueError, EOFError):
            continue
        for label, members in archives:
            lower = {name.lower() for name, _ in members}
            for name, blob, tmf_blob in layouts(members):
                stats["ehf"] += 1
                stats["with tmf"] += tmf_blob is not None
                try:
                    layout = parse(blob)
                    problems = check(layout, lower)
                    if tmf_blob is not None and not tmf_matches(layout, tmf_blob):
                        stats["tmf length differs"] += 1
                        print(f"note {label}/{name}: .tmf has {len(tmf_blob)} bytes for {layout['slots']} slots")
                except (EhfError, struct.error, UnicodeDecodeError) as error:
                    problems = [f"parse error: {error}"]
                    layout = None
                if problems:
                    failures += 1
                    for problem in problems[:5]:
                        print(f"FAIL {label}/{name}: {problem}")
                    continue
                stats["ok"] += 1
                for obj in layout["objects"].values():
                    stats["shapes" if obj["type"] == SHAPE else "clips"] += 1
                    stats["prims"] += len(obj.get("prims", ()))
                    stats["tracks"] += sum(t is not None for t in obj["tracks"])
                stats["nodes"] += len(layout["timeline"])
                stats["texture slots"] += len(layout["names"])
            stats["tmf"] += sum(name.lower().endswith(".tmf") for name, _ in members)
    print(", ".join(f"{k} {v}" for k, v in stats.items()))
    print("OK" if not failures else f"{failures} layouts FAILED")
    return 1 if failures else 0


def output_allowed(path):
    return "extracted" in (part.lower() for part in path.resolve().parts)


def main(argv=None):
    parser = argparse.ArgumentParser(description="List, inspect, check and render .ehf/.tmf layouts.")
    sub = parser.add_subparsers(dest="command", required=True)
    lister = sub.add_parser("list", help="one line per .ehf in each archive")
    lister.add_argument("archives", type=Path, nargs="+")
    insp = sub.add_parser("inspect", help="dump one layout")
    insp.add_argument("archive", type=Path)
    insp.add_argument("member")
    chk = sub.add_parser("check", help="parse and cross-check every .ehf/.tmf pair (directories are walked)")
    chk.add_argument("paths", type=Path, nargs="+")
    ren = sub.add_parser("render", help="render one frame to PNG (output must be under an extracted/ directory)")
    ren.add_argument("archive", type=Path)
    ren.add_argument("member")
    ren.add_argument("--frame", type=int, help="frame to draw (default: middle of the main timeline)")
    ren.add_argument("--background", action="store_true", help="fill with the stage background colour")
    ren.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if args.command == "check":
        return run_check(args.paths)
    if args.command == "list":
        for path in args.archives:
            for label, members in archives_in(path):
                for name, blob, tmf in layouts(members):
                    try:
                        print(f"{label}: " + summary(name, parse(blob), tmf))
                    except EhfError as error:
                        print(f"{label}: {name}: error: {error}")
        return 0
    label, members, blob = find_member(args.archive, args.member)
    tmf = dict((n.lower(), b) for n, b in members).get(args.member[:-4].lower() + ".tmf")
    layout = parse(blob)
    if args.command == "inspect":
        inspect(f"{label}/{args.member}", layout, parse_tmf(tmf) if tmf is not None else None)
        return 0
    if not output_allowed(args.output):
        print("error: rendered game graphics must be written under an extracted/ directory", file=sys.stderr)
        return 1
    frame = args.frame if args.frame is not None else layout["frames"] // 2
    background = layout["background"] if args.background else None
    width, height, rgba = render(layout, frame, load_textures(layout, members), background,
                                 parse_tmf(tmf) if tmf is not None else None)
    _load("cip").write_png(args.output, width, height, rgba)
    print(f"wrote {args.output} ({width}x{height}, frame {frame} of {layout['frames']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
