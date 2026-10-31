# The chain: building, responses and resolution (work package 4)

How `gmodule/rel_duel_eng.prx` (runtime base `0x09be1400`) collects effects into a chain, lets the players respond, and resolves the chain. Effect handler tables are in `docs/formats/effect-tables.md`, the timing-event queue in `battle.md`, the player and field-slot structures in `duel_core.md`.

Evidence is static (Ghidra decompilation of the functions named below, their callers from the call graph, and the effect-table records of known cards); nothing here has been traced in PPSSPP yet. Confidence: H high, M medium, L low.

## Summary

- **Three engines.** A trigger queue collects effects that want to activate (`0x09e289b4`, up to 32). A *building* state machine (`duel_core_chain_build_step`, `0x09c2e244`) activates links one by one (announce, activation step, target choice), then offers response windows. A *resolution* state machine (`duel_core_chain_step`, `0x09c2f1fc`) resolves the links last-in first-out and cleans up. Both are driven once per frame from the pending-work function `duel_core_chain_pending_work` (`0x09c32dac`). (H)
- **Maximum chain length 16.** The chain array at `0x09e28cb4` has room for exactly 16 links (the count at `0x09e28e34` follows it), and responses are only offered while the chain has fewer than 16 links (state `0x0b`), and at most 16 queued triggers are moved onto a chain. (H. The response limit was verified in PPSSPP: with 16 links no window opened for either side although a usable D.D. Crow was in hand, the chain resolved top first, and nothing was written past the 16 links; `docs/verification/results/2026-10-27-sessionD.md`. The trigger limit is not tested yet.)
- **Spell speed** (`duel_effects_get_spell_speed`, `0x09bf275c`): normal spells and monster effects 1, quick-play spells, normal and continuous traps and listed quick-effect monsters 2, counter traps 3. A response needs a speed at least equal to the link it responds to and at least 2 (`duel_effects_can_respond_in_window`, `0x09c52c60`), so only counter traps can respond to a counter trap. (H)
- **Handler slot `+10` is the activation step**, run once while a link is being activated, before target choice: it pays costs (Life Points, discards, Tributes), marks once-per-turn use, or, for optional trigger effects, asks the player "activate?". The earlier "optional check" hypothesis is refuted as a full description and survives only as one use of the slot. (H)
- **Negation** marks the negated link in its byte `+4`: bit 1 "activation negated", bits 2–3 "effect state" (1 = negated). A negated link stays on the chain; at resolution its handler is skipped and the card goes to the Graveyard. Counter traps negate the link immediately below them. (H)
- **Simultaneous triggers** are sorted before they form a chain: turn player's mandatory, opponent's mandatory, turn player's optional, opponent's optional (link 1 first), the SEGOC order of the official rules, without a player choice inside a group. (H for the key, M for the reading.)
- **Once per turn** is a marker on the card's field slot: card id `0xfb6` (a pseudo-key, Time Wizard's id), kind 2, placed by the activation step and checked by 63 activation conditions; the End-Phase cleanup frees kind-2 markers. (M)

## Data

### Globals

| Address | Meaning | Conf. |
| --- | --- | --- |
| `0x09e289b4 + i × 0x18` | Trigger queue (pending activations), up to 32 links | H |
| `0x09e28e48` | Number of queued triggers | H |
| `0x09e28cb4 + i × 0x18` | Chain, link `i + 1` (`= 0x09e289b4 + 0x300`); room for 16 links only, since the count follows at `0x09e28e34 = 0x09e28cb4 + 16 × 0x18` (an earlier reading said 32 slots; address arithmetic, H) | H |
| `0x09e28e34` | Number of links on the chain (counts down while resolving) | H |
| `0x09e28e38` | Building: index of the link being activated; resolving: index of the link being resolved (top), then the sweep index | H |
| `0x09e28e3c` | Building: first link not yet checked for automatic responses | M |
| `0x09e28e40` | Chain length when resolution started (used by the post-chain sweep); read 16 after a 16-link chain and 1 after a single link in PPSSPP | H |
| `0x09e28e44` | Pointer to the link currently being processed (read by handlers and the UI) | M |
| `0x09e28e50` | Ring of 128 `u16` extra target entries (links with more than five targets) | M |
| `0x09e28f50` | 1 while a chain is being built | H |
| `0x09e28f54` | State of the building machine | H |
| `0x09e28f58` | 1 while a chain is being resolved | H |
| `0x09e28f5c` | State of the resolution machine | H |
| `0x09e28f60` | Resolution sub-state passed to multi-frame resolve handlers (starts at `0x80`; 0 = finished) | H |
| `0x09e28f64`, `0x09e28f68` | Target index and per-target sub-step during target re-validation (resolution state 4) | M |
| `0x09e28f6c`, `0x09e28f70` | Sub-state of activation-step and target-choice handlers (reset before each call) | H |
| `0x09e28988`, `0x09e28990` | "Target choice done" and "activation step done" latches of the current link | H |
| `0x09e28f9c` | 1 while a chain is in progress; `duel_core_raise_timing_event` queues nothing while it is set (`battle.md`) | H |
| `0x09e29040`, `0x09e2904c` | Response-window state; `0x09e2904c` is set when a player activated something in the window | H |
| `0x09e29048` | Timing window pending (set again after a chain if timing events were raised) | H |
| `0x09e290b7` | State of the summon-response window (`duel_core_chain_summon_window_step`) | H |
| `0x09e2bba0` bit 3 | A link is resolving (set by command `0x11`, cleared by `0x12`) | H |
| `0x09e2d23c` | Loop guard for forced triggers (stops after 10) | M |

