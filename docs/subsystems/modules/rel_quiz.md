# `rel_quiz`

Module document of the 2026-11-04 round 6 (all game modules imported; `../modules.md`). English, evidence-based: the sections below come from reading every function of the module in the Ghidra decompilation; hypotheses carry a confidence.

| | |
| --- | --- |
| File | `PSP_GAME/USRDIR/gmodule/rel_quiz.prx`, 74,908 bytes, plain ELF (relocatable PRX) |
| Slot | scene 0x18, id 0x2b |
| Exports → importers | — |
| Role (catalogue) | Minigame: quiz (`quiz/*.ehp`, `mini_qz_*`). |
| Runtime base | unknown; imported at image base 0x0, so addresses are module offsets |
| Registry ids | `rel_quiz:0x…` |
| Functions | 197 own functions, 197 documented in this round (world 155, ui 42); tables in `../functions/<group>.md`, section `rel_quiz` |

## Key functions (largest)

| Address | Prototype | Summary (first sentence) |
| --- | --- | --- |
| `0x000009cc` | `int world_quiz_game_update(void *game)` | Per-frame quiz state machine on game +0x04, after reading the pad and running the task updates: 0 stops all sounds, 1-frame black fade out, black screen on, -> 1; 1 waits for the archive loader to be idle, creates the play tasks, loads the language result slot, allocates a 1 MiB buffer (+0x0c) and opens the card8 CIP reader on it (+0x10), creates title kind 0 (+0x20), sets a 60-frame timer (+0x14), plays sound 0x7ac2, -> 2; 2 counts the timer down, clears the black screen, pauses the title's update at its frame 0xd until the CIP reader is ready, the loader idle and the timer expired, then resumes it, -> 3; 3 when the title is done destroys it and starts a 16-frame white fade in, -> 4; 4 when the fade is done clears the power flags, -> 5; 5 when the main task's finished byte is set requests the CIP reader to stop, -> 6; 6 when the reader is idle creates the 0x28-byte result task (world_quiz_result_task_construct; +0x28; priority 6), hands it the main task's score (world_quiz_result_task_start) and plays track 5 with fade, -> 7; 7 result status 3 -> 8, status 2 (play again) fades out, sets the black screen, destroys the tasks and returns to 0; 8 reports completion. |
| `0x000015d4` | `void * world_quiz_wheel_draw_number(void *wheel, void *list, short *pos, int value)` | Draws a number badge on a wheel card: clamps value to 999, counts its digits (1-3), builds in inline vertex data one badge quad (template 0x0000e14c, texture wheel +0x40 = mini_qz_parts02, rect 1) and one quad per digit 30 px apart (digit UVs from world_quiz_get_parts01_rect, digit table 0x0000e994; texture wheel +0x3c = mini_qz_parts01) with the wheel perspective (scale = (cos(fov/2) * 480 / sin(fov/2)) / (pos z + radius + that), centre wheel +0x34/+0x36) and issues two system_ge_draw_array calls with primitive 4 (triangle strip: 4 vertices for the badge, 4 per digit for the digits). |
| `0x00001cb0` | `void * world_quiz_wheel_draw_card(void *wheel, void *list, short *pos, void *record)` | Projects three 4-vertex quads for one wheel card at the 3D position pos (templates 0x0000e08c card art, 0x0000e0cc frame, 0x0000e10c overlay) with the wheel perspective; draws the frame with mini_qz_parts01 (wheel +0x3c), then the card art of record +4 (u16 card id) from the CIP reader when its image is cached (card_db_cip_write_image_texture); when record +0x12 is 1 draws the overlay quad and, if record short +0x14 is positive, the number badge (world_quiz_wheel_draw_number). |
| `0x000021c0` | `void world_quiz_wheel_draw(void *wheel)` | Draw entry of the card wheel: when the CIP reader is ready, both parts gims are loaded and the main task exists, computes ten card positions on a vertical ring (radius wheel +0x20, angle from +0x24 - 2 * step +0x28, tilt +0x30) for question indices +0x44 - 2 .. +0x44 + 7 (wrapping to -1 past 0xde1), sorts them back to front by z, draws each valid one (world_quiz_wheel_draw_card with record main +0x20 + index * 0x18) on GE layer 4 with linear filtering, sets +0x3a when every visible card's art is cached and, while the spin flag +0x48 is set and all art is ready, turns the ring by 1 degree per frame until a full step, then clears the flag and advances +0x44. |
| `0x00002dec` | `void world_quiz_hud_draw(void *hud)` | Draw entry of the HUD task: when all four HUD resources and the main task exist, enables the font shadow and draws on GE layer 4: the category header for the current question's category byte +0x11 (world_quiz_hud_draw_category at 0x89, 6), the correct/answered tally (world_quiz_hud_draw_tally at 0x89, 0xf3), the remaining time in seconds rounded up ((frames + 29) / 30, world_quiz_hud_draw_timer at 0x140, 6), the score (world_quiz_hud_draw_score at 0x136, 0xf3), the two answer markers (parts01 sprites 5/6 at 0xc3, 0x66 and 7/8 at 0xc3, 0x8f, the second of each pair when that choice was pressed), and both answer choices at (0xcc, 0x25) and (0xcc, 0x91) with the drawer for the question type record +0: 0 card name, 1 card frame, 2 level, 3 ATK, 4 DEF, 5 spell/trap icon, 6 attribute, 7 race (values from record +0x08 and +0x0c). |
| `0x00004e68` | `int world_quiz_main_play_step(void *main_task)` | One frame of play: returns 0 when the wheel task does not exist. |
| `0x0000548c` | `int world_quiz_make_frame_question(void *main_task, void *record)` | Fills a card-frame question: the correct slot gets card_db_get_frame(card id); the other slot a random frame from the 7-entry table 0x0000eb64 that differs from it and is not its look-alike pair (frames 3 and 8 exclude each other, as do 0 and 1). |
| `0x00005f28` | `void world_quiz_make_question(void *main_task, int index)` | Generates question record index (its card id is already set): the type pool and the points/category bytes (+0x10/+0x11, both set to the tier) depend on the current combo +0x16ed4: below 6 type 0 (name), tier 1; 6-10 a random type from the 2-entry table 0x0000ebb8, tier 2; 11-15 3 entries at 0x0000ebc0, tier 3; 16-20 4 entries at 0x0000ebcc, tier 4; 21-25 5 entries at 0x0000ebdc, tier 5; 26-30 6 entries at 0x0000ebf0, tier 6; 31-35 7 entries at 0x0000ec08, tier 7; from 36 any type 0..7, tier 8. |
| `0x00006584` | `void * world_quiz_popup_draw_number(void *popup, void *list, short *pos, int value)` | Draws value (clamped to 999, 1-3 digits) scaled by popup +0x34 around pos: the parts02 badge (atlas entry 1) to the left, then each digit as the parts01 entry from the 10-entry table 0x0000ec4c, 19 pixels apart before scaling, vertically centred 11.5 pixels up. |
| `0x0000751c` | `void * ui_quiz_menu_ctx_draw_nine_slice(void *list, int kind, int colour, short x, short y, short width, short height)` | Draws a nine-slice box of width x height at (x, y) from the 9-part table at 0x0000f20c; the colour selects the texture offset (kind 2: colours from 0xc, u = ((c - 0xc) % 6) * 10, v = ((c - 0xc) / 6) * 10; kind 0: u = (c % 6) * 10 + 0x17, v = (c / 6) * 10, colour 8 at (0, 0x74)); edges stretched to width - 9 / height - 9. |
| `0x00007d60` | `void * ui_quiz_menu_ctx_draw_number(void *list, void *ctx, int table_base, int table_offset, int glyph_base, int mode, uint value, uint min_digits, int align, short x, short y, short width, uint color, short scale_x, short scale_y)` | Draws a number with one mini_result string per digit (glyph_base + digit via ui_quiz_menu_ctx_get_message): mode 0 as many digits as needed (at least min_digits), mode 1 exactly min_digits, laid out right to left with a step of min(width / digits, scale_x); mode 2 a time in hundredths of a second with separator strings glyph_base - 5 at half step. |
| `0x000082e8` | `void ui_quiz_result_apply_score(int game, uint *score)` | Scores a finished mini-game into the result block 0x0040f3cc and the save, exactly as rel_title ui_mini_result_apply_score: stores the score values (+0x28 / +0x2c / +0x40) and the main score in world_get_minigame_score(); base DP (+0x30) per game 0 score / 50, 1 / 150, 2 score / 2 plus ceil(score[1] / 100) when score[2] is set, 3 / 10, 4 score[1] * 20 + score[2] * 150, 5 / 50, 6 / 10; each new record (records 0, 1, 2+3, 6, 5+4, 7, 8 for games 0-6) adds 200 DP (+0x34), stores it and sets +0x44/+0x46 and the save record-table byte +0xec + record; total +0x38, EXP +0x3c = total / 25, save_add_dp, save_add_duelist_exp and 400 more DP on a level up; games 3 and 4 store the from-story flag +0x1c (ui_quiz_result_is_from_story). |
| `0x00008d6c` | `void * ui_quiz_result_draw_panels(void *list)` | With context image 0 bound draws the result panels: border box (0x3e, 0x3d, 0x165 x 0xa4), two sections at y 0x40 and 0x79 with title bar and value box (nine-slice colours 1 and 4) and two rows each (colour 3 label box 0x10d x 0x10, colour 1 value box 0x49 x 0x10, plus the new-record mark part 0xc at (0x14a, y + 3) in the first section when +0x44/+0x46 is set), two three-slice bars with value boxes at y 0xb3/0xc8 and the bottom bar (colour 8, y 0x100, 0x1e2 x 0x12). |
| `0x00008fcc` | `void * ui_quiz_result_draw_labels(void *list)` | Draws the result texts from mini_result_<l>.bin: section titles 1/3 and value headers 2/5 (white, scale 0xe), row labels by game (+0x20: 4 for games 0, 1, 3, 5, 6; 6/7 for game 2; 0x13/0x14 for game 4, the second only when +0x40 is set; second section 8 and 9 with unit 0xe in cyan), the totals 10 and 11 with units 0xe/0xf, the centred footer 0xc at y 0x102, then the values (ui_quiz_result_draw_values). |
| `0x00009384` | `void * ui_quiz_result_draw_values(void *list)` | Draws the six result values (+0x28..+0x3c) right-aligned at x 0x155 with digit glyph strings from 0x15 (ui_quiz_menu_ctx_draw_number): rows at y 0x54/0x67, 0x8d/0xa0 and 0xb9/0xce (19 or 21 pixels apart), widths 0x47 or 0x33, at least 6 digits for the first two and 5 for the others; the second value only for game 2 (as a time, mode 2) and game 4 (when +0x40 is set). |

