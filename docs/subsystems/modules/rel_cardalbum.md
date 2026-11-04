# `rel_cardalbum`

Module document of the 2026-11-04 round 6 (all game modules imported; `../modules.md`). English, evidence-based: the sections below come from reading every function of the module in the Ghidra decompilation; hypotheses carry a confidence.

| | |
| --- | --- |
| File | `PSP_GAME/USRDIR/gmodule/rel_cardalbum.prx`, 65,236 bytes, plain ELF (relocatable PRX) |
| Slot | id 0x0c |
| Exports → importers | `libcardalbum_rel` (3) → labo, story, title |
| Role (catalogue) | Card album: OCG pack name/list tables, album pages. The only module using `sceJpeg` (6 functions; card art is JPEG, `docs/formats/cip.md`). |
| Runtime base | unknown; imported at image base 0x0, so addresses are module offsets |
| Registry ids | `rel_cardalbum:0x…` |
| Functions | 81 own functions, 81 documented in this round (ui 80, shop 1); tables in `../functions/<group>.md`, section `rel_cardalbum` |

## Key functions (largest)

| Address | Prototype | Summary (first sentence) |
| --- | --- | --- |
| `0x00000000` | `void ui_card_album_draw(void)` | Album frame draw: clears layer 0 to black; unless the album state 0x0000c310 is 0 or 8, either (card viewer flag 0x0000debc clear) draws the background, the 3D setup, the cover and the pages, then on layer 4 the header, footer, the cursor arrow in browse state 3, the card detail panel (ui_draw_card_detail_view_temp with the block 0x0000dec0) and the index menu in state 5, then the fade on layer 5; or (viewer active) ui_card_viewer_draw and the zoom view. |
| `0x000005dc` | `void ui_album_draw_header(void *list)` | Draws the header bar from resource 0x1002 (three pieces at x 0x91..0x1e0), the title (dictionary word 7 of string table resource 0x1030) at (0x96, 4), word 2 right-aligned before the percentage, a '%' sign and the completion value 0x0000de9e (permille) as tens and units with a '.' and one decimal, or 100 when it reaches 1000. |
| `0x00000b4c` | `void * ui_album_draw_zoom_overlay(void *list)` | Zoom viewer overlay: alpha = 0x0000e964 * 0xff / 10; draws icons from resource 0x100e (corner pieces, button glyphs at (0xb, 0xb0), (0x15, 0xea), (0x1ba, 0xbb)) and dictionary words 6 (both top corners), 4, 9 (left, centred on x 0x1d) and 5 (right) at scale 12. |
| `0x00000ef4` | `void ui_album_draw_zoom_view(void)` | When the zoom viewer is active (0x0000def8), on layer 4 darkens the screen with alpha 0x0000e964 * 20, and once the art is decoded (flag bit 1 of 0x0000def9) binds the 512 x 512 RGBA buffer 0x0000defc as texture, builds a 9 x 9 grid of vertices (u, v, x, y, z) scaled by the zoom 0x0000df08 + 0x200, rotated by 0x0000df0c (system_vfpu_matrix3_rot_z) and offset by the pan 0x0000df00/0x0000df04 + screen centre into one of two vertex buffers at 0x0000df20 (double-buffered by bit 2 of 0x0000def9) and draws 8 triangle strips of 18 indices (0x0000e940) with system_gum_draw_array; then the overlay. |
| `0x000013ac` | `void ui_album_open_jump_menu(void)` | Opens the index (jump) menu: allocates card_db_get_top_count() bytes at 0x0000c274 and marks the letter group (card_db_get_top_group) of every owned slot; selects the letter layout table 0x0000ba64 (10 x 5, language 0) or 0x0000ba98 (7 x 4); flags a special row when slots exist beyond the owned list; allocates and fills a 0x120-byte list window (size from the layout, title word 8, draw callback ui_album_draw_jump_menu_items at +0x100) and opens it; album state 5. |
| `0x00001764` | `void ui_album_update_jump_menu(void)` | Index menu update (state 5): runs ui_update_list_window; when the window reports state 6 (closed) returns to state 3 and, unless cancelled, jumps (ui_album_jump_to_slot) to the first slot of the chosen letter group (ui_album_find_group_start) or to the first special slot, then frees the menu. |
| `0x00001c64` | `void ui_album_draw_jump_menu_items(void *list, int x, int y, int width)` | List-window draw callback of the index menu: draws the cursor frame (22 x 22 on a letter, or 0x4e wide on the special row), then each letter of the layout (card_db_get_top_letter) centred in a 22-pixel cell, black when the group has owned cards and half-transparent otherwise; the Japanese layout leaves a gap column after half the columns; the special row shows word 3. |
| `0x00002034` | `void ui_album_init_render(void)` | One-time render setup on layer 0: viewport, scissor, depth, culling, alpha test, colour, field_3d_init_render_state, installs ui_album_heap_alloc/free as the field_3d allocator, clears the 0x3c-byte light block 0x0000c288 (ambient 0xff000000, diffuse white, position from 0x0000bab4), lighting with light 0, ambient 0xff333333, material, specular 10, fog, perspective (0x0000b92c, 0x0000b928, 10, 40), clear colour 0xff770000, texture scale (1, -1) and 8 identity bone matrices. |
| `0x000023d8` | `void ui_album_setup_3d(void)` | Per-frame 3D setup on layer 1: light 0 from 0x0000c288, lighting, ambient, viewport and raster state, fog; projection = translation (0x0000bac0 + cover offset 0x0000dea0, 0x0000bac4, 0x0000bac8) times perspective (near 10, far 40); camera look-at with eye 0x0000bad0, target 0x0000bae0, up 0x0000baf0; identity model matrix. |
| `0x00002744` | `void ui_album_set_page_anim(float speed, void *page, int kind)` | Sets a page's animation kind: copies the 0x68-byte template model (resource from the 16-byte table 0x0000bb00[kind]; 0x1022 is replaced by 0x1023 on pages beyond the owned list) into page+0x40, builds a group mask hiding empty card slots (bit 11 + n for slots 0-8, 12 + n for 9-17) and, for kinds 1 and 2, slots whose card_db_cip_query_image_state is 0, installs ui_album_card_texture_hook as draw state 0, sets the start frame (+0x60) from the table and the speed (+0xa8 = speed, or 0 when start and end frames are equal) and stores kind in the low nibble of byte +0. |
| `0x0000317c` | `void ui_album_update_grid_cursor(void)` | Cell cursor (zone 0, cell = column 0-5 + row 0-2 * 6 in bits 2-7 of 0x0000dea4): left at column 0 / right at column 5 move to the left / right arrow (zone 1), up stops at row 0, down past row 2 moves to the menu (zone 2) with the menu item = column; stores the cell, fixes the page side, refreshes the detail card; confirm on a non-empty card sets state 6 (0x7a05); square moves to the menu. |
| `0x00003630` | `void ui_album_update_menu_cursor(void)` | Menu zone: left/right cycle the 6 items (low nibble of 0x0000dea5); up or square returns to the grid with menu animation 7; confirm (0x7a05) runs item 0 jump to slot 0, 1 previous letter group, 2 flip backward, 3 flip forward, 4 next letter group, 5 last slot, then plays that item's menu animation when a flip started. |
| `0x00003e9c` | `void ui_album_update_flip(void)` | Flip state 4: updates the auto-repeat speeds; during a jump (bit 0 of 0x0000deb4) confirm rebuilds the pages directly around the target page 0x0000deb6 and ends the jump, cancel ends it. |
| `0x00005368` | `int ui_album_zoom_decode(void)` | Incremental full-size art decode. |
| `0x0000575c` | `int ui_album_zoom_update(void)` | Zoom viewer state 0x0000def8: 0 starts (ui_album_zoom_begin) on confirm while ui_card_viewer_is_shown; 1 decodes while raising the overlay step 0x0000e964 to 10; 2 decodes and zooms in until done; 3 interactive: cancel saves the pose and goes to 4 (BGM back to 0x7f over 600 frames), analog Y zooms (step 4, -0x1e0..0x20), d-pad pans (step 2, +-0xf0 / +-0x88), L/R rotate by 0x0000b970 with wrap, triangle resets the pose; 4 zooms out and lowers the overlay; 5 frees and returns 0. |

