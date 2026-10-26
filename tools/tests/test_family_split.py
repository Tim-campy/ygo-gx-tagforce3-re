#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/family_split.py on a synthetic module. Run with: python3 -I tools/tests/test_family_split.py"""

import contextlib
import csv
import importlib.util
import io
import struct
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_family_split",
                                              Path(__file__).resolve().parents[1] / "family_split.py")
fs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fs)
ec, ep = fs.ec, fs.ep

BASE = ec.BASE
ZERO, AT, V0, V1, A0, A1, A2 = 0, 1, 2, 3, 4, 5, 6
T0, T1, S0, S1, S2, SP, RA = 8, 9, 16, 17, 18, 29, 31
K1, K2, K3 = 0x1000, 0x1001, 0x1002


def itype(op, rs, rt, imm):
    return op << 26 | rs << 21 | rt << 16 | (imm & 0xFFFF)


def addiu(rt, rs, imm):
    return itype(9, rs, rt, imm)


def andi(rt, rs, imm):
    return itype(0x0C, rs, rt, imm)


def sltiu(rt, rs, imm):
    return itype(0x0B, rs, rt, imm)


def lui(rt, imm):
    return itype(0x0F, 0, rt, imm)


def lhu(rt, base, off):
    return itype(0x25, base, rt, off)


def lbu(rt, base, off):
    return itype(0x24, base, rt, off)


def lw(rt, base, off):
    return itype(0x23, base, rt, off)


def sw(rt, base, off):
    return itype(0x2B, base, rt, off)


def addu(rd, rs, rt):
    return rs << 21 | rt << 16 | rd << 11 | 0x21


def subu(rd, rs, rt):
    return rs << 21 | rt << 16 | rd << 11 | 0x23


def sll(rd, rt, sa):
    return rt << 16 | rd << 11 | sa << 6


def jr(rs):
    return rs << 21 | 8


def jump(op, target):
    return op << 26 | (target - BASE) >> 2


def branch(op, rs, rt, pc, target):
    return itype(op, rs, rt, (target - pc - 4) >> 2)


JR_RA = jr(RA)
DRAW, DESTROY, DAMAGE, GAIN = 0x09C40000, 0x09C40010, 0x09C40020, 0x09C40030
EFFID, SETFACE, POS, COUNT = 0x09C40040, 0x09C40050, 0x09C40060, 0x09C40070
H_FAM = 0x09C40100   # card-id compare chain, link pointer spilled to the stack and reloaded
H_SUB = 0x09C40200   # calls SUB with the link in a0
SUB = 0x09C40280     # FUN_: card id test, tail calls
H_JT = 0x09C40300    # jump table indexed by card id - K1
H_REV = 0x09C40400   # face up, destroy, face down again: a reveal
CHAIN = 0x09C40500   # duel_effects_get_lp_change_amounts
RESOLVE = 0x09C40700  # duel_effects_resolve_lp_change
END = 0x09C40800
TABLE = 0x09DE8000   # jump table of H_JT (in the data after .text)

REGISTRY = {DRAW: "duel_core_draw_cards", DESTROY: "duel_core_destroy_slot", DAMAGE: "duel_core_inflict_damage",
            GAIN: "duel_core_gain_lp", EFFID: "duel_core_get_effective_card_id", SETFACE: "duel_core_post_set_face",
            POS: "duel_core_change_position", COUNT: "duel_core_count_things", H_FAM: "FUN_09c40100",
            H_SUB: "FUN_09c40200", SUB: "FUN_09c40280", H_JT: "FUN_09c40300", H_REV: "FUN_09c40400",
            CHAIN: "duel_effects_get_lp_change_amounts", RESOLVE: "duel_effects_resolve_lp_change",
            END: "FUN_09c40800"}

