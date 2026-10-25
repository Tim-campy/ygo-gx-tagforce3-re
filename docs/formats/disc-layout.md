# Disc layout (UMD image)

Status: `reimplemented`: `tools/iso9660.py` lists and extracts every file of the reference dump (see `README.md`). Not yet `verified` against an independent extractor.

## Filesystem

ISO 9660, 2048-byte sectors, little-endian fields read from the primary volume descriptor at sector 16.

| Path | Size (bytes) | Notes |
| --- | --- | --- |
| `UMD_DATA.BIN` | — | Standard UMD identifier file. |
| `PSP_GAME/SYSDIR/EBOOT.BIN` | 1,288,480 | Starts with `~PSP`: encrypted executable. Not to be decrypted (see `CLAUDE.md`). |
| `PSP_GAME/SYSDIR/BOOT.BIN` | 1,288,140 | Starts with `\x7fELF`, `e_type = 0xFFA0` (PSP relocatable PRX), `e_machine = 8` (MIPS), `e_entry = 0x0005b45c`. 888,858 non-zero bytes, so not a blanked placeholder. |
| `PSP_GAME/SYSDIR/UPDATE/` | 2048 (dir) | System update directory. |
| `PSP_GAME/USRDIR/` | — | Game data, see below. |

Basis: direct ISO 9660 directory walk and header reads of the reference dump (2026-10-24).

## `PSP_GAME/USRDIR` top-level directories

`card`, `d_tutorial`, `database`, `deck`, `duelsys`, `duel`, `field`, `gmodule`, `help`, `labo`, `main`, `menu`, `minigame`, `module`, `movie`, `script`, `shop`, `snd`, `title_menu`, `title`, `tutorial`, `umd_replace`.

Names suggest where later work packages start (hypotheses, low confidence until contents are inspected): `card`/`database` → card database (WP2); `duelsys`/`duel` → duel core (WP4); `script` → possibly a script interpreter for effects or events (WP4/WP7); `field` → 3D field backdrops (WP8); `snd` → audio (WP9); `module`/`gmodule` → additional PRX modules.

## Inventory by file type

The image holds 2,194 entries: 2,131 files plus directories. Extract with `tools/iso9660.py <image> -x extracted/umd`. Sizes are MiB of loose files; "first bytes" is the file's leading magic.

| Directory | Files | MiB | Types (first bytes) |
| --- | --- | --- | --- |
| `card` | 12 | 732.4 | `.cip`: `CIP\x1a` ×5, `CPM\x1a` ×5, `CPL\x1a`, `CPJ\x1a`. Card images indexed by card id; see `cip.md` (`CPJ` is encrypted). |
| `movie` | 73 | 243.1 | `.pmf` (`PSMF`): Sony PSMF video. |
| `duel` | 343 | 143.3 | `.ehp` ×303, `.gim` ×40. |
| `field` | 937 | 142.2 | `.gim` ×779, `.ehp` ×80, `.gz` ×78 (gzip around EHP). |
| `snd` | 1 | 132.2 | One `.bin` starting with `SP\0\0`: a chain of 728 sound banks; see `sound.md`. |
| `minigame` | 583 | 73.5 | `.gim` ×518, `.ehp` ×65. |
| `gmodule` | 36 | 7.3 | `.prx`, plain ELF: game code modules, analysable like `BOOT.BIN`. |
| `module` | 1 | <0.1 | `.prx` starting with `~SCE`: a Sony system module (`sdk`). |
| `help` | 53 | 0.6 | `.gim`. |
| all other `USRDIR` directories | 1–18 each | 0.1–18.4 | `.ehp` only. |
| `PSP_GAME/SYSDIR/UPDATE` | 3 | 24.6 | System update (`PSAR`, `~PSP`, `PSF`); out of scope. |
| `PSP_GAME` | 3 | 0.3 | `PARAM.SFO` and two PNG icons. |
| root | 1 | <0.1 | `UMD_DATA.BIN`, starts with the product code `ULES`. |

EHP archives are documented in `ehp.md`.

## Open questions

- Is `BOOT.BIN` the same program as `EBOOT.BIN`? Hypothesis, medium confidence (sizes differ by 340 bytes). Confirm by comparing BOOT.BIN against the module PPSSPP loads at runtime.
- Formats still to identify: the member types listed in `ehp.md` (the `snd/` banks are in `sound.md`, the `script/` archives in `story.md`).
- Which `gmodule/` PRX modules are loaded, by whom and when.
