#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/doc_audit.py and tools/doc_audit_scan.py on synthetic code. Run with:
python3 -I tools/tests/test_doc_audit.py"""

import importlib.util
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
SPEC = importlib.util.spec_from_file_location("re_doc_audit_scan", TOOLS / "doc_audit_scan.py")
scan = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scan)
audit = scan.sys.modules["doc_audit"]

ZERO, V0, V1, A0, A1, A2, A3, T0, S0, SP, RA = 0, 2, 3, 4, 5, 6, 7, 8, 16, 29, 31
NOP = 0


def r_type(rs, rt, rd, fn, sa=0):
    return rs << 21 | rt << 16 | rd << 11 | sa << 6 | fn


def i_type(op, rs, rt, imm):
    return op << 26 | rs << 21 | rt << 16 | imm & 0xFFFF


def move(rd, rs):
    return r_type(rs, ZERO, rd, 33)


def addiu(rt, rs, imm):
    return i_type(9, rs, rt, imm)


def jr_ra():
    return r_type(RA, 0, 0, 8)


def beq(rs, rt, words):
    return i_type(4, rs, rt, words)


def bnel(rs, rt, words):
    return i_type(21, rs, rt, words)


def jal(addr):
    return 3 << 26 | (addr >> 2 & 0x3FFFFFF)


def j(addr):
    return 2 << 26 | (addr >> 2 & 0x3FFFFFF)


def sw(rt, off, base):
    return i_type(43, base, rt, off)


def lw(rt, off, base):
    return i_type(35, base, rt, off)


FIXTURES = []


def tearDownModule():
    for fixture in FIXTURES:
        fixture.dir.cleanup()


class Fixture:
    """A program of a few functions written to a database directory, as ExportAuditData.java would."""

    def __init__(self, functions):
        self.dir = tempfile.TemporaryDirectory()
        FIXTURES.append(self)
        words, table = [], []
        base = 0x1000
        for name, proto, code in functions:
            entry = base + 4 * len(words)
            table.append((entry, name, proto, 4 * len(code)))
            words += code
        stem = os.path.join(self.dir.name, "P.prx")
        with open(stem + ".mem", "wb") as handle:
            handle.write(b"".join(struct.pack("<I", w & 0xFFFFFFFF) for w in words))
        with open(stem + ".map", "w", encoding="utf-8") as handle:
            handle.write(f"0x{base:08x}\t{4 * len(words)}\t0\t.text\tx\n")
        with open(stem + ".fn.tsv", "w", encoding="utf-8") as handle:
            for entry, name, proto, size in table:
                handle.write(f"0x{entry:08x}\t{name}\tsystem\t\t{size}\t{entry:x}-{entry + size - 1:x};\tint\t0\t{proto}\n")
        open(stem + ".xref.tsv", "w", encoding="utf-8").close()
        self.world = scan.World(self.dir.name)
        self.rows = {f"0x{e:08x}": dict(id=f"0x{e:08x}", program="P.prx", addr=f"0x{e:08x}", proto=p, summary="", doc="d")
                     for e, _, p, _ in table}
        self.code = scan.analyse(self.world, self.rows)

    def fn(self, name):
        return next(f for f in self.world.programs["P.prx"].funcs.values() if f.name == name)

    def scans(self):
        return sorted((h["name"], h["scan"]) for h in scan.scan_prototypes(self.world, self.code))


class DecodeTests(unittest.TestCase):
    def test_unconditional_branch_has_no_fall_through(self):
        self.assertEqual(scan.decode(beq(ZERO, ZERO, 3), 0x100).kind, "jump")
        self.assertEqual(scan.decode(beq(A0, ZERO, 3), 0x100).kind, "branch")

    def test_branch_likely_flag(self):
        self.assertTrue(scan.decode(bnel(A0, ZERO, 3), 0x100).likely)

    def test_register_sets(self):
        i = scan.decode(addiu(V0, A1, 4), 0)
        self.assertEqual(i.reads, 1 << A1)
        self.assertEqual(i.writes, 1 << V0)
        self.assertEqual(scan.decode(r_type(RA, 0, 0, 8), 0).kind, "ret")

    def test_prototype_parsing(self):
        ret, params, variadic = scan.proto_args("void * f(void (*cb)(int, int), float x, ...)")
        self.assertEqual(ret, "void *")
        self.assertEqual(len(params), 2)
        self.assertTrue(variadic)
        self.assertEqual(scan.proto_slots(params), (1, 1))
        self.assertEqual(scan.proto_slots(["ulonglong a", "int b"]), (3, 0))


class FlowTests(unittest.TestCase):
    def test_argument_read_before_write(self):
        fx = Fixture([("a", "int a(int x)", [move(V0, A1), jr_ra(), NOP])])
        self.assertEqual(scan.describe_args(fx.fn("a").args), "a1")
        self.assertIn(("a", "args_omitted"), fx.scans())

    def test_read_after_conditional_write_is_not_an_argument(self):
        # a3 is set on one path only and read after the merge: a must-analysis does not call it an argument.
        code = [beq(A0, ZERO, 2), NOP, addiu(A3, ZERO, 1), move(V0, A3), jr_ra(), NOP]
        fx = Fixture([("a", "int a(int x)", code)])
        self.assertEqual(scan.describe_args(fx.fn("a").args), "a0")

    def test_argument_passes_through_a_call(self):
        fx = Fixture([("inner", "int inner(int x, int y)", [move(V0, A1), jr_ra(), NOP]),
                      ("outer", "int outer(int x)", [j(0x1000), NOP])])
        self.assertIn(("outer", "args_omitted"), fx.scans())

    def test_void_read_by_caller(self):
        fx = Fixture([("callee", "void callee(void)", [addiu(V0, ZERO, 1), jr_ra(), NOP]),
                      ("caller", "int caller(void)", [jal(0x1000), NOP, move(A0, V0), sw(A0, 0, SP), jr_ra(), NOP])])
        self.assertIn(("callee", "void_read_by_callers"), fx.scans())

    def test_tail_call_alone_proves_no_return_value(self):
        fx = Fixture([("target", "int target(void)", [addiu(V0, ZERO, 1), jr_ra(), NOP]),
                      ("wrapper", "void wrapper(void)", [j(0x1000), NOP])])
        self.assertNotIn(("wrapper", "void_with_return_write"), fx.scans())

    def test_return_write_in_delay_slot(self):
        fx = Fixture([("a", "void a(void)", [jr_ra(), addiu(V0, ZERO, 1)])])
        self.assertIn(("a", "void_with_return_write"), fx.scans())

    def test_scratch_v0_is_not_a_return_value(self):
        fx = Fixture([("a", "void a(int *p)", [addiu(V0, ZERO, 1), sw(V0, 0, A0), jr_ra(), NOP])])
        self.assertEqual(fx.scans(), [])

    def test_stack_buffer_store_is_not_a_side_effect(self):
        fx = Fixture([("a", "int a(void)", [addiu(A0, SP, 8), sw(ZERO, 0, A0), jr_ra(), NOP])])
        scan.decode_function(fx.fn("a"))
        self.assertEqual(scan.stores_outside_stack(fx.fn("a")), [])
        fx = Fixture([("a", "int a(int *p)", [sw(ZERO, 0, A0), jr_ra(), NOP])])
        self.assertEqual(len(scan.stores_outside_stack(fx.fn("a"))), 1)


class SampleTests(unittest.TestCase):
    def rows(self, n, size):
        return [dict(id=f"{size}:{k}", name="f", group="g", size=size) for k in range(n)]

    def test_allocation_keeps_small_bands(self):
        rows = self.rows(500, 16) + self.rows(100, 300) + self.rows(10, 4000)
        groups, alloc = audit.allocate(rows, 40)
        self.assertEqual(sum(alloc.values()), 40)
        self.assertGreaterEqual(alloc["tiny"], 2)
        self.assertGreater(alloc["huge"] / 10, alloc["tiny"] / 500)

    def test_draw_is_reproducible_and_independent_of_other_strata(self):
        strata = {name: self.rows(200, 100) for name, _, _ in audit.STRATA}
        first = audit.draw(strata, seed=7)
        self.assertEqual(first, audit.draw(strata, seed=7))
        changed = dict(strata, duel_core=self.rows(150, 40))
        again = audit.draw(changed, seed=7)
        self.assertEqual([r["id"] for r in first if r["stratum"] == "ai"], [r["id"] for r in again if r["stratum"] == "ai"])

    def test_wilson(self):
        low, high = audit.wilson(0, 40)
        self.assertEqual(low, 0.0)
        self.assertAlmostEqual(high, 0.0876, places=3)
        low, high = audit.wilson(10, 40)
        self.assertTrue(low < 0.25 < high)

    def test_weighted_rate(self):
        rows = [dict(band_population=90, band_sample=9, hit=0)] * 9 + [dict(band_population=10, band_sample=1, hit=1)]
        p, low, high, n_eff = audit.weighted_rate(rows, lambda r: r["hit"])
        self.assertAlmostEqual(p, 0.1)
        self.assertAlmostEqual(n_eff, 10)


if __name__ == "__main__":
    unittest.main()
