# Duel AI helper vocabulary and shared handlers

Companion to `ai.md` (architecture) and `docs/formats/ai-tables.md` (the priority tables). This document names the queries that the per-card AI handlers are built from, names every handler that at least three table entries share, and sorts the handlers into behaviour classes. All addresses are runtime addresses in `gmodule/rel_duel_eng.prx` (base `0x09be1400`).

Basis: Ghidra decompilation (read-only copy of the project, `Decompile.java`) of the 100 most shared callees of the 677 AI handlers and of the 76 handlers used by three or more entries; callee sharing measured with `tools/effect_classify.py` (depth 1); table membership and the card names of the members (`tools/ai_tables.py list --cardinfo`, kept under `extracted/`), which act as a cross-check: a handler whose code tests "is an equip target strong" and whose members are all equip spells is named for that. Nothing was traced in PPSSPP. Every address named here starts a function in Ghidra (`getFunctionAt` in the decompilation runs, and a row in `re/functions.csv`).

Conventions used below: `ctx` is a 24-byte chain link (`chain.md`); its controller is `side ^ switched`; "own side" is `ctx +2 bit 0`. A **slot mask** has bit `side × 16 + slot` for slots 0–10. Handlers return an `int`; `ai_evaluate_activation` accepts at ≥ 1 (≥ 2 for hand cards under `0x09e28010 & 0x100`), so 0 and −1 both mean "not now".

## Helper vocabulary

### Targets (what the effect could hit)

