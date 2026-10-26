#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Find the card ids that the game's code tests directly, outside the effect tables.

See docs/formats/card-refs.md. Many cards have no record in the effect tables of gmodule/rel_duel_eng.prx: the
engine implements them by testing the card id inside shared code (`if (id == K)` chains, `switch (id)`, range
tests) or by passing the id to a helper ("is card K on the field"). The tool scans every function of the
module (and optionally BOOT.BIN and rel_duel_draw.prx) for 14-bit card-id immediates and keeps the ones whose
value is *used* as a card id:

  eq       `li rX, K` whose first reader is beq/bne(l), xor or subu, or `xori rY, rX, K`
  lt       `li rX, K` read by slt/sltu (one bound of a range test)
  bound    `slti/sltiu rY, rX, K` (one bound of a range test)
  range    `addiu rY, rX, -K; sltiu rZ, rY, N` without a jump table: every id of [K, K+N)
  switch   the same followed by a jump table: every id of [K, K+N) whose target is not the default
  arg      `li a0-t3, K` before a jal/j (the id is an argument), or in the delay slot of a jal
  store    `li rX, K` stored to memory (an id written into a duel structure)
  return   `li v0, K` reaching `jr ra` (a function that returns a card id)

The first reader is searched on the straight line after the `li` (24 instructions, through one `move`); an
`li` in a branch delay slot is followed on the taken path first. Immediates read in any other way (arithmetic,
multiplication, unused) are dropped. For eq references the other operand is traced back on the straight line
(`operand`): a u16 load, a 0x3fff mask, the result of a named call, an argument register, ...

  card_refs.py <USRDIR>/gmodule/rel_duel_eng.prx list -o extracted/card_refs [--cardinfo <cardinfo_eng.ehp>]
               [--boot <SYSDIR>/BOOT.BIN] [--draw <USRDIR>/gmodule/rel_duel_draw.prx] [--functions re/functions.csv]
  card_refs.py <USRDIR>/gmodule/rel_duel_eng.prx --check [--cardinfo ...] [--boot ...] [--draw ...]
               [--spec extracted/card_effects/card_effects.csv]
  card_refs.py <USRDIR>/gmodule/rel_duel_eng.prx describe [--card ID ...] [-o DIR] [--spec ...] [...]

Semantics: tools/engine_ref_semantics.csv maps the engine functions (registry name, glob, address or address
range of unnamed functions) to a semantic tag, a template phrase and an optional per-card parameter read from
the value of the matched path (the branch taken when the id compares equal). Every eq/switch/arg reference
gets a `semantics` dict; describe() merges them per card; --check reports the coverage over the engine_only
cards of card_effects.csv (--spec).

