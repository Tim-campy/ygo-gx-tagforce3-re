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

## Round 2 of the 2026-10-31 naming

Method as in the first round (`system.md`): the still-unnamed functions were re-dumped from Ghidra with the current names, read in packs with full bodies (up to 160 lines), and named H/M with a basis in `re/names*.csv` under "round 2". 17 new `shop` names: the three `libshop_rel` exports that had no function (`shop_lib_start` `0x090d8280`, `shop_lib_draw` `0x090d8330`, `shop_lib_shutdown_step` `0x090d8338`; `system.md`, "Game-library imports"), the five former "empty" text functions, matrix helpers and result icons.

## Documented functions

The functions of this group that reached the `documented` stage in the 2026-10-31 documentation round (prototype, purpose, return value, side effects and callers, read from the decompilation) are listed in [`functions/shop.md`](functions/shop.md), extended in the 2026-11-03 round.

## Functions documented in the 2026-11-03 round (work packages 6-7)

Method: the remaining `shop` functions of `rel_shop` were re-dumped and read in full. Full rows: [`functions/shop.md`](functions/shop.md).

Material: the 67 previously undocumented `rel_shop` functions (packs pack00-pack04), read in full from the Ghidra decompilation. Addresses are runtime addresses (module base `0x090ced00`). Pad words used throughout: `system_pad_get_state()` +0 held, +4 newly pressed, +0xc repeat; buttons 0x10 up, 0x20 right, 0x40 down, 0x80 left, 0x100 L, 0x200 R, 0x1000 triangle, 0x2000 circle, 0x4000 cross, 0x8000 square (standard PSP masks). "Confirm"/"cancel" are `system_get_confirm_button(0)`/`(1)`.

#### Key structures

Counter-scene globals (all module `.bss`/`.data`, read and written by the step functions):

| Address | Size | Meaning | Basis |
| --- | --- | --- | --- |
| `0x090f9af0` | s32 | Shop scene state (table below) | all step functions |
| `0x090f9af4` | s32 | Sub-step of the purchase / card-detail machines | buy steps, `shop_show_result_card_detail` |
| `0x090f9af8` | s32 | DP spent in this visit (price added per purchase) | buy steps |
| `0x090f9afc` | u16[48] | Cart: packs bought per pack index in this visit | buy steps, `shop_open_pack_step` |
| `0x090f9b5c` | u16 | Packs bought in this visit (limit: + quantity must stay <= 1000) | `shop_select_purchase_step` |
| `0x090f9b5e` | u8 | Flags: bits 0-3 message kind open (`shop_show_message`), bit 4 card-detail request, bit 5 card viewer open, bit 6 clerk text pending after a pack change, bit 7 shelf emptied (forces a return to the pack choice and re-entry) | step functions |
| `0x090f9b5f` | u8 | Selected pack 0-47 (grid 4 rows x 12) | `shop_select_pack_step` |
| `0x090f9b60`, `0x090f9b64` | f32 | Slide offsets eased back to 0 in state 1 (`0x090f9b64` set to -5.0 on a pack change) | `shop_update_counter_step` |
| `0x090f9b68` | f32 | Shelf y-rotation in degrees, -26..+26 (column view) | counter step, shelf drawing |
| `0x090f9b6c` | u8 | Slot cursor: bit 7 column (0 = low nibble, 1 = high nibble of the stock byte), bits 0-6 row 0-9 | slot choice |
| `0x090f9b6d` | u8 | Column shown (0/1) | slot choice |
| `0x090f9b70` | f32[2][10] | Slot lift heights (column stride 0x28), 0..3 idle, up to 12 while taking a pack | counter step, buy steps |
| `0x090f9bc0` | u8[48] | Shelf stock per pack (two nibbles, 10 + 10), copied from the save (`packs.md`) | buy steps |
| `0x090f9bf0` | u8 | Flying-object flags: bit 0 single pack, bit 1 whole shelf, bit 2 box | buy steps, `shop_draw_pack_shelf_model` |
| `0x090f9c00`/`0x090f9c10`/`0x090f9c20` | vec4 | Flying pack start point, Bezier control point, current position | single/box purchase |
| `0x090f9c30`/`0x090f9c70` | mat4 | Flying pack start rotation, current rotation | same |
| `0x090f9cb0`/`0x090f9df0`/`0x090f9f30` | vec4[2][10] | Shelf purchase: per-slot start, control, current positions (column stride 0xa0) | `shop_buy_shelf_step` |
| `0x090fa070`/`0x090fa570` | mat4[2][10] | Shelf purchase: per-slot start and current rotations (column stride 0x280) | same |
| `0x090faa70` | u8 | Low nibble: secondary archive load state (0 not started, 1 loading; set to 1 on the first purchase); high nibble: selects packs 9-14 (`shop-rules.md` rule 4) | `shop_select_purchase_step`, counter step, `shop_update_pack_unlocks` |
| `0x090faa88` | s32 | Frame counter of states 2/5 and of purchase animations | several |
| `0x090facf4` | | Progress in the 11-button sequence (existing row of `shop_dispatch_state_step`) | — |
| `0x090facf6` | u8 | Bit 0 set by the 11-button sequence; read only by the pack 46 rule | see below |
| `0x090facf8` | s32 | Purchase mode 0 single, 1 shelf, 2 box | slot choice |
| `0x090facfc`/`0x090facfd` | u8 | Column counts saved at a shelf purchase | `shop_buy_shelf_step` |

