# Duel core (work package 4)

Rules machinery in `gmodule/rel_duel_eng.prx` (runtime base `0x09be1400`). Byte layouts of the engine's global structures (card instances, effect records, command queue, timing queue, input and request blocks, set-up parameters, module tables): [`docs/formats/duel-runtime.md`](../formats/duel-runtime.md). Card effects are covered in `duel_effects.md`; current ATK/DEF, Type, Attribute, Level and effect attachments in `stat-modifiers.md`; summoning, setting, battle positions and the action menu in `summon.md`; the Battle Phase, Life Points and the end of the duel in `battle.md`.

## Player state

Two per-player blocks of `0xb3c` bytes; player `p` (0 or 1) starts at about `0x09e2a528 + p × 0xb3c`. Fields established so far (confidence medium; from the code that reads them):

| Address (player 0) | Meaning | Basis |
| --- | --- | --- |
| `0x09e2a528` (`+0x00`) | Life Points (`int`; confidence high) | Only written by commands `0x23`/`0x24`/`0x25` and the duel start; `duel_core_check_win` returns 1 when the opponent's value is 0 (`battle.md`). |
| `0x09e2a534` (`+0x0c`) | Hand size | Draw-count rules such as "5 minus" and "7 minus" this value (`duel_effects_get_draw_count`); count of the list at `+0x124`. |
| `0x09e2a538` (`+0x10`) | Cards left in the deck | `duel_core_can_draw` compares the requested count with it; count of the list at `+0x304`. |
| `0x09e2a53c` (`+0x14`) | Cards in the graveyard (list at `+0x55c`) | `duel_core_find_in_graveyard`, `duel_core_find_card_location` (H). |
| `0x09e2a540` (`+0x18`) | Cards in the extra deck (list at `+0x4e4`) | Location `0x0c`; swapped with the hand and deck in tag duels (H). |
| `0x09e2a544` (`+0x1c`) | Cards in the banished zone (list at `+0x7b4`) | `duel_core_find_in_banished` (H). |
| `0x09e2a548` (`+0x20`) | Summons completed with command `0x2b` this turn | Incremented by `duel_core_cmd_summon_complete`, cleared by command 2 (M; `summon.md`). |
| `0x09e2a54c` (`+0x24`) | Lost flag (deck-out): the other side wins with reason 2 when it is set | `duel_core_check_win`; written (= 1) by the draw command `0x56` handler `duel_core_cmd_draw_cards` (`0x09dbb7d8`) when the side must draw from an empty Deck (`+0x10` = 0), found in the 2026-10-31 documentation round (H, code). |
| `0x09e2a554` (`+0x2c`) | Card id of a special-victory monster whose battle damage won the duel (reason 8) | `duel_core_cmd_lp_loss`. |
| `0x09e2a558` (`+0x30`) | Win reason of this side after the duel is decided | `duel_core_check_duel_end`, command 5. |
| `0x09e2a648` (`+0x120`) | Player flags word, laid out as a twelfth slot flag word (`+0x10 + 11 × 0x14`); bits 16–31 are per-turn and cleared by command 2 together with the slots' upper halves. Bits 0 skip the draw, 1 hand public, 2 hand card shown, 3 Deck must be shuffled, 16 summoned, 17 Normal Summon used, 18 attack declared, 19 a battle reached damage calculation, 20 Main Phase 1 no longer at its start, 21 Normal Summoned face-up, 22 Special Summon cap reached, 23 turn skipped, 24 own monster sent to the Graveyard, 25/26 Spell/Trap activated | `formats/duel-runtime.md`, "Player and slot flag bits" (H except bits 2, 19, 22 purpose: M). |
| `+0x124`, `+0x304`, `+0x4e4`, `+0x55c`, `+0x7b4` | Hand, deck, extra deck, graveyard, banished lists: 4 bytes per card; capacities from the layout 120, 120, 30, 150, 150 (M) | `duel_core_get_location_entry`. |
| `0x09e2a55c + i × 0x14` | Field slot `i`, 20 bytes each: slots 0–4 are the monster zones, 5–9 the spell/trap zones, 10 the field-spell zone | `duel_effects_target_filter` limits zone classes by these index ranges. |
| slot `+0x00` | Card id (`u16`, low 14 bits) | Read with `& 0x3fff`. |
| slot `+0x06` | Battle position (`u16`): 0 = Attack Position, non-zero = Defense Position (confidence high) | Target-filter bits `0x80` / `0x100`: the cards with `0x80` say "Attack Position" (12 of 13), those with `0x100` "Defense Position" (12 of 15); see `effect-tables.md`. |
| slot `+0x08` | Face-up (`u16`, non-zero = face-up; confidence high). Occupancy is the card id at `+0x00` | Target-filter bits `0x4` / `0x8`: "face-up" in 82 % of the `0x4` cards, "face-down" in 73 % of the `0x8` cards. |
| slot `+0x04` | Placement serial (`u16`, from the counter `0x09e2d1d0`; renewed when the card is turned face-up) | `duel_core_place_in_monster_zone` (M). |
| slot `+0x10` | Flags word (upper 16 bits cleared at every turn start by command 2): bit 21 cannot change position this turn (set on arrival, attack and manual change), bit 16 Normal Summoned face-up, bit 17 Flip Summoned, bit 18 + bit 6 Special Summoned, bit 14 Gemini summoned, bit 5 Tribute Summoned (`summon.md`). Also: bit 3 disables the card's effect handlers (`duel_effects_call_handler_08`); bit 11: a face-up card counts as a spell rather than a trap (hypothesis, medium); bit 12: a monster-zone card counts as a spell/trap, e.g. a trap monster (`0x09bee9d0`; hypothesis, medium); bit 4 and bits 1/3 are tested by the "return" filter bit `0x80000` for spell/trap zones; bit 2 is tested by `0x09bfbb38` | `duel_effects_target_filter` zone classes `0x20`–`0x40`. |

