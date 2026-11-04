# `rel_throw`

Module document of the 2026-11-04 round 6 (all game modules imported; `../modules.md`). English, evidence-based: the sections below come from reading every function of the module in the Ghidra decompilation; hypotheses carry a confidence.

| | |
| --- | --- |
| File | `PSP_GAME/USRDIR/gmodule/rel_throw.prx`, 118,684 bytes, plain ELF (relocatable PRX) |
| Slot | scene 0x1c, id 0x2f |
| Exports → importers | — |
| Role (catalogue) | Minigame (`mini_result`, title messages). |
| Runtime base | unknown; imported at image base 0x0, so addresses are module offsets |
| Registry ids | `rel_throw:0x…` |
| Functions | 282 own functions, 282 documented in this round (world 238, ui 43, audio 1); tables in `../functions/<group>.md`, section `rel_throw` |

## Key functions (largest)

| Address | Prototype | Summary (first sentence) |
| --- | --- | --- |
| `0x00000378` | `void world_throw_draw_actor_parts(void *list, void *upper_tex, int cell_id, int upper_clut, void *lower_tex, int lower_clut, float *pos, int direction, int move_state, int frame)` | Draws a field-model character in two parts using world_get_character_sprite_cell(direction, cell_id, move_state, frame): the lower part (0x33 x 0x40) from lower_tex with palette lower_clut at y + 16, then the upper part (0x33 x 0x32) from upper_tex with palette upper_clut raised by the returned offset, both mirrored by the returned flag; sets blending (0, 2, 3), alpha test and nearest filtering first. |
| `0x00000cbc` | `void ui_throw_menu_ctx_open_message_window(void *heap, void *window, ushort *text, int choices, int modal)` | Opens a message window: default descriptor, type 2, position (0x3c, 100), size 0x168 x 0x50, margins 10/10/8/0, text at +0x84, +0x60 = 1 when modal, flag bit 5 of +0xc8; choices 1 configures one choice, choices 0 three; then ui_open_list_window. |
| `0x00001068` | `void * ui_throw_menu_ctx_draw_nine_slice(void *list, int kind, int colour, short x, short y, short width, short height)` | Draws a nine-slice box of width x height at (x, y) from the 9 x 4-halfword part table 0x000100b8: the colour selects the texture offset (kind 2: colours from 0xc, u = ((c - 0xc) % 6) * 10, v = ((c - 0xc) / 6) * 10; kind 0: u = (c % 6) * 10 + 0x17, v = (c / 6) * 10, colour 8 at (0, 0x74)); corners at their size, edges and centre stretched to width - 9 / height - 9. |
| `0x000018ac` | `void * ui_throw_menu_ctx_draw_number(void *list, void *ctx, int table_base, int table_offset, int glyph_base, int mode, uint value, uint min_digits, int align, short x, short y, short width, uint color, short scale_x, short scale_y)` | Draws a number with one mini_result string per digit (glyph_base + digit via ui_throw_menu_ctx_get_message): mode 0 as many digits as value needs (at least min_digits), mode 1 exactly min_digits, laid out right to left with step min(width / digits, scale_x); mode 2 a time in hundredths of a second (centiseconds, seconds % 60, minutes % 60, hours) with separator strings glyph_base - 5 at half step. |
| `0x00001e34` | `void ui_throw_result_apply_score(int game, uint *score)` | Scores a finished mini-game into the result block 0x00018924 and the save, same logic as the rel_title copy: stores score values (+0x28/+0x2c/+0x40) and the main score into world_get_minigame_score(); base DP (+0x30) per game (0: score / 50, 1: / 150, 2: / 2 plus ceil(sub / 100), 3: / 10, 4: score[1] * 20 + score[2] * 150, 5: / 50, 6: / 10); each new record (save_get/set_minigame_record_0..8) adds 200 bonus DP (+0x34), sets the new-record flags (+0x44/+0x46) and a marker byte in the save record table (+0xec + record); total +0x38, experience +0x3c = total / 25; save_add_dp, save_add_duelist_exp and 400 more DP on a level up; games 3 and 4 also store the from-story flag (+0x1c). |
| `0x000028b8` | `void * ui_throw_result_draw_panels(void *list)` | With context image 0 bound draws the result panels: border box (0x3e, 0x3d, 0x165 x 0xa4), two sections (y 0x40 and 0x79) each with a title bar and value box and two rows (label box 0x10d x 0x10 colour 3, value box 0x49 x 0x10 colour 1, new-record mark part 0xc at (0x14a, y + 3) in the first section when +0x44/+0x46 is set), two three-slice bars with value boxes at y 0xb3/0xc8 and the bottom bar (colour 8, y 0x100, 0x1e2 x 0x12). |
| `0x00002b18` | `void * ui_throw_result_draw_labels(void *list)` | Draws the result texts from mini_result_<l>.bin: section titles 1/3 with value headers 2/5 (white, scale 0xe), row labels per game (first section: 4 for games 0, 1, 3, 5, 6; 6 and 7 for game 2; 0x13 and 0x14 for game 4, the second only when +0x40 is set; second section 8 and 9 with unit string 0xe in cyan 0xff00ffff), totals 10 and 11 with units 0xe/0xf, the centred footer 0xc at y 0x102, then the values (ui_throw_result_draw_values). |
| `0x00002ed0` | `void * ui_throw_result_draw_values(void *list)` | Draws the six result values (+0x28..+0x3c of the block 0x00018924) right-aligned at x 0x155 with digit glyph strings from 0x15 (ui_throw_menu_ctx_draw_number, white, scale 0xe): rows at y 0x54/0x67, 0x8d/0xa0 and 0xb9/0xce; width 0x47 for the first pair, 0x33 for the others; at least 6 digits for the first two, 5 for the others; the second value only for games 2 (as a time, mode 2) and 4 (when +0x40 is set). |
| `0x00004bac` | `void world_throw_pick_random_partner(int *out_character, int *out_variant, int exclude, int *exclude_list, int exclude_count)` | Collects candidate characters 0..0x8e that exist (world_character_exists(c, 0)), are not exclude, are not in exclude_list[0..exclude_count), have a partner deck (world_character_has_partner_deck) and are not 0 or 1; characters 0xc, 0xd, 0x12, 0x15, 0x18, 0x19, 0x1a-0x1d, 0x1f-0x23, 0x2e and 0x79-0x7e need save flag bit 0 (save_test_character_flag_bit0). |
| `0x0000591c` | `void world_throw_tally_draw(void *list)` | Draws the tally panel with alpha a = 0x00238c7c: a full-screen black quad of alpha a * 160, two grey (0xa0a0a0) 1-pixel lines at y 0x3c and 0xb4, then text from strTbl.bin with shadow: title 0xe at (0x73, 0x28) at scale 0x12, and at scale 0xf right-aligned labels at x 300 with values right-aligned at x 0x172: string 6 with 0x00238c84 (y 0x46), 2 with 0x00238c88 (y 100), 4 with 0x00238c8c (y 0x82), 5 with 0x00238c90 (y 0xa0), then in 0xffffff-based colour with alpha the total label 0x10 with the remaining total 0x00238c78 and unit string 10 at (0x17c, 0xbe). |
| `0x00006fe8` | `void * world_throw_sprite_draw(void *sprite, void *list)` | Draws a visible sprite: takes the current frame's rect (u, v, w, h) from the animation descriptor, scales w and h by +0x20, positions it centred on x and with y + h/2 (world space, y up) or y - h/2 (screen space), binds the texture +0x24 (field_3d_gim_emit_texture_frame0), sets the ambient colour white with alpha alpha +0xc * 255 * fade level +0x10, uses additive blending (0, 2, 10, 0, 0xffffffff) when byte +0x19 is 1 else (0, 2, 3); screen space draws with world_throw_draw_screen_sprite(_scaled), world space with world_throw_draw_world_sprite (scale 1 and no flip) or world_throw_draw_world_sprite_scaled with flip mode +0x1c; restores the normal blend after an additive draw. |
| `0x00008300` | `int world_throw_controller_update(void *controller)` | Per-frame round logic: handles input, updates the world and the sprite list, makes the controller x follow the thrown object while it moves and points the camera at (x, y) (world_throw_controller_focus_camera); then by state +0: 0 starts a round (world_throw_controller_start_round) and goes to 1; 1 walks the partner in (world_throw_controller_walk_in) -> 2; 2 pans the camera to the thrower (world_throw_controller_pan_camera), then advances the partner's item flag +0x60 when set, sets the prompt frame 2 (flag < 1) or 3, places the partner at x 0xf0 idle facing 6, HUD message 0xd (0xf with the item flag) and goes to 4, or on the first round shows the start banner (world_throw_show_banner(3)) and waits 60 frames in state 3; 3 waits, timer 15 -> 4; 4 runs the throw (world_throw_controller_update_throw): normal -> 5, early press -> 6 with balloon icon 8, HUD message 1, prompt frame 1 fading out, failure marker and one try lost; 5 resolves the hit (world_throw_controller_resolve_hit), then fades the prompt out, timer 15, window closed -> 7; 6 and 7 wait, timer 180 -> 8; 8 waits (a button press after 29 frames skips), fades out the display object and marker and, when the item flag is above 1, the item sprite (flag cleared), timer 30, then game over (no tries left: banner world_throw_show_banner(4), timer 60, state 10) or next round (state 0xb); 10 runs world_throw_controller_update_game_over; 0xb waits, hides the thrower balloon, increments the round number (world_throw_world_next_round) -> 2. |
| `0x00008dc8` | `int world_throw_controller_update_throw(void *controller)` | State 4: (1) while the timer +0xc runs counts it down and, when it reaches 0, puts the thrower's balloon at (thrower x + 0x16, y + 0x1e) with icon 1, shows it, shows the prompt and fades it in (step 0.1, from 0), sets prompt frame 2 (partner item flag < 1) or 3, picks the delay (world_throw_controller_pick_delay) and the object (world_throw_controller_pick_object); returns 0. |
| `0x00009060` | `int world_throw_controller_resolve_hit(void *controller)` | State 5: while the thrown object is still right of the partner (x > partner x + 0x14) returns 0, or hides it and returns 1 once it has left the screen (x < -0x28). |
| `0x0000a2f0` | `void world_throw_hud_draw_progress(void *hud, void *list)` | Draws the top-centre progress strip: untextured boxes (0xae, 2, 0x84 x 0x1d) in 0xff464646 and (0xaf, 3, 0x82 x 0x1b) in 0xff401c04, then from the atlas three rows (y 0xe, 0x12, 0x16) of 24 dots (x 0xb2 + 5 * i, cell (0x48, 0xf0) 4 x 3), the partner marker (when partner x > 0) at x * 5 / 0x32 + 0xae, y 6 (cell (0x3c, 0xf0) 4 x 6) and the thrower marker likewise (cell (0x34, 0xf0)); finally formats strTbl.bin string 0x11 with the round number (short +0 of the HUD, system_swprintf) and draws it white with shadow, scale 0xc, centred at y 0x20. |

