# Save data (work package 3)

Status: `documented` for the deck slots and the card collection; the rest of the 128 KiB is not mapped yet. Tool: `tools/save.py` (decks, collection, `--check`). Analysed on a plaintext save written by PPSSPP early in the game (one save; the player owned only the starting deck).

## On the memory stick

`PSP/SAVEDATA/ULES011830001/` holds `DATA0` (the game state), `PARAM.SFO`, `ICON0.PNG` and `PIC1.PNG`, written through the system's `sceUtilitySavedata` dialog. A retail-style save is encrypted by the PSP save-data layer: `DATA0` is then 131,088 bytes (the 131,072-byte buffer plus 16 bytes) with a byte entropy of 7.999 bits/byte. Decrypting it would circumvent platform protection (`CLAUDE.md`), so analysis uses saves that PPSSPP writes unencrypted (`EncryptSave = False` in `ppsspp.ini`): PPSSPP loads an encrypted save like the console and writes it back in plaintext.

## In the game

**Verified in PPSSPP (2026-10-26, [`results/2026-10-26-session0.md`](../verification/results/2026-10-26-session0.md))**: the shift word at `0x08ac18c0` read 11 and 7 on two boots, and the 16 bytes at `S + 0x10` equal `DATA0` `+0x10` (the OpenPSID), so `S = 0x08aa5794 + 4 × [0x08ac18c0]` is the block that `DATA0` copies.

| Address | Meaning |
| --- | --- |
| `0x08acda04` | `SceUtilitySavedataParam` block (`0x9d0` bytes, zeroed). |
| `0x08acda08` | Save buffer, `0x20000` bytes: the whole content of `DATA0`. |
| `0x08acda0c` | Buffer for a disc file loaded with the save (root 6, name from `0x088413ec`; presumably an icon or picture). |
| `0x08acda10` | `0x200`-byte work block. |
| `0x08acda00` | Heap the four blocks come from. |

`save_open(request, heap)` (`0x088410dc`, no direct caller: exported) stores `request` (u16) at `0x08acd9cc` and the heap at `0x08acda00`, allocates the four blocks with `system_heap_alloc` and queues `msd_e.ehp` (name from `save_get_resource_name`, `0x088413ec`) from root 6 (`main/`) into the buffer at `0x08acda0c`; its completion callback `save_on_resources_loaded` (`0x088410a8`) sets `0x08acd9f0` and binds the archive with `container_ehp_bind_with_callback`. It returns 0 if an allocation fails (after `save_close` for the later ones), else 1. `save_close` (`0x0883e3b4`; callers `0x0883eafc`, `0x0883eda4`, `0x0883f2dc`, `0x0883f984`, `0x088401f0`, `0x088409e4`, `0x08840d20`, `save_open`) frees them with `system_heap_free` and clears the pointers. Six functions fill the parameter block and call `sceUtilitySavedataInitStart` (`0x0883e694`, `0x0883e78c`, `0x0883e874`, `0x0883e918`, `0x0883e9e0`, `0x0883eaa4`). The two read so far set the mode at `+0x30` (8 and `0x16`), the data buffer at `+0x74` (`*0x08acda08`), buffer and data size at `+0x78`/`+0x7c` (`0x20000`), the file name `DATA0`, and copy a 16-byte value from `0x08879068` to `+0x5dc`, the field that holds the game's save-data key. This project records that the key exists and does not use it.

## `DATA0` layout

All integers little-endian. The buffer is a raw copy of in-memory structures: deck headers contain stale pointers into `BOOT.BIN` (for example `0x08859ac0`), unused bytes hold leftovers of other strings and `0xdeadbeef` fill.

