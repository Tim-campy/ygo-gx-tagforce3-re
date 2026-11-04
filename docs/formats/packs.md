# Booster packs (`gmodule/rel_shop.prx`)

Status: `reimplemented` (table: reader and writer, round trip below; the draw procedure `pack_draw` is `verified`). The 48 booster packs sold in the shop are a static table inside the shop module `rel_shop.prx`, not a data file. Tools: `tools/tables.py packs` (CSV export, `--check`) and `tools/tables.py odds` (draw odds; `--check` replays the draw). `rel_story.prx` contains the same lists at other addresses (157 card-id runs in both modules); it is not decoded yet.

Addresses below are virtual addresses inside the module. The PRX has one loadable segment with `vaddr = file offset − 0x54`; pointers in the table are unrelocated module addresses (the module's relocation table fixes them up at load time).

## Pack table: `0x202c8`, 48 records of 12 bytes

| Offset | Size | Field | Notes |
| --- | --- | --- | --- |
| `0x0` | 1 | cards per pack × 4 | 20 for 47 packs, 40 for pack 23: `byte0 >> 2` = **cards per pack** (5, or 10) (`shop_get_cards_per_pack`, high). At run time bits 0–1 hold the pack's sale state (`shop_load_pack_states`). |
| `0x1` | 1 | — | 0 in the file; at run time the percentage of the pack's cards ever obtained (`shop_get_pack_seen_percent`, `0x090d9550`: cards with a collection state ≠ 0 × 100 / all). |
| `0x2` | 2 | — | 0. |
| `0x4` | 2 | **unit price** in DP | 50, 100, 125, 150, 200, 250, 300, and once 573 (pack 46). Charged per pack (`shop_get_pack_price`, high). |
| `0x6` | 2 | clerk voice | 0 (28 packs), 1 (6), 2 (2), 3 (11), 4 (1): the clerk voice played for the pack in the Japanese setting (`shop_play_clerk_voice`, medium). |
| `0x8` | 4 | descriptor | Address of the pack's tier descriptor. |

## Tier descriptor: 4 × (`u32 address`, `u32 count`)

Each pack has four tiers; each tier is a list of `count` `u16` card ids at `address`. The four lists of a pack are stored back to back, in tier order, followed by a zero `u16` and then the descriptor. Tier counts typically decrease (for example `[40, 12, 9, 7]`, `[61, 16, 10, 8]`).

The tiers are rarities, from common (1) to ultra rare (4): in the packs checked, tier 1 holds weak cards and tier 4 well-known strong ones (`Sangan`, `Spirit Reaper`, `Megamorph`, `Premature Burial`, `United We Stand`). The draw code confirms the order: tier 1 fills the common slots, tiers 2–4 the rare slot with 70 / 20 / 10 % (below). High.

## Observations

- 9,177 entries; every id exists in the card database (`tools/tables.py packs … --check --cardinfo …`). No card appears in two tiers of the same pack. Lists are mostly but not always in ascending id order.
- 3,477 distinct cards appear in packs. The last pack (index 47) contains exactly those 3,477 (`[2283, 509, 381, 304]`), so it is an "all obtainable cards" pack; pack 34 is another large pool (`[1405, 371, 245, 246]`).
- Some packs have empty tiers, for example `[362, 0, 0, 1]`, `[0, 0, 0, 43]`, `[98, 0, 0, 3]`; the draw falls back to a lower tier (below).

## Buying and opening packs (`rel_shop` code)

**Verified in PPSSPP (2026-10-31)**: E16 of [`results/2026-10-31-sessionE-P.md`](../verification/results/2026-10-31-sessionE-P.md) bought one pack (pack 17) and diffed the save: price (DP − 100), bought flag `0x1542a + 17`, purchase counter `0x16602`, one draw, one rarity-box entry (`n = 0`, `r = 1`), stock nibble − 1, and the five cards entering the collection only at the commit on the results screen, exactly as described below. The row `pack_draw` is `verified` ([`results/2026-10-31-format-raises.md`](../verification/results/2026-10-31-format-raises.md)). Which packs are on sale is decided by the rules in [`shop-rules.md`](shop-rules.md).

Static reading of the Ghidra decompilation of `rel_shop.prx` (runtime base `0x090ced00`; function names from `re/names-rel_shop.csv`) and the `BOOT.BIN` save accessors. Confidence: high for the draw procedure (one function, read in full, and replayed by `tools/tables.py odds --check`), medium for the purchase flow (a state machine with UI code around it). Not traced in PPSSPP yet.

### Shelf, purchase modes and prices

- Each pack has a **shelf of 20** in two columns of 10: the two nibbles of save pack record byte 0 (`save_get_pack_stock`, `0x0885745c`; `save_reset_packs` writes `0xaa`, 10 + 10). The shop copies them to `0x090f9bc0 + p` on entry (`shop_load_pack_states`, `0x090d9264`) and writes them back on exit (`shop_save_pack_stock`, `0x090d92fc`). An empty shelf is refilled to `0xaa` the next time the pack is selected (`0x090cf578`).
- Purchase mode (`0x090facf8`, chosen in `shop_select_purchase_step`, `0x090cfa00`): **0** one pack (no shoulder button held); **1** the whole remaining shelf (shoulder button held); **2** a box of 20, when the shelf is full. Quantity = `shop_get_buy_quantity(mode)` (`0x090d9438`): table `s32[3]` at `0x090ef2f0` holding `1, —, 20`, with entry 1 replaced at run time by the shelf count (the two nibbles added).
- Price = record `+4` (unit price, `shop_get_pack_price`, `0x090d9414`) × quantity (`shop_get_purchase_price`, `0x090d949c`). The purchase is refused when DP < price ("not enough DP" message `0x090d42e4(3)`) or when the packs bought in this visit plus the quantity would exceed 1,000 (`0x090f9b5c`, message 4).
- On a purchase (`shop_buy_single_step` `0x090d0178`, `shop_buy_shelf_step` `0x090d0a38`, `shop_buy_box_step` `0x090d154c`): DP −price through `shop_change_dp` (`0x090e0d68` → `save_add_dp(−price)`, with the DP counter animation); `save_set_pack_bought(p)` (`0x088548a0`, save byte `+0x1542a + p` = 1); `save_add_packs_bought(n)` (`0x0885761c`, `u16` at save `+0x16602`, capped at 2,000); the shelf loses the packs; the per-pack cart counter `u16 0x090f9afc[p]` grows by the quantity.
- Record `+6` is a **clerk voice index** (0–4): `shop_play_clerk_voice(2)` (`0x090dbab8`) plays sound `0x79f4 + v` (or `0x79e1 + v` with the other clerk, bit 0 of `0x0973ad50`) when the pack is on sale. The voices exist only in the Japanese language setting (the function returns unless `save_get_language() == 0`). Medium.

### Opening

Packs are opened one at a time, in pack-index order, as the pack-opening animation runs (`shop_open_pack_step`, `0x090d23fc`) or all at once when the player skips (`shop_open_all_packs`, `0x090d2da0`). Each opening is `shop_open_next_pack` (`0x090d2fd4`): `shop_draw_pack_cards(p, cards)` fills a 10-entry array, the number of cards is `shop_get_cards_per_pack(p)` (record byte 0 `>> 2`: 5, or 10 for pack 23), and `shop_record_opened_cards` (`0x090d3104`) appends them to the visit's result list (`0x090faa74`, 10-byte entries `{u16 card, u16 file-table index, u16 pack, u16 copies ≤ 100, u8 copies in the save list at +0x161f6, u8 copies owned}`; a card already in the list for the same pack only increments `copies`). The collection is updated only when the player leaves through the results screen (`0x090d45f8`, menu mode 5; medium): `shop_commit_results` (`0x090d90c0`) calls `save_change_card_count(card, 1)` once per copy (99 at most per card). So the "owned" counts that the draw reads (packs 15 and 47 below) do not include cards from earlier packs of the same visit.

### Draw procedure: `shop_draw_pack_cards(p, out)` (`0x090d9678`)

Random numbers: every draw uses `system_rand_shifted()` (`BOOT.BIN` `0x08859688`) = `system_rand() >> 4`, and `x % n` to pick among `n`. `system_rand` (`0x088101d4`) is newlib's 64-bit LCG in the C library's reentrancy block (`state = state × 0x5851F42D4C957F2D + 1`, returns bits 32–62); it is seeded once at start-up from the low word of `sceRtcGetCurrentTick` (`system_seed_rand_from_rtc`, `0x088596a8` → `system_srand`, `0x0881019c`) and advanced once per frame by `system_main` and by every wait in `system_wait_frame` (`0x0884c6b8`). The stream is shared by the whole game, so the outcome of a purchase cannot be predicted from a save; the port can use any uniform generator.

1. **Rarity box.** The pack's 20 save entries (`save_get_pack_entries(p)`, record `+2`) record the rarities already drawn in the current box of 20 packs. Start from the slot counts `s16[4]` at `0x090ef2fc` = `{0, 14, 4, 2}` and subtract one for each leading entry with a value 1–3 (stop at the first 0). If all 20 are used, clear the entries and restart with `{14, 4, 2}`. Build the list of remaining slots in the order `3…, 2…, 1…`, take `slot[rand % remaining]` as the **rarity** `r` (1–3) and store it in entry `20 − remaining`. So every 20 consecutive packs of one kind contain exactly 14 rare-slot cards of tier 2, 4 of tier 3 and 2 of tier 4; one pack in isolation has 70 / 20 / 10 %. The box survives between visits (it is in the save).
2. **Rare slot.** Take tier index `r` (tier 2–4 in the 1-based numbering of the CSV). If it is empty, fall back to `r − 1`, …, down to tier index 0 (common). Pick one card uniformly from the first non-empty tier; if all are empty there is no rare-slot card (packs 33 and 45 for some rarities).
3. **Common slots.** The common tier is tier index 0, or the first non-empty tier when 0 is empty (pack 33: tier 4; 45: tier 3; 46: tier 2). Draw uniformly from it until the pack holds `cards_per_pack` cards, redrawing when the card fails `card_db_is_valid` or is already in this pack (`shop_pack_has_card`, `0x090d9cac`). So a pack never holds the same card twice; duplicates across packs are normal.
4. **Order.** Swap the first card (the rare slot) with the last one: the rare-slot card is shown last.
5. **Packs 15 and 47** (index 15 and the "all cards" pack 47) build, per non-empty tier, a list of the cards the player owns 0 copies of (`save_get_card_count < 1`); when a tier has none, the cards owned fewer than 3 times. The rare slot takes its card from that list with probability 5/10 (`rand % 10 < 5`), the commons with 3/10 (`rand % 10 < 3`); otherwise, and whenever the list is empty, from the full tier. So these packs favour missing cards.

The order of the random numbers, needed only for a bit-exact replay: rarity; then for the rare slot `[rand % 10 when a filtered list exists] rand % n`; then the same pair for each common attempt, including rejected ones. `tools/tables.py` holds a reference implementation (`draw_pack`, `GameRandom`).

### Odds

For every pack except 15 and 47 (and for those too when the player owns all of a tier's cards equally often) the odds follow from the table alone; `tools/tables.py odds rel_shop.prx -o extracted/…/odds.csv` writes them per pack: cards per pack, unit and box price, tier sizes, the probability that the rare-slot card comes from each tier (or is missing), and the chance that one given card of each tier is in one pack. For a normal 5-card pack with tier sizes `n1…n4`: a given common card is in a pack with probability `4 / n1`, a given tier-2/3/4 card with `0.7 / n2`, `0.2 / n3`, `0.1 / n4`. `--check` validates the ids, reads the box constants and purchase factors from the module, and replays `draw_pack` over 60 boxes of every pack (box composition 14/4/2, pack size, no duplicates, cards from the pack's pool, observed tier counts within 6 σ of the computed odds).

### Story-side draws

`give_random_card` / `give_booster` (story opcodes 50098/50099, `docs/formats/story.md`) use the copies of these lists inside `rel_story.prx` with their own rarity range; they do not touch the shop's rarity box (`rel_story` never calls `save_get_pack_entries` or `save_set_pack_entry`).

## Cards in no pack (2026-11-04)

Joining the pack table (`tables.py packs`) with `cardinfo_eng` gives 3,553 cards, 3,477 of them in at least one pack and **76 in none**. None of the 76 is a story gift: the `give_card`/`if_card_marked`/`mark_card` operands of `EveB.bin` (`story.py events`) name 38 distinct cards, all of them pack cards. The 76 split as follows (static reading with capstone; analysis scripts kept outside the repository):

| Group | Cards | How the game treats them | Conf. |
| --- | --- | --- | --- |
| Tokens | 52: `3751` and `3900`–`3950` (kind 21) | Never collectable; `card_db_is_token` excludes them from every random card draw. | H |
| Underground-duel prize list | 5: `5189`, `5181`, `4343`, `4842`, `4844` (Philosopher's Stone - Sabatier, Illusion Gate, Raigeki, Monster Reborn, Pot of Greed) | `rel_underground` reward picker `+0x6a28` (module offset), mode `0x0e`: copies the 5 `u32` ids at module `+0x17a94` and gives the one with the fewest free copies (`deck_count_free_card_copies`, BOOT export). | H (code), M (that mode `0x0e` is the prize case) |
| Excluded from random rewards and from the collection percentage | 16: `3752`, `3789`, the three Egyptian Gods `4998`–`5000`, `6989`, `7332`–`7341` | Listed both in the underground exclusion list (below) and in the 16 sorted ids at `BOOT.BIN` `0x088a0880` that `card_db_is_collection_excluded` (`0x08836da8`) removes from the collection percentage (`save_get_card_collection_permille`). The game therefore does not expect the player to own them. Routes (B8, `subsystems/shop.md`, "Password machine and conversion machine"): `7332`–`7341` only through the **password machine**, which does not give a copy but registers the card for the lab's rental list; `6989` (Elemental Hero Air Neos) only through the **conversion machine**, when exactly 59 cards are fed in (the password machine refuses it explicitly); `3752`, `3789` and the Gods (passcode 0) through neither machine. | H (lists, machine rules), M (rental meaning) |
| Excluded from random rewards only | 3: `3763`, `3787`, `3790` | In the underground exclusion list but counted in the collection percentage; no route found in the story, packs, the underground or either lab machine (passcode 0, and absent from every conversion result list). | H (absent from these routes) |

**The 19 non-token, non-prize cards by route** (B8, static): password machine (rental registration only) `7332`–`7341` (10); conversion machine `6989` (1); no route in the story, the packs, the underground or the lab machines `3752`, `3763`, `3787`, `3789`, `3790`, `4998`–`5000` (8). For those eight the remaining candidates outside this analysis are the external and wireless card gifts of `rel_title` (`ui_title_update_wireless_card_gift`, `ui_title_update_external_cards`, which set collection bit 7) and downloadable content (`rel_html_view`); not settled. Besides, any card with a passcode (3,399 cards, pack cards included) can be registered for rental, and the conversion machine can yield every pack card except `3737`, `6834` and `7351`.

The underground reward picker (`rel_underground` `+0x6a28`, modes `0x10`, `0x0e`, 7 and the default): every mode except `0x0e` walks the card ids `0xe88`–`0x1f39` (3720–7993) and keeps the ids that exist (`card_db_is_valid`), are not tokens (`card_db_is_token`) and are not in the **exclusion list** at module `+0x17b58` (24 `u32` ids ended by −1, tested by `+0x6dc8`: the 5 prizes, the 16 collection-excluded cards and `3763`/`3787`/`3790`); it then filters by rarity (`card_db_get_prop_bits22`, cardinfo word 1 bits 22–24): default mode rarity 0 or 1, mode 7 rarity 3 or 4, mode `0x10` one rarity drawn per reward from the 16-byte rows at `+0x17aa8` (176 bytes copied, 11 rows of four `u32` percentages for rarity 0, 1, 3 and 4, compared cumulatively with `rand() % 100`; the row index comes from `+0xdcd0` on work `+0xa60`); one of the kept ids is chosen with `system_rand_shifted() % count` and appended to the reward list at work `+0x54`. This also confirms the rarity reading of word 1 bits 22–24 (`cardinfo.md`).

## Writer and round trip

`tables.read_packs()` keeps each pack's descriptor address and tier list addresses with the values; `tables.write_packs(prx, packs)` writes the 48 records, the 48 descriptors and the card id lists back at those addresses (a port can relocate them by changing the addresses), and `tables.pack_spans()` lists the bytes the table owns. The round trip overwrites those bytes with a filler, writes the model back and compares the whole module: byte-identical (`pack_table` is `reimplemented`):

```
python3 -I tools/roundtrip.py --check <PSP_GAME> --only pack_table
```

## Open questions

- Pack names and artwork: which string table and texture belong to each pack index (`shop/all_<lang>.ehp` has `strTbl` with 35 entries and `pack_explain_str` with 392). **Answered elsewhere** (port-readiness audit, 2026-11-04): `string-tables.md` (`pack_name_str_<l>.bin` in the `BOOT.BIN` archive, `pack_explain_str_<l>.bin` in `shop/all_<l>.ehp`); the artwork mapping is cosmetic.
- Confirm in PPSSPP: a single purchase (DP before/after, save byte `+0x1542a + p`, counter `+0x16602`, one rarity entry written), and the rarity entries after 20 packs of one kind. Which visible element the shoulder-button purchase (mode 1) is in the UI was read from the input mask only. **Answered elsewhere** (port-readiness audit, 2026-11-04): `verification/results/2026-10-31-sessionE-P.md` E16, pass.
- The 99-entry card list at save `+0x161f6` (count `+0x161f4`) whose copies the result list shows (`0x08857158`/`0x088571c8`; presumably the trunk or a deck). **Answered** (B8, 2026-11-04): it is the lab rental list that `rel_select_card` picker mode 0 rewrites, whose entries the deck functions count as owned copies (`subsystems/shop.md`, "Password machine and conversion machine"); the value of its state byte (`+0x162bc`) is checked in PPSSPP G3.
- ~~How the 76 cards that are in the database but in no pack are obtained~~: answered statically 2026-11-04, see "Cards in no pack" below. The rules of the password machine (`rel_password`) and of the card conversion machine (`rel_conv_machine`) are settled too (B8, 2026-11-04): `subsystems/shop.md`, "Password machine and conversion machine". Still open: the route, if any, of the eight cards that neither machine gives (above).
