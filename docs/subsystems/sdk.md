# System library imports (`sdk`)

`BOOT.BIN` imports 278 functions from 31 libraries through `.lib.stub` (`0x08872c38`, 20 bytes per library). Each import is an 8-byte stub in `.sceStub.text` (`0x0887234c`–`0x08872bfb`), in the same order as its NID in `.rodata.sceNid`. Per CLAUDE.md, Sony's library internals are not documented; only which functions the game uses.

## Libraries

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

No compression library (such as `sceDeflt`) is imported.

Hints for later packages: `sceAtrac3plus` and `sceSasCore` (audio, WP9), `sceMpeg` (the `movie/*.pmf` files), `sceLibFont` (system fonts are used for at least some text, WP7), the `sceNetAdhoc*` family (ad-hoc multiplayer, outside the port's first scope).

## Named stubs

The stub address is `0x08872364 + 8 × index` for `IoFileMgrForUser`, where `index` is the position of the NID in its table at `0x08876208`. The names come from the publicly documented NIDs.

| Stub | NID | Name |
| --- | --- | --- |
| `0x0887239c` | `0x6A638D83` | `sceIoRead` |
| `0x088723b4` | `0x810C4BC3` | `sceIoClose` |
| `0x088723e4` | `0xACE946E8` | `sceIoGetstat` |
| `0x0887243c` | `0x109F50BC` | `sceIoOpen` |
| `0x08872454` | `0x27EB27B8` | `sceIoLseek` |

## Open questions

- Name the remaining 273 stubs by importing a PPSSPP `.sym` file (`PpssppImportSymFile` from ghidra-allegrex), which also confirms the image base at runtime.
