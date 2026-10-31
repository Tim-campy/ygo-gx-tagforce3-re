# Per-card effect specification (`tools/card_effects.py`)

The per-card effect specification is the artifact a future port consumes: one JSON object per card id that joins everything the extractors know about that card's effect. It is generated from the maintainer's own files at run time. The repository keeps only the tool and this schema; the generated files are game data and stay in `extracted/`.

```
python3 -I tools/card_effects.py <USRDIR>/gmodule/rel_duel_eng.prx <USRDIR>/duelsys/cardinfo_eng.ehp \
        --boot <SYSDIR>/BOOT.BIN [--draw <USRDIR>/gmodule/rel_duel_draw.prx] -o extracted/card_effects \
        [--functions re/functions.csv] [--depth 3] [--search-filters <csv>]
python3 -I tools/card_effects.py <prx> <cardinfo> --boot <BOOT.BIN> [--draw <rel_duel_draw.prx>] --check
python3 -I tools/tests/test_card_effects.py
```

The tool imports the other extractors with `importlib` from `tools/` and copies none of their code. Each source keeps its own checks: `effect_params.check`, `stat_mods.check`, `fusion.check` (with the card database), `effect_classify.check` (which includes `ai_tables.check`), plus a check of the token table defined here. A problem from any of them makes `--check` fail. A full run takes about 30 s with `--boot` and `--draw`. Most of that time goes to the engine-reference scan and the evaluation of every compare chain.

Outputs:

- `card_effects.jsonl`: the first line is a header `{"schema": 3, "meta": {...}}`, which records the depth, whether `--boot` and `--draw` were given and the search-filter source. Then one object per card id, sorted by id.
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
| Compare chains | `effect_params.compare_chains` + `analyse_chain` | `card id -> value` cases of every chain with at least 8 card-id tests (306 functions: 19 parameter, 42 predicate, 1 mixed, 244 unresolved) | `params.chains` |
| Card ids tested in code | `tools/card_refs.py` (`card-refs.md`) | `eq`/`switch`/`range`/`arg`/... references in `rel_duel_eng`, and in `BOOT.BIN` and `rel_duel_draw` with `--boot`/`--draw`, grouped by function | `engine_refs` |
| ATK/DEF stat functions | `stat_mods.stat_uses` | Where the card's ATK/DEF modifier sits (section, constants, helper) | `params.stat_mods` |
| Fusion recipe table, hard-coded fusions, ritual table | `tools/fusion.py` | Recipes, materials, `material_of`, ritual pairs | `fusion` |
| AI priority tables and u16 lists | `tools/ai_tables.py` | Membership (table, index, handler and its name) | `ai` |
| Token table `0x09e019ec` | parsed in `card_effects.py` | Token id, count, position | `tokens`, `token_of` |
| Fallback records S/T 0-2 (placeholder id `0x0e74`) | `card_effects.py` | The generic record a spell without its own record uses | `fallback_effect` |
| Search filters of `0x09dec554` | `tools/search_filters.py` (optional) | Whatever per-card filter the tool decodes | `params.search_filters` |
| Per-card branches of shared resolve handlers, LP chain | `tools/family_split.py` (`effect-classification.md`, "Per-card split of family handlers") | The categories that the card's own branch of a family handler reaches, and the signed LP amounts of `duel_effects_get_lp_change_amounts` | `effects[].slots.resolve.categories_refined`, `.refinement` |

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

## Object schema (schema 4)

Schema 4 adds `effects[].inert` (a record whose every slot is a return-0 stub, section "Inert records"), the card-level `spec_basis` (`records`, `fallback` or `engine` for a `full` card), the CSV column `spec_basis` at the end, and the engine-mapped `full` rule (section "Engine-mapped cards"). It removes or renames nothing; a schema-3 reader keeps working.

Schema 3 adds `slots.resolve.categories_refined` and `slots.resolve.refinement` to schema 2 (records whose resolve handler `tools/family_split.py` examines), the `family_split` key of `sources` and `confidence`, and the CSV column `resolve_categories_refined` at the end. `slots.*.categories` is unchanged: it stays the static reach of the handler. Schema 2 added fields to schema 1 and removed or renamed none:

