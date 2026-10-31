#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Resolve a game module's imports against BOOT.BIN's exported library and name the import stubs.

BOOT.BIN exports the library "libehsys_rel" (resolved by NID); modules such as rel_duel_eng.prx import
from it. Each import stub is named "thunk_<target name>" in the target's group, an ApplyNames.java CSV:

  prx_imports.py BOOT.BIN gmodule/rel_duel_eng.prx 09be1400 re/functions.csv > re/names-imports-duel_eng.csv

A stub whose target has no name yet becomes "thunk_FUN_<address>", which the registry still counts as
unknown. Imports from other game modules resolve when those modules are given with --provider
(e.g. --provider gmodule/rel_field.prx:090ced00:rel_field for rel_story). Imports that neither BOOT.BIN nor a
provider exports (libraries of sub-modules that are not loaded in Ghidra, such as libcharalist_rel, and Sony NIDs
that BOOT.BIN does not import) are looked up by (library, NID) in a names table, by default re/game-libs.csv next to
the registry (--libs). See docs/subsystems/system.md.
"""

import argparse
import csv
import struct
import sys
from pathlib import Path

BOOT_BASE = 0x08804000


class Elf:
    """Allocated sections of a PSP PRX; pointers stored in the file are offsets from the module start."""

    def __init__(self, data, base):
        self.data, self.base = data, base
        shoff, = struct.unpack_from("<I", data, 0x20)
        entsize, count, strndx = struct.unpack_from("<HHH", data, 0x2E)
        headers = [struct.unpack_from("<IIIIII", data, shoff + i * entsize) for i in range(count)]
        names = headers[strndx][4]
        self.sections = {data[names + h[0]:data.index(b"\0", names + h[0])].decode(): h for h in headers}

    def offset(self, pointer):
        """File offset of a module-relative pointer."""
        for _, _, flags, addr, off, size in self.sections.values():
            if flags & 2 and addr <= pointer < addr + size:
                return off + pointer - addr
        raise ValueError(f"pointer {pointer:#x} is outside every allocated section")

    def u32(self, pointer, count=1):
        return struct.unpack_from(f"<{count}I", self.data, self.offset(pointer))

    def string(self, pointer):
        start = self.offset(pointer)
        return self.data[start:self.data.index(b"\0", start)].decode()

    def library_entries(self, section, stride_bytes):
        """(entry pointer) for each variable-size library entry in .lib.ent or .lib.stub."""
        _, _, _, addr, _, size = self.sections[section]
        pointer = addr
        while pointer < addr + size:
            yield pointer
            pointer += stride_bytes(pointer)


def exports(boot):
    """{nid: (library, absolute function address)} for every function BOOT.BIN exports."""
    out = {}
    for entry in boot.library_entries(".lib.ent", lambda p: 4 * boot.data[boot.offset(p) + 8]):
        name_ptr, = boot.u32(entry)
        vcount = boot.data[boot.offset(entry) + 9]
        fcount, = struct.unpack_from("<H", boot.data, boot.offset(entry) + 10)
        table, = boot.u32(entry + 12)
        name = boot.string(name_ptr) if name_ptr else "(module)"
        total = fcount + vcount
        nids = boot.u32(table, total) if total else ()
        addrs = boot.u32(table + 4 * total, total) if total else ()
        for k in range(fcount):
            out[nids[k]] = (name, boot.base + addrs[k])
    return out


def imports(module):
    """[(library, nid, absolute stub address)] for every function a module imports."""
    out = []
    for entry in module.library_entries(".lib.stub", lambda p: 4 * module.data[module.offset(p) + 8]):
        name_ptr, = module.u32(entry)
        fcount, = struct.unpack_from("<H", module.data, module.offset(entry) + 10)
        nid_table, stub_table = module.u32(entry + 12, 2)
        library = module.string(name_ptr)
        for k, nid in enumerate(module.u32(nid_table, fcount) if fcount else ()):
            out.append((library, nid, module.base + stub_table + 8 * k))
    return out


def stub_names(boot, module, registry, providers=(), libs=None):
    """ApplyNames rows (stub, group, name) plus the count of unresolved imports.

    `providers` are (Elf, registry prefix) pairs for game modules whose exported libraries other modules
    import (for example rel_field's library used by rel_story); `registry` maps an address, or a
    (prefix, address) pair for module-qualified ids, to (name, group); `libs` maps (library, nid) to
    (name, group) for imports that no given module exports (see load_libs).
    """
    libs = libs or {}
    sources = [({(lib, nid): addr for nid, (lib, addr) in exports(boot).items()}, "")]
    sources += [({(lib, nid): addr for nid, (lib, addr) in exports(elf).items()}, prefix)
                for elf, prefix in providers]
    rows, unresolved = [], 0
    for library, nid, stub in imports(module):
        for table, prefix in sources:
            address = table.get((library, nid))
            if address is not None:
                break
        else:
            if (library, nid) in libs:
                name, group = libs[(library, nid)]
                rows.append((stub, group, f"thunk_{name}"))
            else:
                unresolved += 1
            continue
        name, group = registry.get((prefix, address) if prefix else address, (f"FUN_{address:08x}", ""))
        rows.append((stub, group, name if name.startswith("thunk_") else f"thunk_{name}"))
    return rows, unresolved


def load_registry(path):
    """re/functions.csv as {address: (name, group)}, with (prefix, address) keys for 'module:0x…' ids."""
    registry = {}
    for row in csv.DictReader(open(path, encoding="utf-8")):
        prefix, _, address = row["id"].rpartition(":")
        key = (prefix, int(address, 16)) if prefix else int(address, 16)
        registry[key] = (row["name"], row["group"])
    return registry


def load_libs(path):
    """re/game-libs.csv as {(library, nid): (name, group)} (columns library,nid,group,name,...; # comments)."""
    lines = [line for line in open(path, encoding="utf-8") if not line.startswith("#")]
    return {(row["library"], int(row["nid"], 16)): (row["name"], row["group"]) for row in csv.DictReader(lines)}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Name a module's import stubs after their BOOT.BIN targets.")
    parser.add_argument("boot", type=Path, help="PSP_GAME/SYSDIR/BOOT.BIN")
    parser.add_argument("module", type=Path, help="gmodule/<name>.prx")
    parser.add_argument("base", help="the module's runtime base address, hex")
    parser.add_argument("registry", type=Path, help="re/functions.csv (names and groups of BOOT.BIN functions)")
    parser.add_argument("--provider", action="append", default=[], metavar="PRX:BASE[:PREFIX]",
                        help="a game module whose exported library this module imports, with its runtime base "
                             "and its registry id prefix (repeatable)")
    parser.add_argument("--libs", type=Path, default=None,
                        help="names of imports that no given module exports, by library and NID "
                             "(default: game-libs.csv next to the registry, if present)")
    args = parser.parse_args(argv)

    registry = load_registry(args.registry)
    libs_path = args.libs or args.registry.parent / "game-libs.csv"
    libs = load_libs(libs_path) if libs_path.exists() else {}
    boot = Elf(args.boot.read_bytes(), BOOT_BASE)
    module = Elf(args.module.read_bytes(), int(args.base, 16))
    providers = []
    for spec in args.provider:
        # Split from the right so that a Windows drive letter in the path survives.
        parts = spec.rsplit(":", 2)
        if len(parts) == 3 and not parts[2].lower().startswith(("0x",)) and not all(
                c in "0123456789abcdefABCDEF" for c in parts[2]):
            path, base, prefix = parts
        else:
            path, base = spec.rsplit(":", 1)
            prefix = ""
        providers.append((Elf(Path(path).read_bytes(), int(base, 16)), prefix))
    rows, unresolved = stub_names(boot, module, registry, providers, libs)
    print(f"# Generated by tools/prx_imports.py for {args.module.name} at {args.base}; do not edit by hand.")
    print("address,group,name")
    for stub, group, name in rows:
        print(f"0x{stub:08x},{group},{name}")
    print(f"{len(rows)} stubs named, {unresolved} unresolved", file=sys.stderr)
    return 1 if unresolved else 0


if __name__ == "__main__":
    sys.exit(main())
