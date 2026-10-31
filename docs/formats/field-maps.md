# Free-roam maps: per-location data (`rel_field.prx`, `rel_story.prx`, `field/map`, `field/big_map`)

Everything the field module uses to set up and run one Duel Academy map, beyond the archive itself: which story location loads which map, lighting and sky per time of day, exits, doors and door cells, walkability overrides, the floor-height rule, the player's arrival cell, NPC positions and the island (travel) map. Static analysis of `rel_field.prx` (base `0x090ced00`) and `rel_story.prx` (base `0x08e9aa00`) in Ghidra plus cross-checks on the disc data; nothing here was traced in PPSSPP. Module offsets as in `field-tables.md` (file offset = offset + `0x54`). The archive layout (`bg_NN_MM.ehp`), the door table and the exit-cell tables themselves are in `docs/formats/field-tables.md`; the walk grid in `docs/formats/hmp.md`.

Tool: `tools/world.py`.

```
python3 -I tools/world.py tables <USRDIR> --check                      # cross-check every table below
python3 -I tools/world.py tables <USRDIR> -o extracted/world/tables.json  # all tables as JSON (--table NAME for one)
python3 -I tools/world.py locations <USRDIR> -o extracted/world/maps --names   # one map_MM.json per field map
```

Check on the reference disc: `failing: 0`; 32 maps, 22 doors, 39 exit groups, 29 selector records, 12 island areas; 801/801 mesh texture names resolve to a GIM member of the same archive; 446 of the 513 exit cells referenced by the selector are walkable (below); 349/350 NPC spots and all fixed NPC positions are walkable. Output is game data and is written only outside the repository or under `extracted/`.

