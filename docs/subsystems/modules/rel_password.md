# `rel_password`

Module document of the 2026-11-04 round 6 (all game modules imported; `../modules.md`). English, evidence-based: the sections below come from reading every function of the module in the Ghidra decompilation; hypotheses carry a confidence.

| | |
| --- | --- |
| File | `PSP_GAME/USRDIR/gmodule/rel_password.prx`, 44,680 bytes, plain ELF (relocatable PRX) |
| Slot | id 0x1a |
| Exports → importers | `libpassword_rel` (3) → labo, story |
| Role (catalogue) | Card password entry: `labo/password.ehp`. |
| Runtime base | unknown; imported at image base 0x0, so addresses are module offsets |
| Registry ids | `rel_password:0x…` |
| Functions | 41 own functions, 41 documented in this round (shop 31, ui 7, system 2, deck 1); tables in `../functions/<group>.md`, section `rel_password` |

## Key functions (largest)

| Address | Prototype | Summary (first sentence) |
| --- | --- | --- |
| `0x00000000` | `void ui_password_draw(void)` | Library draw entry of the password screen: clears layer 0 and, after loading (state 0x00016430 non-zero), draws on layer 4 the background (shop_password_draw_background), the panel (shop_password_draw_panel), the messages (shop_password_draw_messages), the keypad (shop_password_draw_keypad), the digits (shop_password_draw_digits) and the fade. |
| `0x00000150` | `void * shop_password_draw_background(void *list)` | Draws the background texture of resource 0x1001: eight 64-px columns across the top and, mirrored, four 64 x 64 tiles at y 0x100 on each half (same code shape as the conversion machine's background). |
| `0x000002d0` | `void * shop_password_draw_messages(void *list)` | Draws the message area of the password screen inside the scissor (0x19, 0x4e, 0x118, 0xa1), font scale 0xe, white, by state 0x00016430 and sub-step 0x00016432 (frame counter 0x0001756e). |
| `0x00000d8c` | `void * shop_password_draw_card(void *list, int x, int y, int card_id, uint frame, uchar alpha)` | Renders the card face of the found card (ui_draw_card_face with 0x0001756c) off screen and draws it at (x, y): while frame is below 0x78 as 0x9a horizontal line pairs whose x is offset by a decaying sine wave (sceVfpuScalarSin; amplitude 0x18 x (0x78 - frame) / 0x78, alpha growing with frame), afterwards as a plain sprite with alpha (when non-zero). |
| `0x00001128` | `int shop_password_load_resources(void)` | Stepped loader (bits 1-7 of 0x00008420): 0 opens the card-image reader (card_db_open_cardh_cip on the 0xe000-byte buffer 0x00008428, pointer 0x00017578) and starts loading labo/password.ehp (shop_password_load_archive); 1 waits for card_db_cip_is_ready; 2 resets the entry (shop_password_reset_entry) and opens the card view (ui_card_view_open with resources 0x1003, 0x1004, 0x1019, 0x1005, 0x1006 and the reader); 3 returns 1. |
| `0x00001354` | `void * shop_password_get_resource(uint id)` | Finds id among the 0x11 16-byte records at 0x000082c8 (shop_password_find_resource) and, when not cached, looks the member up in labo/password.ehp with its name format and the language letter (container_ehp_find_member); members 0x1011-0x1018 (the 8 digit layouts) are copied into the heap so each digit has its own playable EHF. Caches and returns the pointer, or 0. |
| `0x00001658` | `int ui_password_update(void)` | Library update: dispatches on the state 0x00016430: 0 loading (shop_password_load_resources; then fade-in, track 4, sound 0x7a73, overlay off, state 1), 1 intro (shop_password_run_intro), 2 keypad input (0x00001d28), 3 code check (shop_password_check_code), 4 result (shop_password_show_result), 5 and 6 further message states (0x00002d4c, 0x000030c0); when 4-6 report the end, fades out, stops the music and goes to 7; 7 waits for the fade; 8 shutdown (shop_password_shutdown). |
| `0x000019ec` | `void shop_password_run_intro(void)` | State 1: sub-step 0 copies strTbl.bin (resource 0x1020) string 1 into the message buffer 0x0001656c, counts its characters and seeds the LCG with 3; sub-step 1 types the message one character every 2 frames while flashing random keys (0x000033d4(system_lcg_rand() % 12, 2)); when finished or skipped with confirm/cancel (pad +4 & 0x6000) shows all text, resets the digits, highlights the key under the cursor (shop_password_get_key_code), stops sound 0x7a73 and goes to state 2. |
| `0x00001d28` | `void shop_password_handle_keypad(void)` | State 2 (keypad input). |
| `0x000023f0` | `void shop_password_check_code(void)` | State 3 of the password screen, stepped by sub-state 0x00016432 with the frame counter 0x0001756e: sub-state 0 waits 0x1e frames, copies dictionary word 0xc of resource 0x1020 to the message buffer 0x0001656c, plays sound 0x7a78 and goes to sub-state 1; sub-state 1 reveals the message one character every 2 frames (a press of buttons 0x6000 shows it at once); sub-states 2-9 start one digit animation every 0x14 frames (shop_password_set_digit_anim); sub-state 10 stops sound 0x7a78, converts the 8 entered digits (0x00016437) into a number kept in 0x00016440 and looks it up with card_db_find_by_passcode. |
| `0x00002780` | `int shop_password_show_result(void)` | State 4 (read from its key lines; medium): shows the found card (dissolve-in) with a message containing its name (card_db_get_name, ruby stripped), sets the card's save flag bit 0 (save_set_card_flag_bit0: the card becomes known/owned for the card-list picker), shows strTbl string 4 and asks whether to enter another code; continuing resets the entry and returns to state 1. |
| `0x00002d4c` | `int shop_password_run_wrong_code(void)` | State 5 (code refused) by sub-step 0x00016432 with frame counter 0x0001756e: 0 waits 30 frames, formats strTbl.bin (resource 0x1020) word 10 with the value 0x00016440 (system_swprintf) into message 1 (0x0001656c), counts its visible characters (0x00016444) and starts typing (bit 1 of 0x00017570); 1 types it one character every 2 frames, then copies word 11 into message 2 (0x00016d6c), plays sound 0x7a7a and goes to 2; 2 types message 2 (skippable with pad 0x6000), then 3; 3 waits: cancel returns 1 (leave the screen), confirm goes to 4; 4 waits 30 frames, then clears the counts and message 1 (0x800 bytes), resets the entry (shop_password_reset_entry) and returns to state 1. |
| `0x000030c0` | `int shop_password_run_quit_prompt(void)` | State 6 (entered with cancel from the keypad): 0 waits 30 frames, copies strTbl.bin (resource 0x1020) word 9 into message 1 (0x0001656c), counts it and starts typing; 1 types one character every 2 frames (pad 0x6000 shows it at once), then 2; 2 waits: confirm returns 1 (leave the screen), cancel goes to 3; 3 waits 30 frames, clears the typed count and message 1, refreshes the digit displays (shop_password_update_digit_anims) and returns to state 1. |
| `0x000033d4` | `void shop_password_play_key_anim(uint key, short mode)` | Sets the play range of the keypad EHF (resource 0x1010) for key: each key owns 0x1e frames starting at key x 0x1e (keys 10 and 11 use the block 0x5a frames later when 8 digits are entered). |
| `0x00003688` | `void shop_password_move_cursor_to_key(uint key)` | Puts the keypad cursor on key: 10 -> column 0 row 1, 0 -> column 1 row 1, 11 -> column 2 row 1, 12 -> row 0 (column kept), digits 1-9 -> column (key - 1) % 3, row (key - 1) / 3 + 2 (column in the high nibble of 0x00016434, row in the low nibble of 0x00016435), then plays that key's animation in the current press mode (low nibble of 0x00016434). |

## Purpose and flow

`rel_password` (`libpassword_rel`, id 0x1a) is the card password (passcode) screen. Exports `ui_password_start` (0x300000-byte heap at 0x00017580, track 0x2ce), `ui_password_update` (returns 1 when finished), `ui_password_draw`. Callers: `rel_story` and `rel_labo`. It loads one archive, `labo/password.ehp` (root 3), with 0x11 resource records at 0x000082c8 (16 bytes: u16 id, cached pointer, member-name format with the language letter). The 8 digit layouts 0x1011-0x1018 are copied into the heap so each digit animates independently.

States (`0x00016430`, sub-step `0x00016432`): 0 loading (reader 0xe000-byte buffer, archive, `ui_card_view_open`), 1 intro (typewriter string 1, random key flashes), 2 keypad input (cursor column in the high nibble and row in the low nibble of 0x00016434/0x00016435; up to 8 digits at 0x00016437, count in the low nibble of 0x00016436), 3 check, 4 found card, 5 wrong code, 6 another message state, 7 fade, 8 shutdown.

## Passcode check

`shop_password_check_code` builds the number from the 8 digits and calls `card_db_find_by_passcode`. A result that is not a valid card or that is in the 9-entry sorted exclusion list at 0x000083f8 (`shop_password_is_excluded_card`) is refused (state 5). Otherwise the card image is requested and state 4 shows it; `shop_password_show_result` sets the card's save flag bit 0 (`save_set_card_flag_bit0`). Bit 0 is the flag that `rel_select_card` mode 0 uses to list owned cards (`save_test_card_flag_bit0`), so entering a password registers the card in that list (hypothesis, medium: the exact game meaning of bit 0, "seen" or "obtainable", is not settled here).

Keypad codes (`shop_password_get_key_code`): rows 2-4 are digits 1-9, row 1 is {10, 0, 11}, row 0 is 12 (the special keys' meaning, for example delete and OK, is not confirmed).

## Open questions

- The 9 excluded card ids at 0x000083f8 (read them from the binary; they are not content to dump, ids only).
- The handlers of states 2, 5 and 6 (`0x00001d28`, `0x00002d4c`, `0x000030c0`) and the key animation helpers (`0x000033d4`-`0x00003688`) were not read in full.
- Meaning of save card flag bit 0 versus the card count.
## Keypad (state 2, shop_password_handle_keypad)
- Cursor bytes: 0x00016434 high nibble = column (0-2), low nibble = 1 while a key press animation runs; 0x00016435 low nibble = row (0 = OK key, 1 = {clear 10, digit 0, delete 11}, 2-4 = digits 1-9). Digits at 0x00016437 (8 bytes), count in the low nibble of 0x00016436.
- Buttons: confirm presses the key, cancel opens the quit prompt (state 6), Square deletes the last digit, D-pad moves (rows 1-4 while digits < 8; with 8 digits only the OK row and the clear/delete keys are reachable). Sounds: digit 0x7a74, clear 0x7a75, delete 0x7a76, OK 0x7a77.
- Keypad EHF (resource 0x1010): 0x1e frames per key code starting at key x 0x1e; modes 0 highlight (+1..+0x10), 1 press (+0x10..+0x1e), 2 single flash frame, 3 plain. Keys 10 and 11 use a second block 0x5a frames later when the entry is full.
- Digit EHFs 0x1011-0x1018: frame = digit 0-9, 10 blank, 0xc-0x10 cursor mark, 0x10-0x33 a longer animation (value 0xd, used by the code check).

## States 5 and 6
- State 5 (code refused): strTbl word 10 formatted with the value at 0x00016440 (hypothesis: the entered number), then word 11 with sound 0x7a7a; cancel leaves the screen, confirm returns to state 1.
- State 6 (quit prompt, from cancel on the keypad): strTbl word 9; confirm leaves, cancel returns to state 1.
- Message buffers: 0x0001656c (message 1, typed count 0x00016448), 0x00016d6c (message 2, count 0x0001644a), visible-character total 0x00016444, frame counter 0x0001756e, typing flag bit 1 of 0x00017570.

## Corrections
- The earlier note says `shop_password_reset_entry` puts the cursor on row 3. The cursor is actually placed by `shop_password_move_cursor_to_key(0)`: column 1, row 1 (the 0 key) (high).
