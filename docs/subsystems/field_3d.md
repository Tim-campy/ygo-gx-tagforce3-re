# Rendering data (work package 8)

Entry points found while working on containers, and the 3D model formats.

## Key functions

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x0882f2f0` | `field_3d_set_tgmt_data(ctx, data)` | M | If `data` starts with `TGMT` (`0x544d4754`) it is used in place; otherwise, when `sceGzipIsValid(data)`, it is inflated with `sceGzipDecompress` into one of two alternating buffers (`ctx+0x44`/`ctx+0x48`, size `ctx+0x40`, allocated as `0x1b800` bytes on first use by `0x0882ffcc`) and passed to `0x08830870`. Callers `0x0882f3f4`, `0x0882f97c`, `0x0882fa2c`. |
| `0x08830870` | `field_3d_bind_tmt(tmt) → tmt or 0` | H | Returns 0 unless the magic is `TGMT`. Once (flag bit 0 of `+0x34`): words `+0x04`–`+0x18` become pointers (base + offset), and for each of the `+0x20` entries of the table at `+0x08` (8 bytes each) the word `+4` becomes `table[+0x0c] + 16 × value`. Callers `container_ehp_bind_members`, `field_3d_set_tgmt_data`. |
| `0x08832378` | `field_3d_bind_tma(tma) → tma or 0` | H | Same for `TGMA`: flag `+0x20`, words `+0x04`–`+0x0c`, `+0x14` entries. Caller `container_ehp_bind_members`. |
| `0x0882e524` | `field_3d_bind_tms(tms) → tms or 0` | M | Same for `TGMS`: flag `+0x5c`; words `+0x04`–`+0x14`, `+0x18`/`+0x1c` (only when `+0x3c > 0`), `+0x20` (if non-zero) and `+0x24` become pointers; in each of the `+0x28` objects (0xa4 bytes) four 0x20-byte sub-entries get `+0x1c` = record pointer (`+0x10` table, 0x28 bytes each; −1 → 0) and `+0x20` = `0x0882f050` for type 2, `0x0882ef50` for type 1, else 0; each of the `+0x34` records gets its name pointer relocated and, when the hook `0x08924b14` is set, `record[1] = hook(name)`. Callers `container_ehp_bind_members`, `0x0882f3f4`. |
| `0x08823dc0` | `field_3d_bind_gim(gim)` | H | Clears words `+0x08` and `+0x0c` of the GIM member. Caller `container_ehp_bind_members`. |

Consistency with the disc: every `.gz` member inside an EHP holds a `TGMT` file, and the largest decompressed one is `0x1af58` bytes (`duel/cutin_fujiwara01.ehp:lose206.tmt.gz`), below the `0x1b800` buffer; none of the 8,789 exceeds it.

### Model playback and drawing (read 2026-10-30 with the capstone disassembler; names in `re/names.csv`, status `named` until the signatures are applied in Ghidra)

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x0882fa94` | `field_3d_update_model(inst, step*)` | H | Adds `*step` (1.0 when null) to the frame `inst+0x20`; with loop flag `inst+0x3C` bit 1 wraps by `field_3d_get_loop_length`, else clamps at the frame count; poses with `field_3d_pose_nodes`, or `field_3d_pose_nodes_blend` while bit 0 (cross-fade) is set, with weight `frame × r` (`r` = 1/frame count below 10 frames, else 0.1; table `0x08878c60`); then `skin[i] = world[i] × bone_matrix[i]` for every bone (`sceVfpuMatrix4Mul`); then advances the TGMA frame `inst+0x38` (always wraps) and calls `field_3d_apply_tma`. Called through `libehsys_rel`. |
| `0x0882fd88` | `field_3d_draw_model(inst, hook)` | H | Two passes of `field_3d_draw_pass` (argument 1 = opaque materials, 2 = translucent ones), each between display-list helpers. |
| `0x0882e950` | `field_3d_draw_pass(dl, tms, matrices, pass, inst+0x54, hook)` | M | Per material: pass selection by flag bit 0; group skip (flag bit 3, bit `+0xA0` of `hook+0x10`); animated copy (flag bit 2, `+0x98`); cull face from bit 1; per layer: colour, lighting with material colours (GE `0x54`–`0x57`), alpha test, depth function (`ZTST`), blending, depth mask (`ZMSK`), alpha write mask (`PMSKA`), the layer's texture-map callback, hooks `hook+0`/`hook+4`, then the batches. VFPU-free but long; layer semantics in `tgm.md`. |
| `0x0882e720` | `field_3d_set_texture(dl, texture)` | H | Binds the handle `+4` (or disables `GU_TEXTURE_2D`), `TFUNC` from `+0x0A/+0x0B`, `TEC` from `+0x0C`, `TWRAP` from `+0x10/+0x11`, `sceGuTexOffset(u_off, 1 − v_off)`, `sceGuTexScale(u_scale, −v_scale)`. |
| `0x0882ef50`, `0x0882f050` | `field_3d_apply_texmap_type1`, `…_type2` | L | Layer texture-mapping callbacks installed by `field_3d_bind_tms` for layer type 1 / 2; emit texture-map mode and light-source state through display-list helpers. Exact mapping not decoded. |
| `0x08830944` | `field_3d_pose_nodes(tmt, tms, world, hook, frame)` | H | Walks the bone tree from TGMS `+0x40` (first child / next sibling, climbing back through parents); per node `world = parent × T × R × S` (parent = identity for roots and for flag-2 files); optional per-node callback `hook+4(node, matrix, hook)`. |
| `0x08830d70` | `field_3d_pose_nodes_blend(...)` | M | Same walk sampling two TGMT; translation/scale lerp (`0x08819bb4`), rotation slerp. |
| `0x0883138c` | `field_3d_sample_scalar_track(track, frame) → f32` | H | 0.0 without keys; first/last value outside the keys; binary search; `field_3d_eval_scalar_segment`. Exported (also used by `rel_duel_draw` and `rel_field`). |
| `0x08831314` | `field_3d_eval_scalar_segment(key_a, key_b, frame)` | H | `u = (frame − f_a)/(f_b − f_a)`; tail-calls the Bézier. |
| `0x088312c0` | `field_3d_eval_bezier(v0, h1, h2, v1, u)` | H | `(1−u)³v0 + 3(1−u)²u·h1 + 3(1−u)u²·h2 + u³v1`. |
| `0x088314e4` | `field_3d_sample_rotation_track(out, tmt, track, frame)` | H | f32 keys: identity / clamp / binary search, `system_quat_slerp`, `system_quat_normalize`; flag 4 goes to the s16 variant. Exported. |
| `0x08831788` | `field_3d_sample_rotation_track_s16(...)` | H | Same with `field_3d_decode_quat_s16`. |
| `0x08831a18` | `field_3d_decode_quat_s16(out, in)` | H | Four `s16 / 32760.0`. |
| `0x08831760` | `field_3d_copy_quat(out, in)` | H | Copies four floats. |
| `0x08832428` | `field_3d_apply_tma(tma, tms, mat_copies, tex_copies, frame)` | H | Per entry and drawn layer with an animated texture: UV offset, UV scale, alpha (× 255, clamped) into the instance copies. |
| `0x0882ff84` | `field_3d_get_loop_length(inst) → int` | H | TGMT frame count minus 1 when the loop flag is set; −1 / −2 without instance / animation. |
| `0x0882ffbc`, `0x0882ffc4` | `field_3d_set_group_mask(inst, mask)`, `field_3d_get_group_mask(inst)` | H | Write / read `inst+0x64`. Exported. |
| `0x0881c650` | `system_quat_slerp(out, a, b, u)` | M | VFPU: dot, sign flip, `vasin`/`vsin` weights, linear fallback below 5e-5 (VFPU decoded by hand, lower confidence per `CLAUDE.md`). |
| `0x0881c904` | `system_quat_normalize(out, in)` | M | VFPU `vdot`, `vrsq`, `vscl`. |

In `rel_duel_draw` (base `0x0983fb00`, `re/names-duel_draw.csv`):

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x098a093c` | `field_3d_apply_cutin_camera(etc, frame)` | H | Tracks 0–3 → `2·atan(0.5·t1 / (0.03937·t0))`, near `max(t2, 1)`, far `t3`; node 0 translation/rotation → eye, up `R·(0,1,0)`, target `eye + R·(0,0,−1)`; sets projection (aspect 1.7647) and view. |
| `0x0985b504` | `field_3d_apply_scene_etc(out, etc, frame)` | H | Same camera, plus fog (tracks 4–9), ambient (10–12) and four lights (tracks 20 + 16·i, nodes 1–4) into a scene record (`out+0x30…`, lights at `out+0x60 + 0x3C·i`). |
| `0x0985b44c` | `field_3d_sample_track_rgb(tracks, first, frame) → u32` | H | Three tracks × 255, packed as `R | G<<8 | B<<16`. |
| `0x09842900` | `field_3d_update_visibility_mask(cutin, inst)` | M | Builds a 32-bit mask from tracks 10–41 (bit set when the value is 0), merges overrides `+0x184/+0x188`, calls `field_3d_set_group_mask`. |

Runtime model instance (`tgm_model_instance` in `re/formats.csv`; full 0x68-byte layout table in `docs/formats/tgm.md`, "Runtime model instance"): `+0x00` TGMS, `+0x04`
animation list, `+0x08` its count, `+0x1C` current animation index, `+0x24` previous index, `+0x0C` node
world matrices (64 bytes per bone), `+0x10` skin matrices, `+0x14` TGMT, `+0x18` previous TGMT (cross-fade),
`+0x20` frame (f32), `+0x28` previous frame, `+0x2C` animated material copies (0xA4 per TGMA entry), `+0x30`
animated texture copies (0x28 each), `+0x34` TGMA, `+0x38` TGMA frame, `+0x3C` flags (bit 0 cross-fade, bit 1
loop), `+0x54` draw state, `+0x64` visibility group mask.

Instance helpers in `BOOT.BIN` read at the same time (2026-10-31, capstone; `re/names.csv`):

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x0882f3f4` | `field_3d_create_model_instance(tms, arg) → inst` | M | Binds the TGMS (`field_3d_bind_tms`), allocates through function pointers, clears, sets up matrices; on failure calls `field_3d_destroy_model_instance`. |
| `0x0882f89c` | `field_3d_destroy_model_instance(inst)` | M | Seven frees through the allocator's function pointers. |
| `0x0882fa2c` | `field_3d_set_animation(inst, tmt)` | H | `tmt` ≠ 0: a one-entry animation list (`+0x04` = `&inst+0x14`, count `+0x08` = 1), `field_3d_set_tgmt_data`, frame `+0x20` = 0, index `+0x1C` = 0; `tmt` = 0 clears the list and sets index −1. |
| `0x0882f97c` | `field_3d_play_animation(inst, index, flags) → 0 or −1` | H | Takes entry `index` of the list `+0x04` (bounds `+0x08`); with flags bit 0 saves the current TGMT/index/frame to `+0x18`/`+0x24`/`+0x28` (cross-fade source); stores `flags` in `+0x3C` (bit 1 = loop), sets the TGMT, index `+0x1C`, frame `+0x20` = 0. |
| `0x0882fa88` | `field_3d_set_tma(inst, tma)` | H | `+0x34` = `tma`, TGMA frame `+0x38` = 0. |
| `0x0882ff6c` | `field_3d_get_frame(inst) → f32` | H | `inst+0x20`, or −1.0 without an instance. |

