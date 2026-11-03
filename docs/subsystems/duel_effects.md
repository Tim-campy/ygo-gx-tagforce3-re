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

## Classification by callees

`tools/effect_classify.py` classifies every record by the helpers, engine commands and send-batch stores its handlers reach (92 % of the records get at least one category on the resolve slot at depth 3) and ranks the unnamed helpers by how many records reach them; see `effect-classification.md`. `tools/family_split.py` refines the resolve categories of family-shared handlers per card (card-id branches, LP chain decode); the six family handlers named for it (`duel_effects_resolve_reveal_and_destroy_target` and others) are listed with their evidence in `effect-classification.md`, "Family handlers named in this round".

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
| `0x09ce3da0` | `duel_effects_call_activation_step` | H | Calls slot `+10`, the **activation step** (costs, once-per-turn marker, yes/no prompt of optional triggers; `chain.md`); returns 1 without a handler. The name predates that finding. |
| `0x09ce3e24` | `duel_effects_call_handler_14` | M | Calls slot `+14`. |
| `0x09ce2ff0` | `duel_effects_has_table3_record(id)` | M | Builds a temporary card with selector 3 and returns whether a record exists. |
| `0x09ce27c4` | `duel_effects_check_rule_list()` | M | Calls 112 `(function, argument)` pairs at `0x09dedaf8` and returns 1 if any returns non-zero. |

The helpers that handlers call for Life Points, effect records (ATK/DEF changes), counters, continuous negation, attack locks, position changes, coin tosses and dice are listed in `docs/subsystems/effect-helpers-values.md`.

## Function families named in the 2026-10-31 round

Basis and method: `system.md`, same section. 2,611 new `duel_effects` names in `rel_duel_eng`.

- **Effect-table handlers (2,367, mechanical, H for role and cards).** Every still-unnamed function that an effect record or an L1/L4 list points at is named after its slot and the cards whose records use it, from `tools/card_effects.py` (`slots.*.handler`, `lists[]`): `duel_effects_<slot>_<card id>[_<card id>…]` for up to three cards, `duel_effects_<slot>_shared_<first id>_x<count>` for four or more, and `_v2`… when one card has two handlers in the same slot. Slots: `resolve` (`+04`, 691), `target_filter` (`+08`, 301), `condition` (`+0c`, 718), `activation` (`+10`, 143), `target_choice` (`+14`, 81); `list_builder` for L1 (411) and `end_phase_handler` for L4 (22). 1,777 of them serve exactly one card. The name says where the handler is used, not what it does; the body was not read for this name. `0e74` in a name is the placeholder id of `card-effect-spec.md`.
- **Rule list (42).** The 112 function/card-id pairs at `0x09dedaf8` that `duel_effects_check_rule_list` walks (module-relative pointers + `0x09be1400`) give the card behind each rule handler: `duel_effects_rule_<what>_<card>` (M).
- **Candidate predicates (34).** List-builder predicates that take the card entry in `t0` and the argument in `t1`, like `duel_effects_candidate_in_archetype`: `duel_effects_candidate_*`.
- **Target filters (23) and unreferenced filter stubs (8).** The stubs no record points to are named by their flag word (`duel_effects_target_filter_flags_<word>`).
- Smaller: `select_callbacks` 11, `conditions` 10, `activation_checks` 7, `link_predicates` 5, `zone_filters` 4, `link_lp_analysis` 3.

`card_effects.py --check` still passes; the only change in its summary is that three engine-only references moved from `unnamed` to `ai`.

## Documented functions

The functions of this group that reached the `documented` stage in the 2026-10-31 documentation round and in the 2026-11-03 round (prototype, purpose, return value, side effects and callers, read from the decompilation) are listed in [`functions/duel_effects.md`](functions/duel_effects.md).

## Helpers and handlers documented in the 2026-11-03 round

