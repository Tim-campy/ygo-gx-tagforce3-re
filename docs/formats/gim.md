# GIM texture (as used on this disc)

Status: `named`. GIM is Sony's standard PSP texture format; this page only records which parts of it the game uses. Decoder: `tools/cip.py` (`gim_blocks`, `read_gim`, `decode_surface`, `unswizzle`), also used by `tools/ehf.py render`. Cross-checked by decoding: card art (`docs/formats/cip.md`) and every texture drawn in the `.ehf` renders listed in `docs/formats/ehf.md`.

## Where they are

14,098 GIM files in total:

| Location | Count |
| --- | --- |
| Members of the 531 loose `.ehp` archives (the count in `ehp.md`) | 10,117 |
| Members of the 78 gzip-wrapped `field/*.gz` archives | 2,257 |
| Members of the 20 nested archives (`minigame/`) | 300 |
| Members of the 6 archives embedded in `BOOT.BIN` | 34 |
| Loose `.gim` files on the disc | 1,390 |

Plus the GIM slots inside `card/cardh_*.cip` and `card/card8_a.cip` (see `cip.md`), not counted here.

## Layout

Little-endian. `0x00`: magic `MIG.00.1PSP\0` (12 bytes), then 4 zero bytes. Blocks follow from `0x10`, each with a 16-byte header `u16 id, u16 0, u32 block size (including children), u32 next (equal to the size for leaf blocks), u32 data offset (always 0x10)`.

Block trees seen (all files):

| Tree | Count |
| --- | --- |
| root `0x02` → picture `0x03` → palette `0x05`, image `0x04`; then file-info `0xFF` | 6,271 |
| root → picture → palette, image | 6,484 |
| root → picture → image, palette | 1,254 |
| root → picture → image (no palette) | 89 |

One picture and one image block per file. The `0xFF` block holds 5–8 NUL-separated strings (authoring metadata, not needed).

Image and palette blocks share a 0x30-byte info header: `u16 header size (0x30), u16 0, u16 format, u16 pixel order, u16 width, u16 height, u16 bits per pixel, u16 pitch alignment, u16 height alignment, …, u32 data start (0x1C), u32 data end (0x20), …, u16 level type, u16 level count (0x28), u16 frame type, u16 frame count (0x2C)`.

## Formats seen

| Image format | Count | Pixel order |
| --- | --- | --- |
| index8 (`5`) | 8,761 | 8,590 swizzled, 171 linear |
| index4 (`4`) | 5,248 | 4,843 swizzled, 405 linear |
| RGBA8888 (`3`) | 66 | swizzled |
| DXT1 (`8`) | 23 | linear (block order) |

- Every palette is RGBA8888 (`3`): 256 entries for index8, 16 for index4; among archive members, 86 palettes have 15 entries and 65 have 160.
- Swizzle: PSP standard, 16-byte × 8-row tiles in row-major tile order (`unswizzle`); swizzled images have pitch alignment 16 and height alignment 8 (checked on the 12,345 swizzled archive members); the 340 linear index images inside archives use 16/1, DXT1 uses 4/4.
- Archive members: dimensions are powers of two except one image (largest side 181); largest side 8–512, mostly 32–256.
- 5 images have 9 frames (and 9 palettes), for example `deck/all_<l>.ehp/cis_all.gim`; 201 palettes have more than one level (2, 8, 10, 11 or 16): several palettes for one image (hypothesis: palette swaps).
- Colours are RGBA8888 with red in the low byte; index4 packs the left pixel in the low nibble.

## Open questions

- How the game uses multi-level palettes and multi-frame images (palette animation?).
- What `field_3d_bind_gim` (`0x08823dc0`) changes in place when binding.
