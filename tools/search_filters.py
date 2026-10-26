#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Recover the search filters of the candidate builders of gmodule/rel_duel_eng.prx.

See docs/formats/search-filters.md. The 8-byte list at 0x09dec554 (686 records `(card id, builder)`, sorted by
id) maps a card to the builder that fills the candidate list 0x09e29928 (docs/subsystems/effect-helpers-deck.md).
Most builders call one location scanner per location (Deck, Extra Deck, hand, Graveyard, banished) with a
predicate, a predicate argument, a filter word and an options word. For every record this tool runs the builder
symbolically with the card id in a1 (path-sensitive known-bits dataflow, a1 = the record's card id, stack slots
tracked, shared sub-builders followed), records every scanner call with its arguments and decodes the filter and
options words. Values computed at run time are reported with the call they come from; Type, Attribute and Level
getters called on the card itself are resolved through cardinfo when --cardinfo is given.

  search_filters.py <USRDIR>/gmodule/rel_duel_eng.prx list -o extracted/search_filters/search_filters.csv
                    [--cardinfo <USRDIR>/duelsys/cardinfo_eng.ehp] [--boot <SYSDIR>/BOOT.BIN]
                    [--functions re/functions.csv]
  search_filters.py <USRDIR>/gmodule/rel_duel_eng.prx --check [--cardinfo ...] [--boot ...]

The CSV is game data (per-card parameters): keep it under extracted/, never in git. Addresses are runtime
addresses with the module at 0x09be1400; BOOT.BIN addresses with BOOT.BIN at 0x08804000.
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

BASE, TEXT_END, FULL = ep.BASE, ep.TEXT_END, ec.FULL
BUILDER_LIST = next(entry for entry in ep.LISTS if entry[0] == "L1")  # ("L1", 0x09dec554, 686)
BUILD_DISPATCH = 0x09CDC85C  # duel_effects_build_candidate_list
ADD_CANDIDATE = 0x09CDC7D0  # duel_effects_add_candidate(side, location, index)
QUERY_POINTER = 0x09E29924
ARCHETYPE_PREDICATE = 0x09CD02B0  # duel_effects_candidate_in_archetype: BOOT 0x088633f8(id, *arg)
NAME_PREDICATE = 0x09CD0030  # candidate has the name *arg (BOOT 0x0885fb5c; Graveyard: 0x09bf0ce4)
ARCHETYPE_DISPATCH = 0x088633F8  # BOOT: if id < 0x3f call table[id](card)
ARCHETYPE_TABLE, ARCHETYPE_COUNT = 0x0889E2D8, 0x3F

A0, A1, A2, A3, T0, T1, T2, V0, SP, RA = 4, 5, 6, 7, 8, 9, 10, 2, 29, 31
LOCATIONS = {0x0B: "hand", 0x0C: "extra", 0x0D: "deck", 0x0E: "graveyard", 0x0F: "banished"}

# address -> (location, register of the predicate, of its argument, of the filter word, of the options word)
SCANNERS = {
    0x09CCECBC: ("deck", A2, A3, T0, T1),       # duel_effects_collect_deck_candidates
    0x09CCF134: ("extra", A2, A3, T0, T1),      # duel_effects_collect_extra_deck_candidates
    0x09CCF428: ("hand", A3, T0, T1, T2),       # duel_effects_test_hand_candidate (a2 = hand index)
    0x09CCF768: ("graveyard", A2, A3, T0, T1),  # duel_effects_collect_graveyard_candidates
    0x09CCFCDC: ("banished", A2, A3, T0, T1),   # duel_effects_collect_banished_candidates
}
# Options bits that make the scanner add the monster bit 2 to the filter (code of each scanner).
MONSTER_OPTIONS = {"deck": 0x18, "extra": 0x0F, "hand": 0x06, "graveyard": 0x3CB8, "banished": 0x08}

# Getters on the card itself that cardinfo can answer: registry name -> cardinfo property.
GETTERS = {"card_db_get_race": "race", "card_db_get_attribute": "attribute", "card_db_get_level": "level"}

ATTRIBUTES = {1: "LIGHT", 2: "DARK", 3: "WATER", 4: "FIRE", 5: "EARTH", 6: "WIND", 7: "DIVINE"}
RACES = {1: "Dragon", 2: "Zombie", 3: "Fiend", 4: "Pyro", 5: "Sea Serpent", 6: "Rock", 7: "Machine", 8: "Fish",
         9: "Dinosaur", 10: "Insect", 11: "Beast", 12: "Beast-Warrior", 13: "Plant", 14: "Aqua", 15: "Warrior",
         16: "Winged Beast", 17: "Fairy", 18: "Spellcaster", 19: "Thunder", 20: "Reptile", 21: "Psychic",
         22: "Divine-Beast"}
