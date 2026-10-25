# Setup

How to reproduce the analysis. You need your own copy of the game; nothing from the disc is in this repository.

## Repository layout

| Path | Contents | In git |
| --- | --- | --- |
| `CLAUDE.md` | Working rules for this phase: mission, legal boundary, method. | yes |
| `docs/formats/` | One document per file format or data structure. | yes |
| `docs/subsystems/` | One document per subsystem (`container`, `card_db`, ...), with open questions. | yes |
| `docs/PROGRESS.md` | Counting rules for the progress tool. | yes |
| `re/functions.csv`, `re/formats.csv` | Registries that feed the progress meter. | yes |
| `re/names.csv`, `re/names-ppsspp.csv` | Function names applied to the Ghidra project. | yes |
| `tools/` | Extractors and the progress tool. | yes |
| `tools/tests/` | Tests for the tools (synthetic data only). | yes |
| `tools/ghidra/` | Ghidra scripts (`ApplyNames.java`, `ExportFunctions.java`). | yes |
| `game/` | Your own disc image. | **no** |
| `extracted/` | Files extracted from the disc image. | **no** |
| `ghidra/` | The Ghidra project and PPSSPP symbol exports. | **no** |
| `external/ppsspp/` | PPSSPP portable build. | **no** |
| `build/` | Generated progress site. | **no** |

## Reference dump

| Field | Value |
| --- | --- |
| Image | `Yu-Gi-Oh! GX - Tag Force 3 (Europe) (En,Fr,De,Es,It).iso` |
| Size | 1,792,999,424 bytes |
| SHA-1 | `379601A07D73374FA4A03272488FD195133D7C0D` |

All offsets and addresses in `docs/` refer to this dump unless stated otherwise. Code addresses refer to `PSP_GAME/SYSDIR/BOOT.BIN` loaded at `0x08804000`; the encrypted `EBOOT.BIN` is never needed.

## Extracting data

```
python3 -I tools/iso9660.py game/<image>.iso -x extracted/umd
python3 -I tools/ehp.py extracted/umd/PSP_GAME/USRDIR/<dir>/*.ehp -x extracted/ehp/<dir> -r -z
python3 -I tools/cardinfo.py extracted/umd/PSP_GAME/USRDIR/duelsys/cardinfo_eng.ehp -o extracted/cards_eng.csv
```

## Tools

- **Python 3.11+**, standard library only. Run the tests with `python3 -I tools/tests/test_<name>.py`.
- **Ghidra 12.1.4** (Java 21). Ghidra rejects project and input paths that contain an element starting with `.`, so keep projects under `ghidra/`.
- **ghidra-allegrex** (kotcrab, Apache-2.0) adds the Allegrex processor, including VFPU instructions. No prebuilt release exists for 12.1.4, so build it from the `v21.4` tag:

  ```
  git clone --depth 1 --branch v21.4 https://github.com/kotcrab/ghidra-allegrex.git
  cd ghidra-allegrex
  GHIDRA_INSTALL_DIR=C:/Ghidra ./gradlew buildExtension
  unzip dist/ghidra_12.1.4_PUBLIC_*_ghidra-allegrex.zip -d C:/Ghidra/Ghidra/Extensions/
  ```

  The language id is `Allegrex:LE:32:default`; import `BOOT.BIN` with the `PSP Executable (ELF)` loader and image base `08804000`. Rebuild the extension after every Ghidra upgrade.
- **PPSSPP** is the behavioural oracle; run the game only there. Its Debug menu exports a `.sym` symbol file (keep it in `ghidra/`), which `tools/sym_to_names.py` turns into Ghidra names. The full sequence is in `docs/subsystems/container.md`.
- **REA** (`rea-agents`) can connect an agent to Ghidra; `npx rea-agents setup` registers it.
- Headless Ghidra refuses paths with a `.`-prefixed element, so copy `tools/ghidra/*.java` and the CSV inputs to a plain directory before running them from a checkout under a dot-directory.

## Progress

```
python3 -I tools/progress.py --check
python3 -I tools/progress.py build/progress --log
```

The CI workflow (`.github/workflows/progress.yml`) runs the tests and publishes the same site to GitHub Pages on every push to `main`.
