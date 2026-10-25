# Card database (`duelsys/cardinfo_<lang>.ehp`)

One EHP archive per language (`eng`, `fra`, `ger`, `ita`, `spa`; member suffix `E`, `F`, `G`, `I`, `S`), 14 members each. Loaded by `card_db_load_cardinfo` and bound by `card_db_bind_cardinfo` (`docs/subsystems/card_db.md`). Tool: `tools/cardinfo.py` (CSV/JSON export, `--check`). All integers little-endian.

The database has **3,554 records**: record 0 is empty, records 1–3,553 are cards. Every per-card table is indexed by this record index; the card **id** is a separate number (3720–7993) mapped to the index by `CARD_IntID`.

| Member | Language | Status | Size (eng) |
| --- | --- | --- | --- |
| `CARD_Prop.bin` | shared | documented | 8 × 3,554 |
| `CARD_Pass.bin` | shared | verified | 4 × 3,554 |
| `CARD_IntID.bin` | shared | verified | 2 × 4,274 |
| `CARD_Genre.bin` | shared | documented | 6 × 3,554 |
| `CARD_Indx_<L>.bin` | per language | verified | 8 × 3,555 |
| `CARD_Name_<L>.bin` | per language | verified | 126,084 |
| `CARD_Desc_<L>.bin` | per language | verified | 209,706 |
| `CARD_Huff_<L>.bin` | per language | verified | 826 |
| `DICT_<L>.bin` | per language | documented | 25,050 |
| `CARD_Sort_<L>.bin` | per language | documented | 2 × 3,554 |
| `CARD_Top_<L>.bin` | per language | documented | 110 |
| `CARD_SamePict_<L>.bin` | per language | named | 158 |
| `DLG_Indx_<L>.bin`, `DLG_Text_<L>.bin` | per language | documented | 3,208 / 59,232 |

## How it was verified

- Structure: `tools/cardinfo.py --check` passes for all five languages (every id maps back to its index, every description decodes and ends at or before the next one, every dictionary reference exists, sentinels match, `CARD_Sort` equals the collation rule and every `CARD_Top` entry points to the first card of its letter).
- Descriptions are bit-exact: in English all 3,553 Huffman streams end exactly at the next record's start bit.
- Content, against public card data: 28 well-known cards found by passcode (for example `89631139`, Blue-Eyes White Dragon, index 116, id 4007) all have the expected ATK/DEF; all 21 monsters among them have the expected level, and their attributes, types and card kinds are consistent; their decoded English names match, and Blue-Eyes White Dragon's description starts with its published text.

## `CARD_Prop.bin`: 8 bytes per record

| Bits | Field | Notes |
| --- | --- | --- |
| word 0, 0–13 | id | Card id (3720–7993). |
| word 0, 14–22 | ATK / 10 | 9 bits. |
| word 0, 23–31 | DEF / 10 | 9 bits. |
| word 1, 0–5 | kind | Every value is odd. 1 normal monster (613), 3 effect monster (1,311), 5 fusion (54), 7 effect fusion (90), 9 ritual, 11 effect ritual, 13 toon, 15 spirit, 17 union, 19 gemini, 21 token (52), 23 Egyptian god (3), 27 spell (723), 29 trap (552), 31 normal tuner, 33 effect tuner, 35 synchro, 37 effect synchro. Basis: card names in each group (for example 21 = the 52 "… Token" cards, 35 = Gaia Knight, the Force of Earth; 37 includes Brionac, Dragon of the Ice Barrier); the extra-deck lists of the opponent decks hold only 5/7/35/37 (`deck.md`). |
| word 1, 6–9 | attribute | 1 LIGHT, 2 DARK, 3 WATER, 4 FIRE, 5 EARTH, 6 WIND, 7 DIVINE (the three Egyptian gods), 8 spell, 9 trap. Basis: public card data for each value; this order differs from the one ygotfToolkit gives for other Tag Force games. |
| word 1, 10–13 | level | 0 for spells and traps. |
| word 1, 14–16 | icon | Spell/trap sub-type: 0 normal, 1 counter (Solemn Judgment), 2 field (Fallen Paradise), 3 equip, 4 continuous, 5 quick-play, 6 ritual (Black Luster Ritual). |
| word 1, 17–21 | type (race) | 1 Dragon, 2 Zombie, 3 Fiend, 4 Pyro, 5 Sea Serpent, 6 Rock, 7 Machine, 8 Fish, 9 Dinosaur, 10 Insect, 11 Beast, 12 Beast-Warrior, 13 Plant, 14 Aqua, 15 Warrior, 16 Winged Beast, 17 Fairy, 18 Spellcaster, 19 Thunder, 20 Reptile, 21 Psychic, 22 Divine-Beast, 23 spell, 24 trap. Basis: public card data for each value (for example Kairyu-Shin 5, Skull Servant 2, Mind Master 21); the same order, doubled, appears in ygotfToolkit's notes for TF4. |
| word 1, 22–31 | unknown | Values 0 (2,337), 1 (513), 3 (386), 4 (317). The game reads it as a 3-bit field, bits 22–24 (`card_db_get_prop_bits22`, `0x08832bdc`, exported); bits 25–31 are not read by any getter. |

