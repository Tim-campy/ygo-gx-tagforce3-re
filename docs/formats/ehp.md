# EHP archive

Status: `verified`. The layout below rebuilds all 629 EHP archives on the reference disc byte for byte (531 loose `.ehp` files, 78 gzip-wrapped ones in `field/`, 20 nested inside other archives). Tool: `tools/ehp.py` (`--verify`). The reader in `BOOT.BIN` agrees with every field (see "How the game reads it"). Confidence: high.

EHP is the general-purpose container of the game: almost every directory under `PSP_GAME/USRDIR` stores its data in `.ehp` files, which hold flat lists of named members (textures, models, layouts, binary tables, further archives).

## Layout

All integers are little-endian `u32` unless noted.

| Offset | Size | Field |
| --- | --- | --- |
| `0x00` | 3 | Magic `45 48 50` (`"EHP"`). The game checks only these three bytes. |
| `0x03` | 1 | Format version; `3` on the whole disc. Versions below 3 have no stored member sizes (see below). |
| `0x04` | 4 | Total archive size in bytes, equal to the file size. |
| `0x08` | 4 | Bind state: `"NOT "` on disc ("not bound"); the game overwrites it with `"BIND"` once it has processed the archive in memory, so an archive is never bound twice. |
| `0x0C` | 4 | Member count `N` (1 to 658 on the disc). |
| `0x10` | `8 × N` | Entry table: per member, `name_offset` then `data_offset`, both relative to the start of the archive. |
| `0x10 + 8N` | 8 | Zero padding (the game stops its bind walk at a zero `name_offset`, so this acts as a terminator). |
| `0x18 + 8N` | variable | Name block: per member, in table order, the name (cp932, NUL-terminated) followed immediately by the member size as `u32`. The size field is **not aligned**; the game reads it byte by byte. |
| next multiple of 16 | variable | Member data, in table order. Each member starts at a multiple of 16; the gaps are zero bytes. |
| end | | The archive is zero-padded to a multiple of 16; that padded length is the value at `0x04`. |

Rules the game depends on:

- **Members are sorted by name, case-insensitively** (ASCII `A`–`Z` folded to lower case, then byte order), because lookups are a binary search with `strcasecmp`. All 629 archives follow this order; only 523 would be sorted under a case-sensitive comparison. `tools/ehp.py build()` keeps the order it is given, so new archives must be sorted this way.
- For version < 3 the game derives a member's size from offsets instead: the next entry's data offset, or the archive size for the last member. No such archive exists on this disc.

Observations over the whole disc:

- Names are relative file names with an extension and no directory separators; the longest is 42 bytes; all are ASCII in this dump, but cp932 is assumed because one file name on the disc itself is Japanese (`docs/formats/disc-layout.md`).
- Data offsets are strictly ascending and members never overlap.
- 22 members have size 0; their data offset still points at an aligned position.
- A member whose first four bytes are the EHP magic is itself an archive (20 cases, all in `minigame/`).

## How the game reads it

Functions in `BOOT.BIN` (base `0x08804000`), all in the `container` group; evidence in `docs/subsystems/container.md`.

- `container_ehp_find_member(ehp, name, out_size)` (`0x08822280`) checks the magic (`container_ehp_is_valid`), binary-searches the entry table (`container_ehp_find_entry`, 1-based over `N`), returns `ehp + data_offset`, and optionally the size (`container_ehp_get_member_size`).
- `container_ehp_bind(ehp, flag)` (`0x088220e8`): if the tag is not yet `"BIND"`, writes `"BIND"` and calls `container_ehp_bind_members`, which walks the entry table and prepares each member in place by the last four characters of its name:

