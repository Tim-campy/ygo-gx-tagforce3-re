# Story text and event bytecode (`script/story_scr_*.ehp`)

Status:
- Text tables: `verified`. `tools/story.py text` exports all five languages, and its 59,985 lines are identical to ygotfToolkit's dump (see "Cross-check").
- Bytecode container: `reimplemented`. Records, instruction size and the text references are checked on the whole file.
- Opcode meanings: the interpreter in `rel_story.prx` is located and every handler of the 78 opcodes in use has been read (static analysis only, not traced in PPSSPP). Control flow is `documented`; the effects of individual opcodes carry their own confidence in the opcode table.

Exports go under `extracted/` and are never committed.

## Files

`PSP_GAME/USRDIR/script/` holds six EHP archives (`ehp.md`):

| Archive | Members |
| --- | --- |
| `story_scr_<l>.ehp`, `<l>` ∈ `e f g i s` (English, French, German, Italian, Spanish) | `EveI<l>.bin`, `EveL<l>.bin`, `SysMsgI<l>.bin`, `SysMsgL<l>.bin` |
| `story_scr_b.ehp` (language-independent) | `EveB.bin` (390,950 bytes), `EveBI.bin` (29,872 bytes) |

`gmodule/rel_story.prx` builds these names. At file offset `0x1a880` it has the language letters `j e g f i s` as a `u32` table. At `0x1a8b0` it has the strings `script/story_scr_`, `b.ehp`, `.ehp`, `EveB.bin`, `EveBI.bin`, `EveL`, `EveI`, `SysMsgL`, `SysMsgI`, `.bin`. So the story module loads one text archive per language plus the shared bytecode. `j` (Japanese) has no archive on the European disc.

All integers are little-endian.

## Text tables: `<T>I<l>.bin` + `<T>L<l>.bin`

`T` is `Eve` (event dialogue) or `SysMsg` (21 system messages).

- **`I` (index)**: `u32` offsets in **UTF-16 code units** (not bytes) into the `L` member, one per line plus a final sentinel. The first offset is 0. The offsets are strictly ascending. The sentinel equals the length of `L` in code units.
- **`L` (text)**: UTF-16LE strings, each terminated by one NUL code unit. Line `n` occupies `[2·I[n], 2·I[n+1])` bytes, NUL included. No padding, and no other NUL inside a line.

Line `n` has the same meaning in every language (same counts; the event bytecode refers to lines by number, see below). Counts, identical in all five languages: `Eve` 11,976 lines (158 empty, 159 in Italian), `SysMsg` 21. That gives 11,997 per language and 59,985 in total. `Eve` text sizes range from 528,850 (English) to 558,904 (German) code units. The longest line is 194 code units (French), with up to 10 rows (Spanish).

### Markup kept in the text

`tools/story.py` keeps all markup as stored. In CSV it writes newline as `\n` and backslash as `\\`.

| Markup | Meaning | Per language (Eve) |
| --- | --- | --- |
| `U+000A` | Line break inside the text box. | — |
| `《PLAYER》`, `《PARTNER》`, `《TEAM》` | Placeholders for the player's name, the partner's name and (presumably) the tag team's name. The brackets are `U+300A`/`U+300B`. | about 740 / 26–44 / 3 |
| `《Cnnn_k》` | `nnn` is a three-digit character number (53 distinct in English, 001–151), `k` is 1–5. Hypothesis, medium: a character's name in one of several forms (for example given name, family name, nickname). The same numbers appear as speaker ids in the bytecode. | about 1,440 |
| `《M025_1》`, `《TEST》`, `《BREAD》` | Rare tokens (2, 1 and 2 uses). In the Spanish `SysMsg`, `《BREAD》` and `《PARTNER》` are translated (`《PAN》`, `《COMPAÑERO》`), so there the brackets may be literal text. | — |
| `$M` + 4 digits | A card name by card id (for example `$M4766`). These are the same ids as `CARD_Prop` (3720–7993; `cardinfo.md`). | 96 |
| `$C` + digit | Text colour; `$C0` resets. The same escape as the duel prompts in `cardinfo.md`. | 16–20 |

