#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/psmf.py on hand-built headers (no game data). Run with: python3 -I tools/tests/test_psmf.py"""

import contextlib
import importlib.util
import io
import struct
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_psmf", Path(__file__).resolve().parents[1] / "psmf.py")
psmf = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(psmf)


def pack(scr):
    """An MPEG-2 program stream pack header (14 bytes) carrying the given 90 kHz clock."""
    v = ((1 << 46) | (((scr >> 30) & 7) << 43) | (1 << 42) | (((scr >> 15) & 0x7FFF) << 27) | (1 << 26)
         | ((scr & 0x7FFF) << 11) | (1 << 10) | 1)
    return b"\x00\x00\x01\xba" + v.to_bytes(6, "big") + b"\x00\x4e\x7b\xf8"


def pes(sid, payload, pts=None):
    """A PES packet with an optional PTS (MPEG-2 PES header)."""
    if pts is None:
        header = b"\x81\x00\x00"
    else:
        header = b"\x81\x80\x05" + bytes([0x21 | ((pts >> 29) & 0x0E), (pts >> 22) & 0xFF, ((pts >> 14) & 0xFE) | 1,
                                          (pts >> 7) & 0xFF, ((pts << 1) & 0xFE) | 1])
    return b"\x00\x00\x01" + bytes([sid]) + struct.pack(">H", len(header) + len(payload)) + header + payload


AUDIO_PARAMS = 0x2801  # 44.1 kHz, 2 channels, 16-byte frames


def audio_frame(n):
    return b"\x0f\xd0" + struct.pack(">H", AUDIO_PARAMS) + bytes(4) + bytes([n]) * 16


def audio_packets(pts=85069, frames=3):
    """Private stream 1 packets: a frame split across two packets, as on the disc."""
    stream = b"".join(audio_frame(i + 1) for i in range(frames))
    split = 30
    second_offset = (-split) % 24  # first frame header after the split
    return (pes(0xBD, b"\x00\x00" + struct.pack(">H", 0) + stream[:split], pts)
            + pes(0xBD, b"\x00\x00" + struct.pack(">H", second_offset) + stream[split:]))


def movie(seconds=10, first=90000, streams=((0xE0, 480, 272), (0xBD, 0, 0)), version=b"0015", count=None,
          audio=None):
    last = first + seconds * 90000
    audio = audio_packets() if audio is None else audio
    body = (pack(3000) + pes(0xE0, bytes(40), first) + audio + pes(0xBE, bytes(8))
            + pack(3000 + seconds * 90000) + pes(0xE0, bytes(10)) + b"\x00\x00\x01\xb9")
    header = bytearray(0x800)
    header[0:4] = b"PSMF"
    header[4:8] = version
    struct.pack_into(">II", header, 8, 0x800, len(body))
    struct.pack_into(">I", header, 0x56, first)
    struct.pack_into(">I", header, 0x5C, last)
    struct.pack_into(">H", header, 0x80, len(streams) if count is None else count)
    for i, (sid, w, h) in enumerate(streams):
        entry = 0x82 + 16 * i
        header[entry] = sid
        header[entry + 12], header[entry + 13] = w // 16, h // 16
    return bytes(header) + body


class PsmfTest(unittest.TestCase):
    def test_parse(self):
        info = psmf.parse(movie(seconds=67))
        self.assertEqual((info["version"], info["header_size"]), ("0015", 0x800))
        self.assertAlmostEqual(info["duration"], 67.0)
        self.assertAlmostEqual(info["clock_span"], 67.0)
        self.assertEqual([s["id"] for s in info["streams"]], [0xE0, 0xBD])
        self.assertEqual((info["streams"][0]["width"], info["streams"][0]["height"]), (480, 272))

    def test_pack_clock(self):
        for scr in (0, 3000, 30147, 6087050, (1 << 33) - 1):
            self.assertEqual(psmf.pack_scr(pack(scr), 0), scr)

    def test_good_movie_has_no_problems(self):
        data = movie()
        self.assertEqual(psmf.problems("m.pmf", data, psmf.parse(data)), [])

    def test_problems_are_reported(self):
        cases = {
            "unknown version": movie(version=b"0099"),
            "expected e0 + bd": movie(streams=((0xE0, 480, 272),)),
            "expected 480x272": movie(streams=((0xE0, 320, 240), (0xBD, 0, 0))),
            "not after the first": movie(seconds=0),
            "pack clock spans": movie(seconds=10)[:0x56] + struct.pack(">I", 90000) + movie(seconds=10)[0x5A:0x5C]
            + struct.pack(">I", 90000 + 30 * 90000) + movie(seconds=10)[0x60:],
            "file size": movie() + b"\x00",
        }
        for expected, data in cases.items():
            found = psmf.problems("m.pmf", data, psmf.parse(data))
            self.assertTrue(any(expected in p for p in found), (expected, found))

    def test_pes_pts(self):
        for pts in (0, 85069, 90000, (1 << 33) - 1):
            self.assertEqual(psmf.pes_pts(pes(0xE0, b"", pts), 0), pts)
        self.assertIsNone(psmf.pes_pts(pes(0xE0, b""), 0))

    def test_demux_audio(self):
        audio = psmf.demux_audio(movie())
        self.assertEqual(audio["problems"], [])
        self.assertEqual((audio["frame_bytes"], audio["channels"], audio["rate"]), (16, 2, 44100))
        self.assertEqual(audio["frames"], bytes([1]) * 16 + bytes([2]) * 16 + bytes([3]) * 16)
        self.assertEqual((audio["first_pts"], audio["video_pts"]), (85069, 90000))
        self.assertEqual(psmf.lead_samples(audio), 2416)
        riff = psmf.audio_riff(audio)
        info = psmf.audio_convert.atrac_info(riff)
        self.assertEqual((info["codec"], info["channels"], info["frames"], info["block_align"]), ("ATRAC3plus", 2, 3, 16))
        self.assertEqual(info["samples"], 3 * 2048 - 368)

    def test_demux_reports_broken_audio(self):
        bad = bytearray(audio_packets())
        bad[bad.index(b"\x0f\xd0", 40) + 3] ^= 0xFF  # damage the parameter word of the second frame
        audio = psmf.demux_audio(movie(audio=bytes(bad)))
        self.assertTrue(any("audio frame 1" in p for p in audio["problems"]), audio["problems"])
        found, _ = psmf.audio_problems("m.pmf", movie(audio=b""), psmf.parse(movie(audio=b"")))
        self.assertTrue(any("does not start" in p for p in found), found)

    def test_rejects_other_files(self):
        with self.assertRaises(psmf.PsmfError):
            psmf.parse(b"RIFF" + bytes(0x200))

    def test_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.pmf").write_bytes(movie(seconds=5))
            (Path(tmp) / "b.pmf").write_bytes(movie(seconds=7))
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(psmf.main([tmp, "--check"]), 0)
            self.assertIn("ok: 2 movies", out.getvalue())
            (Path(tmp) / "c.pmf").write_bytes(movie(streams=((0xE0, 480, 272),)))
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(psmf.main([tmp, "--check"]), 1)
            self.assertIn("c.pmf", out.getvalue())
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                psmf.main([str(Path(tmp) / "a.pmf")])
            self.assertIn("480x272", out.getvalue())


if __name__ == "__main__":
    unittest.main()
