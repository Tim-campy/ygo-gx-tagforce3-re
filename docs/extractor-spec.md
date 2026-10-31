# Extractor specification

This document is the deliverable that `CLAUDE.md` ("Done means") asks for: for **every asset class the 3DS port needs**, where it lives on the disc, which format document describes it, which tool in `tools/` reads it today and with which command, what neutral output the port would consume, what is already verified, and what is still missing. It does not describe the port itself; it describes the data the port gets from the maintainer's own copy of the game.

The coverage table and the open questions are at the end.

## Conventions

- **Placeholders.** `<ISO>` is the maintainer's disc image (`game/<image>.iso`); `<UMD>` is its extracted tree (`extracted/umd`); `<USRDIR>` = `<UMD>/PSP_GAME/USRDIR`; `<SYSDIR>` = `<UMD>/PSP_GAME/SYSDIR`; `<PSP_GAME>` = `<UMD>/PSP_GAME`; `<l>` is a language letter (`e f g i s`; `j` names exist in code but have no file on the European disc), `<lang>` a three-letter language (`eng fra ger ita spa`).
- **Commands** run from the repository root with `python3 -I` (standard library only, Python 3.11+). Every output is game data and goes under `extracted/` (or another directory outside the repository); nothing an extractor writes is ever committed (`CLAUDE.md`, legal boundary).
- **Reference dump**: the image named in `docs/SETUP.md` (SHA-1 `379601A0…`). Every "verified" claim below refers to it.
- **Check run.** All `--check` commands and all tests quoted here were re-run on 2026-10-30 against the maintainer's extracted copy, with outputs written to a scratch directory outside the repository; the result is quoted in each section ("Check run").
- **Neutral targets.** The port is not designed here. The targets below are deliberately platform-neutral: PNG (RGBA8), JPEG (as stored), WAV (16-bit PCM), CSV / JSON / JSON Lines for tables, OBJ+MTL today and a glTF-like description (meshes, skeleton, animation curves, materials) as the goal for models, and "convert at install time" for video. A later conversion to 3DS-native formats (for example `.t3x`, `.bcwav`) is a port task and starts from these targets.

## Pipeline

The disc is unpacked in three stages; every leaf decoder below starts from the output of the first two.

```
<ISO> --iso9660.py--> <UMD> tree (2,131 files)
        |
        +-- USRDIR/**/*.ehp, field/bustup/*.ehp.gz --ehp.py -r -z--> members (629 archives incl. 20 nested)
        |        |
        |        +-- .gim  .ehf/.tmf  .tms/.tmt(.gz)/.tma  .bin tables  .ydq  .hmp  .dat  ...
        |        +-- .gim -> gim.py (PNG)   string-table .bin -> strtbl.py (JSON/TSV)
        +-- card/*.cip ------------------------------------------cip.py
        +-- snd/psp_snddat.bin ----------------------------------sound.py, voices.py; audio_convert.py (+FFmpeg: WAV/OGG/FLAC)
        +-- movie/*.pmf -----------------------------------------psmf.py (check; --convert +FFmpeg: MP4/MKV/WAV)
        +-- SYSDIR/BOOT.BIN, USRDIR/gmodule/*.prx (plain ELF) ---tables in code: tables.py, decks.py, fusion.py,
                                                                 ai_tables.py, effect_*.py, world.py, ...
```

```
python3 -I tools/iso9660.py <ISO> -x extracted/umd
python3 -I tools/ehp.py <USRDIR>/<dir>/*.ehp -x extracted/ehp/<dir> -r -z      # per directory; -r nested, -z gunzip
```

Note: on Windows a single `ehp.py` call over every archive of the disc exceeds the command-line length limit ("Argument list too long"); run it per directory (as above) or per file.

---

## 1. Disc layout and file index

| Item | Value |
| --- | --- |
| Source | `<ISO>`: ISO 9660, 2,048-byte sectors, 2,131 files. `PSP_GAME/SYSDIR/BOOT.BIN` is the plain executable used for all code tables; `EBOOT.BIN` is encrypted and never needed. |
| Format docs | `docs/formats/disc-layout.md`, `docs/formats/file-index.md`, `docs/subsystems/container.md` |
| Tool / command | `python3 -I tools/iso9660.py <ISO> [paths…]` (list), `python3 -I tools/iso9660.py <ISO> -x extracted/umd` (extract) |
| Port output | The extracted tree itself, addressed by path. The game has **no custom file table**: it indexes the ISO directories at boot (`container_build_file_index`, `0x0881e054`) and opens files by sector, so paths (case-insensitive, probably) are the only file identity the port must keep. |
| Verified | `disc_layout` is `reimplemented` in `re/formats.csv`; every other extractor in this document runs on its output. Check run: listing `PSP_GAME/USRDIR/duelsys` returns the five `cardinfo_<lang>.ehp` with LBA and size. Tests: `tools/tests/test_iso9660.py`. |
| Gaps | Not compared with an independent extractor. Case-insensitive lookup is inferred from the comparator calling `system_strcasecmp`, not read in full. |

## 2. EHP archives and gzip

| Item | Value |
| --- | --- |
| Source | Almost every `USRDIR` directory: 531 loose `.ehp`, 78 gzip-wrapped archives `field/bustup/*.ehp.gz` (called `field/*.gz` in `ehp.md`; each wraps one EHP), 20 EHP members nested in `minigame/` archives, 6 archives embedded in `BOOT.BIN` `.data` (`0x088b2f90`, `0x088cc480`, `0x088d77e0`, `0x088ff0d0`, `0x089029b0`, `0x08911580`). Inside `duel/*.ehp`, 8,789 `.gz` members (always TGMT). |
| Format docs | `docs/formats/ehp.md` (layout, case-insensitive name order, bind handlers, `*ptrs.txt`) |
| Tool / command | `python3 -I tools/ehp.py <archive…>` (list: size, magic, name), `-x DIR` (extract to `DIR/<name>.d`), `-r` (nested), `-z` (gunzip `.gz` members and `.gz` archives), `--verify` (rebuild and compare byte for byte), `--check` (the same, one summary line per file). An ELF image is accepted in place of an archive: `ehp.py <SYSDIR>/BOOT.BIN --base 08804000 [-x DIR] [--check]` lists, extracts (`DIR/BOOT.BIN@0x<offset>.d`) or checks each embedded archive. |
| Port output | Plain member files in a directory per archive. The port does not need the EHP container itself; it needs the members by `(archive path, member name)`. `*ptrs.txt` lists (425) are resource bundles (offsets of whole members), which a port that converts data offline can replace by member names. |
| Verified | `ehp` and `gzip_member` are `verified`: the layout rebuilds all 629 archives byte for byte. Check run: `--verify` once per file over every `.ehp` and `.ehp.gz` under `<USRDIR>`: 609 files, 0 failing; `ehp.py <SYSDIR>/BOOT.BIN --check`: `ok: BOOT.BIN: 6 embedded archives, 721 members, all rebuild byte for byte` (none of the 36 `gmodule/*.prx` embeds an archive). Tests: `tools/tests/test_ehp.py`. |
| Gaps | The runtime extension-handler table (`0x0892191c`/`0x08921940`) is not mapped. |

## 3. Card database

