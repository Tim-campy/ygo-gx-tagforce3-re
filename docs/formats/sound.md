# Sound banks (`snd/psp_snddat.bin`)

Status: `reimplemented`. `tools/sound.py` walks the whole file, and `--check` passes on the reference disc: 728 banks, 30,779 cues, 18,608 distinct RIFF waves and 107 PS-ADPCM cues. It exports one cue at a time (`--export BANK:CUE`): a RIFF wave as `.at3`, a PS-ADPCM layer decoded to a 16-bit PCM `.wav`. `tools/audio_convert.py` converts the whole file to WAV/OGG/FLAC with FFmpeg and checks every stream (see "Decoding to PCM"). Field meanings marked as hypotheses below are not verified in PPSSPP. Exports go under `extracted/` and are never committed.

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

Several cues can share one wave: 30,672 RIFF cues point to 18,608 distinct waves. The game requests cues, not waves: a global sound id is a bank's first id plus the cue index (see "Sound ids").

## Wave area: RIFF waves

Each wave is a `u32` length followed by that many bytes of a standard RIFF/WAVE file, whose own RIFF size field is length − 8. The waves follow each other with no padding, in offset order. Codecs over the 18,608 distinct waves:

| `fmt` tag | Codec | `fmt` size | Mono | Stereo | Block align |
| --- | --- | --- | --- | --- | --- |
| `0xFFFE` (WAVE_FORMAT_EXTENSIBLE) | ATRAC3plus | 52 | 18,455 | 53 | 192, 280 (mono); 280, 376 (stereo) |
| `0x0270` | ATRAC3 | 32 | 55 | 45 | 192 |

All waves are 44,100 Hz. Chunks: `fmt `, `fact`, `data`, plus `smpl` in 58 waves. Such a wave is what PSP tools call an `.at3` file, so the exporter writes it unchanged.

Codec details (all from `tools/audio_convert.py --survey`; byte layouts checked on every wave):

| Codec | Channels | Block (bytes) | Samples per block | Bitrate (bit/s) | Waves |
| --- | --- | --- | --- | --- | --- |
| ATRAC3plus | 1 | 192 | 2048 | 33,075 | 18,443 |
| ATRAC3plus | 1 | 280 | 2048 | 48,234 | 12 |
| ATRAC3plus | 2 | 280 | 2048 | 48,234 | 19 |
| ATRAC3plus | 2 | 376 | 2048 | 64,772 | 34 |
| ATRAC3 | 1 | 192 | 1024 | 66,150 | 55 |
| ATRAC3 | 2 | 192 | 1024 | 66,150 | 45 |

- **ATRAC3plus `fmt `** (52 bytes): `WAVE_FORMAT_EXTENSIBLE` (`0xFFFE`), channels, 44,100, average bytes per second (block × 44,100 / 2048), block align, bits 0, cbSize 34, `0x0800` (samples per block, in the "valid bits" slot), channel mask (1 mono, 3 stereo), the sub-format GUID `E923AABF-CB58-4471-A119-FFFA01E4CE62`, `u16` 1, then a **big-endian 16-bit codec word** and 8 zero bytes. The codec word is the one OMA headers and the PSMF frame headers use: bits 0–9 = block / 8 − 1, bits 10–12 = channels, bits 13–15 = rate index (1 = 44,100 Hz). Disc values: `0x2417` (mono 192), `0x2422`/`0x2822` (280), `0x282E` (stereo 376).
- **ATRAC3 `fmt `** (32 bytes): tag `0x0270`, cbSize 14 and 14 bytes of ATRAC3 extra data (`u16` 1, `u32` `0x0800` mono or `0x1000` stereo, coding-mode words), passed to the decoder unchanged.
- **`fact`** (8 bytes in every wave): `u32 sample_count`, `u32 first_sample_offset`. The offset is 2048 (ATRAC3plus) or 1024 (ATRAC3) in 18,550 waves; the other 58 have other values (2,077–4,088 in the music banks).
- **`smpl`**: one loop each (36-byte header, one 24-byte loop record: start, end). The values count from `first_sample_offset`: output sample = stored value − offset, end inclusive. Basis: several music loops start exactly at the offset and every music loop that runs to the end stops at offset + sample_count − 1 (bank 2: offset 3,496, samples 3,227,880, loop end 3,231,375). 47 of the 48 music waves have a loop (all but bank 20), plus 5 ATRAC3plus and 6 ATRAC3 effect waves in banks 714–723. Bank 47 loops on a middle part (loop end before the last sample). Whether the game uses the effect loops is not known.

