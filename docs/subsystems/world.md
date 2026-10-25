# Free-roam world (work package 7)

How the Duel Academy free roam is put together: maps and their files, exits, characters on the map, the calendar and time of day, friendship points, the partner, and how the card shop unlocks packs. Static analysis only (Ghidra decompilation of `rel_field.prx`, `rel_story.prx`, `rel_shop.prx` and `BOOT.BIN`, plus the data files); nothing here has been traced in PPSSPP yet.

Modules (`docs/subsystems/modules.md`): `rel_field` (scene 5, base `0x090ced00`) draws and runs the field and serves 33 requests from `rel_story`; `rel_story` (scene 2, base `0x08e9aa00`) owns the calendar, the story state and the event bytecode (`docs/formats/story.md`); `rel_shop` (scene 7, base `0x090ced00`) is the card shop. Persistent state lives in the save state block (`save_get_state()`, `docs/formats/save.md`).

Formats: `docs/formats/hmp.md` (walk grid), `docs/formats/field-tables.md` (map ids, archives, doors, exit cells, field string tables). Tool: `tools/world.py hmp`.

## Maps

- A map is one archive `field/map/bg_NN_MM.ehp`: mesh, animations, textures and the walk grid `.hmp`. The field module knows 32 maps by **field map id** `M` (1–42, sparse) and converts it to an index 0–31 (`world_map_id_to_index`, `rel_field` `0x090d1144`) that selects the archive name and meshes (`field-tables.md`).
- Story scripts name places by **story location** `L` 1–29 (`scene_map`, opcode 50158); `rel_story`'s selector table maps `L` to `M`. Confirmed on data: with this mapping 99% of the scripted start and NPC cells are walkable cells of the right grid.
- **Movement** is on a 0.5-unit grid (`.hmp`): one byte per cell, 1 walkable. Positions in scripts are cell indices; the field centres them (`x·0.5 + 0.25`).
- **Doors** (`rel_field` `+0x25334`) are animated meshes with a target map id; only the classroom, the store and the Slifer dorm outside (its eight room doors and the dining hall) have them. **Exit cells** (`rel_story` `+0x1fb84`) are cells at the map border or room door; hypothesis (medium-high): stepping on one asks "Exit from this spot?" and opens the island map.
- **Island map** (`field/big_map/world_<period>.ehp`, five variants: morning, day, sunset, night, midnight; field resources 2–6 at `rel_field` `+0x2ee3c`): the travel screen with arrows (`bm_arrow11–14.ehf`). Its destination list is not decoded yet.

## Calendar and time of day

The calendar is a 0x24-byte block at story block `+0x3438` (save state `+0x1a24c`, see "Save fields"), registered by `world_set_calendar_blocks` (`rel_story` `0x08eaabd8`) and recomputed by `world_update_calendar` (`0x08eac278`) after each change.

| Word | Meaning | Conf. |
| --- | --- | --- |
| `+0x00` | Time-slot counter `t`, starts at 1 (`world_init_calendar`, `0x08eaac3c`). | H (code) |
| `+0x04` | Slot within the day, `(t − 1) % 7 + 1`, 1–7 (`world_get_time_slot`). | H (code) |
| `+0x08` | 5 at a new game, never recomputed here. Presumably the starting month (May; the field strings name May–August). | L |
| `+0x0c` | Day number, `day + 1` (shown as `(day%d)`). | M |
| `+0x10` | Day index `day = (t − 1) / 7` (`world_get_day_index`). | H (code) |
| `+0x14` | **Light period** of the slot, from the table at `rel_story` `+0x208ec` (8 bytes per slot): slots 1–2 → 0, 3–4 → 1, 5 → 2, 6 → 3, 7 → 4 (`world_get_light_period`). | H (table) |
| `+0x1c` | Weekday `(day % 7 + 1) % 7`, so day 0 → 1. | H (code) |
| `+0x20` | 1 at a new game. | — |

