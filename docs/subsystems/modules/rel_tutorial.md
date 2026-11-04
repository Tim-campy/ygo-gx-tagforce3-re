# `rel_tutorial`

Module document of the 2026-11-04 round 6 (all game modules imported; `../modules.md`). English, evidence-based: the sections below come from reading every function of the module in the Ghidra decompilation; hypotheses carry a confidence.

| | |
| --- | --- |
| File | `PSP_GAME/USRDIR/gmodule/rel_tutorial.prx`, 78,500 bytes, plain ELF (relocatable PRX) |
| Slot | id 0x0b |
| Exports → importers | `libtutorial_rel` (13) → duel_mgr |
| Role (catalogue) | Scripted duel tutorial: `d_tutorial/tutorial/tuto_field_%02d.ydq`, `tuto_cmd_%02d.bin` (`docs/formats/tutorial.md`). Imports duel_eng and duel_draw. Base unknown (not in any symbol export); names at module offsets in `re/names-rel_tutorial.csv`. |
| Runtime base | unknown; imported at image base 0x0, so addresses are module offsets |
| Registry ids | `rel_tutorial:0x…` |
| Functions | 185 own functions, 183 documented in this round (duel_core 162, ui 21); tables in `../functions/<group>.md`, section `rel_tutorial` |

## Key functions (largest)

