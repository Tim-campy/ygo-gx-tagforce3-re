# `rel_recipeviewer`

Module document of the 2026-11-04 round 6 (all game modules imported; `../modules.md`). English, evidence-based: the sections below come from reading every function of the module in the Ghidra decompilation; hypotheses carry a confidence.

| | |
| --- | --- |
| File | `PSP_GAME/USRDIR/gmodule/rel_recipeviewer.prx`, 64,444 bytes, plain ELF (relocatable PRX) |
| Slot | id 0x1b |
| Exports → importers | `librecipe_viewer_rel` (3) → deck, story, title |
| Role (catalogue) | Deck-recipe viewer: `deck_load_recipe`, `deck_get_recipe_name`, OSK. |
| Runtime base | unknown; imported at image base 0x0, so addresses are module offsets |
| Registry ids | `rel_recipeviewer:0x…` |
| Functions | 81 own functions, 81 documented in this round (deck 57, shop 15, ui 9); tables in `../functions/<group>.md`, section `rel_recipeviewer` |

## Key functions (largest)

| Address | Prototype | Summary (first sentence) |
| --- | --- | --- |
| `0x00000008` | `void deck_recipe_viewer_start(uchar mode, int *params, uchar own_reader, int owner)` | Sub-module start of the deck-recipe viewer. |
| `0x00000484` | `uint deck_recipe_viewer_update(void)` | Sub-module update. |
| `0x00000aa4` | `void deck_recipe_viewer_handle_list_input(void)` | Deck-list input (state 3), list of the current tab (0x0000c5ea bits 0-1: 0 stored decks, 1 recipes, 2 imported decks; first visible u16 0x0000c5ec + 4 x tab, cursor row +2, 8 rows). |
| `0x00001814` | `void deck_recipe_viewer_load_selected_deck(void)` | Builds the deck view 0x0000c5fe (0x21e bytes) for the selected entry of the current tab: an imported deck (buffer +0x100 of record i), a recipe (deck_load_recipe and deck_get_recipe_card_list) or a used stored deck (struct at +0x54, card list at +0x114), with deck_recipe_viewer_build_deck_view; clears it when nothing is selected. |
| `0x00001d2c` | `void deck_recipe_viewer_build_deck_view(ushort *view, void *deck, void *key_list)` | Fills the 0x21e-byte deck view from a deck struct: header u16 (bits 0-6 main count, 7-10 side count, 11-15 extra count) and sorted 6-byte entries (id, image index from shop_find_in_sorted_table(id, resource 0x8031), flags) for main (+2), side (+0x16a) and extra (+0x1c4). |
| `0x00002874` | `void deck_recipe_viewer_open_dialog(ushort type)` | Prepares the dialog list window 0x0000e138 (0x120 bytes, heap 0x0000e11c): type 1 word 0x66, 2 word 0x67, 4 word 0x64 and 6 word 0x65 as two-choice prompts, 3 word 0x6b with one button, 5 a two-item menu (0xe8 x 0x13 items, callback deck_recipe_viewer_draw_menu_item); type 0 only resets the fields. |
| `0x00002e60` | `void deck_recipe_viewer_draw(void)` | Sub-module draw: clears layer 0 to black; nothing more in states 1 and 7. |
| `0x00003580` | `void deck_recipe_viewer_draw_deck_cards(void *list)` | Draws the card grid of the selected deck from the deck view 0x0000c5fe, limited to the first 0x0000c81c entries (reveal counter). |
| `0x00003be0` | `void * deck_recipe_viewer_draw_stored_deck_row(void *list, int index, int x, int y)` | Row drawer for stored decks (entry 0 of the table 0x0000c05c): draws the row panel from resource 0x1001 (pieces 0x67, 0x18 and 6 px wide, 0x1e high, texture row v 0x60 in owner mode, else 0) at (x, y); in black at scale 0xc, an empty slot (word 0 of save_get_stored_deck(index) is 0) shows the placeholder string 0x0000c068 centred in 100 px at y + 9, a used one its name (+4) fitted to 0x6e px at (x + 0x10, y + 3) and its timestamp (+0x44, deck_recipe_viewer_draw_timestamp) at (x + 0x10, y + 0x10). |
| `0x0000405c` | `void * deck_recipe_viewer_draw_recipe_row(void *list, int index, int x, int y)` | Row drawer for recipes (entry 1 of the table 0x0000c05c); nothing when index >= the recipe count 0x0000c900. |
| `0x00004f14` | `void * deck_recipe_viewer_draw_scrollbar(void *list, int x, int y, int height, int top, int visible, int count)` | Draws a vertical scrollbar from resource 0x8007 (texture column u 0x77); arguments 5-7 travel in t0-t2. |
| `0x000055fc` | `int deck_recipe_viewer_update_resource_load(void)` | Stepped resource loader on the byte 0x0000e260 (bit 0 idle, bits 1-7 phase); returns 0 while a file load is pending (bit 0 clear). |
| `0x00005ed0` | `int ui_update_osk_input(int layer)` | Per-frame keyboard step by the keyboard state byte: in states 1-3 draws the fade on GE layer layer; in states 1-2 polls sceUtilityOskGetStatus and, when the dialog finished, shuts it down, copies the result back into the caller's buffer doubling every '$' when the dialog result is 0, calls the callback (if any), fades in and moves to 3; state 4 restores the network word and soft reset. |
| `0x00006b8c` | `void *shop_draw_card_badges(void *list, short x, short y, ushort *card, int show_count, int is_new, int show_flag7, int show_bit5, int limit_mode, ushort mark, void *digit_image, void *image, void *overlay_image)` | Draws the badges on a card thumbnail for a 6-byte entry: overlay for byte 5 bit 6, copies with show_count, the new-card mark or the card-limit icon (deck_get_card_limit(limit_mode, id) < 3), and marks for byte 4 bit 7 and byte 5 bit 5 by the show flags. |
| `0x00006fc4` | `void shop_draw_scroll_arrow(void *list, int x, int y, uchar direction, uint period, int blink, int show, uint frame, void *image)` | Draws an 8 x 8 scrollbar arrow from image (ninth argument, stack) at (x, y), oriented by direction, static with show and blinking with a triangle-wave alpha with blink. |

