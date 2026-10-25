# Card-movement helpers of effect handlers (work package 4)

Helpers that per-card effect handlers in `gmodule/rel_duel_eng.prx` (runtime base `0x09be1400`) call to destroy, send, banish, return, flip, take control of and equip cards. Names are applied through `re/names-duel_eng.csv`; the fully understood ones also have a row in `re/documented-duel_eng.tsv`. Effect tables and the handler slots are in `docs/formats/effect-tables.md`, zones and the movement commands in `duel_core.md`, the chain context (`ctx` = chain link) in `chain.md`.

Evidence is static: Ghidra decompilation of every helper listed and of the handlers that call it, call-graph counts, and the card texts of the records whose slot `+04` handler reaches it (`tools/cardinfo.py`). Nothing here has been traced in PPSSPP yet. Confidence: H high, M medium, L low.

## Method and counts

A Ghidra script walked the slot `+04` (resolve) handler of every record in the four 24-byte tables (S/T `0x09dede78`, M1 `0x09df3680`, M2 `0x09df8810`, M3 `0x09dfaa60`) and counted, for each direct callee (`jal` or tail `j`), the distinct handlers and the records that reach it. 507 callees are called by at least one resolve handler. Columns "h / r" below: distinct resolve handlers that call the helper directly / table records behind them; "all" = all callers in the module; for the generic resolve handlers "rec" is the number of table records that use them as their slot `+04` handler.

## Architecture: two request queues, one executor

Effect handlers almost never move a card themselves. They fill one of two single-entry request blocks, which pending-work functions polled by `duel_core_run_turn_flow` execute over the following frames, so that destruction-replacement effects, prompts and link-duel synchronisation can run in between (H):

