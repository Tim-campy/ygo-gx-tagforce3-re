# TGM model family: TGMS, TGMT, TGMA

Status: `documented` (structure and, since 2026-10-30, the playback semantics read from the game code), with
the confidence marked per field. Tools: `tools/tgm.py` (`list`, `inspect`, `check`, `obj`, `gltf`) and
`tools/tgm_gltf.py` (the glTF 2.0 exporter); tests `tools/tests/test_tgm.py`, `tools/tests/test_tgm_gltf.py`
(synthetic data only). `.tmf` (the 2D layout partner of `.ehf`) is a different format and is not covered here.

Three member types of EHP archives (`ehp.md`) share the `TGM?` magic and the same building blocks:

| Extension | Magic | Members on the disc | Role (confidence) |
| --- | --- | --- | --- |
| `.tms` | `TGMS` | 585 | Mesh: GE vertex data, materials with render state, textures, skeleton (high). |
| `.tmt` | `TGMT` | 453 plain + 8,701 `.tmt.gz` + 88 `.vtmt.gz` | Node animation: Bézier translation/scale tracks and quaternion keys per node (high, code); `-etc` files: camera, fog, ambient light, lights or visibility groups (high for the roles read in code, see "Scene block"). |
| `.tma` | `TGMA` | 126 | Texture animation: per material layer, UV offset, UV scale and layer alpha (high, code). |

All 9,953 members (counting every copy in every archive, nested archives included) pass every rule
below: `python3 -I tools/tgm.py check <USRDIR>` reports `failing: 0`. Note the 88 `.vtmt.gz`
members in `duel/cutin_*.ehp` (`voice01.vtmt.gz`): they are TGMT too, which accounts for the
difference between 8,789 gzip members (`ehp.md`) and 8,701 `.tmt.gz`.

## Survey (2026-10-30)

Every TGM member on the disc by variant (`tgm.py list`; counts include every copy):

| Variant | Count | Where |
| --- | --- | --- |
| TGMS with bones (skinned) | 329 | cut-ins (91 in `duel/cutin_*.ehp`, mostly one `cutin-chara-base.tms` per character), field-spell backdrops (53), duel props and card models in `duel/basic*.ehp` (66), field UI (60 in `field/always*`), shop packs (30), card album (6), blackjack (12), others |
| TGMS without bones | 256 | `duel/basic*.ehp` card/field pieces (209), free-roam maps `field/map/bg_*` (40), `duel/cutin_yuberu01/work` (5), two backdrops |
| TGMT node animation, f32 quaternions | 317 plain + 83 gzip | backdrops (55), maps (32), props, UI, shop, album; the 83 gzip ones in cut-ins |
| TGMT node animation, s16 quaternions (flag 4) | 4,309 gzip | cut-in character animations (`duel/cutin_*.ehp`, about 48 per character) |
| TGMT `-etc`, 42 leading tracks | 44 plain + 4,309 gzip | one per cut-in animation, plus `duel/basic*` field-card animations |
| TGMT `-etc`, 84 leading tracks | 92 | backdrops (54), `duel/basic*` (33), shop (5) |
| TGMT `.vtmt` (flag 2, no leading tracks) | 88 gzip | `voice01.vtmt.gz`, one per cut-in archive |
| TGMA with entries / empty | 64 / 62 | backdrops (46 / 9), maps (12 / 20), shop (5), `duel/basic*` (0 / 33), one minigame |

There are no 3D monster models on this disc: no archive outside the list above holds a TGMS, and the
`duel/zakov*.ehp` archives (generic duellists) hold only voice tables. Monsters are shown as card artwork.

## General conventions

- Little-endian. Every offset inside a TGM file is relative to the start of the file (the member).
  No `*ptrs.txt` list points inside a TGM file (see "Pointer lists"). The bind handlers
  (`field_3d_bind_tms` `0x0882e524`, `field_3d_bind_tmt` `0x08830870`, `field_3d_bind_tma`
  `0x08832378`) turn the member-relative header offsets into pointers (see `field_3d.md`).
- Tables follow each other in header order without gaps, except where an alignment is stated.
- "Track" means `(u32 key_count, u32 first_key)`. Tracks index a shared key array; their keys are
  consecutive in track order. A track with no keys stores `first_key = 0`.
