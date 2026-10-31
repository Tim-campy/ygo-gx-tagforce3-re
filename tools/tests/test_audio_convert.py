#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/audio_convert.py on hand-built data (no game data, no ffmpeg needed).
Run with: python3 -I tools/tests/test_audio_convert.py"""

import importlib.util
import json
import struct
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_audio_convert", Path(__file__).resolve().parents[1] / "audio_convert.py")
ac = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ac)
sound = ac.sound


def smpl(start, end):
    return struct.pack("<9I", 0, 0, 22676, 60, 0, 0, 0, 1, 0) + struct.pack("<6I", 0, 0, start, end, 0, 0)


def atrac3_riff(frames, samples, offset, loop=None):
    """An ATRAC3 (tag 0x270) wave laid out like the disc's: 32-byte fmt, fact, optional smpl, data."""
    fmt = struct.pack("<HHIIHHH", 0x0270, 2, 44100, 8269, 192, 0, 14) + bytes.fromhex("0100001000000100010001000000")
    chunks = [(b"fmt ", fmt), (b"fact", struct.pack("<II", samples, offset))]
    if loop:
        chunks.append((b"smpl", smpl(*loop)))
    chunks.append((b"data", bytes(192 * frames)))
    body = b"WAVE" + b"".join(cid + struct.pack("<I", len(c)) + c for cid, c in chunks)
    return b"RIFF" + struct.pack("<I", len(body)) + body


def bank(waves, durations):
    """One SP bank with one RIFF cue per wave."""
    cue_table, count = 0x30, len(waves)
    wave_area = cue_table + 32 * count
    blob, cues, position = b"", b"", 0
    for wave, ms in zip(waves, durations):
        cues += struct.pack("<BBHHHI4xBB6xI4x", 0x7F, 0x40, 0, 0, 0, position, 0, 0, ms)
        blob += struct.pack("<I", len(wave)) + wave
        position += 4 + len(wave)
    head = struct.pack("<2sHIIIIIII16s", b"SP", 0, 0, cue_table, wave_area, wave_area, wave_area, 0, 0, b"t")
    data = head + cues + blob
    size = (len(data) + 4 + 2047) // 2048 * 2048
    data = data.ljust(size - 4, b"\0") + b"EP" + struct.pack("<H", 0)
    return data[:4] + struct.pack("<I", size) + data[8:]


class RiffWrapperTest(unittest.TestCase):
    def test_params_word(self):
        # Values seen on the disc: 0x2417 mono 192 B, 0x282e stereo 376 B, 0x285c stereo 744 B (movies).
        self.assertEqual(ac.atrac3plus_params(192, 1), 0x2417)
        self.assertEqual(ac.atrac3plus_params(376, 2), 0x282E)
        self.assertEqual(ac.atrac3plus_params(744, 2), 0x285C)
        self.assertEqual(ac.parse_atrac3plus_params(0x285C), (744, 2, 44100))
        with self.assertRaises(ValueError):
            ac.atrac3plus_params(100, 2)

    def test_atrac3plus_riff_layout(self):
        riff = ac.atrac3plus_riff(bytes(376 * 4), 376, 2, sample_count=5000, first_sample_offset=2048)
        self.assertEqual(riff[:4] + riff[8:12], b"RIFFWAVE")
        self.assertEqual(struct.unpack_from("<I", riff, 4)[0] + 8, len(riff))
        chunks = sound.riff_chunks(riff)
        self.assertEqual(list(chunks), ["fmt ", "fact", "data"])
        fmt = chunks["fmt "]
        self.assertEqual(len(fmt), 52)
        # Byte for byte the shape of a stereo 376-byte wave on the disc.
        self.assertEqual(fmt.hex(), "feff020044ac0000a01f0000780100002200000803000000"
                                    "bfaa23e958cb7144a119fffa01e4ce620100282e0000000000000000")
        self.assertEqual(chunks["fact"], struct.pack("<II", 5000, 2048))
        info = ac.atrac_info(riff)
        self.assertEqual((info["codec"], info["frames"], info["bitrate"], info["frame_remainder"]),
                         ("ATRAC3plus", 4, 64772, 0))
        with self.assertRaises(ValueError):
            ac.atrac3plus_riff(bytes(377), 376, 2)

    def test_default_sample_count(self):
        info = ac.atrac_info(ac.atrac3plus_riff(bytes(192 * 3), 192, 1))
        self.assertEqual((info["samples"], info["first_offset"]), (3 * 2048 - 368, 0))
        self.assertEqual(ac.skip_samples(info), 368)

    def test_atrac3_info_trim_and_loop(self):
        riff = atrac3_riff(frames=4, samples=2900, offset=1024, loop=(1024 + 100, 1024 + 2899))
        info = ac.atrac_info(riff)
        self.assertEqual((info["codec"], info["channels"], info["frames"], info["bitrate"]), ("ATRAC3", 2, 4, 66150))
        self.assertEqual(ac.skip_samples(info), 1024 + 69)
        self.assertEqual(ac.output_loop(info, info["loops"][0]), {"start": 100, "end": 2899})
        decoded = b"".join(struct.pack("<hh", i, -i) for i in range(4 * 1024))
        out = ac.trim(decoded, info)
        self.assertEqual(len(out), 2900 * 4)
        self.assertEqual(struct.unpack_from("<hh", out, 0), (1093, -1093))

    def test_unsupported_codec(self):
        riff = bytearray(atrac3_riff(1, 100, 1024))
        struct.pack_into("<H", riff, 20, 0x0001)
        with self.assertRaises(ValueError):
            ac.atrac_info(bytes(riff))

    def test_pcm_wav(self):
        wav = ac.pcm_wav(struct.pack("<4h", 1, 2, 3, 4), 2, 22050)
        chunks = sound.riff_chunks(wav)
        self.assertEqual(struct.unpack("<HHIIHH", chunks["fmt "]), (1, 2, 22050, 88200, 4, 16))
        self.assertEqual(len(chunks["data"]), 8)


