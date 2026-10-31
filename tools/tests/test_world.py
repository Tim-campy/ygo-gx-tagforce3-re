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


def hmp_heights(columns, rows, heights):
    """A grid whose vertex (i, j) has height heights[j][i]."""
    vertex_columns, vertex_rows = columns + 1, rows + 1
    count = vertex_columns * vertex_rows
    vertices = b"".join(struct.pack("<3f", 0.5 * (i % vertex_columns), heights[i // vertex_columns][i % vertex_columns],
                                    0.5 * (i // vertex_columns)) for i in range(count))
    header = struct.pack("<6H2I", count, vertex_columns, vertex_rows, columns * rows, columns, rows,
                         20, 20 + 12 * count)
    return header + vertices + bytes([1] * columns * rows)


class FloorHeightTest(unittest.TestCase):
    def test_plane(self):
        # A slope y = x: every point lies on the plane whichever triangle is used.
        grid = world.WalkGrid(hmp_heights(2, 2, [[0.0, 0.5, 1.0]] * 3))
        self.assertAlmostEqual(grid.floor_height(0.3, 0.1), 0.3)
        self.assertAlmostEqual(grid.floor_height(0.1, 0.4), 0.1)
        self.assertIsNone(grid.floor_height(1.2, 0.1))
        self.assertIsNone(grid.floor_height(-0.1, 0.1))

    def test_diagonal_split(self):
        # One raised corner v10 (x = 0.5, z = 0): only the triangle (v00, v11, v10) sees it.
        grid = world.WalkGrid(hmp_heights(1, 1, [[0.0, 1.0], [0.0, 0.0]]))
        self.assertAlmostEqual(grid.floor_height(0.1, 0.4), 0.0)  # px - x0 < pz - z0: (v00, v01, v11)
        self.assertAlmostEqual(grid.floor_height(0.4, 0.1), 0.6)  # else (v00, v11, v10): y = 2 (x - z)


def module(size, patches):
    """A fake module image: PRX_FILE_OFFSET bytes of header, then `size` bytes with patches {offset: bytes}."""
    blob = bytearray(world.PRX_FILE_OFFSET + size)
    for offset, data in patches.items():
        blob[world.PRX_FILE_OFFSET + offset:world.PRX_FILE_OFFSET + offset + len(data)] = data
    return bytes(blob)


class MapIdTest(unittest.TestCase):
    def test_switch(self):
        self.assertEqual([world.map_id_to_index(m) for m in (1, 5, 12, 27, 29, 32, 36, 42)],
                         [0, 4, 5, 20, 21, 24, 25, 31])
        self.assertEqual(world.map_id_to_index(28), 0)
        self.assertEqual(len(world.MAP_IDS), world.MAP_COUNT)
        self.assertEqual(sorted(world.map_id_to_index(m) for m in world.MAP_IDS), list(range(32)))

    def test_locations(self):
        for loc in range(1, 31):
            self.assertEqual(world.MAP_TO_LOCATION[world.LOCATION_TO_MAP[loc]], loc)
        self.assertEqual(world.MAP_TO_LOCATION[37], 6)
        self.assertEqual(world.LOCATION_TO_MAP[27], 39)  # not 37: the selector's group key differs

    def test_island_areas(self):
        for area, maps in world.ISLAND_AREA_MAPS.items():
            for sub, map_id in enumerate(maps):
                self.assertEqual(world.island_area_of_map(map_id), (area, sub))
        self.assertEqual(world.island_area_of_map(17), (0, 0))  # a dorm room belongs to the dorm area
        self.assertEqual(world.island_area_of_map(40), (4, 0))  # unknown maps fall back to the gate

    def test_walk_blocks(self):
        self.assertTrue(world.walk_blocked(12, 15, 24, npc=True))
        self.assertFalse(world.walk_blocked(12, 15, 24))
        self.assertTrue(world.walk_blocked(37, 15, 24, midnight=True))
        self.assertFalse(world.walk_blocked(37, 13, 12, midnight=True))  # one room door stays open at night
        self.assertTrue(world.walk_blocked(2, 10, 1, event=True))
        self.assertFalse(world.walk_blocked(3, 14, 17, event=True))

    def test_arrival(self):
        self.assertEqual(world.arrival_cell(2), (11, 2, 1))
        self.assertEqual(world.arrival_cell(2, system_flags={20}), (8, 25, 1))
        self.assertEqual(world.arrival_cell(6, previous=11), (14, 24, 7))
        self.assertEqual(world.arrival_cell(6, previous=28, previous_cell=(12, 13)), (16, 16, 7))
        self.assertIsNone(world.arrival_cell(6, previous=28, previous_cell=(12, 9)))
        self.assertEqual(world.arrival_cell(14, previous=6), (11, 6, 3))
        self.assertEqual(world.arrival_cell(14, previous=6, flag_08e9b460=True), (4, 4, 0))
        self.assertEqual(world.arrival_cell(30), world.ARRIVAL_DEFAULT)

    def test_abgr(self):
        self.assertEqual(world.abgr_hex(0xFF5AC8FF), "#ffc85aff")


class FieldTableTest(unittest.TestCase):
    def test_map_table_and_names(self):
        names = b"bg_01_01 [OUTSIDE]\nbg_02_01 [ROOM]\0"
        patches = {world.MAP_DEBUG_NAMES: names, 0x100: b"bg_07_01.ehp\0", 0x120: b"bg_07_01.tms\0",
                   world.MAP_ARCHIVES: struct.pack("<I", 0x100), world.MAP_MESHES: struct.pack("<II", 0x120, 0)}
        field = module(0x30000, patches)
        rows = world.read_map_table(field)
        self.assertEqual(rows[0], {"index": 0, "archive": "bg_07_01.ehp", "meshes": ["bg_07_01.tms"]})
        self.assertIsNone(rows[1]["archive"])
        self.assertEqual(world.read_debug_names(field), {"bg_01_01": "OUTSIDE", "bg_02_01": "ROOM"})

    def test_doors(self):
        entry = struct.pack("<3I3f3ffI", 0x200, 1, 0, 1.0, 2.0, 3.0, 0.0, 90.0, 0.0, 0.25, 13)
        offset = world.DOOR_TABLE + world.DOOR_BLOCK * 5 + world.DOOR_ENTRY * 2
        field = module(0x30000, {0x200: b"bg_01_01_door_b.tms\0", offset: entry})
        doors = world.read_doors(field)
        self.assertEqual(len(doors), 1)
        door = doors[0]
        self.assertEqual((door["map_index"], door["slot"], door["mesh"], door["kind"]),
                         (5, 2, "bg_01_01_door_b.tms", 1))
        self.assertEqual((door["position"], door["rotation_degrees"]), ([1.0, 2.0, 3.0], [0.0, 90.0, 0.0]))
        self.assertEqual((door["amount"], door["target_map"]), (0.25, 13))

    def test_lighting_and_island(self):
        lighting = struct.pack("<10I", 0, 0, 1, 1, 2, 2, 3, 3, 4, 4)
        island = struct.pack(f"<{2 * world.ISLAND_AREAS}i", *range(2 * world.ISLAND_AREAS))
        field = module(0x30000, {world.MAP_LIGHTING + 0x28: lighting, world.ISLAND_POSITIONS: island,
                                 world.SKY_GRADIENTS: struct.pack("<3I", 1, 2, 3)})
        self.assertEqual(world.read_map_lighting(field)[1], [(0, 0), (1, 1), (2, 2), (3, 3), (4, 4)])
        self.assertEqual(world.read_island_positions(field)[1], (2, 3))
        self.assertEqual(world.read_sky_gradients(field)[0], (1, 2, 3))

    def test_exit_tables(self):
        selector = (struct.pack("<9H", 6, 12, 0, 0, 0, 0, 0, 0, 0) + struct.pack("<9H", 7, 13, 1, 2, 0, 0, 0, 0, 0)
                    + struct.pack("<9H", 7, 14, 0, 0, 5, 3, 0, 0, 0) + struct.pack("<9H", 7, 15, 0, 0, 0, 0, 0, 0, 0)
                    + bytes(18))
        cells = struct.pack("<9H", 12, 0, 0, 0, 1, 2, 0, 3, 4) + struct.pack("<6H", 13, 0, 0, 0, 5, 6) + bytes(6)
        story = module(0x30000, {world.EXIT_SELECTOR: selector, world.EXIT_CELLS: cells})
        records = world.read_exit_selector(story)
        self.assertEqual([r["location"] for r in records], [6, 7, 7, 7])
        self.assertEqual(world.read_exit_groups(story), {12: [(1, 2), (3, 4)], 13: [(5, 6)]})
        self.assertEqual(world.select_exit_group(records, 6), 12)
        self.assertEqual(world.select_exit_group(records, 7, stage=2), 13)  # stage condition
        self.assertEqual(world.select_exit_group(records, 7, stage=1, story_flags={5}), 14)  # mode 3: flag set
        self.assertEqual(world.select_exit_group(records, 7, stage=1), 15)
        self.assertIsNone(world.select_exit_group(records, 8))

    def test_fixed_spots(self):
        fixed = b"".join(struct.pack("<4i", i, i + 1, i + 2, 1) for i in range(len(world.FIXED_SPOT_CHARS)))
        story = module(0x30000, {world.FIXED_SPOTS: fixed, world.SELLER_SPOTS: struct.pack("<4i", 3, 28, 17, 1)})
        spots = world.read_fixed_spots(story)
        self.assertEqual(spots["fixed"][127], (0, 1, 2, 1))
        self.assertEqual(spots["fixed"][140], (12, 13, 14, 1))
        self.assertEqual(spots["sellers"][0], (3, 28, 17, 1))
        self.assertEqual(len(spots["char139"]), world.CHAR139_SPOT_COUNT)

    def test_output_guard(self):
        repo = Path(SPEC.origin).resolve().parents[1]
        self.assertFalse(world._output_allowed(repo / "tools" / "x.json"))
        self.assertTrue(world._output_allowed(repo / "extracted" / "world" / "x.json"))


if __name__ == "__main__":
    unittest.main()
