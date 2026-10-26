#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Classify the card-effect handlers of gmodule/rel_duel_eng.prx by the helpers and engine commands they reach.

See docs/subsystems/effect-classification.md. For every record of the four 24-byte effect tables
(docs/formats/effect-tables.md) and every one of its five handlers, the tool scans the MIPS code for calls
(`jal`, tail calls through `j`, linking branches), follows them to a bounded depth, and maps the callees to
effect categories through tools/effect_categories.csv. The mapping is driven by the function names in
re/functions.csv at run time, so the classification improves as functions are named. Command codes posted
through the engine queue are recovered when the op word in a0 is a constant (known-bits dataflow, below).
The AI handlers of the priority tables (tools/ai_tables.py) are grouped by the same callee signature.

  effect_classify.py <USRDIR>/gmodule/rel_duel_eng.prx -o extracted/effect_classify [--cardinfo <cardinfo_eng.ehp>]
                     [--functions re/functions.csv] [--categories tools/effect_categories.csv] [--depth 3]
                     [--boot <SYSDIR>/BOOT.BIN]
  effect_classify.py <USRDIR>/gmodule/rel_duel_eng.prx --check

Outputs in the -o directory (game data: keep them under extracted/, never in git): effect_classes.csv (one row
per record), worklist.csv (unnamed callees ranked by the number of records that reach them), ai_clusters.csv
and summary.txt. Addresses are runtime addresses with the module at 0x09be1400.
"""

import argparse
import bisect
import collections
import csv
import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ep = _load("re_effect_params", "effect_params.py")
ait = _load("re_ai_tables", "ai_tables.py")

BASE, TEXT_END = ep.BASE, ep.TEXT_END
STUB_END = 0x09DE71FC  # end of .sceStub.text (import stubs, patched at load time)
TABLES = ep.TABLES
SLOTS = [("resolve", 0x04), ("target_filter", 0x08), ("condition", 0x0C), ("activation", 0x10),
         ("target_choice", 0x14)]
FULL = 0xFFFFFFFF
RA, SP = 31, 29
ARG_REGS = range(4, 12)  # a0-a3 and t0-t3 (a4-a7 in the PSP's EABI)
ARG_NAMES = {f"a{i}": 4 + i for i in range(8)}
CLOBBERED = [1, 2, 3, *range(4, 16), 24, 25, RA]  # caller-saved registers, unknown after a call
DEFAULT_NAME = re.compile(r"^(thunk_)?(FUN|SUB|LAB)_[0-9a-fA-F]+$")

# ---------------------------------------------------------------------------------------------- known bits
# A register value is (mask, value): the bits set in mask are known and equal to the same bits of value.


def _low_known(mask):
    n = 0
    while n < 32 and mask >> n & 1:
        n += 1
    return n


def kb_add(a, b, sub=False):
    k = min(_low_known(a[0]), _low_known(b[0]))
    if not k:
        return None
    m = (1 << k) - 1
    return m, ((a[1] - b[1]) if sub else (a[1] + b[1])) & m


def kb_or(a, b):
    m = (a[0] & b[0]) | (a[0] & a[1]) | (b[0] & b[1])
    return m, (a[1] | b[1]) & m


def kb_and(a, b):
    m = (a[0] & b[0]) | (a[0] & ~a[1]) | (b[0] & ~b[1])
    return m & FULL, a[1] & b[1] & m


def kb_xor(a, b):
    m = a[0] & b[0]
    return m, (a[1] ^ b[1]) & m


def kb_sll(a, sa):
    return ((a[0] << sa) | ((1 << sa) - 1)) & FULL, (a[1] << sa) & FULL


def kb_srl(a, sa):
    top = FULL ^ (FULL >> sa)
    return (a[0] >> sa) | top, a[1] >> sa


def kb_sra(a, sa):
    top = FULL ^ (FULL >> sa)
    if a[0] >> 31:
        return (a[0] >> sa) | top, (a[1] >> sa) | (top if a[1] >> 31 else 0)
    return a[0] >> sa, a[1] >> sa


def kb_meet(a, b):
    m = a[0] & b[0] & ~(a[1] ^ b[1]) & FULL
    return m, a[1] & m


def const(v):
    return FULL, v & FULL


def _get(regs, r):
    return (FULL, 0) if r == 0 else regs.get(r, (0, 0))


def _put(regs, r, v):
    if not r:
        return
    if v is None or not v[0]:
        regs.pop(r, None)
    else:
        regs[r] = (v[0], v[1] & v[0])


def written(w):
    """General register written by instruction word w (None if none or not modelled as a GPR write)."""
    op, rs, rt, rd, fn = w >> 26, w >> 21 & 31, w >> 16 & 31, w >> 11 & 31, w & 63
    if w == 0:
        return None
    if op == 0:
        if fn in (8, 0x0C, 0x0D, 0x0F, 0x11, 0x13, 0x18, 0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x2E, 0x2F) or 0x30 <= fn <= 0x37:
            return None
        return rd
    if op == 3:
        return RA
    if 8 <= op <= 0x0F or 0x20 <= op <= 0x26 or op in (0x30, 0x38):
        return rt
    if op in (0x10, 0x11, 0x12) and rs in (0, 2, 3):  # mfc0, mfc1/cfc1, VFPU mfv/mfvc
        return rt
    if op == 0x1F:
        return rd if fn == 0x20 else rt
    if op == 0x1C:
        return rd
    return None


def apply(regs, w):
    """Update `regs` (register -> known bits) for one non-control-transfer instruction word."""
    op, rs, rt, rd, sa, fn = w >> 26, w >> 21 & 31, w >> 16 & 31, w >> 11 & 31, w >> 6 & 31, w & 63
    imm = w & 0xFFFF
    simm = imm - 0x10000 if imm & 0x8000 else imm
    dst = written(w)
    if dst is None:
        return regs
    s, t = _get(regs, rs), _get(regs, rt)
    v = None
    if op == 0x0F:
        v = const(imm << 16)
    elif op in (8, 9):
        v = kb_add(s, const(simm))
    elif op == 0x0D:
        v = kb_or(s, const(imm))
    elif op == 0x0C:
        v = kb_and(s, const(imm))
    elif op == 0x0E:
        v = kb_xor(s, const(imm))
    elif op in (0x0A, 0x0B):
        v = (FULL ^ 1, 0)
    elif op == 0:
        if fn == 0:
            v = kb_sll(t, sa)
        elif fn == 2 and rs == 0:
            v = kb_srl(t, sa)
        elif fn == 3:
            v = kb_sra(t, sa)
        elif fn in (0x20, 0x21):
            v = kb_add(s, t)
        elif fn in (0x22, 0x23):
            v = kb_add(s, t, sub=True)
        elif fn == 0x24:
            v = kb_and(s, t)
        elif fn == 0x25:
            v = kb_or(s, t)
        elif fn == 0x26:
            v = kb_xor(s, t)
        elif fn == 0x27:
            o = kb_or(s, t)
            v = (o[0], ~o[1] & o[0])
        elif fn in (0x2A, 0x2B):
            v = (FULL ^ 1, 0)
        elif fn in (0x0A, 0x0B):  # movz / movn: either the old value or rs
            v = kb_meet(_get(regs, rd), s)
    elif op == 0x1F and fn == 0:  # ext rt, rs, pos, size
        size = rd + 1
        sm = (1 << size) - 1 if size < 32 else FULL
        v = ((s[0] >> sa) & sm) | (FULL ^ sm), (s[1] >> sa) & sm
    _put(regs, dst, v)
    return regs


def meet_states(a, b):
    out = {}
    for r in a.keys() & b.keys():
        m = kb_meet(a[r], b[r])
        if m[0]:
            out[r] = m
    return out


# ---------------------------------------------------------------------------------------------- scanner

Call = collections.namedtuple("Call", "site kind target args")  # kind: call, tail, indirect


def _is_branch(op, rt):
    return op in (4, 5, 6, 7, 0x14, 0x15, 0x16, 0x17) or (op == 1 and rt in (0, 1, 2, 3, 0x10, 0x11, 0x12, 0x13))


def scan_function(module, start, end, stores=None):
    """Calls made by the code in [start, end): a list of Call with the known bits of a0-a3/t0-t3 at the call.

    Forward dataflow over the function's instructions: the state at each branch target is the meet of every
    path reaching it, iterated to a fixed point. The delay slot of a branch, jump or call is executed before
    the transfer; a likely branch's delay slot only on the taken path. After a call the caller-saved
    registers are unknown. Code that is never reached from the entry (switch cases behind `jr reg`) is
    scanned afterwards from an all-unknown state. When `stores` is a dict, it receives
    {site: (runtime address, size, value)} for every sb/sh/sw of a known value to a known address."""
    end = min(end, TEXT_END)
    if not start < end:
        return []
    count = (end - start) // 4
    words = module.words(start, count)
    word = lambda pc: words[(pc - start) >> 2] if start <= pc < end else 0
    leaders = set()
    for k, w in enumerate(words):
        op, rt = w >> 26, w >> 16 & 31
        if _is_branch(op, rt):
            imm = w & 0xFFFF
            leaders.add(start + 4 * k + 4 + 4 * (imm - 0x10000 if imm & 0x8000 else imm))
        elif op == 2:
            leaders.add(BASE + ((w & 0x3FFFFFF) << 2))
    leaders = {p for p in leaders if start <= p < end}
    states, visited, calls = {}, set(), {}
    work = [(start, {})]
    cursor = start

    def arrive(pc, st):
        if not start <= pc < end:
            return
        if pc in leaders:
            if pc in states:
                new = meet_states(states[pc], st)
                if new == states[pc]:
                    return
                st = new
            states[pc] = st
            work.append((pc, None))  # processed with the state current at pop time, never a stale one
        else:
            work.append((pc, dict(st)))

    def record(site, kind, target, st):
        calls[site] = Call(site, kind, target, {r: st[r] for r in ARG_REGS if r in st})

    while True:
        while work:
            pc, st = work.pop()
            if st is None:
                st = dict(states[pc])
            while start <= pc < end:
                visited.add(pc)
                w = word(pc)
                op, rs, rt, fn = w >> 26, w >> 21 & 31, w >> 16 & 31, w & 63
                if _is_branch(op, rt):
                    imm = w & 0xFFFF
                    target = pc + 4 + 4 * (imm - 0x10000 if imm & 0x8000 else imm)
                    likely = op in (0x14, 0x15, 0x16, 0x17) or (op == 1 and rt in (2, 3, 0x12, 0x13))
                    visited.add(pc + 4)
                    after = apply(dict(st), word(pc + 4))
                    if op == 1 and rt >= 0x10:  # bltzal/bgezal family: a call
                        record(pc, "call", target, after)
                        for r in CLOBBERED:
                            after.pop(r, None)
                        arrive(pc + 8, after)
                        break
                    always = op == 4 and rs == rt or (op == 1 and rt in (1, 3) and rs == 0)
                    if not start <= target < end:
                        if always:
                            record(pc, "tail", target, after)
                            break
                    else:
                        arrive(target, after)
                    if not always:
                        arrive(pc + 8, st if likely else after)
                    break
                if op == 2:
                    visited.add(pc + 4)
                    after = apply(dict(st), word(pc + 4))
                    target = BASE + ((w & 0x3FFFFFF) << 2)
                    if start <= target < end:
                        arrive(target, after)
                    else:
                        record(pc, "tail", target, after)
                    break
                if op == 3 or (op == 0 and fn == 9):
                    visited.add(pc + 4)
                    after = apply(dict(st), word(pc + 4))
                    if op == 3:
                        record(pc, "call", BASE + ((w & 0x3FFFFFF) << 2), after)
                    else:
                        record(pc, "indirect", None, after)
                    for r in CLOBBERED:
                        after.pop(r, None)
                    arrive(pc + 8, after)
                    break
                if op == 0 and fn == 8:  # jr: return (ra) or a switch / computed jump
                    visited.add(pc + 4)
                    break
                if stores is not None and op in (0x28, 0x29, 0x2B):
                    b, v = _get(st, rs), _get(st, rt)
                    if b[0] == FULL and v[0] == FULL:
                        imm = w & 0xFFFF
                        addr = BASE + ((b[1] + (imm - 0x10000 if imm & 0x8000 else imm)) & FULL)
                        size = {0x28: 1, 0x29: 2, 0x2B: 4}[op]
                        stores[pc] = (addr & FULL, size, v[1] & ((1 << 8 * size) - 1))
                st = apply(st, w)
                pc += 4
                if pc in leaders:
                    arrive(pc, st)
                    break
        while cursor < end and (cursor in visited or word(cursor) == 0):
            cursor += 4
        if cursor >= end:
            break
        states.pop(cursor, None)
        arrive(cursor, {})
    return [calls[k] for k in sorted(calls)]


# ---------------------------------------------------------------------------------------------- registry


class Registry:
    """Names from re/functions.csv; function bounds of the module from the registry's start addresses."""

    def __init__(self, names, module, imports=None):
        self.names = names  # address -> name (bare hex ids only)
        self.imports = imports or {}  # import stub -> BOOT.BIN address
        starts = sorted(a for a in names if BASE <= a < TEXT_END)
        if len(starts) < 2:  # no registry for this module: fall back to the heuristic entry points
            starts = ep.function_starts(module)
        self.starts = starts

    def end(self, address):
        k = bisect.bisect_right(self.starts, address)
        return self.starts[k] if k < len(self.starts) else TEXT_END

    def name(self, address):
        if address in self.imports and self.imports[address] in self.names:
            return self.names[self.imports[address]]
        name = self.names.get(address)
        if not name:
            return f"FUN_{address:08x}"
        return name[6:] if name.startswith("thunk_") and not DEFAULT_NAME.match(name) else name


