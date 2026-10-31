# Duel tutorial: `.ydq` duel setups, `tuto_cmd_NN.bin` scripts, `tuto_text_<l>.bin`

Tool: `tools/tutorial.py` (`--check` over every member, a readable listing with text and card names resolved; it also lists the deck-building tutorial of `deck/tutorial.ehp`, see `deck.md`, and checks the legacy `tutorial/` set, see the last section). Tests: `tools/tests/test_tutorial.py` (synthetic data only).

Module offsets are unrelocated (`+0x0`). `rel_duel_eng` addresses are also given at its runtime base `0x09be1400` (as in `re/functions.csv`); `rel_tutorial`'s runtime base is unknown: none of the seven PPSSPP symbol exports was taken during a tutorial, and `tools/modules.py base` matches at most 89 of its 161 function starts in any of them (noise). Its function names are therefore kept at module offsets in `re/names-rel_tutorial.csv` (module `rel_tutorial`, import at image base `0x0`). Imports were resolved with `tools/prx_imports.py` (base 0) and, for the 1,409 imports from other game modules, against those modules' export tables.

| Structure | Where | Status |
| --- | --- | --- |
| `.ydq` duel setup (`[DUEL QUESTION]` text) | `d_tutorial/tutorial.ehp`, 50 members | documented (every key, from the parser) |
| `tuto_cmd_NN.bin` tutorial script | same archive, 17 members | documented (record layout, all 21 tutorial opcodes, all 16 duel-engine codes and 11 UI events the scripts use) |
| `tuto_text_<l>.bin` text table | same archive, 6 members | documented |
| Legacy set `NN_duel_command.bin`, `NN_field_set.txt`, `field_reset_NN.txt`, `NN_message_res.bin` | `tutorial/tutorial_all.ehp`, `tutorial/tutorial_<l>.ehp` | not loaded by the game (confidence high); framing documented, see "The `tutorial/` directory" |

## Archive and lessons

`d_tutorial/tutorial.ehp` holds 73 members: `tuto_cmd_00`–`16.bin` (17 scripts), `tuto_field_00`–`16`, `20`–`25.ydq` (23 initial setups), `tuto_field_reset00`–`25`, `27.ydq` (27 mid-lesson setups; `reset26` does not exist) and `tuto_text_{e,f,g,i,j,s}.bin`.

`rel_tutorial` (library `libtutorial_rel`, 13 exports, imported by `rel_duel_mgr`) runs a lesson. `duel_core_tutorial_load_archive` (`+0x58f0`, from `duel_core_tutorial_init`) loads `d_tutorial/tutorial.ehp` (`container_load_file`, buffer `0x187a8`) and binds it with `container_ehp_bind_with_callback`; `duel_core_tutorial_load_member` (`+0x5a98`) then copies a member out of that buffer by name (`container_ehp_find_member`), so every `d_tutorial/tutorial/<member>` path below is a member of this one archive (H). `duel_core_tutorial_start_lesson(lesson, callback, …)` (`+0x3748`, called by `rel_duel_mgr +0xfd74` with the lesson number from byte `+403` of a session record):

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

`u32 (offset, size)` pairs, one per line, then the text; line count = first offset / 8 (878 in all six languages). Line `n` occupies `[offset, offset + size)`; the lines are contiguous and `size` is a multiple of 4. Text is UTF-16LE (Shift-JIS in `tuto_text_j.bin`), NUL-terminated and zero-padded. `@<digit>` is a colour escape (`@2` on, `@0` off). `duel_core_tutorial_load_text_line(n)` (`+0x4cf0`) opens `tuto_text_%c.bin` with `"jegfis"[language & 7]` (language from `0x08857b80`), seeks to `8n`, reads the pair, then the text into the buffer at `0x17f60`.

The 17 scripts reference 878 text lines through opcodes 1, 2 and 8: every line exactly once, in order (script 0: lines 0–52, … script 16: 823–877).

## `tuto_cmd_NN.bin`: tutorial script