| Address | Prototype | Summary (first sentence) |
| --- | --- | --- |
| `0x00000000` | `void duel_core_tutorial_msgwin_open_list_window(int slot_index, void *win, void *slot)` | Fills the 0x120-byte list window descriptor win (0x12200 + slot * 0x120) for message slot slot_index and opens it with ui_open_list_window. |
| `0x00000440` | `void * duel_core_tutorial_draw_question_item(void *list, uint item, int x, int y)` | List item draw callback of the question window: the question text is the slot-6 text 0x1116e, line 0 the caption and lines 1..n the choices. |
| `0x000007c0` | `void * duel_core_tutorial_msgwin_update_list(void *list, int slot_index, void *slot)` | Per-frame callback of slots 6-9 (slot +0x41c = 0x7c0): state 3/4 opens the list window (duel_core_tutorial_msgwin_open_list_window) and goes to 5 (slots 6, 8, 9) or 6 with the active flag cleared (slot 7, the hint stays up); state 5 updates the window: slot 6 (question) on cancel (-2) goes to 0, on a choice calls duel_core_set_dialog_answer(choice + 1) and goes to 0; slots 8/9 go to 7 when the window is shown (byte +0xe9 = 3) and confirm is pressed; state 7 starts closing (ui_list_window_start_close), state 8 resets the window once it reports closed (+0xe9 = 6) and clears the slot. |
| `0x00000f58` | `void duel_core_tutorial_msgwin_draw_all(void)` | Per-frame update and draw of the message windows on layer 9: activates a pending speaker slot, calls each slot's callback (+0x41c) for slots 0-9, updates the shared message window, then draws the list windows of slots 6-9 whose state is 3..8 (slot 9 first draws the large-window background from GIM 0x12ed8 pieces; slots 7/8 use font end-y 0xc0 in Japanese and draw the card icon of slot +0x40e at the window centre once the window is shown), the shared message window (ui_field_draw_message_window) and the faces of speaker slots in states 3..7. |
| `0x000017d8` | `void duel_core_tutorial_open_quit_prompt(void)` | Opens the in-lesson prompt reached with START: clears and fills the list window descriptor 0x12da8 (title system message 0x1f, two items, width 0xf0), opens it, centres it on the 480 x 272 screen (y + 0xf), sets bit 0 of 0x12ec8 (prompt open) and copies the old prompt flag 0x12da0 into bit 1, sets the flag to 1 and the duel setup buffer word +0x854 to 1. |
| `0x00001e80` | `void duel_core_tutorial_draw_highlight_mask(void *list)` | Spotlight effect: clears the stencil, draws the current rectangles of highlight records 0 and 1 (0x12f10.. and 0x12f1c.., when their flag byte is set) into the stencil with colour 0, then, if either is active, draws a full-screen 0x1e0 x 0x110 quad in 0xc0000000 where the stencil is clear (darkening everything outside the highlights); clears the stencil again and disables stencil testing. |
| `0x00002094` | `void duel_core_tutorial_animate_highlights(void)` | Steps highlight records 0 and 1 (0x12ef8, 0xc bytes each: state byte, target x, y, right/width, bottom/height shorts at +2..+8, step +0xa) and mirrors the state into the current-rectangle records at 0x12f10: state 1 (opening) shrinks the rectangle from the full 480 x 272 screen to the target in 10 steps, then state 2 and the target is copied; state 3 (closing) grows it back in 10 steps and then clears the record. |
| `0x000028ac` | `int ui_field_update_message_window(void)` | Copy of rel_field's per-frame step of the message window (state 0x17dac: 0 hidden, 1 sliding in, 2 shown, 3 sliding out; slide parameter 0x17db0 with step k + k * t, k at 0xf548): in state 2 advances the typewriter (once per line at text speed 2), ticks the idle counter and, when waiting for input (0x17e98) and not locked (0x17f10), confirm (or R + confirm every third frame when save_test_progress_flag_e9_bit4) speeds the page up, turns the page (sound 0x7a0b) or acknowledges the finished text (done flag 0x17ef8, sound 0x7a0b); an empty text is done at once. |
| `0x00002be0` | `void ui_field_draw_message_window(void **list_ptr)` | Copy of rel_field's draw of the message window when visible: its window list 0x17db4 (ruby off), each revealed line through a scissor and the page text as one text box (ui_field_draw_message_line_text) shifted by page * lines * (line height + 3), and, when waiting for input with the text printed and the window still, the blinking continue cursor from GIM 0x17f08 (cell (idle counter 0x17f0c / 10) & 1, source 0xf538-0xf53e, offset 0xf540/0xf544). |
| `0x000039b4` | `int duel_core_tutorial_filter_input(int side, int location, int index, int code)` | Player action validator (registered with ui_set_player_action_validator): reads the card under the cursor; returns 1 (allowed) for lessons >= 20 or when flag bit 1 of 0x17f44 is set, 0 for code 10, and otherwise allows only the awaited wait_input action in state 4 (kind 0x17f3a, card 0x17f3c or 0 = any): kind 1 code 4, 2 code 13 + card, 3 code 0 (state 2), 4 code 11 (state 2), 5 code 6, 7 codes 8/9/5, 8 code 11, 9 code 4 (state 1), 10 code 3, 11 code 7, 14 codes 2/11, 15/16 code 11 (any card), 17 code 11, 19 code 3 (state 1); most matches hide the hint and clear a pending on_event 0x42 handler. |
| `0x00003df8` | `int duel_core_tutorial_on_ui_event(uint event, uint arg1, uint arg2, int arg3)` | Tutorial handling of a duel UI event (see tutorial.md "Hooks and UI events"): lessons >= 20 forward; a matching on_event handler (0x17f3e/0x17f42) jumps to its label, state 1; in state 6 the awaited event (0x17f4a, argument 0x17f4c, minimum 0x17f4e for 0x36) resumes (state 1 for 4 unless arg1 = 7, 0x36 and 0x37; state 2 otherwise); UI event 0x36 with arg1 3 and arg3 < 2 is answered 0 (duel_core_set_dialog_answer) and swallowed unless flag bit 2 is set; in state 4 events 0x36/0x39/0x19/0x2f/0x22/0x2c/0x1c/5/0x1e/0x38 complete the matching wait_input kinds; event 0xd stores the attacker and target card ids (duel_core_get_attack_state, duel_core_get_slot_card_ref, duel_core_get_card_id_by_ref) in 0x17f52/0x17f54. |
| `0x0000473c` | `int duel_core_tutorial_exec_command(ushort *record)` | Executes tutorial command record[0] & 0x3fff (jump table 0xf608): 1 message, 2 hint, 3 hint off, 4 highlight (region record[2], side record[1], timer record[3], state 7), 6 goto, 7 if_answer, 8 question (line count = newlines), 9 show_card (1/2 from 0x17f50), 10 load_field, 11 wait, 12 wait_input, 13 set_turn (duel_core_set_turn_counter), 14 wait_event, 15 card_part, 16 on_event, 17/18 flag on/off (bit 3 also duel_core_tutorial_apply_setup_flag), 19 count_answer, 20 open_list (duel_core_submit_player_action(side, location, 0, 1), state 2). |
| `0x000054c4` | `void duel_core_tutorial_highlight_region(void *handle, int region, int side)` | Command 4: looks the screen rectangle of region 0-0x14 up in a coded table (most regions have one rectangle for side 0 and another for side 1; 8-0xe, 0x10, 0x13, 0x14 are side-independent) and starts highlight 0 with (x1, y1, x2 - x1, y2 - y1); region 0x11 stops the highlight instead, unknown regions use an empty rectangle. |
| `0x00005b78` | `void duel_core_tutorial_init(void *ui_event_forward)` | Resets the module: clears the cursor block, 0x12d88 (0x148 bytes), 0x18794 (0xc) and the language byte, binds the heap, stores the language (save_get_language & 7), loads the archive, stores ui_event_forward at 0x187a4 and registers the hooks (duel_core_set_ui_event_hook(duel_core_tutorial_ui_event_hook), ui_set_player_action_validator(filter_input), ui_set_card_action_auto_choose(duel_core_tutorial_card_action_auto_choose), duel_core_set_duel_flow_gate_hook(gate_duel_flow), ui_set_confirm_prompt_validator(on_answer)); resets the highlights, initialises the message windows, clears the end flag, saves the save option flags 0, 2, 3, 4, 5 (bits 5-7 of 0x12ec8, bits 0-1 of 0x12ec9) and setting b2 bits 1-2 (0x12ecc), then sets them all to 0 for the lesson. |
| `0x0000638c` | `void * duel_core_tutorial_draw_face_anim(void *list, void *anim, int x, int y)` | When anim is ready, draws its two EHF players (+8 eyes, +0xc mouth, hypothesis from the play ranges) at (x, y) with ui_ehf_draw and the frame time; when blinking is enabled (bit 6 of +0x11) counts +0x12 up to the random delay +0x14 and then plays frames base + 4..0xf, and on frame % 15 = 14 restarts with a new delay 0x5a + rand % 0xd2 and frames base..base + 1. |

