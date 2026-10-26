#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/card_effects.py on synthetic inputs. Run with: python3 -I tools/tests/test_card_effects.py"""

import csv
import importlib.util
import json
import struct
import tempfile
import types
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_card_effects", Path(__file__).resolve().parents[1] / "card_effects.py")
ce = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ce)

POG, SHEEP, GOAT, FUSION, MAT, RITUAL_M, RITUAL_S, NORMAL, BARE, EQUIP, GHOST = (
    0x12EC, 0x0F3E, 0x12D2, 0x1000, 0x1001, 0x1100, 0x1101, 0x1200, 0x1300, 0x1400, 0x1F24)
H_DRAW, H_COND, H_TOKEN, H_UNNAMED, H_FB = 0x09C78270, 0x09C56D70, 0x09C795F0, 0x09C74BA4, 0x09CCD668


def ident(name, kind, icon=0, level=0):
    return {"index": 1, "name": name, "passcode": 0, "kind": kind, "kind_name": ce.KINDS.get(kind, ""),
            "attribute": 0, "attribute_name": "", "race": 0, "race_name": "", "level": level, "atk": 0, "def": 0,
            "icon": icon, "icon_name": ce.ICONS.get(icon, ""), "genre_mask": "0x0", "genres": []}


def slot(handler, name, cats=(), meta=()):
    return {"handler": handler, "name": name, "categories": list(cats), "meta": list(meta)}


def record(table, index, cid, slots, unnamed_resolve=0):
    return {"table": table, "index": index, "card_id": cid, "slots": slots, "commands": [0x24],
            "unnamed_resolve": unnamed_resolve, "unnamed": unnamed_resolve}


def sources(**over):
    cards = {POG: ident("Draw Spell", 27), SHEEP: ident("Sheep", 21), GOAT: ident("Goat Spell", 27),
             FUSION: ident("Fusion", 5), MAT: ident("Material", 3), RITUAL_M: ident("Ritual Monster", 9, level=6),
             RITUAL_S: ident("Ritual Spell", 27, icon=6), NORMAL: ident("Vanilla", 1), BARE: ident("Bare", 3),
             EQUIP: ident("Equip", 27, icon=3)}
    src = {
        "cards": cards,
        "records": [
            record("S/T", 0, ce.PLACEHOLDER_ID, {"resolve": slot(H_UNNAMED, "FUN_09c74ba4")}, 2),
            record("S/T", 2, ce.PLACEHOLDER_ID, {"resolve": slot(H_FB, "duel_effects_resolve_ritual_summon",
                                                                 ["special_summon"])}),
            record("S/T", 5, POG, {"resolve": slot(H_DRAW, "duel_effects_resolve_draw", ["draw"]),
                                   "condition": slot(H_COND, "duel_effects_can_activate_draw")}),
            record("S/T", 6, GOAT, {"resolve": slot(H_TOKEN, "duel_effects_resolve_summon_tokens",
                                                    ["special_summon", "token"], ["optional"])}, 3),
            record("S/T", 7, GOAT, {"resolve": slot(H_TOKEN, "duel_effects_resolve_summon_tokens", ["token"])}),
            record("M1", 0, GHOST, {"resolve": slot(H_DRAW, "duel_effects_resolve_draw", ["draw"])}),
        ],
        "target_filters": {("S/T", 6): {"flags": "0x21440", "form": "ori", "side": "opponent", "zone": "spell_trap",
                                        "face": "", "position": "", "actions": "targeted destroy not_self"}},
        "filter_calls": {H_DRAW: [{"call_site": "0x09c78300", "flags": "0x01092", "side": "opponent",
                                   "zone": "monster", "face": "", "position": "attack", "actions": "destroy"}]},
        "lists": [("L1", 0, BARE, 0x09C7B510, "duel_effects_resolve_search_deck")],
        "draw_counts": {POG: {"kind": "constant", "value": 2, "summary": ""}},
        "chain_cases": [
            {"function": "0x09c779bc", "card_id": "0x12ec", "kind": "constant", "value": 2},
            {"function": "0x09c41400", "card_id": "0x1001", "kind": "constant", "value": 1000},
            {"function": "0x09c41400", "card_id": "0x1002", "kind": "computed", "value": ""},
            {"function": "0x09abcdef", "card_id": "0x1001", "kind": "constant", "value": 3},
        ],
        "stat_mods": [{"card_id": "0x1400", "section": "equip_spell", "function_name": "f", "use": "test",
                       "address": "0x09c08b00", "values": "700", "helper": "", "calls": ""}],
        "recipes": [(0, FUSION, (MAT, 0x0F))],
        "hardcoded_fusions": {},
        "rituals": [(0, RITUAL_M, RITUAL_S, 6)],
        "ai": [("B", "main", 17, POG, 0x09D6D3C4, "FUN_09d6d3c4"), ("T1", "chain", 0, GHOST, 0x09D6B6B8, "x")],
        "tokens": [(3, GOAT, SHEEP, 4, 1), (4, BARE, SHEEP, 0, 2)],
        "search_filters": {},
        "search_note": "absent",
        "ai_missing": {GHOST},
    }
    src.update(over)
    return src


