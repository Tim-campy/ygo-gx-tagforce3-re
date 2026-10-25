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
| `0x08832684` | `card_db_load_cardinfo` | H | Builds the path from `…cardinfo_`, a language suffix (table at `0x08878c88`, 8 bytes per language, index from `save_get_language`, `0x08857b80`) and `.ehp`; `container_get_file_size(5, …)`, then `container_load_file` to `0x08926b50` with completion callback `card_db_on_cardinfo_loaded` (`0x08832a04`). No direct caller (exported). |
| `0x08832778` | `card_db_bind_cardinfo` | H | Binds the loaded archive and looks up all 14 members into the globals above. |
| `0x08832718` | `card_db_append_language_suffix(name)` | H | Appends the first letter of the language's code (table `0x08878c88`, index `save_get_language()`) minus `0x20` (upper case) and the suffix at `0x0889f8b0`. Called by `card_db_bind_cardinfo` on `CARD_Name_` etc. before each lookup of a per-language member, whose real names end in `<L>.bin`. |
| `0x08832a1c` | `card_db_index_of_id(id) → index` | H | `id < 0xe88 ? 0 : IntID[id − 0xe88]`. |
| `0x08832a68` | `card_db_get_name(id) → UTF-16 string` | H | `Name + Indx[index].name_offset`. |
| `0x08832b54` | `card_db_get_prop(id) → record` | H | `Prop + 8 × index`; 11 callers (presumably the field getters). |
| `0x08832c04` | `card_db_get_passcode(id)` | H | `Pass[index]`. |
| `0x08832aa4` | `card_db_get_description(id) → UTF-16 string` | H | Huffman-decodes from `Indx[index].desc_offset`, expands the dictionary, then copies into one of four rotating `0x77a`-byte buffers at `0x08924d5c` via `card_db_expand_card_refs` (`0x0883349c`). |
| `0x088332e4` | `card_db_decode_huffman(out, desc, bit)` | H | Tree walk described in `cardinfo.md`. |
| `0x08833390` | `card_db_expand_dictionary(out, in)` | H | `$d` + 3 characters → `card_db_get_dictionary_word(DICT, atoi(…))`, appended with the format `%s` (`0x0889f970`). |
| `0x08836ed0` | `card_db_get_dictionary_word(dict, n)` | H | Bounds check against `dict[0]`, address `dict + dict[1][n] + dict[2]`, expands `%c` + 4 digits with `card_db_get_name`; results go to one of 50 rotating `0x200`-byte buffers at `0x08ac6580`. |
| `0x08833004` | `card_db_has_genre(id, n) → bool` | H | `card_db_index_of_id`, then `(Genre[6·index + 2·(n >> 4)] >> (n & 15)) & 1`. Called by the card-detail code at `0x0884e3e4`, `0x0884e7b0`, `0x0884f3a0` (loops `n = 1 … 37`) and by `0x08833638`. |
| `0x08833064` | `card_db_get_genre_name(n) → UTF-16 string` | H | `0 ≤ n < 40` → `0x08832c94(701 + n)` (DLG string), else the fallback string at `0x088a711c`. Exported (thunk `0x08833650`). |
| `0x088330a8` | `card_db_get_genres(id, u16 out[3])` | H | Copies the record's three genre words. Exported (thunk `0x08833658`). |
| `0x08833638` | `card_db_has_genre_mapped(id, k) → bool` | M | `card_db_has_genre(id, table[k])` with the 35-entry `u32` table at `0x0889f980`; imported by `rel_duel_eng`, `rel_story`, `rel_field`, `rel_shop`; `0x0886347c` passes `k = 22` (Flip Effect). |

### Field getters and the other tables

