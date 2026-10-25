# EHF 2D layout and TMF texture flags

Status: `named` (layout fully parsed and cross-checked on the whole disc; field semantics partly hypotheses). Tool: `tools/ehf.py` (`list`, `inspect`, `check`, `render`). Tests: `tools/tests/test_ehf.py` (synthetic data only).

An `.ehf` is a **vector-animation timeline converted from Flash/SWF**: a stage measured in twips (1/20 pixel), a main timeline of place/remove records with depths and clip (mask) depths, shapes made of textured quads stored as ready-made PSP GE display lists, nested movie clips with their own timelines, and keyframe tracks for an affine matrix and a colour transform. Each `.ehf` lives in an EHP archive next to its textures (`<name>.gim`) and, usually, a `.tmf` with one flag byte per texture.

Evidence for the Flash origin (high confidence): one archive is literally called `umd_replace/basic/swf.ehp`; the stage rectangle is stored as `xmin, xmax, ymin, ymax` in twips (`0, 9600, 0, 5440` = 480 × 272 px × 20), the SWF `RECT` order; the timeline records behave exactly like SWF `PlaceObject`/`RemoveObject`/`ShowFrame` with depths and clip depths; the stage background colour is stored like SWF `SetBackgroundColor`.

## Counts on the disc

`python3 -I tools/ehf.py check USRDIR SYSDIR/BOOT.BIN` parses and cross-checks **1,225 `.ehf`** with no failure: 1,184 in the 609 top-level archives (1,029 in the 531 loose `.ehp` files, which is the count in `ehp.md`, plus 155 in the 78 gzip-wrapped `field/*.gz`), 40 in the 20 nested archives of `minigame/`, and `loading.ehf` in the archive embedded in `BOOT.BIN` (file offset `0xc84d4`, vaddr `0x088cc480`). 689 of them have a `.tmf` (668 top-level, 20 nested, 1 in `BOOT.BIN`); every `.tmf` has an `.ehf` of the same base name.

Totals: 7,881 shapes, 365 clips, 15,390 primitives, 20,889 tracks, 29,133 timeline records, 8,234 texture-name slots.

## File layout

Little-endian. All offsets in the header are relative to the start of the `.ehf`.

| Offset | Size | Field |
| --- | --- | --- |
| `0x00` | 4 | Magic `45 48 46 1A` (`"EHF\x1a"`). |
| `0x04` | 12 | Zero. |
| `0x10` | `5 × 8` | Section table: `(u32 offset, u32 size)` for sections 0–4 below. |
| `0x38` | 8 | Sixth entry, always `(0, 0)`. |
| `0x40` | | Sections, in order, each starting at the next multiple of 16; the last one ends exactly at the end of the file (all 1,225 files). |

| # | Section | Content |
| --- | --- | --- |
| 0 | Stage (`0x20` bytes, always at `0x40`) | See below. |
| 1 | Work area | Zero on disc. Its size is always `align16(0x78 + 0x28 × P)`, where `P` is the peak number of live display instances (a clip instance counts 1 plus the peak of its own timeline). Holds per-instance runtime state (hypothesis, high: the size formula holds for every file and the area is never non-zero). |
| 2 | Main timeline | `N × 12`-byte records (below). |
| 3 | Objects | Shapes and clips, each starting at a multiple of 16 (relative to the section). Timeline records refer to an object by `offset / 16`. |
| 4 | Texture names | 16-byte slots, each a NUL-terminated cp932 name (≤ 15 bytes) without extension, or empty. Shapes refer to a texture by slot offset (`0x00`, `0x10`, …). |

### Stage (section 0)

| Offset | Type | Field |
| --- | --- | --- |
| `0x00` | u32 | Frame count of the main timeline; always equals the sum of its waits. |
| `0x04` | 4 × u8 | Background colour R, G, B, A (17 different values; A is always `0xFF`). Not drawn by `tools/ehf.py` unless `--background` is given; whether the game draws it is open. |
| `0x08` | u32 | 2 (1,039 files), 1 (185) or 4 (`loading.ehf`). Hypothesis (low): frame step in vsyncs (60/rate fps). |
| `0x0C` | u32 | 0. |
| `0x10` | 4 × s32 | Stage `xmin, xmax, ymin, ymax` in twips: `0, 9600, 0, 5440` (1,193 files, 480 × 272 px), `0, 1840, 0, 1280` (24, 92 × 64 px), `0, 14400, 0, 5440` (8, 720 × 272 px). |

### Timeline record (main timeline and clip timelines)

| Offset | Type | Field |
| --- | --- | --- |
| `0x00` | s32 | Object offset / 16 within section 3, or `-1`: remove whatever is at this depth. |
| `0x04` | u16 | Track index in the placed object's animation table. |
| `0x06` | u16 | Depth (draw order, larger on top). |
| `0x08` | u16 | Clip depth: when non-zero this placement is a mask for the depths above it up to this value (576 records). |
| `0x0A` | u16 | Frames to wait after this record (0 = the next record happens on the same frame). |

