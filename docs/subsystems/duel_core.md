# Duel core (work package 4)

Rules machinery in `gmodule/rel_duel_eng.prx` (runtime base `0x09be1400`). Card effects are covered in `duel_effects.md`; summoning, setting, battle positions and the action menu in `summon.md`; the Battle Phase, Life Points and the end of the duel in `battle.md`.

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
| `0x09e2a54c` (`+0x24`) | Lost flag: the other side wins with reason 2 when it is set (hypothesis: deck-out; no direct writer found) | `duel_core_check_win`. |
| `0x09e2a554` (`+0x2c`) | Card id of a special-victory monster whose battle damage won the duel (reason 8) | `duel_core_cmd_lp_loss`. |
| `0x09e2a558` (`+0x30`) | Win reason of this side after the duel is decided | `duel_core_check_duel_end`, command 5. |
| `0x09e2a648` (`+0x120`) | Player flags word, laid out as a twelfth slot flag word (`+0x10 + 11 × 0x14`); the upper 16 bits are per-turn and cleared by command 2 together with the slots' upper halves. Bit 0 skip the draw; bit 16 a summon was declared; bit 17 Normal Summon used; bit 21 a monster was Normal Summoned face-up | `summon.md` (H for bits 0, 17 and the reset). |
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
| `0x09c18550` | `duel_core_send_hand_card(side, entry, flags, dest, discard, reason)` | Hand card to the graveyard (`0x0e`) or banished (`0x0f`); Macro Cosmos-type rules turn the graveyard into banishment (`0x09c0d5e8`, `0x09c0d160`); posts `0x3e`, `0x32` or `0x45`. Wrappers `0x09c18d70`, `0x09c18dc8`, `0x09c18e14`, `0x09c18f98`, `0x09c18fe4`. |
| `0x09c18384` | `duel_core_return_hand_card_to_deck(side, index, top)` | Command `0x3e` hand → deck. |
| `0x09c2b110` | `duel_core_send_list_card_to_graveyard(side, location, index, entry, a5, a6)` | Hand/deck/extra card to the graveyard or banished (command `0x30`); wrappers `duel_core_send_hand_entry_to_graveyard` (`0x09c2b394`), `duel_core_send_deck_card_to_graveyard` (`0x09c2b3b4`), `duel_core_send_extra_card_to_graveyard` (`0x09c2b420`). |
| `0x09c20ad0` | `duel_core_send_field_card(side, slot, dest, flags, by_card)` | Removes a field card to `dest` after immunity checks (`flags` bit 1 destroy, bit 2 rule/no check); posts `0x30`, `0x31`, `0x3c`, `0x4b`, `0x4d`. Called from the batch processor `0x09c232bc` (destroy/tribute batches started by e.g. `duel_core_tribute_monsters`). |
| `0x09c2be00`, `0x09c2be98` | `duel_core_post_set_player_flag(side, bit, value)`, `duel_core_post_set_slot_flag(side, slot, bit, value)` | Flag changes as commands `0x21` / `0x29`. H |

Commands that move field cards: `0x30` field/list → graveyard or banished (`0x09db7db8`), `0x31` (`0x09db8a50`), `0x32` graveyard → banished (`0x09db9f40`), `0x3c`/`0x3d` between field slots or sides (`0x09db5db4`, `0x09db6304`), `0x3f`, `0x40` (`0x09db4d34`, `0x09db561c`), `0x45` (`0x09db9878`), `0x56` draw (`0x09dbb7d8`). Their exact argument packing is not yet recorded.

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
| `0x09dbc184` | `duel_core_next_turn()` | H | Toggles `0x09e2d1d8`, increments `0x09e2d1e0`, sets the phase to 7, walks the 11 field slots of both sides for two special cards, compares the sides' `+0x00` words, and in tag mode swaps the next side's active duelist. |
| `0x09dc7cb0` | `duel_core_reset()` | H | Clears the duel state regions and sets the phase to 7. |
| `0x09bf1f74` | `duel_core_load_deck(side, deck)` | M | Called with a `0xc0`-byte deck structure; body not read. |

`0x09e2bbcc` is a table of 6-byte entries indexed by the `u16` card references stored in hand, deck and field lists; its low 14 bits are the card id.

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

## Open questions

- The rest of the player structure (`+0x34`–`+0x11f` besides the field slots, `+0xa0c`–`+0xb3b`). Life Points at `+0x00` are established statically (`battle.md`); confirm in PPSSPP.
- Argument packing of the field-movement commands `0x30`, `0x31`, `0x3c`, `0x3d`, `0x3f`, `0x40`, `0x45`, and the states of the send batch processor `0x09c232bc` (`0x09e2d298`).
- Summoning and the action menu: see the open questions in `summon.md`.
- ~~The states of `duel_core_chain_step`~~: answered in `chain.md`. (Phase values and the turn state machine: `duel-phases.md`.)
- The remaining event codes in chain links (`0x23` and `0x24` are partly understood, `chain.md`).
