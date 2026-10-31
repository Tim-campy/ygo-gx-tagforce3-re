# Tag duels (work package 5)

Tag duels are implemented on top of the ordinary two-sided duel in `gmodule/rel_duel_eng.prx` (runtime base `0x09be1400`). Confidence: high for the swap mechanism (read in the code), medium for the meaning of the mode values.

## How it works

- **Two sides, four duelists.** The duel keeps two player blocks (`0x09e2a528 + side × 0xb3c`, see `duel_core.md`): one field and one Life Point total per side. Per-duelist data lives in 4-entry arrays: the controller type per side at `0x09e02998` (0 human, 1 CPU, 2 remote, medium confidence; see `ai.md`; `0x09e02990` is the duel RNG seed, not a per-duelist value), and four in-memory deck structures of `0xc0` bytes at `0x09e029ac + n × 0xc0` (the layout documented in `docs/formats/deck.md`).
- **Tag mode** is the flag `0x09e2d1fc`. `tag_duel_start_with_partner_decks` (`0x09dc7ff4`) resets the duel, sets the flag and loads deck structures 2 and 3 into the two sides with `duel_core_load_deck` (`0x09bf1f74`), choosing by `0x09e029a8`.
**Verified in PPSSPP (2026-10-27, [`results/2026-10-27-sessionB.md`](../verification/results/2026-10-27-sessionB.md)):** the tag start entry `0x09dc7ff4` and flag `0x09e2d1fc = 1`; the exchange of hand, deck and Extra Deck with the waiting area at every turn change, LP and Graveyard staying with the side (the pair shares its LP), and the alternation of the active duelist kind.

- **Partner swap at every turn change.** `duel_core_next_turn` (`0x09dbc184`) toggles the side to move and, when the tag flag is set, calls `tag_duel_swap_active_duelist(next side)` (`0x09bf21e4`). That function saves the side's hand, deck and third card list (the Extra Deck, confirmed in PPSSPP) and loads the partner's from a waiting area of 300 bytes per side at `0x09e02cc8 + side × 300` (`0x09e02cb8 + side × 300 + 0x10`: counts as `u16` at `+0x00`, `+0x02`, `+0x04`, followed by up to 147 `u16` card references in list order: hand, deck, Extra Deck). The field, the graveyard and the Life Points stay with the side.

So the rule "partners share field and Life Points and alternate turns, each with their own hand and deck" is realised by swapping three card lists in place rather than by keeping four players.

