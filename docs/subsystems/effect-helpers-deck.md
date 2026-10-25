# Effect helpers: deck, hand, Graveyard and Special Summon (work package 4)

Helpers that per-card effect handlers of `gmodule/rel_duel_eng.prx` (runtime base `0x09be1400`) call to draw, search, discard, mill, shuffle, reveal, return cards to the hand or Deck, banish from the Graveyard and Special Summon by effect (including tokens). Companion of `duel_effects.md` (architecture), `effect-tables.md` (handler slots), `duel_core.md` (zones, location ids `0x0b` hand … `0x0f` banished, card references), `chain.md` (resolution sub-state `0x09e28f60`) and `summon.md` (summon record, `duel_core_special_summon`).

All addresses are runtime addresses in the module. "Callers" counts direct calls in the Ghidra call graph; "records" counts effect-table records (24-byte tables and 8-byte lists) that point at the function itself. Card examples come from the records that reach the function (`tools/cardinfo.py` names). Confidence: H high, M medium, L low.

Method: every table handler was decompiled (headless `DumpAll.java` over the module), the callees of slot `+04` handlers (802 distinct resolve handlers) were ranked by the number of handlers and cards that reach them, and the most called ones in this domain were read, together with the generic resolve handlers shared by the most cards (E - Emergency Call, Mystic Tomato, Monster Reborn, Call of the Haunted, Foolish Burial, Graceful Charity, Scapegoat …). Ghidra's stock MIPS decompiler was sufficient; none of these functions uses VFPU code.

## 1. The candidate list: how "choose a card from the Deck" works

**Finding (H).** Searching is data-driven. The 8-byte list at `0x09dec554` (686 records, `(card id, builder)`, sorted by id; `effect-tables.md` "list L1") is the **candidate-builder table**: for each card that picks cards from a location, a small builder fills a global candidate list. Most builders are one call to a generic per-location scanner with a **filter word** (Type, Attribute, Level, ATK, monster/spell/trap, name) plus an optional predicate (archetype). The resolve handler then shows that list (`duel_core_open_card_list`, mode 6) and reads the player's choice.

Candidate list globals:

| Address | Meaning |
| --- | --- |
| `0x09e29920` | Number of candidates (max `0x200`). |
| `0x09e29928 + i × 4` | Candidate `i`: a copy of the 4-byte list entry (card id + instance reference, `duel_core.md`). |
| `0x09e2a128 + i × 2` | `u16`: low 7 bits `side × 0x80 + location` (bits 0–6 location, bit 7 side); high byte = pick order when several are picked. |
| `0x09e2991c` | Index of the selected candidate. |
| `0x09e29924` | Query pointer: when non-zero, a builder stores its filter word there instead of collecting (used by the AI functions `0x09cfabec`, `0x09d06188`, `ai_choose_normal_summon` … and by `duel_effects_target_still_matches_filter`). |

### Builders and scanners

| Address | Name | Signature | Behaviour | Callers / records | Conf. |
| --- | --- | --- | --- | --- | --- |
| `0x09cdc85c` | `duel_effects_build_candidate_list` | `int (int side, int card_id, int param)` | Clears the list, binary-searches `0x09dec554` for `card_id`, calls the builder with `(side, card_id, param)`, returns the count. | 75 callers (57 handlers, 280 cards) | H |
| `0x09cdc90c` | `duel_effects_count_candidates` (existing name) | `int (int side, int card_id, int param)` | Same lookup but appends and restores the count; returns how many the builder would add. Used by activation conditions. | 126 | H |
| `0x09cdc7d0` | `duel_effects_add_candidate` | `void (int side, int location, int index)` | Appends `duel_core_get_location_entry(side, location, index)` and its location byte. | 34 | H |
| `0x09ccecbc` | `duel_effects_collect_deck_candidates` | `int (int side, int card_id, pred_fn pred, void *pred_arg, uint filter, uint options)` | Walks the Deck (top first), applies `filter` with `duel_effects_candidate_matches_filter`, spell/trap bits, the predicate, and `options`; adds matches. | 81 builders (189 cards) | H |
| `0x09ccf134` | `duel_effects_collect_extra_deck_candidates` | same shape | Extra Deck (location `0x0c`); adds Fusion/Synchro tests. | 14 | M |
| `0x09ccf428` | `duel_effects_test_hand_candidate` | `int (int side, int card_id, int hand_index, pred_fn, void *, uint filter, uint options)` | Tests one hand card (option bit 0: it must be sendable to the Graveyard, `duel_core_can_send_ref_to_graveyard`). | 56 | M |
| `0x09ccf768` | `duel_effects_collect_graveyard_candidates` | same shape as the Deck scanner | Graveyard; checks `duel_core_can_banish_from_graveyard`, `duel_core_can_special_summon_from_graveyard` according to options. | 93 builders (120 cards) | M |
| `0x09ccfcdc` | `duel_effects_collect_banished_candidates` | same shape | Banished zone. | 2 | M |
| `0x09cce9a8` | `duel_effects_candidate_matches_filter` | `int (int side, int location, void *entry, uint filter)` | Monster filter test (below). | 5 (the scanners) | H |
| `0x09cd02b0` | `duel_effects_candidate_in_archetype` | predicate `(side, location, index, card_id, entry, int *archetype)` | `BOOT.BIN 0x088633f8(entry id, *archetype)`; E - Emergency Call passes 8 ("Elemental Hero"), Gravekeeper's Spy 2. | used as a pointer | M |
| `0x09cdc9ec` | `duel_effects_count_hand_candidates` | `int (void *ctx, int side)` | Calls the card's builder once per hand index and counts the hand cards that produced a candidate. | 3 | M |
| `0x09cdc9d0` | `duel_effects_count_controller_hand_candidates` | `int (void *ctx)` | Same for the controller. | 32 | M |
| `0x09cc0dd0` | `duel_effects_get_candidate_param` | `int (void *ctx)` | Per-card compare chain giving the builder's `param` (a Level, a chosen card, a slot, an ATK value with bit 28 …); 0 for most cards. | 64 | M |
| `0x09cdcb34` | `duel_effects_target_still_matches_filter` | `int (void *ctx, int target)` | For a Graveyard target, runs the card's builder in query mode and re-checks Type (bits 27–31) and Attribute (bits 24–26); called by `duel_effects_link_target_is_valid`. | 1 | M |

