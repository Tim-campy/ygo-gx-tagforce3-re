# Free-roam field tables (`rel_field.prx`, `rel_story.prx`, `field/*.ehp`)

Static tables that define the Duel Academy maps: which archive each map loads, its doors, its exit cells, and the field string tables. Addresses are module offsets unless stated; runtime address = base + offset (`rel_field` `0x090ced00`, `rel_story` `0x08e9aa00`), file offset = offset + `0x54`. Pointers stored in the tables are module offsets (relocated at load). All values little-endian. Tables were read from the module files; the code that reads them is named in `docs/subsystems/world.md`.

## Map ids (`rel_field.prx`)

Three numberings are involved:

1. **Story location** `L` (1–30): the argument of the story opcode `scene_map` (50158).
2. **Field map id** `M` (1–42, sparse): the value the field module keeps in `0x09106bec` (`world_get_current_map`, `0x090d9f3c`). The table below (`rel_story` `+0x1f968`) maps `L` → `M`.
3. **Map index** `i` (0–31): `world_map_id_to_index(M)` (`0x090d1144`) is a switch: `M` 1–5 → 0–4, 12–27 → 5–20, 29–32 → 21–24, 36–42 → 25–31; anything else → 0.

`i` indexes two pointer tables:

| Offset | Entries | Content |
| --- | --- | --- |
| `+0x2e798` | 32 × `u32` | Archive name `bg_NN_MM.ehp` (loaded from `field/map`, resource directory table `+0x2f72c`). |
| `+0x2e298` | 32 × 2 × `u32` | Up to two mesh members (`.tms`) to bind; the second is 0 except for index 2 (`bg_09_01_a.tms`, `bg_09_01_b.tms`). `world_bind_map_archive` also looks for `<mesh>_mask.tms`. |

Resulting map list (debug names are the bracketed strings at `+0x2d120`, kept in the module; the English place names are from `field_strtbl_mapname.bin`):

| M | i | Archive | Debug name |
| --- | --- | --- | --- |
| 1 | 0 | `bg_07_01` | `A_MAINGATE` |
| 2 | 1 | `bg_08_01` | `A_CLASS_INTERNAL` |
| 3 | 2 | `bg_09_01` (two meshes) | `A_BUYING` (store) |
| 4 | 3 | `bg_10_01` | `A_DUELAREA` |
| 5 | 4 | `bg_11_01` | `A_PRINCIPALROOM` |
| 12 | 5 | `bg_01_01` | `R_HOSTEL_OUTSIDE` (Slifer Red dorm) |
| 13–20 | 6–13 | `bg_02_01`…`bg_02_08` | `R_HOSTEL_101`…`_204` (the eight rooms; index 12, `M` 19, reuses `bg_02_01`) |
| 21 | 14 | `bg_03_01` | `R_HOSTEL_DINING` |
| 22 | 15 | `bg_04_01` | `Y_HOSTEL_OUTSIDE` (Ra Yellow) |
| 23 | 16 | `bg_05_01` | `B_HOSTEL_MAN` (Obelisk Blue boys) |
| 24 | 17 | `bg_06_01` | `B_HOSTEL_WOMEN` |
| 25 | 18 | `bg_15_01` | `E_PORT` |
| 26 | 19 | `bg_14_01` | `E_CLIFF` |
| 27 | 20 | `bg_16_01` | `E_GHOST_HOSTEL` (abandoned dorm) |
| 29 | 21 | `bg_18_01` | `E_FOREST` |
| 30 | 22 | `bg_19_01` | `E_VOLCANO` |
| 31 | 23 | `bg_20_01` | `E_BEACH` |
| 32 | 24 | `bg_21_01` | `E_LABORATORY` |
| 36 | 25 | `bg_22_01` | `E_SPECIAL_HALL` |
| 37 | 26 | `bg_01_02` | `R_HOSTEL_OUTSIDE2` |
| 38 | 27 | `bg_02_07` | `R_HOSTEL_203` |
| 39 | 28 | `bg_22_02` | `E_SPECIAL_HALL2` |
| 40 | 29 | `bg_02_09` | (no debug name) |
| 41 | 30 | `bg_23_01` | `E_LABORATORY2` |
| 42 | 31 | `bg_24_01` | `E_GENOCIDE_BRIDGE` |

Confidence: high for the table contents and the switch; the place names are labels only. The location → map mapping is confirmed by the walk grids: 99% of the scripted start and NPC cells fall on walkable cells (`hmp.md`).

### Archive members

`bg_NN_MM.ehp` holds the mesh (`.tms`, `tgm.md`), texture animation (`.tma`), node animation (`.tmt`), the walk grid (`.hmp`, `hmp.md`) and GIM textures. Members whose name contains the substring at `+0x2d144` and matches a door mesh name are bound as door objects (below).

## Door table (`rel_field.prx` `+0x25334`)

32 blocks of `0x1b8` bytes (one per map index), each 10 entries of `0x2c` bytes; empty entries are zero. Read by `world_bind_map_archive` (`0x090d9f48`), which matches `+0x00` against the archive members and copies a pointer to the entry into a 0x60-byte door object (`0x09106c10 + 0x60·n`).

| Offset | Type | Field | Conf. |
| --- | --- | --- | --- |
| `+0x00` | ptr | Mesh member name (`bg_01_01_door_a.tms`, …) | H |
| `+0x04` | u32 | Door kind: 0 (`door_a`) or 1 (`door_b`) | M |
| `+0x0c` | 3 × f32 | Position x, y, z (map coordinates before re-centring) | M |
| `+0x1c` | f32 | Rotation about y, degrees (90 in every entry) | M |
| `+0x24` | f32 | Scale or opening amount (1.0, 0.5, 0.25) | L |
| `+0x28` | u32 | **Target field map id** `M`, 0 for none | M |

