# PSMF movies (`movie/*.pmf`)

73 files, 243.1 MiB, 16.9 minutes in total. Every one is a Sony PSMF container with H.264 video and ATRAC3plus audio at 480 x 272. `tools/psmf.py` lists and checks them (`--check` passes on all 73). What they show and how the game plays them is in `docs/subsystems/movies.md`.

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
| Audio `0xbd` | **ATRAC3plus** in MPEG private stream 1; `ffmpeg`'s program-stream demuxer does not list it | The game decodes it with `sceMpegAtracDecode` (`system_movie_decode_audio`, below) (M) |

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
| `0x0882b964` | `system_movie_create_player` | `sceMpegQueryMemSize`, `Create`, `Init`, `RingbufferQueryMemSize`, `RingbufferConstruct`, `RegistStream`, `MallocAvcEsBuf`, `QueryAtracEsSize`, and the matching destroy calls |
| `0x0882c294` | `system_movie_flush_video` | `sceMpegAvcDecodeFlush`, `sceMpegRingbufferAvailableSize` |
| `0x0882c4d0` | `system_movie_query_stream` | `sceMpegQueryStreamOffset`, `sceMpegQueryStreamSize` |
| `0x0882d554` | `system_movie_decode_audio` | `sceMpegGetAtracAu`, `sceMpegAtracDecode` |
| `0x0882d614` | `system_movie_decode_video` | `sceMpegGetAvcAu`, `sceMpegAvcDecode` |
| `0x0882d6fc` | `system_movie_stop_video` | `sceMpegAvcDecodeStop` |
| `0x0882e038` | `system_movie_feed_ringbuffer` | `sceMpegRingbufferAvailableSize`, `sceMpegRingbufferPut` |

## Open questions

- The header bytes between `+0x10` and `+0x55` and the tails of the stream entries (frame rate, ATRAC3plus parameters) are not decoded; only the fields above are used.
- Whether the audio track is the full soundtrack for the movie or only the voice and effects, and its exact ATRAC3plus bitrate.
- The call sites of the player (who opens each file, whether a button press can skip it) are not traced.
