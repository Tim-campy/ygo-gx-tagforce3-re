# `rel_umd_replace`

Module document of the 2026-11-04 round 6 (all game modules imported; `../modules.md`). English, evidence-based: the sections below come from reading every function of the module in the Ghidra decompilation; hypotheses carry a confidence.

| | |
| --- | --- |
| File | `PSP_GAME/USRDIR/gmodule/rel_umd_replace.prx`, 43,356 bytes, plain ELF (relocatable PRX) |
| Slot | scene 0x1b, id 0x2e |
| Exports → importers | — |
| Role (catalogue) | UMD swap: `sceUmdUser` (8 functions), `IoFileMgrForUser`, `database/umd_replace/`. |
| Runtime base | unknown; imported at image base 0x0, so addresses are module offsets |
| Registry ids | `rel_umd_replace:0x…` |
| Functions | 74 own functions, 74 documented in this round (system 74); tables in `../functions/<group>.md`, section `rel_umd_replace` |

## Key functions (largest)

| Address | Prototype | Summary (first sentence) |
| --- | --- | --- |
| `0x000004b0` | `void system_umd_replace_popup_open_reward(int card_id, int count)` | Opens the single-card reward popup: popup state 3, slot 0 identity matrix, rotation timer 0x00008bd4 = 0, card id 0x00008a20 = card_id; formats dictionary word 6 with system_swprintf into 0x00008c9c using card_db_get_name(card_id) and count (name first when save_get_language() is 0, count first otherwise), opens the message window and runs one reward update. |
| `0x000006ec` | `void system_umd_replace_popup_update_reward(void)` | Reward popup update: builds slot 0's matrix from the field_3d camera matrix (+0x80) and position (+0x10..+0x18), a fixed offset (-0.5 and 0x000085ac) and a Y rotation of 0x000085a8 * timer / 15 (sceVfpuMatrix4Mul, sceVfpuMatrix4RotY), copies it with system_matrix4_copy. |
| `0x00000a8c` | `int system_umd_replace_render_card_texture(void **list_ptr, int unused, int part)` | Card model texture hook: for part 0 or 1 renders into a 128 x 256 off-screen target at VRAM offset 0x160000 (psm 3) either the card back (ui_draw_card_blank, part 0) or the face of card 0x00008a20 (ui_draw_card_face, part 1, when non-zero), rebinds the back buffer and sets that VRAM area as the texture with wrap, offset and scale; stores the advanced list in *list_ptr and returns 1. |
| `0x00000d5c` | `void system_umd_replace_open_list_window(void *win, void *text, int kind, uchar default_item, int cancel_allowed)` | Clears and fills a 0x120-byte list-window record: text at +0x84, width 0x1c2 at +0x64, kind in the low nibble of +0xca (style byte +0xd4 = 3 for kind 3, 4 for kind 2, 0 otherwise), default item in +0xd3, flag bit 2 of +0xc8 from cancel_allowed, module heap at +0xc4; opens it with ui_open_list_window, centres it on screen and plays sound 0x7a0c. |
| `0x00001138` | `bool system_umd_replace_update(void)` | Main state machine on 0x00008ea0: 0 waits for the card reader, 1 requests the resources, 2 waits, 3/4 start and run the disc swap, 5/6 start and run a reinsertion swap, 7 grants rewards, 8/9 show three face-down cards, 10/0xb show the already-used message, 0xc/0xd show each reward, 0xe/0xf ask whether to continue, 0x10 waits for the message window to close, 0x11 waits for the fade, tears the module down and stops the BGM (audio_stop_sounds_bgm_arg(600)). |
| `0x000012b8` | `void system_umd_replace_draw(void)` | Frame draw: 3D setup on layer 0; on layer 1 advances and draws the ehf animation 0x000092a0 (params 0x000092b0) and, when 0x00009380 is set, the second one 0x00009310 (params 0x00009320); draws the card popup in main states 9 and 0x0d or the swap windows in state 4; then on layer 4 the list window 0x000090b8, the window list 0x000091d8 and the fade. |
| `0x00001428` | `void * system_umd_replace_setup_3d(void *list)` | Writes the 3D frame setup: offset (0x710, 0x778), 480 x 272 viewport and scissor (scissor test on), depth range, blend function written but blending left disabled (state 4), alpha test, depth test (func 7), culling, texturing and clip planes on, fog parameters 50-100 colour 0x404040 written but fog left disabled (state 7), black colour, depth and stencil clear (flags 0x17), perspective (0x000085fc, 0x000085f8, 5, 400), linear texture filter, white ambient, lighting with light 0 off, camera look-at from the vectors at 0x00008630 (eye), 0x00008640 (target) and 0x00008650 (up), identity model matrix. |
| `0x000016d0` | `void system_umd_replace_open_message(void *text)` | Fills the 0x78-byte window descriptor 0x00009224 (id 1, width 0x1c2, style bytes) with text, adds it to window list 0x000091d8, centres it, opens it and plays sound 0x7a0c. |
| `0x000017ec` | `int system_umd_replace_pick_random_card(void *sector)` | Seeds system_srand with 1 + the sum of the 10 id bytes at sector+0x373 + the sum of N bytes from sector+0x8c, N being the word at sector+0x84 clamped to 0x40..0x774; then draws card ids (rand >> 2) % 0x10b3 + 0xe88 until one is card_db_is_valid, not a token and not one of 0x1388, 0xecb, 0x1386, 0xeb3, 0x1387, 0xece, 0xea8, 0xecd, 0x1b4d. |
| `0x00001cbc` | `void system_umd_replace_grant_rewards(void)` | Main state 7, by disc kind 0x00008ea8: kind 2 (when save_test_progress_flag_e9_bit7 is clear) queues cards 0x1388, 0xecb, 0x12fd, plus the bonus set when flag ea bit0 is already set, adds 10000 DP and sets flag e9 bit7; kind 1 (when flag ea bit0 is clear) queues 0x1386, 0xeb3, 0x1cb5, the bonus set when e9 bit7 is set, adds 10000 DP and sets ea bit0; both go to state 8. |
| `0x00002668` | `int system_umd_replace_swap_update(void)` | Swap state machine on 0x00009390. |
| `0x00002ae8` | `int system_umd_replace_wait_medium(int *status)` | Loops one frame at a time: sceUmdCheckMedium, sceUmdGetDriveStat; the button of system_get_confirm_button(1) sets status 1 and returns 0; while system_get_power_flags() has none of bits 0x800b0000: no medium for 300 frames sets status 4 and returns 0, drive state bit 0x20 (ready) sets status 0 and returns 1, drive state 10 for 300 frames sets status 2 and returns 0. |
| `0x00002c1c` | `int system_umd_replace_identify_disc(int *status)` | Opens umd1: (block device) with system_umd_replace_open_when_ready, seeks (sceIoLseek, offset arguments hidden by the decompiler), reads one sector into 0x00009590 with system_umd_replace_read_when_ready and closes; copies the 10 bytes at 0x00009903 (sector +0x373) and compares them: ULES-01183 gives kind 0, ULJM-05260/ULUS-10302/ULES-00925 kind 1, ULJM-05151/ULUS-10136/ULES-00600 kind 2, anything else kind 3, stored in 0x00009394. |
| `0x00002dec` | `int system_umd_replace_open_when_ready(void *path, int flags, int mode, int *status)` | Waits frame by frame for a ready disc (cancel button: status 1; no medium: status 4), checks sceUmdGetDiscInfo for the game-disc type bit 0x10 (else status 2), then calls sceIoOpen(path, flags, mode), repeating the whole wait while it fails; on success status 0. |
| `0x00002f44` | `int system_umd_replace_read_when_ready(int fd, void *buffer, int size, int *status)` | Same wait loop as system_umd_replace_open_when_ready, then sceIoRead(fd, buffer, size) repeated until it succeeds; status 0 on success. |