No `$R` (furigana) occurs in the European text.

## Event bytecode: `EveB.bin` + `EveBI.bin`

- **`EveB.bin`**: a flat array of 39,095 **instructions of 10 bytes**, each `u16 opcode` followed by four `u16` arguments `a1..a4`. The file size is an exact multiple of 10.
- **`EveBI.bin`**: 7,468 `u32` values. Each is the index (in instructions, not bytes) of the first instruction of one **record** (event script). They are strictly ascending and start at 0. There is no sentinel: the last record ends at the end of `EveB`.
- **Record shape**, checked on all 7,468 records:
  - The first instruction is opcode 1 (header) with `a4 = 0`.
  - The last instruction is all zero (end).
  - Neither opcode 1 nor opcode 0 occurs in between.
  - The header triple `(a1, a2, a3)` is unique per record: `a1` 1–501 (175 distinct values), `a2` 1–121, `a3` 1–51. It is the record's **key**: the interpreter finds a record by searching the headers for it (`0xa67c`, below), and `goto` and the duel follow-ups name records by key. Hypothesis, low: `a1` selects a character or place and `a3` numbers the events within it.
  - 3,394 records are empty (header and end only). The longest has 373 instructions.
- **Opcode numbering**: apart from 0 and 1, all 78 opcodes used lie between 50,001 and 50,176 (`0xC351`–`0xC400`), that is 50,000 + n.

### How the bytecode refers to text

Five opcodes carry an `Eve` line number in **`a4`**. Together they reference all 11,976 lines **exactly once**, and **in ascending order** through the file. So line `n` is the `n`-th text instruction of `EveB`. This holds for each of the five languages, because the line counts are equal. `SysMsg` is not referenced by the bytecode.

The names are the ones `tools/story.py` prints; the full opcode table is under "Opcodes" below.

| Opcode | Count | `a1` | `a2` | `a3` | Meaning |
| --- | --- | --- | --- | --- | --- |
| 50001 `talk` | 9,234 | speaker, 2–141 | expression, 0–16 | flag 0/1 | A character speaks a line in a talk window with a portrait. |
| 50002 `talk_alt` | 1,324 | speaker | expression | flag | Same handler as 50001; the handler passes the opcode itself on, so only the presentation differs. |
| 50008 `narrate` | 651 | 0 | 0 | 0 | A line in the narration box, no speaker. |
| 50009 `narrate_named` | 563 | speaker | 0 | 0 | The same narration-box call as 50008 (`0x11ee4(text, speaker)`), with a speaker; no portrait. Was `talk_intro`. |
| 50011 `choice` | 204 | 0 | 0 | 0 | A menu: the line holds the options separated by newlines, with a trailing newline. See "Control flow". |

## The interpreter (`gmodule/rel_story.prx`)

Addresses in this section are **module offsets** of `rel_story.prx` (its runtime base is not known yet; file offset = offset + `0x54`, one `PT_LOAD` segment, like the other gmodules). The module was read with a small MIPS decoder; nothing is in Ghidra yet. Imports were resolved with `tools/prx_imports.py` (base 0): 1,556 stubs come from `BOOT.BIN`'s `libehsys_rel` (about 210 of them have names yet); the other 55 come from other modules' libraries, among them `libfield_rel` (`rel_field.prx`).

