# Save data (work package 3)

Status: `named` (container and buffer located; contents not yet mapped).

## On the memory stick

`PSP/SAVEDATA/ULES011830001/` holds `DATA0` (the game state), `PARAM.SFO`, `ICON0.PNG` and `PIC1.PNG`, written through the system's `sceUtilitySavedata` dialog. A retail-style save is encrypted by the PSP save-data layer: `DATA0` is 131,088 bytes (the 131,072-byte buffer plus 16 bytes added by the encryption) with a byte entropy of 7.999 bits/byte. Decrypting it would circumvent platform protection (`CLAUDE.md`), so analysis uses saves that PPSSPP writes unencrypted (`EncryptSave = False` in `ppsspp.ini`).

## In the game

| Address | Meaning |
| --- | --- |
| `0x08acda04` | `SceUtilitySavedataParam` block (`0x9d0` bytes, zeroed). |
| `0x08acda08` | Save buffer, `0x20000` bytes: the whole content of `DATA0`. |
| `0x08acda0c` | Buffer for a disc file loaded with the save (root 6, name from `0x088413ec`; presumably an icon or picture). |
| `0x08acda10` | `0x200`-byte work block. |
| `0x08acda00` | Heap the four blocks come from. |

`save_open` (`0x088410dc`) allocates the four blocks; `save_close` (`0x0883e3b4`) frees them. Six functions fill the parameter block and call `sceUtilitySavedataInitStart` (`0x0883e694`, `0x0883e78c`, `0x0883e874`, `0x0883e918`, `0x0883e9e0`, `0x0883eaa4`). The two read so far set the mode at `+0x30` (8 and `0x16`), the data buffer at `+0x74` (`*0x08acda08`), buffer and data size at `+0x78`/`+0x7c` (`0x20000`), the file name `DATA0`, and copy a 16-byte value from `0x08879068` to `+0x5dc`, the field that holds the game's save-data key. This project records that the key exists and does not use it.

## Open questions

- Which code copies the buffer to and from the game state, and the layout of that state (deck records, card collection, story flags, the per-card limit status, settings).
- What modes 8 and `0x16` and the other four callers do (save, load, list, delete, size query).
