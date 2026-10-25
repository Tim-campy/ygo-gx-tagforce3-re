#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""List and check the fusion recipe table and the ritual table of gmodule/rel_duel_eng.prx.

See docs/formats/fusion-recipes.md and docs/subsystems/summon.md.

* Fusion recipes at 0x09debe98: 138 records of four u16 (fusion id, material code 0, 1, 2); a third
  material code of 0 means two materials. A material code below 0x24 is a generic requirement (a monster
  Type, a card group or a Level/graveyard condition, see MATERIAL_CODES); a larger code is a card id.
  Four Fusions are hard-coded in the code instead (HARDCODED).
* Ritual table at 0x09dec4d4: u32 records, terminated by 0; bits 0-13 ritual monster id, bits 14-27
  ritual spell id, bits 28-31 the Level total the tributes must reach.

  fusion.py <USRDIR>/gmodule/rel_duel_eng.prx recipes [--cardinfo cardinfo_eng.ehp] [-o out.csv]
  fusion.py <USRDIR>/gmodule/rel_duel_eng.prx rituals [--cardinfo ...] [-o out.csv]
  fusion.py <USRDIR>/gmodule/rel_duel_eng.prx --check [--cardinfo ...]

Addresses are runtime addresses with the module at 0x09be1400. The output names cards and lists their
materials, which is game data: keep it under extracted/, never in git.
"""

import argparse
import collections
import importlib.util
import io
import csv
import struct
import sys
from pathlib import Path

BASE = 0x09BE1400
FIRST_CARD, LAST_CARD = 3720, 7993  # the card-id range of cardinfo (CARD_IntID)

RECIPES = 0x09DEBE98
RECIPE_COUNT = 0x8A  # 138: the loop bound in every reader
THREE_MATERIAL_FIRST = 119  # records 0-118 have two materials, 119-137 three (layout fact, checked)
RITUALS = 0x09DEC4D4
RITUAL_MAX = 64  # safety bound for the zero-terminated walk; the game has 31 records

# Generic material codes, tested by duel_effects_card_matches_material_code (0x09cb910c).
# Codes 1-0x15 are monster Types (cardinfo race numbers); the predicate of each group code is a BOOT.BIN
# card-id list (address given).
RACES = {1: "Dragon", 2: "Zombie", 3: "Fiend", 4: "Pyro", 5: "Sea Serpent", 6: "Rock", 7: "Machine", 8: "Fish",
         9: "Dinosaur", 10: "Insect", 11: "Beast", 12: "Beast-Warrior", 13: "Plant", 14: "Aqua", 15: "Warrior",
         16: "Winged Beast", 17: "Fairy", 18: "Spellcaster", 19: "Thunder", 20: "Reptile", 21: "Psychic"}
MATERIAL_CODES = {code: f"any {name}-Type monster" for code, name in RACES.items()}
MATERIAL_CODES.update({
    0x16: "Ojama group (BOOT 0x08861068)",
    0x17: "Gladiator Beast group (BOOT 0x08861f94)",
    0x18: "Rainbow Dragon group (BOOT 0x08862334)",
    0x19: "Ancient Gear group (BOOT 0x08861298)",
    0x1A: "any Gemini monster (kind 19)",
    0x1B: "Neos group (BOOT 0x08860e6c)",
    0x1C: "Neo-Spacian group (BOOT 0x088616a8)",
    0x1D: "HERO group (BOOT 0x08861810)",
    0x1E: "Neos, Neo-Spacian or HERO group (BOOT 0x08862968)",
    0x1F: "Fiend-Type monster of Level 6 or more",
    0x20: "monster in a graveyard of Level 4 or less",
    0x21: "monster in a graveyard of Level 5 or 6",
    0x22: "monster in a graveyard of Level 7 or more",
    0x23: "monster in a graveyard of Level 8 or more",
})
GENERIC_LIMIT = 0x24  # codes >= this are card ids

# Fusions whose materials are hard-coded in duel_effects_get_fusion_material_code (0x09cb9630) and
# duel_effects_get_fusion_material_count (0x09cb959c) instead of the table: id -> material codes.
HARDCODED = {
    0x1E7E: (0x1C, 0x1B, 0x1D, 0x1E, 0x1E),
    0x1AB3: (0x1A57, 0x1A4F, 0x18F3, 0x1A55),
    0x19EF: (0x18A6, 0x18A7, 0x18A8, 0x18F9),
    0x157E: (1, 1, 1, 1, 1),
}

# Functions that walk the tables: address, name, size in bytes, table, constants that must occur.
CONSUMERS = [
    (0x09CB9630, "duel_effects_get_fusion_material_code", 304, RECIPES, (RECIPE_COUNT,)),
    (0x09CB959C, "duel_effects_get_fusion_material_count", 148, RECIPES, (RECIPE_COUNT,)),
    (0x09CBACE0, "duel_effects_resolve_fusion_summon", 5264, RECIPES, (RECIPE_COUNT,)),
    (0x09CCD668, "duel_effects_resolve_ritual_summon", 2300, RITUALS, ()),
    (0x09CCD5B4, "duel_effects_cond_ritual_summon", 180, RITUALS, ()),
    (0x09CCD224, "duel_effects_can_ritual_summon_entry", 912, RITUALS, ()),
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


# ---------------------------------------------------------------------------------------------- tables

Recipe = collections.namedtuple("Recipe", "index address fusion materials")
Ritual = collections.namedtuple("Ritual", "index address monster spell level")


def recipes(module):
    """The 138 recipe records; `materials` drops the trailing 0 of two-material records."""
    values = module.halves(RECIPES, 4 * RECIPE_COUNT)
    out = []
    for i in range(RECIPE_COUNT):
        fusion, *codes = values[4 * i: 4 * i + 4]
        out.append(Recipe(i, RECIPES + 8 * i, fusion, tuple(codes[:2] if codes[2] == 0 else codes)))
    return out


def rituals(module):
    """Ritual records up to the terminating 0 word."""
    out = []
    for i in range(RITUAL_MAX):
        word, = module.words(RITUALS + 4 * i, 1)
        if word == 0:
            return out
        out.append(Ritual(i, RITUALS + 4 * i, word & 0x3FFF, word >> 14 & 0x3FFF, word >> 28))
    raise ValueError(f"ritual table not terminated within {RITUAL_MAX} records")


def material_count(module, fusion):
    """What duel_effects_get_fusion_material_count returns: 0 for an unknown Fusion."""
    if fusion in HARDCODED:
        return len(HARDCODED[fusion])
    for r in recipes(module):
        if r.fusion == fusion:
            return len(r.materials)
    return 0


def describe_code(code, cards=None):
    if code < GENERIC_LIMIT:
        return MATERIAL_CODES.get(code, f"unknown generic code {code:#x}")
    name = (cards or {}).get(code)
    return f"{name[0] if isinstance(name, tuple) else name} ({code:#06x})" if name else f"card {code:#06x}"


# ---------------------------------------------------------------------------------------------- code scan

LOADS_STORES = (0x20, 0x21, 0x23, 0x24, 0x25, 0x28, 0x29, 0x2B)


def code_facts(module, start, size):
    """Immediates of I-type ALU instructions, and addresses built from a lui with addiu/ori or used as
    the base of a load/store. Every lui of a register is paired with every user of that register (the
    compiler schedules lui into delay slots): an over-approximation that suits "does this code use X"."""
    words = module.words(start, size // 4)
    immediates, addresses, hi = set(), set(), collections.defaultdict(set)
    for w in words:
        if w >> 26 == 0x0F:
            hi[w >> 16 & 31].add((w & 0xFFFF) << 16)
    for w in words:
        op, rs, imm = w >> 26, w >> 21 & 31, w & 0xFFFF
        simm = imm - 0x10000 if imm & 0x8000 else imm
        if op in (0x09, 0x0D) or op in LOADS_STORES:
            for high in hi.get(rs, ()):
                addresses.add((module.base + high + (imm if op == 0x0D else simm)) & 0xFFFFFFFF)
        if op in (0x09, 0x0A, 0x0B, 0x0D):
            immediates.add(imm)
    return immediates, addresses


# ---------------------------------------------------------------------------------------------- check


def load_cards(path):
    """card id -> (English name, properties) using tools/cardinfo.py."""
    spec = importlib.util.spec_from_file_location("re_cardinfo", Path(__file__).resolve().parent / "cardinfo.py")
    cardinfo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cardinfo)
    info = cardinfo.CardInfo(Path(path).read_bytes(), "E")
    out = {}
    for i in range(1, info.count):
        props = info.properties(i)
        out[props["id"]] = (info.name(i), props)
    return out


FUSION_KINDS = (5, 7)
RITUAL_KINDS = (9, 11)
SPELL_KIND, RITUAL_ICON = 27, 6


def check(module, cards=None):
    """Structural checks, plus card-database checks when `cards` (id -> (name, properties)) is given.
    Returns a list of problems."""
    problems = []
    rows = recipes(module)
    seen = set()
    for r in rows:
        label = f"recipe {r.index} ({r.fusion:#06x})"
        if not FIRST_CARD <= r.fusion <= LAST_CARD:
            problems.append(f"{label}: fusion id out of range")
        if r.fusion in seen:
            problems.append(f"{label}: duplicate fusion id")
        seen.add(r.fusion)
        if r.fusion in HARDCODED:
            problems.append(f"{label}: also hard-coded in the code")
        if 0 in r.materials:
            problems.append(f"{label}: empty material code before the last")
        expected = 2 if r.index < THREE_MATERIAL_FIRST else 3
        if len(r.materials) != expected:
            problems.append(f"{label}: {len(r.materials)} materials, layout expects {expected}")
        for code in r.materials:
            if code < GENERIC_LIMIT:
                if code not in MATERIAL_CODES:
                    problems.append(f"{label}: unknown generic code {code:#x}")
            elif not FIRST_CARD <= code <= LAST_CARD:
                problems.append(f"{label}: material {code:#x} is neither a generic code nor a card id")
    # the table has no terminator; the half-word after it must not look like another recipe
    after, = module.halves(RECIPES + 8 * RECIPE_COUNT, 1)
    if FIRST_CARD <= after <= LAST_CARD:
        problems.append(f"half-word after the table ({after:#x}) looks like a card id: is the count right?")
    try:
        table = rituals(module)
    except ValueError as error:
        problems.append(str(error))
        table = []
    for r in table:
        label = f"ritual {r.index} ({r.monster:#06x})"
        if not (FIRST_CARD <= r.monster <= LAST_CARD and FIRST_CARD <= r.spell <= LAST_CARD):
            problems.append(f"{label}: id out of range")
        if not 1 <= r.level <= 12:
            problems.append(f"{label}: level total {r.level} out of range")
    for address, name, size, target, constants in CONSUMERS:
        immediates, refs = code_facts(module, address, size)
        if target not in refs:
            problems.append(f"{name} ({address:#010x}) does not reference {target:#010x}")
        for c in constants:
            if c not in immediates:
                problems.append(f"{name} ({address:#010x}) lacks the constant {c:#x}")
    if cards is not None:
        problems += check_cards(rows, table, cards)
    return problems


def check_cards(rows, table, cards):
    problems = []

    def kind(card_id):
        return cards[card_id][1]["kind"]

    for fusion, codes in [(r.fusion, r.materials) for r in rows] + list(HARDCODED.items()):
        if fusion not in cards:
            problems.append(f"fusion {fusion:#06x} has no cardinfo record")
        elif kind(fusion) not in FUSION_KINDS:
            problems.append(f"fusion {fusion:#06x} ({cards[fusion][0]}) is not a Fusion monster")
        for code in codes:
            if code >= GENERIC_LIMIT and code not in cards:
                problems.append(f"fusion {fusion:#06x}: material {code:#06x} has no cardinfo record")
    for r in table:
        if r.monster not in cards or r.spell not in cards:
            problems.append(f"ritual {r.index}: id without cardinfo record")
            continue
        if kind(r.monster) not in RITUAL_KINDS:
            problems.append(f"ritual {r.index}: {r.monster:#06x} is not a Ritual monster")
        spell = cards[r.spell][1]
        if spell["kind"] != SPELL_KIND or spell["icon"] != RITUAL_ICON:
            problems.append(f"ritual {r.index}: {r.spell:#06x} is not a Ritual Spell")
        if cards[r.monster][1]["level"] != r.level:
            problems.append(f"ritual {r.index}: level total {r.level} differs from the monster's Level")
    return problems


def summary(module, cards=None):
    rows = recipes(module)
    codes = collections.Counter(c for r in rows for c in r.materials)
    generic = sum(n for c, n in codes.items() if c < GENERIC_LIMIT)
    three = sum(1 for r in rows if len(r.materials) == 3)
    table = rituals(module)
    lines = [f"fusion recipes: {len(rows)} ({len(rows) - three} with 2 materials, {three} with 3); "
             f"{sum(codes.values())} material slots, {generic} generic ({len([c for c in codes if c < GENERIC_LIMIT])} "
             f"distinct codes); {len(HARDCODED)} Fusions hard-coded in the code",
             f"ritual table: {len(table)} records, {len({r.spell for r in table})} distinct spells"]
    if cards is not None:
        fusions = {i for i, (_, p) in cards.items() if p["kind"] in FUSION_KINDS}
        known = {r.fusion for r in rows} | set(HARDCODED)
        lines.append(f"cardinfo: {len(fusions & known)} of {len(fusions)} Fusion monsters have a recipe; "
                     f"{len(fusions - known)} have none (summoned by card-specific code or not at all)")
    return lines


# ---------------------------------------------------------------------------------------------- output


def recipe_rows(module, cards=None):
    out = []
    for r in recipes(module):
        name = cards.get(r.fusion, ("",))[0] if cards else ""
        row = {"index": r.index, "address": f"{r.address:#010x}", "fusion_id": f"{r.fusion:#06x}", "fusion": name,
               "count": len(r.materials), "source": "table"}
        for k in range(3):
            code = r.materials[k] if k < len(r.materials) else 0
            row[f"code{k}"] = f"{code:#06x}" if code else ""
            row[f"material{k}"] = describe_code(code, cards) if code else ""
        out.append(row)
    for fusion, codes in HARDCODED.items():
        name = cards.get(fusion, ("",))[0] if cards else ""
        row = {"index": "", "address": "", "fusion_id": f"{fusion:#06x}", "fusion": name, "count": len(codes),
               "source": "code"}
        for k in range(3):
            row[f"code{k}"] = " ".join(f"{c:#06x}" for c in codes[k::3])
            row[f"material{k}"] = "; ".join(describe_code(c, cards) for c in codes[k::3])
        out.append(row)
    return out


def ritual_rows(module, cards=None):
    cards = cards or {}
    return [{"index": r.index, "address": f"{r.address:#010x}", "monster_id": f"{r.monster:#06x}",
             "monster": cards.get(r.monster, ("",))[0], "spell_id": f"{r.spell:#06x}",
             "spell": cards.get(r.spell, ("",))[0], "level_total": r.level} for r in rituals(module)]


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
    parser = argparse.ArgumentParser(description="List and check the fusion recipe and ritual tables of rel_duel_eng.prx.")
    parser.add_argument("prx", type=Path, help="gmodule/rel_duel_eng.prx")
    parser.add_argument("command", nargs="?", choices=("recipes", "rituals", "check"), default="recipes")
    parser.add_argument("--check", action="store_true", help="same as the check command")
    parser.add_argument("--cardinfo", type=Path, help="duelsys/cardinfo_eng.ehp: card names and id checks")
    parser.add_argument("-o", "--output", type=Path, help="CSV file (keep it under extracted/)")
    args = parser.parse_args(argv)
    module = Module(args.prx.read_bytes())
    cards = load_cards(args.cardinfo) if args.cardinfo else None
    if args.check or args.command == "check":
        problems = check(module, cards)
        for p in problems:
            print("problem:", p, file=sys.stderr)
        if problems:
            print(f"{len(problems)} problem(s)")
            return 1
        for line in summary(module, cards):
            print(line)
        print("ok")
        return 0
    rows = recipe_rows(module, cards) if args.command == "recipes" else ritual_rows(module, cards)
    write_csv(rows, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
