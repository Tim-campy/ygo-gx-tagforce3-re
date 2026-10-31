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

### State snapshots

The AI tests moves on the real duel state. `ai_simulate_attack`, `ai_plan_battle_with_tricks` and `ai_plan_battle` push a snapshot (depth `0x09e27fee`, at most 10) of the command/duel block `0x09e29914` (`0xc14` bytes) and the two player blocks `0x09e2a528` (`0x2de4` bytes) into slot `n` at `0x09dff93c + n × 0x39f8`, run rules code, then restore and re-run `ai_analyze_board` (H). The ten slots (`0x09e03334`–`0x09e27ebc`) make up most of the 150 KiB region `0x09e02ff8` cleared by `duel_core_reset`.

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