A sequence of 8-byte records `u16 op, u16 a, u16 b, u16 c`, ended by a record with `op == 0`, which is always the last record (17/17 files; 400–1,584 bytes, 1,715 records).

`duel_core_tutorial_step` (`+0x4c38`) fetches the record at the program counter and advances it by 8 (`+0x4724`), then:

- `op == 0`: end of lesson (state 8).
- `op & 0x4000`: tutorial command `op & 0x3fff` (`duel_core_tutorial_exec_command`, `+0x473c`, jump table at `+0xf608`, 21 entries).
- otherwise: **duel-engine command**. `duel_core_tutorial_exec_duel_command` (`+0x4b70`) passes the record unchanged to `duel_core_push_command(op, a, b, c)` (`0x09dc07f8`, `rel_duel_eng +0x1df3f8`), which appends it to the engine's 256-entry command queue at `0x09e29100` (count `0x09e29900`; skipped while `0x09e02998` = 3). Bit 15 of `op` selects side 1, as in the `.ydq` loader. Codes 10–15 also call `duel_core_set_phase(code − 10)` directly.

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
| 6 | 61 | goto | `a` label | `duel_core_tutorial_goto_label` (`+0x4e4c`): linear search for `op & 0x3fff == 5` with that `a`; continues after it. |
| 7 | 59 | if_answer | `a` value, `b` label | Goes to `b` when the last answer (`0x17f58`) equals `a`. |
| 8 | 58 | question | `a` text line | Like 1 (style 36) with the number of `\n` in the text as fourth argument: line 1 is the question, the others the choices; the chosen index lands in `0x17f58`. Every use is followed by `if_answer` records (answers 1–3). |
| 9 | 88 | show_card | `a` card id; 0 hides; 1–2 a card remembered from a duel event (`0x17f50[a]`) | Card picture (`+0x57d4`). |
| 10 | 28 | load_field | `a` | `duel_core_tutorial_load_reset_field` (`+0x4ed0`): `tuto_field_reset%02d.ydq` through `duel_core_start_mode3`; state 2. |
| 11 | 2 | wait | `a` frames | State 5 (counter `0x17f5c`). |
| 12 | 109 | wait_input | `a` kind, `b` card id or argument (0 = any) | State 4: wait for the player action `a` (table below). |
| 13 | 8 | set_turn | `a` | `0x09be184c(a)`: writes the turn counter `0x09e2d1e0`. Always 2 in the data. |
| 14 | 85 | wait_event | `a` UI event, `b` argument (0 = any), `c` minimum | State 6 until the engine posts UI event `a` whose second argument (`a2`) equals `b` (export `duel_core_tutorial_on_ui_event`, `+0x3df8`; "Hooks and UI events" below); for event 54 the third argument (`a3`) must be ≥ `c`. |
| 15 | 27 | card_part | `a` 0–9 | `+0x57dc`: points at part `a` of the displayed card (from the surrounding text: 2 type, 3 ATK/DEF, 4 description, 7 and 9 name and illustration, 8 attribute; 0 off). |
| 16 | 57 | on_event | `a` UI event (0 = clear), `b` label, `c` argument (0 = any) | Registers a handler: when UI event `a` arrives with first argument (`a1`) `c` (or, for 66, when the menu is cancelled, see `+0x38a8`), go to label `b`. Used as "if the player backs out, show the hint again": `on_event 66, <label before the hint>`. |
| 17 | 10 | flag_on | `a` bit | Sets bit `a` of `0x17f44`: bit 1 lets every input through the filter; bit 3 also sets `0x18794` = 2 and calls `+0x53fc(…, 1)`. |
| 18 | 9 | flag_off | `a` bit | Clears it (bit 3 reverses the extra actions). |
| 19 | 1 | count_answer | `a` (1) | Counts the cards of a list (`0x09be189c`, `+0x5268`) for which `0x0885f864(id)` returns 2 and stores the count as the answer. |
| 20 | 4 | open_list | `a` side, `b` location | `0x09dcf950(a, b, 0, 1)` then `+0x58e8`; state 2. Used with location 14 (the graveyard list). |

### `wait_input` kinds

