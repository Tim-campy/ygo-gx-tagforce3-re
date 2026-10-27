# Duel phases and the turn state machine (work package 4)

How `gmodule/rel_duel_eng.prx` (runtime base `0x09be1400`) sequences a turn: the phase enum, where phase and turn state live, the step functions that advance them, the command queue that actually changes the phase, and how card effects test the phase. All addresses are runtime addresses in that module. Evidence is static (Ghidra decompilation, read-only); nothing here has been confirmed in PPSSPP yet.

## Summary

The turn is driven by **three nested step tables**, each a NULL-terminated array of step functions indexed by a global counter, with a sub-step counter that the step function advances itself:

| Level | Table | Index | Sub-step | Driver |
| --- | --- | --- | --- | --- |
| Duel | `0x09e01dbc` (2 entries) | `0x09e2d20c` | `0x09e2d214` | `duel_core_run_duel_flow` (`0x09dcb5a4`) |
| Turn | `0x09e01da0` (6 entries) | `0x09e2d210` | `0x09e2d214` | `duel_core_run_turn_flow` (`0x09dcb3d8`) |
| Battle Phase | `0x09e01dcc` (12 entries) | `0x09e2d220` | `0x09e2d224` | `duel_core_run_battle_steps` (`0x09ddabfc`) |

A step function returns non-zero when it is finished; the driver then clears the sub-step and increments the index. The step functions do **not** write the phase variable directly: they post engine commands (`duel_core_push_command`, `tutorial.md`), and the command executor changes the phase while synchronising with the presentation layer. Commands `10 + phase` enter a phase; command 4 is the turn change.

Confidence: high for the tables, drivers and the enum; medium for the meaning of individual sub-steps.

## Phase enum (`0x09e2d1e8`)

**Verified in PPSSPP (2026-10-26, [`results/2026-10-26-sessionA-part1.md`](../verification/results/2026-10-26-sessionA-part1.md), A1–A2):** values 0–5 and 7 (6 never written), the command sequence `2, 10–15, 3, 4` with bit 15 on the CPU's turn, the two writers (`duel_core_cmd_enter_phase`, `duel_core_next_turn`), the AI's temporary overrides, and the turn side `0x09e2d1d8` / turn counter `0x09e2d1e0` (starts at 0, +1 per turn).

| Value | Phase | Basis |
| --- | --- | --- |
| 0 | Draw Phase | `.ydq` `Phase=D` → 0 (`tutorial.md`); entered by command 10 from `duel_core_step_draw_phase`. |
| 1 | Standby Phase | `Phase=S` → 1; command 11 from `duel_core_step_standby_phase`; Standby-Phase card conditions test `== 1` (below). |
| 2 | Main Phase 1 | `Phase=M` → 2; command 12 at the start of `duel_core_step_main_phase`. |
| 3 | Battle Phase | `Phase=B` → 3; command 13 from Battle step 0; `duel_core_set_phase(3)` also sets the Battle step index to 1. |
| 4 | Main Phase 2 | Command 14 when the Battle Phase ends without skipping Main 2; `duel_core_is_main_phase` returns 1 for 2 and 4; `duel_core_can_enter_battle_phase` requires `< 4`. |
| 5 | End Phase | `Phase=E` → 5; command 15 from `duel_core_step_end_phase`. |
| 6 | (unused) | No store or comparison with 6 found among the 160 functions that reference the variable. |
| 7 | No phase yet (turn transition) | Set by `duel_core_reset` and `duel_core_next_turn`; stays until the Draw Phase is entered. `0x09ce10bc` does nothing while it is 7. |

Confidence: high. The phase menu confirms the numbering: its option mask is `1 << phase` (`8` Battle, `0x10` Main 2, `0x20` End), and the human's menu result is `0x0d + phase` (`0x11` Main 2, `0x12` End) (`duel_core_step_main_phase`, `duel_core_battle_step_select_attack`).

