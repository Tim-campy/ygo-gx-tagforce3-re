# `rel_throw_starter`

Module document of the 2026-11-04 round 6 (all game modules imported; `../modules.md`). English, evidence-based: the sections below come from reading every function of the module in the Ghidra decompilation; hypotheses carry a confidence.

| | |
| --- | --- |
| File | `PSP_GAME/USRDIR/gmodule/rel_throw_starter.prx`, 206,216 bytes, plain ELF (relocatable PRX) |
| Slot | scene 0x1d, id 0x30 |
| Exports → importers | — |
| Role (catalogue) | Launcher: 7 function starts; calls scene 0x1c, then returns. Most of its size is data, not yet examined. |
| Runtime base | unknown; imported at image base 0x0, so addresses are module offsets |
| Registry ids | `rel_throw_starter:0x…` |
| Functions | 13 own functions, 13 documented in this round (world 12, ui 1); tables in `../functions/<group>.md`, section `rel_throw_starter` |

## Key functions (largest)

| Address | Prototype | Summary (first sentence) |
| --- | --- | --- |
| `0x00000000` | `int world_throw_starter_module_entry(int arg)` | Module entry point of rel_throw_starter (scene 0x1d): when arg is 0 registers the scene with system_scene_register(start world_throw_starter_scene_main 0x00000038, end world_throw_starter_scene_end_noop 0x00000164, data 0x00041cd0). |
| `0x00000038` | `void world_throw_starter_scene_main(void)` | Scene start callback of scene 0x1d: hides the loading overlay, initialises the selection (world_throw_starter_init) and, when that succeeds, installs the frame callbacks (system_scene_set_frame_callback(1, world_throw_starter_draw, world_throw_starter_leave)) and loops world_throw_starter_update + system_wait_frame. |
| `0x00000164` | `void world_throw_starter_scene_end_noop(void)` | Empty function (returns at once). |
| `0x0000016c` | `int world_throw_starter_init(void)` | Sets the thread attribute 0x4000, creates a 0x10000-byte heap over 0x00031cd0 (pointer 0x00041ce0) and walks the character-key rows 0..0x595 (world_get_character_key(row, &character, &variant)): skips characters 0 and 1, variant 2 of characters 2 and 0x14, variant 1 of characters 0x24 and 0xc, and every variant other than 0 of characters 0x29, 0x27, 0x26, 0x25, 0x10, 8 and 7; keeps the rest when world_character_exists(character, variant) and world_character_has_partner_deck(character, 0) hold, copying the name (world_get_character_name_string(character, variant, 0), system_wcscpy) into 0x40-byte slot n of the table 0x000051b4 (slot 0 already holds the Random entry) and character/variant into 0x00041e18 + n * 4 / 0x00043470 + n * 4. |
| `0x000003c8` | `int world_throw_starter_update(void)` | On the first call opens the selection list (world_throw_starter_open_partner_list), points the title text 0x00044b4c at the UTF-16 string 0x000050f4 (Select Partner) and sets the state 0x00041cdc = 1, returning 0. |
| `0x0000046c` | `void world_throw_starter_draw(void)` | Frame callback: on layer 1 draws the title window list 0x00044ac8 (ui_draw_window_list) and the selection list (world_throw_starter_draw_partner_list), then commits the layer. |
| `0x000004b4` | `void world_throw_starter_leave(void)` | Leave callback: resets the selection list window (world_throw_starter_reset_partner_list) and frees the window list 0x00044ac8 (ui_window_list_free_all). |
| `0x000004dc` | `void world_throw_starter_open_partner_list(void)` | Clears the 0x120-byte list-window descriptor 0x00041cf4 and fills it: +0x4c, +0x60, +0xac and +0xb0 = 1, position (0x32, 0x1e) at +0x58/+0x5a, +0x70 = -1, option bits in +0xc8..+0xca, +0xce = 0xf (rows shown, hypothesis medium), width 300 at +0xf0, row heights 0xe at +0xf2/+0xfa, item draw callback world_throw_starter_draw_list_item at +0xfc, row count 0x00041e14 at +0xcc and the heap at +0xc4; then ui_open_list_window. |
| `0x000005dc` | `int world_throw_starter_poll_partner_list(int *out_character, int *out_variant)` | Updates the selection list (ui_update_list_window(0x00041cf4)); once it returns something other than -1 resets the window and writes the choice: row 0 gives character -1 and variant 0 (the Random entry), row n gives 0x00041e18 + n * 4 and 0x00043470 + n * 4 (for -2 the code reads the words before the tables; the caller treats -2 as cancel). |
| `0x00000670` | `void * world_throw_starter_draw_partner_list(void *list)` | Draws the selection list window 0x00041cf4 (ui_draw_list_window) and returns the advanced display list. |
| `0x0000069c` | `void world_throw_starter_reset_partner_list(void)` | Resets the selection list window 0x00041cf4 (ui_list_window_reset). |
| `0x000006a8` | `void world_throw_starter_draw_list_item(void *list, uint index, int x, int y)` | Item draw callback of the selection list: opens an external font list on list, scale 0xc, shadow, black, and draws the name in slot (index & 0xffff) of the table 0x000051b4 at (x, y) with ui_list_window_draw_text; closes the font list. |
| `0x00000728` | `void ui_list_window_draw_text(int x, int y, void *text)` | Read from the twin (Ghidra shows a garbled body): system_font_draw_text(x << 6, y << 6, (480 - x) << 6, text), text from pixel x to the right screen edge. |

