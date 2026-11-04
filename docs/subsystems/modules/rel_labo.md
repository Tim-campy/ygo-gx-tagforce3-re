# `rel_labo`

Module document of the 2026-11-04 round 6 (all game modules imported; `../modules.md`). English, evidence-based: the sections below come from reading every function of the module in the Ghidra decompilation; hypotheses carry a confidence.

| | |
| --- | --- |
| File | `PSP_GAME/USRDIR/gmodule/rel_labo.prx`, 37,428 bytes, plain ELF (relocatable PRX) |
| Slot | scene 9, id 0x17 |
| Exports → importers | — |
| Role (catalogue) | Hub (8 function starts) that loads and unloads the library tools above. Has a voice-test debug view (`ChrID`, `VOICE` formats). |
| Runtime base | unknown; imported at image base 0x0, so addresses are module offsets |
| Registry ids | `rel_labo:0x…` |
| Functions | 15 own functions, 15 documented in this round (ui 15); tables in `../functions/<group>.md`, section `rel_labo` |

## Key functions (largest)

| Address | Prototype | Summary (first sentence) |
| --- | --- | --- |
| `0x00000000` | `int ui_labo_register_scene(void)` | Module entry point: registers the scene with system_scene_register(0x34 start = ui_labo_scene_main, 0x974 end = ui_labo_scene_end, 0x747c) and returns 0. |
| `0x00000034` | `void ui_labo_scene_main(void)` | Scene start callback of the "labo" debug hub: hides the loading overlay, installs the frame callback ui_labo_draw_frame (system_scene_set_frame_callback(9, 0x97c, 0xa04)), fades in and loops per frame on the state 0x7460 (sub-state 0x7464): state 1 is a 12-item menu (cursor 0x7468, up/down wrap); cancel fades out to state 0xe; confirm on item 11 loads the voice test (state 0xd), on items 0-10 loads the tool's library module id 0x60dc[item] with system_module_load_ex(id, 4, &1, 0, 0), waits for system_module_all_loaded and enters state item + 2; states 2-0xc call the tool's start export once (sub-state 1) and its update export each frame (sub-state 2) until it returns non-zero, then unload the module, fade in and return to state 1: 2 ui_password_start/update, 3 ui_select_card_open(0, 0, 0, 0), 4 ui_select_card_open(2, 0, 0, 0), 5 ui_conv_machine, 6 deck_swap_start(duel set-up buffer filled with member 0's deck and the save card-list states, save_get_card_list_count, set-up + 0xc0, 1), 7 ui_card_album_start(0, 0), 8 ui_charalist_open(0, 0), 9 ui_duel_record_start(0), 0xa deck_limit_list_start(0, 0), 0xb ui_tutorial_list_start(0, 0), 0xc ui_charalist_open(3, 0); 0xd the voice test until it returns non-zero; 0xe when the fade is done clears the frame callback, shows the loading overlay and returns with system_scene_return(9, 0). |
| `0x00000974` | `void ui_labo_scene_end(void)` | Empty function (jr ra). |
| `0x0000097c` | `void ui_labo_draw_frame(void)` | Frame callback: calls the draw function of the current state from the table 0x6110[state] (the menu, the voice test and the tools' draw exports), or, when the entry is the module's offset 0 (no drawer), clears layer 0 to black. |
| `0x00000a04` | `void ui_labo_frame_leave(void)` | Empty function (jr ra). |
| `0x00000a0c` | `void ui_labo_draw_menu(void)` | Menu drawer: clears layer 0 to 0xff404000, draws on font layer 4 at scale 10 in white the menu title (string 0x644c) and the 12 item names (0x40-byte ASCII strings from 0x614c) at y 0x18 + 0xc x i with system_font_printf, a cursor marker at the cursor row blinking with bit 3 of the frame counter, and the fade on layer 4. |
| `0x00000b50` | `void ui_labo_load_voice_test(void)` | Clears the 0x14-byte voice-test block 0x7488, sets its archive pointer 0x7498 = 0x74a0 (module memory) and reads "labo/voicetest.ehp" from root 3 (USRDIR) there synchronously (container_get_file_size, container_read_file_from_start). |
| `0x00000bb4` | `void ui_labo_load_voice_banks(void)` | For the voice-test character 0x748a and variant 0x748c releases all sound banks and loads the four extra voice banks audio_get_voice_extra_bank(...) + 0..3 and the voice bank audio_get_voice_bank(...) + pack 0x748e. |
| `0x00000c3c` | `int ui_labo_update_voice_test(void)` | Voice-test input over 4 rows (row 0x7488: 0 character 0x748a below 0x7f, 1 variant 0x748c below 4, 2 pack 0x748e below 3, 3 voice index 0x7490 below 0x9a for characters under 0x2e, else 0x39): confirm plays the selected voice (audio_start_sound_tracked(ui_labo_get_voice_sound_id())); cancel returns 1; triangle loads the banks (ui_labo_load_voice_banks); L sets the row's value to 0, R to its maximum; left/right (repeat) decrement/increment within the range; up/down cycle the row 0-3. |
| `0x00000f20` | `void ui_labo_draw_voice_character(void)` | When the voice-test character 0x748a is above 1 and exists with variant 0x748c (world_character_exists), draws its name (world_get_character_name_string(character, variant, 0)) at (0xc5, 10). |
| `0x00000f98` | `void ui_list_window_draw_text(int x, int y, void *text)` | Same code as BOOT ui_list_window_draw_text: system_font_draw_text(x << 6, y << 6, (480 - x) << 6, text). |
| `0x00000fb8` | `void ui_labo_draw_voice_line(void)` | For an existing character above 1: builds a base name, for named characters a fixed prefix (0x73d4) + world_get_character_cutin_name(character, variant), for generic ones (world_character_is_generic) a formatted name from (audio_get_voice_bank - 0x1de) / 7 + 0x32 (format 0x73d8); finds the members "<base>voiceidchgtbl.bin" and "<base>wordstbl<lang>.bin" (formats 0x73e4 and 0x73fc, language letter from "jegfis") in the voice-test archive; when both exist splits the current voice sound id (ui_labo_get_voice_sound_id) into bank and index (audio_split_voice_sound_id), looks up the word number with system_lookup_offset_table_u16(0, bank, index, voiceidchgtbl), prints number - 1 at (100, 0x5a) and draws that dictionary word of the word table as a text box (0x32, 0x78, 0x17c, 0x82). |
| `0x0000119c` | `void ui_window_draw_text_box_px(int x, int y, int width, int height, void *text)` | Pixel wrapper, same code as BOOT ui_window_draw_text_box_px: tail-calls system_font_draw_text_box(x << 6, y << 6, width << 6, height << 6, text, -1, 0). |
| `0x000011b8` | `void ui_labo_draw_voice_test(void)` | Voice-test drawer: white text at scale 14: a cursor marker at row 0x7488, then with system_sprintf/system_font_printf the character id (3 digits), variant, pack name (string table 0x64dc[pack]) and voice index with its name (string table 0x6db8 for characters under 0x2e, else 0x72e8), followed by the character name (ui_labo_draw_voice_character), the voice line (ui_labo_draw_voice_line) and a footer line at (10, 0xfa). |
| `0x00001338` | `int ui_labo_get_voice_sound_id(void)` | Sound id of the voice-test selection: for voice index 0x7490 below 5, the first sound of the character's extra voice bank (audio_get_voice_extra_bank) + index; otherwise the first sound of bank audio_get_voice_bank(character, variant) + pack 0x748e, + index - 5. |

## Purpose and flow

Scene 9 (id 0x17): "Labo", a developer hub (its menu title string reads as a debug menu) that loads each library tool on its own. Entry registers start 0x34 and end 0x974; the frame callback 0x97c calls a per-state draw function from the table 0x6110 (the tools' draw exports, the menu and the voice test) or clears the screen.

Menu (state 1, 12 items, names are 0x40-byte strings at 0x614c): items 0-10 load a library module whose id comes from the table 0x60dc (`system_module_load_ex(id, 4, &1, 0, 0)`), call its start export once and its update export every frame until it returns non-zero, then `system_module_unload`. Item to tool: 0 password, 1 card picker mode 0, 2 card picker mode 2, 3 conversion machine, 4 deck swap (with the duel set-up buffer filled from member 0's deck and the save card-list states), 5 card album, 6 character list mode 0, 7 duel record, 8 limit list, 9 tutorial list, 10 character list mode 3. Item 11 is the voice test. Cancel returns to the caller (`system_scene_return(9, 0)`). This answers part of the modules.md open question "who loads the tools in rel_labo": the ids are table-driven, not computed.

## Voice test

Loads `labo/voicetest.ehp` (root 3) synchronously into module memory at 0x74a0. Block 0x7488: row, character (below 0x7f), variant (below 4), pack (below 3), voice index (below 0x9a for characters under 0x2e, else 0x39). Voice indexes 0-4 come from the character's extra voice bank (`audio_get_voice_extra_bank`), the rest from `audio_get_voice_bank(character, variant) + pack`, minus 5. The archive holds per-character tables named from a base name (a fixed prefix + `world_get_character_cutin_name` for named characters, a formatted name from `(voice bank - 0x1de) / 7 + 0x32` for generic ones): `<base>voiceidchgtbl.bin` (a u16 offset table read with `system_lookup_offset_table_u16(0, bank, index, table)` that maps a voice sound to a word number) and `<base>wordstbl<lang>.bin` (a dictionary with the spoken line's text per language). This is the voice-to-subtitle mapping; the port's extractor should handle these two member kinds (format strings at 0x73e4 and 0x73fc).

## Open questions

- Contents of the module-id table 0x60dc and the draw table 0x6110 (confirm the item-to-module mapping above against the ids in modules.md).
- Is `labo/voicetest.ehp` the only place the voice-id and word tables exist, or does the duel use the same tables from another archive?
