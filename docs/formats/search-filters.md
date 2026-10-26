# Search filters: candidate builders, scanner arguments, filter and options words

How a card that "chooses a card from the Deck / hand / Graveyard / …" describes *which* cards qualify, in `gmodule/rel_duel_eng.prx` (runtime base `0x09be1400`). Companion of `docs/subsystems/effect-helpers-deck.md` §1 (the candidate list `0x09e29928` and how resolve handlers read the choice). Tool: `tools/search_filters.py`.

Basis: decompilation of the five scanners, `duel_effects_candidate_matches_filter`, the dispatcher and the predicates (read-only Ghidra project copy, earlier in this pass), their MIPS code, and a symbolic run of all 419 builders checked against well-known cards (below). Not yet traced in PPSSPP. Confidence: H high, M medium, L low.

## 1. Builder list

| Item | Value | Conf. |
| --- | --- | --- |
| Address | `0x09dec554` ("list L1" in `effect-tables.md`) | H |
| Records | 686 × 8 bytes: `u32 card id`, `u32 builder` (module offset; runtime = `0x09be1400 + value`). Sorted by card id, no duplicates. | H |
| Dispatcher | `duel_effects_build_candidate_list` (`0x09cdc85c`): clears the count `0x09e29920`, binary-searches the list for `card_id & 0xffff`, calls the builder with `(side, card_id, param)` and returns the count. `duel_effects_count_candidates` (`0x09cdc90c`) does the same without clearing. | H |
| Builders | 419 distinct functions. 10 of the 686 card ids (`0x1303`, `0x1dee`, `0x1df9`, `0x1dfd`, `0x1e76`–`0x1e78`, `0x1ebc`, `0x1f34`, `0x1f35`) have no record in `cardinfo_eng.ehp` (cards not in this release). | H |

A builder is usually one call (often a tail jump) to a **location scanner**; some call several scanners (Deck + Graveyard, hand + Deck …), select the filter with a compare chain on `card_id`, take it from `param` or from card getters, or add candidates themselves with `duel_effects_add_candidate(side, location, index)` (`0x09cdc7d0`).

## 2. Scanner calls

All scanners take the PSP EABI argument registers `a0`–`a3`, `t0`–`t3`:

| Scanner | Address | Location | Arguments | Conf. |
| --- | --- | --- | --- | --- |
| `duel_effects_collect_deck_candidates` | `0x09ccecbc` | `0x0d` Deck | `(side, card_id, pred, pred_arg, filter, options)` | H |
| `duel_effects_collect_extra_deck_candidates` | `0x09ccf134` | `0x0c` Extra Deck | same | H |
| `duel_effects_test_hand_candidate` | `0x09ccf428` | `0x0b` hand, one card | `(side, card_id, hand_index, pred, pred_arg, filter, options)` | H |
| `duel_effects_collect_graveyard_candidates` | `0x09ccf768` | `0x0e` Graveyard | `(side, card_id, pred, pred_arg, filter, options)` | H |
| `duel_effects_collect_banished_candidates` | `0x09ccfcdc` | `0x0f` banished | same | H |

`pred` is a function `(side, location, index, card_id, entry, pred_arg)` or 0; it is called last, after the filter. `pred_arg` is passed through untouched; builders point it at a stack slot holding the parameter.

Common prologue of every scanner (H):

1. If the filter has no monster bit (`0x2`) but any of the monster-only fields (`filter & 0xff3cfc00`) or a monster-only option (Deck `0x18`, Extra `0x0f`, hand `0x06`, Graveyard `0x3cb8`, banished `0x08`) is set, the monster bit is added.
2. If none of `0x2`/`0x4`/`0x8` is set, all three are (any card kind).
3. Query mode: when `*(u32 *)0x09e29924` is non-zero the scanner stores the final filter word there and returns 0 (used by the AI and by `duel_effects_target_still_matches_filter`).

## 3. Filter word

Monster tests are in `duel_effects_candidate_matches_filter(side, location, entry, filter)` (`0x09cce9a8`), applied when bit `0x2` is set and the card is a monster (BOOT `0x0885fef0`); the spell/trap and name bits are tested by the scanners. A card matches when it passes the monster test **or** the spell test **or** the trap test.