Battle Phase sub-steps are not separate phase values: the phase stays 3 and the position inside the Battle Phase is the Battle step index `0x09e2d220` (below).

## Turn and phase state

| Address | Meaning | Basis / confidence |
| --- | --- | --- |
| `0x09e2d1e8` | Current phase (enum above); 203 reads in 160 functions | Writers listed below. H |
| `0x09e2d1d8` | Side whose turn it is (0/1); 510 reads | Toggled by `duel_core_next_turn`; set from `0x09e029a8` at duel start (`0x09dc7dc4`). H |
| `0x09e2d1dc` | Copy of the turn side, taken by command 2 (begin turn) | `duel_core_cmd_begin_turn`. M |
| `0x09e2d1e0` | Turn counter, 0 on the first turn of the duel | `duel_core_next_turn` increments; `duel_core_can_conduct_battle` returns 0 while it is 0, so the first player cannot battle. H |
| `0x09e2d1e4` | Turn number at which a turn-limit count starts (`0xffff` = not started) | Written by `0x09dcad0c` and command 9; `duel_core_step_turn_start` posts command 9 at `+1` and `+4`, `duel_core_step_turn_end` ends a mode-2 duel at `+0`/`+3`. M (purpose: hypothesis) |
| `0x09e2d1ec` | Phase saved while card `0x151e` interrupts the turn | `0x09de07d0` saves it and re-enters it with command `10 + saved`. M |
| `0x09e2d1f0` | Duel result: 1 = local side (`0x09e02994 & 1`) wins, 2 = opponent wins, 3 = draw | `duel_core_check_duel_end`, `duel_core_step_turn_end`. M |
| `0x09e2d208` | 1 when the engine is idle (no chain, no pending work) | Computed each tick by `duel_core_run_turn_flow`; tested by `0x09c0d7fc`. M |
| `0x09e2d20c` | Duel-flow step index | `duel_core_run_duel_flow`. H |
| `0x09e2d210` | Turn step index (0 start, 1 Draw, 2 Standby, 3 Main/Battle, 4 End, 5 turn end) | `duel_core_run_turn_flow`; reset to 0 by `duel_core_next_turn`; `duel_core_set_phase` maps phase → step (0→1, 1→2, 2/4→3, 3→3, 5→4). H |
| `0x09e2d214` | Sub-step of the current turn (and duel-flow) step | Cleared on every step advance; 0x16 = "inside the Battle Phase" in the Main step. H |
| `0x09e2d218`, `0x09e2d21c` | Loop counters used by the End Phase and Battle-end steps | M |
| `0x09e2d220` | Battle step index (0–11; 12 = past the end) | `duel_core_run_battle_steps`. H |
| `0x09e2d224` | Battle step sub-step | H |
| `0x09e2d228` | Set when the Battle Phase ends straight into the End Phase (skip Main Phase 2) | `duel_core_battle_step_select_attack`, `duel_core_battle_step_start`; read by `duel_core_step_main_phase`. H |
| `0x09e2d248` | CPU decision for the next phase (3 Battle, 4 Main 2, 5 End) | `duel_core_step_main_phase`, `duel_core_battle_step_select_attack`. M |
| `0x09e2d258`, `0x09e2d26c` | Human input: "answer ready" flag and the chosen menu value | Same functions; values `0x0c` (continue), `0x0d + phase`. M |
| `0x09e27fe4` (`u16[4]`), `0x09e27fec` | Small stack for temporarily overriding the phase | `0x09d1586c` pushes the phase, forces 3 while it evaluates an attack, then pops. `0x09d16b38`/`0x09d16b84` force 2 and `0x09d54b78` forces 3 without the stack (all in the range used by AI code; hypothesis: AI look-ahead). M |
| `0x09e28620` | Attacking side; `0x09e2863c` attacking monster's slot | `duel_core_battle_step_select_attack`. M |