| Offset | What | Conf. | Evidence |
| --- | --- | --- | --- |
| `0xb9f4` | Interpreter `run()` (ends `0xc42c`) | H | Loads `code[pc].opcode` (`pc × 10`), subtracts 50,001, bounds-checks against 176 and jumps through the table at `0x19240`; each case calls a handler and increments `pc`. Only caller `0xb990`. |
| `0x19240` | Jump table, 176 entries, opcodes 50001–50176 | H | `lui 0x2; addiu -0x6dc0` in the dispatch; entries are case blocks inside `0xb9f4`. |
| `0x19500` | Second jump table, 15 entries, opcodes 50158–50172 | H | Set-up pass (below). |
| `0x33b30` | VM state: `+0` pointer to the record's header instruction, `+4` `pc` (instruction index in the record), `+8` an argument for the exit code, `+0xc` set by 50137, `+0x10` **exit code** (set by 50108, 50139/50140, 50150, 50152, 50176; reset to 116), `+0x14` set to 1 by `talk`/`narrate_named` | M | Loads and stores in the handlers and in `0xb284`. |
| `0xb284` | Start a record: `pc = 1` (skip the header), exit code 116 | M | Called from the driver at `0xb3c8`. |
| `0xa67c` | **Find a record by its header key** `(a1, a2, a3)`: walks the `EveBI` start table and returns the header instruction whose opcode is 1 and whose arguments match | H | Linear search over `EveBI`, compares `+2`, `+4`, `+6`. So the header triple is the key that events are addressed by. |
| `0xf370` | `skip_to(end_opcode, a1, a2, a3)`: advance `pc` to the next instruction with `end_opcode` (and matching non-zero arguments), counting nested openers/closers | H | Used by every `if` and by `case`/`random_case`; nesting through `0xf588` (openers 50012–50046, table `0x19610`) and `0xf5d8` (closers). |
| `0xf554`, `0xf520` | Test helper: mode 1 → value ≠ 0, mode 2 → value = 0 | H | Code. |
| `0xf4c4` | Compare helper: mode 1 `==`, 2 `!=`, 3 `>=`, 4 `<` (unsigned) | H | Code. |
| `0xa764` | `Eve` line number → text pointer | M | Called with `a4` by every text handler. |
| `0x1673c` / `0x16744` | `libfield_rel` imports: post a request to the field module / poll it. `rel_field.prx` exports them at `0x96c4` / `0x9744`; they index a table of 33 `{start, poll, busy}` entries at `0x2df0c` | H | NID resolution of `rel_field.prx`'s `.lib.ent`; the handlers loop on the poll with a wait call (`0x15a74`, `BOOT.BIN` `0x0884c6b8`) until it returns 1. So a blocking command (text, menu, fade, picture, DP change) waits for the field module. |

### Run model

- **Set-up pass.** When the field state flag (`*(0x33a40) + 0xc`) is clear, the first call executes only opcodes 50158–50172 through the second table and returns at the first other opcode, leaving `pc` there. In the main pass the same opcodes are no-ops. 50158 at the start of a record also resets the field state. In the data these opcodes sit at the start of the record (after the header), except four `scene_bgm` (50167) that come later and would therefore be ignored.
- **Main pass.** Instructions run in order. A handler blocks while the field module carries out a request. The interpreter returns on `end` (opcode 0), on `halt` (50145, without advancing `pc`) and after `goto` (50138).
- **Exit codes.** The value at `0x33b40` is read by the driver after the script returns: 102 (50150), 103 (50152), 104–110 (50176 with `a1` 1–7 via table `0x195f0`), 111 (50139), 112 (50140), 116 (default), 118 (50108). Presumably they select the next game mode (shop, mini-game, travel); not traced.

### Control flow

