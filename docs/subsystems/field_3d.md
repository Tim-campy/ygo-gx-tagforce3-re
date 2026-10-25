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
