#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/sound.py on hand-built banks (no game data). Run with: python3 -I tools/tests/test_sound.py"""

import contextlib
import importlib.util
import io
import struct
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_sound", Path(__file__).resolve().parents[1] / "sound.py")
sound = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sound)


def riff(tag, channels, samples, payload=b"\x11" * 20, rate=44100):
    fmt = struct.pack("<HHIIHH", tag, channels, rate, 0, 192, 0)
    body = (b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"fact" + struct.pack("<II", 8, samples)
            + struct.pack("<I", 0) + b"data" + struct.pack("<I", len(payload)) + payload)
    return b"RIFF" + struct.pack("<I", len(body)) + body


def cue(volume, pan, layers, target, ms, flags=0):
    return struct.pack("<BBHHHI4xBB6xI4x", volume, pan, flags, 0, layers, target, 0, 0, ms)


def pad(blob, serial):
    size = (len(blob) + 4 + 2047) // 2048 * 2048
    blob = blob.ljust(size - 4, b"\0") + b"EP" + struct.pack("<H", serial)
    return blob[:4] + struct.pack("<I", size) + blob[8:]


def header(serial, cue_table, layer, adpcm, wave, envelope, end):
    return struct.pack("<2sHIIIIIII16s", b"SP", serial, 0, cue_table, layer, adpcm, wave, envelope, end,
                       b"test label")


# PS-ADPCM: one silent frame, then one with shift 12 / filter 0 (samples equal the nibbles) and the end flag.
ADPCM = bytes(16) + bytes([0x0C, 0x01, 0x21, 0xF3]) + bytes(12)


def music_bank(serial):
    """Like the 48 music banks: one cue, no layer/ADPCM/envelope tables."""
    wave = riff(0xFFFE, 2, 44100)  # one second
    blob = header(serial, 0x30, 0, 0, 0x50, 0, 0) + cue(0x55, 0x40, 0, 0, 1000)
    return pad(blob + struct.pack("<I", len(wave)) + wave, serial)


def mixed_bank(serial):
    """Two cues sharing one RIFF wave and one cue with a PS-ADPCM layer."""
    cues = 0x30
    layer = cues + 3 * 32
    adpcm = layer + 8
    sample = struct.pack("<IHH", len(ADPCM), 2048, 22050) + ADPCM
    wave_area = adpcm + len(sample)
    wave = riff(0x0270, 1, 4410)  # 100 ms
    envelope = wave_area + 4 + len(wave)
    env = struct.pack("<BB2xI4xI8x", 0x7F, 0x40, 0x1FE0800F, 0x10003C00)
    blob = (header(serial, cues, layer, adpcm, wave_area, envelope, envelope + len(env))
            + cue(0x7F, 0x40, 0, 0, 100) + cue(0x50, 0x40, 0, 0, 100) + cue(0x7F, 0x40, 1, 0, 2)
            + struct.pack("<II", 0, 0) + sample + struct.pack("<I", len(wave)) + wave + env)
    return pad(blob, serial)


class SoundTest(unittest.TestCase):
    def setUp(self):
        self.data = music_bank(0) + mixed_bank(1)
        self.banks = sound.parse(self.data)

    def test_chain_and_cues(self):
        self.assertEqual([b.serial for b in self.banks], [0, 1])
        self.assertEqual([b.size for b in self.banks], [2048, 2048])
        music, mixed = self.banks
        self.assertEqual(len(music.cues), 1)
        self.assertEqual((music.cues[0].volume, music.cues[0].pan, music.cues[0].duration_ms), (0x55, 0x40, 1000))
        self.assertEqual([c.kind for c in mixed.cues], ["riff", "riff", "adpcm"])
        self.assertEqual(len(mixed.wave_spans()), 1)
        self.assertEqual(sound.wave_info(music.wave(music.cues[0])),
                         {"codec": "ATRAC3plus", "channels": 2, "rate": 44100, "samples": 44100})
        self.assertEqual(sound.wave_info(mixed.wave(mixed.cues[1]))["codec"], "ATRAC3")
        self.assertEqual(music.label, "test label")

    def test_layers_and_adpcm(self):
        mixed = self.banks[1]
        (sample_offset, envelope_offset), = mixed.layer_list(mixed.cues[2])
        pitch, rate, blob = mixed.sample(sample_offset)
        self.assertEqual((pitch, rate, blob), (2048, 22050, ADPCM))
        self.assertEqual(mixed.envelope(envelope_offset)[:2], b"\x7f\x40")
        decoded = sound.decode_adpcm(blob)
        self.assertEqual(len(decoded), 56)
        self.assertEqual(decoded[28:32], [1, 2, 3, -1])

    def test_check_passes_and_catches_damage(self):
        self.assertEqual(sound.check(self.banks), [])
        damaged = bytearray(self.data)
        damaged[2048 - 4] = ord("X")  # footer of bank 0
        damaged[2048 + 0x30 + 0x18] = 200 # duration of bank 1 cue 0
        problems = sound.check(sound.parse(bytes(damaged)))
        self.assertTrue(any("footer" in p for p in problems))
        self.assertTrue(any("duration" in p for p in problems))

    def test_bad_chain(self):
        with self.assertRaises(ValueError):
            sound.parse(self.data + b"XX" + bytes(2046))

    def test_cli_check_and_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "snd.bin"
            path.write_bytes(self.data)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(sound.main([str(path), "--check"]), 0)
            self.assertIn("2 banks, 4 cues, 2 distinct RIFF waves, 1 ADPCM cues", out.getvalue())
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(sound.main([str(path), "--export", "1:0", "-o", tmp]), 0)
                self.assertEqual(sound.main([str(path), "--export", "1:2", "-o", tmp]), 0)
                self.assertEqual(sound.main([str(path), "--bank", "1"]), 0)
            self.assertEqual((Path(tmp) / "snd_001_000.at3").read_bytes()[:4], b"RIFF")
            wav = (Path(tmp) / "snd_001_002.wav").read_bytes()
            self.assertEqual(struct.unpack_from("<HHI", wav, 20), (1, 1, 22050))
            self.assertEqual(struct.unpack_from("<I", wav, 40)[0], 56 * 2)


if __name__ == "__main__":
    unittest.main()
