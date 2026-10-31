#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read and check the game's deck data. See docs/formats/deck.md.

  decks.py recipes  <SYSDIR>/BOOT.BIN             the 661 built-in deck recipes (RCP%03d.ydc) and their owners
  decks.py owners   <SYSDIR>/BOOT.BIN [--story <USRDIR>/script/story_scr_b.ehp]
                                                  owner, evidence and game use of every recipe 0-660 (JSON)
  decks.py samecard <USRDIR>/deck/all_e.ehp       sameCardTbl.dat and fileTbl.dat
  decks.py tutorial <USRDIR>/deck/tutorial.ehp    the deck-tutorial scripts (deck_tutorial%02d.bin)

`--check` runs the structural checks and prints a summary; otherwise the data is written as CSV (JSON for
`owners`) to stdout or -o FILE. The output is game data: keep it under extracted/, never in git.
"""

import argparse
import csv
import importlib.util
import json
import struct
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name):
    spec = importlib.util.spec_from_file_location("re_" + name, HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ehp = _load("ehp")
tables = _load("tables")

BOOT_BASE = 0x08804000
RECIPE_ARCHIVE = 0x088D77E0  # embedded EHP holding RCP000.ydc ... and recipe_name_<l>.bin
OWNER_TABLE = 0x08915F28  # 126 x {u32 owner, u32 first recipe, u32 recipe count, u32 0}, sorted by owner
OWNER_COUNT = 126
LEVEL_TABLE = 0x089143F0  # u16 per named recipe (462); deck_get_recipe_level
LEVEL_COUNT = 462
VARIANT_TABLE = 0x08916730  # 67 x {u32 owner, u32 stage, u32 variant}
VARIANT_COUNT = 67

# deck_load_recipe (0x0885c3dc) rejects a recipe whose counts exceed these and clears the deck instead.
MAIN_MAX, EXTRA_MAX, SIDE_MAX = 60, 15, 15
YDC_HEADER = 8
YDC_VERSION = 1

# Deck-tutorial script: opcode -> total instruction length in bytes (opcode included).
TUTORIAL_LENGTHS = {0x01: 9, 0x02: 7, 0x03: 1, 0x04: 5, 0x05: 3, 0x06: 1, 0x07: 5, 0x08: 1, 0x09: 9, 0x0A: 5,
                    0x0B: 3, 0x0C: 1, 0x0D: 3, 0x0E: 1, 0x0F: 9, 0x10: 5, 0x11: 1, 0x12: 1, 0x13: 3, 0x14: 7,
                    0x15: 1, 0x16: 9, 0x17: 1}
TUTORIAL_END = 0x17
TUTORIAL_STRING_ARG = {0x01: 0, 0x02: 0, 0x04: 0, 0x0F: 2, 0x13: 0}  # opcode -> byte offset of a u16 strTbl index
TUTORIAL_CARD_OP = 0x0B  # argument is a u16 card id


# --- YDC deck recipe -------------------------------------------------------------------------------------------

def ydc_parse(blob):
    """Return {'header', 'main', 'extra', 'side'} for a .ydc deck (three u16-counted lists of u16 card ids)."""
    if len(blob) < YDC_HEADER + 6:
        raise ValueError("ydc too short")
    lists = []
    pos = YDC_HEADER
    for _ in range(3):
        if pos + 2 > len(blob):
            raise ValueError("ydc ends before a list count")
        count, = struct.unpack_from("<H", blob, pos)
        pos += 2
        if pos + 2 * count > len(blob):
            raise ValueError("ydc list runs past the end")
        lists.append(list(struct.unpack_from(f"<{count}H", blob, pos)))
        pos += 2 * count
    if pos != len(blob):
        raise ValueError(f"{len(blob) - pos} trailing bytes after the side deck")
    return {"header": bytes(blob[:YDC_HEADER]), "main": lists[0], "extra": lists[1], "side": lists[2]}


def ydc_build(deck):
    header = deck.get("header") or bytes([YDC_VERSION, 0xCC, 0xCC, 0xCC, 0, 0, 0, 0])
    out = bytearray(header)
    for key in ("main", "extra", "side"):
        ids = deck[key]
        out += struct.pack(f"<H{len(ids)}H", len(ids), *ids)
    return bytes(out)


def ydc_check(deck, ids_known=None, name="deck"):
    problems = []
    if deck["header"][0] != YDC_VERSION:
        problems.append(f"{name}: header byte 0 is {deck['header'][0]}, expected {YDC_VERSION}")
    for key, limit in (("main", MAIN_MAX), ("extra", EXTRA_MAX), ("side", SIDE_MAX)):
        if len(deck[key]) > limit:
            problems.append(f"{name}: {key} has {len(deck[key])} cards, the loader accepts at most {limit}")
        if ids_known is not None:
            unknown = [i for i in deck[key] if i not in ids_known]
            if unknown:
                problems.append(f"{name}: unknown card ids in {key}: {unknown[:5]}")
    return problems


# --- tables in BOOT.BIN ----------------------------------------------------------------------------------------

def string_table(blob):
    """Konami string table: u32 count, u32 offset-table position, u32 string base; u32 offsets; UTF-16LE strings."""
    count, table, base = struct.unpack_from("<3I", blob, 0)
    strings = []
    for offset in struct.unpack_from(f"<{count}I", blob, table):
        start = end = base + offset
        while end + 1 < len(blob) and blob[end:end + 2] != b"\0\0":
            end += 2
        strings.append(blob[start:end].decode("utf-16-le"))
    return strings


def find_recipe_archive(data):
    """Locate the embedded EHP whose members are RCP%03d.ydc (by content, so it also works on other builds)."""
    pos = data.find(ehp.MAGIC)
    while pos != -1:
        total, = struct.unpack_from("<I", data, pos + 4)
        try:
            members = ehp.parse(data[pos:pos + total])
        except (ValueError, struct.error, UnicodeDecodeError):
            members = []
        if any(name == "RCP000.ydc" for name, _ in members):
            return pos, members
        pos = data.find(ehp.MAGIC, pos + 4)
    raise ValueError("no embedded archive with RCP000.ydc")


def parse_records(data, offset, count, fmt):
    record = struct.Struct(fmt)
    return [record.unpack_from(data, offset + record.size * k) for k in range(count)]


def read_recipes(boot):
    """All recipe data from BOOT.BIN: decks, names per language, owners, levels and variant table."""
    sections = tables.elf_sections(boot)
    offset, members = find_recipe_archive(boot)
    by_name = dict(members)
    decks = []
    index = 0
    while f"RCP{index:03d}.ydc" in by_name:
        decks.append(ydc_parse(by_name[f"RCP{index:03d}.ydc"]))
        index += 1
    names = {name[len("recipe_name_"):-4]: string_table(blob)
             for name, blob in members if name.startswith("recipe_name_")}
    owners = parse_records(boot, tables.to_offset(sections, OWNER_TABLE, BOOT_BASE), OWNER_COUNT, "<4I")
    levels = list(struct.unpack_from(f"<{LEVEL_COUNT}H", boot, tables.to_offset(sections, LEVEL_TABLE, BOOT_BASE)))
    variants = parse_records(boot, tables.to_offset(sections, VARIANT_TABLE, BOOT_BASE), VARIANT_COUNT, "<3I")
    return {"archive_offset": offset, "member_count": len(members), "decks": decks, "names": names,
            "owners": owners, "levels": levels, "variants": variants}


def owner_of(owners):
    """recipe index -> owner id, from the owner table."""
    result = {}
    for owner, first, count, _ in owners:
        for recipe in range(first, first + count):
            result[recipe] = owner
    return result


def check_recipes(recipes, ids_known=None):
    problems = []
    decks = recipes["decks"]
    for index, deck in enumerate(decks):
        problems += ydc_check(deck, ids_known, f"RCP{index:03d}")
    if recipes["member_count"] != len(decks) + len(recipes["names"]):
        problems.append("recipe archive holds members other than RCP*.ydc and recipe_name_*.bin")
    owners = recipes["owners"]
    keys = [o[0] for o in owners]
    if keys != sorted(keys) or len(set(keys)) != len(keys):
        problems.append("owner table is not sorted by unique owner id (the game binary-searches it)")
    expected = 0
    for owner, first, count, zero in owners:
        if first != expected or zero != 0:
            problems.append(f"owner {owner}: recipes {first}+{count} do not follow on from {expected}")
        expected = first + count
    named = len(next(iter(recipes["names"].values()), []))
    for lang, names in recipes["names"].items():
        if len(names) != named:
            problems.append(f"recipe_name_{lang}: {len(names)} names, expected {named}")
    if expected > named:
        problems.append(f"owner table covers {expected} recipes but only {named} have names")
    if any(not 1 <= v <= 10 for v in recipes["levels"]):
        problems.append("recipe level outside 1-10")
    by_owner = {o[0]: o for o in owners}
    for owner, stage, variant in recipes["variants"]:
        if owner not in by_owner or variant >= by_owner[owner][2]:
            problems.append(f"variant table: owner {owner} stage {stage} variant {variant} has no recipe")
    return problems


# --- recipe owners and users -------------------------------------------------------------------------------------

# Duel set-up records (0x1ac bytes, four per set-up) carry a u16 "recipe" at +0x8. FUN_08836358 (BOOT, called by
# rel_story, rel_title, rel_tutorial, rel_underground and rel_debug_menu) loads RCP<n>.ydc only for n < 462; these
# five values select another deck source instead, and every value >= 467 leaves the duellist without a deck.
SETUP_CODES = {
    462: "keep the deck already stored in the set-up record",
    463: "the player's saved deck number +0xa (save state +0x20 + 0x174 * n)",
    464: "no deck (cleared)",
    465: "the player's current deck (deck slot 1)",
    466: "the duellist's own deck slot (slot = character +0x0)",
}
SETUP_FIRST_REJECTED = 467
# Recipes 462-660 repeat the decks of owners 87-126 in five-slot blocks: block k = recipes 461 + 5k .. 465 + 5k
# belongs to owner 87 + k (the first block starts inside the named range, so owner 87 has only 462 and 463).
DRAFT_FIRST_RECIPE, DRAFT_FIRST_OWNER, DRAFT_STRIDE = 461, 87, 5
PLACEHOLDER_REPEATS = 3  # an unnamed deck body seen this often in 462-660 is a filler, not a real deck
STORY_DUEL_OPCODES = {50119: "duel_single", 50120: "duel_tag_opponent_a", 50121: "duel_tag_opponent_b"}
STORY_NPC_DECK = 50162  # npc_deck(char, n): during an event the character duels with deck_get_owner_recipe(char, n)


def deck_body(deck):
    """All card ids of a deck (main, extra and side) as a sorted tuple: equal tuples are the same deck."""
    return tuple(sorted(deck["main"] + deck["extra"] + deck["side"]))


def similarity(a, b):
    """Multiset Jaccard index of two deck bodies (1.0 = same cards with the same counts)."""
    left, right = Counter(a), Counter(b)
    union = sum((left | right).values())
    return sum((left & right).values()) / union if union else 0.0


def story_opponents(events):
    """From an EveB program (story.Events): {char: number of duel set-ups naming it} and the npc_deck (char, n)."""
    duels, npc_decks = Counter(), Counter()
    for _, _, opcode, a1, a2, _, _ in events.rows():
        if opcode in STORY_DUEL_OPCODES:
            duels[a1] += 1
        elif opcode == STORY_NPC_DECK:
            npc_decks[(a1, a2)] += 1
    return duels, npc_decks


def recipe_owners(recipes, story=None):
    """One entry per recipe: owner, the evidence for it, how the game uses the recipe, and a confidence."""
    decks = recipes["decks"]
    owners = recipes["owners"]
    by_owner = {owner: (first, count) for owner, first, count, _ in owners}
    owner = owner_of(owners)
    named = len(owner)
    bodies = [deck_body(d) for d in decks]
    first_copy = {}
    for index, body in enumerate(bodies):
        first_copy.setdefault(body, index)
    unnamed = Counter(bodies[named:])
    stages = {}
    for who, stage, variant in recipes["variants"]:
        if who in by_owner:
            stages.setdefault(by_owner[who][0] + variant, []).append(stage)
    duels, npc_decks = story if story else (Counter(), Counter())
    entries = []
    for index, body in enumerate(bodies):
        entry = {"recipe": index, "owner": None, "role": None, "evidence": [], "confidence": None,
                 "loaded_by_game": index < named, "setup_code": SETUP_CODES.get(index)}
        if index in owner:
            who = owner[index]
            entry.update(owner=who, role="starting_deck" if index == 0 else "character", confidence="high")
            entry["evidence"].append("owner_table")
            entry["level"] = recipes["levels"][index] if index < len(recipes["levels"]) else None
            entry["evidence"].append("underground_level_pool")  # rel_underground 0xde88 draws among 0..461 by level
            if index in stages:
                entry["variant_stages"] = sorted(stages[index])
                entry["evidence"].append("variant_table")
            n = index - by_owner[who][0]
            if duels.get(who):
                entry["story_duels"] = duels[who]
                entry["evidence"].append("story_duel_opponent")
            if npc_decks.get((who, n)):
                entry["evidence"].append("story_npc_deck")
        else:
            block, slot = divmod(index - DRAFT_FIRST_RECIPE, DRAFT_STRIDE)
            who = DRAFT_FIRST_OWNER + block
            entry.update(owner=who if who in by_owner else None, draft_slot=slot)
            if entry["owner"] is not None:
                entry["evidence"].append("draft_block")
            best = max(range(named), key=lambda j: similarity(body, bodies[j]))
            score = similarity(body, bodies[best])
            entry["nearest_named"] = {"recipe": best, "owner": owner[best], "similarity": round(score, 2)}
            if first_copy[body] != index:
                entry["copy_of"] = first_copy[body]
            if unnamed[body] >= PLACEHOLDER_REPEATS:
                entry.update(role="placeholder", confidence="low")
            else:
                entry["role"] = "draft"
                agrees = owner[best] == entry["owner"]
                if agrees:
                    entry["evidence"].append("content_similarity")
                entry["confidence"] = "medium" if agrees and score >= 0.5 else "low"
        entries.append(entry)
    return entries


def check_owners(entries, recipes, story=None):
    """Structural checks of the owner mapping; returns (problems, summary)."""
    problems = []
    named = sum(count for _, _, count, _ in recipes["owners"])
    by_owner = {o[0] for o in recipes["owners"]}
    for entry in entries:
        if entry["recipe"] < named and entry["owner"] is None:
            problems.append(f"recipe {entry['recipe']}: inside the owner table but without owner")
        if entry["recipe"] >= named and entry["owner"] is None:
            problems.append(f"recipe {entry['recipe']}: its draft block names owner outside the owner table")
    if set(SETUP_CODES) != set(range(named, SETUP_FIRST_REJECTED)):
        problems.append(f"the set-up codes no longer start right after the {named} owned recipes")
    drafts = [e for e in entries if e["role"] == "draft"]
    agree = [e for e in drafts if "content_similarity" in e["evidence"]]
    if drafts and len(agree) * 2 < len(drafts):
        problems.append(f"only {len(agree)} of {len(drafts)} unnamed decks resemble a deck of their block's owner")
    duels, _ = story if story else (Counter(), None)
    missing = sorted(c for c in duels if c not in by_owner)
    if missing:
        problems.append(f"story duel opponents without a recipe owner: {missing}")
    tail = [e for e in entries if e["recipe"] >= named]
    confidence = Counter(e["confidence"] for e in drafts)
    placeholders = sum(e["role"] == "placeholder" for e in tail)
    with_owner = sum(e["owner"] is not None for e in entries)
    span = f"{tail[0]['recipe']}-{tail[-1]['recipe']}" if tail else "none"
    summary = (f"ok: {with_owner} of {len(entries)} recipes have an owner: {named} from the owner table (high); "
               f"{len(tail)} unnamed ({span}) by draft block: {len(drafts)} decks, {len(agree)} resembling a deck "
               f"of the same owner (medium {confidence['medium']}, low {confidence['low']}), {placeholders} "
               f"placeholders (low); no unnamed recipe is loaded by the game; set-up codes "
               f"{min(SETUP_CODES)}-{max(SETUP_CODES)}")
    if story and not missing:
        summary += f"; {len(duels)} story duel opponents, all in the owner table"
    return problems, summary


# --- deck/all_<l>.ehp ------------------------------------------------------------------------------------------

def read_same_card(blob):
    """sameCardTbl.dat: u32 count, then count x (u16 card id, u16 alternative artwork number 1..n)."""
    count, = struct.unpack_from("<I", blob, 0)
    if 4 + 4 * count != len(blob):
        raise ValueError("sameCardTbl size does not match its count")
    return [struct.unpack_from("<HH", blob, 4 + 4 * k) for k in range(count)]


def read_file_table(blob):
    """fileTbl.dat: u16 count, then count u16 card ids; slot 0 holds 0, slots 1.. the non-token cards by id."""
    count, = struct.unpack_from("<H", blob, 0)
    if 2 + 2 * count != len(blob):
        raise ValueError("fileTbl size does not match its count")
    return list(struct.unpack_from(f"<{count}H", blob, 2))


def check_same_card(pairs, samepict=None):
    """Each card's numbers must run 1..n; with CARD_SamePict as {card id: n} they must match it."""
    problems = []
    runs = {}
    for card, number in pairs:
        if number != runs.get(card, 0) + 1:
            problems.append(f"card {card}: artwork {number} out of sequence")
        runs[card] = number
    if samepict is not None:
        for card, n in runs.items():
            if samepict.get(card) != n:
                problems.append(f"card {card}: {n} artworks here, CARD_SamePict says {samepict.get(card)}")
    return problems, runs


