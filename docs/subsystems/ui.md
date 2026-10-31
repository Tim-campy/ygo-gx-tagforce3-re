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
| `rel_deck:0x08eaa6a8` | `ui_deck_get_resource(id)` | H | 41 records `{u32 id, void *cache, char *format}` at `0x08ebd84c` (module `+0x22e4c`) sorted by id (ids `0x8000+`), searched by `0x08eaa360`; on first use `sprintf(format, "jegfis"[save_get_language()])` (ids `0x8036`/`0x8037` use the region string `"jabgfisb"`), `container_ehp_find_member`, and for an `.ehf` also the `.tmf` (`FUN_08821b70`). The same routine, with its own table, is in `rel_deckswap +0x9c8c`, `rel_decktutorial +0x11324`, `rel_select_card +0xc334`, `rel_recipeviewer +0x5ad4` (id `0x8033` = `strTbl.bin`) and `rel_shop:0x090dc228` (`shop_get_archive_member`, 21 records). |
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

## Open questions

- Which menu state uses which of the 41 `rel_title` functions that read `tushin_msg`, and the selector `k` of the 25 `ui_title_get_message` calls whose table is chosen at runtime (a PPSSPP breakpoint on `0x08e9cbf0` would give `(index, k)` per screen).
- The duel HUD's `ddstrtbl_<lang>_idx.bin` / `_body.bin` pair: how `rel_duel_draw` indexes it (not through the headed accessor).
- The minigames' shared result helper (`mini_result`) receives its table from the caller's buffer; its indices are constants but the table is only inferred from the archive.
- Whether the unreferenced archives above are really unused (a file-access trace in PPSSPP across all scenes would settle it).
- What `0x0881e6a4` sets up from the screen-size arguments (probably the stage-to-screen mapping).
- How `ui_bind_ehf` patches the texture and vertex placeholders of the display lists, and how callback `0x088227d0` finds a texture.
- Who plays a layout (frame stepping, looping, jumping to labels or frames) and how menus drive it; there are no frame labels or actions in the format.
- See also the open questions in `docs/formats/ehf.md`.
