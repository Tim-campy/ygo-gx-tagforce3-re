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

Runtime model instance (`tgm_model_instance` in `re/formats.csv`, partial, named): `+0x00` TGMS, `+0x04`
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

- `system_main` (`0x08833734`) loops: `system_scene_run_slice`, `save_tick_frame_counter`,
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
`field_3d_cmd_set_backdrop` (`0x09899cdc`) → `field_3d_backdrop_request(id)`. Which engine event sends
command 7 with which id (activation, destruction of the field spell) is not traced yet.

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

## Open questions

- Answered 2026-10-31 (static, high): `field_3d_update_model` advances 1.0 frame per game frame for backdrops and cut-ins, at a game rate capped at 29.97 per second ("Frame timing and playback rate"); the backdrop loops (flags 2), the cut-in plays once (flags 0). Still to confirm in PPSSPP (F10): the effective rate during a duel, which may drop under load.
- Answered 2026-10-31: the loader of `duel/bg/fmagic<id>.ehp` and the caller of `field_3d_apply_scene_etc` ("Field-spell backdrop manager").
- Which engine event emits draw command 7 and with which id (field spell resolved, field spell leaves the field: presumably 0, low); trace from `rel_duel_eng` or with a PPSSPP breakpoint on `0x09899cdc`.
- What the eight card-specific extras (`field_3d_backdrop_start_extra`) draw, and the change-over task `0x0987a604` (duration, fade or wipe).
- Texture-mapping callbacks `0x0882ef50` / `0x0882f050` (layer types 1/2).
- How the group mask `inst+0x64` reaches the draw hook (`hook+0x10`).
- The unread `-etc` tracks (84-track 13–19, 42-track 4–9) and the purpose of `.vtmt`.
- Role of `.tmf` (with `.ehf`, covered separately).
- The remaining open fields listed in `docs/formats/tgm.md`.
