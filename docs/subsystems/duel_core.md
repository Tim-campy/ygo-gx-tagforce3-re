# Duel core (work package 4)

Rules machinery in `gmodule/rel_duel_eng.prx` (runtime base `0x09be1400`). Card effects are covered in `duel_effects.md`.

## Player state

Two per-player blocks of `0xb3c` bytes; player `p` (0 or 1) starts at about `0x09e2a528 + p × 0xb3c`. Fields established so far (confidence medium; from the code that reads them):

| Address (player 0) | Meaning | Basis |
| --- | --- | --- |
| `0x09e2a534` | Hand size | Draw-count rules such as "5 minus" and "7 minus" this value (`duel_effects_get_draw_count`). |
| `0x09e2a538` | Cards left in the deck | `duel_core_can_draw` compares the requested count with it. |
| `0x09e2a56c + i × 0x14` | Per-slot card state, 20 bytes each | Bit 3 of the first word disables effect handlers (`duel_effects_call_handler_08`). |

`0x09e28620` holds the attacking player (Mirror Force's activation condition compares it with the opponent).

## Key functions

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x09c29bc8` | `duel_core_draw_cards(player, count)` | H | Forwards to `duel_core_draw_cards_ex(player, count, 1, 0)`; called by draw effects such as `duel_effects_resolve_draw`; 47 callers. |
| `0x09c28f44` | `duel_core_draw_cards_ex(player, count, a, b)` | M | Body not read. |
| `0x09c0d920` | `duel_core_can_draw(player, count) → bool` | H | Negative count selects the opponent; false while card `0x178b` or `0x1885` prevents drawing; otherwise compares with the deck size. |
| `0x09c2c134` | `duel_core_get_effective_card_id(ctx)` | M | 0 unless bit 0 of `ctx+6`; then the id at `ctx+0x18`, resolved through a table at `0x09e2bbcc` for card `0x1935`. |

## Open questions

- The full player structure (field zones, graveyard, banished cards, life points) and the per-slot card state.
- Phases and the chain: where the turn loop and chain resolution live, and which code calls `duel_effects_resolve`.
- The meaning of the 6-bit event code in the effect context.