ICONS = {0: "normal", 1: "counter", 2: "field", 3: "equip", 4: "continuous", 5: "quick-play", 6: "ritual"}

# ---------------------------------------------------------------------------------------------- filter word
# Bits tested by duel_effects_candidate_matches_filter (0x09cce9a8) and by the scanners themselves.
FILTER_FLAGS = [
    (0x1, "count_only"),            # scanner: count, do not add
    (0x10, "same_name"),            # scanner: BOOT 0x0885fb5c(candidate, card id) must hold
    (0x20, "different_name"),       # scanner: ... must not hold
    (0x400, "normal_monster"),      # BOOT 0x0885ff84 (kind 1 or 31); hand: 0x09c02f80
    (0x800, "summonable"),          # duel_core_can_special_summon_card(side, id, location)
    (0x1000, "summon_conditions"),  # 0x09c0c8a0(side, id, location)
    (0x2000, "atk_max_1500"),       # ATK < 0x5dd
    (0x4000, "flip"),               # BOOT 0x08863438 (genre 0x16)
    (0x8000, "tuner"),              # BOOT 0x088601c0 (kind 31 or 33)
    (0x10000, "targetable"),        # 0x09c02b48(side, id): no opposing Metalsilver Armor; 0x08862688 list guard
]
KIND_BITS = [(0x2, "monster"), (0x4, "spell"), (0x8, "trap")]
ICON_MASK, LEVEL_MASK, LEVEL_GE, LEVEL_LE = 0x380, 0x3C0000, 0x400000, 0x800000
ATTRIBUTE_MASK, RACE_MASK = 0x7000000, 0xF8000000
MONSTER_FIELDS = 0xFF3CFC00  # any of these makes the scanners add the monster bit
FILTER_KNOWN = 0x3F | ICON_MASK | 0x1FC00 | LEVEL_MASK | LEVEL_GE | LEVEL_LE | ATTRIBUTE_MASK | RACE_MASK

# Options word, per scanner (decompiled code of each scanner).
OPTION_FLAGS = {
    "deck": [(0x1, "opponent"), (0x2, "skip_parasite_paracide"), (0x4, "can_add_to_hand"),
             (0x8, "special_summon_test"), (0x10, "special_summon_test_b"), (0x20, "effect_monster"),
             (0x40, "first_match")],
    "extra": [(0x1, "fusion"), (0x2, "synchro"), (0x4, "extra_summon_test"), (0x8, "fusion_materials"),
              (0x10, "synchro_materials")],
    "hand": [(0x1, "sendable_to_graveyard"), (0x2, "special_summon_test"), (0x4, "special_summon_test_b")],
    "graveyard": [(0x1, "opponent"), (0x4, "necrovalley_check"), (0x8, "can_special_summon"),
                  (0x10, "special_summon_list_card"), (0x20, "special_summon_list_card_2"),
                  (0x40, "entry_flag5_clear"), (0x80, "entry_flag2_set"), (0x100, "entry_flag3_set"),
                  (0x200, "entry_flag4_set"), (0x400, "properly_summoned"), (0x800, "treated_as_normal"),
                  (0x1000, "effect_not_treated_as_normal"), (0x2000, "effect_only_if_treated_as_normal"),
                  (0x4000, "can_banish_from_graveyard")],
    "banished": [(0x1, "opponent"), (0x4, "face_up"), (0x8, "can_special_summon")],
}
TOP_N_SHIFT = 25  # deck: options >> 25 limits the scan to the top n cards


def _known(v, mask):
    """True when every bit of `mask` is known in the known-bits pair v."""
    return v is not None and v[0] & mask == mask


