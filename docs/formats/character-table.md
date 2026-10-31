# Character table (`BOOT.BIN` `0x088aa510`, 174 × 148 bytes)

The resident table of every character appearance: one record per `(character, variant)` (a variant is a costume or role of the same character), 174 records of `0x94` bytes, `0x088aa510`–`0x088b09a7`. Read through about 40 accessors in `BOOT.BIN` `0x0885aca0`–`0x0885bcd0` (`world_*`, `audio_*`), which modules reach through `libehsys_rel`. Voice fields are also described in `sound.md` ("Character table"); the per-row save flags are `save.md` ("Character flags"); the 140-row table of `rel_story` (`world.md`, "Character table (`rel_story` `+0x2245c`)") is a different table.

**Lookup.** Records are sorted by `(u8 character, s8 variant)`; `world_find_character(c, v)` (`0x0885adb0`) uses `bsearch` with `world_compare_character_key` (`0x0885bcd0`). Row index = (record − `0x088aa510`) / `0x94` (`world_find_character_row`, `0x0885aca0`); `world_get_character_key(row)` (`0x0885ad14`) goes back. Most accessors do not check for a missing record. Characters 0 (none) and 1 (the player, `PC_0`) have records like the others.

Pointer fields hold `BOOT.BIN` addresses of NUL-terminated ASCII names (relocated at load; 0 = none). Statistics below are over all 174 records of the retail `BOOT.BIN` (read 2026-10-31).

| Offset | Size | Type | Field | Conf. | Basis |
| --- | --- | --- | --- | --- | --- |
| `+0x00` | 1 | `u8` | Character id | H | comparator, `world_get_character_key` |
| `+0x01` | 1 | `s8` | Variant | H | same |
| `+0x02` | 2 | — | Zero in every record; no access | H (layout) | statistics |
| `+0x04` | 4 | ptr | Record name (`ASUKA_0`, `PC_0`, `NONE_0`, …) | H | `world_get_character_record_name` |
| `+0x08` | 1 | `u8` | Category 0–5: 0–2 duellists (grouped by the weekly pairing), 4–5 non-duellists; 5 returned for a missing character | H | `world_get_character_category` (`0x0885aeb0`), `world_character_can_duel` |
| `+0x09` | 1 | `s8` | Kind byte (values 1–5, 11); 5 together with "generic" marks a generic duellist | M | `world_get_character_byte_09`, `world_character_is_generic_duelist` |
| `+0x0a` | 2 | — | Zero in every record; no access | H (layout) | statistics |
| `+0x0c` | 4 | ptr | Bust-up portrait archive (`bu_*.ehp.gz`), 0 for none | H | `world_get_character_word_0c`; values |
| `+0x10` | 4 | ptr | Small field sprite texture, first form (`sd_*_sla.gim`) | M | `world_get_character_word_10`; values |
| `+0x14` | 4 | ptr | Small field sprite texture, second form (`sd_*_ver.gim`) | M | `world_get_character_word_14`; values |
| `+0x18` | 2 | `s16` | Value a (−1 in the records read) | M (type), — (meaning) | `world_get_character_fields_18` |
| `+0x1a` | 2 | `s16` | Value b | M (type), — (meaning) | same |
| `+0x1c` | 1 | `s8` | Value c | M (type), — (meaning) | same |
| `+0x1d` | 3 | — | Zero in every record; no access | H (layout) | statistics |
| `+0x20` | 4 | ptr | Mini bust-up name (`mini_bup_<name>_<n>`) | M | values |
| `+0x24` | 4 | ptr | Duel cut-in archive (`cutin_*.ehp`), or 0 | H | `sound.md` |
| `+0x28` | 4 | ptr | Mini bust-up texture (`mini_bu_NNN.gim`) | M | `world_get_character_word_28`; values |
| `+0x2c` | 3 | `s8[3]` | Field model ids; all ≥ 0 = the character has a field model (low nibble of `+0x2e` used) | H | `world_get_character_model_ids`, `world_character_has_field_model` |
| `+0x2f` | 1 | — | Zero in every record; no access | H (layout) | statistics |
| `+0x30` | 4 | `u32` | First bank of the voice set (0 = no voice) | H | `audio_get_voice_bank`, `sound.md` |
| `+0x34` | 4 | `u32` | First of the four small voice banks (3 when there is no voice) | H | `audio_get_voice_extra_bank`, `sound.md` |
| `+0x38` | 4 | ptr | Voice/profile key (`ASUKA`, `SYOU`, …), 0 for none | H | `world_get_character_profile_key`, `sound.md` |
| `+0x3c` | 2 | `u16` | Bit set tested by `world_test_character_flag_3c(c, v, bit)` (characters 0/1 map to `(1, 0)`) | H (type), — (meaning) | accessor |
| `+0x3e` | 1 | `u8` | 1 in 8 records, else 0; no accessor found | — | statistics |
| `+0x3f` | 1 | `s8` | Index (−1 none; for characters 0 and 1 the variant-0 value plus the variant) read by `rel_duel_mgr` and `rel_title` | M (type), — (meaning) | `world_get_character_byte_3f` |
| `+0x40` | 4 | `u32` | Name index (0–462) | M | `world_get_character_name_index` |
| `+0x44` | 5 | `u8[5]` | Tuning bytes (values such as 10, 50, 60, 80); no caller in the analysed modules | — | `world_get_character_bytes_44` |
| `+0x49` | 9 | `u8[9]` | Tuning bytes; no caller in the analysed modules | — | `world_get_character_bytes_49` (and an identical copy) |
| `+0x52` | 3 | `u8[3]` | Small values 0–3, no accessor found | — | statistics |
| `+0x55` | 3 | — | Zero in every record | H (layout) | statistics |
| `+0x58` | 8 × 4 | `u32[8]` | Tuning words (non-zero in 133 records); no caller in the analysed modules | — | `world_get_character_words_58` |
| `+0x78` | 6 × 2 | `u16[6]` | Card ids for duel cut-in voice selection (returned in the order `+0x7c, +0x7e, +0x80, +0x82, +0x78, +0x7a`; non-zero in 53 records) | M | `world_get_character_card_ids`, caller `audio_select_cutin_voices_standard` |
| `+0x84` | 4 | ptr | Card-id list used by the deck editor to flag the owner's recipe cards | M | `world_get_character_pointer_pair_84`, caller `deck_flag_listed_recipe_cards` |
| `+0x88` | 4 | `u32` | Count of that list (0–6; 0 in 111 records) | M | same |
| `+0x8c` | 4 | ptr | Key-card id list for voice lines | M | `world_get_character_pointer_pair_8c`, caller `audio_voice_is_character_key_card` |
| `+0x90` | 4 | `u32` | Count of that list (0 in 111 records, else 8–12) | M | same |

The fields `+0x44`–`+0x77` look like duel tuning values and are identical across variants of a character; `world.md` keeps the hypothesis (low) that a module outside the Ghidra project reads them.

## Open questions

- Meanings of `+0x09`, `+0x18`–`+0x1c`, `+0x3c`, `+0x3e`, `+0x3f`, `+0x52`–`+0x54` and of the tuning block `+0x44`–`+0x77`.
- What distinguishes the two sprite textures `+0x10` (`_sla`) and `+0x14` (`_ver`).
