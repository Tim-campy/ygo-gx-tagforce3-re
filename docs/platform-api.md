# Platform API map

The contract between the reverse-engineering phase and the 3DS port: every Sony system interface the game reaches, how the game uses it, and what the port has to provide instead. This records the game's use of the libraries, not the libraries themselves. The maintainer made this map a done criterion on 2026-11-04 (`CLAUDE.md`, `PORT-READINESS.md`). 3DS names (libctru, citro3D and so on) are suggestions, not decisions, and no port code exists.

**Basis.** Static only, nothing below was run. Call counts come from an instruction-level census of `BOOT.BIN` and all 36 plain modules: every `jal`/`j` to a registry function of group `sdk` or its `thunk_` stub, attributed to the containing function through `re/functions.csv` (2026-11-04). `lui`/`addiu` pointer pairs were scanned too and add nothing beyond `sceGu` set-up. The behaviour comes from the decompilation dump and capstone reads of the functions named. `rel_cutin_viewer` holds a copy of much `rel_duel_draw` code, so sites in those two modules count twice. `libfont.prx` is encrypted and stayed so. Confidence is H, M or L; anything uncertain is listed under "Open questions".

**Headline.**

- The game calls 346 system functions from 1,479 sites (appendix). 27 of `BOOT.BIN`'s 278 imports are never called. **`rel_duel_eng`, the duel engine, makes no system call at all**: it only calls the game's own exports (H, census).
- **One main loop works.** Game logic has one thread of control, handed between two kernel threads as a coroutine. No game rule depends on thread priorities or on timing between threads, but the code does depend on being suspended in the middle of nested calls (section 1).
- **The game has no time base except the frame.** It ticks at a fixed 30 Hz with no delta time, and under load it slows down rather than skips (section 3).
- Graphics is the largest port item: there is no 3DS equivalent for palette textures, sprites, lines and doubled-alpha blending, and the 480 × 272 screen fits neither 3DS screen (section 2).
- **Six of the eight "no route" cards are not unreachable.** "PSP Game Recognition" (`rel_umd_replace`) grants them for inserting the two earlier Tag Force discs. The other two are not granted by any code on the disc (section 6).
- The game itself makes no HTTP request and uses USB in a module that no menu reaches (section 6). JPEG is only the card album's zoom view.

## Family summary

"Sites" excludes calls made inside Sony's own statically linked code. Risk means risk to the port: **None** (drop it), **Low** (direct replacement), **Medium** (real work, known route), **High** (no direct equivalent, design needed).

| Family | Functions / sites | Who calls | What the game relies on | Port provides (suggestion) | Risk |
| --- | --- | --- | --- | --- | --- |
| `sceKernel` threads and sync | 79 / 372 (all kernel) | `BOOT.BIN`, sub-modules | Coroutine hand-off, file worker, audio threads (section 1) | Main loop + one coroutine; `threadCreate`, `LightEvent`, `LightLock` | Medium |
| `sceKernel` memory, modules | same | Scenes | FPL/VPL pools, one module per scene (section 9) | Static link, per-scene arena on `linearAlloc`/`malloc` | Low |
| `sceGe` / `sceGu` / `sceGup` | 32 / 127, plus 4,219 sites of the game's own `system_ge_write_*`/`draw_*` | `system_ge_*`, `system_display_*` | Layered list per frame, GE state (section 2) | citro3D renderer | High |
| `sceVfpu` | 31 / 525 | `field_3d`, `ui`, `world`, `shop`, `audio` | Plain matrix and scalar maths, no logic effect (section 9) | Plain float code | Low |
| `sceDisplay` | 6 / 13 | `system_display_flip`, movie player | Vblank wait, vcount (section 3) | `gspWaitForVBlank`, `C3D_FrameBegin` | Low |
| `sceCtrl` | 3 / 5 | `system_pad_update`, movie skip | One sample per frame (section 8) | `hidScanInput` | Low |
| `sceIo` | 14 / 80 | `container_*`, audio stream, import scan | Blocking reads, one async stream (section 9) | stdio or `FSUSER` on a worker thread | Low |
| `sceUmd` | 11 / 35 | `container_*`, boot, `rel_umd_replace`, `rel_quiz` | Drive-ready bit 0x20 (section 9) | Report "ready" | Low |
| `sceUtility` | 23 / 109 | Save tasks, OSK, netconf, viewer | Dialog state machines (section 7) | In-game UI, `swkbd`, `FSUSER` | Medium |
| `sceMpeg`, `sceDmac` | 26 / 31 | `system_movie_*` | Blocking playback of 73 movies (section 9) | Converted video; hardware decode only on New 3DS | High |
| `sceSas` | 18 / 24 | `audio_sas_*` | 32 PS-ADPCM voices, 256-sample grain (section 9) | `ndsp` or a software mixer | Medium |
| `sceAtrac` | 9 / 12 | `audio_mixer_thread`, `audio_start_atrac_voice` | Stream decode (section 9) | Offline conversion to a 3DS-friendly codec | Medium |
| `sceAudio` | 6 / 12 | `audio_*` | One blocking stereo output (section 9) | `ndsp` wave buffers | Low |
| `sceFont` | 9 / 11 | `system_font_*` | Firmware font glyphs and advances (section 4) | Own font or `fontGetSystemFont` | Medium |
| `sceCcc` | 5 / 14 | Save SFO, name entry, debug printf | UTF-8/UTF-16 only on real paths (section 4) | Nothing (or 20 lines of UTF-16 code) | None |
| `sceGzip`/`sceDeflate` | 2 / 12 | Bust-ups, TGMT animations | Whole-buffer inflate (section 5) | Inflate at install time, or zlib | None |
| `sceJpeg` | 6 / 6 | `rel_cardalbum` zoom only | 512 × 512 card art (section 6) | Pre-decoded textures, or a JPEG library | Low |
| `sceHttp`/`sceHttps`/`sceSsl`, `sceNetInet`/`Apctl`/`Resolver` | 15 / 15 | `rel_html_view` only | Stack start-up for Sony's browser (section 6) | Nothing | None |
| `sceUsb` | 4 / 8 | `rel_usb_connect` only | Not reachable (section 6) | Nothing | None |
| `sceNetAdhoc*`, `sceNet`, `sceWlan` | 41 / 59 | `system_adhoc_*`, `system_net_*` | Link play only (`system.md`) | Out of first scope; UDS later | Low |
| `sceImpose` | 2 / 4 | Boot, language change, swap | Home overlay language, UMD popup | Nothing | None |
| `sceRtc` | 2 / 3 | RNG seed, deck save stamp | Seed, wall clock for deck dates | `osGetTime` | None |
| `scePower`, `sceKernelPowerTick` | 2 / 3 | Boot, movie | Suspend flags, anti-idle (section 9) | `aptHook` | Low |
| `sceOpenPSID` | 1 / 1 | `save_init_new_game` | 16 bytes stored in the save | Zero fill | None |

## 1. Threads

### The real model

Priorities are PSP priorities: a lower number runs first.

| Thread | Entry | Priority | Stack | Created by | Lifetime |
| --- | --- | --- | --- | --- | --- |
| `snd_thread_main` | `audio_mixer_thread` `0x08871198` | `0x10` | `0x3800` | `audio_init` | Forever. Paced by the blocking audio output: one 256-sample grain, 5.8 ms |
| `snd_thread_seq` | `audio_sas_voice_thread` `0x0886ffe4` | `0x11` | `0x1000` | `audio_init` | Forever, in lock step with the mixer through event flag `SndSeqEvt` |
| `user_main` | `system_user_main_thread` → `system_main` | `0x20`, then `0x31` | 64 KiB | `system_module_start` | Forever; attributes `0x80004000` (user, VFPU) |
| `ehscript` | `system_scene_thread` `0x0881d028` | `0x32` (caller + 1) | `0x6000` | `system_scene_init` | Forever. All scene code runs here |
| ehfile (`0x0889eda0`) | `container_file_thread` `0x0881dba0` | `0x6f` | `0x2000` | `container_init_file_thread` | Forever. File reads and module loads |
| `YgAdhocMsgSendRecvThreadFunc` | `system_net_msg_thread` | `0x31` | `0x2000` | `system_net_msg_init` | Link play only, woken every vblank |
| movie `soundThread`, `displayThread`, `readThread` | `system_movie_*` | `0x3d`, `0x3e`, `0x40`; caller drops to `0x3f` | | `system_movie_play` | One movie only |
| `USBPSPCommSampleThread` | `system_usb_link_thread` | `0x20` | `0x1000` | `system_usb_start_link` | Unreachable (section 6) |

No other thread exists: `sceKernelCreateThread` has exactly these 10 call sites. Sony's dialogs create their own threads from the priorities the game passes (`0x10`–`0x13` or `0x32`–`0x35`).

**The scene hand-off is a coroutine (H).** `system_scene_run_slice` (`0x0881cf00`), called from the main loop:

```
self_id = sceKernelGetThreadId();        // stored at 0x08920c44
sceKernelResumeThread(ehscript);
sceKernelSleepThread();
sceKernelSuspendThread(ehscript);
```

The scene runs until it calls `system_wait_frame` (`0x0884c6b8`), which steps the random generator and calls `sceKernelWakeupThread(0x08920c44)`. Because `user_main` (`0x31`) outranks `ehscript` (`0x32`), the wake-up switches at once and `user_main` suspends `ehscript` inside that call. `system_wait_frame` returns only at the next slice. This settles the old question of who sleeps on `0x08920c44`: the main thread. It is the scene that wakes main, not the other way round as the function's old comment suggests.

So there is exactly one logical thread: `ehscript` and `user_main` never run game code at the same time, and the priority gap is what enforces it. `system_wait_frame` has 164 call sites, many deep inside nested calls (47 in `rel_story` alone, for example `dialogue_show_talk_line` and `audio_stop_bgm`), so scene code is written as straight-line code that blocks for a frame.

**Main loop order** (`system_main`, `0x08833734`; frame N):

1. `system_rand_shifted()`, result unused: one step of the random stream per frame.
2. `sceKernelPowerTick(0)` when any input is held (pad `+0x18`).
3. `system_scene_run_slice`: scene update up to its next `system_wait_frame`.
4. `system_run_frame_services`: play-time counter (state `+0xc`), loading overlay, duellist voice queues, `audio_update_frame`.
5. `system_scene_run_frame`: the scene's frame callback, on the **main** thread (usually the drawing).
6. `system_net_api_update`.
7. `system_end_frame`: `system_display_flip`, `system_ge_submit_frame`, `system_pad_update`, in that order.
8. `system_check_soft_reset`.

The pad sampled at the end of frame N is what the slice of frame N + 1 reads. The list built in frame N is submitted at its end and runs on the GE while the CPU works on frame N + 1 (section 3).

### Synchronisation objects

