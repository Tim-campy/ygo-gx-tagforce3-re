# System and runtime library

Statically linked C library and runtime helpers in `BOOT.BIN`. Named only when the body itself shows the behaviour, not just the call sites.

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x088115e4` | `system_strcpy` | H | Word-at-a-time copy with the `(x + 0xfefefeff) & ~x & 0x80808080` zero-byte test, then a byte loop up to NUL; returns `dst`. |
| `0x088113c0` | `system_strcat` | H | Finds the end of `dst` with the same zero-byte test, then calls `system_strcpy`. |
| `0x0881166c` | `system_strlen` | H | Byte loop returning the distance to NUL. |
| `0x0880a4a4` | `system_bsearch(key, base, n, size, cmp)` | H | Binary search returning the element pointer or 0. |
| `0x0880f844` | `system_qsort(base, n, size, cmp)` | M | Same argument shape and comparator as the `bsearch` call on the same array; body (2,392 bytes) not read yet. |
| `0x08810f5c` | `system_sprintf(buf, fmt, ...)` | M | Called with a `%04x` format and two values; body not read yet. |
| `0x0880d398` | `system_heap_alloc(size)` | M | Gets the default heap (`0x0880ce2c`) and allocates from it (`0x0880d3f0`); paired with `system_heap_free` on the same pointers. |
| `0x0880d3c4` | `system_heap_free(ptr)` | M | Default heap, then `0x0880c504`. |

## Open questions

- Heap implementation behind `0x0880ce2c`, `0x0880d3f0` and `0x0880c504` (needed later for memory-budget estimates on 3DS).
