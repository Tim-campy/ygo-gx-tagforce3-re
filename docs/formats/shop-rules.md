# Pack availability rules (`rel_shop.prx`)

How the card shop decides which of the 48 packs (`packs.md`) are on sale. The rules are code, not a data table: `shop_update_pack_unlocks` (`rel_shop` `0x090d9e5c`, 5,924 bytes, module `+0xb15c`) runs at every shop visit, before `shop_load_pack_states` copies the save states into the shop table, and writes each pack's state with `save_set_pack_state(p, s)` (save pack record byte 1 bits 0–2, `save.md`). This document lists the rules in the order the function applies them, read instruction by instruction from the disassembly (capstone, 2026-10-31; constants and branch targets checked in the raw listing). It replaces the summary in `world.md` ("Card shop: pack availability"), which read the level and opponent conditions as extra requirements; they are independent ways to open a pack.

## States

| Value | Meaning | Basis |
| --- | --- | --- |
| 0 | Not available (never shown) | code |
| 1 | Was available, its condition no longer holds (shown greyed) | the rules write 1 only when `save_get_pack_state(p) ≠ 0` and the condition fails |
| 2 | On sale | code |
| bit 2 (4) | Unlocked by a story script (`set_pack_state 60000`, `story.md`); turned into 2 by rule 13 below | code |

Every rule only **raises** a pack to 2, except the "else 1" branches and rule 14. A pack is therefore on sale when any rule that names it holds.

## Rules (in execution order)