MAPPING = """kind,pattern,category,role,note
name,^duel_core_draw_cards$,draw,effect,
name,^duel_core_destroy,destroy,effect,
name,^duel_core_inflict_damage$,damage,effect,
name,^duel_core_gain_lp$,gain_lp,effect,
name,^duel_core_change_position$,position_change,effect,
name,^duel_core_(get|count)_,,stop,
"""


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
    for leaf in (DRAW, DESTROY, DAMAGE, GAIN, POS, COUNT, END):
        img.put(leaf, JR_RA, 0)
    img.put(EFFID, JR_RA, addiu(V0, ZERO, 0x1234))
    img.put(SETFACE, jump(3, POS), 0, JR_RA, 0)
    h = H_FAM
    img.put(h, addiu(SP, SP, -16), sw(RA, SP, 0), addu(S0, A0, ZERO), sw(S0, SP, 8), jump(3, EFFID), 0,
            lw(S1, SP, 8), lhu(V0, S1, 0), addiu(V1, ZERO, K1), branch(4, V0, V1, h + 36, h + 60), 0,
            jump(3, DESTROY), 0, branch(4, ZERO, ZERO, h + 52, h + 68), 0,
            jump(3, DRAW), 0, lw(RA, SP, 0), JR_RA, addiu(SP, SP, 16))
    img.put(H_SUB, jump(3, SUB), 0, JR_RA, 0)
    s = SUB
    img.put(s, lhu(V0, A0, 0), addiu(V1, ZERO, K1), branch(5, V0, V1, s + 8, s + 24), 0,
            jump(2, GAIN), 0, jump(2, DAMAGE), 0)
    j = H_JT
    off = TABLE - BASE
    hi, lo = (off + 0x8000) >> 16, off & 0xFFFF
    img.put(j, lhu(V0, A0, 0), addiu(V0, V0, -K1), sltiu(AT, V0, 2), branch(4, AT, ZERO, j + 12, j + 48),
            lui(V1, hi), sll(V0, V0, 2), addu(V0, V0, V1), lw(V0, V0, lo), jr(V0), 0,
            jump(2, DRAW), 0, jump(2, DESTROY), 0)
    img.put(TABLE, j + 40 - BASE, j + 48 - BASE)
    r = H_REV
    img.put(r, addiu(A2, ZERO, 1), jump(3, SETFACE), 0, jump(3, DESTROY), 0, addiu(A2, ZERO, 0),
            jump(3, SETFACE), 0, JR_RA, 0)
    c = CHAIN
    img.put(c, lbu(A2, A0, 2), andi(S2, A2, 1), addu(S0, A1, ZERO), addu(S1, A0, ZERO), lhu(V0, S1, 0),
            addiu(V1, ZERO, K1), branch(5, V0, V1, c + 24, c + 60), 0,
            # K1: out[1 - controller] = -800 (the store sits in the delay slot of the return)
            addiu(T0, ZERO, 1), subu(T0, T0, S2), sll(T0, T0, 2), addu(T0, S0, T0), addiu(T1, ZERO, -800),
            JR_RA, sw(T1, T0, 0),
            addiu(V1, ZERO, K2), branch(5, V0, V1, c + 64, c + 104), 0,
            # K2: out[controller] = count * 4
            jump(3, COUNT), 0, sll(V0, V0, 2), sll(T0, S2, 2), addu(T0, S0, T0), sw(V0, T0, 0), JR_RA, 0,
            JR_RA, 0)
    img.put(RESOLVE, jump(3, CHAIN), 0, jump(3, DAMAGE), 0, jump(3, GAIN), 0, JR_RA, 0)
    tables = {name: address for name, address, _ in ep.TABLES}
    records = {"S/T": [(K1, H_FAM), (K2, H_FAM), (K3, H_SUB)], "M1": [(K1, H_JT), (K2, H_JT)],
               "M2": [(K1, H_REV), (K2, H_REV), (K1, H_SUB), (K2, H_SUB)],
               "M3": [(K1, RESOLVE), (K2, RESOLVE), (K3, RESOLVE)]}
    for name, recs in records.items():
        for i, (cid, handler) in enumerate(recs):
            img.put(tables[name] + 24 * i, cid, handler - BASE, 0, 0, 0, 0)
    return img.elf()