| Object | Users | Purpose |
| --- | --- | --- |
| `ehfile_sema` (1), `ehfile_queue` (0–32) | `container_read_async`, `system_queue_module_load`, file thread | 32-slot request ring |
| `SndSema`, `SndSeqSema`, `SndAtracDecodeSema`, `SndLoadSema` | Audio API calls and the two audio threads | Protect sound objects, voices, decoders and banks |
| Event flag `SndSeqEvt` | Mixer and sequencer | Bit 1 starts a sequencer pass, bit `0x80` ends it, once per grain |
| Semaphores and event flags of the movie player | Movie threads only | Sony sample structure; `system.md` lists what is stubbed out |
| Message box `Mevent` | `system_adhoc_*` | Matching events, polled once per frame |
| Callbacks `EXIT_CALLBACK`, `POWER_CALLBACK` | Registered in `system_main` | Run inside `sceDisplayWaitVblankStartCB` on the main thread |
| UMD callback | `rel_umd_replace` only | Disc change |
| VBLANK sub-interrupt handlers | Net (wakes the message thread), movie | Interrupt 0x1e |
| `sceKernelCpuSuspendIntr` | `system_malloc_lock`, atexit, module reent list | `malloc` is thread safe by masking interrupts |

There are no lightweight mutexes, and game logic takes no semaphore: the scene only meets them inside audio and file API calls.

### Does logic depend on order, priority or blocking waits?

| Question | Answer | Basis |
| --- | --- | --- |
| Between threads | No, apart from the hand-off itself. Scene and frame callback are strictly sequential; audio threads touch only sound state under semaphores | Thread table, step order above |
| Priorities | Only to make the hand-off immediate. A port with no second thread does not need them. The mixer must keep running while the game is busy, so it needs its own thread or a callback | `system_scene_run_slice` |
| Blocking waits | Yes, in one sense: `system_wait_frame` is a blocking wait at any call depth. Module and file loads loop on it (`system_load_file_blocking`) | 164 sites |
| File completion | Callbacks run **on the file thread** (`callback(arg, result)`, repeated until it returns non-zero). They set flags that the scene polls, so the only visible effect is how many frames a load takes. A port should deliver them on the main thread at a fixed point | `container_file_thread` |
| Sound completion | Yes, and the port must honour it: some scenes spin until a sound's status reaches 0, for example `audio_change_bgm_track`, `audio_stop_bgm`, `audio_play_island_map_bgm`, `shop_is_clerk_voice_playing`. Status must really fall to 0, even with sound disabled, or those loops hang | `audio_get_sound_status` callers |
| Random numbers | The stream advances once per frame and once per `system_wait_frame`, so any change in frame count changes later draws. It is seeded from the RTC at boot and again when the scene thread starts, so nothing depends on a reproducible sequence (link duels use an explicit seed) | `system_scene_thread`, `system_seed_rand_from_rtc` |
| Wall clock | `sceKernelGetSystemTime*` only times the ad-hoc layer. `sceRtc` only seeds and stamps. no game caller of `clock`/`time` was found | Census |

### Verdict

**The port can use one main loop.** It needs:

- The ordering above, one tick = one 30 Hz frame.
- A way to suspend scene code at `system_wait_frame`: either a stackful coroutine (a hand-rolled ARM context switch, or a second libctru thread that ping-pongs on `LightEvent` and never runs alongside the main one) or a rewrite as state machines. A clean reimplementation can mix them; the frame boundaries are the behaviour to keep.
- An audio producer that keeps running independently (`ndsp` callback or a thread on the application core).
- A file worker is optional. Synchronous loads are correct but stall the frame, and the original streams during animations, so a worker with main-thread completion is the better fit.

Movies are modal: `system_movie_play` runs its own loop and the main loop does not advance until it returns. Risk: Medium, for the coroutine and for the sound-status contract.

## 2. Graphics

### Structure

- **One frame, one list.** The game writes GE words directly into a display-list buffer (`0xeb000` bytes, config word 4 of `0x088a0154`) split into two halves, one per frame. Each frame has 16 layers linked in index order at submission with BASE + JUMP (`system_ge_link_layers`). `system_ge_select_layer` has 604 sites. Literal layers seen: 4 (102), 5 (97), 8 (71), 0 (52), 1 (42), 2, 7 (34 each), 3 (28), 9 (11), 10 (5), 6 (2). Layers are **draw order**, independent of the order in which code runs, so the port needs an equivalent bucket sort.
- libgu is used only as a thin layer: `sceGuStart`/`Finish` to open and close a list, `sceGuSendList`, `sceGuSwapBuffers`, `sceGuSync`. Everything else goes through the game's own writers at `0x088297c4`–`0x0882b6cc` (`system.md`, `field_3d.md`).
- A static list `0x0889eed0` re-sends the full GE state every frame with the parity-dependent buffer words patched (`system_ge_reset_state_list`), after `sceGeListSync`. Each frame therefore starts from known state.
- `system_gum_*` is a matrix stack with the libgum API, 4 stacks, about 2,400 sites. `system_gum_draw_bezier`/`spline` exist with no caller.

### VRAM layout (2 MiB EDRAM, translation `0x800`)

| Offset | Size | Use |
| --- | --- | --- |
| `0x000000` | `0x88000` | Frame buffer 0: 512 × 272 × 4, PSM 8888 |
| `0x088000` | `0x88000` | Frame buffer 1 |
| `0x110000` | `0x44000` | Depth buffer, stride 512, 16 bit |
| `0x154000` | `0x4000` | Gap |
| `0x158000` | to end | `system_vram_*` bump allocator (`field_3d_gim_upload_to_vram`: exported, no caller, so unused) |
| `0x160000` | up to `0x20000` | Scratch target: 128 × 256 card faces, 128 × 128 renders |
| `0x164000` | | 256 × 256 target (1 site) |
| `0x174000` | to `0x1fc000` | 512-wide RGBA8 scratch: Fusion/Synchro vortex, swirl transition, keyboard backdrop |
| `0x1f0000` | `0x10000` | Two 64 × 32 ramp textures (PSM 5650 and 4444), overlapping the end of the scratch area |

The port has no EDRAM and needs named render targets instead. Effects that overlap do not run together.

### Fixed state from `system_display_init`

480 × 272 viewport in a 512-stride buffer, PSM 3 (RGBA8888), offset `(0x710, 0x778)`, viewport centre 2048. **Reversed depth:** range 50000..10000 at boot, and `0xffff..0` in 15 scene set-ups, with depth function `GEQUAL` (7) as the rule: 24 of 28 literal sites plus every first material layer. Overlay layers use `EQUAL`. Front face CCW.

### State census

Literal arguments in code (`rel_cutin_viewer` excluded) and the state stored in all 585 TGMS models.

| State | What the game uses | 3DS (suggestion) |
| --- | --- | --- |
| Enable bits | Alpha test, depth, scissor, stencil, blend, cull, fog, clip, texture, lighting, lights 0–3, patch cull. Dither, colour test, logic op and `FRAGMENT_2X` are only ever disabled (H for literals) | All present, or not needed |
| Blend, code | `ADD`, `SRC_ALPHA`, `1-SRC_ALPHA` 199 of 224; additive with `FIX` white 11; other `FIX` combinations 9. Every code case fits a PICA blend with one constant colour | `C3D_AlphaBlend`, `C3D_BlendingColor` |
| Blend, models | 939 blended layers in 41 combinations. **25 layers use doubled-alpha factors** (GE 6 and 9); PICA has none. 5 further layers use two unrelated fixed colours | Pre-scale alpha in a combiner stage, or approximate. Listed per file with `tgm.py` |
| Alpha test | `GREATER 0` (67) in code; `GEQUAL n` in models | `C3D_AlphaTest` |
| Stencil | Frame buffer alpha **is** the stencil on PSP. Used for shadow volumes (`rel_field`, INCR/DECR z-pass, then fill where stencil > 0 with `0x80000000`), map stencil volumes, cut-in masks (`EQUAL 0xff`), UI clipping (`ui_ehf_draw_instances`, LP panel) | D24S8 has a real stencil, which removes the aliasing. Check any draw that reads destination alpha |
| Texture function | `MODULATE` 171, `ADD` 24, `REPLACE` 13, `DECAL` 3 literal sites; all models are `MODULATE` | `C3D_TexEnv`, 6 stages |
| Texture filter | Nearest 390, linear 59, mixed 9. No mipmaps (`GIM` has one level) | Direct |
| Texture wrap | Repeat in all models; clamp in UI | Direct |
| Texture matrix | UV scale and offset per layer, animated by TGMA | Vertex shader uniform |
| Texture map mode | Mode 2 (environment map), lights 2/3 or light 0 (143 layers, type 1) | Compute UVs in the vertex shader |
| Lighting | 4 GE lights, material colours, ambient, specular | Vertex shader, or `C3D_LightEnv` (per-fragment, different look) |
| Fog | Linear, near/far/colour from `-etc` tracks; used by backdrops | `C3D_FogLutBind` (needs a LUT per near/far) |
| Skinning | 8-bone palette per batch, 329 of 585 models | Vertex shader; 8 × 3 `vec4` uniforms fit |
| Morph | Weight writer exists; no model sets a morph count (`tgm.md`) | Not needed |
| Vertex types | 24 in models; through mode `0x800102`, `0x80011c`, `0x80011e` for 2D | Convert offline to float or s16 attributes |
| Primitives | Models: triangles 23,571, strips 12,238. Code: sprites (1,186 sprite helper sites + 16 arrays), strips, **lines** (14 array sites: menu separators, list stripes, card frames) | Quads and thick lines built on the CPU or in a geometry shader |
| Render to texture | `system_ge_set_render_targets` and `system_ge_bind_back_buffer`, 28 sites each | `C3D_RenderTarget` |
| Copy image | 5 sites: frame to `0x174000` (swirl, keyboard backdrop) | `GX_DisplayTransfer` or a render target |
| Scissor | 75 sites | `C3D_SetScissor` |

### Textures

14,098 GIM files (`gim.md`): 14,009 palette images (index8 8,761, index4 5,248), 66 RGBA8888, 23 DXT1. 13,499 are swizzled in PSP tiles. Largest side 512; one image is 97 × 181.

### No direct 3DS equivalent

| PSP feature | Where | Port route | Risk |
| --- | --- | --- | --- |
| **Palette textures (CLUT)** | 99 % of images, including 201 with alternative palettes (hair colours) and 5 nine-frame sets | Expand at install time. `gim.py` already writes every plane as RGBA PNG. Size grows 4–8×: use ETC1/RGBA4 where it looks acceptable, keep hot sets resident | High (memory) |
| 480 × 272 screen | Everything 2D is placed in through-mode pixels | Top 400 × 240, bottom 320 × 240: the port redesigns the UI for two screens (`ui.md`) rather than scaling (0.83 × 0.88 would leave card text unreadable) | High (design) |
| Sprite primitive | All 2D | Two triangles per sprite | Low |
| Line primitive | Menu separators, list stripes, card frames | Thin quads | Low |
| Doubled-alpha blend | 25 model layers | See above | Low |
| Two unrelated fixed blend colours | 5 model layers (pairs that sum to white fit one constant) | Approximate | Low |
| DXT1 | 23 images | Decode offline | None |
| PSP swizzle | Most images | Offline; PICA needs its own 8 × 8 Morton order | None |
| Direct GE list writing | Whole engine | Port's draw API with layer buckets | Medium |
| Reading the frame as a texture | Vortex, backdrop swirl, keyboard backdrop | Render the scene to a texture first | Low |
| 16-bit depth, reversed | Whole 3D | Any depth format; keep `GEQUAL` or flip the range | Low |
| CPU writes into EDRAM | Movie frames, `memset` after a movie | Not needed | None |

Texture sizes must be powers of two between 8 and 1024 on PICA; the 97 × 181 image needs padding. Effect recipes that depend on these are in `field_3d.md`.

