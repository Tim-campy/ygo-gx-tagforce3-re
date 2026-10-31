# PSMF movies (`movie/*.pmf`)

73 files, 243.1 MiB, 16.9 minutes in total. Every one is a Sony PSMF container with H.264 video and ATRAC3plus audio at 480 x 272. `tools/psmf.py` lists and checks them (`--check` passes on all 73) and converts them with FFmpeg (see "Conversion"). What they show and how the game plays them is in `docs/subsystems/movies.md`.

## Layout

A `.pmf` is a **0x800-byte PSMF header followed by a plain MPEG-2 program stream**. Offsets are big-endian.

| Offset | Size | Meaning | Confidence |
| --- | --- | --- | --- |
| `+0x00` | 4 | Magic `PSMF` | H |
| `+0x04` | 4 | ASCII version: `0015` (71 files) or `0014` (`exodia_finish`, `ouijaboard_final`) | H |
| `+0x08` | u32 | Header size, always `0x800`; the program stream starts there | H |
| `+0x0c` | u32 | Program stream size; `file size = 0x800 + this` holds for all 73 files | H |
| `+0x56` | u32 | First time stamp, 90 kHz ticks (90000 = 1.0 s in the files read) | H |
| `+0x5c` | u32 | Last time stamp; `(last - first) / 90000` is the duration | H |
| `+0x80` | u16 | Stream count: 2 in every file | H |
| `+0x82` | 16 each | Stream entries. Byte 0 is the MPEG stream id (`0xe0` video, `0xbd` private stream 1), byte 1 the private id (0). For the video entry bytes `+0x0c` and `+0x0d` hold width / 16 and height / 16 (30 and 17 = 480 x 272) | H for ids and size, L for the other bytes |

The other header bytes (between `+0x10` and `+0x55`, and the tail of each stream entry) were not decoded; the tool does not need them.

The body is an MPEG-2 program stream: pack headers (`00 00 01 ba`, system clock in the MPEG-2 layout), video PES packets with stream id `0xe0` and audio PES packets with `0xbd`. The last pack clock minus the first one agrees with the header duration to within 3 s in every file, which is one of the checks.

## Streams

| Stream | Content | Basis |
| --- | --- | --- |
| Video `0xe0` | H.264 (AVC), **Main profile**, 480 x 272, 30000/1001 fps | `ffprobe` on `TF3_opening_a.pmf`; NAL types seen in the stream (access unit delimiters, SEI, IDR and non-IDR slices) (H) |
| Video `0xe0`, all 73 | The decoded frame count equals header duration × 29.97 (for example 330 frames in 11.01 s, 2,003 in the 66.83 s opening); no B-frames in `E_typhoon_attack` (`has_b_frames=0`; the others not probed) | `psmf.py --convert-check` (`ffprobe -count_frames` on each converted file) (H) |
| Audio `0xbd` | **ATRAC3plus, stereo, 44,100 Hz, 744-byte frames (2048 samples), 128,166 bit/s**, in MPEG private stream 1, identical in all 73 files; `ffmpeg`'s program-stream demuxer does not list it | Frame headers in every file (`psmf.py --check`); the game decodes it with `sceMpegAtracDecode` (`system_movie_decode_audio`, below) (H for the parameters) |

The program stream also holds a system header (`0xbb`), private stream 2 (`0xbf`) and padding (`0xbe`) packets; the demuxer steps over them by their length. The audio stream entry of the PSMF header ends in `02 02` in all files (hypothesis, low: channel count and a rate code).

### Audio in private stream 1

Each `0xbd` PES packet (header with PTS on the first packet of the track) carries:

| Payload offset | Size | Meaning | Confidence |
| --- | --- | --- | --- |
| `+0` | 1 | Substream id, 0 | H |
| `+1` | 1 | 0 in every packet read; not decoded | L |
| `+2` | u16 BE | Offset, counted from `+4`, of the first ATRAC frame header that starts in this packet (0 in the first packet, `0xf3` in the second packet of `E_typhoon_attack`) | H (checked on every packet of every file) |
| `+4` | … | A slice of the audio elementary stream; frames run across packet boundaries | H |

The elementary stream is a sequence of `8-byte header + frame`: header `0f d0`, the big-endian codec word (`0x285c`: bits 0–9 = 744 / 8 − 1, bits 10–12 = 2 channels, bits 13–15 = rate index 1, 44,100 Hz; the same word as in the `.at3` `fmt ` chunk, see `sound.md`), then 4 zero bytes. Removing the headers gives the raw frames of an ATRAC3plus `.at3` with block align 744.

**Timing.** The first audio PTS is 85,069 and the first video PTS 90,000 in all 73 files: the audio starts 4,931 ticks (54.8 ms) earlier, which at 44,100 Hz is **2,416 samples = one 2048-sample frame + the 368-sample decoder delay** of ATRAC3plus (the delay is established on the sound banks, `sound.md`). So dropping the first 2,416 decoded samples aligns the audio with the first video frame (M: consistent arithmetic, not checked against the PSP decoder output in PPSSPP).

## Conversion (install time, FFmpeg)

The port does not ship the movies; it converts them from the user's own disc. `tools/psmf.py` specifies and tests that step (FFmpeg 7.1.1 checked):

```
python3 -I tools/psmf.py <USRDIR>/movie --check                       # layout + audio demux
python3 -I tools/psmf.py <USRDIR>/movie --convert -o <scratch>/movie [--format mp4|mkv|wav]
python3 -I tools/psmf.py <USRDIR>/movie --convert-check               # convert to a temp file, decode back, delete
```

