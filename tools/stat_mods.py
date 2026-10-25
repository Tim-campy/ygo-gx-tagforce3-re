#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Extract the per-card ATK/DEF modifiers of gmodule/rel_duel_eng.prx.

See docs/subsystems/stat-modifiers.md. ATK/DEF modifiers are not data: they are card-id compare chains
inside a handful of stat functions (the card's own continuous effect, other face-up cards, the field
spell, attached effects, equip spells, the Damage Step bonuses). This tool lists every card id those
functions test or pass to a lookup helper, with the section of the computation it belongs to and the
constants and calls of the case body, so that the port can rebuild the modifier table.

  stat_mods.py <USRDIR>/gmodule/rel_duel_eng.prx -o extracted/stat_mods [--cardinfo <cardinfo_eng.ehp>]
  stat_mods.py <USRDIR>/gmodule/rel_duel_eng.prx --check

Written files (game data: keep them under extracted/, never in git):

  stat_mods.csv   one row per card-id use in a stat function
  coverage.csv    with --cardinfo: every card with genre "Increase/Decrease ATK/DEF" or a stat-function
                  reference, and the sections that reference it

The MIPS decoder, the module loader and the CSV/name helpers come from tools/effect_params.py.
"""

import argparse
import collections
import importlib.util
import sys
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_effect_params", Path(__file__).resolve().parent / "effect_params.py")
ep = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ep)

GENRE_ATK_DEF = 25  # CARD_Genre bit "Increase/Decrease ATK/DEF" (docs/formats/cardinfo.md)

# The stat functions: (address, size, name, layer, sections). Sections are (start, end, name) address
# ranges of the card-id loads inside the function; see stat-modifiers.md for what each one does.
BUILDER = 0x09C05304
FUNCTIONS = [
    (0x09C04AB4, 2116, "duel_core_compute_base_stats", "base", []),
    (BUILDER, 19196, "duel_core_compute_card_stats", "current", [
        (0x09C054B0, 0x09C05500, "attribute"),
        (0x09C05500, 0x09C07500, "self"),
        (0x09C07500, 0x09C08780, "attached"),
        (0x09C08780, 0x09C08AC0, "linked_card"),
        (0x09C08AC0, 0x09C09500, "equip_spell"),
        (0x09C09500, 0x09C09900, "equipped_monster"),
        (0x09C09900, 0x09C0A000, "final"),
    ]),
    (0x09C04198, 2028, "duel_effects_get_field_card_stat_bonus", "field_card", []),
    (0x09C03B44, 1620, "duel_effects_get_field_spell_stat_bonus", "field_spell", []),
    (0x09DD1C90, 1548, "duel_core_battle_get_damage_calc_bonus", "damage_step", []),  # Ghidra counts 1,496
    (0x09DC15C8, 11616, "duel_core_battle_compute_stats", "damage_step", []),
]

# Helpers that take a card id; named in re/names-duel_eng.csv (stat-modifiers.md).
HELPERS = {
    0x09BE9168: "slot_has_effect",
    0x09BE9B44: "sum_effect_values",
    0x09BE7D00: "count_links_from",
    0x09BF7CB4: "is_active_card_at",
    0x09BF8A78: "count_active_cards",
    0x09BE7C28: "count_links_unchecked",
    0x09BE7D48: "count_links_since",
}
BRANCH_OPS = {4: "beq", 0x14: "beql", 5: "bne", 0x15: "bnel"}

# Anchors for --check: (function, card id, use) that must be found.
ANCHORS = [
    (0x09C03B44, 0x10F3, "test"),     # Sogen: +200 to Warriors and Beast-Warriors
    (0x09C04AB4, 0x1E46, "test"),     # Unstable Evolution: original ATK becomes 2400 or 1000
    (BUILDER, 0x10E0, "test"),        # Horn of the Unicorn: equip +700/+700
    (BUILDER, 0x1C5F, "test"),        # Skullgeoth: set ATK/DEF from attached values
    (BUILDER, 0x1257, "call"),        # Reverse Trap: modifiers are subtracted
    (0x09DD1C90, 0x1B40, "test"),     # Fusion Devourer
]


def section_of(sections, address):
    for start, end, name in sections:
        if start <= address < end:
            return name
    return ""


def _uses_reg(i, reg):
    return i.rs == reg or i.rt == reg


def card_id_uses(module, start, end):
    """Card-id immediates in [start, end): yields (address, card id, use, branch or call instruction).

    `test`: `li rX, K` and, before rX is overwritten, a beq/beql/bne/bnel on rX (within 12 instructions).
    `call`: `li rX, K` with rX an argument register and a `jal` reached before rX is overwritten, or the
    `li` sits in the delay slot of a `jal`. Anything else is `other`."""
    for pc in range(start, end - 4, 4):
        a = ep.insn(module, pc)
        if not (a.kind in ("addiu", "ori") and a.rs == 0 and a.rt and ep.FIRST_CARD <= a.imm <= ep.LAST_CARD):
            continue
        use, ref = "other", None
        prev = ep.insn(module, pc - 4)
        if prev.op == 3 and 4 <= a.rt <= 7:
            yield pc, a.imm, "call", prev
            continue
        for k in range(1, 13):
            b = ep.insn(module, pc + 4 * k)
            if b.op in BRANCH_OPS and _uses_reg(b, a.rt) and b.rs != b.rt:
                use, ref = "test", b
                break
            if b.op == 3:
                if 4 <= a.rt <= 7:
                    use, ref = "call", b
                break
            if b.writes == a.rt or b.op == 2 or b.kind == "jr":
                break
        yield pc, a.imm, use, ref


def case_body(module, branch):
    """Mechanical summary of the code a card-id test selects: stat-like constants and calls.

    The body starts at the branch target (beq) or after the delay slot (bne). The walk follows
    fall-through only and stops at an unconditional branch, `jr`, or the next card-id test."""
    pc = branch.target if branch.op in (4, 0x14) else branch.pc + 8
    values, calls = [], []
    for _ in range(24):
        i = ep.insn(module, pc)
        if i.kind in ("addiu", "ori") and i.rs == 0 and ep.FIRST_CARD <= i.imm <= ep.LAST_CARD:
            nxt = ep.insn(module, pc + 4)
            if nxt.op in BRANCH_OPS:
                break
        if i.kind in ("addiu", "addi") and i.rt != ep.SP and i.rs != ep.SP and 50 <= abs(i.simm) <= 10000 \
                and i.simm % 50 == 0:
            values.append(i.simm)
        elif i.kind == "ori" and i.rs == 0 and 50 <= i.imm <= 10000 and i.imm % 50 == 0:
            values.append(i.imm)
        if i.op == 3:
            calls.append(i.target)
        if i.kind == "jr" or i.op == 2 or (i.op == 4 and i.rs == i.rt == 0):
            break
        pc += 4
    return values, calls


def stat_uses(module):
    """All card-id uses in the stat functions, as CSV rows."""
    rows = []
    for start, size, name, layer, sections in FUNCTIONS:
        for pc, cid, use, ref in card_id_uses(module, start, start + size):
            row = {"function": f"{start:#010x}", "function_name": name, "layer": layer,
                   "section": section_of(sections, pc) or layer, "address": f"{pc:#010x}",
                   "card_id": f"{cid:#x}", "use": use, "target": "", "helper": "", "values": "", "calls": ""}
            if use == "test":
                values, calls = case_body(module, ref)
                row["target"] = f"{ref.target if ref.op in (4, 0x14) else ref.pc + 8:#010x}"
                row["values"] = " ".join(str(v) for v in values)
                row["calls"] = " ".join(HELPERS.get(c, f"{c:#010x}") for c in calls)
            elif use == "call":
                row["helper"] = HELPERS.get(ref.target, f"{ref.target:#010x}")
            rows.append(row)
    return rows


def check(module):
    """Structural checks that the function table matches this module; returns a list of problems."""
    problems = []
    for start, size, name, _, _ in FUNCTIONS:
        if not module.contains(start) or not module.contains(start + size - 4):
            problems.append(f"{name} ({start:#x}) is outside the module")
            continue
        first = ep.insn(module, start)
        if not (first.kind == "addiu" and first.rt == ep.SP and first.rs == ep.SP and first.simm < 0):
            problems.append(f"no prologue at {start:#x} ({name})")
        if not any(ep.insn(module, pc).kind == "jr" and ep.insn(module, pc).rs == ep.RA
                   for pc in range(start, start + size, 4)):
            problems.append(f"{name} has no return in its {size} bytes")
    if problems:
        return problems
    rows = stat_uses(module)
    found = {(int(r["function"], 16), int(r["card_id"], 16), r["use"]) for r in rows}
    for anchor in ANCHORS:
        if anchor not in found:
            problems.append(f"expected {anchor[2]} of card {anchor[1]:#x} in {anchor[0]:#x}")
    return problems


def load_cards(path):
    """{card id: (name, has ATK/DEF genre)} from cardinfo_<lang>.ehp."""
    spec = importlib.util.spec_from_file_location("re_cardinfo", Path(__file__).resolve().parent / "cardinfo.py")
    cardinfo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cardinfo)
    info = cardinfo.CardInfo(Path(path).read_bytes(), "E")
    cards = {}
    for index in range(1, info.count):
        cid = info.properties(index)["id"]
        cards[cid] = (info.name(index), bool(info.genre_mask(index) >> GENRE_ATK_DEF & 1))
    return cards


def coverage(rows, cards):
    by_card = collections.defaultdict(set)
    for r in rows:
        by_card[int(r["card_id"], 16)].add(r["section"])
    out = []
    for cid in sorted(set(by_card) | {c for c, (_, g) in cards.items() if g}):
        name, genre = cards.get(cid, ("", False))
        out.append({"card_id": f"{cid:#x}", "name": name, "genre_atk_def": int(genre),
                    "sections": " ".join(sorted(by_card.get(cid, ())))})
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description="Extract the per-card ATK/DEF modifiers from rel_duel_eng.prx.")
    parser.add_argument("prx", type=Path, help="gmodule/rel_duel_eng.prx")
    parser.add_argument("-o", "--out", type=Path, help="output directory (under extracted/)")
    parser.add_argument("--check", action="store_true", help="only run the structural checks")
    parser.add_argument("--cardinfo", type=Path, help="duelsys/cardinfo_eng.ehp: names and coverage")
    args = parser.parse_args(argv)
    module = ep.Module(args.prx.read_bytes())
    problems = check(module)
    for p in problems:
        print("problem:", p, file=sys.stderr)
    if args.check:
        print("ok" if not problems else f"{len(problems)} problem(s)")
        return 1 if problems else 0
    if not args.out:
        parser.error("-o/--out is required unless --check is given")
    rows = stat_uses(module)
    args.out.mkdir(parents=True, exist_ok=True)
    cards = load_cards(args.cardinfo) if args.cardinfo else None
    ep.write_csv(args.out / "stat_mods.csv", rows, {c: n for c, (n, _) in cards.items()} if cards else None)
    counts = collections.Counter((r["section"], r["use"]) for r in rows)
    for section in dict.fromkeys(r["section"] for r in rows):
        ids = {r["card_id"] for r in rows if r["section"] == section}
        print(f"{section}: {len(ids)} cards ({counts[(section, 'test')]} tests, "
              f"{counts[(section, 'call')]} helper calls, {counts[(section, 'other')]} other)")
    print(f"total: {len({r['card_id'] for r in rows})} distinct cards in {len(rows)} uses")
    if cards:
        cov = coverage(rows, cards)
        ep.write_csv(args.out / "coverage.csv", cov)
        genre = [r for r in cov if r["genre_atk_def"]]
        print(f"genre Increase/Decrease ATK/DEF: {len(genre)} cards, "
              f"{sum(1 for r in genre if r['sections'])} referenced by a stat function")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
