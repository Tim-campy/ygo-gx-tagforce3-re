#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Free-roam field data: walk grids (.hmp) of field/map/bg_*.ehp, the rel_story character and spot tables and the
rel_field/rel_story map, door, exit and island tables. See docs/formats/hmp.md, docs/formats/field-maps.md and
docs/subsystems/world.md.

  world.py hmp <USRDIR>/field/map --check          # parse every bg_*.ehp walk grid, check the layout
  world.py hmp <USRDIR>/field/map/bg_02_01.ehp --grid   # print the walk grid ('#' walkable, '.' blocked)
  world.py chars <USRDIR>/gmodule/rel_story.prx --check   # per-character table (event keys, flags, tastes)
  world.py spots <USRDIR>/gmodule/rel_story.prx           # NPC spot table: spots per story location
  world.py chapters <USRDIR> --check                       # partner chapter table vs. story records/locations
  world.py chapters <USRDIR> -o extracted/world/chapters.json   # the chapter table, caps and partner rows
  world.py tables <USRDIR> --check                         # map/door/exit/island/spot tables, cross-checked
  world.py tables <USRDIR> [--table doors] -o extracted/world/tables.json   # the same tables as JSON
  world.py locations <USRDIR> -o extracted/world/maps [--names]           # one JSON per field map

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

    def floor_height(self, px, pz):
        """Floor height at grid-relative position (px, pz), as rel_field 0x090d9948 samples it: the cell is split
        along its v00-v11 diagonal; the triangle (v00, v01, v11) is used when px - v00.x < pz - v00.z, else
        (v00, v11, v10); the height is the plane of that triangle. Relative to vertex 0, like the field's copy
        of the grid; None outside the grid."""
        width = self.columns + 1
        ix, iz = int(px / CELL_SIZE), int(pz / CELL_SIZE)
        if px < 0 or pz < 0 or ix >= self.columns or iz >= self.rows:
            return None
        x0, y0, z0 = self.vertices[0]

        def rel(i, j):
            x, y, z = self.vertices[j * width + i]
            return x - x0, y - y0, z - z0
        v00 = rel(ix, iz)
        if px - v00[0] < pz - v00[2]:
            a, b = rel(ix, iz + 1), rel(ix + 1, iz + 1)
        else:
            a, b = rel(ix + 1, iz + 1), rel(ix + 1, iz)
        e1 = [a[k] - v00[k] for k in range(3)]
        e2 = [b[k] - v00[k] for k in range(3)]
        n = (e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0])
        d = n[0] * v00[0] + n[1] * v00[1] + n[2] * v00[2]
        return (d - n[0] * px - n[2] * pz) / n[1]

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


# --- Partner chapter table and progression (docs/formats/chapter-table.md) ------------------------------------
#
# rel_story +0x2a10c: 64 rows of 17 entries of four i32. Entry 0 is the header {kind, character, variant, alt
# variant}; entry step + 4 (stage - 1) (stage 1..4, step 1..4) is {location, a1, a2, a3}, the story record key to
# queue and where it plays. world_get_chapter_table_word (0x08eac0c4) is the only reader: it indexes
# row * 0x110 + entry * 16 + word * 4 without bounds, so stages above 4 would read the following row.

CHAPTER_TABLE = 0x2A10C
CHAPTER_ROWS, CHAPTER_ENTRIES = 64, 17
CHAPTER_STAGES = CHAPTER_STEPS = 4
POINTS_CAPS = 0x2E528  # i32 per story stage 0..10 (world_get_points_cap, 0x08eab450)
STORY_STAGE_LAST = 10  # world_advance_story_stage caps the stage byte here; no chapter event at stage 10
CHAPTER_KINDS = {0: "shared chapters, own ending", 1: "generic", 2: "own story"}  # header word 0, never read
CHAPTER_GENERIC_CHARACTER = 1  # world_find_partner_chapter_row: other categories take the first row with char 1
OWN_ROW_CATEGORIES = (0, 2)  # categories that search their own (character, variant) row
ENDING_OFFSET_CATEGORIES = (1, 4, 5)  # stage 4 step 4: a2 += partner - 46 (world_lookup_chapter_event)
ENDING_OFFSET_BASE = 46
DAILY_STEPS = (1, 4)  # queued at the first map entry of a working day, wherever the player is
LOCATION_STEPS = (2, 3)  # queued on entering the entry's location, not in time slots 1 and 7
# 0x08e9cad0: partner 7 at step 2 of stages 5..7 also hides two characters (record flag 1) and flags their duel
# pair partners (flag 2). Stages above 4 are not reached by the shipped records (see the format page).
PARTNER7_HIDDEN = {7: (2, 3), 6: (4, 20), 5: (22, 23)}
# story bytecode opcodes the progression depends on (docs/formats/story.md)
OP_ADVANCE_STAGE, OP_FINISH_PARTNER, OP_GOTO, OP_SCENE_MAP = 50094, 50137, 50138, 50158
# BOOT.BIN character table (docs/formats/sound.md): u8 character, u8 variant, ..., +0x08 i8 category
BOOT_BASE, BOOT_CHARACTERS, BOOT_CHARACTER_ROWS, BOOT_CHARACTER_SIZE = 0x08804000, 0x088AA510, 174, 148


class ChapterTable:
    """The partner chapter table as a flat word array, read the way the game reads it."""

    def __init__(self, words):
        if len(words) % (CHAPTER_ENTRIES * 4):
            raise ValueError("chapter table: not whole rows")
        self.words = list(words)
        self.rows = len(self.words) // (CHAPTER_ENTRIES * 4)

    def word(self, row, entry, index):
        """world_get_chapter_table_word(row, entry, index); None outside the table."""
        position = (row * CHAPTER_ENTRIES + entry) * 4 + index
        return self.words[position] if 0 <= position < len(self.words) else None

    def header(self, row):
        kind, character, variant, alt = (self.word(row, 0, i) for i in range(4))
        return {"kind": kind, "character": character, "variant": variant, "alt_variant": alt}

    def entry(self, row, stage, step):
        """(location, a1, a2, a3) of one stage/step, with no partner adjustment."""
        index = step + CHAPTER_STEPS * (stage - 1)
        return tuple(self.word(row, index, i) for i in range(4))

    def find_row(self, character, variant, category):
        """world_find_partner_chapter_row (0x08e9d25c). None where the game returns an uninitialised register."""
        for row in range(self.rows):
            if category in OWN_ROW_CATEGORIES:
                head = self.header(row)
                if head["character"] == character and variant in (head["variant"], head["alt_variant"]):
                    return row
            elif self.word(row, 0, 1) == CHAPTER_GENERIC_CHARACTER:
                return row
        return None

    def lookup(self, row, stage, step, partner, category):
        """world_lookup_chapter_event (0x08e9d08c): the entry, or None when the game returns 0 (empty entry)."""
        if stage <= 0:
            return None
        location, a1, a2, a3 = self.entry(row, stage, step)
        if None in (location, a1, a2, a3) or min(location, a1, a2, a3) < 0:
            return None
        if (stage, step) == (CHAPTER_STAGES, CHAPTER_STEPS) and category in ENDING_OFFSET_CATEGORIES:
            a2 += partner - ENDING_OFFSET_BASE
        return location, a1, a2, a3

    def next_event(self, row, stage, step, partner, category):
        """world_get_next_chapter_event (0x08e9c868): (step, entry) after skipping empty steps. The game loops
        until it finds an entry; None as the entry stands for that endless loop."""
        for _ in range(CHAPTER_STEPS):
            found = self.lookup(row, stage, step, partner, category)
            if found:
                return step, found
            step = advance_chapter_step(step)
        return step, None


