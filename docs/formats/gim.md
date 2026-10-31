# GIM texture (as used on this disc)

Status: `reimplemented` (`gim` in `re/formats.csv`). GIM is Sony's standard PSP texture format; this page only records which parts of it the game uses. Converter: `tools/gim.py` (every GIM on the disc to PNG, all frames and palette levels); the block walker, colour formats, DXT1 and unswizzle live in `tools/cip.py` and are shared with `tools/ehf.py render` and `tools/tgm.py obj`. Cross-checked by decoding: all 14,098 GIM files decode without error (`gim.py check`), card art (`docs/formats/cip.md`), every texture drawn in the `.ehf` renders listed in `docs/formats/ehf.md`, and visual inspection of samples of each format (swizzled index8 atlas, linear index4 sprite sheets with palette levels, RGBA8888, DXT1).

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

Image and palette blocks share a 0x30-byte surface header (offsets relative to the header, which starts at block offset + `0x10`):

| Offset | Type | Field | On this disc |
| --- | --- | --- | --- |
| `+0x00` | u16 | Header size | `0x30` |
| `+0x04` | u16 | Format (table below) | |
| `+0x06` | u16 | Pixel order: 0 linear, 1 PSP swizzle | |
| `+0x08`, `+0x0a` | u16 | Width, height (palette: entry count × 1) | |
| `+0x0c` | u16 | Bits per pixel | |
| `+0x0e`, `+0x10` | u16 | Pitch alignment (bytes), height alignment (rows) | 16/8 swizzled, 16/1 linear, 4/4 DXT1, 16/1 palettes |
| `+0x18` | u32 | `index_start`: offset of the plane-offset table | `0x30`; 202 images use `0x40` (196), `0x50` (1) or `0x60` (5); the bytes between `0x30` and the table are not interpreted |
| `+0x1c` | u32 | `pixels_start` (= the first plane offset) | |
| `+0x20` | u32 | `pixels_end` | |
| `+0x28` | u16 | Level type | 1 for images, 2 for palettes |
| `+0x2a` | u16 | Level count | images 1; palettes 1, 2, 8, 10, 11 or 16 |
| `+0x2c` | u16 | Frame type | 3 |
| `+0x2e` | u16 | Frame count | 1 or 9 |

At `index_start` follow `level_count × frame_count` u32 **plane offsets** (relative to the header); plane `k` is frame `k / level_count`, level `k mod level_count`, and ends at the next plane's offset or at `pixels_end`. No file has both several levels and several frames, so the frame-major order is an assumption that the disc cannot contradict.

- **Palette levels are alternative palettes** for the same image (high, by inspection): `database/charalist.ehp/common_head.gim` (16 levels of 15 entries) gives the same set of heads in 16 hair colours; `field/always_*.ehp/sd_head_01.gim` (10 levels) and `sd_body_*.gim` (2 levels) likewise. Which level a screen picks is code (open question). A palette with 15 entries is stored in 16-entry (64-byte) planes.
- **Frames**: 5 images have 9 frames with a 9-frame palette (one palette per frame), for example `deck/all_<l>.ehp/cis_all.gim` (512×512 index8: nine pages of card thumbnails). Image frame `f` uses palette frame `f`.

## Formats seen

Histogram of `python3 -I tools/gim.py check <PSP_GAME>` (all 14,098 files; 16,050 planes, counting each frame and each palette level):

| Image format | Pixel order | Palette | Count |
| --- | --- | --- | --- |
| index8 (`5`) | swizzled | RGBA8888 × 256 | 8,465 |
| index4 (`4`) | swizzled | RGBA8888 × 16 | 4,843 |
| index4 | linear | RGBA8888 × 16 | 370 |
| index8 | linear | RGBA8888 × 256 | 171 |
| RGBA8888 (`3`) | swizzled | none | 66 |
| index8 | swizzled | RGBA8888 × 160 | 65 |
| index8 | swizzled | RGBA8888 × 15 | 60 |
| index4 | linear | RGBA8888 × 15 | 35 |
| DXT1 (`8`) | linear (block order) | none | 23 |

| Planes | Count |
| --- | --- |
| 1 frame, 1 palette level | 13,803 (+ 89 without palette) |
| 1 frame, palette levels 2 / 8 / 10 / 11 / 16 | 40 / 1 / 35 / 65 / 60 |
| 9 frames, 9 palette frames | 5 |

- Every palette is RGBA8888 (`3`). No pixel index points past its palette (checked on every plane). The 16-bit direct formats (`0`–`2`), index16/32 and DXT3/5 do not occur; `gim.py` decodes `0`–`7` and DXT1 and rejects the rest.
- Swizzle: PSP standard, 16-byte × 8-row tiles in row-major tile order (`unswizzle`); swizzled images have pitch alignment 16 and height alignment 8, so every swizzled plane is a whole number of tiles.
- Dimensions are powers of two except one image (97×181); largest side 8–512, mostly 32–256.
- Colours are RGBA8888 with red in the low byte; index4 packs the left pixel in the low nibble. DXT1 is 8-byte blocks in raster order, `u32 indices` then two RGB565 colours with red in the high bits.

## Commands

```
python3 -I tools/gim.py check <PSP_GAME>                                     # decode every plane, histogram, exit 1 on failure
python3 -I tools/gim.py info <USRDIR>/deck/all_e.ehp                         # one line per GIM (archive, directory or .gim)
python3 -I tools/gim.py png <USRDIR>/deck/all_e.ehp cis_all.gim --frame 3 -o extracted/gim/cis_all_f3.png
python3 -I tools/gim.py png <USRDIR>/field/sdchr/<name>.gim -o extracted/gim/<name>.png
python3 -I tools/gim.py batch <USRDIR> <SYSDIR>/BOOT.BIN -o extracted/gim [--first]
```

`png` takes a loose `.gim` or an archive (`.ehp`, `.ehp.gz`, or an ELF whose embedded archives are searched) plus a member name (`inner.ehp/name.gim` or `inner.ehp:name.gim` for nested archives); `--frame`, `--clut` (palette level) and `--level` (image level) pick the plane. `batch` walks files and directories and writes every GIM to `<output>/<path of the file or archive>/<member stem>[_f<frame>][_c<palette level>].png`; `--first` writes only frame 0 / palette level 0. PNG is RGBA8 with the alpha of the texture, written with `zlib` + `struct`. Output is game data: the tool refuses to write inside the repository unless the path is under an `extracted/` directory. A full `check` takes about one minute; indexed planes are decoded with `bytes.translate`, not per pixel.

## Open questions

- Which code selects a palette level (hair/costume colour of the field sprites and the character list) and a frame of the 9-frame images.
- What `field_3d_bind_gim` (`0x08823dc0`) changes in place when binding.