def decode_filter(kb, origins=(), location="", options=None):
    """Readable fields of a filter word given as known bits (mask, value). Unknown fields are reported as
    computed, with the calls their value comes from."""
    mask, value = kb if kb else (0, 0)
    out = []
    computed = "computed" + (f"({'+'.join(sorted(origins))})" if origins else "")

    def field(bits):
        return (value & bits) if mask & bits == bits else None

    eff = value
    kinds = field(0xE)
    if kinds is not None and field(0x2) == 0 and mask & MONSTER_FIELDS == MONSTER_FIELDS:
        opts = options[1] if options and options[0] == FULL else 0
        if value & MONSTER_FIELDS or opts & MONSTER_OPTIONS.get(location, 0):
            eff |= 0x2
    if kinds is None:
        out.append(f"kind={computed}")
    else:
        if eff & 0xE == 0:
            eff |= 0xE
        names = [n for b, n in KIND_BITS if eff & b]
        out.append("kind=" + ("any" if eff & 0xE == 0xE else "/".join(names)))
    icon = field(ICON_MASK)
    if icon is None:
        out.append(f"icon={computed}")
    elif icon:
        out.append(f"icon={ICONS.get((icon >> 7) - 1, (icon >> 7) - 1)}")
    for bit, name in FILTER_FLAGS:
        b = field(bit)
        if b is None:
            out.append(f"{name}={computed}")
        elif b:
            out.append(name)
    level = field(LEVEL_MASK)
    if level is None or field(LEVEL_GE | LEVEL_LE) is None:
        out.append(f"level={computed}")
    elif level:
        op = ">=" if value & LEVEL_GE else "<=" if value & LEVEL_LE else "="
        out.append(f"level{op}{level >> 18}")
    elif value & (LEVEL_GE | LEVEL_LE):
        out.append(f"level_bits={value & (LEVEL_GE | LEVEL_LE):#x}")
    attribute = field(ATTRIBUTE_MASK)
    if attribute is None:
        out.append(f"attribute={computed}")
    elif attribute:
        out.append(f"attribute={ATTRIBUTES.get(attribute >> 24, attribute >> 24)}")
    race = field(RACE_MASK)
    if race is None:
        out.append(f"type={computed}")
    elif race:
        out.append(f"type={RACES.get(race >> 27, race >> 27)}")
    unknown = value & mask & ~FILTER_KNOWN & FULL
    if unknown:
        out.append(f"unknown_bits={unknown:#x}")
    return out


def decode_options(kb, location, origins=()):
    mask, value = kb if kb else (0, 0)
    flags = OPTION_FLAGS.get(location, [])
    if mask != FULL:
        computed = "computed" + (f"({'+'.join(sorted(origins))})" if origins else "")
        out = [n for b, n in flags if mask & b and value & b]
        return out + [f"options={computed}"]
    out = [n for b, n in flags if value & b]
    known = sum(b for b, _ in flags)
    if location == "deck":
        if value >> TOP_N_SHIFT:
            out.append(f"top={value >> TOP_N_SHIFT}")
        known |= FULL ^ ((1 << TOP_N_SHIFT) - 1)
    rest = value & ~known & FULL
    if rest:
        out.append(f"unknown_options={rest:#x}")
    return out


# ---------------------------------------------------------------------------------------------- simulator
# A value is (known bits or None, stack offset or None, origins). Known bits as in effect_classify.py.

UNKNOWN = (None, None, frozenset())


def _kb(v):
    return v[0]


def _const(x):
    return ((FULL, x & FULL), None, frozenset())


Call = collections.namedtuple("Call", "site location pred pred_arg filter options index")


