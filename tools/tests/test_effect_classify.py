#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/effect_classify.py on a synthetic module. Run with: python3 -I tools/tests/test_effect_classify.py"""

import contextlib
import csv
import importlib.util
import io
import struct
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_effect_classify",
                                              Path(__file__).resolve().parents[1] / "effect_classify.py")
ec = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ec)

BASE = ec.BASE
ZERO, V0, A0, A1, A3, SP, RA = 0, 2, 4, 5, 7, 29, 31
FULL = 0xFFFFFFFF


def itype(op, rs, rt, imm):
    return op << 26 | rs << 21 | rt << 16 | (imm & 0xFFFF)


def addiu(rt, rs, imm):
    return itype(9, rs, rt, imm)


def ori(rt, rs, imm):
    return itype(0x0D, rs, rt, imm)


def andi(rt, rs, imm):
    return itype(0x0C, rs, rt, imm)


def lui(rt, imm):
    return itype(0x0F, 0, rt, imm)


def sw(rt, base, off):
    return itype(0x2B, base, rt, off)


def addu(rd, rs, rt):
    return rs << 21 | rt << 16 | rd << 11 | 0x21


def sll(rd, rt, sa):
    return rt << 16 | rd << 11 | sa << 6


def jump(op, target):
    return op << 26 | (target - BASE) >> 2


def branch(op, rs, rt, pc, target):
    return itype(op, rs, rt, (target - pc - 4) >> 2)


JR_RA = RA << 21 | 8
PUSH = 0x09C40000      # duel_core_push_command (a leaf: queue)
PUSH_THUNK = 0x09C40010  # j PUSH; nop
DRAW = 0x09C40020      # duel_core_draw_cards
FILTER = 0x09C40030    # duel_effects_target_filter
STUB = 0x09C40040      # j FILTER; addiu a3,zero,0x1410 (a slot +08 stub)
MERGE = 0x09C40100     # side bit chosen on two paths, then op | 0x3e posted
CALLS = 0x09C40200     # jal DRAW with a0 = 5; then jal UNNAMED (a0 clobbered); tail call to FILTER
UNNAMED = 0x09C40300   # FUN_: calls DRAW
BATCH = 0x09C40400     # FUN_: stores the batch destination 0x0f (banished)
H_DEEP = 0x09C40500    # handler: jal UNNAMED (draw only at depth 2)
H_BATCH = 0x09C40600   # handler: jal BATCH
END = 0x09C40700       # last registry entry

REGISTRY = {PUSH: "duel_core_push_command", PUSH_THUNK: "thunk_duel_core_push_command", DRAW: "duel_core_draw_cards",
            FILTER: "duel_effects_target_filter", STUB: "FUN_09c40040", MERGE: "FUN_09c40100",
            CALLS: "FUN_09c40200", UNNAMED: "FUN_09c40300", BATCH: "FUN_09c40400", H_DEEP: "FUN_09c40500",
            H_BATCH: "FUN_09c40600", END: "FUN_09c40700"}