**Filter word** (`duel_effects_candidate_matches_filter`; scanners add the spell/trap bits):

| Bits | Test | Evidence | Conf. |
| --- | --- | --- | --- |
| `0x1` | (scanner) count only, do not add | code | H |
| `0x2` | Monster card (`BOOT 0x0885fef0`); without it the filter function rejects | code | H |
| `0x4`, `0x8` | (scanner) Spell (`0x0885ff3c`), Trap (`card_db_is_trap`); `0x380` = spell/trap icon + 1 | code; Reinforcement-like spell searches pass 4 | H |
| `0x10` / `0x20` | (scanner) same name as / different name from `card_id` (`0x0885fb5c`) | code | H |
| `0x400` | Normal Monster (`0x0885ff84`; in the hand `0x09c02f80`) | Advanced Ritual Art uses the same predicate | M |
| `0x800`, `0x1000` | Can be Special Summoned (`duel_core_can_special_summon_card`), summon conditions (`0x09c0c8a0`) | code | M |
| `0x2000` | ATK ≤ 1500 (`< 0x5dd`) | Sangan, Mystic Tomato, Giant Rat, Gravekeeper's Spy pass `0x2002` | H |
| `0x4000` | FLIP monster (`0x08863438`) | code | M |
| `0x8000` | Tuner (`0x088601c0`) | code | M |
| `0x10000` | `0x09c02b48(side, id)` must hold | common in Graveyard filters (`0x10002`); meaning open | L |
| `0x3c0000`, `0x400000`, `0x800000` | Level field (bits 18–21); bit 22 "≥", bit 23 "≤", neither "=" | code | H |
| `0x7000000` | Attribute (bits 24–26) must equal | Mystic Tomato passes its own Attribute (DARK), Giant Rat EARTH | H |
| `0xf8000000` | Type (bits 27–31) must equal | code | H |

**Options word** (Deck scanner): `0x1` scan the opponent's Deck; `0x2` skip cards marked by Parasite Paracide (marker `0x12a1`); `0x4` requires `duel_core_can_add_from_deck_to_hand`; `0x8` / `0x10` Special Summon tests (`0x09c0cb84` / `0x09c0cb98`); `0x20` extra predicate `0x0885ffc0`; `0x40` stop at the first match; bits 25–31 limit the scan to the top *n* cards. Recruiters pass `0x0a` (Special Summon test, skip Parasite). (M for the bits other than `0x1`, `0x40`, top-*n*.)

### Reading the choice

| Address | Name | Signature | Behaviour | Callers | Conf. |
| --- | --- | --- | --- | --- | --- |
| `0x09dc9cc8` | `duel_core_get_selected_candidate` | `void *(void)` | `&0x09e29928[0x09e2991c]`. | 111 | H |
| `0x09dc9cbc` | `duel_core_set_selected_candidate_index` | `void (int index)` | Sets `0x09e2991c` (cards with exactly one choice skip the list). | 6 | H |
| `0x09dca410` | `duel_core_get_picked_candidate` | `void *(int order)` | Candidate whose pick order (high byte of the meta word) equals `order`; for multi-picks (Foolish Burial ×2, Rescue Cat). | 26 | H |
| `0x09dc9d00` | `duel_core_get_selected_candidate_location` | `int (void)` | Location of the selected candidate (`0x0d` Deck, `0x0e` Graveyard): Woodsman-type "Deck or Graveyard" searches branch on it. | 14 | H |

### Activation conditions built on the list (slot `+0c`)

| Address | Name | Behaviour | Callers / own records | Conf. |
| --- | --- | --- | --- | --- |
| `0x09c56ce4`, `0x09c56c8c` | `duel_effects_has_candidates`, `_b` | Identical: the builder finds at least one candidate. Foolish Burial, Burial from a Different Dimension, Graverobber. | 26 / 9, 27 / 25 | H |
| `0x09c56adc`, `0x09c56b74` | `duel_effects_can_special_summon_candidate`, `_b` | Identical: free Monster Zone, Special Summon allowed for this card, and a candidate exists (recruiters, Monster Reborn-type). | 27 / 47, 24 / 12 | H |
| `0x09c56c0c` | `duel_effects_can_special_summon_hand_candidate` | Same with a hand candidate (`duel_effects_count_controller_hand_candidates`). | 13 / 7 | H |
| `0x09c56a78` | `duel_effects_can_special_summon_now` | Free Monster Zone and `duel_core_can_special_summon_id(controller, id)`. | 71 | H |

## 2. Player card requests (discard, random discard, look at a hand, show the Deck)