## Purpose and flow
Module id 0x0c, library `libcardalbum_rel` with three exports: `ui_card_album_start(mode, heap)` (0x00006abc), `ui_card_album_update()` (0x00006be4, returns 1 when closed) and `ui_card_album_draw()` (0x00000000). Callers: rel_title (main menu, mode 0, title heap), rel_story (world overlay, mode 1, heap 0) and rel_labo. With heap 0 the album creates its own 10 MB FPL (`sceKernelCreateFpl(..., 0xa00000, ...)`) and a heap on it.

The album is a 3D book: pages are TMS models with card-shaped parts, each page holds 18 cards (9 per side, 3 x 3), and turning a page plays a model animation.

Album state 0x0000c310: 0 load (JPEG library + cardj reader, cardh/cardm readers, cardalbum.ehp, card list), 1 cover opening (after 0x21 frames), 2 wait for the cover, 3 browse, 4 page flip, 5 index (letter) menu, 6 card viewer (with the full-size zoom viewer), 8 shutdown. State 7 is unused.

Browse input: d-pad cell cursor (6 x 3 cells over the two visible pages), an arrow zone and a 6-item bottom menu (first, previous letter group, flip back, flip forward, next letter group, last); L/R flip with acceleration while held (speed 1.0 + 0.5 per repeat up to 5.0); triangle opens the index menu; confirm on a card opens the BOOT card viewer; analog stick Y scrolls the detail text; cancel closes.