Library: card_refs(prx_bytes, functions=None, names=None, base=0x09be1400, module="rel_duel_eng")
-> {card id: [dict]}. Outputs (game data: keep them under extracted/, never in git): card_refs.csv (one row per
reference) and card_ref_functions.csv (one row per function). Addresses are runtime addresses (rel_duel_eng at
0x09be1400, BOOT.BIN at 0x08804000, rel_duel_draw at 0x0983fb00).
"""

import argparse
import bisect
import collections
import csv
import fnmatch
import importlib.util
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ep = _load("re_effect_params", "effect_params.py")
BASE = ep.BASE
FIRST_CARD, LAST_CARD = ep.FIRST_CARD, ep.LAST_CARD
V0, SP, RA = ep.V0, ep.SP, ep.RA
MODULES = {"rel_duel_eng": 0x09BE1400, "BOOT.BIN": 0x08804000, "rel_duel_draw": 0x0983FB00}
ARG_REGS = range(4, 12)  # a0-a3, t0-t3 (EABI)
CALLER_SAVED = {1, 2, 3, *range(4, 16), 24, 25}
WINDOW = 24  # instructions scanned forward for the first reader of a loaded id
BACK = 2048  # instructions scanned back for the definition of the other operand of a compare
MAX_RANGE = 128  # widest `addiu -K; sltiu N` range accepted
ID_MASK = 0x3FFF
DEFAULT_NAME = re.compile(r"^(thunk_)?(FUN|SUB|LAB)_[0-9a-fA-F]+$")
KINDS = ("eq", "switch", "range", "lt", "bound", "arg", "store", "return")
STRONG = {"eq", "switch", "arg"}  # kinds that name one card; the others are range bounds or data flow

# Direct tests established in the documents, used by --check to measure recall: (card id, function, kind).
KNOWN = [
    (0x12EC, 0x09C779BC, "eq"),  # Pot of Greed in duel_effects_get_draw_count (effect-tables.md)
    (0x1975, 0x09C54248, "eq"),  # Dark Deal in duel_effects_link_should_resolve (chain.md)
    (0x1B61, 0x09C54248, "arg"),  # Flashbang-type global marker, same function (chain.md)
    (0x1D0A, 0x09BF275C, "eq"),  # duel_effects_get_spell_speed special cases (chain.md)
    (0x1C03, 0x09BF275C, "eq"),
    (0x0FB6, 0x09C43148, "arg"),  # used-this-turn marker in duel_effects_mark_used_this_turn (chain.md)
    (0x0FB6, 0x09C5698C, "arg"),  # ... and in duel_effects_not_used_this_turn (chain.md)
    (0x0FB7, 0x09DCAE58, "arg"),  # Forbidden One pieces 0xfb7-0xfbb passed to 0x09c033a8 by duel_core_check_win
    (0x0FBB, 0x09DCAE58, "arg"),  # (battle.md)
]

# ---------------------------------------------------------------------------------------------- module image


def text_range(data, base):
    """[start, end) of the .text section as runtime addresses (section addresses are module offsets); without
    section headers, the first PT_LOAD segment."""
    shoff, = struct.unpack_from("<I", data, 0x20)
    entsize, count, strndx = struct.unpack_from("<HHH", data, 0x2E)
    if shoff and count and shoff + count * entsize <= len(data):
        headers = [struct.unpack_from("<IIIIII", data, shoff + i * entsize) for i in range(count)]
        names = headers[strndx][4]
        for h in headers:
            if data[names + h[0]:data.index(b"\0", names + h[0])] == b".text":
                return base + h[3], base + h[3] + h[5]
    _, vaddr, size = ep.Module(data, base).segments[0]
    return base + vaddr, base + vaddr + size


def reads(i):
    """Registers an instruction reads."""
    if i.op == 0:
        if i.fn in (0, 2, 3):  # sll srl sra
            return {i.rt}
        if i.fn in (8, 9):  # jr jalr
            return {i.rs}
        return {i.rs, i.rt}
    if i.op in (4, 5, 0x14, 0x15):
        return {i.rs, i.rt}
    if i.op in (1, 6, 7, 0x16, 0x17):
        return {i.rs}
    if i.kind == "store":
        return {i.rs, i.rt}
    if i.op in (2, 3, 0x0F):
        return set()
    return {i.rs}


def is_call(i):
    return i.op == 3 or (i.op == 0 and i.fn == 9)


def default_starts(module, start, end):
    """Heuristic function entries when no registry covers the module: jal targets, prologues after `jr ra`."""
    starts = {start}
    for pc in range(start, end, 4):
        i = ep.insn(module, pc)
        if i.op == 3 and start <= i.target < end:
            starts.add(i.target)
        if i.kind == "jr" and i.rs == RA and pc + 8 < end:
            nxt = ep.insn(module, pc + 8)
            if nxt.kind == "addiu" and nxt.rt == SP and nxt.rs == SP and nxt.simm < 0:
                starts.add(pc + 8)
    return sorted(starts)


# ---------------------------------------------------------------------------------------------- scan


class Scanner:
    def __init__(self, module, text, functions=None, names=None, label="rel_duel_eng"):
        self.m, self.label = module, label
        self.start, self.stop = text
        inside = sorted(f for f in (functions or ()) if self.start <= f < self.stop)
        self.functions = inside if len(inside) >= 2 else default_starts(module, self.start, self.stop)
        self.names = names or {}

    def function(self, pc):
        k = bisect.bisect_right(self.functions, pc) - 1
        return self.functions[k] if k >= 0 else None

    def end(self, start):
        k = bisect.bisect_right(self.functions, start)
        return self.functions[k] if k < len(self.functions) else self.stop

    def name(self, address):
        return self.names.get(address) or f"FUN_{address:08x}"

    def insn(self, pc):
        return ep.insn(self.m, pc)

    # -- forward: how is the loaded id used?

    def use(self, pc, reg, func, end):
        """First use of `reg` (just written by the instruction at `pc`): (kind, detail, reader pc) or None."""
        prev = self.insn(pc - 4) if pc - 4 >= func else None
        if prev is not None:
            if is_call(prev):  # li in the delay slot of a call or tail call
                return ("arg", self._callee(prev), pc - 4) if reg in ARG_REGS else None
            if prev.op == 2:
                return self._walk(prev.target, reg, end, func) if func <= prev.target < end else None
            if prev.kind == "jr":
                return ("return", "", pc - 4) if prev.rs == RA and reg == V0 else None
            if prev.is_branch:
                taken = self._walk(prev.target, reg, end, func) if func <= prev.target < end else None
                if taken or prev.likely:
                    return taken
        return self._walk(pc + 4, reg, end, func)

    def _walk(self, q, reg, end, func, depth=0):
        stop = min(end, q + 4 * WINDOW)
        jumped = False
        while q < stop:
            i = self.insn(q)
            if reg in reads(i) and reg:
                return self._classify(i, reg, end, func, depth)
            if is_call(i) or i.op == 2:
                if reg in ARG_REGS:
                    return "arg", self._callee(i), q
                if reg in CALLER_SAVED or i.op == 2:
                    return None
            if i.kind == "jr":
                d = self.insn(q + 4)
                if reg in reads(d):
                    return self._classify(d, reg, end, func, depth)
                return ("return", "", q) if i.rs == RA and reg == V0 and d.writes != V0 else None
            if i.writes == reg or jumped:
                return None
            if i.op == 4 and i.rs == i.rt == 0:  # unconditional branch: follow it after its delay slot
                d = self.insn(q + 4)
                if reg in reads(d):
                    return self._classify(d, reg, end, func, depth)
                if d.writes == reg or not func <= i.target < end:
                    return None
                q, jumped = i.target, False
                stop = min(stop, q + 4 * WINDOW)
                continue
            q += 4
        return None

    def _callee(self, i):
        return self.name(i.target) if i.op in (2, 3) else "indirect"

    def _classify(self, i, reg, end, func, depth):
        if i.op in (4, 5, 0x14, 0x15):
            return "eq", "", i.pc
        if i.op == 0 and i.fn in (0x26, 0x23):  # xor, subu: equality through a zero test
            return "eq", "", i.pc
        if i.op == 0 and i.fn in (0x2A, 0x2B):
            return "lt", "", i.pc
        if i.kind == "store" and i.rt == reg and i.rs != reg:
            return "store", f"{ {0x28: 8, 0x29: 16, 0x2B: 32}.get(i.op, 32)}-bit", i.pc
        if i.op == 0 and i.fn in (0x21, 0x25) and 0 in (i.rs, i.rt) and depth == 0 and i.rd:  # move
            return self._walk(i.pc + 4, i.rd, end, func, depth + 1)
        return None

    # -- backward: where does the compared register come from?

    def operand(self, at, func, reg):
        """Straight-line definition of `reg` before `at` (one level through moves)."""
        q = at - 4
        lo = max(func, at - 4 * BACK)
        while q >= lo:
            i = self.insn(q)
            if i.writes == reg and not (i.kind in ("addiu", "ori") and i.rs == 0 and
                                        FIRST_CARD <= i.imm <= LAST_CARD):
                if i.kind == "load":
                    return {0x25: "u16 load", 0x21: "s16 load", 0x23: "word load"}.get(i.op, "byte load")
                if i.kind == "andi":
                    return "masked id" if i.imm == ID_MASK else f"andi {i.imm:#x}"
                if i.op == 0 and i.fn in (0x21, 0x25) and 0 in (i.rs, i.rt):
                    src = i.rs or i.rt
                    return self.operand(q, func, src) if src != reg else "other"
                if i.op == 0 and i.fn in (2, 3):
                    return "shifted"
                return "computed"
            if is_call(i) and reg == V0:
                return f"result of {self._callee(i)}"
            if is_call(i) and reg in CALLER_SAVED:
                return "clobbered"
            q -= 4
        return "argument" if reg in ARG_REGS and q < func else "unknown"

    def scan(self):
        """Yield one dict per card-id reference."""
        for pc in range(self.start, self.stop, 4):
            func = self.function(pc)
            if func is None:
                continue
            i = self.insn(pc)
            end = self.end(func)
            if i.kind in ("addiu", "ori") and i.rs == 0 and FIRST_CARD <= i.imm <= LAST_CARD and i.rt:
                u = self.use(pc, i.rt, func, end)
                if u:
                    kind, detail, at = u
                    other = None
                    if kind == "eq":
                        r = self.insn(at)
                        regs = [x for x in (r.rs, r.rt) if x != i.rt]
                        other = self.operand(at, func, regs[0]) if regs and regs[0] else "zero"
                    yield self._row(i.imm, kind, detail, pc, at, func, operand=other)
            elif i.kind == "xori" and FIRST_CARD <= i.imm <= LAST_CARD:
                yield self._row(i.imm, "eq", "xori", pc, pc, func, operand=self.operand(pc, func, i.rs))
            elif i.kind in ("slti", "sltiu") and FIRST_CARD <= i.simm <= LAST_CARD + 1:
                yield self._row(i.simm, "bound", "", pc, pc, func)
            elif i.kind == "addiu" and i.rs not in (0, SP) and FIRST_CARD <= -i.simm <= LAST_CARD:
                yield from self._range(i, pc, func, end)

    def _range(self, i, pc, func, end):
        """`addiu rY, rX, -K` followed (within 4 instructions) by `sltiu rZ, rY, N`."""
        base = -i.simm
        for q in range(pc + 4, min(end, pc + 20), 4):
            j = self.insn(q)
            if j.kind == "sltiu" and j.rs == i.rt and 0 < j.simm <= MAX_RANGE:
                n = j.simm
                table = self._jump_table(q, end, n)
                operand = self.operand(pc, func, i.rs)
                if table:
                    default, targets = table
                    for k, t in enumerate(targets):
                        if t != default:
                            yield self._row(base + k, "switch", f"case {t:#010x}", pc, q, func, case=t,
                                            operand=operand)
                else:
                    for k in range(n):
                        yield self._row(base + k, "range", f"[{base:#x},{base + n:#x})", pc, q, func,
                                        operand=operand)
                return
            if j.writes == i.rt or j.is_branch:
                return

    def _jump_table(self, q, end, n):
        """Jump table after `sltiu rZ, reg, N; beq rZ, zero, default`: (default target, [N case targets])."""
        b = self.insn(q + 4)
        if not (b.op in (4, 0x14) and 0 in (b.rs, b.rt)):
            return None
        hi = None
        for p in range(q + 8, min(end, q + 40), 4):
            k = self.insn(p)
            if k.kind == "lui":
                hi = k.imm << 16
            if k.kind == "load" and k.op == 0x23 and hi is not None and k.rs != SP:
                address = (self.m.base + hi + k.simm) & 0xFFFFFFFF
                if not (self.m.contains(address) and self.m.contains(address + 4 * n - 4)):
                    return None
                targets = [self.m.base + v for v in self.m.words(address, n)]
                if not all(self.start <= t < self.stop for t in targets):
                    return None
                return b.target, targets
            if k.kind == "jr":
                return None
        return None

    def _row(self, cid, kind, detail, pc, at, func, case=None, operand=None):
        return {"card_id": cid, "kind": kind, "detail": detail, "address": pc, "use": at, "function": func,
                "function_name": self.name(func), "module": self.label, "operand": operand or "", "case": case}


def nearby_constants(scanner, row, span=6):
    """Small non-card immediates (`li rX, v`) within `span` instructions of the reference."""
    out = []
    end = scanner.end(row["function"])
    for q in range(max(row["function"], row["address"] - 4 * span), min(end, row["use"] + 4 * span), 4):
        i = scanner.insn(q)
        if i.kind in ("addiu", "ori") and i.rs == 0 and i.rt and not FIRST_CARD <= i.imm <= LAST_CARD:
            out.append(i.simm if i.kind == "addiu" else i.imm)
    return out[:6]


MATCH_CALLS = 3  # callees recorded on the matched path
MATCH_WINDOW = 16  # instructions walked on the matched path


def match_path(scanner, row):
    """Where the code goes when the compare of an eq reference *matches*: (start pc, delay insn or None), or
    None. beq/beql: the branch target (delay slot executed); bne: the fall-through after the delay slot;
    bnel: the fall-through without it. For xor/subu/xori the first branch on the result within 4
    instructions decides (beq/bne against zero)."""
    b = scanner.insn(row["use"])
    if b.op in (0, 0x0E):  # xor/subu (special) or xori: find the zero test of the result
        reg = b.writes
        for q in range(b.pc + 4, b.pc + 20, 4):
            j = scanner.insn(q)
            if j.op in (4, 5, 0x14, 0x15) and reg in (j.rs, j.rt) and 0 in (j.rs, j.rt):
                b = j
                break
            if j.writes == reg or j.is_branch or is_call(j):
                return None
        else:
            return None
        if b.op in (4, 0x14):  # beq result, zero: equal -> taken
            return b.target, scanner.insn(b.pc + 4)
        return b.pc + 8, (None if b.op == 0x15 else scanner.insn(b.pc + 4))
    if b.op in (4, 0x14):
        return b.target, scanner.insn(b.pc + 4)
    if b.op in (5, 0x15):
        return b.pc + 8, (None if b.op == 0x15 else scanner.insn(b.pc + 4))
    return None


def match_calls(scanner, start, delay, func):
    """Named callees on the straight line of the matched path (up to MATCH_CALLS): what the case does."""
    out, end = [], scanner.end(func)
    if delay is not None and is_call(delay):
        out.append(scanner._callee(delay))
    q, jumped = start, False
    for _ in range(MATCH_WINDOW):
        if not func <= q < end:
            break
        i = scanner.insn(q)
        if is_call(i):
            name = scanner._callee(i)
            if name not in out:
                out.append(name)
        elif i.kind == "jr":
            break
        elif i.op == 2 or (i.op == 4 and i.rs == i.rt == 0):
            if jumped:
                break
            q, jumped = i.target, True
            continue
        elif i.is_branch:
            break
        q += 4
    return out[:MATCH_CALLS]


def group_of(name):
    """Registry group from the name prefix (`duel_effects_...` -> duel_effects), or '' for a default name."""
    if not name or DEFAULT_NAME.match(name):
        return ""
    for group in ("duel_effects", "duel_core", "card_db", "tag_duel", "field_3d"):
        if name.startswith(group + "_"):
            return group
    return name.split("_", 1)[0]


def card_refs(prx_bytes, functions=None, names=None, base=BASE, module="rel_duel_eng", cards=None,
              semantics=None):
    """{card id: [reference dict]} for one module image.

    `functions`: function start addresses (re/functions.csv ids); the ones inside the module's .text are used,
    else heuristic entry points. `names`: address -> name. `cards`: optional set of ids to keep. Each dict
    has kind, detail, address, use, function, function_name, group, module, operand (eq/range/switch: where
    the compared value comes from), value (constant returned on the matched path of an eq compare or by a
    switch case, else None), calls (named callees on the matched path), constants (small immediates near the
    reference) and semantics (the engine_ref_semantics.csv rule for an eq/switch/arg reference, or None).
    `semantics`: a rule list from load_semantics(); None loads tools/engine_ref_semantics.csv; [] disables."""
    rules = load_semantics() if semantics is None else semantics
    image = ep.Module(prx_bytes, base)
    text = text_range(prx_bytes, base)
    scanner = Scanner(image, text, functions, names, module)
    out = collections.defaultdict(list)
    seen = set()
    for row in scanner.scan():
        cid = row["card_id"]
        if (cards is not None and cid not in cards) or (cid, row["kind"], row["address"]) in seen:
            continue
        seen.add((cid, row["kind"], row["address"]))
        value, calls = None, []
        if row["kind"] == "eq":
            path = match_path(scanner, row)
            if path:
                value = ep.evaluate(image, path[0], delay=path[1])
                calls = match_calls(scanner, path[0], path[1], row["function"])
        elif row["kind"] == "switch":
            value = ep.evaluate(image, row["case"])
            calls = match_calls(scanner, row["case"], None, row["function"])
        row["value"] = None if value is None else ep.signed(value)
        row["calls"] = calls
        row["constants"] = nearby_constants(scanner, row)
        row["group"] = group_of(row["function_name"])
        row["semantics"] = classify(row, rules) if row["kind"] in STRONG else None
        del row["case"]
        out[cid].append(row)
    return dict(sorted(out.items()))


def merge(*maps):
    out = collections.defaultdict(list)
    for m in maps:
        for cid, rows in m.items():
            out[cid].extend(rows)
    return dict(sorted(out.items()))


def strong_ids(refs):
    return {c for c, v in refs.items() if any(r["kind"] in STRONG for r in v)}


# ---------------------------------------------------------------------------------------------- semantics


SEMANTICS = HERE / "engine_ref_semantics.csv"
# Tags that locate a card without describing its effect: AI knowledge, archetype membership, name aliases,
# references made by another card's effect, and functions without a rule.
GENERIC_TAGS = {"ai_hint", "archetype", "name_alias", "named_reference", "unclassified"}
CONFIDENCE_ORDER = {"H": 0, "M": 1, "L": 2}
# How the helper that receives an `arg` id qualifies the rule of the calling function.
MODALITY = [
    ("duel_core_count_active_card*", "while it is active on the field"),
    ("duel_core_is_active_card_at", "while it is active on the field"),
    ("duel_core_count_active_timed_cards", "while it is active on the field"),
    ("duel_core_count_active_links_from", "while it is active on the field"),
    ("duel_core_slot_has_effect", "through an effect marker it leaves on a slot"),
    ("duel_core_has_marker_value", "through an effect marker it leaves on a slot"),
    ("duel_core_has_current_turn_effect", "for the turn it was applied"),
    ("duel_core_post_add*marker", "adds an effect marker"),
    ("duel_core_post_remove_marker", "removes an effect marker"),
    ("duel_core_attach_effect", "attaches an effect record"),
]


def load_semantics(path=SEMANTICS):
    """Rules of engine_ref_semantics.csv in file order (first match wins). Missing file: []."""
    path = Path(path)
    if not path.exists():
        return []
    rules = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pattern = row["pattern"].strip()
            rule = dict(row, pattern=pattern, lo=None, hi=None)
            m = re.fullmatch(r"0x([0-9a-fA-F]+)(?:-0x([0-9a-fA-F]+))?", pattern)
            if m:
                rule["lo"] = int(m.group(1), 16)
                rule["hi"] = int(m.group(2), 16) if m.group(2) else rule["lo"] + 1
            rule["values"] = parse_values(row.get("values", ""))
            rules.append(rule)
    return rules


def parse_values(text):
    """`1=label;none=label;*=label {value}` -> {key: label} (keys: int, 'none', '*')."""
    out = {}
    for part in filter(None, (p.strip() for p in (text or "").split(";"))):
        key, _, label = part.partition("=")
        key = key.strip()
        out[key if key in ("none", "*") else int(key, 0)] = label.strip()
    return out


def value_label(rule, value):
    v = rule["values"]
    if not rule.get("param"):
        return ""
    if value is None:
        return v.get("none", "")
    label = v.get(value, v.get("*", "{value}"))
    return label.replace("{value}", str(value))


def _rule_matches(rule, row):
    kinds = rule["kinds"] or "any"
    kind = "arg" if row["kind"] == "arg" else "cmp"
    if kinds != "any" and kinds != kind:
        return False
    if rule["callee"] and not (row["kind"] == "arg" and fnmatch.fnmatchcase(row["detail"], rule["callee"])):
        return False
    if rule["lo"] is not None:  # an exact address always applies; a range only to unnamed functions
        if rule["hi"] - rule["lo"] > 1 and not DEFAULT_NAME.match(row["function_name"]):
            return False
        return rule["lo"] <= row["function"] < rule["hi"]
    return fnmatch.fnmatchcase(row["function_name"], rule["pattern"])


def classify(row, rules):
    """Semantic rule for one eq/switch/arg reference: {tag, phrase, modality, confidence, param, value, label,
    rule}. `modality` qualifies an `arg` reference by the helper that receives the id (MODALITY). Unmatched
    references get the tag `unclassified`."""
    mod = ""
    if row["kind"] == "arg":
        mod = next((m for p, m in MODALITY if fnmatch.fnmatchcase(row["detail"], p)), "")
    for rule in rules:
        if _rule_matches(rule, row):
            return {"tag": rule["tag"], "phrase": rule["phrase"], "modality": "" if rule["callee"] else mod,
                    "confidence": rule["confidence"], "param": rule.get("param") or "", "value": row["value"],
                    "label": value_label(rule, row["value"]), "rule": rule["pattern"]}
    return {"tag": "unclassified", "phrase": "card-specific test in " + row["function_name"], "modality": mod,
            "confidence": "L", "param": "", "value": row["value"], "label": "", "rule": ""}


def describe(refs, card_id):
    """Semantic summary of one card: list of {tag, phrase, confidence, generic, functions, labels, modalities},
    one per (tag, phrase), descriptive tags first, then by confidence (the best of the merged references)."""
    by = {}
    for r in refs.get(card_id, ()):
        s = r.get("semantics")
        if not s:
            continue
        e = by.setdefault((s["tag"], s["phrase"]), {
            "tag": s["tag"], "phrase": s["phrase"], "confidence": s["confidence"],
            "generic": s["tag"] in GENERIC_TAGS, "functions": [], "labels": [], "modalities": []})
        if CONFIDENCE_ORDER.get(s["confidence"], 3) < CONFIDENCE_ORDER.get(e["confidence"], 3):
            e["confidence"] = s["confidence"]
        if r["function_name"] not in e["functions"]:
            e["functions"].append(r["function_name"])
        if s["label"] and f"{s['param']}: {s['label']}" not in e["labels"]:
            e["labels"].append(f"{s['param']}: {s['label']}")
        if s.get("modality") and s["modality"] not in e["modalities"]:
            e["modalities"].append(s["modality"])
    return sorted(by.values(), key=lambda e: (e["generic"], CONFIDENCE_ORDER.get(e["confidence"], 3), e["tag"]))


def coverage(refs, ids):
    """(cards with a descriptive tag, Counter of descriptive tags per card, ids without one)."""
    tags, lacking, covered = collections.Counter(), [], 0
    for cid in sorted(ids):
        own = {e["tag"] for e in describe(refs, cid) if not e["generic"]}
        if own:
            covered += 1
            tags.update(own)
        else:
            lacking.append(cid)
    return covered, tags, lacking


# ---------------------------------------------------------------------------------------------- registry


def load_registry(path):
    """(function start addresses, address -> name) from re/functions.csv (bare hex ids only)."""
    names = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["id"].startswith("0x"):
                names[int(row["id"], 16)] = row["name"]
    return sorted(names), names


def load_cards(path):
    """card id -> (English name, kind) through tools/cardinfo.py."""
    ci = _load("re_cardinfo", "cardinfo.py")
    info = ci.CardInfo(Path(path).read_bytes(), "E")
    out = {}
    for i in range(1, info.count):
        p = info.properties(i)
        out[p["id"]] = (info.name(i), p["kind"])
    return out


# ---------------------------------------------------------------------------------------------- check


ID_OPERANDS = ("u16 load", "masked id", "result of ", "argument")


NO_TEXT_KINDS = {1, 5, 9, 21, 31, 35}  # normal, plain fusion/ritual/synchro, token, normal tuner


def check(refs, cards=None, tabled=None, known=True, subject=None, rules=None):
    """(problems, summary lines). `cards`: id -> (name, kind); `tabled`: ids with an effect-table record or
    a list entry (the effect cards outside it are the ones the tables do not explain); `known`: measure the
    recall on the documented tests of KNOWN (the full rel_duel_eng module). `subject`: ids whose semantic
    coverage is reported (the engine_only cards of card_effects.py; default: the effect cards outside the
    tables that have an eq/switch/arg reference). `rules`: the semantic rules to validate."""
    problems, lines = [], []
    problems += [f"semantics: {p}" for p in rule_problems(load_semantics() if rules is None else rules)]
    rows = [r for v in refs.values() for r in v]
    kinds = collections.Counter(r["kind"] for r in rows)
    funcs = {(r["module"], r["function"]) for r in rows}
    lines.append(f"references: {len(rows)} to {len(refs)} ids in {len(funcs)} functions ("
                 + ", ".join(f"{k} {kinds[k]}" for k in KINDS if kinds[k]) + ")")
    per_module = collections.Counter(r["module"] for r in rows)
    lines.append("per module: " + ", ".join(f"{k} {v}" for k, v in sorted(per_module.items())))
    lines.append(f"ids with an eq/switch/arg reference: {len(strong_ids(refs))}")
    eq = [r for r in rows if r["kind"] == "eq"]
    if eq:
        idlike = sum(1 for r in eq if r["operand"].startswith(ID_OPERANDS))
        lines.append(f"eq operands from a u16 load, the 0x3fff id mask, a call result or an argument: "
                     f"{idlike} of {len(eq)} ({100 * idlike / len(eq):.1f} %)")
    if known:
        lost = [(c, f, k) for c, f, k in KNOWN
                if not any(r["function"] == f and r["kind"] == k for r in refs.get(c, ()))]
        lines.append(f"recall on documented tests: {len(KNOWN) - len(lost)} of {len(KNOWN)}")
        problems += [f"documented {k} test of {c:#06x} in {f:#010x} not found" for c, f, k in lost]
    if cards is not None:
        released = set(refs) & set(cards)
        lines.append(f"released cards referenced: {len(released)} of {len(cards)}; other ids: "
                     f"{len(set(refs) - released)}")
        vanilla = sorted(c for c in released if cards[c][1] in (1, 21))
        round_ids = sorted(c for c in refs if c % 100 == 0 and c not in cards)
        lines.append(f"precision proxies: {len(vanilla)} normal/token cards referenced; ids that are multiples "
                     f"of 100 and no card: {' '.join(f'{c:#x}' for c in round_ids) or 'none'}")
        if refs and len(released) < len(refs) / 2:
            problems.append("fewer than half of the referenced ids are released cards")
        if tabled is not None:
            untabled = {c for c, (_, kind) in cards.items() if kind not in NO_TEXT_KINDS and c not in tabled}
            found = untabled & strong_ids(refs)
            rest = collections.Counter(cards[c][1] for c in untabled - found)
            lines.append(f"effect cards without an effect-table record or list entry: {len(untabled)}; with an "
                         f"eq/switch/arg reference: {len(found)}; without: {len(untabled) - len(found)}"
                         + (" (kinds " + ", ".join(f"{k} {n}" for k, n in sorted(rest.items())) + ")" if rest else ""))
            if subject is None:
                subject = found
    if subject:
        lines += semantic_lines(refs, subject)
    return problems, lines


def rule_problems(rules):
    out = []
    for r in rules:
        if r["kinds"] not in ("any", "cmp", "arg"):
            out.append(f"{r['pattern']}: kinds {r['kinds']!r} is not any/cmp/arg")
        if r["confidence"] not in CONFIDENCE_ORDER:
            out.append(f"{r['pattern']}: confidence {r['confidence']!r} is not H/M/L")
        if not r["tag"] or not r["phrase"]:
            out.append(f"{r['pattern']}: empty tag or phrase")
    return out


def semantic_lines(refs, subject):
    """Coverage of the semantic rules over `subject` (card ids)."""
    covered, tags, lacking = coverage(refs, subject)
    n = len(subject)
    lines = [f"semantics: {covered} of {n} cards ({100 * covered / n:.1f} %) have a descriptive tag; "
             f"{len(lacking)} have only generic tags ({', '.join(sorted(GENERIC_TAGS))}) or none"]
    lines.append("semantic tags (cards): " + ", ".join(f"{t} {k}" for t, k in tags.most_common()))
    conf = collections.Counter()
    for cid in subject:
        best = [e for e in describe(refs, cid) if not e["generic"]]
        if best:
            conf[best[0]["confidence"]] += 1
    lines.append("best descriptive confidence per card: " + ", ".join(f"{c} {conf[c]}" for c in "HML"))
    generic = collections.Counter(e["tag"] for cid in lacking for e in describe(refs, cid))
    lines.append("generic tags of the cards without a descriptive one: "
                 + (", ".join(f"{t} {k}" for t, k in generic.most_common()) or "none"))
    return lines


# ---------------------------------------------------------------------------------------------- main


FIELDS = ["card_id", "name", "kind", "detail", "module", "address", "use", "function", "function_name", "group",
          "operand", "value", "calls", "constants", "tag", "phrase", "confidence", "parameter"]
DESCRIBE_FIELDS = ["card_id", "name", "descriptive", "tags", "description"]


def rows_of(refs, cards=None):
    for cid, v in refs.items():
        for r in v:
            yield {"card_id": f"{cid:#06x}", "name": (cards or {}).get(cid, ("",))[0], "kind": r["kind"],
                   "detail": r["detail"], "module": r["module"], "address": f"{r['address']:#010x}",
                   "use": f"{r['use']:#010x}", "function": f"{r['function']:#010x}",
                   "function_name": r["function_name"], "group": r["group"], "operand": r["operand"],
                   "value": "" if r["value"] is None else r["value"], "calls": " ".join(r.get("calls", ())),
                   "constants": " ".join(str(c) for c in r["constants"]),
                   **semantic_cells(r.get("semantics"))}


def semantic_cells(s):
    if not s:
        return {"tag": "", "phrase": "", "confidence": "", "parameter": ""}
    phrase = s["phrase"] + (f" ({s['modality']})" if s.get("modality") else "")
    return {"tag": s["tag"], "phrase": phrase, "confidence": s["confidence"],
            "parameter": f"{s['param']}: {s['label']}" if s["label"] else ""}


def entry_text(e):
    """`phrase (modality) [param: label] (confidence)` for one describe() entry."""
    out = e["phrase"]
    if e["modalities"]:
        out += f" ({'; '.join(e['modalities'])})"
    if e["labels"]:
        out += f" [{', '.join(e['labels'])}]"
    return out + f" ({e['confidence']})"


def describe_rows(refs, ids, cards=None):
    """One row per card: its tags and a one-line description built from the template phrases."""
    for cid in sorted(ids):
        entries = describe(refs, cid)
        text = "; ".join(entry_text(e) for e in entries if not e["generic"])
        generic = sorted({e["tag"] for e in entries if e["generic"]})
        if generic:
            text += ("; " if text else "") + "generic: " + " ".join(generic)
        yield {"card_id": f"{cid:#06x}", "name": (cards or {}).get(cid, ("",))[0],
               "descriptive": int(any(not e["generic"] for e in entries)),
               "tags": " ".join(dict.fromkeys(e["tag"] for e in entries)), "description": text}


def function_rows(refs):
    by = collections.defaultdict(lambda: {"ids": set(), "kinds": collections.Counter()})
    for cid, v in refs.items():
        for r in v:
            f = by[(r["module"], r["function"], r["function_name"], r["group"])]
            f["ids"].add(cid)
            f["kinds"][r["kind"]] += 1
    for (module, func, name, group), f in sorted(by.items()):
        yield {"module": module, "function": f"{func:#010x}", "function_name": name, "group": group,
               "ids": len(f["ids"]), "kinds": " ".join(f"{k}x{n}" for k, n in sorted(f["kinds"].items()))}


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def all_refs(prx_bytes, functions=None, names=None, boot=None, draw=None, semantics=None):
    """References of rel_duel_eng plus, when their bytes are given, BOOT.BIN and rel_duel_draw."""
    rules = load_semantics() if semantics is None else semantics
    maps = [card_refs(prx_bytes, functions, names, semantics=rules)]
    if boot is not None:
        maps.append(card_refs(boot, functions, names, MODULES["BOOT.BIN"], "BOOT.BIN", semantics=rules))
    if draw is not None:
        maps.append(card_refs(draw, functions, names, MODULES["rel_duel_draw"], "rel_duel_draw", semantics=rules))
    return merge(*maps)


def load_spec_ids(path, status="engine_only"):
    """Card ids with spec_status `status` in card_effects.csv (output of tools/card_effects.py)."""
    with open(path, newline="", encoding="utf-8") as f:
        return {int(r["card_id"], 16) for r in csv.DictReader(f) if r["spec_status"] == status}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Find card ids tested directly in the game's code.")
    parser.add_argument("prx", type=Path, help="gmodule/rel_duel_eng.prx")
    parser.add_argument("command", nargs="?", choices=["list", "describe"],
                        help="list: write the CSV files; describe: print the semantic tags per card")
    parser.add_argument("-o", "--out", type=Path, help="output directory (under extracted/)")
    parser.add_argument("--check", action="store_true", help="structural checks and summary")
    parser.add_argument("--cardinfo", type=Path, help="duelsys/cardinfo_eng.ehp: names, kinds, precision proxies")
    parser.add_argument("--boot", type=Path, help="SYSDIR/BOOT.BIN: scan it too (base 0x08804000)")
    parser.add_argument("--draw", type=Path, help="gmodule/rel_duel_draw.prx: scan it too (base 0x0983fb00)")
    parser.add_argument("--functions", type=Path, default=HERE.parent / "re" / "functions.csv")
    parser.add_argument("--semantics", type=Path, default=SEMANTICS, help="engine_ref_semantics.csv")
    parser.add_argument("--spec", type=Path, help="card_effects.csv of tools/card_effects.py: its engine_only "
                                                  "cards are the subject of the semantic coverage and of describe")
    parser.add_argument("--card", action="append", default=[], help="describe: card id (repeatable)")
    args = parser.parse_args(argv)
    if not args.check and args.command not in ("list", "describe"):
        parser.error("give `list -o DIR`, `describe` or --check")
    if args.command == "list" and not args.out:
        parser.error("list needs -o/--out")
    starts, names = load_registry(args.functions) if args.functions and args.functions.exists() else (None, {})
    rules = load_semantics(args.semantics)
    refs = all_refs(args.prx.read_bytes(), starts, names, args.boot.read_bytes() if args.boot else None,
                    args.draw.read_bytes() if args.draw else None, rules)
    subject = load_spec_ids(args.spec) if args.spec else None
    cards = load_cards(args.cardinfo) if args.cardinfo else None
    module = ep.Module(args.prx.read_bytes())
    known = text_range(module.data, BASE)[1] > max(f for _, f, _ in KNOWN)  # the full module, not a test image
    tabled = None
    if known:
        tabled = {c for _, _, c, _ in ep.table_records(module)} | {c for _, _, c, _ in ep.list_records(module)}
    if args.command == "describe":
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(errors="replace")
        ids = [int(c, 0) for c in args.card] or sorted(subject if subject is not None else strong_ids(refs))
        for row in describe_rows(refs, ids, cards):
            print(f"{row['card_id']} {row['name']}: {row['description'] or '-'}")
        if args.out:
            args.out.mkdir(parents=True, exist_ok=True)
            write_csv(args.out / "card_semantics.csv", describe_rows(refs, ids, cards), DESCRIBE_FIELDS)
            print(f"wrote {args.out}")
        if not args.check:
            return 0
    problems, lines = check(refs, cards, tabled, known, subject, rules)
    for p in problems:
        print("problem:", p, file=sys.stderr)
    for line in lines:
        print(line)
    if args.command == "list":
        args.out.mkdir(parents=True, exist_ok=True)
        write_csv(args.out / "card_refs.csv", rows_of(refs, cards), FIELDS)
        write_csv(args.out / "card_ref_functions.csv", function_rows(refs),
                  ["module", "function", "function_name", "group", "ids", "kinds"])
        print(f"wrote {args.out}")
    if args.check:
        print("ok" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
