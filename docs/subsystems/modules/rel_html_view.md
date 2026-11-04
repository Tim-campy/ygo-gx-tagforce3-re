# `rel_html_view`

Module document of the 2026-11-04 round 6 (all game modules imported; `../modules.md`). English, evidence-based: the sections below come from reading every function of the module in the Ghidra decompilation; hypotheses carry a confidence.

| | |
| --- | --- |
| File | `PSP_GAME/USRDIR/gmodule/rel_html_view.prx`, 24,724 bytes, plain ELF (relocatable PRX) |
| Slot | scene 0x0e, id 0x16 |
| Exports → importers | — |
| Role (catalogue) | Download over HTTP/SSL (`sceHttp`, `sceSsl`, `sceNet*`, `sceUtility`). A `konami.jp` URL for TF3 EU, and `/PSP/SAVEDATA/`: downloadable content. |
| Runtime base | unknown; imported at image base 0x0, so addresses are module offsets |
| Registry ids | `rel_html_view:0x…` |
| Functions | 16 own functions, 16 documented in this round (system 16); tables in `../functions/<group>.md`, section `rel_html_view` |

## Key functions (largest)

| Address | Prototype | Summary (first sentence) |
| --- | --- | --- |
| `0x00000000` | `int system_html_view_register_scene(void)` | Module entry point: registers the scene with system_scene_register(0x34 start = system_html_view_scene_main, 0x84 end = system_html_view_scene_end, 0x5620) and returns 0. |
| `0x00000034` | `void system_html_view_scene_main(void)` | Scene start callback: sceKernelChangeCurrentThreadAttr(0, 0x4000), system_html_view_init, then calls system_html_view_step once per frame (system_wait_frame between calls) until it returns non-zero, and returns to the calling scene with system_scene_return(0xe, 0). |
| `0x0000008c` | `int system_html_view_load_net_modules(void)` | Loads the network utility modules in order with sceUtilityLoadModule: 0x100, 0x102, 0x103, 0x104, 0x105, 0x106 (net common, inet, parse URI, parse HTTP, HTTP, SSL); on the first failure unloads them all (system_html_view_unload_net_modules). |
| `0x00000134` | `void system_html_view_unload_net_modules(void)` | Unloads the network utility modules in reverse order with sceUtilityUnloadModule: 0x106, 0x105, 0x104, 0x103, 0x102, 0x100. |
| `0x00000178` | `int system_html_view_init_http(void)` | Initialises the HTTP stack: sceSslInit(0x28000), sceHttpInit(0x28000), sceHttpsInit(0, 0, 0, 0), sceHttpsLoadDefaultCert(0, 0), sceHttpLoadSystemCookie(); after a failure of any call but the first it shuts the stack down again (system_html_view_term_http). |
| `0x00000244` | `void system_html_view_term_http(void)` | Saves the system cookies (sceHttpSaveSystemCookie) and ends HTTPS, HTTP and SSL (sceHttpsEnd, sceHttpEnd, sceSslEnd). |
| `0x00000278` | `int system_html_view_init_network(void)` | Brings the network up for the viewer: loads the net utility modules, sceNetInit(0x20000, 0x2a, 0, 0x2a, 0), sceNetInetInit, sceNetResolverInit, sceNetApctlInit(0x5400, 0x30) (arguments as decompiled; the first is a relocated constant) and the HTTP stack (system_html_view_init_http); any failure after sceNetInit tears everything down (system_html_view_term_network). |
| `0x00000358` | `void system_html_view_term_network(void)` | Tears the network down: system_html_view_term_http, sceNetApctlTerm, sceNetResolverTerm, sceNetInetTerm, sceNetTerm, then unloads the net utility modules. |
| `0x0000039c` | `int system_html_view_get_language(void)` | Maps the game language (save_get_language: 0 j, 1 e, 2 g, 3 f, 4 i, 5 s) to the value stored in the viewer parameters: 0 -> 0, 1 -> 1, 2 -> 6, 3 -> 2, 4 -> 5, 5 -> 3, anything else 1. |
| `0x00000414` | `void system_html_view_append_url(char *buffer)` | Appends the fixed start URL (the string at 0x55cc, a konami.jp address for the game) to buffer with system_strcat. |
| `0x00000420` | `void system_html_view_build_download_dir(char *buffer)` | Writes "/PSP/SAVEDATA/" followed by the game's save directory name (save_build_save_dir_name) into buffer: the viewer's download directory, so downloads land in the game's own save folder. |
| `0x00000470` | `int system_html_view_start_viewer(void *memory)` | Fills the 0xa8-byte HTML viewer parameter block at 0x5630 (field names per the PSPSDK SceUtilityHtmlViewerParam layout, confidence medium): +0 size 0xa8, +4 language (system_html_view_get_language), +8 button swap (1 unless the confirm button is circle 0x2000), thread priorities +0xc 0x11, +0x10 0x13, +0x14 0x12, +0x18 0x10; +0x30 memory, +0x34 memory size 0x600000; +0x40 initial URL 0x56e8 (system_html_view_append_url); +0x44 3 tabs; +0x48 interface mode 2; +0x4c options 0x2ba; +0x50 download directory 0x58e8 (system_html_view_build_download_dir); download/upload names 0; +0x60 cookie mode 3; +0x64 0x200; +0x68 home URL = the initial URL; +0x6c, +0x70, +0x74 = 1; +0x78 = 0; +0xa4 = 1; then calls sceUtilityHtmlViewerInitStart(0x5630). |
| `0x000005a0` | `int system_html_view_update_viewer(void)` | One frame of the HTML viewer utility: sceGuSync(0, 0), then by sceUtilityHtmlViewerGetStatus: 2 (visible) sceUtilityHtmlViewerUpdate, 3 (quit requested) sceUtilityHtmlViewerShutdownStart, 0 (finished) returns 1 when the result word +0x1c of the parameter block (0x564c) is 0, else 2. |
| `0x00000650` | `void system_html_view_init(void)` | Sets the step word 0x562c to 1 and the viewer memory pointer 0x596c to 0x5970 (a buffer inside the module image). |
| `0x00000670` | `int system_html_view_step(void)` | Step machine on 0x562c: 1 brings the network up (system_html_view_init_network) and starts the viewer with the memory 0x596c, going to 2, or to 3 on any failure; 2 updates the viewer until it finishes, then 3; 3 tears the network down, then 4; 4 returns 1. |

