# Resident runtime structures (`BOOT.BIN` and scene-module tables)

Layouts of the small runtime structures of the resident core that the port needs in order to reproduce file loading, scene transitions, heaps and per-language resource lookups. Each section gives the purpose, the address, the layout with evidence and confidence, and the accessor functions. Addresses are runtime addresses in `BOOT.BIN` (base `0x08804000`) unless a module is named; module bases are in `docs/subsystems/modules.md`. All values are little-endian.

Basis for all sections: the capstone disassembly of the accessor functions (2026-10-31), the function descriptions in `re/documented.tsv` / `re/documented-rel_deck.tsv`, and for the static tables the bytes of `BOOT.BIN` and `rel_deck.prx` of the maintainer's disc. No runtime check yet unless stated.

Registry rows: `scene_stack`, `file_request_ring`, `root_path_table`, `heap_header`, `ui_resource_table`, `card_language_suffixes` (`re/formats.csv`).

## `scene_stack`: scene transition stack (`0x08aa56a4`, 144 bytes)

Returned by `system_get_scene_stack()` (`0x0883596c`). Holds the call stack of scenes (a scene module can call another and get control back) and the last transition, which the called module reads to learn where it came from. Prose: `docs/subsystems/modules.md`, "Scenes".

| Offset | Size | Type | Field | Evidence | Conf. |
| --- | --- | --- | --- | --- | --- |
| `+0x00` | 4 | u32 | `depth`: number of entries on the stack | `system_scene_call` loads it, stores `depth + 1` and writes the entry at `+0x0c + 8·depth`; `system_scene_return` decrements it; `system_scene_get_caller` returns 31 when it is 0 | H |
| `+0x04` | 8 | transition | `current`: the last transition (see below) | `system_scene_call` copies the pushed entry here (`memcpy(+4, entry, 8)`); `system_scene_return` writes `{2, from, caller, arg}` and `system_scene_jump` `{3, from, to, arg}` directly; `system_scene_get_transition(buf)` copies these 8 bytes out | H |
| `+0x0c` | 16 × 8 | transition[16] | Stack of pushed `call` transitions, entry `i` at `+0x0c + 8·i` | Indexing in `system_scene_call` / `_return` / `_get_caller`; 16 entries fit before `+0x8c`. No bound check in `system_scene_call` (capacity inferred from the layout) | H (layout), M (capacity) |
| `+0x8c` | 2 | u16 | A value passed between scenes: set by `rel_shop`'s `shop_show_message`, read by `shop_scene_main` and `rel_story`'s `world_state_shutdown_shop` | `system_scene_set_field_8c` (`0x0883de74`) / `system_scene_get_field_8c` (`0x0883de9c`) | H (location), L (meaning: unknown) |
| `+0x8e` | 2 | — | Unused (padding to 144) | No access found | M |

The whole block is cleared (`memset(…, 0, 0x90)`) by `system_scene_jump`, which is the basis for the 144-byte size (high).

Transition (8 bytes):

| Offset | Size | Type | Field |
| --- | --- | --- | --- |
| `+0` | 2 | u16 | `type`: 1 call, 2 return, 3 jump |
| `+2` | 2 | u16 | `from`: scene id of the caller |
| `+4` | 2 | u16 | `to`: scene id requested (for a return, the caller popped from the stack) |
| `+6` | 2 | u16 | `arg`: argument for the target scene |

Scene ids map to modules through the scene table `0x088a1478` (`scene_table`, `modules.md`). `system_scene_get_caller(scene)` returns `from` of the top entry when its `to` equals `scene`, else 31 (no caller).

## File thread state block (`0x08920cac`, `0xc1c` bytes) and `file_request_ring`

`container_init_file_thread(config)` (`0x0881d574`) clears `0xc1c` bytes at `0x08920cac` and fills the header; `container_shutdown_file_thread` (`0x0881d63c`) deletes the two semaphores and clears the block again. Every file read and module load is queued here and served by the single file thread (`container_file_thread`, `0x0881dba0`). Prose: `docs/subsystems/container.md`.

| Offset | Address | Size | Type | Field | Evidence | Conf. |
| --- | --- | --- | --- | --- | --- | --- |
| `+0x000` | `0x08920cac` | 4 | `char **` | Root path table (`config[0]`, the table `root_path_table` below) | Stored by `container_init_file_thread`; read by `container_resolve_path` (`roots[root]`) | H |
| `+0x004` | `0x08920cb0` | 4 | SceUID | File thread id (return of `sceKernelCreateThread`, then started) | Store after the create call in `container_init_file_thread` | H |
| `+0x008` | `0x08920cb4` | 32 × `0x60` | request[32] | Request ring (below) | Slot address `block + 8 + 0x60·index` in `container_read_async` and `container_take_request` | H |
| `+0xc08` | `0x089218b4` | 4 | u32 | Write index (0–31, wraps at 32) | `container_read_async` stores `index + 1` (0 when it reaches 32); `container_take_request` starts its scan there | H |
| `+0xc0c` | `0x089218b8` | 4 | SceUID | Semaphore `ehfile_sema` (1/1): lock around taking a slot | Created in `container_init_file_thread`; waited with a 100 µs timeout and signalled in `container_read_async`; deleted at shutdown | H |
| `+0xc10` | `0x089218bc` | 4 | SceUID | Semaphore `ehfile_queue` (0/32): one signal per queued request | Created in `container_init_file_thread`; signalled at the end of `container_read_async`; waited by the file thread | H |
| `+0xc14` | `0x089218c0` | 8 | — | Unknown (cleared with the block; no access found in the container functions) | — | L |

