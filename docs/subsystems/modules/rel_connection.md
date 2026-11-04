# `rel_connection`

Module document of the 2026-11-04 round 6 (all game modules imported; `../modules.md`). English, evidence-based: the sections below come from reading every function of the module in the Ghidra decompilation; hypotheses carry a confidence.

| | |
| --- | --- |
| File | `PSP_GAME/USRDIR/gmodule/rel_connection.prx`, 106,180 bytes, plain ELF (relocatable PRX) |
| Slot | scene 0x13, id 0x26 |
| Exports → importers | — |
| Role (catalogue) | Minigame: `connection/*.ehp`, SD-character sprites. |
| Runtime base | unknown; imported at image base 0x0, so addresses are module offsets |
| Registry ids | `rel_connection:0x…` |
| Functions | 300 own functions, 300 documented in this round (world 252, ui 42, field_3d 5, system 1); tables in `../functions/<group>.md`, section `rel_connection` |

## Key functions (largest)

| Address | Prototype | Summary (first sentence) |
| --- | --- | --- |
| `0x0000061c` | `int world_connection_app_update(void *app)` | App state machine (+0): reads the pad and runs all task updates (world_connection_task_mgr_update) first. |
| `0x00001f90` | `void * world_draw_character_sprite(void *list, void *tex_odd, void *tex_even, float *pos, int direction, int move_state, int frame)` | Draws a character as two textured quads (same code as rel_field): binds tex_even for even directions and tex_odd for odd ones, enables depth test, texturing, blending and alpha test, builds and draws the upper part (world_build_character_quad part 1) and the lower part (part 0) moved toward the camera (camera +0x30 scaled by 0x12eac); the model matrix is a translation to pos with a rotation about y by 0x12eb0. |
| `0x000024ac` | `float * world_connection_clip_motion(float *out, float *pos, float *velocity, void *grid)` | Keeps a moving character on walkable cells: speed = world_connection_vec3_length(velocity), direction normalised and rescaled; for each of four probe directions (constants 0x137d0, 0x137dc, 0x137e8, 0x137f4, normalised and scaled by the speed) it adds the probe to the four footprint corners of pos (world_get_cell_corners) and, when a corner lands on a cell that is not walkable (world_connection_get_cell == 0), lies below 0 or beyond the grid columns/rows (grid +8/+0xa), clears the velocity component pointing that way (probe 3 the positive x part, 2 the negative x part, 1 positive z, 0 negative z). |
| `0x00002a5c` | `void world_build_character_part_quad(int part, float *verts, int direction, int cell_id, int move_state, int frame)` | Fills 4 screen-space vertices for one part of a model-entry character (same code as rel_field): sprite cells from world_get_character_sprite_cell; projects the origin and a point 1.25 above it through projection * view * model (GU matrices read back, projection scaled by 64); 51-pixel-wide quad (x - 25 .. x + 26) in a 512 x 256 texture; part 0 a 50-row cell placed 80 - 12 pixels above the origin plus the per-frame offset, part 1 a 64-row cell from the origin to 64 - 12 pixels above; depths interpolated; u mirrored when the cell lookup reports a flip. |
| `0x000055f4` | `void * world_connection_radar_draw_dots(void *radar, void *list)` | Builds one point vertex {colour, x, y, z} per drawn character of the 500 slots, skipping the player and partner in the loop: free students blink in their team colour (team 1: 0xff0000ff with the blink byte in green; else 0xffff0000 with the blink in green), line members are solid (team 1 0xff0000ff, team 3 0xffff0000); then appends the player (0xff00e6ff) and the partner (0xff0080ff), and draws the point list four times with screen offsets (0x662/0x663, 0x714/0x715) for a 2 x 2 pixel dot. |
| `0x000058f8` | `void world_connection_radar_draw(void *radar)` | Radar task draw: when the stage is loaded sets the radar quad 0x13850 size from the grid's vertex columns/rows ((n + 1) * 0.5), a top-down camera (eye (4, 4, 4)-type constants, look-at 0) with the map centred and scaled by 0x12fe4, binds mini_sn_radar01.gim from connection/data.ehp, draws it on layer 4 at offset (0x662, 0x714), then the dots (world_connection_radar_draw_dots), and restores offset (0x710, 0x778) and the matrices. |
| `0x00006348` | `void world_connection_game_update(void *game)` | Game task update (state +0x7f8): 0 spawns the leaders once the stage is loaded, 1; 1 when the app reaches state 5 shows the start popup (kind 0), sound 0x7aab, 2; 2 when the popup is done closes it, plays BGM 0x19, enables every character and the radar, 3; 3 play: START (pressed bit 8) toggles pause (sound 0x7a09, popup kind 4 at +0x810; a second press only clears the flag), runs world_connection_game_tick: 2 (crash) or 3 (time up) -> BGM 5, freeze every character (state 2), stop the combo display, end counter 90, state 6 or 8; 1 (all collected) -> BGM 5, sound 0x7aab, counter 30, state 4; 4/8 when the popup is done sets the black overlay and closes it, 0xb; 5 waits for fade and popup, 0xb; 6 holds the crash popup at frame 0x1e for 90 frames or until any button, 7; 7 and 10 wait for the popup, 0xb; 0xb disables every character's update and sets finished +0x819 = 1. |
| `0x00006cbc` | `void world_connection_game_collect_students(void *game)` | For every free student (kind 2, unlinked, not joining) within squared distance 0.25 of the player: attaches it to the player's line (team 1) or the partner's line (other team), sound 0x7aa7; combo: with no combo running starts it (timer 300, count + 1) and opens a new combo display; with a combo running spawns count extra students of the same team that join the same line, adds 30 frames (max 300) and raises the count (max 9); then shows a bonus number at the player (world_connection_bonus_popup_create) and plays 0x7aa5. |
| `0x00007a38` | `void world_connection_hud_draw_timer(void *hud, void *list, int x, int y)` | Draws the time left (world_connection_game_get_time_left): a clock part at x - 0x1e, minutes (frames / 1800), a separator part, seconds ((frames % 1800) / 30), a separator and hundredths ((frames % 30) * constant 0x13348 * 100), each two digits. |
| `0x00009480` | `void * world_connection_pointer_draw_arrow(void *ptask, void *list)` | When the partner is off screen, projects both leaders, takes the normalised screen direction from player to partner and places HUD part 1 on the screen border (half extents 227 x 123 around (240, 136)) rotated to that direction; draws it, then draws it again additively with alpha sin(phase) * 127 + 127 (pulsing). |
| `0x00009cec` | `void * ui_draw_character_portrait_image(void *list, uint character, int x, int y, int scale, int offset, int inset, void *face_gim, void *body_gim)` | Draws a character portrait (same code as rel_duel_draw; nothing when face_gim or body_gim is NULL): characters 0x79-0x8d and those whose world byte 9 is 5 use a fixed 0x33 x 0x54 tile of body_gim at a per-character position; others use world_get_character_model_ids (face index, body column, palette level): the body tile 0x33 x 0x40 at column * 0x33, then the face tile 0x33 x 0x32 at ((i % 10) % 5) * 0x33, (i / 10) * 100 + ((i % 10) / 5) * 0x32 of face_gim at the palette level; sizes scaled by scale percent, texture offsets shifted by offset and shrunk by inset. |
| `0x0000ac94` | `void world_connection_ai_style_keep_away(void *ch)` | Partner AI style 1: farther than squared distance 100 from the player it collects like style 0 (speed by mode, picked student); nearer, it turns away from the player with the speed raised by mode and, when within 2.5 of the walkable border, steers along the stage corner (stage +0x38 corners) best aligned with its velocity (or with the away vector when farther than 2.5 from the player) while avoiding the nearest corner. |
| `0x0000c8e4` | `void * ui_connection_menu_ctx_draw_number(void *list, void *ctx, int table_base, int table_offset, int glyph_base, int mode, uint value, uint min_digits, int align, short x, short y, short width, uint color, short scale_x, short scale_y)` | Copy of rel_title ui_menu_ctx_draw_number: one string per digit (mini_result string glyph_base + digit); mode 0 as many digits as needed, mode 1 min_digits, mode 2 a time h:mm:ss.cc from hundredths with separator glyphs; drawn right to left from x + width. |
| `0x0000ce6c` | `void ui_connection_result_apply_score(int game, uint *score)` | Copy of rel_title ui_mini_result_apply_score (all seven games kept): stores the score in the result block and world_get_minigame_score(); for game 2 (this module): base DP +0x30 = score / 2, plus ceil(time / 100) when cleared (score[2]); the time goes to +0x2c and the cleared flag to +0x40; a score above save record 2 or (cleared) a time above record 3 adds 200 DP each, saves the record and sets the marker bytes +0xee / +0xef of the save record table; total +0x38 is added with save_add_dp, experience +0x3c = total / 25 (save_add_duelist_exp), 400 DP more on a level-up. |
| `0x0000db50` | `void * ui_connection_result_draw_labels(void *list)` | Copy of rel_title ui_mini_result_draw_labels: section titles 1/3, headers 2/5, per-game row labels (game 2: strings 6 and 7, the second only when cleared +0x40), DP rows 8/9 with unit 0xe, totals 10/11 with 0xe/0xf and the footer 0xc. |

