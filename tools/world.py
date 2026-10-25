#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Free-roam field data: walk grids (.hmp) of field/map/bg_*.ehp and the rel_story character and spot tables. See docs/formats/hmp.md and
docs/subsystems/world.md.

  world.py hmp <USRDIR>/field/map --check          # parse every bg_*.ehp walk grid, check the layout
  world.py hmp <USRDIR>/field/map/bg_02_01.ehp --grid   # print the walk grid ('#' walkable, '.' blocked)
  world.py chars <USRDIR>/gmodule/rel_story.prx --check   # per-character table (event keys, flags, tastes)
  world.py spots <USRDIR>/gmodule/rel_story.prx           # NPC spot table: spots per story location

Output describes layout only (sizes, extents); keep any dumps of game data under extracted/.
"""

import argparse
import importlib.util
import struct
import sys
from pathlib import Path


def _load(name):
    spec = importlib.util.spec_from_file_location(f"re_{name}", Path(__file__).resolve().parent / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HEADER = struct.Struct("<6H2I")  # vertex count, vertex columns, vertex rows, cell count, cell columns, cell rows,
#                                  vertex array offset, cell array offset
CELL_SIZE = 0.5  # world units between grid vertices


class WalkGrid:
    """A parsed .hmp: a (columns+1) x (rows+1) vertex grid of float3 and one byte per cell."""

    def __init__(self, blob):
        if len(blob) < HEADER.size:
            raise ValueError("hmp: shorter than its header")
        (vertex_count, vertex_columns, vertex_rows, cell_count, columns, rows,
         vertex_offset, cell_offset) = HEADER.unpack_from(blob)
        problems = []
        if vertex_count != vertex_columns * vertex_rows:
            problems.append("vertex count is not columns x rows")
        if cell_count != columns * rows:
            problems.append("cell count is not columns x rows")
        if (columns, rows) != (vertex_columns - 1, vertex_rows - 1):
            problems.append("cell grid is not one smaller than the vertex grid")
        if vertex_offset != HEADER.size:
            problems.append("vertex array does not follow the header")
        if cell_offset != vertex_offset + 12 * vertex_count:
            problems.append("cell array does not follow the vertex array")
        if len(blob) != cell_offset + cell_count:
            problems.append("file size is not header + vertices + cells")
        if problems:
            raise ValueError("hmp: " + "; ".join(problems))
        self.columns, self.rows = columns, rows
        self.vertices = [struct.unpack_from("<3f", blob, vertex_offset + 12 * i) for i in range(vertex_count)]
        self.cells = blob[cell_offset:cell_offset + cell_count]

    def cell(self, x, y):
        """Cell byte at column x, row y (row-major, x fastest); 1 = walkable, 0 = blocked."""
        return self.cells[y * self.columns + x]

    def origin(self):
        return self.vertices[0]

    def cell_centre(self, x, y):
        """Position of cell (x, y) relative to vertex 0, as the field module uses it (x*0.5+0.25)."""
        return (x * CELL_SIZE + CELL_SIZE / 2, y * CELL_SIZE + CELL_SIZE / 2)

    def check_regular(self):
        """Vertices step by 0.5 in x along a row and in z down the rows."""
        x0, _, z0 = self.vertices[0]
        width = self.columns + 1
        for i, (x, _, z) in enumerate(self.vertices):
            if abs(x - (x0 + CELL_SIZE * (i % width))) > 1e-4 or abs(z - (z0 + CELL_SIZE * (i // width))) > 1e-4:
                return False
        return True

    def grid_text(self):
        return "\n".join("".join("#" if self.cell(x, y) else "." for x in range(self.columns))
                         for y in range(self.rows))


def hmp_members(path):
    ehp = _load("ehp")
    archives = sorted(path.glob("bg_*.ehp")) if path.is_dir() else [path]
    for archive in archives:
        for name, blob in ehp.parse(archive.read_bytes()):
            if name.endswith(".hmp"):
                yield archive.name, name, blob


def cmd_hmp(args):
    failures = 0
    for archive, name, blob in hmp_members(Path(args.path)):
        try:
            grid = WalkGrid(blob)
        except ValueError as error:
            failures += 1
            print(f"{archive}:{name}: {error}")
            continue
        regular = grid.check_regular()
        failures += not regular
        values = sorted(set(grid.cells))
        x, y, z = grid.origin()
        print(f"{archive}:{name}: {grid.columns}x{grid.rows} cells, origin ({x:g}, {z:g}), "
              f"values {values}, walkable {sum(1 for c in grid.cells if c)}{'' if regular else ', IRREGULAR'}")
        if args.grid:
            print(grid.grid_text())
    if args.check:
        print(f"failing: {failures}")
        return 1 if failures else 0
    return 0


# --- rel_story.prx tables (module offsets; file offset = offset + 0x54, docs/subsystems/world.md) -------------

PRX_FILE_OFFSET = 0x54  # one PT_LOAD segment starting right after the ELF and program headers
CHAR_TABLE = 0x2245C  # 140 rows of 57 u32 (world_get_char_table_value, rel_story 0x08eac124)
CHAR_ROWS, CHAR_COLUMNS = 140, 57
SPOT_TABLE = 0x2092C  # 350 x {u32 location, u32 x, u32 y, u32 direction} (world_get_spot, 0x08eac06c)
SPOT_COUNT = 350
ITEM_COUNT = 50  # sandwiches 1..50; item k is column 6 + k of the character table (world_item_taste_column)
DESTINY_ITEM, GOLDEN_EGG_ITEM = 48, 50
# Points added by the generic reaction records (301, 6, taste) that world_give_item_to_partner queues;
# taste 6 / the Destiny sandwich draw a taste 1..5 at random, the golden-egg sandwich runs (301, 6, 6).
GIFT_POINTS = {1: 40, 2: 20, 3: 10, 4: -5, 5: -10}
GOLDEN_EGG_POINTS = 200


class CharacterRow:
    """One row of the rel_story character table: id, event-key a1 per variant, two flags, 50 tastes."""

    def __init__(self, words):
        if len(words) != CHAR_COLUMNS:
            raise ValueError(f"character row: {len(words)} words, expected {CHAR_COLUMNS}")
        self.character = words[0]
        self.event_keys = [k for k in words[1:5]]  # header a1 of the character's records, variant 0..3 (0 = none)
        self.no_free_roam = words[5]  # copied to runtime-record flag 1 at a new partner
        self.no_pairing = words[6]  # copied to runtime-record flag 5: excluded from the daily spot pairing
        self.tastes = list(words[7:7 + ITEM_COUNT])  # taste of item k at index k - 1: 1 best .. 5 worst, 6 random

    def taste(self, item):
        if not 1 <= item <= ITEM_COUNT:
            raise ValueError(f"item {item} out of range")
        return self.tastes[item - 1]


def gift_points(taste, item):
    """Partner points of a gift as the reaction records give them; None when the taste is drawn at random."""
    if item == GOLDEN_EGG_ITEM:
        return GOLDEN_EGG_POINTS
    if taste == 6 or item == DESTINY_ITEM:
        return None
    return GIFT_POINTS[min(max(taste, 1), 5)]


def read_character_table(prx, offset=CHAR_TABLE, rows=CHAR_ROWS):
    base = PRX_FILE_OFFSET + offset
    return [CharacterRow(struct.unpack_from(f"<{CHAR_COLUMNS}i", prx, base + 4 * CHAR_COLUMNS * r))
            for r in range(rows)]


def check_character_table(rows):
    problems = []
    ids = [row.character for row in rows]
    if ids != sorted(set(ids)):
        problems.append("character ids are not unique and ascending")
    for row in rows:
        if not row.event_keys[0]:
            problems.append(f"character {row.character}: no event key for variant 0")
        if any(t not in range(1, 7) for t in row.tastes):
            problems.append(f"character {row.character}: taste outside 1..6")
        if row.no_free_roam not in (0, 1) or row.no_pairing not in (0, 1):
            problems.append(f"character {row.character}: flag columns are not 0/1")
    return problems


def read_spots(prx, offset=SPOT_TABLE, count=SPOT_COUNT):
    base = PRX_FILE_OFFSET + offset
    return [struct.unpack_from("<4i", prx, base + 16 * i) for i in range(count)]


def cmd_chars(args):
    rows = read_character_table(Path(args.prx).read_bytes())
    for row in rows:
        counts = [row.tastes.count(t) for t in range(1, 7)]
        keys = "/".join(str(k) for k in row.event_keys if k)
        print(f"char {row.character:3d}: keys {keys}, flags {row.no_free_roam}{row.no_pairing}, "
              f"tastes 1..6 x {counts}")
    if args.check:
        problems = check_character_table(rows)
        for problem in problems:
            print(problem)
        print(f"failing: {len(problems)}")
        return 1 if problems else 0
    return 0


def cmd_spots(args):
    spots = read_spots(Path(args.prx).read_bytes())
    per_location = {}
    for location, _, _, _ in spots:
        per_location[location] = per_location.get(location, 0) + 1
    for location in sorted(per_location):
        print(f"location {location:2d}: {per_location[location]} spots")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    hmp = sub.add_parser("hmp", help="walk grids of field/map/bg_*.ehp")
    hmp.add_argument("path", help="field/map directory or one bg_*.ehp")
    hmp.add_argument("--check", action="store_true", help="exit 1 if any grid breaks the layout")
    hmp.add_argument("--grid", action="store_true", help="print each walk grid")
    hmp.set_defaults(func=cmd_hmp)
    chars = sub.add_parser("chars", help="rel_story character table (event keys, flags, item tastes)")
    chars.add_argument("prx", help="gmodule/rel_story.prx")
    chars.add_argument("--check", action="store_true", help="exit 1 if the table breaks the documented layout")
    chars.set_defaults(func=cmd_chars)
    spots = sub.add_parser("spots", help="rel_story NPC spot table, counted per story location")
    spots.add_argument("prx", help="gmodule/rel_story.prx")
    spots.set_defaults(func=cmd_spots)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