## Purpose and flow

Scene 0x0e (id 0x16, module-info name `module_htmlview`): opens Sony's HTML viewer utility on a fixed konami.jp start page, with the download directory set to the game's own save folder, so files fetched from the page (downloadable content) land in `/PSP/SAVEDATA/<game save dir>/`. Entry point registers start 0x34 and end 0x84. The start callback runs `system_html_view_step` once per frame and finally calls `system_scene_return(0xe, 0)`.

Steps (word 0x562c): 1 network up (`sceUtilityLoadModule` 0x100, 0x102-0x106; `sceNetInit(0x20000, 0x2a, 0, 0x2a, 0)`; `sceNetInetInit`; `sceNetResolverInit`; `sceNetApctlInit`; `sceSslInit(0x28000)`; `sceHttpInit(0x28000)`; `sceHttpsInit`; `sceHttpsLoadDefaultCert`; `sceHttpLoadSystemCookie`) and `sceUtilityHtmlViewerInitStart`; 2 `sceUtilityHtmlViewerUpdate`/`ShutdownStart` until status 0; 3 teardown in reverse (cookies saved first); 4 done. Any failure skips to the teardown.

## What the game passes to the viewer

Parameter block at 0x5630 (0xa8 bytes; field names after the PSPSDK `SceUtilityHtmlViewerParam`, confidence medium): language mapped from the game language (j 0, e 1, g 6, f 2, i 5, s 3; BOOT.BIN's own dialog mapping gives German 4, so German here looks wrong: hypothesis, low), button swap, thread priorities 0x11/0x13/0x12/0x10, work memory 0x5970 inside the module image with size 0x600000 (the module's memory image must therefore be at least 6 MiB larger than its file), initial and home URL = the string at 0x55cc, 3 tabs, interface mode 2, options 0x2ba, download directory "/PSP/SAVEDATA/" + `save_build_save_dir_name`, cookie mode 3, +0x64 = 0x200, text size/display/connect modes 1, disconnect mode 0, +0xa4 = 1. Result word +0x1c gives the step result (0 ok -> 1, else 2), but the caller ignores it.

For the port: this screen downloads files into the save directory; together with the save-import code in BOOT.BIN (`save_import_*`, kinds 0 cards, 1 decks, 2 limit lists) it is the game's downloadable-content path (the import kinds are documented with rel_limitlist above and in save.md).

## Open questions

- The exact URL string and whether the page still exists (not needed for the port; the port should replace this screen).
- `sceNetApctlInit` arguments shown as (0x5400, 0x30): the first is probably a relocated constant (stack size 0x1400?); check the instruction.