## 3. Frame timing

- The boot configuration sets 30 fps (word 6 of `0x088a0154`). `system_set_frame_rate` has no caller, so 30 is fixed. `system_get_frame_rate` has 3 sites, all UI scroll speed. Pad repeat is 15 and 4 frames at this rate.
- `system_display_flip` (`0x08822d10`), once per frame:

```
sceGuSync(0, 0);                        // previous frame's list finished
if (fps == 30) {
    if (vcount - last < 2) sceDisplayWaitVblankStartCB();
    last = vcount;                      // stored before the final wait
}
sceDisplayWaitVblankStartCB();
pre-swap hook 0x089229b0 (never set: its setter has no caller);
sceGuSwapBuffers(); sceGuSync(0, 0);
frame_counter++;                        // 0x089229b4, bit 0 = buffer on screen
system_ge_reset_state_list();
```

- **Cadence.** With `last` read before the final wait, a frame gets the full two vblanks (33.4 ms at 59.94 Hz). The sequence is swap at `L + 1`, then `L + 3`. A frame still running at `L + 3` swaps at `L + 4`.
- **Under load.** The late frame costs one vblank. Nothing skips: the following frame is still one logic tick, and the game simply runs slower (H, from the code; the frame rate on a real console is not measured). There is no delta time, no catch-up and no frame skip. All durations are frame counts (fades, turn timer, 0xe10-frame quiz clock, watchdogs). The GE runs one frame behind, so both CPU and GE must fit in the frame.
- **What the port must do.** Run logic at a fixed 30 ticks per second. Do not tie it to 60 Hz: animation speed, music cues, input repeat and the play-time counter (state `+0xc`, one per frame) all assume it. 3DS vblank is about 59.8 Hz, so two vblanks per tick matches. Rendering may be decoupled, but interpolation is not needed for fidelity.
- The accumulated-hcount reads (`0x089229a8`, `0x089229ac`) are a profiler; nothing reads them.
- `system_get_frame_timing` (229 sites) returns the frame counter for blink phases and buffer parity.
- Movies use their own clock: `sceDisplayGetFramePerSec`, 90 kHz timestamps, and frames dropped when late (`system.md`).

## 4. Text

**Verdict: `sceCcc` is not on a data path the port needs (H).** All game text is UTF-16LE on disc and in memory.

| Function | Sites | Use | Port |
| --- | --- | --- | --- |
| `sceCccUTF16toUTF8` | 6 | `save_fill_sfo_param` (4), `save_start_msg_dialog`, `system_show_net_text_dialog`: text handed to Sony's dialogs | Gone with the dialogs |
| `sceCccUTF8toUTF16` | 1 | `save_init_new_game`: system nickname into the save, at most 8 units, `$` doubled | Read the 3DS user name (UTF-16 already), keep the `$` rule |
| `sceCccStrlenUTF16` | 1 | `duel_core_tutorial_escape_text` | `u16` length |
| `sceCccSJIStoUTF16` | 5 | `system_font_printf*` (4), `world_field_debug_init` | Not needed |
| `sceCccSetTable` | 1 | `system_font_reset_ccc_table`, always `(0, 0)` | Not needed |

Shift-JIS only reaches `system_font_printf`, whose 60 sites are all in debug tools (`rel_debug_menu`, `rel_labo`, `rel_cutin_viewer`, `rel_movie_viewer`), and the field debug mode. `sceCccSetTable(0, 0)` leaves the JIS table null, so `sceCccSJIStoUTF16` as called here reads `*(u16 *)(jis * 2)`: the path can't convert anything correctly and was not exercised in retail play (H for the code, disassembly at `0x08845768`).

**Tools.** Shift-JIS is handled offline, as `cp932`, in `ehp.py` (member names), `ehf.py`, `iso9660.py`, `tgm.py`, `exe_tables.py` and `tutorial.py` (`.ydq` set-ups and `tuto_text_j.bin`). A strict sweep of the disc on 2026-11-04: all 27,436 EHP member names and 4,142 TGM names are ASCII; all 50 `.ydq` files hold non-ASCII comments and decode and re-encode byte for byte. The `*-ptrs.txt` members are binary pointer lists, not text. UTF-16 is covered by `strtbl.py`, `story.py`, `cardinfo.py`, `decks.py`, `tutorial.py`, `save.py`.

Only one gap existed: `.ydq` was the only tested non-ASCII path, so the name decoders could break unnoticed. `test_ehp.py` and `test_tgm.py` now cover non-ASCII names. No encoding bug was found.

**Font** (`sceFont`, 9 functions, all under `system_font_*`). `system_font_init` opens the default font and, through `sceFontFindOptimumFont`, a 20 × 20 Latin font (style language 2, M), used for characters below `0x2300` flagged in `0x08879220`; missing glyphs show U+25A1. Glyphs are rendered on demand, 4 bpp into a 256-slot LRU cache. The font data lives in the console firmware, is not on the disc and must not be taken from it. The port brings its own font (`PORT-READINESS.md`), with the advance metrics, `$` codes and line-break rules of `system.md`. The 3DS shared font (`fontGetSystemFont`) is a possible source; its metrics differ, so word wrap will not match, which matters little as the UI is redesigned anyway.

## 5. Decompression

**Verdict: the tools cover every path (H).** `sceDeflateDecompress` is only reached from `sceGzipDecompress`; no game code inflates raw deflate.

| Call site | Data | Tool |
| --- | --- | --- |
| `field_3d_set_tgmt_data` (`BOOT.BIN`) | `.tmt.gz`, `.vtmt.gz` members bound as TGMT | `tgm.py`, `ehp.py -z` |
| `field_3d_cutin_start_motion`, `field_3d_cutin_load_voice_anim` (`rel_duel_draw`, `rel_cutin_viewer`) | Cut-in motion and voice animation, into a `0x10000` buffer | `tgm.py` |
| `container_gzip_decompress` ← `world_field_portrait_loaded`, `ui_charalist_get_bustup_ehf` | `field/bustup/*.ehp.gz` | `ehp.py -z`, `read_file` |

Sweep of 2026-11-04 over all loose files and archive members (`.pmf`, `.cip`, `.prx`, `psp_snddat.bin` excluded, as their formats are known and not gzip): 8,789 gzip members (all TGMT, all `.gz`-named) and 78 gzip files (all EHP), 8,867 of 8,867 inflate with valid CRC and `ISIZE`. No gzip stream hides under another extension. This matches `ehp.md`.

The game ignores the CRC and sizes the buffer from `ISIZE` (`container_gzip_get_size`) or a constant. Port: inflate at install time, so nothing is needed at run time; otherwise zlib or a small inflate.

## 6. Network and peripherals

### What each one serves

| API | Caller | Menu entry | Feature | Port |
| --- | --- | --- | --- | --- |
| `sceHttp*`, `sceHttps*`, `sceSsl*`, `sceNetInet`, `sceNetApctl`, `sceNetResolver` | `rel_html_view` only, one call each | Database → "Go to the Yu-Gi-Oh! website" (item 7) → save check (state `0x29`) → state `0x2a` → scene `0x0e` | Starts Sony's **HTML viewer** at `http://www.konami.jp/gs/game/yugioh_tf3/dleu/`, with the download directory set to the game's save folder. **The game sends no request itself:** no `sceHttpCreate*`, `sceHttpSendRequest` or read is imported; the imports only initialise the stack and save cookies | Drop the screen |
| `save_import_*`, `sceIoDopen`/`Dread` | `rel_title`, `rel_limitlist`, `rel_recipeviewer` | Database → "Downloaded Data" (item 8, state 6); deck lists; limit list | Reads `.YGC`, `.YGR`, `.YGL` files from the save folder (`docs/formats/import-files.md`). This settles the meaning of the `ms_import` records | Optional: read such files from the SD card |
| `sceUsb*`, `sceIoDevctl("usbpspcm:")`, utility module `0x200` | `rel_usb_connect` only | **None** | See below | Drop |
| `sceJpeg*` | `rel_cardalbum` only | Database → Card Album, zoom view | Decodes the 512 × 512 art of `cardj_a.cip` to YCbCr, 32 lines per frame to RGB | Pre-decode, or decode on the fly |
| `sceUmd*` extras, `sceIoOpen("umd1:")`, `sceImposeSetUMDPopup` | `rel_umd_replace` only | Database → "PSP Game Recognition" (item 6) → state `0x28` → scene `0x1b` | Disc swap reward (below) | Replace with a port rule |

There is no camera: no `sceUsbCam` or similar is imported. `sceJpeg` is only card art. The `Mjpeg` names are the Sony API's name for still decoding.

**USB is dead code in this build (M–H).** Title state `0x27` is the only way into scene `0x17`, and nothing sets it: the state appears only in `ui_title_enter_state`'s switch, all seven `li 0x27` in `rel_title` are unrelated, the one computed request is `0x1b + item` for items 0 and 1, and no other module names scene `0x17`. The EU database menu has no USB item. Its driver string is `ULJM05373`, the Japanese product id, so this is presumably a Japan-only feature left in the module. Reward if the port wants to keep it: 10,000 DP (`0x2710`, `addiu a0, zero, 0x2710` at `+0x1d70`, which answers that open question in `rel_usb_connect.md`), progress flag `e8` bit 1 (read only by this module) and characters `(3,1) (4,2) (6,1) (6,2) (0x14,1) (0x21,1)` from table `+0x7064`.

### The eight cards with no route

`PORT-READINESS.md` and `packs.md` had listed `3752`, `3763`, `3787`, `3789`, `3790`, `4998`–`5000` as having no route. That was wrong for six of them: `system_umd_replace_grant_rewards` (`+0x1cbc`) and `system_umd_replace_add_bonus_rewards` (`+0x2430`) grant them. Reward entries are `id << 3 | count`.

| Disc inserted | First-time reward | Flag |
| --- | --- | --- |
| Kind 2: ULJM-05151, ULUS-10136, ULES-00600 (first Tag Force) | **5000** The Winged Dragon of Ra, **3787** Satellite Laser X-06S, 4861, 10,000 DP | `+0x1c0e9` bit 7 |
| Kind 1: ULJM-05260, ULUS-10302, ULES-00925 (Tag Force 2) | **4998** Obelisk the Tormentor, **3763** Plasma Warrior Eitom, 7349, 10,000 DP | `+0x1c0ea` bit 0 |
| Both claimed (whichever comes second) | **4999** Slifer the Sky Dragon, **3790** Berserker Soul, 4354 | |
| Any other disc | One random card, 3 copies, once per disc; never one of the 8 or `6989` | |

These flags also unlock shop packs (`shop_update_pack_unlocks`), gallery items and characters.

**`3752` Miracle Contact and `3789` Toon Kingdom** appear in no grant. Every code and data hit for them is an effect check, an AI rule, an album special case or an exclusion list (`rel_umd_replace`, `rel_blackjack`, `rel_quiz`, `rel_underground`, `rel_password` all exclude the same eight plus `6989`). Two routes remain, both needing outside data: a `.YGC` download, which accepts any valid card id and gives three copies, or a wireless gift from another console (`ui_title_update_wireless_card_gift`, same flag and three copies). Which of them Konami used cannot be settled from the disc (L for download as the intended route). The port decides how to grant all eight.

### Ad-hoc

