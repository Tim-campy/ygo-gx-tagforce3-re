# Card effects (work package 4)

## Architecture

**Card effects are native code in the duel-engine module `gmodule/rel_duel_eng.prx`, reached through per-card handler tables and, for the rest, through card-id compare chains. There is no script interpreter.** Confidence: high for the table mechanism, medium for "no other mechanism".

1. **Handler tables.** Four tables of 24-byte records `(card id, five handler addresses)`, sorted by id, are searched by `duel_effects_find_record`; small wrappers call one handler slot each. Layout, lookup and the selector rules are in `docs/formats/effect-tables.md`. 2,233 of the 2,940 cards with effects have at least one record.
2. **Compare chains.** 1,379 functions in the module compare a card id with constants (17,223 instructions). The largest have hundreds of distinct ids and no jump tables, so they are `if (id == A || id == B …)` chains: card-group predicates and per-card exceptions (for example `duel_effects_select_record_variant`). 571 functions test exactly one id; 358 of them have no direct caller, i.e. they are handlers reached through the tables.

Evidence for the overall picture: the module loads a card id as an immediate 19,597 times (2,861 distinct ids), and normal monsters, which have no effect, almost never appear (82 ids). `BOOT.BIN` has 1,996 such instructions (840 ids), not yet classified.

## How a handler is written: Pot of Greed

Pot of Greed (`0x12ec`) shows the pattern behind both the handler tables and the compare chains.

- Its S/T record's slot `+04` is `duel_effects_resolve_draw` (`0x09c78270`), shared by 44 cards: the controller draws `duel_effects_get_draw_count(ctx)` cards through `duel_core_draw_cards`. A negative count makes the opponent draw, and card `0x12da` swaps the player.
- Its slot `+0c` is `duel_effects_can_activate_draw` (`0x09c56d70`), shared by 17 cards: the effect may be activated when `duel_core_can_draw(controller, count)` holds.
- `duel_effects_get_draw_count` (`0x09c779bc`, 2,228 bytes) is a compare chain from card id to the number of cards: Pot of Greed is among the ids that return 2; some cards compute the number from the game state (for example 5 minus the hand size), and some return negative values.

So **handlers implement effect families, and the per-card numbers live in compare chains keyed by card id.** This explains why most effect cards appear as instruction immediates and why handlers are widely shared. For the port, this suggests a data-driven design: one implementation per family plus a per-card parameter table extracted from the chains. `tools/effect_params.py` now extracts such tables from the module: the target-filter flag word of 410 slot `+08` records (every bit decoded), the 120 draw-count cases, and 20 further parameter chains (Life Point costs, discard counts, Spell Counter costs, Standby Phase costs); see "Per-card parameters in code" in `docs/formats/effect-tables.md`.

The `ctx` structure passed to handlers starts with the card id (`u16` at `+0`); bit 0 of `+2` is the owner and bit 6 of `+3` a control-switch flag, so the controller is `owner ^ switched`; `(u16 at +2 & 0xfff) >> 6` is a 6-bit event code, and bits 1–5 of `+2` the field slot (the context is a chain link, `duel_core.md`) (Mirror Force's condition tests `0x12` together with "the attacker is the opponent"; `duel_effects_find_record` tests `0x24`); bits 4–5 of `+3` are the table selector; when bit 0 of `+6` is set, `+0x18` holds the effective card id (`duel_core_get_effective_card_id`, for copied effects). Confidence: medium for field meanings.

## Loading the module in Ghidra

`rel_duel_eng.prx` is relocatable. It is imported into `ghidra/TF3.gpr` with the ghidra-allegrex loader at image base `09be1400`, the address it had when the PPSSPP symbol export (`ghidra/symbols.sym`) was taken. The base was found by matching Ghidra's function offsets and sizes against the export: 1,767 functions agree at `0x09be1400`, against at most 3 for any other base. A different load order could move the module; re-check the base with any new export.

```
analyzeHeadless ghidra TF3 -import extracted/umd/PSP_GAME/USRDIR/gmodule/rel_duel_eng.prx -loader-imagebase 09be1400
python3 -I tools/sym_to_names.py ghidra/symbols.sym --range 09be1400-09deb598 --create-unnamed > re/names-ppsspp-duel_eng.csv
```

Then `ApplyNames.java` with `re/names-ppsspp-duel_eng.csv` and `re/names-duel_eng.csv`, and `ExportFunctions.java`; the module's functions are appended to `re/functions.csv` (7,208 functions; their addresses do not overlap `BOOT.BIN`).

Layout: `.text` `0x09be1400`–`0x09de415b` (2,108,764 bytes), `.sceStub.text` `0x09de415c`–`0x09de71fb` (1,556 import stubs, all from `BOOT.BIN`'s `libehsys_rel`; PPSSPP cannot name them, `tools/prx_imports.py` resolves every one, see `system.md`), `.data` `0x09deb598`–`0x09e01e0f`. After the PPSSPP names, apply `re/names-imports-duel_eng.csv` before `re/names-duel_eng.csv`, then `ApplySignatures.java re/documented-duel_eng.tsv`.

## Key functions

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x09ce2e54` | `duel_effects_find_record(card, …) → record` | H | Table choice from the selector, binary search on the id with a 6-word stride, walk back to the first duplicate, add the variant index. 18 callers. |
| `0x09ce28ec` | `duel_effects_select_record_variant(card) → index` | M | Called only by the lookup; a chain of per-card-id rules returning a variant index. |
| `0x09ce30a4`, `0x09ce3174` | `duel_effects_call_handler_08`, `…_08_b` | M | Call slot `+08` with `(card, player, index)` unless the card's state bit 3 is set; separate recursion counters. 25 and 158 callers. |
| `0x09ce3048`, `0x09ce3c30` | `duel_effects_call_handler_0c`, `…_0c_b` | M | Call slot `+0c` with two arguments; return 1 when there is no handler. |
| `0x09ce3da0` | `duel_effects_check_optional` | H | Calls slot `+10`, the **activation step** (costs, once-per-turn marker, yes/no prompt of optional triggers; `chain.md`); returns 1 without a handler. The name predates that finding. |
| `0x09ce3e24` | `duel_effects_call_handler_14` | M | Calls slot `+14`. |
| `0x09ce2ff0` | `duel_effects_has_table3_record(id)` | M | Builds a temporary card with selector 3 and returns whether a record exists. |
| `0x09ce27c4` | `duel_effects_check_rule_list()` | M | Calls 112 `(function, argument)` pairs at `0x09dedaf8` and returns 1 if any returns non-zero. |

## Open questions

- What each handler slot and each of the four tables means; which wrapper serves which duel phase. Slots `+04`, `+10`, `+14` and the selector are now explained by the chain machinery (`chain.md`): `+10` is the activation step, selector 0 = activation of a spell/trap card, 1 = field monster effect, 2 = hand/Graveyard trigger, 3 = ignition effect.
- Chain building, spell speed, negation and once-per-turn tracking: see `chain.md` and its open questions.
- The card structure (`card + 0` id, `+2`, `+3` selector bits, `+0x15`): this is WP4's central data structure and should be typed in Ghidra next.
- The per-player, per-slot state at `0x09e2a56c` (`player × 0xb3c + index × 0x14`): presumably the field/zone state.
- Classify the `BOOT.BIN` compare chains (AI? deck rules?).