Method: every still-undocumented `duel_effects` function of `rel_duel_eng` (1,480, excluding import stubs) was re-dumped from Ghidra with the current names and read in full, one row per function, in six size bands. all 1,480 reached the `documented` stage; the full rows are in [`functions/duel_effects.md`](functions/duel_effects.md). Per-card handlers with structurally identical bodies were still read one by one: each row states that function's own card id, constants and differences, and the generic slot name (`duel_effects_<slot>_<id>`) is kept. Two size bands were read twice by independent readers; the sampled pairs agree on the branches, constants and return values (for example `duel_effects_target_filter_1328` `0x09c37238`, `duel_effects_condition_14be_1e26` `0x09c5e0dc`, `duel_effects_resolve_destroy_extreme_stat_monster` `0x09c80710`), and the first reading was kept.

Sixteen small L1 list builders only call `duel_effects_test_hand_candidate` (`0x09cd2fb4`, `0x09cd3dcc`, `0x09cd4ad0`, `0x09cd4fd0`, `0x09cd6d6c`, `0x09cd6f08`, `0x09cd70e8`, `0x09cd7478`, `0x09cd7a98`, `0x09cd84ec`, `0x09cd9660`, `0x09cd9e60`, `0x09cdab60`, `0x09cdaf1c`, `0x09cdbd08`, `0x09cdc070`); Ghidra's decompilation hides the predicate, argument, filter and options they pass in `a3`, `t0`, `t1` and `t2`, so they were documented from the disassembly instead (predicate pointer from the `lui`/`addiu` pair, the parameter stored at `sp+0x1c`, filter and options from the delay-slot loads). With them all 1,480 functions are documented.

The first part below covers the 49 largest functions: shared helpers used by many handlers, plus the largest per-card handlers. The later parts list the recurring handler patterns of the smaller size bands.

### Life Point changes

LP effects follow the pattern already seen with Pot of Greed (`duel_effects.md`, "How a handler is written"): a family handler plus a per-card table in code.

- `duel_effects_get_lp_change_amounts` (`0x09c74cbc`, 10,636 bytes) is the per-card table of the LP-change family. It is a compare chain over about 250 card ids. It fills `amounts[2]`, indexed by absolute side, where a negative value is a loss and a positive value a gain. The controller is the owner xor the control-switch bit, and it is inverted when the effective card id is `0x12da`. The kinds of amount are:
  - fixed damage to the opponent, from −200 to −3000;
  - fixed gains, from +200 to +4000;
  - amounts that hit both players;
  - a count multiplied by an amount: Graveyard or face-up monsters by archetype, attribute or race, hand size, spell/trap count, counters;
  - stats of the card instance stored in the link (`u32 +0x14`, looked up in the instance table `0x09e2bbcc`): printed ATK/DEF, half of them, or Level × amount;
  - battle values: the attacker `0x09e28620`/`0x09e2863c`, and the battle-damage words `0x09e286e0`/`0x09e286f4`;
  - values that the activation step saved in the link (`u16 +0x08`, `+0x0a`, `+0x0c`, `u32 +0x14`).

  An id not in the chain leaves both amounts at 0. Callers: the resolve handler `duel_effects_resolve_lp_change`, conditions, and the AI (`ai_estimate_lp_change`).
- `duel_effects_get_link_lp_change_signs` (`0x09bf4984`) gives the direction of the change for a pending link. For links whose resolve handler is `duel_effects_resolve_lp_change`, `_shared_1450_x5` or `_shared_1370_x7` it asks `get_lp_change_amounts`. For about 80 other cards it sets ±1 per side from its own rules (selector, event code, link words). `duel_effects_get_link_damaged_sides` / `_gain_sides`, documented in the previous round, are built on it.
- **LP costs** come from the compare chain `duel_effects_get_lp_cost` (`0x09c41400`). It has fixed costs from 100 to 5000, selector- and event-dependent costs, half the controller's LP, LP − 100 (`0x1bde`), and a battle-ATK difference (`0x1ef2`). It returns 0 in four cases: for event code `0x24` (activation without cost), for a copy made by `0x1935`, for monster-zone sources linked by `0x1ebb`, and for hand spells while `0x17a3` is active.

### Costs

