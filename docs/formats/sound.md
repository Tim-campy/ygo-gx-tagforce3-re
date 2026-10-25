# Sound banks (`snd/psp_snddat.bin`)

Status: `reimplemented`. `tools/sound.py` walks the whole file, and `--check` passes on the reference disc: 728 banks, 30,779 cues, 18,608 distinct RIFF waves and 107 PS-ADPCM cues. It exports one cue at a time (`--export BANK:CUE`): a RIFF wave as `.at3`, a PS-ADPCM layer decoded to a 16-bit PCM `.wav`. Field meanings marked as hypotheses below are not verified in PPSSPP. Exports go under `extracted/` and are never committed.

`PSP_GAME/USRDIR/snd/psp_snddat.bin` (138,645,504 bytes) is the only file in `snd/`. `BOOT.BIN` holds the strings `disc0:/PSP_GAME/USRDIR/snd/` (file offset `0x9bb38`) and `psp_snddat.bin` (`0x9d640`). It imports `sceAtrac3plus` (`0x6f04c`) and `sceSasCore` (`0x6f070`), and names `libatrac3plus.prx` and `sc_sascore.prx`. The waves are ATRAC3/ATRAC3plus (decoded with libatrac3plus), and the ADPCM layers use sceSas pitch units (see below). So the game plays this file with both libraries. That last point is an inference from imports and data: no call site was traced.

All integers are little-endian.

## Chain of banks

The file is a sequence of **banks** with no directory. Each bank starts with `"SP"` and gives its own size. The next bank starts right after it, and the last bank ends exactly at the end of the file (`0x8439000`).

| Offset in bank | Size | Field |
| --- | --- | --- |
| `0x00` | 2 | Magic `"SP"`. |
| `0x02` | 2 | Serial: 0, 1, 2, … in file order (0–727). |
| `0x04` | 4 | Bank size in bytes, footer and padding included; always a multiple of 2048 (one UMD sector). |
| `0x08` | 4 | Cue table offset; always `0x30`. |
| `0x0C` | 4 | Layer table offset (0 in music banks). |
| `0x10` | 4 | ADPCM sample area offset (0 in music banks). |
| `0x14` | 4 | Wave area offset (RIFF waves). |
| `0x18` | 4 | Envelope table offset; equals the end of the wave area (0 in music banks). |
| `0x1C` | 4 | End of the used data, i.e. end of the envelope table (0 in music banks). |
| `0x20` | 16 | ASCII label, NUL-padded, for example `"252041 YUGI_GX3"`. |
| `0x30` | 32 × n | Cue table. |
| … | | Layer table, ADPCM area, wave area, envelope table, in this order. Each starts where the previous one ends: no gaps, checked on every bank. |
| size − 4 | 4 | Footer: `"EP"` + the bank's serial as `u16`. Every byte between the used data and the footer is zero. |

The number of cues is (first non-zero offset among `0x0C`, `0x10`, `0x14`) − `0x30`, divided by 32. In banks without PS-ADPCM, the layer, ADPCM and wave offsets are equal. In the 48 music banks, the layer, ADPCM, envelope and end fields are 0.

Basis: the chain walk reaches the end of the file exactly; all 728 serials are in sequence; all 728 footers match; `tools/sound.py --check`.

## Cue: 32 bytes

| Offset | Size | Field |
| --- | --- | --- |
| `0x00` | 1 | Volume, 0–127 (`0x7F` and `0x50` are common). Hypothesis, medium: the same byte opens every envelope record. |
| `0x01` | 1 | Pan, `0x40` = centre (`0x00` and `0x7F` also occur in envelopes). Hypothesis, medium. |
| `0x02` | 2 | Flags: 0 in 30,767 cues; 3 (×9, mostly bank 725), 4 (×2), 15 (×1). Meaning unknown. |
| `0x04` | 2 | 0, except 1024 in four cues (banks 431, 438, 458, 465, cue 110). Unknown. |
| `0x06` | 2 | Layer count `k`: 0 = one RIFF wave (30,672 cues); 1 (×103) or 2 (×4) = PS-ADPCM layers. |
| `0x08` | 4 | Target. If `k = 0`, the offset of the wave from the wave area. If `k > 0`, the offset from the layer table of `k` consecutive layer entries. |
| `0x0C` | 4 | Always 0. |
| `0x10` | 1 | 0 (×26,110), 2, 3, 4, 5 or 6. Unknown (possibly a priority or a voice group). |
| `0x11` | 1 | 0, except 4 and 6 once each. Unknown. |
| `0x12` | 6 | Always 0. |
| `0x18` | 4 | Duration in milliseconds. For RIFF cues it agrees with the `fact` sample count ÷ 44,100 to within 2 ms in all 30,672 cases. For ADPCM cues it is within a few ms of (frames × 28 ÷ rate). |
| `0x1C` | 4 | Always 0. |

Several cues can share one wave: 30,672 RIFF cues point to 18,608 distinct waves. The cue index, not the wave, is presumably what the game requests. Hypothesis, medium: the 145-cue voice banks below line up with the 145-entry voice tables in `charalist.ehp`.

## Wave area: RIFF waves

Each wave is a `u32` length followed by that many bytes of a standard RIFF/WAVE file, whose own RIFF size field is length − 8. The waves follow each other with no padding, in offset order. Codecs over the 18,608 distinct waves:

| `fmt` tag | Codec | `fmt` size | Mono | Stereo | Block align |
| --- | --- | --- | --- | --- | --- |
| `0xFFFE` (WAVE_FORMAT_EXTENSIBLE) | ATRAC3plus | 52 | 18,455 | 53 | 192, 280 (mono); 280, 376 (stereo) |
| `0x0270` | ATRAC3 | 32 | 55 | 45 | 192 |

All waves are 44,100 Hz. Chunks: `fmt `, `fact`, `data`, plus `smpl` in 58 waves. Such a wave is what PSP tools call an `.at3` file, so the exporter writes it unchanged.

## PS-ADPCM layers (only in 15 banks)

Only bank 65 and banks 712–718 and 720–726 use them.

- **Layer table** (header `0x0C`): 8-byte entries `(u32 sample_offset, u32 envelope_offset)`. The first is relative to the ADPCM area, the second to the envelope table. A cue with `k` layers uses `k` consecutive entries starting at its target.
- **ADPCM sample** (header `0x10` + sample offset): `u32 length`, `u16 pitch`, `u16 rate`, then `length` bytes of PS-ADPCM. Rates are 11,025, 18,000, 22,050, 32,000 and 44,100 Hz. `pitch = rate × 4096 / 44100`, rounded down, in all 111 layers (4096 for 44.1 kHz, 2048 for 22.05 kHz): the sceSas pitch scale, where `0x1000` is unshifted.
- **PS-ADPCM data**: 16-byte frames, the same coding as the PlayStation SPU. Byte 0 holds the shift in its low nibble and the predictor in its high nibble. Byte 1 holds the flags. The remaining 14 bytes hold 28 signed 4-bit samples, low nibble first. Every sample starts with an all-zero frame. 107 layers end with flag 7, after a frame with flag 1 (the classic one-shot ending). Four layers use flags 2/6 inside and end with 3: loop markers. The decoder in `tools/sound.py` uses the standard filters `(0,0) (60,0) (115,−52) (98,−55) (122,−60)` ÷ 64.
- **Envelope record** (header `0x18` + envelope offset): 24 bytes.

  | Offset | Field |
  | --- | --- |
  | `0x00` | Volume. |
  | `0x01` | Pan. |
  | `0x04` | `u32` always `0x1FE0800F`. Hypothesis, medium: SPU-style ADSR1/ADSR2 (`0x800F`, `0x1FE0`), which sceSas also takes. |
  | `0x08` | `u16, u16`: (1, 1) in exactly the 4 records used by the 4 looping samples, otherwise (0, 0). |
  | `0x0D` | 60 (`0x3C`), probably a root note (middle C). |
  | `0x0E` | `u16` `0x1000`. |

  The remaining bytes are 0.

## What the banks hold

The table groups the banks by serial range, label and content.

| Serials | Label(s) | Content |
| --- | --- | --- |
| 0–47 | `02d2520 41` (0–3), `02d2520 42` (4–47) | One cue and one stereo ATRAC3plus wave each, from 2.9 s to over a minute long. Music, by length and channel count (high confidence). |
| 48–711 | `091403`–`091407 YUGI_GX3`, `152039`, `252040`, `252041` | Mono ATRAC3plus. 166 banks have exactly 145 cues and 99 have exactly 52. Character voices, by content (medium confidence). Bank 65 also has one ADPCM cue. |
| 712–727 | `252041 YUGI_GX3` | Short ATRAC3 waves (mono and stereo, up to 8.4 s) mixed with PS-ADPCM layers. Sound effects (medium confidence). |

Treat the labels as build stamps, not as types. Hypothesis, low: the digits look like times. The same label appears in unrelated ranges.

`database/charalist.ehp` holds 95 `chrcutin_<name>_voiceidchgtbl.bin` members of about 944 bytes. Each starts with 16 `u32` byte offsets to `u16` sub-tables. In `chrcutin_aska01` the first three sub-tables have exactly 145 entries, with values below 145. Hypothesis, medium: each sub-table maps a voice event to a cue index in one of the 145-cue voice banks. Not decoded further.

## Cross-check with ygotfToolkit

Its `sound` command (read-only, run on the maintainer's image on 2026-10-25):

- It lists 18,608 clips, the number of distinct RIFF waves found here.
- Its "BGM" filter gives 150 clips. That is the number of RIFF waves in the 60 banks that contain at least one stereo wave (0–47 plus 12 banks in 713–727). It classifies by bank, so its "BGM" set includes short stereo sound effects.
- Its clip numbers are wave ordinals within a bank. With that mapping, codec, channel count and RIFF size agree for every clip.
- In the 15 banks with ADPCM cues, its listed durations are shifted: they are taken from the cue at the wave's ordinal, and that cue may be an ADPCM cue. The durations here come from the cue that points at the wave, and they agree with that wave's `fact` chunk.
- It shows no PS-ADPCM layers.

## Open questions

- Cue flags (`0x02`), `0x04`, `0x10` and `0x11`, and envelope bytes `0x08`–`0x0B`: how the player uses them (trace the sceSas/sceAtrac calls in PPSSPP).
- Whether the game addresses sounds as (bank serial, cue index) and where that mapping lives in code. No call site has been traced yet.
- The voice-bank structure: why there are 145-cue and 52-cue banks, and how `*_voiceidchgtbl.bin` selects among them.
- Whether the `smpl` chunks in 58 waves carry loop points that the game uses for music.
