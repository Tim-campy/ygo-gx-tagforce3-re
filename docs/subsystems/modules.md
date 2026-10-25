# Game modules (`gmodule/`, `module/`) and how they are loaded

The game is split into `BOOT.BIN` (the resident core: runtime library, file system, rendering, card database, save, the exported library `libehsys_rel`) and 36 relocatable PRX modules in `PSP_GAME/USRDIR/gmodule/`. A 37th PRX, `USRDIR/module/libfont.prx`, is Sony's font library. This document lists the modules, their roles, and the loader in `BOOT.BIN`. Addresses are absolute in `BOOT.BIN` (base `0x08804000`); module offsets are unrelocated (`+0x0`).

```
python3 -I tools/modules.py list <SYSDIR>/BOOT.BIN <USRDIR>/gmodule <USRDIR>/module --check
python3 -I tools/modules.py table <SYSDIR>/BOOT.BIN --present <USRDIR>/gmodule <USRDIR>/module
python3 -I tools/modules.py base ghidra/symbols.sym <USRDIR>/gmodule      # about one minute
python3 -I tools/tests/test_modules.py
```

`list` prints each module's sections, module info, exports and imports, and which provider resolves each import library. `--check` fails if a game-library import does not resolve. Today all 36 ELF modules resolve all of their `libehsys_rel` imports against `BOOT.BIN`, and all of their `lib*_rel` imports against the module that exports that library. `table` finds the module descriptor tables in `BOOT.BIN`. `base` votes runtime bases (see below).

## File format

The 36 `gmodule/` files are plain ELF (`e_type 0xffa0`, relocatable PRX). Each has `.text`, `.sceStub.text`, `.lib.ent`, `.lib.stub`, `.rodata.sceModuleInfo`, `.rodata.sceResident`, `.rodata.sceNid` and `.data`, plus `.rel.*` relocation sections. All have module attribute `0x0000` and version 1.1.

- **Imports.** Every module imports all 1,556 `libehsys_rel` functions from `BOOT.BIN`, so the import list says nothing about the module's role. The calls that are actually made (`jal` to a stub) do. `libehsys_rel` has 1,556 function entries but only 1,530 distinct NIDs. 68 of its entries point at `BOOT.BIN`'s own import stubs (for example `sceIoOpen` at `0x0887243c`), under the Sony NIDs. In effect `BOOT.BIN` re-exports part of the firmware API. This is why a module's `IoFileMgrForUser`/`ThreadManForUser`/`sceUmdUser` NIDs also appear in `libehsys_rel`.
- **Exports.** The module's own `(module)` library exports 0 functions and 2 variables (module info and SDK version). There is no `module_start` NID, so the kernel starts the module at the ELF entry point `e_entry`. Each module also exports `lib<name>_rel`. In 13 modules that library holds 0 functions; in the others it is the interface other modules call (table below).
- **Module-info names** are `mod<name>`, with three exceptions: `rel_cutin_viewer` and `rel_movie_viewer` are both `modtemplate` (they export `libtemplate_rel`), and `rel_html_view` is `module_htmlview`.
- **`module/libfont.prx`** is encrypted (`~SCE` header, then `~PSP` with name `sceFont_Library`, attribute `0x0006`, compressed, `elf_size` 37,258). The tool only reads that plain header; the module is not decrypted.

## Load mechanism

Two loaders sit on top of one asynchronous file thread.

### Module descriptor tables (`BOOT.BIN`)

There are two tables of 16-byte records `{u32 id, s32 root, char *name, u16 kind, u16 utility_id}`, each ended by a zero record:

- `0x0889f57c`: Sony modules, ids 1–7: `libfont.prx` (root -2, kind 0), `videocodec.prx` (kind `0xffff`), `audiocodec.prx` (kind 4, utility `0x0300`), `mpegbase.prx` (kind `0xffff`), `mpeg.prx` (4, `0x0303`), `libatrac3plus.prx` (4, `0x0302`), `sc_sascore.prx` (4, `0x0301`).
- `0x0889fea4`: game modules, ids 8–0x31, all root 2 (`gmodule/`), kind 0. There are 42 names. Six of them are not on the disc: `rel_sdchrviewer` (0x1c), `rel_blackjack_starter` (0x23), `rel_dodge_starter` (0x25), `rel_connection_starter` (0x27), `rel_underground_starter` (0x29) and `rel_reversi_starter` (0x2d).