Scene 0x13 (module id 0x26), imported at image base 0, so every address below is a module offset. 300 functions read: 285 named and documented, 15 skipped (14 empty vtable stubs and one empty 16-byte helper).

## Purpose

The "connection" mini-game is a two-leader line-collecting game on a small 3D stage. The player (character 1) and the partner (the character in the connection parameter block, `world_get_connection_params` words +0/+4) each lead a line. Free students (SD characters) wander the stage; a leader that touches a free student (squared distance <= 0.25, i.e. 0.5 units) adds it to the end of a line: the student's team decides which line (team 1 -> player's line, team 3 -> partner's line), whichever leader touched it. There are 400 students in all (`world_connection_game_get_remaining` = 400 - both line lengths). The round ends when:

- all 400 are in lines (result 1, popup kind 1, "cleared");
- the player crashes (result 2, popup kind 2): its head touches the stage edge, a member of its own line other than the first follower that is in front of it, or any member of the partner's line;
- the time limit runs out (result 3, popup kind 5): 18000 frames, shown as minutes = frames / 1800 and seconds = (frames % 1800) / 30, so the game counts at 30 fps (10 minutes).

Combo: collecting with the player starts a 300-frame combo window (count 1, combo display `mini_sn_chance.ehf` + `mini_sn_number.ehf`); each further collection inside the window spawns `count` extra students of the same team directly into the line, adds 30 frames (max 300) and raises the count (max 9). A rising bonus number (HUD part 0x1e + count) appears at the player. When fewer than 4 free students remain, up to 10 new ones are spawned on random cells more than 2 units from the player.

