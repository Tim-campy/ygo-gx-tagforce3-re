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
        split = record("M2", 0, BARE, {"resolve": {**slot(1, "a", ["damage", "gain_lp"]),
                                                   "categories_refined": ["damage"],
                                                   "refinement": {"method": "lp_chain", "confidence": "high"}}})
        self.assertEqual(ce.record_confidence(split, {1: {BARE, POG}}), "high")  # the family split isolates it
        split["slots"]["resolve"]["refinement"]["confidence"] = "medium"
        self.assertEqual(ce.record_confidence(split, {1: {BARE, POG}}), "medium")

    def test_family_split_fields(self):
        res = {**slot(H_DRAW, "duel_effects_resolve_lp_change", ["damage", "gain_lp"]),
               "categories_refined": ["damage"],
               "refinement": {"method": "lp_chain", "confidence": "high", "removed": ["gain_lp"], "added": [],
                              "lp_amounts": ["opponent:-800"]}}
        specs = ce.build_specs(sources(records=[record("S/T", 5, POG, {"resolve": res}),
                                                record("M1", 0, GHOST, {"resolve": dict(res)})]))
        out = specs[POG]["effects"][0]["slots"]["resolve"]
        self.assertEqual(out["categories"], ["damage", "gain_lp"])  # schema 2 field unchanged
        self.assertEqual(out["categories_refined"], ["damage"])
        self.assertEqual(out["refinement"]["lp_amounts"], ["opponent:-800"])
        self.assertEqual(specs[POG]["effects"][0]["confidence"], "high")
        self.assertEqual(specs[POG]["confidence"]["family_split"], "high")
        self.assertIn("family_split", specs[POG]["sources"])
        self.assertEqual(ce.csv_row(specs[POG])["resolve_categories_refined"], "damage")
        self.assertEqual(ce.csv_row(specs[POG])["resolve_categories"], "damage gain_lp")
        _, lines = ce.join_report(sources(), specs)
        self.assertTrue(any(line.startswith("family split: 2 resolve slots examined, 2 refined") for line in lines))

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


def ref(kind, function, name, operand="u16 load", module="rel_duel_eng", detail="", value=None, address=None):
    return {"kind": kind, "detail": detail, "address": address or function + 8, "use": function + 12,
            "function": function, "function_name": name, "module": module, "operand": operand, "value": value,
            "constants": [], "group": ce.cr.group_of(name)}


