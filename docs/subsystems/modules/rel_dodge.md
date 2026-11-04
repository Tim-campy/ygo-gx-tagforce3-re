# `rel_dodge`

Module document of the 2026-11-04 round 6 (all game modules imported; `../modules.md`). English, evidence-based: the sections below come from reading every function of the module in the Ghidra decompilation; hypotheses carry a confidence.

| | |
| --- | --- |
| File | `PSP_GAME/USRDIR/gmodule/rel_dodge.prx`, 107,436 bytes, plain ELF (relocatable PRX) |
| Slot | scene 0x11, id 0x24 |
| Exports → importers | — |
| Role (catalogue) | Minigame: dodgeball (`mini_db_*`). |
| Runtime base | unknown; imported at image base 0x0, so addresses are module offsets |
| Registry ids | `rel_dodge:0x…` |
| Functions | 342 own functions, 342 documented in this round (world 288, ui 50, field_3d 2, save 1, audio 1); tables in `../functions/<group>.md`, section `rel_dodge` |

## Key functions (largest)

| Address | Prototype | Summary (first sentence) |
| --- | --- | --- |
| `0x00000a3c` | `void world_dodge_player_update(void *player)` | Per-frame fighter update. |
| `0x000010a0` | `void *world_dodge_player_draw(int *player, void *list)` | Draws one fighter across three GE layers. |
| `0x00003340` | `void world_dodge_game_draw(void)` | Per-frame draw: GE layer 0 gets world_dodge_setup_ge_state; layer 1 the match scene world_dodge_match_draw in states 8-0xc; layer 4 the score panel world_dodge_draw_score_panel (score 0x00015540, stage 0x00015548) in states 6-0xc, the fade, the dialog ui_dodge_draw_dialog(0x0001554c) in state 10, the title ehf (world_dodge_draw_title) while the title flag 0x00015670 is set in states 2-8, the stage banner while 0x000156e4 is set (strTbl dictionary word 0xe formatted with stage + 1 by system_swprintf, drawn by world_dodge_draw_outlined_text at (0xaa, 0x78) scale 0x1e with alpha fading in over frames 0-15, held to 0x2d and fading out to 0x3c of the timer 0x000156e0) and the result screen 0x0000e46c in state 0xe. |
| `0x00005fac` | `void world_dodge_match_setup(int player_character, int character1, int variant1, int character2, int variant2, int character3, int variant3, int *score, int *stage, int *saved_hp, int period)` | Starts a stage. |
| `0x000065c8` | `void world_dodge_match_draw(void *list)` | Draws the match. |
| `0x00007c44` | `void world_dodge_match_check_hits(void)` | Hit resolution for the active ball. |
| `0x0000907c` | `void *world_dodge_draw_minimap(void *list, int *args)` | Draws the mini-map at the top centre: frame boxes at (0xae, 2) and (0xaf, 3), a 4x3 cell for every present block of the grid args[0] (24 x 5, at x = 0xb2 + column * 5, y = 0x1a - row * 4), a 4x6 dot per living fighter (args[1..8] column/row pairs; uv by team from 0x00013f0c/0x00013f1c, blinking every 5 frames), an extra marker over the current fighter args[9], and the turn caption (strTbl word 0x14 formatted with args[10] + 1) centred at y 0x20. |
| `0x00009cb4` | `int world_dodge_ball_collide_grid(int ball)` | Grid collision of a ball: from its centre cell (x / 52, (y - 27) / 30; nothing outside 24 x 5) gathers the 3 x 3 neighbouring blocks; a block in the centre cell, and blocks next to a cell corner that lies within the ball radius (method +0x38), are hit: each is broken (world_dodge_break_block) when the ball's break method (+0x14) returns non-zero. |
| `0x0000abf8` | `void world_dodge_shots_update(int shots)` | Per-frame shot update. |
| `0x0000b5f0` | `void *world_dodge_score_draw(void *list)` | Draws the tally screen with alpha 0x0019f820: dark panels, three separator lines, the title (strTbl word 0x11), the rows word 10 + table-A points (hit points), word 0x15 + table-B points (turns), word 9 + table-C points (accuracy), word 0x16 + their sum, word 0xb + the stage multiplier printed with the wide format 0x00014c2c, and word 0x13 + the remaining tally total 0x0019f81c with word 0xc; numbers right-aligned at x 0x172. |
| `0x0000cdfc` | `void *ui_dodge_result_draw_frame(void *list, int style, int pattern, short x, short y, short w, short h)` | Draws a nine-slice frame of size w x h at (x, y) from the nine cells of the table 0x000151d0 (4-pixel corners, stretched edges and centre); style 2 and style 0 shift the atlas origin by the pattern index (pattern % 6 * 10, pattern / 6 * 10, with offsets 0x17 or 0x74 for style 0). |
| `0x0000d640` | `void *ui_dodge_result_draw_number(void *list, int *ctx, int table, int language, int first_word, int mode, uint value, uint digits, int align, short x, short y, short cell_w, uint color, short scale_x, short scale_y)` | Draws value right-to-left one glyph per digit, each glyph being string-table word first_word + digit (ui_dodge_result_get_string, ui_dodge_result_draw_text): mode 0 uses as many digits as value needs (at least digits), mode 1 exactly digits, mode 2 a time from hundredths of a second (cc, ss, mm, hh with separator word first_word - 5 and half-width separators). |
| `0x0000dbc8` | `void ui_dodge_result_apply_score(int game, uint *values)` | Applies a mini-game result to the save (block 0x0019f828): stores the score in world_get_minigame_score and the displayed values +0x28.. and computes the base DP +0x30 by game index: 0 score / 50 (record 0), 1 score / 150 (record 1), 2 score / 2 + ceil(time / 100) when cleared (records 2 and 3), 3 score / 10 (record 6), 4 wins * 20 + flag * 150 (records 5 and 4), 5 score / 50 (record 7), 6 score / 10 (record 8); each beaten record (save_get/set_minigame_record_k) adds 200 bonus DP (+0x34), sets the new-record flag +0x44/+0x46 and a marker byte at +0xec.. of the save record table; games 3 and 4 also set the from-story flag +0x1c (ui_dodge_result_is_from_story). |
| `0x0000e8ac` | `void ui_dodge_result_draw_labels(void *list)` | Draws the string-table labels of the result panel (words 1/3 and 2/5 for the section captions; row labels by game index: 4 for most games, 6/7 for game 2, 0x13/0x14 for game 4, 8/9 in the second section; words 10/0xb and 0xe/0xf for the totals; word 0xc centred at y 0x102), then the values (ui_dodge_result_draw_values). |
| `0x0000ef48` | `void world_dodge_pick_random_character(int scene, int *out_character, int *out_variant, int exclude_character, int exclude_variant, int *exclude_list, int exclude_count)` | Chooses a random opponent: candidates are characters 1-0x8e that exist (world_character_exists), are not exclude_character or in exclude_list, have a partner deck and are not 0 or 1; a group of special characters (0x18, 0x1a, 0x1b, 0x21, 0x25, 0x27-0x29, 0x2b-0x2d, 0x79-0x7e) needs a variant with save character flag bit 0. |

