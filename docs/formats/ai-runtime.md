# Duel AI runtime structures (`gmodule/rel_duel_eng.prx`)

Status: `documented` for the nine AI runtime rows of `re/formats.csv` listed below. This file gives the memory layout of the blocks the CPU duelist builds while it thinks; how the AI uses them is told in [`docs/subsystems/ai.md`](../subsystems/ai.md) ("Main-phase decision loop", "Simulation and scoring", "Decision pipeline", "Board view"), [`ai-helpers.md`](../subsystems/ai-helpers.md), [`battle.md`](../subsystems/battle.md) and [`stat-modifiers.md`](../subsystems/stat-modifiers.md). The static AI tables (card-id/handler priority lists) are in [`ai-tables.md`](ai-tables.md).

Addresses are runtime addresses with `rel_duel_eng` loaded at `0x09be1400` (`docs/subsystems/modules.md`). All blocks live in the AI part of the duel engine's `.bss`, the region from `0x09e02ff8` that `duel_core_reset` clears at duel start; all multi-byte values are little-endian. "Side" is 0 or 1 (`side & 1` selects the player block, stride `0xb3c`, at `0x09e2a528`).

Basis: the decompilation-based prose and the documented accessors in `re/documented-duel_eng.tsv` (Ghidra, 2026-10-31 rounds), checked and completed for this document with a read-only capstone disassembly of `rel_duel_eng.prx` (a scan of every `lui`/offset access into each range, then the accessor bodies; relocation entries read from the PRX's `0x700000a0` section). Nothing in this file has been traced in PPSSPP yet; the runtime checks that would confirm it are listed in `ai.md` ("PPSSPP checks for the plan comparison").

Confidence: **H** read directly from the instructions that access the field, **M** a clear code basis with one inferred meaning, **L** structural only.

## Address map

| Range | Size | Row | Content |
| --- | --- | --- | --- |
| `0x09e02ff8`–`0x09e03067` | `0x70` | `ai_context` | AI side, view side, main-phase step state, context stack (the candidate stack sits inside it, see next row) |
| `0x09e03004`–`0x09e03025` | `0x22` | `ai_candidate_stack` | 8 × 4-byte entries + depth word |
| `0x09e03068`–`0x09e0307f` | `0x18` | (not a format row) | AI scratch and rule words, listed under `ai_context` for completeness |
| `0x09e03080`–`0x09e0308b` | `0x0c` | `ai_summon_choice` | Chosen summon |
| `0x09e0308c`–`0x09e03333` | `0x2a8` | `ai_stat_snapshot` | Simulated monster stats, 2 sides × 5 slots × `0x44` |
| `0x09e03334`–`0x09e276e3` | `10 × 0x39f8` | `ai_snapshot_slot` | Duel-state snapshot slots 1–10 |
| `0x09e276e4`–`0x09e27f8f` | `3 × 0x2e4` | `ai_battle_plan` | Working plan, then the saved plan of side 0 and of side 1 |
| `0x09e27f90`–`0x09e27ff7` | `0x68` | (not a format row) | Extra-deck summon plan scratch, plan flags, snapshot depth (see `ai_snapshot_slot`) |
| `0x09e27ff8`–`0x09e28007` | `0x10` | `ai_combat_tricks` | Combat-trick list |
| `0x09e28008`–`0x09e28625` | `2 × 0x30c` | `ai_board_view` | Per-side board view |
| `0x09e01ba4`–`0x09e01bc3` (`.data`) | `0x20` | `ai_main_steps` | Main-phase step table |

The blocks are packed back to back: the stat snapshot ends where snapshot slot 1 begins, slot 10 ends where the working plan begins, and the combat-trick list ends where the board view begins (H, from the addresses).

## `ai_context`: AI side, step state and context stack (`0x09e02ff8`)

Purpose: which side the AI is deciding for and from whose point of view, where the main-phase state machine stands, and a stack that saves those two sides across nested AI questions (a prompt answered by the AI while another AI decision is running).

| Address | Offset | Size | Type | Meaning | Evidence | Conf. |
| --- | --- | --- | --- | --- | --- | --- |
| `0x09e02ff8` | `+0x00` | 2 | s16 | AI side: the side being decided for | Set by `ai_push_context` (`0x09d9da30`) and by `ai_main_phase_step` (`0x09d953b4`, from the turn player `0x09e2d1d8`); compared with `side` in `ai_get_slot_battle_stats_as_ai` (`0x09cea1f8`). 31 loads, 37 stores | H |
| `0x09e02ffa` | `+0x02` | 2 | s16 | View side: the side whose knowledge the board view reflects | Set by `ai_push_context`, `ai_main_phase_step`; passed to `ai_analyze_board` by `ai_pop_state_snapshot`. 69 loads | H |
| `0x09e02ffc` | `+0x04` | 2 | s16 | Main-phase step 0–8 (index into `ai_main_steps`) | `ai_main_phase_step`: read, advanced by the step function's return value, 7 → 2 (loop), 8 → 4 with return 3; also read by `ai_is_past_summon_step`, `ai_main_state_*` | H |
| `0x09e02ffe` | `+0x06` | 2 | s16 | Loop counter of the main phase (step 7 → 2 at most 3 times; also `& 3` in step 4) | `ai_main_phase_step` (`slti 3`), `ai_main_state_after_battle` | H |
| `0x09e03000` | `+0x08` | 4 | u32 | Sub-state of the current step; zeroed each time the step advances | `ai_main_phase_step` `sw $zero` after the advance; 33 loads, 57 stores in the step functions | H (field), M (sub-state meaning) |
| `0x09e03004` | `+0x0c` | 0x20 | — | `ai_candidate_stack` entries (own row, below) | — | H |
| `0x09e03024` | `+0x2c` | 2 | s16 | `ai_candidate_stack` depth | — | H |
| `0x09e03026` | `+0x2e` | 2 | s16 | Context stack depth (number of frames in use) | Incremented by `ai_push_context`, decremented by the 30 AI entry wrappers (`ai_answer_*`, `ai_chain_response`, `ai_main_phase`, `ai_query_battle_dominance`, …) | H |
| `0x09e03028` | `+0x30` | 8 × 8 | frame[8] | Context frames, frame `i` at `0x09e03028 + 8·i` (layout below). Frame `depth − 1` is the current one | `ai_push_context`: `sh side, 0x30(base + 8·(depth−1))`, `sh view, 0x32`, `sw replan, 0x34`. Space up to `0x09e03067` holds 8 frames; no bound check in `ai_push_context` | H (layout), M (capacity 8: the next field starts at `0x09e03068`) |

Context frame (8 bytes):

| Offset | Size | Type | Meaning | Conf. |
| --- | --- | --- | --- | --- |
| `+0x00` | 2 | s16 | AI side of this frame (a negative `side` argument keeps the current AI side) | H |
| `+0x02` | 2 | s16 | View side of this frame | H |
| `+0x04` | 4 | s32 | `replan` argument: when non-zero the push (and the matching pop) re-plans with `0x09d16afc` | H |

Push (`ai_push_context(side, view, replan)`, H): if the depth is 0, or `side` differs from the top frame's side, set `0x09e02ff8 = side` and rebuild the board view (`ai_analyze_board(view)`); otherwise, if `view` differs from the top frame's view, only store `0x09e02ffa = view` (no rebuild), and if both match, force `replan` to 0. Then append the frame (the stored `replan` word is the original argument) and re-plan with `0x09d16afc` when the effective `replan` is non-zero. Pop (inline in each wrapper, H): decrement the depth; if frames remain, restore side/view from the new top frame, rebuild the view when either changed and re-plan when that frame's `replan` word is set.

Neighbouring AI words (not part of this row, listed so the range is complete):

| Address | Size | Meaning | Conf. |
| --- | --- | --- | --- |
| `0x09e03068` | 4 | AI scratch word written by 17 handlers and choosers (cost counts, a controller, a best ATK) and read by the activation code afterwards (`ai.md`, `ai-helpers.md`) | H |
| `0x09e0306c` | 4 | Packed slot (`side` bit 0, slot bits 8–15) used by `ai_score_candidate_stored_in_slot` and `ai_choose_name_copy_candidate` | M |
| `0x09e03070` | 4 | AI rule flags (`0x08`, `0x20` dominance stale, `0x80` control-change lock, bits 0–1 Double Summon / Chain Summoning once per turn) | H for the bits named in `ai.md` |
| `0x09e03074` | 4 | Deferral word of the planned summon (`ai_set_deferrals_for_planned_summon`, `ai_main_state_summon`) | L |
| `0x09e03078` | 4 | Deferred-category mask (table A entries kept only when their bit is set) | H |
| `0x09e0307c` | 4 | Chain response mode (0 / 1 / other) set by `ai_choose_chain_response` | H |

Accessors: `ai_push_context` (`0x09d9da30`, documented), `ai_main_phase_step` (`0x09d953b4`), the `ai_answer_*` wrappers (`ai.md`, "Key functions"). Reset: `duel_core_reset` clears the whole region.

Unknown: nothing inside `0x09e02ff8`–`0x09e03067` is unaccounted for; the meaning of the sub-state values in `+0x08` is per step function and not tabulated.

## `ai_candidate_stack`: AI candidate card stack (`0x09e03004`, depth `0x09e03024`)

Purpose: while the AI simulates a card that would choose candidates (search, revive, cost), it pushes that card so that nested evaluators (veto chains, stat estimates, summon-mode filters) know which effect is being considered.

| Address | Size | Type | Meaning | Evidence | Conf. |
| --- | --- | --- | --- | --- | --- |
| `0x09e03004 + 4·i` | 2 | u16 | Card id of entry `i` (`i` = 0..7) | `ai_push_candidate_card` (`0x09ce4ba8`): `sh card, 0x1c04(base + 4·depth)` | H |
| `0x09e03006 + 4·i` | 2 | u16 | Class of entry `i`: `ai_is_special_summon_effect(link)` (non-zero when the effect special-summons) | Same functions, store at `+2` | H |
| `0x09e03024` | 2 | s16 | Depth (entries in use); the top entry is `0x09e03000 + 4·depth` | `ai_push_candidate_card`/`_link` increment, `ai_pop_candidate_card` (`0x09ce4c54`) decrements and zeroes the popped pair; `ai_allows_summon_mode_04_for_pushed_card` reads the top | H |

Capacity: 8 entries (`0x20` bytes) before the depth word (M: no bound check in the push functions; the depth word follows the 8th entry). Writers: `ai_push_candidate_card`, `ai_push_candidate_link` (`0x09ce4b40`), `ai_pop_candidate_card`, and inline push/pop in `ai_estimate_off_field_atk_for_card` / `…_def_for_card`. The link used for the class is the current chain link `0x09e28e44` when it is for the same card, else a zeroed 24-byte local link (H). Unknown: none.

## `ai_summon_choice`: AI summon choice record (`0x09e03080`, 12 bytes)

Purpose: the summon the AI decided on (Normal, Tribute, Gemini or a special summon from the hand or Extra Deck), read later by the code that submits the summon and by the main-phase steps.

The record is copied as three words (`lwc1`/`swc1` of `+0`, `+4`, `+8`) from a local candidate record by `ai_rate_summon_candidate` (`0x09d1b338`, five copies) and `ai_update_best_summon_candidate` (`0x09d18eb4`), which proves the 12-byte size (H).

| Offset | Size | Type | Meaning | Evidence | Conf. |
| --- | --- | --- | --- | --- | --- |
| `+0x00` | 1 | s8 | Hand index of the monster to summon, or its field slot when `+0x03` is set | `ai_submit_summon_from_hand` (`0x09d6b368`) passes it as the hand index (location `0x0b`) or as the slot of a Gemini summon; `ai_execute_planned_summon` | H |
| `+0x01` | 1 | s8 | Side the candidate is simulated for (`& 1` selects the player block); used when the caller passes a negative side | `ai_sim_summon_card_to_field` (`0x09d17310`), `ai_sim_summon_get_position` (`0x09d1a558`), `ai_should_summon_in_defense` | M |
| `+0x02` | 1 | s8 | Field slot the simulated summon landed in | Written by `ai_sim_summon_card_to_field` with the chosen zone; read by `ai_can_special_summon_card`, `ai_plan_battle_with_summoned_monster` | M |
| `+0x03` | 1 | u8 | From-field flag: the choice is a Gemini summon of a monster already on the field | `ai_submit_summon_from_hand`, `ai_execute_planned_summon`, `ai_try_final_normal_summon` | H |
| `+0x04` | 1 | u8 | Set face-down: the submitted position mode is 6 instead of 4 | `ai_submit_summon_from_hand` | H |
| `+0x05` | 1 | u8 | Summon already handled / pending flag: when set, `ai_can_normal_summon_now` refuses and `ai_execute_planned_summon` reports done | `ai_can_normal_summon_now` (`0x09d39ba8`), `ai_try_final_normal_summon`, `ai_main_state_summon` | M |
| `+0x06` | 2 | u16 | Card that needs special handling (non-zero = yes) | `ai_choice_has_special_card` reads it; written by `ai_choose_normal_summon`, `ai_choose_special_summon` | M |
| `+0x08` | 4 | u32 | Unknown word written by `ai_choose_special_summon`, `ai_eval_extra_deck_summon`, `ai_try_adjust_monster_position`, `ai_try_hand_special_summons` and read by the Extra Deck evaluators | Access scan only | L (unknown) |

Rating (tier 1–5 plus an ATK/DEF tie-breaker) is computed in `ai_rate_summon_candidate` and is not stored in the record (`ai.md`, "Summon choice"). Unknown: the meaning of `+0x08`.

## `ai_stat_snapshot`: simulated monster stats (`0x09e0308c`, `0x154` per side)

Purpose: the AI's frozen view of every monster's battle stats, used by the simulated battles (`ai_sim_battle_between_slots`, `ai_sim_battle_resolve`, and `duel_core_battle_resolve` in simulate mode, `battle.md`) so that simulation does not recompute modifiers.

Writer: `ai_sim_prepare_battle_stats` (`0x09cfcf5c`, H): `system_memzero(0x09e0308c, 0x2a8)`, then for each side 0–1 and monster slot 0–4 holding a card, `ai_get_slot_battle_stats_as_ai(side, slot, record)` (`0x09cea1f8`). Record address: `0x09e0308c + side·0x154 + slot·0x44` (5 records per side, H).

| Offset | Size | Type | Meaning | Evidence | Conf. |
| --- | --- | --- | --- | --- | --- |
| `+0x00` | `0x34` | u32[13] | The 13-word stat block of `stat-modifiers.md` ("The stat block"): name id, effective id, Type, Attribute, attribute mask, Level, ATK `+0x18`, DEF `+0x1c`, original ATK/DEF `+0x20`/`+0x24`, three immunity masks | Filled by `duel_core_get_card_stats` for the AI side and by `ai_estimate_slot_stats` (`0x09ce9edc`) for the other side; `ai_sim_battle_between_slots` copies `0x34` bytes into a battle frame; readers of `0x09e030a4` (`+0x18`) and `0x09e030a8` (`+0x1c`) | H |
| `+0x34` | 4 | s32 | ATK from `duel_core_compute_card_stats(side, slot, rec, 2, 0)` (flags 2), kept before the final recompute | `ai_get_slot_battle_stats_as_ai`: copies `+0x18` → `+0x34` | H (copy), L (meaning of flag 2) |
| `+0x38` | 4 | s32 | DEF, same pass | copies `+0x1c` → `+0x38` | H / L |
| `+0x3c` | 4 | s32 | Original ATK, same pass | copies `+0x20` → `+0x3c` | H / L |
| `+0x40` | 4 | s32 | Original DEF, same pass | copies `+0x24` → `+0x40` | H / L |

The `+0x34`–`+0x43` copies are written only on the AI side's records (`side == 0x09e02ff8`); for the other side `ai_estimate_slot_stats` fills the record and whether it writes `+0x34`–`+0x43` is unknown. In a card-specific branch (cards `0x1678` and `0x0eb8`, only in phase 2) `ai_sim_prepare_battle_stats` also zeroes word `+0x00` of one record (L for the purpose). Empty slots stay zero. Unknown: who reads `+0x34`–`+0x43`; the exact meaning of compute flag 2.

## `ai_snapshot_slot`: AI state snapshot slot (`0x09dff93c + n × 0x39f8`, n = 1..10)

Purpose: save/restore of the rules state around a simulation. The AI runs the real rules code on the real state, so it pushes a copy first and pops it afterwards (`ai.md`, "State snapshots").

| Offset | Size | Copied from/to | Meaning | Evidence | Conf. |
| --- | --- | --- | --- | --- | --- |
| `+0x000` | `0xc14` | `0x09e29914`–`0x09e2a527` | Command/duel block (engine globals before the player blocks: command queue tail, candidate list, …, `docs/subsystems/duel_core.md`) | `ai_push_state_snapshot` (`0x09d0ea9c`): word loop of `0x305` words | H |
| `+0xc14` | `0x2de4` | `0x09e2a528`–`0x09e2d30b` | Both player blocks (`2 × 0xb3c` + tail) | Same function, `0xb79` words to `0x09e00550 + n·0x39f8` | H |

Slot index: the depth word `0x09e27fee` (s16) is incremented **before** the copy, so slots 1–10 are used and live at `0x09e03334`–`0x09e276e3`; the formula's slot 0 (`0x09dff93c`) is never written and overlaps `.data` (H: `slti depth, 10`, increment, multiply). Push returns 0 when the depth is already 10. Pop (`ai_pop_state_snapshot`, `0x09d0edf8`) copies slot `depth` back, rebuilds the board view for `0x09e02ffa`, decrements the depth and calls `duel_effects_update_negated_slots(1)`. Callers push through these two functions or inline copies of the same loops (`ai_simulate_attack`, `ai_plan_battle_with_tricks`, `ai_plan_battle`).

Correction: `ai.md` gives the end of the ten slots as `0x09e27ebc`; the arithmetic gives `0x09e276e3` (slot 10 starts at `0x09e23cec`), which is also the byte before the working battle plan.

Neighbour globals of the AI simulation (not separate rows): `0x09e27fee` snapshot depth (s16, H); `0x09e27ff0` plan-valid flag (s16, H); `0x09e27ff2` set by `ai_plan_init` when `full` (H); `0x09e27ff4` mask of attack targets already flagged (u32, M); `0x09e27fd4`/`0x09e27fd8` simulated battle results (`ai_sim_battle_resolve`, M). Unknown: none inside the slot (it is a byte copy of documented engine blocks).

## `ai_battle_plan`: AI battle plan (`0x2e4` bytes)

Instances: the working plan at `0x09e276e4`, and the saved plan of each side at `0x09e279c8 + side·0x2e4` (`0x09e279c8`, `0x09e27cac`). `ai_get_plan_value(side)` reads `+0x08` of the working plan (side < 0) or of a saved plan (H).

Purpose: the result of simulating every attack the side could make this turn, compared between variants (with/without a combat trick, with a summoned monster) by `ai_compare_plans`.

| Offset | Size | Type | Meaning | Evidence | Conf. |
| --- | --- | --- | --- | --- | --- |
| `+0x00` | 2 | u16 | Own monsters destroyed in the simulated battles | `ai_plan_init` zeroes, `ai_plan_simulate_attacks` increments | H (write), M (meaning) |
| `+0x02` | 2 | u16 | Opponent monsters destroyed | same | H / M |
| `+0x04` | 2 | u16 | Own monsters left | `duel_core_count_monsters` | H / M |
| `+0x06` | 2 | u16 | Opponent monsters left (`ai_compare_plans` bit `0x08`) | same | H / M |
| `+0x08` | 4 | s32 | Plan value: total planned damage (`ai_get_plan_value`) | `ai_plan_simulate_attacks`, `ai_get_plan_value` | H |
| `+0x0c` | 4 | s32 | Secondary score: sum of the evaluator word `0x09e27fb8[defender]` | `ai_compare_plans` bit `0x02` | H (sum), L (meaning) |
| `+0x10` | 4 | s32 | Own LP after the attacks | `ai_plan_init` from the player block or crosswise from `from_plan` | H |
| `+0x14` | 4 | s32 | Opponent LP after the attacks | same | H |
| `+0x18` | 2 | s16 | Battle dominance after the attacks | `ai_eval_battle_dominance(side, 0, 1)` | H |
| `+0x1a` | 2 | u16 | Slot mask of monsters with special attack rules | `ai_plan_prepare_attack_state` | M |
| `+0x1c` | 2 | s16 | Own deck size after the attacks | `ai_plan_init`, battle mill subtracted | H |
| `+0x1e` | 2 | s16 | Opponent deck size after the attacks | same | H |
| `+0x20` | 2 | u16 | Combat trick assumed (0 = none) | `ai_plan_init(…, trick)` from `ai_get_combat_trick(i)` | H |
| `+0x22` | 2 | u16 | 1 when the attacks win the duel | `ai_plan_simulate_attacks` | H |
| `+0x24` | `5 × 0x20` | entry[5] | Per-monster attack entries (monster slot 0–4); entry layout below | `ai_plan_get_attack_entry` (`0x09d1c8e0`): `plan + 0x24 + 32·slot` | H |
| `+0xc4` | `4 × 0x20` | entry[4] | Extra attack entries (`+0x00` = slot, `0xffff` = unused); used for a slot whose flags word has bit 29 set | `ai_plan_init` writes `+0xc4`, `+0xe4`, `+0x104`, `+0x124`; `ai_plan_get_attack_entry` | H (layout), L ("additional attack") |
| `+0x144` | `18 × 0x10` | rec[18] | Attack-order records; `ai_plan_init` sets u16 `+0/+2/+4/+6/+0xa/+0xc` = 0 and `+8` = `0xffff`, leaves `+0xe`. Record 0 `+2` (`plan + 0x146`, `0x09e2782a` in the working plan) is the chosen attacker slot + 1 (0 = none) | `ai_plan_init` (unrolled loop of 8 + 8 + 2 records with stride `0x10`); `ai_get_planned_attacker` returns `[0x09e2782a] − 1`; `ai_review_battle_plan`, `ai_choose_best_attack` read it | H (layout and record 0 `+2`), L (other fields) |
| `+0x264` | `0x80` | — | Unknown: not initialised by `ai_plan_init` and not addressed directly by any `rel_duel_eng` instruction; part of the record only through the `0x2e4` stride of the saved copies | Access scan | L (unknown) |

Attack entry (32 bytes, from `ai.md`, H for the writes in `ai_plan_init`/`ai_plan_simulate_attacks`, M for the meanings): `+0x00` u16 slot (extra entries) / unused, `+0x02` attacks planned, `+0x04` destroyed an opposing monster, `+0x06` and `+0x0a` flags of that destruction, `+0x08` the attacker was destroyed, `+0x0c` cannot attack (Defence Position or `0x09d3996c`), `+0x0e` target (5 = direct / none; `ai_plan_init` writes the init value here), `+0x10`–`+0x13` unknown, `+0x14` u32 mask of slots destroyed, `+0x18` u32 damage, `+0x1c` u32 evaluator score.

Writers: `ai_plan_init` (`0x09d0eeb8`), `ai_plan_simulate_attacks` (`0x09d1329c`), `ai_choose_attack_target` (`0x09d0ca3c`), and the save/restore copies in `ai_plan_battle_with_tricks` (`0x09d15b58`: header, `0x09e27708` entries, `0x09e277a8` extras, `0x09e27828` records), `ai_plan_battle` (`0x09d16568`), `ai_plan_battle_with_summoned_monster`, `ai_find_best_extra_deck_summon_plan`. Readers: `ai_compare_plans` (`0x09d36d4c`), `ai_get_plan_value`, `ai_get_planned_attacker`, about 120 AI handlers and scorers through the base address. Unknown: `+0x0c` meaning, record fields other than record 0 `+2`, `+0x264`–`+0x2e3`.

## `ai_board_view`: AI board view (`0x09e28008 + side × 0x30c`)

Purpose: what the AI knows about each side, rebuilt by `ai_analyze_board(view)` (`0x09d91fe8`) after every push/pop of context or snapshot: cached battle dominance, rule flags and a list of "interest" records naming the combo cards the side holds (`ai.md`, "Board view").

| Offset | Size | Type | Meaning | Evidence | Conf. |
| --- | --- | --- | --- | --- | --- |
| `+0x00` | 2 | s16 | Battle dominance (simulated), −4..4 | `ai_get_battle_dominance` (`0x09d37490`) reads `0x09e28008 + side·0x30c` unless flag `0x09e03070 & 0x20` | H |
| `+0x02` | 2 | s16 | Battle dominance (plain) | `ai_get_plain_battle_dominance` (`0x09d374ec`) reads `0x09e2800a + …` | H |
| `+0x04` | 2 | s16 | Summon slack (`0x80 − x`, or `2 −` hand size under Summon Limit); positive = may still Normal Summon | `ai_can_normal_summon_now` (`lh` at `0x09e2800c + …`, `> 0`); `ai_choose_tribute_summon_from_hand`, three summon handlers | H (read), M (formula) |
| `+0x06` | 2 | u16 | AI activation counter; above `0x7f` the AI stops activating | `ai_increment_activation_count`, `ai_is_activation_count_exhausted` (`0x09e2800e + …`) | H |
| `+0x08` | 4 | u32 | Board rule flags (opponent cannot draw, Necrovalley, King Tiger Wanghu, By Order of the Emperor, …; `0x100` raises the hand-card threshold of `ai_evaluate_activation`) | Written by `ai_analyze_board`; several readers address side 0's copy `0x09e28010` directly | H (field), M (individual bits) |
| `+0x0c` | `32 × 0x18` | rec[32] | Interest records (layout below) | `ai_board_add_interest_record` (`0x09d8fb44`): base `0x09e28014 + side·0x30c`, 32 entries, stride `0x18` | H |

Interest record (24 bytes):

| Offset | Size | Type | Meaning | Conf. |
| --- | --- | --- | --- | --- |
| `+0x00` | 2 | u16 | Weight; 0 = free entry. A new record equal in `+0x04`–`+0x17` adds its weight here | H |
| `+0x02` | 2 | u16 | Copied from the caller's record, not compared; meaning unknown | H (copy), unknown meaning |
| `+0x04` | 4 | u32 | Card id the interest is about | H (compared), M (meaning) |
| `+0x08` | 16 | u32[4] | Flag words compared for equality; meaning unknown (`ai.md`, open question) | H (compared), L |

`ai_board_add_interest_record(side, rec, weight)` returns 1 when a new entry was used, 0 when merged or when all 32 are taken (H). Fillers: `ai_board_note_card_interests` (`0x09d8fc24`), `ai_board_note_combo_interests` (`0x09d91d30`). Size check: `0x0c + 32·0x18 = 0x30c` (H). Unknown: `+0x02` and `+0x08`–`+0x17` of the interest records.

## `ai_main_steps`: main-phase step table (`.data 0x09e01ba4`)

Purpose: the seven functions of the AI's main-phase state machine, called by `ai_main_phase_step` with the step `0x09e02ffc` as index.

| Index | Address | Value | Function | Conf. |
| --- | --- | --- | --- | --- |
| 0 | `0x09e01ba4` | `0x09d8b184` | `ai_main_state_open` | H |
| 1 | `0x09e01ba8` | `0x09d93f6c` | `ai_main_state_summon` | H |
| 2 | `0x09e01bac` | `0x09d94cf4` | `ai_main_state_summon_extra` | H |
| 3 | `0x09e01bb0` | `0x09d9524c` | `ai_main_state_battle_check` | H |
| 4 | `0x09e01bb4` | `0x09d944e8` | `ai_main_state_after_battle` | H |
| 5 | `0x09e01bb8` | `0x09d95144` | `ai_main_state_cleanup` | H |
| 6 | `0x09e01bbc` | `0x09d8cfbc` | `ai_main_state_end` | H |
| 7 | `0x09e01bc0` | 0 | NULL: the runner returns 5 (end) | H |

Entry: `u32` code pointer, stored as a module offset with a type-2 (`R_MIPS_32`) relocation; the PRX relocation section has entries for indices 0–6 only, so index 7 is a true NULL (H). The word after it (`0x09e01bc4`) is also 0 and is not read with a step index ≤ 7 (step 8 is turned into 4 before any table read), so the table is 8 entries, 32 bytes (H). Runner semantics (`ai_main_phase_step`, H): step 0 becomes 5 when the phase word `0x09e2d1e8` is 4 (Main Phase 2); a non-zero return `r` advances the step by `r` and clears `0x09e03000`; a NULL entry returns 5, and so does an advance to a step other than 7 while the word `0x09e2d228` is non-zero; reaching 7 loops back to 2 up to three times (`0x09dd09f4`, `0x09dd0b88`); reaching 8 sets step 4 and returns 3 (go to battle). Step descriptions: `ai.md`, "Main-phase decision loop".

## `ai_combat_tricks`: combat trick list (`0x09e27ff8`, 16 bytes)

Purpose: the battle-time cards the AI could play this turn; the battle planner replays its plan once per entry and keeps the better result (`ai.md`, "Battle plan").

| Offset | Size | Type | Meaning | Evidence | Conf. |
| --- | --- | --- | --- | --- | --- |
| `+0x00 + 2·i` | 2 | u16 | Card id of trick `i` (`i` = 0..7); 0 = free | `ai_add_combat_trick` (`0x09d1cae4`) stores into the first 0 entry, refuses 0 and duplicates, fails when full; `ai_get_combat_trick(i)` (`0x09d1cb10`) returns entry `i` or 0 outside 0–7; `ai_clear_combat_tricks` (`0x09d1ca94`) zeroes 16 bytes | H |

Filled by `ai_analyze_board` (clear, then add the usable tricks such as Battle Fusion, Shield & Sword, Limiter Removal; M for the card list), read only by `ai_plan_battle_with_tricks`. Unknown: none.

## Open questions

- `ai_summon_choice +0x08` (u32) and the meaning of `+0x01`/`+0x02` beyond the simulation side and landing slot.
- `ai_stat_snapshot +0x34`–`+0x43`: readers, the meaning of compute flag 2, and what `ai_estimate_slot_stats` writes there for the non-AI side.
- `ai_battle_plan`: meaning of `+0x0c`, of the attack-order records other than record 0 `+2`, and of the unaddressed tail `+0x264`–`+0x2e3`.
- `ai_board_view` interest records: `+0x02` and the four flag words.
- Runtime confirmation (none of these structures has been traced): dump the context frames during a nested prompt, the summon record after `ai_choose_normal_summon`, and one stat-snapshot record against the on-screen ATK/DEF.