The input filter `duel_core_tutorial_filter_input` (`+0x39b4`, registered with `rel_duel_draw`) receives each player action as a code and blocks it (returns 0) unless it is the awaited one; the card under the cursor must equal `b` when `b` ≠ 0. On a match it removes the hint and, for some kinds, resumes the script. Kinds 0, 6 and 12 are also checked against the cursor position by `+0x43a8` (zone 11 = hand, 0–4 monster zones, 5–9 spell/trap zones). Names come from the hint line each script shows just before the `wait_input` (all 109 uses agree); the input code is what the filter compares.

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

### Hooks and UI events

`duel_core_tutorial_init` (`+0x5b78`, called by `duel_core_tutorial_start_lesson` with its third argument) installs these hooks (H, from the registration calls at `+0x5c18`–`+0x5c48`):

| Hook | Registered with | Function | Role |
| --- | --- | --- | --- |
| UI event hook | `rel_duel_eng 0x09be147c` (stores it at `0x09e01e10`, the hook `duel_core_post_ui_event` calls) | `duel_core_tutorial_ui_event_hook` (`+0x6098`) | Reads the four event arguments (`0x09be1488`, copies of `0x09e01e14`–`0x09e01e20`), calls `duel_core_tutorial_on_ui_event(event, a1, a2, a3)` and, when that returns non-zero, forwards the event to the previous hook (`0x187a4`, the third argument of `start_lesson`: `rel_duel_mgr +0x10690`, which passes it on towards `rel_duel_draw`). |
| Duel-flow gate | `rel_duel_eng 0x09be20e0` (hook `0x09e01e3c`) | `duel_core_tutorial_gate_duel_flow` (`+0x4310`) | Called by `duel_core_run_duel_flow` (`0x09dcb5a4`, call at `0x09dcb640`) when the command queue is idle and the duel mode `0x09e2d1f4` is 3 (tutorial); a non-zero return holds the duel flow for this frame. Returns 0 for lessons ≥ 20 and in states 4, 6 and 8, so the engine runs only while the tutorial waits for the player or for an event. State 2: `duel_core_tutorial_wait_ui_idle` (`+0x4dac`) resumes the script (state 1) once `duel_core_is_ui_event_busy(e)` is 0 for every UI event 0–`0x4e`. State 3: `duel_core_tutorial_wait_message` (`+0x4ca8`) resumes once the window has closed and copies the dialog answer (`0x09be1dac`, word `0x09e2d248`) to `0x17f58`. |
| Input filter | `rel_duel_draw 0x0989c6d4` | `duel_core_tutorial_filter_input` (`+0x39b4`) | See "`wait_input` kinds". |
| Cursor check | `rel_duel_draw 0x0989c72c` (through the wrapper `+0x60e0`, which returns 0) | `duel_core_tutorial_check_cursor` (`+0x43a8`) | Kinds 0, 6, 12. |
| Answer hook | `rel_duel_draw 0x0989c734` | `duel_core_tutorial_on_answer` (`+0x457c`) | Kind 13 (answer YES): resumes (state 1) when the answer argument is 1. |

**The events are UI events, not command codes** (H): `duel_core_post_ui_event` (`0x09be1400`) stores its four arguments and calls the hook, so every number that `wait_event` and `on_event` name is the first argument of a `duel_core_post_ui_event` call. `duel_core_tutorial_on_ui_event` (`+0x3df8`), in order:

