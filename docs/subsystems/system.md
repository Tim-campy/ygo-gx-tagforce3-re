# System and runtime library

Statically linked C runtime (newlib), libm and VFPU helpers in `BOOT.BIN`. Most names come from PPSSPP's hash recognition (`re/names-ppsspp.csv`, prefixed `system_` and `system_vfpu_`); the table lists the ones that were also checked by reading the code.

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x088115e4` | `system_strcpy` | H | Word-at-a-time copy with the `(x + 0xfefefeff) & ~x & 0x80808080` zero-byte test, then a byte loop up to NUL. PPSSPP: `strcpy`. |
| `0x088113c0` | `system_strcat` | H | Finds the end of `dst` with the same test, then calls `system_strcpy`. PPSSPP: `strcat`. |
| `0x0881166c` | `system_strlen` | H | Byte loop returning the distance to NUL. PPSSPP: `strlen`. |
| `0x0880a4a4` | `system_bsearch(key, base, n, size, cmp)` | H | Binary search returning the element or 0. |
| `0x0880f844` | `system_qsort(base, n, size, cmp)` | H | Same comparator as the `bsearch` on the same array. PPSSPP: `qsort`. Callers `container_build_file_index`, `system_module_register_table`, `system_scene_get_module_name`, `0x0885ad64`, `0x0885c660`. |
| `0x08810f5c` | `system_sprintf(buf, fmt, ...)` | H | Builds a string `FILE` over `buf` (flags `0x208`, size `0x7fffffff`), calls `system_vfprintf_r(system_get_reent(), …)` and NUL-terminates. Callers `container_resolve_path`, `deck_load_recipe`, `deck_get_recipe_name`, `0x08850308`. |
| `0x0880d398` | `system_malloc(size)` | H | Calls `system_malloc_r` (`0x0880d3f0`, PPSSPP `_malloc_r`) with the reentrancy struct from `0x0880ce2c`: newlib's `malloc`. Callers `container_build_file_index`, `container_index_directory`, `system_main`, `0x08853c7c`, `0x08853c84`. |
| `0x0880d3c4` | `system_free(ptr)` | H | Same pattern with `system_free_r` (`0x0880c504`). Callers include `container_build_file_index`, `container_index_directory`, `system_main`, `0x0882f2e8`, `0x08853c8c`. |
| `0x0880ce2c` | `system_get_reent()` | H | Returns `*(k0 + 4)` when the thread-local block in `k0` has one, else the global `0x0889e5b0`: newlib's `__getreent`. 27 callers in the C library, including `system_malloc`, `system_free`, `system_sprintf`. |
| `0x08811804` | `system_strncpy(dst, src, n)` | H | Word-at-a-time copy, then NUL padding up to `n`. Callers `container_index_directory`, `container_read_async`, `system_queue_module_load`, `system_module_register_table`, `system_module_get_basename`, `system_module_get_filename`. |
| `0x0885827c` | `system_wcsncpy(dst, src, n)` | H | The same for `u16` strings. Callers include `card_db_expand_dictionary`, `card_db_expand_card_refs`, `deck_set_limit_list_name`, `0x088491dc`, `0x0884d000`, `0x08858304`. |
| `0x08859688` | `system_rand_shifted()` | H | `system_rand() >> 4`. Callers `system_main` (once per frame, result unused), `system_init_game_globals`, `0x0884c6b8`. |

### Heaps

The game manages its own heaps with a 16-byte header tagged `"HOGE"` (`0x45474f48`) and a block list with flag bit 31 in each block word.

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x0882622c` | `system_heap_create(memory, size) → heap` | H (layout M) | Writes the magic, size `<< 8` at `+4`, the first block at `+0x10` and the end marker. Callers `system_load_audio_modules` (`0x08acda40`, `0x280000` bytes), `system_init_game_globals` (`0x08ac2580`, `0x4000` bytes). |
| `0x08826450` | `system_heap_alloc(heap, size) → ptr or 0` | H | Tail call to `0x08826458(heap, size, 1)`; size rounded up to 16. 11 callers, including `save_open`, `0x08841564`, `0x088367bc`. |
| `0x088265ac` | `system_heap_free(heap, ptr) → 1` | M | Sets the block's free bit and relinks it (`0x08826c9c`, `0x08826fb8`, `0x088270ac`). 16 callers, including `save_close`. |

### Boot and main loop

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x08833734` | `system_main` | H | Called from `0x0885f570`. Registers `EXIT_CALLBACK` and `POWER_CALLBACK`, activates the UMD, `container_build_file_index(0x23000)`, `0x0881d1a8` (file thread, module registry), registers the game module table `0x0889fea4`, `system_load_audio_modules`, `system_init_game_globals`, `system_font_init(0, 1)`, `system_scene_init("rel_title", 2, 0)`; then loops forever: `system_rand_shifted`, power tick, `system_scene_run_slice` and per-frame services (`0x088359f4`, `0x0881d24c`, `0x08850e68`, `0x0881d21c`, `system_check_soft_reset`). |
| `0x08833688` | `system_exit_callback` | H | Registered with `sceKernelRegisterExitCallback`; calls `0x0882b8c0`, then `sceKernelExitGame`. |
| `0x088336b0` | `system_power_callback` | H | Registered with `scePowerRegisterCallback`; stores the power flags at `0x08ac24bc` (`0x08835984`). |
| `0x088336d0` | `system_check_soft_reset` | M | Pad word `+0x24` of `0x088284b8()` containing `0x309` (SELECT, START, L, R) plus two zero checks triggers `sceKernelLoadExec("disc0:/PSP_GAME/SYSDIR/BOOT.BIN")`. That `0x088284b8` returns the pad state is inferred from the bit mask. |
| `0x08835c68` | `system_init_game_globals` | H | Binds the six embedded EHP archives, clears `0x1cefc` bytes at `0x08aa5680`, creates a 16 KiB heap, seeds `rand` from the RTC (`0x088596a8`), sets the game-state offset `0x08ac18c0 = rand & 15` (`save.md`), finds `loading.ehf`, calls `save_reset_options`. Caller `system_main`. |

## The `libehsys_rel` export library

`BOOT.BIN` exports one library to the game modules in `gmodule/`: `libehsys_rel`, 1,556 functions and 2 variables (`.lib.ent`, NID and address tables in `.rodata.sceResident`). Modules import it by NID; `rel_duel_eng.prx` imports all 1,556 functions. `tools/prx_imports.py` resolves a module's imports against this table and names each import stub `thunk_<target name>` in the target's group (`re/names-imports-<module>.csv`); stubs whose target is still unnamed stay `thunk_FUN_<address>` and count as unknown. Pointers inside both files are unrelocated module offsets (`BOOT.BIN` is itself a relocatable PRX), so `BOOT.BIN` targets are `0x08804000 + offset`.

This also explains functions with no caller inside `BOOT.BIN`, such as `container_gzip_decompress`: they are part of the export library and are called from modules.

`libehsys_rel` has only 1,530 distinct NIDs among its 1,556 entries. 68 entries re-export `BOOT.BIN`'s own firmware import stubs under their Sony NIDs. The module loader (scene slot, module registry, descriptor tables) and the catalogue of all 37 modules are in `modules.md` (`tools/modules.py`).

## Open questions

- Heap size and placement (needed later for memory-budget estimates on 3DS).
