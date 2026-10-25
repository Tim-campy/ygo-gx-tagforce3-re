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
- **Cell byte**: 1 = walkable, 0 = blocked (high for the data, static only). Basis: with the story location → map mapping of `docs/formats/field-tables.md`, 213 of the 214 player start cells (`scene_player`) and 973 of the 988 in-grid NPC cells (`npc_position`) of the set-up records lie on 1-cells (10 NPCs and 1 start on 0-cells, 5 NPCs outside the grid: presumably characters standing behind a counter or off-screen). The exit cells (for example `(12, 5)` and `(12, 6)` of the 13 × 8 rooms) are 1-cells too.

## Tool

`python3 -I tools/world.py hmp <USRDIR>/field/map --check` parses every grid and checks the header arithmetic and the regular 0.5 spacing; `--grid` prints a grid (`#` walkable). Tests: `tools/tests/test_world.py` (synthetic grids).

## Open questions

- Whether any code reads values other than 0/1 (none occur on the disc).
- How the height is interpolated inside a cell (bilinear over the four vertices is the obvious reading; the sampling code is VFPU-heavy and not read yet).