- **`if` blocks.** Opcodes 50014–50046 are conditions. When the test fails, the handler calls `skip_to(opcode + 33)`, so each `if` is closed by its own `endif` opcode 50047–50079, whose handler is empty. The block structure is checked by `story.py events --check`: all 7,468 records nest correctly (pairs in use: 50019/50052 ×4, 50022/50055 ×10, 50023/50056 ×158, 50028/50061 ×76, 50037/50070 ×112). There is no `else`; scripts use a second `if` with the opposite test.
- **Menus.** `choice` (50011) itself does nothing; it must be followed by `case 1`. The `case 1` handler takes the text of the previous instruction, splits it into up to five options (`0x121e0`), shows the menu (field request 18) and stores the answer (1–5) at offset `+0x64` of the field state. Answer 1 falls through into the body after `case 1`; any other answer `n` skips to `case n`. When execution reaches `case n` with 2 ≤ n ≤ 5 from the previous body, it skips to `case 11`, the end of the menu. Checked: every `choice` is followed by `case 1`, and every group has its `case 11`.
- **`random_case`** (50013) works the same way, with the branch drawn at random: `case 1` with `a2` = count draws `rand() % count + 1` (`BOOT.BIN` `0x08859688`); up to 10 branches; used 15 times (lotteries and random remarks).
- **`goto`** (50138 `a1, a2, a3`): stores the key of another record and returns; the driver runs that record next. All 83 `goto` keys exist.
- **Duel follow-ups** (50131–50134): three or four record keys stored in the duel set-up block (`*(0x33a28) + 0x14/0x20/0x2c/0x38`). All 96 non-zero keys exist; 50131 names `(301, 3, 41)` and 50132/50133 `(301, 3, 42)` in all 32 uses. Presumably win / loss / draw; the order is a hypothesis.

## Opcodes

`H`/`M`/`L` = confidence. "Handler" is the module offset of the function the case block calls. Ranges are over all 7,468 records. "Unused" opcodes do not occur in the data; they are listed with what their handler does.

### Text and windows

| Opcode | Name | Arguments | Handler | Effect | Conf. |
| --- | --- | --- | --- | --- | --- |
| 50001, 50002 | `talk`, `talk_alt` | speaker, expression, flag, line | `0xc430` | `0x11990(speaker, 0x4424(expression), flag, opcode, text)` → field requests 13/14/17 (talk window with portrait); sets "a line was shown". | H for the call; M for the argument roles |
| 50003 | `portrait` | speaker, expression, flag | `0xc4e8` | Same window call without text (`0x11b54`, request 13). Unused. | L |
| 50004, 50005 | `talk_pair`, `talk_pair_b` | speaker, expression | `0xc560` | Combines this instruction with the next (reads its opcode at `+10`) and consumes it. Unused. | L |
| 50006 | `close_talk_of` | speaker | `0xc688` | Closes the talk window of one speaker (request 15). Unused. | M |
| 50007 | `close_talk` | — | `0xc6cc` | Closes the open talk windows (request 15). 607 uses, usually after a line. | M |
| 50008 | `narrate` | line | `0xc6f0` | Narration box, `0x11ee4(text, 0)` (request 17). | H |
| 50009 | `narrate_named` | speaker, line | `0xc738` | Narration box with a speaker, `0x11ee4(text, speaker)`. | H |
| 50010 | `close_narration` | — | `0xc7ac` | Request 17 with empty arguments if the box is open. | M |
| 50011 | `choice` | line | `0xc7d8` (empty) | Menu text; shown by the following `case 1`. | H |

### Control flow

| Opcode | Name | Arguments | Handler | Effect | Conf. |
| --- | --- | --- | --- | --- | --- |
| 50012 | `case` | n (1–5, 11) | `0xc7e0` | See "Menus". | H |
| 50013 | `random_case` | n, count | `0xc9dc` | See "random_case". | H |
| 50047–50079 | `endif` | — | none (dispatch goes straight to `pc + 1`) | Closes the `if` opcode − 33. | H |
| 50138 | `goto` | key a1–a3 | `0xe9d4` | `0xa874(key)` into the field state, state 2, return. | H |
| 50145 | `halt` | — | none | Returns from the interpreter without advancing `pc`. 10 uses. | H (code) |
| 50175 | `end_event` | — | `0xf2ac` | Sets the field state to 2 (`0xa7f4(2)`), as `goto` does. 262 uses, 258 of them as the last instruction before `end`. | M |
| 0 | `end` | — | — | Interpreter returns 0. | H |
| 1 | `header` | key a1–a3 | — | The record's key (see `0xa67c`). Never executed (`pc` starts at 1). | H |

### Conditions (`if`)

All take a test (`test`: 1 true / 2 false) or a comparison (`cmp`: 1 `==`, 2 `!=`, 3 `>=`, 4 `<`); see the helpers above. The state structure "W" is `*(0x33b2c)` inside `rel_story.prx`.

