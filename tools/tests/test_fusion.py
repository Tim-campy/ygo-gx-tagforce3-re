#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/fusion.py on a synthetic module. Run with: python3 -I tools/tests/test_fusion.py"""

import contextlib
import csv
import importlib.util
import io
import struct
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_fusion", Path(__file__).resolve().parents[1] / "fusion.py")
fu = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fu)

BASE = fu.BASE
START, END = 0x09CB9000, 0x09DEC600  # covers the consumers and both tables
V0, V1 = 2, 3
FUSION0 = 0x1000  # synthetic fusion ids 0x1000..; materials 0x1100..
RITUAL_SPELL, RITUAL_MONSTER = 0x1200, 0x1300


def itype(op, rs, rt, imm):
    return op << 26 | rs << 21 | rt << 16 | (imm & 0xFFFF)


class Image:
    def __init__(self):
        self.buf = bytearray(END - START)

    def put(self, address, *words):
        struct.pack_into(f"<{len(words)}I", self.buf, address - START, *words)

    def half(self, address, *values):
        struct.pack_into(f"<{len(values)}H", self.buf, address - START, *values)

    def elf(self):
        header = bytearray(0x54)
        header[0:4] = b"\x7fELF"
        struct.pack_into("<I", header, 0x1C, 0x34)
        struct.pack_into("<H", header, 0x2C, 1)
        struct.pack_into("<6I", header, 0x34, 1, 0x54, START - BASE, 0, len(self.buf), len(self.buf))
        return bytes(header) + bytes(self.buf)


def build(skip_constant=False, use_load=False):
    img = Image()
    for i in range(fu.RECIPE_COUNT):
        third = 0x1180 + i if i >= fu.THREE_MATERIAL_FIRST else 0
        second = 6 if i == 0 else 0x1100 + i  # recipe 0 uses a generic code (Rock)
        img.half(fu.RECIPES + 8 * i, FUSION0 + i, 0x1100 + i, second, third)
    img.half(fu.RECIPES + 8 * fu.RECIPE_COUNT, 0x7E84)  # unrelated data after the table
    for i in range(3):
        img.put(fu.RITUALS + 4 * i, (6 + i) << 28 | (RITUAL_SPELL + i) << 14 | (RITUAL_MONSTER + i))
    img.put(fu.RITUALS + 12, 0)
    for address, _, size, target, constants in fu.CONSUMERS:
        value = target - BASE
        hi = (value + 0x8000) >> 16
        code = [itype(0x0F, 0, V0, hi)]
        # either addiu v0,v0,LO or lhu v1,LO(v0): both use the lui'd register as an address base
        code.append(itype(0x25 if use_load else 0x09, V0, V1 if use_load else V0, value & 0xFFFF))
        if not skip_constant:
            code += [itype(0x09, 0, V1, c) for c in constants]
        img.put(address, *code)
    return img


def cards():
    out = {}
    for i in range(fu.RECIPE_COUNT):
        out[FUSION0 + i] = (f"Fusion {i}", {"kind": 7, "level": 6, "icon": 0})
        out[0x1100 + i] = (f"Material {i}", {"kind": 1, "level": 4, "icon": 0})
        out[0x1180 + i] = (f"Third {i}", {"kind": 1, "level": 4, "icon": 0})
    for fusion, codes in fu.HARDCODED.items():
        out[fusion] = (f"Hard {fusion:#x}", {"kind": 7, "level": 10, "icon": 0})
        for c in codes:
            if c >= fu.GENERIC_LIMIT:
                out[c] = (f"Card {c:#x}", {"kind": 3, "level": 4, "icon": 0})
    for i in range(3):
        out[RITUAL_MONSTER + i] = (f"Ritual {i}", {"kind": 11, "level": 6 + i, "icon": 0})
        out[RITUAL_SPELL + i] = (f"Rite {i}", {"kind": 27, "level": 0, "icon": 6})
    return out


class FusionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = fu.Module(build().elf())

    def test_recipes_decode(self):
        rows = fu.recipes(self.module)
        self.assertEqual(len(rows), 138)
        self.assertEqual(rows[0], fu.Recipe(0, fu.RECIPES, FUSION0, (0x1100, 6)))
        self.assertEqual(rows[-1].materials, (0x1100 + 137, 0x1100 + 137, 0x1180 + 137))
        self.assertEqual(fu.material_count(self.module, FUSION0 + 5), 2)
        self.assertEqual(fu.material_count(self.module, FUSION0 + 130), 3)
        self.assertEqual(fu.material_count(self.module, 0x1E7E), 5)
        self.assertEqual(fu.material_count(self.module, 0x1ABC), 0)

    def test_rituals_decode(self):
        rows = fu.rituals(self.module)
        self.assertEqual([(r.monster, r.spell, r.level) for r in rows],
                         [(RITUAL_MONSTER + i, RITUAL_SPELL + i, 6 + i) for i in range(3)])

    def test_check_passes(self):
        self.assertEqual(fu.check(self.module), [])
        self.assertEqual(fu.check(self.module, cards()), [])
        self.assertEqual(fu.check(fu.Module(build(use_load=True).elf())), [])

    def test_check_detects_problems(self):
        img = build()
        img.half(fu.RECIPES + 8 * 3, FUSION0 + 3, 0x30, 0x1103, 0)  # unknown generic code 0x30 is >= 0x24: bad id
        img.half(fu.RECIPES + 8 * 4 + 6, 0x1104)  # record 4 now has three materials
        img.half(fu.RECIPES + 8 * 5, FUSION0 + 6)  # duplicate fusion id
        img.half(fu.RECIPES + 8 * fu.RECIPE_COUNT, 0x1500)  # data after the table looks like a recipe
        problems = fu.check(fu.Module(img.elf()))
        self.assertTrue(any("recipe 3" in p and "neither" in p for p in problems), problems)
        self.assertTrue(any("recipe 4" in p and "3 materials" in p for p in problems), problems)
        self.assertTrue(any("duplicate" in p for p in problems), problems)
        self.assertTrue(any("after the table" in p for p in problems), problems)

    def test_check_detects_missing_constant_and_reference(self):
        problems = fu.check(fu.Module(build(skip_constant=True).elf()))
        self.assertTrue(any("lacks the constant 0x8a" in p for p in problems), problems)
        img = build()
        img.put(0x09CCD5B4, 0, 0)
        problems = fu.check(fu.Module(img.elf()))
        self.assertTrue(any("duel_effects_cond_ritual_summon" in p for p in problems), problems)

    def test_check_cards(self):
        db = cards()
        db[FUSION0 + 1] = ("Not a fusion", {"kind": 3, "level": 4, "icon": 0})
        del db[0x1100 + 2]
        db[RITUAL_MONSTER + 1] = ("Ritual 1", {"kind": 11, "level": 9, "icon": 0})
        db[RITUAL_SPELL + 2] = ("Plain spell", {"kind": 27, "level": 0, "icon": 0})
        problems = fu.check(self.module, db)
        self.assertTrue(any("is not a Fusion monster" in p for p in problems), problems)
        self.assertTrue(any(f"material {0x1102:#06x} has no cardinfo" in p for p in problems), problems)
        self.assertTrue(any("ritual 1" in p and "Level" in p for p in problems), problems)
        self.assertTrue(any("ritual 2" in p and "Ritual Spell" in p for p in problems), problems)

    def test_describe_code(self):
        self.assertEqual(fu.describe_code(6), "any Rock-Type monster")
        self.assertIn("Gladiator Beast", fu.describe_code(0x17))
        self.assertEqual(fu.describe_code(0x1100, {0x1100: ("Material 0", {})}), "Material 0 (0x1100)")

    def test_main(self):
        with tempfile.TemporaryDirectory() as tmp:
            prx = Path(tmp) / "rel_duel_eng.prx"
            prx.write_bytes(build().elf())
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(fu.main([str(prx), "--check"]), 0)
            self.assertIn("fusion recipes: 138 (119 with 2 materials, 19 with 3)", out.getvalue())
            self.assertTrue(out.getvalue().rstrip().endswith("ok"))
            target = Path(tmp) / "recipes.csv"
            self.assertEqual(fu.main([str(prx), "recipes", "-o", str(target)]), 0)
            with open(target, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 138 + len(fu.HARDCODED))
            self.assertEqual(rows[0]["material1"], "any Rock-Type monster")
            target = Path(tmp) / "rituals.csv"
            self.assertEqual(fu.main([str(prx), "rituals", "-o", str(target)]), 0)
            with open(target, newline="", encoding="utf-8") as f:
                self.assertEqual(len(list(csv.DictReader(f))), 3)


if __name__ == "__main__":
    unittest.main()