**Finding (H).** Effects that need the duelist to pick from the hand, or that reveal a hand or Deck, do not drive the UI themselves. They post a **card request**: a small record that `duel_core_run_pending_action` (`0x09c0e8b8`, called every frame by `duel_core_run_turn_flow`) executes step by step, then the handler continues. In link duels the request is sent to the peer (`0x09dcc884`, messages `0x1e`/`0x1f`).

| Address | Field |
| --- | --- |
| `0x09e2d2dc` | Remote state: 0 local, 2 send to the peer, 1 waiting for it. |
| `0x09e2d2e0` | Request active. |
| `0x09e2d2e4` | Side that answers. |
| `0x09e2d2e8` | Mode (below). |
| `0x09e2d2ec` | Step within the mode. |
| `0x09e2d2f0`, `0x09e2d2f2` | Arguments (`u16`; up to five `u16` from `0x09e2d2f0`). |
| `0x09e2d2fa`, `0x09e2d2fc`, `0x09e2d2fe` | Result (chosen/random index or reference), remaining count, last selection. |

| Mode | Worker | Meaning | Setter(s) | Conf. |
| --- | --- | --- | --- | --- |
| 1, 2 | `duel_core_card_request_discard_step` (`0x09c103e0`) | The side selects `count` hand cards (filter `duel_core_filter_discard_candidate`) and discards them | `duel_core_request_discard`, `_discard_kind`, `_hand_limit_discard`, `_discard_cost`, `_discard_cost_ex`, `0x09c0f0e4`, `0x09c0f18c` | H |
| 3, 4 | `duel_core_card_request_random_discard_step` (`0x09c10798`) | Random hand card(s): mode 3 discards, mode 4 sends to the Graveyard; count 0 only picks a random index | `duel_core_request_random_discard`, `_random_hand_to_graveyard` | H |
| 5 | `duel_core_card_request_random_banish_step` (`0x09c109d8`) | Random hand card(s) banished (count 0: random pick only) | `duel_core_request_banish_random_hand_cards` | H |
| 6 | `duel_core_card_request_choose_hand_card_step` (`0x09c10d10`) | Look at the opponent's hand (flag bit 0 reveals it, command `0x53`) and choose one card; a CPU side picks at random | `duel_core_request_choose_opponent_hand_card` | H |
| 7 | `0x09c111a8` | Select cards in one's own hand with a per-card filter | `duel_core_request_select_hand_cards`, `_ex` | M |
| 8 | `0x09c129cc` | Show the other side's hand and/or Deck (`duel_core_open_card_list`) | `duel_core_request_show_hand_and_deck`, `_show_hand`, `_show_deck` | H |
| `0x0e` | `0x09c12b98` | Card-specific list selections (Painful Choice, Question, Dimension Jar, Jade Insect Whistle, Spell Chronicle, Vampire Lord, Virus Cannon) | `duel_core_request_select_list_cards`, `0x09c0fc50` | L |
| 9–`0x0d`, `0x0f`–`0x15` | various | Outside this domain: tribute/zone selection (9, 10, `0x0b`), negate all links (`0x0c`), declarations (`0x0d`, `0x14`), effect battle (`0x11`), coin toss (`0x12`), dice (`0x13`), deferred resolution (`0x15`) | `0x09c0f55c` …`0x09c10168` | L |

Setters (all store side, mode, arguments, clear the step, and arm the remote state for the CPU-opponent case):

| Address | Name | Signature | Behaviour | Example cards | Conf. |
| --- | --- | --- | --- | --- | --- |
| `0x09c0edf4` | `duel_core_request_discard` | `void (int side, int count, int monsters_only, int by_opponent)` | Mode 1; flag bit 0 monsters only, bit 1 the effect belongs to the opponent. Nothing when `count` is 0. | Graceful Charity, Delinquent Duo, Dark World Dealings | H |
| `0x09c0ee9c` | `duel_core_request_discard_kind` | `void (int side, int count, int kind, int by_opponent)` | Mode 1; kind 1 monster, 8 trap (flag 4), 7 spell (flag 8). | Magic Drain, Dark Spirit Art - Greed | H |
| `0x09c0ef70` | `duel_core_request_hand_limit_discard` | `void (int side, int excess)` | Mode 1, flag `0x80` (plain discard without effect filter). | End Phase | H |
| `0x09ddf468` | `duel_core_enforce_hand_limit` | `int (int side)` | Limit from `0x09c0da14` (`0xffff` = none); requests the discard of the excess and returns 0, else 1. | End Phase | M |
| `0x09c0f020` | `duel_core_request_discard_cost_ex` | `void (int side, int count, int kind)` | Mode 2, flag `0x10` = cost (discard as cost, `duel_core_discard_hand_card_as_cost`); kind as above. | slot `+10` handlers | H |
| `0x09c0effc` | `duel_core_request_discard_cost` | `void (int side, int count, int monsters_only, int spells_only)` | Wrapper of the previous (kind 1 or 7). Called by `duel_effects_cost_discard`. | 125 cards (costs) | H |
| `0x09c0f244` | `duel_core_request_random_discard` | `void (int side, int by_opponent, int count)` | Mode 3. | Spirit Reaper, Robbin' Goblin, Don Zaloog, Mind Crush | H |
| `0x09c0f2c8` | `duel_core_request_random_hand_to_graveyard` | `void (int side, int by_opponent, int count)` | Mode 4. | Ruthless Denial | M |
| `0x09c0f34c` | `duel_core_request_banish_random_hand_cards` | `void (int side, int count)` | Mode 5. | Lightforce Sword, Inspection, Ominous Fortunetelling, Goblin Recon Squad | M |
| `0x09c0f3d0` | `duel_core_request_choose_opponent_hand_card` | `void (int side, int select_mode, int flags)` | Mode 6. | Confiscation, The Forceful Sentry, Exchange, Trap Dustshoot | H |
| `0x09c0f454` | `duel_core_request_select_hand_cards` | `void (int side, int count)` | Mode 7. | Allure of Darkness, Pot of Generosity, Common Charity | M |
| `0x09c0f4d8` | `duel_core_request_select_hand_cards_ex` | `void (int side, int count, int arg)` | Mode 7 with an argument. | Magical Mallet | M |
| `0x09c0f6f8` | `duel_core_request_show_hand_and_deck` | `void (int viewer, int hand, int deck)` | Mode 8 for the other side's hand/Deck, each only if non-empty. Used when a "from hand or Deck" summon finds nothing. | Armed Dragon LV3, A Deal with Dark Ruler | H |
| `0x09c0f804` | `duel_core_request_show_hand` | `void (int viewer)` | Mode 8, hand only. Failed hand summons reveal the hand. | Ancient Rules, Contract with Exodia | H |
| `0x09c0f8c4` | `duel_core_request_show_deck` | `void (int viewer)` | Mode 8, Deck only: a search that found nothing shows the Deck to the opponent. | E - Emergency Call, Mystic Tomato, Foolish Burial (178 cards) | H |
| `0x09c0fbcc` | `duel_core_request_select_list_cards` | `void (int side, int a, int b)` | Mode `0x0e`. | Painful Choice, Question, Dimension Jar | L |
| `0x09c101ec` | `duel_core_filter_discard_candidate` | `int (int side, int location, int index)` | Selection callback of mode 1/2: flag bits 1 monster, 8 spell, 4 trap, `0x10` `duel_core_can_discard_card`, `0x20` must be sendable to the Graveyard; never cards marked by Parasite Paracide; returns `0x800` when selectable. | — | H |

