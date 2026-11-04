# `rel_charalist`

Module document of the 2026-11-04 round 6 (all game modules imported; `../modules.md`). English, evidence-based: the sections below come from reading every function of the module in the Ghidra decompilation; hypotheses carry a confidence.

| | |
| --- | --- |
| File | `PSP_GAME/USRDIR/gmodule/rel_charalist.prx`, 75,412 bytes, plain ELF (relocatable PRX) |
| Slot | id 0x0d |
| Exports → importers | `libcharalist_rel` (11) → labo, story, title |
| Role (catalogue) | Character list/profiles: `database/charalist.ehp`, `field/bustup/`, voice test, OSK (team name). |
| Runtime base | 0x09eee400 (PPSSPP export `duel-2026-10-26.sym`) |
| Registry ids | `rel_charalist:0x…` |
| Functions | 119 own functions, 120 documented in this round (ui 116, save 2, deck 1, shop 1); tables in `../functions/<group>.md`, section `rel_charalist` |

## Key functions (largest)

| Address | Prototype | Summary (first sentence) |
| --- | --- | --- |
| `0x09eee428` | `void * ui_draw_character_portrait_image(void *list, uint character, int x, int y, int scale, int offset, int inset, void *face_gim, void *body_gim)` | Copy of the rel_duel_draw portrait drawer: nothing when a GIM is NULL; characters 0x79-0x8d and those whose world byte 9 is 5 use a fixed 0x33 x 0x54 tile of body_gim (column/row per id); others use world_get_character_model_ids (face index, body column, palette) for a 0x33 x 0x40 body tile and a 0x33 x 0x32 face tile at palette level, scaled by scale percent. |
| `0x09eeeae0` | `int ui_charalist_update_ex(int force_close)` | State machine on +0x02 (force_close jumps to state 8 once past state 1): 0 waits for charalist.ehp (ui_charalist_poll_resources), builds the lists, fades in, prepares the menu bar block 0x09efcea0 (EHF 4, frames 0-0x1df), starts track 2 in modes 0/1 and saves the volume setting; 1 waits for the fade, then 2 (mode 5) or 3; 2 ui_charalist_update_notice; 3 ui_charalist_update_list (not when force_close); 4 ui_charalist_update_profile; 5 waits 0x11 frames and fades out; 6 after the fade opens the partner confirm page (mode 3, not cancelled) as state 7, else 8; 7 runs it (result 3 back to state 0, 2 to state 8); 8 frees the lists and returns 1 (chosen) or 2 (cancelled, bit 0 of +0x30). |
| `0x09eef3ac` | `void ui_charalist_draw(void)` | Draw export: clears layer 0 to black; outside states 0 and 8 sets the 2D state on layer 4 and either draws the partner confirm page (state 7) or the list screen: menu bar EHF, header bar (modes 0/1, list 12 px lower), tab panel (0x22, y, 0x19c, 0xf9), scroll bar, up to four rows (0x38 px apart), then the profile (state 4: dim by open animation and bust-up) or the cursor frame, and in state 2 the notice window; then the fade on layer 5. |
| `0x09eef7b0` | `void * ui_charalist_draw_tab_panel(void *list, int x, int y, int width, int height)` | Draws the list panel frame (resource 0x1002, 6 x 6 corners, palette row = tab * 0x20) and the three tab headers splitting width, the current tab (+6 & 3) white, others grey and lower with a scissor, labels card_db_get_dictionary_word(resource 0x1020, 0x3f + tab). |
| `0x09eefe04` | `void * ui_charalist_draw_row_body(void *list, int x, int y, void *entry)` | Draws a 12-byte list entry: background, the list number (+2 & 0x3ff, swprintf), two labels (dictionary 0xc and 4), the character name of the current variant, the category bar (byte +0x20 of the record, or the entry byte for simple entries), and in a 0x28 scissor either the portrait (simple entries: resources 0x1006/0x1007) or the face icon from world_get_character_byte_3f (highlighted while it is the chosen one in state 5) plus left/right arrows to the neighbouring variants. |
| `0x09ef0624` | `void * ui_charalist_draw_cursor_frame(void *list, int x, int y, int width, int height)` | Draws the selection frame (resource 0x1003 corners and edges) around (x, y, width, height), growing by 2 px every other 8 frames (frame counter bit 3). |
| `0x09ef0df4` | `void * ui_charalist_draw_scrollbar(void *list, int x, int y, int height, int position, int visible, int total, uint frame)` | Draws a vertical scroll bar (resource 0x1003): track, thumb of length visible * (height - 2) / total (at least 10) at position, thumb style alternating with frame bit 0, and up/down arrows shown when scrolling is possible, pulsing with the frame rate. |
| `0x09ef1634` | `void * ui_charalist_draw_voice_bar(void *list, int index)` | Draws the voice test bar (resource 0x1008, rising with the open animation), blinking left/right arrows when index can move within the count +0x68, and, unless voice banks are loading, the number index + 1 and the dictionary word table 0x09efbc2c[voice list 0x09efcd6a[index]]. Returns the list pointer. |
| `0x09ef1bcc` | `void ui_charalist_build_lists(void)` | Builds the three tab lists: for characters 2-0x8e that are listed (ui_charalist_is_character_listed), counting each as list number 1, 2, ..., keeps those with at least one variant unlocked for the mode (save_test_character_flag_bit3 in modes 0/1, bit0 in mode 2, bit1 in modes 3/5, byte1_bit0 in mode 4) and appends (number, id) to tab 0 (category 2), tab 1 (category 0) or tab 2 (others) by world_get_character_category; allocates the 12-byte entry arrays (+0x1c[3]) and fills tabs 0/1 with profile entries and tab 2 with simple entries, storing the counts in +0x16[3]. No return value. |
| `0x09ef1f2c` | `void ui_charalist_update_list(void)` | List input (state 3). |
| `0x09ef2684` | `void ui_charalist_update_profile(void)` | Profile page (state 4) of the current entry: polls voice bank loading (bit 0 of +0x60), ramps the music volume (+0x66: 1 down to a third, 2 back up, over 12 frames); sub-state 0 measures the text, then (record byte +1 bit 1 and no sound playing) loads the voice banks and builds the voice list; 1 waits 2 frames; 2 runs the open animation +0x4a to 12; 3 handles input: cancel closes (voices stopped, banks released, sound 0x7a06, volume restored), SELECT-like bit 0x8000 starts a pose switch, the analogue y (pad +0x14) and up/down scroll the text +0x28 within +0x2c; with a voice list, confirm plays voice list[+0x14] (and queues its second sound), L/R/left/right move by 10 or 1; 4 runs the close animation and returns to state 3. |
| `0x09ef3198` | `uint ui_charalist_fill_profile_entries(void *entries, void *pairs, uint count)` | For each (number, character) pair whose character exists (world_find_character), allocates a 0x44-byte profile record: byte 0 bits 0-2 variant count and 3-5 current variant, +2 world byte +0x3f, then per unlocked variant v (same mode flags as ui_charalist_build_lists) +4[v] variant number, +0xc[v] world_get_character_word_0c (bust-up name), +0x20[v] world byte 9, +0x28[v] the dictionary text 0x09efbf50[character * 4 + v] (resource 0x1020) and +0x3c[v] the character id; writes the entry (+0 id, +2 number, flag bit 2 clear, +8 record). |
| `0x09ef3560` | `void ui_charalist_switch_bustup_pose(void)` | Moves the bust-up body and mouth EHFs to the start of the next 15-frame group (wrapping at the frame count; one group skipped for character 4 variant != 0); for characters 0x26 and 0x25 with a voice list it also switches the record's voice key (+0x3c) and the selected variant at given frames and reloads the voice banks and list. |
| `0x09ef40f8` | `void * ui_charalist_get_bustup_ehf(void *entry, uint which)` | Returns body.ehf (which 0) or mouth.ehf (1) of the entry's current bust-up: when it is the loaded one (key 0x09efe654) returns the cached pointer; when its file is cached, gzip-decompresses it into 0x09efe658, binds it, finds body.ehf/mouth.ehf (play range 0-1) and updates the key; otherwise starts loading field/bustup/<name> (name from the record +0xc[v] or world_get_character_word_0c) into the cache 0x09efcff8 and returns NULL. Side effects: heap, cache, file load. |
| `0x09ef6558` | `int ui_update_osk_input(int layer)` | Copy of rel_deck's keyboard step: draws the fade, polls the dialog, on completion shuts it down, copies the text back doubling "$", calls the callback, fades in; returns 1 when finished. |