Score passed to the shared result screen (game index 2): students collected (400 - remaining), time left in hundredths of a second (`frames * 100 / 30`), cleared flag. With game 2 the result routine gives DP = score / 2 + ceil(time / 100) when cleared, and keeps records 2 (score) and 3 (time, only when cleared).

## Flow

- Entry point `world_connection_module_start` (+0x0): `system_scene_register(+0x38, +0xe4, 0x14b50)`.
- Start callback `world_connection_scene_main` (+0x38): creates the 0x300000-byte module heap at module +0x14b70 (pointer `0x00314b70`) and the app object, installs the frame callback (+0x1b4, draw) and the leave callback (+0x1e4, teardown) for id 2, runs `world_connection_app_update` once per frame until it returns 1, then `system_scene_return(0x13, 0)`.
- App state machine (`world_connection_app_update`, app +0): 0 stop sounds; 1 when loads are idle: create the tasks, start loading `connection/data.ehp` (slot 0), the language archive (slots 1-6), slots 7-0xb and the sdchr sheets of character 1 and the partner, open the intro popup (kind 3, white backdrop), sound 0x7aac; 2 wait 60 frames and all loads (the popup is held at frame 0xd), then VRAM reset and upload of slots 7-0xb; 3 wait for the popup, fade in from white; 4 wait fade; 5 game running until the game task sets its finished byte, then create the result task (priority 9); 6 result outcome 3 -> 7 (leave), 2 -> tear down the tasks and restart at state 0 (play again); 7 returns 1.
- Game task state machine (`world_connection_game_update`, +0x7f8): 0 spawn leaders when the stage is loaded; 1 wait for app state 5, start popup (kind 0); 2 popup done -> BGM 0x19, characters enabled; 3 play (START toggles the pause popup kind 4; `world_connection_game_tick`); 4/8 cleared or time-up: wait popup, black overlay; 6/7 crash: hold popup frame 0x1e for 90 frames or a button; 0xb disable all characters, finished byte +0x819 = 1. On any end the characters switch to state 2 (frozen: the player spins, the others are pushed away from it until they leave the stage).

