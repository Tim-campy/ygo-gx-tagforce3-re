#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Export game tables that live inside executables. See docs/formats/packs.md and docs/formats/limit-list.md.

  tables.py packs  <USRDIR>/gmodule/rel_shop.prx   the 48 booster packs and their four rarity tiers
  tables.py odds   <USRDIR>/gmodule/rel_shop.prx   per-pack draw odds of the shop (docs/formats/packs.md)
  tables.py limits <SYSDIR>/BOOT.BIN               the built-in forbidden/limited list

Output is CSV on stdout (or -o FILE); it is game data, so keep it under extracted/, never in git.
`odds --check` also replays the shop's draw procedure (draw_pack) on every pack and compares the
outcome with the computed odds.
"""

import argparse
import csv
import struct
import sys
from pathlib import Path

BOOT_BASE = 0x08804000
PACK_TABLE = 0x202C8  # vaddr inside rel_shop.prx
PACK_COUNT = 48
PACK_RECORD = struct.Struct("<III")  # a, b, descriptor vaddr
TIERS = 4
# Draw constants of rel_shop (vaddr; runtime address = 0x090ced00 + vaddr). See docs/formats/packs.md.
RARITY_BOX_TABLE = 0x205FC  # s16[4]: slots of rarity 0..3 in a box of 20 packs (rarity 0 unused): 0, 14, 4, 2
BUY_FACTOR_TABLE = 0x205F0  # s32[3]: packs per purchase mode 0 (single), 1 (shelf stock, runtime), 2 (box)
BOX_SIZE = 20
RARITY_BOX_RESET = (0, 14, 4, 2)  # constants written by the draw function when a box is used up
PREFER_UNOWNED_PACKS = (15, 47)  # packs whose draw favours cards the player does not own
LIMIT_TABLE = 0x08878CB8  # vaddr inside BOOT.BIN
LIMIT_COUNT = 114
LIMIT_NAMES = {0: "forbidden", 1: "limited", 2: "semi-limited", 3: "unlimited"}


def elf_segments(data):
    """PT_LOAD segments as (file offset, vaddr, file size)."""
    phoff, = struct.unpack_from("<I", data, 0x1C)
    phnum, = struct.unpack_from("<H", data, 0x2C)
    segments = []
    for i in range(phnum):
        ptype, off, vaddr, _, filesz, _ = struct.unpack_from("<6I", data, phoff + 32 * i)
        if ptype == 1:
            segments.append((off, vaddr, filesz))
    return segments


def elf_sections(data):
    """Allocated sections as (file offset, vaddr, size); used for BOOT.BIN, whose layout is section-based."""
    shoff, = struct.unpack_from("<I", data, 0x20)
    shentsize, shnum = struct.unpack_from("<HH", data, 0x2E)
    out = []
    for i in range(shnum):
        _, _, flags, addr, off, size = struct.unpack_from("<6I", data, shoff + i * shentsize)
        if flags & 2 and size:
            out.append((off, addr, size))
    return out


def to_offset(regions, vaddr, base=0):
    for off, addr, size in regions:
        if addr <= vaddr - base < addr + size:
            return off + vaddr - base - addr
    raise ValueError(f"address {vaddr:#x} is not in any loaded region")


def read_packs(prx):
    segments = elf_segments(prx)
    packs = []
    for index in range(PACK_COUNT):
        a, b, descriptor = PACK_RECORD.unpack_from(prx, to_offset(segments, PACK_TABLE) + PACK_RECORD.size * index)
        pairs = struct.unpack_from(f"<{2 * TIERS}I", prx, to_offset(segments, descriptor))
        tiers = []
        for tier in range(TIERS):
            address, count = pairs[2 * tier], pairs[2 * tier + 1]
            ids = struct.unpack_from(f"<{count}H", prx, to_offset(segments, address)) if count else ()
            tiers.append(ids)
        packs.append({"pack": index, "a": a, "price": b & 0xFFFF, "flags": b >> 16, "tiers": tiers})
    return packs


def read_draw_constants(prx):
    """(rarity box slots s16[4], purchase factors s32[3]) from rel_shop.prx."""
    segments = elf_segments(prx)
    box = struct.unpack_from("<4h", prx, to_offset(segments, RARITY_BOX_TABLE))
    factors = struct.unpack_from("<3i", prx, to_offset(segments, BUY_FACTOR_TABLE))
    return box, factors


def cards_per_pack(pack):
    """Byte 0 of the record >> 2 (rel_shop 0x090d94dc); bits 0-1 hold the runtime pack state."""
    return (pack["a"] & 0xFF) >> 2


class GameRandom:
    """BOOT.BIN system_rand (0x088101d4): newlib's 64-bit LCG, seeded by srand (0x0881019c) with the
    low word of sceRtcGetCurrentTick at start-up. The shop uses system_rand_shifted() = rand() >> 4."""

    def __init__(self, seed=0):
        self.state = seed & 0xFFFFFFFF

    def rand(self):
        self.state = (self.state * 0x5851F42D4C957F2D + 1) & 0xFFFFFFFFFFFFFFFF
        return (self.state >> 32) & 0x7FFFFFFF

    def shifted(self):
        return self.rand() >> 4


def draw_pack(pack, box, rng, owned=None, is_valid=None, rarity_box=RARITY_BOX_RESET):
    """One booster as rel_shop 0x090d9678 (shop_draw_pack_cards) draws it, with the same order of
    random numbers. pack: a read_packs record; box: the pack's 20 save entries (save pack record +2,
    updated in place); rng: has shifted(); owned(card) -> copies (only read for packs 15 and 47);
    is_valid(card) -> bool (card_db_is_valid). Returns the card ids in the order the shop shows them
    (the rare-slot card last)."""
    pack_index, tiers = pack["pack"], pack["tiers"]
    counts = list(rarity_box)
    used = 0
    while used < BOX_SIZE and 0 < box[used] < 4:
        counts[box[used]] -= 1
        used += 1
    if used >= BOX_SIZE:  # box of 20 used up: start a new one
        box[:] = [0] * BOX_SIZE
        counts[1:] = RARITY_BOX_RESET[1:]
    slots = [3] * counts[3] + [2] * counts[2] + [1] * counts[1]
    rarity = slots[rng.shifted() % len(slots)]
    box[BOX_SIZE - len(slots)] = rarity

    filtered = None
    if pack_index in PREFER_UNOWNED_PACKS and owned is not None:
        filtered = []
        for ids in tiers:
            if not ids:
                filtered.append(None)
                continue
            pool = [c for c in ids if owned(c) < 1]
            if not pool:
                pool = [c for c in ids if owned(c) < 3]
            filtered.append(pool)

    def pick(tier, chance):  # chance: rand % 10 below this takes the filtered list
        pool = filtered[tier] if filtered is not None else None
        if pool is None or not pool or rng.shifted() % 10 >= chance:
            pool = tiers[tier]
        return pool[rng.shifted() % len(pool)]

    out = []
    for tier in range(rarity, -1, -1):  # rare slot: tier `rarity`, falling back to lower tiers
        if tiers[tier]:
            out.append(pick(tier, 5))
            break
    common = next((t for t in range(TIERS) if tiers[t]), None)
    if common is None:
        raise ValueError(f"pack {pack_index} has no cards")
    size = cards_per_pack(pack)
    while len(out) < size:
        card = pick(common, 3)
        while is_valid is not None and not is_valid(card):
            card = pick(common, 3)
        if card not in out:
            out.append(card)
    out[0], out[-1] = out[-1], out[0]
    return out


def pack_odds(pack, rarity_box=RARITY_BOX_RESET):
    """Exact odds of one pack when every card of the pack is owned equally often (always true for
    packs other than 15 and 47). Returns rare-slot tier probabilities (index 0..3, None = no card),
    the common tier, and per tier the chance that a given card of that tier is in the pack."""
    tiers = [len(ids) for ids in pack["tiers"]]
    total = sum(rarity_box[1:])
    common = next(t for t in range(TIERS) if tiers[t])
    size = cards_per_pack(pack)
    rare_tier = {}
    per_card = [0.0] * TIERS
    for rarity in (1, 2, 3):
        p = rarity_box[rarity] / total
        tier = next((t for t in range(rarity, -1, -1) if tiers[t]), None)
        rare_tier[tier] = rare_tier.get(tier, 0.0) + p
        commons = size - (tier is not None)
        if tier is None:
            per_card[common] += p * commons / tiers[common]
        elif tier == common:
            per_card[common] += p * (1 + commons) / tiers[common]
        else:
            per_card[tier] += p / tiers[tier]
            per_card[common] += p * commons / tiers[common]
    return rare_tier, common, per_card


def check_draws(packs, rarity_box, factors, boxes=60, seed=1):
    """Replays draw_pack over `boxes` boxes of 20 per pack: box composition, pack size, no duplicate,
    cards from the pack's pool, and the observed per-tier card counts against pack_odds."""
    problems = []
    if tuple(rarity_box) != RARITY_BOX_RESET:
        problems.append(f"rarity box {tuple(rarity_box)} differs from the reset constants {RARITY_BOX_RESET}")
    if (factors[0], factors[2]) != (1, BOX_SIZE):
        problems.append(f"purchase factors {factors}: expected 1 and {BOX_SIZE}")
    rng = GameRandom(seed)
    for pack in packs:
        size = cards_per_pack(pack)
        tier_of = {c: t for t, ids in enumerate(pack["tiers"]) for c in ids}
        _, common, per_card = pack_odds(pack, rarity_box)
        if len(pack["tiers"][common]) < size:
            problems.append(f"pack {pack['pack']}: common tier smaller than the pack ({size} cards)")
            continue
        box = [0] * BOX_SIZE
        seen = [0] * TIERS
        n = boxes * BOX_SIZE
        for k in range(n):
            cards = draw_pack(pack, box, rng, rarity_box=rarity_box)
            if k % BOX_SIZE == BOX_SIZE - 1 and sorted(box) != sorted([1] * 14 + [2] * 4 + [3] * 2):
                problems.append(f"pack {pack['pack']}: box {box} is not 14/4/2")
            if len(cards) != size or len(set(cards)) != size or any(c not in tier_of for c in cards):
                problems.append(f"pack {pack['pack']}: bad draw {cards}")
                break
            for c in cards:
                seen[tier_of[c]] += 1
        for t in range(TIERS):
            expect = n * per_card[t] * len(pack["tiers"][t])
            if abs(seen[t] - expect) > 6 * max(expect, 1) ** 0.5 + 1:
                problems.append(f"pack {pack['pack']} tier {t + 1}: {seen[t]} cards drawn, {expect:.0f} expected")
    return problems