So **a day has seven time slots** and five lighting periods. The five periods match the five island-map archives in the order `morning, day, sunset, night, midnight` (field resources 2–6) (medium: the order of the archive list and the period values agree, the selecting code is not read). Changing time: `world_advance_time_slot` (`0x08eaacc8`, +1), `world_advance_time_slots(n)` (`0x08eaace0`), `world_set_time_slot(n)` (`0x08eab070`, slot `n` 1–7 of the current day), `world_advance_to_next_day` (`0x08eab0bc`, slot 1 of the next day). These back the PDA "Advance Time" menu ("Advance to the designated time", "End the day", "Speed up time to the day before the tournament"; `field_strtbl.bin`).

`world_is_day_off(n)` (`0x08eaacf8`) returns the table `rel_story` `+0x2e50c` `[0,0,0,0,0,0,1]` at `(day + n) % 7`: day index 6 of each week is special. With weekday 1 for day 0, that is weekday 0 — presumably Sunday, so the game starts on a Monday (low). `0x08eab474` tests `day % 10` against 9 and 0 (presumably the ten-day tournament cycle; low).

## Story stage

The field save block (story block `+0x345c`, `0xa8` bytes) starts with the **story stage** byte, 1–10 (`world_get_story_stage`, `0x08eab3fc`; `world_advance_story_stage`, `0x08eab3c0`, is the handler of opcode 50094 `advance_counter`: +1, capped at 10, and sets byte 1 to 1). Story flags (`world_set_story_flag`, `world_test_story_flag`): 1–32 in field-block word `+0x0c`, 33–64 in `+0x10`, 129–160 and 161–192 in words `+0x00`/`+0x04` of the flag block at story block `+0x42d8`; 65–128 are ignored. System flags (`0x08eaaee8` set, `0x08eaafbc` test; bit `n − 1`): 1–32 in field-block `+0x14`, 33–64 in `+0x18`, 65–96 and 97–128 in flag-block `+0x08`/`+0x0c`.

## Characters

- **Static table** (`BOOT.BIN` `0x088aa510`, 174 rows of 148 bytes, `docs/formats/sound.md`): row `r` ↔ `(character, variant)` through `world_get_character_key(r)` (`0x0885ad14`) and `world_find_character_row(c, v, &r)` (`0x0885aca0`, row = (record − `0x088aa510`) / 148); `world_count_character_variants(c)` (`0x0885b0b0`) counts the rows of one character. Other accessors in `0x0885adec`–`0x0885bb60` return single fields (`+0x08` a category byte: `0x0885aeb0`, 5 when missing; `+0x2c..+0x2e` three signed bytes, all ≥ 0 meaning "has a field model", `0x0885b984`; `+0x3c` a u16 bit set, `0x0885b7f4`; `+0x40`, `+0x84..+0x90` pointer pairs). The accessors of `+0x44..+0x74` (`0x0885b4ac`, `0x0885b4fc`, `0x0885b56c`, `0x0885b5dc`) are imported but **not called** by `rel_field`, `rel_story` or `rel_shop` either (their thunks have no call sites), so these bytes are still unexplained.
- **Per-row state in the save**: two bytes per table row at save `+0x1bf8c + 2r` (`save_get_character_flags`, `0x0885519c`; `save_get_character_flags_by_key(c, v)`, `0x08855178`). Byte 0 bits 0–3 and byte 1 bit 0 are flags with set/test pairs (`0x088551d4`–`0x08855548`), byte 1 bits 1–3 and 4–6 are 3-bit values. Bit 2 of byte 0 (`save_test_character_flag_bit2`, `0x08855378`) gates shop packs (below); its meaning (met, beaten, …) is open.
- **Runtime records** in `rel_story`: 141 records of `0x5c` bytes (`*(0x08ecd964)`), binary-searched by the key at `+0x1c` (`0x08e9d594`); `+0x54` is a bit set tested by `0x08e9d6c8(key, bit)`.
- **On the map**: characters are placed by the event set-up pass (`npc_position`, `npc_direction`, `npc_event`, … in `story.md`) of the record that the driver runs for the current location and time; the field module receives them through requests 8 and 3. Which record is chosen for a given location, day and slot (the schedule) is not decoded.
- **Conversation records**: event records with header `a1` 1–153 are per-character (`a1` = character id, about 50 keys each, `a2` 1–10 a situation group, `a3` a running number; groups contain the "Yes, I'll go" partner offer (`exit_111`) and booster gifts). Records with `a1` 201–218 are story chapters, 301 duel follow-ups, 501 one record.