### Chain link (24 bytes)

A link is also the `ctx` that effect handlers receive; handlers that respond to another link receive the link below as their second argument (`NULL` for link 1).

| Offset | Bits | Meaning | Conf. |
| --- | --- | --- | --- |
| `+0x00` | `u16` | Card id | H |
| `+0x02` | bit 0 | Side of the card | H |
| | bits 1–5 | Location: 0–10 field slot, `0x0b` hand, `0x0e` Graveyard | H |
| | bits 6–11 | Event code: the timing code that triggered the effect (`battle.md`); `0x24` and `0x23` are special (cost-free activations / not respondable) | H (field), M (codes) |
| `+0x03` | bits 4–5 | Handler-table selector: 0 S/T (activation of a spell/trap card), 1 M1 (field monster effect), 2 M2 (hand/Graveyard/destruction triggers), 3 M3 (ignition effect) | H |
| | bit 6 | Control switched: controller = side ^ bit 6 | H |
| | bit 7 | Activation step (`+10`) completed | H |
| `+0x04` | bit 0 | Target choice (`+14`) completed | H |
| | bit 1 | Activation negated | H |
| | bits 2–3 | Effect state: 0 normal, 1 negated, 2 disabled when activated (`duel_effects_is_disabled_at_activation`) | H (1), M (2) |
| | bit 4 | The card is sent to the Graveyard after the chain even if it would stay (set with bit 1 by activation negation) | M |
| | bits 5–13 | Instance number of the card (`duel_core.md`, card references) | H |
| `+0x05` | bits 6–7 | The card's 2-bit incarnation counter at activation (from `0x09e2bbcc` byte `+2`); a later mismatch means the card left and came back | H |
| `+0x06` | bit 0 | Copied effect: the effective card id is at `+0x18` (`duel_core_get_effective_card_id`) | M |
| | bits 1–7 | Number of targets | H |
| `+0x07` | bits 1–7 | Number of values recorded by the activation step (e.g. the ATK of a Tributed monster) | M |
| `+0x08` | 5 × `u16` | Targets, or values written by the activation step. Target entry: bit 0 side, bits 1–4 slot, bits 5–13 instance, bits 14–15 incarnation counter | H |
| `+0x12` | `u16` | Start index in the extra-target ring `0x09e28e50` (targets 6 and up) | M |
| `+0x14` | `u32` | Argument of the timing event that triggered the effect (`0x09e28fc0[]`) | H |

`+0x0c` and `+0x16` are read by some per-card rules (`effect-tables.md`, computed draw counts) and are written by individual activation steps; they have no fixed meaning.

The packed form used by the queueing functions is `card | location << 16 | selector << 21 | switched << 24 | event << 25 | side << 31`, with the instance passed separately.

### Effect markers

**Verified in PPSSPP (2026-10-26, [`results/2026-10-26-sessionA-part1.md`](../verification/results/2026-10-26-sessionA-part1.md), A7 and A8):** link layout of `+0x00`/`+0x02`/`+0x03`, the link count at `0x09e28e34`, LIFO resolution, and the once-per-turn marker `0xfb6` (kind 2, counter 0) attached by command `0x35` and freed at the turn change. Many rules leave a marker on a field slot: a linked list of 10-byte nodes in the pool `0x09e2c7cc` (256 nodes), whose head is the slot's `u16 +0x0a` (`0x09e2a566 + side × 0xb3c + slot × 0x14`; slot 11 is the player). Node: `u16 +0` card id (or a pseudo-key), byte `+2` low nibble kind, high nibble a turn counter, `u16 +4` value (often an instance number), `u16 +8` next. Kinds 0–5 are effect markers; kinds ≥ 6 are used for other links between slots (not studied). (H for the layout.)

Markers are added and removed only through commands `0x35` (`duel_core_post_add_marker(side, slot, card, kind, value)`, `0x09c150bc`) and `0x36` (`duel_core_post_remove_marker`, `0x09c15320`), so that a link-duel peer replays them. `duel_core_expire_turn_effects` (`0x09be6864`, run by the end-of-turn command) frees every kind-1 or kind-2 marker whose counter is 0 and decrements the others; kind 7 has per-card rules. Markers on a slot disappear with the card (`duel_core_zone_remove`). (H)

## Collecting triggers

When something happens, the code that raised the event queues the effects that react to it. Every queueing function builds a temporary link, checks it with `duel_effects_can_activate` and calls `duel_core_chain_add_link(0, …)`:

| Function | Queues |
| --- | --- |
| `duel_core_chain_queue_trigger(packed, instance, arg)` `0x09c2c578` | One prepared link (51 callers) |
| `duel_core_chain_queue_field_trigger(side, slot, event, arg)` `0x09c2c754` | The card in a field slot, selector 1 (43 callers) |
| `duel_core_chain_queue_field_triggers_by_id(side, card, event, arg)` `0x09c2cd0c` | Every copy of a card on the field |
| `duel_core_chain_queue_graveyard_triggers(side, card, event, arg)` `0x09c2d1ec` | Every copy in the Graveyard, location `0x0e`, selector 2 |
| `duel_core_chain_queue_hand_triggers(side, card, event, arg)` `0x09c2d4a4` | Every copy in the hand, location `0x0b`, selector 2 |

