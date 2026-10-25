#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Export game tables that live inside executables. See docs/formats/packs.md and docs/formats/limit-list.md.

  tables.py packs  <USRDIR>/gmodule/rel_shop.prx   the 48 booster packs and their four rarity tiers
  tables.py limits <SYSDIR>/BOOT.BIN               the built-in forbidden/limited list

Output is CSV on stdout (or -o FILE); it is game data, so keep it under extracted/, never in git.
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
    parser.add_argument("table", choices=("packs", "limits"))
    parser.add_argument("file", type=Path, help="rel_shop.prx for packs, BOOT.BIN for limits")
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
