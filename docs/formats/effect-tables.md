# Card effect tables (`gmodule/rel_duel_eng.prx`)

Status: `documented` (layout, lookup and dispatch); the meaning of the five handler slots is only partly known. Addresses are runtime addresses with the module loaded at `0x09be1400` (see `docs/subsystems/duel_effects.md`); file offset = address − `0x09be1400` + `0x54`.

## Record: 24 bytes

| Offset | Size | Field |
| --- | --- | --- |
| `0x00` | 4 | Card id (3720–7993). |
| `0x04` | 4 | Handler slot `+04`: **resolution** (the effect itself). Called by `duel_effects_resolve` with `(ctx, arg)`. Example: Pot of Greed's handler draws the card's draw count. Confidence high. |
| `0x08` | 4 | Handler slot `+08`: **target filter**, "is field slot `index` of `player` a valid target for this card". Called with `(ctx, player, index)` through five wrappers that have about 280 calling functions between them; skipped when the slot's state flag (bit 3 of the word at `0x09e2a56c + index × 0x14 + player × 0xb3c`) is set, presumably "effect negated". 410 records (406 cards) use a stub that jumps to `duel_effects_target_filter` with card-specific filter bits in a3 (272 short `addiu` stubs, 138 `lui`+`ori` stubs; see "Per-card parameters in code"); the others have their own function. Confidence high. |
| `0x0c` | 4 | Handler slot `+0c`: **activation condition**. Called with two arguments; a missing record or handler means "allowed" (returns 1). Examples: Pot of Greed's handler checks that the deck holds enough cards; Mirror Force's checks that the opponent is attacking. Confidence high. |
| `0x10` | 4 | Handler slot `+10`: presumably **"can the optional effect be used"**. Called by `duel_effects_check_optional` with two arguments (1 when there is no handler). Mystic Tomato's handler (shared by 16 cards) returns −1 unless per-card checks pass (for example that the deck holds a suitable card), then continues in `0x09c431ac`; table membership correlates with "you can" (×3.3) and "deck" (×2.7). Confidence medium-low. |
| `0x14` | 4 | Handler slot `+14`: **target choice**. Called with two arguments. The most shared handler (315 cards, `duel_effects_choose_targets`) branches on the duelist kind: the interactive path opens the target-selection UI with the card's slot `+08` filter as the callback, the CPU path asks the AI (`docs/subsystems/ai.md`). Confidence high. |

In slot `+0c`, the handler shared by 149 cards (`0x09ce28e4`) returns 2, so activation conditions return more than a boolean; 2 plausibly means a mandatory or automatic activation, as for flip effects (hypothesis, low).

### Target filter flags

`duel_effects_target_filter(ctx, player, index, flags)` (`0x09c32fb8`) checks one field slot against `flags`:

| Bits | Test |
| --- | --- |
| `0x3` | Side: 1 = the card's controller only, 2 = the opponent only, 3 = a special case (`0x09bfbb38`), 0 = either. |
| `0x4` / `0x8` | Face-up only / face-down only (`u16` at slot `+0x08`). |
| `0x80` / `0x100` | Attack position only / defence position only (`u16` at slot `+0x06`). |
| `0x70` | Zone class: `0x10` monster zones (0–4); `0x50` spell/trap zones (5–9); `0x20`, `0x30`, `0x40` combinations up to the field zone (10) with face-up tests. |
| higher bits | Decoded below (`0x400` targeted, `0x1000` destroy, …). |

