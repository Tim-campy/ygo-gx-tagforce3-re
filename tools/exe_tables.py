#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Static tables embedded in BOOT.BIN and the game modules: reader, writer and owned byte spans.

  exe_tables.py list                              the table rows this tool reads and writes
  exe_tables.py dump <PSP_GAME> ID [-o FILE]      one row's tables as JSON (game data: keep it under extracted/)
  exe_tables.py check <PSP_GAME> [ID ...]         parse -> write round trip of every listed row (byte for byte)

Every table is declared by its executable, its module-relative address (the ELF vaddr; runtime address =
module base + vaddr, BOOT.BIN base 0x08804000), a record layout and a record count taken from the code that
reads it (layouts and evidence: docs/formats/duel-runtime.md, ai-runtime.md, story-runtime.md, field-maps.md,
shop-rules.md, character-table.md, system-runtime.md, sound.md). Pointer fields keep the module-relative value
stored in the file (0 = none); a string pointer also brings the NUL-terminated string it points at, and a
counted list pointer the u16 list, both owned by the table and rewritten by the writer.

The model of one table is {"module", "address", "rows": [...], "strings": {pointer: text}, "lists":
{pointer: [values]}}. write() writes the rows, strings and lists back in place; spans() lists the file byte
ranges the table owns, which tools/roundtrip.py blanks before writing to prove that every owned byte comes from
the model.
"""

import argparse
import importlib.util
import json
import struct
import sys
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_prx_imports", Path(__file__).resolve().parent / "prx_imports.py")
prx_imports = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prx_imports)

BOOT = "BOOT"
BOOT_BASE = 0x08804000
DUEL_ENG_BASE = 0x09BE1400
STRING_ENCODING = "cp932"


class Table:
    """One table: `fields` is [(name, kind)] where kind is a struct code ("I", "h", "3b", "8s", ...), "str"
    (u32 pointer to a C string) or ("list", count_field, element code) (u32 pointer to `count_field`
    elements)."""

    def __init__(self, module, address, fields, count, label=None):
        self.module, self.address, self.fields, self.count = module, address, fields, count
        self.label = label or f"{module} +{address:#x}"
        codes = []
        for _, kind in fields:
            codes.append("I" if kind == "str" or isinstance(kind, tuple) else kind)
        self.record = struct.Struct("<" + "".join(codes))

    @property
    def size(self):
        return self.record.size * self.count


def _code_count(code):
    digits = code[:-1]
    return int(digits) if digits else 1


def _unpack_record(table, raw):
    values = list(table.record.unpack(raw))
    row = {}
    for name, kind in table.fields:
        code = "I" if kind == "str" or isinstance(kind, tuple) else kind
        if code.endswith("s"):
            row[name] = values.pop(0).hex()
        elif _code_count(code) > 1:
            n = _code_count(code)
            row[name], values = values[:n], values[n:]
        else:
            row[name] = values.pop(0)
    return row


def _pack_record(table, row):
    values = []
    for name, kind in table.fields:
        code = "I" if kind == "str" or isinstance(kind, tuple) else kind
        value = row[name]
        if code.endswith("s"):
            values.append(bytes.fromhex(value))
        elif _code_count(code) > 1:
            values.extend(value)
        else:
            values.append(value)
    return table.record.pack(*values)


def elf_of(data):
    return prx_imports.Elf(data, 0)


def _cstring(data, offset):
    return data[offset:data.index(b"\0", offset)]


def read(data, table):
    elf = elf_of(data)
    start = elf.offset(table.address)
    rows = [_unpack_record(table, data[start + i * table.record.size:start + (i + 1) * table.record.size])
            for i in range(table.count)]
    strings, lists = {}, {}
    for row in rows:
        for name, kind in table.fields:
            pointer = row[name]
            if kind == "str" and pointer:
                strings[pointer] = _cstring(data, elf.offset(pointer)).decode(STRING_ENCODING)
            elif isinstance(kind, tuple) and pointer and row[kind[1]]:
                code = kind[2]
                size = struct.calcsize("<" + code)
                count = row[kind[1]]
                lists[pointer] = list(struct.unpack_from(f"<{count}{code}", data, elf.offset(pointer)))
                if lists[pointer] and size * count > 0 and len(lists[pointer]) != count:
                    raise ValueError(f"{table.label}: short list at {pointer:#x}")
    return {"module": table.module, "address": table.address, "rows": rows, "strings": strings, "lists": lists}


def _element_code(table, pointer, model):
    for row in model["rows"]:
        for name, kind in table.fields:
            if isinstance(kind, tuple) and row[name] == pointer:
                return kind[2]
    raise ValueError(f"{table.label}: list {pointer:#x} is not referenced by any row")


def spans(data, table, model):
    """(file offset, size) of every byte the table owns: the records, each string with its NUL, each list."""
    elf = elf_of(data)
    out = [(elf.offset(table.address), table.size)]
    for pointer, text in model["strings"].items():
        out.append((elf.offset(int(pointer)), len(text.encode(STRING_ENCODING)) + 1))
    for pointer, values in model["lists"].items():
        code = _element_code(table, int(pointer), model)
        out.append((elf.offset(int(pointer)), struct.calcsize("<" + code) * len(values)))
    return out


def write(data, table, model):
    if len(model["rows"]) != table.count:
        raise ValueError(f"{table.label}: {len(model['rows'])} rows, the table has {table.count}")
    out = bytearray(data)
    elf = elf_of(data)
    start = elf.offset(table.address)
    out[start:start + table.size] = b"".join(_pack_record(table, row) for row in model["rows"])
    for pointer, text in model["strings"].items():
        raw = text.encode(STRING_ENCODING) + b"\0"
        at = elf.offset(int(pointer))
        out[at:at + len(raw)] = raw
    for pointer, values in model["lists"].items():
        code = _element_code(table, int(pointer), model)
        raw = struct.pack(f"<{len(values)}{code}", *values)
        at = elf.offset(int(pointer))
        out[at:at + len(raw)] = raw
    return bytes(out)


# --------------------------------------------------------------------------------------------- the tables

def _eng(runtime):
    return runtime - DUEL_ENG_BASE


def _boot(runtime):
    return runtime - BOOT_BASE


CODE = [("function", "I")]
CHECK = [("function", "I"), ("argument", "I")]
UI_RESOURCE = [("id", "I"), ("cache", "I"), ("format", "str")]

CHARACTER_FIELDS = [
    ("character", "B"), ("variant", "b"), ("pad_02", "H"), ("record_name", "str"), ("category", "B"),
    ("kind", "b"), ("pad_0a", "H"), ("bustup_archive", "str"), ("sprite_first", "str"), ("sprite_second", "str"),
    ("value_a", "h"), ("value_b", "h"), ("value_c", "b"), ("pad_1d", "3s"), ("mini_bustup_name", "str"),
    ("cutin_archive", "str"), ("mini_bustup_texture", "str"), ("model_ids", "3b"), ("pad_2f", "B"),
    ("voice_bank", "I"), ("voice_extra_bank", "I"), ("profile_key", "str"), ("flags_3c", "H"), ("byte_3e", "B"),
    ("index_3f", "b"), ("name_index", "I"), ("tuning_44", "5B"), ("tuning_49", "9B"), ("bytes_52", "3B"),
    ("pad_55", "3s"), ("tuning_58", "8I"), ("cutin_card_ids", "6H"),
    ("recipe_cards", ("list", "recipe_card_count", "H")), ("recipe_card_count", "I"),
    ("key_cards", ("list", "key_card_count", "H")), ("key_card_count", "I"),
]

TABLES = {
    # rel_duel_eng (docs/formats/duel-runtime.md, docs/subsystems/duel-phases.md, docs/formats/ai-runtime.md)
    "duel_flow_steps": [Table("rel_duel_eng", _eng(0x09E01DBC), CODE, 3, "duel-flow steps")],
    "turn_steps": [Table("rel_duel_eng", _eng(0x09E01DA0), CODE, 7, "turn steps")],
    "battle_steps": [Table("rel_duel_eng", _eng(0x09E01DCC), CODE, 13, "Battle Phase steps")],
    "duel_command_dispatch": [Table("rel_duel_eng", _eng(0x09E00944), [("case", "I")], 0x69, "command jump table")],
    "list_activation_table": [Table("rel_duel_eng", _eng(0x09E00DBC),
                                    [("card", "I"), ("location", "I"), ("condition", "I"), ("activation", "I")], 23,
                                    "list activation table")],
    "battle_end_checks": [Table("rel_duel_eng", _eng(0x09E00F5C), CHECK, 31, "Battle-end checks")],
    "end_phase_checks": [Table("rel_duel_eng", _eng(0x09E014F4), CHECK, 8, "End Phase checks")],
    "zone_preference_tables": [Table("rel_duel_eng", _eng(0x09DEBA0C), [("zone", "I")], 5, "monster zone order"),
                               Table("rel_duel_eng", _eng(0x09DEBA20), [("zone", "I")], 5, "spell/trap zone order")],
    "ai_main_steps": [Table("rel_duel_eng", _eng(0x09E01BA4), CODE, 8, "AI main-phase steps")],
    # rel_field (docs/formats/story-runtime.md, docs/formats/field-maps.md)
    "field_request_table": [Table("rel_field", 0x2DF0C, [("start", "I"), ("poll", "I"), ("unused", "I")], 33,
                                  "field requests")],
    "field_marker_hidden_cells": [Table("rel_field", 0x28F7C, [("x", "I"), ("y", "I")], 14, "map 21 cells"),
                                  Table("rel_field", 0x28FEC, [("x", "I"), ("y", "I")], 120, "map 27 cells")],
    # rel_story (docs/formats/story-runtime.md)
    "story_calendar_tables": [Table("rel_story", 0x208EC, [("period", "I"), ("unused", "I")], 8, "light period"),
                              Table("rel_story", 0x2E50C, [("day_off", "I")], 7, "day off"),
                              Table("rel_story", 0x2E528, [("cap", "i")], 10, "points cap")],
    # rel_shop (docs/formats/shop-rules.md)
    "shop_opponent_list": [Table("rel_shop", 0x20508, [("entry", "H")], 104, "shop opponent list")],
    # UI resource tables (docs/formats/system-runtime.md; tables and counts from each module's lookup code)
    "ui_resource_table": [
        Table("rel_deck", 0x22E4C, UI_RESOURCE, 41),
        Table("rel_decktutorial", 0x21D2C, UI_RESOURCE, 41),
        Table("rel_deckswap", 0x1891C, UI_RESOURCE, 41), Table("rel_deckswap", 0x18B30, UI_RESOURCE, 2),
        Table("rel_select_card", 0x19338, UI_RESOURCE, 41), Table("rel_select_card", 0x19534, UI_RESOURCE, 1),
        Table("rel_select_card", 0x19540, UI_RESOURCE, 1), Table("rel_select_card", 0x1955C, UI_RESOURCE, 1),
        Table("rel_recipeviewer", 0xC384, UI_RESOURCE, 41), Table("rel_recipeviewer", 0xC58C, UI_RESOURCE, 3),
        Table("rel_shop", 0x20C50, UI_RESOURCE, 21),
    ],
    # BOOT.BIN (docs/formats/system-runtime.md, docs/formats/character-table.md)
    "root_path_table": [Table(BOOT, _boot(0x0889FB24), [("path", "str")], 10, "root paths")],
    "card_language_suffixes": [Table(BOOT, _boot(0x08878C88), [("code", "8s")], 6, "language codes")],
    "boot_character_table": [Table(BOOT, _boot(0x088AA510), CHARACTER_FIELDS, 174, "character table")],
}


# --------------------------------------------------------------------------------------------- SHDS header

SHDS_ADDRESS = _boot(0x0887B5E0)  # docs/formats/sound.md, "SHDS sound header"
SHDS_MAGIC = b"SHDS"
SHDS_HEAD = 0x34  # attribute words start here


def read_shds(boot):
    """BOOT.BIN SHDS header: counts, the per-id attribute words, bank records, bank offsets and first ids."""
    elf = elf_of(boot)
    at = elf.offset(SHDS_ADDRESS)
    if boot[at:at + 4] != SHDS_MAGIC:
        raise ValueError("no SHDS header at the documented address")
    version, = struct.unpack_from("<H", boot, at + 0x08)
    music, extra, other = struct.unpack_from("<3H", boot, at + 0x0C)
    banks, ids = music + other, music + other + extra
    pos = at + SHDS_HEAD
    attributes = list(struct.unpack_from(f"<{ids}I", boot, pos))
    pos += 4 * ids
    records = [list(struct.unpack_from("<4I", boot, pos + 16 * b)) for b in range(banks)]
    pos += 16 * banks
    offsets = list(struct.unpack_from(f"<{banks}I", boot, pos))
    pos += 4 * banks
    first_ids = list(struct.unpack_from(f"<{banks}H", boot, pos))
    reserved = (boot[at + 0x04:at + 0x08] + boot[at + 0x0A:at + 0x0C] + boot[at + 0x12:at + SHDS_HEAD]).hex()
    return {"version": version, "music_banks": music, "extra_ids": extra, "other_banks": other,
            "reserved": reserved, "attributes": attributes, "bank_records": records, "bank_offsets": offsets,
            "first_ids": first_ids}


def shds_size(model):
    banks = model["music_banks"] + model["other_banks"]
    ids = banks + model["extra_ids"]
    return SHDS_HEAD + 4 * ids + 16 * banks + 4 * banks + 2 * banks


def build_shds(model):
    banks = model["music_banks"] + model["other_banks"]
    ids = banks + model["extra_ids"]
    if (len(model["attributes"]), len(model["bank_records"]), len(model["bank_offsets"]),
            len(model["first_ids"])) != (ids, banks, banks, banks):
        raise ValueError("SHDS table lengths do not match the header counts")
    reserved = bytes.fromhex(model["reserved"])
    head = bytearray(SHDS_HEAD)
    head[0:4] = SHDS_MAGIC
    head[0x04:0x08] = reserved[0:4]
    struct.pack_into("<H", head, 0x08, model["version"])
    head[0x0A:0x0C] = reserved[4:6]
    struct.pack_into("<3H", head, 0x0C, model["music_banks"], model["extra_ids"], model["other_banks"])
    head[0x12:SHDS_HEAD] = reserved[6:]
    return (bytes(head) + struct.pack(f"<{ids}I", *model["attributes"])
            + b"".join(struct.pack("<4I", *r) for r in model["bank_records"])
            + struct.pack(f"<{banks}I", *model["bank_offsets"]) + struct.pack(f"<{banks}H", *model["first_ids"]))


def shds_spans(boot, model):
    return [(elf_of(boot).offset(SHDS_ADDRESS), shds_size(model))]


def write_shds(boot, model):
    out = bytearray(boot)
    at = elf_of(boot).offset(SHDS_ADDRESS)
    raw = build_shds(model)
    out[at:at + len(raw)] = raw
    return bytes(out)


# --------------------------------------------------------------------------------------------- row level

def read_row(executables, row_id):
    """executables: {module name: bytes} ("BOOT" for BOOT.BIN). Returns the list of table models of a row."""
    return [read(executables[t.module], t) for t in TABLES[row_id]]


def row_problems(executables, row_id, rewrite):
    """Round trip of one row through `rewrite(label, data, spans, write, model) -> [problems]` per table."""
    problems = []
    for table in TABLES[row_id]:
        data = executables[table.module]
        model = json.loads(json.dumps(read(data, table)))
        model["strings"] = {int(k): v for k, v in model["strings"].items()}
        model["lists"] = {int(k): v for k, v in model["lists"].items()}
        problems += rewrite(table.label, data, spans(data, table, model),
                            lambda blob, m, t=table: write(blob, t, m), model)
    return problems


def load_executables(root, modules):
    root = Path(root)
    out = {}
    for name in modules:
        path = root / "SYSDIR" / "BOOT.BIN" if name == BOOT else root / "USRDIR" / "gmodule" / f"{name}.prx"
        out[name] = path.read_bytes()
    return out


def _rewrite(label, data, owned, write_fn, model, filler=0xA5):
    blank = bytearray(data)
    for offset, size in owned:
        blank[offset:offset + size] = bytes([filler]) * size
    return [] if write_fn(bytes(blank), model) == data else [f"{label}: differs"]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Static tables in BOOT.BIN and the game modules.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    dump = sub.add_parser("dump")
    dump.add_argument("root", type=Path, help="PSP_GAME directory")
    dump.add_argument("row")
    dump.add_argument("-o", "--output", type=Path)
    chk = sub.add_parser("check")
    chk.add_argument("root", type=Path)
    chk.add_argument("rows", nargs="*")
    args = parser.parse_args(argv)
    if args.command == "list":
        for row_id, tables in TABLES.items():
            print(f"{row_id}: " + ", ".join(f"{t.label} ({t.count} x {t.record.size})" for t in tables))
        print("snd_shds_header: BOOT.BIN SHDS header")
        return 0
    if args.command == "dump":
        if args.row == "snd_shds_header":
            model = read_shds(load_executables(args.root, [BOOT])[BOOT])
        else:
            executables = load_executables(args.root, {t.module for t in TABLES[args.row]})
            model = read_row(executables, args.row)
        text = json.dumps(model, indent=1)
        if args.output:
            args.output.write_text(text, encoding="utf-8")
        else:
            print(text)
        return 0
    rows = args.rows or list(TABLES)
    executables = load_executables(args.root, {t.module for r in rows if r in TABLES for t in TABLES[r]} | {BOOT})
    failed = 0
    for row_id in rows:
        if row_id == "snd_shds_header":
            boot = executables[BOOT]
            model = read_shds(boot)
            problems = _rewrite("SHDS", boot, shds_spans(boot, model), write_shds, model)
        else:
            problems = row_problems(executables, row_id, _rewrite)
        failed += bool(problems)
        print(f"{'FAIL' if problems else 'ok  '} {row_id}" + "".join(f"\n     {p}" for p in problems))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
