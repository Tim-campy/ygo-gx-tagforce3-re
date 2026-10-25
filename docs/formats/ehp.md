# EHP archive

Status: `verified`. The layout below rebuilds all 629 EHP archives on the reference disc byte for byte (531 loose `.ehp` files, 78 gzip-wrapped ones in `field/`, 20 nested inside other archives). Tool: `tools/ehp.py` (`--verify`). Confidence: high.

EHP is the general-purpose container of the game: almost every directory under `PSP_GAME/USRDIR` stores its data in `.ehp` files, which hold flat lists of named members (textures, models, text, binary tables, further archives).

## Layout

All integers are little-endian `u32`.

| Offset | Size | Field |
| --- | --- | --- |
| `0x00` | 4 | Magic `45 48 50 03` (`"EHP\x03"`). |
| `0x04` | 4 | Total archive size in bytes, equal to the file size. |
| `0x08` | 4 | Tag `"NOT "` (`4E 4F 54 20`); identical in every archive. |
| `0x0C` | 4 | Member count `N` (1 to 658 on the disc). |
| `0x10` | `8 × N` | Entry table: per member, `name_offset` then `data_offset`, both relative to the start of the archive. |
| `0x10 + 8N` | 8 | Zero padding. |
| `0x18 + 8N` | variable | Name block: per member, in table order, the name (cp932, NUL-terminated) followed immediately by the member size as `u32`. The size field is **not aligned**. |
| next multiple of 16 | variable | Member data, in table order. Each member starts at a multiple of 16; the gaps are zero bytes. |
| end | | The archive is zero-padded to a multiple of 16; that padded length is the value at `0x04`. |

Observations over the whole disc:

- Names are relative file names with an extension and no directory separators; the longest is 42 bytes; all are ASCII in this dump, but cp932 is assumed because one file name on the disc itself is Japanese (`docs/formats/disc-layout.md`).
- Data offsets are strictly ascending and members never overlap, so a member's size can also be read as "up to the next 16-byte boundary before the next member", but the stored size is the authoritative one.
- 22 members have size 0; their data offset still points at an aligned position.
- A member whose first four bytes are the EHP magic is itself an archive (20 cases, all in `minigame/`).

## Compression

There is no compression inside the EHP format itself. Compressed data appears as ordinary gzip (RFC 1952, deflate, method 8):

| Where | Count | gzip flags | Content |
| --- | --- | --- | --- |
| `.gz` members inside `duel/*.ehp` | 8,789 | `0x00` (no file name) | Always a `TGMT` file. |
| Loose `field/*.gz` files | 78 | `0x08` (`FNAME` set; it equals the file name without `.gz`) | Always an EHP archive. |

Every stream decompresses with a valid CRC-32 and an `ISIZE` that matches the output length; the mean ratio is 0.51. Recompressing byte-identically was not attempted (it depends on the deflate encoder and level and is not needed for extraction).

## Member types seen

Counts are over all 609 top-level archives (loose `.ehp` plus decompressed `field/*.gz`).

| Extension | First bytes | Count | Status |
| --- | --- | --- | --- |
| `.gim` | `MIG.` | 10,117 | Sony GIM texture; standard format, not yet documented here. |
| `.gz` | `1F 8B` | 8,789 | gzip around `TGMT` (see above). |
| `.bin` | various | 2,225 | Unknown; several unrelated formats share the extension. |
| `.ehf` | `EHF` | 1,029 | Unknown; possibly a font or layout format (hypothesis, low). |
| `.tmf`, `.tms`, `.tmt`, `.tma` | `TGM?` for `.tms`/`.tmt`/`.tma` | 1,832 | Unknown; likely models, textures and animations (hypothesis, low). |
| `.txt` | various | 534 | Text, encoding not yet established. |
| `.ydq` | — | 50 | Unknown; only in `d_tutorial/`. |
| `.hmp`, `.efs`, `.dat`, `.png`, `.ehp` | — | small | `.png` is standard PNG; `.ehp` is a nested archive; others unknown. |

## Open questions

- Which code in `BOOT.BIN` reads EHP archives, and does it look members up by name or by index?
- Meaning of the `"NOT "` tag; it never varies on this disc.
- Whether the game accepts archives whose padding differs from the rule above (matters only for modding, not for the port).