Batch L, packs 02-05: 117 of the 118 functions of `rel_charalist` (base `0x09eee400`, absolute addresses). `0x09eef354` (export `558dbb5f`, 8 bytes) was not in the packs.

## Purpose and flow

The character list ("character profiles") used by the world, the title menus (partner and opponent pick, wireless partner) and `rel_labo`. Exports: `ui_charalist_open(mode, heap)`, `ui_charalist_update` (= `update_ex(0)`), `ui_charalist_update_ex(force_close)`, `ui_charalist_draw`, `ui_charalist_close`, the selection getters and three headless helpers.

Modes (low nibble of state byte `0x09efcd00`; selects the unlock flag per character variant):

| Mode | Unlock flag | Behaviour |
| --- | --- | --- |
| 0, 1 | `save_test_character_flag_bit3` | Profile viewer: own music (bank 0x2c8, track 2), confirm opens the profile page (state 4) |
| 2 | `bit0` | Headless (random pick, select by index) |
| 3 | `bit1` | Partner pick: after the choice, the partner confirm page with team name |
| 4 | `byte1_bit0` | Pick |
| 5 | `bit1` | Pick preceded by a notice window (state 2) |

`ui_charalist_update_ex` states (`+0x02`): 0 load `database/charalist.ehp` and build lists, 1 fade in, 2 notice, 3 list input, 4 profile page, 5 delay, 6 fade out, 7 partner confirm, 8 free and return 1 (chosen) or 2 (cancelled). The update returns 0 while running.