## Card list
`ui_album_build_card_list` (0x00004510): card ids 0xe88..0x1f39 placed in `card_db_get_sort_position` order; every valid, non-token card that is not one of 16 "special" ids gets a slot (its id when `save_get_card_state` is non-zero, 0 otherwise), so empty slots keep their place. Slot array: u16 at 0x0000c320, count 0x0000c31c; completion = owned * 1000 / slots (0x0000de9e, shown as a percentage with one decimal). Owned special cards go to a final special page (after rounding to whole 18-slot pages) at fixed positions: 0x1386, 0x1387, 0x1388, 0xecd, 0xea8, 0x1ca4..0x1cac, 0x1cad, 0x1b4d (sorted list at 0x0000bc10). 0x1386-0x1388 are cards granted by rel_umd_replace for inserting earlier discs, and 0xea8, 0xecd and 0x1b4d are on that module's exclusion list for its random card, so the special page holds bonus/promotional cards that do not count toward completion (hypothesis, medium). Total slots including the special page: 0x0000c31e.

Index menu: letter groups from `card_db_get_top_group`/`card_db_get_top_letter` (the CARD_Top table); layout 10 x 5 (table 0x0000ba64) for language 0, 7 x 4 (0x0000ba98) otherwise, plus a row for the special page.

## Key structures
- Page object (0xc0 bytes, list head 0x0000c318, links +0xac prev / +0xb0 next): byte +0 low nibble animation kind, high nibble position 0-7 (3 = left visible page, 4 = right visible page); +2 page number (15 bits); +4 18 card ids (entries 0-8 on the right side, 9-17 on the left side); +0x28..+0x30 position (table 0x0000c1ec, 12 bytes per position); +0x40 copy of the template model instance (0x68 bytes); +0x60 animation frame; +0xa8 speed.
- Animation kind table 0x0000bb00, 16-byte entries {u16 model resource, float start frame, float end frame, u8 next kind}; kinds 1/2 neighbour pages, 3 cover-open pages, 4 flip forward, 5 flip backward.
- Cursor 0x0000dea4: bits 0-1 zone (0 cells, 1 arrows, 2 menu), bits 2-7 cell (column 0-5 + row * 6); 0x0000dea5 low nibble menu item, bits 4-5 arrow side. Jump request 0x0000deb4 (bit 0 active, bits 1-6 target cell), target page 0x0000deb6, jump speed 0x0000deb8 (3.125 / 6.25 / 12.5).
- Resource table 0x0000be88: 0x21 entries of 16 bytes {u16 id 0x1001.., cached pointer, member name format, tmf member name}; names are formatted with a one-letter language code (table 0x0000c1dc). Model table 0x0000c160: 5 entries {u16 id 0x1020..0x1024, instance, tms, animation (TMA list or TGMT), tma}; first tms `album_cover00.tms`. 0x1020 cover, 0x1024 cell cursor; 0x1022/0x1023 page templates (0x1023 for pages beyond the owned list).
- Detail panel block 0x0000dec0 (card id, scroll 0x0000dec8, max 0x0000decc) passed to `ui_draw_card_detail_view_temp`.