MAPPING = """kind,pattern,category,role,note
# a comment
name,^duel_core_push_command$,,queue,
name,^duel_effects_target_filter$,,stop,
name,^duel_core_draw_cards,draw,effect,
name,^duel_core_,,stop,
cmd,0x3e,move_list_card,effect,
arg,^duel_effects_target_filter$|a3&0x1000,destroy,effect,
arg,^duel_effects_target_filter$|a3&0x400,targets,meta,
store,0x09e2d2b8=0x0f,banish,effect,
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
    img.put(PUSH, JR_RA, 0)
    img.put(PUSH_THUNK, jump(2, PUSH), 0)
    img.put(DRAW, JR_RA, 0)
    img.put(FILTER, JR_RA, 0)
    img.put(STUB, jump(2, FILTER), addiu(A3, ZERO, 0x1410))
    m = MERGE  # a1 == 0 -> v0 = 0 (likely delay slot), else v0 = 0x8000; op = v0 | 0x3e
    img.put(m, addiu(SP, SP, -16), branch(0x14, A1, ZERO, m + 4, m + 16), addu(V0, ZERO, ZERO),
            ori(V0, ZERO, 0x8000), ori(V0, V0, 0x3E), andi(A0, V0, 0xFFFF), jump(3, PUSH_THUNK), 0,
            JR_RA, addiu(SP, SP, 16))
    c = CALLS
    img.put(c, addiu(SP, SP, -16), jump(3, DRAW), addiu(A0, ZERO, 5), jump(3, UNNAMED), 0,
            addiu(SP, SP, 16), jump(2, FILTER), addiu(A3, ZERO, 0x1410))
    img.put(UNNAMED, jump(3, DRAW), 0, JR_RA, 0)
    # BATCH: lui v1,0x25 ; addiu a0,zero,0xf ; sw a0,-0x4148(v1)  -> module offset 0x24beb8 = 0x09e2d2b8
    img.put(BATCH, lui(3, 0x25), addiu(A0, ZERO, 0xF), sw(A0, 3, 0xBEB8 - 0x10000), JR_RA, 0)
    img.put(H_DEEP, jump(3, UNNAMED), 0, JR_RA, 0)
    img.put(H_BATCH, jump(3, BATCH), 0, JR_RA, 0)
    img.put(END, JR_RA, 0)
    # effect tables: sorted ids; S/T records 0-3 carry the test handlers
    for name, address, count in ec.TABLES:
        for i in range(count):
            img.put(address + 24 * i, 0x1300 + i, 0, 0, 0, 0, 0)
    st = ec.TABLES[0][1]
    img.put(st, 0x1300, CALLS - BASE, STUB - BASE, 0, 0, 0)
    img.put(st + 24, 0x1301, MERGE - BASE, 0, 0, 0, 0)
    img.put(st + 48, 0x1302, H_DEEP - BASE, 0, 0, 0, 0)
    img.put(st + 72, 0x1303, H_BATCH - BASE, 0, 0, 0, 0)
    return img.elf()


def classifier(depth=3):
    module = ec.ep.Module(build())
    registry = ec.Registry(dict(REGISTRY), module)
    mapping = ec.Mapping.load_text(MAPPING)
    return ec.Classifier(module, registry, mapping, depth)


class KnownBitsTest(unittest.TestCase):
    def test_ops(self):
        self.assertEqual(ec.kb_or((0, 0), ec.const(0x3E)), (0x3E, 0x3E))
        self.assertEqual(ec.kb_and((0, 0), ec.const(0xFFFF)), (0xFFFF0000, 0))
        self.assertEqual(ec.kb_sll((0, 0), 15), (0x7FFF, 0))
        self.assertEqual(ec.kb_meet(ec.const(0), ec.const(0x8000)), (FULL ^ 0x8000, 0))
        self.assertEqual(ec.kb_add(ec.const(3), ec.const(4)), (FULL, 7))
        self.assertIsNone(ec.kb_add((0xFFFFFFFE, 0), ec.const(1)))

    def test_apply(self):
        regs = {}
        ec.apply(regs, lui(V0, 0x8))
        ec.apply(regs, ori(A3, V0, 0x412))
        self.assertEqual(regs[A3], (FULL, 0x80412))
        ec.apply(regs, itype(0x23, SP, A3, 0))  # lw a3, 0(sp) kills a3
        self.assertNotIn(A3, regs)


class ScanTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cl = classifier()

    def test_jal_and_delay_slot_constant(self):
        calls = self.cl.calls(CALLS)
        self.assertEqual([(c.kind, c.target) for c in calls],
                         [("call", DRAW), ("call", UNNAMED), ("tail", FILTER)])
        self.assertEqual(calls[0].args[A0], (FULL, 5))
        self.assertNotIn(A0, calls[1].args)  # clobbered by the first call
        self.assertEqual(calls[2].args[A3], (FULL, 0x1410))

    def test_merge_keeps_common_bits(self):
        call, = self.cl.calls(MERGE)
        a0 = call.args[A0]
        self.assertEqual(a0[0] & 0xFFF, 0xFFF)
        self.assertEqual(a0[1] & 0xFFF, 0x3E)
        self.assertFalse(a0[0] & 0x8000)  # the side bit differs between the two paths

    def test_thunk_resolution(self):
        call, = self.cl.calls(MERGE)
        self.assertEqual(self.cl.resolve(call.target, call.args)[0], PUSH)
        target, args = self.cl.resolve(STUB, {})
        self.assertEqual((target, args[A3]), (FILTER, (FULL, 0x1410)))

    def test_stores(self):
        self.assertEqual(self.cl.stores(BATCH), [(0x09E2D2B8, 4, 0xF)])


class ClassifyTest(unittest.TestCase):
    def test_categories(self):
        cl = classifier()
        self.assertEqual(cl.closure(CALLS)["categories"], {("draw", "effect"), ("destroy", "effect"),
                                                           ("targets", "meta")})
        merge = cl.closure(MERGE)
        self.assertEqual((merge["categories"], merge["commands"]), ({("move_list_card", "effect")}, {0x3E}))
        self.assertEqual(cl.closure(H_BATCH)["categories"], {("banish", "effect")})
        self.assertEqual(cl.closure(STUB)["categories"], {("destroy", "effect"), ("targets", "meta")})

    def test_depth_and_unnamed(self):
        self.assertEqual(classifier(1).closure(H_DEEP)["categories"], set())
        deep = classifier(2).closure(H_DEEP)
        self.assertEqual(deep["categories"], {("draw", "effect")})
        self.assertEqual(deep["unnamed"], {UNNAMED})
        self.assertEqual(deep["callees"][DRAW], ("duel_core_draw_cards", 2))

    def test_first_name_row_wins(self):
        mapping = ec.Mapping.load_text(MAPPING)
        self.assertEqual(mapping.lookup(DRAW, "duel_core_draw_cards"), ("draw", "effect"))
        self.assertEqual(mapping.lookup(0, "duel_core_get_atk"), ("", "stop"))
        self.assertIsNone(mapping.lookup(0, "FUN_09c40300"))

    def test_records_coverage_worklist(self):
        rows, facts = ec.classify_records(classifier())
        first = rows[0]
        self.assertEqual((first["card_id"], first["resolve"], first["target_filter"]),
                         ("0x1300", "destroy draw targets", "destroy targets"))
        self.assertEqual(rows[1]["commands"], "0x3e")
        cov = ec.coverage(facts)
        self.assertEqual((cov["with_resolve"], cov["resolve_covered"]), (4, 4))
        work = ec.worklist(facts)
        self.assertEqual(work[0]["address"], f"{UNNAMED:#010x}")
        self.assertEqual(work[0]["records"], 2)

    def test_check_tables(self):
        cl = classifier()
        problems, queue = ec.check(cl.module, cl.registry, cl.mapping)
        self.assertEqual([p for p in problems if not p.startswith("AI tables")], [])
        self.assertEqual(queue, [PUSH, PUSH_THUNK])

    def test_main_writes_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            prx = tmp / "rel_duel_eng.prx"
            prx.write_bytes(build())
            functions = tmp / "functions.csv"
            with open(functions, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["id", "name", "group", "status", "size"])
                for a, n in REGISTRY.items():
                    w.writerow([f"{a:#010x}", n, "", "", ""])
            categories = tmp / "categories.csv"
            categories.write_text(MAPPING, encoding="utf-8")
            out = tmp / "out"
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                ec.main([str(prx), "-o", str(out), "--functions", str(functions), "--categories", str(categories)])
            for name in ("effect_classes.csv", "worklist.csv", "ai_clusters.csv", "summary.txt"):
                self.assertTrue((out / name).exists(), name)
            self.assertIn("coverage", (out / "summary.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
