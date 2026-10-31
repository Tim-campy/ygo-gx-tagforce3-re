# Partner chapter table (`rel_story.prx` `+0x2a10c`)

The table that decides which story record the partner's chapter plays next, and where. It is the backbone of the partner story: four stages ("chapters") of up to four steps each, gated by friendship points. Static analysis of `rel_story.prx` (capstone disassembly, 2026-10-30) cross-checked against the story bytecode (`script/story_scr_b.ehp`, `tools/story.py`) and the `BOOT.BIN` character table; not traced in PPSSPP yet. Tool: `python3 -I tools/world.py chapters <USRDIR> [--check] [-o out.json]` (JSON goes outside the repository or under `extracted/`).

Module offsets; runtime address = `0x08e9aa00` + offset, file offset = offset + `0x54`. Little-endian.

## Layout

64 rows of `0x110` bytes = 17 entries of four `i32` (17,408 bytes in total).

| Entry | Words | Meaning | Conf. |
| --- | --- | --- | --- |
| 0 | `kind, character, variant, alt variant` | Row header. `character`/`variant` select the row for a partner; `alt variant` (−1 = none) is a second variant that takes the same row. `kind`: 2 = the partner has a story of its own (rows 0–16, characters 2–8, keys 201–217), 0 = shared chapters with an ending of its own (rows 17–56, characters 9–45, chapter key 218, ending key 219), 1 = generic (rows 57–63, character word 5, 1, 2, 3, 4, 16, 15, variant −1). **`kind` is never read by the code**: it describes the row. | H (layout, code); M (`kind` meaning, from the data only) |
| `1 + 4(s − 1) + (t − 1)` | `location, a1, a2, a3` | Stage `s` (1–4), step `t` (1–4). `(a1, a2, a3)` is the key of the story record to queue (`world_queue_event`); `location` is the story location `L` (1–30, `field-tables.md`) where it plays. All four words −1 = empty step. On the disc every filled entry has `a2 = s` and `a3 = t` except the stage-4 step-4 ending (`(219, n, 1)`); `a1` is constant within a row apart from that ending. | H |

The only reader is `world_get_chapter_table_word(row, entry, word)` (`0x08eac0c4`, the only reference to `+0x2a10c` in the module): `+0x2a10c + row·0x110 + entry·16 + word·4`, no bounds check. A stage above 4 would therefore read the next row (stage 5 step 1 is the next row's header); the shipped records never get there (below).

Observed on the disc (`world.py chapters --check`, `failing: 0`):

- Step 4 is empty in rows 0–16; rows 17–63 hold the ending at stage 4 step 4. Steps 1–3 are filled everywhere.
- Every key exists in the story records. Row 2 (character 2 variant 2) points at twelve records `(203, s, t)` that are header + end only: that variant has no chapter story (consistent with the shop rule that unlocks packs 3–41 when every variant of characters 2–8 *except 2/2* has character-row bit 2, `world.md`).
- Every non-empty step-2 record opens with `scene_map L` equal to the entry's location (checked by the tool); 12 step-3 entries of the own-story rows name a location other than the step-3 record's scene, because step 3 normally follows the step-2 duel directly (below).
- The step-1 records of the shared chapters (`(218, s, 1)`) are empty (header + end), so on rows 17–63 queuing step 1 only advances the step; the 64 own-story step-1 records hold dialogue.
- In rows 57–63 only row 58 (character word 1) is ever selected; the seven rows are identical.

## Choosing the row

`world_find_partner_chapter_row()` (`0x08e9d25c`) takes the partner and variant (`world_get_partner`, `world_get_partner_variant`) and the partner's **category** (`world_get_character_category`, `BOOT.BIN` `0x0885aeb0`: the `i8` at `+0x08` of the character's variant-0 row, 5 when missing):

| Category | Characters (variant 0 rows) | Row |
| --- | --- | --- |
| 2 | 2–8 (main cast) | First row whose `character` equals the partner and whose `variant` or `alt variant` equals the partner's variant. |
| 0 | 9–45 | Same search. |
| 1, 3, 4, 5, other | 46–126 (1), 142 (3), 127–141 (4), 0–1 (5) | First row whose header word 1 is **1** (row 58), whatever the character. |