## Decoding to PCM (install-time conversion)

No ATRAC decoder is written for the project. The RIFF waves are complete `.at3` files that **FFmpeg** reads as they are (`wav` demuxer, `atrac3` and `atrac3p` decoders; checked with FFmpeg 7.1.1), so the conversion is a step the port's installer runs on the user's own disc, never a converted copy that the project distributes.

`tools/audio_convert.py` does this step:

```
python3 -I tools/audio_convert.py <USRDIR>/snd/psp_snddat.bin --survey              # codec census, no decoding
python3 -I tools/audio_convert.py <USRDIR>/snd/psp_snddat.bin --check [--jobs 12]   # decode all, write nothing
python3 -I tools/audio_convert.py <USRDIR>/snd/psp_snddat.bin -o <scratch>/snd [--format wav|ogg|flac] [--bank N ...]
```

For each distinct stream of a bank (a RIFF wave shared by several cues is decoded once):

1. Pipe the stored RIFF bytes into `ffmpeg -f wav -i pipe:0 -f s16le pipe:1` (FFmpeg on PATH or `--ffmpeg`).
2. Check the decoded length: exactly `frames × samples per frame` (2048 for ATRAC3plus, 1024 for ATRAC3).
3. Trim: drop `first_sample_offset + decoder delay` samples, keep `sample_count`. The decoder delay is **368** samples for ATRAC3plus and **69** for ATRAC3. Basis: with these values the number of stored frames equals ⌈(offset + delay + sample_count) / frame size⌉ for all 18,608 waves, while with no delay the count would not match for 3,472 waves (high confidence); PPSSPP's sceAtrac emulation skips the same amounts (`0x170` / `0x45`).
4. PS-ADPCM layers are decoded natively (`sound.decode_adpcm`, no FFmpeg). Their loop is taken from the frame flags: the first frame with flag bit 2 starts it, the frame with the end bit (bit 0) and bit 1 ends it (end = last sample of that frame).
5. Write `snd_<bank>_<first cue>[_<layer>].<wav|ogg|flac>`. OGG Vorbis (quality 6) and FLAC are encoded by a second `ffmpeg` call; OGG files get `LOOPSTART` / `LOOPLENGTH` tags.
6. Write `snd_<bank>.json`: label, and per cue the volume, pan, flags, duration, the 24-byte envelope records (ADPCM, hex) and per stream codec, channels, rate, bitrate, block align, sample count, file name and `loop` (`{start, end}` in output samples, or `null`).

`--check` runs steps 1–4 for every stream and also compares each trimmed length with the duration of every cue that uses it (within 2 ms) and each loop with the stream length. Result on the reference disc, about 3 minutes with 12 jobs:

```
ok: 728 banks, 18716 streams decoded: ATRAC3 100 (2.6 min), ATRAC3plus 18508 (478.2 min), PS-ADPCM 108 (0.7 min)
```

(18,716 = 18,608 RIFF waves + 108 distinct ADPCM samples; the 111 layers share three.) FFmpeg prints "non monotonically increasing dts" warnings for ATRAC3plus in WAV when it writes to a muxer; they do not affect the decoded samples (the decoded length is checked) and the tool runs it with `-loglevel fatal`.

Tests on synthetic data only: `tools/tests/test_audio_convert.py` (the RIFF wrapper bytes, the codec word, trimming, loops, a bank converted with a stub in place of FFmpeg).

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

