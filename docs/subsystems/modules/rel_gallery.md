# `rel_gallery`

Module document of the 2026-11-04 round 6 (all game modules imported; `../modules.md`). English, evidence-based: the sections below come from reading every function of the module in the Ghidra decompilation; hypotheses carry a confidence.

| | |
| --- | --- |
| File | `PSP_GAME/USRDIR/gmodule/rel_gallery.prx`, 46,884 bytes, plain ELF (relocatable PRX) |
| Slot | scene 0x1e, id 0x31 |
| Exports → importers | — |
| Role (catalogue) | Gallery: `movie/%s.pmf`, thumbnails, `database/gallery/`, `field/event/<l>/`. |
| Runtime base | unknown; imported at image base 0x0, so addresses are module offsets |
| Registry ids | `rel_gallery:0x…` |
| Functions | 101 own functions, 101 documented in this round (ui 101); tables in `../functions/<group>.md`, section `rel_gallery` |

## Key functions (largest)

| Address | Prototype | Summary (first sentence) |
| --- | --- | --- |
| `0x00000e6c` | `void ui_gallery_grid_setup(void *grid, void *resources, uchar *unlocked)` | Grid method (vtable +0x0c): finds thumbnail1e_gim, thumbnail2e_gim and bg_tf1_gim in resource slot 0 (basic.ehp) and stores them at +0x127c/+0x1280/+0x1284. |
| `0x000010c8` | `void ui_gallery_grid_draw(void *grid)` | Grid method (vtable +0x14): when both thumbnail sheets are loaded, on GE layer 4 sets nearest filtering, alpha blend and white ambient, draws all active thumbnails' frames with the bg_tf1 texture (extent 58 x 34), then each thumbnail (extent 52 x 28) with thumbnail1e or thumbnail2e according to its sheet flag. |
| `0x00001248` | `void ui_gallery_grid_start_enter(void *grid, int page)` | Starts the fly-in of a page's thumbnails to their grid cells (target x = column * 60 + 64, y = row * 32 + 40, 6 columns), picking one of four patterns with (system_rand_shifted() % 400) / 100: 3 = from random x at y 320; 2 = from (224, 320) with a serpentine delay; 1 = alternately from x 480 and x 0 at y 320; 0 = first 16 from x 0, the rest from x 480. |
| `0x000016b0` | `void ui_gallery_grid_animate_page(void *grid, int page, int direction)` | Page animation dispatcher: direction 0 runs ui_gallery_grid_start_enter, 0xffff runs ui_gallery_grid_start_exit; otherwise the current page's thumbnails fly off horizontally (targets x = -direction * 540 + random, y 32..223) and the page (page + 6 + direction) % 6 flies in from x = direction * 540 + random, y 128..255 to its grid cells. |
| `0x00001970` | `void ui_gallery_app_init(void *app)` | Initialises the 0x110-byte app object: loads audio track 0x2c8, clears the state fields (state +0x10 = 0, page +0x18 = 2, cursor and text fields, rectangle 224/320/58/34, lerp 0.25), computes the 0x82 unlock bytes at +0x88 (ui_gallery_compute_unlocks), creates the task manager, allocates and clears the 0xfc-byte resource set (+0x00) and the thumbnail grid (+0x0c), sets +0x16 to 1 when save_get_language() is 0, initialises the 3D render state on layer 0, queues the loads of resource slots 0x3a (language ehp) and 0 (basic.ehp) (ui_gallery_load_slot), plays BGM track 0x1e with fade and starts a fade-out (1, 0, 1). |
| `0x00001b18` | `void ui_gallery_compute_unlocks(void *app)` | Fills the 0x82 unlock bytes at app+0x88: items 0-14 when save_test_progress_flag_e9_bit7, items 15-23 when save_test_progress_flag_ea_bit0, items 24-56 from save_test_picture_seen(bit) with the 33 bit numbers copied from 0x0000953c, item 57 always, item 58 when any character 2..0x8e has an existing variant with save_test_character_flag_bit2, item 59 when character 2 variants 0 and 1 both have that flag, and items 60-129 copied from the save state bytes at +0x153e4 + the index table 0x00008a37.. (one byte per item). |
| `0x00001ed8` | `int ui_gallery_handle_input(void *app)` | Browse-state input: updates the cursor (ui_gallery_update_cursor) and the arrow pulse (+0x74/+0x76, 0x60..0xff), then reads the pad edge word (+0x0c): the button of system_get_confirm_button(1) plays sound 0x7a06 and returns 3 (leave); the confirm button (system_get_confirm_button(0)) plays the buzzer 0x7a07 and returns 0 while the cursor is moving or the item is locked, otherwise stores the item (+0x7a), requests picture slot item + 1 (ui_gallery_load_picture) when item < 0x39 or stores movie index item - 0x39 at +0x78, plays 0x7a05 and returns 1; R (0x200) or square (0x8000) sets direction +0x58 = 1, L (0x100) sets -1, both reset the cursor, play 0x7a0d and return 2; else 0. |
| `0x00002090` | `int ui_gallery_zoom_in_picture(void *app)` | Picture open animation, once the current picture slot is loaded: on the first step (+0x38 == 0) prepares the texture (ui_gallery_prepare_picture, pointer at +0x5c), starts the rectangle +0x3c..+0x48 at the selected cell (52 x 28) with linear filtering (+0x4c = 1). |
| `0x000022b0` | `int ui_gallery_zoom_in_movie(void *app)` | Movie open animation: on the first step clears the texture pointer and starts the rectangle at the selected cell; each step raises the dim alpha +0x54 by 16 and grows the rectangle toward full screen; when done plays movie +0x78 with ui_gallery_play_movie (blocking) and returns 1. |
| `0x00002594` | `int ui_gallery_update(void *app)` | Gallery state machine (state word +0x10), run every frame after updating tasks and the grid: 0 shows the black screen and goes to 1; 1 waits until no load is pending, sets up the grid, finds the GIMs thumbnail1e/thumbnail2e/side/hilight/bg_tf1 in basic.ehp (+0x60..+0x70), creates the looping background task, starts a 16-frame fade-in and goes to 3; 3 after the fade sets the texts, starts the page fly-in, goes to 10; 10 browse (ui_gallery_handle_input: 1 to 0x0b for pictures or 0x0e for movies with audio_stop_sound(0x1e, 500), 2 to 0x10, 3 to 0x11); 0x0b zoom in picture then 0x0c; 0x0c waits for circle/cross then 0x0d; 0x0d fades the picture back to 10; 0x0e plays the movie then 0x0f (restarts BGM 0x1e); 0x0f to 10; 0x10 page change to 10; 0x11 starts a 30-frame black fade-out, stops BGM, flies the grid out and centres the cursor, goes to 0x12; 0x12 returns 1 when the fade is done. |
| `0x00002b48` | `void ui_gallery_update_cursor(void *app)` | Cursor update. |
| `0x00003488` | `void ui_gallery_draw_side_panels(void *app)` | Draws the side GIM (+0x68) as two 64 x 256 panels at (0, 16) and (0x1a0, 16); when the arrows flag +0x15 is set also draws two 16 x 16 arrow sprites from thumbnail1e (+0x60) at (0x28, 0x8c) and (0x1a8, 0x8c) with additive blending and the pulse byte +0x74. |
| `0x00003670` | `void ui_gallery_draw_header(void *app)` | When basic.ehp is loaded, draws the 24-pixel header bar from three thumbnail1e pieces (left cap, stretched middle, right cap) and the header text (ui_gallery_get_text word index 0x88) at (8, 4) with shadow, scale 14 and white colour. |
| `0x000039ac` | `void ui_gallery_draw_texts(void *app)` | Raises the two text alphas (+0x84, +0x86) by 0x20 up to 0xff and draws the page title at (0x46, 0xf3) and the item caption fitted to 0x120 pixels at (0x80, 0xf3), with shadow and scale 14. |
| `0x00003d08` | `void ui_gallery_load_slot(void *resources, int index)` | Queues the load of resource slot index: 0x3a uses database/gallery/%s with the language file table 0x00009668 (basic_lang_jpn.ehp, ...) indexed by save_get_language(); 0 uses database/gallery/basic.ehp; others use %s%s.gim with the per-language prefix table 0x000096e0 (field/event/<l>/) and the name from the 8-byte record table 0x00008bc8 {u32 root, char *name}, whose root is passed to the container. |

