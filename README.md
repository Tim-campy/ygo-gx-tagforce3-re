# Yu-Gi-Oh! GX Tag Force 3 — reverse engineering

Knowledge base for a future native Nintendo 3DS port of *Yu-Gi-Oh! GX Tag Force 3* (PSP). See `CLAUDE.md` for the rules of this phase and `docs/PROGRESS.md` for how progress is counted.

## Layout

| Path | Contents | In git |
| --- | --- | --- |
| `CLAUDE.md` | Agent instructions: mission, legal boundary, method. | yes |
| `docs/formats/` | One document per file format or data structure. | yes |
| `docs/subsystems/` | One document per subsystem (`card_db`, `duel_core`, ...). | yes |
| `docs/PROGRESS.md` | Counting rules for the progress tool. | yes |
| `re/functions.csv`, `re/formats.csv` | Registries that feed the progress meter. | yes |
| `tools/` | Project scripts (`progress.py`, extractors). GPL-2.0-only. | yes |
| `tools/tests/` | Tests for the scripts. | yes |
| `tools/ghidra/` | Ghidra scripts (`ExportFunctions.java` feeds `re/functions.csv`). | yes |
| `game/` | The maintainer's own disc image. | **no** |
| `extracted/` | Files extracted from the disc image. | **no** |
| `ghidra/` | The Ghidra project. | **no** |
| `external/ppsspp/` | PPSSPP portable build, the behavioural oracle. | **no** |
| `build/` | Generated progress site. | **no** |

## Reference dump

| Field | Value |
| --- | --- |
| Image | `Yu-Gi-Oh! GX - Tag Force 3 (Europe) (En,Fr,De,Es,It).iso` |
| Size | 1,792,999,424 bytes |
| SHA-1 | `379601A07D73374FA4A03272488FD195133D7C0D` |

All offsets and addresses in `docs/` refer to this dump unless stated otherwise.

## Tool setup

- **Ghidra 12.1.4** at `C:\Ghidra` (Java 21). Ghidra rejects project and input paths that contain an element starting with `.`, so keep projects under `ghidra/`, not under a dot-directory.
- **ghidra-allegrex** (kotcrab, Apache-2.0) adds the Allegrex processor, including VFPU instructions. No prebuilt release exists for 12.1.4, so it is built from the `v21.4` tag:

  ```
  git clone --depth 1 --branch v21.4 https://github.com/kotcrab/ghidra-allegrex.git
  cd ghidra-allegrex
  GHIDRA_INSTALL_DIR=C:/Ghidra ./gradlew buildExtension
  unzip dist/ghidra_12.1.4_PUBLIC_*_ghidra-allegrex.zip -d C:/Ghidra/Ghidra/Extensions/
  ```

  The language id is `Allegrex:LE:32:default`. Rebuild after every Ghidra upgrade.
- **REA** (`rea-agents`) connects the agent to Ghidra; `npx rea-agents setup` registers it.
- **PPSSPP** portable in `external/ppsspp/`; run the game only there.
