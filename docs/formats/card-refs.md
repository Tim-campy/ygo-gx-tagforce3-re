# Card ids tested in engine code (`tools/card_refs.py`)

Not every card effect goes through the effect tables (`effect-tables.md`). On the disc, 273 released effect cards have no effect-table record, no list entry and no parameter: Goddess with the Third Eye, Marshmallon and Summon Priest are examples. The engine implements these cards by testing their id inside shared code:

- compare chains (`if (id == A || id == B ...)`);
- `switch (id)` jump tables and range tests;
- calls to helpers that take a card id, such as "count the copies of card K in the Graveyard".

`tools/card_refs.py` finds those tests. It scans every function of the module for card-id immediates and records the ones that the code uses as card ids. `tools/card_effects.py` joins the result as `engine_refs` (see `card-effect-spec.md`).

```
python3 -I tools/card_refs.py <USRDIR>/gmodule/rel_duel_eng.prx list -o extracted/card_refs \
        [--cardinfo <USRDIR>/duelsys/cardinfo_eng.ehp] [--boot <SYSDIR>/BOOT.BIN] \
        [--draw <USRDIR>/gmodule/rel_duel_draw.prx] [--functions re/functions.csv]
python3 -I tools/card_refs.py <prx> --check [--cardinfo ...] [--boot ...] [--draw ...] \
        [--spec extracted/card_effects/card_effects.csv] [--semantics tools/engine_ref_semantics.csv]
python3 -I tools/card_refs.py <prx> describe [--card 0x1416 ...] [-o extracted/card_refs] [--cardinfo ...] \
        [--boot ...] [--draw ...] [--spec extracted/card_effects/card_effects.csv]
python3 -I tools/tests/test_card_refs.py
```

Library: `card_refs(prx_bytes, functions=None, names=None, base=0x09be1400, module="rel_duel_eng", cards=None, semantics=None)` returns `{card id: [reference dict]}`, and `all_refs(prx, functions, names, boot=None, draw=None, semantics=None)` merges the three modules. `describe(refs, card_id)` returns the semantic summary of one card (section "Semantics"). Pure Python, about 2 s for `rel_duel_eng` alone and 9 s with `BOOT.BIN` and `rel_duel_draw`. Ghidra is not needed.

## Modules and function bounds

| Module | Base | `.text` |
| --- | --- | --- |
| `rel_duel_eng.prx` | `0x09be1400` | `0x09be1400`–`0x09de415c` |
| `BOOT.BIN` | `0x08804000` | `0x08804000`–`0x0887234c` |
| `rel_duel_draw.prx` | `0x0983fb00` | `0x0983fb00`–`0x098b98a4` |

The `.text` bounds come from the section headers. Section addresses are module offsets, as in every PRX of the disc. Without section headers the tool uses the first `PT_LOAD` segment.

Function bounds and names come from the bare-hex ids of `re/functions.csv` that fall inside the module's `.text`, the same way `effect_classify.Registry` gets them. If fewer than two ids fall inside, the tool uses heuristic entry points instead: `jal` targets, and prologues after `jr ra`. The registry group of a reference is the prefix of the function name (`duel_core`, `duel_effects`, `card_db`, `ai`, ...). It is empty for a default `FUN_…` name.

## Heuristic

Card ids are 14-bit values. The scan uses the id range of `effect_params` (`FIRST_CARD`–`LAST_CARD`, `0x0e88`–`0x1f39`). An immediate in that range becomes a reference only when one of these patterns uses it:

| Kind | Pattern | Ids recorded |
| --- | --- | --- |
| `eq` | `li rX, K` (`addiu`/`ori` from `zero`) whose first reader is `beq`/`bne`/`beql`/`bnel`, `xor` or `subu`; or `xori rY, rX, K` | K |
| `switch` | `addiu rY, rX, -K; sltiu rZ, rY, N; beq rZ, zero, default; ... lw; jr` with a jump table of N module offsets | Each id of `[K, K+N)` whose case target is not the default |
| `range` | The same `addiu -K; sltiu N` (N ≤ 128) without a jump table | Every id of `[K, K+N)` |
| `lt` | `li rX, K` read by `slt`/`sltu` | K (one bound) |
| `bound` | `slti`/`sltiu rY, rX, K` | K (one bound) |
| `arg` | `li a0`–`t3, K` before a `jal`/`j`, or in the delay slot of a `jal` | K; `detail` holds the callee name |
| `store` | `li rX, K` stored with `sb`/`sh`/`sw` | K (an id written into a duel structure) |
| `return` | `li v0, K` that reaches `jr ra` | K |