Batch L, packs 00-02: all 161 own functions of `rel_tutorial` (module offsets, image base 0). The names already in `re/names-rel_tutorial.csv` / `docs/formats/tutorial.md` are kept; 30 of them got rows. 15 tiny stubs were skipped (empty decompilation or hidden register arguments).

## Purpose and flow

The module runs a scripted duel lesson on top of the normal duel engine and duel screen (see `docs/formats/tutorial.md` for the script and hook semantics, which this batch confirms). Besides the script interpreter it contains three self-contained layers that the format document does not describe yet:

1. **A copy of rel_field's message window** (`0x26b0`-`0x3630`, twins of `ui_field_*`): one typewriter window in the 0x180-byte block `0x17dac` (state `0x17dac`: 0 hidden, 1 sliding in, 2 shown, 3 sliding out; text `0x17e90`; done flag `0x17ef8`; wait-input flag `0x17e98`; three line records of 0x18 bytes at `0x17ea0`). The tutorial adds `duel_core_tutorial_place_message_window` (`0x300c`), which puts it at a fixed box without the slide.
2. **Ten message-window slots** at `0xf870` (stride `0x428`): `+0` index, `+4` state, `+8/+0xa` x/y, `+0xc` character, `+0xd` expression, `+0xe` 0x400-byte UTF-16 text, `+0x40e` icon, `+0x418` active, `+0x41c` per-frame callback, `+0x420` line count, `+0x424` caption height. Slots 0-5 are speaker windows drawn through the shared message window with a face (callback `0x624`), slot 6 the question list, 7 the hint, 8 the message, 9 a large window (callback `0x7c0`; list window descriptors at `0x12200 + 0x120 * slot`). Slot states: 0 closed, 1 pending, 2 placed, 3 open requested, 4/5 shown, 6 hint shown (inactive), 7 closing, 8 closed-wait. Script command 1 opens slot 8 at (0xa0, 0x5a), command 8 slot 6 at (0x14, 0x5a), command 2 slot 7 at (0xdc, 0). The scripts in TF3 never use slots 0-5 (character code = face_code / 100, expression = % 100): only `duel_core_tutorial_open_message` and `duel_core_tutorial_open_hint_window` call the setup, with slots 8, 6 and 7 (confidence high).
3. **A spotlight highlight** (`0x1e80`-`0x2314`, `0x54c4`, `0x57dc`): up to three 12-byte records at `0x12ef8` (state byte: 0 off, 1 opening, 2 shown, 3 closing; target rectangle shorts `+2..+8`; step `+0xa`), animated in 10 steps from the full 480 x 272 screen, and drawn on layer 9 as a stencil mask that darkens everything outside (colour `0xc0000000`). Command 4 uses a coded rectangle table per screen region 0-0x14 and side (0x11 = off); command 15 a table per card part 1-9. The "marker" companions (`0x57bc`, `0x57c4`, `0x57cc`) are stubs returning 1/1/0.

