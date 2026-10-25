#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/world.py on hand-built walk grids (no game data). Run with: python3 -I tools/tests/test_world.py"""

import importlib.util
import struct
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_world", Path(__file__).resolve().parents[1] / "world.py")
world = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(world)


def hmp(columns, rows, cells, origin=(-1.0, 0.0, -0.5), step=0.5):
    vertex_columns, vertex_rows = columns + 1, rows + 1
    count = vertex_columns * vertex_rows
    vertices = b"".join(struct.pack("<3f", origin[0] + step * (i % vertex_columns), 0.0,
                                    origin[2] + step * (i // vertex_columns)) for i in range(count))
    header = struct.pack("<6H2I", count, vertex_columns, vertex_rows, columns * rows, columns, rows,
                         20, 20 + 12 * count)
    return header + vertices + bytes(cells)


class WalkGridTest(unittest.TestCase):
    def test_parse_and_cells(self):
        grid = world.WalkGrid(hmp(3, 2, [0, 1, 1, 1, 0, 0]))
        self.assertEqual((grid.columns, grid.rows), (3, 2))
        self.assertEqual(grid.cell(1, 0), 1)
        self.assertEqual(grid.cell(0, 1), 1)
        self.assertEqual(grid.cell(2, 1), 0)
        self.assertEqual(grid.grid_text(), ".##\n#..")
        self.assertEqual(grid.origin(), (-1.0, 0.0, -0.5))
        self.assertTrue(grid.check_regular())

    def test_cell_centre(self):
        grid = world.WalkGrid(hmp(4, 4, [1] * 16))
        self.assertEqual(grid.cell_centre(0, 0), (0.25, 0.25))
        self.assertEqual(grid.cell_centre(3, 2), (1.75, 1.25))

    def test_irregular_grid(self):
        grid = world.WalkGrid(hmp(2, 2, [1] * 4, step=0.75))
        self.assertFalse(grid.check_regular())

    def test_layout_errors(self):
        good = hmp(2, 2, [1] * 4)
        with self.assertRaises(ValueError):
            world.WalkGrid(good[:-1])
        bad = bytearray(good)
        struct.pack_into("<H", bad, 6, 5)  # cell count no longer columns x rows
        with self.assertRaises(ValueError):
            world.WalkGrid(bytes(bad))
        with self.assertRaises(ValueError):
            world.WalkGrid(b"\0" * 8)


if __name__ == "__main__":
    unittest.main()