## Task system (module-local)

All objects of the round are "tasks" with a common 0x20-byte base (constructor `world_connection_task_construct`, base vtable 0x14a24):

| Offset | Field |
| --- | --- |
| +0x00 / +0x04 / +0x08 | update priority, previous, next (update list) |
| +0x0c / +0x10 / +0x14 | draw priority, previous, next (draw list) |
| +0x18 | update enabled (byte) |
| +0x19 | draw enabled (byte) |
| +0x1c | vtable: +8 deleting destructor(obj, flags), +0xc init, +0x10 update, +0x14 draw, +0x18 term |

The list head is a base task at `0x00314bd8`; lists are sorted by ascending priority (`world_connection_task_register(task, update_prio, draw_prio, call_init)`, `world_connection_task_unregister(task, call_term)`). Priorities: stage 0, characters 1, game 2, bonus popup 3, radar 4, HUD 5, combo display 6, partner pointer 7, popups 8, result 9. Each frame the app runs all updates first (from the app update) and all draws in the frame callback.

| Task | Size | Vtable | Constructor | Methods (init / update / draw / term) |
| --- | --- | --- | --- | --- |
| app (not a task) | 0x30 | 0x149f0 at +0x2c | +0xaa4 | — |
| resources (not a task) | 0x704 | 0x149fc at +0x700 | +0x1384 | — |
| stage | 0xa4 | 0x14a40 | +0x5440 | +0x4d50 / +0x4da4 / +0x5138 / +0x5188 |
| character | 0x144 | 0x14a08 | +0x485c | (setup +0x32f8 called explicitly) / +0x43f8 / +0x4508 / ? |
| game | 0x81c | 0x14a78 | +0x709c | +0x5cc8 / +0x6348 / ? / +0x6794 |
| radar | 0x28 | 0x14a5c | +0x5c38 | +0x54d0 / +0x54dc / +0x58f8 / ? |
| HUD | 0x24 | 0x14ab0 | +0x88d0 | +0x7610 / +0x7618 / +0x769c / ? |
| popup | 0x90 | 0x14a94 | +0x7580 | +0x71e4 / +0x729c / +0x74fc / ? |
| combo display | 0xf0 | 0x14acc | +0x8c68 | +0x8a00 / +0x8a4c / +0x8bbc / ? |
| bonus number | 0x4c | 0x14ae8 | +0x9198 | +0x8d60 / +0x8da0 / +0x8ee8 / ? |
| partner pointer | 0x30 | 0x14b04 | +0x9c34 | +0x9274 / +0x9288 / +0x9b64 / ? |
| result | 0x30 | 0x14b20 | +0xb704 | ? / +0xb6a4 / +0xb6cc / ? |

The method assignment comes from the code (what each function touches) and the module's layout (methods sit just before their constructor); the vtable contents were not read (hypothesis, medium). The "?" slots are presumably the 8-byte empty stubs listed in skipped.tsv.

## Key structures

