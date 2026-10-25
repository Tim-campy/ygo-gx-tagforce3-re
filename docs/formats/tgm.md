# TGM model family: TGMS, TGMT, TGMA

Status: `documented` (structure), with the semantics marked per field. Tool: `tools/tgm.py`
(`list`, `inspect`, `check`, `obj`); tests `tools/tests/test_tgm.py` (synthetic data only).
`.tmf` (the 2D layout partner of `.ehf`) is a different format and is not covered here.

Three member types of EHP archives (`ehp.md`) share the `TGM?` magic and the same building blocks:

| Extension | Magic | Members on the disc | Role (confidence) |
| --- | --- | --- | --- |
| `.tms` | `TGMS` | 585 | Mesh: GE vertex data, materials, textures, skeleton (high). |
| `.tmt` | `TGMT` | 453 plain + 8,701 `.tmt.gz` + 88 `.vtmt.gz` | Node animation: translation/scale curves and rotation keys per bone (high); `-etc` variants also hold camera/scene parameters (medium). |
| `.tma` | `TGMA` | 126 | Texture/material animation: UV offset, UV scale and one scalar channel per animated texture (medium-high). |

All 9,953 members (counting every copy in every archive, nested archives included) pass every rule
below: `python3 -I tools/tgm.py check <USRDIR>` reports `failing: 0`. Note the 88 `.vtmt.gz`
members in `duel/cutin_*.ehp` (`voice01.vtmt.gz`): they are TGMT too, which accounts for the
difference between 8,789 gzip members (`ehp.md`) and 8,701 `.tmt.gz`.

General conventions:

- Little-endian. Every offset inside a TGM file is relative to the start of the file (the member).
  No `*ptrs.txt` list points inside a TGM file (see "Pointer lists"); the bind handlers
  (`field_3d_bind_tms` `0x0882e524`, `field_3d_bind_tmt` `0x08830870`, `field_3d_bind_tma`
  `0x08832378`) presumably turn these member-relative offsets into pointers (not verified in code).
- Tables follow each other in header order without gaps, except where an alignment is stated.
- "Track" means `(u32 key_count, u32 first_key)`. Tracks index a shared key array; their keys are
  consecutive in track order. A track with no keys stores `first_key = 0`.
- "Scalar key" (16 bytes): `u32 frame, f32 value, f32 handle1, f32 handle2`. The segment from key
  *k* to key *k+1* is a cubic Bézier in value with control values
  `(value_k, handle1_k, handle2_k, value_k+1)`. Evidence: on linear stretches the four values are
  equally spaced (for example −8.1967, −7.9539, −7.7111, −7.4683); constant tracks repeat the value.
  The parameter is assumed linear in frame time (medium). Frames of a track are strictly increasing
  and lower than the file's frame count.

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
| `0x30` | u32 | Unknown count (see open questions). |
| `0x34` | u32 | Texture count. |
| `0x38` | u32 | Same value as `0x2C` in all 585 files. |
| `0x3C` | u32 | Bone count (0 to 110 on the disc; 329 skinned, 256 unskinned files). |
| `0x40` | u32 | Index of the first bone without parent; `0xFFFF` without bones. |
| `0x44` | f32[3] | Bounding box minimum (model space). |
| `0x50` | f32[3] | Bounding box maximum. |
| `0x5C` | u32 | Zero. |

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
  belongs to exactly one batch; the batch ranges are not always in table order.
- Primitive (12 bytes): `u32 ge_prim` (3 = triangles, 23,571 entries; 4 = triangle strip, 12,238),
  `u32 vertex_count`, `u32 byte offset` into the vertex block. This is exactly a
  `sceGuDrawArray(prim, vertex_type, count, NULL, vertices + offset)` call (non-indexed).

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
  its child). The bone matrices are **offset matrices** (inverse bind pose × de-quantisation):
  applied alone they do not give a meaningful shape. Model position =
  Σ weight_i × node_world[palette_i] × bone_matrix[palette_i] × position, where node_world comes
  from a TGMT (node *i* animates bone *i*, hierarchy from the TGMS bone table). Evidence: of the 196
  skinned TGMS members with a same-name `.tmt` in their archive, the posed vertices fall inside the
  header bounding box (1 % tolerance) at frame 0 for 162 (`check` output); the other 34 are copies
  of five distinct meshes, and each of those fits at a later frame (for example `gx_pda_cover01` from frame 24 on), i.e. the
  bounding box was taken in another pose. Confidence: high.