| Opcode | Name | Arguments | Getter | Effect | Conf. |
| --- | --- | --- | --- | --- | --- |
| 50014 | `if_counter` | index, test | `0xada4` | W `+0x40 + 4·index` ≠ 0 (counters 1–20, 0–99, changed by 50080). Unused. | H (code) |
| 50015 | `if_counter_b` | index, test | `0xaf64` | W `+0x94 + 4·index` (counters 1–50, changed by 50081–50083). Unused. | H (code) |
| 50016, 50017, 50019 | `if_value_34`, `_38`, `_3c` | value, test | `0xae6c`, `0xaea4`, `0xaf20` | W `+0x34` / `+0x38` / `+0x3c` == value. 50019 used 4× with value 49. | H (code), meaning unknown |
| 50018 | `if_counter_b_total` | test | `0xaf80` | Sum of the 50 counters at `+0x94` ≥ 10. Unused. | H (code) |
| 50020 | `if_char_points` | char, value, cmp | `0x2f44` → `BOOT.BIN` `0x08857dd0(char)` | Compares a per-character `u16` (`+0x16` of a 24-byte record at save state `+0xfe0c`; `deck_select_owner_variant` tests the same value ≥ 2000 for owner 8). Unused. | M |
| 50022 | `if_dp` | value, cmp | `BOOT.BIN` `0x08854b68(0)` | Compares a `u32` of the save state (`+0xfdfc`) with `a1`. Used as `if ≥ 200` right before `dp_sub 200` (buying a sandwich), so presumably the player's DP. | M |
| 50023 | `if_flag` | flag, test | `0x10428` | Tests story flag `a1` (bit array, 1–135 used) that `set_flag` writes. 158 uses. | H |
| 50028 | `if_card_marked` | card, test | `BOOT.BIN` `0x0885654c(card)` | Bit 3 of byte 0 of the card's save-collection record (`save.md`; `0x088560e4` maps the id to the record). Always used as "if not marked: show, give and mark the card". | H (code), M (meaning) |
| 50037 | `if_partner` | char, test | `0xb04c` | W `+0x14` == char. W `+0x14` is the character `duel_tag_partner` takes as partner and whose points 50084/50085 change; the dialogue inside the blocks is spoken by that character. | M |
| 50021, 50024–50027, 50029, 50030, 50032, 50035, 50038–50040, 50042–50045 | `if_<opcode>` | — | various | Unused; getters not identified. | — |
| 50031, 50033, 50034, 50036, 50041, 50046 | `nop` | — | empty | Unused openers with an empty handler. | H (code) |

### Story state, rewards, money