All of these were decompiled; signatures and one-line summaries are in `re/documented.tsv`. Most have no direct caller in `BOOT.BIN`: the block `0x08833594`–`0x08833680` holds one export thunk per accessor, and the game modules call them through `libehsys_rel` (`system.md`). Direct callers are listed where they exist.

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x08832a04` | `card_db_on_cardinfo_loaded(arg, result) → 1` | H | Completion callback passed by `card_db_load_cardinfo`; stores 1 in the loaded flag `0x08926b48` that `card_db_bind_cardinfo` tests. |
| `0x08832b80` | `card_db_is_valid(id) → 0xffff or 0` | M | `(Prop[index].word1 & 1) × 0xffff`. Every real record has an odd kind, so this is 0 only for record 0 (unused ids). Callers `0x0884d078`, `0x0884d1bc`, `0x08836e10`, `0x0885c660`. |
| `0x08832bac` | `card_db_get_sort_position(id)` | H | `CARD_Sort[index]`. Caller `card_db_get_top_group`. |
| `0x08832bdc` | `card_db_get_prop_bits22(id)` | H (code) | `(u16 at Prop+6 & 0x1ff) >> 6` = word 1 bits 22–24. The field is therefore 3 bits wide; its meaning is still open (`cardinfo.md`). |
| `0x08832c34` | `card_db_find_by_passcode(passcode) → id or −1` | H | Linear scan of ids `0xe88`–`0x1f39` with `card_db_get_passcode`; passcode 0 returns −1. |
| `0x08832c94` | `card_db_get_dialog_string(n)` | H | `DLG_Text + DLG_Indx[n]`, no bounds check. Callers: the four name getters below and `card_db_get_genre_name`. |
| `0x08832cb8` | `card_db_get_race_name(race)` | H | DLG `500 + race` (DLG 501 = Dragon … 522 = Divine-Beast, 523/524 = SPELL CARD/TRAP CARD in English); 0 → empty string `0x088a711c`. |
| `0x08832d58` | `card_db_get_attribute_name(attr)` | H | DLG `530 + attr` (531 LIGHT … 537 DIVINE, 538 SPELL, 539 TRAP). |
| `0x08832ce8` | `card_db_get_kind_name(kind)` | H | DLG `550 + k` (551 `/Effect` … 560 `/Token`, 561 `/Tuner`, 562 `/Synchro`, 563 `/Synchro/Effect`), with `k` = kind except 15, 16 → 11, 17 → 12, 18 → 13 and any other kind > 10 → 1. Kind 0 (normal monster) gives the empty string. |
| `0x08832d88` | `card_db_get_icon_name(icon)` | H | DLG `570 + icon` (571 Counter, 572 Field, 573 Equip, 574 Continuous, 575 Quick-Play, 576 Ritual, 577 Normal). |
| `0x08832db8` | `card_db_get_race(id)` | H | `(Prop byte 6 & 0x3f) >> 1` = word 1 bits 17–21. Called through its thunk by `card_db_is_trap`. |
| `0x08832de0` | `card_db_get_attribute(id)` | H | `(word1 & 0x3ff) >> 6` = bits 6–9. |
| `0x08832e08` | `card_db_get_level(id)` | H | `(Prop byte 5 & 0x3f) >> 2` = bits 10–13. |
| `0x08832e30` | `card_db_get_icon(id)` | H | `(word1 & 0x1ffff) >> 14` = bits 14–16. |
| `0x08832e58` | `card_db_get_kind(id)` | H | `(word1 & 0x3f) >> 1`, i.e. the stored kind halved (0 normal … 10 token, 11 Egyptian god, 13 spell, 14 trap, 15/16 tuner, 17/18 synchro). Ids `0x1386`–`0x1388` always return 11. Called through its thunk by `card_db_is_token`. |
| `0x08832e94`, `0x08832ed8` | `card_db_get_atk(id)`, `card_db_get_def(id)` | H | `10 × ` the 9-bit field; the value `0x1ff` (printed `?`) returns 0. |
| `0x08832f1c`, `0x08832f60` | `card_db_get_atk_or_unknown(id)`, `card_db_get_def_or_unknown(id)` | H | Same, but `?` returns `0xffff` / −1. |
| `0x088330fc` | `card_db_get_top_count()` | H | `CARD_Top[0]` (27). |
| `0x0883310c`, `0x08833164` | `card_db_get_top_letter(n)`, `card_db_get_top_card(n)` | H | `u16` at `Top + 4n + 2` / `+ 4n + 4`; 0 when `n > count` (the test allows `n == count`). |
| `0x088331bc` | `card_db_get_top_group(id)` | H | Last `n` with `sort(top_card(n)) ≤ sort(id)`: the letter group a card belongs to. |
| `0x08833230` | `card_db_get_artwork_count(id)` | H | Binary search of `CARD_SamePict` by record index; `n + 1` when found, 1 otherwise, 0 when the member is missing. |
| `0x0883349c` | `card_db_expand_card_refs(out, in)` | H | Replaces `$m` + four digits with the name of that card id (copied with `0x0885827c`, converted with `0x08859460`, formatted with `0x088589c8` and the format at `0x0889f978`); other `$x` pairs are copied. Called by `card_db_get_description` as its last step, so descriptions come back with `$m` already expanded. |
| `0x0886010c` | `card_db_is_token(id)` | H | `card_db_get_kind(id) == 10`. Callers `save_get_card_record`, `0x08836e10`, `0x08835dec`. |
| `0x0885ff60` | `card_db_is_trap(id)` | H | `card_db_get_race(id) == 24`. |

The limit getters exported from the same block, `0x08832fa4` and `0x08833624`, are in `deck.md`.

## Open questions

- See `docs/formats/cardinfo.md` for the open fields.
- Pack contents and the restriction list are not in `cardinfo`: they are static tables in `gmodule/rel_shop.prx` (`docs/formats/packs.md`) and `BOOT.BIN` (`docs/formats/limit-list.md`).
- Card effects: no effect data or script references are in `cardinfo`; the evidence points to per-card code in `rel_duel_eng.prx` (`docs/subsystems/duel_effects.md`).
- `card/*.cip`: card images, format unknown.