def advance_chapter_step(step):
    """world_advance_chapter_step (0x08eab40c): step + 1, back to 1 after 4."""
    return step + 1 if step + 1 <= CHAPTER_STEPS else 1


def read_chapter_table(prx, offset=CHAPTER_TABLE, rows=CHAPTER_ROWS):
    count = rows * CHAPTER_ENTRIES * 4
    return ChapterTable(struct.unpack_from(f"<{count}i", prx, PRX_FILE_OFFSET + offset))


def read_points_caps(prx, offset=POINTS_CAPS):
    return list(struct.unpack_from(f"<{STORY_STAGE_LAST + 1}i", prx, PRX_FILE_OFFSET + offset))


def chapter_event_on_map_entry(table, row, partner, category, points, caps, stage, step, location, slot,
                               day_off, talk_pending):
    """0x08e9cad0 (world_try_chapter_event), run by world_select_partner_event on every map entry.

    Returns (result, key, step, hidden): result 1 = no chapter event (the daily talk or a remark follows),
    2 = a daily-step event was queued, 0 = a location-step event was queued; key = (a1, a2, a3) queued or None;
    step = the chapter step afterwards; hidden = characters the partner-7 branch takes off the map."""
    if points != caps[stage] or stage == STORY_STAGE_LAST:
        return 1, None, step, ()
    step, found = table.next_event(row, stage, step, partner, category)
    if found is None:
        raise ValueError(f"row {row} stage {stage}: no entry (the game would loop forever)")
    where, a1, a2, a3 = found
    if step in DAILY_STEPS:
        if day_off or not talk_pending:
            return 1, None, step, ()
        return 2, (a1, a2, a3), advance_chapter_step(step), ()
    if where != location or slot in (1, 7):
        return 1, None, step, ()
    hidden = PARTNER7_HIDDEN.get(stage, ()) if partner == 7 and step == 2 else ()
    return 0, (a1, a2, a3), advance_chapter_step(step), hidden


def read_character_categories(boot):
    """{(character, variant): category} from the BOOT.BIN character table (category is the i8 at +0x08)."""
    tables = _load("tables")
    sections = tables.elf_sections(boot)
    out = {}
    for r in range(BOOT_CHARACTER_ROWS):
        offset = tables.to_offset(sections, BOOT_CHARACTERS + BOOT_CHARACTER_SIZE * r, BOOT_BASE)
        out[(boot[offset], boot[offset + 1])] = struct.unpack_from("<b", boot, offset + 8)[0]
    return out


def partner_category(categories, character):
    """world_get_character_category (BOOT 0x0885aeb0) looks up variant 0; 5 when the character is missing."""
    return categories.get((character, 0), 5)


def story_records(events):
    """{(a1, a2, a3): {"opcodes", "gotos", "scene_maps", "empty"}} from a story.Events program."""
    out = {}
    for record in range(len(events.starts)):
        start, end = events.record_span(record)
        head = events.instructions[start]
        body = events.instructions[start + 1:end - 1]
        out[tuple(head[1:4])] = {
            "opcodes": {ins[0] for ins in body},
            "gotos": [tuple(ins[1:4]) for ins in body if ins[0] == OP_GOTO],
            "scene_maps": [ins[1] for ins in body if ins[0] == OP_SCENE_MAP],
            "empty": not body}
    return out


def record_chain_opcodes(records, key):
    """Opcodes of a record and of every record it reaches through goto."""
    seen, todo, opcodes = set(), [key], set()
    while todo:
        current = todo.pop()
        if current in seen or current not in records:
            continue
        seen.add(current)
        opcodes |= records[current]["opcodes"]
        todo.extend(records[current]["gotos"])
    return opcodes


def chapter_partners(table, categories):
    """Every (character, variant) of the BOOT table with the row and stage-4 ending key the game would use."""
    out = []
    for (character, variant), _ in sorted(categories.items()):
        category = partner_category(categories, character)
        row = table.find_row(character, variant, category)
        ending = None
        if row is not None:
            found = table.lookup(row, CHAPTER_STAGES, CHAPTER_STEPS, character, category)
            ending = list(found[1:]) if found else None
        out.append({"character": character, "variant": variant, "category": category, "row": row,
                    "ending_key": ending})
    return out


def chapters_json(table, caps, categories=None):
    rows = []
    for row in range(table.rows):
        stages = []
        for stage in range(1, CHAPTER_STAGES + 1):
            steps = []
            for step in range(1, CHAPTER_STEPS + 1):
                location, a1, a2, a3 = table.entry(row, stage, step)
                steps.append(None if min(location, a1, a2, a3) < 0 else
                             {"step": step, "location": location, "key": [a1, a2, a3],
                              "trigger": "daily" if step in DAILY_STEPS else "location"})
            stages.append({"stage": stage, "points_cap": caps[stage], "steps": steps})
        rows.append({"row": row, **table.header(row), "stages": stages})
    data = {"source": f"rel_story.prx +{CHAPTER_TABLE:#x}", "points_caps": caps, "rows": rows}
    if categories is not None:
        data["partners"] = chapter_partners(table, categories)
    return data


