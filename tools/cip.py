#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""List and decode the card-image containers card/*.cip (magics CIP/CPM/CPL/CPJ). See docs/formats/cip.md.

Examples (write images outside the repository, for example under extracted/):
    python3 -I tools/cip.py list card/cardh_e.cip
    python3 -I tools/cip.py list card/card8_a.cip --check
    python3 -I tools/cip.py png card/card8_a.cip 4007 -o extracted/cip_check/4007.png
    python3 -I tools/cip.py jpeg card/cardj_a.cip --boot PSP_GAME/SYSDIR/BOOT.BIN extracted/cardj --ids 4007
"""

import argparse
import struct
import sys
import zlib
from pathlib import Path

SECTOR = 0x800
HEADER = struct.Struct("<4sIIIIIIII")  # magic, size, 0, 0, dir_end, first_id, last_id, table, sectors/image
HEADER_SIZE = 0x30
ENTRY = struct.Struct("<II")  # sector (or list reference), reserved (always 0)
LIST_FLAG = 0x80000000
MAGICS = {
    b"CIP\x1a": "cardh",  # GIM, DXT1 128x64, per language
    b"CPM\x1a": "cardm",  # headerless DXT1, per language
    b"CPL\x1a": "card8",  # GIM, 8-bit indexed 128x128, shared
    b"CPJ\x1a": "cardj",  # masked 512x512 baseline JPEG, 80 sectors per image, shared
}
RAW_DXT1_SIZE = (64, 64)  # width, height of headerless CPM slots (2,048 bytes of DXT1; see cip.md)


class Cip:
    """A parsed .cip file. `data` must hold at least the directory (the first header.dir_end bytes)."""

    def __init__(self, data):
        (self.magic, self.size, zero0, zero1, self.dir_end, self.first_id, self.last_id,
         self.table, self.sectors_per_image) = HEADER.unpack_from(data, 0)
        if self.magic not in MAGICS:
            raise ValueError(f"unknown magic {self.magic!r}")
        if zero0 or zero1 or any(data[0x24:HEADER_SIZE]):
            raise ValueError("reserved header bytes are not zero")
        if self.table != HEADER_SIZE or self.last_id < self.first_id:
            raise ValueError("unexpected header layout")
        self.data = data
        self.count = self.last_id - self.first_id + 1
        self.image_bytes = self.sectors_per_image * SECTOR

    @property
    def kind(self):
        return MAGICS[self.magic]

    def raw_entry(self, card_id):
        if not self.first_id <= card_id <= self.last_id:
            raise KeyError(card_id)
        return ENTRY.unpack_from(self.data, self.table + ENTRY.size * (card_id - self.first_id))[0]

    def sectors(self, card_id):
        """Start sectors of every image of a card: [] if it has none, several for alternative artworks."""
        value = self.raw_entry(card_id)
        if value == 0:
            return []
        if not value & LIST_FLAG:
            return [value]
        out = []
        offset = value & ~LIST_FLAG
        while True:
            sector = ENTRY.unpack_from(self.data, offset)[0]
            out.append(sector & ~LIST_FLAG)
            if sector & LIST_FLAG:
                return out
            offset += ENTRY.size

    def ids(self):
        return [card_id for card_id in range(self.first_id, self.last_id + 1) if self.raw_entry(card_id)]

    def check(self, file_size=None):
        """Structural checks; returns a list of problems (empty when the file is consistent)."""
        problems = []
        if file_size is not None and self.size != file_size:
            problems.append(f"header size {self.size:#x} != file size {file_size:#x}")
        lists_start = self.table + ENTRY.size * self.count
        terminator = self.dir_end - ENTRY.size
        if self.data[terminator:self.dir_end] != b"\xff" * 8:
            problems.append("directory does not end with the 0xff terminator")
        used = []
        for card_id in self.ids():
            value = self.raw_entry(card_id)
            if value & LIST_FLAG and not lists_start <= value & ~LIST_FLAG < terminator:
                problems.append(f"id {card_id}: list reference {value:#x} outside the list area")
                continue
            used += self.sectors(card_id)
        first = (self.dir_end + SECTOR - 1) // SECTOR
        expected = list(range(first, self.size // SECTOR, self.sectors_per_image))
        if used != expected:
            problems.append(f"images are not contiguous in id order ({len(used)} used, {len(expected)} slots)")
        return problems


# --- GIM ------------------------------------------------------------------------------------------

GIM_MAGIC = b"MIG.00.1PSP\0"
GIM_FORMATS = {0: "RGBA5650", 1: "RGBA5551", 2: "RGBA4444", 3: "RGBA8888", 4: "INDEX4", 5: "INDEX8",
               6: "INDEX16", 7: "INDEX32", 8: "DXT1", 9: "DXT3", 10: "DXT5"}


def gim_blocks(data):
    """Yield (block id, block offset, block size) for every block of a GIM, depth first."""
    if data[:12] != GIM_MAGIC:
        raise ValueError("not a GIM file")

    def walk(start, end):
        pos = start
        while pos + 0x10 <= end:
            block_id, _, size, _, child = struct.unpack_from("<HHIII", data, pos)
            if size < 0x10:
                break
            yield block_id, pos, size
            if block_id in (2, 3):  # root and picture blocks contain other blocks
                yield from walk(pos + child, min(pos + size, end))
            pos += size

    yield from walk(0x10, len(data))


def gim_surface(data, block_offset):
    """Parse an image (4) or palette (5) block: returns a dict with format, order, size and pixel bytes."""
    head = block_offset + struct.unpack_from("<I", data, block_offset + 12)[0]
    (_, _, fmt, order, width, height, bpp, pitch_align, height_align) = struct.unpack_from("<9H", data, head)
    start, end = struct.unpack_from("<II", data, head + 0x1C)
    return {"format": fmt, "order": order, "width": width, "height": height, "bpp": bpp,
            "pitch_align": pitch_align, "height_align": height_align,
            "pixels": data[head + start:head + end]}


def read_gim(data):
    """Return (image, palette or None) surfaces of the first picture in a GIM."""
    image = palette = None
    for block_id, offset, _ in gim_blocks(data):
        if block_id == 4 and image is None:
            image = gim_surface(data, offset)
        elif block_id == 5 and palette is None:
            palette = gim_surface(data, offset)
    if image is None:
        raise ValueError("GIM has no image block")
    return image, palette


# --- Pixel decoding -------------------------------------------------------------------------------

def unswizzle(pixels, byte_width, rows):
    """Undo the PSP swizzle: the texture is stored as 16-byte x 8-row tiles in row-major tile order."""
    out = bytearray(byte_width * rows)
    tiles_per_row = byte_width // 16
    src = 0
    for tile_y in range(0, rows, 8):
        for tile_x in range(tiles_per_row):
            for y in range(tile_y, min(tile_y + 8, rows)):
                dst = y * byte_width + tile_x * 16
                out[dst:dst + 16] = pixels[src:src + 16]
                src += 16
            src += 16 * max(0, tile_y + 8 - rows)
    return bytes(out)


def color(value, fmt):
    """One PSP colour as (r, g, b, a); red is in the low bits for every format."""
    if fmt == 0:
        return ((value & 0x1F) * 255 // 31, (value >> 5 & 0x3F) * 255 // 63, (value >> 11) * 255 // 31, 255)
    if fmt == 1:
        return ((value & 0x1F) * 255 // 31, (value >> 5 & 0x1F) * 255 // 31, (value >> 10 & 0x1F) * 255 // 31,
                255 if value >> 15 else 0)
    if fmt == 2:
        return tuple((value >> shift & 0xF) * 17 for shift in (0, 4, 8, 12))
    if fmt == 3:
        return (value & 0xFF, value >> 8 & 0xFF, value >> 16 & 0xFF, value >> 24)
    raise ValueError(f"not a colour format: {fmt}")


def palette_colors(palette):
    size = 4 if palette["format"] == 3 else 2
    raw = palette["pixels"]
    code = "<I" if size == 4 else "<H"
    return [color(struct.unpack_from(code, raw, i)[0], palette["format"]) for i in range(0, len(raw) - size + 1, size)]


def rgb565(value):
    """DXT endpoint colour: standard RGB565 with red in the HIGH bits (unlike the GE's 5650 texel format)."""
    return ((value >> 11) * 255 // 31, (value >> 5 & 0x3F) * 255 // 63, (value & 0x1F) * 255 // 31, 255)


def decode_dxt1(pixels, width, height):
    """PSP DXT1: 8-byte blocks in raster order, each `u32 indices` (2 bits per pixel, LSB first) then two
    RGB565 colours. Returns RGBA rows."""
    rgba = bytearray(width * height * 4)
    blocks_x = (width + 3) // 4
    for block in range((height + 3) // 4 * blocks_x):
        offset = block * 8
        if offset + 8 > len(pixels):
            break  # truncated slot (cardh): leave the rest transparent
        bits, c0, c1 = struct.unpack_from("<IHH", pixels, offset)
        p0, p1 = rgb565(c0), rgb565(c1)
        if c0 > c1:
            p2 = tuple((2 * a + b) // 3 for a, b in zip(p0, p1))
            p3 = tuple((a + 2 * b) // 3 for a, b in zip(p0, p1))
        else:
            p2 = tuple((a + b) // 2 for a, b in zip(p0, p1))
            p3 = (0, 0, 0, 0)
        table = (p0, p1, p2, p3)
        bx, by = block % blocks_x * 4, block // blocks_x * 4
        for i in range(16):
            x, y = bx + i % 4, by + i // 4
            if x < width and y < height:
                pos = (y * width + x) * 4
                rgba[pos:pos + 4] = bytes(table[bits >> (2 * i) & 3])
    return bytes(rgba)


def decode_surface(image, palette=None, opaque=True):
    """Decode a GIM image surface to RGBA bytes (width x height)."""
    fmt, width, height = image["format"], image["width"], image["height"]
    if fmt == 8:
        return decode_dxt1(image["pixels"], width, height)
    bits = {0: 16, 1: 16, 2: 16, 3: 32, 4: 4, 5: 8}.get(fmt)
    if bits is None:
        raise ValueError(f"unsupported GIM format {GIM_FORMATS.get(fmt, fmt)}")
    pitch_align = max(image["pitch_align"], 1)
    byte_width = (width * bits // 8 + pitch_align - 1) // pitch_align * pitch_align
    rows = (height + max(image["height_align"], 1) - 1) // max(image["height_align"], 1) * max(image["height_align"], 1)
    pixels = image["pixels"].ljust(byte_width * rows, b"\0")
    if image["order"] == 1:
        pixels = unswizzle(pixels, byte_width, rows)
    lut = palette_colors(palette) if fmt in (4, 5) else None
    rgba = bytearray()
    for y in range(height):
        row = pixels[y * byte_width:(y + 1) * byte_width]
        for x in range(width):
            if fmt == 5:
                px = lut[row[x]]
            elif fmt == 4:
                px = lut[row[x // 2] >> (4 * (x & 1)) & 0xF]
            elif fmt == 3:
                px = color(struct.unpack_from("<I", row, 4 * x)[0], 3)
            else:
                px = color(struct.unpack_from("<H", row, 2 * x)[0], fmt)
            rgba += bytes(px[:3]) + (b"\xff" if opaque else bytes(px[3:]))
    return bytes(rgba)


def write_png(path, width, height, rgba):
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

    raw = b"".join(b"\0" + rgba[y * width * 4:(y + 1) * width * 4] for y in range(height))
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(png)


# --- CPJ masked JPEG ------------------------------------------------------------------------------
# The game unmasks a CPJ slot in its .cip read-completion callback (BOOT.BIN 0x0883d658, module offset
# 0x39658; see docs/formats/cip.md). The 160-byte JPEG head is not in the slot: the game copies
# it from its own data (module address 0x9d3d8), XOR 0x5c, over the slot's first 160 bytes; the seed of
# the byte generator is the big-endian u16 at slot offset 0x9e, read before that copy.

CPJ_HEAD_SIZE = 160
CPJ_HEAD_XOR = 0x5C
CPJ_SEED_OFFSET = 0x9E
CPJ_MUL, CPJ_ADD = 0xC6A1, 0x0D0F
CPJ_HEAD_ADDRESS = 0x9D3D8  # module-relative address of the stored head in BOOT.BIN (EU)
JPEG_HEAD = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00"


def cpj_mask(seed, length):
    """The generator's `length` mask bytes: s = ((s * 0xc6a1 + 0xd0f) >> 1) & 0xffff; byte = s >> 2 & 0xff."""
    out = bytearray(length)
    s = seed & 0xFFFF
    for i in range(length):
        s = (s * CPJ_MUL + CPJ_ADD) >> 1 & 0xFFFF
        out[i] = s >> 2 & 0xFF
    return bytes(out)


def xor_bytes(data, mask):
    return (int.from_bytes(data, "little") ^ int.from_bytes(mask, "little")).to_bytes(len(data), "little")


def cpj_unmask(slot, stored_head):
    """Return the unmasked slot (JPEG followed by fill), as the game leaves it in memory.
    `stored_head` is the 160 bytes as stored in BOOT.BIN (still XOR-ed with 0x5c)."""
    if len(stored_head) != CPJ_HEAD_SIZE:
        raise ValueError("the stored CPJ head must be 160 bytes")
    seed = slot[CPJ_SEED_OFFSET] << 8 | slot[CPJ_SEED_OFFSET + 1]
    head = bytes(b ^ CPJ_HEAD_XOR for b in stored_head)
    body = slot[CPJ_HEAD_SIZE:]
    return head + xor_bytes(body, cpj_mask(seed, len(body)))


def cpj_mask_slot(jpeg_and_fill, seed, filler=b""):
    """Inverse of cpj_unmask for tests and tools: mask bytes 160.. and put `seed` at 0x9e (the other 158 head
    bytes of a slot are not used by the game; `filler` supplies them, zeros by default)."""
    body = jpeg_and_fill[CPJ_HEAD_SIZE:]
    head = bytearray(filler[:CPJ_HEAD_SIZE].ljust(CPJ_HEAD_SIZE, b"\0"))
    head[CPJ_SEED_OFFSET:CPJ_SEED_OFFSET + 2] = struct.pack(">H", seed)
    return bytes(head) + xor_bytes(body, cpj_mask(seed, len(body)))


def jpeg_length(data):
    """Length of the JPEG at the start of `data` up to and including EOI (markers, then entropy data)."""
    if data[:2] != b"\xff\xd8":
        raise ValueError("not a JPEG (no SOI)")
    pos = 2
    while pos + 4 <= len(data):
        if data[pos] != 0xFF:
            raise ValueError(f"bad JPEG marker at {pos:#x}")
        marker = data[pos + 1]
        if marker == 0xFF:
            pos += 1
            continue
        if marker == 0xD9:
            return pos + 2
        length = struct.unpack_from(">H", data, pos + 2)[0]
        pos += 2 + length
        if marker == 0xDA:  # entropy-coded data follows: FF00 is a stuffed byte, FFD0-FFD7 are restarts
            while True:
                pos = data.index(b"\xff", pos)
                following = data[pos + 1]
                if following == 0 or 0xD0 <= following <= 0xD7:
                    pos += 2
                else:
                    break
    raise ValueError("JPEG has no EOI")


def cpj_stored_head(boot):
    """The stored 160-byte head from the maintainer's BOOT.BIN: at CPJ_HEAD_ADDRESS, or else searched for in
    the file (any 160 bytes that unmask to a JFIF start), checked before use."""
    data = boot if isinstance(boot, (bytes, bytearray)) else Path(boot).read_bytes()
    masked_start = bytes(b ^ CPJ_HEAD_XOR for b in JPEG_HEAD)
    candidates = []
    try:
        candidates.append(elf_offset(data, CPJ_HEAD_ADDRESS))
    except ValueError:
        pass
    found = data.find(masked_start)
    if found >= 0:
        candidates.append(found)
    for offset in candidates:
        head = data[offset:offset + CPJ_HEAD_SIZE]
        if head.startswith(masked_start) and len(head) == CPJ_HEAD_SIZE:
            return head
    raise ValueError("no stored CPJ head (JFIF XOR 0x5c) found in the executable")


def elf_offset(data, pointer):
    """File offset of a module-relative pointer in a PRX (allocated sections from the ELF section headers)."""
    if data[:4] != b"\x7fELF":
        raise ValueError("not an ELF file")
    shoff, = struct.unpack_from("<I", data, 0x20)
    entsize, count = struct.unpack_from("<HH", data, 0x2E)
    for i in range(count):
        _, kind, flags, addr, off, size = struct.unpack_from("<IIIIII", data, shoff + i * entsize)
        if flags & 2 and kind != 8 and addr <= pointer < addr + size:  # SHF_ALLOC, not NOBITS
            return off + pointer - addr
    raise ValueError(f"pointer {pointer:#x} is outside every allocated section")


def decode_slot(cip, slot, raw_size=RAW_DXT1_SIZE):
    """Decode one image slot to (width, height, rgba)."""
    if cip.kind == "cardj":
        raise ValueError("CPJ slots are masked JPEGs; use the `jpeg` command (see docs/formats/cip.md)")
    if cip.kind == "cardm":
        width, height = raw_size
        return width, height, decode_dxt1(slot, width, height)
    image, palette = read_gim(slot.ljust(slot_gim_size(slot), b"\0"))
    return image["width"], image["height"], decode_surface(image, palette, opaque=True)


def slot_gim_size(slot):
    """Size the GIM claims (header + root block); cardh slots are 0x80 bytes shorter than their GIM."""
    if slot[:12] != GIM_MAGIC:
        return len(slot)
    return max(len(slot), 0x10 + struct.unpack_from("<I", slot, 0x14)[0])


def open_cip(path):
    with open(path, "rb") as handle:
        head = handle.read(HEADER_SIZE)
        dir_end = HEADER.unpack_from(head, 0)[4]
        handle.seek(0)
        return Cip(handle.read(dir_end))


def read_slot(path, cip, sector):
    with open(path, "rb") as handle:
        handle.seek(sector * SECTOR)
        return handle.read(cip.image_bytes)


def write_jpegs(args, cip):
    """`jpeg` command: <outdir>/<id>.jpg for artwork 0, <id>_<n>.jpg for alternative artwork n."""
    if cip.kind != "cardj":
        print(f"{args.file.name} is not a CPJ file", file=sys.stderr)
        return 1
    head = cpj_stored_head(args.boot)
    args.outdir.mkdir(parents=True, exist_ok=True)
    written = 0
    with open(args.file, "rb") as handle:
        for card_id in args.ids or cip.ids():
            for art, sector in enumerate(cip.sectors(card_id)):
                if args.limit is not None and written >= args.limit:
                    return 0
                handle.seek(sector * SECTOR)
                data = cpj_unmask(handle.read(cip.image_bytes), head)
                if not args.full:
                    data = data[:jpeg_length(data)]
                name = f"{card_id:05d}.jpg" if art == 0 else f"{card_id:05d}_{art}.jpg"
                (args.outdir / name).write_bytes(data)
                written += 1
    print(f"wrote {written} images to {args.outdir}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="List and decode card/*.cip card-image containers.")
    sub = parser.add_subparsers(dest="command", required=True)
    lister = sub.add_parser("list", help="print one line per card id that has images")
    lister.add_argument("file", type=Path)
    lister.add_argument("--check", action="store_true", help="only run the structural checks")
    png = sub.add_parser("png", help="decode one image of a card to PNG (keep the output out of git)")
    png.add_argument("file", type=Path)
    png.add_argument("card_id", type=int)
    png.add_argument("--art", type=int, default=0, help="alternative artwork number (default 0)")
    png.add_argument("--size", default="%dx%d" % RAW_DXT1_SIZE, help="WxH for headerless CPM slots")
    png.add_argument("-o", "--output", type=Path, required=True)
    jpeg = sub.add_parser("jpeg", help="unmask CPJ slots to JPEG files (keep the output out of git)")
    jpeg.add_argument("file", type=Path)
    jpeg.add_argument("outdir", type=Path)
    jpeg.add_argument("--boot", type=Path, required=True, help="the game's BOOT.BIN (holds the 160-byte head)")
    jpeg.add_argument("--ids", nargs="+", type=int, help="only these card ids (default: every id with art)")
    jpeg.add_argument("--limit", type=int, help="stop after this many images")
    jpeg.add_argument("--full", action="store_true", help="write the whole unmasked slot, fill included")
    args = parser.parse_args(argv)

    cip = open_cip(args.file)
    if args.command == "jpeg":
        return write_jpegs(args, cip)
    if args.command == "list":
        if args.check:
            problems = cip.check(args.file.stat().st_size)
            for problem in problems:
                print(problem)
            ids = cip.ids()
            images = sum(len(cip.sectors(i)) for i in ids)
            print(f"{args.file.name}: {cip.magic[:3].decode()} ids {cip.first_id}-{cip.last_id}, {len(ids)} with images, "
                  f"{images} images of {cip.sectors_per_image} sectors: {'OK' if not problems else 'FAILED'}")
            return 1 if problems else 0
        print("id,images,sectors")
        for card_id in cip.ids():
            print(f"{card_id},{len(cip.sectors(card_id))},{' '.join(hex(s) for s in cip.sectors(card_id))}")
        return 0
    sectors = cip.sectors(args.card_id)
    if not sectors:
        print(f"card id {args.card_id} has no image in {args.file.name}", file=sys.stderr)
        return 1
    slot = read_slot(args.file, cip, sectors[args.art])
    width, height = (int(v) for v in args.size.lower().split("x"))
    w, h, rgba = decode_slot(cip, slot, (width, height))
    write_png(args.output, w, h, rgba)
    print(f"wrote {args.output} ({w}x{h})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