- "Scalar key" (16 bytes): `u32 frame, f32 value, f32 handle1, f32 handle2`. The segment from key
  *k* to key *k+1* is the cubic Bézier `(1-u)³·value_k + 3(1-u)²u·handle1_k + 3(1-u)u²·handle2_k +
  u³·value_k+1` with `u = (frame − frame_k) / (frame_k+1 − frame_k)`, i.e. the parameter is linear in
  time. Evidence (high): `field_3d_eval_bezier` `0x088312c0` computes exactly this polynomial, called
  by `field_3d_eval_scalar_segment` `0x08831314` with `u` computed as above. Frames of a track are
  strictly increasing and lower than the file's frame count.
- Sampling rules of `field_3d_sample_scalar_track` `0x0883138c` (high): a track without keys gives
  **0.0** (not a default 1.0, even for scale; no scale track on the disc is empty); one key gives its
  value; a frame at or before the first key gives the first value, at or after the last key the last
  value; otherwise a binary search finds the segment.

## TGMS (mesh)

### Header (0x60 bytes)

| Offset | Type | Field |
| --- | --- | --- |
| `0x00` | char[4] | `TGMS` |
| `0x04` | u32 | Header size, always `0x60`. The primitive table starts here. |
| `0x08` | u32 | Vertex block offset (= end of the primitive table). |
| `0x0C` | u32 | Material table offset. |
| `0x10` | u32 | Texture table offset. |
| `0x14` | u32 | Batch table offset. |
| `0x18` | u32 | Bone table offset (0 without bones). |
| `0x1C` | u32 | Bone matrix table offset (0 without bones). |
| `0x20` | u32 | Root matrix offset. |
| `0x24` | u32 | Name table offset. |
| `0x28` | u32 | Material count. |
| `0x2C` | u32 | Number of textures with an animation index (= TGMA entry count). |
| `0x30` | u32 | Number of opaque materials (material flag bit 0 clear): true in all 585 files (high, data; the reader of this word was not found). |
| `0x34` | u32 | Texture count. |
| `0x38` | u32 | Same value as `0x2C` in all 585 files. |
| `0x3C` | u32 | Bone count (0 to 110 on the disc; 329 skinned, 256 unskinned files). |
| `0x40` | u32 | Index of the first bone without parent; `0xFFFF` without bones. The pose walk (`field_3d_pose_nodes`) starts here. |
| `0x44` | f32[3] | Bounding box minimum (model space). |
| `0x50` | f32[3] | Bounding box maximum. |
| `0x5C` | u32 | Zero in the file; bit 0 is the "bound" flag set by `field_3d_bind_tms`. |

Section order and sizes (all files):

| Section | Size | Notes |
| --- | --- | --- |
| Primitive table | 12 × primitives | Primitives = sum of the batches' primitive counts. |
| Vertex block | runs + 0–3 padding bytes | The primitives' vertex runs tile the block exactly, in any order. |
| Materials | 0xA4 × count | |
| Textures | 0x28 × count | |
| Batches | 24 × batches | Batches = sum of the materials' batch counts. |
| Bones | 8 × bones, zero-padded to 16 | Only with bones; starts right after the batches. |
| Bone matrices | 64 × bones | Only with bones. |
| Root matrix | 64 | Without bones it starts at the batches' end rounded up to 16. |
| Names | to end of file | NUL-terminated texture file names, each start 2-aligned. |

### Draw hierarchy

`material → batches → primitives → vertex runs`:

- Material `+0x9C`: `u16 batch_count, u16 first_batch`; materials take consecutive batch ranges.
- Batch (24 bytes): `s16 palette[8]` (bone indices, used entries first, `-1` after; all `-1`
  without bones), `u32 vertex_type`, `u16 prim_count`, `u16 first_prim`. Each primitive entry
  belongs to exactly one batch; the batch ranges are not always in table order. Three batches of
  skinned files have an empty palette; they are drawn with the root matrix like an unskinned mesh.
- Primitive (12 bytes): `u32 ge_prim` (3 = triangles, 23,571 entries; 4 = triangle strip, 12,238),
  `u32 vertex_count`, `u32 byte offset` into the vertex block. This is exactly a
  `sceGuDrawArray(prim, vertex_type, count, NULL, vertices + offset)` call (non-indexed).
- Winding: with the strip order of the GE (triangle *k* = `k, k+1, k+2`, every odd one reversed),
  counter-clockwise triangles face the side of their stored normals for 97.7 % of the 194,766 lit
  triangles of `duel/bg/` (181,458 of 185,741 skinned, 8,875 of 9,025 unskinned). So "front =
  counter-clockwise" as in glTF (medium-high: data; the GE front-face command was not traced).

### Vertex type (GE `vtype` word)

