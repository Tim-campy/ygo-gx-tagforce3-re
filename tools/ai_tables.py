#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""List and check the duel AI's per-card priority tables in gmodule/rel_duel_eng.prx.

See docs/formats/ai-tables.md. Eleven tables of 8-byte (u32 card id, u32 handler) pairs lie back to back
at 0x09dfd448-0x09e00800 (with two switch jump tables in a 56-byte gap at 0x09dfe4c8); three u16 card-id
lists that share one handler each precede them at 0x09dfd2dc-0x09dfd448. The tables have no terminator:
their lengths are constants in the code that walks them, and --check verifies those constants.

  ai_tables.py <USRDIR>/gmodule/rel_duel_eng.prx list  [--cardinfo cardinfo_eng.ehp] [--functions re/functions.csv] [-o out.csv]
  ai_tables.py <USRDIR>/gmodule/rel_duel_eng.prx cards [--cardinfo ...] [-o out.csv]
  ai_tables.py <USRDIR>/gmodule/rel_duel_eng.prx --check [--cardinfo ...] [--functions ...]
  ai_tables.py <USRDIR>/gmodule/rel_duel_eng.prx classes --functions re/functions.csv [--functions re/names-duel_eng.csv]
               [--summary] [-o out.csv]
  ai_tables.py <USRDIR>/gmodule/rel_duel_eng.prx handlers --functions ... [--cardinfo ...] [--summary] [-o out.csv]

`classes` sorts the handlers into behaviour classes by their registry names (docs/subsystems/ai-helpers.md,
"Taxonomy"); --functions may be given several times (registry or names CSV, later files win). `handlers` gives,
per card, every AI handler its entries use with the handler's family (docs/subsystems/ai.md, "Per-card handler
families"), class and table positions. With --functions, --check also checks the handler names: every handler
is named, a per-card name lists exactly the cards that use the handler, a variant extends a named shared handler.

