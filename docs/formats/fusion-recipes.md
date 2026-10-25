# Fusion recipe table and ritual table (`gmodule/rel_duel_eng.prx`)

Status: `documented` (layout, material-code semantics, readers). Addresses are runtime addresses with the module at `0x09be1400` (file offset = address − `0x09be1400` + `0x54`). Tool: `tools/fusion.py` (`recipes`, `rituals`, `--check`). The summoning procedures that use these tables are described in `docs/subsystems/summon.md`.

Basis: Ghidra decompilation of every reader (read-only project copy), the BOOT.BIN card-group predicates they call, and the card database (`cardinfo.md`) used to check that every id is a real card of the expected kind. Not yet traced in PPSSPP. Confidence per claim: H (high), M (medium), L (low).

## Fusion recipes at `0x09debe98`

138 records (`0x8a`, the loop bound in all three readers) of 8 bytes, no terminator, not sorted (H):

| Offset | Size | Field |
| --- | --- | --- |
| `+0` | u16 | Fusion monster id. |
| `+2` | u16 | Material code 0. |
| `+4` | u16 | Material code 1. |
| `+6` | u16 | Material code 2; 0 = the Fusion has two materials. |

Records 0–118 have two materials, records 119–137 three (the three-material recipes were appended as a block). Every Fusion id is a cardinfo record of kind 5 or 7, and every material that is a card id exists in cardinfo (`--check`, H). 142 of the 144 Fusion-kind cards are covered (138 here, 4 hard-coded below); the two others are Neo-Spacian monsters of Fusion kind that are summoned by their own effect.

Readers: `duel_effects_get_fusion_material_code(fusion_id, slot)` (`0x09cb9630`), `duel_effects_get_fusion_material_count(fusion_id)` (`0x09cb959c`) and the inline copy in `duel_effects_resolve_fusion_summon` (`0x09cbace0`). All three search linearly on `+0`.

### Material codes

A code below `0x24` is a generic requirement; any other code is a card id. Tested by `duel_effects_card_matches_material_code(code, ref)` (`0x09cb910c`), which first takes the card's effective id, Type and Level from where it is (field slot through `0x09c052f8`; hand: `duel_core_get_level_by_ref`; graveyard: `0x09c02c30` for the Type; elsewhere the printed values) (H for the dispatch; the group meanings are named from the id lists):