Root indexes refer to the path table at `0x0889fb24`, which `0x0881d574` installs as the root table `*0x08920cac` (see `container.md`): 0 `disc0:/PSP_GAME/USRDIR/module/`, 1 `…/kmodule/` (absent from the disc), 2 `…/gmodule/`, 3 `…/USRDIR/`, 4 `…/duel/`, 5 `…/duelsys/`, 6 `…/main/`, 7 `…/snd/`, 8 `…/minigame/`. The boot configuration at `0x088a0154` begins `{0x0889fb24, 1, 0, …}`. `0x08827c54` replaces root -1 with 1 and root -2 with 0.

Kind (jump table at `0x08878b74`, index `kind + 1`):

| Kind | Action |
| --- | --- |
| 0 | Load from disc through the file thread. |
| 4 | `sceUtilityLoadModule(utility_id)`. |
| 1–3, `0xffff` | Nothing; the entry is marked loaded. |

### Module registry (libraries, reference counted)

At boot, `0x08833734` calls `0x0881d1a8` → `0x08827c54`, which registers the Sony table. It then calls `0x08827f4c(0x0889fea4)`, which registers the game table. The registry is an array of 76-byte entries at `0x089235b4`, with its count at `0x089248b4`. `0x08827f4c` sorts the array by id with `qsort`, and lookups use `bsearch` (`0x08828144`).

| Offset | Field |
| --- | --- |
| `+0x00` | Id. |
| `+0x04` | Root. |
| `+0x08` | Module UID. |
| `+0x0C` | State: 0 unloaded, 1 loading, 2 loaded. |
| `+0x10` | Reference count. |
| `+0x14` | Name (32 bytes). |
| `+0x34` | Kind. |
| `+0x38` | Utility id. |
| `+0x3C`–`+0x48` | Arguments passed to `sceKernelStartModule`. |

| Address | Name (proposed) | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x08827cec` | `system_module_load(id)` | H | Calls `load_ex(id, 0, 0, 0x089248b8, 0)`. Exported. |
| `0x08827d04` | `system_module_load_ex(id, argsize, argp, status, opt)` | H | Increments the reference count. If the state is 0, switches on kind: kind 0 calls `0x0881d9fc(root, name, 0x08828180, entry)`, kind 4 calls `sceUtilityLoadModule`. Exported. |
| `0x08828180` | `system_module_on_loaded(entry, uid)` | H | Load callback: stores the UID, calls `sceKernelStartModule(uid, args…)`, sets state 2. |
| `0x08827e60` | `system_module_unload(id)` | H | Decrements the reference count. At 0: `sceKernelStopModule` + `sceKernelUnloadModule` (kind 0) or `sceUtilityUnloadModule` (kind 4). Exported. |
| `0x08827e18` | `system_module_all_loaded()` | H | Returns 0 while any entry has state 1. Callers poll it after a load. Exported. |
| `0x08828068`, `0x088280d8` | `system_module_get_basename(id)`, `…_get_filename(id)` | H | Copy the name without/with `.prx` to `0x089248c0` / `0x089248e0`. Exported. |

Library modules are loaded through the registry, either by `BOOT.BIN` or by other modules through the exports:

- `0x0882b834` loads ids 2–5 (video playback) and `0x0882b874` unloads them.
- `0x088415f4` loads ids 3, 7 and 6 at boot (audio) and waits for them.
- `rel_title` loads 0x0d, 0x1b, 0x0c, 0x14, 0x18, 0x21 and 0x12.
- `rel_duel_mgr` loads 8 (`duel_eng`), 9 (`duel_draw`, with `argsize 4`), 0x0a (`deckswap`) and 0x0b (`tutorial`).
- `rel_duel_draw`, when it runs as a scene, loads 8.
- `rel_underground` loads 0x13 (`duel_mgr`, `argsize 1`).
- `rel_story`, `rel_labo` and `rel_conv_machine` load ids computed at runtime.
- `rel_deck` bypasses the registry. It gets the file names of ids 0x1b and 0x12 from `0x088280d8`, queues them with `0x0881d9fc`, and starts and stops them itself through the re-exported `sceKernelStartModule`/`StopModule`/`UnloadModule`.

`libfont.prx` (id 1) is not loaded through the registry. At boot, `0x088453e4` loads it directly with `0x0881d9c4(0, "libfont.prx")`, starts it, and calls `sceFontNewLib`. `0x088456f4` unloads it.

### Scene slot (`ehscript` thread, one scene at a time)

Screens ("scenes") are modules that run in one slot, served by the thread `ehscript`. The slot state is at `0x08920be4` (100 bytes):

| Offset | Field |
| --- | --- |
| `+0x00` | Root. |
| `+0x04` | Requested name (32 bytes). |
| `+0x24` | Current name. |
| `+0x44` | Start callback. |
| `+0x48` | End callback. |
| `+0x4C` | Third registered word. |
| `+0x50` | Module UID. |
| `+0x54` | Static function. |
| `+0x58` | State. |
| `+0x5C` | Thread. |
| `+0x60` | Thread to wake. |

| Address | Name (proposed) | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x0881ce04` | `system_scene_init(name, root, static_fn)` | H | Clears the slot, requests `name` (or a static function), creates thread `ehscript` (`0x0881d028`) at the current priority + 1. Boot calls it with `("rel_title", 2, 0)` at `0x08833878`. |
| `0x0881d028` | `system_scene_thread` | H | State machine. 1: queue a load of the requested name via `0x0881d9fc` (or call the static function for `"staticmodule"`). 2: when the UID arrives (`0x0881d18c`), `sceKernelStartModule`, record the name, state 5, call the start callback. 5: when a new name is requested, call the end callback, then `sceKernelStopModule`/`UnloadModule`, then back to 1. |
| `0x0881cf54` | `system_scene_register(start, end, x)` | H | Writes `+0x44/+0x48/+0x4C`. Called from the entry point of every scene module. Exported. |
| `0x0881cf74` | `system_scene_request(basename)` | H | `strcpy(+0x04, basename); strcat(".prx")`. Exported. |
| `0x0881cf00` | `system_scene_run_slice()` | M | Main thread: `sceKernelResumeThread(ehscript)`, `sceKernelSleepThread`, `sceKernelSuspendThread`. Called once per main-loop iteration at `0x088338ac`. The scene code thus runs as a coroutine of the main loop. |