Writers of `0x09e2d1e8`: `duel_core_set_phase` (`0x09dc8208`), `duel_core_cmd_enter_phase` (`0x09dbc394`) and its six entry stubs, `duel_core_next_turn` (`0x09dbc184`), `duel_core_reset` (`0x09dc7cb0`), `duel_core_load_ydq` (`0x09dc94e4`), and the temporary overrides `0x09d1586c`, `0x09d16b38`, `0x09d16b84`, `0x09d54b78`, `0x09cecc54`, `0x09d1a820` (last two not read).

## The duel and turn drivers

`duel_core_run_duel_flow` (`0x09dcb5a4`) runs once per frame. It first lets the command queue run (`duel_core_process_command_queue`; while a command is in progress nothing else advances), then calls the duel-flow step `0x09e01dbc[0x09e2d20c]`:

1. `duel_core_run_turn_flow` (`0x09dcb3d8`): the whole duel, turn after turn. Returns 1 only when the duel is decided.
2. `duel_core_flow_report_result` (`0x09dcb224`): posts command 5 with the result `0x09e2d1f0`.
3. NULL: the duel is over; the driver copies the result to `0x09e02cb0`/`0x09e02cb4`.

`duel_core_run_turn_flow` first polls a fixed list of "pending work" functions (`0x09dc7ca8`, `0x09dcc5c8`, `0x09c14580`, `0x09c232bc`, `0x09c0e8b8`, `0x09db1e88`, `0x09dcc648`, `0x09c32dac`; the last one runs `duel_core_chain_step`). Only when all report idle does it set `0x09e2d208 = 1`, check for the end of the duel (`duel_core_check_duel_end`), handle card `0x151e` (`0x09de07d0`), and call the turn step `0x09e01da0[0x09e2d210]`:

| Index | Function | What it does |
| --- | --- | --- |
| 0 | `duel_core_step_turn_start` (`0x09de0094`) | Sub-step 0: posts command 2 (begin turn) and clears the `0x25628`-byte area at `0x09e02ff8`. Sub-step 1: cards `0x1356`/`0x1da5`; posts command 9 at turn-limit milestones. |
| 1 | `duel_core_step_draw_phase` (`0x09ddb090`) | Sub-step 0: unless the draw is skipped (player-block flag `+0x120` bit 0, cards `0x14ff`, `0x1548`, `0x1c91`), posts command 10 (enter Draw Phase). Then card checks, the human's confirmation (`begin_player_input(side, 1)`, answer `0x0c`), the normal draw at sub-step 7: `duel_core_draw_cards_ex(side, 1, 0, 0)`, 2 cards with card `0x1dcf`; sub-step 8 raises timing event 1. |
| 2 | `duel_core_step_standby_phase` (`0x09de2460`, 5,912 bytes) | Posts command 11; per-card Standby Phase upkeep (event `0x25`); raises timing event 2. Not read in detail. |
| 3 | `duel_core_step_main_phase` (`0x09de0240`) | Main Phase 1, the Battle Phase and Main Phase 2 (below). |
| 4 | `duel_core_step_end_phase` (`0x09ddf4dc`) | Sub-step 0: posts command 15 (enter End Phase); 1: raises timing event 5; then end-of-turn card upkeep over the 10 monster/spell slots and a table of 8 `(function, argument)` checks at `0x09e014f4`. |
| 5 | `duel_core_step_turn_end` (`0x09de3b78`) | Posts command 3 (end-of-turn cleanup), then command 4 (next turn); in duel mode 2 it can end the duel on the turn limit (compares Life Points). Always returns 0: the turn change resets the index to 0. |

Turn step 3 in detail (`0x09e2d214` values):

