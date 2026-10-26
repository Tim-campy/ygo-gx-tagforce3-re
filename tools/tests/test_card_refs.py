#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/card_refs.py on a synthetic module. Run with: python3 -I tools/tests/test_card_refs.py"""

import contextlib
import csv
import importlib.util
import io
import struct
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_card_refs", Path(__file__).resolve().parents[1] / "card_refs.py")
cr = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cr)

BASE = cr.BASE
ZERO, AT, V0, V1, A0, A1, A2, S0, SP, RA = 0, 1, 2, 3, 4, 5, 6, 16, 29, 31
SIZE = 0x400
F1, F2, F3, F4 = BASE + 0x100, BASE + 0x200, BASE + 0x240, BASE + 0x320
TABLE = 0x300  # module offset of F3's jump table


def itype(op, rs, rt, imm):
    return op << 26 | rs << 21 | rt << 16 | (imm & 0xFFFF)


def li(rt, imm):
    return itype(9, ZERO, rt, imm)


def rtype(fn, rd, rs, rt, sa=0):
    return rs << 21 | rt << 16 | rd << 11 | sa << 6 | fn


NOP = 0
JR_RA = RA << 21 | 8


def jal(target):
    return 3 << 26 | (target - BASE) >> 2


class Asm:
    """Sequential assembler with forward labels resolved by a second pass."""

    def __init__(self, start):
        self.start, self.items = start, []

    @property
    def pc(self):
        return self.start + 4 * len(self.items)

    def emit(self, *words):
        self.items.extend(words)
        return self

    def branch(self, op, rs, rt, label):
        self.items.append((op, rs, rt, label))
        return self

    def words(self, labels):
        out = []
        for k, w in enumerate(self.items):
            if isinstance(w, tuple):
                op, rs, rt, label = w
                pc = self.start + 4 * k
                w = itype(op, rs, rt, (labels[label] - pc - 4) >> 2)
            out.append(w)
        return out


