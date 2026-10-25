# Card image containers (`card/*.cip`)

Status: directory layout `verified` on all 12 files (every image slot is accounted for, in id order, with no gap or overlap); image formats of `cardh`, `cardm` and `card8` decoded and checked visually; `cardj` holds masked 512×512 JPEGs, unmasked with ygotfToolkit (see below). Tool: `tools/cip.py` (`list`, `list --check`, `png`). Tests: `tools/tests/test_cip.py` (synthetic data only).

All integers are little-endian. One sector is 0x800 bytes.

## Files

`BOOT.BIN` holds the paths `card/cardh_<l>.cip` and `card/cardm_<l>.cip` for `l` in `j e g f i s`, and `card/card8_j.cip`, `card/card8_a.cip`, `card/cardj_j.cip`, `card/cardj_a.cip` (strings at file offsets `0x9d28c`–`0x9d400`). The European disc ships the non-`j` files: `_e/_f/_g/_i/_s` are languages, `_a` is shared by all of them; the `_j` names are presumably the Japanese release's files (hypothesis, high confidence).

| File | Magic | Size | Sectors per image | Images | Card ids with images | Content (checked visually) |
| --- | --- | --- | --- | --- | --- | --- |
| `cardh_<l>.cip` ×5 | `CIP\x1a` | 14,819,328 | 2 | 3,609 | 3,560 | GIM, DXT1, 128×64: an atlas holding the card's artwork plus the card's name banner cut into pieces. Language-specific (the name). |
| `cardm_<l>.cip` ×5 | `CPM\x1a` | 7,428,096 | 1 | 3,609 | 3,560 | Headerless DXT1, 64×64: the whole card face (frame, name, stars, art, text box) squeezed into a square. Language-specific. |
| `card8_a.cip` | `CPL\x1a` | 66,557,952 | 9 | 3,609 | 3,560 | GIM, 8-bit indexed (256-colour RGBA8888 palette), swizzled, 128×128: the artwork alone. |
| `cardj_a.cip` | `CPJ\x1a` | 590,188,544 | 80 | 3,602 | 3,553 | 163,840 bytes per image: masked 512×512 baseline JPEG (see "CPJ"). |

The magic's fourth byte `0x1a` follows a three-letter tag; the tool maps each tag to its file family. The letters in the file names (`h`, `m`, `8`, `j`) are not explained by any evidence yet; `m` fits "mini" and `8` fits "8-bit".

Between languages, every `cardm` slot differs between English and German; `cardh` slots differ in 3,313 of 3,609 (English vs. German), and 170 `cardh` slots are identical in all five languages (presumably cards whose names read the same everywhere). Hypothesis (medium): `cardh` is what the duel screen shows for a card in close-up, `cardm` the small whole-card view, `card8` the artwork for detail screens. Which screen uses which file needs a trace.

## Header (0x30 bytes)

| Offset | Size | Field | Values on disc |
| --- | --- | --- | --- |
| `0x00` | 4 | Magic | `CIP\x1a`, `CPM\x1a`, `CPL\x1a`, `CPJ\x1a` |
| `0x04` | 4 | File size in bytes | equals the file size in all 12 files |
| `0x08` | 8 | Zero | |
| `0x10` | 4 | End of the directory (`dir_end`): header + id table + artwork lists + terminator | `0x8880` in all files |
| `0x14` | 4 | First card id | 3720 (`0x0e88`) |
| `0x18` | 4 | Last card id | 7993 (`0x1f39`) |
| `0x1c` | 4 | Offset of the id table | `0x30` |
| `0x20` | 4 | Sectors per image slot (`spi`) | 2, 1, 9, 80 (table above) |
| `0x24` | 12 | Zero | |

## Id table

At `0x30`, one 8-byte entry per card id from first to last (4,274 entries, ending at `0x85c0`): `u32 value`, `u32 reserved` (0 in every entry of every file). The table is indexed directly by `card_id - first_id`; the card database's record index is not involved.

| `value` | Meaning | Count (`cardh`/`cardm`/`card8`) | Count (`cardj`) |
| --- | --- | --- | --- |
| `0` | No image for this id | 714 | 721 |
| `< 0x80000000` | Start sector of the card's only image (byte offset = `value × 0x800`) | 3,522 | 3,515 |
| `0x80000000 \| offset` | Byte offset of an artwork list (card with several artworks) | 38 | 38 |