| Opcode | Name | Arguments | Handler | Effect | Conf. |
| --- | --- | --- | --- | --- | --- |
| 50080 | `counter_step` | index, direction | `0xd980` | 1: W counter `+0x40` +1 (max 99); 2: −1 (min 0). Unused. | H (code) |
| 50081–50083 | `counter_b_step`, … | — | `0xda20`… | Decrement counters at `+0x94`. Unused. | H (code) |
| 50084 | `partner_points_add` | amount (4–500) | `0xdb14` | `0xb5c(W+0x14, amount)` → `0x2fc0` changes a per-character value, then field request 28 shows up/down/no change. Used e.g. after the menu option "strengthen my bond with my partner". | M |
| 50085 | `partner_points_sub` | amount (5, 10) | `0xdb5c` | Same with −amount. | M |
| 50086 | `dp_add` | amount (2,000–10,000) | `0xdba8` | Field request 24 with +amount. Used as a prize after won duels. | M |
| 50087 | `dp_sub` | amount (100, 200) | `0xdc24` | Field request 24 with −amount, after `if_dp ≥ amount` (sandwich, lottery). | M |
| 50090 | `set_flag` | flag (1–133), op | `0xdcac` | `0x10354(flag, op == 1)`: set (1) or clear (2) a story flag; 311 uses. 50091 jumps into the same handler. | H |
| 50094 | `advance_counter` | — | `0x109c0` | Increments a byte (max 10) in the field save block (`*(0x34064)`) and sets the next byte to 1. 188 uses, near the end of story records. | L for the meaning |
| 50097 | `give_card` | card (4007–6397), show | `0xfb70` | Field request 23 (card display) then `BOOT.BIN` `0x08856248(card, show)`. | M |
| 50098 | `give_random_card` | pack (60000 = random), rarity lo, hi | `0xf7a0(1)` | Pack index `a1`, or `rand() % 48` when `a1` ≥ 60,000; draws one card with a rarity in [lo, hi] from the pack lists in the module and gives it with `give_card`'s routine. "There was a card in the sandwich!" | M |
| 50099 | `give_booster` | pack, rarity lo, hi | `0xf7a0(5)` | As 50098 but first 4 cards with rarity range (0, 4), then one in [lo, hi]: a 5-card booster. 279 uses, mostly `(60000, 3, 4)`. | M |
| 50100 | `mark_card` | card | `BOOT.BIN` `0x08856510` | Sets bit 3 of the card's collection flags. | H (code) |
| 50103 | `set_pack_state` | pack (0–47 or 60000), state | `0xde70` | `BOOT.BIN` `0x08857484(pack, state)` writes 3 bits of a per-pack byte; with 60000 the first pack from 3 whose state is < 2 gets state 4. Used next to duel prizes: presumably unlocks shop packs. | M (code), L (meaning) |

### Scene, sound, pictures

| Opcode | Name | Arguments | Handler | Effect | Conf. |
| --- | --- | --- | --- | --- | --- |
| 50111 | `picture` | id (1–86), op | `0xe010` | op 1 shows picture `id` (`id` 1/2 are mapped to −2/−3), op 2 hides it (−1); field request 19. Showing also sets bit `id` of a save bit array (`BOOT.BIN` `0x088580a0`): presumably the gallery unlock. 509 uses, typically between `fade_out` and `fade_in`. | M |
| 50112 / 50113 | `fade_in` / `fade_out` | frames (30, 60, 300), flag | `0xe108` → `0xa70(on, wait, frames)` | Field request 22 with on = 0 / 1. | M |
| 50114 / 50115 | `npc_appear` / `npc_leave` | char | `0xe17c` | Builds a character's placement from its set-up data (50114) or marks it gone (state 4, 50115) and sends field request 8. 50115 used 142×. | L |
| 50116 / 50117 | `screen_effect` / `screen_effect_end` | kind (1–3) | `0xe354` / `0xe414` | Field requests 20 / 21; used around portal and "dimension" scenes. | L |
| 50118 | `op_50118` | a1 (1, 7) | `0xe468` | Field request 26 with a value from table `0x4758`. | — |
| 50153 | `sound_effect` | id (1–4) | `0xedc8` | `0x4578` maps 1–5 to 31,322 / 31,455–31,458 and calls `BOOT.BIN` `0x08841898` → `0x0886da0c(id, 0, 0)`. | M |
| 50155 | `bgm` | id (10–25) | `0xee50` | `0x45c0` maps 0–26 through a table; if the track differs from the current one, stops it, requests the new one (`0x08841840`), waits until loaded (`0x0886997c`), then plays it with a 500 ms fade (`0x08841870`). | M |
| 50167 | `scene_bgm` | id (6–26) | `0xf0d4` (set-up pass) | Stores the same mapped track in the field state (`0xa854`). | M |
| 50156, 50157 | `op_50156`, `op_50157` | — | `0xfe78`, `0xff30` | Sound-side helpers (`0xfe78` is also called when `bgm` replaces a track). 50156: 4 uses; 50157 unused. | L |

### Set-up pass (50158–50172)

The per-character record is returned by `0x2b94(char)`.

