# Card database (work package 2)

Not started; entry points found while working on containers.

## Key functions

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x08832684` | `card_db_load_cardinfo` | H | Builds `…cardinfo_` + a language suffix (table at `0x08878c88`, 8 bytes per language, index from `0x08857b80`) + `.ehp`, gets its size with `container_get_file_size(5, …)` and loads it to `0x08926b50` with `container_load_file`. No direct callers (probably called through a pointer). |

## Data

- `duelsys/cardinfo_<lang>.ehp`, one per language (`eng`, `fra`, `ger`, `ita`, `spa`), 14 members each; layout in `docs/formats/ehp.md`. The members are the first target of this package.
- `card/*.cip`: card images (format unknown), referenced in `BOOT.BIN` as `card/cardh_<lang>.cip` and similar.

## Open questions

- What the 14 `cardinfo` members contain (names, effect text, stats, pack lists?) and how `0x08926b50` is used once loaded.
- The language index source `0x08857b80` (system language, or the game's own setting).
