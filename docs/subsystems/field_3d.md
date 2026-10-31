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

Runtime model instance (`tgm_model_instance` in `re/formats.csv`, partial, named): `+0x00` TGMS, `+0x0C` node
world matrices (64 bytes per bone), `+0x10` skin matrices, `+0x14` TGMT, `+0x18` previous TGMT (cross-fade),
`+0x20` frame (f32), `+0x28` previous frame, `+0x2C` animated material copies (0xA4 per TGMA entry), `+0x30`
animated texture copies (0x28 each), `+0x34` TGMA, `+0x38` TGMA frame, `+0x3C` flags (bit 0 cross-fade, bit 1
loop), `+0x54` draw state, `+0x64` visibility group mask.

## Model formats

Documented in `docs/formats/tgm.md` (tool `tools/tgm.py`, which validates all 9,953 TGM members on the disc):

- `TGMS` (`.tms`): mesh. Materials → batches (bone palette of up to 8, GE vertex type) → `sceGuDrawArray` primitives (triangles / triangle strips) over s16-quantised vertices; skeleton with offset matrices.
- `TGMT` (`.tmt`, `.tmt.gz`, `.vtmt.gz`): node animation (three Bézier scalar tracks for translation and for scale, quaternion keys for rotation); `-etc` files add a scene block (camera lens, fog, ambient and four lights, or 32 visibility groups).
- `TGMA` (`.tma`): per material layer UV offset / UV scale / alpha animation, tied to TGMS materials.
- Pointer lists next to them (`<anim>-ptrs.txt`, `all-ptrs.txt`) bundle members (mesh + animations) and index animations by slot.

Posed skinned vertex = Σ weight × node_world × bone_offset_matrix × position (read in `field_3d_update_model`); this places 162 of 196 skinned meshes inside their header bounding box at frame 0, the rest at a later frame.

Export for the port: `tgm.py gltf` (glTF 2.0 + side JSON, `tools/tgm_gltf.py`), described in `tgm.md` "glTF export".

## Open questions

- Call rate of `field_3d_update_model` per user (frames per second of backdrops and cut-ins).
- Texture-mapping callbacks `0x0882ef50` / `0x0882f050` (layer types 1/2).
- How the group mask `inst+0x64` reaches the draw hook (`hook+0x10`); which code sets the loop and cross-fade flags for backdrops and cut-ins.
- The unread `-etc` tracks (84-track 13–19, 42-track 4–9) and the purpose of `.vtmt`.
- Which code loads `duel/bg/fmagic<id>.ehp` and drives `field_3d_apply_scene_etc`.
- Role of `.tmf` (with `.ehf`, covered separately).
- The remaining open fields listed in `docs/formats/tgm.md`.