The scan looks for the first reader on the straight line after the `li`, up to 24 instructions. Rules for the scan:

- It follows one unconditional branch and one `move`.
- It stops when the register is overwritten, and at a call that clobbers it.
- An `li` in a branch delay slot is followed on the taken path first, as the compiler's `beql …; li a0, K` idiom requires.

An immediate with any other first reader is dropped, for example arithmetic, a multiplication or no reader at all.

Each reference also carries these fields:

| Field | Content |
| --- | --- |
| `operand` | For `eq`, `range` and `switch`, where the compared value comes from. The scan traces it back on the straight line to the function start (2,048 instructions at most): `u16 load`, `masked id` (`andi 0x3fff`), `result of <callee>`, `argument` (an argument register that is never written), `word load`, `computed`, `clobbered`, ... |
| `value` | The constant that the *matched* path returns, evaluated with `effect_params.evaluate` (see "Matched path"). For `switch`, the value its case returns. |
| `calls` | Up to 3 named callees on the straight line of the matched path (or the `switch` case): what the case does when it does not just return a constant. |
| `constants` | Up to 6 small non-card immediates near the reference. |
| `semantics` | For `eq`, `switch` and `arg`: the rule of `tools/engine_ref_semantics.csv` that applies (section "Semantics"), else `None`. |

### Matched path

The matched path is where the code goes when the compare says "the id is K":

| Reader | Matched path |
| --- | --- |
| `beq`/`beql` | The branch target, after the delay slot |
| `bne` | The fall-through after the delay slot |
| `bnel` | The fall-through; the delay slot is annulled |
| `xor`/`subu`/`xori` | The first `beq`/`bne` of the result against `zero` within 4 instructions, read as above (`beq` → target, `bne` → fall-through) |

`value` is the constant in `v0` when the path reaches `jr ra` on straight-line, register-only code (a load, a call or an undecidable branch gives `None`). `calls` walks the same path for 16 instructions, follows one unconditional jump, and stops at a conditional branch or `jr`. On `rel_duel_eng` (registry of this commit), 2,543 of 16,012 `eq` references get a value (2,518 through `beq`, 25 through the new `bne` rule; no `xor` compare ends in a constant), and 5,821 get at least one callee.

`eq` references are a superset of the `li; beq` cases of `effect_params.chain_cases`.

`switch`, `eq` and `arg` name one card. `card_effects.py` counts only these three kinds (`STRONG`). `range`, `lt`, `bound`, `store` and `return` are listed but do not explain a card on their own.

## Precision and recall (disc, registry of this commit)

| Measure | Value |
| --- | --- |
| References, all three modules | 22,158 to 2,971 ids in 1,716 functions: `eq` 18,013, `arg` 3,717, `store` 238, `return` 61, `range` 54, `bound` 50, `switch` 21, `lt` 4 |
| References per module | `rel_duel_eng` 19,961, `BOOT.BIN` 2,119, `rel_duel_draw` 78 |
| Released cards referenced | 2,901 of 3,553. Of the other 70 ids, 59 are unreleased ids that other sources also know (46 have effect records). Eleven occur only here: `0x0f00`, `0x0fa0`, `0x0fa1`, `0x1240`, `0x1447`, `0x15e5`, `0x1b6c`, `0x1f00`, `0x1f0d`, `0x1f1c` and `0x1f3a`. Some of these, such as `0x0fa0` (4000) and `0x0f00`, are likely numeric constants |
| Recall on documented tests (`KNOWN`) | 9 of 9: Pot of Greed in the draw-count chain; Dark Deal and the `0x1b61` marker in `duel_effects_link_should_resolve`; the two `duel_effects_get_spell_speed` cases; the `0xfb6` used-this-turn marker; the Forbidden One pieces passed by `duel_core_check_win` |
| `eq` operands that are card-id shaped | 77.4 % (78.4 % in `rel_duel_eng`): a u16 load, the `0x3fff` id mask, the result of a call (mostly `duel_core_get_slot_card_id`, `ai_get_visible_card_id`, `ai_mask_hidden_card_id`, `duel_core_get_slot_name_id`) or an argument. Word loads 6.0 %, computed values 7.7 %, values clobbered on the straight line 5.3 % |
| Trace error floor | 1.6 % of `eq` operands are byte loads, which can never hold a 14-bit id. These are path-insensitive back-traces that picked a definition on another path |
| Round-number control | Ids that are multiples of 100 could be ATK or LP constants instead of ids. Their `eq` references have the same operand profile (79.5 % card-id shaped) as all references, so the scan shows no excess of false positives there. Of the multiples of 100 that are not cards, only `0xfa0` (4000) and `0x1e78` remain. `0xfa0` occurs only as `lt`, `bound` and `store` (an LP or ATK value, so not a card id). `0x1e78` has an effect record and is an unreleased card id |
| Normal and token cards referenced | 142. Expected for fusion materials, tokens and cards named by other effects. Not checked one by one |