Cost helpers are reached as activation steps (slot `+10`) or from `duel_effects_cost_monster_activation`. They share three conventions. Event code `0x24` and copies made by `0x1935` skip the cost. Multi-frame costs step the sub-step counter `0x09e28f6c` and return 0 while they wait. A finished cost returns 1, and a cancelled one returns −1.

- `duel_effects_get_discard_count` (`0x09c41c38`) gives the number of cards to discard: 5, 2, or 1 for 115 cards. `duel_effects_cost_discard` (`0x09c42afc`) contains its own copy of the same table and calls `duel_core_request_discard_cost`.
- `duel_effects_cost_tribute` (`0x09c43d68`) runs a two-step Tribute selection. It uses the card's own slot `+08` filter, a hint that can name a required card, and `duel_core_tribute_monsters`. It saves per-card data from the Tributed monster into the link (printed ATK, Level, name, instance) for the resolve handler to use later.
- Cards that offer a choice of effects use `duel_effects_get_available_effect_options` (`0x09c44460`, a bit mask of the options that are currently legal) and one of two activation steps:
  - `duel_effects_activation_shared_1298_x19` (`0x09c44e70`): asks with `duel_core_ask_option`, stores option + 1 in `u16 +0x0c`, posts command 8, then pays the cost of the chosen option;
  - `_shared_1388_x7` (`0x09c47560`): the same with a cancel option, text `0x1ac`.
- `duel_effects_activation_shared_16cd_x5` (`0x09c48860`) runs the "reveal cards from the hand" cost.

### Activation locks and negation state

- `duel_effects_can_activate_card` (`0x09c526d0`) is the entry test for activating a hand card or a Set card:
  - **Hand monsters:** need `card_db_has_hand_effect`.
  - **Hand traps:** need an explicit permission.
  - **Hand spells:** a normal spell needs the turn player in a Main Phase.
  - **Set cards:** a card Set this turn cannot be activated.

  It then tries every queued timing event: it writes the event code into the link and the event argument into `u32 +0x14`, then calls `duel_effects_can_respond_in_window` and `duel_effects_can_activate`.
- `duel_effects_is_activation_locked` (`0x09c52f60`) collects every continuous rule that forbids an activation: player-wide effects on slot 11, markers such as `0x1679` (value 1 = monster effects, 2 = spells/traps), counter costs, the draw lock of `duel_effects_get_activation_lock_level`, and about 40 lock cards. For the human side it writes the UI reason `0x14` to `0x09e2d288`.
- **Continuous negation is recomputed, not stored per effect.**
  - `duel_effects_collect_negation_state` (`0x09c54a84`) builds a 17-word summary. It holds trap and spell negation per side (trap words: 1 = all traps, 2 = all traps except `0x1302`), monster-effect negation per side with timestamp thresholds, flip-effect negation, four player-0 rule words, and override words.
  - Monster-based locks are applied in placement-timestamp order (slot `u16 +0x04`), so an older lock can negate a newer one.
  - `duel_effects_update_negated_slots` (`0x09c553e0`) turns the summary into slot flag bit 8 for all 22 slots. With argument 0 it posts `duel_core_set_slot_negated`. With a non-zero argument it only flips the bit; the AI uses this to simulate.
- `duel_effects_is_negated_on_resolution` (`0x09c55d04`) is the test that `duel_core_chain_step` runs before a link resolves. It checks:
  - flip-effect negation;
  - the source's flag bit 8 or marker `0x1636`;
  - the `0x1679` markers and `duel_effects_is_negated_by_active_locks`;
  - attribute-specific locks;
  - Graveyard protection: while `0x159d` is active, an effect that touches a Graveyard (`duel_effects_get_link_affected_sides`, `0x09bf5b40`, a 2-bit mask: bit 0 own, bit 1 opponent) is negated unless the side has `0x158b`.
- Two related predicates came out of the same reading:
  - `duel_effects_can_target_slot` (`0x09bff424`) holds the shared "cannot be targeted" rules.
  - `duel_effects_can_destroy_slot` (`0x09bffa5c`) holds the "cannot be destroyed" rules. It returns 1 when the card can be destroyed and the caller's `protected_result` when a protection applies.

  `duel_effects_get_controlling_side` (`0x09bfe224`) works out control from the slot's effect-record list: equip links, source links, and temporary or lasting records of control-changing cards.