## Purpose and flow

Card quiz mini-game, scene 0x18 (module id 0x2b). Two card-related answers are shown for a card whose art turns on a wheel; the player picks the upper or lower one before a 60-second clock runs out.

- Entry `world_quiz_module_start` (0x00000000) registers `world_quiz_scene_main` (0x38) / `world_quiz_scene_end` (0xe4) with argument block 0x0000f3a0.
- `world_quiz_scene_main` runs `world_quiz_init`, installs the frame callback 0x1b4 (draw) and leave callback 0x1e4, loops `world_quiz_update_frame` until done and returns with `system_scene_return(0x18, 0)`.
- `world_quiz_init`: 4 MiB heap on module memory +0xf3c0 (pointer 0x0040f3c0), 0x30-byte game object (vtable 0xf2d0, singleton 0x0040f3c8, pointer 0x0000f3b0).
- rel_quiz never reads a world parameter block (no `world_get_*_params` call): the quiz has no opponent.

Game state machine `world_quiz_game_update` (game +0x04):

| State | Action |
| --- | --- |
| 0 | stop sounds, black screen, -> 1 |
| 1 | wait for archive loads; create the play tasks; load the language result archive; 1 MiB buffer + `card_db_open_card8_cip` (+0x10); title kind 0; 60-frame timer; sound 0x7ac2 |
| 2 | title paused at frame 0xd until CIP reader ready, loads done and timer out |
| 3 | title done -> white fade in (16) |
| 4 | fade done -> power flags 0 |
| 5 | main task finished byte (+0x16ebc) -> stop the CIP reader |
| 6 | reader idle -> result task (priority 6), `ui_quiz_result_create(heap, lang result slot, 3, &score)`, track 5 |
| 7 | result status 3 -> 8 (leave); 2 -> destroy tasks, back to 0 (play again) |
| 8 | done |

