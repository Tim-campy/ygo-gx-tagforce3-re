# PPSSPP verification plan

Almost everything in `docs/subsystems/` comes from static analysis. This plan is the step-by-step runtime check that turns the hypotheses the port depends on most into `verified` evidence (`docs/PROGRESS.md`). The maintainer runs it in the portable PPSSPP at `external/ppsspp` (Windows, v1.20.x at the time of writing). The agent then updates the documents and registries from the filled-in result tables.

The checks are grouped into sessions so that each needs as little play as possible. Sessions A–D cover the duel engine; Sessions E and F collect the checks that later static work left for PPSSPP (save data, world, story, shop, UI tables, movies, sound, tutorial, the AI plan and the duel leftovers), each split into scene blocks that can be done one sitting at a time:

| Session | Where in the game | Checks | Play time (estimate) |
| --- | --- | --- | --- |
| 0 | Any duel and the free-roam field | M1, M2: module bases and the save-state address | 10 min, then 2 min at the start of every later session |
| A | One single duel against a CPU | A1–A10: phases, turn, draw, LP, battle, summon, ATK/DEF, chain, once per turn, trigger order, AI visibility | 1 duel, about 40 min |
| B | One tag duel | B1, B2: partner swap and tag state | Two turn changes, about 15 min |
| C | Free roam with a partner | C1–C6: calendar, daily pairing, gift points, item counters, DP, partner word | One in-game day, about 20 min |
| D | One single duel against a CPU, with staged hands | D1, D2: the 16-link chain limit and the 16-trigger limit (replaces the former optional A11) | 1 duel, about 30 min |
| E | Outside the duel, in seven scene blocks: boot and title, save/load, free roam, shop, deck editor, tutorial lesson, minigames | E1–E24 (E6, E14, E15, E17 optional): file index, opening movie, title message tables, sound play call, save regions, `hud_marker`, BGM fade, arrival cells, door locks, chapter stage/step, story state 46, one pack purchase and the rarity box, deck-editor and progress bytes, `rel_tutorial` base, `.ydq` draw order, tutorial resumption, minigame scores and result table | 10–45 min per block, about 3 h in all |
| F | Duels: own turns, CPU turns, a field-spell duel, saves around duels, and D2 | F1–F12 (F8 optional): turn-0 draw, LP writers, direct and piercing attacks, A6 steps 3–6, Magic Jammer, the AI plan comparison (the seven `ai.md` checks), the `ddstrtbl` HUD tables, backdrop frame rate, duel-record saves, D2 | about 2 h 30 in five blocks |

Legal boundary (`CLAUDE.md`): savestates, `.sym` exports, `DATA0` files and memory dumps contain game data. They stay under `external/ppsspp/` or `ghidra/` (both git-ignored; `*.ppst` and `*.sym` are ignored as well) and are never committed. Result tables record only addresses, small numbers and card ids, never dumps.

## The PPSSPP tools used

Everything below uses the classic Windows debugger windows: **Debug → Disassembly** (Ctrl+D) and **Debug → Memory View** (Ctrl+M). PPSSPP 1.20 also ships a newer in-window debugger with the same features under similar names. Use whichever you prefer. Debugger features have changed between releases, so each feature comes with its simplest fallback:

| Need | Feature (Disassembly window → Breakpoints tab → right-click → Add, or the breakpoint dialog) | Fallback |
| --- | --- | --- |
| Stop when code runs | Execute breakpoint at an address, optional **Condition** (an expression such as `a0 == 1`) | None needed. |
| Record without stopping | Untick **Break** and tick **Log**. The log text can contain expressions in braces, e.g. `cmd {a0} {a1}`, which are interpolated with registers (and, in recent builds, memory reads such as `{[0x09e2d1e8]}`). Output appears in the log console (**Debug → Log Console**). | If memory reads are not interpolated, log registers only and read memory by hand. If nothing appears, check that logging is enabled and the log level shows debugger messages. |
| Stop when data changes | Memory breakpoint: address, size, **Write** (or **On change**), optional condition and log | If a memory breakpoint never fires, switch **Settings → System → CPU core** to the IR interpreter or interpreter, which check memory accesses most reliably. If conditions are not accepted on memory breakpoints, log every hit and filter afterwards. |
| Read a function's return value | Break at the entry, then **Step Out** and read `v0` in the register list | Break at the caller's next instruction. |
| Read memory | Memory View, **Goto** an address. Expression syntax: `[addr]` reads a 32-bit word (little-endian); mask with `& 0xffff` for a `u16` at an aligned address | Read the bytes and assemble them by hand (little-endian). |
| Freeze a moment | **File → Save State As…** (files go to `memstick/PSP/PPSSPP_STATE/`) | F2 saves and F4 loads the current slot. |
| Export symbols | **Debug → Save Map File…** (`.sym`) into `ghidra/` | None needed. |

A memory breakpoint on a write may fire **before** the store completes, so a value read from memory in that log line can still be the old one. Log the storing register, or break and single-step once (F10) before reading.

Expressions and addresses in this plan are runtime addresses. Values in `[...]` are memory reads. "Side 0/1" are the two duel sides. The human's side is the one with `[0x09e02998 + 4 × side] == 0` (`ai.md`).

## Memory edits: policy and shortcuts

Decision of 2026-10-26: a check that uses memory edits **counts as `verified`** when the edits only speed the test up or set up a situation that rarely arises in normal play. The behaviour that the check observes must still be produced by the game's own code.

### Policy

1. **Allowed edits** (and only these):
   - replacing the card id of a card that already exists in a hand, Deck or Graveyard list (shortcut S1), together with its card-instance entry, without changing any count;
   - setting Life Points to a non-zero value (S2);
   - setting the turn counter (S3), only in checks that do not test the turn counter or a rule that depends on it;
   - nothing else unless a check below names it explicitly.
2. **Never edit** what the check observes or anything the engine derives on its own: chain links (`0x09e28cb4`), the trigger queue (`0x09e289b4`), the timing queue (`0x09e28fa0`), the command queue (`0x09e29100`), the phase (`0x09e2d1e8`), the turn and Battle step indices (`0x09e2d210`, `0x09e2d220`), field slots (`+0x34 + i × 0x14`), flag words (slot `+0x10`, player `+0x120`), effect records (`0x09e2c7cc`), list counts (`+0x0c`–`+0x1c`), or the AI blocks (snapshot slots `0x09dff93c + n × 0x39f8`, battle plans `0x09e276e4`–`0x09e27f8f`, board view `0x09e28008 + side × 0x30c`).
3. **When to edit**: only while emulation is paused (Pause, or stopped at a breakpoint), in a frame where the game waits for the human (Main Phase menu, response prompt) and the AI is not simulating. The AI copies the whole duel state into a snapshot slot and restores it afterwards (`ai.md`, "State snapshots"), so an edit made while the snapshot depth `u16 [0x09e27fee]` is non-zero is silently undone. Check that it is 0 before every edit.
4. **Record every edit** in the results file, one line each: address, old value, new value, the moment (savestate name, turn, phase) and the purpose. Example: `0x09e2a64c u16 0x52ec → 0x5b44 (turn 4, Main 1, hand[0] Pot of Greed → D.D. Crow)`. A check whose results file lacks an edit that was made does not count.
5. **What must come from the game**: every value in the "Record" line of the check (counts, links, commands, states) is read after the game's own code has run on the edited state. If a result could only be explained by the edit itself (for example a count that is inconsistent with the list), report it as an edit artefact, not as a pass or a fail.
6. No checksum over the duel state is known: static analysis found none, and the save checksum, if any, is outside the duel. If the game behaves as if it detected an edit (the duel aborts, a card vanishes, the display freezes), reload the savestate and report it.

### Formats used by the shortcuts

Player block `P = 0x09e2a528 + side × 0xb3c` (`duel_core.md`, player state):

| What | Offset | Side 0 | Side 1 |
| --- | --- | --- | --- |
| Life Points (`int`) | `+0x00` | `0x09e2a528` | `0x09e2b064` |
| Hand count | `+0x0c` | `0x09e2a534` | `0x09e2b070` |
| Deck count | `+0x10` | `0x09e2a538` | `0x09e2b074` |
| Graveyard count | `+0x14` | `0x09e2a53c` | `0x09e2b078` |
| Hand list (entry `i` at `+4i`) | `+0x124` | `0x09e2a64c` | `0x09e2b188` |
| Deck list (entry 0 = top) | `+0x304` | `0x09e2a82c` | `0x09e2b368` |
| Graveyard list | `+0x55c` | `0x09e2aa84` | `0x09e2b5c0` |

**List entry (4 bytes)**: `u16 +0`: bits 0–13 card id, bit 14 bit 0 of the instance number, bit 15 a flag; `u16 +2`: bits 7–14 bits 1–8 of the instance number, the other bits flags. So `instance = ((u16[+2] >> 7) & 0xff) << 1 | (u16[+0] >> 14) & 1`.

**Card-instance entry (6 bytes)** at `0x09e2bbcc + 6 × instance`: `u16 +0` bits 0–13 card id (bits 14–15 kept), byte `+2` bits 0–1 the incarnation counter, `u16 +4` the head of the effect records that follow the card. Only the id bits are ever changed.

### S1. Replace the card id of an existing card

For a hand, Deck or Graveyard entry at address `E`:

1. Read `w0 = u16 [E]` and `w2 = u16 [E + 2]`. Compute the instance `n` and `I = 0x09e2bbcc + 6n`.
2. Check that `u16 [I] & 0x3fff == w0 & 0x3fff` (the entry and the instance agree). If not, do not edit; report it.
3. Write `u16 [E] = (w0 & 0xc000) | new_id` and `u16 [I] = (u16 [I] & 0xc000) | new_id`. Leave `w2`, the counts and every other byte alone.

Worked example: `w0 = 0x52ec`, `w2 = 0x0380` → id `0x12ec` (Pot of Greed), bit 14 = 1, `(0x0380 >> 7) & 0xff = 7`, `n = 7 × 2 + 1 = 15`, `I = 0x09e2bbcc + 0x5a = 0x09e2bc26`. New id `0x1b44` (D.D. Crow): `u16 [E] = 0x4000 | 0x1b44 = 0x5b44`.

Cautions: never raise a count (`+0x0c`, `+0x10`, `+0x14`) to make a list longer; a count must always equal the number of real entries, and every entry must own its instance. The presentation module (`rel_duel_draw`) keeps its own picture of the hand, so the card art shown for an edited hand card can stay stale until the card moves; the engine (menus, activation checks, the action mask queried by `duel_core_get_card_action_mask`) uses the edited id. Deck entries are not shown, so editing the top of the Deck before a draw avoids stale art: replace Deck entries 0…k−1 and let the game draw them. Deck index 0 = top is itself a hypothesis checked in A2; if A2 fails, use the last entries instead.

### S2. Set Life Points

Write the `int` at `P + 0x00` (side 0 `0x09e2a528`, side 1 `0x09e2b064`). Use it to pay repeated costs or to survive a long test, never in A3. Cautions: never write 0 or a negative value (`duel_core_check_win` ends the duel on LP 0, `battle.md`); the LP counter on screen stays stale until the next LP command (`0x23`–`0x25`), and the duel statistics are not updated; values above 99,999 may not fit the display.

### S3. Set the turn counter

Write `[0x09e2d1e0]`. Use it only to leave turn 0 (where the first player cannot battle, `duel_core_can_conduct_battle`) in checks that do not test that rule (A4, A6), never in A2. Cautions: the turn-limit logic compares the counter with `[0x09e2d1e4]` (`0xffff` = not started) and posts command 9 at milestones; keep the new value small (1–3) and check that `[0x09e2d1e4]` is `0xffff`. The turn side `0x09e2d1d8` is never edited.

## Session 0: module bases and the save-state address

Modules are loaded wherever the kernel allocator places them (`modules.md`, "Addresses: not fixed overlays"). The documented bases come from one session's load order. Every check below assumes them, so confirm them first, in every session or once per savestate family.

### M1. Module bases

- **Hypothesis**: `rel_duel_eng` at `0x09be1400`, `rel_duel_draw` at `0x0983fb00`, `rel_duel_mgr` at `0x08e9aa00` during a duel; `rel_story` at `0x08e9aa00` and `rel_field` at `0x090ced00` in free roam (`docs/subsystems/modules.md`, "Runtime bases"; high for this export, unknown for other load orders).
- **Quick check (every session, 1 minute)**: in the Disassembly window go to `0x09be1804` (`duel_core_get_phase`). It must be a three-instruction leaf that loads the word at `0x09e2d1e8`, e.g. `lui v0, 0x9e3` / `jr ra` / `lw v0, -0x2e18(v0)` (`0x09e30000 − 0x2e18 = 0x09e2d1e8`). The exact register may differ. In free roam, check the same way that `rel_story:0x08eaacc8` (`world_advance_time_slot`, 24 bytes) is a short function that starts there.
- **Full check (once per scene)**: boot PPSSPP fresh and go straight to the scene (PPSSPP keeps the symbols of modules that were unloaded, and a fresh boot keeps the export clean, an open question in `modules.md`). Export **Debug → Save Map File…** to `ghidra/duel-<date>.sym` (in a duel) and `ghidra/field-<date>.sym` (on the field map). Then run:

  ```
  python -I tools/modules.py base ghidra/duel-<date>.sym <USRDIR>/gmodule
  python -I tools/modules.py base ghidra/field-<date>.sym <USRDIR>/gmodule
  ```

- **Record**: base and "starts matched" for the modules above.
- **Expected**: the bases in the hypothesis with ≥ 90 % matched starts. **If a base differs, stop**: every module-relative address in this plan shifts by `new base − documented base` for that module (BOOT.BIN addresses never shift). Report it before continuing.

### M2. Save-state address

- **Hypothesis**: the game state that `DATA0` copies sits at `S = 0x08aa5794 + 4 × [0x08ac18c0]` (0–60 bytes of random shift per boot) (`docs/formats/save.md`, "In the game"; high, code).
- **Steps**: Memory View → Goto `0x08ac18c0`, read the word `r` (0–15), and compute `S`. Session C uses `S + offset` for every save offset. A savestate keeps `r`; a fresh boot changes it.
- **Record**: `r`, `S`.
- **Expected**: `r` ≤ 15. Cross-check: the 16 bytes at `S + 0x10` are the OpenPSID. That is the same value as `DATA0` offset `0x10` in a plaintext save written on this PPSSPP install, so compare them and **do not write the value down**, only "matches yes/no".

**Session 0 results**

| Check | Recorded | Expected | Pass? | Notes |
| --- | --- | --- | --- | --- |
| M1 duel_eng / duel_draw / duel_mgr | | `0x09be1400` / `0x0983fb00` / `0x08e9aa00` | | |
| M1 story / field | | `0x08e9aa00` / `0x090ced00` | | |
| M2 r, S | | r ≤ 15, `S = 0x08aa5794 + 4r` | | OpenPSID matches: yes/no |

## Session A: one single duel against a CPU

**Setup.** Start any single (non-tag) duel against a CPU opponent. Use a deck that holds, if possible: one or two Normal Summonable monsters, one equip spell that raises ATK, one field spell that boosts one of those monsters' Type or Attribute, one quick-play spell or trap that boosts ATK "until the end of the turn", and one card whose text says "once per turn" (A8). Take savestates at these points (names are suggestions):

