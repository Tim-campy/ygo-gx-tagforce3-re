# Disc layout (UMD image)

Status: `named` (located; per-file formats not yet documented). Reference dump: see `README.md`.

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

## Open questions

- Is `BOOT.BIN` the same program as `EBOOT.BIN`? Hypothesis, medium confidence (sizes differ by 340 bytes). Confirm by comparing BOOT.BIN against the module PPSSPP loads at runtime.
- Contents and container formats of each `USRDIR` subdirectory (WP1).
- Which PRX modules live in `module/` and `gmodule/`, and who loads them.