def load_registry(path):
    names = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["id"].startswith("0x"):
                names[int(row["id"], 16)] = row["name"]
    return names


def load_imports(boot_path, prx_bytes):
    """Import stub -> BOOT.BIN function address, through tools/prx_imports.py."""
    pi = _load("re_prx_imports", "prx_imports.py")
    boot = pi.Elf(Path(boot_path).read_bytes(), pi.BOOT_BASE)
    module = pi.Elf(prx_bytes, BASE)
    table = {(lib, nid): addr for nid, (lib, addr) in pi.exports(boot).items()}
    return {stub: table[(lib, nid)] for lib, nid, stub in pi.imports(module) if (lib, nid) in table}


# ---------------------------------------------------------------------------------------------- mapping


class Mapping:
    """tools/effect_categories.csv: see the header of that file."""

    def __init__(self, rows):
        self.named, self.cmds, self.args, self.stores = [], collections.defaultdict(list), [], []
        self.dispatch = []  # (callee name regex, 8-byte list address): per-card handler lists
        for row in rows:
            kind, pattern, cat, role = row["kind"].strip(), row["pattern"].strip(), row["category"].strip(), \
                row["role"].strip()
            if kind == "name":
                self.named.append((re.compile(pattern), None, cat, role))
            elif kind == "addr":
                self.named.append((None, int(pattern, 16), cat, role))
            elif kind == "cmd":
                self.cmds[int(pattern, 0)].append((cat, role))
            elif kind == "arg":
                regex, _, conds = pattern.rpartition("|")
                self.args.append((re.compile(regex), [self._arg_condition(c) for c in conds.split()], cat, role))
            elif kind == "dispatch":
                self.dispatch.append((re.compile(pattern), int(cat, 16)))
            elif kind == "store":
                conds = []
                for cond in pattern.split():
                    m = re.fullmatch(r"(0x[0-9a-fA-F]+)\s*([=&])\s*(0x[0-9a-fA-F]+|\d+)", cond)
                    if not m:
                        raise ValueError(f"bad store condition {cond!r}")
                    conds.append((int(m[1], 16), m[2], int(m[3], 0)))
                self.stores.append((conds, cat, role))
            else:
                raise ValueError(f"unknown mapping kind {kind!r}")

    @classmethod
    def load(cls, path):
        return cls.load_text(Path(path).read_text(encoding="utf-8"))

    @classmethod
    def load_text(cls, text):
        lines = [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
        return cls(csv.DictReader(lines))

    def lookup(self, address, name):
        """(category, role) of the first name/addr row matching, or None."""
        for regex, addr, cat, role in self.named:
            if (addr is not None and addr == address) or (regex is not None and regex.search(name)):
                return cat, role
        return None

    def store_categories(self, stores):
        """Categories of the store rows whose conditions all hold for some store of one function."""
        out = []
        for conds, cat, role in self.stores:
            if all(any(a == addr and (v == value if op == "=" else v & value == value) for a, _, v in stores)
                   for addr, op, value in conds):
                out.append((cat, role))
        return out

    @staticmethod
    def _arg_condition(cond):
        """'a3&0x1000' (bits known set), 'a3!&0x1000' (bits known clear) or 'a2=0xe' (whole register known)."""
        m = re.fullmatch(r"(a[0-7])(&|!&|=)(0x[0-9a-fA-F]+|\d+)", cond.strip())
        if not m:
            raise ValueError(f"bad arg condition {cond!r}")
        return ARG_NAMES[m[1]], m[2], int(m[3], 0)

    @staticmethod
    def _arg_holds(v, op, x):
        mask, value = v if v else (0, 0)
        if op == "&":
            return mask & x == x and value & x == x
        if op == "!&":
            return mask & x == x and not value & x
        return mask == FULL and value == x

    def arg_categories(self, name, args):
        out = []
        for regex, conds, cat, role in self.args:
            if all(self._arg_holds(args.get(reg), op, x) for reg, op, x in conds) and regex.search(name):
                out.append((cat, role))
        return out


# ---------------------------------------------------------------------------------------------- closure


class Classifier:
    """`root_names`: a slot handler matched by a `name`/`addr` row (a named generic resolver such as
    duel_effects_resolve_search_deck) gets that row's category as well; it is still scanned like any handler."""

    def __init__(self, module, registry, mapping, depth=3, root_names=True):
        self.module, self.registry, self.mapping, self.depth = module, registry, mapping, depth
        self.root_names = root_names
        self._scans, self._stores, self._closures, self._starts = {}, {}, {}, None

    def calls(self, address):
        if address not in self._scans:
            stores = {}
            self._scans[address] = scan_function(self.module, address, self.registry.end(address), stores)
            self._stores[address] = list(stores.values())
        return self._scans[address]

    def stores(self, address):
        self.calls(address)
        return self._stores[address]

    def resolve(self, target, args):
        """Follow thunks at the callee's entry (`j X; delay` or up to two ALU instructions, `j X; delay`, as in
        the target-filter stubs), applying their ALU code to the argument registers."""
        args = dict(args)
        for _ in range(4):
            if not BASE <= target < TEXT_END - 16:
                break
            w = self.module.words(target, 4)
            k = 0
            while k < 2 and w[k] >> 26 in (8, 9, 0x0C, 0x0D, 0x0E, 0x0F):
                k += 1
            if w[k] >> 26 != 2:
                break
            for x in (*w[:k], w[k + 1]):
                apply(args, x)
            target = BASE + ((w[k] & 0x3FFFFFF) << 2)
        return target, args

    def callbacks(self, args):
        """Function pointers among the known arguments of a call: a fully known value >= 0x10000 whose runtime
        address (module base + value; the PRX relocates the lui/addiu pair) is a registry function start. Only
        followed for callees that are descended into (filters handed to leaf scanners are not effects)."""
        if self._starts is None:
            self._starts = set(self.registry.starts)
        return [BASE + v for mask, v in args.values() if mask == FULL and 0x10000 <= v and BASE + v in self._starts]

    def closure(self, handler):
        """Facts reached from one handler: categories {(category, role)}, command codes, callee names by
        address with their minimum depth, unnamed callees, indirect call count."""
        if handler in self._closures:
            return self._closures[handler]
        cats, cmds, callees, indirect, unknown_cmd = set(), set(), {}, 0, 0
        if self.root_names:  # the handler's own name row adds its category; the handler is still descended into
            hit = self.mapping.lookup(handler, self.registry.name(handler))
            if hit and hit[0] and hit[1] in ("effect", "meta"):
                cats.add(hit)
        frontier, seen, callbacks = [handler], {handler}, []
        for level in range(1, self.depth + 1):
            nxt, later = [], []
            # (call target, argument state) pairs of this level: the calls of the frontier functions, plus the
            # callbacks handed to descended callees one level up (visited as if that callee called them)
            visits = [(cb, {}) for cb in callbacks]
            for f in frontier:
                cats.update(self.mapping.store_categories(self.stores(f)))
                for call in self.calls(f):
                    if call.kind == "indirect":
                        indirect += 1
                        continue
                    visits.append(self.resolve(call.target, call.args))
            for target, args in visits:
                name = self.registry.name(target)
                if target not in callees or callees[target][1] > level:
                    callees[target] = (name, level)
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
                        else:
                            unknown_cmd += 1
                    elif cat and role in ("effect", "meta"):
                        cats.add((cat, role))
                    continue
                if target not in seen and BASE <= target < TEXT_END:
                    seen.add(target)
                    nxt.append(target)
                    later += [cb for cb in self.callbacks(args) if cb not in seen]
            frontier, callbacks = nxt, list(dict.fromkeys(later))
        unnamed = {a for a, (n, _) in callees.items() if DEFAULT_NAME.match(n)}
        result = {"categories": cats, "commands": cmds, "callees": callees, "unnamed": unnamed,
                  "indirect": indirect, "unknown_commands": unknown_cmd}
        self._closures[handler] = result
        return result


def effect_records(module):
    """(table, index, card id, [5 handlers or None]) of the four 24-byte tables."""
    return list(ep.table_records(module))


def categories_text(cats, roles=("effect", "meta")):
    return " ".join(sorted({c for c, r in cats if r in roles}))


def _list_handlers(module, address):
    """card id -> handler of the 8-byte list at `address` (docs/formats/effect-tables.md)."""
    count = next((n for _, a, n in ep.LISTS if a == address), 0)
    out = {}
    for i in range(count):
        cid, handler = module.words(address + 8 * i, 2)
        out[cid] = module.pointer(handler)
    return out


def dispatched(classifier, closure, cid, lists):
    """`closure` with the categories of the card's own list handler added when it reaches a dispatcher named by
    a `dispatch` mapping row (for example the candidate-builder list behind duel_effects_build_candidate_list)."""
    extra = set()
    for regex, address in classifier.mapping.dispatch:
        if any(regex.search(name) for name, _ in closure["callees"].values()):
            if address not in lists:
                lists[address] = _list_handlers(classifier.module, address)
            handler = lists[address].get(cid)
            if handler:
                extra |= classifier.closure(handler)["categories"]
    return dict(closure, categories=closure["categories"] | extra) if extra - closure["categories"] else closure


def classify_records(classifier, cards=None):
    cards = cards or {}
    rows, facts, lists = [], [], {}
    for table, index, cid, handlers in effect_records(classifier.module):
        row = {"card_id": f"{cid:#06x}", "card": cards.get(cid, ""), "table": table, "index": index}
        per = []
        for (slot, _), h in zip(SLOTS, handlers):
            c = classifier.closure(h) if h else None
            if c and classifier.mapping.dispatch:
                c = dispatched(classifier, c, cid, lists)
            per.append(c)
            row[slot] = categories_text(c["categories"]) if c else ""
        res = per[0]
        row["commands"] = " ".join(f"{x:#04x}" for x in sorted(res["commands"])) if res else ""
        row["unknown_resolve"] = len(res["unnamed"]) if res else 0
        row["unknown_callees"] = len(set().union(*(c["unnamed"] for c in per if c)))
        row["handlers"] = " ".join(f"{h:#010x}" if h else "-" for h in handlers)
        rows.append(row)
        facts.append((table, cid, handlers, per))
    return rows, facts


def coverage(facts):
    total = len(facts)
    with_resolve = sum(1 for f in facts if f[3][0])
    covered = sum(1 for f in facts if f[3][0] and any(r == "effect" for _, r in f[3][0]["categories"]))
    any_slot = sum(1 for f in facts if any(c and any(r == "effect" for _, r in c["categories"]) for c in f[3]))
    per_table = {}
    for name, _, _ in TABLES:
        sub = [f for f in facts if f[0] == name]
        per_table[name] = (sum(1 for f in sub if f[3][0] and any(r == "effect" for _, r in f[3][0]["categories"])),
                           len(sub))
    return {"records": total, "with_resolve": with_resolve, "resolve_covered": covered, "any_slot_covered": any_slot,
            "per_table": per_table}


def worklist(facts, limit=None):
    """Unnamed callees ranked by the number of records whose closure (any slot) reaches them."""
    records, resolve, depth, handlers = collections.Counter(), collections.Counter(), {}, collections.defaultdict(set)
    for _, _, hs, per in facts:
        seen = set()
        for k, (h, c) in enumerate(zip(hs, per)):
            if not c:
                continue
            for a in c["unnamed"]:
                handlers[a].add(h)
                depth[a] = min(depth.get(a, 99), c["callees"][a][1])
                if k == 0:
                    resolve[a] += 1
            seen |= c["unnamed"]
        for a in seen:
            records[a] += 1
    rows = [{"address": f"{a:#010x}", "records": n, "resolve_records": resolve[a], "handlers": len(handlers[a]),
             "min_depth": depth[a]} for a, n in records.most_common()]
    return rows[:limit] if limit else rows


def ai_handlers(module_bytes):
    """AI handler address -> number of table entries (pair tables and u16 lists)."""
    m = ait.Module(module_bytes)
    counts = collections.Counter()
    for _, _, _, _, _, h in ait.entries(m):
        if h:
            counts[h] += 1
    for _, _, _, _, h in ait.list_entries(m):
        counts[h] += 1
    return counts


def ai_clusters(classifier, handlers):
    groups = collections.defaultdict(list)
    for h in handlers:
        c = classifier.closure(h)
        groups[tuple(sorted(n for n, _ in c["callees"].values()))].append(h)
    rows = []
    for sig, members in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        cats = set().union(*(classifier.closure(h)["categories"] for h in members))
        rows.append({"cluster": len(rows), "handlers": len(members), "entries": sum(handlers[h] for h in members),
                     "categories": categories_text(cats), "callees": " ".join(sig) or "(none)",
                     "members": " ".join(f"{h:#010x}" for h in sorted(members))})
    return rows


def ai_callee_counts(classifier, handlers):
    """Callee name -> number of AI handlers whose closure reaches it."""
    counts = collections.Counter()
    for h in handlers:
        counts.update({n for n, _ in classifier.closure(h)["callees"].values()})
    return counts


# ---------------------------------------------------------------------------------------------- check


def check(module, registry, mapping):
    problems = []
    for name, address, count in TABLES:
        ids = [module.words(address + 24 * i, 1)[0] for i in range(count)]
        if ids != sorted(ids):
            problems.append(f"table {name} at {address:#x} is not sorted by card id")
        for i in range(count):
            for w in module.words(address + 24 * i + 4, 5):
                if w and module.pointer(w) is None:
                    problems.append(f"table {name} record {i}: handler word {w:#x} is not a .text offset")
    queue = [a for a in registry.starts if (mapping.lookup(a, registry.name(a)) or (None, None))[1] == "queue"]
    if not queue:
        problems.append("no function in the registry matches a queue row of the mapping")
    problems += [f"AI tables: {p}" for p in ait.check(ait.Module(module.data))]
    return problems, queue


# ---------------------------------------------------------------------------------------------- output


def write_csv(path, rows):
    fields = list(rows[0]) if rows else ["empty"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def summary_lines(cov, rows, work, clusters, ai, classifier, top=30, ai_depth=1):
    pct = lambda a, b: f"{100 * a / b:.1f} %" if b else "-"
    lines = [f"depth {classifier.depth}; {len(classifier._scans)} functions scanned",
             f"records {cov['records']}, with a resolve handler {cov['with_resolve']}",
             f"coverage (resolve slot has an effect category): {cov['resolve_covered']} / {cov['records']} = "
             f"{pct(cov['resolve_covered'], cov['records'])} of all records, "
             f"{pct(cov['resolve_covered'], cov['with_resolve'])} of records with a resolve handler",
             f"any slot has an effect category: {cov['any_slot_covered']} ({pct(cov['any_slot_covered'], cov['records'])})",
             "per table (resolve covered / records): " +
             ", ".join(f"{k} {a}/{b}" for k, (a, b) in cov["per_table"].items())]
    counts = collections.Counter(c for r in rows for c in r["resolve"].split())
    lines.append("resolve categories: " + ", ".join(f"{c} {n}" for c, n in counts.most_common()))
    lines.append(f"unnamed callees reached: {len(work)}; top {top} by records:")
    lines += [f"  {w['address']}  records {w['records']}  resolve {w['resolve_records']}  depth {w['min_depth']}"
              f"  {classifier.registry.name(int(w['address'], 16))}" for w in work[:top]]
    sizes = [c["handlers"] for c in clusters]
    lines.append(f"AI handlers {len(ai)} in {len(clusters)} clusters (identical callee sets at depth {ai_depth}); "
                 f"singletons {sizes.count(1)}; largest: " + ", ".join(
                     f"{c['handlers']} [{c['callees'][:60]}]" for c in clusters[:5]))
    return lines


def ai_lines(ai_classifier, ai, top=10):
    counts = ai_callee_counts(ai_classifier, ai)
    return ["AI callees shared by most handlers: " + ", ".join(f"{n} {c}" for n, c in counts.most_common(top))]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Classify the effect handlers of rel_duel_eng.prx by callees.")
    parser.add_argument("prx", type=Path, help="gmodule/rel_duel_eng.prx")
    parser.add_argument("-o", "--out", type=Path, help="output directory (under extracted/)")
    parser.add_argument("--check", action="store_true", help="structural checks and coverage summary only")
    parser.add_argument("--functions", type=Path, default=HERE.parent / "re" / "functions.csv")
    parser.add_argument("--categories", type=Path, default=HERE / "effect_categories.csv")
    parser.add_argument("--depth", type=int, default=3, help="call levels to follow (default 3)")
    parser.add_argument("--no-root-names", action="store_true",
                        help="ignore the name/addr rows that match a slot handler itself (only its callees count)")
    parser.add_argument("--ai-depth", type=int, default=1, help="call levels for the AI handler signatures (default 1)")
    parser.add_argument("--boot", type=Path, help="SYSDIR/BOOT.BIN: name import stubs by their current BOOT.BIN name")
    parser.add_argument("--cardinfo", type=Path, help="duelsys/cardinfo_eng.ehp: add a card-name column")
    parser.add_argument("--top", type=int, default=30, help="worklist entries in the summary")
    args = parser.parse_args(argv)
    data = args.prx.read_bytes()
    module = ep.Module(data)
    imports = load_imports(args.boot, data) if args.boot else None
    registry = Registry(load_registry(args.functions), module, imports)
    mapping = Mapping.load(args.categories)
    problems, queue = check(module, registry, mapping)
    for p in problems:
        print("problem:", p, file=sys.stderr)
    if not args.check and not args.out:
        parser.error("-o/--out is required unless --check is given")
    classifier = Classifier(module, registry, mapping, args.depth, root_names=not args.no_root_names)
    cards = ep.load_names(args.cardinfo) if args.cardinfo else None
    rows, facts = classify_records(classifier, cards)
    cov = coverage(facts)
    work = worklist(facts)
    ai = ai_handlers(data)
    ai_classifier = Classifier(module, registry, mapping, args.ai_depth, root_names=not args.no_root_names)
    ai_classifier._scans, ai_classifier._stores = classifier._scans, classifier._stores
    clusters = ai_clusters(ai_classifier, ai)
    lines = summary_lines(cov, rows, work, clusters, ai, classifier, args.top, args.ai_depth)
    lines += ai_lines(ai_classifier, ai)
    if args.check:
        queue_sites = sum(1 for a in classifier._scans for c in classifier._scans[a]
                          if c.kind != "indirect" and classifier.resolve(c.target, c.args)[0] in queue)
        lines.insert(0, f"queue functions: {' '.join(f'{a:#010x}' for a in queue)}; "
                        f"{queue_sites} queue call sites in the scanned functions")
        for line in lines[:6] + lines[-2:]:
            print(line)
        print("ok" if not problems else f"{len(problems)} problem(s)")
        return 1 if problems else 0
    args.out.mkdir(parents=True, exist_ok=True)
    write_csv(args.out / "effect_classes.csv", rows)
    write_csv(args.out / "worklist.csv", [{**w, "name": registry.name(int(w["address"], 16))} for w in work])
    write_csv(args.out / "ai_clusters.csv", clusters)
    (args.out / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