## Purpose and flow

`rel_dodge` (scene 0x11, 107,436 bytes, image base 0x0) is the "dodgeball" mini-game. Despite the name it is a turn-based 2-vs-2 artillery game: four fighters stand on columns of breakable blocks, and on its turn each fighter moves, picks one of five ball kinds, sets an angle and a power, and throws; balls fly under gravity, break blocks and damage fighters. Fighters whose column loses its blocks fall out.

- Entry `world_dodge_module_entry` (0x00000000) registers the scene: start 0x00000054, end 0x00000110 (not in the registry), data 0x00015500.
- `world_dodge_scene_start` (0x00000054): static init, `world_dodge_scene_init` (reads `world_get_dodge_params`: words 0/1 = character/variant, word 6 = light period or 1 from the menu), registers the frame callback 0x00000198 (`ui_duel_draw_frame_if_active` twin, which calls `world_dodge_game_draw` while 0x0001550c is set) and the leave callback 0x000001c4, then loops `world_dodge_scene_update` until done and returns with `system_scene_return(0x11, 0)`.
- Game state 0x00015520 (`world_dodge_game_update`): 0 load `basic_lang_<lang>.ehp` -> 1 wait -> (callback) 2 title layout (resource 0xb), sound 0x7aa2 -> 3 pick the two enemies (`world_dodge_pick_random_character`) -> 4/5 load the sprite files of character slots 0-3 -> 6 title wait, build the match, music track 0x19 -> 7 match set-up -> 8 run the match -> outcome: win: stage + 1 and state 9; draw: state 9; loss: state 0xb -> 9/10 "continue?" dialog (strTbl word 6; result 2 continue, 3 or -2 quit) -> 0xb score count-down -> 0xc after the fade: state 3 (next stage, new enemies) or 0xd -> 0xd result screen (`ui_dodge_result_create(heap, mini_result, game 1, &score)`) -> 0xe result loop (outcome 2 = play again: score and stage reset, state 2; 3 = leave) -> 0xf shutdown, scene returns.
- Draw (`world_dodge_game_draw`): layer 0 GE set-up; layer 1 the match (states 8-0xc); layer 4 score panel (states 6-0xc), fade, dialog (state 10), title (title flag, states 2-8), stage banner (strTbl word 0xe with stage + 1, alpha ramp over 60 frames), result screen (state 0xe).

