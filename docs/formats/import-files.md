# Downloaded data files (`.YGC`, `.YGR`, `.YGL`)

Status: `documented` (layout read from the verifier, no real file seen: none is on the disc and no download was attempted). These are the files that the title menu entries "Go to the Yu-Gi-Oh! website" (scene `0x0e`, `rel_html_view`) and "Downloaded Data" (title state 6) work with. The browser saves them into the game's save directory, the game lists and imports them. How the feature fits together: `docs/platform-api.md`, section 6.

| Extension | Kind | Content | Record built by the loader |
| --- | --- | --- | --- |
| `.YGC` | 0 | One card | `0x44` bytes: file name widened to UTF-16 at `+0x00` (at most 32 units), u16 card id `+0x40`, flag byte `+0x42` bit 0 = failed |
| `.YGR` | 1 | One deck | `0x1c0` bytes: localised name `+0x00`, `0xc0`-byte deck `+0x100` |
| `.YGL` | 2 | One forbidden/limited list | `0x108` bytes: localised name `+0x00`, u16 pair count `+0x100`, pointer to the pairs `+0x104` |

**Location.** The directory is built by `save_build_save_dir_path` (`0x0883df88`): `"ms0:/PSP/SAVEDATA/"` + `"ULES01183"` + `"0001"`. `save_import_scan_dir` (`0x0884d964`) lists that directory and keeps up to 256 files whose name ends in the four characters of the requested kind (suffix strings `0x088a17d8`, `0x088a17d0`, `0x088a17c8`). Confidence high.

## Layout

Little-endian. `H` = the header length stored at `+0x08`, `S` = file size. Basis: `save_import_verify_file` (`0x0884d6a8`) and the three loaders; confidence high for the checks, medium for the field names.

| Offset | Size | Field |
| --- | --- | --- |
| `+0x00` | 4 | Magic `YGTF` (`0x088a17c4`) |
| `+0x04` | u16 | Scramble seed |
| `+0x06` | u16 | Kind: must equal the requested kind (0, 1, 2) |
| `+0x08` | u32 | `H`, header length |
| `+0x0c` | | Length-prefixed UTF-16 names, one per language index in `save_get_language` order: u16 length, then the units (`save_import_get_localized_name`, `0x0884d000`). Not used for kind 0 |
| `H - 2` | u16 | Header checksum: `0x4654` plus every byte of `[0, H - 2)`, 16-bit |
| `H` | | Scrambled body, `S - H - 2` bytes |
| `S - 4` | u16 | Body checksum, inside the scrambled range: `0x5847` plus `byte[i] >> (i & 3)` for `i` in `[0, S - H - 4)` over the unscrambled body, 16-bit |
| `S - 2` | u16 | File checksum: start `0x3750`, `c = ~(c + byte)` as u16 over `[0, S - 2)` |

**Unscrambling** (`save_import_unscramble`, `0x0884d850`): seed the LCG stream of `system.md` ("LCG streams") with the u16 seed; `n = rand & 0x1ff`; then `n` times swap `body[rand % size]` and `body[rand % size]`, two draws per swap, in that order. `size` is `S - H - 2`. This is a byte shuffle of game data, not platform protection.

**Bodies** (offsets from `H`, after unscrambling):

- Kind 0: u16 card id at `+0`. It must pass `card_db_is_valid`; nothing else limits it.
- Kind 1 (`S - H` at most `0x200`): u16 main count at `+8` (must be 40–60) and the ids, then u16 extra count (below 16) and ids, then u16 side count (below 16) and ids. Invalid ids are dropped and the kept counts stored. Whether the 8 bytes before the main count mean anything is not known.
- Kind 2: u16 pair count at `+0`, at most `0xe10`, then `count` pairs of u16 `{card id, status}`.

## What importing does

- Cards (`ui_title_update_external_cards`, `rel_title` `0x08ebdd34`): on confirm, a card whose collection flag bit 7 is clear gets that flag and three copies (`save_change_card_count(id, 1)` three times). Bit 7 is shared with the wireless card gift, so a card is received once by either route.
- Decks: listed as a third deck source in free duel, wireless duel and the recipe viewer. They are not written to the save.
- Lists: `rel_limitlist`, the second menu choice.

## Open questions

- Whether any real file still exists, and which cards Konami offered. The start page is `http://www.konami.jp/gs/game/yugioh_tf3/dleu/` (`rel_html_view` `0x55cc`); the port does not need it.
- The first 8 bytes of a kind 1 body.
