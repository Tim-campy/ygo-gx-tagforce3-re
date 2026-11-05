#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Instruction-level checks of the documented prototypes, and a reading aid for the audit.

The input is the directory written by tools/ghidra/ExportAuditData.java (relocated images, function bodies,
references, decompilation). That directory holds game code and stays outside the repository.

    doc_audit_scan.py DB scan -o hits.jsonl     # all mechanical scans over all documented functions
    doc_audit_scan.py DB dossier <id>...        # one function: row, disassembly, callers, callees, decompilation
    doc_audit_scan.py DB dis <program> <addr> <bytes>

Register conventions (PSP gcc, MIPS EABI with hardware floats): integer arguments a0-a3, t0-t3, then the stack;
float arguments f12-f19; results v0 (v1 for the high word), f0. docs/verification/documentation-quality-audit.md
explains each scan and its false-positive limits.
"""
import argparse
import bisect
import csv
import glob
import json
import os
import re
import struct
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # noqa: the tools are run from the repository
from doc_audit import load_documented, load_registry  # noqa: E402

REG = ["zero", "at", "v0", "v1", "a0", "a1", "a2", "a3", "t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7",
       "s0", "s1", "s2", "s3", "s4", "s5", "s6", "s7", "t8", "t9", "k0", "k1", "gp", "sp", "fp", "ra"]
V0, V1, A0, T0, SP, RA, F0, F12 = 2, 3, 4, 8, 29, 31, 32, 44
HILO = 64  # one pseudo register for hi and lo
INT_ARGS = [4, 5, 6, 7, 8, 9, 10, 11]
FLOAT_ARGS = [F12 + i for i in range(8)]
ARG_MASK = sum(1 << r for r in INT_ARGS + FLOAT_ARGS)
# Everything a call may change (o32/EABI caller-saved integer and float registers).
CLOBBER = sum(1 << r for r in [1, 2, 3] + list(range(4, 16)) + [24, 25, 31] + [32 + i for i in range(20)] + [HILO])
RESULT_MASK = (1 << V0) | (1 << V1) | (1 << F0)


class Ins:
    """Decoded instruction: register sets as bit masks, kind, target, and stack access if any."""
    __slots__ = ("word", "reads", "writes", "kind", "target", "likely", "store", "load", "base", "off", "imm")

    def __init__(self, word):
        self.word = word
        self.reads = self.writes = 0
        self.kind = "op"
        self.target = None
        self.likely = False
        self.store = self.load = False
        self.base = self.off = None
        self.imm = None


def bits(*regs):
    mask = 0
    for r in regs:
        if r:  # register zero never carries a value
            mask |= 1 << r
    return mask


def decode(word, pc):
    """Decode one Allegrex word into register effects. VFPU registers are not tracked (only their integer
    transfers and addressing); an unknown word is an `op` with no effects."""
    i = Ins(word)
    op, rs, rt, rd = word >> 26, word >> 21 & 31, word >> 16 & 31, word >> 11 & 31
    sa, fn = word >> 6 & 31, word & 63
    imm = word & 0xFFFF
    simm = imm - 0x10000 if imm & 0x8000 else imm
    branch = (pc + 4 + (simm << 2)) & 0xFFFFFFFF
    if op == 0:
        if fn in (0, 2, 3):
            i.reads, i.writes = bits(rt), bits(rd)
        elif fn in (4, 6, 7):
            i.reads, i.writes = bits(rs, rt), bits(rd)
        elif fn == 8:
            i.kind, i.reads = ("ret" if rs == RA else "ijump"), bits(rs)
        elif fn == 9:
            i.kind, i.reads, i.writes = "calli", bits(rs), bits(rd)
        elif fn in (10, 11):
            i.reads, i.writes = bits(rs, rt, rd), bits(rd)
        elif fn in (12, 13):
            i.kind = "trap"
        elif fn == 15:
            pass
        elif fn in (16, 18):
            i.reads, i.writes = 1 << HILO, bits(rd)
        elif fn in (17, 19):
            i.reads, i.writes = bits(rs), 1 << HILO
        elif fn in (22, 23):  # clz, clo
            i.reads, i.writes = bits(rs), bits(rd)
        elif fn in (24, 25, 26, 27):
            i.reads, i.writes = bits(rs, rt), 1 << HILO
        elif fn in (28, 29, 46, 47):  # madd, maddu, msub, msubu
            i.reads, i.writes = bits(rs, rt) | 1 << HILO, 1 << HILO
        elif 32 <= fn <= 45:  # arithmetic, slt, max, min
            i.reads, i.writes = bits(rs, rt), bits(rd)
    elif op == 1:
        i.reads = bits(rs)
        i.kind = "branch"
        i.target = branch
        if rt in (2, 3, 18, 19):
            i.likely = True
        if rt in (16, 17, 18, 19):
            i.kind, i.writes = "call", bits(RA)
    elif op in (2, 3):
        i.target = (pc & 0xF0000000) | (word & 0x3FFFFFF) << 2
        i.kind = "jump" if op == 2 else "call"
    elif op in (4, 5, 6, 7, 20, 21, 22, 23):
        i.kind, i.target, i.likely = "branch", branch, op >= 20
        i.reads = bits(rs, rt) if op in (4, 5, 20, 21) else bits(rs)
        if op in (4, 20) and rs == rt:  # `b target`: there is no fall-through
            i.kind, i.likely = "jump", False
    elif 8 <= op <= 14:
        i.reads, i.writes, i.imm = bits(rs), bits(rt), simm
    elif op == 15:
        i.writes, i.imm = bits(rt), imm << 16
    elif op == 16:
        if rs == 0:
            i.writes = bits(rt)
        elif rs == 4:
            i.reads = bits(rt)
    elif op == 17:
        ft, fs, fd = 32 + rt, 32 + rd, 32 + sa
        if rs in (0, 2):
            i.reads, i.writes = (1 << fs if rs == 0 else 0), bits(rt)
        elif rs in (4, 6):
            i.reads, i.writes = bits(rt), (1 << fs if rs == 4 else 0)
        elif rs == 8:
            i.kind, i.target, i.likely = "branch", branch, bool(rt & 2)
        elif rs in (16, 20):
            if fn < 4:
                i.reads, i.writes = 1 << fs | 1 << ft, 1 << fd
            elif fn >= 48:
                i.reads = 1 << fs | 1 << ft
            else:
                i.reads, i.writes = 1 << fs, 1 << fd
    elif op == 18:
        if rs == 3:
            i.writes = bits(rt)
        elif rs == 7:
            i.reads = bits(rt)
        elif rs == 8:
            i.kind, i.target, i.likely = "branch", branch, bool(rt & 2)
    elif op == 31:
        if fn == 0:
            i.reads, i.writes = bits(rs), bits(rt)
        elif fn == 4:
            i.reads, i.writes = bits(rs, rt), bits(rt)
        elif fn == 32:
            i.reads, i.writes = bits(rt), bits(rd)
    elif 32 <= op <= 38 or op == 48:
        i.reads, i.writes, i.load, i.base, i.off = bits(rs), bits(rt), True, rs, simm
        if op in (34, 38):
            i.reads |= bits(rt)
    elif 40 <= op <= 46 or op == 56:
        i.reads, i.store, i.base, i.off = bits(rs, rt), True, rs, simm
    elif op == 49:
        i.reads, i.writes, i.load, i.base, i.off = bits(rs), 1 << (32 + rt), True, rs, simm
    elif op == 57:
        i.reads, i.store, i.base, i.off = bits(rs) | 1 << (32 + rt), True, rs, simm
    elif op in (50, 53, 54):  # lv.s, lvl/lvr.q, lv.q
        i.reads, i.load, i.base, i.off = bits(rs), True, rs, simm & ~3
    elif op in (58, 61, 62):  # sv.s, svl/svr.q, sv.q
        i.reads, i.store, i.base, i.off = bits(rs), True, rs, simm & ~3
    return i


class Func:
    __slots__ = ("program", "entry", "name", "group", "thunk", "size", "ranges", "ret", "nparams", "proto",
                 "ins", "args", "stack_args", "ret_evidence", "ret_defined", "row", "sites", "indirect", "frame",
                 "fpass", "sp_unknown")

    def __init__(self, program, parts):
        entry, self.name, self.group, thunk, size, body, self.ret, nparams, self.proto = parts[:9]
        self.program, self.entry = program, int(entry, 16)
        self.thunk = int(thunk, 16) if thunk else None
        self.size, self.nparams = int(size), int(nparams)
        self.ranges = [tuple(int(x, 16) for x in r.split("-")) for r in body.split(";") if r]
        self.ins, self.args, self.stack_args = None, 0, 0
        self.ret_evidence = self.ret_defined = False
        self.row, self.sites, self.indirect, self.frame = None, [], 0, 0
        self.fpass, self.sp_unknown = False, False

    def contains(self, addr):
        return any(lo <= addr <= hi for lo, hi in self.ranges)


class Program:
    def __init__(self, stem):
        self.name = os.path.basename(stem)
        self.blocks = []
        with open(stem + ".mem", "rb") as handle:
            self.mem = handle.read()
        with open(stem + ".map", encoding="utf-8") as handle:
            for line in handle:
                start, length, pos, name, perm = line.rstrip("\n").split("\t")
                self.blocks.append((int(start, 16), int(length), int(pos), name, perm))
        self.funcs = {}
        with open(stem + ".fn.tsv", encoding="utf-8") as handle:
            for line in handle:
                f = Func(self, line.rstrip("\n").split("\t"))
                self.funcs[f.entry] = f
        self.xrefs = defaultdict(list)
        with open(stem + ".xref.tsv", encoding="utf-8") as handle:
            for line in handle:
                to, frm, in_fn, kind = line.rstrip("\n").split("\t")
                self.xrefs[int(to, 16)].append((int(frm, 16), int(in_fn, 16) if in_fn else None, kind))
        self.entries = sorted(self.funcs)

    def word(self, addr):
        for start, length, pos, _, _ in self.blocks:
            if start <= addr < start + length - 3:
                return struct.unpack_from("<I", self.mem, pos + addr - start)[0]
        return None

    def data(self, addr, size):
        for start, length, pos, _, _ in self.blocks:
            if start <= addr < start + length:
                return self.mem[pos + addr - start:pos + addr - start + size]
        return b""

    def containing(self, addr):
        k = bisect.bisect_right(self.entries, addr) - 1
        if k >= 0:
            f = self.funcs[self.entries[k]]
            if f.contains(addr):
                return f
        return None


def body_addresses(f):
    for lo, hi in f.ranges:
        yield from range(lo, hi + 1, 4)


def decode_function(f):
    if f.ins is None:
        f.ins = {}
        for pc in body_addresses(f):
            w = f.program.word(pc)
            if w is not None:
                f.ins[pc] = decode(w, pc)
    return f.ins


class World:
    """All programs, with cross-module resolution of import stubs by name."""

    def __init__(self, db):
        self.programs = {}
        for path in sorted(glob.glob(os.path.join(db, "*.fn.tsv"))):
            stem = path[:-len(".fn.tsv")]
            self.programs[os.path.basename(stem)] = Program(stem)
        self.by_name = defaultdict(list)
        for p in self.programs.values():
            for f in p.funcs.values():
                if not f.name.startswith("thunk_"):
                    self.by_name[f.name].append(f)

    def resolve(self, f):
        """Follow local thunks and import stubs to the real function (or the stub if the target is outside)."""
        seen = set()
        while f is not None and id(f) not in seen:
            seen.add(id(f))
            if f.thunk is not None and f.thunk in f.program.funcs and f.thunk != f.entry:
                f = f.program.funcs[f.thunk]
                continue
            if f.name.startswith("thunk_") or f.size <= 8:
                name = f.name
                while name.startswith("thunk_"):
                    name = name[6:]
                others = [g for g in self.by_name.get(name, ()) if g is not f]
                if others and f.name.startswith("thunk_"):
                    f = next((g for g in others if g.program.name == "BOOT.BIN"), others[0])
                    continue
            break
        return f

    def callee(self, f, target):
        g = f.program.funcs.get(target)
        return self.resolve(g) if g else None


def proto_args(proto):
    """Prototype text -> (return text, [parameter texts], variadic)."""
    head, _, rest = proto.partition("(")
    inside = rest.rsplit(")", 1)[0].strip()
    params, depth, cur = [], 0, ""
    for ch in inside:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            params.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        params.append(cur.strip())
    variadic = "..." in params
    params = [p for p in params if p not in ("void", "...")]
    ret = head.rsplit(None, 1)[0].strip() if " " in head.strip() else ""
    if "*" in head.rsplit(None, 1)[-1]:
        ret += " " + "*" * head.rsplit(None, 1)[-1].count("*")
    return ret, params, variadic


def is_float(text):
    return bool(re.match(r"(const\s+)?(float|double)\b", text)) and "*" not in text


def is_wide(text):
    return bool(re.search(r"\b(long long|longlong|u?int64|s64|u64|undefined8)\b", text)) and "*" not in text


def proto_slots(params):
    """Integer register slots and float registers a parameter list occupies."""
    ints = floats = 0
    for p in params:
        if is_float(p):
            floats += 1
        else:
            ints += 2 if is_wide(p) else 1
    return ints, floats


def jump_table_targets(f, pc):
    """Targets of the `jr` at pc: the compiler's `lui r, hi; ...; lw r, lo(r); jr r` over a table of code
    addresses. No table found means no successors, which can only hide reads, never invent them."""
    ins = f.ins
    hi = lo = None
    for back in range(pc - 4, pc - 56, -4):
        i = ins.get(back)
        if i is None:
            break
        if lo is None and (i.load or i.word >> 26 == 9):
            lo = i.word & 0xFFFF
            lo = lo - 0x10000 if lo & 0x8000 else lo
        if i.word >> 26 == 15:
            hi = (i.word & 0xFFFF) << 16
            break
    if hi is None or lo is None:
        return []
    out, base = [], (hi + lo) & 0xFFFFFFFF
    for k in range(1024):
        w = f.program.word(base + 4 * k)
        if w is None or w not in ins:
            break
        out.append(w)
    return out


def walk_args(world, f):
    """Registers among the arguments that are read while still holding their entry value on every path to the
    read, including what direct callees and tail-called functions read. Must-analysis on purpose: a compiler can
    leave a variable unset on a path that never runs (a `switch` default, say), and that read says nothing about
    the prototype. A parameter that is only read after a conditional overwrite is missed, so this is a lower
    bound. Also returns the highest stack argument read."""
    ins = decode_function(f)
    if not ins:
        return 0, 0
    frame = 0
    for pc in sorted(ins)[:12]:
        w = ins[pc].word
        if w >> 16 == 0x27BD and w & 0x8000:  # addiu sp, sp, -N
            frame = 0x10000 - (w & 0xFFFF)
            break
    f.frame = frame
    state = {}
    work = [(f.entry, ARG_MASK)]
    while work:
        pc, undef = work.pop()
        while True:
            i = ins.get(pc)
            if i is None:
                break
            old = state.get(pc)
            if old is not None:
                if undef & old == old:
                    break
                undef &= old
            state[pc] = undef
            if i.kind == "op":
                undef &= ~i.writes
                pc += 4
                continue
            if i.kind == "trap":
                break
            d = ins.get(pc + 4)
            after = undef & ~d.writes if d is not None else undef
            if i.kind == "branch":
                if i.target in ins:
                    work.append((i.target, after))
                undef = undef if i.likely else after
                pc += 8
                continue
            if i.kind in ("call", "calli"):
                undef = after & ~CLOBBER
                pc += 8
                continue
            if i.kind == "jump" and i.target in ins:
                undef = after
                pc = i.target
                continue
            if i.kind == "ijump":
                work.extend((target, after) for target in jump_table_targets(f, pc))
            break
    used = stack = 0
    for pc, undef in state.items():
        i = ins[pc]
        used |= i.reads & undef
        if i.load and i.base == SP and frame and i.off >= frame:
            stack = max(stack, (i.off - frame) // 4 + 1)
        if i.kind in ("op", "trap"):
            continue
        d = ins.get(pc + 4)
        after = undef
        if d is not None:
            used |= d.reads & undef
            if d.load and d.base == SP and frame and d.off >= frame:
                stack = max(stack, (d.off - frame) // 4 + 1)
            after &= ~d.writes
        if i.kind == "call" or (i.kind == "jump" and i.target not in ins):
            g = world.callee(f, i.target)
            if g is not None:
                used |= g.args & after
    return used, stack


def walk_return(world, f):
    """(evidence, defined): evidence = some write of v0 by an instruction reaches `jr ra` unread, which a
    compiler only leaves for a return value, or a tail jump/last call hands on a returning function's value;
    defined = v0 written or received from any call on a path to a return."""
    ins = decode_function(f)
    if not ins:
        return False, False
    evidence = defined = False
    seen = {}
    work = [(f.entry, 0)]  # state: 0 nothing, 1 v0 written by a call, 2 v0 written by an instruction, unread
    while work:
        pc, st = work.pop()
        while True:
            i = ins.get(pc)
            if i is None or seen.get(pc, -1) & (1 << st) if pc in seen else False:
                break
            if i is None:
                break
            seen[pc] = seen.get(pc, 0) | 1 << st
            if i.kind == "op":
                st = step_v0(i, st)
                pc += 4
                continue
            if i.kind == "trap":
                break
            st = 0 if (i.reads >> V0 & 1 and st == 2) else st
            d = ins.get(pc + 4)
            after = step_v0(d, st) if d is not None else st
            if i.kind == "branch":
                if i.target in ins:
                    work.append((i.target, after))
                st = st if i.likely else after
                pc += 8
                continue
            if i.kind in ("call", "calli"):
                st = 1
                pc += 8
                continue
            if i.kind == "ret":
                defined = defined or after != 0
                evidence = evidence or after == 2
                break
            if i.kind == "jump":
                if i.target in ins:
                    st = after
                    pc = i.target
                    continue
                g = world.callee(f, i.target)
                if g is not None:
                    returns = g.ret_evidence or (g.row is not None and not proto_args(g.row["proto"])[0].startswith("void")
                                                 or (g.row is not None and "*" in proto_args(g.row["proto"])[0]))
                    defined = defined or returns
                    evidence = evidence or g.ret_evidence
                break
            break  # ijump: not followed
    return evidence, defined


def step_v0(i, st):
    if i.reads >> V0 & 1:
        st = 1 if st == 2 else st
    if i.writes >> V0 & 1:
        st = 2
    return st


def result_reads(world, f, site):
    """Registers among v0, v1, f0 that the code after the call at `site` reads before any write. Returns
    (read mask, reaches return with v0 unset)."""
    ins = f.ins
    read = 0
    through = False
    work = [(site + 8, RESULT_MASK)]
    seen = {}
    steps = 0
    while work and steps < 600:
        pc, live = work.pop()
        while steps < 600 and live:
            steps += 1
            i = ins.get(pc)
            if i is None or seen.get(pc, 0) & live == live:
                break
            seen[pc] = seen.get(pc, 0) | live
            read |= i.reads & live
            if i.kind == "op":
                live &= ~i.writes
                pc += 4
                continue
            if i.kind == "trap":
                break
            d = ins.get(pc + 4)
            after = live
            if d is not None:
                read |= d.reads & live
                after &= ~d.writes
            if i.kind == "branch":
                if i.target in ins:
                    work.append((i.target, after))
                live = live if i.likely else after
                pc += 8
                continue
            if i.kind in ("call", "calli"):
                break
            if i.kind == "jump" and i.target in ins:
                live = after
                pc = i.target
                continue
            if i.kind == "ret" and after >> V0 & 1:
                through = True
            break
    return read, through


def analyse(world, documented):
    """Attach documented rows, then run the fixpoint of argument use and collect call sites."""
    by_prog_addr = {(r["program"], int(r["addr"], 16)): r for r in documented.values()}
    funcs = []
    for p in world.programs.values():
        for f in p.funcs.values():
            f.row = by_prog_addr.get((p.name, f.entry))
            decode_function(f)
            funcs.append(f)
    # Stubs and functions outside the image take their argument set from the prototype.
    stubs = [f for f in funcs if f.name.startswith("thunk_") or f.size <= 8 or not f.ins]
    for f in stubs:
        if f.row:
            _, params, _ = proto_args(f.row["proto"])
            ints, floats = proto_slots(params)
            f.args = sum(1 << r for r in INT_ARGS[:ints]) | sum(1 << r for r in FLOAT_ARGS[:floats])
    code = [f for f in funcs if f not in set(stubs)] if False else [f for f in funcs if f.ins and f.size > 8 and not f.name.startswith("thunk_")]
    for _ in range(6):
        changed = 0
        for f in code:
            used, stack = walk_args(world, f)
            if used != f.args or stack != f.stack_args:
                f.args, f.stack_args = used, stack
                changed += 1
        if not changed:
            break
    for _ in range(4):
        changed = 0
        for f in code:
            ev, de = walk_return(world, f)
            if (ev, de) != (f.ret_evidence, f.ret_defined):
                f.ret_evidence, f.ret_defined = ev, de
                changed += 1
        if not changed:
            break
    # Call sites, attributed to the resolved target so that import stubs count for the real function.
    for f in code:
        for pc, i in f.ins.items():
            if i.kind == "call" and i.target is not None and i.target != pc + 8:
                g = world.callee(f, i.target)
                if g is None:
                    continue
                read, through = result_reads(world, f, pc)
                g.sites.append((f, pc, read, through))
    return code


def describe_args(mask):
    names = [REG[r] for r in INT_ARGS if mask >> r & 1] + [f"f{r - 32}" for r in FLOAT_ARGS if mask >> r & 1]
    return ",".join(names)


def scan_prototypes(world, code):
    """void-return, return-phantom, argument-count hits."""
    for f in code:
        if f.row is None:
            continue
        ret, params, variadic = proto_args(f.row["proto"])
        ints, floats = proto_slots(params)
        void = ret == "void"
        readers = [(c, pc) for c, pc, read, _ in f.sites if read >> V0 & 1]
        wide = [(c, pc) for c, pc, read, _ in f.sites if read >> V1 & 1]
        freaders = [(c, pc) for c, pc, read, _ in f.sites if read >> F0 & 1]
        base = dict(id=f.row["id"], name=f.name, group=f.group, size=f.size, proto=f.row["proto"],
                    sites=len(f.sites), indirect_or_data_refs=len(f.program.xrefs.get(f.entry, [])) - len(f.sites))
        if void and readers:
            yield dict(base, scan="void_read_by_callers", readers=len(readers), evidence=f.ret_evidence,
                       example=f"{readers[0][0].program.name}:{readers[0][1]:#x}")
        elif void and freaders:
            yield dict(base, scan="void_read_by_callers_f0", readers=len(freaders),
                       example=f"{freaders[0][0].program.name}:{freaders[0][1]:#x}")
        elif void and f.ret_evidence:
            yield dict(base, scan="void_with_return_write")
        if wide and not is_wide(ret):
            yield dict(base, scan="v1_read_by_callers", readers=len(wide),
                       example=f"{wide[0][0].program.name}:{wide[0][1]:#x}")
        if not void and not is_float(ret) and not f.ret_defined and not readers:
            yield dict(base, scan="return_never_set")
        if is_float(ret) and readers and not freaders:
            yield dict(base, scan="float_return_read_as_v0", readers=len(readers))
        if not void and not is_float(ret) and freaders and not readers:
            yield dict(base, scan="int_return_read_as_f0", readers=len(freaders))
        if variadic:
            continue
        need_int = max([k + 1 for k, r in enumerate(INT_ARGS) if f.args >> r & 1], default=0)
        need_float = max([k + 1 for k, r in enumerate(FLOAT_ARGS) if f.args >> r & 1], default=0)
        if f.stack_args:
            need_int = max(need_int, 8 + f.stack_args)
        if need_int > ints:
            yield dict(base, scan="args_omitted", declared=ints, used=need_int, regs=describe_args(f.args),
                       stack=f.stack_args)
        if need_float > floats:
            yield dict(base, scan="float_args_omitted", declared=floats, used=need_float, regs=describe_args(f.args))
        if ints > need_int and f.sites:
            # Declared but unread: a phantom only if no direct caller loads the register either.
            k = need_int
            set_by = 0
            for c, pc, _, _ in f.sites:
                mask = 0
                for back in range(pc + 4, pc - 48, -4):
                    i = c.ins.get(back)
                    if i is None or (i.kind != "op" and back != pc):
                        break
                    mask |= i.writes
                if k < 8 and mask >> INT_ARGS[k] & 1:
                    set_by += 1
            if k < 8 and set_by == 0:
                yield dict(base, scan="args_phantom", declared=ints, used=need_int, regs=describe_args(f.args))
        if floats > need_float and f.sites:
            yield dict(base, scan="float_args_unread", declared=floats, used=need_float, regs=describe_args(f.args))


NOOP = re.compile(r"\b(no-?op|does nothing|empty (function|body|stub)|returns immediately|empty\.)", re.I)
PURE = re.compile(r"\bno side effects?\b|\bpure\b|\bread-only\b", re.I)
CALLERS = re.compile(r"Callers?: (\d+)\b(?: \(([^)]*)\))?")
NO_CALLER = re.compile(r"No (direct )?callers?\b")
IDENT = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+){2,}\b")
COLOUR_WORDS = {"red": (1, 0, 0), "green": (0, 1, 0), "blue": (0, 0, 1), "yellow": (1, 1, 0), "cyan": (0, 1, 1),
                "magenta": (1, 0, 1)}
GROUPS = ("container", "card_db", "deck", "duel_core", "duel_effects", "tag_duel", "ai", "ui", "field_3d", "dialogue",
          "world", "shop", "save", "audio", "sdk", "system", "thunk")


def stores_outside_stack(f):
    """Instructions that write memory through a register other than sp/fp, or any call (first 3 of each)."""
    hits = []
    for pc, i in sorted(f.ins.items()):
        if i.store and i.base not in (SP, 30):
            hits.append(pc)
    return hits


def scan_summaries(world, code, all_names):
    """Claims of the summary that can be compared with the code."""
    for f in code:
        if f.row is None:
            continue
        summary = f.row["summary"]
        base = dict(id=f.row["id"], name=f.name, group=f.group, size=f.size)
        real = [p for p in f.ins.values() if p.kind in ("call", "calli", "jump", "ijump") or p.store]
        count = sum(1 for i in f.ins.values())
        if NOOP.search(summary) and not re.search(r"no-?op (callback|handler|function|stub|variant)s?\b.*(set|pass|regist|install)", summary, re.I):
            if count > 2 and real:
                yield dict(base, scan="noop_claim_with_code", text=NOOP.search(summary).group(0), ins=count)
        if PURE.search(summary):
            stores = stores_outside_stack(f)
            calls = [i for i in f.ins.values() if i.kind in ("calli",)]
            if stores:
                yield dict(base, scan="no_side_effects_but_stores", stores=len(stores), first=f"{stores[0]:#x}")
            elif calls:
                yield dict(base, scan="no_side_effects_but_indirect_call", calls=len(calls))
        # Real callers from Ghidra's references, across modules through the stubs.
        direct = {(c.program.name, c.entry) for c, _, _, _ in f.sites}
        m = CALLERS.search(summary)
        if m:
            said = int(m.group(1))
            if said != len(direct) and (said < 6 or len(direct) < 6 or abs(said - len(direct)) > 1):
                yield dict(base, scan="caller_count", said=said, found=len(direct))
        elif NO_CALLER.search(summary) and direct:
            yield dict(base, scan="no_caller_claim", found=len(direct),
                       example=sorted(n for _, n in direct)[0] if False else None)
        for token in set(IDENT.findall(summary)):
            if token.split("_")[0] in GROUPS and token not in all_names and token != f.name:
                yield dict(base, scan="stale_name", token=token)
        ret, _, _ = proto_args(f.row["proto"])
        if ret == "void" and re.search(r"\bReturns (the|a|an|true|false|non-?zero|zero|0|1|-1|its)\b", summary):
            yield dict(base, scan="void_summary_says_returns")
        if ret != "void" and re.search(r"\bNo return value\b|\bReturns nothing\b", summary):
            yield dict(base, scan="value_summary_says_nothing")
        for m in re.finditer(r"(\b(?:red|green|blue|yellow|cyan|magenta)\b)[^.;]{0,24}?(0x[0-9a-fA-F]{8})|(0x[0-9a-fA-F]{8})[^.;]{0,24}?\b(red|green|blue|yellow|cyan|magenta)\b", summary, re.I):
            word = (m.group(1) or m.group(4)).lower()
            value = int(m.group(2) or m.group(3), 16)
            r, g, b = value & 255, value >> 8 & 255, value >> 16 & 255
            hi = max(r, g, b)
            seen = tuple(1 if c * 2 > hi and hi else 0 for c in (r, g, b))
            if seen != COLOUR_WORDS[word] and value >> 24 in (0, 0x80, 0xff, 0x40, 0xc0):
                yield dict(base, scan="colour_word_mismatch", text=m.group(0), abgr_rgb=[r, g, b])
        if re.search(r"\bRGB\b|\bRRGGBB\b", summary) and not re.search(r"ABGR|AABBGGRR|BGR", summary):
            yield dict(base, scan="colour_rgb_mention", text=re.search(r".{0,40}\b(RGB|RRGGBB)\b.{0,40}", summary).group(0))


def scan_parity(world, documented, registry):
    """Rows whose prototype, registry and Ghidra disagree."""
    for rid, row in documented.items():
        head = row["proto"].split("(")[0].split()[-1].lstrip("*")
        reg = registry.get(rid)
        if reg is None:
            yield dict(id=rid, scan="row_not_in_registry", name=head)
            continue
        if head != reg["name"]:
            yield dict(id=rid, scan="prototype_name_differs", name=head, registry=reg["name"])
        if reg["status"] not in ("documented", "verified"):
            yield dict(id=rid, scan="row_not_documented_in_registry", name=head, status=reg["status"])


def run_scan(db, out, root=None):
    documented = load_documented() if root is None else load_documented(root)
    registry = load_registry() if root is None else load_registry(root)
    world = World(db)
    code = analyse(world, documented)
    names = {f.name for p in world.programs.values() for f in p.funcs.values()}
    names |= {n[6:] for n in names if n.startswith("thunk_")}
    counts = Counter()
    with open(out, "w", encoding="utf-8") as handle:
        for gen in (scan_prototypes(world, code), scan_summaries(world, code, names),
                    scan_parity(world, documented, registry)):
            for hit in gen:
                counts[hit["scan"]] += 1
                handle.write(json.dumps(hit, ensure_ascii=False) + "\n")
    for name, n in counts.most_common():
        print(f"{n:6d}  {name}")
    print(f"functions with code: {len(code)}, documented among them: {sum(1 for f in code if f.row)}")


# ---------------------------------------------------------------------------------------------------------
# Reading aid
# ---------------------------------------------------------------------------------------------------------

def capstone_engine():
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_MIPS, capstone.CS_MODE_MIPS32 | capstone.CS_MODE_LITTLE_ENDIAN)
    return md


ALLEGREX = {(0, 0x2C): "max", (0, 0x2D): "min", (0, 0x2E): "msub", (0, 0x2F): "msubu", (0, 0x16): "clz", (0, 0x17): "clo"}


def text_of(md, word, pc):
    """Capstone's text; Allegrex-only words (which capstone rejects or misreads) get their own rendering."""
    op, fn = word >> 26, word & 63
    rs, rt, rd = REG[word >> 21 & 31], REG[word >> 16 & 31], REG[word >> 11 & 31]
    if (op, fn) in ALLEGREX:
        return f"{ALLEGREX[(op, fn)]} {rd}, {rs}, {rt}"
    if op == 0 and fn == 2 and word >> 21 & 31 == 1:
        return f"rotr {rd}, {rt}, {word >> 6 & 31}"
    if op == 31:
        if fn == 0:
            return f"ext {rt}, {rs}, pos={word >> 6 & 31}, size={(word >> 11 & 31) + 1}"
        if fn == 4:
            return f"ins {rt}, {rs}, pos={word >> 6 & 31}, size={(word >> 11 & 31) - (word >> 6 & 31) + 1}"
        if fn == 32:
            sub = {16: "seb", 24: "seh", 2: "wsbh", 3: "wsbw", 20: "bitrev"}.get(word >> 6 & 31, "bshfl?")
            return f"{sub} {rd}, {rt}"
    if op in (18, 24, 25, 27, 52, 55, 60, 63):
        if op == 18 and word >> 21 & 31 in (3, 7):
            return f"{'mfv' if word >> 21 & 31 == 3 else 'mtv'} {rt}, vfpu_s{word & 127:#x}"
        if op == 18 and word >> 21 & 31 == 8:
            return f"bv{'tf'[not word >> 16 & 1]} cc{word >> 18 & 7}, {word & 0xffff:#x}"
        return f"vfpu.{op:#x} .word {word:#010x}"
    if op in (50, 54, 58, 62, 53, 61):
        simm = word & 0xFFFC
        simm = simm - 0x10000 if simm & 0x8000 else simm
        name = {50: "lv.s", 54: "lv.q", 58: "sv.s", 62: "sv.q", 53: "lvlr.q", 61: "svlr.q"}[op]
        return f"{name} vfpu{word >> 16 & 31:#x}, {simm}({rs})"
    for ins in md.disasm(struct.pack("<I", word), pc, 1):
        return f"{ins.mnemonic} {ins.op_str}"
    return f".word {word:#010x}"