## Match (states in 0x00195780)

`world_dodge_match_update`: 0 turn begin (stunned fighters go to 2) -> 1 move (action slot 0) -> 4 item (slot 1) -> 5 aim (slot 2) -> 6 power (slot 3) -> 8 launch -> 9 flight (hit tests, camera follows the ball) -> 10 end check -> 0xb next turn (order table 0x00013e6c, skips dead fighters, turn count + 1) -> 0xc turn banner -> 0. State 2 (stunned: wait 60 frames or confirm, stun - 1) and 3 (stun emote) end the turn. State 7 is a free camera entered from states 1, 2, 4 with the analogue stick on the player's turn. End: 0xd pause, 0xe outcome layout (win/loss/draw = resources 0xc/0xe/0x10 with TMF members 0xd/0xf/0x11), 0xf on a win starts the score tally, 0x10 tally, 0x11 stores the four hit points in the carry-over array (0x000156f8) and ends the match.

Teams and fighters (`world_dodge_match_setup`): fighter 0 = the player (character 1, the human vtable), fighter 1 = the parameter-block character (CPU team-mate), fighters 2-3 = two random enemies (CPU). So in this game the parameter-block "opponent" words are the player's partner, not an opponent (correction to the reading in world.md "Mini-game parameter blocks"; confidence high from the init calls). Enemy hit points by stage: 1 (stages 0-4), 2, 3, 4, 5 (20+); the player team has 5 each, carried over from stage 21 on. CPU skill (+0x240) = stage * 10. Start columns: team 0 random in 0-7, team 1 near column 0x17.

Score of a won stage (`world_dodge_calc_score`, tally screen `world_dodge_score_draw`): (A(hit points of fighters 0+1) + B(turn count) + C(accuracy %)) * (k * (stage + 1) + 1); A: 2000 for 10 hit points, 1000 for 9, then 800/600/400/200/10; B: 2000 - 100 * turns (min 0); C: 100 % -> 2000, 90-99 -> 1000, 80 -> 800, 70 -> 600, 60 -> 400, 50 -> 200, else 10; accuracy = player-team shots that hit an enemy / player-team shots. k is the float at 0x00013e08 = 0.1 (0x3dcccccd), so the stage multiplier is 0.1 * (stage + 1) + 1.0; `world_dodge_scale_by_frames` uses the same constant (0.1 * value * frames / 30). The final score goes to the shared result routine as game index 1.

## Key structures