Results screen: list `0x090faa74` (10-byte entries, `packs.md`), order array `0x090faa78` (u16 per row), count `0x090faa7c`, top row `0x090faa7e`, cursor in the 5-row window `0x090faa80`, sort mode `0x090faa82` (1-14, keys below), sort order `0x090faa84`, total copies `0x090faa86`, preview block `0x090faccc`.

Opening state `*0x090efc00` (0x520 bytes, heap): u16 +0 step, +2 packs opened of the current pack, +4 card count, +0x10 current pack, +0x20 pack position, +0x30 pack x-rotation, +0x34 pack model frame step; cards at +0x40 + i x 0x60 (u16 +0 state, +2 timer, +4 card id, +0x10 position, +0x20 matrix); u16 +0x400 frame step (1, or 3 while cancel is held), +0x402 timer; path points +0x410..+0x480 and matrices +0x490/+0x4d0 (`shop_init_opening_card_path`); +0x510 pointer to the card id being textured.

Other blocks: result card menu state `*0x090f9ae0` (0xc bytes: +0 state, +4 entry, +8 window); sort menu state `*0x098abe34` (0x18 bytes: +0 state, +2 focus, +4 saved order array, +8 saved mode bits 0-5 / order bits 6-7, +0xc, +0x10 key window, +0x14 order window); message window descriptor `0x090efc04` (0x120 bytes, the generic `ui_open_list_window` descriptor: +0x58/+0x5a position, +0x6c/+0x6e size, +0x84 text, +0xa0 title, +0xc4 heap, +0xcc item count, +0xce visible items, +0xd0 scroll, +0xd2 bits 0-4 cursor, +0xf0/+0xf2 width / item height, +0xfc/+0x100 item draw callbacks); clerk block `0x0973ad50` (byte +0 bit 0 clerk variant, u16 +2 animation state, +4 timer limit, +6 counter, +8 slide offset, +0xc face EHF, +0x10 mouth EHF); speech box globals `0x098abe94..0x098ac00c`; DP HUD block `0x098abe3c`; reveal-effect state blocks `0x090efdc0` (small, 12 bytes), `0x090efdd0` (medium, 0x7ad0), `0x090f78a0` (large, 0x2240).

#### Scene state machine (`0x090f9af0`)

Update: `shop_update_counter_step` (every frame, states < 7 also update clerk, speech box and DP HUD) plus `shop_dispatch_state_step` (input). Draw: `shop_draw_scene`.