`sceNetAdhoc*` is documented in `system.md`: link duels, card trade and gifts. Out of first scope. Nothing in single player uses it except that `system_net_api_update` runs every frame and does nothing while inactive. Later: UDS.

## 7. Save and system dialogs

`sceUtility` carries five dialogs. They all use the Sony pattern `InitStart` → `Update` while status is 2 → `ShutdownStart` at 3 → done at 0, with `sceGuSync(0, 0)` first, on the drawing path. The port needs none of these utilities, only the flows.

| Dialog | Game code | Purpose | Port |
| --- | --- | --- | --- |
| `sceUtilitySavedata*` | `save_start_*`, `save_run_*_task` (`save.md`) | Modes used: 0 autoload, 1 autosave, 3 save, 8 sizes query, plus delete and get-size. One file `DATA0`, buffer `0x20000`, state `0x1c0ec` bytes, SFO text and icons | Write the state to the 3DS save archive or SD |
| `sceUtilityMsgDialog*` | `save_start_msg_dialog`, `system_show_net_*` | Error codes and text | In-game message box |
| `sceUtilityOsk*` | `ui_start_osk_input` (5 modules), `ui_title_start_osk` | Name entry, deck names, up to `0x18` characters, `$` doubled in both directions, soft reset inhibited meanwhile | `swkbd`, or a touch keyboard on the bottom screen |
| `sceUtilityNetconf*` | `system_*_netconf_*` | Ad-hoc connect, create, join | With link play |
| `sceUtilityHtmlViewer*` | `rel_html_view` | Section 6 | Drop |
| `sceUtilityLoadModule`/`Unload` | `system_module_load_ex`, net, codecs | Sony modules `0x100`–`0x106`, `0x200`, `0x300`–`0x303` | Drop |
| `sceUtilityGetSystemParamString` | `save_init_new_game` | Nickname only (parameter 1) | 3DS user name |

**Save contract.**

- **No save encryption in the port.** The game passes a 16-byte key (`0x08879068`) to the savedata utility, which encrypts `DATA0`. **The port never uses or reproduces that key** and writes the state plainly. Import of an old save stays the optional `save.py` path, from a plaintext `DATA0` the player made themselves.
- Load accepts the data only when word 0 is `0x30000`. The save tasks offer overwrite, delete-old-save-when-out-of-space and retry; `save.md` lists the result codes.
- The OpenPSID at state `+0x10` (16 bytes, from `sceOpenPSIDGetOpenPSID` at new game) and `save_compute_psid_checksum` are a RAM tamper check: a changed state gives the warning of sub-state `0xf` in the title menu. The port can drop both, or fill the field with zeros. `save_store_psid_checksum` is only a RAM word.
- Directory `ULES01183` + `0001`, file `DATA0`, plus the import files of section 6.
- Language and confirm button come from the game, not the system: the game offers its own language menu, and `system_get_confirm_button(0)` is `0x4000` (cross) in this build. Only the utility language mapping (`system_get_utility_language`, `system_apply_impose_language`) depends on it.

## 8. Input

`system_pad_update` (`0x08828244`) reads `sceCtrlPeekBufferPositive` once per frame into a 40-byte record (`system.md`, "Pad state block"), and all 273 readers use it through `system_pad_get_state`. The movie skip reads the pad directly. Sampling mode 1 (analog on).

| PSP input | Mask | Used for | Literal sites (approx.) | 3DS (suggestion) |
| --- | --- | --- | --- | --- |
| D-pad | `0x10` up, `0x20` right, `0x40` down, `0x80` left | All menus, walking, field cursor | 1,300 | D-pad |
| Analog stick | `+0x10`, `+0x14`, 0..255, centre `0x80` | Walking (length ≥ 0.5), text scroll, map navigation, a few minigames; 24 functions. Past `0x41`/`0xbe` it also acts as the d-pad on the `+0x18` words | | Circle Pad, ±156 scaled to ±127 around `0x80` |
| Cross | `0x4000` | Confirm (`system_get_confirm_button`, 293 sites) | | A |
| Circle | `0x2000` | Cancel | | B |
| Triangle | `0x1000` | Scene-specific (password, conversion machine, deck screens, quiz) | 47 | X |
| Square | `0x8000` | Scene-specific (title, deck screens, shop) | 34 | Y |
| L, R | `0x100`, `0x200` | Scene-specific, mostly paging (shop, album, field, deck screens; meaning M) | 88 | L, R |
| Start | `0x8` | Skip, confirm name | few | Start |
| Select | `0x1` | Skip | few | Select |
| HOLD | `0x20000` | With hold mode on, stick reads centred | | None: never set it |
| SELECT+START+L+R | `0x309` on `+0x24` | Soft reset to `BOOT.BIN`, inhibited by `0x08aa568c` or a busy file ring | | Same chord: restart the scene stack |

The 3DS has every button the game needs, so a one-to-one map works. Cross to A and Circle to B keep the meaning (confirm, cancel), not the position, so the port may want a setting. The record's repeat and fold logic has no dependency on hardware, so it can be kept as is (repeat delay 15, interval 4; menu repeat after 15 frames, every 4th). The touch screen and C-stick are extras for the port's UI design. `sceCtrlSetSamplingMode` is also called around movie playback, with no effect on the port.

## 9. Other families

**Kernel memory.** No single heap. Budget per scene, the large allocations:

| Pool | Size | Owner |
| --- | --- | --- |
| newlib `UserSbrk` | 64 KiB (`0x0889ed5c` = `0x40` KiB; answers the open question in `system.md`) | `malloc` |
| File index FPL | `0x23000` | `container_build_file_index` |
| `Resource`, `Movie` | `0x7bd000`, `0x1c8000` | `rel_duel_mgr` |
| `HeapMain`, `HeapMovie` | `0x900000`, `0x200000` | `rel_duel_draw` scene 3 |
| Card album | `0xa00000` | `rel_cardalbum` |
| Character list | `0x800000` | `rel_charalist` |
| Shop | `0x640000` | `rel_shop` |
| Deck swap, recipe viewer, deck tutorial | `0x44e000`, `0x468000`, `0x5c0000` | Library modules |
| Story `HeapMovie`, story heap | `0x500000`, `0x200000` | `rel_story` |
| Sound heap (VPL) | `0x280000` | `audio_init` |
| GE list | `0xeb000` | `BOOT.BIN` data |

All pools are one big block with the game's HOGE heap inside. `sceKernelTotalFreeMemSize` only logs. This all fits a 24 MiB budget; the 3DS has 64 MiB for applications on the original model, but expanded textures are what will use it (section 2).

**Modules.** 36 scene and library modules load through the file thread into shared slots (`modules.md`). Exports are by NID. Port: static link, with the scene table and the `system_scene_call`/`return`/`jump` stack kept as data. A module's `.data` starts fresh on every load, so port statics must be reset per scene.

**File I/O.** `container_read_file` is a blocking read of `(path, offset, size)`; `container_read_async` queues it. Disc paths go through `container_io_*_retry` with a UMD wait, and a pre-built index (`file-index.md`) by LBN. The only async call is the sound stream (`sceIoOpenAsync` with `sceIoWaitAsyncCB`). `sceIoGetstat` gives sizes. `sceIoDopen`/`Dread` only scan for import files and in debug viewers. `sceIoDevctl` is USB only. `sceIoWrite` is `host0:` debug screenshots and the `stdio` stubs; **the game never writes a file itself**, as saves go through the utility. `sceIoRemove`, `Mkdir`, `Rmdir`, `Rename` have no real user (rename only in the newlib stub).

**UMD.** `sceUmdCheckMedium`, `Activate(1, "disc0:")`, `WaitDriveStat(0x20)` at boot. Port: skip. Two scene behaviours read the drive state: `system_net_watch_umd_state` (900 frames of state `0x9` ends a link session) and `rel_quiz`'s clock, which waits for the wheel's card art only while bit `0x20` is set and otherwise runs regardless. The port's stub must therefore report ready.

**Power.** `POWER_CALLBACK` stores flags at `0x08ac24bc`. `rel_umd_replace` and `rel_quiz` read them (bits `0x70000` clear the quiz clock, `0x800b0000` pause swap timeouts). `sceKernelPowerTick` stops idle dimming. Port: `aptHook` for suspend; flags stay 0. `EXIT_CALLBACK` stops any movie and exits.

**VFPU.** All VFPU instructions are in `BOOT.BIN` (1,937 words in 192 functions). The 36 modules contain none: they call `sceVfpu*` and `system_vfpu_*` through the export table. `sceKernelChangeCurrentThreadAttr(0, 0x4000)` (34 sites, one per scene entry) grants VFPU use to `ehscript`; drop it. All of this is rendering, cameras, walking and audio panning. **The duel engine does not use it** (`rel_duel_eng` has no system call of any kind), so float differences can't change a duel. Camera code uses `system_fpu_atan`'s own polynomial for exact parity (`system.md`).

**Audio.** `audio_init` reserves channel 2 as the output (256 samples, 44.1 kHz stereo) and runs 32 SAS voices at 44.1 kHz, with up to 6 ATRAC stream rings and 4 + 1 decoder ids. `audio_mixer_thread` mixes per 256-sample grain: faders, SAS keys, streams, echo ring, output effect, then a blocking `sceAudioOutputPannedBlocking`. Everything else is in `audio.md` and `sound.md`. Port: `audio_convert.py` already gives OGG/WAV; on 3DS, `ndsp` has 24 channels against 32 voices, so one-shots may need software mixing, and Vorbis decode on an original 3DS CPU needs measuring. The driver's API can stay the same: id, play, stop, status, faders. Reverb and 3D flags are unused (`sound.md`). The movie player claims the channel while playing.

**Movies.** `system_movie_play(path, flags, volume, ring_packets)`: modal, returns 1 when skipped (`system.md`). `sceDmacMemcpy` only copies frames. 73 files, 480 × 272 H.264 + ATRAC3plus, 243 MiB (`movies.md`). Original 3DS has no H.264 hardware and software decoding at this size is unlikely to keep up (not measured), so the port needs another format; New 3DS has an MVD service. `PORT-READINESS.md` keeps this as a port decision.

**Small families.** `sceImposeSetLanguageMode`: system overlay only. `sceImposeSetUMDPopup`: swap only. `sceWlanGetEtherAddr`, `sceNetEtherNtostr`: ad-hoc identity. `sceRtcGetCurrentClockLocalTime`: date stamp of stored decks (`rel_deck`; its stub is misnamed `deck_stub_noop_save_stored_deck` in the registry). `sceRtcGetCurrentTick`: seeds. `sceKernelPrintf`, `StdioForUser`: logging. `sceKernelLoadExec`: soft reset only. `sceKernelIcacheInvalidateRange`: code loading; not needed.

## What the port must provide

1. A 30 Hz tick with the step order of section 1, and a suspendable scene context.
2. Layered drawing with reversed-depth 3D, stencil, render targets and a 2D path.
3. Texture storage for expanded palette images.
4. Pad record as `system.md` documents it.
5. Sound status that always reaches 0.
6. File reads by `(root, path, offset, size)` with completions on the main thread.
7. Plain save read and write of `0x1c0ec` bytes with the task results the game expects.
8. A font with `$` codes and both line-break rule sets; a keyboard; a message box.
9. A UMD stub that says "ready"; power flags 0.
10. Port decisions: USB (drop), website (drop or SD import), PSP Game Recognition (grant rule), the eight cards, movies.

