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
