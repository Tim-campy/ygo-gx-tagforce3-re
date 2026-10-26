#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Join the per-card analyses of the duel engine into one per-card effect specification.

See docs/formats/card-effect-spec.md. The tool runs the existing extractors on the maintainer's own files and
joins their results by card id; it carries no game data itself and copies no code from them:

  identity        tools/cardinfo.py        (cardinfo_eng.ehp)
  effect records  tools/effect_classify.py (four 24-byte tables, per-slot categories, handler names)
  parameters      tools/effect_params.py   (target-filter flags, draw counts, parameter compare chains)
                  tools/stat_mods.py       (ATK/DEF modifier sections)
  fusion/ritual   tools/fusion.py
  AI tables       tools/ai_tables.py
  tokens          the token table at 0x09e019ec, parsed here (docs/subsystems/effect-helpers-deck.md)
  searches        tools/search_filters.py  (optional; skipped when the tool is absent)
  engine refs     tools/card_refs.py       (card ids tested directly in code: rel_duel_eng, and BOOT.BIN and
                                            rel_duel_draw.prx when --boot / --draw are given)
  family split    tools/family_split.py    (per-card categories of the family-shared resolve handlers)

  card_effects.py <USRDIR>/gmodule/rel_duel_eng.prx <USRDIR>/duelsys/cardinfo_eng.ehp -o extracted/card_effects
                  [--boot <SYSDIR>/BOOT.BIN] [--draw <USRDIR>/gmodule/rel_duel_draw.prx]
                  [--functions re/functions.csv] [--depth 3] [--search-filters file.csv]
  card_effects.py <USRDIR>/gmodule/rel_duel_eng.prx <USRDIR>/duelsys/cardinfo_eng.ehp --check [--boot ...]

