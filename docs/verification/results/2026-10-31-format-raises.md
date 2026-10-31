# Format rows raised to `verified` (2026-10-31)

Each row below was already `documented` (or `reimplemented`) and its layout matched live memory or a differential save in the check named, so `re/formats.csv` sets it to `verified` (`ppsspp-plan.md`, "Reporting results").

| Row | Check | What matched |
| --- | --- | --- |
| `file_index` | E1 (`2026-10-31-sessionE-T.md`) | Start/end/ready words, 2,131 entries = disc files, first entry path/LBA/size |
| `save_header` | E7, E8 (`sessionE-S`) | Frame counter `+0x0c` at 30 per second; `+0x04`–`+0x0b` constant; DATA0 = memory |
| `save_settings` | E5, E5b (`sessionE-T`) | Every option field located by single changes; volumes as value − 1 |
| `save_player_profile` | C4 (`2026-10-27-sessionC.md`), E16 (`sessionE-P`) | DP `u32` at `+0x0fdfc` changed by `save_add_dp` |
| `save_pack_records` | E16 | Stock nibble − 1, rarity-box entry `n = 0`, `r = 1` |
| `save_collection` | E16 | Five drawn cards: count byte 1 → 1 (and byte 0 = `0x02`) |
| `pack_draw` | E16 | Price, bought flag, purchase counter, one draw, one entry, commit at the results screen |
| `story_spot_table` | C2 (`sessionC`) | Records' location, cells and direction equal spots 334/335, 100, 50 |
| `story_chapter_table` | E13 (`sessionE-W`) | Points gate at the cap, keys `(201, 1, 1…3)`, highlighted step-2 location, stage close in the step-3 chain |
| `field_maps` | E11 (`sessionE-W`) | Arrival cell, direction and the per-door rule of location 6 in four map changes |
| `field_door_table` | E12 (`sessionE-W`) | Room 101 locked at light period 4, room 204 and dining hall open; sliding vs hinged kinds |

The duplicate row `pmf` (the same format as `psmf_movie`) was removed from `re/formats.csv`.
