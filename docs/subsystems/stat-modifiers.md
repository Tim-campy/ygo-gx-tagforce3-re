# ATK/DEF and other current stats (work package 4)

How `gmodule/rel_duel_eng.prx` (runtime base `0x09be1400`) computes a monster's current ATK, DEF, Type, Attribute and Level, and how continuous effects, equip spells, field spells and temporary effects change them. All addresses are runtime addresses. Evidence is static (Ghidra decompilation of a read-only copy of the project, the call graph and the card database, used only to identify the card ids that the code tests); nothing here has been traced in PPSSPP yet. Confidence per claim: H (high), M (medium), L (low).

## Summary

- **There is no modifier table.** Every stat modifier is a card-id compare chain in code. One function, `duel_core_compute_card_stats` (`0x09c05304`, 19,196 bytes), produces a 13-word **stat block** for a monster slot; it is called by every reader of a current stat: field display, effects, the AI and the battle code (H).
- The chains are grouped by **where the modifier comes from**: the monster's own effect (keyed by its own id), other face-up cards (keyed by the source card's id), the field-spell zone, effects **attached** to the monster's slot (keyed by the id of the card that created them), equip spells and monsters linked to the slot, and Damage-Step-only bonuses in the battle code (H).
- Effects that last (for example "gains 700 ATK until the end of the turn", Power Bond, Copycat) are not code paths of their own: the effect handler attaches a small **10-byte effect record** to the monster's slot (command `0x35`), and the stat builder looks the record's key (the source card id) up in its chain (H for the mechanism).
- Order: original stats (with "original ATK becomes" effects) → the card's own effect → attached effects, equips and other cards' continuous effects **in timestamp order** (a "becomes X" effect discards everything accumulated before it) → global multipliers (halving, doubling) → clamp at 0. Battle adds a Damage-Step layer on top (H for the structure, M for the exact timestamp rule).
- `tools/stat_mods.py` lists every card id these functions test: 543 distinct cards in 628 uses; 505 of the 512 cards whose `CARD_Genre` has "Increase/Decrease ATK/DEF" are referenced (H; counts from the maintainer's module).

## The stat block (13 words, `0x34` bytes)

Written by `duel_core_compute_card_stats(side, slot, out, flags, timestamp)`; only slots 0–4 are filled (spell/trap zones return after word 0).

| Word | Offset | Meaning | Writer | Conf. |
| --- | --- | --- | --- | --- |
| 0 | `+0x00` | Card name id: the id the card is "treated as" (`duel_core_get_slot_name_id`: Elemental Hero Neos Alius → Neos while face-up, copy effects such as Elemental Hero Divine Neos and Neo-Spacian Dark Panther) | `compute_base_stats` | M |
| 1 | `+0x04` | Effective card id for effect lookups (`duel_core_get_slot_card_id`; copy effects) | `compute_base_stats` | M |
| 2 | `+0x08` | Current Type (race enumeration of `cardinfo.md`: 1 Dragon … 21 Psychic) | `duel_core_get_race` | H |
| 3 | `+0x0c` | Current Attribute (1 LIGHT … 7 DIVINE) | `duel_core_get_attribute` | H |
| 4 | `+0x10` | Attribute mask `1 << attribute`, plus extra attributes (Sphere of Chaos `|2`, Elemental Mistress Doriado `|0x78`) | builder | H |
| 5 | `+0x14` | Current Level | `duel_core_get_level` | H |
| 6 | `+0x18` | **Current ATK** | builder | H |
| 7 | `+0x1c` | **Current DEF** | builder | H |
| 8 | `+0x20` | Original ATK (card data, then "original ATK becomes" effects) | `compute_base_stats` | H |
| 9 | `+0x24` | Original DEF | `compute_base_stats` | H |
| 10 | `+0x28` | Unaffected by Spell effects: bit 0 the monster's controller's, bit 1 the opponent's (`duel_effects_get_spell_immunity`) | `compute_base_stats` | M |
| 11 | `+0x2c` | Unaffected by Trap effects, same bits (`duel_effects_get_trap_immunity`) | `compute_base_stats` | M |
| 12 | `+0x30` | Unaffected by monster effects, same bits (`duel_effects_get_monster_immunity`) | `compute_base_stats` | M |

The immunity words gate every external modifier: a source card controlled by `src_side` is ignored when `mask & ((side != src_side) + 1)` is non-zero; spell/trap sources use word 10 or 11 by `card_db_is_trap`, monsters word 12 (H for the test; the masks' meaning follows from the cards they gate: Zombie World and Forest-type fields use word 10, DNA Surgery and D. Tribe word 11, Parasite Paracide word 12).

### Readers

| Address | Name | Returns |
| --- | --- | --- |
| `0x09c052f8` | `duel_core_get_card_stats(side, slot, out)` | `compute_card_stats(side, slot, out, 0, 0)` (≈ 75 callers). |
| `0x09c0a604` | `duel_core_get_atk(side, slot)` | Word 6 (callers include the target rules `0x09beb8cc`, `0x09bed2d8` and many effect handlers). |
| `0x09c0a654` | `duel_core_get_def(side, slot)` | Word 7. |
| `0x09c0a62c`, `0x09c0a67c` | `duel_core_get_original_atk`, `_def` | Words 8 / 9 from `compute_base_stats` (used by `duel_core_battle_resolve` and "original ATK" effects). |
| `0x09c04aa8` | `duel_core_get_base_stats(side, slot, out)` | `compute_base_stats(…, 0)`. |
| `0x09c0ac64` / `0x09c0ac6c` | `duel_core_get_race(side, slot)` / `_ex(side, slot, mode)` | Current Type: card data, then Type changers by timestamp: Parasite Paracide (Insect), DNA Surgery (declared Type, stored in the source slot), Zombie World (Zombie), Dragonic Attack (Dragon), D. Tribe (Dragon), Mirage/Clone tokens. |
| `0x09c0b204` | `duel_core_get_attribute(side, slot, *out_flag)` | Current Attribute. |
| `0x09c0a6a4` / `0x09c0a6ac` | `duel_core_get_level` / `_ex` | Current Level. |

The AI does not call the builder directly for unknown cards: `0x09ce9edc`/`0x09cea1f8` (AI group, not named here) use it only for cards the AI may see and otherwise read card data (M).

## Effect attachments (`0x09e2c7cc`)

Every field slot has a singly linked list of **effect records**; slot `+0x0a` (`u16`) is the head. Index 11 of each player's slot array (player `+0x11a`) is a player-wide list (for example Double Summon's entry, `summon.md`), and the 6-byte card-instance table `0x09e2bbcc` has a head at `+4` for effects that follow a card off the field. The records live in one pool (H for all fields; `duel_core_attach_effect` writes them):

| Offset | Size | Field |
| --- | --- | --- |
| `+0x00` | 2 | Key. Kinds 0–5: the card id of the effect's source. Kinds 6–12: the source card's location `side | slot << 8`. |
| `+0x02` | 1 | Bits 0–3 kind, bits 4–7 a turn counter. |
| `+0x04` | 2 | Value (amount, chosen option, packed ATK/DEF …; meaning per source card). |
| `+0x06` | 2 | Timestamp: the placement serial `0x09e2d1d0` when the record was made (the same counter as slot `+0x04`). |
| `+0x08` | 2 | Next record index (0 ends the list). |

Pool: index `i` at `0x09e2c7cc + 10 × i`, `i` = 1–255 (index 0 is "none"); a free record has kind 0. `duel_core_expire_turn_effects` (`0x09be6864`, from command handler `0x09dbc584`) walks all 255 at the turn change: kinds 1 and 2 are removed when the counter is 0, otherwise it is decremented; kind 7 links from All-Out Attacks, Swift Samurai Storm! and Attribute Chameleon are removed, and Weapon Change's after its turn (M for the reading of the counter as "turns left").

| Kind | Meaning (from the code that reads it) | Conf. |
| --- | --- | --- |
| 0 | Free | H |
| 1, 2 | Temporary effect with a turn counter; ignored by the stat builder when `flags` bit 1 is set | M |
| 3, 4, 5 | Lasting effect from source card `key` | M |
| 6–9 | Link to a face-up source card at `key` (a continuous card that affects only this monster, e.g. Miniaturize, Shadow Spell, Weapon Change) | M |
| 10, 11 | Equip link: the equip card at `key` is equipped to this monster | H (Heart of Clear Water, the `count_links` callers) |
| 12 | A monster card equipped to this monster (Cyberdark monsters, Thousand-Eyes Restrict, Relinquished, Destiny Hero – Plasma, Truckroid) | M |

Primitives:

| Address | Name | Notes |
| --- | --- | --- |
| `0x09be5894` | `duel_core_attach_effect(side, slot, kind, key, value) → index` | First free record, appended to the slot's list, timestamp from `0x09e2d1d0`; −1 when the pool is full. 69 callers (commands and effect handlers). |
| `0x09be59a8` | `duel_core_attach_instance_effect(instance, kind, key, value) → index` | Same on a card instance's list. |
| `0x09db7208` | `duel_core_cmd_attach_effect()` | Engine command `0x35` (jump table `0x09e00944`): `b` bit 15 selects the instance form; then `0x09be75f8` and UI event `0x26`. |
| `0x09be5660` | `duel_core_detach_effect(index)` | Clears the record and unlinks it from every list. |
| `0x09be5aa8` | `duel_core_detach_effect_list(head)` | Frees a whole list (card leaves its slot). |
| `0x09be57a0` | `duel_core_detach_links_from_source(side, slot)` | Removes the kind ≥ 6 records whose key is that source (the equip card left). |
| `0x09be9168` | `duel_core_slot_has_effect(side, slot, key) → bool` | A kind ≤ 5 record with that key. 250+ callers. |
| `0x09be9b44` | `duel_core_sum_effect_values(side, slot, key)` | Sum of the values of kind < 6 records with that key. |
| `0x09be79dc` | `duel_core_count_links(side, slot, head, card, check_active, check_immunity, kind, timestamp)` | Kind 6–11 records whose source currently is `card` (with optional negation/immunity checks); wrappers `duel_core_count_links_from` (`0x09be7d00`, both checks), `_unchecked` (`0x09be7c28`), `_since` (`0x09be7d48`, a timestamp bound). |

## The computation

### 1. Original stats: `duel_core_compute_base_stats(side, slot, out, flags)` (`0x09c04ab4`, 2,116 bytes)

1. Words 0/1 from the slot's card id; words 8/9 = `card_db_get_atk/def`. Face-down or effect-less (slot flag bit 3) cards stop here.
2. Name id, effective id, immunity words 10–12.
3. Phantom of Chaos-type copy (`0x1cb7` record value, kind 2) unless `flags` bit 1.
4. Trap monsters: `duel_core_apply_trap_monster_stats(card, out)` (`0x09c04984`) writes Type/Attribute/Level/ATK/DEF for Cyber Shadow Gardna, Stronghold the Moving Fortress, Zoma the Spirit, Metal Reflect Slime, Embodiment of Apophis and The Rival's Name (H; the values match the card texts).
5. A per-card chain on the card's own id, using the slot's counter word `+0x0c` (`u32` at `0x09e2a568`): for example Chimeratech Fortress Dragon `count × 1000`, Hourglass of Courage doubles or halves the original stats depending on the turn, Option Token copies the stats of the linked monster.
6. The slot's records: equip links (kind 10) of Unstable Evolution (2,400 or 1,000 by LP comparison) and Zero Sprite (0); effects (kinds 1–5) of Alchemy Cycle (original ATK 0), `0x17b3` (original DEF 0), Cat's Ear Tribe (200), Mirage/Clone tokens (copied values), and ATK/DEF swaps (`0x1f24`, `0x1f08`, `0x19f1`, `0x19d2`, `0x12cb`).

### 2. Current stats: `duel_core_compute_card_stats(side, slot, out, flags, timestamp)` (`0x09c05304`)

`flags` bit 0: do not clamp ATK/DEF at 0 (the battle code sets it); bit 1: ignore kind 1/2 records (AI view). `timestamp` is passed down to the "count cards" helpers (The Wicked Avatar computes the others' ATK with `-own timestamp` to avoid recursion; M).

Accumulators (H; local variables of the function): **own** (`a_own`, `d_own`), **attached** (`a_att`, `d_att`), **other cards** (`a_oth`, `d_oth`), **equips** (`a_eq`, `d_eq`), **field spell** (`a_fld`, `d_fld`). ATK and DEF start at the original values (words 8/9).

1. **Attribute overrides** (Sphere of Chaos, Elemental Mistress Doriado and three others) into word 4.
2. **Reverse Trap** (`0x1257`): if player 0's player-wide list holds it, every accumulator is later *subtracted* instead of added.
3. **The card's own continuous effect** (`self` section, 127 cards): a chain on word 1 that either adds to `a_own/d_own` (for example "+300 per Spellcaster on the field") or sets ATK/DEF directly (The Winged Dragon of Ra, Slifer, Evil Dragon Ananta, Gradius' Option …). Values often come from counting helpers (`0x09c01d64`, `0x09bf9578`, `0x09c01cb8` …; not yet named).
4. **Other face-up cards**: for each of both players' slots 0–9 whose card has an active effect, `duel_effects_get_field_card_stat_bonus(stats, src_side, src_slot, side, slot, &atk, &def)` (`0x09c04198`, 29 cards; monsters in slots 0–4: Command Knight, Harpie Lady 1, the Ultimate Insect auras, Batteryman C, the six "one Attribute +500, its opposite −400" monsters Bladefly, Milus Radiant, Little Chimera, Star Boy, Witch's Apprentice, Hoshiningen …; spells/traps in slots 5–9: Burden of the Mighty, Banner of Courage, Yellow Luster Shield, The A. Forces, Ancient Gear Castle, Aqua Chorus …). A non-zero result stores the source's placement serial (slot `+0x04`) in a 2 × 10 table; the amount is added later, in timestamp order.
5. **Field spell**: the first player (0, then 1) whose slot 10 holds an active card with a bonus for this monster: `duel_effects_get_field_spell_stat_bonus` (`0x09c03b44`, 25 cards: Forest, Wasteland, Mountain, Sogen, Umi, Yami by Type; Gaia Power, Rising Air Current, Molten Destruction, Luminous Spark, Umiiruka, Mystic Plasma Zone by Attribute; Neo Space, Necrovalley, Wetlands, Venom Swamp, Jurassic World, Harpies' Hunting Ground …). Its amount (`a_fld/d_fld`) and the field slot's serial are kept.
6. **The slot's record list**, in list (= creation) order. Before each record, every pending other-card bonus and the field-spell bonus whose serial is ≤ the record's timestamp is added (`a_oth`, `d_oth`). Then by kind:
   - kinds 3/4 (and 1/2 unless `flags` bit 1): a chain on the source card id (`attached` section, 183 cards). Most add the value or a constant to `a_att/d_att` (Winged Minion +700/+700, Power Bond adds the record's value, the original ATK; Triangle Power +2,000/+2,000); "becomes" effects set ATK and/or DEF and **clear the accumulators gathered so far** (Copycat and Paleozoic Fossil Dragon – Skullgeoth take ATK and DEF from two chained records, Mist Condor 1,700, `0x1e88`; "ATK becomes twice the original" records of Speed Warrior, Arcana Force I and others via word 8); Goddess of Whim halves or doubles the running total; Darkblaze Dragon doubles the original values; The Winged Dragon of Ra (`0x1388`) reads a packed `ATK | DEF << 16` value.
   - kinds 6–9: chain on the linked source's current id (`linked_card`, 12 cards: Miniaturize −1,000, Mokey Mokey Smackdown 3,000, Fairy Box 0, Shadow Spell −700, Rare Metalmorph +500, Weapon Change swaps …) into `a_oth/d_oth`.
   - kinds 10/11: chain on the equip card's current id (`equip_spell`, 101 cards: the Legendary Sword family +300/+300, Horn of the Unicorn +700/+700, Burning Spear +400/−200, Megamorph by LP comparison, Dragonic Attack +500/+500 for Warriors, 7 Completed by the chosen option `slot +0x0c`, Stim-Pack 700 − 200 per turn counter …) into `a_eq/d_eq`.
   - kind 12: chain on **this** monster's id (`equipped_monster`, 11 cards: Destiny Hero – Plasma gains half the equipped monster's ATK, the Cyberdark monsters and Truckroid gain its ATK, Thousand-Eyes Restrict and Relinquished take its ATK and DEF; Petit Moth equipped with Cocoon of Evolution becomes 0/2,000).
7. Remaining other-card and field-spell bonuses are added.
8. `ATK = ATK ± (a_oth + a_eq + a_att + a_own)`, `DEF = DEF ± (d_oth + d_eq + d_att + d_own)` (field-spell amounts are inside `a_oth`). Sign `−` under Reverse Trap.
9. **Final rules** (`final` section): The Wicked Avatar (ATK = DEF = 100 more than the highest other face-up monster), Cyber Blader (double ATK while the opponent controls exactly 2 monsters); Water Dragon on the field (either side, unless unaffected): FIRE or Pyro monsters' ATK = 0; Mirror Wall: ATK halved once per Mirror Wall link (`duel_core_count_links_since(…, 0x1381, timestamp)`); The Wicked Dreadroot: ATK and DEF halved once per active Dreadroot on either side (not itself). Halving rounds up: `(x + 1) >> 1`.
10. Clamp ATK and DEF at 0 unless `flags` bit 0.

Two consequences for the port (H): a "becomes" effect only overrides modifiers older than itself (older attached records and the bonuses of cards that arrived earlier); and the result is recomputed from scratch at every read, so there is no stored current ATK to keep in sync.

### 3. Damage Step: `duel_core_battle_compute_stats` (`0x09dc15c8`)

It fills the two battle records (`battle.md`) from `compute_card_stats(side, slot, block, 1, 0)` (no clamp) or, when simulating, from the AI snapshot at `0x09e0308c` (13 words per slot, `0x44` bytes per slot, `0x154` per side). Then, for the attacker and, when not a direct attack, the target:

- The battle-only amounts obey the same global rules as the stat block: per side an ATK halving counter (Mirror Wall links, active Wicked Dreadroots, minus one for Cyber Blader's condition), a DEF halving counter (Dreadroots) and a "zero" flag (Water Dragon for FIRE/Pyro monsters). Earth Giant Gaia Plate halves its battle opponent's ATK and DEF and adds one to both counters (H for the code, M for the reading).
- The attacker's own battle effects: Nitro Warrior (+1,000, tested through `0x09be8fb0`), Cyberdark Edge and Elemental Hero Rampart Blaster (ATK halved when attacking directly), Mirage Knight (+ the target's original ATK), The Hunter with 7 Weapons (+1,000 against the declared Type), Kinetic Soldier (+2,000 ATK and DEF against a Warrior), Spirit Ryu (+1,000 per discarded Dragon, simulation only); the same per-card rules for the target. Clear Vice Dragon and The Wicked Avatar are recognised first (`0x09bf7cb4` tests that fill a per-side flag); what that flag changes is not fully read (L).
- `duel_core_battle_get_damage_calc_bonus(card, defender)` (`0x09dd1c90`, 20 cards) returns the "during damage calculation only" amount of the battling monster's own effect (−1 when the card has none); Fusion Devourer, Super Vehicroid – Stealth Union, Cat's Ear Tribe and Dark Artist are handled specially (ATK 0, original ATK halved, original ATK 200, DEF halving).
- Attached records of the battling monster: 8-Claws Scorpion (2,400 against face-down), Kinetic Soldier, Injection Fairy Lily (+3,000 when its value is 1), Sanga of the Thunder (ATK 0).
- Equip links: Ballista of Rampart Smashing (+1,500), Amulet of Ambition (500 × Level difference); Prideful Roar / Covering Fire values (`sum_effect_values`); Otherworld – The "A" Zone and Shien's Castle of Mist (−300 / −500); A-Counters (−300 each, `0x09c00514`, for Alien monsters).
- The total is shifted by the doubling/halving counters, multiplied by ±1 (Reverse Trap) and added to words 6/7.

Record fields (resolves the open question in `battle.md`, H): `+0x14` = word 0 (name id), `+0x18` = word 1 (effective id), `+0x1c`/`+0x20` = words 8/9 (original ATK/DEF, clamped at 0), `+0x24`/`+0x28` = words 6/7, `+0x2c` = word 2 (Type), `+0x30` = word 5 (Level). The function also posts statistics (`0x09dcb8bc(0xb, ATK)`) and destroys Heart of Clear Water when the equipped monster's ATK is 1,300 or more (`0x09c24c00`).

## Coverage: `tools/stat_mods.py`

```
python3 -I tools/stat_mods.py <USRDIR>/gmodule/rel_duel_eng.prx --check
python3 -I tools/stat_mods.py <USRDIR>/gmodule/rel_duel_eng.prx -o extracted/stat_mods --cardinfo <USRDIR>/duelsys/cardinfo_eng.ehp
python3 -I tools/tests/test_stat_mods.py
```

The tool reuses the decoder of `tools/effect_params.py`. For each stat function above it lists every `li rX, <card id>` and classifies it: `test` (a beq/bne on the register: a case of the chain, with the constants and calls of its body), `call` (the id is an argument of a lookup helper such as `slot_has_effect`), `other`. The builder's cases are assigned to the sections of this document by address ranges, and `--check` verifies prologues, returns and six anchor cases (Sogen, Unstable Evolution, Horn of the Unicorn, Skullgeoth, Reverse Trap, Fusion Devourer). Body constants are a mechanical hint (amounts computed with multiplications or loaded from records do not appear). Results on the maintainer's module:

| Section | Cards | Section | Cards |
| --- | --- | --- | --- |
| base | 37 | equip_spell | 101 |
| attribute | 5 | equipped_monster | 11 |
| self | 127 | final | 5 |
| attached | 183 | field_card | 29 |
| linked_card | 12 | field_spell | 25 |
| damage_step | 50 | **total** | **543 distinct** |

Of the 512 cards with the genre "Increase/Decrease ATK/DEF", 505 appear; the seven that do not are Kazejin, Suijin (their effect zeroes the attacker's ATK through a handler, not a modifier; L) and five Alien monsters (A-Counter penalties are applied by a group predicate, not by id).

## Key functions

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x09c05304` | `duel_core_compute_card_stats(side, slot, out, flags, timestamp)` | H | Above; readers return its words 6/7. |
| `0x09c04ab4` | `duel_core_compute_base_stats(side, slot, out, flags)` | H | Words 8/9 from `card_db_get_atk/def`, then overrides. |
| `0x09c04198` | `duel_effects_get_field_card_stat_bonus(stats, src_side, src_slot, side, slot, *atk, *def) → bool` | H | Card chain on the source id; immunity words. |
| `0x09c03b44` | `duel_effects_get_field_spell_stat_bonus(stats, src_side, src_slot, side, slot, *atk, *def) → bool` | H | Forest … Yami by word 2. |
| `0x09dd1c90` | `duel_core_battle_get_damage_calc_bonus(card, defender) → int` | M | Battle globals; −1 = no entry. |
| `0x09c04984` | `duel_core_apply_trap_monster_stats(card, out)` | H | Six trap monsters. |
| `0x09bf01f8` | `duel_core_is_effect_active(side, slot) → bool` | M | Face-up, flags bits 1/3/8 clear, Gemini monsters only when Gemini-summoned (or with `0x1c85`). |
| `0x09bf0af4` | `duel_core_get_slot_card_id(side, slot)` | M | Slot id with copy effects (Divine Neos, Dark Panther records). |
| `0x09bf0328` | `duel_core_get_slot_name_id(side, slot)` | M | Name the card is treated as (Neos Alius → Neos …). |
| `0x09bf7cb4` | `duel_core_is_active_card_at(side, slot, card) → bool` | H | Id match, active, not disabled by `0x09e2bba8`. |
| `0x09bf8a78` | `duel_core_count_active_cards(side, card, except_slot, timestamp)` | M | Counts active copies on the field (monster or S/T zones by card kind). |
| `0x09bfeca8`, `0x09bfefe4`, `0x09bff190` | `duel_effects_get_spell_immunity`, `_trap_immunity`, `_monster_immunity(side, slot)` | M | Words 10–12; see the stat block. |

The getters, attachment primitives and the race/attribute/level functions are listed in the tables above.

## Open questions

- Confirm in PPSSPP: words 6/7 of the stat block for a monster with an equip, a field spell and a temporary boost, and the record pool at `0x09e2c7cc`.
- The argument packing of command `0x35` (`a` slot and kind, `b` key with bit 15 for instance records, `c` value) is inferred from the instance branch only; the slot branch's registers are lost in the decompilation (M).
- Exact meaning of kinds 1 vs 2, 3 vs 4 vs 5 and 6–9 (which effects create which; the end-of-turn walk only distinguishes 1/2 and 7).
- The counting helpers used by the self chain (`0x09c01d64`, `0x09c01cb8`, `0x09bf9578`, `0x09bf94a0`, `0x09c014ac`, `0x09bf9c2c`, `0x09bfc50c` …) are not named.
- Why the Reverse Trap test reads only player 0's player-wide list.
- `0x09c0a174` (no direct callers; builds a 2 × 11 "affects" matrix with `0x09c09e00`) is presumably the UI's "which cards affect this monster" view.
- How Kazejin/Suijin and the Alien A-Counter penalty reach ATK (handlers, `0x09c00514`).