The `step*` argument of `field_3d_update_model` is a small record, not a bare float: `+0` the frame step
(f32), and for cut-ins `+4` a per-node callback (`0x09842c20`), `+8`/`+0xC` its context
(`field_3d_update_cutin` builds it at `sp+0x30`; the backdrop passes only the step, the other words zero).

## Frame timing and playback rate (2026-10-31, read with capstone; high)

The game runs one main-loop iteration per displayed frame and caps it at 30 frames per second:

- `system_main` (`0x08833734`) loops: `system_scene_run_slice`, `system_run_frame_services` (was `save_tick_frame_counter`),
  `system_scene_run_frame` (`0x0881d24c`, calls the current frame callback from the handler table
  `0x08920c48`: 12 bytes per entry = id, frame callback, leave callback; current index at `0x08920ca8`;
  `system_scene_set_frame_callback(id, cb, leave)` `0x0881d2d0` runs the old leave callback and stores
  the new pair), `0x08850e68`, `system_end_frame` (`0x0881d21c`
  → `system_display_flip` `0x08822d10`), `system_check_soft_reset`.
- `system_init_core` (`0x0881d1a8`) passes 30 to `system_display_init(…, fps)` (`0x08822bd4`) when the
  boot configuration word `+0x18` (at `0x088a0154 + 0x18`) is 30, else 60. On this disc the word is
  `0x1e` = 30. `system_display_init` stores it in the timing record `0x089229b4` (`+0` frame counter,
  `+4` frame rate), which `system_get_frame_timing` (`0x08822e20`) returns.
- `system_display_flip` (`0x08822d10`): when the rate is 30 it waits for one extra vertical blank if fewer
  than two have passed since the last flip (`sceDisplayGetVcount` against `0x089229bc`), then always waits
  for the next one (`sceDisplayWaitVblankStartCB`) and increments the frame counter `+0`. That is two
  vblanks per frame: 59.94 / 2 = **29.97 frames per second**, fewer when a frame's work takes longer
  than two vblanks (no catch-up: the next frame then waits only one vblank).
- Nothing changes the rate later: the setter `system_set_frame_rate` (`0x08822e2c`) has no caller in
  `BOOT.BIN` and none in any of the 34 game modules (scan of every import stub; the getter is only read).

Every model update in a duel uses a hard-coded time step of 1/30 s and multiplies it by that rate:

- `ui_run_duel_draw_frame` (`0x0989cf94`, the per-frame body of the duel presentation, reached through
  the frame callback `0x0989cee0` → `0x0989c60c` that `rel_duel_draw` installs with
  `system_scene_set_frame_callback` `0x0881d2d0`) calls `ui_update_duel_scene(dt)` (`0x0985a980`) and the
  cut-in task `0x09840e24(dt)`, both with `dt` = the float at `0x098c5f5c` = 0.0333333 (1/30).
- `field_3d_backdrop_update(dt)` (`0x0985ac5c`) and `field_3d_update_cutin(cutin, dt)` (`0x09841ee4`)
  compute `step = dt × timing.fps` = (1/30) × 30 = **1.0** and pass it to `field_3d_update_model`. The
  cut-in's step is zeroed only when `0x09842e84` returns 0; in this build it always returns 1.

Result: **one animation frame per game frame, nominally 30 animation frames per second (exactly
29.97 Hz when the game holds its frame rate; slower, not skipped, when it drops)**, for field backdrops
and cut-in characters alike; the TGMA texture animation advances by the same step. Confidence high for
the code path (every value is a constant or a write traced to one site); the effective rate under load is
the PPSSPP check F10. The loop length of a looping animation is `frame_count − 1` frames, so a 301-frame
backdrop (`fmagic3720`) repeats every 300 / 30 = 10 s.

Loop flags as set by the callers (`field_3d_play_animation` call sites in `rel_duel_draw`): the backdrop
plays animation 0 with flags 2 (loop, no cross-fade, `0x0985ae5c`); the other four sites, including the
cut-in (`0x09842158`), pass 0 (play once, clamp at `frame_count`). The cut-in sets `+0x174` = 1 in a
tick where the integer frame advanced or reached the loop length.

Both updaters also keep elapsed seconds (`slot+0x1C`, cut-in `+0x54`, `+= dt`) and hand
`trunc(seconds × fps)` to a per-frame event hook (backdrop: `field_3d_backdrop_frame_hook` `0x0985c488`,
empty in this build; cut-in: `0x09842728`).

## Field-spell backdrop manager (`rel_duel_draw`, 2026-10-31; names in `re/names-duel_draw.csv`)