| Code | Requirement |
| --- | --- |
| `1`–`0x15` | A monster of that Type (cardinfo race number: 1 Dragon … 6 Rock, 7 Machine … 15 Warrior … 21 Psychic). Cards in spell/trap zones 5–10 never match. Examples: Evil Hero Dark Gaia uses `3, 6` (Fiend + Rock); UFOroid Fighter uses UFOroid + `0x0f` (Warrior). |
| `0x16` | Ojama group (BOOT `0x08861068`: the Ojama monsters, Ojama Knight/King and Ojama support cards). Ojama Knight uses it twice. |
| `0x17` | Gladiator Beast group (BOOT `0x08861f94`). |
| `0x18` | BOOT `0x08862334`: Rainbow Dragon and Rainbow Dark Dragon (used by Rainbow Neos). |
| `0x19` | Ancient Gear group (BOOT `0x08861298`). |
| `0x1a` | Any Gemini monster (kind 19, BOOT `0x0886019c`); no Type test (Superalloy Beast Raptinus). |
| `0x1b` | "Neos" group (BOOT `0x08860e6c`: Elemental Hero Neos, its Fusions and other Neos-named cards). |
| `0x1c` | Neo-Spacian group (BOOT `0x088616a8`). |
| `0x1d` | "HERO" group (BOOT `0x08861810`: Elemental Hero, Destiny Hero, the list at BOOT `0x08862118`, Hero's Bond). |
| `0x1e` | Union of `0x1b`, `0x1c`, `0x1d` and the Evil Hero cards (BOOT `0x08862968`). |
| `0x1f` | Fiend-Type monster of Level 6 or more. |
| `0x20`–`0x23` | Monster in a graveyard (location `0x0e`) of Level ≤ 4, 5–6, ≥ 7, ≥ 8 (the Fossil Fusion recipes: Rock + one of these). |

Card-id codes match through BOOT `0x0885fb5c(card, code)`, which accepts the same id and a few alias groups (Harpie Lady and its renamed copies, the token variants, Umi and A Legendary Ocean, Aqua Dolphin and Marine Dolphin, Glow Moss and Twinkle Moss, two alternate-art ids of Dark Magician and Blue-Eyes White Dragon, Polymerization and `0x1303`). A code that is itself a Fusion-kind Neo-Spacian matches only the exact id (H). Chimeratech Fortress Dragon (`0x1ceb`) never counts as a material (H).

### Fusions hard-coded in the code

`duel_effects_get_fusion_material_code` and `_count` handle four Fusions before the table search (H):

| Fusion | Count | Codes per slot |
| --- | --- | --- |
| Elemental Hero Divine Neos (`0x1e7e`) | 5 | `0x1c`, `0x1b`, `0x1d`, then `0x1e` |
| Super Vehicroid – Stealth Union (`0x1ab3`) | 4 | four card ids |
| Elemental Hero Electrum (`0x19ef`) | 4 | four card ids |
| F.G.D. (`0x157e`) | 5 | `1` (Dragon) in every slot |

Chimeratech Overdragon (`0x1a4e`) and Chimeratech Fortress Dragon (`0x1ceb`) have two-material records (Cyber Dragon + code `7` Machine) but their procedures accept "two or more" materials and end the selection when the player stops (`duel_effects_resolve_fusion_summon` state `0x77`, `duel_core_summon_prepare_contact_fusion`) (H).

### Matching a chosen card to a slot

At the start of a fusion the codes are copied to the slot array `0x09e2906c` (up to 5 words). `duel_effects_match_fusion_material(ref, commit)` (`0x09cb97c4`) (M for the tie rules):

- For each non-zero slot code, a card that matches counts; among generic codes (≤ `0x23`) only the first matching slot counts (except a `0x1d` HERO slot after a `0x1b` Neos slot, which also counts). Card-id slots always count.
- A **fusion substitute** (BOOT `0x08866870`: Goddess with the Third Eye, Beastking of the Swamps, Versago the Destroyer, Mystical Sheep #1, King of the Swamp and the three Hex-Sealed Fusions; on the field it must be face-up and its slot flag bit 8 clear) may fill one card-id slot, once per fusion (flag `0x09e29068`). Substitutes are refused for the Fusions in BOOT `0x088668e4` (Destiny End Dragoon, Rainbow Neos, Cyber Twin/End Dragon, Cyber Ogre 2, Cyber Blader, UFOroid Fighter, F.G.D. and others) and when the spell is Cyberdark Impact!.
- With `commit` = 1 a unique match clears that slot; an ambiguous match (several slots) clears nothing and increments `0x09e29060`.

## Ritual table at `0x09dec4d4`

u32 records terminated by a zero word: 31 records + terminator = 128 bytes (H).

| Bits | Field |
| --- | --- |
| 0–13 | Ritual monster id. |
| 14–27 | Ritual Spell id. |
| 28–31 | Level total the tributes must reach (equals the monster's Level in all 31 records). |

28 distinct spells: End of the World lists two monsters and Machine Angel Ritual three. Earth Chant and Contract with the Abyss have no record of their own; they may use any record whose monster is EARTH (5) or DARK (2) (`duel_effects_can_ritual_summon_entry`). Readers: `duel_effects_resolve_ritual_summon` (`0x09ccd668`), `duel_effects_cond_ritual_summon` (`0x09ccd5b4`), `duel_effects_can_ritual_summon_entry` (`0x09ccd224`), `duel_effects_filter_ritual_monster` (`0x09ccd0f8`), `duel_effects_is_valid_ritual_tribute` (`0x09ccc718`).

How Ritual Spells reach this code: most Ritual Spells have **no record** in the effect tables; `duel_effects_find_record` (`0x09ce2e54`) then falls back by spell icon to the first three records of the S/T table, which carry the placeholder id `0xe74`: record 0 for field spells, record 1 for equip spells, record 2 for ritual spells (handlers `+04` `0x09ccd668`, `+0c` `0x09ccd5b4`) (H). Advanced Ritual Art has its own record.

## Checks (`tools/fusion.py --check`)

- 138 recipes, ids in range and unique, no Fusion both in the table and hard-coded, two materials in records 0–118 and three in 119–137, every generic code known, and the half-word after the table is not a card id.
- The ritual table ends with a zero word within 64 records; every Level total is 1–12.
- The readers listed in `CONSUMERS` build the table address (lui + addiu or a load/store base) and contain the constant `0x8a` where applicable.
- With `--cardinfo`: every Fusion is kind 5/7, every card-id material exists, every ritual monster is kind 9/11, every ritual spell is kind 27 with icon 6, and each Level total equals the monster's Level.

On the disc the check passes: 138 recipes (119 + 19), 295 material slots of which 25 are generic (14 distinct codes), 31 ritual records.

## Open questions

- Confirm the slot-matching tie rules of `0x09cb97c4` (ambiguous matches, `0x09e29060`) in PPSSPP with a Fusion whose materials overlap (Elemental Hero Divine Neos, Ojama Knight).
- `0x09e29060` is also used to sum the materials' ATK for UFOroid Fighter and Evil Hero Dark Gaia; check that the two uses never overlap.
- The data after the recipe table (`0x09dec2e8`–`0x09dec4d4`) is not identified.
