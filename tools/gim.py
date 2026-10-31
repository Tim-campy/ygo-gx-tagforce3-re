#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Convert GIM textures (loose .gim or members of EHP archives) to PNG. See docs/formats/gim.md.

  gim.py info  <file> [member]                     one line per GIM (format, size, order, frames, palettes)
  gim.py png   <file> [member] -o out.png [--frame N] [--clut N]
  gim.py batch <files or dirs…> -o DIR [--first]   every GIM, every frame and palette level
  gim.py check <files or dirs…>                    decode every plane of every GIM, print the format histogram

<file> is a .gim, an .ehp (an .ehp.gz is accepted) or an ELF such as BOOT.BIN (its embedded archives are
searched). <member> is a member name, optionally with nested archives (`inner.ehp/name.gim` or `inner.ehp:name.gim`).
PNG output is game data: it must go outside the repository or under an extracted/ directory, never into git.
"""

import argparse
import importlib.util
import struct
import sys
from collections import Counter
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent


def _load(name):
    spec = importlib.util.spec_from_file_location(f"re_{name}", TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ehp = _load("ehp")
cip = _load("cip")  # block walker, colour formats, DXT1, unswizzle and the PNG writer

MAGIC = cip.GIM_MAGIC
FORMATS = cip.GIM_FORMATS
INFO = struct.Struct("<10H2H4I4H")  # the 0x30-byte surface header of image (4) and palette (5) blocks
BITS = {0: 16, 1: 16, 2: 16, 3: 32, 4: 4, 5: 8, 6: 16, 7: 32, 8: 4}
TRANSPARENT = b"\0\0\0\0"


class GimError(ValueError):
    pass


# --- Parsing --------------------------------------------------------------------------------------

def surface(data, block_offset):
    """Image or palette block: header fields plus `planes`, a {(frame, level): bytes} map.

    The surface header is followed (at `index_start`) by `level_count * frame_count` u32 plane offsets,
    relative to the header; plane k is frame k // level_count, level k % level_count. A plane ends at the
    next plane's offset or at `pixels_end`."""
    head = block_offset + struct.unpack_from("<I", data, block_offset + 12)[0]
    (hsize, _, fmt, order, width, height, bpp, pitch_align, height_align, _, _, _,
     index_start, pixels_start, pixels_end, _, level_type, levels, frame_type, frames) = INFO.unpack_from(data, head)
    levels, frames = max(levels, 1), max(frames, 1)
    count = levels * frames
    offsets = list(struct.unpack_from(f"<{count}I", data, head + index_start))
    if offsets[0] != pixels_start:
        raise GimError(f"first plane offset {offsets[0]:#x} differs from data start {pixels_start:#x}")
    planes = {}
    for k, start in enumerate(offsets):
        end = offsets[k + 1] if k + 1 < count else pixels_end
        if not pixels_start <= start <= end <= pixels_end or head + end > len(data):
            raise GimError(f"plane {k} [{start:#x}, {end:#x}) outside the data")
        planes[(k // levels, k % levels)] = data[head + start:head + end]
    return {"format": fmt, "order": order, "width": width, "height": height, "bpp": bpp,
            "pitch_align": max(pitch_align, 1), "height_align": max(height_align, 1),
            "levels": levels, "frames": frames, "level_type": level_type, "frame_type": frame_type,
            "header_size": hsize, "index_start": index_start, "planes": planes}


def parse(data):
    """Return (image, palette or None) of the single picture of a GIM (every GIM on this disc has one)."""
    image = palette = None
    for block_id, offset, _ in cip.gim_blocks(data):
        if block_id == 4 and image is None:
            image = surface(data, offset)
        elif block_id == 5 and palette is None:
            palette = surface(data, offset)
    if image is None:
        raise GimError("GIM has no image block")
    if image["format"] in (4, 5, 6, 7) and palette is None:
        raise GimError("indexed image without a palette")
    return image, palette


# --- Decoding -------------------------------------------------------------------------------------

def clut(palette, frame=0, level=0):
    """Palette plane as a list of 4-byte RGBA entries (only the first `width` entries are meaningful)."""
    plane = palette["planes"][(min(frame, palette["frames"] - 1), level)]
    fmt = palette["format"]
    if fmt == 3:
        entries = [plane[i:i + 4] for i in range(0, len(plane) - 3, 4)]
    elif fmt in (0, 1, 2):
        entries = [bytes(cip.color(v, fmt)) for v in struct.unpack_from(f"<{len(plane) // 2}H", plane)]
    else:
        raise GimError(f"unsupported palette format {FORMATS.get(fmt, fmt)}")
    if len(entries) < palette["width"]:
        raise GimError(f"palette level {level} holds {len(entries)} of {palette['width']} entries")
    return entries[:palette["width"]]


def _lookup(indices, entries):
    """RGBA bytes for an index8 buffer, done per channel with bytes.translate (indices past the palette
    give transparent black)."""
    lut = entries[:256] + [TRANSPARENT] * (256 - min(len(entries), 256))
    out = bytearray(len(indices) * 4)
    for channel in range(4):
        out[channel::4] = indices.translate(bytes(entry[channel] for entry in lut))
    return bytes(out)


LOW = bytes(i & 0xF for i in range(256))
HIGH = bytes(i >> 4 for i in range(256))


def plane_geometry(image, level=0):
    width, height = max(1, image["width"] >> level), max(1, image["height"] >> level)
    bits = BITS.get(image["format"])
    if bits is None:
        raise GimError(f"unsupported image format {FORMATS.get(image['format'], image['format'])}")
    if image["format"] == 8:  # DXT1: 8-byte 4x4 blocks in raster order
        return width, height, (width + 3) // 4 * 8, (height + 3) // 4
    align = image["pitch_align"]
    byte_width = (width * bits + 7) // 8
    byte_width = (byte_width + align - 1) // align * align
    rows = (height + image["height_align"] - 1) // image["height_align"] * image["height_align"]
    return width, height, byte_width, rows


def decode(image, palette=None, frame=0, level=0, clut_level=0):
    """Decode one plane to (width, height, RGBA bytes, notes). `level` is the image level (mipmap),
    `clut_level` the palette level. Notes list non-fatal findings (indices past the palette)."""
    fmt = image["format"]
    width, height, byte_width, rows = plane_geometry(image, level)
    pixels = image["planes"][(frame, level)]
    if len(pixels) < byte_width * rows:
        raise GimError(f"plane ({frame}, {level}) has {len(pixels)} bytes, needs {byte_width * rows}")
    notes = []
    if fmt == 8:
        return width, height, cip.decode_dxt1(pixels, width, height), notes
    pixels = pixels[:byte_width * rows]
    if image["order"] == 1:
        if byte_width % 16 or rows % 8:
            raise GimError(f"swizzled plane of {byte_width} x {rows} bytes is not made of 16x8 tiles")
        pixels = cip.unswizzle(pixels, byte_width, rows)
    if fmt in (4, 5):
        if fmt == 4:
            wide = bytearray(len(pixels) * 2)  # left pixel in the low nibble
            wide[0::2] = pixels.translate(LOW)
            wide[1::2] = pixels.translate(HIGH)
            pixels, byte_width = bytes(wide), byte_width * 2
        indices = b"".join(pixels[y * byte_width:y * byte_width + width] for y in range(height))
        entries = clut(palette, frame, clut_level)
        if max(indices, default=0) >= len(entries):
            notes.append(f"index {max(indices)} past a {len(entries)}-entry palette")
        return width, height, _lookup(indices, entries), notes
    row_bytes = width * BITS[fmt] // 8
    rows_data = b"".join(pixels[y * byte_width:y * byte_width + row_bytes] for y in range(height))
    if fmt == 3:
        return width, height, rows_data, notes
    if fmt in (6, 7):  # index16 / index32: not on this disc, per-pixel fallback
        code = "<H" if fmt == 6 else "<I"
        entries = clut(palette, frame, clut_level)
        step = BITS[fmt] // 8
        out = bytearray()
        for i in range(0, len(rows_data), step):
            index = struct.unpack_from(code, rows_data, i)[0]
            out += entries[index] if index < len(entries) else TRANSPARENT
        return width, height, bytes(out), notes
    out = bytearray()  # 16-bit direct colour: not on this disc, per-pixel fallback
    for (value,) in struct.iter_unpack("<H", rows_data):
        out += bytes(cip.color(value, fmt))
    return width, height, bytes(out), notes


def planes(image, palette):
    """Every (frame, image level, palette level) combination worth writing."""
    cluts = palette["levels"] if palette is not None and image["format"] in (4, 5, 6, 7) else 1
    for frame in range(image["frames"]):
        for level in range(image["levels"]):
            for clut_level in range(cluts):
                yield frame, level, clut_level


def plane_suffix(image, palette, frame, level, clut_level):
    parts = []
    if image["frames"] > 1:
        parts.append(f"f{frame}")
    if image["levels"] > 1:
        parts.append(f"l{level}")
    if palette is not None and palette["levels"] > 1 and image["format"] in (4, 5, 6, 7):
        parts.append(f"c{clut_level}")
    return "".join("_" + p for p in parts)


def describe(image, palette):
    name = FORMATS.get(image["format"], str(image["format"])).lower()
    order = "swizzled" if image["order"] == 1 else "linear"
    text = f"{name} {image['width']}x{image['height']} {order}"
    if image["frames"] > 1:
        text += f", {image['frames']} frames"
    if image["levels"] > 1:
        text += f", {image['levels']} levels"
    if palette is not None:
        text += f", palette {FORMATS.get(palette['format'], palette['format']).lower()} x{palette['width']}"
        if palette["levels"] > 1:
            text += f" x{palette['levels']} levels"
        if palette["frames"] > 1:
            text += f" x{palette['frames']} frames"
    return text


# --- Command line ---------------------------------------------------------------------------------

def output_allowed(path):
    """Game images may only be written outside the repository or under an extracted/ directory."""
    resolved = Path(path).resolve()
    if "extracted" in (part.lower() for part in resolved.parts):
        return True
    try:
        resolved.relative_to(REPO.resolve())
    except ValueError:
        return True
    return False


def gims(paths):
    for label, blob in ehp.walk_paths(paths):
        if blob[:12] == MAGIC:
            yield label, blob


def load_one(path, member):
    if member is None:
        data = ehp.read_file(path)
        if data[:12] != MAGIC:
            raise GimError(f"{path} is not a GIM; name a member")
        return str(path), data
    return ehp.find_leaf(path, member, accept=lambda blob: blob[:12] == MAGIC)


def safe_relative(label):
    parts = [part.replace(":", "_").replace("@", "_at_") for part in label.replace("\\", "/").split("/")]
    return Path(*[p for p in parts if p not in ("", ".", "..")])


def cmd_info(args):
    if args.member is None and (args.file.is_dir() or ehp.read_file(args.file)[:12] != MAGIC):
        items = gims([args.file])
    else:
        items = [load_one(args.file, args.member)]
    for label, blob in items:
        try:
            print(f"{label}: {describe(*parse(blob))}")
        except (GimError, ValueError, struct.error, KeyError) as error:
            print(f"{label}: error: {error}")
    return 0


def cmd_png(args):
    if not output_allowed(args.output):
        print("error: write game images outside the repository or under extracted/", file=sys.stderr)
        return 1
    label, blob = load_one(args.file, args.member)
    image, palette = parse(blob)
    width, height, rgba, notes = decode(image, palette, args.frame, args.level, args.clut)
    cip.write_png(args.output, width, height, rgba)
    for note in notes:
        print(f"note: {note}")
    print(f"wrote {args.output} ({describe(image, palette)}; frame {args.frame}, palette level {args.clut})")
    return 0


def cmd_batch(args):
    if not output_allowed(args.output):
        print("error: write game images outside the repository or under extracted/", file=sys.stderr)
        return 1
    written = failures = 0
    for label, blob in gims(args.paths):
        try:
            image, palette = parse(blob)
            stem = safe_relative(label)
            for frame, level, clut_level in planes(image, palette):
                width, height, rgba, _ = decode(image, palette, frame, level, clut_level)
                suffix = plane_suffix(image, palette, frame, level, clut_level)
                cip.write_png(args.output / stem.with_name(stem.stem + suffix + ".png"), width, height, rgba)
                written += 1
                if args.first:
                    break
        except (GimError, ValueError, struct.error, KeyError, IndexError) as error:
            failures += 1
            print(f"FAIL {label}: {error}")
    print(f"wrote {written} PNG files to {args.output}, {failures} failures")
    return 1 if failures else 0


def cmd_check(args):
    histogram, stats, note_count = Counter(), Counter(), Counter()  # note_count: GIMs with an index past the palette, by format
    failures = 0
    for label, blob in gims(args.paths):
        stats["gim"] += 1
        try:
            image, palette = parse(blob)
            fmt = FORMATS.get(image["format"], str(image["format"])).lower()
            key = f"{fmt} {'swizzled' if image['order'] == 1 else 'linear'}"
            if palette is not None:
                key += f", palette {FORMATS.get(palette['format'], palette['format']).lower()} x{palette['width']}"
            histogram[key] += 1
            stats[f"frames={image['frames']} image levels={image['levels']} palette levels="
                  f"{palette['levels'] if palette else 0} palette frames={palette['frames'] if palette else 0}"] += 1
            noted = False
            for frame, level, clut_level in planes(image, palette):
                _, _, rgba, notes = decode(image, palette, frame, level, clut_level)
                stats["planes decoded"] += 1
                noted = noted or bool(notes)
                for note in notes:
                    if args.verbose:
                        print(f"note {label} {frame}/{level}/{clut_level}: {note}")
            note_count[key] += noted
            stats["ok"] += 1
        except (GimError, ValueError, struct.error, KeyError, IndexError) as error:
            failures += 1
            print(f"FAIL {label}: {error}")
    print("formats:")
    for key, value in sorted(histogram.items(), key=lambda kv: -kv[1]):
        print(f"  {value:>6}  {key}")
    print("planes:")
    for key, value in sorted(stats.items()):
        if key.startswith("frames="):
            print(f"  {value:>6}  {key}")
    print(f"gim {stats['gim']}, ok {stats['ok']}, planes decoded {stats['planes decoded']}, "
          f"images with an index past the palette {sum(note_count.values())}")
    print("OK" if not failures else f"{failures} GIM FAILED")
    return 1 if failures else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Convert GIM textures to PNG; check every GIM decodes.")
    sub = parser.add_subparsers(dest="command", required=True)
    info = sub.add_parser("info", help="describe one GIM, or every GIM of an archive or directory")
    info.add_argument("file", type=Path)
    info.add_argument("member", nargs="?")
    png = sub.add_parser("png", help="write one plane of one GIM as PNG")
    png.add_argument("file", type=Path)
    png.add_argument("member", nargs="?")
    png.add_argument("-o", "--output", type=Path, required=True)
    png.add_argument("--frame", type=int, default=0)
    png.add_argument("--level", type=int, default=0, help="image level (mipmap); every image on this disc has one")
    png.add_argument("--clut", type=int, default=0, help="palette level (alternative palette)")
    batch = sub.add_parser("batch", help="convert every GIM under the given files/directories")
    batch.add_argument("paths", type=Path, nargs="+")
    batch.add_argument("-o", "--output", type=Path, required=True)
    batch.add_argument("--first", action="store_true", help="only frame 0 / palette level 0 of each GIM")
    check = sub.add_parser("check", help="decode every plane of every GIM without writing files")
    check.add_argument("paths", type=Path, nargs="+")
    check.add_argument("-v", "--verbose", action="store_true", help="print each index-past-palette note")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        return {"info": cmd_info, "png": cmd_png, "batch": cmd_batch, "check": cmd_check}[args.command](args)
    except (OSError, GimError, KeyError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