Outputs (game data: keep them under extracted/, never in git): card_effects.jsonl (one JSON object per card id)
and card_effects.csv (one summary row per card id).
"""

import argparse
import collections
import csv
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ec = _load("re_effect_classify", "effect_classify.py")
ep, ait = ec.ep, ec.ait
sm = _load("re_stat_mods", "stat_mods.py")
fu = _load("re_fusion", "fusion.py")
ci = _load("re_cardinfo", "cardinfo.py")
cr = _load("re_card_refs", "card_refs.py")
fs = _load("re_family_split", "family_split.py")

SCHEMA = 3  # 2 = 1 plus engine_refs, params.chains[].class/source and the status engine_only;
#             3 = 2 plus slots.resolve.categories_refined / .refinement (tools/family_split.py)
FIRST_CARD, LAST_CARD = ep.FIRST_CARD, ep.LAST_CARD

# Token table read by duel_effects_find_token_entry (0x09befee0, 68 bytes): 46 records of four u16
# (card id, token card id, count with 0 = computed by the handler, position). Linear search, not sorted.
TOKEN_TABLE = 0x09E019EC
TOKEN_COUNT = 46
TOKEN_LOOKUP, TOKEN_LOOKUP_SIZE = 0x09BEFEE0, 68
TOKEN_POSITIONS = {0: "attack", 1: "defense", 2: "either"}
TOKEN_KIND = 21

# Placeholder id of S/T records 0-2: duel_effects_find_record falls back on them, by spell icon, for a spell
# with no record of its own (docs/subsystems/summon.md): field (2) -> record 0, equip (3) -> 1, ritual (6) -> 2.
PLACEHOLDER_ID = 0x0E74
FALLBACK_RECORD = {2: 0, 3: 1, 6: 2}
SPELL_KIND = 27

SEARCH_LIST = "L1"  # the 8-byte list 0x09dec554 (search / summon-from-deck builders)
OWN_LISTS = ("L1", "L4")  # L2 and L3 are the AI tables (reported under "ai")

# Parameter compare chains with an established meaning (docs/formats/effect-tables.md): function ->
# (label, confidence). Every other compare chain of effect_params (parameter, predicate, mixed or unresolved)
# is labelled with its registry name when it is named (medium), else chain_<address> (low).
PARAM_CHAINS = {
    0x09C779BC: ("draw_count", "high"),
    0x09C41400: ("lp_cost", "high"),
    0x09C41C38: ("discard_count", "medium"),
    0x09C42310: ("spell_counter_cost", "high"),
    0x09DE2310: ("standby_lp_cost", "high"),
    0x09BF4774: ("hand_effect_players", "medium"),
}

KINDS = {1: "normal", 3: "effect", 5: "fusion", 7: "effect_fusion", 9: "ritual", 11: "effect_ritual", 13: "toon",
         15: "spirit", 17: "union", 19: "gemini", 21: "token", 23: "egyptian_god", 27: "spell", 29: "trap",
         31: "normal_tuner", 33: "effect_tuner", 35: "synchro", 37: "effect_synchro"}
NO_TEXT_KINDS = {1, 5, 9, 21, 31, 35}  # kinds that need no effect (normal, plain fusion/ritual/synchro, token)
ATTRIBUTES = {1: "LIGHT", 2: "DARK", 3: "WATER", 4: "FIRE", 5: "EARTH", 6: "WIND", 7: "DIVINE", 8: "spell",
              9: "trap"}
RACES = {**fu.RACES, 22: "Divine-Beast", 23: "spell", 24: "trap"}
ICONS = {0: "normal", 1: "counter", 2: "field", 3: "equip", 4: "continuous", 5: "quick-play", 6: "ritual"}

SOURCES = {
    "identity": "cardinfo_eng.ehp via tools/cardinfo.py (CARD_Prop, CARD_Pass, CARD_Genre, names)",
    "effects": "24-byte effect tables of rel_duel_eng.prx via tools/effect_classify.py (categories by callee "
               "names in re/functions.csv and tools/effect_categories.csv)",
    "lists": "8-byte lists L1 0x09dec554 and L4 0x09e010b0 via tools/effect_params.py",
    "target_filter": "slot +08 stubs of duel_effects_target_filter via tools/effect_params.py",
    "filter_calls": "constant flag words at jal duel_effects_target_filter sites via tools/effect_params.py",
    "draw_count": "duel_effects_get_draw_count compare chain via tools/effect_params.py",
    "chains": "parameter compare chains via tools/effect_params.py (labels from docs/formats/effect-tables.md)",
    "stat_mods": "ATK/DEF stat functions via tools/stat_mods.py",
    "fusion": "fusion recipe table 0x09debe98 and hard-coded fusions via tools/fusion.py",
    "ritual": "ritual table 0x09dec4d4 via tools/fusion.py",
    "ai": "AI priority tables and u16 lists via tools/ai_tables.py",
    "tokens": "token table 0x09e019ec (duel_effects_find_token_entry), parsed by tools/card_effects.py",
    "search_filters": "builders of list 0x09dec554 via tools/search_filters.py (optional)",
    "engine_refs": "card-id immediates used as card ids in engine code via tools/card_refs.py",
    "family_split": "per-card branches of family-shared resolve handlers and the LP chain via tools/family_split.py",
    "fallback_effect": "icon fallback of duel_effects_find_record to S/T records 0-2 (placeholder id 0xe74)",
}
CONFIDENCE = {
    "identity": "high", "lists": "high", "target_filter": "high", "filter_calls": "medium", "fusion": "high",
    "ritual": "high", "ai": "high", "tokens": "high", "fallback_effect": "high", "stat_mods": "medium", "search_filters": "medium",
}


def hx(value, width=6):
    return f"{value:#0{width}x}"


# ---------------------------------------------------------------------------------------------- tokens


def token_entries(module):
    """(index, card id, token card id, count, position) of the token table. `module` needs words()."""
    out = []
    for i in range(TOKEN_COUNT):
        lo, hi = module.words(TOKEN_TABLE + 8 * i, 2)
        out.append((i, lo & 0xFFFF, lo >> 16, hi & 0xFFFF, hi >> 16))
    return out


def check_tokens(module, entries, cards=None):
    problems = []
    immediates, refs = fu.code_facts(module, TOKEN_LOOKUP, TOKEN_LOOKUP_SIZE)
    if TOKEN_TABLE not in refs:
        problems.append(f"duel_effects_find_token_entry ({TOKEN_LOOKUP:#010x}) does not reference {TOKEN_TABLE:#010x}")
    if TOKEN_COUNT not in immediates:
        problems.append(f"duel_effects_find_token_entry lacks the table length {TOKEN_COUNT:#x}")
    for i, cid, token, _, position in entries:
        if not (FIRST_CARD <= cid <= LAST_CARD and FIRST_CARD <= token <= LAST_CARD):
            problems.append(f"token entry {i}: id out of range")
        if position not in TOKEN_POSITIONS:
            problems.append(f"token entry {i}: position {position} unknown")
        if cards is not None and token in cards and cards[token]["kind"] != TOKEN_KIND:
            problems.append(f"token entry {i}: {token:#06x} is not a token card")
    return problems


# ---------------------------------------------------------------------------------------------- search filters


def load_search_filters(prx_bytes, csv_path=None, module=None, tools_dir=HERE):
    """Optional per-card search filters: ({card id: [dict]}, note).

    Sources, in order: a CSV with a `card_id` column (`--search-filters`); else tools/search_filters.py when it
    exists and exposes `card_filters(prx_bytes)`, which returns either a mapping card id -> dict or list of
    dicts, or an iterable of dicts with a `card_id` key (int or hex string). Absence is not an error."""
    def norm(cid):
        return int(cid, 0) if isinstance(cid, str) else int(cid)

    out = collections.defaultdict(list)
    if csv_path:
        with open(csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                out[norm(row["card_id"])].append({k: v for k, v in row.items() if k != "card_id"})
        return dict(out), f"csv {Path(csv_path).name}"
    if module is None:
        path = Path(tools_dir) / "search_filters.py"
        if not path.exists():
            return {}, "absent (tools/search_filters.py not found)"
        try:
            spec = importlib.util.spec_from_file_location("re_search_filters", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as error:  # an unfinished concurrent tool must not break the join
            return {}, f"skipped (import failed: {error})"
    fn = getattr(module, "card_filters", None)
    if fn is None:
        return {}, "skipped (search_filters has no card_filters())"
    try:
        result = fn(prx_bytes)
        items = result.items() if hasattr(result, "items") else ((r["card_id"], r) for r in result)
        for cid, value in items:
            for v in (value if isinstance(value, list) else [value]):
                out[norm(cid)].append({k: x for k, x in dict(v).items() if k != "card_id"})
    except Exception as error:
        return {}, f"skipped (card_filters failed: {error})"
    return dict(out), "tools/search_filters.py"


# ---------------------------------------------------------------------------------------------- extraction


def identity_of(info, index):
    p = info.properties(index)
    mask = info.genre_mask(index)
    return {"index": index, "name": info.name(index), "passcode": info.passes[index], "kind": p["kind"],
            "kind_name": KINDS.get(p["kind"], f"kind{p['kind']}"), "attribute": p["attribute"],
            "attribute_name": ATTRIBUTES.get(p["attribute"], ""), "race": p["race"],
            "race_name": RACES.get(p["race"], ""), "level": p["level"], "atk": p["atk"], "def": p["def"],
            "icon": p["icon"], "icon_name": ICONS.get(p["icon"], "") if p["kind"] in (27, 29) else "",
            "genre_mask": f"{mask:#014x}", "genres": info.genres(index)}


def chain_label(fn, registry):
    """(label, confidence) of a compare chain function."""
    if fn in PARAM_CHAINS:
        return PARAM_CHAINS[fn]
    name = registry.name(fn)
    return (name, "medium") if not ec.DEFAULT_NAME.match(name) else (f"chain_{fn:08x}", "low")


def all_chain_cases(module, functions, users, registry):
    """Cases of every compare chain (>= 8 card-id tests) of effect_params, with class, label and confidence."""
    rows, param_cases = ep.compare_chains(module, functions, users)
    out = []
    for r in rows:
        fn = int(r["function"], 16)
        label, conf = chain_label(fn, registry)
        if r["class"] == "parameter":
            cases = [c for c in param_cases if c["function"] == r["function"]]
        else:
            cases = [{"function": r["function"], "card_id": f"{cid:#x}",
                      "kind": "constant" if v is not None else "computed",
                      "value": "" if v is None else ep.signed(v), "target": f"{b.target:#010x}"}
                     for cid, v, b in ep.analyse_chain(module, fn, ep.function_end(functions, fn))]
        for c in cases:
            out.append({**c, "class": r["class"], "label": label, "confidence": conf})
    return out


def extract(prx_bytes, cardinfo_bytes, functions_path, categories_path, boot_path=None, depth=3,
            search=None, draw_path=None):
    """Run every source tool and return (sources dict for build_specs, problems)."""
    info = ci.CardInfo(cardinfo_bytes, "E")
    cards = {}
    for index in range(1, info.count):
        ident = identity_of(info, index)
        cards[info.properties(index)["id"]] = ident

    module = ep.Module(prx_bytes)
    fmod, amod = fu.Module(prx_bytes), ait.Module(prx_bytes)
    imports = ec.load_imports(boot_path, prx_bytes) if boot_path else None
    registry = ec.Registry(ec.load_registry(functions_path), module, imports)
    mapping = ec.Mapping.load(categories_path)

    problems = [f"effect_params: {p}" for p in ep.check(module)]
    problems += [f"stat_mods: {p}" for p in sm.check(module)]
    problems += [f"fusion: {p}" for p in fu.check(fmod, {c: (v["name"], {"kind": v["kind"], "icon": v["icon"],
                                                                        "level": v["level"]})
                                                       for c, v in cards.items()})]
    cls_problems, _ = ec.check(module, registry, mapping)
    problems += [f"effect_classify: {p}" for p in cls_problems]

    classifier = ec.Classifier(module, registry, mapping, depth)
    refined, _ = fs.split_records(classifier)
    records = []
    for table, index, cid, handlers in ec.effect_records(module):
        slots = {}
        unnamed_resolve, unnamed = 0, set()
        commands = []
        for k, ((slot, _), h) in enumerate(zip(ec.SLOTS, handlers)):
            if not h:
                continue
            c = classifier.closure(h)
            slots[slot] = {"handler": h, "name": registry.name(h),
                           "categories": sorted({x for x, r in c["categories"] if r == "effect"}),
                           "meta": sorted({x for x, r in c["categories"] if r == "meta"})}
            unnamed |= c["unnamed"]
            if k == 0:
                unnamed_resolve = len(c["unnamed"])
                commands = sorted(c["commands"])
        ref = refined.get((table, index))
        if ref and "resolve" in slots:
            res = slots["resolve"]
            res["categories_refined"] = sorted((set(ref["after"]) & set(res["categories"])) | set(ref["added"]))
            res["refinement"] = {"method": ref["method"], "confidence": ref["confidence"],
                                 "removed": sorted(set(ref["removed"]) & set(res["categories"])),
                                 "added": ref["added"], **({"lp_amounts": ref["lp_signs"]} if ref["lp_signs"] else {})}
        records.append({"table": table, "index": index, "card_id": cid, "slots": slots, "commands": commands,
                        "unnamed_resolve": unnamed_resolve, "unnamed": len(unnamed)})

    functions = ep.function_starts(module)
    users = ep.handler_users(module)
    filters = {(r["table"], r["index"]): r for r in ep.target_filters(module)}
    filter_calls = collections.defaultdict(list)
    for r in ep.target_filter_calls(module, functions, users):
        if r["function"] and r["flags"]:
            filter_calls[int(r["function"], 16)].append(
                {k: r[k] for k in ("call_site", "flags", "side", "zone", "face", "position", "actions")})
    lists = [(name, index, cid, h, registry.name(h) if h else "") for name, index, cid, h in ep.list_records(module)
             if name in OWN_LISTS]
    draws = {int(r["card_id"], 16): r for r in ep.draw_counts(module)}
    cases = all_chain_cases(module, functions, users, registry)
    starts, names = cr.load_registry(functions_path)
    engine_refs = cr.all_refs(prx_bytes, starts, names, Path(boot_path).read_bytes() if boot_path else None,
                              Path(draw_path).read_bytes() if draw_path else None)
    ai = [(key, name, i, cid, h, registry.name(h) if h else "") for key, name, i, _, cid, h in ait.entries(amod)]
    ai += [(key, "chain_state_list", i, cid, h, registry.name(h)) for key, i, _, cid, h in ait.list_entries(amod)]
    tokens = token_entries(module)
    problems += [f"tokens: {p}" for p in check_tokens(module, tokens, cards)]
    search_filters, search_note = search if search is not None else ({}, "not requested")
    sources = {
        "cards": cards, "records": records, "target_filters": filters, "filter_calls": dict(filter_calls),
        "lists": lists, "draw_counts": draws, "chain_cases": cases, "stat_mods": sm.stat_uses(module),
        "recipes": [(r.index, r.fusion, r.materials) for r in fu.recipes(fmod)],
        "hardcoded_fusions": dict(fu.HARDCODED),
        "rituals": [(r.index, r.monster, r.spell, r.level) for r in fu.rituals(fmod)],
        "ai": ai, "tokens": tokens, "search_filters": search_filters, "search_note": search_note,
        "ai_missing": set(ait.missing_cards(amod, set(cards))),
        "engine_refs": engine_refs,
    }
    return sources, problems


# ---------------------------------------------------------------------------------------------- join


def material(code, cards):
    if code < fu.GENERIC_LIMIT:
        return {"code": hx(code, 4), "generic": True, "description": fu.MATERIAL_CODES.get(code, "unknown")}
    return {"code": hx(code), "generic": False, "name": cards.get(code, {}).get("name", "")}


def record_confidence(rec, handler_cards):
    """low: no effect category in any slot; medium: the resolve handler serves several cards (family union) or
    the resolve closure reaches unnamed callees; high otherwise. A shared resolve handler whose per-card split
    (tools/family_split.py) has high confidence counts as unshared."""
    if not any(s["categories"] for s in rec["slots"].values()):
        return "low"
    res = rec["slots"].get("resolve")
    if res is None or rec["unnamed_resolve"]:
        return "medium"
    split = res.get("refinement", {}).get("confidence") == "high"
    if len(handler_cards.get(res["handler"], ())) > 1 and not split:
        return "medium"
    return "high"


def record_complete_out(rec):
    """An output effect record reaches an effect category and its resolve closure has no unnamed callee."""
    return rec["unnamed_resolve_callees"] == 0 and any(sl["categories"] for sl in rec["slots"].values())


def build_specs(src):
    """Join the sources (see extract) into {card id: spec dict}, ordered by card id."""
    cards = src["cards"]
    handler_cards = collections.defaultdict(set)
    for rec in src["records"]:
        for s in rec["slots"].values():
            handler_cards[s["handler"]].add(rec["card_id"])
    for _, _, cid, h, _ in src["lists"]:
        if h:
            handler_cards[h].add(cid)

    specs = {}

    def spec(cid):
        if cid not in specs:
            specs[cid] = {"card_id": hx(cid), "card_id_dec": cid, "released": cid in cards,
                          "identity": cards.get(cid), "effects": [], "lists": [], "params": {}, "fusion": {},
                          "ai": [], "tokens": [], "token_of": []}
        return specs[cid]

    for cid in cards:
        spec(cid)
    first_index = {}
    for rec in src["records"]:
        cid, key = rec["card_id"], (rec["table"], rec["card_id"])
        first_index.setdefault(key, rec["index"])
        slots = {}
        for slot, s in rec["slots"].items():
            calls = src["filter_calls"].get(s["handler"])
            slots[slot] = {"handler": f"{s['handler']:#010x}", "name": s["name"],
                           "named": not ec.DEFAULT_NAME.match(s["name"]),
                           "shared_by_cards": len(handler_cards[s["handler"]]), "categories": s["categories"],
                           "meta": s["meta"], **({"filter_calls": calls} if calls else {}),
                           **{k: s[k] for k in ("categories_refined", "refinement") if k in s}}
        out = {"table": rec["table"], "index": rec["index"], "variant": rec["index"] - first_index[key],
               "slots": slots, "commands": [hx(c, 4) for c in rec["commands"]],
               "unnamed_resolve_callees": rec["unnamed_resolve"], "unnamed_callees": rec["unnamed"],
               "confidence": record_confidence(rec, handler_cards)}
        tf = src["target_filters"].get((rec["table"], rec["index"]))
        if tf:
            out["target_filter"] = {k: tf[k] for k in ("flags", "form", "side", "zone", "face", "position")}
            out["target_filter"]["actions"] = tf["actions"].split()
        spec(cid)["effects"].append(out)
    for name, index, cid, h, hname in src["lists"]:
        spec(cid)["lists"].append({"list": name, "index": index, "handler": f"{h:#010x}" if h else None,
                                   "name": hname, "shared_by_cards": len(handler_cards.get(h, ())) if h else 0})

    for cid, r in src["draw_counts"].items():
        constant = r["kind"] == "constant"
        spec(cid)["params"]["draw_count"] = {"kind": r["kind"], "value": r["value"] if constant else None,
                                             "summary": r.get("summary", ""),
                                             "confidence": "high" if constant else "medium"}
    for r in src["chain_cases"]:
        fn = int(r["function"], 16)
        if fn == ep.DRAW_COUNT:
            continue  # reported as draw_count
        label, conf = (r["label"], r["confidence"]) if "label" in r else \
            PARAM_CHAINS.get(fn, (f"chain_{fn:08x}", "low"))
        constant = r["kind"] == "constant"
        spec(int(r["card_id"], 16))["params"].setdefault("chains", []).append(
            {"label": label, "function": r["function"], "kind": r["kind"], "value": r["value"] if constant else None,
             "confidence": conf if constant else "low" if conf == "low" else "medium",
             "class": r.get("class", "parameter")})
    for r in src["stat_mods"]:
        spec(int(r["card_id"], 16))["params"].setdefault("stat_mods", []).append(
            {k: r[k] for k in ("section", "function_name", "use", "address", "values", "helper", "calls")})
    for cid, rows in src["search_filters"].items():
        spec(cid)["params"]["search_filters"] = rows

    for index, fusion, codes in src["recipes"]:
        spec(fusion)["fusion"].setdefault("recipes", []).append(
            {"source": "table", "index": index, "materials": [material(c, cards) for c in codes]})
    for fusion, codes in src["hardcoded_fusions"].items():
        spec(fusion)["fusion"].setdefault("recipes", []).append(
            {"source": "code", "index": None, "materials": [material(c, cards) for c in codes]})
    for fusion, codes in [(f, c) for _, f, c in src["recipes"]] + list(src["hardcoded_fusions"].items()):
        for c in codes:
            if c >= fu.GENERIC_LIMIT:
                lst = spec(c)["fusion"].setdefault("material_of", [])
                if hx(fusion) not in lst:
                    lst.append(hx(fusion))
    for index, monster, spell, level in src["rituals"]:
        spec(monster)["fusion"].setdefault("ritual_monster", []).append(
            {"index": index, "spell": hx(spell), "level_total": level})
        spec(spell)["fusion"].setdefault("ritual_spell", []).append(
            {"index": index, "monster": hx(monster), "level_total": level})

    for key, name, i, cid, h, hname in src["ai"]:
        spec(cid)["ai"].append({"table": key, "name": name, "index": i,
                                "handler": f"{h:#010x}" if h else None, "handler_name": hname})
    for i, cid, token, count, position in src["tokens"]:
        spec(cid)["tokens"].append({"index": i, "token_id": hx(token),
                                    "token_name": cards.get(token, {}).get("name", ""), "count": count or None,
                                    "count_computed": count == 0, "position": TOKEN_POSITIONS.get(position, position)})
        if hx(cid) not in spec(token)["token_of"]:
            spec(token)["token_of"].append(hx(cid))

    for cid, rows in src.get("engine_refs", {}).items():  # ids no other source knows are not added
        if cid in specs:
            specs[cid]["engine_refs"] = engine_ref_groups(rows)
            semantics = cr.describe(src["engine_refs"], cid)
            if semantics:
                specs[cid]["engine_semantics"] = semantics
    placeholder = {e["index"]: e for e in specs.get(PLACEHOLDER_ID, {}).get("effects", []) if e["table"] == "S/T"}
    for cid, s in specs.items():
        ident = s["identity"]
        if ident and ident["kind"] == SPELL_KIND and not s["effects"] and ident["icon"] in FALLBACK_RECORD:
            rec = placeholder.get(FALLBACK_RECORD[ident["icon"]])
            if rec:
                s["fallback_effect"] = {"table": "S/T", "index": rec["index"], "card_id": hx(PLACEHOLDER_ID),
                                        "reason": f"no own record; icon {ident['icon_name']}",
                                        "complete": record_complete_out(rec)}
    for cid, s in specs.items():
        s["spec_status"] = spec_status(s)
        s["sources"] = {k: SOURCES[k] for k in field_keys(s)}
        s["confidence"] = field_confidence(s)
    return dict(sorted(specs.items()))


def engine_ref_groups(rows):
    """card_refs rows of one card grouped by function: the registry name gives the coarse meaning."""
    by = {}
    for r in rows:
        g = by.setdefault((r["module"], r["function"]), {
            "module": r["module"], "function": f"{r['function']:#010x}", "function_name": r["function_name"],
            "group": r["group"], "named": not ec.DEFAULT_NAME.match(r["function_name"]), "kinds": {},
            "references": [], "callees": [], "values": [], "operands": [], "semantics": []})
        g["kinds"][r["kind"]] = g["kinds"].get(r["kind"], 0) + 1
        g["references"].append(f"{r['address']:#010x}")
        if r["kind"] == "arg" and r["detail"] not in g["callees"]:
            g["callees"].append(r["detail"])
        if r["value"] is not None and r["value"] not in g["values"]:
            g["values"].append(r["value"])
        if r["operand"] and r["operand"] not in g["operands"]:
            g["operands"].append(r["operand"])
        sem = r.get("semantics")
        if sem:
            entry = {k: sem.get(k) for k in ("tag", "phrase", "modality", "confidence", "label")}
            if entry not in g["semantics"]:
                g["semantics"].append(entry)
    return sorted(by.values(), key=lambda g: (not g["named"], g["group"], g["module"], g["function"]))


def strong_engine_refs(s):
    """Engine references that name this card (eq, switch, or an argument), not only a range bound."""
    return [g for g in s.get("engine_refs", ()) if set(g["kinds"]) & cr.STRONG]


def field_keys(s):
    keys = ["identity"] if s["identity"] else []
    keys += [k for k in ("effects", "lists", "ai", "tokens") if s[k]]
    if any("target_filter" in e for e in s["effects"]):
        keys.append("target_filter")
    if any("filter_calls" in sl for e in s["effects"] for sl in e["slots"].values()):
        keys.append("filter_calls")
    keys += [k for k in ("draw_count", "chains", "stat_mods", "search_filters") if k in s["params"]]
    if "recipes" in s["fusion"] or "material_of" in s["fusion"]:
        keys.append("fusion")
    if any(k.startswith("ritual") for k in s["fusion"]):
        keys.append("ritual")
    if "fallback_effect" in s:
        keys.append("fallback_effect")
    if s["token_of"] and "tokens" not in keys:
        keys.append("tokens")
    if s.get("engine_refs"):
        keys.append("engine_refs")
    if any("refinement" in e["slots"].get("resolve", {}) for e in s["effects"]):
        keys.append("family_split")
    return keys


def field_confidence(s):
    out = {}
    for k in field_keys(s):
        if k == "effects":
            levels = [e["confidence"] for e in s["effects"]]
            out[k] = "low" if "low" in levels else "medium" if "medium" in levels else "high"
        elif k == "draw_count":
            out[k] = s["params"]["draw_count"]["confidence"]
        elif k == "chains":
            levels = {c["confidence"] for c in s["params"]["chains"]}
            out[k] = "high" if levels == {"high"} else "low" if levels == {"low"} else "medium"
        elif k == "family_split":
            levels = {e["slots"]["resolve"]["refinement"]["confidence"] for e in s["effects"]
                      if "refinement" in e["slots"].get("resolve", {})}
            out[k] = "high" if levels == {"high"} else "medium"
        elif k == "engine_refs":
            strong = strong_engine_refs(s)
            idlike = any(o.startswith(cr.ID_OPERANDS) for g in strong for o in g["operands"]) or \
                any("arg" in g["kinds"] or "switch" in g["kinds"] for g in strong)
            out[k] = "medium" if idlike else "low"
        else:
            out[k] = CONFIDENCE.get(k, "medium")
    return out


def spec_status(s):
    """unreleased: no cardinfo record; vanilla: a kind without effect text and no effect data;
    full: every effect record reaches an effect category and its resolve closure has no unnamed callee;
    partial: effect records not all complete, or only side data (lists, chains, stat mods, ...);
    engine_only: an effect card whose only data is engine code that tests its id (card_refs eq/switch/arg
    references, or compare chains that are not parameter chains);
    missing: an effect card with no data from any source; placeholder: the fallback id 0xe74.
    A spell served by a fallback record is full when that record is complete and the per-card part is known
    (ritual: a ritual-table entry; equip and field: stat modifiers), else partial."""
    if s["card_id_dec"] == PLACEHOLDER_ID:
        return "placeholder"
    if not s["released"]:
        return "unreleased"
    if s["effects"]:
        return "full" if all(record_complete_out(e) for e in s["effects"]) else "partial"
    fb = s.get("fallback_effect")
    if fb:
        per_card = s["fusion"].get("ritual_spell") if fb["index"] == FALLBACK_RECORD[6] else \
            s["params"].get("stat_mods")
        return "full" if fb["complete"] and per_card else "partial"
    params = {k: v for k, v in s["params"].items() if k != "chains"}
    if any(c.get("class", "parameter") == "parameter" for c in s["params"].get("chains", ())):
        params["chains"] = True
    side = s["lists"] or params or s["tokens"] or s["fusion"].get("ritual_spell")
    if s["identity"]["kind"] in NO_TEXT_KINDS:
        return "vanilla"
    if side:
        return "partial"
    return "engine_only" if strong_engine_refs(s) or s["params"].get("chains") else "missing"


# ---------------------------------------------------------------------------------------------- check and output


def join_report(src, specs):
    """(problems, lines) of the join checks."""
    problems, lines = [], []
    cards = src["cards"]
    ids = {r["card_id"] for r in src["records"]}
    out_of_range = sorted(c for c in ids if not FIRST_CARD <= c <= LAST_CARD and c != PLACEHOLDER_ID)
    if out_of_range:
        problems.append(f"effect records with ids outside {FIRST_CARD:#x}-{LAST_CARD:#x}: "
                        + " ".join(hx(c) for c in out_of_range))
    unreleased = sorted(c for c in ids if c not in cards and c != PLACEHOLDER_ID)
    placeholder = sum(1 for r in src["records"] if r["card_id"] == PLACEHOLDER_ID)
    joined = sum(1 for r in src["records"] if r["card_id"] in cards)
    emitted = sum(len(s["effects"]) for s in specs.values())
    if emitted != len(src["records"]):
        problems.append(f"{len(src['records'])} effect records but {emitted} in the output")
    lines.append(f"effect records: {len(src['records'])}; {joined} join a cardinfo record, "
                 f"{placeholder} carry the fallback placeholder id {PLACEHOLDER_ID:#06x}, "
                 f"{len(src['records']) - joined - placeholder} belong to {len(unreleased)} unreleased ids")
    lines.append("unreleased ids with effect records: " + (" ".join(hx(c) for c in unreleased) or "none"))
    ai_missing = src.get("ai_missing", set())
    if ai_missing:
        not_in_ai = sorted(set(unreleased) - ai_missing)
        no_effects = sorted(ai_missing - ids)
        lines.append(f"AI tables name {len(ai_missing)} unreleased ids; {len(ai_missing & set(unreleased))} of them "
                     f"have effect records" + (f"; without effect records: {' '.join(hx(c) for c in no_effects)}"
                                                if no_effects else "")
                     + (f"; unreleased ids only in the effect tables: {len(not_in_ai)}" if not_in_ai else ""))
    other = sorted(c for c, s in specs.items() if not s["released"] and c not in ids)
    if other:
        lines.append(f"other unreleased ids referenced (lists, AI, chains, fusion, tokens): "
                     + " ".join(hx(c) for c in other))
    status = collections.Counter(s["spec_status"] for s in specs.values())
    released = [s for s in specs.values() if s["released"]]
    lines.append(f"cards: {len(cards)} in cardinfo, {len(specs)} ids in the output")
    lines.append("spec status: " + ", ".join(f"{k} {status[k]}" for k in
                                             STATUSES))
    missing = [s for s in released if s["spec_status"] == "missing"]
    lines.append("missing cards by kind: " + (", ".join(
        f"{k} {n}" for k, n in sorted(collections.Counter(s["identity"]["kind_name"] for s in missing).items()))
        or "none"))
    eng = [s for s in released if s["spec_status"] == "engine_only"]
    groups = collections.Counter(g["group"] or "unnamed" for s in eng for g in strong_engine_refs(s))
    lines.append(f"engine_only cards: {len(eng)}, by kind: " + ", ".join(
        f"{k} {n}" for k, n in sorted(collections.Counter(s["identity"]["kind_name"] for s in eng).items()))
        + "; referencing functions by group: " + ", ".join(f"{k} {n}" for k, n in groups.most_common()))
    refs = src.get("engine_refs", {})
    lines.append(f"engine references: {sum(len(v) for v in refs.values())} to {len(refs)} ids")
    own = [s for s in released if s["effects"]]
    full_own = sum(1 for s in own if s["spec_status"] == "full")
    lines.append(f"released cards with own effect records: {len(own)}, full {full_own}"
                 + (f" ({100 * full_own / len(own):.1f} %)" if own else ""))
    fb = [s for s in released if "fallback_effect" in s]
    lines.append(f"spells served by the icon fallback: {len(fb)}, full {sum(s['spec_status'] == 'full' for s in fb)}")
    conf = collections.Counter(e["confidence"] for s in specs.values() for e in s["effects"])
    lines.append("effect record confidence: " + ", ".join(f"{k} {conf[k]}" for k in ("high", "medium", "low")))
    refs = [e["slots"]["resolve"] for s in specs.values() for e in s["effects"]
            if "refinement" in e["slots"].get("resolve", {})]
    changed = [r for r in refs if r["categories_refined"] != r["categories"]]
    split = collections.Counter(r["refinement"]["confidence"] for r in refs)
    lines.append(f"family split: {len(refs)} resolve slots examined, {len(changed)} refined "
                 f"({sum(len(set(r['categories']) - set(r['categories_refined'])) for r in changed)} labels removed); "
                 f"split confidence high {split['high']}, medium {split['medium']}")
    lines.append(f"search filters: {src.get('search_note', '')}; {len(src['search_filters'])} cards")
    return problems, lines


STATUSES = ("full", "partial", "engine_only", "missing", "vanilla", "unreleased", "placeholder")
CSV_FIELDS = ["card_id", "name", "kind", "released", "spec_status", "effect_records", "tables", "fallback", "resolve_categories",
              "target_filters", "draw_count", "lp_cost", "chains", "stat_mod_sections", "fusion_role", "ai_tables",
              "tokens", "search_filters", "effects_confidence", "engine_ref_functions", "engine_ref_groups",
              "resolve_categories_refined"]


def csv_row(s):
    ident = s["identity"] or {}
    chains = s["params"].get("chains", [])
    lp = [str(c["value"]) if c["value"] is not None else "computed" for c in chains if c["label"] == "lp_cost"]
    draw = s["params"].get("draw_count")
    roles = [k for k in ("recipes", "material_of", "ritual_monster", "ritual_spell") if k in s["fusion"]]
    return {"card_id": s["card_id"], "name": ident.get("name", ""), "kind": ident.get("kind_name", ""),
            "released": int(s["released"]), "spec_status": s["spec_status"], "effect_records": len(s["effects"]),
            "tables": " ".join(sorted({e["table"] for e in s["effects"]} | {x["list"] for x in s["lists"]})),
            "fallback": f"S/T:{s['fallback_effect']['index']}" if "fallback_effect" in s else "",
            "resolve_categories": " ".join(sorted({c for e in s["effects"]
                                                   for c in e["slots"].get("resolve", {}).get("categories", [])})),
            "target_filters": sum(1 for e in s["effects"] if "target_filter" in e),
            "draw_count": "" if not draw else draw["value"] if draw["value"] is not None else "computed",
            "lp_cost": " ".join(lp), "chains": " ".join(sorted({c["label"] for c in chains})),
            "stat_mod_sections": " ".join(sorted({m["section"] for m in s["params"].get("stat_mods", [])})),
            "fusion_role": " ".join(roles), "ai_tables": " ".join(sorted({a["table"] for a in s["ai"]})),
            "tokens": " ".join(t["token_id"] for t in s["tokens"]),
            "search_filters": len(s["params"].get("search_filters", [])),
            "effects_confidence": s["confidence"].get("effects", ""),
            "engine_ref_functions": len(s.get("engine_refs", ())),
            "engine_ref_groups": " ".join(sorted({g["group"] or "unnamed" for g in s.get("engine_refs", ())})),
            "resolve_categories_refined": " ".join(sorted({
                c for e in s["effects"] for c in e["slots"].get("resolve", {}).get(
                    "categories_refined", e["slots"].get("resolve", {}).get("categories", []))}))}


def write_outputs(out_dir, specs, meta):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "card_effects.jsonl", "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"schema": SCHEMA, "meta": meta}, ensure_ascii=False) + "\n")
        for s in specs.values():
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    with open(out_dir / "card_effects.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(csv_row(s) for s in specs.values())


def main(argv=None):
    parser = argparse.ArgumentParser(description="Join the per-card effect analyses into one specification.")
    parser.add_argument("prx", type=Path, help="gmodule/rel_duel_eng.prx")
    parser.add_argument("cardinfo", type=Path, help="duelsys/cardinfo_eng.ehp")
    parser.add_argument("-o", "--out", type=Path, help="output directory (under extracted/)")
    parser.add_argument("--check", action="store_true", help="validate the joins and print the counts")
    parser.add_argument("--boot", type=Path, help="SYSDIR/BOOT.BIN: name import stubs by their BOOT.BIN name and "
                                                  "scan it for card-id tests")
    parser.add_argument("--draw", type=Path, help="gmodule/rel_duel_draw.prx: scan it for card-id tests")
    parser.add_argument("--functions", type=Path, default=HERE.parent / "re" / "functions.csv")
    parser.add_argument("--categories", type=Path, default=HERE / "effect_categories.csv")
    parser.add_argument("--depth", type=int, default=3, help="call levels for the categories (default 3)")
    parser.add_argument("--search-filters", type=Path, help="CSV with a card_id column (instead of the tool)")
    args = parser.parse_args(argv)
    if not args.check and not args.out:
        parser.error("-o/--out is required unless --check is given")
    data = args.prx.read_bytes()
    search = load_search_filters(data, args.search_filters)
    src, problems = extract(data, args.cardinfo.read_bytes(), args.functions, args.categories,
                            args.boot, args.depth, search, args.draw)
    specs = build_specs(src)
    join_problems, lines = join_report(src, specs)
    problems += join_problems
    for p in problems:
        print("problem:", p, file=sys.stderr)
    for line in lines:
        print(line)
    if not args.check:
        write_outputs(args.out, specs, {"depth": args.depth, "search_filters": src["search_note"],
                                        "boot": bool(args.boot), "draw": bool(args.draw)})
        print(f"wrote {len(specs)} cards to {args.out}")
    print("ok" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
