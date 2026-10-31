# Save data (work package 3)

Status: the whole 0x20000-byte `DATA0` is mapped without gaps (`python3 -I tools/save.py --check`); 4,850 bytes in five regions are still of unknown content and are listed as such. Tool: `tools/save.py` (`decks`, `collection`, `json` (every region decoded), `map`, `--check`). Analysed statically on `BOOT.BIN` and the modules (capstone, no Ghidra in this pass), and against one plaintext save written by PPSSPP early in the game (the player owned only the starting deck). Confidence per region is in the map; the PPSSPP experiments that would confirm the medium and low ones are at the end.

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

`save_open(request, heap)` (`0x088410dc`, no direct caller: exported) stores `request` (u16) at `0x08acd9cc` and the heap at `0x08acda00`, allocates the four blocks with `system_heap_alloc` and queues `msd_e.ehp` (name from `save_get_resource_name`, `0x088413ec`) from root 6 (`main/`) into the buffer at `0x08acda0c`; its completion callback `save_on_resources_loaded` (`0x088410a8`) sets `0x08acd9f0` and binds the archive with `container_ehp_bind_with_callback`. It returns 0 if an allocation fails (after `save_close` for the later ones), else 1. `save_close` (`0x0883e3b4`; callers `0x0883eafc`, `0x0883eda4`, `0x0883f2dc`, `0x0883f984`, `0x088401f0`, `0x088409e4`, `0x08840d20`, `save_open`) frees them with `system_heap_free` and clears the pointers. Six functions fill the parameter block and call `sceUtilitySavedataInitStart`; they set the mode at `+0x30`, the data buffer at `+0x74` (`*0x08acda08`), buffer and data size at `+0x78`/`+0x7c` (`0x20000`), the file name `DATA0`, and copy a 16-byte value from `0x08879068` to `+0x5dc`, the field that holds the game's save-data key. This project records that the key exists and does not use it.

| Function | Mode (`+0x30`) | Copy |
| --- | --- | --- |
| `save_start_autoload_dialog` `0x0883e874` | 0 (autoload) | — |
| `save_start_autosave_dialog` `0x0883e9e0` | 1 (autosave) | state → buffer before the call |
| `save_start_save_dialog` `0x0883e918` | 3 (save) | state → buffer before the call |
| `0x0883eaa4` | 7 | — |
| `0x0883e694` | 8 | — |
| `0x0883e78c` | `0x16` | — |