## Purpose and flow
Scene 0x1e. The gallery shows unlocked event pictures and movies on a 6-column thumbnail grid split into 6 pages.

- Entry `ui_gallery_module_start` (0x00000988) registers `ui_gallery_scene_main` (0x000009c0) and the empty `ui_gallery_scene_end` (0x00000a6c) with `system_scene_register`, third word 0x000099a4.
- `ui_gallery_scene_main`: `ui_gallery_scene_init`, then `system_scene_set_frame_callback(2, ui_gallery_frame_callback, ui_gallery_leave_callback)`, a loop of `ui_gallery_scene_update` + `system_wait_frame`, then `system_scene_return(0x1e, 0)`. Draw runs in the frame callback (0x00000b58); teardown in the leave callback (0x00000b88).
- `ui_gallery_scene_init` builds a 0x300000-byte heap over the module's own buffer at 0x000099c0 (so module `.bss` 0x000099c0..0x003099c0 is the heap). The movie work area is 0x00309a00..0x00709a00 (0x400000 bytes, `system_movie_set_work_memory`), and the zoomed picture is copied to 0x00709a00.
- App state machine `ui_gallery_update` (0x00002594), state word app+0x10:

| State | Action | Next |
| --- | --- | --- |
| 0 | black screen on | 1 |
| 1 | wait for loads; grid setup; GIM lookup; looping background task; fade in 16 | 3 |
| 3 | after fade: texts, grid fly-in, cursor moving | 10 |
| 10 | browse (`ui_gallery_handle_input`) | 0x0b picture, 0x0e movie, 0x10 page, 0x11 leave |
| 0x0b | picture zoom in | 0x0c |
| 0x0c | wait circle/cross | 0x0d |
| 0x0d | picture fade out, slot freed | 10 |
| 0x0e | black rectangle zoom, blocking movie playback | 0x0f (BGM 0x1e restarts) |
| 0x0f | dim fade out | 10 |
| 0x10 | page slide | 10 |
| 0x11 | 30-frame fade out, BGM stop, grid fly-out | 0x12 |
| 0x12 | wait for fade, return 1 | — |

