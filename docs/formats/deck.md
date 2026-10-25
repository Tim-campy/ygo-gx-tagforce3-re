# Deck data: recipes (`.ydc`), owners, artwork tables, tutorial scripts

Tool: `tools/decks.py` (`recipes`, `samecard`, `tutorial`; CSV export and `--check`). Tests: `tools/tests/test_decks.py`. All integers little-endian. Addresses are `BOOT.BIN` virtual addresses (base `0x08804000`; for every section used here, file offset = vaddr − `0x08804000` + `0x54`).

| Structure | Where | Status |
| --- | --- | --- |
| `.ydc` deck recipe | 661 members `RCP000.ydc`–`RCP660.ydc` of the EHP embedded in `BOOT.BIN` at `0x088d77e0` | verified (round-trips; loader read) |
| Recipe names | `recipe_name_<l>.bin` (`e f g i j s`) in the same archive | documented |
| Recipe owner table | `BOOT.BIN` `0x08915f28`, 126 × 16 bytes | documented |
| Recipe level table | `BOOT.BIN` `0x089143f0`, 462 × `u16` | documented (meaning: hypothesis) |
| Owner variant table | `BOOT.BIN` `0x08916730`, 67 × 12 bytes | documented (fields: hypothesis) |
| In-memory deck | 0xc0-byte struct filled by `deck_load_recipe` | documented |
| `sameCardTbl.dat` | `deck/all_<l>.ehp` | documented |
| `fileTbl.dat` | `deck/all_<l>.ehp` | documented |
| `deck_tutorialNN.bin` | `deck/tutorial.ehp` | documented (instruction lengths; semantics mostly open) |

`deck_tutorialNN.bin` is **not** a deck format: it is a bytecode script for the deck-construction tutorial (see below).

## `.ydc` deck recipe

The built-in decks of every duellist ("recipes") are `.ydc` files inside an EHP archive embedded in `BOOT.BIN`'s data (file offset `0xd3834`, 0x278f0 bytes, 667 members: `RCP000.ydc`–`RCP660.ydc` plus six `recipe_name_<l>.bin`). It is one of the six embedded archives listed in `docs/formats/ehp.md`. Member sizes are 94–134 bytes.

| Offset | Size | Field | Notes |
| --- | --- | --- | --- |
| `0x0` | 1 | version | `1` in all 661 files. |
| `0x1` | 3 | padding | Always `CC CC CC` (a typical uninitialised-memory fill of the authoring tool). |
| `0x4` | 4 | unknown | 12 distinct values; one value (`0x4771a8b1`) is shared by 461 different decks, so it is not a checksum of the contents. It changes in blocks across the recipe numbers and looks like an authoring-tool artefact. `deck_load_recipe` does not read bytes `0x0`–`0x7`. |
| `0x8` | 2 | `main_count` | 40–60 in the data (379 decks have 40, 222 have 42; two have 60). |
| `0xa` | 2 × `main_count` | main deck | Card ids. |
| next | 2 | `extra_count` | 0–15 (133 decks have an extra deck). |
| next | 2 × `extra_count` | extra deck | Card ids. |
| next | 2 | `side_count` | 0–15 (7 decks, including recipe 0, have a side deck). |
| next | 2 × `side_count` | side deck | Card ids. |
| end | | | The file ends exactly after the side deck in all 661 files. |

Evidence (confidence high):

- Structure: all 661 files parse into exactly three counted lists that end at the member end, and `tools/decks.py` rebuilds every file byte for byte from the parsed form. All 28,069 ids exist in the card database. No card appears more than 3 times in a deck (main + extra + side).
- Section meaning, from card kinds (`CARD_Prop` word 1 bits 0–5, `docs/formats/cardinfo.md`): the second list contains only kinds 5 and 7 (fusion monsters) and 35 and 37, the first and third never contain kinds 5, 7, 35 or 37. So the second list is the extra deck and 35/37 are extra-deck monsters too; the cards of kind 37 seen here (for example `Brionac, Dragon of the Ice Barrier`) are Synchro monsters. The third list holds ordinary main-deck cards, so it is the side deck.
- Code: `deck_load_recipe(index, deck)` (`0x0885c3dc`) clears `deck` (0xc0 bytes), formats `"RCP%03d.ydc"` (`0x08916710`), finds the member in the archive at `0x088d77e0` (`container_ehp_find_member`), then reads the count at `+0x8` and the lists in file order with these limits: main `< 0x3d` (≤ 60), extra `< 0x10` (≤ 15), side `< 0x10` (≤ 15). If any limit fails the whole deck is cleared again.
- Content: recipe names (below) match the decks, for example the decks named after Jaden Yuki are Elemental HERO / Neo-Spacian decks with Elemental HERO fusions in the extra deck, the Syrus Truesdale decks are "-roid" machine decks, and a Joshua deck is a Six Samurai deck.

Observations: 611 of 661 main decks list monsters before spells before traps, and in 637 the copies of a card are adjacent; the order has no meaning to the loader. 75 recipes are byte-identical copies of an earlier one; one body (a classic Blue-Eyes / Dark Magician deck) fills 58 of the slots 462–660, apparently as a placeholder.