## Purpose and flow

`rel_throw` is scene 0x1c, the "throw" mini-game (game index 6 of the shared mini-game result screen, save record 8). The thrower NPC (character 0x1a, or 0x1b when the partner is 0x1a) throws objects at the chosen partner character, who stands at world x 0xf0. The player presses a button to make the partner dodge: ordinary objects should be dodged, items the partner likes should be let through (the partner accepts them), items the partner dislikes should be dodged. The partner has 5 tries. Confidence for this reading of the rules: medium (it follows from `world_throw_controller_resolve_hit` and the counters it feeds; the meaning of the art was not checked in PPSSPP).

- Entry: `world_throw_module_entry` (0x0000320c) sets thread attribute 0x4000 and registers start `world_throw_scene_main` (0x00003260), end = thunk of `world_throw_run_global_destructors` (0x00000000), data 0x00018928.
- `world_throw_scene_main`: `world_throw_static_init`, `world_throw_scene_init` (reads the 5-word throw parameter block, `world_get_throw_params`), then `system_scene_set_frame_callback(2, world_throw_frame_callback, thunk of world_throw_game_term)`, loops `world_throw_scene_update` until done, then `system_scene_return(0x1c, 0)`.
- Top-level state 0x00018a10 (`world_throw_update`, 0x00004134): 0 load `basic_lang_<lang>.ehp` -> 1 wait -> 2 title layout (`mini_db_title.ehf`) -> 3 pick thrower -> 4/5 load the two actors' sprite sheets -> 6 wait title, create match objects, BGM 0x19 -> 7 match setup -> 8 play (`world_throw_match_update`) -> 9 fade -> 0xc wait fade -> 0xd result screen (`ui_throw_result_create(heap, mini_result archive, 6, &0x00018bc0)`) -> 0xe result screen update (3 quit -> 0xf, 2 play again -> state 2 with score cleared) -> 0xf terminate, return 1. States 10 (window 0x00018a24) and 0xb (score count-down) are reachable only through `world_throw_match_get_result` returning 1/2, which nothing read here sets (see open questions).
- Drawing (`world_throw_draw`, 0x000042f0): layer 0 3D render state; layer 1 match scene in states 8..0xc (`world_throw_match_draw`: sky, fence rows, actors, HUD, sprite list); layer 4 tally panel, fade, window, title layout, result screen.