## Purpose and flow
Scene 0x1b. Despite the name, this is the "insert another UMD" bonus: the player swaps in a disc of an earlier release, the module reads that disc's identifier and grants cards, DP and unlock flags, then asks for the original disc back.

- Entry `system_umd_replace_module_start` registers `system_umd_replace_scene_main` (0x00000038) and the empty end callback 0x000000dc. Frame callbacks: `system_scene_set_frame_callback(0, system_umd_replace_frame_callback, 0x0000017c)` (0x0000017c is outside the exported packs).
- Init (`system_umd_replace_init`): render state, field_3d allocator (module heap), `audio_release_all_banks` + track 0x2c8, card reader, popup, window list 0x000091d8, UMD callbacks (`system_umd_replace_swap_init`: `sceKernelCreateCallback`, `sceUmdRegisterUMDCallBack`, `sceUmdActivate(1, "disc0:")`, `sceImposeSetUMDPopup(0)` to hide the system "UMD changed" popup).
- Main state machine `system_umd_replace_update` (0x00001138) on 0x00008ea0:

| State | Handler | Next |
| --- | --- | --- |
| 0 | wait for the cardh cip reader | 1 |
| 1 | request resource 0 | 2 (callback sets 3) |
| 3 | swap mode 0, message word 8, BGM 4 | 4 |
| 4 | run swap: 7 done, 8 aborted, 2 close message | 7 / 3 / 0x10→4 |
| 5 | message word 7, swap mode 1 (unreachable: no code sets state 5, directly or through the next-state word, whose values are 4, 7 and 0xe; so `system_umd_replace_start_reinsert` and `system_umd_replace_run_reinsert` are dead) | 6 |
| 6 | run swap | 0x10→7 or 0xe / 3 |
| 7 | grant rewards by disc kind | 8, 0xc, 0xe, 10 |
| 8, 9 | popup with three face-down cards | 3 |
| 10, 0xb | list window word 1 (disc already used) | 3 |
| 0xc, 0xd | reward popup per entry, `save_change_card_count` | next entry or 0xe |
| 0xe, 0xf | list window word 2 (button style 3, buttons 2 and 3): 3/-2 restart, 2 leave | 3 / 0x11 |
| 0x10 | wait for the message window to close | saved state 0x00008ea4 |
| 0x11 | wait for the fade, teardown, BGM stop | end |