| Bits | Name in the tool | Meaning | Conf. |
| --- | --- | --- | --- |
| `0x00000001` | `count_only` | Count matches, do not add them | H |
| `0x00000002` | kind `monster` | Monster card, then all monster fields below | H |
| `0x00000004` | kind `spell` | Spell (BOOT `0x0885ff3c`) | H |
| `0x00000008` | kind `trap` | Trap (`card_db_is_trap`) | H |
| `0x00000010` | `same_name` | BOOT `0x0885fb5c(candidate, card_id)` (same name, with the alias groups of `fusion-recipes.md`) | H |
| `0x00000020` | `different_name` | Not the same name as `card_id` | H |
| `0x00000040` | — | Not tested anywhere; never set by a builder | H |
| `0x00000380` | `icon=` | Spell/trap icon + 1 (`(bits >> 7) − 1` = `card_db_get_icon`: 0 normal, 1 counter, 2 field, 3 equip, 4 continuous, 5 quick-play, 6 ritual); 0 = any | H |
| `0x00000400` | `normal_monster` | BOOT `0x0885ff84`: `card_db_get_kind` 0 or 15 (cardinfo kinds 1 and 31); in the hand `0x09c02f80` | H |
| `0x00000800` | `summonable` | `duel_core_can_special_summon_card(side, id, location)` | M |
| `0x00001000` | `summon_conditions` | `0x09c0c8a0(side, id, location)` (summon conditions) | M |
| `0x00002000` | `atk_max_1500` | `card_db_get_atk_or_unknown(id) < 0x5dd` | H |
| `0x00004000` | `flip` | BOOT `0x08863438` == 1 (genre `0x16` FLIP; some ids return 2 and are excluded) | M |
| `0x00008000` | `tuner` | BOOT `0x088601c0`: kind 15 or 16 (cardinfo 31/33) | H |
| `0x00010000` | `targetable` | `0x09c02b48(side, id)`: false for a monster while a monster on the other side is equipped with Metalsilver Armor (`0x15eb`, through `0x09be7e88`), and for the ids of BOOT `0x08862688` (Lightsworn cards) while card `0x1e74` is active. Set by targeting revivals (Monster Reborn, Premature Burial, Call of the Haunted: `0x10002`) | L (meaning), H (code) |
| `0x00020000` | — | Not tested; never set | H |
| `0x003c0000` | `level` | Level (bits 18–21); hand cards use the current Level (`duel_core_get_level_by_ref`), elsewhere `card_db_get_level` | H |
| `0x00400000` | `level>=` | Level ≥ field | H |
| `0x00800000` | `level<=` | Level ≤ field (neither bit: equal) | H |
| `0x07000000` | `attribute=` | Attribute (bits 24–26) equal; cardinfo numbering 1 LIGHT … 7 DIVINE; in the Graveyard `0x09c02d48` (current) | H |
| `0xf8000000` | `type=` | Type (bits 27–31) equal; cardinfo race numbering 1 Dragon … 21 Psychic; in the Graveyard `duel_core_get_off_field_race` | H |