## Round state machine (controller 0x00238de8, `world_throw_controller_update` 0x00008300)

| State | Handler | What happens |
| --- | --- | --- |
| 0 | `world_throw_controller_start_round` | reset x/y/timer, hide balloons/prompt/marker, partner walks in |
| 1 | `world_throw_controller_walk_in` | partner walks right (speed 3, 6 after a button press) to x 0xf0 |
| 2 | `world_throw_controller_pan_camera` | camera eases to the thrower (x 1064); first round shows the start banner (state 3, 60 frames) |
| 3 | timer | -> 4 |
| 4 | `world_throw_controller_update_throw` | thrower balloon, prompt fades in, random delay 90..299 frames, random object; pressing during the delay is an early press (state 6, one try lost); else the object is launched (state 5) |
| 5 | `world_throw_controller_resolve_hit` | object flies left at speed = power; on contact the outcome is decided (table below) -> 7 |
| 6, 7 | timer | 180 frames -> 8 |
| 8 | wait / skip | fades out display object and marker; no tries left -> game-over banner, state 10; else state 0xb |
| 0xb | timer | hide thrower balloon, round number + 1 -> 2 |
| 10 | `world_throw_controller_update_game_over` | clamps counters to 99 and runs the tally panel; returns 1 when the panel has closed |