- `engine_refs`;
- `params.chains[].class`;
- chains that are not parameter chains;
- the status `engine_only`.

A schema-1 or schema-2 reader that ignores unknown keys keeps working. A schema-1 reader only needs to accept the new status value. A reader that wants the per-card categories uses `categories_refined` when present and `categories` otherwise.

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
| `slots.resolve.categories_refined` | list | `family_split` | The `categories` that the card's own branch reaches (schema 3). A subset of `categories`, except that the LP decode may add `damage` or `gain_lp` that the depth limit hid. Present only for records whose resolve handler is shared by several cards with at least two categories, or reaches `duel_effects_resolve_lp_change` |
| `slots.resolve.refinement` | object | `family_split` | `method` (`branch`: the card id selected the paths; `lp_chain`: the LP amounts were decoded; `unchanged`: the closure does not read the card id through the link; `reveal`: only the temporary face-up pair was dropped), `confidence` (high/medium), `removed[]`, `added[]`, and `lp_amounts[]` for LP records: `side:amount` with side `self`, `opponent`, `player0`, `player1` or `either`, and amount `-800`, `+1000`, `-`/`+` (computed, sign known) or `?` (sign unknown) |
| `slots.*.filter_calls[]` | list | `effect_params` | Constant flag words passed to `duel_effects_target_filter` inside this handler (heuristic function bounds) |
| `effects[].commands` | list | `effect_classify` | Engine command codes reached from the resolve slot |
| `effects[].unnamed_resolve_callees`, `.unnamed_callees` | int | `effect_classify` | Unnamed functions reached (resolve slot only; any slot) |
| `effects[].target_filter` | object | `effect_params` | `flags form side zone face position actions[]` of the slot `+08` stub |
| `effects[].confidence` | high/medium/low | rule below | |
| `fallback_effect` | object | placeholder records | Present only for spells without a record |
| `lists[]` | list | L1/L4 | `list index handler name shared_by_cards` |
| `params.draw_count` | object | draw chain | `kind` constant/computed, `value`, `summary` (what a computed case reads), `confidence` |
| `params.chains[]` | list | compare chains | `label function kind value confidence class`. `class` is the `effect_params` class of the chain: `parameter`, `predicate` (every case returns 0 or 1), `mixed` or `unresolved` (fewer than half the cases evaluate to a constant). The draw chain is reported only as `draw_count` |
| `engine_refs[]` | list | `card_refs` | One object per function that references the id: `module function function_name group named kinds{kind: count} references[] callees[] values[] operands[]`. Named functions come first. The registry name is the coarse meaning, for example `duel_core_has_piercing`. `callees` are the helpers that receive the id (`arg`), `values` the constants returned at the compare targets, `operands` where the compared value comes from. Only ids that another source already knows get the field; engine references never add ids |
| `params.stat_mods[]` | list | `stat_mods` | `section function_name use address values helper calls` |
| `params.search_filters[]` | list | optional | As delivered by the search-filter source |
| `fusion.recipes[]` | list | `fusion` | `source` (`table` or `code`), `index`, `materials[]` = `{code, generic, name or description}` |
| `fusion.material_of[]` | list | `fusion` | Fusions whose recipe names this id |
| `fusion.ritual_monster[]`, `fusion.ritual_spell[]` | list | `fusion` | `index`, the partner id, `level_total` |
| `ai[]` | list | `ai_tables` | `table name index handler handler_name` |
| `tokens[]` | list | token table | `index token_id token_name count count_computed position` |
| `token_of[]` | list | token table | For a token card: the cards that create it |
| `effects[].inert` | bool | effect tables | Present (true) only for an inert record: every slot handler is exactly `jr ra; move v0, zero` |
| `spec_status` | string | rule below | |
| `spec_basis` | string | rule below | For a `full` card only: `records` (its live records are complete), `fallback` (a complete icon fallback plus the per-card part) or `engine` (engine-mapped) |
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

Every other chain that `effect_params.compare_chains` reports gets a label from the registry. This covers parameter, predicate, mixed and unresolved chains. If the chain function has a registry name, that name is the label and the confidence is medium (105 chains, for example `duel_core_has_piercing`). Otherwise the label is `chain_<address>` and the confidence is low (197 chains). A computed case (`value` null) is at most medium.

## Confidence rules

