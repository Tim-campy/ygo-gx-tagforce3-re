# Tag duels (work package 5)

Tag duels are implemented on top of the ordinary two-sided duel in `gmodule/rel_duel_eng.prx` (runtime base `0x09be1400`). Confidence: high for the swap mechanism (read in the code), medium for the meaning of the mode values.

## How it works

- **Two sides, four duelists.** The duel keeps two player blocks (`0x09e2a528 + side × 0xb3c`, see `duel_core.md`): one field and one Life Point total per side. Per-duelist data lives in 4-entry arrays: the controller type per side at `0x09e02998` (0 human, 1 CPU, 2 remote, medium confidence; see `ai.md`; `0x09e02990` is the duel RNG seed, not a per-duelist value), and four in-memory deck structures of `0xc0` bytes at `0x09e029ac + n × 0xc0` (the layout documented in `docs/formats/deck.md`).
- **Tag mode** is the flag `0x09e2d1fc`. `tag_duel_start_with_partner_decks` (`0x09dc7ff4`) resets the duel, sets the flag and loads deck structures 2 and 3 into the two sides with `duel_core_load_deck` (`0x09bf1f74`), choosing by `0x09e029a8`.
**Verified in PPSSPP (2026-10-27, [`results/2026-10-27-sessionB.md`](../verification/results/2026-10-27-sessionB.md)):** the tag start entry `0x09dc7ff4` and flag `0x09e2d1fc = 1`; the exchange of hand, deck and Extra Deck with the waiting area at every turn change, LP and Graveyard staying with the side (the pair shares its LP), and the alternation of the active duelist kind.

- **Partner swap at every turn change.** `duel_core_next_turn` (`0x09dbc184`) toggles the side to move and, when the tag flag is set, calls `tag_duel_swap_active_duelist(next side)` (`0x09bf21e4`). That function saves the side's hand, deck and third card list (presumably the extra deck) and loads the partner's from a waiting area of 300 bytes per side at `0x09e02cb8` (counts as `u16` at `+0x10`, `+0x12`, `+0x14`, followed by `u16` card references). The field, the graveyard and the Life Points stay with the side.

So the rule "partners share field and Life Points and alternate turns, each with their own hand and deck" is realised by swapping three card lists in place rather than by keeping four players.

## Key functions

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x09dc7ff4` | `tag_duel_start_with_partner_decks()` | M | Reset, `0x09e2d1fc = 1`, `0x09dc7dc4`, then `duel_core_load_deck(side, deck[side + 2])` and `duel_core_load_deck(1 − side, deck[3 − side])`. |
| `0x09bf21e4` | `tag_duel_swap_active_duelist(side)` | H | Copies the side's three card lists (counts at block `+0x0c`, `+0x10`, `+0x18`; entries at `+0x124`, `+0x304`, `+0x4e4`, 4 bytes each) out and loads the partner's from `0x09e02cc8 + side × 300`; only caller `duel_core_next_turn`. |

## Open questions

- The high half of the waiting-area word `+0x14` (`u16 +0x16`) changes at every swap (seen in PPSSPP: `0xaa`, `0x57`, `0x23`, `0x12`, `0x81`); meaning unknown.
- At the first swap of side 1 the waiting kind 0 was copied into the active kind word, yet the CPU played that turn and the word read 1 again later: find what rewrites the active kind.

- Confirm that the third list is the extra deck, and read the end of `tag_duel_swap_active_duelist` (where the saved lists go).
- Which entry points start a tag duel versus a single duel (`duel_core_start_mode2`/`_mode3`, `0x09e2d1f4` = 2 or 3).
- How the partner AI and the "tag" commands (asking the partner, partner's turn) are handled; whether cards that refer to "your partner" use the waiting area.