- 0: if the player-block flag `+0x120` bit 23 is set the step is skipped; with card `0x13b1` the phase menu is shown instead (sub-steps 10, 11, 0x14). Otherwise posts command 12 (enter Main Phase 1).
- 2: waits for the turn player's decision. CPU (`0x09e02998[side] == 1`): `0x09d9db38` returns the next phase. Human: `duel_core_begin_player_input(side, 2)` opens free Main Phase control. The decision goes to `0x09de0cac`: 3 (Battle) is accepted when `duel_core_can_enter_battle_phase(side)` holds → sub-step 0x15 and Battle index 0; 5 (End) when `0x09dd0b88(side)` holds → sub-step 0x1e.
- 3: human menu answer, `0x09e2d26c - 0x0d` = requested phase; a refused request reopens the phase menu with mask `1 << phase | 8 (Battle allowed) | 0x20 (End allowed)`.
- 0x15: raises timing event 3 (leaving Main Phase for Battle). 0x16: runs `duel_core_run_battle_steps` until it is done; then posts command 14 (enter Main Phase 2) and returns to sub-step 2, unless `0x09e2d228` asks to skip to the End Phase.
- 0x1e: raises timing event 4 (leaving Main Phase for End) and finishes the step.

The phase menu (`duel_core_show_phase_menu`, `0x09dc78cc`) is only shown to a human (`0x09e02998[side] == 0`): UI event `0x36` with arguments `5, 0xe7, mask`.

## Battle Phase steps (`0x09e01dcc`, index `0x09e2d220`)

| Index | Function | Role (confidence) |
| --- | --- | --- |
| 0 | `duel_core_battle_step_start` (`0x09dd229c`) | Posts command 13 (enter Battle Phase). Cards `0x16a1`/`0x1502` cancel the Battle Phase: index 12, skip Main 2. (H) |
| 1 | `duel_core_battle_step_select_attack` (`0x09dd23fc`) | Posts command `0x14`; sets the attacking side `0x09e28620`; CPU: `0x09d9ec64`; human: `begin_player_input(side, 3)`. Chooses the attacker slot `0x09e2863c`, or leaves the Battle Phase: index 11 with `0x09e2d228` = 0 (to Main 2, menu `0x11` / CPU 4) or 1 (to End, menu `0x12` / CPU 5). (H for the exits, M for the attack path) |
| 2 | `duel_core_battle_step_declare_attack` (`0x09dd2a6c`) | Target choice and attack declaration: command `0x17` (monster) or `0x18` (direct). (H) |
| 3 | `duel_core_battle_step_attack_costs` (`0x09dd3574`) | Declaration costs (Toll, Dark Elf, Jirai Gumo, …) and the replay check. (H) |
| 4 | `duel_core_battle_step_attack_declared` (`0x09dd3bd4`) | Attack-declared window, timing event `0x13`; forced negations post command `0x1f`. (H) |
| 5 | `duel_core_battle_step_damage_start` (`0x09dd4530`) | Start of the Damage Step, timing event `0x14`; face-down target flipped; ends the attack (index 10) if attacker or target changed. (H) |
| 6 | `duel_core_battle_step_damage_calc` (`0x09dd5454`) | Damage calculation: timing `0x0d`, ATK/DEF comparison, commands `0x15`, `0x16`, `0x20`. (H) |
| 7 | `duel_core_battle_step_inflict_damage` (`0x09dd7528`) | Timing `0x0e`, battle damage applied (command `0x24`), timing `0x0f`. (H) |
| 8 | `duel_core_battle_step_after_damage_calc` (`0x09dd7ae4`) | "After damage calculation" triggers (not for direct attacks). (M) |
| 9 | `duel_core_battle_step_damage_end` (`0x09dd82b4`) | End of the Damage Step: monsters destroyed by battle are sent to the Graveyard. (M) |
| 10 | `duel_core_battle_step_attack_end` (`0x09dd889c`) | End of the attack: back to step 1, a second attack (2/3), or leave (11). (H) |
| 11 | `duel_core_battle_step_end` (`0x09ddaa20`) | Posts command `0x1d`, raises timing event `0x17` (end of Battle Phase), runs the 31 `(function, argument)` checks at `0x09e00f5c` twice; cards `0x1ca1` and `0x11ed` restart the Battle Phase at index 0 (an extra Battle Phase). (H) |