1. Lesson ≥ 20: forward, nothing else.
2. An `on_event` handler whose event matches (and whose argument is 0 or equals `a1`) jumps to its label, sets state 1 and is cleared.
3. In state 6, the awaited event with `a2` equal to the `wait_event` argument (or argument 0) resumes the script: events 4 (unless `a1` = 7), 54 (only when `a3` ≥ the minimum) and 55 at once (state 1), any other event once the UI is idle (state 2).
4. Unless bit 2 of the flag word `0x17f44` is set (`flag_on 2`), UI event 54 with `a1` = 3 and `a3` < 2 is answered with 0 (`0x09be1db8`, answer word `0x09e2d248`) and **not forwarded**: that dialog never appears in a lesson. Every other event is forwarded.
5. In state 4, the UI event that confirms the awaited player action completes the `wait_input` (state 2 unless noted; "hint off" = `duel_core_tutorial_hide_hint`, `+0x4ea0`): `0x38` summon done (kind 1); `0x1e` card set (kinds 5, 11); 5 phase banner with `a2` = the awaited phase (kind 2); `0x1c` position changed (kind 7); `0x2c` Tribute (kind 8, hint off; kind 16, hint off and an `on_event 66` handler cleared); `0x22` activation shown (kind 10, hint off); `0x2f` Fusion Material moved (kind 15, as kind 16); `0x19` (kind 17, hint off); `0x39` (kind 14); 54 with `a1` = 5, the phase menu (kind 18, hint off, state 1).
6. UI event `0x0d` (battle damage) stores the attacker's and the target's card ids (`0x09be1c88(side, slot)` with the attacking side `0x09e28620`, attacker slot `0x09e2863c` and the words at `+4`/`+0x20`, then `0x09be1a10` for the id) in `0x17f52` and `0x17f54`, the cards of `show_card 1` and `show_card 2`.

UI events in the scripts (posters are the `duel_core_post_ui_event` call sites with that constant):

| Event | Uses (`wait_event` / `on_event`) | Posted by | Meaning | Confidence |
| --- | --- | --- | --- | --- |
| 4 | 54 / 2 | `0x09dcc5c8` in `duel_core_run_turn_flow`, from the request word `0x09e2d24c` that `duel_core_begin_player_input` (`0x09dce84c`) writes; `a1` = the input mode | The engine asks the player for the next action (mode 7 does not count) | M |
| 5 | 5 / 0 | `duel_core_cmd_enter_phase` | Phase banner `(side, phase)`; always waited for with argument 5 (End Phase) | H |
| 6 | 7 / 0 | `duel_core_next_turn` | Turn change (new side) | H |
| 10 | 0 / 6 | `duel_core_cmd_begin_attack_selection` | Attack-selection mode | H |
| 13 | 2 / 0 | `duel_core_cmd_show_battle_damage` | Battle damage shown (`0x0d`) | H |
| 26 | 3 / 0 | the movement commands (`0x2c`, `0x50`, `0x51`, `0x56`, destroy, …) | A card moved (`0x1a`) | H |
| 34 | 1 / 0 | `duel_core_cmd_announce_activation` and two other handlers | Activation shown (`0x22`) | H |
| 46 | 0 / 3 | `duel_effects_resolve_fusion_summon` | Fusion Summon (`0x2e`) | M |
| 54 | 11 / 7 | `duel_core_show_hint`, the yes/no, option and number prompts, `duel_core_show_phase_menu` | Dialog or menu (`0x36`); `a1` = kind | H |
| 55 | 2 / 0 | `duel_core_open_card_list` | Card list opened (`0x37`) | H |
| 66 | 0 / 30 | none with a constant in `rel_duel_eng`; command `0x68` posts `0x42` | `on_event 66` fires from `duel_core_tutorial_update` when `rel_duel_draw 0x0989c990` reports the menu closed (`+0x38a8`); a UI event `0x42` would also match | M |

### Duel-engine commands in the scripts

59 records, all decoded; `tutorial.py --check` fails on a code without a handler and notes a code missing from its table. Handlers come from the jump table of `duel_core_execute_command` (`0x09dc0974`, table `rel_duel_eng +0x21f544`, bound `sltiu 0x69`: codes 0–`0x68`, code 0 the empty default). Side = bit 15 of `op`. `duel-phases.md`, `summon.md`, `chain.md` and `duel_core.md` describe the shared handlers.

