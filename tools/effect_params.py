#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Extract the per-card effect parameters hidden in code in gmodule/rel_duel_eng.prx.

See docs/formats/effect-tables.md ("Per-card parameters in code"). Four CSV files are written to the
output directory (game data: keep them under extracted/, never in git):

  target_filters.csv       one row per slot +08 record whose handler is a stub that calls
                           duel_effects_target_filter with a constant flag word, decoded
  target_filter_calls.csv  other call sites that pass a constant flag word to the filter
  draw_counts.csv          duel_effects_get_draw_count: card id -> constant, or the computed cases
  compare_chains.csv       every function that is a chain of `if (id == K)` tests, with statistics
  chain_cases.csv          the per-card cases of the chains classified as parameter chains

  effect_params.py <USRDIR>/gmodule/rel_duel_eng.prx -o extracted/effect_params [--cardinfo <cardinfo_eng.ehp>]
  effect_params.py <USRDIR>/gmodule/rel_duel_eng.prx --check

Addresses are runtime addresses with the module at 0x09be1400 (file offset = address - base + 0x54
for the game's single PT_LOAD segment). Pointers and jump targets in the file are module offsets.
"""

import argparse
import bisect
import collections
import csv
import importlib.util
import struct
import sys
from pathlib import Path

BASE = 0x09BE1400
TEXT_END = 0x09DE415C  # .text ends here; .sceStub.text follows
FIRST_CARD, LAST_CARD = 3720, 7993

TABLES = [("S/T", 0x09DEDE78, 938), ("M1", 0x09DF3680, 869), ("M2", 0x09DF8810, 365), ("M3", 0x09DFAA60, 428)]
LISTS = [("L1", 0x09DEC554, 686), ("L2", 0x09DFD448, 528), ("L3", 0x09DFE500, 1120), ("L4", 0x09E010B0, 67)]
TARGET_FILTER = 0x09C32FB8
TARGET_FILTER_SIZE = 2020
DRAW_COUNT = 0x09C779BC
DRAW_COUNT_SIZE = 2228
POT_OF_GREED = 0x12EC

KNOWN_ADDRESSES = {  # labels for computed-case summaries (player 0 addresses; + player * 0xb3c)
    0x09E2A534: "hand size",
    0x09E2A538: "deck size",
    0x09E2A564: "field slot +08 (face-up)",
    0x09E2A562: "field slot +06 (position)",
    0x09E2A56C: "field slot +10 (flags)",
    0x09E28F80: "handler_08 recursion counter",
}

REG = ["zero", "at", "v0", "v1", "a0", "a1", "a2", "a3", "t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7",
       "s0", "s1", "s2", "s3", "s4", "s5", "s6", "s7", "t8", "t9", "k0", "k1", "gp", "sp", "fp", "ra"]
V0, A0, A3, SP, RA = 2, 4, 7, 29, 31

# ---------------------------------------------------------------------------------------------- image


class Module:
    """The PRX image: one PT_LOAD segment, module offset 0 at the segment's file offset."""

    def __init__(self, data, base=BASE):
        if data[:4] != b"\x7fELF":
            raise ValueError("not an ELF file")
        phoff, = struct.unpack_from("<I", data, 0x1C)
        phnum, = struct.unpack_from("<H", data, 0x2C)
        segments = []
        for i in range(phnum):
            ptype, off, vaddr, _, filesz, _ = struct.unpack_from("<6I", data, phoff + 32 * i)
            if ptype == 1:
                segments.append((off, vaddr, filesz))
        if not segments:
            raise ValueError("no PT_LOAD segment")
        self.data, self.base, self.segments = data, base, segments

    def offset(self, address):
        rel = address - self.base
        for off, vaddr, size in self.segments:
            if vaddr <= rel < vaddr + size:
                return off + rel - vaddr
        raise ValueError(f"address {address:#010x} outside the module")

    def word(self, address):
        return struct.unpack_from("<I", self.data, self.offset(address))[0]

    def words(self, address, count):
        return struct.unpack_from(f"<{count}I", self.data, self.offset(address))

    def contains(self, address):
        try:
            self.offset(address)
            return True
        except ValueError:
            return False

    def pointer(self, value):
        """A module offset stored in the file, as a runtime address (None if it is not inside .text)."""
        address = self.base + value
        return address if value and self.base <= address < TEXT_END and self.contains(address) else None


# ---------------------------------------------------------------------------------------------- decoder


class Insn:
    """Fields of one MIPS instruction word; `kind` names the few forms the analyses need."""

    __slots__ = ("w", "pc", "op", "rs", "rt", "rd", "sa", "fn", "imm", "simm", "kind", "_base")

    def __init__(self, w, pc, base=BASE):
        self.w, self.pc = w, pc
        self.op, self.rs, self.rt, self.rd = w >> 26, w >> 21 & 31, w >> 16 & 31, w >> 11 & 31
        self.sa, self.fn, self.imm = w >> 6 & 31, w & 63, w & 0xFFFF
        self.simm = self.imm - 0x10000 if self.imm & 0x8000 else self.imm
        self.kind = KINDS.get(self.op, "other") if self.op else SPECIAL.get(self.fn, "other")
        if self.op == 1:
            self.kind = "regimm"
        if w == 0:
            self.kind = "nop"
        self._base = base

    @property
    def target(self):
        """Jump target (j/jal, as a runtime address) or branch target."""
        if self.op in (2, 3):
            return self._base + ((self.w & 0x3FFFFFF) << 2)
        return self.pc + 4 + 4 * self.simm

    @property
    def is_branch(self):
        return self.op in (1, 4, 5, 6, 7, 0x14, 0x15, 0x16, 0x17)

    @property
    def likely(self):
        return self.op in (0x14, 0x15, 0x16, 0x17) or (self.op == 1 and self.rt in (2, 3))

    @property
    def writes(self):
        """Register written (None for stores, branches, jumps)."""
        if self.kind in ("addiu", "addi", "ori", "andi", "xori", "slti", "sltiu", "lui", "load"):
            return self.rt
        if self.op == 0 and self.fn not in (8, 0x18, 0x19, 0x1A, 0x1B, 0x0C, 0x0D) and self.w:
            return self.rd
        if self.op == 0x1F and self.fn in (0, 4):
            return self.rt
        if self.op == 0x1F and self.fn == 0x20:
            return self.rd
        if self.op == 3:
            return RA
        return None

    def text(self):
        """Short mnemonic form, for messages only."""
        r = REG
        if self.kind in ("addiu", "slti", "sltiu", "addi"):
            return f"{self.kind} {r[self.rt]},{r[self.rs]},{self.simm}"
        if self.kind in ("ori", "andi", "xori"):
            return f"{self.kind} {r[self.rt]},{r[self.rs]},{self.imm:#x}"
        if self.kind == "lui":
            return f"lui {r[self.rt]},{self.imm:#x}"
        if self.op in (2, 3):
            return f"{'j' if self.op == 2 else 'jal'} {self.target:#x}"
        return f"{self.kind} {self.w:08x}"


KINDS = {2: "j", 3: "jal", 4: "beq", 5: "bne", 6: "blez", 7: "bgtz", 8: "addi", 9: "addiu", 0x0A: "slti",
         0x0B: "sltiu", 0x0C: "andi", 0x0D: "ori", 0x0E: "xori", 0x0F: "lui", 0x14: "beql", 0x15: "bnel",
         0x16: "blezl", 0x17: "bgtzl", 0x20: "load", 0x21: "load", 0x23: "load", 0x24: "load", 0x25: "load",
         0x28: "store", 0x29: "store", 0x2B: "store"}
SPECIAL = {0: "sll", 2: "srl", 3: "sra", 8: "jr", 9: "jalr", 0x21: "addu", 0x23: "subu", 0x24: "and",
           0x25: "or", 0x26: "xor", 0x27: "nor", 0x2A: "slt", 0x2B: "sltu"}
LOAD_SIZE = {0x20: 1, 0x21: 2, 0x23: 4, 0x24: 1, 0x25: 2}


def insn(module, address):
    return Insn(module.word(address), address, module.base)


# ---------------------------------------------------------------------------------------------- evaluator


def _alu(i, regs):
    """Value written by a simple ALU instruction, or None if an operand is unknown or the form is not modelled."""
    s, t = regs.get(i.rs), regs.get(i.rt)
    k = i.kind
    if k == "lui":
        return (i.imm << 16) & 0xFFFFFFFF
    if k in ("addiu", "addi"):
        return None if s is None else (s + i.simm) & 0xFFFFFFFF
    if k == "ori":
        return None if s is None else s | i.imm
    if k == "andi":
        return None if s is None else s & i.imm
    if k == "xori":
        return None if s is None else s ^ i.imm
    if k == "sltiu":
        return None if s is None else int(s < (i.simm & 0xFFFFFFFF))
    if k == "slti":
        return None if s is None else int(signed(s) < i.simm)
    if k in ("sll", "srl", "sra"):
        if t is None:
            return None
        if k == "sll":
            return (t << i.sa) & 0xFFFFFFFF
        return t >> i.sa if k == "srl" else (signed(t) >> i.sa) & 0xFFFFFFFF
    if s is None or t is None:
        return None
    return {"addu": lambda: (s + t) & 0xFFFFFFFF, "subu": lambda: (s - t) & 0xFFFFFFFF, "and": lambda: s & t,
            "or": lambda: s | t, "xor": lambda: s ^ t, "nor": lambda: ~(s | t) & 0xFFFFFFFF,
            "slt": lambda: int(signed(s) < signed(t)), "sltu": lambda: int(s < t)}.get(k, lambda: None)()


def signed(v):
    return v - (1 << 32) if v & 0x80000000 else v


def _branch_taken(i, regs):
    """True/False when the branch condition is decidable from known registers, else None."""
    s, t = regs.get(i.rs), regs.get(i.rt)
    if i.op in (4, 0x14, 5, 0x15):
        if i.rs == i.rt:
            return i.op in (4, 0x14)
        if s is None or t is None:
            return None
        return (s == t) == (i.op in (4, 0x14))
    if s is None:
        return None
    v = signed(s)
    if i.op in (6, 0x16):
        return v <= 0
    if i.op in (7, 0x17):
        return v > 0
    if i.op == 1:
        return v < 0 if i.rt in (0, 2) else v >= 0 if i.rt in (1, 3) else None
    return None


def evaluate(module, start, regs=None, delay=None, limit=200):
    """Run straight-line code from `start` (optionally after executing the delay-slot instruction `delay`)
    until `jr ra`. Returns the constant in v0, or None when the result depends on anything not modelled
    (memory, calls, an undecidable branch)."""
    regs = dict(regs or {})
    regs[0] = 0

    def apply(i):
        if i.kind in ("store", "nop"):
            return True
        if i.kind == "load":
            if i.rs == SP:  # epilogue restores; the value no longer matters once v0 is set
                regs.pop(i.rt, None)
                return True
            return False
        if i.kind in ("jal", "jalr", "j", "jr") or i.is_branch:
            return False
        w = i.writes
        if w is None:
            return False
        value = _alu(i, regs)
        if value is None:
            return False
        if w:
            regs[w] = value
        return True

    if delay is not None and not apply(delay):
        return None
    pc = start
    for _ in range(limit):
        i = insn(module, pc)
        if i.kind == "jr" and i.rs == RA:
            nxt = insn(module, pc + 4)  # delay slot: usually the stack-pointer restore
            if nxt.writes not in (None, SP) and not apply(nxt):
                return None
            return regs.get(V0)
        if i.op == 2 or i.is_branch:
            taken = True if i.op == 2 else _branch_taken(i, regs)
            if taken is None:
                return None
            nxt = insn(module, pc + 4)
            if taken or not i.likely:
                if not apply(nxt):
                    return None
            pc = i.target if taken else pc + 8
            continue
        if not apply(i):
            return None
        pc += 4
    return None


def summarize(module, start, ctx_regs, delay=None, limit=96):
    """Mechanical summary of the code reachable from `start` (both ways at each branch, until `jr ra`):
    the context fields, globals and functions it reads or calls."""
    feats = []
    ctx_regs = dict(ctx_regs)  # register -> offset into the context structure
    seen, todo = set(), [start]
    consts = {}
    if delay is not None:
        feats += _features(delay, ctx_regs, consts)
    steps = 0
    while todo and steps < limit:
        pc = todo.pop(0)
        while steps < limit and pc not in seen:
            seen.add(pc)
            steps += 1
            i = insn(module, pc)
            if i.kind == "jr":
                feats += _features(insn(module, pc + 4), ctx_regs, consts)
                break
            feats += _features(i, ctx_regs, consts)
            if i.op == 2 or i.is_branch:
                feats += _features(insn(module, pc + 4), ctx_regs, consts)
                seen.add(pc + 4)
                if not (i.op == 4 and i.rs == i.rt == 0) and i.op != 2:
                    todo.append(pc + 8)
                pc = i.target
                continue
            pc += 4
    return "; ".join(dict.fromkeys(feats))


def _features(i, ctx_regs, consts):
    out = []
    if i.kind == "lui":
        consts[i.rt] = i.imm << 16
    elif i.kind == "addiu" and i.rs in consts:
        address = BASE + ((consts[i.rs] + i.simm) & 0xFFFFFFFF)
        consts[i.rt] = consts[i.rs] + i.simm
        label = KNOWN_ADDRESSES.get(address)
        out.append(f"global {address:#010x}" + (f" ({label})" if label else ""))
    elif i.writes in consts:
        consts.pop(i.writes)
    if i.kind == "load" and i.rs in ctx_regs:
        out.append(f"ctx+{ctx_regs[i.rs] + i.simm:#x} u{8 * LOAD_SIZE[i.op]}")
    if i.kind == "addiu" and i.rs in ctx_regs:
        ctx_regs[i.rt] = ctx_regs[i.rs] + i.simm
    elif i.writes in ctx_regs:
        del ctx_regs[i.writes]
    if i.kind == "jal":
        out.append(f"call {i.target:#010x}")
    return out


# ---------------------------------------------------------------------------------------------- tables


def table_records(module):
    """(table, index, card id, [5 handler addresses or None]) for the four 24-byte tables."""
    for name, address, count in TABLES:
        for index in range(count):
            rec = module.words(address + 24 * index, 6)
            yield name, index, rec[0], [module.pointer(v) for v in rec[1:]]


def list_records(module):
    for name, address, count in LISTS:
        for index in range(count):
            cid, handler = module.words(address + 8 * index, 2)
            yield name, index, cid, module.pointer(handler)


def filter_stub(module, address):
    """Decode a target-filter stub at `address`: (form, flags) or None.

    Forms: `j filter; addiu a3,zero,K` (K sign-extended), `j filter; ori a3,zero,K`,
    `lui r,HI; j filter; ori a3,r,LO` (and the same with addiu, which adds a sign-extended LO)."""
    i0, i1 = insn(module, address), insn(module, address + 4)
    if i0.op == 2 and i0.target == TARGET_FILTER and i1.rt == A3 and i1.rs == 0:
        if i1.kind == "addiu":
            return "addiu", i1.simm & 0xFFFFFFFF
        if i1.kind == "ori":
            return "ori", i1.imm
    i2 = insn(module, address + 8)
    if i0.kind == "lui" and i1.op == 2 and i1.target == TARGET_FILTER and i2.rt == A3 and i2.rs == i0.rt:
        if i2.kind == "ori":
            return "lui+ori", (i0.imm << 16) | i2.imm
        if i2.kind == "addiu":
            return "lui+addiu", ((i0.imm << 16) + i2.simm) & 0xFFFFFFFF
    return None


# The flag word of duel_effects_target_filter(ctx, player, index, flags); see effect-tables.md.
SIDES = {0: "any", 1: "own", 2: "opponent", 3: "tributable"}
ZONES = {0x00: "any", 0x10: "monster", 0x20: "spell", 0x30: "trap", 0x40: "spell_trap", 0x50: "st_zone",
         0x60: "any", 0x70: "any"}
ACTION_BITS = [(0x400, "targeted"), (0x800, "no_immunity_check"), (0x1000, "destroy"), (0x2000, "banish"),
               (0x4000, "send_to_graveyard"), (0x8000, "bit15"), (0x10000, "take_control"),
               (0x20000, "not_self"), (0x40000, "change_position"), (0x80000, "return")]
KNOWN_BITS = 0x3 | 0x4 | 0x8 | 0x70 | 0x80 | 0x100 | sum(b for b, _ in ACTION_BITS)


def decode_flags(flags):
    face = "face_up" if flags & 4 else "face_down" if flags & 8 else ""
    position = "attack" if flags & 0x80 else "defense" if flags & 0x100 else ""
    actions = [name for bit, name in ACTION_BITS if flags & bit]
    if flags & ~KNOWN_BITS & 0xFFFFFFFF:
        actions.append(f"unknown_{flags & ~KNOWN_BITS & 0xFFFFFFFF:#x}")
    return {"side": SIDES[flags & 3], "zone": ZONES[flags & 0x70], "face": face, "position": position,
            "actions": " ".join(actions)}


def handler_users(module):
    """Runtime handler address -> list of 'table:slot:card id' that reference it."""
    users = collections.defaultdict(list)
    for name, _, cid, handlers in table_records(module):
        for slot, h in enumerate(handlers):
            if h:
                users[h].append(f"{name}:+{4 * slot + 4:02x}:{cid:#x}")
    for name, _, cid, h in list_records(module):
        if h:
            users[h].append(f"{name}:{cid:#x}")
    return users


def target_filters(module):
    rows = []
    for name, index, cid, handlers in table_records(module):
        h = handlers[1]
        stub = filter_stub(module, h) if h else None
        if stub:
            rows.append({"table": name, "index": index, "card_id": f"{cid:#x}", "handler": f"{h:#010x}",
                         "form": stub[0], "flags": f"{stub[1]:#07x}", **decode_flags(stub[1])})
    return rows


def target_filter_calls(module, functions, users):
    """Direct `jal filter` sites whose a3 is a constant set in the delay slot or just before."""
    rows = []
    for pc in range(module.base, TEXT_END, 4):
        i = insn(module, pc)
        if i.op != 3 or i.target != TARGET_FILTER:
            continue
        flags = None
        for q in (pc + 4, pc - 4, pc - 8):
            j = insn(module, q)
            if j.writes == A3:
                if j.kind in ("addiu", "ori") and j.rs == 0:
                    flags = j.simm & 0xFFFFFFFF if j.kind == "addiu" else j.imm
                elif j.kind == "ori":
                    hi = insn(module, q - 4)
                    if hi.kind == "lui" and hi.rt == j.rs:
                        flags = hi.imm << 16 | j.imm
                break
        func = containing(functions, pc)
        rows.append({"call_site": f"{pc:#010x}", "function": f"{func:#010x}" if func else "",
                     "flags": "" if flags is None else f"{flags:#07x}",
                     **(decode_flags(flags) if flags is not None else
                        {"side": "", "zone": "", "face": "", "position": "", "actions": ""}),
                     "referenced_by": " ".join(users.get(func, []))})
    return rows


# ---------------------------------------------------------------------------------------------- functions


def function_starts(module):
    """Function entry points: jal targets, handler pointers, and prologues right after a `jr ra`."""
    starts = set()
    for pc in range(module.base, TEXT_END, 4):
        i = insn(module, pc)
        if i.op == 3 and module.base <= i.target < TEXT_END:
            starts.add(i.target)
        if i.kind == "jr" and i.rs == RA and pc + 8 < TEXT_END:
            nxt = insn(module, pc + 8)
            if nxt.kind == "addiu" and nxt.rt == SP and nxt.rs == SP and nxt.simm < 0:
                starts.add(pc + 8)
    for _, _, _, handlers in table_records(module):
        starts.update(h for h in handlers if h)
    for _, _, _, h in list_records(module):
        if h:
            starts.add(h)
    starts.add(module.base)
    return sorted(starts)


def containing(functions, address):
    k = bisect.bisect_right(functions, address) - 1
    return functions[k] if k >= 0 else None


def function_end(functions, start):
    k = bisect.bisect_right(functions, start)
    return functions[k] if k < len(functions) else TEXT_END


def ctx_aliases(module, start, stop):
    """Registers that hold the first argument (a0) when the chain starts."""
    regs = {A0: 0}
    for pc in range(start, stop, 4):
        i = insn(module, pc)
        if i.kind in ("addu", "or") and i.rs in regs and i.rt == 0:
            regs[i.rd] = regs[i.rs]
        elif i.writes in regs:
            del regs[i.writes]
        if i.kind == "jal":  # the callee may clobber argument and temporary registers
            for r in [r for r in regs if 2 <= r <= 15 or r in (24, 25)]:
                del regs[r]
    return regs


def chain_cases(module, start, end):
    """The `li rX, K; beq/beql rY, rX, T` (or `beq rX, rY`) tests in [start, end) with K a card id.
    Yields (address of the li, card id, branch instruction)."""
    for pc in range(start, end - 4, 4):
        a, b = insn(module, pc), insn(module, pc + 4)
        if a.kind in ("addiu", "ori") and a.rs == 0 and FIRST_CARD <= a.imm <= LAST_CARD and \
                b.op in (4, 0x14) and a.rt in (b.rs, b.rt) and b.rs != b.rt:
            yield pc, a.imm, b


def case_value(module, branch, regs=None):
    """Evaluate the code a taken chain branch leads to: the returned constant or None."""
    return evaluate(module, branch.target, regs=regs, delay=insn(module, branch.pc + 4))


def analyse_chain(module, start, end):
    """Per-case results of a compare chain: list of (card id, value or None, branch target)."""
    out, seen = [], set()
    for _, cid, b in chain_cases(module, start, end):
        if cid in seen:
            continue
        seen.add(cid)
        out.append((cid, case_value(module, b), b))
    return out


def draw_counts(module):
    start, end = DRAW_COUNT, DRAW_COUNT + DRAW_COUNT_SIZE
    cases = list(chain_cases(module, start, end))
    first = cases[0][0] if cases else end
    aliases = ctx_aliases(module, start, first)
    rows = []
    for cid, value, b in analyse_chain(module, start, end):
        rows.append({"card_id": f"{cid:#x}", "kind": "constant" if value is not None else "computed",
                     "value": "" if value is None else signed(value), "target": f"{b.target:#010x}",
                     "summary": "" if value is not None else
                     summarize(module, b.target, aliases, delay=insn(module, b.pc + 4))})
    return rows


def compare_chains(module, functions, users, min_cases=8):
    """Every function with at least `min_cases` card-id tests, with statistics and callers."""
    callers = collections.defaultdict(set)
    for pc in range(module.base, TEXT_END, 4):
        i = insn(module, pc)
        if i.op == 3 and module.base <= i.target < TEXT_END:
            f = containing(functions, pc)
            if f is not None:
                callers[i.target].add(f)
    rows, cases_out = [], []
    for start in functions:
        if start >= TEXT_END:
            continue
        end = function_end(functions, start)
        ids = {cid for _, cid, _ in chain_cases(module, start, end)}
        if len(ids) < min_cases:
            continue
        cases = analyse_chain(module, start, end)
        values = collections.Counter(signed(v) for _, v, _ in cases if v is not None)
        constant = sum(values.values())
        parameter = constant >= len(cases) / 2 and len(values) >= 2 and not set(values) <= {0, 1}
        cs = sorted(callers.get(start, ()))
        handler_callers = [c for c in cs if c in users]
        rows.append({"function": f"{start:#010x}", "size": end - start, "cases": len(cases),
                     "constant_cases": constant, "distinct_values": len(values),
                     "values": " ".join(f"{v}x{n}" for v, n in sorted(values.items())),
                     "class": "parameter" if parameter else "unresolved" if constant < len(cases) / 2 else
                     "predicate" if set(values) <= {0, 1} else "mixed",
                     "density": round(12 * len(cases) / max(1, end - start), 2),
                     "callers": " ".join(f"{c:#010x}" for c in cs[:12]) + (" ..." if len(cs) > 12 else ""),
                     "caller_count": len(cs), "handler_callers": len(handler_callers),
                     "handler_cards": sum(len(users[c]) for c in handler_callers)})
        if parameter:
            for cid, v, b in cases:
                cases_out.append({"function": f"{start:#010x}", "card_id": f"{cid:#x}",
                                  "kind": "constant" if v is not None else "computed",
                                  "value": "" if v is None else signed(v), "target": f"{b.target:#010x}"})
    return rows, cases_out


# ---------------------------------------------------------------------------------------------- checks


def check(module):
    """Structural checks that the addresses above match this module; returns a list of problems."""
    problems = []
    for name, address, count in TABLES:
        ids = [module.words(address + 24 * i, 1)[0] for i in range(count)]
        if ids != sorted(ids):
            problems.append(f"table {name} at {address:#x} is not sorted by card id")
        if not all(0 < cid < 0x4000 for cid in ids[:8]):
            problems.append(f"table {name} at {address:#x} does not start with card ids")
    head = [insn(module, TARGET_FILTER + 4 * k) for k in range(12)]
    if not (head[0].kind == "addiu" and head[0].rt == SP and head[0].simm < 0) or \
            not any(i.kind == "andi" and i.imm == 3 for i in head):
        problems.append(f"no target-filter prologue at {TARGET_FILTER:#x}")
    end = insn(module, TARGET_FILTER + TARGET_FILTER_SIZE - 8)
    if not (end.kind == "jr" and end.rs == RA):
        problems.append("target filter does not end where expected")
    stubs = target_filters(module)
    if not stubs:
        problems.append("no target-filter stubs found in slot +08")
    end = insn(module, DRAW_COUNT + DRAW_COUNT_SIZE - 8)
    if not (end.kind == "jr" and end.rs == RA):
        problems.append("draw-count chain does not end where expected")
    pog = [r for r in draw_counts(module) if int(r["card_id"], 16) == POT_OF_GREED]
    if not pog or pog[0]["value"] != 2:
        problems.append("draw-count chain does not map Pot of Greed (0x12ec) to 2")
    return problems


# ---------------------------------------------------------------------------------------------- main


def load_names(path):
    spec = importlib.util.spec_from_file_location("re_cardinfo", Path(__file__).resolve().parent / "cardinfo.py")
    cardinfo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cardinfo)
    info = cardinfo.CardInfo(Path(path).read_bytes(), "E")
    names = {}
    for index in range(1, info.count):
        names[info.properties(index)["id"]] = info.name(index)
    return names


