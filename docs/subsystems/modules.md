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

- **Writer and round trip** (`gmodule_prx`, `reimplemented` 2026-11-04). `modules.elf_decode(data)` turns a plain module into its ELF header fields, program headers, section headers with names, and section contents; the PSP relocation sections (type `0x700000a0`, 8-byte entries) are decoded into `[offset, type, offset segment, address segment, high byte]` (types on the disc: 4 `R_MIPS_26` 81,068, 5 `HI16` 45,664, 6 `LO16` 45,663, 2 `R_MIPS_32` 30,781; high byte always 0), every other section is kept as bytes, and any non-zero byte outside every header and section is kept as a gap (there are none: alignment padding is zero in all 36). `modules.elf_build(model)` writes them back. All 36 `gmodule/*.prx` rebuild byte for byte (`python3 -I tools/roundtrip.py --check <PSP_GAME> --only gmodule_prx`; [`results/2026-11-04-format-raises-2.md`](../verification/results/2026-11-04-format-raises-2.md)). Tests: `tools/tests/test_roundtrip.py` (`MoreFileWriterTest.test_elf_module_codec`).

## Load mechanism

Two loaders sit on top of one asynchronous file thread.

### Module descriptor tables (`BOOT.BIN`)

There are two tables of 16-byte records `{u32 id, s32 root, char *name, u16 kind, u16 utility_id}`, each ended by a zero record:

- `0x0889f57c`: Sony modules, ids 1–7: `libfont.prx` (root -2, kind 0), `videocodec.prx` (kind `0xffff`), `audiocodec.prx` (kind 4, utility `0x0300`), `mpegbase.prx` (kind `0xffff`), `mpeg.prx` (4, `0x0303`), `libatrac3plus.prx` (4, `0x0302`), `sc_sascore.prx` (4, `0x0301`).
- `0x0889fea4`: game modules, ids 8–0x31, all root 2 (`gmodule/`), kind 0. There are 42 names. Six of them are not on the disc: `rel_sdchrviewer` (0x1c), `rel_blackjack_starter` (0x23), `rel_dodge_starter` (0x25), `rel_connection_starter` (0x27), `rel_underground_starter` (0x29) and `rel_reversi_starter` (0x2d).

Writer and round trip of both tables and the scene table below (`modules.read_descriptors`/`write_descriptors`, `read_scene_table`/`write_scene_table`): `python3 -I tools/roundtrip.py --check <PSP_GAME> --only module_descriptor,scene_table` (byte-identical; `reimplemented`).

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

Scene transitions use a scene id, not a module id. The scene table at `0x088a1478` (31 × `{u32 scene, u32 module_id}`) is mapped by `0x0883dbb0`; an unknown id returns the string `"unknown id"`. The stack is a 144-byte structure returned by `0x0883596c`: `+0` depth, `+4` current transition `{u16 type, from, to, arg}`, `+0x0C` stack of 8-byte transitions. Full layout (16 entries, the `+0x8c` halfword): `docs/formats/system-runtime.md`.