### Fusion and Ritual resolution

These functions confirm and extend `summon.md` (both sections).

- `duel_effects_resolve_fusion_summon` (`0x09cbace0`) is a state machine on `0x09e28f60`. Its states, in order:
  - `0x80`: checks;
  - `0x7f`/`0x7e`: Extra Deck choice, material count and variant;
  - `0x7d`: the optional Chain Material dialog;
  - `0x78`/`0x77`: material selection;
  - `100`: field materials;
  - `99`: other materials, one per frame;
  - `0x32`: command `0x4e` and the Special Summon with flags `id << 16 | 1`;
  - `1`: Deck shuffle.

  Material count: hard-coded 5 for `0x1e7e` and `0x157e`, 4 for `0x1ab3` and `0x19ef`. Otherwise it comes from the recipe table `0x09debe98`, 138 records: 3 materials when the third material code is non-zero, else 2.

  Materials go to:
  - the Deck for `0x1c31`, `0x0ea8` and `0x0ea3`;
  - the banished zone for variant 8 and for `0x1cd5`, `0x1a7f`, `0x1921`, `0x1920`, `0x149c` and `0x0ea4`;
  - the Graveyard otherwise.
- `duel_effects_resolve_miracle_contact` (`0x09cbd838`) has the same structure but returns the materials to the Deck. Its summon flags lack bit 0.
- `duel_effects_resolve_future_fusion` (`0x09cbc3f4`) splits the work over two resolutions:
  - **Activation:** sends the materials from the Deck, with one kind-3 marker per material instance and a turn-counted marker (`0x41`) holding the Fusion id.
  - **Later turn:** reads that marker and summons the Fusion. It then links the Fusion to the card with a kind-7 marker (`0x17`).
- `duel_effects_is_valid_fusion_material` (`0x09cb9af0`) is the per-variant source test (variants 0–8). After it, a candidate is accepted only if it:
  - is not prohibited;
  - matches an open material slot;
  - has not already been picked;
  - if no monster zone is free, frees one.
- `duel_effects_is_valid_ritual_tribute` (`0x09ccc718`) implements the Level rule described in `summon.md`. It uses `0x09e28f64` (Level still to cover), `0x09e28f68` (smallest Level used) and `duel_effects_ritual_level_search`, plus three exceptions: `0x1c14` covers everything when its Attribute matches, and four ritual spells start the minimum Level at 1 (exact total).
- `duel_effects_resolve_advanced_ritual_art` (`0x09cce41c`) sends Normal Monsters from the Deck until the Level reaches exactly 0, using `duel_effects_level_subset_sum_exact` through its candidate builder.
- `duel_effects_list_builder_19ad` (`0x09cd5d60`) runs the same exact-sum test for Graveyard Ancient Gear monsters.

### Target choice and candidate lists

- **Slot `+14` target-choice handlers** step `0x09e28f70`, return 0 while busy and return 1 when done. A chosen card is appended as a link target in this form: side | location << 1 | instance << 5 | generation << 14. The first five targets go into `u16 +0x08…`. Later targets go through command `0x28` into the extra-target ring, and `u16 +0x12` keeps the ring base. Each target also gets a target marker.

  Examples are `duel_effects_target_choice_shared_0eb7_x31` (`0x09cc3374`, list mode and hint per card) and `duel_effects_target_choice_1935` (`0x09cc88e0`). The second stores the copied card as target 5 and then runs that card's activation step and target choice under its id.
- `duel_effects_get_target_prompt_text` (`0x09cbf5c4`) maps about 400 card ids to about 48 hint messages and shows the hint. It returns nothing.
- `duel_effects_get_candidate_param` (`0x09cc0dd0`) extracts, per card, the parameter that a card passes to its candidate builder.
- `duel_effects_collect_graveyard_candidates` (`0x09ccf768`) is the Graveyard scanner behind 119 callers. Its filter and option bits are listed in its row: same/different name, kind, icon, entry flags, Normal/Effect monster, properly summoned, Special-Summonable.