## `CARD_Pass.bin`, `CARD_IntID.bin`

- `CARD_Pass`: `u32` per record, the 8-digit passcode printed on the card; 0 for 154 records without one.
- `CARD_IntID`: `u16` per id starting at 3720: `index = IntID[id − 3720]`, 0 for unused ids. The game returns index 0 for ids below 3720 (`card_db_index_of_id`).

## Names: `CARD_Indx_<L>`, `CARD_Name_<L>`

`CARD_Indx` has one 8-byte entry per record plus a sentinel: `u32 name_offset` (bytes into `CARD_Name`) and `u32 desc_offset` (**bits** into `CARD_Desc`). The sentinel holds the size of `CARD_Name` and the exact bit length of `CARD_Desc` (which is padded to a whole byte).

`CARD_Name` is a pool of UTF-16LE strings, each NUL-terminated and starting at a multiple of 4 (0 or 2 bytes of padding follow the NUL). It starts with 4 zero bytes; record 0's name is the empty string at offset 4.

## Descriptions: `CARD_Desc_<L>`, `CARD_Huff_<L>`, `DICT_<L>`

1. **Huffman** (`card_db_decode_huffman`). Bits are read most significant first within each byte, starting at `desc_offset`. `CARD_Huff` is a `u16` array holding a tree: start at node index 0; for each bit `b`, read `child = huff[node + b]`; if `child != 0`, consume the bit and continue at `node = child >> 1` (children are stored as byte offsets); if `child == 0` the node is a leaf, the bit is not consumed, and `huff[node + 2]` is the UTF-16 code unit. Internal nodes take two `u16`, leaves three (`0, 0, symbol`). Symbol 0 ends the text.
2. **Dictionary** (`card_db_expand_dictionary`). `$d` followed by three characters is replaced with dictionary word `atoi(those three)`; five code units are skipped even if `atoi` stopped early (one Italian text contains `$d02$`). Any other `$` + character is copied unchanged. English uses 51,465 references.
3. **Card names inside words** (`card_db_get_dictionary_word`). `DICT` is `u32 count`, `u32 table_offset`, `u32 string_base`, then `count` `u32` offsets; word `n` is the UTF-16LE string at `string_base + table[n]`. Inside a word, `%c` followed by four digits is replaced with the name of the card with that id.
4. **Card references** (`card_db_expand_card_refs`, `0x0883349c`, the last step of `card_db_get_description`). `$m` followed by four digits names another card by id (1,186 English descriptions contain one; for example a field spell naming the monster it supports) and is replaced with that card's name; any other `$` + character pair is copied unchanged.

The remaining escapes are left to the text renderer: `$C<digit>` sets a colour in dialog texts (`$C0` resets), and `$R` marks furigana in Japanese texts according to ygotfToolkit's notes. `tools/cardinfo.py` keeps all escapes, including `$m`, as the game stores them.

## Sorting and lookup tables