| Item | Value |
| --- | --- |
| Source | `<USRDIR>/duelsys/cardinfo_<lang>.ehp` (5 languages, 14 members each): `CARD_Prop`, `CARD_Pass`, `CARD_IntID`, `CARD_Genre`, `CARD_Sort`, `CARD_Top`, `CARD_SamePict` (shared); `CARD_Indx_<L>`, `CARD_Name_<L>`, `CARD_Desc_<L>`, `CARD_Huff_<L>`, `DICT_<L>`, `DLG_Indx_<L>`, `DLG_Text_<L>` (per language). |
| Format docs | `docs/formats/cardinfo.md`, `docs/subsystems/card_db.md` |
| Tool / command | `python3 -I tools/cardinfo.py <USRDIR>/duelsys/cardinfo_<lang>.ehp [--format csv\|json] -o extracted/cards_<lang>.csv`; `--check` for the structural checks; `--dialog [--format csv\|json] -o extracted/dlg_<lang>.csv` dumps the `DLG_Text` duel prompts (`number`, `offset`, `text`), `--dialog --check` checks their layout |
| Port output | One table per language, keyed by card **id** (3720–7993; record index via `CARD_IntID`): ATK, DEF, kind, attribute, Level, spell/trap icon, Type, passcode, name and fully expanded description (Huffman + dictionary + `%c` card-name references), genre bits, sort rank, artwork count. JSON is the natural target. Duel prompts (`DLG_Text`) are a second string table per language. |
| Verified | Check run: `ok: 3553 cards` in all five languages; `--dialog --check`: `ok: 802 DLG strings (158 empty, …)` in all five (English: 402 with `$C` escapes, 84 with `%s`/`%d`, 59,232 bytes). Names, descriptions, passcodes, id map, sort and alphabet table are `verified` in `re/formats.csv` (cross-checked against ygotfToolkit, `docs/PRIOR_ART.md`). Tests: `tools/tests/test_cardinfo.py`. |
| Gaps | `CARD_Prop` word 1 bits 22–24 unknown; who sets genre bits 0 and 38 at run time; descriptions longer than the 0x77a-byte buffer. None blocks the port. |

### 3a. Booster packs and forbidden/limited list

| Item | Value |
| --- | --- |
| Source | Packs: table at `0x202c8` in `<USRDIR>/gmodule/rel_shop.prx` (48 × 12 bytes, four rarity tiers). Limit list: `BOOT.BIN` `0x08878cb8`, 114 × `(u16 id, u16 status)`. |
| Format docs | `docs/formats/packs.md` (table, purchase flow, draw procedure), `docs/formats/limit-list.md`, shop rules in `docs/subsystems/world.md`, save pack records in `docs/formats/save.md` |
| Tool / command | `python3 -I tools/tables.py packs <USRDIR>/gmodule/rel_shop.prx [-o …] [--check] [--cardinfo <cardinfo_eng.ehp>]`; `python3 -I tools/tables.py odds <USRDIR>/gmodule/rel_shop.prx [-o …] [--check] [--cardinfo …]` (per-pack odds; `--check` replays the draw); `python3 -I tools/tables.py limits <SYSDIR>/BOOT.BIN [-o …] [--check] [--cardinfo …]` |
| Port output | CSV/JSON: pack → tier → card ids, cards per pack, unit price, clerk voice; per-pack odds; card id → status (0 forbidden, 1 limited, 2 semi-limited). The draw itself is code: port `draw_pack` from `tools/tables.py` (rarity box of 20 = 14/4/2 per pack kind, kept in the save; rare slot with tier fallback; commons without duplicates; packs 15/47 favour unowned cards). |
| Verified | Check run: `ok: 48 packs, 9177 entries`; `ok: 48 packs, rarity box 14/4/2 per 20, 245 cards per round of packs, draws replayed`; `ok: 114 restricted cards`. `pack_table`, `pack_draw` and `limit_list` `documented`. Tests: `tools/tests/test_tables.py`. |
| Gaps | Pack names/artwork mapping (`shop/all_<l>.ehp` `strTbl`, `pack_explain_str`); the unlock rules (`shop_unlock_rules`, `named`); a PPSSPP trace of one purchase (DP, rarity entry, counters). Not blocking: the draw procedure is documented. |

### 3b. Fusion and ritual recipes

| Item | Value |
| --- | --- |
| Source | `rel_duel_eng.prx`: fusion recipes at `0x09debe98` (138 × 8 bytes), ritual table at `0x09dec4d4` (u32 records, 0-terminated); 4 Fusions hard-coded. |
| Format docs | `docs/formats/fusion-recipes.md`, `docs/subsystems/summon.md` |
| Tool / command | `python3 -I tools/fusion.py <USRDIR>/gmodule/rel_duel_eng.prx recipes\|rituals [--cardinfo …] [-o out.csv]`; `--check` |
| Port output | CSV/JSON: fusion id → material codes (card id, or one of 14 generic codes below `0x24`); ritual monster → spell → Level total. |
| Verified | Check run: 138 recipes (119 two-material, 19 three-material), 31 ritual records, 142 of 144 Fusion monsters have a recipe, `ok`. Tests: `tools/tests/test_fusion.py`. |
| Gaps | Tie rules of the slot matcher `0x09cb97c4`; the data between `0x09dec2e8` and `0x09dec4d4`. |

## 4. Card art (`card/*.cip`)

| Item | Value |
| --- | --- |
| Source | `<USRDIR>/card/`: `cardh_<l>.cip` (CIP, GIM DXT1 128×64 atlas pieces, per language), `cardm_<l>.cip` (CPM, headerless DXT1 64×64 card faces, per language), `card8_a.cip` (CPL, index8 128×128 art), `cardj_a.cip` (CPJ, **masked baseline JPEG 512×512**, the high-resolution art). Indexed directly by card id. |
| Format docs | `docs/formats/cip.md` (directory, slots, image formats, the CPJ unmasking algorithm read from `BOOT.BIN` `0x0883d658`), `docs/formats/gim.md` |
| Tool / command | `python3 -I tools/cip.py list <file.cip> [--check]`; `python3 -I tools/cip.py png <file.cip> <card id> [--art N] [--size WxH] -o extracted/….png`; `python3 -I tools/cip.py jpeg <USRDIR>/card/cardj_a.cip extracted/cardj --boot <SYSDIR>/BOOT.BIN [--ids …] [--limit N] [--full]` |
| Port output | Per card id and artwork number: the unmasked JPEG (`<id>.jpg`, `<id>_<n>.jpg`, cut at EOI) as the master art, and PNG for the small faces/atlas pieces if the port wants the original small renditions. The 160-byte JPEG head is read from the maintainer's `BOOT.BIN` at run time; no game bytes are in the repository. |
| Verified | Check run: all 12 files `OK` (`cardj_a`: 3,553 ids, 3,602 images of 80 sectors; the others 3,560 ids, 3,609 images); `jpeg --ids 4007` wrote the card's images. `cip_cardj` is `verified`: output byte-identical to ygotfToolkit for all 3,602 slots. Tests: `tools/tests/test_cip.py`. |
| Gaps | `png` decodes one card per call (no batch mode for `cardh`/`cardm`/`card8`); placement of the `cardh` atlas pieces on screen; which screens use which file; `cis_all.gim` thumbnail grid ↔ `fileTbl.dat` mapping (medium hypothesis). The port can build every rendition from the 512×512 JPEG, so none of these blocks it. |

## 5. Card effects data

Card effects are **code, not data**: native handlers in `gmodule/rel_duel_eng.prx`, reached through id-sorted handler tables, with per-card numbers in card-id compare chains (`docs/subsystems/duel_effects.md`). There is no script to extract. What the extractors produce is a per-card **specification** that the port's re-implementation is written and tested against.