- Input (pad edge word +0x0c): cancel = `system_get_confirm_button(1)` (sound 0x7a06), confirm = `system_get_confirm_button(0)` (0x7a05, buzzer 0x7a07 for locked items or while the cursor moves), L 0x100 previous page, R 0x200 or square 0x8000 next page (0x7a0d), d-pad cursor (0x7a04).

## Key structures
App object (0x110 bytes, vtable 0x00009974 at +0x10c, global 0x003099c8; scene pointer 0x003099c4):

| Offset | Meaning |
| --- | --- |
| +0x00 | resource set |
| +0x04 | background task |
| +0x0c | thumbnail grid |
| +0x10 | state |
| +0x14 | black-screen flag |
| +0x15 | page arrows visible |
| +0x16 | 1 when `save_get_language()` == 0 |
| +0x18 | page 0..5 (starts at 2) |
| +0x1c | cursor mode (2 moving, 1 idle); +0x1e/+0x20 pulse alpha/step |
| +0x21/+0x22 | cursor column/row (char) |
| +0x24/+0x28, +0x2c/+0x30, +0x34 | cursor position, target, lerp factor |
| +0x38 | zoom step; +0x3c..+0x48 rectangle x0, y0, x1, y1 (float) |
| +0x4c, +0x50, +0x54 | texture filter, picture alpha, dim alpha |
| +0x58 | page direction (-1/+1) |
| +0x5c | picture texture (0x00709a00) |
| +0x60..+0x70 | GIMs thumbnail1e, thumbnail2e, side, hilight, bg_tf1 (from basic.ehp) |
| +0x74/+0x76 | arrow pulse |
| +0x78 | movie index (item - 0x39); +0x7a selected item |
| +0x7c/+0x80, +0x84/+0x86 | page title / caption text pointers and alphas |
| +0x88..+0x109 | 0x82 unlock bytes, one per item |

Item numbering: item = column + row * 6 + byte table 0x00008a88[page]; per-page item counts in 0x00008a80 (cursor) and 0x00008a20 (grid; the grid start indices for the thumbnail sheet are the halfwords at 0x00008a28). Items 0..0x38 are pictures (resource slot item + 1); items >= 0x39 are movies (movie index item - 0x39).

Unlock sources (`ui_gallery_compute_unlocks`): items 0-14 progress flag e9 bit 7; 15-23 progress flag ea bit 0 (the two flags set by rel_umd_replace when a disc of an earlier release is inserted); 24-56 `save_test_picture_seen` with 33 bit numbers at 0x0000953c; 57 always; 58 any character 2..0x8e variant with `save_test_character_flag_bit2`; 59 character 2 variants 0 and 1; 60-129 save-state bytes at +0x153e4 indexed by the table 0x00008a37.. .

Task system (a small scheduler private to the module): manager object at 0x000099a0, two intrusive priority-sorted lists. Task base (vtable 0x0000990c at +0x1c): +0x00 update priority, +0x04/+0x08 prev/next; +0x0c draw priority, +0x10/+0x14 prev/next; +0x18 update enabled, +0x19 draw enabled. Vtable slots: +0x08 delete(this, flags), +0x0c attach, +0x10 update, +0x14 draw, +0x18 detach. Background task (0x90 bytes, vtable 0x00009928): +0x20 0x60-byte ehf draw parameters (frame at +0x20), +0x80 ehf player, +0x84 kind (index into the ehf name table 0x00008db0, first entry gallerybg_ehf), +0x88 end frame (399 for kind 0, looping), +0x8c done, +0x8d auto-delete.

