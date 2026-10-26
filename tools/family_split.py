#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Split the categories of family-shared effect handlers of gmodule/rel_duel_eng.prx per card.

See docs/subsystems/effect-classification.md ("Per-card split of family handlers"). tools/effect_classify.py gives
a handler the union of the categories reachable from it, so a handler shared by a card family (the LP handler of
217 records, the equip, union and fusion handlers, ...) gives every card of the family the categories of all of
them. Inside such a handler the per-card behaviour is chosen by tests of the card id, the u16 at +0 of the chain
link the handler receives in a0. This tool re-runs the closure of effect_classify once per card with that card
id known:

  * a path-sensitive known-bits scan (the transfer functions of effect_classify) that tracks the registers and
    stack slots holding the link pointer, makes `lhu/lh r, 0(link)` the constant card id, and drops the branch
    side a known value rules out; up to MAX_STATES distinct states are kept per address before merging;
  * `duel_core_get_effective_card_id(link)` returns 0 (the effect is not a copied one, the normal case);
  * jump tables (`sltiu; lui; addu; lw; jr`) are followed to the case of a known index, else to all cases;
  * callees are scanned with the known bits of their arguments and with the link registers passed on, so a
    card-id test inside a callee also selects;
  * duel_effects_resolve_lp_change is replaced by a decode of duel_effects_get_lp_change_amounts for the card:
    a small interval/controller-relative evaluator gives the sign and the side (self/opponent) of every amount
    the case stores, hence damage versus gain_lp.

Everything else (mapping rows, depth, thunks, callbacks, dispatch lists, root names) is effect_classify's,
imported with importlib and unchanged. The refined categories are a subset of the original ones, except that the
LP decode may add the LP category that the depth limit hid.

  family_split.py <USRDIR>/gmodule/rel_duel_eng.prx --check [--cardinfo <cardinfo_eng.ehp>]
  family_split.py <USRDIR>/gmodule/rel_duel_eng.prx -o extracted/family_split [--cardinfo ...]