| Code | Uses | Handler | Arguments in the scripts | Effect | Confidence |
| --- | --- | --- | --- | --- | --- |
| `0x03` | 3 | `duel_core_cmd_end_turn_cleanup` (`0x09dbc584`) | — | End-of-turn bookkeeping (UI event `0x4c`); always followed by `0x04` | H |
| `0x04` | 3 | `duel_core_next_turn` (`0x09dbc184`) | — | The other side becomes the turn player, turn counter + 1, phase 7 | H |
| `0x0c`, `0x0d`, `0x0f` | 26, 4, 3 | `duel_core_cmd_enter_main1_phase`, `…_battle_phase`, `…_end_phase` | — | Enter Main Phase 1, Battle Phase, End Phase (`duel_core_cmd_enter_phase(code − 10)`) | H |
| `0x21` | 1 | `duel_core_cmd_set_player_flag` (`0x09dbc7dc`) | `(16, 1, 0)` | Sets bit 16 of player word `+0x120` ("summon declared face-up", `summon.md`) | H |
| `0x27` | 11 | `0x09db78dc` | `a` location (0–10 field slots, 13 deck, 14 graveyard, 15 banished), `b` card (0 in the data) | Field cursor: posts UI event 8 `(side, location, index)` and waits for it; with `b` ≠ 0 the index is that card's position, and in the graveyard or banished list (14/15) the card is first brought up (`0x09c01030`/`0x09c01170`, UI event `0x18`) | M |
| `0x2c` | 1 | `0x09dbf23c` | `(0xc044, 80, 0x700)` | **Puts a card on the field as a trap monster.** `b` = card instance (found with `duel_core_find_card_location`); `a` = destination: bit 0 side, bits 1–5 slot (here 2), bits 6–13 non-zero = apply the trap-monster setup, bits 14–15 passed to `duel_core_zone_insert`; `c` is written to the slot's `+0x0c` parameter word (the field the `.ydq` key `_Param` sets). Moves the card (`duel_core_zone_remove`/`_insert`, UI event `0x1a`), sets slot flag bits 3 and 10, increments the player's summon counter `+0x20`. For the trap monsters it lists (Embodiment of Apophis `0x1472`, Metal Reflect Slime `0x1636`, Zoma the Spirit `0x172f`, Stronghold the Moving Fortress `0x1809`, Cyber Shadow Gardna `0x1aca`, and `0xea9`) it attaches effect `(5, 0x1472, c)` and ORs `0x1000` into the slot flags, the `TRAPMONSTER` bit of the `.ydq` loader. UI events `0x26`, `0x39` | M (H for the data flow) |
| `0x2d` | 1 | `duel_core_cmd_announce_activation` (`0x09dba88c`) | `(7, 5234, 80)` | Shows the activation of the card in slot 7 (`b` card id, `c` instance) | H |
| `0x34` | 1 | `duel_core_cmd_change_face` (`0x09db6cc0`) | `(7, 1, 4)` | Turns the card in slot 7 face-up, reason 4 | H |
| `0x44` | 1 | `duel_core_cmd_summon_finalize` (`0x09dbdedc`) | `(2, 5, 0)` | Finalises the summon in slot 2; `b` bit 0 checks `card_db_is_special_summon_only`, bit 2 sets the Special-Summon flags `0x40040`; no Tributes | M |
| `0x56` | 3 | `0x09dbb7d8` | `(0, 5, 0)` for each side, `(0, 1, 0)` | Draw `b` cards (UI event `0x43`, then the move, UI event `0x1a`); the engine's own poster is `duel_core_draw_cards_ex` | H |
| `0x61` | 1 | `0x09dbe9cc` | `(5234, 1, 6)` | Presentation only: posts UI event `0x44 (side, a, b << 8 | c)` (summon declaration: card, position, kind 6) and waits for it, then UI event 9 | H |

Lesson 13 is the only script that performs a whole action itself: `0x0c`, then `0x34` (the Set trap in slot 7 turns face-up), `0x2d` (its activation), `0x21 16`, `0x61`, `0x2c` (the trap, instance 80, becomes a monster in slot 2) and `0x44`: the Special Summon of Embodiment of Apophis (`5234` = `0x1472`) as a trap monster, posted as engine commands because the player does not perform it.

