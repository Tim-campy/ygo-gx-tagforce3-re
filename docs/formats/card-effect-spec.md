# Per-card effect specification (`tools/card_effects.py`)

The per-card effect specification is the artifact a future port consumes: one JSON object per card id that joins everything the extractors know about that card's effect. It is generated from the maintainer's own files at run time. The repository keeps only the tool and this schema; the generated files are game data and stay in `extracted/`.

```
python3 -I tools/card_effects.py <USRDIR>/gmodule/rel_duel_eng.prx <USRDIR>/duelsys/cardinfo_eng.ehp \
        --boot <SYSDIR>/BOOT.BIN -o extracted/card_effects [--functions re/functions.csv] [--depth 3] \
        [--search-filters <csv>]
python3 -I tools/card_effects.py <prx> <cardinfo> --boot <BOOT.BIN> --check
python3 -I tools/tests/test_card_effects.py
```

The tool imports the other extractors with `importlib` from `tools/` and copies none of their code. Each source keeps its own checks: `effect_params.check`, `stat_mods.check`, `fusion.check` (with the card database), `effect_classify.check` (which includes `ai_tables.check`), plus a check of the token table defined here. A problem from any of them makes `--check` fail. A full run takes about 6 s.

Outputs:

- `card_effects.jsonl`: the first line is a header `{"schema": 1, "meta": {...}}`, which records the depth, whether `--boot` was given and the search-filter source. Then one object per card id, sorted by id.
- `card_effects.csv`: one summary row per card id (columns at the end of this document).

## Sources

| Source | Tool | What it contributes | Key |
| --- | --- | --- | --- |
| `cardinfo_eng.ehp` | `tools/cardinfo.py` | Name, passcode, kind, attribute, Type, Level, ATK/DEF, spell/trap icon, genre bits and names | `identity` |
| Four 24-byte effect tables | `tools/effect_classify.py` (`effect_params.table_records`) | Records with their table, index, the five slot handlers and the categories each slot reaches | `effects` |
| `re/functions.csv` (+ `BOOT.BIN` imports) | `effect_classify.Registry` | Handler names; import stubs named after their `BOOT.BIN` target with `--boot` | `effects[].slots.*.name` |
| 8-byte lists L1 `0x09dec554`, L4 `0x09e010b0` | `effect_params.list_records` | Search/summon-from-deck builders (L1) and End Phase handlers (L4) | `lists` |
| Slot `+08` filter stubs | `effect_params.target_filters` | Decoded target-filter flag word | `effects[].target_filter` |
| `jal duel_effects_target_filter` sites | `effect_params.target_filter_calls` | Constant flag words inside a slot handler | `effects[].slots.*.filter_calls` |
| `duel_effects_get_draw_count` | `effect_params.draw_counts` | Number of cards drawn (negative: the opponent draws) | `params.draw_count` |
| Parameter compare chains | `effect_params.compare_chains` | `card id -> value` cases of the 20 parameter chains | `params.chains` |
| ATK/DEF stat functions | `stat_mods.stat_uses` | Where the card's ATK/DEF modifier sits (section, constants, helper) | `params.stat_mods` |
| Fusion recipe table, hard-coded fusions, ritual table | `tools/fusion.py` | Recipes, materials, `material_of`, ritual pairs | `fusion` |
| AI priority tables and u16 lists | `tools/ai_tables.py` | Membership (table, index, handler and its name) | `ai` |
| Token table `0x09e019ec` | parsed in `card_effects.py` | Token id, count, position | `tokens`, `token_of` |
| Fallback records S/T 0-2 (placeholder id `0x0e74`) | `card_effects.py` | The generic record a spell without its own record uses | `fallback_effect` |
| Search filters of `0x09dec554` | `tools/search_filters.py` (optional) | Whatever per-card filter the tool decodes | `params.search_filters` |

### Token table

`duel_effects_find_token_entry` (`0x09befee0`, 68 bytes) searches linearly through 46 records of 8 bytes at `0x09e019ec`. The table is not sorted; for example `0x1da4` comes before `0x1d8d`.

| Offset | Type | Field |
| --- | --- | --- |
| `+0` | `u16` | Card id of the effect |
| `+2` | `u16` | Token card id |
| `+4` | `u16` | Count; 0 means the handler computes it |
| `+6` | `u16` | Position: 0 Attack, 1 Defense, 2 either |

`--check` verifies the following:

- the lookup builds the address `0x09e019ec` and has the bound `0x2e`;
- every id is in the card range;
- every position is 0-2;
- every token id is a kind-21 (token) card.

All 46 records pass on the disc. Confidence H. The two `u16` pairs after the table (`0x000a 0 0 0`) are not records, because the bound stops the search at 46.

### Fallback records

`docs/subsystems/summon.md` establishes the following (H). For a spell with no record of its own, `duel_effects_find_record` falls back on its icon to the first three S/T records, which carry the placeholder id `0x0e74`:

| Icon | Record |
| --- | --- |
| field | 0 |
| equip | 1 |
| ritual | 2 |

The tool writes the placeholder as a separate object (`spec_status` `placeholder`). Each spell of those icons that has no record gets `fallback_effect` = `{table, index, card_id, reason, complete}`. On the disc 126 spells use the fallback.

### Search filters (optional input)

`tools/search_filters.py` is being written separately. `card_effects.py` uses it, and does not fail without it:

1. `--search-filters <csv>`: any CSV with a `card_id` column (decimal or `0x` hex). The other columns are copied as strings into `params.search_filters`.
2. Otherwise, if `tools/search_filters.py` exists and exposes `card_filters(prx_bytes)`, the tool calls it. The function may return either:
   - a mapping from card id (int or hex string) to a dict or a list of dicts; or
   - an iterable of dicts that each carry a `card_id` key.
3. In every other case, including a failed import, a missing function or an exception, the input is skipped. The reason is printed in the `--check` summary line `search filters: ...` and stored in the JSONL header.

## Object schema (schema 1)

| Field | Type | Source | Notes |
| --- | --- | --- | --- |
| `card_id` | hex string | all | `0x12ec`; `card_id_dec` holds the integer |
| `released` | bool | cardinfo | False when `CARD_IntID` has no record for the id |
| `identity` | object or null | cardinfo | `index name passcode kind kind_name attribute attribute_name race race_name level atk def icon icon_name genre_mask genres`. Enumerations from `cardinfo.md`; `icon_name` only for spells and traps |
| `effects[]` | list | effect tables | One per record, in table order |
| `effects[].table`, `.index` | string, int | | `S/T`, `M1`, `M2`, `M3`; index into the table |
| `effects[].variant` | int | | Position among the card's consecutive records in that table, as `duel_effects_select_record_variant` adds it |
| `effects[].slots` | object | | Keys `resolve` (`+04`), `target_filter` (`+08`), `condition` (`+0c`), `activation` (`+10`), `target_choice` (`+14`); empty slots are omitted |
| `slots.*.handler`, `.name`, `.named` | | registry | Address; registry name, or `FUN_…`; whether the name is meaningful |
| `slots.*.shared_by_cards` | int | effect tables + L1/L4 | Number of distinct card ids whose records use this handler |
| `slots.*.categories`, `.meta` | lists | `effect_classify` | Categories with role `effect`, and with role `meta` (`once_per_turn`, `optional`, …) |
| `slots.*.filter_calls[]` | list | `effect_params` | Constant flag words passed to `duel_effects_target_filter` inside this handler (heuristic function bounds) |
| `effects[].commands` | list | `effect_classify` | Engine command codes reached from the resolve slot |
| `effects[].unnamed_resolve_callees`, `.unnamed_callees` | int | `effect_classify` | Unnamed functions reached (resolve slot only; any slot) |
| `effects[].target_filter` | object | `effect_params` | `flags form side zone face position actions[]` of the slot `+08` stub |
| `effects[].confidence` | high/medium/low | rule below | |
| `fallback_effect` | object | placeholder records | Present only for spells without a record |
| `lists[]` | list | L1/L4 | `list index handler name shared_by_cards` |
| `params.draw_count` | object | draw chain | `kind` constant/computed, `value`, `summary` (what a computed case reads), `confidence` |
| `params.chains[]` | list | compare chains | `label function kind value confidence`; the draw chain is reported only as `draw_count` |
| `params.stat_mods[]` | list | `stat_mods` | `section function_name use address values helper calls` |
| `params.search_filters[]` | list | optional | As delivered by the search-filter source |
| `fusion.recipes[]` | list | `fusion` | `source` (`table` or `code`), `index`, `materials[]` = `{code, generic, name or description}` |
| `fusion.material_of[]` | list | `fusion` | Fusions whose recipe names this id |
| `fusion.ritual_monster[]`, `fusion.ritual_spell[]` | list | `fusion` | `index`, the partner id, `level_total` |
| `ai[]` | list | `ai_tables` | `table name index handler handler_name` |
| `tokens[]` | list | token table | `index token_id token_name count count_computed position` |
| `token_of[]` | list | token table | For a token card: the cards that create it |
| `spec_status` | string | rule below | |
| `sources` | object | | For each populated field, the input and tool it came from |
| `confidence` | object | rule below | For each populated field, high/medium/low |

### Chain labels

These labels and confidences come from `docs/formats/effect-tables.md`:

| Function | Label | Confidence |
| --- | --- | --- |
| `0x09c41400` | `lp_cost` | H |
| `0x09c41c38` | `discard_count` | M |
| `0x09c42310` | `spell_counter_cost` | H |
| `0x09de2310` | `standby_lp_cost` | H |
| `0x09bf4774` | `hand_effect_players` | M |

Every other chain that `effect_params` classifies as a parameter chain gets the label `chain_<address>` and confidence low. A computed case (`value` null) is at most medium.