## Card art (the only sceJpeg user)
Three cip readers: `card_db_open_cardh_cip` (0x6d000-byte reader, for the BOOT card view), `card_db_open_cardm_cip` (0x3f1000-byte reader, page textures through `card_db_cip_query_image_state`/`card_db_cip_write_image_texture`, preloaded one per frame from an 18-entry queue) and `card_db_open_cardj_cip` (0x3e000-byte reader) for the full-size zoom viewer.

Zoom viewer (`ui_album_zoom_*`): `sceJpegInitMJpeg`, `sceJpegCreateMJpeg(512, 512)`; per card `card_db_cip_get_image(cardj, card, artwork)` + `card_db_cip_get_slot_bytes` give the JPEG stream, `sceJpegGetOutputInfo(jpeg, size, &info, 1)` the output size, `sceJpegDecodeMJpegYCbCr(jpeg, size, out, out_size, 1)` decodes to planar YCbCr: Y 512 bytes per line, Cb from out + size * 4 / 6 and Cr from out + size * 5 / 6, 256 chroma bytes per pair of lines (4:2:0). The game converts 32 lines per frame to RGBA8888 (512 x 512 x 4 = 1 MB) with float constants at 0x0000b974..0x0000b984 (Y offset 16, chroma offset 128), then draws it as a 9 x 9 vertex mesh that can be panned, zoomed and rotated. The artwork variant comes from `save_get_card_value_bits4_6(card)`. The BGM is faded to 0 during the decode and to 0x20 while viewing. So the cardj JPEGs decode within a 512 x 512 frame (the decoder limit; the exact image size is not visible in the code).

## Files loaded
- `database/cardalbum.ehp` (root 3): textures, string table resource 0x1030 (dictionary words 2-9 used), ehf menu animation 0x1010, cover/page/cursor models (`album_cover00.tms` and the other members of the model table).
- The cardh, cardm and cardj cip archives through the BOOT card_db readers.

## Name mismatches
- Twins accepted: 0x00000888 `ui_list_window_draw_text`, 0x000008a8 `ui_window_draw_text_px`, 0x000023b8 `field_3d_copy_vec3`, 0x00006384 `shop_on_archive_loaded`, 0x00006414 `deck_compare_u16_ascending`, 0x00006424 `shop_bsearch_resource_table`.
- 0x00001fa0 is a second identical copy of `ui_list_window_draw_text` in the same module; named `ui_album_draw_text_to_edge`.
- Twins rejected: 0x0000649c (`ui_clear_card_info_menu_state_a`; it clears the album preload queue), 0x00002ddc/0x00002dec (`audio_heap_free`; album heap allocator and free).
- The decompiler shows the cursor sound id as the address of `thunk_card_db_is_lightsworn` (`audio_play_sound(card_db::thunk_card_db_is_lightsworn)`); it is a constant that matches a symbol address, not a call. The same artefact hides the DP amount in rel_usb_connect.

## Open questions
- Contents of the layout, position and animation tables (0x0000ba64, 0x0000c1ec, 0x0000bb00, 0x0000bb80) and the member names of the resource table.
- `card_db_cip_query_image_state` return values: the album writes a texture when it returns 0 (page hook) or 1 (preload); confirm the meaning in BOOT.
- 0x00005074 (ehf play range hold) passes hidden register arguments.
- Meaning of mode (bits 0-1 of 0x0000c314: 0 title, 1 story); no code read here branches on it.
- 0x00005074 freezes the EHF of resource 0x1010 on its last frame once its play range has run (`ui_ehf_set_play_range(ehf, end - 1, end)`).
- 0x00006ab4 returns 0 and has no code or data reference in the module image.
