# `rel_blackjack`

Module document of the 2026-11-04 round 6 (all game modules imported; `../modules.md`). English, evidence-based: the sections below come from reading every function of the module in the Ghidra decompilation; hypotheses carry a confidence.

| | |
| --- | --- |
| File | `PSP_GAME/USRDIR/gmodule/rel_blackjack.prx`, 104,628 bytes, plain ELF (relocatable PRX) |
| Slot | scene 0x0f, id 0x22 |
| Exports → importers | — |
| Role (catalogue) | Minigame: blackjack (`mini_bj_*`). |
| Runtime base | unknown; imported at image base 0x0, so addresses are module offsets |
| Registry ids | `rel_blackjack:0x…` |
| Functions | 361 own functions, 361 documented in this round (world 299, ui 55, field_3d 5, audio 1, system 1); tables in `../functions/<group>.md`, section `rel_blackjack` |

## Key functions (largest)

| Address | Prototype | Summary (first sentence) |
| --- | --- | --- |
| `0x00000920` | `void * world_blackjack_card_draw(void *card, void *list)` | Draws one card of the table in 3D: alpha blending and lighting state, model matrix from position +0x04 and rotation +0x10 (sceVfpuMatrix4Transfer/Rot), then the card face (card_db_cip_write_image_texture from the cardm reader with the artwork variant save_get_card_value_bits4_6) on a quad of DAT_000135b0 x DAT_000135ac (world_blackjack_draw_quad), the cover texture (resource 4) with alpha cover * 255 (+0x20), and, rotated by the constant 0x000135b4 about Z, the back texture (resource 3). |
| `0x00001114` | `void * world_blackjack_card_draw_badge(void *card, void *list)` | Draws the small info badge next to an uncovered card: projects the card position (x - 0.5, offset in Z by a constant for hand slots 7-0x10 or 0x11-0x1a) to screen pixels (world_blackjack_project_to_screen), draws the badge frame (resource 2, region (100, 0x54) 0x1b x 0xe) and either, for monsters, a background piece (resource 0x10) plus the level glyph from the table 0x00013700 (8 bytes per level), or for frame-7/frame-8 cards the icon at table +0x68/+0x70 (glyph size from 0x000136f8). |
| `0x00001b78` | `void world_blackjack_table_draw(void *table, void *list)` | Draws the table on layer 1 (depth test off): slots in the 0x1c-entry order table 0x000135b8, each occupied slot's card unless it is moving, on top, or the hovered hand card (cursor slot 7-0x1a); then on layer 2 the hovered hand card, the moving cards and the on-top cards (world_blackjack_card_draw); finally the table model +0x43c with a matrix translated by the vector at 0x00013d00 and scaled by 2.0 (field_3d_draw_model with draw flags {1, 2}). |
| `0x00001f90` | `void world_blackjack_build_deck(void *table, uint *out, int count)` | Builds the blackjack deck: scans card ids 0xe88-0x1f39 that are valid, present in the cardm CIP, not tokens and not one of 0x1388, 0xecb, 0x1386, 0xeb3, 0x1387, 0xece, 0xea8, 0xecd, 0x1b4d, and buckets them as monsters by level 1-12, frame-7 cards and frame-8 cards (two passes: count, then fill malloc'd arrays). |
| `0x00002ca4` | `void world_blackjack_draw(void)` | Frame drawing (when the draw flag 0x00014b44 is set and the state is above 0): layer 0 3D view setup; on layer 1 for states 5-0xc the background, the score panel and the game (world_blackjack_draw_background, world_blackjack_draw_score_panel, world_blackjack_game_draw); on layer 4 the screen fade, the message window in state 10, the intro layout in states 3-8 while 0x000157d4 is set, the round banner (dictionary word 0xb formatted with round 0x00014b6c + 1, outlined text at (0x78, 200) fading in over 15 frames, held, then out until frame 0x3c of 0x00015840), and the result screen in state 0xe; finally the popup draw. |
| `0x00007b04` | `void * world_blackjack_draw_card_info(void *list, void *card)` | Draws the top-left card preview for the card under the cursor (card may be NULL): the card face at (5, 4) (ui_draw_card_face; id -1 when the card is face down or flipping), the frame glow with alpha = cover alpha * 255 (world_blackjack_draw_card_frame_glow), for an uncovered face-up monster the level badge (resource 2 piece and ui_draw_level_badge at (0x73, 0x90)), and the card name (card_db_get_name, black, scale 0xc) clipped to 0x75 x 0xe at (0xe, 0xa3). |
| `0x00008cbc` | `void world_blackjack_popup1_update(void *popup)` | Updates popup 1: builds the model matrix from the camera matrix (field_3d_get_camera +0x80), a translation (constants 0x00013ae8/0x00013ae4) and a uniform scale (0x00013ae0); state +0x54: 0 for 30 frames raises the backdrop alpha (+0x58 top byte, +0x14 per frame up to 0x80), then flips the card (world_blackjack_card_start_flip, 0x1e frames) and goes to 1; 1 rotates about Y by C * frame / 30 (C at 0x00013adc) for 30 frames, then calls the callback with the side and goes to 2; 2 holds up to 90 frames (confirm after 10 skips) -> 3; 3 lowers the alpha by 0x14 per frame and at 0 closes (world_blackjack_popup1_close, active index -1). |
| `0x00009800` | `void * world_blackjack_draw_portrait(float t, void *entry, void *list, int x, int y, int style)` | Draws a character portrait for a turn-ring entry centred at (x, y) with size 22 + t * 16 (+ the constant 0x00013b6c): a nine-slice frame from resource 2 whose piece depends on style (0, 1, 2) and the entry's side; then for named characters (world_character_is_generic == 0) the 0x28 x 0x28 icon number world_get_character_byte_3f (12 per row) from resource 0x22, otherwise the composed portrait (ui_call_draw_character_portrait_image with face/body resources 0x1b/0x1c, scale size * 100 / 0x33) clipped to the frame. |
| `0x0000b3f0` | `void world_blackjack_score_panel_draw(void *list)` | Draws the score panel with alpha 0x001f5a2c: a dimming overlay, three separator lines, the title (dictionary word 0xc) and the rows: word 1 with the distance points, word 3 with the card bonus, word 0x11 with their sum and unit word 9, the round multiplier printed with the wide format at 0x00014400, and word 0xf with the points still to transfer (cyan) and unit word 10. |
| `0x0000b960` | `void * ui_draw_character_portrait_image(void *list, uint character, int x, int y, int scale, int offset, int inset, void *face_gim, void *body_gim)` | Draws a character portrait (twin of rel_duel_draw): characters 0x79-0x8d and those with world byte 9 == 5 use a fixed 0x33 x 0x54 tile of body_gim; others the body tile and the face tile from world_get_character_model_ids; scaled by scale percent. |
| `0x0000c6ec` | `void * ui_blackjack_menu_ctx_draw_nine_slice(void *list, int kind, int colour, int x, int y, int width, int height)` | Draws a nine-slice box from the part table 0x000149a4 with the colour's texture offset (kind 2: colours from 0xc; kind 0: ((c % 6) * 10 + 0x17, (c / 6) * 10), colour 8 at (0, 0x74)). |
| `0x0000cf30` | `void * ui_blackjack_menu_ctx_draw_number(void *list, void *ctx, int table_base, int table_offset, int glyph_base, int mode, uint value, uint min_digits, int align, short x, short y, short width, uint color, short scale_x, short scale_y)` | Draws a number with one mini_result string per digit (glyph_base + digit, ui_blackjack_menu_ctx_get_message): mode 0 as many digits as needed (at least min_digits), mode 1 exactly min_digits, laid out right to left with step min(width / digits, scale_x); mode 2 a time in hundredths of a second with separator strings glyph_base - 5. |
| `0x0000d4b8` | `void ui_blackjack_result_apply_score(int game, uint *score)` | Scores a finished mini-game into the result block (pointer 0x001f5a34) and the save: stores the score values (+0x28/+0x2c/+0x40) and the main score into world_get_minigame_score(); base DP +0x30 per game (0: score / 50, 1: score / 150, 2: score / 2 + ceil(sub / 100) when score[2] is set, 3: score / 10, 4: score[1] * 20 + score[2] * 150, 5: score / 50, 6: score / 10); a new record (save_get/set_minigame_record_N, N 0-8) adds 200 DP (+0x34), sets the new-record flags +0x44/+0x46 and a marker byte in the save record table (+0xec..+0xf4). |
| `0x0000e19c` | `void ui_blackjack_result_draw_labels(void *list)` | Draws the result texts from mini_result_<l>.bin: section titles 1/3 and value headers 2/5, row labels per game (first section: 4 for games 0, 1, 3, 5, 6; 6/7 for game 2; 0x13/0x14 for game 4; second section 8/9 with unit 0xe), totals 10/11 with units 0xe/0xf, the centred footer 0xc at y 0x102, then the values (ui_blackjack_result_draw_values). |
| `0x0000e838` | `void world_blackjack_pick_random_opponent(int scene, int *out_character, int *out_variant, int partner, int partner_variant, int *excluded, int excluded_count)` | Picks a random opponent: collects characters 2-0x8e that exist (world_character_exists), differ from partner, are not in excluded[0..excluded_count), have a partner deck (world_character_has_partner_deck) and, for the special ids 0x79-0x7e, 0x1b, 0x1a, 0x18, 0x29, 0x28, 0x27, 0x21, 0x25, 0x2d, 0x2c, 0x2b, have at least one variant with save character flag bit 0 set; then draws a random character and variant (world_count_character_variants), rejecting variant 2 of characters 2 and 0x14 and variant 1 of 0x24 and 0xc, and re-drawing character 5 variant 1 when scene was called from the story (system_scene_get_caller(scene) == 2) with partner (6, 2); forces variant 1 for 0x1b and variant 0 for 0x29, 0x27, 0x26, 0x25, 0x10, 8 and 7. |

Scene 0x0f, module image base 0 in Ghidra (all addresses below are module offsets unless they are BOOT.BIN addresses 0x088xxxxx). 361 functions, all named and documented in this batch (no skips).

## Purpose and game rules

A card "blackjack" played as a 2-vs-2 tag match: the player's team (side 0: the player, controller slot 0, and the partner, slot 1) against two opponents (side 1, slots 2 and 3). The goal is a hand total as close as possible to 21 (0x15). Card rule (`world_blackjack_apply_kind_to_total`, 0x000044ec), confidence high:

- monster (kind 0): total += card level;
- card with `card_db_get_frame == 7` (kind 1): total *= 2;
- card with `card_db_get_frame == 8` (kind 2): total /= 2 (truncated).

(Frames 7/8 are the Spell/Trap frames per the other modules' usage; which is which was not checked here: hypothesis, medium.)

Each side alternates its two members per turn (side +0x08 toggles in `world_blackjack_side_begin_turn`). On a turn the current member picks either the deck (slot 0) or one of six face-up but covered field cards (slots 1-6). Field cards show their back of a cover texture until revealed; a field card's kind and level are hidden. A deck pick may be followed by more deck draws ("draw again" phase); afterwards the member decides to continue or stand. A hand holds at most 10 cards (hand slots 7-0x10 for side 0, 0x11-0x1a for side 1). When both sides have stood (`game +0xa10` then a second stand) the round is judged: the side closer to 21 wins, equal distance is a draw (`world_blackjack_game_state9_judge`, 0x00005d48).

While the player hovers a field card, the partner AI shows a hint (phase 3): its guess of the card's kind and level, correct with probability = the partner's accuracy byte (character table +0x48, see below). Partner hints, AI picks and AI stands all use the same guessed beliefs (`world_blackjack_ai_begin_turn`, 0x0000005c).

Scoring of a won round (`world_blackjack_calc_score`, 0x0000452c): (base + bonus) * (C * (round + 1) + 1), with base 2000/1000/100 for a final distance of 0/1/2 (else 0), bonus 100, 80, 70, ... 10 for 2..10 cards in hand (else 0), and C the float at 0x00013680 (value not read). Only side 0 is scored. The points are transferred into the running score 0x00014b64 by the score panel. After a win or a draw the player is asked whether to continue (dictionary word 2); a loss ends the run. At the end the shared mini-game result screen is shown with game index 0 (DP = score / 50, save record 0).

## Flow

- Entry `world_blackjack_module_start` (0x00007600) registers `world_blackjack_scene_main` (0x00007638) / `world_blackjack_scene_exit` (0x000076e4) with argument 0x001f589c.
- `world_blackjack_scene_init` (0x000076ec) reads `world_get_blackjack_params()` words 0 and 1 (partner character, variant) and calls `world_blackjack_init(char, var, -1, -1, -1, -1)` (0x0000290c). **Words 2-5 of the parameter block are not read**: the module passes -1 for both opponents, so both are always picked at random by `world_blackjack_pick_random_opponent` (0x0000e838).
- The frame callback `world_blackjack_frame_callback` (0x00007774) draws (`world_blackjack_draw`, 0x00002ca4); the scene loop calls `world_blackjack_update` (0x00002ad0) until it returns 1, then `system_scene_return(0xf, 0)`.
- Main state 0x00014b40 (`world_blackjack_update`): 0 wait for the card CIPs; 1 load the language archive; 2 waiting (load callback `world_blackjack_on_archive_loaded` binds the mini_result archive and sets 3); 3 intro layout; 4 set up a round (game block rebuild, new deck); 5 wait for images and intro; 6 pick opponents and set up players; 7 round banner; 8 play (`world_blackjack_game_update`); 9/10 continue question; 0xb score count-down after a loss; 0xc fade (continue -> 4, quit -> 0xd); 0xd result screen create; 0xe result screen (3 end -> 0xf, 2 retry -> state 3 with score and round reset); 0xf terminate.
- Game state (game block +0): 0 deal field; 1 wait; 2-5 opening card from the deck for the first side (+0xa00) then the second (+0xa04); 6 play / turn check; 7 turn-switch layout; 8 30-frame pause; 9 judge; 10 result layout; 0xb score panel; 0xc done. As read, `0x00014b60` is always 0, so `first side = 1`: the opponents' side opens.
- Side state (side +0x2c), `world_blackjack_side_update` (0x00006934): 0 pick, 1 after take, 2 draw again, 3 stand layout, 4 final layout, 5 next reveal, 6 show card, 7 flip, 8 wait flip, 9 uncover, 10 wait uncover (not entered), 0xb apply card, 0xc wait popup/HUD, 0xd continue question, 0xe turn over (still playing), 0xf stood.

## Controllers (players)

A controller slot is 0xc bytes {object, character, variant} at game +0xa14 + i * 0xc. Objects have a vtable at +0x20 and four phases run by `world_blackjack_obj_run_phase0..3` (0x00001798, 0x0000181c, 0x000018a0, 0x00001924): pending-start flag +4 + i * 4, active bit i of +0, start/poll/draw methods. Base object: +0x14 table, +0x18 own side, +0x1c other side.

| Vtable slot | Purpose | Human (0x00014adc) | AI (0x00014a4c) |
| --- | --- | --- | --- |
| +0x08 | init | 0x000047ac | not identified |
| +0x0c | term | 0x000047cc | not identified |
| +0x10 | turn begin | 0x000047ec (empty) | 0x0000005c (form guesses) |
| +0x14 | partner took a card | 0x000047f4 (empty) | 0x000002c8 (restart hint) |
| +0x18/+0x1c/+0x20 | phase 0 pick | confirm with cursor 0-6 | deck plan or best field guess |
| +0x24/+0x28/+0x2c | phase 1 draw again | window word 8 | counter vs plan |
| +0x30/+0x34/+0x38 | phase 2 continue/stand | window word 0xe | threshold rule |
| +0x3c/+0x40/+0x44 | phase 3 hint | returns 1 | stores cursor/card, draws guess |

Slot mapping beyond +0x08, +0x0c, +0x10, +0x14 and the call sites is by the order of the methods in the binary (medium). The human object is 0x148 bytes (message window at +0x28, 0x120 bytes); the AI object 0x88 bytes: +0x24 character, +0x28..+0x38 five parameters from `world_get_character_bytes_44` (character table bytes +0x44..+0x48): +0x28 chance % of the deck strategy, +0x2c planned deck draws, +0x30 spread of that plan, +0x34 stand threshold (distance to 21), +0x38 guess accuracy %; +0x3c decide-once flag, +0x40 deck strategy, +0x44 planned draws, +0x48 draws done, +0x4c best guessed distance, +0x50 hint slot, +0x54 hint card, +0x58[6] guessed kinds, +0x70[6] guessed levels. Meaning of the five bytes from their use here: medium.

## Key structures

- Game block 0x00014b70 (inside the 0xd20-byte globals cleared from 0x00014b40): +0 state, +4 table (0x4dc bytes), +0x4e0 side 0, +0x770 side 1 (0x290 bytes each), +0xa00/+0xa04 first/second side, +0xa08/+0xa0c current/previous side, +0xa10 one side has stood, +0xa14..+0xa43 controller slots, +0xa44 pointer to the score 0x00014b64, +0xa48 pointer to the round 0x00014b6c, +0xa4c result (0 win, 1 loss, 2 draw), +0xa50 selected result layout, +0xa54/+0xa58/+0xa5c win/lose/draw layouts, +0xa60 its parameters, +0xac0 turn-switch layout, +0xad0 its parameters, +0xb30 pause counter.
- Other globals: 0x00014b44 draw enabled, 0x00014b48..0x00014b5c the six init arguments, 0x00014b64 score (displayed clamped to 9,999,999), 0x00014b68 loss floor, 0x00014b6c round, 0x000156b0 message window, 0x000157d0 quit flag, 0x000157d4/0x000157d8/0x000157e0 intro layout flag/pointer/parameters, 0x00015840/0x00015844 round banner timer/flag, 0x00015848 frame counter, 0x0001584c save mini-game block 0 (stored, not read here), 0x00015850 score copy for the result screen, 0x00015854 bound mini_result archive.
- Table (game +4): 27 card objects of 0x28 bytes at +0, +0x438 next undealt card, +0x43c table model instance, +0x440 owner, +0x444 cardh requests issued, +0x448 slot table of 0x1c card pointers (0 deck, 1-6 field, 7-0x10 side 0 hand, 0x11-0x1a side 1 hand), +0x4b8[6] newly dealt field flags, +0x4d0 deal state, +0x4d4 cursor slot. Slot positions: 3 floats per slot at 0x00013888; cursor neighbour bytes at 0x00013818 (4 per slot); draw order table 0x000135b8.
- Card object (0x28 bytes): +0 card id (halfword), +0x04 position, +0x10 rotation (+0x18 Z), +0x1c/+0x1d animation frame/length, +0x20 cover alpha (1.0 hidden, 0 revealed), +0x24 bit 0 face up, bits 1-6 target slot, bits 7-12 source slot, +0x25 bits 5-7 animation (0 idle, 1 move, 2 flip, 3 uncover), +0x26 bit 0 drawn on top.
- Side (0x290 bytes): +0/+4 controller slots, +0x08 current member, +0x0c other member, +0x10 cards in hand, +0x14 table, +0x18 side index, +0x1c first hand slot, +0x20 turn counter, +0x24 timer, +0x28 other side, +0x2c state, +0x30 HUD (to +0x1ef), +0x1f0 hand total, +0x1f4/+0x1f8 hand-size indicator position, +0x1fc picked from deck, +0x200 cards taken this turn, +0x204 cards revealed, +0x208 opening deal, +0x20c slot being revealed, +0x210 continue answer, +0x214 last-chance turn, +0x218/+0x21c kind/level of the last card, +0x220 stand layout visible, +0x224 stand layout, +0x230 its parameters.
- HUD (side +0x30): +0 displayed total, +4/+8 change-text position, +0xc colour, +0x10 frame, +0x14/+0x18 base position, +0x1c t, +0x20 scale, +0x24 kind, +0x28 target, +0x2c delta, +0x30 step, +0x34 state (0 idle, 1-4 halve/double count, 5-6 level tokens), +0x38 12 tokens of 0x20 bytes, +0x1b8/+0x1bc spawn counters.
- Popups: table 0x00013aa0 of 0x14-byte entries {object, start, ?, update, draw}; active index 0x001f597c (-1 none). Popup 0 (object 0x30 bytes): card revealed on the table, name banner and a 16-copy glow (`world_blackjack_draw_reveal_glow`). Popup 1 (0x70 bytes, model resource 0x20): last deck card of a turn, shown on a rotating 3D card model whose texture is rendered into VRAM EDRAM + 0x160000 by the draw-state hook. Popup 2 (0x1c bytes): last field card of a turn, cover fading over 60 frames. Object addresses 0x001f58c0/0x001f58f0/0x001f5960 are inferred from the sizes and the hook's use of 0x001f58f0 (medium).
- Turn ring 0x001f5980: four {character, variant, side} entries in turn order, state +0x30 (1 slide in, 2 idle, 3 rotating), x offset +0x34, slide t +0x38, current index +0x3c, rotation t +0x40. Character 1 is the player (name from `save_get_player_name`).
- Race bar 0x001f59c4 (0x54 bytes): pointers to the two HUD totals, scale 0x001f59cc (max(40, totals) rounded up to 10), markers for 21 and both sides.
- Score panel 0x001f5a18 (0x1c bytes): state, distance, cards, round, points left, alpha, timer.
- Card-info preview 0x001f58ac (0x14 bytes): current card, enable flag, name scroll offset/state/timer.

## Files and resources

- Card art: `card_db_open_cardh_cip` and `card_db_open_cardm_cip` with readers in module memory 0x00195860 (0x40000 bytes) and 0x001d5860 (0x20000); the module heap is 0x00015860 + 0x180000 bytes (`system_heap_create`). Card faces are drawn with `card_db_cip_write_image_texture` using the artwork variant from `save_get_card_value_bits4_6`.
- Archives are loaded from root 8 as `blackjack/<name>` (`world_blackjack_request_archive_file`, 0x00004f70). Archive slot table 0x001f5860 (0x24 bytes per slot, loaded pointer at +0x20); only slot 0 is used: `basic_lang_<lang>.ehp` from a per-language table at 0x00013d70 (0x20 bytes per language).
- Resource table 0x00013e30: 0x24-byte entries {member name (0x20), archive slot}. Index 0 is `strTbl.bin` (the string table used with `card_db_get_dictionary_word`, words 1-0x11 used); 0x21 is replaced by the per-language name table 0x0001431c (`mini_result_<l>.ehp`). Use of the other indices: 1 background, 2 HUD atlas, 3 card back, 4 card cover, 5 card frame glow, 6 table model, 7 its animation, 8 cursor texture, 9/0xb/0xd win/lose/draw layouts with tmf 0xa/0xc/0xe, 0xf turn-switch layout, 0x10-0x15 card-view resources, 0x1b/0x1c portrait face/body images, 0x1d intro layout, 0x1e/0x1f stand layout and tmf, 0x20 popup card model, 0x22 character icon sheet (0x28 px icons, 12 per row, index = character byte 0x3f). Member names other than those quoted were not read from the data (inferred from use).
- Result screen (inside the mini_result archive): message tables named from 0x0001440c (`mini_result_j.bin`, 0x12 names), images from 0x0001464c (`result_mini01.gim`), layouts from 0x0001478c (`m_menu_bar01.ehf`).
- Sounds: banks 0x2c8 and 0x2d0; effects 0x7a83/0x7a84 reveal (other/monster), 0x7a85 intro, 0x7a86 popup, 0x7a87 turn switch, 0x7a88 stand, 0x7a89 card move/flip, 0x7a8e result, 0x7a8f/0x7a90 total count, 0x7a04 cursor, 0x7a0c window, 0x7a05 result button; music tracks 0x1b (game) and 5 (result).

## Deck construction

`world_blackjack_build_deck` (0x00001f90) takes card ids 0xe88-0x1f39 that are valid, present in the cardm CIP, not tokens and not one of nine excluded ids (0x1388, 0xecb, 0x1386, 0xeb3, 0x1387, 0xece, 0xea8, 0xecd, 0x1b4d); it builds a 40-card pool of 20 monsters (one per level bucket 1-12 in rotation, random member), 10 frame-7 and 10 frame-8 cards, shuffles it with 40 random swaps, forces entries 6 and 7 to random monsters and deals the first 27 ids to the table's card objects. A level bucket or frame group with no members would divide by zero (not guarded).

## Talking to BOOT.BIN and other modules

- `world_get_blackjack_params` (words 0 and 1 only), `world_get_minigame_score` (through the result screen's apply-score), `world_get_character_bytes_44` (AI parameters), `world_character_exists`, `world_character_has_partner_deck`, `world_count_character_variants`, `save_test_character_flag_bit0` (opponent pool), `world_character_is_generic`, `world_get_character_byte_3f`, `world_get_character_name_string`, `save_get_player_name` (portraits and names), `save_get_minigame_record_N`/`save_set_minigame_record_N`, `save_add_dp`, `save_add_duelist_exp`, `save_get_record_table` (result screen), `ui_card_view_open/close`, `ui_draw_card_face`, `ui_draw_card_blank`, `ui_draw_level_badge`, the list-window and EHF layout players, `field_3d_*` model functions.
- The result-screen code at 0x0000bde0-0x0000e7d4 is a copy of rel_title's `ui_menu_ctx_*` / `ui_mini_result_*` set (same logic, different addresses; the twin scan did not pair them). It was named `ui_blackjack_menu_ctx_*` / `ui_blackjack_result_*` to keep names unique; each row names its rel_title counterpart.

## Corrections to existing docs

- `docs/subsystems/world.md`, "Mini-game parameter blocks": rel_blackjack reads only words 0 and 1 of `world_get_blackjack_params()`; it passes -1 for words 2-5 itself (`world_blackjack_scene_init`, 0x000076ec), so the story's and menu's words 2-5 are ignored by this mini-game and both opponents are always random.
- `docs/subsystems/functions/world.md`, `world_get_character_bytes_44` (0x0885b4ac): "no module caller found" is outdated; rel_blackjack calls it (`world_blackjack_ai_set_character`, 0x00000000) and uses the five bytes as AI parameters (see Controllers).
- modules.md describes rel_blackjack only as "Minigame: blackjack (mini_bj_*)". The archive actually loaded is `blackjack/basic_lang_<lang>.ehp` (root 8); `mini_bj_*` names were not seen in the code read.

## Name mismatches

The following pack headers gave twin lines whose summaries do not fit the body (the scan masks call targets, so short wrappers with different callees match); own names were given instead:

- 0x000047ac / 0x000047cc (twin `field_3d_cmd_set_backdrop`): human controller init/term -> `world_blackjack_human_init`, `world_blackjack_human_term`.
- 0x00004d5c (twin `audio_heap_free`): allocates from the module heap -> `world_blackjack_heap_alloc`. 0x00004d6c (same twin) is the matching free on the module heap -> `world_blackjack_heap_free`.
- 0x000025c0 (twin `system_net_api_get_alive_peer_count`): 3D view setup -> `world_blackjack_setup_3d_view`.
- 0x0000605c (twin `duel_core_start_plain`): table destroy -> `world_blackjack_table_destroy`.
- 0x0000613c (twin `container_gzip_is_valid`): images-ready test -> `world_blackjack_table_images_ready`.
- 0x00007774 (twin `ui_duel_draw_frame_if_active`): the module's frame callback -> `world_blackjack_frame_callback` (same shape, different flag and callee).
- 0x0000a150 (twin `ui_field_close_message_window`): sets the turn-ring state to 3 -> `world_blackjack_turn_ring_advance`.
- 0x00007600 (twin `shop_module_start`): same shape, registered as `world_blackjack_module_start`.
- Several real twins occur more than once in this module; the first copy keeps the twin name, later copies get an address suffix: `ui_draw_level_badge_text_fit` (0x0000074c; copies `_37f0`, `_4038`, `_a268`, `_cf1c`), `ui_list_window_draw_text` (0x0000404c; copies `_8018`, `_b894`).

## Open questions

- Values of the float constants that shape the game: round multiplier C (0x00013680), flip angle (0x000135b4, 0x000135a8), card quad size (0x000135b0/0x000135ac), slot positions (0x00013888). Read them from the binary or PPSSPP.
- Which of frames 7 and 8 is Spell and which Trap (doubling vs halving).
- The resource member names at 0x00013e30 (only `strTbl.bin` and the language names were visible in the decompilation).
- The AI controller's vtable slots +0x08/+0x0c and the third word of each popup-table entry (+0x08) were not identified.
- Whether 0x00014b60 (first-side selector) can ever be non-zero: as read, the opponents always open.
- State 0xb of the main machine (score count-down after a loss) appears to finish at once because the floor equals the score; check in PPSSPP whether the score is reduced on a loss.
- Exact meanings of the human window answers (2 = first choice?) for dictionary words 2, 8 and 0xe; needs the string table.