## Confidence rules

| Field | Rule |
| --- | --- |
| `identity`, `lists`, `target_filter`, `fusion`, `ritual`, `ai`, `tokens`, `fallback_effect` | high: direct table reads with structural checks |
| `effects[].confidence` | low: no slot reaches an `effect` category. Medium: the resolve handler serves more than one card (its categories are the union of the family, see below), or the resolve closure reaches unnamed callees, or there is no resolve handler. High: otherwise |
| `confidence.effects` | The lowest of the card's records |
| `draw_count` | high for a constant, medium for a computed case |
| `chains` | high if all cases are high, low if all are low, otherwise medium |
| `stat_mods`, `filter_calls`, `search_filters` | medium: the section is exact, but the constants of a case body are a heuristic (`stat-modifiers.md`); filter calls rely on heuristic function bounds |

## Spec status

| Status | Rule |
| --- | --- |
| `full` | At least one own effect record, and every record reaches an `effect` category in some slot with no unnamed callee in its resolve closure. A spell served by a fallback record is `full` when that record is complete and the per-card part is known: a ritual-table entry for ritual spells, stat modifiers for equip and field spells. |
| `partial` | Effect records that are not all complete, or only side data (lists, chains, stat mods, tokens, a fallback record). |
| `missing` | An effect-bearing kind with no data from any source. |
| `vanilla` | A kind without effect text (normal, plain fusion/ritual/synchro, normal tuner, token) and no own effect record. Recipes and AI entries are still listed. |
| `unreleased` | The engine knows the id but `cardinfo` has no record. |
| `placeholder` | The fallback id `0x0e74`. |

`full` does not mean the effect is reverse engineered: it means every record maps onto named helpers. Behaviour inside a shared family handler still depends on the card id (next section).

## Figures (disc, registry of this commit, depth 3, `--boot`)

| Measure | Value |
| --- | --- |
| Effect records | 2,600. 2,544 join a `cardinfo` record, 3 carry the placeholder `0x0e74`, 53 belong to 47 unreleased ids |
| Unreleased ids | 47 with effect records. All 18 unreleased ids of the AI tables (`ai-tables.md`) are among them; 29 occur only in the effect tables. 5 more (`0x142d`, `0x1f08`, `0x1f0f`, `0x1f35`, `0x1f37`) appear only in lists, chains, fusion or AI data |
| Output | 3,606 ids for 3,553 `cardinfo` cards |
| Released cards with own effect records | 2,251, of which 781 are `full` (34.7 %) |
| Fallback spells | 126, none `full` yet: the field and equip fallback resolve handlers reach unnamed callees |
| Effect record confidence | high 215, medium 2,314, low 71 |
| Cards per source | target filter 406, draw count 120, LP cost 103, any chain 681, stat modifiers 543, fusion/ritual role 386, AI tables 1,660, token makers 46 |

Run `--check` for the current status counts; they move as helpers are named.

## Known gaps

- **Family handlers.** Handlers are shared by card families: Pot of Greed's resolve handler serves 73 cards, and a handler can branch on the card id. Categories are static reach, so a shared handler reports the union of its family's categories (`effect-classification.md`, "Limits"). The per-card part lives in compare chains and in the parameters above. Where neither isolates it, the record stays at medium confidence. `shared_by_cards` shows how wide the family is.
- **Data-driven searches.** The builders of list `0x09dec554` select deck cards through a filter word that is not yet decoded. Until `tools/search_filters.py` exists, searches such as Reinforcement of the Army show only `move_list_card` plus the list membership in `lists`.
- **Compare chains that are predicates.** `effect_params` keeps only the 20 parameter chains. The 244 unresolved predicate chains (`if (id == A || id == B …)`) and the 1,379 functions that test card ids directly are not joined, so cards whose effect lives only there come out `missing` or `partial`.
- **Unnamed helpers.** Completeness depends on names in `re/functions.csv`. The `full` share rises as the naming worklist of `effect-classification.md` is worked off.
- **Variant selection.** `variant` is the position of the record. The rule that picks a variant at run time (`duel_effects_select_record_variant`) is not part of the spec.
- **AI semantics.** `ai[]` gives membership and handler names only. The handlers' conditions are not decoded.
- **Stat-modifier constants** come from a fall-through scan of the case body and can miss values computed elsewhere.

## CSV summary columns

`card_id name kind released spec_status effect_records tables fallback resolve_categories target_filters draw_count lp_cost chains stat_mod_sections fusion_role ai_tables tokens search_filters effects_confidence`. Multi-valued cells are space-separated.

## Open questions

- The run-time variant rule per card, needed to pick the right record when a card has several.
- What the generic field and equip fallback handlers (`0x09c74ba4`, `0x09c748a8`) do beyond the stat modifiers.
- Why 47 engine-supported ids have no `cardinfo` record (cut cards, Japanese-only cards).
