# `rel_limitlist`

Module document of the 2026-11-04 round 6 (all game modules imported; `../modules.md`). English, evidence-based: the sections below come from reading every function of the module in the Ghidra decompilation; hypotheses carry a confidence.

| | |
| --- | --- |
| File | `PSP_GAME/USRDIR/gmodule/rel_limitlist.prx`, 53,164 bytes, plain ELF (relocatable PRX) |
| Slot | id 0x18 |
| Exports → importers | `liblimitlist_rel` (3) → labo, story, title |
| Role (catalogue) | Forbidden/limited list: `database/limitlist.ehp`, `deck_reset_limits`, `deck_set_limit`. |
| Runtime base | unknown; imported at image base 0x0, so addresses are module offsets |
| Registry ids | `rel_limitlist:0x…` |
| Functions | 68 own functions, 68 documented in this round (ui 45, shop 19, deck 4); tables in `../functions/<group>.md`, section `rel_limitlist` |

## Key functions (largest)

| Address | Prototype | Summary (first sentence) |
| --- | --- | --- |
| `0x000003cc` | `void deck_limit_list_draw(void)` | Draw function of the limit-list screen: clears GE layer 0 to black (colour 0xff000000, stencil 0, depth 0, clear flags 0x17). |
| `0x000006c0` | `void * ui_limitlist_draw_tabs(void *list)` | Draws the three tabs (forbidden, limited, semi-limited) when the EHF resource 0x1010 is loaded: plays the layout, then with scissor (0, 0x1a, 480, 12) and font scale 12 x 12 draws each tab label (dictionary resource 0x1020, word from the table 0xa0c4[i]) with ui_draw_level_badge_text_fit at x = per-language table 0xa0a0[language * 3 + i] - 0x59, y 0x1b for the selected tab (bits 2-5 of 0xa6c4, white) or 0x1d (grey 0xffbfbfbf), width 0x48; then each tab's entry count 0xa6da[i] in black at scale 11 x 12 with shop_draw_number_plain (3 digits); finally the scrollbar (shop_draw_scrollbar at (0x1d5, 0x32), height 0xc0, top 0xa6c6[tab], visible 7 rows or 0x42 cells in grid view, count 0xa6da[tab], style 2, image resource 0x8007). |
| `0x00000e0c` | `void * ui_limitlist_draw_card_row(void *list, short x, short y, short *entry)` | Draws one detailed row for the 6-byte entry (u16 card id at +0, u16 thumbnail index at +2): the name plate for the card's frame (ui_draw_card_frame_plate, width 0x13e, at x + 0x17), the thumbnail (shop_draw_card_thumb), the name (card_db_get_name, black, scale 12, width 0x108, at x + 0x1d, y + 2; non-Japanese text with font flag 0x4000 and no trim); for spells and traps (frame 7 or 8) the attribute and spell/trap icons, for monsters attribute, race, level badge and ATK/DEF (shop_draw_stat_value, value 0xffff shown as '?'); then three count badges (shop_draw_results_row_badges) built from the template 0xa0cc: for non-fusion cards copies in member 0's main deck (list 1) and side deck (list 2) plus save card-list entries of state 1 and 2 (whose badge colour turns 0xff0080ff), and the remaining owned copies (save_get_card_count minus both); for fusion cards the first badge is hidden, the second counts the extra deck (list 3) plus state-3 card-list entries, the third the rest. |
| `0x00001948` | `void ui_limitlist_update_dialog(void)` | Dialog update for states 3 and 5. |
| `0x00001f90` | `void ui_limitlist_build_lists(void)` | Rebuilds the three tab lists: frees the old ones, allocates three temporary 0x1b5a-byte id arrays and zeroes the counts 0xa6da[0..2]; every card id 0xe88-0x1f39 that is valid (card_db_is_valid) and whose current limit (deck_get_current_card_limit) is 0, 1 or 2 goes into list[limit]; each list is sorted with system_qsort and ui_limitlist_compare_cards; then for each list allocates count x 6 bytes at 0xa6e0[i] holding {u16 card id, u16 thumbnail index = shop_find_in_sorted_table(id, resource 0x8031), u8 flags = 1}; frees the temporaries, zeroes the scroll tops 0xa6c6[] and cursors 0xa6cc[], sets the tab animation, the cursor rectangle and the detail card. |
| `0x00002284` | `void ui_limitlist_update_browse(void)` | Input handler of the browse state 2 (pad state from system_pad_get_state, +4 pressed): the button system_get_confirm_button(1) (0x2000) leaves: ui_limitlist_find_deck_violation returns 0 -> fade out, audio_stop_sounds_bgm_arg(600), state 6, sound 0x7a06, otherwise opens the deck warning for that card (sound 0x7a0c); system_get_confirm_button(0) (0x4000) on a card enters the card viewer (state 4, sub-state 0, sound 0x7a05); triangle (0x1000) opens the menu (the sound id is shown by the decompiler as a BOOT address, unrecovered); L (0x100) and R or square (0x8200) switch tab (previous/next, modulo 3, sound 0x7a0d); SELECT (0x1) toggles the grid view flag bit 2 of byte 0xa6c5 (sound 0x7a05) and re-places the cursor with ui_limitlist_place_cursor (layout 0x60b grid, 0x701 rows); otherwise moves the cursor (grid or list mover). |
| `0x00002900` | `void ui_limitlist_update_card_viewer(void)` | Card viewer state 4, sub-state 0xa6c2: 0 starts a fade-out; 1 when the fade is done opens the full card viewer for the selected entry (ui_card_viewer_open(id, resource 0x800c, resource 0x8012), ui_card_viewer_set_pack_source(resource 0x8015)), sets the viewer flag bit 3 of byte 0xa6c5 and goes to 2, or with no entry fades in and goes to 3; 2 waits for ui_card_viewer_update to return non-zero, clears the flag and fades in; 3 waits for the fade, then sub-state 0 and state 2. |
| `0x00002d18` | `void ui_limitlist_move_cursor_grid(void *pad)` | Grid-view cursor (11 columns, 6 visible rows): up/down (0x10/0x40 on the repeat word +0xc) move by rows and scroll the top 0xa6c6[t] in steps of 11, with wrap from the first row to the last and back on a new press; left/right (0x80/0x20) move the column modulo 11 within the row; stores cursor 0xa6cc[t] = column + 11 * row. |
| `0x00003538` | `int ui_limitlist_update_loading(void)` | Loading steps, step in bits 1-7 of 0xac50, run only while bit 0 (idle) is set: 0 loads the first archive (ui_limitlist_load_archive; its argument is not shown by the decompiler), 1 loads archive 2; each advances when the load completes (shop_on_archive_loaded) or the archive is already present; 2 allocates 0x135000 bytes at 0xac54 and opens the card image reader card_db_open_cardh_cip(buf, 0x135000, 0) into 0xa6f0; 3 when card_db_cip_is_ready opens the card view (ui_card_view_open) with the 0x24-byte parameters {resources 0x8007, 0x8009, 0x8024, 0x8011, a fifth resource whose id the decompiler shows as a BOOT address, ..., reader 0xa6f0 at +0x1c}, sets the detail card 0xa6f4 = -1 and 0xa6fc = 0; any later step resets the step and returns 1. |
| `0x00003d78` | `void * shop_draw_cursor_frame(void *list, int x, int y, int width, int height, void *image, int flags)` | Same code as rel_shop shop_draw_cursor_frame: four 6 x 6 corners and stretched edges around (x, y, width, height) from image (texture area 0xd5-0xfa, 0x7a-0x9f); bit 3 of flags enlarges it by 2 pixels; nothing for a null image or a non-positive size. |
| `0x000043d0` | `void * shop_draw_stat_value(void *list, uint kind_value, uint xy, uint scale, uint colour, void *image)` | Same code as rel_shop shop_draw_stat_value: kind (low half: 0/1 text labels from the u16 strings 0xa648 + kind x 10, 2/3 icons) then up to 4 digits of the value (high half), '?' for 0xffff, font scale from scale and colour colour. |
| `0x00004978` | `void * ui_draw_card_frame_plate(void *list, uint xy, ushort width, uint frame, void *gim)` | Same code as rel_deck ui_draw_card_frame_plate: draws the coloured name plate of a card frame behind a row (frames 10, 6, 5, 4 on texture level 1, others through shop_get_frame_style_index on level 0), in three sizes by width. |
| `0x00004bfc` | `void * shop_draw_results_row_badges(void *list, uint xy, void *badges, void *label_image, void *icon_image)` | Same code as rel_shop shop_draw_results_row_badges: draws three count badges from three 0xc-byte records (byte +0 icon kind, u32 +4 text colour, byte +8 value) with icon rectangles 0xa678, label widths 0xa69c and x offsets 0xa694; nothing when either image is null. |
| `0x00004fd4` | `void * shop_draw_scroll_arrow(void *list, int x, int y, uchar direction, uint period, int blink, int show, uint frame, void *image)` | Same code as rel_shop shop_draw_scroll_arrow: an 8 x 8 scrollbar arrow at (x, y), flipped for direction > 1, static when show, with a blinking overlay whose alpha is a triangle wave of frame modulo period when blink. |
| `0x0000526c` | `void * shop_draw_scrollbar(void *list, int x, int y, int height, int top, int visible, int count, uint style, void *image)` | Same code as rel_shop shop_draw_scrollbar: track, thumb sized and placed from top, visible and count, and two arrows that blink when the list can scroll. |