| Address | Name (proposed) | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x0883dc54` | `system_scene_call(from, to, arg)` | H | Pushes `{1, from, to, arg}` and requests `to`'s module. Exported. |
| `0x0883dcd8` | `system_scene_return(from, arg)` | H | Current = `{2, from, caller, arg}`; pops; requests the caller's module. Every scene module calls it with its own scene id. Exported. |
| `0x0883dddc` | `system_scene_jump(from, to, arg)` | H | Clears the stack, current = `{3, from, to, arg}`. `rel_duel_mgr` jumps to scene 0x0d (title). Exported. |
| `0x0883dd4c` | `system_scene_get_caller(scene)` | M | `from` of the top entry if its `to` is `scene`, else 31. Exported. |
| `0x0883dda8` | `system_scene_get_transition(buf)` | M | Copies the current 8-byte transition. Exported. |

### Remaining loader functions

All in `re/documented.tsv`. "Exported" means no direct caller in `BOOT.BIN` (reached through `libehsys_rel` or a pointer).

| Address | Name | Conf. | Evidence and callers |
| --- | --- | --- | --- |
| `0x0881d18c` | `system_scene_on_module_loaded(slot, uid) → uid > 0` | H | Stores `uid` at `slot + 0x50` when positive. Passed as the load callback by `system_scene_thread`. |
| `0x0881cfb0` | `system_scene_set_static(fn) → 1` | H | Requests `"staticmodule"` and stores `fn` at `0x08920c38`, or 0 when `fn`'s first word has opcode 2 (`j`, an unresolved stub). Caller `system_scene_init`. |
| `0x0881d9c4` | `system_load_module(root, name) → uid` | H | `container_resolve_path(buf, root, name, 0)` + `sceKernelLoadModule(buf, 0, 0)`. Callers `container_file_thread`, `system_font_init`. |
| `0x0881d9fc` | `system_queue_module_load(root, name, callback, arg) → 1` | H | Type-1 request in the file queue (`container.md`). Callers `system_scene_thread`, `system_module_load_ex`, `0x0884c850`. |
| `0x08827c54` | `system_module_registry_init(root_a, root_b)` | H | Clears the registry (`0x1304` bytes), patches roots −1/−2 of the Sony table `0x0889f57c`, registers it. Caller `0x0881d1a8`. |
| `0x08827f4c` | `system_module_register_table(table) → duplicate` | H | Appends descriptors `{id, root, name, u16 kind, u16}` (16 bytes, list ends at a null name) as 76-byte entries unless the id exists, then `system_qsort` with `system_module_compare_id`; returns 1 if an id was a duplicate. Callers `system_module_registry_init`, `system_main`. |
| `0x08828144` | `system_module_find(id) → entry or 0` | H | `system_bsearch` with `system_module_compare_id`. Callers `system_module_load_ex`, `system_module_unload`, `system_module_get_basename`, `system_module_get_filename`. |
| `0x088281d8` | `system_module_compare_id(a, b)` | H | `*b − *a`: the registry is sorted by descending id. |
| `0x0882b834`, `0x0882b874` | `system_load_movie_modules()`, `system_unload_movie_modules()` | H | Load ids 2–5 / unload 5–2; return 0. Exported. |
| `0x088415f4` | `system_load_audio_modules()` | H | Loads ids 3, 7, 6, waits with `system_module_all_loaded` (pumping `0x0881d21c`), creates the `0x280000`-byte heap at `0x08acda40` (`system_heap_create`), registers callbacks `0x088414a0`/`0x08841514`/`0x08841554` with `0x08869290`, and calls `0x08867a84(0, 0)`, `0x08868ab8(2, 2)`, `0x08841724(n, 12)` for n = 0–2. Caller `system_main`. |
| `0x088453e4` | `system_font_init(root, alt_font) → 1` | H | Retries `system_load_module(root, "libfont.prx")` until it succeeds, starts it, `sceFontNewLib`, `sceFontOpen` (and `sceFontFindOptimumFont` for a 20 × 20 font when `alt_font`), stores the font metrics at `0x08d9ea78`–`0x08d9ea9c`, sets alt character `0x25a1`, scale 1.0 or 0.9. Caller `system_main` with `(0, 1)`. |
| `0x0883dbb0` | `system_scene_get_module_name(scene) → name` | H | Sorts the scene table once (flag `0x08acd9c8`), `bsearch` with `system_scene_compare_id`, then `system_module_get_basename(module_id)`; `"unknown id"` otherwise. Callers `system_scene_call`, `system_scene_return`, `system_scene_jump`. |
| `0x0883de64` | `system_scene_compare_id(a, b)` | H | `*b − *a`. |
| `0x0883596c` | `system_get_scene_stack()` | H | Returns `0x08aa56a4`. Callers: the scene transition functions above and `0x0883de74`, `0x0883de9c`. |

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

A scene module's `e_entry` calls `system_scene_register(start, end, x)` and returns 0: usually a 56-byte `*_module_start`, also a 52-byte `*_register_scene` (`rel_cutin_viewer`, `rel_debug_menu`, `rel_html_view`, `rel_labo`, `rel_movie_viewer`), 84 bytes in `rel_dodge`, `rel_throw` and `rel_duel_mgr`, 64 in `rel_duel_draw`. A library module's `e_entry` is the 8-byte `jr ra; li v0, 0`, and this stub need not sit at offset 0: `ui_album_module_start` 0x6ab4, `ui_charalist_module_start` 0x4a8, `shop_conv_machine_module_start` 0x467c, `deck_swap_module_start` 0x0, `deck_tutorial_module_start` 0x3590, `ui_duelrecord_module_entry` 0x0, `ui_limitlist_module_entry` 0x0, `shop_password_module_start` 0x1598, `deck_recipe_viewer_module_start` 0x0, `deck_select_card_module_start` 0x1b3c, `duel_core_tutorial_module_start` 0x1b10, `ui_tutoriallist_module_entry` 0x26b8. An unreferenced 8-byte `return 0` in a module is therefore its start body, not padding. (All ELF headers read; sizes from the registry, `rel_deck`, `rel_duel_eng` and `rel_title` not compared.) `rel_duel_draw` is both: its entry registers itself as a scene only when started with `argsize <= 0`, that is, as scene 3 and not when `rel_duel_mgr` loads it as a library with `argsize 4`. `rel_field` (scene 5, and `libfield_rel` for `rel_story`) and `rel_duel_mgr` (scene 6, and `libduel_mgr_rel` for `rel_underground`) are dual-use in the same way.

### File thread

`0x0881d9fc(root, name, callback, arg)` queues a request with type 1 in the 32-entry, 0x60-byte queue at `0x08920cac + 8`. This is the same queue that `container_read_async` (`0x0881d7b8`) uses with type 0. The file thread `0x0881dba0` takes requests one at a time. For type 1 it calls `0x0881d9c4(root, name)` = `container_resolve_path` + `sceKernelLoadModule(path, 0, NULL)` (the only `sceKernelLoadModule` call site, `0x0881d9e8`), then `callback(arg, uid)`. Loads are therefore serialised with file reads. Modules are loaded with no partition or position option, so the kernel chooses the address.

### Addresses: not fixed overlays

Modules have no fixed load address; they go wherever the kernel's allocator puts them. The PPSSPP export nevertheless shows that the scene slot reuses the same memory. `rel_title` (618/618 function starts) and `rel_duel_mgr` (202/202) both match at `0x08e9aa00`. Their symbols overlap in the export (246 overlapping functions), which only happens if one was unloaded and the other loaded into the freed block. The duel libraries loaded by `rel_duel_mgr` sit higher, at `0x0983fb00` and `0x09be1400`.

## Runtime bases (`ghidra/symbols.sym`)

**Verified in PPSSPP (2026-10-26, [`results/2026-10-26-session0.md`](../verification/results/2026-10-26-session0.md))**: two further fresh boots gave the same bases for `rel_duel_eng`, `rel_duel_draw`, `rel_duel_mgr` (single duel) and `rel_story`, `rel_field` (free roam), with 100 % (or 1178/1180) of function starts matched.

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

Imported into `ghidra/TF3.gpr` at these bases: `rel_duel_eng` (`0x09be1400`) and `rel_duel_draw` (`0x0983fb00`), which have their own address ranges and keep plain registry ids, and the shared-slot modules `rel_story`, `rel_deck`, `rel_title`, `rel_duel_mgr` (`0x08e9aa00`), `rel_field` and `rel_shop` (`0x090ced00`), whose registry ids are module-qualified (`rel_story:0x08ea63f4`, produced by `ExportFunctions.java <csv> <module>`).

Import stubs are named with `tools/prx_imports.py` (`re/names-imports-<module>.csv`). Imports from other game modules resolve when the exporting module is passed with `--provider PRX:BASE[:PREFIX]`: `rel_duel_draw` and `rel_duel_mgr` resolve all their `libduel_eng_rel` and `libduel_draw_rel` imports, and `rel_story` its 8 `libfield_rel` imports. What remains unresolved comes from libraries whose module base is still unknown (charalist, cardalbum, tutorial, deck swap and similar): 47 in `rel_story`, 36 in `rel_title`, 16 in `rel_duel_mgr`, 7 in `rel_deck`.

### All modules imported (2026-11-04, round 5)

Until round 4 only `BOOT.BIN` and eight game modules were in the Ghidra project, so the registry's function total left out 28 of the 36 `gmodule/` files, and 95 import stubs pointed at exports of modules that were not there. All 28 were imported on 2026-11-04 with the loader and options of the existing ones (`PSP Executable (ELF)` loader `PspElfLoader`, language `Allegrex:LE:32:default`, default auto-analysis):

```
analyzeHeadless ghidra TF3 -import gmodule/rel_charalist.prx -loader PspElfLoader -loader-imagebase 09eee400
analyzeHeadless ghidra TF3 -import gmodule/<module>.prx -loader PspElfLoader -loader-imagebase 0
```

- **Bases.** `tools/modules.py base` was re-run against all seven PPSSPP exports. It finds one new base: `rel_charalist` at `0x09eee400` in `duel-2026-10-26.sym` (107/107 function starts; the runner-up 39). That is the first 256-byte boundary after `rel_title`'s image (`0x08e9aa00` + memory size `0x1053980` = `0x09eee380`), consistent with `rel_title` loading the character list (id `0x0d`) right after itself. No other module reaches the noise threshold in any export. The other 27 modules are therefore imported at image base `0x0`, so their addresses are module offsets, the convention `docs/formats/tutorial.md` already used for `rel_tutorial`. All 28 have module-prefixed registry ids (`rel_quiz:0x00001234`, `rel_charalist:0x09eee8b0`), since their runtime addresses are unknown or shared with other modules.
- **Names.** `re/names-<module>.csv` gives each library module's exports the names `re/game-libs.csv` derives from the importing modules' call sites (placed at the export address of the module's `.lib.ent`); `re/names-rel_tutorial.csv` gains the two missing exports (`duel_core_tutorial_on_duel_end` `+0x468c`, `duel_core_tutorial_is_finished` `+0x46dc`). The PPSSPP export that covers `rel_charalist` names no function there: it lists 120 unnamed starts (`z_un_`), 4 of which Ghidra's analysis had missed (`0x09eee8a8`, `0x09ef44e4`, `0x09ef450c`, `0x09ef4f80`, small functions after a `jr ra` that nothing calls directly); the orphan-code repair below creates them, so no `names-ppsspp` file was added.
- **Import stubs.** `re/names-imports-<module>.csv` for every new module; imports between game modules resolve through `--provider` (for example `rel_conv_machine` → `rel_select_card`, `rel_labo` → nine library modules, `rel_underground` → `rel_duel_mgr`, `rel_tutorial` → `rel_duel_eng`/`rel_duel_draw`). 50 Sony NIDs that `BOOT.BIN` does not import, or re-exports only under `libehsys_rel` (`sceHttp`, `sceSsl`, `sceNet*`, `sceUtility` HTML viewer, `sceUsb`, `sceUmdUser`, `sceImpose`, `sceJpeg`, three `ThreadManForUser` and four `IoFileMgrForUser` functions imported directly by `rel_umd_replace`) are named in `re/game-libs.csv`; each name was checked by recomputing the NID (first four bytes of the SHA-1 of the name, little-endian).
- **Encrypted, not imported.** `USRDIR/module/libfont.prx` (`~SCE`/`~PSP`, Sony's `sceFont_Library`), `SYSDIR/EBOOT.BIN` (the encrypted copy of `BOOT.BIN`) and `SYSDIR/UPDATE/EBOOT.BIN` + `DATA.BIN` (the firmware updater) are encrypted or Sony's and were left alone. There is no other `.prx` or `.elf` on the disc.
- **Counts** (own functions / import stubs, after auto-analysis and stub naming): `rel_cutin_viewer` 569 / 1,557, `rel_underground` 400 / 1,567, `rel_blackjack` 342 / 1,561, `rel_decktutorial` 317 / 1,556, `rel_dodge` 290 / 1,558, `rel_connection` 277 / 1,557, `rel_throw` 275 / 1,560, `rel_select_card` 226 / 1,556, `rel_deckswap` 220 / 1,605, `rel_quiz` 183 / 1,557, `rel_tutorial` 176 / 2,969, `rel_reversi` 169 / 1,556, `rel_charalist` 115 / 1,557, `rel_gallery` 92 / 1,557, `rel_cardalbum` 82, `rel_umd_replace` 85, `rel_usb_connect` 79, `rel_recipeviewer` 78, `rel_limitlist` 65, `rel_conv_machine` 46, `rel_duelrecord` 45, `rel_debug_menu` 42, `rel_password` 39, `rel_html_view` 37, `rel_tutoriallist` 28, `rel_movie_viewer` 13, `rel_labo` 11, `rel_throw_starter` 10 (the Sony stubs of `rel_html_view`, `rel_umd_replace`, `rel_usb_connect` and `rel_cardalbum` are still counted as own functions here and become `thunk_` stubs at the next refresh). In all: 4,311 functions and 45,103 import stubs added to the registry; the documented share of functions fell from 96.33 % (12,269 / 12,737) to 71.97 % (12,269 / 17,048).
- **Registry refresh.** The refresh script processes the library modules before the modules that import them, so stub names always see the providers' current names.
- **Module documents.** Every function of the 28 modules was then named and documented (round 6, `system.md`); each module has its own document with purpose, flow, structures, files and open questions: [`rel_blackjack`](modules/rel_blackjack.md), [`rel_cardalbum`](modules/rel_cardalbum.md), [`rel_charalist`](modules/rel_charalist.md), [`rel_connection`](modules/rel_connection.md), [`rel_conv_machine`](modules/rel_conv_machine.md), [`rel_cutin_viewer`](modules/rel_cutin_viewer.md), [`rel_debug_menu`](modules/rel_debug_menu.md), [`rel_deckswap`](modules/rel_deckswap.md), [`rel_decktutorial`](modules/rel_decktutorial.md), [`rel_dodge`](modules/rel_dodge.md), [`rel_duelrecord`](modules/rel_duelrecord.md), [`rel_gallery`](modules/rel_gallery.md), [`rel_html_view`](modules/rel_html_view.md), [`rel_labo`](modules/rel_labo.md), [`rel_limitlist`](modules/rel_limitlist.md), [`rel_movie_viewer`](modules/rel_movie_viewer.md), [`rel_password`](modules/rel_password.md), [`rel_quiz`](modules/rel_quiz.md), [`rel_recipeviewer`](modules/rel_recipeviewer.md), [`rel_reversi`](modules/rel_reversi.md), [`rel_select_card`](modules/rel_select_card.md), [`rel_throw`](modules/rel_throw.md), [`rel_throw_starter`](modules/rel_throw_starter.md), [`rel_tutorial`](modules/rel_tutorial.md), [`rel_tutoriallist`](modules/rel_tutoriallist.md), [`rel_umd_replace`](modules/rel_umd_replace.md), [`rel_underground`](modules/rel_underground.md), [`rel_usb_connect`](modules/rel_usb_connect.md). Corrections they make to the catalogue below: `rel_dodge` is a turn-based 2-vs-2 artillery game on a breakable block field, not dodgeball; `rel_underground` is a 100-floor ladder (amidakuji) run with duels; `rel_umd_replace` grants bonus cards when a disc of an earlier release is inserted; `rel_throw_starter`'s 200 KB is zero-filled `.data` (a developer launcher with a partner list); `rel_labo` and `rel_debug_menu` are debug hubs.

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
| `rel_tutorial` | 78,500 | id 0x0b | `libtutorial_rel` (13) → duel_mgr | Scripted duel tutorial: `d_tutorial/tutorial/tuto_field_%02d.ydq`, `tuto_cmd_%02d.bin` (`docs/formats/tutorial.md`). Imports duel_eng and duel_draw. Base unknown (not in any symbol export); names at module offsets in `re/names-rel_tutorial.csv`. |
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
- Why the six `*_starter` scenes and `rel_sdchrviewer` are in the tables but not on the disc (cut content or another region's disc). (`rel_throw_starter`'s 200 KB: settled 2026-11-04, zero-filled arrays in `.data`; only the first `0x5200` bytes are non-zero, `modules/rel_throw_starter.md`.)
- Module bases: only `rel_charalist` has a known runtime base among the 28 modules imported in round 6; the others are at module offsets. A PPSSPP symbol export taken inside each mini-game, the labo tools and a tutorial duel would give their bases (and allow `verified` checks there).
- The memory map at runtime: where the heap ends and how much room the scene slot has, needed for a 3DS memory budget. A savestate in each major scene would give the module list and bases directly.
- The PPSSPP export mixes symbols of modules that were loaded at different times; an export taken in each scene would give clean per-module bases.
- Item callbacks with a `void` prototype: `ui_draw_list_window` keeps their result as the list (`ui.md`), so the remaining `void` rows of the family (`rel_deck`, `rel_deckswap`, `rel_decktutorial`, `rel_select_card`, `rel_duel_draw`) need a registry-wide check, including the (list, index, x, y) order of the `+0xfc` copies.
- `ui_mini_result_is_layout_frame_101` (`rel_title`) has registry size 88 against 20 for the other copies, although its decompilation is as short; its machine code compares with 0x65 but leaves the result in v1, so the compare is dead. Check the size. The 20-byte copies are tail calls that return the frame in v0.
- `ui_draw_level_badge_text_fit` and its copies (about 20 modules) are a generic pixel wrapper around `system_font_draw_text_fit_width`; the name comes from the single BOOT caller. A rename of the whole family (for example `ui_draw_text_fit_px`) is a project-wide decision.

## Audit of the round-6 rows (round 7, 2026-11-04)

Twin-assigned names: all 572 names taken from identical code (relocations masked) were compared target by target with their counterpart (`jal`/`j` targets, `lui`/`lo` address pairs, function pointers, bytes of string and table data). 443 have the same targets; 54 call code-identical functions that merely have other names; 60 call the module's own variant of the same role (`deck_swap_*`, `deck_tutorial_*`, `deck_select_card_*`, `ui_cutin_viewer_*`), which their rows state; 15 show a data difference, 14 of them past the end of the table in use or in rows that name this module's data. One name was misleading and changed: `ui_charalist_draw_confirm_face_body` (loads `common_head.gim` / `common_body.gim`, not the duel-versus files). Data in uninitialised memory cannot be compared this way, so a masked match that differs only in such a global would not be caught.

Hidden tail jumps: the decompiler shows short wrappers ending in `j` as empty bodies when the prototype is void or the call is in the delay-slot pattern. Every documented function up to 64 bytes in all programs whose row claimed emptiness was compared with its instructions: rows that said "empty" for real calls were rewritten and the `*_stub_noop_*` names replaced. A void prototype can also hide a computed return value: check the instructions before calling a short function empty.
