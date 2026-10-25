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
3. `ApplyNames.java re/names-ppsspp.csv`, then `ApplyNames.java re/names.csv` (hand-made names win), then `ApplySignatures.java re/documented.tsv`, then `ExportFunctions.java re/functions.csv`.

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
| `0x0881d6a8` | `container_load_file(root, rel, dest, size, callback, arg)` | H | Tail call `container_read_async(root, rel, dest, 0, size, callback, arg)` (register shuffle + `li a3,0`). Callers `card_db_load_cardinfo`, `save_open`, `0x08821e00`, `0x0884c808`. |
| `0x0881d7b8` | `container_read_async(root, rel, dest, offset, size, callback, arg)` | H | Takes the next slot of the request ring under semaphore `0x089218b8`, fills it as type 0 and signals `0x089218bc`. Returns 1. Callers include `container_load_file`, `card_db_read_next_cip_slot`, `0x08822a28`, `0x0883cafc`–`0x0883d980` (card art), `0x088414a0`, `0x08841564` (sound). |
| `0x0881d574` | `container_init_file_thread(config)` | H | Clears `0xc1c` bytes at `0x08920cac`, stores `config[0]` (the root path table) at `0x08920cac`, starts the file thread (priority `0x6f`, `0x2000`-byte stack) and creates semaphores `ehfile_sema` (1/1) and `ehfile_queue` (0/32). Caller `0x0881d1a8` (boot). |
| `0x0881dba0` | `container_file_thread` | H | Loop: wait on `0x089218bc`, `container_take_request`, run it (type 0: `container_read_file`; type 1: `system_load_module`), call `callback(arg, result)`; while the callback returns 0 the operation is repeated; then the slot's busy word is cleared. |
| `0x0881dc70` | `container_take_request() → slot or 0` | H | Scans the ring from the write index `0x089218b4` for a busy slot. Caller `container_file_thread`. |
| `0x0881d6c0` | `container_read_file(root, rel, dest, offset, size) → bytes, −1, −2` | H | `container_resolve_path`; disc paths go to `container_read_disc_file`, others to `sceIoOpen`/`sceIoLseek` (only when `offset > 0`)/`sceIoRead`/`sceIoClose`. −1 open failed, −2 seek failed. Callers `container_file_thread`, `0x0881d69c`, `0x08822a28`. |
| `0x0881e210` | `container_read_disc_file(path, dest, offset, size)` | M | Same sequence through `0x0881e2c4`, `0x0881e448`, `0x0881e378` (not read; presumably sector-level wrappers for `sce_lbn` paths). Caller `container_read_file`. |

**Request ring.** 32 slots of `0x60` bytes at `0x08920cb4` (inside the state block at `0x08920cac`): `+0x00` busy, `+0x04` type (0 read, 1 module load), `+0x08` root, `+0x0c` dest, `+0x10` offset, `+0x14` size, `+0x18` callback, `+0x1c` arg, `+0x20` path (up to 63 characters, `system_strncpy`). The write index is `0x089218b4`. All file reads and module loads are serialised on the one file thread; callers learn of completion only through the callback, which receives `(arg, bytes read or error)` and must return non-zero to accept the result (`card_db_on_cardinfo_loaded` and `save_on_resources_loaded` always return 1).
| `0x0881dce8` | `container_gzip_decompress(dst, dst_size, src)` | H | 28-byte wrapper: `sceGzipDecompress(dst, dst_size, src, &crc)` with the CRC on the stack discarded; returns the inflated size or the error. No direct callers (exported). |
| `0x08822340` | `container_ehp_is_valid(ehp)` | H | `(*(u32 *)ehp & 0xffffff) == 0x504845` (`"EHP"`). |
| `0x08822270` | `container_ehp_find_entry(ehp, name) → entry or 0` | H | Binary search over entries `ehp + 8 + 8i` for `i` in `1..N` (`N` at `+0x0C`), comparing `ehp + name_offset` with `system_strcasecmp`. |
| `0x08822600` | `container_ehp_get_member_size(ehp, entry)` | H | Version byte `< 3`: next data offset (or total size) minus own data offset; otherwise the unaligned `u32` after the NUL of the name, assembled byte by byte. |
| `0x08822280` | `container_ehp_find_member(ehp, name, out_size) → data or 0` | H | Validity check, `find_entry`, returns `ehp + data_offset`; 16 callers, including lookups of `loading.ehf` and `RCP_%03d.ydc`. |
| `0x088220e8` | `container_ehp_bind(ehp, flag)` | H | Writes `"BIND"` over `"NOT "` at `+8` and calls `bind_members` unless already bound; then runs and clears the one-shot callback at `0x08921918`. |
| `0x08822360` | `container_ehp_bind_members(ehp)` | H | Walks the entry table until a zero name offset; dispatches on the name's last four characters (`ptrs.txt`, `.tma`, `.tmt`, `.tms`, `.ehf`, `.gim`, runtime table); see `docs/formats/ehp.md`. |
| `0x08821f40` | `container_ehp_bind_with_callback(callback, ehp) → 1 or 0` | H | Only if the slot `0x08921918` is free: stores `callback`, `container_ehp_bind(ehp, 1)`, returns 1; otherwise returns 0 and does not bind. Callers `card_db_bind_cardinfo`, `save_on_resources_loaded`, `system_init_game_globals` (`0x08835c68`, the six embedded archives, no callback). |

gzip is inflated by a statically linked copy of Sony's `libdeflt` (`sceGzipDecompress` at `0x08817950`, see `sdk.md`). `TGMT` members are inflated on use by `field_3d_set_tgmt_data` (`field_3d.md`).

Library code these depend on is listed in `system.md` and `sdk.md`.

## Open questions

- What the disc wrappers `0x0881e2c4`, `0x0881e378`, `0x0881e448` add over plain `sceIo` calls (retries, sector alignment?).
- Contents of the root-directory table at `*0x08920cac` (filled at runtime by `0x0881d574` and `0x0881d63c`); root index 5 is used for `cardinfo`.
- `0x08822774` returns a pointer into a member name from which the four-character extension is read; confirm whether it is `strrchr(name, '.')`.
- The file-index comparator `0x0881dfd4` also calls `system_strcasecmp`, so disc paths are probably matched case-insensitively; confirm by reading the comparator.
- Who calls `container_gzip_decompress` (through which pointer table), and who inflates the loose `field/*.gz` EHP files.
- Ghidra cannot create the function PPSSPP reports at `0x0881d8f4`, 8 bytes before `container_resolve_path`; check whether it is a real 8-byte function or a misdetection.
- `.cip` card-image containers in `card/` (732 MiB, magics `CIP`, `CPM`, `CPL`, `CPJ`); `BOOT.BIN` references them as `card/cardh_<lang>.cip` among others.
- The `snd/` sound bank (`SP\0\0`, 132 MiB).
- ~~Whether `gmodule/*.prx` are overlays loaded on demand.~~ Answered in `modules.md`: they are loaded on demand, either as the single current scene module (`ehscript` thread) or as reference-counted library modules. The kernel chooses each module's address. Module loads go through the same file-thread queue as `container_read_async`. `0x0889fb24` is the root path table (`module/`, `kmodule/`, `gmodule/`, `USRDIR/`, `duel/`, `duelsys/`, `main/`, `snd/`, `minigame/`).
