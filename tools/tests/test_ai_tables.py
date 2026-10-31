#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/ai_tables.py on a synthetic module. Run with: python3 -I tools/tests/test_ai_tables.py"""

import contextlib
import csv
import importlib.util
import io
import struct
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_ai_tables", Path(__file__).resolve().parents[1] / "ai_tables.py")
at = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(at)

BASE = at.BASE
START, END = 0x09D2F000, 0x09E00900  # the synthetic segment covers the consumers and the tables
HANDLER = 0x09D6B6B8
V0 = 2


def itype(op, rs, rt, imm):
    return op << 26 | rs << 21 | rt << 16 | (imm & 0xFFFF)


def load_address(address):
    """lui v0,HI; addiu v0,v0,LO building the module offset of `address` (as relocated code does)."""
    value = address - BASE
    return [itype(0x0F, 0, V0, (value + 0x8000) >> 16), itype(0x09, V0, V0, value & 0xFFFF)]


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


def build(skip_constant=None):
    img = Image()
    card = 0x1000
    for key, _, address, count, _ in at.TABLES:
        for i in range(count):
            img.put(address + 8 * i, card, HANDLER - BASE)
            card += 1
    for start, count in ((at.GAP[0], 14), (at.TABLES_END, 4)):
        img.put(start, *[HANDLER - BASE] * count)
    for key, address, count, _, _ in at.LISTS:
        img.half(address, *range(0x1100, 0x1100 + count))
    r1 = at.table_by_key("R1")
    img.half(r1[1] + 2 * (r1[2] - 1), at.R1_SENTINEL)
    for address, _, size, keys, constants in at.CONSUMERS:
        code = []
        for key in keys.split():
            t = at.table_by_key(key)
            code += load_address(t[2] if key[0] != "R" else t[1])
        code += [itype(0x09, 0, V0, c) for c in constants if c != skip_constant]
        assert 4 * len(code) <= size
        img.put(address, *code)
    return img


class AiTablesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = at.Module(build().elf())

    def test_layout_is_contiguous(self):
        self.assertEqual(sum(t[3] for t in at.TABLES), 1648)
        self.assertEqual(at.TABLES[0][2] + 8 * sum(t[3] for t in at.TABLES) + (at.GAP[1] - at.GAP[0]),
                         at.TABLES_END)
        self.assertEqual(at.LISTS[-1][1] + 4, at.TABLES[0][2])

    def test_check_passes(self):
        self.assertEqual(at.check(self.module), [])

    def test_check_detects_missing_length_constant(self):
        problems = at.check(at.Module(build(skip_constant=0x2A9).elf()))
        self.assertTrue(any("ai_table_length" in p and "0x2a9" in p for p in problems), problems)

    def test_check_detects_bad_entries(self):
        img = build()
        img.put(0x09E004E0, 5, 0)  # table G entry 0: id out of range, handler not a pointer
        img.half(0x09DFD2DC + 2 * 142, 0x1300)  # R1 no longer ends with its sentinel
        problems = at.check(at.Module(img.elf()))
        self.assertTrue(any("G entry" in p and "out of range" in p for p in problems), problems)
        self.assertTrue(any("G entry" in p and "handler" in p for p in problems), problems)
        self.assertTrue(any("R1 does not end" in p for p in problems), problems)

    def test_check_detects_missing_reference(self):
        img = build()
        img.put(0x09D8C1E8, 0, 0)  # ai_try_summon_enablers no longer builds table C's address
        problems = at.check(at.Module(img.elf()))
        self.assertTrue(any("does not reference table C" in p for p in problems), problems)

    def test_list_rows(self):
        rows = at.list_rows(self.module, {0x1000: "First"}, {HANDLER: "ai_cond_always"})
        self.assertEqual(len(rows), 1648 + 143 + 36 + 1)
        self.assertEqual((rows[0]["table"], rows[0]["card_id"], rows[0]["card"], rows[0]["handler_name"]),
                         ("T1", "0x1000", "First", "ai_cond_always"))
        a = next(r for r in rows if r["table"] == "A")
        self.assertEqual((a["index"], a["address"]), (0, "0x09dfe500"))
        r3 = [r for r in rows if r["table"] == "R3"]
        self.assertEqual([(r["address"], r["handler"]) for r in r3], [("0x09dfd444", "0x09d27348")])

    def test_cards_and_missing(self):
        rows = at.card_rows(self.module)
        sentinel = next(r for r in rows if r["card_id"] == "0x1935")
        self.assertEqual(sentinel["tables"], "R1:142")
        both = next(r for r in rows if r["card_id"] == "0x1100")  # first entry of T1 and of every list
        self.assertEqual(both["count"], 4)
        missing = at.missing_cards(self.module, set(range(0x1000, 0x1000 + 1648)))
        self.assertEqual(dict(missing), {0x1935: 1})

    def test_handler_class(self):
        cases = {"ai_cond_always": "constant", "ai_cond_never": "constant", "FUN_09d6b6c8": "unnamed",
                 "": "unnamed", "ai_handler_on_attack_declared_event": "event",
                 "ai_handler_counter_harmful_link": "chain", "ai_handler_burn": "lp",
                 "ai_handler_stall_if_behind": "battle", "ai_handler_fusion_summon": "summon",
                 "ai_handler_destroy_spell_trap": "removal", "ai_cond_has_target": "target",
                 "ai_cond_no_active_copy": "limit", "ai_handler_in_opponent_end_phase": "phase",
                 "ai_cond_has_candidate": "resources", "ai_handler_field_spell_if_zone_free": "board",
                 "ai_handler_mystery": "other"}
        for name, key in cases.items():
            self.assertEqual(at.handler_class(name), key, name)

    def test_class_rows_and_summary(self):
        rows = at.class_rows(self.module, {HANDLER: "ai_cond_always"})
        self.assertEqual(len(rows), 1 + 3)  # one pair-table handler and the three list handlers
        self.assertEqual((rows[0]["handler"], rows[0]["class"], rows[0]["entries"]), ("0x09d6b6b8", "constant", 1648))
        self.assertIn("T1:345", rows[0]["tables"])
        self.assertEqual(sum(r["entries"] for r in rows), 1648 + 143 + 36 + 1)
        lines = at.class_summary(rows)
        self.assertTrue(lines[1].startswith("constant") and "1648" in lines[1], lines)
        self.assertTrue(lines[-1].startswith("total") and lines[-1].split()[1:] == ["4", "1828"], lines)

    def test_per_card_names_and_families(self):
        known = {"ai_handler_counter_harmful_link", "ai_cond_has_target", "ai_handler_burn_at_least_1000"}
        self.assertEqual(at.per_card_name("ai_handler_check_battle_1ce5"), ("check_battle", [0x1CE5]))
        self.assertEqual(at.per_card_name("ai_handler_counter_harmful_link_1a24_1a25_t3", known),
                         ("counter_harmful_link", [0x1A24, 0x1A25]))
        self.assertIsNone(at.per_card_name("ai_handler_burn_at_least_1000", known))  # shared, "1000" is no id
        self.assertIsNone(at.per_card_name("ai_handler_chain_fizzle_by_face_down"))  # 0xface is no card id
        self.assertEqual(at.per_card_name("thunk_ai_handler_check_targets_1668"), ("check_targets", [0x1668]))
        cases = {"ai_handler_check_battle_1ce5": ("battle", "battle"),
                 "ai_handler_respond_to_link_1330_12d0": ("link", "chain"),
                 "ai_handler_check_rule_state_1803": ("state", "state"),
                 "ai_handler_has_target_17fc": ("variant", "target"),
                 "ai_handler_counter_harmful_link_1b05": ("variant", "chain"),
                 "ai_handler_burn_at_least_1000": ("shared", "lp"),
                 "ai_cond_always": ("shared", "constant"), "FUN_09d1d0c4": ("unnamed", "unnamed")}
        for name, (family, cls) in cases.items():
            self.assertEqual((at.handler_family(name, known), at.handler_class(name, known)), (family, cls), name)

    def test_handler_rows_and_name_check(self):
        first_t1, first_b = 0x1000, 0x1000 + 345 + 2 + 181 + 105  # card ids of T1[0] and B[0] in the image
        img = build()
        img.put(0x09DFD448, first_t1, 0x09D30000 - BASE)  # T1[0] gets its own handler
        img.put(0x09DFE848, first_b, 0x09D30000 - BASE)  # and so does B[0]
        module = at.Module(img.elf())
        names = {HANDLER: "ai_cond_always", 0x09D22924: "ai_handler_on_attack_declared_event",
                 0x09D262C8: "ai_handler_on_damage_step_event", 0x09D27348: "ai_handler_check_rule_state_1803",
                 0x09D30000: f"ai_handler_check_lp_{first_t1:04x}_{first_b:04x}"}
        rows = at.handler_rows(module, {first_t1: "First"}, names)
        own = [r for r in rows if r["handler"] == "0x09d30000"]
        self.assertEqual([(r["card_id"], r["family"], r["class"], r["shared_by"], r["tables"]) for r in own],
                         [("0x1000", "lp", "lp", 2, "T1:0"), (f"{first_b:#06x}", "lp", "lp", 2, "B:0")])
        self.assertEqual(own[0]["card"], "First")
        # R3's single id is 0x1100 in the image, not 0x1803; the check reports the mismatch
        problems = at.check_names(module, names)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("ai_handler_check_rule_state_1803", problems[0])
        names[0x09D27348] = "ai_handler_check_rule_state_1100"
        self.assertEqual(at.check_names(module, names), [])
        names[0x09D30000] = f"ai_handler_mystery_test_{first_t1:04x}_{first_b:04x}"  # stem of no shared handler
        self.assertTrue(any("ai_handler_mystery_test" in p for p in at.check_names(module, names)))
        del names[HANDLER]
        self.assertTrue(any("0x09d6b6b8" in p and "no name" in p for p in at.check_names(module, names)))
        lines = at.family_summary(at.handler_rows(module, None, names))
        self.assertTrue(lines[-1].startswith("total"), lines)

    def test_load_functions_formats(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg, names = Path(tmp) / "functions.csv", Path(tmp) / "names.csv"
            reg.write_text("id,name,group,status,size\n0x09d6b6b8,FUN_09d6b6b8,,,8\nfmt,x,,,\n", encoding="utf-8")
            names.write_text("# comment\naddress,group,name\n0x09d6b6b8,ai,ai_cond_always\n0x09d00000,ai,\n",
                             encoding="utf-8")
            merged = at.load_functions(names, at.load_functions(reg))
            self.assertEqual(merged, {HANDLER: "ai_cond_always"})

    def test_main(self):
        with tempfile.TemporaryDirectory() as tmp:
            prx = Path(tmp) / "rel_duel_eng.prx"
            prx.write_bytes(build().elf())
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(at.main([str(prx), "--check"]), 0)
            self.assertIn("pair tables: 1648 entries", out.getvalue())
            self.assertTrue(out.getvalue().rstrip().endswith("ok"))
            target = Path(tmp) / "cards.csv"
            self.assertEqual(at.main([str(prx), "cards", "-o", str(target)]), 0)
            with open(target, newline="", encoding="utf-8") as f:
                self.assertEqual(len(list(csv.DictReader(f))), 1648 + 1)  # list ids repeat table ids except the sentinel
            names = Path(tmp) / "names.csv"
            names.write_text("address,group,name\n0x09d6b6b8,ai,ai_cond_always\n", encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(at.main([str(prx), "classes", "--functions", str(names), "--summary"]), 0)
            self.assertIn("constant", out.getvalue())
            target = Path(tmp) / "classes.csv"
            self.assertEqual(at.main([str(prx), "classes", "--functions", str(names), "-o", str(target)]), 0)
            with open(target, newline="", encoding="utf-8") as f:
                self.assertEqual(next(csv.DictReader(f))["class"], "constant")


if __name__ == "__main__":
    unittest.main()