App (0x30 bytes, `0x00014b60`; singleton also at `0x00314b74`): +0 state, +4 black-overlay byte, +8 delay counter, +0xc resources, +0x10 stage, +0x14 game, +0x18 radar, +0x1c HUD, +0x20 popup (intro), +0x24 partner pointer, +0x28 result task.

Resources (0x704 bytes): +0x00 18 archive slots (see Files), +0x48 / +0x284 / +0x4c0 three 0x8f-entry tables indexed by character id (+0x48 sdchr body sheet, +0x284 sdchr head sheet, +0x4c0 never filled in the code read), +0x6fc pending-load count, +0x700 vtable. Load requests are 12 bytes `{destination slot, owner, buffer}` handled by the callback `world_connection_res_on_loaded` (+0xc3c), which binds EHP archives (3-byte magic at 0x13730).

Character (0x144 bytes):

| Offset | Field |
| --- | --- |
| +0x20 | position (x, y, z); y is the jump height above the floor |
| +0x2c | velocity (x, vertical speed at +0x30, z) |
| +0x38 | gravity (constant 0x12fe0) |
| +0x3c | speed (minimum 0x12fdc, maximum 0.25) |
| +0x40 | heading in degrees (-180..180) |
| +0x44 | on screen (byte, from the draw cull) |
| +0x48 | state: 0 free / settled, 1 joining a line, 2 frozen (round over) |
| +0x4c | touching the stage edge (byte) |
| +0x50 / +0x54 | sdchr sheets (characters without a field model) |
| +0x58 / +0x5c | shared sd_body / sd_head sheets (characters with a model entry) |
| +0x60 | trail ring: 10 entries of 16 bytes {position, direction}; followers copy the entry 4 frames behind their leader |
| +0x100 | trail index |
| +0x104 | character id |
| +0x108 | kind: 0 player, 1 partner, 2 student |
| +0x10c | team: 1 player's line, 3 partner's line |
| +0x110 / +0x114 / +0x118 | model ids (face index, palette level & 0xf, body column) |
| +0x11c / +0x120 | step counter, walk frame 0-5 |
| +0x124 | direction 0-7 |
| +0x128 | moving this frame |
| +0x12c | student wander timer |
| +0x130 / +0x134 | leader / follower (line links) |
| +0x138 / +0x13c / +0x140 | partner AI: style, speed mode, target preference (signed bytes +0x52, +0x53, +0x54 of the character record returned by `world_find_character`) |

Students' character ids come from two tables: 27 words at module 0x12eb4 (team 1) and 24 words at 0x12f20 (team 3), chosen at random.

Game task (0x81c bytes): +0x20 500 character slots, +0x7f0 player, +0x7f4 partner, +0x7f8 state, +0x7fc combo timer, +0x800 combo count, +0x804 time left (frames), +0x808 combo display, +0x80c current popup, +0x810 pause popup, +0x814 end counter, +0x818 paused, +0x819 finished.

Stage task (0xa4 bytes): +0x20 loaded, +0x24/+0x28 min/max walkable column, +0x2c/+0x30 min/max row, +0x34 hmp member, +0x38/+0x44/+0x50/+0x5c the four corners of the walkable rectangle (cell * 0.5), +0x68 light block. The stage model block is a module global at `0x00314b78` (0x60 bytes: heap, model instance `0x00314b7c`, grid origin `0x00314b80`, grid copy `0x00314b8c`); camera target `0x00314b90`; projection rotation `0x00314be0`; shadow basis `0x00314c20`; result block pointer `0x00314c70`.

Partner AI (`world_connection_partner_move`): style 0 collects while within distance 10 of the player and returns to the player otherwise; style 1 collects only when farther than 10 and otherwise moves away from the player, steering along the stage corners near the edge; style 2 always collects; style 3 always follows the player. Target preference: 0 nearest free student; 1 its own (non-team-1) colour first; 2 team 1 first. Speed mode: 0 minimum speed; 1 faster while a combo is running; 2 and 3 slow/fast variants per style (`world_connection_ai_style_*`).

Player control: D-pad for eight directions (the heading turns by a fixed step), pad bits 0xa000 held to speed up, pad bits 0x5000 pressed to jump (sound 0x7aa9), START (bit 8) to pause.