## Friendship points and the partner

- Points: `u16` at `+0x16` of the 143 save character records (`save.md`), 0–8000.
- Story scripts change them with `world_change_char_points(char, delta)` (`rel_story` `0x08e9d9c0`, called from opcodes 50084/50085): the new value is clamped to `[0, cap]` with **cap = `world_get_points_cap()`** (`0x08eab450`) = table `rel_story` `+0x2e528` indexed by the story stage: stage 1 → 1000, 2 → 2000, …, 8 and 9 → 8000. So friendship can only grow as the story advances (high for the code, medium for the reading). The return value (+1 / −1 / 0) drives the up/down/no-change display (field request 28).
- **Partner**: `u16` at save `+0x16e12` (`save_get_partner_field`, `0x08857be8`): bits 4–11 character, bits 12–15 variant, bit 0 a flag (`0x08857cd8`). `save_get_partner(&variant)` (`0x088550c8`) and `save_set_partner(c, v)` (`0x08855110`). The partner chooses the deck slot (`0x08856730`) and unlocks partner packs in the shop.

## Money and level

- **DP**: `u32` at save `+0xfdfc` (`save_get_player_value(0)`, read by `if_dp`); `save_add_dp(n)` (`0x08854ba0`) clamps to 0–999,999,999. Story `dp_add`/`dp_sub` go through field request 24 (display) (medium).
- **Duelist level**: `u32` at `+0xfdf4` holds level − 1 (`save_get_duelist_level`, `0x08854990`, returns `+1`); `+0xfdf8` is the EXP. `save_add_duelist_exp(n)` (`0x088549bc`) adds EXP and raises the level while EXP reaches `save_get_level_exp_threshold(level + 1)` (`0x08855e08`); the stored value stops at 98 (level 99). Basis: the field strings "Duelist Level", "Duelist Exp", "Until next Level" and the shop thresholds 21–50 (medium).
- Name and team name: `+0xfd5c` (0x32 bytes, `0x08854948`/`0x088548d8`) and `+0xfd8e` (100 bytes, `0x0885496c`/`0x08854910`) (medium; "Team Name:" on the status screen).

## Items and gifts

- Items are numbered 1–50 (sandwiches, 50 = golden-egg sandwich with its own model `for_bread.ehp`/`goldegg_pan.tms`) and 101–104 (four event items); names and descriptions in `field_strtbl_item.bin` (`field-tables.md`). The item menu offers **Eat** and **Give** (`field_strtbl.bin` 7–13); giving needs a character next to the player ("There's no one to give it to!").
- Sandwiches are bought from the two sandwich sellers (characters 26 and 27): their records end with `exit_102` (exit code 102), after `if_dp ≥ 200` and `dp_sub 200`; `give_random_card` (50098) is the "card inside the sandwich" lottery.
- Not found yet: where the item inventory is stored and the code of Eat/Give (and how much a gift adds to the points). The story opcode set has no item opcode, so Give is presumably handled by the field module or the event driver.

## Card shop: pack availability

`rel_shop` `0x090d9264` first calls `0x090d9e5c` and then copies every pack's save state into the shop's pack table; `0x090d9e5c` (5,924 bytes) recomputes the 48 pack states with `save_set_pack_state(p, s)` (`save.md`). States: 0 not available, 1 was available but its condition no longer holds (greyed), 2 on sale, bit 2 (4) "unlocked by the story" (`set_pack_state 60000` in scripts), turned into 2 at the next visit. Rules, in order (medium; static reading of the decompilation):

