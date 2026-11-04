# Free-roam world (work package 7)

How the Duel Academy free roam is put together: maps and their files, exits, characters on the map, the calendar and time of day, friendship points, the partner, and how the card shop unlocks packs. Static analysis only (Ghidra decompilation of `rel_field.prx`, `rel_story.prx`, `rel_shop.prx` and `BOOT.BIN`, plus the data files); nothing here has been traced in PPSSPP yet.

Modules (`docs/subsystems/modules.md`): `rel_field` (scene 5, base `0x090ced00`) draws and runs the field and serves 33 requests from `rel_story`; `rel_story` (scene 2, base `0x08e9aa00`) owns the calendar, the story state and the event bytecode (`docs/formats/story.md`); `rel_shop` (scene 7, base `0x090ced00`) is the card shop. Persistent state lives in the save state block (`save_get_state()`, `docs/formats/save.md`).

Formats: `docs/formats/hmp.md` (walk grid and floor height), `docs/formats/field-tables.md` (map ids, archives, doors, exit cells, field string tables), `docs/formats/field-maps.md` (per-map data: location ↔ map, lighting, door behaviour, door cells, walk overrides, arrival cells, NPC positions, island map, and the per-location JSON export). Tools: `tools/world.py hmp`, `tables`, `locations`.

## Maps

- A map is one archive `field/map/bg_NN_MM.ehp`: mesh, animations, textures and the walk grid `.hmp`. The field module knows 32 maps by **field map id** `M` (1–42, sparse) and converts it to an index 0–31 (`world_map_id_to_index`, `rel_field` `0x090d1144`) that selects the archive name and meshes (`field-tables.md`).
- Story scripts name places by **story location** `L` 1–30 (`scene_map`, opcode 50158); `world_location_to_map_id` (`rel_story` `0x08e9ecfc`) maps `L` to `M` (`field-maps.md`). Confirmed on data: with this mapping 1,214 of 1,218 scripted start and NPC cells are walkable cells of the right grid. (The exit selector at `+0x1f968` gives the exit-group key, which differs from `M` for locations 27–29.)
- **Movement** is on a 0.5-unit grid (`.hmp`): one byte per cell, 1 walkable. Positions in scripts are cell indices; the field centres them (`x·0.5 + 0.25`).
- **Doors** (`rel_field` `+0x25334`) are animated meshes (sliding or hinged, opened within 0.75 units of the player, locked at midnight on the dorm outside except rooms 204 and the dining hall; `world_update_doors`, `field-maps.md`) with a target map id; only the classroom, the store and the Slifer dorm outside (its eight room doors and the dining hall) have them. **Exit cells** (`rel_story` `+0x1fb84`) are cells at the map border or room door; stepping on one ends the walk with field action 0 (see "Field actions"). **Door cells** are hard-coded in `world_get_door_cell_target` (`rel_field` `0x090d9cc8`): on the Slifer dorm outside (`M` 12 and 37) cells `(15, 24)` → `M` 13, `(15, 20)` → 14, `(15, 16)` and `(15, 12)` → 40, `(13, 24)` → 17, `(13, 20)` → 18, `(13, 16)` → 19, `(13, 12)` → 20, `(13, 6)` → 21 (dining hall); on the special hall (`M` 36) `(9, 0)` and `(10, 0)` → 39. They end the walk with action 17 and the target map; `rel_story` converts it to a location with `world_map_id_to_location` and reloads (high, code).
- **Island map** (`field/big_map/world_<period>.ehp`, five variants: morning, day, sunset, night, midnight; field resources 2–6 at `rel_field` `+0x2ee3c`): the travel screen with arrows (`bm_arrow11–14.ehf`). See "Island map" below.

## Island map (travel)

Flow (`rel_story` state machine `world_story_state_step`, `0x08ea0154`, state variable `0x08ecd978`): an exit cell outside a dorm room leads to state 7 (`0x08ea2568`), which **advances the time by one slot** (`world_change_time(2)`) and goes to state 1 (`0x08ea1bf4`): field request 0 (scene set-up) and `world_open_island_map` (`0x08ea1888`); state 2 (`world_poll_island_map`, `0x08ea1cb8`) waits on field request 29, which returns `{cancelled, M}`. On a choice the location becomes `world_map_id_to_location(M)` and state 3 loads it; on cancel state 12 (high, code).

`world_open_island_map` sends field request 2 with `{current M, list pointer, list count, …, highlighted M}`: the current place, the place of the partner's next chapter event (`world_get_next_chapter_event`, only at story sub-stage 2 when the points are at the cap and the slot is < 7, else −1), and a list of **disabled destinations** that holds `M` 2 (the classroom) in slots 3 and 4 only: listed areas (or building sub-points) are not drawn and the cursor skips them (`world_island_map_open`, `world_island_map_navigate`; medium for the reading that the classroom is closed during those slots). The field side (`world_island_map_open`, `rel_field` `0x090e3854`) picks the archive by the light period (period 0–4 → resource 2–6: confirms the period/archive order, high) and works with **12 island areas**:

| Area | Destination `M` | Place |
| --- | --- | --- |
| 0 | 12 | Slifer Red dorm outside (rooms and dining hall belong to this area) |
| 1 | 22 | Ra Yellow dorm |
| 2 | 23 | Obelisk Blue boys' dorm |
| 3 | 24 | Obelisk Blue girls' dorm |
| 4 | 1–5 | Academy main building, with five sub-points: 0 gate, 1 classroom, 2 store, 3 duel area, 4 principal's office |
| 5 | 26 | Cliff |
| 6 | 25 | Port |
| 7 | 27 | Abandoned dorm |
| 8 | 29 | Forest |
| 9 | 30 | Volcano |
| 10 | 31 | Beach |
| 11 | 32 | Laboratory |

`world_island_area_of_map` (`0x090e47d0`) maps `M` → `(area, sub-point)` and `world_island_area_to_map` (`0x090e4710`) back; the result of the menu is `world_island_area_to_map(area, sub-point)`. Area screen positions are `i32` pairs at `rel_field` `0x090f85b0` (8 bytes per area, pixels on the 480 × 272 screen); the cursor moves to the nearest enabled area within a 45°, then 60°, then 75° cone of the input direction (`field-maps.md`, "Island map"). Maps 36–42 (special hall, laboratory 2, bridge…) and the second dorm versions are not reachable from the island map; story scripts move the player there (high for the tables, code).

## Field actions

When the player acts, `rel_field` ends the walk (`world_field_command_step`, `0x090ddb74`; input in `world_field_read_command_input`, `0x090de874`) and `rel_story` reads the result with field request 16 (`world_field_poll_action`, `0x090de6b0`: action code, player cell and direction, the list of characters on the map with their cells, the target row and a door id). `world_handle_field_action` (`rel_story` `0x08ea1ef8`) dispatches on the action code:

| Code | Trigger (field side) | Story side |
| --- | --- | --- |
| 0 | Stepped on an exit cell (`world_is_exit_cell`, `0x090d9c6c`) | `world_classify_exit` (`0x08ea38b8`): in a dorm room (locations 7–15, 28) → back to the dorm outside; slot 7 → the partner refuses (record `(a1, 5, 4)`); slot 2 → `(a1, 3 or 4, 1)` (4 on tournament days, `0x08eab474`); otherwise → island map. |
| 2 | Talk (button on a character) | `world_talk_to_character` (below). |
| 3 | Duel (menu on a character) | Duel request (below). |
| 4, 5, 6 | PDA entries | System flags 5/17, state 12. |
| 7, 11–15 | PDA/menu entries | Other game modes (states 16, 31, 28, 37, 43, 34; not traced). |
| 8 | Advance-time menu | `(partner a1, 5, n)` with n from the slot. |
| 9, 10 | Special cells `(32, 2)`/`(33, 2)` and `(30, 2)`/`(31, 2)` on the laboratory map (`M` 32; `world_get_lab_special_cell`) | States 19 / 25 (not traced). |
| 17 | Door cell | Change location (above). |
| 18 | Item/sub-menu | Field request 30. |

## Calendar and time of day

The calendar is a 0x24-byte block at story block `+0x3438` (save state `+0x1a24c`, see "Save fields"), registered by `world_set_calendar_blocks` (`rel_story` `0x08eaabd8`) and recomputed by `world_update_calendar` (`0x08eac278`) after each change.

| Word | Meaning | Conf. |
| --- | --- | --- |
| `+0x00` | Time-slot counter `t`, starts at 1 (`world_init_calendar`, `0x08eaac3c`). | H (code) |
| `+0x04` | Slot within the day, `(t − 1) % 7 + 1`, 1–7 (`world_get_time_slot`). | H (code) |
| `+0x08` | 5 at a new game, never recomputed here. Presumably the starting month (May; the field strings name May–August). | L |
| `+0x0c` | Day number, `day + 1` (shown as `(day%d)`). | M |
| `+0x10` | Day index `day = (t − 1) / 7` (`world_get_day_index`). | H (code) |
| `+0x14` | **Light period** of the slot, from the table at `rel_story` `+0x208ec` (8 bytes per slot): slots 1–2 → 0, 3–4 → 1, 5 → 2, 6 → 3, 7 → 4 (`world_get_light_period`). | H (table) |
| `+0x1c` | Weekday `(day % 7 + 1) % 7`, so day 0 → 1. 0 = Sunday, 1 = Monday (the game shows day 7 as Monday). It gates the weekly NPC pairing (below). | H (code, verified in PPSSPP) |
| `+0x20` | 1 at a new game. | — |

So **a day has seven time slots** and five lighting periods. The five periods match the five island-map archives in the order `morning, day, sunset, night, midnight` (field resources 2–6) (medium: the order of the archive list and the period values agree, the selecting code is not read). Changing time: `world_advance_time_slot` (`0x08eaacc8`, +1), `world_advance_time_slots(n)` (`0x08eaace0`), `world_set_time_slot(n)` (`0x08eab070`, slot `n` 1–7 of the current day), `world_advance_to_next_day` (`0x08eab0bc`, slot 1 of the next day). These back the PDA "Advance Time" menu ("Advance to the designated time", "End the day", "Speed up time to the day before the tournament"; `field_strtbl.bin`).

`world_is_day_off(n)` (`0x08eaacf8`) returns the table `rel_story` `+0x2e50c` `[0,0,0,0,0,0,1]` at `(day + n) % 7`: day index 6 of each week is special. With weekday 1 for day 0, that is weekday 0, Sunday: the game starts on a Monday (high: PPSSPP showed day index 6 as Sunday and day 7 as Monday, `docs/verification/results/2026-10-27-sessionC.md`). The calendar words, their writers and the seven slots per day were checked in the same session. `0x08eab474` tests `day % 10` against 9 and 0 (presumably the ten-day tournament cycle; low).

## Story stage

The field save block (story block `+0x345c`, `0xa8` bytes) starts with the **story stage** byte, 1–10 (`world_get_story_stage`, `0x08eab3fc`; `world_advance_story_stage`, `0x08eab3c0`, is the handler of opcode 50094 `advance_counter`: +1, capped at 10, and sets byte 1 to 1). Byte 1 is the **chapter step** 1–4 within the stage (`world_get_chapter_step`, `0x08eab440`; `world_advance_chapter_step`, `0x08eab40c`: +1, back to 1 after 4): `world_get_next_chapter_event` looks up the partner chapter table at entry `step + 4·(stage − 1)` and advances the step past empty entries (high, code). Both bytes start at 1 (`world_init_calendar`). The chapter table, the triggers of each step and the end of the partner story are in [`docs/formats/chapter-table.md`](../formats/chapter-table.md): a partner story is four stages of three or four steps, opened by the points cap `1000·stage`, and ends at stage 5 with `finish_partner_story` and the staff roll. Story flags (`world_set_story_flag`, `world_test_story_flag`): 1–32 in field-block word `+0x0c`, 33–64 in `+0x10`, 129–160 and 161–192 in words `+0x00`/`+0x04` of the flag block at story block `+0x42d8`; 65–128 are ignored. System flags (`0x08eaaee8` set, `0x08eaafbc` test; bit `n − 1`): 1–32 in field-block `+0x14`, 33–64 in `+0x18`, 65–96 and 97–128 in flag-block `+0x08`/`+0x0c`.

## Characters

