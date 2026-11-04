# User interface

Data formats established; the scene map (which module loads which archive, layout and string table, and which string indices it asks for) is produced statically by `tools/scenes.py` (below). How a layout is played (frame stepping, which clip a menu shows when) is still open.

## Key functions

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x0881e56c` | `ui_bind_ehf(ehf, tmf, callback, ehp)` | M | Called by `container_ehp_bind_members` for every `.ehf` member, with the `.tmf` member of the same base name and callback `0x088227d0`; followed by `0x0881e6a4(480.0, 272.0, 240.0, 136.0, ehf, 0)`, the PSP screen size and its centre. |
| `0x08836ed0` | `card_db_get_dictionary_word(table, index)` | H | Despite its name (it was first found reading `DICT`), this is the game's one accessor for headed string tables (`string-tables.md` layout A): every scene module calls it with a `container_ehp_find_member(archive, "<table>.bin")` result and an index (854 call sites after following wrappers, table below). Name kept; registry unchanged. |
| `rel_title:0x08e9ce54` | `ui_title_load_archive(slot)` | H | `sprintf(buf, path_table + 64·slot)` (path table at module `+0x4b1b0`: `title_menu_j.ehp` ×3, `mini_result_j.ehp`, then `title_menu_<l>.ehp` for `j e g f i s`), `container_get_file_size(3, buf)`, heap allocation, `container_load_file(3, …)` with a callback that binds the archive; the buffer goes to `+0x364c + 4·slot` of the module work area. |
| `rel_title:0x08e9cfd0` | `ui_title_get_menu_archive()` | H | Returns the buffer of slot `[+0x3640] + 4`, i.e. `title_menu_<l>.ehp` (`+0x3640` is the language index: hypothesis, high, since the same field selects the archive and the `<table>_<l>.bin` record). Leaf; every `rel_title` lookup passes it to `container_ehp_find_member`. |
| `rel_title:0x08e9d0e0` | `ui_title_get_message_table_name(k)` | H | Record `language + k` (stride `0x84`, name at `+4`) of the table at `+0x4beb0`: 24 records, `title_msg`, `option_msg`, `tushin_msg`, `duelmenu_msg` × six languages, so `k` = 0, 6, 12, 18 selects the table. Interpreter result: `k = 0, 6, 12, 18` → `title_msg_j.bin`, `option_msg_j.bin`, `tushin_msg_j.bin`, `duelmenu_msg_j.bin`. |
| `rel_title:0x08e9cbf0` | `ui_title_get_message(index, k)` | H | `card_db_get_dictionary_word(find_member(ui_title_get_menu_archive(), ui_title_get_message_table_name(k)), index)`. |
| `rel_title:0x08e9cb74` | `ui_title_get_title_message(index)` | H | Same with `k = 0` (`title_msg_<l>.bin`). |
| `rel_title:0x08e9d0b8` | `ui_title_get_layout_name(k)` | H | `+0x4b430 + 64·k`: the 19-name array `main_title01.ehf`, `press_start.ehf`, `t_windiw.ehf`, … `trade_menu_bar01.ehf`. |
| `rel_field:0x090e05a4` | `ui_field_find_resource(id)` | H | 12-byte records `{u32 ?, char *member, void *cache}` at `+0x2f548`; returns `&record.cache` after `container_ehp_find_member(field archive, record.member)` on first use. |
| `rel_field:0x090e057c` | `ui_field_get_resource(id)` | H | `*ui_field_find_resource(id)`: the field's string tables are fetched as `card_db_get_dictionary_word(ui_field_get_resource(4/5/7), index)` (`field_strtbl`, `_item`, `_mapname`). |
| `rel_deck:0x08eaa6a8` | `ui_deck_get_resource(id)` | H | 41 records `{u32 id, void *cache, char *format}` at `0x08ebd84c` (module `+0x22e4c`) sorted by id (ids `0x8000+`), searched by `0x08eaa360`; on first use `sprintf(format, "jegfis"[save_get_language()])` (ids `0x8036`/`0x8037` use the region string `"jabgfisb"`), `container_ehp_find_member`, and for an `.ehf` also the `.tmf` (`FUN_08821b70`). The same routine, with its own table, is in `rel_deckswap +0x9c8c`, `rel_decktutorial +0x11324`, `rel_select_card +0xc334`, `rel_recipeviewer +0x5ad4` (id `0x8033` = `strTbl.bin`) and `rel_shop:0x090dc228` (`shop_get_archive_member`, 21 records). Record layout: `docs/formats/system-runtime.md`, "ui_resource_table". |
| `rel_duel_mgr:0x08ea0198` | `ui_duel_mgr_get_string_table(id)` | H | `sprintf(format_table[id], language letter)` (`strTbl_%c.bin`, …), `container_ehp_find_member(work->archive, name)`, cached at `work + 0xd0 + 4·id`. |

## Scene map

### Method (`tools/scenes.py`)

```
python3 -I tools/scenes.py check <PSP_GAME> [-v]               # coverage; -v lists every unattributed layout/table
python3 -I tools/scenes.py map <PSP_GAME> -o ../tf3scratch/scenes.json
python3 -I tools/scenes.py refs <PSP_GAME> rel_title [--filter ehf]   # asset names a module uses, with basis and functions
python3 -I tools/scenes.py calls <PSP_GAME> rel_field 'dictionary_word|find_member'   # resolved call arguments
python3 -I tools/tests/test_scenes.py
```

The map is built from the binaries alone (BOOT.BIN and the 36 `gmodule/*.prx`, unrelocated; nothing is executed natively):

1. **Symbolic pass.** Every function (starts: `jal` targets, relocated code pointers, the entry point) is walked once with symbolic values for registers and stack slots: constants (`lui`/`addiu`/`ori`, moves), the function's own arguments, call results, loads from absolute addresses. Values written between a branch and its target are dropped at the target. Each call is recorded with its four argument expressions; a stack buffer filled by `sprintf`/`strcpy` is passed on as "built from this format".
2. **Imports.** Stubs resolve by NID against BOOT.BIN's `libehsys_rel` and the other modules' libraries (`prx_imports.py`) and are named from `re/functions.csv`.
3. **Resolution.** A call result of a module function is resolved by a small integer MIPS interpreter (`scenes.emulate`): it follows local calls, executes `sprintf`/`strcpy`/`strcat`, answers `save_get_language` with 0, records the arguments of other imported calls, and explores both ways a branch on a zero read from module memory (an empty cache pointer, a "loaded" flag). This is what turns `ui_title_get_message_table_name(12)` into `tushin_msg_j.bin` and `ui_deck_get_resource(0x8033)` into `find_member(…, "strTbl.bin")`. Results that are runtime state (heap pointers) stay unresolved. Globals written with one value only are replaced by it. An accessor call whose table or index is an argument of the enclosing function is re-evaluated in each caller (up to three levels).
4. **Names to the disc.** Asset names come from resolved call arguments (basis `call`), strings the code addresses directly or through a fixed-stride name array (`code`), or asset-like strings in the module's data (`data`). They are matched against every archive, nested archive and member on the disc and in BOOT.BIN's embedded archives, with the language letter normalised (`_j`, `_eng`, `%c`, `%s`, `x` → `<l>`) and printf patterns expanded (`duel/bg/fmagic%04d.ehp`). Bare archive names are kept only when a directory string of the same module (`dodge/%s`, `field/bustup`) or a single archive family on the disc places them; stems completed with a separate `".ehp"` (`basic_ue` in `rel_duel_draw`) and language prefixes (`cardinfo_`, `DICT_`) are expanded the same way. BOOT.BIN's bare names (the bust-up table) are available to every module. A layout or table inside an archive the module names, but not itself named, gets basis `archive` (`container_ehp_bind_members` binds every `.ehf` of a loaded archive).
5. **Scenes.** Modules map to scene ids through BOOT.BIN's scene table (`modules.md`); a library module runs in the scenes of every module that loads it by a constant id or imports its library (transitively). BOOT.BIN is resident.

Certain vs inferred: `call` and `code` attributions are read from the code (high); `data` means only that the name is in the module (medium, the code path may be dead); `archive` is inferred from the binding of whole archives (high for "is loaded", says nothing about whether a screen draws it). A library's scene list is inferred from who imports it; which tool the lab hub (`rel_labo`) opens is chosen at runtime.

### Coverage (check run 2026-10-31)

| Item | On the disc | Attributed to a module | Best basis: call / code / data / archive |
| --- | --- | --- | --- |
| EHF layouts | 1,225 | 1,167 (95 %), all with a scene | 198 / 755 / 176 / 38 |
| String tables | 1,851 | 1,799 (97 %), all with a scene | 641 / 1,080 / 21 / 57 |
| Accessor requests (`card_db_get_dictionary_word`) | 854 | table named 462, constant index 517, both 332 | |

The 58 layouts and 52 tables left over sit in archives whose names no binary contains, so they are probably unused copies (hypothesis, medium): `field/always.ehp` and `field/always_lang_<lang>.ehp` (the field loads `always_<region>_<lang>.ehp`), `field/mail/chr02.ehp`, `tutorial/face/bu_*.ehp`, `tutorial/tutorial_<l>.ehp` (`NN_message_res.bin`; unused with high confidence, `tutorial.md` "The `tutorial/` directory"), `umd_replace/basic.ehp` and `umd_replace/basic/swf.ehp` (the module reads `database/umd_replace/`), `database/umd_replace/basic.ehp`, `database/gallery.ehp` (the gallery reads `database/gallery/basic*.ehp`), `minigame/{dodge,throw,blackjack}/basic.ehp` (the games read `basic_lang_<l>.ehp`), and 11 `field/bustup/bu_*.ehp.gz` whose names are not in BOOT.BIN's bust-up table (`bu_asw`, `bu_daa`, `bu_kgw`, `bu_kmz`, `bu_kni`, `bu_maw`, `bu_miw`, `bu_mtg`, `bu_sal`, …).

The 522 accessor requests without a named table read a table pointer that is runtime state the interpreter cannot follow (the title's per-call table selector, the minigames' shared `mini_result` helper fed from a caller's buffer, the duel HUD's `ddstrtbl` index/body pair); the indices of most of them are still constants.

### Scenes

Counts are layouts / string tables attributed to the module (any basis); a library shares the scenes of its loaders. "Index requests" = accessor calls with table named / total.

| Scene | Screen | Module (base) | Archives (families) | Layouts / tables | String tables read (index requests) |
| --- | --- | --- | --- | --- | --- |
| resident | loading, card text, pack and recipe names, bust-up and cut-in name tables | BOOT.BIN | embedded `@0xc84d4` (`loading.ehf`), `@0x10d5d4` (`pack_name_str_%c.bin`), `@0xd3834`, `@0xfb124`, `@0xfea04`; `duelsys/cardinfo_<lang>.ehp` (`DICT_`) | 222 / 365 | `sysmsg_<l>.bin` (1/5) |
| 0x0d | title, main menu, options, communication menus | `rel_title` (`0x08e9aa00`) | `title_menu/title_menu_<l>.ehp`, `minigame/result/mini_result_<l>.ehp`, `duel/start/start_<l>.ehp`, `database/charalist.ehp` | 156 / 125 | `title_msg_<l>.bin` (9 functions, indices such as 8, 39, 40, 54, 55, 78, 80, 81, 94), `tushin_msg_<l>.bin` (41 functions), `option_msg`/`duelmenu_msg` through `ui_title_get_message` with a runtime selector (121/175) |
| 2 | story / event runner | `rel_story` (`0x08e9aa00`) | none directly; drives `rel_field`, `rel_shop` and the library tools | — | — (its text is `EveB`/`SysMsg`, `story.md`) |
| 5 | free-roam field, island map, PDA-style overlays | `rel_field` (`0x090ced00`) | `field/always_<region>_<lang>.ehp`, `field/big_map/world_<period>.ehp`, `field/map/bg_NN_MM.ehp`, `field/bustup/*.ehp.gz` | 55 / 120 | `field_strtbl.bin` (25 functions), `field_strtbl_item.bin`, `field_strtbl_mapname.bin` through `ui_field_get_resource(4/5/7)` (66/80) |
| 4 | deck editor | `rel_deck` (`0x08e9aa00`) + `rel_recipeviewer`, `rel_decktutorial` | `deck/all_<l>.ehp`, `deck/recipe_view_<l>.ehp`, `deck/tutorial.ehp` | 25+35+25 / 15+15+21 | `strTbl.bin` via `ui_deck_get_resource(0x8033)` (31 index requests in `rel_deck`; 32/78 named); the same resource table also names `help_strtbl_contents.bin` and `ocg_packlist_<l>.bin` |
| 7 | card shop, pack opening | `rel_shop` (`0x090ced00`) | `shop/all_<l>.ehp`, `deck/all_<l>.ehp`, BOOT.BIN `@0x10d5d4` | 45 / 81 | `strTbl_<l>.bin`, `strTbl.bin` via `shop_get_archive_member` (9/22) |
| 6 | duel session: rock-paper-scissors, versus, start, results | `rel_duel_mgr` (`0x08e9aa00`) + `rel_deckswap`, `rel_tutorial` | `duel/start/start_<l>.ehp`, `duel/result/result_<l>.ehp`, `title_menu/title_menu_<l>.ehp`, `deck/deckswap.ehp` | 95 / 5 (+37 / 15) | `strTbl_<l>.bin` via `ui_duel_mgr_get_string_table(5)` (indices 2–6), `strTbl.bin` via `0x08ea4fe8(8)` (indices 220–223, 275–277, 289; 217, 218, 225, 281 where the id is not constant) (31/48) |
| 3, 6 | duel HUD, cut-ins, field backdrop | `rel_duel_draw` (`0x0983fb00`) + `rel_duel_eng` | `duel/basic_<region><lang>.ehp` (`basic_ue` … `basic_bs`, built as stem + `".ehp"`), `duel/cutin_*.ehp`, `duel/bg/fmagic%04d.ehp` | 136 / 164 | `ddstrtbl_<l>.bin`, `ddstrtbl_<lang>_idx/_body.bin`, `help_strtbl_contents_duel_<l>.bin`, `help_strtbl_label_<l>.bin` named in data; table pointers runtime state (0/29) |
| 9 | lab hub (database tools) | `rel_labo` + `rel_cardalbum`, `rel_charalist`, `rel_conv_machine`, `rel_duelrecord`, `rel_limitlist`, `rel_password`, `rel_select_card`, `rel_tutoriallist`, `rel_deckswap` | `labo/voicetest.ehp`, `database/{cardalbum,charalist,duelrecord,limitlist,tutoriallist}.ehp`, `labo/{rental,conv_machine,password}.ehp`, `field/bustup/*.ehp.gz` (character list) | see the libraries | `chr_wordstbl` captions (`%s_wordstbl_<l>.bin`, voice test); each tool's `strTbl_<l>.bin` (album 15/17, password 11/12, conversion 7/7, …) |
| 0x15 | underground duel | `rel_underground` + `rel_duel_mgr` | `minigame/underground/{titlemenu_<l>,game_<l>,game_com}.ehp`, `mini_result_<l>.ehp` | 49 / 45 | table pointers runtime state (0/39, 30 constant indices) |
| 0x0f, 0x11, 0x13, 0x18, 0x19, 0x1c | minigames: blackjack, dodgeball, connection, quiz, reversi, throw | `rel_blackjack`, `rel_dodge`, `rel_connection`, `rel_quiz`, `rel_reversi`, `rel_throw` | `minigame/<game>/basic_lang_<l>.ehp` (connection, quiz: `<l>.ehp`; reversi: `lang_<l>.ehp`) with nested `mini_result_<l>.ehp`, `title_menu_<l>.ehp` | 45–75 / 35–41 each | `strTbl.bin` of the game archive (blackjack 15/27, dodge 17/29, throw 9/20); connection, quiz, reversi through runtime pointers |
| 0x1e | gallery | `rel_gallery` | `database/gallery/basic.ehp`, `database/gallery/basic_lang_<l>.ehp` | 1 / 5 | `strTbl.bin` (8/8, index not constant) |
| 0x1b | UMD swap | `rel_umd_replace` | `database/umd_replace/basic_lang_<l>.ehp` | 10 / 5 | `strTbl.bin` (11/14) |
| 0x0b | cut-in viewer | `rel_cutin_viewer` | every `duel/` archive (viewer) | 380 / 772 | — |
| 0x0a, 0x0e, 0x17, 0x1d, 0, 1, 0x0c | movie viewer, download, USB, throw starter, debug menu | `rel_movie_viewer`, `rel_html_view`, `rel_usb_connect`, `rel_throw_starter`, `rel_debug_menu` | none on the disc named (`usb_connect` asks for 7 strings from a runtime table) | — | — |

The JSON (`map`) carries, per module, every archive and member with basis and referencing functions (runtime addresses where the base is known, `+offset` otherwise) and, per string table, the functions and constant indices that read it; `attribution` lists for every layout and table on the disc the modules and scenes that use it. It is knowledge (names, indices), not text; the strings themselves come from `strtbl.py`.

## Data

- `.ehf` (`docs/formats/ehf.md`): 2D layouts converted from Flash/SWF. Stage in twips (9600 × 5440 = 480 × 272 px), a main timeline of place/remove records with depths and mask (clip) depths, shapes made of textured quads stored as GE display lists, nested looping clips, and quantised keyframe tracks for an affine matrix and a colour transform. 1,225 on the disc, all parsed and cross-checked by `tools/ehf.py check` and exported as neutral JSON by `ehf.py json` (schema in `ehf.md`); renders of `loading.ehf`, the title screen and several menus look correct.
- `.tmf`: one flag byte per texture slot of the `.ehf`; bit 0 is probably additive blending, bit 4 unknown.
- Textures are `<name>.gim` members of the same archive (`docs/formats/gim.md`).
- `loading.ehf` is looked up in the embedded archive at `0x088cc480` (file offset `0xc84d4`) during start-up (`0x08835c68`).
- Each `.ehf` reserves a zero-filled work area of `align16(0x78 + 0x28 × peak live instances)` bytes: the runtime keeps per-instance state inside the file image (hypothesis, high).
- Resource tables: most screens do not name members inline but through a table of `{id, cache, name or format}` records filled on first use (`ui_deck_get_resource` family, `ui_field_find_resource`); the format takes the language letter from `"jegfis"` indexed by `save_get_language()` (`j e g f i s`), or the region-language pair for the duel HUD (`basic_<u|b><e|g|f|i|s>`, `jj` for Japan).

## Function families named in the 2026-10-31 round

Basis and method: `system.md`, same section. 2,665 new `ui` names; most are M (state-machine steps named from callers, callees, layouts and strings).

| Module | Families (count) | Notes |
| --- | --- | --- |
| `BOOT.BIN` (148) | `ehf_player` 34, `card_face_draw` 42, `card_viewer` 26, `window_list` 22, `list_window` 16, `message_box` 8 | The `.ehf` layout runtime (timeline stepping, track evaluation, depth-sorted instances, colour transforms, `.tmf` flags; `0x0881e6a4` is the player init with width and height, stage size as fallback); card face drawing (UTF-16 labels "ATK/" "DEF/"); selection-list window `0x08d4dd28`. |
| `rel_duel_draw` (697) | `duel_help` 77, `draw_cmd_handlers` 40, `card_list_picker` 38, `thing_sprites` 32, `lp_panel` 31, `field_cursor` 25, `duel_options` 22, `message_window` 20, `attack_pointer` 20, `duel_dialogs` 19, `card_info_panel` 18, `duel_text_wrappers` 18, `card_action_menu` 15, HUD families | The draw command table `0x098d0180` (75 entries) is indexed by the same UI event numbers that the engine posts through `duel_core_post_ui_event`; the map event → engine sender was built from the `jal` sites with a constant `a0`. HUD: the shown LP `0x098e6938` moves to the target `0x098e6940` over 60 frames; turn and phase indicators are layouts `0x20002`/`0x20003`; field cursor location code `0x098d5d40` (bit 0 side, bits 1–5 zone, bits 6+ index, as in `chain.md`); two `0x218`-byte card panels at `0x098d54a0` slide 120 px in 0.25 s; the help viewer `0x098b22dc`–`0x098b5b08` (M). |
| `rel_duel_mgr` (125) | `duel_result` 50, `duel_versus` 42, `duel_start` 30 | Results screen (`duel/result/result_%c.ehp`), versus screen (`kao.gim`/`karada.gim`, `duelmenu_msg_<l>.bin`, `TnId.bin`), rock-paper-scissors start (`start/start_<l>.ehp`; the CPU's hand equals the player's 20 % of the time). |
| `rel_title` (636) | `title_wireless` 92, `card_trade` 45, `title_comm` 43, `title_duel_setup` 43, `partner_menu` 39, `title_window` 29, `title_options` 26, `title_library` 26, `title_imports` 24, `menu_ctx` 23, `title_main_menu` 20, `minigame_menu` 17, `title_state` 17, `mini_result` 16 | State machine: state, sub-state and step at `0x08eea3dc`/`0x08eea3e0`/`0x08eea3e4`; a pending state at `0x08eea3de`/`0x08eea3e2` is applied when the fade ends (`0xfff` none, `0xffe` next). Main menu state 9, communication 0xb, ad-hoc wireless lobby 0xf (packets through BOOT `0x08850a18`/`0x088509e8`, rules bitfields `0x08eebfdc`–`0x08eebfde`), options 0x10, library modules (recipe viewer 0x1b, charalist 0xd, card album 0xc, duel record 0x14, limit list 0x18, tutorial list 0x21, deck tutorial 0x12), save check 0x29. 32 eight-byte "no-ops" are import stubs of other game libraries (`ui_call_<lib>_<nid>`). |
| `rel_field` (199) | `pda_menu` 34, `field_hud` 33, `field_message_window` 26, `field_options` 23, `dp_display` 18, `reward_display` 14 | PDA screens, date/time/partner/friendship HUD, letter-by-letter message window, DP counter (the HUD "marker B" `0x090e5b20` makes it blink). |
| `rel_deck` (254) | `help_viewer` 72, `editor_draw` 24, `icon_draw` 25, `command_menu` 22, `text_search` 17, `pane_cursor` 14 | See `deck.md`. |

Several modules contain 8–28-byte functions that Ghidra shows as empty but that every caller uses as text drawing (x, y, width, string between the font begin/end calls); they are named as text-draw wrappers (M): probably tail calls the decompiler lost. Confirmed on 2026-10-31 (round 2) from the instructions (family `font_px_wrappers`, 51 in the scene modules, H): they shift x, y and width left by 6 and jump to `font_draw_text_fit_width`, `font_draw_text_box`, `font_draw_text`, `font_split_lines` or `font_fit_scale_to_width`. Eight `rel_duel_draw` functions that the first round had called `ui_stub_noop_*_text` / `*measure*` are such tail calls too and were renamed (`ui_draw_help_header_text`, `ui_split_help_text_lines` …).

## Round 2 of the 2026-10-31 naming

Method as in the first round (`system.md`): the still-unnamed functions were re-dumped from Ghidra with the current names, read in packs with full bodies (up to 160 lines), and named H/M with a basis in `re/names*.csv` under "round 2". 274 new `ui` names. `rel_duel_draw` (about 150): the duel UI mode table `0x098d1f5c` (`0x14`-byte rows: enter, draw, update, exit) gives mode 1 field cursor, 5 card viewer, 6 cut-in, 7 flag message, 8 help, 9 options, 10 tag-duel partner switch, `0xb` movie; draw command handlers `0x39`–`0x40` (`0x3a` Fusion/Synchro, posted by `duel_core_cmd_announce_fusion_synchro_summon`; `0x3c` coin; `0x3d` dice; `0x40` with reason 4 plays the Destiny Board movie); the Attribute/Type grid dialog (12). `BOOT.BIN`: the 21 counter-badge drawers (`ui_draw_counter_badge_<n>`, icon index from the `li a3, n` of each body) and card-view helpers. Scene modules: 51 text-draw tail calls (`font_px_wrappers`, see the note above) and `stub_noop` hooks named after their callers. Not yet functions in Ghidra (left for a later boundary pass): about 26 handlers of the mode table (`0x098a20e4`…`0x098a4250`) and five cut-in set-up labels (`0x098b5ff0`, `0x098b8898`, `0x098b8ddc`, `0x098b932c`, `0x098b95e8`).

## Documented functions

The functions of this group that reached the `documented` stage in the 2026-10-31 documentation round (prototype, purpose, return value, side effects and callers, read from the decompilation) are listed in [`functions/ui.md`](functions/ui.md).

## Functions documented in the 2026-11-04 round

Method: every still-undocumented `ui` function (2,074: `BOOT.BIN` 116, `rel_field` 179, `rel_deck` 261, `rel_duel_mgr` 135, `rel_duel_draw` 748, `rel_title` 635) was re-dumped from Ghidra with the current names and read in full, one row per function, in seven batches by module and address. Small wrappers that Ghidra showed with an empty body or with hidden `t0`–`t3` arguments (the font pixel wrappers that shift x, y and width by 6 into 1/64-pixel units, the line-split wrappers, sprite, scroll-bar and cursor-frame helpers, the versus and portrait wrappers) were read from the disassembly; the same wrapper shapes recur in `rel_deck`, `rel_duel_draw` and `rel_duel_mgr` because the modules share source. Full rows: [`functions/ui.md`](functions/ui.md).

Corrections to the sections above: `ui_bind_ehf` stores each texture slot's `.tmf` byte (0 without a `.tmf`) in slot word `+0x0c` after the texture callback, so `.tmf` bit 0 is additive blending and bit 4 bilinear filtering (`ehf.md`, open questions answered); `0x0881e6a4` keeps width and height only for the camera-clip path; a layout advances once per new tick of its caller's draw block (word 0, usually the frame counter), and callers pick frame ranges with `ui_ehf_set_play_range` / `ui_ehf_seek_frame`. The title state machine has three pending levels (sub-state `0x08eea3e2`, step `0x08eea3e6`, a third at `0x08eea3ea`; `0xfff` keep, `0xffe` increment), and the title states proper are `0x14`–`0x1a` and `0x2c` (some numbers in the family table are module ids). The duel UI mode stack holds 4 entries and has a mode `0xc` besides the listed ones; push does not run the covered mode's exit and pop does not re-run the restored mode's enter. Findings by reading batch follow.

### Findings from batch 1 (BOOT.BIN layout player, card viewer, windows, rel_field HUD and PDA)

Scope of this batch (295 functions): the BOOT.BIN `.ehf` layout player (`0x0881e6a4`-`0x088227d0`), list/choice windows and the window-list renderer (`0x088338e4`-`0x08844bec`), card face / card view drawing (`0x08837514`-`0x0883ca24`), the save-utility message box (`0x08841fc4`-`0x08842548`), the full-screen card viewer (`0x0884dbb0`-`0x08850488`), and in `rel_field` the field HUD, message window, picture overlay, day banner, reward (item/card received) display, command bar, action menu, resource loader, DP display, PDA menus and the options screen. Everything below is read from the Ghidra decompilation; addresses are runtime addresses (`rel_field` at `0x090ced00`).

#### EHF layout player: runtime structures (layout player, high confidence unless marked)

**Layout header at run time.** The player addresses the file through its section table at header `+0x10`: stage = header + word `+0x10`, work area = `+0x18` (size `+0x1c`), main timeline = `+0x20`/`+0x24`, objects = `+0x28`, texture slots = `+0x30`/`+0x34`. The sixth table entry, header `+0x38` (always `(0, 0)` on disc), is reused at run time as the pointer to an external player buffer (`ui_ehf_set_player_buffer`); when it is 0 the player lives in the layout's own work area (section 1).

**Player block** (0x50 bytes, at the start of the work area or the external buffer; `ui_ehf_reset_player`, `ui_ehf_init_player`):

| Offset | Type | Field |
| --- | --- | --- |
| `+0x00` | ptr | layout file |
| `+0x04` | ptr | section table (file + 0x10) |
| `+0x08` | ptr | stage section |
| `+0x0c` | int | frame-step countdown |
| `+0x10`, `+0x12` | u16 | width, height given to `ui_ehf_init_player` (stage size in px when negative); only used by the camera-clip path |
| `+0x14`, `+0x16` | s16 | screen position (`ui_ehf_set_position`), applied as the first translation |
| `+0x18` | u8 | set to 1 after every reset |
| `+0x1a` | u16 | preserved across `ui_ehf_set_play_range` |
| `+0x1c` | int | tick of the last step (copied from draw-parameter word 0) |
| `+0x20`, `+0x22` | u16 | play range start / end frame |
| `+0x24` | u16 | saved start frame (`ui_ehf_override_start_frame`) |
| `+0x28` | 0x28 | root instance (main timeline); its local frame `+0x4a` is the current frame, `+0x4e` the frame count |

**Instance record** (0x28 bytes; slots follow the player block from `+0x50`; free when `+0x08` = 0). The work-area size formula of `ehf.md`, `0x78 + 0x28 × P`, is exactly 0x50 (player) + 0x28 (root) + 0x28 per live instance.

| Offset | Field |
| --- | --- |
| `+0x00`, `+0x04` | next / prev in a circular list sorted by depth |
| `+0x08` | object pointer (objects section + record.object × 16) |
| `+0x0c` | track pointer (animation block + table[track index]) |
| `+0x10` | child list head (clips) |
| `+0x14`, `+0x18` | timeline cursor / end (clips) |
| `+0x1c` u16 | frame at which the record placed it (track time = local frame − this) |
| `+0x1e` u16 | depth |
| `+0x20` u16 | clip (mask) depth |
| `+0x22` u16 | local frame (clips start at 0xffff so the first step gives 0) |
| `+0x24` u16 | wait counter |
| `+0x26` u16 | frame count (clips) |

**Object types.** 0 shape (animation block at object `+0x20`), 3 clip (timeline `+0x08`/`+0x0c`, animation `+0x10`), and a type 1 "shape array" (animation block at `+0x0c`; `ui_ehf_draw_shape_instance_array`) that the player supports but that no file on the disc uses (`ehf.md` census: only types 0 and 3). A clip whose header word `+0x18` is non-zero is treated as a fit-to-viewport camera (`ui_ehf_build_type3_instance_matrix`) and is not drawn; the census shows `clip.pad_18` is always 0, so this path is dead on the shipped data.

#### EHF player: timeline semantics (resolves several `ehf.md` open questions)

- **Frame step (stage `+0x08`).** `ui_ehf_draw` steps the timeline at most once per new tick (draw-parameter word 0 differs from player `+0x1c` and from the override word `0x08921900`, and the global pause `0x089218e4` is 0). The countdown is reloaded with `field_08 − 1`, or `frame_rate / (60 / field_08) − 1` when the game frame rate (`ui_ehf_get_frame_rate`, 30 on this disc) is below 60. So **stage `+0x08` = vsyncs per layout frame: the layout runs at 60 / field_08 fps, capped at the game frame rate** (value 2 → 30 fps, 1 → 30 fps on a 30 fps game, 4 → 15 fps). High.
- **Records.** Object −1 removes the instance at the record's depth; depth 0xffff makes it a pure wait. Placing always allocates a new instance whose placed frame is the current local frame, inserted by depth and **replacing** an instance at the same depth (its children are released), so a re-placed object restarts its track. High.
- **Looping.** A clip reaching its frame count rewinds its cursor, sets frame and wait to 0 and **releases all its children** (Flash semantics). The root reaching the end of the play range restarts through `ui_ehf_reset_player(player, file, 1)`, which re-steps from frame 0 up to the start frame. Seeking backwards resets and re-steps forward (`ui_ehf_seek_frame`).
- **Interpolation.** Keys are relative to the placed frame. Before/at the first key the first key is held, at/after the last key the last key is held; an exact key is found by binary search; otherwise linear interpolation between the two surrounding keys. High (this was a tool hypothesis in `ehf.md`).
- **Channels** (`ui_ehf_eval_track`, flag word `+0x24`): bit 0 translate, bit 1 scale (a, d), bit 2 skew (b, c), all `s16 × step` added to the base values; bit 3 multiply = `s8 × 256 / 127` (so 0x7f is exactly 1.0 = 256); **bits 4 or 5 → add = four unsigned bytes 0-255** (not `s8 × 2` as `tools/ehf.py` assumes); **bit 6 → a u16 morph weight** (drawn as GE morph weights `1 − w/65535`, `w/65535`; not reported in the `ehf.md` census, presumably unused). Note: the reader tests `flags & 0x30`, so a bit-5-only track (`ryusen01.ehf`) makes it read 4 add bytes per key although the stride excludes them (it then reads the next key's bytes; hypothesis, medium, on what this does on screen).
- **Base matrix** (`ui_ehf_track_base_matrix`): rows `(a, b, 0, 0)`, `(c, d, 0, 0)`, `(0, 0, 1, 0)`, `(tx, ty, 0, 1)` (row vectors), i.e. `x' = a·x + c·y + tx`, `y' = b·x + d·y + ty`, confirming the mapping `ehf.md` chose by rendering.
- **Colour transform** = 8 ints: multiply RGBA (256 = 1.0), add RGBA. Nesting (`ui_ehf_concat_color_transform(out, parent, own)`): `mul = own.mul × parent.mul / 256`, `add = own.add + own.mul × parent.add / 256`. This differs from Flash (`parent.mul × own.add + parent.add`); the port should reproduce the game's formula. Clamped to 0-255 before drawing.

#### EHF player: drawing (layout player and extractor)

- **The display-list words are interpreted, not executed.** `ui_ehf_draw_shape_instance` walks the 6-word primitive records and issues its own GE commands: word 0 low 24 bits = RGB, word 1 low byte = alpha, word 2 low 24 bits = vertex type, word 3 = texture placeholder (0 → texturing off; else low 16 bits = byte offset of the 16-byte texture slot), word 4 low 24 bits = vertex byte offset in the vertex block, word 5 = prim (`(w >> 16) & 7`) and vertex count (low 16 bits). Nothing is patched into the words at bind time (answers the `ehf.md` question about words 4-5). Line strips are drawn like any other primitive type.
- **Per shape:** model matrix = track matrix × translate(anchor `+0x04/+0x08`) × scale(vertex scale `+0x0c`) × parent; GE ambient = multiply colour; material ambient = primitive RGB/alpha; emissive and light 0/1 colours = add colour (lighting enabled, light 1 direction from `0x08921908`), so the add channel acts as a colour offset on top of `texel × prim × multiply` (hypothesis, medium, on the exact GE result; to verify in PPSSPP).
- **Root transform** (`ui_ehf_draw`): identity, then the player position (or the current GE matrix with flag 0x80000), optional translation (flag 0x10000, params `+0x14/+0x18`), scale 0.05 (twips → pixels; × params `+0x20/+0x24` with flag 0x20000), optional Z rotation (flag 0x40000, params `+0x10`), then minus stage `xmin`/`ymin`. With `ui_ehf_begin_draw` the projection is `ortho(0, 480, 272, 0)`, so layout coordinates are screen pixels with y down. The stage background colour (stage `+0x04`) is not read by any of these functions (hypothesis, medium: it is not drawn).
- **Clip masks:** an instance with a clip depth is drawn into the stencil only (pixel mask 0xffffff, stencil replace after clearing stencil to 0); following siblings with depth below the clip depth are drawn with a stencil test; the first sibling above it disables the stencil.
- **Render state** (`ui_ehf_setup_render_state`): clamp wrap, modulate, blending on: `src·α + dst·(1−α)` by default, additive `src·α + dst·1` (fixed white destination factor) with params flag 0x100 or per texture; nearest filtering unless params flag 0x400 or per texture; depth test only with params flag 0x40; stencil kept only with flag 0x800.
- **Draw-parameter block** (0x60 bytes; built by callers such as `ui_draw_card_frame_ehf` and `ui_field_hud_draw_partner_panel`): `+0x00` tick, `+0x04` texture-bind callback `(list, ctx, slot, slot_offset)` (default `field_3d_gim_emit_texture_frame0(slot +4)`), `+0x08` its context, `+0x0c` flags (4 use colour transform `+0x40`; 8 depth bitmask `+0x30`/`+0x34`; 0x40 depth test; 0x80 per-depth track override callback `+0x28` with context `+0x2c`; 0x100 additive; 0x400 linear; 0x800 keep stencil; 0x10000 translate; 0x20000 scale; 0x40000 rotate; 0x80000 use current matrix), `+0x10` rotation, `+0x14/+0x18` translation, `+0x20/+0x24` scale, `+0x40` colour transform (8 ints). Globals: `0x089218e4` (only draw depths in `[0x089218f0, 0x089218f4]` when set), `0x08921900` (override tick word), `0x08921914` (saved matrix mode).

#### EHF: texture slots and `.tmf` flags (extractor)

- At bind time the callback `ui_ehf_resolve_texture` (`0x088227d0`) appends `".gim"` (string `0x0889ee64`, hypothesis high), finds the member in the same archive and **rewrites the 16-byte name slot in place** as `{0xffffffff, GIM pointer (NULL if missing), member size, word +0x0c}`. `ui_ehf_apply_tmf_flags` then ORs the `.tmf` byte of each slot into word `+0x0c` (no length check: one byte per slot is read even when the `.tmf` is shorter).
- **`.tmf` bit 0 = additive blending, bit 4 = linear (bilinear) filtering** — both read directly from `ui_ehf_draw_shape_instance` (high). This resolves the `.tmf` bit-4 question in `ehf.md`.
- Caution for the extractor (hypothesis, low until `ui_bind_ehf` is read): `ui_ehf_resolve_texture` does not clear word `+0x0c`, which on disc holds characters 12-15 of the slot name. Unless `ui_bind_ehf` clears it first, names of 13-15 characters (most names are `<layout name truncated><4 digits>`, i.e. 15 characters) leave the ASCII code of character 12 in the low byte, and its bits 0 and 4 would act as additive/linear flags (`'0'` = 0x30 sets bit 4, `'1'` = 0x31 sets bits 0 and 4). Reading `ui_bind_ehf` (`0x0881e56c`) settles this.
- Files with no `.tmf`: callers that bind manually (`ui_field_hud_bind_partner_anim`, `ui_deck_get_resource`, duel draw) call `ui_ehf_apply_tmf_flags` only when they have one; without it the flags word keeps whatever the bind left there.

#### Card face, card view and card viewer (BOOT.BIN)

- **Card view block** `0x08acc984` (0x44 bytes, filled by `ui_card_view_open` from a 9-word parameter block): `+0x00` card parts GIM (ATK/DEF labels and digits), `+0x08` card-frame EHF (`0x08acc98c`), `+0x0c` card frame GIM (one image per frame type), `+0x10`, `+0x14` blank card GIM (`cil_0000e.gim`, icon archive), `+0x18` counter icon GIM, `+0x1c` card image reader (CIP), `+0x20` EHF flag, `+0x24` text-scroll arrow timers (`0x08acc9a8`, 4 words). The field fills the parameter block from field resources 9, 10, 0xe, 0xf, 0x10 and the card work reader (`ui_field_load_card_display`).
- **Card-frame EHF**: one layout with 60-frame segments per frame type, selected with `ui_ehf_set_play_range` (type 0: 0-0x3b; 1, 6-9, 0xb, 0xf, 0x10: 0x3c-0x77; 4-5: 0x78-0xb3; 2-3: 0xb4-0xef; 0xd: 0xf0-0x12b; 0xe: 0x12c-0x167; 10: 0x168-0x1a3; 0x11-0x12: 0x294-0x2cf; others: 0x1a4-0x1a5).
- **Card frame GIM image index** per frame type (`ui_draw_card_frame`): 0→0, 1→1, 2→2, 3→3, 4→8, 5→9, 6→7, 7→4, 8→5, 9→6, 10→10 (kind 10 forces 6). Card sprites use 10-byte through-mode vertices (`u16 u, v, s16 x, y, z`, vertex type 0x800102) copied from templates in BOOT.BIN data and translated (`ui_alloc_translated_vertices`).
- **Card view state** (0x208 bytes): `[0]` requested card, `[1]` artwork, `[2]` off-screen VRAM offset (default `0x1e8000`), `[3..0x1f]` 0x74-byte info block (`+0` kind, `+4` frame, `+8` ATK, `+0xc` DEF, `+0x10` race, `+0x14` attribute, `+0x18` level, `+0x1c` icon/property, then counter values), `[0x20..]` modified-values block, `[0x3e]/[0x3f]` modifier flags, `[0x40]` text scroll (1/64 px), `[0x41]` text overflow, `[0x42..0x45]` shown card, artwork, flip step, art-ready flag. Stored form (0x20 bytes): `+0` card, `+4` VRAM offset, `+8` scroll, `+0xc` overflow, `+0x10` shown card, `+0x14` artwork, `+0x18` flip step, `+0x1c` ready.
- **Flip animation:** 10 steps; at step 5 the shown card switches to the requested one (once its art is loaded); the card is rendered off screen to a 128 × 196 8888 target and drawn as a 108 × 154 sprite (78 × 78 for art only) scaled horizontally to `|step − 5| × w / 5` with matching alpha.
- **Modifier flags** (`view[0x3e]`): bit 0 kind, 4 ATK, 8 DEF, 0x10 race, 0x20 attribute, 0x40 level, 0x80 property use the modified block; 0x4000 race badge, 0x8000 attribute badge, 0x10000 attribute set (bits 1-7), 0x20000 scrolling secondary card name, 0x800000 combined name format; the counter badges 0-21 map to flags 0x100-0x80000000 and `view[0x3f]` bits 0-1 (table in the badge rows). ATK/DEF colours: white = unchanged, `0xff8888ff` (red) = lower, `0xffff8888` (blue) = higher (colours are ABGR).
- **Full-screen card viewer** state around `0x08db3de8`: card id u16 `0x08db3de8`, option byte `0x08db3dea` (bit 0 pack tab, bit 1 artwork switching), parts GIM `0x08db3dec`, background GIM `0x08db3df0` (128 × 128 stretched to 480 × 272), pack list GIM `0x08db3df4`, pack archive `0x08db3df8` (`pack_name_str_<l>.bin`), pack list (`ui_card_viewer_find_packs`: count u16 `0x08db3e02`, name pointers `0x08db3e08`, pack numbers `0x08db3ef8`, from the 48 pack records at `0x088a6648`), state u16 `0x08db3f6a` (0 off, 1 fade in, 2 active, 3 fade out, 4 done), tab `0x08db3f6c`, artwork count `0x08db3f6e`, scroll `0x08db3f70` / max `0x08db3f74` (1/64 px, 192 px visible), GE layer `0x08db3f78`, card view state `0x08db3f7c`. Genres 1-0x25 (+0x26 for marked multi-artwork cards) are drawn as 16 × 16 icons.

#### Windows and list windows (BOOT.BIN)

- **Window list** = 16 entry pointers (+ default skin GIM at list `+0x44`, scratch at `+0x48`). Entry: `+0x00/+0x04` frame vertex pointer/count, `+0x08` descriptor pointer, `+0x0c` 0x78-byte snapshot of the descriptor, `+0x84` state (0 new, 1 opening, 2 open, 3 closing, 4 closed), `+0x88..+0x9c` saved values during transitions, `+0xa0` transition step (0-4), `+0xa4` overlay flag, `+0xa8/+0xac` overlay vertices/count, `+0xb0..+0xbc` overlay x, y, scale x (1.0), scale y (0.75), colour. Windows are drawn sorted by descriptor priority `+0x10`.
- **Window descriptor** (0x78 bytes; partly known): `+0x00` enabled, `+0x04` skin GIM, `+0x08` skin style (0-3: piece table `0x088790d0`, 4-7: `0x08879148`), `+0x09` colour/UV variant, `+0x0a` speech-tail mode 1-4, `+0x0c/+0x0e` x, y, `+0x10` depth, `+0x14` auto-size, `+0x18/+0x1a` max size, `+0x1c/+0x1e` min size, `+0x20/+0x22` size, `+0x24` frame colour, `+0x28` tail x, `+0x2c` title enable, `+0x34/+0x36` title size, `+0x38` text, `+0x3c` shadow, `+0x40` ruby, `+0x44..+0x4a` margins, `+0x4c` font scale, `+0x50` text colour, `+0x54` title text, `+0x58` title scale, `+0x5c` title colour, `+0x60/+0x64` open/close animation (0 none, 1, 2 = with drop), `+0x68/+0x6c` scale floats, `+0x70` anchor (0 top-left, 1 top-right, 2 bottom-left, 3 bottom-right, 4 top-centre, 5 middle-left, 6 centre).
- **Window frame vertices**: 16 bytes per vertex, 2 per sprite, vertex type `0x80011e` (through mode, `u16 u, v`, ABGR colour, `s16 x, y, z`); skin pieces `{u, v, w, h}`; interior filled in 8-px strips.
- **List window record** (0x120 bytes; descriptor at `+0x4c`): the descriptor fields appear at record offset + 0x4c (`+0x58/+0x5a` x/y, `+0x60` auto-size, cleared after the first measure, `+0x6c/+0x6e` size, `+0x84` text, `+0x8c` ruby, `+0x90..+0x96` margins, `+0xac` open animation: 0 = no opening transition), `+0xc4` allocator, `+0xc8` behaviour bits (1 cursor shown, 2 cancel disabled, 3 stay open after choice, 5 cancel jumps to cancel item, 6 confirm disabled, 7 no wrap), `+0xc9` list mode (bits 3-6: 0 none, odd = horizontal, even = vertical; bit 1 centring), `+0xca` low nibble button style 1-4 (buttons {1}, {1,4}, {2,3}, {2,3,4}; mask table `0x088a02f0`), `+0xcc` item count, `+0xce` visible rows, `+0xd0` scroll offset, `+0xd2` cursor row (5 bits), `+0xd3` selected button, `+0xd4` cancel item/button, `+0xd8` item-frame mask, `+0xdc` disabled mask, `+0xe0` arrow offset, `+0xe4` button icon GIM (`buttom_icon1.gim`), `+0xe8` result bits (0 cancelled, 1 decided), `+0xe9` state (1-6), `+0xec` counter, `+0xf0/+0xf2` item size, `+0xf4/+0xf6` item offset, `+0xf8/+0xfa` frame size, callbacks `+0xfc` item draw, `+0x100` full draw, `+0x104` background, `+0x108` after, `+0x10c` cursor, `+0x110` cursor overlay, `+0x114` item frame, `+0x118` item overlay, `+0x11c` pad override. `ui_update_list_window` returns −1 busy, −2 cancelled, −3 bad state, else item or button. Sounds: 0x7a04 move, 0x7a05 decide, 0x7a06 cancel, 0x7a07 buzzer, 0x7a0c open. Button labels: UTF-16 table `0x088a0278` (5 per language).
- **System message box** (save utility): open flag `0x08d4dc5c`, window list `0x08d4dc64`, plain descriptor `0x08d4dcb0`, choice record `0x08d4dd28`; 400 × 100 centred on (240, 136).

#### Fonts and text (port)

- All font routines work in **1/64 pixel** units; the small text wrappers (`*_draw_text_*`, `ui_pda_draw_entry_text`, `ui_field_draw_command_label`, …) only shift pixel arguments left by 6 and tail-jump to the font routine (the `font_px_wrappers` pattern of `ui.md`). Several of them compute width `480 − x` ("to the screen edge").
- Strings are UTF-16; digits are often drawn one character at a time.
- Per-language settings seen: Japanese (language 0) enables ruby and font flag 1 (line breaking) and disables space trimming; other languages enable space trimming at wraps and flag 0x4000 for names and type lines; German (language 2) uses a narrower 11 × 12 scale for card text. Language index 0-5 = `j e g f i s`.
- Common scales: 12 × 12 card text, 14 × 14 viewer/menus, 13 PDA, 15 HUD/action menu, 22 day banner. Colours are ABGR (`0xff00ffff` yellow, `0xff00ff00` green, `0xff492b02` PDA dark blue, `0xffedeed4` PDA light).
- The field message window uses inline colour codes (`system_font_enable_color_codes`), end-y offset 0xc0, three lines, a per-setting reveal speed table at `0x090f88fc` (pixels per frame) and reveals text by scissoring each line.

#### rel_field UI

- **Resources:** `ui_field_find_resource(id)` = 12-byte records at `0x090fe248` over the field archive `0x090fdb50`. Ids seen: 0 HUD GIM, 2 item icons, 4 `field_strtbl`, 5 `field_strtbl_item`, 8 card model, 9/10/0xe/0xf/0x10 card view GIMs/layouts, 0xb/0xc/0xd card viewer resources, 0x11 HUD GIM 2, 0x1b/0x1c partner animation `.ehf`/`.tmf`. Fixed resources 7/8 are the face/body sheets of generic characters.
- **Loader queue** (`0x0910cc8c` head, `0x0910cc90` tail, `0x0910cc94` busy): 0x1c-byte requests, files read from container root 3 with `world_field_on_archive_read`; localized loads insert the 2-byte language string from `0x090fe4a4` into the path.
- **HUD block** `0x09106930` (0x260 bytes): window list `0x09106954`, panels that slide in with an accelerating step `t += k + k·t` (k at `0x090f400c`): location window (`0x091069a0`), date panel (`0x09106a28`, weekday cells 64 × 16), target info (`0x09106a38`, window descriptor `0x09106a48`, values `0x0910693c`-`0x09106950`), time icon (`0x09106ac0`, 32 × 32 cells, time-of-day column), partner panel (`0x09106ad4`, partner row `0x09106b08`, expression `0x09106b0c`, reaction timer `0x09106b10`, animation layout `0x09106b1c` with draw-parameter block `0x09106b20`, frame range `0x09106b80/84`), points meter (`0x09106ae4`, 8 icons of 11 points-px, full at 8000 points). Marker blink `0x09106af4`-`0x09106b04` selects which element blinks (0 window list, 1 weekday, 2 time icon, 3 partner panel, 4 points meter).
- **Message window** block `0x09899c68` (0x180 bytes): state (0 hidden, 1 in, 2 shown, 3 out), slides from y 300 to y 210, window 400 × 0x3c (x from the caller), 3 lines of 0x18-byte records `{x, y, revealed px, height, start char, char count}` at `0x09899d5c`, text `0x09899d4c`, speaker name as the window title, continue cursor GIM `0x09899dc4`. Confirm advances pages (sound 0x7a0b); confirm + R fast-forwards when progress flag e9 bit 4 is set.
- **Picture overlay** (extractor-relevant): a full-screen picture is a 512 × 256 texture holding a 480 × 272 image: rows 0-255 in columns 0-479, rows 256-271 stored as two 16 × 256 columns at u = 480 and u = 496, drawn rotated (sprite flip mode 3) to (0, 256) and (256, 256). Keys −3/−2 are a coloured / black fill instead of a picture; fades last 15 frames.
- **Reward display** block `0x09106790`: kind `0x0910689c` (1 event item, 2 card), card display state `0x09106898` (0 wait art, 1 15-frame spin-in, 2 message, 3 fade to viewer, 4 card viewer, 5 fade back); the card model's two materials are rendered on the fly into VRAM `0x160000` (128 × 256 8888) by `ui_field_render_card_get_texture` (stage 0 back = blank card, stage 1 face).
- **DP display** block `0x09899c0c`: states 1 slide in, 2 idle, 3 change value shown 10 frames, 4 change value flies to the counter (scale 1 → 0.25), 5 counting (step = delta / 10, sound 0x7a10 every 3 frames, rolling random low digits); sprite digits (small strip, or large 0x28 × 0x30 digits).
- **Command bar / action menu:** page 0 buttons cross/triangle/square/circle → commands 0-3, page 1 circle/triangle/square/cross → 4-7; label positions per language in `0x090f84c4`/`0x090f8524`. Action menu: 4 entries mapped to commands (0x13 with argument 10/9/2/3/1, or 0xb), talk label chosen by `world_get_lab_special_cell` under the player.
- **PDA** block (pointer `0x09899de8`, 0x2a0 bytes from the caller's heap): `+0` state, `+4/+6` x/y, `+8` home x, `+0x0a` main cursor (low nibble), `+0x0c` submenu cursor, `+0x10` idle counter, `+0xa8` heap, `+0xac` archive, `+0xb0` `pda_pack01.gim`, `+0xb4/+0xb5` selection blink, `+0xb6` slide counter, `+0xb8` reveal step, `+0x166` prompt kind (4/5, 0xff none), `+0x168` prompt list window, `+0x288-+0x290` partner record, `+0x294` open mode, `+0x298` restricted, `+0x29c` submenu entry 1 enabled. States: 1 slide in, 2 reveal main, 3 main menu, 4 status, 8/9 three-entry submenu, 10/0xb five-entry submenu, 0xc/0xd options, 0xe return 0xc, 0xf slide out, 0x10 close. `ui_pda_step` return codes: 0 running, 1 closed, 3-5 three-entry choice, 6-10 five-entry choice, 0xb/0xd prompt confirmed, 0xc. Cover model `gx_pda_cover01.tms` + `.tmt` (magic `TGMT` → separate animation), drawn in an orthographic 3D view; PDA strings `event_name.bin`, `option_msg_<l>.bin`.
- **Options** block `0x09899e14` (0x3c bytes): 8-byte settings record (byte 0: bit 0 setting b0 bit 3, bits 1-2 message speed, bits 3-4 setting b1 bits 3-4, bits 5/6/7 option flags 0/5/2; byte 1: bits 0-1 setting b2 bits 1-2, bit 2 flag 4, bit 3 flag 3; u16 volumes 2, 0, 1 at +2/+4/+6, 0-15), working and original copies, skin GIM by mode (`menu_opt01.gim`, …). Item 2 (volume setting 2) is never reachable with the cursor (the up/down code always skips it) and its row is only drawn for Japanese (hypothesis, medium).

#### Coordinate conventions (port)

- 2D UI is drawn in GE through mode (screen pixels, 480 × 272, y down) or, for `.ehf`, through `ortho(0, 480, 272, 0, −1000, 1000)`; `.ehf` geometry is in twips (× 0.05) relative to the stage `xmin`/`ymin`.
- Sprites use `system_ge_set_sprite_extent(src_w, src_h, dst_w, dst_h)` then a draw with texel origin (u, v); flip mode 1 rotates by 90° (`ui_draw_sprite_entry_rotated`), 3 is used for the rotated picture strips.
- The PDA 3D view uses offset (0x710, 0x778), viewport centre (0x800, 0x800), 480 × 272.

#### Name mismatches

- `ui_card_viewer_get_frame_tick` returns word +4 of the frame timing record, which `ui_ehf_get_frame_rate` documents as the frame rate, not a tick; it is used as the blink period.
- `ui_pda_draw_char_at` draws a whole string (from x to the screen edge), not a single character.
- `ui_ehf_build_type3_instance_matrix` builds a fit-to-viewport camera from a special clip (type 3 with header `+0x18` set), not a generic per-instance matrix.
- `ui_options_draw_string` has no direct caller in the header list; `ui_options_draw_colored_string` reaches it.

#### Corrections to existing docs

- `ehf.md` stage `+0x08`: frame step in vsyncs (60 / value fps, capped by the game frame rate) — resolved, high.
- `ehf.md` add channel: four unsigned bytes added as a colour offset (not `s8 × 2`); multiply is `s8 × 256 / 127`; track flag bit 6 is a morph weight channel; bits 4 and 5 both trigger reading add bytes.
- `ehf.md` interpolation (linear, hold outside keys) and re-placing at an occupied depth (new instance, track restarts) — confirmed from code.
- `ehf.md` "words 4-5 presumably patched": not patched; the player interprets the primitive records itself. Header `+0x38` is a run-time player-buffer pointer.
- `ehf.md` `.tmf`: bit 0 additive (confirmed), bit 4 linear filtering (new).
- `ui.md` open question on `0x0881e6a4`: it stores width/height for the camera-clip path only; the centre floats (240, 136) are not used.
- `ui.md` "who plays a layout": every caller passes a draw-parameter block whose word 0 is a tick (usually the frame counter); the layout advances once per new tick, and callers select frame ranges with `ui_ehf_set_play_range` / `ui_ehf_seek_frame` (e.g. the card frame segments, the partner reaction ranges 0-0x4f and 0x5a-0xa9).

#### Open questions (batch 1 (BOOT.BIN layout player, card viewer, windows, rel_field HUD and PDA))
- Does `ui_bind_ehf` (`0x0881e56c`) clear the texture slot word `+0x0c` before `ui_ehf_resolve_texture`/`ui_ehf_apply_tmf_flags`? If not, characters 12-14 of long texture names act as additive/linear flags (see above). Blocks exact `.tmf` emulation in the port.
- Exact GE result of the add-colour trick (emissive + two lights, lighting mode 1) and whether it equals `texel × prim × multiply + add`; verify in PPSSPP on a layout with add keys.
- Units of the draw-parameter rotation `+0x10` (`system_matrix4_post_rotate_z_s16`) and the order semantics of the `system_matrix4_post_*` helpers.
- Behaviour of the bit-5-only tracks of `ryusen01.ehf` (add bytes read beyond the stride).
- Remaining window descriptor fields (`+0x30`, `+0x48` usage) and the skin piece tables at `0x088790d0`/`0x08879148`.
- The state table `0x090fe6f0` (main PDA entries → state) and the meaning of the three PDA submenu/five-entry command codes for `world_field_command_step`.
- What the HUD target-info values `0x09106940`-`0x0910694c` represent (three 0-999 counters with icons and a sprite-digit value).
- Whether options item 2 (volume setting 2) is intentionally hidden in every language.

### Findings from batch 2 (rel_deck deck editor and help viewer)

Deck editor UI in `rel_deck` (module base `0x08e9aa00`; all ids carry the `rel_deck:` prefix). Everything below is read from the decompilation of the 261 functions in this unit (249 documented, 12 skipped).

#### Extractor-relevant facts

- Archive: `deck/all_%c.ehp` (format string at `0x08ebda38`), language letter from `"jegfis"[save_get_language()]`, loaded from root 3 with `container_get_file_size` + asynchronous `container_load_file`; completion callback `ui_deck_on_archive_loaded` binds the members (`container_ehp_bind_with_callback(NULL, buffer)`).
- Resource table: 41 (`0x29`) 12-byte records `{u16 id, void *cache, char *format}` at `0x08ebd84c`, sorted at scene entry with `system_qsort` (comparator `0x08eaa350`) and searched by binary search (`ui_deck_find_resource`). For ids `0x8036`/`0x8037` the format receives the character at index 2 of the 8-byte string at `0x08ebda48` (a constant index in the decompilation; ui.md calls this the region string). For id `0x8024` the matching `.tmf` member is also found (substring at `0x08ebda50` replaced by the 5 bytes at `0x08ebda58`) and applied with `ui_ehf_apply_tmf_flags`.
- Resource ids used by the drawing code (role from use, medium): `0x8001` thumbnail atlas, `0x8002` alternative-artwork thumbnails, `0x8032` artwork table (u32 `{count, entries id | artwork << 16}`), `0x8006` general UI sprite sheet (check mark, frame box, plates, search box, progress bar, recipe mark), `0x8007` attribute/race/property icons, `0x8009` sprite digits and level glyphs, `0x800a` badges, toggle and key icons, frame-category colour texels, `0x800b` 7-column 17-px icon sheet, `0x800c` 16-px icon sheet (8 per row), `0x8010`/`0x8011`/`0x8024` card detail view parts, `0x8012` and `0x8015` card viewer, `0x8013` panel frame and controller guide, `0x8014` help gim, `0x8021`/`0x8025` background `.ehf`, `0x8022`/`0x8023` list-tab `.ehf` (own deck / other owner's deck), `0x8033` `strTbl.bin`, `0x8034`/`0x8035` help page strings and help labels (passed to `ui_help_open`; probably `help_strtbl_contents.bin` and a label table, hypothesis medium).
- Thumbnail atlas: 22 x 30 px cells, 23 per row, 17 rows, 391 (`0x187`) cells per texture level; the image index from `fileTbl.dat` (entry `+2`) gives level = index / 391 and the cell = index % 391 (`ui_get_card_thumbnail_cell`). A marked card with an alternative artwork selected in the save uses the slot of `id | artwork << 16` in the artwork table instead, on level 0 of the alternative texture. The atlas therefore needs at least 506 x 510 px per level (512 x 512 textures, hypothesis high).
- Card art for the detail panel: `ui_deck_poll_archive_load` opens the card-art reader with `card_db_open_cardh_cip(buffer, 0xbc1000, 0)` on a 0xbc1000-byte heap buffer (`*0x08ebf19c`), reader pointer `0x08ebf18c`, and waits for `card_db_cip_is_ready`.
- Help pictures: one file per help page, path from the format at `0x08ebe384` and the directory string at `0x08ebe38c` (the name argument is hidden in the decompilation; it comes from the per-group picture table `0x08ebe22c`/`0x08ebdecc`, one pointer per page, NULL = no picture), loaded from root 3; the picture size comes from the GIM image block (`field_3d_gim_get_surface(gim, 4)` +8 width, +0xa height). The help frame texture is `window01.gim` from the icon archive (`container_get_icon_archive`).
- On-screen keyboard text: the game's strings use `$` as an escape; the keyboard gets `$$` collapsed to `$` (at most 24 units) and doubles every `$` in the result. Deck names are limited to 16 characters.

#### Editor state globals

| Address | Meaning |
| --- | --- |
| `0x08ebf1a0` (u16) | bits 0-3 layout 0-7; bits 4-5 active pane; bit 6 keyboard active; bits 7-14 open message kind; bit 15 alternative background (`0x8025`) |
| `0x08ebf1dc` | sub-screen flags: bit 0 card viewer, bit 1 recipe viewer, bit 2 deck tutorial, bit 3 help, bit 4 skip editor drawing, bit 5 keyboard backdrop captured |
| `0x08ebee00` | editor mode: 0 browse, 1 card move, 2 command menu, 3 sort, 4 filter, 5 text search, 6 hold-L guide, 7 hold-R guide (6/7: hypothesis medium) |
| `0x08ebee02` | step of the running sub-screen (card viewer, help) |
| `0x08ebee06` | bits 0-3 tutorial hint number; bit 4 request card detail view; bits 5-6 deck-options request (with `0x08ebee08` = 2/1/0); bit 7 hints dismissed |
| `0x08ebee07` | help topic request (0 none, -1 whole help) |
| `0x08ebee0a` | text search scope: 1 = clear the filter and search the whole list |
| `0x08ebee0e` | number of card ids the player owns (header counter) |
| `0x08ebee10` | seven u16 deck counts per frame category |
| `0x08ebf0e0` | undo count (0 disables Undo) |
| `0x08ebf132`..`0x08ebf138` | cursor rectangle x, y, w, h |
| `0x08ebf1a4`/`0x08ebf1a8`/`0x08ebf1b4` | description overflow width, marquee offset (1/64 px), marquee delay |
| `0x08ebf1b0`/`0x08ebf1b2`/`0x08ebf1b8` | cursor card id, image index, entry pointer |
| `0x08ebf1bc` | text scroller record for the big detail view (+0 card id, +8 offset, +0xc max) |
| `0x08ebf238` | description buffer, newlines replaced by spaces (0x314 units) |
| `0x08ebedc0` | deck name (UTF-16) |
| `0x08ebeee0` | search history, 8 x 0x40 bytes |

#### Pane records

Two 0x2c-byte records at `0x08ebf1e0` (pane 0) and `0x08ebf20c` (pane 1): `+0` list pointer, `+4` bit 0 list layout (else grid), `+6` first visible index, `+8` column, `+0xa` row, then a 0x1e-byte geometry block copied from `0x08ebd35c + 0x1e * n`: `+0xc` x, `+0xe` y, `+0x10` width, `+0x12` height, `+0x14`/`+0x16` list cell offset, `+0x18` visible rows (list), `+0x1a` row width, `+0x1c` row height, `+0x1e`/`+0x20` grid offset, `+0x22` columns, `+0x24` column pitch, `+0x26` visible rows (grid), `+0x28` row pitch.

Editor list records (0x20 bytes at `0x08ebed00`): besides the fields in deck.md, `+0xc` total copies (shown on the tabs and checked against 60/15/15 by the deck-options menu), `+0x16` bits 0-3 sort mode, 4-5 order, 6-9 filter number (8 = set by an empty text search), `+0x18` saved first index, `+0x1a` saved cursor index, `+0x1c` saved column/row nibbles, `+0x1d` low nibble saved column count.

#### Layouts

Eight layouts in two rows of four (the layout chooser): `ui_select_layout_index` gives 0 (one pane, list), 1 (one pane, grid), 2/3 (two narrow panes, grid+grid / grid+list), 4-7 (two wide panes: 4 list+list, 5 grid+grid, 6 list+grid, 7 grid+list). The layout record table is at `0x08ebd3f4` (8 bytes: pane-0 flag, pane-0 geometry, pane-1 flag, pane-1 geometry, -1 = unchanged). List-box/tab extents per list come from three 10-byte tables chosen by layout class: `0x08ebd440` (0-1), `0x08ebd47c` (2-3), `0x08ebd4b8` (4-7). Pane 0 shows lists 0-2 and pane 1 lists 3-5 in two-pane layouts; in single-pane layouts pane 0 cycles through all lists (skipping 4; another owner's deck also skips 2 and 5).

#### Input map (browse mode, from the handlers)

Hold L: Square/Circle page back/forward, Triangle/Cross jump to the previous/next sort group, Select clears the filter. D-pad moves the cursor and crosses between panes (rows rescaled). Start in a menu or message opens the help on a topic: command menu 8, list tools 0x11, deck options 0x18, layout 0xe, trunk option 0x16, card-limit message 2, rule messages from the table `0x08ebd268`.

#### Menus

- Command menu record `*0x09e0087c` (0x18 bytes): items 0 card details, 1 card save-byte-1 flag, 2 key card, 3 list tools, 4 deck options, 5 layout, 6 clear filter, 7 undo; without a card only items 3-7. Disabled mask at window `+0xdc`. Sub-states 0-5 and 10 (`ui_update_card_command_menu`).
- List tools: 0 sort, 1 filter, 2 text search, 3 trunk display option (save setting byte `0xb0` bits 6-7, three values, confirmed by a 3-choice box; changing it rebuilds the trunk view).
- Deck options: 6 items; items 0-2 post a request through `0x08ebee06` bits 5-6 and `0x08ebee08` (2, 1, 0), 3 reloads the lists, 4 returns all cards to the trunk, 5 renames the deck (keyboard). For another owner's deck items 1, 2, 4, 5 are disabled; item 1 also when the deck is over 60/15/15.
- Sort menu (`*0x09e00884`): key window of 10 sort modes (mode = item + 1) and a 2-item direction window; the list re-sorts live and cancel restores the saved view.
- Filter menu (`*0x08ebecdc`): 7 filters; per-filter value range and item drawer in the 8-byte table `0x08ebd2ac` (`u16 first, u16 last, draw callback`); labels: 1 and 4-6 from `strTbl.bin` index tables (`0x08ebd2fc`, `0x08ebd30c`, `0x08ebd314`), 2 race names, 3 attribute names, 7 genre names (the last genre value is only offered when some card is marked). Values are toggled in a 64-bit mask passed to `deck_filter_list_view`.
- Text search (`*0x09e00888`, 0x60 bytes): query from the keyboard or the history, progress window driven by `deck_step_text_search` (per mille), result count shown as message 6.
- Sort modes (from `ui_draw_sort_group_header`): 1 name initial, 2 frame/type, 3 level, 4 ATK, 5 DEF, 6 race, 7 attribute, 8 Spell/Trap property, 9 a key drawn with icon set C, 10 a 2-digit number. Modes 4-5 group by hundreds.

#### Message window

Record `0x08ebe3b8` (0x120 bytes) + text `0x08ebe4d8` (0x800 bytes); kinds: 2 deck-rule error (string table `0x08ebd248`), 3 key-card question (2 choices), 4 notice (`0x08ebd25c`), 5 card-limit notice, 6 filter/search result count, 7 tutorial hint (3 choices). Tutorial hints use save progress bytes 0-4 and are shown only when save setting byte `0xb0` bit 3 is set.

#### Help viewer (shared code in rel_deck)

- Records: main `0x09e00b2c` (300 bytes), page view `0x09e00a40` (0xec), footer `0x09e00c58` (0xd0), topic list `0x09e00d28` (0x120, widget at `0x09e00d40`), chapter (page) list `0x09e00e48` (0x118, widget at `0x09e00e60`). Layouts in the function rows.
- Parameter groups: chapters 0xd-0x18 (deck editor) use chapter table `0x08ebcec0`, picture table `0x08ebe22c`, page string base 0x54; other chapters `0x08ebce8c`, `0x08ebdecc`, base 0x5c. Chapter tables hold `{u16 first, u16 last}` string ranges.
- Topics 0-0x51 map to chapter and page through `ui_help_get_topic_chapter` / `ui_help_get_topic_page`.
- Generic list widget (0x34 bytes): `+0` count, `+2` cursor, `+4` flags (bit 0 active, 1 no confirm, 2 no cancel, 3 no Up/Down), `+8` result (1 confirm, 2 cancel), `+0xc`..`+0x12` x, y, w, h, `+0x14`/`+0x16` top/bottom padding, `+0x18`/`+0x1a` left/right padding, callbacks `+0x1c` background, `+0x20` item, `+0x24` pre-item, `+0x28` cursor, `+0x2c` measure(index, width) → height, `+0x30` scroll, `+0x32` content height.
- Topic list states: 0 idle, 1 open, 2 opening, 3 active, 4 confirm flash (8 frames), 5 close, 6 closing, 7 done.

#### Keyboard and backdrop

`ui_start_osk_input` fills a `sceUtilityOsk` parameter block at `0x09e00890` inside a 0x1b4-byte record at `0x09e0088c` (state byte: 0 idle, 1 fading out, 2 running, 3 fading in, 4 done); soft reset is inhibited meanwhile and `system_net_set_word_bafc` is set to 0 and back to 1. Before the dialog the displayed frame (480 x 272, 8888, stride 512) is copied to VRAM + 0x174000 and redrawn as the backdrop.

#### Name mismatches

- `ui_draw_menu_highlight_bar` (`0x08ea7b6c`): draws a two-line separator rule (colours `0xff479fc1`/`0xffa9d7e9`) after command items 2 and 5, not a highlight bar.
- `ui_get_frame_counter` (`0x08eafa58`): returns word +4 of the frame-timing record, which its caller uses as a blink period, not the frame counter (word +0) (confidence medium).
- `ui_draw_table_icon_a/b/c`: icon tables for filter, sort mode and sort order respectively (from `ui_draw_pane_status`).

#### Corrections and additions to existing docs

- deck.md: list record `+0x16` packs sort mode, order and filter (bits 0-3, 4-5, 6-9); `+0xc` is the list's total copy count.
- ui.md: the region-string index for resources `0x8036`/`0x8037` appears as a constant (index 2) in the decompilation of `ui_deck_get_resource`; worth checking in the disassembly.

#### Open questions (batch 2 (rel_deck deck editor and help viewer))
- Which sub-screens the deck-options requests (`0x08ebee08` = 2, 1, 0) start, and which save flag `save_*_card_byte1_flag` is (shown as a 2-state icon on rows; "favourite" is a guess).
- What sort mode 9 and 10 group by (icon set C and a 2-digit number).
- The meaning of the three trunk display options (save byte `0xb0` bits 6-7).
- What `0x08ebf1a0` bit 15 (alternative background `0x8025`) signals.
- The 12-byte `*_split_text_lines` wrappers and the 8-byte `ui_help_disable_ruby` need the disassembly; the help scroll-bar part wrappers and cursor blink/flash wrappers hide their register arguments.
- The name argument of the help picture path (`0x08ebe384` format) and the picture-load callback `0x08eb5fe8` (not a function in Ghidra).
- `ui_draw_sprite_number` styles 1 and 2 take their digit width from a register the decompilation does not show.

### Findings from batch 3 (rel_duel_mgr start, versus and result screens)

Scope: `rel_duel_mgr` (base `0x08e9aa00`), the three 2D screens of the duel session: the rock-paper-scissors duel start screen ("janken"), the versus screen and the duel result screen. 135 functions read, 124 documented, 11 skipped (tiny tail-call wrappers whose bodies the decompiler shows as empty, and two argument-inserting wrappers).

#### Decompiler caveat: per-function typing of the work-area globals

The three work-area pointers (`0x08ebaa90`, `0x08ebaa94`, `0x08ebaa98`) are untyped `_DAT_` globals, so Ghidra infers a type for each function separately. In some functions the pointer is treated as `ushort *` (`_DAT_08ebaa90[0x62]`, `*_DAT_08ebaa90 & 0xfc03`) and every offset must be doubled (`[0x62]` is byte `+0xc4`); in others it is a byte address (`(int)_DAT_08ebaa90 + 0xc5`). All offsets below are byte offsets, reconciled across functions (for example layout 2's visible bit is written at byte `+0xb8` by `ui_duel_start_play_member2_anim` and read as `[0x5c]` by `ui_duel_start_draw`). Defining a structure type for each area in Ghidra would remove the ambiguity.

#### Duel session flow (from the callers seen)

`system_duel_mgr_scene_main` runs `ui_duel_start_open` (loads `start/start_<l>.ehp` from device root 4 into the heap `[0x08ebaa58]`, waits for flag `0x08eba1d4`, then `ui_duel_start_init`), then `ui_duel_start_run_loop`. That loop also steps the duel-module loader (`system_duel_mgr_step_module_loading`), which is gated in tag link duels by `ui_duel_start_get_link_load_gate`. After the duel comes `ui_duel_result_init` and `ui_duel_result_run_loop`. Both screens are drawn from `system_duel_mgr_frame_callback`. While the duel runs, `ui_duel_mgr_on_engine_ui_event` is the engine's UI-event callback: it fetches 4 words with `duel_core_get_ui_event_args`, lets `audio_voice_dispatch_ui_event` play a voice, and forwards every event except id 1 to `ui_dispatch_draw_command`.

#### Duel start work area (0xe8 bytes, pointer at 0x08ebaa90)

Allocated by `ui_duel_start_init` from the duel manager heap and freed by `ui_duel_start_free`.

| Offset | Size | Meaning |
| --- | --- | --- |
| +0x00 | u16 | bits 0-1 mode (0 = full rock-paper-scissors, 1 = skip to the turn-order choice, 2 = versus screen only); bits 2-9 state |
| +0x02 | u8 | sub-step of the current state |
| +0x03 | u8 | bit0: the local player chooses the turn order (won the hand, or preset) |
| +0x04 | u8 | player hand / cursor (0-2) |
| +0x05 | u8 | opponent hand (0-2) |
| +0x06 | u8 | bits 3-4 turn-order choice (0 = go first); bits 5-6 random choice when the opponent decides; bit7 duel modules loaded |
| +0x08 | u16 | frame counter of the current step |
| +0x0a | u8 | low nibble: outcome of the hand (1 player wins, 2 opponent wins, 3 draw) |
| +0x0c, +0x0e | u16 | per-side hand state (0 none, 1 chosen, 2 moving, 3 done) |
| +0x10, +0x12 | u16 | per-side tween counters |
| +0x14, +0x16 | u16 | per-side "hand chosen" marker shown |
| +0x18 | ptr | prompt text (strTbl string) drawn at the bottom, or 0 |
| +0x1c | 6 x 0x1a | hand records: player hands at +0x1c + i*0x1a, opponent hands at +0x6a + i*0x1a |
| +0xb8 | u8 | draw flags: bit0 layout 2 visible, bit1 layout 3 visible, bit2 cursor visible, bit3 versus banner visible |
| +0xba, +0xbc | u16 | outcome labels for player/opponent (1/2/3, 0 = hidden) |
| +0xc0 | ptr | heap |
| +0xc4 | u8 | link duel: bits 0-3 local peer index, bits 4-5 local duel side, bit6 local peer is its side's peer |
| +0xc5 | u8 | bit1: tag link data exchange done (load gate) |
| +0xc8 | ptr | 0x400-byte exchange buffer (state 4) |
| +0xcc | ptr | bound `start_<l>.ehp` archive |
| +0xd0 | 4 x n | member cache of `ui_duel_mgr_get_string_table(id)` |

Hand record (0x1a bytes): byte +0 flags (bit0 visible, bits 1-3 hand index), +2 start rect, +0xa current rect, +0x12 target rect (rectangles are four `short`s x, y, w, h; the draw code uses w/h as percentages of the 0x50 x 0x74 card cell), +0x10 doubles as the flip angle in degrees used by `ui_janken_draw_hand_card`. Tweens are quadratic ease-in: `cur = start + t*t*(target - start) / (d*d)`.

Archive members (by id through the name table at `0x08eb9120`, formatted with the language letter): 0 and 1 background layouts (first entry `yugi_bg01.ehf`), 2 the intro/"member2" layout, 3 the turn-order "member3" layout, 4 the hand/icon texture atlas, 5 `strTbl_<l>.bin` (prompt strings 2-6).

#### Duel start state machine (`ui_duel_start_update`)

| State | Action | Next |
| --- | --- | --- |
| 1 | wait for fade-in; mode 2 creates the versus screen | 0xb (mode 2) or 2 |
| 2 | intro clip; creates the versus banner (kind 10) | 8 (mode 1), 5 (offline), 3 or 4 (link) |
| 3 | link sync, `ui_janken_reset_round` | 5 (or 8 in mode 1) |
| 4 | tag link: exchange 0x100 bytes of the setup buffer; copies 0xc0 bytes per player record for characters of category 5 | reset round |
| 5 | hands slide in (0x18 frames) | 6 |
| 6 | `ui_janken_update_choice` | 7 |
| 7 | `ui_janken_update_reveal` | 5/3 on a draw, else 8 |
| 8 | turn-order clip, prompt | 9 |
| 9 | `ui_janken_update_link_exchange` (turn-order choice) | 10 |
| 10 | `ui_janken_update_result` | 0xb |
| 0xb | `ui_duel_start_update_versus` | 0xc |
| 0xc | wait for fade-out; returns 1 or 2 | 0xd |
| 0xd | free; returns 3 | |

Rules established:
- Hands 0-2: hand `i` beats hand `(i + 1) % 3` (`(p0 - p1 + 3) % 3 == 2` means the player wins).
- Offline CPU hand (`ui_janken_pick_cpu_hand`): with r = rand % 100, r < 20 copies the player's hand (a draw); otherwise even r gives `(p + 2) % 3` (the CPU wins) and odd r gives `(p + 1) % 3` (the CPU loses). On a non-draw the CPU therefore wins and loses equally often.
- The winner picks first or second (up/down toggles, confirm). An opponent who wins picks randomly after 0x2d frames. When the choice is confirmed, a random seed goes to duel setup buffer `+0x188`, and the run loop stores the choice (0 = first) in setup `+0x18c`, inverted for local duel side 1 in link play.
- Tag duels with a non-zero count at tail block `+0x34` take the result of the previous duel of the match from `tail[+0x34 + 2*count]` (2: player chooses, 1: opponent chooses, 3: replay rock-paper-scissors).
- Setup `+0x190` of 5 or 6 skips straight to the versus screen. Setup `+0x194` of 4 or 5 selects BGM track 9, otherwise 8.

Link packets: `ui_duel_start_send_link_packet` sends `{phase, 0, state, step, payload...}` (phase 4 = hand choice, 5 = turn-order and versus) and sets the matching sync target. The result screen uses phase 9 (`{9, 0, state, step}`). The peer's buffer is read at bytes +2 (state), +3 (step), +4/+5 (hand, or CPU hand) and +5..+8 (seed).

#### Versus screen (work area 0x98 bytes, pointer at 0x08ebaa98)

| Offset | Meaning |
| --- | --- |
| +0x00 | heap; +0x04 bound archive (the duel start archive) |
| +0x08 | frame counter (state 6, up to 0x78) |
| +0x0c | state word |
| +0x10 | link flag; +0x11 kind; +0x12 entered from scene 2 (`system_scene_get_caller(6) == 2`) |
| +0x14 | 4 duellist entries x 0x18: +0 character, +2 variant, +4/+6 portrait character/variant, +8 deck kind, +0xa deck id, +0xc portrait flag bytes, +0x10 name pointer, +0x14 deck-name pointer |
| +0x74 | main timer {u8 mode (1 slide in, 2 slide out), u16 elapsed +2, u16 duration +4} |
| +0x7c | 4 layout slots (EHF members) |
| +0x8c, +0x90, +0x94 | TnId title tables: id index, offset table, string pool |

Kinds: 8 single duel, 9 tag duel, 10 small banner used during rock-paper-scissors. Kinds 0-7 belong to other callers (the 4-player link layout is used for kinds other than 8-10 with more than 2 peers). The slide offset is ±0x168 pixels interpolated linearly over the timer duration.

Archive members used by the versus screen (all in `start/start_<l>.ehp`): layouts from the 7-name table at `0x08eb95dc` (first `d_menu_partner.ehf`; for tag matches, slot 3 picks name `4 + duel number`); sprite textures from the 7-name table at `0x08eb98b0` (first `d_menu01.gim`); `kao.gim` (faces) and `karada.gim` (bodies); `duelmenu_msg_<l>.bin` (6 names at `0x08eb9b80`); and three title tables from `0x08eb9e80` (first `TnId.bin`).

Extractor-relevant layouts:
- **TnId title tables** (`ui_duel_versus_get_title_string`): member 1 is a list of word pairs `{character, index}`. A character's variant `v` uses the index word of the pair `v` places after the character's own pair. Entry `index + form - 2` (+3 for the second team slot) selects a u32 in member 2, which is a halfword offset into the UTF-16 string pool of member 3. Forms 0-1 come from `world_call_get_character_name_string` instead.
- **Versus sprite piece table** at `0x08eb9a70`: 27 entries of 10 bytes `{u16 texture index (low byte), u16 u, u16 v, u16 tex_w, u16 tex_h}`. Parts are assembled from pieces by `ui_duel_versus_draw_part` and `ui_duel_versus_lookup_part` (9-slice frames with 4-pixel borders).
- **Portraits**: characters below 0x2e use a 0x40 x 0x40 cell in an 8-column sheet indexed by `world_get_character_byte_3f` (values from 0x40 select the second sheet, part 0x17). Other characters are drawn as a 0x33 x 0x40 body cell from `karada.gim` with a 0x33 x 0x32 face cell from `kao.gim` on top, both chosen by `world_get_character_model_ids`. Characters 0x79-0x8d use fixed 0x33 x 0x54 full-body cells.

Versus update states: 0 fade-in, 1 wait (the draw function advances to 2 after the fade), 2 sound 0x7a7e, 3 intro, 4 main timer, 5 tag-only banner, 6 hold until the duel modules are ready and 0x78 frames have passed, 7 outro, 8 done (returns 1).

#### Duel result work area (0x1b8 bytes, pointer at 0x08ebaa94)

| Offset | Meaning |
| --- | --- |
| +0x00 | u16 state; +0x02 u16 sub-step |
| +0x04 | low nibble: current page (0 summary, 1 and 2 lists) |
| +0x08, +0x0c, +0x10 | DP words of lists A, B and C; +0x14 deductions (negative) |
| +0x18 | opponent-record status byte (from stats +0x210 + opponent); +0x1c new value, +0x20 previous value; +0x24 changed flag; +0x26 stamp zoom counter |
| +0x28 | low nibble: header tab; bits 4-5: header clip |
| +0x2a | s16 outcome layout member (2, 3 or 4; -1 none) |
| +0x2c | bit0 outcome layout visible; bits 1-4 previous page; bits 5-6 slide direction |
| +0x2e | u16 page-switch counter |
| +0x30 | 4 page records x 12 bytes {u16 scroll, u16 row count, row-id array, row-line-count array}: summary, list A (+0x3c), B (+0x48), C (+0x54) |
| +0x60 | duel statistics record = duel setup tail block + 0x3c |
| +0x64 | heap (the duel draw heap) |
| +0x68 | 0x120-byte list window record (message box) |
| +0x188 | bits 0-1 open message kind (1 prompt, 2 waiting, 3 connection lost); bit2 the prompt's choice 2 was taken (the screen then returns 2) |
| +0x18a | number of link peers at start |
| +0x18c | bit0 link session, bit1 first packet sent, bit2 archive load pending |
| +0x190 | `duel/result/result_<l>.ehp` buffer; +0x194 member cache |

Result archive members (name table at `0x08eb9398`): 0 `menu_bg.ehf` (background), 1 header layout, 2-4 tag-match outcome layouts, 5 UI atlas texture, 6 page tabs texture, 7 stamp texture, 8 `strTbl.bin`.

DP award (`ui_duel_result_init`):
- List A: bonus amounts from the statistics record at `stats + 0xc4 + 4*i` for each of the 0x53 entries in the u16 table `0x08eb919c`.
- List B: 20 DP for every non-zero `stats[4*i]` among the 0x31 entries in the table `0x08eb9138`, counted only in a local default-rules duel.
- List C: 200 DP when the opponent's record changes (table `0x08eb9244`).
- Offline penalties: -20 % when the card list contains entries of kind 1 or 3 (hypothesis: restricted cards), and -70 % without default rules.
- When the result beats the saved best (record table word +8), a 20 DP bonus is added and the new best is saved.
- The award is applied with `save_add_dp`.
- Each u16 entry of the three tables is `(strTbl string index << 1) | enabled flag`.
- In list B, statistic id 0x25 is displayed as minutes:seconds (presumably the duel time).

Result states: 0 setup, 1-2 header intro, 3 input, 4 page slide (16 frames), 5 exit; in a tag duel this step also computes the match outcome, 6 outcome animation, 7 wait for a button, 8 closing, 9 fade, 10 free (returns 1, or 2 when bit2 of +0x188 is set). The run loop treats 2 as "repeat": it restores the 0x858-byte setup copy at `0x08eba1fc` and clears the tail block counters.

Tag match outcome (`ui_duel_result_get_match_outcome`, tail block): count u16 `+0x34`, per-duel results u16 `+0x36..`. For a duel, 1 means the player's side won and 2 means it lost (the table page swaps them for the other team). Two wins or two losses end the match. After three duels the tally decides, and an even tally is outcome 3. Tail word `+0x24 == 8` returns the stored entry directly.

#### Name mismatches

- `ui_duel_mgr_get_string_table` is the generic member getter of the duel start archive (layouts and textures as well as `strTbl`).
- `ui_janken_update_link_exchange` is the turn-order (first/second) choice step for both offline and link play; the link exchange is only part of it.
- `ui_janken_draw_choice_icons` draws the win/lose/draw labels after the reveal, not choice icons.
- `ui_duel_result_get_frame_counter` returns word +4 of the frame-timing record, which the scrollbar uses as a pulse period; whether it really is a counter is unknown.

#### Open questions (batch 3 (rel_duel_mgr start, versus and result screens))
- Function table `0x08eb93f0` (result page draw routines): entry 0 is the summary page. Page navigation only cycles pages 0-2, using the DP words +8/+0xc as page 1/2 enables, yet `ui_duel_result_draw_list_c_page` draws page header 2 (list C). Read the table to confirm which routine is on which page (list A and B page routines are not in this pack; their row callbacks have no direct callers).
- Statistics record (`tail + 0x3c`): word +0x358 is printed on the summary page (hypothesis: DP total after the award, low). Which statistic does each list entry index correspond to?
- `save_get_byte_16e10` and `+0x12` (entered from scene 2): seen only as "partner present" layout tweaks and team-label sources. Their meaning in the story is unknown.
- Kinds 0-7 of the versus screen: which module creates them (the underground or link flows through `libduel_mgr_rel`?).
- Tag-duel load gate: the 0xc0-byte block copied per player record for character category 5 (setup record +0x230) is presumably a custom deck/appearance block of human link players. Needs a runtime check.
- Turn-order seed `setup + 0x188`: is it the duel engine's RNG seed? A link duel shares it between peers, which suggests it is.
- Skipped tail-call wrappers (`*_draw_text_fit_width_px`, `*_draw_text_px`, `*_draw_text_box_px`, `ui_duel_result_draw_text_to_screen_edge`, `ui_duel_result_split_text_lines`, `ui_duel_result_fit_text_scale_px`, `ui_duel_versus_call_draw_part`, `ui_duel_versus_call_draw_character_sprite`) need reading from the disassembly. The last two insert default arguments that are not visible here.

### Findings from batch 4 (rel_duel_draw HUD, cursor, info panels, duel objects)

Scope of this batch (UD1): 283 `rel_duel_draw` functions from `0x09841854` to `0x09872310`: cut-in speed lines and subtitle, the card information panel, the field cursor, board card objects and their motion, zone markers and badges, the duel HUD (LP, turn and phase indicators, portraits, turn timer), the attack pointer and arrow, zone highlights and card glows, the LP / number panels shown during cut-ins, the duel UI object list, and the popup draw tasks (counter changes, flying LP numbers, coin toss, Arcana roulette, burst). The draw command handlers (`ui_cmd_*`) and the UI mode table were not in these packs; they appear here only as callers. All facts below are read from the Ghidra decompilation (H unless marked).

#### Conventions seen everywhere

- **Location code** (u16): bit 0 side, bits 1-5 zone (0-4 monster, 5-9 spell/trap, 10 field spell, 0xb hand, 0xc Extra Deck, 0xd Deck, 0xe Graveyard, 0xf Banished), bits 6-15 index. The board code additionally uses bit 14 = face-up and bit 15 = battle position in `ui_draw_zone_markers_battle_phase` (only zones 0-4, index field unused there).
- **PSP d-pad bits** used by `ui_field_cursor_handle_input`: 0x10 up, 0x20 right, 0x40 down, 0x80 left. Cursor move sound `0x7a04`.
- **GE state numbers** passed to `system_ge_enable/disable` match sceGu: 0 alpha test, 1 depth test, 2 scissor, 3 stencil, 4 blend, 5 cull face, 9 texture 2D, 10 lighting (M, by the sceGu numbering).
- **Sprite helper**: `system_ge_set_sprite_extent(list, src_w, src_h, dst_w, dst_h)` then `system_ge_draw_sprite_flipped(list, x, y, z, u, v, ...)` draws one textured screen rectangle (the parameter names in the registry prototype say x, y, w, h; every use in this batch passes source then destination size).
- **3D-to-screen projection** (repeated inline): `sx = x * 480 / w + 2122 - 1808`, `sy = -y * 272 / w + 2044 - 1912` after view x projection (and model) matrices; the popup tasks use `+ 2048 + 74 - 1808` and `+ 2048 - 4 - 1912` instead. The constants look like viewport centre 2048 plus GE offset (0x710 = 1808, 0x778 = 1912) (M).
- **Animation speed**: many timings come from tables indexed by `ui_get_anim_speed()`: card motion duration `0x098cf050` (float), HUD layout frame step `0x098cf080`, arrow grow `0x098cf6b0` and fade `0x098cf6c0`. Speed 3 or above skips the centre card display (`ui_create_card_info_display`).
- **Presentation flags** (`system_set_presentation_flag`) raised while an effect runs, so the engine waits: 0 card motion / stacked draw, 0xc attack pointer flight, 0xd battle damage, 0x10 LP change, 0x12 hand relayout, 0x15 deck shuffle, 0x19 location point hold, 0x1f/0x38/0x39 card object flags, 0x25 turn-counter popup, 0x27 counter popup, 0x28 destruction countdown popup, 0x29 monster gather, 0x2c/0x2f/0x32 release effects, 0x3a Fusion/Synchro summon, 0x3c coin toss, 0x3d dice, 0x3e burst, 0x3f final-countdown win, 0x40 Destiny Board letters; HUD layout requests carry their own flag.

#### Card information panel (`0x098d54a0`, 0x880 bytes)

Two 0x218-byte panels at `0x098d54a0` and `0x098d56b8`, a 0x430-byte backup of both at `0x098d58d0`, then state words:

| Address | Meaning |
| --- | --- |
| `0x098d5d00` | manual two-panel view open |
| `0x098d5d04` | automatic two-panel view open (current chain link card) |
| `0x098d5d08` | two-panel view suppressed (confirmation prompt) |
| `0x098d5d0c` | card-view work buffer (duel draw heap, size = `ui_ehf_get_work_size` of layout 0x20001) |
| `0x098d5d10` / `0x098d5d14` | display state / target state (0-2 single panel, 3-5 pair) |
| `0x098d5d18` | slide timer (s) |
| `0x098d5d1c` | horizontal slide offset (px) |

Slide state machine (`ui_card_info_update`): 0/3 settled; when the target differs go to 1/4 (slide out to -120 px in 0.25 s), then 2/5 (switch layout, slide back in 0.25 s) and settle on 0 or 3.

Panel layout (0x218): `+0x00` card id, `+0x04` `save_get_card_value_bits4_6`, `+0x08` constant 0x160000, `+0x0c` kind, `+0x10` frame, `+0x14` ATK (-1 unknown), `+0x18` DEF, `+0x1c` Type, `+0x20` Attribute, `+0x24` Level, `+0x28` icon, `+0x80` 0x74-byte live-stats block (29 words), `+0xf8` display flags, `+0xfc` extra flags (bits 0-1: counter types 0x0c and 0x13), `+0x100` text scroll position, `+0x104` scroll maximum, `+0x208` u16 card instance (0 = shown by id), `+0x20c` card id, `+0x210` name id override, `+0x214` pinned flag. `ui_card_info_get_active_panel` returns the panel that follows the cursor (panel 1 when panel 0 is pinned).

Live display flags (`+0xf8`, `ui_card_info_refresh_live_stats`): 0x40 hand level, 0x7c field monster stats (0x7f for kinds 0xd/0xe), 0x30 off-field Attribute/Type (Graveyard), 0x100 spell-counter capacity, 0x200 turn count, 0x400 own counters, 0x800 type 0x0f, 0x1000 type 0x0d, 0x2000 type 0x0e, 0x40000 type 0x10, 0x80000 type 0x11, 0x400000 type 0x12, 0x200000 type 0x02, 0x100000 type 0x03, 0x1000000-0x80000000 types 0x04-0x0b, 0x800000 renamed card (slot name id or `+0x210`), 0x4000/0x8000/0x10000/0x20000 a slot parameter for a few card ids (0xeb4, 0x14d1, 0x14cc, 0x1358, 0x1357 / 0x1a19, 0x145b, 0x171f / 0x19c2 / 0x1b67, 0x1368).

#### Field cursor (`0x098d5d20`, 0x90 bytes)

| Offset | Address | Meaning |
| --- | --- | --- |
| `+0x00` | `0x098d5d20` | position (vec4) |
| `+0x10` | `0x098d5d30` | rotation (quaternion) |
| `+0x20` | `0x098d5d40` | location code |
| `+0x24` / `+0x28` | `0x098d5d44` / `0x098d5d48` | grid column / row |
| `+0x2c` / `+0x30` | `0x098d5d4c` / `0x098d5d50` | saved-location flag / saved code (`ui_field_cursor_set(..., save)`, `ui_field_cursor_restore`) |
| `+0x34` | `0x098d5d54` | dirty (cursor moved; panel and listeners updated next frame) |
| `+0x38` | `0x098d5d58` | locked (input ignored, locked variant drawn) |
| `+0x3c` | `0x098d5d5c` | 16 listener callbacks `(location, instance)` |
| `+0x7c` / `+0x80` | `0x098d5d9c` / `0x098d5da0` | field location / hand index remembered by the hand toggle |
| `+0x84` | `0x098d5da4` | highlight owner (1 = opponent colours: textures 0x40027/0x40028) |

Navigation grid: 7 x 7 u16 location codes at `0x098ce928` (row stride 0xe bytes); a cell whose zone is 0x10 is a gap. Leaving the grid vertically enters the hand. Jump table for "first selectable card": `0x098ceba0` (two u32[16] location orders, one per side). Overlay sprite rectangles: `0x098ce98c` (16 bytes per `zone + 16 x side`, alternate at `0x098ce994`).

Cursor models (duel object models): 0x1000e/0x1000f zones by side, 0x10011 own hand, 0x10012/0x10013 piles and field-spell zone; +8 for the selectable-zone variant. Material names checked by the texture hooks: `field_cursor00.iff`, `field_cursor01.iff` (replaced by 0x40027/0x40028 for the opponent), `field_cursor02.iff` (3-frame animation from duel textures 0x40021-0x40023, frame/4).

Action masks (`duel_core_view_get_card_action_mask`): bit 0x800 = valid attack target; 0x808 = what the cursor jumps to when input opens; bits other than 0x402 make a card "selectable" for cycling and highlighting; the icon row draws one icon per set bit 0-12 (`ui_card_action_draw_icon`).

#### Board card objects

- Zone lists: `ui_get_zone_card_object(side, zone)` returns a list sentinel at `0x098e3a60 + s x 0xb00 + zone x 0xb0` (16 zones per side); for zones 0xb-0xd `s` is `[0x098e6664 + side x 4]` (deck-set index; tag partner, M). The first object is `sentinel+4`; empty when it points back to the sentinel. Free list sentinel `0x098e39b0` (`ui_pop_free_card_object`).
- Object fields used here: `+0x00/+0x04` links, `+0x10` position, `+0x20` start position, `+0x30` target position, `+0x40` rotation, `+0x50` start rotation, `+0x60` target rotation, `+0x70` timer, `+0x74` duration, `+0x78` next-move code (s16), `+0x7c` next-move argument, `+0x80` u16 card for the face texture, `+0x82` location code, `+0x88` instance, `+0x8c`/`+0x8d`/`+0x8e` flag bytes (completion actions: summon/set/placed-summon effects, chained move, pile sync, arc on x or y; `+0x8d` bit 4 hides the marker, bit 5 = card may be shown), `+0x90` highlight glow handle, `+0x94` material glow handle, `+0x9c` four per-frame callbacks (return non-zero to remove).
- Motion: lerp + quaternion slerp over the duration, plus an arc `360 x u x (1 - u)` (u = t / duration). Card sounds `0x7a2f`-`0x7a33` at random.
- ATK/DEF count tweens: 2 x 5 records of 0x20 bytes at `0x098e6678` (shown ATK, shown DEF, start ATK, target ATK, start DEF, target DEF, timer, duration). Drawn as 7 x 9 digits (8 x 10 while changing) during the Battle Phase.
- Chain-link badges: words `0x098e67b8 + side x 0x44 + zone x 4` (link number), location stack u16 at `0x098e6840`, depth `0x098e6880`.

#### HUD

- Layouts: 0x20001 card view, 0x20002 turn indicator (side 0 loop frames 0-0x77, side 1 0x82-0xf9, transition 0x79-0x80), 0x20003 phase indicator (27 states, frame ranges at `0x098cf12c` pairs, phase per state at `0x098cf0c0`; 0-0xc side 0, 0xd-0x19 side 1, 0x1a neutral, reset frame 0x20e).
- HUD state `0x098e6934` (0x60): frame counter (30/s), shown LP[2] `0x098e6938`, target LP[2] `0x098e6940`, roll start values `0x098e6948`, roll targets `0x098e6950`, roll start frames `0x098e6958`, shown turn side `0x098e6960`, target turn side `0x098e6964`, phase-indicator state `0x098e6968`, target phase `0x098e696c` (7 = none), portrait expression[4] `0x098e6974`, expression timers[4] `0x098e6984` (an expression can change again after 15 ticks). LP roll: 60 frames linear.
- HUD layout animation state `0x098e6898` (0x9c): a 0x44-byte request (ehf, start, end, hold-loop start/end, end callback + argument, presentation flag + enable, sound, x, y, GE layer, text frame, duel-dictionary text index, text centre x/y), then playing `0x098e68dc`, queued `0x098e68e0`, hold done `0x098e68e4`, in hold loop `0x098e68e8`, loop count `0x098e68ec`, queued request `0x098e68f0`. The hold loop is left on a button press offline or after 5 loops in a network duel.
- HUD glyph table `0x098cf27c`: 8-byte records `{u16 u, v, w, h}` of duel texture 0x40006 (LP digits 0x22-0x2b, timer digits 0x2d-0x36, game marks 0x1e-0x20).
- Screen positions: names at x 0xd2 / right edge 0x1a2, LP labels at x 0x98/0x1a6, turn number centred near (0x12d, 9), turn timers at (0x9f, 0x10)/(0x1a8, 0x10), portraits at (0x93, 0x1b)/(0x196, 0x1b), help button at (0x197, 0x104), coin icon at (0x70, 3). The turn timer blinks below 31 s.
- Portraits: 47 px (27 px for a waiting tag partner), nine-slice frame from texture 0x4001f (48-px columns per side), bust-up expressions in 40-px cells (3 per row), generic characters from `kao.gim`/`karada.gim` of the cut-in base archive; active-player pulse 40 frames.

#### Attack pointer and arrow

- State `0x098e6bc0` (0xc bytes): pointer object, arrow object `0x098e6bc4`, arrow from/to codes `0x098e6bc8`/`0x098e6bca`.
- Pointer data (0x60, duel draw heap): `+0x00` position, `+0x10` rotation, `+0x20` mode (0 follows the cursor, 1 flying), `+0x24` attacker location byte, `+0x26` target location byte, `+0x30` start, `+0x40` target (height -2.0), `+0x50` flight time = 0.5 / speed factor. Model 0x1001c with texture 0x40005, 30 units above the zone.
- Arrow data (0x70): 64 segment intensity bytes, `perticle_for_arrow.gim`, `arrow_head.gim` (duel archive 0x80001), head index `+0x48`, repeat `+0x4c` (cleared by `ui_stop_attack_arrow` so it fades), finished `+0x50`, endpoints `+0x54`/`+0x60`, colour `+0x6c` (0xffff6060 while choosing, 0xff0606ff for the declared attack). Sound 0x7a34.

#### Duel UI objects and draw tasks

- Object list: sentinel `0x098e6d7c` (`+0` / `+4` links), delete-current flag `0x098e6d98` (`ui_delete_current_duel_object`). Object (0x1c bytes, duel draw heap): links, draw `(obj, data)`, update `(dt, obj, data)`, free `(obj, data)`, elapsed seconds `+0x14`, data `+0x18`. The 0x8a4-byte area also holds the glowing-object list (512 pointers at `0x098e6d9c`), shared pile glows `{handle, count}` x 16 at `0x098e759c`, deck-effect running `0x098e761c`, attack-ready markers enabled `0x098e7620`.
- Patterns: "request now or retry" objects (card display, hand relayout, monster gather, deck shuffle) re-check `field_3d_board_any_object_busy`/`_is_settled` every frame; "wait objects" (`ui_create_wait_object(flag)`) hold a presentation flag until an effect's completion callback destroys them; `ui_create_wait_until_object(flag, predicate, expected)` waits on a predicate.
- Draw-task callbacks (`ui_duel_create_draw_task(callback, done_cb, done_arg, data_size)`) are called as `(phase, data)` with phase 1 on the first call and return 2 to keep running or 4 when finished; `ui_duel_set_draw_task_flag1(handle)` asks a task with open-ended duration to fade out.
- Counter popups (`ui_start_zone_value_change` kind -> counter reader -> starter): 0 type 0x0f stat popup (alt icon 0x4c), 1 type 0x0d sprite b, 2 type 0x0e sprite c, 3 battle destruction countdown value popup (alt, flag 0x28), 4 type 0x10 sprite d, 5 type 0x11 sprite e, 6 type 0x03 sprite e v1, 7 type 0x02 sprite e v2, 8 type 0x12 sprite d v1, 9-0x11 types 0x04-0x0c icon cells r0c0-r2c0, 0x12 type 0x13 icon r2c1. Icon cells are 60 x 60 at `(col x 60, 0x100 + row x 60)` of effect texture 0x18. Common timeline: fade in 8, pause 4 (or 8), digit roll 4 with sound 0x7a37, hold 16, fade out 8.
- Flying LP number (`ui_start_lp_change_effect`): start points `0x098cf8b0`, end points `0x098cf8c8` (3 words per side), colour (0xff, 0x3c, 0x3c) for damage, (0, 0xef, 0xbb) for gain; sound 0x7a36 (loss) / 0x7a37 (gain); the LP counter starts rolling only when the number lands (`ui_on_lp_change_effect_done`).
- Arcana Force roulette: card quad 108 x 154, 0x40 spin steps upright, 0x20 or 0x60 (random) reversed; sounds 0x7a43/0x7a44.
- Zone highlights: table `0x098e6bcc` (handles [2][16], kinds, layers); 96 x 96 quads from a 4 x 2 atlas of effect texture 0x16 (style 6 tinted red); kind 7 is drawn on GE layer 4 (through `ui_create_zone_highlight_task_dl`), the rest on layer 5. Card glows: effect textures 0x1a (highlight), 0x1c, 0x25 (materials), turning about Y.

#### LP and number panels (cut-in)

- State `0x098e6d4c` (0x30): panel object, saved perspective (4 floats `0x098e6d50`-`0x098e6d5c`), textures.
- Extractor-relevant members of duel archive 0x80001: Japanese `lp_pnl01_j.gim` (128 x 96 gradient base), `lp_pnl02_j.gim` (overlay), `lp_pnl_nmb01_j.gim` (24 x 34 digit cells in a 128 x 128 texture, label at (0, 0x44)), `lp_pnl_nmb02_j.gim` (17 x 24 digits, labels at (0x55, 0)/(0x55, 0x11)); other languages `lp_pnl_a01.gim` (184 x 122 base; bars at (0xb8, 0xbb)/(0xb8, 0xdb)), `lp_pnl_nmb01_a.gim` (18 x 37 or 20 x 27 digits), `pnl_a00.ehf` + `pnl_a00.tmf` (LP gauge layout, frame 0-99 = gauge level against 8000).
- LP roll panel data (0x90): x, y, from, to, current, gauge max (8000), origin (x - 64, y - 48 Japanese; x - 92, y - 61 otherwise), state (1 delay 10 frames, 2 count 35 frames, 3 hold 45 frames, 0 delete), five 0x10-byte roll digits at `+0x24` (rolling flag, angle, current, next), counters `+0x74`/`+0x78`, bar scales and speeds `+0x7c`-`+0x88`, wide flag `+0x8c`. Sounds: loop 0x7a1f while counting, 0x7a1d when the LP reach 0, 0x7a20 otherwise. Japanese digits roll like a drum (3D rotation about X); international digits switch flat. Japanese hides leading zeros; other languages show at least 4 digits.
- Number-pair panel data (0x34): two 5-character strings (digits, `*` blank, `?` for negative inputs), shown 45 frames, sound 0x7a1e.
- The Japanese frame uses a stencil pass: gradient (3 rows x 9 keys of RGB at `0x098cf80c`, 45-frame cycle), panel alpha into stencil, rotating additive light (frame / 20 rad) through the stencil, overlay.

#### Other asset names read here

- Cut-in archive: `ryusen01.ehf` (speed lines; level fades over 10 frames).
- Icon archive (`container_get_icon_archive`): `buttom_icon1.gim` (18 x 22, 4 cells, 15 frames each).
- Duel textures by id (`ui_get_duel_texture`): 0x40001, 0x40004, 0x40005 (attack pointer), 0x40006 (HUD digits and glyphs), 0x40018, 0x40019, 0x4001d (cursor overlay), 0x4001e (badges, coin icon), 0x4001f (portrait frames, help button), 0x40021-0x40023 (cursor animation), 0x40027/0x40028 (opponent cursor).
- Cut-in subtitle: voice cue (bank, index) -> u16 offset table (column by `world_character_is_generic`) -> string index; drawn at font scale 12, centred, bottom at y = 256 over a 50 % backing.

#### Name mismatches

- `ui_field_cursor_add_blocker` / `ui_field_cursor_remove_blocker` register and remove cursor-change listeners (called with location and instance), not blockers.
- `ui_show_stat_change` shows a counter change (counter types 0x01/0x00), not an ATK/DEF change.
- `ui_get_zone_card_object` returns the zone's list sentinel, not an object.
- `ui_create_zone_highlight_task_dl`: the extra argument is the GE layer.
- `ui_draw_hud_icon_4001e` draws the coin-toss result icon.
- `ui_get_zone_card_scale`: returns a factor from `zone + 16 x side` whose purpose is unclear (L).
- `ui_stub_noop_duel_hud_hook` receives the duellist names with position and width; it may be a lost text-draw tail call (L).

#### Open questions (batch 4 (rel_duel_draw HUD, cursor, info panels, duel objects))
- `ui_stub_noop_duel_hud_hook` (`0x09858afc`, 20 bytes): empty or a lost tail call to a text drawer? (check the instructions; the names are visibly drawn in game?).
- `ui_draw_badge_number_at_position`: its callers pass only two visible arguments; where the badge number (third argument) comes from needs the disassembly.
- `ui_draw_card_texture_quad_scaled` (`0x09856400`, skipped) and `ui_duel_create_value_popup_task_moving` (`0x09871dcc`, skipped): argument order hidden by the decompiler.
- `ui_create_wait_object`'s update callback `0x09863a94`, the card display callbacks `0x0986221c`/`0x09862214`, the arrow draw callback `0x0985d004` and the popup hold callbacks `0x09863434`/`0x0986343c` are code labels, not functions, in Ghidra.
- `0x0989ddb8` (unnamed duel-view test used by `ui_update_zone_highlights` to force highlight kind 7).
- Meaning of `ui_get_zone_card_scale`'s ranges 0x10-0x100, 0x200-0x2000 and 0x8000 (unreachable with side 0/1).
- `0x098e6664` (per-side deck-set index for hand/Extra/Deck objects): confirm it is the active tag duellist.
- Which counter types 0x00-0x13 map to which counters (Spell Counters, A-Counters, ...): needs the engine side (`duel_core_view_get_counter_count_type_*`).
- The end of `ui_begin_lp_panel_projection` (last texture state writes) is garbled in the decompilation.

### Findings from batch 5 (rel_duel_draw command and mode tables, task pool, dialogs, help, options)

Scope: `rel_duel_draw` (base `0x0983fb00`), second half by address (`0x09878324`-`0x098b8878`): draw-task pool, draw command handlers, duel draw set-up and frame, resource tables, UI mode machine, dialogs, card list picker, card action menu, duel options, help viewer. 448 functions documented, 17 skipped (empty tail-call bodies and wrappers whose register arguments the decompiler hides).

#### Draw-task pool (`0x098e7680`)

- `0x098e7680` u32 creation serial (wraps to 0 after `0xffffff`), then 254 (`0xfe`) slots of `0x1c` bytes at `0x098e7684`. `ui_duel_init_draw_tasks` clears `0x1cf0` bytes from `0x098e7680`.
- Slot: `+0x00` state (0 free, 1 created, 2 running, 3 stop requested, 4 free on next pass), `+0x04` flags (bit 0 = end/fade-out request, set by `ui_duel_set_draw_task_flag1`, tested by highlight/glow tasks), `+0x08` handle = `slot << 24 | serial & 0xffffff`, `+0x0c` tick callback `int tick(int state, void *data)` whose return value becomes the new state, `+0x10` destructor `void d(int arg)`, `+0x14` destructor argument, `+0x18` data block (zeroed, from the duel draw heap).
- `ui_duel_run_draw_tasks` (once per frame from `ui_draw_duel_objects`): 4 → freed, 3 → 4, 1/2 → tick. A stale handle (slot handle word differs) resolves to NULL.
- Animation helpers used by all effect tasks: `ui_duel_get_progress_ratio(frame, duration)` = clamp(frame)/duration; sine/cosine eases iterate `sin(K·t)` / `cos(K·(1-t))` with K = float `0x098c4fc4` (probably π/2, M); `ui_duel_get_anim_speed_value` / `_frame_step` index 4-word tables `0x098cff64` / `0x098cff74` by the animation speed 0-3.

#### Draw command dispatcher (`ui_dispatch_draw_command`, table `0x098d0180`)

- 75 records of `0xc` bytes `{int event, int arg_kind, handler}`; sorted once at first use (`qsort`, flag `0x098e949c`), then binary-searched. The engine's UI events arrive with three u32 words (a, b, c).
- Argument kinds (how a, b, c are unpacked): 0 none; 1 (a); 2 (a, b); 3 and 7 (a, b, c); 4 (a, b, c & 0xff, c >> 8 & 0xff); 5 (a, b, c & 0xffff, c >> 16); 6 (a, b & 0xff, b >> 8 & 0xff, c); 8 (a, (s16)b, (s16)c); 9 (a & 0xffff, a >> 16, (s16)b, (s16)c); 0xa ((s16)a, b); 0xb ((s16)a, b, c); 0xc (a & 0xff, a >> 8 & 0xff, b, c); 0xd (a & 0xff, a >> 8 & 0xff, b & 0xff, b >> 8 & 0xff, c). Handler return values are discarded (all `ui_cmd_*` return 1).
- Handlers take engine sides and convert them with `duel_core_engine_side_to_view`; location codes keep the layout bit 0 side, bits 1-5 zone, bits 6+ index. Movement (`ui_cmd_move_card`): (instance, kind, src_code, dest_code); a token whose destination zone is `0x0e`-`0x10` is simply released.
- Chain markers: link 1 is only remembered (`0x098e9498`, `0x098e94b0`/`b4`/`b8`); the marker of link 1 is pushed when link 2 arrives (`0x098e9494` set), so a one-link chain shows no marker. A resolving link with the shown flag plays layout `0x2000c` and pops the marker in the completion callback (8-byte heap record: u16 location code, u32 card id at +4).
- Prompt kinds of `ui_cmd_show_prompt` (also stored as the input prompt kind `0x098e9acc`): 0 confirm, 1 confirm with 600-frame timeout (not shown when the local human is asked), 2 confirm with card info, 3 chain-response card prompt, 4 effect option list (tabs), 5 6-icon choice (phase menu, see Name mismatches), 6 Type grid, 7 Attribute grid, 8 card position yes/no, 9 plain choice, 0xa card row, 0xb number choice (arg bits 16-19 base, 20-23 step, 24-31 count, 0-15 format string), 0xd info panel, 0xe Ritual level counter. The text argument is a dialog string number when its high half is 0.
- List kinds of `ui_cmd_open_card_list`: 1-5 browse lists (titles dialog strings `0x246 + (kind - 1) * 2 + view side`, cursor moved to zone `0xc`-`0xf`), 6/`0x4a` single pick, 7-`0x26` exact pick count, `0x28`-`0x47` 1..limit, `0x48` 0..limit, `0x4b`-`0x4e` card name declaration (`0x4e` monsters, `0x4d` monsters with frame != 3, `0x4c` any card with frame != 3, `0x4b` any card; ids `0xe88`-`0x1f39` sorted by `card_db_get_sort_position`).

#### HUD layout request (`ui_play_hud_layout_anim`, 0x44 bytes)

Built on the stack by the phase/turn/result/chain handlers: `+0x00` layout (`ui_get_duel_layout(id)`), `+0x04` start frame, `+0x08` end frame (-1 = to the end), `+0x0c`/`+0x10` (0x32/0x46 for the result), `+0x14` completion callback, `+0x18` its argument, `+0x1c` slot/kind (0, 1, 2, 5, 6, 0x34 seen), `+0x20` 1, `+0x24` probably a sound id (`0x7a22` turn, `0x7a23` phase, `0x7a35` chain resolve; M), `+0x30` 8, `+0x34`/`+0x3c`/`+0x40` text box (0x1e, 0x13a, 0xb6), `+0x38` string index (win reason + `0x3c` for side 0, + `0x2e` for side 1; reason `0xd` shown as `0xb`, reason 8 shown as 1 outside match duels). Layout ids: `0x20004` duel start, `0x20005`-`0x20007` results, `0x20008` turn change (frames 0-0x30 opponent, 0x32-0x62 player), `0x20009` phase banner (6 ranges of 0x19 frames: 0-0x18 … 0x7d-0x95), `0x2000c` chain resolve.

#### Duel draw set-up and frame

- Set-up record from the duel manager (`ui_duel_draw_setup`), copied to `0x098e94d8` (0x74 bytes): word 0 duelist count (tag duel when >= 3), `+0x04` character ids [4], `+0x14` variants [4], `+0x24`/`+0x34` replacement pair [4] used in network sessions for ids < 2, `+0x44` deck pointers [4] (0xc0-byte decks copied to `0x098e9558 + i·0xc0`, pointer table `0x098e951c`), `+0x54` 0x60-byte duelist blocks [4] (copied to `0x098e9858 + i·0x60`, `ui_get_duelist_setup_block`; used as the "chosen card" for deck stacking), `+0x64`/`+0x68` active duelist per side (copied to `0x098e954c`/`0x098e9550`; `0x098e9540` forced to 1 when both are 0), `+0x6c` first player (`0x098e9554`), `+0x70` cut-ins disabled (`0x098e9ab4`).
- Life cycle (exported to `rel_duel_mgr`): `ui_duel_draw_init` (heaps, render state, sort tables) → `ui_duel_draw_setup` → `ui_duel_draw_start_loading` / `_poll_loading` → `ui_duel_draw_begin` (LP targets 8000, HUD phase 7, UI mode 1, active flag `0x098e94c8`) → per frame `ui_duel_draw_frame_if_active` → `ui_run_duel_draw_frame` → `ui_duel_draw_reset` / `ui_duel_draw_term`.
- Draw flags `0x098e94d0` (`ui_test_set_draw_flags(mask, mode)`: mode 0 clear, >0 set, <0 test): 8 cut-in mode (3D scene suspended, cut-in drawn on layer 8 with scissor (100, 0, 0x118, 0x110)), 0x10 one-frame skip, 4 info panel, 0x20 fade layer 10, 0x80 HUD shown (toggled by Select), 1/2/4 cleared while the card viewer is open, `0x87` cleared while the help is open.

#### Resource tables (extractor-relevant)

All binary-searched by `ui_find_resource_entry(key, table, count, stride)` (first word = id), sorted at init by `ui_sort_duel_resource_tables` except the string tables:

| Table | Address | Records | Layout | Notes |
| --- | --- | --- | --- | --- |
| Models | `0x098d0960` | 0x28 × 0x18 | id, …, `+0x14` model instance | destroyed by `ui_release_duel_resources` |
| Archives | `0x098d0dd0` | 4 × 0xcc | `+0` id (`0x80001`, `0x80002`, …), `+4` default stem (first is `basic_jj`), `+0x34 + lang·4` per-language stems, `+0xc4` buffer, `+0xc8` loading flag | path = stem + `".ehp"` (string `0x098d1d4c`), root 4, size from `container_get_file_size`; loaded asynchronously, bound with `container_ehp_bind_with_callback` |
| Textures | `0x098d1380` | 0x23 × 0x10 | id, archive id (-1 = stand-alone file), member name (first `cil_0000.gim`), cache | ids `0x400xx` |
| Layouts | `0x098d16e0` | 0xd × 0x14 | id, archive id, `.ehf` name (first `score_atkdef10.ehf`), `.tmf` name or NULL, cache | ids `0x200xx`; `.tmf` flags applied on first use |
| String tables | `0x098d1b1c` | 0x23 × 0x10 | id, archive id, member name (first `ddstrtbl_jpn_idx.bin`), cache | ids language-relative: `0x8000d + lang` is the headed table read by `ui_get_duel_dict_word`; `0x80017 + lang` and `0x8001e + lang` are the help topic and label tables |

- Card art: list `0x098e9b00` (16-byte entries, count `0x098eaf00`, entry 0 = 0, then every token id in `0xe88`-`0x1f39`, then each deck's main (`+0x0c`, count `+0`) and Extra Deck (`+0xa2`, count `+8`) ids, deduplicated and sorted). Two readers: `cardh.cip` (large, work area `0x098eaf10`, `0x149000` bytes, pointer `0x098eaf08`) and `cardm.cip` (small, `0x09a33f10`, `0xa9000` bytes, pointer `0x098eaf0c`); the artwork variant per card comes from `save_get_card_value_bits4_6`; missing art falls back to texture `0x40002`.
- Movies: table `0x098d27f0` (0x4b × 0x10, path at +8), looked up first with key + 100000, then key; played from root 3 with 0x17cc00 bytes of work memory; VRAM (0x110000 bytes) cleared afterwards.
- Options screen: textures `menu_opt01.gim` … (three 0x40-byte names at `0x098d32d8`, by variant) in archive `0x80001`; strings `option_msg_<l>.bin` (six names at `0x098d3490`) read with `card_db_get_dictionary_word`.
- Help viewer: pages of images loaded by path (`sprintf` format `0x098d3dc8`, root 3) through the image table `0x098d3910` (topics 0-0xc) / `0x098d3c70` (topics 0xd-0x18); index tables `0x098c61d8` / `0x098c620c` (4-byte records: u16 first, u16 last string). `window01.gim` of the icon archive is used for frames throughout.

#### Duel UI mode machine (table `0x098d1f5c`)

- Rows of 0x14 bytes: `+0` enter, `+4` draw (`void *draw(void *list)`), `+8` update, `+0xc` exit. State `0x09bdd0b4` mode, `0x09bdd0b8` argument (a presentation flag index set while the mode is active; dialogs use `0x36`), stack `0x09bdd0bc` (4 entries of 8 bytes, depth `0x09bdd0dc`), entering flag `0x09bdd0e0` (draw/update suppressed until the 3D board is settled).
- `ui_set_duel_ui_mode` runs the old exit and the new enter; `ui_push_duel_ui_mode` runs only the new enter; `ui_pop_duel_ui_mode` runs only the current exit (the covered mode is not re-entered).
- Modes seen: 1 field cursor, 2 card list picker, 3/4 message-window dialogs (4 for every prompt), 5 card viewer, 6 cut-in, 7 flag message, 8 help, 9 options, 0xb movie, 0xc (popped by `ui_close_active_duel_ui_mode`; meaning unknown).
- Common input (`ui_update_duel_draw_common_input`): analog Y scrolls card text; L+R opens the expression picker (9 button masks at `0x098d205c`); Start opens the help; then the mode's update.
- PSP pad masks used: Select 0x1, Start 0x8, Up 0x10, Right 0x20, Down 0x40, Left 0x80, L 0x100, R 0x200, Triangle 0x1000, Circle 0x2000, Cross 0x4000, Square 0x8000. Pad state: `+0` held, `+4` pressed, `+8` released, `+0xc` repeat, `+0x14` analog Y.
- Field cursor mode shortcuts: L + D-pad jumps to zones 7/10 of either side; L + face buttons open Graveyard/banished lists (action 1, mask bit 2); R or cancel answers deck-stacking (action 0xc, mask 0x1000); Circle/confirm opens the card action menu; Triangle the card info menu (view / close input / options / help).

#### Dialog building blocks

- Message window `0x09bdd2ac` (list window, 0x144-byte block): `+0x58/+0x5a` x/y, `+0x6c/+0x6e` size, `+0x84` text, `+0xa0` caption, `+0xc9` bits 3-6 style (0x20 → 2, 0x30 → 3), `+0xca` low nibble choice style (1 or 3), `+0xd0` top index, `+0xd2` bits 0-4 cursor row, `+0xe9` state (0/1/6 closed, 3 open), `+0x11c` pad override, `+0x120` close callback, `+0x124` draw callback, `+0x128` cursor-move callback, `+0x12c` update callback, `+0x130` last result, `+0x134`/`+0x138` caption/text heap copies. Centred on (314, 132). Every dialog opener follows the same pattern: open window → push mode 4 → argument 0x36 → install callbacks → sound `0x7a0c` (or `0x7a08`).
- Window defaults (`ui_init_window_defaults`, 0x120 bytes): margins 10/10/8/8, font 12, colour black, scale 1.0.
- Info panel (`0x09bdd3f0` window list, descriptor `0x09bdd43c`, state `0x09bdd6b4`): 6 closed/new, 3 top, 2 bottom, 4 top→bottom, 1 bottom→top, 5 closing, 0 unused; it moves away from the field cursor's side (cursor blocker `0x098a6d44`), y = 0x42 or 0xca minus half height; closes when its close test (default: no pending engine action) returns non-zero.
- Grid selector (`0x09bdd14c`, 0x150 bytes): descriptor of 11 words (first value, end value, columns, caption, label fn, item draw fn, mark draw fn, cell w/h, min/max picks); cursor row `0x09bdd184` (9 = confirm button), picks `0x09bdd188` (count `0x09bdd208`); answer = bit mask of picked values (Attribute) or lowest picked value (Type 1-0x15).
- Card list picker (`0x09bde010`, 0x2ca8 bytes): windows `0x09bde010` (list) and `0x09bde130` (sort/command/filter), up to 0x200 entries `0x09bde458`, filtered `0x09bdec5c` (count `0x09bdec58`), displayed `0x09bdf45c`, picks `0x09be046c` (count `0x09be0468`), max `0x09be0460`, min `0x09be0464`, sub-menu `0x09be0c70` (1 sort, 2 command, 3 filter), sort key `0x09be0c74` (0 order, 1 sort position, 2 frame, 3 level, 4 ATK, 5 DEF, 6 Type, 7 Attribute, 8 Spell/Trap icon, 9 card limit), ascending `0x09be0c78`, filter `0x09be0c84` (frames from `0x098d3198`). Decide: selected candidate = first pick, answer = pick count, pick order 1..n recorded per candidate.
- Card action menu (`0x09be0cb8`, 0xa0 bytes): action table `0x098d31d8` (16 entries × 16 bytes: icon u, v, label string, action bit/code). Codes < 0xd go to the engine; 0xd card viewer; 0xf put the chosen card on top of the deck then action 0xc. Extra mask bits added by the UI: 0x2000 view card, 0x8000 stack chosen card. The window is projected above the card (screen x = px·480/w + 314, y = -py·272/w + 132).

#### Duel options (`0x09be0d5c`, 0x3c bytes)

`+0` variant (0, 1 in-duel without the first two groups, 2), `+4` cursor item, `+6` first item, `+8` 8-byte settings record (working), `+0x10` saved copy (restored on cancel), `+0x18` redraw byte, `+0x1c` heap, `+0x20` archive, `+0x24` menu texture, `+0x2c` frame counter, `+0x30`-`+0x38` text colours. Settings record: byte 0 bit 0 `save_setting_b0_bit3`, bits 1-2 `b0_bits4_5` (0-2), bits 3-4 animation speed (0-3), bit 5 option flag 0 (cut-ins), bit 6 option flag 5, bit 7 option flag 2; byte 1 bits 0-1 `b2_bits1_2` (0-2), bit 2 option flag 4, bit 3 option flag 3; u16 +2/+4/+6 volume settings 2/0/1 (0-15, applied live). Items 0-0xb map to those fields in that order; item 2 is skipped outside Japanese and item 7 in variant 1.

#### Help viewer (`0x09be0e4c`, 300 bytes)

Topic from the phase / input mode (Draw 4, Standby 5, Main 6, Battle 7, End 8, chain/prompt 9). Three panes: topic list (`0x09be1048`, state machine 0-7), index list (`0x09be1168`), text pane (`0x09be0d60`, scroll `0x09be0e38`, text height `0x09be0e3c`, image `0x09be0d6c`, content height = text + image + 10). Generic list record (0x34 bytes): u16 count, cursor, flag byte (bit 0 focus, 1 ignore confirm, 2 ignore cancel, 3 ignore up/down), result (1 confirm, 2 cancel), area, margins, five callbacks (frame, item, item background, cursor, measure), scroll, content height.

#### Name mismatches

- `ui_duel_open_flag_choice_dialog`, `ui_flag_choice_*`: a 6-icon row dialog whose decide submits action `0x0d + choice` in setup mode 2 (the phase-menu codes of `duel-runtime.md`) and whose captions are duel strings `0x15`+: the phase selection dialog (M).
- `ui_draw_two_way_card_choice`: draws a spinning coin and strings 0xa/0xb: the coin call (heads/tails), not a card choice (M).
- `ui_set_info_panel_state_bit0`: the info panel's field-cursor blocker (moves the panel to the side away from the cursor).
- `ui_start_duel_end_card_fx_14`: starts the Final Countdown win effect.
- `ui_cmd_show_counters`: handles 20 kinds of value changes (stat changes and zone value styles), not only counters.
- `ui_cmd_show_activation`: only calls `field_3d_board_update_hand_reveal`.
- `ui_is_cutin_mode_active`: returns draw flag 8 (Ghidra shows void).
- `ui_card_list_picker_undo_selection`: callers pass a row index that is not used.
- `ui_card_yes_no_draw_item`: the two items are the card upright and sideways (position choice, M).

#### Corrections to existing docs

- `ui.md` lists mode 10 as the partner switch; mode `0xc` also exists (popped directly by `ui_close_active_duel_ui_mode`).
- `ui_load_duel_archive` returns the archive buffer once loaded (Ghidra's listing shows `return 0` on the common path, but the early return gives the buffer); callers treat 0 as "not loaded yet".
- The draw command handlers convert engine sides to view sides themselves; the dispatcher passes raw engine values.

#### Open questions (batch 5 (rel_duel_draw command and mode tables, task pool, dialogs, help, options))
- The event number and argument kind of each of the 75 records of `0x098d0180` (table data, not in the decompilation); a dump of the table would map every `ui_cmd_*` handler to its engine event.
- The rows of the mode table `0x098d1f5c` for modes 2, 3, 4, 0xa and 0xc (which functions are enter/draw/update/exit).
- Meaning of the HUD request fields `+0x0c`-`+0x40` and whether `+0x24` is a sound id.
- Duel set-up buffer byte `+0x190` values 2 and 5 (auto-answer/tutorial modes?) and word `+0x854` (disables prompt input).
- The 10-word location list `0x098d0504` used by `ui_auto_submit_action_mask_800`.
- Close test `0x098abfb8` of the flag message and the signal `0x09bde00c`.
- Pad state word `+0x18` (waited for before leaving the options mode).
- The six helper routines of `ui_draw_polyline_frame` (`0x098a7398`-`0x098a7950`) and the list callbacks at `0x098b4acc`, `0x098b5530`, `0x098b5550`, `0x098b5718` are not functions in Ghidra yet.

### Findings from batch 6 (rel_title state machine, wireless, duel set-up, options)

Scope: `rel_title` (load address `0x08e9aa00`), first half by address (`0x08e9aa00`-`0x08ebcc90`, 276 functions): the title state machine, logos/opening movie, title screen and title menu, save check, name entry, tab select, options, the ad-hoc wireless screens (menu, rules, lobby, single/tag duel set-up, card gift), the shared window/menu/list drawing helpers, and the duel set-up builders that leave the module. All addresses are runtime addresses of `rel_title`; registry ids carry the `rel_title:` prefix.

#### Title state machine (correction and extension of `ui.md`)

Globals (module data): state `0x08eea3dc` (s16), pending state `0x08eea3de`, sub-state `0x08eea3e0`, pending sub-state `0x08eea3e2`, step `0x08eea3e4`, pending step `0x08eea3e6`, third level `0x08eea3e8`, pending third level `0x08eea3ea`; draw copies `0x08eea3fc` (state) / `0x08eea3fe` (sub-state); per-state frame timer `0x08eea3d8`; global frame counter `0x08eea3d4` (wraps at 0x10000); fade state `0x08eea400` (0 idle, 1 fading, 2 finished); pad state pointer `0x08eea414`; module heap `0x08eea404`; flag byte `0x08eeda48` (bits 0-1 cursor blink mode, bit 2 network busy, bit 3 hold pending states, bit 4 library module loaded, bit 5 library module loading).

- `ui_title_request_state*` start a fade (`ui_title_start_screen_fade`) and store pending values; `ui_title_apply_pending_state` applies them when the fade reports finished (`ui_title_get_fade_state() == 2`) and bit 3 of `0x08eeda48` is clear. Each of the three lower levels has its own pending word: `0xfff` = keep, `0xffe` = increment, anything else = new value. The pending state `0x08eea3de` is `0xfff` for "no state change"; any other value is entered through `ui_title_enter_state(state, sub_state)`. (`ui.md` mentions only state/sub-state; the step and third level work the same way.)
- `ui_title_start_screen_fade(kind, type, color, frames)`: kind 0/1 fade in/out black, 2/3 white, 4/5 custom colour. It refuses while a fade runs and always resets the pending state to `0xfff`.
- `ui_title_update_state` returns the module result: normally the state, `0x2e` when the module leaves for another scene.

State numbers (`ui_title_enter_state`, `ui_title_update_state`, `ui_title_draw_state`; high confidence, read from the switches):

| State | Screen / action |
| --- | --- |
| 0 | boot load (sound banks, save request 1, card info) |
| 2 | resource load (title archive in the save's language, menu context) |
| 3 | logos (pages 1-3, skip with Start/confirm; `0x08eeda50` = already seen) |
| 4 | opening movie `movie/TF3_opening_a.pmf` (played synchronously from the draw step with a 0x500000-byte work buffer) |
| 5 | title screen (press start, title menu, continue/new game) |
| 6 | external cards |
| 8 | name entry |
| 9 | main menu |
| 0xb | communication menu |
| 0xd | minigame menu |
| 0xf | ad-hoc wireless |
| 0x10 | options |
| 0x13 | partner deck select |
| 0x14 / 0x15 / 0x16 / 0x18 / 0x19 / 0x1a | recipe viewer / character list / card album / tutorial list / duel record / limit list |
| 0x1d, 0x1e | character list select |
| 0x21 | tab select (leads to state 0x24) |
| 0x22 | language select |
| 0x29 | save check |
| 0x2c | deck tutorial |
| 0x2d | boot language |
| 0x2f | partner menu |
| 0x30 | minigame result (loads archive slot 3) |
| leaving states (return `0x2e`) | 0x12 scene 4 (deck editor), 0x17 scene 0x1e (gallery), 0x1b/0x1c story (scene 2, `save_set_story_cycle`), 0x1f new game (scene 2), 0x23 random demo duel, 0x24 duel set-up mode 3, 0x25 communication duel, 0x26 wireless duel, 0x27 scene 0x17, 0x28 scene 0x1b (UMD swap), 0x2a scene 0xe with soft-reset inhibit, 0x2b duel set-up mode 2 |

The numbers that `ui.md` gives for the library modules ("recipe viewer 0x1b, charalist 0xd, card album 0xc, duel record 0x14, limit list 0x18, tutorial list 0x21, deck tutorial 0x12") are module ids (`system_module_load`; the wireless code loads the character list as module 0xd), not title states; the title states are in the table above. Correction for `ui.md` (medium for the module ids other than 0xd).

As decompiled, `ui_title_update_state` case 0x2f has no `break` and falls into the 0x30 update (hypothesis, medium; check the disassembly).

`ui_title_switch_scene(scene, arg)` = clear the scene frame callbacks, loading overlay on, wait a frame, `system_scene_call(0xd, scene, arg)`.

Title screen (state 5) sub-states: 1-2 press start (random title voice `0x79c2 + rand % 0x1c` when the language is 0; Start/confirm plays layout 1 frames 0x78-0xa4 and fades the press-start colour `0x08eea424` to `0xff404040` over 15 frames with `ui_title_*_color_fade`); after `0x3de` idle frames back to the logos, or to state 0x23 (random demo duel) when bit 2 of `0x08eeda48` is set; 3 open menu; 4 title menu (`0x08eeac84`, items: 0 new game -> name entry, 1 continue -> sub-state 5, 2 -> sub-state 9, 3 external cards; item count byte is 2, so items 2-3 look unreachable, hypothesis medium); 5-6 continue load (save request 4; on a language change the title archive is reloaded); 7 new-game confirmation box; 8 save probe; 0xb new game. Layout 0 loops frames 100-1099.

Save check (state 0x29): load (save request 2) -> prompt (title_msg 0x36, two choices) or notice (0x37) -> write (save request 6) or back to the main menu with `0x08eeac74 = 7` -> state 0x2a.

#### Title resources (extractor-relevant)

- Archive slots: buffers at `0x08eeda20 + 4 * slot`, paths from the 0x40-byte array at `0x08ee5bb0` (rel_title `+0x4b1b0`): slot 3 = the minigame result archive, slots 4-9 = `title_menu_<l>.ehp` for language 0-5 (`j e g f i s`); the language index is `0x08eeda14`, the language chosen on the continue path `0x08eeda18`. Loaded from root 3 with `container_load_file`; the completion callback binds the archive and increments the sub-state.
- Layout slots: `.ehf` pointers at `0x08eea484 + 4 * slot`, names from the 0x40-byte array `0x08ee5e30` (`main_title01.ehf`, ...); slot 0 title background, 1 press start, 4 deck tab, 5/6 tab-select/name-entry backgrounds, 7/8/10 wireless backgrounds, 0xb-0xd wireless set-up, 0xe/0xf/0x10/0x12 menu bars, 0x11 name entry. Frames are driven by `ui_title_set_layout_range` (mode 0 holds a frame, 1/2 play a range).
- Image records (logos, list bars): 0x98-byte records at `0x08ee7510`: `+0x04` GIM name, `+0x84/+0x86` screen x/y, `+0x88/+0x8a` buffer size, `+0x8c/+0x8e` texture u/v, `+0x90/+0x92` texture extent, `+0x94/+0x96` draw size.
- Sprite records: 0x16-byte records at `0x08ee4d70`: `+0x01` index into the 0x40-byte GIM name array `0x08ee62f0`, `+0x02/+0x04` offset, `+0x06/+0x08` size, `+0x0a/+0x0c` texture u/v, `+0x0e/+0x10` piece size / extent, `+0x12/+0x14` draw size. Nine-slice frames use 9 consecutive records from a style index (0x1e, 0x28 cursor, 0x46 bars, 0x49, 0x4b and 0x54 coloured cells, 0x5d); the scrollbar uses records 0x31-0x3a; tabs 0xc-0x1b; menu icons record 0x4a (14 icons per row, icons 1-6 animated in 3 frames of 10).
- GIM members named in code: `e3_end_00.gim` (logo page 3), `d_menu01.gim` (character grid cells), `menu_opt01.gim` + further `menu_opt*` names at `0x08ee5728` (options, indexed by the options mode), face sheet = GIM name 0x14 (40 x 40 tiles, 12 per row).
- Message tables: `ui_title_get_message(index, table)` with table 0 `title_msg`, 6 `option_msg`, 12 `tushin_msg`, 18 `duelmenu_msg` (`ui.md`). Indices 1 and 3 of every table are printed with `swprintf` and the name of card `0x08eec1c4` into `0x08eeda60`. Options text is read separately from `option_msg_<l>.bin` in the options archive (name array `0x08ee58f8`). Movie: `movie/TF3_opening_a.pmf` (string `0x08ee4afc`, both language branches use it).

#### Shared UI records

- Title list menu (`ui_title_init_list_menu`, e.g. title menu `0x08eeac84`): `+0` state (0-1 opening, 2-3 input, 4-5 closing, 6 cancelled, 7 finished), `+3` state after a direct selection, `+4` open style (2 = staggered fade), `+5` close style, `+6` cancel style (4 = cancel disabled), `+8` item count, `+0x0a/+0x0c/+0x0e/+0x10` fade frames/stagger/elapsed/total, `+0x14` per-item fade colours, `+0x3c` per-item flags (1 = disabled), `+0x46-+0x4c` x, y, width, spacing, `+0x55` cursor, `+0x57` bit 0 wrap / bit 1 use repeat input, `+0x60-+0x70` colours, `+0x74` bits 0-5 blink counter, bits 6-7 blink kind, `+0x75` held flag, `+0x7c` item draw callback. `ui_title_update_list_menu` returns the item, -1 running, -2 cancel, -3 idle. Sounds: 0x7a04 move, 0x7a05 confirm, 0x7a06 cancel, 0x7a07 refused.
- Title list-window record (0x34 bytes; shared instance `0x08eea984`, others `0x08eeac08`, `0x08eeac3c`): `+2..+8` rectangle, `+0x0a/+0x0c` cell gaps, `+0x10` colour, `+0x18/+0x19` frame style/variant, `+0x1a` flags (bit 0 no frame, bit 2 no cursor, bit 3 no cell frames, bit 5 no scrollbar), `+0x1b` absolute index, `+0x1c` cursor, `+0x1d` count, `+0x1e` visible, `+0x1f` columns, `+0x20` text alignment, `+0x22..+0x28` cell origin and size, `+0x2c` text, `+0x30` cell callback.
- Generic title menu (`ui_title_init_menu`, instance `0x08eea8f4`): four 0x24-byte tabs at `+0` (rect, piece style and art in `+10`, colours, callback `+0x20`), list window at `+0x90`, BOOT list window (list box) at `+0xc4` (0x120 bytes), flags `+0x304` (bits 0-1 kind 1 tabbed / 2 panel, bit 2 list box), rectangle `+0x306`, current tab `+0x30e`, tab count `+0x30f`, header callback `+0x310`.
- BOOT list window used as message box (`0x08eea594`, `0x08eea6b4`, 0x120 bytes): `+0x54` frame style, `+0x58/+0x5a` position, `+0x6c/+0x6e` size, `+0x84` text, `+0x90-+0x96` margins, `+0x98` font size, `+0xa0`, `+0xac/+0xb0`, `+0xc4` heap, `+0xc8-+0xca` flags (low nibble of `+0xca` = button set), `+0xcc` choice count, `+0xd3` default choice nibble, `+0xd4`, `+0xe9` state (6 = closed), `+0xfc`/`+0x100`/`+0x10c` callbacks (offsets of the title defaults; the BOOT layout is in `ui.md`/`functions/ui.md`).
- Popup message state: `0x08eea3ec` (0 closed, 1 opening, 2 waiting, 3 closing), result `0x08eea3ee`, current table/index `0x08eea3f0/0x08eea3f4`.
- Cursor: `ui_title_draw_pulsing_cursor_frame` grows 1-2 pixels every 8 frames; blink mode (bits 0-1 of `0x08eeda48`, counter `0x08eede62`) shows it 2 of every 4 frames while a choice is processed.

#### Duel set-up writers (leave for scene 6)

All fill `deck_get_duel_setup_buffer()` (0x858-byte block, `deck.md`) and call `ui_title_switch_scene(6, 0)`:

| Function | `+0x190` mode | Notes |
| --- | --- | --- |
| `ui_title_start_random_deck_duel` (state 0x23) | 5 | Demo duel: 8 (character, recipe) pairs at `0x08ee4b70`/`0x08ee4b90`, shuffled; first two used; BGM set 3 or 1 at random. |
| `ui_title_start_duel_type_3` (0x24, from tab select) | 3 | `+0x193` = item chosen in the tab-select list, BGM set 3; decks not loaded here. |
| `ui_title_start_duel_type_2` (0x2b) | 2 | `+0x193 = 0x08eeac74 - 8`, single, BGM set 1. |
| `ui_title_start_comm_duel` (0x25) | 1 or 6 | From the communication rules `0x08eebfdc-0x08eebfde`; external decks from `0x08eed614/0x08eed6d4` (+0x100 per duellist). |
| `ui_title_start_wireless_duel` (0x26) | 1 | Fixed seed `+0x188 = 0x7b`, first player 0, recipe code 462 with the exchanged decks: every console builds the same set-up (high). |

Header fields confirmed: `+0x188` seed, `+0x18c` first player (rand & 1), `+0x191` 1 or 2 (2 when rules bit 7, "match", is set; side deck counted then), `+0x192` 1 single / 2 tag, `+0x194` BGM set, `+0x195`, `+0x196` LP setting (`ui_title_map_rule_to_duel_setting`: rule 0->1, 1->2, 2->0, 3->3, 4->4), `+0x197` time setting, `+0x1a0` = 0. Duellist record fields written: `+0x00` character, `+0x02` variant, `+0x04/+0x06` second pair, `+0x08` recipe or code (462 keep, 463 stored deck `+0x0a = n - 1`, 465 current deck, 466 own slot), `+0x0c` team/side (wireless), `+0x18` name (ruby stripped), `+0x4a` deck name, `+0x8c` deck. In the wireless duel the set-up's first 0xc0 bytes get the local player's deck and the next 0xc6 bytes save state `+0x162bc` (owned counts, hypothesis medium) or 99 halfwords of 4.

#### Ad-hoc wireless (state 0xf)

Sub-states: 0 intro (tushin 0x15), 1-2 `system_net_init`, 3 connecting, 4 room list, 5 host rules, 6 host lobby, 7 guest lobby, 8 single-duel set-up, 9 tag-duel set-up, 0xe card trade, 0xf trade card select, 0x10-0x13 card gift rooms, 0x14-0x16 teardown, 0x17 done. Steps inside each screen follow one pattern: 0-1 init, 2-3 fade, 4-5 menu bar layout 0xf, 0xb input, 0x14 message box, 0x1c back, 0x1e next sub-state, 0x1f/0x20/0x22 waiting for the fade; sub-screens of the set-up use steps 0x23 (external decks), 0x24 (deck select), 0x25 (character grid), 0x26 (partner pick) with the third level as their own step.

Data (high for the layouts, read from the code):

- Rules record `0x08eebfdc` (0x14 bytes): byte 0 bits 0-2 game kind (0 duel, 2 card trade, 1/3/4 card-gift variants), bits 3-4 room state, bits 5-6 single (0) / tag (1), bit 7 match; byte 1 (`0x08eebfdd`) bit 0 custom LP, bits 1-4 LP setting; byte 2 (`0x08eebfde`) low nibble time setting; `0x08eebfe8` host name pointer, `0x08eebfec` room text pointer (the limit-list name).
- Lobby block `0x08eead8c` (0x1250 bytes cleared): `+0` u16 entry count; nine 0x14-byte room records from `0x08eead90` (bit fields as the rules byte, `+4` value word, `+6` offered card id, `+8` card name, `+0x0c` host name, `+0x10` room text); `0x08eead84` edited entry, `0x08eead85` local peer index, `0x08eead86`, `0x08eead87` joined room, `0x08eead88` flags (low nibble CPU-partner entry index, bit 4 CPU partner present, bit 5 slots initialised, bit 6 character list open, bit 7 error), `0x08eead89` handshake step.
- Player entries: 0x84 bytes each from `0x08eeae44` (nine; a tenth at `0x08eeb2e8` is the staging entry for deck/character choices): `+0x00` name pointer, `+0x04` text pointer, `+0x08` name (UTF-16), `+0x3a` deck name (0x18 chars), `+0x7a` character, `+0x7c` second character, `+0x7e` deck value, `+0x80` variant (low) / second variant (high), `+0x81` peer (low) / deck kind (high: 0 own deck, 1 recipe, 2 external), `+0x82` state (low: 0 empty, 1 joined, 2 ready, 3 released; high: occupied by the library), `+0x83` slot (low) / claim (high). Network form (`ui_title_pack_wireless_entry`): 0x3a bytes = deck name 0x30, the three words, the four nibble bytes.
- Network library outputs: room list count `0x08eeb36c`, rooms of 0x6c bytes from `0x08eeb370` (`+0x04` host name, `+0x3c` value, `+0x44-+0x48` rule bytes, `+0x4a` text, `+0x6a` card id); member list / host slots at `0x08eeb73c` (100-byte members: `+0x04`, `+0x08` state nibbles, `+0x14` name, `+0x46` text); selected room `0x08eebff0`.
- Packets (`0x08eebacc`, 0x200 bytes; byte 0 type, byte 2 step, byte 3 phase, payload from `+4`): type 1 name (0x14 bytes), type 2 entry (0x7e: byte, the 4-byte slot-claim table `0x08eebac8` (host only), own entry, CPU partner entry), type 3 deck (0xc4: one 0xc0-byte deck). Received decks: `0x08eebcd4 + 0xc0 * peer`, CPU partner deck `0x08eebf14`. The host rebroadcasts its entry when the claim table changes (`0x08eebac4`).
- Handshake (`ui_title_update_wireless_handshake`, step `0x08eead89`): 0 send name, 1 collect names, 2 branch by rules (single 3, tag 4, trade 7), 3 own slot, 4-6 entry exchange and slot claims, 7-10 trade link, 0xc-0xe teams ready, 0xf sync, 0x10-0x11 deck exchange (phase 2), 0x12 done or CPU-partner deck exchange 0x13-0x15 (phases 3/4, tag duel with at most three consoles), 0x16-0x17 final sync, 0x21 complete (the set-up screens then request state 0x26).
- A room in the list is joinable only when its value word is 0x1d or 0x1e (compatibility value, hypothesis medium).
- Card gift (receiving side, sub-state 0x13): when the card's "received" flag (`save_test_card_flag_bit7`) was clear, sets it and adds three copies (`save_change_card_count(card, 1)` three times); a second gift of the same card only shows a message (high).
- Character grid (`0x08eec1ca`, 45 cells of 10 bytes in 9 x 5): `+0` character, `+2` bit 0 present, bits 1-4 variant count, bits 5-8 current variant, `+4..` variant numbers; L/R triggers change the variant.
- External decks from the memory stick (`save_import_*`): records of 0x1c0 bytes (`+0` name 0x40, `+0x100` deck 0xc0) in a heap list `0x08eec3a4`, count `0x08eec3b0`, loaded `0x08eec3b4` (max 0x100), flags `0x08eec3ac`.

#### Options (state 0x10)

Work area (`0x08eea3d0`, 0x3c bytes): `+0` mode (0, 1, 2; selects colours, GIM and hidden rows), `+4` cursor row, `+6` first row, `+0x08` edited settings, `+0x10` backup, `+0x18` "input this frame", `+0x1c` heap, `+0x20` archive, `+0x24` GIM, `+0x2c` animation counter, `+0x30/+0x34/+0x38` text colours. Settings record (8 bytes): byte 0 bit 0 = save setting b0 bit 3, bits 1-2 = b0 bits 4-5, bits 3-4 = b1 bits 3-4, bits 5/6/7 = option flags 0/5/2; byte 1 bits 0-1 = b2 bits 1-2, bit 2 = option flag 4, bit 3 = option flag 3; `+2/+4/+6` volumes 2, 0, 1 (0-15). Rows 0-11 map to these fields in that order; row 2 (volume 2) is always skipped by the cursor and only drawn for Japanese, row 7 is hidden in mode 1. Cancel restores the backup and rewrites it (volumes change live while editing).

#### Name mismatches

- `ui_title_draw_tab_select_caption` draws the list items of the tab-select list (sprite 0x3d and a message per item), not a caption.
- `ui_title_reset_message_box` re-opens a list window (`ui_list_window_reset` + `ui_open_list_window`).
- `ui_title_draw_option_toggle` with `is_switch = 0` draws the cursor bar, not a toggle.
- `ui_title_get_title_message`, `ui_title_call_handle_comm_single_duel_input`, `ui_title_call_draw_option_message`: Ghidra shows `void` returns, but the result of the callee is passed through in v0 and used by the callers (prototypes in rows.tsv give the real return type).
- `ui_title_send_wireless_entry`, `ui_title_update_wireless_handshake`, `ui_title_check_wireless_teams_ready`, `ui_title_collect_wireless_peer_names`: callers pass arguments that the decompiled bodies never read (documented as `(void)`; check the disassembly for hidden uses, low risk).
- `ui_title_start_duel_type_2` / `_3`: names describe the set-up mode (2 / 3), not what the duel is; type 3 is started from the tab select with the chosen list item in `+0x193` (a free-duel opponent list, hypothesis medium).

#### Open questions (batch 6 (rel_title state machine, wireless, duel set-up, options))
- What set-up modes 2, 3 and 6 (`+0x190`) mean to `rel_duel_mgr`, and what `+0x193` selects for modes 2 and 3.
- Which scene 0xe (state 0x2a, after the save check, with soft-reset inhibit) and 0x17 (state 0x27) are.
- Game kinds 1, 3 and 4 of the wireless rules (card-gift room variants; which side sends) and the meaning of the room value words 0x1d/0x1e.
- Whether state 0x2f really falls through into the 0x30 update (decompiler artefact or bug).
- Title menu items 2 and 3 (sub-state 9 and external cards) with an item count of 2: is the count raised elsewhere?
- The meaning of the save option flags and setting bit fields behind options rows 0-11 (names in `option_msg` 1-11; needs the strings or a PPSSPP check).
- `ui_title_draw_wireless_rules_summary` has no caller in this half; check whether a function-pointer table in the second half references it.

### Findings from batch 7 (rel_title menus, library, card trade, mini-game results)

#### Extractor-relevant facts (rel_title, second half)

- title_menu_<l>.ehp members used here: layouts by slot through the 19-name array (slots 4, 5, 6, 7, 0xb-0x12); GIMs by index through ui_title_get_gim_name (8 digit sprites, 0xb-0xe card view), image records 0x23/0x24 (language flags); message tables title_msg, tushin_msg, duelmenu_msg (duelmenu_msg_<l>.bin also read from the duel setup panel archive).
- Duel setup panel archive members: d_menu_partner.ehf and the following names of the 0x40-byte array 0x08ee8c44, d_menu01.gim (array 0x08ee8f1c), kao.gim, karada.gim, TnId.bin plus two companion members (array 0x08ee94ec: index table, offset table, UTF-16 text block).
- Partner menu archive: m_menu_bar01.ehf (array 0x08ee9ab0), d_menu01.gim (array 0x08ee97f0, 11 names, one per language for the caption), strTbl_<l>.bin, common_head.gim, common_body.gim.
- Mini-game menu / result archive (menu context): m_menu_bar01.ehf (array 0x08eea100, 6 names), result_mini01.gim (array 0x08ee9fc0, 5 names), mini_result_<l>.bin (array 0x08ee9d80, 0x12 names of 0x20 bytes).
- Card trade: cardh.cip and cardm.cip opened through card_db_open_cardh_cip / card_db_open_cardm_cip.
- Sprite tables in module data: 0x16-byte sprite records 0x08ee4d70 (+0x0a u, +0x0c v, +0x0e w, +0x10 h), duel menu sprite parts 0x08ee90dc (27 records of 5 halfwords: gim index, u, v, w, h), partner/menu-context part tables listed below.

#### Title state machine: words and conventions (second half of rel_title)

- `0x08eea3dc` state, `0x08eea3e0` sub-state, `0x08eea3e4` step, `0x08eea3e8` third level (used as "rule index", "team/slot choice" and similar); pending copies `0x08eea3de`/`0x08eea3e2`/`0x08eea3e6`/`0x08eea3ea`. `0x08eea3fe` mirrors the sub-state at the end of many update functions. `0x08eea3d8` is a per-screen frame counter incremented by the draw functions.
- Common sounds: `0x7a04` cursor move, `0x7a05` confirm, `0x7a06` cancel, `0x7a07` refusal/buzzer, `0x7a0c` message box opens, `0x7a0d` tab switch, `0x7a7e`/`0x7a7f` setup panel slide in/out, `0x7a81`/`0x7a82` versus layout hits (names from usage; hypothesis, medium).
- Pad words: `system_pad_get_state()` +0 held, +4 pressed, +0xc repeat. Bits used: 0x8 Start, 0x10 up, 0x20 right, 0x40 down, 0x80 left, 0x100 L, 0x200 R, 0x8000 Square; confirm/cancel through `system_get_confirm_button(0/1)`; `0x2000` (Circle) decides the OSK button swap.
- Library modules loaded by `system_module_load` and remembered in `0x08eeda4c`: 0xd character list, 0x1b recipe viewer, 0xc card album, 0x14 duel record, 0x18 limited-card list, 0x21 tutorial list, 0x12 deck tutorial. Loaded flag: bits 4-5 of `0x08eeda48` = 1; bit 5 is set on entering the partner deck selection. `0x08eeda19` = "library module is drawing" flag tested by the `ui_title_draw_*` wrappers.
- The title heap: `system_heap_create(0x08eedfc0, 0xc00000)`, pointer in `0x08eea404`. Work area 0x3bec bytes from `0x08eea3d4` cleared by `ui_title_init_work`.

#### Main menu (state 9)

Main list `0x08eeac84` (9 items, strings title_msg 0x38 + item, 0x39 + item past 0x40). Items: 0 first submenu (2 items, strings 0x29 + item, requests states 0x1b + item; item 0 disabled until bit 0 of the save partner field is set); 1 state 0xb (communication duel); 2 deck submenu (strings 0x4b + item; 0 -> state 0x12 deck editor, 1 -> 0x13 partner deck select, hidden when no character deck exists, 2 -> 0x14); 3 state 0xd (mini-games; disabled when none is unlocked); 4 database submenu (9 items, strings 0x42 + item; states 0x15, 0x16, 0x17, 0x18, 0x19, 0x1a, 0x28, 0x29, 6); 5 state 0xf (wireless); 6 state 0x10 (options); 7 sub-state 10 (save, `save_open(5)`); 8 state 0x22; cancel -> state 5. Sub-state 0xf is the PSID warning shown when `save_psid_checksum_changed()`; the requested sub-state is parked in `0x08eea3f8` (bit 0 of `0x08eea3fa` = return there).
Return cursors: library modules re-enter the main menu with sub-state 7 (database) or 5 (deck) and put the submenu cursor in `0x08eeac74` (card album 1, tutorial list 3, duel record 4, limit list 5, recipe viewer 2, partner deck 1).

#### Language selection (state 0x2d at boot, from options otherwise)

Five items (title_msg 0x31, 0x33, 0x32, 0x34, 0x35); the chosen language is item + 1, so the European build offers languages 1-5 (e/g/f/i/s in the archive path table) and never 0 (Japanese). Boot flow (`0x08eedfbc`): 1 autoload (`save_open(3)`; result 2 = save found -> its language, 3 = no save -> step 2), 2 load the language archive, 3 run the selection. Changing language outside boot reloads `title_menu_<l>.ehp` and the card info (`card_db_load_cardinfo` / `card_db_bind_cardinfo`).

#### Name entry (state 8) and the on-screen keyboard

Sub-state 1 confirm screen, 2 OSK, 3 save (`save_open(5)`). The name is accepted when any of its first 8 UTF-16 characters is not a space (0x20 or 0x3000). The OSK wrapper (`ui_title_start_osk` / `ui_title_update_osk`, block `0x09aedfcc`, params at `0x09aedfd0`) escapes '$' by doubling it in both directions; OSK language comes from the halfword table `0x08ee8c38` indexed by the save language.

#### External card import (state 6) and external decks

`save_import_*` scans another save: kind 0 = cards (0x44-byte records: 0x40-byte name, u16 card id +0x40, flag byte +0x42 bit 0 = not importable), kind 1 = decks (0x1c0-byte records: 0x40-byte name +0, 0x100-byte deck +0x100 whose first 0xc0 bytes are the card block). Importing a card sets save card flag bit 7 (once per card) and adds three copies. Buffers: cards `0x08eec3a8`, decks `0x08eec3a4`, counts `0x08eec3b0`/`0x08eec3b4` (decks capped at 0x100), state in bits 1-4 of `0x08eec3ac` (3 allocated, 4 loaded).

#### Deck selection lists (communication / wireless)

Three lists of 6-byte entries: stored decks `0x08eec3f8` (0x33 entries: entry 0 = current deck, 1..0x32 = `save_get_stored_deck(i - 1)`, name at +4, date at +0x44 (5 halfwords y/m/d/h/min), cards at +0x54), recipes `0x08eec52a` (up to 0x1ce: u16 bits 0-1 validity, bits 2-11 ordinal, +2 recipe id, +4 owner character), external decks `0x08eecffe` (0x100 entries). Validity comes from `deck_check_deck_valid` (0 invalid -> dark overlay, 1 valid, 2 shown blue with a hint). Tabs exist only for the player (character 1) and character 0x2e; other characters list up to 10 recipe ids from their save record.

#### Duel setup panel (`0x09aee300`, 0x98 bytes)

+0 heap, +4 layout archive, +8 counter, +0xc phase (0 fade, 1 fading, 2-8 slide/loop/exit), +0x10 net-active byte, +0x11 mode (1 single, 3 tag team, 4 tag slots, 5-7 wireless, 8-10 versus/start screens), +0x12 flag (scene 6 called from 2), +0x14 four 0x18-byte slots {+0 character, +2 variant, +4/+6 shown character/variant, +8 deck type (0 stored, 1 recipe, 2 external, 3 given), +0xa deck id, +0x10 name ptr, +0x14 deck name ptr}, +0x74 frame timer, +0x7c four layout pointers. Layout names: 0x40-byte array at `0x08ee8c44` starting with `d_menu_partner.ehf`. Faces: `kao.gim` and `karada.gim` from the panel archive; generic characters 0x79-0x8d use fixed 0x33 x 0x54 cells, others take three bytes from `world_get_character_model_ids`.
Duel setup buffer (`deck_get_duel_setup_buffer`): +0x191 == 2 adds layout 3, +0x192 = 1 single / 2 tag, player records of 0x1ac bytes from +0x1a4 (character, variant, two halfwords, deck +8, peer index +0xc, name +0x18, deck name +0x4a).

#### Communication duel menu (state 0xb)

Sub-states: 0 load the character list module, 1 fill slots, 2 rules, 3 single duel, 4 tag duel, 5 panel only, 6 character pick, 7 deck selection. Rules are stored in `0x08eebfdc`..`0x08eebfde`: rule 0 bits 5-6 of `0x08eebfdc` (1 = tag; >= 2 sets bit 1 of `0x08eec391` and skips rule 1), rule 1 bit 7, rule 2 bit 0 of `0x08eebfdd` (0 skips rules 3/4), rule 3 bits 1-4 of `0x08eebfdd`, rule 4 bits 0-3 of `0x08eebfde`; index 5 is the summary. Strings are tushin_msg (rule descriptions 0x5c, 0x56-0x59, 0x9c; values from 0x63/0x65/0x67/0x97 + choice). Square on a CPU character slot rolls a random character for 60 frames. Starting a duel requests state 0x25.

#### Library-module states (thin wrappers)

Each library screen has the same three-function pattern: `ui_title_enter_*` requests the module (sub-state 0, pending sub-state 1, loading overlay on), `ui_title_update_*` waits for `system_module_all_loaded`, starts the module with the title heap, updates it every frame and on its exit code unloads the module and re-enters the main menu, and `ui_title_draw_*` calls the module's draw while `0x08eeda19` is set. Deck tutorial returns to the tutorial list (state 0x18) with the tutorial as initial selection; the tutorial list launches state 0x2c for tutorials 0-7 and 0x2b for 8+ after passing the selection to BOOT `system_set_word_08ac2574`. The limited-card list can jump to the deck editor (state 0x12, sub-state 2). The partner deck selection opens the deck editor with sub-state `(character << 8) | 8`. States 0x1d/0x1e pick a character and start the story (`ui_title_start_story(2 or 3, character)`).

#### Options and language

`ui_title_enter_options` creates the options work through `ui_title_create_options_work(heap, title_menu archive, 0)` (first half of the module); options exit returns to main menu sub-state 9, the language selection to sub-state 0xb.

#### Text line (title helper text, `0x09aee180`, 0x180 bytes)

A single-window text renderer created by `ui_title_init_work` (`ui_title_create_text_line(heap, x 0x27, width 0x140, font 0xe, 0, 0)`): window list `0x09aee188`, window descriptor `0x09aee1d4` (0x78 bytes; position (x, 0xd2), size (width, 0x3c), colour black, margins 4/0x14), 3 line records of 0x18 bytes at `0x09aee274` ({x, y, 0, line height, start offset, character count}), text pointer `0x09aee264`, text speed from `save_get_setting_b0_bits4_5` at `0x09aee268`, origin vectors (x, 300.0) and (x, 210.0) at `0x09aee2e8`/`0x09aee2f0`. Line spacing = font line height (1/64 px units >> 6) + 3.

#### Menu context (`ui_menu_ctx_*`, 0x150 bytes)

Shared by the mini-game menu (block `0x09aee30c`, 0x2dc bytes, context at +0x6c, window at +0x1bc), the mini-game result (block `0x09aee308`, 0x2c4 bytes, context at +0x54, window at +0x1a4) and the title (`0x08eede64`). Layout: +0 archive, +0x124 six layout pointers (names: 0x40-byte array `0x08eea100`, first `m_menu_bar01.ehf`), +0x13c five image pointers (names: `0x08ee9fc0`, first `result_mini01.gim`). Strings: member name array `0x08ee9d80` of 0x12 entries of 0x20 bytes starting with `mini_result_j.bin`; callers pass `table_base + language` (0 = mini_result, 6 = the mini-game menu table). Sprite part tables: panel parts `0x08eea280` (4 halfwords u, v, w, h), nine-slice `0x08eea318`, border box `0x08eea360`, three-slice bar `0x08eea3a8`.

#### Mini-game menu (state 0xd) and results

Unlock flags (save progress byte 0xe8 bits 2-7 and 0xe9 bit 6) give seven games; game index -> flag: 0 bit 2, 1 bit 3, 2 bit 4, 3 bit 6, 4 bit 5, 5 bit 7, 6 0xe9 bit 6. Launch table (`ui_minigame_menu_launch_game`): 0 blackjack scene 0xf, 1 dodgeball 0x11, 2 connection 0x13, 3 quiz 0x18 (no opponent), 4 underground 0x15 (no opponent), 5 reversi 0x19, 6 throw 0x1c; games with an opponent first open the character list in mode 5 and pass (character, variant) in the world parameter block. Game names are menu string 0x52 + game index.
Result scoring (`ui_mini_result_apply_score`, game index as above): base DP = score / 50 (0), / 150 (1), score / 2 + ceil(time / 100) when cleared (2), / 10 (3), wins * 20 + flag * 150 (4), / 50 (5), / 10 (6); each new record (save mini-game records 0-8; game 2 uses records 2 and 3, game 4 records 5 and 4, game 3 record 6, game 5 record 7, game 6 record 8) adds 200 DP and sets a marker byte at +0xec.. of the save record table; experience = total DP / 25; a level-up adds 400 DP. Result block fields: +0x1c from-story flag, +0x20 game, +0x24 outcome (2 again, 3 quit; hypothesis medium), +0x28.. six displayed values (score, second score, base DP, bonus, total, experience), +0x40 extra flag, +0x44/+0x46 new-record flags. Value strings are digit glyph strings 0x15.. of mini_result_<l>.bin; game 2's second value is a time in hundredths of a second.

#### Partner menu (`0x09aee304`, 0x1a0 bytes)

+0 heap, +4 archive, +0x10 mode (0 main, 1 OSK), +0x14 step (1 fade-in, 2 intro, 3 input, 4 prompt, 5 fade to OSK, 6 fade back, 7 team-name window, 8 delay 0x1e frames, 9 outro fade, 10 commit), +0x1c counter, +0x20/+0x24 partner character/variant, +0x28 list window (0x120 bytes), +0x150 layouts (names `0x08ee9ab0`, first `m_menu_bar01.ehf`), +0x170 images (names `0x08ee97f0`, first `d_menu01.gim`, 11 entries; image 5 is chosen by language), +0x19c result (2 confirmed, 3 cancelled). Strings: `strTbl_<l>.bin` (names `0x08ee9670`) 0x43 help, 0x44 team-name prompt, 0x45 OSK prompt. The default team name is "player name + separator + partner name kind 2" (max 0x11 characters); Start confirms, the confirm button edits the team name, cancel aborts; commit calls `save_set_partner`. Generic characters (>= 0x2e) use `common_head.gim`/`common_body.gim`.

#### Card trade over ad-hoc (wireless sub-states 0xe trade screen, 0xf card picker)

Resources: module 0x1d (card picker `ui_select_card_*`), `cardh.cip` in a 0x135000-byte buffer and `cardm.cip` in a 0x5e5000-byte buffer (extractor: the trade screen reads card images from both CIP archives; artwork variant per card from `save_get_card_value_bits4_6`), picker heap 0x400000 bytes at `0x09aee310`. Packets: 0x20 bytes at `0x08eebacc` {+0 = 2, +2 = 1, +3 step code, +4 0x1c-byte trade record}; trade record {+0 u16 status, +4 card count (max 5), +8 five u16 card ids, +0x18 selected flag, +0x19 selected index in the other side's list}. Local record `0x08eec05c`, saved copy `0x08eec078`, received own echo `0x08eec094`, peer `0x08eec0b0`. Status codes posted: 0 reset, 1 confirm proposal, 2 leave, 3 re-choose offer, 4 clear selection, 5 select, 6 both selected, 8 accept, 9/10/11 save results, 0xc error, 0xd updated list after exchange. Steps are acknowledged by waiting until the peer echoes the same code (step 0xf retry, 0x11 wait). The exchange is journalled in the save title words (`save_write_title_words(0, given, received)`) before saving and reverted with `save_read_title_words` if the save fails. Trade flags `0x08eec0dc`: bit 0 picker module loaded, 1 card view/cardm open, 2 offer resent, 3 picker heap, 4 peer error, 5 saving, 6 picker gate, 7 picker done.

#### Name mismatches

- `ui_title_draw_text_to_screen_edge` (`rel_title:0x08ec58a4`): used as "draw one digit string at (x, y)" by `ui_title_draw_number_text`; the decompiled body is meaningless (skipped).
- `ui_partner_menu_is_layout_frame_101` / `ui_mini_result_is_layout_frame_101`: the decompiled bodies only read the frame and return nothing usable; no test against 0x65 is visible.
- `ui_title_draw_language_cursor(list, item)`: ignores its item argument and uses the selection byte `0x08eeacdd` (medium).
- `ui_card_trade_set_flags_bit4` / `ui_card_trade_test_flags_bit5_clear`: names describe bits; meaning (peer error, save in progress) inferred from use.
- `ui_title_check_deck_valid_copy`: decompiled as void but returns the validity (used as a 2-bit value by its caller).

#### Open questions (batch 7 (rel_title menus, library, card trade, mini-game results))
- The 20/16/28-byte functions that decompile to a bare `return` while receiving text arguments (`ui_title_deck_draw_text_fit_width_px`, `ui_title_date_draw_text_px`, `ui_title_text_line_draw_text_box_px`, `ui_title_draw_text_fit_width_px`, `ui_title_draw_text_box_px`, `ui_title_draw_text_px`, `ui_stub_noop_partner_menu_print`, `ui_stub_noop_menu_ctx_print`) are probably import stubs to BOOT font functions; read their disassembly / import NIDs.
- Meaning of rule values 0-4 of the communication duel rules (only the string ids are known; rule 0 = 1 means tag duel).
- Which world/save meaning the duel setup panel modes 5-10 have outside the title (modes 8-10 are only reached when the panel is created by other code paths; none of the callers in this half passes them).
- `0x08eea424`/`0x08eea428` are reset to -1 by every enter function; their use is in the first half.
- What sets the partner menu's OSK flag +0x148 to 1 and who advances name-entry step 1 -> 2 (not in this half).
- The OSK parameter block field at `0x09aedfec` (result) and the halfword language table `0x08ee8c38` contents.

## Open questions

- Which menu state uses which of the 41 `rel_title` functions that read `tushin_msg`, and the selector `k` of the 25 `ui_title_get_message` calls whose table is chosen at runtime (a PPSSPP breakpoint on `0x08e9cbf0` would give `(index, k)` per screen).
- The duel HUD's `ddstrtbl_<lang>_idx.bin` / `_body.bin` pair: how `rel_duel_draw` indexes it (not through the headed accessor).
- The minigames' shared result helper (`mini_result`) receives its table from the caller's buffer; its indices are constants but the table is only inferred from the archive.
- Whether the unreferenced archives above are really unused (a file-access trace in PPSSPP across all scenes would settle it).
- ~~What `0x0881e6a4` sets up~~: answered 2026-11-04: width and height for the camera-clip path only; the centre floats are unused.
- ~~How `ui_bind_ehf` patches the display lists~~: answered 2026-11-04: it does not; the player reads the primitive records itself, and `ui_bind_ehf` writes each texture slot's `.tmf` byte into slot word `+0x0c` after the texture callback (`ehf.md`).
- ~~Who plays a layout~~: answered 2026-11-04 (batch 1): the caller's draw block word 0 is a tick, the layout advances once per new tick at stage `+0x08` vsyncs per frame, and menus select frame ranges with `ui_ehf_set_play_range` / `ui_ehf_seek_frame`.
- See also the open questions in `docs/formats/ehf.md`.
- From the 2026-11-04 round (details in the per-batch open questions above): the event number of each of the 75 draw-command handlers (table data `0x098d0180`, not code), the `ddstrtbl` index pair, the meaning of the room value words 0x1d/0x1e of the wireless lobby, and a PPSSPP check of the layout timing and of the mini-game scoring formula.