When the search finds nothing the function returns an uninitialised register (`s3`); on the disc this happens only for `(16, 1)`, `(37, 1)`, `(38, 1)`, `(39, 1)` and `(41, 1)`, which are presumably not offered as partners (low). It also calls `BOOT` `0x0885ae0c` (`+0x09` of the row) and discards the result.

## Looking up an entry

`world_lookup_chapter_event(stage, step, &loc, &a1, &a2, &a3)` (`0x08e9d08c`): stage ≤ 0 → all outputs −1, return 0. Otherwise reads entry `step + 4(stage − 1)` of the partner's row; any word < 0 → return 0 (empty). At **stage 4 step 4** and a partner of category 1, 4 or 5, `a2 += partner − 46`: the generic ending `(219, 41, 1)` becomes `(219, partner − 5, 1)`, so characters 46–126 each get their own ending record 219/41–121 (all 121 records 219/1–121 exist and contain `advance_counter` + `finish_partner_story`). Category 3 keeps 219/41. Categories 4 and 5 would ask for 219/122–136 or 219/−5..−4, which do not exist (they are non-duellists, `world_character_can_duel`; presumably never partners). Returns 1. (H, code; the per-character ending reading of the offset is M.)

`world_get_next_chapter_event(&loc, &a1, &a2, &a3)` (`0x08e9c868`) calls the lookup with the current story stage and chapter step and, while it returns 0, advances the step (`world_advance_chapter_step`) and retries, without a limit: a stage with four empty steps would hang the game (none on the disc).

## Progression state

In the field save block (story block `+0x345c`, `story_field_save_block`):

| Byte | Field | Code |
| --- | --- | --- |
| `+0x00` | Story stage 1–10. Init 1 (`world_init_calendar`, `0x08eaac3c`). +1 by opcode 50094 `advance_counter` (`world_advance_story_stage`, `0x08eab3c0`), capped at 10, which also sets the step to 1. | H |
| `+0x01` | Chapter step 1–4. Init 1. `world_get_chapter_step` (`0x08eab440`); `world_advance_chapter_step` (`0x08eab40c`): +1, back to 1 after 4. | H |

The **points cap** of the stage, `world_get_points_cap()` (`0x08eab450`), is the `i32` table `+0x2e528` indexed by the stage: `−1, 1000, 2000, …, 8000, 8000, 3` for stages 0–10. Friendship points are clamped to it (`world_change_char_points`), so the points can only reach `1000·stage` while the stage lasts.

Story state `+0x357c` (8 bytes, registered by the story init through `0x08ea560c`): word `+4` is the **partner talk pending** flag: set to 1 on each new day (`world_change_time`, `0x08ea066c`), cleared by the daily partner talk (`world_partner_daily_event`) and by a daily-step chapter event (`world_get_partner_talk_pending` `0x08ea563c`, `world_set_partner_talk_pending` `0x08ea562c`; M, code).

## When a chapter event is queued

`world_try_chapter_event(points, location, stage)` (`0x08e9cad0`), called by `world_select_partner_event` on every map entry (unless system flag 20 is set: then it only queues `(501, 1, 1)`), with the partner's points (`world_get_char_points`, `0x08e9d944`) and the current location:

1. `points ≠ cap(stage)` → return 1 (no chapter event). Stage 10 → return 1.
2. `world_get_next_chapter_event` (skips empty steps).
3. **Steps 1 and 4 (daily steps)**: if today is the day off (`world_is_day_off(0)`) or the partner talk is no longer pending → return 1. Else clear the pending flag, queue the key, advance the step, return 2. The location is not tested.
4. **Steps 2 and 3 (location steps)**: if the location differs from the entry's, or the time slot is 1 or 7 → return 1. Partner 7 at step 2 of stage 7, 6 or 5 also sets record flag 1 (off the map) on characters 2+3, 4+20 or 22+23 and record flag 2 on their duel-pair partners; unreachable with the shipped data (stages 5+ never run a chapter, below). Queue the key, advance the step, return 0.