## Key functions

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x09dc7ff4` | `tag_duel_start_with_partner_decks() → 1` | H | See below. Verified in PPSSPP (Session B, B2). |
| `0x09bf21e4` | `tag_duel_swap_active_duelist(side)` | H | See below. Verified in PPSSPP (Session B, B1). |

### `int tag_duel_start_with_partner_decks(void)` (`0x09dc7ff4`)

Starts a tag duel: reads the first side `0x09e029a8`, calls `duel_core_reset` (`0x09dc7cb0`), sets the tag flag `0x09e2d1fc = 1`, runs the common start set-up `0x09dc7dc4` (turn side from `0x09e029a8`, duel-start commands; `duel-phases.md`), then `duel_core_load_deck(first, 0x09e029ac + (first + 2) × 0xc0)` and `duel_core_load_deck(1 − first, 0x09e029ac + (3 − first) × 0xc0)`: deck structures 2 and 3 are the active duelists' decks (structures 0 and 1 presumably the waiting partners'; not traced). Returns 1. Only caller `0x09be154c` (not named). Side effects: the whole duel state is reset; the flag makes `duel_core_next_turn` swap partners.

### `void tag_duel_swap_active_duelist(int side)` (`0x09bf21e4`)

Only caller `duel_core_next_turn`, with the side whose turn starts. Steps (decompiled, H):

1. Saves the side's three lists into a 300-byte stack buffer: the counts of hand (`+0x0c`), deck (`+0x10`) and Extra Deck (`+0x18`) as `u16`, then each entry (hand `+0x124`, deck `+0x304`, Extra Deck `+0x4e4`, 4 bytes each) reduced to its 9-bit card reference (`(u16 +2 & 0x7fff) >> 7` × 2 + bit 6 of byte `+1`).
2. Loads the partner's lists from the waiting area `0x09e02cc8 + side × 300`: the three counts, then for each reference `r` an entry with the card id `0x09e2bbcc[r × 6] & 0x3fff` in bits 0–13, `r & 1` in bit 14 and `r >> 1` in bits 23–30 (the other bits are kept).
3. Toggles `u32 0x09e02cb8 + side × 4` (which of the pair is active), copies the saved buffer into the waiting area (`system_memcpy`, 300 bytes), and swaps the duelist kinds `0x09e02998[side]` and `0x09e029a0[side]`.

No return value. Field, Graveyard, banished cards and LP are not touched. The two toggle words (`0x09e02cb8`, `0x09e02cbc`) sit in the 16 bytes before side 0's waiting area; what else that header holds is not known.

**Verified in PPSSPP (2026-10-27, [`results/2026-10-27-sessionB.md`](../verification/results/2026-10-27-sessionB.md)):** entry and return logs at four turn changes showed the three counts exchanged with the waiting area, LP and Graveyard unchanged, and the duelist kinds swapped with the waiting kinds (B1); `0x09dc7ff4` was the only start entry for a story tag duel and left the flag at 1 (B2).

## Function families named in the 2026-10-31 round

Basis and method: `system.md`, same section. 8 new `tag_duel` names, all reading the per-side swap toggle `0x09e02cb8` described above:

| Address | Name | Reads |
| --- | --- | --- |
| `0x09bf25c8` | `tag_duel_get_duelist_kind` | `0x09e02998[d ^ (0x09e02cb8[d & 1] << 1)]`: the kind of duelist `d` after the swap. |
| `0x09bf2600`, `0x09bf2668` | `tag_duel_get_card_owner_duelist`, `tag_duel_is_card_owned_by_duelist` | Owner of a card instance: side, side + 2 (partner range from `0x09e02cc0`) or side + 4 (created after load); always true outside tag mode (`0x09e2d1fc`). |
| `0x09bf26f8` | `tag_duel_is_duelist_active` | `(d < 2) ^ 0x09e02cb8[d & 1]`. |
| `0x09bf271c`, `0x09bf273c` | `tag_duel_get_active_duelist`, `_alt` (byte-identical twin) | `side + 2 · 0x09e02cb8[side]`. |
| `0x09850838` (`rel_duel_draw`) | `tag_duel_get_side_partner_duelist` | Duelist ± 2. |
| `0x08e9ba00` (`rel_duel_mgr`) | `tag_duel_handle_partner_swap` | In a tag set-up (`+0x192 == 2`): sets the new active duelist's kind (0 human, 1 CPU, 2 remote) and calls the draw module with the slot pairs. |

## Round 2 of the 2026-10-31 naming

Method as in the first round (`system.md`): the still-unnamed functions were re-dumped from Ghidra with the current names, read in packs with full bodies (up to 160 lines), and named H/M with a basis in `re/names*.csv` under "round 2". 6 new `tag_duel` names in `rel_duel_draw`: the partner-switch UI mode (mode 10 of the duel UI mode table `0x098d1f5c`, `ui.md`).

## Documented functions

The functions of this group that reached the `documented` stage in the 2026-10-31 documentation round (prototype, purpose, return value, side effects and callers, read from the decompilation) are listed in [`functions/tag_duel.md`](functions/tag_duel.md).

## Open questions

- ~~The high half of the waiting-area word `+0x14` (`u16 +0x16`) changes at every swap (seen in PPSSPP: `0xaa`, `0x57`, `0x23`, `0x12`, `0x81`); meaning unknown.~~ It is the first saved card reference (the first hand card's instance), written by the `memcpy` of step 3 above.
- At the first swap of side 1 the waiting kind 0 was copied into the active kind word, yet the CPU played that turn and the word read 1 again later: find what rewrites the active kind.

- ~~Confirm that the third list is the extra deck, and read the end of `tag_duel_swap_active_duelist` (where the saved lists go).~~ The Extra Deck (PPSSPP, count 15 or 0); the saved lists go to the waiting area.
- Which entry points start a tag duel versus a single duel (`duel_core_start_mode2`/`_mode3`, `0x09e2d1f4` = 2 or 3).
- How the partner AI and the "tag" commands (asking the partner, partner's turn) are handled; whether cards that refer to "your partner" use the waiting area.