| Offset | Size | Content | Confidence |
| --- | --- | --- | --- |
| `0x00000` | 4 | `0x00030000`, presumably a version. | low |
| `0x0000c` | 4 | `0xd79` in the analysed save; unknown. | — |
| `0x00010` | 16 | The console's OpenPSID: `save_init_new_game` fills it with `sceOpenPSIDGetOpenPSID(state + 0x10)`. | high (code) |
| `0x048c4` | 127 × `0x16c` | Deck slots 0–126 (below). The code addresses slot `s` at `0x48c4 + 0x16c`·s (`deck_get_slot_name` reads `+0x10`, `deck_get_slot_cards` returns `+0x50`); slot 1, at `0x4a30`, is the player's starting deck, slots 2–126 are the partners' decks. What slot 0 holds is not established. | high (code) |
| `0x0fd5c` | 16 | Player name: the system nickname (`sceUtilityGetSystemParamString(1)`), at most 8 UTF-16 units, `$` doubled. Starts right after slot 126. | high (code) |
| `0x0fdfc` | 4 × n | `u32` values read by `save_get_player_value(n)`. The first is **DP**, changed by `save_add_dp` (`0x08854ba0`) (verified in PPSSPP, `docs/verification/results/2026-10-27-sessionC.md`); the others are unknown. | H for DP |
| `0x0fe04` | 3+ | Settings bits (below). | high (code) |
| `0x0fe0c` | 143 × `0x18` | Per-character records 0–142 (below); they end exactly at `0x10b74`. | high (code) |
| `0x10b74` | 2 × n | `u16` per entry: bit 0 set once, bits 1–8 a value written with it (`0x08857f2c`, pointer from `0x08857fa4`); meaning unknown. | — |
| `0x11ba4` | 3,554 × 4 | Card collection, one record per card-database record index (below). | high |
| `0x16582` | 0x80 | Name of the active forbidden/limited list, UTF-16 (the analysed save has a `2008/03` date). Written by `deck_set_limit_list_name`, called from `deck_reset_limits`. | medium |
| `0x16602` | 2 | Counter capped at 2000 (`0x0885761c` adds, `0x08857670` reads); meaning unknown. | — |
| `0x16604` | 48 × `0x2a` | Pack records (below). | high (code) |
| `0x16de4` | 0x26 | Bytes that only grow (`0x08856080` keeps the maximum); meaning unknown. | — |
| `0x16e10` – `0x16e14` | | Single bytes and flags read by small getters `0x08857be8`–`0x08858078`; not decoded. | — |
| `0x1b0fc` | | Bit array set and cleared by `0x088580a0(bit, on)`. | — |
| up to `0x1c0ec` | | `save_init_new_game` clears `0x1c0ec` bytes: the size of the game state. | high (code) |

### Deck slot (`0x16c` bytes)

| Offset | Size | Field |
| --- | --- | --- |
| `0x00` | 4 | Stale pointer or 0. |
| `0x04` | 4 | Owner id (2, 3, 4, …): the character whose deck this is; 0 for the player's own slots. |
| `0x08` | 4 | 0. |
| `0x0c` | 4 | Recipe the deck was created from: the owner's first recipe in the recipe owner table (`deck.md`), for example 1 for owner 2 and 11 for owner 3. |
| `0x10` | 64 | Deck name, UTF-16, NUL-terminated (`Starting Deck`, `Partner's Deck`). |
| `0x50` | 12 | `u32` counts: main, side, extra. |
| `0x5c` | 120 | Main deck, up to 60 `u16` card ids. |
| `0xd4` | 30 | Side deck, up to 15 ids. |
| `0xf2` | 30 | Extra deck, up to 15 ids. |
| `0x110` | 92 | Unused in the analysed save (stale bytes). |

