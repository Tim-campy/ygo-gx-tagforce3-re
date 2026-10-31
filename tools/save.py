#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read a plaintext DATA0 save (PPSSPP with save encryption off). See docs/formats/save.md.

  save.py decks      DATA0 [--cardinfo cardinfo_eng.ehp]    deck records (127 slots)
  save.py collection DATA0                                   per-card copies, flags and limit status
  save.py json       DATA0 [-o FILE]                         every mapped region, decoded, as JSON
  save.py map                                                the offset map (no save needed)
  save.py DATA0 --check                                      structural checks of the save and of the map
  save.py --check                                            only check the map (gap-free, sizes add up)

DATA0 is a byte copy of the game state (`save_get_state()`, 0x1c0ec bytes) padded to 0x20000. The
offset map below covers every byte; regions whose meaning is not established are listed as `unknown`.
Output is the player's data (it includes the console's OpenPSID), so keep it under extracted/.
"""

import argparse
import csv
import json
import struct
import sys
from pathlib import Path

SAVE_SIZE = 0x20000  # DATA0 / save buffer
STATE_SIZE = 0x1C0EC  # save_get_state_size(); the bytes the game copies to and from the buffer
VERSION = 0x30000  # checked by the load path before the copy

STORED_BASE, STORED_SIZE, STORED_COUNT = 0x20, 0x174, 50
DECK_BASE, DECK_SIZE, DECK_COUNT = 0x48C8, 0x16C, 127
DECK_NAME = slice(0x0C, 0x4C)  # UTF-16, NUL-terminated; the rest of the field holds stale bytes
COUNTS = 0x4C  # u32 main, side, extra (the 0xc0-byte deck struct of deck.md starts here)
LISTS = (("main", 0x58, 60), ("side", 0xD0, 15), ("extra", 0xEE, 15))
KEY_CARDS = 0x10C  # u32 count + 46 u16 (deck_get_recipe_card_list)
COLLECTION_BASE, CARD_RECORDS, CARD_CAPACITY = 0x11BA4, 3554, 3600  # 4 bytes per card-database index
CHAR_BASE, CHAR_SIZE, CHAR_COUNT = 0xFE0C, 0x18, 143
RECIPE_BASE, RECIPE_COUNT = 0x10B74, 462
DUEL_BASE, DUEL_CHARS = 0x10F10, 143
RECORDS_BASE = 0x113A4  # save_get_record_table()
PACK_BASE, PACK_SIZE, PACK_COUNT = 0x16604, 0x2A, 48
STORY_BASE = 0x16E14  # save_get_story_block()
CHAR_FLAGS_BASE, CHAR_FLAGS_COUNT = 0x1BF8C, 174

# (offset, size, key, confidence, description). Confidence: H/M/L, or "-" for unknown content.
# Children of a parent region (offsets absolute) are in SUBMAPS and must tile it exactly.
MAP = [
    (0x00000, 0x4, "version", "H", "u32 0x30000; the load path rejects another value"),
    (0x00004, 0x8, "header_unknown", "-", "two u32, no reader or writer found; 0 in the analysed save"),
    (0x0000C, 0x4, "frame_counter", "M", "u32 incremented once per main-loop iteration, saturating (play time in frames)"),
    (0x00010, 0x10, "open_psid", "H", "console OpenPSID written by save_init_new_game; checksum kept in RAM"),
    (STORED_BASE, STORED_SIZE * STORED_COUNT, "stored_decks", "M", "50 stored deck records of 0x174 bytes"),
    (DECK_BASE, DECK_SIZE * DECK_COUNT, "deck_slots", "H", "127 deck slots of 0x16c bytes, slot = character id"),
    (0x0FD5C, 0x32, "player_name", "H", "UTF-16 nickname, at most 8 units, '$' doubled"),
    (0x0FD8E, 0x64, "team_name", "M", "UTF-16 team name"),
    (0x0FDF2, 0x2, "pad_fdf2", "M", "alignment before the u32 fields; no access found"),
    (0x0FDF4, 0x4, "duelist_level", "M", "u32 level - 1 (0..98)"),
    (0x0FDF8, 0x4, "duelist_exp", "M", "u32 EXP"),
    (0x0FDFC, 0x4, "dp", "H", "u32 DP, 0..999,999,999"),
    (0x0FE00, 0x4, "dp_earned", "L", "u32 sum of positive save_add_dp amounts"),
    (0x0FE04, 0x8, "settings", "H", "option bits and nibbles"),
    (CHAR_BASE, CHAR_SIZE * CHAR_COUNT, "characters", "H", "143 character records of 0x18 bytes"),
    (RECIPE_BASE, 2 * RECIPE_COUNT, "recipes", "H", "462 u16, one per deck recipe: bit 0 unlocked, bits 1-8 owner"),
    (DUEL_BASE, 0x494, "duel_record", "H", "win/loss/draw totals, streaks and 143 per-character records"),
    (RECORDS_BASE, 0x800, "record_table", "M", "duel records, minigame high scores, duel-bonus states"),
    (COLLECTION_BASE, 4 * CARD_CAPACITY, "collection", "H", "4 bytes per card-database index; 3554 used, room for 3600"),
    (0x153E4, 0xE10, "flag_bytes", "M", "u8[3600]; 0..69 gallery/card milestones, 70..117 pack first-purchase"),
    (0x161F4, 0x2, "card_list_count", "M", "u16 count (< 100) of the card list below"),
    (0x161F6, 0xC6, "card_list", "M", "u16[99] card ids"),
    (0x162BC, 0xC6, "card_list_state", "M", "u16[99] per-entry state (1-3)"),
    (0x16382, 0x200, "edit_block", "L", "0x200-byte block copied whole by rel_deck, rel_deckswap and rel_select_card"),
    (0x16582, 0x80, "limit_list_name", "M", "UTF-16 name of the active forbidden/limited list"),
    (0x16602, 0x2, "packs_bought", "M", "u16 packs bought in total, capped at 2000"),
    (PACK_BASE, PACK_SIZE * PACK_COUNT, "packs", "H", "48 pack records of 0x2a bytes"),
    (0x16DE4, 0x26, "progress_bytes", "L", "u8[38] that only grow (save_raise_progress_byte)"),
    (0x16E0A, 0x2, "pad_16e0a", "M", "alignment; no access found"),
    (0x16E0C, 0x4, "max_story_cycle", "L", "u32 highest value of partner-word bits 1-3 reached"),
    (0x16E10, 0x1, "byte_16e10", "L", "u8 set by rel_story, read by rel_duel_mgr and rel_title"),
    (0x16E11, 0x1, "byte_16e11", "M", "bit 0: random bit drawn by the weekly pairing; bits 1-7 unused"),
    (0x16E12, 0x2, "partner", "H", "u16 partner word: bit 0 flag, bits 1-3 cycle, 4-11 character, 12-15 variant"),
    (STORY_BASE, 0x42E8, "story_block", "H", "story block of rel_story (offsets in docs/subsystems/world.md)"),
    (0x1B0FC, 0xC, "picture_bits", "M", "bit n = picture n shown (story opcode 50111, ids 1-86)"),
    (0x1B108, 0xD04, "unknown_1b108", "-", "no reader or writer found; 0 in the analysed save"),
    (0x1BE0C, 0x4, "minigame_block_0", "L", "pointer target handed to rel_blackjack"),
    (0x1BE10, 0x4, "minigame_block_1", "L", "pointer target handed to rel_dodge"),
    (0x1BE14, 0x4, "minigame_block_2", "L", "getter without callers"),
    (0x1BE18, 0x30, "minigame_block_3", "M", "12 u32 used by rel_underground; defaults from save_reset_options"),
    (0x1BE48, 0x4, "minigame_block_6", "L", "getter without callers"),
    (0x1BE4C, 0x4, "minigame_block_7", "L", "getter without callers"),
    (0x1BE50, 0xBC, "minigame_block_8", "L", "pointer target handed to rel_throw; size by adjacency"),
    (0x1BF0C, 0xC, "title_words", "M", "3 u32 read and written as a triple by rel_title"),
    (0x1BF18, 0x74, "unknown_1bf18", "-", "no reader or writer found"),
    (CHAR_FLAGS_BASE, 2 * CHAR_FLAGS_COUNT, "character_flags", "H", "2 bytes per character-table row"),
    (0x1C0E8, 0x3, "progress_flags", "H", "single-bit progress flags (shop rules, sandwiches)"),
    (0x1C0EB, 0x1, "pad_1c0eb", "M", "alignment to the 0x1c0ec state size"),
    (STATE_SIZE, SAVE_SIZE - STATE_SIZE, "buffer_tail", "H", "save-buffer bytes after the state; never copied"),
]

SUBMAPS = {
    "record_table": [
        (0x113A4, 0xC4, "record_values", "M", "u32[49] record values; [37] init 599,940, [38] init 999, [40..48] minigame high scores"),
        (0x11468, 0x31, "record_new", "M", "u8[49] 'new record' bits shown and cleared by rel_duelrecord"),
        (0x11499, 0x3, "record_pad", "M", "alignment"),
        (0x1149C, 0x54, "bonus_once", "M", "u8[84] set-once flags of rel_duel_eng (2 once shown by rel_duelrecord)"),
        (0x114F0, 0x6C, "bonus_state", "M", "u8[108] 0 never, 1 first time, 2 again"),
        (0x1155C, 0xD8, "bonus_best", "M", "s16[108] best value per entry"),
        (0x11634, 0x2, "record_selector", "L", "s16 read by rel_duel_eng (switch < 118) and rel_duelrecord"),
        (0x11636, 0x56E, "record_unknown", "-", "no reader or writer found"),
    ],
    "story_block": [
        (0x16E14, 0x3250, "runtime_records", "H", "140 runtime character records of 0x5c bytes"),
        (0x1A064, 0x14, "partner_points_block", "M", "0x14-byte block, +0x10 last partner points seen"),
        (0x1A078, 0x68, "event_queue", "H", "event queue (8 x 12 bytes, ring index, last answer)"),
        (0x1A0E0, 0x16C, "field_state", "H", "field state (location, position, partner, item counters)"),
        (0x1A24C, 0x24, "calendar", "H", "calendar"),
        (0x1A270, 0xA8, "field_save_block", "H", "story stage, chapter step, flags, pairing order"),
        (0x1A318, 0x20, "story_block_3504", "M", "0x20-byte block cleared by rel_story 0xa65c"),
        (0x1A338, 0x4, "story_pad_3524", "-", "not covered by any rel_story block"),
        (0x1A33C, 0x48, "story_block_3528", "M", "0x48-byte block cleared by rel_story 0x9784"),
        (0x1A384, 0xC, "story_block_3570", "M", "0xc-byte block cleared by rel_story 0xa958"),
        (0x1A390, 0x8, "story_block_357c", "M", "8-byte block cleared by rel_story 0xac18"),
        (0x1A398, 0xC, "story_block_3584", "M", "0xc-byte block, words 0 and 1 reset to -1"),
        (0x1A3A4, 0x20, "story_bits_3590", "H", "256 flag bits (rel_story 0x0644 / 0x06b4)"),
        (0x1A3C4, 0x8, "sandwiches_seen", "H", "50-bit sandwich-seen set"),
        (0x1A3CC, 0xD20, "runtime_records_b", "M", "140 records of 0x18 bytes sorted by the character id at +0"),
        (0x1B0EC, 0x10, "flag_block", "H", "story flags 129-192 (+0, +4), system flags 65-128 (+8, +0xc)"),
    ],
}

SETTING_FIELDS = (  # (name, byte, shift, bits)
    ("language", 0, 0, 3), ("option_b0_3", 0, 3, 1), ("option_b0_4", 0, 4, 2), ("option_b0_6", 0, 6, 2),
    ("option_b1_0", 1, 0, 3), ("option_b1_3", 1, 3, 2), ("option_b2_1", 2, 1, 2),
)
OPTION_BITS = ((1, 5), (1, 6), (1, 7), (2, 0), (2, 3), (2, 4))  # save_get_option_flag 0..5


def check_map(regions=MAP, start=0, end=SAVE_SIZE, label="DATA0"):
    """Problems with an offset map: gaps, overlaps, a wrong end; recurses into SUBMAPS."""
    problems, position = [], start
    for offset, size, key, _, _ in regions:
        if offset != position:
            problems.append(f"{label}: {'gap' if offset > position else 'overlap'} at {position:#07x} before {key}")
        if size <= 0:
            problems.append(f"{label}: {key} has size {size}")
        position = offset + size
        if key in SUBMAPS:
            problems += check_map(SUBMAPS[key], offset, offset + size, key)
    if position != end:
        problems.append(f"{label}: map ends at {position:#07x}, expected {end:#07x}")
    keys = [r[2] for r in regions]
    if len(set(keys)) != len(keys):
        problems.append(f"{label}: duplicate keys")
    return problems


def coverage():
    """Bytes per confidence class over the leaves of the map."""
    totals = {}
    for offset, size, key, confidence, _ in MAP:
        for leaf in SUBMAPS.get(key, [(offset, size, key, confidence, "")]):
            totals[leaf[3]] = totals.get(leaf[3], 0) + leaf[1]
    return totals


def u16s(data, offset, count):
    return list(struct.unpack_from(f"<{count}H", data, offset))


def u32s(data, offset, count):
    return list(struct.unpack_from(f"<{count}I", data, offset))


def utf16(data, offset, size):
    return data[offset:offset + size].decode("utf-16-le", "replace").split("\0")[0]


def deck_lists(data, base, label):
    counts = struct.unpack_from("<3I", data, base)
    lists = {}
    for (name, offset, capacity), n in zip(LISTS, counts):
        if n > capacity:
            raise ValueError(f"{label}: {name} count {n} exceeds {capacity}")
        lists[name] = u16s(data, base - COUNTS + offset, n)
    return lists


def key_cards(data, offset):
    n = min(struct.unpack_from("<I", data, offset)[0], 46)
    return u16s(data, offset + 4, n)


def decks(data):
    """Yield one dict per deck slot."""
    for slot in range(DECK_COUNT):
        base = DECK_BASE + DECK_SIZE * slot
        owner, variant, recipe = struct.unpack_from("<3I", data, base)
        name = utf16(data, base + DECK_NAME.start, DECK_NAME.stop - DECK_NAME.start)
        yield {"slot": slot, "owner": owner, "variant": variant, "recipe": recipe, "name": name,
               **deck_lists(data, base + COUNTS, f"deck {slot}")}


def stored_decks(data):
    for n in range(STORED_COUNT):
        base = STORED_BASE + STORED_SIZE * n
        yield {"index": n, "flag": struct.unpack_from("<I", data, base)[0], "name": utf16(data, base + 4, 0x40),
               **deck_lists(data, base + 0x54, f"stored deck {n}"), "key_cards": key_cards(data, base + 0x114)}


def collection(data):
    """Yield (record index, flags, copies, limit status, byte 3) for every card-database record."""
    for index in range(CARD_RECORDS):
        flags, copies, status, extra = data[COLLECTION_BASE + 4 * index:COLLECTION_BASE + 4 * index + 4]
        yield index, flags, copies, status & 3, extra


def bits(data, offset, size, first=0):
    """Numbers of the set bits (bit k of byte j is number first + 8j + k)."""
    return [first + 8 * j + k for j in range(size) for k in range(8) if data[offset + j] >> k & 1]


def nonzero(data, offset, size, width=1):
    fmt = {1: "B", 2: "H", 4: "I"}[width]
    values = struct.unpack_from(f"<{size // width}{fmt}", data, offset)
    return {str(i): v for i, v in enumerate(values) if v}


def decode(data):
    """Every region of the map, decoded (unknown regions as their non-zero bytes)."""
    out = {}
    u32 = lambda offset: struct.unpack_from("<I", data, offset)[0]  # noqa: E731
    out["version"] = hex(u32(0))
    out["header_unknown"] = u32s(data, 4, 2)
    out["frame_counter"] = u32(0xC)
    out["open_psid"] = data[0x10:0x20].hex()
    out["stored_decks"] = [d for d in stored_decks(data) if d["flag"] or d["main"] or d["name"]]
    out["deck_slots"] = [d for d in decks(data) if d["main"] or d["owner"] or d["name"]]
    for offset in range(len(out["deck_slots"])):
        slot = out["deck_slots"][offset]["slot"]
        out["deck_slots"][offset]["key_cards"] = key_cards(data, DECK_BASE + DECK_SIZE * slot + KEY_CARDS)
    out["player_name"] = utf16(data, 0xFD5C, 0x32)
    out["team_name"] = utf16(data, 0xFD8E, 0x64)
    out["duelist_level"] = u32(0xFDF4) + 1
    out["duelist_exp"] = u32(0xFDF8)
    out["dp"] = u32(0xFDFC)
    out["dp_earned"] = u32(0xFE00)
    raw = data[0xFE04:0xFE0C]
    settings = {name: raw[byte] >> shift & ((1 << width) - 1) for name, byte, shift, width in SETTING_FIELDS}
    settings["option_flags"] = [bool(raw[byte] >> bit & 1) for byte, bit in OPTION_BITS]
    settings["nibbles"] = [b & 15 for b in raw[3:8]]
    out["settings"] = settings
    chars = []
    for c in range(CHAR_COUNT):
        base = CHAR_BASE + CHAR_SIZE * c
        count = min(struct.unpack_from("<H", data, base)[0], 10)
        points = struct.unpack_from("<H", data, base + 0x16)[0]
        if count or points:
            chars.append({"character": c, "entries": u16s(data, base + 2, count), "points": points})
    out["characters"] = chars
    recipes = u16s(data, RECIPE_BASE, RECIPE_COUNT)
    out["recipes"] = [{"recipe": r, "owner": v >> 1 & 0xFF} for r, v in enumerate(recipes) if v & 1]
    totals = u32s(data, DUEL_BASE, 7)
    out["duel_record"] = {
        "wins": totals[0], "losses": totals[1], "draws": totals[2], "win_streak": totals[3],
        "best_win_streak": totals[4], "loss_streak": totals[5], "best_loss_streak": totals[6],
        "per_character": [{"character": c, "wins": w, "losses": l, "draws": d}
                          for c in range(DUEL_CHARS)
                          for w, l, d, _ in [struct.unpack_from("<4H", data, DUEL_BASE + 0x1C + 8 * c)] if w or l or d]}
    out["record_table"] = {
        "record_values": u32s(data, 0x113A4, 49), "record_new": nonzero(data, 0x11468, 49),
        "bonus_once": nonzero(data, 0x1149C, 84), "bonus_state": nonzero(data, 0x114F0, 108),
        "bonus_best": nonzero(data, 0x1155C, 216, 2), "record_selector": struct.unpack_from("<h", data, 0x11634)[0],
        "record_unknown": nonzero(data, 0x11636, 0x56E)}
    out["collection"] = [{"index": i, "flags": f, "copies": c, "limit_status": s, "byte3": x}
                         for i, f, c, s, x in collection(data) if f or c or s != 3 or x]
    out["collection_spare"] = nonzero(data, COLLECTION_BASE + 4 * CARD_RECORDS, 4 * (CARD_CAPACITY - CARD_RECORDS))
    out["flag_bytes"] = nonzero(data, 0x153E4, 0xE10)
    out["card_list"] = {"count": struct.unpack_from("<H", data, 0x161F4)[0], "cards": nonzero(data, 0x161F6, 0xC6, 2),
                        "states": nonzero(data, 0x162BC, 0xC6, 2)}
    out["edit_block"] = data[0x16382:0x16582].hex()
    out["limit_list_name"] = utf16(data, 0x16582, 0x80)
    out["packs_bought"] = struct.unpack_from("<H", data, 0x16602)[0]
    packs = []
    for p in range(PACK_COUNT):
        base = PACK_BASE + PACK_SIZE * p
        packs.append({"pack": p, "stock": [data[base] & 15, data[base] >> 4], "state": data[base + 1] & 7,
                      "rarity_box": u16s(data, base + 2, 20)})
    out["packs"] = packs
    out["progress_bytes"] = list(data[0x16DE4:0x16E0A])
    out["max_story_cycle"] = u32(0x16E0C)
    out["byte_16e10"] = data[0x16E10]
    out["byte_16e11"] = data[0x16E11]
    word = struct.unpack_from("<H", data, 0x16E12)[0]
    out["partner"] = {"flag": word & 1, "cycle": word >> 1 & 7, "character": word >> 4 & 0xFF, "variant": word >> 12}
    story = {}
    for offset, size, key, _, _ in SUBMAPS["story_block"]:
        story[key] = {"offset": hex(offset), "nonzero_bytes": sum(1 for b in data[offset:offset + size] if b)}
    fsb = 0x1A270
    story["field_save_block"].update({"story_stage": data[fsb], "chapter_step": data[fsb + 1],
                                      "pairing_order": [b for b in data[fsb + 0x1C:fsb + 0x1C + 140] if b != 0xFF]})
    story["calendar"]["words"] = u32s(data, 0x1A24C, 9)
    story["sandwiches_seen"]["bits"] = bits(data, 0x1A3C4, 8, 1)
    story["story_bits_3590"]["bits"] = bits(data, 0x1A3A4, 0x20, 1)
    story["runtime_records_b"]["ids"] = [u32(0x1A3CC + 0x18 * k) for k in range(140)]
    out["story_block"] = story
    out["picture_bits"] = bits(data, 0x1B0FC, 0xC)
    for key in ("minigame_block_0", "minigame_block_1", "minigame_block_2", "minigame_block_3",
                "minigame_block_6", "minigame_block_7", "minigame_block_8", "title_words"):
        offset, size = next((o, s) for o, s, k, _, _ in MAP if k == key)
        out[key] = u32s(data, offset, size // 4)
    out["character_flags"] = nonzero(data, CHAR_FLAGS_BASE, 2 * CHAR_FLAGS_COUNT, 2)
    out["progress_flags"] = list(data[0x1C0E8:0x1C0EB])
    out["unknown_nonzero"] = {key: nonzero(data, offset, size)
                              for offset, size, key, confidence, _ in MAP if confidence == "-"}
    out["unknown_nonzero"]["pads"] = {key: nonzero(data, offset, size)
                                      for offset, size, key, _, _ in MAP if key.startswith("pad_")}
    out["buffer_tail_nonzero_bytes"] = sum(1 for b in data[STATE_SIZE:] if b)
    return out


def check(data, valid_ids=None):
    problems = check_map()
    if len(data) != SAVE_SIZE:
        problems.append(f"size {len(data)}, expected {SAVE_SIZE} (an encrypted save is 16 bytes longer)")
        return problems
    if struct.unpack_from("<I", data, 0)[0] != VERSION:
        problems.append("version word is not 0x30000 (the game would reject this save)")
    for deck in list(decks(data)) + list(stored_decks(data)):
        for label in ("main", "side", "extra"):
            if valid_ids is not None and any(i not in valid_ids for i in deck[label]):
                problems.append(f"deck {deck.get('slot', deck.get('index'))}: unknown card id in {label}")
    statuses = {status for _, _, _, status, _ in collection(data)}
    if not statuses <= {0, 1, 2, 3}:
        problems.append("collection: limit status out of range")
    if struct.unpack_from("<H", data, 0x161F4)[0] >= 100:
        problems.append("card list count out of range")
    return problems


def known_ids(cardinfo_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("re_cardinfo", Path(__file__).resolve().parent / "cardinfo.py")
    cardinfo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cardinfo)
    info = cardinfo.CardInfo(cardinfo_path.read_bytes(), "E")
    return {info.properties(i)["id"] for i in range(1, info.count)}


def map_rows():
    for offset, size, key, confidence, text in MAP:
        yield {"offset": f"{offset:#07x}", "size": size, "key": key, "parent": "", "confidence": confidence, "content": text}
        for sub in SUBMAPS.get(key, []):
            yield {"offset": f"{sub[0]:#07x}", "size": sub[1], "key": sub[2], "parent": key,
                   "confidence": sub[3], "content": sub[4]}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read a plaintext Tag Force 3 DATA0 save.")
    parser.add_argument("args", nargs="*", help="[decks|collection|json|map] [DATA0]")
    parser.add_argument("--cardinfo", type=Path, help="duelsys/cardinfo_eng.ehp, to validate card ids")
    parser.add_argument("--check", action="store_true", help="only run the structural checks")
    parser.add_argument("-o", "--output", type=Path, help="write the output here (keep it out of git)")
    ns = parser.parse_args(argv)
    what = ns.args[0] if ns.args and ns.args[0] in ("decks", "collection", "json", "map") else None
    rest = ns.args[1:] if what else ns.args
    if len(rest) > 1:
        parser.error("too many arguments")
    path = Path(rest[0]) if rest else None

    if what == "map":
        rows = list(map_rows())
        fields = list(rows[0])
    else:
        if path is None:
            if not ns.check:
                parser.error("a DATA0 path is needed")
            problems = check_map()
            totals = coverage()
            print("\n".join(problems) if problems else
                  "ok: map covers {:#x} bytes; ".format(SAVE_SIZE) +
                  ", ".join(f"{k} {v}" for k, v in sorted(totals.items())))
            return 1 if problems else 0
        data = path.read_bytes()
        if ns.check or what is None:
            problems = check(data, known_ids(ns.cardinfo) if ns.cardinfo else None)
            used = sum(1 for d in decks(data) if d["main"])
            owned = sum(1 for _, _, copies, _, _ in collection(data) if copies)
            print("\n".join(problems) if problems else f"ok: {used} non-empty deck slots, {owned} cards owned")
            return 1 if problems else 0
        if what == "json":
            text = json.dumps(decode(data), indent=1, ensure_ascii=False)
            if ns.output:
                ns.output.write_text(text + "\n", encoding="utf-8")
            else:
                print(text)
            return 0
        if what == "decks":
            rows = [{"slot": d["slot"], "owner": d["owner"], "recipe": d["recipe"], "name": d["name"],
                     "section": label, "position": n, "card_id": cid}
                    for d in decks(data) for label in ("main", "side", "extra") for n, cid in enumerate(d[label])]
            fields = ["slot", "owner", "recipe", "name", "section", "position", "card_id"]
        else:
            rows = [{"index": i, "flags": f, "copies": c, "limit_status": s, "byte3": x}
                    for i, f, c, s, x in collection(data) if f or c or s != 3 or x]
            fields = ["index", "flags", "copies", "limit_status", "byte3"]
    out = open(ns.output, "w", encoding="utf-8", newline="") if ns.output else sys.stdout
    try:
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    finally:
        if ns.output:
            out.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