Entries exist for map indices 1 (three classroom doors), 2 (store), 5 and 26 (the Slifer dorm outside, both versions: eight `door_b` with targets 13–20, the rooms 101–204, and one `door_a` with target 21, the dining hall). Basis for `+0x28`: the eight room doors carry 13–20 in the order of the upper/lower floor positions, matching the room maps.

## Exit cells (`rel_story.prx`)

Two tables, read by `world_get_exit_cells` (`0x08eab124`) and sent to the field module with request 3 (`world_send_exit_cells`, `0x08ea0860`); the field module copies at most 128 cells (`0x08ecd998`, count `0x08ecdb98`).

**Selector** (`+0x1f968`, 30 records of 9 `u16`, terminated by a zero record). `world_select_exit_group(L)` (`0x08eab224`) returns `+2` of the first record whose `+0` equals the story location `L` and whose conditions pass:

| Offset | Field |
| --- | --- |
| `+0x00` | Story location `L` |
| `+0x02` | Result: field map id `M` (also the group key below) |
| `+0x04` | If non-zero, `+0x06` must equal the story stage (`world_get_story_stage`) |
| `+0x08`, `+0x0a` | Story flag and mode: 3 = requires the flag set, 4 = requires it clear (`world_test_story_flag`) |
| `+0x0c`, `+0x0e`, `+0x10` | Second condition: a bit test on a runtime character record (`0x08e9d6c8(char, bit)`), mode at `+0x10` as above |

On the disc every record is unconditional, so the selector is a plain `L` → `M` map (1–5 → 1–5, 6–21 → 12–27, 22–25 → 29–32, 26–29 → 36–39).

**Cell groups** (`+0x1fb84`, 6-byte records `u16 key, x, y`, terminated by three zeros at `+0x208ec`): a record with `key ≠ 0` starts the group for map `key` (its `x, y` are 0); following records with `key = 0` are the cells `(x, y)` of that group. Groups exist for keys 1–39.

These are the **exit cells** of each map (high): `world_field_load_map` (`rel_field` `0x090d921c`, the request 3 handler at `+0xa51c`) copies the list, and `world_is_exit_cell` (`0x090d9c6c`) ends the walk with field action 0 when the player's cell is in it; `rel_story` then returns the player from a dorm room to the dorm outside or, elsewhere, advances one time slot and opens the island map (`docs/subsystems/world.md`, "Island map"; the "Exit from this spot?" prompt, `field_strtbl.bin` entry 128, was not traced). Layout basis: they lie on the grid border or at the door of each room (rooms 101–104: `(12, 5)`, `(12, 6)`, the right-hand column of a 13 × 8 grid; classroom: `(0, 3)`, `(0, 4)`, `(10, 0)`, `(11, 0)`, `(21, 0)`, `(22, 0)`); all are walkable. The list is sent only when `0x08ea51e4()` returns 0 (presumably "no event running", low) or the location is 7–15 or 28; otherwise an empty list is sent.

## String tables (`field/always*.ehp`)

`field/always_<region>_<lang>.ehp` (region `usa bri ger fra ita spa`, language `eng ger fra ita spa`; the module names 31 of them, including an absent `always_jpn_jpn.ehp`; but the field module itself only uses the six-entry table at `rel_field` `+0x2f2bc`, indexed by `save_get_language()` (`0x090e135c`): `always_bri_<eng eng ger fra ita spa>.ehp`, so the other region variants are unused by this code. The `bri`/`usa`/… copies of one language are byte-identical in size.) holds the field UI textures and the `strTbl`-format tables below (`u32 count`, `u32 table offset` = 12, `u32 string base`, `count` `u32` offsets from the base, UTF-16LE NUL-terminated strings; the format of `deck.md`). `always_lang_<lang>.ehp` holds only the language-dependent members; `always_zone_<region>.ehp` two region-dependent textures; `always.ehp` the six `field_strtbl_<j e f g i s>.bin`.

| Member | Resource id (`+0x2f578`) | Entries (English) | Content |
| --- | --- | --- | --- |
| `field_strtbl.bin` | 4 | 130 | Field UI: acquisition messages, the item menu (Sandwich / Eat / Item / Give / Select Item), PDA menu names and help, calendar words (AM, PM, month names May–August, weekday abbreviations), the time-advance menu, status screen labels (Duel Points, Duelist Level, GX Medals, Team Name), the field command bar (Talk, Duel, Item, Map, Friends, PDA, Save, Advance Time) and refusals ("There's no one to talk to!"). |
| `field_strtbl_item.bin` | 5 | 202 | Items: entry `k` (1–50) is the description and `50 + k` the name of item `k` (50 sandwiches, item 50 the golden-egg sandwich); entries 104–107 / 154–157 the same for four event items (101 + n / 151 + n). |
| `field_strtbl_mapname.bin` | 7 | 57 | Place names shown in the field (short names 1–17, "Duel Academy - …" forms 18–22, dorm and room names 23–50, others 51–55). |
| `event_name.bin` | 6 | — | Not in the English archive; loaded from `field/event` (resource directory `+0x2f77c`). |
| `option_msg_<l>.bin` | — | — | Options screen text. |

## Open questions

- The meaning of door `+0x24` and of the unread words `+0x08`, `+0x18`, `+0x20`.
- The island-map areas and destinations are in `docs/subsystems/world.md`; the screen coordinates at `rel_field` `0x090f85b0` and the arrow (`bm_arrow11–14`) navigation code (`0x090e3c58`) are not decoded.
- Map ids 6–11, 28, 33–35 are absent from the switch (they map to index 0, the main gate).
