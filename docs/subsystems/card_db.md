# Card database (work package 2)

The whole card database lives in `duelsys/cardinfo_<lang>.ehp`; its layout is in `docs/formats/cardinfo.md`, and `tools/cardinfo.py` exports it:

```
python3 -I tools/cardinfo.py extracted/umd/PSP_GAME/USRDIR/duelsys/cardinfo_eng.ehp --check
python3 -I tools/cardinfo.py extracted/umd/PSP_GAME/USRDIR/duelsys/cardinfo_eng.ehp -o extracted/cards_eng.csv
```

The export is game content: keep it under `extracted/`, never in git.

## How the game uses it

1. `card_db_load_cardinfo` builds `…cardinfo_<lang>.ehp` from a language table and loads it to `0x08926b50`.
2. `card_db_bind_cardinfo` binds the archive and stores a pointer to each member in a table of globals at `0x08924d1c` (cleared over `0x1e2c` bytes first):

| Global | Member | Global | Member |
| --- | --- | --- | --- |
| `0x08924d1c` | `CARD_Name` | `0x08924d40` | `CARD_Top` |
| `0x08924d24` | `CARD_Indx` | `0x08924d44` | `CARD_SamePict` |
| `0x08924d2c` | `CARD_Desc` | `0x08924d48` | `CARD_Prop` |
| `0x08924d30` | `CARD_Sort` | `0x08924d4c` | `CARD_Pass` |
| `0x08924d34` | `DLG_Indx` | `0x08924d50` | `CARD_IntID` |
| `0x08924d38` | `DLG_Text` | `0x08924d54` | `DICT` |
| `0x08924d3c` | `CARD_Genre` | `0x08924d58` | `CARD_Huff` |

3. Accessors take a card **id** and go through `card_db_index_of_id`.

## Key functions

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x08832684` | `card_db_load_cardinfo` | H | Builds the path from `…cardinfo_`, a language suffix (table at `0x08878c88`, 8 bytes per language, index from `0x08857b80`) and `.ehp`; `container_get_file_size(5, …)`, then `container_load_file` to `0x08926b50` with completion callback `0x08832a04`. |
| `0x08832778` | `card_db_bind_cardinfo` | H | Binds the loaded archive and looks up all 14 members into the globals above. |
| `0x08832718` | `card_db_append_language_suffix` | M | Called on `CARD_Name_` etc. before each lookup of a per-language member, whose real names end in `<L>.bin`; body not read. |
| `0x08832a1c` | `card_db_index_of_id(id) → index` | H | `id < 0xe88 ? 0 : IntID[id − 0xe88]`. |
| `0x08832a68` | `card_db_get_name(id) → UTF-16 string` | H | `Name + Indx[index].name_offset`. |
| `0x08832b54` | `card_db_get_prop(id) → record` | H | `Prop + 8 × index`; 11 callers (presumably the field getters). |
| `0x08832c04` | `card_db_get_passcode(id)` | H | `Pass[index]`. |
| `0x08832aa4` | `card_db_get_description(id) → UTF-16 string` | H | Huffman-decodes from `Indx[index].desc_offset`, expands the dictionary, then copies into one of four rotating `0x77a`-byte buffers at `0x08924d5c` via `0x0883349c`. |
| `0x088332e4` | `card_db_decode_huffman(out, desc, bit)` | H | Tree walk described in `cardinfo.md`. |
| `0x08833390` | `card_db_expand_dictionary(out, in)` | H | `$d` + 3 characters → `card_db_get_dictionary_word(DICT, atoi(…))`, appended with the format `%s` (`0x0889f970`). |
| `0x08836ed0` | `card_db_get_dictionary_word(dict, n)` | H | Bounds check against `dict[0]`, address `dict + dict[1][n] + dict[2]`, expands `%c` + 4 digits with `card_db_get_name`; results go to one of 50 rotating `0x200`-byte buffers at `0x08ac6580`. |

Readers of the other tables, not yet decompiled: `CARD_Sort` `0x08832bac`, `DLG_*` `0x08832c94`, `CARD_Genre` `0x08833004`/`0x088330a8`, `CARD_Top` `0x088330fc`/`0x0883310c`/`0x08833164`, `CARD_SamePict` `0x08833230`.

## Open questions

- See `docs/formats/cardinfo.md` for the open fields.
- Pack contents (48 themed packs) and deck restrictions are not in `cardinfo`; locate them (candidates: `database/`, `shop/`, the forbidden/limited list).
- Card effects: no effect data or script references are in `cardinfo`, so effects live elsewhere (WP4).
- `card/*.cip`: card images, format unknown.
