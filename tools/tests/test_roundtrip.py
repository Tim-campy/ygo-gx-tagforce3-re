#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for the format writers and tools/roundtrip.py, on synthetic data only (no game data).

Run with: python3 -I tools/tests/test_roundtrip.py
"""

import importlib.util
import json
import random
import struct
import tempfile
import types
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(f"rt_{name}", TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


roundtrip = load("roundtrip")
tool = roundtrip.tool
PAYLOAD = 0x54  # file offset of module offset 0 in fake_elf (as in the game's modules and BOOT.BIN)


def fake_elf(size):
    """A minimal PRX-like ELF: one PT_LOAD segment and one allocated section, both at module offset 0 and file
    offset 0x54, plus a section-name table (what tables.py, prx_imports.Elf and the Module classes read)."""
    shoff = PAYLOAD + size
    names = b"\0.data\0.shstrtab\0"
    header = bytearray(0x34)
    header[:7] = b"\x7fELF\x01\x01\x01"
    struct.pack_into("<HHI", header, 0x10, 0xFFA0, 8, 1)
    struct.pack_into("<4I", header, 0x18, 0, 0x34, shoff, 0)
    struct.pack_into("<6H", header, 0x28, 0x34, 32, 1, 40, 3, 2)
    program = struct.pack("<8I", 1, PAYLOAD, 0, 0, size, size, 7, 16)
    sections = (bytes(40) + struct.pack("<10I", 1, 1, 3, 0, PAYLOAD, size, 0, 0, 4, 0)
                + struct.pack("<10I", 7, 3, 0, 0, shoff + 120, len(names), 0, 0, 1, 0))
    return bytearray(bytes(header) + program + bytes(size) + sections + names)


def put(elf, module_offset, raw):
    elf[PAYLOAD + module_offset:PAYLOAD + module_offset + len(raw)] = raw


def pattern(size, seed):
    return random.Random(seed).randbytes(size)


class RewriteHelperTest(unittest.TestCase):
    def test_detects_a_byte_the_writer_does_not_write(self):
        data = bytes(range(16))
        lazy = lambda blob, model: blob  # noqa: E731 - writes nothing
        self.assertTrue(roundtrip.rewrite_problems("t", data, [(4, 4)], lazy, None))

        def exact(blob, model):
            out = bytearray(blob)
            out[4:8] = model
            return bytes(out)
        self.assertEqual(roundtrip.rewrite_problems("t", data, [(4, 4)], exact, data[4:8]), [])

    def test_every_writer_check_is_listed(self):
        ids = set(roundtrip.CHECKS)
        for key in ("cardinfo_ehp", "snd_cue", "ptrs_txt", "save_stored_decks", "hmp", "ydq"):
            self.assertIn(key, ids)


class CardInfoWriterTest(unittest.TestCase):
    # Huffman tree: 'A' = 0, 'B' = 10, end = 11 (internal nodes two u16 offsets, leaves 0, 0, symbol).
    HUFF = [4, 10, 0, 0, ord("A"), 14, 20, 0, 0, ord("B"), 0, 0, 0]

    def model(self):
        prop = {"id": 0xE88, "atk": 3000, "def": 2500, "kind": 1, "attribute": 1, "level": 8, "icon": 0,
                "race": 1, "unknown_22": 4}
        empty = dict.fromkeys(prop, 0)
        return {"suffix": "E", "order": None,
                "prop": [empty, prop, {**prop, "id": 0xE8A, "atk": 0, "kind": 27, "icon": 5, "unknown_22": 0}],
                "pass": [0, 12345678, 0], "intid": [1, 0, 2], "names": ["", "Ab", "Cde"], "huff": self.HUFF,
                "descriptions": ["", "AB", "BAAB"], "dict": {"words": ["%c3722", "w"], "gap": 4},
                "genre": [0, 1 << 37 | 2, 1 << 45], "sort": [0, 1, 2], "top": [(ord("*"), 0xE88), (ord("A"), 0xE88)],
                "samepict": [(1, 3)], "dialog": ["", "Hi", "abc$C1"]}

    def test_model_round_trip(self):
        cardinfo = tool("cardinfo")
        model = self.model()
        archive = cardinfo.encode_archive(model)
        decoded = cardinfo.decode_archive(archive)
        for key in ("prop", "pass", "intid", "names", "huff", "descriptions", "dict", "genre", "sort", "dialog"):
            self.assertEqual(decoded[key], model[key], key)
        self.assertEqual([tuple(p) for p in decoded["top"]], model["top"])
        self.assertEqual(cardinfo.encode_archive(decoded), archive)
        self.assertEqual(cardinfo.roundtrip_problems(archive), [])
        info = cardinfo.CardInfo(archive, "E")
        self.assertEqual(info.name(2), "Cde")
        self.assertEqual(info.huffman(info.entry(2)[1])[0], "BAAB")

    def test_layout_details(self):
        cardinfo = tool("cardinfo")
        huff = struct.pack(f"<{len(self.HUFF)}H", *self.HUFF)
        self.assertEqual(cardinfo.huffman_codes(huff), {ord("A"): "0", ord("B"): "10", 0: "11"})
        stream, starts, length = cardinfo.build_descriptions(["AB", ""], huff)
        self.assertEqual((stream, starts, length), (bytes([0b01011110]), [0, 5], 7))
        pool, offsets = cardinfo.utf16_aligned_pool(["", "ab", "c"], lead=bytes(4))
        self.assertEqual(offsets, [4, 8, 16])
        self.assertEqual(len(pool), 20)
        blob = cardinfo.build_dictionary(["x"])
        self.assertEqual(struct.unpack_from("<3I", blob), (1, 12, 20))
        self.assertEqual(cardinfo.parse_dictionary(blob), {"words": ["x"], "gap": 4})
        self.assertEqual(cardinfo.pack_prop(cardinfo.unpack_prop(0xFFFFFFFF, 0xFFFFFFFF)), (0xFFFFFFFF, 0xFFFFFFFF))


class ShopDeckWriterTest(unittest.TestCase):
    def test_pack_table(self):
        tables = tool("tables")
        elf = fake_elf(0x22000)
        lists = 0x20900
        packs = []
        for index in range(tables.PACK_COUNT):
            tiers = [(index + 1, index + 2), (), (7000 + index,), (5000, 5001, 5002)]
            addresses, position = [], lists + 0x40 * index
            for ids in tiers:
                addresses.append(position if ids else 0)
                position += 2 * len(ids)
            packs.append({"pack": index, "a": 9 << 2, "price": 100 + index, "flags": index & 3, "tiers": tiers,
                          "descriptor": 0x1F000 + 32 * index,
                          "tier_addresses": addresses})
        prx = tables.write_packs(bytes(elf), packs)
        read = tables.read_packs(prx)
        self.assertEqual([[tuple(t) for t in p["tiers"]] for p in read], [[tuple(t) for t in p["tiers"]] for p in packs])
        self.assertEqual(roundtrip.rewrite_problems("packs", prx, tables.pack_spans(prx, read), tables.write_packs,
                                                    read), [])

    def test_limit_list(self):
        tables = tool("tables")
        elf = fake_elf(tables.LIMIT_TABLE - tables.BOOT_BASE + 4 * tables.LIMIT_COUNT)
        limits = [(4000 + k, k % 3) for k in range(tables.LIMIT_COUNT)]
        boot = tables.write_limits(bytes(elf), limits)
        self.assertEqual(tables.read_limits(boot), limits)
        self.assertEqual(roundtrip.rewrite_problems("limits", boot, [tables.limit_span(boot)], tables.write_limits,
                                                    limits), [])
        with self.assertRaises(ValueError):
            tables.write_limits(boot, limits[:-1])

    def test_recipe_tables_and_card_lists(self):
        decks = tool("decks")
        elf = bytes(fake_elf(decks.VARIANT_TABLE - decks.BOOT_BASE + 12 * decks.VARIANT_COUNT))
        owners = [(k + 1, 3 * k, 3, 0) for k in range(decks.OWNER_COUNT)]
        levels = [1 + k % 10 for k in range(decks.LEVEL_COUNT)]
        variants = [(k + 1, k % 4, k % 3) for k in range(decks.VARIANT_COUNT)]
        boot = decks.write_variants(decks.write_levels(decks.write_owners(elf, owners), levels), variants)
        spans = decks.table_spans(boot)
        self.assertEqual(decks.parse_records(boot, spans["owners"][0] - 0, decks.OWNER_COUNT, "<4I"), owners)
        table = decks.CARD_LIST_TABLE - decks.BOOT_BASE
        lists, position = [], table - 4 * 3 * decks.CARD_LIST_COUNT
        for k in range(decks.CARD_LIST_COUNT):
            ids = [4000 + k, 4001 + k, 4002 + k][:k % 4]
            lists.append((position if ids else 0x5BD800 + 4 * k, ids))
            position += 2 * len(ids) + (2 * len(ids)) % 4
        boot = decks.write_card_lists(boot, lists)
        self.assertEqual(decks.read_card_lists(boot), lists)
        self.assertEqual(roundtrip.rewrite_problems("card lists", boot, decks.card_list_spans(boot, lists),
                                                    decks.write_card_lists, lists), [])

    def test_small_deck_files(self):
        decks = tool("decks")
        pairs = [(4007, 1), (4007, 2), (4041, 1)]
        self.assertEqual(decks.read_same_card(decks.build_same_card(pairs)), pairs)
        ids = [0, 3720, 3721, 7993]
        self.assertEqual(decks.read_file_table(decks.build_file_table(ids)), ids)
        for op, fmt in decks.TUTORIAL_ARGS.items():
            self.assertEqual(struct.calcsize(fmt) + 1, decks.TUTORIAL_LENGTHS[op], hex(op))
        script = [(0x01, (5, 60, 96, 360)), (0x0D, (2,)), (0x0A, (0, 30)), (0x0E, ()), (0x16, (1, 0, 0x10)),
                  (0x17, ())]
        blob = decks.tutorial_build(script)
        self.assertEqual(len(blob), sum(decks.TUTORIAL_LENGTHS[op] for op, _ in script))
        self.assertEqual(decks.tutorial_decode(blob), script)
        with self.assertRaises(ValueError):
            decks.tutorial_build([(0x18, ())])


class SoundWriterTest(unittest.TestCase):
    def riff(self, length):
        fmt = struct.pack("<HHIIHH", 0x0270, 1, 44100, 16538, 192, 0)
        body = (b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", length)
                + bytes(length))
        return b"RIFF" + struct.pack("<I", len(body)) + body

    def test_bank_with_adpcm_layers(self):
        sound = tool("sound")
        cue = {"volume": 0x7F, "pan": 0x40, "flags": 0, "unknown_4": 0, "layers": 0, "unknown_10": 2,
               "unknown_11": 0, "duration_ms": 10}
        envelope = {"volume": 0x7F, "pan": 0x40, "unknown_2": 0, "adsr": 0x1FE0800F, "loop_a": 1, "loop_b": 1,
                    "unknown_c": 0, "note": 60, "pitch": 0x1000, "rest": bytes(8)}
        model = {"serial": 3, "size": 4096, "label": "1 TEST", "music": False,
                 "cues": [{**cue, "wave": 1}, {**cue, "wave": 0}, {**cue, "layers": 2, "layer": 0}],
                 "layers": [{"sample": 0, "envelope": 0}, {"sample": 1, "envelope": 0}],
                 "samples": [{"pitch": 2048, "rate": 22050, "adpcm": bytes(16) + bytes([0, 7]) + bytes(14)},
                             {"pitch": 4096, "rate": 44100, "adpcm": bytes([0, 7]) + bytes(14)}],
                 "waves": [self.riff(10), self.riff(3)], "envelopes": [envelope]}
        blob = sound.build_bank(model)
        self.assertEqual(len(blob), 4096)
        self.assertEqual(blob[-4:], b"EP\x03\x00")
        bank = sound.Bank(blob, 0)
        self.assertEqual(sound.decode_bank(bank), model)
        self.assertEqual(sound.check_bank(bank, 3), [])

    def test_music_bank(self):
        sound = tool("sound")
        cue = {"volume": 0x7F, "pan": 0x40, "flags": 0, "unknown_4": 0, "layers": 0, "unknown_10": 0,
               "unknown_11": 0, "duration_ms": 0, "wave": 0}
        model = {"serial": 0, "size": 2048, "label": "MUSIC", "music": True, "cues": [cue], "layers": [],
                 "samples": [], "waves": [self.riff(4)], "envelopes": []}
        blob = sound.build_bank(model)
        self.assertEqual(struct.unpack_from("<4I", blob, 0x0C), (0, 0, 0x50, 0))
        self.assertEqual(sound.decode_bank(sound.Bank(blob, 0)), model)
        self.assertEqual(sound.build([model, {**model, "serial": 1}])[2048:2050], b"SP")


class TutorialWriterTest(unittest.TestCase):
    def test_ydq(self):
        tutorial = tool("tutorial")
        text = ("[DUEL QUESTION]\r\n[Player0]\r\nPlayerLP0=8000\r\nCardInDeck0_000=4007\t//青眼\r\n"
                "Phase=Draw\r\nLimitTurn=-1\r\nCardInHand0_001=0012\r\n\r\n[END]\r\n").encode("cp932")
        lines = tutorial.ydq_decode(text)
        self.assertEqual(lines[2], {"key": "PlayerLP0", "value": 8000})
        self.assertEqual(lines[3]["comment"], "青眼")
        self.assertEqual(lines[6]["value"], "0012")  # leading zero kept as text
        self.assertEqual(tutorial.ydq_encode(lines), text)
        with self.assertRaises(ValueError):
            tutorial.ydq_decode(b"[END]")

    def test_text_table(self):
        tutorial = tool("tutorial")
        for language, lines in (("e", ["", "ab", "abc", "@2x@0"]), ("j", ["", "a", "ab", "abc", "abcd"])):
            blob = tutorial.text_build(lines, language)
            entries, decoded = tutorial.text_table(blob, language)
            self.assertEqual(decoded, lines)
            self.assertEqual(tutorial.check_text("t", blob, language), [])
        sizes = [size for _, size in tutorial.text_table(tutorial.text_build(["", "a"], "e"), "e")[0]]
        self.assertEqual(sizes, [4, 8])  # "a": 2 bytes of text + 6 zero bytes

    def test_cmd(self):
        tutorial = tool("tutorial")
        records = [{"kind": "tutorial", "code": 1, "side": 0, "a": 3, "b": 0, "c": 0},
                   {"kind": "engine", "code": 0x56, "side": 1, "a": 1, "b": 2, "c": 3},
                   {"kind": "end", "code": 0, "side": 0, "a": 0, "b": 0, "c": 0}]
        blob = tutorial.cmd_build(records)
        self.assertEqual(struct.unpack_from("<H", blob, 8)[0], 0x8056)
        self.assertEqual(tutorial.cmd_decode(blob), records)


class VoiceWriterTest(unittest.TestCase):
    def test_change_table(self):
        voices = tool("voices")
        tables = [[k, k + 1] if k % 3 else [] for k in range(16)]
        blob = voices.build_change_table(tables)
        self.assertEqual(struct.unpack_from("<I", blob, 0)[0], 64)
        self.assertEqual(voices.parse_change_table(blob), tables)

    def test_boot_sound_tables(self):
        voices = tool("voices")
        offsets, first = voices.derive_boot_tables([2048, 4096, 2048] + [2048] * 47, [1] * 48 + [5, 7])
        self.assertEqual(offsets[:3], [0, 2048, 6144])
        self.assertEqual(first[47:], [47, 50, 55])
        elf = bytes(fake_elf(voices.SOUND_ID_TABLE - voices.BOOT_BASE + 2 * len(offsets)))
        boot = voices.write_boot_tables(elf, (offsets, first))
        read = voices.boot_tables(voices.prx_imports.Elf(boot, voices.BOOT_BASE), len(offsets))
        self.assertEqual((list(read[0]), list(read[1])), (offsets, first))


class DuelTableWriterTest(unittest.TestCase):
    def test_ai_tables(self):
        ai = tool("ai_tables")
        elf = fake_elf(ai.TABLES_END - ai.BASE)
        start = ai.LISTS_START - ai.BASE
        put(elf, start, pattern(ai.TABLES_END - ai.LISTS_START, 1))
        for key, address, count, _, _ in ai.LISTS:  # padding after an odd-length list is zero
            end = address - ai.BASE + 2 * count
            put(elf, end, bytes(-end % 4))
        data = bytes(elf)
        module = ai.Module(data)
        model = ai.read_model(module)
        self.assertEqual(roundtrip.rewrite_problems("ai", data, ai.model_spans(module), ai.write_model, model), [])
        with self.assertRaises(ValueError):
            ai.write_model(data, {**model, "lists": {**model["lists"], "R3": []}})

    def test_fusion_and_rituals(self):
        fusion = tool("fusion")
        elf = bytes(fake_elf(fusion.RITUALS - fusion.BASE + 0x100))
        records = [fusion.Recipe(i, 0, 5000 + i, (0x16, 4000 + i) if i < 119 else (1, 2, 4000 + i))
                   for i in range(fusion.RECIPE_COUNT)]
        rituals = [fusion.Ritual(i, 0, 4100 + i, 4200 + i, 1 + i % 12) for i in range(31)]
        data = fusion.write_rituals(fusion.write_recipes(elf, records), rituals)
        module = fusion.Module(data)
        self.assertEqual([(r.fusion, r.materials) for r in fusion.recipes(module)],
                         [(r.fusion, r.materials) for r in records])
        self.assertEqual([(r.monster, r.spell, r.level) for r in fusion.rituals(module)],
                         [(r.monster, r.spell, r.level) for r in rituals])
        self.assertEqual(fusion.ritual_span(module, 31)[1], 128)

    def test_effect_tables(self):
        ep = tool("effect_params")
        elf = fake_elf(max(a + 8 * n for _, a, n in ep.LISTS) - ep.BASE + 0x100)
        for _, address, count in ep.TABLES:
            put(elf, address - ep.BASE, pattern(24 * count, address))
        for _, address, count in ep.LISTS:
            put(elf, address - ep.BASE, pattern(8 * count, address))
        put(elf, ep.COUNTER_TYPES - ep.BASE, pattern(80, 7))
        data = bytes(elf)
        module = ep.Module(data)
        model = ep.read_effect_model(module)
        self.assertEqual(sorted(model["lists"]), ["L1", "L4"])
        for part in ("tables", "lists", "counter_types"):
            self.assertEqual(roundtrip.rewrite_problems(part, data, ep.effect_spans(module, part),
                                                        ep.write_effect_model, {part: model[part]}), [])

    def test_boot_word_tables(self):
        sf = tool("search_filters")
        elf = fake_elf(sf.GENRE_MAP_TABLE - 0x08804000 + 4 * sf.GENRE_MAP_COUNT)
        put(elf, sf.ARCHETYPE_TABLE - 0x08804000, pattern(4 * sf.ARCHETYPE_COUNT, 3))
        put(elf, sf.GENRE_MAP_TABLE - 0x08804000, pattern(4 * sf.GENRE_MAP_COUNT, 4))
        data = bytes(elf)
        model = sf.read_boot_word_tables(data)
        for key in model:
            self.assertEqual(roundtrip.rewrite_problems(key, data, sf.boot_word_spans(data, key),
                                                        sf.write_boot_word_tables, {key: model[key]}), [])


class WorldWriterTest(unittest.TestCase):
    def test_hmp(self):
        world = tool("world")
        grid = types.SimpleNamespace(columns=2, rows=1, cells=bytes([1, 0]),
                                     vertices=[(0.5 * x, 0.25 * y, 0.5 * z) for z in range(2) for y in (1,)
                                               for x in range(3)])
        blob = world.build_hmp(grid)
        parsed = world.WalkGrid(blob)
        self.assertEqual((parsed.columns, parsed.rows, parsed.cells, parsed.vertices),
                         (2, 1, bytes([1, 0]), grid.vertices))
        self.assertEqual(world.build_hmp(parsed), blob)

    def test_rel_field_tables(self):
        world = tool("world")
        elf = fake_elf(0x30000)
        names = 0x2F000
        rows = []
        for index in range(world.MAP_COUNT):
            archive = (names + 32 * index, f"bg_{index:02d}_01.ehp")
            mesh = (names + 0x400 + 32 * index, f"bg_{index:02d}_01.tms")
            rows.append({"archive": archive, "meshes": [mesh, (0, None)]})
        field = world.write_map_table(bytes(elf), rows)
        self.assertEqual(world.read_map_table_model(field), rows)
        self.assertEqual(world.read_map_table(field)[3]["meshes"], ["bg_03_01.tms"])
        self.assertEqual(roundtrip.rewrite_problems("maps", field, world.map_table_spans(rows), world.write_map_table,
                                                    rows), [])
        put(elf, world.MAP_LIGHTING, pattern(8 * 5 * world.MAP_COUNT, 5))
        put(elf, world.SKY_GRADIENTS, pattern(72, 6))
        put(elf, world.ISLAND_POSITIONS, pattern(96, 7))
        field = bytes(elf)
        self.assertEqual(roundtrip.rewrite_problems("light", field, world.lighting_spans(), world.write_lighting,
                                                    world.read_lighting_model(field)), [])
        self.assertEqual(roundtrip.rewrite_problems("island", field, world.island_spans(),
                                                    world.write_island_positions,
                                                    world.read_island_positions(field)), [])

    def test_rel_story_tables(self):
        world = tool("world")
        elf = fake_elf(0x30000)
        selector = [{"location": loc, "group": 100 + loc, "stage_test": 1, "stage": 2, "story_flag": 0,
                     "story_flag_mode": 0, "record_char": 0, "record_bit": 0, "record_mode": 0} for loc in (1, 2)]
        model = {"selector": selector, "cells": [(101, 7, 7), (0, 12, 5), (0, 12, 6), (102, 0, 0), (0, 3, 4)]}
        story = world.write_exits(bytes(elf), model)
        self.assertEqual(world.read_exit_model(story), model)
        self.assertEqual(world.read_exit_groups(story), {101: [(12, 5), (12, 6)], 102: [(3, 4)]})
        self.assertEqual(roundtrip.rewrite_problems("exits", story, world.exit_spans(model), world.write_exits,
                                                    model), [])
        spots = {"fixed": {c: (c, 1, 2, 3) for c in world.FIXED_SPOT_CHARS},
                 "char139": [(k, -k, k, 0) for k in range(world.CHAR139_SPOT_COUNT)], "sellers": [(9, 9, 9, 9)] * 3}
        story = world.write_fixed_spots(story, spots)
        self.assertEqual(world.read_fixed_spots(story), spots)
        rows = [world.CharacterRow([c + 1, 5, 0, 0, 0, c % 2, 0] + [1 + (c + k) % 6 for k in range(50)])
                for c in range(world.CHAR_ROWS)]
        story = world.write_character_table(story, rows)
        self.assertEqual([world.character_row_words(r) for r in world.read_character_table(story)],
                         [world.character_row_words(r) for r in rows])


class ArchiveWriterTest(unittest.TestCase):
    def test_ptrs(self):
        ehp = tool("ehp")
        archive = ehp.build([("a.tms", bytes(40)), ("b.gim", bytes(24)), ("x-ptrs.txt", bytes(4))])
        layout = ehp.member_offsets(archive)
        offsets = {name: offset for name, offset, _ in layout}
        words = [offsets["a.tms"], 0, offsets["b.gim"] + 8, 0x10, offsets["b.gim"]]
        blob = struct.pack(f"<{len(words) + 1}I", *words, ehp.PTRS_END)
        entries = ehp.parse_ptrs(blob, layout)
        self.assertEqual(entries, ["a.tms", None, ["b.gim", 8], 0x10, "b.gim"])
        self.assertEqual(ehp.build_ptrs(entries, layout), blob)
        with self.assertRaises(ValueError):
            ehp.parse_ptrs(struct.pack("<2I", 4, 5), layout)

    def test_tmf(self):
        ehf = tool("ehf")
        blob = bytes([0x00, 0x01, 0x10, 0x11, 0x80])
        flags = ehf.decode_tmf(blob)
        self.assertEqual(flags[3], {"additive": True, "bit4": True, "other": 0})
        self.assertEqual(ehf.build_tmf(flags), blob)


class SaveWriterTest(unittest.TestCase):
    def test_random_buffer_round_trips(self):
        save = tool("save")
        data = pattern(save.SAVE_SIZE, 11)
        self.assertEqual(save.region_problems(data), [])
        with tempfile.TemporaryDirectory() as tmp:
            source, model, rebuilt = (Path(tmp) / n for n in ("DATA0", "model.json", "rebuilt"))
            source.write_bytes(data)
            self.assertEqual(save.main(["model", str(source), "-o", str(model)]), 0)
            self.assertEqual(save.main(["build", str(model), "-o", str(rebuilt)]), 0)
            self.assertEqual(rebuilt.read_bytes(), data)
            self.assertEqual(save.main(["roundtrip", str(source)]), 0)

    def test_structured_regions(self):
        save = tool("save")
        data = bytearray(save.SAVE_SIZE)
        struct.pack_into("<I", data, 0, save.VERSION)
        base = save.STORED_BASE + 3 * save.STORED_SIZE
        struct.pack_into("<I", data, base, 1)
        data[base + 4:base + 12] = "Deck".encode("utf-16-le")
        data[base + 0x40] = 0x55  # stale byte after the name
        struct.pack_into("<3I", data, base + 0x54, 2, 0, 1)
        struct.pack_into("<3H", data, base + 0x60, 4007, 4008, 4009)  # third main id is past the count
        struct.pack_into("<IH", data, base + 0x114, 1, 4007)
        struct.pack_into("<H", data, save.RECIPE_BASE + 2 * 5, 1 | 7 << 1)
        data[0x1B0FC] = 0b1000  # picture 3
        data[0x1B0FC + 10] = 0b01000000  # picture 86
        struct.pack_into("<H2HxxxxxxxxxxxxxxxxH", data, save.CHAR_BASE + 2 * save.CHAR_SIZE, 2, 10, 11, 500)
        struct.pack_into("<7I", data, save.DUEL_BASE, 3, 1, 0, 2, 2, 0, 1)
        struct.pack_into("<4H", data, save.DUEL_BASE + 0x1C + 8 * 5, 3, 1, 0, 0)
        model = json.loads(json.dumps(save.to_model(bytes(data))))
        regions = model["regions"]
        stored = regions["stored_decks"]
        self.assertEqual([d["index"] for d in stored], [3])
        self.assertEqual(stored[0]["name"]["text"], "Deck")
        self.assertEqual(stored[0]["deck"]["main"], {"values": [4007, 4008], "stale": {"2": 4009}})
        self.assertEqual(regions["recipes"], [{"recipe": 5, "unlocked": 1, "owner": 7}])
        self.assertEqual(regions["picture_bits"], [3, 86])
        self.assertEqual(regions["characters"], [{"index": 2, "entries": {"values": [10, 11]}, "points": 500}])
        self.assertEqual(regions["duel_record"]["per_character"],
                         [{"character": 5, "wins": 3, "losses": 1, "draws": 0}])
        self.assertEqual(save.from_model(model), bytes(data))

    def test_bad_model(self):
        save = tool("save")
        with self.assertRaises(ValueError):
            save.from_model({"format": "other"})


class ModuleTableWriterTest(unittest.TestCase):
    def test_descriptors_and_scenes(self):
        modules = tool("modules")
        elf = fake_elf(modules.SCENE_TABLE - modules.BOOT_BASE + 8 * modules.SCENE_COUNT)
        names = 0x9A000
        model = {}
        for t, address in enumerate(modules.DESCRIPTOR_TABLES):
            model[address] = [{"id": 1 + k + 8 * t, "root": -2 + k, "name_ptr": names + 0x100 * t + 0x20 * k,
                               "name": f"m{t}{k}.prx", "kind": 4, "utility": 0x300 + k} for k in range(3)]
        boot = modules.write_descriptors(bytes(elf), model)
        elf_view = modules.prx_imports.Elf(boot, modules.BOOT_BASE)
        self.assertEqual({a: modules.read_descriptors(elf_view, a) for a in modules.DESCRIPTOR_TABLES}, model)
        pairs = [(k, 8 + k) for k in range(modules.SCENE_COUNT)]
        boot = modules.write_scene_table(boot, pairs)
        self.assertEqual(modules.read_scene_table(modules.prx_imports.Elf(boot, modules.BOOT_BASE)), pairs)


if __name__ == "__main__":
    unittest.main()