### Request (`0x60` bytes)

| Offset | Size | Type | Field | Evidence | Conf. |
| --- | --- | --- | --- | --- | --- |
| `+0x00` | 4 | u32 | `busy`: 1 while queued or running; cleared by the file thread after the callback accepts the result | `sw 1, 0(slot)` in `container_read_async`; `container_take_request` returns the first slot with `busy ≠ 0` | H |
| `+0x04` | 4 | u32 | `type`: 0 file read, 1 module load | `container_read_async` writes 0; the file thread dispatches 0 to `container_read_file`, 1 to `system_load_module` | H |
| `+0x08` | 4 | u32 | `root`: index into the root path table | Argument 0 of `container_read_async` | H |
| `+0x0c` | 4 | `void *` | `dest`: destination buffer | Argument 2 | H |
| `+0x10` | 4 | u32 | `offset` in the file (seek only when > 0) | Argument 3; `container_read_file` | H |
| `+0x14` | 4 | u32 | `size` to read | Argument 4 | H |
| `+0x18` | 4 | function pointer | `callback(arg, bytes_or_error) → accept`; the file thread repeats the operation while it returns 0 | Argument 5; `container_file_thread` | H |
| `+0x1c` | 4 | u32 | `arg` passed to the callback | Argument 6 | H |
| `+0x20` | 64 | char[64] | Relative path, at most 63 characters (`system_strncpy(slot+0x20, rel, 0x3f)`), NUL-terminated by the cleared block | `container_read_async` | H |

Note for the port: `container_read_async` fills the slot after releasing `ehfile_sema` and does not check `busy` before reusing a slot; the game relies on never having more than 32 requests outstanding (observation from the code, medium).

## `root_path_table`: root path table (`0x0889fb24`, 9 pointers + terminator)

Ten `u32` words: nine pointers to NUL-terminated ASCII paths (stored unrelocated in the file, `0x0009ba0c` etc., i.e. `0x0889fa0c` onward at run time) and a zero word. Passed to `container_init_file_thread` as `config[0]`; `container_resolve_path(buf, root, rel, …)` builds `roots[root] + rel`.

| Index | Path (prefix `disc0:/PSP_GAME/USRDIR/`) | Known use |
| --- | --- | --- |
| 0 | `module/` | Sony and library modules |
| 1 | `kmodule/` | — |
| 2 | `gmodule/` | Game PRX modules (`modules.md`) |
| 3 | (empty: `USRDIR/` itself) | — |
| 4 | `duel/` | Duel archives |
| 5 | `duelsys/` | `cardinfo_<lang>.ehp` (`card_db_load_cardinfo` passes root 5) |
| 6 | `main/` | — |
| 7 | `snd/` | Sound bank |
| 8 | `minigame/` | Minigame archives |

Evidence: the bytes of the table and the strings (high); root 5 matches the `duelsys/cardinfo_*.ehp` files on the disc and the `container_get_file_size(5, …)` call in `card_db_load_cardinfo` (high). The strings are packed with 4-byte alignment; only the pointers matter. Paths on `disc` are rewritten to `disc0:/sce_lbn0x…_size0x…` through the file index (`file-index.md`) when the index is ready.

## `heap_header`: HOGE heap header (16 bytes) and block table

The game's own heaps (`system_heap_create`, `0x0882622c`): the 0x4000-byte heap at `0x08ac2580` and the 0x280000-byte audio heap at `0x08acda40` (`system.md`, "Heaps"). The header is followed by the block table, which describes the heap as a sorted list of block start addresses.