| Address | Name | What it does | Conf. |
| --- | --- | --- | --- |
| `0x09ce96bc` | `ai_get_target_mask(ctx)` | Calls the target filter of the card's effect record (record `+8`) on every enabled slot of both sides (this is `0x09ce3244`, a duel_effects routine), then `ai_filter_target_mask`. Most shared AI callee: 140 handlers. | H |
| `0x09ce93fc` | `ai_filter_target_mask(ctx, mask)` | `mask = −1` → every occupied slot that is not disabled; then, only during AI evaluation (`0x09e28f80 < 0`) and for negatable effects, removes slots the per-card check `0x09ce82dc` (4,384 bytes, not read) rejects; Widespread Ruin keeps only the highest-ATK monsters. | H (shape) |
| `0x09ce96f4` | `ai_get_target_mask_with_filter(ctx, filter)` | Same with an explicit filter (`duel_effects_collect_slot_mask`). | H |
| `0x09ce9ad0` | `ai_count_targets_on_side(ctx, side)` | Population count of the mask on one side. 30 handlers. | H |
| `0x09ce9bf0` | `ai_is_valid_target(ctx, side, slot)` | Record filter (`duel_effects_call_handler_08`) and `0x09ce82dc` both accept. | H |
| `0x09cf6358` | `ai_choose_slot_by_card(ctx, side, mask, flag)` | 5,980-byte per-card chooser; returns a slot, or slot + 5 for a "preferred" choice. | L |
| `0x09cf7ab4`, `0x09cf7b44` | `ai_choose_slot_for_ctx_raw`, `ai_choose_slot_for_ctx(ctx, side, exclude, flag)` | Target mask minus `exclude`, then `ai_choose_slot_by_card`; the second folds slot + 5 back to the slot. | M |
| `0x09d64e54` | `ai_choose_cost_by_card(ctx, …, card, mask, flag)` | 9,704-byte chooser of an **own** card. Its users are cards whose cost is a Tribute, discard or send (Metamorphosis, Burst Breath, Horn of Heaven, Golden Flying Fish), so it is read as the cost chooser. | M |
| `0x09d6743c`, `0x09d64e30` | `ai_choose_cost_as_side(ctx, view, card, mask, flag)`, `ai_choose_cost_for_current_link(view, card, mask, flag)` | Run it with the view side `0x09e02ffa` switched; the second uses the current link `0x09e28e44`. | M |
| `0x09d6929c`, `0x09d6a89c` | `ai_choose_hand_card_by_card`, `ai_choose_hand_card_as_side(view, card, flag)` | 5,632-byte chooser by card id that ends in the hand chooser; users summon or banish from the hand (Hidden Soldiers, Elemental Absorber, Seed of Deception); `ai_evaluate_activation` uses it for card `0x142a`. | L |
| `0x09cf9c8c` | `ai_is_valuable_effect_card(side, slot, card, flag)` | True for a face-up, visible card with an active effect from a list of about 30 continuous "lock" cards (Messenger of Peace, Robbin' Goblin, Umi …), some only while rule flag `0x09e03070 & 0x80` is clear. | M |
| `0x09cfa11c` | `ai_count_valuable_effect_targets(ctx, side)` | Monster zones of `side` that are valid targets and `ai_is_valuable_effect_card`. | M |

### What the AI may see

| Address | Name | What it does | Conf. |
| --- | --- | --- | --- |
| `0x09ce43ec` | `ai_mask_hidden_card_id(side, slot, card)` | Returns `card` unless the slot is face-down and the AI is not viewing its own side; then a placeholder id: `0x16a7` for a spell/trap zone, `0x10f4` for the field zone, and for a monster a stand-in that depends on the level (< 5, 5–6, ≥ 7) and on the viewer's LP (≥ 1,000 / ≥ 2,500). **The AI does not read face-down cards.** | H |
| `0x09ce47a0` | `ai_get_visible_card_id(side, slot)` | Masked `duel_core_get_slot_card_id`. 55 handlers; also used by `ai_try_table_entry` to find the card on the field. | H |
| `0x09ce4728`, `0x09ce4760` | `ai_get_visible_raw_card_id`, `ai_get_visible_name_id` | Same on the raw slot id and on the name id. | H |
| `0x09ce48d0` | `ai_is_slot_face_up(side, slot)` | Occupied and face-up. | H |
| `0x09cea3b0` | `ai_get_visible_stats(side, slot, &atk, &def)` | Own side: real stats with the card temporarily face-up; other side: estimate `0x09ce9edc`. | H |
| `0x09cea360`, `0x09cea388`, `0x09cea2fc` | `ai_get_visible_atk`, `ai_get_visible_def`, `ai_get_visible_battle_stat` | The last returns ATK in Attack Position, DEF otherwise. | H |
| `0x09ceb2a0` | `ai_get_best_attacker_atk(side, exclude, mode)` | Highest visible ATK among monsters that can attack. | M |
| `0x09cf5c3c` | `ai_get_best_monster_stats(side, &a, &b, face_up_only)` | Best monster's visible stats; used by `ai_eval_battle_dominance`. | M |

### Simulation

| Address | Name | What it does | Conf. |
| --- | --- | --- | --- |
| `0x09ce47e0` | `ai_sim_set_slot_card(side, slot, card)` | Writes a card id into a slot and sets `0x09e03070 |= 0x20` ("dominance cache stale", read by `ai_get_battle_dominance`). | H |
| `0x09ce483c` | `ai_sim_clear_slot_card(side, slot)` | Removes it, same flag. | H |
| `0x09d30294` | `ai_build_chain_context(ctx, arg, side, location, index, switched)` | Builds a link for a card in a field slot or list (hand, extra deck, deck, Graveyard, banished), with the visible card id. | H |

### Battle

| Address | Name | What it does | Conf. |
| --- | --- | --- | --- |
| `0x09d37990` | `ai_eval_dominance_change(side, mask, simulate, base)` | Dominance without the masked cards minus the current value. Used to ask "is removing these cards worth it". | H |
| `0x09d374ec` | `ai_get_plain_battle_dominance(side)` | Cached non-simulated value (`+2` of the board block). | H |
| `0x09d16c0c` | `ai_get_planned_attacker(side, slot)` | Plans and returns the chosen attacker. | H |
| `0x09d1c8e0` | `ai_plan_get_attack_entry(plan, slot)` | Attack entry of a monster in a plan (`ai.md`, battle plan `+0x00`). | M |
| `0x09cfc178` | `ai_can_attack_now(side, slot)` | Face-up, attacks left, LP mode ≠ 9, `ai_can_slot_attack`. | M |
| `0x09d3a7f8` | `ai_can_slot_attack(side, slot)` | Attack restrictions pass and, in Defense Position, the monster can change position. | M |
| `0x09d30c74` | `ai_is_lethal_attack_threat(side)` | The opponent can battle, has at least as many monsters plus one, none of ours is a stopper (`0x09cf8de4`), and an opponent attacker has ATK ≥ our LP. | M |
| `0x09d39ba8` | `ai_can_normal_summon_now(side)` | Normal Summon available and the board view's slack is positive. | M |

### Life Points

| Address | Name | What it does | Conf. |
| --- | --- | --- | --- |
| `0x09d3908c` | `ai_estimate_lp_change(ctx, out[2], mode, flags)` | LP change of both sides if the effect resolves (1,572 bytes; already used by `ai_evaluate_activation`). | M |
| `0x09d6c1c0` | `ai_eval_damage_effect(ctx, extra, &damage)` | 0 = no damage, the AI would die, the opponent is immune, or Brutal Potion is waiting; 1 = lethal; otherwise 1 if `ai_is_normal_spell_in_graveyard` else −1 ("hold non-lethal burn"). | H |
| `0x09d31e50` | `ai_can_damage_opponent(side)` | Not `0x09c2796c(opponent)` (damage turned into LP gain: Rainbow Life marker, Prime Material Dragon without Bad Reaction to Simochi / Nurse Reficule). | M |
| `0x09d31da0` | `ai_rate_lp_gain(side, card)` | 0 when LP gain is reversed, 2 while Fire Princess is active, 1 otherwise (with Fire Princess in hand or deck only for monsters and continuous cards). | M |
| `0x09cfc2c0` | `ai_get_lp_cost(ctx)` | `duel_effects_get_lp_cost` for a spell/trap activation, else 0. | H |
| `0x09d7cb54`, `0x09d7ccc4`, `0x09d7ceec` | `ai_eval_damage_per_tribute`, `ai_eval_tribute_cost_for_damage`, `ai_eval_damage_combo` | Cannon-Soldier evaluators: lethal in n Tributes without killing the AI; Tributes that do not hurt the battle plan (`ai_eval_dominance_change ≥ 0`); a specific loop combo (Spell Economics, Dimension Fusion, Dark Magician of Chaos). | M/M/L |

### Hand, deck and candidates

| Address | Name | What it does | Conf. |
| --- | --- | --- | --- |
| `0x09d48910` | `ai_count_acceptable_candidates(side, card, param)` | Candidates the effect would offer (`duel_effects_count_candidates`) that `ai_reject_candidate` keeps. 37 handlers. | H |
| `0x09d48b4c` | `ai_reject_candidate(card, index)` | 4,104-byte per-card veto on candidate `index` (e.g. do not search a card already held). | M |
| `0x09ce4ba8`, `0x09ce4c54` | `ai_push_candidate_card(card)`, `ai_pop_candidate_card()` | Stack of (card, threat class) pairs at `0x09e03004`, depth `0x09e03024`. | H |
| `0x09d484d8`, `0x09d48720`, `0x09d487ec` | `ai_simulate_candidate_choice`, `ai_try_choose_candidates`, `ai_choose_candidate_index` | Build the candidate list (`duel_effects_build_candidate_list`) and let the AI pick (kinds 6 and `0x4a` go through `0x09d440d8`); the last returns the picked index or −1. | M |
| `0x09d6b7a0` | `ai_can_choose_candidates_for_ctx(ctx, kind)` | The pick succeeds and the picked candidates are not rejected. | M |
| `0x09cfaa0c` | `ai_choose_discard(side, exclude_instance, flag)` | Picks a hand card to send to the Graveyard (`ai_choose_hand_card_to_send`, `0x09d4cb84`, with an always-true filter) and refuses it when `0x09cf11ac` marks it as worth keeping. | M |
| `0x09cfa5f8` | `ai_has_card_in_hand_or_field(side, card)` | Hand count (`0x09c033a8`) or field count (`0x09bf98b8`, name match `BOOT 0x0885fb5c`). | H |
| `0x09cfa6e8` | `ai_owns_card(side, card)` | Same plus deck (`0x09bf1924`) and Graveyard (`0x09c014ac`). | H |
| `0x09d373d8` | `ai_would_deck_out(side, side2, draws)` | `draws` plus the expected extra draws (`0x09d3727c`) reach the deck size. | M |
| `0x09d6d5f0` | `ai_can_afford_draw(ctx, deck_margin, hand_after)` | Not decking out, and the hand after drawing fits the limit (`0x09d37b70`). | M |
| `0x09d6ce5c` | `ai_can_special_summon_card(ctx, …)` | Checks the summon-table entry of the card (`duel_effects_find_token_entry`) and the zones. | L |

### State and chain

| Address | Name | What it does | Conf. |
| --- | --- | --- | --- |
| `0x09d6b93c` | `ai_is_card_count_below(ctx, limit, any_side)` | `limit` minus links already activating this card on the chain; then active copies (own side, or both) must be fewer. | H |
| `0x09d8d218` | `ai_is_normal_spell_in_graveyard(ctx)` | ctx location `0x0e`, spell (`BOOT 0x0885ff3c`) with icon 0. 71 handlers use it as a shortcut to "yes"; hypothesis (M): it marks an activation that is already committed (a resolving Normal Spell), so prompts during resolution are answered yes. | H (test), M (meaning) |
| `0x09d8f1d0` | `ai_is_past_summon_step()` | Main-phase AI step > 1. | H |
| `0x09d6d1d8`, `0x09d6d33c` | `ai_is_card_threatened_by_link(ctx, link)`, `ai_is_card_threatened_by_chain(ctx, link)` | A link targets ctx's slot, or an untargeted removal (`0x09bf2fbc`, `0x09bf3c34`) can reach it; the second checks every link up to `link`. | H |
| `0x09d6c5b0` | `ai_is_not_applied_to_opponent(ctx)` | The opponent's player slot has no marker of this card (viruses). | H |

Not renamed (other groups, left to the duel_core/duel_effects work): `0x09c033a8` (count hand cards matching a name), `0x09bf98b8` (field), `0x09bf1924` (deck), `0x09c014ac` (Graveyard), `0x09bf3c34` and `0x09bf2fbc` (classify a link as a threat: return values 2–5), `0x09ce3244` (target mask from the record filter), `0x09ce3b3c` (count filter-valid slots), `0x09bee688` (population count), `0x09bfc51c` (count cards by face).

## Shared handlers

Every handler used by at least three table entries now has a name (77 handlers incl. `ai_cond_always`, `ai_cond_has_target`, 1,163 of the 1,828 entries). Members are given as a few examples. Conf. M unless noted.

| Address | Name | Entries (tables) | Decision encoded | Examples |
| --- | --- | --- | --- | --- |
| `0x09d22924` | `ai_handler_on_attack_declared_event` | 143 (R1) | Only for event code `0x12`/`0x13` (`0x13` = attack declared); 13,932-byte per-card chain on the attacker. | Magic Cylinder, Sakuretsu Armor |
| `0x09d262c8` | `ai_handler_on_damage_step_event` | 36 (R2) | Only for event `0x14` (start of the Damage Step); per-card checks on the battle. | Mirror Wall, Reinforcements |
| `0x09d1f5e8` | `ai_handler_on_opponent_summon_event` | 3 | A queued summon event `0x20`–`0x22` by the opponent (not Ultimate Offering's id `0x1be9` being sendable). | Royal Oppression |
| `0x09d6c67c` | `ai_handler_equip_strong_monster` | 80 (D 61, B 18) | After summoning: own equip target exists and is preferred, listed, or has ATK > 1,299. | Axe of Despair, Lightsworn Sabre |
| `0x09d6cadc` | `ai_handler_equip_if_target` | 17 | Same gate, any own target. | Rod of the Mind's Eye |
| `0x09d6e110` | `ai_handler_ritual_summon` | 29 (D) | A ritual monster for the spell is in hand and enough Tributes (simulated by clearing slots) exist. | Black Luster Ritual |
| `0x09d75278` | `ai_handler_revive_monster` | 18 | Per-card revival check on the best Graveyard monster. | Monster Reborn, Call of the Haunted |
| `0x09d75b38` | `ai_handler_summon_by_sending_own_monster` | 8 | Revival check plus the cost card must be weaker than what is summoned. | Lonefire Blossom |
| `0x09d7efa0` | `ai_handler_union_equip` | 18 | Union monsters: not in a chain event, no union link yet, plan comparison. | Y-Dragon Head |
| `0x09d7c780` | `ai_handler_fusion_summon` | 13 | No Chimeratech Overdragon / F.G.D. plan; a candidate can be chosen; Fusion Gate only into a free field zone; Power Bond only if battle is possible. | Polymerization |
| `0x09d6d19c` | `ai_handler_special_summon` | 9 | `ai_can_special_summon_card`. (L) | Contract with Exodia |
| `0x09d1cc5c` | `ai_handler_counter_harmful_link` | 28 (T3) | Respond only to a link of the opponent that is harmful and not aimed only at the Graveyard. | Trap Jammer, Armor Break |
| `0x09d1cf74` | `ai_handler_negate_harmful_link` | 10 (T3) | Same, weighted by how many own cards the link would hit. | Magic Jammer, Seven Tools |
| `0x09d278c4` | `ai_handler_respond_to_opponent_link` | 5 (T3) | Any link that is not the AI's own. | Ryu Senshi |
| `0x09d6d33c` | `ai_is_card_threatened_by_chain` | 12 (T3) | Chain the card when the chain is about to remove it. | Scapegoat, Waboku |
| `0x09d1cb80`, `0x09d1cc10` | `ai_handler_chain_if_threatened_own_target`, `…_has_target` | 9, 3 | Threatened and an own / any target exists. | Rush Recklessly; Shrink |
| `0x09d2a854` | `ai_handler_chain_negate_summon` | 7 | Negate a summon when a Tribute cost can be chosen and it pays off. | Horn of Heaven |
| `0x09d2c5ec` | `ai_handler_chain_destroy_activating_card` | 4 (T3) | Destroy the opponent's activating continuous/equip/field card when valuable. | Mystical Space Typhoon |
| `0x09d28b54`, `0x09d2cb3c` | `ai_handler_chain_use_targeted_card`, `…_use_targeted_own_monster` | 4, 3 (T3) | The link targets a card this effect can use (Tribute/cost) first. | Spiritual Art; Crop Circles |
| `0x09d2774c` | `ai_handler_chain_banish_targeted_grave_card` | 3 (T3) | The link targets a Graveyard card of the opponent. | D.D. Crow |
| `0x09d2b42c` | `ai_handler_chain_fizzle_by_face_down` | 3 (T3) | Turning the single target face-down makes the link's filter fail. | Book of Moon |
| `0x09d6c14c` | `ai_handler_gain_lp` | 21 | `ai_rate_lp_gain`; a continuous card answering a link is refused. | Dian Keto, Red Medicine |
| `0x09d6c3d0` | `ai_handler_burn` | 10 (A 9) | Lethal burn; non-lethal only with Dark Room of Nightmare active or none owned. | Hinotama, Ookazi |
| `0x09d2125c` | `ai_handler_burn_at_least_1000` | 4 | Lethal, or ≥ 1,000 damage. | Secret Barrel |
| `0x09d7d134`, `0x09d7d274`, `0x09d7d2dc` | `ai_handler_tribute_for_damage`, `…_combo`, `ai_handler_send_self_for_damage` | 9, 4, 5 | Tribute/send costs evaluated with the evaluators above. | Cannon Soldier; Mass Driver; Volcanic Queen |
| `0x09d1d6a4` | `ai_handler_stop_large_battle_damage` | 4 (T1) | Battle damage (link `+0x14`) ≥ LP, or ≥ 1,500 (800 for some). (H) | Kuriboh, Defense Draw |
| `0x09d6bb54` | `ai_handler_target_if_can_battle` | 14 | Battle Phase still possible and a target exists. | Enemy Controller |
| `0x09d77d7c` | `ai_handler_equip_opponent_if_behind` | 5 | Dominance < 0 and the opponent's chosen monster has ATK > 1,299. | Paralyzing Potion |
| `0x09d7274c` | `ai_handler_board_wipe_if_behind` | 4 | Opponent has targets and: lethal threat, or we have no monster and they have ≥ 2, or dominance < −2. Not after a summon this turn (player flag bit 17). | Dark Hole |
| `0x09d88214` | `ai_handler_stall_if_behind` | 4 (G) | Not on turn 0, no other staller active, dominance < 0. | Swords of Revealing Light |
| `0x09d1d24c` | `ai_handler_stop_winning_attacker` | 3 (T1) | Opponent attacker would win the battle (`0x09d30dc8`) or deal ≥ LP. (L) | Kazejin |
| `0x09d1f678` | `ai_handler_mass_removal_after_summon_if_behind` | 3 (T1) | Opponent summon events 6–8, dominance < −1, opponent has targets. | Torrential Tribute |
| `0x09d7acb4`, `0x09d7e3f0`, `0x09d81294` | `ai_handler_boost_if_can_attack`, `…_boost_self_before_attack`, `…_boost_if_plan_improves` | 3 each | Boost only a monster that can attack; the last simulates the boost and compares plans. | Thousand Energy; Karate Man; Bazoo |
| `0x09d7f5d8` | `ai_handler_banish_unless_attack_planned` | 3 | Removal effects of monsters that would lose their attack: only if the monster has no planned attack or the AI is behind. | Chaos Sorcerer |
| `0x09d7f9a4` | `ai_handler_remove_if_behind` | 3 | Opponent has targets and (behind, or valuable lock cards). | Dark Core |
| `0x09d709f0` | `ai_handler_swap_if_opponent_stronger` | 4 | Control swap when the opponent's best monster beats our worst. | Interdimensional Warp |
| `0x09d7347c` | `ai_handler_tribute_to_destroy_stronger` | 4 | Target better than the Tribute (or dominance does not drop). | Golden Flying Fish |
| `0x09d7423c`, `0x09d6c520` | `ai_handler_take_control`, `…_if_target` | 4, 3 | Control change allowed (rule flag `0x80` clear) and a target exists. | Brain Control; Alien Hypno |
| `0x09d1e1b8`, `0x09d6e85c`, `0x09d6ed0c` | `ai_handler_destroy_set_spell_trap`, `…_destroy_spell_trap`, `…_mass_spell_trap_removal` | 3 each | Rate spell/traps with `ai_rate_slot_threat` (`0x09cea488`, 3,608 bytes); mass removal when the opponent loses more. | Dust Tornado; Twister; Heavy Storm |
| `0x09d72c24` | `ai_handler_destroy_extreme_stat_monster` | 3 | The extreme-stat monster is the opponent's and worth it. | Fissure |
| `0x09d7ea90` | `ai_handler_board_wipe_effect` | 3 | Opponent has targets; then yes if this monster cannot attack, if its ATK ≥ the opponent's LP or the opponent has a face-down card, else only when dominance < 1. | Judgment Dragon |
| `0x09d6d3c4` | `ai_handler_draw_if_safe` | 11 | Draw count from the card; `ai_can_afford_draw`; some cards need 3 or 5 acceptable candidates. | Pot of Greed |
| `0x09d6e6d4` | `ai_handler_recycle_graveyard_and_draw` | 4 | `0x09c0d4c4` and draw check. | Pot of Avarice |
| `0x09d2db9c` | `ai_handler_virus_if_tribute_ok` | 3 | Not yet applied, a Tribute exists that does not hurt dominance. | Crush Card Virus |
| `0x09d7e31c` | `ai_handler_tribute_self_to_recover_monster` | 3 | ≥ 2 monsters and a better card to recover. (L) | Crimson Sentry |
| `0x09d28754`, `0x09d1cb48` | `ai_handler_in_own_standby_if_candidate`, `ai_handler_in_opponent_end_phase` | 3 each (T1) | Phase/turn timing (turn player `0x09e2d1d8`, phase `0x09e2d1e8` = 1 / 5). (H) | Call of the Haunted; Chain Burst |
| `0x09d878e8` | `ai_handler_set_face_down_once_per_turn` | 17 (G) | Slot has no marker `0x1f1b` (or rule flag `0x80`). | Swarm of Scarabs |
| `0x09d71688`, `0x09d71720` | `ai_handler_field_spell_if_not_active`, `…_if_zone_free` | 26, 12 | Field spell from the hand into an empty or face-down field zone (the first also: not already active). (H) | Wasteland; Necrovalley |
| `0x09d20584` | `ai_handler_reset_own_flip_monster` | 3 (T1) | Flip own Flip-effect monster down to re-use it, or protect a weak one. (L) | Book of Moon |
| `0x09d7fdf4` | `ai_cond_opponent_has_monster` | 3 | (H) | Guardian Ceal |
| `0x09d6b6c8`, `0x09d6b718` | `ai_cond_has_candidate`, `ai_cond_has_two_candidates` | 47, 8 | ≥ 1 / ≥ 2 acceptable candidates. (H) | Hero Signal; Salvage |
| `0x09d6b89c` | `ai_cond_can_choose_candidate` | 18 | `ai_can_choose_candidates_for_ctx(ctx, 6)`. | Return Soul |
| `0x09d6bb0c`, `0x09d6bbe8` | `ai_cond_has_cost`, `ai_cond_has_hand_choice` | 15, 3 | Cost / hand chooser returns a card. | Metamorphosis; Hidden Soldiers |
| `0x09d6bc18`, `0x09d6bfc4` | `ai_cond_can_discard`, `…_and_has_target` | 5, 5 | Committed or a discard exists (and a target). | XY-Dragon Cannon; Snipe Hunter |
| `0x09d6ba20`, `0x09d6ba2c`, `0x09d6ba38` | `ai_cond_no_active_copy`, `ai_cond_fewer_than_two_active_copies`, `ai_cond_no_active_copy_any_side` | 33, 7, 16 | Continuous cards that should not be doubled. (H) | Banner of Courage; Poison Chain; Imperial Iron Wall |
| `0x09d6b8bc`, `0x09d6b8e8`, `0x09d6b914` | `ai_cond_opponent_has_target`, `ai_cond_own_side_has_target`, `ai_cond_no_own_target` | 28, 6, 14 | Target availability per side; the last guards symmetric effects so they only hurt the opponent. (H) | Trap Hole; Common Soul; Acid Rain |

## Taxonomy and coverage

`tools/ai_tables.py <prx> classes --functions re/functions.csv --functions re/names-duel_eng.csv --summary` sorts every handler by its name (regexes in `CLASSES`, first match wins, on the name without its `ai_handler_`/`ai_cond_` prefix; a per-card name takes the class of its family or, for a variant, of the shared handler it extends) and counts table entries (pair tables + u16 lists = 1,828 entries, 677 handlers). Result now that every handler is named (the 77 shared ones of this document and the 600 per-card ones of `ai.md`, "Per-card handler families"):

| Class | Meaning | Handlers | Entries | Share | Of which shared (handlers / entries) |
| --- | --- | --- | --- | --- | --- |
| constant | always / never | 2 | 188 | 10.3 % | 2 / 188 |
| event | reacts to a queued timing event | 6 | 186 | 10.2 % | 3 / 182 |
| chain | responds to a chain link (threat, negation, use before loss) | 62 | 151 | 8.3 % | 12 / 91 |
| lp | LP thresholds (burn, LP gain, damage prevention) | 51 | 106 | 5.8 % | 7 / 57 |
| battle | battle dominance, attackers, battle plan | 101 | 148 | 8.1 % | 11 / 48 |
| summon | summon and equip enablers | 37 | 224 | 12.3 % | 8 / 192 |
| removal | removal or control change gated by value | 26 | 50 | 2.7 % | 9 / 30 |
| target | target availability | 74 | 210 | 11.5 % | 5 / 135 |
| limit | copies already active, once per turn | 30 | 102 | 5.6 % | 4 / 73 |
| phase | phase / turn timing | 20 | 25 | 1.4 % | 2 / 6 |
| resources | hand, deck, Graveyard, candidates, costs | 167 | 292 | 16.0 % | 10 / 117 |
| board | other board-state checks (field zone, monsters present) | 75 | 119 | 6.5 % | 4 / 44 |
| state | rule flags, ctx fields, committed activations | 26 | 27 | 1.5 % | 0 / 0 |

Reading: **63.6 % of all table entries are covered by the 77 shared handlers**; the 600 per-card handlers serve the other 36.4 % with one or two entries each and are grouped into 19 families plus 83 variants of shared handlers (`ai.md`). The classes are not exclusive in behaviour: almost every handler starts with a target or resource test, and the battle/dominance test (`ai_get_battle_dominance`, 86 handlers) is the most common second condition. The name-driven class is the *dominant* decision, which is what a port needs to choose an implementation.

Porting note: the shared vocabulary above is small (about 60 queries, plus the expected-stat estimates `ai_estimate_card_atk` / `ai_estimate_card_def` and the best-monster queries `ai_find_best_monster_slot` / `ai_get_best_monster_value` named with the families). A reimplementation can express every named handler as a predicate over these queries, and the per-card ones as family templates with the member's constants.

## Open questions

- Meaning of `ai_is_normal_spell_in_graveyard` in context (when does an AI-evaluated link sit in the Graveyard?): set a PPSSPP breakpoint on `0x09d8d218` returning 1.
- Event code `0x12` accepted by `ai_handler_on_attack_declared_event` besides `0x13`; R3's event `0x1b` (Mind Crush, `0x09d27348`).
- The per-card filters `0x09ce82dc` (target veto), `0x09d48b4c` (candidate veto), `0x09cf6358` (slot chooser), `0x09d64e54` (cost chooser), `0x09cea488` (slot threat rating), `0x09cf11ac` (keep-card check) are only skimmed; their compare chains are per-card AI knowledge like the handlers.
- Rule flag `0x09e03070 & 0x80`: blocks control-changing handlers but makes `ai_handler_set_face_down_once_per_turn` accept; its writer in `ai_analyze_board` is not identified.
- Marker `0x1f1b` (not a card id in the released list) tested by `ai_handler_set_face_down_once_per_turn`.
- `0x09d37b70` (hand-limit slack with Dark World Grimoire) and `0x09c0d4c4` (used by the Pot of Avarice group) are unnamed.