`world_select_partner_event` returns 1 after a result 2 and 0 after a result 0; on result 1 it falls back to the daily talk (while the talk is pending) or a location remark (`world.md`).

Other places that use the table:

- **Island map**: `world_open_island_map` highlights the location of the next entry when the step is 2, the points are at the cap and the time slot is < 7, and sets system flag 56 (`world.md`).
- **After a chapter duel**: all 68 non-empty step-2 records end in a duel (`duel_rules … duel_then_*`; 47 directly, 21 in a follow-up reached by `goto`); no step-1 or step-3 record starts one. When the story module restarts after the duel (story init `0x08e9f3ac`, entry mode 4) and the step is 3, `world_queue_next_chapter_event` (`0x08e9c568`) queues the step-3 record at once and advances the step, then restores the location and player position from the duel work area. So step 3 is the duel's aftermath and normally plays without the location test (M: mode 4 read as "back from a duel" from the context only).
- **Ending**: when the event queue runs dry after the record `(218, 4, 3)` and the stage and step are both 4, `world_driver_next_event` (`0x08ea61c0`) queues the next chapter event, the stage-4 step-4 ending `(219, n, 1)` (H, code).

## Rules that follow from the data

- Stage `s` opens when the points reach `1000·s`. Step 1 plays on the first map entry of the next working day (an empty record on the shared rows); step 2 at the highlighted location (outside slots 1 and 7), and ends in the chapter duel; step 3 right after it. A stage's records (step 3 or the follow-ups 21–23/31 reached by `goto`) contain `advance_counter`: stage + 1, step 1, new cap. Losing points below the cap (for example with a disliked gift) blocks the chapter until they are back.
- `advance_counter` is in each of stages 1–3 of every row, and in stage 4 of the own-story rows together with `finish_partner_story`; on the shared rows stage 4 ends with `(218, 4, 3)`, which has neither, and the ending `219/n` has both. So **a partner story ends at stage 5**: stage 10 and the points caps of stages 5–9 (5000–8000) are not reached by the partner story itself. Opcode 50094 is used only in the 188 chapter records (`story.md`).
- **End**: `finish_partner_story` (50137) makes the driver (`world_driver_finish_partner_story`, `0x08ea2b38`) set the partner's character-row bit 2 (`save_set_character_flag_bit2`), unlock the partner's decks, and set story state **46**. State 46 (`world_state_start_staff_roll`, `0x08ea3984`, from the state switch at `+0x18f98` in `world_story_state_step`) closes the 12 field overlays and sets state 49 with the per-frame callback `0x08ea39e8` (creates the `HeapMovie` heap, then `0x08ea3a54` waits and sets state 48); state 48 (`0x08ea3a9c`) sets state 49 again with the callback `world_play_staff_roll_movie` (`0x08ea3ae8`, then state 50), which plays `movie/TF3_staffroll2_a.pmf` when the partner is character 2 and bit 2 is set for both of its variants 0 and 1, else `movie/TF3_staffroll_a.pmf` (H for the paths and the test; the save-bit reading "story completed" is M). So character-row bit 2 marks a partner whose story is finished, the bit the shop's partner packs test.

## Open questions

- What the game shows after the staff roll (state 48/50 and later) and whether the stage is reset for a new partner (only `world_init_calendar` writes stage 1, from the new-game paths `0x08e9fd90`, `0x08e9fe5c` and the system-flag-20 start `0x08ea343c`).
- Which characters the partner choice offers (decides whether the rowless variants and the category-4/5 offsets matter).
- The step-3 location test (when does a step-3 event start from the map rather than after the duel: a lost duel?). PPSSPP: watch field block bytes 0–1 across one chapter.
- Rows 57 and 59–63 and the header word `kind` have no reader; perhaps left over from a category-keyed design (low).
