#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/scenes.py on a synthetic MIPS module. Run with: python3 -I tools/tests/test_scenes.py"""

import importlib.util
import struct
import unittest
from collections import Counter
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("re_scenes", TOOLS / "scenes.py")
scenes = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scenes)

FIND, ACC = 0x200, 0x208  # fake import stubs inside .text
NAMES, TABLE, CACHE = 0x1000, 0x1080, 0x1100


def elf(sections, entry=0):
    """ELF with (name, address, flags, bytes) sections plus .shstrtab; no program header."""
    names = b"\0" + b"".join(n.encode() + b"\0" for n, _, _, _ in sections) + b".shstrtab\0"
    body, headers, data_off, name_off = b"", [], 0x34, 1
    for name, addr, flags, blob in sections:
        headers.append((name_off, 1, flags, addr, data_off + len(body), len(blob)))
        name_off += len(name) + 1
        body += blob
    headers.append((name_off, 3, 0, 0, data_off + len(body), len(names)))
    body += names
    header = bytearray(0x34)
    header[0:4] = b"\x7fELF"
    struct.pack_into("<I", header, 0x18, entry)
    struct.pack_into("<I", header, 0x20, data_off + len(body))
    struct.pack_into("<HHH", header, 0x2E, 40, len(headers) + 1, len(headers))
    table = bytes(40) + b"".join(struct.pack("<6I", *h) + bytes(16) for h in headers)
    return bytes(header) + body + table


def jal(target):
    return 0x0C000000 | (target >> 2)


GETTER = [  # 0x00: name_array + 64 * a0
    0x00041980,  # sll v1, a0, 6
    0x3C020000,  # lui v0, 0
    0x24420000 | NAMES,  # addiu v0, v0, NAMES
    0x03E00008,  # jr ra
    0x00431021,  # addu v0, v0, v1
]
WRAPPER = [  # 0x14: accessor(find_member(0, "title_msg_j.bin"), a0)
    0x27BDFFE8,  # addiu sp, sp, -0x18
    0xAFBF0010,  # sw ra, 0x10(sp)
    0xAFA40014,  # sw a0, 0x14(sp)
    0x3C050000,  # lui a1, 0
    0x24A50000 | TABLE,  # addiu a1, a1, TABLE
    jal(FIND),
    0x00002021,  # move a0, zero
    0x00402021,  # move a0, v0
    0x8FA50014,  # lw a1, 0x14(sp)
    jal(ACC),
    0x00000000,
    0x8FBF0010,  # lw ra, 0x10(sp)
    0x03E00008,  # jr ra
    0x27BD0018,  # addiu sp, sp, 0x18
]
CALLER = [  # 0x4c: wrapper(7); find_member(0, getter(1))
    0x27BDFFE8,
    0xAFBF0010,
    jal(0x14),
    0x24040007,  # addiu a0, zero, 7
    jal(0x00),
    0x24040001,  # addiu a0, zero, 1
    0x00402821,  # move a1, v0
    jal(FIND),
    0x00002021,  # move a0, zero
    0x8FBF0010,
    0x03E00008,
    0x27BD0018,
]
CACHED = [  # 0x7c: return cache if set, else find_member(0, "title_msg_j.bin")
    0x3C020000,  # lui v0, 0
    0x8C420000 | CACHE,  # lw v0, CACHE(v0)
    0x14400009,  # bnez v0, +9 (jr ra)
    0x00000000,
    0x27BDFFF0,  # addiu sp, sp, -0x10
    0xAFBF0000,  # sw ra, 0(sp)
    0x3C050000,
    0x24A50000 | TABLE,
    jal(FIND),
    0x00002021,
    0x8FBF0000,  # lw ra, 0(sp)
    0x27BD0010,  # addiu sp, sp, 0x10
    0x03E00008,  # jr ra
    0x00000000,
]


def build_module():
    words = GETTER + WRAPPER + CALLER + CACHED
    assert len(GETTER) * 4 == 0x14 and 0x14 + len(WRAPPER) * 4 == 0x4C and 0x4C + len(CALLER) * 4 == 0x7C
    text = struct.pack(f"<{len(words)}I", *words).ljust(0x210, b"\0")
    data = bytearray(0x200)
    for k, name in enumerate((b"a_menu.ehf", b"b_menu.ehf")):
        data[64 * k:64 * k + len(name)] = name
    data[TABLE - NAMES:TABLE - NAMES + 15] = b"title_msg_j.bin"
    image = elf([(".text", 0, 6, text), (".data", NAMES, 3, bytes(data))], entry=0x4C)
    return scenes.Module("rel_test", image, {FIND: scenes.FIND, ACC: scenes.ACCESSOR}, base=0)


