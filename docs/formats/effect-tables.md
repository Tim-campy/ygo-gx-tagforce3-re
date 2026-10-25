# Card effect tables (`gmodule/rel_duel_eng.prx`)

Status: `documented` (layout, lookup and dispatch); the meaning of the five handler slots is only partly known. Addresses are runtime addresses with the module loaded at `0x09be1400` (see `docs/subsystems/duel_effects.md`); file offset = address − `0x09be1400` + `0x54`.

## Record: 24 bytes

| Offset | Size | Field |
| --- | --- | --- |
| `0x00` | 4 | Card id (3720–7993). |
| `0x04` | 4 | Handler slot `+04`: **resolution** (the effect itself). Called by `duel_effects_resolve` with `(ctx, arg)`. Example: Pot of Greed's handler draws the card's draw count. Confidence high. |
| `0x08` | 4 | Handler slot `+08`. Called with `(ctx, player, index)` through five wrappers that have about 280 calling functions between them; skipped when the card's state flag (bit 3 of the word at `0x09e2a56c + index × 0x14 + player × 0xb3c`) is set, presumably "effect negated". Presumably a continuous or "does it apply" check (hypothesis, medium). |
| `0x0c` | 4 | Handler slot `+0c`: **activation condition**. Called with two arguments; a missing record or handler means "allowed" (returns 1). Examples: Pot of Greed's handler checks that the deck holds enough cards; Mirror Force's checks that the opponent is attacking. Confidence high. |
| `0x10` | 4 | Handler slot `+10`. Called with two arguments. |
| `0x14` | 4 | Handler slot `+14`. Called with two arguments. |

In the module file the handler words are unrelocated module offsets; the PRX relocation table turns them into addresses at load time.

## Tables

Four tables, each sorted by card id; a card may have several consecutive records (variants).

| Table | Address | Records | Selected when | Contents |
| --- | --- | --- | --- | --- |
| S/T | `0x09dede78` | 938 (`0x3aa`) | selector 0, or selector 2 with field `0x24` | Spells and traps. |
| M1 | `0x09df3680` | 869 (`0x365`) | selector 1 | Mostly effect monsters. |
| M2 | `0x09df8810` | 365 (`0x16d`) | selector 2 otherwise | Monsters. |
| M3 | `0x09dfaa60` | 428 (`0x1ac`) | selector 3 | Monsters. |

The counts are the bounds hard-coded in `duel_effects_find_record`. A static scan of the module (records whose id is a real card and whose five words are 0 or code offsets) finds 2,542 records in these ranges, covering 2,233 of the 2,940 cards that are not normal monsters; no normal monster has a record. The difference to the hard-coded counts comes from records whose id is not in the card database (the scan stops at them).

The selector is bits 4–5 of byte `+3` of the card structure passed in; "field `0x24`" is `(u16 at +2 & 0xfff) >> 6 == 0x24`. What these structure fields mean (effect number? card frame? location?) is open.

## Lookup

`duel_effects_find_record(card, …)` (`0x09ce2e54`):

1. picks the table from the selector as above;
2. binary-searches the table on the card id (`u16` at `card + 0`);
3. walks back to the first record with that id;
4. adds the variant index from `duel_effects_select_record_variant` (`0x09ce28ec`), a chain of per-card rules (for example, card `0x1eea` uses `u16 card[6] − 1`; card `0x1da5` picks variant 1 or 2 from the same `>> 6` field);
5. returns the record, or 0.

Wrappers then call one slot each: `duel_effects_call_handler_08` / `_08_b` (`0x09ce30a4`, `0x09ce3174`; 25 and 158 callers, each with its own recursion counter at `0x09e28f80` / `0x09e28f7c`), `duel_effects_call_handler_0c` / `_0c_b` (`0x09ce3048`, `0x09ce3c30`), `duel_effects_call_handler_10` (`0x09ce3da0`), `duel_effects_call_handler_14` (`0x09ce3e24`); `duel_effects_has_table3_record` (`0x09ce2ff0`) only tests whether an M3 record exists. Eighteen functions call the lookup; the slot used by the other eight is not yet established.

## 8-byte lists

Four further tables hold `(u32 card id, u32 handler)` pairs. They were first reported by ygotfToolkit's `effects` command (`docs/PRIOR_ART.md`); the counts below are checked here (records whose id is a real card and whose handler points into `.text`):

| Address | Records | Valid | Order |
| --- | --- | --- | --- |
| `0x09dec554` (`.data` + `0xfbc`) | 686 | 676 | sorted by id |
| `0x09dfd448` (`.data` + `0x11eb0`) | 528 | 523 | unsorted |
| `0x09dfe500` (`.data` + `0x12f68`) | 1,120 | 1,107 | unsorted |
| `0x09e010b0` (`.data` + `0x15b18`) | 67 | 66 | unsorted |

`0x09dfd448` is read by `0x09d2f908`, `0x09d30af8`, `0x09d8efc0` and `0x09d8f0c4`. Together with the 24-byte tables, ygotfToolkit reports 2,872 cards bound to at least one record.

## What the tables are for (hypotheses from card text)

Membership was correlated with phrases in the decoded English descriptions (`tools/cardinfo.py`); "×" is how much more often a phrase occurs among the table's cards than among all cards. These are statistical hints, not yet confirmed by reading the handlers. Confidence: medium.

| Table | Cards | Strongest signal | Reading |
| --- | --- | --- | --- |
| S/T | 930 | spells 440, traps 488; "activate" ×2.6 | Spell and trap effects. |
| M1 | 791 | slots `+08` and `+14`: "flip" ×5 | Summon, flip and continuous monster effects. |
| M2 | 349 | "sent to the graveyard" ×7.1; slot `+08`: "destroyed by battle" ×7.0 | Graveyard and destruction triggers. |
| M3 | 410 | "once per turn" ×7.8–×9.4, "you can" ×3.2 | Ignition (activated) monster effects. |
| list `0x09dec554` | 676 | "deck" ×3.3, "special summon" ×2.6; contains Sangan | Effects that take cards from the deck or summon. |
| list `0x09dfd448` | 499 | 80% traps; contains Kuriboh | Responses and quick activations. |
| list `0x09dfe500` | 1,070 | 62% spells | Unclear. |
| list `0x09e010b0` | 62 | "end phase" in 87% of the cards (×13.8) | End Phase effects. |

The selector of `duel_effects_find_record` therefore picks the category of effect the caller is asking about (0 spell/trap, 1 summon/flip/continuous, 2 graveyard/destruction, 3 ignition), which fits `duel_effects_has_table3_record` forcing selector 3.

Handlers are widely shared: for example, Pot of Greed's slot `+04` handler serves 44 cards and Mirror Force's 75, so many handlers implement generic effect families rather than single cards.

## Open questions

- Roles of slots `+08`, `+10` and `+14`; confirm the table readings above by reading more shared handlers.
- The card-structure fields behind the selector and the `0x24` test.
- The cards with effects and no record in any table: handled by compare chains (1,379 functions in the module test card ids directly)?
- `duel_effects_check_rule_list` (`0x09ce27c4`) walks 112 `(function, argument)` pairs at `0x09dedaf8`; what these global rules are.
