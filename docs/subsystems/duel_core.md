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
| slot `+0x06` | Battle position (`u16`): 0 = Attack Position, non-zero = Defense Position (confidence high) | Target-filter bits `0x80` / `0x100`: the cards with `0x80` say "Attack Position" (12 of 13), those with `0x100` "Defense Position" (12 of 15); see `effect-tables.md`. |
| slot `+0x08` | Face-up (`u16`, non-zero = face-up; confidence high). Occupancy is the card id at `+0x00` | Target-filter bits `0x4` / `0x8`: "face-up" in 82 % of the `0x4` cards, "face-down" in 73 % of the `0x8` cards. |
| slot `+0x10` | Flags word: bit 3 disables the card's effect handlers (`duel_effects_call_handler_08`); bit 11: a face-up card counts as a spell rather than a trap (hypothesis, medium); bit 12: a monster-zone card counts as a spell/trap, e.g. a trap monster (`0x09bee9d0`; hypothesis, medium); bit 4 and bits 1/3 are tested by the "return" filter bit `0x80000` for spell/trap zones; bit 2 is tested by `0x09bfbb38` | `duel_effects_target_filter` zone classes `0x20`–`0x40`. |

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

## The chain

Activated effects are pushed on a chain stack of 24-byte links; the link on top is the `ctx` that effect handlers receive (`duel_effects.md`).

| Address | Meaning |
| --- | --- |
| `0x09e28cb4 + (n − 1) × 0x18` | Chain link `n` (1-based); the link below is at `− 0x18`. |
| `0x09e28e34` | Number of links. |
| `0x09e28e38` | Index walked downwards while resolving. |
| `0x09e28f5c` | State of the resolution state machine (`0x66`, `0x67` among its values). |

Link layout (also the effect context): `u16 +0` card id; `u16 +2`: bit 0 the controlling side, bits 1–5 the field slot index (only values below 11 are field slots), bits 6–11 the event code (`0x12` when an attack is declared, `0x24` selects the spell/trap table in `duel_effects_find_record`); byte `+3` bits 4–5 the handler-table selector; further fields not mapped. Confidence: medium-high (the resolver decodes `+2` into side and slot and indexes the player block with them).

`duel_core_chain_step` (`0x09c2f1fc`, 14,148 bytes; callers `0x09c32dac`, `0x09c32e54`) advances that state machine: in state `0x67` it runs `duel_effects_check_rule_list`; in state `0x66` it walks the links from the top down, checks that each link's slot still holds the card, and calls the per-slot handling (`0x09c26e38`); later states handle card `0x190a`, which reacts to chains, among others.

## Open questions

- The rest of the player structure (graveyard, banished cards; confirm Life Points at `+0x00`) and the per-slot card state.
- What phase values mean (7 at the start of a turn), and the states of `duel_core_chain_step`.
- The remaining event codes in chain links.