- Swap state machine `system_umd_replace_swap_update` (0x00002668) on 0x00009390: 1 prompt, 2, 3 wait for a medium (`sceUmdCheckMedium`, `sceUmdGetDriveStat` bit 0x20 ready, 300-frame timeouts, power flags 0x800b0000 suspend counting), 4 identify, 5 wrong-disc yes/no (word 9), 6 error message (word 5 no disc, word 10 drive error), 7 done, 8 aborted. When done with this game's own disc (kind 0), `sceUmdReplaceProhibit` is called until it succeeds (re-locks the drive).

## Disc identification
`system_umd_replace_identify_disc` opens `umd1:` with `sceIoOpen` after `sceUmdGetDiscInfo` reports the game-disc type bit 0x10, seeks (arguments hidden by the decompiler; probably sector 16, the ISO 9660 primary volume descriptor, hypothesis medium) and reads one sector into 0x00009590. The 10 bytes at sector +0x373 (the application-use field of the PVD, which holds the PSP disc id, hypothesis medium) are compared with product ids:
- kind 0: ULES-01183 (this game, European release);
- kind 1: ULJM-05260, ULUS-10302, ULES-00925;
- kind 2: ULJM-05151, ULUS-10136, ULES-00600;
- kind 3: any other disc.
Kinds 1 and 2 are the ids of the two earlier releases of the series (from public product catalogues; confidence high). The Japanese id of this game is not in the list (the usb_connect module uses ULJM05373 for this game), consistent with this being the European build.

## Rewards
Reward list: u16 entries at 0x00008eb0 (bits 0-2 count, bits 3-15 card id), count 0x000090b0, display index 0x000090b4.
- Kind 2, first time: cards 0x1388, 0xecb, 0x12fd (count 1 each), +10000 DP, sets progress flag e9 bit 7.
- Kind 1, first time: cards 0x1386, 0xeb3, 0x1cb5, +10000 DP, sets progress flag ea bit 0.
- Both flags set (on whichever comes second): bonus cards 0x1387, 0xece, 0x1102.
- Any other disc, or an earlier release already claimed: one random card with count 3, once per disc (the 10-byte disc id is checked and pushed with `system_find_recent_code`/`system_push_recent_code`). The random generator is seeded from the disc's own sector (sum of the id bytes and of N bytes from +0x8c, N = word at +0x84 clamped to 0x40..0x774); cards are drawn from 0xe88..0x1f3a, must be valid, non-token and not one of the reward cards (exclusions 0x1388, 0xecb, 0x1386, 0xeb3, 0x1387, 0xece, 0xea8, 0xecd, 0x1b4d); fallback 0x1366. So the same foreign disc always gives the same card.
- Character flags (bit 1, `save_set_character_flag_bit1`): ea → (6,1), (8,1); e9 → (6,2), (6,3), (8,0); both → (0x18,0), (0x1a,0). These look like partner/opponent unlocks (hypothesis, medium). The gallery reads the same e9/ea flags to unlock its items 0-23.

