# UI and system string tables (`strTbl*.bin`, `*_strtbl*.bin`, `*_msg_<l>.bin`, ...)

Status: `reimplemented` (`strtbl`, `strtbl_offset_list` in `re/formats.csv`). Reader and dumper: `tools/strtbl.py`. Basis: the layout was read from the files (a survey of every `.bin` file and member on the disc, below) and matches the readers already in the repository (`tools/decks.py`, `tools/voices.py`) and the recipe-name lookup in `BOOT.BIN` (`deck_get_recipe_name`, `0x0885c314`, `deck.md`). Confidence: high for the layout; the meaning of individual entries is screen code and is not covered here.

All values are little-endian. Strings are UTF-16LE and NUL-terminated (`00 00`); markup such as `%s`, `%d` and line breaks (`\n`) is part of the text.

## Layout A: `strtbl` (headed)

| Offset | Type | Field |
| --- | --- | --- |
| `+0x00` | u32 | `count`: number of offsets |
| `+0x04` | u32 | Offset of the offset table: always `12` |
| `+0x08` | u32 | `string_base` |
| `+0x0c` | `count` × u32 | Offsets of the strings, relative to `string_base`, ascending |
| `string_base` | | UTF-16LE strings, packed back to back |

On this disc `string_base` = `12 + 4·count` in every table except `DICT_<l>.bin` (card-description dictionary, `cardinfo.md`), which leaves 4 bytes between the offsets and the strings.

**End offset.** In 1,790 of the 1,815 headed tables the last offset equals the size of the string block (`file size − string_base`): it is an end marker, not a string. Such a table of `count` offsets therefore holds `count − 1` strings; reading entry `count − 1` returns an empty string, which is what the game would see if it asked for it. The 25 tables without an end offset are the 20 `NN_message_res.bin` of `tutorial/tutorial_<l>.ehp` and the five `DICT_<l>.bin`. `strtbl.py` reports strings without the end offset and records whether one was present (`has_end_offset`).

Every string of every table is packed directly after the previous one (string `i` ends where offset `i + 1` points), so the tables can be rebuilt from the string list alone: `strtbl.build()` reproduces 1,846 of the 1,851 tables byte for byte; the five `DICT_<l>.bin` differ only by their 4-byte gap.

## Layout B: `offset_list` (`pack_*_str_<l>.bin`)

| Offset | Type | Field |
| --- | --- | --- |
| `+0x00` | u32 | `string_base` = `4 + 4·count` (so `count` = `string_base / 4 − 1`) |
| `+0x04` | `count` × u32 | Offsets relative to `string_base`, ascending; the first is 0, the last is the end offset |
| `string_base` | | UTF-16LE strings |

Used only by the pack tables: `pack_explain_str_<l>.bin` in `shop/all_<l>.ehp` (97 offsets = 96 strings; each of the five shop archives carries all six languages `e f g i j s`, 30 files) and `pack_name_str_<l>.bin` in the EHP embedded in `BOOT.BIN` at file offset `0x10d5d4` (49 offsets = 48 strings, one per booster pack, `packs.md`; six languages). The second word being 0 (the first offset) is what distinguishes it from layout A, whose second word is 12.

## Census (reference dump)

`python3 -I tools/strtbl.py check <PSP_GAME>` walks every file, every EHP member (nested archives and gzip members included) and the archives embedded in `BOOT.BIN`, and parses every `.bin`:

| Group | Files |
| --- | --- |
| `.bin` files and members in total | 2,273 |
| String tables, layout A with end offset | 1,790 |
| String tables, layout A without end offset (`NN_message_res.bin`, `DICT_<l>.bin`) | 25 |
| String tables, layout B (`pack_*_str_<l>.bin`) | 36 |
| Text in another documented layout: `CARD_Name_<l>`, `DLG_Text_<l>` (`cardinfo.md`), `SysMsgI<l>`/`SysMsgL<l>` (`story.md`), `tuto_text_<l>` (`tutorial.md`) | 26 |
| Other data (voice-id maps `*_voiceidchgtbl.bin` (`sound.md`), card tables, tutorial scripts, ...) | 396 |