## Files

Path table at module 0x136a0: 18 entries `{u32 root, char *path}`; slot 0 is `connection/data.ehp`; slots 1-6 the language archives (save language l -> slot l + 1); slots 7-0xb the shared SD sprite sheets uploaded to VRAM (`world_connection_res_get_sd_sheet_textures` maps `sd_body_01.gim`, `sd_body_02.gim`, `sd_body_03.gim`, `sd_head_01.gim`, `sd_head_02.gim` to slots 7-0xb); slots 0xc-0x11 the result archives (language 0 -> 0xc, 1 -> 0xd, 2 -> 0xf, 3 -> 0xe, 4 -> 0x10, 5 -> 0x11). Only the first path string was visible in the decompilation; the others are inferred from the use of each slot (medium).

- `connection/data.ehp` members used: `mini_sn01.tms` (stage model), `mini_sn01.hmp` (walk grid, the layout of `docs/formats/hmp.md`), `mini_sn01.tmt` (animation), `mini_sn01.tma` (texture animation), `mini_sn_radar01.gim` (radar map), `sml_bup01.gim` (small portraits, 0x28 x 0x28 tiles, 12 per row, tile = `world_get_character_byte_3f`), `kao.gim` and `karada.gim` (face and body sheets for generic characters).
- Language archive members: popup layouts from the name table at 0x1394c (first `mini_sn_start.ehf`; six kinds), `mini_sn_chance.ehf`, `mini_sn_number.ehf`, `mini_sn_parts01.gim` (HUD parts; the part table at module 0x13038 is 16-byte float entries {u, v, w, h}: digits 0x13-0x1c, bonus digits 0x1e + n, labels 0x2b-0x30, the arrow 1, the bonus label 0x28).
- Per-character files (root 8): `connection/sdchr/<name>` with name = `world_get_character_word_10` (body) and `world_get_character_word_14` (head), loaded only for characters without a field model entry.
- Result archive: the shared mini_result helper names (`mini_result_<l>.bin` strings, `result_mini01.gim`, `m_menu_bar01.ehf`), same as rel_title.
- Sound: banks 0x2c8 and 0x2d2 are loaded; effects 0x7aa3 (footstep), 0x7aa5 (bonus), 0x7aa6 (combo tick), 0x7aa7 (collect), 0x7aa8 (joined the player line), 0x7aa9 (jump), 0x7aaa (crash), 0x7aab (start / cleared), 0x7aac (intro), 0x7a09 (pause), 0x7a05 (result button); BGM 0x19 during play, 5 at the end.

## Interface with BOOT.BIN and other modules