| State | Meaning | Leaves to |
| --- | --- | --- |
| 0 | Entrance: waits for the speech box and for clerk animation state 2 | 1 (shows the pack's clerk text) |
| 1 | Pack choice (`shop_select_pack_step`) | 2 on confirm of a pack on sale; 7 on cancel with packs in the cart (fade out); stays with message 1/2 when the cart is empty |
| 2 | Zoom into the shelf, 19 frames | 3 |
| 3 | Slot / purchase-mode choice (`shop_select_purchase_step`) | 4 on a valid purchase; 5 on cancel or when the shelf was emptied |
| 4 | Purchase animation (`shop_buy_single_step` / `_shelf_step` / `_box_step`, sub-steps 0-6 on `0x090f9af4`) | 3 |
| 5 | Zoom out, counter 18 -> 0 by 2 | 1 |
| 6 | Leaving (set by `shop_results_exit_step` for message kinds 1/2): `shop_dispatch_state_step` returns 1 once fade and sounds end | module exit |
| 7 | Fade out before the opening; waits for the secondary archive | 8 (`shop_init_pack_opening`) |
| 8 | Pack opening (`shop_open_pack_step`; skip or end -> `shop_open_all_packs`) | 9 |
| 9 | Results list (`shop_results_list_step`) | 10 (L held), 0xb (R held), 0xc sort menu, 0xd card menu, 0xe via message 5 |
| 10 | Results paging with L (group jumps, group label shown) | 9 |
| 0xb | Results with R: toggles the card flag, help panel | 9 |
| 0xc | Sort menu (`shop_results_sort_menu_step`) | 9 |
| 0xd | Result card menu | 9 |
| 0xe | After commit (`shop_commit_results`): fade, `shop_reset_counter`, fade in | counter (state set by `shop_reset_counter`, not in this material) |
| 0xf | Nothing drawn | — |

Purchase sub-steps (all three modes): 0 charge and save writes, 1 lift (single/shelf only; the box skips to 2), 2 compute flying start pose and update stock/cart, 3 10-frame quadratic Bezier with rotation slerp to identity, 4 wait 13 frames, 5 slide out at -2.5 per frame to x < -12, 6 clear the flying flag and return to state 3. Confirm in 4/5 jumps to 6.

Opening steps (`*0x090efc00` +0): 0 open next pack and set it up; 1 pack flies in (24 frames); 2 tear animation (model frame step = speed; the draw function sets step 3 at model frame 40); 3 wait for all card images; 4 cards advance (card states 0 hidden, 1-4 path stages with durations u16 `0x090ea040[state]`, 5 done; state 3 waits for the reveal effect when rarity != 0); 5 pack flies out (12 frames) and the next pack of the cart is chosen; 6/7 every 30 packs (and at each pack-kind change) the cip reader is stopped and the image cache rebuilt.

Reveal effects (`shop_play_reveal_effect`): rarity 1-2 small (pale flare, 8 frames), 3 medium (blue glow, rising emitters and sparks, 50 frames), 4-6 large (gold glow, bursts and stars, 50 frames); each then waits 24 more frames before reporting completion. Sounds when a card reaches state 3: rarity 4 `0x7a5f`, 3 `0x7a60`, 1 `0x7a61` (none for 2).

#### Pack availability and unlock logic

`shop_update_pack_unlocks` was read in full and matches `docs/formats/shop-rules.md` rule by rule (partner lists, thresholds, level and opponent tables, `all_done`, story bit 2), with two corrections/clarifications:

- **Packs 41/42 byte**: in this decompilation the rule reads bit 0 of `0x0973ad50`, the same byte whose bit 0 selects the clerk variant (`shop_get_pack_clerk_text(pack, 0x0973ad50 & 1)`, the greyed-pack message word 0x18/0x19, the clerk voice set in `packs.md`). So packs 41 and 42 are tied to which clerk serves the shop (hypothesis, medium: pack 41 needs character (0x1a, 0) finished and clerk bit 1; pack 42 needs (0x1b, 1) finished and clerk bit 0). Settled 2026-11-04: `0x0973ad50` is right (module `+0x66c050`, inside the module's BSS; the `+0x2c050` reading paired the load with the wrong `lui`), and the clerk is the daily pick of system flag 4 (`shop-rules.md`, "Sources of the three shop bytes").
- **`0x090faa70`**: the high nibble selects packs 9-14; the low nibble is unrelated: it is the secondary archive load state (0 -> 1 at the first purchase, polled while 1).

**Answer to the open question "what bit 0 of `0x090facf6` changes"**: its only reader in the shop is the pack 46 rule (`save_set_pack_state(46, 2)`). The 11-button sequence in `shop_dispatch_state_step` sets the bit and immediately calls `shop_load_pack_states` (which runs `shop_update_pack_unlocks` first, per `shop-rules.md`), so the sequence puts pack 46 (the 573-DP pack) on sale. Because the rule writes the save pack state and no rule ever lowers pack 46, the unlock persists in the save once the game is saved (hypothesis, medium; confirm in PPSSPP).

#### Results sorting

Sort keys (`shop_get_result_sort_key` / `shop_get_result_group_key`, mode = key window index + 1): 1 pack, 2 new (collection state 0), 3 rarity (rarest first), 4 save card flag (flagged first), 5 card sort position / top group (index letter), 6 card frame, 7 level, 8 ATK, 9 DEF (groups of 100), 10 race, 11 attribute, 12 spell/trap icon (frames 7 and 8 only), 13 current card limit, 14 copies obtained. Frames 7 and 8 have only key 12 among 7-12, which suggests they are the spell and trap frames (hypothesis, medium). The sort menu previews every change live and restores the saved order and mode on cancel.

#### Other findings

- The result card menu has three items: 0 open the card detail (card viewer with artwork selection), 1 toggle the save card flag (`save_set_card_byte1_flag`), 2 close.
- `shop_show_message` kinds: 1/2 leave question at the counter (2 with a shoulder button held; they also call `system_scene_set_field_8c(2)` / `(4)`), 3 not enough DP, 4 over 1000 packs, 5 leave the results screen. The kind stays in the low nibble of `0x090f9b5e` until `shop_results_exit_step` handles the answer.
- The speech box reveals text by scissoring each line to its revealed width; a fast-forward (R + confirm held, every third frame) is enabled only when save progress flag `+0x1c0e9` bit 4 is set.
- The reveal effects use their own C-library-style LCG (`x * 0x41c64e6d + 0x3039`, 15-bit output) rather than `system_rand`; it does not affect which cards are drawn.
- The opening renders each card face into EDRAM `+0x160000` (128 x 256) through `shop_card_model_texture_callback` and textures model 0x8004 with it; the medium and large effects reuse that EDRAM image for their glow.

#### Name mismatches

- Resolved 2026-11-04: the two icon drawers were swapped and are renamed. `shop_draw_attribute_icon` (`0x090e3064`, formerly `shop_draw_spell_trap_icon`) receives `card_db_get_attribute` from `shop_draw_results_row` (at `(0xb3, y + 0x28)`) and from `shop_draw_results_group_label` for sort key 11; `shop_draw_spell_trap_icon` (`0x090e2fe8`, formerly `shop_draw_attribute_icon`) receives `card_db_get_icon` of a non-monster (at `(0xc4, y + 0x28)`) and sort key 12. Basis: the call sites in the decompilation of `shop_draw_results_row` (high).
- `shop_results_jump_to_group`: its documented parameter is called `forward`, but `shop_results_find_group_boundary(0)` searches forward and a non-zero argument searches backward (`shop_results_page_step` passes 1 for triangle and 0 for cross).
- `shop_setup_opening_fog_view` also sets up lighting (light block `0x0973ad0c`, light 0, ambient) for the opening stage; the name is acceptable but incomplete.

#### Open questions (rel_shop)
- ~~`0x0973ad50` vs `0x090fad50` and the other references "outside the module image"~~: settled 2026-11-04. `rel_shop`'s program header gives a memory size of `0x7dd330` bytes, so the module occupies `0x090ced00`–`0x098ac030`; the clerk block `0x0973ad50`, the light block `0x0973ad0c`, the sort menu pointer `0x098abe34`, the DP HUD block `0x098abe3c` and the speech box `0x098abe94` all lie in its zero-initialised area, after the `0x640000`-byte heap that `shop_lib_start` creates at `0x090fad00`.
- ~~Who writes the high nibble of `0x090faa70` and bit 0 of `0x0973ad50`~~: `shop_lib_start` (weekday) and `shop_init_clerk` (system flag 4), settled 2026-11-04 (`shop-rules.md`).
- The argument of `shop_set_clerk_animation` in clerk state 1 is hidden (presumably 2); clerk state 5 sets state 0 while the offset is below 0x7c, which reads like an inverted test; check the disassembly.
- The argument the caller passes to `shop_advance_opening_cards` (presumably the frame step) and the `passes` argument of `shop_get_cosine_eased_ratio` are not visible in the caller's decompilation.
- Where the reveal-effect LCG state lives (the decompiler shows a read through address 0).
- What `system_scene_set_field_8c(2/4)` does when the leave question is shown.
- The colour-0 screen rectangle drawn under alpha function 7 by `shop_draw_reveal_effect_large` (stencil or alpha mask?).
- Cell width of `shop_draw_small_digits` size variants 1 and 2 (hidden register).
- Rarity 2 plays no reveal sound; check whether that is intended or another value is used.

## Password machine and conversion machine (lab hub, 2026-11-04)

The two lab-hub card machines are separate modules started by `rel_labo` (`ui_password_start`/`_update`, `ui_conv_machine_start`/`_update`). Neither is part of the shop, but both are the remaining card sources next to the packs (`formats/packs.md`, "Cards in no pack"), so they are specified here. Static reading with capstone (task B8 of `PORT-READINESS.md`); the modules' load bases are unknown, so **every address below is a module offset** (`+0x…`, unrelocated, base 0). Imports were named with `tools/prx_imports.py <BOOT.BIN> <module> 0 re/functions.csv` (BOOT functions by their registry names, module libraries through `re/game-libs.csv`). Neither module calls a DP (money) accessor: **both machines are free**.

### Password machine (`rel_password`, module id `0x1a`)

| Step | Rule | Evidence | Conf. |
| --- | --- | --- | --- |
| Entry | Eight decimal digits, kept as one byte each in the work block at `+0x16437`–`+0x1643e` (most significant first). | Loop at `+0x26a4`: `value = value × 10 + digit` over 8 bytes from `+0x16437`. | H |
| Lookup | `card_db_find_by_passcode(value)` (`0x08832c34`): linear scan of ids `0xe88`–`0x1f39` against `CARD_Pass` (`cardinfo.md`); passcode 0 never matches. 3,399 cards have a passcode and no two cards share one, so the result is unique. | `+0x26d0`; the duplicate count from `cardinfo` (`extracted/cards_eng.csv`). | H |
| Refusal | Refused (state 5, failure message) when the id is outside `0xe88`–`0x1f39`, `card_db_is_valid` fails, or the id is in the **refusal list** at `+0x83f8` (9 × `u16`: `5000, 3787, 4998, 3763, 4999, 3790, 3752, 3789, 6989`) tested by `+0x336c`. | `+0x26dc`–`+0x2710`. | H |
| Refusal-list quirk | `+0x336c` is a binary search (`lo = 0`, `hi = 8`), but the list is not sorted and nothing sorts it (the module's only `system_qsort` sorts the 17 × 16-byte table at `+0x82c8`). Only `6989` (Elemental Hero Air Neos) is reached by the search, and it is also the only listed card with a non-zero passcode: the other eight have passcode 0 and are already rejected by the lookup. Effective rule: **every card with a passcode except `6989`**. | Simulation of the search over the stored order; passcodes from `cardinfo`. | H |
| Accept | No ownership test, no "already registered" test, no cost. State 4 shows the card (`card_db_cip_get_image` with the art variant `save_get_card_value_bits4_6`), waits at least `0x79` frames, then on circle/cross (pad mask `0x6000`) or after `0x259` frames calls `save_set_card_flag_bit0(id)` (`0x088564a8`). | `+0x26f4`–`+0x2744`, `+0x2a68`–`+0x2ad8`. | H |
| Save write | Only collection record byte 0 **bit 0** of the card ("registered by password", `formats/save.md`, "Card collection"). No copy is added (`save_change_card_count` is not imported by the module). | Call census: `save_set_card_flag_bit0` has one caller in all 36 modules, `rel_password +0x2ac0`; no BOOT caller. | H |

**What registration gives.** Bit 0 has exactly one reader in the game: `save_test_card_flag_bit0` from `rel_select_card +0x2598`, inside the list builder `+0x2568`. That builder makes the left-hand list of the card picker's **mode 0**: every valid id `0xe88`–`0x1f39` with bit 0 set, one copy each (entry byte 4 bits 0–6 = 1). Mode 0's right-hand list is the save **card list** at `+0x161f4` (`formats/save.md`, 99 entries; builder `+0x2684`), and on exit (`+0x3088`) mode 0 rewrites that list from the right-hand side: count (`save_set_card_list_count`), ids (`save_set_card_list_entry`) and each entry's state (byte 5 bits 2–4, `save_set_card_list_state`). The save card list is the pool that `deck_count_free_card_copies`, `deck_count_free_card_copies_2` and `deck_check_deck_valid` add to the owned copies (states 1–3): extra, rented copies for decks. `rel_labo` opens the picker in mode 0 (`ui_select_card_open(0, 0, 0, 0)` at `+0x324` and `+0x3bc`; the picker loads `labo/rental.ehp`). So: **a passcode unlocks the card for the rental list; the player then places it in the 99-entry rental list from the lab, one copy per registered card, and decks may use it as if owned.** (H for the data flow; M for "rental" as the player-facing meaning and for the per-card limit of one; the state value a newly placed entry gets is not traced: the builder stores 4, which `deck_count_free_card_copies` would not count, so the move into the right-hand list presumably rewrites it. PPSSPP G3 records it.)

### Conversion machine (`rel_conv_machine`, module id `0x0e`)

| Step | Rule | Evidence | Conf. |
| --- | --- | --- | --- |
| Input | The card picker in **mode 1** (`ui_select_card_open(1, …, &count, ids)` at `+0x52c`, count starting at 0). Left list: every valid id with free copies `> 0` (`deck_count_free_card_copies_2`: owned minus copies in the player's deck, plus rental-list entries), builder `rel_select_card +0x2458`. Right list capacity 99 (`0x63`). | `+0x4e0`–`+0x564`; `rel_select_card +0x2018`. | H |
| Minimum | Fewer than 10 cards: nothing happens (message, back to the machine's menu, state 7). | `+0x5e0`: `count < 10` branch. | H |
| Cost | Each selected card loses one owned copy: `save_change_card_count(id, 0)` for each of the `count` ids. | `+0x60c`–`+0x634`. | H |
| Result | One card, drawn uniformly from the **result list for `count`**: `list[count − 10][system_rand_shifted() % length]`. | `+0x1a38`, called at `+0xa4c` (skip) and `+0xec8` (end of the animation); result kept at work `+0x78cf4`. | H |
| Award | On circle/cross at the result screen: `save_change_card_count(result, 1)` (one copy; a never-owned card becomes "new"). Triangle first opens the card viewer (`ui_card_viewer_open`) and returns. | `+0x15b0`–`+0x15d4`, `+0x1578`. | H (call), M (button roles) |
| Save writes | Only the card counts above. No flag, no counter, no DP. | Import census of the module. | H |

**Result-list table** (`rel_conv_machine` `.data`, module `+0xb014`): 90 records of 8 bytes, index `count − 10` for `count` = 10–99.

| Offset | Size | Field |
| --- | --- | --- |
| `+0x0` | 4 | Pointer (relocated; module offset in the file) to a `u16` card-id array in `.data` (`+0x9494`–`+0xb013`). |
| `+0x4` | 4 | Number of ids in the array (28–40). |

The arrays hold 3,475 ids in total, each id in exactly one array, so the number of cards fed in decides which card can come out. They are exactly the pack cards (`packs.md`) minus three (`3737` Jurassic Impact, `6834` Power Wall, `7351` Phantom of Chaos, which only packs 45 and 47 give) plus **`6989` Elemental Hero Air Neos**, in the array for 59 cards (1 chance in 39). Rarity (cardinfo word 1 bits 22–24) rises with the count: the arrays for 10–30 cards are almost all rarity 0, those for 94–99 mostly rarity 3–4. A port reads the table from the module at these offsets (no extractor step exists yet).

### Open questions (lab machines)

- The state value a password card's rental entry has after it is moved into the rental list (builder stores 4; `deck_count_free_card_copies` counts 1–3), and whether the rental list may hold two entries of one card. PPSSPP G3.
- The meaning of the 17 × 16-byte table at `rel_password +0x82c8` that the module sorts at start-up (presumably the digit-pad layout or message table; not needed for the rule).

## Open questions

- What bit 0 of `0x090facf6` changes in the pack states.
- ~~Five "empty" functions~~: answered 2026-10-31 (round 2) from the instructions: they are tail calls Ghidra lost. `0x090d2d8c`, `0x090de328` and `0x090e41fc` draw text fitted to a width (`font_draw_text_fit_width` with x, y, width << 6); `0x090e1fd4` and `0x090e5200` draw text in a box (`font_draw_text_box`); named H.