| Item | Value |
| --- | --- |
| Source | `<USRDIR>/gmodule/rel_duel_eng.prx` (runtime base `0x09be1400`; file offset = address − base + `0x54`), `<SYSDIR>/BOOT.BIN` (card-group predicates, archetype lists), `<USRDIR>/gmodule/rel_duel_draw.prx` (presentation-side card tests), `cardinfo_eng.ehp` (identity), `re/functions.csv` (handler names). |
| Format docs | `docs/formats/effect-tables.md` (four 24-byte tables, five slots, 8-byte lists), `docs/formats/card-effect-spec.md` (output schema 3), `docs/formats/card-refs.md`, `docs/formats/search-filters.md`, `docs/subsystems/effect-classification.md`, `docs/subsystems/stat-modifiers.md`, `docs/subsystems/effect-helpers-*.md`, `docs/subsystems/chain.md`, `summon.md`, `battle.md`, `duel-phases.md` |
| Tool / command | Joined spec: `python3 -I tools/card_effects.py <USRDIR>/gmodule/rel_duel_eng.prx <USRDIR>/duelsys/cardinfo_eng.ehp --boot <SYSDIR>/BOOT.BIN --draw <USRDIR>/gmodule/rel_duel_draw.prx -o extracted/card_effects` (and `--check`). Components, each with `-o DIR` and `--check`: `effect_classify.py`, `effect_params.py`, `stat_mods.py`, `search_filters.py` (`list -o file.csv`), `card_refs.py` (`list -o DIR`, `describe`), `family_split.py`, `fusion.py`, `ai_tables.py`. |
| Port output | `card_effects.jsonl` (one JSON object per card id: identity, effect records and slot handlers with categories, target-filter words, draw counts, compare-chain values, ATK/DEF modifiers, fusion/ritual, tokens, search filters, engine references, refined per-card categories, each with source and confidence) and `card_effects.csv` (one summary row per card). Plus the rule documents above for the engine itself. |
| Verified | Check run, all `ok`: `effect_classify` 2,600 records, resolve slot categorised for 2,549 (98.0 %; 99.5 % of records with a resolve handler); `effect_params`, `stat_mods`, `fusion` ok; `card_refs` best descriptive confidence H 154 / M 124 / L 34 cards; `search_filters` 686 records (11 cut by limits, 10 ids without a cardinfo record); `family_split` sample precision 83 % → 96 % on 48 records; `card_effects` 915 resolve slots examined, 394 refined, `ok`. Formats `effect_tables`, `effect_lists`, `card_effect_spec`, `card_refs`, `search_filter_word`, `family_split` are `documented`; `chain_link` and `chain_state` `verified` in PPSSPP. Tests: `test_card_effects`, `test_effect_classify`, `test_effect_params`, `test_stat_mods`, `test_search_filters`, `test_card_refs`, `test_family_split`. |
| Gaps | The spec says *which* engine behaviour a card uses and with which numbers, not a complete executable description: the 600 single-use AI handlers are named by family only (their constants are not extracted) and many single-use resolve handlers are unnamed; 244 of 306 compare chains are unresolved; the conditional branches behind `engine_only` cards (273 released effect cards with no table record) are tagged, not decoded; the run-time rule that picks among several records of one card is open. **Blocking**: this is the largest remaining piece of the port; it is a reverse-engineering task per effect family, not an extractor task. |

## 6. Decks

| Item | Value |
| --- | --- |
| Source | 661 recipes `RCP000.ydc`–`RCP660.ydc` and `recipe_name_<l>.bin` in the EHP embedded in `BOOT.BIN` at `0x088d77e0`; owner, level and variant tables in `BOOT.BIN` (`0x08915f28`, `0x089143f0`, `0x08916730`); `deck/all_<l>.ehp` (`sameCardTbl.dat`, `fileTbl.dat`, `cis_all.gim`); `deck/tutorial.ehp` (deck-building tutorial). |
| Format docs | `docs/formats/deck.md`, `docs/subsystems/deck.md` |
| Tool / command | `python3 -I tools/decks.py recipes <SYSDIR>/BOOT.BIN [--lang e] [-o …] [--check] [--cardinfo …]`; `decks.py owners <SYSDIR>/BOOT.BIN [--story <USRDIR>/script/story_scr_b.ehp] [-o owners.json] [--check]` (owner, evidence, confidence and game use of every recipe 0–660, rules in `deck.md`); `decks.py samecard <USRDIR>/deck/all_e.ehp`; `decks.py tutorial <USRDIR>/deck/tutorial.ehp`; readable tutorial listing: `python3 -I tools/tutorial.py <USRDIR>/deck/tutorial.ehp` |
| Port output | JSON per recipe: main/extra/side card ids, name per language, owner character and variant; alternative-artwork table; tutorial script as instruction list. |
| Verified | Check run: `ok: 661 recipes (27078 main, 926 extra, 65 side cards), 126 owners covering 462 recipes, 6 name tables`; `ok: 49 alternative artworks for 38 cards; fileTbl has 3502 slots`; `ok: 5 scripts, 732 instructions, 224 string references`; `owners --check` with `--story`: `ok: 661 of 661 recipes have an owner: 462 from the owner table (high); 199 unnamed (462-660) by draft block: 129 decks, 122 resembling a deck of the same owner (medium 111, low 18), 70 placeholders (low); no unnamed recipe is loaded by the game; set-up codes 462-466; 93 story duel opponents, all in the owner table`. `ydc_recipe` is `verified` (round-trip). Tests: `tools/tests/test_decks.py`. |
| Gaps | Recipes 462–660 are never loaded (set-up codes 462–466, draft blocks of owners 87–126: owners from layout and similarity, medium/low), so the story's opponents only need recipes 0–461 through the owner table. Still open: the `stage` argument and mode of the owner-variant selection, the per-recipe card list's purpose, and the recipe level beyond the underground draw; low priority. |

## 7. GIM textures

| Item | Value |
| --- | --- |
| Source | 14,098 GIM files: 12,374 members of top-level archives (10,117 in loose `.ehp`, 2,257 in the gzip-wrapped `field/bustup/*.ehp.gz`), 300 in nested archives, 34 in `BOOT.BIN` archives, 1,390 loose `.gim` (`field/`, `duel/`, `help/`, `minigame/`, `field/sdchr/`, `field/faceicon/`). |
| Format docs | `docs/formats/gim.md` |
| Tool / command | `python3 -I tools/gim.py check <PSP_GAME>` (decode every plane, format histogram); `gim.py info <file or dir> [member]`; `gim.py png <file.gim \| archive> [member] [--frame N] [--clut N] -o extracted/gim/<name>.png`; batch: `gim.py batch <USRDIR> <SYSDIR>/BOOT.BIN -o extracted/gim [--first]`. Archives may be `.ehp`, `.ehp.gz` or an ELF with embedded archives; nested members as `inner.ehp/name.gim`. The shared decoders stay in `tools/cip.py` (also used by `ehf.py render`, `tgm.py obj`). |
| Port output | PNG RGBA8 per image plane: `<path>/<stem>.png`, with `_f<frame>` for the 5 nine-frame images and `_c<level>` for the 201 images with several palette levels (alternative palettes, for example hair colours). |
| Verified | Check run: `gim 14098, ok 14098, planes decoded 16050`, no index past its palette, `OK` (about one minute). Histogram: index8 swizzled 8,590 (palettes of 256, 160 or 15 entries), index4 swizzled 4,843, index4 linear 405, index8 linear 171, RGBA8888 swizzled 66, DXT1 23; every palette RGBA8888. Samples of each format inspected visually. `gim` is `reimplemented`. Tests: `tools/tests/test_gim.py` (synthetic GIMs: swizzle, nibble order, palette levels, frames, DXT1, errors, CLI). |
| Gaps | Which palette level and frame a screen selects is code (per scene module). Order of planes when an image has both several levels and several frames is assumed frame-major (no such file on the disc). Not blocking. |