1,851 string tables with 191,593 strings in total. No `.bin` whose name suggests text (`str`, `msg`, `tbl`, `name`, `text`, `word`, `explain`, `result`, `dict`) is left unparsed.

Families of layout A (files counted over all languages and all archives that carry a copy; string counts are without the end offset):

| Family | Files | Strings | Where / content |
| --- | --- | --- | --- |
| `strTbl.bin`, `strTbl_<l>.bin` | 40 + 114 | 1–295 | Per-screen text of the scene archives in `database/` (46), `duel/` (35), `shop/` (30), `minigame/` (20), `labo/` (12) and `deck/` (11); the language is in the archive name or the member suffix. |
| `field_strtbl.bin`, `_item`, `_mapname`, `field_strtbl_<l>.bin` | 35 + 35 + 35 + 6 | 129 / 201 / 56 / 129 | Field UI (`field-tables.md`). |
| `option_msg_<l>.bin` | 131 | 39 | Options screen. |
| `title_msg_<l>.bin`, `tushin_msg_<l>.bin`, `duelmenu_msg_<l>.bin`, `sysmsg_<l>.bin` | 30, 30, 35, 6 | 95, 158, 10, 32 | Title, communication (`tushin`), duel menu and system messages. |
| `ddstrtbl_<l>.bin` | 66 | 97 | Duel strings. |
| `help_strtbl_contents*.bin`, `help_strtbl_label*.bin` | 5 + 15, 5 + 15 | 183/200, 9 | Help screens. |
| `mini_result_<l>.bin`, `quiz_strtbl_<l>.bin`, `underground_strtbl_<l>.bin` | 25, 6, 10 | 31, 37, 53 | Minigames. |
| `recipe_name_<l>.bin` | 6 | 462 | Deck recipe names (`BOOT.BIN` archive, `deck.md`). |
| `chr_name_<l>.bin` | 6 | 465 | Character names (`BOOT.BIN` archive). |
| `chr_wordstbl_<l>.bin`, `chrcutin_*_wordstbl_<l>.bin`, `chrzakovN_wordstbl_<l>.bin` | 570 + 366 + 198 | 51–677 | Voice captions (`sound.md`, `voices.py`). |
| `NN_message_res.bin` | 20 | 126–197 | `tutorial/tutorial_<l>.ehp` (no end offset; legacy set the game does not load, `tutorial.md`). |
| `DICT_<l>.bin` | 5 | 990–1000 | Card-description dictionary (`cardinfo.md`; 4-byte gap, no end offset). |

## Commands

```
python3 -I tools/strtbl.py check <PSP_GAME>                                  # census, exit 1 if a text-like .bin fails
python3 -I tools/strtbl.py show <USRDIR>/field/always_bri_eng.ehp field_strtbl.bin [-o extracted/strtbl/field.tsv]
python3 -I tools/strtbl.py dump <USRDIR> -o extracted/strtbl                    # one JSON file per table
```

`show` prints `index<TAB>string` with `\n`, `\t` and `\\` escaped. `dump` writes `{source, layout, has_end_offset, strings}` per table, at `<output>/<path of the archive>/<member>.json` (`@` in an embedded-archive label becomes `_at_`). Members inside archives are named as in `ehp.py` (`inner.ehp/member` or `inner.ehp:member`). Output is game text: the tool refuses to write inside the repository unless the path is under an `extracted/` directory.

## Open questions

- Which index each screen reads: mapped statically by `tools/scenes.py` (`ui.md`, "Scene map"): every table but those in unreferenced archives is attributed to a scene, and 332 of 854 accessor calls give both table and constant index. The rest choose the table at runtime (PPSSPP).
- All headed tables are read through one accessor, `card_db_get_dictionary_word(table, index)` (`0x08836ed0`), with the table from `container_ehp_find_member`.
- Whether any code reads the end offset (for example to compute a string's length) or only uses offsets as start positions.
- What `pack_explain_str` entries 48–95 are (two strings per pack, or a second set for alternative pack states; not checked against the shop code).