`duel_core_chain_add_link(to_chain, packed, instance, arg)` (`0x09c2c19c`): with `to_chain = 0` it appends to the trigger queue (refusing more than 32) unless the same card instance with the same selector is already queued, in which case only some cards (those of `BOOT 0x08866788` and a short list) update the queued event code and argument; with `to_chain ≠ 0` it pushes directly onto the chain. It records the incarnation counter. In a link duel the remote side forwards the request instead (`0x09dcc884(0x12, …)`). (H)

`duel_effects_can_activate(link, prev)` (`0x09c539b0`) is the common activation test: no lock is active (`duel_effects_is_activation_locked`, `0x09c52f60`: Spell Canceller and Talisman of Spell Sealing for spells; Jinzo, Jinzo – Lord and Talisman of Trap Sealing for traps; Cold Wave, Sasuke Samurai #2, Angel O7, Triangle Ecstasy Spark and others); the spell speed is at least that of `prev`; the controller has more Life Points than the cost (`duel_effects_get_lp_cost`; for a hand card, 500 per Chain Energy); for summon events `0x20`–`0x22` the card is not of genre 3; finally the slot `+0c` condition (`duel_effects_call_handler_0c_b`). A spell or trap activated from the hand is tested by placing it temporarily in a free spell/trap zone and restoring the zone afterwards. A trigger whose kind is 2 (below) passes without the condition. (H)

## Forming a chain from triggers (SEGOC)

`duel_core_chain_pending_work()` (`0x09c32dac`, called by `duel_core_run_turn_flow`):

1. building (`0x09e28f50`) → `duel_core_chain_build_step`;
2. resolving (`0x09e28f58`) → `duel_core_chain_step`;
3. a global rule wants to act (`duel_effects_check_rule_list`) → wait;
4. triggers queued → `duel_core_chain_build_from_triggers`;
5. a timing window is pending → `duel_core_run_timing_windows` (`battle.md`); a player who activates a card there calls `duel_core_chain_activate`.

`duel_core_chain_build_from_triggers()` (`0x09c329e8`) gives each queued link the key `(controller ≠ turn player) + 2 × (duel_effects_get_trigger_kind(link) > 0)`, sorts the queue by ascending key (an exchange sort, so links with equal keys may be reordered), copies at most 16 links onto the chain (link 1 = lowest key) and keeps the rest queued, then starts building. The result: turn player's mandatory triggers first, then the opponent's mandatory ones, then the turn player's optional ones, then the opponent's. (H)

`duel_effects_get_trigger_kind(link)` (`0x09ce401c`) returns 0 for selector 0 and 3 and for records without a slot `+10` handler; 2 when slot `+10` is the yes/no handler's thunk (`0x09c43328`); 1 for the other yes/no handlers (`duel_effects_confirm_optional_trigger` `0x09c431ac`, `duel_effects_confirm_recruiter_trigger` `0x09c45f84` and nine others) and for per-card cases keyed on the event code. 1 and 2 are optional ("you can") triggers; 0 is mandatory or not a trigger. (H)

During a summon, `duel_core_chain_summon_window_step` (`0x09c32e54`, called from `duel_core_summon_raise_trigger`) runs the same machines but takes from the queue only the first card of `duel_effects_is_summon_negation_card` (`0x09bf2f30`: Solemn Judgment, Horn of Heaven, Black Horn of Heaven, Forced Back, The Selection, Royal Oppression, Pollinosis, Mind Over Matter, Thunder King Rai-Oh and two unnamed ids), through `duel_core_chain_build_summon_response` (`0x09c32c5c`). The same list is the only one allowed to start a chain on summon events `0x20`–`0x22` (`duel_effects_can_respond_in_window`). (H)

## Building: `duel_core_chain_build_step` (`0x09c2e244`)

`duel_core_chain_activate(packed, instance, mode)` (`0x09c2c9cc`; called by the player-input handlers `0x09dcd49c`, `0x09dcd5d0`, `0x09dcd710`) starts building when the chain is empty (`mode = 0`), or pushes a response link onto the chain (`mode ≠ 0`). It tries the queued timing events in order and gives the link the first event code for which the slot `+0c` condition holds. The AI builds its link at the chain top itself (`ai.md`).

States (`0x09e28f54`); "link" is the chain entry `0x09e28e38`:

| State | Action |
| --- | --- |
| 0 | Wait for `duel_core_check_duel_end` and the forced position changes of `0x09cdd74c` (seven cards listed at `0x09dedadc`); set "chain in progress", reset the indices, sync the timing queue to a link-duel peer. |
| 1 | Announce the activation (`duel_core_chain_announce_activation`, command `0x2d`) unless the card is in the `BOOT 0x08866788` list. A spell or trap activation (selector 0) leaves markers on cards that react to activations: Royal Magical Library-type counters (`0x161a`, kind 2, value = instance), Spell Absorption, Curse of Darkness, Chain Burst, the Counter Trap reactors (Bountiful Artemis, Layard, Meltiel, Synthetic Seraphim), Dark Horus, Nitro Warrior and others. If `duel_effects_is_disabled_at_activation(link)` holds, effect state 2. |
| 2–3 | Activation step: if the record has a slot `+10` handler, call it (through `duel_effects_call_activation_step`, `0x09ce3da0`) every frame until it returns non-zero: > 0 sets `+3` bit 7, < 0 cancels. Without a handler the step counts as done. |
| 4–5 | Target choice: the same with slot `+14` (`duel_effects_call_handler_14`) and `+4` bit 0. |
| 6 | Both bits set: command `0x10` (link `n` activated; the UI shows it), next link; when the second link is activated, Blast Asmodian-type markers (`0x1ae0`) are refreshed. Otherwise the link is cancelled: removed from the chain, the links above move down, and the card's slot is restored with command `0x38` if its slot flag bit 1 is set. When the chain becomes empty building ends. More links to activate → state 1, else state 7. |
| 7 | Wait for the global rules (`duel_effects_check_rule_list`) and the duel-end check. |
| `0x0b` | If the chain has fewer than 16 links, the top link accepts responses (`duel_core_chain_link_accepts_responses`, `0x09c2d7e8`: not event `0x23`, per-card exceptions) and its speed is below 3, look for automatic responses (`duel_core_chain_collect_auto_responses`, `0x09c2ddbc`: field cards such as Light and Darkness Dragon and Royal Command that respond by themselves; they are pushed straight onto the chain) → state 1 if any. |
| `0x0c` | Offer a response window to the opponent of the top link's controller (`duel_core_offer_response_window(top, side)`). Someone activated → state 1. |
| `0x0d`–`0x0e` | The same for the top link's controller. |
| other | Nobody responded: stop building, clear the timing queue, record the chain length (`0x09e28e40`), start resolving (state 0). |

The window order follows the rules: after an activation the opponent may respond first. Each response re-enters state 1 for the new link, so costs and targets of a response are handled before the next window.

### The response window: `duel_core_offer_response_window(link, side)` (`0x09ccbe74`)

`int duel_core_offer_response_window(void *link, int side)` asks one side whether it responds to `link` (the top chain link), or, with `link = 0`, whether it activates something in an open timing window. It is a state machine on `0x09e29040` and is called every frame until it returns non-zero. Callers: `duel_core_chain_build_step` (states `0x0c`–`0x0e`, twice), `duel_core_run_timing_windows` (`0x09ccc494`, twice) and `0x09ccc634`. Confidence H for the paths below (decompiled), M for the meaning of the prompt-state numbers.

- **State 0/1/5 (start).** For an open window (`link = 0`) during event codes `0x20`–`0x22` (`0x09e28fa0`), a side that cannot respond (`duel_core_can_respond(side, 0)`) is skipped (returns 1). Then by the duelist kind `0x09e02998[side]`:
  - CPU (1): `ai_chain_response(side, link)` for a link, `0x09d9e108(side, 0)` for an open window; a "yes" moves to state `0x0b`, a "no" returns 1.
  - remote (2): state `0x14`, which sends net command 10 (the trigger list) and waits (states `0x14`, `0x15`).
  - human (0): builds the prompt text ("activate …?" with the card name, or the generic text) from `duel_core_can_respond`/`0x09ccb534`, shows it with `0x09dc74b8(side, text, n)`, state 2; when the player says yes (`0x09e2d248`), state 10 calls `duel_core_begin_player_input(side, link ? 5 : 4)` and state `0x0b` waits for the choice (`0x09e2d26c`: 1 opens a card list, 3 goes on to the activation, otherwise back to state 10; no choice made → back to state 5 and the prompt).
- **State `0x1e` (activation).** For a link it posts command `0x63` with `b` = 1 when `side` is not the link's controller; sets `0x09e2d258 = 1`; then runs the chosen action by its location `0x09e2d27c`: lists `0x0c`–`0x0f` → `duel_core_action_use_card_list`, the hand (`0x0b`) → `duel_core_action_activate_hand_monster` or `duel_core_action_place_spell_trap(1, link)`, a field slot → `duel_core_action_activate_field_card`. Success sets `0x09e2904c = 1`.
- **Return value**: 1 when the window is over for this side (declined, skipped, or the activation was performed), 0 while it is still running. Side effects: `0x09e29040`, `0x09e2904c`, the input state through `begin_player_input`, command `0x63`.

**Verified in PPSSPP (2026-10-27, [`results/2026-10-27-sessionD.md`](../verification/results/2026-10-27-sessionD.md), D1):** after each new link up to the 15th the function was entered for side 1 (CPU, which declined) and then for side 0, whose path called `begin_player_input(0, 5)`; once the chain held 16 links state `0x0b` no longer reached the windows and the chain resolved.

## Resolution: `duel_core_chain_step` (`0x09c2f1fc`)

This answers the open question "the states of `duel_core_chain_step`". The current link is always the top (`0x09e28cb4 + (n − 1) × 0x18`, `n = 0x09e28e34`); `n` is decremented after each link, so resolution is **last in, first out**. (H)

| State (`0x09e28f5c`) | Action |
| --- | --- |
| 0 | Clear the timing queue; command `7` with `0x1e` when the chain has two or more links (UI; L). "After a chain" monsters are prepared: Man Beast of Ares (2+ links), Lightning Punisher and Iris, the Earth Mother (3+ links, only when no card name appears twice). |
| 1 | Command `0x11` (link `n` starts resolving; sets `0x09e2bba0` bit 3). |
| 2–3 | (Link duel: sync.) If the effect is not already negated and `duel_effects_is_negated_on_resolution(link)` holds, effect state 1 and command `0x42` (negation shown); Coral Dragon-type replays (`0x1add`) follow. Targets that moved to another field slot are relocated (`duel_effects_relocate_link_target`). |
| 4 | Unless the link cannot be negated (`duel_effects_cannot_be_negated(link, 0)`), re-check every target: still the same card (`duel_effects_link_target_is_valid`) and still accepted by the slot `+08` filter (`duel_effects_call_handler_08_b`); target-protection cards negate here: Rod of Silence – Kay'est, Frontier Wiseman, Obsidian Dragon, Spirit Reaper-type cards and Darkbishop Archfiend (die roll), among others; each sets effect state 1 and command `0x42`, some also destroy. A link of a card that is no longer in its slot skips straight to state 5. |
| 5 | Set the resolve sub-state `0x80`, raise timing event 0, show the resolution (`0x09dcbccc`). Resolve only if `duel_effects_link_should_resolve(link)` and the record has a resolve handler (`duel_effects_get_resolve_handler`, slot `+04`; Dark Deal `0x1975` has its own); otherwise go to 7. |
| 6 | Call `duel_effects_resolve(link, link below)` every frame; it returns the next sub-state, 0 when finished. |
| 7 | Command `0x12` (link resolved, with the activation-negated bit). If the card is still in its slot, decide whether it goes to the Graveyard (`duel_core_chain_link_sends_card_to_graveyard`) and set slot flag bit 4. Then, unless the activation was negated, the reactions to a resolved activation: spell counters, Spell Absorption (+500), Chain Burst / Curse of Darkness / Rapid-Fire Magician damage, Arcana Force I, Graverobber's 2000 damage, Null and Void, per-card bookkeeping. |
| 100 | If the activation was not negated and the card's slot flag bit 1 is set, command `0x38` (repeat until cleared); duel-end check. |
| `0x65` | Wait for global rules and the duel-end check. More links → `n − 1`, state 1. Else start the sweep. |
| `0x66` | Walk the links from the top down and send every card whose slot has flag bit 4 to the Graveyard (`duel_core_request_send_field_card_to_graveyard`, one per frame). Then queue the post-chain triggers of Van'Dalgyon the Dark Dragon Lord (opponent's links negated by your Counter Traps; attribute mask) and Voltanis the Adjudicator, the "after a chain resolves" monsters (Man Beast of Ares, Lightning Punisher, Iris, Dark Horus), and remove the per-chain markers (`0x1596`, `0x161a`, `0x1518`, `0x1ae0`, `0x1de3`, `0x1d31`, `0x1b61`). |
| `0x67` | Wait for global rules; clear "chain in progress". |
| `0x68` | Resolution finished (`0x09e28f58 = 0`). |