class Simulator:
    """Path-sensitive execution of one builder with a known card id."""

    def __init__(self, module, registry, cards=None, max_paths=512, max_steps=60000, max_depth=3, max_visits=24):
        self.module, self.registry, self.cards = module, registry, cards or {}
        self.max_paths, self.max_steps, self.max_depth = max_paths, max_steps, max_depth
        self.max_visits = max_visits
        self.starts = set(registry.starts)
        self._reach = {}

    def word(self, pc):
        return self.module.word(pc) if BASE <= pc < TEXT_END else 0

    def reaches_scanner(self, address, depth=3):
        """True when the static call graph from `address` reaches a scanner or add_candidate within `depth`."""
        key = (address, depth)
        if key in self._reach:
            return self._reach[key]
        self._reach[key] = False
        hit = False
        if BASE <= address < TEXT_END:
            for call in ec.scan_function(self.module, address, self.registry.end(address)):
                t = call.target
                if t in SCANNERS or t == ADD_CANDIDATE:
                    hit = True
                    break
                if depth > 1 and t is not None and BASE <= t < TEXT_END and t != address and \
                        self.reaches_scanner(t, depth - 1):
                    hit = True
                    break
        self._reach[key] = hit
        return hit

    # -- value helpers
    def _getter_value(self, name, a0):
        prop = GETTERS.get(name)
        if not prop or not self.cards or not _known(_kb(a0), FULL):
            return None
        card = self.cards.get(_kb(a0)[1] & 0x3FFF)
        return None if card is None else card.get(prop)

    def _alu(self, regs, w):
        op, rs, rt, fn = w >> 26, w >> 21 & 31, w >> 16 & 31, w & 63
        dst = ec.written(w)
        if not dst:
            return
        imm = w & 0xFFFF
        simm = imm - 0x10000 if imm & 0x8000 else imm
        s, t = regs.get(rs, UNKNOWN) if rs else _const(0), regs.get(rt, UNKNOWN) if rt else _const(0)
        if op in (8, 9) and s[1] is not None:
            regs[dst] = (None, s[1] + simm, s[2])
            return
        if op == 0 and fn in (0x21, 0x25, 0x20) and (s[1] is not None or t[1] is not None):
            if s[1] is not None and _known(_kb(t), FULL) and _kb(t)[1] == 0:
                regs[dst] = s
                return
            if t[1] is not None and _known(_kb(s), FULL) and _kb(s)[1] == 0:
                regs[dst] = t
                return
        kb = {r: v[0] for r, v in regs.items() if v[0] is not None}
        ec.apply(kb, w)
        origins = frozenset()
        if op == 0 and fn not in (0, 2, 3):
            origins = s[2] | t[2]
        elif op == 0:
            origins = t[2]
        elif op not in (0x0F,):
            origins = s[2]
        new = kb.get(dst)
        regs[dst] = (new if new and new[0] else None, None, origins if not (new and new[0] == FULL) else frozenset())

    # -- main loop
    def run(self, start, card_id, a2=None):
        """Scanner calls (list of Call) and add_candidate locations reached from builder `start`, and the
        number of paths cut by the limits."""
        regs = {A0: (None, None, frozenset({"side"})), A1: _const(card_id), SP: (None, 0, frozenset()),
                A2: a2 if a2 is not None else (None, None, frozenset({"arg2"})), A3: (None, None, frozenset({"arg3"}))}
        work = [(start, regs, {}, ())]
        calls, adds, seen, visits, first = {}, set(), set(), collections.Counter(), {}
        widened = 0
        paths = steps = cut = 0
        while work:
            pc, regs, stack, frames = work.pop()
            paths += 1
            if paths > self.max_paths:
                cut += 1 + len(work)
                break
            while True:
                steps += 1
                if steps > self.max_steps:
                    cut += 1
                    work = []
                    break
                visits[pc] += 1
                if visits[pc] == 1:
                    first[pc] = (dict(regs), dict(stack))
                elif visits[pc] > self.max_visits:  # loops: widen what changed since the first visit
                    r0, s0 = first[pc]
                    regs = {r: v if r0.get(r) == v else (None, None, v[2]) for r, v in regs.items()}
                    stack = {k: v if s0.get(k) == v else (None, None, v[2]) for k, v in stack.items()}
                    widened += 1
                key = hash((pc, frames, tuple(sorted((r, v[0], v[1]) for r, v in regs.items())),
                            tuple(sorted((k, v[0], v[1]) for k, v in stack.items()))))
                if key in seen:
                    break
                seen.add(key)
                w = self.word(pc)
                op, rs, rt, fn = w >> 26, w >> 21 & 31, w >> 16 & 31, w & 63
                imm = w & 0xFFFF
                simm = imm - 0x10000 if imm & 0x8000 else imm
                if ec._is_branch(op, rt):
                    target = pc + 4 + 4 * simm
                    likely = op in (0x14, 0x15, 0x16, 0x17) or (op == 1 and rt in (2, 3, 0x12, 0x13))
                    if op == 1 and rt >= 0x10:  # bltzal / bgezal (bal): treat as a call when always taken
                        regs2, stack2 = dict(regs), dict(stack)
                        self._exec(regs2, stack2, self.word(pc + 4))
                        res = self._call(target, pc, regs2, stack2, frames, calls, adds)
                        if res is None:
                            break
                        pc, regs, stack, frames = res
                        continue
                    taken = self._decide(op, rs, rt, regs)
                    after_r, after_s = dict(regs), dict(stack)
                    self._exec(after_r, after_s, self.word(pc + 4))
                    if taken is None:
                        if len(work) < self.max_paths:
                            work.append((target, dict(after_r), dict(after_s), frames))
                        else:
                            cut += 1
                        if likely:
                            pc += 8
                        else:
                            pc, regs, stack = pc + 8, after_r, dict(after_s)
                        continue
                    if taken:
                        pc, regs, stack = target, after_r, after_s
                    elif likely:
                        pc += 8
                    else:
                        pc, regs, stack = pc + 8, after_r, after_s
                    continue
                if op in (2, 3) or (op == 0 and fn in (8, 9)):
                    self._exec(regs, stack, self.word(pc + 4))
                    if op == 0 and fn == 8:  # jr
                        if rs == RA and frames:
                            pc, frames = frames[-1], frames[:-1]
                            continue
                        break  # return from the builder, or a computed jump (not followed)
                    if op == 0 and fn == 9:  # jalr: opaque
                        self._clobber(regs, "indirect")
                        pc += 8
                        continue
                    target = BASE + ((w & 0x3FFFFFF) << 2)
                    if op == 2 and target not in self.starts and target not in SCANNERS:
                        pc = target  # jump inside the function
                        continue
                    res = self._call(target, pc, regs, stack, frames, calls, adds, tail=op == 2)
                    if res is None:
                        break
                    pc, regs, stack, frames = res
                    continue
                self._exec(regs, stack, w)
                pc += 4
        return list(calls.values()), adds, cut

    def _decide(self, op, rs, rt, regs):
        s = regs.get(rs, UNKNOWN)[0] if rs else (FULL, 0)
        t = regs.get(rt, UNKNOWN)[0] if rt else (FULL, 0)
        if op in (4, 5, 0x14, 0x15):
            if rs == rt:
                eq = True
            elif s is None or t is None:
                return None
            elif s[0] & t[0] & (s[1] ^ t[1]):
                eq = False
            elif s[0] == FULL and t[0] == FULL:
                eq = s[1] == t[1]
            else:
                return None
            return eq if op in (4, 0x14) else not eq
        if s is None:
            return None
        if s[0] >> 31 and s[1] >> 31:
            negative, zero = True, False
        elif s[0] == FULL:
            negative, zero = False, s[1] == 0
        elif s[0] >> 31 and s[0] & s[1]:
            negative, zero = False, False
        else:
            return None
        if op in (6, 0x16):
            return negative or zero
        if op in (7, 0x17):
            return not (negative or zero)
        if op == 1:
            return negative if rt in (0, 2) else not negative
        return None

    def _exec(self, regs, stack, w):
        op, rs, rt = w >> 26, w >> 21 & 31, w >> 16 & 31
        imm = w & 0xFFFF
        simm = imm - 0x10000 if imm & 0x8000 else imm
        if op in (0x28, 0x29, 0x2B):  # sb sh sw
            base = regs.get(rs, UNKNOWN)
            if base[1] is not None:
                v = regs.get(rt, UNKNOWN) if rt else _const(0)
                if op != 0x2B:
                    size = 1 if op == 0x28 else 2
                    m = (1 << 8 * size) - 1
                    v = ((v[0][0] & m | (FULL ^ m), v[0][1] & m) if v[0] else None, None, v[2])
                stack[base[1] + simm] = v
            return
        if 0x20 <= op <= 0x26:  # loads
            base = regs.get(rs, UNKNOWN)
            if not rt:
                return
            if base[1] is not None:
                v = stack.get(base[1] + simm)
                if v is None or op not in (0x23, 0x24, 0x25):
                    regs[rt] = (None, None, frozenset({"stack"}))
                elif op == 0x23:
                    regs[rt] = v
                else:
                    m = 0xFF if op == 0x24 else 0xFFFF
                    regs[rt] = ((v[0][0] | (FULL ^ m), v[0][1] & m) if v[0] else ((FULL ^ m), 0), None, v[2])
                return
            if base[0] and base[0][0] == FULL:
                regs[rt] = (None, None, frozenset({f"mem[{(BASE + base[0][1] + simm) & FULL:#010x}]"}))
            else:
                regs[rt] = (None, None, frozenset({"mem"}))
            return
        self._alu(regs, w)

    def _clobber(self, regs, origin, result=None):
        for r in ec.CLOBBERED:
            regs.pop(r, None)
        regs[V0] = result if result is not None else (None, None, frozenset({origin}))

    def _call(self, target, site, regs, stack, frames, calls, adds, tail=False):
        """Effect of a call (or tail jump) at `site`. Returns the next (pc, regs, stack, frames) or None when the
        path ends."""
        def ret(new_regs):
            if tail:
                if not frames:
                    return None
                return frames[-1], new_regs, stack, frames[:-1]
            return site + 8, new_regs, stack, frames

        if target in SCANNERS:
            loc, pr, pa, fr, orr = SCANNERS[target]
            pred = regs.get(pr, UNKNOWN)
            pred_addr = BASE + pred[0][1] if _known(pred[0], FULL) and pred[0][1] else None
            if pred_addr is None and _known(pred[0], FULL):
                pred_addr = 0
            arg = regs.get(pa, UNKNOWN)
            if arg[1] is not None:
                arg = stack.get(arg[1], UNKNOWN)
            index = regs.get(A2, UNKNOWN) if loc == "hand" else None
            call = Call(site, loc, pred_addr, arg, regs.get(fr, UNKNOWN), regs.get(orr, UNKNOWN), index)
            calls.setdefault(_call_key(call), call)
            new = dict(regs)
            self._clobber(new, "scan")
            return ret(new)
        if target == ADD_CANDIDATE:
            loc = regs.get(A1, UNKNOWN)[0]
            adds.add(_location_name(loc[1]) if _known(loc, FULL) else "computed")
            new = dict(regs)
            self._clobber(new, "add")
            return ret(new)
        if BASE <= target < TEXT_END and len(frames) < self.max_depth and self.reaches_scanner(target):
            if tail:
                return target, regs, stack, frames
            return target, regs, stack, frames + (site + 8,)
        name = self.registry.name(target)
        new = dict(regs)
        value = self._getter_value(name, regs.get(A0, UNKNOWN))
        a0 = regs.get(A0, UNKNOWN)
        own = _known(a0[0], FULL)
        origin = f"{name}({a0[0][1]:#x})" if own else name
        self._clobber(new, origin, _const(value) if value is not None else None)
        if value is not None:
            new[V0] = (new[V0][0], None, frozenset({f"{name}:cardinfo"}))
        return ret(new)