| Member | Count on disc | What binding does |
| --- | --- | --- |
| `*ptrs.txt` | 425 | Resource pointer list: `u32` offsets relative to the archive, terminated by `0xFFFFFFFF`; every non-zero value gets the archive's address added. All 425 lists end with the terminator and point inside their archive. |
| `.tmt` | 453 | `field_3d_bind_tmt` (`0x08830870`); also the target of inflated `.tmt.gz` members. |
| `.tma` | 126 | `field_3d_bind_tma` (`0x08832378`). |
| `.tms` | 585 | `field_3d_bind_tms` (`0x0882e524`), with callback `0x08822b44`. |
| `.ehf` | 1,029 | Looks up the member with the same base name and extension `.tmf`, then `ui_bind_ehf` (`0x0881e56c`) and `0x0881e6a4(480.0, 272.0, 240.0, 136.0, …)`: screen size and centre, so `.ehf` is a 2D layout tied to a `.tmf` (`docs/formats/ehf.md`). Count over the 531 loose archives. |
| `.gim` | 10,117 | `field_3d_bind_gim` (`0x08823dc0`). |
| other | — | A table of handlers registered at runtime by extension (count `0x0892191c`, handlers from `0x08921940`). |

Six archives are embedded in `BOOT.BIN`'s `.data` and bound at start-up by `0x08835c68` (`0x088b2f90`, `0x088cc480`, `0x088d77e0`, `0x088ff0d0`, `0x089029b0`, `0x08911580`); for example `loading.ehf` and `RCP_%03d.ydc` are looked up in them.

## Compression

There is no compression inside the EHP format itself. Compressed data appears as ordinary gzip (RFC 1952, deflate, method 8):

| Where | Count | gzip flags | Content |
| --- | --- | --- | --- |
| `.gz` members inside `duel/*.ehp` | 8,789 | `0x00` (no file name) | Always a `TGMT` file (8,701 `*.tmt.gz`, 88 `*.vtmt.gz`; see `tgm.md`). |
| Loose `field/*.gz` files | 78 | `0x08` (`FNAME` set; it equals the file name without `.gz`) | Always an EHP archive. |

Every stream decompresses with a valid CRC-32 and an `ISIZE` that matches the output length; the mean ratio is 0.51. The game inflates them with a statically linked copy of Sony's `libdeflt` (`docs/subsystems/sdk.md`). Recompressing byte-identically was not attempted (it depends on the deflate encoder and level and is not needed for extraction).

## Member types seen

Counts are over all 609 top-level archives (loose `.ehp` plus decompressed `field/*.gz`).

| Extension | First bytes | Count | Status |
| --- | --- | --- | --- |
| `.gim` | `MIG.` | 12,374 | Sony GIM texture; see `gim.md`. (10,117 of them are in the 531 loose `.ehp` files; an earlier version of this table counted only those.) |
| `.gz` | `1F 8B` | 8,789 | gzip around `TGMT` (see above). |
| `.bin` | various | 2,225 | Unknown; several unrelated formats share the extension. |
| `.ehf` | `EHF` | 1,184 | 2D layout (converted Flash timeline) bound together with a `.tmf` of the same name; see `ehf.md`. (1,029 in the loose `.ehp` files, 155 in `field/*.gz`.) |
| `.tmf`, `.tms`, `.tmt`, `.tma` | `TGM?` for `.tms`/`.tmt`/`.tma` | 1,832 | `.tms` mesh, `.tmt` node animation, `.tma` texture animation (`tgm.md`); `.tmf` per-texture flags of an `.ehf` layout (`ehf.md`). |
| `.txt` | various | 534 | 425 are `*ptrs.txt` resource pointer lists; the rest are text, encoding not yet established. |
| `.ydq` | — | 50 | Unknown; only in `d_tutorial/`. |
| `.hmp`, `.efs`, `.dat`, `.png`, `.ehp` | — | small | `.png` is standard PNG; `.ehp` is a nested archive; others unknown. |

## Open questions

- `*ptrs.txt` lists: in archives with TGM members every non-zero entry is the offset of a whole member, so these are lists of resources (`<anim>-ptrs.txt` groups mesh, animation and texture; `all-ptrs.txt` has one slot per animation), not fixups inside a member; no entry falls inside an `.ehf` or `.tmf` member either (`tgm.md`, `ehf.md`). Confirm for the remaining archives, and decide whether a port needs these lists once data is converted offline.
- What `0x0881e6a4` does with the screen-size arguments.
- Which extensions are registered in the runtime handler table, and by whom.