Request path: an engine message reaches `rel_duel_draw` through `rel_duel_mgr` (calls of its import of
`ui_dispatch_draw_command` at `0x08e9b0fc`, `0x08e9d984`, `0x08eab0c0`, …). `ui_dispatch_draw_command`
(`0x09899364`, exported) sorts the 75-entry command table `0x098d0180` (12 bytes: id, argument count,
handler) once with `qsort`, binary-searches the id and calls the handler. **Command 7, one argument** is
`field_3d_cmd_set_backdrop` (`0x09899cdc`) → `field_3d_backdrop_request(id)`. The only sender is the engine
command handler `duel_core_cmd_change_field_spell` (`0x09dbc94c`, command `0x13`, read 2026-10-31): it stores the
command's `b` word in `0x09e2bbc8` (the current field-spell id), posts UI event 7 with it once, waits until event 7 is
no longer busy, normalises the effect records and posts UI event `0x26`. Which ids the rules pass (the field
spell's card id, 0 when it leaves) is still to be traced.

Manager record `0x098e69a0` (`0x220` bytes, cleared by `field_3d_backdrop_init` `0x0985a9d8`): two slots
of `0x28` bytes at `+0x00` and `+0x28` (double buffering for the change-over), `+0x50` current slot,
`+0x54` pending id (−1 = none), `+0x58` scene override flag, `+0x60` scene record filled by
`field_3d_apply_scene_etc`, `+0x1B0` exit-done flag, `+0x1B4` enter-done flag, `+0x1C0` view matrix,
`+0x200`–`+0x20C` field of view, aspect, near, far.

Slot: `+0x00` id (card id; 0 = default; −1 = empty), `+0x04` TGMS, `+0x08` TGMT, `+0x0C` TGMA,
`+0x10` `-etc` TGMT, `+0x14` state, `+0x18` model instance, `+0x1C` elapsed seconds (f32), `+0x20`
"start extras" flag, `+0x24` extra-effect handle (−1 = none).

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x0985a9d8` | `field_3d_backdrop_init()` | H | Clears the record, pending id −1, slot 0 = id 0 in state 1: **every duel starts by loading `fmagic0000`**. Both extra handles −1. Called from the duel draw init `0x0985a838`. |
| `0x0985aa54` | `field_3d_backdrop_term()` | H | Per slot with an instance: stop extras, destroy the instance; clears the record. |
| `0x0985af40` | `field_3d_backdrop_request(id) → 1` | H | If the other slot is busy, or the current one is not in state 3, the id is kept in `+0x54` and retried from state 0. Otherwise other slot = `id`, state 1 (load); current slot state 4 (leave); `+0x1B0` = 0; `field_3d_start_backdrop_transition(1, id, field_3d_backdrop_on_exit_done, 0)`. Callers: command 7, `0x09876e08` (an effect animation that requests id 5788 once its time passes 360), the debug field selector `0x098a1460` (steps through card ids whose `card_db_get_icon` is 2 = Field), and state 0. |
| `0x0985ac5c` | `field_3d_backdrop_update(dt)` | H | Per slot, with an instance: frame hook, `field_3d_update_model(inst, {dt × fps})`, `+0x1C += dt`. State machine: **1** waits for `field_3d_get_backdrop_archive(id)` and an idle other slot, reads the members, `field_3d_create_model_instance(tms, 0)`, `field_3d_set_animation(tmt)`, `field_3d_set_tma(tma)`, time 0, extras flag 1, state 2, current slot = this one, `+0x1B4` = 0, `field_3d_start_backdrop_transition(0, id, field_3d_backdrop_on_enter_done, 0)`, `field_3d_play_animation(inst, 0, 2)` (**loop**), one update with step 0 (pose frame 0). **2** → 3 when `+0x1B4` is set. **3** steady. **4** when `+0x1B0` is set: stop extras, destroy the instance, `field_3d_release_backdrop_archive(id)`, slot emptied (id −1, state 0). **0** issues a pending request. Called by `ui_update_duel_scene` `0x0985a980` when `0x0989cc4c(1, −1)` is non-zero. |
| `0x0985aadc` | `field_3d_backdrop_draw()` | M | Sets a perspective of 0.38397 rad (22°) / aspect 1.7647 / near 0.1 / far 10 and default lights, then `field_3d_backdrop_draw_slot(current)` and `(other)`. |
| `0x0985b0f4` | `field_3d_backdrop_draw_slot(index)` | H | Draws in states 2, 3 and 4 (4 until `+0x1B0`); in state 2, once, `field_3d_backdrop_start_extra`. For display lists 1 and 2: `field_3d_backdrop_set_scene(dl, slot.etc, mgr+0x58, field_3d_get_frame(inst))`, then `field_3d_draw_model(inst, {1, 2, …})`. **The `-etc` scene (camera, fog, lights) is sampled at the model's own frame**, so it loops with the node animation. |
| `0x0985b284` | `field_3d_backdrop_set_scene(dl, etc, override, frame)` | H | `etc` ≠ 0 and no override: `field_3d_apply_scene_etc(mgr+0x60, etc, frame)`; else the default scene `0x0985ba50`. Then projection (`fov`, 1.7647, near, far), view matrix, fog, ambient and four lights into the display list. |
| `0x0985c324` / `0x0985c448` | `field_3d_backdrop_start_extra(slot, id)` / `…_stop_extra(slot)` | M | For eight card ids (4899, 4933, 4934, 4937, 5791, 6759, 6823, 7164) starts a card-specific effect task (`0x0987aee0`, `0x0987b450`, …), handle in `+0x24`; stop ends it (`0x09878644`). |
| `0x0987a56c` | `field_3d_start_backdrop_transition(dir, id, done_cb, arg)` | M | Creates the change-over task `0x0987a604` (special variant `0x0987ad08` for id 5788); the task calls `done_cb` at the end. |
| `0x0985c2b0`, `0x0985c2c0` | `field_3d_backdrop_on_enter_done`, `…_on_exit_done` | H | Set `+0x1B4` / `+0x1B0` = 1 (exit also sets up display list 3). |
| `0x0985afe4` | `field_3d_backdrop_get_current_id()` | H | Id of the current slot. Callers `0x098a1238`, `0x098a1db0` (debug selector). |
| `0x0989f5c0` | `field_3d_get_backdrop_archive(id) → archive or 0` | H | Two archive slots of `0x18` bytes at `0x09adcf20` (`+0` id, `+4` buffer, `+8` in use, `+0xC` loaded, `+0x10`, `+0x14` release pending), buffers of `0x80000` bytes at `0x09adcf50 + slot << 19`. Returns the loaded buffer; else claims a slot, `sprintf("duel/bg/fmagic%04d.ehp", id)`, **if `container_get_file_size(3, path)` ≤ 0 uses `fmagic0000`** (`sprintf` with 0), and starts `container_load_file(3, path, buffer, 0x80000, field_3d_on_backdrop_archive_loaded, slot)`; returns 0 while loading. |
| `0x098a00f8` | `field_3d_on_backdrop_archive_loaded(slot, size)` | H | Size ≥ `0x80000` → reloads `duel/bg/fmagic0000.ehp`; else `container_ehp_bind_with_callback(0, buffer)` and `container_ehp_find_member("filelist-ptrs.txt")`; a missing list or a zero first entry → reloads `fmagic0000`; else loaded. Honours a pending release. |
| `0x0989f7cc` | `field_3d_get_backdrop_members(id, &tms, &tmt, &tma, &etc) → 1/0` | H | The first four entries of `filelist-ptrs.txt`. All 54 archives that have the list hold exactly (`.tms`, `.tmt`, `.tma`, `-etc.tmt`, terminator) in that order. |
| `0x0989f734` | `field_3d_release_backdrop_archive(id)` | H | Frees the archive slot, or marks it release-pending while it is still loading. |

Consequences for the port:

- `fmagic0000` is the default backdrop: the initial id is 0, and any id without an archive, with an
  archive of `0x80000` bytes or more, or without `filelist-ptrs.txt` falls back to it (high).
- `fmagic05.ehp` cannot be shown by this loader: it has no `filelist-ptrs.txt` and is 562,576 bytes
  (above `0x80000`). Its member names appear only in the duel object table at `0x098d0960` (entry id
  `0x10001`, read by `0x0989eb08`…`0x0989edfc`, next to `field-duelsheet01` and `field_card-yamahuda01`
  of `duel/basic*.ehp`), whose archive does not contain them (low: probably an unused leftover).
- A field change is a cross-over: the new archive loads into the second slot while the old backdrop is
  still drawn; the old one leaves when its exit transition finishes, the new one is drawn from state 2.

## Model formats

Documented in `docs/formats/tgm.md` (tool `tools/tgm.py`, which validates all 9,953 TGM members on the disc):

- `TGMS` (`.tms`): mesh. Materials → batches (bone palette of up to 8, GE vertex type) → `sceGuDrawArray` primitives (triangles / triangle strips) over s16-quantised vertices; skeleton with offset matrices.
- `TGMT` (`.tmt`, `.tmt.gz`, `.vtmt.gz`): node animation (three Bézier scalar tracks for translation and for scale, quaternion keys for rotation); `-etc` files add a scene block (camera lens, fog, ambient and four lights, or 32 visibility groups).
- `TGMA` (`.tma`): per material layer UV offset / UV scale / alpha animation, tied to TGMS materials.
- Pointer lists next to them (`<anim>-ptrs.txt`, `all-ptrs.txt`) bundle members (mesh + animations) and index animations by slot.

Posed skinned vertex = Σ weight × node_world × bone_offset_matrix × position (read in `field_3d_update_model`); this places 162 of 196 skinned meshes inside their header bounding box at frame 0, the rest at a later frame.

Export for the port: `tgm.py gltf` (glTF 2.0 + side JSON, `tools/tgm_gltf.py`), described in `tgm.md` "glTF export".

## Function families named in the 2026-10-31 round

Basis and method: `system.md`, same section. 775 new `field_3d` names.

| Module | Families (count) | Evidence |
| --- | --- | --- |
| `BOOT.BIN` (46) | `camera_lights` 18, `gim_texture` 12, `model_instance` 9, `model_draw` 7 | Lighting switch `0x08924c24` (`tgm.md`). `0x088241e0` `field_3d_gim_emit_texture_level` picks the GIM plane as level + level count × frame (caller `0x088384f4`); GIM `+0x08`/`+0x0c` are the VRAM copy pointer and frame set by `0x08824838`, and the texture is used from RAM while `+0x08` still reads "PSP". |
| `rel_duel_draw` (512) | `cutin_chara_blocks` 202, `cutin_core` 58, `cutin_fx_tasks` 49, `duel_board` 32, `fx_matrices` 27, `cutin_fx` 22, `backdrop_extras` 17, `fx_render_state` 16, `pose_tables` 15, `cutin_fx_timing` 13, `cutin_loading` 13, `fx_random` 9 | Cut-ins: 4 slots of 400 bytes at `0x098d4d60`, current slot `0x098d4d48`, `0x38`-byte callback descriptors, loading slots `0x09bdcf54`. 40 per-character blocks (motion start/end and frame-hook wrappers, offset lookup, `bsearch`, `qsort`); the character comes from the labels of `field_3d_cutin_get_chara_setup` (`0x09841264`), each `0x4c` bytes before its block, so 15 blocks are tagged `chr<id>` and 25 by their table address (all M). Cut-in effects are chosen by (character, variant, animation id) into channels `+0xb8`/`+0xbc`/`+0xc0` (slots `0x098e937c`). 3D card objects: per-duelist lists of 16 zones at `0x098e3a60`, free list `0x098e39b0`. Task manager `0x098e7684`: 254 entries of `0x1c` bytes (state, flags, handle, callback, destructor, argument, data); state 1 start, 2 run, 3 stop requested, 4 free; the handle carries the index in bits 24–31. |
| `rel_field` (8) | `field_render`, `field_shadow` | Stencil shadows (M). |

Field-spell extras: the switch of `field_3d_backdrop_start_extra` (`0x0985c324`) ties each creator to a card: `0x0987aee0` Chorus of Sanctuary, `0x0987b450` Umiiruka, `0x0987c598` Molten Destruction, `0x0987d014` Mystic Plasma Zone, `0x0987df00` Pandemonium, `0x0987eb08` Mausoleum of the Emperor, `0x0987f004` Jurassic World, `0x0987f5e0` Venom Swamp; `0x0987ad08` is the Final Countdown transition. The texture-name table `0x098cfe8c` has 36 `.gim` entries; 0x19–0x22 are the per-card field textures. Draw event 7 (`field_3d_cmd_set_backdrop`) is posted only by the engine command handler `0x09dbc94c` (partly answers an open question below).

## Round 2 of the 2026-10-31 naming

Method as in the first round (`system.md`): the still-unnamed functions were re-dumped from Ghidra with the current names, read in packs with full bodies (up to 160 lines), and named H/M with a basis in `re/names*.csv` under "round 2". 109 new `field_3d` names, 99 in `rel_duel_draw`. The effect tasks that the first round knew only by sound id are named after the UI event that starts them, with the sound in the basis (family `card_fx_tasks`, 36): card set (`0x7a17`), summon (`0x7a1c`), destroy (`0x7a18`), Tribute (`0x7a3c`), Fusion/Synchro material (`0x7a38`/`0x7a3c`), card travelling between zones, card pop-up. The event → sender map comes from the draw command table `0x098d0180` and the `jal duel_core_post_ui_event` sites with a constant `a0` in `rel_duel_eng` (read from the module files). Events `0x3c`/`0x3d` are the coin and the dice (object table `0x098d0960`: models `coin01`, `dice01`), event `0x40` the Destiny Board letters (`duel_ouija.gim`), case 7 of the duel-end dispatcher `0x0989bdb0` Final Countdown (win reason 7). Fourteen more per-character cut-in callbacks were tied to characters by disassembling `field_3d_cutin_get_chara_setup`.

## Documented functions

The functions of this group that reached the `documented` stage in the 2026-10-31 documentation round (prototype, purpose, return value, side effects and callers, read from the decompilation) are listed in [`functions/field_3d.md`](functions/field_3d.md).

## Functions documented in the 2026-11-04 round

Method: every still-undocumented `field_3d` function (613: 34 in `BOOT.BIN`, 565 in `rel_duel_draw`, 14 in `rel_field`) was re-dumped from Ghidra with the current names and read in full, one row per function, in three address-ordered batches. This Ghidra project decodes the VFPU through the ghidra-allegrex processor module (pseudo-ops such as `vdot_q`, `vscl_t`); values computed under VFPU prefix instructions (`vpfxs`/`vpfxt`/`vpfxd`), which the decompiler does not apply, are marked lower confidence. Eleven functions whose decompilation hid register arguments or lost its stores (wrappers that move arguments into `t0`, an 8-byte tail jump, the map-variant mask builder) were read from the disassembly with capstone. Full rows: [`functions/field_3d.md`](functions/field_3d.md).

Corrections to the sections above: the group mask `inst+0x64` is a **hide** mask (a set bit skips the material; `field_3d_update_visibility_mask` sets bit i when cut-in scene track 10 + i is 0.0); of the fx textures 0x19–0x22 only 0x19, 0x1b, 0x1d, 0x1f, 0x20 and 0x22 come from the `fmagic<card>.ehp` backdrop archives, the others from duel archive `0x80001`. In `rel_field`, `field_3d_set_map_variant_group_mask` (`0x090da484`, read from the disassembly) hides every group except the five of the chosen variant (variant 0: groups 0–4; 1: 5–9; 2: 10–14), and `world_get_map_variant_for_period` picks the variant from the light period (`world.md`, "Mini-game parameter blocks"). Findings by reading batch follow.

### Findings from batch 1 (BOOT.BIN model pipeline, cut-in core, duel board, card effect tasks)

Scope of this batch: 352 functions (BOOT.BIN model pipeline, rel_duel_draw cut-ins, duel board, backdrop scene, card effect tasks). All facts below come from the Ghidra decompilation of these functions; VFPU-heavy parts are marked.

#### TGMS draw structures (BOOT.BIN, read in field_3d_draw_pass / field_3d_draw_material_batches)

Material record (`0xa4` bytes, table TGMS `+0x0c`, count `+0x28`):

| Offset | Meaning |
| --- | --- |
| `+0x00` | flags: bit 0 translucent (drawn in pass 2; clear = pass 1), bit 1 no back-face culling, bit 2 has an animated copy, bit 3 belongs to a visibility group |
| `+0x04..+0x10` | emissive, ambient, diffuse, specular colours (GE model colours) |
| `+0x14` | specular power (f32) |
| `+0x18` | four layers of `0x20` bytes |
| `+0x98` | index of the animated copy (instance material copies, `0xa4` each); the TGMA applier indexes the same array by TGMA entry number |
| `+0x9c` / `+0x9e` | u16 batch count / first batch index |
| `+0xa0` | visibility group number (bit of the group mask) |

Layer (`0x20` bytes): `+0x00` flags (bit 0 present - a clear bit ends the layer list; bit 1 lighting; bit 2 alpha test; bit 3 blending; bit 4 depth write; bit 5 alpha write mask `0xff000000`), `+0x04` texture record pointer, `+0x08` texture-map callback (called with 0 before and 1 after the batches), `+0x0c` colour (alpha in the top byte, animated by TGMA), `+0x10/+0x11/+0x12` alpha func/ref/mask, `+0x13` depth func, `+0x14/+0x15/+0x16` blend op/src/dst, `+0x18/+0x1c` blend fixed colours.

Batch (`0x18` bytes, table TGMS `+0x14`): eight u16 bone indices (0xffff ends), `+0x10` GE vertex type, `+0x14` primitive count, `+0x16` first primitive. Primitive (`0xc` bytes, TGMS `+0x04`): primitive type, vertex count, vertex offset from TGMS `+0x08`. Bone matrices are uploaded per batch into GE bone slots 0..7 with a cache of the last 8 bone indices at `0x08924b18` (reset to 0xffff at every pass).

Texture record (`0x28` bytes, TGMS `+0x10`, count `+0x34`): `+0x00` name pointer, `+0x04` GIM, `+0x0a/+0x0b` texture function and component, `+0x0c` environment colour, `+0x10/+0x11` wrap u/v, `+0x14/+0x18` UV offset, `+0x1c/+0x20` UV scale, `+0x24` animated-copy index (-1 = none).

Instance draw state (`inst + 0x54`, five words, also the `draw_state` argument of `field_3d_draw_pass`): `[0]` texture callback `(list_ptr, tms, material, layer, hook)` returning non-zero when it bound a texture itself; `[1]` batch hook `(list_ptr, tms, material, layer, stage 0/1, hook)`, a negative result at stage 0 skips the batches; `[2]` material copies; `[3]` texture copies; `[4]` group mask (`inst + 0x64`). **A set mask bit hides the group** (the material is skipped when its group bit is set). `field_3d_update_visibility_mask` sets bit i when the cut-in scene track `10 + i` is 0.0, so a track value of 0 hides the group (correction of the wording "visibility" in field_3d.md: the mask is a hide mask).

Draw hook record (`0x34` bytes; default `0x08924b28`): `+0x00` layer of pass 1, `+0x04` layer of pass 2, byte `+0x08` bit 0 = render the EDRAM ramp textures first, `+0x0c..+0x20` ramp keys (see below), `+0x24` frustum test on, byte `+0x28` bit 0 = write the stencil (func always, ref 0xff, op replace on depth pass). Cut-ins also put the character at `+0x2c` and the slot pointer at `+0x30`.

#### Texture-map callbacks and the EDRAM ramp (BOOT.BIN)

- Type 1 (`0x0882ef50`): environment map driven by the camera: lights 2/3 positioned at camera `+0x80` and `-(camera +0x90)`, GE map mode 2 with lights 2 and 3; restored to the saved lights at stage 1.
- Type 2 (`0x0882f050`): map mode 2 driven by light 0 (`0x08924c28`), colour = light 0 diffuse.
- `field_3d_render_edram_ramp_textures` (`0x08830154`): when hook byte `+0x08` bit 0 is set, renders two 64 x 32 ramps into EDRAM offset `0x1f0000` (pixel formats 0 then 2) from key lists in the hook (ramp 1: positions f32 `+0x0c`, grey levels = high nibble of bytes `+0x10`, count `+0x14`; ramp 2: `+0x18`, `+0x1c`, `+0x20`; default 4-vertex ramps at `0x0889f770`/`0x0889f790` when a count is below 2) and installs `field_3d_setup_edram_texmap_layer`, which rebinds every type-2 layer to the EDRAM texture and swaps its callback to `field_3d_apply_texmap_edram` (adds a blend). Hypothesis (medium): a cel-shading / toon ramp looked up by environment mapping. For the port: this is a 1D lighting lookup; reproduce with a shader ramp.
- EDRAM `0x160000` is a second scratch target: 128 x 256 card faces for cut-in props (`4006.iff`, `0000.iff`) and 128 x 128 off-screen renders (`field_3d_draw_spinning_coin_sprite`, `field_3d_render_model_to_texture_128`).

#### TGMT / TGMA details confirmed

- TGMT `+0x34` flags: bit 1 = every node's parent is identity (flat hierarchy); bit 2 = rotation keys stored as four s16 (`/ 32760.0`, 8 bytes) instead of four f32 (16 bytes). Rotation track = {key count, first key}; key frames u32 at `+0x14`, keys at `+0x18`. TGMT `+0x30` = frame count (end frame = count - 1 when looping).
- Node record (TGMT `+0x04`, 8 bytes): u16 translation track, rotation track, scale track (0xffff = none); translation and scale use three consecutive 8-byte scalar tracks at TGMT `+0x08`.
- TGMS hierarchy (`+0x18`, 8 bytes per node): parent, first child, next sibling; root at TGMS `+0x40`; bone offset matrices at TGMS `+0x1c`.
- TGMA entry (`0x24` bytes, table `+0x04`, count `+0x10`): four 8-byte layer records (u16 UV-offset track, UV-scale track, alpha track; offset/scale tracks are pairs u, v), `+0x20` material index; frame count `+0x1c`. Missing UV offset gives 0, missing UV scale 1.0; alpha x 255 clamped into the top byte of the layer colour.
- `field_3d_pose_nodes_blend` reads the previous animation's translation and scale tracks with the indices of the previous node record without checking them for 0xffff (only the current animation's indices are checked) - a latent bug when the two animations differ in channels.

#### Lighting state and camera (BOOT.BIN)

Lighting block `0x08924c24` (`0xf8` bytes): `+0x00` flags (bit 0 = lighting enabled, read by draw_pass), four light records of `0x3c` bytes at `0x08924c28`, `0x08924c64`, `0x08924ca0`, `0x08924cdc`, ambient colour `0x08924d18`.

Light record (`0x3c` bytes, also used in the backdrop scene): `+0x00` type (0 directional, 1 point, 2 spot), `+0x04` ambient, `+0x08` diffuse, `+0x0c` specular (ABGR), `+0x10` position or direction (3 f32), `+0x1c` spot direction, `+0x28` spot exponent, `+0x2c` spot cutoff (cosine of half the cone angle), `+0x30..+0x38` attenuation (constant, linear, quadratic; default 1, 0, 0; the default backdrop scene uses 0.5).

Camera record (`0xc0` bytes, default `0x08924b60`, current pointer `0x08924c20`): `+0x00` eye, `+0x10` target, `+0x20` up, `+0x30` normalised eye - target, `+0x40` view matrix, `+0x80` camera-to-world (inverse ortho of the view).

#### Cut-in system (rel_duel_draw)

Block `0x098d4d40` (`0x660` bytes): `+0x08` current slot pointer (`0x098d4d48`), `+0x0c` current index (`0x098d4d4c`, -1 none), `+0x10` "finished" override (`0x098d4d50`), four slots of `0x190` bytes from `0x098d4d60`. Fallback model instance pointer `0x098d53c0`.

Slot layout (first `0x38` bytes = the descriptor):

| Offset | Meaning |
| --- | --- |
| `+0x00` / `+0x04` | character id / variant |
| `+0x08` | `duel_disc.gim` |
| `+0x0c` / `+0x10` | `chr_voiceidchgtbl.bin`, language word table (member name from the table `0x098ccacc` indexed by `save_get_language`) |
| `+0x14` | on-motion-start callback `(slot, index, arg)` |
| `+0x18` | on-motion-end callback |
| `+0x1c` | frame hook `(slot, index, frame, model_frame, advanced)` |
| `+0x20` | resolve-motion callback `(slot, motion) -> animation index` |
| `+0x24` | map-node callback (default `0x09843b64`) |
| `+0x28` | attach-offset callback `(slot, pos_out, quat_out, attach_id) -> bool` |
| `+0x2c` | voice-node callback (lip sync) |
| `+0x34` | attach table (pairs id, node; 0 ends) |
| `+0x38` | slot index / duellist index for voices |
| `+0x3c` | assets loaded |
| `+0x40` | model instance |
| `+0x44` | scene list (`alletc-ptrs.txt`) |
| `+0x48` | requested motion id |
| `+0x4c` | current scene TGMT (`-etc`: camera and 32 visibility tracks) |
| `+0x50` | animation index |
| `+0x54` | elapsed seconds |
| `+0x58` | `0x10000`-byte inflate buffer for a gzip scene TGMT |
| `+0x5c` | start pending |
| `+0x60` / `+0x64` / `+0x68` | lip-sync TGMT, its inflate buffer (`0x10000`), its time |
| `+0x6c` | selects `voice02.vtmt.gz` for motions 0x15..0x1c and 0x88..0x90 |
| `+0xd0` / `+0x110` / `+0x150` | saved projection, view, eye |
| `+0x160` | card id shown on prop textures and in ATK/DEF panels |
| `+0x164` | set for motion 9: when the scene leaves group 9 shown, hides group 9 and shows group 10 |
| `+0x168` | hides the duel-disc texture swap |
| `+0x16c` / `+0x170` | LP roll from / to values |
| `+0x174` | frame advanced this tick |
| `+0x178` / `+0x17c` | busy / fade started (frame events) |
| `+0x180` / `+0x184` / `+0x188` | last group mask, override select, override values |

Archive members used by a cut-in (extractor-relevant, all in the character's cut-in EHP from `field_3d_get_cutin_archive`): `info-ptrs.txt` (first entry = mesh) or `cutin_chara_base.tms`, `all-ptrs.txt` (animation list), `alletc-ptrs.txt` (scene list, same indices), `voice01.vtmt.gz` / `voice02.vtmt.gz` (lip-sync animation, nine face nodes from the table `0x098ccda0`), `duel_disc.gim`, `chr_voiceidchgtbl.bin`, per-language word tables, `bustup.gim` (in the base archive, portrait). Generic (player-avatar) characters read the voice tables from the nested member `voice/10000.txt`, and every texture named `DA_boy_R01.iff`, `DA_boy_Y01.iff`, `DA_boy_B01.iff` or `DA_girl01.iff` is redirected to the member `texture/10500.txt` (a nested archive or GIM; format not checked here). Texture names with special handling at draw time: `4006.iff` (rendered card face of slot `+0x160`), `0000.iff` (card back), `duel_disc_02.iff` (swapped for `duel_disc.gim`).

Flow: `field_3d_cutin_setup_slot` (character, variant) -> default descriptor + per-character set-up routine (`field_3d_cutin_get_chara_setup`, about 40 routines; generic characters choose by `world_get_character_byte_09` = 5 or model id byte 1 = 3) -> assets loaded unless a network duel. Playing: `field_3d_cutin_select_slot` -> `field_3d_cutin_reset_current(motion)` -> `field_3d_cutin_set_motion` -> resolve -> `field_3d_cutin_start_motion` (play once, flags 0). Each frame: `field_3d_cutin_dispatch_motion_start` (deferred start callback), `field_3d_update_current_cutin` (dt 1/30), frame hook, `field_3d_draw_cutin_layer` (layers 8 and 9, far plane 10000).

Motion resolution (`field_3d_cutin_default_resolve_motion`): ids >= `0x1000` are direct animation indices (`id - 0x1000`); otherwise the motion table `0x098ccdc4` (12 bytes per motion: ?, first index, last index) gives a range and a random present animation is chosen; motions 1, 0x12, 0x13, 0x14 use a fixed index from `0x098ccf20` per voice-bank range (six ranges between 0x1de and 0x2a9); fallbacks 8 -> 6, 0x10 -> 0xf, then the first present index below 0x199.

Finish rule (`field_3d_cutin_is_motion_finished`): end frame reached, no cut-in voice playing, LP panel closed, slot not busy, and either 150 frames past the end or no SE/voice playing.

Lip sync: `field_3d_cutin_pose_node_hook` overrides up to nine face nodes with the lip-sync TGMT sampled at `voice time x fps` while the duellist's queued voice is at level 10 or more (else at time 0 = closed mouth); skipped for non-generic characters in motions 1, 0x12, 0x13, 0x14 and (except characters 9, 0x13) 0x1a.

Per-character attach-offset tables: five entries of `0x20` bytes (`+0x00` attach id, `+0x04` position, `+0x10` quaternion), sorted once on first use with a per-table flag word (`0x098d53c4` upwards), searched with `bsearch` (comparator `0x098a0d04`). Two families (`tbl098cd540`, `tbl098cdd10`) hold two tables chosen by variant. The default attach table `0x098ccbac` has six entries; ids below `0x29` are plain node indices. The family-to-character mapping of the generated rows comes from the set-up routine addresses returned by `field_3d_cutin_get_chara_setup` lying just before each family's first function (medium).

Timed frame events (`field_3d_cutin_default_frame_events`), by motion id range: 0xd5..0xe6 LP roll at frame 10; 0x82..0x85 LP roll at frame 0x19 then a 60-frame fade-out (and a 16-frame fade-in when the motion ends); 0x32..0x3a and 0x3e..0x54 LP roll at frame 0x19; 0x104..0x114 and 0xba..0xc3 ATK/DEF panel of card `+0x160` on the last loop frame. Motion 0xe7 collects the deck card ids for its effect (`field_3d_cutin_collect_deck_card_ids`).

#### Duel board (rel_duel_draw)

Card object (`0xb0` bytes; pool of `0x140` at `0x098d5db0`, free list head `0x098e39b0`; zone list heads are full objects used as sentinels at `0x098e3a60 + duelist x 0xb00 + zone x 0xb0`, 4 duelists x 16 zones; view side -> duelist map `0x098e6664`):

| Offset | Meaning |
| --- | --- |
| `+0x00` / `+0x04` | list links (next is `+0x04` in traversals) |
| `+0x10` / `+0x20` / `+0x30` | current / start / target position (vec4) |
| `+0x40` / `+0x50` / `+0x60` | current / start / target rotation (quaternion) |
| `+0x70` / `+0x74` | motion time / duration (moving while time < duration) |
| `+0x78` / `+0x7c` | queued destination code / move kind |
| `+0x80` | card id (u16) |
| `+0x82` | location code (u16) |
| `+0x84` | location code copy (u16) used by effects |
| `+0x88` | engine instance |
| `+0x8c` | flags: bit 0 move queued, 2 card-set fx deferred, 3 summon fx deferred, 4 placed-summon fx deferred, 5 relayout/gather pending, 6 reveal flip, 7 busy |
| `+0x8d` | flags: bit 0 busy, 1 raised, 2 flipping, 3 revealed hand card, 4 travel fx running / hidden from pile counts, 5 orientation, 6 slide-only motion, 7 destruction deferred |
| `+0x8e` | bit 0 rotation unchanged, bit 1 raised |
| `+0x90` / `+0x94` / `+0x98` | effect handles (-1 none; `+0x98` = card effect task) |

Location code (u16): bit 0 side, bits 1..5 zone (engine location id: 0..4 monsters, 5..9 spell/trap, 10 field, 0x0b hand, 0x0c Extra Deck, 0x0d Deck, 0x0e Graveyard, 0x0f banished), bits 6..13 index, bit 14 face orientation, bit 15 battle position (hypothesis medium: set from `duel_core_view_get_slot_position`).

Board transforms (`field_3d_board_get_location_transform`): positions table `0x098cec80` (vec4 per side x 16 zones), rotation quaternions `0x098ceea0` (base), `0x098ceeb0` (bit 14), `0x098ceec0` (bit 15), `0x098ceed0` (side 1). Piles rise by `field_3d_board_get_pile_height(n)` = `0x098c4be0 + 0x098c4bdc x n / 120` (constant `0x098c4be4` from 120 cards). Hand layout: side 0 spacing 65 units (400 units for 8+ cards), side 1 spacing 70 (420 units, step 420 / n), cursor card raised. Camera: perspective near 100, far 10000, eye `0x098cef70`, up `0x098cef7c`, viewport `(0x84a, 0x7fc, 0x3c0, 0x220)` (twice the screen size, offset), restored to `(0x800, 0x800, 0x1e0, 0x110)`. Duel object models: `0x10002` mat, `0x10003` pile (animation frame = card count), `0x10021` and `0x10026` off-screen renders. Deck record read by `field_3d_board_build_deck_objects`: `+0x00` main count, `+0x08` extra count, u16 main ids at `+0x0c`, u16 extra ids at `+0xa2` (cross-check with `docs/formats/deck.md`).

#### Backdrop scene record (rel_duel_draw, manager `0x098e69a0 + 0x60` = `0x098e6a00`)

`+0x00` eye, `+0x10` up, `+0x20` target, `+0x30` fov, `+0x34` near, `+0x38` far, `+0x3c` fog on, `+0x40/+0x44` fog near/far, `+0x48` fog colour, `+0x4c` ambient (alpha forced 0xff), `+0x50` four light-enable words, `+0x60` four `0x3c`-byte light records. Saved for effects: view matrix `0x098e6b60`, fov/aspect/near/far `0x098e6ba0..0x098e6bac`, eye `0x098e6bb0`; aspect constant `0x098c4c8c`.

`-etc` scalar track map (from `field_3d_apply_scene_etc`): 0..3 lens (focal, film width, near, far), 4 fog on, 5..7 fog RGB, 8/9 fog near/far, 10..12 ambient RGB, per light i at base `0x14 + 16 i`: +0 type, +1 enable, +2..+4 ambient RGB, +5..+7 diffuse RGB, +8..+10 specular RGB, +11..+13 attenuation (hypothesis), +14 cone angle, +15 exponent; node 0 = camera, nodes 1..4 = lights. The backdrop draws are bracketed by fog off on layer 2; extra card effects for field spells 0x1bfc, 0x1aa7, 0x1a67, 0x169f, 0x1349, 0x1346, 0x1345, 0x1323 (hex card ids of the eight ids listed in field_3d.md).

#### Card effect draw tasks (rel_duel_draw)

Created with `ui_duel_create_draw_task(callback, completion, arg, data size)`; the update returns the next task state (2 run, 4 finished). Float arguments of the creators (yaw, size) travel in a0 as raw bits (medium). Data layouts:

- Card set (`0xb8` bytes, 16 frames, SE `0x7a17`): `+0x00` frame, `+0x04` card id, `+0x08` position, `+0x14` rotation (0, yaw, 0), `+0x20` SE flag, `+0x24` texture value (`ui_get_zone_card_scale`), `+0x28` six fan vertices (type `0x19f`, 24 bytes).
- Summon (`0xc4c` bytes, 24 frames, SE `0x7a1c`): `+0x20` variant (0 normal, 1 placed), `+0x24` SE flag, `+0x28` texture value, `+0x2c` ring quad, `+0x8c` spark cursor, `+0x90` eight 2-vertex sprites, `+0x1d0` 32 sparks x `0x18`, `+0x4d0` 17 x `0x30` column vertices, `+0x800` 8-byte strip index list, `+0x808` particle cursor, `+0x80c` six particle quads, `+0xa4c` 32 particles x `0x10`.
- Destroy / shatter (`0x2508` bytes, 24 frames, SE `0x7a18`): `+0x04` card id, `+0x08` position, `+0x14` Euler rotation, `+0x20` scale, `+0x2c` SE flag, `+0x30` texture value, `+0x34..` 6 x 4 x 2 shards with start position, velocity and spin, `+0x21f4` group offset, `+0x2200` velocity, `+0x220c` gravity (0, -0.5, 0), flash fan `+0x2218`, 16 dust sprites `+0x22a8..`.
- Shared card quad `0x098e7624`: 62 x 88 units, UV +-0.4921875 (texture offset 0.5).
Texture value use: texture scale = value / 64 + 1 (a per-zone inset of the card art; meaning of the value not confirmed).

#### Name mismatches

- `field_3d_draw_cb_set_card_texture` (formerly `field_3d_node_cb_set_card_texture`; renamed 2026-11-04) (`0x098562b8`) and `field_3d_draw_cb_blink_tint` (`0x09856358`) are draw-state callbacks (texture callback and batch hook), not node callbacks.
- `field_3d_copy_light_record` (formerly `field_3d_copy_scene_header`; renamed 2026-11-04) (`0x0985b9e4`) copies a `0x3c`-byte light record, not a scene header.
- `field_3d_copy_camera_record` (formerly `field_3d_copy_matrix_triple`; renamed 2026-11-04) (`0x0985de6c`) copies a `0xc0`-byte camera record (three vectors + direction + two matrices).
- `field_3d_draw_scaled_model_10003` draws the pile model with an animation frame equal to the card count; "scaled" is right but the name hides the pile meaning.
- `field_3d_cutin_set_lp_roll_range` (formerly `field_3d_cutin_set_value_range`; renamed 2026-11-04) stores the LP roll from/to values.
- `field_3d_set_duel_scene` (`0x0985b0ec`, 8 bytes) decompiles as the body of `field_3d_backdrop_set_scene`; skipped.

#### Open questions (batch 1 (BOOT.BIN model pipeline, cut-in core, duel board, card effect tasks))
- `field_3d_set_duel_scene` (`0x0985b0ec`): 8 bytes; probably a jump into `field_3d_backdrop_set_scene` or a shared tail (disassembly needed).
- `field_3d_call_draw_card_quad` (`0x09864ff4`) and `field_3d_start_material_send_fx` (`0x09862c44`): argument shuffling hidden by the decompiler.
- Meaning of the value from `ui_get_zone_card_scale` used as texture scale `value / 64 + 1` in card effects.
- EDRAM ramp textures: confirm the cel-shading hypothesis in PPSSPP (which models set hook byte `+0x08` bit 0, and how the ramp is sampled through map mode 2).
- `field_3d_board_resync_piles` leaves objects that no engine entry claims on a stack-local list (they are not returned to the free pool): leak or impossible case?
- `field_3d_cutin_collect_deck_card_ids`: the sign handling of the deck-size limit (cards 0x1a7f, 0x1c31, extra deck 0x1ab1) looks odd in the decompilation; check in the disassembly.
- Member `texture/10500.txt` used as a GIM for generic avatars: format (nested EHP or list) not checked.
- Bit 15 of the location code as battle position: confirm against `duel_core_view_get_slot_position` values.
- `field_3d_draw_billboard_at`: how the computed billboard matrix reaches the GUM stack (VFPU registers).

### Findings from batch 2 (effect tasks, backdrop extras and change-over, cut-in effect channels)

#### Duel draw-task effects (rel_duel_draw): common shape

All card/duel effects in this batch are draw tasks of the task manager at 0x098e7684 (254 entries of 0x1c bytes).
`ui_duel_create_draw_task(callback, done_cb, done_arg, data_size)` allocates a zeroed data block; the two
middle arguments are the completion callback and its argument (confirmed by the backdrop transition creator,
which forwards `done_cb`/`arg`, and by `field_3d_on_summon_fx_show_card_popup`, which is passed as such a callback).

- Creator: `int create_xxx_task(<params>, done_cb, done_arg)`: returns the handle (index in bits 24-31) or -1, fills
  the data block.
- Callback: `int update_xxx(int phase, void *data)`: `phase == 1` on the first call (task state 1 "start"), used to
  build static vertex arrays inside the data block. Returns 2 to keep running, 4 when finished (task state 4 "free").
- Timers advance by `ui_duel_get_anim_frame_step()` (integer frames per game frame, table 0x098cff74 indexed by the
  duel animation-speed setting) or, for model-driven tasks (coin, dice, deck shuffle), by the float
  `ui_duel_get_anim_speed_value()` (table 0x098cff64). Effects therefore run faster at higher speed settings by
  skipping frames, not by shortening their tables.
- Sounds: `audio_play_se_once_at_frame(se, timer, frame, &flags, bit)` plays once per flag bit.
- Drawing: almost always display list 5 (3D effects in the duel camera) or 7 (screen-space overlay with its own
  fx camera); list 3 for a full-screen darkening behind the Destiny Board letters.
- Vertex arrays are built in the data block in GE format: vtype 0x183 (float UV + float XYZ, 5 words/vertex),
  0x19f (float UV + 32-bit colour + float XYZ, 6 words/vertex); 0x983 / 0x99f are the same layouts drawn through an
  8-bit index list (byte pairs built in the data block to walk a grid as strips). GE primitives used: 4 triangle
  strip, 5 triangle fan, 6 sprites.
  Grids that are rewritten every frame are double-buffered by frame parity (two copies in the data block) because
  the GE reads the list asynchronously.
- Alpha is passed as the top byte of the ambient colour (`alpha << 24 | 0xffffff`).
- fx textures are bound by index with `field_3d_dl_bind_fx_texture(list, n)` (texture-name table 0x098cfe8c):
  used indices in this batch: 3 (glow fan), 5 (small sparkle), 10, 12 (Tribute), 0xd (particle sprite atlas),
  0xe (Synchro burst), 0x12 (ground glow), 0x1e (duel_ouija.gim letters), 0x23 (Synchro level ring),
  0x24 (Synchro light beam).

#### Per-effect parameters (for the port)

| Effect | Data size | Duration | Sounds | Notes |
| --- | --- | --- | --- | --- |
| Tribute (`0x09867a20`) | 0x17c4 | 32 frames | 0x7a3c at 0 | card quad fades out; 128 particle ring; 17-segment double ring strip |
| Fusion/Synchro material (`0x098683c0`) | 0x7050 | 32 frames | 0x7a38, 0x7a3c at 0 | card face on a 17x25 grid twisted into a swirl (inner vertices faster); 32 particles pulled in from radius 130 |
| Card travel (`0x09869654`) | 0x490 | 24 frames | none | glow head on a lerp(from, to, ease_sine) path lifted by sin(pi t/24)*150; 8-entry trail |
| Card pop-up (`0x09869e54`) | 0x6c | open 16 frames, close 8 after close flag | none | own fx camera on list 7 at the screen point; flips in about X |
| Coin toss (`0x098723a4`) | 0x100 | 120 time units + fades | 0x7a39 at 38 | up to 3 coins, model ids from 0x098cfb20, result applied by node hook after time 54; model frame clamped at 88 |
| Dice (`0x0987298c`) | 0x6c | model animation per die | 0x7a3f/40/41/42/37 at 19/28/36/45/80 | model 0x1001e (kind 1) or 0x1001f; die face set by node hook after time 25 |
| Deck shuffle (`0x09872e14`) | 0x90 | lift 8, animation, lower 8 | four random of five at 0/10/20/31 | model 0x10020; deck height scale = count/40 |
| Fusion Summon (`0x09873274`) | 0xb5ec + 4n | 5 phases, table 0x098cfb60 | 0x7a38 at 0 | off-screen 512x512 render (VRAM 0x174000) mapped onto a 33x33 polar vortex grid |
| Synchro Summon (`0x09874924`) | 0x186bc + 4n | 9 phases, table 0x098cfb90 | 0x7a45/0x7a38/0x7a27 at 40/50/80 | level rings (card_db_get_level of the first material word, max 8), light beam, 512-particle burst |
| Destiny Board letters (`0x09875d74`) | 0x219c | 120 frames (180 with all five letters) | none | letters at x = 314 + (k-2)*45, y about 157 - 40 |
| Card fx (`0x09876c28`) | 0x4944 | kind 0x14 open-ended, else 100 frames | (see below) | used by the Final Countdown win |

The Fusion and Synchro tasks share a technique worth reproducing on 3DS: each frame they draw the card sprites into
an off-screen 512x512 RGBA8888 colour buffer at VRAM offset 0x174000 (`system_ge_set_render_targets(list, 0x174000,
-1, 512, 512, 3)`, stencil cleared), switch back to the back buffer and use that buffer as a texture on a 33x33
polar grid whose texture coordinates are the screen projections of the grid vertices (so with no distortion the grid
reproduces the image exactly); the vortex is then just a per-ring angular offset of the vertex positions.

#### Model node hooks

`field_3d_update_model(model, params)` takes a parameter record `{float step, hook, value, 0}`; the hook is called
per node as `hook(model?, float *matrix, params)` and the coin/dice tasks use `params+8` (value) to post-multiply a
rotation that shows the required face (coin: value 1 = rotate by the constant at 0x098c4f38 about Y; die: values
2-6 select fixed X/Y/Z rotations, 1 = identity). The first hook argument is not used by either hook (unknown).

#### Final Countdown presentation (card fx task, `0x09876c28` / `0x09876ca8`)

The "card fx" task is the Final Countdown turn counter: 20 glowing points on a circle of radius 150 (tilted about X)
drawn with an own fx camera on list 7. `kind` 1..19 lights `kind` points (the newest after frame 39, duration 100
frames); kind 0x14 (20) lights one point every 16 frames, requests backdrop 0x169c (5788, the Final Countdown field)
at frame 360 through `field_3d_backdrop_request`, and at frame 510 enlarges the sparks and runs a 30-frame white flash;
`field_3d_is_card_fx_task_finished` reports completion when the end counter (+0x4940) passes 29. This is the
"effect animation that requests id 5788 once its time passes 360" mentioned in field_3d.md (call site 0x09876e08).
The backdrop change-over for 0x169c is the plain 60-frame fade to/from black on list 2
(`field_3d_update_final_countdown_transition`); every other field uses the swirl transition below.

#### Backdrop change-over (swirl), `0x0987a604`

16 frames. Each frame the finished screen is block-copied into VRAM 0x174000 (480x272 out of the front/back buffer,
`field_3d_dl_copy_framebuffer_to_texture`) and redrawn through a 31x21 grid of 2D vertices (s16 UV/XYZ, vtype
0x800902, through-mode) over a black sprite on list 3. Each vertex rotates about the screen centre by
`rate * 24` (leaving) or towards 0 (entering), `rate = c1 + c2 * (76096 - min(r^2, 76096)) / 76096`, where
76096 = 240^2 + 136^2, so the centre swirls most; the grid is also scaled. Alpha: entering fades in over frames 0-8,
leaving fades out over frames 8-16. Sound 0x7a3a at frame 0 unless `ui_test_set_draw_flags(8, -1)` is set.
Answers part of the open question "the change-over task 0x0987a604 (duration, fade or wipe)": a 16-frame swirl plus
fade (high for the structure; c1, c2, the zoom constants 0x098c5050/0x098c5054 and the target angle 0x098c504c are
float constants not read here).

#### Field-spell backdrop extras (card-specific, `field_3d_backdrop_start_extra`)

All eight creators have the shape `int start_xxx_extra(int slot?, done_cb, done_arg)` (first argument stored at
data +0, never read by the update callbacks seen here; presumably the backdrop slot, low-medium). Their callbacks
never return 4: they run until `field_3d_backdrop_stop_extra` stops them. All use the duel camera
(`field_3d_push_backdrop_camera_matrices`: projection from `field_3d_get_duel_projection`, view from
`field_3d_get_duel_view_matrix`) and draw into display list 2 (Venom Swamp: list 1), with a private LCG
(`field_3d_backdrop_extra_rand_int/unit`, constants 0x41c64e6d / 0x3039, state address not resolved).

| Card | Data | What it draws | Textures |
| --- | --- | --- | --- |
| 0x1323 | 0x2b4 | one floating sprite at a time anchored at node 4 of the backdrop model (life 30-45 frames, bobbing) | fx 0x1f (backdrop archive) |
| 0x1345 | 0x24ac | 420-frame loop; during frames 308-318 and 346-356 ripples, splash columns and droplet bursts at two fixed points | fx 0xc, 9, 0x20 (backdrop) |
| 0x1346 | 0x1680 | two 64-spark sets (life 64), a scrolling two-pass band (fx 9 then additive fx 0xc), embers every 4 frames | fx 5, 9, 0xc, 0x19 (backdrop) |
| 0x1349 | 0x4a28 | lightning bolts every 5-34 frames (10 % wide bolts at the origin), 32-frame life, ground ripples every 3 frames | fx 0x1b (backdrop), 3 |
| 0x169f | 0xbf8 | a 600-frame ribbon re-started every 620-639 frames, plus flames every 3 frames | fx 0x1d (backdrop), 3 |
| 0x1a67 | 0x74c | rising motes, 32 records of two, life 32, colour 0xff1830ff | fx 5 |
| 0x1aa7 | 0x169c | dust puffs every 4 frames (128 records, life 512), position 0x098d0000 | fx 5 |
| 0x1bfc | 0x484 | bubbles in three rectangles every 30-59 frames, 8-frame sprite animation | fx 0x22 (backdrop) |

Extractor-relevant: `field_3d_dl_bind_fx_texture` looks the name up in the 36-entry table 0x098cfe8c and takes the
member from the backdrop archive `duel/bg/fmagic<card>.ehp` for indices 0x19 (0x1346), 0x1b (0x1349), 0x1d (0x169f),
0x1f (0x1323), 0x20 (0x1345) and 0x22 (0x1bfc); index 0 from the icon archive; every other index (including 0x1a,
0x1c, 0x1e = duel_ouija, 0x21) from duel archive 0x80001. Correction to field_3d.md ("0x19-0x22 are the per-card
field textures"): only those six indices are; the others in that range come from the duel archive (high, from the
code). There is no null check when the backdrop archive is not loaded yet.

#### Cut-in effect channels

A cut-in slot (400 bytes, 0x098d4d60) has three effect channels, each pointing at a 0x18-byte fx slot from the pool
at 0x098e937c (4 slots; part of the 0x124-byte block 0x098e9370 cleared by `field_3d_clear_cutin_fx_slots`):

| Channel | Start | Stop | "phase" setter |
| --- | --- | --- | --- |
| +0xb8 main | `field_3d_start_cutin_fx` (switch on animation id → creator family) | `field_3d_stop_cutin_fx` | `field_3d_set_cutin_fx_frame_advanced` |
| +0xbc extra | `field_3d_start_cutin_extra_fx` (per character: 0x2b, 2, 9, 0xc, 0x29, 0x25) | `field_3d_stop_cutin_extra_fx` | `field_3d_set_cutin_extra_fx_frame_advanced` |
| +0xc0 aux | `field_3d_start_cutin_aux_fx` (always `ui_start_anim_cue_task`) | `field_3d_stop_cutin_aux_fx` (also stops all SE) | `field_3d_set_cutin_aux_fx_frame_advanced` |

fx slot layout: +0x00 task handle (-1 = free), +0x04 "advanced" flag written every tick by the phase setters
(the fifth argument, t0, of the frame hook = cut-in +0x174, set when the integer animation frame advanced), +0x08
character, +0x0c variant, +0x10 animation id, +0x14 cut-in pointer. The fx tasks step their timers only when +4 is 1,
so they stay locked to the cut-in animation rather than to wall time (medium: the t0 mapping comes from the documented
call `field_3d_cutin_call_frame_hook(cutin, +0x50, trunc(+0x54*fps), frame, +0x174)`).

Words of the block 0x098e9370 used as creator arguments: +0 (0x098e9370) for anim3e_54, +4 (0x098e9374, set by
`field_3d_set_cutin_fx_word_04`) for anim107_114, +8 (0x098e9378, `field_3d_set_cutin_fx_word_08`) gates animd5_e6.

Speed lines: `field_3d_start_cutin_fx` ends with `ui_fade_speed_lines(0x60)` (0 for character 0x25's 0x1da-0x21e
group) when an effect started, else `ui_fade_speed_lines(0xff)`, with exceptions listed in its row.

The anim18_31 and anim55_71 effects are hand trails: positions of attach point 0x2a (and scene node 0x17) are kept as
a history of up to 32 points, smoothed with `system_spline_build`/`system_spline_eval` (8 samples per segment) and
extruded into 3- or 5-sided ribbons; their distortion halos sample the captured screen (VRAM 0x174000).

#### Render-state helpers (rel_duel_draw)

- Display lists (system_ge_select_layer indices): 1 and 2 backdrop/extras, 3 full-screen underlays, 5 duel 3D
  (viewport centre 0x84a/0x7fc, size 0x3c0 x 0x220), 7 overlay (centre 0x800/0x800, 480x272), 8 cut-in effects.
  `field_3d_reset_fx_display_lists` resets 1, 2, 3, 5, 7, 8 each frame (from `ui_duel_run_draw_tasks`).
- Off-screen buffers in VRAM: 0x174000 (512x512 RGBA8888, effects and screen captures) and 0x160000 (128x256
  RGBA8888, card face rendered by `field_3d_dl_bind_card_face_texture` mode 0). The two display buffers are at EDRAM
  +0 and +0x88000 (512x272x4) and swap by frame-counter parity.
- `field_3d_setup_fx_camera` viewport centre = (cx + 0x710, cy + 0x778); the effects pass (0x13a, 0x84), i.e. the
  screen centre (0x84a, 0x7fc). The default fx lens: near 100, far 10000.
- Billboards: `field_3d_make_rotation_only_matrix` = transpose of the view matrix with translation removed, from the
  current view (`field_3d_get_view_rotation_matrix`), the cut-in camera (`..._main_camera_...`) or the duel camera
  (`..._backdrop_view_...`).
- Matrix save/restore around the cut-in layer: `field_3d_save_matrix_state` keeps the four GU matrices at
  0x098e9260/0x098e92a0/0x098e92e0/0x098e9320 and the perspective at 0x098e9360..0x098e936c;
  `field_3d_set_fx_perspective`/`field_3d_restore_fx_perspective` use a second copy at 0x098e924c..0x098e9258.

#### Random generators

Three copies of the same LCG (x = x * 0x41c64e6d + 0x3039, value = (x & 0x7fffffff) >> 16, unit = value / 32767):
`field_3d_fx_rand_*` (duel effects), `field_3d_backdrop_extra_rand_*`, `field_3d_cutin_fx_rand_*`, plus
`system_effect_rand_*` in the card tasks. The decompiler shows their state address as `*(0 * 0xc)`, so whether they
share one state word is unknown (read from the disassembly).

#### Name mismatches

- `field_3d_mul_matrix3_by_rot_x` (formerly `field_3d_mul_matrix3_by_axis_rotation`; renamed 2026-11-04) always rotates about X (same as `field_3d_mul_matrix4_by_rot_x`, 3x3).
- `field_3d_set_cutin_fx_frame_advanced` / `_extra_fx_frame_advanced` / `_aux_fx_frame_advanced` (formerly `field_3d_set_cutin_fx_phase` / `_extra_fx_phase` / `_aux_fx_phase`; renamed 2026-11-04) store the per-tick "frame advanced" flag,
  not a phase number (medium).
- `field_3d_push_saved_matrices` only pushes and marks the current matrices dirty; no load of the matrices kept by
  `field_3d_save_matrix_state` is visible (medium; a VFPU load could be hidden).
- `field_3d_is_card_popup_shown` returns true once the pop-up has finished opening (or no longer exists).
- `field_3d_card_fx` family (create/update/is_finished) is specific to the Final Countdown counter in practice
  (only caller `ui_start_final_countdown_win_fx`); a name such as `field_3d_*_final_countdown_fx` would be clearer.

#### Open questions (batch 2 (effect tasks, backdrop extras and change-over, cut-in effect channels))
- The float constants that define several effects were not read (0x098c4ee4-0x098c5064, 0x098c5e48-0x098c5e64,
  0x098cfb20 coin model ids, 0x098cfb30/40 deck positions, 0x098cff50 shuffle sounds, the timing tables 0x098cfb60
  and 0x098cfb90): dump them from BOOT data to get exact sizes/angles/durations for the port.
- Hidden float arguments: the lerp factor in `field_3d_update_deck_shuffle`, the bolt offset in the Mystic Plasma
  extra, the drift vector in the Jurassic extra, the bubble position in the Venom Swamp extra, the texture
  offset/scale passes in the Pandemonium and Mystic Plasma extras, and the rise-speed input in the Mausoleum extra.
- `field_3d_create_material_fx_task_with_card` (0x09868478): which register carries the zone-scale word it stores at
  +0x30 (skipped).
- The first argument of the backdrop-extra creators (stored at +0, unused by the updates).
- GE state indices used with `system_ge_enable/disable` (0..0x15) are the game's wrapper numbering; map them to GE
  commands (state 7 is enabled by the Chorus and Venom Swamp extras, presumably fog; state 9 texturing, 1 depth test,
  4 blending, 3 stencil) from the wrapper in BOOT.BIN.
- What `ui_test_set_draw_flags(8, -1)` tests before the change-over sound.
- Whether the three LCG copies share a state word.

### Findings from batch 3 (cut-in effect animations, archive loading, rel_field rendering)

Scope of this pack set: the end of `rel_duel_draw` (cut-in effect tasks `0x09884584`-`0x09895e08`, the cut-in
aux/extra channels, backdrop and cut-in archive loading, view-matrix store, per-character cut-in callback
blocks) and `rel_field`'s field render state, stencil shadows and map stencil passes. 129 functions read,
7 skipped (hidden register arguments or a broken body).

#### Cut-in effect slots and task protocol

- Effect slots: 4 x `0x18` bytes at `0x098e937c` (allocated by `field_3d_alloc_cutin_fx_slot`, free when
  `+0` is -1): `+0` task handle, `+4` run flag, `+8` character, `+0xc` variant, `+0x10` animation id,
  `+0x14` cut-in (400-byte slot of `0x098d4d60`). Every effect task keeps a pointer to its slot in its data
  (offset varies: `+0x10`, `+0x14`, `+0x18`, `+0x1c`, `+0x20`, `+8`).
- Creation: `ui_duel_create_draw_task(update, a, b, size)`; `field_3d_start_cutin_fx` passes `a = b = 0`.
  Data sizes range from `0x24` (sound-only) to `0x21a24` bytes (`anim3e_54_v1`, double-buffered tunnel).
- Update callback `int update(int state, int *task)`: `state == 1` on the first call (meshes, index strips and
  random tables are built then); returns **2** to keep running and **4** when finished (task-manager states
  of `0x098e7684`: 2 run, 4 free). The aux/cue callbacks (`field_3d_draw_cutin_aux_fx`,
  `field_3d_update_cutin_attach_flash`) take a third argument (the fx slot) and always return 2.
- Common timing record at the start of the task data: `+0` wait counter, `+4` start frame, `+8` elapsed,
  `+0xc` length, filled by a per-family `field_3d_get_cutin_fx_timing_*` function. The effect appears when
  wait counter == start frame; afterwards elapsed counts up to the length. **Both counters advance only while
  the slot's run flag (`+4`) is 1**, so a paused cut-in pauses its effects (high). Typical fades:
  `ui_duel_ease_sine(elapsed, 8)` in, `1 - progress(elapsed - (length - 8), 8)` out (16 frames in some).
- Families (animation id -> creator; timing in the rows): `0x18-0x31` (anim18_31, earlier pack),
  `0x24-0x26/0x6a/0xce/0xcf/0xee/0xef` anim24_ef, `0x32-0x3a/0x44-0x47/0x84` anim32_47,
  `0x3e-0x54/0x82-0x85` anim3e_54 in 9 variants chosen by the word `0x098e9370`, `0x81-0x97` anim81_8f,
  `0x72-0x80/0x8e/0x8f/0xa3-0xb5` anima3_b5, `0xb1-0xb9` animb1 (only for the (character, variant) pairs of
  `field_3d_cutin_has_fx_animb1`: 5/0, 0x14/2, 0x12, 0x19, 0x21), `0xba-0xc3/0x104-0x114` anim107_114 (mode
  from `0x098e9374`, card id from cut-in `+0x160`), `0xd5-0xe6` animd5_e6 (only when `0x098e9378 == 1`),
  `0xe7` anime7 (card burst, list at `0x098e93f0`/`0x098e93f4`, max 40), `0x1da-0x21e` anim1e3_21e (duel-disk
  flash, sets the disc flag), `0x199-0x2b3` sound-only task (clears the disc flag).
- Sound effects used: `0x7a28` (anim32_47, anim3e_54 variants), `0x7a1b` (anim81_8f, anima3_b5, animb1_v1 for
  character 0x29/1), `0x7a27` (animb1), `0x7a1c` (anim107_114), `0x7a29` (animd5_e6, started and stopped),
  `0x7a2a/0x7a2b/0x7a2c/0x7a2d` (disk flash / sound-only), `0x7a3d` (card burst), `0x7a45` (extra B),
  `0x7a19` (attach flash), `0x7a17` (aux layer fade).
- The "disc flag" (cut-in `+0x168`): set to 1 by `field_3d_update_cutin_fx_anim1e3_21e` at its start frame,
  cleared by `field_3d_update_cutin_sound_fx` and by `field_3d_start_cutin_fx` before creating anim1e3_21e;
  `field_3d_draw_cutin_aux_fx` turns its pulsing two-fan glow at attach point 0x2b on/off from it. That this is
  the duel-disk light is a hypothesis (medium).

#### Effect rendering recipes (for the port)

- All effect geometry goes to GE layer 8 (`system_ge_select_layer(8)`), textures from the fx texture table
  (`field_3d_dl_bind_fx_texture(list, i)`, names at `0x098cfe8c`); indices seen here: 3 (soft flash), 5
  (debris), 9, 0xc (tunnel/streak textures), 0xd, 0xe (sparks), 0xf, 0x10, 0x14, 0x15 (beam), 0x17, 0xb.
- Recurrent meshes built at `state == 1`: a "tunnel" of 49 rings x 33 vertices (radius 220, z 0 to -6000,
  origin (0, 120, 160), 6-word vertices u, v, colour, x, y, z, vertex type `0x119f`, 16-bit index strips of
  0x42 indices per ring pair) with a scrolling texture offset; a 33 x 33 screen disc (radius 800); 4 x 2
  atlas-cell quads (u step 0.25, v step 0.5); ribbons of 7-9 vertex pairs.
- Particles live in fixed rings of records (8, 12, 16, 24 or 32), one record filled per frame, each with a
  frame counter and a live bit (bit 0 of word 1); a record dies after its ease length (8-32 frames).
- Random numbers come from the local LCG copies `field_3d_cutin_fx_rand_int` / `_rand_unit`, so the effects are
  not reproducible frame-for-frame unless the seed is matched.
- Stencil masking for anim3e_54 (`field_3d_begin_cutin_fx_stencil_mask`, skipped for id 0x3f): a full-screen
  sprite writes stencil 0xff where it passes depth function 2 against the current depth buffer, then effects
  draw with stencil EQUAL 0xff. Interpretation (effects only where the character is not, medium).
- Frame-buffer effects: radial blur (anim81_8f: 16 scaled redraws of a projected fan sampling the copied frame
  buffer), heat haze (anim3e_54 v4/v5: 9 x 9 or 16 x 16 through-mode grids with +/-2 pixel jitter,
  double-buffered by frame parity), zoom blur through the off-screen target `0x174000` (512 x 512, format 3)
  in anim24_ef for id 0x6a, glow tiles (anim3e_54 v0: 8 x 9 tiles of 64 x 32).
- Screen projection used by several effects: `x_screen = x/w * 240 + 2048 - 0x710`,
  `y_screen = -y/w * 136 + 2048 - 0x778` (GE offset 0x710/0x778, viewport centre 0x800).
- `field_3d_dl_disable_depth_test` ignores its second argument (callers pass the animation id).
- GE enable/disable state numbers match the GU enums: 1 depth test, 2 scissor, 3 stencil, 4 blend, 5 cull,
  7 fog, 8 clip planes, 9 texture, 10 lighting, 11-14 lights 0-3.

#### Extra and aux channels

- Extra channel (cut-in `+0xbc`, `field_3d_start_cutin_extra_fx`): A = bone glow on the main-scene duellist
  model (node lists `0x098d00f0`, `0x098d0120`, `0x098d0130`, `0x098d0138`, `0x098d0148`; characters 2/2, 0x2b,
  0xc, 0x29 and others; length -1 = until stopped), B = two glints transformed by main-scene nodes (nodes at
  `0x098d015c`; characters 9 and 2/0), C = 60-frame screen flash plus two node glows (nodes at `0x098d0154`).
  The per-character cut-in blocks start it in their motion-start callback, stop it in motion-end and set its
  phase (`+0xbc` slot word +4) in the frame hook.
- Aux channel (`+0xc0`): `ui_tick_anim_cue_task` calls `field_3d_draw_cutin_aux_fx` and
  `field_3d_update_cutin_attach_flash` with the slot. `field_3d_cutin_aux_fx_layer_hook` is a model draw hook
  that fades in model layer 0xb (lighting on, lights 0-3 off, ambient alpha ramp) with timing from
  `field_3d_cutin_aux_fx_set_fade_timing` (globals `0x098e93dc`-`0x098e93ec`).

#### Cut-in archive loading (extractor-relevant)

- Loading slots: count `0x09bdcf50`, 0x2c-byte slots at `0x09bdcf54`: `+0` character, `+4` variant, `+8`
  cut-in archive buffer, `+0xc` base archive buffer, `+0x10` cut-in loading, `+0x14` base loading, `+0x18`
  cut-in loaded, `+0x1c` base loaded, `+0x20` face/voice pending, `+0x24` face loading, `+0x28` voice loading.
  One heap block (`0x09bdd004`, 0x483000 bytes or 0x2ff000 in setup mode 2) holds all buffers.
- Buffer sizes = maximum file sizes: base (portrait) archive 0x4800 bytes (0x20c00 for generic characters),
  cut-in archive 0x17b000 bytes, backdrop archive 0x80000 bytes (`duel/bg/fmagic%04d.ehp`, fallback
  `fmagic0000`). All cut-in files load from root 4, backdrops from root 3.
- Base archive path = prefix `0x098d1e38` + `world_get_character_mini_bup_name` + suffix `0x098d1d4c`.
  Cut-in archive name = `world_get_character_cutin_name(character, variant)` with fallbacks (variant 0, then
  character 2/0) and two hard-coded names (character 0x29 variant 0, character 0x27).
- Generic characters' cut-in archives contain two **placeholder members** that are overwritten at run time
  (Ghidra labels `s_texture__10500_txt` and `s_voice__10000_txt`): a face texture of up to 0x10500 bytes loaded
  from `cutin/da_faces/` + a body folder (`DA_girl`, `DA_boy_B`, `DA_boy_Y`, `DA_boy_R` by byte 1 of
  `world_get_character_model_ids`) + a number from byte 2, and a voice archive of up to 0x10000 bytes (a
  `zakov%02d`-style name with 0x32 + voice set index; a fixed message archive for character 0x29), which is
  then bound as an EHP inside the member. The extractor must treat those members as slots, not content.
  Exact punctuation of the labelled strings must be read from the binary (labels only seen here).
- Characters equal to 1 never get a cut-in archive, and no cut-in archives are loaded during network play.
- Possible overlap: for generic characters the cut-in buffer starts 0x20c00 bytes into the slot but the
  cursor only advances 0x17f800, leaving 0x1c400 bytes shared with the next slot's base buffer (see open
  questions).

#### Duel object models and view matrices

- Duel object table `0x098d0960`: 40 x 0x18 bytes (`+0` id, `+4` archive flag, `+8` TMS name, `+0xc` TMT name
  (bound with `field_3d_set_animation` when its magic is 'TGMT', else passed to
  `field_3d_create_model_instance` as its second argument), `+0x10` TMA name, `+0x14` cached instance).
- Saved view matrices: 3 x 0x40 at `0x098e99e0` (board, backdrop, cut-in cameras via
  `field_3d_store_view_matrix(index)`).
- Cut-in camera (`field_3d_apply_cutin_camera`) matches the existing doc row; the aspect 1.7647 is at
  `0x098c5f90` and the focal constant at `0x098c5f94`.

#### rel_field: field render state and stencil passes

- The free-roam field uses an **orthographic** projection (`ortho(-240, 240, -136, 136, -10000, 10000)`
  times the scale vector `0x090fcb80`), depth function GEQUAL with depth range 0xffff..0 (reversed), fog
  50..100 colour 0x404040 (state set but fog disabled), culling on (high).
- Camera: target = player position, eye = target + offset `0x090f3e30`, up `0x090fcb90`, plus a shake vector
  `0x09106730` while `0x09106710` is set; the eye is copied to `0x09106740`.
- Stencil shadows (characters/objects): `field_3d_set_shadow_basis(light_dir)` builds a matrix at
  `0x09105ac0`; `field_3d_begin_shadow_stencil` clears stencil and masks colour/depth writes;
  `field_3d_draw_shadow_volume(radius, list, pos)` draws a fixed volume mesh (strip of 0x30 vertices at
  `0x090fc200` + 0x48 triangle vertices at `0x090fc5c0`, vertex type 0x143) twice, INCR with front face 1 and
  DECR with front face 0 (z-pass); `field_3d_resolve_shadow_stencil` fills stencil > 0 with 0x80000000.
- Map stencil volumes: same scheme with the mesh at `0x090fd1d0`/`0x090fd248` (vertex type 0xa1), special
  scales for map 3 and for maps 0xd-0x14/0x26 at one grid position; closed by a pulsing tint
  (`field_3d_draw_stencil_pulse_overlay`: colour 0x8080ff, alpha 32..64 with a 40-frame period).
- `field_3d_map_stencil_draw_callback` makes a map material write stencil 1 (colour/depth writes masked,
  phase 0) and restores writes in phase 1; its phase arrives in t0 (fifth argument).

#### Name mismatches

- `field_3d_lookup_attach_offsets_a`..`_e`, `field_3d_search_attach_offsets_*` and `field_3d_sort_attach_offsets_*` (formerly `field_3d_lookup_pose_table_*`, `field_3d_search_pose_table_*`, `field_3d_sort_pose_table_*`; renamed 2026-11-04): these are attach-offset lookups (same
  0x20-byte entries and comparator `0x098a0d04` as `field_3d_cutin_*_lookup_attach_offset`), not pose tables.
- `field_3d_draw_cutin_aux_fx` both updates and draws (state from the disc flag); fine as is.
- `field_3d_map_material_dd_callback`: "dd" is unexplained; it toggles one GE state for materials whose name
  contains one of four substrings.
- `field_3d_search_attach_offsets_*` return the bsearch result although Ghidra types them void.

#### Open questions (batch 3 (cut-in effect animations, archive loading, rel_field rendering))
- `field_3d_map_material_dd_callback`: which GE state is toggled (argument hidden) and what the four name
  substrings at `0x090fd16c`-`0x090fd184` are.
- `field_3d_set_map_variant_group_mask` (`rel_field:0x090da484`): body lost in the decompilation; read the
  disassembly.
- `field_3d_lookup_attach_offsets_a` (17 tables, `0x098d3e50`-`0x098d48b0`): which table is searched (hidden).
- Cut-in loading block: is the 0x1c400-byte overlap for generic characters real (buffer 0x20c00 + 0x17b000 >
  stride 0x17f800), or are generic cut-in archives always smaller than 0x15ec00 bytes? Check file sizes.
- Backdrop archive slot `+0x10`: never set in the code read here, so the release-pending path may be dead.
- `field_3d_get_cutin_sound_fx_timing`: ids 0x1bf, 0x24c, 0x294 set a start frame that is then overwritten
  (start = previous sound frame + 8); a bug in the original (medium) — confirm in PPSSPP.
- The off-screen render target `0x174000` used by anim24_ef (id 0x6a): what is read back from it.
- Confirm in PPSSPP that anim3e_54's stencil mask keeps the effects behind the character.

## Round 6 additions (2026-11-04)

- The cut-in code of `rel_duel_draw` has a complete copy in `rel_cutin_viewer` (`modules/rel_cutin_viewer.md`); there the per-character set-up routines are listed explicitly by `field_3d_cutin_get_chara_setup`, which confirms the character of every descriptor family.
- Descriptor slot `+0x30`, missing from the slot table above, is a voice-motion picker callback (shared family and two character-2 pickers with one-entry tables at `0x098d4b30` / `0x098d4be0`); see `ui.md`, "Round 6", for the full list of set-up routines, map-node callbacks and resolve-motion overrides created in this round.
- The 44 per-character set-up routines of `rel_duel_draw` (`0x09842f74`-`0x0984cb30` and five near `0x098b5ff0`-`0x098b95e8`) were code outside any function until round 6; they are now functions named `field_3d_cutin_<family>_setup_desc` with `_map_node` / `_resolve_motion` callbacks.

## Open questions

- Answered 2026-10-31 (static, high): `field_3d_update_model` advances 1.0 frame per game frame for backdrops and cut-ins, at a game rate capped at 29.97 per second ("Frame timing and playback rate"); the backdrop loops (flags 2), the cut-in plays once (flags 0). Still to confirm in PPSSPP (F10): the effective rate during a duel, which may drop under load.
- Answered 2026-10-31: the loader of `duel/bg/fmagic<id>.ehp` and the caller of `field_3d_apply_scene_etc` ("Field-spell backdrop manager").
- Which ids engine command `0x13` carries (the sender of draw command 7 is now known, "Field-spell backdrop manager"): field spell resolved, field spell leaves the field (presumably 0, low); trace the `0x13` pushes in `rel_duel_eng` or break on `0x09899cdc` in PPSSPP.
- ~~The change-over task `0x0987a604`~~: answered 2026-11-04 (batch 2 findings): 16 frames, a screen capture redrawn through a 31 × 21 swirl grid while fading to or from black; backdrop `0x169c` uses a plain 60-frame fade. The eight card-specific extras are described per card in the same findings (static read; not every float constant is read).
- ~~Texture-mapping callbacks `0x0882ef50` / `0x0882f050`~~: answered 2026-11-04 (batch 1 findings, "Texture-map callbacks and the EDRAM ramp"): type 1 is camera-driven environment mapping with lights 2/3, type 2 light-0-driven mapping, optionally against a 64 × 32 EDRAM ramp (cel-shading hypothesis, medium).
- ~~How the group mask `inst+0x64` reaches the draw hook~~: answered 2026-11-04: it is word 4 of the instance draw state `inst+0x54` passed to `field_3d_draw_pass`, and it is a hide mask.
- The unread `-etc` tracks (84-track 13–19, 42-track 4–9). (The purpose of `.vtmt` is settled: lip-sync animation, `docs/formats/vtmt.md`.)
- Role of `.tmf` (with `.ehf`, covered separately).
- The remaining open fields listed in `docs/formats/tgm.md`.
- The open questions of the 2026-11-04 batches (above, per batch): the state word of the cut-in effect random generators, float constants of the effect recipes, the possible `0x1c400`-byte slot overlap of generic characters' cut-in archives, and the latent `field_3d_pose_nodes_blend` track-index issue.