Precision of `eq`/`switch`/`arg`: 77 % of the `eq` references are confirmed by a card-id-shaped operand. The rest are unverified rather than wrong: the trace-error floor is small, and there is no round-number excess. A precision of at least 0.9 is a hypothesis (confidence medium); a PPSSPP trace of a sample would settle it. Not every `eq` reference implements the referenced card's own effect: a card that names another card ("if you control Dark Magician") tests the other card's id. The function name, the operand and the reference kind help to tell these apart.

## Missing cards explained

The 273 effect cards that had no data in `card_effects.py` (188 effect monsters, 30 traps, 26 spells, 15 effect fusions, 6 Gemini, 4 effect tuners, 2 Toons, 2 effect synchros) all have at least one `eq`/`switch`/`arg` reference:

| Basis | Cards |
| --- | --- |
| `eq`/`switch` in a named `rel_duel_eng` function | 185 |
| `eq`/`switch` only in unnamed `rel_duel_eng` functions | 30 |
| Only as a call argument in `rel_duel_eng` (another card or helper names them) | 52 |
| Only in `BOOT.BIN` | 6 |

The functions that test the most of these cards are battle and summon rules:

- `duel_core_get_direct_attack_mode` (23)
- `card_db_can_be_special_summoned` (21, `BOOT.BIN`)
- `duel_core_check_attack_restrictions` (21)
- `duel_core_is_valid_attack_target` (19)
- `duel_core_has_piercing` (18)
- `duel_effects_is_activation_locked` (16)
- `duel_core_chain_step` (15)
- `duel_core_battle_is_destroyed` (14)

The six `BOOT.BIN`-only cards include the four fusion substitutes: Goddess with the Third Eye, Beastking of the Swamps, Versago the Destroyer and Mystical Sheep #1. They form one compare chain in BOOT `0x08866870`, now named `card_db_is_fusion_substitute` (M; `effect-helpers-misc.md`).

These figures describe the set of 273 cards before the engine-mapped rule of `card-effect-spec.md`; 178 of them are now `full` by that rule, and 95 remain `engine_only`.

## Semantics (`tools/engine_ref_semantics.csv`)

The engine functions that test card ids are rules ("has piercing", "can attack directly", "cannot be Special Summoned"). The registry name or the subsystem documents give their meaning, so a card id tested by one of them gets a description: the function's rule applied to that card. `tools/engine_ref_semantics.csv` maps functions to semantic tags.

| Column | Content |
| --- | --- |
| `pattern` | A registry name, an `fnmatch` glob (`card_db_is_*`, `ai_*`), an exact address (`0x09bedc0c`: applies even after the function is renamed) or an address range `0x09ce4000-0x09da0000` (only for functions that still have a default name) |
| `kinds` | `cmp` (`eq`/`switch`), `arg` or `any` |
| `callee` | For `arg` rules only: a glob on the helper that receives the id (`duel_core_count_graveyard_named`) |
| `tag` | Semantic tag (`piercing`, `direct_attack`, `summon_condition`, `activation_lock`, ...) |
| `phrase` | Short template phrase in English |
| `param`, `values` | Name of the per-card parameter and the labels of the branch value: `1=may attack directly;2=must;none=conditional (card-specific test);*=class {value}`. `none` is used when the matched path does not return a constant |
| `confidence` | H, M or L: how well the function's meaning is established. H and M come from a subsystem document; L from the registry name or from the id set of an unnamed function |
| `basis` | The document or observation behind the row |

