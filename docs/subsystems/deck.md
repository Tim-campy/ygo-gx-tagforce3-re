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

## Open questions

- What deck slot 0 holds, and how `0x08856730(x)` chooses a slot for `x != 0` (`0x088550c8`).
- Answered 2026-10-30: recipes 462–660 are never loaded (set-up codes and draft blocks, `deck.md`), and the owner id is the story character id. Still open: what `stage` and the mode of `deck_select_owner_variant` are.
- See also the list at the end of `docs/formats/deck.md`.