Scene transitions use a scene id, not a module id. The scene table at `0x088a1478` (31 × `{u32 scene, u32 module_id}`) is mapped by `0x0883dbb0`; an unknown id returns the string `"unknown id"`. The stack is a 144-byte structure returned by `0x0883596c`: `+0` depth, `+4` current transition `{u16 type, from, to, arg}`, `+0x0C` stack of 8-byte transitions.

| Address | Name (proposed) | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x0883dc54` | `system_scene_call(from, to, arg)` | H | Pushes `{1, from, to, arg}` and requests `to`'s module. Exported. |
| `0x0883dcd8` | `system_scene_return(from, arg)` | H | Current = `{2, from, caller, arg}`; pops; requests the caller's module. Every scene module calls it with its own scene id. Exported. |
| `0x0883dddc` | `system_scene_jump(from, to, arg)` | H | Clears the stack, current = `{3, from, to, arg}`. `rel_duel_mgr` jumps to scene 0x0d (title). Exported. |
| `0x0883dd4c` | `system_scene_get_caller(scene)` | M | `from` of the top entry if its `to` is `scene`, else 31. Exported. |
| `0x0883dda8` | `system_scene_get_transition(buf)` | M | Copies the current 8-byte transition. Exported. |

Scene → module table:

| Scene | Module |
| --- | --- |
| 0, 1, 0x0c | `debug_menu` |
| 2 | `story` |
| 3 | `duel_draw` |
| 4 | `deck` |
| 5 | `field` |
| 6 | `duel_mgr` |
| 7 | `shop` |
| 8 | `sdchrviewer` (missing) |
| 9 | `labo` |
| 0x0a | `movie_viewer` |
| 0x0b | `cutin_viewer` |
| 0x0d | `title` |
| 0x0e | `html_view` |
| 0x0f / 0x10 | `blackjack` / `_starter` (missing) |
| 0x11 / 0x12 | `dodge` / `_starter` (missing) |
| 0x13 / 0x14 | `connection` / `_starter` (missing) |
| 0x15 / 0x16 | `underground` / `_starter` (missing) |
| 0x17 | `usb_connect` |
| 0x18 | `quiz` |
| 0x19 | `reversi` |
| 0x1a | `reversi_starter` (missing) |
| 0x1b | `umd_replace` |
| 0x1c | `throw` |
| 0x1d | `throw_starter` |
| 0x1e | `gallery` |

The own-scene argument that each module passes to `system_scene_return` matches this table for all 19 modules that call it.

A scene module's `e_entry` calls `system_scene_register(start, end, x)` and returns 0. A library module's `e_entry` is `jr ra; li v0, 0`. `rel_duel_draw` is both: its entry registers itself as a scene only when started with `argsize <= 0`, that is, as scene 3 and not when `rel_duel_mgr` loads it as a library with `argsize 4`. `rel_field` (scene 5, and `libfield_rel` for `rel_story`) and `rel_duel_mgr` (scene 6, and `libduel_mgr_rel` for `rel_underground`) are dual-use in the same way.

### File thread

`0x0881d9fc(root, name, callback, arg)` queues a request with type 1 in the 32-entry, 0x60-byte queue at `0x08920cac + 8`. This is the same queue that `container_read_async` (`0x0881d7b8`) uses with type 0. The file thread `0x0881dba0` takes requests one at a time. For type 1 it calls `0x0881d9c4(root, name)` = `container_resolve_path` + `sceKernelLoadModule(path, 0, NULL)` (the only `sceKernelLoadModule` call site, `0x0881d9e8`), then `callback(arg, uid)`. Loads are therefore serialised with file reads. Modules are loaded with no partition or position option, so the kernel chooses the address.

### Addresses: not fixed overlays

Modules have no fixed load address; they go wherever the kernel's allocator puts them. The PPSSPP export nevertheless shows that the scene slot reuses the same memory. `rel_title` (618/618 function starts) and `rel_duel_mgr` (202/202) both match at `0x08e9aa00`. Their symbols overlap in the export (246 overlapping functions), which only happens if one was unloaded and the other loaded into the freed block. The duel libraries loaded by `rel_duel_mgr` sit higher, at `0x0983fb00` and `0x09be1400`.

## Runtime bases (`ghidra/symbols.sym`)

Method (`tools/modules.py base`):

1. Take the targets of `jal` instructions inside the module's `.text` as function starts. Import stubs are left out: their regular 8-byte layout matches any other module's stub block.
2. For a sample of up to 150 starts and every symbol address, vote `base = symbol − offset`.
3. Score the five best candidates by how many starts land on a symbol.

The method finds the known `rel_duel_eng` base `0x09be1400` with 2,007/2,007 starts; the runner-up has 76.

| Module | Base | Starts matched | Stubs matched |
| --- | --- | --- | --- |
| `rel_title` | `0x08e9aa00` | 618/618 (576 with the size ending at the next start) | 1,592/1,592 |
| `rel_duel_mgr` | `0x08e9aa00` | 202/202 | 2,981/2,981 |
| `rel_duel_draw` | `0x0983fb00` | 1,178/1,180 | 2,916/2,916 |
| `rel_duel_eng` | `0x09be1400` | 2,007/2,007 | 1,556/1,556 |

Every other module reaches at most 6–58 % of its starts. That is the noise level of this export, which is dense around `0x08e9aa00`, so those modules are not in this export. For modules with fewer than about 50 starts (`labo` 8, `throw_starter` 7, `movie_viewer` 10, `html_view` 13), the vote cannot tell a match from noise. The bases are specific to this one session's load order: re-vote with every new export.

Later exports taken on the field map, in the deck editor and in the shop (`ghidra/mapa.sym`, `loja.sym`; the deck-editor and dormitory exports are byte-identical to the map one) add:

| Module | Base | Starts matched |
| --- | --- | --- |
| `rel_story` | `0x08e9aa00` | 552/552 |
| `rel_deck` | `0x08e9aa00` | 325/325 |
| `rel_field` | `0x090ced00` | 497/497 |
| `rel_shop` | `0x090ced00` | 230/230 |

PPSSPP keeps the symbols of every module loaded so far, so one export holds several modules at the same address. Two slots stand out: `0x08e9aa00` is the scene slot (title, story, deck editor, duel manager) and `0x090ced00` holds `rel_field` or `rel_shop`.

### In Ghidra and in the registry

`rel_duel_eng` (`0x09be1400`), `rel_story` (`0x08e9aa00`), `rel_field` and `rel_shop` (both `0x090ced00`) are imported into `ghidra/TF3.gpr` at these bases. Modules that share an address get module-qualified registry ids (`rel_story:0x08ea63f4`), produced by `ExportFunctions.java <csv> <module>`; `BOOT.BIN` and `rel_duel_eng` keep plain addresses. Their import stubs are named with `tools/prx_imports.py` (`re/names-imports-<module>.csv`); `rel_story`'s 55 imports from other game modules are not resolved by that tool yet.

## Module catalogue

Columns: size in bytes; slot (scene id / registry id); exported library (function count) and which modules import it; role. The evidence is BOOT.BIN calls actually made (names from `re/functions.csv`) and file names referenced (named only). All modules call `card_db_get_dictionary_word` and `container_ehp_find_member` heavily.

| Module | Size | Slot | Exports → importers | Role and evidence |
| --- | --- | --- | --- | --- |
| `rel_title` | 383,556 | scene 0x0d, id 0x20 | — | Title screen, main menu, options. Started by boot by name. Opening movie (`TF3_opening`), `title_menu_<l>.ehp`, option messages. Calls `save_open` ×11 and `card_db_load_cardinfo`. Loads seven library modules (above) and calls `libcharalist_rel` heavily. Base `0x08e9aa00`. |
| `rel_story` | 230,772 | scene 2, id 0x1f | `libstory_rel` (2) | Story mode / event runner: `script/story_scr_*`, `EveB.bin` (`docs/formats/story.md`), staff-roll movies. Drives the field through `libfield_rel` (two functions called 42 and 41 times). Calls scenes 0x0f, 0x11, 0x13, 0x15, 0x18, 0x19, 0x1c (minigames), 4 (deck) and 6 (duel). Imports 12 module libraries. |
| `rel_field` | 253,044 | scene 5, id 0x15 | `libfield_rel` (8) → story | Free-roam field: `bg_NN_MM.tms` map meshes, doors, `body/mouth.ehf` character parts. VFPU-heavy. |
| `rel_duel_mgr` | 164,684 | scene 6, id 0x13 | `libduel_mgr_rel` (7) → underground | Duel session: rock-paper-scissors (`jyanken*`), versus screen, results (`duel/result/result_<l>.ehp`). Loads and unloads `duel_eng`, `duel_draw`, `deckswap`, `tutorial`. Base `0x08e9aa00`. |
| `rel_duel_eng` | 2,939,436 | id 8 | `libduel_eng_rel` (1,360) → duel_draw, duel_mgr, tutorial | Duel rules and card effects (`duel_core.md`, `duel_effects.md`). Network debug strings (`send_type`, `net_id`). Calls `card_db_get_race`, `card_db_is_trap`. Base `0x09be1400`. |
| `rel_duel_draw` | 800,296 | scene 3 or id 9 | `libduel_draw_rel` (49) → duel_mgr, deckswap, tutorial | Duel presentation: 3D duel field, cut-ins (`cutin_*.ehp`), voices (`voice*.vtmt.gz`), duel disk. Base `0x0983fb00`. |
| `rel_tutorial` | 78,500 | id 0x0b | `libtutorial_rel` (13) → duel_mgr | Scripted duel tutorial: `d_tutorial/tutorial/tuto_field_%02d.ydq`, `tuto_cmd_%02d.bin` (`docs/formats/tutorial.md`). Imports duel_eng and duel_draw. |
| `rel_deckswap` | 132,404 | id 0x0a | `libdeck_swap_rel` (3) → duel_mgr, labo | Deck swap/selection between duels: `deck/deckswap.ehp`, deck-editor UI set. Imports duel_draw. |
| `rel_deck` | 196,612 | scene 4, id 0x11 | — | Deck editor: `deck/all_<l>.ehp`, `fileTbl.dat`, `sameCardTbl.dat` (`docs/formats/deck.md`). Loads `recipeviewer` and `decktutorial` itself. |
| `rel_recipeviewer` | 64,444 | id 0x1b | `librecipe_viewer_rel` (3) → deck, story, title | Deck-recipe viewer: `deck_load_recipe`, `deck_get_recipe_name`, OSK. |
| `rel_decktutorial` | 186,844 | id 0x12 | `libdeck_tutorial_rel` (3) → deck, story, title | Deck-building tutorial: `deck/tutorial.ehp`, `deck_tutorial%02d.bin`. |
| `rel_shop` | 181,856 | scene 7, id 0x1e | `libshop_rel` (5) → story | Card shop and pack opening (`docs/formats/packs.md`): `shop/all_<l>.ehp`, pack/box meshes. Calls scene 4. |
| `rel_select_card` | 136,604 | id 0x1d | `libselect_card_rel` (6) → conv_machine, labo, story, title | Card picker: `labo/rental.ehp`, `labo/conv_machine.ehp`, deck-editor UI set. |
| `rel_conv_machine` | 63,400 | id 0x0e | `libconv_machine_rel` (3) → labo, story | Card conversion machine: `labo/conv_machine.ehp`. Uses `select_card`. |
| `rel_cardalbum` | 65,236 | id 0x0c | `libcardalbum_rel` (3) → labo, story, title | Card album: OCG pack name/list tables, album pages. The only module using `sceJpeg` (6 functions; card art is JPEG, `docs/formats/cip.md`). |
| `rel_charalist` | 75,412 | id 0x0d | `libcharalist_rel` (11) → labo, story, title | Character list/profiles: `database/charalist.ehp`, `field/bustup/`, voice test, OSK (team name). |
| `rel_duelrecord` | 46,924 | id 0x14 | `libduelrecord_rel` (3) → labo, story, title | Duel record: `database/duelrecord.ehp`. |
| `rel_limitlist` | 53,164 | id 0x18 | `liblimitlist_rel` (3) → labo, story, title | Forbidden/limited list: `database/limitlist.ehp`, `deck_reset_limits`, `deck_set_limit`. |
| `rel_password` | 44,680 | id 0x1a | `libpassword_rel` (3) → labo, story | Card password entry: `labo/password.ehp`. |
| `rel_tutoriallist` | 35,116 | id 0x21 | `libtutoriallist_rel` (4) → labo, story, title | Tutorial list: `database/tutoriallist.ehp`. |
| `rel_labo` | 37,428 | scene 9, id 0x17 | — | Hub (8 function starts) that loads and unloads the library tools above. Has a voice-test debug view (`ChrID`, `VOICE` formats). |
| `rel_debug_menu` | 52,540 | scenes 0, 1, 0x0c, id 0x10 | — | Debug menu: `printf` formats, `deck_load_recipe`, `save_open`, starts duels (scene 6). |
| `rel_cutin_viewer` | 365,760 | scene 0x0b, id 0x0f | (`libtemplate_rel`, 0) | Cut-in viewer (module info `modtemplate`): same cut-in/duel-disk assets as `duel_draw`. |
| `rel_movie_viewer` | 23,752 | scene 0x0a, id 0x19 | (`libtemplate_rel`, 0) | Movie viewer (`modtemplate`): lists `movie/` with `sceIoDopen`. |
| `rel_gallery` | 46,884 | scene 0x1e, id 0x31 | — | Gallery: `movie/%s.pmf`, thumbnails, `database/gallery/`, `field/event/<l>/`. |
| `rel_html_view` | 24,724 | scene 0x0e, id 0x16 | — | Download over HTTP/SSL (`sceHttp`, `sceSsl`, `sceNet*`, `sceUtility`). A `konami.jp` URL for TF3 EU, and `/PSP/SAVEDATA/`: downloadable content. |
| `rel_usb_connect` | 34,788 | scene 0x17, id 0x2a | — | USB connection (`sceUsb`, `sceIoDevctl`): `database/usb_connect/data.ehp`. |
| `rel_umd_replace` | 43,356 | scene 0x1b, id 0x2e | — | UMD swap: `sceUmdUser` (8 functions), `IoFileMgrForUser`, `database/umd_replace/`. |
| `rel_blackjack` | 104,628 | scene 0x0f, id 0x22 | — | Minigame: blackjack (`mini_bj_*`). |
| `rel_dodge` | 107,436 | scene 0x11, id 0x24 | — | Minigame: dodgeball (`mini_db_*`). |
| `rel_connection` | 106,180 | scene 0x13, id 0x26 | — | Minigame: `connection/*.ehp`, SD-character sprites. |
| `rel_underground` | 123,676 | scene 0x15, id 0x28 | — | Underground duel minigame: `underground/*.ehp`. Loads `duel_mgr` as a library and calls `libduel_mgr_rel`; calls scene 4. |
| `rel_quiz` | 74,908 | scene 0x18, id 0x2b | — | Minigame: quiz (`quiz/*.ehp`, `mini_qz_*`). |
| `rel_reversi` | 75,388 | scene 0x19, id 0x2c | — | Minigame: reversi (`minigame/reversi/`, `mini_rv_*`). |
| `rel_throw` | 118,684 | scene 0x1c, id 0x2f | — | Minigame (`mini_result`, title messages). |
| `rel_throw_starter` | 206,216 | scene 0x1d, id 0x30 | — | Launcher: 7 function starts; calls scene 0x1c, then returns. Most of its size is data, not yet examined. |
| `module/libfont.prx` | 21,584 | id 1 (root 0) | — | Sony `sceFont_Library`, encrypted. Loaded at boot by `0x088453e4`. |

## Registry proposals

Formats (`re/formats.csv`):

```
gmodule_prx,Plain ELF game modules in gmodule/ (36; scene and library modules),system,documented,
module_descriptor,Module descriptor record {id, root, name, kind, utility id} (BOOT.BIN 0x0889f57c / 0x0889fea4),system,documented,16
module_registry_entry,Module registry entry (BOOT.BIN 0x089235b4),system,documented,76
scene_table,Scene id to module id table (BOOT.BIN 0x088a1478),system,documented,248
scene_stack,Scene transition stack (BOOT.BIN, 0x0883596c),system,named,144
scene_slot,ehscript scene slot state (BOOT.BIN 0x08920be4),system,documented,100
```

Functions (`re/functions.csv`, `BOOT.BIN`); all `named` until the signatures are applied in Ghidra:

```
0x0881ce04,system_scene_init,system,named,
0x0881d028,system_scene_thread,system,named,
0x0881d18c,system_scene_on_module_loaded,system,named,
0x0881cf00,system_scene_run_slice,system,named,
0x0881cf54,system_scene_register,system,named,
0x0881cf74,system_scene_request,system,named,
0x0881cfb0,system_scene_set_static,system,named,
0x0881d9c4,system_load_module,system,named,
0x0881d9fc,system_queue_module_load,system,named,
0x0881dba0,container_file_thread,container,named,
0x0881d574,container_init_file_thread,container,named,
0x08827c54,system_module_registry_init,system,named,
0x08827cec,system_module_load,system,named,
0x08827d04,system_module_load_ex,system,named,
0x08827e18,system_module_all_loaded,system,named,
0x08827e60,system_module_unload,system,named,
0x08827f4c,system_module_register_table,system,named,
0x08828068,system_module_get_basename,system,named,
0x088280d8,system_module_get_filename,system,named,
0x08828144,system_module_find,system,named,
0x08828180,system_module_on_loaded,system,named,
0x0882b834,system_load_movie_modules,system,named,
0x0882b874,system_unload_movie_modules,system,named,
0x088415f4,system_load_audio_modules,system,named,
0x088453e4,system_font_init,system,named,
0x0883dbb0,system_scene_get_module_name,system,named,
0x0883dc54,system_scene_call,system,named,
0x0883dcd8,system_scene_return,system,named,
0x0883dd4c,system_scene_get_caller,system,named,
0x0883dda8,system_scene_get_transition,system,named,
0x0883dddc,system_scene_jump,system,named,
```

## Open questions

- The third word that scene modules pass to `system_scene_register` (stored at `0x08920c30`): `BOOT.BIN` only writes it and clears it. Values are module-relative pointers in some modules (`rel_duel_draw` `0xa99bc`) and constants in others (`rel_title` `0x00c535c0`).
- Who loads `rel_select_card`, `rel_field` (as a library) and the tools in `rel_labo`/`rel_story`: their ids are computed at runtime; trace in PPSSPP.
- `0x0884c63c` loads utility modules `0x100`/`0x101` (network). `0x0884c898` queues a module load through `0x0881d9fc` and starts it: which module (ad-hoc play? `rel_html_view`?).
- Why the six `*_starter` scenes and `rel_sdchrviewer` are in the tables but not on the disc (cut content or another region's disc); what `rel_throw_starter`'s 200 KB of data is.
- The memory map at runtime: where the heap ends and how much room the scene slot has, needed for a 3DS memory budget. A savestate in each major scene would give the module list and bases directly.
- The PPSSPP export mixes symbols of modules that were loaded at different times; an export taken in each scene would give clean per-module bases.