## Open questions

None of these blocks the port: the static answers are enough to design it, and these only confirm or refine them. No new blocking item was added to `open-questions-triage.md`.

| # | Question | Needs PPSSPP |
| --- | --- | --- |
| 1 | Confirm the hand-off: a breakpoint on `system_wait_frame` should show `ehscript` suspended and `user_main` running the next instruction after `sceKernelSleepThread` | **Yes** |
| 2 | Real frame cost and how often a scene misses two vblanks (busiest duel cut-ins, field). Log `sceDisplayGetVcount` deltas in `system_display_flip`. This gives the port a performance target | **Yes** |
| 3 | `sceCccSJIStoUTF16` with a null table: what `system_font_printf` shows in the debug tools. Curiosity only | **Yes** |
| 4 | Whether any draw reads destination alpha after stencil writes, so that D24S8 changes the result (`field_3d_resolve_shadow_stencil` and its users) | **Yes** (GE debugger) |
| 5 | Which of the 16 list layers each scene uses, per frame; the literal counts above do not show computed layers | **Yes** (or static) |
| 6 | Whether scene 0x17 can be reached by any data-driven path that this census of literals can't see | **Yes** (or static) |
| 7 | `sceFontFindOptimumFont`'s result and which characters use the Latin font: firmware-dependent | **Yes** |
| 8 | Whether 3752 and 3789 were ever distributed as `.YGC` files. Not answerable from the disc or an emulator | No |
| 9 | The wireless gift: which card a host offers, and who chooses it (`0x08eec1c4`) | No (static) |
| 10 | `rel_html_view` language map gives German 6 where the rest of the game uses 4 (`rel_html_view.md`). Irrelevant once the screen is dropped | No |

## Appendix: call census

Every system function with at least one site in game code, by family. Wrappers show the three most frequent callers; `(+n)` is the number of further callers. Sony-internal calls are not counted. Imports of `BOOT.BIN` with no caller at all: `sceIoCancel`, `sceIoChangeAsyncPriority`, `sceIoChdir`, `sceIoCloseAsync`, `sceIoGetDevType`, `sceIoGetFdList`, `sceIoIoctl`, `sceIoIoctlAsync`, `sceIoLseek32`, `sceIoLseek32Async`, `sceIoLseekAsync`, `sceIoMkdir`, `sceIoPollAsync`, `sceIoRemove`, `sceIoRmdir`, `sceIoSetAsyncCallback`, `sceIoSync`, `sceIoWaitAsync`, `sceIoWriteAsync`, `sceKernelExitDeleteThread`, `sceKernelGetGPI`, `sceKernelGetModuleIdList`, `sceKernelLoadModuleByID`, `sceKernelMaxFreeMemSize`, `sceKernelQueryModuleInfo`, `sceKernelStopUnloadSelfModule`, `sceKernelTryAllocateFpl`.

### `sceAtrac`

| Function | Sites | Game wrappers (sites) |
| --- | --- | --- |
| `sceAtracDecodeData` | 1 | `audio_mixer_thread` |
| `sceAtracGetLoopStatus` | 2 | `audio_mixer_thread` ×2 |
| `sceAtracGetMaxSample` | 1 | `audio_start_atrac_voice` |
| `sceAtracGetSoundSample` | 1 | `audio_start_atrac_voice` |
| `sceAtracReinit` | 1 | `audio_reinit_atrac` |
| `sceAtracReleaseAtracID` | 1 | `audio_stop_sound_object` |
| `sceAtracResetPlayPosition` | 1 | `audio_mixer_thread` |
| `sceAtracSetDataAndGetID` | 1 | `audio_start_atrac_voice` |
| `sceAtracSetLoopNum` | 3 | `audio_mixer_thread` ×2, `audio_start_atrac_voice` |

### `sceAudio`

| Function | Sites | Game wrappers (sites) |
| --- | --- | --- |
| `sceAudioChangeChannelVolume` | 1 | `audio_set_channel_volume` |
| `sceAudioChRelease` | 6 | `audio_release_output_channels` ×4, `audio_reserve_output_channels` ×2 |
| `sceAudioChReserve` | 2 | `audio_reserve_output_channels` ×2 |
| `sceAudioGetChannelRestLength` | 1 | `audio_get_channel_rest_length` |
| `sceAudioOutputPannedBlocking` | 1 | `audio_output_panned_blocking` |
| `sceAudioSetChannelDataLen` | 1 | `audio_set_channel_data_len` |

### `sceCcc`

| Function | Sites | Game wrappers (sites) |
| --- | --- | --- |
| `sceCccSetTable` | 1 | `system_font_reset_ccc_table` |
| `sceCccSJIStoUTF16` | 5 | `system_font_printf`, `system_font_printf_box`, `system_font_printf_fixed` (+2) |
| `sceCccStrlenUTF16` | 1 | `duel_core_tutorial_escape_text` |
| `sceCccUTF16toUTF8` | 6 | `save_fill_sfo_param` ×4, `save_start_msg_dialog`, `system_show_net_text_dialog` |
| `sceCccUTF8toUTF16` | 1 | `save_init_new_game` |

### `sceCtrl`

| Function | Sites | Game wrappers (sites) |
| --- | --- | --- |
| `sceCtrlPeekBufferPositive` | 1 | `system_pad_update` |
| `sceCtrlReadBufferPositive` | 1 | `system_movie_poll_skip_button` |
| `sceCtrlSetSamplingMode` | 3 | `system_movie_play` ×2, `system_pad_init` |

### `sceDisplay`

| Function | Sites | Game wrappers (sites) |
| --- | --- | --- |
| `sceDisplayGetAccumulatedHcount` | 3 | `system_display_flip` ×2, `system_sample_hcount` |
| `sceDisplayGetFramePerSec` | 1 | `system_movie_video_pts_queue_create` |
| `sceDisplayGetVcount` | 2 | `system_display_flip` ×2 |
| `sceDisplaySetFrameBuf` | 3 | `system_movie_display_present_frame`, `system_movie_display_reset`, `system_movie_display_thread` |
| `sceDisplaySetMode` | 2 | `system_movie_display_create`, `system_movie_display_reset` |
| `sceDisplayWaitVblankStartCB` | 2 | `system_display_flip` ×2 |

### `sceDmac`

| Function | Sites | Game wrappers (sites) |
| --- | --- | --- |
| `sceDmacMemcpy` | 1 | `system_movie_display_present_frame` |

### `sceFont`

| Function | Sites | Game wrappers (sites) |
| --- | --- | --- |
| `sceFontClose` | 2 | `system_font_shutdown` ×2 |
| `sceFontDoneLib` | 1 | `system_font_shutdown` |
| `sceFontFindOptimumFont` | 1 | `system_font_init` |
| `sceFontGetCharGlyphImage` | 1 | `system_font_get_glyph` |
| `sceFontGetCharInfo` | 1 | `system_font_get_glyph` |
| `sceFontGetFontInfo` | 1 | `system_font_init` |
| `sceFontNewLib` | 1 | `system_font_init` |
| `sceFontOpen` | 2 | `system_font_init` ×2 |
| `sceFontSetAltCharacterCode` | 1 | `system_font_init` |

### `sceGe`

| Function | Sites | Game wrappers (sites) |
| --- | --- | --- |
| `sceGeEdramGetAddr` | 41 | `ui_capture_screen_backdrop` ×6, `field_3d_get_vram_addr` ×3, `ui_draw_captured_backdrop` ×3 (+26) |
| `sceGeEdramGetSize` | 2 | `system_vram_init`, `system_vram_set_size` |
| `sceGeEdramSetAddrTranslation` | 1 | `system_display_init` |
| `sceGeListEnQueue` | 2 | `system_ge_init_state_tracking`, `system_ge_reset_state_list` |
| `sceGeListSync` | 2 | `system_ge_init_state_tracking`, `system_ge_reset_state_list` |

### `sceGu`

| Function | Sites | Game wrappers (sites) |
| --- | --- | --- |
| `dl_write_framebuffer_ptr` | 1 | `system_display_init` |
| `sceGuClear` | 4 | `system_display_init`, `system_set_loading_overlay`, `system_debug_menu_draw_frame` (+1) |
| `sceGuClearColor` | 4 | `system_display_init`, `system_set_loading_overlay`, `system_debug_menu_draw_frame` (+1) |
| `sceGuClearDepth` | 4 | `system_display_init`, `system_set_loading_overlay`, `system_debug_menu_draw_frame` (+1) |
| `sceGuClearStencil` | 4 | `system_display_init`, `system_set_loading_overlay`, `system_debug_menu_draw_frame` (+1) |
| `sceGuCopyImage` | 3 | `system_debug_save_screenshot_bmp`, `system_debug_save_screenshot_tga`, `system_copy_display_buffer` |
| `sceGuDebugFlush` | 1 | `system_display_flip` |
| `sceGuDepthBuffer` | 1 | `system_display_init` |
| `sceGuDepthFunc` | 1 | `system_display_init` |
| `sceGuDepthRange` | 1 | `system_display_init` |
| `sceGuDisable` | 2 | `system_display_init` ×2 |
| `sceGuDispBuffer` | 1 | `system_display_init` |
| `sceGuDisplay` | 1 | `system_display_init` |
| `sceGuDrawBuffer` | 1 | `system_ge_emit_render_targets` |
| `sceGuEnable` | 2 | `system_display_init` ×2 |
| `sceGuFinish` | 11 | `system_ge_open_list_ehge_sync` ×2, `system_display_init`, `system_debug_save_screenshot_bmp` (+7) |
| `sceGuFrontFace` | 1 | `system_display_init` |
| `sceGuGetMemory` | 4 | `field_3d_render_edram_ramp_textures` ×4 |
| `sceGuInit` | 1 | `system_display_init` |
| `sceGuOffset` | 1 | `system_display_init` |
| `sceGuScissor` | 1 | `system_display_init` |
| `sceGuSendList` | 1 | `system_ge_submit_frame` |
| `sceGuSetCallback` | 1 | `system_display_init` |
| `sceGuStart` | 11 | `system_duel_mgr_begin_display_list` ×2, `system_display_init`, `system_debug_save_screenshot_bmp` (+7) |
| `sceGuSwapBuffers` | 1 | `system_display_flip` |
| `sceGuSync` | 14 | `ui_update_osk_input` ×5, `system_display_flip` ×2, `system_display_init` (+6) |
| `sceGuViewport` | 1 | `system_display_init` |

### `sceGzip/sceDeflate`

| Function | Sites | Game wrappers (sites) |
| --- | --- | --- |
| `sceGzipDecompress` | 6 | `field_3d_cutin_start_motion` ×2, `field_3d_cutin_load_voice_anim` ×2, `container_gzip_decompress` (+1) |
| `sceGzipIsValid` | 6 | `field_3d_cutin_start_motion` ×2, `field_3d_cutin_load_voice_anim` ×2, `container_gzip_is_valid` (+1) |

### `sceHttp/sceHttps`

| Function | Sites | Game wrappers (sites) |
| --- | --- | --- |
| `sceHttpEnd` | 1 | `system_html_view_term_http` |
| `sceHttpInit` | 1 | `system_html_view_init_http` |
| `sceHttpLoadSystemCookie` | 1 | `system_html_view_init_http` |
| `sceHttpSaveSystemCookie` | 1 | `system_html_view_term_http` |
| `sceHttpsEnd` | 1 | `system_html_view_term_http` |
| `sceHttpsInit` | 1 | `system_html_view_init_http` |
| `sceHttpsLoadDefaultCert` | 1 | `system_html_view_init_http` |