`duel_core_run_effect_battle` (`0x09ddac64`, called from the pending-work function `0x09c0e8b8`) enters the same table at index 5 and runs it while the index is at most 7: a battle started by an effect skips the declaration steps and steps 8–10 (medium). Every step is described in detail in `battle.md`.

## Phase-changing commands

The engine command queue (`0x09e29100`, 256 entries of 8 bytes, count `0x09e29900`; `tutorial.md`) is drained one command at a time by `duel_core_process_command_queue` (`0x09dc1050`): the first entry is copied to the current command at `0x09e290f8` (`u16 op`, bit 15 = side, low 12 bits = code; `u16 a, b, c` at `0x09e290fa`, `+fc`, `+fe`), the rest of the queue shifts down, `0x09e29904` is set while the command runs and `0x09e29908` is its sub-step. `duel_core_execute_command` (`0x09dc0974`) dispatches on the code with a jump table of 104 cases (1–`0x68`). Most handlers post a UI event with `duel_core_post_ui_event` (`0x09be1400`: stores four arguments at `0x09e01e14` and calls the hook at `0x09e01e10`) and then wait while `duel_core_is_ui_event_busy(event)` (`0x09be1448`) reports the animation is still running.

Turn-related commands:

| Code | Handler | Effect |
| --- | --- | --- |
| 1 | `0x09dbbed0` | UI event 1 (duel start presentation); posted by `0x09dc7dc4` before the opening hands. |
| 2 | `duel_core_cmd_begin_turn` (`0x09dbc4a8`) | Copies the turn side to `0x09e2d1dc`, clears the upper 16 bits of every slot's flag word (per-turn flags), clears `0x09e2a548`/`0x09e2b084`. |
| 3 | `duel_core_cmd_end_turn_cleanup` (`0x09dbc584`) | UI event `0x4c`; sets bit 5 of byte `+2` of every entry in the lists at player `+0x55c`/`+0x7b4`; calls `0x09be6864`. |
| 4 | `duel_core_next_turn` (`0x09dbc184`) | Toggles the turn side, increments the turn counter, phase = 7, turn step and sub-step = 0, tag-duel swap (`tag_duel.md`), UI event 6. |
| 5 | `0x09dbbf38` | Duel result presentation; stores the result in `0x09e2d1f0`, `0x09e02cb4`, player `+0x30`. |
| 9 | `0x09dbcec8` | Turn-limit milestone (UI event `0x41` with `a`); `a = 0` also stores the turn counter in `0x09e2d1e4`. |
| 10–15 | `duel_core_cmd_enter_draw_phase` … `_end_phase` (`0x09dbc478`, `…480`, `…488`, `…490`, `…498`, `…4a0`) | 8-byte stubs that call `duel_core_cmd_enter_phase(code − 10)`. |
| `0x1a` | `0x09db3f40` | Calls `duel_core_set_phase` (also used by the tutorial). |

`duel_core_cmd_enter_phase(phase)` (`0x09dbc394`): on its first call posts UI event 5 `(side, phase)` (the phase banner), stores the phase, runs the per-card phase-change hooks `0x09be6d90(new, old)` (cards that end "until the end of the phase"/"until your next Standby Phase", e.g. cards `0x13f9` when leaving the Battle Phase), `0x09be71b4` and `0x09be6ac4(side, phase)` (Battle Phase entry and Draw Phase rules), clears `0x09e2864c`; once the banner animation is done it calls `0x09be75f8` and posts UI event `0x26`.

`duel_core_set_phase(phase)` (`0x09dc8208`) is the non-animated setter used by the `.ydq` loader and command `0x1a`: it stores the phase and positions the turn step accordingly (phase 0 → step 1, 1 → 2, 2/4 → 3, 3 → step 3 with sub-step 0x16 and Battle index 1, 5 → 4; sub-step 1 otherwise).

## Timing events