Main quiz task (`world_quiz_main_update`, +0x16eb8): 0 waits for game state 5, start banner (title kind 1, sound 0x7abf); 1 banner done; 2 play (`world_quiz_main_play_step`) until time is up, then finish banner kind 4; 3 banner held at frame 0x14 until Circle (0x2000); 4 banner done; 5 finished.

Controls (`world_quiz_main_play_step`): Up or Triangle (0x1010) = upper answer (choice 0), Down or Cross (0x4040) = lower answer (choice 1). The clock (frames, 0xe10 at start) only runs while the wheel's card art is cached (when the UMD reports bit 0x20); power flags 0x70000 zero it. Tick sounds 0x7ac1/0x7ac0 each second, 0x7ac3 in the last 10 s.

Scoring (`world_quiz_main_judge_answer`): correct -> score += combo + question points (tier 1-8), combo + 1, correct count + 1, sound 0x7abd, combo pop-up when combo > 0; wrong -> combo = 0, time - 150 frames (5 s), sound 0x7abe. The score at +0x16ecc is the result screen's score (game index 3).

## Task framework

The module has its own small task system (also worth checking in the other mini-games):

- List head 0x0040f3c4 (a base task). Task base, 0x20 bytes: +0x00 update priority, +0x04 prev, +0x08 next (update list); +0x0c draw priority, +0x10 prev, +0x14 next (draw list); +0x18 update-enabled byte, +0x19 draw-enabled byte; +0x1c vtable.
- Vtable slots: +0x08 virtual delete(this, flags), +0x0c attach hook, +0x10 update, +0x14 draw, +0x18 detach hook. Lists are kept in ascending priority; `world_quiz_task_attach(task, upd_prio, draw_prio, before_equal, call_hook)`.
- Tasks: main quiz 0x16eec bytes (vtable 0xf33c, prio 0), HUD 0x30 (0xf320, prio 1), card wheel 0x4c (0xf2e8, prio 2), title/banner 0x90 (0xf304, prio 3, kind 4 at 5), combo pop-up 0x44 (0xf358, prio 4), result 0x28 (0xf374, prio 6).
- The empty functions and the vtable-only functions (reset/load/draw entries) are named after their position; which vtable slot each occupies is a hypothesis (medium) until the vtables at 0xf2b4..0xf374 are dumped.