class EngineRefs(unittest.TestCase):
    """card_refs references, all compare chains and the engine_only status."""

    def setUp(self):
        self.refs = {
            EQUIP: [ref("eq", 0x09BED2D8, "duel_core_get_direct_attack_mode", value=1),
                    ref("eq", 0x09BED2D8, "duel_core_get_direct_attack_mode", address=0x09BED300),
                    ref("arg", 0x09C00000, "FUN_09c00000", operand="", detail="duel_core_is_on_field")],
            MAT: [ref("bound", 0x09C10000, "FUN_09c10000", operand="")],
            NORMAL: [ref("eq", 0x08862300, "card_db_is_forbidden_one", operand="argument", module="BOOT.BIN")],
            0x1F3A: [ref("eq", 0x09C20000, "FUN_09c20000")],  # an id no other source knows
        }

    def build(self, **over):
        return ce.build_specs(sources(**{"stat_mods": [], "chain_cases": [], "engine_refs": self.refs, **over}))

    def test_engine_only_and_groups(self):
        specs = self.build()
        equip = specs[EQUIP]
        self.assertEqual(equip["spec_status"], "engine_only")
        groups = equip["engine_refs"]
        self.assertEqual([g["function_name"] for g in groups], ["duel_core_get_direct_attack_mode", "FUN_09c00000"])
        first = groups[0]
        self.assertEqual((first["group"], first["named"], first["kinds"], first["values"]),
                         ("duel_core", True, {"eq": 2}, [1]))
        self.assertEqual(first["references"], ["0x09bed2e0", "0x09bed300"])
        self.assertEqual(groups[1]["callees"], ["duel_core_is_on_field"])
        self.assertEqual(equip["confidence"]["engine_refs"], "medium")
        self.assertIn("engine_refs", equip["sources"])
        self.assertNotIn(0x1F3A, specs)  # engine references do not create ids

    def test_bound_only_stays_missing_and_vanilla_stays(self):
        specs = self.build(chain_cases=[], records=sources()["records"])
        self.assertEqual(specs[MAT]["spec_status"], "missing")  # a range bound names no card
        self.assertEqual(specs[MAT]["confidence"]["engine_refs"], "low")
        self.assertEqual(specs[NORMAL]["spec_status"], "vanilla")
        self.assertEqual(specs[NORMAL]["engine_refs"][0]["module"], "BOOT.BIN")

    def test_chain_classes(self):
        predicate = {"function": "0x09bedf1c", "card_id": "0x1001", "kind": "constant", "value": 1,
                     "class": "predicate", "label": "duel_core_has_piercing", "confidence": "medium"}
        specs = self.build(chain_cases=[predicate])
        chain = specs[MAT]["params"]["chains"][0]
        self.assertEqual((chain["label"], chain["class"], chain["confidence"]),
                         ("duel_core_has_piercing", "predicate", "medium"))
        self.assertEqual(specs[MAT]["spec_status"], "engine_only")  # predicate chains are engine code
        parameter = dict(predicate, **{"class": "parameter", "label": "lp_cost", "confidence": "high"})
        self.assertEqual(self.build(chain_cases=[parameter])[MAT]["spec_status"], "partial")
        self.assertEqual(ce.build_specs(sources())[MAT]["params"]["chains"][0]["class"], "parameter")  # old rows

    def test_chain_label(self):
        reg = types.SimpleNamespace(name=lambda a: {0x09BEDF1C: "duel_core_has_piercing"}.get(a, f"FUN_{a:08x}"))
        self.assertEqual(ce.chain_label(0x09C41400, reg), ("lp_cost", "high"))
        self.assertEqual(ce.chain_label(0x09BEDF1C, reg), ("duel_core_has_piercing", "medium"))
        self.assertEqual(ce.chain_label(0x09C00000, reg), ("chain_09c00000", "low"))

    def test_report_and_csv(self):
        src = sources(stat_mods=[], chain_cases=[], engine_refs=self.refs)
        specs = ce.build_specs(src)
        problems, lines = ce.join_report(src, specs)
        self.assertEqual(problems, [])
        text = "\n".join(lines)
        self.assertIn("engine_only 1", text)
        self.assertIn("engine_only cards: 1, by kind: spell 1; referencing functions by group: duel_core 1, "
                      "unnamed 1", text)
        self.assertIn("missing cards by kind: effect 1", text)  # MAT: a bound only
        row = ce.csv_row(specs[EQUIP])
        self.assertEqual((row["engine_ref_functions"], row["engine_ref_groups"]), (2, "duel_core unnamed"))


def sem(tag, confidence="M"):
    return {"tag": tag, "phrase": tag, "modality": "", "confidence": confidence, "param": "", "value": None,
            "label": "", "rule": tag}


def tagged(kind, function, name, tag, confidence="M", **kw):
    r = ref(kind, function, name, **kw)
    r["semantics"] = sem(tag, confidence)
    return r