### Multi-frame resolve handlers

Every large resolve handler read here follows the convention in `chain.md`: the handler receives the sub-state `0x09e28f60` (`0x80` at the start) and returns the next sub-state, or 0 when it has finished. Scratch counters live in `0x09e28f64`/`0x09e28f68`. Examples:

- `duel_effects_resolve_summon_tokens` (`0x09c795f0`): the token id, count and position come from `duel_effects_find_token_entry`.
- `duel_effects_resolve_union_equip` (`0x09c91cd0`): equip-link kind 11 for Union monsters, 10 otherwise.
- `duel_effects_resolve_15fd` (`0x09c941a8`): activates a Graveyard spell/trap as a nested link in the temporary link `0x09e28e1c` and runs that link's activation step, target choice, negation check and resolution in turn.

#### Open questions (the 49 largest functions)

- `duel_effects_get_controlling_side`: what the three modes mean exactly (0, 1, 2), and why the walk is skipped while card `0x1632` is active. Confirm in PPSSPP with a Snatch Steal-type equip.
- Collect-negation state words 10–13 (player-0 effects `0x1351`, `0x1350`, `0x134f`, `0x134e`) and word 14 (`0x12bf`): which cards these are, and why only side 0's player slot is read.
- `duel_effects_update_negated_slots` decides with flag bit 9 (always negated) and slot byte `+0x02` bit 6. Neither writer has been found.
- `duel_effects_resolve_15fd` state `0x75`: Ghidra shows a test on the return value of the void helper `duel_effects_update_negated_slots_default`. Check the assembly. Also find what `0x09e28e40 == 0x10` (immediate return) means.
- `duel_effects_resolve_146b`: the meaning of `0x09e2bba0` bits 0–1 and of command `0x19` with `b = 1`.
- Link byte `+7` bits 1–7 count stored target values next to the target count in byte `+6`. Document how they differ in `chain.md`.
- Target-choice list modes (`duel_core_open_card_list` mode 6 + n, `0x27` + n, `0x2a`, `0x2b`, `0x48`): give each a meaning in `ui.md`.
- `duel_effects_target_choice_shared_0eb7_x31` reads the list mode from an uninitialised register for ids outside its chain. Check whether all 31 users are in the chain.
- `duel_effects_is_activatable_in_window` (`0x09bf2910`): what event codes `0x0d`–`0x16` mean as response windows. The response-window event list is still incomplete in `duel-phases.md`.
- `duel_effects_cost_tribute` and `duel_effects_activation_shared_1298_x19` are reached through tables and a handful of callers. List their effect-table users with `tools/card_effects.py`.

### Recurring patterns (functions of about 700-1,300 bytes)