## Purpose and flow

Library module (id 0x18, `liblimitlist_rel`) that shows the forbidden/limited list and lets the player replace it with a list imported from the save directory. Three exports form the usual sub-module protocol: `deck_limit_list_start(mode, heap)` (+0x8), `deck_limit_list_update()` (+0x150) and `deck_limit_list_draw()` (+0x3cc). Callers: rel_story, rel_title and rel_labo.

`deck_limit_list_start`: clears the 0x60-byte screen block at 0xa6c0, stores `mode & 3` in bits 0-1 of halfword 0xa6c4, uses the caller's heap or creates its own 0x500000-byte FPL heap (partition 2), loads BGM bank 0x2c8 unless sound 2 already plays, and sets the font flags per language.

State machine (halfword 0xa6c0, `deck_limit_list_update`):

| State | Meaning |
| --- | --- |
| 0 | Loading (`ui_limitlist_update_loading`); then builds the lists, fades in, plays track 2. |
| 1 | Waiting for the fade-in. |
| 2 | Browsing (`ui_limitlist_update_browse`). |
| 3 | Menu / imported-list choice (`ui_limitlist_update_dialog`). |
| 4 | Full card viewer (`ui_limitlist_update_card_viewer`, sub-state 0xa6c2). |
| 5 | Deck-warning dialog (`ui_limitlist_update_dialog`). |
| 6 | Waiting for the fade-out. |
| 7 | Teardown (`ui_limitlist_shutdown_step`); update returns 1, or 2 when bit 4 of byte 0xa6c5 is set. |

