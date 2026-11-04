# Open-question triage (2026-11-04)

Every bullet of every "Open questions" list in `docs/subsystems/*.md` and `docs/formats/*.md`, as collected on 2026-11-04 for `docs/PORT-READINESS.md`, with its classification for the 3DS port. The question text is shortened; the source document holds the full item and any later answer. Classes:

- **B** blocking: without the answer the port cannot reproduce a gameplay rule, a progression condition or a data asset. Each B item belongs to one task B1–B8 of `PORT-READINESS.md`, settled by static reading (**S**) or a PPSSPP check (**P**, `docs/verification/ppsspp-plan.md`).
- **R** resolved: answered in the item itself, elsewhere in `docs/` (pointer given) or in this audit. Items answered elsewhere in `docs/formats/` now carry the pointer in place; subsystem documents were left unchanged in this audit (another work stream edits them), so their pointers are listed here only.
- **W** non-blocking, part of the card-effect and AI fidelity workstream: a port can implement the behaviour from the official card text and the documented engine rules; the binary only adds the original's exact numbers and quirks.
- **N** non-blocking: fidelity detail (timing, look, unused or dead code, debug paths, Sony library internals, zero bytes, naming, link play, UI layout the port redesigns).

Totals: 573 items: B 13, R 151, W 18, N 391.

| Document | Items | B | R | W | N |
| --- | --- | --- | --- | --- | --- |
| `formats/ai-runtime.md` | 6 |  |  |  | 6 |
| `formats/ai-tables.md` | 4 |  |  | 1 | 3 |
| `formats/card-effect-spec.md` | 10 |  | 2 | 7 | 1 |
| `formats/card-refs.md` | 4 |  |  |  | 4 |
| `formats/cardinfo.md` | 4 |  | 1 |  | 3 |
| `formats/chapter-table.md` | 4 | 3 |  |  | 1 |
| `formats/character-table.md` | 2 |  |  |  | 2 |
| `formats/cip.md` | 7 |  |  |  | 7 |
| `formats/deck.md` | 11 |  | 5 |  | 6 |
| `formats/disc-layout.md` | 3 |  | 1 |  | 2 |
| `formats/duel-runtime.md` | 5 |  | 1 |  | 4 |
| `formats/effect-tables.md` | 6 |  | 3 | 2 | 1 |
| `formats/ehf.md` | 6 |  | 5 |  | 1 |
| `formats/ehp.md` | 3 |  | 1 |  | 2 |
| `formats/field-maps.md` | 6 | 1 | 1 |  | 4 |
| `formats/field-tables.md` | 2 |  | 1 |  | 1 |
| `formats/file-index.md` | 3 |  | 2 |  | 1 |
| `formats/fusion-recipes.md` | 3 |  | 1 |  | 2 |
| `formats/gim.md` | 2 |  |  |  | 2 |
| `formats/hmp.md` | 2 |  |  |  | 2 |
| `formats/limit-list.md` | 2 |  | 1 |  | 1 |
| `formats/packs.md` | 4 |  | 4 |  |  |
| `formats/psmf-movies.md` | 4 |  | 1 |  | 3 |
| `formats/save-minigame-blocks.md` | 2 | 1 |  |  | 1 |
| `formats/save.md` | 6 | 1 | 1 |  | 4 |
| `formats/search-filters.md` | 6 |  | 1 | 4 | 1 |
| `formats/shop-rules.md` | 3 |  | 2 |  | 1 |
| `formats/sound.md` | 5 |  | 3 |  | 2 |
| `formats/story-runtime.md` | 3 |  | 1 |  | 2 |
| `formats/story.md` | 7 | 1 | 3 |  | 3 |
| `formats/string-tables.md` | 4 |  | 1 |  | 3 |
| `formats/tgm.md` | 8 |  | 2 |  | 6 |
| `formats/tutorial.md` | 6 |  |  |  | 6 |
| `formats/vtmt.md` | 2 |  |  |  | 2 |
| `subsystems/ai-helpers.md` | 6 |  |  | 1 | 5 |
| `subsystems/ai.md` | 58 |  | 3 | 1 | 54 |
| `subsystems/audio.md` | 9 |  | 5 |  | 4 |
| `subsystems/battle.md` | 22 | 2 | 5 |  | 15 |
| `subsystems/card_db.md` | 4 |  | 3 |  | 1 |
| `subsystems/chain.md` | 9 |  | 4 |  | 5 |
| `subsystems/container.md` | 9 |  | 6 |  | 3 |
| `subsystems/deck.md` | 3 |  | 2 |  | 1 |
| `subsystems/dialogue.md` | 6 |  | 1 |  | 5 |
| `subsystems/duel-phases.md` | 6 |  | 5 |  | 1 |
| `subsystems/duel_core.md` | 13 |  | 3 |  | 10 |
| `subsystems/duel_effects.md` | 32 | 2 | 5 |  | 25 |
| `subsystems/effect-classification.md` | 5 |  | 3 |  | 2 |
| `subsystems/effect-helpers-deck.md` | 8 |  |  |  | 8 |
| `subsystems/effect-helpers-misc.md` | 17 | 2 | 3 | 1 | 11 |
| `subsystems/effect-helpers-movement.md` | 7 |  | 1 |  | 6 |
| `subsystems/effect-helpers-predicates.md` | 9 |  |  |  | 9 |
| `subsystems/effect-helpers-values.md` | 6 |  |  | 1 | 5 |
| `subsystems/field_3d.md` | 34 |  | 7 |  | 27 |
| `subsystems/modules.md` | 6 |  |  |  | 6 |
| `subsystems/movies.md` | 4 |  |  |  | 4 |
| `subsystems/save.md` | 1 |  |  |  | 1 |
| `subsystems/sdk.md` | 1 |  | 1 |  |  |
| `subsystems/shop.md` | 11 |  | 4 |  | 7 |
| `subsystems/stat-modifiers.md` | 7 |  | 2 |  | 5 |
| `subsystems/summon.md` | 17 |  | 12 |  | 5 |
| `subsystems/system.md` | 15 |  | 3 |  | 12 |
| `subsystems/tag_duel.md` | 5 |  | 5 |  |  |
| `subsystems/ui.md` | 68 |  | 14 |  | 54 |
| `subsystems/world.md` | 20 |  | 10 |  | 10 |

## `formats/ai-runtime.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 0 | `ai_attack_result`: what `ai_sim_resolve_battle(..., 1)` restricts in the early return of `ai_eval_attack`; how the header flags `+0x06` and the … | N |  |
| 1 | `ai_summon_choice +0x08` (u32) and the meaning of `+0x01`/`+0x02` beyond the simulation side and landing slot. | N |  |
| 2 | `ai_stat_snapshot +0x34`–`+0x43`: readers, the meaning of compute flag 2, and what `ai_estimate_slot_stats` writes there for the non-AI side. | N |  |
| 3 | `ai_battle_plan`: meaning of `+0x0c`, of the attack-order records other than record 0 `+2`, and of the unaddressed tail `+0x264`–`+0x2e3`. | N |  |
| 4 | `ai_board_view` interest records: what the keys `0xe133`/`0xe26d`/`0xea93`/`0xe27b` select (as s16 they read "every card except …"; confirm). The … | N |  |
| 5 | Runtime confirmation (none of these structures has been traced): dump the context frames during a nested prompt, the summon record after … | N |  |

