# `rel_tutoriallist`

Module document of the 2026-11-04 round 6 (all game modules imported; `../modules.md`). English, evidence-based: the sections below come from reading every function of the module in the Ghidra decompilation; hypotheses carry a confidence.

| | |
| --- | --- |
| File | `PSP_GAME/USRDIR/gmodule/rel_tutoriallist.prx`, 35,116 bytes, plain ELF (relocatable PRX) |
| Slot | id 0x21 |
| Exports → importers | `libtutoriallist_rel` (4) → labo, story, title |
| Role (catalogue) | Tutorial list: `database/tutoriallist.ehp`. |
| Runtime base | unknown; imported at image base 0x0, so addresses are module offsets |
| Registry ids | `rel_tutoriallist:0x…` |
| Functions | 30 own functions, 30 documented in this round (ui 27, shop 2, deck 1); tables in `../functions/<group>.md`, section `rel_tutoriallist` |

## Key functions (largest)

| Address | Prototype | Summary (first sentence) |
| --- | --- | --- |
| `0x00000000` | `void ui_tutorial_list_draw(void)` | Draw function of the tutorial list: clears GE layer 0 to black; in states 1-3 draws on layer 4 the background layout, the title bar, the tab panel at (0x4b, 0x27, 0x14b, 0xdb), the scrollbar at (0x18a, 0x42) height 0xb3 from the line counts of the current tab (lines before the scroll top, visible 8, total), the rows from the scroll top 0x7428[tab] at x 0x51, y 0x3c + 0x18 x line while 8 lines are not used up (ui_tutoriallist_draw_row), the cursor frame around the entry at top + cursor 0x742c[tab] (x 0x6e, width 0x117, height lines x 0x18 - 5), and the fade on layer 5. |
| `0x00000454` | `void * ui_tutoriallist_draw_background(void *list)` | When EHF resource 0x1011 is loaded plays it with a cleared 0x60-byte parameter block holding the frame counter between ui_ehf_begin_draw and ui_ehf_end_draw and restores texture function and blending. |
| `0x00000510` | `void * ui_tutoriallist_draw_title_bar(void *list)` | When GIM 0x1003 is loaded draws the title bar (end pieces at x 0 and 0x1d4, a 0x1c8-wide middle) and dictionary word 1 in white at scale 14 at (8, 4). |
| `0x00000678` | `void * ui_tutoriallist_draw_tab_panel(void *list, int x, int y, int width, int height)` | When GIM 0x1002 is loaded draws the panel frame (texture row tab x 0x20, current tab in the low nibble of 0x7424) and two tab buttons splitting width: the current one white, the other translucent, grey and 2 pixels lower under a scissor; each with a 16 x 16 icon from GIM 0x1003 (u = tab x 16) and dictionary word 2 + tab at scale 13. |
| `0x00000b9c` | `void * ui_tutoriallist_draw_row(void *list, int x, int y, int id)` | Draws tutorial id's row when GIM 0x1003 is loaded: a 0x19 x 0x15 number badge, the row box (ui_tutoriallist_draw_row_box, width 0x11b, height 0x18 x line count 0x74cc[id] - 1), the number (id + 1, or id - 7 for ids from 8) in white, and dictionary word id + 4 in black as a text box (0x110 wide) at (x + 0x20, y + 5); font end-y offset 0x280 for Japanese, 0x180 otherwise. |
| `0x00000d74` | `void * ui_tutoriallist_draw_row_box(void *list, int x, int y, int width, int height)` | When GIM 0x1003 is loaded draws a 9-slice box at (x, y, width, height) with 6 x 6 corners at texture (0x19/0x24, 0x2f/0x3a) and edges/centre stretched from (0x1f, 0x35). |
| `0x00000fd8` | `void * ui_tutoriallist_draw_cursor(void *list, int x, int y, int width, int height)` | When GIM 0x1003 is loaded draws the cursor frame around (x, y, width, height): 6 x 6 corners at texture (0x19/0x28, 0x14/0x29) and stretched edges; every other 8 frames (bit 3 of the frame counter) the frame is 2 pixels larger. |
| `0x00001264` | `void * ui_tutoriallist_draw_scroll_arrow(void *list, int x, int y, char direction, uint period, int blink, int show, uint frame, void *image)` | Scrollbar arrow from image at (x, y), 8 x 8, texture column 0x2e (v + 8 for direction 1): static arrow (v 0x30) when show, overlay (v 0) with triangle-wave alpha over frame modulo period when blink. |
| `0x000014e8` | `void * ui_tutoriallist_draw_scrollbar(void *list, int x, int y, int height, int top, int visible, int total)` | When GIM 0x1003 is loaded draws the scrollbar: track (column 0x37), a thumb of length visible x (height - 2) / total (at least 10, whole track when everything fits) placed at top x free length / (total - visible), and arrows (ui_tutoriallist_draw_scroll_arrow, period = frame rate) blinking when top > 0 / top < total - visible; values are line counts. |
| `0x00001880` | `void ui_tutoriallist_build_lists(void)` | Builds the two tabs: for tutorial ids 0-0x17 (5-7 skipped) puts ids below 8 into tab 1 (list 0x7480, count 0x7432) and ids 8-0x17 into tab 0 (list 0x7434, count 0x7430), remembering the tab and position of the initial selection 0x7426; stores each id's line count 0x74cc[id] = (text height of dictionary word id + 4 at width 0x110 + 0x40) / font line height; sets 0x7518 = 1 and the current tab; then moves the cursor/scroll of that tab down (same rules as the down key) until the selected entry is under the cursor. |
| `0x00001c68` | `void ui_tutoriallist_update_browse(void)` | Input of the browse state 2 (pad +4 pressed, +0xc repeat): cancel (system_get_confirm_button(1)) sets the cancelled flag bit 4 of 0x7424, fades out, stops the BGM (fade 600), state 3, sound 0x7a06; confirm on a real entry stores its id in 0x7426, fades out, stops the BGM only for ids above 7, state 3, sound 0x7a05; L, R, left, right or square (0x83a0) toggle the tab (sound 0x7a0d); up moves the cursor 0x742c[tab] up, else the scroll top 0x7428[tab], and on a fresh press at the top jumps to the end; down moves the cursor while the next entry still fits in 8 lines, else scrolls by enough entries to show it, and on a fresh press at the end wraps to the top; sound 0x7a04 on moves. |
| `0x00002404` | `void * ui_tutoriallist_load_archive(void)` | Returns the archive 0x7414 when loaded; otherwise, when the loader is idle, clears the idle bit, allocates the size of "database/tutoriallist.ehp" (root 3, USRDIR) from the work heap and starts container_load_file with callback shop_on_archive_loaded; returns 0. |
| `0x000024b4` | `void * ui_tutoriallist_get_resource(uint id)` | Looks id up in the 4-record resource table 0x739c ({u16 id, cached member +4, name format +8}) with shop_bsearch_resource_table; on a cache miss formats the member name with the language letter of the 6-character string 0x73e8, finds it in the archive (container_ehp_find_member) and caches it. |
| `0x000026c0` | `void ui_tutorial_list_start(int selection, void *heap)` | Start function of the tutorial list (libtutoriallist_rel export): clears the 0x10c-byte block 0x7420, uses heap as work heap 0x751c or creates its own 0x200000-byte FPL (name 0x73f4, partition 2) into 0x7520/0x7524 with system_heap_create; sceKernelChangeCurrentThreadAttr(0, 0x4000); initialises the resource loader; stores the initial selection 0x7426 = selection (8 when negative) and, when it is above 7, releases all banks and loads BGM bank 0x2c8; enables font shadow and colour codes, resets the end-y offset and sets the language-dependent font flags. |
| `0x0000280c` | `int ui_tutorial_list_update(void)` | Per-frame update, state halfword 0x7420: 0 waits for the archive, builds the lists, state 1, fades in, hides the loading overlay and plays track 2 (audio_play_track_with_fade); 1 waits for the fade, then 2; 2 browsing (ui_tutoriallist_update_browse); 3 waits for the fade-out, then 4; 4 shuts down and returns 1 (a tutorial was chosen) or 2 (cancelled, bit 4 of 0x7424). |