- **Inlined "add a list target" block.** Target-choice handlers that target cards outside the field (Graveyard 0x0e, banished 0x0f) do not call `duel_effects_add_link_target`. The same sequence is inlined in each of them: build the target entry (side bit 0, location bits 1-4, instance bits 5-13, incarnation bits 14-15 from the instance table byte `0x09e2bbce`), store it at link `+0x08 + 2 x (byte +7 bits 1-7)`, save the ring position `0x09e28e4c` in `+0x12` at the sixth target and post command `0x28` (a = 0xffff, c = 0xffff) beyond five, call `duel_core_post_target_marker(side, location, ref, index)`, and increment the target count (byte +6 bits 1-7). Seen in `0x09cc8eb0` (target_choice_1951), `0x09cc12a0` (shared_0ea9_x131), `0x09cc2808` (shared_12ed_x8), `0x09cc39a0` (shared_133b_x4), `0x09cc3d10` (1d1a), `0x09cc4314` (0eb0_138a_18a4), `0x09cc569c` (14c2), `0x09cc830c` (18f7_191f); `0x09cc7d68` (17f4) uses the storage half for declared values. For the port this is one helper `add_list_target(link, owner, location, ref)`.
- **Cost waived for copied or free activations.** Activation steps (slot +10) return 1 (done) and one target filter accepts any slot at once when the event code is `0x24` or when the link's instance shows card `0x1935` while the link card is another id (an effect copied by 0x1935): `0x09c47fc8` (162d_1631_1634), `0x09c493e0` (shared_14d7_x13), `0x09c4a994` (188d), `0x09c4ac24` (0e92_18a3_1dc6), `0x09c50ff8` (1d7c), `0x09c37f10` (target_filter_shared_0e9d_x16). One predicate in the port.
- **Cost loops that build a slot mask in the link.** Activation steps that Tribute or send several monsters keep a per-side 16-bit slot mask in the link (two u16 words, one per side, so the pair reads as the u32 mask `side x 16 + slot` the engine requests take) and post one request at the end: `0x09c4a548` (1870_1871_1872, `duel_core_tribute_monsters`), `0x09c4a994` (188d, idem), `0x09c4ac24` (0e92_18a3_1dc6, `duel_core_request_send_mask_to_graveyard_as_cost`). Highlight/unhighlight uses UI events 0x2a/0x2b.
- **Resolve state machines on 0x09e28f60.** Every multi-frame resolve starts at state 0x80 and returns the next state (0 = finished). The tails are shared idioms: "no candidate" shows hint 0x0d, then the Deck (`duel_core_request_show_deck`) or hand (`duel_core_request_show_hand`) is shown to the opponent and the Deck is shuffled (states 100/0x78/0x6e/0x62 by handler). Examples: `0x09c78804`, `0x09c78bac`, `0x09c8a994`, `0x09c908bc`, `0x09c91124`, `0x09caca5c`, `0x09cb13ec`.
- **"Card still in place" idiom.** Resolve handlers test that the slot named by the link location still holds the link's instance (`ctx+4 bits 5-13` against the slot's instance) and that slot flag bit 3 is clear before acting or before returning the card: `0x09c748a8`, `0x09c7d6a8`, `0x09c7e0f8`, `0x09c7eca8`, `0x09c89294`, `0x09c89e10`, `0x09c8b980`, `0x09cb16c0`, `0x09cb1dcc`. A single `link_card_still_active(link)` helper in the port.
- **Simultaneous effects walk both sides, turn player first** (`side = 0x09e2d1d8 ^ i`): `0x09c826b4` (1331), `0x09c83368` (135b), `0x09c8e2e8` (1516), `0x09cb86d4` (1efe), `0x09cc39a0`, `0x09cc3d10`, `0x09cdeb90` (check_self_destruct_rules), `0x09cdf160` and `0x09ce0218` (rule list handlers).
- **Engine command 8 as the declaration display.** Handlers post command 8 (bit 15 = declaring side) with `a` = kind and `b` = value after a declaration prompt: a = 0 card name (`0x09c90420`, `0x09cb29d8`), 2 option (`0x09c4e104`), 3 Type and 4 Attribute (`0x09cc7d68`, `0x09cb86d4`), 5 number/Level (`0x09c91124`). This matches `duel_core_cmd_show_declaration` (a, b, c passed to the declaration message); hypothesis, medium.
- **Shared filters = base flags + card-id chain.** `target_filter_shared_*` bodies call `duel_effects_target_filter(ctx, side, slot, flags)` with one fixed flag word and then branch on the card id: `0x09c352bc` (0x1014), `0x09c37610` (0x10416), `0x09c37f10` (0x13), `0x09c3eb8c` (0x1010), `0x09c379ac` (0x15). The per-card tail is a Type/attribute/name/Level test, so these 58 records (16 + 17 + 16 + 9) reduce to data (flags + one predicate per card).
- **Fusion set-up duplicated.** The material count special cases (0x1e7e and 0x157e 5, 0x1ab3 and 0x19ef 4, else 2/3 from the 138-record recipe table `0x09debe98`) and the spell-to-variant chain (0x1d15 7, 0x1cd5 3, 0x1c31 6, 0x1a7f/0x1921/0x1920 1, 0x1a7e 2, 0x0ea8 5) are repeated inline in `0x09cba5dc` (check_fusion_materials), `0x09cbd0b8` (resolve_time_stream) and `0x09cbd3e4` (resolve_fossil_fusion); `duel_effects_get_fusion_spell_mode` (`0x09cba1ac`) holds the same variant chain.
- **The extra-target ring as scratch memory.** Besides link targets, handlers store instances (`0x09c83368`, `0x09c8c5b4`), material references (`0x09cba5dc`, `0x09cbd3e4`) and a Level multiset for the exact subset sum (`0x09cd7bac`, list_builder_1b54) at `0x09e28e50 + (0x09e28e4c + i) & 0x7f`, without advancing the write position.
- **Candidate scanners.** `0x09ccf134` (Extra Deck), `0x09ccf428` (one hand card) and `0x09ccfcdc` (banished) share the prologue and the query mode of `docs/formats/search-filters.md`; their bodies differ only in the location list and the options bits.