## Purpose and flow

Scene 0x1d, a developer launcher for the throw game. Entry `world_throw_starter_module_entry` registers start 0x00000038, end 0x00000164 (empty) and data 0x00041cd0 (no thread-attribute call). `world_throw_starter_scene_main` builds a list of partner candidates, shows a list window titled with the UTF-16 string at 0x000050f4 ("Select Partner", English debug text in the module), and on a choice fills the throw parameter block (partner, variant, thrower 0x1a/0x1b, 0, 1) and calls scene 0x1c with `system_scene_call(0x1d, 0x1c, 0)`; cancel returns with `system_scene_return(0x1d, 0)`. Row 0 is the built-in entry at 0x000051b4 ("Random") and yields partner -1.

Candidate filter (`world_throw_starter_init`): character-key rows 0..0x595 (`world_get_character_key`), excluding characters 0/1, variant 2 of 2 and 0x14, variant 1 of 0x24 and 0xc, and non-zero variants of 0x29, 0x27, 0x26, 0x25, 0x10, 8, 7; requires `world_character_exists` and `world_character_has_partner_deck(c, 0)`.

## Layout of the 200 KB file

The ELF has one loadable segment: file size 0x31cd0, memory size 0x44c00. Section headers: `.text` 0x748 bytes (the 7 own functions), `.sceStub.text` 0x30a0 (import stubs), `.rodata.sceNid` 0x1850, and `.data` 0x50ec..0x31cd0 (0x2cbe4 = 183,268 bytes). Only the first 0x5200 bytes of the segment contain non-zero data (code, stubs, NIDs, the two UTF-16 strings); the rest of `.data` is zero-filled storage, of which the code uses the name table 0x000051b4 (0x596 slots of 0x40 bytes, up to 0x0001b734). The remaining zeroed `.data` (0x0001b734..0x00031cd0) has no reference in the code read. `.bss` 0x31cd0..0x44c00 holds the 64 KB heap (0x00031cd0), scene data 0x00041cd0, the list window 0x00041cf4, the id/variant tables 0x00041e18 / 0x00043470 and the window list 0x00044ac8. So the module's size is zero-initialised arrays placed in `.data`, not hidden content (confidence high).

## Shared code

`ui_list_window_draw_text` (0x00000728) is a copy of the BOOT function. Twin lines for 0x00000000 (rel_shop shop_module_start) and 0x00000670 (ui_card_list_draw_sort_menu) only reflect a generic shape with module-specific constants; the functions got module names.

## Open questions

- Whether any menu reaches scene 0x1d (no caller was looked for outside this batch); it looks like a leftover developer launcher.
- The unreferenced zeroed `.data` range 0x0001b734..0x00031cd0.
