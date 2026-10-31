# Session E, block E-W results (2026-10-31, part 1)

Plan: [`ppsspp-plan.md`](../ppsspp-plan.md), Session E, block E-W. An older save with 1,568 DP, Monday, time slot 2, partner Jaden (`0x0023`). `r = 0x0d`, `S = 0x08aa57c8`. Log-only breakpoints, no memory edits. Savestate `E-W0`. (Some breakpoints of block E-T were still set and logged too; they are ignored here.)

## E9. `hud_marker` at the sandwich seller: not observed

- Buying one sandwich logged `queue (0x25, 8, 6)` (the seller's sandwich dialogue, group 8 / 6: `world.md`, "Talk"), `dp_add -200` (`ra 0x090e5a54`, `rel_field`) and then `queue (0x12d, 4, 1)` (key 301, group 4).
- **No call** of `world_field_req_hud_marker` (`0x090d87a8`), marker A (`0x090d5fa4`) or marker B (`0x090e5b20`). On screen the seller's balloon showed an item roulette that stops on Cross and hands over the sandwich; no arrow or highlight appeared.
- Reading: the `hud_marker` lines of the seller records are not on this path (a repeat purchase); they may belong to the first-visit explanation. The check stays open; the record to replay is to be chosen from `story.py events` (opcode 50118).

## E10. BGM fade time: pass

Every map change with a new track logged `bgm_fade 0x5dc` (1,500) from `ra 0x08eaa8a4` (`rel_story`), then `bgm_stop` (`ra 0x08eaa8cc`) and `bgm_release` in the same frame. Fade → stop, frame counter at 30 Hz (E7):

| `bgm_fade` fc | `bgm_stop` fc | Frames | Seconds |
| --- | --- | --- | --- |
| `0x1099e` | `0x109cc` | 46 | 1.53 |
| `0x10a9b` | `0x10ac9` | 46 | 1.53 |
| `0x10c98` | `0x10cc6` | 46 | 1.53 |
| `0x108e2` | `0x10910` | 46 | 1.53 |
| `0x116a8` | `0x116d6` | 46 | 1.53 |

The argument is a 1,500 ms fade-out, and the track is stopped and released about 1.5 s later (46 frames, the fade plus one frame of polling).

## E11. Arrival cells: pass

`world_place_player_on_arrival` (`arrival`) ran once per map change, followed by `world_field_request` with `a0 = 9` and a single argument, a pointer (`a1 = 0x09fe91f4`; `a2`/`a3` hold `0xdeadbeef`, unused). Field state `S + 0x1a0e0` after each change (location, previous location, `f32` x, `f32` y, direction), against the arrival table (`world.py tables --table arrival`, cell → `cell · 0.5 + 0.25`):

| Change | Location ← previous | x, y | Direction | Table entry | Match |
| --- | --- | --- | --- | --- | --- |
| Ra Yellow dorm → Slifer dorm outside | 6 ← 16 | 15.75, 14.75 | 3 | location 6, default: cell (31, 29), direction 3 | yes |
| Slifer dorm → room 204 | 14 ← 6 | 5.75, 3.25 | 3 | location 14 from 6: (11, 6), 3 | yes |
| Room 204 → Slifer dorm outside | 6 ← 14 | 7.25, 6.25 | 7 | location 6 from 14: (14, 12), 7 | yes |
| Slifer dorm → store | 3 ← 6 | 15.75, 8.75 | 3 | location 3: (31, 17), 3 | yes |

All four agree exactly, including the per-door rule of location 6 (the arrival cell depends on the room the player comes from). The field state holds the live location, previous location, position and direction (`field-maps.md`, "Arrival cell"; `world.md`, field state). Field request 9 takes one pointer argument.

## E12. Doors at midnight: pass

- Slot 2: room 101's door opened (`door_open kind=0`, a sliding door) and the map changed.
- Slot 7 (light period 4): room 101 did not open and its cell could not be entered; room 204 and the dining hall opened and led in (`door_open kind=0` and `kind=1`, a hinged door). The maintainer confirmed every outcome as expected.
- `world_get_door_cell_target` (`0x090d9cc8`) runs **every frame** with the player's current cell (the log follows the walk cell by cell), not only on a door cell. Note for later checks: **PPSSPP reads numbers in breakpoint conditions as hexadecimal**, so the condition `a0 == 13 || a0 == 15` matched x = 19 and 21 (`0x13`, `0x15`), not 13 and 15; the door-cell part of the log is therefore not the intended filter, and it does not affect the open/closed results.
- The partner's location remark `queue (1, 2, 6)` and `queue (301, 11, 1)` were queued on map entries.

## E13. Chapter stage and step: pass for steps 1–3 (stage advance still to observe)

Named memory edit **E-X1** (savestate `E13-pre`, Monday slot 2, emulation paused): partner points `u16` at `S + 0x0fe52` (`0x08ab561a`) `0x00dc` (220) → `0x03de` (990). Read before: stage/step `S + 0x1a270` = `01 01`, talk-pending word `S + 0x1a394` = 0.

| Moment | Log | Stage, step |
| --- | --- | --- |
| Map entries before the edit | `try_chapter pts=0xdc loc=0x10/0x03 stage=1`, no queue | 1, 1 |
| Sandwich given | `points char=2 delta=+20` (990 + 20 clamped) | 1, 1 |
| End of day, then map entry (location 14) | `try_chapter pts=0x3e8 loc=0x0e stage=1` → `queue (201, 1, 1)`, `advance_step`, write of byte `+0x01` from `0x08eab41c` | **1, 2** |
| Map entry at location 6 | `try_chapter pts=1000 loc=6`, no queue | 1, 2 |
| Map entry at the highlighted location 23 (the island map showed it) | `queue (201, 1, 2)`, `advance_step` | 1, 3 |
| Step-2 record | `queue (201, 1, 21)` twice (the record's continuation), then the chapter duel | 1, 3 |
| Back from the duel (won; `dp_add +0x5e9` = 1,513 DP from `rel_story` `0x08ea33e8`) | `queue (201, 1, 3)` at once, `advance_step` | **1, 4** |

- The points reached 1,000 through the game's own `world_change_char_points` (delta +20 clamped at the stage-1 cap), and `try_chapter` received 1,000 from then on; below the cap it queued nothing.
- Keys `(201, 1, 1)`, `(201, 1, 2)`, `(201, 1, 3)` are Jaden's row (key 201), stage 1, steps 1–3, as `chapter-table.md` predicts; step 2 needed the highlighted location; step 3 was queued right after the duel.
- Not yet observed: the stage-closing `advance_stage` (expected `(2, 1)`).
- **Caution for later sessions:** during the duel, `rel_duel_mgr` occupies `rel_story`'s base `0x08e9aa00`, so the `rel_story` execute breakpoints fired on unrelated duel code every frame (`advance_stage` thousands of times, `try_chapter` and `queue` with garbage arguments). Those lines are ignored here; disable `rel_story` breakpoints before a duel.
- Music: event starts logged `bgm_fade 0x258` (600 ms, `ra 0x08ea23f4`/`0x08ea3a28`) and `0x64` (100 ms, `ra 0x08e9b4a8`): `bgm_fade` takes the fade time in ms at every call site (E10).
