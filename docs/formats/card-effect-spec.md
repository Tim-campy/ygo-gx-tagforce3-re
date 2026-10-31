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

- `card_effects.jsonl`: the first line is a header `{"schema": 5, "meta": {...}}`, which records the depth, whether `--boot` and `--draw` were given and the search-filter source. Then one object per card id, sorted by id.
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
| Compare chains | `effect_params.chain_results` + `resolve_chain` (symbolic evaluator, section "Compare chains") | `card id -> value` cases of every chain with at least 8 card-id tests (307 functions: 21 parameter, 72 predicate, 4 mixed, 58 expression, 10 behaviour, 142 unresolved) | `params.chains` |
| `tools/engine_branches.csv` + behaviour chain cases | `card_effects.load_engine_branches`, `generated_branches` | Branches read in the decompilation (amount, condition) and the own code of behaviour chain cases | `engine_branches` |
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

## Object schema (schema 5)

Schema 5 adds the symbolic chain cases and `engine_branches[]`. In `params.chains[]` it adds the optional keys `method`, `values`, `expression`, `reason` and `own`, the kinds `conditional`, `expression` and `behaviour`, and the classes `expression` and `behaviour` (section "Compare chains"). It adds the card-level list `engine_branches[]`, the `engine_branches` key of `sources` and `confidence`, and the CSV column `engine_branches` at the end. It removes or renames nothing, and the status rules are unchanged; a schema-4 reader that ignores unknown keys keeps working. Such a reader only sees new string values in `kind` and `class`. A case that schema 4 had as `constant` keeps its value: the symbolic evaluator returns the same constant wherever the plain evaluator returned one, which is checked on the disc and in the tests.

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
| `params.chains[]` | list | compare chains | `label function kind value confidence class`, plus (schema 5, only when non-empty) `method`, `values[]`, `expression`, `reason`, `own`. `kind`: `constant` (`value` is the integer), `conditional` (`values[]` lists the possible results as text), `expression` (`expression` is the result as text), `computed` (`reason` says why), or `behaviour` (the chain's class is `behaviour`, the return value is not used). `method`: `straight` (the plain evaluator of schema 4 gives the value) or `paths` (only the symbolic evaluator does). `own`: the join state and calls of the case's own code (section "Compare chains"). `class` is the chain class: `parameter`, `predicate`, `mixed`, `expression`, `behaviour` or `unresolved`. The draw chain is reported only as `draw_count` |
| `engine_branches[]` | list | `engine_branches.csv`, behaviour chains | One object per decoded branch of an engine function for this card: `function when effect amount condition confidence basis source` (section "Field: `engine_branches`"). `source` is `read` (a row of `tools/engine_branches.csv`) or `chain` (generated from a compare-chain case) |
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

Every other chain that `effect_params.chain_results` reports gets a label from the registry, whatever its class. If the chain function has a registry name, that name is the label and the confidence is medium (156 chains besides the five above, for example `duel_core_has_piercing`). Otherwise the label is `chain_<address>` and the confidence is low (145 chains). A case that is not a `straight` constant is at most medium.

## Compare chains

A compare chain is a function with at least 8 `li rX, K; beq/beql rY, rX, T` tests where `K` is a card id (`effect_params.chain_cases`). Schema 4 evaluated each taken branch with the plain evaluator `effect_params.evaluate`, which stops at the first value it does not know. Schema 5 resolves every case with `effect_params.resolve_chain`, which uses a symbolic evaluator.

### Why the plain evaluator failed (disc)

The 244 chains that schema 4 classed `unresolved` have 10,325 cases; 347 of them were constants. For the other 9,978 cases, the first instruction where the plain evaluator stopped:

| First stop | Cases | Chains (dominant reason) |
| --- | --- | --- |
| Arithmetic on a value the case did not set (an argument, a saved register, a stack local) | 4,355 | 128 |
| Load through a register (the context, a field slot, an argument structure) | 3,008 | 57 |
| Branch on an unknown value | 1,417 | 28 |
| Call (`jal`) | 591 | 14 |
| Load from a global address (state or a table) | 575 | 16 |
| `v0` never set before `jr ra` | 14 | 1 |
| Indirect call (`jalr`) | 12 | 0 |
| Instruction the decoder does not model (`mult`, `ext`, `seb` ...) | 6 | 0 |

A first stop is not the whole story: past it, most cases also call functions, fork on run-time state, and use `mult`/`mflo`, `ext`/`ins`, `seb`/`seh` or variable shifts (about 3,200 such instructions inside the 244 functions, 176 of them FPU loads and stores).

### The symbolic evaluator

`effect_params.SymbolicEvaluator` runs from the case target (after the branch's delay slot) to `jr ra`:

- **Values.** A register holds an integer or an expression. Expressions are nested tuples: `("arg", n)` (argument `a<n>` at function entry), `("reg", name)` (unknown at the case entry), `("sp", delta)`, `("load", base, offset, size, signed)`, `("call", target, (a0, a1, a2, a3))` and `("op", symbol, a, b)`. `effect_params.render` prints them: `u16[arg0+0x2]`, `duel_core_count_monsters(arg0, 1)`, `(x * 300)`, `(x != 0)`, `!(x < 2)`. An unknown call argument prints as `_`.
- **Entry state** (`chain_entry_state`). The prologue (function start to the first test) is run straight. Registers and stack slots that are not written again in the rest of the function keep that value in every case: for example `s0 = arg0` or `s1 = u16[arg0+0x0]`. The stack pointer is always kept. At the case entry, the tested register and the constant register both hold the case's card id.
- **Card-id binding** (`_id_expression`). The expression that the branch compares with the card id (the stable register, or its last writer just before the branch) is bound to the case's id. A later test of the same expression against another card id is then decided instead of forked.
- **Instructions.** Everything the plain evaluator models, plus `mult`/`multu`/`div`/`divu` with `mfhi`/`mflo`, `sllv`/`srlv`/`srav`, `movz`/`movn`, the Allegrex `min`/`max`, `ext`, `ins`, `seb`, `seh`. FPU loads and stores are ignored, and stores to the stack are modelled. Stores to other memory are not modelled: a load after a store returns the load expression, not the stored value.
- **Branches.** A branch whose condition is known is followed. Otherwise the path forks (at most 16 paths and 400 steps per case).
- **Calls.** A `jal` to a leaf helper of the module (no calls of its own, at most 256 bytes) is evaluated on the argument values. When every path of the helper returns one constant, that constant is the result (inlined). Otherwise `v0` becomes a call expression. The caller-saved registers are clobbered in both cases. `jalr` and `jr` through a register (jump tables) stop the case.

A case's result:

| Kind | Rule |
| --- | --- |
| `constant` | Every path returns the same integer |
| `conditional` | Every path returns a value; the results differ (`values[]`, sorted, integers first) |
| `expression` | Every path returns the same expression, with no leaf unknown at the case entry (call arguments excepted) |
| `computed` | `reason`: `path_limit`, `step_limit`, `jump_table`, `indirect_call`, `unmodelled`, `unknown_input` (the result depends on a register unknown at the entry) or `v0_not_set` |

**Own code (join state).** Addresses that the case bodies of two or more distinct branch targets reach within 48 instructions are *shared*. The case is run again until it reaches a shared address. At that address, the live registers that the case changed are its *join state*, for example `a1=5 at 0x09c43124`: the discard count that `duel_effects_cost_discard` passes to its shared call `duel_core_request_discard_cost`. Only grounded values are kept, and `lui` address halves are dropped. The join states and the calls that the case's own code makes (except inlined calls) form `own` (`effect_params.case_summary`). This is the per-card part of a chain whose return value is the same for every card.

**Return value used** (`returns_value`). A function returns a value when, at some direct call site, `v0` is live after the call: read, or returned by `jr ra` (a liveness walk of 48 instructions over both ways of each branch). A function that has direct callers, none of which uses `v0`, is void. A function without direct callers (one reached only through table pointers) counts as returning a value.

### Chain classes (`effect_params.chain_class`)

| Class | Rule |
| --- | --- |
| `behaviour` | The function is void, and at least half the cases have own code |
| `parameter` | At least half the cases `constant`, with at least two distinct values not all in {0, 1} (schema-4 rule) |
| `predicate` | At least half the cases `constant`, all values in {0, 1} (schema-4 rule) |
| `mixed` | At least half the cases `constant`, otherwise (schema-4 rule) |
| `expression` | Fewer than half `constant`, but at least half resolve to a value (`constant`, `conditional` or `expression`) |
| `unresolved` | Otherwise |

`compare_chains.csv` (from `effect_params.py -o`) also gives `plain_class` (the schema-4 class), the case counts by kind, the failure reasons, `own_code_cases`, `own_varies` and `returns_value`. `chain_results.csv` lists every case.

### Results (disc)

Classes, schema 4 → schema 5: the 63 chains that were already `parameter`, `predicate` or `mixed` keep their class. Of the 244 `unresolved` chains, 1 becomes `parameter`, 30 `predicate`, 3 `mixed`, 58 `expression` and 10 `behaviour`; 142 stay `unresolved`. Every schema-4 constant is unchanged.

The 9,978 cases that were not constants in the 244 chains:

| Result | Cases |
| --- | --- |
| `constant` | 1,006 |
| `conditional` | 1,253 |
| `expression` | 1,333 (a call result 1,060, arithmetic 237, a load 36) |
| `computed`: path limit | 4,515 |
| `computed`: unknown input | 1,265 |
| `computed`: `v0` not set | 265 |
| `computed`: step limit | 249 |
| `computed`: indirect call / jump table | 78 / 14 |

2,751 of the 6,386 cases that stay `computed` still have own code (a join state or a call with its arguments).

The largest remaining class, the path limit, comes from case bodies that loop over the field or the hand with an unknown count (`duel_core_compute_card_stats`, `duel_core_send_field_card_body`, `duel_core_set_slot_negated`). Raising the limits to 64 paths and 1,500 steps made a full run take more than ten times as long, so the limits stay at 16 and 400.

**Precision** (disc, judged against the card texts, read locally and not copied). The sample was 30 random newly resolved values (method `paths`; `constant`, `conditional` or `expression`) of value chains. 14 values say something the text can confirm, and all 14 agree with it:

- Dark Effigy: double Tribute when the Attribute matches DARK.
- Discard counts of 1 for Coelacanth, Gladiator Beast Heraklinos, Curse of Aging, Lightning Vortex and D.D. Crow.
- Type tests: Dragon for Dragon Seeker, Fiend for Infernal Gainer, Thunder plus the named card for Makiu.
- Instant Neo Space names Elemental HERO Neos.
- The banish procedures of Desert Twister and Aztekipede.
- `card_db_is_spell` for Spell Vanishing.
- FIRE Attribute 4 for Flamvell Dragnov.

The other 16 cannot be judged from the text: AI scores, prompt and text ids, 0/1 results of a condition, or helpers called with the card's own id. None contradicts its text.

## Confidence rules

| Field | Rule |
| --- | --- |
| `identity`, `lists`, `target_filter`, `fusion`, `ritual`, `ai`, `tokens`, `fallback_effect` | high: direct table reads with structural checks |
| `effects[].confidence` | low: no slot reaches an `effect` category. Medium: the resolve handler serves more than one card and its per-card split is not high (its categories are the union of the family, see below), or the resolve closure reaches unnamed callees, or there is no resolve handler. High: otherwise |
| `refinement.confidence`, `confidence.family_split` | High: an LP decode whose amounts are all constants, or a closure that reads the card id from the link with no unresolved computed jump (every path that the card id excludes is dropped). Medium: computed LP amounts (taken as non-negative before their sign), or a closure that never reads the card id. `confidence.family_split` is high when every refinement of the card is high |
| `confidence.effects` | The lowest of the card's records |
| `draw_count` | high for a constant, medium for a computed case |
| `params.chains[].confidence` | The label's confidence for a `constant` of method `straight`. Every other case (method `paths`, `conditional`, `expression`, `computed`, `behaviour`) is at most medium: the entry state and the card-id binding are heuristics, although each value is exactly what the evaluator computes from the code |
| `chains` | high if all cases are high, low if all are low, otherwise medium |
| `engine_branches` | From the rows' H/M/L: high if all are H, low if all are L, otherwise medium. Generated rows are always L |
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

Precision (disc, judged against the card texts, read locally and not copied): 25 random cards that moved from `partial` to `full` (engine): every descriptive tag matched the text (25/25), and for 23 of 25 every clause of the text has a tag (the two gaps are a Toon's "destroyed when Toon World leaves" and a Gemini's position lock). 20 random cards that moved from `engine_only`: 19 of 20 have only correct tags (one `destruction_rule` phrase, "changes where battle-destroyed monsters go", is too narrow for a card that destroys its attacker), and every clause was located for all 20. 10 of 10 fallback spells were right (6 ritual spells with their table entry; the 3 equip spells and 1 field spell that are full through an engine-mapped rule). Third round (battle functions): all 41 cards that moved to `full` were judged; 40 had only correct tags and every clause located, one phrase of the stat-function `arg` rows was too narrow (Cyber Blader) and was reworded.

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
| Cards per source | target filter 406, draw count 120, LP cost 103, any chain 2,702 (697 in parameter chains), engine branches 1,809 (24 from read rows, 1,803 from generated rows), engine references 2,960 (medium 2,866, low 94), stat modifiers 543, fusion/ritual role 386, AI tables 1,660, token makers 46 |
| Spec status (`--boot --draw`) | full 2,748, partial 46, engine_only 21, missing 0, vanilla 738, unreleased 60, placeholder 1 (unchanged by schema 5: the new parameter chain and the engine branches belong to cards that already had other data) |
| Chain cases (all 306 labelled chains) | constant 3,123, conditional 1,282, expression 822, behaviour 719, computed 6,488 |
| `full` by basis | records 2,218, fallback 119, engine 411 |
| `partial` by reason | 24 with a live record that reaches no `effect` category, 15 cards with only side data that is not engine-mapped (stat modifiers, lists or parameter chains plus engine tests in unnamed functions or with only L tags), 5 equip/field spells whose fallback has no per-card part, 2 ritual spells without a ritual-table entry |
| `engine_only` by kind | effect 12, trap 4, spell 2, effect fusion 2, Gemini 1 |
| Without `--boot` | full 2,703, partial 62, engine_only 44, 6 `missing` (effect monsters tested only in `BOOT.BIN`, see `card-refs.md`) |
| Previous commit (same flags) | full 2,748, partial 46, engine_only 21: this commit (schema 5, symbolic chain cases, `engine_branches`, 7 functions named) moves no card |
| Two commits back (same flags) | full 2,707, partial 66, engine_only 42: the battle functions read branch by branch, 22 rel_duel_eng and 2 BOOT.BIN functions named, 59 semantic rows added or rewritten, replacing 7 old ones (`effect-helpers-misc.md`, "Third round"); 41 cards moved to `full` (21 from `engine_only`, 20 from `partial`), none moved back |
| Three commits back | full 2,625, partial 95, engine_only 95 (`effect-helpers-misc.md`, "Second round") |
| Before the engine-mapped rule (same flags) | full 2,288, partial 254, engine_only 273 |

Run `--check` for the current status counts; they move as helpers are named.

## Known gaps

- **Family handlers.** Handlers are shared by card families: Pot of Greed's resolve handler serves 73 cards, and a handler can branch on the card id. Categories are static reach, so a shared handler reports the union of its family's categories in `categories` (`effect-classification.md`, "Limits"). `categories_refined` gives the card's own share where `tools/family_split.py` can isolate it (resolve slot only; 96 % label precision on a judged sample of family records, against 83 % for `categories`). Unions remain where the branch depends on run-time state: state carried between the steps of a handler (every fusion spell keeps `banish`, which applies only under a field effect), targets and choices, and data-driven handlers that never test the id. Those records stay at medium confidence. `shared_by_cards` shows how wide the family is.
- **Data-driven searches.** The builders of list `0x09dec554` select deck cards through a filter word that is not yet decoded. Until `tools/search_filters.py` exists, searches such as Reinforcement of the Army show only `move_list_card` plus the list membership in `lists`.
- **Engine-only and engine-mapped cards.** Both are located, not decoded: `engine_refs` names the functions that test the id, and the semantic tags of `tools/engine_ref_semantics.csv` say which rule each function implements. The 411 engine-mapped cards have every test in a named, tagged function; the 21 remaining `engine_only` cards have a test in an unnamed function without a rule or only L tags (the L-only ones sit in `duel_core_summon_step_flip`, `duel_effects_can_target_slot`, `duel_effects_can_destroy_slot`, `duel_core_draw_cards_ex`, `duel_effects_get_lp_cost`, the Ritual helpers and `duel_core_can_banish*`; the unnamed blockers left are listed in `effect-helpers-misc.md`, "Open questions", several of them presentation code in rel_duel_draw). The conditional branch that the test selects is decoded where `tools/engine_branches.csv` lists it, and its own code is given where a behaviour chain case generates an `engine_branches` row (next section).
- **Stat-modifier arithmetic.** Cards located in `duel_core_compute_card_stats` by the `stat_modifier` tag (69 of the engine-mapped cards), but `params.stat_mods[].values` holds the constant only when the case body is a straight constant; amounts that scale with a count (per card in hand, per Dragon in the Graveyard) are not decoded.
- **Unresolved chains.** 142 of the 307 compare chains are still `unresolved` (244 with the schema-4 evaluator); 6,488 cases stay `computed`, mostly through the path limit of case bodies that loop over the field or the hand (section "Compare chains"). Their cases are joined with `value` null and a `reason`; `own` still gives the case's join state and calls where it has them. `expression` values name helpers, and many of those are still unnamed (`fn_<address>`): naming them makes the expressions readable without rerunning anything.
- **Unnamed helpers.** Completeness depends on names in `re/functions.csv`. The `full` share rises as the naming worklist of `effect-classification.md` is worked off.
- **Variant selection.** `variant` is the position of the record. The rule that picks a variant at run time (`duel_effects_select_record_variant`) is not part of the spec.
- **AI semantics.** `ai[]` gives membership and handler names only. The handlers' conditions are not decoded.
- **Stat-modifier constants** come from a fall-through scan of the case body and can miss values computed elsewhere.

### Engine reference semantics

Each `engine_refs` group carries a `semantics` list (`{tag, phrase, modality, confidence, label}`, one per distinct rule of `tools/engine_ref_semantics.csv` matched by its references), and a card with at least one tagged reference gets a card-level `engine_semantics` list from `card_refs.describe()` (descriptive tags first; `generic` marks `ai_hint`, `archetype`, `name_alias`, `named_reference` and `unclassified`). See `card-refs.md`, "Semantics", for coverage and precision.

### Field: `engine_branches` (schema 5)

What a card's own branch inside an engine function does (the amount, the condition) is kept in `tools/engine_branches.csv` (branches read in the decompilation) and joined into the spec by `card_effects.load_engine_branches` (`--branches` selects another file). Each row whose `card_id` is the card becomes one object of `engine_branches[]` with `source: "read"`:

| Field | Type | Meaning |
| --- | --- | --- |
| `engine_branches[].function` | hex string | The engine function whose branch was read (`0x09dc5a4c`) |
| `engine_branches[].when` | string | Timing of the branch: `battle`, `attack_declared`, `damage_calculation`, `battle_damage`, `after_damage_calculation`, `destroyed_by_battle`, `rule_check`, `continuous`, `activation`, `sent_to_graveyard`, `card_moved`, `state_reset` |
| `engine_branches[].effect` | string | What it does: `battle_damage_multiply`, `battle_damage_set`, `battle_damage_redirect`, `battle_damage_to_effect_damage`, `negate_destroyed_effects`, `negate_battle_opponent`, `spell_trap_lock`, `destroy_after_turns`, `destroy_self`, `add_counter`, `attribute_becomes`, `target_side`, `player_marker`, ... |
| `engine_branches[].amount` | string | The decoded amount or value: `x2`, `1000`, `0`, `5` (turns), `DARK`, `opponent`, `flip only`; empty when the branch has none |
| `engine_branches[].condition` | string | The condition the branch tests, in engine terms (Type and Attribute numbers, marker kinds) |
| `engine_branches[].confidence`, `.basis` | | H/M/L and where the reading is recorded (`battle.md`, a function name) |

| `engine_branches[].source` | string | `read` (a row of the file) or `chain` (generated, below) |

Rules: a row is added only for a branch that was read in the decompilation; it describes the engine's behaviour in its own terms and never copies card text. The file is knowledge, small and committed. `--check` reports a missing column, an id or function that is not hex, a confidence that is not H/M/L, an empty `effect`, and ids without a `cardinfo` record. Rows never add ids to the output. On this commit the file has 27 rows: the battle branches of this round (doubling, fixed 1000, redirection, Flip-only negation, the Spell/Trap lock of the Ancient Gear monsters, the 5-turn countdown) and the decoded branches of cards that stay `partial` or `engine_only` (Advanced Dark, Rainbow Veil, Makyura the Destructor, Elemental Hero Necroshade, Goblin Attack Force, Greed Quasar, Paralyzing Potion; L where the function is still unnamed).

**Generated rows** (`card_effects.generated_branches`, `source: "chain"`). Some compare chains carry their per-card part in their own code rather than in the return value. These are every case with own code of a `behaviour` chain, and of an `unresolved` chain whose cases' own code differs between cards (`own_varies`). Each such case becomes one row:

- `function`: the chain;
- `when`: empty, because the chain's timing is not decoded;
- `effect`: `chain_case:<label>`;
- `amount`: the case's `own` text (join state and calls, for example `a1=124 at 0x09cc0bac` for the prompt text id that `duel_effects_get_target_prompt_text` passes on, or `calls duel_core_is_field_spell(4340)`);
- `confidence`: L;
- `basis`: the case target.

Rows for cards of a kind without effect text (normal, plain fusion/ritual/synchro, token) are dropped, because there the case is another card's reference to the id.

On the disc there are 3,483 generated rows (2,825 from 124 `unresolved` chains with varying own code, 658 from the 10 `behaviour` chains) for 1,803 cards: full 1,731, partial 25, engine_only 8, unreleased 39. Precision (20 random rows judged against the card texts, locally): 6 rows name what the text needs, and all 6 match:

- Armoroid Gaidengo: `card_db_is_roid`;
- Comrade Swordsman of Landstar: Warrior, Type 15;
- Sea Koala: another Beast, Type 11;
- Spirit Ryu: a Dragon in the hand;
- The Legendary Fisherman: Umi;
- Knight's Title: the two named cards.

13 are opaque (prompt text ids, flags such as `s1=1`, helpers without names), and none contradicts its text. One was another card's reference on a Normal Monster; that is why the rows of cards without effect text are now dropped. The rows locate the per-card data; they do not say what the shared tail does with it.

## CSV summary columns

`card_id name kind released spec_status effect_records tables fallback resolve_categories target_filters draw_count lp_cost chains stat_mod_sections fusion_role ai_tables tokens search_filters effects_confidence engine_ref_functions engine_ref_groups resolve_categories_refined spec_basis engine_branches`. Multi-valued cells are space-separated. `resolve_categories_refined` (schema 3) is the union over the card's records of `categories_refined`, or of `categories` where a record has no refinement. `engine_ref_functions` is the number of functions in `engine_refs`; `engine_ref_groups` lists their registry groups (`unnamed` for default names). `spec_basis` (schema 4) is empty unless the card is `full`. `engine_branches` (schema 5) is the number of objects in `engine_branches[]`.

## Open questions

- The run-time variant rule per card, needed to pick the right record when a card has several.
- What the generic field and equip fallback handlers (`0x09c74ba4`, `0x09c748a8`) do beyond the stat modifiers.
- Why 47 engine-supported ids have no `cardinfo` record (cut cards, Japanese-only cards).
- For each `engine_only` card, what the branch selected by its id does beyond the function's rule (the semantic tags of `card-refs.md` say which rule; the conditional branches are decoded only in `engine_branches`).
- The meaning of the per-card values of the `expression` and `unresolved` chains whose cases call unnamed AI helpers (`0x09ce536c`, `0x09d3ba48`, `0x09d8fb44`), and of the generated `engine_branches` rows: they give the register or call the case sets, not what the shared tail does with it.
- The 4,559 `path_limit` cases: a loop-aware evaluator (summarising a loop over field slots instead of forking on each iteration) would resolve most of them.
