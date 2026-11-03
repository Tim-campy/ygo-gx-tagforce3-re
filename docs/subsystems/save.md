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

## Documented functions

The functions of this group that reached the `documented` stage in the 2026-10-31 documentation round and in the 2026-11-03 round (prototype, purpose, return value, side effects and callers, read from the decompilation) are listed in [`functions/save.md`](functions/save.md).

## Functions documented in the 2026-11-03 round

Every save task in `BOOT.BIN` is a per-frame state machine on the shared state word `0x08acd9d4`. `save_update_task` (`0x0884123c`) calls it once per frame while the request word `0x08acd9cc` selects the task. Each task owns its own range of state values: getsize 3–9, autoload 1–2, space check 10–0x10 and 0x33–0x34, load 0x11–0x1b, save 0x1c–0x26, delete 0x27–0x2a, autosave 0x2b–0x32. Five states are shared by all tasks:

- `0x35` counts `0x08acd9d2` frames down, then jumps to `0x08acd9ec`.
- `0x36` waits for the in-game message box to close (`0x08acd9f4` cleared by `save_update_utility_dialogs`). It then jumps through the table `0x08acd9d8`, indexed by the box result `0x08acd9d0`. Slot 2 (`0x08acd9e0`) is used after a programmatic `ui_close_message_box`; slots 3 and 4 (`0x08acd9e4`, `0x08acd9e8`) are the two answers of a yes/no box; slot 5 (`0x08acd9ec`) follows an OK box.
- `0x37` calls `save_close`.
- `0x38` holds and keeps returning the result word `0x08acd9fc`.

A task returns 1 while running, then 2 (success) or 3 (failure or declined).

The interactive tasks follow one pattern:

1. Show the "working" message 3 for 20 frames.
2. Start a utility with a `save_start_*` function.
3. Poll `sceUtilitySavedataGetStatus`: statuses 1, 2 and 4 mean busy, 3 calls `ShutdownStart`, 0 means finished.
4. Branch on the utility result: `+0x1c` of the param block, or `+0x5cc` when `+0x1c` is 2.

The result codes are handled as follows:

- `0x80110321` and `0x80110322` lead to message `0x14` or `0x15`. Hypothesis (medium): no Memory Stick, or the stick was removed.
- `0x80110327` (no save data) leads to message `0x16`. In the save, autosave and space-check tasks it is accepted when the size list's needed-space word (`*(+0x5fc) + 0x24`) is 0.
- Any other non-zero code goes to the system error dialog (`save_start_msg_dialog`) and then to a yes/no "retry?" box.

`save_run_load_task` (`0x0883f984`) runs a size query before the autoload. It accepts the data only when buffer word 0 is `0x30000`. `save_run_save_task` (`0x088401f0`) can delete the old save (`save_start_delete_dialog`) when there is not enough space. `save_run_autoload_task` (`0x0883eafc`) and `save_run_autosave_task` (`0x08840d20`) are silent variants with no message boxes. `save_run_delete_task` (`0x088409e4`) always ends with result 2. The tasks that change the state or the file call `save_store_psid_checksum` and set the task status flag (`save_set_task_status_flag(1)`).

The `ms_import` loader `save_import_update_load` (`0x0884cbbc`) is another state machine, stored in the context `*0x08db3de4` (bits 3–6 of `+4`). Its steps are: open the message box and inhibit soft reset; load up to 8 files per frame; wait 9 frames and close the box; wait for the box flag to clear, then report the count and free the context. Records are 0x44 bytes for cards (failures are kept and flagged in bit 0 of `+0x42`), 0x1c0 bytes for decks, and 0x108 bytes for lists. A deck record (`save_import_load_deck_file`, `0x0884d1bc`) is the localized name at `+0`, followed by a normal 0xc0-byte deck at `+0x100`. The file stores its lists in the order main (40–60), extra (< 16), side (< 16), and invalid ids are dropped.

## Open questions

- The meaning of the `ms_import` records for the game (download, trade or another save) is not established.