## Key structures

- State block `0x09efcd00` (0x2f0 bytes): `+0x02` state, `+0x04` sub-state, `+0x06` tab (bits 0-1), `+0x08[3]` first visible row, `+0x0e[3]` cursor row, `+0x14` voice index, `+0x16[3]` entry counts, `+0x1c[3]` entry arrays, `+0x28/+0x2c` profile text scroll and limit, `+0x30` bit 0 cancelled, `+0x34/+0x38` selected character/variant, `+0x3c` heap, `+0x40/+0x44` FPL id/memory (8 MB when no heap is passed), `+0x4a` profile open animation (0-12), `+0x4c` bust-up slide, `+0x4e/+0x4f` pose-switch fade and alpha, `+0x50`-`+0x5c` loaded voice banks, `+0x60` bit 0 banks loading / bit 1 second sound pending, `+0x64` saved music volume, `+0x66` volume ramp, `+0x68` voice count, `+0x6a` voice index list, `+0x1a0` menu bar block (archive + EHFs at `+0x124`), `+0x1a4` notice list window.
- List entry (12 bytes): `+0` character id (10 bits), `+2` list number (10 bits; characters numbered 1.. in id order over all existing characters), `+3` bit 2 = simple entry (third tab), `+8` profile record pointer (or the world byte 9 for simple entries).
- Profile record (0x44 bytes): byte 0 bits 0-2 variant count, bits 3-5 current variant; byte 1 bit 1 voice test enabled; `+2` world byte `+0x3f`; per variant `+4[v]` variant number, `+0xc[v]` bust-up file name (world word `+0xc`), `+0x20[v]` world byte 9 (category bar kind), `+0x28[v]` profile text (dictionary word from table `0x09efbf50`), `+0x3c[v]` voice key.
- Tabs: 0 = world category 2, 1 = category 0, 2 = all others (no profile).
- Resource table `0x09efc13c`: 9 entries of 12 bytes (u16 id, cached member, name format with a language letter); ids `0x1002`-`0x1008` are GIMs, `0x1020` the text table used with `card_db_get_dictionary_word`.
- Bust-up cache `0x09efcff8`: `0x8f` characters x 5 variants (`+4` file buffer, `+0xb30` size); the decompressed current bust-up `0x09efe658` with `body.ehf` (`0x09efe65c`) and `mouth.ehf` (`0x09efe660`), key `0x09efe654` (id, variant).
- Partner confirm work area `0x09efe664` (0x1a0 bytes): `+0` heap, `+4` archive, `+0x10` keyboard mode, `+0x14` page state, `+0x20/+0x24` partner, `+0x28` list window, `+0x150[2]` menu bars, `+0x170[6]` GIMs, `+0x19c` result (2 accept, 3 cancel).

