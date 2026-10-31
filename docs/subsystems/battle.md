# Battle Phase, battle damage and Life Points (work package 4)

How `gmodule/rel_duel_eng.prx` (runtime base `0x09be1400`) runs an attack from declaration to the end of the Damage Step, how it resolves ATK against ATK/DEF, how Life Points change, and how the duel ends. The turn-level framing (phase enum, Battle step driver, command queue) is in `duel-phases.md`; player-block fields are in `duel_core.md`. All addresses are runtime addresses. Evidence is static (Ghidra decompilation of a read-only copy of the project); nothing here has been confirmed in PPSSPP yet. Card names are given only to identify the card ids that the code tests (from the maintainer's own card table, `tools/cardinfo.py`).

## Summary

- The Battle Phase is the 12-entry step table at `0x09e01dcc`. Steps 2–10 are one attack: declaration (2), declaration costs (3), the attack-declared window (4), start of the Damage Step (5), damage calculation (6), inflicting battle damage (7), after damage calculation (8), end of the Damage Step / destruction (9), end of the attack (10). Confidence: high for the order and the role of each step, medium for individual sub-steps.
- All the battle arithmetic lives in two functions that are shared with the AI's simulator: `duel_core_battle_compute_stats` (`0x09dc15c8`) builds two 0x48-byte **battle records** with the final ATK/DEF after every damage-step modifier, and `duel_core_battle_resolve` (`0x09dc5a4c`) compares them, sets "destroyed by battle" flags and writes up to two **damage records**. Confidence: high.
- Life Points are the `int` at player block `+0x00` (`0x09e2a528 + side × 0xb3c`). They are changed **only** by three engine commands: `0x23` gain, `0x24` loss, `0x25` set. Every LP change in the game (battle damage, effect damage, costs, gains) posts one of them. Confidence: high.
- The duel does not end at the moment LP reaches 0. `duel_core_check_duel_end` (`0x09dcb0ec`) is polled whenever the engine is idle and at chain/timing boundaries; it asks `duel_core_check_win` (`0x09dcae58`) for both sides, which tests "opponent LP == 0" among ten win conditions. Confidence: high.
- Timing events raised by `duel_core_raise_timing_event` are consumed in two ways: `duel_core_run_timing_windows` (`0x09ccc494`) opens a response window for the turn player and then the opponent whenever the queue is non-empty, and card activation conditions scan the queue (`0x09e28fa0[]`, `0x09e28fc0[]`) for the code they react to. Confidence: high for the window driver, medium for the per-card readers.

## Attack globals

| Address | Meaning | Basis / conf. |
| --- | --- | --- |
| `0x09e28620` | Attacking side | Set in Battle step 1; every step reads it. H |
| `0x09e28624` | Defending side (`1 − attacker`, written by step 2) | Step 2 first statement. H |
| `0x09e28628` | 1 = direct attack (target slot 5) | Set by step 2 when no target is needed; command `0x18`; `duel_core_cmd_declare_attack` sets it from `target ≥ 5`. H |
| `0x09e2862c` | 1 once the damage has been shown (command `0x16`) | `duel_core_cmd_show_battle_damage`. M |
| `0x09e28630` | Declaration costs done | Set by step 3, cleared for a second attack in step 10. M |
| `0x09e28634` | Effect-driven battle without Damage-Step windows | Set by `duel_core_run_effect_battle` when its third argument is non-zero; steps 5–7 skip timing events while it is set. M |
| `0x09e28638` | Replay flag (the attack is being re-declared after the opponent's field changed) | `duel_core_battle_check_replay`; step 2 then asks "continue the attack?" (prompt `0xdf`). H |
| `0x09e2863c` | Attacker's monster slot (0–4) | Step 1. H |
| `0x09e28640` | Target slot (0–4, 5 = the player) | Step 2 (`0x09e2d27c + 0x09e2d280` from the human's cursor, 5 for a direct attack). H |
| `0x09e28648` | Card id of an effect that "dealt the battle damage" for a follow-up check (Advanced Dark family) | Steps 6, 8. L |
| `0x09e28730` … `0x09e2875c` | Replay snapshot: attacker instance + 2-bit generation, the five defender monster instances + generations (12 words) | `duel_core_battle_snapshot_targets`; compared with `memcmp` (`0x30` bytes) by `duel_core_battle_check_replay`. H |

A monster instance is identified by its card-reference index (slot bytes `+1`–`+3`: `((u16 +2 & 0x7fff) >> 7) × 2 − bit 6 of +1`) plus the 2-bit generation in byte `+2` of its 6-byte entry in `0x09e2bbcc`. The engine compares both to notice that a monster left and came back (H for the formula; the meaning "generation" is an inference, M).

## Battle records (`0x09e28650 + side × 0x48`, indexed by player, not by role)

Filled by `duel_core_battle_compute_stats`; offsets relative to the record.

| Offset | Meaning | Conf. |
| --- | --- | --- |
| `+0x00`, `+0x04` | Side, slot (5 for the player in a direct attack) | H |
| `+0x08` | Battle position (slot `+0x06`; 0 = Attack Position) | H |
| `+0x0c`, `+0x10` | Card instance and its generation | H |
| `+0x14` | Name id the card is treated as (`duel_core_get_slot_name_id`, stat-block word 0; `stat-modifiers.md`) | M |
| `+0x18` | Effective card id (`duel_core_get_slot_card_id`, stat-block word 1) | H |
| `+0x1c`, `+0x20` | Original ATK / DEF (stat-block words 8/9), clamped at 0 | H |
| `+0x24` | Final ATK used by the damage calculation, clamped at 0 | H (compared in `duel_core_battle_resolve`; sent in command `0x15`, timing `0x0d`) |
| `+0x28` | Final DEF, clamped at 0 | H |
| `+0x2c`, `+0x30` | Current Type and current Level (stat-block words 2 and 5) | H |
| `+0x34` | Destroyed by battle | H |
| `+0x38` | Destruction handled by a card effect instead (Mystical Beast Serket, Thunder Nyan Nyan set it in step 9) | M |
| `+0x40` | Effect negation of this monster when it is destroyed by battle, from `duel_core_get_battle_destroyed_negation` (`0x09dc5150`): 0 none, 1 or 2 its effects are negated (see "Per-card branches"); command `0x20` sets slot byte `+0x36` bit 6 when > 0 | M (the card set is the "negate the effects of monsters destroyed by battle with this card" family; the difference between 1 and 2 is open) |
| `+0x44` | Monster still on the field at the end of the Damage Step | M |

Damage records follow at `0x09e286e0 + i × 0x14` (2 entries): `+0x00` amount, `+0x04` source side, `+0x08` source slot, `+0x0c` damaged player, `+0x10` damaged slot (5 = the player). `duel_core_battle_add_damage` fills the first free entry (H).

## The steps

`duel_core_run_battle_steps` calls `0x09e01dcc[0x09e2d220]`; a non-zero return advances the index and clears the sub-step `0x09e2d224`. Steps 0, 1 and 11 are described in `duel-phases.md`.

| # | Function | What it does |
| --- | --- | --- |
| 2 | `duel_core_battle_step_declare_attack(side)` `0x09dd2a6c` | Chooses the target. Sub-step 0: on a replay the CPU decides (`ai_battle_decide_attack`) or the human is asked (prompt `0xdf`). Sub-step 1: direct attack when `duel_core_can_attack_directly` (no blocking monster) or `duel_core_get_direct_attack_mode == 2` (effect that attacks directly); Ring of Magnetism forces its holder as target; Patrician of Darkness / Call of the Earthbound let the other player choose (sub-steps `0x0a`/`0x0b`); mode 1 asks "attack directly?" (prompt `0xe1`). Sub-step 3: human cursor (`0x09dce978(side, 0x0d, …)`, UI events `0x0b`, `8`); 4: reads the answer (`0x09e2d26c == 0x0b`) or returns to step 1. Sub-step 5 commits: command `0x17` (attack a monster: slot, `target << 8 | defender`) or `0x18` (direct attack, target 5). |
| 3 | `duel_core_battle_step_attack_costs()` `0x09dd3574` | If the attacker can no longer attack: command `0x19` (attack over) and back to step 1. Otherwise snapshots the targets, then pays "to declare an attack" costs: Gravekeeper's Servant (top card to the Graveyard), Toll (500 LP per attack, both sides' Spell/Trap Zones), Dark Elf / Machiners Force (1,000 LP), Toon monsters (500 LP), Jirai Gumo (coin toss; `duel_core_lose_lp(side, LP / 2)`), Insect Queen / Panther Warrior (Tribute, sub-steps 100/101). Then the replay check. |
| 4 | `duel_core_battle_step_attack_declared()` `0x09dd3bd4` | The attack-declared window. Sub-step 2: forced negations (Mirror Wall, Hero Barrier, Necro Gardna, Cyber Barrier Dragon) post command `0x1f` (attack negated → step 10). Sub-step 3: on the first declaration, "when this card attacks" monsters and White Veil, Advanced Dark, Rainbow Veil; `0x09c17ec4` registers attack triggers. Sub-step 4: raises timing event **`0x13` (attack declared)** while new events were queued (`0x09e28e40`), re-running the replay check each time. |
| 5 | `duel_core_battle_step_damage_start()` `0x09dd4530` | Start of the Damage Step. Sub-step 0: command `0x19` with `b = 1` (the monster has now attacked), new snapshot. Sub-step 1: Hero Spirit; "at the start of the Damage Step" triggers of attacker and target. Sub-step 2: if the attacker or the target changed, the attack ends (step 10); a face-down target is turned face-up (`0x09c15e8c`). Sub-step 3: `duel_core_battle_compute_stats_live(0)` and per-card Damage-Step effects (`0x09dd1c90`). Raises timing event **`0x14` (start of the Damage Step)**, argument `attacker | slot << 8 | (defender | target << 8) << 16`. |
| 6 | `duel_core_battle_step_damage_calc()` `0x09dd5454` | Sub-steps 0–1: per-card "during damage calculation" effects of attacker, then target. Sub-step 2: command `0x15` (show both monsters), stats with effects, timing event **`0x0d` (damage calculation)**, argument `attacker ATK | target ATK-or-DEF << 16`. Sub-step 3: replay check, final stats. Sub-steps 100–`0x73` and `0x480`: interrupts that need a selection (Telekinetic Shocker, Ancient City – Rainbow Ruins, Toon Kingdom, Advanced Dark). Sub-step 4: **`duel_core_battle_resolve_live(1)`** (the actual ATK/DEF comparison). Sub-step 5: command `0x16` (damage display: damage to each side, destroyed/position flags). Sub-step 6: command `0x20` for each monster destroyed by battle. |
| 7 | `duel_core_battle_step_inflict_damage()` `0x09dd7528` | Sub-step 0: timing event **`0x0e` (battle damage about to be inflicted)** once per non-zero damage record. Sub-step 2: "when this card inflicts battle damage" registrations, then **`duel_core_apply_battle_damage`** for both records; Gravekeeper's Vassal (battle damage becomes effect damage, `duel_core_inflict_card_damage`), Rainbow Life (gain instead), Reflect Bounder. |
| 8 | `duel_core_battle_step_after_damage_calc()` `0x09dd7ae4` | Not for direct attacks. Waits for pending work, then per-card "after damage calculation" effects of both monsters (trigger registration `0x09c2c578` with event `0x2a2`). |
| 9 | `duel_core_battle_step_damage_end()` `0x09dd82b4` | Refreshes `+0x44`; cards that replace destruction (Serket, Thunder Nyan Nyan, Great Dezard, Big Shield Gardna's position change); sub-step 2: `duel_core_request_battle_destruction()` hands the destroyed monsters to the pending-work function `0x09c232bc`, which sends them to the Graveyard and raises the "destroyed by battle" triggers. |
| 10 | `duel_core_battle_step_attack_end(side)` `0x09dd889c` | Sub-step 0: "after battle" effects (Cyber Ogre, Kaminote Blow, Big Shield Gardna, Swift Samurai Storm!, Spacegate counters). Sub-step 1: command `0x1c` (end of attack); Neko Mane King ends the turn (command `0x1a` with phase 5, then `0x0f`); Super Junior Confrontation and Last Turn leave the Battle Phase (index 11); Black Luster Soldier – Envoy of the Beginning attacks again (index 2, or index 3 with a preset target for Nitro Warrior). Otherwise index 1 (next attack). |

`duel_core_battle_check_replay` (`0x09dd177c`, called by steps 3 and 4) compares the snapshot with the field. If the attacker changed or can no longer attack: command `0x19` and back to step 1. If only the defender's monsters changed (or Decoy Dragon, Call of the Earthbound or Neo-Spacian Glow Moss apply): if the attacker can still declare an attack, replay (index 2, `0x09e28638 = 1`, UI event `0x0c`), otherwise end the attack. Returns 1 when it moved the step index (H).

`duel_core_run_effect_battle` (`0x09ddac64`, case `0x11` of the pending-action dispatcher `0x09c0e8b8`) starts at index 5 sub-step 1 and runs the table until the index passes 7: a battle caused by an effect has no declaration, no after-damage triggers and no step 10 (H for the range, M for the purpose).

## Damage calculation

`duel_core_battle_resolve(apply, simulate)` (`0x09dc5a4c`) with the attacker record `A`, target record `T`:

| Case | Destruction | Damage |
| --- | --- | --- |
| Direct attack | – | `A.ATK` to the defending player (`add_damage(A, NULL, ATK)`, damaged slot 5). |
| `T` in Attack Position, `A.ATK > T.ATK` | `T` | `A.ATK − T.ATK` to `T`'s controller. |
| `T` in Attack Position, `A.ATK < T.ATK` | `A` | `T.ATK − A.ATK` to `A`'s controller. |
| `T` in Attack Position, equal ATK | both, only if ATK > 0 | none |
| `T` in Defense Position, `A.ATK > T.DEF` | `T` | `A.ATK − T.DEF` to `T`'s controller only if `duel_core_has_piercing(A)` (a list of monsters with piercing, or the Fairy Meteor Crush / Big Bang Shot / Cyclon Laser / Sword of Kusanagi / Pitch-Dark Dragon / Koitsu equips). |
| `T` in Defense Position, `A.ATK < T.DEF` | none | `T.DEF − A.ATK` to `A`'s controller (Destruction Punch, Cross Counter and Continuous Destruction Punch then destroy `A`). |
| `T` in Defense Position, equal | none | none |

Then, in order: `duel_core_battle_is_destroyed` cancels a destruction for monsters that cannot be destroyed by battle; Gravekeeper's Vassal records become effect damage; `duel_core_battle_is_damage_prevented` zeroes damage that a monster's effect negates; doubling (`×2`, e.g. Cross Counter or Canyon when the target is in Defense Position, Stone Statue of the Aztecs for damage to the attacker's controller) and halving (`>> 1`, e.g. Ancient City – Rainbow Ruins, Arcana Force XIV – Temperance); Rod of the Mind's Eye sets 1,000; Clear Wall zeroes damage of 1,000 or less; Rainbow Life converts damage into a gain. Amounts are clamped to `0xffff` (H for each rule's position in the function; the card names identify the ids tested).

`duel_core_battle_add_damage(src, dst, amount)` (`0x09dc4330`) redirects the damage to the other player when the damaged side controls Magical Reflect Slime, Amazoness Swords Woman or a Metal Fiend Token in the battle, or Dimension Wall is active (H).

The two arguments of `resolve` (and the second of `compute_stats`) let the AI reuse the same code: `apply = 0` suppresses side effects (activations, statistics), `simulate ≠ 0` keeps damage that a real battle would hand to an effect and reads the stats from the AI snapshot at `0x09e0308c` (callers `0x09d06188`, `0x09d30ef0` in the AI; M).

## Per-card branches of the battle functions

The battle functions were read branch by branch in a `-readOnly` Ghidra decompilation (this round: `duel_core_battle_resolve`, `duel_core_battle_add_damage`, `duel_core_get_battle_destroyed_negation`, steps 4, 7 and 8 completely; steps 2, 6 and 10 for the branches that the blocked cards use). Card names identify the ids the code tests. "Record" is a battle record; the compare is on its card id `+0x18` unless the table says otherwise. These readings back the battle rows of `tools/engine_ref_semantics.csv`; per-card arithmetic is listed machine-readably in `tools/engine_branches.csv` (`card-effect-spec.md`, "Proposed field: engine_branches").

`duel_core_battle_resolve` (`0x09dc5a4c`), after the ATK/DEF comparison of "Damage calculation":

| Test | Branch | Conf. |
| --- | --- | --- |
| Equip links on the attacker (`duel_core_count_links_from_card_if_affected`): Fairy Meteor Crush, Big Bang Shot, Cyclon Laser, Pitch-Dark Dragon (not on Union Rider), Koitsu, Sword of Kusanagi | Piercing damage for a Defense-Position target | H |
| Destruction Punch / Cross Counter (slot effect) and an active Continuous Destruction Punch on the target's side, when the attacker hit a stronger DEF | Marker on the attacker (destroyed afterwards) | H |
| Gravekeeper's Vassal active on the damage source, damage to the other player | Player marker with the amount (turned into effect damage in step 7); the record is zeroed unless `simulate` | H |
| Dark Scorpion Combination on a direct attack | Damage set to 400 | H |
| Submarineroid / Sonic Shooter attacking directly by their effect | Damage set to the original ATK | H |
| Piranha Army on a direct attack | Damage doubled | H |
| Shadowknight Archfiend / Susa Soldier (attacker or target) | Damage to the opponent of its controller halved | H |
| Crystal Beast Amethyst Cat / Plasma Warrior Eitom attacking directly by their effect | Damage halved | H |
| Saurobeast Brachion / Stone Statue of the Aztecs as the target | Damage to the attacker's controller doubled | H |
| Arcana Force XIV - Temperance (effect value 2 on the damaged player's side, or value 1 on the other side) | Damage halved | M |
| Cross Counter on a Defense-Position target; Canyon with a Rock-Type (Type 6) target in Defense Position | Damage doubled | H |
| Ancient City - Rainbow Ruins on the damaged player | Damage halved | H |
| Rod of the Mind's Eye equipped on the damage source | Damage set to 1000 | H |
| Clear Wall on the damaged player's side | Damage of 1000 or less set to 0 | H |
| Rainbow Life marker (kind 1) on the damaged player | Player marker with the amount (LP gain in step 7); damage 0 | H |
| The Unhappy Girl (attacker or target, effect not negated, face-up Attack Position) | Marker on the other monster naming its slot (kind 6: battle lock) | H |
| Maiden in Love as the target | Maiden Counter (counter 0x0d) on the attacker unless it is immune | H |
| Ally Bomb (destroyed by a monster of Attribute 1), Gonogo, The Six Samurai - Zanji, Alien Hunter (target with an A-Counter), Oxygeddon (vs Type 4), Dark Mimic LV3, Prickle Fairy, Elemental Hero Neo Bubbleman / Hyper Hammerhead / Archfiend Matador (other side), Soldier of Mist Valley, Ryu Kokki (vs Types 0x12 / 0x0f), Getsu Fuhma (vs Types 2 / 3), Mechanical Spider (vs Attribute 2), Kaminote Blow | Marker for the after-battle effect resolved in steps 8-10 (`+0x38` set for the destroy-by-effect ones when `simulate`) | M |
| Sword of Dragon's Soul linked to a monster battling a Dragon (Type 1) | Marker on the Dragon (destroyed after the battle) | M |

`duel_core_battle_add_damage` (`0x09dc4330`): the damaged player's battle record holds Magical Reflect Slime, Amazoness Swords Woman or Metal Fiend Token with an active effect, or the damaged player has Dimension Wall: the damage goes to the other player (H).

`duel_core_get_battle_destroyed_negation` (`0x09dc5150`, renamed from `duel_core_get_battle_flip_trigger`): the value for the monster destroyed by battle. The old name read the flip test as a trigger; the card set and the texts show a negation (H for the set, M for value 2):

| Destroyer | Result |
| --- | --- |
| Element Doom / Element Saurus / Element Soldier while a DARK (Attribute 5) monster is face-up | 1; posts marker `0x17e4` on the destroyed monster |
| Dark Lucius LV6 / LV8 with their own effect, different sides; LV4 and Ancient Gear Beast on different sides | 1 (LV6 posts an instance marker) |
| Terrorking Archfiend, Guardian Baou, Ultimate Obedient Fiend, Dark Balter the Terrible | 1 |
| Twin-Headed Wolf with another face-up Fiend (Type 3); Blade Knight as the only monster; Harpie Lady 2 | 1 only for a Flip monster (`card_db_get_flip_kind == 1`) |
| Diffusion Wave-Motion marker, Wicked-Breaking Flamberge - Baou link | 1 |
| Fiend destroyer with Dark Ruler Ha Des active, Zombie destroyer with Revived King Ha Des active | 2 when a copy in another slot applies, else 1 |
| Marker `0x1f19` on the destroyed monster | 2 |

Step 4, `duel_core_battle_step_attack_declared` (`0x09dd3bd4`): The Dark Door (player marker kind 1 on the attacker's instance); Mirror Wall (kind-7 marker on the attacker naming the Mirror Wall slot, unless linked); Hero Barrier (player effect slot `0xb`, with an Elemental Hero, attacker not immune to Traps), Necro Gardna (player effect slot `0xb`), Cyber Barrier Dragon in Attack Position (once, Time Wizard key as the "used" marker) negate the attack (command `0x1f`); on the first declaration the Ancient Gear monsters (Ultimate Ancient Gear Golem, Evil Hero Wild Cyclone, Ancient Gear Knight, Gadjiltron Dragon, Engineer, Soldier, Beast, Golem) post player marker `0x18ab` on the opponent, which `duel_effects_is_activation_locked` reads (no Spell/Trap activation until the end of the Damage Step); White Veil marks itself; `duel_core_mark_battle_opponent_negated` (`0x09ce2230`) runs for Advanced Dark (a Rainbow Dragon battles) and Rainbow Veil (the equipped monster battles); Super Vehicroid - Stealth Union marks itself (H).

Step 7, `duel_core_battle_step_inflict_damage` (`0x09dd7528`): the attacker's "inflicts battle damage" trigger (event `0x1e2`) for Red Dragon Archfiend, Nitro Warrior, Alien Hunter, Ruin Queen of Oblivion, Divine Dragon - Excelion, Element Doom / Magician / Dragon, Black Luster Soldier - Envoy of the Beginning, Rocket Warrior and `0x1f19` (also as target); Satellite Cannon and Satellite Laser lose their counter marker; Gravekeeper's Vassal: effect damage of the marker value (`duel_core_inflict_card_damage(opponent, value, 1, Vassal)`); Rainbow Life: `duel_core_gain_lp` of the marker value; Reflect Bounder (target, other side) destroys the attacker; Cloudian monsters, Berserk Gorilla and Scab Scar Knight attacked in Defense Position are destroyed (`duel_core_battle_record_effect_applies` gates both) (H).

Step 8, `duel_core_battle_step_after_damage_calc` (`0x09dd7ae4`): sub-step 0 runs `duel_effects_apply_unique_name_rule(Kotodama)` and `duel_core_destroy_targeted_spirit_reapers`; sub-step 1 queues the "after damage calculation" trigger (event `0x2a2`) of Ally of Justice - Unknown Crusher (vs LIGHT), D.D. Assailant (destroyed, other side), D.D. Warrior Lady (other side), Divine Knight Ishzark / D.D. Crazy Beast (opponent destroyed), Mechanical Spider (marked), Kangaroo Champ, D.D. Warrior, Kelbek, Wall of Illusion; Swordsman from a Foreign Land and Zone Eater (attacker) mark the target with command `0x46` (5 turns, key Zone Eater) and Steel Scorpion (target) the attacker (3 turns) unless it is a Machine (Type 7); Electric Lizard (target) gives the attacker marker kind `0x21` unless it is a Zombie (Type 2); Cloak and Dagger marks itself when its declared name dealt the damage (H).

Step 10, `duel_core_battle_step_attack_end` (`0x09dd889c`), branches used by the cards of this round: Spear Dragon / Axe Dragonute / Elemental Hero Darkbright change to Defense Position after attacking (marker `0x14d6`); Big Shield Gardna to Attack Position after being attacked; Kaminote Blow markers destroy; the B.E.S. monsters and Big Core are destroyed without counters or queue their trigger; the after-battle markers of step 6 queue their triggers (event `0x002`); equips found on the attacker: Cupid Kiss (the damage dealer with a Maiden Counter: marker kind 5 = take control), Gladiator Beast's Battle Halberd / Ancient Gear Fist / Cyclone Blade (field trigger) (M; the rest of the function is in the step table above).

Step 2, `duel_core_battle_step_declare_attack` (`0x09dd2a6c`): Ring of Magnetism forces its holder as target; Evil Hero Malicious Fiend, Scab Scar Knight and Volcanic Doomfire (with a Defense-Position monster) on the defender's side, Patrician of Darkness, Dark Arena and Call of the Earthbound let the other player choose (selection prompt `0x0b`, yes/no `0x0a`); Submarineroid, Sonic Shooter, Cyberdark Edge, Crystal Beast Amethyst Cat and Plasma Warrior Eitom post a player marker when they attack directly only by their effect, which `duel_core_battle_resolve` reads (M).

## Function boundaries

`0x09be2eac` was cut by Ghidra at 268 bytes because the `jr v1` at `0x09be2f24` dispatches through a jump table (`0x09deb640`, 82 entries, bound `sltiu 0x52`) that the analyser did not recover; `0x09be2fb8`-`0x09be3bb4` were outside any function. `tools/ghidra/FixJumpTableFunction.java` reads the table, adds the 81 distinct case targets as `COMPUTED_JUMP` references from the `jr`, writes a decompiler jump-table override and re-derives the body: 268 → 3,340 bytes (`0x09be2eac`-`0x09be3bb8`, which ends at the `jr ra` before `thunk_world_character_can_duel`). It is idempotent and must run without `-readOnly`:

```
analyzeHeadless <projdir> TF3 -process rel_duel_eng.prx -noanalysis -scriptPath tools/ghidra \
    -postScript FixJumpTableFunction.java 0x09be2eac 0x09be2f24 0x09deb640 82
```

The repaired function is `duel_core_compute_duel_bonuses`: the end-of-duel bonus table. Each case writes the points of one bonus to the result block `+0xc4 + 4 × index` (examples: duelist level × 2, LP below 1000 → 20, below 100 → 100, at least 20000 → 20, exactly 5730 → 573, duel statistics through `0x09dcb734`, a listed card used in the duel (`duel_core_was_card_used_in_duel`: Perfectly Ultimate Great Moth, Gate Guardian, Exodia Necross ...) → 30, global `0x09e2d1f8` equal to Skull Servant → 1) and `+0x20c` receives 30 × the number of non-zero entries (one more when `0x09be2604(0x52)` is true). Caller `duel_core_record_duel_result` (M: the reading as DP bonuses follows the in-game result screen, not a runtime trace). The `0x1662` compare in it is the LP value 5730, not a card.

## Life Points

Player block `+0x00` is the LP. Initial value from the LP mode `0x09e02cac` (`0x09dc7dc4`): 3 → 4,000, 2 → 2,000, 1 → 1,000, anything else → 8,000; both sides get the same value (H). The `.ydq` loader (`0x09dc94e4`) writes it too.

The only writers in the game logic are the three command handlers (all wait for UI event `0x10` "LP counter animation" and post UI event 9 afterwards; they also update duel statistics with `0x09dcb8bc`/`0x09dcba48`):

| Command | Handler | Effect |
| --- | --- | --- |
| `0x23` (`a` = amount, `b` = reason) | `duel_core_cmd_lp_gain` `0x09dc05e4` → body `0x09dbffd8(1)` | `LP += a` unless LP is already 0. |
| `0x24` (`a` = amount, `b` = reason, `c` = source card) | `duel_core_cmd_lp_loss` `0x09dc05ec` → body `0x09dbffd8(0)` | `LP = max(LP − a, 0)`. With reason 1 (battle) and a lethal amount from a direct attack by one of the "special victory" monsters (Victory Dragon, Meteo the Matchless, Queen of Fate – Eternia, Emperor of Lightning, Tyr, Lorelei and others; ids `0x16ec`–`0x1f39`), the card id is stored in the winner's block `+0x2c` → win reason 8. With reason 2 on the turn player, Life Absorbing Machine is credited. |
| `0x25` (`a` = new value) | `duel_core_cmd_set_lp` `0x09dc05f4` | `LP = a` (UI event `0x0f`). |

Reasons passed in `b`: 0 effect damage, 1 battle damage, 2 paid cost, 3 lost (not a cost, e.g. Jirai Gumo), 4 gain (H from the five posting functions).

Posting functions (who changes LP):

| Function | Posts | Callers |
| --- | --- | --- |
| `duel_core_apply_battle_damage(rec)` `0x09c28074` | `0x24` reason 1, source = card id of the monster that dealt it; Power Wall reduces the amount by 100 per card; then "when battle damage is inflicted" triggers and timing event **`0x0f`** | Battle step 7 only. |
| `duel_core_inflict_damage(ctx, player, amount)` `0x09c27b34` | `0x24` reason 0; timing event **`0x10`** | 69 effect handlers, `duel_core_inflict_card_damage`, itself. Handles Energy-Absorbing Monolith (gain instead), Ring of Defense (none), Barrel Behind the Door / Spell of Pain (redirect), Trap of Board Eraser, Rainbow Life, Prime Material Dragon; `0x09c0d6ac` can prevent it. |
| `duel_core_inflict_card_damage(player, amount, flip, card)` `0x09c27a94` | Builds a dummy context for `card` and calls the above | 13 callers (battle step 7, chain resolver, End Phase upkeep). |
| `duel_core_gain_lp(ctx, player, amount)` `0x09c28cf0` | `0x23` reason 4; timing event **`0x11`** | 19 effect handlers, `duel_core_inflict_damage`. Bad Reaction to Simochi / Nurse Reficule the Fallen One on the other side turn the gain into damage (unless Prime Material Dragon). |
| `duel_core_pay_lp(player, amount)` `0x09c278cc` | `0x24` reason 2 | 28 callers: declaration costs (step 3), Standby/End Phase upkeep (`0x09de2460`, `0x09ddf4dc`), activation costs in effect handlers (`duel_effects_get_lp_cost` supplies the amounts). |
| `duel_core_lose_lp(player, amount)` `0x09c2791c` | `0x24` reason 3 | Battle step 3 (Jirai Gumo), `0x09c7c9a4`. |

So costs and damage both go through `0x24`; only the reason code distinguishes them (for triggers and statistics), and effect damage is subject to more replacement effects than battle damage.

## End of the duel

`duel_core_check_duel_end()` (`0x09dcb0ec`; callers `duel_core_run_turn_flow`, `duel_core_chain_step`, the chain resolver `0x09c2e244`, `duel_core_run_timing_windows`) calls `duel_core_check_win(side)` for the local side and the other side. If either is non-zero, it stores each side's code in its block `+0x30`, sets `0x09e2d1f0` (1 local side wins, 2 opponent wins, 3 both: draw), latches `0x09e2d1d4 = 1` and returns 1. In a link duel the remote side's check is skipped.

`duel_core_check_win(side)` (`0x09dcae58`) returns the first win reason that applies:

| Code | Condition |
| --- | --- |
| 2 | The opponent's block `+0x24` is set (hypothesis: the opponent had to draw from an empty deck; no writer found by direct reference) |
| 3 | `side` has the five Forbidden One pieces (`0xfb7`–`0xfbb`) in hand (`0x09c033a8`) |
| 4 | Destiny Board plus the four Spirit Message cards |
| 6 | Last Turn resolved (and `side` has a monster) |
| 7 | Final Countdown |
| 8 | `side`'s block `+0x2c` holds a special-victory card id (see command `0x24`) |
| 9 | Vennominaga the Deity of Poisonous Snakes |
| 10 | Exodius the Ultimate Forbidden Lord |
| 1 | **The opponent's LP (`+0x00`) is 0** |
| 11 | Turn limit reached (`turn ≥ 0x09e2d1e4 + 4`) and the opponent has fewer LP |
| 0 | No win |

The result is then reported by the duel-flow step `duel_core_flow_report_result` (command 5).

## Timing events and their consumers

`duel_core_raise_timing_event(code, arg)` (`0x09ccaae4`) appends to the queue: codes at byte `0x09e28fa0[i]`, arguments at `0x09e28fc0[i]`, count `0x09e28f98` (max 32), serial `0x09e28f94`. Outside a batch the queue is restarted with the new event; `duel_core_timing_batch_begin`/`_end` (`0x09c2bbcc`/`0x09c2bd18`, nest counter `0x09e28f90`, about 200 callers) group simultaneous events. Raising sets `0x09e29048` (window pending) and resets the window state `0x09e29044`, `0x09e2904c`. While the chain is being resolved (`0x09e28f9c`) nothing is queued.

Codes identified in this work (H for where they are raised):

| Code | Event | Argument |
| --- | --- | --- |
| `0x0d` | Damage calculation | `attacker ATK | target ATK-or-DEF << 16` |
| `0x0e` | Battle damage about to be inflicted | packed damage record (amount, source side/slot, damaged player, slot) |
| `0x0f` | Battle damage inflicted | same packing, bit 26 = direct attack |
| `0x10` | Effect damage inflicted | amount, controller, damaged player |
| `0x11` | LP gained | amount, player |
| `0x13` | Attack declared | 0 |
| `0x14` | Start of the Damage Step | `attacker | slot << 8 | (defender | target << 8) << 16` |
| `0x17` | End of the Battle Phase | 0 |

Consumers:

1. `duel_core_run_timing_windows()` (`0x09ccc494`), reached from the chain pending-work function `0x09c32dac` when no chain is building or resolving and `0x09e29048` is set. State 0: `duel_core_check_duel_end`; if the first queued code is `0x17`, `0x04` or `0x03` (leaving a phase) the turn player's window is skipped. State 1: `duel_core_offer_response_window(NULL, turn side)`; state 3: the same for the opponent. If someone activated a card (`0x09e2904c`), the window closes and the chain machinery takes over; the chain resolver `0x09c2e244` sets `0x09e29048` again afterwards. `duel_core_offer_response_window` (`0x09ccbe74`) asks a human (`duel_core_begin_player_input(side, 4)` for a timing window, `5` for a chain response), the AI, or forwards the queue to the link peer; `duel_core_can_respond(side, check_cards)` (`0x09ccb3b0`) tests every field card and hand card for an activatable effect at this timing (`0x09c52168`, `0x09c522d8`).
2. About 45 activation-condition handlers and AI routines read the queue directly (`0x09c382ec`, `0x09c67538`, `0x09c74010`, `0x09cda268`, `0x09d1d8f8`, …): they loop over `0x09e28fa0[0..count)` looking for a code (e.g. 8/9, `0x1e`) and decode the argument. A chain link's event code (bits 6–11 of `ctx + 2`) is the timing code that triggered it.

## Battle-related commands

| Code | Handler | Effect |
| --- | --- | --- |
| `0x14` | `duel_core_cmd_begin_attack_selection` `0x09db30f0` | Battle index = 1; UI event 10 (attack-selection mode). |
| `0x15` | `duel_core_cmd_recalc_battle` `0x09db3f14` | Recomputes stats and result without side effects (`compute_stats_live(0)`, `resolve_live(0)`). |
| `0x16` | `duel_core_cmd_show_battle_damage` `0x09db3780` | Sets `0x09e2862c`, recomputes, Confusion Chaff / Berserker Soul / Turbo Booster / Spacegate bookkeeping, marks the turn player's block `+0x120` bit 19, UI event `0x0d` with the damage values. |
| `0x17` | `duel_core_cmd_declare_attack` `0x09db35cc` | `0x09db315c(side, slot, defender, target)` sets up the attack globals (`0x09e28628 = target ≥ 5`); `c ≠ 0` takes a new snapshot; UI event `0x0c` (attack animation). |
| `0x18` | `duel_core_cmd_declare_direct_attack` `0x09db36bc` | Same with target 5. |
| `0x19` | `duel_core_cmd_attack_done` `0x09db3b1c` | `b = 0`: clears slot flag bit 22; `b ≠ 0`: counts the attack (`0x09bee500`) and handles monsters that may attack several times (Asura Priest, Diffusion Wave-Motion, …). |
| `0x1c` | `duel_core_cmd_end_attack` `0x09db4158` | Clears Hero Spirit and the attacker's slot flag bit 25. |
| `0x1d` | `duel_core_cmd_end_battle_phase` `0x09db4224` | Battle index = 11; UI events `0x0e`, `0x26`. |
| `0x1f` | `duel_core_cmd_negate_attack` `0x09db42ac` | Battle index = 10 (local duel); counts the attack; clears slot flag bits 25 and 30. |
| `0x20` | `duel_core_cmd_mark_battle_destroyed` `0x09db44a8` | Sets slot flag bit 2 of monster `a` (`b` = 0 attacker side, 1 defender side). |
| `0x23`, `0x24`, `0x25` | see "Life Points" | |

## Key functions

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x09dd2a6c` | `duel_core_battle_step_declare_attack(side)` | H | Battle table entry 2; posts `0x17`/`0x18`. |
| `0x09dd3574` | `duel_core_battle_step_attack_costs()` | H | Entry 3; pays Toll, Dark Elf costs. |
| `0x09dd3bd4` | `duel_core_battle_step_attack_declared()` | H | Entry 4; timing `0x13`, command `0x1f`. |
| `0x09dd4530` | `duel_core_battle_step_damage_start()` | H | Entry 5; timing `0x14`. |
| `0x09dd5454` | `duel_core_battle_step_damage_calc()` | H | Entry 6; timing `0x0d`, `resolve_live(1)`, commands `0x15`, `0x16`, `0x20`. |
| `0x09dd7528` | `duel_core_battle_step_inflict_damage()` | H | Entry 7; timing `0x0e`, `apply_battle_damage`. |
| `0x09dd7ae4` | `duel_core_battle_step_after_damage_calc()` | H | Entry 8; trigger event `0x2a2`, command `0x46` countdowns (read completely, "Per-card branches"). |
| `0x09dd82b4` | `duel_core_battle_step_damage_end()` | M | Entry 9; `request_battle_destruction`. |
| `0x09dd889c` | `duel_core_battle_step_attack_end(side)` | H | Entry 10; command `0x1c`, next index 1/2/3/11. |
| `0x09ddac64` | `duel_core_run_effect_battle(a, cancel_cmd, no_windows)` | M | Runs entries 5–7. |
| `0x09dd177c` | `duel_core_battle_check_replay()` | H | Snapshot `memcmp`, replay or cancel. |
| `0x09dd1544` | `duel_core_battle_snapshot_targets(int *out)` | H | Writes the 12-word snapshot. |
| `0x09dc15c8` | `duel_core_battle_compute_stats(apply, simulate)` | H | Fills the battle records from `duel_core_compute_card_stats` plus the Damage-Step modifiers (`stat-modifiers.md`). |
| `0x09dc4328` | `duel_core_battle_compute_stats_live(apply)` | H | `compute_stats(apply, 0)`. |
| `0x09dc5a4c` | `duel_core_battle_resolve(apply, simulate)` | H | Table above. |
| `0x09dc6f90` | `duel_core_battle_resolve_live(apply)` | H | `resolve(apply, 0)`. |
| `0x09dc4330` | `duel_core_battle_add_damage(src, dst, amount)` | H | Writes `0x09e286e0`. |
| `0x09dc4594` | `duel_core_battle_is_destroyed(attacker, apply, simulate)` | M | Per-card "cannot be destroyed by battle" chain. |
| `0x09dc5150` | `duel_core_get_battle_destroyed_negation(defender_destroyed, apply)` | H | Battle record `+0x40`; card table in "Per-card branches". |
| `0x09bf7ea8` | `duel_core_battle_record_effect_applies(rec)` | H | Not an effect monster, or effect active with `+0x40` = 0. |
| `0x09ce2230` | `duel_core_mark_battle_opponent_negated(card_id)` | M | Rainbow Veil / Advanced Dark kind-9 marker in steps 4-6. |
| `0x09ce096c` | `duel_core_check_defense_position_destruction()` | H | Cloudian / Berserk Gorilla rule check. |
| `0x09c14480` | `duel_core_prompt_advanced_dark_deck_card(side, card_id, arg)` | M | Prompt-request kind 8 (Deck list for Advanced Dark). |
| `0x09be2eac` | `duel_core_compute_duel_bonuses()` | M | 82-case bonus table; body repaired ("Function boundaries"). |
| `0x09dc555c` | `duel_core_battle_is_damage_prevented(rec, attacker)` | M | Per-card damage negation. |
| `0x09bedf1c` | `duel_core_has_piercing(side, slot)` | H | Card list; equips. |
| `0x09c28074` | `duel_core_apply_battle_damage(rec)` | H | Command `0x24` reason 1, timing `0x0f`. |
| `0x09c27b34` | `duel_core_inflict_damage(ctx, player, amount)` | H | Command `0x24` reason 0, timing `0x10`. |
| `0x09c27a94` | `duel_core_inflict_card_damage(player, amount, flip, card)` | H | Dummy context, calls the above. |
| `0x09c28cf0` | `duel_core_gain_lp(ctx, player, amount)` | H | Command `0x23`, timing `0x11`. |
| `0x09c278cc` | `duel_core_pay_lp(player, amount)` | H | Command `0x24` reason 2. |
| `0x09c2791c` | `duel_core_lose_lp(player, amount)` | H | Command `0x24` reason 3. |
| `0x09dc05e4`, `0x09dc05ec`, `0x09dc05f4` | `duel_core_cmd_lp_gain`, `_lp_loss`, `_set_lp` | H | Commands `0x23`–`0x25`; the only LP writers. `_lp_loss` verified in PPSSPP (Session A, A3: 8000 → 7800 for `0x24 a=200`; Session B: the tag pair's LP fell by the logged amounts); `_lp_gain` and `_set_lp` not exercised yet. |
| `0x09dcae58` | `duel_core_check_win(side)` | H | Win-reason table. |
| `0x09ccc494` | `duel_core_run_timing_windows()` | H | Window state machine. |
| `0x09ccbe74` | `duel_core_offer_response_window(link, side) → done` | H | Human/AI/link response window; documented in `chain.md` ("The response window"). |
| `0x09ccb3b0` | `duel_core_can_respond(side, check_cards)` | M | Field and hand scan. |
| `0x09c2bbcc`, `0x09c2bd18` | `duel_core_timing_batch_begin()`, `_end()` | H | Nest counter `0x09e28f90`. |
| `0x09c232a0` | `duel_core_request_battle_destruction()` | H | `0x09e2d2bc = 4`, `0x09e2d298 = 1`. |
| `0x09bea640` | `duel_core_can_monster_attack(side, slot, flag)` | M | Face-up, Attack Position (with exceptions), not restricted. |
| `0x09bea574` | `duel_core_can_declare_attack(side, slot, flag)` | M | Can attack and has a target or a direct attack. |
| `0x09bed1d0` | `duel_core_can_attack_directly(side, slot)` | M | Opponent's Monster Zones hold no blocking monster. |
| `0x09bed2d8` | `duel_core_get_direct_attack_mode(side, slot, flag)` | L | 0 no, 1 may attack directly, 2 must (effects). |
| `0x09beb8cc` | `duel_core_is_valid_attack_target(side, slot, def_side, def_slot, mode)` | M | 4,616-byte rule chain; 16 callers. |
| `0x09becad4` | `duel_core_count_attack_targets(side, slot)` | H | Counts valid targets among the 5 opposing slots. |
| `0x09db30f0` … `0x09db44a8` | battle commands | H/M | Table above. |

## Open questions

- Confirm at runtime (PPSSPP): LP at `0x09e2a528`/`0x09e2b064`, the step sequence through `0x09e2d220`, and the damage records at `0x09e286e0` for one ATK-vs-DEF attack with piercing.
- Resolved: the per-card modifiers and their order are in `stat-modifiers.md` and extracted by `tools/stat_mods.py`; record fields `+0x14`–`+0x30` are stat-block words.
- Record field `+0x40`: the meaning is established (effect negation of the battle-destroyed monster); open: what value 2 changes against value 1 (Ha Des copies, marker `0x1f19`), and what the Clear Vice Dragon / Wicked Avatar flag of `duel_core_battle_compute_stats` changes.
- Trigger codes queued by the steps: `0x1e2` (inflicts battle damage, step 7), `0x2a2` (after damage calculation, step 8), `0x002` (after battle, step 10). Their decoding into timing events is not traced.
- `duel_core_compute_duel_bonuses`: the name of each of the 82 bonuses (the result screen text table) and what `0x09e2d1f8` holds (compared with Skull Servant).
- Step 6 (`duel_core_battle_step_damage_calc`) and steps 5, 9 and 10 are only partly read; their rows in `tools/engine_ref_semantics.csv` stay L where the branch was not read.
- Who writes player block `+0x24` (win reason 2, presumably deck-out); it is not referenced directly.
- The second record written by `resolve` when the attacker carries one of the piercing equips controlled by the opponent (`add_damage(A, A, …)`); the rule it implements is unclear.
- Event code `0x2a2` used by after-battle trigger registrations (`0x09c2c578`) and the other timing codes raised elsewhere (`0x03`, `0x04`, `0x08`, `0x09`, `0x1e`, `0x20`–`0x22`, `0x25`).
- `0x09de0c98` (tested in steps 2 and 10; Last Turn related, hypothesis) and `0x09dd11dc` (step 2 sub-step 0) are not named.
