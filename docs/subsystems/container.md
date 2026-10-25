# Containers (work package 1)

How the game's data is packaged on the disc, from the outside in:

1. **UMD image** (ISO 9660): `docs/formats/disc-layout.md`, extractor `tools/iso9660.py`.
2. **In-memory file index**: at boot the game indexes the disc's own directories and later opens files by sector (`docs/formats/file-index.md`). There is no custom file table on the disc.
3. **EHP archives**: the general container used by almost every `USRDIR` directory. `docs/formats/ehp.md`, tool `tools/ehp.py` (list, extract, rebuild, `--verify`).
4. **gzip**: standard gzip, used in two places only: `.gz` members inside `duel/` archives (always `TGMT`) and loose `field/*.gz` files (always EHP). `tools/ehp.py -z` decompresses while extracting.
5. **Leaf formats** inside archives or loose on the disc: GIM textures, PSMF movies, PNG, and the formats still unknown (`.cip`, the `snd/` bank, `.ehf`, the `TGM*` family, `.ydq`, `.bin`, `.txt`).

No custom compression or encryption has been found in the data files so far; the only encrypted file is `EBOOT.BIN`, and it is not needed because `BOOT.BIN` is a plain ELF.

## Extracting everything

```
python3 -I tools/iso9660.py game/<image>.iso -x extracted/umd
python3 -I tools/ehp.py extracted/umd/PSP_GAME/USRDIR/duel/*.ehp -x extracted/ehp/duel -r -z
```

## Ghidra setup

`BOOT.BIN` is imported into `ghidra/TF3.gpr` with the ghidra-allegrex `PSP Executable (ELF)` loader at image base `0x08804000`. That base is confirmed at runtime: of Ghidra's 2,251 auto-analysed functions, 2,200 start exactly where PPSSPP's symbol export has a function, 2,158 with the same size.

Symbols are rebuilt in this order (scripts copied to a path without a `.` element first, see `README.md`):

1. Export symbols from PPSSPP with the game running (Debug menu) to `ghidra/symbols.sym` (not committed).
2. `python3 -I tools/sym_to_names.py ghidra/symbols.sym --range 08804000-08872bfc --create-unnamed > re/names-ppsspp.csv`
3. `ApplyNames.java re/names-ppsspp.csv`, then `ApplyNames.java re/names.csv` (hand-made names win), then `ExportFunctions.java re/functions.csv`.

This adds the 278 import stubs and about 370 functions that only PPSSPP had found, for 2,898 functions in total.

## Key functions

Addresses are in `BOOT.BIN` at base `0x08804000`. Confidence: H high, M medium.

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x0881e054` | `container_build_file_index` | H | Opens `umd1:`, reads the PVD path-table size (`+0x84`), the path table, the root LBA, walks it, then sorts and sets the ready flag. Single caller `0x08833734`. |
| `0x0881dd88` | `container_index_directory` | H | Walks ISO 9660 directory records (flags `+0x19` bit 1, name `+0x20/+0x21`, LBA `+0x02`, size `+0x0A`); recursive. |
| `0x0881dfe0` | `container_lookup_file_index(path, out_size) → lba or -1` | H | `bsearch` over the 16-byte entries; returns `+4`, stores `+8`. |
| `0x0881d8fc` | `container_resolve_path(buf, root, rel, no_lbn)` | H | `strcpy(buf, roots[root]); strcat(buf, rel)`; when `no_lbn == 0`, the path is on `disc` and the index is ready, rewrites `buf` as `disc0:/sce_lbn0x%04x_size0x%04x`. Root table pointer at `0x08920cac`. |
| `0x0881dafc` | `container_get_file_size(root, rel) → size or -1` | H | Index lookup on `disc` paths, else `sceIoGetstat` and the stat size field. |
| `0x0881dcd0` | `container_is_disc_path(path)` | H | Compares the first word with `"disc"` (`0x0889ede0`). |
| `0x0881d6a8` | `container_load_file(root, rel, dest, size, callback, arg)` | M | Forwards to `0x0881d7b8`; argument roles inferred from the `card_db_load_cardinfo` call site. |
| `0x0881dce8` | `container_gzip_decompress` | M | 28-byte wrapper that only calls `sceGzipDecompress`; no direct callers (called through a pointer). |
| `0x08822340` | `container_ehp_is_valid(ehp)` | H | `(*(u32 *)ehp & 0xffffff) == 0x504845` (`"EHP"`). |
| `0x08822270` | `container_ehp_find_entry(ehp, name) → entry or 0` | H | Binary search over entries `ehp + 8 + 8i` for `i` in `1..N` (`N` at `+0x0C`), comparing `ehp + name_offset` with `system_strcasecmp`. |
| `0x08822600` | `container_ehp_get_member_size(ehp, entry)` | H | Version byte `< 3`: next data offset (or total size) minus own data offset; otherwise the unaligned `u32` after the NUL of the name, assembled byte by byte. |
| `0x08822280` | `container_ehp_find_member(ehp, name, out_size) → data or 0` | H | Validity check, `find_entry`, returns `ehp + data_offset`; 16 callers, including lookups of `loading.ehf` and `RCP_%03d.ydc`. |
| `0x088220e8` | `container_ehp_bind(ehp, flag)` | H | Writes `"BIND"` over `"NOT "` at `+8` and calls `bind_members` unless already bound; then runs and clears the one-shot callback at `0x08921918`. |
| `0x08822360` | `container_ehp_bind_members(ehp)` | H | Walks the entry table until a zero name offset; dispatches on the name's last four characters (`ptrs.txt`, `.tma`, `.tmt`, `.tms`, `.ehf`, `.gim`, runtime table); see `docs/formats/ehp.md`. |
| `0x08821f40` | `container_ehp_bind_with_callback(callback, ehp)` | M | Stores `callback` in `0x08921918` if free, then `container_ehp_bind(ehp, 1)`. The six embedded archives are bound this way with no callback by `0x08835c68`. |

gzip is inflated by a statically linked copy of Sony's `libdeflt` (`sceGzipDecompress` at `0x08817950`, see `sdk.md`). `TGMT` members are inflated on use by `field_3d_set_tgmt_data` (`field_3d.md`).

Library code these depend on is listed in `system.md` and `sdk.md`.

## Open questions

- `container_load_file` / `0x0881d7b8`: synchronous or queued? Which thread performs the read, and what does the callback receive?
- Contents of the root-directory table at `*0x08920cac` (filled at runtime by `0x0881d574` and `0x0881d63c`); root index 5 is used for `cardinfo`.
- `0x08822774` returns a pointer into a member name from which the four-character extension is read; confirm whether it is `strrchr(name, '.')`.
- The file-index comparator `0x0881dfd4` also calls `system_strcasecmp`, so disc paths are probably matched case-insensitively; confirm by reading the comparator.
- Who calls `container_gzip_decompress` (through which pointer table), and who inflates the loose `field/*.gz` EHP files.
- Ghidra cannot create the function PPSSPP reports at `0x0881d8f4`, 8 bytes before `container_resolve_path`; check whether it is a real 8-byte function or a misdetection.
- `.cip` card-image containers in `card/` (732 MiB, magics `CIP`, `CPM`, `CPL`, `CPJ`); `BOOT.BIN` references them as `card/cardh_<lang>.cip` among others.
- The `snd/` sound bank (`SP\0\0`, 132 MiB).
- Whether `gmodule/*.prx` are overlays loaded on demand (the path `disc0:/PSP_GAME/USRDIR/module/` is referenced at `0x0889fb24`).