The batch's `vertex_type` is the GE vertex type word: bits 0–1 texture coordinates, 2–4 colour,
5–6 normal, 7–8 position, 9–10 weights, 11–12 index (never set), 14–16 weight count − 1, 18–20
morph count (never set), 23 through mode (never set). Components are stored in GE order (weights,
UV, colour, normal, position), each aligned to its element size, the vertex to the largest one.
With this rule every primitive's run ends exactly where the next begins in all 585 files. Types on
the disc (batches): `0x8502` 6,099, `0x4502` 5,882, `0x502` 4,548, `0xC502` 3,791, `0x10502` 1,678,
`0x543` 1,024, `0x15F` 805, `0x14502` 469, `0x143` 428, `0x4543` 242, `0x542` 200, `0x10542` 200,
`0x8542` 165, `0xC542` 130, `0x55F` 114, `0x8543` 111, `0x18502` 85, `0x4542` 64, `0xC543` 50,
`0x10543` 11, `0x1C502` 7, `0x14543` 2, `0x51E` 2, `0x455F` 1. So: positions are always s16;
normals s16 or absent; UVs u16 or f32; colour (ABGR8888 or 4444) rare; 1 to 8 u16 weights whenever
the mesh is skinned. Values are normalised as the GE does (16-bit / 32768); vertex weights sum to
1.0.

### Positions, bones and matrices

Matrices are PSP `ScePspFMatrix4`: four column vectors (x axis, y axis, z axis, translation).

- Without bones: model position = root matrix × (s16 position / 32768). The root matrix is
  essentially the de-quantisation scale (for a card plane: diagonal 3.817 = half the bounding box
  extent). All 256 unskinned files lie inside their bounding box.
- With bones: bone record (8 bytes) = `s16 parent, s16 first_child, s16 next_sibling, u16 0`
  (child/sibling links point back consistently in all files; a parent can have a higher index than
  its child). The bone matrices are **offset matrices** (inverse bind pose × de-quantisation).
  Model position = Σ weight_i × node_world[palette_i] × bone_matrix[palette_i] × position.
  Evidence (high, code): `field_3d_update_model` `0x0882fa94` computes, for every bone *i*,
  `skin[i] = node_world[i] × bone_matrix[i]` (`sceVfpuMatrix4Mul(ctx+0x10 + 64i, ctx+0xC + 64i,
  tms+0x1C + 64i)`) after posing the nodes. Data: of the 196 skinned TGMS members with a same-name
  `.tmt`, the posed vertices fall inside the header bounding box at frame 0 for 162 (`check`); the
  other 34 (five distinct meshes) fit at a later frame. The exported `fmagic3720` backdrop stays
  within 0.002 of its header box at frames 0, 50, 100, 200 and 300.
- With bones the root matrix equals the posed matrix of the root bone in the cases inspected
  (album cover: translation 1.101 + animated 1.0 = 2.101). Hypothesis, medium.

### Material (0xA4 bytes)

Read by the draw `field_3d_draw_pass` `0x0882e950`; GE command codes identified from the helpers it calls
(confidence high where a GE command is named).

| Offset | Field |
| --- | --- |
| `0x00` | u32 flags: bit 0 = translucent (drawn in the second pass of `field_3d_draw_model`, opaque materials in the first); bit 1 = double-sided (`GU_CULL_FACE` disabled, else enabled); bit 2 = animated (`+0x98` selects the TGMA entry whose animated copy is drawn); bit 3 = in a visibility group (`+0xA0`). Values on the disc: 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 13. |
| `0x04` | RGBA emissive (GE `EMC`, `0x54`). |
| `0x08` | RGBA ambient (GE `AMC`, `0x55`). |
| `0x0C` | RGBA diffuse (GE `DMC`, `0x56`); equal to `0x08` in every file. |
| `0x10` | RGBA specular (GE `SMC`, `0x57`). |
| `0x14` | f32 specular power (`0x0882a4e8`, after the colours). |
| `0x18` | Four layers of 0x20 bytes (below). Up to two used: 4,218 materials use layer 0 only, 143 use two. |
| `0x98` | u32 TGMA entry index when flag bit 2 is set (206 non-zero, 69 entry 0). |
| `0x9C` | u16 batch count, u16 first batch. |
| `0xA0` | u32 visibility group (0–31) when flag bit 3 is set: the material is skipped while bit `group` of the draw hook's mask (`hook+0x10`) is set. |

Layer (0x20 bytes, at `0x18 + 0x20·k`):

