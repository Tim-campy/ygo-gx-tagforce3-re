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
| `0x08859688` | `system_rand_shifted()` | H | `system_rand() >> 4`. Callers `system_main` (once per frame, result unused), `system_init_game_globals`, `system_wait_frame`; imported by every game module (the shop's pack draw, `docs/formats/packs.md`). |
| `0x088101d4` | `system_rand()` | H | newlib `rand`: the 64-bit state at reentrancy block `+0xa8`/`+0xac` becomes `state × 0x5851F42D4C957F2D + 1`; returns bits 32–62. One stream for the whole game. Callers `system_rand_shifted`, `0x0884adf0`, `0x0884ae5c`. |
| `0x0881019c` | `system_srand(seed)` | H | newlib `srand`: state = `seed`, high word 0. Callers `system_seed_rand_from_rtc`, `0x088596cc`, `0x0881d028`. |
| `0x088596a8` | `system_seed_rand_from_rtc()` | H | `system_srand(low word of sceRtcGetCurrentTick)`; called once by `system_init_game_globals`. So the random stream differs at every boot. |
| `0x0884c6b8` | `system_wait_frame()` | M | `system_rand_shifted()` (discarded) then `0x0881d01c` = `system_wakeup_scene_thread`, a `sceKernelWakeupThread(*0x08920c44)` (corrected 2026-11-04: it wakes the scene thread rather than waiting itself, M); the busy-wait loops of the story handlers call it (`docs/formats/story.md`). Callers `0x0884c6dc`, `0x0884c808`, `0x0884c850` and the module imports. |

### Heaps

The game manages its own heaps with a 16-byte header tagged `"HOGE"` (`0x45474f48`) and a block list with flag bit 31 in each block word.

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x0882622c` | `system_heap_create(memory, size) → heap` | H (layout M) | Writes the magic, size `<< 8` at `+4`, the first block at `+0x10` and the end marker. Callers `system_load_audio_modules` (`0x08acda40`, `0x280000` bytes), `system_init_game_globals` (`0x08ac2580`, `0x4000` bytes). |
| `0x08826450` | `system_heap_alloc(heap, size) → ptr or 0` | H | Tail call to `0x08826458(heap, size, 1)`; size rounded up to 16. 11 callers, including `save_open`, `0x08841564`, `0x088367bc`. |
| `0x088265ac` | `system_heap_free(heap, ptr) → 1` | M | Sets the block's free bit and relinks it (`0x08826c9c`, `0x08826fb8`, `0x088270ac`). 16 callers, including `save_close`. |

Header and block-table layout: `docs/formats/system-runtime.md`, "heap_header".

### Boot and main loop

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x08833734` | `system_main` | H | Called from `0x0885f570`. Registers `EXIT_CALLBACK` and `POWER_CALLBACK`, activates the UMD, `container_build_file_index(0x23000)`, `0x0881d1a8` (file thread, module registry), registers the game module table `0x0889fea4`, `system_load_audio_modules`, `system_init_game_globals`, `system_font_init(0, 1)`, `system_scene_init("rel_title", 2, 0)`; then loops forever: `system_rand_shifted`, power tick, `system_scene_run_slice` and per-frame services (`0x088359f4`, `0x0881d24c`, `0x08850e68`, `0x0881d21c`, `system_check_soft_reset`). |
| `0x0881d1a8` | `system_init_core(config)` | H | `system_display_init(config+0x14, config+0x18 == 30 ? 30 : 60)`, file thread, module registry. Config `0x088a0154`, whose `+0x18` is 30. Caller `system_main`. Details in `field_3d.md`, "Frame timing". |
| `0x08822bd4` | `system_display_init(arg, fps)` | M | Frame counter `0x089229b4` = 0, frame rate `0x089229b8` = `fps`; GE and display set-up. |
| `0x08822d10` | `system_display_flip()` | H | At 30: an extra `sceDisplayWaitVblankStartCB` when fewer than two vblanks passed since the last flip; then one more wait; increments the frame counter. Two vblanks per frame = 29.97 Hz. Via `system_end_frame` (`0x0881d21c`), once per main-loop iteration. |
| `0x08822e20` | `system_get_frame_timing() → {frame counter, fps}` | H | Returns `0x089229b4`. 26 callers in `BOOT.BIN` and many in the modules; all only read. |
| `0x08822e2c` | `system_set_frame_rate(fps)` | H | Writes `0x089229b8`. No caller in `BOOT.BIN` or any module: the rate stays 30. |
| `0x0881d24c` | `system_scene_run_frame()` | H | Calls the frame callback of the current handler entry (`0x08920c48`, 12 bytes: id, frame, leave). |
| `0x0881d2d0` | `system_scene_set_frame_callback(id, frame_cb, leave_cb)` | M | Runs the old leave callback, stores the new entry. |
| `0x08833688` | `system_exit_callback` | H | Registered with `sceKernelRegisterExitCallback`; calls `0x0882b8c0`, then `sceKernelExitGame`. |
| `0x088336b0` | `system_power_callback` | H | Registered with `scePowerRegisterCallback`; stores the power flags at `0x08ac24bc` (`0x08835984`). |
| `0x088336d0` | `system_check_soft_reset` | M | Pad word `+0x24` of `0x088284b8()` containing `0x309` (SELECT, START, L, R) plus two zero checks triggers `sceKernelLoadExec("disc0:/PSP_GAME/SYSDIR/BOOT.BIN")`. That `0x088284b8` returns the pad state is inferred from the bit mask. |
| `0x08835c68` | `system_init_game_globals` | H | Binds the six embedded EHP archives, clears `0x1cefc` bytes at `0x08aa5680`, creates a 16 KiB heap, seeds `rand` from the RTC (`0x088596a8`), sets the game-state offset `0x08ac18c0 = rand & 15` (`save.md`), finds `loading.ehf`, calls `save_reset_options`. Caller `system_main`. |

## The `libehsys_rel` export library

`BOOT.BIN` exports one library to the game modules in `gmodule/`: `libehsys_rel`, 1,556 functions and 2 variables (`.lib.ent`, NID and address tables in `.rodata.sceResident`). Modules import it by NID; `rel_duel_eng.prx` imports all 1,556 functions. `tools/prx_imports.py` resolves a module's imports against this table and names each import stub `thunk_<target name>` in the target's group (`re/names-imports-<module>.csv`); stubs whose target is still unnamed stay `thunk_FUN_<address>` and count as unknown. Pointers inside both files are unrelocated module offsets (`BOOT.BIN` is itself a relocatable PRX), so `BOOT.BIN` targets are `0x08804000 + offset`.

This also explains functions with no caller inside `BOOT.BIN`, such as `container_gzip_decompress`: they are part of the export library and are called from modules.

`libehsys_rel` has only 1,530 distinct NIDs among its 1,556 entries. 68 entries re-export `BOOT.BIN`'s own firmware import stubs under their Sony NIDs. The module loader (scene slot, module registry, descriptor tables) and the catalogue of all 37 modules are in `modules.md` (`tools/modules.py`).

## Function families named in the 2026-10-31 round

Basis for the whole round (all groups): the Ghidra decompilation of every function that still had a default name, exported read-only in one headless run per program, read in packs that list each function's callers, callees and nearest named neighbours. Every name, with its confidence (H/M) and a one-line basis, is a row in `re/names*.csv` under a `# family <tag>` comment. Low-confidence candidates were left unnamed. Nothing in this round was traced in PPSSPP.

`BOOT.BIN` families in `system` (868 names):

| Family | Count | Range / evidence |
| --- | --- | --- |
| newlib C runtime (`newlib_stdio`, `_stdlib`, `_reent`, `_mprec`, `_syscalls`, `_malloc`, `_locale`, `_wchar`, `_libm`) | 122 | `0x08804000`–`0x08817000`; the libc names (`system_vfprintf`, `system_bfree`, `system_hi0bits`, `system_sinit` …) follow the newlib structure: reentrancy offsets, `__sdidinit`, Bigint free lists, the syscall stubs over `sceIo*`/`sceKernelLibc*`. |
| `libgcc_softfp`, `libgcc` | 24 | `0x0885d024`–`0x0885f3f8`: 64-bit division (`system_udivdi3`, `system_umoddi3`) and soft-float. The six float compares are named in source order only (M). |
| VFPU vector and matrix helpers (`vfpu_vector2/3/4`, `vfpu_matrix2/3`, `vfpu_color`, `quaternion`, `matrix_helpers`, `vfpu_random`) | 135 | Named `system_vfpu_vector3_*` etc. because the plain `system_vfpu_v*` names already exist. VFPU bodies are lower confidence (stock Ghidra), so most are M. |
| `ge_lists` | 42 | The game's own GE display-list builder: 16 linked layers, current layer `0x08924980`, tracking of changed GE commands so their defaults can be restored, draw array/bezier/spline, render targets. |
| `ge_cmd_writers` | 57 | `0x088297c4`–`0x0882b6cc`: one writer per GE command, decoded from the opcode each emits (ZTST `0xde` → `system_ge_write_depth_func`); the libgu equivalent is in the basis. Imported by every module (value 9). |
| `gum_matrix` | 36 | The `ehgum.c` matrix stack: mode `0x08923150`, stack pointer `0x08923154`, per-mode base `0x08923158 + 12·mode`, dirty flags `0x08923188`. |
| `movie_player` | 77 | The PSMF player helpers (Sony sample-player structure): audio queue, video timestamp queue, display queue, reader, threads; strings `sound_lockSema`, `display_lockSema`, `display_delay_flag`, `controlFlag`, `waitFlag`, `UMD_SAMPLE_IO_SEMA`. |
| `font`, `font_flags` | 69 | The sceFont text renderer. Control codes: `$R` ruby (reading in brackets), `$f`/`$F` character conversion mode, `$C<hex>` colour (palette `0x088a1604`). Flag word `0x08d9eaac`: `0x2` colour, `0x4` shadow, `0x8` trim spaces at a wrap, `0x8000` ruby. |
| ad-hoc network (`adhoc`, `net_*`) | 205 | `0x08850b68`–`0x0885cff0`: the "YgAdhocMsg"/"ygadh" stack: state machine, phase/state/step sync, PDP socket on port `0x315`, 30-entry ring queue, message header magic `0xab` plus checksum. Prefixed `system_net_` (there is no `net` group). `system_net_api_*` are the exported wrappers that fetch the context from `0x088505c4`. |
| `utility_dialogs`, `screen_fade`, `blocking_helpers` | 30 | PSP utility dialogs (message, network), screen fades, blocking waits. |
| `heap`, `cxx_heap`, `vram_alloc` | 27 | HOGE heap internals (allocation takes a direction argument, `system_heap_alloc` passes 1); `vram_alloc` is a bump allocator at EDRAM + `0x158000`. |
| `pad` | 13 | Pad state block `0x08924900` (64 bytes), repeat timers driven by the frame rate. |
| `scene`, `globals`, `wide_string`, `spline`, `lcg`, `fpu_fast_math` | 52 | Scene frame-callback table `0x08920c48`; u16 string helpers; splines; fast math exported to the modules. |
| startup | 2 | `system_module_start` (`0x0885f45c`: SDK/compiler version, creates thread `user_main` at `0x0885f570`) and `system_user_main_thread`. |

Modules: `rel_duel_mgr` scene (`duel_mgr_scene`, 25: entry, `scene_main`/`shutdown`, frame callback, FPL heaps, the UI-event hook `+0x10690`), `rel_duel_draw` heaps (HeapMain/HeapMovie) and scene entry, `rel_story` heap.

### Documented in this round

The following small functions were read in full (prototype, side effects and callers); their prototypes are in `re/documented.tsv`.

| Address | Function | Callers |
| --- | --- | --- |
| `0x08809cb0` | `system_fabsf` | `system_atanf`, `system_ieee754_asinf`, `system_ieee754_rem_pio2f`, `system_ieee754_atan2f`, `system_asinf` (was `system_acosf`) |
| `0x0880a3a8` | `system_abs` | `ui_draw_card_art_flip_offscreen`, `ui_draw_card_flip_offscreen`, `system_pad_analog_outside_deadzone` |
| `0x0880a48c` | `system_atoi` | `card_db_get_dictionary_word` |
| `0x08812e7c` | `system_strtol` | `system_atoi` |
| `0x0880cf18` | `system_localeconv_r` | `system_localeconv` |
| `0x0880cf60` | `system_localeconv` | `system_vfprintf_r` |
| `0x0880e33c`, `0x0880e378` | `system_malloc_lock`, `system_malloc_unlock` | `system_malloc_r`, `system_free_r`, `system_realloc_r`, `system_memalign_r`, `system_malloc_trim_r` |
| `0x0880ea64` | `system_hi0bits` | `system_dtoa_r`, `system_d2b`, `system_b2d` |
| `0x0880f77c` | `system_bfree` | `system_pow5mult`, `system_dtoa_r`, `system_reclaim_reent`, `system_multadd`, `system_strtod_r`, `system_lshift` |
| `0x088108ac` | `system_cleanup_glue` | `system_reclaim_reent`, itself |
| `0x0881574c` | `system_vfprintf` | `system_printf`, `system_sbprintf` |
| `0x0881d69c` | `container_read_file_from_start` | `container_load_archive` |
| `0x0881e52c` | `container_wait_umd_ready` | `container_io_read_retry`, `container_io_getstat_retry`, `container_io_open_retry` |
| `0x0881ef68` | `system_matrix4_mul_swapped` | `ui_ehf_draw`, `ui_ehf_draw_instances`, `ui_ehf_draw_shape_instance`, `system_matrix4_post_translate_xy`, `system_matrix4_post_scale_xy`, `system_matrix4_post_rotate_z_s16`, `0x0881f7ac`, `0x08820e7c` |
| `0x0881f168` | `system_vector4_copy` | `system_gum_get_eye_position`, `system_gum_set_eye_position`, `system_spline_eval`, `system_spline_eval_closed`, `field_3d_pose_nodes`, `field_3d_pose_nodes_blend`, `field_3d_camera_set_look_at`, `system_matrix4_inverse_rigid` |
| `0x08821470`, `0x088214c8` | `system_matrix4_post_scale_xy`, `system_matrix4_post_translate_xy` | `ui_ehf_draw`, `ui_ehf_draw_shape_instance`, `0x0881f7ac`, `0x08820e7c` |
| `0x08823cf0`, `0x088287b4` | `system_ge_uncached_address`, `system_make_uncached_pointer` (identical bodies) | `system_ge_reset_state_list`; `system_ge_init_layers` |
| `0x08824b28` | `system_align_past_string` | `0x088249d8` |
| `0x08825864` | `system_gum_pop_matrix` | `ui_ehf_restore_matrices`, `ui_ehf_end_draw`, `field_3d_draw_pass` |
| `0x0882591c` | `system_gum_get_matrix_mode` | `ui_ehf_begin_draw` |
| `0x088281e8`, `0x088281f8` | `system_module_add_ref`, `system_module_release_ref` | `system_module_load_ex`; `system_module_unload` |
| `0x08828208` | `system_pad_init` | `system_init_core` |
| `0x088284b8` | `system_pad_get_state` | `system_main`, `system_check_soft_reset`, `system_run_text_menu`, `system_net_update`, `system_net_watch_umd_state`, `ui_card_viewer_update`, `ui_update_list_window`, `ui_list_window_step_cursor_down` (and module imports) |
| `0x088285b4` | `system_pad_get_frame_rate` | `system_pad_init_repeat` |
| `0x08828c3c` | `system_ge_get_current_layer` | the `system_ge_open_list_*`/`close_list_*` functions, `0x08830638`, `0x088306c0` |
| `0x0882acd0`, `0x0882acfc` | `system_ge_write_tex_sync`, `system_ge_write_tex_flush` | `0x08830154`, `0x08837964`; `ui_draw_card_art_flip_offscreen`, `ui_draw_card_flip_offscreen`, `system_font_draw_text_fit_width`, `0x08830154` |
| `0x0882caa8` | `system_movie_audio_queue_push` | `system_movie_decode_audio` |
| `0x0882cf44` | `system_movie_reader_close` | `system_movie_play` |
| `0x0882d344`, `0x0882d3b4`, `0x0882d3f8` | `system_movie_control_flags_create`, `_destroy`, `_clear` | `system_movie_play` |
| `0x0882d434`, `0x0882d464` | `system_movie_wait_waitflag_bit0`, `_bit1` | `system_movie_display_show_next_frame`, `system_movie_display_thread`; `system_movie_flush_video` |

### Findings to reconcile (from the round), settled on 2026-10-31 (round 2)

- `0x08809fec` `system_acosf` → **`system_asinf` (changed, H).** The wrapper calls only `system_ieee754_asinf` and, on a domain error, fills the `matherr` record with the name string at `0x088779ac`, which reads "asinf". Its callers `0x0881c258`/`0x0881c3b0` are VFPU helpers.
- `system_movie_create_player` (`0x0882b964`) → **`system_movie_play` (changed, H).** It creates the sceMpeg player, starts the display, read and sound threads, runs `system_movie_flush_video` (the playback loop), waits for the threads, deletes them and frees everything; the return value is 1 when the playback was cut short (state 10). Its wrappers are now `system_call_movie_play` (`0x0882b95c`) and `system_movie_play_with_volume` (`0x0883debc`).
- `save_tick_frame_counter` (`0x088359f4`) → **`system_run_frame_services` (changed, H; still documented).** Per main-loop iteration it advances the play-time counter at game state `+0xc` (`save.md`), calls `0x08835bf0(4)` while `0x08aa5698` is set, `audio_update_voice_queues` and `audio_update_frame`. The prototype in `re/documented.tsv` is renamed with it.
- Duplicate `system_vfpu_*` names → **changed (M).** The second and third copies (`0x0881b508`–`0x0881b878`, `0x0881c5dc`, `0x0881c5f8`, `0x0881c630`) are byte-identical to the first ones at `0x08819970`–`0x08819cc0` and have no caller; they are now `<name>_b` / `_c`. `0x0881a838` `sceVfpuMatrix4Zero` (VFPU `vmzero.q`) and `0x0881a818` `system_vfpu_vmidt_q` (`vmidt.q`, identity) are **not** swapped: kept.

## Round 2 of the 2026-10-31 naming (contradictions, imports, boundaries)

### Game-library imports (`re/game-libs.csv`)

`tools/prx_imports.py` left 47 stubs of `rel_story`, 32 of `rel_title`, 7 of `rel_deck` and 16 of `rel_duel_mgr` unresolved. The cause: those modules import libraries that neither `BOOT.BIN` nor a module given with `--provider` exports. Ten of them belong to sub-modules that are not loaded in Ghidra (`libcardalbum_rel`, `libcharalist_rel`, `libconv_machine_rel`, `libdeck_tutorial_rel`, `libduelrecord_rel`, `liblimitlist_rel`, `libpassword_rel`, `librecipe_viewer_rel`, `libselect_card_rel`, `libtutoriallist_rel`, plus `libtutorial_rel` and `libdeck_swap_rel`); `libshop_rel` is exported by `rel_shop`, which the registry refresh processes after `rel_story`, so its names were not available; and `rel_deck` imports one Sony NID that `BOOT.BIN` does not (`sceRtc` `0xe7c27d1b`, `sceRtcGetCurrentClockLocalTime`). The same staleness hit `rel_story`'s `libfield_rel` stubs once (they carried `thunk_FUN_…` names until the next refresh).

`prx_imports.py` now looks unresolved imports up by (library, NID) in `re/game-libs.csv` (default: next to the registry; `--libs` overrides) and names the stub `thunk_<name>`. The table names 63 exports and one Sony NID from their call sites: the sub-modules share a `start(args)` / `update()` (non-zero = result) / `draw()` protocol, so `rel_story`'s 24 state functions (`dialogue.md`, "Sub-module states"), `rel_title`'s library states and `rel_deck`'s `deck_run_*` give the roles; exports without a caller keep a library-and-NID name (`ui_charalist_953239e8`). `rel_shop`'s three exports that Ghidra had no function for (`0x090d8280`, `0x090d8330`, `0x090d8338`) are created and named (`shop_lib_start`, `shop_lib_draw`, `shop_lib_shutdown_step`). The hand-made `ui_call_*`/`deck_call_*` rows of `rel_title` and `rel_deck` were removed, since the generated names replace them. Test: `tools/tests/test_prx_imports.py`.

### Function boundaries

Ghidra had 13,677 functions with a one-byte body (86 in `BOOT.BIN`, 1,768 in `rel_duel_eng`, the rest import stubs of the modules). `ApplyNames.java` created them on addresses where nothing had been disassembled (effect handlers reached only through tables, stubs), so the decompiler showed the real code but the registry size was 1. `tools/ghidra/FixOneByteBodies.java` (run once per program, not read-only) disassembles from each such entry and re-derives the body with `CreateFunctionCmd.fixupFunctionBody`; all 13,677 were repaired (145,184 bytes). `ApplyNames.java` now disassembles before it creates a function, so new ones get a real body. Remaining boundary observations from the reading packs, not changed: 8-byte entries that load an argument and jump into a neighbour's body (`rel_duel_eng` `0x09bf8988`, `0x09bfa76c`, `0x09c004fc`, `0x09c00504`, `0x09c0b7b8`, `0x09c0d4c4`, and the AI handler stubs that enter `0x09d76574`, `0x09d7e92c`, `0x09d6de24`; `BOOT.BIN` `0x08837578`, `0x08837950`, `0x0886f50c`): they are separate entry points sharing a body, which is how the compiler laid them out, and their names describe the entry; overlapping hand-written inflate code at `0x08817e70`/`0x08817f08`/`0x08817fa4`; and two functions whose decompilation is the tail of a neighbour (`0x0881697c`, `0x0886f520`), left unnamed. `ai_eval_attack` (`0x09d06188`, 17,700 bytes) itself is one correct function: its "truncated inner parts" were the helpers it calls, now named (`ai.md`).

### Result, quality sample and what stays unnamed

916 names were added or changed in this round (189 H, 727 M; 28 candidates were rejected as mere accessors of an unexplained global address, and 4 duplicates were dropped), and `prx_imports.py` named the remaining import stubs. The named share went from 92.45 % to 99.0 % (28,182 functions; 63 created: request polls, library exports, stubs). `card_effects.py --check` and `ai_tables.py --check --functions` still pass.

Quality sample of the first round (seed 20261031, re-read against the current decompilation): 30 `duel_effects_<slot>_<card>` handlers re-derived from a freshly generated `card_effects.jsonl` (slot and card list identical in 30/30, bodies consistent with the slot role: step machines for `resolve`, booleans for `condition`, filters and candidate collectors), 10 thunks and import stubs re-resolved by NID or thunk target (10/10), and 40 names given by reading (40/40 consistent with the body; two, `ui_cmd_move_list_card` and the `chr1f` cut-in callback, can only be checked as far as the draw-command and character tables go). Error rate in the sample: 0/40 mechanical, 0/40 read. Outside the sample, reading the packs found 9 wrong names, all corrected: `system_acosf`, `audio_stop_track`, the two Datatron evaluators, `duel_core_request_pick_hand_cards`, `world_field_req_bind_ui`, and 8 `rel_duel_draw` `ui_stub_noop_*_text` functions that are lost tail calls to the font functions (`ui.md`).

Still unnamed (281 registry rows, about 1 %): 52 own functions and the 229 thunks/stubs that point at them. They are kept unnamed because no H/M name exists: getters, setters and swaps of single globals whose meaning is unknown (`0x08823dac`, `0x0882ef28`, `0x0882ef3c`, `0x088359dc`/`e8`, `0x0883744c`/`58`, the 13 constant-address getters `0x0885bd4c`–`0x0885bddc`, `0x08850610`–`0x088525c4` in the net API, `0x08867f7c`, `0x0886d86c`, `rel_duel_draw` `0x098a3db8`, `0x098a6194`–`0x098a6a8c`, `rel_duel_eng` `0x09be4bd8`/`0x09be4bf4`); empty or constant stubs without a caller or context (`0x08817270`, `0x0882d338`, `0x08867b28`, `0x0886d8e4`, `0x09be5000`); code fragments that are the tail of a neighbour (`0x0880dc40`, `0x0886f520`); one function the decompiler fails on (`0x09be26f4`); and a few with unexplained mappings or no reader (`rel_field` `0x090cf0b8`, `0x090d0c80`, `0x098419b4`, `0x0985345c`, `0x0989ddb8`, `0x098a35a0`, `0x098a6d44`, `0x09be1dc4`, `0x09cdfbac`).

## Documentation round of 2026-10-31

Method: every program in `ghidra/TF3.gpr` was dumped read-only with the current names (decompilation, callers, callees and tags of every function). Named but undocumented functions were ranked (those already described in `docs/`, exported functions whose import stubs depend on them, then size) and read in packs of 60-110 functions per group; a row was written only when the whole body was read, with the prototype corrected for tail calls and hidden pass-through arguments (in doubtful cases from the disassembly), and skipped otherwise (296 skips: hidden arguments, lost tail calls, unresolved import stubs, failed decompilations, VFPU code, and 3 names contradicted by the body: `rel_deck` `deck_stub_noop_save_stored_deck` is the sceRtc import, `ui_card_viewer_get_frame_tick` returns the frame rate, `ui_help_disable_ruby` is empty). 33 rows whose writer flagged a decompiler artefact or an inferred return value were withdrawn before applying. All prototypes were parsed by `ApplySignatures.java` in a read-only session before the registry refresh. Result: 4,707 functions read and documented, plus 10,856 import stubs whose targets are documented (below). A re-read of 16 random rows against the decompilation found no error. The per-group tables are in `functions/`.

## Import stubs of documented functions

Module import stubs whose target is documented are documented with the target's prototype; they are listed in [`functions/import-stubs.md`](functions/import-stubs.md).

## Registry hygiene (2026-11-03)

Before this round 53 own functions had no group and 13 sat in Ghidra pseudo-namespaces `switchD_<jr address>`. Each was read in the disassembly (capstone) and the Ghidra decompilation.

**Not functions: 15 fragments folded into their parents.** The PPSSPP symbol import (`re/names-ppsspp.csv`, "create only" rows) had created functions at blocks that are only reached from inside another function: they use the parent's saved registers (`$s0`, `$s1`, `$t0`, `$t1`) and return through the parent's stack frame or jump back into it. `tools/ghidra/MergeFragments.java` removes such a function and re-derives the parent body from its flow (`CreateFunctionCmd.fixupFunctionBody`); it restores the fragment if the parent does not reach it. Applied to `BOOT.BIN`:

| Parent | Fragments (old names) | Evidence | Parent body |
| --- | --- | --- | --- |
| `sceGuFinishId` `0x08804a1c` | `0x08804b3c`, `0x08804b90` (`caseD_1`, `caseD_2`) | cases of the `jr` at `0x08804a74` (table `0x08876cd8`, 5 entries); use `$s0`, jump back to `0x08804ab4` | 288 → 420 bytes |
| `sceGuSync` `0x088055e4` | `0x0880562c`, `0x08805644` (`caseD_3`, `caseD_4`) | cases of the `jr` at `0x08805608` (table `0x08876cec`, 5 entries); return through the parent's frame (`0x0880561c`) | 72 → 108 |
| `dl_write_light_color` `0x08807a00` | `0x08807ac0` (`caseD_6`) | case of the `jr` at `0x08807a20` (table `0x08876d58`, 7 entries); uses the parent's `$t0` | 192 → 260 |
| `audio_init_voice` `0x08867b30` | `0x08867c94`, `0x08867d08`, `0x08867d10` (`caseD_4`, `caseD_2`, `caseD_1`) | cases of the `jr` at `0x08867c3c` (table `0x0889e3f4`, 6 entries); restore the parent's `$s0`–`$s5` | 356 → 556 |
| `system_mbrtowc_r` `0x0880dbe4` | `0x0880dc40` (`FUN_0880dc40`) | target of the parent's `beqz $a2` at `0x0880dbf8`, jumps back to `0x0880dc0c` | 92 → 120 |
| `audio_set_note_voice_param` `0x0886f50c` | `0x0886f520` (`FUN_0886f520`) and `0x0886f5c8`, `0x0886f5dc`, `0x0886f5f0`, `0x0886f604`, `0x0886f618` (`caseD_0`–`caseD_4`) | loop of the parent (`j 0x0886f530`, back edge to `0x0886f520`) and cases of its `jr` at `0x0886f5b8` (table `0x0889e508`, 5 entries) | 20 → 328 |

The registry loses these 15 rows (28,182 → 28,167 functions). The documented summary of `audio_set_note_voice_param` already described the whole loop and the five cases, so it stands. The empty `switchD_*` namespaces remain in Ghidra and export nothing.

**Grouped, name kept: 51 functions.** None of them has a name with an H/M basis, so they keep the Ghidra default name; a row in `re/names*.csv` that repeats the default name (`FUN_<address>`) gives the group only (`ApplyNames.java` leaves a default name as it is). Evidence and confidence per row are in the name files (section "registry hygiene 2026-11-03"):

- `system` (14): the global setters/getters next to the frame services (`0x088359dc`/`e8` on `0x08ac2574`, `0x0883744c`/`58` on `0x08ac2578`), the display-flip swap `0x08823dac` (`0x089229b0`, read by `system_display_flip`), two empty stubs in the start-up and movie ranges (`0x08817270`, `0x0882d338`) and six net-API functions: the wrappers `0x08850610`, `0x08850664`, `0x08850694` (each `system_net_get_manager()` then a manager method) and the methods `0x08852584` (copies the ad-hoc string `0x08dbfbcc`), `0x088525a4` (+`0xbafc`, +`0xbb00`) and `0x088525c4` (+`0xbb00`).
- `world` (15): the 13 constant-address getters `0x0885bd4c`–`0x0885bddc` return parameter blocks `0x08dc16a8`–`0x08dc1740` for the mini-game scenes; `rel_story` `world_exit_story_scene` and `rel_title` `ui_minigame_menu_launch_game` fill them (partner, variant, light period, −1 slots) before `system_scene_call` with scenes `0xf`, `0x11`, `0x13`, `0x15`, `0x19`, `0x1c`. `rel_field` `0x090cf0b8` (empty debug switch, caller `world_field_debug_main`) and `0x090d0c80` (maps 1–4 to 0/1/2/2, caller `world_bind_map_archive`).
- `audio` (4): `0x08867f7c` / `0x0886d86c` (setter/getter of words that `audio_init` uses) and two `return 1` stubs among the audio functions.
- `field_3d` (4): `0x0882ef28`, `0x0882ef3c` (word swaps between the field-3D draw functions; L), `rel_duel_draw` `0x098419b4` (caller `field_3d_cutin_reset_current`) and `0x0985345c` (word read by `field_3d_board_sync_zone`).
- `duel_core` (6): `0x09be1dc4` (candidate-list word `0x09e29918` in 7..`0x48`), `0x09be26f4` (decompilation fails; called by `duel_core_record_duel_result`), the pair `0x09be4bd8`/`0x09be4bf4` (`0x09e01eb4`–`0x09e01ebc`, set from `rel_duel_mgr` `duel_core_setup_engine_for_duel`), the `return 0` stub `0x09be5000` and the view wrapper `rel_duel_draw` `0x0989ddb8`.
- `duel_effects` (1): `0x09cdfbac`, a predicate on a card id + kind nibble (card `0x1598` for kind 2) among the rule-update functions, without a direct caller.
- `ui` (7): `rel_duel_draw` message-window and info-panel accessors `0x098a35a0`, `0x098a3db8`, `0x098a6194`, `0x098a61a0`, `0x098a6550`, `0x098a655c`, `0x098a6a8c`, `0x098a6d44` (the last toggles the info-panel state `0x09bdd6b4` 1↔2 / 3↔4).

Their import stubs take the group of the target at the next `prx_imports.py` run. Two stub targets in `BOOT.BIN` still have no function at all (`0x0881d8f4`, `0x08832a4c`; stubs `thunk_FUN_0881d8f4`, `thunk_FUN_08832a4c` in every module) and a few `rel_duel_mgr` stubs point at `rel_duel_draw` addresses without a function (`0x0989c464`–`0x0989d4c0`); they are listed under "Open questions".
## Documented functions

The functions of this group that reached the `documented` stage in the 2026-10-31 documentation round (prototype, purpose, return value, side effects and callers, read from the decompilation) are listed in [`functions/system.md`](functions/system.md).

## Functions documented in the 2026-11-04 round

Method: every still-undocumented `system` function (825: 759 in `BOOT.BIN`, 33 in `rel_duel_mgr`, 20 in `rel_duel_draw`, the rest in `rel_duel_eng`, `rel_field`, `rel_story`, `rel_title`) was re-dumped from Ghidra with the current names and read in full, one row per function, in two batches (C runtime, libm, VFPU helpers, heaps, display, file thread and module loader; then input, font, movie player, ad-hoc networking, services and the module-side system code). The C library and the VFPU helper library are identified by PPSSPP's function-hash names; their rows say which standard function each is. Eleven functions the decompiler could not show (three scanf entries behind an unrecovered jump table at `0x088783a4`, VFPU helpers whose results depend on prefix instructions, `system_vfpu_vector4_min` and `system_vfpu_restore_rand_state` whose operands are in VFPU registers) were documented from the disassembly or at the confidence their names and structure allow, which each row states. `0x0881c6fc` was renamed `system_quat_squad` (it computes `slerp(slerp(q1, q2, t), slerp(s1, s2, t), 2t(1 − t))`, not a shortest-path slerp). Full rows: [`functions/system.md`](functions/system.md); 1,734 import stubs follow their targets.

Corrections to the sections above: `0x0881d01c`, which `system_wait_frame` calls, is `sceKernelWakeupThread(*0x08920c44)` (`system_wakeup_scene_thread`): `system_wait_frame` wakes the thread whose id is stored at `0x08920c44` instead of waiting itself (the hand-off that makes the story busy-waits advance; medium). The display uses a **reversed depth range** (50000..10000 with depth test `GEQUAL`), 480 × 272 ABGR8888 with stride 512, draw buffer at VRAM `0`, display buffer at `0x88000`, depth buffer at `0x110000` (batch 1, "Core start-up and display"): a port must invert its depth test or range. Findings by reading batch follow.

### Findings from batch 1 (C runtime, VFPU library, core start-up and display)

Scope of this batch: the first half of `BOOT.BIN`'s `system` group, `0x08804000`–`0x08822f00`: the newlib syscall layer, libm (single precision), the stdio/stdlib/mprec parts of newlib, the module-reentrancy glue of Sony's libc port, the VFPU vector/matrix/colour/random helper library, the 4x4 matrix helpers used by the EHF UI renderer, core start-up, display set-up and flip, and one debug screenshot routine. 336 functions: 325 rows, 11 skipped.

#### C runtime: newlib with a PSP syscall layer

- **Syscalls** (`0x08804000`–`0x08804670`): `system_sys_open/read/write/close/lseek` map descriptors 0/1/2 to `sceKernelStdin/Stdout/Stderr` and return `0xfffffff7` (−9) for a negative descriptor. `system_sys_open` translates newlib `O_*` flags to `PSP_O_*` (access mode +1, `O_APPEND 0x8 → 0x100`, `O_NONBLOCK 0x4000 → 0x4`, CREAT/TRUNC/EXCL kept) and always passes mode `0x1a4` (0644). `system_sys_fstat` reports every descriptor as a character device (`st_mode = 0x2000`) and `system_sys_isatty` always returns 1, so stdout is line buffered. Eleven other syscall slots are `return -1` stubs (one stores −1 through its pointer and returns 0). `clock/time/gettimeofday` forward to `sceKernelLibc*`. Nothing in the game uses file I/O through stdio; the game's own file layer is `container_*`.
- **`_r` wrappers** (`system_close_r`, `_read_r`, `_write_r`, `_lseek_r`, `_fstat_r`, `_sbrk_r`): clear a **global errno at `0x08dce4c0`**, call the syscall and copy that errno into `reent->_errno` on −1.
- **`sbrk`** (`system_sys_sbrk`, high): the heap that newlib `malloc` grows into is one block from user partition 2 named `UserSbrk`, allocated on the first call with `sceKernelAllocPartitionMemory(2, "UserSbrk", 3, size, 0x1000)`; `size = *(u32 *)0x0889ed5c × 0x400` (a KiB count, the usual `sce_newlib_heap_kb_size` variable). State: break `0x08916dd0`, start `0x08916dd4`, end `0x08916dd8`, block id `0x08916ddc` (freed by `system_sys_free_heap_partition` from `system_module_stop`). The value at `0x0889ed5c` was not read here; it bounds every `system_malloc` allocation (memory budget for the port, see open questions).
- **malloc** is dlmalloc 2.6 as shipped with newlib: bin array `0x0889e954` (top chunk pointer at `0x0889e95c`, last remainder `0x0889e964/68`), bin map `0x0889e958`, sbrk base `0x0889e94c`, trim threshold `0x0889e950`, top pad `0x0891f7c0`, sbrked total `0x0891f790`, maxima `0x0891f7b8/0x0891f7bc`. Lock/unlock are `system_malloc_lock/unlock` (documented earlier). Chunks are 16-byte aligned with a minimum of 0x10 bytes.
- **Reentrancy structure** (`system_reent_init`, high): newlib `struct _reent` with errno `+0x00`, stdin/stdout/stderr pointers `+0x04/+0x08/+0x0c` pointing at embedded FILEs `+0x268/+0x2c4/+0x320` (FILE = `0x5c` bytes), `__sdidinit +0x38`, `__cleanup +0x3c`, dtoa result `+0x40/+0x44`, pow5 cache `+0x48`, Bigint free lists `+0x4c`, locale `+0x30/+0x34`, `rand` state `+0xa8/+0xac` (matches `system_rand`), rand48 seed/multiplier/addend `+0xb0`–`+0xbc`, atexit list `+0x148` with the static block at `+0x14c`, glue `+0x25c` (count `+0x260`, iobs `+0x264`), and a PSP addition at **`+0x37c`: the owning module id**. The global struct is `0x0889e5b0`.
- **Per-module reentrancy registry** (Sony libc port): `system_register_module_reent(module_id, reent)` / `system_unregister_module_reent` / `system_get_module_reent` keep a hash chain at `0x0891f7cc` of `0x104`-byte blocks `{next, reent[32], id[32]}` keyed by `id % 32`. `system_get_module_reent` takes the thread's struct from the k0 thread-local block (`*(k0 + 4)`), reads its module id at `+0x37c`, and falls back to the global struct with a printed libc error. `exit` runs the module's atexit list and `_exit` reclaims the struct and stops/unloads the module (`sceKernelStopUnloadSelfModuleWithStatus` for the main module).
- **Locale / wide characters**: `wchar_t` is **16-bit** (`ushort`) in this build. `system_wctomb_r` switches on the charset name string at `0x0889e938` and supports `C-UTF-8`, `C-SJIS`, `C-EUCJP` and `C-JIS` (ISO-2022 escapes `ESC $ B` / `ESC ( B`); the default charset name returned by `system_locale_charset` (`0x0889e948`) is ISO-8859-1. `system_setlocale_r` only accepts two names. The mbtowc side is the single-byte C locale. None of this is used for game text (the game has its own u16 string helpers and font renderer).
- **printf**: `system_vfprintf_r` is the full newlib engine including floating point via `system_dtoa_r` and the soft-float `libgcc` helpers (`system_muldf3`, `system_divdf3`, compares). The game calls it through `system_sprintf`, `system_snprintf` (only from the two debug screenshot functions) and `system_vsprintf` (from the four `system_font_printf*` functions). scanf exists (`system_sscanf_r`, `system_svfscanf_r`) but its conversion handlers sit behind a jump table Ghidra did not recover (skipped).
- **libm**: fdlibm single-precision `asinf`, `atan2f`, `atanf`, `sqrtf`, `floorf`, `scalbnf`, `copysignf`, `rem_pio2f`, `kernel_sinf/cosf/rem_pio2f`; the `_LIB_VERSION` mode word is `0x08877900` and `matherr` always returns 0. A separate fast `system_fpu_atan` (`0x08818474`) with its own short polynomial is exported to the modules (`rel_duel_draw` camera code) — a port that wants bit-exact camera angles should use that polynomial (constants `0x08878750`–`0x08878774`), not libm.

#### VFPU helper library (`0x08818eb0`–`0x0881ca74`)

- Pattern: `out`-first functions that return `out`, vectors as 2/3/4 floats, matrices column-major (2×2 = 4 floats, 3×3 = 9 floats, 4×4 = 16 floats). The `_t` (three-lane) variants that take 4-float vectors **copy `w` from the first input** (`vadd_t`, `vsub_t`, `vmul_t`, `vdiv_t`, `vscl_t`, `vector4_lerp_xyz`, `vnormalize_t`, `vneg_t`, `vocp_t`, `vclamp_t`); `vcross_t` sets `w = 0`. The `vector3_*` variants write only 3 floats.
- Normalise functions use `vrsq` with a `vcmp`/`vcmovt` guard so a zero vector stays zero instead of producing NaN (medium; the guard's exact effect depends on prefixes).
- Angle conversion constants: VFPU `vcst 5` (2/π) converts radians to the quarter turns that `vrot`/`vsin` expect (`system_vfpu_matrix2_rot`, `matrix3_rot_z`); `vcst 6` (1/π) is used for the half field-of-view in `system_vfpu_matrix4_perspective`. The integer-angle convention of the UI renderer is different: `system_matrix4_post_rotate_z_s16` uses 0x10000 per full turn (`angle × π / 32768`).
- Duplicates: besides the `_b`/`_c` copies named in round 2 there are further copies with `_2` suffixes (`vector4_set_2`, `vector3_set_2`, `vector4_copy_2`, `vector4_lerp_2`, `vector3_lerp_2`, `vector4_is_zero_2`) and `vector4_max`/`vector4_is_equal` that equal `vmax_q`/`vector4_equal`. Most of the library is exported with 8 import stubs and no caller anywhere (dead library code); the functions actually used by the game are listed with their module callers in the rows.
- **Random numbers**: the `system_vfpu_rand_*` helpers use the VFPU hardware generator (`vrndf1` gives [1, 2)), a stream separate from newlib `rand`. `system_vfpu_save_rand_state` copies the eight generator control registers; `system_vfpu_rand_float_keep_state` draws without advancing the stream. No BOOT.BIN or module caller of these helpers was listed, so game randomness (shop packs, AI) still comes from `system_rand` (high).
- **Colour packing (extractor/renderer relevant)**: the helpers pack colours in the GE little-endian layouts with **red in the lowest bits**: 5650 (`r | g << 5 | b << 11`), 4444 (`r | g << 4 | b << 8 | a << 12`), 5551 (`r | g << 5 | b << 10 | a << 15`, alpha bit set when `a > threshold`), 8888 (`r` in the low byte). Unpacking scales by 1/15, 1/31 (and 1/63 for green). This matches the GE texture/vertex colour formats the port must decode from GIM/TGM data.

#### Matrix helpers used by the UI renderer

`system_matrix4_inverse_rigid` (transpose + `-Rᵀt`), `system_matrix4_rotate_vector3`, `system_matrix4_copy`, `system_matrix4_determinant`, `system_matrix4_inverse` (general cofactor inverse, no singularity check) and `system_matrix4_post_rotate_z_s16` are plain FPU code called from `ui_ehf_*`; all column-major with translation in elements 12–14.

#### Core start-up and display

- `system_init_core(config)` (`config = 0x088a0154`): `config[5]` → display argument, `config[6]` → frame rate (30 here, anything else means 60), `config[0]` root path table for the file thread, `config[1]/[2]` module-registry arguments, `config + 3` GE layer configuration. Order: display, file thread, module registry, GE layers, pad, VRAM allocator.
- **Display set-up** (`system_display_init`, high): 480×272, pixel format 3 (ABGR8888), frame-buffer stride 512 pixels; draw buffer at VRAM offset `0`, display buffer at `0x88000` (512×272×4), depth buffer at `0x110000` (stride 512); EDRAM address translation `0x800`; offset `(0x710, 0x778)` = 2048 − 240/136, viewport centred at 2048. **Depth range 50000..10000 with depth function 7 (GEQUAL)**: the game uses a reversed depth range (near maps to the larger value), so a port must invert its depth test or the range. Scissor test on, dither and blend off, front face CCW. A GE finish callback (`system_sample_hcount`) samples the accumulated hcount each frame (`0x089229ac`), the flip stores the hcount after the vblank wait (`0x089229a8`): a simple GPU/CPU-time profiler.
- **Flip** (`system_display_flip`): at 30 fps it enforces two vblanks per frame via `sceDisplayGetVcount` and `0x089229bc`; before `sceGuSwapBuffers` it calls an optional hook at `0x089229b0` (the swap function `0x08823dac` named in the registry hygiene notes writes it). Bit 0 of the frame counter `0x089229b4` tells which of the two buffers is on screen (`system_debug_save_screenshot_bmp` uses that).
- **Scene frame**: `system_scene_run_frame` calls the frame callback of entry `*(0x08920ca8)` in the 12-byte table `0x08920c48` and returns the entry's id.

#### Debug features

`system_debug_save_screenshot_bmp` writes the displayed frame to `host0:` as a 24-bit top-down BMP named with a 6-digit counter (probing for the first free number, counter `0x089229c0`). It is exported but has no caller (the TGA twin calls `system_snprintf` as well); it only works under a host file system (PSPLink/emulator).

#### Corrections to existing docs

- `docs/subsystems/system.md` describes `0x0881d01c` as "the wait" called by `system_wait_frame`. The function (`system_wakeup_scene_thread`) is a single `sceKernelWakeupThread(*(0x08920c44))`; `system_wait_frame` therefore *wakes* another thread (most likely the scene/ehscript thread whose id is stored at `0x08920c44`) rather than waiting itself, and the busy-wait behaviour of the story handlers must come from that thread hand-off (hypothesis, confidence medium; needs a look at who sleeps on that thread id).
- `system_atoi_r` (`0x0880a498`, 12 bytes) is an entry point that continues into the `_strtol_r` body; its decompilation is the strtol loop, not a separate function body.

#### Name mismatches

- `0x0881c6fc` `system_quat_slerp_shortest`: the body is **squad** (spherical quadrangle interpolation): `slerp(slerp(q1, q2, t), slerp(s1, s2, t), 2t(1 − t))`, six arguments. The shortest-path flip it was probably named after is inside every slerp, including `system_quat_slerp`. Suggested name: `system_quat_squad` (high).
- `0x0881ba18` `system_vfpu_rand_float_times_cst5`: multiplies by VFPU constant 5 = 2/π, i.e. a random value in [0, 2/π) (medium; prefix constant not confirmed). The name is accurate but uninformative.
- `0x08804660` `system_stub_set_minus1_sys_08804660`: returns 0 after storing −1, not −1 like its neighbours; which syscall slot it fills is unknown.
- `0x0881c550` `system_vfpu_matrix_mogrify`: converts a quaternion to a rotation matrix (the libvfpu name); a descriptive alias would be `system_quat_to_matrix4` (medium).

#### Open questions (batch 1 (C runtime, VFPU library, core start-up and display))
- The newlib heap size: the KiB count at `0x0889ed5c` (read it from the BOOT.BIN data) gives the size of the `UserSbrk` block and hence the upper bound of all `system_malloc` memory.
- `0x0881ca74` `system_vfpu_restore_rand_state`, `0x0881b8c8` `system_vfpu_vector4_min`, `0x0881be70` `system_vfpu_matrix4_build_projection`, the colour-normalise pair `0x0881b92c`/`0x0881b960`, the adjugates `0x0881a704`/`0x0881adf8` and `0x08819e34` `system_vfpu_vector4_wrap_angle` need the disassembly (VFPU prefixes, control-register writes or stack arguments the decompiler drops).
- `system_vfpu_color_from_rgb565`: the decompiler shows the green field as `(c & 0x7f) >> 1`, which cannot be the 6-bit field at bits 5–10; check the `ext` instruction in the disassembly.
- `system_display_init` ignores its first argument (`config[5]`) in the decompiled body; confirm in the disassembly whether it is passed on (for example to `dl_write_framebuffer_ptr`).
- Who sleeps on the thread id at `0x08920c44` (woken by `system_wakeup_scene_thread` from `system_wait_frame`)?
- `__svfscanf_r` (`0x0881593c`) and its two wrappers: recover the jump table at `0x088783a4` if scanf turns out to be used (no game caller of `system_sscanf_r` was seen in this batch).

### Findings from batch 2 (input, display lists, heaps, movie player, font, ad-hoc network, module-side code)

Scope: 489 functions of group `system` (BOOT.BIN `0x088233d0`-`0x0885f834` and `0x08867178`-`0x0886784c`; rel_duel_draw, rel_duel_eng, rel_duel_mgr, rel_field, rel_story, rel_title). Basis: the Ghidra decompilation in the reading packs (no runtime trace). All 489 rows written, none skipped; rows with partly hidden values carry a "(hypothesis, confidence medium)" note.

#### Pad state block (`0x08924900`, written by `system_pad_update` once per frame)

| Offset | Field |
| --- | --- |
| `+0x00` | buttons held (SceCtrlData buttons) |
| `+0x04` | newly pressed this frame |
| `+0x08` | released this frame |
| `+0x0c` | pressed or auto-repeated (per-button repeat, below) |
| `+0x10` / `+0x14` | analog x / y (0..255, centre 0x80) |
| `+0x18` | buttons with the stick folded onto the d-pad bits: x < 0x41 -> 0x80 (left), x > 0xbe -> 0x20 (right), y < 0x41 -> 0x10 (up), y > 0xbe -> 0x40 (down) |
| `+0x1c` / `+0x20` | pressed / released of `+0x18` |
| `+0x24` | menu repeat of `+0x18`: fires on any change, then after 15 identical frames every 4th frame (counter `0x08924938`) |
| `0x08924928` | last raw SceCtrlData (16 bytes), reused when `sceCtrlPeekBufferPositive` returns < 1 |
| `0x0892493c` | hold mode: with HOLD (0x20000) the stick reads as centred |
| `0x08924940` / `0x08924941` | repeat delay / interval in frames (set from the frame rate: rate x 30/60 and rate x 8/60) |
| `0x08924944` | 32 signed byte counters, one per button bit |

Repeat algorithm (`system_pad_update_repeat`): released -> counter = -(delay - interval); held -> counter + 1, and when it reaches `interval` it is reset to 0 and the bit fires. So the first repeat comes `delay` frames after the press and then every `interval` frames. Port: the 3DS HID layer can produce the same 10-word record.

#### Display-list layers (`0x08924964`-`0x089249cc`)

The game builds one GE list per frame in a buffer split into two halves (base `0x08924964` uncached, size `0x08924968`, current half `0x08924974`, list start `0x08924978`). The start of each half holds 16 two-word link slots (`0x0892497c` points at them), then FINISH/END, then the code area. Each of the 16 layers has a write pointer (`0x08924984 + 4·layer`, current layer `0x08924980`). `system_ge_link_layers` chains the used layers in index order with BASE+JUMP pairs (unused layers are skipped by copying the next slot), `system_ge_submit_frame` sends the list with `sceGuSendList` and restarts in the other half. Layer numbers seen: 0 (duel clear), 10 (fades in rel_duel_mgr), the font layer byte `0x08d9ea98`.

"open_list"/"close_list" pairs (`ehge`, `ehgim`, `ehgum`, `tgmodel`, `ygsys`, `duelmgr`): `open` finishes the libgu context (`sceGuFinish`) and commits the layer write pointer just before the two words libgu appended, so the caller can write raw GE words; `close(ptr)` commits `ptr` and restarts libgu on the layer with `sceGuStart(2, …)`. The (file, line) arguments ("ehge.c", 0x314; "duelmgr.c", 0x427) are unused debug data.

`system_ge_enable` / `system_ge_disable` take libgu's state numbers (GU_ALPHA_TEST 0 … GU_FRAGMENT_2X 21) and write the GE opcodes directly; scissor (2) and fragment-2x (21) keep shadow state at `0x08924a4c`-`0x08924a70`. `system_ge_write_matrix` modes are libgu's (0 projection 0x3e/0x3f, 1 view 0x3c/0x3d, 2 model 0x3a/0x3b, 3 texture 0x40/0x41). `system_ge_draw_sprite_flipped` draws a through-mode sprite with vertex type 0x800102 (u16 uv, s16 xyz), size from `0x08924a98`-`0x08924aa4`, flip modes 1/2/3.

gum matrix stacks (`system_gum_init(stack, n0, n1, n2, n3)`): one buffer of 64-byte matrices, per mode base/current/top at `0x08923158 + 12·mode`, per-mode enable words `0x0892318c`-`0x08923194`, dirty word `0x08923188`, mode `0x08923150`.

VRAM bump allocator: `0x08923144` start = EDRAM + `0x158000`, `0x08923148` current, `0x0892314c` remaining. EDRAM below `0x158000` holds the two 512 x 272 x 4 frame buffers (`0x0`, `0x88000`) and a depth buffer (inferred from the movie player and screenshot code, which use EDRAM + 0 / + 0x88000 / + 0x110000).

#### HOGE heap internals (complements `docs/formats/system-runtime.md`)

- The block table is kept low in the heap: after an allocation or free, `system_heap_relocate_block` moves the table into a free block that precedes it.
- Growing the table (`system_heap_grow_table`): absorb the following free block when possible (capacity doubled), else copy the table into the best-fitting free block of twice the capacity (halving the request toward capacity + 0x40 on failure).
- Header byte `+0x04` bits 0-1: a saturating counter (max 3) incremented when the table moves, cleared by `system_heap_compact_table` (merges runs of free blocks). This settles the "flags, meaning unknown" bits of the heap header (confidence medium: only the writers were read).
- `system_heap_split_block(heap, entry, size, from_end)`: from_end = 0 carves from the start of the free block, non-zero from its end (`system_heap_alloc` passes 1, so ordinary allocations come from the end of a free block).

#### Movie player (PSMF, `system_movie_play(path, flags, volume, ring_packets)`)

Sony sample-player structure. Work memory is carved from `0x08924ac0` with 64-byte alignment: control flags, display queue (2 frames of 0x88000 bytes = 512 x 272 x 4, PSM 8888), audio queue (frames of the size returned by `sceMpegQueryAtracEsSize`, 2 entries; timestamp step 0x1053 = 4179 ticks of 90 kHz), reader, video timestamp ring (4), ring buffer of `ring_packets x 4` packets of 0x800 bytes, the sceMpeg instance. Threads: displayThread (prio 0x3e), readThread (0x40), soundThread (0x3d); the caller drops to 0x3f. Streams: AVC 0 and ATRAC 1. Flags: bit 0 keep the audio channel (do not reserve/release), bit 1 any newly pressed button skips, bit 2 skipping disabled; otherwise SELECT (0x1) or START (0x8) skips. Returns 1 when skipped. Frames are copied to EDRAM + 0x88000 / + 0x110000 alternately and shown with `sceDisplaySetFrameBuf(…, 512, PSM 3)`. A/V sync: video late by more than 2 frames (step `0x08924af0` = 2 x 90000 / fps) drops frames, early holds them.

Finding: `system_movie_stub_set_event_flag` is an empty function, so the event-flag bits that the Sony sample sets (EOF 0x4, end 0x8, abort 0xff/0xc00, thread-done 0x10/0x20) are never set in this build; the loop still ends through the reader state and ring-buffer level. `system_movie_reader_is_done` depends on another empty stub and is effectively always true. The UMD read path calls an empty stub where the sample takes the I/O semaphore, so the semaphore is signalled without a matching wait (harmless: max count 1). Port: reimplement a plain PSMF/H.264+ATRAC3plus player; none of this threading is needed.

#### Font renderer (sceFont-based, context `0x08d4de60`)

| Address / offset | Field |
| --- | --- |
| `0x08d4de60` (+0) | glyph texture, 512 x 512, 4 bpp, PSP-swizzled (16-byte x 8-row blocks), 256 cells of 32 x 32 (cell = slot: column slot & 15, row slot >> 4); CLUT at `0x08879200` |
| `0x08d6de60` (+0x20000) | 256 slot records of 8 bytes {u16 char, u16 prev, u16 next, s16 advance} on an LRU list (head `0x08d9ea86`, tail `0x08d9ea88`, count `0x08d9ea84`) |
| `0x08d6e660` (+0x20800) | sorted index of cached characters {u16 char, u16 slot} |
| `0x08d6ea68` / `0x08d6ea6c` | sceFont handles: main font, and a second font for characters < 0x2300 flagged in the byte table `0x08879220` |
| `0x08d6ea70`.. | sceFont allocation arena (bump pointer `0x08d9ea70`, stack-like free) |
| +0x50c14 / +0x50c54 | default colour / shadow colour (`0x08d9ea74`, `0x08d9eab4`) |
| +0x50c18 | line height (`0x08d9ea78`) |
| +0x50c20 | output write pointer (`0x08d9ea80`) |
| +0x50c2a / +0x50c2b | scale x / y in 20ths (`0x08d9ea8a/8b`); floats at +0x50c2c / +0x50c30 |
| +0x50c3c | tab unit (`0x08d9ea9c`) |
| +0x50c48 | line spacing (`0x08d9eaa8`) |
| +0x50c4c | flag word (`0x08d9eaac`, see below) |
| +0x50c58 | command list: 256 records of 16 bytes {u16 type, …, word +4, word +8, word +0xc}; count at +0x51c58 |
| +0x51c5c | cached `rubi_font00.gim` (icon archive) for ruby glyphs, 8 x 8 cells, 16 per row, index = char - 0x3040 |
| `0x08d9eab0` | external list pointer: when set, text is written into a caller's list instead of a layer |
| `0x08d9eaa0` / `0x08d9eaa4` | pen x / y after the last draw call |

Coordinates are in 1/64 pixel throughout (0x40 = 1 px; ruby glyph step 0x1c0 = 7 px). Flag word bits: 0x1 Japanese line-break rules (kinsoku tables `0x088a16a8` (47 chars) and `0x088a1708` (10 chars)), 0x2 colour codes, 0x4 drop shadow (+1 px, colour from luma: black at alpha x 128/255 for light text, x 64/255 for dark), 0x8 Western word wrap (break classes: control/space 0, punctuation `?;:/.-,!` 1, digits and quotes 2, a French space 3), 0x4000 small capitals, 0x8000 ruby (7 px reserved above each line).

Command types: 1 glyph {x, y, slot or char}, 2 scale {x, y}, 3 colour {colour, shadow}, 4 ruby start, 5 ruby end. Control codes in text: `$R` ruby group `base(reading)`, `$f`/`$F` small capitals off/on, `$C<d>` colour (0 = default, else palette `0x088a1604[d % 15]`, `d` hex digit or letter), `$$` literal `$`. `system_font_layout_line` return codes: 0 end, 1 line break, 2 glyph limit, -1 command list full.

Layout cursor (0x48 bytes): +0 text pointer, +4 pen x, +8 pen y, +0xc baseline offset (small capitals), +0x10 right limit, +0x14 characters consumed, +0x18 u16 flags (0x1 inside ruby, 0x2 kinsoku, 0x4 small-caps scale active, 0x8 literal `$`, 0x10 small capitals on), +0x1c colour, +0x20 shadow colour, +0x24/+0x26 ruby gaps, +0x28/+0x2c ruby pen, +0x30 ruby limit, +0x34/+0x38 ruby line start / step, +0x3c/+0x3d base scale x/y, +0x3e/+0x3f current scale, +0x40 glyph count, +0x44 glyph limit (-1 none). `system_font_split_lines` saves one cursor per line so a text box can resume a page (`system_font_draw_text_box`'s last argument).

Port: glyphs come from the PSP system font (sceFont), not from game files; the port needs its own font with the same advance metrics, the `$` control codes and both line-break rule sets.

#### Screen fade (`0x08d4de48`)

Byte `+0x00` mode (& 0x3f: 1 linear alpha, 2 quadratic alpha, 3 bar wipe), `+0x04` colour RGBA, `+0x08` u16 frame, `+0x0a` u16 duration, `+0x0c` byte direction (bits 0-1 == 0: progress counts down). `system_draw_fade` returns true once frame > duration. The wipe draws 136 one-pixel bars from the right on even lines and from the left on odd lines.

#### LCG streams

`0x0889f494 + 12·stream` (current stream `0x089235b0`): state = state x 0x41c64e6d + 0x3039, result (state & 0x7fffffff) >> 16 (15 bits). Used by `save_import_unscramble` (seeded explicitly) and the fade wipe; rel_duel_draw has its own copy (`system_effect_rand_float` returns result / 32767.0). This is separate from the newlib `rand` stream.

#### Ad-hoc networking (net manager `0x08db3fa8`, "ygadh")

Layers: (1) sceNetAdhocctl + sceNetAdhocMatching lobby (`system_adhoc_*`), (2) the "YgAdhocMsg" reliable message layer over one PDP socket on port 0x315 (`system_net_msg_*`), (3) game data exchange in 0x200-byte peer buffers with phase/state/step synchronisation (`system_net_*`).

Globals block `0x08dbfb00` (0x138 bytes, cleared by `system_net_start`):

| Address | Field |
| --- | --- |
| `0x08dbfb00` | net state (below); `0x08dbfb90` copy |
| `0x08dbfb04` | own hello data (0xb8 bytes): +0 0x32-byte name/profile, `0x08dbfb94` room info (40 bytes: 6 + 32 + u16), `0x08dbfb9a` 0x20 bytes, `0x08dbfbba` u16 tag |
| `0x08dbfb84` | 1 host, 0 client |
| `0x08dbfb88` | member count (host) |
| `0x08dbfb8c` | max peers (9) |
| `0x08dbfbbc` | pointer to the host's hello data |
| `0x08dbfbc0` | selected peer slot (-1 none) |
| `0x08dbfbc8` | cancelled flag |
| `0x08dbfbcc` | own MAC |
| `0x08dbfbd4` | matching context id |
| `0x08dbfbd8` / `0x08dbfbdc` | member count / own member index (0 = host) |
| `0x08dbfbe0` | connect retry counter |
| `0x08dbfbe4` | member MAC list (up to 9 x 6 bytes; index = member index) |
| `0x08dbfc1a` | host MAC |
| `0x08dbfc20` | member being served by the host |
| `0x08dbfc28` / `0x08dbfc30` | 64-bit timestamps (PTP timeouts: 5 s; retry 200 ms) |
| `0x08dbfc38` | 9 peer slots x 200 bytes: +0 state (0 free, 1 new, 2 listed room, 3 accepted, 4 selected, 5 connected, 6 member list delivered), +4 timeout (0xf0 frames), +8 MAC, +0x10 0xb8-byte hello data (+0x94 occupied places, +0xa0 room info, +0xc6 u16 tag) |
| `0x08dc0340` | 8-byte ad-hoc group name (host: 7 random letters) |
| `0x08dc0350` / `0x08dc0356` / `0x08dc035c` | own MAC / host MAC / host flag (game socket) |
| `0x08dc0360` | running-duel flag |
| `0x08dc0368`-`0x08dc0374` | block transfer: size, source, destination, started |
| `0x08dc0380` | 4 peer game-data buffers x 0x200 (byte 0 phase, 1 sender index, 2 state, 3 step / target mask, …); copy at `0x08dc0b80` |

Net state machine (`system_adhoc_update`, `system_adhoc_update_ptp`, `system_net_update`): 0 idle; 1 start scan -> 2 scanning -> 3 scanned; 4 open netconf (connect) -> 5 netconf running -> 0xb lobby (matching started as client); 0xd join requested -> 0x14 established (client) -> 0x15 PTP listen, wait for the member list -> 0x12; 0x11 join failed; host: 0x1d start host matching -> 0x1e accepting members -> (host closes the room) 0x16 open PTP to the next member -> 0x17 connect -> 0x18 send member list -> 0x19 flush -> 0x16 …, 0x1c refused-retry, 0x23 too many retries; 0x12/0x13 disconnect -> 7/9; 7 reconnect to the game group through netconf (create as host / join as client) -> 8 -> open the PDP socket -> 0x1f in game; errors: 10 message dialog shown, 0x21/0x22 and 0x24/0x25 disconnect paths, 0x26 dialog failed, -1 finished. Names of the states are in the pointer table `0x088a707c` (debug strings).

Matching parameters: `sceNetAdhocMatchingCreate(mode 1 host / 2 client, 9 peers, port 1, buffer 0x400, hello 2 s, keep-alive 2 s, 3 retries, 500 ms)`, hello data 0xb8 bytes; `sceNetAdhocctlInit(0x1c00, 0x30, product 0x088a68d8)`; PTP port 0x42 (member-list distribution only); PDP port 0x315 (game traffic). Matching events are copied by the callback into a 64 KiB ring of 0xd4-byte entries (`0x08d9fac4`, tagged free/used) and posted to the mailbox "Mevent", drained once per frame.

YgAdhocMsg message (10-byte header + payload, buffer `0x08dc13a0`): +0 magic 0xab, +1 type (0 game, 1 ack, 2 keep-alive; init value 3), +2 0, +3 message number (`0x08dc16a0`, incremented per queued message), +4 ack-required, +6 u16 checksum = byte sum of the payload, +8 u16 payload length, +10 payload (up to 0x2f6 bytes). Queues: 30 entries of 0x30c bytes {MAC, size, message} (send queue at manager +0x20, receive queue at +0x5b94). Reliability: only the head of the send queue is in flight; it is re-sent every 120 message-thread steps (one step per vblank); the receiver acks the last number it got (ack every 40 steps, first one 3 steps after a receipt); a broadcast message completes when every other member acked it (flags `0x08dc139c`). Keep-alive every 120 steps. Any hard send/receive error moves the net state to 0x24 and deletes the socket. Identical consecutive payloads to the same MAC are not queued again.

Game data: packets start with phase byte 0; 7 and 10 are logged-only, 10 = short broadcast {seq +6, two bytes +0x10/+0x11}, 11 = duelist value (byte 5 sender, word +0x10 written into the duel setup tail block for the duelist whose peer index matches). Phase 8 = block exchange in 0x80-byte chunks (byte 2: 1 data, 2 ready; byte 3 chunk number). With 2 members data goes straight to the partner; with 3-4 members clients send to the host and the host relays (byte 1 = original sender), during the duel byte 3 is a target bit mask (0x0f = all). Sync: `system_net_set_sync_target(phase, state, step)` with wildcards 0xc / 4 / 0xff; `system_net_update` recomputes the synced flag (+0xbb4c) every frame.

Link watchdog in game (`system_net_check_beacons`): every member is queried with `sceNetAdhocctlGetPeerInfo`; 0x1c2 (450) misses before the first contact or 300 after it (3000 / 0x1194 with game-global flag 4) declare the link lost (+0xbb14). `system_net_watch_umd_state`: 90 frames of SELECT held or 900 frames of UMD drive state 0x9 set the abort byte +0xbb15, which ends the session (state 0x24) when +0xbb00 is set.

Manager fields (`0x08db3fa8 + offset`): +0 message layer (owner +0, PDP socket +4, thread +8, counters +0xc..+0x1c, queues +0x20 / +0x5b94, read-index memo +0xb708, vtable +0xb70c), +0xb710 room block (member list 100-byte entries from +4, MACs +0x388, ignore list count +0x3c0 / MACs +0x3c4 (max 3), counters +0x3dc/+0x3e0, vtable +0x3e4), +0xbaf8 running, +0xbafc dialog-on-loss, +0xbb00 abort watch, +0xbb04 alive members, +0xbb08 host-wait counter, +0xbb0c/+0xbb10 abort counters, +0xbb14 link lost, +0xbb15 abort, +0xbb18 "ygadh_hold" FPL (0x5f000 bytes), +0xbb1c frame counter, +0xbb20 per-member watchdog {seen, misses} x 4, +0xbb40-+0xbb4c sync target and flag, +0xbb4d broadcast sequence, +0xbb54 vtable.

Port: ad-hoc play maps to 3DS local wireless (UDS); the protocol needs to be reproduced only if PSP interoperability is wanted (it is not); the per-phase data layout of the 0x200-byte buffers is what the duel code depends on.

#### Utility dialogs

Netconf parameter block `0x08db3ad0` (0x44 bytes): size, language (`system_get_utility_language`: game 0-5 -> utility 0, 1, 4, 2, 5, 3), button swap, thread priorities 0x33/0x35/0x34/0x10, result +0x1c, action +0x30 (2 connect, 4 create, 5 join), ad-hoc parameters +0x34 -> `0x08db3b14` (8-byte group name, timeout 30 s or 120 s with game-global flag 4). Message dialog block `0x08db3b20` (0x2c4 bytes): mode +0x34 (0 error code at +0x38, 1 text at +0x3c, UTF-8 from a sysmsg string), result +0x1c. Utility modules 0x100/0x101 (net) are loaded for the session and unloaded at the end.

#### Start-up (BOOT.BIN)

`system_module_start`: SDK version 0x03090510, compiler 0x30306, thread "user_main" (priority/stack/attributes from `0x0889ed70` / `0x0889ed6c` KiB / `0x0889ed74 | 0x80000000`). `system_user_main_thread`: sbrk init, argv split (max 20), reentrancy structure on the stack registered for the module and in k0+4, `atexit(0x08817270)` (empty), then `system_main`. C++ statics: `system_register_global_destructor` keeps a list at `0x08dc1390`; the net manager, its message layer and queues are C++ objects with vtables at `0x08916d88`, `0x08916d94`, `0x08916da0`, `0x08916dac`.

#### Module-side system code

- rel_duel_mgr state machine (`0x08eba03c`): 1 duel running, 2 prepare, 3/4 duel start screen, 5 start duel -> 0xb (wait for the fade), 6 finish, 7 result screen, 8 deck swap (sub-state `0x08eba040`, return state `0x08eba03e`), 9 load draw+engine -> 10 tutorial, 0xc debug entry, 0x12 leave the link, 0x13 exit. Fade sequencer `0x08eba042` (7 fade-in, 6 fade-in then state 1, 5 fade-out 64 frames then state 6, 4/3/2/1 completion steps). Heaps: FPL "Resource" 0x7bd000 and "Movie" 0x1c8000, each holding a HOGE heap (`0x08ebaa54` / `0x08ebaa58`). Modules loaded: 9 rel_duel_draw (with option block {0x14, 0, 0x4000, 0, 0}), 8 rel_duel_eng, the movie modules, 10 rel_deckswap, 0xb rel_tutorial. Duel mode 5 from the title is an auto/demo duel that ends after 0xe10 frames (2 min) or any key (hypothesis, medium). Setup modes 5/6 save and restore 8 bytes of the save state at `+0xfe04`.
- rel_duel_draw stand-alone scene (scene 3): FPL "HeapMain" 0x900000 and "HeapMovie" 0x200000; recipes 0 and 1; ends on SELECT; a test/debug duel. Draw heaps at `0x09bdd008` / `0x09bdd00c`.
- rel_story heap: 0x200000 bytes at `0x08ececb0` (`0x08ecec94`).
- rel_title: the first title state is chosen from the scene transition (table in the `system_title_scene_start` row).

#### Corrections and additions to existing docs

- `system.md`, family table: the net message header magic is 0xab and the checksum is a 16-bit byte sum of the payload (not a CRC); the ring queue has 30 entries of 0x30c bytes.
- `system-runtime.md`, heap header `+0x04` bits 0-1: a saturating move counter (see above), medium.
- `system_ge_reset_state_list`: the static list `0x0889eed0` is re-enqueued every flip with the frame-parity words at +0x270/+0x274 patched (double buffer).
- The libgcc fp-bit names (`system_fp_*`, `system_*df*`) are confirmed by the bodies; the six compare functions differ only in the NaN result (eq/ne/lt/le 1, gt/ge -1), which matches libgcc, so the order-based names are right.

#### Name mismatches

- `system_font_is_no_line_start_char` / `system_font_is_no_line_end_char` return true when the character is NOT in the forbidden table (i.e. "may start/end a line"); the callers use them that way.
- `system_wcs_format_hex_padded` does not produce hexadecimal: it divides by 10 and takes the remainder modulo 15 (bug in the game); `%x` in `system_swprintf` is therefore broken, and the letter base passed for `%X`/`%x` ('X' - 0x17) would give 'K'/'k' for digit 10.
- `system_movie_read_sectors` is the sceMpeg ring-buffer callback (reads packets, not sectors as such; same size 0x800).
- `system_movie_flush_video` is the whole decode loop, not only a flush.
- `system_font_draw_glyph_sprite_8x8`: its range test is always true (draws every character).
- `system_duel_mgr_stub_noop_*` (rel_duel_mgr `0x08eb5894`-`0x08eb58b4`): 8-byte entries in the import-stub area; by their call sites they are unresolved import stubs of `libdeck_swap_rel` and `libtutorial_rel` (start/update/draw), not game no-ops (medium).
- `system_get_file_size_from_offset` leaves the file open.

#### Open questions (batch 2 (input, display lists, heaps, movie player, font, ad-hoc network, module-side code))
- `rel_duel_draw` targets without a function in Ghidra, called from rel_duel_mgr: `0x0989c638` (every duel frame, argument word `0x08eb8afc`) and `0x0989c6c4` (tutorial busy flag). Create and read them.
- `system_net_check_beacons`: the beacon-age comparison uses a timestamp the decompiler shows uninitialised (probably a field of the `sceNetAdhocctlGetPeerInfo` record); check in the disassembly.
- `system_get_word_08ac2574` / `system_set_word_08ac2574` (title/tutorial list value passed to title state 0x18) and `0x08ac2578`: meaning still unknown.
- The second sceFont handle `0x08d6ea6c` and the character table `0x08879220`: which font (Latin vs. Japanese) and which characters are flagged.
- Hello-data layout beyond the fields used here (0xb8 bytes; +0x80 must be 1 for a room to be listed).
- rel_title `system_title_register_scene` passes `0x09aedfc0` as the scene argument, outside the module image; check the relocation.

## Open questions

- Import stubs whose target has no function in Ghidra (registry hygiene 2026-11-03): `BOOT 0x0881d8f4`, `0x08832a4c` and the `rel_duel_draw` targets `0x0989c464`-`0x0989d4c0` of `rel_duel_mgr` stubs. Create the functions (a create-only row) and read them.

- Heap size and placement (needed later for memory-budget estimates on 3DS).
- From the 2026-11-04 round: two `rel_duel_draw` addresses that `rel_duel_mgr` calls every duel frame (`0x0989c638`) and for the tutorial busy flag (`0x0989c6c4`) have no function in Ghidra yet; the thread that sleeps on the id at `0x08920c44`; the meaning of `0x08ac2574`/`0x08ac2578`; the value of the newlib heap size word `0x0889ed5c` (the ceiling of every `system_malloc`).
