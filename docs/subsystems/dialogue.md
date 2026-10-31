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

## Open questions

- Opcodes 50042, 50100 and 50154 are read (`dialogue_op_if_setting_b0_bit3`, `dialogue_op_mark_card`, `dialogue_op_prefetch_bgm`; `story.md`). BOOT `0x08835ad0(0/1)` around every sub-module run is `system_set_loading_overlay` (round 2: it restarts the `loading.ehf` player; M), so the open point is only what its argument selects.