def fmt_string(p, addr):
    data = p.data(addr, 48)
    end = data.find(b"\0")
    if end >= 4 and all(32 <= c < 127 for c in data[:end]):
        return f' "{data[:end].decode()}"'
    return ""


def disassemble(world, p, start, end, md=None):
    """Annotated listing: call and branch targets with names, lui pairs as absolute addresses, float constants."""
    md = md or capstone_engine()
    lines = []
    his = {}
    pc = start
    while pc < end:
        w = p.word(pc)
        if w is None:
            break
        text = text_of(md, w, pc)
        note = ""
        i = decode(w, pc)
        op, rs, rt = w >> 26, w >> 21 & 31, w >> 16 & 31
        if i.kind in ("call", "jump") and i.target is not None:
            g = p.funcs.get(i.target)
            if g:
                note = f" -> {g.name}"
                r = world.resolve(g)
                if r is not g and r is not None and r.row:
                    note += f" [{r.row['proto']}]"
                elif g.row:
                    note += f" [{g.row['proto']}]"
            else:
                h = p.containing(i.target)
                note = f" -> {h.name}+{i.target - h.entry:#x}" if h else ""
        if op == 15:
            his[rt] = (w & 0xFFFF) << 16
            value = struct.unpack("<f", struct.pack("<I", (w & 0xFFFF) << 16))[0]
            if 0.0001 < abs(value) < 1e7:
                note = f"  ; as float {value:g}"
        elif op in (8, 9, 13) or i.load or i.store or op == 49 or op == 57:
            if rs in his:
                imm = w & 0xFFFF
                addr = (his[rs] | imm) if op == 13 else (his[rs] + (imm - 0x10000 if imm & 0x8000 else imm)) & 0xFFFFFFFF
                note = f"  ; = {addr:#010x}"
                f = p.funcs.get(addr)
                if f:
                    note += f" {f.name}"
                note += fmt_string(p, addr)
                if op not in (8, 9, 13):
                    his.pop(rs, None) if rs == rt else None
        if i.writes and op not in (15,):
            for r in range(1, 32):
                if i.writes >> r & 1 and r in his and not (op in (8, 9, 13) and r == rt and False):
                    his.pop(r)
        lines.append(f"{pc:08x}  {w:08x}  {text}{note}")
        pc += 4
    return lines