- `world_get_connection_params` (4 call sites): word +0 the partner character (also the HUD's second panel), +4 its variant (sprite load and portrait), +0x18 the light period, which selects the stage's ambient colour (`world_connection_get_period_ambient`: 1 white, 2 0xff5ac8ff, 3 0xffff8c78, 4 0xffbe7165, other 0xffffeed8).
- `world_get_minigame_score` is written by the result routine with the collected count.
- The result screen is a full copy of rel_title's `ui_mini_result_*` and `ui_menu_ctx_*` code (+0xb794..+0xe188), created with game index 2.
- Field rendering helpers are copies of rel_field (character sprites, cell corners, shadows) and rel_duel_draw (portrait image).

## Corrections to existing docs

- `docs/formats/save-minigame-blocks.md` / `save.md`: the connection module calls its result routine (`ui_connection_result_create`, +0xcd84) from `world_connection_result_task_start` (+0xb5f8) with the constant game index 2. So the connection mini-game is game 2 (records 2 = students collected and 3 = time left in hundredths when all 400 were collected; marker bytes +0xee/+0xef). The save doc's "+0xb680 work-state field" path is not what this module does (high).
- `docs/subsystems/world.md` (open question on character-table bytes +0x44..+0x74): bytes +0x52, +0x53 and +0x54 of the character record (`world_find_character(character, 0)`) are read by rel_connection as the partner AI style (0-3), speed mode (0-3) and target preference (0-2) (high for the read, medium for the meanings).
- `docs/subsystems/world.md` mini-game parameter blocks: connection block word +0x18 (light period) is read here for the stage ambient colour.
- `docs/subsystems/ui.md` line 72: the connection mini-game time base is 30 frames per second (18000-frame limit = 10 minutes).

## Name mismatches

- +0x0: the twin line names it rel_shop `shop_module_start`; kept as `world_connection_module_start` (same 3-instruction pattern, different callbacks).
- +0x258 / +0x268: twin lines say BOOT `audio_heap_free`; these are the module heap's allocator pair handed to `field_3d_set_allocator` (`world_connection_heap_alloc` / `world_connection_heap_free`, medium).
- +0xb794..+0xe188: not flagged as twins, but they are copies of rel_title `ui_menu_ctx_*` / `ui_mini_result_*`; named `ui_connection_menu_ctx_*` / `ui_connection_result_*` to stay unique per module. If the project prefers one name per code body, rename them to the rel_title names.

## Open questions

- The contents of the vtables 0x14a08-0x14b20 (which empty stub is which slot; the result task's init and term).
- The strings of the path table 0x136a0 beyond slot 0 and of the popup layout table 0x1394c beyond `mini_sn_start.ehf` (read the module's data to confirm the slot meanings above).
- The 16-byte function +0x15a0 called every frame by the stage update has an empty decompiled body.
- `world_connection_game_spawn_students` measures both distance checks from the player; the second was probably meant for the partner (behaviour as coded: only the player's surroundings are kept free).
- The third character table +0x4c0 of the resource object is freed but never filled in the code read.
- `world_character_has_field_model` == 0 selects the per-character sdchr sheets and the generic two-part sprite; == 1 the shared sd sheets with the model-entry renderer. The function's name suggests the opposite sense; check in PPSSPP which characters take which path.
- Exact values of the float constants (speeds 0x12fa0-0x12fe0, the hundredths factor 0x13348, presumably 1/30) were not read.
## Task vtables (module offsets)
| Vtable | Class | destructor | +0xc init | +0x10 update | +0x14 draw | +0x18 term |
| --- | --- | --- | --- | --- | --- | --- |
| 0x00014a08 | character | 0x4890 | 0x32f0 (empty) | 0x43f8 | 0x4508 | 0x4714 (empty) |
| 0x00014a24 | base task | 0x4d08 | 0x4b98 (empty) | 0x4984 (empty) | 0x49e0 (empty) | 0x4ca8 (empty) |
| 0x00014a40 | stage | 0x5474 | 0x4d50 | 0x4da4 | 0x5138 | 0x5188 |
| 0x00014a5c | radar | 0x5c6c | 0x54d0 | 0x54dc | 0x58f8 | 0x5c30 (empty) |
| 0x00014a78 | game | 0x70d0 | 0x5cc8 | 0x6348 | 0x678c (empty) | 0x6794 |
| 0x00014a94 | popup | 0x75b4 | 0x71e4 | 0x729c | 0x74fc | 0x7570 (empty) |
| 0x00014ab0 | HUD | 0x8904 | 0x7610 | 0x7618 | 0x769c | 0x88c8 (empty) |
| 0x00014acc | combo | 0x8c9c | 0x8a00 | 0x8a4c | 0x8bbc | 0x8c60 (empty) |
| 0x00014ae8 | bonus popup | 0x9218 | 0x8d60 | 0x8da0 | 0x8ee8 | 0x9190 (empty) |
| 0x00014b04 | pointer | 0x9c68 | 0x9274 | 0x9288 | 0x9b64 | 0x9c2c (empty) |
| 0x00014b20 | result | 0xb738 | 0xb5f0 (empty) | 0xb6a4 | 0xb6cc | 0xb6fc |

## Corrections
- `world_connection_stage_update` does not call an empty helper each frame: 0x000015a0 is `world_connection_stage_animate_model`, `field_3d_update_model(*(0x00314b7c), 0)` (one animation tick of the stage model).
