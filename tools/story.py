#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read the story text and event bytecode in script/story_scr_*.ehp. See docs/formats/story.md.

  story.py text story_scr_e.ehp [-o lines.csv] [--check]
      Export the Eve and SysMsg line tables of one language to CSV (newlines written as \\n).
  story.py events story_scr_b.ehp [--text story_scr_e.ehp] [-o events.csv] [--check]
                  [--list] [--record N ...]
      Dump the event bytecode (one row per instruction, with symbolic opcode names and named
      arguments); with --text, attach the referenced lines and check that every line is referenced
      exactly once. --list writes a readable disassembly (indented blocks, resolved event keys)
      instead of CSV. --check also checks the block structure and that every event key exists.

Output goes to stdout or a file; keep it under extracted/, never in git.
"""

import argparse
import csv
import importlib.util
import struct
import sys
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_ehp", Path(__file__).resolve().parent / "ehp.py")
ehp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ehp)

TABLES = ("Eve", "SysMsg")  # each has an index member <name>I<l>.bin and a text member <name>L<l>.bin
INSTRUCTION = struct.Struct("<5H")  # opcode, then four u16 arguments
OP_END = 0  # all-zero instruction closing every record
OP_HEADER = 1  # first instruction of every record: (key_a, key_b, key_c, 0)
# Opcodes whose fourth argument is an Eve line number. Together they reference every line exactly
# once, in ascending order (checked on the European disc).
TEXT_OPCODES = {50001: "talk", 50002: "talk_alt", 50008: "narrate", 50009: "narrate_named", 50011: "choice"}

# The interpreter in gmodule/rel_story.prx (0xb9f4, module offset) dispatches 50001..50176 through a
# 176-entry jump table at 0x19240. Names and argument roles below come from the handlers; the
# confidence of each is in docs/formats/story.md. An argument name of None means the handler does not
# read it. "test" is 1 = true / 2 = false; "cmp" is 1 ==, 2 !=, 3 >=, 4 <; "key" is a1..a3 read as an
# event header key.
IF_FIRST, IF_LAST, ENDIF_DELTA = 50014, 50046, 33  # a false test skips to the opener + 33 (50047..50079)
OP_CHOICE, OP_CASE, OP_RANDOM_CASE, CASE_END = 50011, 50012, 50013, 11
OP_GOTO = 50138
KEY_OPCODES = (50131, 50132, 50133, 50134, OP_GOTO)  # a1..a3 name another record's header key
SETUP_FIRST, SETUP_LAST = 50158, 50172  # run only in the set-up pass at the start of a record
NOP_OPCODES = (50031, 50033, 50034, 50036, 50041, 50046, 50088, 50089, 50092, 50093, 50095, 50102,
               50107, 50109, 50110, 50135, 50136, 50142, 50143, 50146, 50147, 50163, 50165, 50172,
               50173, 50174, 50157)  # handler is a bare return (50157: 0xff30)
OPCODES = {
    OP_END: ("end", ()),
    OP_HEADER: ("header", ("key_a", "key_b", "key_c")),
    50001: ("talk", ("speaker", "expression", "flag", "line")),
    50002: ("talk_alt", ("speaker", "expression", "flag", "line")),
    50003: ("portrait", ("speaker", "expression", "flag")),
    50004: ("talk_pair", ("speaker", "expression")),
    50005: ("talk_pair_b", ("speaker", "expression")),
    50006: ("close_talk_of", ("speaker",)),
    50007: ("close_talk", ()),
    50008: ("narrate", (None, None, None, "line")),
    50009: ("narrate_named", ("speaker", None, None, "line")),
    50010: ("close_narration", ()),
    OP_CHOICE: ("choice", (None, None, None, "line")),
    OP_CASE: ("case", ("n",)),
    OP_RANDOM_CASE: ("random_case", ("n", "count")),
    50014: ("if_counter", ("index", "test")),
    50015: ("if_counter_b", ("index", "test")),
    50016: ("if_value_34", ("value", "test")),
    50017: ("if_value_38", ("value", "test")),
    50018: ("if_counter_b_total", ("test",)),
    50019: ("if_value_3c", ("value", "test")),
    50020: ("if_char_points", ("char", "value", "cmp")),
    50022: ("if_dp", ("value", "cmp")),
    50023: ("if_flag", ("flag", "test")),
    50028: ("if_card_marked", ("card", "test")),
    50037: ("if_partner", ("char", "test")),
    50080: ("counter_step", ("index", "direction")),
    50081: ("counter_b_step", ("index", "direction")),
    50084: ("partner_points_add", ("amount",)),
    50085: ("partner_points_sub", ("amount",)),
    50086: ("dp_add", ("amount",)),
    50087: ("dp_sub", ("amount",)),
    50090: ("set_flag", ("flag", "op")),
    50091: ("set_flag_b", ("flag", "op")),
    50094: ("advance_counter", ()),
    50097: ("give_card", ("card", "show")),
    50098: ("give_random_card", ("pack", "rarity_lo", "rarity_hi")),
    50099: ("give_booster", ("pack", "rarity_lo", "rarity_hi")),
    50100: ("mark_card", ("card",)),
    50103: ("set_pack_state", ("pack", "state")),
    50104: ("advance_time", ("slots",)),  # 0 = one slot
    50105: ("set_time_slot", ("slot",)),
    50106: ("next_day", ()),
    50108: ("exit_118", ()),
    50111: ("picture", ("id", "op")),
    50112: ("fade_in", ("frames", "flag")),
    50113: ("fade_out", ("frames", "flag")),
    50114: ("npc_appear", ("char",)),
    50115: ("npc_leave", ("char",)),
    50116: ("screen_effect", (None, "kind")),
    50117: ("screen_effect_end", ()),
    50118: ("hud_marker", ("target",)),  # 1 = off
    50119: ("duel_single", ("opponent", "variant")),
    50120: ("duel_tag_opponent_a", ("char", "variant")),
    50121: ("duel_tag_opponent_b", ("char", "variant")),
    50122: ("duel_tag_partner", (None, "variant")),
    50126: ("duel_target_single", ()),  # the character the Duel command was used on
    50127: ("duel_target_by_partner", ()),
    50128: ("duel_target_tag", ()),
    50129: ("duel_rules", ("a", "b", "c")),
    50130: ("duel_option", ("a", "b")),
    50131: ("duel_then_a", ("key_a", "key_b", "key_c")),
    50132: ("duel_then_b", ("key_a", "key_b", "key_c")),
    50133: ("duel_then_c", ("key_a", "key_b", "key_c")),
    50134: ("duel_then_d", ("key_a", "key_b", "key_c")),
    50137: ("finish_partner_story", ()),
    OP_GOTO: ("goto", ("key_a", "key_b", "key_c")),
    50139: ("exit_111", ()),
    50140: ("exit_112", ()),
    50144: ("preload_portrait", ("char",)),
    50145: ("halt", ()),
    50148: ("series_win", ()),
    50149: ("series_loss", ()),
    50150: ("exit_102", ("char",)),
    50151: ("buy_sandwich", ()),  # a1 (26/27) is not read by the handler
    50152: ("exit_103", ()),
    50153: ("sound_effect", ("id",)),
    50155: ("bgm", ("id",)),
    50156: ("bgm_stop", ()),
    50158: ("scene_map", ("map", "b")),
    50159: ("scene_player", ("direction", "x", "y")),
    50160: ("npc_set_variant", ("char", "row")),
    50161: ("npc_set_variant_b", ("char", "row")),
    50162: ("npc_deck", ("char", "deck")),
    50166: ("npc_event", ("char", "group", "number")),
    50167: ("scene_bgm", ("id",)),
    50168: ("npc_position", ("char", "x", "y")),
    50169: ("npc_direction", ("char", "direction", "c")),
    50170: ("npc_remark", ("char", "remark")),
    50171: ("npc_event_b", ("char", "group", "number")),
    50175: ("end_event", ()),
    50176: ("exit_select", ("n",)),
}
for _op in range(IF_FIRST + ENDIF_DELTA, IF_LAST + ENDIF_DELTA + 1):
    OPCODES[_op] = ("endif", ())
for _op in NOP_OPCODES:
    OPCODES.setdefault(_op, ("nop", ()))
ENUMS = {"test": {1: "true", 2: "false"}, "cmp": {1: "==", 2: "!=", 3: ">=", 4: "<"},
         "op": {1: "set", 2: "clear"}, "direction": {1: "up", 2: "down"}}


def opcode_name(opcode):
    if opcode in OPCODES:
        return OPCODES[opcode][0]
    if IF_FIRST <= opcode <= IF_LAST:
        return f"if_{opcode}"
    return f"op_{opcode}"


def format_args(instruction):
    """'name=value …' for the arguments the handler reads; unknown opcodes show the non-zero ones."""
    opcode, args = instruction[0], instruction[1:]
    names = OPCODES.get(opcode, (None, ()))[1]
    parts = []
    for k, value in enumerate(args):
        name = names[k] if k < len(names) else None
        if name is None:
            if value:  # an argument the handler does not read, or an opcode not decoded yet
                parts.append(f"a{k + 1}={value}")
        else:
            parts.append(f"{name}={ENUMS.get(name, {}).get(value, value)}")
    return " ".join(parts)


# ---------------------------------------------------------------------- text tables

def escape(text):
    """Make a line fit one CSV cell: backslash and newline become two-character escapes."""
    return text.replace("\\", "\\\\").replace("\n", "\\n")


def unescape(text):
    out, i = [], 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text):
            out.append("\n" if text[i + 1] == "n" else text[i + 1])
            i += 2
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


class TextTable:
    """u32 offsets in UTF-16 code units (the last one is a sentinel), and a pool of NUL-terminated
    UTF-16LE strings."""

    def __init__(self, index_bytes, text_bytes):
        if len(index_bytes) % 4 or len(index_bytes) < 4:
            raise ValueError("index member is not a whole number of u32 offsets")
        self.offsets = struct.unpack(f"<{len(index_bytes) // 4}I", index_bytes)
        self.text = text_bytes

    def __len__(self):
        return len(self.offsets) - 1

    def raw(self, number):
        return self.text[2 * self.offsets[number]:2 * self.offsets[number + 1]]

    def line(self, number):
        return self.raw(number)[:-2].decode("utf-16-le")

    def lines(self):
        return [self.line(n) for n in range(len(self))]

    def check(self, name="table"):
        problems = []
        if self.offsets[0] != 0:
            problems.append(f"{name}: first offset is not 0")
        if self.offsets[-1] * 2 != len(self.text):
            problems.append(f"{name}: sentinel {self.offsets[-1]} does not mark the end of the text "
                            f"({len(self.text) // 2} code units)")
        for n in range(len(self)):
            if self.offsets[n + 1] <= self.offsets[n]:
                problems.append(f"{name} line {n}: offsets not strictly ascending")
                continue
            raw = self.raw(n)
            if raw[-2:] != b"\0\0" or b"\0\0" in [raw[i:i + 2] for i in range(0, len(raw) - 2, 2)]:
                problems.append(f"{name} line {n}: not exactly one NUL at the end")
                continue
            try:
                raw.decode("utf-16-le")
            except UnicodeDecodeError as error:
                problems.append(f"{name} line {n}: {error}")
        return problems


def text_tables(archive_bytes):
    """{table name: TextTable} and the language letter of a story_scr_<l>.ehp archive."""
    members = dict(ehp.parse(archive_bytes))
    found, language = {}, None
    for name in members:
        for table in TABLES:
            prefix = f"{table}I"
            if name.startswith(prefix) and name.endswith(".bin") and len(name) == len(prefix) + 5:
                language = name[len(prefix)]
                found[table] = TextTable(members[name], members[f"{table}L{language}.bin"])
    if not found:
        raise ValueError("no EveI/SysMsgI members: not a story text archive")
    return found, language


# ---------------------------------------------------------------------- event bytecode

class Events:
    """EveB.bin: 10-byte instructions; EveBI.bin: u32 index of the first instruction of each record."""

    def __init__(self, archive_bytes):
        members = dict(ehp.parse(archive_bytes))
        if "EveB.bin" not in members or "EveBI.bin" not in members:
            raise ValueError("no EveB/EveBI members: not the event bytecode archive")
        code, index = members["EveB.bin"], members["EveBI.bin"]
        if len(code) % INSTRUCTION.size or len(index) % 4:
            raise ValueError("EveB/EveBI sizes are not whole instructions / offsets")
        self.instructions = [INSTRUCTION.unpack_from(code, i) for i in range(0, len(code), INSTRUCTION.size)]
        self.starts = struct.unpack(f"<{len(index) // 4}I", index)

    def record_span(self, record):
        end = self.starts[record + 1] if record + 1 < len(self.starts) else len(self.instructions)
        return self.starts[record], end

    def rows(self):
        """(record, position, opcode, a1, a2, a3, a4) for every instruction."""
        for record in range(len(self.starts)):
            start, end = self.record_span(record)
            for position in range(start, end):
                yield (record, position) + self.instructions[position]

    def text_references(self):
        """[(position, line number)] in bytecode order."""
        return [(p, ins[4]) for p, ins in enumerate(self.instructions) if ins[0] in TEXT_OPCODES]

    def check(self, line_count=None):
        problems = []
        say = problems.append
        if not self.starts or self.starts[0] != 0:
            say("EveBI does not start at instruction 0")
        if any(b <= a for a, b in zip(self.starts, self.starts[1:])) or \
                (self.starts and self.starts[-1] >= len(self.instructions)):
            say("EveBI is not strictly ascending inside EveB")
            return problems
        keys = set()
        for record in range(len(self.starts)):
            start, end = self.record_span(record)
            head, last = self.instructions[start], self.instructions[end - 1]
            if head[0] != OP_HEADER or head[4] != 0:
                say(f"record {record}: does not start with a header instruction")
            if last != (OP_END, 0, 0, 0, 0) or end - start < 2:
                say(f"record {record}: does not end with the all-zero instruction")
            if any(ins[0] in (OP_HEADER, OP_END) for ins in self.instructions[start + 1:end - 1]):
                say(f"record {record}: header or end opcode inside the body")
            if head[1:4] in keys:
                say(f"record {record}: header key {head[1:4]} repeated")
            keys.add(head[1:4])
        if line_count is not None:
            lines = [line for _, line in self.text_references()]
            if sorted(lines) != list(range(line_count)):
                say(f"text references do not cover lines 0..{line_count - 1} exactly once "
                    f"({len(lines)} references, {len(set(lines))} distinct)")
            if lines != sorted(lines):
                say("text references are not in ascending order")
        problems += self.control_problems()
        return problems

    def keys(self):
        """{header key (a1, a2, a3): record}; the interpreter finds a record by this key (0xa67c)."""
        return {self.instructions[self.starts[r]][1:4]: r for r in range(len(self.starts))}

    def control_problems(self):
        """Block structure: if/endif nesting, menus and case groups, and keys naming existing records."""
        problems, keys = [], self.keys()
        for record in range(len(self.starts)):
            start, end = self.record_span(record)
            body = self.instructions[start:end]
            stack, opened = [], {OP_CASE: 0, OP_RANDOM_CASE: 0}
            for k, ins in enumerate(body):
                op = ins[0]
                if IF_FIRST <= op <= IF_LAST:
                    stack.append(op + ENDIF_DELTA)
                elif IF_FIRST + ENDIF_DELTA <= op <= IF_LAST + ENDIF_DELTA:
                    if not stack or stack.pop() != op:
                        problems.append(f"record {record}: endif {op} at {k} does not close the innermost if")
                elif op == OP_CHOICE and (k + 1 >= len(body) or body[k + 1][:2] != (OP_CASE, 1)):
                    problems.append(f"record {record}: choice at {k} is not followed by case 1")
                elif op in opened and ins[1] in (1, CASE_END):
                    opened[op] += 1 if ins[1] == 1 else -1
                elif op in KEY_OPCODES and any(ins[1:4]) and ins[1:4] not in keys:
                    problems.append(f"record {record}: {opcode_name(op)} at {k} names missing key {ins[1:4]}")
            if stack:
                problems.append(f"record {record}: {len(stack)} if block(s) not closed")
            if any(opened.values()):
                problems.append(f"record {record}: case groups not closed by case {CASE_END}")
        return problems

    def listing(self, record, eve=None):
        """Lines of a readable disassembly of one record: index, symbolic name, named arguments,
        indentation for if blocks and case groups, the record a key points to, and optionally the text."""
        start, end = self.record_span(record)
        keys = self.keys()
        out, depth = [], 0
        for k, ins in enumerate(self.instructions[start:end]):
            op = ins[0]
            if (IF_FIRST + ENDIF_DELTA <= op <= IF_LAST + ENDIF_DELTA) or \
                    (op in (OP_CASE, OP_RANDOM_CASE) and ins[1] != 1):
                depth = max(depth - 1, 0)
            text = f"{k:4d}  {'  ' * depth}{opcode_name(op)}"
            args = format_args(ins)
            if args:
                text += " " + args
            if op in KEY_OPCODES and ins[1:4] in keys:
                text += f"  -> record {keys[ins[1:4]]}"
            if SETUP_FIRST <= op <= SETUP_LAST and k:
                text += "  [set-up]"
            if eve is not None and op in TEXT_OPCODES:
                text += "  | " + escape(eve.line(ins[4]))
            out.append(text)
            if IF_FIRST <= op <= IF_LAST or (op in (OP_CASE, OP_RANDOM_CASE) and ins[1] != CASE_END):
                depth += 1
        return out


# ---------------------------------------------------------------------- command line

def open_output(path):
    return open(path, "w", encoding="utf-8", newline="") if path else sys.stdout


def main(argv=None):
    parser = argparse.ArgumentParser(description="Story text and event bytecode of script/story_scr_*.ehp.")
    sub = parser.add_subparsers(dest="command", required=True)
    text = sub.add_parser("text", help="export one language's line tables to CSV")
    text.add_argument("archive", type=Path, help="script/story_scr_<l>.ehp")
    events = sub.add_parser("events", help="dump the event bytecode")
    events.add_argument("archive", type=Path, help="script/story_scr_b.ehp")
    events.add_argument("--text", type=Path, help="a story_scr_<l>.ehp whose Eve lines to attach and check")
    events.add_argument("--list", action="store_true", help="write a readable disassembly instead of CSV")
    events.add_argument("--record", type=int, action="append", help="only this record (repeatable)")
    for command in (text, events):
        command.add_argument("-o", "--output", type=Path, help="write here instead of stdout (keep it out of git)")
        command.add_argument("--check", action="store_true", help="only run the structural checks")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if args.command == "text":
        tables, language = text_tables(args.archive.read_bytes())
        if args.check:
            problems = [p for name, table in tables.items() for p in table.check(name)]
            counts = ", ".join(f"{name} {len(table)}" for name, table in tables.items())
            print("\n".join(problems[:20]) if problems else f"ok: language {language}: {counts} lines")
            return 1 if problems else 0
        out = open_output(args.output)
        try:
            writer = csv.writer(out)
            writer.writerow(["table", "language", "line", "text"])
            for name, table in tables.items():
                for number, line in enumerate(table.lines()):
                    writer.writerow([name, language, number, escape(line)])
        finally:
            if args.output:
                out.close()
        return 0

    program = Events(args.archive.read_bytes())
    eve = text_tables(args.text.read_bytes())[0]["Eve"] if args.text else None
    if args.check:
        problems = program.check(len(eve) if eve else None)
        summary = (f"ok: {len(program.starts)} records, {len(program.instructions)} instructions, "
                   f"{len(program.text_references())} text references")
        print("\n".join(problems[:20]) if problems else summary)
        return 1 if problems else 0
    records = args.record if args.record else range(len(program.starts))
    out = open_output(args.output)
    try:
        if args.list:
            for record in records:
                key = program.instructions[program.starts[record]][1:4]
                out.write(f"record {record} key {key[0]},{key[1]},{key[2]}\n")
                out.write("".join(line + "\n" for line in program.listing(record, eve)) + "\n")
            return 0
        writer = csv.writer(out)
        writer.writerow(["record", "position", "opcode", "a1", "a2", "a3", "a4", "name", "args", "text"])
        for record in records:
            start, end = program.record_span(record)
            for position in range(start, end):
                ins = program.instructions[position]
                line = escape(eve.line(ins[4])) if eve is not None and ins[0] in TEXT_OPCODES else ""
                writer.writerow([record, position, *ins, opcode_name(ins[0]), format_args(ins), line])
    finally:
        if args.output:
            out.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
