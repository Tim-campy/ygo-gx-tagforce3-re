# About

Reverse engineering of *Yu-Gi-Oh! GX Tag Force 3* (PSP, Konami, 2008; released in Europe and Japan only), working towards a native Nintendo 3DS remake that uses both screens.

The project is in its **reverse-engineering phase**: the output is knowledge, not a port. File formats, data structures and the game's own code are documented precisely enough that the 3DS version can later be built without reopening the binary.

[Setup and extraction](docs/SETUP.md), [file formats](docs/formats), [subsystems](docs/subsystems), [progress rules](docs/PROGRESS.md), [working method](CLAUDE.md)

## Status

[![functions](https://tim-campy.github.io/ygo-gx-tagforce3-re/badge-functions.svg)](https://tim-campy.github.io/ygo-gx-tagforce3-re/progress.html) [![formats](https://tim-campy.github.io/ygo-gx-tagforce3-re/badge-formats.svg)](https://tim-campy.github.io/ygo-gx-tagforce3-re/progress.html)

[![progress map](https://tim-campy.github.io/ygo-gx-tagforce3-re/progress.svg)](https://tim-campy.github.io/ygo-gx-tagforce3-re/progress.html)

<sub>* Percentages count entries already in the registries (`re/functions.csv`, `re/formats.csv`) at the `documented` stage, not every function in the game. The function list covers `BOOT.BIN` and the duel engine `rel_duel_eng.prx` (Ghidra plus PPSSPP's runtime symbols); the other 35 modules in `gmodule/` are not counted yet.</sub>

| Work package | State |
| --- | --- |
| 1. Containers and file formats | Disc layout, the boot-time file index, [EHP archives](docs/formats/ehp.md) (byte-exact rebuild of all 629 on the disc), gzip (Sony's `libdeflt`, statically linked) and the [`.cip` card images](docs/formats/cip.md) are done. `TGM*` models, `.ehf` layouts and the sound bank are open. |
| 2. Card database | [`cardinfo`](docs/formats/cardinfo.md) is decoded: 3,553 cards with stats and all enumerations, passcodes, names and Huffman-coded descriptions, verified in all five languages. The [48 booster packs](docs/formats/packs.md), the [forbidden/limited list](docs/formats/limit-list.md) and the [661 opponent decks](docs/formats/deck.md) (byte-exact rebuild) are decoded. |
| 3. Save data | Not started. |
| 4. Duel core and card effects | The [effect architecture](docs/subsystems/duel_effects.md) is established: native per-card handlers in `rel_duel_eng.prx`, found through four id-sorted [handler tables](docs/formats/effect-tables.md), plus card-id compare chains; no script interpreter. Slot meanings are open. |
| 5. Tag-duel specifics | Not started. |
| 6–9. AI, free-roam world, rendering data, audio | Entry points found while working on packages 1–2. |

## Tools

All tools are Python 3 with the standard library only, and each has tests on synthetic data.

| Tool | Purpose |
| --- | --- |
| [`tools/iso9660.py`](tools/iso9660.py) | List and extract the UMD image. |
| [`tools/ehp.py`](tools/ehp.py) | List, extract, rebuild and verify EHP archives (`-r` nested, `-z` gunzip). |
| [`tools/cardinfo.py`](tools/cardinfo.py) | Export the card database to CSV/JSON and check its structure. |
| [`tools/tables.py`](tools/tables.py) | Export the booster packs (`rel_shop.prx`) and the limit list (`BOOT.BIN`). |
| [`tools/decks.py`](tools/decks.py) | Export the opponent deck recipes, alternative-artwork tables and tutorial scripts. |
| [`tools/cip.py`](tools/cip.py) | List the card image containers and decode an image to PNG. |
| [`tools/sym_to_names.py`](tools/sym_to_names.py) | Turn a PPSSPP `.sym` export into Ghidra names. |
| [`tools/prx_imports.py`](tools/prx_imports.py) | Resolve a module's imports against `BOOT.BIN`'s exports and name the stubs. |
| [`tools/progress.py`](tools/progress.py) | Progress numbers, treemap, badges and history from the registries. |
| [`tools/ghidra/`](tools/ghidra) | Ghidra scripts to apply names and export the function registry. |

## Related projects

[ygotfToolkit](https://github.com/eireetm/ygotfToolkit) is a modding toolkit for the whole Tag Force series. This project's findings were cross-checked against its format notes; see [prior art](docs/PRIOR_ART.md) for what agrees, what differs on Tag Force 3 and the leads it gives.

## Disclaimer

This project is intended for research, preservation and interoperability. It does not include, distribute or require copyrighted game data: no disc images, executables, extracted assets, text dumps or save files. Findings are recorded as knowledge (layouts, offsets, algorithms, names and small illustrative values). Users are responsible for obtaining their own copy of the game and using it in accordance with applicable laws.

This is an independent project and is not affiliated with, authorized or endorsed by Konami or Sony Interactive Entertainment. "Yu-Gi-Oh!" is a trademark of Kazuki Takahashi and Konami; "PlayStation Portable" and "PSP" are trademarks of Sony Interactive Entertainment Inc.

## License

This project is licensed under the GNU General Public License version 2 only. `tools/progress.py` adapts parts of [AnyPS5](https://github.com/boykopovar/AnyPS5)'s progress tool, which is GPL-2.0.