## Purpose and flow

Library module (id 0x21, `libtutoriallist_rel`): a two-tab list of duel tutorials. Exports: `ui_tutorial_list_draw` (+0x0), `ui_tutorial_list_start(selection, heap)` (+0x26c0), `ui_tutorial_list_update()` (+0x280c), `ui_tutorial_list_get_selection()` (+0x2980); callers rel_story, rel_title, rel_labo. The 8-byte function at +0x26b8 that returns 0 is the probable e_entry.

States (halfword 0x7420): 0 loading `database/tutoriallist.ehp`, then building the lists; 1 fade-in; 2 browsing; 3 fade-out; 4 shutdown, update returns 1 (chosen) or 2 (cancelled). `ui_tutorial_list_get_selection` returns the chosen id or -1.

Tutorial ids 0-0x17 (ids 5-7 are skipped by the list builder): tab 0 holds ids 8-0x17, tab 1 ids 0-4 (dictionary word of entry id = id + 4, shown number = id + 1 or id - 7). The initial selection (start argument, 8 when negative) picks the tab and scroll position; when it is above 7 the start function loads BGM bank 0x2c8, and choosing an id above 7 stops the BGM (hypothesis: ids above 7 are the duel tutorials that switch scenes, ids below 8 run elsewhere; confidence low).

## Key structures

Block 0x7420 (0x10c bytes): state 0x7420; selection 0x7426; byte 0x7424 low nibble tab, bit 4 cancelled; 0x7428[2] scroll top; 0x742c[2] cursor; 0x7430[2] counts; lists 0x7434 + tab x 0x4c (u16 ids); 0x74cc[0x26] line count per id (text height at width 0x110); 0x7518 built flag; 0x751c heap; 0x7520/0x7524 own FPL (0x200000 bytes). The view holds 8 lines of 0x18 pixels.

## Files and resources

`database/tutoriallist.ehp` (root 3); resource table 0x739c, 4 records `{u16 id, cached member, name format}`: 0x1002, 0x1003 (GIM), 0x1011 (background EHF), 0x1020 (dictionary); member names formatted with the language letter from 0x73e8.

## Shared code

The row, tab-panel, scrollbar and arrow drawers are the same code shapes as rel_duelrecord's (different addresses, so no twin lines); the archive callback and resource search are rel_shop's.

## Open questions

- 0x00001c5c (12 bytes, hidden-argument text measure) is skipped.
- Which scene or tutorial each id starts (the caller decides; see rel_story `world_state_update_tutorial_list` and rel_title).
