# Story runtime state (`rel_story` story block, calendar tables, event VM, field requests)

Layouts of the free-roam state that `rel_story.prx` keeps in the saved **story block** (game state `+0x16e14`, `0x42e8` bytes, `save.md`) and of the small tables and globals around it. Behaviour (pairing, schedule, event driver, gifts) is in [`docs/subsystems/world.md`](../subsystems/world.md); this document gives the byte layouts. All values little-endian. Addresses: `rel_story` runtime base `0x08e9aa00`, `rel_field` `0x090ced00` (`modules.md`); "`+0x…`" after a module name is the unrelocated module offset. "S" is the game state (`save_get_state()`, `save.md`), so story block offset `b` is at `S + 0x16e14 + b` and at `DATA0` offset `0x16e14 + b`.

Confidence: H high (code, and for the rows marked "verified" a PPSSPP check), M medium, L low, — unknown content. Basis "code" means the loads and stores were read in the disassembly (capstone over `rel_story.prx` / `rel_field.prx`, 2026-10-31) or in the documented accessors (`re/documented-rel_story.tsv`, `docs/subsystems/functions/world.md`).

## Story block (`save` `+0x16e14`, `0x42e8` bytes)

`save_get_story_block()` (`0x08857c5c`) returns `S + 0x16e14`. The story init (`world_story_init`, `rel_story` `0x08e9f3ac`) hands sub-blocks to their owners (`world_bind_runtime_records` `0x08e9d3e8`, `world_set_calendar_blocks` `0x08eaabd8`, `world_bind_field_state` `0x08ea565c`, and the per-block clear functions named below), which keep the pointers in module globals. Every sub-block is reached only through those pointers. The block is saved with the rest of the state, so all of it persists.

| Offset | Size | Content | Pointer global | Conf. | Basis |
| --- | --- | --- | --- | --- | --- |
| `+0x0000` | 140 × `0x5c` | Runtime character records (below) | `0x08ecd964` | H | `world_bind_runtime_records`; verified (C2, E7) |
| `+0x3250` | `0x14` | Scene context block (`scene_ctx` accessors); `+0x10` = the partner points last shown | — | M | cleared by `rel_story +0x748` |
| `+0x3264` | `0x68` | Event queue (below) | `0x08ecea48` | H | `world_queue_event`, `world_driver_next_event` |
| `+0x32cc` | `0x16c` | Field state (below) | `0x08ece52c` | H | `world_bind_field_state`, `world_clear_field_state`; verified (E11) |
| `+0x3438` | `0x24` | Calendar, 9 `u32` (layout in `world.md`, "Calendar and time of day") | `0x08ecea68` | H | `world_update_calendar`; verified (C1) |
| `+0x345c` | `0xa8` | Field save block (below) | `0x08ecea64` | H | `world_set_calendar_blocks`; verified (E13) |
| `+0x3504` | `0x20` | Block cleared by `rel_story +0xa65c`; content unknown | — | M (bounds) | clear routine size |
| `+0x3524` | 4 | **Unknown**: no clear routine or access covers it | — | — | — |
| `+0x3528` | `0x48` | Block cleared by `rel_story +0x9784`; content unknown | — | M (bounds) | clear routine size |
| `+0x3570` | `0xc` | Block cleared by `rel_story +0xa958`; content unknown | — | M (bounds) | clear routine size |
| `+0x357c` | 8 | Block cleared by `rel_story +0xac18`; word `+4` = partner talk pending (`0x08ea563c` get, `0x08ea562c` set) | — | M | clear routine, accessors |
| `+0x3584` | `0xc` | Block cleared by `rel_story +0xfc20` (words 0 and 1 reset to −1); content unknown | — | M (bounds) | clear routine |
| `+0x3590` | `0x20` | 256 flag bits 1–256 (`rel_story +0x644` set/clear, `+0x6b4` test) | — | H | code |
| `+0x35b0` | 8 | Sandwich-seen set, bits 0–49 for items 1–50 (`world_set_sandwich_seen` `0x08ea5b2c`, `world_all_sandwiches_seen` `0x08ea5bb4`) | `0x08ece528` | H | code |
| `+0x35b8` | 140 × `0x18` | Second record set, sorted by the character id at `+0`, binary-searched at `rel_story +0x2b24`; fields unknown | `0x08ecd968` | M | `world_bind_runtime_records` |
| `+0x42d8` | `0x10` | Flag block (below) | — | H | `world_set_story_flag`, system-flag accessors |