Frame flow: `duel_core_tutorial_update` -> `duel_core_tutorial_update_frame` (`0x5f74`): quit prompt (`0x5de0`) or, once the fade is done, `duel_core_tutorial_update_overlay` (`0x5ec4`: START opens the prompt; otherwise highlight layer + message windows), then the fade on layer 10.

Quit prompt: START (pad pressed bit 8) opens a two-item list window (`0x12da8`, title system message `0x1f`); item 2 calls `duel_core_tutorial_on_duel_end(1)` (fade out, `duel_core_tutorial_is_finished` then reports 1). While it is open `duel_core_tutorial_is_busy` returns 1 (bit 0 of `0x12ec8`).

## Key structures

- State block `0x17f2c` (0x834 bytes cleared by `start_lesson`): as in tutorial.md; `0x17f60` holds the current text line (UTF-16), `0x17f48` the hint line.
- Cursor block `0x18764` (0x18 bytes): `+0` card under the cursor, `+4/+8/+0xc` cursor side/zone/index, `+0x10` side of the hand list.
- Object handles `0x1877c`-`0x18790` (message, hint, highlight, marker, card view, list): only passed as `this`; the methods ignore them.
- Heap: `0x17da0` = `system_duel_draw_get_heap()`; every module allocation (`0x2684`) and free (`0x2694`) goes there.
- Text escapes: `duel_core_tutorial_escape_text` (`0x626c`) turns each `@` of a `tuto_text` line into the font colour code `$C` (so `@2`/`@0` become `$C2`/`$C0`); `duel_core_tutorial_expand_placeholders` (`0x2550`) expands `$0` (player name), `$1`-`$4` (ATK of the card `0x17d9a`: full, halved, halved + 200, halved + 700) and `$$`.
- Archive reader: a 0x84-byte "file" record (`0x59b8`-`0x59f8`, path + position) that reads straight from the bound `d_tutorial/tutorial.ehp`; the position is not advanced by a read.

## Files

- `d_tutorial/tutorial.ehp` (root 3) only, as documented. `card_icon02.gim` from the duel archive 0x80001 (icons in slots 7/8). `tuto_duel01.gim`, `window02.gim`, `tuto_bigwin01.gim`, `tuto_duelimg%02d.gim` come from the never-set pointer `0x17da4` (dead, as tutorial.md says); the six 8-byte entries `0x1554`-`0x157c` are `draw_lesson_image` with image numbers 1-6.
- Music: track `0x20` with fade at lesson start; `audio_stop_sounds_bgm_arg(600)` at shutdown.

## Interfaces

