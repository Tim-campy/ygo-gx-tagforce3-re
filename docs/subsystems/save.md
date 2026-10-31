# Save data and game state (`save`, work package 3)

The save file layout is in `docs/formats/save.md`. This document lists the code families around it. Addresses are runtime addresses in `BOOT.BIN` unless a module is named.

## Function families named in the 2026-10-31 round

Basis and method: `system.md`, same section. 120 names (115 in `BOOT.BIN`, 5 in `rel_field`).

| Family | Count | Evidence |
| --- | --- | --- |
| `progress_flags` | 32 | Getters and setters of the progress bit arrays of the game state (`save.md`). |
| `character_row_flags` | 22 | Per-character row flags of the game state. |
| `settings_fields` | 14 | Option and settings fields. |
| `save_dialogs`, `save_tasks` | 19 | The save-data utility dialogs and the request dispatcher `0x0884123c` on the request word `0x08acd9cc`: 1 space check, 2 size, 3 autoload, 4 and 7 load, 5 save, 6 delete, 8 autosave. |
| `ms_import` | 11 | `0x0884c978`–`0x0884d964`: reads files under `ms0:/PSP/SAVEDATA/<ULES01183…>/` of three kinds (one card record of `0x44` bytes, a deck of 40–60 cards in `0x1c0` bytes, a list of up to `0xe10` entries). Each file has a magic, three checksums and a byte-swap scramble driven by an LCG: game-data obfuscation, not platform protection. The functions are named only; nothing was unscrambled. `rel_title` state 6 lists these records. |
| `card_record_flags` | 8 | Bits of the per-card save record: byte 1 bit 7 (`0x0885640c`/`0x08856478`) is the flag the player toggles from the shop results' card menu (icon `0x2026`); byte 0 bits 4–6 (`0x088565dc`) with `card_db_is_card_marked` choose an alternate art variant (from `rel_shop`). |
| `save_paths`, `save_player` | 6 | Save paths and player record. |
| `field_save` (`rel_field`) | 5 | Save dialog opened from the field. |

## Open questions

- The meaning of the `ms_import` records for the game (download, trade or another save) is not established.