- Block grid 0x001957a0: 120 blocks of 0x150 bytes, index = column * 5 + row (24 columns x 5 rows), x = column * 52 + 26, y = row * 30 + 42 (world y grows upwards; screen y = -(y - camera) + 136). Block: +0x00 x, +0x04 y, +0x08 present, +0x0c breaking, +0x10 finished, +0x14 break frame, +0x18 four debris particles of 0x2c bytes, +0xc8 falling, +0xcc target row, +0xd0 fall count, +0xd4 fall frame, +0xe0 ehf parameter block (0x60), +0x140 break-layout work buffer. Column heights are random 1-5 at stage start. Debris by particle 0-3: u/v table 0x00013cb0 = (0x160, 0), (0x1b0, 0), (0x160, 0x50), (0x1b0, 0x50); speed 0x00013cd0 = 0, 0, 0.5, 0.5; particle +0x24 from 0x00013ce0 = 0, 1.0, 0.1, 0.1; scale step 0x00013cf4 = 0.05. In the particle only the scale is a float kept in an int field; the offset +0x18 is an integer.
- Match flags 0x00015710: word 0 set when fighter 0 or 1 is dead, word 1 when fighter 0 is dead (`world_dodge_match_state_turn_begin`), word 2 when fighter 0 or 1 is stunned (`world_dodge_match_update`).
- Score digits: cell 10 x 12 (0x00013e14); uv table 0x00013e1c starts at (0x19c, 0xbc), u advancing by 10.
- Fighter (0x290 bytes CPU / 0x380 player; vtable at +0x234: base 0x00015278, CPU 0x000152c8, player 0x00015318): +0x00 character, +0x04 variant, +0x08 side 0-3, +0x0c team, +0x10/+0x14 x/y, +0x1c/+0x20 column/target column, +0x24/+0x28 facing, +0x2c knock-away frame, +0x30 state (1 stand, 3 jump, 4 hit shake, 5 knocked away, 6 fall start, 7 falling, 8 out), +0x34 hit-effect flag, +0x38 stun counter, +0x3c active, +0x40 hit points, +0x44/+0x48 panel flags, +0x4c timer, +0x50 frame counter, +0x58 shake counter, +0x5c jump t, +0x60/+0x64 velocity, +0x70 three effect slots of 0x80 bytes (ehf work at +0xe0), +0x1f0/+0x1f4 sprite buffers, +0x1f8 model slot, +0x1fc emote controller (6 words), +0x214 active-action mask, +0x218..+0x224 action-ready flags, +0x228 grid, +0x22c shot system, +0x230 partner. CPU: +0x240 skill, +0x244..+0x264 nine AI bytes from `world_get_character_bytes_49` (item weights 0-4, base accuracy, move bias, move probability, one unused here), +0x268 item, +0x26c/+0x270 angle gauge/direction, +0x274/+0x278 power gauge/direction, +0x27c move decision, +0x280 accuracy, +0x284/+0x288 planned angle/power. Player: +0x360 start column, +0x364 item, +0x368/+0x36c angle, +0x370/+0x374 power.
- Fighter vtable entries seen: +0x08 reset, +0x0c free, +0x10 update, +0x14 draw, +0x18 init, +0x1c turn begin, then four action slots of three entries (+0x20 start, +0x24 poll, +0x28 draw for slot 0; +0x2c/+0x30/+0x34; +0x38/+0x3c/+0x40; +0x44/+0x48/+0x4c). Read from the data (high): +0x08 0x918, +0x0c 0x9d0, +0x10 0xa3c in all three vtables, then:

  | Slots | CPU 0x000152c8 | Player 0x00015318 |
  | --- | --- | --- |
  | +0x14 / +0x18 / +0x1c | 0x4918 / 0x496c / 0x49fc | 0x524c / 0x13dc / 0x52a0 |
  | +0x20 / +0x24 / +0x28 | 0x4a04 / 0x4b88 / 0x4bf8 | 0x52ac / 0x52b8 / 0x5420 |
  | +0x2c / +0x30 / +0x34 | 0x4c00 / 0x4d9c / 0x4dac | 0x5428 / 0x5448 / 0x5544 |
  | +0x38 / +0x3c / +0x40 | 0x4db4 / 0x5008 / 0x5158 | 0x554c / 0x5554 / 0x56b8 |
  | +0x44 / +0x48 / +0x4c | 0x5160 / 0x5168 / 0x5244 | 0x56c0 / 0x56c8 / 0x5790 |

  So `world_dodge_human_turn_begin` (0x52a0, stores the current column +0x1c as the start column +0x360) is the turn-begin slot run by `world_dodge_match_state_turn_begin`, and `world_dodge_human_move_begin` (0x52ac) the move-start slot run by `world_dodge_player_step_action0`.
