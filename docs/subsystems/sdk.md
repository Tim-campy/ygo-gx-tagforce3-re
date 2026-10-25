# System library code (`sdk`)

Per CLAUDE.md, Sony's library internals are not documented; this file records which library code the game uses and where it sits.

## Imports

`BOOT.BIN` imports 278 functions from 31 libraries through `.lib.stub` (`0x08872c38`, 20 bytes per library). Each import is an 8-byte stub in `.sceStub.text` (`0x0887234c`–`0x08872bfb`), in the same order as its NID in `.rodata.sceNid`. All 278 stubs are named in Ghidra from a PPSSPP `.sym` export (`re/names-ppsspp.csv`).

| Library | Functions | Library | Functions |
| --- | --- | --- | --- |
| `ThreadManForUser` | 48 | `sceUtility` | 19 |
| `IoFileMgrForUser` | 33 | `sceSasCore` | 18 |
| `sceMpeg` | 25 | `sceNetAdhoc` | 14 |
| `sceGe_user` | 12 | `ModuleMgrForUser` | 11 |
| `sceNetAdhocctl` | 10 | `sceAtrac3plus`, `sceLibFont`, `sceNetAdhocMatching` | 9 each |
| `SysMemUserForUser` | 8 | `UtilsForUser` | 7 |
| `sceDisplay`, `sceAudio`, `sceUmdUser`, `sceNet` | 6 each | `InterruptManager`, `LoadExecForUser`, `StdioForUser`, `sceCtrl` | 3 each |
| `Kernel_Library` | 2 | `sceSuspendForUser`, `sceDmac`, `sceOpenPSID`, `sceRtc`, `sceWlanDrv`, `scePower`, `sceNetIfhandle`, `sceImpose` | 1 each |

Cross-check: before the `.sym` import, five `IoFileMgrForUser` stubs were named by hand from their NIDs (stub = `0x08872364 + 8 × NID index`): `sceIoRead` `0x0887239c` (`0x6A638D83`), `sceIoClose` `0x088723b4` (`0x810C4BC3`), `sceIoGetstat` `0x088723e4` (`0xACE946E8`), `sceIoOpen` `0x0887243c` (`0x109F50BC`), `sceIoLseek` `0x08872454` (`0x27EB27B8`). PPSSPP assigns the same five names.

Hints for later packages: `sceAtrac3plus` and `sceSasCore` (audio, WP9), `sceMpeg` (the `movie/*.pmf` files), `sceLibFont` (system fonts are used for at least some text, WP7), the `sceNetAdhoc*` family (ad-hoc multiplayer, outside the port's first scope).

## Statically linked Sony libraries

| Library | Where | Basis |
| --- | --- | --- |
| `libgu` / `libgup` (`sceGu*`, `sceGup*`, `dl_write_*`) | `0x08804f70`–`0x08807dac` | PPSSPP hash recognition. |
| `libvfpu` (`sceVfpu*`) | `0x088194ac`–`0x0881b3b0` | PPSSPP hash recognition. |
| `libdeflt` (gzip/deflate) | `0x08817950`–`0x08817e4b` | See below. |

### libdeflt

No deflate library is imported, but `BOOT.BIN` contains its own copy of Sony's `libdeflt` API. Confidence: high for the gzip entry points, medium-high for the inflater.

| Address | Name | Evidence |
| --- | --- | --- |
| `0x08817bb8` | `sceGzipIsValid(buf)` | Returns 1 when the first bytes are `1F 8B`. |
| `0x08817a2c` | `sceGzipGetInfo(buf, &extra, &name, &comment, &crc16, &data)` | Six output parameters as in the public API; parses `FEXTRA`, `FNAME`, `FCOMMENT` from the flag byte; error `0x80000103`. |
| `0x08817b80` | `sceGzipGetCompressedData(buf)` | Calls `sceGzipGetInfo` and returns only the data pointer. |
| `0x08817950` | `sceGzipDecompress(dst, dst_size, src, &crc32)` | Requires CM byte `== 8`, inflates, checks the result against the trailer's `ISIZE`, returns the trailer's CRC-32; errors `0x80000108`/`0x80000004`. |
| `0x08817bf0` | `sceDeflateDecompress(dst, dst_size, src, &next)` | Bit reader with 2-bit block type and dynamic Huffman header; its code-length order table at `0x08878646` ends with DEFLATE's `0 8 7 9 6 10 5 11 4 12 3 13 2 14 1 15`. PPSSPP's hash database labels it `openseason_data_decode`, so the same code exists in another game. |

## Open questions

- PPSSPP saw about 17,500 more function entries in user memory outside `BOOT.BIN` (`0x08E…`, `0x098…`, `0x09B…`–`0x09D…`); these are presumably the `gmodule/*.prx` modules loaded at runtime. Map each range to its module.