Examples, consistent with the card texts: Man-Eater Bug passes `0x1410` (any side, monster zone; it destroys any monster); Mirror Force passes `0x1092` (opponent's side, monster zone, and `0x80`, which matches "attack position" in its text).

This summary is superseded by the full decoding in "Per-card parameters in code" below (the field-slot meanings of `+0x06` and `+0x08` are now established: battle position and face-up).

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

Wrappers then call one slot each: `duel_effects_call_handler_08` / `_08_b` (`0x09ce30a4`, `0x09ce3174`; 25 and 158 callers, each with its own recursion counter at `0x09e28f80` / `0x09e28f7c`), `duel_effects_call_handler_0c` / `_0c_b` (`0x09ce3048`, `0x09ce3c30`), `duel_effects_check_optional` (`0x09ce3da0`), `duel_effects_call_handler_14` (`0x09ce3e24`); `duel_effects_has_table3_record` (`0x09ce2ff0`) only tests whether an M3 record exists. Eighteen functions call the lookup; the slot used by the other eight is not yet established.

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

## Per-card parameters in code

Handlers implement effect families; the per-card numbers sit in code, as immediates of small stubs and as `card id → value` compare chains. `tools/effect_params.py` extracts them from the maintainer's own `rel_duel_eng.prx` at run time (nothing is stored in the repository):

```
python3 -I tools/effect_params.py <USRDIR>/gmodule/rel_duel_eng.prx --check
python3 -I tools/effect_params.py <USRDIR>/gmodule/rel_duel_eng.prx -o extracted/effect_params \
        [--cardinfo <USRDIR>/duelsys/cardinfo_eng.ehp]      # adds a card-name column
python3 -I tools/tests/test_effect_params.py
```

It writes `target_filters.csv`, `target_filter_calls.csv`, `draw_counts.csv`, `compare_chains.csv` and `chain_cases.csv`. The tool carries its own minimal MIPS decoder and a constant evaluator: from a taken chain branch it executes the delay slot and the following straight-line code (ALU operations on known registers, unconditional and decidable branches) up to `jr ra`; anything else (a memory load, a call, a branch on an unknown value) makes the case "computed", and the tool then lists which context fields, globals and functions the code reaches. `--check` verifies the table bounds and ordering, the filter's prologue and size, the draw chain's size and that Pot of Greed (`0x12ec`) maps to 2.

### Target-filter stubs (slot `+08`)

410 of the records in the four 24-byte tables (406 distinct cards) have a slot `+08` handler that is a stub calling `duel_effects_target_filter` with a constant flag word; no other slot and none of the 8-byte lists points to such a stub. Two forms exist:

| Form | Code | Records | Flags |
| --- | --- | --- | --- |
| short | `j 0x09c32fb8` ; `addiu a3, zero, K` (delay slot) | 272 | `K` sign-extended (all observed `K` are positive) |
| long | `lui v0, HI` ; `j 0x09c32fb8` ; `ori a3, v0, LO` | 138 | `HI << 16 \| LO` (bits 16–19) |

Per table: S/T 146 (104 short, 42 long), M1 130 (80, 50), M2 25 (18, 7), M3 109 (70, 39). The records use 131 distinct flag words. A further 203 `jal 0x09c32fb8` sites inside larger handlers exist; 144 of them load a constant flag word next to the call and are listed in `target_filter_calls.csv` with the function that contains them and the table records that reference that function.

### Target-filter flag bits

`duel_effects_target_filter(ctx, player, index, flags)` (`0x09c32fb8`, 2,020 bytes) returns 1 when field slot `index` (0–4 monster zones, 5–9 spell/trap zones, 10 field zone) of `player` may be chosen, else 0. `controller = (ctx[2] & 1) ^ (ctx[3] >> 6 & 1)`. The slot fields below are the 20-byte field slots of `duel_core.md` (`0x09e2a55c + player × 0xb3c + index × 0x14`). The tests run in this order and each failing test returns 0:

| Bits | Test, from the instructions | Meaning | Evidence from card text (`tools/cardinfo.py`) | Conf. |
| --- | --- | --- | --- | --- |
| `0x3` = 1 | `player == controller` | Your side | "you control" in 46 % of the 37 records against 13 % | H |
| `0x3` = 2 | `player != controller` | The opponent's side | "your opponent" 97 % of 175 against 21 % | H |
| `0x3` = 3 | `0x09bfbb38(controller, player, index)` must be non-zero: special-cases The Immortal Bushi (`0x1d06`), then `0x09bfb03c`, which tests Soul Exchange, Mind Control, Summon Priest, Archfiend's Roar … | A monster the controller may Tribute | All 14 records are Tribute costs (Catapult Turtle, Cannon Soldier, Mystik Wok, Horn of Heaven) | H |
| `0x3` = 0 | none | Either side | "on the field" 70 % against 11 % | H |
| `0x4` | `u16 slot+0x08 != 0` | Face-up only | "face-up" 82 % of 100 against 19 % | H |
| `0x8` (only without `0x4`) | `u16 slot+0x08 == 0` | Face-down only | "face-down" 73 % of 37 against 3 % | H |
| `0x80` | `u16 slot+0x06 == 0` | Attack Position only | "attack position" 92 % of 13 against 6 % | H |
| `0x100` (only without `0x80`) | `u16 slot+0x06 != 0` | Defense Position only | "defense position" 80 % of 15 against 9 % | H |
| `0x70` = `0x10` | `index < 5` | Monster zones | "monster" 98 % of 243, "spell"/"trap" ≤ 6 % | H |
| `0x70` = `0x20` | `index ≤ 10`; a monster zone only if slot `+0x10` bit 12; a face-up card must have slot `+0x10` bit 11 set or not be a trap (`card_db_is_trap`) | Spell Cards (face-down cards pass, as for De-Spell) | "spell card" in all 6 (De-Spell, Mask of Dispel, Cyber Prima) | H |
| `0x70` = `0x30` | `index ≤ 9`; monster zone only with bit 12; a face-up card must be a trap; slot `+0x10` bit 11 must be clear | Trap Cards (face-down pass) | "trap card" in all 6 (Remove Trap, Trap Master, Bait Doll) | H |
| `0x70` = `0x40` | `index ≤ 10`; a monster zone only with bit 12 | Spell or Trap Cards, including the field zone | "spell or trap" 76 % of 74 against 1 % (Mystical Space Typhoon, Heavy Storm) | H |
| `0x70` = `0x50` | `5 ≤ index ≤ 9` | Cards in the Spell & Trap Card Zones (not the field zone) | All 5 say "Spell & Trap Card Zone(s)" (Tornado, Straight Flush) | H |
| `0x70` = 0, `0x60`, `0x70` | none | Any card on the field (`0x60` does not occur) | "card on the field" / "1 card" (Raigeki Break, Final Destiny) | H |
| (always) | `u16 slot+0x00 & 0x3fff != 0` | The slot must hold a card | | H |
| `0x400` | `0x09bff424(ctx, player, index)` must be non-zero; it tests the "cannot be targeted" cards (the Egyptian gods, Lord of D., Horus' Servant, King Dragun, Belial, Metalsilver Armor, Turbo Warrior, Vennominaga …) | The effect targets | Mystical Space Typhoon `0x21440` and Raigeki Break `0x21470` have it, Heavy Storm `0x21040`, Mirror Force `0x1092` and Dark Mirror Force `0x2112` do not; "select" 31 % of 278 against 8 % | H |
| `0x800` | when clear, and side ≠ 3, and zone class ∈ {0, `0x10`, `0x70`}, and the counter at `0x09e28f80` (recursion counter of `duel_effects_call_handler_08`) is ≤ 0: reject if `0x09bff318(ctx, player, index)` is non-zero. That function picks a per-card-type test from the effect card's type (trap `0x09bfefe4`, spell `0x09bfeca8`, monster `0x09bff190`); the trap test names Elemental Hero Wildheart, Vennominaga, Tenkabito Shien, Swordsman of Doom Lithmus, The Lady in Wight | Skip the "unaffected by this card type" check | 21 records, mostly lingering effects that select a monster (Spellbinding Circle, Shadow Spell, Riryoku, Copycat); why they skip the check is not established | M (test), L (why) |
| `0x1000` | `0x09bffa5c(ctx, player, index, targeted = flags & 0x400 != 0, nested)` must be non-zero, `nested` = counter `0x09e28f80` > 0 or `0x800` set; it tests the "cannot be destroyed by effects" cards (Field Barrier, Magical Hats, Timidity, Jade Knight, Exodia Necross, Different Dimension Dragon …) | The effect destroys | "destroy" in all 211 records, against 20 % of the others | H |
| `0x2000` | `0x09c001a0(player, index, ctx id)` must be non-zero (skipped when `0x1000` is set and `nested` is 0); special-cases Miracle Jurassic Egg (`0x1a8d`, "cannot be removed from play") | The effect removes from play | All 15 records banish (Nobleman of Crossout, Dimensionhole, Karma Cut) | H |
| `0x4000` | `0x09c0d0d8(player, zone class == 0x10)` and `0x09c0d310(player, 1 << (index + 16 × player))` must be non-zero | The effect sends to the Graveyard | 4 records: Emergency Provisions, Altar for Tribute, White Night Dragon, Volcanic Queen | M |
| `0x8000` | `0x09c0dac8(player, 1 << (index + 16 × player))` must be non-zero | Unclear (return to the hand as a cost?) | 1 record: Shaman of Mist Valley | L |
| `0x10000` | `0x09bfeaa8(player, index, ctx id)` must be non-zero (special-cases Spatial Collapse) | The effect takes control | All 12 (Change of Heart, Mind Control, Creature Swap, Relinquished) | H |
| `0x20000` | reject if the 9-bit value `(u16 ctx+4 >> 5) & 0x1ff` equals the slot's `(u8 slot+1 >> 6 & 1) + 2 × (u16 slot+2 >> 7 & 0xff)` | Not this card itself | Heavy Storm, Mystical Space Typhoon, Emergency Provisions ("except this card"), Summoner of Illusions ("1 other monster") | H |
| `0x40000` | `0x09bfd51c(player, index)`: accept a Defense Position monster; for an Attack Position one, reject if `0x09be9168(player, index, 0x1de1)` | The effect changes the battle position | All 24 (Stop Defense, Book of Taiyou, Earthquake, Black Rose Dragon) | H (meaning), L (the `0x1de1` test) |
| `0x80000` | for a spell/trap zone (`index ≥ 5`): reject if slot `+0x10` bit 4 is set; if bit 1 or bit 3 is set, reject a card that is a link of the current chain (entries of 24 bytes at `0x09e289b4 + 0x300`, count at `0x09e28e38`, test `0x09c2dc2c`) | The effect returns the card to the hand or Deck | All 33 (Giant Trunade, Compulsory Evacuation Device, Phoenix Wing Wind Blast, Penguin Soldier) | H (meaning), M (chain test) |
| `0x200`, `0x100000`+ | not tested | Unused | never set | H |

Two slot-flag bits follow from these tests (see `duel_core.md`): bit 12 of slot `+0x10` lets a monster-zone card count as a spell/trap (tested through `0x09bee9d0`; presumably trap monsters), and bit 11 makes a face-up card count as a spell rather than a trap (presumably cards "treated as" Spell Cards, such as Crystal Beasts in the Spell & Trap Zone). Both are hypotheses, confidence medium.

`card_db_is_trap(id)` is the import `0x09de4a34` → `BOOT.BIN` `0x0885ff60`, which returns `card_db_get_race(id) == 24` (`0x08832db8`: bits 1–5 of byte 6 of the `CARD_Prop` record, i.e. word 1 bits 17–21, the type field, where 24 = trap; `cardinfo.md`).

Statistics: most frequent flag words are "targeted destroy" (106 records), "targeted" (58), "destroy" (49), "targeted destroy not_self" (31), "targeted return" (25); 25 records have no action bit (side/zone/face only). By side: 184 either, 175 opponent, 37 own, 14 Tribute. By zone class: monster 243, spell/trap 74, any 76, spell 6, trap 6, S/T zones 5.

### Draw counts: `duel_effects_get_draw_count`

`duel_effects_get_draw_count(ctx)` (`0x09c779bc`, 2,228 bytes) first computes the controller and swaps it when `duel_core_get_effective_card_id(ctx)` is Mystical Refpanel (`0x12da`); then it compares the raw card id (`u16 ctx+0`) with 120 constants. A positive result is the number of cards the controller draws, a negative one the number the opponent draws (see `duel_effects_resolve_draw`), 0 means none; unlisted cards return 0. 106 cases are constants (`-3` ×1, `-2` ×3, `-1` ×5, `1` ×63, `2` ×28, `3` ×6; Pot of Greed `0x12ec` → 2); 14 are computed:

| Card id | Computation |
| --- | --- |
| `0x16bd` | `−max(0, 7 − hand size of the opponent)` (the opponent draws until 7) |
| `0x1501` | `max(0, 5 − hand size of the controller)` |
| `0x1567` | `max(0, 2 − hand size of the controller)` |
| `0x1e96` | `1` if the event code (`u16 ctx+2` bits 6–11) is `0x15`, else `0` |
| `0x1ce9` | `2` if the event code is 6, else `1` |
| `0x1cf5` | `2` if the table selector (`ctx+3` bits 4–5) is 3 (ignition effect), else `1` |
| `0x1776` | `2` if `u16 ctx+0x0c == 2` (chosen option?), else `1` |
| `0x1d22` | `u16 ctx+0x12` (a count stored in the context) |
| `0x1bf9` | `3` if `u16 ctx+0x12 > 0`, else `2` |
| `0x1966` | `1` or `2` from bit 2 of `ctx+0x16` and bit 1 of `ctx+0x15` compared with the owner (whether the discard was caused by the opponent) |
| `0x18f9` | `0` unless the controller's hand is empty; then `2` if `0x09bf9c2c(controller)` agrees with a test on the card's own slot (bit 2 of slot `+0x10`), else `0` |
| `0x1888` | `1 + 0x09c014ac(controller, id)` |
| `0x17d6` | `1 + 0x09be9168(owner, 11, id)` |
| `0x1dc3` | `0x09bf9f9c(owner, predicate 0x09de4b64)` (a count of matching cards) |

The meaning of the context fields `+0x0c`, `+0x12`, `+0x15`, `+0x16` is not yet established; the port needs them as effect-context fields.

### Other parameter chains

`compare_chains.csv` lists every function (entry points: `jal` targets, table handlers and prologues after `jr ra`) with at least 8 `li rX, id ; beq rY, rX, …` tests: 307 functions. Classified by the constant evaluator: 20 **parameter** chains (at least half of the cases constant and the values not just 0/1; 946 cases in `chain_cases.csv`), 42 predicates (0/1), 1 mixed, 244 unresolved (the tests jump to shared code, i.e. `if (id == A || id == B …)` predicates). The parameter chains whose cards make the purpose clear:

| Function | Size | Cases (constant) | Values | Callers (handlers / cards) | Reading from the cards | Conf. |
| --- | --- | --- | --- | --- | --- | --- |
| `0x09c779bc` | 2,228 | 120 (106) | −3 … 3 | 17 (16 / 171) | Draw count (above) | H |
| `0x09c41400` | 2,104 | 103 (73) | 100 … 5,000 | 20 (14 / 228) | Life Points paid as a cost (Revival Jam 1000, Vampire's Curse 500; computed: "half your LP", "so that you have 100") | H |
| `0x09c41c38` | 1,476 | 119 (119) | 1, 2, 5 | 6 (5 / 70) | Number of cards to discard (Final Destiny 5, Spell Vanishing 2; "discard your hand" cards return 1) | M |
| `0x09c42310` | 204 | 13 (13) | 1, 2, 3, 10 | 6 (6 / 51) | Spell Counters removed as a cost (Mega Ton Magical Cannon 10, Royal Magical Library 3) | H |
| `0x09de2310` | 228 | 18 (18) | 100 … 2,000 | 2 | Life Points paid in each Standby Phase (the Archfiends 500, Imprisoned Queen Archfiend 1000) | H |
| `0x09bf4774` | 528 | 40 (40) | 1, 2, 3 | 2 (2 / 7) | Which players a hand effect affects (3 for Card Destruction, Morphing Jar, Dark World Dealings: both) | M |
| `0x09bf5b40` | 2,680 | 181 (158) | 0 … 3 | 2 | Unknown (mostly 1) | L |
| `0x09cf16d8`, `0x09cf4288`, `0x09cfc34c`, `0x09d36efc`, `0x09d36fb8`, `0x09da0510` | 176–1,484 | 13–55 | small values; `0x09cfc34c` −1 for 50 LP-payment cards | mostly functions in `0x09ce5000`–`0x09dac000`, few of them table handlers | Unknown; per-card scores or categories (an AI use is a guess) | L |
| `0x09c11ea0`, `0x09dabf4c` | 332, 916 | 16, 49 | `0x30000`–`0x1d0000` | — | Return module offsets (pointers), not numbers | M |

Function sizes from this scan agree with `re/functions.csv` for all listed functions except `0x09bf6f50` (1,116 against 1,080).

## Open questions

- Confirm slots `+10` and `+14`.
- Target filter: why the `0x800` cards skip the immunity check; the purpose of bit `0x8000` and of the `0x1de1` test under `0x40000`; confirm slot `+0x10` bits 11 and 12 in PPSSPP.
- The effect-context fields read by the computed draw counts (`+0x0c`, `+0x12`, `+0x15`, `+0x16`), and the computed cases of the LP-cost chain.
- The card-structure fields behind the selector and the `0x24` test.
- The cards with effects and no record in any table: handled by compare chains (1,379 functions in the module test card ids directly)?
- `duel_effects_check_rule_list` (`0x09ce27c4`) walks 112 `(function, argument)` pairs at `0x09dedaf8`; what these global rules are.
