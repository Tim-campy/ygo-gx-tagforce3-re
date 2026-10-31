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

Second group, raised in the same round after their layouts were written down (`documented`) in `docs/formats/save.md` and `docs/formats/story-runtime.md`; the checks are the earlier sessions:

| Row | Check | What matched |
| --- | --- | --- |
| `save_partner_word` | C3 (`2026-10-27-sessionC.md`), E8 (`sessionE-S`) | `0x0023` = character 2 (bits 4–11), variant 0 (bits 12–15) with Jaden as partner and the logged `char=2`; same word in memory and `DATA0` |
| `story_runtime_records` | C2 (`sessionC`), E7 (`sessionE-S`) | Record index = id − 2; `+0x00` location, `+0x0c/+0x10` cells, `+0x15` direction, `+0x18` spot equal the spot table; `+0x58` = day index; idle diff changes only `+0x04/+0x08/+0x14` of walking NPCs |
| `story_field_state` | E11 (`sessionE-W`) | `S + 0x1a0e0`: location, previous location, `f32` x, `f32` y, direction equal the arrival table after four map changes |
| `story_event_queue` | Queue logs of `sessionE-W` (E10–E13) | `world_queue_event` keys `{a1, a2, a3}` (`(0x25, 8, 6)`, `(301, 4, 1)`, `(201, 1, 1…3)`, …) and the records ran in queue order; the ring memory was not dumped |

The duplicate row `pmf` (the same format as `psmf_movie`) was removed from `re/formats.csv`.