Banks 48–711 form **voice groups** of seven banks: a voice set of three banks with the same cue layout (145 cues for named characters, 149 for one, 52 for generic students), then four small banks of 2, 1, 1 and 1 cues. Some characters add extra groups of four small banks only (for example banks 129–140 for the three Syrus variants). See "Character voices" below.

## Sound ids (`BOOT.BIN`)

`BOOT.BIN` addresses sounds by a global id, through two tables indexed by bank serial (728 entries each):

| Address | Type | Content |
| --- | --- | --- |
| `0x0889cf20` | `u32[728]` | Byte offset of each bank in `psp_snddat.bin` (the file has no directory; this is it). |
| `0x0889da80` | `u16[728]` | Global sound id of the bank's cue 0. Banks 0–47 (music) have ids 0–47; the cues of banks 48–727 are numbered consecutively from 728, so `id = first[bank] + cue`. |

`0x08868874(bank)` returns `first[bank]` through a pointer in the sound state (`*0x08dd3004`, field `+0x20`), so the table is copied or referenced at run time from this static copy. Both tables match the bank chain exactly (`tools/voices.py --check`). The 16-byte records just before `0x0889cf20` (one per bank, the third word a size-like value) are not decoded.

## Character voices

Status: the mapping below is established from code in `rel_charalist.prx` (the voice test) and `BOOT.BIN`, and cross-checked against every table and bank by `tools/voices.py --check`. How the duel (`rel_duel_draw.prx`) picks among the three banks of a voice set is not traced.

### Character table (`BOOT.BIN` `0x088aa510`)

174 records of 148 bytes, sorted by `(u8 character, u8 variant)` at `+0x00`; `0x0885adb0(character, variant)` finds one with `bsearch` (`world_find_character`; comparator `world_compare_character_key`, `0x0885bcd0`: `u8` character, then the variant as a signed byte); `world_character_exists` (`0x0885b8dc`) tests that a record exists. `world_find_character` has 28 callers in `0x0885aca0`–`0x0885b984`, among them `audio_get_voice_bank` and `audio_get_voice_extra_bank`, whose callers are `0x08836c78`, `0x08841a6c` and `0x08841d88`. `audio_get_bank_first_sound_id` (`0x08868874`) is called by `0x088418b8`, `0x088419c4`, `0x08841a6c`, `0x08841d88` and `0x08868890`. Fields used here:

| Offset | Field |
| --- | --- |
| `+0x00` | `u8` character, `u8` variant (for example `07 00` Alexis, `07 01` her second costume). |
| `+0x04` | Pointer to the record name (`ASUKA_0`, `ZAKO_07_0`, …). |
| `+0x24` | Pointer to the duel cut-in archive name (`cutin_aska01.ehp`), or 0. |
| `+0x30` | First bank of the voice set (0 = no voice). Returned by `0x0885aef4(character, variant)` (0 for characters 0 and 1, the player). |
| `+0x34` | First of the four small banks (3 when there is no voice). Returned by `0x0885af24` when `+0x30 > 0`, else 0. |
| `+0x38` | Pointer to a voice/profile key (`ASUKA`, `SCHOOLBOY_NOM3`, …). |

### Voice ids

A character's voices are numbered by **voice id** (`rel_charalist` `0x5780`, which turns one into a global sound id):

- ids 0–4: `first[+0x34] + id`. Because the global ids run on across banks, these are cue 0 and 1 of the first small bank, then the single cue of each of the next three.
- ids 5 and up: `first[+0x30] + id − 5`, cue `id − 5` of the voice set's first bank.

The first bank of a voice set holds the full set of lines; the second and third have the same number of cues but reuse waves for more of them (Alexis: 127, 93 and 61 distinct waves for 145 cues). Hypothesis (medium): reduced sets for situations with less sound memory, for example tag duels with four duellists.

### Voice-test menu (`rel_charalist.prx`)

