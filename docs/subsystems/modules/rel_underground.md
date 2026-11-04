# `rel_underground`

Module document of the 2026-11-04 round 6 (all game modules imported; `../modules.md`). English, evidence-based: the sections below come from reading every function of the module in the Ghidra decompilation; hypotheses carry a confidence.

| | |
| --- | --- |
| File | `PSP_GAME/USRDIR/gmodule/rel_underground.prx`, 123,676 bytes, plain ELF (relocatable PRX) |
| Slot | scene 0x15, id 0x28 |
| Exports → importers | — |
| Role (catalogue) | Underground duel minigame: `underground/*.ehp`. Loads `duel_mgr` as a library and calls `libduel_mgr_rel`; calls scene 4. |
| Runtime base | unknown; imported at image base 0x0, so addresses are module offsets |
| Registry ids | `rel_underground:0x…` |
| Functions | 404 own functions, 404 documented in this round (world 397, ui 7); tables in `../functions/<group>.md`, section `rel_underground` |

## Key functions (largest)

| Address | Prototype | Summary (first sentence) |
| --- | --- | --- |
| `0x00002f84` | `void * world_underground_game_draw(void *game, void *list)` | Draws the game object on layer 1. |
| `0x00003870` | `void world_underground_game_state_choose_column(void *game)` | State 9: while no slide runs, confirm (with follow mode +0x124) closes the message and either plays 0x7a05 and goes to state 0xc (+0x04 clear) or shows message 0xd and goes to state 10; cancel re-centres the view on the player; in follow mode left/right (repeat, mask 0x80/0x20) moves the target column 0..4 and starts a 5-frame slide (sound 0x7a04), the direction button opposite to the walking direction (0x10 or 0x40 by floor parity) leaves follow mode; outside follow mode the d-pad scrolls the view by 16 px (x 0..0x1e8, y 0..0x4f0). |
| `0x000040c8` | `int world_underground_game_walk_player(void *game)` | Moves the player one step along the ladder. |
| `0x00004668` | `bool world_underground_game_handle_cursor(void *game, int enabled)` | Map input while walking. |
| `0x00005448` | `int world_underground_game_run_duel_event(void *game)` | Duelist event, substates +0x13c: 0 stops the BGM (fade 10) and shows text 0; 1 after 30 frames or confirm closes the text and starts a white fade-out; 2 when faded initialises (0x0000d99c) and starts (0x0000dadc(floor, LP, slot 0 > 3)) the duel object +0xa60; 3 when the duel ends (0x0000d9b0) reads deck_get_duel_setup_tail_block() +0x20 (result, 1 = won) into +0x150 and +0x28 (remaining LP) into LP +0x14 (capped at max) and the HUD; on a win increments the duels-won count +0x4c, deactivates the duelist (+0x134), recentres the view, restarts the floor music and resets the cursor (0x0000af34), on a loss sets player +0x38; ends the duel object (0x0000d9a8) and fades in; 4 on a win rolls a reward (world_underground_game_roll_duel_reward) into +0x144, picks a slot and applies it, then shows text 1 (results 2 and 8, substate 7), goes to 5 (result 0x10) or finishes; on a loss plays effect 0xe (substate 6); 5 shows text 1; 6 and 8 wait for the effect; 7 on confirm closes the text and refreshes the HUD, then plays the slot effect when result 8 raised a slot to its maximum. |
| `0x00005fa4` | `void world_underground_game_setup_floor(void *game)` | Builds the current floor: generates the ladder with 0x00008448(+0x04, floor, slot 3 > 3, slot 7 > 3), takes the duelist count +0x128 (0x00008754) and box count +0x12c (0x000087c0), clears the moving flag, enters follow mode, places the player at its column and at row 0x11 heading to 0x10 facing up on even floors or row 0 heading to 1 facing down on odd floors, centres the view, copies the target cell to the cursor, sets the floor view's floor, initialises the player (0x00009534), activates and initialises the duelists (0x0000aa90 with per-index words 0x00008760/8778/8790/87a8 and the player position) and boxes (0x00009a74 with 0x000087cc/87e4/87fc/8814) and deactivates the unused records, hides the cursor, initialises the HUD (0x00009da8 with floor, LP, max LP, tools, timer and slots) and the +0xb2c object (0x00011a00, timer == 0), and sets the scroll targets to the cursor cell. |
| `0x00006a28` | `void world_underground_game_award_random_card(void *game, int result)` | Builds a candidate list (up to 4275 ids on the stack) and appends a random one to the won-card list (+0x54 + count * 4, count +0x50 incremented). |
| `0x000073fc` | `void world_underground_game_show_text(void *game, int text)` | Opens a text window: finds the language string table (world_underground_get_strtbl_path) in archive 3, plays a sound (0x7ab6 for text 0, 0x7ab4 or 0x7a08 by result for texts 1/2/6, 0x7ab9 for 3, 0x7a08 for 4/5/7/8) and formats into the 0x100-byte buffer game +0xbb8 a dictionary word (card_db_get_dictionary_word): text 0 word 0xb, 3 0x27, 4 0x26, 5 0x22, 7 0x23, 8 0x24; texts 1/2/6 a word chosen by result +0x144 (0x2e..0x34, 0x28 for bad results with a second word 0x29..0x2d, the slot name from the table 0x00017bbc for result 8, or the last won card's name for card results). |
| `0x00007bd0` | `void * world_underground_game_draw_scroll_arrows(void *game, void *list)` | When not following draws up to four scroll arrows (member 0xc) at the screen edges for the directions in which the view can still scroll (x > 0, x < 0x1e8, y > 0, y < 0x4f0), pulsing in alpha with +0x168 or highlighted while the matching d-pad button is held, then draws dictionary word 0xc of the language string table at (0x115, 0xf6) with the font at scale 14. |
| `0x00008b00` | `void world_underground_ladder_generate_entities(int floor, int more_boxes)` | Collects candidate spots (line cells holding 1 on rows 2..15, and fixed rungs) and fills the duelist table 0x1a194 (30 x 0x10: type, gap, column, row; defaults 6, -1, -1, -1) and box table 0x1a374 (10 x 0x10; default type 3) with distinct random spots: world_underground_ladder_roll_duelist_count duelists (their type words come from a stack array that the callee does not visibly fill; hypothesis: unused, confidence low) and the boxes of world_underground_ladder_roll_boxes, except on floor 100 where five type-2 boxes are placed on row 0 of columns 0..4. |
| `0x0000c9b8` | `void * world_underground_title_draw_floor_picker(void *title, void *list)` | Draws the floor picker with dictionary words of the language string table (archive 1): the limit line (word 9 with best - 10), a dark bar, up/down arrows of member 2 when the floor can change, the chosen floor (word 7, centred unless language index 4 or world_underground_get_constant_2 says otherwise), the cost (word 10, fee +0x1c) and the remaining DP (word 8, DP - fee) right-aligned with word 6 as unit. |
| `0x0000f544` | `void * world_underground_result_draw_number(void *list, void *layout, int language, int base, int glyph_base, int format, uint value, uint digits, int align, short right_x, short y, short width, uint color, short scale_x, short scale_y)` | Draws value with one dictionary word per digit (word glyph_base + digit of the string table base + language, world_underground_result_get_text) from right to left ending at right_x: format 0 uses as many digits as the value needs (at least digits), format 1 exactly digits, format 2 a time in hundredths shown as h:mm:ss:cc with separator glyphs (word glyph_base - 5) at positions 2, 5 and 8; the cell width is width / digits capped at scale_x (arguments beyond the eighth on the stack). |
| `0x0000facc` | `void world_underground_result_apply_score(int kind, uint *values)` | Shared mini-game result scoring for the screen 0x1a754: per kind stores the score(s) in +0x28/+0x2c/+0x40, sets the story score world_get_minigame_score, computes the base DP +0x30 and adds a 200 DP bonus +0x34 for each new record (save_get/set_minigame_record_0..8, record-table flag bytes +0xec..+0xf4 set, new-record marks +0x44/+0x46). |
| `0x000107b0` | `void * world_underground_result_draw_values(void *list)` | Draws the text of the result screen 0x1a754 with dictionary words of the result string table for the current language: two block titles (words 1 and 3) with their headers (2 and 5), the row labels of the first block chosen by the kind +0x20 (kinds 0, 1, 3, 5, 6 word 4; kind 2 words 6 and 7 when +0x40 is set; kind 4 words 0x13 and 0x14 when +0x40 is set), the second block's labels (8, 9) with unit word 0xe, two separator rows (10, 11) with units 0xe and 0xf, and the centred footer word 0xc; then the numbers (world_underground_result_draw_numbers). |
| `0x000111c8` | `void world_underground_open_list_window(void *window, void *heap, int columns, uchar rows, int center_x, int center_y, int center_text, void *desc, void *template)` | Clears the 0x120-byte list window, copies the descriptor fields as world_underground_open_text_window does (plus +0xac/+0xb0), and either sets the layout from columns/rows (cursor flag bits, heap +0xc4) or, when template is given, copies the item layout, item callback and cursor from template; opens it with ui_open_list_window, optionally centres it and its text, restores the font flags and marks it active (+0x120 = 1) (arguments 5-8 in t0-t3, the ninth on the stack). |

## Purpose and flow

Scene 0x15, the underground duel mini-game: a 100-floor dungeon built as an amidakuji (ghost-leg) ladder. On every floor the player picks one of five vertical lines and walks along it; horizontal rungs divert the walker to the neighbouring line. Duelists and boxes stand on the lines and rungs, and the end row holds stairs up, stairs down or an exit. Duels are real card duels run by `rel_duel_mgr`, loaded as a library (`libduel_mgr_rel`). Addresses below are module offsets (image base 0).

- Entry: `world_underground_module_start` (0x000080ec) registers `world_underground_scene_main` (0x00008124) / `world_underground_scene_exit_nop` (0x00008224) with argument 0x00019efc when the module is started with argsize 0.
- `world_underground_scene_main` calls `world_underground_scene_init` (thread attribute 0x4000, `world_underground_scene_start(*world_get_underground_params())`), installs the frame callback `world_underground_scene_frame` and the end callback `world_underground_scene_end`, then loops `world_underground_scene_step` + `system_wait_frame`. Exit code 2 writes 1 to the underground parameter word and calls scene 4 (deck editor) with `system_scene_call(0x15, 4, 0)`; exit code 1 writes 0 and returns with `system_scene_return(0x15, 0)`.
- The frame callback runs one `system_duel_mgr_lib_run_frame` while a duel is in progress (scene state 3, game in a duel, duel object state 2), then `world_underground_draw` (layer 0: 3D render state and camera, layer 1: title/game/result, layer 4: fades and the title intro ehf).
- Scene state 0x00018b90 (`world_underground_update`): 0 start the title, 1 title, 2 start a run, 3 game, 4 start the result screen, 5 result screen, 6 finished. The exit code is 0x00018bdc (1 leave, 2 deck editor).
- Entry mode 0x00019e38: 2 on the first entry (title intro with sound 0x7aad and ehf member 0, white fade), 0 when coming back from the deck editor (parameter word 1; title cursor on the deck item), 1 after a result screen.

## Title menu (object 0x00018be0)

States (`world_underground_title_update`): 0 save font flags, 1 load archives 0 and 1, 2 wait, 3 loaded, 4 build strings (music track 0xb), 5 fade in, 6 menu, 7 confirm enter, 8 floor picker, 9 confirm floor, 10 confirm deck editor, 0xb help pages, 0xc confirm quit, 0xd fade out, 0xe wait, 0xf wait for `rel_duel_mgr` (module 0x13, loaded with `system_module_load_ex(0x13, 1, ...)` on "yes" and initialised with `system_duel_mgr_lib_init`), 0x10 free archives, 0x11 done.

Menu items: 0 enter at the saved floor (free), 1 enter at a chosen floor (enabled when DP >= 200 and best floor >= 11; the start floor is 1..min(best - 10, DP / 200) and costs 200 DP per floor, deducted with `save_add_dp(-fee)`), 2 deck editor, 3 help (six scrollable text pages with 14 illustrations), 4 quit. Choice word +0x24: 0 enter, 1 enter at floor, 2 deck, 3 quit.

## Run state and save block

`world_underground_load_progress` reads the 0x30-byte block returned by `save_get_minigame_block_3`:

| Offset | Meaning | Range / default |
| --- | --- | --- |
| +0x00 | current floor | 1..100, clamped to the best floor |
| +0x04 | best floor | 1..100 |
| +0x08..+0x24 | eight upgrade slot levels | 0..4 (out of range -> 0) |
| +0x28 | run in progress (resume flag) | 0/1 |
| +0x2c | resume column | 0..4, default 2 |

The run also uses LP = duelist level (`save_get_duelist_level`) * 100 as both LP and max LP, and the DP (`save_get_player_value(0)`). The block is written back after the title (choices 0/1) and after each run. Outcome +0x16c of the game object: 2 left through an exit (progress and column kept, run flag 1), 1 defeated (LP 0 or a lost duel: floor 1, slots cleared, best kept), 0 cleared (final-floor prize: everything reset including best = 1). When the run counts (outcomes 0 and 2) the won cards are added with `save_change_card_count(id, 1)`; `save_set_progress_flag_e9_bit5` is called when the outcome is 0 or the best floor exceeds 0x31 (49).

Upgrade slots (levels 0..4, raised by box/duel result 8, a slot at 4 is "maxed"): slot 0 > 3 halves the opponent LP; slot 1 > 3 slows the timer (one tick per 30 frames instead of 10); slot 2 > 3 lowers the bad-box chance from 20 % to 10 %; slot 3 > 3 removes stairs down from the end row; slot 4 >= 4 regenerates 1 % of max LP per second; slot 5 > 3 raises the tool cap from 5 to 10; slot 6 >= 4 lets the player choose the start column on every floor; slot 7 > 3 places 6..8 boxes instead of 3..5. (Confidence high for the conditions; the in-game names of the slots come from dictionary words at 0x00017bbc and were not read.)

## Game object (0x00019160)

| Offset | Meaning |
| --- | --- |
| +0x00 | state 0..0x16 (see below) |
| +0x04 | "first floor of this visit" flag (no exits, column choice) |
| +0x0c | map archive loaded |
| +0x10 | run flag |
| +0x14 / +0x18 | LP / max LP |
| +0x1c | tool uses (start 5) |
| +0x20 | timer (start 1000; at 0 the map goes dark and the music switches to track 0xe) |
| +0x24..+0x40 | eight slot levels |
| +0x44 | floor |
| +0x48 | floors climbed this run (result screen) |
| +0x4c | duels won this run (result screen) |
| +0x50 / +0x54 | won-card count / list (words, up to 50) |
| +0x11c, +0x120, +0x124 | moving, view animation, view follows player |
| +0x128 / +0x12c | duelist / box count |
| +0x130 / +0x134 | touched box / duelist index |
| +0x138 | event kind (0 tool, 1 box, 2 duelist, 3 end row, 4 none) |
| +0x13c / +0x140 | event substate / limit |
| +0x144 / +0x148 / +0x14c | result code / slot picked / slot maxed (9 = none) |
| +0x150 | duel result (1 = won) |
| +0x16c | outcome |
| +0x170 / +0x174 | scroll (0..0x1e8, 0..0x4f0) |
| +0x180 | floor view (floor, tier = (floor - 1) / 10) |
| +0x190 | player record (0x3c bytes: pixel +0x08/+0x0c, column/row +0x10/+0x14, target +0x18/+0x1c, walking +0x20, direction +0x24, animation +0x28/+0x2c, visible +0x30, running +0x34, spin +0x38) |
| +0x1cc | 30 duelist records of 0x24 bytes |
| +0x604 | 10 box records of 0x34 bytes |
| +0x80c | map cursor |
| +0x830 | HUD (LP, tools +0x14, timer bar, slot panel, floor label window +0x140) |
| +0xa60 | duel object; +0xa64 text window list |
| +0xb28 | active word of the text window list (+0xa64 list, +0xc4 in it); hides the text while the view scrolls |
| +0xb2c | darkness record (spotlight when the timer is 0) |
| +0xb44 / +0xb50 / +0xbb0 | effect ehf / parameter block / effect id (0x16 none) |
| +0xbb8 | 0x100-byte text buffer |
| +0xcb8 / +0xcbc | current / wanted music track (0xc normal, 0xe timer out) |

States: 0 init, 1-2 load sdchr slot 0 (character 1) and archives 2 and 3, 3 floor setup, 4-5 load the map archive of the tier, 6 hide loading, 7 fade in, 8 intro text, 9 choose column, 0xa wait effect, 0xb view map, 0xc start walking, 0xd play, 0xe recentre, 0xf event begin, 0x10 event run, 0x11 event end, 0x12 fade out, 0x13 next floor or leave, 0x14 free map, 0x15 free archives, 0x16 done.

Effects and text are separate mechanisms. `world_underground_game_state_choose_column` and `world_underground_game_state_view_map` call `world_underground_game_play_effect(game, 0xd)` just before state 0xa, and `world_underground_game_draw` draws the effect in that state; `world_underground_game_begin_box_event` plays effects 0xb, 10 and 7. Text windows go through `world_underground_game_show_text` / `world_underground_game_close_text`. Effect 8 plays at the HUD timer position (`world_underground_hud_get_timer_x` / `_y`) and `world_underground_game_is_effect_done` waits for it on `world_underground_hud_is_timer_animating`.

Controls (hypothesis medium for button names): confirm held = fast walk (6 px/frame instead of 0.5); d-pad scrolls the map and moves the cursor; pad bit 0x8000 uses a tool on the cursor cell (adds a rung, value 2); cancel recentres.

## Ladder data (0x00019f0c, 0x514 bytes)

- Line cells: 5 columns x 18 rows of words at 0x00019f0c + column * 0x48 + row * 4. Rows 0 and 0x11 are the end rows; values 1 plain, 4 stairs down, 5 stairs up, 6 exit. Even floors walk upward (start row 0x11, end row 0), odd floors downward.
- Rung slots: 4 gaps x 18 rows at 0x0001a074 + gap * 0x48 + row * 4; values 0 empty, 1 fixed rung, 2 rung added with a tool, 3 blocked (rungs alternate rows between neighbouring gaps so two never meet).
- Duelist placements 0x0001a194 (30 x 0x10: type, gap, column, row; count 0x0001a414); box placements 0x0001a374 (10 x 0x10: type, gap, column, row; count 0x0001a418). A placement is on a line (gap -1) or on a rung (column -1).
- Generation per floor (`world_underground_ladder_generate`): 3..17 random rungs (none on floors 20/40/60/80); 10..14 duelists (20..24 on multiples of 25); 3..5 type-1 boxes plus 0..1 type-0 box (none on multiples of 30); floor 100 has five type-2 boxes on row 0 instead and no end-row features; end row: stairs up everywhere, plus N exits (N grows by one per floor change in `world_underground_ladder_add_exit`, count 0x0001a41c, max 3, none on the first floor of a visit) and a chance of one stairs-down cell of 0/25/50/75/100 % by floor band.
- Pixel tables: column x 0x00017be0 (5 words), row y 0x00017bf4 (18 words), gap x 0x00017c3c (4 words).

## Boxes, duels and rewards

- Box types: 1 always good (results 0..3), 0 random (good 4..8 or bad 9..0xd), 2 final prize (0xe). Result codes: 0 LP + 10 %, 1 timer + 100, 2 tool + 1, 3 card (class 0/1), 4 LP full, 5 timer full, 6 tools + 5, 7 card (class 3/4), 8 slot + 1, 9 LP - 10 %, 10 timer - 100, 0xb tool - 1, 0xc a maxed slot reset, 0xd floor - 1, 0xe final card (one of five ids at 0x00017a94, fewest owned first; ends the run as "cleared"), 0x10 duel card reward, 0x11 nothing.
- Card rewards (`world_underground_game_award_random_card`) scan card ids 0xe88..0x1f39 that are valid, not tokens and not in the 25-id exclusion list 0x00017b58, filtered by `card_db_get_prop_bits22` (class value; hypothesis: rarity). Duel rewards use a per-rank percentage row from 0x00017aa8.
- Duels: opponent LP is a random multiple of 10 between the bounds of 0x00018450 (pair per 5 floors), the opponent deck is a random recipe whose `deck_get_recipe_level` equals the floor rank from 0x000184f0 (per 5 floors). The 0x858-byte duel setup is passed to `duel_setup_load_decks`, then `system_duel_mgr_lib_start_duel_draw`; the module then calls the `rel_duel_mgr` exports `system_duel_mgr_lib_poll_draw_loading` (0x08e9dcb0, ready test), `system_duel_mgr_lib_begin_duel` (0x08e9dcb8, start) and `system_duel_mgr_lib_update_duel` (0x08e9db84, running test). The result comes back in `deck_get_duel_setup_tail_block()` +0x20 (1 = won) and +0x28 (remaining LP, which becomes the run LP).

## Files

Archive table at 0x00016e80 (0x24-byte entries: 0x20-byte path, loaded pointer at +0x20), loaded from root 8 through `container_load_file` into the module's 1 MB heap (carved from the sound heap):

| Index | File |
| --- | --- |
| 0 | `underground/titlemenu_com.ehp` |
| 1 | `underground/titlemenu_<l>.ehp` (table 0x00016f58) |
| 2 | common game archive (entry 2 of 0x00016e80; name not read, likely `underground/game_com.ehp`) |
| 3 | `underground/game_<l>.ehp` (table 0x00016f78), holds `strtbl_<l>.bin` |
| 4 | map by tier: `underground/map01.ehp` table 0x00017258, 0x20 per tier |
| 5 | `result/mini_result_<l>.ehp` (table 0x00016fb8) |

Language tables have one 0x80-byte block per language index (four 0x20-byte names); `world_underground_get_language_index` maps `save_get_language` 0..5 to 4, 0, 2, 1, 3, 5 (index 0 is the `_e` block; index 4 uses ruby text, hypothesis: Japanese). Members are looked up by name through the 0x24-byte member table 0x00017398 (name, archive index; member 0 `mn_dj_title.ehf`); map backgrounds `mini_dj_map01_<0..2>.gim` per tier (0x0001768c/0x000176ac/0x000176cc, 0x60 per tier). Sprite characters are loaded from `underground/sdchr/%s` with the names returned by `world_get_character_model_entry_words` (or `world_get_character_word_14/_10`); frames are 0x33 x 0x54 cells, table 0x000167a8 (row per direction pair, 0x38 bytes; 7 cells: stand + 6 walk frames). Text comes from dictionary words of `strtbl_<l>.bin` (`card_db_get_dictionary_word`).

## Result screen

`world_underground_result_*` (0x0000e110..0x00010de8) is the shared mini-game result screen, statically linked: `world_underground_result_apply_score` handles seven kinds (0..6) with `save_get/set_minigame_record_0..8`, the record-table flags +0xec..+0xf4, `world_get_minigame_score`, `save_add_dp` and `save_add_duelist_exp` (+400 DP on a level-up); the underground uses kind 4: DP = duels won * 20 + floors climbed * 150, plus 200 per new record (record 5 duels, record 4 floors), EXP = DP / 25. When the mini-game was called from the story (`system_scene_get_caller(0x15) == 2`) the screen leaves directly; otherwise it asks whether to continue (choice 0 = back to the underground title). Archive 5 members: `mini_result_j.bin` .. (18 string tables), `result_mini01.gim` .. (5), `m_menu_bar01.ehf` .. (6). Two drawing helpers are exact copies of `rel_duel_mgr` `ui_duel_result_reset_sprite_state` / `ui_duel_result_draw_atlas_rect`. (Hypothesis, medium: the same block exists in the other mini-game modules; compare with `rel_title` `ui_mini_result_*`, which is larger.)

## Corrections to existing docs

- `world.md`, mini-game parameter blocks: `world_get_underground_params` (4 bytes) is also written by `rel_underground` itself: 1 before calling the deck editor (scene 4) and 0 before returning; its value is the argument of `world_underground_scene_start` (0 = first entry with intro). The module does not read `world_get_minigame_score`; the result screen writes it.
- `modules.md`: "calls scene 4" is the deck editor called from the underground title menu (exit code 2).

## Name mismatches

- 0x00000000: pack twin `system_net_api_get_alive_peer_count` is a false positive (masked jal targets); real function `world_underground_begin_3d_frame`.
- 0x00002764 / 0x00002774: pack twin `audio_heap_free` is a false positive; they are `world_underground_heap_alloc` / `world_underground_heap_free` on the module heap 0x00019ec4.
- 0x000080ec: twin `shop_module_start` (rel_shop) has the same code but the name is wrong for this module; named `world_underground_module_start`.
- 0x0000ce88 is a second copy of `ui_list_window_draw_text` in the same module; named `ui_list_window_draw_text_2`.
- 0x00007934 (16 bytes in the registry) holds two pieces of code: the wrapper `world_underground_game_set_text_visible` (`j 0x793c; addiu a0, a0, 0xa64`) and an 8-byte helper at 0x0000793c (`jr ra; sw a1, 0xc4(a0)`), the set-active of the text window list. The helper has no function entry; the wrapper is its only `j`/`jal` reference.

## Open questions

- The archive name of table entry 2 (0x00016ea0 + 0x48 region) and the full map-name table 0x00017258 (number of tiers: the code uses (floor - 1) / 10, i.e. 10 tiers, but only three background gim names per tier).
- Duelist type words come from a stack array that `world_underground_ladder_roll_duelist_count` does not visibly fill; whether duelists have types at all (confidence low).
- `world_underground_title_measure_help_page` (0x0000d030) decompiles as an empty body; its return value is used as the page height (skipped).
- The meaning of the `card_db_get_prop_bits22` classes (0, 1, 3, 4) used by the card rewards (rarity hypothesis).
- In-game names of the eight upgrade slots and of the result codes (dictionary words, not read).