class AdpcmLoopTest(unittest.TestCase):
    def frame(self, flags):
        return bytes([0x0C, flags]) + bytes(14)

    def test_loop_flags(self):
        blob = self.frame(0) + self.frame(6) + self.frame(2) + self.frame(3)
        self.assertEqual(ac.adpcm_loop(blob), {"start": 28, "end": 4 * 28 - 1})

    def test_one_shot(self):
        self.assertIsNone(ac.adpcm_loop(self.frame(0) + self.frame(1) + self.frame(7)))


class BankConversionTest(unittest.TestCase):
    """process_bank with ffmpeg replaced by a stub that returns the right number of silent samples."""

    def setUp(self):
        self.original = ac.ffmpeg_decode

        def fake_decode(_ffmpeg, riff, input_format="wav"):
            info = ac.atrac_info(riff)
            return bytes(info["frames"] * 1024 * 2 * info["channels"])

        ac.ffmpeg_decode = fake_decode

    def tearDown(self):
        ac.ffmpeg_decode = self.original

    def test_writes_wav_and_json(self):
        waves = [atrac3_riff(4, 2900, 1024, loop=(1124, 3923)), atrac3_riff(2, 900, 1024)]
        banks = sound.parse(bank(waves, [66, 20]))
        with tempfile.TemporaryDirectory() as tmp:
            problems, results = ac.process_bank(banks[0], "ffmpeg", Path(tmp))
            self.assertEqual(problems, [])
            files = sorted(p.name for p in Path(tmp).iterdir())
            self.assertEqual(files, ["snd_000.json", "snd_000_000.wav", "snd_000_001.wav"])
            wav = sound.riff_chunks((Path(tmp) / "snd_000_000.wav").read_bytes())
            self.assertEqual(len(wav["data"]), 2900 * 4)
            meta = json.loads((Path(tmp) / "snd_000.json").read_text())
            self.assertEqual(meta["cues"][0]["streams"][0]["loop"], {"start": 100, "end": 2899})
            self.assertIsNone(meta["cues"][1]["streams"][0]["loop"])

    def test_check_catches_short_decode_and_duration(self):
        banks = sound.parse(bank([atrac3_riff(4, 2900, 1024)], [500]))
        problems, _ = ac.process_bank(banks[0], "ffmpeg")
        self.assertTrue(any("cue says 500 ms" in p for p in problems), problems)
        ac.ffmpeg_decode = lambda *_: bytes(100)
        problems, _ = ac.process_bank(banks[0], "ffmpeg")
        self.assertTrue(any("expected 4096" in p for p in problems), problems)

    def test_survey(self):
        banks = sound.parse(bank([atrac3_riff(4, 2900, 1024, loop=(1124, 3923))], [66]))
        lines = ac.survey(banks)
        self.assertTrue(any(line.startswith("ATRAC3        2  44100    192") for line in lines), lines)
        self.assertIn("ATRAC3: 1", lines[-2])
        self.assertIn("ATRAC3 yes: 1", lines[-1])


if __name__ == "__main__":
    unittest.main()
