# `rel_conv_machine`

Module document of the 2026-11-04 round 6 (all game modules imported; `../modules.md`). English, evidence-based: the sections below come from reading every function of the module in the Ghidra decompilation; hypotheses carry a confidence.

| | |
| --- | --- |
| File | `PSP_GAME/USRDIR/gmodule/rel_conv_machine.prx`, 63,400 bytes, plain ELF (relocatable PRX) |
| Slot | id 0x0e |
| Exports → importers | `libconv_machine_rel` (3) → labo, story |
| Role (catalogue) | Card conversion machine: `labo/conv_machine.ehp`. Uses `select_card`. |
| Runtime base | unknown; imported at image base 0x0, so addresses are module offsets |
| Registry ids | `rel_conv_machine:0x…` |
| Functions | 52 own functions, 52 documented in this round (shop 43, ui 5, system 2, field_3d 1, deck 1); tables in `../functions/<group>.md`, section `rel_conv_machine` |

## Key functions (largest)

| Address | Prototype | Summary (first sentence) |
| --- | --- | --- |
| `0x0000004c` | `void shop_conv_machine_run_intro(void)` | Scene state 1 by sub-step 0x00078c22: 0 copies strTbl.bin (resource 0x1030) string 7 into the message buffer 0x00078d02, counts its visible characters (0x00078cfe) and seeds the LCG with 0; 1 after the fade starts the typewriter (flag 0x00079102 bit 0) and sound 0x7a72; 2 and 3 show random counter frames (system_lcg_rand % 100) while the text types, then after 25 frames switch to string 6, rewind slot 1, stop 0x7a72 and play 0x7a64 once; 4 types it; 5 waits for confirm or cancel (pad +4 & 0x6000) and goes to scene state 2. |
| `0x00000458` | `void shop_conv_machine_select_cards(void)` | Scene state 2: fades out, then opens the card picker in mode 1 (ui_select_card_open(1, {heap 0x00079104, reader 0x00079108, archive 1, archive 2}, &count 0x00078c28, ids 0x00078c2c), flag 0x00079114 bit 0 so the draw entry delegates to ui_select_card_draw) and updates it until it returns 1; after the fade-in, with fewer than 10 cards shows strTbl string 3 and goes to state 7 (ask again); with 10 or more removes every chosen card from the collection (save_change_card_count(id, 0), once per id entry), clears the 2000-byte card record area 0x00079118 and goes to state 3. |
| `0x00000708` | `void shop_conv_machine_feed_cards(void)` | Scene state 3 (feeding animation): 0 initialises one 0x14-byte record per chosen card at 0x00079118 (+0 x 0, +4 y = step x i + 250.0, +8 20.0, +0xc state 1, +0x10 timer -4 - 3i); 1 moves every record in state 1 for 22 frames (random sound 0x7a65-0x7a68 at its start), then marks it 2; when the last is done rewinds slot 0, sets the machine flag (0x00079114 bits 1-2 = 2) and plays 0x7a6a; 2 waits for that flag to clear; 3 counts the counter animation up to the number of cards (shop_conv_machine_set_counter_anim) and goes to state 4. |
| `0x0000099c` | `void shop_conv_machine_run_conversion(void)` | Scene state 4 (machine animation) by sub-step: types strTbl string 4, starts the layer animations (shop_conv_machine_set_layer_speed) and sound 0x7a6b, swirls the card records in on a shrinking circle (sceVfpuScalarCos/Sin), runs the machine for 0x150 frames, picks the result (shop_conv_machine_pick_result(count)) into 0x00078cf4, fades a flash (0x00078cf6/0x00078cf7), plays 0x7a6e, 0x7a70 and 0x7a71 while the result card model moves out (0x000798e8-0x000798fc), and ends in scene state 5 with the name slide position 0x00078cfa = 0x1e0. |
| `0x00001380` | `void shop_conv_machine_show_result(void)` | Scene state 5: 0 fades the result banner in (0x00079900) and measures the card name (scale fitted to 480 px); 1 slides the name in over 16 frames (0x00078cfa); 2 waits: Triangle (0x1000) fades out and opens the card viewer for the result card (ui_card_viewer_open with resources 0x800c, 0x8012, pack source 0x8015, artwork select; sub-steps 10-12, then back to 2), confirm or cancel adds the card to the collection (save_change_card_count(result, 1)) and goes to 3; 3 slides the result card away, then shows strTbl string 3 and goes to scene state 7 (ask again). |
| `0x00001828` | `void shop_conv_machine_ask_again(void)` | Scene states 6 and 7: sub-step 0 types the message; 1 waits for an answer: in state 7 confirm restarts at scene state 1 and cancel ends, in state 6 the buttons are swapped; ending fades out to black, stops the music (audio_stop_sounds_bgm_arg(600)) and sets scene state 8. |
| `0x00001cc8` | `void ui_conv_machine_draw(void)` | Library draw entry of the card conversion machine. |
| `0x00002438` | `void * shop_conv_machine_draw_message(void *list)` | Draws the machine's message: opens the font list on list, colour 0xff363a21, scale 0xe, and types the UTF-16 buffer 0x00078d02 into the box (0x25, 0x1d, 0x11c, 0x1e) px showing at most the u16 count 0x00078d00 characters (shop_conv_machine_draw_typed_text_px). |
| `0x00002648` | `void * shop_conv_machine_draw_conversion_fx(void *list)` | Draws the 2D effects of the conversion (scene state 0x00078c20 = 4). |
| `0x00002cf4` | `void * shop_conv_machine_draw_layer4_faded(void *list, uchar alpha)` | Draws EHF layer slot 4 with a global alpha: alpha 0 draws nothing; 0xff draws the slot directly (shop_conv_machine_draw_layer_slot(list, 4)); other values render it off screen (render target VRAM +0x174000, 512 x 512, psm 3, first cleared with an opaque black 0x1e0 x 0x110 quad), bind the back buffer again and draw that buffer as one textured 0x1e0 x 0x110 sprite with ambient colour alpha << 24 \| 0xffffff, so the whole layer fades as one image. |
| `0x00003140` | `void shop_conv_machine_init_3d(void)` | Prepares the 3D scene: field_3d_init_render_state on layer 0, field_3d_set_allocator(shop_conv_machine_heap_alloc, shop_conv_machine_heap_free), two light records 0x0000bb90 / 0x0000bbcc (0x3c bytes: ambient 0xff000000, diffuse white / 0xff404040), lighting on, perspective (near 30.0, far 300.0) and identity view and model matrices, then commits the layer. |
| `0x00003560` | `void shop_conv_machine_begin_3d_frame(void)` | On layer 2 installs lights 0 and 1 (field_3d_set_light with 0x0000bb90 / 0x0000bbcc), enables lighting and both lights with a black ambient, commits, sets camera 0 (shop_conv_machine_set_camera) and resets the model matrix. |
| `0x00003738` | `void shop_conv_machine_draw_machine(void)` | Animates and draws the machine model 0x1020 (shop_conv_machine_get_model) on layer 2 with lighting and camera 1 (shop_conv_machine_set_camera). |
| `0x00003f34` | `int shop_conv_machine_load_resources(void)` | Stepped loader (bits 1-7 of 0x0000bc10, waiting while bit 0 is clear): 0 opens the card-image reader (card_db_open_cardh_cip on the 0x6d000-byte buffer 0x0000bc14, stored in 0x00079108) and starts archive 2; 1 starts archive 1; 2 waits for card_db_cip_is_ready; 3 loads module 0x1d (rel_select_card, system_module_load); 4 waits for system_module_all_loaded and records 0x1d in 0x00079110; 5 runs shop_conv_machine_init_scene and returns 1. |
| `0x00004224` | `void * shop_conv_machine_get_resource(uint id)` | Resource lookup: ids with bit 15 search the 0x29 12-byte records at 0x0000b740 (archive 1; member-name format with the language letter, a fixed letter for 0x8036/0x8037), ids with bit 12 the 12 16-byte records at 0x0000ba44 (archive 2, e.g. |

## Purpose and flow

`rel_conv_machine` (`libconv_machine_rel`, id 0x0e) is the card conversion machine: the player feeds 10 or more cards and receives one random card. Exports: `ui_conv_machine_start` (0x600000-byte heap at 0x00079910, 3D scene, resource tables, track 0x2ce), `ui_conv_machine_update` (returns 1 when finished), `ui_conv_machine_draw` (delegates to `ui_select_card_draw` while the picker runs, flag 0x00079114 bit 0). Callers: `rel_story` and `rel_labo`.

Scene states (`0x00078c20`, sub-step `0x00078c22`, frame timer `0x0007910c`):

| State | Handler | What happens |
| --- | --- | --- |
| 0 | `shop_conv_machine_load_resources` | cardh CIP reader (0x6d000-byte buffer), archives 1 and 2, `system_module_load(0x1d)` (`rel_select_card`), then fade-in and track 4. |
| 1 | `shop_conv_machine_run_intro` | Typewriter messages (strTbl strings 7, 6), random counter frames; confirm continues. |
| 2 | `shop_conv_machine_select_cards` | `ui_select_card_open(1, {heap, reader, archive 1, archive 2}, &count, ids)`. Fewer than 10 cards: message 3 and state 7. Otherwise every chosen card is removed with `save_change_card_count(id, 0)`. |
| 3 | `shop_conv_machine_feed_cards` | 0x14-byte records per card at 0x00079118 (position x/y/z floats, state, timer) fly into the machine; counter counts up. |
| 4 | `shop_conv_machine_run_conversion` | Machine animation (EHF slot table 0x0000b2e4), swirl, flash; result = `shop_conv_machine_pick_result(count)`. Confirm skips. |
| 5 | `shop_conv_machine_show_result` | Result model with the card face rendered off screen (`shop_conv_machine_render_card_face`), name slide-in; confirm adds the card (`save_change_card_count(id, 1)`), Triangle opens the card viewer. |
| 6/7 | `shop_conv_machine_ask_again` | Yes restarts at state 1, no fades out. |
| 8/9 | fade, `shop_conv_machine_shutdown` | Release track, close card view, stop reader, unload module 0x1d, free heap. |

## Result pools (data the port needs)

`shop_conv_machine_pick_result(count)` reads the 8-byte record `0x0000b014 + (count - 10) x 8` = `{u32 pointer to a u16 card-id list, u32 length}` and returns a uniformly random id of that list (`system_rand_shifted() % length`). The pools therefore depend only on how many cards were fed (10 and up; the upper bound is the picker's 99-copy limit, the record count was not read). These are the "46 runs of card ids" that `docs/formats/` mentions for `rel_conv_machine.prx` (hypothesis, high: the pointers point into the module's data). Which cards were fed does not matter, only their number (medium: no other input reaches the pick).

## Resources

Archive records at `0x0000b488` (2 x 12 bytes, paths with the language letter, root 3); resource tables 0x0000b740 (0x29 x 12 bytes, ids 0x8xxx, archive 1, the deck-editor UI set), 0x0000ba44 (12 x 16 bytes, ids 0x1xxx, archive 2) and 0x0000bb44 (2 x 20-byte 3D model records {id, instance, TMS, TMT, TMA member names}; models 0x1020 machine, 0x1021 card). Cameras: 0x30-byte records at 0x0000b380.

## Name mismatches

None (exports keep their names).

## Open questions

- Number of pool records at 0x0000b014 and the maximum card count accepted.
- Archive 1/2 file names (likely `labo/conv_machine.ehp` and the common UI set).
- Whether `save_change_card_count(id, 0)` decrements by one (the picker writes one id per copy, so it is called once per copy; hypothesis, medium).
## Draw order (ui_conv_machine_draw)
Flag byte 0x00079114: bit 0 card picker active (only `ui_select_card_draw`), bits 1-2 machine animation direction (2 forward, 1 backward, 0 hold), bit 3 set when the backward play reached frame 0, bit 4 card viewer open. Layer 0 clear; layer 1: conversion effects, background, EHF layer slots 0-3 and 5, panel, message; layer 2 (3D): machine model 0x1020, then in states 4/5 the dim overlay (alpha byte 0x00079900, drawn on layer 1) and the result card model, in state 3 the fed card models; layer 4: result name at (0x00078cfa, 0xdd) and the hint (bit 2 of 0x00079116) in state 5, then layer slots 6-8; layer 5: fade.

## Effects (shop_conv_machine_draw_conversion_fx)
- Off-screen buffers: VRAM +0x160000 (128 x 256, psm 3) receives a card face (`ui_draw_card_face`) before it is drawn as a texture; VRAM +0x174000 (512 x 512) is used to fade layer slot 4 as one image (alpha byte 0x00079115, fade mode bits 0-1 of 0x00079116: 1 in by +4, 2 out by -8).
- Result flash: 6-vertex triangle strip from the template 0x0000b308 (6 x 16 bytes: x, y in a 108 x 154 frame, u, v), growth byte 0x00078cf7 (full size 78 x 112 px at 0x80; beyond it the strip is deformed), alpha byte 0x00078cf6, centred in the box (0x83, 0x5a, 0xb9, 0x8d).
- Fed cards in record state 3 (the swirl of `shop_conv_machine_run_conversion`, medium) are drawn as growing 2D sprites while their timer +0x10 counts down from 20.
- Message cursor: a solid rectangle in the font colour drawn after the typed text, steady while bit 0 of 0x00079102 is set (typing), else blinking on bit 3 of the frame counter. The password screen uses the same scheme (bit 1 of 0x00017570).
- Module heap pointer: 0x00079104 (allocator callbacks 0x00003b58 / 0x00003b68).