| Offset | Field |
| --- | --- |
| `+0x00` | u32 flags: bit 0 drawn; bit 1 lighting (`GU_LIGHTING` and the material colours, only when the global lighting switch `0x08924c24` bit 0 is set); bit 2 alpha test; bit 3 blending; bit 4 no depth write (GE `ZMSK` = 1); bit 5 alpha writes masked (GE `PMSKA` = 0xFF). On the disc: layer 0 `3`, `7`, `0xB`, `0xF`; layer 1 `9` (143 times). |
| `+0x04` | s32 texture index (−1 = none: `GU_TEXTURE_2D` disabled). Bound to a pointer by `field_3d_bind_tms`. |
| `+0x08` | u32 texture-mapping type: 0 none, 1 → callback `0x0882ef50`, 2 → `0x0882f050` (installed at bind time, run after the state setup). Only 0 and 1 occur; type 1 always on layer 1 with flags 9 and depth function `EQUAL`, i.e. a second pass over the same surface (environment-style overlay, medium). |
| `+0x0C` | RGBA layer colour (`sceGuColor`); the TGMA alpha channel writes its alpha byte. |
| `+0x10` | u8 alpha function, u8 reference, u8 mask (`sceGuAlphaFunc` when bit 2). |
| `+0x13` | u8 depth function (GE `ZTST`): 7 = `GEQUAL` on first layers, 2 = `EQUAL` on overlay layers. |
| `+0x14` | u8 blend op, u8 source, u8 destination, u8 0 (`sceGuBlendFunc` when bit 3). |
| `+0x18` | u32 fixed colour A, `+0x1C` u32 fixed colour B (`GU_FIX` blending). |

### Texture (0x28 bytes)

| Offset | Field |
| --- | --- |
| `0x00` | u32 name offset (into the name table); a pointer after binding. |
| `0x04` | u32 0; the bind hook `0x08924b14` stores a texture handle here. |
| `0x08` | u8, u8: `01 01` in every file; not read by `field_3d_set_texture` (unknown). |
| `0x0A` | u8 texture function, u8 texture alpha (`sceGuTexFunc`, GE `TFUNC` 0xC9): `00 00` (modulate, RGB) 3,421 times, `00 01` (modulate, RGBA) 721. |
| `0x0C` | RGBA texture environment colour (GE `TEC` 0xCA); `FFFFFFFF` everywhere. |
| `0x10` | u8 wrap u, u8 wrap v (GE `TWRAP` 0xC7; 0 = repeat); `0x12`–`0x13` zero. |
| `0x14` | f32 u offset, f32 v offset. |
| `0x1C` | f32 u scale, f32 v scale (1.0 in 4,121 of 4,142). |
| `0x24` | s32 animation (−1 or the TGMA entry index; the indices 0…n−1 are each used once and n = header `0x2C`). |

`field_3d_set_texture` `0x0882e720` draws with `sceGuTexOffset(u_off, 1 − v_off)` and
`sceGuTexScale(u_scale, −v_scale)`: the GE coordinate is `(u·su + ou, (1 − ov) − sv·v)`. The stored
`v` therefore counts from the bottom of the image (high: code, and the exported card pack and album
textures read correctly only with this flip). `tgm.py obj` writes `vt u v` accordingly (it wrote
`1 − v` before 2026-10-30, which mirrored the textures).

Names are source-file names with `.iff` (2,592) or `.tga` (1,550). The GE texture is the GIM member
of the same base name with `.gim` in the same archive for 3,314 of 4,142 references; the rest are
presumably loaded from another archive (open question).

## TGMT (node animation)

### Header (0x38 bytes)

| Offset | Field |
| --- | --- |
| `0x00` | `TGMT` |
| `0x04` | Header size `0x38`; the node table starts here. |
| `0x08` | Scalar track table offset (`0x38 + 8 × nodes`). |
| `0x0C` | Scalar key table offset (+ 8 × tracks). |
| `0x10` | Rotation track table offset (+ 16 × scalar keys). |
| `0x14` | Rotation key frame table offset (+ 8 × rotation tracks). |
| `0x18` | Rotation key value table offset (frame table end rounded up to 16). |
| `0x1C` | Node count. |
| `0x20` | Scalar track count. |
| `0x24` | Scalar key count. |
| `0x28` | Rotation track count. |
| `0x2C` | Rotation key count. |
| `0x30` | Frame count (every key frame is below it; the last key is at count − 1 in 8,352 of 9,242 files). |
| `0x34` | Flags: `4` = rotation values are 4 × s16 (8 bytes), otherwise 4 × f32 (16 bytes); `2` = camera/scene file (`-etc.tmt`, `.vtmt`): its nodes ignore their parents. Bit 0 is the "bound" flag at run time. Values seen: 0, 2, 4. |

