# Summoning, setting, battle positions and the player's action menu (work package 4)

How `gmodule/rel_duel_eng.prx` (runtime base `0x09be1400`) decides which actions a duelist may take with a card in the Main Phase, and how Normal Summons, Tribute Summons, Sets, Flip Summons, Gemini summons, Special Summons (including Synchro and Fusion) and battle-position changes are carried out. All addresses are runtime addresses in that module unless marked `BOOT.BIN`. Zones, location ids and the card-movement primitives are in `duel_core.md`.

Basis: static analysis of the Ghidra decompilation (read-only, project copy), the call graph, the card database (`cardinfo.md`, used only to name the card ids that the code compares against) and the tutorial scripts (`tutorial.md`), whose hint texts name the player actions. Nothing here has been traced in PPSSPP yet. Confidence per claim: H (high), M (medium), L (low).

## Architecture in one paragraph

Summoning is **hand-written rules code plus card-id special cases**, not data-driven. (1) The presentation module asks the engine, per card under the cursor, for a **bit mask of allowed actions** (`duel_core_get_card_action_mask`); bit *n* corresponds to action code *n* (H). (2) The chosen action code is stored with `duel_core_submit_player_action` and executed by `duel_core_execute_player_action`, one of the "pending work" functions polled every frame by `duel_core_run_turn_flow` (H). The CPU duelist calls the same submit function with the same codes, so human and AI share one execution path (H). (3) Every summon goes through one **summon record** at `0x09e290bc` (60 bytes) and one state machine, `duel_core_run_summon_procedure`, also a pending-work function: a preparation stage picks tributes or materials (generic code or one of about 30 card-specific routines), then a kind-specific executor posts the engine commands that move the card, mark the slot and raise the "summoned" timing event (H). (4) Rule restrictions (once-per-turn Normal Summon, "cannot change position this turn") are bits in the per-player word at player `+0x120` and in each field slot's flag word, cleared at the start of every turn (H).

## The action menu

### Query: `duel_core_get_card_action_mask(side, location, index)` (`0x09dceec4`)

Not called inside the module (H: no callers; it is reached through a pointer from `rel_duel_draw`, not traced). It returns 0 unless player input is open (`0x09e2d254`), then switches on the input mode `0x09e2d24c` (set by `duel_core_begin_player_input` and the selection functions below):

| Mode | Opened by | Mask returned |
| --- | --- | --- |
| 1 | Draw Phase confirmation | Lists (deck, extra deck, graveyard, banished): `2` (view) when the list can be viewed, `8` from `0x09cdc85c(side, 0xfffe, location)`, `0x1000` (continue) on the own deck. |
| 2, 3 | Main Phase / Battle Phase free control | Per zone, below. |
| 4, 5 | Response windows (chain); mode 5 uses the chain link on top | `8` when a set or face-up card can be activated (`0x09c52168`, `0x09c522d8` for hand cards). |
| 6 | `duel_core_begin_select_monster_to_summon` (`0x09dce8e4`) | Hand: `duel_core_get_summon_set_mask_ex(side, ref, 1, tributes)`; monster zone: `0x10` for a Gemini monster that can be summoned again. |
| 7 | `duel_core_begin_select_zone` (`0x09dce9f4`) | The callback `0x09e2d28c(side, location, index)`. |
| 8 | `duel_core_begin_select_cards` (`0x09dce978`, and `0x09dcebd8`) | The callback. |
| 9 | `0x09dcea6c`, `0x09dced60` | `0x800` when the callback accepts the chain context `0x09e28e44`. |

In modes 2 and 3 the mask comes from:

- **Monster zones 0–4** (`duel_core_get_monster_action_mask`, `0x09dce044`), own card: Battle Phase: `1` (attack) when `0x09bea184(side, slot)` is 0 and `duel_core_can_declare_attack` allows; Main Phase (phase 2 or 4): `0x10` when `duel_core_has_normal_summon(side)` and `duel_core_can_gemini_summon(side, slot)`; when `duel_core_can_change_position(side, slot)`: face-down → `0x200` if slot `+0x06` is 0, plus `0x20` when `duel_core_can_flip_summon_slot`; face-up Attack Position → `0x200`; face-up Defense Position → `0x100`. In any phase, a face-up monster with an ignition effect (`duel_effects_has_table3_record`) whose activation check `0x09c523cc` passes adds `8`. Opponent's card: only `8`, for the few cards whose effect the opponent may use (`BOOT.BIN 0x08866820`: Royal Oppression, Mausoleum of the Emperor, Fusion Gate, Magical Labyrinth, Fallen Paradise). (M for the bit names, H for the conditions.)
- **Spell/trap zones 5–10** (`duel_core_get_spell_trap_action_mask`, `0x09dce474`): `8` (activate) for a set trap (`0x09c53f54`), a set spell (quick-play outside the own Main Phase only; Curse of Fiend also in the Standby Phase) or a face-up card with an ignition-style record (`0x09c53e5c`); Cold Wave (`0x1407`) blocks spells. (M)
- **Hand** (`duel_core_get_hand_action_mask`, `0x09dcdcac`), own hand only, nothing for a card named by Prohibition (`0x09bfd3fc`): Main Phase: spell/trap → `8` when `0x09c5404c` (can be activated from the hand), `0x80` when `duel_core_can_set_spell_trap(side)` and the card is not barred from being set (`0x09bee784`), both only with a free zone (`duel_core_has_spell_trap_zone_for`); monster → `duel_core_get_summon_set_mask` (`0x10`, `0x40`) unless it cannot be Normal Summoned (`BOOT.BIN 0x08863d98`) or the Normal Summon is used up, plus `duel_core_get_special_summon_mask` (`4`), plus `0x80` for Toy Magician (`0x1a9f`, set as a trap) and `8` for monsters with an effect usable from the hand (`BOOT.BIN 0x08866594`: Kiteroid, Gallis the Star Beast, Thunder Dragon, Cocoon of Evolution …). Battle Phase: only quick-play spells, traps (none), and hand effects (`8`). (M–H)
- **Lists 0x0c–0x0f** (extra deck, deck, graveyard, banished): `2` (view) when `0x09dcac18` allows (always the own extra deck and banished zone; the graveyard unless the opponent has Question `0x1576` in hand), `8` from `0x09cdc85c(side, 0xfffe, location)` (an activatable card in that list: Synchro and contact-fusion monsters in the extra deck, graveyard effects), `0x400` on the own deck. (M)