In the analysed save, slot 1 (`0x4a30`) is the player's `Starting Deck` (40 main, 15 side) and slots 2–126 are `Partner's Deck` records, one per partner character (owners 2–126), each seeded from that character's first recipe. An earlier reading of this save counted 21 further empty slots after them; the code shows that this region (`0xfd58` onwards) is the player name, settings and character records instead, so there are 127 slots. The offsets in the table below are relative to a slot's start. Every listed id exists, no card appears more than three times, extra decks hold only fusion and synchro monsters, and main decks hold none.

### Card collection (4 bytes per card)

Indexed by the card-database record index (`CARD_IntID` maps ids to it).

| Byte | Meaning | Basis |
| --- | --- | --- |
| 0 | Flags; 4 on every owned card. | Only owned cards have it set. |
| 1 | Copies owned. | Equals, for all 54 cards, the number of copies in the starting deck (55 in total), which is the whole collection at this point. |
| 2, bits 0–1 | Forbidden/limited status of the card for this save (0 forbidden, 1 limited, 2 semi-limited, 3 unlimited). | All 114 entries of the built-in list (`limit-list.md`) match, and every other card is 3. This is the per-save copy that `deck_reset_limits` seeds. |
| 3 | 0 in the analysed save. | — |

## Game-state accessors (`BOOT.BIN`)

The game keeps the state that `DATA0` copies in memory and reaches it only through `save_get_state()` (`0x08835dc4`, about 120 callers), which returns `0x08aa5794 + 4 × r`. `r` is the `u32` at `0x08ac18c0`, set once at boot by `system_init_game_globals` to `system_rand_shifted() & 15`, so the block moves by 0–60 bytes from boot to boot (presumably to hinder memory editing; medium). The collection offset `0x11ba4` and the deck-slot offsets match the `DATA0` layout above exactly, so the save buffer is a 1:1 copy of this block. Signatures are in `re/documented.tsv`.

**New game.** `save_init_new_game` (`0x08853e80`, no direct caller) clears `0x1c0ec` bytes, restores the language, copies the nickname, loads recipe 0 (`deck_load_recipe`), stores its lists in deck slot 1 (`0x088569fc`, `0x08856b84`) while adding each card with `save_change_card_count(id, 1)` and `save_clear_card_new`, names slot 1 after recipe 0 (`deck_get_recipe_name`, `0x088568a4`), writes the OpenPSID, calls `save_reset_options` and `deck_reset_limits` and stores version `0x30000` at `+0`.

**Card collection** (record from `save_get_card_record(id)`, `0x088560e4`: `state + 0x11ba4 + 4 × index`, 0 for index 0 and for tokens):

| Bits | Meaning | Accessors |
| --- | --- | --- |
| byte 0 bit 0 | Flag, meaning unknown. | set `0x088564a8`, get `0x088564e4` |
| byte 0 bits 1–2 | State: 0 never obtained, 1 new, 2 owned (the analysed save's value 4 = state 2). | `save_get_card_state` `0x08856370`, `save_is_card_new` `0x08856338`, `save_clear_card_new` `0x088562fc` (state 2) |
| byte 0 bit 3 | "Marked" flag used by the story script (`story.md`). | `card_db_is_card_marked` `0x0885654c`, `card_db_mark_card` `0x08856510` |
| byte 0 bits 4–6 | Value 0–7, meaning unknown. | set `0x0885657c` (caller `0x0884dbb0`), get `0x088565dc` |
| byte 0 bit 7 | Flag, meaning unknown (getter returns 1 without a record). | set `0x088563a0`, get `0x088563dc` |
| byte 1 bits 0–6 | Copies owned, 0–99. | `save_get_card_count` `0x0885615c` (callers `0x08835ebc`, `0x08836104`, `0x0885c660`, `0x0885ca28`), `save_set_card_count` `0x08856188`, `save_change_card_count` `0x08856248` (caller `save_init_new_game`) |
| byte 1 bit 7 | Flag, meaning unknown. | set `0x0885640c`, get `0x08856478` |
| byte 2 bits 0–1 | Limit status. | `deck_set_limit`, `deck_get_limit` (`deck.md`) |

`save_set_card_count(id, n)` sets the state to 2 if the card already had copies, else to 1 (`n > 0`) or 0. `save_change_card_count(id, 1)` adds a copy (at most 99) and turns state 0 into 1; `(id, 0)` removes one.

**Settings** (`save_get_settings()` = `state + 0xfe04`, `0x08857698`):

| Bits | Meaning | Accessors |
| --- | --- | --- |
| byte 0 bits 0–2 | Language: 0 Japanese, 1 English, 2 German, 3 French, 4 Italian, 5 Spanish (the order of the letters `jegfis` that `deck_get_recipe_name` indexes with it; `card_db_load_cardinfo` builds the archive name from the same index). | `save_get_language` `0x08857b80` (23 callers), `save_set_language` `0x08857ba4` (callers `save_init_new_game`, `0x08836adc`; also calls `0x088373c8`) |
| byte 0 bit 3, bits 4–5, bits 6–7 | Option fields, meaning unknown. | `0x08857860`/`0x088578c0`, `0x088577b4`/`0x0885778c`, `0x088576e4`/`0x088576bc` |
| byte 1 bits 0–2, bits 3–4; byte 2 bits 1–2 | Option fields, meaning unknown. | `0x0885774c`/`0x08857728`, `0x08857aac`/`0x08857af0`, `0x08857b18`/`0x08857b58` |
| byte 1 bits 5–7, byte 2 bits 0, 3, 4 | Six on/off options 0–5. | `save_set_option_flag` `0x088578f0`, `save_get_option_flag` `0x08857a00` |
| bytes 3 + n | 4-bit values. | `0x088577f8` / `0x08857834` |

`save_reset_options` (`0x0885442c`, callers `system_init_game_globals` and `save_init_new_game`) writes the defaults: options 0, 2, 5 on, 3, 4 off; byte 0 bit 3 set; `0x08841724(n, 12)` for n = 0–2 (presumably volumes); and a 12-word block from `0x0885c084`.

**Characters** (`save_get_character_table()` = `state + 0xfe0c`, `0x08857c10`; record `c` = `save_get_character_record(c)`, `0x08857d9c`, 0x18 bytes): `+0x00 u16` list count, `+0x02` up to 10 `u16` entries (`save_add_character_entry`, `0x08857d0c`, caller `0x08854188`, appends without duplicates), `+0x16 u16` points, 0–8000 (`save_get_char_points` `0x08857dd0`, `save_set_char_points` `0x08857e08`, `save_add_char_points` `0x08857e68`, all clamped). `save_find_top_character` (`0x08857ed8`) returns the character 2–142 with the most points. `deck_select_owner_variant` reads character 8's points (threshold 2000), so the points are presumably friendship points (medium).

**Packs** (`save_get_pack_record(p)` = `state + 0x16604 + 0x2a × p` for `p < 48`, `0x088573d4`): byte 0 (set to `0xaa` by `save_reset_packs`, `0x088575c8`, caller `0x08854310`; accessors `0x0885742c`/`0x0885745c`), byte 1 bits 0–2 state (`save_set_pack_state` `0x08857484`, `save_get_pack_state` `0x088574d8`, caller `0x0885042c`), `+2` 20 `u16` entries (`save_get_pack_entries` `0x08857504`, `save_set_pack_entry` `0x0885752c`, `save_get_pack_entry` `0x0885757c`). 48 records match the game's 48 packs; what the state and entries mean is open.

`save_get_player_value(n)` (`0x08854b68`, exported) reads the `u32` at `state + 0xfdfc + 4n`.

**Free-roam fields** (from `docs/subsystems/world.md`, medium unless noted): `0xfd5c` player name (0x32 bytes), `0xfd8e` team name (100 bytes), `0xfdf4` duelist level − 1 and `0xfdf8` EXP (`save_get_duelist_level`, `save_add_duelist_exp`), `0xfdfc` DP (`save_add_dp`, clamp 0–999,999,999), `0x16e12` partner `u16` (bits 4–11 character, 12–15 variant; `save_get_partner`), `0x16e14` story block (calendar at `+0x3438`, field save block at `+0x345c`, flag block at `+0x42d8`; high for the offsets), `0x1bf8c` two flag bytes per character-table row (`save_get_character_flags`), `0x1c0e8`–`0x1c0ea` progress bits read by the shop (`0x1c0e9` bit 1 golden-egg sandwich bought, bit 2 all 50 sandwich kinds seen; high, code). Inside the story block (offsets from `0x16e14`, high for the offsets): `+0x0000` 140 runtime character records of `0x5c` bytes (location, cell, spot index, event keys, flag bits), `+0x3264` the event queue (8 × 12 bytes, ring index, last menu answer), `+0x32cc` the field state (location, player position, partner, current item, 50 item counters at `+0x94`), `+0x345c + 0x1c` the 140-byte daily pairing order, `+0x35b0` the 50-bit sandwich-seen set; layouts in `docs/subsystems/world.md`.

## Open questions

- What the pack record state and its 20 entries hold, the meaning of the unknown collection and option bits, and the counters at `0xfdfc` and `0x16602`.
- The unmapped regions (after the pack records, up to `0x1c0ec`): story progress, duel records, unlocks and DP. A second save that differs by one known action (for example buying one pack, with the DP before and after) will locate DP and confirm collection updates.
- Whether the game rejects a save whose OpenPSID at `0x10` differs from the console's.
- Which code copies the buffer to and from the game state; the meaning of collection byte 0 bits and of the other save modes (8, `0x16` and the four other callers).
