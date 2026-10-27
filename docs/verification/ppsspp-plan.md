# PPSSPP verification plan

Almost everything in `docs/subsystems/` comes from static analysis. This plan is the step-by-step runtime check that turns the hypotheses the port depends on most into `verified` evidence (`docs/PROGRESS.md`). The maintainer runs it in the portable PPSSPP at `external/ppsspp` (Windows, v1.20.x at the time of writing). The agent then updates the documents and registries from the filled-in result tables.

The checks are grouped into four sessions so that each needs as little play as possible:

| Session | Where in the game | Checks | Play time (estimate) |
| --- | --- | --- | --- |
| 0 | Any duel and the free-roam field | M1, M2: module bases and the save-state address | 10 min, then 2 min at the start of every later session |
| A | One single duel against a CPU | A1–A10: phases, turn, draw, LP, battle, summon, ATK/DEF, chain, once per turn, trigger order, AI visibility | 1 duel, about 40 min |
| B | One tag duel | B1, B2: partner swap and tag state | Two turn changes, about 15 min |
| C | Free roam with a partner | C1–C6: calendar, daily pairing, gift points, item counters, DP, partner word | One in-game day, about 20 min |
| D | One single duel against a CPU, with staged hands | D1, D2: the 16-link chain limit and the 16-trigger limit (replaces the former optional A11) | 1 duel, about 30 min |

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
| D1 highest chain count / link number of the last window | | 16 / 15 | | Crows left in hand |
| D1 window or input with 16 links? | | no | | guard region unchanged? |
| D1 resolution order | | 16 → 1 | | |
| D1 several Crows on the same target allowed? | | (open) | | |
| D2 queued `N`, chain / queue after the sort | | `N` / 16 / `N − 16` | | trigger kinds |
| D2 sides of links 1–16 | | turn player's first | | |
| D2 second chain from the remainder | | `N − 16` links | | |
| Edits (S1/S2/S3) | | all listed | | |

## Reporting results

1. Fill in the session's results table (copy it from this file). Save it as `docs/verification/results/<yyyy-mm-dd>-<session>.md`, or paste it into a session with the agent. Record values, addresses and card ids only: no screenshots of card art, no memory dumps, no text from the game.
2. Add one line per check: PPSSPP version, CPU core used (JIT, IR interpreter, interpreter) and the savestate name. Savestates themselves stay local.
3. A failed or surprising check is as useful as a pass: write what was seen. The agent then re-reads the code and revises the hypothesis.

The agent then, in the same session:

- Edits the subsystem or format document: the claim's confidence becomes "verified in PPSSPP (`<date>`, results file)". Answered open questions are struck through with the answer, and refuted claims are rewritten.
- Raises registry rows, following the stage definitions in `docs/PROGRESS.md`:
  - **Formats** (`re/formats.csv`, edited by hand): set `verified` when the layout matched live memory in the check. A row can only reach `verified` if its layout is already written down (`documented`). Candidates: `chain_link` (A7), `effect_marker` (A8), `duel_stat_block` and `duel_effect_records` (A6), `duel_turn_state` (A1, A2), `duel_player_block` (A2, A3, A5), `duel_field_slot` (A5, A6), `attack_state`, `battle_record`, `battle_steps` and `battle_damage_record` (A4), `turn_steps` (A1), `summon_record` (A5), `chain_state` (A7, D1), `trigger_queue` (A9, D2), `duel_command_queue` (every session), `tag_waiting_area` (B1), `story_calendar` (C1), `story_runtime_records` (C2), `story_field_state` (C3, C4), `save_player_profile` (C4), `save_data` (C4, C5). The rows still at `named` are first brought to `documented` from the existing text.
  - **Functions** (`re/functions.csv`): `verified` only for functions that are already `documented` and whose documented behaviour (arguments, return value, side effects) the check exercised. Examples: `duel_core_cmd_enter_phase`, `duel_core_get_phase`, `duel_core_cmd_lp_gain`/`_lp_loss`/`_set_lp`, `duel_core_use_normal_summon`, `duel_core_has_normal_summon`, `duel_core_get_atk`, `duel_core_chain_build_from_triggers`, `duel_effects_mark_used_this_turn`, `ai_mask_hidden_card_id`. Functions still at `named` (`duel_core_next_turn`, `tag_duel_swap_active_duelist`, `duel_core_push_command`, the `rel_story` world functions) are documented first, with the runtime evidence as one of their bases.
- Runs `python -I tools/progress.py --check` and the headline command, and reports what moved.

## Decisions for the maintainer

- **How functions reach `verified` in the registry.** `re/functions.csv` is regenerated by `tools/ghidra/ExportFunctions.java`, which writes only `documented` (from the `DOCUMENTED` tag) or a blank status. A `verified` typed by hand would be lost at the next export. One option keeps the counting rules unchanged: a `re/verified.tsv` list applied as a `VERIFIED` tag in Ghidra, which the export then writes as `verified`. Until a mechanism is chosen, verified functions are recorded in the results files and the documents, and only `re/formats.csv` rows are raised.
Decided on 2026-10-26:

- **Structures without a registry row**: counted. `re/formats.csv` now has a row for every runtime structure and table that the subsystem and format documents describe (player block, field slot, turn/phase globals, step tables, battle and damage records, chain and trigger queues, request blocks, AI blocks, save and world blocks). A row is `documented` only where a document gives a layout table, purpose and evidence; the others are `named`.
- **The 16-link limit**: tested in Session D (D1 responses, D2 triggers) instead of the optional A11.
- **Staging with memory edits**: counts as `verified` under the policy in "Memory edits" (allowed edits only, every edit recorded, observations produced by the game's code).