- Shot system 0x0019f520 (>= 0x6c bytes): +0x00 5 x 3 ball pointers (row = kind; count per kind from 0x00014040, kind 1 is a fan of several balls released every 10 frames, 5 degrees apart), +0x3c kind (-1 idle), +0x40 position, +0x48 direction, +0x50 power, +0x54 team flag, +0x58 real-shot flag (0 for the CPU's simulation), +0x5c launched, +0x60 frame, +0x64 "rose > 63 above the launch point" flag (enables friendly fire), +0x68 grid. Damage per kind: table 0x00014054. Hit sounds by kind: 1 0x7a9c, 4 0x7a9a, 3 0x7a9d (stun), others 0x7a9b.
- Ball (0x3c bytes, vtable +0x38: base 0x00015368; kinds 0-4: 0x000153e8, 0x000154a8, 0x00015468, 0x00015428, 0x000153a8): +0x00/+0x04 position, +0x08/+0x0c velocity, +0x10..+0x1c box, +0x20 active, +0x24 frame counter, +0x28 spin frame 0-5, +0x2c spin direction, +0x30 bounce count, +0x34 grid. The five method groups are named a, b, c, bounce, e by address; from the vtable data and the constructors `world_dodge_ball_construct_kind0..4` (high): kind 0 = b, 1 = e, 2 = bounce, 3 = c, 4 = a. Gravity 2.0 for all; radius 20.0, 10.0 for group e. The bounce ball (kind 2) rebounds up to three times at 0.75 speed in a random direction within +-90 degrees; +0x30 is incremented only at 0xa6f4, inside its method group.
- Ball vtable slots (all six vtables: 0x00015368 base, 0x000153a8 a, 0x000153e8 b, 0x00015428 c, 0x00015468 bounce, 0x000154a8 e): +0x08 gravity, +0x0c grid collision (0x00009cb4, shared), +0x10 block contact (called from `world_dodge_ball_collide_grid` at 0xa1d8 with a vector in a1), +0x14 breaks blocks, +0x28 set grid, +0x30 `world_dodge_ball_get_velocity` (0x75f4, shared), +0x38 radius, +0x3c hit method. Slot +0x10: groups b, c, e clear active (`*_stop`), the bounce ball rebounds, group a does nothing (`world_dodge_ball_a_nop`). Slot +0x3c stops the ball on a fighter hit for all but the bounce ball, whose 0x0000a720 calls its own slot +0x10.
- Launch: `world_dodge_ball_launch_base` ends with `j thunk_system_vfpu_vector2_scale` (a0 = ball + 8, a1 = dir, f12 = 0.17 * power, float at 0x00013f48), so velocity = dir * 0.17 * power. The launch wrappers take a sixth argument in t1: `world_dodge_ball_a_launch` plays sound 0x7a9e when it is non-zero.
- Emote controller (+0x1fc): animation table 0x00014100 + id * 0x40 of (cell, duration) pairs ending with -2; drawn from resource 10 above the fighter (balloon 44x36 + icon 24x24). Ids used: 0 fall, 3 falling, 5 hurt, 8 stunned, 9 last hit point.
- Camera: position 0x00015510/0x00015514 eases towards the target 0x00015518/0x0001551c (clamped x 0xf0-0x3f0, y 0x80-0x4eb).
- Module heap: 0x180000 bytes at 0x00015720 (handle 0x00195744), also the field_3d allocator. Archive slots 0x00195720 (0x24 bytes: name, pointer +0x20); character sprite slots 0x00195754 (4 x 2 pointers). Static constructor/atexit helpers at 0x81bc-0x82e8.

## Files

- Container root 8, path `dodge/%s` (format 0x00014c0c; the root's directory was not checked here): `basic_lang_<lang>.ehp` (names at 0x000147b0, stride 0x20, by `save_get_language`) and the character sprite files `sdchr...%s` (format 0x00014c00) named by `world_get_character_model_entry_words` (field-model characters) or `world_get_character_word_14`/`_10`.
- Resource table 0x00014870 (0x24 bytes: member name, archive slot): 0 `strTbl.bin` (dictionary words used: 1-5 item names, 6 continue question, 7/8/0xd/0xf/0x10/0x12 help lines, 9-0xc/0x11/0x13/0x15/0x16 tally labels, 0xe stage banner, 0x14 turn caption), 1 main sprite atlas, 2-4 backgrounds by light period (2 default, 3 period 2, 4 periods 3-4), 5/6 power gauge (team 0/1), 7/8 angle gauge, 9 block-break / hit effect layout, 10 emote atlas, 0xb title, 0xc-0x11 outcome layouts and their TMF members, 0x12 turn banner, 0x13 `mini_result_<lang>.ehp` (names at 0x00014b40).
- Result archive members: string tables `mini_result_<l>.bin` (0x00014c38), textures `result_mini01.gim`.. (0x00014e78), layouts `m_menu_bar01.ehf`.. (0x00014fb8).
- Audio: tracks 0x2c8 and 0x2d1 loaded at set-up, music 0x19 (match) and 5 (outcome); effects 0x7a04-0x7a06, 0x7a0c, 0x7a91-0x7aa2.

## BOOT.BIN and other modules

`world_get_dodge_params`, `save_get_minigame_block_1` (pointer kept in 0x000156ec, never read, as save-minigame-blocks.md says), `world_get_minigame_score` and the save record/DP/experience functions through the result routine, `world_get_character_bytes_49` (AI bytes), `world_character_has_partner_deck`, `save_test_character_flag_bit0`, character name and model getters, `system_scene_get_caller`.

## Result screen copy

0x0000c4f0-0x0000eee4 is the shared mini-game result screen (counterpart of `rel_title` `ui_mini_result_*`, named `ui_dodge_result_*` here because the code is not byte-identical). `ui_dodge_result_apply_score` has the same game-index switch as `ui_mini_result_apply_score`; rel_dodge passes game 1, so the dodgeball high score is save mini-game record 1 and the base DP is score / 150 (confidence high; answers part of the save-minigame-blocks open question for this game).

## Corrections to existing docs

- world.md "Mini-game parameter blocks": for `rel_dodge` words +0x00/+0x04 are the player's team-mate (fighter 1), not the opponent; the opponents are chosen at random per stage. Word +0x18 (period) selects the background (resources 2-4).
- save.md / save-minigame-blocks.md: dodge uses result game index 1 (record 1).

## Name mismatches

- `rel_dodge:0x00005be0` twin header `audio_heap_free`: the code is `system_heap_alloc` on the module heap; named `world_dodge_heap_alloc`. `0x00005bf0` (also `audio_heap_free` in the header) frees from the module heap, not the sound heap; named `world_dodge_heap_free`.
- Repeated twins inside the module were renamed to keep names unique: `0x00008c20` `world_dodge_draw_text_fit`, `0x0000d62c` `ui_dodge_result_draw_text_fit` (copies of `ui_draw_level_badge_text_fit`, kept at 0x00004210); `0x000093e4` `world_dodge_draw_text`, `0x0000bb3c` `world_dodge_score_draw_text` (copies of `ui_list_window_draw_text`, kept at 0x00004224).
- Twin names kept although their meaning here differs: `ui_init_cutin_subtitle` (0x00003e74) clears the match flag block 0x00015710; `ui_duel_draw_frame_if_active` (0x00000198) is the scene frame callback; `save_copy_file_data_desc` (0x00002794) copies a block rectangle.

## Open questions

- The item names of kinds 0-4; the damage table 0x00014054 and the ball count table 0x00014040 values.
- Group-a balls (kind 4) do nothing on block contact (slot +0x10 is `world_dodge_ball_a_nop`), so they seem to keep flying through blocks; this comes from the slot contents only, confirm in PPSSPP.
- Exact meaning of the free-camera trigger (only positive analogue values tested in the decompilation); what reads the match flag word 2.
- The turn-order table 0x00013e6c.
- Whether the end callback 0x00000110 and the leave callback 0x000001c4 exist as functions (not in the registry).
