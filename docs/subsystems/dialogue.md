# Story scripts and dialogue (`dialogue`)

The story bytecode is specified in `docs/formats/story.md`; the free-roam world is in `world.md`. `rel_story` loads at `0x08e9aa00`. Addresses are runtime addresses.

## Function families named in the 2026-10-31 round

Basis and method: `system.md`, same section. 205 names (183 in `rel_story`, 22 in `rel_field`).

| Family | Count | Evidence |
| --- | --- | --- |
| `opcode_handlers` | 111 | The bytecode interpreter's handlers: runtime address = `0x08e9aa00` + the module offset listed in `story.md` (for example `+0xc430` → `0x08ea6e30`, talk), H. The opcode numbers of the empty handlers come from their place in address order, which agrees with every no-op listed in `story.md`. |
| `talk_windows`, `talk_window` (`rel_field`), `portraits` | 33 | Talk and narration windows, the choice menu, character portraits. |
| `event_state` | 14 | Event state block `0x08ece440`. |
| `script_tables`, `script_archives`, `opcode_maps`, `event_vm`, `vm_helpers` | 27 | Script loading and the interpreter loop. |
| `text_expand`, `sysmsg`, `card_rewards` | 15 | Text expansion, system messages, card rewards. |
| `field_requests` (`rel_field`) | 5 | Field requests that open dialogue. |

Differences with `story.md` found by reading the handlers, and how they were settled on 2026-10-31 (round 2):

- 50160/50161 (`npc_place`): **changed.** Handler `0x08ea99c4` writes record `+0x40` (the event variant) from `world_get_character_key(row a2)` through `world_set_record_event_variant(char a1, …)`; nothing converts a location. Renamed `dialogue_op_npc_set_variant`; the opcodes are `npc_set_variant`/`npc_set_variant_b` with arguments (char, row) in `story.md` and `tools/story.py`.
- 50112/50113: **story.md changed, opcode names kept.** `dialogue_op_fade` passes `on = 1` for 50112 and 0 for 50113. `on = 1` is a fade in: `world_state_enter_location` and `world_state_staff_roll_movie` call `world_fade_screen(1, …)` after the set-up, `world_leave_field_scene`, `world_state_sleep_to_next_day` and `world_state_return_from_story` call `world_fade_screen(0, …)` before leaving, and `world_field_req_fade` (`rel_field` request 22) calls `system_start_fade_in` for 1 and `system_start_fade_out` for 0. So `fade_in`/`fade_out` were right; only the "on = 0 / 1" column of `story.md` was swapped.
- 50030: **kept, recorded.** Handler `0x08ea7d50` skips to `0xc38e`, the `endif` of 50029, not to `0xc38f`. It is a slip in the game that matters only if the opcode is used; `story.md` now says so and a port should keep it.

## Sub-module states (2026-10-31, round 2)

`rel_story` runs the game's library sub-modules from 24 small states at `0x08ea2e44`–`0x08ea3800` (family `sub_module_states`). Each pair is `world_state_start_<module>` (calls the module's start export once, then `system_set_loading_overlay(0)`) and `world_state_update_<module>` (calls update; while it returns 0 calls draw; otherwise `system_set_loading_overlay(1)`, stores a result code in `0x08ecd974`, fades and picks the next story state in `0x08ecd978`). Result codes: 1 shop, 2 recipe viewer, 3 password, 4 select card, 5 conversion machine, 6 card album, 7 character list, 8 limit list, 9 tutorial list, 10 deck tutorial, 11 duel record. Two special cases: the character list with system flag `0x14` set opens in mode 3 and afterwards resets the location (`0xe`), calendar and character records and selects the partner event (the start of a new game), and a tutorial-list choice of 8–`0x17` sets duel set-up mode 0–15 and starts a default duel. Three further states drive the field module itself (`world_state_init_field_module`, `world_state_run_field_frame`, `world_state_shutdown_field_module`).

The import stubs they call are named from `re/game-libs.csv` (see `system.md`, "Game-library imports").

## Documented functions

The functions of this group that reached the `documented` stage in the 2026-10-31 documentation round (prototype, purpose, return value, side effects and callers, read from the decompilation) are listed in [`functions/dialogue.md`](functions/dialogue.md), extended in the 2026-11-03 round.

## Functions documented in the 2026-11-03 round (work packages 6-7)

Method: the remaining `dialogue` functions of `rel_story` and `rel_field` were re-dumped and read in full. Full rows: [`functions/dialogue.md`](functions/dialogue.md).

### Findings from rel_field

#### Portraits