| Packs | Condition for state 2 |
| --- | --- |
| 0–2 | Always. |
| 3–8 | Pack `p − 3` at least 50% collected: `0x090d9cec(p)` = owned cards of the pack's four tiers × 1000 / total ≥ 500. |
| 9–14 | A shop-local value `*(0x090faa70) >> 4` equals 1–6 (source not found; else demoted to 1). |
| 15, 16 | Save flag `+0x1c0e9` bit 4 and the partner's points < 2000 (15) or 2000–4000 (16). |
| 17–23 | Partner is character 2–8 (else 1). |
| 24–33 | Partner in a per-pack character list (ids from 9 to 120, some with a variant condition). |
| 34, 47 | `0x08836e10()` > 599 / > 899 (presumably a collection count). |
| 35–38, 40 | Save counters `+0x11444` > 49,999, `+0x11448` > 99,999, `+0x1144c` > 399, `+0x11460` > 49,999, `+0x11464` > 4,499 (meaning open). |
| 39, 43, 44, 45 | Save flag bits `+0x1c0e9` bit 5, bit 1, bit 7, `+0x1c0ea` bit 0. |
| 41, 42 | Character 26 (variant 0) / 27 (variant 1) has row flag bit 2, combined with bit 0 of the shop byte `0x0973ad50` (set by `0x090db590(mode)`): presumably which of the two counters is open (low). |
| 46 | Shop byte `0x090facf6` bit 0. |
| 9–33, 47 | Also: duelist level > 20 + (p − 9) for packs 9–33, level > 49 for 47. |
| 9–47 | Also: `0x090d9dd4()` (per mille of the flagged entries of a 104-entry list at `0x090ef208` whose byte at duel-record block `+0x494 + 0x14c + n` is set; presumably opponents beaten) above 100–1000, a threshold per pack. |
| 3–41 | All, when every variant of characters 2–8 (except 2/2) has row flag bit 2. |

The 12-byte pack records of the shop table (`docs/formats/packs.md`) are partly runtime: `0x090d9264` writes the save state into bits 0–1 of byte 0 and a value from `0x090d9550` into byte 1, so the static `a` word (20 or 40) only contributes `byte0 >> 2` = 5 or 10 (`0x090d94dc`; hypothesis, medium: cards per pack). `+4` is read by `0x090d9414` and multiplied by `0x090d9438(n)` (a factor; for `n` = 1 the sum of the two nibbles of the save pack byte 0, which `save_reset_packs` sets to `0xaa`, giving 20), so `+4` is a unit price (medium). `+6` is read by `0x090d9508`.

## Key functions

Registry names (`re/names.csv`, `re/names-rel_field.csv`, `re/names-rel_story.csv`); evidence above.