## Key structures

Main task (offsets from the task):

| Offset | Meaning |
| --- | --- |
| +0x20 | 3554 (0xde2) question records of 0x18 bytes |
| +0x14d50 | 0x2166 bytes: 2 bytes per card id 0xe88..0x1f3a; bit 0 of the second byte = card already used |
| +0x16eb8 | task state |
| +0x16ebc | finished byte |
| +0x16ec0 | current question index |
| +0x16ec4 | wheel-spin latch |
| +0x16ec8 | time left in frames (start 0xe10) |
| +0x16ecc | score |
| +0x16ed0 / +0x16ed4 / +0x16ed8 | correct count / combo / answered count |
| +0x16edc, +0x16edd | answer 0 / 1 just pressed |
| +0x16ee0 | current banner task |
| +0x16ee8 | number of eligible cards |

Question record (0x18 bytes): +0 type (0 card name, 1 card frame, 2 level, 3 ATK, 4 DEF, 5 spell/trap icon, 6 attribute, 7 race), +4 card id (u16), +6 correct slot (0/1), +8 and +0xc the two answer values (text pointer, byte or short by type), +0x10 points, +0x11 tier/category (drives the background palette and the category header), +0x12 answered correctly, +0x14 combo at answer time (shown as a badge on the wheel card).