### In-memory deck (`deck_load_recipe` output)

| Offset | Size | Field |
| --- | --- | --- |
| `0x00` | 4 | main count |
| `0x04` | 4 | side count |
| `0x08` | 4 | extra count |
| `0x0c` | 2 × 60 | main deck ids |
| `0x84` | 2 × 15 | side deck ids |
| `0xa2` | 2 × 15 | extra deck ids |
| `0xc0` | | end |

Note that memory order (main, side, extra) differs from file order (main, extra, side). Confidence high (store offsets read from `0x0885c43c`–`0x0885c4f8`). Whether the player's own decks in save data use this struct is open.

## Recipe names: `recipe_name_<l>.bin`

A string table in the format also used by `strTbl` members: `u32 count`, `u32 table_offset` (12), `u32 string_base`, then `count` `u32` offsets relative to `string_base`; each string is UTF-16LE, NUL-terminated. All six languages have 463 entries. Name `i` belongs to recipe `i` for `i` < 462 ("Starting Deck", then `<character> 01`, `<character> 02`, …); entry 462 is empty and recipes 462–660 have no name. `deck_get_recipe_name(index)` (`0x0885c314`) first checks that `RCP<index>.ydc` exists, replaces the `x` in `"recipe_name_x.bin"` (`0x0891671c`) with the current language letter from `"jegfis"` (`0x08916708`, indexed by `0x08857b80()`), and returns string `index` via `0x08836ed0`.

## Recipe owner table: `0x08915f28`

126 records of 16 bytes, sorted by owner id and binary-searched (`0x0880a4a4(key, table, 0x7e, 0x10, compare 0x0885ce3c)`, compare = `u32` subtraction):

| Offset | Size | Field | Notes |
| --- | --- | --- | --- |
| `0x0` | 4 | owner id | 1–126, consecutive. |
| `0x4` | 4 | first recipe | |
| `0x8` | 4 | recipe count | 1–10. |
| `0xc` | 4 | zero | |

The records cover recipes 0–461 contiguously without gaps or overlaps (owner 1 = recipe 0, "Starting Deck"; owner 2 = recipes 1–10, Jaden Yuki 01–10; …; 125 owners for 461 character decks: 7 with 8 or 10 decks, 33 with 4, 6 with 5 and 79 with 3). The name groups of `recipe_name_e` match the records one for one. Readers: `deck_get_owner_recipe_count(owner)` (`0x0885cc3c`, returns the count or 0) and `deck_get_owner_recipe(owner, n)` (`0x0885cc80`, returns `first + n`, or −1 when `n` is out of range or the owner is not listed). Confidence high for the layout; that the owner id is the game's character id is a hypothesis (medium: it indexes a per-owner array of 0x16c-byte records in `0x08854218`).

## Recipe level table: `0x089143f0`

462 `u16` values, one per named recipe, all 1–10. `deck_get_recipe_level(index)` (`0x0885c2dc`) returns the value for 0 ≤ index < 462 and 1 otherwise. Hypothesis (medium): the difficulty "level" or star rating shown for a deck. Its only caller in `BOOT.BIN` is `deck_load_recipe`, which ignores the result.

## Owner variant table: `0x08916730`

67 records of 12 bytes: `u32 owner`, `u32 stage`, `u32 variant`, sorted by owner then stage, for owners 1–45. `deck_select_owner_variant(owner, stage)` (`0x0885cd2c`): when the mode returned by `0x0885aeb0` is 0 or 2 it linearly searches this table for `(owner, stage)` and returns `variant`; for owner 8 at stage 1 the variant is increased by one when `0x08857dd0(8)` returns ≥ 2000; in mode 1 it returns 1; otherwise 0 for owner 1 and −1 for everyone else. `0x0885ccfc(owner, stage)` combines it with `deck_get_owner_recipe`; `0x08854218(owner, stage)` uses that to pick and load a duellist's deck and stores owner, stage and recipe at offsets `0x48c8`/`0x48cc`/`0x48d0` of a per-owner record. Every variant is smaller than its owner's recipe count. The meaning of `stage` (story chapter? number of duels won?) and of the mode is open; confidence for the field roles: low–medium.

## Other runs of card ids in the executables

A scan for ≥ 20 consecutive valid card ids (`u16`, even-aligned) finds 787 runs in `BOOT.BIN`: 661 are the `.ydc` files (this includes the area around file offset `0xdb606`), 63 are byte-identical copies of the `rel_shop.prx` pack lists (`docs/formats/packs.md`; from file offset `0x9d834`), and 63 are other data: zero-terminated lists of 3–71 ids at file offsets `0xa3560`–`0xa3c80` (some contain a card 4–6 times, so they are not decks; purpose unknown), one list at `0x99bf0`, and false positives in byte data at `0xb3f1e`+ (repeated `0x13` bytes read as id 4883). In `gmodule/`, `rel_shop.prx` and `rel_story.prx` hold the pack lists, `rel_conv_machine.prx` has 46 runs (one of 1,199 ids at `0x94e8`) and `rel_duel_eng.prx` three; none of these were decoded here. No module contains another deck format: opponent decks come only from the recipe archive.

