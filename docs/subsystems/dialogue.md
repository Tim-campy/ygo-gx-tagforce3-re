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

Differences with `story.md` found by reading the handlers (to reconcile there):

- 50160/50161 (`npc_place`): handler `0x08ea99c4` writes record `+0x40` (the event variant) from `world_get_character_key(row)`, which matches `world.md`'s `+0x40`, rather than converting a location to a position through `0x0885ad14`.
- 50112/50113: the fade sense is the other way round; 50112 passes `on = 1` (fade in), 50113 passes 0.
- 50030: handler `0x08ea7d50` skips to `0xc38e`, the endif of 50029, not to `0xc38f`. It looks like a bug in the game; it matters only if the opcode is used.

## Open questions

- 32 import stubs of `rel_story` (`0x08eadfc4`–`0x08eae074`, `0x08eb115c`–`0x08eb1214`) point at libraries whose module is not resolved, and the 21 mini-game and mode state functions `0x08ea2e44`–`0x08ea3800` that call only them are unnamed.
- Opcodes 50042 (`0x08ea8170`, tests `0x088578c0`), 50100 (`0x08ea87dc`, decompiles empty) and 50154 (`0x08ea980c`).
