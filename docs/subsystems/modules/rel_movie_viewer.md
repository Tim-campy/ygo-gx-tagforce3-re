# `rel_movie_viewer`

Module document of the 2026-11-04 round 6 (all game modules imported; `../modules.md`). English, evidence-based: the sections below come from reading every function of the module in the Ghidra decompilation; hypotheses carry a confidence.

| | |
| --- | --- |
| File | `PSP_GAME/USRDIR/gmodule/rel_movie_viewer.prx`, 23,752 bytes, plain ELF (relocatable PRX) |
| Slot | scene 0x0a, id 0x19 |
| Exports → importers | (`libtemplate_rel`, 0) |
| Role (catalogue) | Movie viewer (`modtemplate`): lists `movie/` with `sceIoDopen`. |
| Runtime base | unknown; imported at image base 0x0, so addresses are module offsets |
| Registry ids | `rel_movie_viewer:0x…` |
| Functions | 16 own functions, 16 documented in this round (ui 16); tables in `../functions/<group>.md`, section `rel_movie_viewer` |

## Key functions (largest)

| Address | Prototype | Summary (first sentence) |
| --- | --- | --- |
| `0x00000000` | `int ui_movie_viewer_register_scene(void)` | Module entry point: registers the scene with system_scene_register(0x34 start = ui_movie_viewer_scene_main, 0x1cc end = ui_movie_viewer_scene_end, 0x5300) and returns 0. |
| `0x00000034` | `void ui_movie_viewer_scene_main(void)` | Scene start callback: initialises the viewer block, hides the loading overlay, installs the frame callback ui_movie_viewer_draw_frame with leave callback 0x714 (system_scene_set_frame_callback(0, ...)), then once per frame (system_wait_frame) runs the state 0x485344: 1 scans the movie directory and opens the list (state 2), 2 list input, 3 playback, 4 ends the loop; afterwards frees the heap, installs the no-op scene callbacks, waits a frame and returns with system_scene_return(10, 0). |
| `0x00000138` | `void ui_movie_viewer_init(void)` | Clears the 0x653c-byte viewer block at 0x485340, creates an 0x80000-byte heap on module memory at 0x5310 (system_heap_create, stored at 0x485340), sets the state 0x485344 = 1 and the movie volume 0x48b870 = 0x28. |
| `0x00000190` | `void ui_movie_viewer_free_heap(void)` | When the heap word 0x485340 is set releases it with system_free_aligned and clears it. |
| `0x000001cc` | `void ui_movie_viewer_scene_end(void)` | Empty function (jr ra). |
| `0x000001d4` | `void ui_movie_viewer_set_state(int state)` | Changes the viewer state 0x485344: when leaving state 2 calls ui_movie_viewer_leave_list; entering 3 clears the play flag 0x48b874; entering 2 opens the movie list (ui_movie_viewer_open_list). |
| `0x00000258` | `void ui_movie_viewer_scan_movies(void)` | Builds the path of root 3 (container_get_root_path, USRDIR) + "movie/", resets the movie count 0x48b748 and lists the directory recursively (ui_movie_viewer_scan_dir). |
| `0x000002a0` | `void ui_movie_viewer_open_list(void)` | Fills the 0x120-byte list-window record at 0x48b74c (title/item text scale 12, colours, heap 0x485340, item draw callback ui_movie_viewer_draw_item at +0xfc, size 0xf0 x 0x10, item count +0xcc = movie count 0x48b748) and opens it (ui_open_list_window); then places the window's top and cursor so that the last played index 0x48b86c is visible (top = min(index, count - 10)). |
| `0x00000470` | `void ui_movie_viewer_leave_list(void)` | Leave handler of the list state: tail-jumps to ui_list_window_reset(0x0048b74c), which removes the list window record from the window list and frees its items (Ghidra shows an empty body; instructions: lui/addiu a0 around j thunk_ui_list_window_reset). |
| `0x0000047c` | `void ui_movie_viewer_update_list(void)` | List state 2: steps the list window (ui_update_list_window); left/right (pad repeat word +0xc) change the movie volume 0x48b870 within 6-100; L/R decrease/increase a BGM track number 0x48b878 (not below 0) and play it with audio_play_track_with_fade; when the window has closed (state byte +0xe9 = 6) a result of -2 (cancel) goes to state 4 (exit), any other result is stored as the movie index 0x48b86c and goes to state 3 (play). |
| `0x000005a0` | `void ui_movie_viewer_play(void)` | Playback state 3: loads the movie modules (system_load_movie_modules; arguments hidden), waits until system_module_all_loaded, gives the movie player 0x400000 bytes of module memory at 0x85340 (system_movie_set_work_memory), sets the play flag 0x48b874 so that the next frame callback plays the movie, waits one frame, unloads the movie modules and returns to the list (state 2). |
| `0x00000624` | `void ui_movie_viewer_draw_frame(void)` | Frame callback: in state 3 with the play flag set plays the chosen movie path (0x485348 + index x 0x100) with system_movie_play_with_volume(path, 0, volume 0x48b870) and clears the flag; in state 2 draws the list window on layer 1 (ui_draw_list_window); in state 1 and otherwise prints a fixed status string at (0, 0), scale 16. |
| `0x0000071c` | `void ui_movie_viewer_scan_dir(char *path)` | Lists path with sceIoDopen/sceIoDread/sceIoDclose: for a directory entry (mode bit 0x1000) whose name does not start with '.' appends name and "/" to path, recurses and truncates path again; for a regular file (mode bit 0x2000) stores path + name as a 0x100-byte entry at 0x485348 + count x 0x100 and increments the count 0x48b748; stops at 100 files. |
| `0x00000828` | `void ui_movie_viewer_draw_item(void *list, uint index, int x, int y)` | List-window item callback: widens the stored ASCII path of movie index to UTF-16 and draws it, without the leading USRDIR root path (strlen of container_get_root_path(3) characters skipped), in black at scale 12 at (x + 2, y + 2) inside an external font list. |
| `0x000008f4` | `void ui_list_window_draw_text(int x, int y, void *text)` | Same code as BOOT ui_list_window_draw_text: system_font_draw_text(x << 6, y << 6, (480 - x) << 6, text). |

## Purpose and flow

Scene 0x0a (id 0x19, module-info `modtemplate`): a developer movie viewer. Entry registers start 0x34 and end 0x1cc; frame callback 0x624 with leave callback 0x714. States (0x485344): 1 scan `movie/` under USRDIR recursively (`sceIoDopen`/`sceIoDread`, up to 100 regular files, paths of 0x100 bytes at 0x485348) and open a list window; 2 list (left/right movie volume 6-100, default 0x28; L/R step a BGM track number and play it); 3 play: load the movie modules, give the player 0x400000 bytes at 0x85340, the frame callback plays the file with `system_movie_play_with_volume(path, 0, volume)`, unload; 4 exit with `system_scene_return(10, 0)`.

Module memory: heap 0x80000 bytes at 0x5310, movie work 0x400000 bytes at 0x85340, viewer block 0x653c bytes at 0x485340 (so the module image is about 4.6 MiB in memory).

## Open questions

- The two status strings printed in states 1 and other (0x52c8, 0x52bc) were not read.
- 0x00000470 (12 bytes) shows no effect in the decompilation.
