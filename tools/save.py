#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read a plaintext DATA0 save (PPSSPP with save encryption off). See docs/formats/save.md.

  save.py decks      DATA0 [--cardinfo cardinfo_eng.ehp]    deck records (127 slots)
  save.py collection DATA0                                   per-card copies, flags and limit status
  save.py DATA0 --check                                      structural checks

Output is CSV on stdout or -o FILE; it is the player's data, so keep it under extracted/.
"""

import argparse
import csv
import struct
import sys
from pathlib import Path

SAVE_SIZE = 0x20000
DECK_BASE, DECK_SIZE, DECK_COUNT = 0x48C4, 0x16C, 127
NAME = slice(0x10, 0x50)  # UTF-16, NUL-terminated; the rest of the field holds stale bytes
COUNTS = 0x50  # u32 main, side, extra
LISTS = (("main", 0x5C, 60), ("side", 0xD4, 15), ("extra", 0xF2, 15))
COLLECTION_BASE, CARD_RECORDS = 0x11BA4, 3554  # 4 bytes per card-database record index


def decks(data):
    """Yield one dict per deck slot."""
    for slot in range(DECK_COUNT):
        base = DECK_BASE + DECK_SIZE * slot
        _, owner, _, recipe = struct.unpack_from("<4I", data, base)
        counts = struct.unpack_from("<3I", data, base + COUNTS)
        lists = {}
        for (label, offset, capacity), n in zip(LISTS, counts):
            if n > capacity:
                raise ValueError(f"deck {slot}: {label} count {n} exceeds {capacity}")
            lists[label] = list(struct.unpack_from(f"<{n}H", data, base + offset))
        name = data[base + NAME.start:base + NAME.stop].decode("utf-16-le", "replace").split("\0")[0]
        yield {"slot": slot, "owner": owner, "recipe": recipe, "name": name, **lists}


def collection(data):
    """Yield (record index, flags, copies, limit status) for every card-database record."""
    for index in range(CARD_RECORDS):
        flags, copies, status, extra = data[COLLECTION_BASE + 4 * index:COLLECTION_BASE + 4 * index + 4]
        yield index, flags, copies, status & 3, extra


def check(data, valid_ids=None):
    problems = []
    if len(data) != SAVE_SIZE:
        problems.append(f"size {len(data)}, expected {SAVE_SIZE} (an encrypted save is 16 bytes longer)")
        return problems
    for deck in decks(data):
        for label in ("main", "side", "extra"):
            if valid_ids is not None and any(i not in valid_ids for i in deck[label]):
                problems.append(f"deck {deck['slot']}: unknown card id in {label}")
    statuses = {status for _, _, _, status, _ in collection(data)}
    if not statuses <= {0, 1, 2, 3}:
        problems.append("collection: limit status out of range")
    return problems


def known_ids(cardinfo_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("re_cardinfo", Path(__file__).resolve().parent / "cardinfo.py")
    cardinfo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cardinfo)
    info = cardinfo.CardInfo(cardinfo_path.read_bytes(), "E")
    return {info.properties(i)["id"] for i in range(1, info.count)}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read a plaintext Tag Force 3 DATA0 save.")
    parser.add_argument("what", nargs="?", choices=("decks", "collection"))
    parser.add_argument("save", type=Path)
    parser.add_argument("--cardinfo", type=Path, help="duelsys/cardinfo_eng.ehp, to validate card ids")
    parser.add_argument("--check", action="store_true", help="only run the structural checks")
    parser.add_argument("-o", "--output", type=Path, help="write CSV here (keep it out of git)")
    args = parser.parse_args(argv)

    data = args.save.read_bytes()
    if args.check or args.what is None:
        problems = check(data, known_ids(args.cardinfo) if args.cardinfo else None)
        used = sum(1 for d in decks(data) if d["main"])
        owned = sum(1 for _, _, copies, _, _ in collection(data) if copies)
        print("\n".join(problems) if problems else f"ok: {used} non-empty deck slots, {owned} cards owned")
        return 1 if problems else 0
    if args.what == "decks":
        rows = [{"slot": d["slot"], "owner": d["owner"], "recipe": d["recipe"], "name": d["name"],
                 "section": label, "position": n, "card_id": cid}
                for d in decks(data) for label in ("main", "side", "extra") for n, cid in enumerate(d[label])]
        fields = ["slot", "owner", "recipe", "name", "section", "position", "card_id"]
    else:
        rows = [{"index": i, "flags": f, "copies": c, "limit_status": s, "byte3": x}
                for i, f, c, s, x in collection(data) if f or c or s != 3 or x]
        fields = ["index", "flags", "copies", "limit_status", "byte3"]
    out = open(args.output, "w", encoding="utf-8", newline="") if args.output else sys.stdout
    try:
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    finally:
        if args.output:
            out.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
