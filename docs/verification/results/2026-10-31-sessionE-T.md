# Session E, block E-T results (2026-10-31)

Plan: [`ppsspp-plan.md`](../ppsspp-plan.md), Session E, block E-T. Log-only breakpoints, no memory edits. First boot: `r = [0x08ac18c0] = 6`, `S = 0x08aa57ac`; after the fresh boot of E2: `r = 1`, `S = 0x08aa5798`. E0: the symbol export `ghidra/title-2026-10-31.sym` matched `rel_title` at the documented base `0x08e9aa00` (618/618 function starts, `tools/modules.py base`), and the word at `0x08e9cc30` is `jal 0x08e9d0e0`.

Standing logs (save dialog modes, `ra` in `BOOT.BIN`):

| Moment | Calls in order |
| --- | --- |
| Boot | autoload (`ra 0x0883eb80`), mode 8 (`0x0883f824`), mode `0x16` (`0x0883f428`) |
| Load from the title menu | mode `0x16` (`0x0883fae8`), autoload (`0x0883fc84`) |
| Save from the title menu | mode `0x16` (`0x08840354`), save (`0x088404fc`) |

Modes 8 and `0x16` are the SDK savedata modes `SIZES` (free-space check) and `GETSIZE` (size of an existing save) of `sceUtilitySavedata`; mode `0x16` runs before every load and save. Mode 7 (`DELETE`) never ran. This answers the open question in `save.md` for modes 8 and `0x16` (high: SDK mode numbers plus the call order).

## E1. File index: pass

- `[0x089218c8..0x089218e0]` = start `0x08e67000`, end `0x08e6f530`, name pool `0x08e71c4d`, `0x119`, `0x08e67000`, ready `1`, building `0`.
- Entries: `(0x08e6f530 − 0x08e67000) / 16` = **2,131**, equal to the 2,131 files of the extracted disc.
- First entry: path pointer `0x08e89fec` → `/PSP_GAME/ICON0.PNG`, LBA `0xd5a0`, size `0x7eb8` (32,440 bytes). It is the alphabetically first path of the disc (upper case sorts `I` before `P`, `S`, `U`).
- Not run: the optional writer breakpoint.

## E2. Opening movie: answered

- Each start: `system_load_movie_modules` from `rel_title` `ra 0x08e9c248`, then `system_movie_play` (formerly `system_movie_create_player`) with `ra 0x0883df30` (a `BOOT.BIN` wrapper, not `rel_title`), `a0 = 0x09fff550`; at the end `system_unload_movie_modules` from `rel_title` `ra 0x08e9c358`.
- **Skip: every button skips the opening** (Cross, Circle, Square, Triangle, R1, L1, d-pad, Start). A skipped run calls no `movie_stop`; the modules are unloaded 4–8 s after the start.
- Played to the end (67 s, 15:42 → 16:49): `system_movie_stop_video` with `ra 0x0882c468` (inside `system_movie_flush_video`), then the unload.
- **Idle on the title screen: a demo duel starts** instead of the opening replaying (attract mode). At that moment the movie modules were loaded again from `rel_title` `ra 0x08eaa264`.

## E3. Title message tables: partly answered

- Every call during the visit came from **`ra 0x08eb9174` with `k = 12`**, once per frame, with `idx` following the menu cursor (`0`, `0x82`, `0x83`, `0x86`, …): a per-frame help or caption line of the title menu reads table 12.
- Communication menu (network mode): one call `idx = 0x15`, `k = 12`, `ra 0x08ea8748`.
- One call with `idx = k = 0xdeadbeef` at `ra 0x08ea5df8` (thread `ehscript`): arguments uninitialised in PPSSPP's sense; to be read in the code.
- The deck menu, database and options screens made no call: they run in other modules. Only 3 of the 25 runtime call sites were reached; the others need the screens that stay in `rel_title`.

## E4. Sound path: answered in part

- `0x08826458` is **not** a sound function: its arguments are a heap handle (`0x08eedfc0` or `0x08acda40`), a size (`0xc0` … `0x500000`) and a flag — a heap allocator (high from the arguments; name to be given from the code).
- Sound effects: `__sceSasSetVoice` (`ra 0x08818b4c`, thread `snd_thread_s`) then `__sceSasSetKeyOn` (`ra 0x08818964`, thread `snd_thread_m`), core `0x0891f900`, voice 0 or 1. Per action one pair; the buffer identifies the sound: cursor move `0x08acdc90` size `0x2e0`, `0x08acdf78` size `0x20b0`, `0x08ad2a28` size `0x1cf0`, `0x08ad0030` size `0xf80`. The game code queues the request to the sound threads, so the play call itself is the queue writer (to be found statically from `0x08818b4c`/`0x08818964`).
- Music: `sceAtracSetDataAndGetID` from `ra 0x08868374` (main thread) and `sceAtracSetLoopNum(id, -1)` from `0x088683ec` and from the sound thread at `0x08871684`: **title music loops forever** (expected).

## E5. Title and option words: hypothesis refuted, options located

- The memory breakpoint on `S + 0x1bf0c` (12 bytes) logged no CPU write while the options were changed; it logged the save copy and reads of the six `u16` by `0x088370d8`–`0x0883716c`. So the three words are **not** the option settings.
- Diff of `E5-a`/`E5-b` (eleven options changed: Tutorial on→off, Message speed slow→normal, BGM 13→14, SE 13→14, Card animation normal→fast, Duel effects on→off, Destiny draw on→off, Activation confirm on→off, Auto chain dialog default→all, Card placement auto→manual, Auto draw off→on): only the frame counter `+0x0c` and the **settings `0x0fe04`–`0x0fe08`** changed: `09 a8 10 0c 0c → 11 10 0b 0d 0d`.
  - Byte 3 and byte 4: `0x0c → 0x0d` = **BGM and SE volume**, stored as shown value − 1 (high).
  - Byte 0 bit 3 1→0; byte 0 bits 4–5 0→1; byte 1 bits 3–4 1→2; options 0, 2, 5 on→off; options 3, 4 off→on; byte 2 bits 1–2 0→1. Which menu entry owns which field needs one option per save (follow-up E5b).
