#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/effect_params.py on a synthetic module. Run with: python3 -I tools/tests/test_effect_params.py"""

import contextlib
import csv
import importlib.util
import io
import struct
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_effect_params",
                                              Path(__file__).resolve().parents[1] / "effect_params.py")
ep = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ep)

BASE = ep.BASE
ZERO, V0, A0, A2, A3, S0, S2, SP, RA = 0, 2, 4, 6, 7, 16, 18, 29, 31


def itype(op, rs, rt, imm):
    return op << 26 | rs << 21 | rt << 16 | (imm & 0xFFFF)


def addiu(rt, rs, imm):
    return itype(9, rs, rt, imm)


def ori(rt, rs, imm):
    return itype(0x0D, rs, rt, imm)


def lui(rt, imm):
    return itype(0x0F, 0, rt, imm)


def lhu(rt, base, off):
    return itype(0x25, base, rt, off)


def addu(rd, rs, rt):
    return rs << 21 | rt << 16 | rd << 11 | 0x21


def jump(op, target):
    return op << 26 | (target - BASE) >> 2


def branch(op, rs, rt, pc, target):
    return itype(op, rs, rt, (target - pc - 4) >> 2)


JR_RA = RA << 21 | 8
STUB_A = 0x09C34000  # j filter; addiu a3,zero,0x1092
STUB_B = 0x09C34010  # lui v0,0x8; j filter; ori a3,v0,0x412
OTHER = 0x09C34020   # a handler that is not a stub
CALLER = 0x09C34100  # a function that calls the filter with a constant


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
    for name, address, count in ep.TABLES:
        for i in range(count):
            img.put(address + 24 * i, 0x1300 + 2 * i, 0, 0, 0, 0, 0)
    st = ep.TABLES[0][1]
    img.put(st, 0x12EC, 0, STUB_A - BASE, 0, 0, 0)          # record 0: addiu stub
    img.put(st + 24, 0x12ED, 0, STUB_B - BASE, 0, 0, 0)     # record 1: lui+ori stub
    img.put(st + 48, 0x12EE, 0, OTHER - BASE, 0, 0, 0)      # record 2: own function
    m1 = ep.TABLES[1][1]
    img.put(m1, 0x0E90, CALLER - BASE, 0, 0, 0, 0)          # CALLER is a slot +04 handler
    # the filter itself: prologue with `andi s1,s2,3`, epilogue at the documented size
    f = ep.TARGET_FILTER
    img.put(f, addiu(SP, SP, -64), itype(0x0C, S2, 17, 3))
    img.put(f + ep.TARGET_FILTER_SIZE - 8, JR_RA, addiu(SP, SP, 64))
    img.put(STUB_A, jump(2, f), addiu(A3, ZERO, 0x1092))
    img.put(STUB_B, lui(V0, 0x8), jump(2, f), ori(A3, V0, 0x412))
    img.put(OTHER, JR_RA, addiu(V0, ZERO, 1))
    img.put(CALLER, addiu(SP, SP, -16), jump(3, f), addiu(A3, ZERO, 0x4410), jump(3, ep.DRAW_COUNT), 0,
            JR_RA, addiu(SP, SP, 16))
    # the draw-count chain
    d = ep.DRAW_COUNT
    end = d + ep.DRAW_COUNT_SIZE - 12
    block = end - 0x40
    code = [addiu(SP, SP, -16), addu(S2, A0, ZERO), lhu(A2, S2, 0)]
    pc = d + 4 * len(code)
    for cid, op, target, delay in [(0x12EC, 0x14, end, addiu(S0, ZERO, 2)),
                                   (0x1300, 4, block, 0),
                                   (0x1301, 0x14, end, lhu(S0, S2, 0x12))]:
        code += [addiu(V0, ZERO, cid), branch(op, A2, V0, pc + 4, target), delay]
        pc += 12
    code += [branch(4, ZERO, ZERO, pc, end), 0]
    img.put(d, *code)
    img.put(block, addiu(S0, ZERO, -1), branch(4, ZERO, ZERO, block + 4, end), 0)
    img.put(end, addu(V0, S0, ZERO), JR_RA, addiu(SP, SP, 16))
    return img.elf()


class EffectParamsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = ep.Module(build())

    def test_check_passes(self):
        self.assertEqual(ep.check(self.module), [])

    def test_check_fails_on_other_data(self):
        img = Image()
        self.assertTrue(ep.check(ep.Module(img.elf())))

    def test_target_filter_stubs(self):
        rows = ep.target_filters(self.module)
        self.assertEqual([(r["card_id"], r["form"], r["flags"]) for r in rows],
                         [("0x12ec", "addiu", "0x01092"), ("0x12ed", "lui+ori", "0x80412")])
        self.assertEqual(rows[0]["side"], "opponent")
        self.assertEqual(rows[0]["zone"], "monster")
        self.assertEqual(rows[0]["position"], "attack")
        self.assertEqual(rows[0]["actions"], "destroy")
        self.assertEqual(rows[1]["actions"], "targeted return")

    def test_negative_addiu_is_sign_extended(self):
        img = bytearray(build())
        struct.pack_into("<I", img, STUB_A - BASE + 0x54 + 4, addiu(A3, ZERO, -2))
        self.assertEqual(ep.filter_stub(ep.Module(bytes(img)), STUB_A), ("addiu", 0xFFFFFFFE))

    def test_decode_flags(self):
        self.assertEqual(ep.decode_flags(0x1410), {"side": "any", "zone": "monster", "face": "", "position": "",
                                                   "actions": "targeted destroy"})
        d = ep.decode_flags(0x20000 | 0x200 | 0x8 | 0x3 | 0x100)
        self.assertEqual((d["side"], d["face"], d["position"]), ("tributable", "face_down", "defense"))
        self.assertEqual(d["actions"], "not_self unknown_0x200")

    def test_filter_calls(self):
        functions = ep.function_starts(self.module)
        users = ep.handler_users(self.module)
        rows = ep.target_filter_calls(self.module, functions, users)
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["function"], rows[0]["flags"], rows[0]["referenced_by"]),
                         (f"{CALLER:#010x}", "0x04410", "M1:+04:0xe90"))

    def test_draw_counts(self):
        rows = {r["card_id"]: r for r in ep.draw_counts(self.module)}
        self.assertEqual(rows["0x12ec"]["value"], 2)
        self.assertEqual(rows["0x1300"]["value"], -1)
        self.assertEqual(rows["0x1301"]["kind"], "computed")
        self.assertIn("ctx+0x12 u16", rows["0x1301"]["summary"])

    def test_compare_chains(self):
        functions = ep.function_starts(self.module)
        rows, cases = ep.compare_chains(self.module, functions, ep.handler_users(self.module), min_cases=3)
        draw = [r for r in rows if r["function"] == f"{ep.DRAW_COUNT:#010x}"]
        self.assertEqual(len(draw), 1)
        self.assertEqual((draw[0]["cases"], draw[0]["constant_cases"], draw[0]["class"]), (3, 2, "parameter"))
        self.assertEqual(len([c for c in cases if c["function"] == draw[0]["function"]]), 3)

    def test_evaluate_branches(self):
        img = Image()
        a = 0x09C40000
        img.put(a, addiu(V0, ZERO, 5), branch(5, V0, ZERO, a + 4, a + 20), addiu(V0, V0, 1),
                addiu(V0, ZERO, 0), JR_RA, JR_RA, 0)
        self.assertEqual(ep.evaluate(ep.Module(img.elf()), a), 6)

    def test_main_writes_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            prx = Path(tmp) / "rel_duel_eng.prx"
            prx.write_bytes(build())
            out = Path(tmp) / "out"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ep.main([str(prx), "-o", str(out)]), 0)
                self.assertEqual(ep.main([str(prx), "--check"]), 0)
            with open(out / "target_filters.csv", encoding="utf-8") as f:
                self.assertEqual(len(list(csv.DictReader(f))), 2)
            for name in ("target_filter_calls", "draw_counts", "compare_chains", "chain_cases"):
                self.assertTrue((out / f"{name}.csv").exists())


