# Duel tutorial: `.ydq` duel setups, `tuto_cmd_NN.bin` scripts, `tuto_text_<l>.bin`

Tool: `tools/tutorial.py` (`--check` over every member, a readable listing with text and card names resolved; it also lists the deck-building tutorial of `deck/tutorial.ehp`, see `deck.md`). Tests: `tools/tests/test_tutorial.py` (synthetic data only).

Module offsets are unrelocated (`+0x0`). `rel_duel_eng` addresses are also given at its runtime base `0x09be1400` (as in `re/functions.csv`); `rel_tutorial`'s base is unknown. Imports were resolved with `tools/prx_imports.py` (base 0) and, for the 1,409 imports from other game modules, against those modules' export tables.

| Structure | Where | Status |
| --- | --- | --- |
| `.ydq` duel setup (`[DUEL QUESTION]` text) | `d_tutorial/tutorial.ehp`, 50 members | documented (every key, from the parser) |
| `tuto_cmd_NN.bin` tutorial script | same archive, 17 members | documented (record layout, all 21 tutorial opcodes; duel-engine opcodes partly) |
| `tuto_text_<l>.bin` text table | same archive, 6 members | documented |

## Archive and lessons

`d_tutorial/tutorial.ehp` holds 73 members: `tuto_cmd_00`–`16.bin` (17 scripts), `tuto_field_00`–`16`, `20`–`25.ydq` (23 initial setups), `tuto_field_reset00`–`25`, `27.ydq` (27 mid-lesson setups; `reset26` does not exist) and `tuto_text_{e,f,g,i,j,s}.bin`.

`rel_tutorial` (library `libtutorial_rel`, 13 exports, imported by `rel_duel_mgr`) runs a lesson. `tutorial_start_lesson(lesson, callback, …)` (`+0x3748`, called by `rel_duel_mgr +0xfd74` with the lesson number from byte `+403` of a session record):

1. Lesson 15 is replaced by 16 for the file names (`if lesson == 15: n = 16`); the original number is kept in `0x17f38`.
2. Loads `d_tutorial/tutorial/tuto_field_%02d.ydq` (n) and passes it to `duel_core_start_mode3` (below), then frees it.
3. Only for lessons below 20: loads `tuto_cmd_%02d.bin` (n) and keeps it (`0x17f30` start, `0x17f34` program counter). Lessons 20–25 have no script: they are free duels (all files `tuto_field_20`–`25` set `Turn=1`, `LimitTurn=-1` and 2,000 or 4,000 LP), and the input filter lets every action through when the lesson number is 20 or more.

Consequences (confidence medium-high, from the code and the data): `tuto_field_15.ydq` is byte-identical to `tuto_field_16.ydq`, and `tuto_cmd_15.bin` is never loaded. It is also the only script that loads `tuto_field_reset26.ydq`, the one reset file missing from the archive; its 54 text lines (769–822) are therefore never shown. `tools/tutorial.py --check --notes` reports this.

## `.ydq`: duel setup text

Plain text, Shift-JIS (CP932), CRLF line ends, one `key=value` per line, `//` comments (the files carry the Japanese card name after every card id). All 50 files start with `[DUEL QUESTION]` and contain the sections `[Player0]`, `[Player1]`, `[Equipment]` (always empty) and `[END]`.

### Parser

`duel_core_load_ydq(text)` (`rel_duel_eng +0x1e80e4`, `0x09dc94e4`):

1. Sets both sides' Life Points to 8,000 and their card serial counters (`+0x04`) to 1, and posts duel command 1.
2. Copies one line at a time into a 256-byte buffer (up to and including `\n`, at most 254 bytes) and calls `duel_core_parse_ydq_line` (`+0x1e6ecc`, `0x09dc82cc`) until that returns 1 (`[END]`) or the text ends (NUL).
3. Posts the commands that put the parsed state on the table (below).

The line parser does not tokenise: it dispatches on the first character and reads values at **fixed byte offsets** with `strncmp` (`0x08811684` via its import stub) and `sscanf("%d")` (`0x08810fec`). Consequences:

- Section headers are ignored; only `[END]` matters. Lines after `[END]` are not read.
- Comments do not matter because `%d` stops at the tab.
- **Count lines (`CardInHand0=5`) are ignored**: the parser skips any `CardIn…<p>=` line (the character after the player digit is `=`). The lists are built from the `_NNN` entries alone.
- **The `NNN` index of list entries is not read**: entries are appended in file order. Only `CardInGame` reads its number (the field slot).
- The player digit is used as `p & 1` for the side; `p` = 2 or 3 is a tag partner (below).

| Key (first character) | Read at | Effect |
| --- | --- | --- |
| `[END]` | — | Stop. |
| `LimitTurn=n` | `%d` at 10 | `n <= 0`: no limit (`0xffff`); otherwise last turn = current turn + n − 1 (`0x09e2d1e4`). Uses the `Turn` value parsed so far. |
| `TurnPlayer=d` | char 11 | Side that moves first (`0x09e029a8`, copied to `0x09e2d1d8`/`0x09e2d1dc`). Unused in the data. |
| `Turn=d` | char 5 | Turn counter = d − 1 (`0x09e2d1e0`, 0-based; one digit). |
| `PlayerLP<p>=n` | char 8, `%d` at 10 | Life Points, player block `+0x00` (this confirms the LP field of `duel_core.md`). |
| `Phase=<word>` | char 6 | Only the first letter: `D` draw 0, `S` standby 1, `M` main 2, `B` battle 3, `E` end 5; `duel_core_set_phase` (`+0x1e6e08`, `0x09dc8208`). Other letters are ignored. The data uses `Draw` 36×, `Main` 7×, `MAIN1` 6×, `DRAW` 1×. |
| `CardInHand<p>_NNN=id` | char 10, `%d` at 16 | Appended to the **deck** list and the side's hand counter (`+0x0c`) incremented (see "Hand" below). |
| `CardInDeck<p>_NNN=id` | char 10, `%d` at 16 | Appended to the deck list (`+0x10` count, entries at `+0x304`). |
| `CardInFusion<p>_NNN=id` | char 12, `%d` at 18 | Extra (Fusion) deck: `+0x18` count, entries at `+0x4e4`. |
| `CardInGrave<p>_NNN=id` | char 11, `%d` at 17 | Graveyard: `+0x14` count, entries at `+0x55c`. |
| `CardInExclude<p>_NNN=id` | char 13, `%d` at 19 | Banished ("removed from play"): `+0x1c` count, entries at `+0x7b4`. |
| `CardInGame<p>_SSS=id` | char 10, slot `%d` at 12, `%d` at 16 | Field slot `S` (player block `+0x34 + 20·S`): card id into `+0x00` (low 14 bits). |
| `CardInGame<p>_SSS_Face=n` | `%d` at 21 | Slot `+0x08` (face-up when non-zero). |
| `CardInGame<p>_SSS_Turn=n` | `%d` at 21 | Slot `+0x06`: the battle position (1 = Defense). "Turn" means turned sideways. |
| `CardInGame<p>_SSS_Owner=n` | `%d` at 22 | Slot byte `+0x01` bit 6 = (n ≠ p): the card belongs to the other side. |
| `CardInGame<p>_SSS_Param=n` | `%d` at 22 | Slot `+0x0c` (`u32`). |
| `CardInGame<p>_SSS_Flag=NAME` | name at 21 | ORed into slot `+0x10`: `PUTBYANOTHER` 0x1, `SPECIALSUMMONED` 0x40, `PARTICULAR` 0x80, `CAPTURED` 0x800, `TRAPMONSTER` 0x1000. |
| `EquipActNNN_SrcPlayer` / `_SrcLocate` / `_DstPlayer` / `_DstLocate=n` | `%d` at 22 | Equip record `NNN` (10 bytes at block 0 `+0x22ae + 10·NNN`): `+0` low/high byte = source player/location, `+4` low/high byte = destination player/location. The record count is max(NNN + 1). |
| `EquipActNNN_SrcCardID=n` | `%d` at 22 | Writes the whole `u16` at `+0` (overwriting player and location). |
| `EquipActNNN_Type=NAME` | name at 17 | Low nibble of `+2`: `ONLYINTURN` 1, `ONLYFACETURN` 2, `ONLYFACE` 3, `FOREVER` 5, `PERMANENT` 6, `DURINGFACE` 7, `EQUIPMENT` 10, `UNION` 11, `CAPTURED` 12. |