def odds_rows(packs, rarity_box, factors):
    rows = []
    for pack in packs:
        rare_tier, common, per_card = pack_odds(pack, rarity_box)
        row = {"pack": pack["pack"], "cards_per_pack": cards_per_pack(pack), "price": pack["price"],
               "box_price": pack["price"] * factors[2], "common_tier": common + 1}
        for t in range(TIERS):
            row[f"tier{t + 1}_cards"] = len(pack["tiers"][t])
        for t in range(TIERS):
            row[f"rare_slot_tier{t + 1}"] = round(rare_tier.get(t, 0.0), 4)
        row["rare_slot_empty"] = round(rare_tier.get(None, 0.0), 4)
        for t in range(TIERS):
            row[f"per_card_tier{t + 1}"] = round(per_card[t], 6)
        rows.append(row)
    return rows


def read_limits(boot):
    sections = elf_sections(boot)
    start = to_offset(sections, LIMIT_TABLE, BOOT_BASE)
    return [struct.unpack_from("<HH", boot, start + 4 * k) for k in range(LIMIT_COUNT)]


def known_ids(cardinfo_path):
    """Card ids from a cardinfo archive, or the plain id range when none is given."""
    if cardinfo_path is None:
        return set(range(0xE88, 0x1F3A))
    import importlib.util
    spec = importlib.util.spec_from_file_location("re_cardinfo", Path(__file__).resolve().parent / "cardinfo.py")
    cardinfo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cardinfo)
    info = cardinfo.CardInfo(cardinfo_path.read_bytes(), "E")
    return {info.properties(i)["id"] for i in range(1, info.count)}