- **Static table** (`BOOT.BIN` `0x088aa510`, 174 rows of 148 bytes, `docs/formats/sound.md`): row `r` ↔ `(character, variant)` through `world_get_character_key(r)` (`0x0885ad14`) and `world_find_character_row(c, v, &r)` (`0x0885aca0`, row = (record − `0x088aa510`) / 148); `world_count_character_variants(c)` (`0x0885b0b0`) counts the rows of one character. Other accessors in `0x0885adec`–`0x0885bb60` return single fields (`+0x08` a category byte: `0x0885aeb0`, 5 when missing; `+0x2c..+0x2e` three signed bytes, all ≥ 0 meaning "has a field model", `0x0885b984`; `+0x3c` a u16 bit set, `0x0885b7f4`; `+0x40`, `+0x84..+0x90` pointer pairs). The accessors of `+0x44..+0x74` (`0x0885b4ac`: 5 bytes `+0x44..+0x48`; `0x0885b4fc` and `0x0885b56c`, identical: 9 bytes `+0x49..+0x51`; `0x0885b5dc`: 8 words `+0x58..+0x74`) have no caller in `BOOT.BIN`, `rel_field`, `rel_story`, `rel_shop`, `rel_duel_eng`, `rel_duel_draw` or `rel_duel_mgr`. They are **not** gift preferences: gifts use a table in `rel_story` (below). The values look like duel tuning (bytes 10/50/60/80, signed −5/−10, words 1000/100/1) and are identical across variants of a character; hypothesis (low): AI personality for a module not in the Ghidra project. `+0x08` is the **category** (`world_get_character_category`, `0x0885aeb0`; 5 when the character does not exist): 0, 1, 2 are duellists, 4 and 5 are not (`world_character_can_duel`, `0x0885b8fc`, returns category ∉ {4, 5}); the daily pairing below groups characters by it.
- **Per-row state in the save**: two bytes per table row at save `+0x1bf8c + 2r` (`save_get_character_flags`, `0x0885519c`; `save_get_character_flags_by_key(c, v)`, `0x08855178`). Byte 0 bits 0–3 and byte 1 bit 0 are flags with set/test pairs (`0x088551d4`–`0x08855548`), byte 1 bits 1–3 and 4–6 are 3-bit values. Bit 2 of byte 0 (`save_test_character_flag_bit2`, `0x08855378`) gates shop packs (below); it is set by `finish_partner_story` for the partner's row, so it marks a **finished partner story** (medium: the only setter in `rel_story` is `world_driver_finish_partner_story`, and the staff roll picks its second movie when both of Jaden's variants 0 and 1 have it; `chapter-table.md`).
- **Runtime records**: 140 records of `0x5c` bytes at **story block `+0x0000`** (so they are saved; `*(0x08ecd964)`, set by `0x08e9d3e8` from the story init `0x08e9f3ac`), sorted by character id at `+0x1c` (record index = character id − 2 in the save read in PPSSPP) and binary-searched (`world_find_runtime_record`, `0x08e9d594`). Fields used here: `+0x00 u16` current location, `+0x0c`/`+0x10` cell x/y, `+0x15` direction, `+0x17` a remark index (table `0x08eb4e10`), `+0x18 u16` **spot index** (below), `+0x20` variant, `+0x24` deck index n *within the owner* (0–9; `deck_get_owner_recipe(char, n)` turns it into a recipe, `docs/formats/deck.md`), set by `0x08e9e340` from the partner's points, `+0x28`… event-set-up position (`npc_position`), `+0x40 u16` event variant (65000 = none), `+0x46/+0x48/+0x4a` the Duel key (`npc_event`, 50166), `+0x4c/+0x4e/+0x50` the Talk key (`npc_event_b`, 50171), `+0x54` flag bits (`world_set_record_flag` / `world_test_record_flag`, `0x08e9d65c` / `0x08e9d6c8`, bit `n` = `1 << (n − 1)`): 1 not in free roam, 2 placed by the daily pairing, 3 absent (slots 3–4), 4 gone (`npc_leave`; cleared for all after events), 5 excluded from pairing, 6–8 random per pair (6: present in slots 3–4; 8: remark 6). (Medium: offsets from the code, meanings from the uses. `+0x00`, `+0x0c/+0x10`, `+0x15` and `+0x18` were checked against the spot table in PPSSPP, Session C; `+0x58`, not used here, held 1 or 6.)

### Character table (`rel_story` `+0x2245c`)

140 rows of 57 `u32` (228 bytes), one per character 2–141 in ascending order, read only through `world_get_char_table_value(char, column)` (`0x08eac124`) and `world_get_char_table_cell(row, column)` (`0x08eac0f4`). Tool: `tools/world.py chars <rel_story.prx> --check` (all rows pass).

| Column | Content | Conf. |
| --- | --- | --- |
| 0 | Character id | H |
| 1–4 | **Event key `a1`** of the character's conversation records, for variant 0–3 (0 = none; for example character 6 has four) | H (all callers use `variant + 1`) |
| 5 | 1 = not placed by the free-roam schedule (42 rows; main cast and story characters); copied to record flag 1 | H (code), M (meaning) |
| 6 | 1 = excluded from the daily pairing (17 rows, among them the two sandwich sellers 26 and 27); copied to record flag 5; also returned by `0x08e9c504` | H (code) |
| 7–56 | **Taste of item 1–50** (column `6 + k`, `world_item_taste_column`, `0x08e9f1c4`): 1 best … 5 worst, 6 random. Item 48 (Destiny) is 6 for everyone, item 50 (golden egg) 1 for everyone | H |

### Daily schedule and NPC placement