| Field | Rule |
| --- | --- |
| `identity`, `lists`, `target_filter`, `fusion`, `ritual`, `ai`, `tokens`, `fallback_effect` | high: direct table reads with structural checks |
| `effects[].confidence` | low: no slot reaches an `effect` category. Medium: the resolve handler serves more than one card and its per-card split is not high (its categories are the union of the family, see below), or the resolve closure reaches unnamed callees, or there is no resolve handler. High: otherwise |
| `refinement.confidence`, `confidence.family_split` | High: an LP decode whose amounts are all constants, or a closure that reads the card id from the link with no unresolved computed jump (every path that the card id excludes is dropped). Medium: computed LP amounts (taken as non-negative before their sign), or a closure that never reads the card id. `confidence.family_split` is high when every refinement of the card is high |
| `confidence.effects` | The lowest of the card's records |
| `draw_count` | high for a constant, medium for a computed case |
| `chains` | high if all cases are high, low if all are low, otherwise medium |
| `stat_mods`, `filter_calls`, `search_filters` | medium: the section is exact, but the constants of a case body are a heuristic (`stat-modifiers.md`); filter calls rely on heuristic function bounds |
| `engine_refs` | medium: an `eq`/`switch` reference with a card-id-shaped operand (u16 load, `0x3fff` mask, call result, argument), or a `switch`/`arg` reference. Low: otherwise (only bounds, ranges, stores, or operands that could not be traced). Precision of the scan in `card-refs.md` |

## Spec status

| Status | Rule |
| --- | --- |
| `full` | Basis `records`: at least one live (not inert) effect record, and every live record reaches an `effect` category in some slot with no unnamed callee in its resolve closure. Basis `fallback`: a spell served by a complete fallback record whose per-card part is known: a ritual-table entry for ritual spells; stat modifiers, or an engine-mapped card, for equip and field spells. Basis `engine`: no live record, and the card is engine-mapped (below). |
| `partial` | Live effect records that are not all complete, or only side data (lists, parameter chains, stat mods, tokens, a fallback record, inert records) that is not engine-mapped. |
| `engine_only` | An effect-bearing kind with no effect record, no fallback and no side data, whose id the engine tests directly (an `eq`, `switch` or `arg` reference in `engine_refs`, or a case in a non-parameter compare chain), and that is not engine-mapped. The behaviour lives in the shared engine function(s) named in `engine_refs`; the spec gives where, not what. |
| `missing` | An effect-bearing kind with no data from any source, and no `eq`/`switch`/`arg` engine reference. |
| `vanilla` | A kind without effect text (normal, plain fusion/ritual/synchro, normal tuner, token) and no own effect record. Recipes and AI entries are still listed. |
| `unreleased` | The engine knows the id but `cardinfo` has no record. |
| `placeholder` | The fallback id `0x0e74`. |

`full` does not mean the effect is reverse engineered: it means every record maps onto named helpers, or every engine test of the card maps onto a named rule. Behaviour inside a shared family handler still depends on the card id (next section), and an engine-mapped card's branch arithmetic is not decoded.

### Inert records

`duel_effects_cond_never` (`0x09ce28dc`) and `duel_effects_resolve_noop` (`0x09c7eb14`) are both exactly `jr ra; move v0, zero`. A record whose every slot is such a stub can never be activated through the chain (a condition that is never true) or resolves to nothing; the card's behaviour is triggered by engine code that tests its id (Royal Decree, Imperial Order, The Emperor's Holiday, the Spirit Message and Sarcophagus cards, the "when this face-down card is destroyed" traps). The tool detects the stub from the two instruction words, not from the name (H). Inert records are kept in `effects[]` with `inert: true` but do not count as live records: a card whose only records are inert is judged like a card without records. On the disc 17 cards carry an inert record, 9 of them no live record.

### Engine-mapped cards

A card without a live record can still be fully located when everything the engine does with its id lies in named functions whose rule is known. `card_effects.engine_mapped` requires all of:

