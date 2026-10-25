# Card database (`duelsys/cardinfo_<lang>.ehp`)

One EHP archive per language (`eng`, `fra`, `ger`, `ita`, `spa`; member suffix `E`, `F`, `G`, `I`, `S`), 14 members each. Loaded by `card_db_load_cardinfo` and bound by `card_db_bind_cardinfo` (`docs/subsystems/card_db.md`). Tool: `tools/cardinfo.py` (CSV/JSON export, `--check`). All integers little-endian.

The database has **3,554 records**: record 0 is empty, records 1–3,553 are cards. Every per-card table is indexed by this record index; the card **id** is a separate number (3720–7993) mapped to the index by `CARD_IntID`.

| Member | Language | Status | Size (eng) |
| --- | --- | --- | --- |
| `CARD_Prop.bin` | shared | documented | 8 × 3,554 |
| `CARD_Pass.bin` | shared | verified | 4 × 3,554 |
| `CARD_IntID.bin` | shared | verified | 2 × 4,274 |
| `CARD_Genre.bin` | shared | named | 6 × 3,554 |
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

- Structure: `tools/cardinfo.py --check` passes for all five languages (every id maps back to its index, every description decodes and ends at or before the next one, every dictionary reference exists, sentinels match).
- Descriptions are bit-exact: in English all 3,553 Huffman streams end exactly at the next record's start bit.
- Content, against public card data: 28 well-known cards found by passcode (for example `89631139`, Blue-Eyes White Dragon, index 116, id 4007) all have the expected ATK/DEF; all 21 monsters among them have the expected level, and their attributes, types and card kinds are consistent; their decoded English names match, and Blue-Eyes White Dragon's description starts with its published text.

## `CARD_Prop.bin`: 8 bytes per record

| Bits | Field | Notes |
| --- | --- | --- |
| word 0, 0–13 | id | Card id (3720–7993). |
| word 0, 14–22 | ATK / 10 | 9 bits. |
| word 0, 23–31 | DEF / 10 | 9 bits. |
| word 1, 0–5 | kind | Values seen with counts: `1` (613), `3` (1,311), `5` (54), `7` (90), `9`–`23` (odd, 148 in total), `27` (723), `29` (552), `31`–`37` (odd, 62). Confirmed: 1 normal monster, 3 effect monster, 5 fusion, 7 effect fusion, 27 spell, 29 trap. Every value is odd. |
| word 1, 6–9 | attribute | Confirmed: 1 LIGHT, 2 DARK, 4 FIRE, 5 EARTH, 6 WIND, 8 spell, 9 trap. Hypotheses: 3 WATER (248 cards), 7 DIVINE (3 cards). |
| word 1, 10–13 | level | 0 for spells and traps. |
| word 1, 14–16 | icon | Spell/trap sub-type: 0 normal; 5 seen on a quick-play spell; 1–6 otherwise unconfirmed. |
| word 1, 17–21 | type (race) | Confirmed: 1 Dragon, 3 Fiend, 7 Machine, 15 Warrior, 16 Winged Beast, 17 Fairy, 18 Spellcaster, 23 spell, 24 trap. The other values (2, 4–6, 8–14, 19–22) are unconfirmed; 22 has 3 cards (likely Divine-Beast). |
| word 1, 22–31 | unknown | Values 0 (2,337), 1 (513), 3 (386), 4 (317). |

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

Remaining escapes are left to the text renderer; dialog texts use `$C<digit>` (colour, `$C0` resets). English card descriptions contain none after expansion.

## Sorting and lookup tables

- `CARD_Sort_<L>`: `u16` per record, the record's position in the alphabetical card list (record 0 has 0; the others are a permutation of 1–3,553). The order is case-insensitive and keeps spaces but not all punctuation (`30,000-Year …` sorts before `3-Hump …`); 3,511 of 3,552 neighbouring pairs agree with a plain case-insensitive comparison. The exact collation is open.
- `CARD_Top_<L>`: `u16 count` (27) followed by `count` pairs `(u16 character, u16 card id)`: `*` and `A`–`Z`, each pointing to a card whose name starts with that character (`*` covers names that start with a symbol). Hypothesis: the first card of each letter, for alphabet jumps in card lists.
- `CARD_SamePict_<L>`: `u16 count` (39) followed by `count` pairs `(u16 record index, u16 n)`. Records with several artworks appear here (Blue-Eyes White Dragon and Dark Magician both have `n = 3`); `n` is the number of artworks beyond the first: it equals the length of the card's artwork list minus one in every `card/*.cip` file for all 38 cards that have one (see `cip.md`), high confidence. Record 855 is listed but has a single image.
- `CARD_Genre`: 6 bytes per record, non-zero for 2,885 records; presumably 48 category flags used by deck search. Not decoded.

## Duel prompts: `DLG_Indx_<L>`, `DLG_Text_<L>`

`DLG_Indx` is 802 `u32` byte offsets, ascending, into `DLG_Text`, a pool of NUL-terminated UTF-16LE strings with `$C<digit>` colour escapes (for example selection prompts during a duel).

## Open questions

- Remaining `kind`, `attribute`, `type` and `icon` values; the meaning of word 1 bits 22–31.
- `CARD_Genre` flag meanings.
- The exact collation behind `CARD_Sort`, and whether `CARD_Top` points to the first card of each letter.
- Why `CARD_SamePict` lists record 855, which has only one image in the `.cip` files.
- What the game does with descriptions longer than its 0x77a-byte buffers (`card_db_get_description` rotates four of them at `0x08924d5c`).