| Savestate | Moment |
| --- | --- |
| `A0-start` | Versus screen done, before the opening hands are dealt |
| `A1-myturn` | Start of your first turn (or of the CPU's first turn if it goes first) |
| `A5-main` | Your Main Phase with a monster in hand and the Normal Summon unused |
| `A6-stats` | Your Main Phase with the monster on the field and the equip, field spell and temporary boost in hand |
| `A7-chain` | Just before you activate a card the CPU is likely to respond to (a set trap on the CPU side) |

If the deck lacks a card a check needs, shortcut S1 (replace a hand or Deck card's id, "Memory edits") gets it into the hand without waiting for a lucky draw; S2 (Life Points) and S3 (turn counter) may shorten A4 and A6. Do not use S2 in A3 or S3 in A2, which test those values.

**Standing instrumentation for the whole session** (set it once and leave it on):

1. **Command log**: execute breakpoint at `0x09dc07f8` (`duel_core_push_command(op, a, b, c)`, `tutorial.md`), Break off, Log on, text `cmd op={a0} a={a1} b={a2} c={a3}`. Bit 15 of `op` is the side and the low 12 bits are the code (`duel-phases.md`, "Phase-changing commands"). This one log covers phases (codes 10–15), the turn change (4), begin turn (2), Life Points (`0x23`–`0x25`), attacks (`0x14`–`0x20`), chain links (`0x10`), summons (`0x2b`, `0x44`, `0x50`) and markers (`0x35`). Hypothesis to watch for: every engine action passes through this function. If an action shows on screen but logs no command, note it.
2. **Memory View pinned** on `0x09e2d1d8` to show turn side `0x09e2d1d8`, turn counter `0x09e2d1e0` and phase `0x09e2d1e8` in one row.

### A1. Phase values and the turn sequence

- **Hypothesis**: `0x09e2d1e8` holds 0 Draw, 1 Standby, 2 Main 1, 3 Battle, 4 Main 2, 5 End, 7 between turns. Phases are entered through commands `10 + phase`, and command 4 (next turn) sets 7 (`docs/subsystems/duel-phases.md`, "Phase enum"; high).
- **Breakpoints**: memory breakpoint on `0x09e2d1e8`, size 4, Write, Log on, Break off, text `phase write pc={pc} v={[0x09e2d1e8]}`. Optional: execute log at `0x09dbc394` (`duel_core_cmd_enter_phase(phase)`), text `enter_phase {a0}`.
- **Steps**: from `A1-myturn`, play one full turn: Draw → Standby → Main 1 → Battle (if allowed) → Main 2 → End. Then let the CPU play its turn.
- **Record**: the sequence of phase values per turn, the command codes logged between them, and the writer `pc` values.
- **Expected**: per turn, `7 → 0 → 1 → 2 → (3 → 4) → 5 → 7`. Commands appear in the order `2, 10, 11, 12, (13, …, 14), 15, 3, 4`, with bit 15 set on the CPU's turn (e.g. `0x800c`). The writer `pc` lies in `duel_core_cmd_enter_phase` (`0x09dbc394`–`0x09dbc477`), `duel_core_next_turn` (`0x09dbc184`–`0x09dbc393`) or `duel_core_reset` (`0x09dc7cb0`). Also expected: AI look-ahead writes from `0x09d1586c`, `0x09d16b38`, `0x09d16b84` or `0x09d54b78` that set 2 or 3 and then restore the value. Note them, because they confirm the "temporary override" reading. The value 6 never appears.

### A2. Turn side, turn counter, first-turn rules and the draw

- **Hypotheses**:
  1. `0x09e2d1d8` is the side to move and toggles at command 4. `0x09e2d1e0` is 0 on the first turn and increments at command 4 (`duel-phases.md`, "Turn and phase state"; high).
  2. The first player cannot battle on turn 0 (`duel_core_can_conduct_battle`; high).
  3. Open question: whether the first player draws on turn 0 (`duel-phases.md`, "Open questions").
  4. Deck list index 0 is the top of the Deck (`duel_core.md`, location table; open question in `effect-helpers-movement.md`).
- **Addresses**: hand count side 0/1 `0x09e2a534` / `0x09e2b070`; deck count `0x09e2a538` / `0x09e2b074`; deck list entry 0 `0x09e2a82c` / `0x09e2b368` (card id = `[addr] & 0x3fff`); hand list `0x09e2a64c` / `0x09e2b188` (entry `i` at `+4i`).
- **Steps**: load `A0-start`. After the opening hands, read the hand and deck counts. On turn 0, before the Draw Phase, read deck entry 0 of the turn player. After the Draw Phase, read the hand count and the last hand entry. On turn 0, open the phase menu and note whether Battle is offered. Repeat the deck-top read on turn 1.
- **Record**: `[0x09e2d1d8]` and `[0x09e2d1e0]` at each turn start; hand and deck counts before and after each Draw Phase; the deck-top card id and the drawn card id; whether Battle was offered on turn 0.
- **Expected**: the counter goes 0, 1, 2… and the side alternates. Battle is not offered on turn 0. Each draw takes the deck-top card id that was read before it (index 0 = top). Write the turn-0 draw (yes/no) down as the answer to the open question.

### A3. Life Points and commands `0x23`–`0x25`

- **Hypothesis**: LP is the `int` at `0x09e2a528` (side 0) and `0x09e2b064` (side 1). Only commands `0x23` (gain), `0x24` (loss; `b` = reason 0 effect, 1 battle, 2 cost, 3 lost) and `0x25` (set) write it, plus the duel start. Initial LP comes from the LP mode `0x09e02cac` (other → 8,000) (`docs/subsystems/battle.md`, "Life Points"; high).
- **Breakpoints**: memory breakpoint on `0x09e2a528` size 4 and on `0x09e2b064` size 4, Write, **Break on** (writes are rare), Log `LP write pc={pc} ra={ra}`.
- **Steps**: from `A0-start` let the duel start and note the writers of the initial value. During the duel, cause at least one battle damage (A4 does this), and if your deck allows, one cost payment and one effect damage or gain. At each break, step once (F10) and read the new value.
- **Record**: for each LP change, the command logged just before it (`op`, `a` amount, `b` reason), the LP before and after, and the writer `pc`.
- **Expected**: the initial value is written during the duel start (`0x09dc7dc4`–`0x09dc7fcb`). The `duel_core_reset` clear runs before it, probably through a `BOOT.BIN` memset, so a `pc` outside the module there is fine. Every later write has a `pc` inside `0x09dbffd8`–`0x09dc05e3` (gain/loss body) or the `0x25` handler `0x09dc05f4`. Each matches a preceding `0x24`/`0x23` with the same amount. Example: LP `8000 → 7500` after `cmd op=0x24 a=0x1f4 b=1`. Loss clamps at 0, and a duel won by LP sets `[0x09e2d1f0]` to 1 or 2.

### A4. Battle step sequence and the damage records

- **Hypothesis**: during the Battle Phase the step index `0x09e2d220` runs 0, 1, then 2–10 for each attack, back to 1 for the next attack, 11 to leave, 12 at the end. Battle records are at `0x09e28650 + side × 0x48` (final ATK `+0x24`, final DEF `+0x28`) and damage records at `0x09e286e0 + i × 0x14` (amount, source side, source slot, damaged player, damaged slot) (`docs/subsystems/battle.md`, "The steps", "Battle records"; high for order and roles).
- **Breakpoints**: memory breakpoint on `0x09e2d220` size 4, Write, Log `bstep pc={pc}` (read the value in Memory View or after F10). As an alternative without memory breakpoints: execute logs on the step entries `0x09dd229c, 0x09dd23fc, 0x09dd2a6c, 0x09dd3574, 0x09dd3bd4, 0x09dd4530, 0x09dd5454, 0x09dd7528, 0x09dd7ae4, 0x09dd82b4, 0x09dd889c, 0x09ddaa20` with condition `[0x09e2d224] == 0` (sub-step 0), so that each step logs once.
- **Steps**: on a turn > 0, attack an opposing Attack Position monster with a stronger monster. If possible, also make one direct attack and one attack on a Defense Position monster. Before damage is applied (break at `0x09dd7528`, step 7), read both battle records and the two damage records.
- **Record**: the step sequence per attack, `0x09e28620` (attacker side), `0x09e2863c` (attacker slot), `0x09e28640` (target slot, 5 = direct), the record fields `+0x24`/`+0x28`, and the damage records.
- **Expected**: the index runs `0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 1, …, 11` (12 at the very end). Commands `0x13` (enter Battle), `0x14`, `0x17` or `0x18`, `0x15`, `0x16`, `0x24` (b = 1), `0x1c` and `0x1d` appear in the log. Damage amount = ATK difference (e.g. 1800 vs 1500 → `0x12c`) to the weaker monster's controller. Note whether step 8 shows up for a direct attack.

### A5. Normal Summon flag and per-turn reset

- **Hypothesis**: player flags word `+0x120` (`0x09e2a648` / `0x09e2b184`): bit 17 (`0x20000`) is set when the Normal Summon (or Set) is used, bit 16 (`0x10000`) when a summon is declared, bit 21 (`0x200000`) after a face-up Normal Summon. Command 2 at turn start clears the upper 16 bits. The summon count `+0x20` (`0x09e2a548` / `0x09e2b084`) is incremented by command `0x2b` (`docs/subsystems/summon.md`, "Once-per-turn Normal Summon"; `duel_core.md`, player state; high for bits 0, 17 and the reset).
- **Breakpoints**: memory breakpoint on the human side's flags word, size 4, Write, Log `pflags pc={pc}`.
- **Steps**: load `A5-main` and read the flags word. Normal Summon one monster in Attack Position and read it again. Try to summon a second monster: the menu should not offer it. Reload `A5-main`, **Set** a monster instead and read the word. Continue to the next own turn and read the word after command 2.
- **Record**: the flags word before and after each action; `+0x20`; the logged `0x50` (`c` bit 0 = uses the Normal Summon), `0x2b` and `0x44` commands; the monster slot's flag word `+0x10` (slot `i` at `0x09e2a55c + i × 0x14 + 0x10` for side 0).
- **Expected**: bit 17 is set after both the summon and the Set. Bit 21 is set only after the face-up summon. The slot flag has `0x10000` (Normal Summoned face-up) and `0x200000` (cannot change position this turn). All of the upper 16 bits are clear after the next command 2, while bit 0 and other low bits are kept.

### A6. ATK/DEF recomputation with equip, field spell and temporary boost

- **Hypothesis**: current ATK/DEF are words 6/7 (`+0x18`/`+0x1c`) of the 13-word stat block built by `duel_core_compute_card_stats` (`0x09c05304`). There is no modifier table. Lasting effects attach 10-byte records to the slot list (pool `0x09e2c7cc`, head `u16` at slot `+0x0a`). Order: original → own effect → attached/equip/other cards by timestamp → multipliers → clamp. Kind 2 "until the End Phase" records are freed at the turn change (`docs/subsystems/stat-modifiers.md`; high for the structure, medium for the timestamp rule).
- **Instrument**: execute breakpoint at `0x09c0a604` (`duel_core_get_atk(side, slot)`) with condition `a0 == <your side> && a1 == <slot>`, **Break on**; then Step Out and read `v0`. Do the same at `0x09c0a654` for DEF. This function is called often, so enable the breakpoint only when you want a reading. Alternative: break at `0x09c052f8` (`duel_core_get_card_stats(side, slot, out)`), note `a2`, Step Out, read `[a2 + 0x18]` and `[a2 + 0x1c]`.
- **Steps**: from `A6-stats`, take a reading after each action:
  1. Monster alone.
  2. After the equip spell.
  3. After the field spell.
  4. After the temporary boost.
  5. In the opponent's turn (temporary boost gone).
  6. After the equip spell leaves the field, if your deck allows.

  After steps 2–4, walk the slot's record list: head = `[0x09e2a566 + slot × 0x14] & 0xffff` for side 0; record `i` is at `0x09e2c7cc + 10 × i` (`u16` key, byte kind | counter << 4, `u16` value, `u16` timestamp, `u16` next).
- **Record**: the readings next to the on-screen ATK/DEF; the `0x35` commands (`a = slot | kindbyte << 8`, `b` = key, `c` = value); each record (key as card id, kind, counter, value, timestamp).
- **Expected**: each reading equals the previous one plus the card text's modifier and matches the screen. The temporary boost appears as a kind-2 record (counter 0) keyed by its card id and disappears after the turn change (`duel_core_expire_turn_effects`, `0x09be6864`). The equip appears as a kind 10/11 link. Report the order of timestamps.

### A7. The chain: link layout, count, LIFO resolution and handler dispatch

- **Hypothesis**: links are 24 bytes at `0x09e28cb4 + (n − 1) × 0x18`. The count is `0x09e28e34`, building is flagged at `0x09e28f50` and resolving at `0x09e28f58`. Link `+0x00` is the card id; `+0x02` bit 0 the side, bits 1–5 the location, bits 6–11 the event code; `+0x03` bits 4–5 the table selector. Resolution is last in, first out. An opponent may respond first after an activation. Handler records are found by `duel_effects_find_record(ctx)` (`docs/subsystems/chain.md`; `duel_core.md`, "The chain"; high).
- **Breakpoints**: memory breakpoint on `0x09e28e34` size 4, Write, Log `chain_n pc={pc}`. Execute log at `0x09ce2e54` (`duel_effects_find_record`) with text `find_record card={[a0]}` (the low 16 bits are the card id). It runs very often while the game scans for activatable cards, so enable it only around the activation.
- **Steps**: from `A7-chain`, activate a card and let the CPU respond (or, against a set trap, attack into it). With two or more links on the chain, break (the `0x10` command for link 2 is a good moment) and read the links. Then let the chain resolve while you watch the count.
- **Record**: for each link the card id, side, location, event code and selector, and `+0x04` bit 1 when a link is negated; the order in which `0x10` (link activated) commands appear; the count over time.
- **Expected**: link 1 is the first card. The count rises 1, 2, … and falls back to 0, with the top link resolving first. A spell or trap activated from its zone has selector 0 and a location 5–9 (or `0x0b` if activated from the hand). A negated link keeps its place with `+0x04` bit 1 set (Magic Jammer, if available, answers the open question in `chain.md`).

### A8. Once-per-turn marker `0xfb6`

- **Hypothesis**: the activation step of a once-per-turn effect adds marker `0xfb6` of kind 2 to the card's slot (`duel_effects_mark_used_this_turn`, `0x09c43148`, or command `0x35` with `b = 0xfb6`). The activation condition `duel_effects_not_used_this_turn` (`0x09c5698c`) tests for it, and the turn change frees it (`docs/subsystems/chain.md`, "Once per turn"; medium).
- **Find a card**: look up the cards of your deck in the per-card spec (`tools/card_effects.py`, kept under `extracted/`) or in the effect classification for a record whose activation condition is `0x09c5698c`. Any face-up monster with a "once per turn" ignition effect is a good candidate.
- **Breakpoints**: execute log at `0x09c43148` (`marked side? {a0}`) and at `0x09c150bc` (`duel_core_post_add_marker(side, slot, card, kind, value)`) with condition `a2 == 0xfb6`, Log `add_marker {a0} {a1} {a2} {a3}`.
- **Steps**: activate the effect once. Walk the slot's marker list as in A6 (same pool and head). Try to activate it again in the same turn: the option should be missing. Continue to the next turn of the same player and check that the list no longer holds `0xfb6` and the effect is available again.
- **Record**: the logged marker command (`op 0x35`, `b = 0xfb6`), the record (kind, counter), menu availability before and after, and the turn-change expiry.
- **Expected**: one `0xfb6` record of kind 2 with counter 0 after the activation, absent after the next turn change. If the card uses its own id as the key (as Exarion Universe does), note it.

### A9. Trigger order for simultaneous triggers (SEGOC)

- **Hypothesis**: `duel_core_chain_build_from_triggers` (`0x09c329e8`) sorts the trigger queue (`0x09e289b4 + i × 0x18`, count `0x09e28e48`) by key `(controller ≠ turn player) + 2 × (optional)`: turn player's mandatory, opponent's mandatory, turn player's optional, opponent's optional. The order within a group is not chosen by the player (`chain.md`, "Forming a chain from triggers"; high for the key, medium for the reading).
- **Opportunistic**: a breakpoint at `0x09c329e8` with condition `[0x09e28e48] >= 2`, **Break on**, catches any moment two or more triggers are queued. Leave it enabled through the whole session.
- **Steps**: when it breaks, read the queued links (card id, `+0x02` side), Step Out, and read the chain links. If it never fires naturally, stage it with shortcut S1 (one own turn, about 5 minutes):
  1. In your Main Phase 1 (no chain, `u16 [0x09e27fee] == 0`), replace two of your hand cards with Broww, Huntsman of Dark World (`0x1966`) and one with Card Destruction (`0x12d5`), and two of the CPU's hand cards with Broww as well. Optionally replace a third own card with Beiige, Vanguard of Dark World (`0x1965`) to mix two trigger kinds. Record every edit (policy, rule 4).
  2. Enable an execute log at `0x09ce401c` (`duel_effects_get_trigger_kind`, text `kind? link={a0}`) and read `v0` on Step Out for each queued link, so that "mandatory" (0) and "optional" (1/2) come from the game rather than the card text.
  3. Activate Card Destruction. Both hands are discarded by a card effect, which queues the Dark World triggers (Broww and Beiige are compared in `duel_core_send_hand_card`, `0x09c18550`, at `0x09c18850`/`0x09c1885c`; static, medium). The breakpoint at `0x09c329e8` fires with four or five queued links.
  This staging is the small version of D2.
- **Record**: queue order (card, side, trigger kind from `0x09ce401c`) and chain order after the sort; whether the game asked the player to choose an order; the edits made.
- **Expected**: chain link 1 holds the lowest key `(controller ≠ turn player) + 2 × (kind > 0)`, in the group order above (in the staged version, with equal kinds: your two Browws first, then the CPU's). The game does not ask.

### A10. The AI does not read hidden cards

- **Hypotheses**:
  1. When the AI analyses the board, it registers an opponent's hand card only when `duel_core_is_hand_card_revealed(side, index)` (`0x09c038a8`) returns 1 (`docs/subsystems/ai.md`, "Board view (what the AI knows)"; medium; `effect-helpers-misc.md`).
  2. `ai_mask_hidden_card_id(side, slot, card)` (`0x09ce43ec`) replaces a face-down card of the other side with a placeholder (`0x16a7` spell/trap zone, `0x10f4` field zone, a level-based stand-in for monsters) (`ai-helpers.md`; high).
- **Breakpoints**: execute breakpoint at `0x09c038a8` with condition `a0 == <human side>`, Break on. Execute breakpoint at `0x09ce43ec` with condition `a0 == <human side>`, Break on, enabled only while you have a face-down card.
- **Steps**: during the CPU's Main Phase, at the first hit of each breakpoint, note the arguments, Step Out and read `v0`. Do this for several indices. For the mask, set one monster and one spell/trap face-down before ending your turn.
- **Record**: `(a0, a1)` and `v0` for `0x09c038a8`; `(a0, a1, a2)` and `v0` for `0x09ce43ec` next to the real card id.
- **Expected**: `v0 = 0` for every hand index in normal play (1 only after a reveal effect or with a card that makes hands public). `0x09ce43ec` returns `0x16a7` for the face-down spell/trap and a stand-in id different from the real one for the face-down monster.

The 16-link limit (formerly the optional A11) is now Session D.

**Session A results**

| Check | Recorded | Expected | Pass? | Notes |
| --- | --- | --- | --- | --- |
| A1 phase sequence, turn 1 | | `7,0,1,2,(3,4),5,7` | | writer pcs |
| A1 phase sequence, CPU turn | | same, cmds with `0x8000` | | |
| A2 turn side / counter | | toggles / 0,1,2 | | |
| A2 Battle on turn 0 offered? | | no | | |
| A2 draw on turn 0? | | (open question) | | |
| A2 drawn card = deck entry 0 | | yes | | |
| A3 initial LP, LP mode | | 8000 (mode other than 1–3) | | |
| A3 each LP change: cmd, amount, reason, pc | | `0x24`/`0x23`/`0x25` only | | |
| A4 battle step sequence | | `0,1,2…10,1,…,11` | | |
| A4 damage record | | ATK difference | | |
| A5 flags after summon / set / next turn | | bit 17 set / set / clear | | |
| A6 ATK readings 1–6 vs screen | | equal | | timestamps |
| A6 temporary record kind, expiry | | kind 2, gone next turn | | |
| A7 link layout, LIFO | | as documented | | |
| A8 `0xfb6` added, blocks, expires | | yes / yes / yes | | card used |
| A9 trigger order | | TP mand., opp. mand., TP opt., opp. opt. | | staged? edits listed |
| A10 revealed? for human hand | | 0 | | |
| A10 mask for face-down | | placeholder ids | | |

## Session B: one tag duel

**Setup.** Reach any tag duel (story mode with a partner). Savestate `B0-start` before the first turn and `B1-turnend` in the End Phase of the first turn. Keep the command log from Session A.

### B1. Partner swap at the turn change

- **Hypothesis**: in tag mode (`[0x09e2d1fc] == 1`), `duel_core_next_turn` calls `tag_duel_swap_active_duelist(next side)` (`0x09bf21e4`). It saves the side's hand, deck and third list (presumably the extra deck) and loads the partner's from the waiting area (`0x09e02cb8 + side × 300`; counts `u16` at `+0x10`, `+0x12`, `+0x14`). Field, Graveyard and LP stay with the side. The waiting partner's duelist kind (`0x09e029a0[side]`) is swapped with `0x09e02998[side]` (`docs/subsystems/tag_duel.md`; `ai.md`; high for the mechanism).
- **Breakpoints**: execute breakpoint at `0x09bf21e4`, Break on, Log `tag_swap side={a0}`.
- **Steps**: load `B1-turnend` and end the turn. At the break, read for the side in `a0`: hand, deck and extra counts (`+0x0c`, `+0x10`, `+0x18` of its player block), the first two hand entries, the three waiting-area counts, and both duelist-kind words. Step Out and read them again. Repeat for the next turn change.
- **Record**: the before/after values; whether LP (`0x09e2a528`/`0x09e2b064`) and the Graveyard count (`+0x14`) are unchanged.
- **Expected**: the side's three counts become the waiting area's previous counts and vice versa. LP and Graveyard are untouched. The third list is the extra deck (compare its count with the partner's Extra Deck on screen). The duelist kind of the active side changes when a human and a CPU partner alternate. Read the end of the function in Ghidra afterwards only if the saved lists do not appear in the waiting area (open question in `tag_duel.md`).

### B2. Tag state at duel start

- **Hypothesis**: `tag_duel_start_with_partner_decks` (`0x09dc7ff4`) resets the duel, sets `0x09e2d1fc = 1` and loads deck structures 2 and 3 (`0x09e029ac + n × 0xc0`). `0x09e2d1f4` (duel mode 2 or 3) distinguishes the start functions (`tag_duel.md`; `duel_core.md`, "Duel globals"; medium).
- **Steps**: load `B0-start` (or start a new tag duel) with execute breakpoints at `0x09dc7ff4`, `0x09dc8088`, `0x09dc8148` and `0x09dc7fcc`, Log only. Note which ones run, then read `0x09e2d1fc` and `0x09e2d1f4`. Do the same once in a single duel (Session A) for comparison.
- **Expected**: the tag duel runs `0x09dc7ff4` and the flag is 1. The single duel runs another entry point and the flag is 0. Record `0x09e2d1f4` in both.

**Session B results**

| Check | Recorded | Expected | Pass? | Notes |
| --- | --- | --- | --- | --- |
| B1 counts before/after swap (turn 1→2) | | swapped with waiting area | | |
| B1 counts before/after swap (turn 2→3) | | swapped back | | |
| B1 LP / Graveyard unchanged | | yes | | |
| B1 third list = extra deck | | yes | | |
| B1 duelist kind words | | swapped | | |
| B2 start function, `0x09e2d1fc`, `0x09e2d1f4` | | `0x09dc7ff4`, 1, ? | | single duel: |

## Session C: free roam

**Setup.** Load a game in free roam with a partner chosen and at least 400 DP. Confirm M1 (`rel_story` at `0x08e9aa00`) and compute `S` (M2). All addresses below are `S + save offset`, and the `rel_story:` functions are runtime addresses in `rel_story`. Savestate `C0-field` on the field map in time slot 1 or 2.

### C1. Calendar block

- **Hypothesis**: the calendar is 9 words at save `+0x1a24c` (story block `+0x3438`): `+0x00` slot counter `t` (from 1), `+0x04` slot within the day `(t − 1) % 7 + 1`, `+0x0c` day number `day + 1`, `+0x10` day index `(t − 1) / 7`, `+0x14` light period (slots 1–2 → 0, 3–4 → 1, 5 → 2, 6 → 3, 7 → 4), `+0x1c` weekday `(day % 7 + 1) % 7` (`docs/subsystems/world.md`, "Calendar and time of day"; high for the code).
- **Breakpoints**: memory breakpoint on `S + 0x1a24c`, size `0x24`, Write, Log `cal pc={pc}`. Execute log at `rel_story:0x08eac278` (`world_update_calendar`).
- **Steps**: from `C0-field`, read the 9 words. Leave a map through an exit cell (advances one slot) and read again. Then use the PDA's "Advance Time" to a later slot, and finally "End the day".
- **Record**: the 9 words after each step, plus the island-map lighting (morning, day, …).
- **Expected**: the words follow the formulas. The lighting matches `+0x14`. Report `+0x08` and `+0x20` (open: month/date).

### C2. Daily NPC pairing

- **Hypothesis**: on a new day `world_assign_daily_spots` (`rel_story:0x08eab8a4`) writes the pairing order to the field save block `+0x1c` (save `+0x1a28c`, 140 bytes). Consecutive entries form pairs that get neighbouring spots `(s − 1, s)` with `s` odd in their runtime records (save `+0x16e14 + r × 0x5c`: `u16 +0x18` spot index, `+0x1c` character id, `+0x54` flags with bit 2 = value `0x2` "placed by the pairing"). It runs once per day, not at every time slot (`world.md`, "Daily schedule and NPC placement"; high for the code, medium for the pair reading).
- **Breakpoints**: execute log at `rel_story:0x08eab8a4` (`assign_daily_spots`) and at `rel_story:0x08e9d72c` (`update_npc_positions`).
- **Steps**: from `C0-field`, advance one slot (only the second should log), then "End the day" (both should log). Read the first 6 bytes of the pairing order. For those characters, find their runtime records (the records are sorted by character id at `+0x1c`) and read the spot indices and flags. In the game, find two of the paired characters on the map.
- **Record**: three pairs as `(char, spot)`, the flag words, and whether each pair stands together on screen.
- **Expected**: spots `(s − 1, s)` with `s` odd for each pair, flag `0x2` set, and the pair standing next to each other. The pairing changes from day to day (repeat once more if time allows).

### C3. Gift points

- **Hypothesis**: giving a sandwich to the partner changes the partner's points through `world_change_char_points(char, delta)` (`rel_story:0x08e9d9c0`) with taste 1 → +40, 2 → +20, 3 → +10, 4 → −5, 5 → −10, golden egg → +200, clamped to the stage cap. Points are the `u16` at save `+0x0fe0c + c × 0x18 + 0x16`. The partner word `u16` at save `+0x16e12` holds the character in bits 4–11 and the variant in bits 12–15 (`world.md`, "Items and gifts", "Friendship points and the partner"; high for the code and records).
- **Breakpoints**: execute log at `rel_story:0x08e9d9c0`, text `points char={a0} delta={a1}`. Execute log at `rel_story:0x08e9c6f8` (`world_give_item_to_partner`).
- **Steps**: read the partner word and the partner's points. Buy a sandwich from the seller (200 DP), choose "Yes" to give it, then read the points again. Repeat with a second sandwich if DP allows.
- **Record**: partner `c`, points before/after, logged `delta`, the item id (field state current item, save `+0x1a118`), and the reaction shown.
- **Expected**: `delta` is one of `+40, +20, +10, −5, −10, +200`. Points after = points before + delta, clamped to the cap of the current story stage (stage 1 → 1000, stage 2 → 2000, …). `c` from the partner word matches the partner on screen.

### C4. Item counters at save `+0x1a174` and DP

- **Hypothesis**:
  1. Low: the 50 `u32` counters at save `+0x1a174 + 4k` (field state `+0x94`) are the item menu's counts. Nothing in `rel_story` increments them (`world.md`, "Items and gifts", Inventory; open question).
  2. DP is the `u32` at save `+0x0fdfc` (`save_add_dp`, `0x08854ba0`; `world.md`, "Money and level"; medium). `save.md` still lists this offset as "meaning unknown".
- **Breakpoints**: memory breakpoint on `S + 0x1a174`, size `0xc8`, Write, Break on. Memory breakpoint on `S + 0x0fdfc`, size 4, Write, Log `dp pc={pc}`. Execute log at `0x08854ba0` (`save_add_dp`), text `dp_add {a0}`.
- **Steps**: buy a sandwich and choose "No" (eat it). Then open the item menu.
- **Record**: whether anything writes the counter range, and the `pc` if so; DP before/after and the logged argument; what the item menu shows.
- **Expected**: DP drops by 200 (`dp_add` with `-200` = `0xffffff38`, or an equivalent subtraction). For the counters, either result is useful: if they never change while the item menu shows a count, the hypothesis is refuted and the menu's counts live elsewhere (`rel_field` was not read).

### C5. Save buffer round trip (optional)

- **Hypothesis**: `DATA0` is a 1:1 copy of the state at `S` (`save.md`; high for the collection and deck offsets).
- **Steps**: save in game (plaintext save, `EncryptSave = False`, see `save.md`). Then compare: `python -I tools/save.py <DATA0> --check`, and spot-compare DP (`+0x0fdfc`), partner (`+0x16e12`) and calendar `+0x00` (`+0x1a24c`) between the file and memory at `S`.
- **Expected**: identical values.

**Session C results**

| Check | Recorded | Expected | Pass? | Notes |
| --- | --- | --- | --- | --- |
| C1 calendar after +1 slot / advance / new day | t 2→3→8→50, all words per formula | formulas in C1 | pass | `+0x08` = 5, `+0x20` = 1, never written; weekday 0 = Sunday, 1 = Monday |
| C2 assign_daily_spots runs only on a new day | only on the change to weekday 1 (Monday) | yes | pass (corrected) | weekly, gated by `0x08eab3b0` |
| C2 three pairs (char, spot) | (3, 334), (120, 335), location 21 | `(s−1, s)`, `s` odd, flag `0x2` | pass | flags `0xa0`, no flag 2; pairs stand together |
| C3 partner word, points before/after, delta | `0x0023`, 200 → 220, +20 (and +10) | delta ∈ {40,20,10,−5,−10,200} | pass | "Delish! Thanks!" |
| C4 writes to `+0x1a174`? | none | (open) | — | an eaten sandwich gives a card |
| C4 DP before/after | 1768 → 1568 → 1368 | −200 | pass | |
| C5 DATA0 vs memory | not run | identical | | |

Details: `docs/verification/results/2026-10-27-sessionC.md`.

## Session D: the chain limits (staged with memory edits)

**Hypotheses** (`chain.md`, "Summary", building state `0x0b`, "Forming a chain from triggers"; high, static):

1. Responses are offered only while the chain has fewer than 16 links: with 16 links on the chain no response window opens for either player, and the chain starts resolving.
2. `duel_core_chain_build_from_triggers` moves at most 16 queued triggers onto a chain (lowest key first) and leaves the rest in the queue (`0x09e289b4`, up to 32 entries), which form the next chain afterwards.

Address arithmetic adds weight to (1): the chain array starts at `0x09e28cb4` and the link count follows at `0x09e28e34 = 0x09e28cb4 + 16 × 0x18`, so the array has room for exactly 16 links (the trigger queue, `0x09e289b4 + 32 × 0x18 = 0x09e28cb4`, is the one with 32 entries). A 17th link would overwrite the count and the building globals.

**Why staging is needed.** A spell or trap occupies a Spell/Trap Zone while it is on the chain, so one side contributes at most five such links. The remaining links must come from hand quick effects. D.D. Crow (`0x1b44`) is one: its record is in the M2 table (hand effects, `tools/card_effects.py`), it is in the spell-speed-2 monster list of `BOOT 0x08865e64` (immediate `0x1b44` at `0x08866010`, before the function's first `jr ra` at `0x0886619c`; pure-Python scan, medium), and it needs no zone. It needs one card in the opponent's Graveyard as a target. Jar of Greed (`0x145a`, normal trap, no activation condition) supplies the zone links. Pot of Greed (`0x12ec`) draws the Crows. Ids checked with `tools/cardinfo.py` on `cardinfo_eng.ehp`; all three are cards of this game.

**Setup.** Any single duel against a CPU (an early opponent with few removal cards is best). Session 0 first. Use the standing instrumentation of Session A (command log at `0x09dc07f8`) and add:

| Instrument | Address | Settings |
| --- | --- | --- |
| Chain count | `0x09e28e34`, size 4 | Memory breakpoint, Write, Log `chain_n pc={pc}` (read the value with F10 or in Memory View) |
| Building state, resolving flag | `0x09e28f54`, `0x09e28f58`, size 4 each | Memory breakpoints, Write, Log `build_state pc={pc}` / `resolving pc={pc}` |
| Response windows | `0x09ccbe74` (`duel_core_offer_response_window(link, side)`) | Execute, Log `window link={a0} side={a1}` |
| Player input | `0x09dce84c` (`duel_core_begin_player_input(side, mode)`) | Execute, Log `input side={a0} mode={a1}` (mode 5 = chain response, 4 = timing window) |
| Trigger formation (D2) | `0x09c329e8` (`duel_core_chain_build_from_triggers`) | Execute, **Break on**, condition `[0x09e28e48] >= 2` |
| Guard for a 17th link | `0x09e28e34`–`0x09e28e4b` | Memory View pinned; nothing but the count and the building globals may change there |

All edits use shortcut S1 and follow the policy above; write each one into the results file.

### D1. Sixteen links from responses

1. **Set the zone links.** In an own Main Phase 1, replace five hand cards with Jar of Greed (`0x145a`) (S1; if the hand has fewer than five cards, replace Deck entries 0–4 before the Draw Phase and draw over two turns instead). Set all five face-down. Savestate `D1-set`. Traps cannot be activated in the turn they are set, so end the turn.
2. **Wait for a Crow target.** Continue until the CPU's Graveyard holds at least one card (`[P + 0x14] ≥ 1` for the CPU side: a destroyed monster, a used spell or a hand-limit discard). The official rules allow several chain links to target the same card; if the game refuses that (the target choice offers nothing for the second Crow), each Crow needs its own card in the CPU's Graveyard; note it and wait for more.
3. **Fill the hand.** In a later own Main Phase 1, with the Jars still set, check that the own deck count `[P + 0x10]` is at least 14. Replace six hand cards with Pot of Greed (`0x12ec`) and Deck entries 0–11 with D.D. Crow (`0x1b44`) (S1). Play the six Pots: they draw the twelve Crows. Savestate `D1-chain`.
4. **Build the chain.** Activate one set Jar of Greed (link 1). Every time the game offers you a response (`input … mode=5`), activate the next card: the other four Jars (links 2–5), then Crows (each discards itself and targets a card in the CPU's Graveyard). The CPU gets a window after each of your links; any CPU response is a link too, so simply keep going until no window is offered. You have 4 + 12 = 16 cards for links 2–17.
5. Let the chain resolve without further input.

- **Record**: the chain count after each `0x10` command; the window and input logs between links; the building-state sequence; the link number at which the windows stop; how many Crows remain in hand; whether the 24-byte guard region changed in any way other than the count; the resolution order (cards of the `0x11`/`0x12` commands); every edit.
- **Expected**: the count rises 1, 2, …, 16 with one `0x10` command per link (the chain number in the command reaches 16). Up to 15 links a window is offered after each activation. After link 16 there is no `window` log and no `input … mode=5` for either side, although Crows are still in hand; the resolving flag `0x09e28f58` becomes 1 and the count falls 16 → 0 with sixteen `0x11`/`0x12` pairs, top link first. Link 17 is never created: the count never exceeds 16 and the guard region is never overwritten by link data. If a window does open with 16 links, activate one Crow, record what happens to `0x09e28e34`–`0x09e28e4b`, and reload `D1-chain`: that refutes hypothesis 1.

### D2. Sixteen links from simultaneous triggers

Card Destruction (`0x12d5`) makes both players discard their hands by a card effect. Broww, Huntsman of Dark World (`0x1966`) has a trigger when it is discarded by a card effect (M2 table; its id is compared in `duel_core_send_hand_card`, `0x09c18550`, at `0x09c18850`; static, medium). Seventeen or more Browws discarded at once give seventeen or more simultaneous triggers.

1. In an own Main Phase 1 (savestate `D2-pre`), read the own hand count `H` (at least 7), the CPU's hand count `c` (at least 5) and the own deck count (at least 30 is comfortable; see the note below).
2. With S1: replace six own hand cards with Pot of Greed and one with Card Destruction; replace the other `H − 7` own hand cards and own Deck entries 0–11 with Broww; replace all `c` CPU hand cards with Broww.
3. Play the six Pots (they draw the twelve Browws). Your hand is now Card Destruction plus `H + 5` Browws; with the CPU's `c` the total `N = H + 5 + c` is at least 17.
4. Activate Card Destruction. When the breakpoint at `0x09c329e8` breaks, read `[0x09e28e48]` and the queued links (card id, side bit 0 of `+0x02`). Step Out and read `[0x09e28e34]`, `[0x09e28e48]` and the 16 chain links. Optionally log `0x09ce401c` (trigger kind) as in A9.
5. Continue. If Broww's trigger is optional, each link asks "activate?" (answer Yes for your links). After the chain has resolved, the breakpoint fires again for the triggers left in the queue.

- **Record**: `N` before the sort; chain count and queue count after it; the side of each chain link 1–16; the queue count and the sides at the second break; every edit.
- **Expected**: `[0x09e28e48] = N` (at most 32) before; after the Step Out the chain holds 16 links and the queue `N − 16`. Order: your Browws (turn player) first, then the CPU's, so the triggers left in the queue are the CPU's (assuming equal trigger kinds; otherwise by the key of A9). After the first chain, a new chain forms from the `N − 16` remaining triggers.
- **Note**: the draws (twelve for the Pots, `H + 5` for Card Destruction, one per resolved own Broww) can empty your Deck. The observation is taken before any Broww resolves; a deck-out loss afterwards does not affect it. Broww's activation condition may require a non-empty Deck when it is queued, so keep at least one card in the Deck after Card Destruction's redraw (own deck count at step 1 ≥ `12 + H + 6`).

**Session D results**

| Check | Recorded | Expected | Pass? | Notes |
| --- | --- | --- | --- | --- |
| D1 highest chain count / link number of the last window | 16 / 15 | 16 / 15 | pass | 1 Crow left in hand |
| D1 window or input with 16 links? | none | no | pass | guard region: only `0x09e28e40` 1 → 16 |
| D1 resolution order | 16 → 1 | 16 → 1 | pass | |
| D1 several Crows on the same target allowed? | yes | (open) | — | 12 Crows, one target |
| D2 queued `N`, chain / queue after the sort | | `N` / 16 / `N − 16` | | trigger kinds |
| D2 sides of links 1–16 | | turn player's first | | |
| D2 second chain from the remainder | | `N − 16` links | | |
| Edits (S1/S2/S3) | 25 S1 edits | all listed | pass | |

Details: `docs/verification/results/2026-10-27-sessionD.md`. D2 not run.

## Session E: outside the duel (title, save, free roam, shop, deck editor, tutorial, minigames)

Session E collects the checks that static work on save data, the world, the story bytecode, the shop, the UI string tables, movies, sound and the tutorial left for PPSSPP. It is split into seven **scene blocks**. Each block is self-contained: do one block per sitting, in any order, and start each sitting with Session 0's quick check for the modules that block uses (table E0). Inside each block the cheapest, highest-value checks come first; checks marked *(optional)* can be skipped without blocking anything.

| Block | Scene | Checks | Time (estimate) |
| --- | --- | --- | --- |
| E-T | Boot and title screen | E1–E6 (E6 optional) | 30 min |
| E-S | Save and load | E7, E8 | 10 min |
| E-W | Free roam | E9–E15 (E14, E15 optional) | 45 min, plus a chapter duel if E13 is taken to the end |
| E-P | Card shop | E16, E17 (E17 optional) | 15 min |
| E-K | Deck editor | E18, E19 | 15 min |
| E-L | Tutorial lesson | E20–E22 | 20 min |
| E-M | Minigames | E23, E24 | 5 min per minigame, about 40 min for all seven |

**Save-file setup** (blocks E-S, E-P, E-K, E-M and some E-W checks). Several checks are the "differential saves" of `docs/formats/save.md` ("PPSSPP experiments"): save in game, do one action, save again, compare. `EncryptSave = False` must be set in `ppsspp.ini` so that `DATA0` is written in plaintext (`save.md`, "On the memory stick"). After each save copy `PSP/SAVEDATA/ULES011830001/DATA0` to `external/ppsspp/saves/<check>-<a|b>.bin` (git-ignored) and compare with

```
python -I tools/save.py json external/ppsspp/saves/<check>-a.bin > external/ppsspp/saves/<check>-a.json
python -I tools/save.py json external/ppsspp/saves/<check>-b.bin > external/ppsspp/saves/<check>-b.json
```

and a JSON or byte diff (`fc /b` on Windows). The results file records offsets and small values only (the list of changed offsets, old → new), never the files.

**Save-state address.** Checks that read the game state in memory use `S = 0x08aa5794 + 4 × [0x08ac18c0]` (Session 0, M2, verified). `S` changes on every fresh boot and is kept by a savestate, so compute it once per boot and write it at the top of the results file. In the log texts below, `S+0x…` stands for the computed number: type the sum, not the letter (for example with `S = 0x08aa57c0`, `{[S+0x0c]}` becomes `{[0x08aa57cc]}`).

**Standing instrumentation for every block of Session E** (set once per sitting, Log on, Break off; all `BOOT.BIN` addresses, which never shift):

| Address | Function (`docs/formats/save.md`, "In the game") | Log text |
| --- | --- | --- |
| `0x0883e874` | `save_start_autoload_dialog` (mode 0) | `save_dialog autoload ra={ra}` |
| `0x0883e9e0` | `save_start_autosave_dialog` (mode 1) | `save_dialog autosave ra={ra}` |
| `0x0883e918` | `save_start_save_dialog` (mode 3) | `save_dialog save ra={ra}` |
| `0x0883eaa4` | save dialog mode 7 (unnamed) | `save_dialog mode7 ra={ra}` |
| `0x0883e694` | save dialog mode 8 (unnamed) | `save_dialog mode8 ra={ra}` |
| `0x0883e78c` | save dialog mode `0x16` (unnamed) | `save_dialog mode16 ra={ra}` |
| `0x08854ba0` | `save_add_dp(delta)` | `dp_add {a0} ra={ra}` |

Any hit of modes 7, 8 or `0x16`, with the screen it happened on, answers the open question in `save.md` ("The meaning of the other save modes").

### E0. Module bases for Session E

Modules are placed by the kernel allocator; the bases below come from PPSSPP symbol exports (`docs/subsystems/modules.md`, "Runtime bases"), but only `rel_duel_*`, `rel_story` and `rel_field` were re-confirmed in Session 0. **Quick check** (1 minute per scene): in the Disassembly window go to the address in the last column. PPSSPP labels every function it has detected (`z_un_<address>` or a symbol name): the label must sit exactly at that address. **Full check** (once per scene, if the quick check fails or for a module without a known base): fresh boot, go to the scene, **Debug → Save Map File…** to `ghidra/<scene>-<date>.sym`, then `python -I tools/modules.py base ghidra/<scene>-<date>.sym <USRDIR>/gmodule` (as M1). If a base differs, every module-relative address of that module below shifts by `new base − documented base`; report it before continuing.

| Module | Scene (block) | Documented base | Quick-check address |
| --- | --- | --- | --- |
| `rel_title` | title (E-T) | `0x08e9aa00` (export only, not in Session 0) | `0x08e9cbf0` `ui_title_get_message`; within its 252 bytes there is a `jal 0x08e9d0e0` |
| `rel_story`, `rel_field` | free roam (E-W) | `0x08e9aa00`, `0x090ced00` (verified, M1) | as M1 (`0x08eaacc8`) |
| `rel_shop` | shop (E-P) | `0x090ced00` (export only) | `0x090d9678` `shop_draw_pack_cards` |
| `rel_deck` | deck editor (E-K) | `0x08e9aa00` (export only) | not needed: E-K uses no module address |
| `rel_tutorial` | lesson (E-L) | **unknown** | found in E20 |
| minigame modules | minigames (E-M) | **unknown** | found in E23 |

### Block E-T: boot and title screen

#### E1. The in-memory file index is ready after boot

- **Hypothesis**: `container_build_file_index` (`0x0881e054`) builds a sorted array of 16-byte entries `{path pointer, LBA, size, unused}` from the disc's ISO 9660 directories at boot, between `[0x089218c8]` (start) and `[0x089218cc]` (end), and sets the ready flag `0x089218dc` to 1 (`docs/formats/file-index.md`; high, code; open question "confirm at runtime").
- **Breakpoints**: none needed. *Optional*, only if your PPSSPP build can start a game paused (a developer setting in recent builds; otherwise skip it): fresh boot, paused before the first instruction, memory breakpoint on `0x089218dc`, size 4, Write, Log `index_ready pc={pc}`.
- **Steps**: on the title screen open Memory View at `0x089218c8` and read the seven words `0x089218c8`–`0x089218e0`. Go to the address in `[0x089218c8]`, read the first entry's path pointer, LBA and size, and look at the path string it points to.
- **Record**: `[0x089218dc]`, `[0x089218e0]`, the entry count `([0x089218cc] − [0x089218c8]) / 16`, the first entry's path (a file name), LBA and size; the writer `pc` if the optional breakpoint ran.
- **Expected**: ready = 1, building = 0, the count equals the number of files on the disc (the agent counts them from the ISO with the extractor), and the first entry is the alphabetically first path (the array is sorted case-insensitively, presumably); its LBA and size equal the ISO's. The writer `pc` lies in `0x0881e054`–`0x0881e447`.

#### E2. Who plays the opening movie, and can it be skipped?

- **Hypothesis**: `rel_title` plays `movie/TF3_opening_a.pmf` through the `BOOT.BIN` player (`system_movie_create_player` `0x0882b964`); whether a button skips it, and whether it replays after an idle time on the title screen, is open (`docs/subsystems/movies.md`, "Open questions"; `psmf-movies.md`; low for the skip, no claim made).
- **Breakpoints** (`BOOT.BIN`, Log only): `0x0882b964` `movie_create ra={ra} a0={a0}`; `0x0882d6fc` (`system_movie_stop_video`) `movie_stop ra={ra}`; `0x0882b834` (`system_load_movie_modules`) `movie_modules_load ra={ra}`; `0x0882b874` (`system_unload_movie_modules`) `movie_modules_unload ra={ra}`.
- **Steps**: fresh boot; set the breakpoints on the title-scene load at the latest (the opening starts after the boot logos; if the first run is missed, take a savestate during the logos, `E2-boot`, and reload it). Let the opening start; after about 5 s press Start. If it keeps playing, press Cross, then Circle. Reload the boot savestate and let the opening run to the end without input. Then wait 3 minutes on the title screen without input.
- **Record**: for each run the logged functions with `ra`; which button stopped the movie (none / Start / Cross / Circle); whether the title screen came early; whether the opening (or another movie) started again after the idle wait.
- **Expected**: `movie_create` with `ra` inside `rel_title` (`0x08e9aa00`–`0x08ef8443`, 383,556 bytes). Skip: no expectation, the result is the answer. The `ra` of `movie_stop` after a button press names the `rel_title` code that handles the skip (the agent reads it afterwards).

#### E3. Which message table each title screen reads

- **Hypothesis**: `ui_title_get_message(index, k)` (`rel_title` `0x08e9cbf0`) reads message `index` from table `k` (0 `title_msg`, 6 `option_msg`, 12 `tushin_msg`, 18 `duelmenu_msg`, plus the language) of `title_menu_<l>.ehp`; 25 call sites choose `k` at runtime (`docs/subsystems/ui.md`, "Open questions"; high for the function, the per-screen `k` is unknown).
- **Base**: `rel_title` at `0x08e9aa00` (E0 quick check).
- **Breakpoints**: execute at `0x08e9cbf0`, Log only, `title_msg idx={a0} k={a1} ra={ra}`.
- **Steps**: from the title screen, open every screen reachable without starting a game: main menu, each options page, the communication (ad hoc / infrastructure) menus, the duel menu if it is offered from the title. Stay about 3 s on each screen and note the screen name in the log console's order (or write it down with the time).
- **Record**: per screen the distinct `(ra, idx, k)` triples.
- **Expected**: `k` ∈ {0, 6, 12, 18} (the language is added inside the function, so `k` itself never carries it). Every `ra` lies in `rel_title`. The agent maps the 25 runtime call sites (`ra − 8`) to their tables.

#### E4. The sound play call (menu sounds)

- **Hypothesis** (low): one `BOOT.BIN` function takes a global sound id (bank first id + cue, `audio_get_bank_first_sound_id` `0x08868874`) and starts it on a sceSas voice (PS-ADPCM) or a sceAtrac handle. The old candidates were `0x08826458`/`0x088265ac`, called from `0x08841514`–`0x0884155c` (`docs/formats/sound.md`, "Open questions"); `0x088265ac` has since been identified as `system_heap_free`, so only `0x08826458` (340 bytes, unnamed) stays a candidate, and a weak one. **Address status**: the candidate is unconfirmed; the check is designed to find the real function from the system calls instead.
- **Breakpoints** (Log only; import stubs can take execute breakpoints, they run as `jr ra` + `syscall`):
  - `0x08826458` `snd_candidate a0={a0} a1={a1} a2={a2} ra={ra}`
  - `0x0887288c` (`__sceSasSetVoice`) `sas_set_voice core={a0} voice={a1} buf={a2} size={a3} ra={ra}`
  - `0x0887287c` (`__sceSasSetKeyOn`) `sas_key_on core={a0} voice={a1} ra={ra}`
  - `0x088727d4` (`sceAtracSetDataAndGetID`) `atrac_set_data buf={a0} size={a1} ra={ra}`
  - `0x088727dc` (`sceAtracSetLoopNum`) `atrac_loop id={a0} n={a1} ra={ra}`
  - `0x08868874` (`audio_get_bank_first_sound_id`) `bank_first {a0} ra={ra}`
  - Fallback if stub breakpoints do not fire: **Log Console** with the `SASMIX` and `ME`/`ATRAC` channels at Debug level, which print the same calls.
- **Steps**: on the title menu move the cursor five times (one sound each), confirm once, cancel once. Then wait 10 s without input (music only).
- **Record**: per button press the logged lines in order; which `ra` values repeat once per press; the `atrac_loop` calls for the music.
- **Expected**: each press gives one `sas_key_on` (or one `atrac_set_data`) whose `ra` lies in one `BOOT.BIN` function; walking up its callers (the agent does this statically from the `ra` chain) names the play call. The music track gives `atrac_loop … n=-1` (loop forever). Follow-ups once the play call is known (not part of this check): the cue flags `0x02`, `0x04`, `0x10`, `0x11` and envelope bytes `0x08`–`0x0b` (`sound.md`) can then be traced on a cue that has them, and the 11 looping effect waves in banks 714–723 can be watched for `sceAtracSetLoopNum`.

#### E5. Title and option words `0x1bf0c` (differential save 16)

- **Hypothesis**: the three words at save `+0x1bf0c` hold title-screen / extras settings (`save.md`, map and experiment 16; medium).
- **Breakpoints**: memory breakpoint on `S + 0x1bf0c`, size 12, Write, Log `title_words pc={pc}`.
- **Steps**: load the game, save (`E5-a`); return to the title, change each option on the options screen once (one at a time, noting the order), then load and save again (`E5-b`).
- **Record**: the logged writes (pc and which option was changed just before), and the diff of `E5-a`/`E5-b` restricted to `0x1bf0c`–`0x1bf17` and to the settings bits `0x0fe04`–`0x0fe0b`.
- **Expected**: each option change writes one field of the three words or of the settings bits (`save_get_settings`); the diff shows only those bytes and the frame counter `+0x0c`.

#### E6. *(optional)* Audio lead of the opening movie

- **Hypothesis**: every movie's first audio PTS is 85,069 and first video PTS 90,000, so the audio leads by 2,416 samples (one 2,048-sample ATRAC3plus frame + 368 samples of decoder delay), and dropping them aligns audio with the first frame (`docs/formats/psmf-movies.md`, "Timing"; medium).
- **Caveat**: PPSSPP's `sceMpeg` is an emulation (FFmpeg-based); what it does is evidence about PPSSPP, not about the PSP decoder. Record it as "PPSSPP behaviour"; this check alone cannot reach `verified`.
- **Breakpoints** (Log only): `0x0887299c` (`sceMpegAtracDecode(mpeg, au, buffer, init)`) `atrac_dec pts={[a1+4]} ra={ra}`; `0x08872934` (`sceMpegAvcDecode(mpeg, au, …)`) `avc_dec pts={[a1+4]} ra={ra}` (`SceMpegAu`: `+0` PTS high, `+4` PTS low). Disable both after the first ten lines of each.
- **Steps**: fresh boot, let the opening start.
- **Record**: the first five PTS values of each stream, in log order.
- **Expected**: first audio PTS `0x14c4d` (85,069), first video PTS `0x15f90` (90,000), and the first audio decode happens before the first video decode. Whether the first decoded audio frame is played or dropped cannot be seen from these calls; note PPSSPP's console messages about the audio stream if any.

### Block E-S: save and load

#### E7. Frame counter and main-loop rate (differential saves 1 and 2)

- **Hypotheses**: `u32` save `+0x0c` counts main-loop iterations (`save_tick_frame_counter` `0x088359f4`, saturating), so its rate is the game's frame rate; the two `u32` at `+0x04` are unknown and expected never to change (`save.md`, experiments 1 and 2; medium / unknown).
- **Breakpoints**: none.
- **Steps**: in free roam, read `[S + 0x0c]`, wait exactly 60 s by a stopwatch with PPSSPP at 100 % speed (no fast-forward; the speed is shown with **Settings → Graphics → Show FPS counter**), read it again. Then save (`E7-a`), wait 60 s, save again (`E7-b`). Return to the title, load, save (`E7-c`).
- **Record**: the two in-memory readings and their difference; the FPS counter shown (game frames per second); the diffs `E7-a`/`E7-b` and `E7-b`/`E7-c`.
- **Expected**: the counter grows by about 3,600 (60 per second) or 1,800 (30 per second); the FPS counter agrees. Between `E7-a` and `E7-b` only `+0x0c` (and possibly the calendar) changes; `+0x04`–`+0x0b` never change. Any other changed byte is new information for the map. The main-loop rate is also the time base of E10 and F10.

#### E8. Save buffer round trip and the unknown regions (C5 and differential save 15)

- **Hypothesis**: `DATA0` is a 1:1 copy of the `0x1c0ec` state bytes at `S` (`save.md`; high for the copy code), and the unknown regions (`0x00004`, story block `+0x3524`, record table `+0x292`, `0x1b108`, `0x1bf18`) stay zero or unchanged unless the static pass missed a writer.
- **Steps**: this is Session C's C5 (not run there): save in game, then compare `python -I tools/save.py <DATA0> --check` and spot values between the file and memory at `S`: DP `+0x0fdfc`, partner word `+0x16e12`, calendar `+0x1a24c`, frame counter `+0x0c` (allow the frames that passed). Then, at the end of every block of Session E and F, run the diff of that block's save pairs over the five unknown regions.
- **Record**: matches yes/no per value; per unknown region, any byte that ever changed (offset, old → new, the action that changed it).
- **Expected**: identical values; no change in the unknown regions (any change locates a field).

### Block E-W: free roam

**Setup.** Confirm M1 for `rel_story` and `rel_field`, compute `S`. Savestate `E-W0` on a field map in time slot 2–6 of a working day (calendar weekday `[S + 0x1a268]` ≠ 0), with the partner chosen (Session C used Jaden, partner word `0x0023`) and at least 600 DP. Add these standing logs for the whole block (all Log only):

| Address | Function | Log text |
| --- | --- | --- |
| `0x0884192c` (`BOOT.BIN`) | BGM fade start, called by `bgm_stop` and by `bgm` before a new track (`story.md`, opcode 50156) | `bgm_fade {a0} fc={[S+0x0c]} ra={ra}` |
| `0x088418f8` (`BOOT.BIN`) | stop the current track | `bgm_stop fc={[S+0x0c]} ra={ra}` |
| `0x08841850` (`BOOT.BIN`) | release the track | `bgm_release fc={[S+0x0c]}` |
| `rel_story:0x08ea5d18` | `world_queue_event(a1, a2, a3)` | `queue {a0} {a1} {a2}` |

#### E9. `hud_marker` at the sandwich seller

- **Hypothesis**: story opcode 50118 `hud_marker` posts field request 26; the `rel_field` handler `world_field_req_hud_marker` (`0x090d87a8`) arms marker A with sub-index `v` (`0x090d5fa4(10, 5, v)`, script targets 0 and 2–6) or marker B (`0x090e5b20(10, 5)`, target 7), and target 1 clears both. The seller lines use 7 … 1, so marker B points at the DP display (`docs/formats/story.md`, opcode table; medium for the code, low for which element 0–4 is).
- **Base**: `rel_field` `0x090ced00`.
- **Breakpoints** (Log only): `0x090d87a8` `hud_req a0={a0} a1={a1}`; `0x090d5fa4` `markerA {a0} {a1} {a2}`; `0x090e5b20` `markerB {a0} {a1}`.
- **Steps**: from `E-W0`, talk to the sandwich seller and buy one sandwich (it can be given to the partner, as in C3). Note on screen what the arrow or highlight points at while each log line appears.
- **Record**: the order of the log lines relative to the dialogue; what the marker points at (in words, no screenshot in the repository).
- **Expected**: `markerB 10 5` when the line that mentions DP appears, with a marker on the DP counter; a later `hud_req` that clears it (no marker call). Marker A (sub-index 0–4) needs the other six `hud_marker` uses: before the session the agent lists their records with `python -I tools/story.py events <USRDIR>/script/story_scr_b.ehp --list -o extracted/story/events.txt` (opcode 50118) and says where they play; observe them only if one is reachable.

#### E10. BGM fade time (opportunistic, standing logs)

- **Hypothesis**: `bgm_stop` (50156) and `bgm` call `0x0884192c(1500)`: a 1,500 ms fade-out, then wait for the voices, stop and release the track (`story.md`; medium).
- **Steps**: no extra steps: every event in this block that changes the music logs the three lines. Make sure at least one happens (an event with its own music, for example a chapter event in E13 or the duel request menu).
- **Record**: per fade: `a0`, the frame counter at `bgm_fade`, `bgm_stop` and `bgm_release`, and the `ra` of `bgm_fade`.
- **Expected**: `a0 = 0x5dc` (1,500), and `bgm_stop` follows about 1.5 s later (90 frames at 60 per second, 45 at 30, using E7's rate). If the stop follows at once, the argument is not a fade time.

#### E11. Arrival cells

- **Hypothesis**: when no event places the player, `world_place_player_on_arrival` (`rel_story` `0x08ea09c8`) puts the player on a fixed cell and direction per location, centred as `x·0.5 + 0.25`, and sends it with field request 9; the field state (save `+0x1a0e0`) holds `+0x00` location, `+0x04` previous location, `+0x08`/`+0x0c` player position (`f32`) and `+0x10` direction (`docs/formats/field-maps.md`, "Arrival cell"; `world.md`, save fields; high for the code, the field-state reading is high from the code but untested).
- **Breakpoints** (Log only): `rel_story:0x08ea09c8` `arrival`; `rel_field:0x090d83c4` (`world_field_request`) with condition `a0 == 9`, Log `req9 {a1} {a2} {a3}` (the argument layout of field requests is not documented: log the registers and read what they point at if they look like pointers). **Address status**: the request number in `a0` is an assumption from the name; if the condition never matches, log every call for one map change and report the `a0` values.
- **Steps**: from `E-W0`, make four map changes without an event: (1) from the Slifer dorm outside (location 6) into room 101 (location 7); (2) back out of room 101; (3) into the store (location 3) from outside; (4) any other exit. After each change, when the map is shown and the player stands still, read the five field-state words at `S + 0x1a0e0`–`S + 0x1a0f0`.
- **Record**: per change the location and previous location, the two floats (convert from hex), the direction, and the logged lines.
- **Expected**: (1) room 101: cell (11, 6), direction 3 → `5.75` (`0x40b80000`), `3.25` (`0x40500000`); (2) dorm outside from 7: (17, 24), direction 7 → `8.75` (`0x410c0000`), `12.25` (`0x41440000`); (3) store: (31, 17), direction 3 → `15.75` (`0x417c0000`), `8.75`; (4) the cell listed for that location in `field-maps.md`. If the floats do not change between maps, the live position is held elsewhere (in `rel_field`) and only the logs count.

#### E12. Doors: midnight lock *(distance part optional)*

- **Hypothesis**: on the Slifer dorm outside (maps 12/37, location 6) at light period 4 (time slot 7, "midnight"), the doors to maps 13–19 and 38 stay shut and the door cells `(15, 24)`, `(15, 20)`, `(15, 16)`, `(15, 12)`, `(13, 24)`, `(13, 20)`, `(13, 16)` are not walkable (`world_is_cell_walkable` mode 1), while room 204 (`(13, 12)` → map 20) and the dining hall (`(13, 6)` → map 21) stay reachable. A door opens when the player is within 0.75 units (`world_update_doors` `0x090da588`; `field-maps.md`, "Doors", "Walkability overrides"; high for the code).
- **Base**: `rel_field` `0x090ced00`.
- **Breakpoints** (Log only): `0x090db820` (door sound, called when a door starts opening) `door_open kind={a0} pc={pc}`; `0x090d9cc8` (`world_get_door_cell_target(x, y)`) with condition `a0 == 13 || a0 == 15`, Log `door_cell x={a0} y={a1}`.
- **Steps**: on the dorm outside in slot 2–6, walk up to room 101's door and step on its cell (`door_open`, then the map change). Reload, use the PDA's "Advance Time" to slot 7 (read `[S + 0x1a260]` = 4, the light period), go to the dorm outside, and try room 101, then room 204 and the dining hall. *(Optional, distance)*: at the moment `door_open` logs, read the player floats at `S + 0x1a0e8`/`S + 0x1a0ec` (if E11 showed that they follow the walk) and compare with the door's position (the agent supplies it from `world.py tables`, `doors`).
- **Record**: per door and slot: door opened (log yes/no), could the player step on the cell, did the map change; light period; *(optional)* distance at opening.
- **Expected**: slot 2–6: room 101 opens and leads in. Slot 7: room 101 neither opens nor lets the player onto its cell; room 204 and the dining hall open and lead in. *(Optional)* the distance at opening is ≤ 0.75 (in map units, after subtracting grid vertex 0).

#### E13. Chapter stage and step bytes during one chapter

- **Hypothesis**: field save block bytes `+0x00` (story stage 1–10) and `+0x01` (chapter step 1–4) at save `+0x1a270`/`+0x1a271` drive the partner chapter: when the partner's points equal the stage cap (`1000 × stage`), `world_try_chapter_event` (`rel_story` `0x08e9cad0`) queues step 1 on the first map entry of a working day (daily step, needs the partner-talk-pending word, save `+0x1a394`, = 1), step 2 at the highlighted location in slots 2–6 (it ends in a duel), step 3 right after the duel, and the stage-closing record's `advance_counter` (`world_advance_story_stage` `0x08eab3c0`) sets stage + 1, step 1 (`docs/formats/chapter-table.md`; high for the code; the step-3 location test is an open question there).
- **Named memory edit E-X1** (allowed for this check only, under rules 3–5 of the policy: emulation paused, recorded, everything observed comes from the game's code): set the partner's points `u16` at `S + 0x0fe0c + c × 0x18 + 0x16` (Jaden `c = 2`: `S + 0x0fe52`) to `cap − 10` (990 in stage 1). The gift in step 2 below then lets the game's own `world_change_char_points` reach and clamp to the cap. The check observes the stage/step bytes and the queued keys, never the points directly.
- **Breakpoints**: memory breakpoint on `S + 0x1a270`, size 2, Write, Log `stage_step pc={pc}`; execute logs (`rel_story`): `0x08e9cad0` `try_chapter pts={a0} loc={a1} stage={a2}`, `0x08eab40c` `advance_step`, `0x08eab3c0` `advance_stage`, `0x08e9d9c0` `points char={a0} delta={a1}`, and the standing `queue` log.
- **Steps**:
  1. From `E-W0` (stage byte `[S + 0x1a270]` = 1, step 1), read stage, step, points and `[S + 0x1a394]`. Savestate `E13-pre`. Apply E-X1.
  2. Give the partner one sandwich (any taste except 4/5, which lower the points): the points should become 1,000.
  3. End the day (PDA), then enter any map in slot 1–6: expect step 1's key in the `queue` log and step → 2.
  4. Open the island map: the step-2 location should be highlighted. Go there in slot 2–6: expect step 2's key and step → 3; the record ends in a duel. Savestate `E13-duel`.
  5. *(optional, 15 min)* Play and win the duel. Back on the field, expect step 3's key at once (`world_queue_next_chapter_event`, mode 4), step → 4, then `advance_stage` (stage → 2, step 1) from the stage-closing record.
- **Record**: the stage/step bytes after each step with the writer `pc`; every `try_chapter` and `queue` line; the points before and after the gift; whether the location of step 2 needed a slot outside 1 and 7; the edit E-X1.
- **Expected**: bytes `(1,1)` → `(1,2)` → `(1,3)` → [after the duel] `(1,4)` → `(2,1)`. Queued keys `(a1, 1, 1)`, `(a1, 1, 2)`, `(a1, 1, 3)` with `a1` the partner's row key (201–203 for Jaden's rows; `world.py chapters` gives the exact row). `try_chapter` returns early (no queue) while the points are below 1,000. The points clamp at 1,000 even when the delta would exceed it.

#### E14. *(optional)* Weekly pairing byte and picture bits (differential saves 13 and 11)

- **Steps**: save on a Sunday (weekday `[S + 0x1a268]` = 0, `E14-a`), end the day, save on the Monday (`E14-b`); watch an event that shows a picture (story opcode 50111; the agent names one from `story.py events`) and save before (`E14-c`) and after (`E14-d`).
- **Expected**: `0x16e11` bit 0 may flip on Monday and the pairing order at `0x1a28c` changes (Session C); `0x16e10`: record whether and when it changes. After the picture, bit `id` of `0x1b0fc` is set (`save.md`, experiments 13 and 11).

#### E15. *(optional, needs a late save)* Story state 46 and what follows the staff roll

- **Hypothesis**: `finish_partner_story` (50137) makes `world_driver_finish_partner_story` (`rel_story` `0x08ea2b38`) set the partner's character-row bit 2, unlock the partner's decks and set story state 46; state 46 (`world_state_start_staff_roll`, `0x08ea3984`) leads through 49/48 to `world_play_staff_roll_movie` (`0x08ea3ae8`), which plays `TF3_staffroll2_a.pmf` or `TF3_staffroll_a.pmf` (`chapter-table.md`, "End"; `story.md`; medium). What comes after is open.
- **Precondition**: a save at stage 4 step 4 of a partner story (or just before the ending record `(219, n, 1)`). Without one, skip this check; E13 shows the way there.
- **Breakpoints**: memory breakpoint on the story state `0x08ecd978` (`rel_story` global), size 4, Write, Log `story_state pc={pc}`; execute logs `0x08ea2b38` `finish_partner`, `0x08ea3984` `staff_roll_start`, `0x08ea3ae8` `staff_roll_movie`, and E2's `movie_create`.
- **Record**: the sequence of story-state values, the movie chosen, what the game shows after the movie (title, new partner choice, field), the stage/step bytes afterwards, and the diff of a save before/after (also differential save 14 if a new cycle starts: partner word bits 1–3, `0x16e0c`, all pack stocks back to `0xaa`).
- **Expected**: states 46 → 49 → 48 → 49 → 50; character-row bit 2 of the partner set (save `+0x1bf8c + 2r`, byte 0 bit 2).

### Block E-P: card shop

**Setup.** Confirm `rel_shop` at `0x090ced00` (E0). Free roam with enough DP for one pack of a kind never bought (the shelf of packs on sale; prices are in `tools/tables.py odds`). Save before entering (`E16-a`).

#### E16. One pack purchase

- **Hypothesis**: buying one pack (mode 0, no shoulder button) calls `save_add_dp(−price)`, `save_set_pack_bought(p)` (`0x088548a0`, save byte `+0x1542a + p` = 1) and `save_add_packs_bought(1)` (`0x0885761c`, `u16` `+0x16602`), and removes one pack from the shelf (record byte 0, two nibbles); opening it (`shop_draw_pack_cards(p, out)`, `0x090d9678`) draws the rarity from the pack's rarity box and writes it to one entry with `save_set_pack_entry(p, n, r)` (`0x0885752c`), `n = 20 − remaining`, `r` ∈ 1–3; the cards enter the collection only at `shop_commit_results` (`0x090d90c0`) when leaving through the results screen (`docs/formats/packs.md`; high for the draw, medium for the flow).
- **Breakpoints** (Log only): `0x088548a0` `pack_bought p={a0}`; `0x0885761c` `packs_bought +{a0}`; `rel_shop:0x090d9678` `draw p={a0} out={a1}`; `0x0885752c` `pack_entry p={a0} n={a1} r={a2}`; `rel_shop:0x090d90c0` `commit`; standing `dp_add`.
- **Steps**: in the shop, before buying, read for the chosen pack `p` (the agent gives `p` for the pack's shelf position, or read it from the first `draw` log and repeat on a reload): the record at `S + 0x16604 + 0x2a × p` (byte 0 stock, byte 1 state, 20 `u16` entries from `+2`), `[S + 0x1542a + p]`, `u16 [S + 0x16602]`, DP `[S + 0x0fdfc]`. Buy one pack, let it open, leave through the results screen, read everything again. Save (`E16-b`).
- **Record**: values before/after; the log lines in order; the pack's 5 card ids drawn (from `out` after the draw, `u16` each, or from the results screen).
- **Expected**: DP − price (one `dp_add` with the negative price), byte `0x1542a + p` 0 → 1, `0x16602` + 1, stock nibble − 1, exactly one `pack_entry` with `n` = the number of non-zero entries before and `r` ∈ {1, 2, 3}, and the rare-slot card shown last. `commit` logs once on leaving. The diff `E16-a`/`E16-b` shows these bytes and the collection counts of the drawn cards (`0x11ba4 + 4 × record`, byte 1), nothing else outside the frame counter (this is differential save 10).

#### E17. *(optional)* A box of 20: the rarity box

- **Hypothesis**: every 20 consecutive packs of one kind hold exactly 14 rarity-1, 4 rarity-2 and 2 rarity-3 draws (slot counts `{0, 14, 4, 2}` at `rel_shop` `0x090ef2fc`); when all 20 entries are used they are cleared and the box restarts (`packs.md`, "Rarity box"; high, code).
- **Steps**: with a full shelf of one pack kind (stock `0xaa`), hold the shoulder button for the box purchase (mode 2, 20 packs), open them all (skipping is fine: `shop_open_all_packs`). Keep E16's logs on.
- **Record**: the 20 entries before, the `pack_entry` lines `(n, r)` in order, and the 20 entries after.
- **Expected**: counting the entries that were already used before the box and the new draws up to the point where the box was full, the rarities are exactly 14 × 1, 4 × 2, 2 × 3; at the wrap the entries are cleared and `n` restarts at 0.

### Block E-K: deck editor

#### E18. Deck editor state (differential saves 8 and 9)

- **Hypotheses**: the 99-entry card list at save `+0x161f4` (count) / `+0x161f6`, its states at `+0x162bc`, and the `0x200`-byte edit block at `+0x16382` belong to the deck editor (medium for the list, low for the meaning); stored deck records at `+0x20` hold named decks saved from the editor (medium) (`save.md`, experiments 8 and 9).
- **Steps**: save (`E18-a`). In the deck editor: take two cards out of the deck, put one in, change the sort order and one filter, then save the deck and leave; save the game (`E18-b`). If the editor offers storing a deck under a new name, do it and save the game again (`E18-c`).
- **Record**: the changed offsets of each pair (offset, old → new), grouped by region; which action came last before each change.
- **Expected**: changes in the deck slot lists (slot 0 or 1), in the card list `0x161f4` and its states, possibly in the edit block (sort and filter settings); with a stored deck, flag, name and lists of stored record 0.

#### E19. First-visit progress bytes (differential save 12)

- **Hypothesis**: the bytes `0x16de4 + n` record first visits of help pages or tutorials; entry 2 changes to 1 after day 8 (`save.md`, experiment 12; low).
- **Steps**: save (`E19-a`), open each deck-editor help page that has never been opened, save (`E19-b`). *(optional)* Save before and after day 8 (Session C's savestate reached day 8).
- **Expected**: one byte `0x16de4 + n` grows per new page; record `n` per page.

### Block E-L: tutorial lesson

**Setup.** Start tutorial lesson 1 (lessons 20–25 have no script and are not useful here) from the tutorial list. Confirm M1 for `rel_duel_eng` (`0x09be1804`, as always). Savestates: `E-L00` in the tutorial list just before choosing the lesson (the `.ydq` loader and the opening draws may run before the field is shown), `E-L0` on the first frame of the duel field. As with `S`, `T+0x…` in a log text stands for the computed number (E20).

#### E20. `rel_tutorial`'s runtime base

- **Hypothesis**: during a lesson `rel_tutorial` is loaded at an unknown base `T` (none of the seven symbol exports was taken in a lesson; `docs/formats/tutorial.md`, "Open questions"). Its init registers `duel_core_tutorial_ui_event_hook` (`T + 0x6098`) at `0x09e01e10` and `duel_core_tutorial_gate_duel_flow` (`T + 0x4310`) at `0x09e01e3c` (`tutorial.md`, hook table; high).
- **Steps**: read `[0x09e01e10]` and `[0x09e01e3c]`; compute `T = [0x09e01e10] − 0x6098` and `T' = [0x09e01e3c] − 0x4310`. Then **Debug → Save Map File…** to `ghidra/tutorial-<date>.sym` and run `python -I tools/modules.py base ghidra/tutorial-<date>.sym <USRDIR>/gmodule`. Also read the duel mode `[0x09e2d1f4]`.
- **Record**: both pointers, `T`, `T'`, the vote result for `rel_tutorial` (base, starts matched), the duel mode.
- **Expected**: `T = T'`, aligned to `0x100`, equal to the vote result with most of the 161 starts matched; duel mode 3. Every `T + offset` below uses this value.

#### E21. Opening hands are drawn from the start of the `.ydq` list

- **Hypothesis**: the `.ydq` loader puts the lesson's hand cards into the deck list ahead of the deck cards and then posts command `0x56` (draw, handler `0x09dbb7d8`) per side with the hand count, turn player first, so a draw takes the list from its start (index 0 = top) (`tutorial.md`, "Hand"; medium; the deck-top convention itself was effectively confirmed in Session D, where Pots of Greed drew Deck entries 0–11).
- **Breakpoints**: execute at `0x09dbb7d8`, **Break on**, enabled from `E-L00` (load it, set the breakpoint, choose the lesson) until the two opening draws have run.
- **Steps**: at each break read the side's hand count `+0x0c` and deck count `+0x10` and the first eight deck entries (`[P + 0x304 + 4i] & 0x3fff`; side 0 `0x09e2a82c`, side 1 `0x09e2b368`); Step Out and read the hand list (`P + 0x124`) and both counts again.
- **Record**: per side the deck ids before (first eight), the hand ids after, the counts.
- **Expected**: the hand equals the first `n` deck entries in order (`n` = the lesson's hand count), the deck count falls by `n`, and the ids match the lesson file's `CardInHand` lines (the agent compares them with `python -I tools/tutorial.py` output under `extracted/`).

#### E22. How a `wait_input` and a `wait_event` resume the script

- **Hypothesis**: the tutorial state word (`T + 0x17f2c`) is 4 while a `wait_input` waits; the UI event that confirms the awaited action (for example `0x38` summon done, `0x1e` card set, 5 phase banner) sets 2, and `duel_core_tutorial_wait_ui_idle` sets 1 once no UI event is busy; in state 6 (`wait_event`) the awaited event resumes at once (events 4, 54, 55) or through state 2. The duel-flow gate holds the engine except in states 4, 6 and 8 (`tutorial.md`, hook table, "The events are UI events"; high for the code).
- **Breakpoints**: memory breakpoint on `T + 0x17f2c`, size 4, Write, Log `tut_state pc={pc}` (read the value with F10 or log `{[T+0x17f2c]}` one write later); execute at `0x09be1400` (`duel_core_post_ui_event(event, a1, a2, a3)`), Log `ui_event {a0} {a1} {a2} {a3}`; execute at `T + 0x39b4` (`duel_core_tutorial_filter_input`), Log `filter {a0} {a1}`. Keep the Session A command log on.
- **Steps**: from `E-L0`, follow the lesson's instructions for its first three player actions (for example a Normal Summon, a set card, a phase change). Once, do a wrong action first (press a different button than the hint asks).
- **Record**: the sequence of states with the UI events and commands between them; for the wrong action, the `filter` line and whether anything happened on screen; the awaited kind and card `u16 [T + 0x17f3a]`, `u16 [T + 0x17f3c]` during each wait.
- **Expected**: per instruction: state 4 (awaited kind as in the `wait_input` table) → the matching UI event → state 2 → 1 after the UI is idle, then the script runs to the next wait. The wrong action is filtered (`filter` logs, nothing happens). No UI event 54 with `a1 = 3`, `a3 < 2` reaches the screen (answered with 0 unless `flag_on 2`).

### Block E-M: minigames

#### E23. Minigame bases, high scores and blocks (differential saves 6 and 7)

- **Hypotheses**: nine high scores at save `0x11444`–`0x11464` and their "new" bits at `0x11490 + k`, plus per-minigame blocks at `0x1be0c` (blackjack), `0x1be10` (dodge), `0x1be18` (underground), `0x1be50` (throw) (`save.md`, experiments 6 and 7; medium / low). The minigame modules' runtime bases are unknown (`modules.md`).
- **Steps**: save (`E23-<game>-a`). Play one round of one minigame, note the score and any setting changed inside the game, and on its result screen take **Debug → Save Map File…** (`ghidra/<game>-<date>.sym`; the agent runs `modules.py base` on it later). Leave and save (`E23-<game>-b`). Repeat for blackjack, connection, dodge, quiz, reversi, throw, underground, as time allows.
- **Record**: per minigame: score shown, settings changed, the changed save offsets with old → new, DP before/after (standing `dp_add` log).
- **Expected**: per game one high-score word and one bit change (the index → minigame mapping), DP rises by the reward, and the game's block (if it has one) changes when its settings do. The `.sym` files give the module bases for E24 and later work.

#### E24. The result screen's string table (`mini_result`)

- **Hypothesis**: the minigames share one result helper that receives its string table from the caller's buffer; the table is presumably `mini_result_<l>.bin` from `mini_result_<l>.ehp`, inferred from the archive only (`ui.md`, "Open questions"). **Address status**: the helper's address is not known (minigame bases unknown), so this check works from `BOOT.BIN` functions only.
- **Breakpoints**: `0x08822280` (`container_ehp_find_member(ehp, name, out_size)`), **Break on**, enabled only while the result screen is being entered; `0x08836ed0` (`card_db_get_dictionary_word(dict, n)`), Log `dict={a0} n={a1} ra={ra}`, enabled on the result screen.
- **Steps**: in one minigame, just before the round ends, enable the `find_member` breakpoint. At each break read the name string at `a1` in Memory View, Step Out, note `v0`. Disable it when the result screen shows, then let the dictionary log run for 3 s.
- **Record**: the `(name, v0)` pairs; the distinct `(dict, n, ra)` lines.
- **Expected**: one `find_member` returns the pointer that later appears as `dict` in the dictionary log, and its name is `mini_result_<l>.bin` (or the table the open question names); the `ra` values lie in the minigame module (E23's base) and give the helper's address.

**Session E results**

| Check | Recorded | Expected | Pass? | Notes |
| --- | --- | --- | --- | --- |
| E0 bases: title / shop / tutorial / minigames | | `0x08e9aa00` / `0x090ced00` / E20 / E23 | | `.sym` names |
| Save dialog modes seen (standing) | | modes 0, 1, 3; 7/8/`0x16`? | | screen per mode |
| E1 ready flag, building flag, entry count | | 1, 0, number of files on the disc | | first path, LBA, size |
| E2 opening: `movie_create` ra; skip button | | ra in `rel_title`; (open) | | idle replay? |
| E3 `(ra, idx, k)` per title screen | | `k` ∈ {0, 6, 12, 18} | | screens visited |
| E4 play call: function of the repeating `ra` | | one function per sound | | `atrac_loop` for music |
| E5 title words / settings bits per option | | one field per option | | |
| E6 *(optional)* first audio / video PTS | | `0x14c4d` / `0x15f90`, audio first | | PPSSPP behaviour only |
| E7 frame counter +60 s, FPS shown; `+0x04` | | ≈ 3,600 or 1,800; `+0x04` constant | | |
| E8 file vs memory; unknown regions | | identical; no change | | |
| E9 marker B on the DP counter | | `markerB 10 5`, then cleared | | other targets reachable? |
| E10 fade `a0`, frames fade → stop | | `0x5dc`, ≈ 1.5 s | | |
| E11 field state after four map changes | | cells and directions of the table | | |
| E12 doors at slot 2–6 / slot 7 | | 101 open / 101 shut, 204 and dining hall open | | *(optional)* distance |
| E13 stage/step bytes, queued keys | | `(1,1)→(1,2)→(1,3)[→(1,4)→(2,1)]` | | edit E-X1 listed |
| E14 *(optional)* `0x16e10`/`0x16e11`, picture bit | | (open) / bit `id` | | |
| E15 *(optional)* story states, movie, what follows | | 46 → 49 → 48 → 49 → 50 | | |
| E16 DP, bought byte, packs bought, stock, rarity entry | | −price, 1, +1, −1, one entry 1–3 | | pack `p`, cards |
| E17 *(optional)* box rarity counts | | 14 / 4 / 2 | | |
| E18 changed offsets: editor actions, stored deck | | `0x161f4` list, slots, edit block | | |
| E19 progress byte per help page | | one byte per page | | |
| E20 `T` from hook, gate, vote; duel mode | | equal; 3 | | |
| E21 hand = first `n` deck entries | | yes | | lesson file match |
| E22 state sequence per instruction; wrong input | | 4 → event → 2 → 1; filtered | | |
| E23 score offset and bit per minigame | | one each | | `.sym` per game |
| E24 result table name, helper `ra` | | `mini_result_<l>.bin` | | |

## Session F: duels (leftovers of Session A, the AI plan, the duel HUD, D2)

**Setup.** Session 0 (M1 duel bases, M2 for `S`), then a single duel against a CPU (an early opponent with few removal cards is best, as in Session D). Standing instrumentation of Session A: command log at `0x09dc07f8` and Memory View pinned on `0x09e2d1d8`. All shortcuts (S1–S3) follow the memory-edit policy; write every edit into the results file. Card ids below were looked up with `tools/cardinfo.py` on `cardinfo_eng.ehp` and are cards of this game: Dian Keto the Cure Master `0x10fc`, Ookazi `0x1100`, Pot of Greed `0x12ec`, Magic Jammer `0x12fe`, Shield & Sword `0x12cb`, Rush Recklessly `0x1329`, Big Bang Shot `0x1625`, Cyberdark Impact! `0x1c31`.

| Block | Scene | Checks | Time (estimate) |
| --- | --- | --- | --- |
| F-1 | Single duel, own turns | F1–F5 | 40 min |
| F-2 | Same duel, CPU turns | F6–F8 (F8 optional) | 25 min |
| F-3 | Any duel with a field spell | F9, F10 | 15 min |
| F-4 | Free roam around duels | F11 | 3 duels (one tag), about 45 min; can be combined with ordinary play |
| F-5 | Single duel, staged | F12 (= D2) | 30 min |

### Block F-1: own turns

#### F1. Does the first player draw on turn 0 of a single duel?

- **Hypothesis**: open for single duels (`duel-phases.md`, "Open questions"); in tag duels the first player draws on turn 0 (Session B).
- **Steps**: start the command log **before** the duel starts (on the versus screen). After the opening hands (`0x56` / `0x8056` with `b = 5`), watch turn 0 (`[0x09e2d1e0] = 0`) between command `0x0a` (or `0x800a`, enter Draw Phase) and `0x0b`.
- **Record**: the commands of turn 0 up to `0x0c`; the first player's hand count `+0x0c` before and after its Draw Phase.
- **Expected**: none fixed; the answer closes the open question. Note which side went first.

#### F2. Every Life Point writer, gain and effect damage

- **Hypothesis**: only commands `0x23` (gain), `0x24` (loss; `b` = 0 effect, 1 battle, 2 cost, 3 lost) and `0x25` (set) write LP, through `0x09dbffd8`–`0x09dc05e3` and the `0x25` handler `0x09dc05f4` (`battle.md`, "Life Points"; high; `_lp_loss` verified in Session A, `_lp_gain` and `_set_lp` not exercised).
- **Breakpoints**: memory breakpoints on `0x09e2a528` and `0x09e2b064`, size 4, Write, **Break on** (rare), Log `LP write pc={pc} ra={ra}`; step once (F10) before reading the new value.
- **Steps**: with S1, replace two own hand cards with Dian Keto the Cure Master (`0x10fc`, gain 1,000) and Ookazi (`0x1100`, 800 damage to the opponent) in a Main Phase 1 (`u16 [0x09e27fee] == 0`). Activate both. Keep the breakpoints on for the rest of the session: every battle damage, cost and effect counts.
- **Record**: per write the command before it (`op`, `a`, `b`), LP before/after, the writer `pc`; whether any write had no command before it.
- **Expected**: Dian Keto: `0x23 a=0x3e8` (side bit clear for side 0), own LP + 1,000, `pc` in the gain/loss body. Ookazi: `0x8024 a=0x320 b=0` (bit 15 = the damaged side, as Session A's `0x8024 a=0xc8 b=1`), CPU LP − 800. No write without a preceding `0x23`–`0x25` after the duel start. A `0x25` (set) only if a card in play sets LP; note it if seen.

#### F3. Direct attack (step 8?) and piercing damage

- **Hypotheses**: the Battle step index `0x09e2d220` runs `2…10` per attack (`battle.md`, "The steps"); whether step 8 runs for a direct attack is open (Session A stopped at step 4). With a piercing equip (Big Bang Shot `0x1625`: +400 ATK and piercing, `duel_core_has_piercing` `0x09bedf1c`), an attack on a Defense Position monster with `ATK > DEF` deals `ATK − DEF` to its controller; damage records at `0x09e286e0 + i × 0x14` (amount, source side, source slot, damaged player, damaged slot) (`battle.md`; high).
- **Breakpoints**: memory breakpoint on `0x09e2d220`, size 4, Write, Log `bstep pc={pc}` (or the step-entry logs of A4 with condition `[0x09e2d224] == 0`); execute at `0x09dd7528` (step 7), **Break on**.
- **Steps**: (a) on a turn > 0 with the CPU's monster zones empty, attack directly. (b) Equip Big Bang Shot (S1 into the hand) to a monster and attack a CPU Defense Position monster whose DEF is lower than the new ATK. At each step-7 break read `0x09e28620` (attacker side), `0x09e2863c` (attacker slot), `0x09e28640` (target, 5 = direct), the battle records' `+0x24`/`+0x28` (`0x09e28650 + side × 0x48`) and the two damage records.
- **Record**: the step sequence of each attack; the damage records; the `0x24` commands.
- **Expected**: (a) target 5, damage record `damaged slot = 5`, amount = ATK; record whether 8 appears. (b) one damage record with amount `ATK − DEF` for the CPU, `0x24 … b=1`, the defender destroyed. A second record (`add_damage(A, A, …)`) should not appear here (it belongs to an opponent-controlled piercing equip, `battle.md` open question).

#### F4. ATK with a temporary boost and a field spell (A6 steps 3–6)

- **Hypothesis**: as A6 (Session A). Steps 1–2 passed; steps 3–6 remain: the field spell, the temporary boost (a kind-2 record keyed by the card, freed at the turn change by `duel_core_expire_turn_effects` `0x09be6864`), the reading in the opponent's turn, the equip leaving.
- **Instrument**: as A6 (`0x09c0a604` `duel_core_get_atk`, Break on with a condition on side and slot, Step Out, `v0`; enable only for a reading).
- **Steps**: from a Main Phase with a face-up monster: activate Rush Recklessly (`0x1329`, +700 until the End Phase; S1 into the hand) and read ATK; walk the slot's record list as in A6 (head `[0x09e2a566 + slot × 0x14] & 0xffff` for side 0, records at `0x09e2c7cc + 10 × i`). In the CPU's turn read ATK again and walk the list. If the deck has a field spell that boosts the monster's Type or Attribute, activate it and read ATK; if the equip from A6 can be destroyed (or the monster unequipped), read once more.
- **Record**: the readings next to the screen; each record (key, kind, counter, value, timestamp); the `0x35` commands.
- **Expected**: +700 after Rush Recklessly with a kind-2 record keyed `0x1329`, counter 0; the record gone and ATK back in the CPU's turn; field spell and equip changes match the card texts and the screen.

#### F5. A negated chain link keeps its place (Magic Jammer)

- **Hypothesis**: a negated link stays on the chain with `+0x04` bit 1 set; its effect does not run (`chain.md`; open question answered by Magic Jammer).
- **Breakpoints**: memory breakpoint on `0x09e28e34` (chain count), size 4, Write, Log `chain_n pc={pc}`.
- **Steps**: with S1 put Magic Jammer (`0x12fe`) and Pot of Greed (`0x12ec`) into the hand; set Magic Jammer face-down and end the turn. In the next own Main Phase 1 activate Pot of Greed, then chain Magic Jammer (discard one card). When link 2 has resolved (count 2 → 1), break once and read link 1 (`0x09e28cb4`: `+0x00` card id, `+0x04`).
- **Record**: link 1's id and `+0x04` before and after link 2 resolves; whether Pot of Greed drew (hand and deck counts); the `0x11`/`0x12` commands.
- **Expected**: link 1 = `0x12ec` with `+0x04` bit 1 set after the Jammer resolves; no draw; Pot of Greed goes to the Graveyard.

### Block F-2: the CPU's turns (AI plan checks of `ai.md`)

These are the seven checks of `docs/subsystems/ai.md`, "PPSSPP checks for the plan comparison", made concrete. `rel_duel_eng` must be at `0x09be1400` (M1). None of them edits an AI block (policy rule 2); only S1 on the CPU's hand is used, during the human's Main Phase with `u16 [0x09e27fee] == 0`.

**Staging.** In your Main Phase 1 replace one CPU hand card with Shield & Sword (`0x12cb`, a combat trick listed by `ai_analyze_board`) and, for F7, another with Cyberdark Impact! (`0x1c31`, a card that `ai_board_note_card_interests` tests). Leave at least one monster on your side so that the CPU has something to attack. Savestate `F6-pre` at your End Phase.

#### F6. Plan headers, the trick mask, snapshots and the plan value (ai.md checks 1, 2, 4, 5, 6)

- **Hypothesis**: during the CPU's battle planning `ai_plan_battle_with_tricks` (`0x09d15b58`) builds a base plan and one plan per usable trick, compares each with `ai_compare_plans(new, best)` (`0x09d36d4c`) and keeps the new one when `v0 & 0x1e` (`& 0x10` for Limiter Removal `0x1409`) is non-zero. Plan header: `+0x06` opposing monsters (`u16`), `+0x08` total damage, `+0x0c` score, `+0x10`/`+0x14` own / opposing LP after the plan, `+0x1c`/`+0x1e` own / opposing deck (`s16`), `+0x20` the trick card id (0 in the base plan). `ai_plan_battle` (`0x09d16568`) pushes and pops snapshots (depth `u16 0x09e27fee`) and leaves LP unchanged. The accepted full plan is copied to `0x09e279c8 + side × 0x2e4` (`ai.md`, "Decision pipeline", steps 3 and 7; high for the logic, medium for the field meanings).
- **Breakpoints** (Log only unless noted):
  - `0x09d16568` `plan_battle depth={[0x09e27fee]&0xffff} lp0={[0x09e2a528]} lp1={[0x09e2b064]}`
  - `0x09d15b58` `with_tricks side={a0} mode={a1}`
  - `0x09d36d4c` `cmp a={a0} b={a1} a.trick={[a0+0x20]&0xffff} a.opp_mon={[a0+0x04]>>16} a.dmg={[a0+0x08]} a.score={[a0+0x0c]} a.own={[a0+0x10]} a.opp={[a0+0x14]} b.score={[a1+0x0c]} b.own={[a1+0x10]} b.opp={[a1+0x14]}` (if memory reads are not interpolated, use **Break on** for the first three hits and read the fields by hand)
  - the result `v0` of `ai_compare_plans`: **Break on** at `0x09d36d4c` for the first three hits and Step Out. *Address status*: `ai.md` suggests a log at `0x09d36e00`; use it only if the Disassembly shows `jr ra` there and the instruction after it (the delay slot, `0x09d36e04`) does not write `v0`; then log `cmp_ret {v0}`.
  - `0x09d16a84` (`ai_get_plan_value`), **Break on** once, Step Out, read `v0`.
  - `0x09d0c2e4` (`ai_is_better_attack_result(side, result, best, flag)`) `better side={a0} res={a1} best={a2} flag={a3}`; enable only for one attacker (it runs per candidate target).
- **Steps**: load `F6-pre`, end your turn, let the CPU play. Disable the logs after the CPU's Battle Phase begins. Then read the CPU's accepted plan header at `0x09e279c8 + side × 0x2e4` (*address status*: that the header starts at the block start is an assumption; record the first `0x28` bytes' fields as above and say if they look shifted) and let the Battle Phase run.
- **Record**: the `cmp` lines (trick, fields, `v0`), which plan was kept (the next `cmp` uses it as `b`), whether the CPU actually activated Shield & Sword; depth and LP at entry and after Step Out of `ai_plan_battle`; `ai_get_plan_value`'s `v0`; the planned `+0x08` against the battle damage actually dealt (the `0x24 … b=1` commands of that turn); the `better` hits and the attack the CPU declared (`0x09e2863c`, `0x09e28640`, command `0x14`/`0x15`).
- **Expected**: the base plan with `a.trick = 0`, the trick plan with `0x12cb`; `+0x10`/`+0x14` equal to the LP minus the planned damage; the trick plan is kept exactly when `v0 & 0x1e ≠ 0`, and the CPU activates Shield & Sword only then. Depth and LP are the same before and after `ai_plan_battle`. Planned damage `+0x08` = damage dealt when the CPU follows the plan. The winning `better` candidate matches the declared target.

#### F7. Interest records (ai.md check 7)

- **Hypothesis**: `ai_analyze_board(view)` (`0x09d91fe8`) fills 32 interest records of 24 bytes at `0x09e28014 + side × 0x30c` (`u16` weight at `+0`, card id at `+4`, flag bytes) for cards the side holds (`ai.md`, "Board view"; medium, flag bytes low).
- **Breakpoints**: `0x09d91fe8`, **Break on** once in the CPU's Main Phase 1, Step Out.
- **Steps**: with Cyberdark Impact! in the CPU's hand (staging above), read the CPU side's table after Step Out: for each non-empty record, the weight, the card id and the flag bytes (`+6`–`+0x17`).
- **Record**: the non-empty records (index, weight, id, flag bytes); the CPU's hand and field ids for comparison.
- **Expected**: at least one record whose id is `0x1c31` or one of the cards it combines with (the agent reads the compare chain for `0x1c31` to say which); weights small positive integers; empty records all zero.

#### F8. *(optional)* The crossed guards of `ai_compare_plans` (ai.md check 3)

- **Hypothesis**: `ai_compare_plans(a, b)` returns 0 when `a.own_lp ≤ 0 && b.opp_lp > 0`, and sets `0x10` when `a.opp_lp ≤ 0 && b.own_lp > 0` (the guards cross `a`'s own value with `b`'s opponent value; whether that is intended is open; `ai.md`, step 7).
- **Steps**: no staging is required: every `cmp` line of F6 (and of any later CPU turn with the same logs) is a data point. To provoke the "a wins" case, use S2 to set your LP low (for example 500, never 0) before the CPU's turn, so that a plan can win; for "a loses", set the CPU's LP low while you have a monster whose battle damage reflects (as in Session A's 2000-DEF Defense Position monster).
- **Record**: the `cmp` lines with `a.own ≤ 0` or `a.opp ≤ 0`, and `v0`.
- **Expected**: `v0 = 0` for `a.own ≤ 0` with `b.opp > 0`; bit `0x10` for `a.opp ≤ 0` with `b.own > 0`; the agent checks every logged pair against the formula.

### Block F-3: a duel with a field spell

#### F9. The duel HUD's `ddstrtbl` index/body pair

- **Hypothesis**: `rel_duel_draw` (`0x0983fb00`–`0x09903127`, 800,296 bytes) reads `ddstrtbl_<lang>_idx.bin` / `_body.bin` without the headed accessor, and `ddstrtbl_<l>.bin`, `help_strtbl_*` through `card_db_get_dictionary_word` with table pointers held in runtime state (`ui.md`, "Open questions"; the table names are in the module's data, medium).
- **Breakpoints**: `0x08822280` (`container_ehp_find_member(ehp, name, out_size)`) with condition `ra >= 0x0983fb00 && ra < 0x09903128`, **Break on**; `0x08836ed0` (`card_db_get_dictionary_word(dict, n)`) with the same condition, Log `dict={a0} n={a1} ra={ra}`.
- **Steps**: set both before the duel starts (versus screen). At each `find_member` break read the name at `a1` and Step Out (`v0` = member data, `[a2]` = size if `a2` ≠ 0). For the `_idx` member, add a memory breakpoint on its first 16 bytes (`v0`, size 16), **Read**, Log `ddidx read pc={pc}`, and disable the `find_member` break. Play until the HUD has shown a phase banner, a card-effect message and a menu.
- **Record**: the `(name, v0, size, ra)` list; the `pc` values of the `_idx` reads; the distinct `(dict, n, ra)` lines, with `dict` matched to a name from the list.
- **Expected**: `find_member` returns the `_idx` and `_body` members, and their reads come from one or two `rel_duel_draw` functions (the agent decompiles them); every `dict` of the dictionary log is one of the names found, which turns the 29 runtime-table requests of `rel_duel_draw` into named ones.

#### F10. Playback rate of the 3D backdrop animation

- **Hypothesis**: `field_3d_update_model(inst, step*)` (`BOOT.BIN` `0x0882fa94`) advances an instance's frame by `*step` (1.0 when `step` is null) per call; the number of calls per second (30, 60 or variable) is not established; the exporter assumes 30 (`docs/formats/tgm.md`, "Playback", "Open questions"; high for the code, unknown for the rate).
- **Breakpoints**: `0x0882fa94`, Log only, `tgm_upd inst={a0} step={a1} fc={[S+0x0c]} ra={ra}`; enable for about 5 s, then disable (it runs for every animated model every frame).
- **Steps**: activate a field spell so that its backdrop (`duel/bg/fmagic%04d.ehp`) animates. Enable the log for 5 s with PPSSPP at 100 % speed and the FPS counter on. If `step` is non-zero, read the float at that address once. *(optional)* Repeat the same 5-second log on a free-roam map and in the shop's pack screen.
- **Record**: per distinct `inst`: number of calls and the first and last `fc`; `step` (null or the float); the `ra` (backdrop, cut-in, HUD); the FPS shown.
- **Expected**: one call per instance per frame-counter tick, with a null step (1.0) or a constant float; the backdrop rate is then E7's main-loop rate × step (30 or 60 per second). Report each `ra` group separately, since the step may differ per user.

### Block F-4: around duels in free roam (differential saves 3, 4, 5)

#### F11. Duel record, record table and recipe unlock

- **Hypotheses**: a win adds to the totals `0x10f10`, `0x10f1c`, the streak maximum `0x10f20` and the opponent's row `0x10f2c + 8c`; record values `0x113a4 + 4i`, bits `0x11468 + i` and the bonus bytes `0x1149c`/`0x114f0`/`0x1155c` reflect the bonuses shown after the duel; a loss updates the loss fields and streaks; a tag win also updates the second opponent's row; the first win against a character whose deck was not unlocked sets bit 0 and the owner bits of that recipe's `u16` at `0x10b74 + 2r` (`save.md`, experiments 3–5; high for the duel record, medium for the record table).
- **Steps**: in free roam, save (`F11-a`); win one single duel against a known character `c` (note `c` and the bonuses on the result screen); save (`F11-b`). Lose one duel; save (`F11-c`). Win one tag duel; save (`F11-d`). Use an opponent whose deck you have not unlocked for the first win (the deck list in the editor shows which), or note that it was already unlocked.
- **Record**: per pair the changed offsets (old → new); the opponent ids; the bonuses shown (names in words, no text dump).
- **Expected**: the fields listed in the hypothesis and nothing else outside the frame counter, the calendar and DP; the tag win changes two opponent rows.

### Block F-5: D2 (sixteen links from simultaneous triggers)

#### F12. D2 of Session D

Run D2 exactly as written in Session D (staging with S1, Card Destruction `0x12d5`, Broww `0x1966`, Pot of Greed `0x12ec`; breakpoint at `0x09c329e8` with condition `[0x09e28e48] >= 2`). It was not run in Session D. Record into the D2 rows of the Session F table below (they replace the empty D2 rows of the Session D table).

**Session F results**

| Check | Recorded | Expected | Pass? | Notes |
| --- | --- | --- | --- | --- |
| F1 first player draws on turn 0 (single duel)? | | (open) | | side that went first |
| F2 Dian Keto: cmd, LP, pc | | `0x23 a=0x3e8`, +1000, body | | |
| F2 Ookazi: cmd, LP, pc | | `0x8024 a=0x320 b=0`, −800 | | |
| F2 any LP write without a command? | | no | | `0x25` seen? |
| F3 direct attack: steps, damage record | | target 5, amount = ATK | | step 8 present? |
| F3 piercing: damage record, cmd | | `ATK − DEF` to the CPU, `b=1` | | |
| F4 ATK readings 3–6 vs screen | | equal | | records |
| F4 temporary record kind, key, expiry | | kind 2, `0x1329`, gone | | |
| F5 link 1 `+0x04` bit 1, draw? | | set, no draw | | |
| F6 `cmp` fields: base and trick plan | | as documented | | |
| F6 kept plan vs `v0 & 0x1e`; trick used? | | consistent | | |
| F6 depth / LP across `ai_plan_battle` | | unchanged | | |
| F6 planned `+0x08` vs damage dealt | | equal | | plan block offset ok? |
| F6 `better` winner vs declared target | | same | | |
| F7 interest records | | `0x1c31`-related record | | |
| F8 *(optional)* guard cases | | formula | | edits listed |
| F9 `ddstrtbl` member names, reader pcs | | `_idx`/`_body` read in `rel_duel_draw` | | dict names |
| F10 calls per tick per instance, step, FPS | | 1 per tick, step 1.0? | | per `ra` group |
| F11 win / loss / tag win changed offsets | | as listed in `save.md` | | opponent ids |
| F12 (D2) queued `N`, chain / queue after the sort | | `N` / 16 / `N − 16` | | trigger kinds |
| F12 (D2) sides of links 1–16 | | turn player's first | | |
| F12 (D2) second chain from the remainder | | `N − 16` links | | |
| Edits (S1/S2/S3, E-X1) | | all listed | | |

## Reporting results

1. Fill in the session's results table (copy it from this file). Save it as `docs/verification/results/<yyyy-mm-dd>-<session>.md`, or paste it into a session with the agent. Record values, addresses and card ids only: no screenshots of card art, no memory dumps, no text from the game.
2. Add one line per check: PPSSPP version, CPU core used (JIT, IR interpreter, interpreter) and the savestate name. Savestates themselves stay local.
3. A failed or surprising check is as useful as a pass: write what was seen. The agent then re-reads the code and revises the hypothesis.

The agent then, in the same session:

- Edits the subsystem or format document: the claim's confidence becomes "verified in PPSSPP (`<date>`, results file)". Answered open questions are struck through with the answer, and refuted claims are rewritten.
- Raises registry rows, following the stage definitions in `docs/PROGRESS.md`:
  - **Formats** (`re/formats.csv`, edited by hand): set `verified` when the layout matched live memory in the check. A row can only reach `verified` if its layout is already written down (`documented`). Candidates: `chain_link` (A7), `effect_marker` (A8), `duel_stat_block` and `duel_effect_records` (A6), `duel_turn_state` (A1, A2), `duel_player_block` (A2, A3, A5), `duel_field_slot` (A5, A6), `attack_state`, `battle_record`, `battle_steps` and `battle_damage_record` (A4), `turn_steps` (A1), `summon_record` (A5), `chain_state` (A7, D1), `trigger_queue` (A9, D2), `duel_command_queue` (every session), `tag_waiting_area` (B1), `story_calendar` (C1), `story_runtime_records` (C2), `story_field_state` (C3, C4), `save_player_profile` (C4), `save_data` (C4, C5); from Sessions E and F: `file_index` (E1), `story_field_state` (E11), `field_door_table` (E12), `story_field_save_block` and `story_chapter_table` (E13), `save_pack_records` and `pack_draw` (E16, E17), `save_card_list` (E18), `save_progress_bytes` (E19), `ydq` (E21), `save_minigame_blocks` and `save_record_table` (E23, F11), `ai_battle_plan` and `ai_board_view` (F6, F7), `tgm_model_instance` (F10), `save_duel_record` and `save_recipe_table` (F11). The rows still at `named` are first brought to `documented` from the existing text.
  - **Functions** (`re/functions.csv`): `verified` only for functions that are already `documented` and whose documented behaviour (arguments, return value, side effects) the check exercised. Examples: `duel_core_cmd_enter_phase`, `duel_core_get_phase`, `duel_core_cmd_lp_gain`/`_lp_loss`/`_set_lp`, `duel_core_use_normal_summon`, `duel_core_has_normal_summon`, `duel_core_get_atk`, `duel_core_chain_build_from_triggers`, `duel_effects_mark_used_this_turn`, `ai_mask_hidden_card_id`. Functions still at `named` (`duel_core_next_turn`, `tag_duel_swap_active_duelist`, `duel_core_push_command`, the `rel_story` world functions) are documented first, with the runtime evidence as one of their bases.
- Runs `python -I tools/progress.py --check` and the headline command, and reports what moved.

## Decisions for the maintainer

- **How functions reach `verified` in the registry.** `re/functions.csv` is regenerated by `tools/ghidra/ExportFunctions.java`, which writes only `documented` (from the `DOCUMENTED` tag) or a blank status. A `verified` typed by hand would be lost at the next export. One option keeps the counting rules unchanged: a `re/verified.tsv` list applied as a `VERIFIED` tag in Ghidra, which the export then writes as `verified`. Until a mechanism is chosen, verified functions are recorded in the results files and the documents, and only `re/formats.csv` rows are raised.
Decided on 2026-10-26:

- **Structures without a registry row**: counted. `re/formats.csv` now has a row for every runtime structure and table that the subsystem and format documents describe (player block, field slot, turn/phase globals, step tables, battle and damage records, chain and trigger queues, request blocks, AI blocks, save and world blocks). A row is `documented` only where a document gives a layout table, purpose and evidence; the others are `named`.
- **The 16-link limit**: tested in Session D (D1 responses, D2 triggers) instead of the optional A11.
- **Staging with memory edits**: counts as `verified` under the policy in "Memory edits" (allowed edits only, every edit recorded, observations produced by the game's code).