def _location_name(location):
    if location in LOCATIONS:
        return LOCATIONS[location]
    return "monster_zone" if location < 5 else "spell_trap_zone" if location <= 10 else f"location_{location:#x}"


def _fmt_value(v):
    if v[1] is not None:
        return f"&stack{v[1]:+#x}"
    if v[0] and v[0][0] == FULL:
        return f"{v[0][1]:#x}"
    if v[0]:
        return f"{v[0][1]:#x}/{v[0][0]:#x}"
    return "?" + ("(" + "+".join(sorted(v[2])) + ")" if v[2] else "")


def _call_key(call):
    return (call.location, call.pred, _fmt_value(call.pred_arg), _fmt_value(call.filter), _fmt_value(call.options))


# ---------------------------------------------------------------------------------------------- BOOT.BIN groups


def archetype_predicates(boot_bytes):
    """Archetype id -> BOOT.BIN predicate address, from the dispatch table of BOOT 0x088633f8."""
    pi = _load("re_prx_imports", "prx_imports.py")
    boot = pi.Elf(boot_bytes, pi.BOOT_BASE)
    return {i: v + pi.BOOT_BASE for i, v in enumerate(boot.u32(ARCHETYPE_TABLE - pi.BOOT_BASE, ARCHETYPE_COUNT))}


