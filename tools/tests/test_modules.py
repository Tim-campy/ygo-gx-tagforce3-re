#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/modules.py on synthetic PRX images. Run with: python3 -I tools/tests/test_modules.py"""

import contextlib
import importlib.util
import io
import struct
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location("re_" + name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


modules = load("modules")
helpers = load("tests/test_prx_imports")  # reuse the synthetic ELF builder
build, library_entry = helpers.build, helpers.library_entry


def module_info(name, gp=0x1000):
    return struct.pack("<HH", 0, 0x0101) + name.encode().ljust(28, b"\0") + struct.pack("<5I", gp, 0, 0, 0, 0)


def boot_image():
    # libehsys_rel exports NIDs 0xA1, 0xA2 (functions at 0x40, 0x80); .data holds a descriptor table.
    rodata = b"libehsys_rel\0\0\0\0" + struct.pack("<4I", 0xA1, 0xA2, 0x40, 0x80)
    names = b"rel_a.prx\0\0\0rel_b.prx\0\0\0"            # at 0x300 and 0x30c
    table = struct.pack("<8I", 8, 2, 0x300, 0, 9, 2, 0x30C, 0x03000004) + bytes(16)
    return build([(".lib.ent", 0x200, library_entry(0x100, 0, 2, 0x110)),
                   (".rodata", 0x100, rodata),
                   (".data", 0x300, names + bytes(8) + table)])


def game_module(name, text=b"", exports=None, imports=()):
    """ELF module importing (library, [nids]) pairs and optionally exporting (library, [nids])."""
    strings, nid_words, entries_ent, entries_stub = b"", b"", b"", b""
    rodata_addr = 0x800
    blobs = []

    def add_string(s):
        nonlocal strings
        ptr = rodata_addr + len(strings)
        strings += s.encode() + b"\0"
        while len(strings) % 4:
            strings += b"\0"
        return ptr

    lib_names = [lib for lib, _ in imports] + ([exports[0]] if exports else [])
    ptrs = {lib: add_string(lib) for lib in lib_names}
    nid_base = rodata_addr + len(strings)
    stub_addr = 0x600
    for lib, nids in imports:
        table = nid_base + len(nid_words)
        nid_words += struct.pack(f"<{len(nids)}I", *nids)
        entries_stub += library_entry(ptrs[lib], 0, len(nids), table, stub_addr)
        stub_addr += 8 * len(nids)
    if exports:
        lib, nids = exports
        table = nid_base + len(nid_words)
        nid_words += struct.pack(f"<{2 * len(nids)}I", *nids, *[0x10 * (k + 1) for k in range(len(nids))])
        entries_ent += library_entry(ptrs[lib], 0, len(nids), table)
    blobs = [(".text", 0x0, text or bytes(8)), (".rodata", rodata_addr, strings + nid_words),
             (".rodata.sceModuleInfo", 0xF00, module_info(name))]
    if entries_ent:
        blobs.append((".lib.ent", 0xA00, entries_ent))
    if entries_stub:
        blobs.append((".lib.stub", 0xC00, entries_stub))
    return build(blobs)


def jal(target):
    return struct.pack("<I", (3 << 26) | (target >> 2))


class ModulesTest(unittest.TestCase):
    def setUp(self):
        self.boot = modules.Elf(boot_image(), modules.BOOT_BASE)
        self.provider = modules.Module("rel_b.prx", game_module("modb", exports=("libb_rel", [0xB1, 0xB2])))
        self.user = modules.Module("rel_a.prx", game_module(
            "moda", imports=[("libehsys_rel", [0xA1, 0xA2]), ("libb_rel", [0xB1, 0xB9]), ("sceJpeg", [0x5])]))

    def test_module_info_and_libraries(self):
        self.assertEqual(modules.module_info(self.user.elf)[:3], ("moda", 0, 0x0101))
        self.assertEqual(self.provider.exports, [("libb_rel", 2, 0, [0xB1, 0xB2])])
        self.assertEqual([(lib, f) for lib, f, _, _ in self.user.imports],
                         [("libehsys_rel", 2), ("libb_rel", 2), ("sceJpeg", 1)])

    def test_resolution_against_boot_and_other_modules(self):
        index = modules.provider_index(self.boot, [self.user, self.provider])
        self.assertEqual(modules.resolve(self.user, index), [
            ("libehsys_rel", 2, 2, "BOOT.BIN"), ("libb_rel", 2, 1, "rel_b.prx"), ("sceJpeg", 1, 0, "system")])
        _, problems = modules.describe(self.user, index)
        self.assertEqual(problems, ["rel_a.prx: 1 of 2 libb_rel imports do not resolve in rel_b.prx"])

    def test_encrypted_header(self):
        data = b"~SCE" + bytes(0x3C) + b"~PSP" + struct.pack("<HH", 6, 1) + b"\x01\x01" + b"font_lib".ljust(28, b"\0")
        data += bytes(0x40 + 0x28 - len(data)) + struct.pack("<II", 1000, 500)
        module = modules.Module("libfont.prx", data)
        self.assertIsNone(module.elf)
        self.assertEqual(module.header, ("font_lib", 6, 1, 1000, 500))

    def test_descriptor_table(self):
        tables = modules.descriptor_tables(self.boot)
        self.assertEqual(len(tables), 1)
        address, rows = tables[0]
        self.assertEqual(address, modules.BOOT_BASE + 0x320)
        self.assertEqual(rows, [(8, 2, "rel_a.prx", 0), (9, 2, "rel_b.prx", 0x03000004)])

    def test_vote_base(self):
        starts = [0x40, 0x100, 0x180, 0x2C4]
        text = b"".join(jal(t) for t in starts) + bytes(0x300)
        base = 0x09000000
        symbols = {base + s: 8 for s in starts}
        symbols.update({0x08900000 + 4 * k: 4 for k in range(50)})   # unrelated module
        self.assertEqual(modules.vote_base(text, 0, symbols), (base, 4, 4))

    def test_cli_list_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "BOOT.BIN").write_bytes(boot_image())
            (tmp / "g").mkdir()
            (tmp / "g" / "rel_b.prx").write_bytes(game_module("modb", exports=("libb_rel", [0xB1])))
            (tmp / "g" / "rel_a.prx").write_bytes(game_module("moda", imports=[("libb_rel", [0xB1])]))
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(modules.main(["list", str(tmp / "BOOT.BIN"), str(tmp / "g"), "--check"]), 0)
            self.assertIn("import libb_rel: 1 functions, 1 resolved in rel_b.prx", out.getvalue())
            (tmp / "g" / "rel_a.prx").write_bytes(game_module("moda", imports=[("libb_rel", [0xBF])]))
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(modules.main(["list", str(tmp / "BOOT.BIN"), str(tmp / "g"), "--check"]), 1)


if __name__ == "__main__":
    unittest.main()