Thumbnail grid (0x128c bytes, vtable 0x00009944 at +0x1288: +0x08 delete, +0x0c setup, +0x10 update, +0x14 draw): 0x82 thumbnails of 0x24 bytes (+0x00 active, +0x02 page, +0x04/+0x08 position, +0x0c/+0x10 target, +0x14/+0x16 uv, +0x18 moving, +0x1c has image, +0x1e delay, +0x1f second sheet, +0x20 vtable 0x0000995c); +0x1248 + page * 8 first thumbnail of the page, +0x124c + page * 8 count; +0x127c/+0x1280/+0x1284 GIMs. Thumbnails are 52 x 28 cells (4 per row) in sheets of 72 (thumbnail1e for the first 72, thumbnail2e after); locked items use cell (0x68, 0x188).

Resource set (0xfc bytes, vtable 0x00009980 at +0xf4): 0x3b slot pointers (+0x00..+0xe8), +0xec pending loads, +0xf0 size of the last picture file, +0xf8 current picture slot.

## Files loaded
`ui_gallery_load_slot` (0x00003d08), records of 8 bytes at 0x00008bc8 {u32 root, char *name}:
- slot 0: `database/gallery/basic.ehp` (members: gallerybg ehf table at 0x00008db0, `thumbnail1e.gim`, `thumbnail2e.gim`, `side.gim`, `hilight.gim`, `bg_tf1.gim`).
- slot 0x3a: `database/gallery/<basic_lang_xxx.ehp>` from the table 0x00009668 indexed by `save_get_language()`; member `strTbl.bin` (texts by dictionary word number from the halfword table 0x00008a90; title word index 0x88, locked caption 0x87, item caption item + 4, page titles from the word table 0x00008ba4).
- slots 1..0x39: `%s%s.gim` = per-language prefix (table 0x000096e0, `field/event/<l>/`) + record name; a plain GIM file per event picture.
- Movies: `movie/%s.pmf`, names from the pointer-pair table 0x000092f4 (first: default name; second at 0x000092f8: alternative used when the language is not 0, if non-null), resolved with `container_resolve_path_lbn(root 3)`.
- Loaded buffers starting with the 3-byte magic at 0x000098e4 (EHP) are bound with `container_ehp_bind_with_callback`.

`ui_gallery_prepare_picture` copies the picture file to 0x00709a00, patches header bytes (+0x14 = 8, +0x16/+0x26/+0x486/+0x48a/+0x4b2 = 4, +0x49b = 2) and transposes 8 x 8-byte tiles (stride 0x10) between tile rows 0x1f-i and 0x20+j. Hypothesis (low): the event GIMs are stored in a different orientation or size and are reformatted for the 480 x 272 zoom; needs a PPSSPP trace.

## BOOT.BIN interfaces
`system_heap_create`, `system_operator_new_on_heap`, `container_get_file_size`/`container_load_file`/`container_ehp_find_member`, `ui_ehf_*` (background), `system_ge_*`, `field_3d_gim_emit_texture_frame0`, `system_font_*`, `card_db_get_dictionary_word` (string table), `save_*` unlock tests, `world_count_character_variants`/`world_character_exists`, `system_load_movie_modules`/`system_movie_play_with_volume`/`system_unload_movie_modules`, audio track 0x2c8 (sound effects bank) and BGM 0x1e.

## Name mismatches
- Twin lines accepted: 0x00003850 = `ui_list_window_draw_text`, 0x00003b54 = `ui_draw_level_badge_text_fit` (tail calls hidden by the decompiler, argument shapes match the callers).
- 0x00000988 matches `shop_module_start` byte for byte but registers different callbacks; named `ui_gallery_module_start`.

## Open questions
- What the header patch and tile transposition in `ui_gallery_prepare_picture` achieve (trace the buffer at 0x00709a00 in PPSSPP).
- Contents of the tables 0x00008a20/0x00008a28/0x00008a80/0x00008a88 (page sizes and first items) and how many of the 73 items >= 0x39 are real movies; read the module's data section.
- Which vtable slots the empty functions 0x000001e8, 0x00000244, 0x0000041c, 0x0000052c fill; and the purpose of the empty 0x00001db8.
- Meaning of the save-state bytes at +0x153e4 used for items 60-129.
- Base task vtable 0x0000990c `{0, 0, ui_gallery_task_destroy, 0x41c, 0x1e8, 0x244, 0x52c}`: all four methods are empty; the background task (vtable 0x00009928) overrides them. 0x00001db8 is an empty hook called once when loading finishes (state 1 of `ui_gallery_update`).
