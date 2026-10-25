# Duel core (work package 4)

Rules machinery in `gmodule/rel_duel_eng.prx` (runtime base `0x09be1400`). Card effects are covered in `duel_effects.md`.

## Player state

Two per-player blocks of `0xb3c` bytes; player `p` (0 or 1) starts at about `0x09e2a528 + p × 0xb3c`. Fields established so far (confidence medium; from the code that reads them):

| Address (player 0) | Meaning | Basis |
| --- | --- | --- |
| `0x09e2a528` (`+0x00`) | Life Points (hypothesis, medium) | `duel_core_next_turn` compares this word of the two sides. |
| `0x09e2a534` (`+0x0c`) | Hand size | Draw-count rules such as "5 minus" and "7 minus" this value (`duel_effects_get_draw_count`); count of the list at `+0x124`. |
| `0x09e2a538` (`+0x10`) | Cards left in the deck | `duel_core_can_draw` compares the requested count with it; count of the list at `+0x304`. |
| `0x09e2a540` (`+0x18`) | Size of a third card list, presumably the extra deck | Count of the list at `+0x4e4`; swapped with the hand and deck in tag duels. |
| `+0x124`, `+0x304`, `+0x4e4` | Hand, deck and third list: 4 bytes per card (`u16` card reference with flags in the top bits, more bits in the following `u16`) | `tag_duel_swap_active_duelist`. |
| `0x09e2a55c + i × 0x14` | Field slot `i`, 20 bytes each: slots 0–4 are the monster zones, 5–9 the spell/trap zones, 10 the field-spell zone | `duel_effects_target_filter` limits zone classes by these index ranges. |
| slot `+0x00` | Card id (`u16`, low 14 bits) | Read with `& 0x3fff`. |
| slot `+0x06` | Unknown `u16`; tested by target-filter bits `0x80`/`0x100` (possibly the battle position) | Mirror Force's filter sets `0x80`. |
| slot `+0x08` | Non-zero when the slot is occupied | Target-filter bits `0x4`/`0x8`. |
| slot `+0x10` | Flags word: bit 3 disables the card's effect handlers (`duel_effects_call_handler_08`); bit 11 is tested together with occupancy (possibly face-down) | |

`0x09e28620` holds the attacking player (Mirror Force's activation condition compares it with the opponent).

## Duel globals

| Address | Meaning | Basis |
| --- | --- | --- |
| `0x09e2d1d8` | Side whose turn it is (0/1); 510 reads | `duel_core_next_turn` toggles it. |
| `0x09e2d1e0` | Turn counter | Incremented by `duel_core_next_turn`; set to 9 or 0 by the start functions. |
| `0x09e2d1e8` | Phase or step; set to 7 at reset and at each turn change | Written by the reset, the turn change and phase code; 203 reads. |
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

## Open questions

- The rest of the player structure (graveyard, banished cards; confirm Life Points at `+0x00`) and the per-slot card state.
- What phase values mean (7 at the start of a turn).
- Phases and the chain: where the turn loop and chain resolution live, and which code calls `duel_effects_resolve`.
- The meaning of the 6-bit event code in the effect context.