## `sameCardTbl.dat` (`deck/all_<l>.ehp`)

200 bytes, identical in all five languages: `u32 count` (49), then `count` pairs `(u16 card id, u16 artwork number)`. For each card the numbers run 1, 2, …, n without gaps (38 cards: 30 with n = 1, 5 with n = 2, 3 with n = 3, for example Blue-Eyes White Dragon, Dark Magician and Red-Eyes B. Dragon have 3).

Relation to `CARD_SamePict_<L>` (`docs/formats/cardinfo.md`, 39 pairs `(record index, n)`): for all 38 cards of `sameCardTbl`, `n` equals the `CARD_SamePict` value of the same card, so `n` in `CARD_SamePict` is the number of **alternative** artworks besides the normal one (confidence medium-high: the counts agree exactly; that the entries are artworks rests on the archive names and on the cards involved, which are those with famous reprint artworks). `CARD_SamePict` has one card more, Big Shield Gardna (n = 1), which has no entry here. Hypothesis (low): the position of a pair in `sameCardTbl` selects the image slot of that alternative artwork.

## `fileTbl.dat` (`deck/all_<l>.ehp`)

7,006 bytes, identical in all five languages: `u16 count` (3,502), then `count` `u16` values. Slot 0 is 0; slots 1–3,501 are the ids of all 3,501 cards that are not tokens, strictly ascending. The 52 cards missing are exactly the cards of kind 21 (tokens). Hypothesis (medium): the slot number is a card's image index in a card-image container, which would explain slot 0 as "no card". (The stored layout can also be read as a `u32` count followed by 3,501 ids; the `u16` reading gives one entry per counted slot.)

## Deck-tutorial script: `deck_tutorial00.bin`–`04.bin` (`deck/tutorial.ehp`)

Loaded by `rel_decktutorial.prx` (strings `deck/tutorial.ehp`, `deck_tutorial%02d.bin`). Each file is a sequence of instructions: one opcode byte followed by fixed-length arguments, ending with opcode `0x17`. With the length table below all five files (730, 272, 147, 1,520 and 1,591 bytes; 732 instructions) parse exactly, ending at their last byte. Confidence high for the lengths, low for meanings.

| Opcode | Length | Arguments | Notes |
| --- | --- | --- | --- |
| `0x01` | 9 | `u16 string, u16 x, u16 y, u16 width` | 149 uses; usually `(60, 96, 360)`: a message box. |
| `0x02` | 7 | `u16 string, u16 x, u16 y` | 51 uses; a positioned text. |
| `0x04` | 5 | `u16 string, u16 n` | |
| `0x05` | 3 | `u16` | Values 0–21, mostly ascending: probably a step or page number. |
| `0x07` | 5 | `u32` | Small bit masks. |
| `0x09` | 9 | `u32, u32` | First word always 0, second a single bit (`0x10`–`0x8000`): probably a button mask to wait for. |
| `0x0a` | 5 | `u16, u16` | Often `(0, 30)`, `(0, 16)`, `(0, 8)`: probably a wait in frames. |
| `0x0b` | 3 | `u16 card id` | Valid card ids (for example Polymerization). |
| `0x0d` | 3 | `u16` | 0–5. |
| `0x0f` | 9 | `u16 index, u16 string, u16, u16` | |
| `0x10` | 5 | `u16, u16` | |
| `0x13` | 3 | `u16` | |
| `0x14` | 7 | `u16, u16, u16` | |
| `0x16` | 9 | `u32, u32` | |
| `0x03 0x06 0x08 0x0c 0x0e 0x11 0x12 0x15` | 1 | — | |
| `0x17` | 1 | — | End of script. |

String arguments index `strTbl_<l>.bin` of the same archive (same string-table layout as above, 229 entries in every language). The scripts reference 223 different strings, each exactly once, all below 229; the six unreferenced entries are 0–3 (menu captions such as "Sample Deck" and "End tutorial?"), 84 and 228.

## Open questions

- The `u32` at `.ydc` offset 4: who wrote it and whether anything reads it.
- Which duellists use recipes 462–660 (unnamed, mostly in groups of five with two placeholder copies); no table referencing them was found in `BOOT.BIN`, and the modules were not searched with code analysis.
- Whether the owner id is the character id used by `chr_name_<l>.bin` (466 entries, apparently three name forms per character) and the rest of the game.
- The `stage` argument and mode of `deck_select_owner_variant`, and the value compared with 2000 for owner 8.
- What the recipe level is used for (the deck-recipe viewer `rel_recipeviewer.prx` is the likely reader).
- The player's deck format in save data, and whether it is the 0xc0-byte in-memory struct.
- The image container indexed by `fileTbl` / `sameCardTbl` slots (`card/*.cip` headers contain the id range `0xe88`–`0x1f39`).
- Meanings of the tutorial opcodes; string 84 is never referenced.
- The zero-terminated card lists at `BOOT.BIN` file offsets `0xa3560`–`0xa3c80` and the id runs in `rel_conv_machine.prx`.
