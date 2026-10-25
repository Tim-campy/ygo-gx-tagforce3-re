#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Free-roam field data: walk grids (.hmp) of field/map/bg_*.ehp. See docs/formats/hmp.md and
docs/subsystems/world.md.

  world.py hmp <USRDIR>/field/map --check          # parse every bg_*.ehp walk grid, check the layout
  world.py hmp <USRDIR>/field/map/bg_02_01.ehp --grid   # print the walk grid ('#' walkable, '.' blocked)

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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    hmp = sub.add_parser("hmp", help="walk grids of field/map/bg_*.ehp")
    hmp.add_argument("path", help="field/map directory or one bg_*.ehp")
    hmp.add_argument("--check", action="store_true", help="exit 1 if any grid breaks the layout")
    hmp.add_argument("--grid", action="store_true", help="print each walk grid")
    hmp.set_defaults(func=cmd_hmp)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