- Save settings: `duel_core_tutorial_init` saves save option flags 0, 2, 3, 4, 5 and `save_get_setting_b2_bits1_2`, clears them for the lesson, `duel_core_tutorial_cleanup` restores them.
- `duel_core_tutorial_setup_duel_draw` (`0x6100`) builds a 0x858-byte duel setup and a 0x74-byte draw setup on the stack (`duel_setup_load_decks`, `ui_duel_draw_setup`, loading poll, `ui_duel_draw_begin`).
- Command 20 calls `duel_core_submit_player_action(side, location, 0, 1)` (named now; tutorial.md says `0x09dcf950`).
- Command 19 counts the local side's hand cards whose `card_db_get_frame` is 2 (tutorial.md says "0x0885f864(id) returns 2").
- Script end (op 0) sets word `+0x2cac` of `duel_core_get_player_blocks()` to 1 (meaning unknown).

## Corrections to existing docs

- `duel_core_tutorial_is_busy` also returns 1 while the quit prompt is open (bit 0 of `0x12ec8`), not only by lesson/state.
- `duel_core_tutorial_init_graphics` is mainly the message-window initialiser (slots, shared window `ui_field_init_message_window(heap, 0x27, 400, 0xe, 1, 3)`); the GIM lookups are the dead part.
- `0x678c`, called by `escape_text`, is an sceCcc import wrapper (`0x670c` is `sceCccDecodeUTF16` per the auto names).

## Name mismatches

None of the existing names is wrong. Twin lines rejected as false positives (tiny functions around different local callees): `0x14dc` / `0x5b2c` (not `ui_ehf_get_frame_rate`), `0x2654` (not `system_sample_hcount`), `0x2684`/`0x2694` (heap alloc/free on `0x17da0`, not `audio_heap_free`), `0x2f68` (opens the message window, not `field_3d_board_mark_layout_dirty`), `0x360c` (font pop, not `field_3d_term_render_state`), `0x5da0` (same memset as `ui_field_clear_picture` but clears the cursor block), `0x6230` (not `system_net_cancel_selected_peer`). `0x2e8c` has the code of `ui_window_draw_text_box_px`, which is already used by `0x608` in this module, so it is named like rel_field's copy `ui_field_draw_message_line_text`.

## Open questions

- The face table `0x12d40` (8 entries: EHF animation pointer, character) is never written in this module, so speaker faces (slots 0-5) cannot appear; the scripts do not use those slots either. Leftover from another game (medium)?
- What the two-item quit prompt says (system message `0x1f`) and what item 1 does besides closing.
- Meaning of the duel setup byte `+0x191` and tail-block shorts `+0x34/+0x36` toggled by `flag_on/flag_off 3`.
- Meaning of player block word `+0x2cac` set at script end.
- Stubs with empty decompilation (`0x515c` hand count, `0x57d4` show_card, `0x5b70`, `0x58e8`, `0x1b04`): read the disassembly to see whether they are tail jumps to imports.
- Sprite helpers: `duel_core_tutorial_draw_gim_sprite` (13 arguments: list, gim index into the pointer table 0x00012ed0, x, y, width, height, u, v, tex_w, tex_h, colour, flip_uv, flip_xy; args 5-8 in t0-t3, 9-13 on the stack) and `duel_core_tutorial_draw_sprite_scaled` (11 arguments, same without gim and colour); the `_noflip` wrappers push two zero flips.
- `duel_core_tutorial_open_hint_window` takes the text as its fourth argument (a3 = 0x00017f60 from `duel_core_tutorial_show_hint`); the first three are ignored.
- Command 9 calls an empty on/off hook (0x00005b70) and then `ui_duel_draw_show_card_info_id(card)` through 0x000057d4; command 0x14 calls an empty hook (0x000058e8) after submitting the action. `duel_core_tutorial_cleanup` calls three empty hooks and `duel_core_tutorial_init` one.
- 0x0000515c is `duel_core_view_get_hand_count(*hand_list)` (resolves the hypothesis in `duel_core_tutorial_count_answer`); 0x00001b04 is the measure-text-height wrapper used by `duel_core_tutorial_measure_caption`.
