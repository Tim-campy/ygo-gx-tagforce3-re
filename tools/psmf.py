#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""List and check the PSMF movies of the disc (USRDIR/movie/*.pmf). See docs/formats/psmf-movies.md.

  psmf.py <USRDIR>/movie             one line per movie: size, version, duration, resolution, streams
  psmf.py <USRDIR>/movie --check     structural checks over every movie (exit 1 on a problem)
  psmf.py <file.pmf> [--check]       the same for a single file

A PSMF file is a 0x800-byte Sony header followed by a plain MPEG-2 program stream (AVC video, stream id
0xe0, and ATRAC3plus audio in private stream 1, id 0xbd). The tool only reads headers and pack clocks; it
never decodes or copies the video. Listings are knowledge about the files, not content.
"""

import argparse
import struct
import sys
from pathlib import Path

CLOCK = 90000  # PSMF and MPEG-PS time stamps tick at 90 kHz
PACK_START = b"\x00\x00\x01\xba"
VERSIONS = {"0012", "0013", "0014", "0015"}
VIDEO_ID, AUDIO_ID = 0xE0, 0xBD
STREAM_TABLE = 0x82  # 16-byte entries after the u16 stream count at 0x80


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


def movies(path):
    path = Path(path)
    return sorted(path.glob("*.pmf")) if path.is_dir() else [path]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", type=Path, help="USRDIR/movie directory or one .pmf file")
    parser.add_argument("--check", action="store_true", help="exit 1 when a movie breaks the documented layout")
    args = parser.parse_args(argv)

    files = movies(args.path)
    found, total, seconds = [], 0, 0.0
    for file in files:
        data = file.read_bytes()
        try:
            info = parse(data)
        except PsmfError as error:
            found.append(f"{file.name}: {error}")
            continue
        found += problems(file.name, data, info)
        total += len(data)
        seconds += max(info["duration"], 0)
        video = next((s for s in info["streams"] if s["id"] == VIDEO_ID), {})
        if not args.check:
            ids = ",".join(f"{s['id']:02x}" for s in info["streams"])
            print(f"{file.name:28} {len(data):>10} bytes  v{info['version']}  {info['duration']:6.1f} s  "
                  f"{video.get('width', '?')}x{video.get('height', '?')}  streams {ids}")
    if args.check:
        print("\n".join(found) if found else
              f"ok: {len(files)} movies, {total / 1048576:.1f} MiB, {seconds / 60:.1f} min in total")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
