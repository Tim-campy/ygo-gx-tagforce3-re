#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/prx_imports.py on synthetic PRX images. Run with: python3 -I tools/tests/test_prx_imports.py"""

import importlib.util
import struct
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_prx_imports", Path(__file__).resolve().parents[1] / "prx_imports.py")
prx_imports = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prx_imports)


def build(sections):
    """ELF with the given (name, module address, bytes) allocated sections plus .shstrtab."""
    names = b"\0" + b"".join(n.encode() + b"\0" for n, _, _ in sections) + b".shstrtab\0"
    body, headers, data_off = b"", [], 0x34
    name_off = 1
    for name, addr, blob in sections:
        headers.append((name_off, 1, 2, addr, data_off + len(body), len(blob)))
        name_off += len(name) + 1
        body += blob
    headers.append((name_off, 3, 0, 0, data_off + len(body), len(names)))
    body += names
    shoff = data_off + len(body)
    header = bytearray(0x34)
    header[0:4] = b"\x7fELF"
    struct.pack_into("<I", header, 0x20, shoff)
    struct.pack_into("<HHH", header, 0x2E, 40, len(headers) + 1, len(headers))
    table = bytes(40) + b"".join(struct.pack("<6I", *h) + bytes(16) for h in headers)
    return bytes(header) + body + table


def library_entry(name_ptr, vcount, fcount, table, stubs=None):
    """20-byte library entry (export or import); size field in words."""
    tail = struct.pack("<I", table) + (struct.pack("<I", stubs) if stubs is not None else b"")
    size = (12 + len(tail)) // 4
    return struct.pack("<IHHBBH", name_ptr, 0x11, 0x4001, size, vcount, fcount) + tail


class PrxImportsTest(unittest.TestCase):
    def test_resolves_stubs_by_nid(self):
        # BOOT.BIN: library "lib" at 0x100 exports two functions at 0x40 and 0x80 with NIDs 0xAAAA, 0xBBBB.
        boot_rodata = b"lib\0" + bytes(12) + struct.pack("<4I", 0xAAAA, 0xBBBB, 0x40, 0x80)
        boot = build([(".lib.ent", 0x200, library_entry(0x100, 0, 2, 0x110)),
                      (".rodata", 0x100, boot_rodata)])
        # Module: imports NIDs 0xBBBB, 0xAAAA, 0xCCCC; stubs at 0x300.
        mod_rodata = b"lib\0" + bytes(12) + struct.pack("<3I", 0xBBBB, 0xAAAA, 0xCCCC)
        module = build([(".lib.stub", 0x400, library_entry(0x100, 0, 3, 0x110, 0x300)),
                        (".rodata", 0x100, mod_rodata)])
        boot_elf = prx_imports.Elf(boot, prx_imports.BOOT_BASE)
        module_elf = prx_imports.Elf(module, 0x09000000)
        self.assertEqual(prx_imports.exports(boot_elf), {0xAAAA: ("lib", 0x08804040), 0xBBBB: ("lib", 0x08804080)})
        registry = {0x08804040: ("container_open", "container")}
        rows, unresolved = prx_imports.stub_names(boot_elf, module_elf, registry)
        self.assertEqual(rows, [(0x09000300, "", "thunk_FUN_08804080"),
                                (0x09000308, "container", "thunk_container_open")])
        self.assertEqual(unresolved, 1)


if __name__ == "__main__":
    unittest.main()
