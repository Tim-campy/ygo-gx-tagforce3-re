# Booster packs (`gmodule/rel_shop.prx`)

Status: `documented`. The 48 booster packs sold in the shop are a static table inside the shop module `rel_shop.prx`, not a data file. Tool: `tools/tables.py packs` (CSV export, `--check`). `rel_story.prx` contains the same lists at other addresses (157 card-id runs in both modules); it is not decoded yet.

Addresses below are virtual addresses inside the module. The PRX has one loadable segment with `vaddr = file offset − 0x54`; pointers in the table are unrelocated module addresses (the module's relocation table fixes them up at load time).

## Pack table: `0x202c8`, 48 records of 12 bytes

| Offset | Size | Field | Notes |
| --- | --- | --- | --- |
| `0x0` | 4 | `a` | 20 for 47 packs, 40 for one. Meaning unknown. |
| `0x4` | 2 | `price` (hypothesis) | 50, 100, 125, 150, 200, 250, 300, and once 573; consistent with shop prices in DP except the last. Confidence low. |
| `0x6` | 2 | `flags` | 0 (28 packs), 1 (6), 2 (2), 3 (11), 4 (1). Possibly an unlock condition. Unknown. |
| `0x8` | 4 | descriptor | Address of the pack's tier descriptor. |

## Tier descriptor: 4 × (`u32 address`, `u32 count`)

Each pack has four tiers; each tier is a list of `count` `u16` card ids at `address`. The four lists of a pack are stored back to back, in tier order, followed by a zero `u16` and then the descriptor. Tier counts typically decrease (for example `[40, 12, 9, 7]`, `[61, 16, 10, 8]`).

The tiers are rarities, from common (1) to ultra rare (4): in the packs checked, tier 1 holds weak cards and tier 4 well-known strong ones (`Sangan`, `Spirit Reaper`, `Megamorph`, `Premature Burial`, `United We Stand`). Confidence medium-high; the per-tier pull rates are not in this table.

## Observations

- 9,177 entries; every id exists in the card database (`tools/tables.py packs … --check --cardinfo …`). No card appears in two tiers of the same pack. Lists are mostly but not always in ascending id order.
- 3,477 distinct cards appear in packs. The last pack (index 47) contains exactly those 3,477 (`[2283, 509, 381, 304]`), so it is an "all obtainable cards" pack; pack 34 is another large pool (`[1405, 371, 245, 246]`).
- Some packs have empty tiers, for example `[362, 0, 0, 1]`, `[0, 0, 0, 43]`, `[98, 0, 0, 3]`.

## Open questions

- Pack names and artwork: which string table and texture belong to each pack index (`shop/all_<lang>.ehp` has `strTbl` with 35 entries and `pack_explain_str` with 392).
- Meaning of `a`, `flags`, and whether `price` is the DP price; the shop code in `rel_shop.prx` that reads the table.
- Cards per pack and per-tier pull probabilities (not in this table).
- How the 76 cards that are in the database but in no pack are obtained (rewards, starter deck, story).