| Offset | Size | Type | Field | Evidence | Conf. |
| --- | --- | --- | --- | --- | --- |
| `+0x00` | 4 | u32 | Magic `0x45474f48` (`"HOGE"`) | `lui 0x4547; ori 0x4f48; sw 0(heap)` | H |
| `+0x04` | 4 | bitfield | bits 0–1: cleared at creation (flags, meaning unknown); bits 2–7: 0x3f when the heap was built in caller memory, 0 when `system_heap_create` allocated it itself (`system_memalign`); bits 8–31: heap size in bytes (rounded down to 16 for caller memory) | Byte/word masking in `system_heap_create`; `system_heap_contains` uses `word >> 8` as the size | H (size), M (bits 2–7), L (bits 0–1) |
| `+0x08` | 4 | `u32 *` | Block table pointer, initially `heap + 0x10` | `system_heap_create`; `system_heap_get_free_used` reads the table through it | H |
| `+0x0c` | 2 | u16 | Table capacity in bytes, initially `0x80` (32 entries), kept a multiple of 16 | `system_heap_create`; `system_heap_alloc_ex` grows the table (`system_heap_grow_table`) when capacity < `(count + 2) × 4` | H |
| `+0x0e` | 2 | u16 | Number of blocks (`count`); the table holds `count + 1` words, the last being the end marker | Initially 3 with 4 words written | H |

Block table entry (u32): bits 0–30 the block's start address, bit 31 the free flag (set = free). The size of block `i` is `entry[i+1] − entry[i]` (masked with `0x7fffffff`); the entry after the last block is the end marker `heap + size`. Allocation clears bit 31 (`system_heap_alloc_ex`), `system_heap_free` sets it and merges neighbours.

Initial table written by `system_heap_create` (high):

| Entry | Address | Free | Block |
| --- | --- | --- | --- |
| 0 | `heap` | no | The 16-byte header |
| 1 | `heap + 0x10` | no | The block table itself (capacity `0x80`) |
| 2 | `heap + 0x90` | yes | All remaining memory |
| 3 | `heap + size` | — | End marker |

Allocation rounds the size up to 16, picks the best-fitting free block (`system_heap_find_best_fit`) and splits it when it is more than `0x40` bytes larger (`system_heap_split_block`, with a direction argument: `system_heap_alloc` passes 1). The table may be moved when it grows (`system_heap_relocate_block`). The splitting direction and table relocation details are described with the functions in `docs/subsystems/functions/system.md`; a port can use any allocator.

## `ui_resource_table`: per-scene UI resource records (12 bytes each)

Scene modules look up their UI members (textures, layouts, string tables) by a 16-bit id through a sorted table of records. In `rel_deck` the table is at `0x08ebd84c` (module `+0x22e4c`), 41 records with ids `0x8001`–`0x8045`; the same routine and record layout exist with their own tables in `rel_deckswap` (`+0x9c8c`), `rel_decktutorial` (`+0x11324`), `rel_select_card` (`+0xc334`), `rel_recipeviewer` (`+0x5ad4`) and `rel_shop` (`shop_get_archive_member`, 21 records). Prose: `docs/subsystems/ui.md`.

| Offset | Size | Type | Field | Evidence | Conf. |
| --- | --- | --- | --- | --- | --- |
| `+0x00` | 4 | u32 | `id` (`0x8000+`); the search compares only the low 16 bits | `ui_deck_find_resource` (`rel_deck:0x08eaa360`): binary search on `lhu 0(a1 + 12·mid)`; the table is sorted ascending (checked on all 41 records) | H |
| `+0x04` | 4 | `void *` | `cache`: the member pointer once found, 0 in the file | All 41 file values are 0; `ui_deck_get_resource` stores the result of `container_ehp_find_member` | H |
| `+0x08` | 4 | `char *` | `format`: member name or `sprintf` format with a `%c` for the language letter (`"jegfis"[save_get_language()]`; ids `0x8036`/`0x8037` use the region string `"jabgfisb"`) | Pointers into the module's string area (for example `cis_all.gim`, `panel.gim`); `ui_deck_get_resource` | H |

An `.ehf` member also gets its `.tmf` companion bound on first use (`ui.md`). `rel_field` uses a different 12-byte record (`{u32 ?, char *member, void *cache}` at `+0x2f548`, `ui_field_find_resource`), documented in `ui.md`; it is not this row.

## `card_language_suffixes`: language code table (`0x08878c88`, 6 × 8 bytes)

Six 8-byte slots, each a NUL-padded three-letter ASCII language code, indexed by `save_get_language()` (`0x08857b80`): 0 `jpn`, 1 `eng`, 2 `ger`, 3 `fra`, 4 `ita`, 5 `spa`.

| Offset | Size | Type | Field |
| --- | --- | --- | --- |
| `+0x00 + 8·lang` | 8 | char[8] | Code (3 characters + NUL padding) |

Uses: `card_db_load_cardinfo` (`0x08832684`) builds `cardinfo_<code>.ehp` (root 5, `duelsys/`); `card_db_append_language_suffix` (`0x08832718`) appends the first letter minus `0x20` (`J E G F I S`) and `.bin` (`0x0889f8b0`) to the member names (`CARD_Name_E.bin`, …). Evidence: the table bytes and both functions (high). The disc has no `cardinfo_jpn.ehp` (only `eng fra ger ita spa`), so index 0 is never used by this release (observation, high).