`0x09c0e8b8` is `duel_core_run_pending_action()`: returns 1 when idle or finished, 0 while a step is in progress.

## 3. Hand primitives

| Address | Name | Signature | Behaviour | Callers | Conf. |
| --- | --- | --- | --- | --- | --- |
| `0x09c18d70` | `duel_core_discard_hand_card` | `void (int side, int index, int by_opponent)` | `duel_core_send_hand_card(side, entry, by_opponent, 0x0e, discard=1, reason=0)`. | 21 | H |
| `0x09c18dc8` | `duel_core_discard_hand_card_reason2` | `void (int side, int index)` | Discard with reason 2 (hand-limit path, flag `0x80`). | 1 | M |
| `0x09c18e14` | `duel_core_discard_hand_card_as_cost` | `void (int side, int index)` | Discard with reason 1 (cost); callers are slot `+10` handlers. | 9 | H |
| `0x09c18f6c` | `duel_core_send_hand_card_to_graveyard` | `int (int side, void *entry, int by_opponent)` | Not a discard (`discard=0`); returns 1 when the card really went to the Graveyard (not banished by Macro Cosmos-type rules). | 29 | H |
| `0x09c18f98` | `duel_core_send_hand_card_to_graveyard_as_cost` | `void (int side, int index)` | Same, reason 1. | 12 | H |
| `0x09c18f5c` | `duel_core_banish_hand_card` | `void (int side, void *entry, int by_opponent)` | Destination `0x0f`. | 8 | H |
| `0x09befac0` | `duel_core_find_in_hand` | `int (int side, int ref)` | Hand index of the card reference, or −1. | 48 | H |
| `0x09c0bb98` | `duel_core_can_discard_card` | `int (int side, int card_id, int as_cost)` | Rejects Vicious Claw while its effect applies; for costs also checks `0x09bfd3fc`, Chain Energy's LP condition and Cold Wave. | 9 | M |
| `0x09c56488` | `duel_core_hand_has_discardable_cards` | `int (int side, int count, int except_ref, int kind)` | At least `count` discardable cards other than `except_ref`; kind 0 any, 7 spell, 8 trap, other monster. | 9 | H |
| `0x09c56670` | `duel_core_hand_has_cards_to_send` | `int (int side, int count, int except_ref, int monsters, int spells)` | Same for "send from hand to the Graveyard" costs. | 9 | H |
| `0x09c569c0` | `duel_effects_can_pay_discard_cost` | `int (void *ctx)` | Slot `+0c` handler for discard costs: `duel_effects_get_discard_count(ctx)` discardable cards other than the activating card (always true when the link event is `0x24` or the card copies 0x1935). | 21 / 26 records | H |
| `0x09c56844` | `duel_effects_count_other_hand_cards` | `int (void *ctx, int side)` | Hand size minus 1 when the effect's card is in that hand. | 22 | H |
| `0x09c2b6b8` | `duel_core_post_reveal_hand_card` | `void (int side, int ref)` | Command `0x52`: UI event `0x13` on that hand card and player flag bit 2 (card known to the opponent). Posted after a card is added to the hand from the Deck or Graveyard. | 29 | M |
| `0x09c2b704` | `duel_core_post_set_hand_reveal` | `int (int side, int state)` | Command `0x53` when the hand-reveal state changes (state 0 = current from `0x09c03968`); used to show a whole hand. | 12 | M |

## 4. Deck primitives