| Address | Name | Conf. |
| --- | --- | --- |
| `0x08854990` | `save_get_duelist_level() → level` | M |
| `0x088549bc` | `save_add_duelist_exp(exp)` | M |
| `0x08855e08` | `save_get_level_exp_threshold(level) → exp` (0 for level > 99) | M |
| `0x08854ba0` | `save_add_dp(delta)` | M |
| `0x088550c8` / `0x08855110` | `save_get_partner(&variant) → char` / `save_set_partner(char, variant)` | M |
| `0x08857be8` / `0x08857cac` | `save_get_partner_field() → state+0x16e12` / `save_copy_partner_field(out)` | H (code) |
| `0x0885519c` / `0x08855178` | `save_get_character_flags(row)` / `…_by_key(char, variant)` | H (code) |
| `0x08855378` | `save_test_character_flag_bit2(char, variant)` | H (code) |
| `0x08857c5c` | `save_get_story_block() → state+0x16e14` | H (code) |
| `0x0885aca0` / `0x0885ad14` / `0x0885b0b0` | `world_find_character_row`, `world_get_character_key`, `world_count_character_variants` | H |
| `0x088581bc`–`0x08858304` | `system_wcscmp`, `system_wcslen`, `system_wcsindex`, `system_wcscpy`, `system_wcscat`, `system_wcsncat` (UTF-16 string helpers) | H |
| `rel_field 0x090d1144` | `world_map_id_to_index(M)` | H |
| `rel_field 0x090d9f3c` | `world_get_current_map()` | M |
| `rel_field 0x090d9f48` | `world_bind_map_archive(ehp)`: binds meshes, masks, doors, `.hmp` | M |
| `rel_story 0x08eaabd8` | `world_set_calendar_blocks(calendar, field_block, flags)` (caller `0x08e9f3ac`, story init) | H (code) |
| `rel_story 0x08eaac3c` | `world_init_calendar()` (new game) | M |
| `rel_story 0x08eac278` | `world_update_calendar()` | H (code) |
| `rel_story 0x08eaacc8`, `0x08eaace0`, `0x08eab070`, `0x08eab0bc` | time-advance functions | M |
| `rel_story 0x08eaac88`, `0x08eaac98`, `0x08eaaca8` | day index, time slot, light period getters | M |
| `rel_story 0x08eaacf8` | `world_is_day_off(offset)` | L |
| `rel_story 0x08eab3c0` / `0x08eab3fc` | `world_advance_story_stage` / `world_get_story_stage` | M |
| `rel_story 0x08eab450` | `world_get_points_cap()` | M |
| `rel_story 0x08e9d9c0` | `world_change_char_points(char, delta) → +1/−1/0` | H |
| `rel_story 0x08eab224`, `0x08eab124`, `0x08ea0860` | exit-cell selection and request 3 | M |
| `rel_shop 0x090d9e5c`, `0x090d9cec`, `0x090d9264`, `0x090d9dd4` | shop pack-unlock rules, pack completion ‰, load pack states, opponent ratio ‰ (not in a names file yet: there is no `re/names-rel_shop.csv`) | M |

## Save fields found here

Additions to `docs/formats/save.md` (offsets in the game state / `DATA0`):

| Offset | Content |
| --- | --- |
| `0x0fd5c` | Player name (0x32 bytes). |
| `0x0fd8e` | Team name (100 bytes). |
| `0x0fdf4` | Duelist level − 1 (`u32`). |
| `0x0fdf8` | Duelist EXP (`u32`). |
| `0x0fdfc` | DP (`u32`). |
| `0x10f10` | Duel-record block (`0x08854c6c`; counters capped at 999,999 / 999; `+0x494` a sub-block). |
| `0x11444`–`0x11464` | `u32` counters read by the shop rules. |
| `0x161f4`, `0x161f6`, `0x162bc` | A count < 100 and two `u16[99]` lists (states 1–3 in the second); presumably the mail list (low). |
| `0x16e12` | Partner `u16`. |
| `0x16e14` | Story block: `+0x3438` calendar (0x24 bytes), `+0x345c` field save block (0xa8 bytes), `+0x42d8` flags. |
| `0x1bf8c` | 174 × 2 bytes: per character-table-row flags. |
| `0x1c0e8`–`0x1c0ea` | Single-bit progress flags (`0x08855660`–`0x08855ddc`), several used by the shop rules. |

## Open questions

- The event driver: which record runs for a location, day and slot (NPC schedules), and how Talk/Duel/Give pick a character's record (`npc_event` `(301, n)` keys, conversation groups `a2` 1–10).
- Item inventory location in the save, the Eat and Give code, and the points a gift adds (and whether character preferences exist; the character-table bytes `+0x44..+0x74` are a candidate but have no caller in the three modules).
- How the island map lists destinations; what the exit cells trigger on the field side (request 3 handler `rel_field` `0xa51c`).
- The source of the shop value `*(0x090faa70) >> 4` (packs 9–14), the meaning of the save counters `+0x11444…`, of `0x08836e10()`, and of character-row flag bit 2.
- The exact EXP table (`0x08855e08` was not read in full) and the month/date mapping of calendar `+0x08`/`+0x20`.
- Confirm in PPSSPP: the slot → period table against the island-map lighting, and the partner word.