## `formats/ai-tables.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 6 | What `BOOT 0x0885ff3c` and `BOOT 0x0885fef0` test (gates for A-in-B and for B in response windows); probably card-kind predicates. | N |  |
| 7 | Meaning of the timing-event codes 2, `0x12` and `0x1b` that select the T1 subset, R1 (with `0x13` attack declared) and R3 (`0x14` is the start of the … | N |  |
| 8 | Why 18 engine-supported card ids have no cardinfo record (cut cards, Japanese-only cards). | N |  |
| 9 | Handler semantics: the 77 handlers shared by ≥ 3 entries are named and classified (`docs/subsystems/ai-helpers.md`); the 600 single-use handlers are … | W | Card-effect / AI fidelity workstream (`PORT-READINESS.md`). |

## `formats/card-effect-spec.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 10 | The run-time variant rule per card, needed to pick the right record when a card has several. | R | Decoded in this audit: `formats/effect-tables.md`, "Variant selection rule". |
| 11 | What the generic field and equip fallback handlers (`0x09c74ba4`, `0x09c748a8`) do beyond the stat modifiers. | R | `effect-helpers-misc.md` (`0x09c74ba4`, `0x09c748a8` steps), `functions/duel_effects.md`. |
| 12 | Why 47 engine-supported ids have no `cardinfo` record (cut cards, Japanese-only cards). | N |  |
| 13 | For each `engine_only` card, what the branch selected by its id does beyond the function's rule (the semantic tags of `card-refs.md` say which rule; … | W | Card-effect / AI fidelity workstream (`PORT-READINESS.md`). |
| 14 | The meaning of the per-card values of the `expression` and `unresolved` chains whose cases call AI helpers (`ai_estimate_card_atk` `0x09ce536c`, … | W | Card-effect / AI fidelity workstream (`PORT-READINESS.md`). |
| 15 | The 1,265 `path_limit` cases left after loop summaries and merging: most are bodies with many independent tests whose states differ (no merge); state … | W | Card-effect / AI fidelity workstream (`PORT-READINESS.md`). |
| 16 | The stack slots of the `iteration` cases of `duel_core_compute_card_stats` (which slot is ATK, DEF, the per-side bonus): naming them would turn those … | W | Card-effect / AI fidelity workstream (`PORT-READINESS.md`). |
| 17 | `iteration` effects say what a case leaves for the rest of its loop in registers and stack slots, not what the code after the loop does with it … | W | Card-effect / AI fidelity workstream (`PORT-READINESS.md`). |
| 18 | Category model: proposals (a)-(d) of schema 7 are implemented in schema 8 (sections "Information-only records" to "Name-alias cards"). Open: how the … | W | Card-effect / AI fidelity workstream (`PORT-READINESS.md`). |
| 19 | Narrow Pass: the engine refuses a Normal Summon while the summoning player controls 2 or more monsters (`duel_core_count_monsters`), which is not the … | W | Card-effect / AI fidelity workstream (`PORT-READINESS.md`). |

## `formats/card-refs.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 20 | The scan is straight-line and path-insensitive. An id that is loaded into a register and compared after a loop or join is not seen. Some operands are … | N |  |
| 21 | Ids built arithmetically (`base + k`) or read from data tables are not found. The known data tables have their own tools: effect tables, lists, AI … | N |  |
| 22 | `range` and `bound` keep every id of the interval; they are not used to explain cards. | N |  |
| 23 | Whether a reference implements the card's own effect or names it from another card's effect needs the function's meaning. This improves as functions … | N |  |

## `formats/cardinfo.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 24 | The meaning of word 1 bits 22–24 (read only through the export `0x08832bdc`; trace a module caller). | R | Rarity field: `card_db.md`; confirmed by the underground reward filter (`formats/packs.md`, "Cards in no pack"). |
| 25 | `CARD_Genre`: who sets bits 0 (New Card) and 38 (different artwork) at run time, and whether the table at `0x0889f980` is the deck editor's filter … | N |  |
| 26 | Why `CARD_SamePict` lists record 855, which has only one image in the `.cip` files. | N |  |
| 27 | What the game does with descriptions longer than its 0x77a-byte buffers (`card_db_get_description` rotates four of them at `0x08924d5c`). | N |  |

## `formats/chapter-table.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 28 | What the game shows after the staff roll (state 48/50 and later) and whether the stage is reset for a new partner (only `world_init_calendar` writes … | B (P) | B5: PPSSPP E15 (needs a late save) or static reading of `rel_story` states 48/50. |
| 29 | Which characters the partner choice offers (decides whether the rowless variants and the category-4/5 offsets matter). | B (S) | B4: read the character-list filter of `ui_charalist` mode 3 (system flag `0x14`). |
| 30 | The step-3 location test (when does a step-3 event start from the map rather than after the duel: a lost duel?). PPSSPP: watch field block bytes 0–1 … | B (P) | B6: PPSSPP G2. |
| 31 | Rows 57 and 59–63 and the header word `kind` have no reader; perhaps left over from a category-keyed design (low). | N |  |

## `formats/character-table.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 32 | Meanings of `+0x09`, `+0x18`–`+0x1c`, `+0x3c`, `+0x3e`, `+0x3f`, `+0x52`–`+0x54` and of the tuning block `+0x44`–`+0x77`. | N |  |
| 33 | What distinguishes the two sprite textures `+0x10` (`_sla`) and `+0x14` (`_ver`). | N |  |

## `formats/cip.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 34 | Which screens use `cardh`, `cardm` and `card8`, and how the `cardh` atlas pieces are assembled on screen (needs the loader and a PPSSPP trace). | N |  |
| 35 | The exact placement of each piece in the `cardh` atlas, and whether the 128 truncated bytes at its end are ever sampled. | N |  |
| 36 | `CPJ`: what the slot's first 158 bytes (before the seed) hold; they are neither the JPEG head nor generator output from any seed and the game … | N |  |
| 37 | What the 7 ids without a database record are, and why `CARD_SamePict` lists record 855, which has only one image. | N |  |
| 38 | Meaning of the per-entry `reserved` word (always 0) and of the palette alpha bytes in `card8` (always 0). | N |  |
| 39 | `cis_all.gim` cell geometry and whether `fileTbl.dat` index `i` is cell `i`. | N |  |
| 40 | The functions in `BOOT.BIN` that open and read these files (string xrefs from `0x9d28c`–`0x9d400`; not traced because Ghidra was not available in … | N |  |

## `formats/deck.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 41 | The `u32` at `.ydc` offset 4: who wrote it and whether anything reads it. | N |  |
| 42 | Answered 2026-10-30 ("Who uses which recipe"): recipes 462–660 are never loaded as decks; their contents are five-slot draft blocks of owners 87–126, … | N |  |
| 43 | The owner id is the story character id (answered from `rel_story` `0xa5cc`, which passes the character of the duel set-up to … | N |  |
| 44 | `rel_story` duel mode 6 (`0xa098`, set-up byte `0x33358`): it loads the set-up recipes of duellists 0 and 1 with `deck_load_recipe` directly (except … | N |  |
| 45 | The recipe card list at `0x089150b8`: what reads set-up record `+0x14c` (key cards for the AI, the versus screen or the recipe viewer). | N |  |
| 46 | The `stage` argument and mode of `deck_select_owner_variant`, and the value compared with 2000 for owner 8. | R | `formats/deck.md` "Who uses which recipe" and `formats/story-runtime.md` (`+0x24` deck index from friendship points, `+0x42` event deck); the 2000 threshold is character points (`formats/save.md`). |
| 47 | What `rel_duel_eng` does with the recipe level (six calls) and what decides the level that `rel_underground` asks for. | R | Settled in this audit: experience reward of a won duel (`formats/deck.md`, open questions). |
| 48 | The player's deck format in save data, and whether it is the 0xc0-byte in-memory struct. | R | `formats/save.md`, deck slots. |
| 49 | The image container indexed by `fileTbl` / `sameCardTbl` slots (`card/*.cip` headers contain the id range `0xe88`–`0x1f39`). | R | `formats/cip.md` (`fileTbl.dat` is not the `.cip` map). |
| 50 | Deck tutorial: the wait kinds 3/4 (who advances `+0x22c34`), `wait_button` mode 1, the `cursor` argument, and the highlight regions; strings 0, 1, 3, … | N |  |
| 51 | The zero-terminated card lists at `BOOT.BIN` file offsets `0xa3560`–`0xa3c80` and the id runs in `rel_conv_machine.prx`. | R | Settled in this audit: character-table `+0x84`/`+0x8c` lists (`formats/character-table.md`). |

## `formats/disc-layout.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 52 | Is `BOOT.BIN` the same program as `EBOOT.BIN`? Hypothesis, medium confidence (sizes differ by 340 bytes). Confirm by comparing BOOT.BIN against the … | N |  |
| 53 | Formats still to identify: the member types listed in `ehp.md` (the `snd/` banks are in `sound.md`, the `script/` archives in `story.md`). | N |  |
| 54 | Which `gmodule/` PRX modules are loaded, by whom and when. | R | `subsystems/modules.md`. |

## `formats/duel-runtime.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 55 | Meaning of the instance-table bits 14–15 and byte `+0x03`, of list-entry bits 2, 4–6 and 15 of `u16 +2`, and whether effect-record byte `+0x03` is … | N |  |
| 56 | Input-state words `0x09e2d25c` and `0x09e2d294`; four of the seven executor masks at `0x09e2bba8`–`0x09e2bbc3`. | N |  |
| 57 | `0x09e02cb0` (extra duel result) and the gate `0x09de4d0c` of the list-activation collector. | R | `functions/import-stubs.md` (`card_db_get_spell_speed` stub) and `ai.md`. |
| 58 | Prompt kinds 4, 7 and 8 (workers not read). | N |  |
| 59 | Confirm in PPSSPP: the battle damage records for one attack with piercing (`battle.md`), the phase override stack during an AI turn, and the material … | N |  |

## `formats/effect-tables.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 60 | ~~Confirm slots `+10` and `+14`~~: both are activation-time steps of the chain builder (`chain.md`); `+14` returns > 0 / < 0 like `+10`. | R | Struck in the item; `chain.md`. |
| 61 | Target filter: why the `0x800` cards skip the immunity check; the purpose of bit `0x8000` and of the `0x1de1` test under `0x40000`; confirm slot … | N |  |
| 62 | The effect-context fields read by the computed draw counts (`+0x0c`, `+0x12`, `+0x15`, `+0x16`), and the computed cases of the LP-cost chain. | W | Card-effect / AI fidelity workstream (`PORT-READINESS.md`). |
| 63 | The card-structure fields behind the selector and the `0x24` test. | W | Card-effect / AI fidelity workstream (`PORT-READINESS.md`). |
| 64 | The cards with effects and no record in any table: handled by compare chains (1,379 functions in the module test card ids directly)? | R | `formats/card-effect-spec.md` (`engine_only`), `formats/card-refs.md`. |
| 65 | `duel_effects_check_rule_list` (`0x09ce27c4`) walks 112 `(function, argument)` pairs at `0x09dedaf8`; what these global rules are. | R | `subsystems/duel_effects.md` "Rule list", `functions/duel_effects.md`. |

## `formats/ehf.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 66 | ~~What `ui_bind_ehf` writes into words 4–5 of each primitive~~: answered 2026-11-04 (static, high): nothing; the player reads the 6-word primitive … | R | Answered in the item. |
| 67 | ~~Stage field `0x08`~~: answered 2026-11-04 (high): vsyncs per layout frame, so a layout runs at 60 / value frames per second, capped by the game's … | R | Answered in the item. |
| 68 | ~~Interpolation and the `add` channel~~: answered 2026-11-04 (high): keys interpolate linearly and hold the first/last value outside their range; the … | R | Answered in the item. |
| 69 | ~~`.tmf` bits~~: answered 2026-11-04 (high): bit 0 additive blending, bit 4 bilinear filtering; without a `.tmf` every slot gets 0 (normal blending, … | R | Answered in the item. |
| 70 | ~~Re-placing at an occupied depth~~: answered 2026-11-04: it creates a new instance, so the track restarts (as the tool does). | R | Answered in the item. |
| 71 | Line-strip primitives (16) are not drawn by the tool. | N |  |

## `formats/ehp.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 72 | `*ptrs.txt` lists: in archives with TGM members every non-zero entry is the offset of a whole member, so these are lists of resources … | R | Answered in the item. |
| 73 | What `0x0881e6a4` does with the screen-size arguments. | N |  |
| 74 | Which extensions are registered in the runtime handler table, and by whom. | N |  |

## `formats/field-maps.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 75 | What loads maps 37 and 38 (no location maps to them), and what selects the second dorm version. | B (S) | B4: find who passes map ids 37/38 and selects the second dorm (`rel_field`/`rel_story`). |
| 76 | The meaning of `0x08e9b460()` (arrival in room 204) and of the direction values 0–7. | N |  |
| 77 | The scripted placements behind cells 10000/10001 (`world_send_npc_list`, locations 5 and 25) and the anonymous extras on locations 2 and 4. | N |  |
| 78 | Which part of `bm_parts.gim` and which EHF layout each island area uses; the exact on-screen marker sprite. | N |  |
| 79 | Whether `0x090d3f54` draws the talk balloon (the cell lists of maps 21 and 27 suppress it). | N |  |
| 80 | PPSSPP confirmation of the door-opening distance, the midnight lock and the arrival cells. | R | `verification/results/2026-10-31-sessionE-W.md` E11, E12. |

## `formats/field-tables.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 81 | The island-map areas and destinations are in `docs/subsystems/world.md`; screen positions and navigation are decoded in `field-maps.md`. | R | Cross-reference, not a question. |
| 82 | Map ids 6–11, 28, 33–35 are absent from the switch (they map to index 0, the main gate). | N |  |

## `formats/file-index.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 83 | Comparator `0x0881dfd4`: it calls `system_strcasecmp`, so lookups are probably case-insensitive; confirm by reading it. The lookup key is the path … | N |  |
| 84 | What the device positioning helper `0x0881e448` does before each read (only the descriptor argument survives decompilation). | R | `subsystems/container.md` (`container_io_lseek`). |
| 85 | Confirm at runtime in PPSSPP: index size, first entries, and that `0x089218dc` becomes 1 after boot. | R | `verification/results/2026-10-31-sessionE-T.md` E1. |

## `formats/fusion-recipes.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 86 | Confirm the slot-matching tie rules of `0x09cb97c4` (ambiguous matches, `0x09e29060`) in PPSSPP with a Fusion whose materials overlap (Elemental Hero … | N |  |
| 87 | `0x09e29060` is also used to sum the materials' ATK for UFOroid Fighter and Evil Hero Dark Gaia; check that the two uses never overlap. | N |  |
| 88 | The data after the recipe table (`0x09dec2e8`–`0x09dec4d4`) is not identified. | R | Settled in this audit: compiler jump tables (`formats/fusion-recipes.md`). |

## `formats/gim.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 89 | Which code selects a palette level (hair/costume colour of the field sprites and the character list) and a frame of the 9-frame images. | N |  |
| 90 | What `field_3d_bind_gim` (`0x08823dc0`) changes in place when binding. | N |  |

## `formats/hmp.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 91 | Whether any code reads values other than 0/1 (none occur on the disc). | N |  |
| 92 | PPSSPP confirmation of the triangle split (static only). | N |  |

## `formats/limit-list.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 93 | `deck_set_limit` writes the status into a per-card table; is that table part of save data (does the game support editing or updating the list)? | R | `formats/save.md`, card collection byte 2. |
| 94 | Header bytes before the table (`0x7073`, `0x61`) and the data after it (`(0x2b28, 3)`, `(0x2b40, 3)`, …) are unrelated or unexplained. | N |  |

## `formats/packs.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 95 | Pack names and artwork: which string table and texture belong to each pack index (`shop/all_<lang>.ehp` has `strTbl` with 35 entries and … | R | `formats/string-tables.md` (`pack_name_str`, `pack_explain_str`). |
| 96 | Confirm in PPSSPP: a single purchase (DP before/after, save byte `+0x1542a + p`, counter `+0x16602`, one rarity entry written), and the rarity … | R | `verification/results/2026-10-31-sessionE-P.md` E16. |
| 97 | The 99-entry card list at save `+0x161f6` (count `+0x161f4`) whose copies the result list shows (`0x08857158`/`0x088571c8`; presumably the trunk or a … | R | B8 (2026-11-04): the lab rental list, `subsystems/shop.md` "Password machine and conversion machine". |
| 98 | How the 76 cards that are in the database but in no pack are obtained (rewards, starter deck, story). | R | Settled in this audit: `formats/packs.md`, "Cards in no pack" (tokens, underground prizes, collection-excluded cards); the password and conversion routes are blocking item B8. |

## `formats/psmf-movies.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 99 | The header bytes between `+0x10` and `+0x55` and the tails of the stream entries (frame rate, ATRAC3plus parameters) are not decoded; only the fields … | N |  |
| 100 | Whether the audio track is the full soundtrack for the movie or only the voice and effects (the bitrate is answered: 744-byte frames, 128,166 bit/s). | N |  |
| 101 | Whether the PSP player really drops 2,416 samples (one frame + decoder delay) before the first video frame; check the A/V offset in PPSSPP. | N |  |
| 102 | The call sites of the player (who opens each file, whether a button press can skip it) are not traced. | R | `verification/results/2026-10-31-sessionE-T.md` E2. |

## `formats/save-minigame-blocks.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 103 | Which mini-game passes which game index to the result routine (so which of the nine records belongs to blackjack, connection, dodge, quiz, reversi, … | B (P) | B7: PPSSPP E23 (differential save 6). |
| 104 | The meaning of the `rel_underground` block fields (play the mode in PPSSPP and watch `+0x1be18`). | N |  |

## `formats/save.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 105 | The meaning of the unknown collection and option bits. | N |  |
| 106 | The five unknown regions (4,850 bytes, listed in the map). (The readers of the minigame blocks were followed on 2026-11-04: … | N |  |
| 107 | Which minigame owns each of the nine high scores (the game index → record map is in `save-minigame-blocks.md`; the module → game index link is … | B (P) | B7. |
| 108 | What slot 0, the stored decks and the card list hold (deck editor), and the content of the `0x200`-byte edit block. | N |  |
| 109 | Whether `rel_title` rejects a save whose OpenPSID differs from the console's (the checksum only detects in-memory edits). | N |  |
| 110 | The meaning of the other save modes (7, 8, `0x16`). | R | `verification/results/2026-10-31-sessionE-T.md`. |

## `formats/search-filters.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 111 | Filter `0x10000`: the second condition (card `0x1e74`, absent from cardinfo, with the Lightsworn list `0x08862688`) — which card is `0x1e74` and why … | N |  |
| 112 | `0x09c0cb98`'s fifth argument (Deck/hand option `0x8` passes 1, option `0x10`/`0x4` passes 0). | R | `subsystems/effect-helpers-predicates.md`. |
| 113 | Graveyard options `0x40`–`0x200`: the meaning of entry byte `+2` bits 2–5. | W | Card-effect / AI fidelity workstream (`PORT-READINESS.md`). |
| 114 | Extra Deck options `0x4`, `0x8`: the per-card lists in BOOT `0x08864ff8`, `0x08865ad8`, `0x08863a34`. | W | Card-effect / AI fidelity workstream (`PORT-READINESS.md`). |
| 115 | Archetype `0x1f` (BOOT `0x08861d6c`): predicate without a card-id list (13 builders use it). | W | Card-effect / AI fidelity workstream (`PORT-READINESS.md`). |
| 116 | The `param` values reaching partial builders (Destiny Board, Machine Duplication, Metamorphosis …) come from `duel_effects_get_candidate_param` … | W | Card-effect / AI fidelity workstream (`PORT-READINESS.md`). |

## `formats/shop-rules.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 117 | ~~The source of the shop bytes for packs 9–14, 41/42 and 46~~: settled 2026-11-04 (weekday, daily clerk pick, button code; above). | R | Settled in the item. |
| 118 | The meaning of the save progress flags `+0x1c0e9` bits 4, 5, 7 and `+0x1c0ea` bit 0, and of minigame records 0, 1, 2, 7, 8 (`save.md`). | R | Settled in this audit (writers of every flag): `formats/shop-rules.md`; the minigame-record part is B7. |
| 119 | What the upper 15 bits of the shop opponent list encode, and whether the 104 entries are opponents or duel bonuses. | N |  |

## `formats/sound.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 120 | ~~Cue flags `0x02`, `0x04`, `0x10`, `0x11`, envelope byte `0x08`~~: answered statically 2026-11-04 ("`SHDS` sound header" above); envelope bytes … | R | Answered in the item. |
| 121 | ~~The play call and bank loading~~: answered 2026-11-04: `audio_start_sound` (`0x0886b37c`) and its wrappers take the global id; `audio_load_bank` … | R | Answered in the item. |
| 122 | How the duel chooses among the three banks of a voice set, and which voice ids the duel uses for the 52-cue generic-student sets. | N |  |
| 123 | Banks 709–711: partly answered 2026-11-04: 709 is loaded by the title, 710/711 by the free roam (with 712, 713, 715–717, 727); the duel loads 719 … | N |  |
| 124 | ~~Whether the game loops the 11 effect waves with a `smpl` chunk~~: answered 2026-11-04: yes, every RIFF wave is registered with … | R | Answered in the item. |

## `formats/story-runtime.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 125 | Content of the story sub-blocks `+0x3504`, `+0x3528`, `+0x3570`, `+0x3584` and of the second record set `+0x35b8`, and the 4 bytes at `+0x3524`. | N |  |
| 126 | Field state `+0x34` (writer), `+0x160`–`+0x168` (meanings), and whether the item counters `+0x94` are the item menu's counts. | R | `subsystems/world.md` ("Inventory"). |
| 127 | Field save block `+0x03` and `+0x08`. | N |  |

## `formats/story.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 128 | The driver around `0xb3c8` (how the field module picks the record to run, how the exit codes are consumed). | R | `subsystems/world.md` (event driver). |
| 129 | Which save fields the `BOOT.BIN` getters read (DP, per-character points, pack state, picture bits). The field side of the 33 requests is now listed … | N |  |
| 130 | The meaning of `talk`'s `a3` flag (0/1; 148 uses with 1, often on lines like "..."), of `npc_event`'s `(301, n)` pair, of the … | B (S) | B4: read the `rel_duel_mgr` readers of the set-up bytes behind `duel_rules`/`duel_option`. |
| 131 | Every opcode in use now has a name (the nine formerly open ones and 50126–50128 were read on 2026-10-30). Readings that a PPSSPP trace should … | N |  |
| 132 | The `《Cnnn_k》` forms 1–5, and whether `nnn` equals the speaker id in `a1` of 50001/50002/50009. The ranges overlap (2–141 vs 001–151), but this is … | R | `subsystems/dialogue.md` (`dialogue_expand_name_tokens`). |
| 133 | Where `《…》` placeholders and `$M`/`$C` are expanded in code, and whether the bracketed tokens in `SysMsg` are placeholders at all. | R | `subsystems/dialogue.md`. |
| 134 | Whether the empty lines (158 per language) are ever displayed. | N |  |

## `formats/string-tables.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 135 | Which index each screen reads: mapped statically by `tools/scenes.py` (`ui.md`, "Scene map"): every table but those in unreferenced archives is … | N |  |
| 136 | All headed tables are read through one accessor, `card_db_get_dictionary_word(table, index)` (`0x08836ed0`), with the table from … | R | Statement of fact. |
| 137 | Whether any code reads the end offset (for example to compute a string's length) or only uses offsets as start positions. | N |  |
| 138 | What `pack_explain_str` entries 48–95 are (two strings per pack, or a second set for alternative pack states; not checked against the shop code). | N |  |

## `formats/tgm.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 139 | Answered statically 2026-10-31: backdrops and cut-ins advance one frame per game frame at 30 Hz (above). Open: the effective rate under load (PPSSPP … | R | Answered in the item. |
| 140 | What texture-mapping types 1/2 do exactly (`0x0882ef50` / `0x0882f050` emit GE texture-map mode and light-source state; environment or projection … | N |  |
| 141 | Texture bytes `+0x08`/`+0x09` (`01 01`) and the reader of TGMS header `0x30`. | N |  |
| 142 | The 84-track `-etc` tracks 13–19 and the 42-track tracks 4–9; the direction convention of GE lights. | N |  |
| 143 | How the cut-in's group mask (`+0x64`) reaches the draw hook's mask (`hook+0x10`); which objects own the 32 visibility groups (props, alternative … | N |  |
| 144 | ~~The role of `.vtmt`~~: lip-sync animation, [`vtmt.md`](vtmt.md) (2026-11-04). | R | `formats/vtmt.md`. |
| 145 | Where the 828 textures without a same-archive `.gim` come from (character faces from `cutin_da_faces`, shared textures from `cutin_common.ehp`?). | N |  |
| 146 | The GE front-face setting (winding was established from normals, not from code). | N |  |

## `formats/tutorial.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 147 | Draw order of the deck list (does command `0x56` take entries from the start?), and the effect of the `0x08`-word serial bookkeeping. | N |  |
| 148 | The meaning of `PUTBYANOTHER`, `PARTICULAR` and the equip record fields; no file uses them. `_Param` is the slot word that command `0x2c` fills for … | N |  |
| 149 | The highlight regions 16–20 and the input codes of the filter in `rel_duel_draw`. | N |  |
| 150 | UI event 4's input modes (`duel_core_begin_player_input`) and why mode 7 is excluded; the dialog kind 3 that the tutorial answers with 0 unless … | N |  |
| 151 | Whether `rel_duel_draw` still handles UI event `0x42` (the legacy relay of command `0x68`), and the two unnamed exports `+0x468c`/`+0x46dc`. | N |  |
| 152 | `rel_tutorial`'s runtime base: take a PPSSPP symbol export during a lesson and run `tools/modules.py base`. | N |  |

## `formats/vtmt.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 153 | The per-character node maps (descriptor `+0x24` callbacks in the `cutin_chara_blocks` family): which mesh bones the ids 4–12 select for each … | N |  |
| 154 | Whether the voice level threshold 10 is on the same scale as the SHDS level meter of `audio.md` (it comes from `audio_get_sound_level(id, 1)`). | N |  |

## `subsystems/ai-helpers.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 155 | Meaning of `ai_is_normal_spell_in_graveyard` in context (when does an AI-evaluated link sit in the Graveyard?): set a PPSSPP breakpoint on … | N |  |
| 156 | Event code `0x12` accepted by `ai_handler_on_attack_declared_event` besides `0x13`; R3's event `0x1b` (Mind Crush, `0x09d27348`). | N |  |
| 157 | The per-card filters `0x09ce82dc` (target veto), `0x09d48b4c` (candidate veto), `0x09cf6358` (slot chooser), `0x09d64e54` (cost chooser), … | W | Card-effect / AI fidelity workstream (`PORT-READINESS.md`). |
| 158 | Rule flag `0x09e03070 & 0x80`: blocks control-changing handlers but makes `ai_handler_set_face_down_once_per_turn` accept; its writer in … | N |  |
| 159 | Marker `0x1f1b` (not a card id in the released list) tested by `ai_handler_set_face_down_once_per_turn`. | N |  |
| 160 | `0x09d37b70` (hand-limit slack with Dark World Grimoire) and `0x09c0d4c4` (used by the Pot of Avarice group) are unnamed. | N |  |

## `subsystems/ai.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 161 | Exact meaning of `ai_choose_summon_position_by_card`'s `flag` (3rd argument) and of card `0x135d` forcing it; what `context_card` is at the other … | N |  |
| 162 | Meaning of the `mode` word (0/1/2) of `ai_choose_monster_candidate_with_score_fn` and `ai_pick_candidate_by_score_fn`, and the layout of the 40-byte … | N |  |
| 163 | Whether `ai_try_card_from_table(side, card, table, 0)` called from `ai_choose_summon_position_by_card` can commit an activation or is only a probe. | N |  |
| 164 | The flags of `ai_pick_least_valuable_slot` beyond the documented `mode`/`check_link` behaviour, and what the `flag` of `ai_is_valuable_card_id` … | N |  |
| 165 | The `0x1889` branch of `ai_choose_target_by_card` clears slot-flag bits 22-23 and sets one back based on the post-simulation state; whether this is … | N |  |
| 166 | The `0x18aa`/`0xfe0` cases of `ai_choose_summon_position_by_card` leave a 1 in the borrowed zone's face-up word; confirm in PPSSPP whether it … | N |  |
| 167 | What `ai_sim_resolve_battle(..., 1)` restricts, so that the early return of `ai_eval_attack` does not skip ordinary kills (needs `0x09cfd864` read or … | N |  |
| 168 | Header `+0x06` values 1/2 and the per-side `+0x1c`/`+0x1e` words: how `ai_is_better_attack_result` and `ai_plan_simulate_attacks` weigh them. | N |  |
| 169 | Meaning of the attack-result class beyond the grading rules (the comparator `0x09d0c2e4` decides the order). | N |  |
| 170 | Interest records: the special keys `0xe133`, `0xe26d`, `0xea93`, `0xe27b`; the kind flags `+0x06`/`+0x07`/`+0x08`; `+0x12` category codes; … | N |  |
| 171 | `0x09e2d274` (written by `ai_choose_cost_by_card` with the side) and `0x09e28f80` (decremented around shared-handler calls): meanings. | N |  |
| 172 | `0x09e27fa4 + side·0x18` (byte read as a slot after `ai_simulate_attack` in the cost chooser). | N |  |
| 173 | The unused `mode` argument of `ai_eval_attack`: confirm in the disassembly that `a3` is really ignored. | N |  |
| 174 | `ai_check_target_slot` rejects every slot while `0x09e28f80 >= 0`; `ai_is_valid_target` (22 callers, mostly AI handlers) calls it without … | N |  |
| 175 | Slot flag bit 10 (`+0x10`) decides whether a face-down card is estimated (`ai_estimate_slot_stats`) and gates several target rules … | R | B3: slot bit 10 = face-up since placed (identity known), `formats/duel-runtime.md`, "Player and slot flag bits". |
| 176 | Meaning of the codes returned by `ai_classify_resolve_kind` (0-6) beyond "0 = nothing to answer", and of the outcome bits of `ai_sim_resolve_battle` … | N |  |
| 177 | `ai_card_can_target_slot` (`0x09ceb738`) needs the disassembly to recover its arguments (skipped). | N |  |
| 178 | `0x09e28e38` is used by `ai_sim_resolve_card_with_temp_link` as the index of the borrowed chain entry, while the other temp-link helpers use the link … | N |  |
| 179 | What `ai_eval_attack` does with the return values of `ai_eval_battle_damage_effects` (1 only for 0x1504/0x1502/0x1501 with slot flag bit 16 or 17) … | N |  |
| 180 | Meaning of the `mode` argument of `ai_get_card_lp_amount` (1, 2, 3 select exclusion lists). | N |  |
| 181 | Meaning of `0x09e2d1e0` (forced to 1 by `ai_should_summon_in_defense`; 0 makes the summon rating assume an opposing best ATK of 10,000). | N |  |
| 182 | Attack-order record `+0x0a` and the attack result fields `+0x04`, `+0x06`, `+0x10` (value word added to the snapshot ATK after planning). | N |  |
| 183 | `0x09e28e34` versus `0x09e28e38` (chain counts) and the AI-evaluation depth `0x09e28f80` (decremented per nested evaluation, set to -1 by … | N |  |
| 184 | `0x09e28628` (returned as the decision by `ai_handler_special_summon_1973_172f` for attack events) and `0x09e28f8c` (set around a target-filter call … | N |  |
| 185 | Why `ai_handler_check_candidates_162c_184c` accepts only when the 3-candidate pick is not "1, 2, 3 in order". | N |  |
| 186 | The three forwarders `ai_call_eval_hand_summon_candidate` (48 bytes), `ai_call_should_summon_in_defense` (36 bytes) and … | N |  |
| 187 | Whether the stand-in summon `0x129f` used for the opponent's reply plan is a dummy monster record (check the card table). | N |  |
| 188 | Skipped: the 8-byte thunks `ai_call_rate_slot_threat_with_links` (`0x09d49f3c`) and `_alt` (`0x09d49f44`) probably load a different third/fourth … | N |  |
| 189 | `ai_rate_slot_threat_if_link` and `ai_score_candidate_by_low_stats` pass their registers through to the callee; their parameter counts were taken … | N |  |
| 190 | `ai_score_a_counter_target`: the decompiled `-300` adjustment for field `0x1bd9` clears positive values (`if (0 < x) x = 0`), which looks like a lost … | N |  |
| 191 | `ai_choose_declared_card_name` (kind `0x4d`) tests a fixed Graveyard-list word (`0x09e2aa80 + side * 0xb3c`, one word before the list) instead of the … | N |  |
| 192 | `ai_score_target_for_12e2` compares the re-simulated attack value with the LP of the side that takes the monster; the meaning of the three flag bits … | N |  |
| 193 | Kind-1 LP records are ignored when `ai_apply_lp_change_record`'s first argument is set; what that argument means is open. | N |  |
| 194 | The meaning of `duel_core_count_named_cards_both_sides` in `ai_filter_targets_for_1ba2` (targets are kept only when it returns 0) is unclear. | N |  |
| 195 | Confirm `0x09e2d1e0` = turn counter and `0x09e03088` = tried Extra Deck mask in PPSSPP. | N |  |
| 196 | `0x09e029ac + 0x09e02a6c`: the turn limit for cards `0x1c38`, `0x1309`, `0x10e7`, `0x10e0`, `0x10df`, `0x10d6` in the shared gate. Both words lie in … | N |  |
| 197 | Whether the chooser's ctx is always the current link `0x09e28e44` (the scorers read their thresholds from it); confirm with a breakpoint on any … | N |  |
| 198 | Meaning of the small selection codes 0-0xd in `ai_choose_hand_card_by_card(_b)`, of `0x09e29050` (compared with card `0x1c0b`) and `0x09e29064` (a … | N |  |
| 199 | The two chain counts `0x09e28e34` and `0x09e28e38`. | N |  |
| 200 | `0x09e27828 == 5` in `ai_handler_check_cost_1927` (working plan record 0 `+0`), and the meaning of attack-order record fields other than `+2` and … | N |  |
| 201 | `ai_choose_slot_for_ctx_raw` called with the opponent's side by three equip-type handlers: is that the target side of an equip that weakens, or a … | N |  |
| 202 | `ai_score_target_for_1e3f` and the five `void`-decompiled functions: confirm their return values in the disassembly. | N |  |
| 203 | `ai_is_ranked_card_with_low_atk(side)` is called with one visible argument from `ai_has_hand_monster_to_give_away`; it may take hidden register … | N |  |
| 204 | Meaning of the result sign and flag bit 0 of `ai_sim_current_attack` (used by the redirect and blocker functions). | N |  |
| 205 | `0x09e28624` / `0x09e28640`: read as the attacked side / slot (M); confirm in `battle.md`. | N |  |
| 206 | Slot flags word bit 10 (tested by several handlers) and bit 14 (set temporarily by `ai_handler_check_battle_1d1f`); slot word `+0x0c` (zeroed by … | N |  |
| 207 | `duel_core_submit_player_action` code meanings beyond the call sites. | N |  |
| 208 | Whether the 28-byte stubs pass more than the card id and cost count into their shared body. | N |  |
| 209 | Return values of `ai_choose_declared_type_0eb4` / `_1357` (void in Ghidra, tail-called). | N |  |
| 210 | Plan comparison: the logic and the header writes are read (see "Decision pipeline"); still open are the meaning of `+0x0c` (the evaluator word … | N |  |
| 211 | The interest records at `0x09e28014`: layout of the flag bytes `+6`..`+0x17` and which handlers read them. | N |  |
| 212 | The attack comparator `ai_is_better_attack_result` (`0x09d0c2e4`): the decompilation loses several assignments; the criteria order (result class … | N |  |
| 213 | The 12 KiB yes/no evaluator `0x09d95f5c` and the 17,700-byte attack evaluator `ai_eval_attack` (`0x09d06188`, 68-byte result record) are only skimmed. | N |  |
| 214 | Exact meaning of steps 3–5 and of `0x09d94740`, `0x09d899a8`, `0x09d8c79c` in the main loop. | N |  |
| 215 | Whether `0x09c038a8` is "card revealed" (the no-cheating claim for the opponent's hand); confirm at run time. | R | `verification/results/2026-10-26-sessionA-part1.md` A10. |
| 216 | Who reads the character-table bytes `+0x44`–`+0x74` (`BOOT 0x0885b4ac`, `0x0885b4fc`, `0x0885b56c`, `0x0885b5dc`); if a module outside the current … | R | `functions/world.md`, `functions/import-stubs.md`: no reader in any module. |
| 217 | `0x09e02cb0`, `0x09e02cb4` setters: set by the duel manager, meaning unknown. | N |  |
| 218 | The priority tables are exported and checked (`docs/formats/ai-tables.md`, `tools/ai_tables.py`). The shared handlers are named and classified … | W | Card-effect / AI fidelity workstream (`PORT-READINESS.md`). |

## `subsystems/audio.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 219 | Where the SHDS header is stored and its exact address (read `system_load_audio_modules`); dumping its attribute table would give every sound's type, … | R | `formats/sound.md` "SHDS sound header". |
| 220 | Whether any id is typed 0 (sequence) or 1 (sound script) in the attribute table, and which data they would read. | N |  |
| 221 | The stereo output filter `audio_effect_filter_stereo_s16` (`0x08870bc8`, skipped) and who enables output effects. | N |  |
| 222 | Hidden second arguments of `audio_load_duellist_extra_voice_bank` for the lose/draw cases, and of the 12-byte stop wrappers `0x0886c4ec`-`0x0886c510` … | N |  |
| 223 | ~~`0x0989d4c0`, `0x0989d490` and `0x0989d3e8` need names~~: created and named 2026-11-04: `thunk_audio_build_current_cutin_voice_queue`, … | R | Answered in the item. |
| 224 | Meaning of cue byte `+0x1e`, of the object flag bits `0x08`/`0x10` counted by `audio_get_sound_flags_state`, and of set-up byte `+0x190`. | N |  |
| 225 | ~~Stream flags `+0xe0`–`+0xe3` and the pause/resume candidates~~: read 2026-11-04: `+0xe0`/`+0xe1` are the stream echo send level and delay (copied … | R | Answered in the item. |
| 226 | ~~`0x088418f8` "stop the current track"~~: settled 2026-10-31. Its body is `audio_stop_sound(id, 0)`: it stops one sound id at once (no fade). The … | R | Answered in the item. |
| 227 | ~~`0x090dbc60` tests 15 sounds~~: settled 2026-10-31, no conflict. `shop_is_clerk_voice_playing` checks whether any of the current clerk's 15 voice … | R | Answered in the item. |

## `subsystems/battle.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 228 | `0x09e2bba0`: bit 0 suppresses `duel_core_battle_get_damage_calc_bonus` in simulated stats; bit 1 enables the after-battle sub-step of step 10. Who … | N |  |
| 229 | The meaning of `0x09e2d258` differs between readers: step 2 treats 0 as "cancelled", step 1 and the Main Phase treat 0 as "a menu/phase answer is … | N |  |
| 230 | Step 10: the attacker must already carry a kind-4 `0x16cb` marker to attack again, and the step posts the same marker again; whether the marker … | N |  |
| 231 | Battle record `+0x3c`: written by `duel_core_battle_is_destroyed`, read by `duel_core_battle_is_damage_prevented`; other readers not searched. | N |  |
| 232 | `0x09e29920` is used both as the `.ydq` equip-record count and as the count of the candidate list built by `duel_core_collect_list_activations` … | N |  |
| 233 | Player block `+0x108` (`0x09e2a630`), compared `> 3` for field card `0x1a0c` in `duel_core_battle_is_damage_prevented`, is not identified. | N |  |
| 234 | `0x09e2b168` (read as a side for card `0x1ba7` in step 6) lies inside player 1's block (`+0x104`); its meaning is open. | N |  |
| 235 | `duel_core_check_select_target_soul_exchange`: Ghidra shows the call to the saved filter `0x09e2d290` without arguments; the real argument … | N |  |
| 236 | `duel_core_end_phase_set_marked_monsters_face_down`: which table holds it (End Phase table `0x09e0107c` or the L4 list `0x09e010b0`) is not confirmed. | N |  |
| 237 | `duel_core_battle_check_replay` is decompiled without parameters although step 3 passes the attacking side; confirm in the assembly whether the … | N |  |
| 238 | Fix `formats/tutorial.md` (command `0x43` bits 14/15) after a PPSSPP check of one `.ydq` field card. | R | `formats/tutorial.md` (2026-11-03 correction). |
| 239 | Link duel: packet type meanings are read from the receiver only; the sender side and the acknowledgement protocol are not documented. | N |  |
| 240 | Confirm at runtime (PPSSPP): LP at `0x09e2a528`/`0x09e2b064`, the step sequence through `0x09e2d220`, and the damage records at `0x09e286e0` for one … | R | `verification/results/2026-10-26-sessionA-part1.md` A3, A4. |
| 241 | Resolved: the per-card modifiers and their order are in `stat-modifiers.md` and extracted by `tools/stat_mods.py`; record fields `+0x14`–`+0x30` are … | R | `stat-modifiers.md`, `tools/stat_mods.py`. |
| 242 | Record field `+0x40`: the meaning is established (effect negation of the battle-destroyed monster); open: what value 2 changes against value 1 (Ha … | N |  |
| 243 | Trigger codes queued by the steps: `0x1e2` (inflicts battle damage, step 7), `0x2a2` (after damage calculation, step 8), `0x002` (after battle, step … | B (P) | B1 (timing events). Static part settled in this audit: `formats/duel-runtime.md`, "Event codes by raiser"; the packed trigger codes follow the link layout of `chain.md`. |
| 244 | `duel_core_compute_duel_bonuses`: the name of each of the 82 bonuses (the result screen text table) and what `0x09e2d1f8` holds (compared with Skull … | N |  |
| 245 | Step 6 (`duel_core_battle_step_damage_calc`) and steps 5, 9 and 10 are only partly read; their rows in `tools/engine_ref_semantics.csv` stay L where … | N |  |
| 246 | Who writes player block `+0x24` (win reason 2, presumably deck-out); it is not referenced directly. | R | `duel_core.md` (draw command `0x56` handler). |
| 247 | The second record written by `resolve` when the attacker carries one of the piercing equips controlled by the opponent (`add_damage(A, A, …)`); the … | N |  |
| 248 | Event code `0x2a2` used by after-battle trigger registrations (`0x09c2c578`) and the other timing codes raised elsewhere (`0x03`, `0x04`, `0x08`, … | B (P) | B1. Static part settled: `formats/duel-runtime.md`, "Event codes by raiser"; computed codes need PPSSPP G1. |
| 249 | `0x09de0c98` (tested in steps 2 and 10; Last Turn related, hypothesis) and `0x09dd11dc` (step 2 sub-step 0) are not named. | R | `functions/duel_core.md` (`is_last_turn_battle`, `is_attack_optional`). |

## `subsystems/card_db.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 250 | See `docs/formats/cardinfo.md` for the open fields. | N |  |
| 251 | Pack contents and the restriction list are not in `cardinfo`: they are static tables in `gmodule/rel_shop.prx` (`docs/formats/packs.md`) and … | R | `formats/packs.md`, `formats/limit-list.md`. |
| 252 | Card effects: no effect data or script references are in `cardinfo`; the evidence points to per-card code in `rel_duel_eng.prx` … | R | `duel_effects.md`, `formats/card-effect-spec.md`. |
| 253 | `card/*.cip`: card images, format unknown. | R | `formats/cip.md`. |

## `subsystems/chain.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 254 | Confirm in PPSSPP: the 16-link limit (Session D of `docs/verification/ppsspp-plan.md`), the SEGOC order with two simultaneous triggers per player, … | R | Sessions A (A8, A9) and D (D1). |
| 255 | The exchange sort may reorder triggers with equal keys; the official rules let the player choose. Check whether the game ever asks. | R | `verification/results/2026-10-26-sessionA-part1.md` A9. |
| 256 | `0x09cdd74c` (building state 0): forced position changes for seven listed cards (`0x09dedadc`) before a chain starts; which cards and why. | R | `functions/duel_core.md` (`apply_forced_positions`). |
| 257 | Slot flag bits 1 and 4 of field slots in the chain context (bit 4 "send to the Graveyard after the chain" is H; bit 1 and command `0x38` are not … | N |  |
| 258 | Event codes `0x23` (link that cannot be responded to) and `0x24` (activation without cost) need their raisers identified. | N |  |
| 259 | The copied-effect layout (`+0x06` bit 0 with data at `+0x18`, i.e. in the next link slot) and Trap of Darkness's shifted target indexing. | N |  |
| 260 | `duel_effects_is_activation_locked` is now read in full (`effect-helpers-values.md`); `duel_core_chain_collect_auto_responses` is only summarised; … | N |  |
| 261 | What the value 2 returned by 274 slot `+0c` handlers (`duel_effects_cond_return_2`) means for the callers that distinguish it. | N |  |
| 262 | The second-level path `0x09c941a8`, which calls the same activation, target, negation and resolve helpers outside the state machines (AI simulation … | R | `duel_effects.md`, `functions/duel_effects.md` (`duel_effects_resolve_15fd`). |

## `subsystems/container.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 263 | What the disc wrappers `0x0881e2c4`, `0x0881e378`, `0x0881e448` add over plain `sceIo` calls (retries, sector alignment?). | N |  |
| 264 | Contents of the root-directory table at `*0x08920cac` (filled at runtime by `0x0881d574` and `0x0881d63c`); root index 5 is used for `cardinfo`. | R | `formats/system-runtime.md`, `modules.md`. |
| 265 | ~~`0x08822774` returns a pointer into a member name from which the four-character extension is read; confirm whether it is `strrchr(name, '.')`.~~ It … | R | Struck in the doc; `functions/container.md`. |
| 266 | The file-index comparator `0x0881dfd4` also calls `system_strcasecmp`, so disc paths are probably matched case-insensitively; confirm by reading the … | N |  |
| 267 | Who calls `container_gzip_decompress` (through which pointer table), and who inflates the loose `field/*.gz` EHP files. | N |  |
| 268 | ~~Ghidra cannot create the function at `0x0881d8f4`~~: settled 2026-11-04. It is a real 8-byte exported entry, `container_resolve_path_lbn(buf, root, … | R | Settled in the item. |
| 269 | `.cip` card-image containers in `card/` (732 MiB, magics `CIP`, `CPM`, `CPL`, `CPJ`); `BOOT.BIN` references them as `card/cardh_<lang>.cip` among … | R | `formats/cip.md`. |
| 270 | The `snd/` sound bank (`SP\0\0`, 132 MiB). | R | `formats/sound.md`. |
| 271 | ~~Whether `gmodule/*.prx` are overlays loaded on demand.~~ Answered in `modules.md`: they are loaded on demand, either as the single current scene … | R | `modules.md`. |

## `subsystems/deck.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 272 | What deck slot 0 holds, and which slot `save_get_partner(0)` (`0x088550c8`) returns for the current partner (`deck_get_member_slot` gives slot 1 for … | R | `formats/save.md` "Deck slots". |
| 273 | Answered 2026-10-30: recipes 462–660 are never loaded (set-up codes and draft blocks, `deck.md`), and the owner id is the story character id. Still … | R | `formats/save.md`, `formats/character-table.md`. |
| 274 | See also the list at the end of `docs/formats/deck.md`. | N |  |

## `subsystems/dialogue.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 275 | Which request polls `0x09105348` and `0x09105350` (presumably 13 show and 12 release). | N |  |
| 276 | `dialogue_draw_text_to_screen_edge` (skipped): read from the disassembly. | N |  |
| 277 | `dialogue_map_language_index` (`0x08e9eee0`) and `dialogue_get_location_map_name` (`0x08eadd3c`) decompile to empty bodies; their return values need … | N |  |
| 278 | The `random_case` jump table `0x08eb3f3c` targets. | R | `formats/story.md` (`random_case`). |
| 279 | Which side of the screen windows 0 and 2 are. | N |  |
| 280 | Opcodes 50042, 50100 and 50154 are read (`dialogue_op_if_setting_b0_bit3`, `dialogue_op_mark_card`, `dialogue_op_prefetch_bgm`; `story.md`). BOOT … | N |  |

## `subsystems/duel-phases.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 281 | Battle steps 2–10, timing events `0x0d`–`0x14` and the timing-queue consumer are now documented in `battle.md`; the remaining battle questions are … | R | Pointer to `battle.md`. |
| 282 | Whether the first player's draw on turn 0 is skipped (not seen in `duel_core_step_draw_phase`; the skip conditions there are card- and flag-based). … | R | Session B. |
| 283 | The meaning of player-block flag `+0x120` bit 23 (skips Draw and Main steps; hypothesis: "skip this turn") and bit 0 (skips the draw). | N |  |
| 284 | ~~`0x09dd0b88`: not named~~: `duel_core_can_end_battle_phase`, documented in the 2026-11-03 round (`battle.md`, "Large procedures documented in the … | R | Struck: `duel_core_can_end_battle_phase`. |
| 285 | The turn-limit mechanism around `0x09e2d1e4` and duel mode 2. | R | `duel-phases.md`, `battle.md` (win reason 11), `formats/tutorial.md`. |
| 286 | Confirm the phase values and the Battle-step index at runtime (PPSSPP breakpoint on writes to `0x09e2d1e8` and `0x09e2d220`). | R | Session A A1, A4. |

## `subsystems/duel_core.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 287 | Slot flag bits 22, 23 and 27: "has attacked", "no attack left" and a per-phase flag are inferred from their readers (M); find the writers. | N |  |
| 288 | Event-word bits 25–30: the Type-specific bits are set for Types `0x14`, `0x15` and 9, but their readers were not identified. | N |  |
| 289 | The Type `0x15` test on the opponent's battle record in send-batch state 2 and in `send_battle_destroyed_cards`: the banish-by-battle cards it gates … | N |  |
| 290 | The counter `0x09e2d238` (limit 10) in `set_slot_negated` and `apply_forced_positions`, and `0x09e2d23c`, `0x09e2d240`: loop guards or a real rule? | N |  |
| 291 | The direction of each forced position in `apply_forced_positions` (which cards force Attack and which force Defense) is read from the compare logic … | N |  |
| 292 | `timing_event_allows_card_response` returns at once on event codes 1 and 5 (duelist kind 1, the CPU), so it does not look at later events in the … | N |  |
| 293 | The last two arguments that `duel_core_filter_valid_attack_target` passes to `is_valid_attack_target`, and the pass-through arguments of … | N |  |
| 294 | The extra duel result values 1–3 used by `record_duel_result` (`0x09e02cb0`). (The function `0x09be26f4` it calls is `duel_core_update_duel_records`, … | R | `duel-phases.md`; `formats/duel-runtime.md` (`0x09e02cb0`, settled in this audit). |
| 295 | The rest of the player structure (`+0x34`–`+0x11f` besides the field slots, `+0xa0c`–`+0xb3b`). Life Points at `+0x00` are established statically … | N |  |
| 296 | ~~Argument packing of the field-movement commands and the states of the send batch processor~~: packing in "Locations and card movement"; the batch … | R | Struck. |
| 297 | Summoning and the action menu: see the open questions in `summon.md`. | N |  |
| 298 | ~~The states of `duel_core_chain_step`~~: answered in `chain.md`. (Phase values and the turn state machine: `duel-phases.md`.) | R | Struck: `chain.md`. |
| 299 | The remaining event codes in chain links (`0x23` and `0x24` are partly understood, `chain.md`). | N |  |

## `subsystems/duel_effects.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 300 | `duel_effects_get_controlling_side`: what the three modes mean exactly (0, 1, 2), and why the walk is skipped while card `0x1632` is active. Confirm … | N |  |
| 301 | Collect-negation state words 10–13 (player-0 effects `0x1351`, `0x1350`, `0x134f`, `0x134e`) and word 14 (`0x12bf`): which cards these are, and why … | N |  |
| 302 | `duel_effects_update_negated_slots` decides with flag bit 9 (always negated) and slot byte `+0x02` bit 6. Neither writer has been found. | N |  |
| 303 | `duel_effects_resolve_15fd` state `0x75`: Ghidra shows a test on the return value of the void helper `duel_effects_update_negated_slots_default`. … | N |  |
| 304 | `duel_effects_resolve_146b`: the meaning of `0x09e2bba0` bits 0–1 and of command `0x19` with `b = 1`. | N |  |
| 305 | Link byte `+7` bits 1–7 count stored target values next to the target count in byte `+6`. Document how they differ in `chain.md`. | N |  |
| 306 | Target-choice list modes (`duel_core_open_card_list` mode 6 + n, `0x27` + n, `0x2a`, `0x2b`, `0x48`): give each a meaning in `ui.md`. | N |  |
| 307 | `duel_effects_target_choice_shared_0eb7_x31` reads the list mode from an uninitialised register for ids outside its chain. Check whether all 31 users … | N |  |
| 308 | `duel_effects_is_activatable_in_window` (`0x09bf2910`): what event codes `0x0d`–`0x16` mean as response windows. The response-window event list is … | B (S) | B1. Read in this audit as the Damage Step activation rule (`formats/duel-runtime.md`); the fallback path of `duel_effects_can_respond_in_window` is not traced. |
| 309 | `duel_effects_cost_tribute` and `duel_effects_activation_shared_1298_x19` are reached through tables and a handful of callers. List their … | N |  |
| 310 | `duel_core_special_summon_impl` position argument 2 (default of `0x09c78804`, used by `0x09c908bc`, `0x09c826b4`): the player's choice of position? … | N |  |
| 311 | `0x09e2991c`, cleared by `0x09c78804` for 12 cards before the Deck list opens: auto-pick or list mode flag? | N |  |
| 312 | Byte `0x09e290bc` (bit 1 side, bits 2-5 slot) read after a summon by `0x09c7eca8`, `0x09c826b4`, `0x09c83368`: is it "zone of the last placed card"? … | N |  |
| 313 | Engine commands `0x58` (`0x09cb6bd4`, a = 0x0d, b = Deck instance) and `0x60` (`0x09c89e10`, a = counter, b = zone): handlers not yet identified here. | R | `functions/duel_core.md` (`0x58`); `0x60` minor. |
| 314 | Command 8 = declaration display (above): confirm the case stub in the dispatch table `0x09e00944`. | N |  |
| 315 | Slot flag bit 25 of the attacking monster (`0x09c7d6a8`) and slot flag bit 13 set by `0x09cb13ec`: meanings unknown. | R | B3: slot bit 25 = attacker of the current attack (M-H), bit 13 = monster placed as a Continuous Spell, `formats/duel-runtime.md`, "Player and slot flag bits". |
| 316 | The per-entry word at player `+0xa0c` (`0x09e2af34 + index x 2`) used by `0x09c87ea0` for a banished card's return (low byte 0x40, … | N |  |
| 317 | `0x09c7e0f8` sets bit 0 of the responded link's byte +6, which `chain.md` documents as the copied-effect flag; its meaning in that use is open. | N |  |
| 318 | `0x09c8cab8` decrements `0x09e28f64` and waits for zero without initialising it: is the counter reset by the chain driver before each resolve (then … | N |  |
| 319 | `0x09cc1a14`: card 0x1db4 may start with 1 valid target but its loop asks for 2; intended or a bug of the original? | N |  |
| 320 | `duel_effects_classify_link_targeting` (`0x09bf6f50`) returns classes 0-3 for the AI; their meaning (no target / one / several / other) is not … | N |  |
| 321 | `0x09bfeca8` (get_spell_immunity): a 0x1693 link from the same side assigns 2 instead of OR-ing it, discarding earlier per-card bits; check against … | N |  |
| 322 | Event codes `0x12`, `0x16`, `0x19`, `0x1a`, `0x1b`, `0x1c`, `0x20`-`0x22` are used by many conditions but are not in the timing-code table of … | B (P) | B1 (same enumeration). |
| 323 | `duel_core_draw_cards` returns its count in `v0` that Ghidra shows as `extraout_v0`; its prototype says `void`. | N |  |
| 324 | `0x09c7ac70` reads Deck entry 0 right after posting a draw: confirms that the draw is a queued command and entry 0 is the next card drawn (to verify … | N |  |
| 325 | Byte `+1` bit 6 of a list entry is compared with a side in `0x09c88730` (original owner?). | N |  |
| 326 | The flag word `0x09e28f84` (`0x09c66390`) and `0x09e2bba0` bits 0-1 (`0x09c5ae2c`, `0x09c80380`, `0x09c87a78`). | N |  |
| 327 | What each handler slot and each of the four tables means; which wrapper serves which duel phase. Slots `+04`, `+10`, `+14` and the selector are now … | R | Answered in the item via `chain.md`. |
| 328 | Chain building, spell speed, negation and once-per-turn tracking: see `chain.md` and its open questions. | R | `chain.md`. |
| 329 | The card structure (`card + 0` id, `+2`, `+3` selector bits, `+0x15`): this is WP4's central data structure and should be typed in Ghidra next. | N |  |
| 330 | The per-player, per-slot state at `0x09e2a56c` (`player × 0xb3c + index × 0x14`): presumably the field/zone state. | R | `duel_core.md`, `ai.md`. |
| 331 | Classify the `BOOT.BIN` compare chains (AI? deck rules?). | N |  |

## `subsystems/effect-classification.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 332 | The meaning of the batch mode bits `0x20000`, `0x4000000`, `0x10000000` and `8`, and of the slot-mask global `0x09e2bba4`. | N |  |
| 333 | Commands `0x52`, `0x55` and `0x39`–`0x3a`/`0x41`, which effect handlers reach often (Sangan; Snatch Steal, Premature Burial), are not yet documented. | R | `functions/duel_core.md` handler rows. |
| 334 | Per-card resolution inside family handlers is done by `tools/family_split.py` for the resolve slot. Left open: state carried between the steps of a … | N |  |
| 335 | Player flag bit 0 (Time Seal, Fenrir) and slot flag 8 (Skill Drain): their meanings would turn these flag-only records into categories. | R | `battle.md`; `set_slot_negated`. |
| 336 | Commands `0x07` and `0x08` (UI-only handlers `0x09dbc66c`, `0x09dbc6d8`) are reached by 15 and 42 records (Crush Card Virus, Painful Choice); they … | R | `functions/duel_core.md` (UI-only commands). |

## `subsystems/effect-helpers-deck.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 337 | Filter bit `0x10000` (`0x09c02b48`) is now read as a targetability guard (`search-filters.md`); open: the card `0x1e74` it tests (absent from … | N |  |
| 338 | 35 builder records take part of their filter from `param` (`duel_effects_get_candidate_param`); joining that compare chain with … | N |  |
| 339 | `duel_effects_get_candidate_param`: the remaining context fields it reads (`ctx+8`, `+0xa`, `+0xc`, `+0x14`). | N |  |
| 340 | Request modes 7 and `0x0e`: the per-card filters inside `0x09c111a8` and `0x09c12b98`. | N |  |
| 341 | Who sets player flag bit 3 ("Deck must be shuffled"): presumably viewing or searching the Deck; confirm in PPSSPP. | N |  |
| 342 | `duel_core_add_deck_card_to_hand` sends the card to the Graveyard when adding is forbidden; check whether any caller reaches that branch in play. | N |  |
| 343 | Commands `0x28`, `0x52`, `0x53`, `0x58`, `0x59`: argument packing beyond what is used here, and UI events `0x13`, `0x17`. | N |  |
| 344 | The 8-byte list `0x09dec554` is now known to hold candidate builders; the other two unexplained lists (`0x09dfe500`, `0x09e010b0`) remain as in … | N |  |

## `subsystems/effect-helpers-misc.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 345 | Prompt-request kind 7 (`0x09c14284`) and the meaning of UI events 3 (command 7) and `0x2a` (mode 9 picks). Kinds 4 and 8 are Great Shogun Shien's … | N |  |
| 346 | Command `0x28` with a non-zero location and reference 0 (`duel_core_post_show_location`): what the presentation layer shows. | N |  |
| 347 | Mode `0x0d`: whether every caller declares an Attribute (the prompt is the Attribute one, message `0xf2`) or only reuses its mask mechanism. | N |  |
| 348 | `card_db_fusion_allows_substitute`: the reading "no Fusion substitute" for the eleven listed Fusions is a hypothesis; the flag is only consumed by … | N |  |
| 349 | `card_db_get_turn_counter_rule`: the sign convention (positive own turns, negative both players' turns, `0xffff` open-ended) needs a runtime check. | N |  |
| 350 | `duel_core_raise_attack_event`: the meaning of timing event `0x12` (raised with the packed attacker and target). | B (P) | B1 (`0x12` is the attack event, settled in this audit; readers' argument use is per card). |
| 351 | `duel_core_get_slot_activation_kind` and `duel_core_flag_face_up_copies` (slot flag 7): the meaning of the returned kinds and of the flag. | N |  |
| 352 | The 87 records still partial reach no effect category; they need categories (new `effect_categories.csv` rows or per-card reading), not names. | W | Card-effect / AI fidelity workstream (`PORT-READINESS.md`). |
| 353 | `card_db_get_special_summon_condition_class` (BOOT `0x0886354c`): what classes 1-5 mean (stays L until a caller is read). | N |  |
| 354 | Resolved: `0x09be2eac` is `duel_core_compute_duel_bonuses`; its body was repaired with `tools/ghidra/FixJumpTableFunction.java` (`battle.md`, … | R | `battle.md` "Function boundaries". |
| 355 | `duel_core_check_duel_condition` / `duel_core_was_card_used_in_duel`: which game feature the condition index at `+0x290` belongs to (duel bonuses or … | B (S) | B2: decode the condition switch of `duel_core_check_duel_condition` (`0x09be3bc0`) and the writers of the challenge index (record table word `0xa4`). |
| 356 | `duel_core_is_destruction_substitute`: the BOOT list `0x08861d2c` and card `0x1f0d` (unreleased) are not identified. | N |  |
| 357 | Resolved for the battle functions (third round). Still L: `duel_core_summon_step_flip`, `duel_effects_can_target_slot`, … | N |  |
| 358 | Resolved (sixth round): the unnamed blockers of the fifth round are named (`duel_effects_resolve_magical_hats`, … | R | Resolved in the item. |
| 359 | `duel_core_begin_select_tributes`: the meaning of its arguments `a`/`b` and of selection state 8 outside Ritual and Tribute selections. | N |  |
| 360 | Resolved (sixth round) for the records whose state has a traced reader: `state_effect:<kind>` (`card-effect-spec.md`). Resolved (seventh round): the … | R | `formats/card-effect-spec.md`. |
| 361 | `duel_effects_get_link_affected_sides`: which bit is the own side when a link targets both, and why some cards return 0 regardless of targets. | N |  |

## `subsystems/effect-helpers-movement.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 362 | Confirm in PPSSPP the flag bits marked M (`0x8`, `0x10000`, `0x4000000`, `0x10000000`) and the deck index convention of command `0x3f` (0 = top, … | N |  |
| 363 | `0x09c1f548` (the per-slot pre-check of the executor) and `0x09c1fb50` (called at the end of every `send_field_card`) are not read in full. | N |  |
| 364 | The auxiliary masks `0x09e2bbac`, `0x09e2bbb0`, `0x09e2bbb4`, `0x09e2bbb8` of the executor: their exact roles in the replacement prompts. | N |  |
| 365 | Marker kinds of control change (1, 5, `0x11`) and how they map to "until the End Phase" and "while equipped". | N |  |
| 366 | `duel_core_return_graveyard_card_to_deck_ex`: whether `top = 0` means "shuffle" (index 1) or "bottom". | N |  |
| 367 | The remaining pending-action kinds (selection helpers) belong to the hand/deck helper families and are not covered here. | N |  |
| 368 | Commands `0x39`, `0x3b`, `0x41`, `0x4b`, `0x4d`, `0x55` are posted by these paths but their handlers were not read. | R | `functions/duel_core.md` handler rows. |

## `subsystems/effect-helpers-predicates.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 369 | Slot flag bit 2 (required clear for an "active" lock or effect source in many helpers) and bit 8 (ignored locks in `duel_core_is_zone_usable`, forces … | N |  |
| 370 | `duel_core_is_zone_usable`: the `u16` array at player `+0xa0c`, iterated with the banished-count word `+0x1c` and matched on low byte `0x40`; which … | N |  |
| 371 | `duel_core_is_entry_properly_summoned`: confirm that entry byte 1 bit 7 is "properly Special Summoned" with a PPSSPP trace of a Nomi monster sent to … | N |  |
| 372 | `card_db_can_be_special_summoned` (`0x08864ff8`): the 2,784-byte body was only partly read (spirits and Gladiator Beast Spartacus return 0; a list of … | N |  |
| 373 | `card_db_get_flip_kind`: what value 2 (Kinka-byo, Mecha Bunny, Royal Keeper, the flip spirits …) means to the summon code. | N |  |
| 374 | Archetype 60 (`0x08862fec`) tests ids missing from the English database; check the Japanese database. | N |  |
| 375 | Command `0x28`: the two uses (reveal/target number, and `c = 0xffff` for targets after the fifth) should be confirmed in its handler. | N |  |
| 376 | The card request posted by `0x09c0f55c` is read (2026-10-31): `duel_core_request_tribute_for_effect`, mode 9, Tribute of field monsters as a cost … | N |  |
| 377 | `duel_core_add_statistic`: map the statistic indexes (`0x34`/`0x35` Spell Counters) to the duel-record screen or save data. | N |  |

## `subsystems/effect-helpers-values.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 378 | Kind 1 vs kind 2: both expire identically and the stat builder treats them alike; kind 1 dominates player-wide flags (Waboku, Asura Priest, Berserker … | N |  |
| 379 | Command codes `0x39` and `0x3b` for the handlers `0x09db7540` and `0x09db7620` are inferred from the posters, not from the jump table `0x09e00944`; … | N |  |
| 380 | `BOOT.BIN` predicates `0x088664fc` (counter type 1), `0x088661a4` (turn duration), `0x08863438` (Flip threshold), `0x0885fb5c` (name match), … | N |  |
| 381 | The remaining pending-action types (5–10, `0x0d`–`0x10`, `0x14`, `0x15`) and their posters. | N |  |
| 382 | `duel_core_can_take_effect_damage`: the exact meaning of the second argument. | N |  |
| 383 | Per-card meanings in `duel_core_check_attack_restrictions` and `duel_effects_update_negated_slots` should be extracted as tables like the other … | W | Card-effect / AI fidelity workstream (`PORT-READINESS.md`). |

## `subsystems/field_3d.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 384 | `field_3d_set_duel_scene` (`0x0985b0ec`): 8 bytes; probably a jump into `field_3d_backdrop_set_scene` or a shared tail (disassembly needed). | N |  |
| 385 | `field_3d_call_draw_card_quad` (`0x09864ff4`) and `field_3d_start_material_send_fx` (`0x09862c44`): argument shuffling hidden by the decompiler. | N |  |
| 386 | Meaning of the value from `ui_get_zone_card_scale` used as texture scale `value / 64 + 1` in card effects. | N |  |
| 387 | EDRAM ramp textures: confirm the cel-shading hypothesis in PPSSPP (which models set hook byte `+0x08` bit 0, and how the ramp is sampled through map … | N |  |
| 388 | `field_3d_board_resync_piles` leaves objects that no engine entry claims on a stack-local list (they are not returned to the free pool): leak or … | N |  |
| 389 | `field_3d_cutin_collect_deck_card_ids`: the sign handling of the deck-size limit (cards 0x1a7f, 0x1c31, extra deck 0x1ab1) looks odd in the … | N |  |
| 390 | Member `texture/10500.txt` used as a GIM for generic avatars: format (nested EHP or list) not checked. | N |  |
| 391 | Bit 15 of the location code as battle position: confirm against `duel_core_view_get_slot_position` values. | N |  |
| 392 | `field_3d_draw_billboard_at`: how the computed billboard matrix reaches the GUM stack (VFPU registers). | N |  |
| 393 | The float constants that define several effects were not read (0x098c4ee4-0x098c5064, 0x098c5e48-0x098c5e64, 0x098cfb20 coin model ids, 0x098cfb30/40 … | N |  |
| 394 | Hidden float arguments: the lerp factor in `field_3d_update_deck_shuffle`, the bolt offset in the Mystic Plasma extra, the drift vector in the … | N |  |
| 395 | `field_3d_create_material_fx_task_with_card` (0x09868478): which register carries the zone-scale word it stores at +0x30 (skipped). | N |  |
| 396 | The first argument of the backdrop-extra creators (stored at +0, unused by the updates). | N |  |
| 397 | GE state indices used with `system_ge_enable/disable` (0..0x15) are the game's wrapper numbering; map them to GE commands (state 7 is enabled by the … | N |  |
| 398 | What `ui_test_set_draw_flags(8, -1)` tests before the change-over sound. | N |  |
| 399 | Whether the three LCG copies share a state word. | N |  |
| 400 | `field_3d_map_material_dd_callback`: which GE state is toggled (argument hidden) and what the four name substrings at `0x090fd16c`-`0x090fd184` are. | N |  |
| 401 | `field_3d_set_map_variant_group_mask` (`rel_field:0x090da484`): body lost in the decompilation; read the disassembly. | N |  |
| 402 | `field_3d_lookup_attach_offsets_a` (17 tables, `0x098d3e50`-`0x098d48b0`): which table is searched (hidden). | N |  |
| 403 | Cut-in loading block: is the 0x1c400-byte overlap for generic characters real (buffer 0x20c00 + 0x17b000 > stride 0x17f800), or are generic cut-in … | N |  |
| 404 | Backdrop archive slot `+0x10`: never set in the code read here, so the release-pending path may be dead. | N |  |
| 405 | `field_3d_get_cutin_sound_fx_timing`: ids 0x1bf, 0x24c, 0x294 set a start frame that is then overwritten (start = previous sound frame + 8); a bug in … | N |  |
| 406 | The off-screen render target `0x174000` used by anim24_ef (id 0x6a): what is read back from it. | N |  |
| 407 | Confirm in PPSSPP that anim3e_54's stencil mask keeps the effects behind the character. | N |  |
| 408 | Answered 2026-10-31 (static, high): `field_3d_update_model` advances 1.0 frame per game frame for backdrops and cut-ins, at a game rate capped at … | R | `field_3d.md` "Frame timing". |
| 409 | Answered 2026-10-31: the loader of `duel/bg/fmagic<id>.ehp` and the caller of `field_3d_apply_scene_etc` ("Field-spell backdrop manager"). | R | `field_3d.md` "Field-spell backdrop manager". |
| 410 | Which ids engine command `0x13` carries (the sender of draw command 7 is now known, "Field-spell backdrop manager"): field spell resolved, field … | R | `effect-helpers-misc.md`, `field_3d.md`. |
| 411 | ~~The change-over task `0x0987a604`~~: answered 2026-11-04 (batch 2 findings): 16 frames, a screen capture redrawn through a 31 × 21 swirl grid while … | R | Struck. |
| 412 | ~~Texture-mapping callbacks `0x0882ef50` / `0x0882f050`~~: answered 2026-11-04 (batch 1 findings, "Texture-map callbacks and the EDRAM ramp"): type 1 … | R | Struck. |
| 413 | ~~How the group mask `inst+0x64` reaches the draw hook~~: answered 2026-11-04: it is word 4 of the instance draw state `inst+0x54` passed to … | R | Struck. |
| 414 | The unread `-etc` tracks (84-track 13–19, 42-track 4–9). (The purpose of `.vtmt` is settled: lip-sync animation, `docs/formats/vtmt.md`.) | N |  |
| 415 | Role of `.tmf` (with `.ehf`, covered separately). | R | `formats/ehf.md`. |
| 416 | The remaining open fields listed in `docs/formats/tgm.md`. | N |  |
| 417 | The open questions of the 2026-11-04 batches (above, per batch): the state word of the cut-in effect random generators, float constants of the effect … | N |  |

## `subsystems/modules.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 418 | The third word that scene modules pass to `system_scene_register` (stored at `0x08920c30`): `BOOT.BIN` only writes it and clears it. Values are … | N |  |
| 419 | Who loads `rel_select_card`, `rel_field` (as a library) and the tools in `rel_labo`/`rel_story`: their ids are computed at runtime; trace in PPSSPP. | N |  |
| 420 | `0x0884c63c` loads utility modules `0x100`/`0x101` (network). `0x0884c898` queues a module load through `0x0881d9fc` and starts it: which module … | N |  |
| 421 | Why the six `*_starter` scenes and `rel_sdchrviewer` are in the tables but not on the disc (cut content or another region's disc); what … | N |  |
| 422 | The memory map at runtime: where the heap ends and how much room the scene slot has, needed for a 3DS memory budget. A savestate in each major scene … | N |  |
| 423 | The PPSSPP export mixes symbols of modules that were loaded at different times; an export taken in each scene would give clean per-module bases. | N |  |

## `subsystems/movies.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 424 | Which 3DS decode path plays the converted movies with enough margin (needs a measurement on hardware). The install-time conversion itself is done … | N |  |
| 425 | Call sites of `system_movie_play` in `rel_title`, `rel_story` and `rel_duel_draw`: when the opening starts (boot, after an idle timeout on the title … | N |  |
| 426 | What selects between the base and the `_a` movie names, why `ouijaboard_death` has no file on this disc, and whether a localised variant per language … | N |  |
| 427 | A PPSSPP check of the playback timing (`docs/verification/ppsspp-plan.md` has no movie check yet). | N |  |

## `subsystems/save.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 428 | The meaning of the `ms_import` records for the game (download, trade or another save) is not established. | N |  |

## `subsystems/sdk.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 429 | ~~PPSSPP saw about 17,500 more function entries in user memory outside `BOOT.BIN`; map each range to its module.~~ Mapped in `modules.md`: … | R | Struck. |

## `subsystems/shop.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 430 | ~~`0x0973ad50` vs `0x090fad50` and the other references "outside the module image"~~: settled 2026-11-04. `rel_shop`'s program header gives a memory … | R | Struck. |
| 431 | ~~Who writes the high nibble of `0x090faa70` and bit 0 of `0x0973ad50`~~: `shop_lib_start` (weekday) and `shop_init_clerk` (system flag 4), settled … | R | Struck; `formats/shop-rules.md`. |
| 432 | The argument of `shop_set_clerk_animation` in clerk state 1 is hidden (presumably 2); clerk state 5 sets state 0 while the offset is below 0x7c, … | N |  |
| 433 | The argument the caller passes to `shop_advance_opening_cards` (presumably the frame step) and the `passes` argument of `shop_get_cosine_eased_ratio` … | N |  |
| 434 | Where the reveal-effect LCG state lives (the decompiler shows a read through address 0). | N |  |
| 435 | What `system_scene_set_field_8c(2/4)` does when the leave question is shown. | N |  |
| 436 | The colour-0 screen rectangle drawn under alpha function 7 by `shop_draw_reveal_effect_large` (stencil or alpha mask?). | N |  |
| 437 | Cell width of `shop_draw_small_digits` size variants 1 and 2 (hidden register). | N |  |
| 438 | Rarity 2 plays no reveal sound; check whether that is intended or another value is used. | N |  |
| 439 | What bit 0 of `0x090facf6` changes in the pack states. | R | `shop.md`, `formats/shop-rules.md`. |
| 440 | ~~Five "empty" functions~~: answered 2026-10-31 (round 2) from the instructions: they are tail calls Ghidra lost. `0x090d2d8c`, `0x090de328` and … | R | Struck. |

## `subsystems/stat-modifiers.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 441 | Confirm in PPSSPP: words 6/7 of the stat block for a monster with an equip, a field spell and a temporary boost, and the record pool at `0x09e2c7cc`. | N |  |
| 442 | ~~The argument packing of command `0x35`~~: the posters (`duel_effects_attach_effect_to_slot` `0x09c150ec`, `duel_core_add_counters`) give `a = slot … | R | Struck; `effect-helpers-values.md`. |
| 443 | Kinds 1 vs 2 (no distinguishing reader found), 4 vs 5 and 6–9 (which effects create which). Kind 3 holds counters of types 13–19. | N |  |
| 444 | Counting helpers of the self chain: `0x09c01cb8` `duel_core_count_graveyard_by_race`, `0x09bf9578` / `0x09bf94a0` … | R | `functions/duel_core.md`. |
| 445 | Why the Reverse Trap test reads only player 0's player-wide list. | N |  |
| 446 | `0x09c0a174` (no direct callers; builds a 2 × 11 "affects" matrix with `0x09c09e00`) is presumably the UI's "which cards affect this monster" view. | N |  |
| 447 | How Kazejin/Suijin reach ATK (handlers). The A-Counter penalty: `duel_core_get_a_counter_penalty_count` (`0x09c00514`) returns the monster's … | N |  |

## `subsystems/summon.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 448 | ~~The command codes of the handlers without a known poster~~: read from the jump table `0x09e00944`: `duel_core_cmd_show_duel_result` `0x05`, … | R | Struck. |
| 449 | `duel_core_step_apply_lp_change`: who calls it (thunks of the LP commands `0x23`/`0x24`/`0x25`?) and what cause `b` = 2 means (it records `0x14c0` … | R | `functions/duel_core.md`. |
| 450 | `duel_core_get_procedure_material_rule`: confirm that the filter address is returned in `v0` (Ghidra shows `void`). | R | `functions/duel_core.md`. |
| 451 | Card `0x1f32`: slot flag bit 8 gates the "Level 2" question and bit 7 stores the choice; confirm in PPSSPP. | N |  |
| 452 | Player flag bits 22 (more than 99 Special Summon placements, counter `0x09e2d240`), 24 (own monster sent to the Graveyard), 25/26 (spell/trap … | R | B3 settled statically (2026-11-04): player bits 22/24/25/26 and slot bits 10/13/15/19/28/30 with writers and readers, `formats/duel-runtime.md`, "Player and slot flag bits". Optional confirmation: PPSSPP G5. |
| 453 | The statistic indices of `duel_core_add_statistic` (`0x11`–`0x40`) should be mapped to the duel-record screen. | N |  |
| 454 | The step-0x16 controller check `duel_core_enforce_slot_controller` (returns non-zero while it is still working; what it enforces is not read). | R | `functions/duel_core.md`. |
| 455 | Bit 20 (`0x00100000`) of the player flags word `+0x120` is set by a face-up Normal Summon together with bits 16, 17 and 21 (seen in PPSSPP, … | R | B3: bit 20 = Main Phase 1 no longer at its start (set for the turn player by a summon, Set, position change or activation while the phase is 2; only reader Cold Wave), `formats/duel-runtime.md`, "Player and slot flag bits". |
| 456 | Confirm the action-code/bit mapping and the reason codes in PPSSPP (breakpoint on `0x09dcf950`, watch `0x09e2d288`), and find the `rel_duel_draw` … | N |  |
| 457 | ~~Action 10 and command `0x22`~~: answered on 2026-10-31. Action 10 is surrender; `duel_core_cmd_concede_duel` (`0x09dbfe9c`, command `0x22`) sets … | R | Answered in the item. |
| 458 | Synchro: what card `0x1f32` is (not in the European cardinfo; may count as Level 2) and why slot flag bit 7 is reset when it is used as material … | N |  |
| 459 | Fusion: the tie rules of `duel_effects_match_fusion_material` (ambiguous slot matches); the bodies of Future Fusion `0x09cbc3f4`, Fossil Fusion … | R | `functions/duel_effects.md`. |
| 460 | Ritual: the role of `0x09e28f68` for Machine Angel Ritual and the other exact-total spells should be confirmed in play; Samsara's (`0x19da`) effect … | N |  |
| 461 | The about 30 card-specific preparation routines called from `duel_core_summon_prepare`. | R | `effect-helpers-misc.md`. |
| 462 | Slot flag bit 3 is set by a Gemini summon, while `duel_effects.md` describes bit 3 as disabling effect handlers; reconcile (Gemini monsters are … | R | `summon.md` "Slot flag 3 during a summon": bit 3 is the transient effects-off flag of every placement (command `0x2b` type 2 sets `0x200008`, `0x44` clears bit 3); the Gemini-summoned state is slot flag bit 14 (`duel_core.md`). |
| 463 | Player word `+0x120` bits 20, 22 and 24 (set by several movement commands). | R | B3: bits 20, 22 and 24, `formats/duel-runtime.md`, "Player and slot flag bits". |
| 464 | The summon-negation window `0x09c32e54` (the command `0x61` handler is read, table above). | R | `chain.md` (`chain_summon_window_step`). |

## `subsystems/system.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 465 | The newlib heap size: the KiB count at `0x0889ed5c` (read it from the BOOT.BIN data) gives the size of the `UserSbrk` block and hence the upper bound … | N |  |
| 466 | `0x0881ca74` `system_vfpu_restore_rand_state`, `0x0881b8c8` `system_vfpu_vector4_min`, `0x0881be70` `system_vfpu_matrix4_build_projection`, the … | N |  |
| 467 | `system_vfpu_color_from_rgb565`: the decompiler shows the green field as `(c & 0x7f) >> 1`, which cannot be the 6-bit field at bits 5–10; check the … | N |  |
| 468 | `system_display_init` ignores its first argument (`config[5]`) in the decompiled body; confirm in the disassembly whether it is passed on (for … | N |  |
| 469 | Who sleeps on the thread id at `0x08920c44` (woken by `system_wakeup_scene_thread` from `system_wait_frame`)? | N |  |
| 470 | `__svfscanf_r` (`0x0881593c`) and its two wrappers: recover the jump table at `0x088783a4` if scanf turns out to be used (no game caller of … | N |  |
| 471 | ~~`rel_duel_draw` targets without a function in Ghidra (`0x0989c638`, `0x0989c6c4`)~~: created 2026-11-04 as `thunk_ui_update_turn_timer_blink` and … | R | Struck. |
| 472 | `system_net_check_beacons`: the beacon-age comparison uses a timestamp the decompiler shows uninitialised (probably a field of the … | N |  |
| 473 | `system_get_word_08ac2574` / `system_set_word_08ac2574` (title/tutorial list value passed to title state 0x18) and `0x08ac2578`: meaning still … | N |  |
| 474 | The second sceFont handle `0x08d6ea6c` and the character table `0x08879220`: which font (Latin vs. Japanese) and which characters are flagged. | N |  |
| 475 | Hello-data layout beyond the fields used here (0xb8 bytes; +0x80 must be 1 for a room to be listed). | N |  |
| 476 | ~~rel_title `system_title_register_scene` passes `0x09aedfc0`, outside the module image~~: settled 2026-11-04. The module's program header gives a … | R | Struck. |
| 477 | ~~Import stubs whose target has no function in Ghidra~~: all created and documented on 2026-11-04 ("Registry hygiene, round 5"). | R | Struck. |
| 478 | Heap size and placement (needed later for memory-budget estimates on 3DS). | N |  |
| 479 | From the 2026-11-04 round: the thread that sleeps on the id at `0x08920c44`; the meaning of `0x08ac2574`/`0x08ac2578`; the value of the newlib heap … | N |  |

## `subsystems/tag_duel.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 480 | ~~The high half of the waiting-area word `+0x14` (`u16 +0x16`) changes at every swap (seen in PPSSPP: `0xaa`, `0x57`, `0x23`, `0x12`, `0x81`); … | R | Struck. |
| 481 | At the first swap of side 1 the waiting kind 0 was copied into the active kind word, yet the CPU played that turn and the word read 1 again later: … | R | `functions/tag_duel.md` (`tag_duel_handle_partner_swap`). |
| 482 | ~~Confirm that the third list is the extra deck, and read the end of `tag_duel_swap_active_duelist` (where the saved lists go).~~ The Extra Deck … | R | Struck. |
| 483 | Which entry points start a tag duel versus a single duel (`duel_core_start_mode2`/`_mode3`, `0x09e2d1f4` = 2 or 3). | R | `battle.md` (`setup_engine_for_duel`), `formats/tutorial.md`. |
| 484 | How the partner AI and the "tag" commands (asking the partner, partner's turn) are handled; whether cards that refer to "your partner" use the … | R | `ai.md` "Personality and tag partners". |

## `subsystems/ui.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 485 | **Frame step (stage `+0x08`).** `ui_ehf_draw` steps the timeline at most once per new tick (draw-parameter word 0 differs from player `+0x1c` and … | R | Finding, not a question (ui.md). |
| 486 | **Records.** Object −1 removes the instance at the record's depth; depth 0xffff makes it a pure wait. Placing always allocates a new instance whose … | R | Finding, not a question (ui.md). |
| 487 | **Looping.** A clip reaching its frame count rewinds its cursor, sets frame and wait to 0 and **releases all its children** (Flash semantics). The … | R | Finding, not a question (ui.md). |
| 488 | **Interpolation.** Keys are relative to the placed frame. Before/at the first key the first key is held, at/after the last key the last key is held; … | R | Finding, not a question (ui.md). |
| 489 | **Channels** (`ui_ehf_eval_track`, flag word `+0x24`): bit 0 translate, bit 1 scale (a, d), bit 2 skew (b, c), all `s16 × step` added to the base … | R | Finding, not a question (ui.md). |
| 490 | **Base matrix** (`ui_ehf_track_base_matrix`): rows `(a, b, 0, 0)`, `(c, d, 0, 0)`, `(0, 0, 1, 0)`, `(tx, ty, 0, 1)` (row vectors), i.e. `x' = a·x + … | R | Finding, not a question (ui.md). |
| 491 | **Colour transform** = 8 ints: multiply RGBA (256 = 1.0), add RGBA. Nesting (`ui_ehf_concat_color_transform(out, parent, own)`): `mul = own.mul × … | R | Finding, not a question (ui.md). |
| 492 | Does `ui_bind_ehf` (`0x0881e56c`) clear the texture slot word `+0x0c` before `ui_ehf_resolve_texture`/`ui_ehf_apply_tmf_flags`? If not, characters … | N |  |
| 493 | Exact GE result of the add-colour trick (emissive + two lights, lighting mode 1) and whether it equals `texel × prim × multiply + add`; verify in … | N |  |
| 494 | Units of the draw-parameter rotation `+0x10` (`system_matrix4_post_rotate_z_s16`) and the order semantics of the `system_matrix4_post_*` helpers. | N |  |
| 495 | Behaviour of the bit-5-only tracks of `ryusen01.ehf` (add bytes read beyond the stride). | N |  |
| 496 | Remaining window descriptor fields (`+0x30`, `+0x48` usage) and the skin piece tables at `0x088790d0`/`0x08879148`. | N |  |
| 497 | The state table `0x090fe6f0` (main PDA entries → state) and the meaning of the three PDA submenu/five-entry command codes for … | N |  |
| 498 | What the HUD target-info values `0x09106940`-`0x0910694c` represent (three 0-999 counters with icons and a sprite-digit value). | N |  |
| 499 | Whether options item 2 (volume setting 2) is intentionally hidden in every language. | N |  |
| 500 | Which sub-screens the deck-options requests (`0x08ebee08` = 2, 1, 0) start, and which save flag `save_*_card_byte1_flag` is (shown as a 2-state icon … | N |  |
| 501 | What sort mode 9 and 10 group by (icon set C and a 2-digit number). | N |  |
| 502 | The meaning of the three trunk display options (save byte `0xb0` bits 6-7). | N |  |
| 503 | What `0x08ebf1a0` bit 15 (alternative background `0x8025`) signals. | N |  |
| 504 | The 12-byte `*_split_text_lines` wrappers and the 8-byte `ui_help_disable_ruby` need the disassembly; the help scroll-bar part wrappers and cursor … | N |  |
| 505 | The name argument of the help picture path (`0x08ebe384` format) and the picture-load callback `0x08eb5fe8` (not a function in Ghidra). | N |  |
| 506 | `ui_draw_sprite_number` styles 1 and 2 take their digit width from a register the decompilation does not show. | N |  |
| 507 | Function table `0x08eb93f0` (result page draw routines): entry 0 is the summary page. Page navigation only cycles pages 0-2, using the DP words … | N |  |
| 508 | Statistics record (`tail + 0x3c`): word +0x358 is printed on the summary page (hypothesis: DP total after the award, low). Which statistic does each … | N |  |
| 509 | `save_get_byte_16e10` and `+0x12` (entered from scene 2): seen only as "partner present" layout tweaks and team-label sources. Their meaning in the … | N |  |
| 510 | Kinds 0-7 of the versus screen: which module creates them (the underground or link flows through `libduel_mgr_rel`?). | N |  |
| 511 | Tag-duel load gate: the 0xc0-byte block copied per player record for character category 5 (setup record +0x230) is presumably a custom … | N |  |
| 512 | Turn-order seed `setup + 0x188`: is it the duel engine's RNG seed? A link duel shares it between peers, which suggests it is. | R | `battle.md` (`+0x188` RNG seed). |
| 513 | Skipped tail-call wrappers (`*_draw_text_fit_width_px`, `*_draw_text_px`, `*_draw_text_box_px`, `ui_duel_result_draw_text_to_screen_edge`, … | N |  |
| 514 | `ui_stub_noop_duel_hud_hook` (`0x09858afc`, 20 bytes): empty or a lost tail call to a text drawer? (check the instructions; the names are visibly … | N |  |
| 515 | `ui_draw_badge_number_at_position`: its callers pass only two visible arguments; where the badge number (third argument) comes from needs the … | N |  |
| 516 | `ui_draw_card_texture_quad_scaled` (`0x09856400`, skipped) and `ui_duel_create_value_popup_task_moving` (`0x09871dcc`, skipped): argument order … | N |  |
| 517 | `ui_create_wait_object`'s update callback `0x09863a94`, the card display callbacks `0x0986221c`/`0x09862214`, the arrow draw callback `0x0985d004` … | N |  |
| 518 | `0x0989ddb8` (the duel-view test used by `ui_update_zone_highlights` to force highlight kind 7): named `duel_core_view_is_zone_usable_lenient` on … | R | Answered in the item. |
| 519 | Meaning of `ui_get_zone_card_scale`'s ranges 0x10-0x100, 0x200-0x2000 and 0x8000 (unreachable with side 0/1). | N |  |
| 520 | `0x098e6664` (per-side deck-set index for hand/Extra/Deck objects): confirm it is the active tag duellist. | N |  |
| 521 | Which counter types 0x00-0x13 map to which counters (Spell Counters, A-Counters, ...): needs the engine side … | N |  |
| 522 | The end of `ui_begin_lp_panel_projection` (last texture state writes) is garbled in the decompilation. | N |  |
| 523 | ~~The event number and argument kind of each of the 75 records of `0x098d0180`~~: dumped on 2026-11-04 ("Draw command dispatcher" above). | R | Struck. |
| 524 | The rows of the mode table `0x098d1f5c` for modes 2, 3, 4, 0xa and 0xc (which functions are enter/draw/update/exit). | N |  |
| 525 | Meaning of the HUD request fields `+0x0c`-`+0x40` and whether `+0x24` is a sound id. | N |  |
| 526 | Duel set-up buffer byte `+0x190` values 2 and 5 (auto-answer/tutorial modes?) and word `+0x854` (disables prompt input). | N |  |
| 527 | The 10-word location list `0x098d0504` used by `ui_auto_submit_action_mask_800`. | N |  |
| 528 | Close test `0x098abfb8` of the flag message and the signal `0x09bde00c`. | N |  |
| 529 | Pad state word `+0x18` (waited for before leaving the options mode). | N |  |
| 530 | The six helper routines of `ui_draw_polyline_frame` (`0x098a7398`-`0x098a7950`) and the list callbacks at `0x098b4acc`, `0x098b5530`, `0x098b5550`, … | N |  |
| 531 | What set-up modes 2, 3 and 6 (`+0x190`) mean to `rel_duel_mgr`, and what `+0x193` selects for modes 2 and 3. | N |  |
| 532 | Which scene 0xe (state 0x2a, after the save check, with soft-reset inhibit) and 0x17 (state 0x27) are. | R | `modules.md` scene table. |
| 533 | Game kinds 1, 3 and 4 of the wireless rules (card-gift room variants; which side sends) and the meaning of the room value words 0x1d/0x1e. | N |  |
| 534 | Whether state 0x2f really falls through into the 0x30 update (decompiler artefact or bug). | N |  |
| 535 | Title menu items 2 and 3 (sub-state 9 and external cards) with an item count of 2: is the count raised elsewhere? | N |  |
| 536 | The meaning of the save option flags and setting bit fields behind options rows 0-11 (names in `option_msg` 1-11; needs the strings or a PPSSPP … | N |  |
| 537 | `ui_title_draw_wireless_rules_summary` has no caller in this half; check whether a function-pointer table in the second half references it. | N |  |
| 538 | The 20/16/28-byte functions that decompile to a bare `return` while receiving text arguments (`ui_title_deck_draw_text_fit_width_px`, … | N |  |
| 539 | Meaning of rule values 0-4 of the communication duel rules (only the string ids are known; rule 0 = 1 means tag duel). | N |  |
| 540 | Which world/save meaning the duel setup panel modes 5-10 have outside the title (modes 8-10 are only reached when the panel is created by other code … | N |  |
| 541 | `0x08eea424`/`0x08eea428` are reset to -1 by every enter function; their use is in the first half. | N |  |
| 542 | What sets the partner menu's OSK flag +0x148 to 1 and who advances name-entry step 1 -> 2 (not in this half). | N |  |
| 543 | The OSK parameter block field at `0x09aedfec` (result) and the halfword language table `0x08ee8c38` contents. | N |  |
| 544 | Which menu state uses which of the 41 `rel_title` functions that read `tushin_msg`, and the selector `k` of the 25 `ui_title_get_message` calls whose … | N |  |
| 545 | The duel HUD's `ddstrtbl_<lang>_idx.bin` / `_body.bin` pair: how `rel_duel_draw` indexes it (not through the headed accessor). | N |  |
| 546 | The minigames' shared result helper (`mini_result`) receives its table from the caller's buffer; its indices are constants but the table is only … | N |  |
| 547 | Whether the unreferenced archives above are really unused (a file-access trace in PPSSPP across all scenes would settle it). | N |  |
| 548 | ~~What `0x0881e6a4` sets up~~: answered 2026-11-04: width and height for the camera-clip path only; the centre floats are unused. | R | Answered in the item. |
| 549 | ~~How `ui_bind_ehf` patches the display lists~~: answered 2026-11-04: it does not; the player reads the primitive records itself, and `ui_bind_ehf` … | R | Answered in the item. |
| 550 | ~~Who plays a layout~~: answered 2026-11-04 (batch 1): the caller's draw block word 0 is a tick, the layout advances once per new tick at stage … | R | Answered in the item. |
| 551 | See also the open questions in `docs/formats/ehf.md`. | N |  |
| 552 | From the 2026-11-04 round (details in the per-batch open questions above): the `ddstrtbl` index pair, the meaning of the room value words 0x1d/0x1e … | N |  |

## `subsystems/world.md`

| # | Question (shortened) | Class | Settles / answered in |
| --- | --- | --- | --- |
| 553 | Who writes occupancy value 5, and what the pool-entry word `+0x20` (eviction lock) is. | N |  |
| 554 | The meaning of the HUD words `+0xdc/+0xe0/+0xe4` from the request-7 record, and of NPC `+0xcc`. | N |  |
| 555 | The NPC wander step (jump table `0x090f80cc`) and the analogue-stick word at pad `+0x18` used by the island map. | N |  |
| 556 | Whether `world_clip_character_motion` reads the fifth value its callers pass (run flag / 0); the decompilation shows four parameters. | N |  |
| 557 | `world_draw_object_list` disables texturing while R is held (pad bit 0x200) — intentional or debug leftover. | N |  |
| 558 | Field action 1 (prompt 128 confirmed) is not in the `world.md` action table; its story-side handling needs checking. | R | `world.md` "Field action → state". |
| 559 | `field-maps.md` says pick-ups end the walk with "field action 15"; in this code a pick-up enters command **state** 0xf (card get) and action 15 is … | N |  |
| 560 | Content of story block `+0x3570` (opcode 50141) and the exact role of `0x08ecd980` beyond "first map entry after a new game" (field request 27). | R | `formats/story.md` (opcode unused). |
| 561 | ~~The BOOT functions `0x0885bddc`, `0x0885bd4c`, … (scene parameter blocks of modes 5–11)~~: settled 2026-11-04, see "Mini-game parameter blocks" … | R | Struck. |
| 562 | Duel result values in deck block `T + 0x20` (1 = win?) and the meaning of tally word d. | R | Settled in this audit: `formats/duel-runtime.md` (`0x09e02cb0`: 1 won, 2 lost, 3 draw); optional confirmation G4. |
| 563 | System flag `0xc`/`0xd` (mode 8 return): which game mode it is. | R | `world.md` "Next scene mode", `modules.md`. |
| 564 | Whether the restart branch of `world_story_init` (location `0xe`, player position) is reachable. | N |  |
| 565 | Field requests 27 and 30 (table above). | N |  |
| 566 | The meaning of the field result codes 7 and 9–15 (other game modes). (The island-map list is the set of disabled destinations, `field-maps.md`.) | R | `world.md` "Field action → state". |
| 567 | Where the item menu's counts live: the counters at field state `+0x94` are only decremented in `rel_story`; the field module's Item menu (and the … | N |  |
| 568 | Which driver result queues `(301, 8/9/10/11, …)` (duel win/loss, events) and the exact role of the story flags 21–29 in `world_driver_next_event`. | R | `world.md` "Back from a story duel". |
| 569 | The character-table bytes `+0x44..+0x74` in `BOOT.BIN` (no caller found; not gifts). | N |  |
| 570 | (The source of the shop value `*(0x090faa70) >> 4` is the weekday, settled 2026-11-04.) The meaning of the save counters `+0x11444…`, and of … | R | `formats/save-minigame-blocks.md`, `functions/save.md`. |
| 571 | The exact EXP table (`0x08855e08` was not read in full) and the month/date mapping of calendar `+0x08`/`+0x20`. | R | `functions/save.md`. |
| 572 | Confirmed in PPSSPP (Session C): the pairing (neighbouring spots, weekly), the gift points, the partner word, DP. Answered from the code: flag 2 is … | R | Answered in the item. |