`duel_core_raise_timing_event(code, arg)` (`0x09ccaae4`, 41 callers) records a timing for trigger-effect checks: the first code goes to byte `0x09e28fa0` with its argument at `0x09e28fc0`, further ones while `0x09e28f90` is set are appended (up to 32). In a link duel it is forwarded to the peer (`0x09dcc884(7, …)`). Codes raised by the turn machine: 1 Draw Phase, 2 Standby Phase, 3 Main → Battle, 4 Main → End, 5 End Phase, `0x13` attack declared, `0x14` start of the Damage Step, `0x0d` damage calculation, `0x0e`/`0x0f` battle damage, `0x10` effect damage, `0x11` LP gain, `0x17` end of the Battle Phase, `0x25` Standby upkeep. The queue is consumed by `duel_core_run_timing_windows` (`0x09ccc494`), which offers response windows to both players, and by activation conditions that scan it; see `battle.md`. Confidence: high.

## How effects test the phase

Card handlers read `0x09e2d1e8` directly and compare it with constants. Over the 160 functions that reference it, the comparisons found are: `== 3` 44×, `== 2` 36×, `== 4` 29×, `== 5` 25×, `< 4` 12×, `!= 5` 11×, `== 0` 10×, `== 1` 8×, `!= 2`/`!= 4` (as a pair) 6–7×, `< 2`, `< 3`, `< 5` a few each, `!= 7` once. Typical patterns:

- Main Phase only: `phase == 2 || phase == 4` (`duel_core_is_main_phase`, `0x09be1810`, and many inlined copies).
- Battle Phase only: `phase == 3`, often together with the attacker `0x09e28620` (Mirror Force's condition, `duel_effects.md`).
- Standby Phase of a given player: `duel_effects_cond_opponent_standby_phase` (`0x09c60f90`): `turn side != controller && phase == 1`; `duel_effects_cond_own_standby_phase_tribute` (`0x09c586a4`): own Standby Phase, the card's slot occupied, a tribute possible; returns 2 when the record lookup finds a variant.
- Before Main Phase 2: `phase < 4` (`duel_core_can_enter_battle_phase`, `0x09c5e54c` which also requires turn `!= 0`).
- Turn ownership is tested separately against `0x09e2d1d8` with the controller computed from the context (`owner ^ switched`).

So the phase is not passed to the handlers; there is no per-phase handler slot. Phase-restricted effects are ordinary activation conditions (slot `+0x0c`) that read the global.

## Key functions

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x09be1804` | `duel_core_get_phase()` | H | Returns `0x09e2d1e8`. |
| `0x09be1810` | `duel_core_is_main_phase()` | H | 1 when the phase is 2 or 4. |
| `0x09dc8208` | `duel_core_set_phase(phase)` | H | See above. |
| `0x09dbc394` | `duel_core_cmd_enter_phase(phase)` | H | Shared body of commands 10–15. |
| `0x09dbc478`–`0x09dbc4a0` | `duel_core_cmd_enter_{draw,standby,main1,battle,main2,end}_phase` | H | Dispatch cases 10–15; each stores its constant (decompiled). |
| `0x09dc0974` | `duel_core_execute_command()` | H | Switch on `op & 0xfff`, 104 cases. |
| `0x09dc1050` | `duel_core_process_command_queue()` | H | Pops `0x09e29100` into `0x09e290f8`, calls the executor. |
| `0x09be1400` | `duel_core_post_ui_event(event, a, b, c)` | M | Stores arguments, calls the hook at `0x09e01e10`; over 100 callers. |
| `0x09be1448` | `duel_core_is_ui_event_busy(event)` | M | 0 for events outside 0–`0x5f`, otherwise `BOOT.BIN` `0x08836a0c`; handlers wait on it. |
| `0x09dcb5a4` | `duel_core_run_duel_flow()` | H | Driver of table `0x09e01dbc`. |
| `0x09dcb3d8` | `duel_core_run_turn_flow()` | H | Driver of table `0x09e01da0`. |
| `0x09dcb224` | `duel_core_flow_report_result()` | M | Second duel-flow step, posts command 5. |
| `0x09dcb0ec` | `duel_core_check_duel_end()` | M | Win checks for both sides (`0x09dcae58`), sets `0x09e2d1f0`. |
| `0x09de0094` | `duel_core_step_turn_start()` | H | Turn step 0. |
| `0x09ddb090` | `duel_core_step_draw_phase()` | H | Turn step 1. |
| `0x09de2460` | `duel_core_step_standby_phase()` | M | Turn step 2, posts command 11. |
| `0x09de0240` | `duel_core_step_main_phase()` | H | Turn step 3. |
| `0x09ddf4dc` | `duel_core_step_end_phase()` | H | Turn step 4. |
| `0x09de3b78` | `duel_core_step_turn_end()` | H | Turn step 5. |
| `0x09ddabfc` | `duel_core_run_battle_steps()` | H | Driver of table `0x09e01dcc`. |
| `0x09dd229c` | `duel_core_battle_step_start()` | H | Battle step 0. |
| `0x09dd23fc` | `duel_core_battle_step_select_attack(side)` | M | Battle step 1. |
| `0x09ddaa20` | `duel_core_battle_step_end(side)` | M | Battle step 11. |
| `0x09dd0a2c` | `duel_core_can_conduct_battle(side)` | M | 0 on turn 0 and while one of several cards (`0xeb7`, `0xebd`, `0x13eb`, `0x1475`, `0x15f0`, `0x173f`, `0x16d4`, `0x1dbf`) applies. |
| `0x09dd09f4` | `duel_core_can_enter_battle_phase(side)` | H | `phase < 4 && duel_core_can_conduct_battle(side)`; about 80 callers. |
| `0x09dc78cc` | `duel_core_show_phase_menu(side, mask)` | M | Human only; UI event `0x36`. |
| `0x09dce84c` | `duel_core_begin_player_input(side, mode)` | M | Human: resets the input state and stores the mode (1 Draw, 2 Main, 3 Battle) in `0x09e2d24c`. CPU: mode 1 only. |
| `0x09ccaae4` | `duel_core_raise_timing_event(code, arg)` | M | See "Timing events". |
| `0x09dbc4a8` | `duel_core_cmd_begin_turn()` | M | Command 2. |
| `0x09dbc584` | `duel_core_cmd_end_turn_cleanup()` | M | Command 3. |
| `0x09c60f90` | `duel_effects_cond_opponent_standby_phase(ctx)` | H | No direct callers (handler-table entry). |
| `0x09c586a4` | `duel_effects_cond_own_standby_phase_tribute(ctx)` | M | No direct callers (handler-table entry). |

## Presentation hooks

`rel_duel_draw.prx` contains the files behind the phase UI: `phase_icon01.gim`, the banner animation `phase_t_10.ehf`/`.tmf`, `score-phase10.ehf` and the menu layout `phase_select-ptrs.txt`. The engine side is UI event 5 `(side, phase)` for the banner and UI event `0x36` for the phase menu; how `rel_duel_draw` maps these to the files has not been traced.

## Open questions

- Battle steps 2–10, timing events `0x0d`–`0x14` and the timing-queue consumer are now documented in `battle.md`; the remaining battle questions are listed there.
- Whether the first player's draw on turn 0 is skipped (not seen in `duel_core_step_draw_phase`; the skip conditions there are card- and flag-based). Confirm in PPSSPP. **Answered for tag duels in PPSSPP (2026-10-27, Session B): the first player draws on turn 0.**
- The meaning of player-block flag `+0x120` bit 23 (skips Draw and Main steps; hypothesis: "skip this turn") and bit 0 (skips the draw).
- `0x09dd0b88`: condition for ending the Main/Battle Phase (checks cards `0x16a1`, `0x1502`, `0x15ff`); not named.
- The turn-limit mechanism around `0x09e2d1e4` and duel mode 2.
- Confirm the phase values and the Battle-step index at runtime (PPSSPP breakpoint on writes to `0x09e2d1e8` and `0x09e2d220`).