### `sceImpose`

| Function | Sites | Game wrappers (sites) |
| --- | --- | --- |
| `sceImposeSetLanguageMode` | 2 | `system_main`, `system_apply_impose_language` |
| `sceImposeSetUMDPopup` | 2 | `system_umd_replace_swap_init`, `system_umd_replace_swap_term` |

### `sceIo`

| Function | Sites | Game wrappers (sites) |
| --- | --- | --- |
| `sceIoClose` | 19 | `system_umd_replace_identify_disc` ×4, `system_debug_save_screenshot_bmp` ×3, `system_debug_save_screenshot_tga` ×3 (+7) |
| `sceIoDclose` | 3 | `save_import_scan_dir`, `ui_cutin_viewer_scan_dir_recursive`, `ui_movie_viewer_scan_dir` |
| `sceIoDevctl` | 2 | `system_usb_start_link`, `system_usb_stop_link` |
| `sceIoDopen` | 3 | `save_import_scan_dir`, `ui_cutin_viewer_scan_dir_recursive`, `ui_movie_viewer_scan_dir` |
| `sceIoDread` | 3 | `save_import_scan_dir`, `ui_cutin_viewer_scan_dir_recursive`, `ui_movie_viewer_scan_dir` |
| `sceIoGetstat` | 2 | `container_get_file_size`, `container_io_getstat_retry` |
| `sceIoLseek` | 9 | `system_read_file_range` ×2, `system_sys_lseek`, `container_read_file` (+5) |
| `sceIoOpen` | 14 | `system_debug_save_screenshot_bmp` ×3, `system_debug_save_screenshot_tga` ×3, `system_sys_open` (+7) |
| `sceIoOpenAsync` | 2 | `system_movie_host_open_async_wait`, `audio_set_stream_source` |
| `sceIoRead` | 9 | `system_sys_read`, `container_read_file`, `container_io_read_retry` (+6) |
| `sceIoReadAsync` | 2 | `system_movie_host_read_async_wait`, `system_movie_umd_read_async_wait` |
| `sceIoRename` | 1 | `system_sys_rename` |
| `sceIoWaitAsyncCB` | 4 | `system_movie_host_open_async_wait`, `system_movie_host_read_async_wait`, `system_movie_umd_read_async_wait` (+1) |
| `sceIoWrite` | 7 | `system_debug_save_screenshot_bmp` ×3, `system_debug_save_screenshot_tga` ×3, `system_sys_write` |

### `sceJpeg`

| Function | Sites | Game wrappers (sites) |
| --- | --- | --- |
| `sceJpegCreateMJpeg` | 1 | `ui_album_jpeg_init` |
| `sceJpegDecodeMJpegYCbCr` | 1 | `ui_album_zoom_decode` |
| `sceJpegDeleteMJpeg` | 1 | `ui_album_jpeg_term` |
| `sceJpegFinishMJpeg` | 1 | `ui_album_jpeg_term` |
| `sceJpegGetOutputInfo` | 1 | `ui_album_zoom_decode` |
| `sceJpegInitMJpeg` | 1 | `ui_album_jpeg_init` |

### `sceKernel`

| Function | Sites | Game wrappers (sites) |
| --- | --- | --- |
| `sceKernelAllocateFpl` | 15 | `system_duel_draw_scene_start` ×2, `system_duel_mgr_init_heaps` ×2, `container_build_file_index` (+10) |
| `sceKernelAllocPartitionMemory` | 1 | `system_sys_sbrk` |
| `sceKernelChangeCurrentThreadAttr` | 34 | `audio_set_listener_table`, `ui_duel_draw_init`, `world_blackjack_scene_init` (+31) |
| `sceKernelChangeThreadPriority` | 3 | `system_movie_play` ×2, `system_main` |
| `sceKernelCheckCallback` | 1 | `system_movie_decode_loop` |
| `sceKernelClearEventFlag` | 4 | `system_movie_control_flags_clear` ×2, `system_movie_display_reset`, `system_movie_display_clear_delay_flag` |
| `sceKernelCpuResumeIntr` | 11 | `system_register_module_reent` ×4, `system_atexit` ×2, `system_get_module_reent` ×2 (+2) |
| `sceKernelCpuSuspendIntr` | 7 | `system_atexit` ×2, `system_register_module_reent` ×2, `system_malloc_lock` (+2) |
| `sceKernelCreateCallback` | 3 | `system_main` ×2, `system_umd_replace_swap_init` |
| `sceKernelCreateEventFlag` | 4 | `system_movie_control_flags_create` ×2, `system_movie_display_create`, `audio_init` |
| `sceKernelCreateFpl` | 16 | `system_duel_draw_scene_start` ×2, `system_duel_mgr_init_heaps` ×2, `container_build_file_index` (+11) |
| `sceKernelCreateMbx` | 1 | `system_adhoc_init_matching` |
| `sceKernelCreateSema` | 9 | `audio_init` ×4, `container_init_file_thread` ×2, `system_movie_audio_queue_create` (+2) |
| `sceKernelCreateThread` | 10 | `system_movie_play` ×3, `audio_init` ×2, `system_scene_init` (+4) |
| `sceKernelCreateVpl` | 2 | `audio_set_output_effect`, `audio_init` |
| `sceKernelDcacheWritebackAll` | 1 | `system_font_shutdown` |
| `sceKernelDcacheWritebackInvalidateAll` | 4 | `system_debug_save_screenshot_bmp`, `system_debug_save_screenshot_tga`, `system_copy_display_buffer` (+1) |
| `sceKernelDelayThread` | 5 | `system_movie_audio_thread` ×2, `system_movie_display_thread`, `system_movie_feed_ringbuffer` (+1) |
| `sceKernelDelayThreadCB` | 1 | `system_movie_decode_loop` |
| `sceKernelDeleteCallback` | 1 | `system_umd_replace_swap_term` |
| `sceKernelDeleteEventFlag` | 3 | `system_movie_control_flags_destroy` ×2, `system_movie_display_destroy` |
| `sceKernelDeleteFpl` | 15 | `system_duel_draw_scene_start` ×2, `system_duel_mgr_scene_shutdown` ×2, `system_net_stub_noop_start_hook` (+10) |
| `sceKernelDeleteMbx` | 1 | `system_adhoc_term_matching` |
| `sceKernelDeleteSema` | 5 | `container_shutdown_file_thread` ×2, `system_movie_audio_queue_destroy`, `system_movie_display_destroy` (+1) |
| `sceKernelDeleteThread` | 4 | `system_movie_play` ×3, `system_net_msg_term` |
| `sceKernelDeleteVpl` | 1 | `audio_apply_output_effect` |
| `sceKernelEnableSubIntr` | 1 | `system_set_vblank_interrupt_handler` |
| `sceKernelExitGame` | 1 | `system_exit_callback` |
| `sceKernelExitThread` | 6 | `system_sys_exit` ×2, `system_movie_audio_thread`, `system_movie_display_thread` (+2) |
| `sceKernelFreeFpl` | 12 | `system_duel_mgr_scene_shutdown` ×2, `ui_album_shutdown_step`, `ui_charalist_free_lists` (+8) |
| `sceKernelFreePartitionMemory` | 1 | `system_sys_free_heap_partition` |
| `sceKernelFreeVpl` | 1 | `audio_free_memory` |
| `sceKernelGetBlockHeadAddr` | 1 | `system_sys_sbrk` |
| `sceKernelGetModuleId` | 1 | `system_sys_exit` |
| `sceKernelGetModuleIdByAddress` | 1 | `system_user_main_thread` |
| `sceKernelGetSystemTimeLow` | 1 | `system_module_start` |
| `sceKernelGetSystemTimeWide` | 8 | `system_adhoc_ptp_connect_step` ×2, `system_adhoc_update_ptp` ×2, `system_adhoc_ptp_open` (+3) |
| `sceKernelGetThreadCurrentPriority` | 2 | `system_scene_init`, `system_movie_play` |
| `sceKernelGetThreadId` | 6 | `system_movie_play` ×2, `system_scene_init`, `system_scene_run_slice` (+2) |
| `sceKernelIcacheInvalidateRange` | 2 | `system_read_file_range`, `system_read_fd_or_file_range` |
| `sceKernelLibcClock` | 1 | `system_sys_clock` |
| `sceKernelLibcGettimeofday` | 1 | `system_sys_gettimeofday` |
| `sceKernelLibcTime` | 1 | `system_sys_time` |
| `sceKernelLoadExec` | 1 | `system_check_soft_reset` |
| `sceKernelLoadModule` | 1 | `system_load_module` |
| `sceKernelPollMbx` | 2 | `system_adhoc_term_matching`, `system_adhoc_poll_events` |
| `sceKernelPowerTick` | 2 | `system_movie_decode_loop`, `system_main` |
| `sceKernelPrintf` | 4 | `system_get_module_reent` ×2, `system_sys_exit`, `audio_print_sound_heap_usage` |
| `sceKernelReferEventFlagStatus` | 2 | `system_movie_get_event_flag_bits`, `system_movie_display_is_delayed` |
| `sceKernelRegisterExitCallback` | 1 | `system_main` |
| `sceKernelRegisterSubIntrHandler` | 1 | `system_set_vblank_interrupt_handler` |
| `sceKernelReleaseSubIntrHandler` | 1 | `system_set_vblank_interrupt_handler` |
| `sceKernelResumeThread` | 1 | `system_scene_run_slice` |
| `sceKernelSendMbx` | 1 | `system_adhoc_on_matching_event` |
| `sceKernelSetCompiledSdkVersion395` | 1 | `system_module_start` |
| `sceKernelSetCompilerVersion` | 1 | `system_module_start` |
| `sceKernelSetEventFlag` | 4 | `system_stub_noop_0882d338`, `system_movie_stub_set_event_flag`, `audio_sas_voice_thread` (+1) |
| `sceKernelSignalSema` | 34 | `audio_load_bank` ×5, `audio_mixer_thread` ×4, `audio_stop_sound_object` ×3 (+17) |
| `sceKernelSleepThread` | 3 | `system_scene_init`, `system_scene_run_slice`, `system_net_msg_thread` |
| `sceKernelStartModule` | 6 | `system_scene_thread`, `system_module_on_loaded`, `system_font_init` (+3) |
| `sceKernelStartThread` | 9 | `system_movie_play` ×3, `audio_init` ×2, `system_scene_init` (+3) |
| `sceKernelStderr` | 5 | `system_sys_lseek` ×2, `system_sys_read`, `system_sys_write` (+1) |
| `sceKernelStdin` | 5 | `system_sys_lseek` ×2, `system_sys_read`, `system_sys_write` (+1) |
| `sceKernelStdout` | 5 | `system_sys_lseek` ×2, `system_sys_read`, `system_sys_write` (+1) |
| `sceKernelStopModule` | 6 | `system_sys_exit`, `system_scene_thread`, `system_module_unload` (+3) |
| `sceKernelStopUnloadSelfModuleWithStatus` | 1 | `system_sys_exit` |
| `sceKernelSuspendThread` | 2 | `system_scene_init`, `system_scene_run_slice` |
| `sceKernelTerminateDeleteThread` | 2 | `system_usb_start_link`, `system_usb_stop_link` |
| `sceKernelTerminateThread` | 1 | `system_net_msg_term` |
| `sceKernelTotalFreeMemSize` | 2 | `system_net_msg_term`, `system_usb_link_task_attach` |
| `sceKernelTryAllocateVpl` | 2 | `audio_set_output_effect`, `audio_alloc_memory` |
| `sceKernelUnloadModule` | 6 | `system_sys_exit`, `system_scene_thread`, `system_module_unload` (+3) |
| `sceKernelWaitEventFlag` | 4 | `system_movie_wait_waitflag_bit0`, `system_movie_wait_waitflag_bit1`, `system_movie_wait_controlflag_bit0` (+1) |
| `sceKernelWaitEventFlagCB` | 2 | `audio_sas_voice_thread`, `audio_mixer_thread` |
| `sceKernelWaitSema` | 29 | `audio_mixer_thread` ×5, `audio_stop_sound_object` ×3, `audio_wait_sema_08dce654` ×2 (+18) |
| `sceKernelWaitSemaCB` | 1 | `system_movie_stub_noop_umd_retry_wait` |
| `sceKernelWaitThreadEnd` | 9 | `system_movie_play` ×6, `system_movie_shutdown_on_exit` ×3 |
| `sceKernelWaitThreadEndCB` | 3 | `system_movie_play` ×3 |
| `sceKernelWakeupThread` | 3 | `system_wakeup_scene_thread`, `system_scene_thread`, `system_net_wake_msg_thread` |

