# Effect helpers: values, negation and restrictions (work package 4)

The per-card handlers of `gmodule/rel_duel_eng.prx` (runtime base `0x09be1400`; tables in `docs/formats/effect-tables.md`) are written against a small vocabulary of helper functions. This document names the helpers that deal with **numbers and locks**: Life Points, ATK/DEF changes through effect records, counters, continuous negation, attack and summon restrictions, battle-position changes, coin tosses and dice, and the counting predicates that feed them. Helpers that move cards, choose targets or summon are documented elsewhere (`summon.md`, `chain.md`, `duel_core.md`).

All addresses are runtime addresses. Evidence is static: Ghidra decompilation of a read-only copy of the project, the call graph, constants loaded before calls, and the card database (`tools/cardinfo.py`) to identify card ids and to correlate helpers with the cards' `CARD_Genre` flags. Nothing here has been traced in PPSSPP. Confidence: H (high), M (medium), L (low).

## Method

1. A call graph of the module was built from the instructions (`jal` and tail `j` out of the function) with the function bounds of `re/functions.csv`.
2. Every helper was ranked by the number of slot `+04` (resolution) handlers and of all table handlers that call it, and by the cards behind those handlers.
3. For each genre of my domain ("Reduce Life Points", "Recover Life Points", "Increase/Decrease ATK/DEF", "Counter", "Cancel out Effect", "Restrict Attack", "Cannot be destroyed", "Change card position", "Gamble", "Pierce", "Multiple Attack"), helpers were ranked by enrichment: the share of their cards that carry the genre against the share among all cards. Example: `0x09c0fe60` is reached by 34 cards, all 34 of genre "Gamble" (×58); `0x09c1abec` by 65 cards, 64 of genre "Counter" (×38).
4. The top helpers and the resolve handlers of well-known cards (Ookazi, Dian Keto, Shrink, Rush Recklessly, Book of Moon, Stop Defense, Swords of Revealing Light, Graceful Dice, Dice Jar, Time Wizard, Breaker the Magical Warrior, Skill Drain, Magic Cylinder, Negate Attack, Waboku, Limiter Removal) were decompiled; continuous cards without a table record (Jinzo, Imperial Order, Messenger of Peace, Gravity Bind, Nightmare's Steelcage) were located through the functions that load their ids.

The call counts below are "resolve handlers / any table handler / all calling functions" from that call graph.

## Life Points and burn

There is one generic LP effect. `duel_effects_get_lp_change_amounts` is a per-card chain (10,636 bytes) that writes the signed LP change of both players; `duel_effects_resolve_lp_change` applies it. 24 cards use this resolve handler directly (Ookazi, Hinotama, Dian Keto the Cure Master, Wave-Motion Cannon, Marshmallon …); the chain itself is reached by 216 cards through other handlers and the AI (`0x09d3908c`, which evaluates an effect by calling the same chain).

| Address | Name | Signature | Behaviour | Posts | Examples | Conf. |
| --- | --- | --- | --- | --- | --- | --- |
| `0x09c74cbc` | `duel_effects_get_lp_change_amounts` | `void (link *ctx, int out[2])` | `out[player]` = signed change for player 0/1: negative = damage, positive = gain. Controller `owner ^ switched`, swapped for Mystical Refpanel (`0x12da`). Values are constants (Ookazi −800 to the opponent) or computed: per Level of a target × 100, × −500 per Level of the card instance, the card's ATK or half of it, counters × −1000 (Morphtronic Clocken), Graveyard counts × −200 … | — | 216 cards (chain + AI) | H |
| `0x09c77648` | `duel_effects_resolve_lp_change` | `int (link *ctx)` | Calls the chain; inside one timing batch inflicts the negative entries (`duel_core_inflict_damage`, opponent first) then applies the positive ones (`duel_core_gain_lp`). Returns 0. | `0x24`, `0x23` | Ookazi, Hinotama, Dian Keto, Wave-Motion Cannon, Marshmallon (13 handlers / 24 cards) | H |
| `0x09c27894` | `duel_core_set_lp` | `void (int side, int value)` | Clamps to `0xffff`; posts command `0x25` (LP = value). | `0x25` | 8 callers | H |
| `0x09c27a18` | `duel_core_is_lp_gain_reversed` | `bool (int side)` | True when the opponent controls an active Bad Reaction to Simochi (`0x1256`) or Nurse Reficule the Fallen One (`0x1cb8`) and no Prime Material Dragon (`0x1d8f`) is active: gains for `side` become damage. Used by `duel_core_gain_lp` and the AI. | — | 9 callers | H |
| `0x09c0d6ac` | `duel_core_can_take_effect_damage` | `bool (int side, int all)` | False while a player-wide marker of Pikeru's Circle of Enchantment, Cyber Kirin, Cocoon Veil or Hanewata is on `side`, or while `side` controls Des Wombat; with `all` set also Hallowed Life Barrier and Flame Wall (when the Graveyard holds a card of Type 4). This is the `0x09c0d6ac` check of `duel_core_inflict_damage` (`battle.md`). | — | 4 callers | M (meaning of `all`) |
| `0x09c87a78` | `duel_effects_resolve_negate_attack_lp` | `int (link *ctx)` | If an attack is in progress (`0x09e2bba0` bit 1 set, bit 0 clear) and the target (the attacker) is still valid: command `0x1f` (negate the attack), then per card: Magic Cylinder inflicts the attacker's ATK to its controller, Draining Shield gains it, Morphtransition changes the position of a second target. | `0x1f`, `0x24`/`0x23` | Magic Cylinder, Draining Shield, Morphtransition | H |

Other burn patterns found in single-card handlers: Dice Jar (`0x09c8f0c4`) inflicts `500 × die` (6 → 6,000) to the lower roller; Time Wizard's failure branch (`0x09c7af44`) inflicts half the summed ATK of the destroyed monsters to its controller; the battle-step and Standby Phase costs are in `battle.md`.

## ATK/DEF changes and other lasting effects (effect records)

Temporary and lasting effects are 10-byte records on a slot's list (`stat-modifiers.md`); handlers create them through these helpers. The stat builder interprets the record by its key (the source card id).

| Address | Name | Signature | Behaviour | Posts | Examples | Conf. |
| --- | --- | --- | --- | --- | --- | --- |
| `0x09c150ec` | `duel_effects_attach_effect_to_slot` | `bool (link *ctx, int side, int slot, int key, int kind, int value)` | Unless the slot is unaffected by `ctx` (`duel_effects_is_slot_unaffected`), posts command `0x35` with `a = slot | kind << 8`, `b = key`, `c = value`, side in bit 15. Returns whether it posted. `kind` is the full byte `+2` of the record (low nibble kind, high nibble turn counter). | `0x35` | 36 handlers / 71 cards (Graceful Dice, Limiter Removal, Pyramid Energy …) | H |
| `0x09c793e4` | `duel_effects_attach_effect_to_targets` | `bool (link *ctx, int kind, int value)` | For each target of the link that is still valid (`duel_effects_link_target_is_valid` + slot `+08` filter): kinds < 6 → `attach_effect_to_slot(…, key = ctx card id)`; kinds ≥ 6 → `duel_core_post_add_marker` with the key = the card instance's location. Returns true when every target received it. | `0x35` | 9 handlers / 60 cards | H |
| `0x09c7954c` | `duel_effects_attach_effect_to_all` | `void (link *ctx, int kind, int value)` | Same for every field slot (both sides, 0–10) that passes the card's slot `+08` filter. | `0x35` | 5 handlers / 18 cards | H |
| `0x09c80d2c` | `duel_effects_resolve_turn_stat_effect` | `int (link *ctx)` | `attach_effect_to_targets(ctx, 2, 0)`: a kind-2 record keyed by the card; its amount is in the stat builder's `attached` chain. | `0x35` | Shrink, Rush Recklessly (+2 more) | H |
| `0x09c87d0c` | `duel_effects_resolve_boost_own_monsters` | `int (link *ctx)` | For each of the controller's monster slots passing the filter, a kind-2 record with a computed value: The Big March of Animals 200 × face-up monsters of Type 11 (`count_face_up_monsters_by_race`), Limiter Removal the monster's ATK / 5, Pyramid Energy the option stored in the link (`u16 ctx+8`), D. Tribe the current placement serial `0x09e2d1d0`; the stat chain turns these into amounts. | `0x35` | 4 cards | M (value meanings) |
| `0x09c8be00` | `duel_effects_resolve_add_player_marker` | `int (link *ctx)` | `post_add_player_marker(controller, card, kind 1, value)` (value = the card instance for Super Rejuvenation). The rule checks look for the key on the player slot. | `0x35` | Waboku, Threatening Roar, Super Rejuvenation | H |
| `0x09c2b6a0` | `duel_core_post_add_player_marker` | `void (int side, int key, int kind, int value)` | `duel_core_post_add_marker(side, 11, …)`: a player-wide record (slot 11). | `0x35` | 91 handlers / 329 cards | H |

Record queries used by handlers and rule checks (all walk the slot's list from `u16 +0x0a`, pool `0x09e2c7cc`):

| Address | Name | Signature | Returns | Conf. |
| --- | --- | --- | --- | --- |
| `0x09be8fb0` | `duel_core_count_slot_effects` | `int (side, slot, key)` | Number of kind < 6 records with that key (23 callers). | H |
| `0x09be957c` | `duel_core_get_effect_value` | `int (side, slot, key)` | `u16 value` of the first kind < 6 record with that key, −1 if none (56 callers). | H |
| `0x09be9200` | `duel_core_find_effect_with_value` | `int (side, slot, key, value)` | Pool index of a kind < 6 record with that key and value, 0 if none. | H |
| `0x09be93e8` | `duel_core_has_current_turn_effect` | `bool (side, slot, key)` | A kind 1 or 2 record with that key whose turn counter is 0 (i.e. it applies now and expires at the next turn change). Callers test Electric Lizard, Sage of Silence/Stillness. | M |
| `0x09be8228` | `duel_core_get_link_kind_from` | `int (side, slot, src_side, src_slot)` | Kind (6–15) of the link record on `side/slot` whose key is the source location, 0 if none (34 callers). | H |
| `0x09be83b0` | `duel_core_find_linked_slot` | `int (src_side, src_slot)` | Location `side | slot << 8` of the first field card that carries a link from this source (the monster an equip/continuous card is attached to), `0xffff` if none (58 callers). | H |
| `0x09be7c70` | `duel_core_count_active_links_from` | `int (side, slot, card)` | `duel_core_count_links(…, card, check_active = 1, check_immunity = 0, …)` (22 callers). | H |
| `0x09c2bf4c` | `duel_effects_is_link_card_face_up` | `int (link *ctx)` | Whether the link's card instance is still on the field: for a monster zone face-up and slot flag bit 2 clear; for a spell/trap zone the face-up word. 89 resolve handlers use it as "the card is still there" (Breaker, Skill Drain-type checks). | M |

## Counters

Counters live in two places (H, from `duel_core_get_counter_count` and the command handler):

- **Types 0–12**: the slot's 32-bit value word `+0x0c` (`0x09e2a568 + side × 0xb3c + slot × 0x14`). The card in the slot decides which type the word holds.
- **Types 13–19**: a kind-3 effect record keyed by a card id; its value is the count.

The type table at `0x09deb97c` (20 words) gives, per type, the card id that defines it. Types 0 and 1 use predicates in `BOOT.BIN` instead (`0x08866398` returns a card's Spell Counter capacity, `0x088664fc` a second group). Read from the module (card names from the maintainer's `cardinfo`):

| Type | Card | Type | Card |
| --- | --- | --- | --- |
| 0 | Spell Counter (any card with a capacity) | 10 | Worm Gurus / Worm Illidan (Worm Counter) |
| 1 | predicate `0x088664fc` | 11 | Morphtronic Clocken |
| 2 | Clock Tower Prison | 12 | The World Tree |
| 3 | Vennominaga the Deity of Poisonous Snakes | 13 | Maiden in Love (record) |
| 4 | Crystal Tree | 14 | Magic Reflector (record) |
| 5 | Spell Chronicle | 15 | A-Counter, Alien Grey (record) |
| 6 | Six Samurai United (at most 2: adding is refused at 2) | 16 | Ice Master (record) |
| 7 | D - Formation | 17 | Venom Swamp (record) |
| 8 | Realm of Light | 18 | Cloudian - Ghost Fog (record) |
| 9 | Spacegate | 19 | Sacred Protective Barrier (record) |

| Address | Name | Signature | Behaviour | Posts | Examples | Conf. |
| --- | --- | --- | --- | --- | --- | --- |
| `0x09beff3c` | `duel_core_get_counter_count` | `int (side, slot, type)` | Types < 13: the slot word if the slot's card matches the type (0 otherwise); types ≥ 13: `duel_core_sum_effect_values(side, slot, type card)`. | — | 109 callers | H |
| `0x09c1abec` | `duel_core_add_counters` | `bool (side, slot, type, delta)` | Refuses (returns 0) when `delta` is 0, the slot's card does not take that type, a positive `delta` meets a negated card (slot flag bit 8), a Spell Counter card is full, or Six Samurai United already has 2. Posts command `0x3b (a = slot, b = delta, c = type)`. Side rules: A-Counters (type 15) reaching 0 release the control links of Alien Hypno, Mass Hypnosis and Brainwashing Beam (command `0x36`) and a negative change triggers "A" Cell Incubator; Spell Counters raising Silent Magician LV4 to 5 add the LV8 marker, Tower of Babel reaching 4 queues its trigger. | `0x3b`, `0x36`, `0x35` | 31 handlers / 67 cards | H |
| `0x09bf0064` | `duel_core_count_counters_on_side` | `int (side, type)` | Sum over slots 0–10. | — | 5 callers / 44 cards | H |
| `0x09beff24` | `duel_core_get_counter_type_card` | `int (type)` | `0x09deb97c[type]`. | — | | H |
| `0x09c47d8c` | `duel_effects_cost_remove_spell_counters` | `int (link *ctx)` | Activation step (slot `+10`): removes the per-card number of Spell Counters (Mega Ton Magical Cannon 10, Royal Magical Library / Legendary Flame Lord 3, Dark Red Enchanter 2, Breaker 1 …) with `add_counters(…, 0, −n)`. The same numbers as `duel_effects_get_counter_cost`. | `0x3b` | 19 cards | H |
| `0x09c94830` | `duel_effects_resolve_add_spell_counter` | `int (link *ctx)` | If the card is still face-up on the field: refresh the link's location, add 1 Spell Counter (2 for Dark Red Enchanter). | `0x3b` | Breaker the Magical Warrior, Dark Red Enchanter | H |
| `0x09cab73c` | `duel_effects_resolve_place_counters_on_targets` | `int (link *ctx)` | Sub-step machine (states 100/99/0x62 in `0x09e28f60`): choose a target, add one counter of type `0x09e28f68` unless unaffected, repeat `0x09e28f64` times. | `0x3b` | 3 cards | M |
| `0x09db7620` | `duel_core_cmd_add_counters` | `void ()` | Command handler: Spell Counters are clamped to the capacity and at 0 (and counted for the statistics `0x34`/`0x35`); types 1–12 clamped at 0; types ≥ 13 rebuild the kind-3 record with the new sum. UI event `0x27 (side | slot << 8, delta, type)`. | — | | M (command code `0x3b` inferred from the poster) |
| `0x09db7540` | `duel_core_cmd_set_slot_value` | `void ()` | Command handler: `a` = slot, `a >> 8` = add flag; the slot word `+0x0c` is set to (or increased by) the 32-bit value `b | c << 16`. UI event `0x26`. | — | | M (command code `0x39` inferred) |
| `0x09c1aad4` | `duel_core_post_set_slot_value` | `void (side, slot, value)` | Posts command `0x39 (slot, value & 0xffff, value >> 16)`: sets the slot word (counters, Swords-type turn counts, declared values). Used to reset counters when an effect is negated. | `0x39` | 21 handlers / 69 cards | H |
| `0x09c00514` | `duel_core_get_a_counter_penalty_count` | `int (side, slot)` | A-Counters on the monster × number of active Alien monsters (Alien Grey, Alien Shocktrooper-type ids `0x1a90`, `0x1a92`, `0x1a94`, `0x1a96`, `0x1c83`) on the sides it is not immune to; the battle code multiplies it by −300 (`stat-modifiers.md`). | — | | M |

## Continuous negation (Skill Drain, Jinzo, Imperial Order …)

Continuous negation is **not** checked by each handler. A global pass recomputes a per-slot "negated" flag (slot `+0x10` bit 8, the bit that `duel_core_is_effect_active` and `duel_effects_is_negated_on_resolution` already test), and runs per-card clean-up when a card becomes negated (H for the structure).

| Address | Name | Signature | Behaviour | Conf. |
| --- | --- | --- | --- | --- |
| `0x09c54a84` | `duel_effects_collect_negation_state` | `void (int state[17])` | Snapshot of the active negators: Judgment of Pharaoh markers (`0x1679`, values 1 and 2), Triangle Ecstasy Spark, Skill Drain (the oldest active copy's placement serial, `0x09bf8990`), Imperial Order and Talisman of Spell Sealing (spells of both players), Jinzo (traps of both players; its controller is exempt while an Amplifier link `0x12d3` is on it), and further per-player flags for monster-effect and spell/trap negation. | M |
| `0x09c553e0` | `duel_effects_update_negated_slots` | `bool ()` | For every occupied field slot computes "negated" from the snapshot: face-up effect monsters are negated while Skill Drain-type negators are active; four cards (Vennominaga, `0x19c3`, `0x194e`, `0x1437`) only when their placement serial is newer than the negator's, the card's own immunity, A-Counter rules, Spell/Trap negation for spells and traps, Necrovalley/Gravekeeper exceptions, Vehicroid Connection Zone; then `duel_core_set_slot_negated`. Returns whether anything ran. | M |
| `0x09c19d1c` | `duel_core_set_slot_negated` | `void (side, slot, on)` | If the flag changes: `post_set_slot_flag(side, slot, 8, on)`; when a face-up monster becomes negated, per-card clean-up: reset the slot value (`post_set_slot_value(…, 0)`) for ~45 cards with counters or stored values, remove self-markers (Slate Warrior `0x13ad`, `0x1009`), drop links created by the card (Gradius' Option). | H |
| `0x09c548bc` | `duel_effects_is_monster_effect_negated_by_card` | `bool (side, slot)` | The monster is named by Prohibition, or carries one of a dozen card-specific negation markers or links (Level Modulation, `0x1d0a`, Rainbow Veil links …). | M |
| `0x09bfd264` | `duel_effects_is_slot_prohibited` | `bool (side, slot)` | An active, non-negated Prohibition (`0x1368`) whose declared name (its slot word) matches the monster, unless the monster is unaffected by spells. Also blocks attacks (`duel_core_check_attack_restrictions` sets message `0x10`). | H |
| `0x09bfd3fc` | `duel_effects_is_card_prohibited` | `bool (card, instance)` | Same test by card id; with `instance ≥ 0` a Prohibition that already holds that instance's marker is ignored. | H |
| `0x09bfefb4`, `0x09bff160` | `duel_effects_is_unaffected_by_spells`, `_by_traps` | `bool (side, slot, rel)` | `(rel + 1) & immunity word` (stat-block words 10/11); `rel` = 1 when the source belongs to the other player. | H |

**Activation locks.** `duel_effects_is_activation_locked(link, prev)` (`0x09c52f60`, `chain.md`) is the per-activation counterpart; read in full here. It returns 1 (and sets the UI message `0x09e2d288 = 0x14` for the human player) when any of these holds (H for the list, M for the per-card readings):

- Level Modulation marker on the monster; Diffusion Wave-Motion player marker naming this card;
- monster effects: Judgment of Pharaoh (value 1), Angel O7 on either side; spell/trap cards: Cold Wave, Sasuke Samurai #2 player markers, Judgment of Pharaoh (value 2), Ancient Gear Drill, Light Barrier on the card;
- not during a chain build (`prev == 0`): Prohibition (`duel_effects_is_slot_prohibited` / `_is_card_prohibited`), Goblin of Greed with a discard cost, a draw effect when the player(s) it makes draw cannot draw (`0x09bf5890` gives 1 = self, 2 = opponent, 3 = both);
- spells: Spell Canceller, Talisman of Spell Sealing (`count_active_card`); traps: any Jinzo not protected by Amplifier, Jinzo - Lord, Talisman of Trap Sealing, Triangle Ecstasy Spark;
- spells and traps: Ancient Gear Golem (player marker pointing to an active Golem), Penalty Game!, Whirlwind Weasel, The Wicked Avatar player markers, an opponent's Great Shogun Shien or `0x1f13` that already saw an activation (its own marker or `0x161a`), a Xing Zhen Hu link on the card, Sanguine Swamp, a Cursed Fig marker;
- spells: Clear World with a WIND monster (`count_face_up_monsters_by_attribute(side, 6)`), Anti-Spell Fragrance link, Sonic Jammer, Fairy of the Spring, Mechanical Hound (empty hand), Invader of Darkness (Quick-Play), Linear Accelerator Cannon, Sage of Silence, Cursed Seal of the Forbidden Spell (marker with the card id), Field Barrier (field spells), Secret Village of the Spellcasters;
- traps: a link of `0x182f`–`0x1832` (Eagle Eye, Creeping Doom Manta …) in the current chain, Forced Ceasefire, the opponent's Pitch-Black Warwolf / Mirage Dragon during the Battle Phase (`0x09e2d1e8 == 3`), `0x19bb`, Sage of Stillness.

## Restrictions and locks

| Address | Name | Signature | Behaviour | Conf. |
| --- | --- | --- | --- | --- |
| `0x09bea7a8` | `duel_core_check_attack_restrictions` | `bool (side, slot, declaring)` | Called last by `duel_core_can_monster_attack`; returns 0 when an attack lock applies: Prohibition; Ultimate Tyranno's partner rule; links of Ekibyo Drakmord, Mask of the Accursed, Flint (unless `0x1c25` is on the slot), Spellbinding Circle, Shadow Spell, Nightmare Wheel; Wall of Revealing Light (ATK ≥ the paid LP), Nightmare's Steelcage on either side; Vengeful Bog Spirit (turn of summon); Gravity Bind (Level 4+); The Dark Door (only one attacker); Omega Goggles; ~40 card markers and player markers (Electric Lizard, Level Modulation, Diffusion Wave-Motion's restriction …); with `declaring`: Swords of Revealing Light of the opponent, Array of Revealing Light (declared Type), Messenger of Peace (ATK ≥ 1,500), Paralyzing Potion link, Gora Turtle (ATK ≥ 1,900), The Regulation of Tribe … Each card is tested through `duel_core_count_active_card_affecting` so the monster's immunity words apply. | H (structure), M (individual cards) |
| `0x09bea184` | `duel_core_has_no_attacks_left` | `bool (side, slot)` | Slot flag bit 22 = "has attacked"; if set, per-card rules decide whether another attack is allowed (Diffusion Wave-Motion player marker, Ultimate Tyranno's counter, extra attacks counted by markers `0x1505`, `0x18a6`/`0x195b`, `0x19c1`, `0x186c`; Black Luster Soldier - Envoy kind-4 marker `0x16cb`). True = it cannot attack again. | M |
| `0x09bf8388` | `duel_core_count_active_card_affecting` | `int (card, side, immunity_mask)` | Active copies of `card` on the sides whose bit is clear in `mask` (bit 0 own side, bit 1 opponent's; the monster's immunity word); mask 0 = both sides. | H |
| `0x09bf91d8` | `duel_core_count_active_timed_cards` | `int (side, card)` | Active copies in zones 5–10 that are still within their turn limit (`duel_core_is_within_turn_limit`): Swords of Revealing Light, Nightmare's Steelcage. | H |
| `0x09befdbc` | `duel_core_is_within_turn_limit` | `bool (side, slot)` | `BOOT 0x088661a4(card)` = the card's duration in turns (> 0); true while the turn count (`duel_core_get_turn_count`) is below it. | M |
| `0x09befbc0` | `duel_core_get_turn_count` | `int (side, slot)` | `u16` slot word for timed cards (−1 when the card has no duration, the count reached it, or a card-specific condition fails: Spellbinding-type links, Burning Land …). | M |
| `0x09c1ab2c` | `duel_core_post_advance_turn_count` | `bool (side, slot, reset)` | Posts command `0x3a (slot, reset)` for a timed card. | M |
| `0x09bf93c0` | `duel_core_count_active_cards_value_at_least` | `int (side, card, min)` | Active copies in zones 5–10 whose slot word ≥ `min` (Wall of Revealing Light: LP paid). | H |
| `0x09bf92b0` | `duel_core_count_active_cards_with_value` | `int (side, card, value)` | Active copies whose slot word equals `value` (declared Type/name: The Regulation of Tribe, Angel O7 …). | H |
| `0x09c0c330` | `duel_core_can_set_face_down` | `bool (side)` | False under Light of Intervention, a Searchlightman player marker, the opponent's Dark Simorgh, or a Judgment of Pharaoh marker (value 1); also in duel mode `0x09e02cac == 6`. Used by Book of Moon-type effects. | H |
| `0x09bfd224` | `duel_core_is_field_spell` | `bool (card)` | `0x09e2bbc8` (the active field spell id) equals `card`; Umi (`0x10f4`) also matches A Legendary Ocean (`0x150b`). | H |
| `0x09dc1354` | `duel_core_is_attacking_monster` | `bool (side, slot)` | The slot holds the attacker of the current attack (instance and generation of the attacker's battle record, `battle.md`). | H |

Player-wide "this turn" locks (Waboku: no battle damage, Threatening Roar: no attack) are kind-1 records on slot 11 (`duel_effects_resolve_add_player_marker`), read by the battle code with `duel_core_slot_has_effect(side, 11, card)`.

## Battle position and face

| Address | Name | Signature | Behaviour | Posts | Examples | Conf. |
| --- | --- | --- | --- | --- | --- | --- |
| `0x09c164b8` | `duel_effects_change_position` | `bool (link *ctx, side, slot, flip, a5)` | Unless unaffected: `duel_core_change_position(side, slot, flip, a5, ctx card, side != controller)`. | `0x33` | 25 handlers / 71 cards | H |
| `0x09c790f4` | `duel_effects_resolve_change_position` | `int (link *ctx)` | For each valid target, change its position (Aqua Spirit-type cards first set slot flag 21); `0x09e28f64` = 0 if any failed. Mode 2 for `0x1953`, `0x1954`, `0x1f1a`. | `0x33` | Stop Defense and 4 others | H |
| `0x09c16cc8` | `duel_effects_set_face_down` | `void (link *ctx, side, slot)` | If `duel_core_can_set_face_down(controller)` and the slot is affected: a face-up non-token monster in Attack Position → `change_position(…, 1, …)`, in Defense Position → `duel_core_flip_card_face(…, 0, …)` (turned face-down); a token or face-down monster in Attack Position → `change_position(…, 0, …)`. | `0x33`/`0x34` | Book of Moon (8 callers / 37 cards) | M |
| `0x09c15e8c` | `duel_core_flip_card_face` | `void (side, slot, flip_trigger, card, by_opponent)` | Turns a card face-up or face-down (command `0x34`), unless the card is unaffected by `card`'s type. Nothing happens while slot flag bit 2 is set. Turning face-up: the card's Flip trigger is queued when `0 < flip_trigger ≤ BOOT 0x08863438(card)`, per-card side effects (Worm Gurus slot flag 7, markers `0x1174`, `0x1b67`), timing event `0x0c`; turning face-down: timing event 9. | `0x34` | | H |
| `0x09c15e64` | `duel_effects_flip_card_face` | `void (link *ctx, side, slot, flip_trigger)` | Wrapper with `card = ctx id`, `by_opponent = side != controller`. Swords of Revealing Light flips every face-down monster of the opponent. | `0x34` | 11 handlers | H |

## Coin tosses and dice

Random effects run through the **pending-action** slot at `0x09e2d2e0` (H): `+0` active, `+4` player (`0x09e2d2e4`), `+8` type (`0x09e2d2e8`), `+0xc` sub-step, `+0x10`/`+0x12` arguments, results at `0x09e2d2fa` and `0x09e2d2fc`. About 30 small posters set the type (all write `0x09e2d2e8`; `0x09c0ed4c`–`0x09c10168`); `duel_core_run_pending_action` dispatches. In a link duel the remote player's request is mirrored with message `0x1e` and the results with `0x1f`.

| Type | Processor | Meaning |
| --- | --- | --- |
| 1, 2 | `0x09c103e0` | Discard/send chosen hand cards (count, flags) |
| 3, 4 | `0x09c10798` | Random hand card to the Graveyard (3: discard) |
| 5 … `0x10`, `0x14`, `0x15` | various | Other hand/deck actions (not read) |
| `0x0c` | inline | Negate every link of the chain that can be negated |
| `0x11` | `duel_core_run_effect_battle` | Battle by effect |
| `0x12` | `duel_core_action_coin_toss` | Coin toss |
| `0x13` | `duel_core_action_dice_roll` | Dice roll |

| Address | Name | Signature | Behaviour | Posts | Examples | Conf. |
| --- | --- | --- | --- | --- | --- | --- |
| `0x09c0fe60` | `duel_core_request_coin_toss` | `void (side, slot, card, count, call)` | Type `0x12`, argument `slot | (count | call << 4) << 8`. | — | Time Wizard and other coin cards (20 handlers / 34 cards) | H |
| `0x09c0ff50` | `duel_core_request_die_roll` | `void (side, slot, card)` | Type `0x13` with one die. | — | Graceful Dice, Skull Dice (11 handlers) | H |
| `0x09c10010` | `duel_core_request_dice_rolls` | `void (side, slot, card, count)` | Type `0x13` with `count` dice (Dice Jar rolls one per player). | — | Dice Jar | H |
| `0x09dc7a88` | `duel_core_ask_coin_call` | `void (side, card, message)` | Human: UI event `0x36 (9, message)`; CPU: `0x09e2d248 = 0x09d9f434()` (the AI's call). The answer is read from `0x09e2d248`. | — | Time Wizard (11 handlers) | M |
| `0x09c0decc` | `duel_core_action_coin_toss` | `int ()` | Light Barrier (`0x1dc8`) lets its owner choose the result; otherwise `count` coins from `duel_core_random(2)` packed as bits in `0x09e2d2fa`, shown with command `0x5d`; `0x09e2d2fc` = number of coins equal to the call. Second Coin Toss (`0x150f`) offers one retry per turn; Lucky Chance (`0x1de3`) reacts to a single coin. | `0x5d`, `0x08` | | H |
| `0x09c0e56c` | `duel_core_action_dice_roll` | `int ()` | `n` dice `1 + duel_core_random(6)` into `0x09e2d2fa + 2·i`, each shown with command `0x5e`; Dice Re-Roll (`0x16a5`) may re-roll once; Needle Wall stops on 6, Dice Jar on a tie. | `0x5e` | | H |
| `0x09c0e8b8` | `duel_core_run_pending_action` | `int ()` | Dispatcher above; returns 1 when idle or done. | | | H |
| `0x09dca478` | `duel_core_random_raw` | `int ()` | Advances the duel LCG (`0x09e2d1cc`) and returns its upper 15 bits; called before posting coin/dice requests. | | | M |
| `0x09c0fdd4` | `duel_core_request_effect_battle` | `void (a, b)` | Type `0x11` for the turn player. | | 9 handlers | M |

Handler pattern (Graceful Dice, Dice Jar, Time Wizard): sub-step `0x80` posts the request and returns `0x7f`; the handler is called again in step `0x7f` once the action is done and reads `0x09e2d2fa`/`0x09e2d2fc`. Graceful Dice then attaches a kind-2 record with value `die × 100` to each monster it affects.

## Counting predicates

The conditions and the stat chains count cards with these helpers (resolves part of the open question in `stat-modifiers.md`). "Face-up" means slot `+0x08` ≠ 0; slot flag bit 3 excludes a card (effect-less / not yet usable; bit 1 or 3 for spells and traps).

| Address | Name | Signature | Counts | Conf. |
| --- | --- | --- | --- | --- |
| `0x09bf9c8c` | `duel_core_count_monsters` | `int (side)` | Occupied monster zones without flag bit 3 (152 callers). | H |
| `0x09bf9c2c` | `duel_core_count_field_cards` | `int (side)` | The same over zones 0–10. | H |
| `0x09bf9578` | `duel_core_count_face_up_monsters_by_race` | `int (side, race)` | Current Type (`duel_core_get_race`). | H |
| `0x09bf94a0` | `duel_core_count_face_up_monsters_by_race_except` | `int (side, race, except_slot)` | Same, skipping one slot. | H |
| `0x09bf9720` | `duel_core_count_face_up_monsters_by_attribute` | `int (side, attribute)` | `duel_core_monster_has_attribute`. | H |
| `0x09c0b8f4` | `duel_core_monster_has_attribute` | `bool (side, slot, attribute)` | Current Attribute bit, with the extra attributes of Sphere of Chaos-type cards (`0x1e9e`, `0x1e5a`, `0x1aa5`, `0x19ef`, `0x18c7`) when their effect is active (46 callers). | H |
| `0x09bf9da8` | `duel_core_count_monsters_matching` | `int (side, predicate, except_name, face_up_only)` | Monsters whose name id passes `predicate(name)`. | H |
| `0x09bfa330` | `duel_core_count_spell_traps_matching` | `int (side, predicate)` | Face-up active spells/traps in zones 5–9. | H |
| `0x09bf8e48` | `duel_core_count_face_up_named` | `int (side, card)` | Face-up active cards with that name, in the zones of the card's kind. | H |
| `0x09bf7d7c` | `duel_core_is_face_up_card_at` | `bool (side, slot, card)` | Slot card id = `card`, face-up, flags 1/3 clear, not disabled in `0x09e2bba8`. | H |
| `0x09c01cb8` | `duel_core_count_graveyard_by_race` | `int (side, race)` | Graveyard cards (list at player `+0x55c`, count `+0x14`) whose Type is `race` (`duel_core_get_off_field_race`). | H |
| `0x09c02c30` | `duel_core_get_off_field_race` | `int (card)` | Card data Type, overridden for monsters by Zombie World (Zombie) and Declaration of Rebirth (the declared Type, the newer of the two wins). | M |
| `0x09bf87a8` | `duel_core_get_active_card_timestamp` | `int (side, card, newest)` | Placement serial of the oldest (or newest) active copy; used for Skill Drain-type ordering. | M |
| `0x09bf7708` | `duel_effects_link_targets_one_monster` | `bool (link *ctx)` | The link has exactly one target and it is a monster zone (Counter-trap style negation checks). | H |

## Record kinds observed at the call sites

Constants loaded into the `kind` argument of `duel_core_post_add_marker` (282 calls), `duel_core_attach_effect` (159) and `duel_effects_attach_effect_to_slot` (44) show that the argument is the whole record byte `+2`: low nibble kind, high nibble the initial turn counter (`0x12`, `0x22`, `0x16`, `0x17`, `0x21`; H). `duel_core_add_counters` builds `0x10 | 2` or `0x20 | 2` depending on whether it is the controller's turn, i.e. an effect that must survive one more turn change. See `stat-modifiers.md` for the resulting reading of kinds 1–5.

## Open questions

- Kind 1 vs kind 2: both expire identically and the stat builder treats them alike; kind 1 dominates player-wide flags (Waboku, Asura Priest, Berserker Soul), kind 2 card effects until the End Phase (Shrink, Limiter Removal, `0xfb6`). Find a reader that distinguishes them.
- Command codes `0x39` and `0x3b` for the handlers `0x09db7540` and `0x09db7620` are inferred from the posters, not from the jump table `0x09e00944`; check the table entries.
- `BOOT.BIN` predicates `0x088664fc` (counter type 1), `0x088661a4` (turn duration), `0x08863438` (Flip threshold), `0x0885fb5c` (name match), `0x0885fef0` / `0x0885ff3c` (monster / spell tests) are used but not named.
- The remaining pending-action types (5–10, `0x0d`–`0x10`, `0x14`, `0x15`) and their posters.
- `duel_core_can_take_effect_damage`: the exact meaning of the second argument.
- Per-card meanings in `duel_core_check_attack_restrictions` and `duel_effects_update_negated_slots` should be extracted as tables like the other compare chains; confirm the Skill Drain ordering rule in PPSSPP.