## Purpose and flow
Library `librecipe_viewer_rel` (id 0x1b). Lists decks and shows their cards. Three sources (tab 0x0000c5ea bits 0-1): 0 the 50 stored decks (`save_get_stored_deck`), 1 the recipes 1-461 unlocked in the save (save recipe entry bit 0), 2 decks imported from other saves (`save_import_*`, 0x1c0 bytes per deck, deck struct at +0x100).

- `deck_recipe_viewer_start(mode, params, own_reader, owner)` (`0x00000008`): `mode` 0 browse/manage, 1 choose a stored-deck slot to save the current deck, 2 choose a deck to load. `params` = 5 words: heap (0 = own 0x468000 FPL), card reader, unknown, save callback, load callback (`rel_deck` passes `deck_save_to_stored_deck` and `deck_load_deck_into_editor`). `owner != 1` selects owner mode: only the owner's first recipe is listed and availability uses `deck_get_other_deck_card_allowance` with the owner's slot recipe (loaded into `0x0000c820`).
- `deck_recipe_viewer_update` (`0x00000484`) state (bits 4-11 of `0x0000c5e0`): 0 import scan + resource load, 1 first frame set-up, 2 fade, 3 list, 4 card grid, 5 save into slot, 6 fade out, 7 release. Return: -1 running; when finished -2 (cancel or mode 0), the slot index (mode 1) or `index | tab << 16` (mode 2).
- Dialogs (`deck_recipe_viewer_open_dialog`, window `0x0000e138`): 1 load? (word 0x66), 2 overwrite? (0x67), 3 notice (0x6b), 4 delete? (0x64), 5 stored-deck menu (rename via OSK with title word 0x6a, delete), 6 word 0x65.