### `sceMpeg`

| Function | Sites | Game wrappers (sites) |
| --- | --- | --- |
| `sceMpegAtracDecode` | 1 | `system_movie_decode_audio` |
| `sceMpegAvcDecode` | 1 | `system_movie_decode_video` |
| `sceMpegAvcDecodeFlush` | 1 | `system_movie_decode_loop` |
| `sceMpegAvcDecodeStop` | 1 | `system_movie_stop_video` |
| `sceMpegCreate` | 1 | `system_movie_play` |
| `sceMpegDelete` | 1 | `system_movie_play` |
| `sceMpegFinish` | 1 | `system_movie_play` |
| `sceMpegFlushAllStream` | 1 | `system_movie_play` |
| `sceMpegFreeAvcEsBuf` | 1 | `system_movie_play` |
| `sceMpegGetAtracAu` | 1 | `system_movie_decode_audio` |
| `sceMpegGetAvcAu` | 1 | `system_movie_decode_video` |
| `sceMpegInit` | 1 | `system_movie_play` |
| `sceMpegInitAu` | 2 | `system_movie_play` ×2 |
| `sceMpegMallocAvcEsBuf` | 1 | `system_movie_play` |
| `sceMpegQueryAtracEsSize` | 1 | `system_movie_play` |
| `sceMpegQueryMemSize` | 1 | `system_movie_play` |
| `sceMpegQueryStreamOffset` | 1 | `system_movie_query_stream` |
| `sceMpegQueryStreamSize` | 1 | `system_movie_query_stream` |
| `sceMpegRegistStream` | 2 | `system_movie_play` ×2 |
| `sceMpegRingbufferAvailableSize` | 3 | `system_movie_decode_loop`, `system_movie_stub_noop_reader_done`, `system_movie_feed_ringbuffer` |
| `sceMpegRingbufferConstruct` | 1 | `system_movie_play` |
| `sceMpegRingbufferDestruct` | 1 | `system_movie_play` |
| `sceMpegRingbufferPut` | 1 | `system_movie_feed_ringbuffer` |
| `sceMpegRingbufferQueryMemSize` | 1 | `system_movie_play` |
| `sceMpegUnRegistStream` | 2 | `system_movie_play` ×2 |

### `sceNet (other)`

| Function | Sites | Game wrappers (sites) |
| --- | --- | --- |
| `sceNetApctlInit` | 1 | `system_html_view_init_network` |
| `sceNetApctlTerm` | 1 | `system_html_view_term_network` |
| `sceNetEtherNtostr` | 2 | `system_adhoc_on_matching_event`, `system_net_get_local_mac_string` |
| `sceNetFreeThreadinfo` | 1 | `system_net_msg_term` |
| `sceNetGetDropRate` | 1 | `system_net_msg_init` |
| `sceNetGetLocalEtherAddr` | 2 | `system_net_open_game_socket`, `system_net_create_pdp_socket` |
| `sceNetGetMallocStat` | 1 | `system_net_log_pool_stats` |
| `sceNetInetInit` | 1 | `system_html_view_init_network` |
| `sceNetInetTerm` | 1 | `system_html_view_term_network` |
| `sceNetInit` | 2 | `system_adhoc_init_net`, `system_html_view_init_network` |
| `sceNetResolverInit` | 1 | `system_html_view_init_network` |
| `sceNetResolverTerm` | 1 | `system_html_view_term_network` |
| `sceNetTerm` | 2 | `system_adhoc_term_net`, `system_html_view_term_network` |

### `sceNetAdhoc`

| Function | Sites | Game wrappers (sites) |
| --- | --- | --- |
| `sceNetAdhocInit` | 1 | `system_adhoc_init_net` |
| `sceNetAdhocPdpCreate` | 1 | `system_net_create_pdp_socket` |
| `sceNetAdhocPdpDelete` | 1 | `system_net_delete_pdp_socket` |
| `sceNetAdhocPdpRecv` | 1 | `system_net_receive_messages` |
| `sceNetAdhocPdpSend` | 5 | `system_net_resend_pending` ×2, `system_net_pdp_broadcast`, `system_net_send_keepalive` (+1) |
| `sceNetAdhocPtpAccept` | 1 | `system_adhoc_ptp_accept_step` |
| `sceNetAdhocPtpClose` | 2 | `system_adhoc_ptp_close_all` ×2 |
| `sceNetAdhocPtpConnect` | 1 | `system_adhoc_ptp_connect_step` |
| `sceNetAdhocPtpFlush` | 1 | `system_adhoc_ptp_flush_step` |
| `sceNetAdhocPtpListen` | 1 | `system_adhoc_ptp_listen` |
| `sceNetAdhocPtpOpen` | 1 | `system_adhoc_ptp_open` |
| `sceNetAdhocPtpRecv` | 1 | `system_adhoc_ptp_accept_step` |
| `sceNetAdhocPtpSend` | 1 | `system_adhoc_send_member_list` |
| `sceNetAdhocTerm` | 1 | `system_adhoc_term_net` |

### `sceNetAdhocMatching`

| Function | Sites | Game wrappers (sites) |
| --- | --- | --- |
| `sceNetAdhocMatchingCancelTargetWithOpt` | 4 | `system_adhoc_handle_host_event` ×2, `system_adhoc_cancel_selected_peer`, `system_adhoc_drop_peer` |
| `sceNetAdhocMatchingCreate` | 2 | `system_adhoc_start_matching_client`, `system_adhoc_start_matching_host` |
| `sceNetAdhocMatchingDelete` | 1 | `system_adhoc_stop_matching` |
| `sceNetAdhocMatchingInit` | 1 | `system_adhoc_init_matching` |
| `sceNetAdhocMatchingSelectTarget` | 2 | `system_adhoc_select_peer`, `system_adhoc_select_target_with_name` |
| `sceNetAdhocMatchingSetHelloOpt` | 3 | `system_adhoc_handle_host_event` ×2, `system_net_change_state` |
| `sceNetAdhocMatchingStart` | 2 | `system_adhoc_start_matching_client`, `system_adhoc_start_matching_host` |
| `sceNetAdhocMatchingStop` | 1 | `system_adhoc_stop_matching` |
| `sceNetAdhocMatchingTerm` | 1 | `system_adhoc_term_matching` |

### `sceNetAdhocctl`

| Function | Sites | Game wrappers (sites) |
| --- | --- | --- |
| `sceNetAdhocctlAddHandler` | 1 | `system_adhoc_init_net` |
| `sceNetAdhocctlDelHandler` | 1 | `system_adhoc_term_net` |
| `sceNetAdhocctlDisconnect` | 1 | `system_adhoc_disconnect` |
| `sceNetAdhocctlGetNameByAddr` | 1 | `system_adhoc_find_or_add_peer` |
| `sceNetAdhocctlGetParameter` | 1 | `system_net_get_local_mac_string` |
| `sceNetAdhocctlGetPeerInfo` | 1 | `system_net_check_beacons` |
| `sceNetAdhocctlGetState` | 2 | `system_adhoc_wait_scan`, `system_adhoc_handle_ctl_disconnected` |
| `sceNetAdhocctlInit` | 1 | `system_adhoc_init_net` |
| `sceNetAdhocctlScan` | 1 | `system_adhoc_start_scan` |
| `sceNetAdhocctlTerm` | 1 | `system_adhoc_term_net` |

### `sceOpenPSID`

| Function | Sites | Game wrappers (sites) |
| --- | --- | --- |
| `sceOpenPSIDGetOpenPSID` | 1 | `save_init_new_game` |

### `scePower`

| Function | Sites | Game wrappers (sites) |
| --- | --- | --- |
| `scePowerRegisterCallback` | 1 | `system_main` |

### `sceRtc`

| Function | Sites | Game wrappers (sites) |
| --- | --- | --- |
| `sceRtcGetCurrentClockLocalTime` | 1 | `deck_save_to_stored_deck` |
| `sceRtcGetCurrentTick` | 2 | `system_scene_thread`, `system_seed_rand_from_rtc` |

### `sceSas`

| Function | Sites | Game wrappers (sites) |
| --- | --- | --- |
| `sceSasCore` | 1 | `audio_sas_core` |
| `sceSasCoreWithMix` | 1 | `audio_sas_core_with_mix` |
| `sceSasGetEndFlag` | 1 | `audio_sas_get_end_flag` |
| `sceSasGetEnvelopeHeight` | 1 | `audio_sas_get_envelope_height` |
| `sceSasGetOutputmode` | 3 | `audio_sas_set_reverb_dry_wet`, `audio_sas_set_reverb_volume`, `audio_sas_set_reverb_type` |
| `sceSasInit` | 1 | `audio_sas_init` |
| `sceSasRevEVOL` | 1 | `audio_sas_set_reverb_volume` |
| `sceSasRevType` | 1 | `audio_sas_set_reverb_type` |
| `sceSasRevVON` | 1 | `audio_sas_set_reverb_dry_wet` |
| `sceSasSetADSR` | 1 | `audio_sas_set_adsr` |
| `sceSasSetADSRmode` | 1 | `audio_sas_set_adsr_mode` |
| `sceSasSetKeyOff` | 1 | `audio_sas_set_key_off` |
| `sceSasSetKeyOn` | 1 | `audio_sas_set_key_on` |
| `sceSasSetPause` | 2 | `audio_sas_set_voice_pause`, `audio_sas_set_pause_mask` |
| `sceSasSetPitch` | 2 | `audio_sas_init`, `audio_sas_set_pitch` |
| `sceSasSetSimpleADSR` | 2 | `audio_sas_init`, `audio_sas_set_simple_adsr` |
| `sceSasSetVoice` | 1 | `audio_sas_set_voice` |
| `sceSasSetVolume` | 2 | `audio_sas_init`, `audio_sas_set_volume` |

### `sceSsl`