### Action codes

The mask bit for action *n* is `1 << n`. This follows from the code (the hand mask's `0x10`/`0x40` are the two bits that `duel_core_get_summon_set_mask` returns; the CPU posts code `0x0c` on the deck in the Draw Phase where mode 1 offers `0x1000`; selection answers are code `0x0b` where mode 9 offers `0x800`) and from the tutorial's `wait_input` table, whose hint texts name codes 2–9 and 11. Confidence H.

| Code | Bit | Action | Executed by `duel_core_execute_player_action` (`0x09dcc648`) |
| --- | --- | --- | --- |
| 0 | `0x1` | Attack with this monster | Handled by the Battle steps (`duel-phases.md`), not here. |
| 1 | `0x2` | View the list | `duel_core_open_card_list(side, location − 0x0b, −1)` (UI event `0x37`). |
| 2 | `0x4` | Special Summon (by the card's own procedure) | `duel_core_begin_summon_from_hand(1, 1, 0)`. |
| 3 | `0x8` | Activate | Lists: `duel_core_action_use_card_list`; hand spell: `duel_core_action_place_spell_trap(1, 0)` (place, then activate); hand monster: `duel_core_action_activate_hand_monster`; field: `duel_core_action_activate_field_card`. |
| 4 | `0x10` | Normal Summon (hand) / Gemini summon (field) | Hand: `duel_core_begin_summon_from_hand(1, 0, 1)`; field: `duel_core_action_gemini_summon(1)`. |
| 5 | `0x20` | Flip Summon | `duel_core_action_flip_summon`. |
| 6 | `0x40` | Set (monster) | `duel_core_begin_summon_from_hand(0, 0, 1)`. |
| 7 | `0x80` | Set (spell/trap) | `duel_core_action_place_spell_trap(0, 0)`. |
| 8, 9 | `0x100`, `0x200` | Change to Attack / Defense Position | `duel_core_action_change_position` → `duel_core_change_position(side, slot, 0, 0, 0, 0)` (the position is toggled). |
| 10 | `0x400` | Deck action in Main Phase (L: probably surrender) | `0x09dcdbc0`: before turn 9 shows message `0x52`; otherwise a yes/no dialog, then command `0x22`. |
| 11 | `0x800` | Confirm a selected card/zone | Read by the selection loops through `duel_core_is_selection_confirmed` (`0x09dcedec`). |
| 12 | `0x1000` | Continue (Draw Phase) | Phase driver. |
| `0x0d + p` | — | Phase menu choice | `duel_core_submit_phase_choice(p)` (`0x09dcfce4`); see `duel-phases.md`. |

`duel_core_submit_player_action(side, location, index, code)` (`0x09dcf950`) stores the answer: code `0x09e2d26c`, side `0x09e2d278`, location `0x09e2d27c`, index `0x09e2d280`, the card id `0x09e2d264` and the card reference `0x09e2d268` (field slot, hand entry or list entry; for lists the index is 1-based and 0 or ≥ 3000 means "a card id, not a position"). In mode 7 it only stores the chosen zone `location + index` in `0x09e2d284`. It sets `0x09e2d258` (answer ready) and leaves input mode. Callers: the AI (`ai_try_main_cards` with codes 5/8/9, `ai_activate_from_table` with 3, `0x09d899a8`, `0x09d8c79c`, …), `duel_core_begin_player_input` (CPU draw, code `0x0c`), the tutorial (`open_list`, code 1), and `0x09dcfb3c`. (H)

`duel_core_get_phase_menu_mask()` (`0x09dcfc18`, no callers: export) gives the phase menu's options: in mode 2 `8` (Battle) when `duel_core_can_enter_battle_phase`, `0x20` (End) when `0x09dd0b88`; in mode 3 `0x10` (Main Phase 2) and `0x20` (End, `0x09de0694`). (M)

### Why an action is missing

When a check fails for the local player (`0x09e02994 & 1`), it leaves a reason code in `0x09e2d288`, presumably shown as a message (M for the mechanism, L for the texts): 2 Normal Summon already used; 3 the monster cannot change position this turn; `0x0b` no free monster zone; `0x0c` no free spell/trap zone; `0x0d` the monster cannot be Normal Summoned; `0x0e` Fusion Summons are prevented (Non-Fusion Area); `0x10` the card is named by Prohibition; `0x11` the summon is prevented by a card; `0x12` the position change is prevented by a card; 4–8, `0x0a`, `0x0f` are set while activations are checked.

## Normal Summon, Set and Tribute Summon

### Conditions: `duel_core_get_summon_set_mask_ex(side, ref, mode, tributes)` (`0x09da0a4c`)

`ref` is a card reference (index into the instance table `0x09e2bbcc`, `duel_core.md`). Returns `0x10` (may be Normal Summoned) and/or `0x40` (may be Set). The wrapper `duel_core_get_summon_set_mask(side, ref)` (`0x09da0a40`) passes `mode = 1, tributes = 0`. `mode` is 0, 1, 2 or 3 depending on the caller (the UI uses 1; 2 is the re-check inside a card-specific summon; 3 excludes some alternative-tribute paths); `tributes` ≠ 0 asks "with exactly this many tributes already chosen". In order (H unless noted):

1. 0 for an empty reference or a non-monster (`BOOT.BIN 0x0885fef0`), for a card named by Prohibition, when `0x09c0bb98(side, card, 1)` fails (Chain Energy LP check, Cold Wave …), or when the card cannot be Normal Summoned/Set at all (`BOOT.BIN 0x08864300`).
2. Light of Intervention (`0x135d`) on the field: the "Set" choice becomes a face-up summon (Normal Summon bit becomes `0x50`, Set bit 0).
3. Chain Energy (`0x132c`) and Queen of Thorns (`0x1df4`, non-Plant monsters): 0 when Life Points ≤ 500 × copies + 1,000 × copies.
4. `duel_core_can_normal_summon(side)` and the summon-lock checks of `0x09c0c584` (Rivalry of Warlords: one Type; Gozen Match: one Attribute) and Tualatin (`0x197d`, opponent's declared Attribute); a failure clears the summon bit (reason `0x11`). `duel_core_can_set_monster(side)` false clears the Set bit.
5. Card-specific rules, a compare chain over about 50 ids: monsters with their own tribute rules (Phantom Dragon, Fog King, Infernal Incinerator, the gods `0x1386`–`0x1388`, Ultimate Offering-type cards), "tribute any monster from either side" monsters, Arcana Force VI – The Lovers, Elemental Hero Necroshade's free summon (`BOOT.BIN 0x08860af8`, the Elemental Hero list), Ancient Gear Factory/Geartown (`BOOT.BIN 0x08861298`, the Ancient Gear list), Big Evolution Pill (Dinosaurs, race 9), and so on.
6. The generic rule: **tributes needed = (level ≥ 5) + (level ≥ 7)**, using `duel_core_get_level_by_ref(side, ref)` (`0x09c02fb4`: the card's level, overridden by Level Conversion Lab `0x18d9`, −1 for Water monsters under A Legendary Ocean `0x150b`, −2 per Cost Down `0x15c7` resolved this turn, never below 1), minus 1 for a Wind monster while Simorgh, Bird of Ancestry (`0x1dbc`) is on the field. With 0 tributes both bits are set if `duel_core_count_free_monster_zones(side) > 0`, otherwise reason `0x0b`. With 1 or 2 tributes the summon bit needs `duel_core_count_tribute_value(side, card, 1) ≥ n` and the Set bit `duel_core_count_tribute_value(side, card, 0) ≥ n`. With `tributes` ≠ 0 both bits are set when `tributes` equals the requirement and a zone is free.

`duel_core_count_tribute_value(side, card, face_up_summon)` (`0x09bfbe18`) adds 1 per monster that `0x09bfb1b0` accepts as a tribute for `card` (own monsters, plus opponent's monsters only where a card allows it), 2 for monsters that count as two tributes (`duel_core_is_double_tribute`, `0x09bfbbf4`: The Lovers for Arcana Force monsters, attribute-specific double-tribute monsters such as `0x1cc7`/`0x1cc8`, `0x1b8c` for same Attribute and Type), and returns 0 unless tributing would free at least one own zone. (M)

### Starting the summon

`duel_core_begin_summon_from_hand(mode, special, normal_flag)` (`0x09da5774`) reads the side and card reference from the answer variables and calls `duel_core_init_summon_from_hand(side, ref, special ? 2 : mode, normal_flag)` (`0x09da54ec`), which fills the summon record:

- `mode` 1 = Normal Summon (face-up Attack Position, record bits `0x40`), 0 = Set (face-down Defense Position, `0x80`; Light of Intervention makes it face-up, `0xc0`), 2 = Special Summon by the card's own procedure (flag byte bit 1).
- `normal_flag` ≥ 1 marks the summon as using the turn's Normal Summon (flag byte bit 2); `normal_flag − 1` is a tribute count already chosen (bits 4–5; the AI passes it, the human path passes 1 = none chosen yet).
- Flag byte bit 0 = "preparation needed" and bit 6 = "procedure pending"; it also clears bit 3 of player word `+0x120` for both sides (`0x09bf101c`).

AI callers: `ai_execute_summon`, `ai_choose_special_summon`; effect callers: `0x09c80e24`, `0x09ca76a0` (effects that grant a summon), `duel_core_activate_from_list` (Synchro/contact fusion from the extra deck), and `duel_core_execute_player_action`.

### The summon record (`0x09e290bc`, `0x3c` bytes)

Confidence M (layout inferred from the writers; all fields are consistently used by the readers).

| Offset | Size | Field |
| --- | --- | --- |
| `+0x00` | u32 | Bit 0 side that summons; bit 1 controller of the result (differs when summoning to the opponent's side); bits 2–5 target slot (filled from the zone choice); bit 6 face-up; bits 7–8 position (0 Attack, 1 Defense, 2 "ask the player"); bits 9–12 source location (`location × 2`, e.g. `0x16` = hand); bits 13–21 card reference. |
| `+0x04` | u16 | Card id. |
| `+0x06` | u16 | Summon type: 0 Normal, 2 Flip, 5 Special by procedure, 8 Gemini, `4 | flags` Special by effect (`flags & 0x10` = to the opponent's side). |
| `+0x08` | u16 | Card id of the effect that summons (Special Summon by effect); for card-specific procedures, the card whose rule applies. |
| `+0x0a` | u8 | Number of tributes chosen. |
| `+0x0b` | u8 | Number of distinct tributes (used by cards that count them). |
| `+0x0c` | u16[] | Card references of the tributes. |
| `+0x34` | u8 | Flags: bit 0 preparation pending, bit 1 Special Summon by procedure, bit 2 uses the Normal Summon, bit 3 cancelled, bits 4–5 preselected tribute count, bit 6 procedure pending, bit 7 controlled by the link-duel peer. |
| `+0x35` | u8 | Bits 0–2 kind: 1 Normal Summon/Set, 2 Flip Summon, 3 Gemini summon, 4 Special Summon by effect, 5 Special Summon by procedure. |
| `+0x36` | u8 | Sub-step of the current stage. |

A second record at `0x09e29080` holds a summon that arrives while one is in progress (flag `0x09e290b4` bit 6); it is copied in when the current one ends.

### The procedure: `duel_core_run_summon_procedure()` (`0x09db1e88`)

Polled every frame by `duel_core_run_turn_flow` (it is in the pending-work list). Returns 1 while busy. (H)

1. **Preparation** (flag bit 0): `duel_core_summon_prepare` (`0x09dab210`) dispatches on the card id. About 30 card-specific routines handle cards with their own summon conditions (gods, Fog King, Infernal Incinerator, the Cloudians, Ancient Gear/Elemental Hero alternatives, monsters that are Special Summoned by removing or tributing specific cards …). The default path: Synchro monsters (`BOOT.BIN 0x08860084`) → `duel_core_summon_prepare_synchro`; monsters summoned from the extra deck by their own procedure (`BOOT.BIN 0x088648d4`: Gladiator Beast Gyzarus, Elemental Hero Storm Neos, Chimeratech Fortress Dragon, XY-Dragon Cannon …) → `duel_core_summon_prepare_contact_fusion` (L for the name); Elemental Hero → `0x09da60f8`; Ancient Gear → `0x09da63c8`; Dinosaur → `0x09da6860`; everything else → `duel_core_summon_select_tributes`. A routine returns 1 when done, −1 when cancelled (UI event `0x2b`, flag bit 3), 0 to be called again. On success the record is re-initialised for the execution stage: Normal Summon/Set by `duel_core_init_normal_summon(side, ref, keep_tributes, attack)` (`0x09db2284`, kind 1), Special Summon by procedure by `duel_core_init_procedure_summon(side, ref, position, keep_tributes)` (`0x09db2df0`, kind 5).
2. **Execution**, by kind: 1 `duel_core_summon_step_normal` (`0x09daea0c`); 2 `duel_core_summon_step_flip` (`0x09dafc90`); 3 Gemini summon inline (command `0x61`, player flag 16, command `0x2b` with type 2 and the "uses Normal Summon" bit, then the trigger stage); 4 `duel_core_summon_step_special` (`0x09db00f8`); 5 `duel_core_summon_step_procedure` (`0x09db1334`, which pays the tributes and then continues in the kind-4 code).

`duel_core_summon_select_tributes` (`0x09da57c8`): tributes needed as above (Simorgh rule included; none for a procedure Special Summon unless `BOOT.BIN 0x08860130` says the card needs them). If the AI preselected that many, it is done. Otherwise: message `0x14f` (`0x151` for a Special Summon) "select 1 tribute", or `0x150`/`0x152` formatted with 2 or 3; card selection (mode 8) with the filter `duel_core_filter_tribute_candidate` (`0x09da3a3c`: monster zones only; `duel_core_can_tribute_for_effect` for procedures, `0x09bfb1b0` otherwise); each pick posts UI event `0x2a` and is stored in the record. A monster that counts as two tributes (`duel_core_is_double_tribute`) ends the selection early after a confirmation (message `0x124`). Sub-steps `0x0a`–`0x0c` (1 tribute), `0x14`–`0x17` (2), `0x1e`–`0x21` (3, the gods). (H for the structure.)

`duel_core_summon_step_normal` (`0x09daea0c`), sub-steps (H for the commands, M for the order details):

- 1: if the position is "ask", take it from the answer; if face-up, post command `0x61` (summon declaration) and set player flag 16 (`duel_core_post_set_player_flag`). For each tribute post command `0x49`, then `duel_core_tribute_monsters(side, slot_mask)` (`0x09c268d0`), which queues the tributes in the batch "send to graveyard" processor (`0x09e2d298`, destination `0x0e`, flags `0x1000`).
- 2: choose a monster zone: if exactly one is free it is taken, if none the card is sent to the graveyard instead (`duel_core_send_*_to_graveyard`, by source location), otherwise zone selection (mode 7) with the filter `0x09dac660`.
- 3: post command `0x50` (move the hand card to the monster zone, see below), with per-card bookkeeping for cards that remember their tributes (`0x09c1aad4`: Cloudian – Nimbusman, Fog King, Simorgh, …).
- 4: post command `0x2b` (summon complete, type 0) and command `0x44` (finalise: slot and player flags).
- `0x0a`–`0x0e`: `duel_core_summon_raise_trigger(0x20)` (`0x09dac2e0`): opens the response window for summon negation (`0x09c32e54`; Solemn Judgment and similar) and raises timing event `0x20` (Normal Summon) with a packed summary of the record; `0x14`–`0x16` handle a negated summon.

### Once-per-turn Normal Summon

Tracked in **player word `+0x120` (`0x09e2a648 + side × 0xb3c`) bit 17**, confidence H:

- `duel_core_has_normal_summon(side)` (`0x09c0bcac`) is true while bit 17 is clear; once it is set, it is true only while Double Summon (`0x1c33`) or Chain Summoning (`0x1d20`) is active for the player and its use count (`0x09be9348(side, 0x0b, card, 2)`) is not exhausted.
- `duel_core_use_normal_summon(side)` (`0x09be9c94`) sets bit 17 the first time; later calls mark the Double Summon / Chain Summoning entry as used (`0x09be5894(side, 0x0b, 2, card, 0)`). It is called by command `0x50` when its argument `c` bit 0 is set (Normal Summon/Set from the hand), by command `0x2b` for a Gemini summon that uses the Normal Summon, and by command `0x51` (`0x09dbda08`) in one path.
- Bit 17 is in the upper half of the word, and **command 2 (begin turn) clears the upper 16 bits of all twelve flag words of each side**: the eleven field slots' `+0x10` and the player word `+0x120` (they are laid out at stride `0x14`, the player word being "slot 11"). That is the per-turn reset. (H: `duel_core_cmd_begin_turn` loop of 12 words; `+0x120 = +0x10 + 11 × 0x14`.)
- Double Summon and Chain Summoning resolve through `0x09c8be00`, which registers the card as an active effect for its controller (`0x09c2b6a0(side, card, 1, n)`). (M)

Other per-turn bits of `+0x120` seen in the summon code: bit 16 set when a summon is declared face-up (command `0x61` stage); bit 20 set by commands `0x50`, `0x2b`, `0x33` and others when they run during Main Phase 1 (phase 2) (purpose L); bit 21 set by command `0x44` when a monster is Normal Summoned face-up. Bit 3 is cleared when a summon starts. Bit 0 (persistent, lower half) skips the Draw Phase draw (`duel-phases.md`).

`player + 0x20` (`0x09e2a548`) counts the summons completed with command `0x2b` this turn (Normal, Flip and Gemini; bit 16 instead when `0x09e2bba0` bit 3 is set); command 2 clears it. (M)

## Flip Summon, Gemini summon and battle positions

- `duel_core_can_flip_summon_slot(side, slot)` (`0x09bfdca0`): the card is face-down, `duel_core_can_change_position` holds, `duel_core_can_flip_summon(side)` holds, card-specific checks (Phantom Dragon needs two zones, `0x1691` needs a matching face-up monster, the six "cannot be summoned while … is on the field" cards), and `0x09c0c584` (summon locks). (H)
- `duel_core_action_flip_summon` → `duel_core_init_flip_summon(side, slot)` (`0x09db2578`): record kind 2, type 2. `duel_core_summon_step_flip` posts command `0x61` (type 4), sets player flag 16, posts command `0x34 (slot, 1, 2)` (turn face-up) and `0x33 (slot, 1, 1)` (to Attack Position), command `0x2b` (type 1), command `0x44`, then raises timing event `0x21` (Flip Summon). (H for the commands)
- Gemini: `duel_core_can_gemini_summon(side, slot)` (`0x09bfe0ac`): face-up, slot flag bit 8 clear, Gemini kind (`BOOT.BIN 0x0886019c`), not already Gemini-summoned (`0x09bf0158`), `duel_core_can_normal_summon(side)`, not prevented, the card can be Normal Summoned, and either `0x09bff2e8` or Tualatin allows it; the caller also requires `duel_core_has_normal_summon`. `duel_core_action_gemini_summon(1)` → `duel_core_init_gemini_summon(side, slot, uses_normal)` (`0x09db281c`, kind 3, type 8); command `0x2b` with type 2 sets slot flags `0x200008` and consumes the Normal Summon. (M)
- Position changes: `duel_core_can_change_position(side, slot)` (`0x09bfd584`) is false when slot flag **bit 21** is set (reason 3), during duel mode 8 (`0x09e02cac`), when one of about 20 card ids applies (`0x12ce`, `0x131e` Curse of Fiend, `0x17b3`, `0x1990`, `0x1b69`, … tested with `0x09be9168`/`0x09be7d00`; reason `0x12`), or for a face-down card under specific rules. Bit 21 is set **when a card is placed in a monster zone** (`duel_core_place_in_monster_zone`), **when the monster attacks** (`0x09bee500`, called from the attack commands), and **when its position is changed manually** (`duel_core_change_position` with `by_effect = 0` posts `duel_core_post_set_slot_flag(side, slot, 21, 1)`); command 2 clears it at the start of the turn. So a monster may change position once per turn, not in the turn it arrived, and not after attacking. (H)
- `duel_core_change_position(side, slot, flip, a4, by_effect, a6)` (`0x09c16540`): refuses a slot whose flag bit 2 is set; with `by_effect` it first asks `duel_effects_can_change_position`. Posts command `0x33 (slot, flip, by_effect == 0)`; the handler toggles slot `+0x06` (position) and XORs slot `+0x08` (face) with `flip`. Flipping a face-down monster face-up runs its FLIP effect (`BOOT.BIN 0x08863438`) and raises timing event 9 (flipped) or `0x0b` (position changed). (M–H)

## Setting and activating spells and traps from the hand

`duel_core_action_place_spell_trap(activate, a2)` (`0x09dcd710`): step 0: a field spell (icon 2) goes to zone 10, sending a previous field spell to the graveyard (`0x09c24c00(side, 10, 0, 0)`); otherwise the human picks a spell/trap zone (mode 7, `duel_core_begin_select_zone`), a link-duel peer's choice is read from `0x09e2d2d8`, and the CPU uses `0x09c13674`. Step 1: `duel_core_place_spell_trap_from_hand(side, hand_index, zone, activate)` (`0x09c2b48c`) posts command `0x51 (card id, face_up << 14 | zone << 1 | side, ref)`; when set face-down it raises timing event `0x0a`. Step 2: with `activate`, the activation is posted with `0x09c2c9cc`. (H)

`duel_core_can_set_spell_trap(side)` (`0x09c0bd60`): false in duel mode 6, under Judgment of Pharaoh (`0x1679`), Searchlightman (`0x1a1b`) or the opponent's Dark Simorgh (`0x1e5a`). `duel_core_has_spell_trap_zone_for(side, card)` (`0x09bfca98`): a field spell needs room under Spatial Collapse (`0x16df`); other checks for `0x1bd7`. (M)

## Special Summon

### By an effect: `duel_core_special_summon(side, entry, face_up, position, flags)` (`0x09db2de4` → `0x09db2ae0`)

67 effect handlers call it (Monster Reborn-type resolutions, Polymerization, Future Fusion …). It refuses when `0x09bfaf70` fails; Light of Intervention forces face-up; it fills the record (kind 4, type `flags | 4`, `flags >> 16` = the summoning card's id, `flags & 0x10` = summon to the opponent's side) from the list entry `entry` and its location (`duel_core_find_card_location`). (H for the record, M for the parameter names.)

`duel_core_summon_step_special` (`0x09db00f8`) and `duel_core_summon_step_procedure` (`0x09db1334`): position choice (dialog `0xf7` when the position is "ask"), command `0x61` (type 6 for a procedure), player flag 16, tributes for procedures (commands `0x49`, `duel_core_tribute_monsters`), zone choice; **with no free zone the card is sent to the graveyard from wherever it is** (banished `0x09c196c8`, extra deck, deck or hand); then the move and finalisation; timing event `0x22` (Special Summon). (M)

### By the card's own procedure (from the hand or extra deck)

Hand monsters with a summon procedure get mask bit `4` from `duel_core_get_special_summon_mask(side, ref)` (`0x09da19b4`, 8,324 bytes): `duel_core_can_special_summon(side)`, the zone count, `0x09c0c8a0` and per-card conditions (a long compare chain; the Toon monsters `0x154a`, `0x12a5`, `0x127d`–`0x127f` need `0x09bf9a5c(side)`, presumably a face-up Toon World; Volcanic Queen, Grinder Golem, Alien Skull and Lava Golem test the summon locks of the opponent's side, consistent with being summoned there). The action posts `duel_core_begin_summon_from_hand(1, 1, 0)` (mode 2). (M)

Extra-deck monsters with a procedure (Synchro monsters and the contact-fusion list `BOOT.BIN 0x088648d4`) are activated with code 3 on the extra-deck list: `duel_core_action_use_card_list` opens the list, the player picks a card, and `duel_core_activate_from_list(side, location, card, ref)` (`0x09dd08b8`) calls `duel_core_begin_summon_from_hand(1, 1, 0)` for them. Other list activations use a table of 23 `(card id, …, handler)` records at `0x09e00dbc`; Destiny Hero – Diamond Dude's graveyard effect (`0x1a04`) is special-cased. (M)

### Synchro Summon: `duel_core_summon_prepare_synchro` (`0x09da8ca4`)

Sub-step 0 stores the Synchro monster (`0x09e29050` id, `0x09e29054` reference), its material count bound (`0x09cbded4`) and the level still to cover (`0x09e28f64` = the Synchro monster's level, `BOOT.BIN 0x08832e08`), and shows message `0x3a` with that level. Sub-steps 1–3 repeat a card selection (mode 8) with the material filter `0x09cbe5bc`; each picked monster's level (`0x09c0a6a4(side, slot)`) is subtracted, with a special case for card `0x1f32` that may count as either of two levels. When the remaining level reaches 0 or less, sub-step 4 posts command `0x4c` for every material (sent to the graveyard as Synchro Material) and command `0x61` (type 8), and sub-step 5 posts command `0x4e` (`id, ref, count | 0x200`). The procedure then continues as a kind-5 Special Summon from the extra deck. Confidence M (the tuner/non-tuner rule lives in the filter `0x09cbe5bc`, not read).

### Fusion Summon with Polymerization: `duel_effects_resolve_fusion_summon` (`0x09cbace0`)

Polymerization (`0x12e5`) and Miracle Fusion (`0x1920`) share this resolution handler (spell/trap effect table slot `+04`); Future Fusion (`0x1a7e`) has its own (`0x09cbc3f4`). The activation condition `duel_effects_cond_fusion_summon` (`0x09cbac10`) requires `duel_core_can_special_summon`, no Non-Fusion Area (`0x197a`, reason `0x0e`), for Fusion Gate the graveyard-to-banished rule (`0x09c0d5e8`), and a summonable Fusion (`0x09cdc90c(side, card, 0)`). The resolution is a state machine on `0x09e28f60` (M):

1. `0x80`/`0x7f`/`0x7e`: re-check; open the extra deck list for the player to choose a Fusion monster (Cyberdark Impact! takes a different path). Store the Fusion's id `0x09e29050` and reference `0x09e29054`. The number of materials `0x09e29058` comes from the **fusion recipe table at `0x09debe98`** (138 records of 8 bytes, searched by the Fusion's id; `u16 +6` = 0 → 2 materials, else 3), except for a few hard-coded Fusions (Elemental Hero Divine Neos 5, `0x1ab3`/`0x19ef` 4, `0x157e` 5). A variant code `0x09e2905c` per spell selects where materials come from (1 Miracle Fusion/Fusion Gate-type: banish from field or graveyard; 2 Future Fusion; 3, 5, 6, 7 other fusion spells; 8 Chain Material: from the deck).
2. `0x78`/`0x77`: material selection (mode 8 with filter `0x09cba218`, or a list for hand/deck materials), each pick validated (`0x09cb97c4`) and stored in the ring `0x09e28e50`.
3. `100`: post command `0x4a` per material; `99`: move each material to its destination (graveyard `0x0e` by default; banished `0x0f`, deck `0x0d` for the variants), using `duel_core_send_hand_card`, `duel_core_return_hand_card_to_deck`, `0x09c19488` (graveyard → banished), `0x09c2af48` (deck → banished), and `0x09c22a98` for field materials.
4. `0x32`: post command `0x4e` (fusion announcement) and call `duel_core_special_summon(side, extra-deck entry, 1, …, id << 16 | 1)`.

## Summon and movement commands

The summon code changes the duel state only through engine commands (`duel_core_push_command`, executed by `duel_core_execute_command`; `duel-phases.md`). Arguments as `(a, b, c)`; `side` is bit 15 of the opcode. Confidence M unless noted.

| Code | Handler | Arguments and effect |
| --- | --- | --- |
| `0x21` | `duel_core_cmd_set_player_flag` (`0x09dbc7dc`) | Set (`b` ≠ 0) or clear bit `a` of player word `+0x120`. H |
| `0x29` | `0x09dbc898` | Set/clear bit `b` of slot `a`'s flag word (posted by `duel_core_post_set_slot_flag`). M |
| `0x2b` | `duel_core_cmd_summon_complete` (`0x09dbefcc`) | `a` card id, `b` slot, `c` low byte type (0 Normal, 1 Flip, 2 Gemini: slot flags `|= 0x200008`), high byte "uses the Normal Summon"; increments player `+0x20`; UI event `0x38`. |
| `0x33` | `duel_core_cmd_change_position` (`0x09db67f0`) | `a` slot, `b` flip face-up, `c` 1 = manual change; UI events `0x4a`, `0x1c`. |
| `0x34` | `0x09db6cc0` | Turn a monster face-up/face-down (`b`, `c` reason). |
| `0x3e` | `duel_core_cmd_move_list_card` (`0x09db4560`) | Move a card between card lists: `a = ref << 6 | location << 1 | side` (source), `b = index << 6 | location << 1 | side` (destination; for the deck `index` 0 = top), `c` flags (bit 0 face-up/revealed, bits 4–5 hand flags). UI event `0x1a`. |
| `0x44` | `duel_core_cmd_summon_finalize` (`0x09dbdedc`) | `a` slot, `b` summon type, `c` tribute count: slot flags `0x40040` (Special), `0x20000` (Flip), `0x4000` (Gemini), `0x20` (tributes used), `0x10000` and player bit 21 (face-up Normal Summon); statistics counters. |
| `0x49` | `0x09dbe2ec` | Tribute announcement for slot `a`. |
| `0x4a`, `0x4b` | `0x09dbe374`, `0x09dbe4b8` | Fusion material announcement / material moved. |
| `0x4c` | `0x09dbe418` | Synchro material sent. |
| `0x4e` | `0x09dbe814` | Fusion/Synchro summon announcement (`c & 0x200` = Synchro). |
| `0x50` | `duel_core_cmd_summon_from_hand` (`0x09dbd5c0`) | `a` card id, `b = position << 15 | face_up << 14 | slot << 1 | side`, `c = ref << 1 | uses_normal_summon`. Moves the hand card to the monster zone (`duel_core_zone_remove` + `duel_core_zone_insert`), calls `duel_core_use_normal_summon` when `c & 1`, handles Cost Down; UI events `0x48`, `0x1a`, `0x1e` (set). |
| `0x51` | `duel_core_cmd_place_spell_trap_from_hand` (`0x09dbda08`) | `a` card id, `b = face_up << 14 | zone << 1 | side`, `c` ref. |
| `0x61` | handler not read | Summon declaration shown to the player (`a = ref | 0x8000`, `b` position, `c` 7 Normal / 4 Flip / 6 procedure / 8 Synchro). L |

The field-card movements (`0x30`, `0x31`, `0x32`, `0x3c`, `0x3d`, `0x3f`, `0x40`, `0x45`) are described in `duel_core.md`.

## Timing events raised by summons

| Code | Raised by | Meaning |
| --- | --- | --- |
| `0x20` | `duel_core_summon_raise_trigger` from the Normal and Gemini paths | Normal Summon (H) |
| `0x21` | Flip path | Flip Summon (H) |
| `0x22` | Special paths | Special Summon (H) |
| 9, `0x0b` | `duel_core_change_position` | Flipped face-up / position changed (M) |
| `0x0a` | `duel_core_place_spell_trap_from_hand` | Spell/trap set (M) |

## Key functions

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x09dceec4` | `duel_core_get_card_action_mask(side, location, index)` | H | Mode switch above; bit *n* = action *n*. |
| `0x09dcdcac` | `duel_core_get_hand_action_mask(card, side, index)` | M | Hand branch. |
| `0x09dce044` | `duel_core_get_monster_action_mask(card, side, slot)` | M | Monster-zone branch. |
| `0x09dce474` | `duel_core_get_spell_trap_action_mask(card, side, slot)` | M | Spell/trap-zone branch. |
| `0x09dcf950` | `duel_core_submit_player_action(side, location, index, code)` | H | Stores the answer; AI and tutorial callers. |
| `0x09dcc648` | `duel_core_execute_player_action()` | H | Pending-work function, switch on the code. |
| `0x09dcfc18` | `duel_core_get_phase_menu_mask()` | M | Export. |
| `0x09dcfce4` | `duel_core_submit_phase_choice(phase)` | M | Answer `0x0d + phase`. |
| `0x09dce8e4`, `0x09dce9f4`, `0x09dce978` | `duel_core_begin_select_monster_to_summon`, `_select_zone`, `_select_cards` | M | Input modes 6, 7, 8; the CPU branch asks the AI. |
| `0x09dcedec` | `duel_core_is_selection_confirmed()` | H | `answer ready && code == 0x0b`; about 130 callers. |
| `0x09da0a4c` / `0x09da0a40` | `duel_core_get_summon_set_mask_ex` / `duel_core_get_summon_set_mask` | H | Normal Summon/Set rules. |
| `0x09da19b4` | `duel_core_get_special_summon_mask(side, ref)` | M | Hand Special Summon rules. |
| `0x09c0bcac` | `duel_core_has_normal_summon(side)` | H | Player bit 17, Double Summon, Chain Summoning. |
| `0x09be9c94` | `duel_core_use_normal_summon(side)` | H | Sets bit 17 or uses up the extra summon. |
| `0x09c0bdec` | `duel_core_is_summon_kind_allowed(side, kind, a3)` | M | Kinds 1 Normal, 2 Set, 4 Flip, 8 Special (from the wrappers' callers); card-based locks. |
| `0x09c0c440`, `0x09c0c324`, `0x09c0c44c`, `0x09c0c4bc` | `duel_core_can_normal_summon`, `_can_set_monster`, `_can_flip_summon`, `_can_special_summon` | M | One-line wrappers. |
| `0x09bfac80` | `duel_core_count_free_monster_zones(side)` | M | Empty, usable zones; Spatial Collapse caps at 5 cards. |
| `0x09c02fb4` | `duel_core_get_level_by_ref(side, ref)` | M | See the tribute formula. |
| `0x09bfbe18` | `duel_core_count_tribute_value(side, card, face_up)` | M | Tribute capacity. |
| `0x09bfbbf4` | `duel_core_is_double_tribute(side, card, owner, slot)` | M | Monsters worth two tributes. |
| `0x09da3a3c` | `duel_core_filter_tribute_candidate(owner, location, index)` | M | Selection filter. |
| `0x09bfd584` | `duel_core_can_change_position(side, slot)` | H | Slot bit 21 and card locks. |
| `0x09bfdca0` | `duel_core_can_flip_summon_slot(side, slot)` | H | Flip Summon rules. |
| `0x09bfe0ac` | `duel_core_can_gemini_summon(side, slot)` | M | Gemini rules. |
| `0x09c0bd60` | `duel_core_can_set_spell_trap(side)` | M | Card locks. |
| `0x09bfca98` | `duel_core_has_spell_trap_zone_for(side, card)` | M | Zone availability. |
| `0x09da5774` | `duel_core_begin_summon_from_hand(mode, special, normal_flag)` | H | Starts a summon from the current answer. |
| `0x09da54ec` | `duel_core_init_summon_from_hand(side, ref, mode, normal_flag)` | H | Fills the record. |
| `0x09db2284` | `duel_core_init_normal_summon(side, ref, keep_tributes, attack)` | M | Kind 1. |
| `0x09db2df0` | `duel_core_init_procedure_summon(side, ref, position, keep_tributes)` | M | Kind 5. |
| `0x09db2de4` → `0x09db2ae0` | `duel_core_special_summon(side, entry, face_up, position, flags)` | H | Kind 4; 67 callers. |
| `0x09db2578` | `duel_core_init_flip_summon(side, slot)` | H | Kind 2. |
| `0x09db281c` | `duel_core_init_gemini_summon(side, slot, uses_normal)` | M | Kind 3. |
| `0x09db1e88` | `duel_core_run_summon_procedure()` | H | Pending-work state machine. |
| `0x09dab210` | `duel_core_summon_prepare()` | H | Per-card preparation dispatch. |
| `0x09da57c8` | `duel_core_summon_select_tributes()` | H | Generic tribute selection. |
| `0x09daea0c`, `0x09dafc90`, `0x09db00f8`, `0x09db1334` | `duel_core_summon_step_normal`, `_flip`, `_special`, `_procedure` | M | Execution stages. |
| `0x09da8ca4` | `duel_core_summon_prepare_synchro()` | M | Synchro materials. |
| `0x09da868c` | `duel_core_summon_prepare_contact_fusion()` | L | Extra-deck procedure for the `0x088648d4` list (messages `0x4c`, `0x3a`, `0x46`); body not read in detail. |
| `0x09dac2e0` | `duel_core_summon_raise_trigger(code)` | M | Negation window and timing event. |
| `0x09c268d0` | `duel_core_tribute_monsters(side, slot_mask)` | M | Batch send to the graveyard as tribute. |
| `0x09c16540` | `duel_core_change_position(side, slot, flip, a4, by_effect, a6)` | M | Command `0x33`. |
| `0x09c2b48c` | `duel_core_place_spell_trap_from_hand(side, index, zone, face_up)` | H | Command `0x51`. |
| `0x09dcd49c`, `0x09dcd5d0`, `0x09dcd67c`, `0x09dcd6c4`, `0x09dcd710`, `0x09dcd954`, `0x09dcd9cc` | `duel_core_action_*` | M | Executors of codes 3–9 (table above). |
| `0x09dc9b28` | `duel_core_open_card_list(side, mode, a3, a4)` | M | UI event `0x37`; CPU branch `0x09d9eeb8`. |
| `0x09dd08b8` | `duel_core_activate_from_list(side, location, card, ref)` | M | Extra-deck procedures, list activations. |
| `0x09cbace0` | `duel_effects_resolve_fusion_summon(ctx)` | M | Polymerization, Miracle Fusion. |
| `0x09cbac10` | `duel_effects_cond_fusion_summon(ctx)` | M | Their activation condition. |

`BOOT.BIN` card predicates used here (not renamed in this pass): `0x0885fef0` is a monster; `0x0885f864` summon class from the kind (0 normal, 1 effect/toon/spirit/union/gemini/tuner, 2 ritual, 3 fusion, 7 spell, 8 trap, 9 token, 10 synchro, gods `id − 0x1382`); `0x08860084` is Synchro; `0x088648d4` summoned from the extra deck by its own procedure; `0x08863d98` cannot be Normal Summoned/Set; `0x0886019c` Gemini; `0x08860af8` Elemental Hero; `0x08861298` Ancient Gear; `0x08866594` effect usable from the hand; `0x08866a1c` Toy Magician; `0x08866820` usable by either player; `0x088621c4` Arcana Force; `0x08863438` FLIP effect (genre `0x16`). Basis: the decompiled id lists checked against card names.

## Open questions

- Confirm the action-code/bit mapping and the reason codes in PPSSPP (breakpoint on `0x09dcf950`, watch `0x09e2d288`), and find the `rel_duel_draw` code that calls `duel_core_get_card_action_mask` and turns the mask into menu entries.
- Action 10 (`0x400` on the own deck, `0x09dcdbc0`): surrender or something else; what command `0x22` does.
- The Synchro material filter `0x09cbe5bc` (tuner + non-tuner rule, levels) and the role of card `0x1f32`; the bound returned by `0x09cbded4`.
- The fusion recipe table at `0x09debe98`: field layout beyond the id and the 2/3-material flag; how materials are matched (`0x09cba218`, `0x09cb97c4`).
- `duel_core_summon_prepare_contact_fusion` (`0x09da868c`) and the about 30 card-specific preparation routines called from `duel_core_summon_prepare`.
- Slot flag bit 3 is set by a Gemini summon, while `duel_effects.md` describes bit 3 as disabling effect handlers; reconcile (Gemini monsters are effect-less until summoned twice).
- Player word `+0x120` bits 20, 22 and 24 (set by several movement commands); the Ritual Summon path (no generic code seen; presumably in the ritual spells' handlers).
- Command `0x61` handler and the summon-negation window `0x09c32e54`.