Numbers used below: **story location** `L` (0–30, the field state's location), **field map id** `M` (1–42, sparse), **map index** `i` (0–31, `world_map_id_to_index`), **light period** `p` (0–4, calendar `+0x14`; `docs/subsystems/world.md`).

## Location ↔ map

`world_location_to_map_id` (`rel_story` `0x08e9ecfc`) and `world_map_id_to_location` (`0x08e9ebc8`) are switches (high):

| `L` | `M` |
| --- | --- |
| 1–5 | 1–5 (main building: gate, classroom, store, duel area, principal's office) |
| 6–21 | 12–27 (Slifer dorm outside, its eight rooms, dining hall, Ra dorm, Obelisk dorms, port, cliff, abandoned dorm) |
| 22–25 | 29–32 (forest, volcano, beach, laboratory) |
| 26 | 36 (special hall) |
| 27, 28, 29, 30 | 39, 40, 41, 42 |
| 0 and anything else | 30 |

The inverse maps 37 and 38 (second versions of the dorm outside and of room 203) to 6 and 13; no location loads them through this switch (scripts or another path must, open question).

**Correction to earlier notes**: the selector table at `rel_story` `+0x1f968` is *not* the location → map mapping. It returns the **exit-group key** (`world_select_exit_group`), which equals `M` for locations 1–26 but is 37, 38, 39 for locations 27, 28, 29 (maps 39, 40, 41). Basis: the script set-up cells (`scene_player`, `npc_position` after `scene_map L`) fall on walkable cells for 1,214 of 1,218 positions with the switch above, but only 1,186 with the selector (all 9 positions of location 29 and 3 of location 27 fail, and location 30 has no selector record); the exit cells of group 37 (`x` = 60) fit the 64 × 64 grid of map 39, not the 33 × 46 grid of map 37.

## Map table

Per map id the tool exports: map index, archive `field/map/bg_NN_MM.ehp`, mesh members, debug name (parsed from the debug-menu string at `rel_field` `+0x2d120`, `"bg_NN_MM [NAME]\n…"`), place-name index, island area, and the per-period lighting.

**Place name**: `world_map_id_to_name_index` (`rel_field` `0x090d1270`) is a switch from `M` to an entry of `field_strtbl_mapname.bin` (field resource 7); `world_show_location_name` (`0x090d616c`) shows it on map entry (high: the 31 entries read as the expected places, for example `M` 3 → the store, 25 → the harbour). Maps 37/38/39 reuse the names of 12/19/36.

**Mesh members**: the up to two `.tms` names of `+0x2e298`; the archive also holds `<mesh>.tmt` (node animation), `<mesh>.tma` (texture animation), optionally `<mesh>_mask.tms`, the door meshes and the GIM textures. Every texture name in the meshes (`.tga` names in the TGMS texture table, `tgm.md`) resolves to the GIM member with the same stem in the same archive. Per mesh the location export lists `{member, mask, node_animation, texture_animation, textures: [{name, gim}]}`, so the port can convert the textures with `tools/gim.py` and the meshes with `tools/tgm.py`.

### Lighting and sky (`+0x28a7c`, `+0x28a34`)

`+0x28a7c`: 32 records of `0x28` bytes (by map index), each five `{u32 light_mode, u32 sky_gradient}` pairs, one per light period.

- `world_field_load_map` (`0x090d921c`) calls `world_set_light_mode(record[p].light_mode)` (`0x090d4850`, global `0x0910678c`); `world_apply_light_colour` (`0x090d4c64`) turns the mode into an ABGR colour passed to the BOOT.BIN lighting calls: 0 `0xffffeed8`, 1 `0xffffffff`, 2 `0xff5ac8ff`, 3 `0xffff8c78`, 4 `0xffbe7165` (as RGB: pale blue-white, white, orange, blue, dark blue for morning, day, sunset, night, midnight; high for the values, medium for the reading).
- `world_draw_sky_gradient` (`0x090dafc8`) takes `record[p].sky_gradient` as an index into `+0x28a34`, 6 entries of three ABGR words, and draws two full-screen quads: rows 0–136 from colour 0 to colour 1 and rows 136–272 from colour 1 to colour 2 (high for the geometry, medium that it is the background behind the mesh).
- On the disc most maps use `(0,0) (1,1) (2,2) (3,3) (4,4)`; the classroom and the store keep light mode 1 until midnight; the duel area (`M` 4), the laboratory (32), laboratory 2 (41) and the bridge (42) use gradient 5 in every period.

`p` is word 2 of field request 0 (scene set-up), filled from the calendar's light period by `world_fill_scene_calendar_params` (`rel_story` `0x08eab35c`) and stored by `world_field_req_scene_setup` (`rel_field` `0x090de430`) in the scene parameters `0x0910c624` (`world_get_scene_params`) (high).

## Doors

Table layout in `field-tables.md`. Decoded behaviour (`world_update_doors`, `0x090da588`, per frame; high for the code):

| Field | Meaning |
| --- | --- |
| `+0x0c` position | Map coordinates; the field subtracts walk-grid vertex 0 (`0x09106fe4`) like everything else. |
| `+0x18`, `+0x1c`, `+0x20` | Rotation about x, y, z in degrees (y is 90 for most doors, 0 for two classroom doors). |
| `+0x24` amount | Kind 0 (`door_a`, sliding, `world_animate_sliding_door` `0x090da8a8`): the door moves by `t · 1.5 · R(rotation)·(amount, 0, 0)`. Kind 1 (`door_b`, hinged, `world_animate_hinged_door` `0x090dab48`): yaw grows by `t · 2π · amount` (0.25 = a quarter turn). |
| `+0x28` | Target map id (informative: the door cells below do the map change). |

A door opens (`t` → 1, `t += 0.1 + 0.1·t` per frame, sound `0x090db820(kind)`) when the player is within 0.75 units of its position and closes beyond. Doors stay closed while the field event flag is set (maps 2, 12, 37) and, on maps 12/37 at light period 4 (midnight), those leading to maps 13–19 and 38. Only rooms 20 (204) and 21 (dining hall) stay reachable at midnight, which matches the walk overrides below.

## Door cells and special cells (code)

`world_get_door_cell_target` (`0x090d9cc8`): stepping on one of these cells ends the walk with field action 17 and the target map (`rel_story` turns it into a location with `world_map_id_to_location`). The action is raised only on maps 12/37.

| Maps | Cells → target `M` |
| --- | --- |
| 12, 37 | `(15, 24)` → 13, `(15, 20)` → 14, `(15, 16)` and `(15, 12)` → 40, `(13, 24)` → 17, `(13, 20)` → 18, `(13, 16)` → 19, `(13, 12)` → 20, `(13, 6)` → 21 |
| 36 | `(9, 0)`, `(10, 0)` → 39 (not acted on: the action test requires 12/37) |

`world_get_lab_special_cell` (`0x090d0cc8`): on map 32, `(32, 2)`/`(33, 2)` → kind 1 (field action 9) and `(30, 2)`/`(31, 2)` → kind 2 (action 10).

`world_is_marker_hidden_cell` (`0x090d9e78`): two cell lists (`u32 x, y` pairs), 14 cells of map 21 at `+0x28f7c` and 120 cells of map 27 at `+0x28fec`. On these cells `0x090d3f54` draws nothing over a character; elsewhere it draws a 44 × 36 sprite plus a 24 × 24 icon from the field UI texture above the character (presumably the talk/event balloon; low).

## Walkability overrides (code)

`world_is_cell_walkable(x, y, mode)` (`0x090d93b0`) returns 0 for these cells before it reads the grid byte (cells outside the grid are 0 too). Mode 0 is used for NPCs (`0x090dc2a4`) and the partner's free-cell search (`world_find_follower_cell`, `0x090dd8dc`), mode 1 for the player's collision (`world_clip_player_motion`, `0x090d1df4`). The **event flag** is field context `0x091057f0 + 0x14`, set by field request 1 (`world_field_req_set_event_mode`, `0x090d8494`) from `rel_story` `world_send_event_mode` (`0x08ea1830`, the driver's event flag `world_get_driver_event_flag`, `0x08ea51e4`); while it is set the command bar also loses entries (high for the code, medium that the flag means "an event is running").

| Maps | When | Cells |
| --- | --- | --- |
| 3 | mode 0 | `(14, 17)`, `(14, 18)` |
| 2 | mode 0, or event flag | `(1, 3)`, `(1, 4)`, `(10, 1)`, `(11, 1)`, `(21, 1)`, `(22, 1)` (next to the classroom exits) |
| 12, 37 | mode 0, or event flag | the nine door cells |
| 12, 37 | mode 1 at light period 4 | the door cells of maps 13–19 and 40: `(15, 24)`, `(15, 20)`, `(15, 16)`, `(15, 12)`, `(13, 24)`, `(13, 20)`, `(13, 16)` |

Movement also consults a per-cell occupancy word (`world_get_cell_occupant` / `world_set_cell_occupant`, a `u32` grid at `*(0x098997f0)`): NPC movement writes 3 at its cells, pick-up items write 4 at theirs (`world_update_pickups`, `rel_field` `0x090e1ba4`: `world_set_cell_occupant(x / 0.5, z / 0.5, 4)` per active slot; added 2026-10-31), the partner's free-cell search rejects 3 and the player's collision rejects 5 (meaning of 5 open). Pick-up items are 8 runtime slots of `0x60` bytes at `0x09896ec0` (`world_take_pickup_at_cell`, field action 15). Both are runtime state.

## Floor height

`world_sample_floor_height` (`0x090d9948`) answers the interpolation question of `hmp.md`: the cell is split along the diagonal from vertex `(x, y)` to `(x+1, y+1)` and the height is the plane of one triangle (rule in `hmp.md`; `WalkGrid.floor_height` in the tool). High for the structure, medium for the two BOOT.BIN vector helpers (cross and dot product, recognised from the plane formula).

## Exits

Exit cells (`field-tables.md`) are sent per location: `world_send_exit_cells` (`rel_story` `0x08ea0860`) gives the group of `world_select_exit_group(L)` for map `world_location_to_map_id(L)`, and sends an empty list while the driver's event flag is set unless `L` is 7–15 or 28. Of the 513 cells in the 29 selected groups, 446 are walkable; the others lie on blocked cells or outside the grid (for example `x` = 64 on a 64-wide grid, `(60, 30)` in group 38 for the 13 × 16 map 40) and can never trigger, because the player cannot stand there. Location 29 (map 41, laboratory 2) has no reachable exit, presumably because it is only used by events; location 30 has no selector record (medium).

## Arrival cell (code)

When no event places the player, `world_place_player_on_arrival` (`rel_story` `0x08ea09c8`) picks a cell and direction per location, centres it (`x·0.5 + 0.25`) and sends it with field request 9. "Previous" is the previous location (field state `+0x04`, `world_get_previous_location`); "previous cell" is the player's cell on the previous map (the door cell).

| `L` | Cell (x, y), direction |
| --- | --- |
| 1, 0, 29, 30, others | (45, 31), 3 |
| 2 | system flag 20 clear: (11, 2), 1; set: (8, 25), 1 |
| 3 | (31, 17), 3 |
| 4 | (46, 24), 3 |
| 5 | system flag 6 set: (8, 10), 3, and the flag is cleared; else (18, 9), 3 |
| 6 | from 28: (16, 16) if the previous cell has x 11–13, y 12–14; (16, 12) if x 11–13, y 4–6 (otherwise undefined). From 15: (16, 6); 14: (14, 12); 13: (14, 16); 12: (14, 20); 11: (14, 24); 10: (16, 12); 9: (16, 16); 8: (16, 20); 7: (17, 24); all direction 7. Else (31, 29), 3 |
| 7–12 | (11, 6), 3 |
| 13 | (9, 6), 3 |
| 14 | from 6: (11, 6), 3, unless the word `*(0x08ec9130) + 8` (read by `0x08e9b460`) is non-zero; otherwise (4, 4), 0 |
| 15 | (18, 2), 3 |
| 16 | (18, 1), 1 |
| 17 / 18 / 19 | (24, 28) / (38, 40) / (62, 10), 3 |
| 20 | (12, 1), 1 |
| 21 | (61, 31), 3 |
| 22 | (33, 61), 5 |
| 23 | (38, 44), 3 |
| 24 | (35, 47), 5 |
| 25 | (16, 2), 3 |
| 26 | from 27: (10, 2), 1; else (62, 54), 3 |
| 27 | (55, 32), 3 |
| 28 | previous cell x 14–16: y 15–17 → (11, 13), 3; y 11–13 → (11, 5), 3 (otherwise undefined) |

Every listed cell is walkable on its map (`--check`). The arrival cells sit next to the matching door cells (from room 101 = location 7 the player appears at (17, 24), right of door cell (15, 24)), which also confirms the door-cell targets (high). Room 204 (location 14) is the one room still open at midnight and the only room with a second arrival cell, (4, 4) facing 0; presumably the player's own room, entered in bed at the start of a day (low). Direction is the 0–7 value of the field state (its compass mapping is not decoded).

## NPC positions

- **Spot table** (`rel_story` `+0x2092c`, `docs/subsystems/world.md`): 350 × `{location, x, y, direction}`; the location export lists the spots whose location loads this map. 349 are walkable; spot 186 (location 16, cell (4, 25)) is not.
- **Fixed positions** (`world_get_fixed_npc_spot`, `0x08eab500`), same 16-byte records: 13 entries at `+0x2238c` for characters 127, 51, 128–136, 138, 140 (in this order); 72 entries at `+0x21f0c` for character 139, chosen by the daily random byte (field save block `+0x02`); 3 entries at `+0x2e550` for the sandwich sellers 26/27 (entry 0 or 1 by system flag 4; entry 0 when the partner is a seller) and for character 140 when the partner is a seller (entry 2, cell `x` = −1, off the map). Cells 10000 and 10001 are placeholders that `world_send_npc_list` expands into scripted multi-cell placements on locations 5 and 25 (not decoded).

## Island map

Data and code in `docs/subsystems/world.md` ("Island map"). Additions (high for the code):

- **Area positions** (`+0x298b0`): 12 × `{i32 x, i32 y}` screen pixels on the 480 × 272 screen, by area.
- **Disabled destinations**: the map-id list of field request 2 disables areas: `world_island_map_open` sets bit `area` in the mask `0x09899bd8` for each listed map (for area 4 it marks the sub-point, and the whole area only when all five are listed); disabled areas are not drawn (`world_island_draw_areas`, `0x090e52d0`) and are skipped by the cursor. So the classroom (`M` 2) that `rel_story` lists in time slots 3 and 4 is **not selectable** then (medium for the reading of the slots).
- **Highlighted map** (request word 4): a marker is drawn at the area position + (−0x11, −0x28).
- **Navigation** (`world_island_map_navigate`, `0x090e3c58`): the d-pad gives one of eight directions (`+0x2f800`, unit steps with y downwards) and the analogue stick a direction when its length is ≥ 0.5; the cursor moves to the nearest enabled area whose direction from the current one lies within ±45°, else ±60°, else ±75° (cones `+0x29b74`, radians). Confirm on area 4 opens a five-entry sub-menu (`world_island_open_building_menu`, `0x090e4b7c`) whose disabled entries come from the same list; the result is `world_island_area_to_map(area, sub-point)`.
- **Art**: one archive per light period, `field/big_map/world_<morning|day|sunset|night|midnight>.ehp` (field resources 2–6), with the background picture `bm_island.gim`, the parts sheet `bm_parts.gim`, the arrow layouts `bm_arrow11–14.ehf` (+ `.tmf`) and the effect layout `bm_efct_whole.ehf` (`tools/ehf.py`, `tools/gim.py`). Which part of `bm_parts.gim` each area uses is not decoded.

## Location export (JSON)

`world.py locations` writes one `map_MM.json` per field map. Keys:

| Key | Content |
| --- | --- |
| `map_id`, `map_index`, `locations` | `M`, `i`, the story locations that load it (or `world_map_id_to_location(M)` for 37/38) |
| `archive`, `debug_name`, `name_index`, `name` | Archive path, debug name, place-name entry (and the string with `--names`) |
| `meshes`, `door_meshes`, `textures` | Mesh members with mask/animation members and resolved textures; door mesh names; all GIM members |
| `lighting` | Per period: light mode and colour (`#rrggbbaa`), sky gradient colours |
| `walk_grid` | `.hmp` member, columns, rows, cell size 0.5, origin (vertex 0), cell rows (`#` walkable), vertex heights relative to vertex 0 (`--no-heights` leaves them out) |
| `exits` | Per location: exit group and cells |
| `doors`, `door_cells`, `walk_blocks`, `special_cells`, `marker_hidden_cells` | The tables above for this map |
| `arrival` | Per location: the arrival rules (condition, cell, direction) |
| `npc_spots`, `fixed_npc_spots` | Spot-table entries and fixed positions on this map |
| `island_area`, `ambient_sounds` | Area and sub-point on the island map; the forest's looping sound `0x7a48` on map 29, volume `factor·(18 − distance)` clamped to 0–127 from (15.75, 9.75) (`world_update_forest_ambient`, `0x090dc0d8`, factor at `+0x293c8`) |

`world.py tables` writes the same tables once for the whole game (`maps`, `doors`, `door_cells`, `walk_blocks`, `special_cells`, `marker_hidden_cells`, `exit_selector`, `exit_groups`, `arrival`, `island`, `npc_spots`, `fixed_npc_spots`, `location_to_map`, `sky_gradients`, `light_modes`, `ambient_sounds`).

## Open questions

- What loads maps 37 and 38 (no location maps to them), and what selects the second dorm version.
- The meaning of `0x08e9b460()` (arrival in room 204) and of the direction values 0–7.
- The scripted placements behind cells 10000/10001 (`world_send_npc_list`, locations 5 and 25) and the anonymous extras on locations 2 and 4.
- Which part of `bm_parts.gim` and which EHF layout each island area uses; the exact on-screen marker sprite.
- Whether `0x090d3f54` draws the talk balloon (the cell lists of maps 21 and 27 suppress it).
- PPSSPP confirmation of the door-opening distance, the midnight lock and the arrival cells.
