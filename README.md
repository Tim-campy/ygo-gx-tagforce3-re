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
| 1. Containers and file formats | Disc layout, the boot-time file index, [EHP archives](docs/formats/ehp.md) (byte-exact rebuild of all 629 on the disc), gzip (Sony's `libdeflt`, statically linked), the [`.cip` card images](docs/formats/cip.md) including the 512×512 JPEG art, the [sound banks](docs/formats/sound.md) (728 banks, 18,608 clips) and the [story text and event bytecode](docs/formats/story.md) are done. The [2D layouts](docs/formats/ehf.md) (`.ehf`, converted Flash timelines) and [GIM textures](docs/formats/gim.md) are documented; The [3D models](docs/formats/tgm.md) (TGMS meshes with GE vertex formats and skinning, TGMT node animation, TGMA texture animation) are decoded. |
| 2. Card database | [`cardinfo`](docs/formats/cardinfo.md) is decoded: 3,553 cards with stats and all enumerations, passcodes, names and Huffman-coded descriptions, verified in all five languages. The [48 booster packs](docs/formats/packs.md), the [forbidden/limited list](docs/formats/limit-list.md) and the [661 opponent decks](docs/formats/deck.md) (byte-exact rebuild) are decoded. |
| 3. Save data | [`DATA0`](docs/formats/save.md) is a raw 128 KiB copy of game state: the deck slots (the player's and one per partner character) and the card collection with per-card copies and forbidden/limited status are mapped; story progress, characters and DP are open. |
| 4. Duel core and card effects | The [effect architecture](docs/subsystems/duel_effects.md) is established: native handlers in `rel_duel_eng.prx`, found through id-sorted [handler tables](docs/formats/effect-tables.md) whose slots are resolution (`+04`), target filter (`+08`) and activation condition (`+0c`); handlers implement effect families and per-card numbers live in card-id compare chains; no script interpreter. The [field layout](docs/subsystems/duel_core.md) is partly known. |
| 5. Tag-duel specifics | The [partner swap](docs/subsystems/tag_duel.md) is established: partners share field and Life Points, and each turn change swaps the active duelist's hand, deck and extra deck with the partner's. |
| 6. AI | [Entry points](docs/subsystems/ai.md): the CPU branch of target choice and its working memory. |
| 7. Free-roam world | The [story event bytecode](docs/formats/story.md) is decoded: interpreter, control flow (conditions, menus, jumps) and opcode families (dialogue, story flags, DP, card gifts, duels, scene set-up). |
| 8–9. Rendering data, audio | 3D models, 2D layouts, textures and sound banks are decoded (package 1). |

## Tools

All tools are Python 3 with the standard library only, and each has tests on synthetic data.

| Tool | Purpose |
| --- | --- |
| [`tools/iso9660.py`](tools/iso9660.py) | List and extract the UMD image. |
| [`tools/ehp.py`](tools/ehp.py) | List, extract, rebuild and verify EHP archives (`-r` nested, `-z` gunzip). |
| [`tools/cardinfo.py`](tools/cardinfo.py) | Export the card database to CSV/JSON and check its structure. |
| [`tools/tables.py`](tools/tables.py) | Export the booster packs (`rel_shop.prx`) and the limit list (`BOOT.BIN`). |
| [`tools/decks.py`](tools/decks.py) | Export the opponent deck recipes, alternative-artwork tables and tutorial scripts. |
| [`tools/cip.py`](tools/cip.py) | List the card image containers, decode images to PNG and unmask the 512×512 JPEG card art (`jpeg`). |
| [`tools/tgm.py`](tools/tgm.py) | List and check the 3D models and animations; export a model to OBJ with textures. |
| [`tools/ehf.py`](tools/ehf.py) | List, check and render the 2D layouts (`.ehf` + `.tmf`) to PNG. |
| [`tools/tutorial.py`](tools/tutorial.py) | Check and list the duel-tutorial setups (`.ydq`), scripts and text. |
| [`tools/effect_params.py`](tools/effect_params.py) | Extract per-card effect parameters from the duel engine: target filters, draw counts, LP costs and other compare chains. |
| [`tools/effect_classify.py`](tools/effect_classify.py) | Classify the effect records by the helpers, engine commands and batch stores their handlers reach (mapping in `tools/effect_categories.csv`); coverage, naming worklist and AI handler clusters. |
| [`tools/stat_mods.py`](tools/stat_mods.py) | List the per-card ATK/DEF modifiers of the duel engine by layer (own effect, other cards, field spell, attached effects, equips, Damage Step) and their coverage. |
| [`tools/ai_tables.py`](tools/ai_tables.py) | List and check the duel AI's per-card priority tables (card id, handler, situation). |
| [`tools/fusion.py`](tools/fusion.py) | List and check the duel engine's fusion recipe table (materials by card id, Type or card group) and ritual table (monster, spell, Level total). |
| [`tools/card_effects.py`](tools/card_effects.py) | Join the per-card analyses (effect records and categories, parameters, stat modifiers, fusion/ritual, AI tables, tokens, optional search filters) into one per-card effect specification (JSON Lines + CSV) with sources and confidence per field. |
| [`tools/save.py`](tools/save.py) | Read a plaintext `DATA0` save: deck slots, card collection, checks. |
| [`tools/sound.py`](tools/sound.py) | List and check the sound banks; export a clip (ATRAC3/ATRAC3plus as stored, PS-ADPCM to WAV). |
| [`tools/voices.py`](tools/voices.py) | Check and list the character voice tables, voice banks and voice-test items. |
| [`tools/world.py`](tools/world.py) | Check and dump the free-roam walk grids (`.hmp`) of the field maps. |
| [`tools/story.py`](tools/story.py) | Export the story text and check the event bytecode and its text references. |
| [`tools/sym_to_names.py`](tools/sym_to_names.py) | Turn a PPSSPP `.sym` export into Ghidra names. |
| [`tools/modules.py`](tools/modules.py) | Catalogue the game modules: sections, exports and imports, descriptor tables, runtime bases. |
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
