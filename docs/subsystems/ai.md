# Opponent and partner AI (work package 6)

The duel AI lives in the duel engine `gmodule/rel_duel_eng.prx` (runtime base `0x09be1400`), roughly `0x09cec000`–`0x09da0000` plus the entry wrappers at `0x09d9da30`–`0x09d9fc9c`. All addresses below are runtime addresses in that module unless marked `BOOT.BIN`.

Basis: static analysis of the Ghidra decompilation of the whole module (call graph and code of every function) and of the data tables the code indexes. Nothing here has been traced in PPSSPP yet. Confidence is given per claim (H/M/L).

## Architecture in one paragraph

The AI is **hand-written code plus card-id tables**, not a script interpreter and not a generic search. (1) Every place where a duelist has to decide checks the duelist kind and, for a CPU duelist, calls an AI entry wrapper instead of opening a menu (H). (2) The main phase is a small state machine of seven steps; each step walks **priority tables of `(card id, AI handler)` pairs** and activates the first card in hand or on the field whose handler accepts (H). (3) Summons, attacks and battle tricks are chosen by **simulation**: the AI snapshots the duel state (up to 10 levels deep), plays a candidate out with the real rules code, scores the outcome and restores the state (M–H). (4) Target choices go through a 131-case compare chain on the card id with generic "best/worst ATK/DEF" pickers as fallback (H). (5) No per-character personality parameter reaches the duel engine; behaviour differences between CPU duelists come from their decks (M, see "Personality").

## Human/CPU split

The duelist kind is `u32 0x09e02998[side]` (and `0x09e029a0[side]` for the waiting tag partner, swapped in by `tag_duel_swap_active_duelist`): 0 = local human, 1 = CPU, 2 = remote (wireless) duelist, 3 at `0x09e02998` = replay/demo mode where commands are not queued (H for 0/1; M for 2/3, from the `0x09e2d200` "link" checks around every command push and `duel_core_push_command` skipping kind 3). Getters at `0x09be190c`/`0x09be192c`/`0x09be194c`/`0x09be196c` are exported but not called inside the module.

Prompt functions near `0x09dc7200`–`0x09dc7c00` all have the same shape: if the asking duelist is a CPU, call an AI wrapper and store its answer in `0x09e2d248` (the same "dialog result" word a human answer would fill); otherwise open dialog `0x09be1400(0x36, kind, …)` (H). Observed pairs:

| Prompt | Dialog kind | AI wrapper | AI worker |
| --- | --- | --- | --- |
| `0x09dc72b0`, `0x09dc73e0` (yes/no on a card, 31 + 13 callers in effect handlers) | 2 | `ai_ask_yes_no` `0x09d9efcc` | `ai_decide_yes_no` `0x09d9903c` → `ai_decide_optional_activation` `0x09d95f5c` (12 KiB) |
| `0x09dc725c`, `0x09dc733c` (yes/no without a ctx) | 2 | `0x09d9f0c0` | `0x09d990a4`, `0x09d99284` |
| `0x09dc74f8` | – | `0x09d9f0c0` | – |
| `0x09dc76c8` (pick one of up to four card ids, 17 callers) | 4 | `0x09d9f654` | `0x09d9a1fc`, `0x09d9a4b4` |
| `0x09dc790c` | 6 | `0x09d9f8a4` | `0x09d9c2c4` |
| `0x09dc795c` | 7 | `0x09d9f9a8` | `0x09d9d238` |
| `0x09dc79c0` `duel_core_ask_summon_position` (summon position prompt; passes fields of the summon record `0x09e290bc`, `summon.md`; corrected 2026-10-31) | 8 | `0x09d9e204` | `0x09d48720` among others |
| `0x09dc7a88` | 9 | `0x09d9f434` | `0x09d99fe0` (per-card coin/odd-even answers, `duel_core_random(2)` default) |
| `0x09dc7adc` | 10 | `0x09d9f31c` | `0x09d99db8` (Sixth Sense number choice) |
| `0x09dc7b60` (choose a number in a range) | 11 | `0x09d9f1d4` | `0x09d999dc` (per-card values, e.g. a random 4–8) |
| target-selection UI `0x09dcea6c`, `0x09dced60`, `0x09dce978`… | – | `0x09d9ea94`, `0x09d9e8b4` | `0x09d67474`, `0x09d6a8d4` |
| effect slot `+0x14` choose-target handlers (9) | – | `ai_choose_targets` `0x09d9ddfc` | `ai_decide` `0x09d649ec` |

Every wrapper has the same frame (H): `ai_push_context(side, side, replan)`, call the worker, then pop the AI context stack and, if the popped level had a different side/view, rebuild the view (`ai_analyze_board`) and re-plan (`ai_replan_turn_player`). So AI decisions can nest (a CPU effect asking the CPU opponent for a response).

## Phase handlers that call the AI

The phase/step handlers are function-pointer tables at `0x09e01da0` (`0x09de0094`, `0x09ddb090`, `0x09de2460`, `0x09de0240`, `0x09ddf4dc`, `0x09de3b78`, …) and `0x09e01dcc` (`0x09dd229c`, `0x09dd23fc`, `0x09dd2a6c`, `0x09dd3574`, …); their phase meaning is documented with the duel core.

| Handler | Calls | Role (confidence) |
| --- | --- | --- |
| `0x09de0240` | `ai_main_phase` `0x09d9db38` when the turn player is a CPU (state `0x09e2d214` 1/2), human path opens the command menu `0x09dc78cc` | Main phase (H) |
| `0x09dd23fc` | `ai_battle_choose_attacker` `0x09d9ec64` | Battle step: pick an attacker or leave battle (H for the AI call, M for the step) |
| `0x09dd2a6c` | `ai_battle_decide_attack` `0x09d9edc8` | Attack confirmation / replay step (M) |
| `0x09ddf4dc`, `0x09de2460` | `0x09d9f76c` → `0x09d9b258`, `0x09d9b2f8` | Card-specific per-phase prompts (Mirror Wall, Imperial Order, Messenger of Peace upkeep, …) (M) |
| `0x09ccbe74` (chain building) | `ai_chain_response` `0x09d9e024` → `ai_choose_chain_response` `0x09d2fd80` | Response window: walks the trap tables below (M) |

## Main-phase decision loop

`ai_main_phase_step` (`0x09d953b4`) runs one step per call of the phase handler (H). State: `0x09e02ffc` (u16 step 0–7), `0x09e02ffe` (loop counter), `0x09e03000` (sub-state of the current step). It sets the AI side `0x09e02ff8` and view side `0x09e02ffa` to the turn player and calls `0x09e01ba4[step]`; a non-zero return advances the step by that amount. Return codes to the phase handler: 0 = an action was issued (call again), 3 = go to battle, 5 = no step function / end. Step 7 loops back to step 2 up to three times while the AI can still act (`0x09dd09f4`, `0x09dd0b88`), and step 8 turns into "battle" (`0x09e02ffc = 4`, return 3).

