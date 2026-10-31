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

`rel_shop` `0x090d9264` first calls `0x090d9e5c` and then copies every pack's save state into the shop's pack table; `0x090d9e5c` (5,924 bytes) recomputes the 48 pack states with `save_set_pack_state(p, s)` (`save.md`). States: 0 not available, 1 was available but its condition no longer holds (greyed), 2 on sale, bit 2 (4) "unlocked by the story" (`set_pack_state 60000` in scripts), turned into 2 at the next visit. Rules, in order (medium; static reading of the decompilation):

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

The functions of this group that reached the `documented` stage in the 2026-10-31 documentation round (prototype, purpose, return value, side effects and callers, read from the decompilation) are listed in [`functions/world.md`](functions/world.md).

## Open questions

- Field requests 27 and 30 (table above).
- The meaning of the field result codes 7 and 9–15 (other game modes). (The island-map list is the set of disabled destinations, `field-maps.md`.)
- Where the item menu's counts live: the counters at field state `+0x94` are only decremented in `rel_story`; the field module's Item menu (and the event items 101–104, bandanna, barrette, hat, autograph) was not read. PPSSPP (Session C): buying a sandwich and giving or eating it never writes them (an eaten sandwich gives a card at once); what the menu counts is still open.
- Which driver result queues `(301, 8/9/10/11, …)` (duel win/loss, events) and the exact role of the story flags 21–29 in `world_driver_next_event`.
- The character-table bytes `+0x44..+0x74` in `BOOT.BIN` (no caller found; not gifts).
- The source of the shop value `*(0x090faa70) >> 4` (packs 9–14), the meaning of the save counters `+0x11444…`, and of `0x08836e10()`. (Character-row flag bit 2 = partner story finished, above.)
- The exact EXP table (`0x08855e08` was not read in full) and the month/date mapping of calendar `+0x08`/`+0x20`.
- Confirmed in PPSSPP (Session C): the pairing (neighbouring spots, weekly), the gift points, the partner word, DP. Answered from the code: flag 2 is cleared on paired records ("Daily schedule"), and `save_add_dp` has no second argument. Record `+0x58` (6 and 1 in PPSSPP) is the day index of the last per-slot update. The low 4 bits of the partner word (3 for Jaden) are a flag (bit 0) and the story cycle (bits 1–3; `save.md`, "Partner word").