| Function | Sites | Game wrappers (sites) |
| --- | --- | --- |
| `sceSslEnd` | 1 | `system_html_view_term_http` |
| `sceSslInit` | 1 | `system_html_view_init_http` |

### `sceUmd`

| Function | Sites | Game wrappers (sites) |
| --- | --- | --- |
| `sceUmdActivate` | 3 | `system_movie_reader_init_device`, `system_main`, `system_umd_replace_swap_init` |
| `sceUmdCancelWaitDriveStat` | 1 | `system_movie_umd_io_term` |
| `sceUmdCheckMedium` | 4 | `system_main`, `system_umd_replace_wait_medium`, `system_umd_replace_open_when_ready` (+1) |
| `sceUmdGetDiscInfo` | 2 | `system_umd_replace_open_when_ready`, `system_umd_replace_read_when_ready` |
| `sceUmdGetDriveStat` | 11 | `container_io_open_retry`, `container_io_read_retry`, `container_io_getstat_retry` (+8) |
| `sceUmdRegisterUMDCallBack` | 1 | `system_umd_replace_swap_init` |
| `sceUmdReplacePermit` | 1 | `system_umd_replace_swap_start` |
| `sceUmdReplaceProhibit` | 2 | `system_umd_replace_swap_term`, `system_umd_replace_swap_update` |
| `sceUmdUnRegisterUMDCallBack` | 1 | `system_umd_replace_swap_term` |
| `sceUmdWaitDriveStat` | 4 | `container_wait_umd_ready`, `system_movie_umd_read_retry`, `system_get_file_size_from_offset` (+1) |
| `sceUmdWaitDriveStatCB` | 5 | `system_main` ×2, `container_wait_umd_ready`, `system_movie_umd_open_retry` (+1) |

### `sceUsb`

| Function | Sites | Game wrappers (sites) |
| --- | --- | --- |
| `sceUsbActivate` | 1 | `system_usb_start_drivers` |
| `sceUsbDeactivate` | 1 | `system_usb_stop_drivers` |
| `sceUsbStart` | 2 | `system_usb_start_drivers` ×2 |
| `sceUsbStop` | 4 | `system_usb_start_drivers` ×2, `system_usb_stop_drivers` ×2 |

### `sceUtility`

| Function | Sites | Game wrappers (sites) |
| --- | --- | --- |
| `sceUtilityGetSystemParamString` | 1 | `save_init_new_game` |
| `sceUtilityHtmlViewerGetStatus` | 1 | `system_html_view_update_viewer` |
| `sceUtilityHtmlViewerInitStart` | 1 | `system_html_view_start_viewer` |
| `sceUtilityHtmlViewerShutdownStart` | 1 | `system_html_view_update_viewer` |
| `sceUtilityHtmlViewerUpdate` | 1 | `system_html_view_update_viewer` |
| `sceUtilityLoadModule` | 11 | `system_html_view_load_net_modules` ×6, `system_load_net_modules` ×2, `system_module_load_ex` (+2) |
| `sceUtilityMsgDialogGetStatus` | 7 | `save_run_getsize_task`, `save_run_space_check_task`, `save_run_load_task` (+4) |
| `sceUtilityMsgDialogInitStart` | 3 | `save_start_msg_dialog`, `system_show_net_error_dialog`, `system_show_net_text_dialog` |
| `sceUtilityMsgDialogShutdownStart` | 6 | `save_run_getsize_task`, `save_run_space_check_task`, `save_run_load_task` (+3) |
| `sceUtilityMsgDialogUpdate` | 2 | `save_update_utility_dialogs`, `system_update_net_msg_dialog` |
| `sceUtilityNetconfGetStatus` | 2 | `system_update_netconf_dialog`, `system_poll_netconf_dialog` |
| `sceUtilityNetconfInitStart` | 1 | `system_start_netconf_dialog` |
| `sceUtilityNetconfShutdownStart` | 1 | `system_poll_netconf_dialog` |
| `sceUtilityNetconfUpdate` | 1 | `system_update_netconf_dialog` |
| `sceUtilityOskGetStatus` | 7 | `ui_update_osk_input` ×5, `ui_title_update_osk`, `ui_card_trade_update_picker_result` |
| `sceUtilityOskInitStart` | 6 | `ui_start_osk_input` ×5, `ui_title_start_osk` |
| `sceUtilityOskShutdownStart` | 6 | `ui_update_osk_input` ×5, `ui_title_update_osk` |
| `sceUtilityOskUpdate` | 6 | `ui_update_osk_input` ×5, `ui_title_update_osk` |
| `sceUtilitySavedataGetStatus` | 12 | `save_run_save_task` ×3, `save_run_space_check_task` ×2, `save_run_load_task` ×2 (+4) |
| `sceUtilitySavedataInitStart` | 6 | `save_start_sizes_query`, `save_start_getsize_query`, `save_start_autoload_dialog` (+3) |
| `sceUtilitySavedataShutdownStart` | 12 | `save_run_save_task` ×3, `save_run_space_check_task` ×2, `save_run_load_task` ×2 (+4) |
| `sceUtilitySavedataUpdate` | 1 | `save_update_utility_dialogs` |
| `sceUtilityUnloadModule` | 14 | `system_html_view_unload_net_modules` ×6, `audio_unload_codec_modules` ×3, `system_unload_net_modules` ×2 (+3) |

### `sceVfpu`

| Function | Sites | Game wrappers (sites) |
| --- | --- | --- |
| `sceVfpuMatrix3Mul` | 5 | `ui_draw_lp_panel_frame` ×4, `field_3d_mul_matrix3_by_rot_x` |
| `sceVfpuMatrix3Rot` | 3 | `field_3d_update_destroy_fx`, `field_3d_update_tribute_fx`, `field_3d_update_material_fx` |
| `sceVfpuMatrix3RotX` | 10 | `field_3d_update_cutin_fx_anim55_71` ×2, `field_3d_update_cutin_fx_anim81_8f` ×2, `field_3d_update_cutin_fx_animb1_v0` ×2 (+3) |
| `sceVfpuMatrix3RotY` | 8 | `field_3d_update_material_fx` ×2, `world_connection_rotate_y_deg`, `world_get_direction_vector` (+4) |
| `sceVfpuMatrix3Unit` | 34 | `ui_draw_lp_panel_frame` ×4, `field_3d_update_material_fx` ×2, `field_3d_update_cutin_fx_anim55_71` ×2 (+23) |
| `sceVfpuMatrix4Copy` | 39 | `field_3d_get_main_camera_mvp_matrix` ×4, `field_3d_strip_matrix_translation` ×4, `field_3d_update_cutin_fx_anima3_b5` ×4 (+13) |
| `sceVfpuMatrix4InverseOrtho` | 5 | `ui_draw_lp_roll_digit` ×2, `system_vfpu_matrix4_view_from_direction`, `field_3d_camera_update_matrices` (+1) |
| `sceVfpuMatrix4Mul` | 114 | `ui_draw_lp_roll_digit` ×8, `field_3d_update_cutin_fx_anima3_b5` ×6, `field_3d_update_cutin_fx_anim107_114` ×6 (+49) |
| `sceVfpuMatrix4Rot` | 3 | `world_blackjack_card_draw`, `world_animate_sliding_door`, `world_animate_hinged_door` |
| `sceVfpuMatrix4RotX` | 23 | `field_3d_update_cutin_fx_anim107_114` ×6, `ui_draw_lp_roll_digit` ×4, `field_3d_update_cutin_fx_anima3_b5` ×4 (+7) |
| `sceVfpuMatrix4RotY` | 23 | `field_3d_update_cutin_fx_anim107_114` ×2, `world_draw_character_sprite` ×2, `world_draw_character_sprite_parts` ×2 (+15) |
| `sceVfpuMatrix4RotZ` | 4 | `field_3d_fx_node_hook_rotate_by_kind` ×3, `world_blackjack_card_draw` |
| `sceVfpuMatrix4Scale` | 5 | `world_build_character_part_quad` ×2, `world_blackjack_table_draw`, `world_blackjack_popup1_update` (+1) |
| `sceVfpuMatrix4Transfer` | 47 | `field_3d_update_cutin_fx_anima3_b5` ×10, `field_3d_update_cutin_fx_anim107_114` ×6, `shop_draw_opening_pack_model` ×3 (+20) |
| `sceVfpuMatrix4Transform` | 79 | `field_3d_update_cutin_fx_anim107_114` ×8, `field_3d_update_cutin_fx_anim55_71` ×6, `field_3d_update_cutin_fx_anima3_b5` ×6 (+44) |
| `sceVfpuMatrix4TransformXYZ` | 9 | `field_3d_apply_cutin_camera` ×4, `field_3d_apply_scene_etc` ×3, `field_3d_update_cutin_fx_anim81_8f` ×2 |
| `sceVfpuMatrix4Transpose` | 4 | `field_3d_make_rotation_only_matrix` ×2, `shop_init_opening_card_path`, `shop_get_billboard_matrix` |
| `sceVfpuMatrix4Zero` | 2 | `world_blackjack_popup1_start`, `ui_field_show_card_get` |
| `sceVfpuScalarAbs` | 21 | `ui_create_number_pair_panel` ×4, `field_3d_update_cutin_fx_anime7` ×2, `world_update_npcs` ×2 (+13) |
| `sceVfpuScalarAsin` | 2 | `field_3d_matrix_to_euler`, `field_3d_quat_to_euler` |
| `sceVfpuScalarAtan2` | 9 | `field_3d_quat_to_euler` ×4, `field_3d_matrix_to_euler` ×3, `audio_update_sound_3d` (+1) |
| `sceVfpuScalarCeil` | 16 | `ui_update_window` ×4, `ui_get_decimal_digit_or_blank` ×2, `ui_duel_help_draw_index_item` ×2 (+7) |
| `sceVfpuScalarCos` | 14 | `field_3d_draw_spinning_coin_sprite` ×3, `field_3d_render_model_to_texture_128` ×3, `world_island_map_navigate` ×3 (+4) |
| `sceVfpuScalarMax` | 1 | `field_3d_matrix_to_euler` |
| `sceVfpuScalarMin` | 1 | `field_3d_matrix_to_euler` |
| `sceVfpuScalarPow` | 4 | `ui_get_decimal_digit_or_blank` ×2, `ui_field_draw_dp_value`, `shop_draw_dp_counter` |
| `sceVfpuScalarRound` | 16 | `field_3d_update_backdrop_transition` ×6, `field_3d_update_cutin_fx_anim3e_54_v4` ×4, `field_3d_update_cutin_fx_anim3e_54_v5` ×4 (+1) |
| `sceVfpuScalarSin` | 11 | `field_3d_draw_spinning_coin_sprite` ×3, `field_3d_render_model_to_texture_128` ×3, `system_matrix4_post_rotate_z_s16` (+4) |
| `sceVfpuScalarSqrt` | 11 | `audio_update_sound_3d` ×2, `audio_play_se_at_position`, `world_connection_vec3_length` (+7) |
| `sceVfpuScalarTan` | 1 | `system_gum_is_sphere_visible` |
| `sceVfpuVector3Mul` | 1 | `field_3d_update_destroy_fx` |

### `sceWlan`

| Function | Sites | Game wrappers (sites) |
| --- | --- | --- |
| `sceWlanGetEtherAddr` | 1 | `system_adhoc_on_netconf_done` |
