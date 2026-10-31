# Field walk grid (`.hmp`)

Status: `documented` (layout checked on all 31 files by `tools/world.py hmp <USRDIR>/field/map --check`, `failing: 0`; the meaning of the cell byte is medium confidence, static analysis only).

Every free-roam map archive `field/map/bg_NN_MM.ehp` holds one `bg_NN_MM.hmp` member (`bg_09_01.ehp` holds `bg_09_01_a.hmp`). It is the walk grid and floor height of the map. The field module picks it up by extension: `world_bind_map_archive` (`rel_field` `0x090d9f48`) walks the archive members and keeps the member whose extension matches the string at `0x090fd168`.

All integers little-endian.

## Layout

| Offset | Size | Field |
| --- | --- | --- |
| `0x00` | 2 | `vertex_count` = `vertex_columns × vertex_rows` |
| `0x02` | 2 | `vertex_columns` (`columns + 1`) |
| `0x04` | 2 | `vertex_rows` (`rows + 1`) |
| `0x06` | 2 | `cell_count` = `columns × rows` |
| `0x08` | 2 | `columns` |
| `0x0a` | 2 | `rows` |
| `0x0c` | 4 | Offset of the vertex array, always `0x14` |
| `0x10` | 4 | Offset of the cell array = `0x14 + 12 × vertex_count` |
| `0x14` | 12 × `vertex_count` | Vertices, `f32 x, y, z`, row-major (x fastest). x steps by 0.5 along a row, z by 0.5 down the rows; y is the floor height. |
| … | `cell_count` | One byte per cell, row-major. Values 0 and 1 only. |

The file ends exactly after the cell array.

Sizes on the disc: from 13 × 8 cells (the eight Slifer dorm rooms, 1,636 bytes) to 64 × 64 cells (the outdoor maps, 54,816 bytes). Heights range from −1.125 to 12.0.

## Use in the field module

- After loading, `world_bind_map_archive` subtracts vertex 0 from every vertex (`system_vfpu_vector_sub_t` loop over `vertex_count`) and stores vertex 0 separately (`0x09106fe4`). Grid coordinates are therefore relative to the grid corner.
- Story set-up opcodes give positions as cell indices: `scene_player` (50159) and `npc_position` (50168) turn `(x, y)` into `(x·0.5 + 0.25, y·0.5 + 0.25)`, the centre of cell `(x, y)` (`docs/formats/story.md`).
- **Cell byte**: 1 = walkable, 0 = blocked (high for the data, static only). Basis: with the story location → map switch of `docs/formats/field-maps.md` (`world_location_to_map_id`), 1,214 of the 1,218 player start (`scene_player`) and NPC (`npc_position`) cells of the set-up records lie on 1-cells; 349 of the 350 NPC spots do too. (An earlier count used the exit selector as the location → map mapping, which is wrong for locations 27–30.) The exit cells (for example `(12, 5)` and `(12, 6)` of the 13 × 8 rooms) are 1-cells too.

## Floor height

`world_sample_floor_height` (`rel_field` `0x090d9948`) gives the height at a grid-relative position `(px, pz)` (high for the structure; the two BOOT.BIN vector helpers it calls are read as cross and dot product from the formula, medium):

1. Cell `(ix, iz) = (int(px / 0.5), int(pz / 0.5))`; vertex `v00` = vertex `ix + iz · vertex_columns`. On maps 12 and 37 (Slifer dorm outside) the door cells `(15, 24)` and `(15, 20)`, `(15, 16)`, `(15, 12)` use the column to their right.
2. If `px − v00.x < pz − v00.z` the triangle is `(v00, v01, v11)` (v01 = next row, v11 = next row and column), else `(v00, v11, v10)`: the cell is split along the `v00`–`v11` diagonal.
3. `n = (a − v00) × (b − v00)` for the triangle's other two vertices; `y = (n · v00 − n.x · px − n.z · pz) / n.y`.

Outside the vertex array the position is left unchanged. Vertices are relative to vertex 0 (see "Use in the field module"), so the result is too. `WalkGrid.floor_height` in `tools/world.py` implements the rule (tests on synthetic grids).

Walkability: the field also blocks a few cells by code before it reads the cell byte (door cells, cells next to the classroom exits, two store cells); see `docs/formats/field-maps.md`.

## Tool

`python3 -I tools/world.py hmp <USRDIR>/field/map --check` parses every grid and checks the header arithmetic and the regular 0.5 spacing; `--grid` prints a grid (`#` walkable). Tests: `tools/tests/test_world.py` (synthetic grids).

## Open questions

- Whether any code reads values other than 0/1 (none occur on the disc).
- PPSSPP confirmation of the triangle split (static only).