- `CARD_Sort_<L>`: `u16` per record, the record's position in the alphabetical card list (record 0 has 0; the others are a permutation of 1–3,553). The collation is below; it reproduces the table exactly in all five languages.
- `CARD_Top_<L>`: `u16 count` (27) followed by `count` pairs `(u16 character, u16 card id)`: `*` and `A`–`Z`. Each letter points to the first card in `CARD_Sort` order whose collation key starts with that letter, and `*` to the first card of the whole list (a symbol- or digit-initial name where one exists, for example `"A" Cell …` in English and the card named `7` in French). Checked for all 27 entries in all five languages by `tools/cardinfo.py --check`, high confidence. Presumably used for alphabet jumps in card lists.
- `CARD_SamePict_<L>`: `u16 count` (39) followed by `count` pairs `(u16 record index, u16 n)`. Records with several artworks appear here (Blue-Eyes White Dragon and Dark Magician both have `n = 3`); `n` is the number of artworks beyond the first: it equals the length of the card's artwork list minus one in every `card/*.cip` file for all 38 cards that have one (see `cip.md`), high confidence. Record 855 is listed but has a single image.
### Collation of `CARD_Sort`

Ranking the records by `(key(name), record index)` gives `CARD_Sort` exactly, for all 3,553 records in each of the five languages (`collation_key` in `tools/cardinfo.py`; `--check` compares the whole table). The key:

1. Case-insensitive (Unicode case folding).
2. Hyphens `-` and apostrophes `'` are skipped (`Alligator's …` before `All-Out …`, `Catnipped …` before `Cat's Ear …`, `D- Time` before `D. …`).
3. Diacritics are dropped: an accented letter sorts as its base letter (`é` = `e`, `ü` = `u`, not `ue`); `œ` expands to `oe` and `ß` to `ss`.
4. The remaining characters compare one by one by class, then by code point: class 0 is everything that is not a digit or a letter (space, `.`, `,`, `!`, `"`, `#`, `¡`, `¿`, `„`, `«`, …), class 1 digits, class 2 letters. A shorter key that is a prefix of a longer one sorts first.
5. Equal keys (only the seven pairs of identical token names, for example the four "Sheep Token" records) keep record order.

How much of this the data pin down: dropping `-`/`'` is forced (treating them as low or high symbols breaks 21–120 pairs per language), as are case folding (90–362 pairs), accent folding (5–246 pairs, umlaut-as-`ue` breaks 5) and `œ` → `oe` (11 French pairs). Space and `.` must be kept (ignoring either breaks 5–170 pairs). Symbols before digits is forced by one Spanish pair (`¿…` before `7`); otherwise the order inside class 0 and of the other punctuation (`:`, `!`) is not exercised, and `ß` is only constrained to sort between `s…` and `t…`. The game ships the table precomputed; no runtime collation code is needed.

## `CARD_Genre`: 6 bytes per record

Three `u16` words per record, read as one 48-bit flag set: genre `n` is bit `n & 15` of word `n >> 4`. 2,885 records have at least one flag; bits 38–47 are never set.

Readers (`docs/subsystems/card_db.md`): `card_db_has_genre(id, n)` (`0x08833004`) returns `(word[n >> 4] >> (n & 15)) & 1`; `card_db_get_genres(id, out)` (`0x088330a8`) copies the three words; `card_db_get_genre_name(n)` (`0x08833064`) returns DLG string `701 + n` (`0x08832c94`) for `0 ≤ n < 40` and a fixed fallback string otherwise. So the genre names are `DLG_Text` entries 701–740 of the same archive, in the card language, which makes the meanings direct evidence (high confidence). The card-detail code at `0x0884e3e4`, `0x0884e7b0` and `0x0884f3a0` loops over `n = 1 … 37` and lists each set genre.