def write_csv(path, rows, names=None):
    if names is not None:
        for r in rows:
            if "card_id" in r:
                r["name"] = names.get(int(r["card_id"], 16), "")
    fields = list(rows[0]) if rows else ["empty"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Extract per-card effect parameters from rel_duel_eng.prx.")
    parser.add_argument("prx", type=Path, help="gmodule/rel_duel_eng.prx")
    parser.add_argument("-o", "--out", type=Path, help="output directory (under extracted/)")
    parser.add_argument("--check", action="store_true", help="only run the structural checks")
    parser.add_argument("--cardinfo", type=Path, help="duelsys/cardinfo_eng.ehp: add a card-name column")
    args = parser.parse_args(argv)
    module = Module(args.prx.read_bytes())
    problems = check(module)
    for p in problems:
        print("problem:", p, file=sys.stderr)
    if args.check:
        print("ok" if not problems else f"{len(problems)} problem(s)")
        return 1 if problems else 0
    if not args.out:
        parser.error("-o/--out is required unless --check is given")
    names = load_names(args.cardinfo) if args.cardinfo else None
    args.out.mkdir(parents=True, exist_ok=True)
    functions = function_starts(module)
    users = handler_users(module)
    filters = target_filters(module)
    calls = target_filter_calls(module, functions, users)
    draws = draw_counts(module)
    chains, cases = compare_chains(module, functions, users)
    write_csv(args.out / "target_filters.csv", filters, names)
    write_csv(args.out / "target_filter_calls.csv", calls)
    write_csv(args.out / "draw_counts.csv", draws, names)
    write_csv(args.out / "compare_chains.csv", chains)
    write_csv(args.out / "chain_cases.csv", cases, names)
    forms = collections.Counter(r["form"] for r in filters)
    print(f"target filters: {len(filters)} records ({', '.join(f'{k} {v}' for k, v in forms.items())}), "
          f"{len({r['flags'] for r in filters})} distinct flag words")
    print(f"direct filter calls: {len(calls)} ({sum(1 for r in calls if r['flags'])} with a constant)")
    print(f"draw counts: {sum(r['kind'] == 'constant' for r in draws)} constant, "
          f"{sum(r['kind'] == 'computed' for r in draws)} computed")
    print(f"compare chains: {len(chains)} functions with >= 8 card-id tests, "
          f"{sum(r['class'] == 'parameter' for r in chains)} parameter chains ({len(cases)} cases)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