| Opcode | Name | Arguments | Effect | Conf. |
| --- | --- | --- | --- | --- |
| 50158 | `scene_map` | map (1–30), b (0/2) | Field state `+0x14` = map, `+0x18` = b; map 2 sets system flag 30. Once in each of the 218 set-up records. | M |
| 50159 | `scene_player` | direction (8–11), x, y | Player position `(x·0.5 + 0.25, y·0.5 + 0.25)` and direction (`0x453c`: 8→1, 9→3, 10→5, 11→7) into W `+0x8/+0xc/+0x10`. | M |
| 50160, 50161 | `npc_place`, `npc_place_b` | char, location | Location id → position via `BOOT.BIN` `0x0885ad14`; record `+0x40`. | L |
| 50162, 50164 | `op_50162`, `op_50164` | char, value | Record `+0x42` / `+0x44`. 50162: 8 uses; 50164 unused. | — |
| 50166 | `npc_event` | char, group, number | Record `+0x46`–`+0x4a`. `(0, 0)` in 833 uses; otherwise group 301 and a number 204–340. Hypothesis: the event that talking to the character starts (301 is a header `a1`). | L |
| 50168 | `npc_position` | char, x, y | Record `+0x28/+0x2c/+0x30/+0x34/+0x38`. 1,000 uses (one per character on stage). | M |
| 50169 | `npc_direction` | char, direction (8–11), c (0/5) | Record `+0x3c/+0x3d/+0x3e`; same direction mapping as `scene_player`. | M |
| 50170 | `op_50170` | char, a2 (always 0) | Record `+0x3f`. | — |
| 50171 | `npc_event_b` | char, group, number | Record `+0x4c`–`+0x50`; same values as 50166 in every use. | L |
| 50163, 50165, 50172 | `nop` | — | Empty. | H (code) |

### Duels

`0x33350` onwards is a duel set-up block in `rel_story.prx`; `0xa4f4(char, variant)` picks the character (or, for `variant` > 0, a character and position from `BOOT.BIN` `0x0885ad14`) and `0xa5cc` the deck: `deck_get_owner_recipe(char, 0x3178(char))`, or recipe 466 for the partner in one mode.

| Opcode | Name | Arguments | Handler | Effect | Conf. |
| --- | --- | --- | --- | --- | --- |
| 50119 | `duel_single` | opponent, variant | `0xe4e8` → `0x97f4` | One-to-one duel set-up (writes the opponent, its deck recipe and the duel-type bits at `0x33a24`); clears the follow-up keys. Used after lines such as "Let's duel!". | H |
| 50120 | `duel_tag_opponent_a` | char, variant | `0xe538` → `0x994c` | Tag duel (type 2), first opponent. | H |
| 50121 | `duel_tag_opponent_b` | char, variant | `0xe588` → `0x9a6c` | Second opponent (`+0x3870`). | H |
| 50122 | `duel_tag_partner` | variant | `0xe5b4` → `0x9b20` | The player's partner is W `+0x14`. | M |
| 50129 | `duel_rules` | a (1/2), b (1/3), c (1) | `0x9e38` | Bytes `0x3335d`, `0x3335c`, `0x33359`. Follows every duel set-up. | M (code), meaning unknown |
| 50130 | `duel_option` | a, b | `0x9f74` | Bytes `0x3335e/f`. | — |
| 50131–50134 | `duel_then_a`…`_d` | key | `0x9ea8`, `0x9ee0`, `0x9f18`, `0x9f50` | Follow-up record keys (see "Control flow"). | M |
| 50123–50128 | `op_…` | — | `0xe5e0`–`0xe798` | Other set-up variants; 50126/50127/50128 are used once each under the menu "You duel / Your partner duels / Tag duel". | L |

### Exits and other