Object kinds (`world_throw_controller_pick_object`): weights 0x0000f568 = {8, 8, 8, 8, 8, 60} for kinds 1..6; kind 5 is not repeated while the partner wears the kind-5 item. Kind 6 is an item icon from `story_item.gim`, item number `rand % 50 + 1`.

Outcomes (`world_throw_controller_resolve_hit`):

| Dodge pressed | Kind | Result |
| --- | --- | --- |
| no | 6, partner likes it | success, items accepted (+0x30) + 1, balloon icon 6, sound 0x7add |
| no | 6, partner does not like it | failure without losing a try (icon 7, sound 0x7ade) |
| no | 3 | partner knocked away, tries = 0 (sound 0x7ad8) |
| no | 1, 2, 4, 5 | failure, one try lost (icon 3); kind 5 puts the item sprite on the partner (+0x60 = 1, sound 0x7ad9) |
| yes | 6 | success (items dodged +0x38 + 1, streak + 1) only when preference +0x58 < 2 and the partner does not like it; else failure, one try lost (icon 5) |
| yes | 1-5 | success, dodges +0x34 + 1, streak + 1 (icon 4) |

Failures end the streak and lower the throw power by 6 (minimum 8); each launch raises power by 3 (maximum 0x96). Streaks of 3 or more add (streak - 1) to the bonus counter +0x3c (`world_throw_controller_end_combo`).