| Address | Name | Signature | Behaviour | Command / event | Callers | Conf. |
| --- | --- | --- | --- | --- | --- | --- |
| `0x09c2b838` | `duel_core_post_shuffle_deck` | `void (int side)` | Posts the shuffle with the current seed `0x09e2d1cc`. | `0x55` | 86 (279 cards) | H |
| `0x09dbbbac` | (handler of `0x55`) | | Clears player flag bit 3, stores the seed, shuffles with `duel_core_shuffle_deck_list`, UI events `0x15`/`0x16`; nothing for fewer than 2 cards. | | | H |
| `0x09bf104c` | `duel_core_shuffle_deck_list` | `void (int side)` | Fisher–Yates over the Deck list with `duel_core_random`. | | 2 | H |
| `0x09c2b868` | `duel_core_shuffle_searched_decks` | `void (void)` | Posts `0x55` for each side whose player flag bit 3 is set (turn player first). Bit 3 therefore means "Deck must be shuffled". | `0x55` | 23 | H (code), M (bit meaning) |
| `0x09bef8b0` | `duel_core_find_in_deck` | `int (int side, int ref)` | Deck index or −1. | | 5 | H |
| `0x09c19b34` | `duel_core_post_reveal_card` | `void (int side, int location, int ref)` | Shows one card (UI `0x18`/`0x19`); a Graveyard/banished card is moved to the top of its pile first. | `0x28` | 7 | M |
| `0x09c19b58` | `duel_core_post_reveal_deck_top` | `void (int side)` | `0x28` with location `0x0d` and the top card. | `0x28` | 17 | M |
| `0x09c2b778` | `duel_core_post_flip_deck_top` | `void (int side)` | UI event `0x17` for the Deck (pairs with the previous one around "send the top card" effects and Null and Void in `duel_core_draw_cards_ex`). | `0x59` | 17 | L |
| `0x09c0d7c0` | `duel_core_can_add_from_deck_to_hand` | `int (int side)` | False while Thunder King Rai-Oh (`0x1ce5`) or Deck Lockdown (`0x1dd1`) is active. | | 27 | H |
| `0x09c197c0` | `duel_core_add_deck_card_to_hand` | `int (int side, void *entry)` | Finds the card in the Deck, moves it to the hand (`0x3e` from `ref<<6 | 0x0d<<1 | side` to `count<<6 | 0x0b<<1 | side`), reveals it (`0x52`), queues Watapon's trigger, Puppet King's for the opponent when it is a monster, raises timing event `0x1b`; when adding is forbidden it sends the card to the Graveyard instead and returns 0. | `0x3e`, `0x52`; event `0x1b` | 17 (78 cards) | H |
| `0x09c2a69c` | `duel_core_send_deck_ref_to_graveyard_ex` | `void (int side, int banish, int ref, int by_opponent, int card_id)` | Deck (or Extra Deck for Fusion/Synchro) card to the Graveyard, or banished when `banish`, when the Graveyard is locked (`0x09c0d160`), or for card `0x1cf9`; Imperial Iron Wall turns banishment back into the Graveyard. | `0x3e` / `0x32`; event `0x1d` | 8 | H |
| `0x09c2af20` | `duel_core_send_deck_ref_to_graveyard` | `void (int side, int ref, int card_id, int by_opponent)` | Wrapper, `banish = 0`. | | 17 | H |
| `0x09c2af34` | `duel_core_send_deck_ref_to_graveyard_as_cost` | `void (int side, int ref)` | Wrapper without card. | | 5 | M |
| `0x09c2af48` | `duel_core_banish_deck_ref` | `void (int side, int ref, int card_id, int by_opponent)` | Wrapper, `banish = 1`. | | 6 | H |
| `0x09c2ac4c` | `duel_effects_mill_deck` | `void (void *ctx, int side, int count)` | Top `count` cards (capped by the Deck) to the Graveyard in one timing batch; `by_opponent` = side ≠ controller. | | 25 (42 cards) | H |
| `0x09c2ab68` | `duel_core_mill_deck` | `void (int side, int count, int card_id, int by_opponent)` | Same without a context. | | 2 | H |
| `0x09c2ad3c` | `duel_core_mill_deck_as_cost` | `void (int side, int count)` | Same without card; slot `+10` callers. | | 6 (56 cards) | H |
| `0x09c2ae0c` | `duel_core_banish_deck_top` | `void (int side, int count, int card_id, int by_opponent)` | Top `count` cards banished. | | 5 | H |
| `0x09c2a958` | `duel_core_send_named_cards_from_deck` | `void (int side, int name, int banish, int all, int card_id, int by_opponent)` | Every (or the first) card with that name in the Deck and Extra Deck. | | 2 | M |
| `0x09c0d218` | `duel_core_can_mill_deck` | `int (int side, int count)` | Deck ≥ `count` and no Graveyard lock (`0x09c0cf8c` flags). | | 12 | H |

## 5. Graveyard and banished zone

