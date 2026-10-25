# System and runtime library

Statically linked C runtime (newlib), libm and VFPU helpers in `BOOT.BIN`. Most names come from PPSSPP's hash recognition (`re/names-ppsspp.csv`, prefixed `system_` and `system_vfpu_`); the table lists the ones that were also checked by reading the code.

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x088115e4` | `system_strcpy` | H | Word-at-a-time copy with the `(x + 0xfefefeff) & ~x & 0x80808080` zero-byte test, then a byte loop up to NUL. PPSSPP: `strcpy`. |
| `0x088113c0` | `system_strcat` | H | Finds the end of `dst` with the same test, then calls `system_strcpy`. PPSSPP: `strcat`. |
| `0x0881166c` | `system_strlen` | H | Byte loop returning the distance to NUL. PPSSPP: `strlen`. |
| `0x0880a4a4` | `system_bsearch(key, base, n, size, cmp)` | H | Binary search returning the element or 0. |
| `0x0880f844` | `system_qsort(base, n, size, cmp)` | H | Same comparator as the `bsearch` on the same array. PPSSPP: `qsort`. |
| `0x08810f5c` | `system_sprintf(buf, fmt, ...)` | M | Called with a `%04x` format; body not read. |
| `0x0880d398` | `system_malloc(size)` | H | Calls `system_malloc_r` (`0x0880d3f0`, PPSSPP `_malloc_r`) with the reentrancy struct from `0x0880ce2c`: newlib's `malloc`. |
| `0x0880d3c4` | `system_free(ptr)` | H | Same pattern with `system_free_r` (`0x0880c504`). |

## The `libehsys_rel` export library

`BOOT.BIN` exports one library to the game modules in `gmodule/`: `libehsys_rel`, 1,556 functions and 2 variables (`.lib.ent`, NID and address tables in `.rodata.sceResident`). Modules import it by NID; `rel_duel_eng.prx` imports all 1,556 functions. `tools/prx_imports.py` resolves a module's imports against this table and names each import stub `thunk_<target name>` in the target's group (`re/names-imports-<module>.csv`); stubs whose target is still unnamed stay `thunk_FUN_<address>` and count as unknown. Pointers inside both files are unrelocated module offsets (`BOOT.BIN` is itself a relocatable PRX), so `BOOT.BIN` targets are `0x08804000 + offset`.

This also explains functions with no caller inside `BOOT.BIN`, such as `container_gzip_decompress`: they are part of the export library and are called from modules.

`libehsys_rel` has only 1,530 distinct NIDs among its 1,556 entries. 68 entries re-export `BOOT.BIN`'s own firmware import stubs under their Sony NIDs. The module loader (scene slot, module registry, descriptor tables) and the catalogue of all 37 modules are in `modules.md` (`tools/modules.py`).

## Open questions

- `0x0880ce2c` presumably returns newlib's `_impure_ptr` (reentrancy struct); confirm.
- Heap size and placement (needed later for memory-budget estimates on 3DS).