**The copy** (high, code): `save_get_state_size()` (`0x08835de0`) returns **`0x1c0ec`**. The two save functions `system_memcpy(param+0x74, save_get_state(), 0x1c0ec)`. The load tasks (`0x0883eafc` at `0x0883ec60`, `0x0883f984` at `0x0883fda8`) first compare buffer word 0 with `0x30000` (another value skips the copy and sets the task's result word `0x08acd9fc` to 3), then copy `0x1c0ec` bytes back into the state, call `save_store_psid_checksum` and `0x08835a88(1)`. So `DATA0` = the game state (`0x1c0ec` bytes) followed by `0x3f14` bytes that the game never copies (zero in the analysed save).

**State checksum** (high, code; corrected in the 2026-10-31 documentation round, which read the loop bound): `save_compute_psid_checksum` (`0x088370b8`) sums `(address & 0xffff) xor u16` over `0xe06e` halfwords from `S + 0x10` (the OpenPSID) to `S + 0x1c0ec`, i.e. the whole state after the first 16 bytes, and returns `~sum - 0xe06e`; `save_store_psid_checksum` (`0x08835d94`) keeps it in RAM at `0x08aa569c` (after every load and in `rel_title`), `save_clear_psid_checksum` (`0x08835db8`) clears it (new game), and `save_psid_checksum_changed` (`0x08835d68`, caller `rel_title +0x2c648`) compares. This detects edits of the state in memory (not only of its PSID); the name predates the finding; whether `rel_title` refuses a save made on another console was not read.

## `DATA0` offset map

All integers little-endian. The state is a raw copy of in-memory structures: unused bytes hold stale stack data (for example pointers into `BOOT.BIN` such as `0x08859ac0` at the end of a deck slot's key-card list). `tools/save.py` holds the same table (`save.py map`), and `save.py --check` fails if it has a gap or an overlap or does not end at `0x20000`. Confidence: H high, M medium, L low, — unknown content.

| Offset | Size | Content | Conf. | Basis |
| --- | --- | --- | --- | --- |
| `0x00000` | 4 | Version `0x30000`; the load path rejects another value. | H | `save_init_new_game` writes it; load tasks compare it. |
| `0x00004` | 8 | Two `u32`, **unknown** (0 in the analysed save). | — | No access through `save_get_state` found. |
| `0x0000c` | 4 | `u32` frame counter: +1 per main-loop iteration, saturating at `0xffffffff` (play time in frames; 3,449 in the analysed save). | M | `system_run_frame_services` (`0x088359f4`, formerly `save_tick_frame_counter`), called by `system_main`; also read by `rel_debug_menu`. |
| `0x00010` | 16 | The console's OpenPSID (`sceOpenPSIDGetOpenPSID(state + 0x10)`). | H | `save_init_new_game`; checksum above. |
| `0x00020` | 50 × `0x174` | Stored deck records (below). | M | `save_get_stored_deck(n)` = `+0x20 + 0x174n`; 50 records end exactly at the deck slots. |
| `0x048c8` | 127 × `0x16c` | Deck slots 0–126 (below). | H | `deck_get_slot_cards` (`+0x4914 + 0x16c·s`), `save_reset_deck_slot` (`+0x48c8`). |
| `0x0fd5c` | `0x32` | Player name: the system nickname, at most 8 UTF-16 units, `$` doubled. | H | `save_init_new_game`; `save_get_player_name` (`0x08854948`, 30 callers). |
| `0x0fd8e` | `0x64` | Team name, UTF-16. | M | `save_get_team_name` (`0x0885496c`; `rel_charalist`, `rel_title`, `rel_field`, `rel_story`). |
| `0x0fdf2` | 2 | Alignment. | M | No access. |
| `0x0fdf4` | 4 | Duelist level − 1 (0–98). | M | `save_get_duelist_level`, `save_add_duelist_exp`. |
| `0x0fdf8` | 4 | Duelist EXP. | M | same |
| `0x0fdfc` | 4 | DP, 0–999,999,999 (verified in PPSSPP, `results/2026-10-27-sessionC.md`). | H | `save_add_dp`, `save_get_player_value(0)`. |
| `0x0fe00` | 4 | Sum of the positive `save_add_dp` amounts (presumably total DP earned). | L | `save_add_dp`. |
| `0x0fe04` | 8 | Settings bits and nibbles (below). | H | `save_get_settings`. |
| `0x0fe0c` | 143 × `0x18` | Character records (below). | H | `save_get_character_record`. |
| `0x10b74` | 462 × 2 | Recipe table, one `u16` per deck recipe 0–461 (below). | H | `save_unlock_recipe`, `save_get_recipe_entry`. |
| `0x10f10` | `0x494` | Duel record: totals, streaks, 143 per-character records (below). | H | `save_add_duel_result`. |
| `0x113a4` | `0x800` | Record table (below): record values, minigame high scores, duel-bonus states. | M | `save_get_record_table`. |
| `0x11ba4` | 3,600 × 4 | Card collection, one record per card-database record index (below); 3,554 used, 46 spare. | H | `save_get_card_record`; the spare 46 records make the array exactly 3,600 long, up to the next array. |
| `0x153e4` | 3,600 | `u8` flag bytes (below). | M | `save_set_card_milestone_flag`, `rel_gallery`, `save_set_pack_bought`. |
| `0x161f4` | 2 | `u16` count (< 100) of the card list. | M | `save_get_card_list_count`, `save_set_card_list_count`. |
| `0x161f6` | 99 × 2 | Card list: `u16` card ids. | M | `save_get_card_list_entry`, `save_set_card_list_entry`. |
| `0x162bc` | 99 × 2 | Per-entry `u16` state of the card list (1–3). | M | `save_get_card_list_state`, `save_set_card_list_state`. |
| `0x16382` | `0x200` | Block copied whole in and out by the deck editor modules. | L | `save_read_edit_block` / `save_write_edit_block` (`rel_deck`, `rel_deckswap`, `rel_select_card`). |
| `0x16582` | `0x80` | Name of the active forbidden/limited list, UTF-16 (`2008/03` in the analysed save). | M | `deck_set_limit_list_name`. |
| `0x16602` | 2 | Packs bought in total, capped at 2,000. | M | `save_add_packs_bought`, `save_get_packs_bought`. |
| `0x16604` | 48 × `0x2a` | Pack records (below). | H | `save_get_pack_record`. |
| `0x16de4` | `0x26` | 38 bytes that only grow (below). | L | `save_raise_progress_byte`, `save_get_progress_byte`. |
| `0x16e0a` | 2 | Alignment. | M | No access. |
| `0x16e0c` | 4 | `u32` highest story cycle reached (partner word bits 1–3, below). | L | `save_set_story_cycle`, `save_advance_story_cycle`, `save_get_max_story_cycle`. |
| `0x16e10` | 1 | `u8` set by `rel_story` (`+0xa278`), read by `rel_duel_mgr` (6 sites) and `rel_title` (6). Meaning unknown. | L | `save_set_byte_16e10`, `save_get_byte_16e10`. |
| `0x16e11` | 1 | Bit 0: a random bit (`rand & 1`) drawn by the weekly pairing (`world_assign_daily_spots`); read by `rel_duel_mgr` and `rel_title`. Bits 1–7 unused. | M | `save_set_week_random_bit`, `save_get_week_random_bit`. |
| `0x16e12` | 2 | Partner word (below). | H | `save_get_partner_field`. |
| `0x16e14` | `0x42e8` | Story block of `rel_story` (below). | H | `save_get_story_block`; registration in `rel_story +0x49cc`. |
| `0x1b0fc` | 12 | Picture-seen bits: bit `n` set when story opcode 50111 shows picture `n` (ids 1–86). | M | `save_set_picture_seen` (`rel_story`), `save_test_picture_seen` (`rel_gallery`). The functions have no bound; 12 bytes cover the ids used. |
| `0x1b108` | `0xd04` | **Unknown** (3,332 bytes, 0 in the analysed save). | — | No access found in `BOOT.BIN` or any module. |
| `0x1be0c` | 4 | Minigame block 0, handed to `rel_blackjack`. | L | `save_get_minigame_block_0`. |
| `0x1be10` | 4 | Minigame block 1, handed to `rel_dodge`. | L | `save_get_minigame_block_1`. |
| `0x1be14` | 4 | Minigame block 2 (getter has no caller). | L | `save_get_minigame_block_2`. |
| `0x1be18` | `0x30` | Minigame block 3: 12 `u32` used by `rel_underground`; `save_reset_options` writes the defaults. | M | `save_get_minigame_block_3`. |
| `0x1be48` | 4 | Minigame block 6 (getter has no caller). | L | `save_get_minigame_block_6`. |
| `0x1be4c` | 4 | Minigame block 7 (getter has no caller). | L | `save_get_minigame_block_7`. |
| `0x1be50` | `0xbc` | Minigame block 8, handed to `rel_throw`; size by adjacency only. | L | `save_get_minigame_block_8`. |
| `0x1bf0c` | 12 | Three `u32` read and written as a triple by `rel_title` (`+0x3faf0`, `+0x3fa4c`, `+0x4089c`). | M | `save_read_title_words`, `save_write_title_words`. |
| `0x1bf18` | `0x74` | **Unknown** (116 bytes). | — | No access found. |
| `0x1bf8c` | 174 × 2 | Per character-table-row flags (`docs/subsystems/world.md`). | H | `save_get_character_flags`. |
| `0x1c0e8` | 3 | Single-bit progress flags (`0x08855660`–`0x08855ddc`; `0x1c0e9` bit 1 golden-egg sandwich bought, bit 2 all 50 sandwich kinds seen; shop rules in `world.md`). | H | set/test pairs. |
| `0x1c0eb` | 1 | Alignment to the state size. | M | — |
| `0x1c0ec` | `0x3f14` | Rest of the save buffer: never copied to or from the state; 0 in the analysed save. | H | `save_get_state_size`. |

Totals over the leaves of the map (sub-maps of the record table and the story block included): high 98,363 bytes (of which 16,148 the buffer tail), medium 27,090, low 769, unknown 4,850 (`0x00004` 8, story block `+0x3524` 4, record table `+0x292` 1,390, `0x1b108` 3,332, `0x1bf18` 116).

### Stored deck record (`0x174` bytes)

| Offset | Size | Field |
| --- | --- | --- |
| `0x000` | 4 | Flag (non-zero = used; hypothesis). |
| `0x004` | `0x50` | Deck name, UTF-16 (`0x40` used by the copies in `duel_setup_load_decks`). |
| `0x054` | `0xc0` | Deck lists: the `0xc0`-byte struct of `deck.md` (u32 counts main/side/extra, then 60 + 15 + 15 ids). |
| `0x114` | `0x60` | Key-card list: `u32 count` + 46 `u16` (`deck_get_recipe_card_list` format). |

Readers: `duel_setup_load_decks` (set-up code 463), `rel_recipeviewer`, `rel_title`, `rel_deck`. All 50 are empty in the analysed save. Meaning (the player's own saved decks) is a hypothesis, medium.

### Deck slot (`0x16c` bytes)

Slot `s` is at `0x48c8 + 0x16c·s`. The earlier version of this document placed the slots at `0x48c4`; the code (`save_reset_deck_slot`, `0x08854218`, writes `+0x48c8/+0x48cc/+0x48d0`, and `deck_get_slot_key_cards` returns `+0x49d4 + 0x16c·s`) shows that the struct starts 4 bytes later and ends with the key-card list.

| Offset | Size | Field |
| --- | --- | --- |
| `0x000` | 4 | Slot index = owner character id (2, 3, …; 0 for the player's slots 0 and 1). |
| `0x004` | 4 | Variant of the owner. |
| `0x008` | 4 | Recipe the deck was created from (`deck_get_owner_current_recipe`). |
| `0x00c` | 64 | Deck name, UTF-16, NUL-terminated (`Starting Deck`, `Partner's Deck`; `deck_set_slot_name`). |
| `0x04c` | 12 | `u32` counts: main, side, extra (start of the `0xc0`-byte deck struct, `deck_get_slot_cards`). |
| `0x058` | 120 | Main deck, up to 60 `u16` card ids. |
| `0x0d0` | 30 | Side deck, up to 15 ids. |
| `0x0ee` | 30 | Extra deck, up to 15 ids. |
| `0x10c` | `0x60` | Key-card list of the recipe: `u32 count` + 46 `u16` (only `count` valid; the rest is stale stack data). |

`save_init_partner_decks` (`0x088540dc`, from `save_init_new_game`) fills one slot per character 2–142 with `save_reset_deck_slot(char, variant)` for its first existing variant, which loads the owner's current recipe, copies its lists and key cards and names the slot with string `0x17`. Slot 1 is the player's `Starting Deck` (recipe 0, written by `save_init_new_game`). Slot 0 is empty in the analysed save; `0x08835ebc` (the count of free copies of a card: owned − copies in slot 0 + entries of the card list with states 1–3) treats slot 0 as a deck that holds owned cards, so slot 0 is presumably the deck being edited or the active deck (low). Every listed id exists, no card appears more than three times, extra decks hold only fusion and synchro monsters, and main decks hold none.

### Card collection (4 bytes per card)

Indexed by the card-database record index (`CARD_IntID` maps ids to it); 3,600 records of capacity, 3,554 used by the card database.

| Byte | Meaning | Basis |
| --- | --- | --- |
| 0 | Flags; 4 on every owned card (bits below). | Only owned cards have it set. |
| 1 | Copies owned. | Equals, for all 54 cards, the number of copies in the starting deck (55 in total), which is the whole collection at this point. |
| 2, bits 0–1 | Forbidden/limited status of the card for this save (0 forbidden, 1 limited, 2 semi-limited, 3 unlimited). | All 114 entries of the built-in list (`limit-list.md`) match, and every other card is 3. This is the per-save copy that `deck_reset_limits` seeds. |
| 3 | 0 in the analysed save. | — |

### Recipe table (`u16` × 462)

Entry `r` belongs to deck recipe `r` (`deck.md`). Bit 0: unlocked; bits 1–8: the owner character stored at unlock time. `save_unlock_recipe(recipe, owner)` (`0x08857f2c`) sets both only once. Callers: `rel_story +0x81c4` unlocks every recipe of the partner when the partner story is finished (`finish_partner_story`, `story.md`), `rel_story +0xde4c` after a duel (recipe and owner from the duel set-up), and `rel_debug_menu`. Readers: `rel_title +0x288f8` (recipes 1–461 with bit 0; `deck.md`), `rel_recipeviewer` (the recipe viewer), `rel_story +0xd2ec`. High (code).

### Duel record (`0x10f10`, `0x494` bytes)

| Offset | Size | Field |
| --- | --- | --- |
| `0x00` | 4 | Wins, capped at 999,999. |
| `0x04` | 4 | Losses. |
| `0x08` | 4 | Draws. |
| `0x0c` | 4 | Current win streak (reset by a loss or a draw). |
| `0x10` | 4 | Best win streak. |
| `0x14` | 4 | Current losing streak (reset by a win or a draw). |
| `0x18` | 4 | Worst losing streak. |
| `0x1c` | 143 × 8 | Per character id `c`: `u16` wins, losses, draws (capped at 999), `u16` unused. |

`save_add_duel_result(result, opponent, other)` (`0x08854d4c`; result 1 win, 2 loss, 3 draw; called twice by `rel_duel_eng`) updates the totals, the streaks and the records of `opponent` and of `other` (skipped when `other` is 1, the player; so presumably the second opponent of a tag duel). `save_get_duel_record(who, out[3])` returns the totals for `who` 0 and record 0 for `who` 1; `save_get_duel_count_vs(kind, c)` one count (callers `rel_charalist`, `rel_field`, `rel_story`). High for the layout, medium for "record 0 = the player's own row".

### Record table (`0x113a4`, `0x800` bytes)

| Offset | Size | Field | Conf. |
| --- | --- | --- | --- |
| `+0x000` | 49 × 4 | `u32` record values. `save_init_new_game` sets `[37]` = 599,940 and `[38]` = 999 (initial values of "smallest is best" records, such as the fastest win and the fewest turns; hypothesis). `[40]`–`[48]` (`+0xa0`–`+0xc0`) are the **minigame high scores**: `save_get/set_minigame_record_0..8`. `rel_duelrecord` lists the values with text ids from `0x1020`. | M |
| `+0x0c4` | 49 | "New record" bits per value (bits 0–1); `rel_duelrecord` shows and clears them; the minigame result routine sets `+0xec + k`. | M |
| `+0x0f5` | 3 | Alignment. | M |
| `+0x0f8` | 84 | Set-once flags: `rel_duel_eng +0x1204` sets `[n]` to 1 and returns whether it was new; `rel_duelrecord` writes 2 after showing. A loop over 82 cases in `rel_duel_eng +0x1ae0` evaluates them. | M |
| `+0x14c` | 108 | Duel-bonus state per entry: 0 never, 1 first time, 2 again (`rel_duel_eng +0x1244`; read by `rel_shop +0xb0dc` and `rel_duelrecord`). | M |
| `+0x1b8` | 108 × 2 | `s16` best value per entry (`rel_duel_eng` stores the new value when it beats the old one; `rel_duel_mgr +0x8624` reads it). | M |
| `+0x290` | 2 | `s16` selector, read by `rel_duel_eng +0x27e4` (switch on values < 118) and `rel_duelrecord`; writer not found. | L |
| `+0x292` | `0x56e` | **Unknown** (1,390 bytes). | — |

The minigame high scores are written by a result routine that every minigame module carries a copy of (`rel_blackjack +0xd4b8`, `rel_connection +0xce6c`, `rel_dodge +0xdbc8`, `rel_quiz +0x82e8`, `rel_reversi +0x8194`, `rel_throw +0x1e34`, `rel_underground +0xfacc`, `rel_title +0x3b830`): it switches on a minigame index 0–6, derives a reward value from the score (for example score / 50, stored in the routine's work block; that it is DP is not checked), and when the score beats `save_get_minigame_record_k` stores it and sets the new-record bit. The shop rules (`world.md`) test records 0 (> 49,999), 1 (> 99,999), 2 (> 399), 7 (> 49,999) and 8 (> 4,499) for packs 35–38 and 40. Which minigame owns which of the nine values is not established (seven switch cases, nine values; low).

### Flag bytes (`0x153e4`, 3,600 bytes)

One `u8` per index. Used indices: 0–69 are read by `rel_gallery` through a byte table at `rel_gallery +0x8a34` (70 unlock entries) and written by `save_set_card_milestone_flag` (`0x088544f8`, for 13 card ids, from `duel_core_record_duel_result`); 70–117 (`0x1542a + p`) are the per-pack "bought once" bytes of `save_set_pack_bought(p)`. The other 3,482 bytes have no reader. That the array has 3,600 entries, the capacity of the collection, suggests one byte per card-database index that the game uses only partly (medium for the bounds, low for that reading).

### Card list (`0x161f4`)

A `u16` count (< 100), 99 `u16` card ids and 99 `u16` states (1–3). Written by `rel_deck` and `rel_select_card`; read by `rel_deck`, `rel_decktutorial`, `rel_deckswap`, `rel_limitlist`, `rel_recipeviewer`, `rel_select_card`, `rel_shop`, `rel_duel_mgr`, `rel_labo` and by `0x08835ebc`/`0x08836104`, which add the entries with states 1–3 back to the free copies of a card. The shop's pack results show the copies of a card in this list (`packs.md`). Presumably a list of cards set aside by the deck editor (low).

### Progress bytes (`0x16de4`, 38 bytes)

`save_raise_progress_byte(n, v)` keeps the maximum (`n < 38`); `rel_deck` reads and raises entries, and `rel_story`'s new-day code raises entry 2 to 1 once the day index exceeds 8 (`world_change_time`). Presumably tutorial or help-page progress (low).

### Settings (`0xfe04`, 8 bytes)

| Bits | Meaning | Accessors |
| --- | --- | --- |
| byte 0 bits 0–2 | Language: 0 Japanese, 1 English, 2 German, 3 French, 4 Italian, 5 Spanish (the order of the letters `jegfis` that `deck_get_recipe_name` indexes with it; `card_db_load_cardinfo` builds the archive name from the same index). | `save_get_language` `0x08857b80` (23 callers), `save_set_language` `0x08857ba4` (callers `save_init_new_game`, `0x08836adc`; also calls `0x088373c8`) |
| byte 0 bit 3 | **Tutorial** (1 on). | `0x08857860`/`0x088578c0` |
| byte 0 bits 4–5 | **Message speed**: 0 slow, 1 normal, 2 fast. | `0x088577b4`/`0x0885778c` |
| byte 0 bits 6–7 | Option field, meaning unknown (0 in every save read). | `0x088576e4`/`0x088576bc` |
| byte 1 bits 0–2 | Option field, meaning unknown (0 in every save read). | `0x0885774c`/`0x08857728` |
| byte 1 bits 3–4 | **Card animation**: 1 normal, 2 fast, 3 very fast (0 presumably slow). | `0x08857aac`/`0x08857af0` |
| byte 2 bits 1–2 | **Auto chain dialog**: 0 default, 1 all, 2 manual. | `0x08857b18`/`0x08857b58` |
| byte 1 bits 5–7, byte 2 bits 0, 3, 4 | Six on/off options: 0 = **Duel effects** (byte 1 bit 5), 1 = unknown (byte 1 bit 6, never set), 2 = **Activation confirm** (byte 1 bit 7), 3 = **Auto draw** (byte 2 bit 0), 4 = **Card placement manual** (byte 2 bit 3; 0 = auto), 5 = **Destiny draw** (byte 2 bit 4). | `save_set_option_flag` `0x088578f0`, `save_get_option_flag` `0x08857a00` |
| bytes 3–7 | One 4-bit value per byte (`settings[3 + n]`, low nibble): byte 3 **BGM volume**, byte 4 **SE volume** (stored as the shown value − 1: 13 on screen = 12), byte 5 a third volume (12, not shown on the options screen), bytes 6–7 unused (0). | `0x088577f8` (set) / `0x08857834` (get); `0x08841724`/`0x088416f8` |

The option meanings were verified in PPSSPP by changing one option at a time on the title options screen and reading the eight bytes after each change (`docs/verification/results/2026-10-31-sessionE-T.md`, E5 and E5b; high). The defaults written by `save_reset_options` therefore mean: tutorial on, duel effects, activation confirm and destiny draw on, auto draw off, card placement auto.

`save_reset_options` (`0x0885442c`, callers `system_init_game_globals` and `save_init_new_game`) writes the defaults: options 0, 2, 5 on, 3, 4 off; byte 0 bit 3 set; `0x08841724(n, 12)` for n = 0–2 (presumably three volumes, 12 each in the analysed save); and the 12 words of minigame block 3 (`0x1be18`) from `save_get_minigame_block_3`.

### Characters (`0xfe0c`, 143 × `0x18`)

`save_get_character_table()` = `state + 0xfe0c` (`0x08857c10`); record `c` = `save_get_character_record(c)` (`0x08857d9c`): `+0x00 u16` list count, `+0x02` up to 10 `u16` entries (`save_add_character_entry`, `0x08857d0c`, caller `save_init_character` `0x08854188` and `rel_story`, appends without duplicates; `save_init_character` adds the character's first recipe), `+0x16 u16` points, 0–8000 (`save_get_char_points` `0x08857dd0`, `save_set_char_points` `0x08857e08`, `save_add_char_points` `0x08857e68`, all clamped). `save_find_top_character` (`0x08857ed8`) returns the character 2–142 with the most points. `deck_select_owner_variant` reads character 8's points (threshold 2000), so the points are presumably friendship points (medium).

### Packs (`0x16604`, 48 × `0x2a`)

`save_get_pack_record(p)` = `state + 0x16604 + 0x2a × p` for `p < 48` (`0x088573d4`): byte 0 the **shelf stock**, two nibbles of up to 10 packs (set to `0xaa` by `save_reset_packs`, `0x088575c8`, caller `save_set_story_cycle`; `save_set_pack_stock` `0x0885742c` / `save_get_pack_stock` `0x0885745c`), byte 1 bits 0–2 sale state (`save_set_pack_state` `0x08857484`, `save_get_pack_state` `0x088574d8`, caller `0x0885042c`), `+2` 20 `u16` entries, the **rarity box**: the rarity (1–3) drawn for each pack of the current box of 20, 0 = not yet drawn (`save_get_pack_entries` `0x08857504`, `save_set_pack_entry` `0x0885752c`, `save_get_pack_entry` `0x0885757c`). Meanings from the shop code (`docs/formats/packs.md`, high).

### Partner word (`0x16e12`)

`u16`: bit 0 a flag (`save_set_partner_flag`, `0x08857cd8`; cleared by the two cycle functions); bits 1–3 the **story cycle** 1–3; bits 4–11 the partner character, bits 12–15 its variant (`save_get_partner`, `save_set_partner`; `world.md`). `save_set_story_cycle(n)` (`0x08854310`, caller `rel_title +0x6db4` with the cycle of a stored partner word) sets bits 1–3 to `n`, refills every pack shelf (`save_reset_packs`) and raises `0x16e0c` to `n`; `save_advance_story_cycle` (`0x088543a0`, caller `rel_story +0x9224`) clears bit 0, computes the next cycle (1 → 2 → 3 → 1) and raises `0x16e0c` to it, but does not write the new cycle back into bits 1–3 (read in the disassembly, 2026-10-31). That this counts play-throughs of the story is a hypothesis (low). This answers the earlier open question about the low 4 bits of the partner word (value 3 for Jaden = flag 1 + cycle 1).

### Story block (`0x16e14`, `0x42e8` bytes)

Registered by the story init (`rel_story +0x49cc`); blocks and sizes from the per-block clear functions. Layouts of the records and the field blocks are in `docs/subsystems/world.md`.

| Story offset | State offset | Size | Content | Conf. |
| --- | --- | --- | --- | --- |
| `+0x0000` | `0x16e14` | 140 × `0x5c` | Runtime character records. | H |
| `+0x3250` | `0x1a064` | `0x14` | Block cleared by `rel_story +0x748` (`+0x10` last partner points seen). | M |
| `+0x3264` | `0x1a078` | `0x68` | Event queue. | H |
| `+0x32cc` | `0x1a0e0` | `0x16c` | Field state (cleared by `rel_story +0xac70`). | H |
| `+0x3438` | `0x1a24c` | `0x24` | Calendar. | H |
| `+0x345c` | `0x1a270` | `0xa8` | Field save block (stage, chapter step, flags, pairing order). | H |
| `+0x3504` | `0x1a318` | `0x20` | Block cleared by `rel_story +0xa65c`. | M |
| `+0x3524` | `0x1a338` | 4 | **Unknown**: no block covers it. | — |
| `+0x3528` | `0x1a33c` | `0x48` | Block cleared by `rel_story +0x9784`. | M |
| `+0x3570` | `0x1a384` | `0xc` | Block cleared by `rel_story +0xa958`. | M |
| `+0x357c` | `0x1a390` | 8 | Block cleared by `rel_story +0xac18`. | M |
| `+0x3584` | `0x1a398` | `0xc` | Block cleared by `rel_story +0xfc20` (words 0, 1 reset to −1). | M |
| `+0x3590` | `0x1a3a4` | `0x20` | 256 flag bits `1–256` (`rel_story +0x644` set/clear, `+0x6b4` test). | H |
| `+0x35b0` | `0x1a3c4` | 8 | 50-bit sandwich-seen set. | H |
| `+0x35b8` | `0x1a3cc` | 140 × `0x18` | Second set of character records, sorted by the character id at `+0` (binary search at `rel_story +0x2b24`). | M |
| `+0x42d8` | `0x1b0ec` | `0x10` | Story flags 129–192 (`+0`, `+4`), system flags 65–128 (`+8`, `+0xc`). | H |

## Game-state accessors (`BOOT.BIN`)

The game keeps the state that `DATA0` copies in memory and reaches it only through `save_get_state()` (`0x08835dc4`, about 120 callers), which returns `0x08aa5794 + 4 × r`. `r` is the `u32` at `0x08ac18c0`, set once at boot by `system_init_game_globals` to `system_rand_shifted() & 15`, so the block moves by 0–60 bytes from boot to boot (presumably to hinder memory editing; medium). Signatures are in `re/documented.tsv`; names of the accessors read in this pass are in `re/names.csv` (group `save`).

**New game.** `save_init_new_game` (`0x08853e80`, no direct caller) clears `0x1c0ec` bytes, restores the language, copies the nickname, loads recipe 0 (`deck_load_recipe`), stores its lists in deck slot 1 (`0x088569fc`, `0x08856b84`) while adding each card with `save_change_card_count(id, 1)` and `save_clear_card_new`, stores its key cards and names slot 1 after recipe 0 (`deck_get_recipe_name`, `0x088568a4`), writes the OpenPSID, calls `save_reset_options` and `deck_reset_limits`, sets record values 37 and 38 to 599,940 and 999, stores version `0x30000` at `+0`, clears the PSID checksum and runs `save_init_partner_decks`.

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

`save_get_player_value(n)` (`0x08854b68`, exported) reads the `u32` at `state + 0xfdfc + 4n`.

## How the map was built

A capstone pass over `BOOT.BIN` and all 36 modules (scratch script, not in the repository) followed every call to `save_get_state` and to the 28 getters that return `state + k`, tracked the register that holds the pointer through moves, constant additions and calls (callee-saved registers survive), and recorded every load, store and call argument relative to the state, including indexed accesses. Module calls were resolved through the import stubs (NIDs of `libehsys_rel`). Each region of the map is backed by at least one of those accesses, a clear routine with a size, or the exact adjacency of two arrays (marked M or L). The unknown regions are those no access reaches; an access through a pointer kept in a module global (as the minigame blocks are) is not followed, so a later trace may still find readers there.

## PPSSPP experiments (differential saves)

Each experiment: save in PPSSPP with `EncryptSave = False`, do one action, save again, and compare the two `DATA0` with `save.py json` (or a byte diff). Expected changes are listed; anything else that changes is new information for the map.

| # | Region (conf.) | In the game | Bytes that should change |
| --- | --- | --- | --- |
| 1 | `0x0000c` frame counter (M) | Save twice, 60 s of play apart, without other actions. | `+0x0c` grows by about 3,600 (60 fps) or 1,800 (30 fps); nothing else apart from the calendar. |
| 2 | `0x00004` (—) | Same pair of saves; also compare a save made after loading from the title screen. | Expect no change; any change identifies the field. |
| 3 | Duel record `0x10f10` (H), record table (M) | Win one single duel against a known character `c`. | `0x10f10` +1, `0x10f1c` +1, `0x10f20` = max; `0x10f2c + 8c` +1; some record values `0x113a4 + 4i` and bits `0x11468 + i`; bonus bytes `0x1149c`/`0x114f0`/`0x1155c` for the bonuses shown after the duel (note them). |
| 4 | Duel record (H) | Lose one duel; then win a tag duel. | Loss fields and streaks as in `save_add_duel_result`; the tag win also updates the second opponent's row (confirms `other`). |
| 5 | Recipe table `0x10b74` (H, meaning) | Win the first duel against a character whose deck was not unlocked. | Bit 0 and the owner bits of that recipe's `u16`. |
| 6 | Record table, minigame scores (M) | Play each minigame once (blackjack, connection, dodge, quiz, reversi, throw, underground) and note the score. | One of `0x11444`–`0x11464` per game and its new bit `0x11490 + k`: gives the index → minigame mapping; DP rises by the reward. |
| 7 | Minigame blocks `0x1be0c`–`0x1bf0b` (L) | Same sessions; change settings inside each minigame if it has any. | The block handed to that minigame (blackjack `0x1be0c`, dodge `0x1be10`, underground `0x1be18`, throw `0x1be50`); confirms sizes. |
| 8 | Card list `0x161f4` (M, meaning L) and edit block `0x16382` (L) | In the deck editor, take cards out of / put cards in the deck, change sort or filter, and save. | Count and entries at `0x161f4`, states at `0x162bc`; the `0x200`-byte block if it holds editor settings; deck slot 0 or 1 lists. |
| 9 | Stored decks `0x20` (M) | Save a deck under a new name in the deck editor (if the menu exists). | Flag, name and lists of stored record 0. |
| 10 | Flag bytes `0x153e4` (M) | Buy one pack of a kind never bought; open the gallery after a story picture. | `0x1542a + p` = 1 (and `0x16602` +1, one rarity entry of pack `p`, DP − price); a gallery index 0–69 if a milestone card was used. |
| 11 | Picture bits `0x1b0fc` (M) | Watch an event that shows a picture (opcode 50111). | Bit `id` of `0x1b0fc`. |
| 12 | Progress bytes `0x16de4` (L) | Open each deck-editor help page or tutorial for the first time; advance past day 8. | Bytes `0x16de4 + n` grow (entry 2 → 1 after day 8). |
| 13 | `0x16e10`, `0x16e11` (L, M) | Save before and after the weekly pairing (Monday), and around the event that `rel_story +0xa278` handles. | `0x16e11` bit 0 may flip on Monday; record when `0x16e10` changes. |
| 14 | Story cycle (L) | Finish the story and continue into the next cycle (if offered). | Partner word bits 1–3 and `0x16e0c`; all pack stocks back to `0xaa`. |
| 15 | Unknown `0x1b108`, `0x1bf18`, record table `+0x292` (—) | Diff every pair above. | Any non-zero byte here locates a field the static pass missed. |
| 16 | Title words `0x1bf0c` (M) | Change options on the title screen / extras menu. | The three words at `0x1bf0c`. |

## Open questions

- The meaning of the unknown collection and option bits.
- The five unknown regions (4,850 bytes, listed in the map); the readers of the minigame blocks inside the modules (pointers kept in module globals were not followed).
- Which minigame owns each of the nine high scores, and what the 49 record values and 108 duel-bonus entries are (text ids `0x1020` onwards in `rel_duelrecord` would name them).
- What slot 0, the stored decks and the card list hold (deck editor), and the content of the `0x200`-byte edit block.
- Whether `rel_title` rejects a save whose OpenPSID differs from the console's (the checksum only detects in-memory edits).
- The meaning of the other save modes (7, 8, `0x16`).
