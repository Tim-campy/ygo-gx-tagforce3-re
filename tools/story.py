#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read the story text and event bytecode in script/story_scr_*.ehp. See docs/formats/story.md.

  story.py text story_scr_e.ehp [-o lines.csv] [--check]
      Export the Eve and SysMsg line tables of one language to CSV (newlines written as \\n).
  story.py events story_scr_b.ehp [--text story_scr_e.ehp] [-o events.csv] [--check]
      Dump the event bytecode (one row per instruction); with --text, attach the referenced lines
      and check that every line is referenced exactly once.

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
TEXT_OPCODES = {50001: "talk", 50002: "talk_alt", 50008: "narrate", 50009: "talk_intro", 50011: "choice"}


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
        return problems


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
    out = open_output(args.output)
    try:
        writer = csv.writer(out)
        writer.writerow(["record", "position", "opcode", "a1", "a2", "a3", "a4", "name", "text"])
        for row in program.rows():
            opcode = row[2]
            name = TEXT_OPCODES.get(opcode, {OP_HEADER: "header", OP_END: "end"}.get(opcode, ""))
            line = escape(eve.line(row[6])) if eve is not None and opcode in TEXT_OPCODES else ""
            writer.writerow(list(row) + [name, line])
    finally:
        if args.output:
            out.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
