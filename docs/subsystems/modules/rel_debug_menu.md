# `rel_debug_menu`

Module document of the 2026-11-04 round 6 (all game modules imported; `../modules.md`). English, evidence-based: the sections below come from reading every function of the module in the Ghidra decompilation; hypotheses carry a confidence.

| | |
| --- | --- |
| File | `PSP_GAME/USRDIR/gmodule/rel_debug_menu.prx`, 52,540 bytes, plain ELF (relocatable PRX) |
| Slot | scenes 0, 1, 0x0c, id 0x10 |
| Exports → importers | — |
| Role (catalogue) | Debug menu: `printf` formats, `deck_load_recipe`, `save_open`, starts duels (scene 6). |
| Runtime base | unknown; imported at image base 0x0, so addresses are module offsets |
| Registry ids | `rel_debug_menu:0x…` |
| Functions | 45 own functions, 45 documented in this round (system 42, ui 3); tables in `../functions/<group>.md`, section `rel_debug_menu` |

## Key functions (largest)

| Address | Prototype | Summary (first sentence) |
| --- | --- | --- |
| `0x00000034` | `void system_debug_menu_scene_main(void)` | Scene start callback and main loop of the debug menu: sceKernelChangeCurrentThreadAttr(0, 0x4000), creates an 0x800000-byte heap on the module's own memory at 0x98a0 (system_heap_create, kept in 0x9890), hides the loading overlay, installs the frame callback system_debug_menu_draw_frame with leave callback 0xc4c (system_scene_set_frame_callback(1, ...)), sets font colour 0 and clears the state words; when the current scene transition (system_scene_get_transition) is all zero (the game booted straight into this scene) starts in state 0x5a (autoload), else state 0. |
| `0x000002dc` | `void system_debug_menu_draw_frame(void)` | Frame callback of the debug scene: increments the blink counter 0x9854, starts libgu on layer 0 (system_ge_close_list_ehge_restart), clears colour/depth/stencil (sceGuClear 0x17), finishes the list (system_ge_open_list_ehge_sync), sets font scale 14 and prints the screen of the current state with system_font_printf: state 199 the net card test, 99 the net duel test, 0x5b and 4 the save utility dialogs (save_update_utility_dialogs), 7 the sound test (title, 10 rows of BGM/SE/character/variant/voice values, a bar of the current sound level, red text when a voice bank is not loaded, character name via world_get_character_name_string_first), 3 the 8-row option menu (current language name, region label), states 0-2 the menu title, the play time split from save state +0xc, up/down page markers and up to 15 entry names of the current menu table (second name pointer for non-Japanese languages); a cursor marker blinks with bit 3 of 0x9854. |
| `0x00000d40` | `void system_debug_menu_update_menu(void)` | State 1 input (pad state +0x24 menu repeat, +0x1c pressed, +0x20 released): up/down move the cursor 0x9848 with wrap, left/right move by 15 entries (page) together with the top 0x9844, the top follows the cursor within 15 rows; R (0x200) opens the option menu (state 3), L (0x100) the sound test (state 7: audio_set_sound_heap(debug heap), resets its values, loads tracks 0x2c8-0x2cf); releasing the confirm button (system_get_confirm_button(0)) advances to state 2, or for entry 0xe goes to state 99 and initialises the net duel test; releasing cancel returns to the root menu. |
| `0x000010dc` | `int system_debug_menu_update_options(void)` | State 3, an 8-item option menu (cursor 0x9848; R returns to state 1): on confirm (released) item 0 cycles the language 1-5 (save_set_language) and reloads card info (card_db_load_cardinfo, waiting for card_db_bind_cardinfo); 1 starts a new game (save_init_new_game), copies recipe 0 into the main/side/extra lists of members 0 and 1 (deck_set_member_slot_count/card), names member 0's deck after recipe 0, loads a cleared 0x858-byte duel set-up block (duel_setup_load_decks), save_set_setting_b1_bits3_4(2) and option flags 0 and 2 on; 2 fills the collection (system_debug_menu_fill_collection); 3 save_open(5) (save) and 4 save_open(4) (load), both to state 4; 5 starts a test duel: duel set-up buffer +0x188 = 3, +0x18c = 0, +0x190 = 5, +0x191 = 1, +0x192 = 1, +0x194 = 3, duellist 0 character 2 variant 0 recipe 1, duellist 1 character 4 recipe 0x15 (names and recipe decks copied), then system_scene_call(2, 6, 0) and returns 1; 6 opens the net card test (state 199); 7 switches back to Japanese (reloading card info and re-initialising the font on layer 4) and re-applies volume setting 2. |
| `0x00001690` | `void system_debug_menu_update_sound_test(void)` | Sound test (states 6 and 7), 10 rows (cursor 0x9848): left/right change row 0 BGM track 0x985c (0-0x2f), 1 SE bank 0x9860 (0-7, bank 0x2c8 + n), 2 SE index 0x9864, 3 character 0x9868 (2-0x8e), 4 variant 0x986c (0-2), 5 voice bank offset 0x9870 (0-6), 6 voice index 0x9874 (below 0x35 for character category 1, else 0x91), 7-9 volume settings 0-2 (0-15, audio_set_volume_setting); when no direction is held the voice bank audio_get_voice_bank(character, variant) + offset is loaded (releasing the previous one in 0x9888 and waiting for audio_get_bank_data); square queues the duellist voice cues 0x71, 0x77, 0x78, 0x72, 0x7b, 0x7c for side 0 (duel set-up +0x1b8 = the bank), triangle stops duellist voices, cancel stops all sounds (fade 400), confirm plays the voice (row 6), the SE (row 2) or the BGM track (row 0); L returns to state 1 and restores the default sound heap. |
| `0x00001edc` | `void system_debug_menu_fill_collection(void)` | Debug collection set-up: sets the owned count of every card id 0xe88-0x1f39 to 0, clears member 0's deck and fills its main/side/extra lists from recipe 0, adding one owned copy per card; when the option cursor 0x9848 is 2 (always, since only item 2 calls it) adds 3 copies of every card id; for each character 0-0x8e that exists (variant 0) and can duel unlocks all its recipes (deck_get_owner_recipe, save_unlock_recipe, save_add_character_entry); sets character flag bit 2 for the (character, variant) of the 0xae character rows (world_get_character_key). |
| `0x000021c4` | `int system_debug_menu_net_card_step(void)` | Net card test, dispatched on system_net_api_get_manager_state: states 5, 7, 8, 9 set status 0x8098b4 = 0; 0x1e (in a room) status 3, member list into 0x809cb8, cross requests manager state 0x13; 0 requests state 4; -1 terminates networking (system_net_term) and returns 2; 0xb (lobby) status 1 with a card id editor: row 0x80a040 (up/down) 0 edits digit 0x80a744 (left/right, 0-3) of the id 0x80a748 with L/R subtracting or adding 10^digit (clamped to 0xe88-0x1f39), row 1 steps by card_db_get_sort_position (left/right) or by top-card group (L/R, card_db_get_top_group/top_card); START with a valid card sets room info +0x44 = 1 and +0x6a = the id and hosts a room (system_net_api_host_room(0x80a048)); cross requests manager state 0x21. |
| `0x000025d8` | `void system_debug_menu_draw_net_card(void)` | Draws the net card test by status 0x8098b4: status 3 prints the card name (blinking, scale 16, ruby enabled for Japanese) and the 9 member entries (0x14-byte records at 0x809cb8, name at +0x14 or a placeholder) and reads the room counters; status 1 prints the digit carets (row 0), a row marker, the card id with printf and its name (card_db_get_name) or an unknown marker. |
| `0x000029e4` | `void system_debug_menu_edit_room_rules(void)` | Room-creation editor (status 0x80a74c = 2): cross cancels (0x80aedc = 0); START hosts the room described by the 0x6c-byte room info 0x80aee0 (system_net_api_host_room) and leaves the editor; up/down move the row 0x80aed8 (0-4); the room name +0x4a is set to a fixed ASCII string; left/right on rows 1-4 toggle +0x45 (1/2, tag duel), toggle +0x46 (1/2, single/match), cycle +0x47 (0-5, life points) and +0x48 (0-4, time limit). |
| `0x00002b80` | `void system_debug_menu_update_lobby(void)` | Lobby (manager state 0xb): triangle (pressed) opens the room editor with defaults (+0x45 = 1, +0x46 = 1, +0x47 = 0, +0x48 = 0, player name at +4); while editing calls system_debug_menu_edit_room_rules; otherwise status 1, exchange step 0x80af4c = 0, cursor 0x80a750 (0-8) over the room list (system_net_api_get_room_list into 0x80a780, 0x6c-byte entries), circle joins the selected room when present (system_net_api_join_room with the player name and a fixed ASCII name), cross requests manager state 0x21. |
| `0x00002e90` | `int system_debug_menu_exchange_decks(void)` | Data exchange of the net duel test (manager state 0x1f, status 7), step 0x80af4c, using a 0x200-byte packet at 0x80af54 (u8 +0 type, +2 phase, +3 ready, UTF-16 text at +4) sent with system_net_api_send_game_data: 0 sends type 1 phase 1 with the player name; 1 when all peers reached phase 1 (system_net_api_check_peers_sync(1, 4, 0xff)) copies each peer's name (0x30-byte slots at 0x80b154) and sends phase 2; 2 the host (peer 0) waits for sync(1, 2) and sends type 2, clients wait for the host's type 2; 3 left/right choose a recipe 0x80a77c (0-0x1cd), sending its name, until the local state is 2; 4 the host on sync(2, 2) and circle, or a client when the host step is 1, sends ready; local state 1 goes back, cross re-sends phase 1, triangle calls system_net_set_word_bafc(0); 5 loads the chosen recipe into a 0x100-byte buffer and sets up a block transfer into 0x400 bytes; 6 when system_net_api_exchange_data_blocks completes copies each peer's 0xc0-byte deck to 0x80b2d4 and frees the buffers; 7 sends type 0xd and waits 8 frames (8); 0xb fills the duel set-up buffer: +0x190 = 1, +0x192/+0x191/+0x196/+0x197 = the room's tag, single/match, life-point and time rules (from the own room or the selected room), +0x193 = 0, +0x194 = 3, +0x195 = 2; for each peer a 0x1ac-byte duellist record with name, deck name, deck, recipe code 0x1ce, peer index, character 1 for the local peer (whose deck is also copied to set-up +0, with card flags 4, or for recipe 0x1d1 member 0's own deck and the save card-list states) and 0 for others; in a tag duel the missing members 2-3 get character 2 with recipe 1. |
| `0x00003730` | `int system_debug_menu_net_duel_step(void)` | Net duel test dispatcher on system_net_api_get_manager_state: 5, 7, 8, 9 set status 0; 0x1f runs system_debug_menu_exchange_decks and returns its result; 0x23 status 6, cross requests state 0x13; 0xe-0x11 status 5, circle requests state 0xb; 0x15 joining; 0x1e room members; 0xb lobby; 0 requests state 4; -1 terminates networking and returns 2. |
| `0x000038d4` | `void system_debug_menu_format_room_rules(void *room)` | For the five rule rows copies a label into a 64-byte local buffer: row 0 a fixed label, row 1 by +0x45 (1/2), row 2 by +0x46 (1 single, 2 match), row 3 by +0x47 (0-4: life-point values up to 16000), row 4 by +0x48 (0 no limit, 1-4: 30, 60, 180, 300 seconds); the buffer is never printed in the decompiled body (output probably compiled out; callers pass a second argument 5). |
| `0x00003cc8` | `void system_debug_menu_draw_members(void)` | Room-member draw (status 3): MAC string, room rules, blinking cursor at row 0x80a754 + 7, then for 9 member entries (0x14-byte records at 0x80ab50: present +4, flag +8, index +0xc, name +0x14, text +0x46) the index + 1, name and text, or a placeholder. |
| `0x00003eac` | `void system_debug_menu_draw_exchange(void)` | Exchange draw (status 7) for steps 3-5: in step 3 prints the local recipe choice (deck_get_recipe_name(0x80a77c)); then for each peer its number, its name slot (0x80b154 + 0x30 x i) and, when the peer's packet phase byte is 2, the recipe name it sent (copied into 0x80b214 + 0x30 x i), else a blinking waiting marker. |

## Purpose and flow

Scene module for scenes 0, 1 and 0x0c (id 0x10): the developers' test mode. Entry point `system_debug_menu_register_scene` registers start 0x34, end 0x264 and the word 0x8098a8. The module reserves an 8 MiB heap inside its own image (0x98a0..0x8098a0, `system_heap_create`); all net-test globals live after it (0x8098a0 onwards), so the module's memory size is far larger than its 52,540-byte file.

The start callback `system_debug_menu_scene_main` is a per-frame loop (`system_wait_frame`); drawing is done by the frame callback `system_debug_menu_draw_frame` (installed with `system_scene_set_frame_callback(1, 0x2dc, 0xc4c)`) using `system_font_printf` on a plain cleared screen (libgu `sceGuStart`/`sceGuClear`/`sceGuFinish` through BOOT.BIN's layer helpers). When the scene transition is all zero (the boot went straight to this scene), it starts with an autoload (`save_open(3)`), then reloads card info.

State word 0x9840:

| State | Handler | Meaning |
| --- | --- | --- |
| 0 | `system_debug_menu_fade_in` | Font-colour fade-in, then 1. |
| 1 | `system_debug_menu_update_menu` | Menu of 0x14-byte entries `{name, other-language name, handler, arg1, arg2}` (root table 0x9428, at most 0x32 entries, 15 rows per page). R: options, L: sound test, confirm: run, cancel: root. Entry 0xe opens the net duel test. |
| 2 | `system_debug_menu_run_entry` | Fade-out, then `handler(arg1, arg2)`. Handlers in this module: `system_debug_menu_call_scene(scene, arg)` (`system_scene_call(1, scene, arg)`) and `system_debug_menu_open_submenu(menu)`. |
| 3 | `system_debug_menu_update_options` | 8 options: language cycle, new game, fill collection, save (`save_open(5)`), load (`save_open(4)`), test duel, net card test, back to Japanese. |
| 4 | `system_debug_menu_wait_save` | Save task. |
| 6, 7 | `system_debug_menu_update_sound_test` | Sound test (BGM 0-0x2f, SE banks 0x2c8-0x2cf, voices per character/variant, three volume settings). |
| 0x5a-0x5c | autoload, wait, card-info reload | Boot path. |
| 99 | `system_debug_menu_update_net_duel` | Ad-hoc duel test (lobby, room rules, members, deck exchange), then scene 6. |
| 199 | `system_debug_menu_update_net_card` | Ad-hoc test that hosts a room carrying a chosen card id. |

The menu title line shows the play time from save state +0xc split at 30 frames per second (`system_debug_menu_split_play_time`): save state +0xc is the play-time frame counter (confidence medium: the split result is computed for the title line; the printf arguments are hidden).

## Duel set-up fields established here

The test duel and the net duel fill BOOT.BIN's 0x858-byte duel set-up buffer (`deck_get_duel_setup_buffer`) directly; together with the room-rule editor this names several bytes:

| Offset | Test duel | Net duel | Meaning |
| --- | --- | --- | --- |
| +0x188 / +0x18c | 3 / 0 | — | Unknown words. |
| +0x190 | 5 | 1 | Duel kind (5 debug/CPU test, 1 network; hypothesis, medium). |
| +0x191 | 1 | room +0x46 | 1 single, 2 match (room rule labels SINGLE/MATCH). |
| +0x192 | 1 | room +0x45 | 1 normal, 2 tag duel (matches `audio_select_voice_set_bank`). |
| +0x193-+0x195 | +0x194 = 3 | 0, 3, 2 | Unknown. |
| +0x196 | — | room +0x47 | Starting life points index (0-4; labels up to 16000). |
| +0x197 | — | room +0x48 | Time limit index (0 none, 1-4 = 30, 60, 180, 300 s). |

Duellist records (0x1ac bytes from +0x1a4): +0x1a4 character (1 = the player, 2+ = characters; 0 = remote peer), +0x1a6 variant, +0x1a8 1, +0x1aa / +0x1b0 peer index, +0x1ac recipe/deck code (0x1ce for a deck supplied in the record), +0x1b4/+0x1b8 voice words, +0x1bc name (0x32 bytes), +0x1ee deck name (0x40), +0x230 deck (0xc0). The test duel puts character 2 (recipe 1) against character 4 (recipe 0x15) and calls `system_scene_call(2, 6, 0)` (from scene 2, the story, not from its own scene id). The net tests call `system_scene_call(0xd, 6, 0)` (returning to the title).

## Network test structures

- Room info (0x6c bytes; own room 0x80aee0, card-test room 0x80a048): +4 UTF-16 player name (15 units), +0x44 card-test flag, +0x45 tag (1/2), +0x46 single/match (1/2), +0x47 life points (0-5 in the editor), +0x48 time limit (0-4), +0x4a ASCII room name, +0x6a card id (card test).
- Exchange packet (0x200 bytes at 0x80af54): u8 +0 type (1 hello, 2 host go, 0xd start), +2 phase, +3 ready, UTF-16 text at +4 (name or recipe name). Decks are exchanged as 0xc0-byte blocks with `system_net_api_set_block_transfer`/`exchange_data_blocks`.
- Manager states used: 0 (start, request 4), 5/7/8/9 (busy), 0xb (lobby), 0xe-0x11, 0x15 (joining), 0x1e (in room), 0x1f (exchange), 0x23, -1 (terminated); requests 4, 0xb, 0x13 (leave), 0x21.

## Name mismatches

None (no exports). Twin lines to `deck_editor_register_scene` (offset 0) are the generic entry shape and were not reused.

## Open questions

- Contents of the root menu table 0x9428 (entries and their scene arguments) and the option labels: read from `.data` to list which scenes the debug menu can start.
- `system_debug_menu_format_room_rules` builds labels that are never printed; its printf was probably compiled out.
- Meaning of duel set-up +0x188, +0x18c, +0x193-+0x195.
