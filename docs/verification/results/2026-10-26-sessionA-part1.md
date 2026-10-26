# Session A results, part 1 (2026-10-26)

Plan: [`ppsspp-plan.md`](../ppsspp-plan.md), Session A. Single duel against a CPU, savestate `A1-myturn`. Instrumentation: execute log at `0x09dc07f8` (`cmd op={a0} a={a1} b={a2} c={a3}`) and a write memory breakpoint on `0x09e2d1e8` (`phase write pc={pc} v={[0x09e2d1e8]}`). No memory edits. Note: the write breakpoint fires before the store, so the logged `v` is the **old** value; the new value is the `v` of the next write.

Card ids seen (cardinfo): `0x18be` White Ninja (1500/800), `0x193a` Divine Sword - Phoenix Blade (equip, +300 ATK), `0x18b3` Moai Interceptor Cannons (1100/2000), `0x1962` B.E.S. Tetran, `0x1581` Enemy Controller, `0x1c6c` Chamberlain of the Six Samurai, `0x1237` Megamorph, `0x16a7` Sakuretsu Armor.

## A1. Phase values and the turn sequence: pass

| Turn | Commands (in order) | Phase writes (old → new) | Writer `pc` |
| --- | --- | --- | --- |
| Human, no battle | `0x56`, `0x0b`, `0x0c`, …, `0x0f`, `0x03`, `0x04` | 0→1, 1→2, 2→5, 5→7 | `0x09dbc3ec` (enter_phase), `0x09dbc1f8` (next_turn) |
| CPU, no battle | `0x8002`, `0x800a`, `0x8056`, `0x800b`, `0x800c`, …, `0x800f`, `0x8003`, `0x8004` | 7→0, 0→1, 1→2, 2→5, 5→7 | same |
| Human, with battle | `0x56`, `0x0b`, `0x0c`, …, `0x0d`, …, `0x0e`, `0x0f`, `0x03`, `0x04` | 0→1, 1→2, 2→3, 3→4, 4→5, 5→7 | same |
| CPU, with battle | `0x800b`, `0x800c`, …, `0x800d`, …, `0x800e`, `0x800f`, `0x8003`, `0x8004` | 0→1, 1→2, 2→3, 3→4, 4→5, 5→7 | same |

- Values 0 Draw, 1 Standby, 2 Main 1, 3 Battle, 4 Main 2, 5 End, 7 between turns; 6 never written. Bit 15 of `op` set on every CPU command.
- Real phase writes come only from `0x09dbc3ec` (inside `duel_core_cmd_enter_phase`, `0x09dbc394`–`0x09dbc477`) and `0x09dbc1f8` (inside `duel_core_next_turn`, `0x09dbc184`–`0x09dbc393`).
- A turn without an attack goes Main 1 → End directly (command `0x0f` right after Main 1), as `duel-phases.md` describes.
- **Correction:** the AI look-ahead overrides are written from `0x09d15acc`, `0x09d15b18`, `0x09d1695c`, `0x09d16a00`, `0x09d16e88`, `0x09d18018`, `0x09d186c4`, `0x09d1876c`, `0x09d1a79c` (the plan listed `0x09d1586c`, `0x09d16b38`, `0x09d16b84`, `0x09d54b78`). They write 2/3 (or 3/4 during Battle/Main 2) and restore the value, confirming the temporary-override reading.

## Other checks observed in the same log (partial, to be completed)

- **A3 (LP command):** White Ninja + Phoenix Blade (1800 ATK) attacked face-down Moai Interceptor Cannons (DEF 2000): commands `0x8034` (defender flipped face-up), `0x15 a=0x18be b=0x18b3` (damage calculation), `0x16 a=0xc8` (200), `0x24 a=0xc8 b=1 c=0x18b3` (LP loss 200 for side 0, reason 1 = battle, cause = defender). The 200 = 2000 − 1800 also shows the equip bonus was applied (A6, partial). LP memory not yet read.
- **A4 (battle):** declaration `0x17 a=3 b=0x201` (attacker slot 3), `0x14`/`0x1c`/`0x1d` around the Battle steps; CPU declaration `0x8017 a=2 b=0x300`.
- **A7 (chain):** each activation posts `0x10` (link activated, `a` = slot), `0x11` (resolving), `0x12` (resolved), then `0x38`; a response by the human during the CPU's attack (Enemy Controller in slot 7) produced its own `0x10/0x11/0x12` and `0x8033` (position change of the CPU's slot 2).
- **A8 (once per turn):** the CPU's B.E.S. Tetran effect posted `0x8035 a=0x0202 b=0x0fb6` (attach marker key `0xfb6` to slot 2, kind byte 2) before removing a counter (`0x803b a=2 b=0xffff`) and destroying a spell (`0x30 a=8 …`). Tetran's summon also posted `0x803b a=2 b=3 c=1` (3 counters). Consistent with `chain.md` and `effect-helpers-values.md`.

## A2. Turn side and turn counter: pass

| Moment | `0x09e2d1d8` (turn side) | `0x09e2d1e0` (turn counter) |
| --- | --- | --- |
| Human's third turn, Main 1 | 0 | 4 |
| Following CPU turn | 1 | 5 |

The counter starts at 0 on the first turn of the duel and increases by one per turn (human turns 0, 2, 4; CPU turns 1, 3, 5). Side 0 is the human, side 1 the CPU. The first-turn draw question stays open (needs a log from the very first turn).

## A3. Life Points: pass (amount and storage)

| Address | Value | Meaning |
| --- | --- | --- |
| `0x09e2a528` (side 0, `+0x00`) | `0x1e78` = 7800 | 8000 − 200 reflect damage logged as `0x24 a=0xc8 b=1` |
| `0x09e2b064` (side 1, `+0x00`) | `0x1f40` = 8000 | no damage taken |

LP are a 32-bit integer at player block `+0x00`, the player blocks are `0xb3c` bytes apart, and the battle damage path (`0x15` → `0x16` → `0x24`, reason 1) is the one that changed them. The write itself (`0x24` handler) is still to be watched with a memory breakpoint for the formal check of "only commands `0x23`–`0x25` write LP".

## A5. Normal Summon flag and per-turn reset: pass (one new bit)

Player flags word of side 0 at `0x09e2a648` (player block `+0x120`):

| Moment | Bytes | Word |
| --- | --- | --- |
| Main 1, before the Normal Summon | `00 00 00 00` | `0x00000000` |
| After a face-up Normal Summon | `00 00 33 00` | `0x00330000` |
| Next own turn, after the Draw | `00 00 00 00` | `0x00000000` |

Bits 16 (summon declared), 17 (Normal Summon used) and 21 (a monster was Normal Summoned face-up) are set as `summon.md` describes, and the whole upper half is cleared by the next turn's begin-turn command. **New:** bit 20 (`0x00100000`) is also set by a face-up Normal Summon; its meaning is not documented (open question added to `summon.md`).