def predicate_members(boot_bytes, address, end):
    """Card ids loaded as immediates (`addiu r, zero, K` / `ori r, zero, K`, K a card id) in the BOOT.BIN
    function [address, end): the members of a compare-chain group predicate (a heuristic, for labels only)."""
    pi = _load("re_prx_imports", "prx_imports.py")
    boot = pi.Elf(boot_bytes, pi.BOOT_BASE)
    count = max(0, min((end - address) // 4, 4096))
    ids = []
    for w in boot.u32(address - pi.BOOT_BASE, count) if count else ():
        if w >> 26 in (9, 0x0D) and w >> 21 & 31 == 0 and ep.FIRST_CARD <= (w & 0xFFFF) <= ep.LAST_CARD:
            ids.append(w & 0xFFFF)
    return ids


# ---------------------------------------------------------------------------------------------- analysis


def builder_records(module):
    """(index, card id, builder address or None) of the list at 0x09dec554."""
    _, address, count = BUILDER_LIST
    for index in range(count):
        cid, handler = module.words(address + 8 * index, 2)
        yield index, cid, module.pointer(handler)


def load_cards(path):
    """card id -> {name, race, attribute, level, kind} from cardinfo (tools/cardinfo.py)."""
    ci = _load("re_cardinfo", "cardinfo.py")
    info = ci.CardInfo(Path(path).read_bytes(), "E")
    cards = {}
    for index in range(1, info.count):
        p = info.properties(index)
        cards[p["id"]] = {"name": info.name(index), "race": p["race"], "attribute": p["attribute"],
                          "level": p["level"], "kind": p["kind"]}
    return cards


def describe_call(call, archetypes=None, cards=None):
    """(decoded filter text, raw filter word text, raw options text, predicate text)."""
    filt = decode_filter(call.filter[0], call.filter[2], call.location, call.options[0])
    filt += decode_options(call.options[0], call.location, call.options[2])
    pred = ""
    if call.pred == ARCHETYPE_PREDICATE:
        arg = call.pred_arg[0]
        if _known(arg, FULL):
            label = (archetypes or {}).get(arg[1], "")
            pred = f"archetype={arg[1]:#x}" + (f" ({label})" if label else "")
        else:
            pred = f"archetype={_fmt_value(call.pred_arg)}"
    elif call.pred == NAME_PREDICATE:
        arg = call.pred_arg[0]
        if _known(arg, FULL):
            name = (cards or {}).get(arg[1] & 0x3FFF, {}).get("name", "")
            pred = f"name={arg[1]:#x}" + (f" ({name})" if name else "")
        else:
            pred = f"name={_fmt_value(call.pred_arg)}"
    elif call.pred:
        pred = f"predicate={call.pred:#010x} arg={_fmt_value(call.pred_arg)}"
    elif call.pred is None:
        pred = f"predicate={_fmt_value((None, None, frozenset()))}"
    if pred:
        filt.append(pred)
    return filt, _fmt_value(call.filter), _fmt_value(call.options)


def call_is_decoded(call):
    ok = _known(call.filter[0], FULL) and _known(call.options[0], FULL) and call.pred is not None
    if call.pred in (ARCHETYPE_PREDICATE, NAME_PREDICATE):
        ok = ok and _known(call.pred_arg[0], FULL)
    return ok


def analyse(module, registry, cards=None):
    """One dict per record: card id, builder, calls, adds, status (decoded, partial, custom, none)."""
    sim = Simulator(module, registry, cards)
    out = []
    for index, cid, builder in builder_records(module):
        rec = {"index": index, "card_id": cid, "builder": builder, "calls": [], "adds": set(), "cut": 0}
        if builder:
            calls, adds, cut = sim.run(builder, cid)
            rec.update(calls=calls, adds=adds, cut=cut)
        if rec["calls"]:
            rec["status"] = "decoded" if all(call_is_decoded(c) for c in rec["calls"]) else "partial"
        elif rec["adds"]:
            rec["status"] = "custom"
        else:
            rec["status"] = "none"
        out.append(rec)
    return out


def archetype_labels(boot_bytes, cards, boot_starts):
    """Archetype id -> "BOOT <predicate>; n ids e.g. <first> / <last>" (boot_starts: sorted BOOT.BIN function
    starts, from re/functions.csv, bounding each predicate)."""
    import bisect
    labels = {}
    for aid, address in archetype_predicates(boot_bytes).items():
        k = bisect.bisect_right(boot_starts, address)
        end = boot_starts[k] if k < len(boot_starts) else address + 0x400
        ids = predicate_members(boot_bytes, address, end)
        names = [cards[i]["name"] for i in ids if i in cards] if cards else []
        text = f"BOOT {address:#010x}"
        if names:
            text += f"; {len(ids)} ids e.g. {names[0]}" + (f" / {names[-1]}" if len(names) > 1 else "")
        labels[aid] = text
    return labels


def rows(records, cards=None, archetypes=None):
    out = []
    for rec in records:
        locs, decoded, raw_f, raw_o = [], [], [], []
        for call in rec["calls"]:
            text, f, o = describe_call(call, archetypes, cards)
            locs.append(call.location)
            decoded.append(f"{call.location}: " + " ".join(text))
            raw_f.append(f)
            raw_o.append(o)
        locs += sorted(a for a in rec["adds"] if a not in locs)
        out.append({"index": rec["index"], "card_id": f"{rec['card_id']:#06x}",
                    "card": (cards or {}).get(rec["card_id"], {}).get("name", ""),
                    "locations": " ".join(dict.fromkeys(locs)), "status": rec["status"],
                    "filter": " | ".join(decoded), "raw_filter": " ".join(raw_f), "raw_options": " ".join(raw_o),
                    "custom_adds": " ".join(sorted(rec["adds"])),
                    "builder": f"{rec['builder']:#010x}" if rec["builder"] else ""})
    return out


def card_filters(prx_bytes, functions=None, cards=None, archetypes=None):
    """Library entry point (used by tools/card_effects.py): one dict per record of the builder list with
    card_id (int), card, locations (list), status, filter (decoded text), raw_filter, raw_options,
    custom_adds and builder (text). `functions` is a re/functions.csv path (default: the repository's),
    `cards` a load_cards() dict for names and getter resolution, `archetypes` archetype_labels() output."""
    module = ep.Module(prx_bytes)
    names = ec.load_registry(functions or HERE.parent / "re" / "functions.csv")
    records = analyse(module, ec.Registry(names, module), cards)
    out = rows(records, cards, archetypes)
    for row in out:
        row["card_id"] = int(row["card_id"], 16)
        row["locations"] = row["locations"].split()
    return out


def check(module, records, cards=None):
    problems = []
    ids = [r["card_id"] for r in records]
    if ids != sorted(ids):
        problems.append(f"list {BUILDER_LIST[1]:#x} is not sorted by card id")
    if len(set(ids)) != len(ids):
        problems.append("duplicate card ids in the builder list")
    for r in records:
        if not r["builder"]:
            problems.append(f"record {r['index']}: builder pointer is not a .text offset")
    w = module.words(BUILD_DISPATCH, 64)
    if not any((x & 0xFFFF) == (BUILDER_LIST[1] - BASE) & 0xFFFF or (x & 0xFFFF) == (BUILDER_LIST[1] & 0xFFFF)
               for x in w):
        problems.append(f"the dispatcher {BUILD_DISPATCH:#x} does not reference the list")
    return problems


def summary(records):
    status = collections.Counter(r["status"] for r in records)
    by_loc = collections.Counter(c.location for r in records for c in r["calls"])
    calls = sum(len(r["calls"]) for r in records)
    decoded_calls = sum(1 for r in records for c in r["calls"] if call_is_decoded(c))
    builders = {r["builder"] for r in records if r["builder"]}
    unrecovered = sorted({r["builder"] for r in records if r["status"] == "none" and r["builder"]})
    lines = [f"records {len(records)}, builders {len(builders)}",
             "records: " + ", ".join(f"{k} {status.get(k, 0)}" for k in ("decoded", "partial", "custom", "none")),
             f"scanner calls {calls} (distinct per record), fully decoded {decoded_calls}; by location: " +
             ", ".join(f"{k} {n}" for k, n in by_loc.most_common()),
             f"paths cut by limits: {sum(1 for r in records if r['cut'])} records"]
    if unrecovered:
        lines.append("builders with no scanner or add_candidate call recovered: " +
                     " ".join(f"{a:#010x}" for a in unrecovered))
    return lines


def write_csv(path, out_rows):
    fields = list(out_rows[0]) if out_rows else ["empty"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(out_rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Decode the search filters of the candidate builders.")
    parser.add_argument("prx", type=Path, help="gmodule/rel_duel_eng.prx")
    parser.add_argument("command", nargs="?", choices=["list"], help="list: write the per-record CSV to -o")
    parser.add_argument("-o", "--out", type=Path, help="output CSV (under extracted/)")
    parser.add_argument("--check", action="store_true", help="structural checks and a decoding summary")
    parser.add_argument("--functions", type=Path, default=HERE.parent / "re" / "functions.csv")
    parser.add_argument("--cardinfo", type=Path, help="duelsys/cardinfo_eng.ehp: names, id checks, getters")
    parser.add_argument("--boot", type=Path, help="SYSDIR/BOOT.BIN: archetype predicates")
    args = parser.parse_args(argv)
    if not args.check and args.command != "list":
        parser.error("give the list command or --check")
    if args.command == "list" and not args.out:
        parser.error("list needs -o/--out")
    module = ep.Module(args.prx.read_bytes())
    registry = ec.Registry(ec.load_registry(args.functions), module)
    cards = load_cards(args.cardinfo) if args.cardinfo else None
    records = analyse(module, registry, cards)
    problems = check(module, records, cards)
    for p in problems:
        print("problem:", p, file=sys.stderr)
    names = ec.load_registry(args.functions)
    boot_starts = sorted(a for a in names if a < BASE)
    archetypes = archetype_labels(args.boot.read_bytes(), cards, boot_starts) if args.boot else None
    lines = summary(records)
    if cards is not None:
        missing = [f"{r['card_id']:#06x}" for r in records if r["card_id"] not in cards]
        lines.append(f"card ids without a cardinfo record (cut cards): {len(missing)}" +
                     (f" ({' '.join(missing)})" if missing else ""))
    if args.command == "list":
        write_csv(args.out, rows(records, cards, archetypes))
        lines.append(f"wrote {args.out}")
    print("\n".join(lines))
    if args.check:
        print("ok" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