| Address | Name | Signature | Behaviour | Command / event | Callers | Conf. |
| --- | --- | --- | --- | --- | --- | --- |
| `0x09c190ec` | `duel_core_add_list_card_to_hand` | `int (void *ctx, int side, int location, int ref)` | Graveyard/banished card to the hand (Fusion/Synchro to the Extra Deck); Graverobber takes it into its controller's hand; from the Graveyard, Transmigration Break banishes it instead. Reveals it, raises event `0x1b` (`0x25` for the Extra Deck). | `0x3e`, `0x52` | 2 | H |
| `0x09c19384` | `duel_core_add_graveyard_card_to_hand` | `int (void *ctx, int side, void *entry)` | Wrapper, location `0x0e`. | | 16 (73 cards) | H |
| `0x09c19400` | `duel_core_add_banished_card_to_hand` | `int (void *ctx, int side, void *entry)` | Wrapper, location `0x0f`. | | 4 (55 cards) | H |
| `0x09c18434` | `duel_core_return_graveyard_card_to_deck_ex` | `int (int owner, int side, int ref, int top)` | Graveyard card to the Deck (Extra Deck for Fusion/Synchro), top when `top` ≠ 0 else bottom; Transmigration Break banishes instead. | `0x3e`; event `0x25` | 2 | H |
| `0x09c18428` | `duel_effects_return_graveyard_card_to_deck` | `int (void *ctx, int side, int ref, int top)` | Wrapper with the context's owner. | | 12 (47 cards) | H |
| `0x09c19488` | `duel_core_banish_graveyard_card_ex` | `int (int side, void *entry, int by_opponent, int flag)` | Graveyard → banished unless Imperial Iron Wall; queues triggers of `0x1cf6`/`0x17bb`. | `0x32`; event `0x1f` | 4 | H |
| `0x09c1947c` | `duel_core_banish_graveyard_card` | `int (int side, void *entry, int by_opponent)` | Wrapper. | | 36 (85 cards) | H |
| `0x09c196c8` | `duel_core_return_banished_card_to_graveyard` | `void (int side, int ref)` | Banished → Graveyard (also used by the summon steps when no zone is free). | `0x3e`; event `0x25` | 9 | H |
| `0x09c0d5e8` | `duel_core_can_banish` | `int (void)` | No Imperial Iron Wall (`0x1eb2`) active. | | 47 | H |
| `0x09c0d60c` | `duel_core_can_banish_from_graveyard` | `int (int side, int owner)` | No Imperial Iron Wall, no Kycoo the Ghost Destroyer on the other side, and Necrovalley only with Gravekeeper's Chief on `owner`'s side. | | 64 | H |
| `0x09c0d4cc` | `duel_core_graveyard_card_may_leave` | `int (int owner, int side, int *banisher)` | 0 when Transmigration Break (`0x1d36`) forces banishment (and who controls it), else 1. | | 2 | H |
| `0x09c01404` | `duel_core_find_entry_in_graveyard` | `int (int side, void *entry)` | 1-based Graveyard position of an entry, 0 if absent. | | 1 | H |
| `0x09c0d0d8` | `duel_core_can_send_to_graveyard` | `int (int side, int is_monster)` | Graveyard-lock flags from `0x09c0cf8c` (both sides, monsters only, per side). | | 20 | M |
| `0x09c0d088` | `duel_core_can_send_ref_to_graveyard` | `int (int ref)` | The previous for a card reference. | | 31 | M |

## 6. Special Summon by effect and tokens

`duel_core_special_summon(side, entry, face_up, position, flags)` and `duel_core_special_summon_impl` are in `summon.md`. Position values in these callers: 0 Attack, 1 Defense, 2 the player chooses.

| Address | Name | Signature | Behaviour | Callers | Conf. |
| --- | --- | --- | --- | --- | --- |
| `0x09c74640` | `duel_effects_revive_target_ex` | `int (void *ctx, int position)` | Special Summons the link's first target (Graveyard or banished) for the controller after: free zone, Special Summon allowed, target still valid, and either `duel_core_can_special_summon_list_card` or, for Level Modulation, Lord of Dark Summons and Ultimate Ancient Gear Golem, "ignore conditions" checks. | 5 (71 cards) | H |
| `0x09c74638` | `duel_effects_revive_target` | `int (void *ctx)` | Same with position 2. | 8 | H |
| `0x09c0c4b0` | `duel_core_can_special_summon_id` | `int (int side, int card_id)` | `duel_core_is_summon_kind_allowed(side, 8, id)`. | 23 | H |
| `0x09c027ec` | `duel_core_can_special_summon_list_card` | `int (int side, int owner, void *entry, int location, int flag)` | Summon locks, nomi/semi-nomi rules, per-card exceptions. | 14 | M |
| `0x09c02ad8` | `duel_core_can_special_summon_from_graveyard` | `int (int side, int owner, int index)` | Previous for Graveyard index. | 35 | H |
| `0x09c02b10` | `duel_core_can_special_summon_from_banished` | `int (int side, int owner, int index)` | Previous for banished index. | 5 | H |
| `0x09c0cb28` | `duel_core_can_special_summon_card` | `int (int side, int card_id, int where)` | `0x09c0c58c` and `0x09c0c8a0` (summon conditions). | 28 | M |
| `0x09c5683c` | `duel_effects_count_free_monster_zones` | `int (void *ctx, int side)` | Thunk to `duel_core_count_free_monster_zones(side)`. | 26 | H |
| `0x09befee0` | `duel_effects_find_token_entry` | `void *(int card_id)` | Linear search of the **token table** `0x09e019ec` (46 entries of 8 bytes: `u16` card id, `u16` token card id, `u16` count (0 = computed by the handler), `u16` position 0 Attack / 1 Defense / 2 either). Scapegoat: 4 Defense; Ojama Trio: 3 Defense, on the opponent's side; Insect Queen: 1 Attack. | 3 | H |

## 7. Generic resolve handlers (slot `+04`)

These are the effect families; the cards differ only in parameters (builder filter, compare chains on the card id).

