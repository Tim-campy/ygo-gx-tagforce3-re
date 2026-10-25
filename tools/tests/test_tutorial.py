#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/tutorial.py on hand-built data (no game data). Run with: python3 -I tools/tests/test_tutorial.py"""

import contextlib
import importlib.util
import io
import struct
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_tutorial", Path(__file__).resolve().parents[1] / "tutorial.py")
tutorial = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tutorial)

YDQ = "\r\n".join([
    "[DUEL QUESTION]",
    "Turn=3",
    "LimitTurn=2",
    "TurnPlayer=1",
    "Phase=MAIN1",
    "[Player0]",
    "PlayerLP0=4000",
    "CardInHand0=1",  # count lines are not read: this one is wrong on purpose
    "CardInHand0_000=5000\t//\tcomment",
    "CardInHand0_007=5001",  # the index is not read either: entries keep file order
    "CardInDeck0=1",
    "CardInDeck0_000=5002",
    "CardInGame0_002=5003",
    "CardInGame0_002_Face=1",
    "CardInGame0_002_Turn=1",
    "CardInGame0_002_Owner=1",
    "CardInGame0_002_Param=7",
    "CardInGame0_002_Flag=SPECIALSUMMONED",
    "CardInGame0_002_Flag=TRAPMONSTER",
    "CardInFusion0_000=5004",
    "[Player1]",
    "CardInGrave1_000=5005",
    "CardInExclude1_000=5006",
    "[Player2]",
    "CardInHand2_000=5007",
    "CardInGrave2_000=5008",  # players 2/3 share the grave of side p & 1
    "[Equipment]",
    "EquipAct000_Type=UNION",
    "EquipAct000_DstLocate=3",
    "[END]",
    "PlayerLP1=1",  # after [END]: not read
    ""]).encode("cp932")


def records(*rows):
    return b"".join(struct.pack("<4H", *row) for row in rows)


SCRIPT = records(
    (0x4001, 0, 0, 0),  # message text 0
    (0x0027, 2, 0, 0),  # duel command 0x27, side 0
    (0x8056, 0, 5, 0),  # duel command 0x56, side 1
    (0x4005, 1, 0, 0),  # label 1
    (0x4008, 1, 0, 0),  # question text 1
    (0x4007, 2, 1, 0),  # if answer 2 goto 1
    (0x4010, 0, 0, 0),  # on_event 0: clears the handler, label 0 is not a reference
    (0x400C, 6, 4000, 0),  # wait_input kind 6, card 4000
    (0x400A, 0, 0, 0),  # load tuto_field_reset00.ydq
    (0x4006, 1, 0, 0),  # goto 1
    (0, 0, 0, 0))


def text_table(lines, language="e"):
    encoding, nul = ("cp932", b"\0") if language == "j" else ("utf-16-le", b"\0\0")
    blobs = []
    for line in lines:
        raw = line.encode(encoding) + nul
        blobs.append(raw + b"\0" * (-len(raw) % 4))
    position, index = 8 * len(lines), b""
    for blob in blobs:
        index += struct.pack("<II", position, len(blob))
        position += len(blob)
    return index + b"".join(blobs)


def duel_archive(script=SCRIPT, reset=True):
    members = {"tuto_cmd_00.bin": script, "tuto_field_00.ydq": YDQ,
               "tuto_text_e.bin": text_table(["Hello\nthere", "Pick one\nA\nB"]),
               "tuto_text_j.bin": text_table(["こん", "どれ"], "j")}
    if reset:
        members["tuto_field_reset00.ydq"] = YDQ
    return tutorial.ehp.build(sorted(members.items()))


def string_table(strings):
    blobs = [s.encode("utf-16-le") + b"\0\0" for s in strings]
    offsets, position = [], 0
    for blob in blobs:
        offsets.append(position)
        position += len(blob)
    head = struct.pack("<3I", len(strings), 12, 12 + 4 * len(strings))
    return head + struct.pack(f"<{len(strings)}I", *offsets) + b"".join(blobs)