Item preference (`world_throw_partner_set_item_preference`): column item + 6 of the partner's row in this module's character table copy 0x00010160 (140 rows x 57 words, `world_get_char_table_value`); value < 4 = likes; value 6 = 50 % coin flip. Hypothesis (medium): columns 7..56 hold the per-item preference ranks of each character (the same table the story uses for gifts).

Final tally (`world_throw_tally_start`): items accepted x 300 + dodges x 20 + items dodged x 20 + bonus x 100. `world_throw_tally_update` transfers the total into the score 10 points per frame (all at once with confirm), `world_throw_world_update_tally` publishes it to the score word 0x00018a18, which becomes the mini-game score (0x00018bc0) for the result screen: DP = score / 10, record 8 (`ui_throw_result_apply_score`).

## Key structures (all heap objects come from `system_malloc`; vtables are GCC 2.x style with two zero words, destructor at +8)

- World 0x34 bytes (pointer 0x00238de4, `world_throw_world_construct`): +0 partner actor, +4 thrower actor, +8 thrown object, +0xc display copy of the object, +0x10 prompt, +0x14 marker, +0x18 HUD, +0x1c 1-byte block (no reader), +0x20 effect sprite, +0x24 frame counter, +0x28 tally active, +0x2c tally done, +0x30 tally score.
- Round controller 0x44 bytes (0x00238de8, `world_throw_controller_reset`): +0 state, +4 x float, +8 y float (188.0), +0xc timer, +0x10 throw delay, +0x14 power (8..0x96), +0x18 input window, +0x1c dodge pressed, +0x20 hit flag, +0x24 early press, +0x28 first round, +0x2c byte walk speed, +0x30 items accepted, +0x34 dodges, +0x38 items dodged, +0x3c bonus, +0x40 streak.
- Sprite list 0x54 bytes (0x00238de0): 20 sprite pointers, count short +0x50; update/animate/fade virtuals each frame, then sorted by layer.
- Actor base (vtable 0x00018878: +8 destructor 0x00006998, +0xc init 0x000064c0, +0x10 update 0, +0x14 draw 0x00006544): +0 character, +4 variant, +0xc x, +0x10 y (world, y up), +0x14/+0x18 sprite files of the slot, +0x1c slot, +0x20 direction, +0x24 move state (0 idle, 1 walk, 2 run, 3 recoil), +0x28 frame counter, +0x2c..+0x34 draw pointer-to-member {delta, index -1, function} (0x00018728 -> `world_throw_actor_draw_sheet`, 0x00018734 -> `world_throw_actor_draw_model`), +0x38 vtable.
  - Partner (100 bytes, vtable 0x00018860: init 0x00006b28, update 0x00006b98): +0x3c tries (5), +0x40 state (2 dodge, 3 shake, 4 knocked away), +0x48 balloon, +0x4c item sprite, +0x50 shake timer, +0x54 slide speed, +0x58 preference value, +0x5c likes flag, byte +0x60 item flag.
  - Thrower (0x44 bytes, vtable 0x00018848: init 0x00006d00, update 0x00006d40 empty): +0x3c balloon. Starts at x 0x428, y 0xbc, direction 2.