The menu lists 134 items (`VOICE TEST:%03d:%s`, `strTbl_<l>.bin` entry 43). Two parallel tables give each item its name and voices:

| Module offset | Type | Content |
| --- | --- | --- |
| `0xd82c` | `u16[134]` | `strTbl_<l>.bin` entry naming the item (48 distinct names, entries 14–62 except 43). |
| `0xd938` | `(s16, s16)[134]` | Voice id played first, then a second voice id or −1. |

Items 0–4 are Start Duel, Duel, Win, Lose and Draw (voice ids 0–4). Items 5–16 are the twelve "Own Turn (Ahead/Normal/Behind)" pairs (a line, then "my turn"), and the remaining items follow the voice ids in order: Draw!, Activate (Normal/Chain), Activate From Hand, the spell and trap types, Activate Flip Card, Activate Monster Effect, Pot of Greed, Graceful Charity, Activate Field Spell, Activate Main Spell, the summon types, Summon Main Monster (pairs), attacks, Direct Damage!, Battle Cry Before Attack, Attack With Main Monster (pairs), Set Card, MonsterSet, End Turn, Damage, Battle, Surprise, CounterUP and "2–5 Continuous hits" (voice ids 150–153, which only the 149-cue set has). Together the items cover voice ids 0–153 without gaps. The availability test at module `0x57f8` admits voice ids below 149 for most characters and also ids 149 (and up) only for characters 5, 6 and 18 under per-variant conditions (not fully decoded).

### `*_voiceidchgtbl.bin`: voice → caption

95 tables in `database/charalist.ehp`: 62 `chrcutin_<cut-in>_voiceidchgtbl.bin` and 33 `chrzakov<n>_voiceidchgtbl.bin` (n = 50–82). The same bytes are stored as `chr_voiceidchgtbl.bin` in `duel/cutin_<cut-in>.ehp` and `duel/zakov<n>.ehp`, next to `chr_wordstbl_<l>.bin` (a strTbl-format caption table per language: `u32 count`, `u32 table offset`, `u32 string base`, `count` `u32` offsets).

Layout: 16 `u32` byte offsets, each to a `u16` array that runs to the next offset; only the first seven are non-empty. Sub-table `k` has one entry per cue of the group's bank `k` (0–2 the voice set, 3–6 the small banks), and each entry is the index of that cue's line in `chr_wordstbl` (the caption shown in the cut-in). Evidence: the entry counts equal the cue counts for every table, including the 144-cue and 149-cue banks; cues that share a wave always share a caption index; the captions match the events (Alexis: voice id 5 → caption "I'm not holding anything back.", item "Own Turn (Ahead)"; the Win/Lose/Draw banks → her win, loss and draw lines). High confidence.

`rel_charalist` `0x5fb0(character, variant)` builds the member name as `"chr"` + the record's cut-in name without `.ehp` + `"_voiceidchgtbl.bin"` (format at module `0xddf4`). Exceptions found by the check:

- KAMYURA_1 and TANIYA_1 share their cut-in (and table) with variant 0 but have their own voice sets (banks 422 and 436); the entry counts match, the shared-wave pattern does not.
- KAGEMARU_1 (voice set 457) names `cutin_kagemaru01.ehp`, for which `charalist.ehp` has no table.
- Generic students (`ZAKO_*`, voice sets in banks 478–708) have no cut-in name in the record. `chrzakov<n>` matches the voice group starting at bank `478 + 7·(n − 50)` (entry counts and wave sharing agree for all 33). Hypothesis (medium): that is how the game pairs them; the code that picks `zakov%02d.ehp` (string in `rel_duel_draw.prx`) was not traced. The 52-cue sets do not follow the 145-cue voice-id layout, so their events are unknown.

`tools/voices.py <PSP_GAME> --check` runs all of the above; without `--check` it writes one CSV row per (character, voice-test item, voice id) with bank, cue, duration, caption index and caption (game text: keep the output in `extracted/`).

## Cross-check with ygotfToolkit