def sw(rt, base, off):
    return itype(0x2B, base, rt, off)


def lw(rt, base, off):
    return itype(0x23, base, rt, off)


def lbu(rt, base, off):
    return itype(0x24, base, rt, off)


A1, T0, T1, T2, T3, S1, V1 = 5, 8, 9, 10, 11, 17, 3
CHAIN = 0x09C50000
LEAF, NONLEAF, SIDE, VOID_CALLER = 0x09C50400, 0x09C50440, 0x09C50480, 0x09C504C0


def build_chain():
    """A synthetic compare chain on u16[arg0] (kept in s0) with one case per evaluator extension:

    0x1301 / 0x1302  a1 = 5 / 2, then a tail shared by both that calls SIDE and returns 1 (join states)
    0x1303           returns 1 or 2 depending on u8[arg0+3] (conditional)
    0x1304           returns LEAF(3) = 3 * 2 through mult/mflo (leaf helper inlined), with a stack-slot read
    0x1305           returns NONLEAF(9) (call expression)
    0x1306           re-tests u16[arg0] (through s1) against 0x1306 (bound to the case's id: constant 4, not 4 or 5)
    VOID_CALLER calls CHAIN and overwrites v0 before reading it."""
    img = Image()
    epi = [lw(RA, SP, 12), JR_RA, addiu(SP, SP, 16)]
    code = [addiu(SP, SP, -16), sw(RA, SP, 12), addiu(T0, ZERO, 7), sw(T0, SP, 8), lhu(S0, A0, 0),
            addu(S1, A0, ZERO)]
    cases = []
    pc = CHAIN + 4 * len(code)
    for cid in range(0x1301, 0x1307):
        code += [addiu(V1, ZERO, cid), 0, 0]  # branch filled in below
        cases.append((cid, pc + 4))
        pc += 12
    ret0 = pc + 8
    code += [branch(4, ZERO, ZERO, pc, ret0), 0, addiu(V0, ZERO, 0)] + epi
    pc = CHAIN + 4 * len(code)
    bodies = {}
    tail = pc + 0x200 - 0x40  # placed later
    blocks = {
        0x1301: [addiu(A1, ZERO, 5), "j_tail", 0],
        0x1302: [addiu(A1, ZERO, 2), "j_tail", 0],
        0x1303: [lbu(T1, A0, 3), "beq_t1_skip", addiu(V0, ZERO, 1), addiu(V0, ZERO, 2)] + epi,
        0x1304: [lw(A1, SP, 8), addiu(A0, ZERO, 3), jump(3, LEAF), 0] + epi,
        0x1305: [addiu(A0, ZERO, 9), jump(3, NONLEAF), 0] + epi,
        0x1306: [lhu(T2, S1, 0), addiu(T3, ZERO, 0x1306), "beq_t2_t3_skip", addiu(V0, ZERO, 4),
                 addiu(V0, ZERO, 5)] + epi,
    }
    for cid, words in blocks.items():
        bodies[cid] = pc
        out = []
        for k, w in enumerate(words):
            here = pc + 4 * k
            if w == "j_tail":
                w = branch(4, ZERO, ZERO, here, tail)
            elif w == "beq_t1_skip":
                w = branch(4, T1, ZERO, here, here + 12)  # taken: skip `v0 = 2`, land on the epilogue
            elif w == "beq_t2_t3_skip":
                w = branch(4, T2, T3, here, here + 12)
            out.append(w)
        img.put(pc, *out)
        pc += 4 * len(out)
    img.put(CHAIN, *code)
    for cid, at in cases:
        img.put(at, branch(4, S0, V1, at, bodies[cid]), 0)
    img.put(tail, jump(3, SIDE), 0, addiu(V0, ZERO, 1), *epi)
    img.put(LEAF, addiu(T0, ZERO, 2), A0 << 21 | T0 << 16 | 0x18, V0 << 11 | 0x12, JR_RA, 0)
    img.put(NONLEAF, addiu(SP, SP, -8), sw(RA, SP, 4), jump(3, SIDE), 0, lw(RA, SP, 4), JR_RA, addiu(SP, SP, 8))
    img.put(SIDE, JR_RA, 0)
    img.put(VOID_CALLER, addiu(SP, SP, -8), sw(RA, SP, 4), jump(3, CHAIN), 0, addiu(V0, ZERO, 0), lw(RA, SP, 4),
            JR_RA, addiu(SP, SP, 8))
    return img.elf()


class SymbolicEvaluatorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = ep.Module(build_chain())
        cls.functions = [CHAIN, LEAF, NONLEAF, SIDE, VOID_CALLER, VOID_CALLER + 0x40]
        cls.results = {r["card_id"]: r for r in ep.resolve_chain(cls.module, CHAIN, LEAF, cls.functions)}

    def test_join_states(self):
        for cid, a1 in ((0x1301, 5), (0x1302, 2)):
            r = self.results[cid]
            self.assertEqual(r["kind"], "constant")  # the shared tail returns 1
            self.assertEqual(r["method"], "paths")   # the plain evaluator stops at the call
            self.assertEqual([state for _, state in r["join"]], [{"a1": a1}])
            self.assertTrue(ep.case_summary(dict(r, kind="computed")).startswith(f"a1={a1} at 0x"))
        plain = {cid: v for cid, v, _ in ep.analyse_chain(self.module, CHAIN, LEAF)}
        self.assertIsNone(plain[0x1301])

    def test_conditional(self):
        r = self.results[0x1303]
        self.assertEqual((r["kind"], r["values"]), ("conditional", [1, 2]))

    def test_leaf_inlined_with_mult_and_stack(self):
        r = self.results[0x1304]
        self.assertEqual((r["kind"], r["value"]), ("constant", 6))
        self.assertEqual(r["calls"], [(LEAF, (3, 7, ("reg", "a2"), ("reg", "a3")), 6)])

    def test_call_expression(self):
        r = self.results[0x1305]
        self.assertEqual(r["kind"], "expression")
        self.assertEqual(ep.render(r["value"]), f"fn_{NONLEAF:08x}(9)")
        self.assertEqual(ep.render(r["value"], {NONLEAF: "helper"}), "helper(9)")

    def test_id_binding(self):
        self.assertEqual((self.results[0x1306]["kind"], self.results[0x1306]["value"]), ("constant", 4))

    def test_classes(self):
        res = list(self.results.values())
        self.assertTrue(ep.own_varies(res))
        self.assertEqual(ep.chain_class(res, None), "parameter")  # constants 1, 1, 6, 4 of 6 cases
        self.assertEqual(ep.chain_class(res, False), "behaviour")
        returns = ep.returns_value(self.module, self.functions)
        self.assertIs(returns[CHAIN], False)
        self.assertIs(returns[SIDE], True)  # NONLEAF returns SIDE's v0 to its own caller

    def test_render_forms(self):
        x = ("load", ("arg", 0), 2, 2, False)
        self.assertEqual(ep.render(x), "u16[arg0+0x2]")
        self.assertEqual(ep.render(("op", "<u", 0, x, )), "(u16[arg0+0x2] != 0)")
        self.assertEqual(ep.render(("op", "^", ("op", "<", x, 2), 1)), "!(u16[arg0+0x2] < 2)")
        self.assertEqual(ep.render(("op", "*", x, 300)), "(u16[arg0+0x2] * 300)")
        self.assertTrue(ep.grounded(x))
        self.assertFalse(ep.grounded(("op", "+", ("reg", "s3"), 1)))

    def test_unmodelled_and_jump_table_fail(self):
        img = Image()
        a = 0x09C40000
        img.put(a, 2 << 21 | 8, 0)  # jr v0
        ev = ep.SymbolicEvaluator(ep.Module(img.elf()))
        with self.assertRaises(ep.EvalFail):
            ev.paths(a, {})


if __name__ == "__main__":
    unittest.main()