- Sprite base 0x48 bytes (vtable 0x0001881c at +0x44: +8 destructor, +0xc show, +0x10 hide, +0x14 fade step, +0x18 fade in, +0x1c fade out, +0x20 animate, +0x24 fade update, +0x28 update): +0 x, +4 y, +8 visible, +0xc alpha, +0x10 fade level, +0x14 fade step, byte +0x18 fade mode (1 in, 2 out then hide), byte +0x19 additive, +0x1c flip/rotation mode, +0x20 scale, +0x24 texture (GIM), +0x28 layer, +0x2c world space, +0x30 animation, +0x34 playing, short +0x38 frame, +0x3c speed, +0x40 time.
  - Animation descriptor 0xc bytes: {int mode (0 static, 1 loop, 2 hold last, 3 hide at end), short frame count, frame table pointer}; frame entry 8 bytes {ushort *rect (u, v, w, h), short duration}. Descriptors live at 0x0000f8b4.. (object kinds at 0x0000f8b4 + kind * 0xc, item frames 51), balloon icons 0x0000fa0c..0x0000fa60.
  - Sub-classes: thrown object (vtable 0x000187e4, 0x5c bytes: +0x48 child, +0x4c kind, short +0x50 item, +0x54 moving, +0x58 speed), prompt (0x000187b8, 0x4c: pulse child), marker (0x0001878c, 0x54: +0x48 delay, +0x4c active, +0x50 result kind 9/10), effect (0x00018760). HUD (vtable 0x00018810 at +0xc, 0x10 bytes: short +0 round number, +8 message index). Balloon 0x18 bytes (no vtable): +0 visible, +4/+8 position, +0xc icon, +0x10 balloon sprite, +0x14 icon sprite.
- Camera 0x00018938 (current x, y; target x 0x00018940, y 0x00018944), eased by 1/3 per frame; `world_throw_world_to_screen` adds a depth parallax of 0.01 * depth.
- Mini-game result block: same 0x2c4-byte layout as the rel_title copy, pointer 0x00018924.

## Files and resources

- Archive slot 0 (`world_throw_load_archive`): `minigame/throw/basic_lang_<lang>.ehp` (device root 8, path built as `throw/%s`; language names from 0x00017e14, jpn first). It contains `mini_result_<l>.ehp` (resource 0x18), bound for the result screen. `basic.ehp` (language-independent, on disc) is not referenced by code read here.
- Resource table 0x00017ed4 (0x24-byte records {member name[0x20], archive slot}): 0 strTbl.bin, 1 mini_db_ball01.gim (sprite atlas), 2-4 mini_db_sky01-03.gim (background by parameter word 4), 5-8 mini_db_meter11/21/10/20.ehf, 9 mini_db_bomb1.ehf, 10 sp_baloon.gim, 11 story_item.gim, 12 mini_db_title.ehf, 13/14 mini_db_win .ehf/.tmf, 15/16 mini_db_lose, 17/18 mini_db_draw, 19/20 mini_sn_start, 21/22 mini_sn_over, 23 next_player10.ehf. Resources 5-9, the win/lose/draw banners and next_player10 are loaded but never drawn by code read here.
- Actor sprite sheets: `minigame/throw/sdchr/<name>` from `world_get_character_word_14/10` or the model entry words (on disc `sd_<name>_ver.gim` / `sd_<name>_sla.gim`, 86 pairs); even directions use the first file, odd (diagonal) directions the second.
- Module heap: a static 0x220000-byte buffer at 0x00018c00 inside the module image (`world_throw_heap_init`), used for file data and as the field_3d allocator.
- Sounds: tracks 0x2c8 and 0x2d6 loaded, BGM track 0x19 (play) and 5 (game over); effects 0x7ad1-0x7ade, 0x7a05.
- strTbl.bin strings used: 1, 0xd, 0xf (HUD messages), 0x11 (round format), 0xe, 6, 2, 4, 5, 0x10, 10 (tally panel).