| Address | Name | Records | Example cards | Behaviour (resolution sub-states `0x80` → …) | Conf. |
| --- | --- | --- | --- | --- | --- |
| `0x09c7b510` | `duel_effects_resolve_search_deck` | 41 | Sangan, E - Emergency Call, Reinforcement of the Army, Gather Your Mind, Gadgets | Deck not empty and adding allowed → build list; none: hint `0x15`, show Deck to the opponent, shuffle; else open list (mode 6), `duel_core_add_deck_card_to_hand`, shuffle. Six single-target cards (The White Stone of Legend, Gadgets, Genex Undine, Berfomet) skip the list. | H |
| `0x09c78804` | `duel_effects_resolve_special_summon_from_deck` | 55 | Mystic Tomato, Giant Rat, Apprentice Magician, Magical Labyrinth | Free zone, Special Summon allowed, candidates → list → `duel_core_special_summon_impl` with per-card position/face; none: show Deck, shuffle. | H |
| `0x09c78bac` | `duel_effects_resolve_special_summon_from_hand_or_deck` | 55 | Armed Dragon LV3/LV5, Horus LV4/LV6, A Deal with Dark Ruler, Hero Signal | Same from the candidate list; on failure shows hand and Deck (`duel_core_request_show_hand_and_deck`). | H |
| `0x09c783c8` | `duel_effects_resolve_special_summon_from_hand` | 37 | Ancient Rules, Hero's Bond, The Flute of Summoning Dragon, Don Turtle | Up to N (1, 2 or 5) hand monsters chosen with `duel_core_begin_select_cards`; Type/Attribute hint per card; on failure reveals the hand. | H |
| `0x09ca6cf8` | `duel_effects_resolve_special_summon_self_from_hand` | 13 | Gorz, Cyber Dinosaur, Watapon, Puppet King | The card itself from the hand. | M |
| `0x09c9e99c` | `duel_effects_resolve_special_summon_from_deck_multi` | 6 | Rescue Cat, Cocoon Party, Gladiator Beast Gyzarus | Several picks (`duel_core_get_picked_candidate`); with no free zone the pick goes to the Graveyard. | M |
| `0x09c78f88` | `duel_effects_resolve_revive_target` | 45 | Miracle Restoring, Lord of Dark Summons, Gilasaurus, Chimera | `duel_effects_revive_target_ex(ctx, 2)`. | H |
| `0x09c809f4` | `duel_effects_resolve_monster_reborn` | 1 | Monster Reborn | Unless Call of Darkness (`0x12fb`) is active, `duel_effects_revive_target`. | H |
| `0x09c852c4` | `duel_effects_resolve_revive_bound` | 21 | Call of the Haunted, Premature Burial-type equips, Birthright | Revives the target (Attack for Call of the Haunted and seven others) and binds it to the card: equip (icon 3) via `0x09c15584`, otherwise marker `0x17` on the summoned slot. | M |
| `0x09c78fa8` | `duel_effects_resolve_revive_self` | 29 | Sacred Phoenix of Nephthys, Vampire Lord, Stardust Dragon, Beiige | The card itself from the Graveyard if it is still the same instance there. | H |
| `0x09c9b8f8` | `duel_effects_resolve_special_summon_banished` | 6 | Return from the Different Dimension, Hysteric Party | Candidates from the banished zone/Graveyard, Special Summons each. | M |
| `0x09c974fc` | `duel_effects_resolve_return_self_from_banished` | 4 | D.D. Survivor, D.D. Scout Plane | The banished card returns to the field. | M |
| `0x09c795f0` | `duel_effects_resolve_summon_tokens` | 36 | Scapegoat, Fiend's Sanctuary, Multiply, Ojama Trio, Dandylion | Token table entry; count computed for some cards (free zones, monsters on a side); asks yes/no for optional ones; one `duel_core_special_summon_impl` per token. | H |
| `0x09c7bad8` | `duel_effects_resolve_add_targets_to_hand` | 36 | Magician of Faith, Mask of Darkness, Night Assailant | Each valid target: Graveyard → hand or banished → hand. | H |
| `0x09c957c8` | `duel_effects_resolve_add_self_to_hand` | 17 | Sinister Serpent, Return Zombie, Gladiator Beast's equips | The card itself from the Graveyard/banished zone to the hand. | H |
| `0x09c94d7c` | `duel_effects_resolve_add_from_deck_or_graveyard` | 5 | Elemental Hero Woodsman, Arms Hole | Candidates in the Deck and Graveyard; branches on the selected candidate's location. | H |
| `0x09c81964` | `duel_effects_resolve_add_named_card_from_deck` | 13 | Elemental Hero Captain Gold, King of the Swamp, Fusion Sage | The card named by `0x09c81888` (compare chain) from the Deck. | M |
| `0x09c90d64` | `duel_effects_resolve_place_deck_card_on_top` | 5 | A Cat of Ill Omen, An Owl of Luck | Shows the choice (command 8), shuffles, puts it on top (command `0x58`); with Necrovalley it may be added to the hand after a yes/no. | H |
| `0x09c8a994` | `duel_effects_resolve_send_deck_to_graveyard` | 5 | Foolish Burial, Armageddon Knight, Skreech (2), Hero Mask | Picks 1 or 2 candidates and sends them with `duel_core_send_deck_ref_to_graveyard`. | H |
| `0x09cb4558` | `duel_effects_resolve_lightsworn_mill` | 8 | Lightsworn monsters (3), Judgment Dragon (4), Jain (2) | End Phase mill with `duel_effects_mill_deck` while the card is still on the field. | H |
| `0x09c7f86c` | `duel_effects_resolve_draw_then_discard` | 3 | Graceful Charity, Spiral Spear Strike, Treasure Map | Draws the draw count, then requests the discard of (cards drawn − 1), corrected for Parasite Paracide cards. | H |
| `0x09c7bc3c` | `duel_effects_resolve_random_discard` | 18 | Spirit Reaper, Robbin' Goblin, Kunoichi (own hand), Goe Goe (2) | `duel_core_request_random_discard(opponent, …, 1 or 2)`. | H |
| `0x09c91ad4` | `duel_effects_resolve_reload_hand` | 4 | Reload, Mind Wipe, Disturbance Strategy, Psi-Impulse | Returns the whole hand to the Deck one by one, shuffles, draws the same number (3 for Psi-Impulse). | H |
| `0x09c9a494` | `duel_effects_resolve_return_targets_to_deck` | 8 | Recycle (bottom), Hard-sellin' Zombie (bottom), A Feather of the Phoenix (top) | Each target from the Graveyard to the Deck. | H |
| `0x09c972d4` | `duel_effects_resolve_return_targets_to_deck_shuffle` | 8 | Return Soul, The Transmigration Prophecy, Hidden Book of Spell | Previous, then `duel_core_shuffle_searched_decks` when something was returned. | H |
| `0x09ca2650` | `duel_effects_resolve_pot_of_avarice` | 5 | Pot of Avarice, Gladiator's Return, Fifth Hope | Returns the targets to the Deck, shuffles, then `duel_effects_resolve_draw`. | M |
| `0x09c80a38` | `duel_effects_resolve_banish_graveyard_targets` | 10 | D.D. Crow, Soul Release, Kycoo, Gravedigger Ghoul | Banishes the valid Graveyard targets if banishing from the Graveyard is allowed. | H |