#### Open questions (functions of about 700-1,300 bytes)

- `duel_core_special_summon_impl` position argument 2 (default of `0x09c78804`, used by `0x09c908bc`, `0x09c826b4`): the player's choice of position? Needs a PPSSPP trace.
- `0x09e2991c`, cleared by `0x09c78804` for 12 cards before the Deck list opens: auto-pick or list mode flag?
- Byte `0x09e290bc` (bit 1 side, bits 2-5 slot) read after a summon by `0x09c7eca8`, `0x09c826b4`, `0x09c83368`: is it "zone of the last placed card"? Confirm in PPSSPP.
- Engine commands `0x58` (`0x09cb6bd4`, a = 0x0d, b = Deck instance) and `0x60` (`0x09c89e10`, a = counter, b = zone): handlers not yet identified here.
- Command 8 = declaration display (above): confirm the case stub in the dispatch table `0x09e00944`.
- Slot flag bit 25 of the attacking monster (`0x09c7d6a8`) and slot flag bit 13 set by `0x09cb13ec`: meanings unknown.
- The per-entry word at player `+0xa0c` (`0x09e2af34 + index x 2`) used by `0x09c87ea0` for a banished card's return (low byte 0x40, side/slot/face/position bits): layout and writer.
- `0x09c7e0f8` sets bit 0 of the responded link's byte +6, which `chain.md` documents as the copied-effect flag; its meaning in that use is open.
- `0x09c8cab8` decrements `0x09e28f64` and waits for zero without initialising it: is the counter reset by the chain driver before each resolve (then the loop ends only when no slot is left)?
- `0x09cc1a14`: card 0x1db4 may start with 1 valid target but its loop asks for 2; intended or a bug of the original?
- `duel_effects_classify_link_targeting` (`0x09bf6f50`) returns classes 0-3 for the AI; their meaning (no target / one / several / other) is not established.
- `0x09bfeca8` (get_spell_immunity): a 0x1693 link from the same side assigns 2 instead of OR-ing it, discarding earlier per-card bits; check against PPSSPP whether that is observable.

### Recurring handler patterns (functions of about 380-500 bytes)

- **Cost-skip prologue.** Activation steps and cost conditions start with the same test: return 1 (or 2 in some
  conditions, 0 in `0x09c5e0dc`) when the event code `(u16 ctx+2 & 0xfff) >> 6` is `0x24`, or when the card-instance
  entry (`0x09e2bbcc + ref x 6`, ref = ctx+4 bits 5-13) is `0x1935` while ctx is not. Seen in `0x09c43330`,
  `0x09c461f8`, `0x09c470f8`, `0x09c490b8`, `0x09c4a2e8`, `0x09c4f7b4`, `0x09c5f7f0`, `0x09c635f8`, `0x09c65e58`,
  `0x09c66390`.
- **Activation-step state machine on `0x09e28f6c`.** Yes/no prompt (`duel_core_ask_yes_no_with_card_name`, message
  `0xfa`), then on "no" command 8 `(a = 9, b = card id)` and -1 on the next frame; on "yes"
  `duel_core_chain_announce_activation`. `duel_effects_confirm_optional_trigger` (`0x09c431ac`) is the shared form;
  `0x09c499a8`, `0x09c48f04` inline it; `0x09c4b8b4`, `0x09c513cc` delegate states 0-4/0-9 to it and continue at 5/10.