| Opcode | Name | Arguments | Effect | Conf. |
| --- | --- | --- | --- | --- |
| 50108 | `exit_118` | — | Exit code 118. 1 use. | H (code) |
| 50139 | `exit_111` | — | Player mode 2 at (7.75, 12.75), then exit code 111 or (if `0x10a74()`) the 50140 path. After "Yes, I'll go." | M (code) |
| 50140 | `exit_112` | — | Same position, system flag 9, exit code 112. 137 uses, alone in a record. | M (code) |
| 50150 | `exit_102` | char (26/27) | Exit code 102, `a1` into VM `+8`. Sandwich sellers. | M (code) |
| 50152 | `exit_103` | — | Exit code 103. | H (code) |
| 50176 | `exit_select` | n (1–7) | Exit code 103 + n for n 1–7 (104–110, table `0x195f0`; 0 or > 7 give 104); n = 4 also sets system flag 10. Used after the quiz rules ("Try to answer…"). | M (code) |
| 50137 | `op_50137` | — | VM `+0xc` = 1. 137 uses, before `end_event`. | — |
| 50144 | `op_50144` | char | Field request 11 with the character's position; 35 uses in one record. | — |
| 50148, 50149 | `op_50148`, `op_50149` | — | A counter at field state `+0x65` (5 → system flag 24); system flag 25. | — |
| 50151 | `op_50151` | a1 (26/27) | Long handler (positions, flags); after buying a sandwich. | — |
| 50105 | `op_50105` | a1 (5) | `0x5ba8(4, a1)`; 2 uses, before `exit_111`. 50104 and 50106 call the same function. | — |
| 50096, 50101, 50104, 50106, 50124, 50125, 50154 | `op_…` | — | Unused. | — |
| 50141 | `op_50141` | — | `0xa96c(1)`. Unused. | — |
| 50088, 50089, 50092, 50093, 50095, 50102, 50107, 50109, 50110, 50135, 50136, 50142, 50143, 50146, 50147, 50173, 50174 | `nop` | — | Empty handlers. | H (code) |


## Cross-check with ygotfToolkit

Its `story --dump`, run read-only on the maintainer's image (2026-10-25) with the CSV written to `extracted/`, gives the same 59,985 (archive, table, language, line) keys and identical text for every line. Both tools write newline as `\n`. Its notes give the same `I`/`L` structure and the 59,985 total.

The bytecode findings (10-byte instructions, `EveBI` record starts, text references in `a4`) were established here and are not in the toolkit's output.

## Tool

`tools/story.py events story_scr_b.ehp [--text story_scr_e.ehp]` writes one CSV row per instruction with the symbolic name and the named arguments (`args` column, enumerations spelled out: `test=true`, `cmp=>=`, `op=clear`); undecoded opcodes print as `op_<n>` / `if_<n>` with their non-zero arguments. `--list` writes a readable listing instead: indented `if` blocks and `case` groups, `[set-up]` on the set-up opcodes, keys resolved to record numbers, and the line text. `--record N` limits either output. `--check` adds the control-structure checks (if/endif nesting, `choice` → `case 1`, every `case` group closed by `case 11`, every `goto`/duel follow-up key present); they pass on the European disc.

## Open questions

- Runtime base of `rel_story.prx`, so the offsets above can go into Ghidra and the registry; the driver around `0xb3c8` (how the field module picks the record to run, how the exit codes are consumed).
- What the field-module requests (33 entries in `rel_field.prx` at `0x2df0c`) do on the field side, in particular 11, 13/14 (talk window), 19 (picture), 20/21, 24 (DP display), 26 and 28; and which save fields the `BOOT.BIN` getters read (DP, per-character points, pack state, picture bits).
- The meaning of `talk`'s `a3` flag (0/1; 148 uses with 1, often on lines like "..."), of `npc_event`'s `(301, n)` pair, of the `duel_rules`/`duel_option` bytes, and the order of the duel follow-up keys (win/loss/draw?).
- Opcodes in use whose effect is still unnamed: 50118, 50137, 50144, 50148, 50149, 50151, 50156, 50162, 50170 (and 50105, two uses).
- The `《Cnnn_k》` forms 1–5, and whether `nnn` equals the speaker id in `a1` of 50001/50002/50009. The ranges overlap (2–141 vs 001–151), but this is not proven.
- Where `《…》` placeholders and `$M`/`$C` are expanded in code, and whether the bracketed tokens in `SysMsg` are placeholders at all.
- Whether the empty lines (158 per language) are ever displayed.
