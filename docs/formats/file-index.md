# In-memory file index (runtime structure)

Status: `documented`. Built at boot by `container_build_file_index` (`0x0881e054`) from the disc's own ISO 9660 directories; there is **no custom file table on the disc**. Confidence: high (decompiled builder, lookup and both call sites; not yet observed at runtime).

## Purpose

The game resolves paths under `disc0:` to raw sector addresses itself and then opens `disc0:/sce_lbn0x<lbn>_size0x<size>`, which reads by sector instead of through the UMD filesystem's directory lookup. For the port this means paths on the disc are the only file identity that matters: no hash table or archive index needs to be reproduced.

## Globals

| Address | Type | Meaning |
| --- | --- | --- |
| `0x089218c8` | `entry *` | Start of the entry array. |
| `0x089218cc` | `entry *` | One past the last entry (grows while building). |
| `0x089218d0` | `char *` | Name pool cursor; names are written from the end of the buffer downwards. |
| `0x089218d4` | `SceUID` | Memory block returned by `ThreadManForUser` stub `0x08872544` (`FUN_08872544("…", 2, 0, size, 1, 0)`, likely a variable-pool create; hypothesis, low). |
| `0x089218d8` | `void *` | Base of that block; entries start here. |
| `0x089218dc` | `int` | 1 once the index is ready; lookups are skipped while 0. |
| `0x089218e0` | `int` | 1 while the index is being built. |

## Entry (16 bytes)

| Offset | Size | Field | Source in the ISO 9660 directory record |
| --- | --- | --- | --- |
| `0x0` | 4 | Pointer to the NUL-terminated path | Parent path + record name (`+0x21`, length `+0x20`), copied as stored. This disc stores names without the `;1` version suffix (checked on the root directory: `PSP_GAME`, `UMD_DATA.BIN`). |
| `0x4` | 4 | Extent LBA (sector number) | `+0x02` |
| `0x8` | 4 | Size in bytes | `+0x0A` |
| `0xC` | 4 | Not written by the builder | — |

Entries are sorted with `system_qsort` and searched with `system_bsearch`, both using the comparator at `0x0881dfd4`.

## How it is built

1. Open the raw device `umd1:` (`0x0889ede8`).
2. Read one sector and take `u32` at `+0x84`, the path-table size field of the primary volume descriptor.
3. Read the path table (rounded up to whole 2048-byte sectors) and take the extent LBA of its first record (`+0x02`), the root directory.
4. `container_index_directory` (`0x0881dd88`) walks the directory recursively: files become entries; directories other than `\0`/`\1` (`.`/`..`) recurse with `<parent><name>/` as prefix.
5. Sort, set `0x089218dc = 1`.

## Open questions

- Comparator `0x0881dfd4`: it calls `system_strcasecmp`, so lookups are probably case-insensitive; confirm by reading it. The lookup key is the path after `disc0:` (`buf + 6`).
- What the device positioning helper `0x0881e448` does before each read (only the descriptor argument survives decompilation).
- Confirm at runtime in PPSSPP: index size, first entries, and that `0x089218dc` becomes 1 after boot.