| Bit | English name (DLG 701 + n) | Records | Notes from the card data |
| --- | --- | --- | --- |
| 0 | New Card | 0 | Never set in the file; presumably set at run time. |
| 1 | Remove card from play | 176 | |
| 2 | Destroy Spell/Trap | 233 | |
| 3 | Destroy monster | 361 | |
| 4 | Deck destruction | 57 | Milling the opponent's Deck (Needle Worm). |
| 5 | Hand destruction | 84 | |
| 6 | LV Monsters | 33 | 28 of the 30 names with "LV<n>", plus support cards. |
| 7 | Toon | 12 | The 9 toon-kind monsters (kind 13) plus support. |
| 8 | Spirit | 22 | The 14 spirit-kind monsters (kind 15) plus support. |
| 9 | Union | 32 | All 18 union-kind monsters (kind 17) plus partners such as X-Head Cannon. |
| 10 | Gemini | 26 | All 21 gemini-kind monsters (kind 19) plus support. |
| 11 | Tuner | 41 | 36 tuners (kinds 31/33) plus support. |
| 12 | Synchro | 35 | |
| 13 | Fusion Material | 198 | Mostly Normal Monsters named in fusion recipes. |
| 14 | Token | 103 | 51 of the 52 token records (kind 21) plus token makers. |
| 15 | Flip Effect | 112 | |
| 16 | Change card position | 136 | |
| 17 | Get control | 52 | |
| 18 | Cancel out Effect | 150 | Negation. |
| 19 | Attribute | 226 | Cards that refer to an Attribute. |
| 20 | Type | 354 | Cards that refer to a Type. |
| 21 | Return card | 80 | Bounce. |
| 22 | Increase draw | 150 | |
| 23 | Search Deck | 265 | |
| 24 | Recover cards from Graveyard | 301 | |
| 25 | Increase/Decrease ATK/DEF | 512 | |
| 26 | Pierce | 54 | |
| 27 | Cannot be destroyed | 117 | |
| 28 | Restrict Attack | 157 | |
| 29 | Direct Attack | 57 | |
| 30 | Multiple Attack | 50 | |
| 31 | Reduce Life Points | 278 | Burn and LP costs. |
| 32 | Recover Life Points | 89 | |
| 33 | Counter | 93 | Counters placed on cards. |
| 34 | Gamble | 61 | Coin tosses and dice. |
| 35 | Special Summon | 564 | |
| 36 | Cannot perform Normal Summon | 299 | All 144 fusion monsters (kinds 5/7), 28 of 31 ritual monsters, plus effect monsters that can only be Special Summoned. |
| 37 | Game Original | 94 | Anime/game cards such as Slash Draw and Fallen Paradise. |
| 38 | Card with a different artwork | 0 | Never set; presumably derived from `CARD_SamePict`. |
| 39 | (empty string) | 0 | |

The names are the game's own (English `DLG_Text`); the other languages translate them at the same indices. The flags look hand-assigned rather than derived from the text: keyword searches over names and descriptions agree with the bits only approximately (for example 530 of the 564 "Special Summon" records contain that phrase, but 875 records do).

A second accessor, `card_db_has_genre_mapped(id, k)` (`0x08833638`), maps `k` through the 35-entry `u32` table at `0x0889f980` (`32, 31, 22, 35, 18, 23, 24, 25, 16, 17, 3, 2, 5, 4, 1, 21, 26, 29, 30, 27, 28, 36, 15, 7, 8, 9, 10, 6, 0, 13, 14, 33, 34, 19, 20`) before testing the bit. It is exported to the modules (`rel_duel_eng`, `rel_story`, `rel_field`, `rel_shop` import it); `BOOT.BIN` `0x0886347c` calls it with `k = 22` (bit 15, Flip Effect). The table omits bits 11, 12, 37 and 38. Hypothesis (medium): it is the order of the deck editor's genre filter list.

`tools/cardinfo.py` exports the mask as `genre` (hex) and the names as `genres` (`; `-separated, in the archive's language).

## Duel prompts: `DLG_Indx_<L>`, `DLG_Text_<L>`

`DLG_Indx` is 802 `u32` byte offsets, ascending, into `DLG_Text`, a pool of NUL-terminated UTF-16LE strings with `$C<digit>` colour escapes (for example selection prompts during a duel).

## Open questions

- The meaning of word 1 bits 22–24 (read only through the export `0x08832bdc`; trace a module caller).
- `CARD_Genre`: who sets bits 0 (New Card) and 38 (different artwork) at run time, and whether the table at `0x0889f980` is the deck editor's filter order (trace the deck editor in PPSSPP).
- Why `CARD_SamePict` lists record 855, which has only one image in the `.cip` files.
- What the game does with descriptions longer than its 0x77a-byte buffers (`card_db_get_description` rotates four of them at `0x08924d5c`).