## Files

- `database/charalist.ehp` (root 3): resources by id (language-specific names), `strTbl_<l>.bin` confirm texts, `mini_result_<l>.bin` notice texts, `m_menu_bar01.ehf` menu bars, `d_menu01.gim`.. confirm GIMs, `common_head.gim` / `common_body.gim`, and `<prefix><cutin name>_voiceidchgtbl.bin` per character (presence enables the voice list).
- `field/bustup/<name>` (root 3): gzip-compressed EHP with `body.ehf` and `mouth.ehf`.
- Voice test: four "extra" banks from `audio_get_voice_extra_bank` + the character's voice bank; voice index < 5 maps into the extra banks. The 0x86-entry voice table `0x09efbd38` (sound number, second sound) and the name table `0x09efbc2c` are module data.

## Interfaces

Save: `save_test_character_flag_bit0/1/2/3`, `byte1_bit0`, `save_get_duel_count_vs(kind 0-2, character)` (three counters per character on each row), `save_set_team_name`, `save_set_partner`. World: `world_get_character_category`, `world_count_character_variants`, `world_find_character`, `world_get_character_byte_09/3f`, `world_get_character_word_0c`, `world_get_character_cutin_name`. Copies of other modules' code: the portrait drawer of rel_duel_draw, the atlas helpers and face/body drawer of rel_duel_mgr's versus screen, rel_deck's OSK keyboard, rel_shop's resource binary search.

Partner confirm (mode 3): shows player, partner and team name; the default team name is player name + separator + partner name; confirm opens the keyboard (title text `0x45`, 17 characters), START accepts if the name is not blank (otherwise warning text `0x44`), cancel goes back to the list (state 0). Accept writes `save_set_partner`.

## Name mismatches

- `ui_charalist_e11636ec` -> `ui_charalist_pick_random_character` (H)
- `ui_charalist_953239e8` -> `ui_charalist_build_lists_headless` (H)
- `ui_charalist_df67151f` -> `ui_charalist_select_entry_by_index` (H)
- `ui_charalist_558dbb5f` -> `ui_charalist_free` (M; body not in the pack, a caller of `ui_charalist_free_lists`)

Twin lines rejected or renamed: `0x09ef4454` (same shape as `shop_on_archive_loaded`, own block -> `ui_charalist_on_archive_loaded`), `0x09ef4618` (same code as `ui_duel_versus_free`, own block -> `ui_charalist_free_partner_confirm`), `0x09ef5f5c` (code of `ui_draw_level_badge_text_fit`, name already used by `0x09ef02b8`).

## Open questions

- Voice test reachability: the list input clears bit 1 of profile byte +1 when a profile opens, and nothing in this module sets it, so the voice list (and the voice bar) may never appear (hypothesis, confidence medium). Check in PPSSPP.
- Mode 3 cancel does not set the cancelled bit, so the confirm page opens with the old selection (possibly -1). Verify at runtime.
- Meaning of the category bar kinds 0-4 (world byte 9) and of the three duel counters (`kind` 0-2).
- Which callers use modes 1, 4 and 5 (rel_title/rel_story/rel_labo call sites).
- The 8-byte export `0x09eef354` should be read to confirm it only tail-calls `ui_charalist_free_lists`.
- Export NID 0x558dbb5f (0x09eef354) is a tail jump to `ui_charalist_free_lists`.

## rel_underground, rel_duelrecord, rel_tutoriallist, rel_select_card, rel_quiz, rel_decktutorial
- The 12-byte measure wrappers are `system_font_split_lines(width, text, 0, 0)`; the 8-byte fit-scale wrappers are `system_font_fit_scale_to_width(max_width << 6, text)`.

## Name mismatches
- rel_decktutorial 0x00019f78: given `deck_tutorial_stub_draw_type_line`; the disassembly shows the rel_deck wrapper `ui_card_info_draw_text_fit_width` (j system_font_draw_text_fit_width, t0 = -1), so that name is used.
- rel_select_card 0x00013b88: given `deck_select_card_stub_13b88`; renamed `deck_select_card_fit_text_scale_px` (j system_font_fit_scale_to_width, a0 <<= 6).
- rel_charalist 0x09eef354: header name `ui_charalist_558dbb5f` (NID) replaced by `ui_charalist_free`.