Records are processed in order with a running frame counter; placing at an occupied depth replaces the instance. The waits of every timeline add up to its frame count (all 1,225 main timelines and all 365 clips). A track's key frames are relative to the frame the record was executed (every keyed track starts at key frame 0). Clip-depth semantics are confirmed visually: in `chra_make01.ehf` an untextured black bar placed with clip depth 3 grows vertically and reveals only the layers at depths 2–3.

### Objects (section 3)

Every object starts with `u32 type`: `0` shape (7,881) or `3` clip (365). No other type occurs.

**Shape** (header `0x30` bytes):

| Offset | Type | Field |
| --- | --- | --- |
| `0x00` | u32 | 0. |
| `0x04` | 2 × f32 | Anchor `x, y` in twips, added to every vertex after scaling (usually minus half the size, so the shape is centred on its origin). |
| `0x0C` | f32 | Vertex scale: twips per vertex unit (for example `2.5012 = 5120 / 2047` for a 256 px wide quad spanning vertex x 0..2047; 1.0 in 4,169 shapes, mostly the vector ones). |
| `0x10` | 3 × (u32, u32) | `(offset, size)` relative to the object of: display list, vertex block, animation block. |
| `0x28` | 8 | Zero. |

Display list: six GE words per primitive, always in this order:

| Word | GE command | Meaning |
| --- | --- | --- |
| 1 | `0x55` (ambient colour) | RGB of the primitive (`ffffff` for 14,737 of 15,390; flat colours for vector shapes). |
| 2 | `0x58` (ambient alpha) | Alpha, `0xFF` everywhere. |
| 3 | `0x12` (vertex type) | `0x102` (16-bit UV + 16-bit position) or `0x100` (16-bit position only). |
| 4 | `0xFF` / `0x00` | Placeholder, not a GE command: `0xFF` with parameter `0xFF0000 | slot` names the texture slot (section 4); `0x00` = untextured. |
| 5 | `0x00` | Placeholder: parameter is the byte offset of the primitive's vertices in the vertex block. |
| 6 | `0x04` (prim) | Primitive type and vertex count: triangle strips (15,192, almost all 4-vertex quads), triangle fans (182) and line strips (16, not drawn by the tool). |

Words 4 and 5 are presumably patched into real texture/vertex-address commands when `ui_bind_ehf` binds the layout (hypothesis, medium: they are relative offsets that cannot be executed as they are).

Vertices: optional `u16 u, v` then `s16 x, y, z` (GE order). UV 0..2047 spans the power-of-two texture (all UVs are ≤ 2047); `z` is `0x4000` in every vertex. Vertex `y` grows downwards, like the screen.

**Clip** (header `0x20` bytes): `u32 3`, `u32 frame count`, `(u32 offset, u32 size)` of its timeline (same 12-byte records), `(u32 offset, u32 size)` of its animation block, zero padding. A clip instance plays its own timeline and loops (Flash movie-clip semantics; `tools/ehf.py` renders local frame `t mod frames`). Example: the "loading" text in `loading.ehf` is a 3-frame clip that swaps three shapes.

### Animation block and tracks

The block begins with a table of `u32` offsets (relative to the block; 0 = unused); its length is the first offset / 4 (4, 8, 12, 16, 20, 24 or 44 entries seen). A timeline record selects an entry with its track index, so one object can be placed several times with different motions.

Track:

| Offset | Type | Field |
| --- | --- | --- |
| `0x00` | 4 × f32 | Base matrix `a, b, c, d`. |
| `0x10` | 2 × f32 | Base translation `tx, ty` (twips). |
| `0x18` | 3 × f32 | Dequantisation steps for the translate, scale and skew channels. |
| `0x24` | u16 | Channel flags. |
| `0x26` | u16 | Key count (0 in 5,153 static tracks). |
| `0x28` | u16 | Key stride `2 + 4 × popcount(flags & 0x1F)`. |
| `0x2A` | u16 | 0. |
| `0x2C` | | Keys: `u16 frame`, then 4 bytes per present channel in bit order. |

| Bit | Channel (tracks using it) | Key data | Applied as |
| --- | --- | --- | --- |
| 0 | translate (4,731) | `s16 qx, qy` | `tx += qx × step0`, `ty += qy × step0` |
| 1 | scale (3,486) | `s16 qa, qd` | `a += qa × step1`, `d += qd × step1` |
| 2 | skew (608) | `s16 qb, qc` | `b += qb × step2`, `c += qc × step2` |
| 3 | multiply (11,150) | `u8 r, g, b, a` | colour × value / 128 (`0x7F` ≈ 1.0, never above `0x80`) |
| 4 | add (5,941) | 4 bytes | Colour offset; the tool reads `s8 × 2` (hypothesis, low) |
| 5 | ? (2 tracks, `ryusen01.ehf`) | none | Unknown; stride ignores it |