# --- deck_tutorial%02d.bin -------------------------------------------------------------------------------------

def tutorial_parse(blob):
    """Split a deck-tutorial script into (offset, opcode, argument bytes); it must end with opcode 0x17."""
    ops = []
    pos = 0
    while pos < len(blob):
        op = blob[pos]
        if op not in TUTORIAL_LENGTHS:
            raise ValueError(f"unknown opcode {op:#04x} at {pos:#x}")
        length = TUTORIAL_LENGTHS[op]
        if pos + length > len(blob):
            raise ValueError(f"opcode {op:#04x} at {pos:#x} runs past the end")
        ops.append((pos, op, bytes(blob[pos + 1:pos + length])))
        pos += length
        if op == TUTORIAL_END:
            break
    if pos != len(blob) or not ops or ops[-1][1] != TUTORIAL_END:
        raise ValueError("script does not end exactly at its 0x17 opcode")
    return ops


def tutorial_strings(ops):
    return [struct.unpack_from("<H", args, TUTORIAL_STRING_ARG[op])[0] for _, op, args in ops if op in TUTORIAL_STRING_ARG]


# --- command line ----------------------------------------------------------------------------------------------

def card_tools(path):
    if path is None:
        return None, None
    cardinfo = _load("cardinfo")
    archive = path.read_bytes()
    info = cardinfo.CardInfo(archive, "E")
    known = {info.properties(i)["id"] for i in range(1, info.count)}
    members = dict(ehp.parse(archive))
    samepict = None
    name = next((n for n in members if n.startswith("CARD_SamePict_")), None)
    if name:
        blob = members[name]
        count, = struct.unpack_from("<H", blob, 0)
        samepict = {info.properties(index)["id"]: n
                    for index, n in (struct.unpack_from("<HH", blob, 2 + 4 * k) for k in range(count))}
    return known, samepict


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read the game's deck recipes, artwork tables and tutorial scripts.")
    parser.add_argument("table", choices=("recipes", "owners", "samecard", "tutorial"))
    parser.add_argument("file", type=Path, help="BOOT.BIN, deck/all_<l>.ehp or deck/tutorial.ehp")
    parser.add_argument("-o", "--output", type=Path, help="write CSV (owners: JSON) here (keep it out of git)")
    parser.add_argument("--check", action="store_true", help="only run the structural checks")
    parser.add_argument("--cardinfo", type=Path, help="duelsys/cardinfo_eng.ehp: check ids against the real database")
    parser.add_argument("--lang", default="e", help="recipe-name language for CSV output (e f g i j s)")
    parser.add_argument("--story", type=Path, help="owners: script/story_scr_b.ehp, to mark story duel opponents")
    args = parser.parse_args(argv)

    data = args.file.read_bytes()
    known, samepict = card_tools(args.cardinfo)
    rows = []
    if args.table == "owners":
        recipes = read_recipes(data)
        story = story_opponents(_load("story").Events(args.story.read_bytes())) if args.story else None
        entries = recipe_owners(recipes, story)
        problems, summary = check_owners(entries, recipes, story)
        problems = check_recipes(recipes, known) + problems
        if args.check:
            print("\n".join(problems) if problems else summary)
            return 1 if problems else 0
        out = open(args.output, "w", encoding="utf-8") if args.output else sys.stdout
        try:
            json.dump(entries, out, indent=1)
            out.write("\n")
        finally:
            if args.output:
                out.close()
        return 0
    if args.table == "recipes":
        recipes = read_recipes(data)
        problems = check_recipes(recipes, known)
        owners = owner_of(recipes["owners"])
        names = recipes["names"].get(args.lang, [])
        for index, deck in enumerate(recipes["decks"]):
            for section in ("main", "extra", "side"):
                for card in deck[section]:
                    rows.append({"recipe": index, "owner": owners.get(index, ""),
                                 "name": names[index] if index < len(names) else "",
                                 "level": recipes["levels"][index] if index < len(recipes["levels"]) else "",
                                 "section": section, "card_id": card})
        decks = recipes["decks"]
        summary = (f"ok: {len(decks)} recipes ({sum(len(d['main']) for d in decks)} main, "
                   f"{sum(len(d['extra']) for d in decks)} extra, {sum(len(d['side']) for d in decks)} side cards), "
                   f"{len(recipes['owners'])} owners covering {len(owners)} recipes, "
                   f"{len(recipes['names'])} name tables")
    elif args.table == "samecard":
        members = dict(ehp.parse(data))
        pairs = read_same_card(members["sameCardTbl.dat"])
        files = read_file_table(members["fileTbl.dat"])
        problems, runs = check_same_card(pairs, samepict)
        if files[0] != 0 or files[1:] != sorted(set(files[1:])):
            problems.append("fileTbl: slot 0 is not 0 or the ids are not strictly ascending")
        if known is not None and any(i not in known for i in files[1:]):
            problems.append("fileTbl: unknown card id")
        rows = [{"table": "sameCardTbl", "slot": k, "card_id": c, "value": n} for k, (c, n) in enumerate(pairs)]
        rows += [{"table": "fileTbl", "slot": k, "card_id": c, "value": ""} for k, c in enumerate(files)]
        summary = f"ok: {len(pairs)} alternative artworks for {len(runs)} cards; fileTbl has {len(files)} slots"
    else:
        members = dict(ehp.parse(data))
        problems = []
        scripts = sorted(n for n in members if n.startswith("deck_tutorial") and n.endswith(".bin"))
        string_count = None
        if "strTbl_e.bin" in members:
            string_count, = struct.unpack_from("<I", members["strTbl_e.bin"], 0)
        used = []
        total_ops = 0
        for name in scripts:
            try:
                ops = tutorial_parse(members[name])
            except ValueError as error:
                problems.append(f"{name}: {error}")
                continue
            total_ops += len(ops)
            used += tutorial_strings(ops)
            for offset, op, arguments in ops:
                rows.append({"script": name, "offset": offset, "opcode": f"{op:#04x}", "args": arguments.hex(" ")})
                if op == TUTORIAL_CARD_OP and known is not None:
                    card, = struct.unpack_from("<H", arguments, 0)
                    if card not in known:
                        problems.append(f"{name}: opcode 0x0b at {offset:#x} names unknown card {card}")
        if string_count is not None and any(s >= string_count for s in used):
            problems.append("a script references a string index past strTbl")
        summary = f"ok: {len(scripts)} scripts, {total_ops} instructions, {len(used)} string references"
    if args.check:
        print("\n".join(problems) if problems else summary)
        return 1 if problems else 0
    out = open(args.output, "w", encoding="utf-8", newline="") if args.output else sys.stdout
    try:
        writer = csv.DictWriter(out, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    finally:
        if args.output:
            out.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