- With bones the root matrix equals the posed matrix of the root bone in the cases inspected
  (album cover: translation 1.101 + animated 1.0 = 2.101). Hypothesis, medium.

### Material (0xA4 bytes)

| Offset | Field | Observation |
| --- | --- | --- |
| `0x00` | u32 | Unknown, 0–10 (0 in 1,761 of 4,361 materials, 8 in 1,334). |
| `0x04` | RGBA | `000000FF` almost always (emissive? low). |
| `0x08` | RGBA | Diffuse (medium). |
| `0x0C` | RGBA | Always equal to `0x08` (ambient? low). |
| `0x10` | RGB + 0 | Specular (`808080` / `000000`; medium). |
| `0x14` | f32 | Specular power (20.0 in 3,837; medium). |
| `0x18` | u32 | Flags: `3` 3,525, `0xB` 766, `7` 40, `0xF` 30. Bit 3 correlates with blended layers (low). |
| `0x1C` | 4 × 32 bytes | Texture layers, see below. Up to two used (4,090 one, 26 two, 245 none). |
| `0x98` | u32 | 0 in 4,155 materials, else small; in the files inspected it equals the animation index of the material's texture (hypothesis, medium). |
| `0x9C` | u16, u16 | Batch count, first batch. |
| `0xA0` | u32 | Unknown (0, 1, 3, 7, 0xB, 0xC, 0xD, 0xF, …). |

Layer (32 bytes): `s32 texture` (index into the texture table, −1 = unused), `u32` 0 or 1, `RGBA`
colour (layer 0: equals the diffuse colour), 4 bytes state (`00 00 00 07` or `07 xx FF 07`;
alpha-test parameters? low), 4 bytes blend `(op, src, dst, 0)` in `sceGuBlendFunc` encoding
(`00 02 03 00` = add, src alpha, one-minus-src alpha; `00 02 0A 00`, `00 0A 0A 00` use fixed
colours; medium), two fixed colours (RGB + 0) for `GU_FIX` blending, then a u32 (0 or 9 on layer 0
when a second layer is present).

### Texture (0x28 bytes)

`u32 name offset` (into the name table), `u32 0`, 4 bytes mode (`01 01 00 00` 3,421 /
`01 01 00 01` 721; wrap/clamp or filter flags, low), `s32 −1`, `u32 0`, `f32 u_offset, v_offset`,
`f32 u_scale, v_scale` (1.0 in 4,121 of 4,142), `s32 animation` (−1 or the TGMA entry index; the
indices 0…n−1 are each used once and n = header `0x2C`).

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
| `0x30` | Frame count (every key frame is below it; the last key is usually at count − 1). |
| `0x34` | Flags: `4` = rotation values are 4 × s16 / 32767 (8 bytes), otherwise 4 × f32 (16 bytes); `2` = camera/scene file (`-etc.tmt`, `.vtmt`). Values seen: 0, 2, 4. |

The file ends exactly after the rotation values. Node record (8 bytes): `u16 translation_track`
(first of three consecutive scalar tracks x, y, z; `0xFFFF` = none), `s16 rotation_track`
(−1 = none; the used ones are 0, 1, 2… in node order), `s16 scale_track` (first of three; −1 =
none), `u16 0`. Rotation keys: `u32 frame` in the frame table, quaternion `(x, y, z, w)` in the value
table, all unit length. The local transform is translation × rotation × scale; defaults are 0,
identity, 1. Order of quaternion components: x, y, z, w (the w-first reading fits the bounding boxes
far worse: 123 vs 160 of 194 test cases at frame 0). Interpolation between rotation keys is not established
(the tool blends linearly and normalises).

Pairs: for 240 non-camera `.tmt` with a same-name `.tms` in the archive, the node count equals the
bone count in every case.

Variants:

- Main animations (`duel/cutin_*` `.tmt.gz`, flags 4; plain files flags 0).
- `-etc.tmt[.gz]` (flags 2): 4,353 files have one node whose tracks start at 42, 92 have five nodes
  starting at 84. The leading 42 (84) scalar tracks are not referenced by any node and hold scene
  parameters; in one example track 0 = 60, track 3 = 1000 (constant), track 16 = 35, 19 = 0.1,
  20 = 1000. Hypothesis (medium): camera blocks (field of view, near/far planes and similar); the
  node is the camera, animated by its translation/rotation.
