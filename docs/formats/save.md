# Save data (work package 3)

Status: `documented` for the deck slots and the card collection; the rest of the 128 KiB is not mapped yet. Tool: `tools/save.py` (decks, collection, `--check`). Analysed on a plaintext save written by PPSSPP early in the game (one save; the player owned only the starting deck).

## On the memory stick

`PSP/SAVEDATA/ULES011830001/` holds `DATA0` (the game state), `PARAM.SFO`, `ICON0.PNG` and `PIC1.PNG`, written through the system's `sceUtilitySavedata` dialog. A retail-style save is encrypted by the PSP save-data layer: `DATA0` is then 131,088 bytes (the 131,072-byte buffer plus 16 bytes) with a byte entropy of 7.999 bits/byte. Decrypting it would circumvent platform protection (`CLAUDE.md`), so analysis uses saves that PPSSPP writes unencrypted (`EncryptSave = False` in `ppsspp.ini`): PPSSPP loads an encrypted save like the console and writes it back in plaintext.

## In the game

| Address | Meaning |
| --- | --- |
| `0x08acda04` | `SceUtilitySavedataParam` block (`0x9d0` bytes, zeroed). |
| `0x08acda08` | Save buffer, `0x20000` bytes: the whole content of `DATA0`. |
| `0x08acda0c` | Buffer for a disc file loaded with the save (root 6, name from `0x088413ec`; presumably an icon or picture). |
| `0x08acda10` | `0x200`-byte work block. |
| `0x08acda00` | Heap the four blocks come from. |

`save_open` (`0x088410dc`) allocates the four blocks; `save_close` (`0x0883e3b4`) frees them. Six functions fill the parameter block and call `sceUtilitySavedataInitStart` (`0x0883e694`, `0x0883e78c`, `0x0883e874`, `0x0883e918`, `0x0883e9e0`, `0x0883eaa4`). The two read so far set the mode at `+0x30` (8 and `0x16`), the data buffer at `+0x74` (`*0x08acda08`), buffer and data size at `+0x78`/`+0x7c` (`0x20000`), the file name `DATA0`, and copy a 16-byte value from `0x08879068` to `+0x5dc`, the field that holds the game's save-data key. This project records that the key exists and does not use it.

## `DATA0` layout

All integers little-endian. The buffer is a raw copy of in-memory structures: deck headers contain stale pointers into `BOOT.BIN` (for example `0x08859ac0`), unused bytes hold leftovers of other strings and `0xdeadbeef` fill.

| Offset | Size | Content | Confidence |
| --- | --- | --- | --- |
| `0x00000` | 4 | `0x00030000`, presumably a version. | low |
| `0x0000c` | 4 | `0xd79` in the analysed save; unknown. | — |
| `0x00010` | 16 | High-entropy value; not an MD5 or CRC32 of the file in any obvious range. Possibly a game-level checksum. | — |
| `0x04a30` | 147 × `0x16c` | Deck slots (below). | high |
| `0x11ba4` | 3,554 × 4 | Card collection, one record per card-database record index (below). | high |
| `0x16582` | | UTF-16 text starting `2008/03`; a date. | low |
| `0x16604` – `0x1c0d3` | | Not mapped: a table with a `0x2a`-byte stride at the start, then denser data. | — |

### Deck slot (`0x16c` bytes)

| Offset | Size | Field |
| --- | --- | --- |
| `0x00` | 4 | Stale pointer or 0. |
| `0x04` | 4 | Owner id (2, 3, 4, …): the character whose deck this is; 0 for the player's own slots. |
| `0x08` | 4 | 0. |
| `0x0c` | 4 | Recipe the deck was created from: the owner's first recipe in the recipe owner table (`deck.md`), for example 1 for owner 2 and 11 for owner 3. |
| `0x10` | 64 | Deck name, UTF-16, NUL-terminated (`Starting Deck`, `Partner's Deck`). |
| `0x50` | 12 | `u32` counts: main, side, extra. |
| `0x5c` | 120 | Main deck, up to 60 `u16` card ids. |
| `0xd4` | 30 | Side deck, up to 15 ids. |
| `0xf2` | 30 | Extra deck, up to 15 ids. |
| `0x110` | 92 | Unused in the analysed save (stale bytes). |

In the analysed save, slot 0 is the player's `Starting Deck` (40 main, 15 side) and 125 slots are `Partner's Deck` records, one per partner character (owners 2–126), each seeded from that character's first recipe; 21 slots are empty. Every listed id exists, no card appears more than three times, extra decks hold only fusion and synchro monsters, and main decks hold none.

### Card collection (4 bytes per card)

Indexed by the card-database record index (`CARD_IntID` maps ids to it).

| Byte | Meaning | Basis |
| --- | --- | --- |
| 0 | Flags; 4 on every owned card. | Only owned cards have it set. |
| 1 | Copies owned. | Equals, for all 54 cards, the number of copies in the starting deck (55 in total), which is the whole collection at this point. |
| 2, bits 0–1 | Forbidden/limited status of the card for this save (0 forbidden, 1 limited, 2 semi-limited, 3 unlimited). | All 114 entries of the built-in list (`limit-list.md`) match, and every other card is 3. This is the per-save copy that `deck_reset_limits` seeds. |
| 3 | 0 in the analysed save. | — |

## Open questions

- The region from `0x16604`: characters (friendship, unlocks), story progress, duel records, DP and settings. A second save that differs by one known action (for example buying one pack, with the DP before and after) will locate DP and confirm collection updates.
- The 16 bytes at `0x10`: which code computes them, and whether the game rejects a save whose value does not match.
- Which code copies the buffer to and from the game state; the meaning of collection byte 0 bits and of the other save modes (8, `0x16` and the four other callers).
