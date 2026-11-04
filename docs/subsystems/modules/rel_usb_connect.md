# `rel_usb_connect`

Module document of the 2026-11-04 round 6 (all game modules imported; `../modules.md`). English, evidence-based: the sections below come from reading every function of the module in the Ghidra decompilation; hypotheses carry a confidence.

| | |
| --- | --- |
| File | `PSP_GAME/USRDIR/gmodule/rel_usb_connect.prx`, 34,788 bytes, plain ELF (relocatable PRX) |
| Slot | scene 0x17, id 0x2a |
| Exports → importers | — |
| Role (catalogue) | USB connection (`sceUsb`, `sceIoDevctl`): `database/usb_connect/data.ehp`. |
| Runtime base | unknown; imported at image base 0x0, so addresses are module offsets |
| Registry ids | `rel_usb_connect:0x…` |
| Functions | 92 own functions, 92 documented in this round (system 92); tables in `../functions/<group>.md`, section `rel_usb_connect` |

## Key functions (largest)

| Address | Prototype | Summary (first sentence) |
| --- | --- | --- |
| `0x00000038` | `void system_usb_scene_main(void)` | Scene start callback (scene 0x17): clears the loading overlay, runs system_usb_scene_init, installs system_scene_set_frame_callback(2, system_usb_frame_callback, system_usb_leave_callback), loops system_usb_scene_update plus system_wait_frame until done, restores the no-op callbacks, shows the loading overlay, waits a frame and calls system_scene_return(0x17, 0). |
| `0x00000330` | `int system_usb_start_link(void)` | Creates the thread "USBPSPCommSampleThread" (entry system_usb_link_thread, priority 0x20, stack 0x1000, attribute 0x200000), loads utility module 0x200 (sceUtilityLoadModule), starts the drivers and registers the thread id with sceIoDevctl("usbpspcm:", 0x3415001, &thread, 4); each failure undoes the earlier steps. |
| `0x0000067c` | `void system_usb_load_slot(void *resources, int index)` | Takes the 8-byte record {u32 root, char *name} at 0x00006f00 + index * 8 (entry 0: database/usb_connect/data.ehp), gets the file size, allocates a 12-byte request and the buffer on the module heap and queues container_load_file(root, name, buffer, size, system_usb_on_file_loaded, request); increments the pending count. |
| `0x00000814` | `void system_usb_app_init(void *app)` | Initialises the app (state +0x00, black flag +0x04, resources +0x08, background task +0x0c, flow task +0x10): loads audio track 0x2c8, creates the task manager, allocates and clears the resource set, initialises the 3D render state on layer 0, queues the load of data.ehp (slot 0) and starts a fade-out (1, 0, 1). |
| `0x00000914` | `int system_usb_update(void *app)` | App state machine (app+0x00), run after updating all tasks: 0 enables the black screen and goes to 1; 1 waits until no load is pending, creates the flow task and the background task (kind 0), enables the background draw, clears the black screen, starts a 16-frame fade-in, goes to 3; 3 goes to 7 after the fade; 7 waits for the flow task's done flag, then starts a 16-frame black fade-out, stops the BGM (audio_stop_sounds_bgm_arg(600)) and goes to 4; 4 returns 1 when the fade is done. |
| `0x00000a6c` | `void system_usb_draw_black_screen(void *app)` | Draws an opaque black 480 x 272 sprite on GE layer 5. |
| `0x00000b2c` | `void system_usb_draw_background(void *app)` | When data.ehp is loaded, draws its member usb_connect_bg_gim on layer 4 as a 480 x 256 sprite at (0, 0) and two 256 x 16 strips from texels (0x1e0, 0) and (0x1f0, 0) drawn rotated (flip mode 3) at (0, 256) and (256, 256) to fill the bottom 16 lines. |
| `0x00000e00` | `void * system_usb_create_bg_task(int kind, char auto_delete)` | Allocates a 0x90-byte background task (system_usb_bg_task_construct), attaches it with priorities 0/0 for kind 0 or 3/3 otherwise and sets kind and auto_delete. |
| `0x00000f2c` | `void system_usb_bg_task_update(void *task)` | Background task update: on first call finds the ehf named by the pointer table 0x00006ffc[kind] (first entry usb_connect01_ehf) in data.ehp, allocates its work buffer and initialises a player; then advances frame +0x20, looping at the end frame for kind 0, otherwise marking done and detaching and deleting itself when auto-delete is set. |
| `0x00001640` | `void system_usb_message_task_open(void *task, void *text)` | Sets the open flag +0x20, initialises the task's window list at +0x24 with the module heap and fills the 0x78-byte window descriptor at +0x70 (id 1, 300 x 0xb4 centred on screen, width field 400, text at +0xa8, margins 10/8, style 0x0c), adds and opens it. |
| `0x000017b4` | `void system_usb_message_task_draw(void *task)` | Message task draw: ui_draw_window_list of the task's list (+0x24) on GE layer 4 with alpha blending. |
| `0x0000191c` | `void * system_usb_get_text(void *flow, int number)` | Returns dictionary word number from the per-language string table in data.ehp: language 1 uses usb_strtbl_e.bin, 2 usb_strtbl_g.bin, 3 usb_strtbl_f.bin, 4 usb_strtbl_i.bin, 5 usb_strtbl_s.bin; language 0 passes a null name (no table for it in this build). |
| `0x00001a80` | `void system_usb_flow_update(void *flow)` | Flow task update (state +0x20). |
| `0x00002120` | `void system_usb_list_task_open(void *task, void *text)` | Sets the open flag +0x20, clears the 0x120-byte list-window record at +0x24, fills it (text at +0xa8, margins 10/10/8/0, style 0x0c, flag bits at +0xec/+0xee/+0xf7, module heap at +0xe8), opens it with ui_open_list_window and centres it on screen. |
| `0x00002298` | `void system_usb_list_task_draw(void *task)` | List task draw: ui_draw_list_window of the record at +0x24 on GE layer 4. |