Examples (checked against the cards' printed text): Sangan `0x2002` (monster, ATK ≤ 1500); Mystic Tomato `0x2002002` (+ DARK) and Giant Rat `0x5002002` (+ EARTH), both with options `0x0a`; Reinforcement of the Army `0x78900002` (Warrior, Level ≤ 4); Armageddon Knight `0x2000002` (DARK); Monster Reborn `0x10002` in its own and (options `0x9`) the opponent's Graveyard.

## 4. Options word (per scanner)

| Scanner | Bit | Name in the tool | Meaning | Conf. |
| --- | --- | --- | --- | --- |
| Deck | `0x1` | `opponent` | Scan the other side's Deck | H |
| Deck | `0x2` | `skip_parasite_paracide` | Skip cards with marker `0x12a1` (Parasite Paracide) | H |
| Deck | `0x4` | `can_add_to_hand` | `duel_core_can_add_from_deck_to_hand(side)` must hold | H |
| Deck | `0x8` | `special_summon_test` | `0x09c0cb84(side, id, 0x0d)` = `0x09c0cb98(side, side, id, 0x0d, 1)` | M |
| Deck | `0x10` | `special_summon_test_b` | `0x09c0cb98(side, side, id, 0x0d, 0)` | M |
| Deck | `0x20` | `effect_monster` | BOOT `0x0885ffc0`: an Effect Monster kind (cardinfo 3, 7, 11, 13, 15, 17, 19, 23, 33, 37) | H |
| Deck | `0x40` | `first_match` | Stop at the first match | H |
| Deck | `0xfe000000` | `top=n` | Scan only the top `options >> 25` cards | H |
| Deck | — | — | Any of filter `0x1800` or options `0x18` also requires `0x09c0c4c8` (no Deck Lockdown `0x1dd1` active) | H |
| Extra | `0x1` | `fusion` | BOOT `0x08860060`: summon class 3 (Fusion) | H |
| Extra | `0x2` | `synchro` | BOOT `0x08860084`: summon class 10 (Synchro) | H |
| Extra | `0x4` | `extra_summon_test` | BOOT `0x08864ff8` and `0x08865ad8` (per-card summonability lists) | L |
| Extra | `0x8` | `fusion_materials` | BOOT `0x08863a34` < 2 and `0x09cba5dc(side, 0x09cba1ac(card_id), id)` (materials available) | L |
| Extra | `0x10` | `synchro_materials` | `0x09cbdf00(side, id)`: Synchro monster, not prohibited, materials on the field (`duel_core_filter_synchro_material`) | M |
| Hand | `0x1` | `sendable_to_graveyard` | `duel_core_can_send_ref_to_graveyard` | H |
| Hand | `0x2` | `special_summon_test` | `0x09c0cb84(side, id, 0x0b)` | M |
| Hand | `0x4` | `special_summon_test_b` | `0x09c0cb98(side, side, id, 0x0b, 0)` | M |
| Graveyard | `0x1` | `opponent` | The other side's Graveyard | H |
| Graveyard | `0x4` | `necrovalley_check` | `0x09c0d594`: false while Necrovalley (`0x159d`) is active unless the owner controls Gravekeeper's Chief (`0x158b`) | H |
| Graveyard | `0x8` | `can_special_summon` | `duel_core_can_special_summon_from_graveyard(side, owner, index)` | H |
| Graveyard | `0x10` / `0x20` | `special_summon_list_card`, `_2` | `duel_core_can_special_summon_list_card(side, side, entry, 0x0e, 0 / 2)` | M |
| Graveyard | `0x40`, `0x80`, `0x100`, `0x200` | `entry_flag5_clear`, `entry_flag2_set`, `entry_flag3_set`, `entry_flag4_set` | Bits of entry byte `+2` | L |
| Graveyard | `0x400` | `properly_summoned` | Also adds filter `0x800`; `0x09befb80(entry)`: a card that cannot be Normal Summoned (BOOT `0x08863d98`) must have entry bit 15 set | M |
| Graveyard | `0x800` | `treated_as_normal` | `0x09beeef8(owner, index)`: kind 0 or 15, or a Gemini whose entry flag says it is not yet a Effect Monster | M |
| Graveyard | `0x1000` / `0x2000` | `effect_not_treated_as_normal` / `effect_only_if_treated_as_normal` | Combinations of `0x0885ffc0` and `0x09beeef8` | M |
| Graveyard | `0x4000` | `can_banish_from_graveyard` | `duel_core_can_banish_from_graveyard(side, owner)` | H |
| Banished | `0x1` | `opponent` | The other side's banished zone | H |
| Banished | `0x4` | `face_up` | `0x09dcaa50(side, 0x0f, index)` (the card is face-up) | M |
| Banished | `0x8` | `can_special_summon` | `duel_core_can_special_summon_from_banished` | H |

## 5. Predicates

| Address | Name | `pred_arg` | Behaviour | Conf. |
| --- | --- | --- | --- | --- |
| `0x09cd02b0` | `duel_effects_candidate_in_archetype` | `int *archetype` | `BOOT 0x088633f8(id, *archetype)`: if `archetype < 0x3f`, calls entry `archetype` of the 63-pointer table at BOOT `0x0889e2d8` | H |
| `0x09cd0030` | `duel_effects_candidate_has_name` (new) | `int *card` | Graveyard: `0x09bf0ce4(side, index, *card)`; elsewhere BOOT `0x0885fb5c(id, *card)` (same name or alias) | H |

**Archetype ids are not the Fusion material group codes** of `fusion-recipes.md`, but both index the same BOOT.BIN group predicates: archetype `0x0d` = material code `0x16` (Ojama, `0x08861068`), `0x24` = `0x17` (Gladiator Beast, `0x08861f94`), `0x2d` = `0x18` (Rainbow Dragon, `0x08862334`), `0x11` = `0x19` (Ancient Gear, `0x08861298`), `0x0c` = `0x1b` (Neos, `0x08860e6c`), `0x17` = `0x1c` (Neo-Spacian, `0x088616a8`), `0x1b` = `0x1d` (HERO, `0x08861810`), `0x39` = `0x1e` (`0x08862968`). Archetype ids used by builders, labelled from the card ids compared in each predicate (H for the table, M for the labels):

| Id | BOOT predicate | Group | Id | BOOT predicate | Group |
| --- | --- | --- | --- | --- | --- |
| `0x00` | `0x08860200` | Toon | `0x1b` | `0x08861810` | HERO |
| `0x01` | `0x088602bc` | Archfiend | `0x1e` | `0x08861c40` | Six Samurai |
| `0x02` | `0x08860444` | Gravekeeper's | `0x1f` | `0x08861d6c` | (no id list; open) |
| `0x03` | `0x088604dc` | Guardian | `0x20` | `0x08861dac` | Volcanic |
| `0x04` | `0x088605c8` | Dark Scorpion | `0x21` | `0x08861e50` | Blaze Accelerator |
| `0x07` | `0x08860918` | LV monsters | `0x22` | `0x08861e7c` | Venom |
| `0x08` | `0x08860af8` | Elemental Hero | `0x23` | `0x08861ee4` | Cloudian |
| `0x09` | `0x08860f94` | Destiny Hero | `0x24` | `0x08861f94` | Gladiator Beast |
| `0x0e` | `0x08861118` | Batteryman | `0x25` | `0x088620bc` | Gladiator Beast's equips |
| `0x0f` | `0x08861174` | Dark World | `0x29` | `0x088621c4` | Arcana Force |
| `0x10` | `0x08861248` | B.E.S. | `0x2d` | `0x08862334` | Rainbow Dragon |
| `0x11` | `0x08861298` | Ancient Gear | `0x32` | `0x0886256c` | Worm |
| `0x13` | `0x088613d4` | Machiners | `0x33` | `0x08862688` | Lightsworn |
| `0x15` | `0x088614bc` | -roid (Vehicroid) | `0x34` | `0x08862738` | Frog |
| `0x16` | `0x08861614` | Super Vehicroid | `0x36` | `0x088627b8` | Genex |
| `0x17` | `0x088616a8` | Neo-Spacian | `0x39` | `0x08862968` | Neos / Neo-Spacian / HERO / Evil Hero |
| `0x18` | `0x0886164c` | Chrysalis | `0x3a` | `0x08862f00` | Morphtronic |
| `0x19` | `0x0886171c` | Alien | `0x3b` | `0x08862f9c` | Iron Chain |

## 6. Recovery results (`search_filters.py --cardinfo --boot`)

The tool runs every builder with `a1` = the record's card id: a path-sensitive known-bits evaluation (the same lattice as `effect_classify.py`), stack slots tracked so that `pred_arg` pointers resolve, sub-builders that reach a scanner followed up to 3 calls deep, loops widened after 24 visits. `card_db_get_race/attribute/level` called on a constant card id are answered from cardinfo (some builders compute "same Type/Attribute as this card" at run time).

| Status | Records | Meaning |
| --- | --- | --- |
| decoded | 599 | Every scanner call has a constant filter word, options word and predicate argument |
| partial | 35 | At least one field depends on `param` (the caller's third argument: a chosen card, a Level …), on memory, or on a card absent from cardinfo |
| custom | 52 | No scanner: the builder adds candidates itself (`duel_effects_add_candidate`); the tool reports the locations |
| none | 0 | |

881 distinct scanner calls (Graveyard 332, Deck 300, hand 194, Extra 37, banished 18), 827 fully constant. No builder passes filter bits `0x40` or `0x20000` or an options bit outside the tables above. Without `--cardinfo` the getter-based records stay partial (533 decoded).

## Open questions

- Filter `0x10000`: the second condition (card `0x1e74`, absent from cardinfo, with the Lightsworn list `0x08862688`) — which card is `0x1e74` and why it blocks Lightsworn candidates; confirm the Metalsilver Armor reading in PPSSPP.
- `0x09c0cb98`'s fifth argument (Deck/hand option `0x8` passes 1, option `0x10`/`0x4` passes 0).
- Graveyard options `0x40`–`0x200`: the meaning of entry byte `+2` bits 2–5.
- Extra Deck options `0x4`, `0x8`: the per-card lists in BOOT `0x08864ff8`, `0x08865ad8`, `0x08863a34`.
- Archetype `0x1f` (BOOT `0x08861d6c`): predicate without a card-id list (13 builders use it).
- The `param` values reaching partial builders (Destiny Board, Machine Duplication, Metamorphosis …) come from `duel_effects_get_candidate_param` (`0x09cc0dd0`); joining the two would decode those records too.