The sub-blocks tile `+0x0000`–`+0x42e8` without gaps or overlaps (sums checked); the same table, as game-state offsets, is in `save.md` ("Story block"), and `tools/save.py map` holds it.

## Runtime character record (`0x5c` bytes, 140 records)

Record `i` is at story block `+0x5c·i`; the records are sorted by the character id at `+0x1c` (record index = id − 2 for characters 2–141 in every save read) and found with `world_find_runtime_record(id)` (`0x08e9d594`, binary search). The **event set-up** fields (`+0x28`–`+0x3f`, `+0x40`–`+0x50`) are written by the set-up opcodes of a scripted event (50160–50171, `story.md`) and override the free-roam fields while the event runs.

| Offset | Size | Type | Field | Conf. | Basis |
| --- | --- | --- | --- | --- | --- |
| `+0x00` | 2 | `u16` | Current location (story location id) | H | `world_get_record_location`; verified C2 |
| `+0x02` | 2 | — | Unknown (alignment; no access found) | — | — |
| `+0x04` | 4 | `u32` | Live position x (raw word; changes while the NPC walks) | M | `world_get_record_pos_x`; E7 (`2026-10-31-sessionE-S.md`) |
| `+0x08` | 4 | `u32` | Live position y | M | `world_get_record_pos_y`; E7 |
| `+0x0c` | 4 | `u32` | Cell x of the assigned spot (target cell) | H | `world_get_record_cell_x`, `world_update_npc_positions`; verified C2 |
| `+0x10` | 4 | `u32` | Cell y of the assigned spot | H | same; verified C2 |
| `+0x14` | 1 | `u8` | Facing / movement state (changes while the NPC walks) | M | `world_get_record_facing`; E7 |
| `+0x15` | 1 | `u8` | Direction 0–7 of the spot | H | `world_get_record_direction`; verified C2 |
| `+0x16` | 1 | `u8` | Byte set to 6 with record flag 8 (`world_update_npc_positions`) | M | `world_get_record_byte16` |
| `+0x17` | 1 | `u8` | Remark index (table `0x08eb4e10`), re-rolled daily by `0x08e9deac` | M | `world_get_remark` |
| `+0x18` | 2 | `u16` | Spot index into the spot table (`rel_story +0x2092c`) | H | `world_set_record_spot`; verified C2 |
| `+0x1a` | 2 | — | Unknown (alignment; no access found) | — | — |
| `+0x1c` | 4 | `u32` | Character id (sort key) | H | `world_get_record_char_id_by_index`; C2 |
| `+0x20` | 4 | `u32` | Variant | H | `world_set_record_variant` |
| `+0x24` | 4 | `u32` | Deck index within the owner, 0–9 (`deck_get_owner_recipe(char, n)`) | H | `world_update_npc_deck_indices` (`0x08e9e340`, `sw +0x24`) |
| `+0x28` | 2 | `u16` | Event set-up location | H | `world_get_record_event_location` (`lhu`/`sh`) |
| `+0x2a` | 2 | — | Unknown (alignment; no access found) | — | — |
| `+0x2c` | 4 | `u32` | Event set-up position x | H | `world_set_record_event_position` |
| `+0x30` | 4 | `u32` | Event set-up position y | H | same |
| `+0x34` | 4 | `u32` | Event set-up cell x | H | `world_get_record_event_cell_x` |
| `+0x38` | 4 | `u32` | Event set-up cell y | H | `world_get_record_event_cell_y` |
| `+0x3c` | 1 | `u8` | Event set-up facing | H | `world_set_record_event_facing` |
| `+0x3d` | 1 | `u8` | Event set-up direction | H | `world_get_record_event_direction` |
| `+0x3e` | 1 | `u8` | Event set-up counterpart of `+0x16` | M | `world_get_record_event_byte3e` |
| `+0x3f` | 1 | `u8` | Event set-up remark | H | `world_set_event_remark` |
| `+0x40` | 2 | `u16` | Event variant (65000 = none) | H | `world_set_record_event_variant` |
| `+0x42` | 2 | `u16` | Event deck (opcode `npc_deck`) | H | `world_set_event_deck` |
| `+0x44` | 2 | `u16` | Event value (opcode `npc_value_44`); meaning unknown | M | `world_set_record_event_word44` |
| `+0x46` | 3 × 2 | `u16[3]` | Duel key `{a1, a2, a3}` (`npc_event`, 50166) | H | `dialogue_op_npc_event`, `world_handle_field_action` |
| `+0x4c` | 3 × 2 | `u16[3]` | Talk key `{a1, a2, a3}` (`npc_event_b`, 50171) | H | `dialogue_op_npc_event_b`, `world_talk_to_character` |
| `+0x52` | 2 | — | Unknown (alignment; no access found) | — | — |
| `+0x54` | 4 | `u32` | Record flags, bit `n − 1` = flag `n` (1 not in free roam, 2 left without a pair, 3 absent, 4 gone, 5 excluded from pairing, 6–8 weekly random) | H (bits), M (meanings) | `world_set_record_flag`, `world_test_record_flag`; flags `0xa0` read in C2 |
| `+0x58` | 4 | `u32` | Day index of the last per-slot update | H | `world_update_npc_positions` (`sw +0x58`); verified C2 (6 and 1) |