Its `sound` command (read-only, run on the maintainer's image on 2026-10-25):

- It lists 18,608 clips, the number of distinct RIFF waves found here.
- Its "BGM" filter gives 150 clips. That is the number of RIFF waves in the 60 banks that contain at least one stereo wave (0–47 plus 12 banks in 713–727). It classifies by bank, so its "BGM" set includes short stereo sound effects.
- Its clip numbers are wave ordinals within a bank. With that mapping, codec, channel count and RIFF size agree for every clip.
- In the 15 banks with ADPCM cues, its listed durations are shifted: they are taken from the cue at the wave's ordinal, and that cue may be an ADPCM cue. The durations here come from the cue that points at the wave, and they agree with that wave's `fact` chunk.
- It shows no PS-ADPCM layers.

## Bank writer and round trip

`sound.decode_bank(bank)` turns a bank into plain values in which every offset is an index: cues keep their fields (`CUE_FIELDS`) with `wave` (index of a distinct RIFF wave, in offset order) or `layer` (first layer entry) instead of `target`; layers name a sample and an envelope record; samples keep pitch, rate and PS-ADPCM bytes; envelopes are decoded with `ENVELOPE` (volume, pan, a `u16`, the ADSR word, the two loop `u16`, a byte, the note, the pitch and 8 trailing bytes). `sound.build_bank(model)` lays out header, cue table, layer table, ADPCM area, wave area (length-prefixed RIFFs) and envelope table back to back, zero-fills to the bank size and writes the `EP` footer; music banks keep the zero layer/ADPCM/envelope/end fields. `sound.build(models)` writes the chain. All 728 banks rebuild byte for byte, the 15 banks with PS-ADPCM layers included (`snd_cue` and `snd_adpcm_layer` are `reimplemented`):

```
python3 -I tools/roundtrip.py --check <PSP_GAME> --only snd_cue,snd_adpcm_layer
```

The `BOOT.BIN` bank offset and first-id tables (`boot_sound_tables`) are written by `voices.write_boot_tables()`; `voices.derive_boot_tables()` regenerates both from the bank sizes and cue counts, and the round trip checks that the derived tables equal the stored ones. The voice change tables (`*_voiceidchgtbl.bin`, 189 copies) are rebuilt by `voices.build_change_table()` (16 `u32` offsets from 64, then the `u16` sub-tables back to back). Both are `reimplemented`:

```
python3 -I tools/roundtrip.py --check <PSP_GAME> --only boot_sound_tables,voiceidchgtbl
```

## `SHDS` sound header in `BOOT.BIN` (2026-11-04)

The driver's sound header is a static block in `BOOT.BIN` at runtime address `0x0887b5e0` (file offset `0x77634`), magic `"SHDS"` (`0x53444853`). `audio_bind_sound_header` (`0x08867938`) accepts it when `u16 +0x08 & 0xfff0 == 0x50` and stores it in `0x08dd3004`. Read from the driver code in the 2026-11-04 documentation round (`docs/subsystems/audio.md`) and checked against the disc: the computed table positions land exactly on the bank-offset table `0x0889cf20` described above (high).

| Offset | Type | Meaning |
| --- | --- | --- |
| `+0x00` | `char[4]` | `SHDS` |
| `+0x08` | u16 | version, `0x50` on this disc |
| `+0x0c` | u16 | music banks / music ids (48): ids below this are BGM, one cue per bank |
| `+0x0e` | u16 | ids beyond the banks (30,731) |
| `+0x10` | u16 | other banks (680) |
| `+0x34` | `u32[ids]` | attribute word per global sound id; ids = `+0x0c + +0x10 + +0x0e` = 31,459 |
| then | 16-byte records `[banks]` | bank records (banks = `+0x0c + +0x10` = 728); `+0x08` is the bank size `audio_load_bank` reads (the "size-like value" above) |
| then | `u32[banks]` | bank offsets in `psp_snddat.bin` (= `0x0889cf20`) |
| then | `u16[banks]` | first global id of each bank (= `0x0889da80`) |

Attribute word (one per global sound id):

| Bits | Meaning |
| --- | --- |
| byte 0 bits 0–3 | sound type: 0 SAS note sequence, 1 sound script (frame-timed event list), 2–3 one-shot PS-ADPCM on sceSas, 4 and 5 ATRAC streams (4 vs 5 = ATRAC3plus vs ATRAC3, hypothesis, medium-high) |
| byte 0 bit 5 (`0x20`) | voice category |
| byte 0 bit 6 (`0x40`) | two ADPCM layers |
| byte 0 bit 7 (`0x80`) | may not steal other sounds' SAS voices |
| byte 1 | priority (a new sound cannot evict a playing one with a higher value) |
| byte 2 | maximum simultaneous instances |
| byte 3 | `0x01` no 3D positioning, `0x02` no distance volume, `0x04` no 3D pan, `0x08` Doppler pitch, `0x10` ignore mix presets and pause groups, `0x20` no reverb send, `0x80` decoded but not mixed (streams) |

Runtime semantics the port must reproduce (driver code, medium-high unless stated; details in `audio.md`):

- **Cue `+0x10` is a random-variation count.** A sound effect or voice whose cue has `+0x10 = k > 0` plays cue `N + r`, `r` random in `0..k-1`, never repeating the previous pick for the same (owner, id) pair (32-entry history `0x08dd3010`); a non-zero `+0x11` replaces the random pick by a counter cycling through `+0x11` values. About 4,670 cues on the disc have `+0x10` in 2–6. `audio_play_se_unlimited` bypasses it.
- Cue `+0x02`: BGM ducking level while the sound plays (`((15 − v) × 0x1112) >> 4` / 0x1000, smallest wins, 150 ms fades); `+0x03`: retrigger lock in mixer grains × 6; `+0x04`: volume/stop group (selectors `0xfffffe00 | group`); `+0x05`: mix-preset row; `+0x18`: duration in ms; `+0x1c`: minimum audible level for culling positional sounds; `+0x1d`: exclusive group.
- Envelope `+0x04`/`+0x06` are ADSR1/ADSR2 for `sceSasSetSimpleADSR` and `+0x08` bit 0 the loop flag of `sceSasSetVoice` (confirms the hypotheses above); the sample's `u16 pitch` is the sceSas pitch at the root note.
- **Every RIFF wave loops forever when it has a `smpl` chunk**: `audio_start_atrac_voice` calls `sceAtracSetLoopNum(id, -1)`, so the 11 effect waves with loops loop too; a stop switches to `sceAtracSetLoopNum(id, 0)` and lets the stream play out.
- Output: 44,100 Hz stereo s16 in grains of 256 frames; the driver's tick is one grain (`ms × 10 / 58`).

## Open questions

- ~~Cue flags `0x02`, `0x04`, `0x10`, `0x11`, envelope byte `0x08`~~: answered statically 2026-11-04 ("`SHDS` sound header" above); envelope bytes `0x09`–`0x0B` beyond the reverb send `+0x09` and a PPSSPP confirmation of the variation pick remain.
- ~~The play call and bank loading~~: answered 2026-11-04: `audio_start_sound` (`0x0886b37c`) and its wrappers take the global id; `audio_load_bank` reads a whole bank (size from the `SHDS` bank record) at its offset plus the stream base `0x08dd3114` (`audio.md`).
- How the duel chooses among the three banks of a voice set, and which voice ids the duel uses for the 52-cue generic-student sets.
- Banks 709–711: partly answered 2026-11-04: 709 is loaded by the title, 710/711 by the free roam (with 712, 713, 715–717, 727); the duel loads 719 plus music bank 8 or 9. Which characters' lines they hold is still open.
- ~~Whether the game loops the 11 effect waves with a `smpl` chunk~~: answered 2026-11-04: yes, every RIFF wave is registered with `sceAtracSetLoopNum(-1)` (medium-high, static).