1. The card's own strong engine references (`eq`/`switch`/`arg`) are grouped by function, ignoring AI functions (registry group `ai`) and groups whose every semantic tag only locates the card (`ai_hint`, `archetype`, `name_alias`, `named_reference`, `save_record`). At least one group remains.
2. Every remaining group is in a named function and carries at least one descriptive semantic tag (`card-refs.md`, "Semantics"; `unclassified` and the generic tags do not count).
3. At least one descriptive tag of the card has confidence H or M.
4. Every stat-modifier function (`params.stat_mods`) and every L1/L4 list handler is named.

This is the engine-side counterpart of the record rule: a full record maps onto named helpers with categories; an engine-mapped card maps onto named rule functions with tags. It says where the behaviour is and which rule it belongs to (`stat_modifier`, `piercing`, `summon_condition`, `negation` ...), not the arithmetic of the card's branch (the `+300 per card in hand` of a stat case is in `params.stat_mods[].values` only when the case body is a constant).

Precision (disc, judged against the card texts, read locally and not copied): 25 random cards that moved from `partial` to `full` (engine): every descriptive tag matched the text (25/25), and for 23 of 25 every clause of the text has a tag (the two gaps are a Toon's "destroyed when Toon World leaves" and a Gemini's position lock). 20 random cards that moved from `engine_only`: 19 of 20 have only correct tags (one `destruction_rule` phrase, "changes where battle-destroyed monsters go", is too narrow for a card that destroys its attacker), and every clause was located for all 20. 10 of 10 fallback spells were right (6 ritual spells with their table entry; the 3 equip spells and 1 field spell that are full through an engine-mapped rule).

## Figures (disc, registry of this commit, depth 3, `--boot`)

| Measure | Value |
| --- | --- |
| Effect records | 2,600. 2,544 join a `cardinfo` record, 3 carry the placeholder `0x0e74`, 53 belong to 47 unreleased ids |
| Unreleased ids | 47 with effect records. All 18 unreleased ids of the AI tables (`ai-tables.md`) are among them; 29 occur only in the effect tables. 5 more (`0x142d`, `0x1f08`, `0x1f0f`, `0x1f35`, `0x1f37`) appear only in lists, chains, fusion or AI data |
| Output | 3,614 ids for 3,553 `cardinfo` cards (8 more unreleased ids than schema 1, from the cases of non-parameter chains) |
| Released cards with own effect records | 2,251, of which 2,227 are `full` (98.9 %; some of these have only inert records and are `full` by the engine rule) |
| Fallback spells | 126, 113 `full`: 28 ritual spells with a ritual-table entry (the ritual record S/T 2 is complete since its six callees were named) and 85 equip and field spells with stat modifiers or engine-mapped (previous commit: 82) |
| Effect record confidence | high 1,289, medium 1,269, low 42 (before the family split, same registry: high 604, medium 1,954, low 42) |
| Family split | 915 resolve slots examined, 394 refined (425 labels removed); split confidence high 689, medium 226 |
| Cards per source | target filter 406, draw count 120, LP cost 103, any chain 2,702 (681 in parameter chains), engine references 2,960 (medium 2,866, low 94), stat modifiers 543, fusion/ritual role 386, AI tables 1,660, token makers 46 |
| Spec status (`--boot --draw`) | full 2,707, partial 66, engine_only 42, missing 0, vanilla 738, unreleased 60, placeholder 1 |
| `full` by basis | records 2,218, fallback 113, engine 376 |
| `partial` by reason | 29 cards with only side data that is not engine-mapped (stat modifiers or parameter chains plus engine tests in unnamed functions or with only L tags), 24 with a live record that reaches no `effect` category, 11 equip/field spells whose fallback has no per-card part, 2 ritual spells without a ritual-table entry |
| `engine_only` by kind | effect 27, spell 5, trap 4, effect fusion 3, Gemini 3 |
| Without `--boot` | full 2,703, partial 62, engine_only 44, 6 `missing` (effect monsters tested only in `BOOT.BIN`, see `card-refs.md`) |
| Previous commit (same flags) | full 2,625, partial 95, engine_only 95: 50 rel_duel_eng functions named since (`effect-helpers-misc.md`, "Second round"), 82 cards moved to `full` (53 from `engine_only`, 29 from `partial`), none moved back |
| Before the engine-mapped rule (same flags) | full 2,288, partial 254, engine_only 273 |

Run `--check` for the current status counts; they move as helpers are named.

## Known gaps