**Verified in PPSSPP**: [`results/2026-10-27-sessionC.md`](../verification/results/2026-10-27-sessionC.md), C2: the records of characters 3 and 120 (indices 1 and 118, so index = id − 2) held location 21, cells (20, 1) / (19, 1), direction 1 and spots 334 / 335, equal to the spot-table entries; `+0x58` held the day index; characters 5 and 122 matched spots 100 and 50. [`results/2026-10-31-sessionE-S.md`](../verification/results/2026-10-31-sessionE-S.md), E7: a 60-second idle diff changed only `+0x04`/`+0x08` and `+0x14` of two records (walking NPCs), which places the live position and the state byte; E8: memory equals `DATA0` for the story block.

## Event queue (story block `+0x3264`, `0x68` bytes)

An 8-entry ring of record keys. `world_queue_event(a1, a2, a3)` (`0x08ea5d18`) scans from the ring index for the first entry whose `a1` is 0 and stores the key there; `world_driver_next_event` (`0x08ea5dc8`) takes the entry at the ring index, clears its three words, starts the record (`dialogue_find_event_record`) and advances the index (wrapping at 8) to the next non-empty entry.

| Offset | Size | Type | Field | Conf. | Basis |
| --- | --- | --- | --- | --- | --- |
| `+0x00` | 8 × 12 | `{u32 a1, u32 a2, u32 a3}[8]` | Queued record keys; `a1 = 0` marks a free entry | H | `world_queue_event` (`sw +0/+4/+8` at `0x08ea5d6c`), `world_driver_next_event` (`0x08ea5e48`–`0x08ea5e88`) |
| `+0x60` | 4 | `u32` | Ring index 0–7 of the next entry to run | H | both functions (`lw/sw +0x60`) |
| `+0x64` | 1 | `u8` (width not confirmed; `+0x65` is a separate byte) | Answer 1–5 of the last menu (`case` after `choice`, `story.md` "Menus"; the driver reads 1 = Yes for the gift question) | M | `story.md`, `world.md` "Items and gifts" |
| `+0x65` | 1 | `u8` | Series-win counter: +1 per `series_win` (50148), flag 24 at 5; cleared at event start (`0x08ea5cb0`) | H | `sb +0x65` at `0x08ea5d04`, `lbu/sb +0x65` in the 50148 handler |
| `+0x66` | 2 | — | Unknown (alignment; no access found) | — | — |