## Purpose and flow
Scene 0x17. A one-shot USB link through Sony's PSP communication driver (`USBPSPCommunicationDriver`, device `usbpspcm:`): when data arrives over the link the game sets progress flag e8 bit 1, adds DP and unlocks characters. The peer is not identified in the code; the driver product string is `ULJM05373` (hypothesis, medium: the Japanese product id of this game; the PSP-to-PS3 USB link of the communication driver is the likely use, confidence low).

- Entry `system_usb_module_start` registers `system_usb_scene_main` (0x00000038) and the empty 0x000000e4. Frame callbacks `system_scene_set_frame_callback(2, system_usb_frame_callback, system_usb_leave_callback)`; end with `system_scene_return(0x17, 0)`.
- Heap: 0x100000 bytes over the module buffer at 0x00007180 (global 0x00107180). App object 0x18 bytes (vtable 0x000070c4 at +0x14, globals 0x00107184/0x00107190): +0x00 state, +0x04 black-screen flag, +0x08 resource set, +0x0c background ehf task, +0x10 flow task.
- The module uses the same private task scheduler as rel_gallery (manager 0x00107194; same node layout and vtable slots +0x08 delete, +0x0c attach, +0x10 update, +0x14 draw, +0x18 detach). Task classes: base 0x000070ec, link 0x0000709c (0x28 bytes), resource set 0x000070b8, background 0x000070d0 (0x90 bytes, ehf `usb_connect01_ehf`, loop 0x50 frames), message 0x00007108 (0xe8 bytes, window list +0x24, descriptor +0x70), flow 0x00007124 (0x34 bytes), list window 0x00007140 (0x144 bytes, record +0x24).
- App states (`system_usb_update`): 0 → 1 (wait for data.ehp) → 3 (fade in) → 7 (wait for flow done) → 4 (fade out, return 1).
- Flow states (`system_usb_flow_update`, +0x20): 0 prompt (word 7, or word 1 when e8 bit 1 is already set: state 1, cancel only); 2 confirm starts the link (word 3, link task, animation); 3 waits for `system_usb_is_data_received` (cancel stops the link); on data: flag e8 bit 1, DP, `system_usb_grant_characters`, list window word 2; 4 → word 5 → 6 (word 6) or 7 when `save_get_pack_state(0x2b)` is non-zero; 7 done. State 5 (word 4) has no setter.