- **Family handlers.** Handlers are shared by card families: Pot of Greed's resolve handler serves 73 cards, and a handler can branch on the card id. Categories are static reach, so a shared handler reports the union of its family's categories in `categories` (`effect-classification.md`, "Limits"). `categories_refined` gives the card's own share where `tools/family_split.py` can isolate it (resolve slot only; 96 % label precision on a judged sample of family records, against 83 % for `categories`). Unions remain where the branch depends on run-time state: state carried between the steps of a handler (every fusion spell keeps `banish`, which applies only under a field effect), targets and choices, and data-driven handlers that never test the id. Those records stay at medium confidence. `shared_by_cards` shows how wide the family is.
- **Data-driven searches.** The builders of list `0x09dec554` select deck cards through a filter word that is not yet decoded. Until `tools/search_filters.py` exists, searches such as Reinforcement of the Army show only `move_list_card` plus the list membership in `lists`.
- **Engine-only and engine-mapped cards.** Both are located, not decoded: `engine_refs` names the functions that test the id, and the semantic tags of `tools/engine_ref_semantics.csv` say which rule each function implements. The 376 engine-mapped cards have every test in a named, tagged function; the 42 remaining `engine_only` cards have a test in an unnamed function without a rule or only L tags (24 of the blocked cards carry only L descriptive tags, in `duel_core_battle_resolve`, the `duel_core_battle_step_*` functions and `duel_core_get_battle_flip_trigger`; the unnamed blockers left each hold one or two cards, for example `0x09bf5b40`, `0x09ce2230`, `0x09c11ea0`/`0x09c139e0`, `0x09ddef8c`). The conditional branch that the test selects inside the function is still not decoded for either.
- **Stat-modifier arithmetic.** Cards located in `duel_core_compute_card_stats` by the `stat_modifier` tag (69 of the engine-mapped cards), but `params.stat_mods[].values` holds the constant only when the case body is a straight constant; amounts that scale with a count (per card in hand, per Dragon in the Graveyard) are not decoded.
- **Unresolved chains.** 244 of the 306 compare chains have fewer than half of their cases evaluating to a constant. Their cases are joined with `value` null, labelled from the registry when the function is named.
- **Unnamed helpers.** Completeness depends on names in `re/functions.csv`. The `full` share rises as the naming worklist of `effect-classification.md` is worked off.
- **Variant selection.** `variant` is the position of the record. The rule that picks a variant at run time (`duel_effects_select_record_variant`) is not part of the spec.
- **AI semantics.** `ai[]` gives membership and handler names only. The handlers' conditions are not decoded.
- **Stat-modifier constants** come from a fall-through scan of the case body and can miss values computed elsewhere.

### Engine reference semantics

Each `engine_refs` group carries a `semantics` list (`{tag, phrase, modality, confidence, label}`, one per distinct rule of `tools/engine_ref_semantics.csv` matched by its references), and a card with at least one tagged reference gets a card-level `engine_semantics` list from `card_refs.describe()` (descriptive tags first; `generic` marks `ai_hint`, `archetype`, `name_alias`, `named_reference` and `unclassified`). See `card-refs.md`, "Semantics", for coverage and precision.

## CSV summary columns

`card_id name kind released spec_status effect_records tables fallback resolve_categories target_filters draw_count lp_cost chains stat_mod_sections fusion_role ai_tables tokens search_filters effects_confidence engine_ref_functions engine_ref_groups resolve_categories_refined spec_basis`. Multi-valued cells are space-separated. `resolve_categories_refined` (schema 3) is the union over the card's records of `categories_refined`, or of `categories` where a record has no refinement. `engine_ref_functions` is the number of functions in `engine_refs`; `engine_ref_groups` lists their registry groups (`unnamed` for default names). `spec_basis` (schema 4) is empty unless the card is `full`.

## Open questions

- The run-time variant rule per card, needed to pick the right record when a card has several.
- What the generic field and equip fallback handlers (`0x09c74ba4`, `0x09c748a8`) do beyond the stat modifiers.
- Why 47 engine-supported ids have no `cardinfo` record (cut cards, Japanese-only cards).
- For each `engine_only` card, what the branch selected by its id does beyond the function's rule (the semantic tags of `card-refs.md` say which rule; the conditional branches are not decoded).