Three slots of `0x100` bytes at `0x09105370`: `+0x00` load handle pointer, `+0x04` decompressed buffer, `+0x08` handle, `+0x0c` body layout (`body.ehf`), `+0x10` blink frame, `+0x5c`/`+0xcc` body/mouth alpha, `+0x70` expression, `+0x74/+0x78` blink state/timer, `+0x7c` mouth layout (`mouth.ehf`), `+0xe4` loaded, `+0xe8` state (0 none, 1 appearing, 2 shown, 3 leaving), `+0xec` character key, `+0xf0` slot index. Portrait archives are gzip-compressed EHP; size from `world_field_get_resource_file_size(5, key)`. Fade steps ±31 per frame; blink every 90–299 frames; the speaker is field context `+0x08`. Pending flags `0x09105354[3]` (show) and `0x09105364[3]` (hide) gate the busy words `0x09105348`/`0x09105350` (M which requests they belong to). Preload (request 11): pending counter `0x09105670`, busy `0x09105340`; all-loaded word `0x09105360`.

#### Open questions (rel_field)
- Which request polls `0x09105348` and `0x09105350` (presumably 13 show and 12 release).
- `dialogue_draw_text_to_screen_edge` (skipped): read from the disassembly.

### Findings from rel_story

#### Interpreter

`dialogue_run_event_script` executes 10-byte instructions `{u16 opcode, u16 a1, u16 a2, u16 a3, u16 line}` from the record header `0x08ece530` at index `0x08ece534`. It runs synchronously until opcode 0, `goto` (50138, returns after the handler) or `halt` (50145, returns without advancing); blocking handlers wait on field requests inside the call. Unknown non-zero opcodes are skipped silently. The set-up pass is as in `story.md` ("Run model"); the driver side of the two passes is under `## world` above.

#### Menus

`dialogue_op_case`: the field returns the chosen option 0–4 for request 18; the handler stores 1–5 in byte `+0x64` of the event queue block (confirms `story-runtime.md` width u8). `dialogue_op_random_case`: draws `rand % count` (count 1–10) and jumps through a 10-entry table at `0x08eb3f3c` that Ghidra did not recover; `story.md` says the branch is `rand % count + 1` (consistent if entry r skips to `case r + 1`; M). `dialogue_is_block_closer`: `case`/`random_case` with a1 = 11 and every `endif` 50047–50079 close a block for the skip search.

#### Talk windows and portraits

Two speaker slots: characters at `0x08ecec70[2]`, slot records at `0x08ecec78` (12 bytes `{portrait row, window, expression}`), current window `0x08ecec90` (−1 none). Windows are numbered 0, 1, 2: a single speaker uses window 1; with two speakers the newest takes window 2 for opcode 50001 (`0xc351`) and window 0 for 50002, the other the opposite (`dialogue_open_talk_slot`) — presumably right/left sides of the screen (L). Adding a third speaker closes (field request 15) the slot not on the requested side. Field requests: 13 show portraits, 14 change expression `{window, 1, expression}`, 15 close windows, 17 talk line `{text, name, window}` (window −1 for a speaker without a portrait).

#### Text expansion

- `dialogue_expand_card_names`: `$M` + four decimal digits → card name (`card_db_get_name`).
- `dialogue_expand_name_tokens`: tokens between U+300A and U+300B, keyed by ASCII letters: `C` (event key a1 as 3 digits + which-name digit) → character name looked up by the a1 columns 1–4 of the character table; `M` (3 digits + digit) → `dialogue_get_location_map_name` (not decoded); `PA` → partner name; `TEA` → team name; `TES` → the number in field state `+0x168` (the score set after mode-4/mode-8 returns, `## world`); `B` → current item name; `PL` is left as is (presumably the player name, expanded elsewhere, L). Replacements are wrapped in colour codes `$C<n>` … `$C0`.
- `dialogue_replace_token(text, token, value)`: generic replacement wrapped in `$C7` … `$C0`.

All three work on at most 0x100 UTF-16 characters and stop when the result grows past that.

#### Name mismatches

- `dialogue_call_close_talk_windows` (`0x08eac798`) is 8 bytes; the decompiled body belongs to the following code (skipped).

#### Open questions (rel_story)
- `dialogue_map_language_index` (`0x08e9eee0`) and `dialogue_get_location_map_name` (`0x08eadd3c`) decompile to empty bodies; their return values need the disassembly.
- The `random_case` jump table `0x08eb3f3c` targets.
- Which side of the screen windows 0 and 2 are.

## Open questions

- Opcodes 50042, 50100 and 50154 are read (`dialogue_op_if_setting_b0_bit3`, `dialogue_op_mark_card`, `dialogue_op_prefetch_bgm`; `story.md`). BOOT `0x08835ad0(0/1)` around every sub-module run is `system_set_loading_overlay` (round 2: it restarts the `loading.ehf` player; M), so the open point is only what its argument selects.