class Synthetic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = build()
        module = ep.Module(cls.data)
        registry = ec.Registry(dict(REGISTRY), module)
        cls.classifier = ec.Classifier(module, registry, ec.Mapping.load_text(MAPPING), depth=3)
        cls.splitter = fs.FamilySplitter(cls.classifier)
        cls.refined, cls.families = fs.split_records(cls.classifier, cls.splitter)

    def cats(self, handler, card):
        return fs.effect_set(self.splitter.closure(handler, card)["categories"])

    def test_union_before(self):
        for h, want in ((H_FAM, {"draw", "destroy"}), (H_SUB, {"gain_lp", "damage"}), (H_JT, {"draw", "destroy"}),
                        (H_REV, {"destroy", "position_change"}), (RESOLVE, {"damage", "gain_lp"})):
            self.assertEqual(fs.effect_set(self.classifier.closure(h)["categories"]), want, hex(h))

    def test_compare_chain_with_spilled_link(self):
        self.assertEqual(self.cats(H_FAM, K1), {"draw"})
        self.assertEqual(self.cats(H_FAM, K2), {"destroy"})
        self.assertGreater(self.splitter.closure(H_FAM, K1)["id_reads"], 0)

    def test_callee_receives_link(self):
        self.assertEqual(self.cats(H_SUB, K1), {"gain_lp"})
        self.assertEqual(self.cats(H_SUB, K2), {"damage"})

    def test_jump_table(self):
        self.assertEqual(self.cats(H_JT, K1), {"draw"})
        self.assertEqual(self.cats(H_JT, K2), {"destroy"})
        self.assertFalse(self.splitter.closure(H_JT, K1)["fallback"])
        self.assertEqual(self.cats(H_JT, K3), {"destroy"})  # out of range: the default branch

    def test_reveal_pair(self):
        c = self.splitter.closure(H_REV, K1)
        self.assertEqual(fs.effect_set(c["categories"]), {"destroy"})
        self.assertIn(("reveal", "meta"), c["categories"])

    def test_lp_decode(self):
        stores, complete = self.splitter.lp.decode(K1)
        self.assertTrue(complete)
        self.assertEqual(stores, [("opponent", ("i", -800, -800))])
        lp = self.splitter.lp_decode(K1)
        self.assertEqual((lp["categories"], lp["signs"], lp["exact"]), ({"damage"}, ["opponent:-800"], True))
        lp = self.splitter.lp_decode(K2)
        self.assertEqual((lp["categories"], lp["signs"], lp["exact"]), ({"gain_lp"}, ["self:+"], False))
        self.assertEqual(self.splitter.lp_decode(K3)["categories"], set())

    def test_records(self):
        by = {(t, i): r for (t, i), r in self.refined.items()}
        self.assertEqual(by[("S/T", 0)]["after"], ["draw"])
        self.assertEqual(by[("S/T", 0)]["removed"], ["destroy"])
        self.assertEqual(by[("S/T", 0)]["method"], "branch")
        self.assertEqual(by[("S/T", 0)]["confidence"], "high")
        self.assertEqual(by[("M3", 0)]["after"], ["damage"])
        self.assertEqual(by[("M3", 0)]["method"], "lp_chain")
        self.assertEqual(by[("M3", 0)]["confidence"], "high")
        self.assertEqual(by[("M3", 1)]["confidence"], "medium")  # a computed (non-negative) amount
        self.assertEqual(by[("M3", 2)]["after"], ["damage", "gain_lp"])  # no case in the chain: kept
        self.assertEqual(by[("M3", 2)]["method"], "lp_chain_unresolved")
        self.assertEqual(by[("M2", 0)]["method"], "reveal")
        self.assertEqual(by[("M2", 0)]["removed"], ["position_change"])
        self.assertEqual(by[("S/T", 2)]["after"], ["damage"])  # H_SUB is shared by K1, K2 and K3
        for r in self.refined.values():
            self.assertTrue(set(r["after"]) <= set(r["before"]))
        self.assertEqual({f["handler"] for f in self.families}, {H_FAM, H_SUB, H_JT, H_REV, RESOLVE})

    def test_precision(self):
        sample = {(K1, H_FAM): {"draw"}, (K2, RESOLVE): {"gain_lp"}}
        self.assertEqual(fs.precision(self.refined, sample), ((2, 4), (2, 2)))

    def test_decide(self):
        regs = {V0: ec.const(K1), V1: ec.const(K2), S0: (0xFFFF0000, 0)}
        self.assertFalse(fs.decide(itype(4, V0, V1, 0), regs))  # beq: known unequal
        self.assertTrue(fs.decide(itype(5, V0, V1, 0), regs))   # bne
        self.assertIsNone(fs.decide(itype(4, S0, V1, 0), regs))
        self.assertFalse(fs.decide(itype(1, V0, 0, 0), regs))   # bltz on a positive constant
        self.assertTrue(fs.decide(itype(7, V0, 0, 0), regs))    # bgtz
        self.assertTrue(fs.decide(itype(6, ZERO, 0, 0), regs))  # blez zero

    def test_lp_categories(self):
        cats, signs, exact = fs.lp_categories([("self", ("i", 500, 500)), ("opponent", ("x", 1, -200, 0, 0, 9))])
        self.assertEqual((cats, signs, exact), ({"gain_lp", "damage"}, ["self:+500", "opponent:-"], False))
        self.assertEqual(fs.lp_categories([("either", None)])[0], {"damage", "gain_lp"})

    def test_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "m.prx").write_bytes(self.data)
            with open(tmp / "f.csv", "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["id", "name", "group", "status", "size"])
                for a, n in sorted(REGISTRY.items()):
                    w.writerow([f"{a:#010x}", n, "", "", ""])
            (tmp / "c.csv").write_text(MAPPING, encoding="utf-8")
            out = io.StringIO()
            args = [str(tmp / "m.prx"), "--functions", str(tmp / "f.csv"), "--categories", str(tmp / "c.csv")]
            with contextlib.redirect_stdout(out):
                self.assertEqual(fs.main(args + ["--check"]), 0)
            self.assertIn("families split: 5 resolve handlers", out.getvalue())
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(fs.main(args + ["-o", str(tmp / "out")]), 0)
            with open(tmp / "out" / "family_split.csv", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 12)
            self.assertIn("lp_amounts", rows[0])
            with open(tmp / "out" / "families.csv", encoding="utf-8") as f:
                fams = list(csv.DictReader(f))
            self.assertEqual(len(fams), 5)


if __name__ == "__main__":
    unittest.main()
