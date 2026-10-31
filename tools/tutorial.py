#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read and check the tutorial data: the duel tutorial (d_tutorial/tutorial.ehp: tuto_field_*.ydq duel
setups, tuto_cmd_NN.bin scripts, tuto_text_<l>.bin text) and the deck-building tutorial
(deck/tutorial.ehp: deck_tutorialNN.bin scripts, strTbl_<l>.bin). See docs/formats/tutorial.md and deck.md.

  tutorial.py <USRDIR>/d_tutorial/tutorial.ehp --check          structural checks over every member
  tutorial.py <USRDIR>/d_tutorial/tutorial.ehp [--only cmd_03]  readable listing, text resolved (--lang e)
  tutorial.py <USRDIR>/deck/tutorial.ehp [--check]              the same for the deck-building tutorial
  tutorial.py <USRDIR>/tutorial/tutorial_*.ehp --check          the legacy set the game never loads

Several archives may be given at once. `--cardinfo duelsys/cardinfo_eng.ehp` checks card ids against the
card database and prints card names. The listing is game data: keep it under extracted/, never in git.
"""

import argparse
import importlib.util
import re
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
decks = _load("decks")

LANGUAGES = "jegfis"  # index = the game's language number (rel_tutorial 0xf788, "jegfis"[n & 7])

# ---------------------------------------------------------------------- .ydq duel setup (rel_duel_eng)

DEFAULT_LP = 8000  # duel_core_load_ydq stores 8000 for both sides before parsing
PHASES = {"D": (0, "draw"), "S": (1, "standby"), "M": (2, "main"), "B": (3, "battle"), "E": (5, "end")}
SLOT_FLAGS = {"PUTBYANOTHER": 0x1, "SPECIALSUMMONED": 0x40, "PARTICULAR": 0x80, "CAPTURED": 0x800,
              "TRAPMONSTER": 0x1000}  # ORed into the field slot's flag word (+0x10)
EQUIP_TYPES = {"ONLYINTURN": 1, "ONLYFACETURN": 2, "ONLYFACE": 3, "FOREVER": 5, "PERMANENT": 6,
               "DURINGFACE": 7, "EQUIPMENT": 10, "UNION": 11, "CAPTURED": 12}
# CardIn<list><p>_NNN=<id>: character that selects the list, position of the player digit, of the value.
LISTS = {"Hand": ("hand", 10, 16), "Deck": ("deck", 10, 16), "Fusion": ("extra", 12, 18),
         "Exclude": ("banished", 13, 19), "Grave": ("grave", 11, 17)}
SLOT_COUNT = 11  # field slots 0-4 monster zones, 5-9 spell/trap zones, 10 field-spell zone


def scan_int(text, pos):
    """sscanf("%d") at pos: optional blanks and sign, then digits; None when nothing matches."""
    match = re.match(rb"[ \t\r\n\v\f]*([+-]?\d+)", text[pos:])
    return int(match.group(1)) if match else None


def new_side():
    return {"lp": DEFAULT_LP, "hand": [], "deck": [], "extra": [], "grave": [], "banished": [], "field": {},
            "counts": {}}


def new_setup():
    return {"phase": None, "turn": 0, "turn_player": None, "limit_turn": None, "end": False,
            "sides": [new_side(), new_side()],
            "partners": [{"hand": [], "deck": [], "extra": []} for _ in range(2)],
            "equips": {}, "ignored": [], "lines": 0}


def ydq_lines(blob):
    """The game copies one line at a time (up to '\\n', at most 254 bytes) into a 256-byte buffer."""
    lines, pos = [], 0
    while pos < len(blob) and blob[pos]:
        end = blob.find(b"\n", pos)
        end = len(blob) if end < 0 else end + 1
        while end - pos > 254:
            lines.append(blob[pos:pos + 254])
            pos += 254
        lines.append(blob[pos:end])
        pos = end
    return lines


def parse_ydq_line(setup, line):
    """Apply one line the way duel_core_parse_ydq_line (rel_duel_eng +0x1e6ecc) does; False after [END]."""
    def ignore():
        setup["ignored"].append(line.rstrip(b"\r\n").decode("cp932", "replace"))

    first = line[:1]
    if first == b"[":
        if line.startswith(b"[END]"):
            setup["end"] = True
            return False
        return True  # section headers are not interpreted
    if first == b"L":
        if line.startswith(b"LimitTurn"):
            n = scan_int(line, 10)
            setup["limit_turn"] = None if n is None or n <= 0 else setup["turn"] + n - 1
        else:
            ignore()
    elif first == b"T":
        if line.startswith(b"TurnPlayer"):
            setup["turn_player"] = line[11] - 0x30
        elif line.startswith(b"Turn"):
            setup["turn"] = line[5] - 0x31  # one digit, stored 0-based
        else:
            ignore()
    elif first == b"P":
        if line.startswith(b"PlayerLP"):
            player = (line[8] - 0x30) & 1
            setup["sides"][player]["lp"] = scan_int(line, 10)
        elif line.startswith(b"Phase"):
            phase = PHASES.get(chr(line[6])) if len(line) > 6 else None
            if phase:
                setup["phase"] = phase
            else:
                ignore()
        else:
            ignore()
    elif first == b"C":
        parse_card_line(setup, line, ignore)
    elif first == b"E":
        parse_equip_line(setup, line, ignore)
    else:
        ignore()
    return True


def parse_card_line(setup, line, ignore):
    if not line.startswith(b"CardIn") or len(line) < 8:
        return ignore()
    kind = chr(line[6])
    if kind == "G" and chr(line[7]) != "r":
        return parse_field_line(setup, line, ignore)
    name = {"G": "Grave", "E": "Exclude", "F": "Fusion", "D": "Deck", "H": "Hand"}.get(kind)
    if name is None:
        return ignore()
    target, digit, value = LISTS[name]
    if len(line) <= digit + 1:
        return ignore()
    player = line[digit] - 0x30
    if line[digit + 1:digit + 2] == b"=":  # CardInHand0=5: count lines are not read
        setup["sides"][player & 1]["counts"][target] = scan_int(line, digit + 2)
        return
    card = scan_int(line, value)
    if card is None:
        return ignore()
    card &= 0x3FFF
    if player >= 2 and target in ("hand", "deck", "extra"):
        setup["partners"][player & 1][target].append(card)  # tag partner: separate table, ids only
    else:
        setup["sides"][player & 1][target].append(card)


def parse_field_line(setup, line, ignore):
    if not line.startswith(b"CardInGame") or len(line) < 16:
        return ignore()
    side = setup["sides"][(line[10] - 0x30) & 1]
    slot_number = scan_int(line, 12)
    if slot_number is None:
        return ignore()
    slot = side["field"].setdefault(slot_number, {"card": 0, "face_up": 0, "owner_other": False,
                                                    "defense": 0, "param": 0, "flags": 0})
    rest = line[15:]
    if rest.startswith(b"="):
        slot["card"] = (scan_int(line, 16) or 0) & 0x3FFF
    elif rest.startswith(b"_Face"):
        slot["face_up"] = scan_int(line, 21)
    elif rest.startswith(b"_Owner"):
        slot["owner_other"] = scan_int(line, 22) != line[10] - 0x30
    elif rest.startswith(b"_Turn"):
        slot["defense"] = scan_int(line, 21)  # slot +0x06, the battle position
    elif rest.startswith(b"_Param"):
        slot["param"] = scan_int(line, 22)
    elif rest.startswith(b"_Flag"):
        for name, bit in SLOT_FLAGS.items():
            if line[21:].startswith(name.encode()):
                slot["flags"] |= bit
                break
        else:
            ignore()
    else:
        ignore()


def parse_equip_line(setup, line, ignore):
    if not line.startswith(b"EquipAct") or len(line) < 9:
        return ignore()
    if line[8:9] == b"=":
        return  # EquipAct=<count>: not read
    number = scan_int(line, 8)
    if number is None:
        return ignore()
    record = setup["equips"].setdefault(number, {})
    key = line[12:]
    for field in ("SrcPlayer", "SrcLocate", "SrcCardID", "DstPlayer", "DstLocate"):
        if key.startswith(field.encode()):
            record[field] = scan_int(line, 22)
            return
    if key.startswith(b"Type"):
        for name, value in EQUIP_TYPES.items():
            if line[17:].startswith(name.encode()):
                record["Type"] = value
                return
    ignore()


def parse_ydq(blob):
    setup = new_setup()
    for line in ydq_lines(blob):
        setup["lines"] += 1
        if not parse_ydq_line(setup, line):
            break
    return setup


YDQ_KEY = re.compile(r"^(\[(DUEL QUESTION|Player[0-3]|Equipment|END)\]"
                     r"|Phase=\w+|Turn=\d+|TurnPlayer=\d|LimitTurn=-?\d+|PlayerLP[0-3]=\d+"
                     r"|CardIn(Hand|Deck|Fusion|Grave|Exclude)[0-3]=\d+"
                     r"|CardIn(Hand|Deck|Fusion|Grave|Exclude)[0-3]_\d{3}=\d+"
                     r"|CardInGame[0-3]_\d{3}=\d+|CardInGame[0-3]_\d{3}_(Face|Owner|Turn|Param)=-?\d+"
                     r"|CardInGame[0-3]_\d{3}_Flag=[A-Z]+"
                     r"|EquipAct=\d+|EquipAct\d{3}_(SrcPlayer|SrcLocate|SrcCardID|DstPlayer|DstLocate)=\d+"
                     r"|EquipAct\d{3}_Type=[A-Z]+)$")


def check_ydq(name, blob, known=None):
    """(errors, notes). Errors break the format; notes are facts the game ignores (count lines)."""
    errors, notes = [], []
    try:
        text = blob.decode("cp932")
    except UnicodeDecodeError as error:
        return [f"{name}: not Shift-JIS text ({error})"], notes
    for number, raw in enumerate(text.split("\n"), 1):
        line = raw.rstrip("\r").split("//", 1)[0].strip()
        if line and not YDQ_KEY.match(line):
            errors.append(f"{name} line {number}: unknown line {line[:40]!r}")
    setup = parse_ydq(blob)
    if not setup["end"]:
        errors.append(f"{name}: no [END] line")
    if setup["phase"] is None:
        errors.append(f"{name}: no Phase")
    if setup["ignored"]:
        errors.append(f"{name}: {len(setup['ignored'])} line(s) the game would ignore, e.g. {setup['ignored'][0]!r}")
    for player, side in enumerate(setup["sides"]):
        for slot, state in side["field"].items():
            if not 0 <= slot < SLOT_COUNT:
                errors.append(f"{name}: player {player} field slot {slot} out of range")
            if not state["card"]:
                errors.append(f"{name}: player {player} field slot {slot} has attributes but no card")
        for target, count in side["counts"].items():
            if count != len(side[target]):
                notes.append(f"{name}: player {player} {target} count line says {count}, {len(side[target])} entries")
        if known is not None:
            cards = [c for t in ("hand", "deck", "extra", "grave", "banished") for c in side[t]]
            cards += [s["card"] for s in side["field"].values()]
            for card in cards:
                if card not in known:
                    notes.append(f"{name}: player {player} card id {card} is not in the card database")
    return errors, notes


def side_summary(side, names):
    def cards(ids):
        return ", ".join(names(c) for c in ids) if ids else "-"
    out = [f"  LP {side['lp']}", f"  hand ({len(side['hand'])}): {cards(side['hand'])}",
           f"  deck ({len(side['deck'])}): {cards(side['deck'])}", f"  extra ({len(side['extra'])}): {cards(side['extra'])}",
           f"  grave ({len(side['grave'])}): {cards(side['grave'])}",
           f"  banished ({len(side['banished'])}): {cards(side['banished'])}"]
    for slot in sorted(side["field"]):
        s = side["field"][slot]
        zone = "monster" if slot < 5 else "spell/trap" if slot < 10 else "field"
        attributes = [names(s["card"]), "face-up" if s["face_up"] else "face-down"]
        if s["defense"]:
            attributes.append("defense")
        if s["owner_other"]:
            attributes.append("owned by the opponent")
        if s["param"]:
            attributes.append(f"param {s['param']}")
        attributes += [n for n, b in SLOT_FLAGS.items() if s["flags"] & b]
        out.append(f"  slot {slot:2d} ({zone}): " + ", ".join(attributes))
    return out


def ydq_listing(name, setup, names):
    phase = setup["phase"][1] if setup["phase"] else "?"
    limit = "none" if setup["limit_turn"] is None else setup["limit_turn"]
    out = [f"== {name}: phase {phase}, turn {setup['turn']} (0-based), turn player "
           f"{setup['turn_player'] if setup['turn_player'] is not None else 'default'}, last turn {limit}"]
    for player, side in enumerate(setup["sides"]):
        out.append(f" player {player}")
        out += side_summary(side, names)
    for player, partner in enumerate(setup["partners"]):
        if any(partner.values()):
            out.append(f" tag partner of player {player}: " + "; ".join(f"{k} {len(v)}" for k, v in partner.items()))
    for number, record in sorted(setup["equips"].items()):
        out.append(f" equip {number}: {record}")
    return out


# ---------------------------------------------------------------------- tuto_text_<l>.bin

def text_table(blob, language):
    """u32 (offset, size) pairs, one per line, then the text; count = first offset / 8.
    UTF-16LE (Shift-JIS for 'j'), NUL-terminated, zero-padded to a multiple of 4 bytes."""
    first, = struct.unpack_from("<I", blob, 0)
    if first % 8 or first == 0 or first > len(blob):
        raise ValueError("first offset is not a plausible index size")
    entries = [struct.unpack_from("<II", blob, 8 * i) for i in range(first // 8)]
    encoding = "cp932" if language == "j" else "utf-16-le"
    unit = 1 if language == "j" else 2
    lines = []
    for number, (offset, size) in enumerate(entries):
        raw = blob[offset:offset + size]
        end = next((k for k in range(0, len(raw), unit) if raw[k:k + unit] == b"\0" * unit), None)
        if end is None:
            raise ValueError(f"line {number} has no NUL")
        lines.append(raw[:end].decode(encoding))
    return entries, lines


def check_text(name, blob, language):
    try:
        entries, _ = text_table(blob, language)
    except (ValueError, UnicodeDecodeError) as error:
        return [f"{name}: {error}"]
    errors = []
    for number, (offset, size) in enumerate(entries):
        following = entries[number + 1][0] if number + 1 < len(entries) else len(blob)
        if offset + size != following:
            errors.append(f"{name} line {number}: not contiguous with the next line")
        if size % 4:
            errors.append(f"{name} line {number}: size {size} is not a multiple of 4")
    return errors


# ---------------------------------------------------------------------- tuto_cmd_NN.bin (rel_tutorial)

RECORD = struct.Struct("<4H")
SCRIPT_FLAG = 0x4000  # set: tutorial command (rel_tutorial +0x473c); clear: duel-engine command
SIDE_FLAG = 0x8000  # duel-engine commands: the side (bit 15), as in duel_core_load_ydq
# opcode: (name, argument names, kinds of the arguments: t = text line, l = label, r = reset file, c = card)
COMMANDS = {
    0: ("yield", (), ""), 1: ("message", ("text", "b"), "t"), 2: ("hint", ("text",), "t"),
    3: ("hint_off", (), ""), 4: ("highlight", ("side", "region", "frames"), ""), 5: ("label", ("n",), ""),
    6: ("goto", ("label",), "l"), 7: ("if_answer", ("value", "label"), ".l"), 8: ("question", ("text",), "t"),
    9: ("show_card", ("card",), "c"), 10: ("load_field", ("reset",), "r"), 11: ("wait", ("frames",), ""),
    12: ("wait_input", ("kind", "arg"), ""), 13: ("set_turn", ("turn",), ""),
    14: ("wait_event", ("event", "arg", "min"), ""), 15: ("card_part", ("part",), ""),
    16: ("on_event", ("event", "label", "arg"), ".l"), 17: ("flag_on", ("bit",), ""), 18: ("flag_off", ("bit",), ""),
    19: ("count_answer", ("mode",), ""), 20: ("open_list", ("side", "location"), ""),
}
# wait_input kinds, named after the hint text the scripts show just before them.
INPUT_KINDS = {0: "pick a hand card", 1: "menu: Summon", 2: "phase menu: pick phase <arg>", 3: "pick attacker",
               4: "pick attack target", 5: "menu: Set (monster)", 6: "pick a monster on the field",
               7: "menu: change battle position", 8: "pick Tribute", 9: "menu: Summon (Tribute)",
               10: "menu: Activate", 11: "menu: Set (spell/trap)", 12: "pick a Set spell/trap",
               13: "answer YES", 14: "pick a monster to Special Summon", 15: "pick Fusion Materials",
               16: "pick Tribute (list)", 17: "pick an opponent's card", 18: "open the phase menu",
               19: "extra deck: Activate"}
# Duel-engine commands: duel_core_execute_command (rel_duel_eng 0x09dc0974) dispatches codes 0-0x68 through the
# jump table at module +0x21f544 (bound sltiu 0x69); code 0 is the default case (nothing). Every code that the
# tuto_cmd scripts or the .ydq loader post is listed, with the handler's effect (docs/formats/tutorial.md).
ENGINE_COMMAND_LAST = 0x68
DUEL_COMMANDS = {0x03: "end-of-turn cleanup", 0x04: "next turn (other side)",
                 0x0A: "enter draw phase", 0x0B: "enter standby phase", 0x0C: "enter main phase 1",
                 0x0D: "enter battle phase", 0x0E: "enter main phase 2", 0x0F: "enter end phase",
                 0x21: "player flag bit <a> = <b>", 0x27: "field cursor to location <a> (card <b>)",
                 0x29: "set slot flag bit", 0x2C: "card ref <b> to slot <a> as a trap monster (param <c>)",
                 0x2D: "announce activation: slot <a>, card <b>, ref <c>", 0x34: "turn slot <a> face-up (<b>), reason <c>",
                 0x35: "equip", 0x39: "set slot param", 0x43: "place card on field",
                 0x44: "finalize summon: slot <a>, type bits <b>, tributes <c>", 0x56: "draw <b> cards",
                 0x61: "show summon declaration: card <a>, position <b>, kind <c>", 0x67: "turn limit reached",
                 0x68: "relay to UI event 0x42 (legacy tutorial record)"}
# UI events (duel_core_post_ui_event, rel_duel_eng 0x09be1400) as seen by the tutorial's hook; wait_event and
# on_event name them. 66 also stands for "menu closed" (rel_tutorial +0x38a8 checks rel_duel_draw for it).
UI_EVENTS = {4: "action request", 5: "phase banner (side, phase)", 6: "turn change", 10: "attack selection",
             13: "battle damage shown", 26: "card moved", 34: "activation shown", 46: "Fusion Summon",
             54: "dialog or menu (kind, ...)", 55: "card list opened", 66: "menu closed / UI event 0x42"}


def cmd_parse(blob):
    """[(offset, word0, a, b, c)] up to and including the terminating record whose word0 is 0."""
    if len(blob) % RECORD.size:
        raise ValueError(f"size {len(blob)} is not a multiple of 8")
    records = []
    for offset in range(0, len(blob), RECORD.size):
        records.append((offset,) + RECORD.unpack_from(blob, offset))
        if records[-1][1] == 0:
            if offset + RECORD.size != len(blob):
                raise ValueError(f"end record at {offset:#x} is not the last record")
            return records
    raise ValueError("no end record (first word 0)")


def cmd_refs(records):
    """{'text': [...], 'labels': [...], 'gotos': [...], 'resets': [...], 'cards': [...]}."""
    refs = {"text": [], "labels": [], "gotos": [], "resets": [], "cards": []}
    for _, word, a, b, c in records:
        if not word & SCRIPT_FLAG:
            continue
        op = word & 0x3FFF
        if op not in COMMANDS:
            continue
        kinds = COMMANDS[op][2]
        if op == 16 and a == 0:
            kinds = ""  # on_event 0: clears the handler, the label is not used
        for kind, value in zip(kinds, (a, b, c)):
            key = {"t": "text", "l": "gotos", "r": "resets", "c": "cards"}.get(kind)
            if key:
                refs[key].append(value)
        if op == 5:
            refs["labels"].append(a)
    return refs


def check_cmd(name, blob, text_count=None, resets=None):
    """(errors, notes); `resets` is the set of tuto_field_reset numbers present in the archive."""
    try:
        records = cmd_parse(blob)
    except ValueError as error:
        return [f"{name}: {error}"], []
    errors, notes = [], []
    for offset, word, a, b, c in records[:-1]:
        if word & SCRIPT_FLAG and (word & 0x3FFF) not in COMMANDS:
            errors.append(f"{name} {offset:#x}: tutorial opcode {word & 0x3FFF} past the 21-entry table")
        if word & SCRIPT_FLAG and word & SIDE_FLAG:
            errors.append(f"{name} {offset:#x}: both flag bits set")
        if not word & SCRIPT_FLAG:
            code = word & 0x3FFF
            if not 0 < code <= ENGINE_COMMAND_LAST:
                errors.append(f"{name} {offset:#x}: duel-engine code {code:#x} has no handler (1-{ENGINE_COMMAND_LAST:#x})")
            elif code not in DUEL_COMMANDS:
                notes.append(f"{name} {offset:#x}: duel-engine code {code:#x} is not documented")
        elif word & 0x3FFF in (14, 16) and a and a not in UI_EVENTS:
            notes.append(f"{name} {offset:#x}: event {a} is not documented")
    refs = cmd_refs(records)
    if len(set(refs["labels"])) != len(refs["labels"]):
        errors.append(f"{name}: duplicate label")
    for label in refs["gotos"]:
        if label not in refs["labels"]:
            errors.append(f"{name}: jump to missing label {label}")
    if text_count is not None:
        for line in refs["text"]:
            if line >= text_count:
                errors.append(f"{name}: text line {line} past the table ({text_count})")
    if resets is not None:
        for number in refs["resets"]:
            if number not in resets:
                notes.append(f"{name}: load_field {number}: tuto_field_reset{number:02d}.ydq is not in the archive")
    return errors, notes


def cmd_listing(records, text=None, names=str):
    out = []
    for offset, word, a, b, c in records:
        if word == 0:
            out.append(f"{offset:04x}  end")
            continue
        if not word & SCRIPT_FLAG:
            code = word & 0x3FFF
            label = DUEL_COMMANDS.get(code, "")
            out.append(f"{offset:04x}  duel {code:#04x} side {word >> 15}  {a} {b} {c}" + (f"   ; {label}" if label else ""))
            continue
        op = word & 0x3FFF
        name, arg_names, kinds = COMMANDS.get(op, (f"op{op}", ("a", "b", "c"), ""))
        values = (a, b, c)
        parts = [f"{n}={v}" for n, v in zip(arg_names, values)]
        extra = [f"{v}" for v in values[len(arg_names):] if v]
        line = f"{offset:04x}  {name:<13} " + " ".join(parts + (["?" + " ".join(extra)] if extra else []))
        for kind, value in zip(kinds, values):
            if kind == "t" and text is not None and value < len(text):
                line += "  \"" + text[value].replace("\n", "\\n") + "\""
            elif kind == "c" and value > 2:
                line += f"  [{names(value)}]"
        if op == 12:
            line += f"   ; {INPUT_KINDS.get(a, '?')}" + (f" [{names(b)}]" if b > 5 else "")
        elif op in (14, 16) and a:
            line += f"   ; {UI_EVENTS.get(a, '?')}"
        out.append(line)
    return out


# ---------------------------------------------------------------------- deck-tutorial scripts (rel_decktutorial)

DECK_OPS = {0x01: "message", 0x02: "label_text", 0x03: "label_off", 0x04: "panel", 0x05: "highlight",
            0x06: "highlight_off", 0x07: "allow_buttons+next", 0x08: "allow_off", 0x09: "wait_button", 0x0A: "wait",
            0x0B: "show_card", 0x0C: "card_off", 0x0D: "repeat", 0x0E: "repeat_end", 0x0F: "menu_step",
            0x10: "shoulder_hint", 0x11: "shoulder_off", 0x12: "toggle_swap", 0x13: "caption", 0x14: "picture",
            0x15: "picture_off", 0x16: "cursor", 0x17: "end"}


def deck_listing(ops, strings=None):
    out = []
    for offset, op, args in ops:
        line = f"{offset:04x}  {op:02x} {DECK_OPS.get(op, '?'):<18} {args.hex(' ')}"
        if op in decks.TUTORIAL_STRING_ARG and strings is not None:
            index, = struct.unpack_from("<H", args, decks.TUTORIAL_STRING_ARG[op])
            if index < len(strings):
                line += "  \"" + strings[index].replace("\n", "\\n") + "\""
        out.append(line)
    return out


# ---------------------------------------------------------------------- command line

def card_namer(path):
    if path is None:
        return None, str
    cardinfo = _load("cardinfo")
    info = cardinfo.CardInfo(path.read_bytes(), "E")
    known = {info.properties(i)["id"] for i in range(1, info.count)}

    def name(card):
        index = info.index_of(card)
        return f"{card} {info.name(index)}" if index else str(card)
    return known, name


def run_duel(members, args, known, names):
    errors, notes, out = [], [], []
    texts = {}
    for name, blob in members.items():
        match = re.fullmatch(r"tuto_text_(\w)\.bin", name)
        if match:
            errors += check_text(name, blob, match.group(1))
            texts[match.group(1)] = text_table(blob, match.group(1))[1]
    counts = {len(t) for t in texts.values()}
    if len(counts) > 1:
        errors.append(f"text tables differ in line count: {sorted(counts)}")
    text_count = min(counts) if counts else None
    resets = {int(m.group(1)) for n in members for m in [re.fullmatch(r"tuto_field_reset(\d+)\.ydq", n)] if m}
    used_text = []
    fields = cmds = engine = 0
    for name in sorted(members):
        blob = members[name]
        if args.only and args.only not in name:
            continue
        if name.endswith(".ydq"):
            fields += 1
            e, n = check_ydq(name, blob, known)
            errors += e
            notes += n
            out += ydq_listing(name, parse_ydq(blob), names) + [""]
        elif name.startswith("tuto_cmd_"):
            cmds += 1
            e, n = check_cmd(name, blob, text_count, resets)
            errors += e
            notes += n
            if not e:
                records = cmd_parse(blob)
                used_text += cmd_refs(records)["text"]
                engine += sum(1 for r in records[:-1] if not r[1] & SCRIPT_FLAG)
                out += [f"== {name}"] + cmd_listing(records, texts.get(args.lang), names) + [""]
    summary = (f"ok: {fields} duel setups, {cmds} scripts, {len(texts)} text tables of {text_count} lines; "
               f"{len(used_text)} text references to {len(set(used_text))} lines; {engine} duel-engine records")
    return errors, notes, out, summary


# ---------------------------------------------------------------------- legacy set: tutorial/tutorial_<l>.ehp

# Not loaded by the game (docs/formats/tutorial.md, "The tutorial/ directory"). NN_duel_command.bin is a u16
# record count followed by that many 8-byte records (u16 op, a, b, c) with no end record: raw duel-engine
# commands, and tutorial steps wrapped in engine command 0x68 whose a & 0xff is the sub-operation.
LEGACY_TUTORIAL_OP = 0x68
LEGACY_MESSAGE_OP = 0  # 0x68 sub-operation that names a line of NN_message_res.bin in c


def legacy_parse(blob):
    """[(offset, word0, a, b, c)] of a legacy NN_duel_command.bin."""
    if len(blob) < 2:
        raise ValueError("shorter than the record count")
    count, = struct.unpack_from("<H", blob, 0)
    if 2 + RECORD.size * count != len(blob):
        raise ValueError(f"record count {count} does not match the size {len(blob)}")
    return [(2 + RECORD.size * i,) + RECORD.unpack_from(blob, 2 + RECORD.size * i) for i in range(count)]


def legacy_message_count(blob):
    """NN_message_res.bin is a headed string table (layout A, no end offset): u32 count first."""
    count, table = struct.unpack_from("<II", blob, 0)
    if table != 12:
        raise ValueError("not a headed string table")
    return count


def check_legacy(name, blob, message_count=None):
    try:
        records = legacy_parse(blob)
    except ValueError as error:
        return [f"{name}: {error}"], []
    errors = []
    for offset, word, a, b, c in records:
        code = word & 0x7FFF
        if not 0 < code <= ENGINE_COMMAND_LAST:
            errors.append(f"{name} {offset:#x}: duel-engine code {code:#x} has no handler")
        if code == LEGACY_TUTORIAL_OP and a & 0xFF == LEGACY_MESSAGE_OP and message_count is not None \
                and c >= message_count:
            errors.append(f"{name} {offset:#x}: message {c} past the table ({message_count})")
    return errors, records


def run_legacy(members, args, known, names):
    errors, notes, out = [], [], []
    setups = scripts = total = wrapped = 0
    for name in sorted(members):
        blob = members[name]
        if args.only and args.only not in name:
            continue
        if name.endswith(".txt"):
            setups += 1
            e, n = check_ydq(name, blob, known)
            errors += e
            notes += n
            out += ydq_listing(name, parse_ydq(blob), names) + [""]
        elif name.endswith("_duel_command.bin"):
            scripts += 1
            table = name.replace("_duel_command.bin", "_message_res.bin")
            count = None
            if table in members:
                try:
                    count = legacy_message_count(members[table])
                except ValueError as error:
                    errors.append(f"{table}: {error}")
            else:
                errors.append(f"{name}: no {table}")
            e, records = check_legacy(name, blob, count)
            errors += e
            total += len(records)
            wrapped += sum(1 for r in records if r[1] & 0x7FFF == LEGACY_TUTORIAL_OP)
            out.append(f"== {name}")
            for offset, word, a, b, c in records:
                code = word & 0x7FFF
                label = f"tutorial sub {a & 0xFF} ({a >> 8})" if code == LEGACY_TUTORIAL_OP else DUEL_COMMANDS.get(code, "")
                out.append(f"{offset:04x}  duel {code:#04x} side {word >> 15}  {a} {b} {c}   ; {label}")
            out.append("")
    summary = (f"ok: legacy tutorial set (not loaded by the game): {setups} duel setups, {scripts} scripts of "
               f"{total} records ({wrapped} wrapped in command 0x68)")
    return errors, notes, out, summary


def run_deck(members, args, known, names):
    errors, out = [], []
    strings = None
    table = f"strTbl_{args.lang}.bin"
    if table in members:
        strings = decks.string_table(members[table])
    total = 0
    for name in sorted(members):
        if not re.fullmatch(r"deck_tutorial\d+\.bin", name) or (args.only and args.only not in name):
            continue
        try:
            ops = decks.tutorial_parse(members[name])
        except ValueError as error:
            errors.append(f"{name}: {error}")
            continue
        total += len(ops)
        for offset, op, arguments in ops:
            if op == decks.TUTORIAL_CARD_OP and known is not None:
                card, = struct.unpack_from("<H", arguments, 0)
                if card not in known:
                    errors.append(f"{name} {offset:#x}: unknown card {card}")
        if strings is not None and any(s >= len(strings) for s in decks.tutorial_strings(ops)):
            errors.append(f"{name}: string index past {table}")
        out += [f"== {name}"] + deck_listing(ops, strings) + [""]
    return errors, [], out, f"ok: deck tutorial, {total} instructions"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read and check the duel and deck-building tutorial data.")
    parser.add_argument("archives", type=Path, nargs="+",
                        help="d_tutorial/tutorial.ehp, deck/tutorial.ehp and/or tutorial/tutorial_*.ehp")
    parser.add_argument("--check", action="store_true", help="only run the structural checks")
    parser.add_argument("--notes", action="store_true", help="with --check, also print facts the game ignores")
    parser.add_argument("--lang", default="e", help="text language for the listing (e f g i j s)")
    parser.add_argument("--only", help="only members whose name contains this text")
    parser.add_argument("--cardinfo", type=Path, help="duelsys/cardinfo_eng.ehp: check ids and print names")
    parser.add_argument("-o", "--output", type=Path, help="write the listing here (keep it out of git)")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    known, names = card_namer(args.cardinfo)
    errors, notes, out, summaries = [], [], [], []
    for path in args.archives:
        members = dict(ehp.parse(path.read_bytes()))
        if any(n.endswith("_field_set.txt") for n in members):
            result = run_legacy(members, args, known, names)
        elif any(n.startswith("tuto_") for n in members):
            result = run_duel(members, args, known, names)
        elif any(n.startswith("deck_tutorial") for n in members):
            result = run_deck(members, args, known, names)
        else:
            errors.append(f"{path}: not a duel-, deck- or legacy tutorial archive")
            continue
        errors += [f"{path.name}: {e}" for e in result[0]]
        notes += result[1]
        out += result[2]
        summaries.append(result[3] + (f" ({len(result[1])} notes)" if result[1] else ""))
    if args.check:
        print("\n".join(errors) if errors else "\n".join(summaries))
        if args.notes:
            print("\n".join("note: " + n for n in notes))
        return 1 if errors else 0
    text = "\n".join(out) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
