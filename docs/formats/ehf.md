# EHF 2D layout and TMF texture flags

Status: `named` (layout fully parsed and cross-checked on the whole disc; field semantics partly hypotheses). Tool: `tools/ehf.py` (`list`, `inspect`, `check`, `render`, `json`). Tests: `tools/tests/test_ehf.py` (synthetic data only).

An `.ehf` is a **vector-animation timeline converted from Flash/SWF**: a stage measured in twips (1/20 pixel), a main timeline of place/remove records with depths and clip (mask) depths, shapes made of textured quads stored as ready-made PSP GE display lists, nested movie clips with their own timelines, and keyframe tracks for an affine matrix and a colour transform. Each `.ehf` lives in an EHP archive next to its textures (`<name>.gim`) and, usually, a `.tmf` with one flag byte per texture.

Evidence for the Flash origin (high confidence): one archive is literally called `umd_replace/basic/swf.ehp`; the stage rectangle is stored as `xmin, xmax, ymin, ymax` in twips (`0, 9600, 0, 5440` = 480 × 272 px × 20), the SWF `RECT` order; the timeline records behave exactly like SWF `PlaceObject`/`RemoveObject`/`ShowFrame` with depths and clip depths; the stage background colour is stored like SWF `SetBackgroundColor`.

## Counts on the disc

`python3 -I tools/ehf.py check USRDIR SYSDIR/BOOT.BIN` parses and cross-checks **1,225 `.ehf`** with no failure: 1,184 in the 609 top-level archives (1,029 in the 531 loose `.ehp` files, which is the count in `ehp.md`, plus 155 in the 78 gzip-wrapped `field/*.gz`), 40 in the 20 nested archives of `minigame/`, and `loading.ehf` in the archive embedded in `BOOT.BIN` (file offset `0xc84d4`, vaddr `0x088cc480`). 689 of them have a `.tmf` (668 top-level, 20 nested, 1 in `BOOT.BIN`); every `.tmf` has an `.ehf` of the same base name.

Totals: 7,881 shapes, 365 clips, 15,390 primitives, 20,889 tracks, 29,133 timeline records, 8,234 texture-name slots.

These counts contain no duplicates. Until 2026-10-30 `ehf.archives_in` scanned an ELF for every `EHP\x03` magic and also recursed into nested archives, so an archive nested inside a `BOOT.BIN`-embedded archive would have been reported twice (the bug fixed in `ehp.walk_blob` during the GIM work). It now uses `ehp.embedded_archives`, which skips past each archive it finds. On this disc the six `BOOT.BIN` archives (`0xaefe4`, `0xc84d4`, `0xd3834`, `0xfb124`, `0xfea04`, `0x10d5d4`) contain no nested archive, so the counts above were already correct: the raw magic scan finds exactly these six offsets, and `ehp.walk_paths` over `USRDIR` and `BOOT.BIN` finds 1,225 leaves with the EHF magic (all named `.ehf`, no duplicate labels) and 689 `.tmf`.

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

## JSON export

`tools/ehf.py json` writes one neutral JSON document per `.ehf` (with its `.tmf`) for the port's asset pipeline. Output must go outside the repository or under an `extracted/` directory (it is derived game data and is never committed).

```
python3 -I tools/ehf.py json <archive> --member <name.ehf | inner.ehp/name.ehf> -o <out>.json
python3 -I tools/ehf.py json <USRDIR> <SYSDIR>/BOOT.BIN -o <outdir> [--no-frames] [--compact]
python3 -I tools/ehf.py json --check <USRDIR> <SYSDIR>/BOOT.BIN
```

A batch writes `<outdir>/<file label>/<prefix><name>.json`, with `@` in an embedded-archive label replaced by `_at_` (for example `BOOT.BIN_at_0xc84d4/loading.json`). The whole disc gives 1,225 files, 233 MB compact with frames, 27 MB with `--no-frames`. `--check` converts and serialises every layout in memory and prints the census of unknown fields; it writes nothing.

Design rules: every decoded value is stored as read (floats as the exact f32 value, quantised keys as integers, not pre-multiplied), so the port can apply its own interpolation; all offsets are byte offsets, absolute within the `.ehf` unless named `*_offset` inside a `blocks` entry (then relative to the object); every byte of the file is either decoded into a named field, recorded in `unknown` with its offset and raw value, or listed in `gaps`. Schema version 1:

| Key | Content |
| --- | --- |
| `format`, `version` | `"tf3-ehf-layout"`, `1`. |
| `source` | `file` (disc file, relative to the walked directory), `embedded_offset` (file offset of the archive in an ELF, else `null`), `archive` (`file` plus `@0x…`), `member` (path inside it, `inner.ehp/name.ehf` when nested), `tmf_member` (or `null`). `member`-style paths are what `tools/gim.py` and `ehp.find_leaf` take. |
| `size` | File size in bytes. |
| `sections` | `[{index, name, offset, size}]` for `stage`, `work_area`, `main_timeline`, `objects`, `texture_names`. |
| `stage` | `frames`, `background_rgba` (4 ints), `rect_twips` (`xmin, xmax, ymin, ymax`), `width_px`, `height_px`, `twips_per_pixel` (20), `field_08` (raw stage+0x08), `field_0c` (raw stage+0x0C). |
| `work_area` | `size`, `zero` (all bytes zero), `peak_instances` (from the size formula above). |
| `labels` | Always `[]`. The format has no frame labels: every byte is accounted for by the structures above, and the only strings are the texture names. Which clip or frame range a screen shows is chosen by scene code. |
| `textures` | One entry per 16-byte slot: `slot` (index, the `.tmf` byte index), `slot_offset` (as referenced by primitives), `name` (or `null` for an empty slot), `gim` (member name with its case in the archive), `gim_member` (path to give `tools/gim.py png <file> <gim_member>`; `null` if the GIM is missing), `tmf` (flag byte or `null`), and when `tmf` is present `additive` (bit 0, hypothesis medium) and `tmf_bit4`. |
| `tmf` | `null`, or `{bytes, matches_slots}`. |
| `timeline` | Main timeline records in file order: `index`, `frame` (running frame at which the record executes), `action` (`place`/`remove`), `object` (object `id` or `null`), `track`, `depth`, `clip_depth`, `wait`. |
| `objects` | `id` (byte offset in section 3; a record stores `id / 16`), `type` (`shape`/`clip`), `offset` (absolute), `record_index` (`id / 16`), `blocks` (`{name: {offset, size}}` relative to the object: `display_list`, `vertices`, `animation` for shapes; `timeline`, `animation` for clips), `tracks` (by track index; `null` for an unused table entry). Shapes add `anchor` `[x, y]` (twips), `vertex_scale`, `primitives`; clips add `frames` and `timeline` (same record form as the main timeline). |
| primitive | `type` (`triangle_strip`, `triangle_fan`, `line_strip`, …), `prim_code`, `rgb`, `alpha`, `vertex_type`, `texture_slot` (index or `null` = untextured), `texture` (name), `vertex_offset` (in the vertex block), `words` (the six raw display-list words as hex), `vertices` (`[{uv: [u, v] or null, xyz: [x, y, z]}]`, raw 16-bit values). |
| track | `index`, `offset` (absolute), `base_matrix` `[a, b, c, d]`, `base_translate` `[tx, ty]`, `steps` `{translate, scale, skew}`, `flags`, `channels` (names of bits 0–4 set), `flag_bit5`, `key_stride`, `pad_2a`, `keys`: `[{frame, translate: [qx, qy], scale: [qa, qd], skew: [qb, qc], multiply: [r, g, b, a], add: [4 × s8], add_raw: hex}]` with only the present channels. |
| `unknown` | `[{kind, offset, raw, where?}]`: every instance of a field whose meaning is not established, with its absolute offset (for `tmf.*`, `offset` is the slot index and `where` is `"tmf"`). Kinds below. |
| `gaps` | `[{offset, size, zero, raw?}]`: byte ranges no structure claims (alignment padding, the tails of name slots after the NUL, and any other unreferenced bytes); `raw` hex only when not all zero. |
| `frames` | Omitted with `--no-frames`. One entry per main-timeline frame: `{frame, draw: [...]}`, the flattened draw list in draw order. Each draw: `path` (depths from the main timeline down), `object`, `track`, `clip_depth`, `chain` (`[{depth, object, track, placed_at, local_frame}]` from the outermost clip to the shape), `matrix` `[a, b, c, d, tx, ty]` (twips, stage coordinates before subtracting `xmin/ymin`), `multiply` (4 floats, 1.0 = unchanged), `add` (4 values), rounded to 6 decimals. This is a convenience produced with the tool's hypotheses (linear interpolation, looping clips, parent × child composition, multiplied colour multiply, summed colour add, `add = 2 × s8`); the raw `timeline`/`tracks` are authoritative. |

Unknown-field census from `ehf.py json --check` over the whole disc (1,225 converted, 0 failures, 8,234 texture references resolved; each `gim_member` was also confirmed to resolve through `ehp.find_leaf` to the same bytes):

| Kind | Instances | Non-zero / set | Meaning |
| --- | --- | --- | --- |
| `stage.field_08` | 1,225 | 1,225 | Values 2, 1, 4; frame step? (hypothesis, low). |
| `stage.field_0c` | 1,225 | 0 | Always zero. |
| `shape.pad_28` | 7,881 | 0 | Always zero. |
| `clip.pad_18` | 365 | 0 | Always zero. |
| `track.pad_2a` | 20,889 | 0 | Always zero. |
| `track.flag_bit5` | 2 | 2 | Unknown flag, no key data (`ryusen01.ehf`). |
| `key.add` | 5,941 tracks | 5,941 | Colour-add encoding unknown (raw bytes kept per key). |
| `tmf.bit4` | 993 slots | 993 | Unknown. |
| `tmf.other_bits` | 0 | 0 | No other bits are used. |
| `gap` | 12 | 12 | See below. |

So 10 kinds are tracked and 5 still carry data whose meaning is unknown: `stage.field_08`, `track.flag_bit5`, the `add` channel, `.tmf` bit 4 and one stray padding pattern. The zero-only kinds (`field_0c`, the three pads) are recorded so a rebuilt file can be checked byte for byte. Gaps total 149,960 bytes, all zero except one case: `start_duel10.ehf`, present identically in the 12 `duel/basic_*.ehp` archives, has the 4 bytes `0b 80 7f 7f` in the 16-byte alignment padding after the shape at object `0x1e0` (its animation block ends at object offset `0x12c`, the next object starts at `0x130`). No structure points there; they are most likely stale buffer bytes left by the converter (hypothesis, low), and they are kept raw in `gaps`.

## Open questions

- What `ui_bind_ehf` writes into words 4–5 of each primitive and how the callback `0x088227d0` resolves texture names (presumably `container_ehp_find_member(ehp, name + ".gim")`).
- Stage field `0x08` (frame step?); whether the background colour is drawn.
- Exact interpolation between keys, and the meaning and encoding of the `add` channel (bit 4) and of flag bit 5.
- `.tmf` bit 4, confirmation of bit 0 = additive blending, and what happens without a `.tmf`.
- Whether placing the same object again at an occupied depth restarts its track (the tool restarts it).
- Line-strip primitives (16) are not drawn by the tool.