1. **The send batch** (field cards leaving their zone). A *request function* copies the cause (the 24-byte chain link of the effect, or a synthetic link built from a card id) to `0x09e2d2a0`, ORs the affected slots into the mask `0x09e2bba4` (bit `slot + 16 × side`, slots 0–10), stores the destination location in `0x09e2d2b8` and the flags in `0x09e2d2bc`, and sets the state `0x09e2d298 = 1`. `duel_core_send_batch_step` (`0x09c232bc`) then sends every slot of the mask through `duel_core_send_field_card` (`0x09c20ad0`), which posts the engine command. Requests made inside a timing batch (`0x09e28f90 ≠ 0`, outside a link duel) also get flag `0x8000000`, so the executor continues that batch instead of opening a new one.
2. **The pending action** (`0x09e2d2e0` = 1 pending; kind `0x09e2d2e8`; side `0x09e2d2e4`; arguments `u16 0x09e2d2f0`, `u16 0x09e2d2f2`; sub-step `0x09e2d2ec`), executed by `duel_core_run_pending_action` (`0x09c0e8b8`), a switch over kinds 1–`0x15`. Kind `0x0b` is "take control" (below); kind `0x11` is the effect battle (`battle.md`); kind `0x0c` negates every link below a given index; kinds 1–10, `0x0d`–`0x10`, `0x12`–`0x15` are player selections (discard, deck search, Creature Swap's choice …) and belong to other helper families.

Cards in lists (hand, deck, Graveyard, banished) are moved immediately by posting command `0x3e`, `0x32` or `0x40` (`duel_core.md`).

### Send-batch flags (`0x09e2d2bc`, the `flags` argument of `duel_core_send_field_card`)

| Bit | Meaning | Basis | Conf. |
| --- | --- | --- | --- |
| `0x1` | Caused by the opponent of the card's controller (added per slot by the executor: cause side ≠ slot side) | `send_field_card` computes `by_opp = flags & 1` and passes it to every immunity test | H |
| `0x2` | Destroy (not merely send). Enables the "cannot be destroyed" check `0x09c000fc`, destruction replacements and the `0x30` command | requesters of Raigeki, Mystical Space Typhoon … all set it; tribute and cost requesters do not | H |
| `0x4` | Destroyed by battle: command `0x31`, timing event `0x16` instead of `0x1c` | only `duel_core_request_battle_destruction` sets it | H |
| `0x8` | Activation negated: destination redirects (Dark Magician of Chaos, Quillbolt Hedgehog, Exodius …) are skipped; set by `duel_core_request_destroy_negated_slot` | code path; callers `duel_effects_negate_link`, the Horn of Heaven summon negation | M |
| `0x10`, `0x20` | Show the card as an effect target (command `0x4b`) | posted only when set | M |
| `0x1000` | Tribute: command `0x45` instead of `0x30`/`0x3f` | Tribute requesters and `duel_core_tribute_monsters` | H |
| `0x10000` | Request comes from the batch executor (skips the per-cause immunity tests that the executor already made) | always ORed by `duel_core_send_batch_step` | M |
| `0x20000` | Send to the other player's list (the card's controller instead of its owner, or the opponent's Deck) | `0x3c`/`0x3f` destination side = owner ^ bit; set by Parasite Paracide's requester and by `duel_core_request_send_slot_to_side` | H |
| `0x4000000` | Deck destination: bottom instead of top (command `0x3f` index ≠ 0 → appended at the end of the list; index 0 = top) | `send_field_card` and the `0x3f` handler | M |
| `0x8000000` | Requested inside a timing batch | request functions, executor | H |
| `0x10000000` | The destruction targets (passed as "targeted" to the destroy-immunity test `0x09c000fc`; Abyssal Kingshark's protection is skipped) | only `duel_core_request_destroy_target_slot` | M |

### Destination redirects inside `duel_core_send_field_card`

Before posting, the destination is rewritten (H for the code, M for the card readings): a battle-destroyed monster goes to the Deck while Grave Protector (`0x1797`) is active; a ritual card goes to the Deck under Samsara-type rule `0x19da`; Imperial Iron Wall (`0x1eb2`, test `0x09c0d5e8`) turns a banishment into a Graveyard send; banish-instead-of-Graveyard rules (`0x09c0d160`), Destiny Hero – Departed (`0x1cf9`), Exodius and Dark Magician of Chaos (`0x1ce0`, `0x16f8`, unless flag `0x8`), the Quillbolt Hedgehog marker (`0x1e15`), Winged Kuriboh LV9 (`0x1d66`) and Degenerate Circuit (`0x1afc`) turn the destination into `0x0f`; an extra-deck monster bound for the hand or Deck goes to the extra deck (`0x0c`); a token goes to "nowhere" (`0x10`, it disappears). The function returns the final destination; the executor compares it with the requested one (`0x09e2bbc0` = slots that reached it, `0x09e2bbbc` = slots handled at all).

### Executor states (`duel_core_send_batch_step`, `0x09e2d298`)

| State | Action |
| --- | --- |
| 0 | Idle. |
| 1 | Clear the bookkeeping masks `0x09e2bba8`–`0x09e2bbc0`; state 2. |
| 2–3 | Battle destruction (flag `0x4`): Dark Lucius LV8, Divine Knight Ishzark, D.D. Crazy Beast, Lesser Fiend, Mystical Beast Serket-type banish rules and Storm Caller, then `duel_core_send_battle_destroyed_cards` (`0x09c2215c`). Otherwise each masked slot is checked by `0x09c1f548(cause, side, slot, dest, destroy)` and the mask is reduced to the slots that can go; a dry run of `duel_core_send_field_card` (state 2 returns the destination without acting) collects destruction replacements. |
| 10–12 | Per-card replacement prompts (Telekinetic Shocker `0x1e28`, the Gladiator-Beast field `0x1c8b`, substitutes found by `0x09c13764`); each prompt runs as state + 100 and returns here. |
| 100 | Open a timing batch, send every masked slot for real (`send_field_card` with `flags | by_opp | 0x10000`), record results. |
| `0x65`–`0x67` | Follow-up prompts for slots in `0x09e2bbb4`, the Horseytail rule (`0x1df5`) after battle, close the timing batch, clear the mask; state 0. |
| `0x6d`–`0x70`, `0xc9`, `0xca` | Deferred card-specific sub-steps (Storm Caller, Colosseum, Telekinetic Shocker). |

States and masks: M (the control flow is clear, the purpose of each auxiliary mask is partly inferred).

## Helper reference

### Send-batch request functions (`duel_core`)

All return `void` and only fill the request block; the move happens later in `duel_core_send_batch_step`. `ctx` is the cause link (24 bytes, copied); "by card" variants build a zeroed link with side `side ^ by_opp` and card id `card`. Masks use bit `slot + 16 × side`. Confidence H for all (the bodies are 20 straight-line stores); the card readings are M.

| Address | Name and signature | Dest. | Flags | h / r / all | Example cards (resolve handler) |
| --- | --- | --- | --- | --- | --- |
| `0x09c24790` | `duel_core_request_destroy_mask(ctx, mask)` | GY | 2 | 46 / 162 / 46 | Dark Hole, Raigeki, Harpie's Feather Duster, Heavy Storm (through `duel_effects_resolve_destroy_all_matching`), Fissure |
| `0x09c24f9c` | `duel_core_request_destroy_slot(ctx, side, slot)` | GY | 2 | 30 / 43 / 33 | Sasuke Samurai, Fake Trap, Judgment of Anubis, Needle Wall, negated activations (`duel_effects_negate_link`) |
| `0x09c2508c` | `duel_core_request_destroy_target_slot(ctx, side, slot)` | GY | `0x10000002` | 8 / 128 / 9 | Mystical Space Typhoon, Trap Hole, Remove Trap, Man-Eater Bug (via `duel_effects_resolve_destroy_target`) |
| `0x09c24c00` | `duel_core_request_destroy_slot_by_card(side, slot, by_opp, card)` | GY | 2 | 16 / 58 / 48 | Self-destruction (Karate Man, Puppet King), rule destruction (no free zone after a control change) |
| `0x09c24874` | `duel_core_request_destroy_mask_by_card(side, card, mask)` | GY | 2 | 0 / – / 6 | Rule code in `0x09dd…` (battle, End Phase) |
| `0x09c25184` | `duel_core_request_destroy_slot_to_deck(ctx, side, slot)` | Deck, or extra deck for extra-deck monsters | 2 | 1 / 1 / 1 | one handler (`0x09c9d3f4`) |
| `0x09c252d8` | `duel_core_request_destroy_negated_slot(ctx, side, slot)` | GY | `0xa` | 1 / 5 / 2 | `duel_effects_negate_link`, Horn of Heaven summon negation `0x09c817bc` |
| `0x09c271d4` | `duel_core_request_send_slot_to_graveyard(ctx, side, slot)` | GY | 0 | 12 / 37 / 12 | Relinquished, Thousand-Eyes Restrict, Union Rider, Light of Judgment, Spatial Collapse |
| `0x09c273c0` | `duel_core_request_send_mask_to_graveyard(ctx, mask)` | GY | 0 | 7 / 8 / 8 | Last Turn, Chaos Emperor Dragon – Envoy of the End, Ocean Dragon Lord – Neo-Daedalus, Crystal Abundance |
| `0x09c272c4`, `0x09c274a4` | `duel_core_request_send_slot_to_graveyard_as_cost(ctx, side, slot)`, `…_mask_to_graveyard_as_cost(ctx, mask)` | GY | 0 | activation steps only (`0x09c43…`–`0x09c51…`) | Costs: the cause card id is zeroed while the request is made, so no immunity applies (M) |
| `0x09c26e38` | `duel_core_request_send_field_card_to_graveyard(side, slot, flip, card)` | GY | | (named in `chain.md`) | post-chain sweep |
| `0x09c26c5c`, `0x09c26d50` | `duel_core_request_tribute_slot(ctx, side, slot)`, `duel_core_request_tribute_mask(ctx, mask)` | GY | `0x1000` | 5 / 7, 1 / 1 | Ectoplasmer, Magical Dimension, Order to Smash, Bubble Shuffle, Volcanic Queen |
| `0x09c26878` | `duel_core_tribute_own_slot(side, slot)` | GY | `0x1000` | 1 / 1 / 14 | Activation-step costs "Tribute this card" (`0x09c43180`) |
| `0x09c25778` | `duel_core_request_banish_slot(ctx, side, slot, flags)` | Banished | `flags` | 10 / 22 / 10 | Dimensional Prison, Nobleman of Crossout, D.D. Warrior Lady, Karma Cut, Chaos Sorcerer |
| `0x09c25868` | `duel_core_request_banish_slot_checked(ctx, side, slot, flags) → bool` | Banished | `flags`, 0 for Exodius/Dark Magician of Chaos and Quillbolt-marked cards | 6 / 14 / 6 | Dimensionhole, Interdimensional Matter Transporter, Different Dimension Gate. Returns 0 and requests nothing while Imperial Iron Wall is active |
| `0x09c25a84` | `duel_core_request_banish_mask(ctx, mask, flags)` | Banished | `flags` | 8 / 11 / 10 | Bottomless Trap Hole (flags 2), Dark Mirror Force (0), D.D. Trap Hole, Chain Disappearance, Gandora the Dragon of Destruction |
| `0x09c253e4` | `duel_core_request_banish_slot_no_cause(side, slot, flags)` | Banished | `flags` | activation steps | Costs that banish a field card |
| `0x09c25b68` | `duel_core_request_return_slot_to_hand(ctx, side, slot)` | Hand | 0 | 12 / 47 / 12 | Compulsory Evacuation Device, Hane-Hane, Spirit monsters (Yata-Garasu) |
| `0x09c25ff4` | `duel_core_request_return_mask_to_hand(ctx, mask)` | Hand | 0 | 8 / 30 / 8 | Giant Trunade, Penguin Soldier, Tornado Bird |
| `0x09c25c58` | `duel_core_request_return_slot_to_hand_by_card(side, slot, by_opp, card)` | Hand | 0 | 0 / – / 3 | rule code |
| `0x09c260d8` | `duel_core_request_return_slot_to_deck(ctx, side, slot)` | Deck top (extra deck for extra-deck monsters) | 0 | 17 / 38 / 17 | Phoenix Wing Wind Blast, Back to Square One, De-Fusion, Monster Recovery, Elemental Hero Neos fusions at the End Phase |
| `0x09c261c8` | `duel_core_request_return_slot_to_deck_bottom(ctx, side, slot)` | Deck bottom | `0x4000000` | 2 / 2 / 2 | two handlers (`0x09cb3474`, `0x09ca119c`) |
| `0x09c262bc` | `duel_core_request_return_mask_to_deck(ctx, mask)` | Deck | 0 | 4 / 4 / 5 | Morphing Jar #2, Fiber Jar, Elemental Hero Storm Neos, Rainbow Neos |
| `0x09c263a0` | `duel_core_request_return_slot_to_deck_by_card(side, slot, by_opp, card)` | Deck | 0 | 0 / – / 1 | `0x09c5085c` |
| `0x09c2673c` | `duel_core_request_send_slot_to_opponent_deck(ctx, side, slot)` | Deck of the player who does not own the card | `0x20000` if the owner is `side` | 1 / 2 / 1 | Parasite Paracide |
| `0x09c27594` | `duel_core_request_send_slot_to_side(ctx, side, slot, to_side, dest)` | `dest` of player `to_side` | `0x20000` if `side ≠ to_side` | 6 / 31 / 7 | Relinquished, Thousand-Eyes Restrict, Union Rider, Formation Union, Brain Jacker (a card controlled by one player goes to the other player's list) |
| `0x09c22a98` | `duel_core_request_send_mask(ctx, mask, dest, flags)` | any | any | 10 / 24 / 14 | generic form (Polymerization, Miracle Contact, Rivalry of Warlords, Forced Back) |
| `0x09c22b78`, `0x09c22f18` | `duel_core_request_send_slot_by_card(side, slot, dest, flags, card)`, `duel_core_request_send_mask_by_card(side, mask, dest, flags, card)` | any | any | rule code | generic forms with a synthetic cause |
| `0x09c232a0` | `duel_core_request_battle_destruction()` (`battle.md`) | | 4 | | Battle step 9 |

### Executor and primitives (`duel_core`)

| Address | Name | What it does | Conf. |
| --- | --- | --- | --- |
| `0x09c232bc` | `duel_core_send_batch_step() → busy` | State machine above; pending-work function of `duel_core_run_turn_flow`. | M |
| `0x09c20ad0` | `duel_core_send_field_card(side, slot, dest, flags, cause_card) → final_dest` | Immunity tests by cause type (trap `0x09bff160`, spell `0x09bfefb4`, monster `0x09bff2e8`), destroy test `0x09c000fc`, banish test `duel_effects_can_banish_slot`; destruction substitutes (Sacred Protective Barrier, Metal Shooter, Abyssal Kingshark, Realm of Light, equip-type substitutes Gladiator Beast's Battle Archfiend Shield, Armored Cybern, Spirit of the Six Samurai, Heavy Mech Support Platform); redirects (above); posts `0x4b`/`0x4d`, then `0x31` (battle), `0x30` (destroy), `0x3c` (to a field slot), `0x32` (banish), `0x3f` (to a list) or `0x45` (Tribute); raises timing event `0x16` (battle) or `0x1c` (sent from the field) with a 32-bit event word (instance, side, slot, position, face, destroy, destination). | H (posting), M (substitutes) |
| `0x09c2215c` | `duel_core_send_battle_destroyed_cards()` | Sends the battle participants recorded at `0x09e28650 + side × 0x48` (flags `6`), with the banish rules listed in state 2. | M |
| `0x09c0e8b8` | `duel_core_run_pending_action() → 1` | Pending-action dispatcher (kinds above). | H |
| `0x09c0fa18` | `duel_core_request_take_control(controller, side, slot, mode)` | Pending action `0x0b`: `0x09e2d2f0 = slot`, `0x09e2d2f2 = (1 − side) + 2 × mode + 4 × (controller ≥ 0)`; a negative controller means "the opponent of `side`". 15 / 78 / 16. | H |
| `0x09c0dccc` | `duel_core_pending_take_control_step(controller, slot, arg)` | Kind `0x0b`: if the new controller has a free monster zone, lets them choose it (`duel_core_begin_select_zone`) and moves the card with `duel_core_move_field_card_to_slot`; otherwise destroys it (`duel_core_request_destroy_slot_by_card`). Bit 1 of `arg` wraps the move in a timing batch. | H |
| `0x09c172f8` | `duel_core_move_field_card_to_slot(?, from, to, a4)` | `from`/`to` = `side | slot << 8`; refuses an empty source or an occupied target; moves markers and links (`0x09c16e90`, `0x09c17040`: equips, Spellbinding-type bindings, triggers such as Kinetic Soldier-type listeners), posts command `0x3c`, raises timing event `0x19` (control changed). | M |
| `0x09c19a24` | `duel_core_post_place_list_card_on_field(side, location, ref, to_side, slot, face_up, position)` | Posts command `0x40` (list card to a field slot; packing in `duel_core.md`). 14 / 30 / 15. | H |
| `0x09c163b4` | `duel_core_post_set_face(side, slot, face_up)` | Posts command `0x34 (slot, face_up, 8)` if the slot is occupied. 11 / 35 / 13. | H |
| `0x09c15e8c` | `duel_core_flip_card_face(side, slot, run_flip, cause_card, by_opp)` | Turns the card face-up or face-down (command `0x34 (slot, new_face, …)`), unless the slot is disabled (flag bit 3) or immune to the cause's card type. Turning face-up queues and raises timing event `0x0c` (FLIP trigger, only when `run_flip` ≤ the card's FLIP level `BOOT 0x08863438`); turning face-down raises event 9. Per-card hooks: Morphing Jar-type, Gladiator Beast `0x1b67`, `0x1e95`. | M |
| `0x09c2a69c` | `duel_core_send_deck_ref_to_graveyard_ex(side, banish, ref, by_opp, cause_card)` | Deck or extra-deck card (instance `ref`) to the Graveyard (command `0x3e`) or banished (`0x32`), with the Imperial Iron Wall and banish-instead rules; raises timing event `0x1d`. | H |
| `0x09c2af20`, `0x09c2af34`, `0x09c2af48` | `duel_core_send_deck_ref_to_graveyard(side, ref, card, by_opp)`, `duel_core_send_deck_ref_to_graveyard_as_cost(side, ref)`, `duel_core_banish_deck_ref(side, ref, card, by_opp)` | Wrappers of the above. 13 / 20, –, 6 / 18. | H |
| `0x09c2ab68`, `0x09c2ad3c`, `0x09c2ae0c` | `duel_core_mill_deck(side, n, card, by_opp)`, `duel_core_mill_deck_as_cost(side, n)`, `duel_core_banish_deck_top(side, n, card, by_opp)` | Top `min(n, deck size)` cards in one timing batch. | H |
| `0x09c2a958` | `duel_core_send_named_cards_from_deck(side, name, banish, …)` | Every copy of a card name in the Deck and extra deck (name test `BOOT 0x0885fb5c`). | M |
| `0x09c19488`, `0x09c1947c` | `duel_core_banish_graveyard_card_ex(side, entry, by_opp, a4) → bool`, `duel_core_banish_graveyard_card(side, entry, by_opp)` | Graveyard card to banished (command `0x32 (0x0e, by_opp, ref)`), timing event `0x1f`; refuses under Imperial Iron Wall. 1 / 12, 19 / 32 / 36. | H |
| `0x09c18434` | `duel_core_return_graveyard_card_to_deck_ex(controller, side, ref, top) → bool` | Graveyard card to the Deck (extra deck for extra-deck monsters) by command `0x3e`, `top` = 0 shuffle/bottom (index 1) else top (index 0); if a Necrovalley-type rule (`0x09c0d4cc`) forbids it, banishes instead. Event `0x25`. | M |
| `0x09c190ec` | `duel_core_add_list_card_to_hand(ctx, side, from_location, ref) → bool` | Graveyard or banished card to the hand (extra deck for extra-deck monsters) by command `0x3e`; event `0x1b` (added to the hand) or `0x25`. | H |
| `0x09c1558c`, `0x09c15584` | `duel_core_equip_card_ex(side, equip, target, kind)`, `duel_core_equip_card(side, equip, target)` (kind 10) | `equip`/`target` = `side | slot << 8`. Detaches the equip card from its old target (marker kind 10 removed with command `0x36`), posts command `0x41 (equip, target, kind)`, raises timing event `0x18` (equipped). Per-card hooks: Armored Cybern-type `0x1edf`/`0x1cf4`, `0x13ea`, `0x186b`, `0x13c3`. 8 / 53 (both). | M |

### Effect-level helpers (`duel_effects`)

| Address | Name | What it does | h / r | Conf. |
| --- | --- | --- | --- | --- |
| `0x09ce3364` | `duel_effects_collect_target_mask(ctx) → mask` | Calls the card's own slot `+08` filter on all 22 field slots (skipping disabled ones; recursion counter `0x09e28f7c`); −1 without a filter. The "all matching cards" mask of mass effects. | 35 / 154 | H |
| `0x09ce3484` | `duel_effects_collect_slot_mask(ctx, filter) → mask` | Same with an explicit filter function. | 18 / 24 | H |
| `0x09ce35d0` | `duel_effects_count_valid_targets(ctx) → n` | Count of slots accepted by the slot `+08` filter. | 19 / 83 | H |
| `0x09c2bf4c` | `duel_effects_is_link_card_face_up(ctx) → bool` | Finds the link's card by instance (`ctx +4`): a monster zone counts if face-up and not disabled, a spell/trap zone if face-up. Guard of continuous and self-affecting effects. | 89 / 297 | M |
| `0x09c2c0b4` | `duel_effects_link_refresh_location(ctx)` | Rewrites the side and slot of `ctx +2` from the card's current monster zone. | 65 / 252 | H |
| `0x09c164b8` | `duel_effects_change_position(ctx, side, slot, flip, a5) → bool` | `duel_core_change_position` unless `duel_effects_is_slot_unaffected`; `by_effect` = side ≠ controller. | 25 / 72 | H |
| `0x09c15e64` | `duel_effects_flip_card_face(ctx, side, slot, run_flip)` | `duel_core_flip_card_face` with the cause card and by-opponent flag from `ctx`. | 11 / 14 | H |
| `0x09c16cc8` | `duel_effects_set_face_down(ctx, side, slot)` | Book of Moon semantics: face-up Attack → position change with flip; face-up Defense → turn face-down; a token or face-down Attack card → Defense only. Refused when the controller may not set (`0x09c0c330`) or the slot is unaffected. | 6 / 38 | H |
| `0x09c1758c` | `duel_effects_swap_control(ctx, a, b, kind) → bool` | Creature Swap: both monsters (`side | slot << 8`) must be occupied, affected and controllable (`duel_effects_can_take_control`); adds control markers (command `0x35`, kind `kind`), posts command `0x3d`, raises event `0x19` twice. | 5 / 7 | H |
| `0x09c80544` | `duel_effects_find_extreme_stat_target(ctx, &out) → value` | Among the opponent's monsters accepted by the filter, the highest DEF (Smashing Ground), lowest ATK (Fissure, Chthonian Blast) or highest ATK (Hammer Shot, Bottomless Shifting Sand, Widespread Ruin). | 1 / 5 | H |
| `0x09c2ac4c` | `duel_effects_mill_deck(ctx, side, n)` | Top `n` Deck cards of `side` to the Graveyard; by-opponent from `ctx`. | 25 / 42 | H |
| `0x09c19384`, `0x09c19400` | `duel_core_add_graveyard_card_to_hand(ctx, side, entry)`, `duel_core_add_banished_card_to_hand(ctx, side, entry)` | Wrappers of `duel_core_add_list_card_to_hand` after checking the card is still there. | 15 / 79, 4 / 56 | H |
| `0x09c18428` | `duel_effects_return_graveyard_card_to_deck(ctx, side, ref, top)` | `duel_core_return_graveyard_card_to_deck_ex` with the controller from `ctx`. | 12 / 52 | M |

### Generic resolve handlers (slot `+04`, also called by other handlers)

They all re-check the first target (`duel_effects_link_target_is_valid`, `duel_effects_call_handler_08_b`) before acting, so a target that left the field or became illegal is skipped. Confidence H for the action; the card lists are the records that use the handler.

| Address | Name | Action | rec | Example cards |
| --- | --- | --- | --- | --- |
| `0x09c747e4`, `0x09c744bc` | `duel_effects_resolve_destroy_target`, `…_b` | Destroy target 0 (`duel_core_request_destroy_target_slot`). Identical bodies. | 114, (19 handlers call `_b`) | Mystical Space Typhoon, Trap Hole, Remove Trap, Tribute to the Doomed |
| `0x09c74874` | `duel_effects_resolve_destroy_all_matching` | `duel_core_request_destroy_mask(ctx, collect_target_mask(ctx))`. | 90 | Dark Hole, Raigeki, Harpie's Feather Duster, Heavy Storm, Acid Rain, Eradicating Aerosol |
| `0x09c80710` | `duel_effects_resolve_destroy_extreme_stat_monster` | Choice via `find_extreme_stat_target` (or a player choice on ties), then destroy. | 5 | Fissure, Hammer Shot, Smashing Ground |
| `0x09c8ef38` | `duel_effects_resolve_destroy_battle_opponent` | Destroy the monster recorded at `0x09e28624`/`0x09e28640` (the battle opponent; M). | 6 | Sasuke Samurai, Paladin of White Dragon, Nanobreaker |
| `0x09c9d7b0` | `duel_effects_resolve_destroy_self` | Destroy the card itself if it is still the same instance. | 12 | Karate Man, Puppet King, Infernal Dragon, Gellenduo |
| `0x09c8e6bc` | `duel_effects_resolve_destroy_banish_all_matching` | `duel_core_request_banish_mask(ctx, mask, 2)`. | 1 | Bottomless Trap Hole |
| `0x09c987b0` | `duel_effects_resolve_banish_all_matching` | Same with flags 0. | 2 | Dark Mirror Force, Armoroid Gaidengo |
| `0x09c97874` | `duel_effects_resolve_banish_target` | `duel_core_request_banish_slot(ctx, target, 0)`. | 6 | Dimensional Prison, Chaos Sorcerer, Black Luster Soldier – Envoy of the Beginning |
| `0x09c80a38` | `duel_effects_resolve_banish_graveyard_targets` | Every Graveyard target to banished (`duel_core_banish_graveyard_card`). | 10 | Soul Release, Gravedigger Ghoul, Kycoo the Ghost Destroyer |
| `0x09c7cd5c` | `duel_effects_resolve_return_target_to_hand` | `duel_core_request_return_slot_to_hand`. | 13 | Compulsory Evacuation Device, Hane-Hane, Spiritualism |
| `0x09c7d284` | `duel_effects_resolve_return_targets_to_hand` | All valid targets as one mask. | 8 | Penguin Soldier, Tornado Bird |
| `0x09c824dc` | `duel_effects_resolve_return_all_matching_to_hand` | Mask from the filter, to the hand. | 11 | Giant Trunade, Dark Scorpion Retreat, Burst Return |
| `0x09c7b368` | `duel_effects_resolve_return_self_to_hand` | The card itself, if still face-up on the field. | 18 | Spirit monsters (Yata-Garasu, Susa Soldier, Maharaghi) |
| `0x09c957c8` | `duel_effects_resolve_add_self_to_hand` | The card itself from the Graveyard (or banished) to the hand. | 17 | Sinister Serpent, Return Zombie, Regenerating Mummy |
| `0x09c7bad8` | `duel_effects_resolve_add_targets_to_hand` | Every Graveyard/banished target to the hand. | 36 | Salvage, Backup Soldier, Spell Reproduction, Magical Stone Excavation |
| `0x09c9dbec` | `duel_effects_resolve_return_target_to_deck` | `duel_core_request_return_slot_to_deck`. | 5 | Phoenix Wing Wind Blast, Back to Square One |
| `0x09ca7bc0` | `duel_effects_resolve_return_self_to_extra_deck` | Elemental Hero Neos fusions: the card itself back to the extra deck at the End Phase (redirect of a Deck return); other cases are per-card. | 9 | Elemental Hero Air/Aqua/Flare/Dark Neos |
| `0x09c7ced0` | `duel_effects_resolve_mill_opponent` | `duel_effects_mill_deck(ctx, opponent, n)`, `n` per card (count functions `0x09bf9d4c`, `0x09bf9720`, `0x09c014ac`). | 10 | Needle Worm, Goblin Zombie, Doom Dozer |
| `0x09c81650` | `duel_effects_resolve_take_control_target` | Marker on the target (kind 1; kind 5 for Intercept, Chthonian Polymer, Arcana Force XVIII; Electromagnetic Bagworm kind 1 or `0x11`), then `duel_core_request_take_control`. | 18 | Change of Heart, Mind Control, Brain Control |
| `0x09c889c8` | `duel_effects_resolve_creature_swap` | Choice of one monster per player (pending action 10), then `duel_effects_swap_control`. | 2 | Creature Swap, Creature Seizure |
| `0x09c8d120` | `duel_effects_resolve_set_target_face_down` | `duel_effects_set_face_down` on the target. | 6 | Book of Moon, Tsukuyomi |
| `0x09c8f06c` | `duel_effects_resolve_set_self_face_down` | The same on the card itself. | 17 | Royal Keeper, Swarm of Scarabs, Guardian Sphinx |
| `0x09c8f418` | `duel_effects_resolve_flip_target_face_up` | Turn face-up (FLIP runs) and change the position. | 1 | Book of Taiyou |
| `0x09c790f4` | `duel_effects_resolve_change_position` | Position change on each target (Aqua Spirit also sets slot flag 21). | 18 | Stop Defense, Block Attack, Security Orb |
| `0x09c792ac` | `duel_effects_resolve_change_position_all` | All matching monsters. | 13 | Earthquake, Windstorm of Etaqua, Zero Gravity |
| `0x09c7f2bc` | `duel_effects_resolve_change_self_to_defense` | The card itself to Defense Position if in Attack Position. | 9 | Summon Priest, Total Defense Shogun, Silent Insect |
| `0x09c748a8` | `duel_effects_resolve_equip_to_target` | Equip the activated card to its target (`duel_core_equip_card`), or take control for Snatch Steal-type cards (`duel_core_request_take_control`, mode 1). | 20 | Metalmorph, Zero Sprite, Attribute Mastery, Cocoon of Evolution |

## Card cases checked against the method

| Card | Resolve handler | Helper chain |
| --- | --- | --- |
| Raigeki, Dark Hole, Heavy Storm, Harpie's Feather Duster | `duel_effects_resolve_destroy_all_matching` | slot `+08` filter (side/zone bits) → `collect_target_mask` → `request_destroy_mask` → batch → command `0x30` |
| Mystical Space Typhoon | `duel_effects_resolve_destroy_target` | `request_destroy_target_slot` (flags `0x10000002`) |
| Change of Heart, Mind Control | `duel_effects_resolve_take_control_target` | marker (`0x35`) → pending action `0x0b` → zone choice → command `0x3c`, event `0x19` |
| Creature Swap | `duel_effects_resolve_creature_swap` | command `0x3d` |
| Giant Trunade | `duel_effects_resolve_return_all_matching_to_hand` | `request_return_mask_to_hand` → command `0x3f` (dest `0x0b`) |
| Bottomless Trap Hole | `duel_effects_resolve_destroy_banish_all_matching` | `request_banish_mask(…, 2)` → command `0x30` with dest `0x0f` |
| Book of Moon | `duel_effects_resolve_set_target_face_down` | command `0x33` or `0x34` |

The control duration (until End Phase for Change of Heart, permanent for Snatch Steal) is carried by the marker kind and handled by the End-Phase marker expiry (`chain.md`); which kind means which duration is not yet confirmed.

## Open questions

- Confirm in PPSSPP the flag bits marked M (`0x8`, `0x10000`, `0x4000000`, `0x10000000`) and the deck index convention of command `0x3f` (0 = top, non-zero = bottom).
- `0x09c1f548` (the per-slot pre-check of the executor) and `0x09c1fb50` (called at the end of every `send_field_card`) are not read in full.
- The auxiliary masks `0x09e2bbac`, `0x09e2bbb0`, `0x09e2bbb4`, `0x09e2bbb8` of the executor: their exact roles in the replacement prompts.
- Marker kinds of control change (1, 5, `0x11`) and how they map to "until the End Phase" and "while equipped".
- `duel_core_return_graveyard_card_to_deck_ex`: whether `top = 0` means "shuffle" (index 1) or "bottom".
- The remaining pending-action kinds (selection helpers) belong to the hand/deck helper families and are not covered here.
- Commands `0x39`, `0x3b`, `0x41`, `0x4b`, `0x4d`, `0x55` are posted by these paths but their handlers were not read.