"Partner" is `(character, variant)` from the save partner word (`save_copy_partner_field`, bits 4–11 and 12–15). "Level" is `save_get_duelist_level()` (1–99). "Owned ‰" of a pack is `shop_get_pack_owned_permille(p)` (owned cards of the pack's four tiers × 1000 / cards listed). "Opponents ‰" is `shop_get_opponents_beaten_permille()` (shop opponent list below). Records `k` are `save_get_minigame_record_k()` (record table `+0xa0 + 4k`, `save.md`).

| # | Packs | Condition → state | Else | Conf. |
| --- | --- | --- | --- | --- |
| 1 | — | `all_done` = every variant of characters 2–8 (except character 2 variant 2) has character-row flag bit 2 (partner story finished; `save_test_character_flag_bit2`, `world_count_character_variants`) | — | H |
| 2 | 0, 1, 2 | always → 2 | — | H |
| 3 | 3–8 | owned ‰ of pack `p − 3` ≥ 500 → 2 | — | H |
| 4 | 9–14 | shop byte `0x090faa70` (module `+0x2bd70`) bits 4–7 = `p − 8` (1–6) → 2 | state ≠ 0 → 1 | H (code); source of the byte unknown |
| 5 | 15 | save progress flag `+0x1c0e9` bit 4 and partner points 0–1999 → 2 | — | H |
| 6 | 16 | same flag and partner points 2000–4000 → 2 | — | H |
| 7 | 17–23 | partner character = `p − 15` (2–8, any variant) → 2 | state ≠ 0 → 1 | H |
| 8 | 24–33 | partner in the pack's list (table below) → 2 | state ≠ 0 → 1 | H |
| 9 | 34 | `save_get_card_collection_permille()` ≥ 600 → 2 | — | H |
| 9 | 35, 36, 37, 38, 40 | record 0 ≥ 50,000; record 1 ≥ 100,000; record 2 ≥ 400; record 7 ≥ 50,000; record 8 ≥ 4,500 → 2 | — | H |
| 9 | 39, 43, 44, 45 | progress flag `+0x1c0e9` bit 5; bit 1 (golden-egg sandwich bought); bit 7; `+0x1c0ea` bit 0 → 2 | — | H |
| 10 | 41 | row flag bit 2 of (26, 0) → 1, then → 2 if shop byte `0x090fad50` (module `+0x2c050`) bit 0 = 1 | — | H (code), L (meaning of the byte) |
| 10 | 42 | row flag bit 2 of (27, 1) → 1, then → 2 if that bit = 0 | — | same |
| 10 | 46 | shop byte `0x090facf6` (module `+0x2bff6`) bit 0 → 2 | — | H (code) |
| 10 | 47 | collection ‰ ≥ 900 → 2 | — | H |
| 11 | 9–33 | level ≥ `p + 12` (pack 9 at 21 … pack 33 at 45) → 2 | — | H |
| 11 | 47 | level ≥ 50 → 2 | — | H |
| 12 | 9–45, 47 | opponents ‰ ≥ threshold (table below) → 2 | — | H |
| 13 | 3–33, 35–41 | `all_done` → 2 | — | H |
| 14 | 3–47 | state bit 2 (story unlock) set → 2 | — | H |
| 15 | 41 / 42 | state ≠ 0 and the byte `0x090fad50` bit 0 ≠ 1 (41) / ≠ 0 (42) → 1 | — | H |

Rules 10 and 15 make packs 41 and 42 mutually exclusive: once the corresponding character's story is finished, the byte at `0x090fad50` decides which of the two is on sale and greys the other. (`world.md` gave this byte as `0x0973ad50`; the code addresses module `+0x2c050`.)

### Partner lists of packs 24–33 (rule 8)

| Pack | Partner character (variant) | Pack | Partner character (variant) |
| --- | --- | --- | --- |
| 24 | 36 (variant 1); 37–41 | 29 | 34, 35; 52–78 |
| 25 | 9, 10, 12, 13, 21 | 30 | 20 (variant 2); 28, 29; 79–90 |
| 26 | 11, 15, 17, 18, 42 | 31 | 33, 43; 91–105 |
| 27 | 24, 25, 31, 32, 44, 45; 20 (variants 0–1) | 32 | 22, 23, 30; 106–120 |
| 28 | 14, 16, 19; 36 (variant 0); 46–51 | 33 | 121–126 |

### Opponent thresholds (rule 12, per mille)

| Packs | Threshold | Packs | Threshold |
| --- | --- | --- | --- |
| 9, 10, 11, 12, 13, 14 | 100, 150, 200, 250, 300, 350 | 36, 38 | 750 |
| 15 | 400 | 37, 41 | 800 |
| 16–23 | 450 | | |
| 24–32 | 500 | 39, 43 | 950 |
| 33, 35, 40 | 600 | 42, 44, 45, 47 | 1000 |

Packs 34 and 46 have no opponent threshold.

## Shop opponent list (`rel_shop` `0x090ef208`, module `+0x20508`, 104 × 2 bytes)

Read only by `shop_get_opponents_beaten_permille` (`0x090d9dd4`): for `i` = 0–103 it counts the entries whose low byte has bit 0 set ("eligible") and, among those, the entries with a non-zero byte at save record table `+0x14c + i` (the duel-bonus state per entry, `save.md` "Record table"); it returns beaten × 1000 / eligible.

| Offset | Size | Type | Field | Conf. | Basis |
| --- | --- | --- | --- | --- | --- |
| `+2·i` bit 0 | — | flag | Entry `i` counts towards the percentage; set in all 104 entries of the retail module | H | code, file |
| `+2·i` bits 1–15 | — | `u16` | Not read by this function; the 104 values are distinct, 169–431, all odd | — | file statistics |

So the percentage is in effect "entries 0–103 of the 108 duel-bonus states that are non-zero". That the 104 entries are opponents (as the registry name says) is a hypothesis (low): the save block they index is the duel-bonus table of the record table, which `rel_duel_eng` fills after duels. Another `u16` table follows directly at `+0x205d8`.

## Open questions

- The source of the shop byte `0x090faa70` (packs 9–14) and of the bytes `0x090fad50` (packs 41/42) and `0x090facf6` (pack 46).
- The meaning of the save progress flags `+0x1c0e9` bits 4, 5, 7 and `+0x1c0ea` bit 0, and of minigame records 0, 1, 2, 7, 8 (`save.md`).
- What the upper 15 bits of the shop opponent list encode, and whether the 104 entries are opponents or duel bonuses.
