# Session E, block E-S results (2026-10-31)

Plan: [`ppsspp-plan.md`](../ppsspp-plan.md), Session E, block E-S. Same boot as E5b: `r = 1`, `S = 0x08aa5798`. No breakpoints, no memory edits. PPSSPP at 100 % speed; its FPS counter showed **30**.

## E7. Frame counter and main-loop rate: pass

- `[S + 0x0c]` read twice 60 s apart (stopwatch): `0x86fb` → `0x8e0b`, +1,808 = **30.1 per second**. The counter counts main-loop frames at 30 Hz, matching PPSSPP's 30 fps and the 2-vblank flip of `system_display_flip` (`field_3d.md`, "Frame timing").
- `E7-a` → `E7-b` (60 s idle in free roam between two saves): `+0x0c` (`0x8e8d` → `0x9719`, +2,188, the wait plus the time spent in the save dialog) and **two runtime character records**: story block record 3 (save `0x16f30` `+0x08`: `0x23` → `0x21`; `0x16f3c` `+0x14`: `1` → `5`) and record 63 (save `0x184bc` `+0x04`: `0x15` → `0x11`; `0x184c0` `+0x08`: `0x21` → `0x1f`; `0x184cc` `+0x14`: `6` → `4`). NPCs walk while the player is idle, and their records hold the live position (`+0x04`/`+0x08`) and a state byte at `+0x14` (new: `world.md` listed the cell at `+0x0c`/`+0x10`, which is the target/spot cell; M).
- `E7-b` → `E7-c` (back to the title, load, save): only `+0x0c` changed. The calendar did not advance.
- `+0x04`–`+0x0b` never changed (zero in all three files).

## E8. Save buffer round trip and unknown regions: pass

Memory just after the `E7-c` save, against the file:

| Value | Memory | `E7-c.bin` |
| --- | --- | --- |
| DP `+0x0fdfc` | 0 | 0 |
| Partner word `+0x16e12` | `0x0023` | `0x0023` |
| Calendar `+0x1a24c` (9 words) | `1 1 5 1 0 0 0 1 1` | identical |
| Frame counter `+0x0c` | `0x9c2a` | `0x97e6` (the memory was read about 36 s later) |

The unknown regions `0x00004` (8 bytes), `0x1b108` (3,332 bytes) and `0x1bf18` (116 bytes) are zero in all five saves of E5 and E7, and none of them appears in any diff.
