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


def char_row(character, keys=(1, 0, 0, 0), flags=(0, 0), tastes=None):
    tastes = tastes or [3] * world.ITEM_COUNT
    return [character, *keys, *flags, *tastes]


class CharacterTableTest(unittest.TestCase):
    def prx(self, rows):
        body = b"".join(struct.pack(f"<{world.CHAR_COLUMNS}i", *row) for row in rows)
        return bytes(world.PRX_FILE_OFFSET) + body

    def test_parse_rows(self):
        tastes = [1, 2, 3, 4, 5] * 10
        rows = world.read_character_table(self.prx([char_row(2, (1, 2, 0, 0), (1, 0), tastes), char_row(3)]),
                                          offset=0, rows=2)
        self.assertEqual(rows[0].character, 2)
        self.assertEqual(rows[0].event_keys, [1, 2, 0, 0])
        self.assertEqual((rows[0].no_free_roam, rows[0].no_pairing), (1, 0))
        self.assertEqual(rows[0].taste(1), 1)
        self.assertEqual(rows[0].taste(50), 5)
        with self.assertRaises(ValueError):
            rows[0].taste(51)
        self.assertEqual(world.check_character_table(rows), [])

    def test_check_problems(self):
        rows = world.read_character_table(self.prx([char_row(5), char_row(4, (0, 0, 0, 0)),
                                                    char_row(6, tastes=[7] * 50)]), offset=0, rows=3)
        problems = world.check_character_table(rows)
        self.assertEqual(len(problems), 3)  # order, missing key, taste out of range

    def test_gift_points(self):
        self.assertEqual(world.gift_points(1, 1), 40)
        self.assertEqual(world.gift_points(4, 10), -5)
        self.assertEqual(world.gift_points(5, 10), -10)
        self.assertIsNone(world.gift_points(6, 3))
        self.assertIsNone(world.gift_points(2, world.DESTINY_ITEM))
        self.assertEqual(world.gift_points(1, world.GOLDEN_EGG_ITEM), 200)

    def test_spots(self):
        blob = bytes(world.PRX_FILE_OFFSET) + struct.pack("<8i", 1, 37, 31, 7, 2, 4, 5, 1)
        self.assertEqual(world.read_spots(blob, offset=0, count=2), [(1, 37, 31, 7), (2, 4, 5, 1)])


if __name__ == "__main__":
    unittest.main()