def check_packs(packs, ids_known):
    problems = []
    if len(packs) != PACK_COUNT:
        problems.append(f"expected {PACK_COUNT} packs, found {len(packs)}")
    for pack in packs:
        for tier, ids in enumerate(pack["tiers"], 1):
            unknown = [i for i in ids if i not in ids_known]
            if unknown:
                problems.append(f"pack {pack['pack']} tier {tier}: unknown card ids {unknown[:5]}")
    return problems


def check_limits(limits, ids_known):
    problems = []
    if any(i not in ids_known for i, _ in limits):
        problems.append("limit list: unknown card id")
    if any(s not in (0, 1, 2) for _, s in limits):
        problems.append("limit list: status other than 0-2")
    if len({i for i, _ in limits}) != len(limits):
        problems.append("limit list: duplicate id")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description="Export packs or the limit list from the game's executables.")
    parser.add_argument("table", choices=("packs", "odds", "limits"))
    parser.add_argument("file", type=Path, help="rel_shop.prx for packs/odds, BOOT.BIN for limits")
    parser.add_argument("-o", "--output", type=Path, help="write CSV here (keep it out of git)")
    parser.add_argument("--check", action="store_true", help="only run the structural checks")
    parser.add_argument("--cardinfo", type=Path, help="duelsys/cardinfo_eng.ehp: check ids against the real database")
    args = parser.parse_args(argv)

    data = args.file.read_bytes()
    ids_known = known_ids(args.cardinfo)
    if args.table == "packs":
        packs = read_packs(data)
        problems = check_packs(packs, ids_known)
        rows = [{"pack": p["pack"], "a": p["a"], "price": p["price"], "flags": p["flags"], "tier": tier, "card_id": i}
                for p in packs for tier, ids in enumerate(p["tiers"], 1) for i in ids]
        summary = f"ok: {len(packs)} packs, {len(rows)} entries"
    elif args.table == "odds":
        packs = read_packs(data)
        rarity_box, factors = read_draw_constants(data)
        problems = check_packs(packs, ids_known)
        if args.check:
            problems += check_draws(packs, rarity_box, factors)
        rows = odds_rows(packs, rarity_box, factors)
        summary = (f"ok: {len(packs)} packs, rarity box {rarity_box[1]}/{rarity_box[2]}/{rarity_box[3]} per "
                   f"{BOX_SIZE}, {sum(cards_per_pack(p) for p in packs)} cards per round of packs, draws replayed")
    else:
        limits = read_limits(data)
        problems = check_limits(limits, ids_known)
        rows = [{"card_id": i, "status": s, "meaning": LIMIT_NAMES[s]} for i, s in limits]
        summary = f"ok: {len(rows)} restricted cards"
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