def check_chapters(table, caps, records, categories=None):
    """Cross-check the table against the story records, the story locations and the BOOT categories.
    Returns (problems, notes)."""
    problems, notes = [], []
    for stage in range(1, STORY_STAGE_LAST):
        if caps[stage] != 1000 * min(stage, 8):
            problems.append(f"points cap of stage {stage} is {caps[stage]}, expected {1000 * min(stage, 8)}")
    generic = [r for r in range(table.rows) if table.word(r, 0, 1) == CHAPTER_GENERIC_CHARACTER]
    if not generic:
        problems.append("no generic row (character word 1)")
    elif table.header(generic[0])["kind"] != 1:
        problems.append(f"generic row {generic[0]} is not of kind 1")
    owners = {}
    for row in range(table.rows):
        head = table.header(row)
        if head["kind"] not in CHAPTER_KINDS:
            problems.append(f"row {row}: kind {head['kind']}")
        if head["kind"] == 1 and row not in generic[:1]:
            notes.append(f"row {row}: kind-1 row with character word {head['character']} is never selected")
        for v in (head["variant"], head["alt_variant"]):
            if v >= 0 and head["kind"] != 1:
                if (head["character"], v) in owners:
                    notes.append(f"row {row}: ({head['character']}, {v}) already matched by row "
                                 f"{owners[(head['character'], v)]}")
                owners.setdefault((head["character"], v), row)
        a1s, chain_ops, empty = set(), [], 0
        for stage in range(1, CHAPTER_STAGES + 1):
            stage_ops, filled = set(), 0
            for step in range(1, CHAPTER_STEPS + 1):
                entry = table.entry(row, stage, step)
                if max(entry) < 0:
                    continue
                if min(entry) < 0:
                    problems.append(f"row {row} stage {stage} step {step}: partly empty entry {entry}")
                    continue
                filled += 1
                location, a1, a2, a3 = entry
                if (stage, step) != (CHAPTER_STAGES, CHAPTER_STEPS):
                    a1s.add(a1)  # the stage-4 step-4 ending uses its own key (219)
                if location not in LOCATION_TO_MAP or location == 0:
                    problems.append(f"row {row} stage {stage} step {step}: location {location} is not a story "
                                    f"location")
                if (stage, step) == (CHAPTER_STAGES, CHAPTER_STEPS) and head["kind"] == 1:
                    continue  # the ending key depends on the partner; checked per partner below
                key = (a1, a2, a3)
                if key not in records:
                    problems.append(f"row {row} stage {stage} step {step}: record {key} missing")
                    continue
                record = records[key]
                empty += record["empty"]
                if step == 2 and record["scene_maps"] and record["scene_maps"][0] != location:
                    problems.append(f"row {row} stage {stage} step 2: record {key} opens scene map "
                                    f"{record['scene_maps'][0]}, not location {location}")
                stage_ops |= record_chain_opcodes(records, key)
            if not filled:
                problems.append(f"row {row} stage {stage}: no entry (world_get_next_chapter_event would loop)")
            chain_ops.append(stage_ops)
        if len(a1s) > 1:
            problems.append(f"row {row}: entries use several keys {sorted(a1s)}")
        if any(a1 not in range(201, 220) for a1 in a1s):
            problems.append(f"row {row}: key outside 201..219")
        if empty and all(not ops for ops in chain_ops):
            notes.append(f"row {row} ({head['character']}, {head['variant']}): every record is empty")
            continue
        for stage, ops in enumerate(chain_ops[:CHAPTER_STAGES - 1], 1):
            if OP_ADVANCE_STAGE not in ops:
                problems.append(f"row {row} stage {stage}: no advance_counter in the stage's records")
        if head["kind"] != 1 and head["kind"] != 0 and OP_FINISH_PARTNER not in chain_ops[-1]:
            problems.append(f"row {row}: no finish_partner_story in stage 4")
        if head["kind"] == 0:
            ending = table.entry(row, CHAPTER_STAGES, CHAPTER_STEPS)
            ops = record_chain_opcodes(records, tuple(ending[1:]))
            if not {OP_ADVANCE_STAGE, OP_FINISH_PARTNER} <= ops:
                problems.append(f"row {row}: ending {tuple(ending[1:])} lacks advance_counter/finish_partner_story")
    if categories is not None:
        selectable = 0
        for partner in chapter_partners(table, categories):
            c, v, category, row = partner["character"], partner["variant"], partner["category"], partner["row"]
            if row is None:
                notes.append(f"({c}, {v}) category {category}: no row (the game would use an undefined row)")
                continue
            selectable += 1
            ending = partner["ending_key"]
            if ending is None:
                continue
            ops = record_chain_opcodes(records, tuple(ending))
            if tuple(ending) not in records:
                (problems if category in (0, 1, 2) else notes).append(
                    f"({c}, {v}) category {category}: ending record {tuple(ending)} missing")
            elif table.header(row)["kind"] != 2 and not {OP_ADVANCE_STAGE, OP_FINISH_PARTNER} <= ops:
                problems.append(f"({c}, {v}): ending {tuple(ending)} lacks advance_counter/finish_partner_story")
        notes.append(f"{selectable} of {len(categories)} BOOT character rows resolve to a chapter row")
    return problems, notes


def _boot_path(usrdir):
    return Path(usrdir).parent / "SYSDIR" / "BOOT.BIN"


def cmd_chapters(args):
    usrdir = Path(args.usrdir)
    prx = (usrdir / "gmodule" / "rel_story.prx").read_bytes()
    table, caps = read_chapter_table(prx), read_points_caps(prx)
    boot = Path(args.boot) if args.boot else _boot_path(usrdir)
    categories = read_character_categories(boot.read_bytes()) if boot.is_file() else None
    if args.check:
        events = _load("story").Events((usrdir / "script" / "story_scr_b.ehp").read_bytes())
        problems, notes = check_chapters(table, caps, story_records(events), categories)
        if categories is None:
            notes.append(f"{boot}: not found, partner rows and endings not checked")
        for line in notes:
            print(line)
        for problem in problems:
            print(problem)
        print(f"rows {table.rows}, stages {CHAPTER_STAGES} x steps {CHAPTER_STEPS}, caps {caps[1:STORY_STAGE_LAST]}")
        print(f"failing: {len(problems)}")
        return 1 if problems else 0
    _json_out(chapters_json(table, caps, categories), args.output)
    return 0


# --- Map, door, exit, island and per-location tables (docs/formats/field-maps.md) ---------------------
#
# Offsets are module offsets (runtime address = base + offset; file offset = offset + 0x54). Tables that the
# game keeps as data are read from the modules; tables that only exist as code (switches and comparisons)
# are reproduced below with the address of the function that holds them.

FIELD_BASE, STORY_BASE = 0x090CED00, 0x08E9AA00
MAP_COUNT = 32
MAP_ARCHIVES = 0x2E798  # rel_field: 32 x ptr to "bg_NN_MM.ehp", by map index
MAP_MESHES = 0x2E298  # rel_field: 32 x 2 x ptr to the mesh members bound by world_bind_map_archive
MAP_DEBUG_NAMES = 0x2D120  # rel_field: one string "bg_NN_MM [NAME]\n..." (debug map menu)
DOOR_TABLE, DOOR_BLOCK, DOOR_ENTRY, DOORS_PER_MAP = 0x25334, 0x1B8, 0x2C, 10
MAP_LIGHTING = 0x28A7C  # rel_field: 32 x 5 periods x {u32 light mode, u32 sky gradient} (0x090d921c, 0x090dafc8)
SKY_GRADIENTS, SKY_GRADIENT_COUNT = 0x28A34, 6  # rel_field: 6 x {u32 top, middle, bottom} ABGR, 0x090dafc8
ISLAND_POSITIONS, ISLAND_AREAS = 0x298B0, 12  # rel_field: 12 x {i32 x, i32 y} screen pixels of the island areas
ISLAND_CONES = 0x29B74  # rel_field: 3 x f32 radians (75, 60, 45 degrees), tried widest last by 0x090e3c58
ISLAND_MARKER_OFFSET = (-0x11, -0x28)  # partner-event marker drawn at area position + offset (0x090e3854)
MARKER_HIDDEN_CELLS = {21: (0x28F7C, 14), 27: (0x28FEC, 120)}  # rel_field 0x090d9e78: map -> (table, pairs)
FOREST_SOUND_FACTOR = 0x293C8  # rel_field f32 at 0x090f80c8 (volume = factor x (18 - distance), 0..127)
EXIT_SELECTOR, EXIT_RECORD = 0x1F968, 18  # rel_story: 9 x u16, zero record ends the table
EXIT_CELLS = 0x1FB84  # rel_story: {u16 key, x, y}, three zeros end the table
FIXED_SPOTS, FIXED_SPOT_CHARS = 0x2238C, (127, 51, 128, 129, 130, 131, 132, 133, 134, 135, 136, 138, 140)
CHAR139_SPOTS, CHAR139_SPOT_COUNT = 0x21F0C, 72  # indexed by field save block byte +2 (daily random 0..71)
SELLER_SPOTS = 0x2E550  # 3 entries for characters 26/27 (system flag 4) and 140 when the partner is a seller
SPECIAL_CELL = (10000, 10001)  # placeholder cells expanded into scripted placements by world_send_npc_list
PERIODS = ("morning", "day", "sunset", "night", "midnight")  # light period 0..4 = field resources 2..6
ISLAND_ARCHIVE = "field/big_map/world_{}.ehp"
SCREEN = (480, 272)
DOOR_OPEN_DISTANCE = 0.75  # world units from the door position (0x090da588)
DOOR_SLIDE_SCALE = 1.5  # kind 0: offset = t x 1.5 x R(rotation) (amount, 0, 0) (0x090da8a8)
DOOR_SWING = 6.2831855  # kind 1: yaw += t x 2 pi x amount (0x090dab48)
# Light colour per light mode (ABGR immediates in rel_field 0x090d4c64).
LIGHT_MODE_COLOURS = {0: 0xFFFFEED8, 1: 0xFFFFFFFF, 2: 0xFF5AC8FF, 3: 0xFFFF8C78, 4: 0xFFBE7165}