(`story.md` calls this block "the field state" in the `choice` and `series_win` rows; the pointer they use, `*(0x08ecea48)`, is this queue block, not the field state below.)

**Verified in PPSSPP**: [`results/2026-10-31-sessionE-W.md`](../verification/results/2026-10-31-sessionE-W.md) logged `world_queue_event` on every queued record with three-word keys (`(0x25, 8, 6)`, `(0x12d, 4, 1)`, `(1, 2, 6)`, `(301, 11, 1)`, the chapter keys `(201, 1, 1…3)`, `(201, 1, 21)`, `(201, 1, 22)`), and the records ran in queue order (E13). The ring memory itself was not dumped; the entry layout rests on the code and the logged keys.

## Field state (story block `+0x32cc`, `0x16c` bytes)

`*(0x08ece52c)`, cleared by `world_clear_field_state` (`0x08ea5670`) at story init. Accessors at `rel_story` `0x08ea5684`–`0x08ea5b1c` (`functions/world.md`).

| Offset | Size | Type | Field | Conf. | Basis |
| --- | --- | --- | --- | --- | --- |
| `+0x00` | 4 | `u32` | Current story location (`world_get_location` returns 1 when 0) | H | `world_set_location`; verified E11 |
| `+0x04` | 4 | `u32` | Previous location | H | `world_set_previous_location`; verified E11 |
| `+0x08` | 4 | `f32` | Player x (cell · 0.5 + 0.25) | H | `world_set_player_position`; verified E11 |
| `+0x0c` | 4 | `f32` | Player z / map y | H | same; verified E11 |
| `+0x10` | 4 | `u32` | Player direction 0–7 | H | same; verified E11 |
| `+0x14` | 4 | `u32` | Partner character id | H | `world_get_partner` (31 callers) |
| `+0x18` | 4 | `u32` | Partner variant | H | `world_get_partner_variant` |
| `+0x1c` | 4 | `u32` | Partner's character-table row (`BOOT.BIN` table) | H | `world_get_partner_row` |
| `+0x20` | 4 × 4 | `u32[4]` | Duel tally (four values stored after a duel) | M | `world_set_duel_tally`, `world_get_duel_tally` |
| `+0x30` | 4 | `s32` | Talk target (−1 none) | H | `world_set_talk_target` |
| `+0x34` | 4 | `u32` | Value tested by `if_value_34` (50016); writer not found | M (layout), — (meaning) | `world_test_field_value_34` |
| `+0x38` | 4 | `u32` | Item value set by the buy and give paths (`if_value_38`, 50082) | M | `world_set_field_value_38` |
| `+0x3c` | 4 | `u32` | Current item (sandwich 1–50) | H | `world_get_current_item`, `world_op_buy_sandwich` |
| `+0x40` | 21 × 4 | `u32[21]` | Counters, index 1–20 used (0–99; opcodes 50014, 50080); index 0 unused | H (layout) | `world_increment_counter` etc. |
| `+0x94` | 51 × 4 | `u32[51]` | Item counters, index 1–50 = item id (opcodes 50015, 50018, 50081–50083); index 0 unused; never incremented in `rel_story` | H (layout), L (meaning) | `world_decrement_item_count`; C4 saw no write |
| `+0x160` | 2 | `u16` | Value set at story init, tested by the `if_value_160` opcode | M | `world_set/get_field_state_160` |
| `+0x162` | 2 | `u16` | Value set at story init, tested by the `if_value_162` opcode | M | `world_set/get_field_state_162` |
| `+0x164` | 4 | `u32` | Value set at story init, tested by the `if_value_164` opcode | M | `world_set/get_field_state_164` |
| `+0x168` | 4 | `u32` | Value set by story init and `world_driver_handle_result`, read by the name-token expander | M | `world_set/get_field_state_168` |