1. Demux private stream 1 in Python (`demux_audio`), strip the 4-byte payload headers and the 8-byte frame headers, and wrap the frames in a RIFF `.at3` (`audio_convert.atrac3plus_riff`, the same 52-byte `fmt ` layout as the disc's own waves).
2. `ffmpeg -f wav -i pipe:0 -f s16le pipe:1` decodes it to PCM; drop the lead (video PTS − audio PTS, 2,416 samples).
3. `ffmpeg -fflags +genpts -f mpeg -i <file>.pmf -f s16le -ar 44100 -ac 2 -i pipe:0 -map 0:v:0 -map 1:a:0 -c:v copy …`: FFmpeg's `mpeg` demuxer reads the H.264 stream directly (the 0x800-byte header is skipped by its probe), and the video is **copied unchanged**. Audio: AAC 160 kbit/s in `.mp4` (`+faststart`), FLAC in `.mkv`; `--format wav` writes only the PCM audio.

`--convert-check` result on the reference disc:

```
ok: 73 movies converted and decoded, 16.9 min of video; largest audio/video length difference 0.083 s, largest video/header difference 0.000 s
```

The video length of every converted file equals the header duration; the audio is at most 83 ms longer (the padding of the last ATRAC frame plus AAC framing). The output is game content: it stays outside the repository. Re-encoding to the 3DS playback format (resolution 400 × 240 or 400 × 225, a codec the 3DS can decode) is a port-side step from these files and is not specified here.

Bitrate of the opening: 18,049,024 bytes in 66.8 s, about 2.17 Mbit/s for video and audio together.

## Inventory

| Group | Files | Total size | Duration each | Played from |
| --- | --- | --- | --- | --- |
| Opening `TF3_opening_a` | 1 | 17.2 MiB | 66.8 s | `rel_title` |
| Staff roll `TF3_staffroll_a`, `TF3_staffroll2_a` | 2 | 53.5 MiB | 104.9 s | `rel_story` |
| Monster summon cut-ins `<name>_summon` | 34 | 88.8 MiB | 4.5 - 20.0 s | `rel_duel_draw` |
| Monster attack cut-ins `<name>_attack` | 34 | 76.7 MiB | 4.7 - 16.1 s | `rel_duel_draw` |
| `exodia_finish`, `ouijaboard_final` (version `0014`) | 2 | 6.8 MiB | 19.0 s, 15.3 s | `rel_duel_draw` (win scenes) |

Evidence for the "played from" column: each module contains the path as a string (`movie/TF3_opening_a.pmf` in `rel_title`, the two `_a` staff roll paths in `rel_story`, 75 `movie/<name>.pmf` paths in `rel_duel_draw`: the 70 cut-in and win-scene files plus 5 names with no file). `rel_gallery` holds all 73 file names without the directory and builds `movie/%s.pmf` (it lists every movie); `rel_movie_viewer` enumerates the `movie/` directory (H for the strings, M for "played from", since the call sites were not traced). Eight names used by the code have no file on this disc and the disc ships the `_a` variants instead; see `docs/subsystems/movies.md`, "Region variants".

## The player in BOOT.BIN

One generic player serves all of them. It is a thin layer over the `sceMpeg` imports (`modules.md`: `system_load_movie_modules`, `0x0882b834`, loads the Sony modules with ids 2-5, among them `mpegbase.prx`). BOOT.BIN contains seven functions that call `sceMpeg*`, all between `0x0882b964` and `0x0882e038`; they are named after the calls each one makes and are not decompiled (M):

| Address | Name | `sceMpeg` calls it makes |
| --- | --- | --- |
| `0x0882b964` | `system_movie_play` (formerly `system_movie_create_player`: it also runs the playback loop and tears the player down) | `sceMpegQueryMemSize`, `Create`, `Init`, `RingbufferQueryMemSize`, `RingbufferConstruct`, `RegistStream`, `MallocAvcEsBuf`, `QueryAtracEsSize`, and the matching destroy calls |
| `0x0882c294` | `system_movie_flush_video` | `sceMpegAvcDecodeFlush`, `sceMpegRingbufferAvailableSize` |
| `0x0882c4d0` | `system_movie_query_stream` | `sceMpegQueryStreamOffset`, `sceMpegQueryStreamSize` |
| `0x0882d554` | `system_movie_decode_audio` | `sceMpegGetAtracAu`, `sceMpegAtracDecode` |
| `0x0882d614` | `system_movie_decode_video` | `sceMpegGetAvcAu`, `sceMpegAvcDecode` |
| `0x0882d6fc` | `system_movie_stop_video` | `sceMpegAvcDecodeStop` |
| `0x0882e038` | `system_movie_feed_ringbuffer` | `sceMpegRingbufferAvailableSize`, `sceMpegRingbufferPut` |

## Open questions

- The header bytes between `+0x10` and `+0x55` and the tails of the stream entries (frame rate, ATRAC3plus parameters) are not decoded; only the fields above are used.
- Whether the audio track is the full soundtrack for the movie or only the voice and effects (the bitrate is answered: 744-byte frames, 128,166 bit/s).
- Whether the PSP player really drops 2,416 samples (one frame + decoder delay) before the first video frame; check the A/V offset in PPSSPP.
- The call sites of the player (who opens each file, whether a button press can skip it) are not traced.