### Artwork lists

From `0x85c0` up to `dir_end - 8`: lists of 8-byte entries `u32 sector`, `u32 reserved = 0`. A list is read from the referenced offset until an entry whose sector has bit 31 set; that bit marks the last entry and is masked off. The 38 lists hold 87 sectors (49 more than one per card). An 8-byte `0xff` terminator ends the directory at `dir_end`; the bytes from `dir_end` to the first image (sector `0x12` = `0x9000`) are zero.

Artwork 0 is the first list entry. Cross-checks:

- The number of extra artworks per card equals `n` in `duelsys/cardinfo_<lang>.ehp/CARD_SamePict_<L>.bin` for all 38 cards (Blue-Eyes White Dragon, id 4007: 4 artworks, `n = 3`), which settles `n` as "number of alternative artworks" (high). `CARD_SamePict` has one more record (index 855) that has a single image in every `.cip`; open question.
- `deck/all_<lang>.ehp/sameCardTbl.dat` is `u32 count` (49) followed by `count` pairs `(u16 card id, u16 artwork number 1..n)`, one per extra artwork: the same 49 extra artworks.

### Slot placement

Images are stored in card-id order, an artwork list's images consecutively, starting at sector `0x12`, each in a slot of `spi` sectors, with the file ending exactly after the last slot. `tools/cip.py list --check` verifies this for each file (all 12 pass): the sequence of sectors obtained by walking the ids in order equals `0x12, 0x12 + spi, …` up to the file size. Image count = `(size / 0x800 − 0x12) / spi` = 3,609 (3,602 for `cardj`).

The tool therefore never needs the slot size from elsewhere: an image is the `spi × 0x800` bytes at its sector.

## Images

None of the slots is gzip/deflate-compressed: `cardh` and `card8` slots start with the GIM magic, `cardm` slots are raw texture data (see below), and `cardj` has no compressed-stream signature and does not inflate as raw deflate, zlib or gzip.

### GIM (`cardh`, `card8`)

Standard Sony GIM (`MIG.00.1PSP`, block tree root `0x02` → picture `0x03` → palette `0x05` / image `0x04`). Every slot of a file has the same shape:

| File | Image format | Pixel order | Size | Palette | GIM size | Slot size |
| --- | --- | --- | --- | --- | --- | --- |
| `cardh` | 8 (DXT1), 4 bpp | 0 (linear) | 128×64 | none | 4,224 (`0x1080`) | 4,096 |
| `card8` | 5 (index8) | 1 (swizzled) | 128×128 | format 3 (RGBA8888), 256 entries | 17,616 (`0x44d0`) | 18,432 |

The writer appears to fill each slot by repeating the GIM cyclically and cutting it at the slot size:

- `card8`: in all 3,609 slots the 816 bytes after the GIM are an exact copy of the slot's first 816 bytes.
- `cardh`: the GIM is 128 bytes longer than the slot, so its last 16 DXT1 blocks (pixels x 64–127, y 60–63) are cut off; the next slot's GIM header follows. The tool decodes the missing blocks as transparent. In the images checked this corner of the atlas is padding, but whether the game ever samples it is open.

Image block header (offsets relative to the start of the image or palette block's data, i.e. block + `0x10`): `u16 header_size (0x30)`, `u16 reference`, `u16 format`, `u16 pixel_order`, `u16 width`, `u16 height`, `u16 bpp`, `u16 pitch_align`, `u16 height_align`, … , `u32 pixels_start` at `0x1c` and `u32 pixels_end` at `0x20` (both relative to the header). `card8` palette alpha bytes are 0; the tool draws the palette opaque (the alpha's meaning for the game is open).

### Pixel formats as decoded