- **Selection step pair.** `duel_core_begin_select_target(..., duel_effects_call_handler_08)` then
  `duel_core_is_selection_confirmed` with the pick in `0x09e2d278` (side), `0x09e2d27c + 0x09e2d280` (slot); an
  unconfirmed pick steps the state back (`0x09c43330`, `0x09c461f8`, `0x09c513cc`).
- **Discard-count chain duplicated.** `duel_effects_activation_14ea` (`0x09c470f8`) and `_1c2f` (`0x09c4f7b4`) contain
  the same 17-id discard-count chain (whole hand for 3 ids, 2 for 2 ids, 1 for 9 ids); they differ only in the last two
  arguments of `duel_core_request_discard_cost_to_graveyard` (`0, 1` against `1, 0`) and the once-per-turn marker
  `0x0fb6` posted by `_1c2f`.
- **Multi-frame resolve handlers on `0x09e28f60`.** Start at `0x80`, return the next state, 0 ends; typical ladders
  `0x80 -> 0x7f -> 0x7e -> ...` (`0x09c79f38`, `0x09c7aa94`, `0x09c7ac70`, `0x09c7f164`, `0x09c82510` down to
  `0x63`). `0x09c7ff78` delegates to `duel_effects_resolve_revive_target` by shifting the state by +2 and back.
- **Timing-event queue walk.** Filters and conditions loop over `0x09e28fa0[i]` (codes), `0x09e28fc0[i]` (arguments)
  for summon events 6/7/8 and decode the argument as instance bits 0-8, side bit 9, slot bits 10-13, controller =
  bit 9 xor bit 16 (`0x09c3a900`, `0x09c3fe70`, `0x09c3e7e4`, `0x09c3d8b0`, `0x09c51ea0`, `0x09c69d78`).
- **"Card still in place" test.** Own-slot instance `((u16 slot+2 & 0x7fff) >> 7) x 2 - (slot+1 bit 6)` compared
  with ctx+4 bits 5-13, plus slot flag `+0x10` bit 2 clear (`0x09c43a24`, `0x09c499a8`, `0x09c624d4`, `0x09c64eac`,
  `0x09c8de5c`, `0x09c8e150`).

#### Open questions (functions of about 380-500 bytes)

- Event codes `0x12`, `0x16`, `0x19`, `0x1a`, `0x1b`, `0x1c`, `0x20`-`0x22` are used by many conditions but are not
  in the timing-code table of `battle.md`; their argument bits 11, 14-23 and 30 are tested without a known meaning.
- `duel_core_draw_cards` returns its count in `v0` that Ghidra shows as `extraout_v0`; its prototype says `void`.
- `0x09c7ac70` reads Deck entry 0 right after posting a draw: confirms that the draw is a queued command and entry 0
  is the next card drawn (to verify in PPSSPP).
- Byte `+1` bit 6 of a list entry is compared with a side in `0x09c88730` (original owner?).
- The flag word `0x09e28f84` (`0x09c66390`) and `0x09e2bba0` bits 0-1 (`0x09c5ae2c`, `0x09c80380`, `0x09c87a78`).

## Open questions

- What each handler slot and each of the four tables means; which wrapper serves which duel phase. Slots `+04`, `+10`, `+14` and the selector are now explained by the chain machinery (`chain.md`): `+10` is the activation step, selector 0 = activation of a spell/trap card, 1 = field monster effect, 2 = hand/Graveyard trigger, 3 = ignition effect.
- Chain building, spell speed, negation and once-per-turn tracking: see `chain.md` and its open questions.
- The card structure (`card + 0` id, `+2`, `+3` selector bits, `+0x15`): this is WP4's central data structure and should be typed in Ghidra next.
- The per-player, per-slot state at `0x09e2a56c` (`player × 0xb3c + index × 0x14`): presumably the field/zone state.
- Classify the `BOOT.BIN` compare chains (AI? deck rules?).