class InterpreterTest(unittest.TestCase):
    def setUp(self):
        self.m = build_module()

    def test_getter_is_evaluated(self):
        self.assertEqual(scenes.emulate(self.m.bin, 0x00, (1, None, None, None)), NAMES + 64)
        self.assertIsNone(scenes.emulate(self.m.bin, 0x00, (None, None, None, None)))

    def test_cache_branch_is_explored(self):
        result = scenes.emulate(self.m.bin, 0x7C, (None,) * 4, self.m.stubs)
        self.assertEqual(result, ("call", scenes.FIND, (0, TABLE, None, None)))

    def test_sprintf_builds_names(self):
        st = scenes._State()
        st.mem, st.mtaint, st.regs = {}, {}, [None] * 32
        scenes._write_cstring(st, 0x0BF00000, b"strTbl_%c.bin")
        self.assertEqual(scenes._format(self.m.bin, st, b"strTbl_%c.bin", (ord("e"),)), b"strTbl_e.bin")
        self.assertEqual(scenes._format(self.m.bin, st, b"RCP_%03d.ydc", (7,)), b"RCP_007.ydc")
        self.assertIsNone(scenes._format(self.m.bin, st, b"%s", (None,)))


class UsesTest(unittest.TestCase):
    def setUp(self):
        self.m = build_module()

    def test_wrapper_index_is_taken_from_the_caller(self):
        strings = scenes.uses(self.m)["strings"]
        self.assertIn((0x4C, 0x54, "title_msg_<l>.bin", 7), strings)

    def test_call_argument_names_a_layout(self):
        names = scenes.uses(self.m)["names"]
        self.assertIn((0x4C, 0x68, scenes.FIND, "b_menu.ehf"), names)
        self.assertIn((0x14, 0x28, scenes.FIND, "title_msg_j.bin"), names)

    def test_collect_ranks_bases(self):
        strings, _ = scenes.collect(self.m, None)
        self.assertEqual(strings["b_menu.ehf"][0], "call")
        self.assertEqual(strings["a_menu.ehf"][0], "code")  # same name array, addressed by the getter
        self.assertEqual(strings["title_msg_j.bin"][0], "call")


class FakeDisc:
    def __init__(self, archives):
        self.archives = archives


class MatchTest(unittest.TestCase):
    def test_norm_and_patterns(self):
        self.assertEqual(scenes.norm("title_msg_j.bin"), "title_msg_<l>.bin")
        self.assertEqual(scenes.norm("basic_lang_eng.ehp"), "basic_lang_<l>.ehp")
        self.assertEqual(scenes.dir_of("database/gallery/%s"), "database/gallery")
        self.assertEqual(scenes.dir_of("field/bustup"), "field/bustup")
        self.assertIsNone(scenes.dir_of("movie/%s.pmf"))
        self.assertTrue(scenes.in_dir("minigame/dodge/basic_lang_eng.ehp", "dodge"))
        self.assertFalse(scenes.in_dir("minigame/throw/basic_lang_eng.ehp", "dodge"))

    def test_matcher(self):
        entry = lambda members, layouts=(), tables=(): {"members": set(members), "layouts": list(layouts),
                                                       "tables": list(tables)}
        disc = FakeDisc({
            "title_menu/title_menu_e.ehp": entry(["title_msg_e.bin", "press.ehf"], ["press.ehf"], ["title_msg_e.bin"]),
            "title_menu/title_menu_j.ehp": entry(["title_msg_j.bin"], [], ["title_msg_j.bin"]),
            "duel/bg/fmagic3720.ehp": entry([]),
            "duelsys/cardinfo_eng.ehp": entry(["DICT_E.bin"], [], ["DICT_E.bin"]),
        })
        mt = scenes.Matcher(disc)
        self.assertEqual(mt.archives_for("title_menu/title_menu_j.ehp"),
                         {"title_menu/title_menu_e.ehp", "title_menu/title_menu_j.ehp"})
        self.assertEqual(mt.archives_for("duel/bg/fmagic%04d.ehp"), {"duel/bg/fmagic3720.ehp"})
        self.assertEqual(mt.archives_for("cardinfo_"), {"duelsys/cardinfo_eng.ehp"})
        self.assertEqual(mt.member_hits("title_msg_x.bin"),
                         {("title_menu/title_menu_e.ehp", "title_msg_e.bin"),
                          ("title_menu/title_menu_j.ehp", "title_msg_j.bin")})
        self.assertEqual(mt.member_hits("DICT_"), {("duelsys/cardinfo_eng.ehp", "DICT_E.bin")})

    def test_coverage_counts(self):
        doc = {"modules": {"a": {"string_sites": {"requests": 2, "table_named": 1, "index_constant": 1,
                                                  "table_and_index": 1}}},
               "attribution": {"layouts": {"x:a.ehf": [{"module": "a", "basis": "code", "scenes": [4]}],
                                           "x:b.ehf": []}}}
        cov = scenes.coverage(doc)
        self.assertEqual(cov["string_requests"]["requests"], 2)
        total, to_module, to_scene, basis, missing = cov["layouts"]
        self.assertEqual((total, to_module, to_scene, basis, missing), (2, 1, 1, Counter(code=1), ["x:b.ehf"]))
        self.assertEqual(scenes.site_summary([(0, 0, "a.bin", 3), (0, 0, "?", None)]),
                         {"requests": 2, "table_named": 1, "index_constant": 1, "table_and_index": 1})


if __name__ == "__main__":
    unittest.main()
