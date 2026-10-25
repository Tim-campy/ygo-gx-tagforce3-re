#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read and check the game's deck data. See docs/formats/deck.md.

  decks.py recipes  <SYSDIR>/BOOT.BIN             the 661 built-in deck recipes (RCP%03d.ydc) and their owners
  decks.py samecard <USRDIR>/deck/all_e.ehp       sameCardTbl.dat and fileTbl.dat
  decks.py tutorial <USRDIR>/deck/tutorial.ehp    the deck-tutorial scripts (deck_tutorial%02d.bin)

`--check` runs the structural checks and prints a summary; otherwise the data is written as CSV
(stdout or -o FILE). The output is game data: keep it under extracted/, never in git.
"""

import argparse
import csv
import importlib.util
import struct
import sys
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
    parser.add_argument("table", choices=("recipes", "samecard", "tutorial"))
    parser.add_argument("file", type=Path, help="BOOT.BIN, deck/all_<l>.ehp or deck/tutorial.ehp")
    parser.add_argument("-o", "--output", type=Path, help="write CSV here (keep it out of git)")
    parser.add_argument("--check", action="store_true", help="only run the structural checks")
    parser.add_argument("--cardinfo", type=Path, help="duelsys/cardinfo_eng.ehp: check ids against the real database")
    parser.add_argument("--lang", default="e", help="recipe-name language for CSV output (e f g i j s)")
    args = parser.parse_args(argv)

    data = args.file.read_bytes()
    known, samepict = card_tools(args.cardinfo)
    rows = []
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