## Key structures
- Deck view `0x0000c5fe` (0x21e bytes): u16 header (bits 0-6 main count, 7-10 side count, 11-15 extra count), sorted 6-byte entries main at +2 (`0x0000c600`), side at +0x16a (`0x0000c768`), extra at +0x1c4 (`0x0000c7c2`). Entry byte 5 bit 1 = the player can field this copy (owned copies, else save card-list items which also set byte 4 bit 7), bit 5 = key card. Sorting: frame, then `card_db_get_sort_position`.
- Card grid: 7 rows (0-3 main, 4-5 extra, 6 side), columns per row `0x0000c5fa` (main), `0x0000c5fc` (extra); reveal animation counter `0x0000c81c`.
- List records: recipes `0x0000c902` (8 bytes: u16 recipe, u16 number, u8 save entry bits 1-8, u8 owned copies, u8 total cards; count `0x0000c900`), stored decks `0x0000d772`, imports `0x0000d90c`. The row drawer for imports shows a "complete" mark when owned == total.
- Stored deck fields used: +0 used flag, +4 name (UTF-16, 16 chars max via OSK), +0x54 deck struct, +0x114 card list (u32 count + u16 ids).

## Files and resources
Same resource scheme as `rel_deckswap`: tables `0x0000c384` (0x29 ids) and `0x0000c58c` (3 ids with bit 0x1000: 0x1001 row panels, 0x1010 tabs, 0x1011 title), file table `0x0000c0cc` (2 files, container root 3). Title words per mode: u16 table `0x0000c054`; help words `0x0000c094`.

## Talks to
BOOT.BIN `deck_load_recipe`, `deck_get_recipe_name`, `deck_get_recipe_level`, `deck_get_owner_recipe`, `deck_get_recipe_card_list`, `save_get_recipe_entry`, `save_get_stored_deck`, `save_import_begin/update_scan/update_load/update_message`, card viewer, OSK; music bank 0x2c8 is loaded when no BGM plays and released on exit.

## Corrections / notes for docs
- `docs/subsystems/deck.md` says the viewer receives `deck_save_to_stored_deck` and `deck_load_deck_into_editor` as callbacks: confirmed as params words 3 and 4 (`0x0000e128`, `0x0000e12c`); the load callback receives (deck, card list, name or import record, owner).
- The recipe list shows recipes 1-461 with a non-zero level and save recipe entry bit 0 set (recipe 0, the starting deck, is not listed).

## Name mismatches
- 0x00002d70: twin `ui_card_list_draw_sort_menu` (a single `ui_draw_list_window` call matches many functions); this copy draws the dialog window, named `deck_recipe_viewer_draw_dialog`. The `rel_deckswap` copy 0x00002ed4 (message window 0x000196a4) has the same generic shape and probably deserves a module name too (not checked).

## Open questions
- `deck_recipe_viewer_count_owned_copies` counts copy k of an id while the owned count differs from k; this looks like an off-by-one-tolerant "owned copies" count but gives odd results for 1 owned / 3 listed (check in PPSSPP).
- Word 3 of the parameter block (`0x0000e124`) is never read in the functions covered.
- Functions skipped (partly read): `0x00003580`, `0x00003be0`, `0x0000405c`, `0x0000520c`, `0x000055fc`, `0x00004f14`.
## Resolved open question
- Parameter word 0x0000e124 is read: in loader phase 0 (`deck_recipe_viewer_update_resource_load`) a non-zero value is installed as the already-loaded buffer of file group 1 in the file table 0x0000c0cc, so the viewer does not load that archive itself (the caller can share its own copy). With a caller-supplied card reader (0x0000e120 non-zero) the loader finishes right after loading file group 2, without opening the card view.

## Layout facts
- Card grid y: main rows 0xf, 0x30, 0x51, 0x72; extra rows 0x9e, 0xbf; side row 0xeb; counts at x 0x1cd, y 3 / 0x92 / 0xdf. Card x = 300 + column x 0xaf / 7 (rows of fewer than 8) or 300 + column x 0x98 / (n - 1).
- Tab labels: dictionary resource 0x8033, word table 0x0000c084 indexed [label x 2 + (tab count != 2)], label 3 replaces tab 0 in owner mode.
- Card view resources: 0x8007, 0x8009, 0x8024, 0x8011, 0x8010 (the third one appears as a bogus `card_db_is_neo_spacian` pointer in the decompilation; the disassembly shows `ori a0, zero, 0x8024`).

## Open questions
- `deck_recipe_viewer_draw_recipe_row` in owner mode tests the complete mark on the stored-deck records (0x0000d777/0x0000d778 + 8 x index) instead of the recipe records; check in PPSSPP whether the mark can appear wrongly in owner mode.
