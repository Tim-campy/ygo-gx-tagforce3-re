#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""List, check and convert the PSMF movies of the disc (USRDIR/movie/*.pmf). See docs/formats/psmf-movies.md.

  psmf.py <USRDIR>/movie             one line per movie: size, version, duration, resolution, streams
  psmf.py <USRDIR>/movie --check     structural checks over every movie, audio demux included (exit 1 on a problem)
  psmf.py <file.pmf> [--check]       the same for a single file
  psmf.py <USRDIR>/movie --convert -o DIR [--format mp4|mkv|wav]
                                     install-time conversion with ffmpeg (H.264 copied; audio to AAC, FLAC or WAV)
  psmf.py <USRDIR>/movie --convert-check
                                     convert every movie to a temporary file, decode it back, report durations

A PSMF file is a 0x800-byte Sony header followed by a plain MPEG-2 program stream (AVC video, stream id
0xe0, and ATRAC3plus audio in private stream 1, id 0xbd). FFmpeg's program-stream demuxer reads the video
but not the audio, so the tool demuxes private stream 1 itself, wraps the ATRAC3plus frames in a RIFF .at3
(tools/audio_convert.py) and lets ffmpeg decode and mux. Listings are knowledge about the files, not
content; converted movies are game content and stay outside the repository.
"""

import argparse
import importlib.util
import struct
import subprocess
import sys
import tempfile
from pathlib import Path


def _load(name):
    spec = importlib.util.spec_from_file_location(f"re_{name}", Path(__file__).resolve().parent / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audio_convert = _load("audio_convert")

CLOCK = 90000  # PSMF and MPEG-PS time stamps tick at 90 kHz
PACK_START = b"\x00\x00\x01\xba"
VERSIONS = {"0012", "0013", "0014", "0015"}
VIDEO_ID, AUDIO_ID = 0xE0, 0xBD
STREAM_TABLE = 0x82  # 16-byte entries after the u16 stream count at 0x80
ATRAC_SYNC = b"\x0f\xd0"  # each ATRAC3plus frame in private stream 1 carries an 8-byte header 0f d0 <params> 0*4
ATRAC_FRAME_HEADER = 8
PRIVATE_HEADER = 4  # private stream 1 payload: u8 substream id (0), u8, u16 BE offset of the first frame header


class PsmfError(ValueError):
    pass


def pack_scr(data, pos):
    """System clock reference of the MPEG-2 pack header at `pos`, in 90 kHz ticks."""
    v = int.from_bytes(data[pos + 4:pos + 10], "big")
    return (((v >> 43) & 7) << 30) | (((v >> 27) & 0x7FFF) << 15) | ((v >> 11) & 0x7FFF)


def parse(data):
    """Header fields of one PSMF file as a dict; raises PsmfError when the header is not a PSMF."""
    if data[:4] != b"PSMF" or len(data) < 0x100:
        raise PsmfError("not a PSMF file")
    header_size, stream_size = struct.unpack_from(">II", data, 8)
    first_ts, = struct.unpack_from(">I", data, 0x56)
    last_ts, = struct.unpack_from(">I", data, 0x5C)
    count, = struct.unpack_from(">H", data, 0x80)
    streams = []
    for i in range(min(count, 8)):
        entry = data[STREAM_TABLE + 16 * i:STREAM_TABLE + 16 * (i + 1)]
        stream = {"id": entry[0], "private": entry[1]}
        if entry[0] == VIDEO_ID:
            stream["width"], stream["height"] = entry[12] * 16, entry[13] * 16
        streams.append(stream)
    info = {"version": data[4:8].decode("ascii", "replace"), "header_size": header_size,
            "stream_size": stream_size, "first_ts": first_ts, "last_ts": last_ts,
            "duration": (last_ts - first_ts) / CLOCK, "stream_count": count, "streams": streams}
    first = data.find(PACK_START, header_size)
    last = data.rfind(PACK_START)
    info["first_pack"] = first
    if first == header_size and last > first:
        info["clock_span"] = (pack_scr(data, last) - pack_scr(data, first)) / CLOCK
    else:
        info["clock_span"] = None
    return info


# ---------------------------------------------------------------------- program stream demux

def pes_pts(data, pos):
    """PTS of the PES packet at `pos` in 90 kHz ticks, or None when the packet carries none."""
    if not data[pos + 7] & 0x80:
        return None
    b = data[pos + 9:pos + 14]
    return (((b[0] >> 1) & 7) << 30) | ((((b[1] << 8) | b[2]) >> 1) << 15) | (((b[3] << 8) | b[4]) >> 1)


def packets(data, start=0x800):
    """(stream id, PTS or None, payload) of every video and private-stream-1 PES packet, in file order.
    Pack headers and the end code are skipped; other packets (system header 0xbb, padding 0xbe, private
    stream 2 0xbf) are stepped over by their length."""
    pos = start
    while pos + 4 <= len(data):
        if data[pos:pos + 3] != b"\x00\x00\x01":
            raise PsmfError(f"no start code at {pos:#x}")
        sid = data[pos + 3]
        if sid == 0xBA:
            pos += 14 + (data[pos + 13] & 7)
            continue
        if sid == 0xB9:
            pos += 4
            continue
        length, = struct.unpack_from(">H", data, pos + 4)
        end = pos + 6 + length
        if sid in (VIDEO_ID, AUDIO_ID):
            yield sid, pes_pts(data, pos), data[pos + 9 + data[pos + 8]:end]
        pos = end


def demux_audio(data, start=0x800):
    """The ATRAC3plus track of private stream 1.

    Returns a dict: `frames` (the frames without their 8-byte headers, ready for a RIFF .at3), `frame_bytes`,
    `channels`, `rate`, `params` (codec word), `first_pts` (first audio PTS), `video_pts` (first video PTS)
    and `problems` (list of strings).
    """
    stream, found = bytearray(), []
    first_pts = video_pts = None
    for sid, pts, payload in packets(data, start):
        if sid == VIDEO_ID:
            if video_pts is None and pts is not None:
                video_pts = pts
            continue
        if len(payload) < PRIVATE_HEADER or payload[0] != 0:
            found.append(f"private stream 1 packet with substream {payload[:1].hex()} skipped")
            continue
        if first_pts is None and pts is not None:
            first_pts = pts
        offset, = struct.unpack_from(">H", payload, 2)
        body = payload[PRIVATE_HEADER:]
        # The offset is relative to the bytes after the 4-byte private header, in the reassembled stream
        # the frame header sits there only when a frame starts in this packet.
        if offset + 2 <= len(body) and body[offset:offset + 2] != ATRAC_SYNC and len(found) < 5:
            found.append(f"frame header not at the offset given by the packet ({offset:#x})")
        stream += body
    if stream[:2] != ATRAC_SYNC:
        raise PsmfError("audio stream does not start with an ATRAC3plus frame header")
    params, = struct.unpack_from(">H", stream, 2)
    frame_bytes, channels, rate = audio_convert.parse_atrac3plus_params(params)
    step = ATRAC_FRAME_HEADER + frame_bytes
    frames = bytearray()
    for pos in range(0, len(stream) - step + 1, step):
        if stream[pos:pos + 4] != stream[:4]:
            found.append(f"audio frame {pos // step} has header {stream[pos:pos + 4].hex()}")
            break
        frames += stream[pos + ATRAC_FRAME_HEADER:pos + step]
    if len(stream) % step:
        found.append(f"{len(stream) % step} trailing audio bytes after the last whole frame")
    return {"frames": bytes(frames), "frame_bytes": frame_bytes, "channels": channels, "rate": rate,
            "params": params, "first_pts": first_pts, "video_pts": video_pts, "problems": found}


def audio_riff(audio):
    """RIFF .at3 file of a demuxed track (fact: every decoded sample after the decoder delay, offset 0)."""
    count = len(audio["frames"]) // audio["frame_bytes"] * 2048
    return audio_convert.atrac3plus_riff(audio["frames"], audio["frame_bytes"], audio["channels"], audio["rate"],
                                         sample_count=count - audio_convert.DECODER_DELAY["ATRAC3plus"])


def lead_samples(audio):
    """Decoded audio samples before the first video frame: (video PTS - audio PTS) at the audio rate.
    2416 (one 2048-sample frame + the 368-sample decoder delay) in all 73 movies of the disc."""
    if audio["first_pts"] is None or audio["video_pts"] is None:
        return 0
    return round((audio["video_pts"] - audio["first_pts"]) * audio["rate"] / CLOCK)


# ---------------------------------------------------------------------- conversion (ffmpeg)

def convert(path, target, ffmpeg, data=None):
    """Convert one movie. The H.264 stream is copied unchanged; the demuxed ATRAC3plus track is decoded by
    ffmpeg, its lead trimmed so that it starts with the first video frame, then encoded according to the
    target suffix (.mp4: AAC, .mkv: FLAC) or written alone as 16-bit PCM (.wav).
    Returns (audio samples written, lead samples dropped)."""
    data = data if data is not None else Path(path).read_bytes()
    audio = demux_audio(data)
    pcm = audio_convert.ffmpeg_decode(ffmpeg, audio_riff(audio))
    lead = max(lead_samples(audio), 0)
    frame = 2 * audio["channels"]
    pcm = pcm[lead * frame:]
    if target.suffix == ".wav":
        target.write_bytes(audio_convert.pcm_wav(pcm, audio["channels"], audio["rate"]))
        return len(pcm) // frame, lead
    codec = {".mp4": ["-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart"],
             ".mkv": ["-c:a", "flac"]}[target.suffix]
    result = subprocess.run([ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error", "-y",
                             "-fflags", "+genpts", "-f", "mpeg", "-i", str(path),
                             "-f", "s16le", "-ar", str(audio["rate"]), "-ac", str(audio["channels"]), "-i", "pipe:0",
                             "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", *codec, str(target)],
                            input=pcm, capture_output=True)
    if result.returncode:
        raise audio_convert.FfmpegError(result.stderr.decode("utf-8", "replace").strip()[-300:])
    return len(pcm) // frame, lead


def probe(ffmpeg, target):
    """{codec type: (seconds, frames)} of a converted file, counted by decoding it completely (ffprobe)."""
    ffprobe = Path(ffmpeg).with_name("ffprobe" + Path(ffmpeg).suffix)
    result = subprocess.run([str(ffprobe), "-v", "error", "-count_frames", "-show_entries",
                             "stream=codec_type,duration,nb_read_frames", "-of", "compact=p=0:nk=1", str(target)],
                            capture_output=True, text=True)
    if result.returncode:
        raise audio_convert.FfmpegError(result.stderr.strip()[-300:] or "ffprobe failed")
    streams = {}
    for line in result.stdout.split():
        kind, duration, frames = line.split("|")
        streams[kind] = (float(duration), int(frames))
    return streams


# ---------------------------------------------------------------------- checks

def problems(name, data, info):
    """Structural problems of one movie (empty list when it matches docs/formats/psmf-movies.md)."""
    out = []
    if info["version"] not in VERSIONS:
        out.append(f"{name}: unknown version {info['version']}")
    if info["header_size"] != 0x800:
        out.append(f"{name}: header size {info['header_size']:#x}, expected 0x800")
    if len(data) != info["header_size"] + info["stream_size"]:
        out.append(f"{name}: file size {len(data)} != header {info['header_size']:#x} + stream {info['stream_size']:#x}")
    if info["first_pack"] != info["header_size"]:
        out.append(f"{name}: the program stream does not start right after the header")
    if info["duration"] <= 0:
        out.append(f"{name}: last time stamp not after the first")
    ids = [s["id"] for s in info["streams"]]
    if info["stream_count"] != 2 or ids != [VIDEO_ID, AUDIO_ID]:
        out.append(f"{name}: streams {[hex(i) for i in ids]} (count {info['stream_count']}), expected e0 + bd")
    else:
        video = info["streams"][0]
        if (video["width"], video["height"]) != (480, 272):
            out.append(f"{name}: video {video['width']}x{video['height']}, expected 480x272")
    span = info["clock_span"]
    if span is None:
        out.append(f"{name}: no pack clock found")
    elif abs(span - info["duration"]) > 3.0:
        out.append(f"{name}: pack clock spans {span:.1f} s but the header says {info['duration']:.1f} s")
    return out


def audio_problems(name, data, info):
    """Problems of the private-stream-1 audio demux (run only on structurally sound movies)."""
    try:
        audio = demux_audio(data, info["header_size"])
    except (PsmfError, ValueError, struct.error) as error:
        return [f"{name}: audio: {error}"], None
    out = [f"{name}: audio: {p}" for p in audio["problems"]]
    if not audio["frames"]:
        out.append(f"{name}: audio: no ATRAC3plus frames")
    return out, audio


def movies(path):
    path = Path(path)
    return sorted(path.glob("*.pmf")) if path.is_dir() else [path]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", type=Path, help="USRDIR/movie directory or one .pmf file")
    parser.add_argument("--check", action="store_true", help="exit 1 when a movie breaks the documented layout")
    parser.add_argument("--convert", action="store_true", help="convert the movies with ffmpeg into -o DIR")
    parser.add_argument("--convert-check", action="store_true",
                        help="convert every movie to a temporary file and decode it back (nothing kept)")
    parser.add_argument("-o", "--output", type=Path, help="output directory for --convert (outside the repository)")
    parser.add_argument("--format", choices=("mp4", "mkv", "wav"), default="mp4")
    parser.add_argument("--ffmpeg", help="path of the ffmpeg executable (default: from PATH)")
    args = parser.parse_args(argv)
    if args.convert or args.convert_check:
        return convert_main(args)

    files = movies(args.path)
    found, total, seconds = [], 0, 0.0
    codecs = set()
    for file in files:
        data = file.read_bytes()
        try:
            info = parse(data)
        except PsmfError as error:
            found.append(f"{file.name}: {error}")
            continue
        structural = problems(file.name, data, info)
        found += structural
        audio = None
        if args.check and not structural:
            extra, audio = audio_problems(file.name, data, info)
            found += extra
            if audio:
                codecs.add((audio["frame_bytes"], audio["channels"], audio["rate"], lead_samples(audio)))
        total += len(data)
        seconds += max(info["duration"], 0)
        video = next((s for s in info["streams"] if s["id"] == VIDEO_ID), {})
        if not args.check:
            ids = ",".join(f"{s['id']:02x}" for s in info["streams"])
            print(f"{file.name:28} {len(data):>10} bytes  v{info['version']}  {info['duration']:6.1f} s  "
                  f"{video.get('width', '?')}x{video.get('height', '?')}  streams {ids}")
    if args.check:
        audio_line = "; ".join(f"ATRAC3plus {b}-byte frames, {c} ch, {r} Hz, lead {lead} samples"
                               for b, c, r, lead in sorted(codecs))
        print("\n".join(found) if found else
              f"ok: {len(files)} movies, {total / 1048576:.1f} MiB, {seconds / 60:.1f} min in total; audio: {audio_line}")
    return 1 if found else 0


def convert_main(args):
    try:
        ffmpeg = audio_convert.find_ffmpeg(args.ffmpeg)
    except audio_convert.FfmpegError as error:
        print(error)
        return 2
    if args.convert and args.output is None:
        print("--convert needs -o DIR")
        return 2
    files = movies(args.path)
    found, worst_av, worst_header, total_video = [], 0.0, 0.0, 0.0
    with tempfile.TemporaryDirectory() as scratch:
        directory = Path(scratch) if args.convert_check else args.output
        directory.mkdir(parents=True, exist_ok=True)
        suffix = "." + (args.format if args.convert else "mp4")
        for file in files:
            target = directory / (file.stem + suffix)
            try:
                data = file.read_bytes()
                info = parse(data)
                written, lead = convert(file, target, ffmpeg, data)
                if args.convert and not args.convert_check:
                    print(f"wrote {target} ({target.stat().st_size} bytes, audio {written} samples, lead {lead})")
                    continue
                streams = probe(ffmpeg, target)
                (video_s, video_frames), (audio_s, _) = streams["video"], streams["audio"]
                av = abs(video_s - audio_s)
                worst_av, total_video = max(worst_av, av), total_video + video_s
                worst_header = max(worst_header, abs(video_s - info["duration"]))
                if av > 0.5:
                    found.append(f"{file.name}: video {video_s:.2f} s but audio {audio_s:.2f} s")
                print(f"{file.name:28} video {video_s:7.2f} s {video_frames:5d} frames  audio {audio_s:7.2f} s  "
                      f"header {info['duration']:7.2f} s")
            except (PsmfError, audio_convert.FfmpegError, KeyError, ValueError) as error:
                found.append(f"{file.name}: {error}")
            finally:
                if args.convert_check and target.exists():
                    target.unlink()
    if args.convert_check:
        print("\n".join(found) if found else
              f"ok: {len(files)} movies converted and decoded, {total_video / 60:.1f} min of video; "
              f"largest audio/video length difference {worst_av:.3f} s, "
              f"largest video/header difference {worst_header:.3f} s")
    elif found:
        print("\n".join(found))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