- **Swizzle** (pixel order 1): the texture is stored as tiles of 16 bytes × 8 rows, tiles in row-major order; within a tile, rows of 16 bytes follow each other.
- **DXT1** (PSP layout): 8-byte blocks of 4×4 pixels in raster order; each block is `u32 indices` (2 bits per pixel, pixel 0 in the lowest bits, row-major) followed by two `u16` RGB565 endpoints with **red in the high bits** (the GE's 5650 texel format has red in the low bits; decoding the endpoints that way turns the blue dragon gold). If `c0 > c1`, four colours (`c0`, `c1`, ⅔/⅓ blends); otherwise three plus transparent.

### `cardm`: headerless DXT1

A slot is exactly 2,048 bytes = one 64×64 DXT1 texture in the layout above, with no header. Width and height are not stored in the file; 64×64 is established by decoding (at 64×32 only the top half of a card appears, continuing seamlessly into the second half at 64×64) and by the arithmetic `64 × 64 / 2 = 2,048`. Confidence high for the layout; the dimensions the game passes to the GE are not traced.

### CPJ (`cardj_a.cip`): masked JPEG, the high-resolution card art

Each 163,840-byte slot holds one **baseline JPEG of 512×512 pixels**, the largest card art in the game, stored masked. The method below was read from the instructions of `BOOT.BIN` (European disc; module-relative addresses, absolute = `0x08804000 +` address) and confirms ygotfToolkit's description (`docs/PRIOR_ART.md`); `tools/cip.py jpeg` implements it.

**Where (high).** The test for the magic is a two-instruction leaf, `0x39b1c` (`lw v1,0xac(a0)`; `lui v0,0x1a4a`; `ori v0,v0,0x5043`; return `v1 == 0x1a4a5043`): the reader context keeps the `.cip` header at `+0xac`. Its sibling `0x39b04` tests `CPM` (`0x1a4d5043`). `0x39b1c` is called from `0x390f4` (an image lookup that skips CPJ) and from `0x39694`, inside `0x39658`, the read-completion callback: `0x394a0` starts an asynchronous read of the next pending slot through `0x197b8` (`a2` = buffer, `a3` = byte offset `sector << 11`, `t0` = length `spi << 11`, `t1` = callback `0x39658`, built with `lui t1,0x4` + `addiu t1,t1,-27048`); `0x39658(ctx, bytes_read)` unmasks the buffer when the context is a CPJ file, marks the slot loaded and calls `0x394a0` again for the next one.

**Algorithm (high; every step is an instruction in `0x39658`).** With `buf` = the slot buffer (`ctx+0x90`) and `n = ctx[0xcc] << 11` = 163,840 bytes:

1. `seed = buf[0x9e] << 8 | buf[0x9f]` (`lbu` at `0x396b4`/`0x396b8`, `sll 8`, `addu`), read **before** step 2. In the plain JPEG these two bytes are the `FF C0` (SOF0) marker, which the slot does not need to store.
2. `memcpy(buf, 0x9d3d8, 160)` (`jal 0x9e84` with `lui a1,0xa` + `addiu a1,a1,-11304`, `a2 = 160`), then `buf[i] ^= 0x5c` for `i < 160` (`xori 0x5c`, loop unrolled ×8). The 160 bytes at `.data` address `0x9d3d8` are the JPEG head (SOI, JFIF APP0, DQT tables, up to the SOF0 marker) XOR `0x5c`; they start `a3 84 a3 bc 5c 4c …` = `FF D8 FF E0 00 10 …`. The slot's own first 160 bytes are discarded except for the seed.
3. If `n > 160`: for `i = 160 … n−1`: `s = ((s × 0xc6a1 + 0xd0f) >> 1) & 0xffff`; `buf[i] ^= (s >> 2) & 0xff`, starting from `s = seed`. In the code: `ori v0,zero,0xc6a1`; `mult`; `mflo`; `addiu 3343`; `ext t,x,1,16` (bits 1–16); `ext y,t,2,8` (bits 2–9); `xor`; `sb` (loop unrolled ×8 at `0x397d0`, tail loop at `0x398f0`). The product fits in 32 bits, so the signed `mult` changes nothing.

The generator has a short cycle (for card 3720, seed `0x6431`: 174 steps into a cycle of 183), which explains the repeating 16-byte blocks measured earlier.

**Slot layout (measured).** After unmasking, the JPEG ends at its EOI marker and the rest of the slot is not zero: the stored (masked) slot is the masked JPEG of length `L` repeated cyclically, `slot[k] = slot[k mod L]`, for every byte from `L` to the end (checked on cards 3720, 3721, 4007, 5000). `tools/cip.py jpeg` therefore cuts the output at EOI (found by walking the marker segments, then the entropy data, where `FF 00` and `FF D0`–`FF D7` do not end it); `--full` keeps the whole unmasked slot.

**Verification.** `tools/cip.py jpeg` reads the stored head from the maintainer's `BOOT.BIN` at run time (at `0x9d3d8`, or by searching for the masked JFIF start, then checked); no game bytes are in the repository. Its output is byte-identical to ygotfToolkit's `cardpics --archive cardj` (run as an external tool) for all 3,602 slots (3,553 cards, including the 87 images of the 38 cards with alternative artworks), and for the 400 reference files made earlier.

```
python3 -I tools/cip.py jpeg card/cardj_a.cip extracted/cardj --boot PSP_GAME/SYSDIR/BOOT.BIN [--ids 4007 …] [--limit N] [--full]
```

Files are `<id>.jpg` (artwork 0) and `<id>_<n>.jpg` (alternative artwork `n`), ids zero-padded to five digits. Output stays in `extracted/`.

`cardj` has images for exactly the 3,553 card ids of the card database (the same set as `CARD_IntID`); the other files have 7 more (see below).

## How images map to cards

- The `.cip` directory is indexed directly by card id (3720–7993); no other table is needed. Artwork `k` of a card is entry `k` of its list.
- `cardh`, `cardm`, `card8` contain the 3,553 database ids plus 7 ids with no database record: 3725, 3726, 3728, 3729, 3733, 3735, 3736. Their `cardm` images are complete card faces; why the database lacks them (removed or unfinished cards?) is open.
- `deck/all_<lang>.ehp/fileTbl.dat` is **not** the `.cip` map. It is `u16 count` (3,502) followed by `count` `u16` card ids in ascending order, the first being 0 (an empty slot, like record 0 of the card database); 3,501 ids are real cards. It omits 52 database ids, all of them tokens (3751 and 3900–3950), and the 7 ids above, so it cannot address the `.cip` slots, whose count is 3,609. The same archive holds `cis_all.gim` (index8, swizzled, 512×512, 9 frames with 9 palettes of 256 colours: `9 × 512 × 512` pixel bytes and `9 × 1024` palette bytes), a sheet of small card thumbnails in a grid of about 22 columns × 18 rows per page (`9 × 396 ≥ 3,502`). Hypothesis (medium): `fileTbl.dat` gives the card id of each thumbnail cell of `cis_all.gim`, for the deck editor's card list; the exact cell size and order are not established.

## Tool

```
python3 -I tools/cip.py list <file.cip>            # id,images,sectors per card
python3 -I tools/cip.py list <file.cip> --check     # structural check (all 12 files pass)
python3 -I tools/cip.py png <file.cip> <card id> [--art N] [--size WxH] -o extracted/....png
python3 -I tools/cip.py jpeg cardj_a.cip <outdir> --boot BOOT.BIN [--ids …] [--limit N] [--full]   # CPJ
```

`png` decodes GIM slots (DXT1, index4/8 with palette, 5650/5551/4444/8888, swizzled or not) and headerless `cardm` slots (`--size`, default 64×64). Output must stay outside the repository (for example under `extracted/`).

## Open questions

- Which screens use `cardh`, `cardm` and `card8`, and how the `cardh` atlas pieces are assembled on screen (needs the loader and a PPSSPP trace).
- The exact placement of each piece in the `cardh` atlas, and whether the 128 truncated bytes at its end are ever sampled.
- `CPJ`: what the slot's first 158 bytes (before the seed) hold; they are neither the JPEG head nor generator output from any seed and the game overwrites them. Whether other code paths (for example `0x390f4`'s caller) ever read a CPJ slot without unmasking it.
- What the 7 ids without a database record are, and why `CARD_SamePict` lists record 855, which has only one image.
- Meaning of the per-entry `reserved` word (always 0) and of the palette alpha bytes in `card8` (always 0).
- `cis_all.gim` cell geometry and whether `fileTbl.dat` index `i` is cell `i`.
- The functions in `BOOT.BIN` that open and read these files (string xrefs from `0x9d28c`–`0x9d400`; not traced because Ghidra was not available in this session).