def dossier(world, documented, rid, decompiled, context=14):
    """Everything a reader needs for one row, in one text."""
    row = documented[rid]
    p = world.programs[row["program"]]
    addr = int(row["addr"], 16)
    f = p.funcs.get(addr)
    out = [f"=== {rid}", f"prototype: {row['proto']}", f"summary: {row['summary']}", f"document: {row['doc']}"]
    if f is None:
        return "\n".join(out + ["NO FUNCTION IN GHIDRA"])
    out.append(f"ghidra: name={f.name} group={f.group} size={f.size} ghidra_proto={f.proto}")
    out.append(f"scanner: args_read_before_write=[{describe_args(f.args)}] stack_args={f.stack_args} "
               f"frame={f.frame} return_write_evidence={f.ret_evidence} v0_defined_at_return={f.ret_defined}")
    md = capstone_engine()
    out.append("--- disassembly (instructions are the evidence)")
    for lo, hi in f.ranges:
        out += disassemble(world, p, lo, hi + 1, md)
    out.append(f"--- direct call sites: {len(f.sites)} (v0/v1/f0 reads after the call in brackets)")
    for c, pc, read, through in sorted(f.sites, key=lambda s: (s[0].program.name, s[1]))[:12]:
        flags = "".join(n for n, r in (("v0 ", V0), ("v1 ", V1), ("f0 ", F0)) if read >> r & 1) or "-"
        out.append(f"  {c.program.name} {c.name} at {pc:#010x} [{flags.strip()}]{' passes v0 to its own caller' if through else ''}")
        for line in disassemble(world, c.program, pc - 4 * context // 2, pc + 4 * context // 2, md):
            out.append("    " + line)
    if len(f.sites) > 12:
        out.append(f"  ... {len(f.sites) - 12} more sites")
    other = [x for x in p.xrefs.get(f.entry, []) if "CALL" not in x[2]]
    out.append(f"--- other references (pointers, tables): {len(other)}")
    for frm, fn, kind in other[:10]:
        owner = p.funcs.get(fn).name if fn in p.funcs else "data"
        out.append(f"  {frm:#010x} {kind} in {owner}")
    if decompiled is not None:
        out.append("--- decompilation (secondary, can hide things)")
        out.append(decompiled.get((row["program"], addr), "(not exported)"))
    return "\n".join(out)


def load_decompiled(db, program):
    path = os.path.join(db, program + ".c")
    table = {}
    if not os.path.exists(path):
        return table
    key, cur = None, []
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith("//==== "):
                if key is not None:
                    table[(program, key)] = "".join(cur)
                key, cur = int(line.split()[1], 16), []
            else:
                cur.append(line)
    if key is not None:
        table[(program, key)] = "".join(cur)
    return table


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("db")
    parser.add_argument("command", choices=["scan", "dossier", "dis"])
    parser.add_argument("rest", nargs="*")
    parser.add_argument("-o", "--output")
    parser.add_argument("--list", help="dossier: file with one registry id per line; -o is then a directory")
    args = parser.parse_args(argv)
    if args.command == "scan":
        run_scan(args.db, args.output)
        return 0
    world = World(args.db)
    if args.command == "dis":
        p = world.programs[args.rest[0]]
        start = int(args.rest[1], 16)
        print("\n".join(disassemble(world, p, start, start + int(args.rest[2], 0))))
        return 0
    documented = load_documented()
    analyse(world, documented)
    ids = list(args.rest)
    if args.list:
        with open(args.list, encoding="utf-8") as handle:
            ids += [x.strip() for x in handle if x.strip()]
    tables = {}
    for rid in ids:
        program = documented[rid]["program"]
        if program not in tables:
            tables[program] = load_decompiled(args.db, program)
        text = dossier(world, documented, rid, tables[program])
        if args.output:
            with open(os.path.join(args.output, rid.replace(":", "_") + ".txt"), "w", encoding="utf-8") as handle:
                handle.write(text)
        else:
            print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