`0x09e28620` holds the attacking player (Mirror Force's activation condition compares it with the opponent).

## Locations and card movement

A **location id** names every place a card can be (H: `duel_core_get_location_entry` (`0x09dca4ec`), `duel_core_find_card_location` (`0x09bef4a4`), the list-move command `0x3e`, and the tutorial's field cursor which names 13 deck, 14 graveyard, 15 removed zone):

| Id | Location | Storage (player block) |
| --- | --- | --- |
| 0–4 | Monster zones | Slots at `+0x34 + i × 0x14` |
| 5–9 | Spell/trap zones | Same slot array |
| 10 | Field-spell zone | Same slot array |
| `0x0b` | Hand | List `+0x124`, count `+0x0c` |
| `0x0c` | Extra (Fusion) deck | List `+0x4e4`, count `+0x18` |
| `0x0d` | Deck (index 0 = top) | List `+0x304`, count `+0x10` |
| `0x0e` | Graveyard | List `+0x55c`, count `+0x14` |
| `0x0f` | Banished | List `+0x7b4`, count `+0x1c` |

In commands a location is often packed as `index << 6 | location << 1 | side`. `duel_core_find_card_location(ref)` returns `side | location << 8 | index << 16`, or `0x1000` when the card is nowhere.

**Card references.** Every physical card of the duel has an instance number (9 bits) indexing the 6-byte table `0x09e2bbcc` (low 14 bits of the first `u16` = card id; byte `+2` bits 0–1 a 2-bit counter incremented when the card enters a monster zone, the graveyard or the banished zone, purpose M). A list entry or a field slot stores the card id in `u16 +0` bits 0–13 and the instance number as `(u16 +2 bits 7–14) << 1 | (u16 +0 bit 14)`. (H: the same expression appears in every reader.)

**Primitives** (all M unless noted; the summon-specific ones are in `summon.md`):

| Address | Name | What it does |
| --- | --- | --- |
| `0x09dca4ec` | `duel_core_get_location_entry(side, location, index)` | Pointer to the 4-byte list entry or 20-byte slot. H |
| `0x09bf77e4` | `duel_core_zone_remove(side, location, index)` | Removes a card: per-list removers (`0x09c02e60` hand, `0x09bf149c` extra, `0x09bf12a4` deck, `0x09c00f04` graveyard, `0x09c018b4` banished); for a slot, ends its lingering effects and clears the 20 bytes. Called only by command handlers. H |
| `0x09bf794c` | `duel_core_zone_insert(side, location, pos, entry)` | Inserts: hand append, deck top/bottom by `pos`, graveyard/banished append, monster zone via `duel_core_place_in_monster_zone(side, slot, entry, position, face_up)` (`0x09bef1cc`, also sets slot bit 21), spell/trap zone via `0x09bef348`. H |
| `0x09db4560` | `duel_core_cmd_move_list_card` | Command `0x3e`: list-to-list move (hand, deck, extra deck, graveyard, banished). |
| `0x09c18550` | `duel_core_send_hand_card(side, entry, flags, dest, discard, reason)` | Hand card to the graveyard (`0x0e`) or banished (`0x0f`); banish-instead-of-Graveyard rules (`0x09c0d160`) turn the graveyard into banishment, and Imperial Iron Wall (`0x09c0d5e8`, "no Imperial Iron Wall active") turns banishment back into the graveyard; posts `0x3e`, `0x32` or `0x45`. Wrappers `0x09c18d70`, `0x09c18dc8`, `0x09c18e14`, `0x09c18f98`, `0x09c18fe4`. |
| `0x09c18384` | `duel_core_return_hand_card_to_deck(side, index, top)` | Command `0x3e` hand → deck. |
| `0x09c2b110` | `duel_core_send_list_card_to_graveyard(side, location, index, entry, a5, a6)` | Hand/deck/extra card to the graveyard or banished (command `0x30`); wrappers `duel_core_send_hand_entry_to_graveyard` (`0x09c2b394`), `duel_core_send_deck_card_to_graveyard` (`0x09c2b3b4`), `duel_core_send_extra_card_to_graveyard` (`0x09c2b420`). |
| `0x09c20ad0` | `duel_core_send_field_card(side, slot, dest, flags, by_card)` | Removes a field card to `dest` after immunity checks (`flags` bit 0 by opponent, bit 1 destroy, bit 2 battle; full list in `effect-helpers-movement.md`); posts `0x4b`, `0x4d`, then one of `0x30`, `0x31`, `0x32`, `0x3c`, `0x3f`, `0x45`; returns the final destination. Called from the batch executor `duel_core_send_batch_step` (`0x09c232bc`), which the `duel_core_request_*` functions start. |
| `0x09c2be00`, `0x09c2be98` | `duel_core_post_set_player_flag(side, bit, value)`, `duel_core_post_set_slot_flag(side, slot, bit, value)` | Flag changes as commands `0x21` / `0x29`. H |

Commands that move field cards: `0x30` field/list → graveyard or banished (`0x09db7db8`), `0x31` (`0x09db8a50`), `0x32` graveyard → banished (`0x09db9f40`), `0x3c`/`0x3d` between field slots or sides (`0x09db5db4`, `0x09db6304`), `0x3f`, `0x40` (`0x09db4d34`, `0x09db561c`), `0x45` (`0x09db9878`), `0x56` draw (`0x09dbb7d8`).

**Argument packing** (from the posting code in `duel_core_send_field_card` `0x09c20ad0`, `duel_core_send_deck_ref_to_graveyard_ex` `0x09c2a69c`, `duel_core_banish_graveyard_card_ex` `0x09c19488`, `duel_effects_swap_control` `0x09c1758c`, `duel_core_move_field_card_to_slot` `0x09c172f8`, `duel_core_post_place_list_card_on_field` `0x09c19a24`, and the handlers that decode `a, b, c` at `0x09e290fa/fc/fe`; `side` = bit 15 of the opcode unless noted). "Event word" is the 9-bit card summary of the timing event (instance, side, slot, position, face) built by `send_field_card`. Who calls these and why: `effect-helpers-movement.md`.

| Cmd | Handler | `a` | `b` | `c` | Effect | Conf. |
| --- | --- | --- | --- | --- | --- | --- |
| `0x30` | `0x09db7db8` | low byte location (field slot 0–10, or `0x0b`/`0x0c`/`0x0d` with the index recomputed), high byte index | low byte destination (`0x0b`–`0x0f`, `0x10` = token vanishes, < `0x0b` = a field slot); bits 8–11 flags (bit 8 by opponent, copied to the entry's bit 3; non-zero shows UI event `0x4e`), bits 12+ keep the entry's bit 15 (M) | card instance (used to find hand, extra-deck and Deck sources; corrected in the 2026-11-03 round, formerly read as an event word) | Card destroyed by an effect (or a token sent): `zone_remove` + `zone_insert`, deck insertion at the top, UI event `0x1a` (move) and `0x4e` | H |
| `0x31` | `0x09db8a50` | slot | destination | bit 0 by opponent | Card destroyed by battle (UI event `0x20`), then the same move | H |
| `0x32` | `0x09db9f40` | low byte location (< `0x0b` field slot, high byte its index; otherwise the index is found from `c`) | flags: bit 0 by opponent, bits 4–5 counter state, bits 6–7 "remember the field slot" | card instance | Card banished (destination always `0x0f`, appended); field markers listed in the handler are carried over as player markers | H |
| `0x3c` | `0x09db5db4` | `side | slot << 8` (source) | `side | slot << 8` (target, side may differ) | new face-up value (`u16 slot +0x08`) | Moves the 20-byte slot to an empty slot, possibly of the other player (control change); clears slot bit 25, sets bit 10 and clears bit 21 when the side changes; moves markers (`0x09be7908`); for a spell/trap target clears the position and the word at `+0x0c` and sets slot bit 20 when face-down | H |
| `0x3d` | `0x09db6304` | `side | slot << 8` | `side | slot << 8` | (overwritten: card id) | Swaps two occupied slots (Creature Swap); both get slot bit 10, lose bits 21 and 25; markers swapped | H |
| `0x3f` | `0x09db4d34` | `index << 6 | location << 1 | side` (location < `0x0b`: field slot, index ignored); no side bit in the opcode | `index << 6 | dest << 1 | dest_side`; a non-zero `index` is replaced by the destination list size (append at the end, i.e. Deck bottom), 0 inserts at the front (Deck top) | flags: bit 0 by opponent, bit 3 do not count statistics, bits 4–5 entry bits 0–1, bits 6–7 remember the field slot (as `0x32`) | Field or list card sent (not destroyed) to hand, extra deck, Deck, Graveyard or banished; hand: sets player flag 2, Deck: player flag 3 | H (layout), M (flag bits) |
| `0x40` | `0x09db561c` | `ref << 6 | location << 1 | side` (source list card, found by instance) | `offset << 6 | slot << 1 | side` (target slot = `slot + offset`) | low byte face-up, high byte position | List card (Graveyard, banished …) placed directly in a field slot; a Graveyard/banished card is first brought to the top of its list (UI event `0x18`); markers on the banished card follow it | H |
| `0x45` | `0x09db9878` | location (field slot) | destination | card instance | Card Tributed (UI event `0x2c`), then moved; Deck sets player flag 3 | H |

The `0x3e` list-to-list move is in `summon.md`.

## Duel globals

| Address | Meaning | Basis |
| --- | --- | --- |
| `0x09e2d1d8` | Side whose turn it is (0/1); 510 reads | `duel_core_next_turn` toggles it. |
| `0x09e2d1e0` | Turn counter | Incremented by `duel_core_next_turn`; set to 9 or 0 by the start functions. |
| `0x09e2d1e8` | Current phase: 0 Draw, 1 Standby, 2 Main 1, 3 Battle, 4 Main 2, 5 End, 7 none (turn transition) | `duel-phases.md`; 203 reads. |
| `0x09e2d1f4` | Duel mode: 2 or 3 depending on the start function | `duel_core_start_mode2` / `_mode3`. |
| `0x09e2d1fc` | Tag-duel flag | `tag_duel.md`. |
| `0x09e2d200` | Set when a duelist value at `0x09e02998`/`0x09e0299c` is 2 | `duel_core_reset`. |

`duel_core_reset` (`0x09dc7cb0`) clears the duel state regions (`0x09e2a528` ×`0x2de4`, `0x09e02ff8` ×`0x25628` and nine smaller ones). Four entry points call it: `duel_core_start_mode2` (`0x09dc8088`), `duel_core_start_mode3` (`0x09dc8148`), `duel_core_start_plain` (`0x09dc7fcc`) and `tag_duel_start_with_partner_decks` (`0x09dc7ff4`).

## Key functions

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x09c29bc8` | `duel_core_draw_cards(player, count)` | H | Forwards to `duel_core_draw_cards_ex(player, count, 1, 0)`; called by draw effects such as `duel_effects_resolve_draw`; 47 callers. |
| `0x09c28f44` | `duel_core_draw_cards_ex(player, count, a, b)` | M | Body not read. |
| `0x09c0d920` | `duel_core_can_draw(player, count) → bool` | H | Negative count selects the opponent; false while card `0x178b` or `0x1885` prevents drawing; otherwise compares with the deck size. |
| `0x09c2c134` | `duel_core_get_effective_card_id(ctx)` | M | 0 unless bit 0 of `ctx+6`; then the id at `ctx+0x18`, resolved through a table at `0x09e2bbcc` for card `0x1935`. |
| `0x09dbc184` | `duel_core_next_turn()` | H | Handler of command 4; documented in `duel-phases.md` ("Phase-changing commands"). Toggles `0x09e2d1d8`, increments `0x09e2d1e0`, sets the phase to 7, walks the 11 field slots of both sides for two special cards, compares the sides' LP (`+0x00`), and in tag mode swaps the next side's active duelist. Verified in PPSSPP (Sessions A and B). |
| `0x09dc07f8` | `duel_core_push_command(op, a, b, c)` | H | See "The command queue" below. Verified in PPSSPP (Sessions A, B, D). |
| `0x09dc7cb0` | `duel_core_reset()` | H | Clears the duel state regions and sets the phase to 7. |
| `0x09bf1f74` | `duel_core_load_deck(side, deck)` | M | Called with a `0xc0`-byte deck structure; body not read. |

`0x09e2bbcc` is a table of 6-byte entries indexed by the `u16` card references stored in hand, deck and field lists; its low 14 bits are the card id.

### The command queue: `duel_core_push_command` (`0x09dc07f8`)

`void duel_core_push_command(int op, int a, int b, int c)` is how the whole engine changes duel state: rules code, effect handlers, the summon, battle and phase steps, the AI and the tutorial post **engine commands**, which `duel_core_process_command_queue` later executes one at a time (`duel-phases.md`, "Phase-changing commands"). The function stores the four arguments as `u16` at `0x09e29100 + count × 8` (`op`, `a`, `b`, `c`) and increments the count `0x09e29900`. It does nothing when the duelist kind word `0x09e02998` is 3 (replay/demo mode, `ai.md`) or when the queue already holds 256 entries (the command is then lost; no error path). Bit 15 of `op` is the side, the low 12 bits the command code. No return value. Callers: about 390 call sites in about 200 functions (the full list comes from the call graph; `effect-classification.md` recovers the code at 385 of 388 sites), plus the thunk `0x09be14bc` and the tutorial (`tutorial.md`). Confidence H (decompiled).

**Verified in PPSSPP** (2026-10-26/27, [`results/2026-10-26-sessionA-part1.md`](../verification/results/2026-10-26-sessionA-part1.md), [`results/2026-10-27-sessionB.md`](../verification/results/2026-10-27-sessionB.md), [`results/2026-10-27-sessionD.md`](../verification/results/2026-10-27-sessionD.md)): an execute log at its entry recorded `(op, a, b, c)` for whole duels; bit 15 was set on every CPU command, and every posted command then took effect in posting order (phase changes, LP changes, chain links, markers).

## The chain

Activated effects are pushed on a chain stack of 24-byte links; the link on top is the `ctx` that effect handlers receive (`duel_effects.md`).

| Address | Meaning |
| --- | --- |
| `0x09e28cb4 + (n − 1) × 0x18` | Chain link `n` (1-based); the link below is at `− 0x18`. |
| `0x09e28e34` | Number of links. |
| `0x09e28e38` | Index walked downwards while resolving. |
| `0x09e28f5c` | State of the resolution state machine (`0x66`, `0x67` among its values). |

Link layout (also the effect context): `u16 +0` card id; `u16 +2`: bit 0 the controlling side, bits 1–5 the field slot index (only values below 11 are field slots), bits 6–11 the event code (`0x12` when an attack is declared, `0x24` selects the spell/trap table in `duel_effects_find_record`); byte `+3` bits 4–5 the handler-table selector; further fields not mapped. Confidence: medium-high (the resolver decodes `+2` into side and slot and indexes the player block with them).

`duel_core_chain_step` (`0x09c2f1fc`, 14,148 bytes; callers `0x09c32dac`, `0x09c32e54`) is the resolution state machine (states 0–7, 100, `0x65`–`0x68`, LIFO); building, response windows, the trigger queue, spell speed, negation and the full link layout are documented in `chain.md`. Corrections to the table above: `0x09e28e38` is the index of the link being activated or resolved, and `0x09e28f5c` is the resolution state (`0x09e28f54` is the building state).

## Function families named in the 2026-10-31 round

Basis and method: `system.md`, same section. 517 new `duel_core` names in `rel_duel_eng`, 62 in `rel_duel_draw`, 16 in `rel_duel_mgr`.

| Family | Count | Evidence |
| --- | --- | --- |
| `export_accessors` | 57 | The exported getters and setters at `0x09be147c`–`0x09be20ec`: turn, seed, local side, duelist kinds, LP, list counts and references, slot fields, hooks. |
| `engine_commands`, `engine_command_stubs`, `command_posts` | 64 | Command handlers. The jump table of `duel_core_execute_command` at `0x09e00944` was decoded from the module file; it agrees with every documented code. Command `0x22` makes a side concede: its LP become 0 and the opponent's block `+0x30` gets the reason passed in `b` (`0xc` from `duel_core_action_surrender`; `0xd` skips UI event `0x35`; its poster is `duel_core_declare_turn_limit_loss` (`0x09dcad94`, found in the 2026-10-31 documentation round), which posts `0x22` with `a = 0xd` once per duel (guard `0x09e2d1d4`) and is called by `duel_core_step_turn_end` and by `rel_duel_mgr`'s `duel_core_tick_turn_timers`; the "turn limit" reading of `0xd` is withdrawn, the turn-limit win is reason 11 of `duel_core_check_win`). |
| `effect_records` | 33 | Find, count and detach records in the effect pool `0x09e2c7cc`. |
| field, hand, deck, graveyard and banished counts | 61 | Counting queries (`duel_core_count_tokens` …). `0x09bf9cec` has the same body as `duel_core_count_monsters` (`_alt`). |
| `list_primitives` | 22 | Append, insert and remove for hand, deck, extra deck, graveyard and banished; card-instance allocation. |
| `end_phase_checks`, `standby_checks`, `battle_end_checks` | 56 | `0x09ddc56c`–`0x09ddf2dc`, `0x09de0d38`–`0x09de21f4` (queue triggers with event 2, the Standby Phase), `0x09dd9c24`–`0x09dda8f0` (event `0x17`). |
| `summon_steps`, `summon_filters`, `summon_procedures`, `summon_wrappers` | 54 | Steps of `duel_core_summon_prepare`; procedure material filters that return `0x800`. |
| `pending_requests`, `prompt_requests`, `prompts`, `response_windows` | 36 | Card-request block `0x09e2d2e0`, prompt block `0x09e2d2c4`, UI `0x36` dialogs. |
| `selection_filters`, `zone_filters`, `slot_predicates`, `field_predicates` | 29 | Zone callbacks returning `0x800`. |
| `net_link`, `net_sync` | 15 | The link-duel packet processor `0x09dcc94c` and the requests the local side runs for the peer. |
| others | 34 | `duel_result`, `deck_stack_assist`, `candidate_list`, `duel_statistics`, `list_activation` (table `0x09e00dbc`), `last_turn`, `location_access`, `player_input`, `trigger_queue`, `control_rules`. |
| `view_side_wrappers` (`rel_duel_draw`) | 62 | `duel_core_view_*`: the draw module's wrappers of the engine exports `0x09be1840`–`0x09be1ea0`. |
| `duel_setup`, `tutorial_imports` (`rel_duel_mgr`) | 9 | Start LP by set-up `+0x196` (8000/2000/4000/12000/16000/custom), the tutorial import stubs named after the offsets of `tutorial.md`. |

Duel set-up block fields seen by `rel_duel_mgr` (M, not yet in `save.md`/`tutorial.md`): `+0x188` seed, `+0x18c` first player, `+0x190` mode, `+0x192` 1 single / 2 tag, `+0x193` tutorial lesson, `+0x194` BGM set, `+0x196` LP mode, `+0x197` time limit, `+0x198`/`+0x19c` custom LP. The BOOT duel session at `0x08836718` is `0x398` bytes: `+0x00`–`+0x0c` turn timers, `+0x34`… per-game results.

Findings to reconcile, settled on 2026-10-31 (round 2):

- `0x09c0f55c` `duel_core_request_pick_hand_cards` → **`duel_core_request_tribute_for_effect` (changed, M).** It posts card request mode 9 (`0x09e2d2e8 = 9`, side, source `side | slot << 8`, count in the low byte and an optional Type in the high byte of the third argument). The worker `duel_core_card_request_select_tributes_step` (`0x09c11fec`) counts and selects field slots with `duel_core_filter_tribute_selection_candidate` (`0x09c114e0`: zones 0–4 that pass `duel_core_can_tribute_for_effect`, of the Type when one is given, not the source, not yet picked). Callers are cost handlers. `effect-helpers-misc.md` is corrected.
- Turn names → **`duel_core_set_turn` renamed `duel_core_set_turn_counter` (H)**: it writes the turn counter `0x09e2d1e0` that `duel_core_get_turn_counter` (`0x09be1840`) returns. **`duel_core_get_turn_count` renamed `duel_core_get_slot_turn_count` (H)**: it reads the per-slot `u16` at slot entry `+0x0c` (`0x09e2a568 + slot·0x14`) for cards whose `card_db_get_turn_counter_rule` is positive, with card-specific conditions, and returns −1 otherwise; it has nothing to do with the global turn counter.
- `0x61` → **settled, `summon.md` corrected**: `duel_core_execute_command` case `0x61` calls `duel_core_cmd_show_summon_declaration` (`0x09dbe9cc`), as `tutorial.md` says.
- Command `0x22` → **settled** (`summon.md`, "Open questions"): surrender posts reason `0xc`; the meaning of `0xd` is open.

## Round 2 of the 2026-10-31 naming

Method as in the first round (`system.md`): the still-unnamed functions were re-dumped from Ghidra with the current names, read in packs with full bodies (up to 160 lines), and named H/M with a basis in `re/names*.csv` under "round 2". 40 new `duel_core` names: 13 more `duel_core_view_*` wrappers in `rel_duel_draw`; in `rel_duel_eng` the engine command 8 handler `duel_core_cmd_show_declaration` (`0x09dbc6d8`: shows `duel_core_show_declaration_message` with the command arguments, then clears the busy word `0x09e29904`), the duelist timers of the BOOT session (`duel_core_get_duelist_timer_seconds`/`_value`), and six 8-byte entries that fix an argument and enter a neighbour's body (`duel_core_can_send_slot_to_graveyard`/`_to_hand` …).

## Documented functions

The functions of this group that reached the `documented` stage in the 2026-10-31 documentation round and in the 2026-11-03 round (prototype, purpose, return value, side effects and callers, read from the decompilation) are listed in [`functions/duel_core.md`](functions/duel_core.md).

## Large procedures documented in the 2026-11-03 round

Basis: full reads of the Ghidra decompilations of 47 `duel_core` functions of `rel_duel_eng` below `0x09d00000` (the largest still undocumented ones, 100 to 13,844 bytes) and four `rel_duel_draw` wrappers. Per-function rows are in `functions/duel_core.md`. Confidence is high for control flow and the addresses named; card readings stay at the ids. Nothing here was traced in PPSSPP.

### The field-card send pipeline

Every field card that leaves its zone through an effect, a cost, a Tribute or battle passes through the same five functions:

1. A `duel_core_request_*` function fills the send-batch request (`effect-helpers-movement.md`).
2. `duel_core_send_batch_step` (`0x09c232bc`), polled by `duel_core_run_turn_flow`, works through it frame by frame. State 1 clears the masks. State 2 handles battle-only banish rules. State 3 filters the slot mask with `duel_core_can_send_field_card` and runs a pre-pass. States 10–12 offer the replacement prompts; each prompt is answered in state + 100 (`0x6e`–`0x70`). State 100 opens a timing batch and moves every slot for real. States `0x65`–`0x67` handle Crystal Beast placement, the post-battle `0x1df5` discard and the end of the batch.
3. `duel_core_send_field_card` (`0x09c20ad0`) does one slot. The executor state selects one of three modes:
   - **Pre-pass** (state ≠ 2 and < 100): runs the immunity and replacement checks and records the slot in `0x09e2bba8`, and in `0x09e2bbb8` when an effect destroys it. Replacements are taking counters off, the substitutes already chosen, and equip-linked cards destroyed instead.
   - **Dry run** (state 2): returns the final destination after all redirects and does nothing else.
   - **Real** (state ≥ 100): builds the event word and posts one of `0x31`, `0x30`, `0x3c`, `0x32`, `0x3f` or `0x45`.
4. `duel_core_send_field_card_body` (`0x09c1be50`) runs after a real move. It queues the leaving card's own "sent/destroyed" trigger: a compare chain over about 170 card ids picks the trigger kind and argument. It also queues the watchers of other cards (field, hand and Graveyard triggers, face-up-copy flags, player markers, burn damage). For a battle event it then calls `duel_core_apply_destroyed_by_battle_rules` (`0x09c1b224`). That function handles the destroyer's "when this card destroys a monster by battle" trigger, its markers, and the equip cards of the destroyer that trigger on event `0x16`.
5. `duel_core_apply_leave_field_rules` (`0x09c1fb50`) runs after every mode except the dry run. It handles cascades:
   - cards that take other cards with them, such as link sources sending every linked card to the Graveyard, set pieces, Toon and Spirit rules;
   - for every record in the leaving slot's effect list, `duel_core_get_linked_card_leave_rule` decides whether the record's source (for example an equip spell) follows the card to the Graveyard.

   The per-card flag bits that these follow-up sends carry (`0x80000` destroyed, `0x100000` battle, `0x200000` Tribute, `0x400000` to the Graveyard, `0x800000`/`0x1000000` the source's controller moved it to Deck/Extra Deck or hand, `0x2000000` always) are the same bits that `send_field_card_body` tests for the per-card triggers of equip cards.

Monsters destroyed by battle skip state 3. `duel_core_send_battle_destroyed_cards` (`0x09c2215c`) runs in both passes and does three things:

- sends each battle record's monster whose slot flag bit 2 marks it as destroyed, to the Graveyard, the banished zone or the Deck by destroyer rules;
- destroys the cards that die with it (effects `0x1b35`, `0x1e28`, `0x15b3`) and the attacker destroyed by a defender's rule;
- shuffles any Deck that received a card.

Cards in lists do not use the batch. `duel_core_send_hand_entry_to_graveyard` (`0x09c2b394`), `duel_core_send_deck_card_to_graveyard` (`0x09c2b3b4`) and `duel_core_send_extra_card_to_graveyard` (`0x09c2b420`) are thin wrappers of `duel_core_send_list_card_to_graveyard` for locations `0x0b`, `0x0d` and `0x0c`.

On the command side, the move handlers call `duel_core_detach_effects_of_moved_card(from, to, entry)` (`0x09be5eb8`). It frees the effect records that refer to the moved card's instance. One group of records is freed when the card leaves the Graveyard or banished zone, or goes to the hand, Deck or Extra Deck. Another group is freed on any move.

**Event word of a field card leaving its zone** (built by `send_field_card`, low 9 bits passed as command `c`, all 32 bits passed to the body and to timing events `0x16`/`0x1c`):

| Bits | Meaning |
| --- | --- |
| 0–8 | Card instance |
| 9 | Controller side |
| 10–13 | Slot |
| 14 | Defense Position (slot `+0x06` bit 0) |
| 15 | Destroyed (flag `0x2`) |
| 16 | By battle (flag `0x4`) |
| 17 | Was face-up (slot `+0x08` bit 0) |
| 18 | Side of the cause (controller XOR by-opponent) |
| 19–22 | Final destination location |
| 23 | Activation-negated flag `0x8` |
| 24 | Gemini monster with its effect enabled |
| 25, 27, 28, 30 | Type-specific bits (Type `0x14`; battle in Defense Position with lower ATK than DEF (H for the condition, M for the reading); Type `0x15` by battle; Type 9) |
| 26 | The card is the cause of its own removal (cause link `0x09e2d2a4` instance) |
| 29 | Redirected to the banished zone by a card of the other side |

`duel_core_flip_card_face` and `duel_core_move_field_card_to_slot` build the same word for timing events 9/`0xc` and `0x19`, using the same low bits. The meaning of bits 16–23 changes per event: for example, bit 16 is "by the opponent" in a flip, and bits 19–22 are the target slot in a control change.

**Executor masks** (closes part of the open question in `duel-runtime.md`). All masks use bit `slot + 16 × side`.

| Address | Meaning |
| --- | --- |
| `0x09e2bba8` | Slots taken in by the pre-pass; cleared one by one when they are really sent |
| `0x09e2bbac` | A destruction substitute was chosen for the slot; the field zone uses it as "cancelled" |
| `0x09e2bbb0` | The 0x1e28 replacement applies |
| `0x09e2bbb4` | Crystal Beasts that will be placed in a spell/trap zone instead |
| `0x09e2bbb8` | Slots destroyed by an effect |
| `0x09e2bbbc` | Slots that were handled (replaced, or actually moved) |
| `0x09e2bbc0` | Slots that reached the requested destination |
| `0x09e2bbc4` | `duel_core_get_banish_redirect_mask()` saved at the start of the real pass |

### Attack legality

The attack checks are spread over six predicates that the battle steps, the action menu and the AI call:

| Function | Address | Question it answers |
| --- | --- | --- |
| `duel_core_check_attack_restrictions(side, slot, full)` | `0x09bea7a8` | Can this monster declare an attack at all? It reads the stat block, the slot flags and about 90 card rules. With `full` it also checks the per-attack rules and the attack costs (Toons 500 LP, 1000 LP cards, `0x1320` adding 500 per copy), which must stay below the LP. On refusal it writes reason `0x13` (or `0x10` for a prohibited card) to `0x09e2d288`. |
| `duel_core_has_no_attacks_left(side, slot)` | `0x09bea184` | Has the monster used up its attacks this turn? Slot flag bit 22 = has attacked, bit 23 = no further attack (M), plus the per-card attack counts kept as effect records (`0x1505` family, `0x1a4e`, `0x19c1`, `0x186c`). |
| `duel_core_is_direct_attack_allowed(side, slot)` | `0x09becb60` | May it attack the player at all? Blocked, for example, by the opponent's forced-target monsters `0x17fc` and by `0x1ad2`/`0x1cd4`. |
| `duel_core_get_direct_attack_mode(side, slot, check_card)` | `0x09bed2d8` | 0 no; 1 may attack directly by an effect (step 2 then asks "attack directly?"); 2 must attack directly. |
| `duel_core_is_valid_attack_target(atk side, atk slot, tgt side, tgt slot, mode)` | `0x09beb8cc` | May it attack this monster? `mode` 0 applies only the attacker-side and forced-target rules, non-zero also the target's "cannot be attacked" protections, 2 skips the `0x1318` rule. Selection filters `duel_core_filter_attack_target_slot` and `duel_core_filter_valid_attack_target` (`0x09c11d64`) wrap it. |
| `duel_core_has_piercing(side, slot)` | `0x09bedf1c` | Does it inflict piercing damage? Read by `duel_core_battle_resolve` and the AI. |

All six follow one pattern: a gate on the card's own effect (`duel_core_is_effect_active` plus slot flag bit 2 clear), per-card compare chains, and global rules gated by the immunity words of the stat block (bit `(side ≠ source side) + 1`).

At the declaration, three functions record the attack:

- `duel_core_raise_attack_event(mode)` (`0x09c17ec4`) raises timing event `0x12` and queues the triggers. Its event word holds the attacker, the target, the direct flag and `mode > 0`.
- `duel_core_attach_attack_markers` (`0x09c17aa4`), at the start of the Damage Step, records the first-attack value `0x1505` and the attacker-to-target link through command `0x35`.
- `duel_core_apply_phase_start_attack_rules(new, old)` (`0x09be6d90`, run by `duel_core_cmd_enter_phase`) clears those records at the next phase change, together with slot flag bit 27.

### Current Level, Attribute, Type and name

`duel_core_get_level_ex` (`0x09c0a6ac`), `duel_core_get_attribute` (`0x09c0b204`), `duel_core_get_race_ex` (`0x09c0ac6c`) and `duel_core_get_slot_name_id` (`0x09bf0328`) apply modifiers in the same order:

1. Card data value (`card_db_get_*`); an empty slot gives 0.
2. Only a face-up card in a monster zone with slot flag bit 3 clear is modified. Name rules apply to spell/trap zones too.
3. Copy rules: `0xf57` takes the value of its linked monster (recursive call); a trap monster takes the matching word of `duel_core_apply_trap_monster_stats`. Name copies are kind-2 records (`0x1f0e`, `0x1dc2`, `0x1d43`, `0x1a74`) whose value is a monster that is not prohibited.
4. Overrides. Attribute and Type use "newest wins": each candidate carries a timestamp, either the placement serial (slot `+0x04`) of a continuous card on the field or the record timestamp (`+0x06`) of an effect record, and the newest one replaces the value. The kind-5 records `0xf49`/`0xf47` act only while no other override applied. `get_race_ex(…, skip)` ignores the override whose timestamp equals `skip`, so a caller can evaluate "the Type without this card's effect".
5. Level only: additive deltas from link records (kinds 7/10) and temporary records (kinds 1–3), and `0x1ec1` sets the Level and discards the earlier deltas. A non-zero Level is clamped at 1. `base_only` skips the temporary part.
6. Name only: when no copy record is newer than the card's placement, built-in "treated as" rules apply (4 monsters, and `0xecd` → `0x12be` in a spell/trap zone).

Each source is accepted only if the monster's spell or trap immunity word does not block that source's side. The getters read the immunity words with the nesting counter `0x09e2d244` raised, which suggests the immunity functions use it to avoid recursing into these getters (M).

### Negation, targeting links and forced positions

- `duel_core_set_slot_negated(side, slot, negated)` (`0x09c19d1c`) is called only by `duel_effects_update_negated_slots`. It owns slot flag bit 8 = "effect negated", which explains why many predicates test bit 8. When a card becomes negated, it removes the card's own records (commands `0x36`/`0x37`), resets slot values, destroys monsters equipped through kind-12 records, and removes every counter.
- `duel_core_check_targeting_links(side, slot)` (`0x09c147f0`) is run for every slot by `duel_effects_rule_check_all_targeting_links`. It makes at most one correction per call:
  - destroys a source whose link the target's shield negates;
  - drops links whose condition no longer holds;
  - destroys equips that `duel_effects_filter_equip_target` no longer accepts.
- `duel_core_apply_forced_positions` (`0x09cdd74c`), called from the chain builder, enforces the seven continuous position-changing cards of table `0x09dedadc`, oldest source first.

`set_slot_negated` and `apply_forced_positions` share the counter `0x09e2d238`: after about 10 repetitions they destroy the card instead of changing it again. This is presumably a guard against endless negate/flip loops (L).

### Pending actions and selections

`duel_core_run_pending_action` (`0x09c0e8b8`) is the single driver of the pending-action block `0x09e2d2e0`. It dispatches 21 kinds to their workers and synchronises link duels (packets `0x1e` request, `0x1f` result). The request finishes only when the worker reports done **and** the engine command queue is empty.

Workers documented in this round:

- coin toss, kind `0x12` (`0x09c0decc`, with the Arcana Force call and the retoss);
- `duel_core_pending_select_with_hint`, kind 10;
- `duel_core_card_request_select_list_cards_step`, kind `0xe`;
- inline negation of chain links, kind `0xc`. It sets bits in link byte `+0x04` unless `duel_effects_cannot_be_negated`.

### Response windows

- `duel_core_timing_event_allows_card_response(side, card)` (`0x09ccacdc`) filters by event code. A card is offered in a window only when a queued timing event is one it can react to.
- `duel_core_has_activatable_response(link, side, strict)` (`0x09ccb534`) asks whether any field or hand card can be activated in response. In strict mode, a player responding to their own link is limited to 21 listed cards, unless they hold one of five cards that lift the limit.
- `duel_core_format_response_window_text` (`0x09ccba44`) picks the window's prompt text from the first queued event.
- `duel_core_chain_collect_auto_responses` (`0x09c2ddbc`) adds the automatic responders (`0x148e`, `0x1aa5`, `0x1cb0`, …) to the chain being built.

### Other procedures

- **Drawing.** `duel_core_draw_cards_ex(side, count, by_effect, quiet)` (`0x09c28f44`) is the body behind every draw. It returns 1 when the cards are drawn, −1 when the Deck is too small (command `0x56` still sets the lost flag), and 0 when the draw is replaced by a mill or blocked (commands `0x2e`/`0x2f`). It raises timing event `0x1a` per card, and the triggers that react to drawing run only when `quiet` is 0.
- **Summon gate.** `duel_core_is_summon_kind_allowed(side, kind_mask, card)` (`0x09c0bdec`) is shared by the five `can_*_summon` checks. It covers rule modes 4, 5 and 6 of `0x09e02cac` (no Normal Summon or Set, no Special Summon, no Set) and about 40 lock cards.
- **End of duel.** `duel_core_record_duel_result` (`0x09be4648`, exported to `rel_duel_mgr`) writes the result block, experience and save statistics. It calls `duel_core_check_duel_condition` (`0x09be3bc0`), which evaluates the challenge selected by the save's record table word `0xa4` (byte `+0x290`): about 115 conditions over duel statistics, results, turn counts, cards used and save progress. The index is the Duel Record screen's active challenge; every condition, the writer and the reward are in "Duel challenges" below.
- **View wrappers.** `duel_core_view_get_zone_highlight_states` returns the slot relation table of `duel_core_build_slot_relation_table` (`0x09c0a174`). The values are 7 blocked, 6 marked by the card, a link kind, and `| 0x100` targeted.

### The last default-named functions (2026-11-04, round 5)

The six `duel_core` and the one `duel_effects` function that still had Ghidra default names were read (Ghidra and capstone) and documented (`functions/duel_core.md`, `functions/duel_effects.md`):

- `duel_core_update_duel_records` (`0x09be26f4`, 1,976 bytes): Ghidra cut the body at a 40-case jump table (`0x09deb5a0`, `jr` at `0x09be2754`); `FixJumpTableFunction.java` restored it. After an offline default-rules duel, `duel_core_record_duel_result` calls it to raise the 49 best-record values of the save record table (`save.md`, "Record table"): records 0–`0x23` from duel statistics or sums/maxima of them (`duel_core_get_statistic`), `0x24` from the set-up tail block, `0x25` (duel time in seconds, `tail +0x10 / 30 + 1`) and `0x26` (turns) lower-is-better, `0x27` (turns) higher-is-better; records 2 and `0x1d` have no case and `0x28`–`0x30` (mini-game scores) are only cleared in the per-duel copy. Each improved value is copied to tail `+0x3c + 4i` and flags the new-record byte `+0xc4 + i`. The two lower-is-better records are skipped when the win reason `0x09e02cb4` is `0xc` or `0xd`. This answers the open question below about the function; the extra result values 1–3 remain.
- `duel_core_is_multi_pick_list_mode` (`0x09be1dc4`): card-list mode `0x09e29918` in 7..`0x48`.
- `duel_core_set_output_binding` / `duel_core_flush_output_binding` (`0x09be4bd8` / `0x09be4bf4`): a (mode, value, pointer) triple at `0x09e01eb4`–`0x09e01ebc`; nothing writes the value, and the only call (from `rel_duel_mgr` at duel set-up) passes mode 0: vestigial (meaning low).
- `duel_core_stub_return_0_09be5000`: unreferenced `return 0`.
- `duel_core_view_is_zone_usable_lenient` (`rel_duel_draw` `0x0989ddb8`): view-side wrapper of `duel_core_is_zone_usable_lenient` for the zone highlights.
- `duel_effects_is_spirit_reaper_target_marker` (`0x09cdfbac`): the `duel_core_find_slot_marker` predicate of `duel_core_destroy_targeted_spirit_reapers` (equip-link kinds 10/11, source-link kinds 6/7 with byte `+2` bit 4, or the kind-2 key `0x1598`).

### Open questions from the 2026-11-03 round
- Slot flag bits 22, 23 and 27: "has attacked", "no attack left" and a per-phase flag are inferred from their readers (M); find the writers.
- Event-word bits 25–30: the Type-specific bits are set for Types `0x14`, `0x15` and 9, but their readers were not identified.
- The Type `0x15` test on the opponent's battle record in send-batch state 2 and in `send_battle_destroyed_cards`: the banish-by-battle cards it gates (`0x1ade`, `0x18e6`, `0x15d9`, `0x14b7`, `0x147a`, `0x16f8`) do not obviously share that Type. Check the meaning of record `+0x2c` in this path.
- The counter `0x09e2d238` (limit 10) in `set_slot_negated` and `apply_forced_positions`, and `0x09e2d23c`, `0x09e2d240`: loop guards or a real rule?
- The direction of each forced position in `apply_forced_positions` (which cards force Attack and which force Defense) is read from the compare logic (M); confirm in PPSSPP.
- `timing_event_allows_card_response` returns at once on event codes 1 and 5 (duelist kind 1, the CPU), so it does not look at later events in the queue. Is that intended?
- The last two arguments that `duel_core_filter_valid_attack_target` passes to `is_valid_attack_target`, and the pass-through arguments of `duel_core_view_can_activate_slot_card` and `duel_core_call_face_change_hook`, are hidden by the decompiler; read the disassembly.
- ~~The extra duel result values 1–3 used by `record_duel_result` (`0x09e02cb0`)~~: 1 won, 2 lost, 3 draw (`duel-runtime.md`; the win, loss and draw branches in "Duel challenges"). (The function `0x09be26f4` it calls is `duel_core_update_duel_records`, above.)

## Duel challenges (`duel_core_check_duel_condition`)

Settled statically on 2026-11-04 (port blocker B2; capstone on `rel_duel_eng`, `rel_duel_mgr`, `rel_duelrecord`, Ghidra C of `rel_duel_eng` and `rel_duel_mgr`). The condition index is the **active challenge** of the Duel Record screen. It is not a story feature and not a duel bonus.

### The feature

- **Choosing a challenge.** The Duel Record screen (`rel_duelrecord`, scene "duel record", text table `database/duelrecord.ehp` `strTbl_<l>.bin`) has three lists: records (49 entries, tab 0), bonuses (83 entries, tab 1) and challenges (104 entries, tab 2). The challenge list is built at `rel_duelrecord +0x2eb0`: for `i` = 0..`0x67` it stores the challenge index `i` at entry `+0`, the state byte record table `+0x14c + i` at entry `+4` bits 0–1, and the best value record table `+0x1b8 + 2i` at entry `+0xe` (16-byte entries, pointer at module `+0x9590`, count `u16` at `+0x9586`). On tab 2 the confirm button (`thunk_system_get_confirm_button`, prompt text "Set Challenge") calls `rel_duelrecord +0x3f70`, which stores the highlighted entry's `+0` into **record table `+0x290`** (`sh $v1, 0x290($a3)` at `+0x3fcc`) and plays sound `0x7a05`. A capstone scan of every module and of `BOOT.BIN` for `lh`/`lhu`/`sh` with offset `0x290` finds this as the only writer that changes the value (`rel_duel_mgr +0x8a10` stores back the value it has just read). Nothing initialises it, so a new save (record table cleared) starts with challenge 0 active (M: the zero fill of the record table by the new-game routine is assumed, not traced). Confidence H for the writer and the list layout.
- **Text.** Each list has a parallel `u16` table (challenges: `rel_duelrecord +0x9270`, the same 116 values at `rel_duel_mgr +0x1e844`): bit 0 = shown, bits 1–15 = row of the duel-record string table. All 104 challenge entries have bit 0 set. The rows give the name the game shows for each index; the table below paraphrases them (the port takes the text from the extracted table, row = value >> 1).
- **Evaluation.** `duel_core_record_duel_result` (`0x09be4648`) calls `duel_core_check_duel_condition` only for a **won** duel (extra result 1), offline (`system_get_net_active_flag` 0), with default rules (set-up bytes `+0x196` and `+0x197` both 0), with set-up `+0x190` = 1 and exactly one human duelist (`0x09e01e48` = its entry). Challenges `0x18` and `0x19` are also handled in the **draw** branch (extra result 3) under the same conditions: `0x18` when the match was won (`set-up +0x191 == 2` and `duel_core_get_match_result() == 1`), `0x19` always; both then call `duel_core_update_record_best(index)` and `duel_core_set_record_flag_once(2)`. The switch reads the index as `s16` from record table `+0x290` and copies it to the set-up tail block `+0x390`; the jump table covers 0..`0x75` (`sltiu $at, $s4, 0x76` at `0x09be3c1c`), other values do nothing.
- **Record.** When the condition holds, `duel_core_update_record_best(index)` (`0x09be2644`) compares `v` = `0x09e01e44`, the **opponent's recipe level** (`deck_get_recipe_level` of the opponent's recipe; the mean of both opponents in a tag duel, set by `record_duel_result` before the call). It records when (`v` ≠ 0 and state byte record table `+0x14c + index` is 0) or `v` > the best value `s16` record table `+0x1b8 + 2·index`: state byte 0 → 1 (and tail `+0x3c +0x210 + index` = 1, "first time"), otherwise tail byte = 2 ("again"); tail `+0x3c +0x27c + 2·index` = `v`; returns 1. Otherwise returns 0 and records nothing. Confidence H (disassembly `0x09be2644`–`0x09be26f0`).
- **Reward.** `ui_duel_result_init` (`rel_duel_mgr`, `0x08ea2f2c`) for a local default-rules duel reads the active index from tail `+0x390`. If the challenge's text-table bit 0 is set and the tail state is 1 or 2 and the new value differs from the stored best, it shows the "New Challenge Bonus" line (result-screen block `+0x24` = 1) and adds **200 DP** to the DP sum (block `+0x10`). It then writes the best value: record table `+0x1b8 + 2·index` = the new value when the challenge was met, the old value otherwise. The duel-bonus table adds bonus 2 ("Challenge Bonus", `duel_core_compute_duel_bonuses` case 8): 2 points per challenge whose state byte `+0x14c + i` (i < `0x68`) is non-zero. The shop's pack rules read the same state bytes (`shop-rules.md`). Confidence H for the code path, M for the reading "+0x10 is DP" (the four result words `+0x08`–`+0x14` are summed and passed to `save_add_dp`).
- **"Card used in this duel".** `duel_core_was_card_used_in_duel(id)` (`0x09dcbbcc`) tests the instance bitmap at `0x09e02f24` (512 bits, one per card instance). It is cleared by `duel_core_reset` (`0x09dc7cb0`, which zeroes `0x09e02f20`–`0x09e02ff7` together with the duel statistics) and set by `duel_core_mark_card_used_in_duel` (`0x09dcbc54`), called from three places: `duel_core_cmd_summon_finalize` (`0x09dbe274`: the instance of the summoned card), `duel_core_chain_step` (`0x09c30d04`: the card of a resolving chain link when the link's controller is the local side `0x09e02994 & 1` and the test `0x09de4a24(card id)` is 0) and `duel_core_net_process_packet` (`0x09dcd1e4`, link play). The thunks in `rel_duel_draw` (`0x098bb46c`) and `rel_duel_mgr` (`0x08eb18e4`) have no caller. So "used" means summoned (either side; the instance is tested by card id) or resolved in a chain by the local player. Confidence H for the writers, M for the summary.

### Statistic indices used by the challenges

`duel_core_get_statistic(i)` (`0x09dcb734`): `i` < 10 → `u32` at `0x09e02f64 + 4i`; `i` < `0x3e` → `u16` at `0x09e02f76 + 2i`; otherwise bit `i − 0x3f` of `0x09e02ff4`. The meanings come from two independent pairings that agree: the record each statistic feeds in `duel_core_update_duel_records` (record names from the duel-record text table) and the challenge text of the index that tests it. Confidence M per index (no writer traced one by one); the writers are `duel_core_set_statistic`, `_set_statistic_max` and `_add_statistic`.

| Stat | Meaning | Record (`update_duel_records`) |
| --- | --- | --- |
| 0 | effect damage dealt (total) | part of record 5 "total damage" (0 + 1 + 2) |
| 1 | battle damage dealt | 6 |
| 2 | deflected (reflected) battle damage | 7 |
| 3 | direct damage | 8 |
| 4 | damage dealt in one turn (maximum) | — |
| 6 | direct damage with Toon monsters | `0x1c` |
| 7 | Life Points restored | — |
| `0xc`, `0xd`, `0xe` | largest single damage (three sources; the record takes the maximum) | 9 |
| `0x12` / `0x13` | opponent's monsters destroyed by effects / in battle | `0xc` / `0xb` |
| `0x17`, `0x18`, `0x1b`, `0x1c`, `0x28`, `0x29` | Normal, Flip, Tribute, Special, Fusion, Ritual Summons | `0xf`–`0x14` |
| `0x1a` | Tokens Special Summoned | `0x15` |
| `0x21` | Spell Cards used | `0x18` |
| `0x23` | Quick-Play Spells used in the opponent's turn | — |
| `0x25` | Trap Cards activated | `0x19` |
| `0x26` | opponent's moves countered | `0x1a` |
| `0x2b` | chains (the challenge reads it as chain links; L for which) | `0x1f` |
| `0x2d` | opponent's monsters banished by effects | `0xd` |
| `0x2e` | cards discarded from the opponent's hand | `0x21` |
| `0x33` | opponent's monsters taken over | `0x1b` |
| `0x35` | Spell Counters used | 4 |
| `0x36` | Union monsters equipped | `0x17` |
| `0x3a` | coin tosses won in a row | `0x1e` |
| `0x3f` | bit 0 of `0x09e02ff4`: the player took damage | — |

### Deck statistics

Deck challenges test the 0x68-byte block at `0x09e01e4c` that `duel_core_build_deck_stats` fills from the human duelist's deck (set-up entry `+0x230 + 0x1ac · 0x09e01e48`, Main and Extra Deck) before the call (`functions/duel_core.md`, `duel_core_tally_deck_card_stats`). `u16` indices: `[0]` monsters; `[1 + kind]` per `card_db_get_kind` (kinds 2/3 Fusion, 13 Spell, 14 Trap); `[0x10 + race]`; `[0x26 + attribute]`; `[0x2e]` bit `level` set for each monster level present; `[0x2f]` flags (bit 0 a non-"LV" monster, 1 a non-Elemental Hero, 2 a non-Spirit, 3 a non-Toon, 4 a card whose current limit is not 3, 5 a duplicated id, 6 an Effect Monster); `[0x30]`/`[0x31]` maximum/minimum ATK (minimum preset to `0xffff`).

### Condition table

"≥ n" means the statistic reached n in the won duel. Result word = `0x09e02cb4` (`duel-runtime.md`; the end-of-duel reason). Every row: code H (`0x09be3bc0`, jump table and case bodies read); the paraphrased name M–H (text row matches the condition in every row checked; differences are listed).

| Index | Condition (evaluated at the end of a won duel) | Text agrees? |
| --- | --- | --- |
| `0x00` | stat 1 ≥ 10,000 (battle damage) | yes |
| `0x01` | stat 2 ≥ 4,000 (deflected battle damage) | yes |
| `0x02` | stat 3 ≥ 20,000 (direct damage) | yes |
| `0x03` | stat 0 + 1 + 2 ≥ 50,000 (total damage) | yes |
| `0x04` | stat `0x13` ≥ 20 (destroyed in battle) | yes |
| `0x05` | stat `0x12` ≥ 20 (destroyed by effects) | **text says 30**; the code tests 20 |
| `0x06` | stat `0x2d` ≥ 10 (banished by effects) | yes |
| `0x07` | stat `0x17` ≥ 10 (Normal Summons) | yes |
| `0x08` | stat `0x18` ≥ 10 (Flip Summons) | yes |
| `0x09` | stat `0x28` ≥ 10 (Fusion Summons) | yes |
| `0x0a` | stat `0x29` ≥ 10 (Ritual Summons) | yes |
| `0x0b` | stat `0x1c` ≥ 20 (Special Summons) | yes |
| `0x0c` | stat `0x1a` ≥ 15 (Tokens) | yes |
| `0x0d` | stat `0x36` ≥ 5 (Union equips) | yes |
| `0x0e` | stat 6 ≥ 8,000 (Toon direct damage) | yes |
| `0x0f` | stat `0x21` ≥ 20 (Spells used) | yes |
| `0x10` | stat `0x23` ≥ 10 (Quick-Play in the opponent's turn) | yes |
| `0x11` | stat `0x25` ≥ 10 (Traps activated) | yes |
| `0x12` | stat `0x26` ≥ 10 (counters) | yes |
| `0x13` | stat `0x33` ≥ 10 (take-overs) | yes |
| `0x14` | stat `0x2b` ≥ 5 ("a chain of 5 links") | yes (stat meaning L) |
| `0x15` | stat `0x35` ≥ 10 (Spell Counters used) | yes |
| `0x16` | stat `0x2e` ≥ 20 (opponent's discards) | yes |
| `0x17` | stat 7 ≥ 20,000 (LP restored) | yes |
| `0x18` | match duel (set-up `+0x191` = 2) and `duel_core_get_match_result()` = 1 ("won the match"); also checked after a draw | yes |
| `0x19` | no case here; set in the draw branch of `record_duel_result` ("ended in a draw") | yes |
| `0x1a` | result word ≠ `0xc` and stat `0x3f` = 0 (won without taking damage) | yes |
| `0x1b` | stat 4 ≥ 8,000 (damage in one turn) | yes |
| `0x1c` | stat `0xc`, `0xd` or `0xe` ≥ 8,000 (one attack or effect) | yes |
| `0x1d` | result word = 2 (opponent decked out) | yes |
| `0x1e` / `0x1f` / `0x20` | turn counter `0x09e2d1e0` + 1 < 8 / 6 / 4 (won within 7 / 5 / 3 turns) | yes |
| `0x21` | result word ≠ `0xc` and the turn player `0x09e2d1d8` ≠ the local side `0x09e02994 & 1` (won in the opponent's turn) | yes |
| `0x22` | result word = 3 (Exodia, `0xfbb`) | yes |
| `0x23` | result word = 4 (Destiny Board, `0x1468`) | yes |
| `0x24` | result word = 7 (Final Countdown, `0x169c`) | yes |
| `0x25` | match duel and result word = 8 (a match-winning effect) | yes |
| `0x26` | result word = 5 (Yata-Garasu lock, `0x14ff`) | yes |
| `0x27` | cards `0x15b1`, `0x15b4`, `0x15f9`, `0x15fa` all used (XYZ series) | yes |
| `0x28` | `0x1954` used (VWXYZ-Dragon Catapult Cannon) | yes |
| `0x29` / `0x2a` / `0x2b` | `0x19a3` / `0x19a4` / `0x19a5` used (Uria / Hamon / Raviel) | yes |
| `0x2c` | `0x19a3`, `0x19a4` and `0x19a5` all used (Sacred Beasts) | yes |
| `0x2d` | `0x16cf` used (Ojama Delta Hurricane!!) | yes |
| `0x2e` | `0x15ef` used (Huge Revolution) | yes |
| `0x2f` | `0xfe9` used (Perfectly Ultimate Great Moth) | yes |
| `0x30` | `0x111c` used (Gate Guardian) | yes |
| `0x31` | `0x138a` used (Valkyrion the Magna Warrior) | yes |
| `0x32` | `0x146e` used (Dark Sage) | yes |
| `0x33` | `0x16a3` used (Dark Scorpion Combination) | yes |
| `0x34` | `0x143f` used (Dark Scorpion Retreat) | yes |
| `0x35` | `0x09e2d1f8` = `0xfbe` (finishing card is Skull Servant) | yes; answers `battle.md`'s question on `0x09e2d1f8` (the card that dealt the final damage, M) |
| `0x36` | deck flag bit 6 clear (no Effect Monsters) | yes |
| `0x37` | no monster of Level 1–4 (`([0x2e] & 0x1f) >> 1` = 0) | yes |
| `0x38` | no monster of Level 5–12 | yes |
| `0x39` | no monster of Level 2–12 | yes |
| `0x3a` | monsters of every Level 1–12 | yes |
| `0x3b` | minimum ATK ≥ 1,500 | text "none with ATK 1500 or less": the code admits exactly 1,500 |
| `0x3c` | maximum ATK ≤ 1,500 | text "none with ATK 1500 or more": the code admits exactly 1,500 |
| `0x3d` | maximum ATK ≤ 1 | text "none with ATK 1 or more": the code admits 1 |
| `0x3e`–`0x43` | every monster has Attribute `index − 0x3d` (`[0]` = `[0x26 + a]`): LIGHT, DARK, WATER, FIRE, EARTH, WIND | yes |
| `0x44`–`0x57` | every monster has Type `index − 0x43` (`[0]` = `[0x10 + r]`): Dragon, Zombie, Fiend, Pyro, Sea Serpent, Rock, Machine, Fish, Dinosaur, Insect, Beast, Beast-Warrior, Plant, Aqua, Warrior, Winged Beast, Fairy, Spellcaster, Thunder, Reptile | yes |
| `0x58` / `0x59` / `0x5a` / `0x5b` | deck flag bit 0 / 1 / 2 / 3 clear: only "LV" monsters / only Elemental Heroes / only Spirits / only Toons | yes |
| `0x5c` | monsters = Fusion monsters (`[0]` = `[3] + [4]`): no Main Deck monster | yes ("not including Extra Deck"); a Synchro monster (kinds 17/18) would fail it |
| `0x5d` | no monsters at all | yes |
| `0x5e` / `0x5f` / `0x60` | no Trap / no Spell / neither (`[0xf]`, `[0xe]`) | yes |
| `0x61` | Main Deck count (set-up entry `+0x230`) = 60 | yes |
| `0x62` | deck flag bit 4 clear (every card at limit 3: no Forbidden/Limited/Semi-Limited) | yes |
| `0x63` | deck flag bit 5 clear (no duplicate id) | yes |
| `0x64` / `0x65` / `0x66` | stat `0x1b` / `0x1c` / `0x17` = 0 (no Tribute / Special / Normal Summon) | yes |
| `0x67` | stat `0x3a` ≥ 10 (coin tosses won in a row) | yes |
| `0x68`–`0x6a` | no case | — |
| `0x6b`–`0x74` | save-progress tests (every duelable character's record word 0 non-zero; all sandwiches; Golden Egg Sandwich; every variant of category-2 / of every duelable character flagged; collection ≥ 30 / 50 / 100 %; 48 packs bought; 70 gallery flags after progress flag `e9` bit 4) | **unreachable**, see below |

**Unreachable cases `0x68`–`0x75`.** The selector is written only from the 104-entry challenge list, and the save arrays it indexes (`+0x14c`, `+0x1b8`) hold 108 entries, so indices ≥ `0x68` never become active. The text tables carry 12 more entries after the 104 (`0x68`–`0x73`: Special Summons by banishing from the Graveyard, database complete, sandwiches, Golden Egg, story cleared for the main / all characters, collection 30 / 50 / 100 %, all packs, all movies, and "picked up all cards" with bit 0 clear), in an order shifted by two from the code cases `0x6c`–`0x74`. They are a cut "accomplishment" set; the port can drop them or implement them as achievements. Confidence M (static: one writer, list bound `0x68` in `rel_duelrecord +0x2fe8` and `+0x3ac8`).

## The tutorial module (round 6, 2026-11-04)

`rel_tutorial` is now in the Ghidra project (module offsets, ids `rel_tutorial:0x…`) and every function is documented (`modules/rel_tutorial.md`, which adds to `docs/formats/tutorial.md`: the copied message window, ten window slots of which the scripts use three, the stencil "spotlight", the text escapes `@`, `$0`-`$4`, `$$`, and the START quit menu that makes `duel_core_tutorial_is_busy` return 1).

## Open questions

- The rest of the player structure (`+0x34`–`+0x11f` besides the field slots, `+0xa0c`–`+0xb3b`). Life Points at `+0x00` are established statically (`battle.md`); confirm in PPSSPP.
- ~~Argument packing of the field-movement commands and the states of the send batch processor~~: packing in "Locations and card movement"; the batch (`duel_core_send_batch_step`, request block `0x09e2d298`–`0x09e2d2bc`, flag bits) in `effect-helpers-movement.md`. Still open: the remaining flag bits of `0x30`/`0x3f` `c`, and confirmation of the Deck top/bottom convention in PPSSPP.
- Summoning and the action menu: see the open questions in `summon.md`.
- ~~The states of `duel_core_chain_step`~~: answered in `chain.md`. (Phase values and the turn state machine: `duel-phases.md`.)
- The remaining event codes in chain links (`0x23` and `0x24` are partly understood, `chain.md`).