The rows tile `0x16c` bytes exactly (`0x94 + 51·4 = 0x160`).

**Verified in PPSSPP**: [`results/2026-10-31-sessionE-W.md`](../verification/results/2026-10-31-sessionE-W.md), E11: after each of four map changes, `S + 0x1a0e0` held location, previous location, `f32` x, `f32` y and direction equal to the arrival table (`field-maps.md`, "Arrival cell"); [`results/2026-10-27-sessionC.md`](../verification/results/2026-10-27-sessionC.md), C4: no write to the item counters `S + 0x1a174` during buying, giving or eating.

## Field save block (story block `+0x345c`, `0xa8` bytes)

`*(0x08ecea64)`, registered by `world_set_calendar_blocks`; initialised by `world_init_calendar`.

| Offset | Size | Type | Field | Conf. | Basis |
| --- | --- | --- | --- | --- | --- |
| `+0x00` | 1 | `u8` | Story stage 1–10 | H | `world_get_story_stage`, `world_advance_story_stage`; verified E13 (`02 01` after stage 1) |
| `+0x01` | 1 | `u8` | Chapter step 1–4 | H | `world_get_chapter_step`, `world_advance_chapter_step`; verified E13 |
| `+0x02` | 1 | `u8` | Daily random 0–71: entry of the 72-entry fixed-spot table of character 139 | H | `world_roll_npc139_spot` (`0x08eab810`, `sb +2`), `world_get_fixed_npc_spot` |
| `+0x03` | 1 | — | Unknown (no access found) | — | — |
| `+0x04` | 4 | `u32` | Last day index seen (new-day detection) | H | `world_check_new_day` (`lw/sw +4`) |
| `+0x08` | 4 | — | Unknown (no access found) | — | — |
| `+0x0c` | 4 | `u32` | Story flags 1–32: bit `n & 31` (flag 32 is bit 0, flags 1–31 bits 1–31; corrected 2026-11-03, unlike the system flags, which use bit `n − 1`); flags 33–64 likewise in `+0x10` | H | `world_set_story_flag`, `world_test_story_flag` |
| `+0x10` | 4 | `u32` | Story flags 33–64 | H | same |
| `+0x14` | 4 | `u32` | System flags 1–32 | H | `0x08eaaee8` set, `0x08eaafbc` test |
| `+0x18` | 4 | `u32` | System flags 33–64 | H | same |
| `+0x1c` | 140 | `u8[140]` | Weekly pairing order (character ids, `0xff` after the last); consecutive entries are pairs | H | `world_assign_daily_spots`; verified C2 (order read at `S + 0x1a28c`) |

**Verified in PPSSPP**: [`results/2026-10-31-sessionE-W.md`](../verification/results/2026-10-31-sessionE-W.md), E13: the stage and step bytes moved `1,1 → 1,2 → 1,3 → 1,4 → 2,1` through the game's own writers; [`results/2026-10-27-sessionC.md`](../verification/results/2026-10-27-sessionC.md), C2: the order at `+0x1c` stayed the same on days 1–6 and changed on day 7 (Monday).

## Flag block (story block `+0x42d8`, `0x10` bytes)

| Offset | Size | Type | Field | Conf. | Basis |
| --- | --- | --- | --- | --- | --- |
| `+0x00` | 4 | `u32` | Story flags 129–160: bit `n & 31` (flag 160 is bit 0; corrected 2026-11-03) | H | `world_set_story_flag` / `world_test_story_flag` |
| `+0x04` | 4 | `u32` | Story flags 161–192 | H | same |
| `+0x08` | 4 | `u32` | System flags 65–96 | H | `0x08eaaee8` / `0x08eaafbc` |
| `+0x0c` | 4 | `u32` | System flags 97–128 | H | same |