class EngineMapped(unittest.TestCase):
    """Inert records and the engine-mapped rule (docs/formats/card-effect-spec.md)."""

    def build(self, refs, **over):
        return ce.build_specs(sources(**{"stat_mods": [], "chain_cases": [], "engine_refs": refs, **over}))

    def test_described_named_references_make_full(self):
        refs = {MAT: [tagged("eq", 0x09BED2D8, "duel_core_get_direct_attack_mode", "direct_attack"),
                      tagged("eq", 0x09D00000, "FUN_09d00000", "ai_hint", "L"),        # AI: ignored
                      tagged("eq", 0x09C30000, "card_db_is_hero", "archetype", "H"),   # membership: ignored
                      tagged("arg", 0x09C40000, "ai_choose_attack_target", "ai_hint", operand="",
                             detail="x")]}
        s = self.build(refs)[MAT]
        self.assertEqual((s["spec_status"], s["spec_basis"]), ("full", "engine"))

    def test_blockers(self):
        base = [tagged("eq", 0x09BED2D8, "duel_core_get_direct_attack_mode", "direct_attack")]
        unnamed = base + [tagged("eq", 0x09C50000, "FUN_09c50000", "piercing")]
        untagged = base + [tagged("eq", 0x09C60000, "duel_core_compute_card_stats", "unclassified", "L")]
        only_low = [tagged("eq", 0x09BED2D8, "duel_core_battle_resolve", "battle_damage_rule", "L")]
        for refs in (unnamed, untagged, only_low):
            self.assertEqual(self.build({MAT: refs})[MAT]["spec_status"], "engine_only")
        # side data keeps the card partial unless the references are mapped
        stat = [{"card_id": "0x1001", "section": "self", "function_name": "duel_core_compute_card_stats",
                 "use": "test", "address": "0x09c05a00", "values": "300", "helper": "", "calls": ""}]
        self.assertEqual(self.build({MAT: untagged}, stat_mods=stat)[MAT]["spec_status"], "partial")
        self.assertEqual(self.build({MAT: base}, stat_mods=stat)[MAT]["spec_status"], "full")
        unnamed_stat = [dict(stat[0], function_name="FUN_09c05304")]
        self.assertEqual(self.build({MAT: base}, stat_mods=unnamed_stat)[MAT]["spec_status"], "partial")
        self.assertEqual(self.build({}, stat_mods=stat)[MAT]["spec_status"], "partial")  # side data, no references

    def test_equip_fallback_engine_mapped(self):
        refs = {EQUIP: [tagged("eq", 0x09BED2D8, "duel_core_is_valid_attack_target", "attack_target_rule")]}
        records = sources()["records"] + [
            record("S/T", 1, ce.PLACEHOLDER_ID, {"resolve": slot(0x09C748A8, "duel_effects_resolve_equip_to_target",
                                                                 ["equip"])})]
        s = self.build(refs, records=records)[EQUIP]
        self.assertEqual((s["spec_status"], s["spec_basis"]), ("full", "fallback"))
        self.assertEqual(self.build({}, records=records)[EQUIP]["spec_status"], "partial")

    def test_inert_records(self):
        stub = dict(record("S/T", 9, BARE, {"condition": slot(0x09CE28DC, "duel_effects_cond_never")}), inert=True)
        refs = {BARE: [tagged("eq", 0x09BED2D8, "duel_effects_collect_negation_state", "negation", "H")]}
        s = self.build(refs, records=sources()["records"] + [stub], lists=[], tokens=[])[BARE]
        self.assertTrue(s["effects"][0]["inert"])
        self.assertEqual((s["spec_status"], s["spec_basis"]), ("full", "engine"))
        s = self.build({}, records=sources()["records"] + [stub], lists=[], tokens=[])[BARE]
        self.assertEqual(s["spec_status"], "partial")  # an inert record alone is not a spec
        live = record("S/T", 10, BARE, {"resolve": slot(H_DRAW, "duel_effects_resolve_draw", ["draw"])})
        s = self.build({}, records=sources()["records"] + [stub, live], lists=[], tokens=[])[BARE]
        self.assertEqual((s["spec_status"], s["spec_basis"]), ("full", "records"))

    def test_return_zero_stub(self):
        words = {0x100: (0x03E00008, 0x00001021), 0x200: (0x03E00008, 0x24020001)}
        module = types.SimpleNamespace(words=lambda a, n: words[a])
        self.assertTrue(ce.is_return_zero_stub(module, 0x100))
        self.assertFalse(ce.is_return_zero_stub(module, 0x200))  # returns 1
        self.assertFalse(ce.is_return_zero_stub(module, 0x300))  # no code there