The file ends exactly after the rotation values. Node record (8 bytes): `u16 translation_track`
(first of three consecutive scalar tracks x, y, z; `0xFFFF` = none), `s16 rotation_track`
(−1 = none; the used ones are 0, 1, 2… in node order), `s16 scale_track` (first of three; −1 =
none), `u16 0`. Rotation keys: `u32 frame` in the frame table, quaternion `(x, y, z, w)` in the value
table.

Evaluation (`field_3d_pose_nodes` `0x08830944`, high): the walk starts at the TGMS root bone (header
`0x40`) and follows first-child and next-sibling links; node *i* animates bone *i*. For each node,
`world = parent_world × T × R × S` where T is the translation from the three scalar tracks (identity
when absent), R the rotation matrix of the sampled quaternion (skipped when absent) and S scales the
three axis columns by the three scale samples (skipped when absent). A root, or every node of a
flag-2 file, uses the identity as parent. A per-node callback (`hook+4`) may then edit the matrix.

Rotation sampling (`field_3d_sample_rotation_track` `0x088314e4`, high): no key → identity; one key, or a
frame outside the key range → that key as stored; otherwise a binary search and
`system_quat_slerp(q_k, q_k+1, u)` (`0x0881c650`, VFPU: dot product, sign flip of `q_k+1` when the dot
is negative, `asin`/`sin` weights, linear blend when the sine is below 5e-5) followed by
`system_quat_normalize` (`0x0881c904`). With flag 4, `field_3d_decode_quat_s16` `0x08831a18` converts
each component as `s16 / 32760.0` (the constant is `0x46fff000`; not 32767). Component order x, y, z,
w (the code's matrix conversion and the bounding-box fit agree).

Pairs: for 240 non-camera `.tmt` with a same-name `.tms` in the archive, the node count equals the
bone count in every case.

### Playback (`field_3d_update_model` `0x0882fa94`)

Per call, with a frame step (default 1.0): `frame += step`. If the instance's loop flag (`+0x3C` bit 1)
is set, the frame wraps by the loop length `frame_count − 1` (`field_3d_get_loop_length` `0x0882ff84`),
so the last key, which equals the first in looping files, is not shown twice; otherwise it clamps at
`frame_count`. While a cross-fade is active (`+0x3C` bit 0) the pose is
`field_3d_pose_nodes_blend` `0x08830d70` of the previous animation (`+0x18`, frame `+0x28`) and the new
one, translation and scale blended linearly and rotation by slerp, with weight `frame × r` where
`r = 1/frame_count` for animations shorter than 10 frames and 0.1 otherwise (table at `0x08878c60`);
the blend ends when the weight reaches 1. Then the skin matrices are computed (above) and the TGMA is
applied with its own frame counter (`+0x38`), which always wraps at the TGMA frame count. The wall-clock
rate of these calls is not established (the exporter assumes 30 frames per second; `--fps` changes it).

### Scene block of `-etc` files (flag 2)

The scalar tracks before the first one a node uses are scene parameters. Two layouts exist:

| Tracks | Role (reader, confidence) |
| --- | --- |
| 0, 1 | Focal length (mm) and film aperture (inches): vertical field of view `2·atan(0.5·aperture·25.4 / focal)`; aspect 480/272 (`rel_duel_draw` `0x098a093c` and `0x0985b504`, constant 0.03937 = 1/25.4 at `+0x86494`; high). Values: focal 60, 35, 24, 30 …; aperture 1.0 or 0.945. |
| 2, 3 | Near plane (clamped to at least 1.0) and far plane (same functions; high). |
| node 0 | Camera: eye = translation, view direction = R·(0, 0, −1), up = R·(0, 1, 0) (vectors at `rel_duel_draw` `+0x8fa50`/`+0x8fa60`; high). This is the glTF camera convention, so the node maps to a glTF camera node directly. |

84-track layout (92 files: backdrops, `duel/basic*`, shop), read by `field_3d_apply_scene_etc`
`0x0985b504` (high unless stated):

| Tracks | Role |
| --- | --- |
| 4 | Fog switch (integer). |
| 5–7 | Fog colour (× 255, packed by `field_3d_sample_track_rgb` `0x0985b44c`). |
| 8, 9 | Fog near and far. |
| 10–12 | Ambient colour (packed with alpha 0xFF). |
| 13–19 | Not read by this function (constant 1, 0, 1, 35, 1, 1, 0.1 in 91 of 92 files: they repeat a camera block; unknown). |
| 20 + 16·i … | Light *i* (0–3), node *i*+1: `+0` type (0 directional, 1 point, 2 spot), `+1` on/off, `+2..4` ambient, `+5..7` diffuse, `+8..10` specular colour, `+11..13` constant/linear/quadratic attenuation, `+14` spot cut-off (the game uses `cos(value / 2)`), `+15` spot exponent. Position = node translation; direction = R·(0, 0, 1) (medium: which way a GE light vector points is not checked). |

42-track layout (4,353 files: every cut-in animation and the `duel/basic*` card animations):

| Tracks | Role |
| --- | --- |
| 4–9 | Constant 0, 1, 0, 0, 0, 0 in every file; not read by the cut-in camera (unknown; the same slots are the fog block of the 84-track layout). |
| 10 + i (i = 0–31) | Visibility group *i*: `field_3d_update_visibility_mask` `0x09842900` sets mask bit *i* when the track's value is exactly 0, merges the result with two override masks of the cut-in object (`+0x184`, `+0x188`, bit 9/10 special case), and stores it with `field_3d_set_group_mask` `0x0882ffbc` (instance `+0x64`). Materials with flag bit 3 and group *i* (`+0xA0`) are hidden while bit *i* is set (medium-high: the setter and the material test are read, the hand-over from `+0x64` to the draw hook's mask was not traced). |