## USB link (Sony calls and what the game passes)
- `system_usb_start_link`: `sceKernelCreateThread("USBPSPCommSampleThread", entry 0x0000045c, prio 0x20, stack 0x1000, attr 0x200000, 0)`; `sceUtilityLoadModule(0x200)` (the USB PSPCM utility module); `sceUsbStart("USBBusDriver", 0, 0)`; `sceUsbStart("USBPSPCommunicationDriver", 10, "ULJM05373")`; `sceUsbActivate(0x1cb)`; `sceIoDevctl("usbpspcm:", 0x3415001, &thread_id, 4, 0, 0)`. Stop: devctl 0x3415002 with the same word, `sceUsbDeactivate`, `sceUsbStop` both, `sceUtilityUnloadModule(0x200)`, `sceKernelTerminateDeleteThread`.
- `system_usb_link_thread` receives {word, flags}: flags bit 0x80 with bit 0 stores the word in 0x00107188 and sets the received flag 0x0010718c; bit 1 stores -1. Only the flag is consumed; the received word 0x00107188 is never read in the module (the payload itself is not used beyond "something arrived").

## Files loaded
- Record table 0x00006f00 {u32 root, char *name}: entry 0 `database/usb_connect/data.ehp`.
- data.ehp members: `usb_connect_bg.gim` (background, 480 x 256 plus a 32-pixel-wide area used for the bottom 16 lines), `usb_connect01.ehf` (animation, name table 0x00006ffc), string tables `usb_strtbl_<l>.bin` for languages 1-5 (e, g, f, i, s; language 1's name is the string at 0x00007000); language 0 has no table (null name passed). EHP magic check against 0x00006fd0.

## Rewards
- Progress flag e8 bit 1 (one-time; later visits show word 1 and exit).
- DP: `save_add_dp(10000)` in flow state 3 (an older decompilation printed the constant as the address of a symbol).
- Characters: table of {int character, int variant} pairs at 0x00007064 terminated by a negative value; each gets `save_add_character_entry(character, deck_get_owner_recipe(character, 0))` and character flags bit 0 and bit 1.

## Name mismatches
- 0x00000000 matches `shop_module_start` byte for byte but registers its own callbacks; named `system_usb_module_start`.

## Open questions
- The contents of the character table 0x00007064.
- What `0x00002288` returns (8-byte body hidden); the flow relies on it returning 1 when the list window has finished.
- Peer device/software of the usbpspcm link.
## Task vtables
| Vtable | Class | destructor | +0xc attach | +0x10 update | +0x14 draw | +0x18 detach |
| --- | --- | --- | --- | --- | --- | --- |
| 0x0000709c | link | 0x054c | 0x04bc | 0x04f4 (jump stub to `system_usb_is_data_received`) | 0x04fc (empty) | 0x0504 |
| 0x000070d0 | background | 0x1158 | 0x0eac | 0x0f2c | 0x1090 | 0x10ec |
| 0x000070ec | base task | 0x15f0 | 0x1480 (empty) | 0x124c (empty) | 0x12a8 (empty) | 0x1590 (empty) |
| 0x00007108 | message | 0x18a8 | 0x1638 | 0x17a4 (window transition done) | 0x17b4 | 0x186c (free window list) |
| 0x00007124 | flow | 0x20bc | 0x1904 | 0x1a80 | 0x2078 (empty) | 0x2080 (empty) |
| 0x00007140 | list | 0x238c | 0x2118 | 0x2290 (empty) | 0x2298 | 0x2350 (list window reset) |

- All six task vtables share the layout {0, 0, destructor, attach, update, draw, detach}; `system_usb_attach_task` / `system_usb_detach_task` call exactly slots +0x0c / +0x18. `system_usb_message_task_reset` and `system_usb_list_task_reset` are the attach methods of their classes. The stub 0x000007b0 to `system_usb_free_slot` is what `system_usb_app_term` calls.
- The ehf name table 0x00006ffc has one entry (the next word has no relocation and starts the string at 0x00007000), and only kind 0 is ever created (`system_usb_create_bg_task(0, 0)` from `system_usb_update`), so the kind != 0 paths of `system_usb_create_bg_task` and `system_usb_bg_task_update` are dead; a non-zero kind would index past the table.
- Message and list tasks keep their window list / list window record at task +0x24; 0x00002288 (`ui_update_list_window(task + 0x24)`) is called directly by `system_usb_flow_update`.