class Join(unittest.TestCase):
    def setUp(self):
        self.src = sources()
        self.specs = ce.build_specs(self.src)

    def test_every_id_once_and_sorted(self):
        ids = list(self.specs)
        self.assertEqual(ids, sorted(ids))
        for cid in (POG, GOAT, GHOST, ce.PLACEHOLDER_ID, 0x1002):
            self.assertIn(cid, self.specs)
        self.assertEqual(sum(len(s["effects"]) for s in self.specs.values()), len(self.src["records"]))

    def test_effect_record_fields(self):
        pog = self.specs[POG]
        e = pog["effects"][0]
        self.assertEqual(e["slots"]["resolve"]["categories"], ["draw"])
        self.assertEqual(e["slots"]["resolve"]["shared_by_cards"], 2)  # POG and the unreleased id
        self.assertEqual(e["slots"]["resolve"]["filter_calls"][0]["flags"], "0x01092")
        self.assertTrue(e["slots"]["condition"]["named"])
        self.assertEqual(e["commands"], ["0x24"])
        self.assertEqual(e["confidence"], "medium")  # shared resolve handler
        self.assertEqual(pog["params"]["draw_count"]["value"], 2)
        self.assertNotIn("chains", pog["params"])  # the draw chain is reported once, as draw_count
        self.assertEqual(pog["spec_status"], "full")
        self.assertEqual(pog["confidence"]["draw_count"], "high")
        self.assertIn("draw_count", pog["sources"])

    def test_variants_and_target_filter(self):
        goat = self.specs[GOAT]
        self.assertEqual([e["variant"] for e in goat["effects"]], [0, 1])
        self.assertEqual(goat["effects"][0]["target_filter"]["actions"], ["targeted", "destroy", "not_self"])
        self.assertEqual(goat["effects"][0]["slots"]["resolve"]["meta"], ["optional"])
        self.assertEqual(goat["spec_status"], "partial")  # first record reaches unnamed callees
        self.assertEqual(goat["tokens"][0]["token_name"], "Sheep")
        self.assertEqual(goat["tokens"][0]["position"], "defense")
        self.assertEqual(self.specs[SHEEP]["token_of"], ["0x12d2", "0x1300"])
        self.assertTrue(self.specs[BARE]["tokens"][0]["count_computed"])

    def test_record_confidence(self):
        unique = record("M2", 0, BARE, {"resolve": slot(1, "a", ["destroy"])})
        self.assertEqual(ce.record_confidence(unique, {1: {BARE}}), "high")
        self.assertEqual(ce.record_confidence(unique, {1: {BARE, POG}}), "medium")
        empty = record("M2", 0, BARE, {"resolve": slot(1, "a")})
        self.assertEqual(ce.record_confidence(empty, {1: {BARE}}), "low")

    def test_chains(self):
        chains = self.specs[MAT]["params"]["chains"]
        self.assertEqual({c["label"]: c["confidence"] for c in chains}, {"lp_cost": "high", "chain_09abcdef": "low"})
        computed = self.specs[0x1002]["params"]["chains"][0]
        self.assertEqual((computed["value"], computed["confidence"]), (None, "medium"))
        self.assertFalse(self.specs[0x1002]["released"])

    def test_fusion_and_ritual(self):
        recipe = self.specs[FUSION]["fusion"]["recipes"][0]
        self.assertEqual(recipe["materials"][0]["name"], "Material")
        self.assertTrue(recipe["materials"][1]["generic"])
        self.assertEqual(self.specs[MAT]["fusion"]["material_of"], ["0x1000"])
        self.assertEqual(self.specs[RITUAL_M]["fusion"]["ritual_monster"][0]["spell"], "0x1101")
        self.assertEqual(self.specs[FUSION]["spec_status"], "vanilla")
        self.assertEqual(self.specs[NORMAL]["spec_status"], "vanilla")

    def test_statuses(self):
        s = self.specs
        self.assertEqual(s[GHOST]["spec_status"], "unreleased")
        self.assertEqual(s[ce.PLACEHOLDER_ID]["spec_status"], "placeholder")
        self.assertEqual(s[BARE]["spec_status"], "partial")  # list record and token only
        self.assertEqual(s[MAT]["spec_status"], "partial")  # chains only
        self.assertEqual(s[RITUAL_S]["fallback_effect"]["index"], 2)
        self.assertEqual(s[RITUAL_S]["spec_status"], "full")  # complete fallback + ritual table
        self.assertNotIn("fallback_effect", s[EQUIP])  # no record 1 in the synthetic placeholder set
        self.assertEqual(s[EQUIP]["spec_status"], "partial")  # stat mods only
        missing = ce.build_specs(sources(stat_mods=[]))
        self.assertEqual(missing[EQUIP]["spec_status"], "missing")

    def test_join_report(self):
        problems, lines = ce.join_report(self.src, self.specs)
        self.assertEqual(problems, [])
        text = "\n".join(lines)
        self.assertIn("1 belong to 1 unreleased ids", text)
        self.assertIn("2 carry the fallback placeholder id 0x0e74", text)
        self.assertIn("0x1f24", text)
        bad = sources(records=self.src["records"] + [record("M3", 0, 0x0100, {})])
        problems, _ = ce.join_report(bad, ce.build_specs(bad))
        self.assertTrue(any("outside" in p for p in problems))

    def test_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            ce.write_outputs(tmp, self.specs, {"depth": 3})
            lines = (Path(tmp) / "card_effects.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(json.loads(lines[0])["schema"], ce.SCHEMA)
            self.assertEqual(len(lines), len(self.specs) + 1)
            with open(Path(tmp) / "card_effects.csv", newline="", encoding="utf-8") as f:
                rows = {r["card_id"]: r for r in csv.DictReader(f)}
            self.assertEqual(rows["0x12ec"]["draw_count"], "2")
            self.assertEqual(rows["0x1001"]["lp_cost"], "1000")
            self.assertEqual(rows["0x1101"]["fallback"], "S/T:2")
            self.assertEqual(rows["0x12d2"]["resolve_categories"], "special_summon token")


class FakeModule:
    """words() over a dict image, enough for token_entries and fusion.code_facts."""

    def __init__(self, words, base=ce.ep.BASE):
        self.mem, self.base = words, base

    def words(self, address, count):
        return tuple(self.mem.get(address + 4 * k, 0) for k in range(count))


def lookup_code():
    """lui v1,HI; addiu v1,v1,LO (the table) and sltiu v0,a1,46 at the lookup address."""
    off = ce.TOKEN_TABLE - ce.ep.BASE
    hi, lo = (off + 0x8000) >> 16, off & 0xFFFF
    return {ce.TOKEN_LOOKUP: 0x0F << 26 | 3 << 16 | hi, ce.TOKEN_LOOKUP + 4: 9 << 26 | 3 << 21 | 3 << 16 | lo,
            ce.TOKEN_LOOKUP + 8: 0x0B << 26 | 5 << 21 | 2 << 16 | ce.TOKEN_COUNT}


class Tokens(unittest.TestCase):
    def image(self, entries):
        mem = lookup_code()
        for i, (cid, token, count, position) in enumerate(entries):
            mem[ce.TOKEN_TABLE + 8 * i] = cid | token << 16
            mem[ce.TOKEN_TABLE + 8 * i + 4] = count | position << 16
        return FakeModule(mem)

    def test_parse_and_check(self):
        good = [(0x12D2, 0x0F3E, 4, 1)] * ce.TOKEN_COUNT
        m = self.image(good)
        entries = ce.token_entries(m)
        self.assertEqual(entries[0], (0, 0x12D2, 0x0F3E, 4, 1))
        self.assertEqual(len(entries), ce.TOKEN_COUNT)
        self.assertEqual(ce.check_tokens(m, entries, {0x0F3E: {"kind": 21}}), [])
        self.assertTrue(ce.check_tokens(m, entries, {0x0F3E: {"kind": 3}}))
        bad = self.image([(0x12D2, 0x0F3E, 4, 7)] + good[1:])
        self.assertTrue(any("position" in p for p in ce.check_tokens(bad, ce.token_entries(bad))))
        no_ref = FakeModule({})
        self.assertEqual(len([p for p in ce.check_tokens(no_ref, []) if "find_token_entry" in p]), 2)


class SearchFilters(unittest.TestCase):
    def test_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, note = ce.load_search_filters(b"", tools_dir=tmp)
        self.assertEqual(data, {})
        self.assertTrue(note.startswith("absent"))

    def test_module_mapping_and_rows(self):
        mapping = types.SimpleNamespace(card_filters=lambda data: {0x1000: {"filter": "0x10"}})
        self.assertEqual(ce.load_search_filters(b"", module=mapping)[0], {0x1000: [{"filter": "0x10"}]})
        rows = types.SimpleNamespace(card_filters=lambda data: [{"card_id": "0x1001", "filter": "a"},
                                                                {"card_id": 0x1001, "filter": "b"}])
        self.assertEqual(ce.load_search_filters(b"", module=rows)[0], {0x1001: [{"filter": "a"}, {"filter": "b"}]})

    def test_module_without_api_or_failing(self):
        self.assertIn("no card_filters", ce.load_search_filters(b"", module=types.SimpleNamespace())[1])

        def boom(data):
            raise ValueError("unfinished")
        data, note = ce.load_search_filters(b"", module=types.SimpleNamespace(card_filters=boom))
        self.assertEqual(data, {})
        self.assertIn("unfinished", note)

    def test_tool_file_and_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "search_filters.py").write_text(
                "def card_filters(data):\n    return {0x1200: [{'n': len(data)}]}\n", encoding="utf-8")
            self.assertEqual(ce.load_search_filters(b"abc", tools_dir=tmp)[0], {0x1200: [{"n": 3}]})
            Path(tmp, "search_filters.py").write_text("raise ImportError('half written')\n", encoding="utf-8")
            self.assertIn("import failed", ce.load_search_filters(b"", tools_dir=tmp)[1])
            path = Path(tmp, "f.csv")
            path.write_text("card_id,flags\n0x1300,0x5\n", encoding="utf-8")
            self.assertEqual(ce.load_search_filters(b"", csv_path=path)[0], {0x1300: [{"flags": "0x5"}]})

    def test_joined(self):
        specs = ce.build_specs(sources(search_filters={BARE: [{"flags": "0x5"}]}))
        self.assertEqual(specs[BARE]["params"]["search_filters"], [{"flags": "0x5"}])
        self.assertEqual(specs[BARE]["confidence"]["search_filters"], "medium")


if __name__ == "__main__":
    unittest.main()