Question generation (`world_quiz_make_question`): cards are drawn once each (shuffled order) from ids 0xe88..0x1f3a that are valid, not race 0x16, not tokens, not 0x1ca4..0x1cad and not one of nine excluded ids. The type pool grows with the combo: combo < 6 only names (tier 1), then tables at 0xebb8 (2 types), 0xebc0 (3), 0xebcc (4), 0xebdc (5), 0xebf0 (6), 0xec08 (7) every 5 combo steps, and from combo 36 any type (tier 8). Wrong answers: another random card's name; a random different frame (frames 0/1 and 3/8 never paired); level x3 (< 4), x2 (4-5), /2 (>= 6); ATK x3 below 2400 else /2, 0 <-> unknown (0xffff); DEF same with threshold 2000; a random different icon / attribute / race.

Card wheel (0x4c-byte task): ring radius 800.0, 10 degrees per card, fov 170, tilt 77, centre (120, 136); draws 10 cards around the current question, depth sorted, card art through `card_db_cip_write_image_texture` from the card8 CIP reader; spins one step per answer.

## Files

- Archive loader with 13 slots (`world_quiz_loader_*`), table of {root, path} at 0x0000e024 (8 bytes per slot): slot 0 `quiz_data.ehp` (contains `mini_qz_bg0.gim`, `mini_qz_icon01.gim`); slots 1-6 per-language UI archives (`world_quiz_get_lang_ui_slot`: language 0..5 -> 1..6; contain `mini_qz_title.ehf` and the other banner EHFs named by the table 0xea18, `mini_qz_parts01.gim`, `mini_qz_parts02.gim`, `quiz_strtbl_<j/e/g/f/i/s>.bin`); slots 7-12 per-language mini_result archives (language 0,1,2,3,4,5 -> 7,8,10,9,11,12: the order of German and French is swapped relative to the UI slots). The exact path strings of slots 1-12 were not visible in the decompilation (read the table at 0xe024 from the binary).
- Loaded EHPs are bound when their first 3 bytes match the magic at 0x0000e968; release runs the extension handlers.
- Sprite atlases: 16-byte {u, v, w, h} float tables 0xe190 (parts01; digits at entries 0x10..0x19), 0xe360 (parts02), 0xe3a0 (icon01: level star 0x26, icons 0x16-0x1c, attributes 0x1d-0x25, races 0..0x15).
- `quiz_strtbl_*.bin` is read with `card_db_get_dictionary_word`: word 1 ATK label, 2 DEF label, 4-10 frame names, 0x24 unknown value, digit words from the table 0xeb3c, level words from 0xeae0.
- Sound tracks 0x2d4 and 0x2c8 are loaded for the module.

## Talks to

- BOOT: card database (`card_db_get_name/frame/level/atk_or_unknown/def_or_unknown/icon/attribute/race/is_monster/is_token/is_valid`, icon/attribute/race name strings), the card8 CIP image reader, `save_get_language`, EHF player, GE/font wrappers.
- Result screen: game index 3 -> mini-game record 6, DP = score / 10; `ui_quiz_result_is_from_story` (game 3 -> scene 0x18) sets the story flag, so from the story the result screen skips the retry window.

## Name mismatches

- 0x00007d4c has a twin line to BOOT `ui_draw_level_badge_text_fit`, but that name is already used by the identical stub at 0x000033a4 in the same module; named `ui_quiz_menu_ctx_draw_text_fit_width_px` after its rel_title counterpart.

## Open questions

- 0x000033b8 (8 bytes) returns a font scale used by the name answers; Ghidra shows an empty body (skipped). Probably a tail jump to a fit-scale helper.
- The vtable layouts at 0xf2b4, 0xf2d0, 0xf2dc, 0xf2e8, 0xf304, 0xf320, 0xf33c, 0xf358, 0xf374 (confirm which function sits in which slot).
- The strings behind the slot table 0xe024 and the banner EHF table 0xea18 (kinds 0-4: intro, start, wrong, correct, finish; medium).
- The meaning of the HUD tally label sprite index and the score label for languages other than 2 and 4 (hidden register arguments).
