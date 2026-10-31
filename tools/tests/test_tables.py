#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/tables.py on synthetic ELF images. Run with: python3 -I tools/tests/test_tables.py"""

import contextlib
import importlib.util
import io
import struct
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_tables", Path(__file__).resolve().parents[1] / "tables.py")
tables = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tables)

SEGMENT_OFFSET = 0x54  # as in the game's PRX modules: vaddr 0 sits at file offset 0x54


def fake_prx(packs):
    """One PT_LOAD segment; pack i gets descriptor and id lists after the pack table."""
    image = bytearray(tables.PACK_TABLE + 12 * tables.PACK_COUNT + 0x4000)
    struct.pack_into("<3i", image, tables.BUY_FACTOR_TABLE, 1, 0, 20)
    struct.pack_into("<4h", image, tables.RARITY_BOX_TABLE, 0, 14, 4, 2)
    cursor = tables.RARITY_BOX_TABLE + 8
    for index in range(tables.PACK_COUNT):
        tiers = packs.get(index, ([], [], [], [0xE88]))
        pairs = []
        for ids in tiers:
            pairs += [cursor, len(ids)]
            struct.pack_into(f"<{len(ids)}H", image, cursor, *ids)
            cursor += 2 * len(ids) + 2
        cursor = (cursor + 3) & ~3
        descriptor = cursor
        struct.pack_into("<8I", image, descriptor, *pairs)
        cursor += 32
        struct.pack_into("<III", image, tables.PACK_TABLE + 12 * index, 20, (index % 4) << 16 | 100, descriptor)
    header = bytearray(SEGMENT_OFFSET)
    header[0:4] = b"\x7fELF"
    struct.pack_into("<I", header, 0x1C, 0x34)  # e_phoff
    struct.pack_into("<H", header, 0x2C, 1)  # e_phnum
    struct.pack_into("<6I", header, 0x34, 1, SEGMENT_OFFSET, 0, 0, len(image), len(image))
    return bytes(header) + bytes(image)


def fake_boot(limits):
    """One allocated section that holds the limit list at its real address."""
    data_vaddr = tables.LIMIT_TABLE - tables.BOOT_BASE - 0x10
    payload = bytearray(0x10 + 4 * tables.LIMIT_COUNT)
    for k, pair in enumerate(limits):
        struct.pack_into("<HH", payload, 0x10 + 4 * k, *pair)
    shoff = 0x40
    header = bytearray(shoff + 40 * 2)
    header[0:4] = b"\x7fELF"
    struct.pack_into("<I", header, 0x20, shoff)
    struct.pack_into("<HH", header, 0x2E, 40, 2)
    struct.pack_into("<6I", header, shoff + 40, 0, 1, 2, data_vaddr, len(header), len(payload))
    return bytes(header) + bytes(payload)


class TablesTest(unittest.TestCase):
    def test_packs(self):
        packs = tables.read_packs(fake_prx({0: ([0xE89, 0xE88], [0xF00], [], [0x1000, 0x1001])}))
        self.assertEqual(len(packs), 48)
        self.assertEqual(packs[0]["tiers"], [(0xE89, 0xE88), (0xF00,), (), (0x1000, 0x1001)])
        self.assertEqual((packs[1]["a"], packs[1]["price"], packs[1]["flags"]), (20, 100, 1))
        self.assertEqual(tables.check_packs(packs, tables.known_ids(None)), [])
        self.assertTrue(tables.check_packs(packs, {0xE88}))

    def test_random_is_newlib_rand(self):
        rng = tables.GameRandom(1)
        self.assertEqual(rng.rand(), 0x5851F42D)  # newlib rand() after srand(1)
        self.assertEqual(tables.GameRandom(1).shifted(), 0x5851F42D >> 4)

    def test_draw_box_and_order(self):
        pack = {"pack": 0, "a": 20, "tiers": [tuple(range(0xE88, 0xE90)), (0xF00, 0xF01), (0xF10,), (0xF20,)]}
        box, rng = [0] * 20, tables.GameRandom(7)
        rarities = []
        for _ in range(20):
            cards = tables.draw_pack(pack, box, rng)
            self.assertEqual(len(set(cards)), 5)
            self.assertTrue(all(c in pack["tiers"][0] for c in cards[:4]))  # rare-slot card is last
            rarities.append(next(t for t, ids in enumerate(pack["tiers"]) if cards[-1] in ids))
        self.assertEqual(sorted(rarities), [1] * 14 + [2] * 4 + [3] * 2)
        self.assertEqual(sorted(box), [1] * 14 + [2] * 4 + [3] * 2)
        tables.draw_pack(pack, box, rng)  # the 21st pack starts a new box
        self.assertEqual(box[1:], [0] * 19)

    def test_draw_fallback_and_odds(self):
        pack = {"pack": 1, "a": 20, "tiers": [(), (), (), tuple(range(0xE88, 0xE88 + 10))]}
        rare, common, per_card = tables.pack_odds(pack)
        self.assertEqual((common, round(rare[None], 3), round(rare[3], 3)), (3, 0.9, 0.1))
        self.assertAlmostEqual(per_card[3], 0.5)
        cards = tables.draw_pack(pack, [0] * 20, tables.GameRandom(3))
        self.assertEqual(len(set(cards)), 5)

    def test_draw_prefers_unowned(self):
        tiers = [tuple(range(0xE88, 0xE88 + 40)), (0xF00,), (0xF10,), (0xF20,)]
        pack = {"pack": 47, "a": 20, "tiers": tiers}
        unowned = set(tiers[0][:4])
        owned = lambda c: 0 if c in unowned else 1
        rng, box, hits, n = tables.GameRandom(5), [0] * 20, 0, 2000
        for _ in range(n):
            hits += sum(c in unowned for c in tables.draw_pack(pack, box, rng, owned=owned)[:4])
        # 30% of the common picks come from the 4 unowned cards, the rest from all 40
        self.assertAlmostEqual(hits / (4 * n), 0.3 + 0.7 * 4 / 40, delta=0.03)

    def test_check_draws(self):
        image = fake_prx({i: (list(range(0xE88 + 8 * i, 0xE8F + 8 * i)), [0x1800 + i], [], []) for i in range(48)})
        packs = tables.read_packs(image)
        box, factors = tables.read_draw_constants(image)
        self.assertEqual((box, factors), ((0, 14, 4, 2), (1, 0, 20)))
        self.assertEqual(tables.check_draws(packs, box, factors, boxes=2), [])
        self.assertTrue(tables.check_draws(packs, (0, 10, 8, 2), factors, boxes=1))
        self.assertTrue(tables.check_draws(tables.read_packs(fake_prx({})), box, factors, boxes=1))  # 1-card pools

    def test_limits(self):
        pairs = [(0xE88 + k, k % 3) for k in range(tables.LIMIT_COUNT)]
        limits = tables.read_limits(fake_boot(pairs))
        self.assertEqual(limits, pairs)
        self.assertEqual(tables.check_limits(limits, tables.known_ids(None)), [])
        self.assertTrue(tables.check_limits([(0xE88, 3)], tables.known_ids(None)))

    def test_cli_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rel_shop.prx"
            path.write_bytes(fake_prx({}))
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(tables.main(["packs", str(path)]), 0)
        lines = out.getvalue().splitlines()
        self.assertEqual(lines[0], "pack,a,price,flags,tier,card_id")
        self.assertEqual(len(lines), 1 + 48)


if __name__ == "__main__":
    unittest.main()