## Key structures
- 0x00008950 (0x550 bytes) card popup: state, model instance 0x00008954, slots of 0xd0 bytes from 0x00008960 (+0x80 matrix, +0xb4 its Y translation, element 13: face-down cards start at Y = slot * 5 + 10 and fall 0.25 per frame until the last one reaches -10; +0xc0 card id), count 0x00008bd0, rotation timer 0x00008bd4, window list 0x00008bd8, message window 0x00008c24, text buffer 0x00008c9c.
- 0x00008ea0 (0x4f0 bytes) main block: state, next state +4, disc kind +8, rewards +0x10, list window 0x000090b8 (0x120-byte record), window list 0x000091d8, message window 0x00009224, ehf animations 0x000092a0/0x00009310 with params 0x000092b0/0x00009320, flag 0x00009380.
- 0x00009390 (500 bytes) swap block: state, kind 0x00009394, mode 0x00009398, callback id 0x0000939c, list window 0x000093a0, window list 0x000094c0, message window 0x0000950c, sector buffer 0x00009590 (id at 0x00009903).
- Module heap: 0x180000 bytes at 0x0000e590 (`system_umd_replace_heap_alloc` / `_free` are tail jumps to `system_heap_alloc` / `system_heap_free`, the latter returning 1); cardh cip reader buffer 0x100000 bytes at 0x0018e590; globals 0x0028e5b4 heap, 0x0028e5b8 reader; resource table 0x0028e590 (0x24-byte entries {name[0x20], data}), pending index/callback/arg 0x0028e5bc..0x0028e5c4.

## Files loaded
- `database/umd_replace/%s`, root 3; file 0 is the language EHP named by the 0x20-byte table at 0x000086c8 (first entry `basic_lang_jpn.ehp`) indexed by `save_get_language()`.
- Members (table 0x00008788, 0x24-byte entries {char name[0x20], int file_index}): 0 `strTbl.bin` (dictionary words 1, 2, 3, 5, 6, 7, 8, 9, 10 used for messages), 1 card model (TMS for `field_3d_create_model_instance`), 2-6 card viewer resources, 7/9 ehf animations with 8/10 their tmf flag tables. Names ending in the 3-character suffix at 0x00008914 are bound as nested EHPs.
- Card art: `card_db_open_cardh_cip` + `card_db_cip_get_image(reader, card, save_get_card_value_bits4_6(card))` (the artwork variant comes from the save).

## Sony library use (what the game passes)
`sceUmdActivate(1, "disc0:")`, `sceUmdRegisterUMDCallBack`/`UnRegister`, `sceUmdCheckMedium`, `sceUmdGetDriveStat` (bit 0x20 ready, value 10 counted as error), `sceUmdGetDiscInfo` (8-byte struct, type bit 0x10), `sceUmdReplaceProhibit` (retried each frame until >= 0), `sceImposeSetUMDPopup(0/1)`, `sceIoOpen("umd1:", 1, 0)`, `sceIoLseek`, `sceIoRead(fd, 0x00009590, 1)` (one sector on the block device), `sceIoClose`, `sceKernelCreateCallback`/`DeleteCallback`.

## Name mismatches
- Twin lines rejected: 0x00000150 (`ui_duel_draw_frame_if_active`), 0x000005d0 (`ui_is_lp_panel_open`), 0x00003400 (`audio_heap_free`; it allocates), 0x00000000 (`shop_module_start`; same code, own callbacks). 0x00003410 has the shape of `audio_heap_free` but frees from the module heap, named `system_umd_replace_heap_free`.
- Twin accepted: 0x000008f4 = `system_matrix4_copy`.

## Open questions
- `sceIoLseek` offset (hidden register arguments); confirm sector 16 in PPSSPP.
- The leave callback 0x0000017c is not a defined function in the packs (at most 8 bytes before 0x00000184, probably an empty stub); check in Ghidra. Note that the module teardown runs from state 0x11, not from the leave callback.
- The 3-character suffix at 0x00008914 and the member names 1-10 (read the data section).
- Meaning of the character flags set at the end of state 7.
- 0x0000327c (start of every update) and 0x00002660 (swap result 8, swap teardown) are empty hooks.