List entries are 4 bytes: `u16` card id (low 14 bits) with bit 14 = side, and a `u16` whose bits 7–14 hold the card's serial number from the side's counter at `+0x04` (each card gets a fresh serial; the loader stores the last one at `+0x08`). Addresses above are relative to the player block (`0x09e2a528 + side × 0xb3c`, `duel_core.md`). The flag bit 12 (`TRAPMONSTER`) is the bit that `duel_core.md` already suspected of marking a trap monster; `_Turn` writing `+0x06` confirms that field as the battle position.

**Hand.** Hand entries go into the same list as the deck, ahead of the deck entries in every file, and only the hand counter tells them apart. After parsing, the loader posts duel command `0x56` (draw) for each side with count = hand counter, turn player first, then clears the counter. For the listed hand cards to be the ones drawn, a draw must take the list from its start; that is consistent with every file but was not checked in the draw code (confidence medium).

**Tag partners.** `CardInHand2/3`, `CardInDeck2/3` and `CardInFusion2/3` do not touch the player blocks. They go, as bare ids, into a separate table (`0x09e02cb8 + (p & 1) × 300`: `u16` hand, deck and extra counts at `+16/+18/+20`, then the ids from `+22`) and set `0x09e2d1fc`. The loader then sets `0x09e029a0`/`0x09e029a4` to 1 and registers the cards with serials after those of the main duellist. Other keys with player 2/3 fall back to side `p & 1`. No file uses players 2 or 3 (confidence medium for the "tag partner" reading; it matches `tag_duel.md`'s two duellists per side).

**After parsing** the loader posts, per side and occupied field slot: command `0x43` (side bit = owning side; `a` = side | slot << 1 | position << 14 | face-up << 15; `b` = card id); `0x39` with the slot parameter (`a` slot, `b`/`c` low/high half) when it is non-zero; `0x29 (slot, bit, 1)` for every set flag bit. Then `0x35` for each equip record, then the two draws. In mode 2 only it also posts command `10 + phase`, sets the phase to 7 and, when the turn equals the last turn, posts `0x67 (0, 5, 0)`.

`duel_core_start_mode2(text)` (`+0x1e6c88`) and `duel_core_start_mode3(text)` (`+0x1e6d48`) reset the duel, set the mode (`0x09e2d1f4` = 2 or 3) and call the loader. Mode 3 starts at turn 0 with no turn limit; mode 2 presets turn and limit to 9 (the file then overrides them). `rel_tutorial` only uses mode 3; `rel_duel_mgr` imports both (the mode-2 caller is not identified).

### The 50 files

- All parse; no file has a line the game ignores. Phase: see table. LP: 8,000 in 85 of 100 sides, otherwise 4,000 (8), 2,000 (4), 16,000 (2), 2,100 (1).
- 3,687 deck entries, 274 hand entries, 68 field cards (`_Face` on all 68, `_Turn` on the 53 in monster slots 0–4), 43 extra-deck and 14 graveyard entries. No `_Owner`, `_Param`, `_Flag`, `EquipAct`, `TurnPlayer` or banished cards.
- Count lines disagree with the entries three times (`tuto_field_21` deck, `tuto_field_reset25` hand 1 vs 3 entries and graveyard 0 vs 6); the game ignores them, so the entries count.
- With `--cardinfo`, one id is not in the card database: 4006, in player 1's deck of `tuto_field_21`–`24` (commented as Blue-Eyes White Dragon, whose id is 4007).

## `tuto_text_<l>.bin`: text table

`u32 (offset, size)` pairs, one per line, then the text; line count = first offset / 8 (878 in all six languages). Line `n` occupies `[offset, offset + size)`; the lines are contiguous and `size` is a multiple of 4. Text is UTF-16LE (Shift-JIS in `tuto_text_j.bin`), NUL-terminated and zero-padded. `@<digit>` is a colour escape (`@2` on, `@0` off). `tutorial_load_text_line(n)` (`+0x4cf0`) opens `tuto_text_%c.bin` with `"jegfis"[language & 7]` (language from `0x08857b80`), seeks to `8n`, reads the pair, then the text into the buffer at `0x17f60`.

The 17 scripts reference 878 text lines through opcodes 1, 2 and 8: every line exactly once, in order (script 0: lines 0–52, … script 16: 823–877).

## `tuto_cmd_NN.bin`: tutorial script

A sequence of 8-byte records `u16 op, u16 a, u16 b, u16 c`, ended by a record with `op == 0`, which is always the last record (17/17 files; 400–1,584 bytes, 1,715 records).

`tutorial_step` (`+0x4c38`) fetches the record at the program counter and advances it by 8 (`+0x4724`), then:

- `op == 0`: end of lesson (state 8).
- `op & 0x4000`: tutorial command `op & 0x3fff` (`tutorial_exec_command`, `+0x473c`, jump table at `+0xf608`, 21 entries).
- otherwise: **duel-engine command**. `tutorial_exec_duel_command` (`+0x4b70`) passes the record unchanged to `duel_core_push_command(op, a, b, c)` (`0x09dc07f8`, `rel_duel_eng +0x1df3f8`), which appends it to the engine's 256-entry command queue at `0x09e29100` (count `0x09e29900`; skipped while `0x09e02998` = 3). Bit 15 of `op` selects side 1, as in the `.ydq` loader. Codes 10–15 also call `duel_core_set_phase(code − 10)` directly.

The loop repeats while the handler returns 0 and stops (until the next frame) when it returns 1.

### Tutorial commands (`op & 0x3fff`, with `0x4000` set)

| Op | Uses | Name | Arguments | Behaviour (from the handler) |
| --- | --- | --- | --- | --- |
| 0 | 0 | yield | — | Nothing; stops for this frame. |
| 1 | 702 | message | `a` text line, `b` | Loads text `a` and opens the message window (`+0x529c`, style 35, `b` passed through; always 0); state 3 (wait until closed). |
| 2 | 118 | hint | `a` text line | Shows a persistent instruction line (`+0x50e8`; remembered at `0x17f48` and redrawn by export `+0x45f8`). Continues. |
| 3 | 11 | hint_off | — | Removes it; `0x17f48` = −1. Continues. |
| 4 | 36 | highlight | `a` side (0 own, 1 opponent), `b` screen region 0–20, `c` frames (300 or 150) | Frames a region of the duel screen (`+0x54c4`, `+0x57bc`); state 7 until `c` frames pass or ○/× is pressed. The text before each use names the region (0 a whole side, 1 monster zones, 2 spell/trap zones, 3 graveyard, 4 deck, 5 removed zone, 6 field zone, 7 Fusion deck, 8 phase display, 9–14 the phases, 15 Life Points, …). |
| 5 | 166 | label | `a` number | Jump target; stops for this frame. |
| 6 | 61 | goto | `a` label | `tutorial_goto_label` (`+0x4e4c`): linear search for `op & 0x3fff == 5` with that `a`; continues after it. |
| 7 | 59 | if_answer | `a` value, `b` label | Goes to `b` when the last answer (`0x17f58`) equals `a`. |
| 8 | 58 | question | `a` text line | Like 1 (style 36) with the number of `\n` in the text as fourth argument: line 1 is the question, the others the choices; the chosen index lands in `0x17f58`. Every use is followed by `if_answer` records (answers 1–3). |
| 9 | 88 | show_card | `a` card id; 0 hides; 1–2 a card remembered from a duel event (`0x17f50[a]`) | Card picture (`+0x57d4`). |
| 10 | 28 | load_field | `a` | `tutorial_load_reset_field` (`+0x4ed0`): `tuto_field_reset%02d.ydq` through `duel_core_start_mode3`; state 2. |
| 11 | 2 | wait | `a` frames | State 5 (counter `0x17f5c`). |
| 12 | 109 | wait_input | `a` kind, `b` card id or argument (0 = any) | State 4: wait for the player action `a` (table below). |
| 13 | 8 | set_turn | `a` | `0x09be184c(a)`: writes the turn counter `0x09e2d1e0`. Always 2 in the data. |
| 14 | 85 | wait_event | `a` event, `b` argument (0 = any), `c` minimum | State 6 until the engine reports event `a` (export `tutorial_on_duel_command`, `+0x3df8`); for event 54 the fourth hook argument must be ≥ `c`. |
| 15 | 27 | card_part | `a` 0–9 | `+0x57dc`: points at part `a` of the displayed card (from the surrounding text: 2 type, 3 ATK/DEF, 4 description, 7 and 9 name and illustration, 8 attribute; 0 off). |
| 16 | 57 | on_event | `a` event (0 = clear), `b` label, `c` argument (0 = any) | Registers a handler: when event `a` arrives (or, for 66, when the menu is cancelled, see `+0x38a8`), go to label `b`. Used as "if the player backs out, show the hint again": `on_event 66, <label before the hint>`. |
| 17 | 10 | flag_on | `a` bit | Sets bit `a` of `0x17f44`: bit 1 lets every input through the filter; bit 3 also sets `0x18794` = 2 and calls `+0x53fc(…, 1)`. |
| 18 | 9 | flag_off | `a` bit | Clears it (bit 3 reverses the extra actions). |
| 19 | 1 | count_answer | `a` (1) | Counts the cards of a list (`0x09be189c`, `+0x5268`) for which `0x0885f864(id)` returns 2 and stores the count as the answer. |
| 20 | 4 | open_list | `a` side, `b` location | `0x09dcf950(a, b, 0, 1)` then `+0x58e8`; state 2. Used with location 14 (the graveyard list). |

### `wait_input` kinds

The input filter `tutorial_filter_input` (`+0x39b4`, registered with `rel_duel_draw`) receives each player action as a code and blocks it (returns 0) unless it is the awaited one; the card under the cursor must equal `b` when `b` ≠ 0. On a match it removes the hint and, for some kinds, resumes the script. Kinds 0, 6 and 12 are also checked against the cursor position by `+0x43a8` (zone 11 = hand, 0–4 monster zones, 5–9 spell/trap zones). Names come from the hint line each script shows just before the `wait_input` (all 109 uses agree); the input code is what the filter compares.

| Kind | Accepts input code | Meaning (hint text) |
| --- | --- | --- |
| 0 | cursor on hand card | pick a card in the hand |
| 1 | 4 | menu: Summon |
| 2 | 13 + `b` | phase menu: pick phase `b` (3 Battle, 5 End) |
| 3 | 0 | pick a monster to attack with (resumes) |
| 4 | 11 | pick the attack target (resumes) |
| 5 | 6 | menu: Set (monster) |
| 6 | cursor on monster zone | pick a monster on the field |
| 7 | 8, 9 or 5 | menu: change battle position |
| 8 | 11 (no resume) | pick a Tribute |
| 9 | 4 (resumes at once) | menu: Summon (Tribute Summon) |
| 10 | 3 | menu: Activate |
| 11 | 7 | menu: Set (spell/trap) |
| 12 | cursor on spell/trap zone | pick a Set spell/trap |
| 13 | — (handled by export `+0x457c`) | answer YES |
| 14 | 2 or 11 | pick a monster to Special Summon |
| 15, 16 | 11, any card | pick Fusion Materials / Tributes from a list |
| 17 | 11 | pick an opponent's card |
| 18 | — (not through the filter) | open the phase menu |
| 19 | 3 (resumes) | Extra Deck: Activate |

Confidence: high that the kinds are these player actions (hint texts, 109/109), medium for the input-code meanings.

### Events and duel-engine commands

`wait_event` and `on_event` use the duel-engine command codes that the engine reports to `tutorial_on_duel_command` (`+0x3df8`, export of `libtutorial_rel`). In the data: 4 (after a summon or attack resolves, 54×), 54 (10×, an activation), 6 (7×, end of turn), 5 (5×), 26 (3×, a card picked from a list), 13, 55, 34; `on_event` 66 (menu cancelled) and 10.

Raw duel commands in the scripts (59 records): `0x27` (11×, `a` = field location 0–15 of side bit 15: the field cursor; the texts name 2 the middle monster zone, 7 the middle spell/trap zone, 13 deck, 14 graveyard, 15 removed zone), `0x0c` (26×), `0x0d` (4×), `0x0f` (3×) = phase changes (10 + phase), `0x56 (0, n, 0)` = draw n cards (as posted by the `.ydq` loader), `0x03` and `0x04` (3× each), and once each `0x21`, `0x2c`, `0x2d`, `0x34`, `0x44`, `0x61` (unknown).

### State machine

`tutorial_update` (`+0x3864`, export) switches on the state `0x17f2c` (table `+0xf54c`): 1 runs `tutorial_step`; 3 waits for the message window; 4 and 6 wait for the input filter / event hook; 5 counts down `0x17f5c`; 7 runs the highlight timer (`+0x5000`); 8 ends the lesson. `0x17f30`/`0x17f34` hold the script and its program counter; `0x17f3a`/`0x17f3c` the awaited input kind and card; `0x17f3e`/`0x17f40`/`0x17f42` the `on_event` handler; `0x17f4a`–`0x17f4e` the awaited event; `0x17f58` the last answer.

## Functions

| Module offset (address) | Name | Confidence | Evidence |
| --- | --- | --- | --- |
| `rel_duel_eng +0x1e80e4` (`0x09dc94e4`) | `duel_core_load_ydq` | H | Line splitter, defaults, post-parse commands; called only by `duel_core_start_mode2/3`. |
| `rel_duel_eng +0x1e6ecc` (`0x09dc82cc`) | `duel_core_parse_ydq_line` | H | All `.ydq` key strings (`0x09e01be8`–`0x09e01d94`) are referenced only here. |
| `rel_duel_eng +0x1e6e08` (`0x09dc8208`) | `duel_core_set_phase` | M | Stores the phase in `0x09e2d1e8`; called for `Phase=` and by the tutorial for commands 10–15. |
| `rel_duel_eng +0x1df3f8` (`0x09dc07f8`) | `duel_core_push_command` | H | Appends `(u16 op, a, b, c)` to the 256-entry queue `0x09e29100`. |
| `rel_duel_eng +0x44c` (`0x09be184c`) | `duel_core_set_turn` | H | Writes `0x09e2d1e0`. |
| `rel_tutorial +0x3748` | `tutorial_start_lesson` | H | `.ydq`/`tuto_cmd` loading. |
| `rel_tutorial +0x3864` | `tutorial_update` | M | Per-frame state machine. |
| `rel_tutorial +0x3974` | `tutorial_shutdown` | M | Frees the script. |
| `rel_tutorial +0x39b4` | `tutorial_filter_input` | M | See above. |
| `rel_tutorial +0x3df8` | `tutorial_on_duel_command` | M | See above. |
| `rel_tutorial +0x43a8` | `tutorial_check_cursor` | M | Kinds 0, 6, 12. |
| `rel_tutorial +0x4724` | `tutorial_fetch_record` | H | |
| `rel_tutorial +0x473c` | `tutorial_exec_command` | H | Jump table `+0xf608`. |
| `rel_tutorial +0x4b70` | `tutorial_exec_duel_command` | H | |
| `rel_tutorial +0x4c38` | `tutorial_step` | H | |
| `rel_tutorial +0x4cf0` | `tutorial_load_text_line` | H | |
| `rel_tutorial +0x4e4c` | `tutorial_goto_label` | H | |
| `rel_tutorial +0x4ed0` | `tutorial_load_reset_field` | H | |

## Open questions

- Draw order of the deck list (does command `0x56` take entries from the start?), and the effect of the `0x08`-word serial bookkeeping.
- The duel-engine command codes: only 0x0a–0x0f, 0x27, 0x29, 0x35, 0x39, 0x43, 0x56 and 0x67 are understood; the event codes 4, 5, 6, 13, 26, 34, 54, 55 are named only from context.
- The meaning of `_Param`, `PUTBYANOTHER`, `PARTICULAR` and the equip record fields; no file uses them. Who calls `duel_core_start_mode2` (another `.ydq` user, possibly a puzzle mode) is open.
- The highlight regions 16–20 and the input codes of the filter in `rel_duel_draw`.