`.vtmt` (88 files, `voice01.vtmt.gz` in each cut-in archive): flag 2, nine nodes, no leading tracks.
Purpose unknown (lip or face animation driven by voice playback is a guess, low).

## TGMA (texture animation)

Header (0x24 bytes): `TGMA`, header size `0x24`, track table offset (`0x24 + 36 × entries`), key
table offset (+ 8 × tracks), entry count, track count, key count (16-byte scalar keys, as above),
frame count, `u32 0`. The file ends after the keys. 62 of the 126 files are empty (all counts 0
except the frame count `0x79` = 121).

Entry (36 bytes): four layers × `s16 uv_offset_track, s16 uv_scale_track, s16 alpha_track, s16 unused`,
then `u32 material`. Applied by `field_3d_apply_tma` `0x08832428` (high): for each entry and each of the
material's four layers that is drawn (layer flag bit 0) and has an animated texture, it writes into a
per-instance copy of the texture record: UV offset (two tracks u, v; 0 when absent), UV scale (two
tracks; 1.0 when absent), and into the copy of the material, layer colour alpha =
`clamp(trunc(255 × value), 0, 255)`. Slot 3 of a layer is never read. On this disc only layer 0 is
animated: UV offset in 205 entries, UV scale in 34, alpha in 104 (every copy counted).

`material` is a material index of the same-name `.tms`; that material's first-layer texture has
animation index equal to the entry index (93 of 93 same-name pairs; the 33 others are the empty
`coin01_anm` / `dice01_anm*` files, paired with their mesh through a pointer list, not by name). The
track bases of all slots of all entries increase; trailing tracks may have zero keys.

## Pointer lists (`*ptrs.txt`) in archives with TGM members

No list entry points inside a TGM file. Every non-zero entry (all 9,414 in archives containing TGM
members) is the data offset of a whole member: `.tmt.gz` 8,787, `.tmt` 262, `.tms` 178, `.gim` 100,
`.tma` 87; besides these, 117,617 null entries. At bind time each entry becomes a pointer to that
member. Patterns:

- `<anim>-ptrs.txt` with four entries = (`.tms`, `.tmt`, `.tma`, `-etc.tmt`), for example
  `coin01_anm-ptrs.txt` in `duel/basic.ehp`: a resource bundle naming the mesh and its animations.
  The glTF exporter uses these bundles to pair members whose names differ.
- `all-ptrs.txt` / `alletc-ptrs.txt` in every `duel/cutin_*.ehp`: 693 slots each, mostly null,
  the others pointing to the main / `-etc` `.tmt.gz` of each animation: a table indexed by an
  animation id (hypothesis: id = slot, medium).
- `_info-ptrs.txt`: one entry, the character mesh (`cutin-chara-base.tms`).

## glTF export

`tools/tgm_gltf.py` (driven by `tgm.py gltf`) writes glTF 2.0 with the standard library only, plus a JSON
side file for what core glTF cannot hold. Output is derived game data: it must go outside the repository
or under an `extracted/` directory (the tool refuses other paths) and is never committed.

```
python3 -I tools/tgm.py gltf <archive> --member <name.tms> -o <dir>      # + same-stem .tmt, -etc.tmt, .tma
python3 -I tools/tgm.py gltf <archive> --member <name.tms> --tmt <anim.tmt.gz> --tmt <anim-etc.tmt.gz> -o <dir>
python3 -I tools/tgm.py gltf <archive> --member cutin-chara-base.tms --all-tmt -o <dir>   # every matching TGMT
python3 -I tools/tgm.py gltf --check <USRDIR>    # convert and validate everything in memory, write nothing
```