The first rule that matches wins, so specific rows come before globs, and the `*` callee rows come last. An `arg` reference also gets a `modality` from the helper that receives the id: `while it is active on the field` for the `duel_core_count_active_card*` / `duel_core_is_active_card_at` family, `through an effect marker it leaves on a slot` for `duel_core_slot_has_effect`, `adds an effect marker` for `duel_core_post_add_marker` and so on (`MODALITY` in the tool). References without a rule get the tag `unclassified`.

Generic tags locate a card without describing its effect: `ai_hint` (AI knowledge only), `archetype` (membership in a `card_db_is_*` list), `name_alias` (alias and name rules), `named_reference` (another card's effect names the card), `save_record` (save-file bookkeeping such as `save_set_card_milestone_flag`) and `unclassified`. All other tags are descriptive.

`describe(refs, card_id)` merges the references of one card by (tag, phrase): descriptive tags first, then by confidence; each entry keeps the functions, the modalities and the parameter labels. The `describe` command prints one line per card (by default the `engine_only` cards of `--spec`, or the effect cards outside the tables), for example `inflicts piercing battle damage [piercing: always] (H); generic: archetype`. With `-o` it writes `card_semantics.csv`.

Unnamed functions in the table were given a meaning from their id set or their caller, with confidence L or M; each row's `basis` says how. Examples: `0x09bedc0c` tests exactly the `duel_core_has_piercing` list; `0x09bf6728` the hand-procedure monsters of `duel_core_get_special_summon_mask`; BOOT `0x08863a34` returns the summoning class (1 Polymerization, 2 Dark Fusion, 3 Fossil Fusion) of `effect-helpers-misc.md`; `0x09cdd74c` is the forced position change of chain building state 0 (`chain.md`). These and the other unnamed functions that blocked the most cards are now named (`effect-helpers-misc.md`, "Functions named for the per-card effect spec"); an address row keeps applying after the rename. The stat functions of `stat-modifiers.md` (`duel_core_compute_card_stats`, `duel_effects_get_field_card_stat_bonus`, `duel_core_battle_compute_stats`, `duel_core_battle_get_damage_calc_bonus`, `duel_core_compute_base_stats`) carry the tag `stat_modifier`, `duel_effects_get_standby_lp_cost` the tag `maintenance_cost`, and `duel_core_step_apply_lp_change` (`0x09dbffd8`) the `win_condition` of the eleven "win the Match" monsters.

### Coverage and precision (disc, `--boot --draw`, registry of this commit)

| Measure | Value |
| --- | --- |
| `engine_only` cards with at least one descriptive tag | 266 of 273 (97.4 %) before the engine-mapped rule; 88 of the 95 that remain `engine_only` now (`--check --spec`) |
| Best descriptive confidence per card | H 105, M 132, L 29 (of the 273); H 26, M 33, L 29 (of the 95) |
| Cards with only generic tags | 7: four with `ai_hint`, `archetype` and `name_alias` (alias cards), three with only `unclassified` (tests in unnamed functions without a rule) |

Descriptive tags, as the number of `engine_only` cards that carry them: `summon_condition` 33, `direct_attack` 29, `battle_trigger` 27, `attack_restriction` 23, `multiple_attacks` 21, `negation` 21, `battle_damage_rule` 20, `attack_target_rule` 19, `activation_lock` 19, `fusion_rule` 18, `piercing` 18, `chain_rule` 17, `summon_procedure` 14, `immunity` 14, `battle_indestructible` 14, `destruction_rule` 13, `summon_lock` 13, `tribute_rule` 13, `post_attack` 12, `lp_rule` 8, `position_rule` 8, `phase_effect` 8, `equip_rule` 7, `hand_rule` 6, `banish_rule` 6, `control_rule` 6, `turn_counter` 5, `forced_attack` 4, `summon_trigger` 4, `move_trigger` 4, `target_rule` 3, `coin_toss` 2, `deck_rule` 2, `draw_rule` 2, `ritual_rule` 2, `synchro_rule` 2, `win_condition` 1, `counter_rule` 1, `gemini_rule` 1.

Precision was estimated by comparing the descriptions with public knowledge of the cards (the official card texts, summarised, not copied):

- Systematic sample: every ninth `engine_only` card (31 cards, 29 with a descriptive tag). The first descriptive entry was right for 28 of the 29. The one miss is a monster whose first entry is an attack restriction; this is very probably another card's rule that names it (the reference is a compare on a word load).
- A second, ad hoc check of about 45 cards (direct attackers, piercing monsters, double-Tribute monsters, attack locks, fusion substitutes, Barrier Statues, banishers) found one more wrong first entry: a monster tested in `duel_core_has_piercing` on a conditional path, whose card has no piercing.
- Entry level (every descriptive entry, not only the first): about 85 %. The misses are mostly references where another card names this one (an `eq` on a word load inside a rule function), and vague L phrases (`battle_trigger`, `chain_rule`) that are right but say little.

Estimate (M): about 0.95 for the best descriptive tag of a card and about 0.85 for all its descriptive entries. A tag says *which rule* a card takes part in, not the full effect: `chain_rule` or `battle_trigger` only say where the card is handled.

Parameters recovered from the branch value: `direct_attack` mode (10 cards "may attack directly", the others conditional), `piercing` (15 unconditional), `multiple_attacks` (6 unconditional), the Fusion spell class (Polymerization / Dark Fusion / Fossil Fusion), the Fusion material count, the turn count of `card_db_get_turn_counter_rule`, the immunity mask, and the Special/Normal Summon permission bits.

### Limits of the semantics

- The tag comes from the function, not from the card's branch. A card that is only *named* by another card's rule in that function (for example "while card K is on the field") gets the function's tag too. The operand and the reference kind help: an `eq` on `result of duel_core_get_slot_card_id` is the tested monster's own rule; an `eq` on a word load is often a stored link or marker.
- `value` covers only straight-line, register-only paths. Conditional branches (`none`) need the branch body decoded; `calls` gives a first hint of what they do.
- L rows come from registry names or id sets. They should be confirmed when the functions are documented, and unnamed functions given a rule here should be named in `re/functions.csv`.
- `card_effects.py` carries the `semantics` of each `engine_refs` group and uses them for the engine-mapped `full` rule (`card-effect-spec.md`, "Engine-mapped cards"). A wrong tag in a named function can therefore raise a card to `full`; the precision of that rule is measured there.

## Outputs

`card_refs.csv` (one row per reference): `card_id name kind detail module address use function function_name group operand value calls constants tag phrase confidence parameter`.

`card_semantics.csv` (`describe -o`, one row per card): `card_id name descriptive tags description`. `address` is the instruction with the immediate. `use` is its reader (the branch, `sltiu`, call or store).

`card_ref_functions.csv` (one row per function): `module function function_name group ids kinds`.

Both are game data: keep them in `extracted/`.

## `--check`

`--check` prints the counts, the operand profile and the recall on `KNOWN`. With `--cardinfo` it also prints the released-card share, the precision proxies, and the effect cards without an effect-table record or list entry (369 on the disc, all referenced). It then prints the semantic coverage: of the `engine_only` cards of `--spec` (273), or else of those 369 cards: the cards with a descriptive tag, the tag distribution, the best confidence per card and the generic tags of the rest. It fails in three cases:

- a documented test of `KNOWN` is not found (checked only on the full `rel_duel_eng` module);
- fewer than half of the referenced ids are released cards;
- a rule of `engine_ref_semantics.csv` has a `kinds` other than `any`/`cmp`/`arg`, a confidence other than H/M/L, or an empty tag or phrase.

## Limits and open questions

- The scan is straight-line and path-insensitive. An id that is loaded into a register and compared after a loop or join is not seen. Some operands are attributed to a definition on another path.
- Ids built arithmetically (`base + k`) or read from data tables are not found. The known data tables have their own tools: effect tables, lists, AI tables, token, fusion and ritual tables.
- `range` and `bound` keep every id of the interval; they are not used to explain cards.
- Whether a reference implements the card's own effect or names it from another card's effect needs the function's meaning. This improves as functions are named in `re/functions.csv`.
