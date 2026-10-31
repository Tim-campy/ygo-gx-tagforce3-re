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
| `0x0884c6b8` | `system_wait_frame()` | M | `system_rand_shifted()` (discarded) then `0x0881d01c` (the wait); the busy-wait loops of the story handlers call it (`docs/formats/story.md`). Callers `0x0884c6dc`, `0x0884c808`, `0x0884c850` and the module imports. |

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

## Open questions

- Heap size and placement (needed later for memory-budget estimates on 3DS).
