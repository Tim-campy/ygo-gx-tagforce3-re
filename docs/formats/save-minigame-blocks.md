# Mini-game save blocks and high scores (registry key `save_minigame_blocks`)

The part of the game state (`save.md`, "Game-state accessors") that belongs to the mini-games: seven small blocks at state `+0x1be0c`–`+0x1bf0b` (256 bytes) and the nine high scores with their "new record" bytes inside the record table. Offsets are relative to the game state returned by `save_get_state()` (`0x08835dc4`); in `DATA0` the same offsets apply (the state is copied whole, `save.md`). All values are little-endian `u32` unless stated.

Status: `documented` (2026-11-04). Basis: the BOOT.BIN getters (capstone: each calls `save_get_state` and adds a constant), `save_reset_options` (`0x0885442c`, the only writer of defaults), a capstone pass over the 36 game modules that follows every call to a block getter through its import stub (scratch tracer: the returned pointer is tracked through moves, constant additions and stores to module globals; branches ignored), and the mini-game result routine of `rel_title` (`ui_mini_result_apply_score`, `0x08ed6230`, read in Ghidra; every mini-game module carries a copy, `save.md`).

## Blocks (`+0x1be0c`–`+0x1bf0b`)

| Offset | Size | Getter (BOOT.BIN) | Users | Layout | Conf. |
| --- | --- | --- | --- | --- | --- |
| `+0x1be0c` | 4 | `save_get_minigame_block_0` (`0x0885beac`) | `rel_blackjack` (`+0x2a10`) stores the pointer in its global `+0x1584c`; no read of that global anywhere in the module | 1 word, never read or written | H (access), — (meaning) |
| `+0x1be10` | 4 | `save_get_minigame_block_1` (`0x0885bf2c`) | `rel_dodge` (`+0x304c`) stores the pointer in `+0x156ec`; never read | 1 word, unused | H, — |
| `+0x1be14` | 4 | `save_get_minigame_block_2` (`0x0885bfac`) | none (no module calls the getter) | unused | H |
| `+0x1be18` | `0x30` | `save_get_minigame_block_3` (`0x0885c084`) | `rel_underground`: loaded at start (`+0x1554`), written back at two exits (`+0x196c`, `+0x1b90`); `save_reset_options` | 12 words, below | H (layout), M (meaning) |
| `+0x1be48` | 4 | `save_get_minigame_block_6` (`0x0885c15c`) | none | unused | H |
| `+0x1be4c` | 4 | `save_get_minigame_block_7` (`0x0885c1dc`) | none | unused | H |
| `+0x1be50` | `0xbc` | `save_get_minigame_block_8` (`0x0885c25c`) | `rel_throw` (`+0x401c`) stores the pointer in `+0x18bbc`; never read | unused; size by adjacency up to `+0x1bf0c` | H (access), L (size) |

There are no getters for blocks 4 and 5 (the numbering of the BOOT.BIN getters skips them). Only block 3 holds live data: the pointers kept by `rel_blackjack`, `rel_dodge` and `rel_throw` are written once and never dereferenced (a full-text scan with capstone `skipdata`, so VFPU words do not stop the scan), so in the shipped game those blocks stay as `save_init_new_game` leaves them (0 in the analysed save).

### Block 3: `rel_underground` settings (12 `u32`)

`rel_underground` copies the block into its work state at start-up (work base `s0` = module `+0x18b90`) and back at the two exits; the start-up code clamps the values.

| Offset | Work field | Default (`save_reset_options`) | Start-up rule | Meaning (hypothesis) |
| --- | --- | --- | --- | --- |
| `+0x00` | `+0x18` | 1 | values outside 1–100 become 1; then lowered to `+0x04` when larger | current level/floor (M) |
| `+0x04` | `+0x1c` | 1 | outside 1–100 becomes 1 | highest level reached (M) |
| `+0x08`–`+0x24` | `+0x20`–`+0x3c` | 0 | each of the 8 values outside 0–4 becomes 0 | eight per-slot settings in 0–4 (L) |
| `+0x28` | `+0x08` | 0 | not clamped | unknown |
| `+0x2c` | `+0x0c` | 2 | outside 0–4 becomes 2 | a 0–4 setting, default 2 (speed or difficulty; L) |

## High scores (record table `+0xa0`–`+0xc3`)

The record table (`save.md`, at state `+0x113a4`) holds 49 values; values 40–48 (`+0xa0`–`+0xc0`, state `+0x11444`–`+0x11464`) are the mini-game high scores, read and written by `save_get/set_minigame_record_k` (k = 0–8, BOOT.BIN `0x0885bf04` … `0x0885c2b4`). Their "new record" bytes are record-table `+0xec + k` (= the generic new-record bytes `+0xc4 + 40 + k`). `duel_core_update_duel_records` (`duel_core.md`) only clears the per-duel copies of these nine values; it never writes them.

The result routine (`ui_mini_result_apply_score(game, score)`) maps its game index to records and DP as follows (higher score is better in every case; a new record adds 200 DP and sets the byte):

| Game index | Record(s) | Base DP |
| --- | --- | --- |
| 0 | 0 (`score[0]`) | `score[0] / 50` |
| 1 | 1 (`score[0]`) | `score[0] / 150` |
| 2 | 2 (`score[0]`); 3 (`score[1]`) when `score[2]` is set | `score[0] / 2`, plus `ceil(score[1] / 100)` when `score[2]` is set |
| 3 | 6 (`score[0]`) | `score[0] / 10` |
| 4 | 5 (`score[1]`); 4 (`score[2]`) when `score[0]` is set | `score[1] × 20 + score[2] × 150` |
| 5 | 7 (`score[0]`) | `score[0] / 50` |
| 6 | 8 (`score[0]`) | `score[0] / 10` |

Total DP = base + bonuses; experience = total / 25 (`save_add_duelist_exp`), 400 more DP on a level-up. The game index is not a constant in the modules: each module's copy of the routine receives it from a work-state field (`rel_blackjack +0x2c14`, `rel_connection +0xb680`, … traced three calls up), so which mini-game owns which index is still open (below).

## For the port

- Round-trip: `tools/save.py` already models each block as its own region of `u32` words (`minigame_block_0` … `_8`, keyed by the offsets above) and the high scores inside `record_values`; nothing else is needed.
- New game: block 3 = {1, 1, 0 × 9, 2}, everything else 0.

## Open questions

- Which mini-game passes which game index to the result routine (so which of the nine records belongs to blackjack, connection, dodge, quiz, reversi, throw and underground). Needs PPSSPP (differential save 6 in `save.md`) or a deeper trace of each module's work state.
- The meaning of the `rel_underground` block fields (play the mode in PPSSPP and watch `+0x1be18`).
