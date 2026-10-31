# Effect helpers: miscellaneous callees of partial resolve closures (work package 4)

`tools/card_effects.py` calls a card **full** when every effect record reaches an effect category and the resolve closure of the record (slot `+04` handler, depth 3, `docs/subsystems/effect-classification.md`) contains no unnamed callee. Before this document 812 released cards were **partial** and 562 of their records reached an unnamed function through the resolve slot. This document names the 183 distinct unnamed callees behind those records (176 in `gmodule/rel_duel_eng.prx`, runtime base `0x09be1400`, and 7 in `BOOT.BIN` reached through import stubs). The other helper families are in `effect-helpers-movement.md`, `effect-helpers-deck.md`, `effect-helpers-values.md`, `effect-helpers-predicates.md` and `ai-helpers.md`.

All addresses are runtime addresses. Evidence is static: Ghidra decompilation of a read-only copy of the project (`Decompile.java`, `DumpWords.java`, `FindRefs.java`; every name checked with `FuncAt.java` to start a function), the card database (`tools/cardinfo.py`) to identify card ids, and the registries. Nothing here has been traced in PPSSPP. Confidence: H (high), M (medium), L (low).

## Method

1. Worklist: the resolve closure of every effect record of a partial card was rebuilt with the classifier of `tools/effect_classify.py` (as `card_effects.py` does) and its unnamed callees counted. 183 distinct functions; the top three (the CPU's yes/no answer chain) alone sat in 121–122 records.
2. Every function was decompiled, together with the code that gives it meaning: the engine command executor `duel_core_execute_command` (`0x09dc0974`) and the handlers of the commands they post, the card-request runner `duel_core_run_pending_action` (`0x09c0e8b8`) and its mode workers, and the prompt-request runner `0x09c14580` with its handler table `0x09debad4`.
3. Names follow `tools/effect_categories.csv`: functions that do something carry the verb of their category (`destroy`, `return_…to_deck`, `send_…to_graveyard`, `negate`, `equip`, `counter`, `coin`, `set_face_down`, `resolve_…summon`, `attach_effect_to_`), pure queries the `get_/is_/can_/count_/has_/find_/filter_/cond_` prefixes (neutral leaves), and CPU-only code the `ai_` group (a leaf).

**Result (M, measured, not committed).** Re-running `card_effects.py --check` with a temporary copy of `re/functions.csv` in which these 183 names are applied by address: full cards 1,730 → 2,267, partial 812 → 275; released cards with own effect records that are full 1,677 → 2,189 (74.5 % → 97.2 %); fallback spells full 53 → 78. No new unnamed callee appears in any partial resolve closure; the 87 records still partial reach no effect category at all. `re/functions.csv` is regenerated from the name files by its owner, so the committed numbers move when that happens.

The "Partial records (cards)" column counts the partial records (and cards) whose resolve closure reached the function before naming; one record usually reaches several of them, so the column does not add up. "Callers" is the number of calling functions in Ghidra (for `BOOT.BIN` functions: callers of the import stub).

## New findings

### Engine commands

Handlers read in `duel_core_execute_command` (side in bit 15 of the opcode; arguments `a`, `b`, `c` at `0x09e290fa`/`+fc`/`+fe`). (H for the code, M for the readings.)

| Command | Handler | Effect | Posted by |
| --- | --- | --- | --- |
| `0x06` | `0x09dbc758` | Sets (`b ≠ 0`) or clears bit `a` of the duel flag word `0x09e2bba0`; UI event `0x26` | `duel_core_post_set_duel_flag` |
| `0x07` | `0x09dbc66c` | UI event 3 with `a`, waits for it | `duel_core_post_ui_message` |
| `0x13` | `0x09dbc94c` | Active field spell `0x09e2bbc8 = a`; UI event 7; recomputes (`0x09be75f8`) | `duel_core_post_field_spell_change` |
| `0x28` | `0x09db7aa4` | `a = 0xffff`: appends `b` to the target ring `0x09e28e50`. Otherwise brings a Graveyard/banished card to the top of its pile (UI `0x18`) and shows card `b` of location `a` (UI `0x19`); a target number `c > 5` also goes to the ring | `duel_core_post_show_location`, `duel_effects_append_link_target` |
| `0x2e` | `0x09dbabfc` | UI events `0x47` then `0x22` for slot `a` (announces a field card) | `duel_core_post_announce_slot` |
| `0x37` | `0x09db72a4` → `0x09be7828` | Rewrites marker node `a >> 8` of slot `a & 0xff`: kind/turn byte `b` (0 clears the node: key 0, kind 1) and value `c` | `duel_core_post_set_marker_node`, `duel_core_post_clear_marker_with_value` |
| `0x48` | `0x09dbea78` | Seed `(a, b)` into `0x09e2d1cc`; permutes the Monster Zones of mask `c` at random (Fisher–Yates with `duel_core_random`), UI `0x29` | `duel_core_shuffle_face_down_defense_monsters` |
| `0x4f` | `0x09dbd1e4` → `0x09c03a5c` | Seed; shuffles the hand (unless player flag bit 1, public hand); UI `0x12`; clears player flag bit 2 | `duel_core_post_shuffle_hand` |
| `0x58` | `0x09dbbd5c` | Moves card reference `b` of location `a` (Deck, or the Extra Deck for `0x0c`) to the top (`c = 0`) or bottom of that pile; UI `0x16` | `duel_core_place_picked_cards_on_deck_top` |
| `0x5c` | `0x09dbd13c` → `0x09c019f8` | Swaps every player's Deck and Graveyard lists (Exchange of the Spirit) | `duel_effects_swap_decks_and_graveyards` |

### Card requests (pending action) and prompt requests

The card-request modes left open in `effect-helpers-deck.md` (M):

| Mode | Worker | Meaning | Setter |
| --- | --- | --- | --- |
| 9 | `0x09c11fec` | The side picks `count` hand cards through a filter (`0x09c114e0`); each pick may be shown (UI `0x2a`) | `duel_core_request_pick_hand_cards` |
| 10 | `0x09c12230` | Card-specific selection with a per-card hint and filter (`0x09c11ea0`): Bubble Crash (hand + field down to five), Ectoplasmer, Patrician of Darkness (attack target), Dark Coffin, Cyber Angel - Dakini … | `duel_core_request_card_selection` |
| `0x0c` | inline | Marks every negatable link below index `a` as negated (link `+4` bits 1, 2, 4) | `duel_core_request_negate_links_below` |
| `0x0d` | `0x09c12918` | Declaration from an allowed mask through the Attribute prompt `0x09dc795c` (message `0xf2`); index of the answer in `0x09e2d2fc` | `duel_core_request_declare_attribute_ex` |
| `0x0e` | `0x09c12b98` | List selection with up to four extra arguments | `duel_core_request_select_list_cards_ex` |
| `0x14` | `0x09c13154` | Number declaration with per-card prompt texts (Card Blocker, Card Trooper, Power Wall, Wall of Revealing Light, Reasoning, Psychic Commander, Bark of Dark Ruler) | `duel_core_request_declare_number` |

A second request block drives player prompts (H for the layout, M for the kinds): `0x09e2d2c4` active, `0x09e2d2c8` side, `0x09e2d2cc` kind, `0x09e2d2d0` step, `u16 0x09e2d2d4`/`0x09e2d2d6` arguments, `u16 0x09e2d2d8` answer, `0x09e2d2c0` link-duel state (2 send, 1 waiting). The runner `0x09c14580` (called by `duel_core_run_turn_flow`) dispatches kinds 1–8 through the table `0x09debad4`: 1 hint (`0x09c13994`), 2 per-card yes/no or option question (`0x09c139e0`), 3 zone choice from a mask (`0x09c13c80`; `duel_core_request_monster_zone`, `duel_core_request_spell_trap_zone`), 4 `0x09c13d40`, 5 Type declaration (`0x09c13f2c`), 6 Attribute declaration (`0x09c140e8`), 7 `0x09c14284`, 8 `0x09c14480` (4, 7 and 8 not read).

### Other findings

- **CPU answers.** Every yes/no prompt for a CPU side goes through `ai_answer_card_yes_no` (fixed answers first, then per-card heuristics inside an AI context); option menus through `ai_answer_card_option`, number selections through `ai_answer_select_numbers`. The same three-level shape (fixed table, evaluation, context restore) is used each time. (H)
- **Visible hands.** `duel_core_is_hand_revealed` lists the cards that open a hand (Clear World with a LIGHT monster, The Eye of Truth, Ceremonial Bell, Mind on Air, Thousand-Eyes Jellyfish, Respect Play for the turn player); player flag bit 1 is the "hand public" bit, and single hand cards can be shown by an instance marker (Golden Ladybug). (H/M)
- **Control.** `duel_effects_get_controlling_side` resolves who controls a monster from the kind-10 and kind-1/5 links of the control cards listed in `duel_effects_is_control_changing_card`; Remove Brainwashing (`0x1632`) cancels them. (M)
- **Exchange of the Spirit** is one command (`0x5c`), posted after the Fusion/Synchro monsters went back to the Extra Decks and the Deck cards to their owners. (M)

## Function tables

### Prompts and the CPU's answers

| Address | Name | Signature | Meaning | Callers | Partial records (cards) | Conf. |
| --- | --- | --- | --- | --- | --- | --- |
| `0x09d9f0c0` | `ai_answer_card_yes_no` | `int (int side, int card_id, int arg)` | CPU answer to a card-specific yes/no prompt: the fixed answer of ai_get_fixed_card_yes_no, else pushes an AI context (ai_push_context), evaluates ai_evaluate_card_yes_no and restores the board analysis (ai_analyze_board, ai_replan_turn_player). Called by the prompt functions 0x09dc725c, 0x09dc72b0, 0x09dc733c, 0x09dc73e0, 0x09dc74f8. | 5 | 122 (122) | H |
| `0x09d990a4` | `ai_get_fixed_card_yes_no` | `int (int side, int card_id)` | Constant CPU answers: 1 for about 20 listed ids, 0 for 0x1d2a and id 0, state-dependent for 0x1cec, 0x1864/0x147b, 0xe; -1 otherwise. | 1 | 121 (121) | H |
| `0x09d99284` | `ai_evaluate_card_yes_no` | `int (int side, int card_id, int ref)` | Per-card yes/no heuristics: deck-out checks (ai_would_deck_out) for 0x1ed2, 0x1dcf, 0x1ba9, 0xecd; ATK comparisons for 0x1e28 and 0x1ba7; LP comparisons for 0x12fd and 0x167a; Crystal Beasts through 0x09cf5968. -1 when the card is not listed. | 2 | 121 (121) | M |
| `0x09dc725c` | `duel_core_ask_yes_no_by_side` | `void (int side, int card_id, int message)` | Yes/no prompt addressed to a side: a CPU side (0x09e02998[side] == 1) answers through ai_answer_card_yes_no into 0x09e2d248; otherwise UI event 0x36 kind 2 with the message. | 13 | 38 (38) | H |
| `0x09d9a1fc` | `ai_get_fixed_card_option` | `int (void *link, uint enabled)` | Fixed CPU option for listed cards or a single enabled option; -1 otherwise. | 2 | 13 (13) | M |
| `0x09d9a4b4` | `ai_evaluate_card_option` | `int (void *link, uint enabled)` | Per-card CPU choice for option menus (Rainbow Neos, Rain Storm, Elemental Hero Stratos, Dark Scorpion cards, Judgment of Pharaoh ...); falls back to the lowest enabled option. | 2 | 13 (13) | M |
| `0x09d9f654` | `ai_answer_card_option` | `int (void *link, uint enabled)` | CPU answer wrapper of duel_core_ask_option (fixed choice, else evaluated with an AI context). | 1 | 13 (13) | H |
| `0x09dc733c` | `duel_core_ask_yes_no_by_side_with_card_name` | `void (int side, int card_id, int message, int entry)` | As duel_core_ask_yes_no_by_side, with %s of the message replaced by the name of card entry `entry` (duel_core_format_text_string). | 13 | 12 (12) | H |
| `0x09d99db8` | `ai_get_fixed_number_choice` | `uint (void *link, uint mask)` | CPU choice for number declarations: Sixth Sense picks the two highest allowed numbers of `mask`; -1 for other cards. | 1 | 2 (2) | M |
| `0x09d99e40` | `ai_choose_number_by_target` | `int (void *link, uint mask)` | CPU choice for Roulette Barrel: tries the extreme values against duel_effects_count_slots_passing; result bit in 0x09e2d248. | 1 | 2 (2) | M |
| `0x09d9f31c` | `ai_answer_select_numbers` | `int (void *link, int count)` | CPU answer wrapper of duel_core_ask_select_numbers (fixed choice, else evaluated with an AI context). | 1 | 2 (2) | M |
| `0x09dc7adc` | `duel_core_ask_select_numbers` | `void (void *link, int message, uint mask, int count)` | Number-selection prompt (UI event 0x36 kind 10); the CPU answers through ai_answer_select_numbers. | 2 | 2 (2) | M |
| `0x09bf3c34` | `ai_classify_resolve_kind` | `int (void *link)` | AI classification of an effect by its resolve handler and card id into codes 0-6 (destroy targets, destroy all, negate ...). 46 callers, mostly AI. | 46 | 1 (1) | M |
| `0x09dc7c68` | `duel_core_show_hint_ex` | `void (int side, int a, int b)` | UI event 0x36 kind 0x0e for a human side. | 2 | 1 (1) | M |

### Card requests and prompt requests

| Address | Name | Signature | Meaning | Callers | Partial records (cards) | Conf. |
| --- | --- | --- | --- | --- | --- | --- |
| `0x09c0f674` | `duel_core_request_card_selection` | `void (int side, int card_id, int arg)` | Card request mode 10 (pending action): card-specific selection run by 0x09c12230 (hints and filters per card: Bubble Crash, Ectoplasmer, Patrician of Darkness, Dark Coffin, Cyber Angel - Dakini ...); the pick lands in 0x09e2d2fa. | 15 | 13 (13) | M |
| `0x09c134ac` | `duel_core_request_hint_message` | `void (int side, int message)` | Prompt request (block 0x09e2d2c4, kind 1): shows hint `message` to the side; a remote duelist gets it through the link (state 2). | 10 | 12 (12) | M |
| `0x09c13518` | `duel_core_request_yes_no` | `void (int side, int card_id, int entry)` | Prompt request kind 2 (worker 0x09c139e0): per-card yes/no or option question (duel_core_ask_yes_no_by_side, ..._with_card_name, option menus for Dark Coffin and Ordeal of a Traveler); answer in 0x09e2d2d8. | 13 | 12 (11) | M |
| `0x09c13584` | `duel_core_request_monster_zone` | `void (int side, int field_side, int arg)` | Prompt request kind 3 with the mask of free Monster Zones of field_side (duel_core_is_monster_zone_free) and field_side in bit 15: choose a zone. | 2 | 9 (6) | M |
| `0x09c0f18c` | `duel_core_request_discard_to_graveyard` | `void (int side, int count, int monsters, int spells, int by_opponent)` | Card request mode 2 with flag 0x20 (the card must be sendable to the Graveyard) and bits 0/8/2 from the arguments. | 6 | 7 (7) | M |
| `0x09c0f984` | `duel_core_request_declare_attribute_ex` | `void (int side, int card_id, int count, int mask)` | Card request mode 0x0d (worker 0x09c12918): declare from an allowed mask; result index in 0x09e2d2fc, mask in 0x09e2d2fa. | 7 | 4 (4) | M |
| `0x09c0f55c` | `duel_core_request_pick_hand_cards` | `void (int side, int arg, int count)` | Card request mode 9 (worker 0x09c11fec): the side picks `count` hand cards with a filter; each pick can be shown (UI event 0x2a). Called by six cost handlers. | 8 | 3 (3) | L |
| `0x09c137d4` | `duel_core_request_declare_type` | `void (int side, int card_id)` | Prompt request kind 5 (worker 0x09c13f2c): declare a monster Type (Types on the field for 0x161c, the side's Types for 0x15f6); answer in 0x09e2d2d8. | 4 | 2 (1) | M |
| `0x09c13844` | `duel_core_request_declare_attribute` | `void (int side, int card_id)` | Prompt request kind 6 (worker 0x09c140e8): declare an Attribute; for 0x1efe the single Attribute of the side's monsters is taken without asking; answer in 0x09e2d2d8. | 1 | 2 (1) | M |
| `0x09c0fac4` | `duel_core_request_negate_links_below` | `void (int side, int index)` | Card request mode 0x0c: negates every chain link below `index` that can be negated. | 1 | 1 (1) | H |
| `0x09c0fc50` | `duel_core_request_select_list_cards_ex` | `void (int side, int card_id, short *args, int count)` | Card request mode 0x0e with up to four extra arguments copied after the card id. | 1 | 1 (1) | M |
| `0x09c100e4` | `duel_core_request_declare_number` | `void (int side, int card_id, int arg)` | Card request mode 0x14 (worker 0x09c13154): number declaration with per-card prompts (Card Blocker, Card Trooper, Power Wall, Wall of Revealing Light, Reasoning, Psychic Commander, Bark of Dark Ruler). | 4 | 1 (1) | M |

### Engine-command posters and state primitives

| Address | Name | Signature | Meaning | Callers | Partial records (cards) | Conf. |
| --- | --- | --- | --- | --- | --- | --- |
| `0x09c19aec` | `duel_core_post_show_location` | `void (int side, int location)` | Posts command 0x28 (location, 0, 0) with the side in bit 15: the reveal/target-marker command with reference 0. Called after selections are confirmed (18 callers). | 18 | 30 (30) | M |
| `0x09c15188` | `duel_core_post_add_instance_marker` | `void (int ref_side, int key, int kind)` | Command 0x35 with a = instance \| kind << 8 and b = key \| 0x8000 (bit 15: the marker goes to a card instance, not a slot). | 8 | 17 (16) | M |
| `0x09c2bbb8` | `duel_core_post_ui_message` | `void (int arg)` | Posts command 7, whose handler shows UI event 3 with `arg` and waits for it. | 9 | 15 (15) | L |
| `0x09be4c28` | `system_memzero` | `void (void *p, int size)` | system_memset(p, 0, size). | 30 | 14 (14) | H |
| `0x09c19a74` | `duel_core_post_place_list_card_on_field_raw` | `void (int side, int location, int ref, int to_side, int slot, int face_up, int position)` | Packs and posts command 0x40 (list card placed directly in a field slot) without further checks. | 3 | 11 (7) | H |
| `0x09c151cc` | `duel_core_post_remove_link_marker` | `int (int side, int slot, int from, int arg)` | If (side, slot) has a link from `from` (duel_core_get_link_kind_from), posts command 0x36 kind 0x0a to remove it; returns whether it posted. | 6 | 7 (7) | M |
| `0x09bf101c` | `duel_core_clear_deck_shuffle_flags` | `void (void)` | Clears bit 3 ("Deck must be shuffled") of both player flag words. | 4 | 6 (4) | M |
| `0x09c19c34` | `duel_core_shuffle_face_down_defense_monsters` | `void (int side, uint mask)` | If at least two face-down Defense Position monsters of the side are in `mask`, posts command 0x48 with the shuffle seed: their zones are permuted at random. | 6 | 6 (6) | M |
| `0x09c2bc7c` | `duel_core_timing_batch_begin_ex` | `void (void)` | Opens a timing batch (nest counter 0x09e28f90, serial 0x09e28f94) unless the chain is resolving; in a link duel with a remote turn player sends message 8 instead. | 12 | 6 (4) | M |
| `0x09c15894` | `duel_core_move_equip_card` | `void (int equip, int target)` | Moves an equip card: removes its link to the old monster (command 0x36 kind 0x0a) and equips it to `target` with the old link kind (duel_core_equip_card_ex). | 4 | 5 (5) | M |
| `0x09c17ec4` | `duel_core_raise_attack_event` | `void (int mode)` | Queues the attack-related field triggers (Super Conductor Tyranno, Mad Archfiend, Prepare to Strike Back, Ordeal of a Traveler, Fairy Box ...) and raises timing event 0x12 with the packed attacker/target. | 3 | 5 (5) | L |
| `0x09c1b118` | `duel_core_post_field_spell_change` | `void (int card_id)` | Posts command 0x13 (sets the active field spell 0x09e2bbc8); when Umi leaves for another field spell, destroys every face-up Tornado Wall. | 2 | 5 (4) | M |
| `0x09cdd140` | `duel_core_flag_face_up_copies` | `void (int side, int card_id)` | Sets slot flag 7 (duel_core_post_set_slot_flag) on every face-up copy of card_id in the matching zone range of the side. | 11 | 5 (5) | L |
| `0x09c2aef0` | `duel_core_send_named_cards_from_deck_to_graveyard` | `void (int side, int name, int all, int card_id, int by_opponent)` | duel_core_send_named_cards_from_deck with banish = 0. | 3 | 4 (3) | H |
| `0x09c2af58` | `duel_core_place_named_deck_card_on_field` | `int (int side, int card_id, int slot)` | Places the first Deck card with that name face-up in `slot` (command 0x40); returns 1 if found. | 3 | 4 (3) | M |
| `0x09c2b06c` | `duel_core_place_picked_cards_on_deck_top` | `void (int side)` | Posts command 0x58 (move within the Deck) for the picked candidates in reverse order, so the first pick ends on top. | 2 | 4 (4) | M |
| `0x09c19714` | `duel_core_return_banished_card_to_deck` | `int (int side, int ref)` | Moves a banished card to the Deck, or to the Extra Deck for Fusion/Synchro monsters (command 0x3e), raises event 0x25; 0 if the card is not banished. | 1 | 3 (2) | H |
| `0x09c19b10` | `duel_core_post_show_location_b` | `void (int side, int location)` | Byte-identical twin of duel_core_post_show_location (command 0x28 (location, 0, 0)). | 4 | 3 (3) | M |
| `0x09c27870` | `duel_core_post_announce_slot` | `void (int side, int slot)` | Posts command 0x2e (slot, 1, 0): UI events 0x47 and 0x22 show the card in the slot. | 28 | 3 (2) | M |
| `0x09c2af08` | `duel_core_banish_named_cards_from_deck` | `void (int side, int name, int all, int card_id, int by_opponent)` | duel_core_send_named_cards_from_deck with banish = 1. | 2 | 3 (3) | H |
| `0x09bef048` | `system_copy_word` | `void (uint *dst, const uint *src)` | *dst = *src. | 31 | 2 (2) | H |
| `0x09c15438` | `duel_core_post_clear_marker_with_value` | `void (int side, int slot, int key, int value)` | Finds the marker node (duel_core_find_effect_with_value) and posts command 0x37 with zero kind/value, which clears that node. | 15 | 2 (2) | M |
| `0x09cde2a8` | `duel_core_pay_chain_energy_lp` | `void (int side)` | Each active Chain Energy (0x132c) makes the side pay 500 LP (announced). | 5 | 2 (2) | H |
| `0x09c0ba44` | `duel_core_set_duel_flag` | `void (int bit, int value)` | Sets or clears bit `bit` of 0x09e2bba0. | 3 | 1 (1) | H |
| `0x09c15258` | `duel_core_post_remove_links_from` | `void (int side, int slot)` | Removes every link (command 0x36 kind 0x0a) that (side, slot) holds on any field slot. | 2 | 1 (1) | M |
| `0x09c153a0` | `duel_core_post_remove_marker_if_present` | `void (int side, int slot, int key, int kind, int value)` | If the marker kind exists (duel_core_has_marker_kind), posts command 0x36 for it. | 8 | 1 (1) | L |
| `0x09c154d8` | `duel_core_post_remove_instance_marker` | `void (int ref_side, int key, int value)` | When the instance carries the marker (duel_core_has_instance_marker), command 0x36 with a = instance \| 0x100 and b = key \| 0x8000. | 4 | 1 (1) | M |
| `0x09c15550` | `duel_core_post_set_marker_node` | `void (int side, int slot, int node, int kind, int value)` | Posts command 0x37: rewrites the marker node's kind byte and value (0 clears it). | 1 | 1 (1) | M |
| `0x09c17aa4` | `duel_core_attach_attack_markers` | `void (void)` | After an attack: markers for Diffusion Wave-Motion, Asura Priest-type attack-all monsters (0x1505) and the Spear Dragon-type position change (0x14d6), via command 0x35. | 2 | 1 (1) | M |
| `0x09c1aafc` | `duel_core_post_set_slot_value_b` | `void (int side, int slot, uint value)` | Command 0x39 with slot \| 0x100 (second slot word). | 4 | 1 (1) | L |
| `0x09c2b910` | `duel_core_post_shuffle_hand` | `void (int side)` | Posts command 0x4f with the shuffle seed: the side's hand is shuffled unless it is public. | 3 | 1 (1) | H |
| `0x09c2bd9c` | `duel_core_post_set_duel_flag` | `bool (int bit, int value)` | When bit `bit` of 0x09e2bba0 differs, sets it locally and posts command 6 (bit, value); returns whether it changed. | 4 | 1 (1) | H |
| `0x09cdd544` | `duel_core_update_pumpking` | `int (int mode)` | Pumpking the King of Ghosts upkeep with Castle of Dark Illusions: turn count, ATK marker and slot flag 7. | 2 | 1 (1) | M |
| `0x09cde344` | `duel_core_pay_queen_of_thorns_lp` | `void (int side)` | Each active Queen of Thorns (0x1df4) on the monster zones makes the side pay 1000 LP. | 3 | 1 (1) | M |
| `0x09dcb8bc` | `duel_core_set_statistic_max` | `void (int index, int value)` | Duel statistics: raises statistic `index` to `value` when larger (same storage as duel_core_add_statistic). | 6 | 1 (1) | H |

### Effect handlers and resolution steps

| Address | Name | Signature | Meaning | Callers | Partial records (cards) | Conf. |
| --- | --- | --- | --- | --- | --- | --- |
| `0x09c74548` | `duel_effects_destroy_valid_targets` | `void (void *link)` | Mask of the link targets still accepted by the record filter, destroyed in one batch (duel_core_request_send_mask, location 0x0e, flags 0x10000002). | 2 | 13 (13) | H |
| `0x09c16e90` | `duel_effects_clear_markers_on_control_change` | `void (int from, int to)` | When a monster changes sides: removes the markers of Great Shogun Shien-type cards (0x1f13, 0x1b39), resets the slot value of Phantom Dragon / Ultimate Tyranno, removes the Viser Des link (commands 0x36, 0x39). | 2 | 7 (7) | M |
| `0x09c17040` | `duel_effects_raise_control_change_triggers` | `void (int from, int to)` | When a monster changes sides: advances the turn count of Ekibyo Drakmord links and queues the triggers of Kunoichi, Griggle and Ameba (duel_core_chain_queue_trigger). | 2 | 7 (7) | M |
| `0x09c9dc6c` | `duel_effects_return_hand_cards_to_deck_step` | `int (void *link)` | Activation step: checks that enough hand candidates exist, lets the controller select hand cards and returns them to the Deck one by one (duel_core_return_hand_card_to_deck, revealed when requested), then shuffles. | 3 | 6 (6) | M |
| `0x09c817bc` | `duel_effects_negate_summon_and_destroy` | `int (void *link)` | Summon negation (Solemn Judgment / Horn of Heaven path): shows the negation, adds marker 0x12fd and destroys the summoned monster (duel_core_request_destroy_negated_slot). | 2 | 5 (4) | H |
| `0x09c74ba4` | `duel_effects_destroy_old_field_spell_step` | `int (void *link)` | Field spell activation step: destroys the opponent's face-up field spell (unless Field Barrier) and changes the active field spell. | 2 | 4 (3) | M |
| `0x09c7bf94` | `duel_effects_attach_effect_to_self_kind2` | `int (void *link)` | Adds a kind-2 marker of the card on itself with a per-card value (Iron Chain Dragon x200, Gaap x300, Copy Plant the target Level, Exarion Universe ...). | 4 | 4 (4) | M |
| `0x09c9fad8` | `duel_effects_resolve_counted_targets` | `int (void *link)` | Per-card target count (tuners for Ally of Justice - Cyclone Creator, HEROes for Elemental Hero Stratos, Toy Magicians, Voltanis ...), selection loop, then destroys or returns to the hand the selected mask. | 4 | 4 (4) | M |
| `0x09caaae4` | `duel_effects_resolve_target_payoff` | `int (void *link)` | Two-phase handler: records a value of the target (Spell Counters of Diamond-Dust Cyclone, original ATK for Edge Hammer, ATK for Trojan Blast and Arcana Force XII), then draws 1 per 4 counters or inflicts that damage. | 1 | 4 (4) | M |
| `0x09c88cf0` | `duel_effects_store_targets_as_slot_mask` | `int (void *link)` | Stores the target slots as a bit mask in the source slot word (command 0x39), removes the player link marker and adds player marker kind 6. | 1 | 3 (3) | L |
| `0x09c8ad6c` | `duel_effects_attach_effect_to_self_kind3` | `int (void *link)` | Adds a kind-3 marker of the card on itself with a per-card value (Gadget Hauler x800, Rainbow Dark Dragon x500, Elemental Hero Poison Rose 200, Knospe 100, Gaia Soul x1000). | 2 | 3 (3) | M |
| `0x09c91cd0` | `duel_effects_resolve_union_equip` | `int (void *link)` | Union-style equip: chooses a spell/trap zone, equips the monster (kind 10, or 11 for Union monsters) to the target; Brain Jacker also takes control; the unequip branch Special Summons it back. | 3 | 3 (3) | M |
| `0x09ca20fc` | `duel_effects_negate_current_attack` | `int (void *link)` | If an attack is in progress and the attacker is still valid and affected, posts command 0x1f (negate the attack); returns 1 when posted. | 2 | 3 (3) | H |
| `0x09ca671c` | `duel_effects_send_source_card_to_graveyard` | `int (void *link)` | If the link's card is still in its slot and enabled, sends it to the Graveyard (duel_core_request_send_field_card_to_graveyard). | 2 | 3 (2) | H |
| `0x09c7d108` | `duel_effects_resolve_destroy_valid_targets` | `int (void *link)` | Resolve handler: duel_effects_destroy_valid_targets, returns 0. | 2 | 2 (2) | H |
| `0x09c82250` | `duel_effects_resolve_move_equip` | `int (void *link)` | Two targets: moves the equip card target 0 to monster target 1 when the new target is valid (duel_effects_can_equip_to, duel_core_move_equip_card). | 2 | 2 (2) | H |
| `0x09c841d0` | `duel_effects_resolve_special_summon_targets` | `int (void *link)` | Special Summons each target from its list (The Grave of Enkindling, The Shallow Grave face-down, Spear Cretin) with duel_core_special_summon_impl. | 1 | 2 (1) | H |
| `0x09c90fe0` | `duel_effects_destroy_battle_opponent` | `int (void *link)` | For link kind 0x16 destroys the other battle participant if it is in a Monster Zone. | 2 | 2 (2) | M |
| `0x09c9631c` | `duel_effects_mark_opponent_player` | `int (void *link)` | Adds a player marker (kind 1) of the card on the opponent, value per card (Elemental Hero Chaos Neos, Judgment of Pharaoh). | 1 | 2 (2) | M |
| `0x09c978f8` | `duel_effects_mark_source_card` | `int (void *link)` | If the source is still in its slot, adds marker 0x16cb kind 4 to it. | 2 | 2 (2) | L |
| `0x09c9c3f4` | `duel_effects_send_selected_card_to_graveyard_step` | `int (void *link)` | Builds the candidate list, lets the side select (duel_core_request_select_list_cards), sends the pick from the hand or Deck to the Graveyard, then shuffles; the side flips for card 0x12da. | 1 | 2 (2) | M |
| `0x09c9ecec` | `duel_effects_resolve_set_face_down_all` | `int (void *link)` | Turns every field card accepted by the record filter face-down (duel_effects_set_face_down) inside a timing batch. | 1 | 2 (1) | H |
| `0x09ca5504` | `duel_effects_return_banished_cards_to_deck` | `int (void *link)` | Returns every banished card of both sides to the Deck (duel_core_return_banished_card_to_deck) and shuffles; Necroface then gains 100 per card. | 1 | 2 (1) | H |
| `0x09cb54c4` | `duel_effects_reapply_arcana_force_effect` | `int (void *link)` | Arcana Force coin results: removes the Magician marker, or re-runs the resolve handler of The Chariot / The Strength on a synthetic link. | 2 | 2 (2) | L |
| `0x09c2b954` | `duel_effects_swap_decks_and_graveyards` | `void (void)` | Exchange of the Spirit: sends Fusion/Synchro monsters from the Graveyards to the Extra Decks and Deck cards to their owners (command 0x3e), swaps every Deck with its Graveyard (command 0x5c) and shuffles both Decks. | 1 | 1 (1) | M |
| `0x09c7bdc8` | `duel_effects_return_graveyard_to_deck_step` | `int (void *link)` | Returns the side's Graveyard to the Deck card by card (duel_effects_return_graveyard_card_to_deck) and shuffles; the opponent for Rainbow Neos. | 1 | 1 (1) | H |
| `0x09c7cc5c` | `duel_effects_send_selected_deck_card_to_graveyard` | `int (void *link)` | Activation step: opens the Deck list, sends the picked card to the Graveyard (duel_core_send_deck_ref_to_graveyard). | 1 | 1 (1) | H |
| `0x09c7cddc` | `duel_effects_take_control_of_source` | `int (void *link)` | Adds a kind-5 control marker for the opponent and requests the control change of the source card (duel_core_request_take_control). | 1 | 1 (1) | M |
| `0x09c7eb1c` | `duel_effects_resolve_equip_source_to_target` | `int (void *link)` | Moves the source equip card to the valid target (duel_core_move_equip_card). | 1 | 1 (1) | M |
| `0x09c821b8` | `duel_effects_copy_target_value` | `int (void *link, void *other)` | Copies word +0x08 of the link to `other` when target 0 is still on the field. | 1 | 1 (1) | L |
| `0x09c859a4` | `duel_effects_destroy_source_if_condition` | `int (void *link, int arg)` | If the card is face-up and its slot +0c condition holds, destroys its own slot. | 1 | 1 (1) | M |
| `0x09c8b160` | `duel_effects_resolve_attack_target_step` | `int (void *link)` | Effect battle setup: requests the effect battle, then declares an attack (command 0x17) of the current attacker on the target. | 1 | 1 (1) | M |
| `0x09c94fcc` | `duel_effects_resolve_summon_trap_monster` | `int (void *link)` | Special Summons the trap card itself as a monster (Defense Position for Cyber Shadow Gardna, Embodiment of Apophis, The Rival's Name). | 1 | 1 (1) | H |
| `0x09caa0b8` | `duel_effects_move_monster_to_zone` | `int (void *link)` | Moves the source monster to the chosen free Monster Zone (command 0x3c). | 1 | 1 (1) | M |
| `0x09caa86c` | `duel_effects_resolve_add_counter_to_target` | `int (void *link)` | Adds one counter of kind 0x10 to the still-valid target (duel_core_add_counters). | 1 | 1 (1) | H |
| `0x09cad71c` | `duel_effects_resolve_special_summon_target` | `int (void *link, int a, int b, int c, int d)` | Special Summons the valid target (duel_core_special_summon) when duel_effects_can_special_summon_with_filter holds. | 1 | 1 (1) | M |
| `0x09cb2780` | `duel_effects_resolve_return_filtered_to_deck` | `int (void *link)` | Returns every card accepted by the record filter to the Deck (duel_core_request_return_mask_to_deck) and shuffles. | 1 | 1 (1) | H |
| `0x09cb42c4` | `duel_effects_resolve_arcana_coin_toss` | `int (void *link)` | Arcana Force: tosses a coin (duel_core_request_coin_toss) and stores the result + 1 in the slot word. | 1 | 1 (1) | H |
| `0x09cbebe8` | `duel_effects_append_link_target` | `void (void *link, int side, int slot, int ref)` | Appends a target entry to the link (first five in the link, then command 0x28 with c = 0xffff for the ring). | 1 | 1 (1) | M |
| `0x09cde8e8` | `duel_effects_refresh_prohibition_markers` | `void (int side, int slot)` | Prohibition (0x1368): re-adds the markers naming every card with the declared name on the field (and the Parasite Paracide cards in the Decks). | 2 | 1 (1) | M |

### Predicates, counters and finders

| Address | Name | Signature | Meaning | Callers | Partial records (cards) | Conf. |
| --- | --- | --- | --- | --- | --- | --- |
| `0x09bf10e0` | `duel_core_find_deck_card_by_name` | `int (int side, int card_id)` | Index of the first Deck card (list +0x304) with the same name (card_db_is_same_name), -1 if none. | 18 | 27 (26) | H |
| `0x09bfc874` | `duel_core_count_usable_spell_trap_zones` | `int (int side)` | Number of empty spell/trap zones (slots 5-9) that duel_core_is_zone_usable(side, zone, 1) accepts. | 5 | 25 (25) | H |
| `0x09c2c03c` | `duel_effects_is_link_card_ref_face_up` | `int (void *link)` | Finds the field slot of the link's card reference (+0x04) and returns its face-up word (slot +0x08); 0 when the card is not on the field. | 1 | 21 (21) | H |
| `0x09bf55f8` | `duel_effects_is_control_changing_card` | `bool (int card_id, int kind)` | True for cards that take or lend control through link markers: Dharc and the other Charmers, Alien Hypno, Mass Hypnosis, Mark of the Rose, Mask of Remnant, Snatch Steal, Brain Jacker, Falling Down, Dark Necrofear, Psychic Jumper and about 30 others; Interplanetary Invader "A" only for kind 5. | 5 | 20 (13) | H |
| `0x09c03880` | `duel_core_get_hand_public_flag` | `int (int side)` | Bit 1 of the player flag word (+0x120): the side's whole hand is public. | 3 | 18 (18) | M |
| `0x09c03968` | `duel_core_is_hand_revealed` | `int (int side)` | 1 when the side plays with its hand revealed: Clear World with a LIGHT monster of that side, the opponent's The Eye of Truth, Mind on Air or Thousand-Eyes Jellyfish, Ceremonial Bell, or Respect Play for the turn player. | 6 | 16 (16) | H |
| `0x09bff2e8` | `duel_effects_has_monster_immunity_against` | `bool (int side, int slot, int other)` | (other + 1) & duel_effects_get_monster_immunity(side, slot) is non-zero: the monster is unaffected by monster effects of that side (1 own, 2 opponent). | 17 | 15 (8) | M |
| `0x09bfe224` | `duel_effects_get_controlling_side` | `int (int side, int slot, int mode)` | Side that controls the monster at (side, slot) after the control markers (kind 10 and 1/5 links) of Mark of the Rose, Mask of Remnant, Snatch Steal, Brain Jacker, Alien Hypno, the Charmers ...; Remove Brainwashing (0x1632) returns control to the owner; spell/trap immunity is respected. mode 1 ignores some links, mode 2 returns the owner side. | 13 | 14 (7) | M |
| `0x09c038a8` | `duel_core_is_hand_card_revealed` | `int (int side, int index)` | Hand card `index` is visible: the hand is public (player word `+0x120` bit 1) or its instance (the 9-bit reference of the hand entry) carries marker 0xfe0 or 0x1db9 (Golden Ladybug), tested with `duel_core_has_marker_value(side, 0x0b, key, ref)`. No side effects. Callers: `ai_analyze_board`, `duel_core_is_card_face_up_at`, `duel_core_cmd_summon_from_hand` and six effect functions. Verified in PPSSPP (Session A, A10: 0 for three hidden hand cards of the human). | 9 | 14 (14) | H |
| `0x09dc1400` | `duel_core_is_attack_target` | `bool (int side, int slot)` | The slot holds the monster recorded as the defending battle participant (0x09e2865c of the non-attacking record, instance and generation) and the attack is not direct (0x09e28628 == 0). | 12 | 14 (14) | M |
| `0x09bf118c` | `duel_core_find_deck_card_by_id` | `int (int side, int card_id)` | Index of the first Deck card whose id equals card_id exactly, -1 if none. | 1 | 13 (13) | H |
| `0x09c01b84` | `duel_core_count_graveyard_monsters` | `int (int side)` | Number of monsters in the side's Graveyard (list +0x55c). | 21 | 13 (13) | H |
| `0x09c81888` | `duel_effects_find_search_target_in_deck` | `int (void *link)` | Deck index of the card a searcher fetches: maps the searcher to its target id (Warrior of Atlantis -> A Legendary Ocean by exact id, Hecatrice -> Valhalla, Hall of the Fallen, eight other pairs) and finds it in the controller's Deck. | 3 | 13 (13) | M |
| `0x09dcaa50` | `duel_core_is_card_face_up_at` | `int (int side, int location, int index)` | Visibility of a card by location: hand duel_core_is_hand_card_revealed, banished from the entry flags, Graveyard always, Deck top from 0x09e2bba0 bit 2 with Parasite Paracide-type markers, Extra Deck never, field slot +0x08. 33 callers. | 33 | 13 (13) | M |
| `0x09bef934` | `duel_core_find_extra_deck_card_by_instance` | `int (int side, int instance)` | Index of the Extra Deck entry holding card instance `instance`, -1 if none. | 6 | 12 (12) | H |
| `0x09bf8e50` | `duel_core_count_named_cards_both_sides` | `int (int card_id)` | duel_core_count_named_cards_except(0, card, -1) + the same for side 1. | 19 | 12 (12) | H |
| `0x09bf90c0` | `duel_core_count_face_up_monsters_matching_all` | `int (int (*pred)(int))` | Face-up monsters on both sides (flags bits 1 and 3 clear) whose card id satisfies pred. | 2 | 9 (9) | H |
| `0x09bfa158` | `duel_core_count_face_up_cards_matching` | `int (int side, int (*pred)(int))` | Occupied face-up slots 0-10 of the side (flags bits 1 and 3 clear) whose name id satisfies pred. | 9 | 9 (9) | H |
| `0x09c366c0` | `duel_effects_filter_position_change_target` | `int (void *link, int side, int slot)` | Per-card target filter after duel_effects_target_filter(..., 0x14): Type, Flamvell, Gemini not yet enabled, Venom, Elemental Hero, Level, Morphtronic; then the monster must be face-down or changeable (duel_effects_can_change_position) and be a link target or the attacker. | 1 | 9 (9) | M |
| `0x09c0c740` | `duel_core_can_summon_race` | `int (int side, int race)` | Always 1 (summon restriction hook by Type, unused in this build). | 3 | 7 (7) | M |
| `0x09be8574` | `duel_core_find_equipped_monster` | `int (int side, int slot)` | side \| slot << 8 of the card that holds a link of kind >= 10 from (side, slot), i.e. the monster this equip card is attached to; 0xffff if none. | 12 | 6 (6) | M |
| `0x09be90d0` | `duel_core_count_slot_markers_with_value` | `int (int side, int slot, int key, int value)` | Number of effect markers (kind < 6) on the slot with this key and value. | 9 | 6 (6) | H |
| `0x09be9a4c` | `duel_core_count_instance_markers` | `int (int instance, int key)` | Number of effect markers (kind < 6) with this key on a card instance (list head at 0x09e2bbd0 + instance * 6). | 8 | 6 (5) | H |
| `0x09bf11f8` | `duel_core_find_extra_deck_card_by_name` | `int (int side, int card_id)` | Index of the first Extra Deck card with the same name, -1 if none. | 8 | 6 (5) | H |
| `0x09bf9f78` | `duel_core_get_alias_name_bits` | `int (int card_id)` | 2 for Neo-Spacian Twinkle Moss, 1 for Neo-Spacian Marine Dolphin, 0 otherwise. | 2 | 6 (6) | M |
| `0x09c020b8` | `duel_core_count_distinct_graveyard_names_matching` | `int (int side, int (*pred)(int))` | Number of distinct names among Graveyard monsters satisfying pred, plus the alias names of Neo-Spacian Twinkle Moss and Marine Dolphin (duel_core_get_alias_name_bits). | 7 | 6 (6) | M |
| `0x09c6185c` | `duel_effects_can_summon_trap_monster` | `int (void *link)` | Trap monster check: free Monster Zone, Special Summon allowed, the trap's monster stats (duel_core_apply_trap_monster_stats) pass the Type/Attribute restrictions, and Power Filter (0x1e6b) blocks ATK <= 1000. | 4 | 6 (6) | M |
| `0x09c03678` | `duel_core_count_hand_monsters` | `int (int side)` | Number of monsters in the side's hand. | 31 | 5 (5) | H |
| `0x09c0d594` | `duel_core_can_use_graveyard` | `int (int a, int side)` | 0 while Necrovalley (0x159d) is active unless `side` controls Gravekeeper's Chief (0x158b); 1 otherwise. | 14 | 5 (5) | H |
| `0x09be8aa4` | `duel_effects_can_equip_to` | `bool (int side, int slot, int to_side, int to_slot)` | Builds a link for the equip card at (side, slot) and runs duel_effects_filter_equip_target on the new target; false when the current link is of kind 0x0c. | 6 | 4 (4) | M |
| `0x09bf9d58` | `duel_core_count_monsters_matching_both` | `int (void *filter)` | duel_core_count_monsters_matching for side 1 plus side 0. | 2 | 4 (4) | H |
| `0x09cbaab4` | `duel_effects_can_fusion_with_materials` | `int (int fusion, int count, void *refs)` | Checks a list of material references against the Fusion's material codes (duel_effects_get_fusion_material_code, duel_effects_match_fusion_material); Chimeratech Overdragon needs an extra condition. | 2 | 4 (4) | M |
| `0x09bf1b30` | `duel_core_count_deck_cards_matching` | `int (int side, int (*pred)(int))` | Number of Deck cards satisfying pred. | 13 | 3 (3) | H |
| `0x09bf992c` | `duel_core_count_owned_named_cards_on_field_and_graveyard` | `int (int owner, int card_id)` | Cards with that name owned by `owner` on both fields plus in its Graveyard. | 3 | 3 (3) | H |
| `0x09c033a8` | `duel_core_count_hand_cards_named` | `int (int side, int card_id)` | Number of hand cards with the same name. | 94 | 3 (3) | H |
| `0x09c56df8` | `duel_effects_can_summon_tokens` | `bool (void *link)` | Token summon check from the token table entry: enough free zones on the receiving side, Special Summon allowed, token id allowed (0x09c0c898, 0x09c0c584). | 14 | 3 (2) | H |
| `0x09c6d4f4` | `duel_effects_can_special_summon_with_filter` | `int (void *link)` | Free Monster Zone, Special Summon allowed and a candidate for the filter 0x09c3f604 (returns 2), else 0. | 3 | 3 (3) | M |
| `0x09ce3244` | `duel_effects_get_target_filter_mask` | `uint (void *link)` | Bit mask (slot + 16 x side) of field slots that pass the record's slot +08 filter; -1 without a filter. | 20 | 3 (3) | H |
| `0x09be96c4` | `duel_core_get_turn_marker_value` | `int (int side, int slot, int key)` | Value of the first kind-1/2 marker with this key and turn counter 0 on the slot, -1 if none. | 7 | 2 (1) | M |
| `0x09beea80` | `duel_core_has_active_monster_effect` | `int (int side, int slot)` | The slot's monster counts as an effect monster: trap-monster ids by flag bits, Geminis only when Gemini-summoned or enabled, else card_db_is_effect_monster. | 6 | 2 (2) | M |
| `0x09bf1924` | `duel_core_count_deck_cards_named` | `int (int side, int card_id)` | Number of Deck cards with that name. | 45 | 2 (2) | H |
| `0x09bf1a84` | `duel_core_count_extra_deck_by_frame` | `int (int side, int frame)` | Extra Deck cards whose card_db_get_frame equals `frame`. | 5 | 2 (2) | H |
| `0x09bf7564` | `duel_effects_is_coin_toss_monster_effect` | `bool (void *link)` | A monster effect whose resolve handler is the Arcana Force coin toss (unless Light Barrier) or one of the listed coin cards. | 2 | 2 (1) | L |
| `0x09bf8f3c` | `duel_core_count_named_cards_face_up_both` | `int (int card_id)` | Face-up cards with that name on both fields (duel_core_is_slot_card_named). | 10 | 2 (2) | H |
| `0x09c01374` | `duel_core_find_last_graveyard_card_named` | `int (int side, int card_id)` | Highest Graveyard index holding that name, -1 if none. | 19 | 2 (2) | H |
| `0x09c03458` | `duel_core_count_hand_cards_matching` | `int (int side, int (*pred)(int))` | Number of hand cards satisfying pred. | 21 | 2 (2) | H |
| `0x09c5664c` | `duel_effects_can_discard_from_hand` | `int (void)` | Thunk-like wrapper of duel_core_hand_has_discardable_cards. | 6 | 2 (2) | H |
| `0x09c67650` | `duel_effects_cond_defense_monster_attacked` | `bool (void *link)` | Link kind 0x12 and the opponent attacks a face-up Defense Position monster of the controller. | 1 | 2 (1) | L |
| `0x09c6cec8` | `duel_effects_can_activate_as_rainbow_ruins` | `bool (void *link)` | Temporarily sets the link's card to Ancient City - Rainbow Ruins (0x1ba7) and checks that the activation is not locked. | 2 | 2 (2) | M |
| `0x09cbf0ac` | `duel_effects_get_link_target_raw` | `int (void *link, int index)` | Raw target entry `index` of a link (first five in the link, the rest in the ring 0x09e28e50); Dark Deal shifts the index. | 4 | 2 (2) | H |
| `0x09be7cb8` | `duel_core_count_links_to` | `void (int side, int slot, int kind)` | Wrapper of duel_core_count_links over the slot's list. | 2 | 1 (1) | M |
| `0x09be7dd8` | `duel_core_count_links_from_card_if_affected` | `int (int side, int slot, int card_id, int from_side)` | duel_core_count_link_sources unless the slot is unaffected by spells/traps of that side. | 8 | 1 (1) | M |
| `0x09be7e88` | `duel_core_count_link_sources` | `int (int side, int slot, int card_id, int from_side, int value)` | Links (kind 6-11) on the slot whose source card is card_id, optionally filtered by source side and source slot word. | 13 | 1 (1) | M |
| `0x09be978c` | `duel_core_has_instance_marker` | `bool (int instance, int key)` | A card instance carries an effect marker with this key. | 10 | 1 (1) | H |
| `0x09be989c` | `duel_core_has_instance_marker_value` | `bool (int instance, int key, int value)` | Same with a value match. | 3 | 1 (1) | H |
| `0x09be9bd4` | `duel_core_find_slot_marker` | `void * (int side, int slot, int (*pred)(void *, int), int arg)` | First marker node of the slot accepted by pred, 0 if none. | 2 | 1 (1) | H |
| `0x09bee720` | `duel_core_get_first_slot_in_mask` | `int (uint mask)` | side \| slot << 8 of the lowest set bit (slot + 16 x side), -1 for an empty mask. | 1 | 1 (1) | H |
| `0x09bee8e0` | `duel_core_is_trap_card_at` | `int (int side, int slot)` | The slot holds a trap card (a trap monster in a Monster Zone by flag bit 12). | 6 | 1 (1) | M |
| `0x09beebc8` | `duel_core_is_effect_monster_at` | `int (int side, int slot)` | Like duel_core_has_active_monster_effect but every face-up Gemini counts. | 2 | 1 (1) | M |
| `0x09bf7b64` | `duel_core_find_face_up_spell_trap_by_name` | `int (int side, int card_id)` | Slot 5-10 holding that name face-up, -1 if none. | 2 | 1 (1) | H |
| `0x09bf86bc` | `duel_core_count_special_summoned_copies` | `int (int side, int card_id)` | Face-up enabled copies of card_id in the side's Monster Zones with slot flag bit 18 (Special Summoned). | 3 | 1 (1) | L |
| `0x09bf98b8` | `duel_core_count_side_slots_named` | `int (int side, int card_id)` | Slots 0-10 of the side holding that name. | 38 | 1 (1) | H |
| `0x09c00670` | `duel_core_get_slot_activation_kind` | `int (int side, int slot, int card_id)` | 0 none, 1 or 2 depending on the slot flags and card kind (continuous cards, listed ids) for a set or face-up card. | 8 | 1 (1) | L |
| `0x09c03250` | `duel_core_count_hand_cards_by_race` | `int (int side, int race)` | Number of hand cards whose card_db_get_race equals race. | 10 | 1 (1) | H |
| `0x09c035cc` | `duel_core_find_hand_card_by_name` | `int (int side, int card_id)` | Index of the first hand card with that name, -1 if none. | 16 | 1 (1) | H |
| `0x09c11948` | `duel_core_filter_special_summonable_monster` | `int (int side, int slot, int offset)` | Selection filter: a non-token monster of the requesting side that can be Special Summoned (or a Neo-Spacian Fusion); returns 0x800. | 1 | 1 (1) | M |
| `0x09c379ac` | `duel_effects_filter_monster_target_b` | `int (void *link, int side, int slot)` | Per-card target filter after duel_effects_target_filter(..., 0x15): tuners, Fusion, Crystal Beasts, Six Samurai, Destiny Heroes, Beasts, Level 1/2 normal monsters ... | 2 | 1 (1) | M |
| `0x09c5c6a4` | `duel_effects_cond_hand_has_summonable_monster` | `bool (void *link)` | Special Summon possible now, a hand monster can be Special Summoned face-up and at least two other hand cards are not monsters. | 1 | 1 (1) | L |
| `0x09c6b4c0` | `duel_effects_is_source_in_attack_position` | `bool (void *link)` | The link's card is still in its slot, enabled, face-up and in Attack Position. | 1 | 1 (1) | M |
| `0x09c96c5c` | `duel_effects_filter_dark_scorpion_hand` | `int (int side, int location, int index)` | Selection filter: Dark Scorpion hand cards whose bit in the link word +0x08 is still clear (0x800). | 1 | 1 (1) | M |
| `0x09cbe6b4` | `duel_core_get_instance_marker_values` | `int (int instance, uint *out)` | Values of the kind-3 markers with keys 0x1e11, 0x15b4 or 0x12e5 on a card instance (out may be 0); returns their count. | 4 | 1 (1) | M |
| `0x09ce388c` | `duel_effects_count_slots_passing` | `int (void *link, int side, int (*pred)(void *, int, int))` | Number of enabled slots of the side accepted by pred. | 2 | 1 (1) | H |
| `0x09ce3b3c` | `duel_effects_count_filter_matches_on_side` | `int (void *link, int side)` | Number of slots of one side accepted by the record's slot +08 filter. | 20 | 1 (1) | H |
| `0x09d9fca0` | `duel_core_is_summoned_to_opponent_field` | `int (int card_id)` | 1 for Volcanic Queen, Grinder Golem, Alien Skull and Lava Golem. | 1 | 1 (1) | M |
| `0x09dc5150` | `duel_core_get_battle_flip_trigger` | `int (int defender, int apply)` | For a battle participant: 0/1/2 whether a flip or battle effect triggers (Dharma-type, Ha Des rules, 0x165f, 0x1f19 ...); with `apply` set adds the related markers. | 1 | 1 (1) | L |

### BOOT.BIN card_db helpers (reached through import stubs)

| Address | Name | Signature | Meaning | Callers | Partial records (cards) | Conf. |
| --- | --- | --- | --- | --- | --- | --- |
| `0x088600a8` (stub `0x09de4a5c`) | `card_db_is_extra_deck_monster` | `int (int card_id)` | card_db_get_frame is 10 (Synchro) or 3 (Fusion): the card belongs in the Extra Deck. | 19 | 22 (21) | H |
| `0x088668e4` (stub `0x09de4d54`) | `card_db_fusion_allows_substitute` | `int (int card_id)` | 0 for eleven Fusion monsters (Destiny End Dragoon, Rainbow Neos, Cyber Ogre 2, Super Vehicroid Jumbo Drill, D.3.S. Frog, Cyber Blader, Alkana Knight Joker, Cyber End Dragon, F.G.D., Fiend Skull Dragon, Ryu Senshi), 1 otherwise; read by the fusion material check (0x09cbaab4) as a flag. | 7 | 19 (18) | L |
| `0x088648d4` (stub `0x09de4cec`) | `card_db_is_summoned_without_polymerization` | `bool (int card_id)` | Synchro monsters and the Fusions of summoning class 4 (Contact Fusions of Neos, Gladiator Beast Heraklinos/Gaiodiaz, Chimeratech Fortress Dragon, Armityle, VWXYZ/XYZ/YZ machines); the class table also gives 1 (Polymerization-only HERO Fusions), 2 (Dark Fusion), 3 (Fossil Fusion), 5 (Neo-Spacians). | 9 | 4 (4) | M |
| `0x08864300` (stub `0x09de4ce4`) | `card_db_can_be_normal_summoned` | `int (int card_id)` | 0 for spells, traps, Fusion/Ritual/Synchro monsters and monsters with a special summoning condition (class table: Theinen 5, Yubel - The Ultimate Nightmare 4, Wulf, Rare Metal Dragon ...); 1 otherwise. | 4 | 3 (3) | M |
| `0x088661a4` (stub `0x09de4d14`) | `card_db_get_turn_counter_rule` | `int (int card_id)` | Per-card turn-count setting: 2 or 3 turns (Swords of Revealing Light 3, Nightmare's Steelcage 2, Seismic Shockwave 3 ...), negative values for counts of both players' turns (Final Countdown -20, Lightforce Sword -4), 0xffff for open-ended counters (Pumpking, Castle of Dark Illusions, Blockman, Spark Blaster), 0 otherwise. | 7 | 3 (3) | L |
| `0x0885f944` (stub `0x09de4a0c`) | `card_db_get_next_alias_id` | `int (int card_id)` | Next id in a ring of ids treated as the same card: the paired Token ids (Fluff, Ojama, Sheep, Lamb), Neo-Spacian Twinkle Moss/Glow Moss and Marine Dolphin/Aqua Dolphin, Umi/A Legendary Ocean, Harpie Lady/Harpie Lady 1-3/Cyber Harpie Lady, and Dark Magician and Blue-Eyes White Dragon with an unreleased twin id; the id itself otherwise. | 1 | 1 (1) | M |
| `0x088630d8` (stub `0x09de4cbc`) | `card_db_get_evolution_relatives` | `int (int card_id, int *out)` | LV-monster and Chrysalis neighbours of a card: writes one or two related ids (previous/next LV, Chrysalis -> Neo-Spacian, Ultimate Insect LV1-LV7, Armed Dragon LV10 -> LV7 ...) and returns their count. | 10 | 1 (1) | M |

### Functions named for the per-card effect spec

Named while reducing the `partial` and `engine_only` cards of `tools/card_effects.py` (`card-effect-spec.md`, "Engine-mapped cards"). Basis: Ghidra decompilation of each function (`-readOnly`), its callers, and the card texts of its id lists (read locally, not copied). The first six are the unnamed callees of the ritual fallback record S/T 2 (`duel_effects_resolve_ritual_summon`); naming them makes that record complete, so the 28 ritual spells with a ritual-table entry reach `full`.

| Address | Name | Signature | Meaning | Callers | Conf. |
| --- | --- | --- | --- | --- | --- |
| `0x09dcebd8` | `duel_core_begin_select_tributes` | `void (int side, int a, int b, int (*filter)(int, int, int))` | Opens selection state 8: stores the arguments at `0x09e2d250`-`0x09e2d290` and the validator `0x09dceae8`; when the side is CPU-controlled (`0x09e02998[side] == 1`) runs `ai_run_card_selection`, else clears the result words. | 11 (ritual resolve, `0x09c11fec`, `0x09c12230`, `0x09da5xxx`-`0x09da7xxx`) | M |
| `0x09dceae8` | `duel_core_check_tribute_selection_soul_exchange` | `int (int side)` | Validator of state 8: 0 when the filter rejects, or when the selecting side may still pick an opponent monster that carries this side's Soul Exchange marker `0x13eb`; else `0x800`. | function pointer only | M |
| `0x09c27818` | `duel_core_post_announce_card` | `void (int side, int card_id)` | Posts command `0x2f` with the card id (bit 15 for side 1; `side < 0` sets `b = 1`, both players). The neighbour of `duel_core_post_announce_slot` (command `0x2e`). | 12 | M |
| `0x09c18e60` | `duel_core_send_ritual_hand_tribute` | `void (int side, int hand_index, int samsara)` | Sends a hand card Tributed for a Ritual Summon (`duel_core_send_hand_card`, reason `0x1000`, destination `0x0e`; `0x0c`/`0x0d` while Samsara `0x19da` is active); a tribute whose `card_db_get_race` is 1 adds player marker `0x14e2`. State 99 of the ritual resolve (`summon.md`). | 2 (`0x09ccd668`, `0x09da75f4`) | H |
| `0x09d9e8b4` | `ai_run_card_selection` | `void (int side, int a, int b)` | CPU answer to an open card selection: `ai_push_context`, `ai_submit_hand_card_choice`, then pops the context stack `0x09e03026` and re-analyses the board when the top entry changed. | 3 | M |
| `0x09d6a8d4` | `ai_submit_hand_card_choice` | `void (int side, int a, int b)` | Asks `ai_choose_hand_card_by_card` and submits the pick as player action `0x0b`; falls back to `0x09dcfb0c` when nothing is chosen. | 1 | M |
| `0x09ce28dc` | `duel_effects_cond_never` | `int (void)` | `jr ra; move v0, zero`: a condition slot that is never true. Used by 14 records (Hot Sauce Bottle, Spirit Message cards, the Sarcophagus cards ...) whose behaviour the engine triggers by card id. | function pointer only | H |
| `0x09c7eb14` | `duel_effects_resolve_noop` | `int (void)` | `jr ra; move v0, zero` as a resolve slot (Royal Decree, Imperial Order, The Emperor's Holiday). | function pointer only | H |
| `0x09bedc0c` | `duel_core_slot_has_piercing` | `int (int side, int slot)` | 1 when the slot's card has an active, non-negated effect and is in the piercing list (the same ids as `duel_core_has_piercing`; Ancient Gear Gadjiltron Dragon and Voltech Dragon by their tribute flags, the Familiar-Possessed by a slot marker). | import stub in `rel_duel_draw` | H |
| `0x09bfb1b0` | `duel_core_can_tribute_slot_for` | `int (int side, int slot_side, int slot, int card_id, int tributes)` | Per-card Tribute eligibility before `duel_core_can_tribute`: rules of the monster in the slot (The Immortal Bushi only for a Warrior, tokens that cannot be Tributed such as the Doomsday, Cloudian and Fluff Tokens, Fox Fire) and of the monster being summoned (the 3-Tribute Type monsters accept only their own Type, the Guardians need their equip on the field, Genex/Worm/Phantom Beast requirements, Infernal Incinerator-type ATK floor, attribute-matching rules). Returns 0 or the result of `duel_core_can_tribute`. | 9 | M |
| `0x09dbffd8` | `duel_core_step_apply_lp_change` | `void (int sign)` | Engine-command step that changes LP by `b` for side `a` (`0x09e290f8`), with UI events `0x10`/`0x4d` and the duel statistics. When the damage reduces the LP to 0 and the source is one of the eleven "win the Match" monsters (Victory Dragon, the 3-Tribute Type monsters), stores that id in the loser's player word `+0x2c`. | command handler | M |
| `0x09dabf4c` | `duel_core_get_procedure_material_rule` | `void (int card_id, int *count)` | For monsters with a Special Summon procedure that consumes materials (Gate Guardian, Des Guardius, Dogma, the Toons, Perfectly Ultimate Great Moth, Montage Dragon ...): returns nothing but selects a material filter callback (`duel_core_filter_tribute_candidate` or `0x09da3bec`-`0x09daaff0`) and writes the count 1-3 to `*count` (0 = no rule). | 1 (`0x09d899a8`, CPU) | M |
| `0x09bf6728` | `ai_is_special_summon_effect` | `int (short *link)` | 1 when the link's resolve handler is one of the Special Summon resolvers (from Deck, from hand, revive, ritual ...), else a per-card test of genre 3 cards. Every caller is CPU code. | 12 (CPU) | M |
| `0x09dda1cc` | `duel_core_apply_post_attack_defense_change` | `int (int side)` | At the end of the attack: every active, non-negated monster with marker `0x14d6` that is Goblin Attack Force, Spear Dragon or one of the listed monsters is changed to Defense Position (and gets marker `0x1419` for the "cannot change position" monsters); returns 1 when none is left. | 1 (`duel_core_battle_step_end`) | H |
| `0x09cdd74c` | `duel_core_apply_forced_positions` | `int (void)` | Chain building state 0: forced battle-position changes for the listed cards (Level Limit - Area A/B type) before a chain starts. | 1 (`duel_core_chain_build_step`) | M |
| `0x09c1fb50` | `duel_core_apply_leave_field_rules` | `void (int side, int slot, int destination, uint flags)` | Per-card consequences when a field card is sent away (destination `0x0e` = Graveyard): Destiny Board removes the Spirit Messages, Pyramid of Light destroys its sphinxes, Fulfillment of the Contract destroys its monster, the Sarcophagus cards, Doom Shaman, Kinka-byo ... | 1 (`duel_core_send_field_card`) | M |
| `0x09be6d90` | `duel_core_apply_phase_start_attack_rules` | `void (int side, int phase)` | Scans the attack-rule markers at the start of a phase (attack-all monsters, The Dark Door). | 1 (`duel_core_cmd_enter_phase`) | L |
| `0x09bf5970` | `duel_effects_is_spell_trap_negator` | `int (int card_id)` | 1 for a list of about 30 cards that negate or ignore Spell/Trap effects (Royal Decree, Jinzo-type ...). | 1 (`0x09c3a56c`) | L |
| `0x08863a34` (BOOT) | `card_db_get_fusion_summon_class` | `int (int card_id)` | Summoning class of a Fusion: 1 Polymerization, 2 Dark Fusion, 3 Fossil Fusion, 4/5 own procedures (the class table of `card_db_is_summoned_without_polymerization`). | import stubs | M |
| `0x08864c60` (BOOT) | `card_db_is_fusion_class_summonable` | `int (int card_id)` | The same class table inlined; 1 for classes 0-3. | import stubs | L |
| `0x08865ad8` (BOOT) | `card_db_is_extra_deck_unrestricted` | `bool (int card_id)` | True for Synchro frames (`card_db_get_frame == 10`) and class 0. | import stubs | L |
| `0x0886354c` (BOOT) | `card_db_get_special_summon_condition_class` | `int (int card_id)` | Special summoning condition class 0-5 per card id (the class table behind `card_db_can_be_normal_summoned`). The meaning of each class is open. | import stubs | L |
| `0x088544f8` (BOOT) | `save_set_card_milestone_flag` | `void (int card_id, int offset)` | Writes 1 to a per-card byte of the save state (`save_get_state() + 0x153e4 + offset + k`) for 13 card ids. Bookkeeping, not an effect. | import stubs | M |
| `0x08866870` (BOOT) | `card_db_is_fusion_substitute` | `int (int card_id)` | 1 for the eight Fusion-substitute monsters (Goddess with the Third Eye, Beastking of the Swamps, Versago the Destroyer, Mystical Sheep #1 ...). | import stubs | M |
| `0x088669a0` (BOOT) | `card_db_is_control_locked` | `int (int card_id)` | 1 for four ids (Blindly Loyal Goblin, Mataza the Zapper ...): control of these cannot switch. Raised from L to M: its only engine consumer is `duel_core_is_control_change_blocked` under `duel_effects_can_take_control`. | import stubs | M |

### Second round: functions that blocked the most cards

The unnamed functions were ranked by how many `partial`/`engine_only` cards they would unblock under the engine-mapped rule (a greedy cover over the cards whose only blockers are unnamed functions). Each was decompiled in Ghidra (`-readOnly`); the owner of a record handler (a function with no callers) comes from the effect records that point to it. A semantic row of `tools/engine_ref_semantics.csv` was added only where the decompiled branch supports the tag; where one function holds both the card's own rule and ids that another card's effect names, the new `operand` column separates them (`docs/formats/card-refs.md`, "Semantics"). Functions marked D are also in `re/documented-duel_eng.tsv` with prototype, side effects and callers.

| Address | Name | Meaning | Callers | Conf. |
| --- | --- | --- | --- | --- |
| `0x09da3dfc` | `duel_core_filter_procedure_material` (D) | Material filter of the one-monster Special Summon procedures, chosen by the card being summoned (`0x09e290c0`): Metalzoa (Zoa + Metalmorph), Red-Eyes Black Metal Dragon, Plasma Warrior Eitom (Level 7+), Masked Beast Des Guardius, Dark Eradicator Warlock, Red-Eyes Darkness Dragon ... Returns `0x800` for a valid slot. | `0x09d9fe24`, `0x09da4314`, `0x09da446c` | H |
| `0x09da3bec` | `duel_core_filter_moth_procedure_material` (D) | Petit Moth with a Cocoon of Evolution link at least 2/4/6 turns old for Larvae Moth / Great Moth / Perfectly Ultimate Great Moth. | `0x09d9fce4` | H |
| `0x09da9470` | `duel_core_filter_familiar_possessed_material` (D) | The Charmer of each Familiar-Possessed plus a monster of its Attribute. | `duel_core_get_special_summon_mask` | H |
| `0x09da784c` | `duel_core_summon_step_cost_procedure` | `summon_prepare` state machine for hand costs: The Tricky and Dark Grepher discard, Izanagi sends a card, Montage Dragon sends 3 and sums their Levels into `0x09e290c8`. | `duel_core_summon_prepare` | H |
| `0x09da0510` | `duel_core_get_procedure_banish_count` (D) | Graveyard cards banished by each banish-cost procedure (Spirit of Flames, Soul of Purity and Light, Fenrir, Earth Giant Gaia Plate, Megarock Dragon, Spell Striker, Beast Machine King Barbaros Ur ...). | `0x09da7b84`, `0x09daaad8` | H |
| `0x09da7b84` | `duel_core_summon_step_banish_procedure` | `summon_prepare` states that open the Graveyard list filtered by the summoned card's Attribute or Type and banish the picks (or the hand/field copy). | `duel_core_summon_prepare` | H |
| `0x09da60f8` | `duel_core_summon_step_necroshade` | Asks with Elemental Hero Necroshade's name and adds player marker `0x197f` (Tribute Summon without Tributes once while it is in the Graveyard). | `duel_core_summon_prepare` | M |
| `0x09daa470` | `duel_core_summon_step_swift_gaia` | Asks with Swift Gaia's name when the summon-set masks allow its no-Tribute Normal Summon. | `duel_core_summon_prepare` | M |
| `0x09ddd544` | `duel_core_queue_spirit_return_triggers` (D) | End Phase return of Spirit monsters; none while Spiritual Energy Settle Machine is active, optional with Izanagi or Mirror of Yata. | function pointer | H |
| `0x09dd11dc` | `duel_core_is_attack_optional` | 0 when the monster must attack (Dark Arena, Berserk Gorilla, Ultimate Tyranno, Evil Hero Malicious Fiend, Attribute Gravity, markers `0x15ff`/`0x14a6`/`0x1669`/`0x1eee` ...). | `duel_core_battle_step_declare_attack`, CPU | M |
| `0x09dd0b88` | `duel_core_can_end_battle_phase` | 0 while a monster that must attack can still attack (same card set). | `duel_core_get_phase_menu_mask`, `duel_core_step_main_phase`, `duel_core_battle_step_select_attack`, CPU | M |
| `0x09c0da14` | `duel_core_get_hand_size_limit` (D) | Hand limit 6 / none (Infinite Cards) / 5 (Enervating Mist) / 7 (Hieroglyph Lithograph). | `duel_core_enforce_hand_limit`, CPU | H |
| `0x09db7db8` | `duel_core_cmd_destroy_by_effect` | Engine command `0x30` (`duel_core.md`). | `duel_core_execute_command` | H |
| `0x09db8a50` | `duel_core_cmd_destroy_by_battle` | Engine command `0x31`; per-card markers for Dark Ruler Ha Des, Element Soldier, Boss Rush. | `duel_core_execute_command` | H |
| `0x09db9f40` | `duel_core_cmd_banish_field_card` | Engine command `0x32`; listed marker keys (Dark Lucius LV8, Ultimate Insect LV7 ...) are re-attached to the player. | `duel_core_execute_command` | H |
| `0x09db4d34` | `duel_core_cmd_send_field_card` | Engine command `0x3f`. | `duel_core_execute_command` | H |
| `0x09db561c` | `duel_core_cmd_place_list_card` | Engine command `0x40`. | `duel_core_execute_command` | H |
| `0x09db9878` | `duel_core_cmd_tribute_card` | Engine command `0x45`. | `duel_core_execute_command` | H |
| `0x09db6cc0` | `duel_core_cmd_change_face` | Engine command `0x34`; attaches effect 7 from each active Judgment of the Desert. | `duel_core_execute_command` | H |
| `0x09c00a50` | `duel_core_add_active_card_count` (D) | Adds to the slot value of every active copy of a card (Fatal Abacus, Skull Invitation counts). | the card-move commands | H |
| `0x09c00b94` | `duel_core_flag_active_card` (D) | Sets slot flag bit 7 of every active copy of a card. | the card-move commands | H |
| `0x09cde754` | `duel_effects_resolve_counted_damage` (D) | Converts those counts into damage: Fatal Abacus 500, Skull Invitation 300 per card. | function pointer | H |
| `0x09cde168` | `duel_effects_resolve_discard_damage` (D) | 500 per counted card to the opponent (Magical Thorn). | function pointer | H |
| `0x09bfe878` | `duel_core_is_control_change_blocked` (D) | `card_db_is_control_locked` plus Element Valkyrie / Element Soldier while a WATER monster is on the field. | `duel_effects_can_take_control`, `0x09c146f0` | H |
| `0x09db315c` | `duel_core_apply_attack_declaration` | Bookkeeping of an attack declaration: per-card markers (Dizzy Tiger), the Ultimate Tyranno flag, player/duel flags. | `duel_core_cmd_declare_attack`, `_declare_direct_attack` | M |
| `0x09be6ac4` | `duel_core_init_battle_phase_attack_state` | Phase 3: detaches the per-card attack-count effects (Chimeratech Overdragon, Chain Thrasher, Ben Kei ...), marks the opponent's monsters when it controls two or more, sets the must-attack word of Ultimate Tyranno; phase 0 attaches `0x1911`. | `duel_core_cmd_enter_phase`, `0x09d12a24` | M |
| `0x09bee500` | `duel_core_record_attack_done` (D) | After an attack: attacked bits and the per-card attack-count effects. | `duel_core_cmd_attack_done`, `duel_core_cmd_negate_attack` | H |
| `0x09c1be50` | `duel_core_send_field_card_body` | 13,844-byte body of `duel_core_send_field_card`: per-card markers when a field card is removed (Makyura, Mokey Mokey Smackdown ...). | `duel_core_send_field_card` | M |
| `0x09c147f0` | `duel_core_check_targeting_links` | Walks the links that point at a monster: negates and destroys targeting Spells/Traps for Freed, Ryu Senshi, Tyrant Dragon, Fiend Skull Dragon, Ancient Gear Engineer, Frontier Wiseman, Obsidian Dragon, Arcana Force 0 (unless Splendid Venus); ends links whose condition fails (Limit Reverse, Soul Devouring Bamboo Sword, Rare Metalmorph, Alien Hypno, Option tokens, equips failing their filter). | `0x09ce2558` | M |
| `0x09befe58` | `duel_core_get_battle_destruction_countdown` (D) | Smallest Zone Eater / Steel Scorpion countdown on a slot. | function pointer | M |
| `0x09c2796c` | `duel_core_is_damage_converted_to_gain` (D) | Rainbow Life / Prime Material Dragon conversion, blocked by the opponent's LP-gain reversers. | 7 (damage posting, CPU) | H |
| `0x09c0c4c8` | `duel_core_can_use_deck` (D) | 0 while Deck Lockdown is active. | `duel_effects_collect_deck_candidates`, CPU | H |
| `0x09bf0e20` | `duel_core_substitute_covers_slot` (D) | Which monsters a destruction substitute protects (Plant Type for Nettles, Six Samurai ...). | `duel_core_battle_step_damage_calc`, `duel_core_send_batch_step` | M |
| `0x09bf0d68` | `duel_core_is_destruction_substitute` (D) | Whether a slot's card can be destroyed instead (BOOT list `0x08861d2c`, Nettles, `0x1f0d`). | same | M |
| `0x09be4648` | `duel_core_record_duel_result` | End of duel: result words, save milestones (`save_set_card_milestone_flag` for 0x1468 / Exodia), duel-condition check. | function pointer | M |
| `0x09be3bc0` | `duel_core_check_duel_condition` | Switch on the duel-condition index (`+0x290` of the duel record): damage thresholds (`0x09dcb734`) or "card X was used" tests. Bookkeeping, not an effect. | `duel_core_record_duel_result` | M |
| `0x09dcbbcc` | `duel_core_was_card_used_in_duel` | 1 when an instance of the card id is flagged in the bit set `0x09e02f24`. | `duel_core_check_duel_condition`, `0x09be2eac` | M |
| `0x09beefb4` | `duel_effects_is_archfiend_roll_success` (D) | Die results that trigger each Archfiend's negation. | `duel_core_chain_step`, `duel_core_action_dice_roll` | H |
| `0x09c3dd68` | `duel_effects_filter_target_by_source` (D) | Shared target filter with a per-source condition (Tail Swipe, Lone Wolf, Staunch Defender, Defense Maiden, Jam Defender ...). | six records | H |
| `0x09c355c4` | `duel_effects_filter_target_by_source_b` | A second shared target filter switching on the source id (Orca Mega-Fortress of Darkness: Torpedo Fish / Cannonball Spear Shellfish ...). | six handlers | M |
| `0x09c55b90` | `duel_effects_is_negated_by_active_locks` (D) | Lock-state negation of Spells, Traps and monsters; Royal Decree spares itself. | `duel_effects_is_negated_on_resolution` | M |
| `0x09cdcdc0` | `duel_effects_update_field_spell_override` (D) | Active Field Spell, Umi while Maiden of the Aqua is face-up. | `duel_effects_check_rule_list` | H |
| `0x09cdeb90`, `0x09ce0724` | `duel_effects_check_self_destruct_rules`, `_b` | Per-card "destroy this card when its condition fails" checks on the argument id (Thunder Nyan Nyan, Exodia Necross, Sanguine Swamp ...). | function pointers | M |
| `0x09c02b48` | `duel_effects_is_candidate_allowed_by_locks` | Candidate filter: no monster while an opposing monster has a Metalsilver Armor link; Lightsworn lock `0x1e74`. | 10+ candidate filters | M |
| `0x09bf2910` | `duel_effects_is_activatable_in_window` | Switch on the response window with per-card lists. | `duel_effects_can_respond_in_window` | M |
| `0x09cba5dc` | `duel_effects_check_fusion_materials` | Fusion material check of an Extra Deck card: F.G.D. and `0x1e7e` need 5, `0x1ab3`/`0x19ef` 4; other Fusions use the 138-entry recipe table at `0x09debe98`. | `duel_core_get_special_summon_mask`, `duel_effects_collect_extra_deck_candidates`, 4 more | M |
| `0x09c34b18` | `duel_effects_filter_time_stream_target` (D) | Time Stream's target: the next Fossil Knight form in the Extra Deck. | record of Time Stream | H |
| `0x09c6b9d4` | `duel_effects_filter_instant_fusion_candidate` (D) | Instant Fusion candidate filter; none while Non-Fusion Area is active. | record of Instant Fusion | H |
| `0x09cbd068` | `duel_effects_cond_time_stream` (D) | Time Stream condition; false while Non-Fusion Area is active. | record of Time Stream | H |

Rows without a name: other cards' record handlers that only name the blocked card (Dragon Piper `0x09c34cf4`, Desrook Archfiend `0x09c61e38`, Orca Mega-Fortress of Darkness `0x09c3b904`, The First Sarcophagus `0x09c497e8`/`0x09c9af3c`, Silent Magician LV4 `0x09c64eac`, Machiners Force `0x09c66200`, Burst Stream of Destruction / Evolution Burst `0x09c997f4`, the shared link handler `0x09c36bdc`, the shared resolve `0x09c4c140`) get `named_reference`; `0x09be2eac` (whose body `0x09be2fb8`-`0x09be3bb8` Ghidra cut off) gets `save_record` like `duel_core_check_duel_condition`. Arguments in the id range passed to `duel_effects_target_filter` are flag words (`effect-tables.md`) and get the new generic tag `not_card_id`; this removed false card references for Hayabusa Knight (`0x1411`), Mad Sword Beast (`0x1416`) and Alchemic Kettle - Chaos Distill (`0x1444`).

## Open questions

- Prompt-request kinds 4, 7 and 8 (`0x09c13d40`, `0x09c14284`, `0x09c14480`) and the meaning of UI events 3 (command 7) and `0x2a` (mode 9 picks).
- Command `0x28` with a non-zero location and reference 0 (`duel_core_post_show_location`): what the presentation layer shows.
- Mode `0x0d`: whether every caller declares an Attribute (the prompt is the Attribute one, message `0xf2`) or only reuses its mask mechanism.
- `card_db_fusion_allows_substitute`: the reading "no Fusion substitute" for the eleven listed Fusions is a hypothesis; the flag is only consumed by `duel_effects_can_fusion_with_materials`.
- `card_db_get_turn_counter_rule`: the sign convention (positive own turns, negative both players' turns, `0xffff` open-ended) needs a runtime check.
- `duel_core_raise_attack_event`: the meaning of timing event `0x12` (raised with the packed attacker and target).
- `duel_core_get_slot_activation_kind` and `duel_core_flag_face_up_copies` (slot flag 7): the meaning of the returned kinds and of the flag.
- The 87 records still partial reach no effect category; they need categories (new `effect_categories.csv` rows or per-card reading), not names.
- `card_db_get_special_summon_condition_class` (BOOT `0x0886354c`): what classes 1-5 mean (stays L until a caller is read).
- `0x09be2eac`: Ghidra ends the function at 268 bytes; the code at `0x09be2fb8`-`0x09be3bb8` (jump-table cases that call `duel_core_was_card_used_in_duel`) has no function. Re-create the function body and check whether it is a second duel-condition table.
- `duel_core_check_duel_condition` / `duel_core_was_card_used_in_duel`: which game feature the condition index at `+0x290` belongs to (duel bonuses or story challenges), and what sets the bit set `0x09e02f24`.
- `duel_core_is_destruction_substitute`: the BOOT list `0x08861d2c` and card `0x1f0d` (unreleased) are not identified.
- The 24 cards whose engine references carry only L descriptive tags (`duel_core_battle_resolve`, `duel_core_battle_step_*`, `duel_core_get_battle_flip_trigger` ...) need those named functions read branch by branch before their rows can be raised.
- `duel_core_begin_select_tributes`: the meaning of its arguments `a`/`b` and of selection state 8 outside Ritual and Tribute selections.
