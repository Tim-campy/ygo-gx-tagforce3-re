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
# Record 0: header, two talk lines, end. Record 1: header, narration, choice, a non-text opcode, end.
RECORDS = [
    [ins(1, 201, 1, 1), ins(50001, 4, 7, 0, 0), ins(50002, 3, 13, 0, 1), END],
    [ins(1, 201, 1, 2), ins(50008, 0, 0, 0, 2), ins(50011, 0, 0, 0, 3), ins(50012, 1), END],
]


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
        self.assertEqual(program.record_span(1), (4, 9))
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
            self.assertIn("2 records, 9 instructions, 4 text references", printed.getvalue())
            self.assertEqual(story.main(["events", str(events), "--text", str(text), "-o", str(out)]), 0)
            with open(out, encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 9)
            self.assertEqual((rows[1]["opcode"], rows[1]["name"], rows[1]["a1"]), ("50001", "talk", "4"))
            self.assertEqual(story.unescape(rows[1]["text"]), LINES[0])
            self.assertEqual((rows[0]["name"], rows[3]["name"], rows[7]["text"]), ("header", "end", ""))


if __name__ == "__main__":
    unittest.main()