Options: `--fps` (default 30, an assumption), `--flip-winding`, `-v`. Pairing: the same-stem `.tmt`
(node count = bone count), `-etc.tmt` and `.tma`, or the four-entry `<anim>-ptrs.txt` bundle that names
the mesh; `--tmt` adds members (an `-etc` file replaces the camera; the first node animation gives the
rest pose); `--all-tmt` adds every non-camera TGMT whose node count matches.

Files per model: `<stem>.gltf`, `<stem>.bin`, one PNG per distinct GIM (decoded with `tools/gim.py`), and
`<stem>.tgm.json`.

Mapping (confidence of the mapping itself in brackets):

| TGM | glTF |
| --- | --- |
| Vertices | `POSITION` = s16/32768 as stored (skinned meshes) or with the root matrix as the mesh node's `matrix` (unskinned meshes and palette-less batches); `NORMAL` normalised; `TEXCOORD_0` = `(u, 1 − v)`; `COLOR_0` (8888, or 4444/5551/5650 expanded); `JOINTS_0/1` = batch palette entries, `WEIGHTS_0/1` normalised to sum 1 (high). |
| Primitives | One glTF primitive per material and attribute signature; triangle lists with indices (strips unrolled, degenerate joints dropped; counter-clockwise front) (high). |
| Bones | One node per bone (`bone000`…), children from the bone table; one skin with `inverseBindMatrices` = the bone offset matrices (PSP column order is glTF's column-major order), `skeleton` = root bone (high). |
| Rest pose | Frame 0 of the first node animation; identity without one (medium: the game has no separate bind pose). |
| Node animation | Translation and scale: the three scalar tracks are merged on the union of their key frames; each Bézier segment is split exactly at the extra frames (de Casteljau) and written as `CUBICSPLINE` with Hermite tangents `3(h1 − v0)/dt` and `3(v1 − h2)/dt` (or `LINEAR` when every segment is linear). Rotation: the keys, normalised and sign-aligned, as `LINEAR` (glTF slerp = the game's slerp). A path without a track gets a constant channel with the game's default (0 / identity / 1) when the rest pose differs, because the game does not fall back to a rest pose (high). |
| `-etc` camera | Perspective camera at frame 0 (yfov from tracks 0/1, znear `max(track 2, 1)`, zfar track 3, aspect 480/272) on a root node animated by node 0; merged into the first animation. Light nodes 1–4 are exported as empty nodes with their animation (high for the camera; lights only in the side file). |
| Materials | `baseColorFactor` = layer 0 colour, `baseColorTexture` with `KHR_texture_transform` (offset `(ou, 1 − ov − sv)`, scale `(su, sv)`) when the texture record is not the identity, `doubleSided` = flag bit 1, `alphaMode` `BLEND` (flag bit 0 or layer blending) or `MASK` (alpha test with `GREATER`/`GEQUAL`, cutoff = ref/255), `KHR_materials_unlit` when layer 0 has no lighting (medium: GE state approximated by PBR). Samplers from the wrap bytes. |

Side file (`format: "tf3-tgm-scene"`, `version: 1`): `source` (archive, member, paired animations), `fps`,
`model` (header box, opaque material count, bones with their glTF node, root matrix, every material's full
render state per layer, every texture record with its glTF texture), `animations` (per TGMT: member, its
glTF animation index or `null` when it has no channel, flags, frame count, loop length, and every node's
raw tracks: Bézier keys `[frame, value, h1, h2]` and rotation keys `[frame, x, y, z, w]` as decoded),
`scene` (for an `-etc` file: layout, every leading track with its role and raw keys, lights summary, the
camera at frame 0, the nodes' raw tracks), `texture_animation` (TGMA entries per layer with raw keys and
the formula), `unknown` (every instance of a field whose meaning is not established, with its raw value).

`--check` converts every TGMS with its pairs (here with `--all-tmt` pairing, so one TGMT can be checked
against several meshes of an archive), validates the glTF (accessor bounds, index range, joint range,
weight sums, unit normals, affine inverse bind matrices, single parent per node, increasing sampler times,
output counts, one channel per node path), compares the glTF curves with the game sampler at up to seven
frames per animation (the first three animations of each model, and every unpaired TGMT), converts every
TGMT/TGMA left over on its own, and prints the unknown-field census. Results on the EU disc (2026-10-30,
4 min 13 s):

| Item | Result |
| --- | --- |
| Models converted | 585 (329 with a skin), 1,186,744 triangles, 1,952 texture images decoded, 828 texture references without a same-archive GIM |
| Model/animation pairs | 5,251; `-etc` scenes with a model 81; TGMA with a model 115 |
| Converted without a model | 90 node animations, 4,452 `-etc`/`.vtmt`, 11 TGMA (so every TGM member was converted at least once) |
| `failing` | 0 |
| Largest deviation glTF vs game sampler | translation 2.2e-5 (relative), scale 6.1e-7, rotation 1.7e-5 (quaternion chord): f32 rounding of the stored tangents |
| Unknown-field census (instances / not zero or not the common value) | texture `+0x08/+0x09` 4,142 / 0 (`01 01`); texture `+0x12/+0x13` 4,142 / 0; texture `+0x04` 4,142 / 0; layer map type 17,444 / 143; layer blend pad 17,444 / 0; layer flag bits above 5 17,444 / 0; material flag bits above 3 4,361 / 0; TGMT node pad 309,196 / 0; unassigned `-etc` tracks 26,762 / 4,902 |

Validation beyond the check:

- `duel/bg/fmagic3720.ehp` (the backdrop of card 3720) exported with its `-base.tmt`, `-base-etc.tmt`
  and `.tma` and rendered headless through the exported camera with an independent glTF evaluator and
  rasteriser (numpy, scratch tool outside the repository): a coherent scene (ground, sky dome, a tree
  whose roots move over the 301 frames); posed bounding box equal to the TGMS header box within 0.002 at
  frames 0–300.
- `duel/cutin_abdos01.ehp`: `cutin-chara-base.tms` (78 bones, 11,645 triangles) with
  `D_draw103.tmt.gz` (s16 quaternions, 70 frames) and `D_draw103-etc.tmt.gz` as camera: the character is
  framed by the exported camera at frames 0, 35 and 69 and goes through a card-draw motion; textures
  (face, costume) are oriented correctly.
- `shop/all_s.ehp:pack11.tms` and `database/cardalbum.ehp:album_cover00.tms`: the logo and the "Album"
  lettering read correctly, which fixes the V convention; the album cover opens over frames 0–40.

Confidence of the decoded fields: high for geometry, skin, node animation (tracks, Bézier, slerp,
defaults, s16 scale), TGMA application, material flags and layer state that map to named GE commands, and
the camera; medium for the mapping of GE render state to glTF PBR, the light directions, the visibility
hand-over and the root-matrix hypothesis; low/unknown as listed below. Timing in seconds is an
assumption (`--fps`).

## Tool

```
python3 -I tools/tgm.py list <ehp or directory>...
python3 -I tools/tgm.py inspect <archive.ehp> <member>          # .gz suffix optional
python3 -I tools/tgm.py check <USRDIR> [-v]                       # all rules above, whole disc
python3 -I tools/tgm.py obj <archive.ehp> <member.tms> -o extracted/tgm/<name> [--tmt X --frame N]
python3 -I tools/tgm.py gltf <archive.ehp> --member <member.tms> -o extracted/tgm/<name> [--tmt X] [--all-tmt]
python3 -I tools/tgm.py gltf --check <USRDIR>
```

`obj` writes OBJ + MTL (one object per material, triangle strips unrolled, degenerate joints
dropped) and decodes the textures through `tools/cip.py`'s GIM reader to PNG. Skinned meshes are
posed with the same-name `.tmt` (or `--tmt`) at frame 0. UV offset/scale of the texture record is
not applied. Keep exports out of git.

## Open questions

- The wall-clock rate of `field_3d_update_model` calls (30 or 60 per second, or a variable step) for each
  user (backdrops, cut-ins, field UI); needs a PPSSPP trace of the step argument.
- What texture-mapping types 1/2 do exactly (`0x0882ef50` / `0x0882f050` emit GE texture-map mode and
  light-source state; environment or projection mapping?) and how the second (`EQUAL` depth) layer blends.
- Texture bytes `+0x08`/`+0x09` (`01 01`) and the reader of TGMS header `0x30`.
- The 84-track `-etc` tracks 13–19 and the 42-track tracks 4–9; the direction convention of GE lights.
- How the cut-in's group mask (`+0x64`) reaches the draw hook's mask (`hook+0x10`); which objects own the
  32 visibility groups (props, alternative hands or faces?).
- The role of `.vtmt`.
- Where the 828 textures without a same-archive `.gim` come from (character faces from `cutin_da_faces`,
  shared textures from `cutin_common.ehp`?).
- The GE front-face setting (winding was established from normals, not from code).