Story flags 65–128 have no storage (the accessors ignore them); together with the field save block this gives story flags 1–64 and 129–192 and system flags 1–128.

## Calendar tables (`rel_story.prx`)

Read by the calendar code; static data in the module.

| Module offset | Size | Layout | Content | Conf. | Basis |
| --- | --- | --- | --- | --- | --- |
| `+0x208ec` | 8 × 8 | `{u32 period, u32 unused}[8]` indexed by the time slot 0–7 (entry 0 unused) | Light period: slots 1–2 → 0, 3–4 → 1, 5 → 2, 6 → 3, 7 → 4; the second word is 0 in every entry and never read | H | `world_update_calendar` (`0x08eac2c8`: `+0x8ec + slot·8`, first word only) |
| `+0x2e50c` | 7 × 4 | `u32[7]` | Day-off table by `(day + n) % 7`: `0,0,0,0,0,0,1` (day index 6 = Sunday) | H | `world_is_day_off` copies 7 words |
| `+0x2e528` | 10 × 4 | `s32[10]` indexed by the story stage | Points cap: entry 0 = −1, stages 1–8 = 1000·stage, stage 9 = 8000. Stage 10 would read the next table (`+0x2e550`, first word 3); not reached in normal play (low) | H | `world_get_points_cap` (`0x08eab450`: `+0x2e528 + 4·stage`); verified E13 (cap 1000 at stage 1) |

## Event interpreter state (`rel_story` `+0x33b30`, 24 bytes)

Runtime only (module `.bss`, `0x08ece530`); not saved. One instance: the interpreter runs one record at a time (`story.md`, "Run model").

| Offset | Size | Type | Field | Conf. | Basis |
| --- | --- | --- | --- | --- | --- |
| `+0x00` | 4 | ptr | Header instruction of the running record (0 = none) | M | handlers, `0xb284` |
| `+0x04` | 4 | `u32` | `pc`: instruction index within the record (reset to 1) | M | same; `world_reset_event_driver` writes 1 |
| `+0x08` | 4 | `u32` | Argument for the exit code | M | handlers |
| `+0x0c` | 4 | `u32` | Value set by opcode 50137 | L | handler |
| `+0x10` | 4 | `u32` | Exit code (set by 50108, 50139/50140, 50150, 50152, 50176; reset to 116) | M | `world_reset_event_driver` (`0x08ea5c84`) writes 116 |
| `+0x14` | 4 | `u32` | Set to 1 by `talk` / `narrate_named`; reset to 0 | M | same |

## Field request table (`rel_field.prx` `+0x2df0c`, 33 × 12 bytes)

The `rel_story` → `rel_field` request interface (`world_field_request(n, …)`). Entry `n` is three module-relative words; runtime address = `0x090ced00` + word. The table ends at `+0x2e098`, where a string table begins.

| Offset | Size | Type | Field | Conf. | Basis |
| --- | --- | --- | --- | --- | --- |
| `+0x00` | 4 | `u32` (module offset) | Start handler of request `n` | H | read from the module file; handler bodies match their requests |
| `+0x04` | 4 | `u32` (module offset) | Poll handler: returns 0 while the field is busy (18 and 25 also return a result word) | H | same |
| `+0x08` | 4 | `u32` | 0 in all 33 entries; not read | H | file |

The meaning of each request number (0 scene set-up … 32 end field) is the table in `world.md`, "Field request table". Requests 27 and 30 are open there.

## Open questions

- Content of the story sub-blocks `+0x3504`, `+0x3528`, `+0x3570`, `+0x3584` and of the second record set `+0x35b8`, and the 4 bytes at `+0x3524`.
- Field state `+0x34` (writer), `+0x160`–`+0x168` (meanings), and whether the item counters `+0x94` are the item menu's counts.
- Field save block `+0x03` and `+0x08`.
