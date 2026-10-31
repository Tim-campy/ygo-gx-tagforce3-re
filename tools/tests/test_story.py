#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/story.py on hand-built archives (no game data). Run with: python3 -I tools/tests/test_story.py"""

import contextlib
import csv
import importlib.util
import io
import struct
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_story", Path(__file__).resolve().parents[1] / "story.py")
story = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(story)

LINES = ["Hello, 《PLAYER》!", "", "Two\nrows with $C9colour$C0", "A \\ backslash"]
SYSMSG = ["Saved."]


def table(lines):
    """(index member, text member): u32 offsets in UTF-16 code units plus a sentinel, NUL-terminated strings."""
    offsets, text = [], b""
    for line in lines:
        offsets.append(len(text) // 2)
        text += line.encode("utf-16-le") + b"\0\0"
    offsets.append(len(text) // 2)
    return struct.pack(f"<{len(offsets)}I", *offsets), text


def text_archive(lines=LINES, language="x"):
    eve_i, eve_l = table(lines)
    sys_i, sys_l = table(SYSMSG)
    members = {f"EveI{language}.bin": eve_i, f"EveL{language}.bin": eve_l,
               f"SysMsgI{language}.bin": sys_i, f"SysMsgL{language}.bin": sys_l}
    return story.ehp.build(sorted(members.items(), key=lambda item: item[0].lower()))


def ins(*fields):
    return struct.pack("<5H", *(list(fields) + [0] * (5 - len(fields))))


END = ins(0)
# Record 0: header, two talk lines, end. Record 1: header, narration, a one-option menu (choice, case 1,
# case 11), end.
RECORDS = [
    [ins(1, 201, 1, 1), ins(50001, 4, 7, 0, 0), ins(50002, 3, 13, 0, 1), END],
    [ins(1, 201, 1, 2), ins(50008, 0, 0, 0, 2), ins(50011, 0, 0, 0, 3), ins(50012, 1), ins(50012, 11), END],
]
# A record with set-up, an if block, a two-way menu and a jump to record 0.
CONTROL = [ins(1, 7, 1, 1), ins(50158, 3, 2), ins(50023, 54, 1), ins(50090, 54, 2), ins(50056),
           ins(50011, 0, 0, 0, 4), ins(50012, 1), ins(50086, 500), ins(50012, 2), ins(50087, 100),
           ins(50012, 11), ins(50138, 201, 1, 1), END]


def event_archive(records=RECORDS):
    code, starts = b"", []
    for record in records:
        starts.append(len(code) // 10)
        code += b"".join(record)
    members = {"EveB.bin": code, "EveBI.bin": struct.pack(f"<{len(starts)}I", *starts)}
    return story.ehp.build(sorted(members.items(), key=lambda item: item[0].lower()))


class TextTest(unittest.TestCase):
    def test_lines_and_language(self):
        tables, language = story.text_tables(text_archive())
        self.assertEqual(language, "x")
        self.assertEqual(tables["Eve"].lines(), LINES)
        self.assertEqual(tables["SysMsg"].lines(), SYSMSG)
        self.assertEqual(tables["Eve"].check(), [])

    def test_check_catches_bad_sentinel_and_missing_nul(self):
        index, text = table(LINES)
        self.assertTrue(story.TextTable(index, text + b"\0\0").check())
        broken = bytearray(text)
        broken[2 * len(LINES[0])] = ord("?")  # overwrite the NUL of line 0
        self.assertTrue(any("NUL" in p for p in story.TextTable(index, bytes(broken)).check()))

    def test_escape_round_trip(self):
        for line in LINES:
            self.assertEqual(story.unescape(story.escape(line)), line)
            self.assertNotIn("\n", story.escape(line))

    def test_cli_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, out = Path(tmp) / "story_scr_x.ehp", Path(tmp) / "lines.csv"
            path.write_bytes(text_archive())
            with contextlib.redirect_stdout(io.StringIO()) as printed:
                self.assertEqual(story.main(["text", str(path), "--check"]), 0)
            self.assertIn("Eve 4, SysMsg 1 lines", printed.getvalue())
            self.assertEqual(story.main(["text", str(path), "-o", str(out)]), 0)
            with open(out, encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 5)
            self.assertEqual([story.unescape(r["text"]) for r in rows[:4]], LINES)
            self.assertEqual((rows[4]["table"], rows[4]["language"], rows[4]["line"]), ("SysMsg", "x", "0"))


class EventTest(unittest.TestCase):
    def test_records_and_references(self):
        program = story.Events(event_archive())
        self.assertEqual(program.starts, (0, 4))
        self.assertEqual(program.record_span(1), (4, 10))
        self.assertEqual(program.text_references(), [(1, 0), (2, 1), (5, 2), (6, 3)])
        self.assertEqual(program.check(len(LINES)), [])

    def test_check_catches_problems(self):
        missing_end = [RECORDS[0][:-1], RECORDS[1]]
        self.assertTrue(any("end" in p for p in story.Events(event_archive(missing_end)).check()))
        # Lines 0..3 exist but only 0..2 are referenced.
        short = [RECORDS[0], [RECORDS[1][0], RECORDS[1][1], END]]
        self.assertTrue(any("exactly once" in p for p in story.Events(event_archive(short)).check(4)))
        repeated = [RECORDS[0], [ins(1, 201, 1, 1)] + RECORDS[1][1:]]
        self.assertTrue(any("repeated" in p for p in story.Events(event_archive(repeated)).check()))

    def test_cli_dump_with_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            events, text, out = Path(tmp) / "story_scr_b.ehp", Path(tmp) / "story_scr_x.ehp", Path(tmp) / "e.csv"
            events.write_bytes(event_archive())
            text.write_bytes(text_archive())
            with contextlib.redirect_stdout(io.StringIO()) as printed:
                self.assertEqual(story.main(["events", str(events), "--text", str(text), "--check"]), 0)
            self.assertIn("2 records, 10 instructions, 4 text references", printed.getvalue())
            self.assertEqual(story.main(["events", str(events), "--text", str(text), "-o", str(out)]), 0)
            with open(out, encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 10)
            self.assertEqual((rows[1]["opcode"], rows[1]["name"], rows[1]["a1"]), ("50001", "talk", "4"))
            self.assertEqual(story.unescape(rows[1]["text"]), LINES[0])
            self.assertEqual((rows[0]["name"], rows[3]["name"], rows[7]["text"]), ("header", "end", ""))
            self.assertEqual((rows[1]["args"], rows[7]["name"], rows[7]["args"]),
                             ("speaker=4 expression=7 flag=0 line=0", "case", "n=1"))

    def test_names_and_arguments(self):
        self.assertEqual(story.opcode_name(50023), "if_flag")
        self.assertEqual(story.opcode_name(50056), "endif")
        self.assertEqual(story.opcode_name(50024), "if_50024")
        self.assertEqual(story.opcode_name(50154), "op_50154")
        self.assertEqual(story.opcode_name(50157), "nop")
        self.assertEqual(story.format_args((50162, 16, 3, 0, 0)), "char=16 deck=3")
        self.assertEqual(story.opcode_name(50033), "nop")
        self.assertEqual(story.format_args((50022, 200, 3, 0, 0)), "value=200 cmp=>=")
        self.assertEqual(story.format_args((50090, 54, 2, 0, 0)), "flag=54 op=clear")
        self.assertEqual(story.format_args((50154, 0, 9, 0, 0)), "a2=9")  # undecoded: non-zero arguments
        self.assertEqual(story.format_args((50175, 0, 0, 5, 0)), "a3=5")  # unread argument that is set

    def test_control_structure_and_listing(self):
        lines = LINES + ["Yes\nNo\n"]
        program = story.Events(event_archive(RECORDS[:1] + [CONTROL]))
        self.assertEqual(program.control_problems(), [])
        self.assertEqual(program.keys(), {(201, 1, 1): 0, (7, 1, 1): 1})
        eve = story.TextTable(*table(lines))
        listing = program.listing(1, eve)
        self.assertEqual(listing[1], "   1  scene_map map=3 b=2  [set-up]")
        self.assertEqual(listing[2], "   2  if_flag flag=54 test=true")
        self.assertEqual(listing[3], "   3    set_flag flag=54 op=clear")
        self.assertEqual(listing[4], "   4  endif")
        self.assertEqual(listing[5], "   5  choice line=4  | Yes\\nNo\\n")
        self.assertEqual([listing[k][6:] for k in (6, 7, 8, 9, 10)],
                         ["case n=1", "  dp_add amount=500", "case n=2", "  dp_sub amount=100", "case n=11"])
        self.assertEqual(listing[11], "  11  goto key_a=201 key_b=1 key_c=1  -> record 0")

    def test_control_problems(self):
        def problems(body):
            return story.Events(event_archive([RECORDS[0], [ins(1, 7, 1, 1)] + body + [END]])).control_problems()
        self.assertTrue(any("not closed" in p for p in problems([ins(50023, 1, 1)])))
        self.assertTrue(any("innermost" in p for p in problems([ins(50023, 1, 1), ins(50052)])))
        self.assertTrue(any("case 1" in p for p in problems([ins(50011, 0, 0, 0, 0), ins(50007)])))
        self.assertTrue(any("case groups" in p for p in problems([ins(50012, 1), ins(50012, 2)])))
        self.assertTrue(any("missing key" in p for p in problems([ins(50138, 9, 9, 9)])))
        self.assertEqual(problems([ins(50131, 0, 0, 0), ins(50132, 201, 1, 1)]), [])

    def test_cli_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            events, out = Path(tmp) / "story_scr_b.ehp", Path(tmp) / "e.txt"
            events.write_bytes(event_archive(RECORDS[:1] + [CONTROL]))
            self.assertEqual(story.main(["events", str(events), "--list", "--record", "1", "-o", str(out)]), 0)
            text = out.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("record 1 key 7,1,1\n   0  header key_a=7 key_b=1 key_c=1\n"))
            self.assertIn("-> record 0", text)
            self.assertNotIn("record 0 key", text)


if __name__ == "__main__":
    unittest.main()
