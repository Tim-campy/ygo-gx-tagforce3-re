# Rendering data (work package 8)

Entry points found while working on containers, and the 3D model formats.

## Key functions

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x0882f2f0` | `field_3d_set_tgmt_data(ctx, data)` | M | If `data` starts with `TGMT` (`0x544d4754`) it is used in place; otherwise, when `sceGzipIsValid(data)`, it is inflated with `sceGzipDecompress` into one of two alternating buffers (`ctx+0x44`/`ctx+0x48`, size `ctx+0x40`, allocated as `0x1b800` bytes on first use by `0x0882ffcc`) and passed to `0x08830870`. Callers `0x0882f3f4`, `0x0882f97c`, `0x0882fa2c`. |

Consistency with the disc: every `.gz` member inside an EHP holds a `TGMT` file, and the largest decompressed one is `0x1af58` bytes (`duel/cutin_fujiwara01.ehp:lose206.tmt.gz`), below the `0x1b800` buffer; none of the 8,789 exceeds it.

## Model formats

Documented in `docs/formats/tgm.md` (tool `tools/tgm.py`, which validates all 9,953 TGM members on the disc):

- `TGMS` (`.tms`): mesh. Materials → batches (bone palette of up to 8, GE vertex type) → `sceGuDrawArray` primitives (triangles / triangle strips) over s16-quantised vertices; skeleton with offset matrices.
- `TGMT` (`.tmt`, `.tmt.gz`, `.vtmt.gz`): node animation (three Bézier scalar tracks for translation and for scale, quaternion keys for rotation); `-etc` files add camera/scene parameter tracks.
- `TGMA` (`.tma`): per-texture UV offset / UV scale / scalar animation, tied to TGMS materials.
- Pointer lists next to them (`<anim>-ptrs.txt`, `all-ptrs.txt`) bundle members (mesh + animations) and index animations by slot.

Posed skinned vertex = Σ weight × node_world × bone_offset_matrix × position; this places 162 of 196 skinned meshes inside their header bounding box at frame 0, the rest at a later frame.

## Open questions

- What `0x08830870` does with a `TGMT` at bind time (pointer conversion only?), and how the animation player interpolates rotations.
- Camera model behind the 42 leading tracks of `-etc.tmt`; purpose of `.vtmt`.
- Role of `.tmf` (with `.ehf`, covered separately).
- The remaining open fields listed in `docs/formats/tgm.md`.
