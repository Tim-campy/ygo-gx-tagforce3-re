# Card shop (`shop`, `rel_shop`)

The pack tables are in `docs/formats/packs.md`. `rel_shop` loads at `0x090ced00` (`modules.md`). Addresses are runtime addresses.

## Function families named in the 2026-10-31 round

Basis and method: `system.md`, same section. 190 names, all prefixed `shop_` (the module's local copies of UI and render code included, so that they do not collide with the same code in other modules).

| Family | Count | What it covers |
| --- | --- | --- |
| `shop_results` | 36 | The pack-opening results screen and its card menu. |
| `shop_resources`, `shop_render`, `shop_sprites`, `shop_math` | 40 | Resource loading, GE helpers, sprites, vector maths. |
| `shop_speech`, `shop_clerk` | 22 | The clerk's speech and voice. |
| `shop_counter_draw`, `shop_ui`, `shop_text`, `shop_dp_hud` | 42 | The counter scene, menus, text and the DP display. |
| `shop_effects`, `shop_opening` | 22 | Card reveal effects and the opening sequence. |
| `shop_card_list` | 12 | The list of cards obtained. |
| `shop_scene_flow` | 11 | The scene's state machine. |
| `shop_pack_table`, `shop_stubs` | 5 | The pack table at runtime is `0x090eefc8` (= base + `0x202c8`, consistent with `packs.md`). |

Facts established while naming:

- `card_db_get_prop_bits22` acts as the card's rarity in the shop (M): values 1/2, 3 and 4–6 select the reveal effect (`0x090d5200`, `0x090d5338`, `0x090d6560`); values 4/3/1 select the sounds `0x7a5f`/`0x7a60`/`0x7a61` and the icon cell `0x2027`; the field is also sort key 3.
- `shop_dispatch_state_step` (`0x090cf31c`) compares pad input with an 11-button sequence at `0x090e9ecc`. When the sequence is completed it sets bit 0 of `0x090facf6`, calls `shop_load_pack_states` and plays `0x7a0c`. That this is a secret code unlocking packs is a hypothesis (M) to check in PPSSPP.

## Open questions

- What bit 0 of `0x090facf6` changes in the pack states.
- Five 20–28-byte "empty" functions (`0x090d2d8c`, `0x090de328`, `0x090e41fc`, `0x090e5200`, `0x090e1fd4`) are probably tail calls Ghidra lost; unnamed.
