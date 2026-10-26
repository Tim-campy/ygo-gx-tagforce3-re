#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/search_filters.py on a synthetic module. Run with: python3 -I tools/tests/test_search_filters.py"""

import contextlib
import csv
import importlib.util
import io
import struct
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_search_filters",
                                              Path(__file__).resolve().parents[1] / "search_filters.py")
sf = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sf)
ec = sf.ec

BASE = sf.BASE
ZERO, V0, V1, A0, A1, A2, A3, T0, T1, T2, SP, RA = 0, 2, 3, 4, 5, 6, 7, 8, 9, 10, 29, 31
DECK, HAND, GRAVE = 0x09CCECBC, 0x09CCF428, 0x09CCF768
LIST, COUNT = sf.BUILDER_LIST[1], sf.BUILDER_LIST[2]


def itype(op, rs, rt, imm):
    return op << 26 | rs << 21 | rt << 16 | (imm & 0xFFFF)


def addiu(rt, rs, imm):
    return itype(9, rs, rt, imm)


def ori(rt, rs, imm):
    return itype(0x0D, rs, rt, imm)


def lui(rt, imm):
    return itype(0x0F, 0, rt, imm)


def sw(rt, base, off):
    return itype(0x2B, base, rt, off)


def lw(rt, base, off):
    return itype(0x23, base, rt, off)


def addu(rd, rs, rt):
    return rs << 21 | rt << 16 | rd << 11 | 0x21


def sll(rd, rt, sa):
    return rt << 16 | rd << 11 | sa << 6


def jump(op, target):
    return op << 26 | (target - BASE) >> 2


def branch(op, rs, rt, pc, target):
    return itype(op, rs, rt, (target - pc - 4) >> 2)


JR_RA = RA << 21 | 8
GETATTR = 0x09C40000   # card_db_get_attribute (leaf)
B_TAIL = 0x09C41000    # j DECK with filter 0x2002, options 0xa
B_CHAIN = 0x09C41100   # filter 0x8002 for card 0x1301 else 0x4002; archetype 8 through a stack slot; Graveyard
B_SUB = 0x09C41200     # jal SUB (a sub-builder calling the hand scanner)
SUB = 0x09C41300
B_CUSTOM = 0x09C41400  # add_candidate(side, 0x0e, 0)
B_GETTER = 0x09C41500  # filter = card_db_get_attribute(card) << 24 | 2; Deck
B_RACE = 0x09C41600    # filter = (a2 << 27) | 2: computed at run time
END = 0x09C41700

REGISTRY = {GETATTR: "card_db_get_attribute", B_TAIL: "FUN_09c41000", B_CHAIN: "FUN_09c41100",
            B_SUB: "FUN_09c41200", SUB: "FUN_09c41300", B_CUSTOM: "FUN_09c41400", B_GETTER: "FUN_09c41500",
            B_RACE: "FUN_09c41600", END: "FUN_09c41700",
            DECK: "duel_effects_collect_deck_candidates", HAND: "duel_effects_test_hand_candidate",
            GRAVE: "duel_effects_collect_graveyard_candidates", sf.ADD_CANDIDATE: "duel_effects_add_candidate",
            sf.BUILD_DISPATCH: "duel_effects_build_candidate_list", 0x09CCF134: "duel_effects_collect_extra_deck_candidates",
            0x09CCFCDC: "duel_effects_collect_banished_candidates"}
BUILDERS = [B_TAIL, B_CHAIN, B_CHAIN, B_SUB, B_CUSTOM, B_GETTER, B_RACE]
FIRST_ID = 0x1300
CARDS = {FIRST_ID + 5: {"name": "Test Card", "race": 15, "attribute": 2, "level": 4, "kind": 3}}


class Image:
    def __init__(self):
        self.size = 0x09E01E10 - BASE
        self.buf = bytearray(self.size)

    def put(self, address, *words):
        struct.pack_into(f"<{len(words)}I", self.buf, address - BASE, *words)

    def elf(self):
        header = bytearray(0x54)
        header[0:4] = b"\x7fELF"
        struct.pack_into("<I", header, 0x1C, 0x34)
        struct.pack_into("<H", header, 0x2C, 1)
        struct.pack_into("<6I", header, 0x34, 1, 0x54, 0, 0, self.size, self.size)
        return bytes(header) + bytes(self.buf)