Controls in state 2 (pad +4 pressed, +0xc repeat): the `system_get_confirm_button(1)` button (0x2000) leaves, `system_get_confirm_button(0)` (0x4000) opens the card viewer, triangle opens the menu, L / R or square switch tabs, SELECT toggles a row view (7 rows) and a thumbnail grid (11 x 6), d-pad moves, the analog stick scrolls the card text.

Leaving checks the player's deck (`ui_limitlist_find_deck_violation`): it counts the copies of each card in member 0's three lists and compares them with `deck_get_current_card_limit`; one forbidden card is tolerated when `save_test_progress_flag_e9_bit0` is set (same rule as `deck_check_deck_valid`). If a card breaks the list, a warning is built from dictionary words 9/10/11 (forbidden/limited/semi-limited) with the card name; dialog result 2 leaves anyway and sets bit 4 of 0xa6c5, so the update returns 2 instead of 1 (what the caller does with 2: open question).

## Key structures

Screen block 0xa6c0 (0x60 bytes):

| Offset (address) | Field |
| --- | --- |
| 0xa6c0 | u16 state. |
| 0xa6c2 | u16 card-viewer sub-state. |
| 0xa6c4 | u16 bits: 0-1 start mode, 2-5 current tab (0 forbidden, 1 limited, 2 semi-limited), 6-9 teardown step, 10 grid view, 11 card viewer open, 12 "left with an illegal deck". |
| 0xa6c6[3] | u16 scroll top per tab. |
| 0xa6cc[3] | u16 cursor per tab (grid: column + 11 x row). |
| 0xa6d2-0xa6d8 | u16 cursor rectangle x, y, w, h. |
| 0xa6da[3] | u16 entry count per tab. |
| 0xa6e0[3] | pointer to the tab's entries, 6 bytes each: u16 card id, u16 thumbnail index (looked up in the sorted u16 table resource 0x8031), u8 flags (1). |
| 0xa6ec | work heap. |
| 0xa6f0 | card image reader (`card_db_open_cardh_cip`, buffer 0x135000 bytes at 0xac54). |
| 0xa6f4 | card detail view block (card id +0, text scroll +8). |
| 0xa714 / 0xa718 | own FPL id / memory (only when no heap was passed). |

