# Port readiness

Audit of 2026-11-04 against the "Done means" criteria of `CLAUDE.md`: what is finished, what still blocks a 3DS port, and how each blocking item gets settled. It builds on `docs/extractor-spec.md` (per-asset detail), `docs/open-questions-triage.md` (every open question, classified) and `docs/verification/ppsspp-plan.md` (runtime checks).

**Verdict.** Three of the four criteria are met. Work packages 1–5 are documented, the extractors regenerate every asset class the port can take from the disc (one command, run end to end on the reference dump on 2026-11-04), and the effect architecture is documented. The fourth criterion is not met yet: 16 of the 573 open questions still block the port. They form eight tasks (B1–B8 below): three need static reading, four a PPSSPP check (B1's static part is done), one both. None of them is a format or extraction gap. They are rules: event codes, duel conditions, flag bits, progression triggers.

## Done criteria

| Criterion (`CLAUDE.md`) | State | Evidence |
| --- | --- | --- |
| Work packages 1–5 at least `documented` | **Met** | `python3 -I tools/progress.py`: formats 182/182 `documented` (125 `reimplemented`, 31 `verified`); functions 12,269/12,737 `documented` (96.3 %), and 100 % in every WP1–5 group: `container` 54/54, `card_db` 181/181, `deck` 155/155, `save` 248/248, `duel_core` 1,308/1,308, `duel_effects` 2,896/2,896, `tag_duel` 16/16. The 468 functions below the bar are in the AI, UI and SDK groups (WP6+). |
| The extractor specification can regenerate every asset class the port needs | **Met** (with the port-side decisions listed below) | `docs/extractor-spec.md`; `tools/extract_all.py` runs all 51 extraction steps in one command. See "Asset classes". |
| The effect architecture is documented | **Met** | `docs/subsystems/duel_effects.md` (native handlers in `rel_duel_eng`, id-sorted handler tables, compare chains; no script interpreter), `docs/formats/effect-tables.md` (tables, lookup and, since this audit, the per-card **variant rule**), `docs/formats/card-effect-spec.md` (per-card specification, `tools/card_effects.py`), `docs/formats/duel-runtime.md` (timing-event vocabulary, added in this audit). |
| The open-question lists contain nothing blocking the port | **Not met: 16 items in 8 tasks** | `docs/open-questions-triage.md`: 573 items, of which 16 B (blocking), 145 R (resolved), 18 W (fidelity workstream), 394 N (non-blocking). The tasks are listed under "Blocking questions". |

## Asset classes

Every asset class the port needs, with the tool that produces it and the form the port consumes. "Run" is the port-readiness run of 2026-11-04 on the reference dump (`docs/SETUP.md`), output under `extracted/port/` (git-ignored, never committed). Step ids are those of `tools/extract_all.py --list`.

| Asset class | Source on the disc | Step(s) and tool | Port-usable output | Run 2026-11-04 |
| --- | --- | --- | --- | --- |
| Card data: stats, names, descriptions (5 languages) | `duelsys/cardinfo_<lang>.ehp` | `cards_<lang>`: `cardinfo.py` | JSON per language | ok: 3,553 cards × 5 |
| Duel prompts and messages | same, `DLG_*` | `duel_prompts_<lang>`: `cardinfo.py --dialog` | JSON | ok: 802 strings × 5 |
| Card art, master (512 × 512) | `card/cardj_a.cip` (masked JPEG) | `card_art`: `cip.py jpeg` | JPEG per card and artwork | ok: 3,602 images, 296 s |
| Card art, small renditions | `card/cardh_<l>`, `cardm_<l>`, `card8_a` `.cip` | `card_small_*`: `cip.py pngs` (**new**) | PNG per card | ok: `cardm_e` 3,609 PNG in 33 s; `cardh`, `card8` sampled |
| Booster packs, odds, draw | `rel_shop.prx` | `packs`, `pack_odds`: `tables.py` | CSV; the draw procedure is code (`packs.md`) | ok: 48 packs |
| Forbidden/limited list | `BOOT.BIN` | `limit_list`: `tables.py limits` | CSV | ok: 114 cards |
| Fusion and ritual recipes | `rel_duel_eng.prx` | `fusions`, `rituals`: `fusion.py` | CSV | ok: 138 + 31 |
| Card effects (specification) | `rel_duel_eng`, `BOOT.BIN`, `rel_duel_draw` | `card_effects`: `card_effects.py` | JSON Lines + CSV per card, with sources and confidence | ok: 3,614 ids, 112 s (content partial: workstream W) |
| AI per-card priority tables | `rel_duel_eng.prx` | `ai_tables`: `ai_tables.py` | CSV | ok |
| Opponent decks and owners | `BOOT.BIN` embedded archive and tables | `deck_recipes`, `deck_owners`: `decks.py` | CSV / JSON | ok: 661 recipes, 661 owners |
| Character table | `BOOT.BIN` `0x088aa510` | `characters`: `exe_tables.py dump` | JSON (174 records, names, card lists) | ok |
| Story and dialogue text (5 languages) | `script/story_scr_<l>.ehp` | `story_text_<l>`: `story.py text` | CSV, markup kept | ok: 11,976 lines × 5 |
| Story event scripts | `script/story_scr_b.ehp` | `story_events`: `story.py events` | CSV of named instructions for the port's event VM | ok: 7,468 records |
| UI and system strings | `strTbl*`, `*_strtbl_*`, … | `strings`: `strtbl.py dump` | JSON per table | ok: 1,851 tables, 22 s |
| Fonts | not on the disc: text is drawn with the PSP system font (`sceFont`, `libfont.prx` is an encrypted Sony module) | none possible | port supplies its own font with the metrics and `$` control codes of `system.md` | port decision (below) |
| Textures | every `.gim` (archives, loose, `BOOT.BIN`) | `textures`: `gim.py batch` | PNG RGBA8 per plane, palette level and frame | ok: 16,050 PNG, 0 failures, 532 s |
| 2D layouts (menus, HUD, bust-ups) | `.ehf` + `.tmf` | `layouts`: `ehf.py json` | JSON timelines (schema 1) referencing the PNGs | ok: 1,225 layouts, 0 failures |
| Screen map (which scene loads which layout/table) | modules + archives | `scenes`: `scenes.py map` | JSON | ok |
| 3D models, animations, cut-ins, props, maps | `.tms`/`.tmt(.gz)`/`.tma`/`.vtmt` | `models`: `tgm.py gltf --all` (**new**) | glTF 2.0 + `.bin` + PNG + `tf3-tgm-scene` JSON | ok: 585 models with all fitting animations, 0 failures, 364 s, 1.4 GB |
| Field-spell 3D backdrops | `duel/bg/fmagic<id>.ehp` | included in `models` | glTF scene + side file; card id = file name | ok (`fmagic3720` sample: 4,406 triangles, camera, lights) |
| Free-roam maps, walk grids, doors, exits | `field/map/*.ehp`, `rel_field`, `rel_story` | `world_maps`, `world_tables`: `world.py` | JSON per map, JSON tables | ok: 32 maps |
| Partner chapters (progression) | `rel_story` | `world_chapters`: `world.py chapters` | JSON | ok: 64 rows |
| Duel tutorials | `d_tutorial/tutorial.ehp` | `tutorial`: `tutorial.py --json` (**new**) | JSON: 50 set-ups, 17 scripts, 6 × 878 text lines | ok |
| Music, effects, voices | `snd/psp_snddat.bin` | `audio`: `audio_convert.py` (FFmpeg) | OGG/WAV per stream + JSON per bank (loops, cue data) | ok: 728 banks, 18,716 streams (481 min) to OGG, 453 s |
| Sound attributes | `BOOT.BIN` SHDS header | `sound_attributes`: `exe_tables.py sound-attributes` (**new**) | CSV/JSON per global id | ok: 31,459 ids, type matches the stored codec for all 30,779 cues |
| Voice routing and captions | `BOOT.BIN`, `database/`, `duel/cutin_*` | `voices`: `voices.py` | CSV | ok |
| Movies | `movie/*.pmf` | `movies`: `psmf.py --convert` (FFmpeg) | MP4 (H.264 + AAC), MKV or WAV | ok: 73 movies to MP4, 38 s |
| Save import (optional) | the player's plaintext `DATA0` | `save.py json` (not in `extract_all`: input is a save, not the disc) | JSON of every mapped region | ok on save `v1` (126 deck slots, 54 cards) |
| Minigames | `minigame/*` | assets via `textures`, `layouts`, `models`, `strings` | as above | assets ok; game logic not analysed (outside WP1–5) |

FFmpeg 7.1.1 was used for the audio and movie steps (ATRAC decoding is delegated to it, `extractor-spec.md` §16, §17).

### Port-side decisions (not reverse-engineering questions)

- **Font.** Glyphs come from the PSP firmware font through `sceFont`; nothing on the disc holds them except the ruby glyphs `rubi_font00.gim`. The port needs its own font with the same advance metrics, the `$R`/`$f`/`$F`/`$C` control codes and both line-break rule sets (`system.md`, "Font renderer").
- **UMD-swap unlocks.** Save flags `+0x1c0e9` bit 7 and `+0x1c0ea` bit 0 (they gate shop packs) are set only by `rel_umd_replace`, which reads another UMD (`shop-rules.md`). The port must decide how to grant them.
- **Video format** for the 3DS (`extractor-spec.md`, open questions); the converter produces MP4 as the neutral start.
- **Link play** (ad-hoc duels, `rel_duel_eng` network packets) is out of the first port scope; nothing in single-player depends on it.
- **Positional audio**: no sound on the disc uses the SHDS 3D, Doppler or reverb flags (`sound.md`, census), so the port needs no 3D audio.

## Blocking questions

The 16 blocking items of `open-questions-triage.md`, grouped into tasks, in order of value for the port. "S" = static reading of `BOOT.BIN`/modules (capstone and the docs are enough), "P" = PPSSPP check.

| Task | Items (triage #) | What is missing | Settled by | State after this audit |
| --- | --- | --- | --- | --- |
| **B1** Timing-event vocabulary | 243, 248, 308, 322, 350 | Which game event each timing code means; the trigger system of the port is keyed on them | S done: all 52 raisers enumerated, 32 code values named (`duel-runtime.md`, "Event codes by raiser"); the Damage Step window lists read. **P: G1** (one logged duel) for the codes that are computed at run time (`0x16`/`0x1c`, discard, effect summon) | Mostly settled; one PPSSPP session left |
| **B2** Duel conditions / challenges | 355 | Which feature the condition index of `duel_core_check_duel_condition` (`0x09be3bc0`, ~115 cases) belongs to, and who sets the bit set `0x09e02f24`; feeds the save record table (progression) | S: decode the switch case by case and the writers of record word `0xa4` (1–2 days) | Open |
| **B3** Player and slot flag bits | 452, 455, 463 | Readers of player `+0x120` bits 20/22/24–26 and slot flags 10/13/15/19/28/30 (per-turn rule state that card conditions test) | S done: capstone sweep of `rel_duel_eng`, `rel_duel_draw`, `rel_duel_mgr`; complete bit tables of both words with writers and readers (`duel-runtime.md`, "Player and slot flag bits"). Bit 20 = Main Phase 1 no longer at its start; 22 = Special Summon cap; 24 = own monster sent to the Graveyard; 25/26 = Spell/Trap activated; slot 10 face-up since placed, 13 monster as Continuous Spell, 15/19 turned face-up (lasting / this turn), 28 activated from the hand, 30 attack declared. Optional **P: G5** | **Settled statically (H; bits 2, 19, 22 purpose M)** |
| **B4** World and story rules | 29, 75, 130 | Partner-choice roster (`ui_charalist` mode 3); what loads maps 37/38 and the second dorm; story-duel `duel_rules`/`duel_option` bytes and follow-up order | S: three small reads in `rel_story`, `rel_field`, `rel_charalist`, `rel_duel_mgr` (1 day) | Open |
| **B5** After the staff roll | 28 | What the game shows after the ending, whether the stage resets for a new partner | P: E15 (needs a late save); alternatively S: `rel_story` states 48/50 | Open |
| **B6** Lost chapter duel | 30 | Whether step 3 starts from the map after a lost step-2 duel, or the duel repeats | P: **G2** | Open |
| **B7** Minigame records | 103, 107 | Which minigame owns which of the nine high-score records (shop unlock rules read them) | P: E23 (differential save 6) | Open |
| **B8** Password and conversion machines | (new; from 98), 97 | The rules of `rel_password` and `rel_conv_machine`, the only routes left for 19 cards that are in no pack (`packs.md`, "Cards in no pack") | S done: both modules read (`shop.md`, "Password machine and conversion machine"): a passcode registers any card except `6989` for the lab rental list (no copy, no cost); the conversion machine trades 10–99 cards for one card from 90 result lists (`6989` only with 59). Eight no-pack cards have no route in either machine (external gifts/DLC: port decision). **P: G3** (rewritten) confirms the rental entry | **Settled statically (H)**; G3 confirms |

### Settled in this audit (static, capstone)

- **Effect record variant rule** (`effect-tables.md`): every per-card rule of `duel_effects_select_record_variant`, keyed on the chain link's event code, location and event argument, with the Spirit default. Closes `card-effect-spec.md`'s blocking question.
- **Timing-event vocabulary** (`duel-runtime.md`): 52 raisers, 32 code values named from their raisers; the Damage Step activation lists of `duel_effects_is_activatable_in_window` read against them.
- **Story duel result word** (`duel-runtime.md`, `0x09e02cb0`): 1 won, 2 lost, 3 draw, as `world_record_duel_result` receives it.
- **Recipe level** (`deck.md`): used only for the experience reward of a won duel.
- **Cards in no pack** (`packs.md`): 52 tokens, 5 underground-duel prizes, 16 cards excluded from the collection percentage and from random rewards, 3 more excluded from rewards; the underground reward picker and its rarity tiers are documented.
- **Shop unlock flags** (`shop-rules.md`): writers of `+0x1c0e9` bits 0/4 (partner stories finished: ≥ 1, ≥ 6), bit 5 (underground counter ≥ 50), bit 7 and `+0x1c0ea` bit 0 (UMD swap).
- **SHDS sound types** (`sound.md`): type 4 = ATRAC3, 5 = ATRAC3plus (the earlier hypothesis was reversed), census of the attribute words.
- **Gemini state** (triage 462): slot flag bit 3 is the transient effects-off flag of every placement, cleared by command `0x44`; the Gemini-summoned state is bit 14 (`summon.md`, `duel_core.md`). Reclassified as resolved.
- **Data after the fusion recipes** (`fusion-recipes.md`): compiler jump tables, not game data.
- **BOOT.BIN card lists `0xa3560`–`0xa3c80`** (`deck.md`): the character table's recipe-card and key-card lists.
- 22 open questions in `docs/formats/` that other documents already answered now carry the pointer in place; the matching subsystem items are listed with pointers in the triage.

### Non-blocking workstreams

- **W: card-effect and AI fidelity** (18 triage items, and `extractor-spec.md` §5, §18). The per-card specification names the engine behaviour and numbers of most cards; 244 compare chains, the `engine_only` branches and the 600 single-use AI handlers are not decoded one by one. A port can implement effects from the official card text on top of the documented engine rules (chain, timing events, battle, summon, stat layers) and use the specification as its test oracle; decoding the rest adds the original's exact quirks. Work per effect family, not per card.
- **UI playback**: how each scene steps its layouts (`ui.md`). The port redesigns the UI for two screens; the layouts, textures and strings are extracted.
- **Rendering fidelity**: TGM overlay texture-map types, unknown `-etc` tracks (`tgm.md`).

## PPSSPP checks still to run, by value

Only the checks that settle a blocking item or confirm a rule the port depends on; the full list with steps is `docs/verification/ppsspp-plan.md`.

1. **G1** timing-event codes of the computed raisers (B1): one duel with a logging breakpoint, about 30 min.
2. **E23** minigame bases and high scores, differential save 6 (B7): about 40 min for all seven minigames.
3. **G2** step 3 after a lost chapter duel (B6): builds on E13's set-up, about 20 min.
4. **G3** the password machine (B8): about 10 min.
5. **E15** story state 46 and what follows the staff roll (B5): needs a save at the end of a partner story.
6. **F11** duel record, record table and recipe unlock: confirms the save fields B2 writes.
7. **E13** (remainder) stage advance at the end of a chapter: confirms the chapter progression already specified.
8. **G4** the story duel result word (optional confirmation of the static answer).
9. The rest of Session F (F1–F10, F12) and E17–E22: confirmations of rules already specified statically (fidelity).

## Run log (2026-11-04)

- All 35 test files under `tools/tests/` pass (`test_extract_all.py` new; new cases in `test_cip.py`, `test_tgm_gltf.py`, `test_tutorial.py`, `test_roundtrip.py`).
- `python3 -I tools/progress.py --check`: ok (28,203 functions, 182 formats).
- `python3 -I tools/roundtrip.py --check <PSP_GAME> --saves external/ppsspp/saves`: all 87 round trips byte-identical (66 without the saves).
- `python3 -I tools/extract_all.py <PSP_GAME> -o extracted/port`: **51 of 51 steps ok**, about 31 minutes (card art 306 s, textures 524 s, models 364 s, audio 453 s, everything else under 2 min per step). Output stays under `extracted/` and is not committed.