def build():
    img = Image()
    for leaf in (GETATTR, DECK, HAND, GRAVE, sf.ADD_CANDIDATE, 0x09CCF134, 0x09CCFCDC, END):
        img.put(leaf, JR_RA, 0)
    off = LIST - BASE
    img.put(sf.BUILD_DISPATCH, lui(V0, off >> 16), addiu(V0, V0, off & 0xFFFF), JR_RA, 0)
    img.put(B_TAIL, addu(A2, ZERO, ZERO), addu(A3, ZERO, ZERO), addiu(T0, ZERO, 0x2002), jump(2, DECK),
            addiu(T1, ZERO, 0xA))
    c = B_CHAIN
    pred = sf.ARCHETYPE_PREDICATE - BASE
    img.put(c, addiu(SP, SP, -32), sw(RA, SP, 28), addiu(V0, ZERO, 0x1301), addiu(T0, ZERO, 0x4002),
            branch(0x14, A1, V0, c + 16, c + 24), ori(T0, ZERO, 0x8002),  # beql: delay only when taken
            lui(A2, pred >> 16), ori(A2, A2, pred & 0xFFFF), addiu(V1, ZERO, 8), sw(V1, SP, 16),
            addiu(A3, SP, 16), jump(3, GRAVE), addiu(T1, ZERO, 0x8), lw(RA, SP, 28), JR_RA, addiu(SP, SP, 32))
    img.put(B_SUB, addiu(SP, SP, -16), sw(RA, SP, 12), jump(3, SUB), addiu(A2, ZERO, 3), lw(RA, SP, 12),
            JR_RA, addiu(SP, SP, 16))
    img.put(SUB, addu(A3, ZERO, ZERO), addu(T0, ZERO, ZERO), lui(T1, 0x7890), ori(T1, T1, 0x0002), jump(2, HAND),
            addiu(T2, ZERO, 1))
    img.put(B_CUSTOM, addiu(A1, ZERO, 0x0E), jump(2, sf.ADD_CANDIDATE), addu(A2, ZERO, ZERO))
    g = B_GETTER
    img.put(g, addiu(SP, SP, -16), sw(RA, SP, 12), addu(16, A1, ZERO), jump(3, GETATTR), addu(A0, A1, ZERO),
            sll(T0, V0, 24), ori(T0, T0, 2), addu(A1, 16, ZERO), addu(A2, ZERO, ZERO), addu(A3, ZERO, ZERO),
            jump(3, DECK), addu(T1, ZERO, ZERO), lw(RA, SP, 12), JR_RA, addiu(SP, SP, 16))
    img.put(B_RACE, sll(T0, A2, 27), ori(T0, T0, 2), addu(A2, ZERO, ZERO), addu(A3, ZERO, ZERO), jump(2, DECK),
            addu(T1, ZERO, ZERO))
    for i in range(COUNT):
        builder = BUILDERS[i] if i < len(BUILDERS) else B_TAIL
        img.put(LIST + 8 * i, FIRST_ID + i, builder - BASE)
    return img.elf()


def records(cards=None):
    module = sf.ep.Module(build())
    registry = ec.Registry(dict(REGISTRY), module)
    return module, sf.analyse(module, registry, cards)


class DecodeTest(unittest.TestCase):
    def test_filter_fields(self):
        full = sf.FULL
        self.assertEqual(sf.decode_filter((full, 0x78900002)), ["kind=monster", "level<=4", "type=Warrior"])
        self.assertEqual(sf.decode_filter((full, 0x2002002)), ["kind=monster", "atk_max_1500", "attribute=DARK"])
        self.assertEqual(sf.decode_filter((full, 0)), ["kind=any"])
        self.assertEqual(sf.decode_filter((full, 0x4 | 0x180)), ["kind=spell", "icon=field"])
        self.assertEqual(sf.decode_filter((full, 0x10000 | 0x8000 | 0x10 | 0x20)),
                         ["kind=monster", "same_name", "different_name", "tuner", "targetable"])
        self.assertIn("unknown_bits=0x40", sf.decode_filter((full, 0x42)))
        computed = sf.decode_filter((0x07FFFFFF, 0x2), {"arg2"})
        self.assertIn("type=computed(arg2)", computed)
        self.assertNotIn("attribute", " ".join(computed))

    def test_monster_implied_by_options(self):
        self.assertEqual(sf.decode_filter((sf.FULL, 0), (), "deck", (sf.FULL, 0x8))[0], "kind=monster")
        self.assertEqual(sf.decode_filter((sf.FULL, 0), (), "hand", (sf.FULL, 0x8))[0], "kind=any")

    def test_options(self):
        full = sf.FULL
        self.assertEqual(sf.decode_options((full, 0xA), "deck"), ["skip_parasite_paracide", "special_summon_test"])
        self.assertEqual(sf.decode_options((full, 3 << 25 | 0x40), "deck"), ["first_match", "top=3"])
        self.assertEqual(sf.decode_options((full, 0x9), "graveyard"), ["opponent", "can_special_summon"])
        self.assertEqual(sf.decode_options((full, 0x80), "hand"), ["unknown_options=0x80"])
        self.assertEqual(sf.decode_options((0xFF, 0x1), "banished"), ["opponent", "options=computed"])


class SimulatorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module, cls.records = records(CARDS)

    def calls(self, index):
        return self.records[index]["calls"]

    def test_tail_call(self):
        (call,) = self.calls(0)
        self.assertEqual((call.location, call.filter[0][1], call.options[0][1], call.pred), ("deck", 0x2002, 0xA, 0))
        self.assertEqual(self.records[0]["status"], "decoded")

    def test_compare_chain_and_stack_argument(self):
        (first,), (second,) = self.calls(1), self.calls(2)  # cards 0x1301 and 0x1302
        self.assertEqual((first.location, first.filter[0][1]), ("graveyard", 0x8002))
        self.assertEqual(second.filter[0][1], 0x4002)
        self.assertEqual(first.pred, sf.ARCHETYPE_PREDICATE)
        self.assertEqual(first.pred_arg[0], (sf.FULL, 8))
        text, raw, opts = sf.describe_call(first, {8: "BOOT x"})
        self.assertIn("archetype=0x8 (BOOT x)", text)
        self.assertIn("tuner", text)
        self.assertEqual((raw, opts), ("0x8002", "0x8"))

    def test_sub_builder_and_hand_index(self):
        calls = self.calls(3)
        self.assertEqual({c.location for c in calls}, {"hand"})
        self.assertIn(0x78900002, {c.filter[0][1] for c in calls})
        self.assertTrue(all(c.index[0] == (sf.FULL, 3) for c in calls))

    def test_custom_builder(self):
        self.assertEqual(self.records[4]["status"], "custom")
        self.assertEqual(self.records[4]["adds"], {"graveyard"})

    def test_getter_resolved_through_cardinfo(self):
        (call,) = self.calls(5)
        self.assertEqual(call.filter[0], (sf.FULL, 0x2000002))
        _, plain = records()
        self.assertEqual(plain[5]["status"], "partial")

    def test_runtime_parameter_is_partial(self):
        (call,) = self.calls(6)
        self.assertEqual(self.records[6]["status"], "partial")
        self.assertIn("arg2", call.filter[2])
        self.assertIn("type=computed(arg2)", sf.describe_call(call)[0])

    def test_check_and_summary(self):
        self.assertEqual(sf.check(self.module, self.records), [])
        lines = sf.summary(self.records)
        self.assertTrue(lines[0].startswith(f"records {COUNT}"))


def write_functions(path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "group", "status", "size"])
        for a, n in REGISTRY.items():
            w.writerow([f"{a:#010x}", n, "", "", ""])


class InterfaceTest(unittest.TestCase):
    def test_card_filters(self):
        with tempfile.TemporaryDirectory() as tmp:
            functions = Path(tmp) / "functions.csv"
            write_functions(functions)
            rows = sf.card_filters(build(), functions)
        self.assertEqual(len(rows), COUNT)
        self.assertEqual(rows[1]["card_id"], FIRST_ID + 1)
        self.assertEqual(rows[1]["locations"], ["graveyard"])
        self.assertIn("graveyard: kind=monster tuner", rows[1]["filter"])

    def test_main_list_and_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            prx = tmp / "rel_duel_eng.prx"
            prx.write_bytes(build())
            functions = tmp / "functions.csv"
            write_functions(functions)
            out = tmp / "out" / "search_filters.csv"
            with contextlib.redirect_stdout(io.StringIO()) as text, contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(sf.main([str(prx), "list", "-o", str(out), "--functions", str(functions)]), 0)
                self.assertEqual(sf.main([str(prx), "--check", "--functions", str(functions)]), 0)
            self.assertIn("ok", text.getvalue())
            with open(out, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(rows[0]["raw_filter"], "0x2002")
            self.assertEqual(rows[0]["builder"], f"{B_TAIL:#010x}")


class DispatchHookTest(unittest.TestCase):
    """effect_classify's `dispatch` mapping row adds the categories of the card's own builder."""

    def test_dispatch(self):
        img = Image()
        img.buf[:] = build()[0x54:]
        handler = 0x09C41800
        img.put(handler, jump(3, sf.BUILD_DISPATCH), 0, JR_RA, 0)
        for name, address, count in ec.TABLES:
            for i in range(count):
                img.put(address + 24 * i, 0x2000 + i, 0, 0, 0, 0, 0)
        img.put(ec.TABLES[0][1], FIRST_ID + 1, handler - BASE, 0, 0, 0, 0)
        module = ec.ep.Module(img.elf())
        names = {**REGISTRY, handler: "FUN_09c41800", 0x09C41900: "FUN_09c41900"}
        mapping_text = ("kind,pattern,category,role,note\n"
                        "name,^duel_effects_collect_graveyard_candidates$,search_graveyard,effect,\n")
        hook = f"dispatch,^duel_effects_build_candidate_list$,{LIST:#x},,\n"
        for text, expected in ((mapping_text, ""), (mapping_text + hook, "search_graveyard")):
            cl = ec.Classifier(module, ec.Registry(dict(names), module), ec.Mapping.load_text(text))
            rows, _ = ec.classify_records(cl)
            self.assertEqual(rows[0]["resolve"], expected)


if __name__ == "__main__":
    unittest.main()