Triggers raised during resolution are queued; when the chain is over, `duel_core_chain_pending_work` forms the next chain from them (previous section). Timing events raised during a chain set the window flag again at the end.

### Which cards go to the Graveyard

`duel_core_chain_link_sends_card_to_graveyard(link)` (`0x09c2dc2c`, also the chain test of target-filter bit `0x80000`) applies to spell/trap activations (selector 0): yes when `+4` bit 4 or bit 1 is set; otherwise no for continuous, equip and field cards (icons 4, 3, 2); for traps that become equip cards (Metalmorph, Kunai with Chain when its option is 1, Zero Sprite, Hero Ring, Brutal Potion…) yes only when negated; no for normal spells that remain on the field (Swords of Revealing Light, Different Dimension Capsule, Nightmare's Steelcage, Big Evolution Pill, Cocoon of Evolution); yes for everything else. (H) `card_db_get_icon` values: 0 normal, 1 counter, 2 field, 3 equip, 4 continuous, 5 quick-play, 6 ritual (H: matches the card texts).

## Spell speed

`duel_effects_get_spell_speed(link)` (`0x09bf275c`) handles a few cards whose speed depends on the selector or option (for example `0x1d0a` and `0x1c03`), then calls `BOOT 0x08865e64(card)`:

| Card | Speed |
| --- | --- |
| Spell (type `0x17`), quick-play (icon 5) | 2 |
| Other spells | 1 |
| Trap (type `0x18`), counter (icon 1) | 3 |
| Other traps | 2 |
| About 60 listed monsters (quick effects: Light and Darkness Dragon, Thunder King Rai-Oh, Dark Balter, Ryu Senshi, Blue-Eyes Shining Dragon…) | 2 |
| Other monsters | 1 |

`duel_effects_can_respond_in_window(link, prev)` (`0x09c52c60`, used when the response window scans field and hand cards): with a link to respond to, the speed must be ≥ that of `prev` and ≥ 2, and a spell/trap slot with flag bit 1 or 3 is excluded. With no chain (an open timing window), speed 1 is allowed only for the turn player in Main Phase 1 or 2 with event codes below 6 (6–8 for monsters on the field) and for four listed cards. Events `0x20`–`0x22` (summons) accept only summon-negation cards when no link is below. (H)

## Activation step (slot `+10`) and costs

The slot is called with `(link, link below)` once per frame until it returns a non-zero value: > 0 continue, < 0 cancel the activation, 0 not finished (the sub-state is in `0x09e28f6c`). 1,044 of the 2,600 records have one (S/T 225, M1 250, M2 166, M3 403 of 428). The most used handlers (record counts) show its purpose:

| Handler | Records | Does | Conf. |
| --- | --- | --- | --- |
| `duel_effects_mark_used_this_turn` `0x09c43148` | 107 | Adds marker `0xfb6` kind 2 to the card's slot | H |
| `duel_effects_confirm_optional_trigger` `0x09c431ac` | 87 | Optional trigger: re-checks the event and condition, asks "activate?" (message `0xfa`, `0x148` hand, `0x149` Graveyard), announces on yes, returns −1 on no | H |
| thunk of the above `0x09c43328` | 75 | Same; trigger kind 2 | H |
| `duel_effects_cost_tribute` `0x09c43d68` | 73 | Choose and Tribute monsters (Horn of Heaven…), recording e.g. ATK or level in `+0x08` | H |
| `duel_effects_cost_pay_lp` `0x09c42ab4` | 58 | Pay `duel_effects_get_lp_cost(link)` (Solemn Judgment, Seven Tools of the Bandit) | H |
| `duel_effects_cost_discard` `0x09c42afc` | 52 | Discard `n` cards (a 104-id chain: Magic Jammer, Divine Wrath → 1) | H |
| `0x09c43180` | 32 | Tribute or send the card itself (`0x09c26878(side, slot)`) | M |
| `0x09c435ac` | 22 | Discard the card itself from the hand | M |
| `duel_effects_confirm_recruiter_trigger` `0x09c45f84` | 20 | Mystic Tomato-type: is a suitable monster in the Deck?, then the yes/no handler | H |

Chaos Sorcerer's handler adds `0x16c9` and `0xfb6` markers; Spell Counter cards remove counters (`0x09c47d8c`). Cost handlers skip the payment when the event code is `0x24` (activation without cost, e.g. through Trap of Darkness `0x1935`). (H)

## Once per turn and once per chain

- **Once per turn** (M): 63 activation conditions call `duel_effects_not_used_this_turn(link)` (`0x09c5698c`: no marker `0xfb6` on the card's slot), and the activation steps of these cards add it (`duel_effects_mark_used_this_turn` and 27 other handlers call `duel_core_post_add_marker(…, 0xfb6, 2, 0)`). The marker belongs to the field slot, so it ends at the End Phase (`duel_core_expire_turn_effects`) or when the card leaves the field. Some cards use their own id as the key instead (Exarion Universe). Not yet confirmed in PPSSPP.
- **Once per chain**: there is no generic counter. Per-chain bookkeeping uses markers that the sweep (state `0x66`) removes: `0x161a` (spell activations seen by Royal Magical Library-type cards), `0x1596` (Spirit Reaper targeted), `0x1518`, `0x1ae0`, `0x1de3`, `0x1d31`, `0x1b61`. The trigger queue also refuses a second entry for the same card instance and selector. (M)

## Negation

### Marking

| Kind | How | Example handlers |
| --- | --- | --- |
| Activation negated | `+4` bit 1, effect state 1, bit 4; command `0x42`; the card is destroyed (on the field: `0x09c252d8` for a spell/trap activation, `0x09c24f9c` otherwise) or discarded from the hand | `duel_effects_negate_link(ctx, link, 1)` `0x09c7772c` through `duel_effects_resolve_negate_activation` `0x09c7799c` (15 callers: Magic Jammer, Seven Tools of the Bandit, Divine Wrath, Counter Counter, Dark Bribe, Solemn Judgment…); `0x09ca5034`, `0x09ca516c`, `0x09cab0c0`, `0x09caaf90`, `0x09cb399c` |
| Effect negated | Effect state 1, command `0x42`; the activation stands | `duel_effects_negate_link(ctx, link, 0)`; `0x09c81240` (White Hole, Anti Raigeki, Call of the Grave, Jar Robber), `0x09c8c8f0` (Dark Balter, Blue-Eyes Shining Dragon, Alkana Knight Joker) |
| Negated at resolution by continuous cards | Effect state 1 in resolution state 2 | `duel_effects_is_negated_on_resolution` `0x09c55d04`: Royal Command (Flip effects), Fiend Skull Dragon, Light-/Shadow-Imprisoning Mirror, Cyber Blader, Necrovalley (Gravekeeper's Chief exempts its controller), Dark Ruler Ha Des, Judgment of Pharaoh, The End of Anubis, per-slot "negated" flag (slot `+0x10` bit 8, recomputed for every field card by `duel_effects_update_negated_slots` `0x09c553e0` from the active Skill Drain, Imperial Order and Jinzo-type cards; `effect-helpers-values.md`), Metal Reflect Slime-type markers |
| Disabled at activation | Effect state 2 in building state 1 | `duel_effects_is_disabled_at_activation` `0x09c2d9a4`: effects of monsters summoned by Junk Synchron, Revival Gift, Mosaic Manticore…, Rainbow Veil / Advanced Dark battle negation, slot flag bit 2 |
| Negated on targeting | Effect state 1 in resolution state 4 | Rod of Silence – Kay'est, Frontier Wiseman, Obsidian Dragon, Darkbishop Archfiend |

`duel_effects_negate_link` refuses when `duel_effects_cannot_be_negated(link, mode)` (`0x09bf73ac`) holds: Spiritualism, Amplifier and Slash Draw (`BOOT 0x088669e4`); spell/trap activations of a player who controls Splendid Venus; and, for effect negation of a monster, a Vehicroid Connection Zone marker. It also refuses for a monster on the field that is unaffected (`duel_effects_is_slot_unaffected`). (H)

The two kinds of negation compare as in the rules: activation negation (Solemn Judgment, Magic Jammer, Seven Tools) sets bit 1, which also stops every "when activated" reaction in resolution state 7 and sends a continuous card to the Graveyard; effect negation leaves the activation, so a continuous spell stays and the reactions still happen. (H)

### Who may negate what

Counter traps check the link below them in their slot `+0c` condition, `duel_effects_cond_respond_to_previous_link(ctx, prev)` (`0x09c59e2c`, 41 records): `prev` must exist, be a field or hand activation (location ≤ 10), be the activation of a spell/trap card (selector 0) and be negatable (`duel_effects_cannot_be_negated(prev, 1)` false). Per card: Seven Tools → `prev` is a trap; Magic Jammer → a spell and a discard is possible; Counter Counter → a counter trap; Dark Bribe → the opponent's card and they can draw; Magic Drain, Divine Wrath and others analogous. A counter trap therefore only reaches the link immediately below it, and a negated link can still be responded to. (H)

Solemn Judgment's resolve handler (`duel_effects_resolve_solemn_judgment`, `0x09c8178c`) negates the link below when there is one, otherwise (summon window) it runs the summon negation of Horn of Heaven (`0x09c817bc`). (H)

### What a negated link does at resolution

`duel_effects_link_should_resolve(link)` (`0x09c54248`) returns 0 when `+4` bit 1 is set or a Flashbang-type global marker (`0x1b61`) is present; when the effect state is non-zero it returns 0 except for equip/field cards activated as cards (selector 0) and about 20 listed cards whose resolve handler must still run (to clean up); it also checks that a continuous/equip/field card is still in its slot. Dark Deal (`0x1975`, copied effect) always resolves. (H)

## Commands posted by the chain

| Command | Handler | Meaning |
| --- | --- | --- |
| `0x10` | `duel_core_cmd_chain_link_activated` `0x09dbca4c` | Link activated: UI event `0x33` (side, location, chain number), log `0x2b`; a Graveyard activation through Trap of Darkness is undone here |
| `0x11` | `duel_core_cmd_chain_link_resolving` `0x09dbcbd8` | UI event `0x34`; sets `0x09e2bba0` bit 3 |
| `0x12` | `duel_core_cmd_chain_link_resolved` `0x09dbcc68` | Clears `0x09e2bba0` bit 3; folds the players' pending summon counts (`+0x20` high half into the low half) |
| `0x2d` | `duel_core_cmd_announce_activation` `0x09dba88c` | Shows the card (UI events `0x18`, `0x14`, `0x47`, `0x22`) |
| `0x35`, `0x36` | `duel_core_cmd_attach_effect` `0x09db7208`, `duel_core_cmd_remove_marker` `0x09db7310` | Effect markers |
| `0x38` | `0x09db7490` | Renews the slot's placement serial and calls `0x09c0bb04(side, slot, 1, 0)` (purpose L) |
| `0x42` | `duel_core_cmd_show_negation` `0x09dbaf94` | UI event `0x23` (negation shown) |

## Key functions

All addresses are in `rel_duel_eng.prx` at base `0x09be1400`. Callers come from the full call graph.

| Address | Name | Conf. | Callers / notes |
| --- | --- | --- | --- |
| `0x09c32dac` | `duel_core_chain_pending_work() → busy` | H | `duel_core_run_turn_flow` (`0x09dcb3d8`) |
| `0x09c32e54` | `duel_core_chain_summon_window_step() → busy` | H | `duel_core_summon_raise_trigger` |
| `0x09c2e244` | `duel_core_chain_build_step() → 1` | H | the two above |
| `0x09c2f1fc` | `duel_core_chain_step() → 1` | H | the two above |
| `0x09c329e8` | `duel_core_chain_build_from_triggers() → 1` | H | `0x09c32dac`. Verified in PPSSPP (Session A, A9) |
| `0x09ccbe74` | `duel_core_offer_response_window(link, side) → done` | H | `duel_core_chain_build_step` (2), `duel_core_run_timing_windows` (2), `0x09ccc634`; see "The response window". Verified in PPSSPP (Session D, D1) |
| `0x09c32c5c` | `duel_core_chain_build_summon_response() → 1` | H | `0x09c32e54` |
| `0x09c2c19c` | `duel_core_chain_add_link(to_chain, packed, instance, arg) → added` | H | 10 |
| `0x09c2c9cc` | `duel_core_chain_activate(packed, instance, mode)` | H | player input `0x09dcd49c`, `0x09dcd5d0`, `0x09dcd710` |
| `0x09c2c578`, `0x09c2c754`, `0x09c2cd0c`, `0x09c2d1ec`, `0x09c2d4a4`, `0x09c2ccf8` | `duel_core_chain_queue_*` | H | 51, 43, 10, 4, 5, 1 |
| `0x09c539b0` | `duel_effects_can_activate(link, prev) → bool` | H | 11 |
| `0x09c52c60` | `duel_effects_can_respond_in_window(link, prev) → bool` | H | `0x09c523cc`, `0x09c526d0` |
| `0x09c52f60` | `duel_effects_is_activation_locked(link, prev) → bool` | H | per-card locks; full list in `effect-helpers-values.md` |
| `0x09bf275c` | `duel_effects_get_spell_speed(link) → 1..3` | H | 3 |
| `0x09ce401c` | `duel_effects_get_trigger_kind(link) → 0..2` | H | 7 |
| `0x09ce3dfc`, `0x09ce3e80`, `0x09ce3fc8` | `duel_effects_get_activation_step_handler`, `_get_target_choice_handler`, `_get_resolve_handler` | H | slot `+10`, `+14`, `+04` pointers |
| `0x09c2778c` | `duel_core_chain_announce_activation(link)` | H | 8 |
| `0x09c2d7e8` | `duel_core_chain_link_accepts_responses(link, strict) → bool` | M | 2 |
| `0x09c2ddbc` | `duel_core_chain_collect_auto_responses(link, &used_mask, &count) → bool` | M | 1 |
| `0x09c2dc2c` | `duel_core_chain_link_sends_card_to_graveyard(link) → bool` | H | 5 (incl. the target filter) |
| `0x09c2d9a4` | `duel_effects_is_disabled_at_activation(link) → bool` | M | 1 |
| `0x09c55d04` | `duel_effects_is_negated_on_resolution(link) → bool` | M | 4 |
| `0x09bf73ac` | `duel_effects_cannot_be_negated(link, activation) → bool` | H | 30 |
| `0x09c54248` | `duel_effects_link_should_resolve(link) → bool` | M | 3 |
| `0x09cbf120`, `0x09cbf228`, `0x09cbf438` | `duel_effects_get_link_target(link, i)`, `_link_target_is_valid(link, i, &out)`, `_relocate_link_target(link, i)` | H | 203, 162, 1 |
| `0x09c7772c` | `duel_effects_negate_link(ctx, link, activation) → negated` | H | 5 |
| `0x09c7799c`, `0x09c8178c` | `duel_effects_resolve_negate_activation`, `duel_effects_resolve_solemn_judgment` | H | handlers (slot `+04`) |
| `0x09c59e2c` | `duel_effects_cond_respond_to_previous_link(ctx, prev) → bool` | H | 41 records (slot `+0c`) |
| `0x09c42ab4`, `0x09c42afc`, `0x09c43d68`, `0x09c431ac`, `0x09c45f84`, `0x09c43148` | activation-step handlers (table above) | H | slot `+10` |
| `0x09c5698c` | `duel_effects_not_used_this_turn(ctx) → bool` | H | 63 |
| `0x09bf2f30` | `duel_effects_is_summon_negation_card(id) → bool` | H | 2 |
| `0x09c150bc`, `0x09c15320` | `duel_core_post_add_marker`, `duel_core_post_remove_marker` | H | 168, 71 |
| `0x09be9168`, `0x09be92a4`, `0x09be9348` | `duel_core_slot_has_effect(side, slot, card)`, `_has_marker_value(…, value)`, `_has_marker_kind(…, kind)` | H | 252 and more |
| `0x09be5660`, `0x09be6864` | `duel_core_detach_effect(node)`, `duel_core_expire_turn_effects()` | H | |
| `0x09bf7f08`, `0x09bf8140` | `duel_core_count_active_card_on_side(side, card, except_slot)`, `duel_core_count_active_card(card)` | H | face-up, not disabled copies |
| `0x09c26e38` | `duel_core_request_send_field_card_to_graveyard(side, slot, flip, card)` | M | starts the send batch (`0x09e2d298`) with destination `0x0e` |
| `0x09c19cf8`, `0x09c276e0` | `duel_core_post_show_negation`, `duel_core_post_announce_field_card` | H | commands `0x42`, `0x2d` |

## Open questions

- Confirm in PPSSPP: the 16-link limit (Session D of `docs/verification/ppsspp-plan.md`), the SEGOC order with two simultaneous triggers per player, the once-per-turn marker `0xfb6` and its expiry, and the activation-negated bit on Magic Jammer.
- The exchange sort may reorder triggers with equal keys; the official rules let the player choose. Check whether the game ever asks.
- `0x09cdd74c` (building state 0): forced position changes for seven listed cards (`0x09dedadc`) before a chain starts; which cards and why.
- Slot flag bits 1 and 4 of field slots in the chain context (bit 4 "send to the Graveyard after the chain" is H; bit 1 and command `0x38` are not understood).
- Event codes `0x23` (link that cannot be responded to) and `0x24` (activation without cost) need their raisers identified.
- The copied-effect layout (`+0x06` bit 0 with data at `+0x18`, i.e. in the next link slot) and Trap of Darkness's shifted target indexing.
- `duel_effects_is_activation_locked` is now read in full (`effect-helpers-values.md`); `duel_core_chain_collect_auto_responses` is only summarised; their per-card lists should be extracted like the other compare chains.
- What the value 2 returned by 274 slot `+0c` handlers (`duel_effects_cond_return_2`) means for the callers that distinguish it.
- The second-level path `0x09c941a8`, which calls the same activation, target, negation and resolve helpers outside the state machines (AI simulation or a forced resolution?).