def map_id_to_index(map_id):
    """rel_field 0x090d1144: field map id 1-5, 12-27, 29-32, 36-42 -> map index 0..31; anything else -> 0."""
    for first, last, index in ((1, 5, 0), (12, 27, 5), (29, 32, 21), (36, 42, 25)):
        if first <= map_id <= last:
            return index + map_id - first
    return 0


MAP_IDS = [m for m in range(1, 43) if map_id_to_index(m) or m == 1]
# rel_field 0x090d1270: field map id -> entry of field_strtbl_mapname.bin (location banner); 0 for others.
MAP_NAME_INDEX = {1: 5, 2: 2, 3: 1, 4: 3, 5: 7, 12: 50, 13: 40, 14: 41, 15: 42, 16: 43, 17: 44, 18: 45, 19: 46,
                  20: 47, 21: 48, 22: 55, 23: 10, 24: 11, 25: 39, 26: 12, 27: 15, 29: 13, 30: 54, 31: 9, 32: 17,
                  36: 53, 37: 50, 38: 46, 39: 53, 40: 49, 41: 17, 42: 14}
# rel_story 0x08e9ecfc world_location_to_map_id (story location -> field map id; default 30).
LOCATION_TO_MAP = {0: 30, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, **{loc: loc + 6 for loc in range(6, 22)},
                   22: 29, 23: 30, 24: 31, 25: 32, 26: 36, 27: 39, 28: 40, 29: 41, 30: 42}
# rel_story 0x08e9ebc8 world_map_id_to_location (the inverse; 37 and 38 are second versions of 6 and 13).
MAP_TO_LOCATION = {**{m: loc for loc, m in LOCATION_TO_MAP.items() if loc}, 37: 6, 38: 13}
# rel_field 0x090e4710 / 0x090e47d0: island area -> destination map ids (area 4 has five sub-points).
ISLAND_AREA_MAPS = {0: (12,), 1: (22,), 2: (23,), 3: (24,), 4: (1, 2, 3, 4, 5), 5: (26,), 6: (25,), 7: (27,),
                    8: (29,), 9: (30,), 10: (31,), 11: (32,)}
# rel_field 0x090d9cc8 world_get_door_cell_target: (maps, cell, target map id); stepping on it ends the walk with
# field action 17 (only acted on for maps 12 and 37).
DOOR_CELLS = (((12, 37), (15, 24), 13), ((12, 37), (15, 20), 14), ((12, 37), (15, 16), 40),
              ((12, 37), (15, 12), 40), ((12, 37), (13, 24), 17), ((12, 37), (13, 20), 18),
              ((12, 37), (13, 16), 19), ((12, 37), (13, 12), 20), ((12, 37), (13, 6), 21),
              ((36,), (9, 0), 39), ((36,), (10, 0), 39))
_DORM_DOORS = ((15, 24), (15, 20), (15, 16), (15, 12), (13, 24), (13, 20), (13, 16), (13, 12), (13, 6))
_CLASS_DOORS = ((1, 3), (1, 4), (10, 1), (11, 1), (21, 1), (22, 1))
# rel_field 0x090d93b0 (walkability test): cells reported blocked before the grid byte is read.
# "npc": test mode 0 (NPC wandering 0x090dc2a4, the partner's free-cell search 0x090dd8dc); "event": either
# mode while the field event flag (request 1, context +0x14) is set; "player_midnight": mode 1 (player collision
# 0x090d1df4) at light period 4.
WALK_BLOCKS = (
    {"maps": (3,), "when": "npc", "cells": ((14, 17), (14, 18))},
    {"maps": (2,), "when": "npc", "cells": _CLASS_DOORS},
    {"maps": (12, 37), "when": "npc", "cells": _DORM_DOORS},
    {"maps": (12, 37), "when": "player_midnight", "cells": _DORM_DOORS[:7]},
    {"maps": (2,), "when": "event", "cells": _CLASS_DOORS},
    {"maps": (12, 37), "when": "event", "cells": _DORM_DOORS},
)
# rel_field 0x090d0cc8 world_get_lab_special_cell (map 32): kind 1 -> field action 9, kind 2 -> action 10.
SPECIAL_CELLS = ((32, (32, 2), 1), (32, (33, 2), 1), (32, (30, 2), 2), (32, (31, 2), 2))
# rel_field 0x090dc0d8: looping sound 0x7a48 on map 29, volume from the distance to a point.
AMBIENT_SOUNDS = ({"map": 29, "sound": 0x7A48, "centre": (15.75, 9.75), "radius": 18.0},)
# rel_story 0x08ea09c8 world_place_player_on_arrival: arrival cell (x, y, direction) per story location when no
# event places the player. Each rule: (condition, x, y, direction); the first matching rule wins.
# Conditions: None (always), ("flag", n, set) system flag, ("from", L) previous location (field state +0x04),
# ("from_at", L, x_range, y_range) previous location and the player cell on the previous map (ranges are
# inclusive), ("from_flag", L) previous location L while the word returned by rel_story 0x08e9b460 is non-zero
# (meaning unknown; low). A rule with cell None means the code leaves the registers unset (undefined).
ARRIVAL = {
    1: ((None, 45, 31, 3),),
    2: ((("flag", 20, False), 11, 2, 1), (None, 8, 25, 1)),
    3: ((None, 31, 17, 3),),
    4: ((None, 46, 24, 3),),
    5: ((("flag", 6, True), 8, 10, 3), (None, 18, 9, 3)),  # flag 6 is cleared on use
    6: ((("from_at", 28, (11, 13), (12, 14)), 16, 16, 7), (("from_at", 28, (11, 13), (4, 6)), 16, 12, 7),
        (("from", 28), None, None, None),
        (("from", 15), 16, 6, 7), (("from", 14), 14, 12, 7), (("from", 13), 14, 16, 7), (("from", 12), 14, 20, 7),
        (("from", 11), 14, 24, 7), (("from", 10), 16, 12, 7), (("from", 9), 16, 16, 7), (("from", 8), 16, 20, 7),
        (("from", 7), 17, 24, 7), (None, 31, 29, 3)),
    **{loc: ((None, 11, 6, 3),) for loc in range(7, 13)},
    13: ((None, 9, 6, 3),),
    14: ((("from_flag", 6), 4, 4, 0), (("from", 6), 11, 6, 3), (None, 4, 4, 0)),
    15: ((None, 18, 2, 3),),
    16: ((None, 18, 1, 1),),
    17: ((None, 24, 28, 3),),
    18: ((None, 38, 40, 3),),
    19: ((None, 62, 10, 3),),
    20: ((None, 12, 1, 1),),
    21: ((None, 61, 31, 3),),
    22: ((None, 33, 61, 5),),
    23: ((None, 38, 44, 3),),
    24: ((None, 35, 47, 5),),
    25: ((None, 16, 2, 3),),
    26: ((("from", 27), 10, 2, 1), (None, 62, 54, 3)),
    27: ((None, 55, 32, 3),),
    28: ((("from_at", 6, (14, 16), (15, 17)), 11, 13, 3), (("from_at", 6, (14, 16), (11, 13)), 11, 5, 3)),
}
ARRIVAL_DEFAULT = (45, 31, 3)  # locations 0, 29, 30 and anything else