The base values are the centre of each channel's range, and quantised values span about ±32,760, so a step is (range / 2) / 32,767. Example: a rotation from 30° to 0° at scale 1.5 is stored as base `[1.3995, -0.375, 0.375, 1.3995]`, scale keys from -32,759 to 32,760 with step `3.07e-6` (±0.1) and skew keys with step `1.14e-5` (±0.375); the reconstructed matrix keeps `|scale| = 1.5` at every key, which pins down the channel assignment.

Point mapping (confidence high, chosen by rendering): `x' = a·x + c·y + tx`, `y' = b·x + d·y + ty`, i.e. `a, b, c, d` = SWF `ScaleX, RotateSkew0, RotateSkew1, ScaleY`. The opposite order visibly tears apart the rotated multi-part character in `loading.ehf`. Nested clips compose parent × child.

Between keys the tool interpolates linearly and holds the first/last key outside them (hypothesis, medium: key spacing looks like it marks the ends of linear segments; the game's interpolation is not yet traced).

Full transform of a vertex: `(vx·scale + anchor_x, vy·scale + anchor_y)` → track matrix → parent clips → minus `xmin/ymin` → divide by 20 for pixels.

## TMF

Size 1–40 bytes, no header: one byte per texture-name slot of the `.ehf` with the same base name (682 of 689). Values: `0x00` (1,358 slot uses), `0x11` (612), `0x10` (381), `0x01` (275).

- **Bit 0 = additive blending** (hypothesis, medium). Rendering `loading.ehf` and `chra_make01.ehf` with src-over draws an opaque black square around a glow and a halo; additive blending for the flagged slots removes it. Over the distinct textures, 31 textures whose sampled texels are ≥ 70 % opaque black all have bit 0 set, while no texture without bit 0 is more than 60 % opaque black.
- **Bit 4**: unknown. No correlation with GIM format, size or power-of-two dimensions. Candidates: bilinear filtering or UV clamping.
- 7 pairs do not match: 4 localised `duel/start/start_<l>.ehp/vs_bg01_1` have 9 slots and a `.tmf` of 8 bytes (the English one has 8 slots: the `.tmf` was not regenerated), `minigame/reversi/lang_ger.ehp/mini_rv_turn` (2 bytes, 4 slots), and two `umd_circle01` without textures and a 1-byte `.tmf`. 536 `.ehf` have no `.tmf`; how the binder treats a missing one is open.

## Textures

Every texture slot resolves to a member `<name>.gim` in the same archive (all 8,234, case-insensitive). 8,126 names are the layout name, truncated so that the whole name fits 15 bytes, followed by a 4-digit number (for example `press_start` → `press_start0001`). Formats and swizzling are in `docs/formats/gim.md`; on screen one texel is one pixel at scale 1.

`*ptrs.txt` resource lists are not related: none of their 138,113 entries falls inside an `.ehf` or `.tmf` member (they fall in the entry table and inside `.gz`, `.tmt`, `.tms`, `.gim` and `.tma` members).

## Rendering check

`tools/ehf.py render` (output only under an `extracted/` directory) was compared visually: `loading.ehf` (a chibi magician with an additive glow at the tip of her staff, bottom right), `title_menu_e.ehp/main_title01.ehf` frame 200 (the complete title screen with logo, characters and copyright line), `press_start.ehf` (button centred at x = 240, y = 234), `chra_make01.ehf` frame 20 (mask reveal, character with additive halo), `database/charalist.ehp/d_menu_bg01.ehf` (animated background built from clip instances) and `umd_replace/basic/swf.ehp/umd_circle01.ehf` (untextured vector circles). All look coherent; this supports the stage size, twips, anchors, the matrix order and the clip semantics.

## How the game binds it

`container_ehp_bind_members` calls `ui_bind_ehf(ehf, tmf, 0x088227d0, ehp)` (`0x0881e56c`) with the `.tmf` of the same base name, then `0x0881e6a4(480.0, 272.0, 240.0, 136.0, ehf, 0)` (`docs/formats/ehp.md`). With the format known, the first four arguments are probably the screen size and the origin used to map the 9600 × 5440 twip stage to the screen (hypothesis, medium). These functions were not opened in this work (no disassembler was used).

## Open questions

- What `ui_bind_ehf` writes into words 4–5 of each primitive and how the callback `0x088227d0` resolves texture names (presumably `container_ehp_find_member(ehp, name + ".gim")`).
- Stage field `0x08` (frame step?); whether the background colour is drawn.
- Exact interpolation between keys, and the meaning and encoding of the `add` channel (bit 4) and of flag bit 5.
- `.tmf` bit 4, confirmation of bit 0 = additive blending, and what happens without a `.tmf`.
- Whether placing the same object again at an occupied depth restarts its track (the tool restarts it).
- Line-strip primitives (16) are not drawn by the tool.