class EngineBranches(unittest.TestCase):
    CSV = ("card_id,function,when,effect,amount,condition,confidence,basis\n"
           "0x1001,0x09dc5a4c,battle,battle_damage_multiply,x2,direct attack,H,battle.md\n")

    def write(self, tmp, text):
        path = Path(tmp) / "engine_branches.csv"
        path.write_text(text, encoding="utf-8")
        return path

    def test_load_and_problems(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows, problems = ce.load_engine_branches(self.write(tmp, self.CSV))
            self.assertEqual(problems, [])
            self.assertEqual(rows, [{"card_id": MAT, "function": "0x09dc5a4c", "when": "battle",
                                     "effect": "battle_damage_multiply", "amount": "x2", "condition": "direct attack",
                                     "confidence": "H", "basis": "battle.md", "source": "read"}])
            _, problems = ce.load_engine_branches(self.write(tmp, self.CSV.replace(",H,", ",X,")))
            self.assertEqual(len(problems), 1)
            _, problems = ce.load_engine_branches(self.write(tmp, "card_id,function\n0x1,0x2\n"))
            self.assertIn("lacks the column", problems[0])
        self.assertEqual(ce.load_engine_branches(Path("no/such/file.csv")), ([], []))

    def test_generated_rows(self):
        base = {"function": "0x09c4b050", "target": "0x09c4b100", "label": "chain_09c4b050", "own": "a1=2 at 0x09c4b6a0"}
        cases = [{**base, "card_id": "0x1001", "class": "behaviour"},
                 {**base, "card_id": "0x1300", "class": "unresolved", "own_varies": 1},
                 {**base, "card_id": "0x1200", "class": "unresolved", "own_varies": 0},
                 {**base, "card_id": "0x12ec", "class": "parameter", "own_varies": 1},
                 {**base, "card_id": "0x1400", "class": "behaviour", "own": ""},
                 {**base, "card_id": "0x1500", "class": "iteration", "kind": "iteration", "own": "",
                  "values": "next: s2=(?s2 + 1)"},
                 {**base, "card_id": "0x1501", "class": "iteration", "kind": "iteration", "own": "",
                  "values": "next: no change"}]
        rows = ce.generated_branches(cases)
        self.assertEqual([r["card_id"] for r in rows], [MAT, BARE, 0x1500])
        self.assertEqual(rows[2]["amount"], "per iteration next: s2=(?s2 + 1)")
        self.assertEqual((rows[0]["effect"], rows[0]["amount"], rows[0]["confidence"], rows[0]["source"]),
                         ("chain_case:chain_09c4b050", "a1=2 at 0x09c4b6a0", "L", "chain"))

    def test_joined_into_spec(self):
        read = {"card_id": MAT, "function": "0x09dc5a4c", "when": "battle", "effect": "battle_damage_set",
                "amount": "1000", "condition": "", "confidence": "H", "basis": "battle.md", "source": "read"}
        gen = {**read, "effect": "chain_case:x", "confidence": "L", "source": "chain"}
        specs = ce.build_specs(sources(engine_branches=[read, gen, {**gen, "card_id": NORMAL}, {**read, "card_id": 0x7777}]))
        mat = specs[MAT]
        self.assertEqual([b["source"] for b in mat["engine_branches"]], ["read", "chain"])
        self.assertNotIn("card_id", mat["engine_branches"][0])
        self.assertEqual(mat["confidence"]["engine_branches"], "medium")
        self.assertIn("engine_branches", mat["sources"])
        self.assertNotIn("engine_branches", specs[NORMAL])  # vanilla: a generated row is another card's reference
        self.assertNotIn(0x7777, specs)  # engine branches never add ids
        self.assertEqual(ce.csv_row(mat)["engine_branches"], 2)
        self.assertEqual(mat["spec_status"], ce.build_specs(sources())[MAT]["spec_status"])  # status rules unchanged
        _, lines = ce.join_report(sources(engine_branches=[read, gen]), specs)
        self.assertTrue(any(line.startswith("engine branches: 1 read rows, 1 generated") for line in lines))

    def test_schema5_chain_fields(self):
        cases = [{"function": "0x09abcdef", "card_id": "0x1001", "kind": "conditional", "value": "", "values": "1 | 2",
                  "method": "paths", "reason": "", "own": "a1=1 at 0x09abce00", "expression": "",
                  "class": "expression", "label": "chain_09abcdef", "confidence": "medium"},
                 {"function": "0x09abcdef", "card_id": "0x1300", "kind": "constant", "value": 7, "method": "paths",
                  "class": "parameter", "label": "lp_cost", "confidence": "high"},
                 {"function": "0x09abcdef", "card_id": "0x1400", "kind": "expression", "value": "",
                  "expression": "helper(arg0, 5)", "method": "paths", "class": "expression",
                  "label": "chain_09abcdef", "confidence": "low"}]
        specs = ce.build_specs(sources(chain_cases=cases))
        c = specs[MAT]["params"]["chains"][0]
        self.assertEqual((c["kind"], c["values"], c["own"], c["confidence"]), ("conditional", ["1", "2"],
                                                                               "a1=1 at 0x09abce00", "medium"))
        self.assertNotIn("reason", c)
        bare = specs[BARE]["params"]["chains"][0]
        self.assertEqual((bare["value"], bare["confidence"]), (7, "medium"))  # paths constants are at most medium
        self.assertEqual(specs[EQUIP]["params"]["chains"][0]["expression"], "helper(arg0, 5)")
        self.assertEqual(ce.SCHEMA, 7)


if __name__ == "__main__":
    unittest.main()