Already named and still central: `duel_effects_resolve_draw` (`0x09c78270`, 73 records), `duel_effects_cost_discard` (`0x09c42afc`), `duel_effects_get_discard_count` (`0x09c41c38`), `duel_effects_resolve_fusion_summon`, `duel_core_draw_cards`, `duel_core_special_summon`.

## 8. Shared context and UI helpers

| Address | Name | Signature | Behaviour | Callers | Conf. |
| --- | --- | --- | --- | --- | --- |
| `0x09cbf1ac` | `duel_effects_get_link_target_ref` | `int (void *ctx, int i)` | Card reference of target `i`: `u16 ctx+8+2i` for i < 5, else the ring `0x09e28e50` from `u16 ctx+0x12` (128 entries); card `0x1935` rotates the order. | 63 | H |
| `0x09befb44` | `duel_core_get_entry_by_ref` | `void *(int ref)` | `duel_core_find_card_location` + `duel_core_get_location_entry`; 0 if nowhere. | 40 | H |
| `0x09bef810` | `duel_core_find_field_slot_by_ref` | `int (int ref)` | `side | slot << 8` of the card on the field, or −1. | 61 | H |
| `0x09dc6f98` | `duel_core_show_hint` | `void (int side, int message)` | UI event `0x36` with a message id when `side` is a human duelist (`0x09e02998[side] == 0`). | 222 | H |
| `0x09dc72b0` | `duel_core_ask_yes_no` | `void (void *ctx, int message)` | Asks the controller; the CPU answers through `ai_ask_yes_no`; the answer is read later from `0x09e2d248`. | 31 | M |

## Commands and timing events used by these helpers

| Code | Use here | Conf. |
| --- | --- | --- |
| Command `0x28` | Reveal one card (location, reference) | M |
| Command `0x3e` | Move between card lists (`duel_core.md`) | H |
| Command `0x52` | A card in the hand becomes known (player flag bit 2) | M |
| Command `0x53` | Hand reveal state | M |
| Command `0x54` | Random-pick animation over the hand (UI event 8, up to 32 frames) | M |
| Command `0x55` | Shuffle the Deck with a seed | H |
| Command `0x58` | Move a Deck card to the top | M |
| Command `0x59` | UI event `0x17` on the Deck | L |
| Event `0x1b` | Card added to the hand from the Deck, Graveyard or banished zone | H |
| Event `0x1d` | Card sent from the Deck to the Graveyard (or banished) | H |
| Event `0x1f` | Card banished from the Graveyard | H |
| Event `0x25` | Card returned to the Deck / Extra Deck or to the Graveyard from banishment | M |

## Open questions

- Filter bit `0x10000` (`0x09c02b48`) and options `0x8`/`0x10`/`0x20` of the scanners; the meaning of the hand-scanner index argument for builders called outside `duel_effects_count_hand_candidates`.
- `duel_effects_get_candidate_param`: the remaining context fields it reads (`ctx+8`, `+0xa`, `+0xc`, `+0x14`).
- Request modes 7 and `0x0e`: the per-card filters inside `0x09c111a8` and `0x09c12b98`.
- Who sets player flag bit 3 ("Deck must be shuffled"): presumably viewing or searching the Deck; confirm in PPSSPP.
- `duel_core_add_deck_card_to_hand` sends the card to the Graveyard when adding is forbidden; check whether any caller reaches that branch in play.
- Commands `0x28`, `0x52`, `0x53`, `0x58`, `0x59`: argument packing beyond what is used here, and UI events `0x13`, `0x17`.
- The 8-byte list `0x09dec554` is now known to hold candidate builders; the other two unexplained lists (`0x09dfe500`, `0x09e010b0`) remain as in `effect-tables.md`.