## Talks to BOOT.BIN and other modules

`world_get_throw_params` (words 0-4: partner, variant, unused, unused, background selector), `world_get_minigame_score` (via the result copy), `save_get/set_minigame_record_0..8`, `save_add_dp`, `save_add_duelist_exp`, `save_get_minigame_block_8` (stored in 0x00018bbc, no reader found), `world_character_*` / `world_get_character_*` lookups, `field_3d_set_allocator`, `container_load_file`, `ui_ehf_*`, `ui_*list_window*`, `system_font_*`, `audio_*`. Called by the title's mini-game menu (entry 6) and the story, and by `rel_throw_starter`.

## Shared code (copies)

- 0x0000075c..0x00003150: copy of rel_title's mini-game result screen and menu-context helpers. Named `ui_throw_menu_ctx_*` / `ui_throw_result_*` (module infix, same convention as `ui_blackjack_*`); the body of each matches the rel_title function named in names.tsv.
- Exact twins kept under their own names: `world_get_character_sprite_cell` (rel_field), `world_get_char_table_value` (rel_story), `ui_duel_result_reset_sprite_state`, `ui_duel_result_draw_atlas_rect` (rel_duel_mgr); BOOT wrappers with address suffixes because two copies exist: `ui_draw_level_badge_text_fit_1898/_3bf0`, `ui_list_window_draw_text_5d7c/_a598`.
- Twin lines judged false positives (generic shape, different callee or global): 0x0000339c (ui_duel_draw_frame_if_active), 0x00004ef0 (ui_init_cutin_subtitle), 0x00005284 (audio_heap_free; it allocates), 0x000060c0 (system_net_api_get_alive_peer_count), 0x00008078 (ui_card_action_layout_callback). 0x00005294 matches the audio_heap_free shape but frees on this module's heap, so it is named `world_throw_heap_free`.

## Name mismatches

None (no meaningful names were present in the pack headers).

## Open questions

- `world_throw_match_get_result` returns 0x00238cd4, which no code read here writes; therefore top-level states 10 (window 0x00018a24, never opened) and 0xb (score count-down) look unreachable, and every match goes 9 -> 0xc -> 0xd. Check in PPSSPP.
- `world_throw_state_setup_actors` calls `world_throw_pick_random_partner` but the decompiled code discards its result. `rel_throw_starter` passes partner -1 for its "Random" row, so the pick probably replaces a -1 partner; check the disassembly at 0x00004504.
- 0x0000f300 = 0x1cb is the button mask for dodging; which PSP buttons it covers depends on the pad remapping in `system_pad_get_state`.
- The window-open condition in `world_throw_controller_update_throw` compares the prompt's alpha (+0xc, always 1.0 here) with 0.5, so the input window opens on the first delay frame; possibly the intended field is the fade level +0x10.
- `world_throw_sprite_animate` adds the speed twice per frame when the frame does not advance; confirm against the original timing.
- What the "fence" rows (atlas cell 0x1be, 0x15), the effect sprite and the meter/bomb layouts show; the tally panel is drawn on layers 1 and 4.
- The four point helpers 0x00004fd8..0x00005100 are called on tally words that are never set (leftovers of another scoring scheme?).
- `save_get_minigame_block_8` is stored in 0x00018bbc but never read; whether the game writes anything into minigame block 8.
- Parameter words 2 and 3 are ignored (the starter puts the thrower id in word 2); word 4 selects the sky (1 from the title menu; the story value is not traced).
- `world_throw_call_member_pointer` (0x000000c4) is an old-GCC pointer-to-member thunk: descriptor {delta, index, function or vptr offset} in t9; index < 0 means a non-virtual call. Its only reference is the tail jump in `world_throw_actor_draw` (t9 = actor + 0x2c, the member pointer stored in each actor).
