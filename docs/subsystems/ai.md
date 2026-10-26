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
| `0x09dc79c0` (chain/response prompt; reads the pending link `0x09e290bc`) | 8 | `0x09d9e204` | `0x09d48720` among others |
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
| 0 | `ai_main_state_open` `0x09d8b184` | Rebuild view and plan; summon set-up (`0x09d9284c`); **table A** (105 opening spells such as Heavy Storm, Harpie's Feather Duster); field/flip checks (`0x09d8c79c`); hand spells (`0x09d899a8`); comeback table if losing; main table and position changes (`ai_try_main_cards`). |
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

## Simulation and scoring

### State snapshots

The AI tests moves on the real duel state. `ai_simulate_attack`, `ai_plan_battle_with_tricks` and `ai_plan_battle` push a snapshot (depth `0x09e27fee`, at most 10) of the command/duel block `0x09e29914` (`0xc14` bytes) and the two player blocks `0x09e2a528` (`0x2de4` bytes) into slot `n` at `0x09dff93c + n × 0x39f8`, run rules code, then restore and re-run `ai_analyze_board` (H). The ten slots (`0x09e03334`–`0x09e27ebc`) make up most of the 150 KiB region `0x09e02ff8` cleared by `duel_core_reset`.

### Battle plan

A plan is a `0x2e4`-byte record: the working plan at `0x09e276e4` and one saved per side at `0x09e279c8 + side × 0x2e4` (H for the copies). `+0x00`: five per-monster attack entries (`0x09d1c8e0(plan, i)`); `+0x08` `int` plan value returned by `ai_get_plan_value` (non-zero when the plan deals damage or wins a battle, hypothesis M); `+0x0c`, `+0x10`, `+0x14`, `+0x1c`, `+0x1e` are compared by `ai_compare_plans`; `+0x146` a flag read by the battle check; `0x09e2782a` is the chosen attacker slot + 1.

- `ai_plan_battle(side, mode, flag)` (`0x09d16568`): `mode = -1` full plan for the turn player, `-2` hypothetical (forces phase 2), `≥ 0` a given monster. Calls `ai_plan_battle_with_tricks`, then evaluates the result (`0x09d0afd0`) and, if the opponent is the turn player's AI side, also plans the opponent's best reply with Alligator's Sword-style checks (`0x09cfca08`).
- `ai_plan_battle_with_tricks` (`0x09d15b58`): builds the base plan (`ai_build_battle_plan` `0x09d1586c` → `0x09d0eeb8`, `0x09d12a24`, `0x09d1329c`), then replays it once for each **combat trick** listed at `0x09e27ff8` (up to 8 card ids, filled by `ai_analyze_board` with Battle Fusion, Shield & Sword and Limiter Removal when they can be used) and keeps the better plan (`ai_compare_plans` mask `0x1e`, `0x10` for Limiter Removal).
- `ai_compare_plans(a, b)` (`0x09d36d4c`): lexicographic comparison; bits `0x10`, `0x08` (`+6` u16 smaller), `0x04` (`+0x14` int larger), `0x02` (`+0x0c` int smaller). Field meanings open.
- `ai_choose_attack_target(side, slot, …)` (`0x09d0ca3c`): tries the direct attack (target 5) and each opposing monster, starting at a random slot (`duel_core_random(5)`), skipping targets already flagged in `0x09e27ff4`, scoring with `0x09d06188` (17,700-byte battle evaluator) and keeping the best by `0x09d0c2e4`.

### Battle dominance

`ai_eval_battle_dominance(side, slot_mask, simulate)` (`0x09d37548`, H for the formula): compares each side's best attacker (`0x09cf5c3c`; with `simulate`, only monsters that can actually win a battle, tested with `0x09d30ef0`) and returns +4 (our best beats theirs with ≥ 2,000), +2 (beats with less), −2/−4 symmetrically, −1 when our simulated best is weaker than our nominal best, 0 otherwise; `slot_mask` temporarily removes cards. `ai_analyze_board` caches it per side at `0x09e28008 + side × 0x30c` (simulated) and `+2` (plain); `ai_get_battle_dominance(side)` (`0x09d37490`) reads the cache (or recomputes under flag `0x09e03070 & 0x20`). A negative value switches on the comeback table D and changes many handlers.

### Summon choice

`ai_choose_normal_summon` (`0x09d1bb24`) simulates each hand monster (`0x09d177e0` plans the battle with the monster added) and rates it with `ai_rate_summon_candidate` (`0x09d1b338`). The rating is a tier plus a stat tie-breaker, kept in the 12-byte choice record at `0x09e03080` (`s8` hand index, …, `+3` from field, `+4` set face-down, `+6` u16 card needing special handling): tier 5 tribute summon that beats the tributes, 4 stronger than the opponent's best, 3 positive card-specific value (`0x09d1aec0`), 2 stronger than the previous best, 1 anything summonable; the stat is ATK, DEF or the larger, depending on the position. `ai_execute_summon` (`0x09d92afc`) picks tributes (`0x09cf4288`, `0x09cf4588`) and issues the summon (`0x09da5774`). `ai_choose_special_summon` (`0x09d92d5c`) is a compare chain over hand monsters that can be special summoned, with per-card conditions (about 40 card ids).

### Target choice

`ai_choose_target_by_card(ctx, ctx2, card, slot_mask, mandatory)` (`0x09d608d4`, 16 KiB, H): two generic pre-checks (`0x09d605c8`, `0x09d60760`), then a compare chain of 131 card ids with dedicated choosers, then generic fallbacks. Returns `side | slot << 8` or −1. Generic pickers (H): `ai_pick_monster_by_stats(side, mask, atk_sign, def_sign)` (`0x09d4a5c0`, best/worst ATK or DEF, +1 for monsters that can attack) and `ai_pick_slot_by_score(side, mask, score_fn)` (`0x09d4a9cc`); both shuffle the candidates first, so ties break randomly. `ai_choose_target_as_controller` (`0x09d64b18`) runs the chooser with the view side set to the card's controller; `ai_decide` (`0x09d649ec`) tries the mandatory then the optional variant and applies the choice (`0x09cbed3c`).

## Board view (what the AI knows)

`ai_analyze_board(view_side)` (`0x09d91fe8`, M) rebuilds, for both sides, a 0x30c-byte block at `0x09e28008 + side × 0x30c`: dominance values, `+4` a slack value (`0x80 − x`, or `2 −` the hand size under Summon Limit), `+8` flags (`0x09e28010`: bits for "opponent cannot draw", Necrovalley, King Tiger Wanghu, Cocoon Veil-like slots, By Order of the Emperor, Witch Doctor of Sparta, Dark Cure, Thunder King Rai-Oh, Sanguine Swamp …), and a 0x300-byte known-card table filled by `0x09d8fc24` from the 11 field slots, the hand and the extra deck. **The opponent's hand is only registered for cards that are revealed** (`0x09c038a8`); the AI's own hand is always registered (M: the branch is clear, the meaning of `0x09c038a8` is inferred). Global rule flags go into `0x09e03070` (Kotodama, Remove Brainwashing, Gaap the Divine Soldier). The AI context: `0x09e02ff8` AI side, `0x09e02ffa` view side, stack of 8-byte frames at `0x09e03028` with depth `0x09e03026` (`ai_push_context`).

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
| `0x09d1586c` | `ai_build_battle_plan(…)` | L | Clears attack flags, calls the plan builders. |
| `0x09d36d4c` | `ai_compare_plans(a, b) → mask` | M | 19 callers. |
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

## Open questions

- Meaning of the plan fields compared by `ai_compare_plans` and of the plan value `+0x08` (trace a CPU battle phase in PPSSPP with a breakpoint on `0x09d36d4c`).
- The 12 KiB yes/no evaluator `0x09d95f5c` and the 17,700-byte battle evaluator `0x09d06188` are only skimmed.
- Exact meaning of steps 3–5 and of `0x09d94740`, `0x09d899a8`, `0x09d8c79c` in the main loop.
- Whether `0x09c038a8` is "card revealed" (the no-cheating claim for the opponent's hand); confirm at run time.
- Who reads the character-table bytes `+0x44`–`+0x74` (`BOOT 0x0885b4ac`, `0x0885b4fc`, `0x0885b56c`, `0x0885b5dc`); if a module outside the current Ghidra project passes them to the duel, the "no personality" finding must be revised.
- `0x09e02cb0`, `0x09e02cb4` setters: set by the duel manager, meaning unknown.
- The priority tables are exported and checked (`docs/formats/ai-tables.md`, `tools/ai_tables.py`). The shared handlers are named and classified (`ai-helpers.md`); 600 single-use handlers remain unnamed. The gates `BOOT 0x0885ff3c` / `0x0885fef0` are the spell / monster predicates (`effect-helpers-deck.md`). `0x09e28fa0` is the timing-event queue (`battle.md`), so R1–R3 are selected by the first queued event code (R1 `0x12`/`0x13`, R2 `0x14` start of the Damage Step, R3 `0x1b`); the meaning of `0x12` and `0x1b` is open.