| Step | Function | What it tries, in order (confidence M unless noted) |
| --- | --- | --- |
| 0 | `ai_main_state_open` `0x09d8b184` | Rebuild view and plan; summon set-up (`0x09d9284c`); **table A** (105 opening spells such as Heavy Storm, Harpie's Feather Duster); field/flip checks (`0x09d8c79c`); hand monsters' Special Summons (`ai_try_hand_special_summons` `0x09d899a8`, which walks hand monsters with `duel_core_get_special_summon_mask`; formerly read as "hand spells"); comeback table if losing; main table and position changes (`ai_try_main_cards`). |
| 1 | `ai_main_state_summon` `0x09d93f6c` | Summon enablers (table C), special summons (`ai_choose_special_summon`), normal summon or set (`ai_choose_normal_summon` → `ai_execute_summon`), then the same sequence again after re-planning; skips summoning while the opponent controls Swords of Revealing Light. |
| 2 | `ai_main_state_summon_extra` `0x09d94cf4` | Double Summon / Chain Summoning once per turn (flags `0x09e03070` bits 0–1), then hand spells, comeback, main table, set monsters (`0x09d94740`), second summon. |
| 3 | `ai_main_state_battle_check` `0x09d9524c` | Decides whether to enter battle: battle-phase cards (`ai_try_battle_cards`), plan value `ai_get_plan_value(side) == 0` and no attacker → skip battle. |
| 4 | `ai_main_state_after_battle` `0x09d944e8` | Comeback table, hand spells, extra summons; loops twice (`0x09e02ffe & 3`). |
| 5 | `ai_main_state_cleanup` `0x09d95144` | Hand spells, main table, set/flip of monsters (`0x09d94740` for slots 0–4). (L) |
| 6 | `ai_main_state_end` `0x09d8cfbc` | Comeback table (when losing), **table G** (94 end-of-turn cards), field checks, Swift Gaia special case, **table H** (6 cards); returns 1 to end. |

### Priority tables of `(card id, handler)` pairs

Each entry is 8 bytes: `u32 card id`, `u32` pointer to an AI handler `int handler(ctx, arg)` (H; 1,648 entries, 1,548 distinct cards, 674 distinct handlers). The tables are contiguous in `.data` (apart from a 56-byte gap of jump tables at `0x09dfe4c8`), have no terminator (all lengths are code constants) and are specified in `docs/formats/ai-tables.md`; `tools/ai_tables.py` lists and checks them:

| Key | Address | Entries | Used by | Content (card kinds from `CARD_Prop`) |
| --- | --- | --- | --- | --- |
| T1 | `0x09dfd448` | 345 (`ai_chain_table_length`) | `ai_try_chain_tables` `0x09d2f908` (chain response) | Mostly traps and quick-plays |
| T2 | `0x09dfdf10` | 2 (0 when `ai_chain_table_length` gets flag 0) | `ai_choose_chain_response` | Response cards, tried first when there is a chain link |
| T3 | `0x09dfdf20` | 181 (0 when `ai_chain_table_length` gets flag 0) | `ai_choose_chain_response` | Response cards, only when the response mode `0x09e0307c` is set or `0x09ccb534` accepts the link |
| A | `0x09dfe500` | 105 | step 0; also prepended to B when `0x09e03078 != 0` | 84 spells (mass removal etc.) |
| B | `0x09dfe848` | 681 (786 with A) | `ai_try_main_cards`, `0x09d8c420`, effect handlers | Main-phase spells and monster effects |
| C | `0x09dffd90` | 7 | `ai_try_summon_enablers` | Teleport, Call of the Mummy, Frontline Base, … |
| D | `0x09dffdc8` | 199 (0 unless `ai_get_battle_dominance < 0`) | `ai_try_comeback_cards` | Spells used when behind (Graceful Charity, Fusion Sage, …) |
| E | `0x09e00400` | 16 | `ai_try_battle_cards` | Battle-time cards (Meteorain, …) |
| F | `0x09e00480` | T1 then 12 (345 + 12, only in the battle phase; T1 comes first) | `ai_try_battle_cards` | Battle-time traps |
| G | `0x09e004e0` | 94 | step 6 | End-of-main-phase cards |
| H | `0x09e007d0` | 6 | step 6 | Last-resort cards |

`ai_table_length` (`0x09d8f0c4`) and `ai_table_entry` (`0x09d8efc0`) implement these counts and the A-before-B filter (A entries are kept only when bit `0x08832e30(card)` of the deferred-category mask `0x09e03078` is set).

`ai_try_table_entry(side, entry, mode)` (`0x09d894e8`, H): for the AI side (and, for cards allowed by `BOOT 0x08866820`, the opponent side), finds a field slot 0–10 holding `entry.card` that is not disabled (slot `+0x44` bits 1/3), builds a chain context at the chain top `0x09e28cb4` (`0x09d30294`), then for the hand (`0x09c035cc` finds the card, slot 11); calls `ai_activate_from_table` and restores the 24-byte chain top afterwards. First match wins, so **table order is the priority**.

`ai_evaluate_activation(entry, ctx, arg, commit)` (`0x09d88c34`, M) is the common gate: refuses when the LP cost would kill the AI (`0x09d3908c` estimates the LP change of both sides) and accepts at once when the effect would reduce the opponent to 0; handles anti-spell/trap cards on the field (`0x09c033a8`, cards `0x19a3`, `0x19a4`); calls `entry.handler(ctx, arg)` and accepts when the result is ≥ 1 (≥ 2 for hand cards under flag `0x09e28010 & 0x100`); defers whole card categories (`0x09e03074` → `0x09e03078`); for a few cards (Limiter Removal family, `0x1430`, `0x142a`, `0x12cb`) re-checks the target against the battle plan. `ai_is_activation_blocked` (`0x09d8923c`) handles locks (Royal Decree, Spell Canceller, Jinzo-like ids `0x17c6`, `0x184f`, `0x17d4`, `0x1816`, `0x171d`) and slot `0x1aa5` checks before any evaluation.

Handlers are small per-card predicates, many shared: `ai_cond_always` `0x09d6b6b8` (187 entries), `ai_cond_has_target` `0x09d6ba6c` (asks the target chooser and accepts when a target exists, 82 entries), `ai_cond_has_candidate` `0x09d6b6c8`, the copy limits `ai_cond_no_active_copy` and relatives (wrappers of `ai_is_card_count_below`), and `ai_handler_equip_strong_monster` `0x09d6c67c` (80 entries, mostly equip spells in table D: accepts an own equip target with ATK > 1,299 or from a short list; an earlier reading of it as "comeback draw spells" was wrong). The helper vocabulary, the 77 handlers shared by three or more entries and a behaviour taxonomy with coverage counts (63.6 % of all entries) are in `ai-helpers.md`. The AI never reads face-down cards: `ai_mask_hidden_card_id` replaces them by level-based stand-ins (H).

So the effect knowledge for the AI is: which cards it knows (table membership), when to use them (handler), and where (table). Cards absent from every table are never activated voluntarily by the CPU (hypothesis, M: no other path to `ai_activate_from_table` was found besides `0x09d41050`/`0x09d30af8`, which use the same tables).

### Per-card handler families

Besides the 77 shared handlers of `ai-helpers.md`, the tables point to **600 single-use handlers** (665 entries: 543 serve one card, sometimes in two tables, and 57 serve two cards). Every one of them is now named by family, `ai_handler_<stem>_<card id>[_<card id>][_<tables>]`: the ids are the cards whose entries use the handler (4 lower-case hex digits; the tables say which cards these are), and a table suffix (`_t3`, `_b`) separates two handlers of one card. `ai_tables.py handlers` reports per card which handlers it has and their family, and `--check --functions …` verifies that each per-card name lists exactly the cards that use it (`docs/formats/ai-tables.md`).

Basis: Ghidra decompilation of all 677 handlers (read-only project, one headless run of a list decompiler), then a rule-based classifier over each handler's callees (registry names) and the globals it reads; about 60 handlers of all families were read in full to write the descriptions below and to check that the rule picks the decision that dominates the code. The rule tests the features in this order and the first match wins: (1) calls a named shared handler or `ai_cond_*` → **variant** of that handler (stem = the shared name; an `ai_handler_*` callee wins over an `ai_cond_*` one); (2) reads the timing-event queue `0x09e28f98`/`0x09e28fa0` → event; (3) in a chain table (T1–T3, R1–R3) and reads the link argument or calls a threat query (`ai_is_card_threatened_*`, `duel_effects_get_link_target`, `ai_classify_resolve_kind`, `0x09bf2fbc`, `0x09bf3c34`) → link; (4) draw, LP, discard, cost, candidate, summon queries, in that order; (5) battle queries; (6) target queries (with `ai_get_battle_dominance` → target_dom); (7) dominance, copy limit, field spell, Graveyard, phase/turn words, the committed shortcut, other duel-core counts (board), nothing called (state). Confidence: M for the family of a member (the rule is mechanical and a handler often combines two tests), L for any member's exact semantics until it is read.

| Family | Stem | Handlers | Entries | Tables | What decides | Example (read in full) |
| --- | --- | --- | --- | --- | --- | --- |
| variant | shared handler's stem | 83 | 96 | T1 43, T3 35, B 17, C 1 | A shared handler's test plus a card-specific condition (usually `shared(...) && extra`). Stems: `counter_harmful_link` 22, `draw_if_safe` 15, `can_discard` 9, `has_target` 7, `can_choose_candidate` 6, `revive_monster` 4, `gain_lp` 3, `special_summon` 3, `no_active_copy`, `has_candidate`, `opponent_has_target` 2 each, 8 others 1 each | `0x09d1f5f0`: `ai_handler_counter_harmful_link` and the link's card is not `0x19cb` |
| event | `react_to_event` | 3 | 4 | T1 | Walks the queued timing events | `0x09d1f358`: refuse while a summon event (codes 6–8) of the AI's own side is queued |
| link | `respond_to_link` | 28 | 35 | T3 30, T1 4, T2 1 | Reads the link it answers: owner, response mode `0x09e0307c`, the link's card or targets | `0x09d27d40`: no link → yes; mode 1 → only own-side links whose resolve kind is non-zero |
| draw | `check_draw` | 14 | 15 | B 6, T1 5, A 3, T3 1 | `ai_would_deck_out`, hand limit | `0x09d1f9a4`: in the opponent's End Phase, if drawing 5 does not deck out |
| lp | `check_lp` | 39 | 44 | B 19, T1 15, others | LP estimates (`ai_estimate_lp_change`, `ai_eval_damage_effect`), LP thresholds | `0x09d2d694`: opponent LP ≤ 1,000 × valid targets |
| discard | `check_discard` | 20 | 23 | B 19, D 3, E 1 | `ai_choose_discard` finds a hand card to give up | `0x09d800dc`: best attacker ATK ≥ 2,000 and a discard exists |
| cost | `check_cost` | 30 | 33 | B 22, others | Cost/hand choosers (`ai_choose_cost_*`, `ai_choose_hand_card_*`) | `0x09d70ac0`: ≥ 2 own monsters and a hand card can be chosen |
| candidate | `check_candidates` | 48 | 53 | B 34, D 11, others | Enough acceptable candidates for a search/revive/recover | `0x09d216a4`: opponent's End Phase and ≥ 3 acceptable candidates |
| summon | `check_summon` | 20 | 21 | B 14, others | Free zones, Normal Summon available, summon simulation | `0x09d79a98`: Neo-Spacians in the Graveyard fill the free zones, or a lethal threat |
| battle | `check_battle` | 66 | 72 | B 48, D 17, E 3, T1 3, G 1 | Battle phase possible, attackers, the battle plan | `0x09d6d728`: the controller can enter battle and this monster can attack now |
| target | `check_targets` | 60 | 64 | B 38, D 9, T1 7, others | Target mask or a chosen target, often weighed by ATK | `0x09d1dd00`: the opponent's highest original-ATK target must have ATK ≥ the opponent's LP |
| target_dom | `check_targets_by_dominance` | 17 | 20 | B 13, others | A target choice gated by the battle dominance | `0x09d83abc` |
| dominance | `check_dominance` | 24 | 28 | B 10, D 8, T1 6, others | Dominance only | `0x09d7e2cc`: dominance < 1 |
| limit | `check_copies` | 22 | 24 | A 6, B 7, G 7, C 3, E 1 | `ai_is_card_count_below` with other limits | `0x09d6ba44`: fewer than 2 copies on both sides |
| field | `check_field_spell` | 11 | 11 | A 8, B 3 | Field-spell zone | `0x09d72098` |
| graveyard | `check_graveyard` | 11 | 12 | B 5, T1 4, others | Graveyard counts | `0x09d703fc`: opponent has ≥ 2 Graveyard monsters (≥ 1 when committed) |
| phase | `check_phase` | 18 | 19 | T1 18, T2 1 | Turn player `0x09e2d1d8` and phase `0x09e2d1e8` only | `0x09d1d230`: not the controller's turn |
| committed | `check_committed` | 12 | 12 | D 5, B 4, G 2, A 1 | `ai_is_normal_spell_in_graveyard` shortcut plus own counts | `0x09d6fd3c` |
| board | `check_board` | 60 | 64 | T1 25, B 19, others | Named-card, monster, counter, hand counts | `0x09d21384`: card `0x1817` active on the own side |
| state | `check_rule_state` | 14 | 15 | T1 8, others | Rule flags, link fields or event codes, no call | `0x09d2f0dc`: the ctx event code is 3 |

Shape facts that a port needs (H, from the decompilation):

- Signature `int handler(ctx, arg)`: `ctx` is the 24-byte link built for the card (`chain.md`), `arg` the link being answered in a response window (0 outside one). Results ≥ 1 accept, 0 or −1 refuse; no decompiled single-use handler has a literal `return 2` (L: a computed 2 was not searched for), so the "≥ 2 for hand cards" threshold of `ai_evaluate_activation` probably makes those hand cards refuse under that flag.
- Recurring idioms: "own side" `ctx +2 bit 0`; "controller" that bit xor `ctx +3 bit 6`; "opponent's End Phase" = turn player ≠ own side and phase 5 (the usual timing of T1 cards that act at the end of the opponent's turn); event code `(u16 ctx +2 & 0xfff) >> 6`.
- Some handlers share one body: `0x09d70070`, `0x09d70084`, `0x09d70098`, `0x09d700ac` load a different constant (the most cards the effect may use: 1, or −1 for no limit) and fall into common code; Ghidra gives them a 1-byte body. They are separate table pointers and are named separately. `0x09d6b90c` (`ai_handler_check_targets_1668`) is a Ghidra thunk of `0x09ce9b54` (accept when the record's target mask, filtered by `ai_filter_target_mask`, is non-empty); the registry lists it as `thunk_…`, which `ai_tables.py` strips.
- 17 handlers write the AI scratch word `0x09e03068` (for example the number of cards to send for +500 ATK each in the body above), which the activation code reads afterwards; the handler is therefore not always side-effect free.

Porting: a family is a template (its dominant query); the member adds constants (card ids, thresholds) and at most one or two extra tests. The registry names point at the template, the decompilation of each member gives the constants.

## Simulation and scoring

Memory layouts of the AI runtime blocks (context stack, candidate stack, summon choice, stat snapshot, snapshot slots, battle plan, combat tricks, board view, step table) are in [`docs/formats/ai-runtime.md`](../formats/ai-runtime.md).

### State snapshots

The AI tests moves on the real duel state. `ai_simulate_attack`, `ai_plan_battle_with_tricks` and `ai_plan_battle` push a snapshot (depth `0x09e27fee`, at most 10) of the command/duel block `0x09e29914` (`0xc14` bytes) and the two player blocks `0x09e2a528` (`0x2de4` bytes) into slot `n` at `0x09dff93c + n × 0x39f8`, run rules code, then restore and re-run `ai_analyze_board` (H). The ten slots used (1–10, ending at `0x09e276e3`; see `docs/formats/ai-runtime.md`, which corrects the earlier range `0x09e03334`–`0x09e27ebc`) make up most of the 150 KiB region `0x09e02ff8` cleared by `duel_core_reset`.

### Battle plan

A plan is a `0x2e4`-byte record: the working plan at `0x09e276e4` and one saved per side at `0x09e279c8 + side × 0x2e4` (H for the copies). Its header is written by `ai_plan_init` (`0x09d0eeb8`) and `ai_plan_simulate_attacks` (`0x09d1329c`); "own" is the planning side (H for the writes, M for the meanings):

| Offset | Type | Meaning |
| --- | --- | --- |
| `+0x00` | u16 | Own monsters destroyed in the simulated battles |
| `+0x02` | u16 | Opponent monsters destroyed |
| `+0x04` | u16 | Own monsters left (`duel_core_count_monsters`) |
| `+0x06` | u16 | Opponent monsters left |
| `+0x08` | int | Plan value: total damage the planned attacks deal (sum of the battle evaluator's two damage words per attack); returned by `ai_get_plan_value` |
| `+0x0c` | int | Secondary score: sum of the evaluator's per-attack word `0x09e27fb8[defender]` (meaning open) |
| `+0x10` / `+0x14` | int | Own / opponent LP after the attacks (start: the player blocks' LP) |
| `+0x18` | s16 | Battle dominance after the attacks (`ai_eval_battle_dominance(side, 0, 1)`) |
| `+0x1a` | u16 | Slot mask of monsters with special attack rules (`ai_plan_prepare_attack_state`) |
| `+0x1c` / `+0x1e` | s16 | Own / opponent deck size after the attacks (cards milled by battle subtracted) |
| `+0x20` | u16 | Combat-trick card the plan assumes (0 = none): `ai_plan_battle_with_tricks` passes the trick list entry `0x09d1cb10(i)` through `ai_build_battle_plan` to `ai_plan_init` |
| `+0x22` | u16 | 1 when the attacks win the duel (opponent LP < 1, or deck < 1 while it had cards) |
| `+0x24` | 5 × 32 bytes | Per-monster attack entries: `+0x02` attacks planned, `+0x04` destroyed an opposing monster, `+0x06`, `+0x0a` flags of that destruction, `+0x08` the attacker was destroyed, `+0x0c` cannot attack (Defense Position or `0x09d3996c`), `+0x0e` target (5 = direct / none), `+0x14` mask of slots destroyed, `+0x18` damage, `+0x1c` evaluator score |
| `+0xc4` | 4 × 32 bytes | Extra entries (`+0x00` = the slot, `0xffff` = unused). `ai_plan_get_attack_entry(plan, slot)` (`0x09d1c8e0`) returns `plan + 0x24 + 32 × slot`, or the extra entry of that slot when bit 29 of the turn player's slot flags word (`+0x10`) is set (H for the address computation; "monster with an additional attack" is a hypothesis, L) |

`0x09e2782a` (plan `+0x146`) is the chosen attacker slot + 1, also read by the battle check.

- `ai_plan_battle(side, mode, flag)` (`0x09d16568`): `mode = -1` full plan for the turn player, `-2` hypothetical (forces phase 2), `≥ 0` a given monster. Calls `ai_plan_battle_with_tricks`, then evaluates the result (`0x09d0afd0`) and, if the opponent is the turn player's AI side, also plans the opponent's best reply with Alligator's Sword-style checks (`0x09cfca08`).
- `ai_plan_battle_with_tricks` (`0x09d15b58`): builds the base plan (`ai_build_battle_plan` `0x09d1586c` → `0x09d0eeb8`, `0x09d12a24`, `0x09d1329c`), then replays it once for each **combat trick** listed at `0x09e27ff8` (up to 8 card ids, filled by `ai_analyze_board` with Battle Fusion, Shield & Sword and Limiter Removal when they can be used) and keeps the better plan (`ai_compare_plans` mask `0x1e`, `0x10` for Limiter Removal).
- `ai_compare_plans(a, b)` (`0x09d36d4c`): not a lexicographic order but a mask of independent criteria in which `a` beats `b`; the caller keeps `a` when `mask & wanted ≠ 0`. Exact logic (H, from the disassembly) and field meanings (M) are in "Decision pipeline" below.
- `ai_choose_attack_target(side, slot, …)` (`0x09d0ca3c`): tries the direct attack (target 5) and each opposing monster, starting at a random slot (`duel_core_random(5)`), skipping targets already flagged in `0x09e27ff4`, scoring with `0x09d06188` (17,700-byte battle evaluator) and keeping the best by `0x09d0c2e4`.

### Battle dominance

`ai_eval_battle_dominance(side, slot_mask, simulate)` (`0x09d37548`, H for the formula): compares each side's best attacker (`0x09cf5c3c`; with `simulate`, only monsters that can actually win a battle, tested with `0x09d30ef0`) and returns +4 (our best beats theirs with ≥ 2,000), +2 (beats with less), −2/−4 symmetrically, −1 when our simulated best is weaker than our nominal best, 0 otherwise; `slot_mask` temporarily removes cards. `ai_analyze_board` caches it per side at `0x09e28008 + side × 0x30c` (simulated) and `+2` (plain); `ai_get_battle_dominance(side)` (`0x09d37490`) reads the cache (or recomputes under flag `0x09e03070 & 0x20`). A negative value switches on the comeback table D and changes many handlers.

### Summon choice

`ai_choose_normal_summon` (`0x09d1bb24`) simulates each hand monster (`0x09d177e0` plans the battle with the monster added) and rates it with `ai_rate_summon_candidate` (`0x09d1b338`). The rating is a tier plus a stat tie-breaker, kept in the 12-byte choice record at `0x09e03080` (`s8` hand index, …, `+3` from field, `+4` set face-down, `+6` u16 card needing special handling): tier 5 tribute summon that beats the tributes, 4 stronger than the opponent's best, 3 positive card-specific value (`0x09d1aec0`), 2 stronger than the previous best, 1 anything summonable; the stat is ATK, DEF or the larger, depending on the position. `ai_execute_summon` (`0x09d92afc`) picks tributes (`0x09cf4288`, `0x09cf4588`) and issues the summon (`0x09da5774`). `ai_choose_special_summon` (`0x09d92d5c`) is a compare chain over hand monsters that can be special summoned, with per-card conditions (about 40 card ids).

### Target choice

`ai_choose_target_by_card(ctx, ctx2, card, slot_mask, mandatory)` (`0x09d608d4`, 16 KiB, H): two generic pre-checks (`0x09d605c8`, `0x09d60760`), then a compare chain of 131 card ids with dedicated choosers, then generic fallbacks. Returns `side | slot << 8` or −1. Generic pickers (H): `ai_pick_monster_by_stats(side, mask, atk_sign, def_sign)` (`0x09d4a5c0`, best/worst ATK or DEF, +1 for monsters that can attack) and `ai_pick_slot_by_score(side, mask, score_fn)` (`0x09d4a9cc`); both shuffle the candidates first, so ties break randomly. `ai_choose_target_as_controller` (`0x09d64b18`) runs the chooser with the view side set to the card's controller; `ai_decide` (`0x09d649ec`) tries the mandatory then the optional variant and applies the choice (`0x09cbed3c`).

## Decision pipeline (reimplementation spec)

Every CPU decision runs through the same pipeline. Confidence per step; "H" steps are read from the code (decompilation, disassembly where noted), "M" steps have a clear code basis but one uncertain reading, "L" steps are structural only. Nothing here has been traced in PPSSPP.

1. **Hand-off (H).** A phase handler or prompt sees `0x09e02998[side] == 1` and calls an AI wrapper instead of the human UI; the wrapper calls `ai_push_context(side, view, replan)` and stores the answer where the human answer would go (`0x09e2d248` for prompts). Nested AI questions push further frames.
2. **View (M).** `ai_analyze_board(view)` rebuilds the per-side block `0x09e28008 + side × 0x30c`: cached battle dominance (`+0` simulated, `+2` plain), slack `+4`, rule flags `+8`, and the table of 32 **interest records** at `+0x0c` (24 bytes each, built by `ai_board_note_card_interests` `0x09d8fc24` and `ai_board_note_combo_interests` `0x09d91d30`, compare chains on the cards the side holds, through `ai_board_add_interest_record`; the record is a card id at `+4` plus flag bytes, merged by equality with a u16 weight at `+0`). Face-down opposing cards are replaced by stand-ins (`ai_mask_hidden_card_id`, H). The interest records are read by the handlers' "wanted card" tests (meaning of the flag bytes L).
3. **Battle plan (H for the sequence).** `ai_replan_turn_player()` → `ai_plan_battle(turn player, −1, 1)`:
   1. Push a snapshot (depth `0x09e27fee` ≤ 10): `0xc14` bytes from `0x09e29914` and `0x2de4` bytes from `0x09e2a528` into slot n (`0x09dff93c + n × 0x39f8`, player part at `0x09e00550 + n × 0x39f8`); then `0x09d0e7b4(0)` and `duel_effects_update_negated_slots(1)`.
   2. `ai_plan_battle_with_tricks(side, mode, 0, flag, mode == −2)`: build the base plan with `ai_build_battle_plan`, save it (header, `0x09e27708` attack entries, `0x09e277a8` extra entries, `0x09e27828` state) as *best*; then for each combat trick `t` in the list read by `0x09d1cb10(i)` (filled by `ai_analyze_board` from Battle Fusion, Shield & Sword, Limiter Removal … that can be used): restore the snapshot, rebuild the plan with `t` as `+0x20`, compute `m = ai_compare_plans(new, best)` and keep the new plan when `m & mask ≠ 0` with `mask = 0x10` for Limiter Removal (`0x1409`) and `0x1e` otherwise.
   3. `ai_build_battle_plan(side, mode, from, trick, flag, full)`: `ai_plan_init`; if own LP (`+0x10`) > 0, own deck (`+0x1c`) ≥ 0 and `duel_core_can_enter_battle_phase(side)`: `ai_plan_prepare_attack_state` (attack restrictions per card), set the phase word `0x09e2d1e8` to 3 (Battle Phase; old value pushed on a 4-entry stack `0x09e27fe4`), `ai_plan_simulate_attacks(side, mode)`, restore the phase.
   4. `ai_plan_simulate_attacks` (M): for each attacker, `ai_choose_attack_target` (`0x09d0ca3c`) tries the direct attack (target 5) when allowed, then each opposing monster starting from a random slot (`duel_core_random(5)`), skipping targets flagged in `0x09e27ff4`; each candidate is pre-checked (`0x09d0a6ac`), evaluated by `ai_eval_attack(side, slot, target, mode, &result)` (68-byte result) and kept when `ai_is_better_attack_result(side, result, best, flag)`; the chosen attack is applied to the simulated board (destroyed monsters removed with `ai_sim_clear_slot_card`, LP and deck counts reduced, counters `+0`/`+2` incremented), and the header is finished with the monster counts, `+0x08` total damage, `+0x0c` total score and `+0x18` the new dominance.
   5. `0x09d0afd0(side, −1, mode)` reviews the plan (opposing lock cards such as `0x1eaf`, `0x1842`); the outer loop repeats steps 1–4 until it returns non-zero (H for the loop, L for the purpose). An accepted full plan (`mode = −1`) is copied to `0x09e279c8 + side × 0x2e4` and `0x09e27ff0 = 1` (plan valid; `ai_get_plan_value` re-plans when it is 0).
   6. When `side` is the AI side, the opponent's reply is planned the same way from the AI's plan (`ai_build_battle_plan(opponent, 1, ai_plan, 0, 1, 1)`, LP and deck counts taken crosswise) with the view switched to the opponent, and saved in the opponent's slot (H for the calls, M for "reply").
   7. Pop the snapshots and rebuild the view (`ai_analyze_board(view)`).
4. **Scoring a card (H).** The main-phase steps and the response windows walk the priority tables in order; for each entry whose card is available, `ai_evaluate_activation(entry, ctx, arg, commit)` applies the locks and the LP guard (`ai_estimate_lp_change`: refuse a cost that kills, accept at once an effect that wins) and calls the handler; ≥ 1 accepts (≥ 2 for hand cards under `0x09e28010 & 0x100`). The first accepted entry is activated; the step is then re-run. Handlers score with the shared queries (`ai-helpers.md`) and the plan (`ai_get_plan_value`, `ai_get_planned_attacker`, `ai_compare_plans`).
5. **Summons (M).** `ai_choose_normal_summon` simulates each hand monster on the board (`0x09d177e0`: plan with the monster added) and ranks by the tier of `ai_rate_summon_candidate` (5 beats the Tributes, 4 beats the opponent's best, 3 card-specific bonus, 2 beats the previous best, 1 summonable), ties by ATK/DEF.
6. **Targets and choices (H).** `ai_choose_target_by_card` (per-card compare chain, generic pickers with random tie-breaks); hidden-card stand-ins; expected stats of cards off the field from `ai_estimate_card_atk` / `ai_estimate_card_def`.
7. **Plan comparison (H for the logic, M for the field meanings).** `ai_compare_plans(a, b)` exactly:

   ```c
   uint ai_compare_plans(plan *a, plan *b) {
       if (a->own_lp <= 0 && b->opp_lp > 0) return 0;      // +0x10, +0x14
       if (a->own_deck <= 0 && b->opp_deck > 0) return 0;  // +0x1c, +0x1e (s16)
       uint m = 0;
       if ((a->opp_lp <= 0 && b->own_lp > 0) || (a->opp_deck <= 0 && b->own_deck > 0)) m |= 0x10;  // a wins
       if (a->opp_monsters < b->opp_monsters) m |= 0x08;   // +0x06 (u16)
       if (a->opp_lp < b->opp_lp) m |= 0x04;
       if (a->score > b->score) m |= 0x02;                  // +0x0c
       return m;
   }
   ```

   The guards compare `a`'s own values with `b`'s opponent values (and the 0x10 test `a`'s opponent with `b`'s own). Read literally, "a loses and b does not win → not better" and "a wins and b does not lose → better". Whether this crossing is intended or a slip in the original source is open; a port should keep it until a trace shows otherwise. Callers combine the bits with a mask, so the order is not lexicographic: with `0x1e` a trick plan that leaves one more opposing monster but deals more damage is still taken.

### PPSSPP checks for the plan comparison

These confirm step 3 and step 7 (breakpoints on runtime addresses; `rel_duel_eng` must be loaded at `0x09be1400`):

1. **Header meanings.** Break at `ai_compare_plans` `0x09d36d4c` during a CPU battle phase with a combat trick in the CPU's hand (Limiter Removal or Shield & Sword). Dump 0x28 bytes at `a0` and `a1`; expect `+0x10`/`+0x14` = the two players' LP minus the planned damage, `+0x1c`/`+0x1e` the deck sizes, `+0x20` the trick card id in `a0` (0 in the base plan). Log `v0` at `0x09d36e00`.
2. **Mask use.** In the same run, step out to `0x09d15b58`'s caller site after `ai_compare_plans` and check that the new plan replaces the saved one exactly when `v0 & 0x1e` (or `& 0x10` for `0x1409`) is non-zero, then compare with the trick the CPU actually activates.
3. **The crossed guards.** Prepare a board where the trick plan makes the CPU lose (own LP ≤ 0) while the base plan leaves the opponent alive; confirm `v0 = 0`. Then a board where the trick plan wins and the base plan does not: expect bit `0x10`.
4. **Plan value.** Break at the return of `ai_plan_simulate_attacks` (`0x09d1329c`, `jr ra`) and of `ai_get_plan_value` `0x09d16a84`; compare `v0` with the battle damage actually dealt in the following Battle Phase (`+0x08` should equal it when the CPU follows the plan).
5. **Snapshots.** Watch `0x09e27fee` (depth) and the LP word `0x09e2a528` across `ai_plan_battle` `0x09d16568`: the depth returns to its entry value and the LP are unchanged after the call.
6. **Target choice.** Break at `ai_is_better_attack_result` `0x09d0c2e4` and log which target index wins; compare with the attack the CPU declares (`0x09e2863c` attacker slot, the target of the battle command).
7. **Interest records.** After `ai_analyze_board`, dump `0x09e28014 + side × 0x30c` (32 × 24 bytes) with a known combo card in hand (for example a card that `ai_board_note_card_interests` tests, such as `0x1c31`) to read the record layout.

## Board view (what the AI knows)

`ai_analyze_board(view_side)` (`0x09d91fe8`, M) rebuilds, for both sides, a 0x30c-byte block at `0x09e28008 + side × 0x30c`: dominance values, `+4` a slack value (`0x80 − x`, or `2 −` the hand size under Summon Limit), `+8` flags (`0x09e28010`: bits for "opponent cannot draw", Necrovalley, King Tiger Wanghu, Cocoon Veil-like slots, By Order of the Emperor, Witch Doctor of Sparta, Dark Cure, Thunder King Rai-Oh, Sanguine Swamp …), and at `+0x0c` a table of 32 interest records (24 bytes each, `ai_board_add_interest_record`) filled by `ai_board_note_card_interests` (`0x09d8fc24`, a compare chain on each card of the 11 field slots, the hand and the extra deck) and `ai_board_note_combo_interests` (`0x09d91d30`). **The opponent's hand is only registered for cards that are revealed** (`0x09c038a8`); the AI's own hand is always registered (M: the branch is clear, the meaning of `0x09c038a8` is inferred). Global rule flags go into `0x09e03070` (Kotodama, Remove Brainwashing, Gaap the Divine Soldier). The AI context: `0x09e02ff8` AI side, `0x09e02ffa` view side, stack of 8-byte frames at `0x09e03028` with depth `0x09e03026` (`ai_push_context`).

## Randomness

`duel_core_random(n)` (`0x09dca4ac`, H) is a linear congruential generator: `seed = seed × 0x343fd + 0x269ec3` at `0x09e2d1cc`, result `n × ((seed & 0x7fffffff) >> 16) >> 15`, i.e. `0 ≤ r < n`. The seed is copied from `0x09e02990` at duel start (`0x09dc7dc4`); `0x09e02990` is therefore the duel's RNG seed set by the caller through `0x09be1878`, not a per-duelist value as `tag_duel.md` assumed. 100 functions call it, most of them AI tie-breaks; deck shuffling uses it too (`duel_core_load_deck`).

## Personality and tag partners

- **No AI parameter interface found in the duel engine** (M). The exported setters at `0x09be1840`–`0x09be1df4` cover turn, seed (`0x09e02990`), local side (`0x09e02994`), duelist kinds, first player (`0x09e029a8`), `0x09e02cb0`, `0x09e02cb4` (read by `0x09be3bc0`, not by AI code) and the LP mode `0x09e02cac` (8000/4000/2000/1000 LP). No AI function reads a per-duelist weight, level or character id.
- **Character table** (`BOOT.BIN 0x088aa510`, 174 × 148 bytes): besides the fields in `docs/formats/sound.md`, it holds per-character byte groups at `+0x44`–`+0x48` (5 bytes), `+0x49`–`+0x51` (9 bytes) and eight words at `+0x58`–`+0x74`, identical across a character's variants and with AI-like values (0x32, 0x64, 0x0a, −5, −10). Their accessors `BOOT 0x0885b4ac`, `0x0885b4fc`/`0x0885b56c`, `0x0885b5dc` are exported but called by none of the loaded modules (`rel_duel_eng`, `rel_duel_draw`, `rel_duel_mgr`); hypothesis (L): they serve the free-roam or friendship code in a module not yet imported, not the duel AI. Words `+0x78`–`+0x82` are card ids (favourite cards, read by `0x0885b664` from `rel_duel_draw 0x0983fe50`, presumably for cut-ins).
- **Tag partner**: the CPU partner uses exactly the same code. At each turn change `tag_duel_swap_active_duelist` copies the incoming duelist's kind into `0x09e02998[side]`, and every AI call keys on the side, so a CPU partner is just a CPU side for its turns (H for the mechanism). The AI has no notion of the waiting partner's hand.

## Key functions

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x09d9da30` | `ai_push_context(side, view, replan)` | H | Pushes `(side, view, replan)` on the stack at `0x09e03028`; rebuilds the view and re-plans when they change; 28 callers, all entry wrappers. |
| `0x09d91fe8` | `ai_analyze_board(view)` | M | Writes the per-side blocks at `0x09e28008`; 54 callers. |
| `0x09d16afc` | `ai_replan_turn_player()` | H | `0x09e27ff0 = 0; ai_plan_battle(turn side, -1, 1)`. |
| `0x09d16568` | `ai_plan_battle(side, mode, flag)` | M | See "Battle plan". |
| `0x09d15b58` | `ai_plan_battle_with_tricks(…)` | M | Loops over `0x09e27ff8`, compares with `ai_compare_plans`. |
| `0x09d1586c` | `ai_build_battle_plan(side, mode, from, trick, flag, full)` | M | `ai_plan_init`, then (LP, deck and Battle Phase allow it) `ai_plan_prepare_attack_state` and `ai_plan_simulate_attacks` with the phase forced to 3. |
| `0x09d0eeb8` | `ai_plan_init(side, full, from_plan, trick)` | H | Plan header and attack entries reset (table "Battle plan"). |
| `0x09d12a24` | `ai_plan_prepare_attack_state(side, …)` | L | `duel_core_init_battle_phase_attack_state`, per-card attack rules, mask `+0x1a`. |
| `0x09d1329c` | `ai_plan_simulate_attacks(side, mode) → damage` | M | Writes the header fields `+0x00`–`+0x18`; returns `+0x08`. |
| `0x09d06188`, `0x09d0c2e4` | `ai_eval_attack`, `ai_is_better_attack_result` | M/L | 68-byte attack result record; comparator of two results. |
| `0x09d36d4c` | `ai_compare_plans(a, b) → mask` | H | Exact logic in "Decision pipeline"; 19 callers. |
| `0x09d16a84` | `ai_get_plan_value(side)` | M | Plans if needed, returns plan `+0x08`; 23 callers. |
| `0x09d16c4c` | `ai_simulate_attack(side, slot, …)` | M | Snapshot, `ai_choose_attack_target`, restore. |
| `0x09d0ca3c` | `ai_choose_attack_target(side, slot, …)` | M | Direct attack then 5 targets from a random start. |
| `0x09d37548` | `ai_eval_battle_dominance(side, mask, simulate)` | H | Formula above. |
| `0x09d37490` | `ai_get_battle_dominance(side)` | H | Cached value; 129 callers. |
| `0x09d9db38` | `ai_main_phase()` | H | Wrapper of `ai_main_phase_step`; caller main-phase handler `0x09de0240`. |
| `0x09d953b4` | `ai_main_phase_step()` | H | Step table `0x09e01ba4`. |
| `0x09d8b184` … `0x09d8cfbc` | `ai_main_state_*` | M/L | Steps 0–6, table above. |
| `0x09d894e8` | `ai_try_table_entry(side, entry, mode)` | H | 9 callers. |
| `0x09d88c34` | `ai_evaluate_activation(entry, ctx, arg, commit)` | M | Calls `entry +4`. |
| `0x09d8923c` | `ai_is_activation_blocked(ctx)` | M | Lock cards. |
| `0x09d306b0` | `ai_activate_from_table(ctx, arg, entry, mode)` | M | Evaluates, then issues the activation command `0x09dcf950(…, 3)`. |
| `0x09d8f0c4` / `0x09d8efc0` | `ai_table_length` / `ai_table_entry` | H | Table sizes above. |
| `0x09d3023c` | `ai_chain_table_length(side, table, flag)` | M | T1–T3 sizes. |
| `0x09d8c1e8`, `0x09d8c280`, `0x09d8c300`, `0x09d8c508` | `ai_try_summon_enablers`, `ai_try_comeback_cards`, `ai_try_battle_cards`, `ai_try_main_cards` | M | Walk tables C, D, E/F, B; `ai_try_main_cards` also changes battle positions (`0x09dcf950(side, slot, 0, 5/8/9)`). |
| `0x09d1bb24`, `0x09d1b338`, `0x09d92afc`, `0x09d92d5c` | summon choice and execution | M | See "Summon choice". |
| `0x09d9ec64` | `ai_battle_choose_attacker(side)` | M | `0x09d16c0c` gives the attacker slot (`0x09e2863c`) or −1 → leave battle (`0x09e2d220 = 0xb`). |
| `0x09d9edc8` | `ai_battle_decide_attack(side, slot)` | L | Wrapper of `ai_simulate_attack`; answer feeds prompt `0x09dc725c`. |
| `0x09d9efcc`, `0x09d9903c`, `0x09d95f5c` | yes/no chain | M | Prompt kind 2. |
| `0x09d9e024`, `0x09d2fd80` | chain response | M | Tables T1–T3; mode `0x09e0307c` (0/1/2) set from cards that punish chaining. |
| `0x09d608d4` | `ai_choose_target_by_card(…)` | H | 131 card cases. |
| `0x09d64b18` | `ai_choose_target_as_controller(ctx, …)` | M | 75 callers. |
| `0x09d4a5c0`, `0x09d4a9cc` | generic pickers | H | Shuffle then best by stat or callback. |
| `0x09d6b6b8`, `0x09d6b6c0`, `0x09d6ba6c` | `ai_cond_always`, `ai_cond_never`, `ai_cond_has_target` | H/H/M | Shared handlers. |
| `0x09dca4ac` | `duel_core_random(n)` | H | LCG above. |
| `0x09ce536c`, `0x09ce9c64`, `0x09ce767c`, `0x09ce9da0` | `ai_estimate_card_atk(side, location, card, mode)`, `ai_estimate_off_field_atk(side, card)`, `ai_estimate_card_def`, `ai_estimate_off_field_def` | H/H/M/M | Expected ATK (DEF) of a card, with ~100 per-card cases and field-spell bonuses; the DEF pair has the same entry shape (first call `card_db_get_def`) and was not read in full. |
| `0x09d8fb44`, `0x09d8fc24`, `0x09d91d30` | `ai_board_add_interest_record`, `ai_board_note_card_interests`, `ai_board_note_combo_interests` | H/M/L | Interest records of the board view. |
| `0x09d3ba48` | `ai_find_candidate_index_by_card(card)` | H | First unselected, unvetoed candidate of that card. |
| `0x09cf5d94`, `0x09cf5f64`, `0x09cf5e40` | `ai_get_best_visible_battle_stat`, `ai_find_best_monster_slot`, `ai_get_best_monster_value` | H | Best monster by visible ATK/DEF. |
| `0x09d48908` | `ai_simulate_candidate_pick(ctx, side)` | M | Builds the candidate list (kind 6) and returns the index the AI would pick, or −1. |
| `0x09d37b70`, `0x09d6ba50` | `ai_get_effective_hand_limit`, `ai_can_controller_enter_battle` | H | Small queries used by the handler families. |
| `0x09dc9d24`, `0x09dc9ce8`, `0x09dca314` | `duel_core_get_candidate_count`, `…_entry`, `…_selection` | H | Candidate list at `0x09e29920`/`0x09e29928`, per-candidate state `0x09e2a128`. |
| `0x09cc0cdc`, `0x09cc0bd8`, `0x09d9ddfc`, `0x09d649ec` | `duel_effects_choose_targets`, `…_ui`, `ai_choose_targets`, `ai_decide` | H/H/M/M | Earlier entry point (target choice in effect slot `+0x14`). |

### Documented signatures

The following are recorded in `re/documented-duel_eng.tsv` (purpose, side effects and callers above):

- `ai_get_battle_dominance(int side) → int`: no side effects; 129 callers (main-phase steps, handlers).
- `ai_table_length(int side, void *table) → int`, `ai_table_entry(int side, void *table, int i) → void *`: no side effects (they read `0x09e03078`, `0x09e2d1e8`); callers `ai_try_*`, `0x09d307c4`, `0x09d309b0`, `0x09d41050`, `0x09d8b38c`.
- `ai_pick_monster_by_stats(int side, uint mask, int atk_sign, int def_sign) → int slot`: advances the RNG; 12 callers including `ai_choose_target_by_card`.
- `ai_pick_slot_by_score(int side, uint mask, code *score) → int slot`: advances the RNG; 10 callers.
- `ai_push_context(int side, int view, int replan)`: pushes a frame, may rebuild the view and plan; 28 callers.
- `duel_core_random(int n) → int`: advances x.
- `ai_cond_always()`, `ai_cond_never()`: constant 1 / 0; referenced only from the tables.
- `ai_compare_plans(void *a, void *b) → uint`, `ai_plan_init(int side, int full, void *from_plan, int trick)`: logic in "Decision pipeline"; the second writes the working plan `0x09e276e4` and sets `0x09e27ff2` when `full`.
- `ai_estimate_card_atk(int side, int location, uint card, uint mode) → int`, `ai_estimate_off_field_atk(int side, uint card) → int`: pure; 33 and 45 callers (choosers, vetoes, per-card handlers).
- `ai_find_candidate_index_by_card(uint card) → int`, `ai_board_add_interest_record(int side, void *record, int weight) → int` (writes the side's interest table), `ai_get_best_visible_battle_stat(int side)`, `ai_find_best_monster_slot(...)`, `ai_get_best_monster_value(...)`, `ai_get_effective_hand_limit(int side)`, `ai_can_controller_enter_battle(void *ctx)`: pure apart from the noted write; callers in `re/documented-duel_eng.tsv`.
- `duel_core_get_candidate_count()`, `duel_core_get_candidate_entry(int i)`, `duel_core_get_candidate_selection(int i)`: pure accessors of the candidate list.

## Function families named in the 2026-10-31 round

Basis and method: `system.md`, same section. 577 new `ai` names in `rel_duel_eng`, mostly M (the role comes from callers and callees).

| Family | Count | Evidence |
| --- | --- | --- |
| `ai_card_choosers` | 148 | `ai_choose_target_for_<id>`, `ai_choose_cost_for_<id>` and their `ai_score_*_for_<id>` scorers: the card-id branches of `ai_choose_target_by_card`, `ai_choose_cost_by_card` and `ai_choose_hand_card_by_card` (from `card_refs`) say which card each callee serves. Shared choosers by effect kind (counters, position change). |
| candidates and slots (`ai_candidate_scores`, `ai_candidate_pickers`, `ai_slot_filters`, `ai_slot_pickers`, `ai_zone_choice`) | 130 | Score and filter callbacks of the candidate list and of slot masks; `0x09d440d8` is `ai_choose_candidate_by_card`; zone order table `0x09dfd2b4`/`0x09dfd2c8`. |
| board and rating (`ai_board_queries`, `ai_card_rating`, `ai_card_lists`, `ai_card_evals`, `ai_card_filters`, `ai_board_interests`, `ai_board_view`) | 102 | Board queries, card ratings, card-id lists (`ai_is_card_in_list_<id>`: true about the code, not about the purpose). |
| `ai_simulation`, `ai_battle_plan`, `ai_lp_estimate` | 35 | `ai_push_state_snapshot`/`ai_pop_state_snapshot` (`0x09d0ea9c`/`0x09d0edf8`, H); `ai_sim_battle_resolve` (`0x09d30ef0`), results at `0x09e27fd4`/`0x09e27fd8`; the battle-trick list at `0x09e27ff8`. |
| `ai_tribute`, `ai_tribute_filters`, `ai_summon`, `ai_summon_filter`, `ai_summon_choice`, `ai_position` | 47 | `ai_get_required_tribute_count` (`0x09cf4288`), `ai_choose_tributes` (`0x09cf4588`). Summon option mask (`0x09d3b3e8`): `0x10` Attack Position, `0x40` Defence; `0x04` and `0x20` unknown (kept numeric in the names). The summon choice stores the hand index in `0x09e03080`. |
| `ai_answers`, `ai_declarations`, `ai_main_loop`, `ai_conditions` | 63 | `ai_push_context` wrappers, answers to coin, number, maintenance and dialogs 6/7/8/11, Type/Attribute declarations, the main loop. |

Findings to reconcile:

Settled on 2026-10-31 (round 2):

- `0x09d30dc8` → **named `ai_get_relative_atk_bonus` (M), `ai-helpers.md` corrected.** It is not "the opponent's attacker would win": it returns 100 for The Wicked Avatar (`0x1bb3`, unless slot flag `0x100` is set), the target's visible ATK when Clear Vice Dragon (`0xec2`) is the attacker, else 0. Callers: `ai_eval_attack` and three AI handlers.
- `0x09cec59c` `ai_can_best_attacker_beat_a_monster` → **kept; the code is confirmed and differs from `0x09cec388`.** Both functions use the same stats frame (`duel_core_get_card_stats` out `+0x18` ATK, `+0x1c` DEF, `stat-modifiers.md`) and the same slot `+0x06` (0 = Attack Position, H in `duel_core.md`). `ai_can_boost_win_battle` (`0x09cec388`) compares ATK in Attack Position and DEF in Defence Position, as the rules do; `0x09cec59c` does the opposite (DEF for an Attack Position monster, ATK for a Defence Position one). So the original AI misjudges this case; a faithful port should keep it. To confirm in PPSSPP (one breakpoint on `0x09cec59c` with a monster in each position).
- Dialog 8 (`0x09dc79c0`) → **prompts table corrected**: the function is `duel_core_ask_summon_position` and it passes fields of the summon record `0x09e290bc` (`summon.md`). The main-loop row now calls `0x09d899a8` `ai_try_hand_special_summons`.
- Morphtronic Datatron → **renamed, no reversal.** `0x09d8e848` runs only for a monster in Defence Position (`+0x06 != 0`) and `0x09d8eb68` only for a face-up Attack Position monster; each evaluates what the monster gains from a **position change**: changed to Attack Position, Crass Clown (Defence→Attack trigger) and Datatron's 600 damage; changed to Defence Position, Dream Clown and Blade Rabbit (Attack→Defence triggers), Datatron's 300, Morphtronic Clocken, Yubel. That matches the card text. Now `ai_eval_change_to_attack_position` and `ai_eval_change_to_defense_position` (M); callers `ai_try_main_cards` (position changes).

## Round 2 of the 2026-10-31 naming

Method as in the first round (`system.md`): the still-unnamed functions were re-dumped from Ghidra with the current names, read in packs with full bodies (up to 160 lines), and named H/M with a basis in `re/names*.csv` under "round 2". 95 new `ai` names in `rel_duel_eng` (M except a few H). The "truncated inner parts" of `ai_eval_attack` (`0x09d06188`) are separate helpers, not mis-split code: the function boundary is correct. They work on a 68-byte attack result with one block per side at `+0x14 + side·0x18` (`+0x16` destination of the destroyed card, `+0x20` battle damage, `+0x24` LP loss by effects, `+0x28` value lost) plus the destroyed mask `+0x0e`, a flag `+0x06` and the result class `+0x02`: `ai_attack_result_get_destroyed_destination` (`0x09d1c99c`), `ai_attack_result_add_card_lp_change` (`0x09cfe484`), `ai_attack_result_add_chosen_targets` (`0x09cfe5f8`), `ai_attack_result_add_side_losses` (`0x09d04a88`), `ai_eval_destroyer_battle_effects` (`0x09cfe7c8`), `ai_eval_destroyer_graveyard_effects` (`0x09cff044`, only when the destination is `0x0e`), `ai_eval_destroyed_monsters_effects` (`0x09d01288`), `ai_eval_battle_card_effects` (`0x09d015b8`), `ai_eval_battle_damage_effects` (`0x09d050b0`), `ai_rate_monster_loss_value` (`0x09d0457c`), `ai_sim_redirect_attack_to_slot` (`0x09d04914`: Dreamsprite, White Night Dragon, Amber Mammoth) and `ai_is_attack_trade_favorable` (`0x09d05734`). Other families: per-card choosers and scorers (21), summon choice and filters (17; five per-card veto chains carry generic `_a`…`_d` suffixes because only their card list tells them apart), attack-declared responses (5). Several AI handler stubs are 8-byte entries that load an argument and jump into a shared body (`0x09d76574`, `0x09d7e92c`, `0x09d6de24`), as `ai-helpers.md` describes.

## Documented functions

The functions of this group that reached the `documented` stage in the 2026-10-31 documentation round (prototype, purpose, return value, side effects and callers, read from the decompilation) are listed in [`functions/ai.md`](functions/ai.md), extended in the 2026-11-03 round.

## Functions documented in the 2026-11-03 round (work packages 6-7)

Method: every still-undocumented `ai` function of `rel_duel_eng` (827) was re-dumped from Ghidra with the current names and read in full, one row per function; the eight largest per-card dispatchers were read by dedicated readers and the rest in five address-ordered bands. Forwarders whose register arguments (`t0`-`t3`, PSP EABI) the decompiler hides were read from the disassembly. Full rows: [`functions/ai.md`](functions/ai.md). Findings by reading batch follow.

### Findings from the per-card target, candidate and position choosers

Basis: full read of the Ghidra decompilations of `ai_check_card_condition` (`0x09cee284`, 11,976 bytes), `ai_choose_candidate_by_card` (`0x09d440d8`, 14,528 bytes) and `ai_choose_target_by_card` (`0x09d608d4`, 16,252 bytes). All three are hand-written `if`/`else` compare chains on a card id (Ghidra shows no `switch`; the two 7-word jump tables at `0x09dfe4c8` mentioned in ai-tables.md belong to small internal switches, e.g. the `0x1b33`-`0x1b38` counter inside the `0x1c9b`/`0x1be9` case). None is VFPU code. Nothing was traced in PPSSPP.

Distinct card-id constants compared against the dispatch argument (counted mechanically from the decompilation, H): 202 in `ai_check_card_condition` (effect-helpers-misc.md says 209 cases; the difference may be ids compared through other variables), 235 in `ai_choose_candidate_by_card` (ai-tables.md / effect-helpers-misc.md say 240), 386 in `ai_choose_target_by_card` plus 18 more compared on the ctx card id inside one branch. ai.md's "131 card ids" for the target chooser counts branches, not ids: many branches test groups of 2-90 ids.

#### ai_check_card_condition (summon position per card)

Signature (M): `int ai_check_card_condition(int side, uint card_id, int flag, int context_card)`; result 0 / 1 / -1.

- Meaning of the result (M): -1 = no card-specific answer. The only caller that is documented, `ai_eval_hand_card_condition`, simulates the summon and calls `ai_choose_monster_position` when it gets -1, so 0/1 are positions. 1 comes from `ai_wants_set_flip_monster` (flip monsters want to be Set) and from cards that do nothing face-up (e.g. `0x1ea6` when there is no race-2 monster in the Graveyard); 0 from cards whose effect wants them face-up (e.g. `0x1ec2` when it has candidates to bring, `0x1d78` when a target exists). Reading: 0 = face-up Attack Position, 1 = Set / Defense Position.
- Structure: (1) `safe = ai_survives_attacks_with_monster(side, -1, card)`; (2) global gates (Battle Phase + field effect `0x1669` → 1; the low-level Normal Monster swarm test with `0x17a8`; opposing `0x1eda` / `0x1e37` locks; `context_card == 0x1a13`); (3) `flag` forced to 1 while `0x135d` is active anywhere (`duel_core_count_active_card`); (4) `ai_is_card_in_list_1dbd` cards → 0 when `flag` or `safe`; (5) the per-card chain; (6) a common tail for cards that got no decision (Fusion vs. opposing `0x1b40` → 1; Elemental Hero checks → 0; `0x142a` combat-trick check with `ai_is_ranked_card_with_low_atk` → 0; flip monster → 1; level-lock (`ai_is_slot_blocked_by_level_lock`) → 0; else -1).
- `flag`: most card cases only apply when it is 0, so it means "the card-specific face-up reasons do not apply" (L for the meaning; the caller passes its own `arg`). Card `0x135d` forces it (L: a card that prevents or changes summons/flip; not checked).
- `context_card` (4th argument): compared with `0x1a13` and `0x1ec2`, and used as a boolean for `0x1cfe`, `0x14ac`, `0x1e86`, `0x1e80`, some groups. `ai_eval_hand_card_condition` passes 0. Hypothesis (L): the card whose effect performs the summon.
- Case shapes (examples): LP threshold against `ai_get_card_lp_amount` (`0x1daf`, `0x19d5`, `0x13a7`: 0 when LP > cost); presence of a partner card (`0x1917` ↔ `0x190b`, `0x1620` ↔ `0x160a`: 0 when the other is face-up); candidate availability (`0x1ab0`-`0x1aae`, `0x1d90`, `0x180c`… : 0 when `ai_count_acceptable_candidates` ≠ 0); battle comparisons (`0x1e86`, `0x1c0c`-`0x1c0e`, `0x1523` weakest opposing ATK outside 1,101-1,899 → 0); simulations: `0x1504`/`0x1502`/`0x1501` put the card id in a free zone and ask `ai_can_slot_attack`; `0x18aa`/`0xfe0` put it there face-up and probe table D (`0x1d83`) or B (`0x12c5`, `0x1d82`) with `ai_try_card_from_table(..., 0)`.
- Side-effect concerns: rule flag `0x09e03070 |= 0x20` (dominance stale) is set and never cleared by this function (H) — that just forces a later recomputation. The `0x18aa`/`0xfe0` cases write 1 to the zone's face-up word (`0x09e2a564 + zone × 0x14`) and clear only the card id afterwards (M: the decompilation shows no restore; the word is harmless on an empty zone but differs from the 0 a reset leaves).

Fit in the pipeline: step 5 (summons). It is the card-knowledge shortcut in front of the summon simulation: `ai_choose_summon_from_hand` → `ai_eval_hand_card_condition` → this; also `ai_should_summon_in_defense`, `ai_eval_hand_monster_summon(_option)`, `ai_update_best_summon_candidate`, `ai_choose_summon_by_dominance_order`, `ai_sim_prepare_battle_stats`, `ai_score_fusion_by_hand_materials`.

#### ai_choose_candidate_by_card (which list entry to take)

Signature (M): `int ai_choose_candidate_by_card(int side, uint card_id, int param, int mandatory)`; returns a candidate index (into the list built by `duel_effects_build_candidate_list`, `0x09e29928`), -1, or 0 in one table path.

- Pre-checks (H): empty list → -1; if `mandatory == 0`, the first entry that is not already selected and not vetoed by `ai_reject_candidate(stack top card, i)` must exist, else -1 (the stack top is the u16 at `0x09e03000 + depth × 4`, i.e. entry depth−1 of `0x09e03004`). `mandatory` is also passed on to the final generic picker and decides, in the AI-table default, between -1 and the "sarcophagus / restricted / mode 2" fallback.
- `ai_collect_board_stat_extremes(side, rec)` fills a 40-byte local record (its word at +0x14 is tested `< 0` by the `0x1399`/`0x1b89`/`0x1c4f` group: a negative value selects a fixed priority list `0x17dd`, `0x17d9`, `0x12ac`, … on the opponent's turn) (L for the record layout).
- `ai_choose_exodia_piece_candidate(side, card)` is tried before any card case (H).
- Dispatch: the card id `card_id`, about 235 ids. Each case either returns, or sets `(mode, score_fn)` and jumps to the common end `ai_choose_monster_candidate_with_score_fn(side, card_id, param, count, mode, extremes, score_fn, mandatory)`. `mode` is 0 by default, 1 or 2 per case; `ai_pick_candidate_by_score_fn(card, count, mode, extremes, fn)` takes the same values (meaning open; candidates: a location preference or a sort direction).
- Shapes (H for the code, M for the purpose): named-card priority lists (most common; ~130 `ai_find_candidate_*` calls), score callbacks (≈25 different `ai_score_*` functions), delegation to dedicated choosers, small rule code. `param` is the candidate parameter of the effect (`duel_effects_get_candidate_param`); some cases compare it with card ids (`0x1c5d`, `0x18fb`), so it can carry a card id (M).
- AI-table default (H): when the current link `0x09e28e44` is for `card_id`, `ai_find_candidate_from_ai_table(side, card, table, 0x09e03068 & 1)` is tried on D (`0x09dffdc8`), A (`0x09dfe500`) and B (`0x09dfe848`); bit 1 of `0x09e03068` then makes the function return 0. This is how a search/recover effect picks a card the AI would later want to activate (M).
- Writes through the current link pointer `0x09e28e44` (`+0x12` for `0x1e07`, `+0x08` for `0x1b50`) pass a value to the score callback through the link (M).

Fit in the pipeline: step 6 (choices). `ai_simulate_candidate_choice` (and the capped / up-to variants) call it for every pick; kinds 6 and `0x4a` reach it through `ai_try_choose_candidates` / `ai_choose_candidate_index` (ai-helpers.md). Handlers of the `candidate` family (`ai_cond_has_candidate`, `ai_count_acceptable_candidates`) use the same list and `ai_reject_candidate`.

#### ai_choose_target_by_card (which field slot to target)

Signature (M): `int ai_choose_target_by_card(void *ctx, void *link, int card_id, uint mask, int strict)`; returns `side | slot << 8` or -1. `mask` bit `side × 16 + slot` (slots 0-10).

- Order (H): `mask == 0` → -1; pre-choosers `ai_choose_target_for_179f_17b8_1889_1c9f` and `ai_choose_target_for_12d1` (own side, card, mask); the compare chain on `card_id`; the common fallback.
- Fallback (H): `strict == 0` → `ai_pick_random_slot_prefer_side(ctx, preferred, mask)` with `preferred = 1 − ((ctx +2 bit 0) xor (ctx +3 bit 6))`, i.e. the opponent of the controller (one branch sets it to the own side); `strict != 0` → -1. Several branches also return -1 early only when `strict` is set, and `0x1f1f` masks out planned attack targets only when `strict`. So `strict` = "return only a target the AI likes".
- Branch shapes: see the rows.tsv summary (dedicated chooser, score picker, stat picker, battle context, link target reuse, threat pickers, controller-side selection). Battle globals: attacker `0x09e28620`/`0x09e2863c`, attack target `0x09e28624`/`0x09e28640` (duel-runtime.md), read only in phase 3. `ai_choose_slot_target_by_threat(side, card, mask, strict, a, b)` is the default for the biggest groups (≈90 ids with `(0,1)`); `a`/`b` meanings open.
- Some branches dispatch a second time on the ctx card id (`*ctx`, 18 ids) rather than on `card_id`; the two differ when the caller (`ai_choose_cost_by_card`) passes a card other than the acting one (M).
- Answered link (`link`): read as a chain link — `link +0` card id, `+2` bit 0 side, `+6 >> 1` target count, targets via `duel_effects_get_link_target`. Cases `0x1c64`/`0x1bb6`/`0x1591`/`0xebf`, `0x1cd9`, `0x1c08`/`0x156c` (link's card) remove the link's valid targets (`ai_is_valid_target`) from the mask before `ai_pick_slot_by_threat`; `0x15b8` protects own cards that the opposing link would destroy (`duel_effects_link_would_destroy_card`).

Fit in the pipeline: step 6. `ai_choose_target_as_controller` (76 callers: `ai_cond_has_target`, handlers, `ai_decide`) wraps it with the view side switched; `ai_count_choosable_targets` calls it repeatedly removing each chosen slot; `ai_choose_cost_by_card` uses it for cost targets.

#### Corrections to existing docs

- ai.md "Target choice": the chain has 386 distinct card ids (131 is about the number of branches). The fifth parameter, called `mandatory` there, suppresses the random fallback when non-zero, so it reads as "strict / optional target"; `ai_decide` "tries the mandatory then the optional variant" should be re-checked against this (M).
- ai-tables.md: the 7-word jump table of `0x09d440d8` at `0x09dfe4c8` is not a card-id dispatch; the card dispatch of that function is a compare chain (H for the chain; the switch visible in the decompilation is on `0x1b33`-`0x1b38`, a 6-way switch, so the 7-word table is plausibly it, L).
- effect-helpers-misc.md "209-case chain" / "240 cases": 202 / 235 distinct ids by a mechanical count of compare constants (M; the counting methods may differ).

#### Name mismatches

- `ai_check_card_condition`: the function decides a summon position (0 face-up attack, 1 set/defense, -1 undecided), not a generic "condition" (M). A name such as `ai_choose_summon_position_by_card` would fit.

#### Open questions (the per-card target, candidate and position choosers)
- Exact meaning of `ai_check_card_condition`'s `flag` (3rd argument) and of card `0x135d` forcing it; what `context_card` is at the other seven callers.
- Meaning of the `mode` word (0/1/2) of `ai_choose_monster_candidate_with_score_fn` and `ai_pick_candidate_by_score_fn`, and the layout of the 40-byte record from `ai_collect_board_stat_extremes` (its `+0x14` word).
- Whether `ai_try_card_from_table(side, card, table, 0)` called from `ai_check_card_condition` can commit an activation or is only a probe.
- Meanings of the last two arguments of `ai_choose_slot_target_by_threat` (`(0,0)`, `(0,1)`, `(1,1)` groups) and of `ai_pick_least_valuable_slot`'s flags.
- The `0x1889` branch of `ai_choose_target_by_card` clears slot-flag bits 22-23 and sets one back based on the post-simulation state; whether this is an exact restore needs the disassembly.
- The `0x18aa`/`0xfe0` cases of `ai_check_card_condition` leave a 1 in the borrowed zone's face-up word; confirm in PPSSPP whether it persists.

### Findings from the attack evaluator, cost chooser, interests and yes/no evaluator

Basis: full read of the Ghidra decompilations of `ai_eval_attack` (`0x09d06188`), `ai_eval_battle_card_effects` (`0x09d015b8`), `ai_choose_cost_by_card` (`0x09d64e54`), `ai_board_note_card_interests` (`0x09d8fc24`) and `ai_decide_optional_activation` (`0x09d95f5c`) of `rel_duel_eng` (runtime base `0x09be1400`). Nothing traced in PPSSPP. No VFPU code in any of the five. Confidence per claim: H read directly from the code, M one inferred meaning, L structural only.

Player-block offsets used below (from `docs/formats/duel-runtime.md`, confirmed by how these functions use them): hand list `+0x124` with count `+0x0c` (`0x09e2a534`), deck list `+0x304` with count `+0x10` (`0x09e2a538`), Graveyard list `+0x55c` with count `+0x14` (`0x09e2a53c`). Field slot `s` at `0x09e2a55c + side·0xb3c + s·0x14`: `+0x00` card id (low 14 bits), `+0x06` position (0 = Attack), `+0x08` face-up word (non-zero = face-up), `+0x10` flags word (bit 2 tested as "effect negated" before card effects; bit 8 tested by all five functions as "ignore this card's effects", and set/cleared by `ai_eval_attack` around the `card_db_is_rainbow_dragon` / `0xead` simulation). M for the two bit meanings.

#### The 68-byte attack result`n`nLayout and grading: [`../formats/ai-runtime.md`](../formats/ai-runtime.md), `ai_attack_result`.`n`n### `ai_eval_attack` (`0x09d06188`) flow

1. `ai_init_attack_result(result, side, slot, target)`.
2. Monster target only: copy the two 52-byte stat blocks from the stat snapshot (`0x09e0308c + s·0x154 + slot·0x44`) and call `ai_sim_resolve_battle(side, slot, target, atk, def, 1)`; bit 1 → attacker slot into the mask, bit 0 → target slot. Either one ends the evaluation early (class 0 / ≥ 4 and `+0x28` of the loser += rating + 1). Hypothesis (L): flag 1 limits this to outcomes that do not depend on damage calculation; otherwise every ordinary kill would skip the damage booking.
3. Save globals: battle globals `0x09e28620`–`0x09e2875c` (attack globals, the battle records `0x09e28650 + s·0x48`, damage records, replay snapshot), `0x09e29914`–`0x09e29927` (5 words), the candidate list `0x09e29928` (`0x800` bytes) and the per-candidate words `0x09e2a128` (`0x400` bytes); the attacker's and defender's snapshot records (13 words each) and the defender's position word. Set `0x09e28620 = side`, `0x09e28624 = 1 − side`, `0x09e28628 = direct`, `0x09e2863c = slot`, `0x09e28640 = target`; `ai_mark_monsters_for_snapshot(1)`.
4. Pre-battle card cases that edit the snapshot ATK/DEF (`+0x18`/`+0x1c` of the 0x44 record), the defender's position or the result: a `card_db_is_rainbow_dragon` attacker with field card `0xead` (attaches effect kind 9 and slot flag bit 8 to the defender, recomputes its stats), `ai_sim_apply_1d14_in_battle`, attacker ids `0x1ccc`, `0x1ed9`, `0x1e95`, `0x1e08`, `0x1ce0`, `0x1ab3`, `0x152d`, `0x1c60`, `0x1c5f`, `0x1ebe`, `0x1eb8`, `0x1e1e`, `0x1c7c`, `0x1c5d`, `0x1954`, `0x1913`, `0x158d`, `0x13a7`; defender ids `0x1ccc`, `0x1c4f` (revives a Level ≥ 7 Type-1 monster from the Graveyard as the new defender value), `0x1aca`, `0x1ebf`/`0x1a78`, `0x148a` and the redirect cards (`0x1e16`, `0x1cb1`, `0x1caf`, `0x1ba0`) through `ai_sim_redirect_attack_to_slot`, `0x13a7`, `0x111b`-`0x1119`; plan trick `0xeab` (plan `+0x20` = `0x09e27704`); Type `0x15` monsters lose 500 per active `0x1e26`.
5. `duel_core_battle_compute_stats(0, 1)`; field cards `0x1381` (halve the final ATK `0x09e28674 + side·0x48` per valid copy) and `0x13f9` (zero it for the best attacker); `duel_core_battle_resolve(0, 1)`; book damage.
6. Effects: `ai_eval_battle_damage_effects` for both battlers, `ai_sim_get_destroyed_card_destinations` (destination array `dest[4]`), per-side destinations into block `+0x02`, `card_db_is_saber` battlers with `0x1d70`, `0x1e13` forced target, destroyer effects (Graveyard destination `0x0e`), `ai_eval_battle_card_effects`, link sources `0x1e00`/`0x1408`/`0x1625` (attacker damage += defender DEF), `0x1819`, `0x18e5`, `0x1abc` mutual destruction, `ai_eval_destroyed_monsters_effects`, damage cancellers (`0xecb`, `0x1cd1`, `0x1d62`, `0x1db7`), `0x1512` (both destroyed), `0xe9e` (LP loss = card ATK), grading, `ai_attack_result_add_side_losses` ×2, `ai_is_attack_trade_favorable`, late per-card class corrections.
7. Undo: remove the temporary link markers (`duel_core_post_remove_link_marker`), clear slot flag bit 8, recompute stats, `ai_detach_markers_since_snapshot` when step 3 marked, restore every saved block.

The `mode` argument (4th) is never read in the decompilation (callers pass 1 or the plan mode). The caller list includes `ai_eval_attack` itself although the body has no self call (probably an address reference Ghidra counts as a call; L).

#### `ai_eval_battle_card_effects` (`0x09d015b8`)

Arguments: side, slot, target, attacker stat record (int words), defender stat record, destination array (`dest[s]`, `dest[2+s]`), result. Structure (H):

1. Attacker chain (skipped when the attacker's slot flag bit 8 is set or its battle record `+0x40` (`0x09e28690 + side·0x48`) is non-zero): ~20 ids. Effects are recorded either directly in the result or through a local LP pair passed to `ai_attack_result_add_card_lp_change(side, slot, card, 1, 1, pair, result, 0, 0)`, and through a "destroy the target too" level (`local_48`: 1 or 2) that marks the target destroyed when `ai_card_can_target_slot_from_zone` allows it.
2. Defender chain (same skips): ~30 ids, same mechanisms, plus three ids handled regardless of record `+0x40`: `0x1c4f` (a destroyed defender whose destination is `0x0e` is treated as surviving), `0x1a72`, `0x129a`.
3. Second attacker chain (only the bit 8 skip): ids that react to the attacker's own destruction or to the battle position (`0x1e98`, `0x1ce0`, `0x1cd3`, `0x1eaf`, `0x1bed`, `0x1aef`, `0x1a72`, `0x18b9`/`0x18b8`/`0x185a` with slot effect `0x18cd`, `0x1b20`, `0x1835` and five ids that need their own slot effect).
4. Slot effect `0x1f1b` on the destroyed attacker.
5. Defender `0x1e24`: cancels both damages and both destructions and books its LP amount (`ai_get_slot_card_lp_amount`).

Return value: 1 when an attacker-side effect still applies although the attacker is destroyed (cases 1 with level 2, 3, 4), else 0; `ai_eval_attack` then sets result `+0x06 = 1` (M).

#### `ai_choose_cost_by_card` (`0x09d64e54`)

Arguments: ctx (24-byte link; uses `+0` card, `+2` side/slot, `+3` bit 7 / bit 6, `+6 >> 1` target count, `+7 >> 1` second count, `+8`/`+0xa`/`+0xc` words, writes `+0x10`/`+0x12`), side, card id, slot mask (`side·16 + slot`, 11 slots per side), optional flag. Answer `side | slot << 8` or −1. Structure (H):

1. `0x09e2d274 = side` (written before anything; meaning of that word open).
2. With optional set: mask pre-filters (see the row).
3. `ai_choose_cost_for_tribute_cards(ctx, side, card, mask)` wins when ≥ 0.
4. Compare chain of about 200 ids. Recurring patterns: (a) dedicated chooser; (b) "collect own slots of mask, Fisher-Yates shuffle with `duel_core_random`, keep the highest positive score" with a per-card scorer (ties keep the first after the shuffle, scores ≤ 0 never win); (c) `ai_choose_slot_target_by_threat(side, card or ctx card, mask [own or opponent half], optional, a, b)` with the flag pair (0,0) / (0,1) / (1,1) by card group; (d) `ai_pick_least_valuable_slot(side, 0, mask, optional, 0 or 1, 0)` for a 20-id group; (e) ~70 ids in a single "not equal" test that go to `ai_choose_tribute_slot_2` (with no optional pointer for `0x1ad1`, `0x195c`, `0x187e`, `0x1713`, `0x167d`, `0xe9d`).
5. Fallback when the chosen value is negative: optional → −1; else a random opponent slot of mask (`duel_core_random(count)`), else a random own slot.

Simulations inside: `0x1e8e` runs `ai_init_plan_and_battle_stats` + `ai_eval_attack(controller's opponent, 0x09e2863c, 0x09e28640, 1, local result)` and keeps the own pick only when the controller's `+0x20 + +0x24` stays below its LP (otherwise compares ATK with the source slot); `0x18e5`/`0x0d` call `ai_simulate_attack(side, slot, 0, 1, cannot_skip)` and answer `opponent | byte 0x09e27fa4 + (1 − side)·0x18` (a simulated target slot; meaning of that array M/L); `0x14ee` checks `ai_eval_dominance_change` of the picked slot.

#### `ai_board_note_card_interests` (`0x09d8fc24`) and the interest record

Arguments: side, card id, slot (`0x0b` = hand). Called by `ai_analyze_board` for each card the side holds (field, hand). Face state: −1 hand, 1 face-up (slot `+0x08` ≠ 0), 0 face-down (H for the computation, H for "face-up" from `ai_is_slot_face_up`).

Interest record as built here (24 bytes; `ai_board_add_interest_record` adds `weight` to `+0x00` of an equal record, comparing `+0x04`–`+0x17`, or takes a free entry):

| Offset | Type | Values written here | Reading | Conf. |
| --- | --- | --- | --- | --- |
| `+0x00` | u16 | 0 in the template (weight is the call argument: 1, 2, 3, 5 or 7) | Weight | H |
| `+0x02` | u16 | always 0 here | — | H |
| `+0x04` | u16 | A card id (named-card records) or one of `0xe133`, `0xe26d`, `0xea93`, `0xe27b` (with a Type in `+0x10` for the last three) | Wanted card, or a special key (high bits `0xe000`; meaning unknown) | H / L |
| `+0x06` | u8 | 1 in named-card records and in templates T3/T4 | Kind flag A | H / L |
| `+0x07` | u8 | 1 in templates T1/T2 | Kind flag B | H / L |
| `+0x08` | u16 | 1 (T1, T3) or 0 (T2, T4) | Kind flag C | H / L |
| `+0x0a` | u16 | 2 or 3 | Level comparison: 2 = at least, 3 = at most (pairs (3,4), (2,7) with `0x1c4f`, whose battle case revives Level ≥ 7; (3,4) with `0x1927`, whose cost chooser uses `ai_score_low_level_cost_monster`) | M |
| `+0x0c` | u16 | 2, 3, 4, 6, 7 | Level for `+0x0a` | M |
| `+0x0e` | u16 | 1, 2, 3, 5, 6 | Attribute (`0x1d8b`/`0x1cfd` write 2 unless more than 2 Graveyard monsters of Attribute 2 already exist) | M |
| `+0x10` | u16 | 1–0x17, Fusion material codes < 0x16 | Type (`0xebb` writes 4 when no Type-4 monster is in the Graveyard; `0x1d93` writes `0x11` when other Type-`0x11` monsters are face-up) | M |
| `+0x12` | u16 | 2, 3, 8, 9, 0xa, 0xe, 0xf, 0x10, 0x12, 0x15, 0x1f, 0x25, 0x2e, 0x34, 0x3c | Category code (Fusion material codes 0x16–0x19 map to 0xe, 0x25, 0x2e, 0x12; looks like an archetype index) | L |
| `+0x14` | u16 | 1, 2, 3 | Second comparison kind | L |
| `+0x16` | u16 | 0, 1, 2, 3, 5, 6, 7, 0xa, 0xf | Value for `+0x14` (hypothesis: ATK/DEF in hundreds, L) | L |

Templates (H): T1 = `+7=1, +8=1` (`0x1b92` when its planned attack entry `+0x02` is set, `0x1d2f`, `0x17be`/`0x1712`); T2 = `+7=1, +8=0` (`0x1dce` unless `ai_is_not_spell_blocked_by_17a3` passes and LP ≤ 800); T3 = `+6=1, +8=1` (the main chain; about 70 ids are explicitly excluded from it); T4 = `+6=1, +8=0` (a final chain: `0x1cb7`, `0x1c10`/`0x1c0f` weight 5, `0xebb`, `0x1dd5`, `0x1dcc`, `0x1d45`, `0x1e47`, `0x1d1d`, `0x1714`, `0x1bc9`/`0x1bc8` two records each, `0x1e5a`, `0x1cfc`, `0x1cee` weight 7 from the hand, `0x16cb`, `0x1466`, `0x1daf`, `0x1920`/`0xea8`, `0x1d8b`/`0x1cfd`). Named-card records: fresh zeroed record with only `+0x04` = id and `+0x06` = 1, added only while the side has no copy of that id in the Graveyard (`duel_core_count_graveyard_named < 1`) — so they mean "wants this card in its Graveyard" or "misses this card" (M).

Answer to the `ai.md` open question "layout of the flag bytes `+6`..`+0x17`": as tabled; which handlers read the records is not visible from this function (the readers were not in this batch).

#### `ai_decide_optional_activation` (`0x09d95f5c`)

Argument: the 24-byte chain link of the card being asked about. Fields read: `+0x00` card id, `+0x02` bit 0 side, bits 1–5 slot, `(u16 +0x02 & 0xfff) >> 6` event code (values tested 2, 5, 0xf, 0x16, 0x17), `+0x03` bit 6 control swap, bits 4–5 selector, bit 7 (set temporarily for `0x1e3c`), `+0x08` (instance index for `0x1c9a`), `+0x07 >> 1` count, `+0x14` event argument (LP value for `0x199e`, packed slot for `0x1cb1`, instance for `0x1592`), `+0x15` packed target (`bit 1` side, `bits 2–5` slot) for `0x1ef7`, `0x1eb9`, `0x1e41`. H for the reads, M for the meanings.

Structure (H): pre-checks (`0x1b39` substitute; `ai_is_activation_blocked` → 0; `card_db_is_spirit` cards at event 5 → position-change check); compare chain of about 230 ids (patterns in the row); cases that set the answer without returning fall through to the tail (`card_db_is_gladiator_beast` cards at event 0x17; cards with a non-zero `card_db_get_lv_family` and selector 1). Default answer 1 ("yes") for ids not in the chain — so an unknown optional effect is activated (H). Several branches decrement `0x09e28f80` around a shared-handler call and restore it (purpose open; it is also adjusted in `ai_eval_attack` around `ai_is_valid_target` for `0x1381`).

This answers the open question "the 12 KiB yes/no evaluator is only skimmed": it is a per-card compare chain with shared handlers and simulations, default yes, no scoring scale (the result is a boolean except `0x1678`, which returns a mask, and the pass-through answers of the shared handlers).

#### Corrections to existing docs

- `ai-runtime.md` interest record: `+0x04` is a u16 card id/key, not a u32; `+0x06`, `+0x07` are separate bytes and `+0x08`–`+0x16` are u16 criteria fields (table above). The comparison still covers `+0x04`–`+0x17` (from `ai_board_add_interest_record`, not re-read here).
- `ai.md` "Round 2" paragraph: the per-side block of the attack result also holds `+0x18` mill count, `+0x1a`/`+0x1c` effect flags and `+0x1e` counter, and the header `+0x04` direct, `+0x08` Graveyard-destination flag, `+0x0a`, `+0x0c` flags and `+0x10` ATK bonus.

#### Name mismatches

None: the five names fit what the code does.

#### Open questions (the attack evaluator, cost chooser, interests and yes/no evaluator)
- What `ai_sim_resolve_battle(..., 1)` restricts, so that the early return of `ai_eval_attack` does not skip ordinary kills (needs `0x09cfd864` read or a trace).
- Header `+0x06` values 1/2 and the per-side `+0x1c`/`+0x1e` words: how `ai_is_better_attack_result` and `ai_plan_simulate_attacks` weigh them.
- Meaning of the attack-result class beyond the grading rules (the comparator `0x09d0c2e4` decides the order).
- Interest records: the special keys `0xe133`, `0xe26d`, `0xea93`, `0xe27b`; the kind flags `+0x06`/`+0x07`/`+0x08`; `+0x12` category codes; `+0x14`/`+0x16`; the readers of the table.
- `0x09e2d274` (written by `ai_choose_cost_by_card` with the side) and `0x09e28f80` (decremented around shared-handler calls): meanings.
- `0x09e27fa4 + side·0x18` (byte read as a slot after `ai_simulate_attack` in the cost chooser).
- The unused `mode` argument of `ai_eval_attack`: confirm in the disassembly that `a3` is really ignored.

### Findings from band 1

Notes from the A1 batch (94 undocumented `ai` functions of `rel_duel_eng`, address order, `0x09bf3c34`-...). Basis: the exported Ghidra decompilation only; nothing traced in PPSSPP.

#### Temporary links in the chain array (H)

`ai_choose_candidate_with_temp_link` (`0x09ceb830`), `ai_choose_target_with_temp_link` (`0x09ceba44`) and `ai_choose_cost_with_temp_link` (`0x09cebd00`) borrow the next free chain entry `0x09e28cb4 + n * 0x18` (`n` = link count `0x09e28e34`; they refuse with -1 when `n >= 16`): they save its 24 bytes, write a link for the card (`+0` card, `+2` bit 0 side, bits 1-5 slot, bits 6-11 event, `+3` bits 4-5 handler selector, `+3` bit 7, `+4` bits 5-13 instance of the slot's card, `+6`/`+7` counts), make it the current link `0x09e28e44`, run the normal target / cost / candidate chooser, and restore both. `ai_get_card_target_mask` (`0x09ce9878`) builds the same kind of link on the stack instead.

The effect recursion counter `0x09e28f80` doubles as the "AI evaluation" switch: `ai_check_target_slot` returns 0 (reject) whenever it is `>= 0`, and the AI wrappers decrement it around their call (`ai_get_card_target_mask` always, the temp-link choosers when their `simulate` argument is set). So AI target checks only apply inside those wrappers (H for the code; the reading that `ai_is_valid_target` therefore rejects every slot when called outside them is an open question).

`ai_classify_resolve_kind` reads the byte at `link - 0x16`: the location byte of the previous 24-byte link, i.e. the link being answered when the classified link is a negation (H for the address arithmetic, M for the meaning).

#### Tribute choice pipeline (H)

`ai_choose_tributes(side, instance, count, out_refs)` loops `count` times over `ai_choose_tribute_slot(side, instance, mask, chosen, out_refs, 0)`; the slot chooser narrows the mask with per-card pre-filters (`ai_filter_mask_*`, `ai_filter_tribute_mask_for_exodia`), then always with `ai_filter_mask_keep_card_specific_tributes` and `ai_filter_mask_keep_useful_tributes`, picks with `ai_choose_tribute_slot_2(side, 0, mask, &flag)` and falls back to `ai_choose_slot_from_mask_b` with an ATK/Level sanity test. Every filter returns the original mask when its result would be empty (except the `0x1e85` branch, which can leave an empty mask, and `ai_filter_mask_keep_attribute_3` with `strict`). Required counts come from `ai_get_required_tribute_count(side, instance, set_mode, reduction)`, where `reduction` is a card id produced by `ai_get_tribute_reduction_card` (`0x1e03` = one less, `0x19b2`/`0x1aa3` = none needed, others = 1 when the summon mask allows it).

#### Position choice (M)

`ai_choose_monster_position(side, atk, def, margin)` returns 0, 1 or -1; the branches (0 for a lethal board or a weak opposing attacker, 1 when atk is 0 or far below the opponent's best attacker) fit 0 = Attack Position, 1 = Defense Position, -1 = no preference. `ai_check_monster_position_change` returns the same codes after about 75 per-card rules.

#### Other globals seen

- `0x09e27fa4 + side * 0x18`: per-side simulated attack result read by `ai_check_monster_position_change` after `ai_simulate_attack` (u16 `+0` < 5 tested like a slot; `+0x0c` and `+0x10` summed as damage). M.
- `0x09e290f0` bit 1: tested by `ai_choose_tribute_slot` for card `0xeca` (inside the summon record area `0x09e290bc`, `+0x34`). Meaning unknown.
- Link hint words `+0xa`..`+0x12` are written by `ai_fill_link_hints_for_1ba2` into the current link; `+0x12` is the extra-target ring index in `chain.md`, so the AI reuses link fields as scratch for this card group.

#### 68-byte attack result (as read by this batch)

Built by `ai_init_attack_result(result, side, slot, target)` and filled by `ai_eval_attack` and the `ai_eval_*` helpers; compared by `ai_is_better_attack_result`. Fields used here (H for the accesses, M for the meanings):

| Offset | Type | Use |
| --- | --- | --- |
| `+0x02` | u16 | Attack rating: higher wins in `ai_is_better_attack_result`; 5 is a special top value; `ai_choose_attack_target` returns `rating != 0`; `ai_is_attack_trade_favorable` returns 0 when it is >= 2 |
| `+0x06` | u16 | Second rating (lower is better in the tie-break; set to 2 by removal effects in `ai_eval_destroyer_graveyard_effects`; >= 2 makes `ai_is_attack_trade_favorable` return 1) |
| `+0x0e` | u16 | Destroyed/removed mask, bit `side * 5 + slot` |
| `+0x14 + s * 0x18` | u16 | Side `s`'s monster in the battle (attacker slot / target slot) |
| `+0x16 + s * 0x18` | s16 | Destination of `s`'s destroyed monster (`ai_attack_result_get_destroyed_destination`) |
| `+0x18 + s * 0x18` | u16 | Card-advantage counter of side `s` (incremented by draw/recruit/search effects, decremented by 0x1ed2) |
| `+0x1a`, `+0x1c` + `s * 0x18` | u16 | Effect flags of side `s`; `+0x1c` also holds a recruited card id or `side | slot << 8` + 2 |
| `+0x20`, `+0x24` + `s * 0x18` | u32 | Damage / LP-loss words of side `s` |
| `+0x28 + s * 0x18` | s32 | Loss value of side `s` (monster values from `ai_rate_monster_loss_value`, ATK of removed monsters) |

#### Working-plan details confirmed

- Attack-order records at `0x09e27828 + i * 0x10` are walked as a list by `ai_review_battle_plan`: `+0x02` attacker slot + 1 (0 ends the list), `+0x04` target slot (5 = direct), `+0x00` compared with 1, `+0x0a` and `+0x0c` gate the risk check. This extends `ai-runtime.md`, where only record 0 `+2` was known (M for `+2`/`+4` of every record).
- `ai_choose_attack_target` saves and restores the working plan as header `0x09e276e4`-`0x09e27707` (0x24 bytes), attack entries `0x09e27708` (0xa0), extra entries `0x09e277a8` (0x80) and records `0x09e27828` (0x1a0 = 26 records): 0x284 bytes in total, so the unaddressed tail `+0x264`..`+0x2e3` of `ai_battle_plan` is not part of this copy either.
- The working plan's `+0x1a` word (`0x09e276fe`) is used by `ai_review_battle_plan` as a mask with bit `side * 5 + slot` over both sides' monster zones (slots restored from the snapshot and cleared again), not only as an own-slot mask.
- Extra attack entries: `ai_sim_summon_monster` claims a free one (`+0x00 == 0xffff`) for a monster with slot flag bit 29 and stores the index in that monster's main attack entry `+0x00` (H). This supports the "additional attack" reading in `ai-runtime.md` (L -> M).
- `ai_summon_choice +0x01` (`0x09e03081`) is written with the summoning side by `ai_sim_resolve_card_with_temp_link` (H), which supports the "side the candidate is simulated for" reading.

#### Simulation undo markers (H)

`ai_mark_monsters_for_snapshot` attaches a kind-2 effect with key `0xff` (value `side | slot << 8`) to every monster and to each hand slot; `ai_detach_markers_since_snapshot` finds the marker that belongs to the current snapshot depth `0x09e27fee` in each slot's effect list (pool `0x09e2c7cc`, 10-byte entries: `+0` key, `+2` low 4 bits kind, `+8` next index; list head at slot `+0x0a`, hand list at player block `+0x11a`) and detaches it together with every later entry. Effects attached during a simulation are therefore removed by list position, not by key. `ai_sim_summon_monster` attaches the same `0xff` marker to a simulated monster.

#### Destination codes (M)

`ai_sim_get_destroyed_card_destinations` fills `int dests[4]` (`[owner]` when the result gives a destination, `[owner + 2]` otherwise) with defaults from `.data` `0x09e01b94`/`0x09e01b98`, using `0xf` (banished) under the banish-redirect mask; card rules write `0xd` and `10`. Together with the self-exclusions of `ai_estimate_card_def` (location `0xb` hand, `0xe` Graveyard, `0xf` banished) this gives the AI location codes `0xb` hand, `0xd` Deck, `0xe` Graveyard, `0xf` banished, `10` spell/trap zone placement (M).

#### Battle and stat snapshot

- `ai_stat_snapshot +0x34`..`+0x43` readers (open question in `ai-runtime.md`): `ai_rate_monster_loss_value` reads `+0x34`, `+0x38`, `+0x40` of records (H). `ai_estimate_slot_stats` writes `+0x34`..`+0x40` for the non-AI side too: estimated ATK/DEF and printed ATK/DEF for a hidden card, or the flag-2 recompute for a visible one (H).
- `ai_is_slot_battle_stopper(side, slot, attacker_slot)` reads the attacker's snapshot record (`+0x10` attribute mask, `+0x14` Level, `+0x18` ATK).
- `0x09e28690 + side * 0x48`: a per-side battle word that, when non-zero, disables the destroyed/winner card effects in all `ai_eval_*` helpers (meaning unknown; not in `battle.md`).
- `0x09e28638`: set to 1 by `ai_review_battle_plan` and `ai_choose_best_attack` around their simulations and restored after (meaning unknown).

#### Name mismatches

- `ai_filter_mask_exclude_1807_group`: with card 0 it returns `ai_filter_mask_by_1807_group(side, 0x1b14, mask)` (a keep filter); it only excludes for the three group ids.
- `ai_is_ranked_card_with_low_atk` repeats the whole `ai_get_card_rank` table inline instead of calling it.
- `ai_eval_destroyer_graveyard_effects` evaluates both the destroyed monster's effects and the winner's; `ai_eval_destroyer_battle_effects` likewise covers both monsters.
- `ai_choose_slot_from_mask_ex` is a wrapper of `ai_choose_tribute_slot_2`, not a mask chooser of its own.
- `ai_is_slot_max_threat_b` is the body that `ai_is_slot_max_threat` (8 bytes earlier) falls into with `target_slot = -1`.
- `ai_check_monster_position_change` returns a position code (0 Attack / 1 Defense / -1), not a yes/no.

#### Possible bugs in the original (L, from the decompilation only)

- `ai_try_kuriboh_support_cards` restores the slot id after its test but leaves the face-up word at 1.
- `ai_check_monster_position_change` (the 0x16bf path) writes the attacker globals `0x09e28620`/`0x09e2863c` and does not restore them.
- `ai_eval_destroyer_battle_effects` compares a chosen slot index with a side number in the 0x1d16 branch.
- `ai_choose_tribute_slot` for card 0x1e85 can replace the mask by an empty set.

#### Open questions (band 1)
- `ai_check_target_slot` rejects every slot while `0x09e28f80 >= 0`; `ai_is_valid_target` (22 callers, mostly AI handlers) calls it without decrementing the counter. Either the counter is negative during all AI handler evaluations (find where it is set) or those handlers reject every target. Trace `0x09e28f80` in PPSSPP during an AI main phase.
- Slot flag bit 10 (`+0x10`) decides whether a face-down card is estimated (`ai_estimate_slot_stats`) and gates several target rules (`ai_get_effective_attack_vs_target`, `ai_is_better_attack_result`, `ai_zone_score_opposite_column`); its meaning (known/revealed face-down card?) is not established.
- Meaning of the codes returned by `ai_classify_resolve_kind` (0-6) beyond "0 = nothing to answer", and of the outcome bits of `ai_sim_resolve_battle` / `ai_combine_battle_destroy_flags`.
- `ai_card_can_target_slot` (`0x09ceb738`) needs the disassembly to recover its arguments (skipped).
- `0x09e28e38` is used by `ai_sim_resolve_card_with_temp_link` as the index of the borrowed chain entry, while the other temp-link helpers use the link count `0x09e28e34`.
- What `ai_eval_attack` does with the return values of `ai_eval_battle_damage_effects` (1 only for 0x1504/0x1502/0x1501 with slot flag bit 16 or 17) and `ai_eval_destroyer_battle_effects`.
- Meaning of the `mode` argument of `ai_get_card_lp_amount` (1, 2, 3 select exclusion lists).

### Findings from band 2

Notes from the second fifth of the undocumented `ai` functions of `rel_duel_eng` (156 functions, `0x09d12730`-`0x09d34ac0`): battle planning, summon choice, chain response, the summon veto chains and about 110 per-card handlers. Basis: the Ghidra decompilation of each function, read in full. Nothing traced in PPSSPP.

#### Battle planning: call flow and snapshot discipline

- `ai_plan_battle(side, mode, simulate)` loops until `ai_review_battle_plan(side, -1, mode)` accepts: push snapshot, `ai_plan_battle_with_tricks(side, mode, 0, simulate, mode == -2)`, review, then two pops. The second pop matches a push that `ai_plan_battle_with_tricks` makes on entry and **does not undo itself** (H). Every caller of `ai_plan_battle_with_tricks` (`ai_plan_battle`, `ai_plan_battle_with_summoned_monster`, `ai_plan_battle_with_gemini_summon`, `ai_should_summon_in_defense`) pops one extra snapshot (H for the counts).
- `ai_sim_summon_card_to_field(..., push_snapshot = 1)` also leaves its snapshot for the caller to pop (H).
- Every inline snapshot push in this range is followed by `ai_mark_monsters_for_snapshot(0)` and `duel_effects_update_negated_slots(1)`; every pop by `ai_analyze_board(view side)` and `duel_effects_update_negated_slots(1)` (H).
- `ai_plan_battle_with_tricks` saves and restores not only the plan but the simulated board of the best plan: `0x09e2a528` for `0x1678` bytes (both player blocks), the 11 words at `0x09e2bba0`, `0x09e2bbcc` (`0xc00` bytes, card instance table) and `0x09e2c7cc` (`0xa00` bytes, attached-effect list) (H).
- Opponent reply: when `side` is the AI side, `ai_plan_battle` and `ai_plan_battle_with_summoned_monster` simulate the opponent summoning card `0x129f` (`ai_sim_summon_monster(opp, 0x129f, -1, 1, 0, 0, 0, 0)`) before `ai_build_battle_plan(opp, 1, side's saved plan, 0, 1, 1)`, with rule flag `0x09e03070` bit 2 set (H for the calls; "stand-in for an unknown summon" is a hypothesis, M).
- Phase stack: `0x09e27fe4` (4 × s16) with depth `0x09e27fec`; `ai_build_battle_plan` pushes phase 3, `ai_should_summon_in_defense` pushes phase 2; phase readers use the bottom entry `0x09e27fe4` when the depth is > 0 (H).
- `ai_build_battle_plan(side, mode, from_plan, trick, simulate, reset_attacks)`: `reset_attacks` (= `mode == -2` from `ai_plan_battle`) clears the attacked flags (bits 22-23 of slot word `+0x44`) of all five monsters. **Correction to `ai.md`**: `mode = -2` does not force phase 2 in `ai_plan_battle`; it only resets the attacked flags and makes `ai_plan_prepare_attack_state` re-run `duel_core_init_battle_phase_attack_state` (H).

#### Battle plan record: corrections (`docs/formats/ai-runtime.md`, `ai_battle_plan`)

- `+0x1a` (u16, `0x09e276fe` in the working plan) is the **mask of monsters expected to leave the field at the end of the turn** (bit `side * 5 + slot`): self-destroying cards `0x1d12`, `0x1c6b`, `0x1c09`, `0x1b4c`-`0x1b4e`, `0x1a6d`-`0x1a6f` (not under `0x1a77` / `0x1d17`), Spirit monsters when `ai_get_spirit_return_mode`, and every slot in the target mask of `0x1d12`/`0x1c09`. `ai_plan_simulate_attacks` clears these monsters from the simulated board after the attacks (or zeroes the mask when the plan wins). Replaces "slot mask of monsters with special attack rules" (H for the writes and the clearing, M for the meaning).
- Attack-order records start at `+0x144`, stride `0x10`, and there are **26** of them (`0x1a0` bytes, to `+0x2e3`): `ai_plan_battle_with_tricks` and `ai_plan_battle_with_summoned_monster` copy `0x68` words from `0x09e27828`, and `ai_update_best_summon_candidate` scans up to 26 records. So the "unaddressed tail `+0x264`-`+0x2e3`" is records 18-25 (not initialised by `ai_plan_init`, filled by `ai_plan_simulate_attacks` as attacks are added) (H for the copy size and the scan bound).
- Record fields written by `ai_plan_simulate_attacks` (H for the writes, M for meanings): `+0x00` result class (attack result `+0x02`), `+0x02` attacker slot + 1 (0 ends the list), `+0x04` target slot, `+0x06` target destroyed (result destination non-zero or destroyed-mask bit), `+0x08` extra-entry index 0-3 or `0xffff`, `+0x0a` set to 1 when the target was not a monster or was destroyed and (result `+0x06` > 1, or the target's snapshot original ATK `+0x20` >= the attacker's original ATK + 200) (meaning open), `+0x0c` set to 1 when an opposing `0x1df2` was triggered.
- `+0x22` win flag is set when the opponent's LP (`+0x14`) or, while the opponent's deck is non-empty, its deck count (`+0x1e`) drops below 1 (H).

#### Attack result record `0x09e27f90` (68 bytes) as used by the planner

Read by `ai_plan_simulate_attacks` after each `ai_choose_best_attack` (H for the offsets, M for meanings): `+0x02` result class, `+0x04` "battle cancelled / no battle" (when 0 the opposing slot gets effect `0x1e13` and per-card post-battle effects run), `+0x06` count compared with 1, `+0x08` flag copied to entry `+0x0a`, `+0x0e` u16 destroyed mask (bit `side * 5 + slot`), `+0x10` s32 value adjustment of the attacker (many per-card constants: -400, -500, +200, +3,000 …; afterwards added to the attacker's snapshot ATK `+0x18`, purpose L), per-side blocks at `+0x14 + side * 0x18`: `+0x14` slot, `+0x16` flag (e.g. a flip that is consumed), `+0x18` s16 deck loss, `+0x1a` and `+0x1c` u16 links used by some cards (`+0x1c` holds `side | slot << 8` + 1 of a card to act on), `+0x20` battle damage, `+0x24` effect LP loss, `+0x28` score. The planner keeps the first attack's result and restores it into `0x09e27f90` at the end.

#### Simulated battle results `0x09e27fd4`

`ai_sim_battle_resolve` clears and fills two 8-byte per-side records: `0x09e27fd4 + side * 8` battle damage taken by `side` (summed from the battle record per-side word `+0xc0` indexed by the side word `+0xcc`), `0x09e27fd8 + side * 8` = 1 when `side`'s monster is destroyed (battle record words `+0x64`/`+0x68`/`+0x6c`, or bits 0/1 of `ai_sim_battle_between_slots`). It saves and restores the whole battle record `0x09e28620`-`0x09e2875f` (H).

#### Summon choice pipeline

- `ai_choose_normal_summon(side, filter, tributes, slot, fallback)`: Gemini summons of own monsters, then each hand monster with each tribute-reduction card (`ai_eval_hand_monster_summon` → `ai_sim_summon_get_position` → `ai_rate_summon_candidate`), then a Graveyard `0x1f2e` special case (choice `+0` = `0x7f`, `+5` = 1, `+6` = `0x1f2e`), then a fallback "first level < 5 monster that can be summoned or set" (H).
- Opponent best stat used by the ratings: 10,000 when the word `0x09e2d1e0` is 0, else the opponent's best monster ATK (at least 1,400). `ai_should_summon_in_defense` forces `0x09e2d1e0` to 1 during its run and treats "was 0" as "ATK < 1,400 and ATK <= DEF + 200 → Defense". Meaning of `0x09e2d1e0` open (hypothesis L: "the turn player may attack this turn" / first-turn flag).
- `ai_choose_summon_by_dominance_order` tries `ai_choose_best_summon_candidate` with tribute modes 2 (level >= 5), then 0 (no tribute, no reduction; only with dominance > 0) and 1 (reduction card, no tribute) when dominance >= 0, then -1 (any) (H).
- `ai_update_best_summon_candidate` keeps a candidate when its record class is higher **or** its value is higher, or on an equal value by tie-breakers (opponent monsters destroyed `+0x02` with own monsters left, score `+0x0c`, ATK). The class comparison is an OR, not a primary key (H, literal reading).
- Tier table of `ai_rate_summon_candidate` (H): 5 tribute summon beating tributes and opponent's best (or `slot_flag` clear), 4 beats tributes and opponent's best, 3 card bonus (`ai_rate_summon_card_bonus`), 2 stat > own best, 1 any summon without tributes.
- Summon-mode bits seen here: `0x10` Attack, `0x40` Defense, `0x50` either, `0x04` used for Gemini/from-field simulations, `0x80` added for the "can set" fallback, `0xd0` the full hand mask (H for the constants).

#### Summon veto chains (`ai_filter_summon_mode_flags` callees)

`ai_filter_summon_requires_attack_chance`, `ai_filter_summon_flags_by_board_cards`, `ai_check_summon_card_conditions_a`…`_d` and `ai_check_summon_by_effect_card_conditions` are per-card compare chains with one signature shape `(side, slot, card, effect_card, stat, …)`: `slot < 0` means "card in hand / about to be summoned", `slot >= 0` a monster already on the field (then almost every rule passes). Return non-zero to allow; some rules return a count as the truth value and the LP-gain/`0x144d` rule (cards `0x1454`, `0x1450`, `0x1db9`) returns 2. The `_c` chain also implements a Six Samurai "do not summon a duplicate while a non-duplicate is in hand" rule (H).

#### Chain response

- `ai_choose_chain_response(side, link)` sets the response mode `0x09e0307c` (0/1/2) from lock cards depending on the chain length `0x09e28e38` (length 1: `0x1aee`, `0x1aec`, `0x1aed`; length 2: `0x1aea`, `0x1ae9` with deck-out counts), then tries T2 (2 entries), stops when the mode is 0 and `duel_core_has_activatable_response(link, side, 1)` is false, then T3 (181 entries) and `ai_try_chain_tables` (H).
- `ai_try_chain_tables(side, link)`: the timing-event lists R1-R3 are **u16 card-id arrays** combined with a handler fixed in code (a temporary 8-byte entry on the stack): first event code `0x12`/`0x13` → 143 ids at `0x09dfd2dc` with `ai_handler_on_attack_declared_event`, `0x14` → 36 ids at `0x09dfd3fc` with `ai_handler_on_damage_step_event`, `0x1b` → the single id at `0x09dfd444` with `ai_handler_check_rule_state_1803`. First code `0x02` restricts T1 (`0x09dfd448`, 345 entries) to eight card ids (`0x1dd4`, `0x1d2f`, `0x137d`, `0x1eee`, `0x1a9d`, `0x15f0`, `0x15ad`, `0x131e`). Then `ai_try_response_window_cards` (no link) and a `0x19a3`-in-hand rule that flips the first face-down icon-4 trap with `duel_core_submit_player_action(side, slot, 0, 3)` (H). Cross-check against `docs/formats/ai-tables.md` (R1-R3 description) when merging.
- `ai_try_chain_table_entry(side, entry, link, no_commit)` decrements the AI-evaluation depth `0x09e28f80` around the attempt, sets AI side and view side to `side`, tries field slots (also the opponent's face-up cards when `card_db_is_usable_by_opponent`), then the hand (H).
- `ai_build_chain_context` returns the `duel_effects_can_activate[_face_up]_card` result (callers test it although Ghidra typed it `void`, M). Context fields it writes: `+0` card, `+2` bit 0 side / bits 1-5 location or slot, `+3` bit 6 switched, `+4` bits 5-13 instance ref, `+5` bits 6-7 from the instance-table byte `0x09e2bbce + ref * 6` (H).

#### Recurring handler idioms

- **Response-mode test** T(ctx, link) (inlined in about 40 handlers, H): true when there is no link; with mode `0x09e0307c` = 0 when the link's controller (`+2 bit 0 xor +3 bit 6`) is ctx's controller; with mode 1 when it is the same controller and `ai_classify_resolve_kind(link) != 0`; false for other modes. Handlers **refuse** when T is true, i.e. they answer only opposing links (mode 0), and with mode 1 also own links of resolve kind 0. **Correction to `ai.md`** ("Per-card handler families", link example `0x09d27d40`: "no link → yes; mode 1 → only own-side links whose resolve kind is non-zero"): that is the refusal condition; the handler says no in those cases.
- **Target-exception check** after `ai_handler_counter_harmful_link` (inlined in about 8 handlers, H): by `ai_classify_resolve_kind(link)`: kinds 4/5 accept when the link's filter matches more cards on ctx's side than ctx's own card (`duel_effects_count_filter_matches_on_side` minus `duel_effects_call_handler_08_b` on ctx's slot); kinds 2/3 with exactly one target refuse when that target's visible card is `0x14de`, `0x15f1`, `0x1435`, `0x12ff`, `0x12fe` or `0x10dd`; other kinds accept.
- **Timing-event queue** layout (H): count `0x09e28f98`, code bytes `0x09e28fa0[i]`, 4-byte entries `0x09e28fc0 + 4 * i`: u16 low 9 bits = card instance ref (card id via `0x09e2bbcc + ref * 6`), byte +1 bit 1 side, bits 2-5 slot, byte +2 bit 0 xor'ed with the side for the controller. Codes seen: 6/7/8 and `0x20`/`0x21`/`0x22` summons, `0x16`, `0x12`/`0x13` attack, `0x14`, `0x1b`, `0x02`.
- Chain stack: links at `0x09e28cb4`, stride `0x18`; handlers count links with `0x09e28e34` while `ai_choose_chain_response` tests `0x09e28e38` (== 1, == 2) and the AI builds its scratch context at `0x09e28cb4 + 0x09e28e38 * 0x18`. Whether `0x09e28e38` is the chain length and `0x09e28e34` the number of resolved/active links is open (M for both being link counts).
- Player block words used as list counts (H): `+0x0c` hand, `+0x10` deck, `+0x14` Graveyard (list `+0x55c`); the Graveyard entry byte `+2` bit 2 is tested by `ai_handler_check_graveyard_1ca1`.
- Several handlers write the scratch word `0x09e03068` as a bit set: `ai_handler_can_choose_candidate_1379` (bit 0 threatened, bit 1 link affects players), `ai_handler_draw_if_safe_1efd` (bit 0 draw safe, bit 1 opponent decks out) (H).

#### Name mismatches

- `ai_handler_check_draw_14f0`: does not test a draw; it compares deck and Graveyard counts (deck-out drawing 4, then the opponent's Graveyard count against both decks/Graveyards and card `0x12f9`).
- `ai_handler_burn_15ae`: no burn test; it counts face-up race-1 monsters and Extra Deck `0x157e` support (a "5 monsters of one Type" combo) and an attack combo with `0x15fc`/`0x157d`. The `m == 0` branch that calls `ai_handler_burn` is unreachable.
- `ai_handler_check_phase_1d96`: the decision is a simulated attack (`ai_sim_current_attack`) for event code `0x0d`, not a phase test.
- `ai_handler_check_targets_175a`: sums upkeep LP costs and compares them with the own LP; the target mask only selects which monster's stat is subtracted.
- `ai_should_summon_in_defense`: returns the card rule's value when `ai_check_card_condition` is >= 0, so callers may get values other than 0/1.
- `ai_is_slot_blocked_by_level_lock`: with a slot outside 0-4 it answers "is any level lock active" (no monster).

#### Probable original bugs (keep in a faithful port)

- `ai_handler_check_board_154c` reads the target's DEF at the attacker's slot index (`0x09e2863c`) instead of `0x09e28640` (H for the code).
- `ai_check_summon_by_effect_card_conditions` calls `ai_is_revive_on_summon_monster(side)` with the side instead of a card id (H).
- `ai_eval_hand_monster_summon_option` and `ai_choose_normal_summon` turn "tributes = 3" into 1 when the side's LP <= tributes × 1,000 (literal; purpose unclear, M).
- `ai_plan_battle_with_gemini_summon` tests `stats == NULL` twice (dead second fallback).

#### Open questions (band 2)
- Meaning of `0x09e2d1e0` (forced to 1 by `ai_should_summon_in_defense`; 0 makes the summon rating assume an opposing best ATK of 10,000).
- Attack-order record `+0x0a` and the attack result fields `+0x04`, `+0x06`, `+0x10` (value word added to the snapshot ATK after planning).
- `0x09e28e34` versus `0x09e28e38` (chain counts) and the AI-evaluation depth `0x09e28f80` (decremented per nested evaluation, set to -1 by `ai_sim_gemini_summon_slot`).
- `0x09e28628` (returned as the decision by `ai_handler_special_summon_1973_172f` for attack events) and `0x09e28f8c` (set around a target-filter call by `ai_handler_respond_to_link_1b5f`).
- Why `ai_handler_check_candidates_162c_184c` accepts only when the 3-candidate pick is not "1, 2, 3 in order".
- The three forwarders `ai_call_eval_hand_summon_candidate` (48 bytes), `ai_call_should_summon_in_defense` (36 bytes) and `ai_call_try_chain_table_entry` (8 bytes): read their argument set-up from the disassembly.
- Whether the stand-in summon `0x129f` used for the opponent's reply plan is a dummy monster record (check the card table).

### Findings from band 3

Scope: 166 `ai` functions of `rel_duel_eng` from `0x09d358fc` to `0x09d550c0` (summon-mode filters, LP estimators, Extra Deck plan search, the candidate-choice machinery with its score callbacks and per-card choosers, slot pickers, and about 60 per-card target/cost choosers). Basis: the Ghidra decompilation in the packs; nothing traced in PPSSPP. 163 rows written, 3 skipped (hidden register arguments).

#### Candidate choice pipeline (`ai_simulate_candidate_choice`, 0x09d484d8)

How the AI answers a candidate selection (H for the control flow):

1. Header: `0x09e29914` = side, `0x09e29918` = selection kind, `0x09e2991c` = 0; the list arrays (`0x800` bytes at `0x09e29928`, `0x400` at `0x09e2a128`) are cleared and rebuilt with `duel_effects_build_candidate_list(side, card, param)`; `duel_core_get_candidate_pick_limit()` gives the limit.
2. Kind dispatch: kinds 6 and `0x4a` = one pick (`ai_choose_candidate_by_card`); kinds 7-`0x26` = exactly `kind - 6` picks (`ai_choose_candidates_up_to`); kinds `0x28`-`0x47` = 1..limit picks (`ai_choose_candidates_capped`, success with >= 1); `0x48` = capped, always success; kinds > `0x4a` = declare a card name (`ai_choose_declared_card_name`, success when the id > 0). Other kinds (< 6, `0x27`, `0x49`) return false (M: whether those kinds exist is not checked).
3. Picks are counted in the dialog answer word `0x09e2d248` and marked with `duel_core_set_selected_candidate_index` / `duel_core_set_candidate_pick_order`; the board view is rebuilt between picks.

Candidate entry (H for the reads; the list itself is duel_core's): u16 `+0` low 14 bits card id, bit 14 owner side; `+2` bits 7-14 with `+1` bit 6 form the card instance reference (`((u16 +2 & 0x7fff) >> 7) * 2 - sign(+1 bit 6)`), the index into the instance table `0x09e2bbcc` (6-byte entries, low 14 bits = card id).

"Acceptable candidate" idiom used by about 40 functions (H): `duel_core_get_candidate_selection(i) < 1` (not yet picked) and `ai_reject_candidate(top card of the AI candidate stack, i) == 0`. The top card is `*(s16 *)(0x09e03000 + depth * 4)` with depth `0x09e03024` (0 when empty).

`ai_reject_candidate` (`0x09d48b4c`, 4,104 bytes) splits on the class of the top candidate-stack entry (`0x09e03006 + 4 * (depth - 1)`, = `ai_is_special_summon_effect`): class 0 (searches, sends, recoveries) and class != 0 (special summons) have separate per-card rule lists. One rule recurses (cards `0x1dd4`/`0x1d2f`/`0x137d` check that a searched card has acceptable candidates of its own by pushing it and calling `ai_reject_candidate` on `0x09e29920 + i`). Board-view flag `0x20` adds a final rule (low LP, location `0x0d`, genre 5).

#### Score callbacks

Two callback signatures appear (M, from the call sites in the packs):

- Candidate score `int fn(int index, uint mode, int *stats)`: called by `ai_pick_candidate_by_score_fn` (`score_fn(index, a, b)`) and `ai_choose_monster_candidate_with_score_fn` (`score_fn(index, mode, stats)`). `stats` is the 10-int board-stat record of `ai_collect_board_stat_extremes`. Most callbacks end in `ai_score_candidate_by_location(index, base)` = `base * 8 + location bonus` (own side: hand 1, `0x0e` 2, `0x0d` 3; other side: hand 6, `0x0e` 5, `0x0d` 4, other 7). About 25 callbacks in this range have no direct caller and are reached only through these pointers; Ghidra types several of them `void` because they end in a tail call.
- Slot score `int fn(int side, int slot)`: used by the slot pickers (`ai_pick_target_by_score_fn_and_side_counts`, the `ai_choose_target_for_<id>` choosers, `ai_pick_field_slot_by_score_fn`). Pickers shuffle the candidate slots with `duel_core_random` and keep the first strictly higher positive score, so ties break randomly and score 0 means "never".

Board-stat record (`ai_collect_board_stat_extremes`, `0x09d3b158`; 10 ints, H for the writes): `[0]` own best ATK able to attack this turn, `[1]` own lowest Attack Position ATK, `[2]` own lowest Defense Position DEF, `[3]`/`[4]` opponent's highest visible ATK/DEF, `[5]` opponent's highest attack-capable ATK, `[6]` the highest of those with piercing, `[7]` own active `0xec4`, `[8]` active `0x175e` (both sides), `[9]` own active `0x17fe` (`[7]`-`[9]` only when `[5] > 0`). `ai_filter_positions_by_lethal_attack` reads it at byte offsets `+0x08`, `+0x14`, `+0x18`, `+0x1c`, `+0x20`, `+0x24`.

#### Current link used as AI scratch

Many choosers write per-card working values into the current link (pointer `0x09e28e44`, 24 bytes) at `+0x08`..`+0x13`, beyond the documented fields, and the matching score callbacks read them (H for the writes/reads in this range; e.g. `ai_tally_alien_cards_for_ctx` `+0x0a/+0x0c/+0x0e/+0x10`, `ai_note_gladiator_beast_candidate_flags` `+0x08/+0x10/+0x12`, `ai_note_crystal_beast_holdings` bytes `+0x0a..+0x11`, `ai_choose_name_copy_candidate` masks `+0x08..+0x13`, `ai_choose_target_for_12e2` `+0x0e/+0x10/+0x12`). Several functions save and restore `+0x0c` (temporarily 1 or 2) around `ai_get_target_mask`, so `+0x0c` influences the target filter (M). A port can model these as a per-decision scratch struct; the layout is per card.

#### Name-copy flow (`ai_choose_name_copy_candidate`, 0x09d426d0)

For cards `0x1dc2`, `0x1d43`, `0x0ea9` (H): the slot that will carry the copied name is packed in `0x09e0306c` (`side | slot << 8`; for `0x0ea9` a monster zone where the card is placed by simulation with slot flag bit `0x0c`). The link scratch is filled with masks of cards that cannot be activated now (hand indexes in `+0x08..+0x0f`, Extra Deck indexes in `+0x10`, monster zones in `+0x12`). Each candidate name is then tried by attaching a kind-2 effect `0x1d43` with the name as value to that slot (`ai_score_prisma_name_candidate`) and counting, with `ai_count_activatable_table_cards`, how many masked cards the AI tables would now activate (100,000 per card). `0x1d43` with arg 0 looks one selection ahead (`ai_score_prisma_candidate_by_followup`).

#### Extra Deck plan search (`ai_find_best_extra_deck_summon_plan`, 0x09d39c2c)

- Iterates indices below the count at player block `+0x18` (`0x09e2a540 + side * 0xb3c`) after `duel_effects_build_candidate_list(side, 0xfffe, 0x0c)`; the same pattern appears in `ai_count_activatable_table_cards`, `ai_score_slot_for_synchro_material` and `ai_score_level_change_for_synchro`, and `ai_choose_name_copy_candidate` reads an Extra Deck list at player `+0x4e4` with that count (capped 15). Hypothesis (M): `+0x18` is the Extra Deck count and `+0x4e4` the Extra Deck list.
- Score from `ai_compare_plans(new, best)`: bit `0x10` 1,000,000 - record `+0x18`; bit `0x08` 800,000 + 10,000 per opposing monster removed; bit `0x04` 300,000 + damage gain (plan `+0x08`); bit `0x02` the `+0x0c` gain. A score >= 300,000 stops the search.
- The 0x34-byte `record` is a 13-word stat block: `ai_choose_hand_monster_by_stats` reads its `+0x18`/`+0x1c` as the summoned monster's ATK/DEF (M), so bit `0x10` prefers the lower-ATK winning summon.
- What the search keeps and restores together: working plan header, entries `0x09e27708` (0xa0 bytes), extras `0x09e277a8` (0x80), records `0x09e27828` (0x1a0), the scratch `0x09e27f90`-`0x09e27fd3` (0x44 bytes) and the summon choice `0x09e03080` (12 bytes). This confirms `ai-runtime.md`'s "Extra-deck summon plan scratch" range.
- `ai_summon_choice +0x08` (`0x09e03088`): `ai_score_extra_deck_fusion_candidate` refuses an Extra Deck index whose bit is set there, and `ai_choose_name_copy_candidate` skips those bits. Hypothesis (M): a mask of Extra Deck indices already used or tried, which answers the open question in `ai-runtime.md` in part.

#### LP-change record (12 bytes) used by `ai_estimate_lp_change`

Built by `ai_collect_activation_lp_effects` (`0x09d3857c`) and `ai_collect_activation_lp_gain_effects` (`0x09d38bb8`), consumed by `ai_apply_lp_change_record` (`0x09d38d7c`). H for the field accesses, M for the meanings:

| Offset | Type | Meaning |
| --- | --- | --- |
| `+0x00` | u16 | Side whose LP changes |
| `+0x02` | u16 | Card id causing it (0 = empty record) |
| `+0x04` | u16 | Amount per occurrence (1,000, 500, 400, 300, 3,000) |
| `+0x06` | u16 | Count (copies active) |
| `+0x08` | u16 | Timing: 0 for the activation's own cost/gain, 1 for reactions, `timing + 1` for records derived by `ai_apply_lp_change_record` |
| `+0x0a` | u16 | Kind: 0 normal, 1 counter/marker based (skipped when the apply call's first argument is set), 2 one-shot derived record (zeroed after use) |

Lists hold 32 records; derived records go to the first free entry from index 1. `ai_collect_activation_lp_effects` returns NULL (no estimate) when the board-view flags forbid it: own view (`0x09e28010 + side * 0x30c`) bit 1, or bit 2 unless the flags argument has bit 1; the other view's bit 0.

#### Summon-mode bits (`ai_filter_summon_mode_flags`, 0x09d35920)

Bit tests (H): `0x10` Attack Position and `0x40` Defense (as in `ai.md`), `0x04` and `0x20` unnamed, `0x80` = "refine `0x50` with `ai_filter_summon_flags_by_board_cards`" (consumed). Sub-checks clear groups: `ai_check_summon_card_conditions_a` `0x74`, `_b` `0x34`, `_c` `0x50`, `_d` `0x10`, `ai_check_summon_by_effect_card_conditions` `0x04`, the Spirit rule `0x30`, the source-card list `0x14`. The fourth argument is a second card id (`ai_rate_extra_deck_summon_by_card` passes the summoned card itself); hypothesis (M): the card whose effect performs the summon. `ai_filter_positions_by_lethal_attack` reuses `0x10`/`0x40` as "may be placed in Attack / Defense Position without a lethal attack".

#### Other structures and globals

- Effect list nodes (H): head u16 at player block `+0x11a` (side's list) or slot `+0x0a` (`0x09e2a566 + slot * 0x14`, slot list); 10-byte nodes at `0x09e2c7cc + n * 10`: `+0` u16 key (card id), `+2` low nibble type, high nibble a value (read by `ai_score_candidate_by_card_state`), `+4` u16 value / card instance, `+8` u16 next. Readers: `ai_find_candidate_skipping_gold_sarcophagus`, `ai_find_final_countdown_candidate`, `ai_score_target_for_1890`.
- Chain links (H): 24-byte links at `0x09e28cb4` (`0x09e289b4 + 0x300`), count `0x09e28e38` (`ai_mask_out_same_card_link_targets`).
- Field slot flags word `+0x10` (`0x09e2a56c + slot * 0x14`), bits read here (H for the tests, L for meanings): 1 and 3 disabled (as `ai.md`), 2 effect suppressed for estimates, 7 (0x1f1e's condition), 8, 10 (required by `ai_rate_slot_threat_with_links`; valuable-card test in `ai_choose_target_for_1c69`), 22, 23 (`ai_score_low_level_cost_monster`), 25 (`ai_can_slot_attack_this_turn`). Slot word `+0x0c` holds a coin result for Arcana Force monsters (`ai_is_slot_card_liability`, `ai_reject_candidate`).
- Rule flags `0x09e03070`: bit `0x40` enables the name filter of `ai_filter_targets_for_1ba2`; bit `0x200` is set by `ai_choose_exodia_piece_candidate` when the chosen pieces complete the hand (both new, H for the access).
- Board-view flags (`0x09e28010 + side * 0x30c`): bit `0x08` refuses summon bits `0x14` for ATK < 1,401; `0x10` and `0x20` used by `ai_reject_candidate`; bits 0-2 gate LP estimates (above).
- Duelist registration block `0x09e02990 + side * 0xc0` (`ai_choose_declared_card_name`): `+0x1c` a card count and `+0x28` a u16 card list, read as the opponent's registered deck when nothing visible is left (M).
- Battle plan attack-order records: `ai_choose_target_for_1a0b` reads u16 `+4` of record i (`plan + 0x148 + 0x10 * i`) as the opposing slot attack entry i targets (M), a field `ai-runtime.md` lists as unknown.
- `0x09e2d1e0`: `ai_score_candidate_by_card_state` computes card `0x169c`'s countdown as `(0x09e2d1e0 + 1) - effect value + markers` and expects 19/20, so `0x09e2d1e0` is very probably the turn counter (M). `ai_filter_summon_mode_flags` refuses a Spirit summon when it is 0 and `ai_get_spirit_return_mode` is 1.
- `0x09e28f80` (AI evaluation depth, negative during evaluation per `ai-helpers.md`): decremented around simulated fusion material picks (`ai_score_extra_deck_fusion_candidate`) and incremented while `ai_pick_least_valuable_slot` computes a real target mask.
- Spell-search priority (`ai_get_spell_search_priority`): a fixed rank 1-12 for 12 card ids, used only by the `0x1638` rule of `ai_reject_candidate`.

#### Name mismatches

- `ai_is_position_unlocked` (`0x09d399dc`): tests lock cards on a face-up monster in either position and returns false for any Attack Position monster under `0x1d5a`; it works as an attack/position permission for `ai_can_slot_attack`, not only a position lock (M).
- `ai_find_elemental_hero_fusion_candidate`: the code is a rule table over eight material ids; the family is supported only by the ids, keep as is.
- `ai_choose_target_for_12e2`, `ai_choose_a_counter_target`, `ai_choose_target_for_1b52`, the `ai_choose_target_for_<id>` choosers of pack 07 and `ai_choose_slot_target_by_threat` return a bare slot in some cases and `side | slot << 8` in others (see each row); the names do not tell which.
- `ai_score_target_for_0ec8` returns the scratch word `0x09e03068` set by `ai_choose_declared_attribute`, not a score computed from the slot.
- Ghidra types as `void` several functions whose callers use the tail-call value: `ai_filter_hand_summon_mode_flags`, `ai_rate_extra_deck_summon_by_card`, `ai_score_candidate_by_low_stats`, `ai_score_candidate_for_graveyard_pick`, `ai_get_candidate_level`, `ai_score_crystal_beast_by_missing`, `ai_score_candidate_by_level_and_stats`, `ai_score_candidate_by_stats_vs_board`, `ai_score_candidate_vs_board_krebons`, `ai_score_candidate_by_low_atk_prefer_normal`, `ai_estimate_slot_upkeep_lp_change_own`.

#### Open questions (band 3)
- Skipped: the 8-byte thunks `ai_call_rate_slot_threat_with_links` (`0x09d49f3c`) and `_alt` (`0x09d49f44`) probably load a different third/fourth argument in the delay slot; `ai_choose_target_for_1c25` (`0x09d5255c`) calls `ai_choose_cost_for_1c25` without a visible depth argument. Read the disassembly.
- `ai_rate_slot_threat_if_link` and `ai_score_candidate_by_low_stats` pass their registers through to the callee; their parameter counts were taken from the callees (M).
- `ai_score_a_counter_target`: the decompiled `-300` adjustment for field `0x1bd9` clears positive values (`if (0 < x) x = 0`), which looks like a lost `max(x, 0)`; check the disassembly.
- `ai_choose_declared_card_name` (kind `0x4d`) tests a fixed Graveyard-list word (`0x09e2aa80 + side * 0xb3c`, one word before the list) instead of the chosen card; probably a bug in the original or a decompiler artefact.
- `ai_score_target_for_12e2` compares the re-simulated attack value with the LP of the side that takes the monster; the meaning of the three flag bits returned by `ai_sim_current_attack` is open.
- Kind-1 LP records are ignored when `ai_apply_lp_change_record`'s first argument is set; what that argument means is open.
- The meaning of `duel_core_count_named_cards_both_sides` in `ai_filter_targets_for_1ba2` (targets are kept only when it returns 0) is unclear.
- Confirm `0x09e2d1e0` = turn counter and `0x09e03088` = tried Extra Deck mask in PPSSPP.

### Findings from band 4

Material from the fourth fifth of the undocumented `ai` functions of `rel_duel_eng` (221 functions, `0x09d55250`-`0x09d7adbc`: per-card target/cost/hand-card choosers and their scorers, the hand-card chooser `ai_choose_hand_card_by_card`, summon-from-hand choosers, and about 150 per-card AI handlers). Basis: Ghidra decompilation read in full; nothing traced in PPSSPP.

#### Chooser/scorer idiom (shuffle and pick)

About 60 choosers share one inlined body (H): collect the slots 0-10 of one side whose bit `side * 16 + slot` is set in a slot mask into a local `u16[11]` list, Fisher-Yates shuffle it with `duel_core_random(i + 1)` from the end, then walk the list keeping the slot whose score is strictly greater than the best so far (start 0). Result: the best slot with a positive score, -1 when none is positive; ties are broken by the shuffle, so equal scores pick at random. Scores are tiered by adding 100000-500000 (sometimes 600000, 1000000, 2000000) to an ATK/DEF value, so the tier dominates and the stat breaks ties; a few scorers return small priorities (`ai_score_target_for_1c8a`: 0-20, `ai_rank_card_by_genre`: 0-13). Variants pass the score function as a pointer (`ai_choose_position_change_target`, `ai_choose_target_for_1d78_1d7b`) or call `ai_pick_field_slot_by_score_fn(mask, score_fn)`, which takes the slot mask of both sides.

Return formats (H): a plain slot index (many `ai_choose_target_for_*`), a packed field slot `side | slot << 8` (`ai_choose_fog_counter_target`, `ai_choose_target_for_13fe_1c57_1d1a`, the `ai_choose_hand_card_by_card*` family), or a packed hand location `side | 0x0b00 | index << 16` (`ai_choose_hand_card_by_card`, `ai_choose_random_hand_card_by_filter`); -1 = none, -2 = refuse (card `0x198d` in `ai_choose_hand_card_by_card` while `0x09e28f64 != 0`).

#### Link scratch words used by choosers (H for the accesses, M for the reading)

The 24-byte chain link / ctx has words `+0x08`, `+0x0a`, `+0x0c`, `+0x0e`, `+0x10`, `+0x12` that the per-card choosers overwrite with precomputed thresholds (best attacker ATK, best monster value, dominance flags, counter counts, LP-derived bounds, a mode). The matching scorer has only `(side, slot)` parameters and reads the same words through the current link pointer `0x09e28e44`, so the chooser's ctx is that current link (M: the pairing is consistent in every chooser/scorer pair read; the pointer identity was not traced). Examples: `ai_choose_target_for_138d` writes `+0x0a` battle mode 1/2, `+0x0c` mass-attack-trap flag, `+0x0e` opposing best attacker ATK, `+0x10`/`+0x12` LP-derived ATK bounds; `ai_choose_target_for_1efd` uses bytes `+0x08 + Attribute` as per-Attribute counts and `+0x10` as an Attribute mask; `ai_choose_target_for_1e3f` stores free monster zones at `+0x08 + 2·i` (overlapping `+0x0e`..`+0x12` when several zones are free). Byte `+0x07` bits 1-7 are also used as a sub-mode by several cost choosers (`ai_choose_cost_for_1328`, `_1eca`, `_1afd`, `ai_choose_cost_for_14e4_1ca9`), and `duel_effects_record_link_slot` + "clear `+0x07` bits 1-7" is the idiom to evaluate a target mask for another card position.

Other ctx fields read here: `+0x02` bits 6-11 event code (`0x24` = spell/trap table; `0x12`/`0x13` attack declared; `0x17` used by `ai_choose_special_case_summon_from_hand`), `+0x03` bit 6 switched controller, bits 4-5 handler-table selector (non-zero changes many handlers' branch), bit 7 a target-mask mode set temporarily before `ai_get_target_mask` (`ai_choose_cost_for_1e8b`, `ai_handler_tribute_to_destroy_stronger`, `ai_handler_check_targets_by_dominance_1bda`); `+0x04 >> 5` the card instance (table `0x09e2bbcc`; several handlers accept at once when that instance is card `0x1935` while the ctx card is not); `+0x06 >> 1` the link's target count; `+0x0c` an effect option (set to 1/2/3 before evaluating an option, e.g. `ai_handler_revive_monster_1eea`, `ai_handler_check_lp_14e0`).

#### Battle and simulation globals seen here

- `0x09e28620` attacking side, `0x09e2863c` attacker slot, `0x09e28624` defending side, `0x09e28640` attack target slot (H: always paired as side/slot in the packed results of `ai_choose_target_for_1763`, `_1eca`, `_1328`; matches `battle.md`).
- `0x09e27fa4 + side · 0x18` (byte): the target slot chosen by the last `ai_simulate_attack` for that side; `ai_choose_hand_card_by_card_b` returns it for code `0xd` (M).
- `0x09e27fb0`/`0x09e27fb4`/`0x09e27fb8 + side · 0x18`: three per-side loss words of the attack evaluator, summed as a score by `ai_score_adjacent_zone_move` (M; same block as `0x09e27fb8[defender]` in `ai.md`).
- `0x09e27fd4`/`0x09e27fd8 + side · 8`: results of `ai_sim_battle_resolve`; the 19b3 scorers compare `0x09e27fd4[side]` with the side's LP (damage taken, M) and test `0x09e27fd8` as "destroyed" (M).
- 68-byte attack result (`ai_eval_attack`): class at `+0x02` (0 = no attack, 5 = special class scored highest), per-side loss words at `+0x20`/`+0x24`/`+0x28 + side · 0x18` (consistent with `ai.md` round 2).
- Battle plan attack-order records (`plan + 0x144`, 16 bytes, scanned while record `+2` is non-zero): record `+4 == 5` marks a direct attack (`ai_handler_check_copies_1e6b`, M); `0x09e27828` (working plan `+0x144`, record 0 `+0`) is compared with 5 by `ai_handler_check_cost_1927` (meaning open). Plan `+0x14` (opponent LP after the attacks) of the opponent's saved plan is used as "the opponent's plan kills us" (`ai_handler_check_candidates_1712`); `+0x22` "plan wins" (`ai_handler_revive_monster`); `+0x02` and `+0x08` are compared with a simulated card effect in `ai_handler_check_lp_1dbf`.

#### Player block and slot fields used

- Player block: `+0x0c` hand count (list `+0x124`), `+0x10` Deck count (list `+0x304`; entry 0's instance is tested against markers by `ai_handler_check_copies_1599`), `+0x14` Graveyard count (list `+0x55c`), `+0x18` Extra Deck count, `+0x1c` banished count (list `+0x7b4`) (H).
- Field slot (20 bytes at `+0x34 + slot · 0x14`): `+0x06` position, `+0x08` face-up (temporarily set to 1 by several choosers to evaluate a flipped card and restored), `+0x0a` head of the slot's effect list (pool `0x09e2c7cc`, 10-byte records, `+2` low nibble kind, `+4` value, `+8` next; kind >= 10 = equip link, walked by `ai_score_cost_for_1e49`), `+0x0c` a per-slot value word compared with the turn counter `0x09e2d1e0` (`ai_score_target_for_1326`) and with a coin call + 1 (`ai_score_target_for_1dd8`/`_1dda`), `+0x10` flags (bit 2 effect disabled for the AI's "active effect" tests, bit 8, bit 10, bit 20, bits 22-23 tested as a pair by `ai_score_defusion_target`).
- Field zone face-up word `0x09e2a62c + side · 0xb3c` (slot 10 `+0x08`): the "field zone empty or face-down" gate of the field-spell handlers (`ai_handler_check_field_spell_*`, `_board_1eec`, `_candidates_0eb7`); the stand-in `0x10f4` is the face-down field card (`ai_handler_check_board_150b`).
- Chain link array at `0x09e28cb4 + 0x18 · i`, counts `0x09e28e34` (used by `ai_choose_cost_for_14e6`) and `0x09e28e38` (used by `ai_can_special_summon_card`); two different count words, meaning of the difference open.

#### Summon choice record (`0x09e03080`)

Confirmed accesses (H): `+0x00` hand index / slot, `+0x03` from-field flag, `+0x04` set face-down, written by `ai_choose_tribute_summon_from_hand`, `ai_choose_special_case_summon_from_hand`, `ai_choose_summon_from_hand`; `+0x01`/`+0x02` (`0x09e03081`/`0x09e03082`) read by `ai_can_special_summon_card` as the side and slot of the simulated summon; `+0x08` (`0x09e03088`) saved, zeroed and restored around `ai_eval_extra_deck_summon` (`ai_handler_check_candidates_1ef0`, `ai_choose_target_for_1e32_1e33`). Tribute count for summons from an effect: `(0x09e290f0 & 0x3f) >> 4`; `0x09e290f0` bit 0 is another flag of the same record (summon record `0x09e290bc` area, `summon.md`).

#### The shared slot-choice gate (inlined in about 20 handlers)

`ai_handler_equip_stat_boost`, `ai_handler_check_discard_1661_165f`, `ai_handler_check_battle_1322_1edf`, `_169a`, `_1b51`, `_1d46`, `ai_handler_check_targets_150d`, `_1514`, `_1a9e` and (first half only) `_159e`, `_1232_19d8`, `_1ee3`, `_1237`, `_165d`, `_1c8c`, `_1e46`, `_1e01`, `_1eed` contain the same inlined test (H):

1. `ai_is_past_summon_step()` must hold; a non-monster card with a handler-table selector (`ctx +3` bits 4-5) fails;
2. cards `0x1c38`, `0x1309`, `0x10e7`, `0x10e0`, `0x10df`, `0x10d6` pass only while the turn counter `0x09e2d1e0 < [0x09e029ac] + [0x09e02a6c]`;
3. full form: `s = ai_choose_slot_for_ctx_raw(ctx, side, -1, 0)`; accept when `s >= 5` (a "preferred" pick, slot + 5), when the picked card is `0x1bb5` or one of 13 ids (`0x1b89`, `0x1b7f`, `0x1b7e`, `0x1acf`, `0x18b6`, `0x186c`, `0x186b`, `0x182d`, `0x179d`, `0x13c3`, `0x1399`, `0x1193`, `0xeca`), or when its ATK > 1,299; short form: `ai_choose_slot_for_ctx(ctx, side, -1, 0) >= 0` (sometimes restricted to zones 0-4 or to an original-ATK bound).

This is the same decision as the shared `ai_handler_equip_strong_monster` (`ai-helpers.md`, "ATK > 1,299"), inlined. The side is the owner in most copies but the opponent in `ai_handler_equip_stat_boost`, `_1322_1edf` and `_169a` (H for the argument; purpose of passing the opponent side open).

#### Name mismatches

- `ai_choose_cost_for_1e49` (`0x09d5f120`) is a scorer, not a chooser: parameters `(side, slot)` of an equip card, returns the best `ai_score_cost_for_1e49` value (not a slot); no direct caller.
- `ai_choose_cost_for_tribute_cards` (`0x09d64b68`): the code does not choose Tributes by value; for its card list it returns the own slot that the previous chain link targets (`ai_is_slot_targeted_by_previous_link`), i.e. "spend the card that is about to be hit". The same body serves `ai_choose_target_for_179f_17b8_1889_1c9f`.
- `ai_handler_equip_stat_boost` (`0x09d6c8a8`) evaluates `ai_choose_slot_for_ctx_raw` on the opponent's side (see the gate above); "equip boost" is not visible in the code.
- `ai_has_hand_monster_to_give_away` (`0x09d704b0`) returns the opponent's hand count (not 0/1) for hand cards `0x11f5` and `0x1e2d`.
- `ai_handler_check_board_1630_16a8`, `ai_score_cost_for_1e8b`, `ai_choose_target_for_138d`, `_1e3f`, `ai_choose_cost_for_1c83` are decompiled as `void` although they end in a call whose result is evidently the answer (prototype given as `int`, M).

#### Code slips to keep in a port (H for the code, interpretation M/L)

- `ai_handler_check_targets_by_dominance_15df`: tests `L & 1 << (L & 31)` (the Level mask indexed by itself) where the monster's Level was evidently meant.
- `ai_handler_check_summon_15c7`: clears the sent hand card's index from a field-slot Tribute mask.
- `ai_score_cost_for_1e49`: the `+100000` bonus for result class 5 is overwritten by the next assignment (`+1` for any non-zero class).
- `ai_handler_check_cost_1927`: after the simulation sets slot flag bit 23 or 22 instead of restoring the original bits 22-23 of the cost slot.
- `ai_handler_tribute_to_destroy_stronger`: leaves ctx `+3` bit 7 set when no target is found.
- `ai_choose_hand_card_by_card`, card `0x1a31`: with `0x190b` face-up it uses the count of `0x1917` in hand as a hand index.
- `ai_choose_tribute_summon_from_hand`: `ai_wants_set_position` is applied to a hand entry indexed from the outer Tribute counter, not to the candidate.
- `ai_score_target_for_1e3f`: the candidate whose index equals link `+0x10` would go into the target slot, but the index never reaches that value; the function returns 0 for own monsters in the decompilation, discarding `ai_score_plan_improvement` (needs the disassembly).
- `ai_handler_check_dominance_1257`: uses the constant side 0 for the player slot, and reads the cached dominance right after attaching an effect (only meaningful if the cache is stale).

#### Hand-card and summon choosers

`ai_choose_hand_card_by_card` (`0x09d6929c`) is the entry for every pending selection the AI answers for an effect: it chooses or builds a filter (`duel_effects_select_filter_hand_candidate`, `duel_core_get_pending_selection_filter`, `ai_filter_link_controller_hand_card`), builds the field mask, tries the field branch `ai_choose_hand_card_by_card_b` (a compare chain on about 150 card ids and the small codes 0-0xd, which look like generic selection kinds: `0xb` Tribute, `0xc` ritual monster, `0xd` battle target; M), then hand branches; mode = "AI evaluation" (`0x09e28f80 < 0`), raised to 2 when the dominance is below -2. It stores the side in `0x09e2d274` and `0x09e2d2e4` (prompt state, `duel-runtime.md`). The summon choosers (`ai_choose_summon_from_hand` -> `ai_choose_special_case_summon_from_hand` -> `ai_choose_tribute_summon_from_hand`) fill `0x09e03080` and return 1/0.

#### Open questions (band 4)
- `0x09e029ac + 0x09e02a6c`: the turn limit for cards `0x1c38`, `0x1309`, `0x10e7`, `0x10e0`, `0x10df`, `0x10d6` in the shared gate. Both words lie in the duel-setup area near the duelist kinds `0x09e02998`; who writes them (tutorial / story duel scripts?) is unknown.
- Whether the chooser's ctx is always the current link `0x09e28e44` (the scorers read their thresholds from it); confirm with a breakpoint on any `ai_score_target_for_*`.
- Meaning of the small selection codes 0-0xd in `ai_choose_hand_card_by_card(_b)`, of `0x09e29050` (compared with card `0x1c0b`) and `0x09e29064` (a count used by card `0x1ceb`).
- The two chain counts `0x09e28e34` and `0x09e28e38`.
- `0x09e27828 == 5` in `ai_handler_check_cost_1927` (working plan record 0 `+0`), and the meaning of attack-order record fields other than `+2` and `+4`.
- `ai_choose_slot_for_ctx_raw` called with the opponent's side by three equip-type handlers: is that the target side of an equip that weakens, or a slip?
- `ai_score_target_for_1e3f` and the five `void`-decompiled functions: confirm their return values in the disassembly.
- `ai_is_ranked_card_with_low_atk(side)` is called with one visible argument from `ai_has_hand_monster_to_give_away`; it may take hidden register arguments.

### Findings from band 5

Notes from batch A5 (182 `ai` functions of `rel_duel_eng`, `0x09d7af40`–`0x09d9e204`): per-card handlers `0x09d7af40`–`0x09d8885c`, the activation gate, the main-phase step functions, the board view builder and the declaration/answer helpers. Basis: Ghidra decompilation only (no PPSSPP traces).

#### Interest records (board view `+0x0c`, 32 × 24 bytes) — layout now read

Read from `ai_card_matches_interest_record` (`0x09d8f1e4`), `ai_board_count_interest_matches` (`0x09d8f53c`), `ai_rate_card_interest` (`0x09d8f7f0`) and the writers in `ai_analyze_board` / `ai_board_note_combo_interests` (H for the reads, M for the meanings). Record `r` of side `s` is at `0x09e28014 + s·0x30c + r·0x18`; the list ends at the first record with weight 0.

| Offset | Type | Meaning |
| --- | --- | --- |
| `+0x00` | u16 | Weight (wanted count); 0 = end of list |
| `+0x02` | u16 | Matches already present: rewritten by `ai_board_count_interest_matches` (Graveyard list when `+6`, else banished list when `+7`, plus selected candidates while the candidate stack `0x09e03024` is non-empty). Corrects `ai-runtime.md` ("copied, meaning unknown") |
| `+0x04` | s16 | Card id: > 0 only that card, < 0 every card except `-id`, 0 generic |
| `+0x06` | u8 | Wanted in the Graveyard (location `0x0e` allowed) |
| `+0x07` | u8 | Wanted banished (location `0x0f` allowed) |
| `+0x08` | u16 | "For summoning": the card must be summonable; in `ai_rate_card_interest` it moves the record's score into the summon-material term |
| `+0x0a` | u16 | Level compare mode: 1 equal, 2 at least, 3 at most |
| `+0x0c` | u16 | Level (0 = any) |
| `+0x0e` | u16 | Attribute (0 = any) |
| `+0x10` | u16 | Race (0 = any; off-field race for Graveyard) |
| `+0x12` | u16 | Archetype + 1 (0 = any; `card_db_is_in_archetype(card, v − 1)`) |
| `+0x14` | u16 | Kind selector: 1 monster subtype, 2 spell/trap icon, 3 ATK cap |
| `+0x16` | u16 | Kind value: subtype 0 any / 1 Normal / 2 Ritual / 3 Fusion / 4 Synchro / 5 Gemini / 6 Effect / 7 Tuner; or the icon; or ATK cap ÷ 100 |

Score (`ai_rate_card_interest`): per matching record `min(10, weight + 1 − count)` (1 when already satisfied) summed into g (`+8 == 0`) or s (`+8 != 0`); result `max(1, min(10000, 10g) − a)` plus, for s, `a + 100·clamp(level − 4, 0, 9) + max(9999, 1000·(min(s, 90) − 1))`, with `a` = estimated ATK / 100 clamped 1–100; 0 when `ai_is_card_worth_keeping`.

#### Board view corrections (`ai_analyze_board`, `0x09d91fe8`)

- `+0x04` "summon slack" is `0x80 − u16 +0x06` (the AI activation counter), clamped at 0; under `0x1de4` it is `2 −` the summons completed this turn (player block `+0x20`, `0x09e2a548`), **not** the hand size as `ai-runtime.md` says (H).
- Flag word `+0x08` bits: 0 opponent cannot take effect damage; 1 own side cannot; 2 own `0x1850`/`0x15a7` in zones 5–9 with slot flags bit 20 clear; 3 `0x1398` active (cleared by own `0x1d60`); 4 `0x159d` active (cleared by own `0x158b`); 5 opponent `0x1c7b`; 6 opponent `0x1cb9` while LP gain is worthless; 7 opponent `0x1ce5`; 8 (`0x100`) own `0x1de2` (the hand-card threshold flag of `ai_evaluate_activation`) (H).
- AI rule flags `0x09e03070`: `ai_analyze_board` keeps bits 0–4 and sets `0x40` (`0x1343`), `0x80` (`0x1632`; this is the writer the open question in `ai-helpers.md` asks for), `0x100` (`0x1d5a`). Bit `0x10` is set by `ai_handler_check_board_1c70`, bit `0x200` is tested by `ai_handler_check_discard_1845` (writer not in this batch).
- Combat tricks registered: `0xeab` (with a face-up Fusion monster), `0x12cb`, `0x1409` (with targets, `ai_card_has_targets`).
- The opponent's hand is noted only for revealed cards (`duel_core_is_hand_card_revealed`) — confirms the M claim of `ai.md`.

#### Main-phase state machine (sub-states `0x09e03000`)

- Step 0 `ai_main_state_open`: 0 view + plan; 1 `ai_set_deferrals_for_planned_summon`; 2 table A; 3 `ai_try_set_spell_traps(side, 0)`; 4 `ai_try_hand_special_summons`; 5 comeback (table D); 6 `ai_try_main_cards`; 7 clear `0x09e03070` bits 0–1, return 1. Corrects the order in `ai.md` (set spell/traps comes before the hand Special Summons; the comeback step always runs, table D's length handles "losing").
- Step 1 `ai_main_state_summon`: sub-states 0–9 (summary in the row). Turn 0 (`0x09e2d1e0 == 0`) skips the step. A summon needs the choice flag `+5` clear, `duel_core_has_normal_summon`, `ai_has_lp_above_500_per_active_132c`, Normal Summon or set possible and card `0x1102` not active on the opponent's side. Sub-state 6 leaves the step when dominance ≥ 0 and the plan value is non-zero.
- Step 2 `ai_main_state_summon_extra`: returns `1 − step` (back to step 1) once per turn for the `0x1c33` / `0x1d20` extra Normal Summon markers (bits 0/1 of `0x09e03070`).
- Step 4 `ai_main_state_after_battle`: loop counter `0x09e02ffe`; returns `2 − step` (back to step 2) while `(counter & 3) < 2` and battle is still possible.
- Step 6 `ai_main_state_end`: sub-state 4 returns `1 − step` (back to step 1) when the hand is exactly one `0x147b` and `ai_try_final_normal_summon` succeeds.
- Actions are submitted through `duel_core_submit_player_action(side, location, index, code)`: code 2 hand Special Summon by procedure, 3 activation from a list location, 5 flip summon, 7 set from hand, 8 to Attack Position, 9 to Defense Position (M for the code meanings, H for the call sites); `0x09e2d274` = acting side, `0x09e2d25c = 1` after most actions.

#### Activation gate (`ai_evaluate_activation`, `0x09d88c34`)

- Returns 1 accept, 0 refuse, and **−1 when it issued a position change instead** (cards `0x1f17`, `0x1e33`, `0x1e32`, `0x1e0a` via the scratch slot `0x09e03068`; `0x1430`, `0x142a`, `0x12cb`): it flips a face-down own monster up first (`ai_try_change_position_to`). This corrects `ai.md` ("re-checks the target against the battle plan").
- Deferral is by spell icon: a selector-0 spell whose bit `1 << icon` is in `0x09e03074` sets that bit in `0x09e03078` and is refused. `ai_set_deferrals_for_planned_summon` fills `0x09e03074` (`0x1964` → bit 0; eight cards → all bits; `0x1520` → `0x21`).
- A `0x1a9d` marker on the opponent's player slot with value = card makes the gate accept when 1000 per marker would kill the controller (read literally).
- `ai_try_table_entry` maps its mode: mode 0 → activation mode 2, any other → 0 (so `ai_try_card_from_table`, which passes 1, activates in mode 0).

#### Card-specific stubs decompiled through shared code

`0x09d82430`, `0x09d8244c`, `0x09d82468`, `0x09d82484`, `0x09d824a0`, `0x09d824bc` are 28-byte functions; Ghidra follows each into an unowned shared body and propagates the stub's constants (target card, number of costs). The rows describe the specialised result (M). A disassembly read of the shared body (after `0x09d824d8`) would confirm the register interface.

#### Name mismatches

- `ai_choose_special_summon` (`0x09d92d5c`): starts **Normal (or Gemini) summons** (`duel_core_begin_summon_from_hand(1, 0, 1)`) of hand monsters chosen by ~40 per-card conditions; nothing in it special-summons. Suggested: `ai_choose_conditional_normal_summon`.
- `ai_get_hand_dump_mode` (`0x09d8acec`): returns a 0–3 urgency mode for setting hand spell/traps; "dump" is a guess (L).
- `ai_choose_card_blocker_mill_count` (`0x09d95b50`): only the 500-per-card boost count is certain; "blocker"/"mill" unverified.
- `ai_eval_ice_master_targets` (`0x09d81da4`): the code counts opponent monsters with type-`0x10` counters at equal/higher ATK; name plausible, not verified against card text.

#### Possible original bugs (read literally)

- `ai_handler_check_battle_1be4`: moves slot records directly without setting the dominance-stale flag `0x09e03070 & 0x20`, so `ai_get_battle_dominance` probably returns the cached value and the simulation has no effect (M).
- `ai_handler_check_lp_1e79`: loops forever if `ai_choose_cost_as_side` returns −1 with a non-empty mask (L: depends on the chooser).
- `ai_handler_tribute_for_damage`: compares `out[opponent] < (1 − own side)` instead of `< 0` (H for the code).
- `ai_handler_check_committed_15a5` and `ai_eval_damage_combo`: compare one side's loss with the other side's LP (crossed, like `ai_compare_plans`).
- `ai_choose_attributes_by_owned_cards`: picks the same bucket `count` times.
- `ai_handler_check_summon_1f2d`: divides by the deck size without a zero check.

#### No-cheating claim

`ai_guess_hand_card_type` (`0x09d9d88c`) reads the real card types of the first half of a **hidden** hand and only guesses the rest (H). So the AI does read part of the opponent's hidden hand for type-guess effects (`0x153f`, `0x1519`); `ai.md` ("The AI never reads face-down cards") holds for the field, not for this guess.

#### Other structures touched

- Summon record `0x09e290bc` (`summon.md`): `+0x34` flag byte `0x09e290f0` bits 0–1 = 3 while the AI picks materials, bits 4–5 = 3 during `ai_handler_check_candidates_1a67` / `ai_choose_range_number`; picked list `0x09e290c8`, count `0x09e290c6`.
- `0x09e03088` (summon choice `+0x08`): bit per Extra Deck index already evaluated by `ai_eval_extra_deck_summon` in the current pass (first pass sets, retry pass refuses); cleared by `ai_try_hand_special_summons`. Answers the open question in `ai-runtime.md` (M).
- `0x09e03068` scratch word also holds a **function pointer** (procedure material filter for `0x1e20`, called by `ai_filter_unpicked_hand_card`) and the reason index 1–8 of `ai_choose_attribute_for_chameleon`.
- Temporary links: `ai_eval_flip_effect` and the position evaluators build their link at chain index `0x09e28e38`; `ai_try_location_cards` at the link count `0x09e28e34`.
- Ctx fields used as handler scratch: u16 `+0x0a`, `+0x0c` (per-card parameter read by the effect filters), `+0x12` (draw count for `ai_handler_draw_if_safe`), `+7` bits 1–7 (recorded-value count), `+3` bit 7 and selector bits 4–5 (temporarily switched; some handlers leave them changed).
- Attack redirect: `ai_eval_attack_redirect_option` writes criteria into ctx `+0x0c`–`+0x12`, read back by the score callback `ai_rate_attack_redirect_slot` through `0x09e28e44`.

#### Open questions (band 5)
- Meaning of the result sign and flag bit 0 of `ai_sim_current_attack` (used by the redirect and blocker functions).
- `0x09e28624` / `0x09e28640`: read as the attacked side / slot (M); confirm in `battle.md`.
- Slot flags word bit 10 (tested by several handlers) and bit 14 (set temporarily by `ai_handler_check_battle_1d1f`); slot word `+0x0c` (zeroed by `ai_handler_union_equip`).
- `duel_core_submit_player_action` code meanings beyond the call sites.
- Whether the 28-byte stubs pass more than the card id and cost count into their shared body.
- Return values of `ai_choose_declared_type_0eb4` / `_1357` (void in Ghidra, tail-called).

## Open questions

- Plan comparison: the logic and the header writes are read (see "Decision pipeline"); still open are the meaning of `+0x0c` (the evaluator word `0x09e27fb8`), whether the crossed guards of `ai_compare_plans` are intended, and the role of the plan review `0x09d0afd0`. Confirm with the PPSSPP checks listed above.
- The interest records at `0x09e28014`: layout of the flag bytes `+6`..`+0x17` and which handlers read them.
- The attack comparator `ai_is_better_attack_result` (`0x09d0c2e4`): the decompilation loses several assignments; the criteria order (result class `+2`, destroyed counts, damage sums) needs the disassembly or a trace.
- The 12 KiB yes/no evaluator `0x09d95f5c` and the 17,700-byte attack evaluator `ai_eval_attack` (`0x09d06188`, 68-byte result record) are only skimmed.
- Exact meaning of steps 3–5 and of `0x09d94740`, `0x09d899a8`, `0x09d8c79c` in the main loop.
- Whether `0x09c038a8` is "card revealed" (the no-cheating claim for the opponent's hand); confirm at run time.
- Who reads the character-table bytes `+0x44`–`+0x74` (`BOOT 0x0885b4ac`, `0x0885b4fc`, `0x0885b56c`, `0x0885b5dc`); if a module outside the current Ghidra project passes them to the duel, the "no personality" finding must be revised.
- `0x09e02cb0`, `0x09e02cb4` setters: set by the duel manager, meaning unknown.
- The priority tables are exported and checked (`docs/formats/ai-tables.md`, `tools/ai_tables.py`). The shared handlers are named and classified (`ai-helpers.md`) and the 600 single-use handlers are named by family ("Per-card handler families"); their individual constants are read from the decompilation, not documented one by one. The gates `BOOT 0x0885ff3c` / `0x0885fef0` are the spell / monster predicates (`effect-helpers-deck.md`). `0x09e28fa0` is the timing-event queue (`battle.md`), so R1–R3 are selected by the first queued event code (R1 `0x12`/`0x13`, R2 `0x14` start of the Damage Step, R3 `0x1b`); the meaning of `0x12` and `0x1b` is open.
