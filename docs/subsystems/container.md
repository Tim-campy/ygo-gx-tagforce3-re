# Containers (work package 1)

How the game's data is packaged on the disc, from the outside in:

1. **UMD image** (ISO 9660): `docs/formats/disc-layout.md`, extractor `tools/iso9660.py`.
2. **EHP archives**: the general container used by almost every `USRDIR` directory. `docs/formats/ehp.md`, tool `tools/ehp.py` (list, extract, rebuild, `--verify`).
3. **gzip**: standard gzip, used in two places only: `.gz` members inside `duel/` archives (always `TGMT`) and loose `field/*.gz` files (always EHP). `tools/ehp.py -z` decompresses while extracting.
4. **Leaf formats** inside archives or loose on the disc: GIM textures, PSMF movies, PNG, and the formats still unknown (`.cip`, the `snd/` bank, `.ehf`, the `TGM*` family, `.ydq`, `.bin`, `.txt`).

No custom compression or encryption has been found in the data files so far; the only encrypted file is `EBOOT.BIN`, and it is not needed because `BOOT.BIN` is a plain ELF.

## Extracting everything

```
python3 -I tools/iso9660.py game/<image>.iso -x extracted/umd
python3 -I tools/ehp.py extracted/umd/PSP_GAME/USRDIR/duel/*.ehp -x extracted/ehp/duel -r -z
```

## Key functions

None identified yet; the EHP reader in `BOOT.BIN` is the next target.

## Open questions

- Which `BOOT.BIN` functions open files, read EHP archives and inflate gzip, and does the game look EHP members up by name or by index?
- `.cip` card-image containers in `card/` (732 MiB, four magics: `CIP`, `CPM`, `CPL`, `CPJ`).
- The `snd/` sound bank (`SP\0\0`, 132 MiB).
- Whether `gmodule/*.prx` are overlays loaded on demand, and which subsystem each one implements.