def build(sections=False):
    buf = bytearray(SIZE)

    def put(address, words):
        struct.pack_into(f"<{len(words)}I", buf, address - BASE, *words)

    a = Asm(F1)
    a.emit(itype(9, SP, SP, -16), itype(0x25, A0, A2, 0))          # lhu a2,0(a0)
    a.emit(li(V0, 0x12EC)).branch(4, A2, V0, "t1").emit(NOP)        # eq, value 2
    a.emit(li(V0, 0x1300)).branch(5, V0, A2, "t1").emit(NOP)        # eq through bne
    a.emit(itype(0x0E, A2, V1, 0x1301))                             # xori: eq
    a.emit(itype(0x0A, A2, V1, 0x1400))                             # slti: bound
    a.emit(itype(9, A2, V1, -0x1500), itype(0x0B, V1, AT, 3), NOP)  # range [0x1500, 0x1503)
    a.emit(li(A0, 0x1600), jal(F2), NOP)                            # arg
    a.emit(jal(F2), li(A1, 0x1601))                                 # arg in the delay slot
    a.branch(0x14, V0, ZERO, "x").emit(li(A0, 0x1602))              # beql: taken path calls F2
    labels = {"x": a.pc}
    a.emit(jal(F2), NOP)
    a.emit(li(V1, 0x1603), itype(0x29, S0, V1, 4))                  # sh: store
    a.emit(li(V1, 0x1605), rtype(0x21, V1, V1, A2))                 # arithmetic: dropped
    a.emit(li(V0, 0x1604), JR_RA, itype(9, SP, SP, 16))             # return
    labels["t1"] = a.pc
    a.emit(JR_RA, li(V0, 2))
    put(F1, a.words(labels))
    put(F2, [JR_RA, NOP])
    # F3: switch (id - 0x1700) over 3 cases with a jump table; case 1 is the default
    c0, c2, default = F3 + 0x40, F3 + 0x48, F3 + 0x50
    b = Asm(F3)
    b.emit(itype(9, A0, V0, -0x1700), itype(0x0B, V0, V1, 3)).branch(4, V1, ZERO, "d")
    b.emit(rtype(0, V0, ZERO, V0, 2), itype(0x0F, 0, V1, 0), rtype(0x21, V0, V0, V1),
           itype(0x23, V0, V0, TABLE), V0 << 21 | 8, NOP)
    put(F3, b.words({"d": default}))
    put(c0, [JR_RA, li(V0, 7)])
    put(c2, [JR_RA, li(V0, 9)])
    put(default, [JR_RA, li(V0, 0)])
    struct.pack_into("<3I", buf, TABLE, c0 - BASE, default - BASE, c2 - BASE)
    # F4: a bne compare (the match falls through and returns 5) and a xor compare whose match calls F2
    d = Asm(F4)
    d.emit(itype(0x25, A0, A2, 0), li(V0, 0x1310)).branch(5, V0, A2, "l1").emit(NOP, JR_RA, li(V0, 5))
    l1 = d.pc
    d.emit(li(V1, 0x1311), rtype(0x26, V1, V1, A2)).branch(5, V1, ZERO, "l2").emit(NOP, jal(F2), NOP)
    l2 = d.pc
    d.emit(JR_RA, li(V0, 0))
    put(F4, d.words({"l1": l1, "l2": l2}))

    header = bytearray(0x54)
    header[0:4] = b"\x7fELF"
    struct.pack_into("<I", header, 0x1C, 0x34)
    struct.pack_into("<H", header, 0x2C, 1)
    struct.pack_into("<6I", header, 0x34, 1, 0x54, 0, 0, SIZE, SIZE)
    data = bytes(header) + bytes(buf)
    if not sections:
        return data
    names = b"\0.text\0.shstrtab\0"
    shoff = len(data) + len(names)
    table = struct.pack("<10I", *[0] * 10)
    table += struct.pack("<10I", 1, 1, 6, 0, 0x54, 0x240, 0, 0, 4, 0)            # .text: up to F3
    table += struct.pack("<10I", 7, 3, 0, 0, len(data), len(names), 0, 0, 1, 0)  # .shstrtab
    data = bytearray(data + names + table)
    struct.pack_into("<I", data, 0x20, shoff)
    struct.pack_into("<HHH", data, 0x2E, 40, 3, 2)
    return bytes(data)


FUNCTIONS = [BASE, F1, F2, F3, F4]
NAMES = {F1: "duel_core_test_chain", F2: "duel_core_is_on_field", F4: "duel_core_other_test"}
RULES = f"""pattern,kinds,callee,tag,phrase,param,values,confidence,basis
duel_core_test_chain,cmp,,piercing,inflicts piercing battle damage,piercing,2=always;none=conditional,H,test
{F4:#010x},cmp,,direct_attack,can attack directly,mode,1=may;*=mode {{value}},M,test
{BASE:#010x}-{BASE + 0x400:#010x},any,,ai_hint,AI-specific handling,,,L,test
*,arg,duel_core_is_on_*,named_reference,named by another card,,,L,test
"""