def _u32s(blob, offset, count, fmt="I"):
    return list(struct.unpack_from(f"<{count}{fmt}", blob, PRX_FILE_OFFSET + offset))


def _cstring(blob, offset):
    start = PRX_FILE_OFFSET + offset
    end = blob.index(b"\0", start)
    return blob[start:end].decode("ascii")


def _ptr_string(blob, pointer):
    return _cstring(blob, pointer) if pointer else None


def read_map_table(field):
    """Map index -> archive name and up to two mesh member names (rel_field +0x2e798 / +0x2e298)."""
    rows = []
    for index in range(MAP_COUNT):
        archive = _ptr_string(field, _u32s(field, MAP_ARCHIVES + 4 * index, 1)[0])
        meshes = [_ptr_string(field, p) for p in _u32s(field, MAP_MESHES + 8 * index, 2)]
        rows.append({"index": index, "archive": archive, "meshes": [m for m in meshes if m]})
    return rows


def read_debug_names(field):
    """bg_NN_MM -> debug name from the debug map menu string (rel_field +0x2d120)."""
    names = {}
    for line in _cstring(field, MAP_DEBUG_NAMES).split("\n"):
        stem, _, rest = line.partition(" ")
        if rest.startswith("[") and rest.endswith("]"):
            names[stem] = rest[1:-1]
    return names


def read_map_lighting(field):
    """Map index -> five {light mode, sky gradient} pairs, one per light period."""
    return [[tuple(_u32s(field, MAP_LIGHTING + 0x28 * index + 8 * period, 2)) for period in range(len(PERIODS))]
            for index in range(MAP_COUNT)]


def read_sky_gradients(field):
    return [tuple(_u32s(field, SKY_GRADIENTS + 12 * i, 3)) for i in range(SKY_GRADIENT_COUNT)]


def read_doors(field):
    """Door table (rel_field +0x25334): map index -> list of door entries (empty entries skipped)."""
    doors = []
    for index in range(MAP_COUNT):
        for slot in range(DOORS_PER_MAP):
            offset = DOOR_TABLE + DOOR_BLOCK * index + DOOR_ENTRY * slot
            name_ptr, kind, unused = _u32s(field, offset, 3)
            if not name_ptr:
                continue
            position = _u32s(field, offset + 0x0C, 3, "f")
            rotation = _u32s(field, offset + 0x18, 3, "f")
            amount, = _u32s(field, offset + 0x24, 1, "f")
            target, = _u32s(field, offset + 0x28, 1)
            doors.append({"map_index": index, "slot": slot, "mesh": _ptr_string(field, name_ptr), "kind": kind,
                          "unused_08": unused, "position": position, "rotation_degrees": rotation,
                          "amount": amount, "target_map": target})
    return doors


def read_island_positions(field):
    values = _u32s(field, ISLAND_POSITIONS, 2 * ISLAND_AREAS, "i")
    return [(values[2 * a], values[2 * a + 1]) for a in range(ISLAND_AREAS)]


def read_marker_hidden_cells(field):
    cells = {}
    for map_id, (offset, count) in MARKER_HIDDEN_CELLS.items():
        values = _u32s(field, offset, 2 * count, "i")
        cells[map_id] = [(values[2 * i], values[2 * i + 1]) for i in range(count)]
    return cells


def read_exit_selector(story):
    """Location selector (rel_story +0x1f968): records {location, group, conditions...} up to a zero record."""
    records = []
    offset = EXIT_SELECTOR
    while True:
        words = struct.unpack_from("<9H", story, PRX_FILE_OFFSET + offset)
        if not any(words):
            return records
        records.append({"location": words[0], "group": words[1], "stage_test": words[2], "stage": words[3],
                        "story_flag": words[4], "story_flag_mode": words[5], "record_char": words[6],
                        "record_bit": words[7], "record_mode": words[8]})
        offset += EXIT_RECORD


def read_exit_groups(story):
    """Exit-cell groups (rel_story +0x1fb84): group key -> list of (x, y)."""
    groups, key = {}, None
    offset = EXIT_CELLS
    while True:
        k, x, y = struct.unpack_from("<3H", story, PRX_FILE_OFFSET + offset)
        offset += 6
        if (k, x, y) == (0, 0, 0):
            return groups
        if k:
            key = k
            groups.setdefault(key, [])
        elif key is not None:
            groups[key].append((x, y))


def select_exit_group(selector, location, stage=1, story_flags=(), record_flags=()):
    """world_select_exit_group (rel_story 0x08eab224): the group of the first record of `location` whose
    conditions pass. A flag condition with mode 3 fails while the flag is clear, mode 4 fails while it is set,
    other modes always pass (as the code tests them)."""
    def passes(is_set, mode):
        return mode != 3 if not is_set else mode != 4
    for r in selector:
        if r["location"] != location:
            continue
        if r["stage_test"] and r["stage"] != stage:
            continue
        if r["story_flag"] and not passes(r["story_flag"] in story_flags, r["story_flag_mode"]):
            continue
        if r["record_char"] and not passes((r["record_char"], r["record_bit"]) in record_flags, r["record_mode"]):
            continue
        return r["group"]
    return None


def read_fixed_spots(story):
    """Fixed NPC positions of world_get_fixed_npc_spot (rel_story 0x08eab500), as {location, x, y, direction}."""
    def entries(offset, count):
        return [tuple(_u32s(story, offset + 16 * i, 4, "i")) for i in range(count)]
    return {"fixed": dict(zip(FIXED_SPOT_CHARS, entries(FIXED_SPOTS, len(FIXED_SPOT_CHARS)))),
            "char139": entries(CHAR139_SPOTS, CHAR139_SPOT_COUNT),
            "sellers": entries(SELLER_SPOTS, 3)}


def island_area_of_map(map_id):
    """rel_field 0x090e47d0: map id -> (area, sub-point); the dorm rooms belong to area 0; unknown -> (4, 0)."""
    if 13 <= map_id <= 21 or map_id in (37, 38):
        return 0, 0
    for area, maps in ISLAND_AREA_MAPS.items():
        if map_id in maps:
            return area, maps.index(map_id)
    return 4, 0


def walk_blocked(map_id, x, y, npc=False, midnight=False, event=False):
    """The overrides of rel_field 0x090d93b0: True when the cell is reported blocked before the grid byte."""
    for rule in WALK_BLOCKS:
        if map_id not in rule["maps"] or (x, y) not in rule["cells"]:
            continue
        when = rule["when"]
        if (when == "npc" and npc) or (when == "event" and event) or \
                (when == "player_midnight" and midnight and not npc):
            return True
    return False


def arrival_cell(location, previous=None, previous_cell=None, system_flags=(), flag_08e9b460=False):
    """world_place_player_on_arrival (rel_story 0x08ea09c8) without an event: (x, y, direction) or None when
    the code leaves the result undefined (location 6 from 28 and location 28 outside the door ranges)."""
    rules = ARRIVAL.get(location)
    if rules is None:
        return ARRIVAL_DEFAULT
    for condition, x, y, direction in rules:
        if x is None and condition is not None and condition[0] == "from" and previous == condition[1]:
            return None
        if condition is None:
            return x, y, direction
        kind = condition[0]
        if kind == "flag" and (condition[1] in system_flags) == condition[2]:
            return x, y, direction
        if kind == "from" and previous == condition[1]:
            return x, y, direction
        if kind == "from_at" and previous == condition[1] and previous_cell is not None:
            (x0, x1), (y0, y1) = condition[2], condition[3]
            if x0 <= previous_cell[0] <= x1 and y0 <= previous_cell[1] <= y1:
                return x, y, direction
        if kind == "from_flag" and flag_08e9b460 and previous == condition[1]:
            return x, y, direction
    return None