The `.ydq` loader also posts `0x29` (slot flag bit), `0x35` (equip record), `0x39` (slot parameter), `0x43` (place on field), `0x56` (opening hands), `0x67` (turn limit) and `10 + phase`. Code `0x68` (`0x09dbd0b0`) posts UI event `0x42 (side, a, b | c << 16)` and waits for it; no TF3 file uses it, but it wraps every tutorial step of the legacy scripts (last section).

### State machine

`duel_core_tutorial_update` (`+0x3864`, export, called every frame by `rel_duel_mgr +0x427c`) first calls `+0x5f74` (and returns 0 when that returns 1), then fires an `on_event 66` handler when `rel_duel_draw` reports the menu closed, then switches on the state `0x17f2c` (table `+0xf54c`): 1 runs `duel_core_tutorial_step`; 5 counts down `0x17f5c`; 7 runs the highlight timer (`+0x5000`); states 2 and 3 are advanced by the duel-flow gate, 4 by the input filter and the UI hook, 6 by the UI hook; 8 is the end. It returns 0 in states 4, 6 and 8. `0x17f30`/`0x17f34` hold the script and its program counter; `0x17f3a`/`0x17f3c` the awaited input kind and card; `0x17f3e`/`0x17f40`/`0x17f42` the `on_event` handler (event, label, argument); `0x17f4a`–`0x17f4e` the awaited event, argument and minimum; `0x17f52`/`0x17f54` the battle cards; `0x17f58` the last answer.

## Functions

| Module offset (address) | Name | Confidence | Evidence |
| --- | --- | --- | --- |
| `rel_duel_eng +0x1e80e4` (`0x09dc94e4`) | `duel_core_load_ydq` | H | Line splitter, defaults, post-parse commands; called only by `duel_core_start_mode2/3`. |
| `rel_duel_eng +0x1e6ecc` (`0x09dc82cc`) | `duel_core_parse_ydq_line` | H | All `.ydq` key strings (`0x09e01be8`–`0x09e01d94`) are referenced only here. |
| `rel_duel_eng +0x1e6e08` (`0x09dc8208`) | `duel_core_set_phase` | M | Stores the phase in `0x09e2d1e8`; called for `Phase=` and by the tutorial for commands 10–15. |
| `rel_duel_eng +0x1df3f8` (`0x09dc07f8`) | `duel_core_push_command` | H | Appends `(u16 op, a, b, c)` to the 256-entry queue `0x09e29100`. |
| `rel_duel_eng +0x44c` (`0x09be184c`) | `duel_core_set_turn` | H | Writes `0x09e2d1e0`. |
| `rel_duel_eng +0x1d64dc` (`0x09db78dc`) | engine command `0x27` handler | M | Field cursor, UI event 8 (above). Not renamed here: the `duel_eng` names are kept by another work stream. |
| `rel_duel_eng +0x1dde3c` (`0x09dbf23c`) | engine command `0x2c` handler | M | Trap monster placement (above). |
| `rel_duel_eng +0x1da3d8` (`0x09dbb7d8`) | engine command `0x56` handler | H | Draw. |
| `rel_duel_eng +0x1dd5cc` (`0x09dbe9cc`) | engine command `0x61` handler | H | Summon declaration display. |
| `rel_duel_eng +0x1dbcb0` (`0x09dbd0b0`) | engine command `0x68` handler | H | Relays to UI event `0x42`. |

`rel_tutorial` names are in `re/names-rel_tutorial.csv` (group `duel_core`, module offsets):