- `.vtmt.gz` (88, flags 2): nine nodes, no leading tracks. Purpose unknown ("voice"?).

## TGMA (texture animation)

Header (0x24 bytes): `TGMA`, header size `0x24`, track table offset (`0x24 + 36 × entries`), key
table offset (+ 8 × tracks), entry count, track count, key count (16-byte scalar keys, as above),
frame count, `u32 0`. The file ends after the keys. 62 of the 126 files are empty (all counts 0
except the frame count `0x79` = 121).

Entry (36 bytes): `s16 slot[16]`, `u32 material`. Only slots 0–2 are used (all 64 non-empty files):

| Slot | Tracks | Meaning (confidence) | Example |
| --- | --- | --- | --- |
| 0 | 2 (u, v) | UV offset (high: values run 0 → 1 or 0 → −1 over the whole animation, i.e. scrolling) | 203 uses |
| 1 | 2 (u, v) | UV scale (medium: values 1, 4, 10) | 34 uses |
| 2 | 1 | Scalar, 0…1 (alpha / blend amount? low) | 91 uses |

`material` is a material index of the same-name `.tms`; that material's first-layer texture has
animation index equal to the entry index (93 of 93 same-name pairs; the 33 others are the empty
`coin01_anm` / `dice01_anm*` files, paired with their mesh through a pointer list, not by name). The track bases of all slots of
all entries increase; trailing tracks may have zero keys.

## Pointer lists (`*ptrs.txt`) in archives with TGM members

No list entry points inside a TGM file. Every non-zero entry (all 9,414 in archives containing TGM
members) is the data offset of a whole member: `.tmt.gz` 8,787, `.tmt` 262, `.tms` 178, `.gim` 100,
`.tma` 87; besides these, 117,617 null entries. At bind time each entry becomes a pointer to that
member. Patterns:

- `<anim>-ptrs.txt` with four entries = (`.tms`, `.tmt`, `.tma`, `-etc.tmt`), for example
  `coin01_anm-ptrs.txt` in `duel/basic.ehp`: a resource bundle naming the mesh and its animations.
- `all-ptrs.txt` / `alletc-ptrs.txt` in every `duel/cutin_*.ehp`: 693 slots each, mostly null,
  the others pointing to the main / `-etc` `.tmt.gz` of each animation: a table indexed by an
  animation id (hypothesis: id = slot, medium).
- `_info-ptrs.txt`: one entry, the character mesh (`cutin-chara-base.tms`).

## Tool

```
python3 -I tools/tgm.py list <ehp or directory>...
python3 -I tools/tgm.py inspect <archive.ehp> <member>          # .gz suffix optional
python3 -I tools/tgm.py check <USRDIR> [-v]                       # all rules above, whole disc
python3 -I tools/tgm.py obj <archive.ehp> <member.tms> -o extracted/tgm/<name> [--tmt X --frame N]
```

`obj` writes OBJ + MTL (one object per material, triangle strips unrolled, degenerate joints
dropped) and decodes the textures through `tools/cip.py`'s GIM reader to PNG. Skinned meshes are
posed with the same-name `.tmt` (or `--tmt`) at frame 0. UV offset/scale of the texture record is
not applied. Keep exports out of git.

## Open questions

- TGMS header `0x30`: equals the number of materials without flag bit 3 in 566 of 585 files, but not
  always; meaning unknown.
- Material `0x00`, `0x04`, `0x0C`, `0xA0`, the layer state word and the second u32 of a layer.
- Texture mode bytes and the constant fields (`+0x04`, `+0x0C`, `+0x10`).
- Rotation interpolation (slerp vs. normalised lerp) and whether the Bézier parameter is linear in
  time; confirm in PPSSPP or in `field_3d_bind_tmt` / the animation player.
- The 42 leading scalar tracks of `-etc.tmt` (camera model) and the role of `.vtmt`.
- TGMA slot 2 (alpha?) and slots 3–15 (never used on this disc).
- Where the 828 textures without a same-archive `.gim` come from.
- Confirm that the bind handlers convert exactly the header offsets (and nothing else) to pointers.