- **Once per day** (`world_change_time`, `0x08ea05a8`, detects the new day with `world_check_new_day`, `0x08eab380`: calendar day `+0x10` against the last day seen at field save block `+0x04`): `world_pick_sandwich_seller` (`0x08eab848`) sets system flag 4 at random (forced when the partner is 26 or 27), which decides which seller (26 or 27) sells sandwiches and which cards; **only when the calendar weekday `+0x1c` is 1 (Monday)**, read by `world_get_weekday` (`0x08eab3b0`), `world_assign_daily_spots` (`0x08eab8a4`) runs, so the pairs are drawn once a week and kept for seven days (high: code at `0x08ea0690`, and PPSSPP showed the same pairing order on days 1–6 and a new one on day 7); then `0x08eab810` (a random 0–71 for character 139) run, `0x08e9deac` re-rolls the remark index, story flags 1–20 are cleared.
- **`world_assign_daily_spots`**: takes every runtime character except the fixed ones (127–136, 138, 140, 51, 26, 27), groups them by category (0, 1, 2; others go to the fixed group), shuffles each group, then swaps about 60% of category-2 characters with a random category-0 or -1 one. Characters with flags 1 and 5 clear are written in this order to the field save block `+0x1c` (140 bytes, filled with `0xff` first) and get flag 2 **cleared** (`world_set_record_flag(char, 2, 0)`); when their number is odd, character 100 is taken out of the order and gets flag 2 set, so flag 2 marks a character left without a pair (high, code; this answers the PPSSPP observation that paired characters do not have flag 2). Consecutive entries form **pairs**: each pair receives two neighbouring spots `(s − 1, s)` (s odd) of the **spot table** (`rel_story` `+0x2092c`, 350 × `{u32 location, u32 x, u32 y, u32 direction}`, `world_get_spot`, `0x08eac06c`; `tools/world.py spots`), drawn at random among free spots with at most 10 characters per location (6 at location 28). Each pair also gets the random flags 6–8. `world_get_duel_pair_partner(char)` (`0x08eac004`) returns the other member; it is used when the player duels one of them (`0x08ea4a98`). So **NPC placement is random per week, in pairs (presumably two students talking or duelling), not a fixed schedule** (high for the code. Verified in PPSSPP: the first pair of the order, characters 3 and 120, held spots 334 and 335 at location 21, cells (20, 1) and (19, 1), and paired characters stood together on screen. The function name keeps "daily" for history). ~~Open: neither member of that pair had flag 2 set on day 6 (flags `0xa0`).~~ Expected: the pairing clears flag 2 (above). The spot table covers locations 1–4, 6–8, 11–13, 15–24 and 28 (20–30 spots each, 6 in rooms).
- **Each time slot** (`world_update_npc_positions`, `0x08e9d72c`; it also stores the current day index in record `+0x58` and sets byte `+0x16` to 6 when flag 8 is set; the flag `world_change_time` passes in `a0` is not read): record flag 3 is set in slots 3 and 4 (absent, presumably class time) unless flag 6 is set; character 51 gets flag 1 from slot 3 on, so it appears only in slots 1–2. Fixed characters take their place from `world_get_fixed_npc_spot` (`0x08eab500`): a 13-entry table at `rel_story` `+0x2238c` for characters 51 and 127–136/138/140, a 72-entry table at `+0x21f0c` indexed by the daily random for 139, and `+0x2e550` for the sellers 26/27 (two positions, swapped by flag 4; the partner's seller uses the third). Everyone else gets location and cell from its spot (`+0x18`).
- **On entering a location** (state 4, `0x08ea1d90`): `world_place_player_on_arrival` (`0x08ea09c8`) puts the player on a fixed cell per location (or per door when entering the dorm outside), `world_send_exit_cells`, then `world_send_npc_list` (`0x08ea0f58`) sends field request 7 with every runtime character whose location equals the current one, flags 1–4 clear (unless an event runs), not the partner (unless system flag 30), and not the sellers in slot 7; plus anonymous extras on locations 2 and 4. During a scripted event the set-up opcodes override location and cell (`+0x28…`).

### Event driver and record selection

- **Queue**: an 8-entry ring of record keys `{a1, a2, a3}` at story block `+0x3264` (`*(0x08ecea48)`, `+0x60` ring index, `+0x64` the last menu answer). `world_queue_event(a1, a2, a3)` (`0x08ea5d18`) appends; `world_driver_next_event` (`0x08ea5dc8`) takes the next entry and starts it (`dialogue_find_event_record`), returning 0x65 while records remain; when the queue is empty it checks system flags 21–25, 15/16, 28, 3, 29 for pending follow-ups (for example flag 15 → the gift record) and returns a result code that `world_driver_handle_result` (`0x08ea259c`) turns into a state change (0x66–0x6e mini-games and quiz, 0x6f/0x70 partner offer, 0x71 gift reaction, 0x73 day events, 0x74 back to the field, 0x76 next day, 0x77 end of an event).
- **Talk** (`world_talk_to_character`, `0x08e9c5b0`): during a scripted event, the character's Talk key (`+0x4c`) if set; otherwise `(a1, 8, n)` with `a1` = column `variant + 1` of the character table and n = 1, except: the sellers use n = 6 (sandwiches) or 7 (cards) by flag 4, and n = 8 when the partner is character 8 variant 1 (high, code). Group 8 is therefore "free-roam talk"; 8/6 and 8/7 are the shop dialogues.
- **Duel** (action 3, in `world_handle_field_action`): the character's Duel key (`+0x46`) during an event; otherwise `(a1, 8, 2)` (the duel request line), then, if `world_character_can_duel`, `(301, 5, 1)` (menu "You duel / Your partner duels / Tag duel") or `(301, 5, 2)` (two options; sellers 26/27 with story flags 135/134, and character 51) and the duel set-up `0x08ea4d8c(char)` (high, code).
- **Partner events** (`world_select_partner_event`, `0x08e9c3e0`, on every map entry): with `a1` = the partner's key: at the points cap, the next **chapter event** from the partner chapter table (`rel_story` `+0x2a10c`, 64 rows of `0x110` bytes: a header `{kind, char, variant, alt variant}` and 16 entries `{location, a1, a2, a3}` = 4 stages × 4 steps; `world_try_chapter_event`, `0x08e9cad0`; layout, row choice by character category and trigger rules in [`chapter-table.md`](../formats/chapter-table.md)): steps 1 and 4 on the first map entry of a working day while the partner talk is pending, steps 2 and 3 when the player enters the entry's location outside slots 1 and 7; else `world_partner_daily_event` (`0x08e9cd0c`): `(a1, 1, 1)` always, then `(a1, 1, 2)` on day 0, `(a1, 1, 4)` on the day off, `(a1, 1, 6)` once points ≥ 2000 (system flags 2/3), `(a1, 1, 5)` with 10% chance when the points grew by 200 since the last time, else `(a1, 1, 3)`; or, 25% of the time, a location remark `(a1, 2, n)` (`world_partner_location_remark`, n from the location). Other groups: `(a1, 3/4, …)` slot-2 and tournament days, `(a1, 5, n)` time menu, `(a1, 6, taste)` gifts, `(a1, 9/10, …)` driver follow-ups.
- **Conversation records** therefore follow `(a1, group, n)`: group 1 daily partner talk, 2 location remarks, 3/4 day events, 5 time-of-day reactions, 6 gift reactions (n = taste 1–5), 8 free-roam talk/duel/shop, 9/10 follow-ups. `a1` 301 holds the generic records (points changes, menus, gift dialogue), 201–219 the chapters.

## Friendship points and the partner

- Points: `u16` at `+0x16` of the 143 save character records (`save.md`), 0–8000.
- Story scripts change them with `world_change_char_points(char, delta)` (`rel_story` `0x08e9d9c0`, called from opcodes 50084/50085): the new value is clamped to `[0, cap]` with **cap = `world_get_points_cap()`** (`0x08eab450`) = table `rel_story` `+0x2e528` indexed by the story stage: stage 1 → 1000, 2 → 2000, …, 8 and 9 → 8000. So friendship can only grow as the story advances (high for the code, medium for the reading). The return value (+1 / −1 / 0) drives the up/down/no-change display (field request 28).
- **Partner**: `u16` at save `+0x16e12` (`save_get_partner_field`, `0x08857be8`): bits 4–11 character, bits 12–15 variant, bit 0 a flag (`0x08857cd8`). `save_get_partner(&variant)` (`0x088550c8`) and `save_set_partner(c, v)` (`0x08855110`). The partner chooses the deck slot (`0x08856730`) and unlocks partner packs in the shop.

## Money and level

- **DP**: `u32` at save `+0xfdfc` (`save_get_player_value(0)`, read by `if_dp`); `save_add_dp(n)` (`0x08854ba0`) clamps to 0–999,999,999; a positive `n` is also added to `u32 +0xfe00` (capped at 999,999,999; presumably the total DP earned, low). It reads only `a0`: the `a1 = 200` seen in PPSSPP for a sandwich is a leftover register value. Story `dp_add`/`dp_sub` go through field request 24 (display) (medium).
- **Duelist level**: `u32` at `+0xfdf4` holds level − 1 (`save_get_duelist_level`, `0x08854990`, returns `+1`); `+0xfdf8` is the EXP. `save_add_duelist_exp(n)` (`0x088549bc`) adds EXP and raises the level while EXP reaches `save_get_level_exp_threshold(level + 1)` (`0x08855e08`); the stored value stops at 98 (level 99). Basis: the field strings "Duelist Level", "Duelist Exp", "Until next Level" and the shop thresholds 21–50 (medium).
- Name and team name: `+0xfd5c` (0x32 bytes, `0x08854948`/`0x088548d8`) and `+0xfd8e` (100 bytes, `0x0885496c`/`0x08854910`) (medium; "Team Name:" on the status screen).

## Items and gifts

- Items are numbered 1–50 (sandwiches, 50 = golden-egg sandwich with its own model `for_bread.ehp`/`goldegg_pan.tms`) and 101–104 (four event items); names and descriptions in `field_strtbl_item.bin` (`field-tables.md`). The item menu offers **Eat** and **Give** (`field_strtbl.bin` 7–13); the refusal "There's no one to give it to!" exists; the gift itself always goes to the partner (below).
- **Buying** (records `(a1 of 26/27, 8, 6)`): `if_dp ≥ 200`, `dp_sub 200`, then opcode 50151 (`world_op_buy_sandwich`, `rel_story` `0x08ea9688`; was `op_50151`): it sets system flag 15, opens field request 25 (the stack of sandwiches; returns the item id 1–50), stores the item at field state `+0x38`/`+0x3c` (`world_get_current_item`, `0x08ea5910`), marks the sandwich kind as seen in a 50-bit set at story block `+0x35b0` (`world_set_sandwich_seen`, `0x08ea5b2c`; when all 50 are seen, `world_all_sandwiches_seen` → `save_set_all_sandwiches_flag`, save `+0x1c0e9` bit 2), and for item 50 sets system flag 1 (one golden egg a day) and `save_set_golden_egg_flag` (`+0x1c0e9` bit 1, the condition of shop pack 43). If the item is 49, `if_value_3c 49` gives three cards ("There was a card in the sandwich!"). Exit code 102 (`exit_102`) is the card counter, not the sandwich.
- **Eat or Give**: when the purchase record ends, the driver sees flag 15 and queues `(301, 4, 1)`: "Give the sandwich to your partner? Yes / No". **No = Eat**: the player eats it and a weighted `random_case` gives one random card with rarity 1 (40%), 2 (30%), 3 (20%) or 4 (10%). **Yes = Give**: the answer (queue `+0x64` = 1) makes the driver return 0x71 and `world_give_item_to_partner` (`0x08e9c6f8`) runs. So a sandwich is used at once; gifts go **only to the partner** (field state `+0x14`), never to other characters (high, code and records).
- **Gift value**: `taste = character table[partner][6 + item]`; taste 6 or item 48 (Destiny) → `rand() % 5 + 1`; clamped to 1–5. The driver queues `(partner a1, 6, taste)` (the partner's reaction lines) and `(301, 6, taste)`, or `(301, 6, 6)` for item 50. The generic records change the points with `partner_points_add`/`_sub`: **taste 1 +40, 2 +20, 3 +10, 4 −5, 5 −10, golden egg +200** (then clamped to the stage cap by `world_change_char_points`). So the gift depends on the character (high: code, table and the six records). `tools/world.py` (`gift_points`) encodes this.
- **Inventory**: the field state has 50 `u32` counters at `+0x94 + 4k` (story block `+0x3360 + 4k`, save `0x1a174 + 4k`), decremented by opcodes 50081–50083 (`world_decrement_item_count`, `0x08ea5938`; 50083 decrements the current item) and summed by `if_counter_b_total`. Nothing in `rel_story` increments them and all are 0 in the analysed save; whether they are the item menu's counts ("×", "Eat a sandwich?", `field_strtbl.bin` 10 and 13) is open (low). The four event items 101–104 were not found.
- Other partner-point sources: `(301, 8, n)` +40/−5, `(301, 9, n)` +80/−10, `(301, 10, 1)` +200, `(301, 11, 1)` +5 (records queued by the driver after duels and events; not traced which is which).

## Card shop: pack availability

`rel_shop` `0x090d9264` first calls `0x090d9e5c` and then copies every pack's save state into the shop's pack table; `0x090d9e5c` (5,924 bytes) recomputes the 48 pack states with `save_set_pack_state(p, s)` (`save.md`). States: 0 not available, 1 was available but its condition no longer holds (greyed), 2 on sale, bit 2 (4) "unlocked by the story" (`set_pack_state 60000` in scripts), turned into 2 at the next visit. **Superseded (2026-10-31):** the full rule list, read instruction by instruction, is in [`docs/formats/shop-rules.md`](../formats/shop-rules.md). It corrects this summary: the level, opponent and "all of characters 2–8" rules are independent ways to put a pack on sale (each one alone sets state 2), not extra requirements; pack 15's opponent threshold is 400 and the packs 41/42 byte is `0x090fad50`. The summary below is kept for history. Rules, in order (medium; static reading of the decompilation):

| Packs | Condition for state 2 |
| --- | --- |
| 0–2 | Always. |
| 3–8 | Pack `p − 3` at least 50% collected: `0x090d9cec(p)` = owned cards of the pack's four tiers × 1000 / total ≥ 500. |
| 9–14 | A shop-local value `*(0x090faa70) >> 4` equals 1–6 (source not found; else demoted to 1). |
| 15, 16 | Save flag `+0x1c0e9` bit 4 and the partner's points < 2000 (15) or 2000–4000 (16). |
| 17–23 | Partner is character 2–8 (else 1). |
| 24–33 | Partner in a per-pack character list (ids from 9 to 120, some with a variant condition). |
| 34, 47 | `0x08836e10()` > 599 / > 899 (presumably a collection count). |
| 35–38, 40 | Save counters `+0x11444` > 49,999, `+0x11448` > 99,999, `+0x1144c` > 399, `+0x11460` > 49,999, `+0x11464` > 4,499 (meaning open). |
| 39, 43, 44, 45 | Save flag bits `+0x1c0e9` bit 5, bit 1, bit 7, `+0x1c0ea` bit 0. |
| 41, 42 | Character 26 (variant 0) / 27 (variant 1) has row flag bit 2, combined with bit 0 of the shop byte `0x0973ad50` (set by `0x090db590(mode)`): presumably which of the two counters is open (low). |
| 46 | Shop byte `0x090facf6` bit 0. |
| 9–33, 47 | Also: duelist level > 20 + (p − 9) for packs 9–33, level > 49 for 47. |
| 9–47 | Also: `0x090d9dd4()` (per mille of the flagged entries of a 104-entry list at `0x090ef208` whose byte at duel-record block `+0x494 + 0x14c + n` is set; presumably opponents beaten) above 100–1000, a threshold per pack. |
| 3–41 | All, when every variant of characters 2–8 (except 2/2) has row flag bit 2. |

The 12-byte pack records of the shop table (`docs/formats/packs.md`) are partly runtime: `shop_load_pack_states` (`0x090d9264`) writes the save state into bits 0–1 of byte 0 and the percentage of the pack's cards ever obtained (`0x090d9550`) into byte 1; `byte0 >> 2` is the number of cards per pack (5, or 10 for pack 23), `+4` the unit price, `+6` a clerk voice index. Buying, the shelf of 20, the rarity box and the card draw are in `docs/formats/packs.md` ("Buying and opening packs"; high for the draw).

## Documented functions

Prototype, purpose, side effects and callers of the functions listed in `re/documented-rel_story.tsv` (and `save_add_dp` in `re/documented.tsv`). Decompiled in Ghidra (high unless noted). "Calendar" is the 0x24-byte block above (`*(0x08ecea68)`); "field save block" is story block `+0x345c` (`*(0x08ecea64)`).

| Function | Prototype | Purpose and side effects | Callers |
| --- | --- | --- | --- |
| `rel_story 0x08eac278` | `void world_update_calendar(void)` | Recomputes calendar `+0x04`, `+0x10`, `+0x0c`, `+0x14`, `+0x1c` from `t` (`+0x00`) with the formulas of "Calendar and time of day". Never writes `+0x08`, `+0x18`, `+0x20`. | `world_advance_time_slot`, `world_advance_time_slots`, `world_set_time_slot`, `world_advance_to_next_day` |
| `rel_story 0x08eaacc8` | `void world_advance_time_slot(void)` | `t += 1`, then `world_update_calendar`. | `world_change_time` (mode 2) |
| `rel_story 0x08eab0bc` | `void world_advance_to_next_day(void)` | `t += 7 − (t − 1) % 7` (slot 1 of the next day), then `world_update_calendar`. | `world_change_time` (modes 5, 6) |
| `rel_story 0x08eab3b0` | `int world_get_weekday(void)` | Returns calendar `+0x1c`. No side effects. | `world_change_time`, `0x08eab474`, `0x08ea2ef0` |
| `rel_story 0x08eab380` | `int world_check_new_day(void)` | 1 when calendar `+0x10` differs from field save block `+0x04`, which it then updates; 0 otherwise. | `world_change_time` |
| `rel_story 0x08ea05a8` | `void world_change_time(int mode, int n)` | Mode 2: +1 slot; 3: +`n` slots; 4: slot `n` of the day; 5: next day; 6: location 14 (`world_set_location`) and next day; 7: slot 4; other modes (1 is used on map entry) change nothing. Then, on a new day: unless system flag 20 is set `0x08e9b450(1)`; `0x08ea562c(1)`; system flag 1 cleared; `world_pick_sandwich_seller(partner)`; `world_assign_daily_spots` when `world_get_weekday() == 1`; `0x08eab810`; `0x08e9deac`; story flags 1–20 cleared; a save bit (`0x08856080(2, 1)`) set once the day index exceeds 8 (unread). Always ends with `world_update_npc_positions`. | 13 call sites: story init `0x08e9f3ac` (2), `world_driver_handle_result` (2), state functions `0x08ea1bf4`, `0x08ea1d90`, `0x08ea2568` (map exit, mode 2), `0x08ea2c40`, `0x08ea338c`, and the opcode wrappers `0x08ea8954` (2), `0x08ea89b0`, `0x08ea89dc` |
| `rel_story 0x08eab848` | `void world_pick_sandwich_seller(int partner)` | System flag 4 = 1 when the partner is 27, 0 when it is 26, else `rand & 1`. | `world_change_time`, `0x08e9b5d8` |
| `rel_story 0x08eab8a4` | `void world_assign_daily_spots(void)` | The weekly pairing of "Daily schedule": order at field save block `+0x1c`, record flags 2 and 6–8, spot index `+0x18` (`0x08e9d704`) for both members; then two random per-character values (`0x08855590(c, v, rand % 5)`, `0x088555f8(c, v, rand % 6)`) and `0x08857fd0(rand & 1)` in `BOOT.BIN` (unread). | `world_change_time` |
| `rel_story 0x08e9d72c` | `void world_update_npc_positions(void)` | Per record: flags 1 (character 51) and 3, location `+0x00`, cell `+0x0c`/`+0x10`, direction `+0x15` from the fixed table or the spot, `+0x58` = day index, `+0x16` = 6 with flag 8; then `0x08e9e340` (deck recipes). | `world_change_time` |
| `rel_story 0x08e9d9c0` | `int world_change_char_points(int chr, int delta)` | See "Friendship points": clamps to 0 and the stage cap (0xffff on overflow), calls `0x08eaa6bc(delta)` whenever the value changes (unread). Returns 1 / −1 / 0. | `world_change_partner_points_shown` (`0x08e9b55c`, opcodes 50084/50085) |
| `rel_story 0x08e9c6f8` | `void world_give_item_to_partner(void)` | See "Items and gifts": taste lookup, reaction events `(partner key, 6, taste)` and `(301, 6, taste)` (`(301, 6, 6)` for item 50); `0x08ea5884(item)` (unread). Changes no points itself. | `world_driver_handle_result` |
| `0x08854ba0` | `void save_add_dp(int delta)` | See "Money and level". | the `thunk_save_add_dp` import stubs of `rel_story`, `rel_shop`, `rel_field`, `rel_deck`, `rel_title`, `rel_duel_mgr`, `rel_duel_eng`, `rel_duel_draw` |

**Verified in PPSSPP (2026-10-27, [`results/2026-10-27-sessionC.md`](../verification/results/2026-10-27-sessionC.md))**: `world_update_calendar`, `world_advance_time_slot`, `world_advance_to_next_day` and `world_change_time` (C1, C2: the logged modes and the weekly call of `world_assign_daily_spots`), `world_assign_daily_spots` and `world_update_npc_positions` (C2: weekly order, neighbouring spots, record fields equal to the spot entries, `+0x58` equal to the day index), `world_give_item_to_partner` and `world_change_char_points` (C3), `save_add_dp` (C4). `world_pick_sandwich_seller`, `world_get_weekday` and `world_check_new_day` ran in that session but their results (system flag 4, return values) were not read, so they stay `documented`.

The map, exit, door, walkability and island functions (`rel_field`: `world_map_id_to_index`, `world_map_id_to_name_index`, `world_field_load_map`, `world_is_exit_cell`, `world_get_door_cell_target`, `world_get_lab_special_cell`, `world_is_cell_walkable`, `world_sample_floor_height`, `world_update_doors`, `world_island_area_of_map`, `world_island_area_to_map`, `world_island_map_open`; `rel_story`: `world_location_to_map_id`, `world_map_id_to_location`, `world_select_exit_group`, `world_get_exit_cells`, `world_send_exit_cells`, `world_place_player_on_arrival`, `world_get_fixed_npc_spot`) are documented in `re/documented-rel_field.tsv` and `re/documented-rel_story.tsv`; their behaviour is described in `docs/formats/field-maps.md` and `docs/formats/hmp.md` (static, not yet traced).

## Key functions

Registry names (`re/names.csv`, `re/names-rel_field.csv`, `re/names-rel_story.csv`); evidence above.

| Address | Name | Conf. |
| --- | --- | --- |
| `0x08854990` | `save_get_duelist_level() → level` | M |
| `0x088549bc` | `save_add_duelist_exp(exp)` | M |
| `0x08855e08` | `save_get_level_exp_threshold(level) → exp` (0 for level > 99) | M |
| `0x08854ba0` | `save_add_dp(delta)` | H (documented below) |
| `0x088550c8` / `0x08855110` | `save_get_partner(&variant) → char` / `save_set_partner(char, variant)` | M |
| `0x08857be8` / `0x08857cac` | `save_get_partner_field() → state+0x16e12` / `save_copy_partner_field(out)` | H (code) |
| `0x0885519c` / `0x08855178` | `save_get_character_flags(row)` / `…_by_key(char, variant)` | H (code) |
| `0x08855378` | `save_test_character_flag_bit2(char, variant)` | H (code) |
| `0x08857c5c` | `save_get_story_block() → state+0x16e14` | H (code) |
| `0x0885aca0` / `0x0885ad14` / `0x0885b0b0` | `world_find_character_row`, `world_get_character_key`, `world_count_character_variants` | H |
| `0x088581bc`–`0x08858304` | `system_wcscmp`, `system_wcslen`, `system_wcsindex`, `system_wcscpy`, `system_wcscat`, `system_wcsncat` (UTF-16 string helpers) | H |
| `rel_field 0x090d1144` | `world_map_id_to_index(M)` | H |
| `rel_field 0x090d9f3c` | `world_get_current_map()` | M |
| `rel_field 0x090d9f48` | `world_bind_map_archive(ehp)`: binds meshes, masks, doors, `.hmp` | M |
| `rel_story 0x08eaabd8` | `world_set_calendar_blocks(calendar, field_block, flags)` (caller `0x08e9f3ac`, story init) | H (code) |
| `rel_story 0x08eaac3c` | `world_init_calendar()` (new game) | M |
| `rel_story 0x08eac278` | `world_update_calendar()` | H (code) |
| `rel_story 0x08eaacc8`, `0x08eaace0`, `0x08eab070`, `0x08eab0bc` | time-advance functions | M |
| `rel_story 0x08eaac88`, `0x08eaac98`, `0x08eaaca8` | day index, time slot, light period getters | M |
| `rel_story 0x08eaacf8` | `world_is_day_off(offset)` | L |
| `rel_story 0x08eab3c0` / `0x08eab3fc` | `world_advance_story_stage` / `world_get_story_stage` | M |
| `rel_story 0x08eab450` | `world_get_points_cap()` | M |
| `rel_story 0x08e9d9c0` | `world_change_char_points(char, delta) → +1/−1/0` | H |
| `rel_story 0x08eab224`, `0x08eab124`, `0x08ea0860` | exit-cell selection and request 3 | M |
| `rel_shop 0x090d9e5c`, `0x090d9cec`, `0x090d9264`, `0x090d9dd4` | `shop_update_pack_unlocks`, `shop_get_pack_owned_permille`, `shop_load_pack_states`, `shop_get_opponents_beaten_permille` (`re/names-rel_shop.csv`; the draw functions are in `docs/formats/packs.md`) | M |
| `rel_story 0x08ea0154` | `world_story_state_step()`: the free-roam state machine (state `0x08ecd978`) | H (code) |
| `rel_story 0x08ea5dc8` / `0x08ea259c` | `world_driver_next_event() → result` / `world_driver_handle_result()` | H (code) |
| `rel_story 0x08ea5d18` / `0x08ea5c84` | `world_queue_event(a1, a2, a3)` / `world_reset_event_driver()` | H |
| `rel_story 0x08eac124` / `0x08eac0f4` | `world_get_char_table_value(char, column)` / `world_get_char_table_cell(row, column)` | H |
| `rel_story 0x08e9d594`, `0x08e9d65c`, `0x08e9d6c8` | `world_find_runtime_record(char)`, `world_set_record_flag(char, bit, on)`, `world_test_record_flag(char, bit)` | H |
| `rel_story 0x08ea5a1c`, `0x08ea5a2c`, `0x08ea56c0`, `0x08ea5684`, `0x08ea5910` | field-state getters/setters: partner, partner variant, location (1 when 0), set location, current item | H |
| `rel_story 0x08ea1ef8` | `world_handle_field_action()`: dispatch of field request 16 | H |
| `rel_story 0x08ea38b8` | `world_classify_exit() → 0 map / 1 slot 7 / 2 room / 3 slot 2` | H |
| `rel_story 0x08e9c5b0` | `world_talk_to_character(row)` | H |
| `rel_story 0x08e9c6f8`, `0x08e9f1c4` | `world_give_item_to_partner()`, `world_item_taste_column(item) → 7..56` | H |
| `rel_story 0x08ea9688` | `world_op_buy_sandwich()`: handler of opcode 50151 | H |
| `rel_story 0x08e9b55c`, `0x08ea8514`, `0x08ea855c` | `world_change_partner_points_shown(char, delta)`; handlers of 50084 / 50085 | H |
| `rel_story 0x08ea5938`, `0x08ea5b2c`, `0x08ea5bb4` | item counter −1, sandwich-seen bit, all-seen test | M |
| `rel_story 0x08e9c3e0`, `0x08e9cd0c`, `0x08e9ced8` | partner event selection, daily partner talk, location remark | M |
| `rel_story 0x08e9c868`, `0x08e9d08c`, `0x08e9d25c`, `0x08eac0c4` | chapter table: next event, lookup, row search, word (`chapter-table.md`) | H (code) |
| `rel_story 0x08e9cad0`, `0x08e9c568`, `0x08eab440`, `0x08eab40c` | `world_try_chapter_event(points, location, stage) → 0/1/2`, `world_queue_next_chapter_event()`, chapter step get / advance | H (code) |
| `rel_story 0x08e9d944`, `0x08ea563c` / `0x08ea562c`, `0x08e9c504` | `world_get_char_points(char)`, partner-talk-pending flag get / set (story block `+0x357c` word `+4`), `world_get_char_no_pairing(char)` (character table column 6) | M |
| `rel_story 0x08ea3984`, `0x08ea3ae8` | story state 46 (start of the staff roll) and the staff-roll movie choice | M |
| `rel_story 0x08eab8a4`, `0x08e9d72c`, `0x08eab500`, `0x08eac06c` | daily spot pairing, per-slot positions, fixed spots, spot table | H (code) |
| `rel_story 0x08ea0f58`, `0x08ea09c8` | NPC list to the field (request 7), player arrival cell (request 9) | H (code) |
| `rel_story 0x08ea1888`, `0x08ea1cb8` | island map open (request 2) / poll (request 29) | H (code) |
| `rel_story 0x08e9ecfc` / `0x08e9ebc8` | `world_location_to_map_id(L)` / `world_map_id_to_location(M)` | H |
| `rel_story 0x08ea05a8` | `world_change_time(mode, n)`: modes 2–7 call the calendar functions, then run the new-day and per-slot updates | H (code) |
| `rel_story 0x08eab848`, `0x08eac004` | daily seller pick (system flag 4), duel-pair partner | M |
| `rel_field 0x090ddb74`, `0x090de874`, `0x090de6b0` | field command step, command input, poll of request 16 | M |
| `rel_field 0x090d921c` | `world_field_load_map(params)`: request 3 start (map id, exit cells) | H |
| `rel_field 0x090d9c6c`, `0x090d9cc8`, `0x090d0cc8` | exit-cell test, door-cell target, laboratory special cells | H |
| `rel_field 0x090e3854`, `0x090e47d0`, `0x090e4710` | island map set-up, map → area, area → map | H |
| `0x08855ae0` / `0x08855b54` | `save_set_golden_egg_flag()` / `save_set_all_sandwiches_flag()` (`+0x1c0e9` bits 1 / 2) | H (code) |
| `0x0885aeb0` / `0x0885b8fc` | `world_get_character_category(char)` (`+0x08`) / `world_character_can_duel(char)` | H (code) |
| `rel_field 0x090d93b0`, `0x090d9948` | `world_is_cell_walkable(x, y, mode)` (code overrides, then the grid byte), `world_sample_floor_height(x, z, pos)` (triangle split) | H (documented) |
| `rel_field 0x090d934c`, `0x090d9358`, `0x090d9384` | walk grid, its vertices, its cells | H |
| `rel_field 0x090d1270`, `0x090d616c` | `world_map_id_to_name_index(M)`, `world_show_location_name()` | H / M |
| `rel_field 0x090d4850`, `0x090d4c64`, `0x090dafc8` | light mode per map and period, light colour, sky gradient | M |
| `rel_field 0x090da588`, `0x090da548`, `0x090da8a8`, `0x090dab48` | door update (documented), door object init, sliding / hinged door animation | H |
| `rel_field 0x090d1df4`, `0x090dd8dc`, `0x090e27c0`, `0x090e282c`, `0x090e1cf0` | player collision, partner free-cell search, cell occupancy get/set, pick-up at a cell | M |
| `rel_field 0x090d9e78`, `0x090dc0d8` | marker-hidden cells (maps 21, 27; low for the meaning), forest ambient sound | L / M |
| `rel_field 0x090e3614`, `0x090e3c58`, `0x090e4b7c`, `0x090e52d0` | island map step, cursor navigation, building sub-menu, area drawing | M |
| `rel_field 0x090d8494`, `0x090de430`, `0x090de378`, `0x090d0c74` | request 1 (event flag) and request 0 (scene set-up) handlers, scene parameters `0x0910c624`, field context `0x091057f0` | H (code) |
| `rel_story 0x08ea1830`, `0x08ea51e4`, `0x08ea0730`, `0x08eab35c` | send the event flag (request 1), driver event flag, send the scene set-up (request 0), its calendar words | H (code) |
| `rel_story 0x08ea56f0`, `0x08ea5718`, `0x08ea5728`, `0x08ea5738`, `0x08ea5700` | field state: previous location, player x / z / direction, set player position | H |

## Save fields found here

Additions to `docs/formats/save.md` (offsets in the game state / `DATA0`):

| Offset | Content |
| --- | --- |
| `0x0fd5c` | Player name (0x32 bytes). |
| `0x0fd8e` | Team name (100 bytes). |
| `0x0fdf4` | Duelist level − 1 (`u32`). |
| `0x0fdf8` | Duelist EXP (`u32`). |
| `0x0fdfc` | DP (`u32`; verified in PPSSPP: −200 per sandwich). |
| `0x0fe00` | `u32` increased by every positive `save_add_dp` (presumably total DP earned; low). |
| `0x10f10` | Duel-record block (`0x08854c6c`; counters capped at 999,999 / 999; `+0x494` a sub-block). |
| `0x11444`–`0x11464` | `u32` counters read by the shop rules. |
| `0x161f4`, `0x161f6`, `0x162bc` | A count < 100 and two `u16[99]` lists (states 1–3 in the second); presumably the mail list (low). |
| `0x16e12` | Partner `u16`. |
| `0x16e14` | Story block: `+0x0000` 140 runtime character records (0x5c each), `+0x3250` 0x14-byte block (`+0x10` last partner points seen), `+0x3264` event queue (0x68 bytes), `+0x32cc` field state (0x16c bytes: `+0x00` location, `+0x04` previous location, `+0x08`/`+0x0c` player position (f32), `+0x10` direction, `+0x14`/`+0x18` partner and variant, `+0x30` talk target, `+0x38`/`+0x3c` current item, `+0x40` counters, `+0x94` item counters, `+0x168`), `+0x3438` calendar (0x24 bytes), `+0x345c` field save block (0xa8 bytes; `+0x1c` the 140-byte daily pairing order), `+0x3504`, `+0x3528`, `+0x3570`, `+0x357c`, `+0x3584`, `+0x3590` other blocks registered by the story init, `+0x35b0` 50-bit sandwich-seen set, `+0x35b8` second runtime-record pointer, `+0x42d8` flags. |
| `0x1bf8c` | 174 × 2 bytes: per character-table-row flags. |
| `0x1c0e8`–`0x1c0ea` | Single-bit progress flags (`0x08855660`–`0x08855ddc`), several used by the shop rules. `0x1c0e9` bit 1: a golden-egg sandwich was bought (shop pack 43); bit 2: all 50 sandwich kinds seen. |

## Function families named in the 2026-10-31 round

Basis and method: `system.md`, same section. 764 new `world` names.

- `BOOT.BIN` `character_table` (41): accessors of the character table.
- `rel_field` (219): the module is a set of components with init, reset, shutdown, update and draw, called from the lists `0x090d88ec`, `0x090d89e4`, `0x090d8968`; frame loop update `0x090d8098`, draw `0x090d8188`. Families: `field_resources` 36 (field heap `0x780000`, asynchronous load queue, fixed and pooled resources of kinds 0–8), `island_map` 23, `field_player` 17, `field_npcs` 17, `field_map` 16, `sandwich_roulette` 14 (request 25, `goldegg_pan` model), `field_requests` 13 (handlers without a direct caller, matched to requests 7, 8, 9, 19, 22, 23 and 25 by behaviour; not yet checked against the request table `+0x2df0c`), `overhead_icons` 12, `field_pickups` 11, `field_characters` 10, `field_draw_list` 8 (122 entries of `0x50` bytes at `0x098971c0`, sorted by view depth with `qsort`), `field_partner` 8, `field_debug` 4 (a debug entry with map select and `save_add_dp(99999)`, M). Pick-ups write occupancy value 4 into the cell grid; `field-maps.md` lists only 3 and 5.
- `rel_story` (198): `duel_setup` 35 (set-up block `0x08ecdd50`, duel request `0x08ece428`), `field_state` 21 (`0x08ece52c`), `record_getters` 20 and `record_setters` 11 (runtime record `+0x5c`), `map_pickups` 14, `scene_ctx` 12 (story block `+0x3250`), `story_states` 10, `story_scene` 10, `runtime_records` 10, `overlays` 8, `npc_record_getters` 8.

### Field request table (checked 2026-10-31, round 2)

The finding of the round above, that the `field_requests` handlers were matched to requests "by behaviour" and not against the table, is settled: `rel_field.prx` `+0x2df0c` holds 33 entries of three module-relative words `{start, poll, unused (0)}` (runtime = `0x090ced00` + word), read from the module file. Most poll handlers and nine start handlers had no function in Ghidra (only data references); they are created and named now (`field_request_polls`, `field_requests`). Every poll is "busy flag == 0" (18 and 25 also return a result word).

| # | Start | Meaning (story side in `story.md`) |
| --- | --- | --- |
| 0 | `world_field_req_scene_setup` | scene parameters; busy until `world_field_on_ui_resource_loaded` (`0x090dee74`, formerly `world_field_req_bind_ui`: it is the resource-load callback, not a request) |
| 1 | `world_field_req_set_event_mode` | event mode, command bar |
| 2 | `world_field_req_island_map` | island map |
| 3 | `world_field_load_map` | map and exit cells (`field-maps.md`) |
| 4, 5 | `world_field_req_release_map`, `world_field_req_release_character_models` | release pools |
| 6 | `world_spawn_pickups` | pick-ups |
| 7, 8 | `world_field_req_npc_list`, `world_field_req_update_npc` | NPCs (the earlier matching was right) |
| 9 | `world_field_req_place_player_at` (`0x090de508`) | jumps into `world_field_req_place_player` (`0x090df2ec`), so that name and its "request 9" basis stand |
| 10 | `world_field_req_set_partner` | partner follower |
| 11–14 | `world_field_req_preload_portraits`, `dialogue_field_req_release_portraits`, `dialogue_field_req_show_portraits`, `dialogue_field_req_set_portrait_expressions` | portraits |
| 15 | `dialogue_field_req_close_talk_windows` (`0x090cf980`, M) | `close_talk`/`close_talk_of` |
| 16 | `world_field_req_begin_walk` | free walk (poll `world_field_poll_action`) |
| 17, 18 | `dialogue_field_req_talk_line`, `dialogue_field_req_choice_menu` | talk line, choice menu (poll returns the option) |
| 19 | `ui_field_req_picture` | picture |
| 20, 21 | `world_field_req_camera_shake`, `world_field_req_stop_camera_shake` | camera shake on/off |
| 22 | `world_field_req_fade` | fade (1 in, 0 out; `dialogue.md`) |
| 23 | `ui_field_req_show_card_get` (jumps to `ui_field_show_card_get`) | `give_card` |
| 24 | `ui_field_req_dp_change` | `dp_add`/`dp_sub` |
| 25 | `world_field_req_buy_sandwich` (M) | `buy_sandwich` (command state `0x11`, the sandwich roulette; poll returns the item) |
| 26 | `world_field_req_hud_marker` | `hud_marker` |
| 27 | `world_field_req_store_param_27` | stores a word at `0x09106b18`; meaning open |
| 28 | `ui_field_req_partner_points_anim` (jumps to `ui_field_req_set_partner_icon_anim`) | `partner_points_add` mood animation; so `0x090d60b8` is the request-28 body and keeps its name |
| 29 | `world_island_begin_session` | island session (poll `world_island_poll_result`) |
| 30 | `world_field_req_30` | sets `0x09899e10`/`0x09899e0c`; meaning open |
| 31, 32 | `world_field_req_start_field`, `world_field_req_end_field` | start/end the field |

## Round 2 of the 2026-10-31 naming

Method as in the first round (`system.md`): the still-unnamed functions were re-dumped from Ghidra with the current names, read in packs with full bodies (up to 160 lines), and named H/M with a basis in `re/names*.csv` under "round 2". 94 new `world` names: the 26 `rel_story` sub-module states (`dialogue.md`), the `rel_field` request handlers (table above), story globals and field-state accessors (`+0x160`–`+0x168`).

## Documented functions

The functions of this group that reached the `documented` stage in the 2026-10-31 documentation round (prototype, purpose, return value, side effects and callers, read from the decompilation) are listed in [`functions/world.md`](functions/world.md), extended in the 2026-11-03 round.

## Functions documented in the 2026-11-03 round (work packages 6-7)

Method: every still-undocumented `world` function (`rel_field`, `rel_story`, two in `BOOT.BIN`) was re-dumped from Ghidra with the current names and read in full, one row per function. Full rows: [`functions/world.md`](functions/world.md).

### Findings from rel_field

Static reading of the Ghidra decompilation only. Addresses are runtime (`rel_field` base `0x090ced00`). Confidence: H high (code read directly), M medium, L low.

#### Module frame and request plumbing

- `world_field_init_module` clears the request busy words `0x09106b90`–`0x09106bc7` and also clears the **third word of each field request table entry** (`0x090fcc14 + 12·n` = `rel_field +0x2df0c + 8`). So the third word, documented as "0 in all 33 entries; not read", is runtime state reset at init (H for the write; its readers were not in this batch).
- Frame order (`world_field_update`, only while `0x09106bb4` is set): DP display, load queue, message window, camera shake, island map, map, forest ambience (only when `0x09106bbc` is 0), pick-ups, NPCs, command state machine, portraits, talk, day banner, picture, save dialog, busy-flag clean-up, then field context `+0x00` (frame counter) += 1. Draw order (`world_field_draw`): fade (layer 6), message window, 3D scene begin, island, map, pick-up draw entries, DP display, field UI (player, partner, HUD, menus, PDA, roulette), picture, portraits, NPC draw entries, sorted object list, talk windows, day banner, save dialog (H).
- Fade (request 22): busy `0x09106ba0`, direction `0x09106bc0`; a fade-in sets the draw-enable word `0x09106bb8`, the end of a fade-out clears it, so the field stops drawing after a fade-out (H).
- Field context (`world_get_field_context`, `0x091057f0`): `+0x00` frame counter, `+0x04` NPC wandering allowed (1 only in command state 1), `+0x08` current speaker index for portraits, `+0x14` event flag, `+0x18` partner row (request 10) (H).
- Debug entry `world_field_debug_main`: map menu, `save_add_dp(99999)`, plays a 9-entry request script from `0x090f3620`; only a button press leaves it (M for the purpose).

#### Command state machine (`world_field_command_step`, state `0x0910c648`)

Command block `0x0910c5f0` (`0x8c` bytes): `+0x0c` walk flag (`0x0910c5fc`, set by request 16, cleared to end the walk), `+0x10` roulette active (`0x0910c600`), `+0x18` action code (`0x0910c608`), `+0x1c` talk target row at walk end (`0x0910c60c`), `+0x20` door target map (`0x0910c610`), `+0x24`/`+0x28` roulette arguments, `+0x2c` roulette result item, `+0x40` PDA event mode (`0x0910c630`), `+0x44` get-callback, `+0x58` state, `+0x5c` current talk target (`0x0910c64c`, −1 none), `+0x78` PDA kept flag (`0x0910c668`), `+0x7c` PDA reopen flag, `+0x88` command bar mask.

| State | Meaning | Next |
| --- | --- | --- |
| 0 | enable input, restore turned NPC | 1 |
| 1 | free walk, `world_field_read_command_input` | 2, 4, 7, 0xb, 0xc, 0xf, 0x13 |
| 2 / 3 | message box `field_strtbl` 126 | yes → 0x13 action 8; no/cancel → 0 |
| 4 / 5 | message box entry 128 | yes → 0x13 action **1**; no → 0 |
| 6 | wait for auto-walk | 0 |
| 7 / 8 | action menu (`ui_field_step_action_menu` writes state and action) | — |
| 9 / 10 | "no one in reach" (entry 122 for action 3, 124 for action 2) | 0 |
| 0xb / 0xc | PDA mode 0 / step: results 3–13 → actions 4, 6, 7, 14, 11, 12, 13, 15, 8, 18 (+reopen PDA mode 6 at next walk), 16; result 1 → 0 | 0x13 |
| 0xd / 0xe | event item get | (poll) |
| 0xf / 0x10 | card get (pick-up) | (poll) |
| 0x11 / 0x12 | sandwich roulette (request 25, outside a walk) | result in `0x0910c61c` |
| 0x13 | end walk: talk/duel turn NPC and player to each other, clear walk flag | request 16 poll returns |

Input mapping (`world_field_read_command_input`; PSP pad bits): holding R shows command page 0 (results 0 talk → action 2, 1 duel → action 3, 2 → advance-time prompt, 3 → prompt 128 → action 1; event mode enables only 0 and 1); holding L shows page 1 (4 → action 5, 5 → action 18, 6/7 → PDA modes 4/5; event mode disables 5); triangle = talk (or laboratory special cell → action 9/10); confirm = action menu; square = PDA. Cell triggers: exit cell → action 0, door cell on maps 37/12 → action 17, pick-up → state 0xf (H).

Request 16 poll result (`world_field_poll_action`): `[0]` action, `[1]`/`[2]` player **position as raw f32** (not cells), `[3]` direction, `[4+4i]` per loaded NPC `{row, cell x, cell y, direction}`, `[0x84]` NPC count, `[0x85]` talk target row, `[0x86]` door target map (H).

#### Field characters

- **Character object** (player `0x0910c690`, partner `0x0910c540`, first `0xa0` bytes of NPC slots): `+0x00` character-table row, `+0x04`/`+0x08` sprite resources (odd / even directions), `+0x0c` sprite kind (kind 1 draws only odd directions), `+0x10` position f32×3, `+0x1c` move state (0 idle, 1 walking), `+0x20` direction 0–7, `+0x24` walk frame 0–5 (advances every 3 field frames, 2 when running), `+0x28` motion vector, `+0x40` 4×4 matrix, `+0x80` visible, `+0x84` overhead icon pointer, `+0x88` run flag, `+0x8c` "extra object" flag (drawn in the last pass), `+0x90` billboard / placeholder flag (H for offsets, M for names).
- **Direction values** (answers the open question in `field-maps.md`): from the d-pad in `world_read_player_move_input`: 0 down, 1 down-left, 2 left, 3 up-left, 4 up, 5 up-right, 6 right, 7 down-right (screen directions; vectors at `0x090f38b4` rotated by the camera yaw constant `0x090f3928`) (H).
- **Load mode** of `world_init_character_object` / `world_field_load_character_resource`: 0 player (sprites always resident as field UI resources 0x12/0x13), 1 partner (single-entry pools 2/3), 2 NPC (pools 0/1, or shared fixed resources 9/10 for generic duellists) (H).
- **NPC slots**: 32 × `0xf0` at `0x09107020`; extra objects 80 × `0xb0` at `0x09108e20`. NPC fields beyond the object: `+0xa0` loaded, `+0xa4` load handle, `+0xa8/+0xac` home cell, `+0xb0` wander radius, `+0xb4` idle timer (90–209 frames), `+0xb8/+0xbc` current cell, `+0xc0/+0xc4` target cell, `+0xc8` walk t, `+0xcc` record word 1, `+0xd0` paused (turned to the player), `+0xd4/+0xd8` saved direction / move state, `+0xdc/+0xe0/+0xe4` three words shown in the HUD target panel, `+0xe8/+0xec` extra talk-cell list (0x14-byte entries) and count.
- **Request 7 record** (0x40 bytes): `+0x00` row, `+0x04`, `+0x08/+0x0c` home cell, `+0x10/+0x14` cell, `+0x18` visible, `+0x1c` kind (0 NPC slot, else extra object), `+0x20` wander radius, `+0x24` direction, `+0x28–+0x30` HUD words, `+0x34` overhead icon kind, `+0x38/+0x3c` extra talk cells. Request words `params[2]/[3]` = an NPC row to turn to a direction once all are loaded (H).
- While loading, an NPC is drawn as a **billboard placeholder** (`+0x90`, sprite from character-table row fields `+0x18..+0x1c`, field UI resource 0x19 + sheet); `world_check_npc_loaded` swaps to the real sprites when both resources are bound (M for the purpose, H for the flags).
- NPC wandering: random target within the wander radius of the home cell, unoccupied, walkable (mode 0), not an exit cell; the per-direction step is behind a jump table (`0x090f80cc`) Ghidra did not recover.
- **Talk target**: within 0.75 units, height difference < 1, in front of the player (best cosine with the facing vector); NPC extra talk cells count too (H).
- **Occupancy values**: 1 player footprint, 2 partner, 3 NPC, 4 pick-up; the player's collision rejects 5 (writer still not found). The grid is allocated lazily by `world_place_object_on_floor` (4 bytes per cell) (H).
- Player: running = circle held, two steps per frame; on maps 12/37 positive x motion is blocked in cell column 14, rows 11–25, for x ≥ 7.25 (H). NPC avoidance slides around the first NPC ahead and stops at a second.
- Partner follows the player's previous-frame position; far away (≥ 1) it walks straight through walls, near (0.5–1) it is clipped and slides round NPCs, closer than 0.5 it stops; it always faces the player; spawn behind the player (direction + 4, then round) (H).

#### Overhead balloons (answers "does `0x090d3f54` draw the talk balloon")

`world_draw_overhead_icon` draws a 44 × 36 balloon (field UI resource 3) with a 24 × 24 animated icon above a character; it is suppressed on the marker-hidden cells of maps 21 and 27. Icons are 32 slots of `0x60` at `0x09105b10` (`+0x00` active, `+0x04` owner, `+0x10` matrix, `+0x50` frame counter, `+0x54` step, `+0x58` kind 0–14, `+0x5c` custom descriptor). Kind tables: `0x090f39ac` (12 bytes: balloon index, icon u/v, offset), animation `0x090f3a60 + kind·0x40` ({frame, duration} steps, −2 loops, −1 = no icon). Uses seen: NPC icon kind from the request-7 record, kinds 0xd/0xe above the player on the laboratory special cells, and a custom descriptor for the sandwich roulette (H for the drawing, M that the kinds are talk/event markers).

#### Sandwich roulette (request 25)

State block `0x09105680` (0x170 bytes). States 0 start → 1 fade-in (30 frames, waits for the golden-egg model) → 2 spin (item changes every 3 frames, confirm stops) → 3 result text → 4 wait (golden egg: sub-states 0–4 of an egg animation) → 5 → 6 cleanup, returns item. Item list: one of five 10-item rows of the table `0x090f3704` (`rand % 5`); when the golden egg is allowed, a 1-in-10 chance adds item 50 at a random position (11 items). **The item is the one shown when the player presses confirm**, so the result is player-timed, not a hidden random pick (H). Seller voice: character 0x1b sounds 0x7a00/0x7a01, character 0x8c none, others 0x79ed/0x79ee.

#### Map

- **Map sections**: a map can have two meshes (index 2, `M` 3, the store); the player's cell x selects the visible section (`world_get_map_section`); a change starts a 30-frame crossfade that renders the old section to a 256 × 256 texture at VRAM `+0x164000` and fades it out (H).
- **Door table `+0x08`** is read: `world_draw_door_models` draws a door only when its `+0x08` equals the current section (all doors when sections are off). Correction to `field-tables.md` ("not read by the door code") (H).
- Door object (`0x60` bytes at `0x09106c10`): `+0x00` door-table entry, `+0x04` model, `+0x10` matrix, `+0x50` state (0 open, 1 opening, 2 closed, 3 closing), `+0x54` t. Door sounds: maps 12/37 hinged open 0x7a50 / close 0x7a51, sliding 0x7a52 / 0x7a53; maps 2/3 0x7a54 / 0x7a55 (H).
- `world_bind_map_archive` subtracts walk-grid vertex 0 from every grid vertex in place and stores it at `0x09106fe4` (the "field subtracts vertex 0" rule) (H).
- Sky gradient is drawn only where the stencil is 0 (behind the map) (H).
- Ambient loops per map: listed in the `world_play_map_ambient_sounds` row; rooms and the dining hall get 0x7a4b only at midnight, at volume 0x60 (H).

#### Resources

- Field heap 0x780000 bytes at `0x0910cca0`. Fixed resources: 11 entries of `0x2c` at `0x090fdb3c` (`+0x08` file name, `+0x10` buffer, `+0x14` data, `+0x18` loading, `+0x1c` callbacks, `+0x24` release request); entry 0 is `always_bri_<lang>.ehp`, entry 1 the golden-egg model, 9/10 the generic NPC sprites.
- Pooled tables (descriptors `0x090fe3cc`, 0x18 bytes; entries 0x24 bytes): pool 0/1 NPC sprite parts (10 entries each), 2/3 partner parts (1), 4 map archive (1), 5 portraits (10), 6 partner portrait (1), 7 pictures (1), 8 partner icon / mini bust-up (1). Load kind = pool + 1. File names come from `BOOT.BIN` character-table row words `+0x10` (part 0), `+0x14` (part 1), `+0x0c` (portrait). Evicted entries are those not loading and with word `+0x20` = 0 (H).
- Load queue head `0x0910cc8c` (`+0x00` kind, `+0x04` status 0 queued / 1 loaded, incremented by the read callback `world_field_on_archive_read`, `+0x18` completion callback); a release requested during a load is honoured on completion (H).

#### Island map (`0x09899988` loaded, state `0x0989998c`)

States: 1 navigate, 2 cursor move animation, 3 building sub-menu, 4 chosen (result `{0, area_to_map(area, sub-point)}`, busy `0x0989994c` cleared). **Cancel does not cancel**: it moves the cursor back to the start area; the field side always writes 0 in the first result word (H). Neighbours: with no area disabled (or only the laboratory, mask 0x800) the cursor uses a hand-made neighbour table `0x090f8610` (two 8-byte bit-packed records per area); only other masks use the 45/60/75° cone search (correction to `field-maps.md`, which presents the cone as the only rule) (H). Preview pictures: 17 rectangles of 0x66 × 0x53 in `bm_parts.gim` at u/v pairs `0x090f86d0` (areas 0–11, building sub-points 12–16) (partly answers the `bm_parts.gim` open question). Area markers use `bm_arrow11`, the cursor `bm_arrow12`, the chosen area `bm_arrow13`; `bm_arrow14` is not referenced in this batch. Place-name indices per area: `world_island_get_area_name_index`.

#### Character drawing

Generic characters: 51 × 84 cells in a 512 × 256 sheet, split at row 61 into an upper and a lower quad (lower drawn nearer the camera); cell tables `0x090f8984` (idle) / `0x090f898c` (walking), 7 frames per direction pair. Model-entry characters: two screen-space parts, part 0 a 51 × 50 cell chosen by the model id (`id % 10`: 5 rows × 2 halves), part 1 a 51 × 64 cell from the animation table `0x090f8a64/0x090f8a6c`, five drawn directions with 5–7 mirrored, per-frame vertical offset `0x090f8b80` (M for the reading of "head/body").

#### Name mismatches

- `world_get_npc_event_key`: returns the NPC words `+0xdc/+0xe0/+0xe4`, used only for the HUD target panel; no evidence they are an event key (L for the current name).
- `world_clip_player_motion`: also used for the partner, not only the player.
- `world_island_draw_menu_text` and `dialogue_draw_text_to_screen_edge`: bodies not decompiled (skipped).
- `world_check_npc_loaded`: also completes field request 7 (busy word and the turned NPC).

#### Open questions (rel_field)
- Who writes occupancy value 5, and what the pool-entry word `+0x20` (eviction lock) is.
- The meaning of the HUD words `+0xdc/+0xe0/+0xe4` from the request-7 record, and of NPC `+0xcc`.
- The NPC wander step (jump table `0x090f80cc`) and the analogue-stick word at pad `+0x18` used by the island map.
- Whether `world_clip_player_motion` reads the fifth value its callers pass (run flag / 0); the decompilation shows four parameters.
- `world_draw_object_list` disables texturing while R is held (pad bit 0x200) — intentional or debug leftover.
- Field action 1 (prompt 128 confirmed) is not in the `world.md` action table; its story-side handling needs checking.
- `field-maps.md` says pick-ups end the walk with "field action 15"; in this code a pick-up enters command **state** 0xf (card get) and action 15 is PDA result 10. Needs reconciliation.

### Findings from rel_story

All addresses are runtime addresses (`rel_story` base `0x08e9aa00`). Basis: the Ghidra decompilations of this batch; confidence high unless marked.

#### Story block sub-blocks (answers to `story-runtime.md` open questions)

`world_story_init` (`0x08e9f3ac`) binds every sub-block of the story block (`save_get_story_block()`, `S + 0x16e14`) in one place. This names the owners of the blocks that `story-runtime.md` lists as "content unknown":

| Story block offset | Bound by | Content |
| --- | --- | --- |
| `+0x0000` / `+0x35b8` | `world_bind_runtime_records(records, seen)` (`0x08ecd964` / `0x08ecd968`) | Runtime records / **seen-recipe set** (below) |
| `+0x3250` | `world_bind_scene_ctx` | Scene context (`+0x00` word set by field actions and the tutorial list, `+0x08` word sent with field request 31, `+0x10` last partner points shown) |
| `+0x3264` | `world_bind_event_queue` | Event queue |
| `+0x32cc`, `+0x35b0` | `world_bind_field_state(state, sandwich_bits)` | Field state, sandwich-seen bits |
| `+0x3438`, `+0x345c`, `+0x42d8` | `world_set_calendar_blocks` | Calendar, field save block, flag block |
| `+0x3504` | `dialogue_bind_event_state` | Event state block (dialogue) |
| `+0x3528` | `world_bind_duel_request` | **Duel request block** `*(0x08ece428)`, `0x48` bytes (below) |
| `+0x3570` | `world_bind_story_block_3570` | Written by opcode 50141 (`dialogue_op_set_block_3570_50141`); content still open |
| `+0x357c` | `world_bind_partner_talk_block` | Partner talk pending (word `+4`) |
| `+0x3584` | `audio_bind_bgm_state` | **BGM state** (audio) |
| `+0x3590` | `world_bind_pickup_taken_bits` | **Pick-up taken set**: 256 bits, bit `id − 1` (`world_set_pickup_taken` `0x08e9b028`, `world_is_pickup_taken` `0x08e9b0b4`) |

Correction: `story-runtime.md` gives the `+0x3590` accessors as `rel_story +0x644` (set/clear) and `+0x6b4` (test). `+0x6b4` is `world_is_pickup_taken`; the setter starts at `+0x628` (`0x08e9b028`); `+0x644` is inside it.

**Seen-recipe set** (story block `+0x35b8`, 140 × `0x18` bytes, sorted by character): `+0x00 u32` character id, `+0x04 u16[10]` recipes the player has seen this character use (0 = empty slot). Filled by `world_record_seen_recipe` when a story duel starts (`world_prepare_story_duel`), read by `world_is_recipe_seen` and `world_get_seen_deck_level` (deck level shown in the NPC list, 0 for an unseen recipe; also used to pick the `(301, 7, n)` duel-result record). `world_reset_runtime_records` writes the ids. (H.)

`world_clear_calendar_blocks` clears the field save block (`0xa8`) and the calendar (`0x24`) but **not** the flag block `+0x42d8`, so system flags 65–128 and story flags 129–192 survive a new story. `world_story_init` tests system flag `0x1f` right after that clear (new-game path); since flag `0x1f` lives in the cleared field save block, the "restart" branch (location `0xe`) looks unreachable from that path (M; possibly reached when the clears are skipped, not seen).

#### Story flags use bit `n & 31`, not `n − 1` (correction)

`world_set_story_flag` / `world_test_story_flag` use bit `flag & 0x1f` of the selected word (flags 1–0x20 → field save block `+0x0c`, 0x21–0x40 → `+0x10`, 0x81–0xa0 → flag block `+0x00`, 0xa1–0xc0 → `+0x04`). So story flag 1 is bit 1, flag 31 bit 31 and flag 32 bit 0 of the first word (likewise 33 → bit 1 … 64 → bit 0 of the second). The **system** flags (`world_test_system_flag`) use bit `flag − 1`. `story-runtime.md` and `world.md` say "bit n − 1" for both; that is right only for the system flags. A save reader must use `n & 31` for story flags. (H.)

#### Character info table (`0x08ec9134`, 140 × `0x84` bytes, `.bss`)

`+0x00 u32` character id (sorted ascending by `world_bind_runtime_records`, binary-searched by `world_find_char_info_entry`); `+0x04` UTF-16 string, up to `0x80` bytes: the name of the character's current deck recipe, or system-message line 1 when the player has not seen it (`world_update_npc_deck_indices`). `world_get_char_info_payload` returns `+0x04`; it is sent to the field in the NPC list and with `npc_appear`. (H.)

#### Map card pick-ups

- Static table `0x08eb4130`: 20-byte entries `{u32 id, u32 location, u32 x, u32 y, u32 card}`, ended by `id = −1`.
- Active list `0x08ec90a4`: 8 × 16 bytes `{id, card, x, y}`, rebuilt on each map entry by `world_build_map_pickup_list` for untaken entries of the location; sent with field request 6 as `{card, x, y}` triples.
- The field reports a pick-up through the callback `world_on_field_pickup(kind, id, delta, x, y)` passed in field request 0: kind 1 = card (`world_collect_map_card`: +1 copy, marks the id taken), else a counter item (`world_collect_map_counter_item`: adds `delta` to field-state counter `+0x40 + 4·id`, ids 1–20, capped below 100; the "taken" step is the empty `world_stub_noop_counter_pickup`, so counter pick-ups are not remembered). Counter pick-up slots: `0x08ece448`, 16 bytes `{id, counter, x, y}`.

#### Free-roam state machine (`0x08ecd978`)

`world_story_state_step` (one call per frame):

| State | Function | Next |
| --- | --- | --- |
| 1 | `world_state_open_island_map` | 2 |
| 2 | `world_poll_island_map` (request 29) | 3 on a choice, 12 (+ next scene mode `0xe`) on cancel |
| 3 | `world_state_sync_then_enter_location` | — |
| 4 | `world_state_enter_location` | sets `0xb` |
| 5 | `world_state_start_field_walk` | — |
| 6 | `world_handle_field_action` | see below |
| 7 | `world_state_exit_to_island_map` | — |
| 8 / 10 | `world_switch_field_overlay(0, 1 / 0)` | — |
| `0xb` | `world_driver_handle_result` | see below |
| `0xc` | `world_leave_field_scene(1)` | leaves the scene |
| `0xd` … `0x2d` | overlays 1–11: state `3n + 0xa` opens overlay `n` and moves to `3n + 0xb` (waits while the overlay's frame function runs); state `3n + 0xc` closes it and returns to 4 (overlay 1: close state `0xf`, no state change) | |
| `0x2e`, `0x30` | staff roll start, staff-roll movie | |
| `0x32` → `0x33` → `0x34` → `0xc` | `world_state_save_story_cycle`, `world_state_poll_save`, `world_state_return_from_story` | |
| other | reset to 4 | |

States 9, `0xe`, `0x11`, …, `0x2f`, `0x31` do nothing (waiting states).

**Field overlays** (table `0x08eb5128`, 12 × 16 bytes `{module id, start fn, frame fn, shutdown fn}`; loaded flags `0x08ece4e0[12]`, current `0x08ece4dc`, frame callback `0x08ece510`): only one is loaded at a time (`world_load_field_overlay` refuses while any is loaded; `world_switch_field_overlay` unloads the others first). Overlay 0 is the field module; overlays 1–11 are the library sub-modules, and their frame functions store result code `n` in `0x08ecd974`: 1 shop, 2 recipe viewer, 3 password, 4 select card, 5 conversion machine, 6 card album, 7 character list, 8 limit list, 9 tutorial list, 10 deck tutorial, 11 duel record (agrees with `dialogue.md`). The `world_state_start_*` / `update_*` / `shutdown_*` functions therefore have no direct callers: they are reached through this table (M for the word order: start/frame used by load, word 3 by unload).

#### Field action → state (answers the `world.md` open question on result codes 7 and 9–15)

`world_handle_field_action` (state 6):

| Action | Effect |
| --- | --- |
| 0 | exit cell (`world_classify_exit`) |
| 1 and unknown codes | location fix-up (0x1b → 0x1a; dorm rooms 7–15, 0x1c → 6) then the exit case (fall-through in the code) |
| 2 / 3 | talk / duel request |
| 4, 5, 6 | leave the story scene with next scene mode 2 → `system_scene_call(2, 4, 1 or 5)`; system flag 5 for 4 and 6, flag `0x11` for 6 |
| 7 | overlay 2, recipe viewer (state `0x10`) |
| 8 | time-menu reaction |
| 9 | overlay 3, password (state `0x13`) |
| 10 | overlay 5, conversion machine (state `0x19`) |
| 11 | overlay 7, character list (`0x1f`), system flag `0x37` |
| 12 | overlay 6, card album (`0x1c`), flag `0x37` |
| 13 | overlay 9, tutorial list (`0x25`), flag `0x37`, scene context word 0 = −1 |
| 14 | overlay 11, duel record (`0x2b`), flag `0x37` |
| 15 | overlay 8, limit list (`0x22`), flag `0x37` |
| 16 (`0x10`) | leave with next scene mode 1 |
| 17 (`0x11`) | door → new location |
| 18 (`0x12`) | item menu: field request 30; result 0 → walk, else leave with mode 1 |

Actions 9 and 10 come from the laboratory special cells (`world.md`), so those cells open the password machine and the conversion machine (M: overlay numbers from the code, machine reading from the result-code list). System flag `0x37` makes the next scene set-up send mode 2 (`world_send_scene_setup`).

#### Next scene mode (`world_get/set_next_scene_mode`)

Leaving (`world_exit_story_scene`): 2 → `scene_call(2, 4, sysflag 0x11 ? 5 : 1)`; 3 → `scene_call(2, 4, 2)`; 4 and `0xc` → `scene_call(2, 6, 0)` (story duel / default duel); 5 → scene `0xf`; 6 → `0x13`; 7 → `0x11`; 8 → `0x18`; 9 → `0x19`; 10 → `0x15`; 11 → `0x1c` (5–11 fill a BOOT parameter block with the partner, and for 6, 7, 11 the light period, and each sets one save progress flag e8 bit 2/4/3/6/7/5, e9 bit 6); any other → `system_scene_return(2, world_get_scene_return_value())`. Driver results `0x68`–`0x6e` select modes 5–11 (mini-games; presumably, M), `0x72` mode 8, `0x6f` (second time) mode 10.

Returning (`world_story_init`, same mode still set): 3 → state `0x22` (overlay 8, limit list, which is where mode 3 was set); 4 → back from a story duel (below); 5, 6, 7, 9, 11 → enter the location and queue `(partner a1, 10, 1)` + `(301, 8, 1)` when the BOOT result word (`0x0885bddc`) exceeds 9999 (199 for mode 6), else `(partner a1, 10, 2)` + `(301, 8, 2)`; 8 → `(301, 2, 2)` and system flag `0xc`; 10 → BGM `0xb`, all NPCs hidden while entering, `(301, 2, 0xd)`, `(partner a1, 3, 2)`, exit code `0x77`; `0xc` → state `0x25` (back to the tutorial list); `0xe` → state 1 (island map); other → state 5.

#### Back from a story duel (mode 4) — answers "which result queues (301, 7/8/9/…)"

`T = deck_get_duel_setup_tail_block()`; `T + 0x20` is the duel result, `+0x24/+0x28/+0x2c` go to field state `+0x164/+0x160/+0x162`. `world_record_duel_result(T+0x20)` updates the tally (below). Then:

- Chapter step 3 → `world_queue_next_chapter_event` (the chapter duel's aftermath), state `0xb`.
- System flag `0x36` (an event-211 record was queued): maps entry word 0 (3/2/1 → 2/1/0) to a pair of characters in table `0x08eb5110` (2 × u32 per entry) and unlocks both (`world_set_flag1_if_partner_deck(c, 0)`), then the `(211, n, 2)` follow-up.
- Otherwise, without system flag `0xc`: result 0 or 3 → `(opponent a1, 8, 5)`, `(partner a1, 7, 3)`, then the `duel_then_c` key or `(301, 7, 0x20)`; result 2 → `(opp, 8, 4)`, `(partner, 7, 2)`, `duel_then_b` or `(301, 7, 0x1f)`; any other result → `(opp, 8, 3)`, `(partner, 7, 1)`, `duel_then_a` or `(301, 7, n)` with n = seen deck level of opponent A (averaged with B in a tag duel) clamped to 1–10, plus 10 when the partner asked for the duel and 20 in a tag duel (n = 1–30). Reading result 1 as a win and 0/3 as loss/draw is a hypothesis (M: the "1" branch is the one that rates the opponent).
- With system flag `0xc` (set on return from mode 8; presumably a tournament or series, L): clears it, sets `0xd`, `score = (result is 1 ? 500 : 0) + *BOOT 0x0885bddc()`, field state `+0x168 = score` (the `TES` text token prints it); queues `(301, 2, 6)`, `(301, 2, 7…11)` by score (< 500, < 1000, < 2000, < 4000, else), `(301, 9, 1)` + `(partner, 4, 2)` when score ≥ 1000 else `(301, 9, 2)` + `(partner, 4, 3)`, for score ≥ 1000 one of `(301, 2, 0xe…0x13)` by band (1000–1099, 1100–1299, 1300–1599, 1600–1999, 2000–3999, ≥ 4000), and `(301, 2, 0xd)`.

Duel tally (field state `+0x20`, four words a, b, c, d; `world_record_duel_result`): counted only when system flag `0x12` (an opponent slot was the partner) or `0x13` (the player's side was the partner) is set; both are cleared. Result 0/3 → c + 1; result 2 → a + 1 (flag 0x12) or b + 1 (0x13); other results → b + 1 (0x12) or a + 1 (0x13). So the tally counts duels involving the partner, split by side; d is never changed here (M for the meaning).

#### Event driver (`world_driver_next_event`, `world_driver_handle_result`)

Interpreter state `0x08ece530` (`story-runtime.md`): `+0x00` header, `+0x04` pc, `+0x10` exit code. `world_queue_event` starts a record at once when none is loaded. The driver, with no record loaded, clears the finished entry and starts the next queued one (`0x65`); when the queue is empty it handles the follow-up system flags (these are **system** flags, `world.md` calls them "story flags 21–29"):

| System flag | Meaning from the code | Driver result |
| --- | --- | --- |
| `0x15` (21) | set by the day-off partner talk | `0x73`: system message `0x101` (a yes/no question), answer → `(partner a1, 9, 1)` + flag `0x16`, else `(partner a1, 9, 2)` + flag `0x17` |
| `0x16` (22) | answer 1 of `0x73` | queues `(301, 3, 1)`, `0x75` |
| `0x17` (23) | answer 2 of `0x73` | `0x76` (sleep to the next day) |
| `0x18` / `0x19` (24 / 25) | only during an event; 24 is the series-win flag of opcode 50148 | `(301, 1, 2)` + `(partner, 10, 1)` + `(301, 10, 1)` / `(partner, 10, 2)`, exit code `0x76` |
| `0x0f` / `0x10` | sandwich bought / gift question asked | `(301, 4, 1)` / `0x71` |
| `0x1c` (28) | time-menu reaction queued | exit code becomes `0x76` |
| `3` | set with flag 2 at 2000 points | system message `0x103` |
| `0x1d` (29) | a location remark was queued | `(301, 0xb, 1)` (+5 points record) when a line was shown |

Exit codes (`0x08ece540`): `0x66` → overlay 1 (shop), `0x67` → overlay 4 (select card), `0x68`–`0x6e` → scene modes 5–11, `0x6f` → first time flags 7/8 and `(301, 1, 1)`, second time `world_change_time(7)` and mode 10, `0x70` → slot 4, `+0x168 = 0`, `(301, 2, 1)`, `0x71` → gift (answer 2 returns to the walk), `0x72` → mode 8, `0x74` (default 116) → end of records, `0x75` → fade out and continue, `0x76` → sleep, `0x77` → end of event (partner story end, character list on a new game, prepared duel or island map). This answers the `story.md` "Exit codes … not traced" note for 102–112, 116, 118.

**Two-pass scripted events** (M; flow read across functions): a record that starts with `scene_map` runs its set-up opcodes first (`dialogue_run_event_script`, event state 1), returns, and the driver gets `0x74`; with event state 1 `world_driver_next_event` re-queues the same key and `world_driver_handle_result` resets the event state, syncs with the field and goes to state 4, so the location is rebuilt with the event's set-up overrides (`world_get_npc_*` read the event fields while `world_get_driver_event_flag` is set) before the main pass of the same record runs. After `(218, 4, 3)` at stage 4 step 4 the driver also queues the ending.

#### Duel set-up (`0x08ecdbc8`, `0x858` bytes) and request (`*(0x08ece428)`, `0x48` bytes)

| Address | Field |
| --- | --- |
| `0x08ecdd58` (`+0x190`) | u8 mode: 1 story duel, 2 default duel (tutorial list), 6 partner duels instead of the player |
| `0x08ecdd59` | u8 rule from `duel_rules` value (1, else 2) |
| `0x08ecdd5a` | u8 1 single, 2 tag |
| `0x08ecdd5b` | u8 duel set-up mode (from `0x08ece420`) |
| `0x08ecdd5c`, `0x08ecdd5d` | u8 rule byte, u8 (0 when `duel_rules` kind is 2, else 1) |
| `0x08ecdd6c` + `i · 0x1ac` | duellist slot `i` (0–3): `+0 u16` character (1 = the player), `+2 u16` variant, `+8 u16` recipe (`0x1d1` the player's deck, `0x1d2` the partner's own deck when system flag 2 is set; no recipe name), `+0x18` name (0x32 bytes), `+0x4a` recipe name (0x40 bytes), `+0x8c` loaded deck |

Slots: single duel 0 = player, 1 = opponent; tag duel 0 = the player's partner, 1 = opponent A, 2 = player, 3 = opponent B; mode 6: 0 = the partner, 1 = opponent. Completeness byte `0x08ece424`: bit 0 own side/opponent A, bit 1 opponent (B), bit 2 partner, bit 3 rules, bit 4 (set elsewhere, presumably `duel_then`, L); `world_is_duel_setup_complete` needs bits 0–4. Request block: `+0x00/+0x04` opponent A and variant, `+0x08/+0x0c` opponent B, `+0x44` u8 flags: bit 0 tag, bit 1 partner-requested, bit 2 "pair" flag (set when the duel was requested in free roam; then `world_prepare_story_duel` saves the opponent's duel-pair partner with `save_set_byte_16e10`).

#### Partner, chapter and daily events

Read in full and consistent with `chapter-table.md` and `world.md`. Additional details:

- `world_partner_location_remark` maps locations 1–6 to remarks 1–6 (6 only when not coming from a dorm room or location `0x1c`) and 15–25 to 7–17; other locations have none.
- Event-211 table `0x08eb4d50`: 16-byte entries `{n, trigger system flag, done system flag, location}`, ended by `n = −1`. On a map entry at the entry's location with the trigger set and done clear, `(211, n, 1)` is queued and system flag `0x36` set; after the duel (`world_story_init` mode 4) `(211, n, 2)` follows and the done flag is set. The island map can highlight the entry's location, but the gate `world_stub_return_0_island_map` always returns 0, so it never does.
- `world_talk_to_character` key: character `0x1b` → n 6 with system flag 4, 7 without; `0x1a` the opposite (so flag 4 decides which seller sells sandwiches, `world.md`).
- `world_init_character_records`: per-partner variant table `0x08eb321c` (65 × `{char, variant, column}`, default column 11) selects a column of `0x08eb2e20` (17 rows × 15 words `{character, variant per column}`); table `0x08eb4b58` (`{flag, char, variant}`, ended by three −1) re-enables characters (record flag 1 cleared) whose system flag is set and whose variant matches (the flag argument is hidden in the decompilation; M).
- `world_recompute_completion_flags` (run when a partner story ends) turns finished stories into unlocks: progress flags e9 bit 4 (≥ 1 story) and e9 bit 0 (≥ 6), story flags `0x81`, `0x86`, `0x87`, system flags `0x41`–`0x69`, and character-row bit 1 (`world_set_flag1_if_partner_deck`) for characters 2–0x7e, gated by individual finished stories (character-row bit 2 of specific characters), by progress flags e9 bit 7 / ea bit 0, or by the count (1, 2, 3, 4, 5, 7).
- NPC deck choice (`world_update_npc_deck_indices`): threshold 2000 points once progress flag e9 bit 4 is set (a story was finished), 100000 (never) before; above it most NPCs use their stronger recipe; `deck_member_has_forbidden_card(0)` forces a fixed index. Character `0x29` and character 8 variant 0 pick random recipes.

#### Staff roll and story cycle

State `0x2e` (`world_state_start_staff_roll`) → frame callbacks in `0x08ecd98c` run by `world_story_frame_callback`: `world_staff_roll_create_heap` (5 MiB `HeapMovie` pool, movie modules) → `world_staff_roll_wait_modules` (state `0x30`) → `world_play_staff_roll_movie` (next scene mode 1, state `0x32`) → `world_state_save_story_cycle` (closes all overlays, save request 5, `save_advance_story_cycle`) → `0x33` poll → `0x34` `world_state_return_from_story` → `0xc` leave. This answers the `chapter-table.md` question "what the game shows after the staff roll": a save, then the story scene ends (scene return value 1, set by `world_driver_finish_partner_story`). Whether the next partner choice follows is decided outside `rel_story` (open).

#### Name mismatches

- `world_wait_field_sync` (`0x08ea1aec`): waits for field request 7 (NPC list) and then posts and waits for request 32, which `world.md`'s request table calls `world_field_req_end_field`. It is called before every location change, so request 32 is "release the field scene", not the end of the free roam (M).
- `world_story_init`: the "new game" flag tested is bit 0 of the partner word copy (`world_copy_partner_word`); `save.md` calls bit 0 a flag, here it means "story in progress" (set by `save_set_partner_flag` at the end of the new-game path) (M).
- The Ghidra prototypes of `world_handle_field_action` (3 params) and `world_state_update_charalist` (3 params) show register garbage; both take no arguments. `dialogue_run_event_script` (2 params) also takes none.
- `world_get_npc_*` are shown returning `void`; they return the callee's value (tail calls).
- `dialogue_open_portrait_slot`: its fifth argument is compared both with window numbers and with opcode `0xc351`; it is probably the talk opcode like in `dialogue_open_talk_slot`, and the "side" reading is uncertain (L).

#### Open questions (rel_story)
- Content of story block `+0x3570` (opcode 50141) and the exact role of `0x08ecd980` beyond "first map entry after a new game" (field request 27).
- ~~The BOOT functions `0x0885bddc`, `0x0885bd4c`, … (scene parameter blocks of modes 5–11)~~: settled 2026-11-04, see "Mini-game parameter blocks" below. Still open: what each mini-game reads from its block beyond words 0 and 1, and the role of words 2–5 (-1 from the story, -1/0 from the menu).
- Duel result values in deck block `T + 0x20` (1 = win?) and the meaning of tally word d.
- System flag `0xc`/`0xd` (mode 8 return): which game mode it is.
- Whether the restart branch of `world_story_init` (location `0xe`, player position) is reachable.

## Mini-game parameter blocks (2026-11-04)

The last 15 default-named `world` functions were named and documented in the 2026-11-04 round. Thirteen of them are constant-address getters in `BOOT.BIN` (`0x0885bd4c`–`0x0885bddc`) for a data area at `0x08dc16a8`–`0x08dc1743` that carries arguments from the story (`rel_story` `world_exit_story_scene`) and from the title's mini-game menu (`rel_title` `ui_minigame_menu_launch_game`) into the mini-game scenes. Which mini-game reads which block was established by scanning every mini-game module for `jal` instructions to its import stubs of these getters (the modules import the whole `libehsys_rel`, so the import tables alone do not tell). Confidence high for the layout and the callers; medium for the "end" words, which have no reader anywhere.

| Getter | Address | Size | Scene / module | Filled by |
| --- | --- | --- | --- | --- |
| `world_get_blackjack_params` | `0x08dc16a8` | `0x18` | `0xf` `rel_blackjack` | story mode 5; menu entry 0 |
| `world_get_dodge_params` | `0x08dc16c4` | `0x1c` | `0x11` `rel_dodge` | story mode 7 (`+0x18` = light period); menu entry 1 (`+0x18` = 1) |
| `world_get_connection_params` | `0x08dc16e4` | `0x1c` | `0x13` `rel_connection` (4 call sites) | story mode 6 (`+0x18` = light period); menu entry 2 |
| `world_get_underground_params` | `0x08dc1704` | 4 | `0x15` `rel_underground` (2 call sites) | menu entry 4 stores 0; story mode 10 leaves it |
| `world_get_reversi_params` | `0x08dc170c` | `0x18` | `0x19` `rel_reversi` | story mode 9; menu entry 5 |
| `world_get_throw_params` | `0x08dc1728` | `0x14` | `0x1c` `rel_throw`, also `rel_throw_starter` | story mode 0xb; menu entry 6 (`+0x10` = 1) |
| `world_get_minigame_score` | `0x08dc1740` | 4 | every mini-game module (blackjack, dodge, connection, underground, quiz, reversi, throw) | the mini-game; `ui_mini_result_apply_score` stores the score; `world_story_init` reads it on return (score > 9999, or > 199 for mode 6, picks which partner event pair is queued) |

Words `+0x00`/`+0x04` of each block are the opponent character and its variant (from the story: the partner; from the menu: the chosen character). Each block is followed by one word with its own getter (`world_get_<game>_params_end`: `0x0885bd58`, `…bd70`, `…bd88`, `…bda0`, `…bdb8`, `…bdd0`), which nothing calls in `BOOT.BIN`, in the Ghidra-imported modules or in the mini-game modules.

In `rel_field`: `world_field_debug_line_to_location` (`0x090cf0b8`) maps the debug map-menu line 0–0x1d to a location id through the jump table at module `+0x24968` (each case loads its constant in a branch delay slot, so Ghidra shows empty cases; read from the disassembly); `world_get_map_variant_for_period` (`0x090d0c80`) maps light period 1 → 0, 2 → 1, 3 and 4 → 2 (else 0), the map variant whose group mask `world_bind_map_archive` applies to every map mesh.

## Open questions

- Field requests 27 and 30 (table above).
- The meaning of the field result codes 7 and 9–15 (other game modes). (The island-map list is the set of disabled destinations, `field-maps.md`.)
- Where the item menu's counts live: the counters at field state `+0x94` are only decremented in `rel_story`; the field module's Item menu (and the event items 101–104, bandanna, barrette, hat, autograph) was not read. PPSSPP (Session C): buying a sandwich and giving or eating it never writes them (an eaten sandwich gives a card at once); what the menu counts is still open.
- Which driver result queues `(301, 8/9/10/11, …)` (duel win/loss, events) and the exact role of the story flags 21–29 in `world_driver_next_event`.
- The character-table bytes `+0x44..+0x74` in `BOOT.BIN` (no caller found; not gifts).
- The source of the shop value `*(0x090faa70) >> 4` (packs 9–14), the meaning of the save counters `+0x11444…`, and of `0x08836e10()`. (Character-row flag bit 2 = partner story finished, above.)
- The exact EXP table (`0x08855e08` was not read in full) and the month/date mapping of calendar `+0x08`/`+0x20`.
- Confirmed in PPSSPP (Session C): the pairing (neighbouring spots, weekly), the gift points, the partner word, DP. Answered from the code: flag 2 is cleared on paired records ("Daily schedule"), and `save_add_dp` has no second argument. Record `+0x58` (6 and 1 in PPSSPP) is the day index of the last per-slot update. The low 4 bits of the partner word (3 for Jaden) are a flag (bit 0) and the story cycle (bits 1–3; `save.md`, "Partner word").