The lists hold every valid card id 0xe88-0x1f39 whose current limit is 0, 1 or 2, sorted by `card_db_get_frame` then `card_db_get_sort_position`. Each row shows deck badges: copies in member 0's main (list 1) and side (list 2) decks, or the extra deck (list 3) for fusions, plus save card-list entries with state 1/2/3, and the copies left over.

Dialog block 0xa720 (0x530 bytes): u16 dialog mode 0xa720 (0 menu, 1 imported-list choice, 3 deck warning), import step 0xa722, import flag bit 0 of 0xa724, message text 0xa728, imported-list count 0xab28, imported records 0xab2c, list-window record 0xab30.

## Files and resources

- Archives: a 2-record table at 0xa124, 12 bytes each `{u16 archive id, void *data, char *path format}`. Paths are formatted with one language letter from the string `jegfis` at 0xa090 (indexed by `save_get_language`) and loaded from root 3 (USRDIR) with `container_load_file`. modules.md names `database/limitlist.ehp`; the exact format strings were not printed in the decompilation (open question). Loading order: the first archive, then archive id 2.
- Resources: ids with bit 0x8000 (0x29 records, table 0xa3dc) and bit 0x1000 (3 records, table 0xa5f4), 12 bytes each `{u16 id, u16 archive id, void *cached member, char *member-name format}`; both tables are sorted by id at start and searched with a binary search. The member name is formatted with the language letter, except for ids 0x8036 and 0x8037, which use the third character of the 8-byte string at 0xa618. Ids used: 0x1002 (title bar GIM), 0x1010 (tab EHF layout; play range = tab), 0x1020 (dictionary), 0x8001/0x8002 (thumbnail images), 0x8006, 0x8007, 0x8009, 0x800a, 0x800c, 0x8011, 0x8012, 0x8015, 0x8021 (background EHF), 0x8024, 0x8031 (sorted thumbnail table), 0x8032 (art-variant table). This is the same resource scheme as rel_deck's `ui_deck_get_resource`.

## Imported limit lists (answers an open question of docs/formats/limit-list.md)

The menu's second choice starts a save import of kind 2 (`save_import_begin`, `save_import_update_scan(2, ...)`, `save_import_update_load`). Each imported list is a 0x108-byte record: UTF-16 name at +0, u16 pair count at +0x100, pointer at +0x104 to count `{u16 card id, u16 status}` pairs (filled by BOOT.BIN's `save_import_load_list_file`). Choosing a record (`ui_limitlist_apply_list`) sets every id 0xe88-0x1f39 to 3 (unlimited) with `deck_set_limit`, applies the pairs and stores the name with `deck_set_limit_list_name`; item 0 (system message 5) restores the built-in list with `deck_reset_limits`. The menu's other choice (result 1) also calls `deck_reset_limits`. So the game does support replacing the list with files from the memory stick, and the per-card status written by `deck_set_limit` lives in the save collection records.

## Shared code

Most drawing helpers are byte-identical to rel_shop's results-list helpers (`shop_draw_card_thumb`, `shop_draw_stat_value`, `shop_draw_scrollbar`, ...), to rel_deck's `ui_draw_card_frame_plate`/`ui_deck_find_resource`, and to BOOT.BIN font wrappers; they keep the twins' names. Where the same BOOT.BIN wrapper appears twice in this module (`ui_list_window_draw_text` three times, `ui_draw_level_badge_text_fit` twice), only one copy takes the twin name and the others get module names (`ui_limitlist_draw_text_to_edge`, `ui_limitlist_draw_digit_text`, `ui_limitlist_draw_text_fit`).

## Name mismatches

- The three exports are named `deck_limit_list_start/update/draw` (group deck) from the importers. The bodies match (they are the screen's start/update/draw), so they were kept; a `ui_limitlist_` name would fit the batch convention better but renaming is not required.

## Open questions

- The archive path and member-name format strings (0xa12c, 0xa3dc + 8, ...) were not shown; read them from `.data` to give the extractor the exact member names.
- The argument of the first `ui_limitlist_load_archive` call in loading step 0 is hidden by the decompiler (probably archive id 1).
- The sound played when triangle opens the menu and the fifth card-view resource id appear as BOOT.BIN addresses in the decompilation (relocated constants); read them from the instructions.
- What callers do with the return value 2 of `deck_limit_list_update`.