## 8. EHF 2D layouts (UI timelines) and TMF

| Item | Value |
| --- | --- |
| Source | 1,225 `.ehf` (1,029 in loose archives, 155 in `field/bustup/*.ehp.gz`, 40 in nested `minigame/` archives, `loading.ehf` in `BOOT.BIN`) with 689 `.tmf`; textures are `<name>.gim` in the same archive. Menus, title, duel HUD, results, field UI, bust-ups (`field/bustup/*.ehp.gz` hold `body.ehf` + body textures). |
| Format docs | `docs/formats/ehf.md`, `docs/subsystems/ui.md` |
| Tool / command | `python3 -I tools/ehf.py list <archives…>`; `ehf.py inspect <archive> <member>`; `ehf.py check <USRDIR> <SYSDIR>/BOOT.BIN`; `ehf.py render <archive> <member> [--frame N] [--background] -o extracted/ehf/….png`; JSON export: `ehf.py json <archive> --member <name.ehf> -o <out>.json`, batch `ehf.py json <USRDIR> <SYSDIR>/BOOT.BIN -o <outdir> [--no-frames] [--compact]` (output outside the repository or under `extracted/`), `ehf.py json --check <USRDIR> <SYSDIR>/BOOT.BIN` (convert everything in memory, census of unknown fields) |
| Port output | One JSON document per layout (schema version 1 in `docs/formats/ehf.md`, "JSON export"): stage size and background, main timeline of place/remove records with depths and clip depths, shapes as raw primitives (colour, texture slot, UV and position vertices, the six display-list words), nested clips with their timelines, matrix and colour-transform keyframe tracks as stored (base, steps, quantised keys), texture slots with the `.tmf` flags and the GIM member path that `gim.py png` takes, every unknown field with its offset and raw value, unclaimed byte ranges, and optionally the evaluated per-frame draw lists (matrix, colour multiply/add per shape). Textures come from `gim.py batch` (§7). Frame labels do not exist in the format. |
| Verified | Check run: `ok 1225` of 1,225 `.ehf`, 689 `.tmf` (7 with a length that differs from the slot count, one note on `umd_replace/basic.ehp/umd_circle01.ehf`), 7,881 shapes, 15,390 primitives, 20,889 tracks. Renders of `loading.ehf`, the title screen and several menus look correct. JSON check run: 1,225 of 1,225 converted, 0 failures, 8,234 texture references resolved (each also resolved through `ehp.find_leaf` to the same bytes), 175,541 frames evaluated; batch output 233 MB compact (27 MB with `--no-frames`). Archive counts were checked for duplicates: the six `BOOT.BIN` archives hold no nested archive, and `ehf.archive_entries` now uses `ehp.embedded_archives` so a nested one could not be counted twice. `ehf` is `reimplemented`, `tmf` `documented`. Tests: `tools/tests/test_ehf.py`. |
| Gaps | Unknown fields that still carry data (census in `ehf.md`): stage field `0x08` (frame step?), track flag bit 5 (2 tracks), the `add` colour channel encoding (5,941 tracks), `.tmf` bit 4 (993 slots); exact key interpolation; line-strip primitives (not drawn). Which scene loads each layout is mapped: `python3 -I tools/scenes.py check <PSP_GAME>` attributes 1,167 of 1,225 layouts to a module and scene (198 by a resolved `container_ehp_find_member` argument, 755 by a name the code addresses, 176 by a name in the module's data, 38 by their archive only); the 58 left are in archives no binary names (probably unused copies, list in `ui.md`). `scenes.py map <PSP_GAME> -o <json>` writes the per-scene archives, members and referencing functions. Still open: how a scene plays a layout (frame stepping, looping, which clip a menu shows when). Blocking for the UI (playback code, not data). |

## 9. TGM models (characters, cut-ins, props, maps)

| Item | Value |
| --- | --- |
| Source | EHP members: 585 `.tms` (TGMS mesh), 453 `.tmt` + 8,701 `.tmt.gz` + 88 `.vtmt.gz` (TGMT node animation), 126 `.tma` (TGMA texture animation). Mostly `duel/cutin_*.ehp` (one character mesh and about 48 animations + 48 `-etc` camera files per character), `duel/basic*.ehp` (coins, dice, card and field pieces), `field/map/bg_*.ehp` (maps), `field/always*.ehp` (field UI), `duel/bg/fmagic*.ehp` (§10), `shop/`, `database/`, `minigame/`. Survey per variant in `tgm.md`. There are no 3D monster models (`duel/zakov*.ehp` hold voice tables only). |
| Format docs | `docs/formats/tgm.md`, `docs/subsystems/field_3d.md` |
| Tool / command | `python3 -I tools/tgm.py list <paths…>`; `tgm.py inspect <archive> <member>` (nested: `outer.ehp:inner`); `tgm.py check <USRDIR> [-v]`; `tgm.py obj <archive> <member.tms> [--tmt member] [--frame F] -o extracted/tgm/<name>`; glTF: `tgm.py gltf <archive> --member <name.tms> [--tmt member]… [--all-tmt] [--fps F] -o extracted/tgm/<name>`, `tgm.py gltf --check <USRDIR>` (convert and validate every model and animation in memory, census of unknown fields; writes nothing) |
| Port output | glTF 2.0 per model (`.gltf` + `.bin` + PNG per GIM): triangle-list meshes (positions, normals, UVs, colours, joints/weights), materials (layer 0 as PBR, `KHR_texture_transform`, `KHR_materials_unlit`), one node per bone with a skin whose inverse bind matrices are the TGMS offset matrices, node animations (translation/scale as exact `CUBICSPLINE` conversions of the Bézier tracks, rotation `LINEAR` = the game's slerp) and the `-etc` camera. Side file `<stem>.tgm.json` (`tf3-tgm-scene` v1): raw tracks, the decoded scene block (lens, fog, ambient, lights, visibility groups), TGMA tracks per layer, full material render state, unknown fields. OBJ+MTL remains for a static pose. |
| Verified | Check run: `total 9953 failing: 0` (TGMA 126, TGMS 585, TGMT 453, TGMT gz 8,789); posed skinned meshes fall inside their header bounding box at frame 0 for 162 of 196. glTF check (`tgm.py gltf --check`, 4 min): 585 models converted and validated with every paired animation, every other TGMT/TGMA converted on its own, `failing: 0`, largest deviation of the glTF curves from the game sampler 2.2e-5. Sampling, slerp, s16 quaternion scale, skinning and TGMA application read in `BOOT.BIN` (`field_3d.md`). Rendered headless from the glTF (backdrop `fmagic3720`, cut-in `abdos01`, pack, album): coherent, textures upright. Format rows `tgm_tms`, `tgm_tmt`, `tgm_tma` are `reimplemented`, `tgm_etc_scene` `documented`. Tests: `tools/tests/test_tgm.py`, `tools/tests/test_tgm_gltf.py`. |
| Gaps | Frame rate of playback (the exporter assumes 30 fps); layer texture-map types 1/2 (an overlay pass on 143 materials); 84-track `-etc` tracks 13–19 and 42-track tracks 4–9; light direction convention; how the cut-in visibility mask reaches the draw; `.vtmt` role; 828 textures with no same-archive `.gim`; texture bytes `+0x08/+0x09`. Not blocking for meshes, skeletons and animations; the frame rate and the overlay pass are needed for a faithful look. |

## 10. Field-spell 3D backdrops (`duel/bg/`)

New observation for this document (2026-10-30, archive listings only; no code read): the animated 3D field-spell backdrops are the **55 archives `duel/bg/fmagic<id>.ehp`**. 53 names carry a card id (3720–7916), plus `fmagic0000.ehp` and `fmagic05.ehp` (presumably the default field and one special case; low confidence). Of the 53 ids, 52 are Spell cards in `cardinfo` (51 with the Field icon, one with icon 0) and one has no record. Each archive is a small scene: one `duel-bg-fmagic<id>-base.tms`, its `-base.tmt` and `-base-etc.tmt` (node and camera/scene tracks), a `.tma` texture animation, GIM textures and a `filelist-ptrs.txt` bundle (55 `.tms`, 55 `.tma`, 109 `.tmt`, 377 `.gim` in total). Example: `fmagic3720` exports to an 8,230-vertex OBJ with 10 textures, or to glTF (18 bones, 4,406 triangles, 301-frame animation with the camera; the 84-track `-etc` file also holds fog, ambient and four lights).

| Item | Value |
| --- | --- |
| Source | `<USRDIR>/duel/bg/fmagic<id>.ehp` |
| Format docs | `docs/formats/tgm.md`, `docs/formats/gim.md`, `docs/formats/ehp.md` (no dedicated document yet) |
| Tool / command | `python3 -I tools/tgm.py list <USRDIR>/duel/bg/fmagic<id>.ehp`; `python3 -I tools/tgm.py gltf <USRDIR>/duel/bg/fmagic<id>.ehp --member duel-bg-fmagic<id>-base.tms -o extracted/tgm/fmagic<id>` (pairs `-base.tmt`, `-base-etc.tmt`, `-base.tma` automatically); `tgm.py obj …` for a static pose |
| Port output | The glTF scene of §9 (mesh, skeleton, animation, camera) plus the side file's scene block (fog, ambient, four lights, TGMA UV/alpha tracks) and the card id → backdrop mapping (the file name). |
| Verified | Every member passes `tgm.py check` and `tgm.py gltf --check`; `fmagic3720` rendered from the exported glTF through its own camera, posed box equal to the header box over all 301 frames. Not yet seen in PPSSPP. |
| Gaps | Which code loads `fmagic<id>` and what selects `0000`/`05`; whether the backdrop loops (the loop flag is set by the caller); the frame rate. The data side is exportable. |

## 11. Free-roam maps and field assets

| Item | Value |
| --- | --- |
| Source | `field/map/bg_NN_MM.ehp` (31 maps: TGMS/TGMT/TGMA, GIM, one `.hmp` walk grid), `field/big_map/world_<period>.ehp` (island map, five lighting periods), `field/always*.ehp` (field UI per region/language, `field_strtbl*.bin`), `field/sdchr/*.gim` (172 loose character sprites), `field/faceicon/*.gim` (87), `field/bustup/*.ehp.gz` (78 bust-ups: EHF + GIM), `field/event/<l>/`, `field/mail/chr02.ehp`, `field/for_bread.ehp`. |
| Format docs | `docs/formats/hmp.md`, `docs/formats/field-tables.md`, `docs/formats/field-maps.md`, `docs/subsystems/world.md`; models and layouts per §7–§9 |
| Tool / command | `python3 -I tools/world.py hmp <USRDIR>/field/map --check`; `world.py hmp <USRDIR>/field/map/bg_NN_MM.ehp --grid`; `python3 -I tools/world.py locations <USRDIR> -o extracted/world/maps [--names]` (one JSON per map); models with `tgm.py`, textures with `gim.py`, island layouts with `ehf.py` |
| Port output | Per map (`map_MM.json`): archive, mesh members with their masks, animations and resolved GIM textures, door meshes, lighting and sky gradient per light period, walk grid (columns, rows, origin, 0.5-unit cells as `#`/`.` rows, vertex heights), exits per location, doors, door cells, walk overrides, special cells, arrival rules, NPC spots and fixed positions, island area. Scene geometry itself via `tgm.py` (§9); sprites and icons as PNG (§7). |
| Verified | Check runs: 31 grids `failing: 0`; `world.py tables --check` `failing: 0` (801/801 mesh textures resolve; arrival, spot and fixed cells walkable except one spot). Floor height rule implemented (`WalkGrid.floor_height`). `hmp` and `field_maps` `documented`. Tests: `tools/tests/test_world.py` (synthetic). Not yet seen in PPSSPP. |
| Gaps | Which bm_parts.gim region and EHF layout each island area uses; what loads maps 37/38; scripted placements behind cells 10000/10001; `field/event/` and `field/mail/` contents not inspected. Sprites and icons convert with `gim.py batch` (§7). |

## 12. World and field tables (in code)

| Item | Value |
| --- | --- |
| Source | `rel_field.prx` (map id → archive/mesh tables, door table `+0x25334`, island-map areas, field request table `+0x2df0c`), `rel_story.prx` (character table `+0x2245c`, NPC spot table `+0x2092c`, location selector and exit cells `+0x1f968`/`+0x1fb84`, calendar tables, partner chapter events `+0x2a10c`), `BOOT.BIN` character table `0x088aa510`. |
| Format docs | `docs/formats/field-tables.md`, `docs/formats/chapter-table.md`, `docs/subsystems/world.md` |
| Tool / command | `python3 -I tools/world.py chars <USRDIR>/gmodule/rel_story.prx [--check]`; `python3 -I tools/world.py spots <USRDIR>/gmodule/rel_story.prx`; `python3 -I tools/world.py tables <USRDIR> [--check] [--table NAME] -o extracted/world/tables.json`; `python3 -I tools/world.py chapters <USRDIR> [--check] -o extracted/world/chapters.json` |
| Port output | JSON (`tables`): maps (archive, meshes, debug name, place-name index, location, island area, lighting), light-mode colours, sky gradients, location → map, doors, door cells, walk overrides, special and marker-hidden cells, exit selector and groups, arrival rules, island areas/positions/cones/archives, NPC spots, fixed NPC positions, ambient sounds. JSON (`chapters`): the 64 chapter rows (header, 4 stages × 4 steps with location, record key and trigger kind), the points caps per stage, and per `BOOT.BIN` character the row and the stage-4 ending key the game would use. The progression rules (cap gate, daily/location steps, duel follow-up, ending) are specified in `chapter-table.md` and mirrored by `world.chapter_event_on_map_entry`. Characters and calendar rules as before. |
| Verified | Check run: `world.py chars --check` `failing: 0`; `spots` lists spots per location; `world.py tables <USRDIR> --check` `failing: 0` (32 maps, 22 doors, 39 exit groups, 29 selector records, 12 island areas; 446/513 exit cells walkable, the rest unreachable); `world.py chapters <USRDIR> --check` `failing: 0` (every key exists in `story_scr_b.ehp`, every location is a story location, every step-2 record opens on its location, stages 1–3 of each row advance the stage, every ending holds `advance_counter` + `finish_partner_story`; 169 of 174 character rows resolve to a row). Calendar, gift points, DP and the weekly pairing were confirmed in PPSSPP (`docs/verification/results/2026-10-27-sessionC.md`); `story_calendar` is `verified`. |
| Gaps | The map, door, exit, island and fixed-spot tables now have JSON output (`tables`, `locations`); the exit selector's conditions are all zero on the disc, so their semantics are read from code only. The partner chapter table is decoded (static; not traced in PPSSPP). Still open: what follows the staff roll; item counters and several field requests (`world.md`); PPSSPP checks of doors, arrival and the island cursor. |

## 13. Story, dialogue and event scripts

| Item | Value |
| --- | --- |
| Source | `<USRDIR>/script/story_scr_<l>.ehp` (`EveI/EveL`, `SysMsgI/SysMsgL` text per language) and `story_scr_b.ehp` (`EveB.bin` bytecode, `EveBI.bin` index), interpreted by `rel_story.prx`. |
| Format docs | `docs/formats/story.md` (text tables, markup, bytecode records, all 78 opcodes in use) |
| Tool / command | `python3 -I tools/story.py text <USRDIR>/script/story_scr_<l>.ehp [-o lines.csv] [--check]`; `python3 -I tools/story.py events <USRDIR>/script/story_scr_b.ehp --text <USRDIR>/script/story_scr_e.ehp [-o events.csv \| --list] [--record N] [--check]` |
| Port output | Text: CSV/JSON of lines per language (markup kept: `《PLAYER》`, `《Cnnn_k》`, `$M`/`$C`). Events: one row per instruction with symbolic opcode names and named arguments, or a readable disassembly; the port's own event VM consumes the instruction list. |
| Verified | Check run: all five languages `Eve 11976, SysMsg 21 lines`; events `ok: 7468 records, 39095 instructions, 11976 text references`. `story_text` is `verified` (59,985 lines identical to ygotfToolkit); `story_bytecode` `reimplemented`. Tests: `tools/tests/test_story.py`. |
| Gaps | Every opcode in use is named (2026-10-30: `set_time_slot`, `hud_marker`, `finish_partner_story`, `preload_portrait`, `series_win`, `series_loss`, `bgm_stop`, `npc_deck`, `npc_remark`, plus `duel_target_*`); PPSSPP confirmation of `hud_marker` targets and of story state 46; most of the 33 field requests on the field side; where `《…》` placeholders are expanded; the driver that picks records. Not blocking: the VM can be built from `story.md`. |

## 14. Tutorials

| Item | Value |
| --- | --- |
| Source | `d_tutorial/tutorial.ehp`: 50 `.ydq` duel setups (Shift-JIS INI text), 17 `tuto_cmd_NN.bin` scripts, `tuto_text_<l>.bin` (read by `rel_tutorial`). `deck/tutorial.ehp`: deck-building tutorial (§6). `tutorial/tutorial_all.ehp` and `tutorial/tutorial_<l>.ehp`: a **second, undocumented set** (`NN_field_set.txt` and `field_reset_NN.txt` in the same `[DUEL…]` text form as `.ydq`, `NN_duel_command.bin`, `NN_message_res.bin`, GIM). |
| Format docs | `docs/formats/tutorial.md`, `docs/formats/deck.md` |
| Tool / command | `python3 -I tools/tutorial.py <USRDIR>/d_tutorial/tutorial.ehp <USRDIR>/deck/tutorial.ehp --check [--notes] [--cardinfo …]`; listing: `tutorial.py <archive> [--only cmd_03] [--lang e] [-o …]` |
| Port output | JSON per lesson: duel setup (both sides' cards per zone, LP, options), script instructions, text per language. |
| Verified | Check run: `ok: 50 duel setups, 17 scripts, 6 text tables of 878 lines; 878 text references to 878 lines (8 notes)`; deck tutorial `ok, 732 instructions`. `ydq`, `tuto_cmd`, `tuto_text` `documented`. Tests: `tools/tests/test_tutorial.py`. |
| Gaps | Duel-engine command codes used by the scripts only partly understood; draw order of the deck list. The `tutorial/` directory is not handled (`tutorial.py` finds 0 members in it) and no module string names it (`rel_tutorial` names only `tutorial/tutorial.ehp` under its own root); it may be unused (low confidence). |

## 15. UI and system string tables

| Item | Value |
| --- | --- |
| Source | `strTbl*.bin`, `*_strtbl_<l>.bin`, `*_msg_<l>.bin`, `ddstrtbl_<l>.bin`, `option_msg_<l>.bin`, `help_strtbl_*`, `pack_explain_str_<l>.bin`, `mini_result_<l>.bin`, `chr_wordstbl_<l>.bin`, `chr_name_<l>.bin` (BOOT.BIN archive) across `database/`, `deck/`, `duel/`, `field/`, `labo/`, `minigame/`, `shop/`, `title_menu/`. More than a thousand `.bin` members, most of them per-language copies (the census in `ehp.md` counts 2,225 `.bin` members of several formats). |
| Format docs | `docs/formats/string-tables.md` (two layouts: headed `strtbl` with an end offset, and the `offset_list` of `pack_*_str`; the census of every `.bin`); field tables in `field-tables.md`; captions in `sound.md`. |
| Tool / command | `python3 -I tools/strtbl.py check <PSP_GAME>`; `strtbl.py show <archive or .bin> [member] [-o extracted/strtbl/<name>.tsv]`; `strtbl.py dump <USRDIR> <SYSDIR>/BOOT.BIN -o extracted/strtbl` (one JSON per table: source, layout, strings). |
| Port output | JSON per table and language: index → UTF-16 string, markup kept (`%s`, `%d`, line breaks). |
| Verified | Check run: `.bin files 2273: string tables 1851 (191593 strings, 1846 rebuilt byte for byte), text in other layouts 26, other data 396`, `OK` (1,790 headed tables with end offset, 25 without, 36 offset lists; the five that do not rebuild are `DICT_<l>.bin` with their 4-byte gap). No text-like `.bin` is left unparsed. `strtbl` and `strtbl_offset_list` are `reimplemented`. Tests: `tools/tests/test_strtbl.py`. |
| Gaps | Scene attribution done (`tools/scenes.py`, `ui.md` "Scene map"): 1,799 of 1,851 tables attributed to a module and scene; the 52 left are in unreferenced archives (`field/always*_lang`, `tutorial/tutorial_<l>.ehp`, `database/gallery.ehp`). Of the 854 calls of the string accessor (`card_db_get_dictionary_word`, after following wrappers to their callers), 462 name their table, 517 have a constant index, 332 both. The rest read a table pointer chosen at runtime (title selector, minigame result helper, duel HUD `ddstrtbl` pair): PPSSPP breakpoints listed in `ui.md`. Not blocking: the port can load each scene's tables whole. |

## 16. Sound: music, effects and voices

| Item | Value |
| --- | --- |
| Source | `<USRDIR>/snd/psp_snddat.bin`: 728 `SP` banks chained without a directory (banks 0–47 music, 48–711 voices, 712–727 effects, medium confidence by content). Voice routing: `BOOT.BIN` character and sound-id tables, `rel_charalist.prx` voice-test table, `*_voiceidchgtbl.bin` and `chr_wordstbl_<l>.bin` in `database/charalist.ehp` and `duel/cutin_*.ehp`. |
| Format docs | `docs/formats/sound.md` |
| Tool / command | `python3 -I tools/sound.py <USRDIR>/snd/psp_snddat.bin [--bank N] [--check]`; export: `sound.py <…> --export BANK:CUE -o extracted/snd/<file>`; batch conversion (needs FFmpeg with the `atrac3`/`atrac3p` decoders, on PATH or given with `--ffmpeg`): `python3 -I tools/audio_convert.py <USRDIR>/snd/psp_snddat.bin -o <scratch>/snd [--format wav\|ogg\|flac] [--bank N …]`, `audio_convert.py <…> --check [--jobs N]` (decodes everything, writes nothing), `audio_convert.py <…> --survey` (codec census, no decoding); voices: `python3 -I tools/voices.py <PSP_GAME> --check`, `voices.py <PSP_GAME> [--language e] -o extracted/voices.csv` |
| Port output | Install-time conversion from the user's own disc: one 16-bit PCM WAV (or OGG Vorbis q6 / FLAC) per distinct stream, named `snd_<bank>_<first cue>[_<layer>]`, trimmed to the `fact` sample count, plus `snd_<bank>.json` per bank: per cue volume, pan, flags, duration, envelope records (ADPCM), and per stream codec, channels, rate, bitrate, sample count, file and loop `{start, end}` in output samples (end inclusive). OGG files also carry `LOOPSTART`/`LOOPLENGTH` tags. Voice table CSV: (character, voice id) → bank, cue, caption. |
| Verified | Check run: `ok: 728 banks, 30779 cues, 18608 distinct RIFF waves, 107 ADPCM cues`; `voices --check` `ok: 97 voice tables, 728 banks, 134 voice-test items` (two notes); `audio_convert.py --check --jobs 12` with FFmpeg 7.1.1 (about 3 min): `ok: 728 banks, 18716 streams decoded: ATRAC3 100 (2.6 min), ATRAC3plus 18508 (478.2 min), PS-ADPCM 108 (0.7 min)`. Every wave decodes to exactly (frame count × frame size) samples, every trimmed stream matches the duration of each cue that uses it within 2 ms, every loop lies inside its stream. `snd_bank` and `snd_at3_wave` `reimplemented`. Tests: `tools/tests/test_sound.py`, `tools/tests/test_voices.py`, `tools/tests/test_audio_convert.py`. |
| Gaps | ATRAC decoding is delegated to FFmpeg (`atrac3`, `atrac3p`), run on the user's machine at install time; no ATRAC decoder is written for the project. Open: whether the game honours the `smpl` loops of the 11 non-music waves that have one (47 of the 48 music waves have one), cue flags and envelope bytes 8–11, the play call and bank loading, which banks the duel uses for a voice set. Not blocking: every stream converts. |

## 17. PSMF movies

| Item | Value |
| --- | --- |
| Source | `<USRDIR>/movie/*.pmf`: 73 files, 243.1 MiB, 16.9 min (opening, two staff rolls, 68 summon/attack cut-ins, two win scenes). |
| Format docs | `docs/formats/psmf-movies.md`, `docs/subsystems/movies.md` |
| Tool / command | `python3 -I tools/psmf.py <USRDIR>/movie [--check]`; `psmf.py <file.pmf> [--check]` (headers, pack clocks and the audio demux); conversion with FFmpeg: `psmf.py <USRDIR>/movie --convert -o <scratch>/movie [--format mp4\|mkv\|wav]`; `psmf.py <USRDIR>/movie --convert-check` (converts each movie to a temporary MP4, decodes it back with `ffprobe -count_frames`, deletes it) |
| Port output | Install-time conversion from the user's own copy: `<name>.mp4` (the H.264 Main 480×272 29.97 fps stream copied bit for bit; audio demuxed by the tool from private stream 1, decoded from ATRAC3plus by FFmpeg, trimmed to start with the first video frame, encoded as AAC 160 kbit/s), or `<name>.mkv` (same video, FLAC audio), or `<name>.wav` (audio only, 16-bit PCM). Re-encoding to what the 3DS plays (for example 400×240 H.264 Baseline or a 3DS-native format) is a second, port-side step from this file. Plus a JSON list: name, duration, which module plays it. |
| Verified | Check run: `ok: 73 movies, 243.1 MiB, 16.9 min in total; audio: ATRAC3plus 744-byte frames, 2 ch, 44100 Hz, lead 2416 samples`; `--convert-check` with FFmpeg 7.1.1: `ok: 73 movies converted and decoded, 16.9 min of video; largest audio/video length difference 0.083 s, largest video/header difference 0.000 s`. `psmf_movie` and `psmf_audio_stream` are `reimplemented`. Tests: `tools/tests/test_psmf.py`. |
| Gaps | The 3DS playback format; header bytes `+0x10`–`+0x55`; the decoder delay inside the movie audio (the alignment comes from the PTS, see `psmf-movies.md`); what selects the `_a` names; skip behaviour. Not blocking (a "skip movie" path exists by design). |

## 18. AI tables

| Item | Value |
| --- | --- |
| Source | `rel_duel_eng.prx` `0x09dfd2dc`–`0x09e00800`: eleven `(u32 card id, u32 handler)` tables and three u16 card-id lists, lengths fixed in code. |
| Format docs | `docs/formats/ai-tables.md`, `docs/subsystems/ai.md`, `docs/subsystems/ai-helpers.md` |
| Tool / command | `python3 -I tools/ai_tables.py <USRDIR>/gmodule/rel_duel_eng.prx list\|cards\|classes\|handlers [--cardinfo …] [--functions re/functions.csv --functions re/names-duel_eng.csv] [-o out.csv]`; `--check [--functions …]` (with names: every handler named, per-card names match the table users) |
| Port output | CSV/JSON: table key (T1–T3, A–H, R1–R3) → ordered card ids → handler, family and behaviour class (`handlers`: one row per card and handler). Order is priority. The handler logic is code (re-implemented from `ai-helpers.md` and the family templates of `ai.md`). |
| Verified | Check run: `ok`, 18 card ids without a cardinfo record (cut cards), u16 lists R1 143 / R2 36 / R3 1. `ai_priority_tables` `documented`. Tests: `tools/tests/test_ai_tables.py`. |
| Gaps | The 600 single-use handlers are named by family (`ai_tables.py handlers`), not decoded one by one; the plan comparison is read statically (`ai.md`, "Decision pipeline") but not traced; the two large evaluators are only skimmed. Partly blocking for faithful CPU behaviour; a port can start from the 77 classified shared handlers (63.6 % of entries) and the family templates. |

## 19. Save data

| Item | Value |
| --- | --- |
| Source | `PSP/SAVEDATA/ULES011830001/DATA0` (131,072-byte game-state copy), written **unencrypted by PPSSPP** with `EncryptSave = False`. Retail saves are encrypted by the PSP save layer and are not decrypted (`CLAUDE.md`). |
| Format docs | `docs/formats/save.md`, save fields in `docs/subsystems/world.md` |
| Tool / command | `python3 -I tools/save.py decks <DATA0> [--cardinfo …] [-o …]`; `save.py collection <DATA0> [-o …]`; `save.py <DATA0> --check` |
| Port output | An importer from a plaintext `DATA0` into the port's own save: decks (127 slots), card collection (copies, flags, limit status), player profile and DP, story block. The port's save format itself is a port decision. |
| Verified | Check run (save `extracted/saves/v1`): `ok: 126 non-empty deck slots, 54 cards owned`. DP, calendar and partner word confirmed in PPSSPP (session C). `save_data`, `save_decks`, `save_collection`, `save_player_profile` `documented`. Tests: `tools/tests/test_save.py`. |
| Gaps | Character records, pack records, duel records, much of the story block are `named` only; `save.py` exports only decks and collection. Not blocking if the port starts new games; blocking for save import. |

## 20. Minigames and other screens

| Item | Value |
| --- | --- |
| Source | `minigame/<game>/` (blackjack, connection, dodge, quiz, result, reversi, throw, underground: EHP with nested archives, EHF, GIM, string tables, one `.hmp`), `labo/`, `database/`, `title/`, `title_menu/`, `menu/tga.ehp`, `main/msd_*.ehp`, `help/*.gim`, `umd_replace/`. |
| Format docs | Containers and leaf formats as above (`ehp.md`, `ehf.md`, `gim.md`, `tgm.md`); modules in `docs/subsystems/modules.md` |
| Tool / command | `ehp.py`, `ehf.py check/render`, `tgm.py`, `gim.py` (§7), `strtbl.py` (§15) |
| Port output | As §7–§9 and §15. |
| Verified | All their layouts and models pass `ehf.py check` and `tgm.py check`. |
| Gaps | Game logic of each minigame and the quiz data (`minigame/quiz/data.ehp`) are not analysed. Not in work packages 1–5; low priority. |

## Check run (2026-10-30)

Every command in the "Check run" lines above returned exit code 0 on the reference dump, except as noted here:

- `python3 -I tools/ehp.py --verify` over all archives in one call failed on Windows with "Argument list too long" (shell limit, not a tool fault). Run once per file instead, it reported **609 files, 0 failing** (531 loose `.ehp` and the 78 `field/bustup/*.ehp.gz`; the 20 nested archives are inside them).
- `python3 -I tools/modules.py list <SYSDIR>/BOOT.BIN <USRDIR>/gmodule <USRDIR>/module --check` passed; it identifies `module/libfont.prx` as an encrypted Sony module and does not decrypt it.
- `python3 -I tools/progress.py --check`: `ok`.
- Added with the deck-owner work: `decks.py owners --check` (§6), `cardinfo.py --dialog --check` for all five languages (§3) and `ehp.py <SYSDIR>/BOOT.BIN --check` (§2) pass; their dumps were written to a scratch directory outside the repository.
- All 33 test files under `tools/tests/` pass (`test_gim.py` and `test_strtbl.py` added with the GIM and string-table tools, `test_audio_convert.py` with the audio conversion, `test_scenes.py` with the scene map).
- `python3 -I tools/scenes.py check <PSP_GAME>`: layouts 1,167/1,225 and string tables 1,799/1,851 attributed to a scene, `OK` (about 15 s).
- Audio and movie conversion (FFmpeg 7.1.1): `audio_convert.py --check` and `psmf.py --convert-check` pass (§16, §17); outputs of the trial conversions went to a scratch directory outside the repository.
- `python3 -I tools/gim.py check <PSP_GAME>` and `python3 -I tools/strtbl.py check <PSP_GAME>`: `OK` (§7, §15).
- `python3 -I tools/tables.py odds <USRDIR>/gmodule/rel_shop.prx --check --cardinfo <cardinfo_eng.ehp>` (added with the pack-draw analysis): `ok: 48 packs, rarity box 14/4/2 per 20, 245 cards per round of packs, draws replayed` (§3a); `story.py events --check` still passes with the new opcode names (§13).
- `python3 -I tools/world.py tables <USRDIR> --check` and `world.py locations <USRDIR> -o <dir>` (added with the map tables, §11–§12): `failing: 0`, 32 map files written.

## Coverage

| Asset class | Status | Blocking for the port? | Next step |
| --- | --- | --- | --- |
| Disc layout and file index | complete | no | Optional cross-check with a second ISO extractor. |
| EHP archives and gzip | complete | no | Map the runtime extension-handler table (optional). |
| Card database (`cardinfo`) | complete | no | Close the small field questions (word 1 bits 22–24, run-time genre bits). |
| Packs and limit list | complete (data and draw) | no | Map pack names and art; PPSSPP trace of one purchase. |
| Fusion and ritual recipes | complete | no | PPSSPP check of overlapping-material ties. |
| Card art (`.cip`) | complete | no | Batch mode for `cip.py png` (optional; the JPEG covers the port). |
| Card effects data | partial | **yes** | Continue per effect family: name single-use handlers, resolve the 244 open compare chains, decode `engine_only` branches. |
| Decks | complete | no | `stage`/mode of `deck_select_owner_variant`; trace one story duel set-up in PPSSPP to confirm the set-up codes. |
| GIM textures | complete | no | Map palette levels and frames to the screens that select them (scene code). |
| EHF UI timelines | partial (exporter and scene map complete) | yes (playback code) | JSON exporter and scene attribution (95 % of layouts, `scenes.py`) done; interpolation, `add` channel and `.tmf` bit 4 in PPSSPP; how each scene plays its layouts. |
| TGM models | complete for geometry, skin and animation (glTF) | partly | Playback frame rate; layer texture-map types; unknown `-etc` tracks; `.vtmt`; textures from other archives. |
| Field-spell 3D backdrops | complete for data (glTF + scene block) | partly | Find the loader and the loop/frame-rate settings in `rel_duel_draw`; check one backdrop in PPSSPP. |
| Free-roam maps and field assets | partial (per-map export complete) | partly (scene export via TGM) | Per-map JSON with grid, heights rule, exits, doors and art references done; inspect `field/event/` and `field/mail/`; island-area sprite regions; geometry through the TGM exporter. |
| World and field tables | partial (map/door/exit/island and chapter-table export complete) | no | PPSSPP check of one chapter (field block bytes 0–1), of arrival cells and door locks; what follows the staff roll. |
| Story and event scripts | partial | no | Trace the field requests and the lower-confidence opcodes in PPSSPP. |
| Tutorials | partial | no | Identify whether `tutorial/` is used; decode the remaining engine command codes. |
| UI string tables | partial (tables mapped to scenes) | no | Tool, census and scene map done (97 % of tables, 332 index requests with table and constant index); trace the runtime-selected tables in PPSSPP. |
| Sound and voices | complete for decoding (FFmpeg at install time, PS-ADPCM native, loops in JSON) | no | Cue flags, envelope bytes and the play call (PPSSPP trace); whether the SFX loops are used. |
| PSMF movies | complete for conversion (own audio demux + FFmpeg) | no | Choose the 3DS playback format; the port's installer re-encodes the MP4 to it. |
| AI tables | partial | partly | PPSSPP trace of the plan comparison (checks in `ai.md`); decode the per-card handlers' constants family by family. |
| Save data | partial | no (new games) / yes (import) | Map the remaining regions with differential saves; extend `save.py`. |
| Minigames and other screens | partial | no | Out of work packages 1–5; analyse when the port reaches them. |

## Open questions

- Answered 2026-10-30: ATRAC3/ATRAC3plus are decoded by FFmpeg (`atrac3`, `atrac3p`) on the user's machine at install time (`audio_convert.py`, `psmf.py --convert`); the `smpl` loop points are carried over in the JSON side files and as OGG tags.
- Which video format and resolution the port plays, and therefore what the port-side re-encode of the converted MP4 produces.
- Answered 2026-10-30: the model target is glTF 2.0 (the Bézier tracks convert exactly to `CUBICSPLINE` after splitting at the union of the per-axis key frames) plus the `tf3-tgm-scene` side file for what glTF cannot hold.
- Which code loads `duel/bg/fmagic<id>.ehp` and what `fmagic0000` and `fmagic05` are (the `-etc` tracks are read by `rel_duel_draw` `0x0985b504`, see `field_3d.md`).
- Whether `tutorial/tutorial_all.ehp` and `tutorial/tutorial_<l>.ehp` are used by any module (no file-name string was found in `BOOT.BIN` or `gmodule/`; `scenes.py check` leaves them, with `field/always_lang_<lang>.ehp`, `tutorial/face/`, `umd_replace/` and `database/gallery.ehp`, unattributed).
- Whether the port reads assets from the user's ISO at first run (and converts them) or ships a converter tool; this decides whether the extractors must become a single "convert everything" command.
- Whether `*ptrs.txt` bundles are needed at all once members are addressed by name.