def run(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = tutorial.main(argv)
    return code, out.getvalue()


class YdqTest(unittest.TestCase):
    def test_semantics(self):
        setup = tutorial.parse_ydq(YDQ)
        self.assertTrue(setup["end"])
        self.assertEqual(setup["phase"], (2, "main"))
        self.assertEqual((setup["turn"], setup["limit_turn"], setup["turn_player"]), (2, 3, 1))
        me, you = setup["sides"]
        self.assertEqual((me["lp"], you["lp"]), (4000, tutorial.DEFAULT_LP))
        self.assertEqual(me["hand"], [5000, 5001])
        self.assertEqual(me["deck"], [5002])
        self.assertEqual(me["extra"], [5004])
        self.assertEqual(me["counts"], {"hand": 1, "deck": 1})
        slot = me["field"][2]
        self.assertEqual((slot["card"], slot["face_up"], slot["defense"], slot["param"]), (5003, 1, 1, 7))
        self.assertTrue(slot["owner_other"])
        self.assertEqual(slot["flags"], 0x40 | 0x1000)
        self.assertEqual(you["grave"], [5005])
        self.assertEqual(you["banished"], [5006])
        self.assertEqual(setup["partners"][0]["hand"], [5007])
        self.assertEqual(me["grave"], [5008])
        self.assertEqual(setup["equips"], {0: {"Type": 11, "DstLocate": 3}})
        self.assertEqual(setup["ignored"], [])

    def test_limit_turn_off(self):
        setup = tutorial.parse_ydq(b"LimitTurn=-1\r\nPhase=Draw\r\n[END]\r\n")
        self.assertIsNone(setup["limit_turn"])
        self.assertEqual(setup["phase"], (0, "draw"))

    def test_check(self):
        errors, notes = tutorial.check_ydq("x", YDQ, known={5000, 5001, 5002, 5003, 5004, 5005, 5006, 5008})
        self.assertEqual(errors, [])
        self.assertIn("x: player 0 hand count line says 1, 2 entries", notes)
        errors, _ = tutorial.check_ydq("x", b"Phase=Draw\r\nBogus=1\r\n")
        self.assertTrue(any("unknown line" in e for e in errors))
        self.assertTrue(any("no [END]" in e for e in errors))

    def test_long_lines_are_split(self):
        self.assertEqual([len(x) for x in tutorial.ydq_lines(b"a" * 300 + b"\n")], [254, 47])


class CmdTest(unittest.TestCase):
    def test_parse_and_refs(self):
        rows = tutorial.cmd_parse(SCRIPT)
        self.assertEqual(len(rows), 11)
        refs = tutorial.cmd_refs(rows)
        self.assertEqual(refs["text"], [0, 1])
        self.assertEqual(refs["labels"], [1])
        self.assertEqual(refs["gotos"], [1, 1])
        self.assertEqual(refs["resets"], [0])
        self.assertEqual(tutorial.check_cmd("s", SCRIPT, 2, {0}), ([], []))

    def test_problems(self):
        with self.assertRaises(ValueError):
            tutorial.cmd_parse(SCRIPT[:-8])  # no end record
        with self.assertRaises(ValueError):
            tutorial.cmd_parse(SCRIPT + SCRIPT[:8])  # record after the end
        bad = records((0x4006, 9, 0, 0), (0x4015, 0, 0, 0), (0x4001, 5, 0, 0), (0, 0, 0, 0))
        errors, _ = tutorial.check_cmd("s", bad, 2, set())
        self.assertEqual(len(errors), 3)
        _, notes = tutorial.check_cmd("s", SCRIPT, 2, set())
        self.assertEqual(len(notes), 1)

    def test_listing(self):
        lines = tutorial.cmd_listing(tutorial.cmd_parse(SCRIPT), ["Hi\nthere", "Q"])
        self.assertIn('message       text=0 b=0  "Hi\\nthere"', lines[0])
        self.assertIn("duel 0x56 side 1", lines[2])
        self.assertIn("pick a monster on the field", lines[7])
        self.assertTrue(lines[-1].endswith("end"))


class TextTest(unittest.TestCase):
    def test_tables(self):
        for language, lines in (("e", ["One", "Two lines\nhere", ""]), ("j", ["あ", "いう"])):
            blob = text_table(lines, language)
            self.assertEqual(tutorial.text_table(blob, language)[1], lines)
            self.assertEqual(tutorial.check_text("t", blob, language), [])
        broken = bytearray(text_table(["One", "Two"]))
        broken[8:12] = struct.pack("<I", 0x30)  # second line no longer follows the first
        self.assertTrue(tutorial.check_text("t", bytes(broken), "e"))


class MainTest(unittest.TestCase):
    def test_duel_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tutorial.ehp"
            path.write_bytes(duel_archive())
            code, out = run([str(path), "--check"])
            self.assertEqual(code, 0, out)
            self.assertIn("2 duel setups, 1 scripts, 2 text tables of 2 lines", out)
            code, out = run([str(path), "--lang", "j", "--only", "cmd"])
            self.assertEqual(code, 0)
            self.assertIn("こん", out)
            path.write_bytes(duel_archive(records((0x4006, 3, 0, 0), (0, 0, 0, 0))))
            code, out = run([str(path), "--check"])
            self.assertEqual(code, 1)
            self.assertIn("missing label 3", out)

    def test_deck_archive(self):
        script = bytes.fromhex("01 01 00 3c 00 60 00 68 01" "13 00 00" "17")
        members = {"deck_tutorial00.bin": script, "strTbl_e.bin": string_table(["Caption", "Welcome"])}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tutorial.ehp"
            path.write_bytes(tutorial.ehp.build(sorted(members.items())))
            code, out = run([str(path), "--check"])
            self.assertEqual(code, 0, out)
            code, out = run([str(path)])
            self.assertIn('message            01 00 3c 00 60 00 68 01  "Welcome"', out)
            self.assertIn('caption            00 00  "Caption"', out)


if __name__ == "__main__":
    unittest.main()