Outputs (game data: keep them under extracted/, never in git): family_split.csv (one row per examined record:
card, table, index, handler, categories before and after, removed, added, method, confidence, LP amounts),
families.csv (the examined resolve handlers ranked by records x categories, with the split result).
--check prints the summary and the precision on the built-in judged sample (SAMPLE).
"""

import argparse
import collections
import csv
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ec = _load("re_effect_classify", "effect_classify.py")
ep = ec.ep

BASE, TEXT_END, FULL = ec.BASE, ec.TEXT_END, ec.FULL
V0, A0, A1, SP, RA = 2, 4, 5, 29, 31
MAX_STATES = 8  # distinct register states kept per address before they are merged
MAX_STEPS = 60000  # instructions interpreted per specialised scan
LP_RESOLVE_NAME = "duel_effects_resolve_lp_change"
LP_CHAIN_NAME = "duel_effects_get_lp_change_amounts"
EFFECTIVE_ID_NAME = "duel_core_get_effective_card_id"
SET_FACE_NAME = "duel_core_post_set_face"  # (side, slot, face_up): command 0x34
LP_CATEGORIES = ("damage", "gain_lp")
CTX = "ctx"  # state key: frozenset of registers and ('sp', offset) slots that hold the link pointer


def _branch_kind(w):
    op, rt = w >> 26, w >> 16 & 31
    return ec._is_branch(op, rt)


def _target(pc, w):
    imm = w & 0xFFFF
    return pc + 4 + 4 * (imm - 0x10000 if imm & 0x8000 else imm)


# ---------------------------------------------------------------------------------------------- known-bit decisions


def _sign(v):
    """(negative, nonneg, zero, nonzero) as True/False/None from known bits."""
    mask, value = v
    neg = None if not mask >> 31 & 1 else bool(value >> 31 & 1)
    zero = True if mask == FULL and value == 0 else (False if value & mask else None)
    return neg, zero


def decide(w, regs):
    """True (taken) / False (not taken) / None (unknown) for the branch word `w` under the known bits `regs`."""
    op, rs, rt = w >> 26, w >> 21 & 31, w >> 16 & 31
    a, b = ec._get(regs, rs), ec._get(regs, rt)
    if op in (4, 5, 0x14, 0x15):
        eq = op in (4, 0x14)
        if rs == rt:
            return eq
        if (a[0] & b[0]) & (a[1] ^ b[1]):
            return not eq
        if a[0] == FULL and b[0] == FULL:
            return (a[1] == b[1]) == eq
        return None
    neg, zero = _sign(a)
    if op == 1:
        kind = rt & 3  # 0 bltz, 1 bgez (and the likely / linking forms)
        if neg is None:
            return None
        return neg if kind in (0, 2) else not neg
    if op in (6, 0x16, 7, 0x17):  # blez / bgtz
        le = True if neg or zero else (False if neg is False and zero is False else None)
        if le is None:
            return None
        return le if op in (6, 0x16) else not le
    return None


# ---------------------------------------------------------------------------------------------- states



def _covers(a, b):
    """State a is at most as precise as b (every fact of a also holds in b)."""
    if not a.get(CTX, frozenset()) <= b.get(CTX, frozenset()):
        return False
    for r, mv in a.items():
        if r == CTX:
            continue
        m, v = mv
        if r not in b:
            return False
        bm, bv = b[r]
        if bm & m != m or (bv ^ v) & m:
            return False
    return True


def _meet(a, b):
    out = {}
    for r in a.keys() & b.keys():
        if r == CTX:
            continue
        m = ec.kb_meet(a[r], b[r])
        if m[0]:
            out[r] = m
    out[CTX] = a.get(CTX, frozenset()) & b.get(CTX, frozenset())
    return out


SCall = collections.namedtuple("SCall", "site kind target args ctx_args")
Scan = collections.namedtuple("Scan", "calls stores decided id_reads fallback")


class SpecialisedScanner:
    """Path-sensitive scan of one function for one card id (see the module docstring)."""

    def __init__(self, module, registry, effective_id=None):
        self.module, self.registry = module, registry
        self.effective_id = effective_id  # address of duel_core_get_effective_card_id (returns 0), or None

    def scan(self, start, end, card_id, args=None, ctx=frozenset({A0})):
        end = min(end, TEXT_END)
        if not start < end:
            return Scan([], [], 0, 0, False)
        words = self.module.words(start, (end - start) // 4)
        word = lambda pc: words[(pc - start) >> 2] if start <= pc < end else 0
        entry = dict(args or {})
        entry[CTX] = frozenset(ctx)
        states = collections.defaultdict(list)  # pc -> list of states already processed at pc
        work = [(start, entry)]
        calls, stores = {}, {}
        decided = id_reads = steps = 0
        fallback = False
        visited = set()

        def arrive(pc, st):
            if not start <= pc < end:
                return
            known = states[pc]
            for old in known:
                if _covers(old, st):
                    return
            if len(known) >= MAX_STATES:
                merged = _meet(known[-1], st)
                if _covers(known[-1], merged) and _covers(merged, known[-1]):
                    return
                known[-1] = merged
                st = merged
            else:
                known.append(st)
            work.append((pc, dict(st)))

        def record(site, kind, target, st):
            a = {r: st[r] for r in ec.ARG_REGS if r in st}
            c = tuple(r for r in ec.ARG_REGS if r in st.get(CTX, ()))
            old = calls.get(site)
            if old is None:
                calls[site] = SCall(site, kind, target, a, c)
            else:  # the same site reached in several states: keep the facts common to all
                merged = {r: ec.kb_meet(old.args[r], a[r]) for r in old.args.keys() & a.keys()}
                calls[site] = SCall(site, kind, target, {r: v for r, v in merged.items() if v[0]},
                                    tuple(r for r in old.ctx_args if r in c))

        def clobber(st):
            for r in ec.CLOBBERED:
                st.pop(r, None)
            st[CTX] = frozenset(x for x in st[CTX] if not (isinstance(x, int) and x in ec.CLOBBERED))

        def step(st, w, pc):
            """Apply one non-transfer instruction, with the link-pointer rules."""
            nonlocal id_reads
            op, rs, rt, rd, fn = w >> 26, w >> 21 & 31, w >> 16 & 31, w >> 11 & 31, w & 63
            imm = w & 0xFFFF
            simm = imm - 0x10000 if imm & 0x8000 else imm
            ctxs = st[CTX]
            if op == 0x2B and rs == SP:  # sw to a stack slot: the link pointer may be spilled
                slot = ("sp", simm)
                st[CTX] = (ctxs | {slot}) if rt in ctxs else (ctxs - {slot})
                return
            if op == 0 and fn in (0x21, 0x25) and (rs == 0 or rt == 0) and (rs in ctxs or rt in ctxs) and rd:
                ec.apply(st, w)
                st[CTX] = ctxs | {rd}
                return
            dst = ec.written(w)
            if op == 0x23 and rs == SP and ("sp", simm) in ctxs:
                st.pop(rt, None)
                st[CTX] = ctxs | {rt}
                return
            if op in (0x21, 0x25) and rs in ctxs and simm == 0 and rt:  # lh/lhu r, 0(link): the card id
                st[rt] = ec.const(card_id)
                st[CTX] = ctxs - {rt}
                id_reads += 1
                return
            if op == 0x0B and rt:  # sltiu: remember the switch index and bound for a following jump table
                st[100] = ec._get(st, rs)
                st[101] = ec.const(simm & FULL)
            if op == 0 and fn == 0x2B and rd:  # sltu rd, rs, rt
                st[100] = ec._get(st, rs)
                b = ec._get(st, rt)
                if b[0] == FULL:
                    st[101] = b
                else:
                    st.pop(101, None)
            ec.apply(st, w)
            if dst and (op in (0x0A, 0x0B) or (op == 0 and fn in (0x2A, 0x2B))):  # set-less-than of constants
                a = ec._get(st, rs) if dst != rs else None
                b = ec.const(simm) if op in (0x0A, 0x0B) else (ec._get(st, rt) if dst != rt else None)
                if a is not None and b is not None and a[0] == FULL and b[0] == FULL:
                    x, y = a[1], b[1]
                    if op == 0x0A or (op == 0 and fn == 0x2A):
                        x, y = ep.signed(x), ep.signed(y)
                    st[dst] = ec.const(int(x < y))
                st[CTX] = ctxs - {dst}

        def jump_table(pc, reg, st):
            """Targets of a `jr reg` jump table, or None when the table is not recognised."""
            lo = hi = None
            for q in range(pc - 4, max(start, pc - 48) - 4, -4):
                w = word(q)
                op, rs, rt = w >> 26, w >> 21 & 31, w >> 16 & 31
                if lo is None and op == 0x23 and rt == reg:
                    lo = w & 0xFFFF
                    lo = lo - 0x10000 if lo & 0x8000 else lo
                elif lo is not None and op == 0x0F:
                    hi = (w & 0xFFFF) << 16
                    break
            if lo is None or hi is None or 101 not in st or st[101][0] != FULL:
                return None
            table, count = (hi + lo) & FULL, st[101][1]
            if not 0 < count <= 512:
                return None
            idx = st.get(100, (0, 0))
            indices = [idx[1]] if idx[0] == FULL and idx[1] < count else range(count)
            out = []
            for k in indices:
                try:
                    v = self.module.word(BASE + table + 4 * k)
                except ValueError:
                    return None
                out.append(BASE + v)
            return out

        while work:
            pc, st = work.pop()
            while start <= pc < end:
                steps += 1
                if steps > MAX_STEPS:
                    fallback = True
                    work.clear()
                    break
                visited.add(pc)
                w = word(pc)
                op, rs, rt, fn = w >> 26, w >> 21 & 31, w >> 16 & 31, w & 63
                if _branch_kind(w):
                    target = _target(pc, w)
                    likely = op in (0x14, 0x15, 0x16, 0x17) or (op == 1 and rt in (2, 3, 0x12, 0x13))
                    visited.add(pc + 4)
                    taken = decide(w, st)
                    after = dict(st)
                    step(after, word(pc + 4), pc + 4)
                    if op == 1 and rt >= 0x10:  # bltzal / bgezal: a call
                        record(pc, "call", target, after)
                        clobber(after)
                        arrive(pc + 8, after)
                        break
                    always = (op == 4 and rs == rt) or (op == 1 and rt in (1, 3) and rs == 0)
                    if always:
                        taken = True
                    elif taken is not None:
                        decided += 1
                    if taken is not False:
                        if start <= target < end:
                            arrive(target, after)
                        elif always:
                            record(pc, "tail", target, after)
                    if taken is not True:
                        arrive(pc + 8, st if likely else after)
                    break
                if op == 2:
                    visited.add(pc + 4)
                    after = dict(st)
                    step(after, word(pc + 4), pc + 4)
                    target = BASE + ((w & 0x3FFFFFF) << 2)
                    if start <= target < end:
                        arrive(target, after)
                    else:
                        record(pc, "tail", target, after)
                    break
                if op == 3 or (op == 0 and fn == 9):
                    visited.add(pc + 4)
                    after = dict(st)
                    step(after, word(pc + 4), pc + 4)
                    target = BASE + ((w & 0x3FFFFFF) << 2) if op == 3 else None
                    record(pc, "call" if op == 3 else "indirect", target, after)
                    clobber(after)
                    if target is not None and self.effective_id is not None:
                        resolved = target
                        for _ in range(4):  # follow a thunk
                            if not BASE <= resolved < TEXT_END - 8:
                                break
                            t = self.module.word(resolved)
                            if t >> 26 != 2:
                                break
                            resolved = BASE + ((t & 0x3FFFFFF) << 2)
                        if resolved == self.effective_id:
                            after[V0] = ec.const(0)
                    arrive(pc + 8, after)
                    break
                if op == 0 and fn == 8:  # jr
                    visited.add(pc + 4)
                    if rs != RA:
                        after = dict(st)
                        step(after, word(pc + 4), pc + 4)
                        targets = jump_table(pc, rs, st)
                        if targets is None:
                            fallback = True
                        else:
                            for t in targets:
                                if start <= t < end:
                                    arrive(t, dict(after))
                                else:
                                    fallback = True
                    break
                if op in (0x28, 0x29, 0x2B):
                    b, v = ec._get(st, rs), ec._get(st, rt)
                    if b[0] == FULL and v[0] == FULL:
                        imm = w & 0xFFFF
                        addr = BASE + ((b[1] + (imm - 0x10000 if imm & 0x8000 else imm)) & FULL)
                        size = {0x28: 1, 0x29: 2, 0x2B: 4}[op]
                        stores[pc] = (addr & FULL, size, v[1] & ((1 << 8 * size) - 1))
                step(st, w, pc)
                pc += 4
        if fallback:  # an unresolved computed jump: also scan what was not reached, as effect_classify does
            for c in ec.scan_function(self.module, start, end, None):
                if c.site not in calls:
                    calls[c.site] = SCall(c.site, c.kind, c.target, c.args, ())
            extra = {}
            ec.scan_function(self.module, start, end, extra)
            for site, s in extra.items():
                stores.setdefault(site, s)
        return Scan([calls[k] for k in sorted(calls)], list(stores.values()), decided, id_reads, fallback)


# ---------------------------------------------------------------------------------------------- LP chain decode
# Abstract values: ("i", lo, hi) an integer interval; ("c", a, b) = a * C + b with C the controller (0 or 1);
# ("p", base, off) a pointer (base "ctx", "out" or "sp", off an abstract value); ("b2",) the byte at link +2;
# None = unknown.

LP_CALL_HI = 0xFFFF  # call results (counts, Levels, ATK/DEF, predicates) are taken as non-negative


def _iv(v):
    """Interval of an abstract value, or None."""
    if v is None:
        return None
    if v[0] == "i":
        return v[1], v[2]
    if v[0] == "c":
        xs = (v[2], v[1] + v[2])
        return min(xs), max(xs)
    if v[0] == "x":
        xs = (v[2] * v[4] + v[3], v[2] * v[5] + v[3])
        return min(xs), max(xs)
    return None


def _atom(pc, hi):
    """A fresh unknown X in [0, hi] (a call result or a loaded field), as the linear form 1 * X + 0."""
    return ("x", pc, 1, 0, 0, hi)


def _const(x):
    x &= FULL
    x = x - (1 << 32) if x & 0x80000000 else x
    return ("i", x, x)


def _is_const(v):
    return v is not None and v[0] == "i" and v[1] == v[2]


def _hull(a, b):
    if a == b:
        return a
    ia, ib = _iv(a), _iv(b)
    if ia is None or ib is None:
        return None
    return ("i", min(ia[0], ib[0]), max(ia[1], ib[1]))


def _add(a, b, sub=False):
    if a is not None and a[0] == "p" and b is None:  # a pointer plus an unknown index stays a pointer
        return ("p", a[1], None)
    if b is not None and b[0] == "p" and a is None and not sub:
        return ("p", b[1], None)
    if a is None or b is None:
        return None
    s = -1 if sub else 1
    if a[0] == "p" and b[0] in ("i", "c", "x") and not sub:
        return ("p", a[1], _add(a[2], b))
    if b[0] == "p" and a[0] in ("i", "c", "x") and not sub:
        return ("p", b[1], _add(b[2], a))
    if a[0] == "p" and b[0] in ("i", "c", "x") and sub:
        return ("p", a[1], _add(a[2], b, True))
    if a[0] == "x" and b[0] == "x" and a[1] == b[1]:  # the same unknown: shift-and-add multiplications
        coef = a[2] + s * b[2]
        return _const(a[3] + s * b[3]) if coef == 0 else ("x", a[1], coef, a[3] + s * b[3], a[4], a[5])
    if a[0] == "x" and _is_const(b):
        return ("x", a[1], a[2], a[3] + s * b[1], a[4], a[5])
    if b[0] == "x" and _is_const(a):
        return ("x", b[1], s * b[2], a[1] + s * b[3], b[4], b[5])
    if a[0] == "c" and b[0] == "c":
        r = ("c", a[1] + s * b[1], a[2] + s * b[2])
        return _const(r[2]) if r[1] == 0 else r
    if a[0] == "c" and _is_const(b):
        return ("c", a[1], a[2] + s * b[1])
    if b[0] == "c" and _is_const(a):
        return ("c", s * b[1], a[1] + s * b[2])
    ia, ib = _iv(a), _iv(b)
    if ia is None or ib is None:
        return None
    lo, hi = (ia[0] - ib[1], ia[1] - ib[0]) if sub else (ia[0] + ib[0], ia[1] + ib[1])
    if lo == hi:
        return _const(lo)
    if a[0] == "i" and b[0] == "i":
        return ("i", lo, hi)
    # a new unknown named by how it was computed, so that later shift-and-add steps on it stay exact
    return ("x", ("-" if sub else "+", a, b), 1, 0, lo, hi)


def _mul(a, k):
    """a * constant k."""
    if a is None:
        return None
    if a[0] == "c":
        return ("c", a[1] * k, a[2] * k)
    if a[0] == "x":
        return ("x", a[1], a[2] * k, a[3] * k, a[4], a[5]) if k else _const(0)
    if a[0] == "i":
        xs = (a[1] * k, a[2] * k)
        return ("i", min(xs), max(xs))
    return None


def _mul2(a, b):
    if _is_const(b):
        return _mul(a, b[1])
    if _is_const(a):
        return _mul(b, a[1])
    ia, ib = _iv(a), _iv(b)
    if ia is None or ib is None:
        return None
    xs = [x * y for x in ia for y in ib]
    return ("i", min(xs), max(xs))


def _values(v):
    """The set of possible values when small (constants and controller-relative values), else None."""
    if _is_const(v):
        return {v[1]}
    if v is not None and v[0] == "c":
        return {v[2], v[1] + v[2]}
    return None


class LpDecoder:
    """Evaluates duel_effects_get_lp_change_amounts(link, out[2]) for one card id: the amounts stored to out[]."""

    def __init__(self, module, start, end, effective_id=None, max_steps=20000):
        self.module, self.start, self.end = module, start, end
        self.effective_id, self.max_steps = effective_id, max_steps

    def decode(self, card_id):
        """List of (side, value) for every non-zero store to out[]: side self/opponent/player0/player1/either,
        value an abstract value. Returns (stores, complete): complete is False when the walk hit its budget."""
        out = []
        regs = {A0: ("p", "ctx", _const(0)), A1: ("p", "out", _const(0)), SP: ("p", "sp", _const(0)), 0: _const(0)}
        work = [(self.start, regs, {}, None)]
        visits = collections.Counter()
        steps = 0
        complete = True
        while work:
            pc, regs, stack, lo = work.pop()
            while self.start <= pc < self.end:
                steps += 1
                visits[pc] += 1
                if steps > self.max_steps or visits[pc] > 64:
                    complete = False
                    work.clear()
                    break
                w = self.module.word(pc)
                op, rs, rt, fn = w >> 26, w >> 21 & 31, w >> 16 & 31, w & 63
                if _branch_kind(w) and not (op == 1 and rt >= 0x10):
                    target = _target(pc, w)
                    likely = op in (0x14, 0x15, 0x16, 0x17) or (op == 1 and rt in (2, 3))
                    taken = self._decide(w, regs)
                    a_regs, a_stack = dict(regs), dict(stack)
                    a_lo = self._step(a_regs, a_stack, self.module.word(pc + 4), card_id, out, lo, pc)
                    if taken is not False:
                        work.append((target, dict(a_regs), dict(a_stack), a_lo))
                    if taken is not True:
                        if likely:
                            work.append((pc + 8, regs, stack, lo))
                        else:
                            work.append((pc + 8, a_regs, a_stack, a_lo))
                    break
                if op == 2:
                    lo = self._step(regs, stack, self.module.word(pc + 4), card_id, out, lo, pc)
                    pc = BASE + ((w & 0x3FFFFFF) << 2)
                    continue
                if op == 3 or (op == 0 and fn == 9) or (op == 1 and rt >= 0x10):
                    lo = self._step(regs, stack, self.module.word(pc + 4), card_id, out, lo, pc)
                    target = BASE + ((w & 0x3FFFFFF) << 2) if op == 3 else None
                    for r in ec.CLOBBERED:
                        regs.pop(r, None)
                    effective = target is not None and target == self.effective_id
                    regs[V0] = _const(0) if effective else _atom(pc, LP_CALL_HI)
                    pc += 8
                    continue
                if op == 0 and fn == 8:  # jr ra (return) or an unresolved computed jump, after its delay slot
                    self._step(regs, stack, self.module.word(pc + 4), card_id, out, lo, pc)
                    break
                lo = self._step(regs, stack, w, card_id, out, lo, pc)
                pc += 4
        return out, complete

    @staticmethod
    def _decide(w, regs):
        op, rs, rt = w >> 26, w >> 21 & 31, w >> 16 & 31
        a, b = regs.get(rs) if rs else _const(0), regs.get(rt) if rt else _const(0)
        if op in (4, 5, 0x14, 0x15):
            eq = op in (4, 0x14)
            if rs == rt:
                return eq
            va, vb = _values(a), _values(b)
            if va is not None and vb is not None:
                if len(va) == 1 and va == vb:
                    return eq
                if not va & vb:
                    return not eq
                return None
            ia, ib = _iv(a), _iv(b)
            if ia is not None and ib is not None and (ia[1] < ib[0] or ib[1] < ia[0]):
                return not eq
            return None
        ia = _iv(a)
        if ia is None:
            return None
        if op == 1:
            lt = True if ia[1] < 0 else False if ia[0] >= 0 else None
            if lt is None:
                return None
            return lt if rt & 3 in (0, 2) else not lt
        if op in (6, 0x16, 7, 0x17):
            le = True if ia[1] <= 0 else False if ia[0] > 0 else None
            if le is None:
                return None
            return le if op in (6, 0x16) else not le
        return None

    def _step(self, regs, stack, w, card_id, out, lo, pc):
        """Apply one instruction to the abstract state; returns the new LO register value."""
        op, rs, rt, rd, sa, fn = w >> 26, w >> 21 & 31, w >> 16 & 31, w >> 11 & 31, w >> 6 & 31, w & 63
        imm = w & 0xFFFF
        simm = imm - 0x10000 if imm & 0x8000 else imm
        g = lambda r: _const(0) if r == 0 else regs.get(r)

        def put(r, v):
            if r:
                if v is None:
                    regs.pop(r, None)
                else:
                    regs[r] = v

        if w == 0:
            return lo
        if op in (0x28, 0x29, 0x2B):  # stores
            base, val = g(rs), g(rt)
            if base is not None and base[0] == "p":
                off = _add(base[2], _const(simm))
                if base[1] == "sp" and _is_const(off):
                    stack[off[1]] = val
                elif base[1] == "out" and op == 0x2B:
                    if not (_is_const(val) and val[1] == 0):
                        out.append((self._side(off), val))
            return lo
        if op in (0x20, 0x21, 0x23, 0x24, 0x25):  # loads
            base = g(rs)
            v = None
            if base is not None and base[0] == "p":
                off = _add(base[2], _const(simm))
                if base[1] == "ctx" and _is_const(off):
                    k = off[1]
                    if k == 0 and op in (0x21, 0x25):
                        v = _const(card_id)
                    elif k == 2 and op == 0x24:
                        v = ("b2",)
                    elif op == 0x23:
                        v = _atom(pc, 0x7FFFFFFF)  # an amount stored in the link: assumed non-negative
                elif base[1] == "sp" and _is_const(off) and op == 0x23:
                    v = stack.get(off[1])
            if v is None:
                # the words read by the chain are counts, stats and amounts: taken as non-negative
                v = {0x20: ("i", -128, 127), 0x24: _atom(pc, 255), 0x21: ("i", -32768, 32767),
                     0x25: _atom(pc, 0xFFFF), 0x23: _atom(pc, 0x7FFFFFFF)}.get(op)
            put(rt, v)
            return lo
        s, t = g(rs), g(rt)
        if op == 0x0F:
            put(rt, _const(imm << 16))
        elif op in (8, 9):
            put(rt, _add(s, _const(simm)))
        elif op == 0x0C:  # andi
            if s is not None and s[0] == "b2" and imm == 1:
                put(rt, ("c", 1, 0))
            elif s is not None and s[0] == "c" and imm == 1 and s[1] in (1, -1):
                put(rt, s)
            elif _is_const(s):
                put(rt, _const(s[1] & imm))
            else:
                put(rt, ("i", 0, imm))
        elif op == 0x0D:  # ori
            put(rt, _const(s[1] | imm) if _is_const(s) else (s if imm == 0 else None))
        elif op == 0x0E:  # xori
            if _is_const(s):
                put(rt, _const(s[1] ^ imm))
            elif s is not None and s[0] == "c" and imm == 1 and (s[1], s[2]) in ((1, 0), (-1, 1)):
                put(rt, ("c", -s[1], 1 - s[2]))
            else:
                put(rt, None)
        elif op in (0x0A, 0x0B):  # slti / sltiu
            iv = _iv(s)
            if iv is not None and (op == 0x0A or iv[0] >= 0) and simm >= 0:
                put(rt, _const(1) if iv[1] < simm else _const(0) if iv[0] >= simm else ("i", 0, 1))
            else:
                put(rt, ("i", 0, 1))
        elif op == 0:
            if fn == 0:  # sll (unknown when the result can leave the signed 32-bit range)
                v = _mul(t, 1 << sa) if t is not None and t[0] in ("i", "c", "x") else None
                iv = _iv(v)
                put(rd, v if iv is not None and -0x80000000 <= iv[0] and iv[1] <= 0x7FFFFFFF else None)
            elif fn in (2, 3):  # srl / sra
                iv = _iv(t)
                if iv is not None and (fn == 3 or iv[0] >= 0):
                    put(rd, ("i", iv[0] >> sa, iv[1] >> sa))
                elif fn == 2 and rs == 0:
                    put(rd, ("i", 0, FULL >> sa))
                else:
                    put(rd, None)
            elif fn in (0x20, 0x21):
                put(rd, _add(s, t))
            elif fn in (0x22, 0x23):
                put(rd, _add(s, t, True))
            elif fn == 0x24:  # and
                put(rd, _const(s[1] & t[1]) if _is_const(s) and _is_const(t) else None)
            elif fn == 0x25:  # or (move)
                if rt == 0:
                    put(rd, s)
                elif rs == 0:
                    put(rd, t)
                else:
                    put(rd, _const(s[1] | t[1]) if _is_const(s) and _is_const(t) else None)
            elif fn == 0x26:  # xor: owner ^ switched-control bit -> the controller
                if _is_const(s) and _is_const(t):
                    put(rd, _const(s[1] ^ t[1]))
                elif s is not None and s[0] == "c" and _iv(t) is not None and _iv(t)[0] >= 0 and _iv(t)[1] <= 1:
                    put(rd, s)
                elif t is not None and t[0] == "c" and _iv(s) is not None and _iv(s)[0] >= 0 and _iv(s)[1] <= 1:
                    put(rd, t)
                else:
                    put(rd, None)
            elif fn in (0x2A, 0x2B):  # slt / sltu
                ia, ib = _iv(s), _iv(t)
                if ia is not None and ib is not None:
                    put(rd, _const(1) if ia[1] < ib[0] else _const(0) if ia[0] >= ib[1] else ("i", 0, 1))
                else:
                    put(rd, ("i", 0, 1))
            elif fn in (0x0A, 0x0B):  # movz / movn
                put(rd, _hull(g(rd), s))
            elif fn in (0x18, 0x19):  # mult / multu
                return _mul2(s, t)
            elif fn == 0x12:  # mflo
                put(rd, lo)
            elif fn in (0x1A, 0x1B):  # div / divu: LO = quotient
                ia = _iv(s)
                if ia is not None and _is_const(t) and t[1] > 0:
                    return ("i", int(ia[0] / t[1]), int(ia[1] / t[1]))
                return None
            elif fn in (0x2C, 0x2D):  # Allegrex max / min
                put(rd, _hull(s, t))
            else:
                dst = ec.written(w)
                if dst is not None:
                    put(dst, None)
        else:
            dst = ec.written(w)
            if dst is not None:
                put(dst, None)
        return lo

    @staticmethod
    def _side(off):
        vals = _values(off)
        if off is not None and off[0] == "c":
            if (off[1], off[2]) == (4, 0):
                return "self"
            if (off[1], off[2]) == (-4, 4):
                return "opponent"
        if vals is not None and len(vals) == 1:
            return {0: "player0", 4: "player1"}.get(next(iter(vals)), "either")
        return "either"


def lp_categories(stores):
    """(categories, signs, exact) of the decoded LP stores: damage for a negative amount, gain_lp for a positive
    one, both when the sign is unknown. `exact` is True when every amount is a constant."""
    cats, signs, exact = set(), [], True
    for side, v in stores:
        iv = _iv(v)
        if iv is None or not _is_const(v):
            exact = False
        if iv is None or (iv[0] < 0 < iv[1]):
            cats.update(LP_CATEGORIES)
            signs.append(f"{side}:?")
        elif iv[1] <= 0:
            cats.add("damage")
            signs.append(f"{side}:{iv[0] if iv[0] == iv[1] else '-'}")
        else:
            cats.add("gain_lp")
            signs.append(f"{side}:+{iv[0] if iv[0] == iv[1] else ''}")
    return cats, signs, exact


# ---------------------------------------------------------------------------------------------- per-card closure


class FamilySplitter:
    """Per-card closures of the slot handlers on top of an effect_classify.Classifier."""

    def __init__(self, classifier):
        self.cl = classifier
        self.module, self.registry, self.mapping = classifier.module, classifier.registry, classifier.mapping
        by_name = {n: a for a, n in self.registry.names.items() if BASE <= a < TEXT_END}
        self.effective_id = by_name.get(EFFECTIVE_ID_NAME)
        self.lp_resolve = by_name.get(LP_RESOLVE_NAME)
        self.lp_chain = by_name.get(LP_CHAIN_NAME)
        self.set_face = by_name.get(SET_FACE_NAME)
        self.scanner = SpecialisedScanner(self.module, self.registry, self.effective_id)
        self.lp = LpDecoder(self.module, self.lp_chain, self.registry.end(self.lp_chain), self.effective_id) \
            if self.lp_chain else None
        self._scans, self._lp, self._closures = {}, {}, {}

    def scan(self, f, card_id, args, ctx):
        key = (f, card_id if ctx else None, tuple(sorted(args.items())), ctx)
        if key not in self._scans:
            self._scans[key] = self.scanner.scan(f, self.registry.end(f), card_id, args, frozenset(ctx))
        return self._scans[key]

    def lp_decode(self, card_id):
        if card_id not in self._lp:
            stores, complete = self.lp.decode(card_id)
            cats, signs, exact = lp_categories(stores)
            self._lp[card_id] = {"categories": cats, "signs": signs, "exact": exact and complete,
                                 "complete": complete}
        return self._lp[card_id]

    def closure(self, handler, card_id):
        """effect_classify.Classifier.closure for one card id: {categories, commands, callees, decided, id_reads,
        fallback, lp}."""
        key = (handler, card_id)
        if key in self._closures:
            return self._closures[key]
        cats, cmds, callees = set(), set(), {}
        decided = id_reads = reveals = 0
        fallback, lp = False, None
        if self.cl.root_names:
            hit = self.mapping.lookup(handler, self.registry.name(handler))
            if hit and hit[0] and hit[1] in ("effect", "meta") and handler != self.lp_resolve:
                cats.add(hit)
        frontier, seen, callbacks = [(handler, {}, (A0,))], {handler}, []
        if handler == self.lp_resolve and self.lp:
            frontier = []
            lp = self.lp_decode(card_id)
            cats.update((c, "effect") for c in lp["categories"])
        for level in range(1, self.cl.depth + 1):
            nxt, later = [], []
            visits = [(cb, {}, ()) for cb in callbacks]
            for f, args, ctx in frontier:
                s = self.scan(f, card_id, args, ctx)
                decided += s.decided
                id_reads += s.id_reads
                fallback |= s.fallback
                cats.update(self.mapping.store_categories(s.stores))
                resolved = [(self.cl.resolve(c.target, c.args), c.ctx_args) for c in s.calls if c.kind != "indirect"]
                faces = {a.get(6) for (t, a), _ in resolved if t == self.set_face}
                reveal = ec.const(0) in faces and ec.const(1) in faces
                for (target, a), ctx_args in resolved:
                    if reveal and target == self.set_face:  # face-up then face-down again: a look, not a flip
                        cats.add(("reveal", "meta"))
                        reveals += 1
                        continue
                    visits.append((target, a, ctx_args))
            for target, args, ctx in visits:
                name = self.registry.name(target)
                if target not in callees or callees[target][1] > level:
                    callees[target] = (name, level)
                if target == self.lp_resolve and self.lp:
                    lp = self.lp_decode(card_id)
                    cats.update((c, "effect") for c in lp["categories"])
                    continue
                cats.update(self.mapping.arg_categories(name, args))
                hit = self.mapping.lookup(target, name)
                if hit:
                    cat, role = hit
                    if role == "queue":
                        a0 = args.get(4)
                        if a0 and a0[0] & 0xFFF == 0xFFF:
                            code = a0[1] & 0xFFF
                            cmds.add(code)
                            cats.update(self.mapping.cmds.get(code, ()))
                    elif cat and role in ("effect", "meta"):
                        cats.add((cat, role))
                    continue
                if target not in seen and BASE <= target < TEXT_END:
                    seen.add(target)
                    nxt.append((target, args, ctx))
                    later += [cb for cb in self.cl.callbacks(args) if cb not in seen]
            frontier, callbacks = nxt, list(dict.fromkeys(later))
        result = {"categories": cats, "commands": cmds, "callees": callees, "decided": decided,
                  "id_reads": id_reads, "fallback": fallback, "lp": lp, "reveals": reveals}
        self._closures[key] = result
        return result


def effect_set(cats):
    return {c for c, r in cats if r == "effect"}


def family_table(classifier, records=None, keep=None):
    """Shared resolve handlers: [(handler, records [(table, index, card id)], categories)], ranked by
    records x effect categories. `keep(handler)` admits a handler of a single card as well."""
    fam = collections.defaultdict(list)
    for table, index, cid, handlers in (records if records is not None else ec.effect_records(classifier.module)):
        if handlers[0]:
            fam[handlers[0]].append((table, index, cid))
    rows = []
    for h, recs in fam.items():
        if len({c for _, _, c in recs}) < 2 and not (keep and keep(h)):
            continue
        cats = effect_set(classifier.closure(h)["categories"])
        rows.append((h, recs, cats))
    rows.sort(key=lambda r: (-len(r[1]) * len(r[2]), r[0]))
    return rows


def split_records(classifier, splitter=None, min_categories=2, records=None):
    """Refine the resolve slot of every record whose resolve handler is shared by several cards and reaches at
    least `min_categories` effect categories, and of every record whose resolve closure reaches
    duel_effects_resolve_lp_change (the LP decode). Returns ({(table, index): refinement}, families) where a refinement
    is {card_id, handler, before, after, removed, method, confidence, lp_signs, decided}."""
    splitter = splitter or FamilySplitter(classifier)
    lists = {}
    out, families = {}, []
    reaches_lp = lambda h: splitter.lp_resolve is not None and splitter.lp_resolve in classifier.closure(h)["callees"]
    for h, recs, cats in family_table(classifier, records, reaches_lp):
        if len(cats) < min_categories and not reaches_lp(h):
            continue
        fam = {"handler": h, "name": classifier.registry.name(h), "records": len(recs),
               "cards": len({c for _, _, c in recs}), "refined": 0, "before": set(), "after": set()}
        for table, index, cid in recs:
            base = classifier.closure(h)
            c = splitter.closure(h, cid)
            if classifier.mapping.dispatch:
                base = ec.dispatched(classifier, base, cid, lists)
                c = ec.dispatched(classifier, c, cid, lists)
            before, after = effect_set(base["categories"]), effect_set(c["categories"])
            lp = c.get("lp")
            # a refinement only removes categories, except that the LP decode may name the LP category that the
            # depth limit hid (a wrapper reaching duel_core_inflict_damage but not duel_core_gain_lp)
            lp_added = (lp["categories"] - before) if lp and before & set(LP_CATEGORIES) else set()
            after = (after & before) | lp_added
            if lp is not None:
                method = "lp_chain"
                if not lp["categories"]:  # the card has no case in the chain (or only zero amounts): keep
                    after = before
                    method = "lp_chain_unresolved"
                confidence = "high" if lp["exact"] and method == "lp_chain" else "medium"
            elif c["id_reads"]:
                method = "branch_fallback" if c["fallback"] else "branch"
                confidence = "medium" if c["fallback"] else "high"
            else:
                method = "reveal" if c["reveals"] else "unchanged"
                confidence = "medium"
            if not after and before:  # never leave a record without the categories it had
                after, method, confidence = before, method + "_empty", "medium"
            fam["before"] |= before
            fam["after"] |= after
            removed, added = before - after, after - before
            if removed or added:
                fam["refined"] += 1
            out[(table, index)] = {"card_id": cid, "handler": h, "before": sorted(before), "after": sorted(after),
                                   "removed": sorted(removed), "added": sorted(added), "method": method,
                                   "confidence": confidence,
                                   "lp_signs": lp["signs"] if lp else [], "decided": c["decided"],
                                   "id_reads": c["id_reads"]}
        families.append(fam)
    return out, families


# ---------------------------------------------------------------------------------------------- reporting

# Hand-checked sample: 50 family records drawn at random (seed 7) from the output of this tool on the disc, 47 of
# them judged against public card knowledge (3 uncertain readings left out). Key (card id, resolve handler) ->
# the categories of the record's "before" set that are correct for that resolve slot. Ids and category names only.
# Lenient on implementation labels, as the spot check of effect-classification.md: attach_effect for markers,
# send_to_graveyard and destroy for the union substitution. Used by --check for the before/after precision.
_SAMPLE_ROWS = """
0x1457 0x09c89840 add_to_hand attach_effect search_graveyard
0x194f 0x09c78804 search_deck shuffle special_summon
0x1b8b 0x09c77648 gain_lp
0x140b 0x09c78804 search_deck shuffle special_summon
0x147d 0x09c8ad6c atk_change attach_effect
0x15a0 0x09c77648 damage
0x1bc9 0x09c987e8 draw send_to_graveyard
0x16fa 0x09c77648 damage
0x1939 0x09c78804 search_deck shuffle special_summon
0x1ec9 0x09cb70d4 atk_change discard search_hand send_to_graveyard
0x1506 0x09c77648 gain_lp
0x18c6 0x09c81650 attach_effect control_change
0x1c68 0x09c77648 damage
0x13b0 0x09c81650 attach_effect control_change
0x1689 0x09c7b510 add_to_hand search_deck shuffle
0x1e45 0x09c86648 equip place_on_field
0x1d3e 0x09c8a994 mill search_deck send_to_graveyard shuffle
0x1593 0x09c90d64 deck_order search_deck shuffle
0x1d07 0x09c90d64 deck_order search_deck shuffle
0x16bc 0x09c951f4 equip place_on_field
0x1cd1 0x09c91cd0 attach_effect destroy equip send_to_graveyard special_summon
0x1d94 0x09c81964 add_to_hand shuffle
0x1520 0x09c77648 damage
0x1d92 0x09caefac banish draw search_hand send_to_graveyard
0x1d85 0x09c78bac search_graveyard search_hand special_summon
0x17d9 0x09c78bac search_deck search_hand shuffle special_summon
0x1c78 0x09c78804 search_deck shuffle special_summon
0x1307 0x09c77648 damage
0x12fd 0x09c8178c destroy negate
0x1527 0x09c7bf94 atk_change attach_effect
0x1e54 0x09c87a78 negate_attack
0x1ed6 0x09cb70d4 atk_change discard search_hand send_to_graveyard
0x1bc1 0x09c81964 add_to_hand shuffle
0x1481 0x09c8aeb8 search_extra special_summon tribute
0x1c76 0x09c78804 search_deck shuffle special_summon
0x1476 0x09c8b160 battle declare_attack
0x1cfe 0x09c8ad6c atk_change attach_effect
0x1862 0x09c8ad6c atk_change attach_effect
0x1ebe 0x09c792ac position_change
0x18c1 0x09c9f548 attach_effect control_change
0x17c9 0x09c7bf94 atk_change attach_effect
0x1db1 0x09c78804 search_deck shuffle special_summon
0x12a2 0x09c77648 gain_lp
0x1d0a 0x09c908bc search_deck shuffle special_summon
0x1d24 0x09c7b510 add_to_hand search_deck shuffle
0x166a 0x09c795f0 special_summon token
0x1abd 0x09c77648 damage
"""
SAMPLE = {(int(c, 16), int(h, 16)): set(cats) for c, h, *cats in (line.split() for line in _SAMPLE_ROWS.split("\n")
                                                                   if line.strip())}


def precision(refined, sample=SAMPLE):
    """(correct, assigned) labels over the sample records, before and after the split."""
    b = a = bc = ac = 0
    for r in refined.values():
        good = sample.get((r["card_id"], r["handler"]))
        if good is None:
            continue
        b += len(r["before"])
        a += len(r["after"])
        bc += len(set(r["before"]) & good)
        ac += len(set(r["after"]) & good)
    return (bc, b), (ac, a)


def summary(refined, families):
    lines = []
    total = len(refined)
    changed = [r for r in refined.values() if r["removed"] or r["added"]]
    lines.append(f"families split: {len(families)} resolve handlers (shared with >= 2 categories, or reaching the "
                 f"LP handler); {total} records examined, {len(changed)} refined "
                 f"({sum(len(r['removed']) for r in changed)} labels removed, "
                 f"{sum(len(r['added']) for r in changed)} LP labels added)")
    methods = collections.Counter(r["method"] for r in refined.values())
    lines.append("methods: " + ", ".join(f"{k} {v}" for k, v in methods.most_common()))
    labels_before = sum(len(r["before"]) for r in refined.values())
    labels_after = sum(len(r["after"]) for r in refined.values())
    lines.append(f"labels on these records: {labels_before} before, {labels_after} after")
    removed = collections.Counter(c for r in changed for c in r["removed"])
    lines.append("labels removed by category: " + ", ".join(f"{k} {v}" for k, v in removed.most_common()))
    lines.append("top families (records, categories before -> union after, records refined):")
    for f in families[:12]:
        lines.append(f"  {f['handler']:#010x} {f['name']}: {f['records']} records, "
                     f"{' '.join(sorted(f['before']))} -> {' '.join(sorted(f['after']))}; refined {f['refined']}")
    return lines


def write_csv(path, rows):
    fields = list(rows[0]) if rows else ["empty"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Split the categories of family-shared effect handlers per card.")
    parser.add_argument("prx", type=Path, help="gmodule/rel_duel_eng.prx")
    parser.add_argument("-o", "--out", type=Path, help="output directory (under extracted/)")
    parser.add_argument("--check", action="store_true", help="print the summary and the sample precision")
    parser.add_argument("--functions", type=Path, default=HERE.parent / "re" / "functions.csv")
    parser.add_argument("--categories", type=Path, default=HERE / "effect_categories.csv")
    parser.add_argument("--depth", type=int, default=3)
    parser.add_argument("--cardinfo", type=Path, help="duelsys/cardinfo_eng.ehp: add a card-name column")
    args = parser.parse_args(argv)
    if not args.check and not args.out:
        parser.error("-o/--out is required unless --check is given")
    data = args.prx.read_bytes()
    module = ep.Module(data)
    registry = ec.Registry(ec.load_registry(args.functions), module)
    mapping = ec.Mapping.load(args.categories)
    classifier = ec.Classifier(module, registry, mapping, args.depth)
    splitter = FamilySplitter(classifier)
    problems = []
    if splitter.lp_chain is None or splitter.lp_resolve is None:
        problems.append("the registry names neither duel_effects_get_lp_change_amounts nor _resolve_lp_change")
    refined, families = split_records(classifier, splitter)
    lines = summary(refined, families)
    (bc, b), (ac, a) = precision(refined)
    if b:
        n = sum(1 for r in refined.values() if (r["card_id"], r["handler"]) in SAMPLE)
        lines.append(f"sample precision on {n} records: before {bc}/{b} = {100 * bc / b:.0f} %, "
                     f"after {ac}/{a} = {100 * ac / max(1, a):.0f} %")
    for r in refined.values():
        if not set(r["added"]) <= set(LP_CATEGORIES):
            problems.append(f"record of {r['card_id']:#06x}: refinement adds non-LP categories")
    names = ep.load_names(args.cardinfo) if args.cardinfo else {}
    for p in problems:
        print("problem:", p, file=sys.stderr)
    print("\n".join(lines))
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        rows = [{"card_id": f"{r['card_id']:#06x}", "card": names.get(r["card_id"], ""), "table": t, "index": i,
                 "handler": f"{r['handler']:#010x}", "before": " ".join(r["before"]), "after": " ".join(r["after"]),
                 "removed": " ".join(r["removed"]), "added": " ".join(r["added"]), "method": r["method"],
                 "confidence": r["confidence"],
                 "lp_amounts": " ".join(r["lp_signs"]), "decided_branches": r["decided"]}
                for (t, i), r in sorted(refined.items())]
        write_csv(args.out / "family_split.csv", rows)
        write_csv(args.out / "families.csv", [
            {"handler": f"{f['handler']:#010x}", "name": f["name"], "records": f["records"], "cards": f["cards"],
             "categories": " ".join(sorted(f["before"])), "after_union": " ".join(sorted(f["after"])),
             "refined_records": f["refined"]} for f in families])
        print(f"wrote {len(rows)} records to {args.out}")
    print("ok" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
