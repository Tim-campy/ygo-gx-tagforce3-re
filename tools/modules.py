#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Catalogue the game's PRX modules (gmodule/*.prx, module/*.prx) and how their imports resolve.

  modules.py list BOOT.BIN gmodule/ module/ [--check]   # one block per module (see below)
  modules.py table BOOT.BIN [--present gmodule/ ...]   # BOOT.BIN's module descriptor tables
  modules.py base symbols.sym gmodule/ [...]            # vote each module's runtime base (PPSSPP export)

`list` prints, per module: file size, module-info name/attribute/version, entry point, allocated sections,
export libraries (function/variable counts), import libraries with how many NIDs resolve and against whom
(BOOT.BIN's `libehsys_rel` or another game module's `lib*_rel`; Sony libraries are reported as `system`).
`--check` fails when a game-library import does not resolve. Encrypted modules (`~SCE`/`~PSP`) are only
identified from their plain header and never decrypted.

`base` derives function starts from each module's own code (targets of `jal` inside `.text`) and votes
`base = symbol address - offset` over the symbol export, as in docs/subsystems/duel_effects.md.
See docs/subsystems/modules.md.
"""

import argparse
import importlib.util
import struct
import sys
from collections import Counter
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_prx_imports", Path(__file__).resolve().parent / "prx_imports.py")
prx_imports = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prx_imports)
Elf = prx_imports.Elf
BOOT_BASE = prx_imports.BOOT_BASE
GAME_LIBRARY = "libehsys_rel"


def libraries(elf, section):
    """[(name, fcount, vcount, nids)] of the .lib.ent or .lib.stub table; name is None for the module itself."""
    if section not in elf.sections:
        return []
    out = []
    for entry in elf.library_entries(section, lambda p: 4 * elf.data[elf.offset(p) + 8]):
        off = elf.offset(entry)
        name_ptr, = struct.unpack_from("<I", elf.data, off)
        vcount = elf.data[off + 9]
        fcount, = struct.unpack_from("<H", elf.data, off + 10)
        table, = struct.unpack_from("<I", elf.data, off + 12)
        if section == ".lib.ent":
            total = fcount + vcount
            nids = list(elf.u32(table, total)[:fcount]) if total else []
        else:
            nids = list(elf.u32(table, fcount)) if fcount else []
        out.append((elf.string(name_ptr) if name_ptr else None, fcount, vcount, nids))
    return out


def module_info(elf):
    """(name, attribute, version, gp) from .rodata.sceModuleInfo, or None."""
    sec = elf.sections.get(".rodata.sceModuleInfo")
    if sec is None:
        return None
    off = sec[4]
    attr, version = struct.unpack_from("<HH", elf.data, off)
    name = elf.data[off + 4:off + 32].split(b"\0")[0].decode("ascii", "replace")
    gp, = struct.unpack_from("<I", elf.data, off + 32)
    return name, attr, version, gp


def psp_header(data):
    """Plain header fields of an encrypted ~SCE/~PSP module: (name, attribute, compression, elf_size, psp_size)."""
    base = 0x40 if data[:4] == b"~SCE" else 0
    if data[base:base + 4] != b"~PSP":
        return None
    attr, comp = struct.unpack_from("<HH", data, base + 4)
    name = data[base + 0x0A:base + 0x26].split(b"\0")[0].decode("ascii", "replace")
    elf_size, psp_size = struct.unpack_from("<II", data, base + 0x28)
    return name, attr, comp, elf_size, psp_size


# ----------------------------------------------------------------- plain ELF module codec (gmodule_prx)

ELF_HEADER = struct.Struct("<16sHHIIIIIHHHHHH")
ELF_HEADER_FIELDS = ("ident", "type", "machine", "version", "entry", "phoff", "shoff", "flags", "ehsize",
                     "phentsize", "phnum", "shentsize", "shnum", "shstrndx")
PROGRAM_FIELDS = ("type", "offset", "vaddr", "paddr", "filesz", "memsz", "flags", "align")
SECTION_FIELDS = ("name_offset", "type", "flags", "addr", "offset", "size", "link", "info", "addralign", "entsize")
SHT_NOBITS = 8
SHT_PSP_REL = 0x700000A0  # PSP relocation section: 8-byte entries {u32 offset, u32 info}


def _runs(raw, start=0):
    """[(offset, hex)] of the non-zero runs of raw (offsets relative to `start`)."""
    out, pos = [], 0
    while pos < len(raw):
        if raw[pos]:
            end = pos
            while end < len(raw) and raw[end]:
                end += 1
            out.append((start + pos, raw[pos:end].hex()))
            pos = end
        else:
            pos += 1
    return out


def elf_decode(data):
    """Plain PRX (ELF) -> {header, program_headers, sections, gaps, size}. Each section keeps its header fields,
    its name and its contents: PSP relocation sections as [offset, type, offset_base, address_base, high] per
    entry (info byte 0 = relocation type, byte 1 = segment of the offset, byte 2 = segment of the address),
    other sections as bytes. `gaps` holds the non-zero bytes no header or section claims (alignment padding is
    zero in every module of the disc). elf_build() inverts it byte for byte."""
    if data[:4] != b"\x7fELF":
        raise ValueError("not a plain ELF module")
    header = dict(zip(ELF_HEADER_FIELDS, ELF_HEADER.unpack_from(data, 0)))
    header["ident"] = header["ident"].hex()
    claimed = [(0, ELF_HEADER.size)]
    programs = [dict(zip(PROGRAM_FIELDS, struct.unpack_from("<8I", data, header["phoff"] + i * header["phentsize"])))
                for i in range(header["phnum"])]
    claimed.append((header["phoff"], header["phnum"] * header["phentsize"]))
    raw_sections = [dict(zip(SECTION_FIELDS, struct.unpack_from("<10I", data,
                                                                header["shoff"] + i * header["shentsize"])))
                    for i in range(header["shnum"])]
    claimed.append((header["shoff"], header["shnum"] * header["shentsize"]))
    names = raw_sections[header["shstrndx"]]
    sections = []
    for sec in raw_sections:
        entry = dict(sec)
        entry["name"] = prx_imports_cstring(data, names["offset"] + sec["name_offset"]) if sec["type"] else ""
        if sec["type"] != SHT_NOBITS and sec["size"]:
            body = data[sec["offset"]:sec["offset"] + sec["size"]]
            claimed.append((sec["offset"], sec["size"]))
            if sec["type"] == SHT_PSP_REL and sec["size"] % 8 == 0:
                entry["relocations"] = [[off, info & 0xFF, info >> 8 & 0xFF, info >> 16 & 0xFF, info >> 24]
                                        for off, info in struct.iter_unpack("<II", body)]
            else:
                entry["data"] = body
        sections.append(entry)
    covered = bytearray(len(data))
    for start, size in claimed:
        covered[start:start + size] = b"\1" * size
    gaps = [(offset, raw) for offset, raw in _runs(bytes(b if not c else 0 for b, c in zip(data, covered)))]
    return {"header": header, "program_headers": programs, "sections": sections, "gaps": gaps, "size": len(data)}


def prx_imports_cstring(data, offset):
    return data[offset:data.index(b"\0", offset)].decode("ascii")


def elf_build(model):
    """Inverse of elf_decode(): headers, section contents at their offsets, then the non-zero gap bytes."""
    out = bytearray(model["size"])
    header = dict(model["header"])
    header["ident"] = bytes.fromhex(header["ident"])
    ELF_HEADER.pack_into(out, 0, *(header[f] for f in ELF_HEADER_FIELDS))
    for i, program in enumerate(model["program_headers"]):
        struct.pack_into("<8I", out, header["phoff"] + i * header["phentsize"], *(program[f] for f in PROGRAM_FIELDS))
    for i, sec in enumerate(model["sections"]):
        struct.pack_into("<10I", out, header["shoff"] + i * header["shentsize"], *(sec[f] for f in SECTION_FIELDS))
        if "relocations" in sec:
            body = b"".join(struct.pack("<II", off, kind | ofs << 8 | addr << 16 | high << 24)
                            for off, kind, ofs, addr, high in sec["relocations"])
        else:
            body = sec.get("data", b"")
        if len(body) != (sec["size"] if "relocations" in sec or "data" in sec else 0):
            raise ValueError(f"section {sec['name']}: {len(body)} content bytes for size {sec['size']}")
        out[sec["offset"]:sec["offset"] + len(body)] = body
    for offset, raw in model["gaps"]:
        chunk = bytes.fromhex(raw)
        out[offset:offset + len(chunk)] = chunk
    return bytes(out)


class Module:
    """One PRX file: parsed ELF (elf is None when encrypted) and its library tables."""

    def __init__(self, name, data):
        self.name, self.size = name, len(data)
        self.elf = self.header = None
        self.exports, self.imports = [], []
        if data[:4] == b"\x7fELF":
            self.elf = Elf(data, 0)
            self.exports = libraries(self.elf, ".lib.ent")
            self.imports = libraries(self.elf, ".lib.stub")
        else:
            self.header = psp_header(data)

    def entry(self):
        return struct.unpack_from("<I", self.elf.data, 0x18)[0]


def provider_index(boot, modules):
    """{library: (provider, set of exported function NIDs)}; BOOT.BIN first, then every ELF module."""
    index = {}
    for provider, libs in [("BOOT.BIN", libraries(boot, ".lib.ent"))] + [(m.name, m.exports) for m in modules]:
        for lib, _, _, nids in libs:
            if lib is not None:
                index.setdefault(lib, (provider, set()))[1].update(nids)
    return index


def resolve(module, index):
    """[(library, imported, resolved, provider or 'system')] for each import library of a module."""
    out = []
    for lib, fcount, _, nids in module.imports:
        if lib in index:
            provider, exported = index[lib]
            out.append((lib, fcount, sum(1 for n in nids if n in exported), provider))
        else:
            out.append((lib, fcount, 0, "system"))
    return out


def load_modules(paths):
    files = []
    for path in paths:
        files += sorted(path.glob("*.prx")) if path.is_dir() else [path]
    return [Module(f.name, f.read_bytes()) for f in files]


def describe(module, index):
    """Text block for `list`; also returns the list of problems found."""
    lines, problems = [f"{module.name}  {module.size} bytes"], []
    if module.elf is None:
        if module.header:
            name, attr, comp, elf_size, psp_size = module.header
            lines.append(f"  encrypted ~PSP module '{name}' attr {attr:#06x} compression {comp:#x} "
                         f"elf_size {elf_size} psp_size {psp_size} (not decrypted)")
        else:
            lines.append("  not an ELF and no ~PSP header")
        return lines, problems
    info = module_info(module.elf)
    if info:
        lines.append(f"  module info '{info[0]}' attr {info[1]:#06x} version {info[2] >> 8}.{info[2] & 0xff} "
                     f"gp {info[3]:#x}; entry {module.entry():#x}")
    secs = [(n, h) for n, h in module.elf.sections.items() if h[2] & 2 and h[5]]
    lines.append("  sections " + ", ".join(f"{n} {h[3]:#x}+{h[5]:#x}" for n, h in sorted(secs, key=lambda s: s[1][3])))
    for lib, fcount, vcount, _ in module.exports:
        lines.append(f"  export {lib or '(module)'}: {fcount} functions, {vcount} variables")
    for lib, imported, resolved, provider in resolve(module, index):
        lines.append(f"  import {lib}: {imported} functions, {resolved} resolved in {provider}")
        if provider != "system" and resolved != imported:
            problems.append(f"{module.name}: {imported - resolved} of {imported} {lib} imports do not resolve in {provider}")
    return lines, problems


def descriptor_tables(boot):
    """[(address, [(id, root, name, word3)])] runs of 16-byte {id, root, name pointer, word} records naming .prx files."""
    _, _, _, addr, off, size = boot.sections[".data"]
    data = boot.data
    count = size // 4
    words = struct.unpack_from(f"<{count}I", data, off)

    def prx_name(pointer):
        try:
            text = boot.string(pointer)
        except (ValueError, UnicodeDecodeError):
            return None
        return text if text.endswith(".prx") else None

    tables, i = [], 0
    while i + 3 < count:
        rows, j = [], i
        while j + 3 < count:
            ident, root, name_ptr, word3 = words[j:j + 4]
            root = root - (1 << 32) if root & 0x80000000 else root
            name = prx_name(name_ptr) if ident < 0x100 and -2 <= root < 0x40 else None
            if name is None:
                break
            rows.append((ident, root, name, word3))
            j += 4
        if len(rows) >= 2:
            tables.append((boot.base + addr + 4 * i, rows))
            i = j
        else:
            i += 1
    return tables


# --- writers (round trip, tools/roundtrip.py) -----------------------------------------------------------------

DESCRIPTOR_TABLES = (0x0889F57C, 0x0889FEA4)  # Sony modules (ids 1-7), game modules (ids 8-0x31)
DESCRIPTOR = struct.Struct("<IiIHH")  # id, root, name pointer (module offset), kind, utility id
SCENE_TABLE, SCENE_COUNT = 0x088A1478, 31  # {u32 scene id, u32 module id}


def read_descriptors(boot, address):
    """Records of one descriptor table up to its zero record: {id, root, name pointer, name, kind, utility}."""
    rows, pointer = [], address - BOOT_BASE
    while True:
        ident, root, name_ptr, kind, utility = DESCRIPTOR.unpack_from(boot.data, boot.offset(pointer))
        if not (ident or root or name_ptr or kind or utility):
            return rows
        rows.append({"id": ident, "root": root, "name_ptr": name_ptr, "name": boot.string(name_ptr),
                     "kind": kind, "utility": utility})
        pointer += DESCRIPTOR.size


def descriptor_spans(boot, address, rows):
    """The records, the zero record and each NUL-terminated name."""
    spans = [(boot.offset(address - BOOT_BASE), DESCRIPTOR.size * (len(rows) + 1))]
    spans += [(boot.offset(r["name_ptr"]), len(r["name"]) + 1) for r in rows]
    return spans


def write_descriptors(data, model):
    """model: {table address: rows}. Writes records, a zero record and the names at their pointers."""
    boot = prx_imports.Elf(data, BOOT_BASE)
    out = bytearray(data)
    for address, rows in model.items():
        start = boot.offset(address - BOOT_BASE)
        for k, r in enumerate(rows + [None]):
            values = (0, 0, 0, 0, 0) if r is None else (r["id"], r["root"], r["name_ptr"], r["kind"], r["utility"])
            DESCRIPTOR.pack_into(out, start + DESCRIPTOR.size * k, *values)
            if r is not None:
                name = r["name"].encode("ascii") + b"\0"
                out[boot.offset(r["name_ptr"]):boot.offset(r["name_ptr"]) + len(name)] = name
    return bytes(out)


def read_scene_table(boot):
    """[(scene id, module id)] x 31."""
    start = boot.offset(SCENE_TABLE - BOOT_BASE)
    return [struct.unpack_from("<2I", boot.data, start + 8 * k) for k in range(SCENE_COUNT)]


def write_scene_table(data, pairs):
    boot = prx_imports.Elf(data, BOOT_BASE)
    out = bytearray(data)
    start = boot.offset(SCENE_TABLE - BOOT_BASE)
    for k, pair in enumerate(pairs):
        struct.pack_into("<2I", out, start + 8 * k, *pair)
    return bytes(out)


def vote_base(text, text_addr, symbols, sample=150):
    """(base, starts matched, starts total) for the base that best aligns a module's jal targets with symbols."""
    words = struct.unpack_from(f"<{len(text) // 4}I", text)
    starts = sorted({(w & 0x3FFFFFF) << 2 for w in words
                     if w >> 26 == 3 and text_addr <= (w & 0x3FFFFFF) << 2 < text_addr + len(text)})
    if not starts or not symbols:
        return None, 0, len(starts)
    votes = Counter()
    for offset in starts[::max(1, len(starts) // sample)]:
        for address in symbols:
            votes[address - offset] += 1
    best = max(((sum(1 for o in starts if b + o in symbols), b) for b, _ in votes.most_common(5)))
    return best[1], best[0], len(starts)


def read_symbols(path):
    """{address: size} from a PPSSPP symbol export (`ADDR name,SIZE` per line)."""
    out = {}
    for line in open(path, encoding="utf-8", errors="replace"):
        parts = line.strip().split(" ", 1)
        if len(parts) == 2 and "," in parts[1]:
            try:
                out[int(parts[0], 16)] = int(parts[1].rsplit(",", 1)[1], 16)
            except ValueError:
                continue
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description="Catalogue PRX modules and their library links.")
    sub = parser.add_subparsers(dest="command", required=True)
    p_list = sub.add_parser("list", help="per-module sections, module info, exports and imports")
    p_list.add_argument("boot", type=Path)
    p_list.add_argument("paths", type=Path, nargs="+", help="module files or directories")
    p_list.add_argument("--check", action="store_true", help="exit 1 when a game-library import does not resolve")
    p_table = sub.add_parser("table", help="module descriptor tables in BOOT.BIN")
    p_table.add_argument("boot", type=Path)
    p_table.add_argument("--present", type=Path, nargs="*", default=[], help="directories to look the files up in")
    p_base = sub.add_parser("base", help="vote runtime bases against a PPSSPP symbol export")
    p_base.add_argument("symbols", type=Path)
    p_base.add_argument("paths", type=Path, nargs="+")
    p_base.add_argument("--min", type=float, default=0.9, help="fraction of matched starts to call a base found")
    args = parser.parse_args(argv)

    if args.command == "list":
        boot = Elf(args.boot.read_bytes(), BOOT_BASE)
        modules = load_modules(args.paths)
        index = provider_index(boot, modules)
        problems = []
        for module in modules:
            lines, found = describe(module, index)
            print("\n".join(lines))
            problems += found
        print(f"{len(modules)} modules, {sum(1 for m in modules if m.elf is None)} encrypted, "
              f"{len(problems)} problems", file=sys.stderr)
        for problem in problems:
            print("  " + problem, file=sys.stderr)
        return 1 if args.check and problems else 0

    if args.command == "table":
        boot = Elf(args.boot.read_bytes(), BOOT_BASE)
        present = {f.name for d in args.present for f in d.glob("*.prx")}
        for address, rows in descriptor_tables(boot):
            print(f"table at {address:#010x}: {len(rows)} records")
            for ident, root, name, word3 in rows:
                mark = "" if not args.present else ("  present" if name in present else "  MISSING")
                print(f"  id {ident:#04x} root {root:2d} kind {word3 & 0xffff:#06x} util {word3 >> 16:#06x}  {name}{mark}")
        return 0

    symbols = read_symbols(args.symbols)
    for module in load_modules(args.paths):
        if module.elf is None:
            print(f"{module.name:24s} encrypted, skipped")
            continue
        _, _, _, addr, off, size = module.elf.sections[".text"]
        base, matched, total = vote_base(module.elf.data[off:off + size], addr, symbols)
        found = total and matched >= args.min * total
        verdict = f"base {base:#010x}" if found else "not in this export"
        best = f"best {base:#010x}" if base is not None else "no candidate"
        print(f"{module.name:24s} {verdict:22s} ({matched}/{total} function starts; {best})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