class CardRefs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.refs = cr.card_refs(build(), FUNCTIONS, NAMES)

    def kinds(self, cid):
        return [r["kind"] for r in self.refs.get(cid, ())]

    def test_compares(self):
        r = self.refs[0x12EC][0]
        self.assertEqual((r["kind"], r["function"], r["function_name"], r["group"]),
                         ("eq", F1, "duel_core_test_chain", "duel_core"))
        self.assertEqual(r["value"], 2)
        self.assertEqual(r["operand"], "u16 load")
        self.assertEqual(self.kinds(0x1300), ["eq"])
        self.assertEqual(self.refs[0x1301][0]["detail"], "xori")
        self.assertEqual(self.kinds(0x1400), ["bound"])

    def test_range_and_switch(self):
        self.assertEqual([c for c in self.refs if 0x1500 <= c < 0x1510], [0x1500, 0x1501, 0x1502])
        self.assertEqual(self.kinds(0x1500), ["range"])
        self.assertEqual(self.kinds(0x1700), ["switch"])
        self.assertNotIn(0x1701, self.refs)  # the default case
        self.assertEqual((self.refs[0x1700][0]["value"], self.refs[0x1702][0]["value"]), (7, 9))
        self.assertEqual(self.refs[0x1700][0]["operand"], "argument")

    def test_data_flow_kinds(self):
        for cid in (0x1600, 0x1601, 0x1602):
            self.assertEqual(self.kinds(cid), ["arg"], hex(cid))
            self.assertEqual(self.refs[cid][0]["detail"], "duel_core_is_on_field")
        self.assertEqual(self.kinds(0x1603), ["store"])
        self.assertEqual(self.refs[0x1603][0]["detail"], "16-bit")
        self.assertEqual(self.kinds(0x1604), ["return"])
        self.assertNotIn(0x1605, self.refs)

    def test_card_filter_and_sections(self):
        only = cr.card_refs(build(), FUNCTIONS, NAMES, cards={0x12EC})
        self.assertEqual(list(only), [0x12EC])
        self.assertEqual(cr.text_range(build(sections=True), BASE), (BASE, BASE + 0x240))
        self.assertNotIn(0x1700, cr.card_refs(build(sections=True), FUNCTIONS, NAMES))  # F3 is outside .text
        heuristic = cr.card_refs(build())  # no registry: heuristic entry points
        self.assertIn(0x12EC, heuristic)
        self.assertTrue(heuristic[0x12EC][0]["function_name"].startswith("FUN_"))

    def test_other_module_base(self):
        base = cr.MODULES["BOOT.BIN"]
        refs = cr.card_refs(build(), [base + 0x100, base + 0x200], {}, base, "BOOT.BIN")
        self.assertEqual(refs[0x12EC][0]["module"], "BOOT.BIN")
        self.assertEqual(refs[0x12EC][0]["function"], base + 0x100)
        merged = cr.merge(self.refs, refs)
        self.assertEqual(len(merged[0x12EC]), 2)

    def test_check(self):
        cards = {cid: ("Monster", 3) for cid in self.refs}
        cards.update({0x12EC: ("Draw", 27), 0x1300: ("Plain", 1), 0x1302: ("Effect", 3), 0x1600: ("Spell", 27)})
        tabled = set(cards) - {0x1302, 0x1600}
        problems, lines = cr.check(self.refs, cards, tabled, known=False)
        self.assertEqual(problems, [])
        text = "\n".join(lines)
        self.assertIn("effect cards without an effect-table record or list entry: 2; with an eq/switch/arg "
                      "reference: 1; without: 1 (kinds 3 1)", text)
        self.assertIn("1 normal/token cards referenced", text)
        problems, lines = cr.check(self.refs, known=True)
        self.assertEqual(len(problems), len(cr.KNOWN))
        self.assertIn(f"recall on documented tests: 0 of {len(cr.KNOWN)}", "\n".join(lines))

    def test_match_path(self):
        r = self.refs[0x1310][0]
        self.assertEqual((r["kind"], r["value"], r["calls"]), ("eq", 5, []))
        r = self.refs[0x1311][0]
        self.assertEqual((r["kind"], r["value"], r["calls"]), ("eq", None, ["duel_core_is_on_field"]))
        self.assertEqual(self.refs[0x12EC][0]["calls"], [])

    def test_semantics(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rules.csv"
            path.write_text(RULES, encoding="utf-8")
            rules = cr.load_semantics(path)
        self.assertEqual(cr.rule_problems(rules), [])
        refs = cr.card_refs(build(), FUNCTIONS, NAMES, semantics=rules)
        s = refs[0x12EC][0]["semantics"]
        self.assertEqual((s["tag"], s["confidence"], s["label"]), ("piercing", "H", "always"))
        self.assertEqual(refs[0x1300][0]["semantics"]["label"], "conditional")
        self.assertEqual(refs[0x1600][0]["semantics"]["tag"], "named_reference")  # arg rule by callee
        self.assertEqual(refs[0x1310][0]["semantics"]["label"], "mode 5")  # exact-address rule
        self.assertEqual(refs[0x1311][0]["semantics"]["label"], "")  # no value, no `none` label
        self.assertIsNone(refs[0x1400][0]["semantics"])  # bounds get no semantics
        row = dict(refs[0x1600][0], kind="eq", function=F2, function_name="duel_core_is_on_field")
        self.assertEqual(cr.classify(row, rules)["tag"], "unclassified")  # named: the range rule does not apply
        row["function_name"] = f"FUN_{F2:08x}"
        self.assertEqual(cr.classify(row, rules)["tag"], "ai_hint")  # unnamed function inside the range
        self.assertEqual(cr.card_refs(build(), FUNCTIONS, NAMES, semantics=[])[0x12EC][0]["semantics"]["tag"],
                         "unclassified")
        entries = cr.describe(refs, 0x12EC)
        self.assertEqual([(e["tag"], e["generic"], e["labels"]) for e in entries],
                         [("piercing", False, ["piercing: always"])])
        covered, tags, lacking = cr.coverage(refs, {0x12EC, 0x1300, 0x1600})
        self.assertEqual((covered, tags["piercing"], lacking), (2, 2, [0x1600]))
        problems, lines = cr.check(refs, known=False, subject={0x12EC, 0x1600}, rules=rules)
        self.assertEqual(problems, [])
        self.assertIn("semantics: 1 of 2 cards (50.0 %) have a descriptive tag", "\n".join(lines))
        row = next(cr.describe_rows(refs, [0x12EC]))
        self.assertEqual(row["description"], "inflicts piercing battle damage [piercing: always] (H)")
        self.assertEqual(next(cr.describe_rows(refs, [0x1600]))["description"], "generic: named_reference")
        bad = [dict(rules[0], confidence="X", kinds="both")]
        self.assertEqual(len(cr.rule_problems(bad)), 2)
        self.assertEqual(cr.parse_values("1=a;none=b;*=c {value}"), {1: "a", "none": "b", "*": "c {value}"})

    def test_group_of(self):
        self.assertEqual(cr.group_of("duel_effects_get_x"), "duel_effects")
        self.assertEqual(cr.group_of("ai_choose_slot"), "ai")
        self.assertEqual(cr.group_of("FUN_09c00000"), "")

    def test_main(self):
        with tempfile.TemporaryDirectory() as tmp:
            prx = Path(tmp) / "rel_duel_eng.prx"
            prx.write_bytes(build())
            reg = Path(tmp) / "functions.csv"
            reg.write_text("id,name,group,status,size\n" + "".join(
                f"{a:#010x},{NAMES.get(a, f'FUN_{a:08x}')},,,\n" for a in FUNCTIONS), encoding="utf-8")
            out = Path(tmp) / "out"
            with contextlib.redirect_stdout(io.StringIO()) as text:
                self.assertEqual(cr.main([str(prx), "list", "-o", str(out), "--functions", str(reg)]), 0)
                self.assertEqual(cr.main([str(prx), "--check", "--functions", str(reg)]), 0)
            self.assertIn("ok", text.getvalue())
            with open(out / "card_refs.csv", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(rows[0]["card_id"], "0x12ec")
            self.assertEqual(rows[0]["function_name"], "duel_core_test_chain")
            self.assertTrue((out / "card_ref_functions.csv").exists())
            with contextlib.redirect_stdout(io.StringIO()) as text:
                self.assertEqual(cr.main([str(prx), "describe", "--card", "0x12ec", "--functions", str(reg),
                                          "-o", str(out)]), 0)
            self.assertIn("0x12ec : generic: unclassified", text.getvalue())
            self.assertTrue((out / "card_semantics.csv").exists())


if __name__ == "__main__":
    unittest.main()