| Module offset | Name | Confidence | Evidence |
| --- | --- | --- | --- |
| `+0x3748` | `duel_core_tutorial_start_lesson` | H | Export; `.ydq`/`tuto_cmd` loading; called by `rel_duel_mgr +0xfd74`. |
| `+0x3864` | `duel_core_tutorial_update` | M | Export; per-frame state machine; called by `rel_duel_mgr +0x427c`. |
| `+0x3974` | `duel_core_tutorial_shutdown` | M | Export; frees the script. |
| `+0x39b4` | `duel_core_tutorial_filter_input` | M | Export; registered with `rel_duel_draw 0x0989c6d4`. |
| `+0x3df8` | `duel_core_tutorial_on_ui_event` | H | Export; called only by the UI event hook with the event's four arguments (formerly `tutorial_on_duel_command`). |
| `+0x4310` | `duel_core_tutorial_gate_duel_flow` | H | Export; registered with `rel_duel_eng 0x09be20e0`, called from `duel_core_run_duel_flow`. |
| `+0x43a8` | `duel_core_tutorial_check_cursor` | M | Export; kinds 0, 6, 12. |
| `+0x4548` | `duel_core_tutorial_fire_event_handler` | H | Export; goto the `on_event` label, clear the handler, state 1. |
| `+0x457c` | `duel_core_tutorial_on_answer` | M | Export; registered with `rel_duel_draw 0x0989c734`; kind 13. |
| `+0x45f8` | `duel_core_tutorial_redraw_hint` | H | Export; redraws the hint `0x17f48` when ≥ 0. |
| `+0x4624` | `duel_core_tutorial_is_busy` | M | Export; 0 for lessons ≥ 20 and in states 4 and 6, else 1; read by `rel_duel_mgr +0xfdcc`. |
| `+0x4724` | `duel_core_tutorial_fetch_record` | H | |
| `+0x473c` | `duel_core_tutorial_exec_command` | H | Jump table `+0xf608`. |
| `+0x4b70` | `duel_core_tutorial_exec_duel_command` | H | |
| `+0x4c38` | `duel_core_tutorial_step` | H | |
| `+0x4ca8` | `duel_core_tutorial_wait_message` | M | State 3 of the gate. |
| `+0x4cf0` | `duel_core_tutorial_load_text_line` | H | |
| `+0x4dac` | `duel_core_tutorial_wait_ui_idle` | H | State 2 of the gate. |
| `+0x4e4c` | `duel_core_tutorial_goto_label` | H | |
| `+0x4ea0` | `duel_core_tutorial_hide_hint` | H | Same body as opcode 3. |
| `+0x4ed0` | `duel_core_tutorial_load_reset_field` | H | |
| `+0x58f0` | `duel_core_tutorial_load_archive` | H | Loads and binds `d_tutorial/tutorial.ehp`. |
| `+0x5a98` | `duel_core_tutorial_load_member` | H | Member copy from the bound archive. |
| `+0x5b78` | `duel_core_tutorial_init` | H | Resets state, loads the archive, registers the hooks. |
| `+0x6098` | `duel_core_tutorial_ui_event_hook` | H | See "Hooks and UI events". |
| `+0x09e4` | `duel_core_tutorial_init_graphics` | M | Looks up `tuto_duel01.gim`, `window02.gim`, `tuto_bigwin01.gim` in the archive at `0x17da4` (dead, see below). |
| `+0x1584` | `duel_core_tutorial_draw_lesson_image` | M | `sprintf("tuto_duelimg%02d.gim")` from the same archive; returns at once when `0x17da4` is 0. |

Exports `+0x468c` and `+0x46dc` (a fade request through `0x08844ec0` and its state `0x18760`) are not named.

## The `tutorial/` directory: a legacy set the game does not load

`USRDIR/tutorial/` holds `tutorial_all.ehp` (12 members), `tutorial_{e,f,g,i,s}.ehp` (26 members each; there is no `_j`) and `face/bu_{ask,cro,dai,hyt,jdi,maa,mab,mis,ryo,sam,sho}.ehp`. **Verdict: not used by TF3. Confidence high.** Basis:

1. **No reference.** The game opens files only by path (`file-index.md`: the index is built from the ISO directories, no hidden table). No string in `BOOT.BIN`, in the 36 `gmodule/` PRXs or in any file on the disc (every archive and gzip member searched, ASCII and UTF-16LE) contains `tutorial/` other than the `d_tutorial/tutorial/<member>` paths of `rel_tutorial`, which resolve inside the bound `d_tutorial/tutorial.ehp` (above). None contains the member names `_duel_command`, `_message_res`, `_field_set` or `field_reset_`. No binary has a standalone `tutorial` or `face` path component that the generic builders (`"%s/%s"` in `rel_deck`, `rel_duel_draw`, `rel_field`) could join, and the portrait file names in `BOOT.BIN` are all `bu_*.ehp.gz`, which exist only in `field/bustup/`.
2. **The only shared names are dead code.** `rel_tutorial` still names `tuto_duel01.gim`, `tuto_bigwin01.gim` (`duel_core_tutorial_init_graphics`, `+0x9e4`) and `tuto_duelimg%02d.gim` (`duel_core_tutorial_draw_lesson_image`, `+0x1584`), which exist only in `tutorial/tutorial_*.ehp`. Both look them up in the archive pointer at `0x17da4` (`.bss`), which is read at `+0xa68`, `+0xe40` and `+0x15ac` and **written nowhere** (no store to it, no address of it taken, no relocated pointer to it in `.data`; the module exports only functions), so it stays 0 and all three paths are skipped.
3. **Different content.** No member of the set is byte-identical to a member of `d_tutorial/tutorial.ehp`. It has 5 duel setups and 4 scripts (TF3: 23 setups, 17 scripts), opening setups with full 40-card decks and no hand, and a different script format. `face/` holds older revisions of 11 portrait archives: same member names in part, no member identical to `field/bustup/<name>.ehp.gz`.

The set looks like the tutorial data of an earlier engine revision left on the disc (hypothesis, medium: the dead `tuto_*` look-ups and engine command `0x68` are the only traces in the code). The port does not need it.

### Legacy formats (framing only)

| Member | Layout | Status |
| --- | --- | --- |
| `NN_field_set.txt`, `field_reset_NN.txt` (`NN` = 01–05 / 00–04) | The `.ydq` text format above; all 10 parse with no ignored line (`tutorial.py`). Identical in all six archives. | framing H |
| `NN_duel_command.bin` (01–04, identical in all five language archives) | `u16 count`, then `count` records `u16 op, a, b, c` (size = 2 + 8 × count in all four; no end record). `op` low 15 bits = engine command code (all ≤ `0x68`), bit 15 = side. 277 of the 1,550 records are plain engine commands (most often `0x56` draw 27×, `0x0e` 20×, `0x2c` 18×, `0x02` 17×, `0x0d` 16×); 1,273 are command `0x68`, whose `a & 0xff` is a sub-operation (22 distinct values, 0–31) and `a >> 8` a parameter. | framing H, sub-operations unknown |
| `NN_message_res.bin` | Headed string table without end offset (`string-tables.md`, layout A). With sub-operation 0, `c` is a line index: the indices run in order and the largest equals count − 1 in all four lessons (148, 126, 197, 189 lines). | H |
| `tuto_duel01.gim`, `tuto_bigwin01.gim`, `tuto_duelimg01`–`06.gim` | GIM images (`gim.md`); `tuto_duelimg*` differ per language. | — |

`tutorial.py <USRDIR>/tutorial/tutorial_*.ehp --check` checks this framing (record count, codes within the dispatcher, message indices within the table, the setups). The meaning of the `0x68` sub-operations is not recoverable from TF3: command `0x68` only relays them as UI event `0x42`.

## Open questions

- Draw order of the deck list (does command `0x56` take entries from the start?), and the effect of the `0x08`-word serial bookkeeping.
- The meaning of `PUTBYANOTHER`, `PARTICULAR` and the equip record fields; no file uses them. `_Param` is the slot word that command `0x2c` fills for trap monsters (its packing, e.g. `0x700` for Embodiment of Apophis, is not decoded). Who calls `duel_core_start_mode2` (another `.ydq` user, possibly a puzzle mode) is open.
- The highlight regions 16–20 and the input codes of the filter in `rel_duel_draw`.
- UI event 4's input modes (`duel_core_begin_player_input`) and why mode 7 is excluded; the dialog kind 3 that the tutorial answers with 0 unless `flag_on 2`.
- Whether `rel_duel_draw` still handles UI event `0x42` (the legacy relay of command `0x68`), and the two unnamed exports `+0x468c`/`+0x46dc`.
- `rel_tutorial`'s runtime base: take a PPSSPP symbol export during a lesson and run `tools/modules.py base`.
