# Decks and deck rules

## Key functions

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x08835e70` | `deck_get_default_limit(id) → status` | H | Linear search of the 114 `(id, status)` pairs at `0x08878cb8`; 3 when absent. Caller `0x08832fa4`. |
| `0x08835df4` | `deck_reset_limits()` | H | `deck_set_limit(id, 3)` for ids `0xe88`–`0x1f39`, then `deck_set_limit` for each listed pair; then `0x08836aec(5)` and `0x0885660c`. Caller `0x08853e80`. |
| `0x088566a4` | `deck_set_limit(id, status)` | H | Writes `status` into bits 0–1 of byte 2 of the card's collection record (`save_get_card_record`); ignored when `status >= 4` or the card has no record (index 0, tokens). Caller `deck_reset_limits`. |
| `0x08856704` | `deck_get_limit(id) → status` | H | Reads the same bits; 3 without a record. Callers `deck_get_card_limit`, `0x08857070`, `0x0885c660`. |
| `0x08832fa4` | `deck_get_card_limit(use_builtin, id) → status` | H | `deck_get_default_limit(id)` when the global `0x08aa5688` (returned by `0x08835ac4`) is non-zero or `use_builtin == 1`, else `deck_get_limit(id)`. Exported (thunk `0x08833630`). Hypothesis (low): `0x08aa5688` selects the official list for modes that ignore the save's list. |
| `0x08833624` | `deck_get_current_card_limit(id)` | H | `deck_get_card_limit(0, id)`. Exported. |
| `0x0885660c`, `0x08856674` | `deck_set_limit_list_name(name)`, `deck_get_limit_list_name()` | M | Write (clear 0x80 bytes, then `system_wcsncpy` of 63 units) and return the UTF-16 field at game state `+0x16582`. The setter's only caller is `deck_reset_limits`; the analysed save holds a `2008/03` date there, the date of the built-in list. |
| `0x08856780` | `deck_get_slot_cards(slot)` | H | `state + 0x4914 + 0x16c × slot`: the 0xc0-byte card lists of a deck slot. Callers include `0x08854218`, `0x08856954`, `0x08856a3c`, `0x08856ad0`, `0x08856bd4`, `0x08856cc8`, `0x0885704c`. |
| `0x088567e8` | `deck_copy_slot_cards(slot, out)` | H | Copies those 0xc0 bytes. Callers `0x08836358`, `0x088567b8`. |
| `0x0885684c`, `0x088568d4` | `deck_get_slot_name(slot, out)`, `deck_set_slot_name(slot, name)` | H | Copy the 64-byte UTF-16 name at slot `+0x10` out or in, forcing a final NUL. Callers `0x08836358`, `0x0885681c` / `0x088568a4`, `0x08854218`. |
| `0x0885c3dc` | `deck_load_recipe(index, deck)` | H | Clears the 0xc0-byte deck, formats `"RCP%03d.ydc"` (`0x08916710`), looks it up in the archive at `0x088d77e0` with `container_ehp_find_member`, copies main/extra/side with limits 60/15/15. Callers `0x088365b8`, `0x08836840`, `0x08853f3c`, `0x08854270`. |
| `0x0885c314` | `deck_get_recipe_name(index)` | H | Checks that the `.ydc` exists, builds `recipe_name_<l>.bin` from `"recipe_name_x.bin"` and `"jegfis"`, returns string `index` via `0x08836ed0`. Callers `0x08836594`, `0x0885406c`. |
| `0x0885c2dc` | `deck_get_recipe_level(index)` | M | `u16` table at `0x089143f0` for 0 ≤ index < 462 (`slti 0x1ce`), else 1. The name rests on the 1–10 value range. |
| `0x0885cc3c` | `deck_get_owner_recipe_count(owner)` | H | Binary search (`0x0880a4a4`) of the 126 × 16-byte owner table at `0x08915f28`; returns field `+8` or 0. |
| `0x0885cc80` | `deck_get_owner_recipe(owner, n)` | H | Same search; returns `first + n` when 0 ≤ n < count, else −1. Callers `0x088541f0`, `0x0885cd14`. |
| `0x0885cd2c` | `deck_select_owner_variant(owner, stage)` | M | Searches the 67 × 12-byte table at `0x08916730`; mode from `0x0885aeb0`; special case for owner 8. |
| `0x0885ccfc` | `deck_get_owner_current_recipe(owner, stage)` | M | `deck_get_owner_recipe(owner, deck_select_owner_variant(owner, stage))`. Caller `0x08854244`. |
| `0x08836358` | `duel_setup_load_decks(setup)` | H (code), M (name) | Copies the 0x858-byte duel set-up block to a static buffer (`0x0883634c`) and, for each of the four 0x1ac-byte duellist records at `+0x1a4`, sets the duellist name and fills the deck from record `+0x8`: a recipe below 462, or one of the set-up codes 462–466 (keep, stored deck, none, player's deck, own deck slot); 467 and above clear the deck (`docs/formats/deck.md`, "Who uses which recipe"). Callers: the set-ups of `rel_story` (`0xa284`, `0xa2ec`), `rel_title` (`0x595c`, `0x5e58`, `0xcae4`), `rel_tutorial` (`0x614c`), `rel_underground` (`0xdc14`), `rel_debug_menu` (`0x13b8`), all through their `libehsys_rel` import stub. Not yet in Ghidra. |
| `0x088367bc` | `deck_is_player_deck_recipe(recipe) → 0/1` | M | Loads `recipe` and deck slot 1 into two heap buffers of 0xc0 bytes, sorts the main and extra lists of both (`0x08836750`) and returns 1 when the counts and ids are equal; side deck ignored. Only caller: the handler of story condition 50030 (`rel_story` `0xd350`), which no record uses. |
| `0x0885c528` | `deck_get_recipe_card_list(recipe, out)` | M | `out = {u32 count, u16 ids[46]}` from the 462 × 8-byte table at `0x089150b8` (count clamped to 46); no bounds check on `recipe`. Callers `duel_setup_load_decks`, `0x08854064`, `0x088542d4`, and `rel_recipeviewer` (2). Meaning of the list: hypothesis (low, key cards). |
| `0x0885600c` | `save_get_stored_deck(n)` | M | `save_get_state() + 0x20 + 0x174 · n`: a stored deck record (`+0` flag, `+4` name 0x40, `+0x54` deck 0xc0, `+0x114` card list 0x60, from the copies in `duel_setup_load_decks`). Used for set-up code 463. Group `save`. |
| `0x0885ce3c` | `deck_compare_owner_key(a, b)` | H | `*(u32*)a − *(u32*)b`; comparison callback of the owner-table search. |

`0x08854218(owner, stage)` picks the current recipe of an owner, stores owner, stage and recipe in a per-owner 0x16c-byte record (offsets `0x48c8`–`0x48d0`, that is `+4`–`+0xc` of deck slot `owner`) and loads the deck; not yet named. The deck slots are therefore indexed by owner: slot 1 is the player's starting deck (owner 1 = recipe 0) and slots 2–126 belong to the partner characters (`save.md`). `0x08856730(x)` returns slot 1 for `x == 0`; the wrappers `0x088567b8`, `0x0885681c`, `0x088568a4` use it to reach the player's slot.

## Data

- Restriction list: `docs/formats/limit-list.md`.
- Deck recipes, recipe names, owners, levels and variants, `sameCardTbl.dat`, `fileTbl.dat` and the deck-tutorial scripts: `docs/formats/deck.md`.
- Opponent decks are the `.ydc` recipes embedded in `BOOT.BIN`: the 462 named ones, assigned to 126 owners (the starting deck plus 125 characters). The other 199 are never loaded; values 462–466 of the set-up's recipe field select other deck sources (`deck.md`, "Who uses which recipe").

## Function families named in the 2026-10-31 round

Basis and method: `system.md`, same section. 434 new `deck` names (39 in `BOOT.BIN`, 90 in `rel_deck`, 9 in `rel_title`) and 254 `ui` names in `rel_deck`.

- `BOOT.BIN`: `deck_member_slot` 18 and `deck_slot_access` 17. `0x08856730` maps a team member to a deck slot: 0 gives slot 1 (the player), any other value the partner's slot through `save_get_partner`. This bears on the open question about partner decks; the `deck_*member*` names depend on it (M). Checked again on 2026-10-31 (round 2): the body is exactly `member == 0 ? 1 : save_get_partner(0)`, and all 17 callers are the `deck_*member*` accessors, so the names stand; the open question below is narrowed accordingly.
- `rel_deck`: six lists of `0x20` bytes at `0x08ebed00`: 0 main, 1 extra (Fusion and Synchro go there), 2 side (written to the stored deck at `+0x0c`, `+0xa2`, `+0x84`), 3 trunk, 4 a copy of list 2, 5 save-card-list entries that are not in the deck. Entries are 6 bytes: id, image index in `fileTbl.dat`, copies (`& 0x7f`) and flags `0x80` (from the save card list), `0x20` (key card, stored in the list at stored deck `+0x114`: supports the key-card hypothesis), `0x40` (in the owner's original recipe, read at `+0x48d0`). The scene transition word carries the owner type and slot; there is an 8-deep undo stack; filters are a predicate table; the text search is Boyer-Moore-Horspool with katakana→hiragana folding. Families: `editor_lists` 25, `card_move` 16, `editor_main` 11, `text_search` 24, `filter_predicates` 7, `key_cards` 5, `recipe_cards` 4.
- Seven 8-byte stubs at `0x08eb81c0`–`0x08eb81d0` and `0x08ebb278`–`0x08ebb288` lie outside the `libehsys_rel` block: they read as imports of `libdeck_tutorial_rel` and `librecipe_viewer_rel`, which `tools/prx_imports.py` did not resolve. **Resolved on 2026-10-31 (round 2):** the cause was that these libraries are exported by sub-modules that are not loaded in Ghidra (`rel_decktutorial.prx`, `rel_recipeviewer.prx`), and the seventh stub (`0x08eb81b8`) is the Sony NID `0xe7c27d1b` of `sceRtc`, which `BOOT.BIN` does not import. `prx_imports.py` now names them from `re/game-libs.csv` (`thunk_deck_tutorial_start/update/draw`, `thunk_deck_recipe_viewer_start/update/draw`, `thunk_sceRtcGetCurrentClockLocalTime`); the hand-made `deck_call_*` rows were removed.

## Documented functions

The functions of this group that reached the `documented` stage in the 2026-10-31 documentation round and in the 2026-11-03 round (prototype, purpose, return value, side effects and callers, read from the decompilation) are listed in [`functions/deck.md`](functions/deck.md).

## Functions documented in the 2026-11-03 round

The deck editor (`rel_deck`) moves cards between six lists: 0 main, 1 extra, 2 side, 3 trunk, 4 an alias of 2 used by the second pane, and 5 the pool of save "card list" items. An entry is 6 bytes: id, image index, copies (bits 0–6 of byte 4) and flags. Byte 4 bit 7 marks a card-list item, byte 5 bit 5 a key card, and byte 5 bit 6 a card from the owner's recipe. All moves use the 0x250-byte move record `*0x08ebe3b0`. It holds the source pane and list, up to three candidate targets with "full" flags, the selected target, a copy of the entry, the Bézier points `+0x230`/`+0x238`/`+0x240` and the drawn position `+0x248`/`+0x24a`, and the menu window descriptor `+0x24c`. `deck_update_card_move` (`0x08e9ee94`) runs the record's state machine (low nibble of byte 0); sub-steps sit in the high nibble:

- **1:** `deck_animate_card_move_flight` (`0x08e9f608`) flies the card from its list to the menu over 10 frames on a quadratic Bézier curve, and removes it from the source list.
- **2:** the menu window opens.
- **3:** `deck_handle_card_move_input` (`0x08e9f27c`) handles input. Left and Right cycle the targets, Up and Down scroll the target pane. Confirm pushes an undo record and goes to 6; cancel goes to 4.
- **4:** cancel. The card is put back at its old view position.
- **6, then 5:** the window closes once the target slot is placed.
- **7:** `deck_finish_card_move` (`0x08e9fa64`) flies the card to its target slot and drops it (`deck_drop_card_move`).
- **8:** the move is freed, and the last target is remembered in `0x08ebe3b4`/`0x08ebe3b6`.

There are three ways to start a move:

- **Confirm in browse mode**, `deck_start_card_move` (`0x08e9d310`). It builds the menu targets and enforces the rules: 3 copies per name, the card limits (`deck_get_card_limit`), the forbidden-card allowance (1 after progress flag `e9` bit 0), "full" at 20 extra or side cards and at more than 64 main cards, and no moving the owner's recipe cards while editing another character's deck. A non-zero result is shown as deck message 2.
- **R + confirm**, `deck_start_card_transfer` (`0x08e9e720`). It sends the card straight to its default list (trunk or pool, or main or extra) and enters state 7 directly.
- **Undo**, `deck_start_undo_move` (`0x08e9e23c`). It pops the 8-entry undo stack and replays the record backwards.

`deck_editor_handle_browse_input` (`0x08ea0b60`) maps the browse-mode buttons:

| Input | Action |
| --- | --- |
| D-pad | Moves the cursor. |
| Hold L | Scrolls the pane. |
| Hold R | Tool input (`deck_editor_handle_tool_input`). |
| Confirm | Starts a card move. |
| Cancel | Runs the legality check (`deck_check_deck_legality`) before leaving. |
| Triangle | Opens the command menu. |
| Square | Cycles the list. |
| Select | Toggles between grid and list layout. |

The session is loaded by the list builders (`deck_build_main_deck_list` `0x08e9ad8c`, `deck_build_side_deck_list` `0x08e9aff0`). They re-mark the save card-list items, matching save card-list state 1 to the main deck and state 2 to the side deck. `deck_commit_editor_to_slot` (`0x08e9cbd0`) writes the session back when the editor closes. The deck goes to the slot. Card-list items get state 1 (main), 2 (side) or 3 (extra), and pool items get state 4. The "new" state of every card that was looked at is cleared. The edit block and the layout are also saved.

The recipe viewer and the deck tutorial are separate modules (files `0x1b` and `0x12`), run as editor sub-screens by `deck_run_recipe_viewer` (`0x08ea9cc4`) and `deck_run_deck_tutorial` (`0x08ea9fc8`). The recipe viewer receives `deck_save_to_stored_deck` and `deck_load_deck_into_editor` (`0x08e9c760`) as callbacks. `deck_load_deck_into_editor` first returns the current deck to the trunk (`deck_return_deck_cards_to_trunk`, `0x08e9c258`), then takes each card from the trunk or the pool and silently skips cards the player does not have. In `BOOT.BIN`, `deck_check_deck_valid` (`0x0885c660`) is the stand-alone validity check that `rel_title` uses. It returns 0 for an invalid deck, 1 for a valid one, and 2 when the deck is valid only by counting save card-list items. `duel_setup_load_decks` (`0x08836358`) fills the duellist records (see `formats/deck.md`). For a player record it also writes the deck to block `+0` and 99 `u16` values to block `+0xc0`, taken from save state `+0x162bc` for code 465 or set to 4 otherwise. This header part of the 0x858-byte set-up block was unmapped until now. Open question: the meaning of those 99 values.

## Deck tool modules (round 6, 2026-11-04)

The deck-related library modules are now in the Ghidra project and documented, each with a module document: `rel_deckswap` (side decking between duels: a cut-down copy of the editor with main, extra and side lists; leaving requires the original counts; 90-second limit in network play), `rel_decktutorial` (the deck-building tutorial; its "wait button" opcode presses the button itself and opcode `0x13` sets the text-search query, correcting `docs/formats/deck.md`; the tutorial deck comes from a sample table at module `+0x212ac`, not from the save, and the save's per-card flags are backed up and restored), `rel_recipeviewer` (three tabs: 50 stored decks, unlocked recipes 1-461, imported decks of 0x1c0 bytes; three modes) and `rel_select_card` (card picker with three modes: the story's 99-card list, the conversion machine and labo, and the wireless trade). See `modules/rel_deckswap.md`, `modules/rel_decktutorial.md`, `modules/rel_recipeviewer.md`, `modules/rel_select_card.md`, and for `rel_limitlist` (forbidden lists imported from the Memory Stick) `modules/rel_limitlist.md`.

## Open questions

- What deck slot 0 holds, and which slot `save_get_partner(0)` (`0x088550c8`) returns for the current partner (`deck_get_member_slot` gives slot 1 for member 0 and that slot for any other member).
- Answered 2026-10-30: recipes 462–660 are never loaded (set-up codes and draft blocks, `deck.md`), and the owner id is the story character id. Still open: what `stage` and the mode of `deck_select_owner_variant` are.
- See also the list at the end of `docs/formats/deck.md`.