def abgr_hex(value):
    """ABGR word (PSP GE colour) -> '#rrggbbaa'."""
    a, b, g, r = (value >> 24) & 0xFF, (value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF
    return f"#{r:02x}{g:02x}{b:02x}{a:02x}"


class Disc:
    """The field tables of one extracted disc (USRDIR)."""

    def __init__(self, usrdir):
        self.usrdir = Path(usrdir)
        self.field = (self.usrdir / "gmodule" / "rel_field.prx").read_bytes()
        self.story = (self.usrdir / "gmodule" / "rel_story.prx").read_bytes()
        self.maps = read_map_table(self.field)
        self.debug_names = read_debug_names(self.field)
        self.lighting = read_map_lighting(self.field)
        self.gradients = read_sky_gradients(self.field)
        self.doors = read_doors(self.field)
        self.island = read_island_positions(self.field)
        self.marker_hidden = read_marker_hidden_cells(self.field)
        self.selector = read_exit_selector(self.story)
        self.exit_groups = read_exit_groups(self.story)
        self.spots = read_spots(self.story)
        self.fixed_spots = read_fixed_spots(self.story)
        self.forest_factor, = _u32s(self.field, FOREST_SOUND_FACTOR, 1, "f")
        self._archives = {}

    def archive_members(self, name):
        if name not in self._archives:
            path = self.usrdir / "field" / "map" / name
            self._archives[name] = dict(_load("ehp").parse(path.read_bytes())) if path.is_file() else None
        return self._archives[name]

    def map_names(self, language="eng"):
        """field_strtbl_mapname.bin of always_bri_<language>.ehp (the variant the field module loads)."""
        path = self.usrdir / "field" / f"always_bri_{language}.ehp"
        members = dict(_load("ehp").parse(path.read_bytes()))
        return _load("strtbl").parse(members["field_strtbl_mapname.bin"])["strings"]

    def map_row(self, map_id):
        index = map_id_to_index(map_id)
        row = self.maps[index]
        stem = row["archive"].rsplit(".", 1)[0]
        return index, row, stem

    def walk_grid(self, archive):
        members = self.archive_members(archive) or {}
        for name, blob in members.items():
            if name.endswith(".hmp"):
                return name, WalkGrid(blob)
        return None, None


def tables_json(disc):
    """The map, door, exit, island and spot tables as one neutral dictionary."""
    maps = []
    for map_id in MAP_IDS:
        index, row, stem = disc.map_row(map_id)
        maps.append({"map_id": map_id, "map_index": index, "archive": "field/map/" + row["archive"],
                     "meshes": row["meshes"], "debug_name": disc.debug_names.get(stem),
                     "name_index": MAP_NAME_INDEX.get(map_id, 0), "location": MAP_TO_LOCATION.get(map_id),
                     "island_area": list(island_area_of_map(map_id)),
                     "lighting": [{"period": PERIODS[p], "light_mode": mode, "sky_gradient": gradient}
                                  for p, (mode, gradient) in enumerate(disc.lighting[index])]})
    return {
        "source": "rel_field.prx / rel_story.prx (docs/formats/field-maps.md)",
        "periods": list(PERIODS),
        "light_modes": {str(k): abgr_hex(v) for k, v in LIGHT_MODE_COLOURS.items()},
        "sky_gradients": [[abgr_hex(c) for c in g] for g in disc.gradients],
        "maps": maps,
        "location_to_map": {str(k): v for k, v in LOCATION_TO_MAP.items()},
        "doors": [dict(d, map_id=MAP_IDS[d["map_index"]]) for d in disc.doors],
        "door_cells": [{"maps": list(maps_), "cell": list(cell), "target_map": target}
                       for maps_, cell, target in DOOR_CELLS],
        "walk_blocks": [{"maps": list(r["maps"]), "when": r["when"], "cells": [list(c) for c in r["cells"]]}
                        for r in WALK_BLOCKS],
        "special_cells": [{"map": m, "cell": list(c), "kind": k} for m, c, k in SPECIAL_CELLS],
        "marker_hidden_cells": {str(m): [list(c) for c in cells] for m, cells in disc.marker_hidden.items()},
        "exit_selector": disc.selector,
        "exit_groups": {str(k): [list(c) for c in v] for k, v in sorted(disc.exit_groups.items())},
        "arrival": {str(loc): [{"condition": list(c) if c else None, "cell": [x, y], "direction": d}
                               for c, x, y, d in rules] for loc, rules in ARRIVAL.items()},
        "arrival_default": list(ARRIVAL_DEFAULT),
        "island": island_json(disc),
        "npc_spots": [{"index": i, "location": s[0], "cell": [s[1], s[2]], "direction": s[3]}
                      for i, s in enumerate(disc.spots)],
        "fixed_npc_spots": {
            "by_character": {str(c): list(v) for c, v in disc.fixed_spots["fixed"].items()},
            "character_139": [list(v) for v in disc.fixed_spots["char139"]],
            "sellers": [list(v) for v in disc.fixed_spots["sellers"]]},
        "ambient_sounds": [dict(a, factor=disc.forest_factor) for a in AMBIENT_SOUNDS],
    }


def island_json(disc):
    archives = []
    for period in PERIODS:
        relative = ISLAND_ARCHIVE.format(period)
        path = disc.usrdir / relative
        members = [name for name, _ in _load("ehp").parse(path.read_bytes())] if path.is_file() else []
        archives.append({"period": period, "archive": relative, "members": members})
    cones = _u32s(disc.field, ISLAND_CONES, 3, "f")
    return {"screen": list(SCREEN), "marker_offset": list(ISLAND_MARKER_OFFSET),
            "cone_radians": cones,
            "areas": [{"area": a, "position": list(disc.island[a]), "maps": list(ISLAND_AREA_MAPS[a])}
                      for a in range(ISLAND_AREAS)],
            "archives": archives}


def _mesh_textures(members, mesh):
    """Texture names of a TGMS mesh and the GIM member each resolves to (tools/tgm.py); [] if unreadable."""
    try:
        tgm = _load("tgm")
        tms = tgm.Tms(members[mesh])
        out = []
        for texture in tms.textures:
            gim, _ = tgm.texture_member(texture["name"], members)
            out.append({"name": texture["name"], "gim": gim})
        return out
    except Exception:  # the mesh parser is optional for this export
        return []


def location_json(disc, map_id, names=None, heights=True):
    """Everything the port needs to set up one field map, as a neutral dictionary."""
    index, row, stem = disc.map_row(map_id)
    archive = row["archive"]
    members = disc.archive_members(archive) or {}
    meshes = []
    for mesh in row["meshes"]:
        base = mesh[:-4]
        meshes.append({"member": mesh, "mask": base + "_mask.tms" if base + "_mask.tms" in members else None,
                       "node_animation": base + ".tmt" if base + ".tmt" in members else None,
                       "texture_animation": base + ".tma" if base + ".tma" in members else None,
                       "textures": _mesh_textures(members, mesh)})
    grid_name, grid = disc.walk_grid(archive)
    grid_json = None
    if grid:
        x0, y0, z0 = grid.origin()
        grid_json = {"member": grid_name, "columns": grid.columns, "rows": grid.rows, "cell_size": CELL_SIZE,
                     "origin": [x0, y0, z0], "cells": grid.grid_text().split("\n"),
                     "cell_legend": {"#": "walkable (1)", ".": "blocked (0)"}}
        if heights:
            width = grid.columns + 1
            grid_json["vertex_heights"] = [[round(grid.vertices[r * width + c][1] - y0, 5)
                                            for c in range(width)] for r in range(grid.rows + 1)]
    locations = sorted(loc for loc, m in LOCATION_TO_MAP.items() if m == map_id and loc)
    if not locations and map_id in MAP_TO_LOCATION:
        locations = [MAP_TO_LOCATION[map_id]]
    exits = {}
    for loc in locations:
        group = select_exit_group(disc.selector, loc)
        exits[str(loc)] = {"group": group, "cells": [list(c) for c in disc.exit_groups.get(group, [])]}
    doors = [{"mesh": d["mesh"], "kind": d["kind"], "position": d["position"],
              "rotation_degrees": d["rotation_degrees"], "amount": d["amount"], "target_map": d["target_map"]}
             for d in disc.doors if d["map_index"] == index]
    spots = [{"index": i, "location": s[0], "cell": [s[1], s[2]], "direction": s[3]}
             for i, s in enumerate(disc.spots) if s[0] in locations]
    fixed = [{"character": c, "cell": [v[1], v[2]], "direction": v[3]}
             for c, v in disc.fixed_spots["fixed"].items() if v[0] in locations]
    fixed += [{"character": 139, "slot": i, "cell": [v[1], v[2]], "direction": v[3]}
              for i, v in enumerate(disc.fixed_spots["char139"]) if v[0] in locations]
    fixed += [{"characters": [26, 27, 140], "slot": i, "cell": [v[1], v[2]], "direction": v[3]}
              for i, v in enumerate(disc.fixed_spots["sellers"]) if v[0] in locations]
    area, sub = island_area_of_map(map_id)
    out = {
        "map_id": map_id, "map_index": index, "locations": locations,
        "archive": "field/map/" + archive, "debug_name": disc.debug_names.get(stem),
        "name_index": MAP_NAME_INDEX.get(map_id, 0),
        "meshes": meshes,
        "door_meshes": sorted({d["mesh"] for d in doors}),
        "textures": sorted(n for n in members if n.lower().endswith(".gim")),
        "lighting": [{"period": PERIODS[p], "light_mode": mode,
                      "light_colour": abgr_hex(LIGHT_MODE_COLOURS.get(mode, 0)),
                      "sky_gradient": [abgr_hex(c) for c in disc.gradients[gradient]]
                      if gradient < len(disc.gradients) else None}
                     for p, (mode, gradient) in enumerate(disc.lighting[index])],
        "walk_grid": grid_json,
        "exits": exits,
        "doors": doors,
        "door_cells": [{"cell": list(c), "target_map": t} for maps_, c, t in DOOR_CELLS if map_id in maps_],
        "walk_blocks": [{"when": r["when"], "cells": [list(c) for c in r["cells"]]}
                        for r in WALK_BLOCKS if map_id in r["maps"]],
        "special_cells": [{"cell": list(c), "kind": k} for m, c, k in SPECIAL_CELLS if m == map_id],
        "marker_hidden_cells": [list(c) for c in disc.marker_hidden.get(map_id, [])],
        "arrival": {str(loc): [{"condition": list(c) if c else None, "cell": [x, y], "direction": d}
                               for c, x, y, d in ARRIVAL.get(loc, ((None,) + ARRIVAL_DEFAULT,))]
                    for loc in locations},
        "npc_spots": spots,
        "fixed_npc_spots": fixed,
        "island_area": {"area": area, "sub_point": sub},
        "ambient_sounds": [dict(a, factor=disc.forest_factor) for a in AMBIENT_SOUNDS if a["map"] == map_id],
    }
    if names is not None:
        out["name"] = names[out["name_index"]] if out["name_index"] < len(names) else None
    return out


def _cell_ok(grid, x, y):
    return grid is not None and 0 <= x < grid.columns and 0 <= y < grid.rows and grid.cell(x, y) == 1


def check_disc(disc):
    """Cross-checks of the tables against each other and against the archives; returns (problems, notes)."""
    problems, notes = [], []
    grids = {}
    for map_id in MAP_IDS:
        index, row, stem = disc.map_row(map_id)
        members = disc.archive_members(row["archive"])
        if members is None:
            problems.append(f"map {map_id}: archive {row['archive']} missing")
            continue
        for mesh in row["meshes"]:
            if mesh not in members:
                problems.append(f"map {map_id}: mesh {mesh} not in {row['archive']}")
        grids[map_id] = disc.walk_grid(row["archive"])[1]
        if grids[map_id] is None:
            problems.append(f"map {map_id}: no walk grid")
        for p, (mode, gradient) in enumerate(disc.lighting[index]):
            if mode not in LIGHT_MODE_COLOURS or gradient >= len(disc.gradients):
                problems.append(f"map {map_id} period {p}: light mode {mode} / gradient {gradient} out of range")
    for door in disc.doors:
        map_id = MAP_IDS[door["map_index"]]
        members = disc.archive_members(disc.maps[door["map_index"]]["archive"]) or {}
        if door["mesh"] not in members:
            problems.append(f"door {map_id}/{door['slot']}: mesh {door['mesh']} not in the archive")
        if door["target_map"] and door["target_map"] not in MAP_IDS:
            problems.append(f"door {map_id}/{door['slot']}: target {door['target_map']} is not a map id")
        if door["kind"] not in (0, 1):
            problems.append(f"door {map_id}/{door['slot']}: kind {door['kind']}")
    for loc, map_id in LOCATION_TO_MAP.items():
        if loc and MAP_TO_LOCATION.get(map_id) != loc and map_id != 30:
            problems.append(f"location {loc}: map {map_id} does not map back")
    seen_groups, exit_total, exit_inert = set(), 0, 0
    for record in disc.selector:
        loc = record["location"]
        group = record["group"]
        seen_groups.add(group)
        if group not in disc.exit_groups:
            problems.append(f"selector location {loc}: group {group} has no cells")
            continue
        grid = grids.get(LOCATION_TO_MAP.get(loc))
        cells = disc.exit_groups[group]
        bad = [c for c in cells if not _cell_ok(grid, *c)]
        exit_total += len(cells)
        exit_inert += len(bad)
        if bad:  # the player cannot stand on a blocked or off-grid cell, so these never trigger
            notes.append(f"location {loc}: exit cells {bad} are blocked or off map {LOCATION_TO_MAP.get(loc)}")
        if len(bad) == len(cells):  # tolerated only on the event-only maps 36-42
            (problems if LOCATION_TO_MAP.get(loc) < 36 else notes).append(
                f"location {loc}: no reachable exit cell on map {LOCATION_TO_MAP.get(loc)}")
        if group != LOCATION_TO_MAP.get(loc):
            notes.append(f"location {loc}: exit group {group} differs from its map id {LOCATION_TO_MAP.get(loc)}")
    for maps_, cell, target in DOOR_CELLS:
        for map_id in maps_:
            grid = grids.get(map_id)
            if grid is None or not (0 <= cell[0] < grid.columns and 0 <= cell[1] < grid.rows):
                problems.append(f"door cell {cell} outside map {map_id}")
        if target not in MAP_IDS:
            problems.append(f"door cell {cell}: target {target} is not a map id")
    for loc, rules in ARRIVAL.items():
        grid = grids.get(LOCATION_TO_MAP[loc])
        for _, x, y, _ in rules:
            if x is not None and not _cell_ok(grid, x, y):
                problems.append(f"arrival cell ({x}, {y}) of location {loc} not walkable")
    spot_bad = 0
    for i, (loc, x, y, _) in enumerate(disc.spots):
        if not _cell_ok(grids.get(LOCATION_TO_MAP.get(loc)), x, y):
            spot_bad += 1
            notes.append(f"spot {i}: cell ({x}, {y}) of location {loc} not walkable")
    fixed = list(disc.fixed_spots["fixed"].values()) + disc.fixed_spots["char139"] + disc.fixed_spots["sellers"]
    fixed_bad = 0
    for loc, x, y, _ in fixed:
        if x in SPECIAL_CELL or x < 0:
            continue
        if not _cell_ok(grids.get(LOCATION_TO_MAP.get(loc)), x, y):
            fixed_bad += 1
            notes.append(f"fixed spot ({loc}, {x}, {y}) not walkable")
    for area, (x, y) in enumerate(disc.island):
        if not (0 <= x < SCREEN[0] and 0 <= y < SCREEN[1]):
            problems.append(f"island area {area}: position ({x}, {y}) off screen")
        for sub, map_id in enumerate(ISLAND_AREA_MAPS[area]):
            if island_area_of_map(map_id) != (area, sub):
                problems.append(f"island area {area}/{sub}: map {map_id} does not map back")
    for period in PERIODS:
        path = disc.usrdir / ISLAND_ARCHIVE.format(period)
        if not path.is_file():
            problems.append(f"island archive {path.name} missing")
    for map_id, cells in disc.marker_hidden.items():
        bad = [c for c in cells if not (0 <= c[0] < grids[map_id].columns and 0 <= c[1] < grids[map_id].rows)]
        if bad:
            problems.append(f"marker-hidden cells {bad} outside map {map_id}")
    texture_total = texture_missing = 0
    for row in disc.maps:
        members = disc.archive_members(row["archive"]) or {}
        for mesh in row["meshes"]:
            if mesh in members:
                textures = _mesh_textures(members, mesh)
                texture_total += len(textures)
                texture_missing += sum(1 for t in textures if t["gim"] is None)
    if texture_missing:
        problems.append(f"{texture_missing} of {texture_total} mesh texture names have no GIM member")
    notes.append(f"mesh textures: {texture_total - texture_missing}/{texture_total} resolve to a GIM member")
    notes.append(f"exit cells: {exit_total - exit_inert}/{exit_total} walkable; "
                 f"spots: {len(disc.spots) - spot_bad}/{len(disc.spots)} on walkable cells; "
                 f"fixed spots: {fixed_bad} off walkable cells")
    return problems, notes


def _json_out(data, output):
    import json
    text = json.dumps(data, indent=1, ensure_ascii=False)
    if output:
        if not _output_allowed(output):
            raise SystemExit(f"{output}: game data goes outside the repository or under extracted/")
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(text + "\n", encoding="utf-8")
    else:
        sys.stdout.write(text + "\n")


def _output_allowed(path):
    """Derived game data goes outside the repository or under an extracted/ directory."""
    resolved = Path(path).resolve()
    if "extracted" in (part.lower() for part in resolved.parts):
        return True
    try:
        resolved.relative_to(Path(__file__).resolve().parent.parent)
    except ValueError:
        return True
    return False


def cmd_tables(args):
    disc = Disc(args.usrdir)
    data = tables_json(disc)
    if args.table:
        data = {"source": data["source"], args.table: data[args.table]}
    if args.check:
        problems, notes = check_disc(disc)
        for line in notes if args.verbose else notes[-2:]:
            print(line)
        for problem in problems:
            print(problem)
        print(f"maps {len(MAP_IDS)}, doors {len(disc.doors)}, exit groups {len(disc.exit_groups)}, "
              f"selector records {len(disc.selector)}, island areas {len(disc.island)}")
        print(f"failing: {len(problems)}")
        return 1 if problems else 0
    _json_out(data, args.output)
    return 0


def cmd_locations(args):
    disc = Disc(args.usrdir)
    names = disc.map_names(args.language) if args.names else None
    wanted = [LOCATION_TO_MAP[args.location]] if args.location is not None else \
        [args.map] if args.map is not None else MAP_IDS
    if args.output_dir and not _output_allowed(args.output_dir):
        raise SystemExit(f"{args.output_dir}: game data goes outside the repository or under extracted/")
    for map_id in wanted:
        data = location_json(disc, map_id, names, heights=not args.no_heights)
        if args.output_dir:
            _json_out(data, str(Path(args.output_dir) / f"map_{map_id:02d}.json"))
        elif not args.summary:
            _json_out(data, None)
        if args.summary or args.output_dir:
            grid = data["walk_grid"]
            exits = sum(len(e["cells"]) for e in data["exits"].values())
            size = f"{grid['columns']}x{grid['rows']}" if grid else "-"
            print(f"map {map_id:2d} locations {data['locations']}: {data['archive']}, "
                  f"grid {size}, exits {exits}, doors {len(data['doors'])}, "
                  f"door cells {len(data['door_cells'])}, spots {len(data['npc_spots'])}, "
                  f"meshes {len(data['meshes'])}, textures {len(data['textures'])}")
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
    chapters = sub.add_parser("chapters", help="rel_story partner chapter table and points caps as JSON")
    chapters.add_argument("usrdir", help="PSP_GAME/USRDIR of the extracted disc")
    chapters.add_argument("--boot", help="BOOT.BIN for the character categories (default: ../SYSDIR/BOOT.BIN)")
    chapters.add_argument("-o", "--output", help="JSON file (outside the repository or under extracted/)")
    chapters.add_argument("--check", action="store_true",
                          help="check every row against the story records, the locations and the categories")
    chapters.set_defaults(func=cmd_chapters)
    tables = sub.add_parser("tables", help="map, door, exit, island and spot tables of rel_field/rel_story as JSON")
    tables.add_argument("usrdir", help="PSP_GAME/USRDIR of the extracted disc")
    tables.add_argument("-o", "--output", help="JSON file (outside the repository or under extracted/)")
    tables.add_argument("--table", choices=("maps", "doors", "door_cells", "walk_blocks", "special_cells",
                                            "marker_hidden_cells", "exit_selector", "exit_groups", "arrival",
                                            "island", "npc_spots", "fixed_npc_spots", "location_to_map",
                                            "sky_gradients", "light_modes", "ambient_sounds"),
                        help="export one table only")
    tables.add_argument("--check", action="store_true", help="cross-check the tables against the disc")
    tables.add_argument("-v", "--verbose", action="store_true", help="with --check: print every note")
    tables.set_defaults(func=cmd_tables)
    locations = sub.add_parser("locations", help="one neutral JSON per field map: art, grid, exits, doors, spots")
    locations.add_argument("usrdir", help="PSP_GAME/USRDIR of the extracted disc")
    locations.add_argument("-o", "--output-dir", help="write map_MM.json files here (outside the repository)")
    which = locations.add_mutually_exclusive_group()
    which.add_argument("--map", type=int, help="one field map id")
    which.add_argument("--location", type=int, help="one story location (converted with world_location_to_map_id)")
    locations.add_argument("--names", action="store_true", help="add the place name (field_strtbl_mapname.bin)")
    locations.add_argument("--language", default="eng", help="language of --names (eng ger fra ita spa)")
    locations.add_argument("--no-heights", action="store_true", help="leave out the vertex height grid")
    locations.add_argument("--summary", action="store_true", help="print one line per map instead of JSON")
    locations.set_defaults(func=cmd_locations)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