Addresses are runtime addresses with the module at 0x09be1400 (file offset = address - base + 0x54 for the
game's single PT_LOAD segment); pointers stored in the file are module offsets. The output is game data:
keep it under extracted/, never in git.
"""

import argparse
import collections
import csv
import importlib.util
import io
import re
import struct
import sys
from pathlib import Path

BASE = 0x09BE1400
TEXT_END = 0x09DE415C  # .text ends here; .sceStub.text follows
FIRST_CARD, LAST_CARD = 3720, 7993  # 0xe88-0x1f39, the card-id range of cardinfo (CARD_IntID)

# Pair tables: key, name, address, entries, situation. Order = layout order in .data.
TABLES = [
    ("T1", "chain", 0x09DFD448, 345, "chain response: every response window; also appended to F in the battle phase"),
    ("T2", "chain_first", 0x09DFDF10, 2, "chain response: tried first when there is a chain link to answer"),
    ("T3", "chain_conditional", 0x09DFDF20, 181, "chain response: only when the response mode is set or the link qualifies"),
    ("A", "opening", 0x09DFE500, 105, "main phase step 0; prepended to B (filtered) while categories are deferred"),
    ("B", "main", 0x09DFE848, 681, "main phase: spells and monster effects"),
    ("C", "summon_enablers", 0x09DFFD90, 7, "main phase step 1: before summoning"),
    ("D", "comeback", 0x09DFFDC8, 199, "main phase and end: only while the AI's battle dominance is negative"),
    ("E", "battle", 0x09E00400, 16, "battle check and attacker choice"),
    ("F", "battle_traps", 0x09E00480, 12, "battle check: only in the battle phase, followed by T1"),
    ("G", "end_of_turn", 0x09E004E0, 94, "main phase step 6 (end)"),
    ("H", "last_resort", 0x09E007D0, 6, "main phase step 6, after G"),
]
TABLES_END = 0x09E00800  # the jump table of ai_main_state_open follows
GAP = (0x09DFE4C8, 0x09DFE500)  # switch jump tables of 0x09d3ecf0 and 0x09d440d8 (7 + 7 words)

# u16 card-id lists walked by ai_try_chain_tables with one fixed handler each, chosen by the chain
# state byte 0x09e28fa0: key, address, entries, handler, state values.
LISTS = [
    ("R1", 0x09DFD2DC, 143, 0x09D22924, "0x12 0x13"),
    ("R2", 0x09DFD3FC, 36, 0x09D262C8, "0x14"),
    ("R3", 0x09DFD444, 1, 0x09D27348, "0x1b"),
]
R1_SENTINEL = 0x1935  # last entry of R1; 0x09d261c4 stops when it reaches the caller's own card id

# Consumers and the constants that encode the table lengths: address, name, size in bytes, table keys whose
# address the code builds with lui/addiu, immediates that must occur in the code.
CONSUMERS = [
    (0x09D8F0C4, "ai_table_length", 268, "A B C D E F G H", (0x69, 0x2A9, 0x312, 7, 199, 0x10, 0x0C, 0x5E, 6)),
    (0x09D8EFC0, "ai_table_entry", 260, "T1 A B F", ()),
    (0x09D3023C, "ai_chain_table_length", 88, "T1 T2 T3", (0x159, 2, 0xB5)),
    (0x09D2FD80, "ai_choose_chain_response", 1200, "T2 T3", (2, 0xB5)),
    (0x09D2F908, "ai_try_chain_tables", 1136, "T1 R1 R2 R3", (0x159, 0x8F, 0x24)),
    (0x09D8B184, "ai_main_state_open", 520, "A", (0x69,)),
    (0x09D8CFBC, "ai_main_state_end", 604, "D G H", (199, 0x5E, 6)),
    (0x09D8C1E8, "ai_try_summon_enablers", 120, "C", (7,)),
    (0x09D8C280, "ai_try_comeback_cards", 128, "D", (199,)),
    (0x09D8C300, "ai_try_battle_cards", 288, "E F", ()),
    (0x09D8C508, "ai_try_main_cards", 660, "B", ()),
    (0x09D30AF8, "ai_evaluate_card_all_tables", 380, "T1 T2 T3 A B C D E F G H", ()),
]

# ---------------------------------------------------------------------------------------------- image


class Module:
    """The PRX image: PT_LOAD segments, module offset 0 at the first segment's file offset."""

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

    def words(self, address, count):
        return struct.unpack_from(f"<{count}I", self.data, self.offset(address))

    def halves(self, address, count):
        return struct.unpack_from(f"<{count}H", self.data, self.offset(address))

    def code_pointer(self, value):
        """A module offset stored in the file, as a runtime address inside .text, or None."""
        address = self.base + value
        if not value or not self.base <= address < TEXT_END:
            return None
        try:
            self.offset(address)
        except ValueError:
            return None
        return address


def table_by_key(key):
    for t in TABLES:
        if t[0] == key:
            return t
    for t in LISTS:
        if t[0] == key:
            return t
    raise KeyError(key)


def entries(module):
    """(key, name, index, address, card id, handler address or None) for every pair-table entry."""
    for key, name, address, count, _ in TABLES:
        words = module.words(address, 2 * count)
        for i in range(count):
            yield key, name, i, address + 8 * i, words[2 * i], module.code_pointer(words[2 * i + 1])


def list_entries(module):
    """(key, index, address, card id, handler) for the u16 lists."""
    for key, address, count, handler, _ in LISTS:
        for i, cid in enumerate(module.halves(address, count)):
            yield key, i, address + 2 * i, cid, handler


# ---------------------------------------------------------------------------------------------- code scan


def code_facts(module, start, size):
    """Immediates of I-type ALU instructions and addresses built with lui + addiu/ori in one function.

    Only the forms the consumers use are modelled: `lui r,HI` and `addiu/ori x,r,LO` anywhere in the
    function (the module offset HI<<16 + LO is relocated at load time, so the runtime address is base + that).
    The compiler schedules the lui into branch delay slots, so every lui of a register is paired with every
    addiu/ori that reads it: an over-approximation that is fine for "does this function build address X"."""
    words = module.words(start, size // 4)
    immediates, addresses, hi = set(), set(), collections.defaultdict(set)
    for w in words:
        if w >> 26 == 0x0F:
            hi[w >> 16 & 31].add((w & 0xFFFF) << 16)
    for w in words:
        op, rs, imm = w >> 26, w >> 21 & 31, w & 0xFFFF
        simm = imm - 0x10000 if imm & 0x8000 else imm
        if op in (0x09, 0x0D):
            for high in hi.get(rs, ()):
                addresses.add((module.base + high + (simm if op == 0x09 else imm)) & 0xFFFFFFFF)
        if op in (0x09, 0x0A, 0x0B, 0x0D):
            immediates.add(imm)
    return immediates, addresses


# ---------------------------------------------------------------------------------------------- check


def check(module):
    """Structural checks; returns a list of problems (empty when everything matches the documented layout).

    Card ids are only range-checked here: the engine knows cards that the European cardinfo has no record
    for (they have effect records too), so ids missing from cardinfo are reported by missing_cards()."""
    problems = []
    expected = TABLES[0][2]
    for key, _, address, count, _ in TABLES:
        if address != expected and (expected, address) != GAP:
            problems.append(f"table {key} starts at {address:#010x}, previous ends at {expected:#010x}")
        expected = address + 8 * count
    if expected != TABLES_END:
        problems.append(f"last table ends at {expected:#010x}, expected {TABLES_END:#010x}")
    # no terminator: the word pair after a table is the next table's first entry, so validate every entry
    for key, _, _, address, cid, handler in entries(module):
        if not FIRST_CARD <= cid <= LAST_CARD:
            problems.append(f"{key} entry at {address:#010x}: card id {cid:#x} out of range")
        if handler is None:
            problems.append(f"{key} entry at {address:#010x}: handler is not a .text pointer")
    # the gap and the word after the last table hold jump-table pointers, not (id, handler) pairs
    for start, count in ((GAP[0], (GAP[1] - GAP[0]) // 4), (TABLES_END, 4)):
        for i, w in enumerate(module.words(start, count)):
            if module.code_pointer(w) is None:
                problems.append(f"word at {start + 4 * i:#010x} is not a jump-table pointer")
    for key, address, count, handler, _ in LISTS:
        ids = module.halves(address, count + 1)
        for i, cid in enumerate(ids[:count]):
            if not FIRST_CARD <= cid <= LAST_CARD:
                problems.append(f"list {key} entry {i}: card id {cid:#x} out of range")
        if key != "R2" and ids[count] != 0:  # R2 runs straight into R3
            problems.append(f"list {key} is not followed by a zero half-word")
    r1 = table_by_key("R1")
    if module.halves(r1[1] + 2 * (r1[2] - 1), 1)[0] != R1_SENTINEL:
        problems.append(f"list R1 does not end with {R1_SENTINEL:#x}")
    for address, name, size, keys, constants in CONSUMERS:
        immediates, refs = code_facts(module, address, size)
        for key in keys.split():
            if table_by_key(key)[2 if key[0] != "R" else 1] not in refs:
                problems.append(f"{name} ({address:#010x}) does not reference table {key}")
        for c in constants:
            if c not in immediates:
                problems.append(f"{name} ({address:#010x}) lacks the length constant {c:#x}")
    return problems


def missing_cards(module, known_ids):
    """Card ids of table and list entries that have no cardinfo record: {card id: entry count}."""
    ids = [r[4] for r in entries(module)] + [r[3] for r in list_entries(module)]
    return collections.Counter(cid for cid in ids if cid not in known_ids)


def summary(module):
    rows = list(entries(module))
    ids = {r[4] for r in rows}
    handlers = collections.Counter(r[5] for r in rows)
    per = ", ".join(f"{key} {count}" for key, _, _, count, _ in TABLES)
    lists = ", ".join(f"{key} {count}" for key, _, count, _, _ in LISTS)
    lines = [f"pair tables: {len(rows)} entries ({per})",
             f"distinct cards {len(ids)}, distinct handlers {len(handlers)}; most shared handler "
             f"{handlers.most_common(1)[0][0]:#010x} ({handlers.most_common(1)[0][1]} entries)",
             f"u16 lists: {lists}; {len({r[3] for r in list_entries(module)})} distinct cards"]
    return lines


# ---------------------------------------------------------------------------------------------- names


def load_cardinfo(path):
    """card id -> English name, using tools/cardinfo.py."""
    spec = importlib.util.spec_from_file_location("re_cardinfo", Path(__file__).resolve().parent / "cardinfo.py")
    cardinfo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cardinfo)
    info = cardinfo.CardInfo(Path(path).read_bytes(), "E")
    return {info.properties(i)["id"]: info.name(i) for i in range(1, info.count)}


def load_functions(path, names=None):
    """runtime address -> name from re/functions.csv (column id) or a names CSV (column address).

    Plain hex ids only; comment lines (#) are skipped; empty names are ignored. Entries update `names`."""
    names = {} if names is None else names
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(line for line in f if not line.startswith("#")):
            ident = row.get("id") or row.get("address") or ""
            if ident.startswith("0x") and row.get("name"):
                names[int(ident, 16)] = row["name"]
    return names


# ---------------------------------------------------------------------------------------------- classes

# Behaviour classes of the AI handlers, derived from their names (first match wins). The names encode what
# the handler tests (docs/subsystems/ai-helpers.md); unnamed handlers (tool default names) are "unnamed".
CLASSES = [
    ("constant", "always / never", r"^ai_cond_(always|never)$"),
    ("event", "reacts to a queued timing event (attack, damage step, summon)", r"_event$"),
    ("chain", "response to a chain link: threat, negation, use-before-loss", r"link|chain|threatened|respond"),
    ("lp", "Life-Point thresholds: burn, LP gain, damage prevention", r"burn|damage|_lp\b|_lp_|lethal"),
    ("battle", "battle dominance, attackers, battle plan", r"battle|attack|behind|dominance|plan|boost|stall"),
    ("summon", "summon or equip enablers", r"summon|revive|ritual|fusion|union|equip|token"),
    ("removal", "removal or control change, gated by the target's value", r"destroy|removal|wipe|banish|remove|"
                                                                            r"control|swap"),
    ("target", "target availability", r"target"),
    ("limit", "copies already active, once per turn", r"active_cop|count_below|once_per_turn|applied"),
    ("phase", "phase / turn timing", r"standby|end_phase"),
    ("resources", "hand, deck, candidates and costs", r"draw|discard|candidate|hand|cost|deck|tribute|recycle"),
    ("board", "other board-state checks", r"monster|field_spell|zone|face_up|board"),
    ("state", "rule flags, turn state and committed activations", r"rule_state|committed"),
]
DEFAULT_NAME = re.compile(r"^(FUN_|thunk_FUN_|LAB_|SUB_)|^$")

# Families of the single-use (per-card) handlers (docs/subsystems/ai.md, "Per-card handler families"). A per-card
# handler is named ai_handler_<stem>_<card id>[_<card id>][_<tables>]: the ids are the cards whose table entries
# use it (4 lower-case hex digits each), the optional last part tells two handlers of one card apart by their
# tables. The stem is either a family stem below (a bespoke predicate whose dominant query decides the family) or
# the stem of the shared handler it extends (family "variant"). key, stem, behaviour class, description.
FAMILIES = [
    ("event", "react_to_event", "event", "reads the queued timing events (0x09e28f98 / 0x09e28fa0)"),
    ("link", "respond_to_link", "chain", "chain-table handler that reads the link it answers or a threat query"),
    ("draw", "check_draw", "resources", "deck-out and hand-limit checks for draw effects"),
    ("lp", "check_lp", "lp", "LP estimates, burn, LP gain or LP thresholds"),
    ("discard", "check_discard", "resources", "a discard cost can be paid without losing a needed card"),
    ("cost", "check_cost", "resources", "a Tribute/send/hand cost can be chosen"),
    ("candidate", "check_candidates", "resources", "enough acceptable candidates (search, revive, recover)"),
    ("summon", "check_summon", "summon", "free monster zones, Normal Summon still available, summon simulation"),
    ("battle", "check_battle", "battle", "battle phase, attackers, the battle plan"),
    ("target", "check_targets", "target", "target mask or a chosen target"),
    ("target_dom", "check_targets_by_dominance", "removal", "target choice gated by the battle dominance"),
    ("dominance", "check_dominance", "battle", "battle dominance without a target query"),
    ("limit", "check_copies", "limit", "copies already active or on the chain"),
    ("field", "check_field_spell", "board", "field-spell zone state"),
    ("graveyard", "check_graveyard", "resources", "Graveyard contents"),
    ("phase", "check_phase", "phase", "turn player and phase only"),
    ("committed", "check_committed", "state", "the committed-activation shortcut (ai_is_normal_spell_in_graveyard)"),
    ("board", "check_board", "board", "other board counts (named cards, monsters, counters, hand size)"),
    ("state", "check_rule_state", "state", "rule flags, link fields or event codes only, no helper call"),
]
PER_CARD = re.compile(r"^ai_handler_(?P<stem>[a-z0-9_]+?)(?P<ids>(?:_[0-9a-f]{4})+)(?:_(?P<tables>[a-z0-9]+))?$")


FAMILY_STEMS = {stem for _, stem, _, _ in FAMILIES}


def per_card_name(name, known=None):
    """(stem, [card ids]) of a per-card handler name, or None.

    The ids must be card ids (3720-7993). A stem that is not a family stem must be the stem of a shared handler
    (ai_handler_<stem> or ai_cond_<stem>); with `known` (the set of registry names) that is checked, which keeps
    shared names such as ai_handler_burn_at_least_1000 from being read as per-card."""
    m = PER_CARD.match(re.sub(r"^thunk_", "", name or ""))  # Ghidra shows a thunk handler as thunk_<name>
    if not m:
        return None
    ids =[int(x, 16) for x in m["ids"][1:].split("_")]
    if not all(FIRST_CARD <= c <= LAST_CARD for c in ids):
        return None
    if m["stem"] not in FAMILY_STEMS and known is not None and not {f"ai_handler_{m['stem']}",
                                                                      f"ai_cond_{m['stem']}"} & known:
        return None
    return m["stem"], ids


def handler_family(name, known=None):
    """Family key of a handler name: a FAMILIES key, "variant" (per-card refinement of a shared handler),
    "shared" (a named handler that is not per-card) or "unnamed". `known` as in per_card_name."""
    if not name or DEFAULT_NAME.search(name):
        return "unnamed"
    pc = per_card_name(name, known)
    if not pc:
        return "shared"
    for key, stem, _, _ in FAMILIES:
        if pc[0] == stem:
            return key
    return "variant"


def handler_class(name, known=None):
    """Behaviour class key of a handler name: a CLASSES key, "unnamed" or "other"."""
    if not name or DEFAULT_NAME.search(name):
        return "unnamed"
    pc = per_card_name(name, known)
    if pc:
        for _, stem, cls, _ in FAMILIES:
            if pc[0] == stem:
                return cls
        name = "ai_handler_" + pc[0]  # a variant takes the class of the shared handler it extends
    stem = re.sub(r"^ai_(handler_|cond_)?", "", name)  # "handler" must not match "hand"
    for key, _, pattern in CLASSES:
        if re.search(pattern, name if key == "constant" else stem):
            return key
    return "other"


def class_rows(module, functions=None):
    """One row per distinct handler (pair tables and u16 lists): address, name, class, entries, tables."""
    functions = functions or {}
    known = set(functions.values())
    per = collections.defaultdict(collections.Counter)
    for key, _, _, _, _, handler in entries(module):
        if handler:
            per[handler][key] += 1
    for key, _, _, _, handler in list_entries(module):
        per[handler][key] += 1
    rows = []
    for handler, tables in sorted(per.items(), key=lambda kv: (-sum(kv[1].values()), kv[0])):
        name = functions.get(handler, "")
        rows.append({"handler": f"{handler:#010x}", "name": name, "class": handler_class(name, known),
                     "entries": sum(tables.values()),
                     "tables": " ".join(f"{k}:{n}" for k, n in sorted(tables.items()))})
    return rows


def handler_users(module):
    """handler address -> {card id: [table:index, ...]} over the pair tables and the u16 lists."""
    users = collections.defaultdict(lambda: collections.defaultdict(list))
    for key, _, i, _, cid, handler in entries(module):
        if handler:
            users[handler][cid].append(f"{key}:{i}")
    for key, i, _, cid, handler in list_entries(module):
        users[handler][cid].append(f"{key}:{i}")
    return users


def handler_rows(module, cards=None, functions=None):
    """One row per (card, handler) pair: the AI handlers each card has, with family and behaviour class."""
    cards, functions = cards or {}, functions or {}
    known = set(functions.values())
    rows = []
    for handler, per in handler_users(module).items():
        name = functions.get(handler, "")
        for cid, where in per.items():
            rows.append({"card_id": f"{cid:#06x}", "card": cards.get(cid, ""), "handler": f"{handler:#010x}",
                         "handler_name": name, "family": handler_family(name, known),
                         "class": handler_class(name, known),
                         "shared_by": len(per), "tables": " ".join(where)})
    rows.sort(key=lambda r: (r["card_id"], r["tables"]))
    return rows


def check_names(module, functions):
    """Registry checks of the handler names: every handler named; a per-card name lists exactly the cards whose
    entries use the handler; a variant extends a shared handler that exists. Returns a list of problems."""
    problems = []
    known = set(functions.values())
    for handler, per in sorted(handler_users(module).items()):
        name = functions.get(handler, "")
        if handler_family(name, known) == "unnamed":
            problems.append(f"handler {handler:#010x} ({len(per)} cards) has no name")
            continue
        pc = per_card_name(name, known)
        if not pc:
            loose = per_card_name(name)  # per-card grammar, but the stem is neither a family nor a shared handler
            if loose and set(loose[1]) == set(per):
                problems.append(f"{name} ({handler:#010x}) extends ai_handler_{loose[0]} / ai_cond_{loose[0]}, "
                                f"which is not named")
            continue
        if set(pc[1]) != set(per):
            problems.append(f"{name} ({handler:#010x}) names cards {' '.join(f'{c:#x}' for c in pc[1])}, "
                            f"used by {' '.join(f'{c:#x}' for c in sorted(per))}")
    return problems


def family_summary(rows):
    """Lines: per family, handlers and (card, handler) pairs."""
    handlers, pairs = collections.defaultdict(set), collections.Counter()
    for r in rows:
        handlers[r["family"]].add(r["handler"])
        pairs[r["family"]] += 1
    order = ["shared", "variant"] + [k for k, _, _, _ in FAMILIES] + ["unnamed"]
    lines = [f"{'family':12} {'handlers':>8} {'cards':>6}"]
    lines += [f"{k:12} {len(handlers[k]):8} {pairs[k]:6}" for k in order if handlers[k]]
    lines.append(f"{'total':12} {len(set().union(*handlers.values())):8} {sum(pairs.values()):6}")
    return lines


def class_summary(rows):
    """Lines: per class, handlers and table entries (with the share of all entries)."""
    total = sum(r["entries"] for r in rows)
    handlers, count = collections.Counter(), collections.Counter()
    for r in rows:
        handlers[r["class"]] += 1
        count[r["class"]] += r["entries"]
    order = [k for k, _, _ in CLASSES] + ["other", "unnamed"]
    lines = [f"{'class':10} {'handlers':>8} {'entries':>8} {'share':>7}"]
    for key in order:
        if handlers[key]:
            lines.append(f"{key:10} {handlers[key]:8} {count[key]:8} {100 * count[key] / total:6.1f}%")
    lines.append(f"{'total':10} {len(rows):8} {total:8}")
    return lines


# ---------------------------------------------------------------------------------------------- output


def list_rows(module, cards=None, functions=None):
    cards, functions = cards or {}, functions or {}
    rows = []
    for key, name, i, address, cid, handler in entries(module):
        rows.append({"table": key, "name": name, "index": i, "address": f"{address:#010x}", "card_id": f"{cid:#06x}",
                     "card": cards.get(cid, ""), "handler": f"{handler:#010x}" if handler else "",
                     "handler_name": functions.get(handler, "")})
    for key, i, address, cid, handler in list_entries(module):
        rows.append({"table": key, "name": "chain_state_list", "index": i, "address": f"{address:#010x}",
                     "card_id": f"{cid:#06x}", "card": cards.get(cid, ""), "handler": f"{handler:#010x}",
                     "handler_name": functions.get(handler, "")})
    return rows


def card_rows(module, cards=None):
    cards = cards or {}
    per = collections.defaultdict(list)
    for key, _, i, _, cid, _ in entries(module):
        per[cid].append(f"{key}:{i}")
    for key, i, _, cid, _ in list_entries(module):
        per[cid].append(f"{key}:{i}")
    return [{"card_id": f"{cid:#06x}", "card": cards.get(cid, ""), "count": len(v), "tables": " ".join(v)}
            for cid, v in sorted(per.items())]


def write_csv(rows, out):
    handle = open(out, "w", newline="", encoding="utf-8") if out else io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", newline="", write_through=True)
    try:
        w = csv.DictWriter(handle, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    finally:
        if out:
            handle.close()
        else:
            handle.detach()


def main(argv=None):
    parser = argparse.ArgumentParser(description="List and check the duel AI priority tables of rel_duel_eng.prx.")
    parser.add_argument("prx", type=Path, help="gmodule/rel_duel_eng.prx")
    parser.add_argument("command", nargs="?", choices=("list", "cards", "check", "classes", "handlers"),
                        default="list")
    parser.add_argument("--check", action="store_true", help="same as the check command")
    parser.add_argument("--cardinfo", type=Path, help="duelsys/cardinfo_eng.ehp: card names (and id check)")
    parser.add_argument("--functions", type=Path, action="append",
                        help="re/functions.csv or a names CSV: handler names (repeatable; later files win)")
    parser.add_argument("--summary", action="store_true", help="classes / handlers: print the per-class / per-family totals only")
    parser.add_argument("-o", "--output", type=Path, help="CSV file (keep it under extracted/)")
    args = parser.parse_args(argv)
    module = Module(args.prx.read_bytes())
    cards = load_cardinfo(args.cardinfo) if args.cardinfo else None
    functions = None
    for path in args.functions or ():
        functions = load_functions(path, functions)
    if args.check or args.command == "check":
        problems = check(module) + (check_names(module, functions) if functions else [])
        for p in problems:
            print("problem:", p, file=sys.stderr)
        if problems:
            print(f"{len(problems)} problem(s)")
            return 1
        for line in summary(module):
            print(line)
        if functions:
            families = collections.Counter(handler_family(functions.get(h, ""), set(functions.values())) for h in handler_users(module))
            print(f"handler names: {sum(families.values())} handlers; "
                  + ", ".join(f"{k} {n}" for k, n in families.most_common()))
        if cards:
            missing = missing_cards(module, set(cards))
            print(f"cardinfo: {len(missing)} card ids ({sum(missing.values())} entries) have no record "
                  f"(not in the released card list): {' '.join(f'{c:#x}' for c in sorted(missing))}")
        print("ok")
        return 0
    if args.command == "classes":
        rows = class_rows(module, functions)
        if args.summary:
            print("\n".join(class_summary(rows)))
            return 0
    elif args.command == "handlers":
        rows = handler_rows(module, cards, functions)
        if args.summary:
            print("\n".join(family_summary(rows)))
            return 0
    elif args.command == "list":
        rows = list_rows(module, cards, functions)
    else:
        rows = card_rows(module, cards)
    write_csv(rows, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
