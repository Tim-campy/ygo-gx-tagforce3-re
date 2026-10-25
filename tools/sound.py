#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read the audio bank chain snd/psp_snddat.bin ("SP" banks). See docs/formats/sound.md.

Lists banks and cues, runs structural checks over the whole file (--check) and exports single
sounds: a RIFF wave (ATRAC3 / ATRAC3plus) is written unchanged as .at3; a PS-ADPCM layer is decoded
to a 16-bit PCM .wav. Write exports under extracted/, never into git.
"""

import argparse
import struct
import sys
from pathlib import Path

MAGIC = b"SP"
FOOTER = b"EP"
SECTOR = 2048
HEADER = struct.Struct("<2sHIIIIIII16s")  # magic, serial, size, cue, layer, adpcm, wave, envelope, end, label
CUE = struct.Struct("<BBHHHI4xBB6xI4x")  # volume, pan, flags, unknown_4, layers, target, unknown_10/11, ms
CUE_SIZE = 32
LAYER = struct.Struct("<II")  # sample offset (from the ADPCM area), envelope offset (from the envelope table)
ENVELOPE_SIZE = 0x18
SAMPLE_HEADER = struct.Struct("<IHH")  # data length, sceSas pitch, sample rate
ADPCM_FRAME = 16
SAMPLES_PER_FRAME = 28
WAVE_FORMATS = {0xFFFE: "ATRAC3plus", 0x0270: "ATRAC3"}
# PS-ADPCM prediction filters (numerators over 64), the same as the PlayStation SPU / PSP sceSas.
FILTERS = ((0, 0), (60, 0), (115, -52), (98, -55), (122, -60))
DURATION_TOLERANCE_MS = 2  # cue durations vs. the RIFF 'fact' sample count (all 30,672 RIFF cues agree)


class Cue:
    def __init__(self, bank, index, raw):
        (self.volume, self.pan, self.flags, self.unknown_4, self.layers, self.target,
         self.unknown_10, self.unknown_11, self.duration_ms) = CUE.unpack(raw)
        self.bank, self.index = bank, index

    @property
    def kind(self):
        return "riff" if self.layers == 0 else "adpcm"


class Bank:
    def __init__(self, data, offset):
        (magic, self.serial, self.size, self.cue_table, self.layer_table, self.adpcm_area, self.wave_area,
         self.envelope_table, self.end, label) = HEADER.unpack_from(data, offset)
        if magic != MAGIC:
            raise ValueError(f"no SP bank at {offset:#x}")
        if self.size == 0 or self.size % SECTOR or offset + self.size > len(data):
            raise ValueError(f"bank at {offset:#x}: bad size {self.size:#x}")
        self.offset = offset
        self.label = label.rstrip(b"\0").decode("ascii", "replace")
        self.data = data[offset:offset + self.size]
        self.cues = [Cue(self, i, self.data[self.cue_table + CUE_SIZE * i:self.cue_table + CUE_SIZE * (i + 1)])
                     for i in range(self.cue_count())]

    def cue_count(self):
        # The cue table ends at the next non-zero table offset; music banks leave the
        # layer/ADPCM offsets at 0 and go straight to the wave area.
        following = [x for x in (self.layer_table, self.adpcm_area, self.wave_area) if x]
        return (min(following) - self.cue_table) // CUE_SIZE

    # ------------------------------------------------------------------ RIFF waves

    def wave(self, cue):
        """The RIFF file of a 'riff' cue (u32 length, then the RIFF bytes)."""
        start = self.wave_area + cue.target
        length = struct.unpack_from("<I", self.data, start)[0]
        return self.data[start + 4:start + 4 + length]

    def wave_spans(self):
        """Distinct (start, end) of the length-prefixed waves, relative to the wave area."""
        spans = set()
        for cue in self.cues:
            if cue.kind == "riff":
                length = struct.unpack_from("<I", self.data, self.wave_area + cue.target)[0]
                spans.add((cue.target, cue.target + 4 + length))
        return sorted(spans)

    # ------------------------------------------------------------------ ADPCM layers

    def layer_list(self, cue):
        """[(sample offset, envelope offset)] of an 'adpcm' cue."""
        base = self.layer_table + cue.target
        return [LAYER.unpack_from(self.data, base + LAYER.size * k) for k in range(cue.layers)]

    def sample(self, sample_offset):
        """(pitch, rate, PS-ADPCM bytes) of one sample in the ADPCM area."""
        start = self.adpcm_area + sample_offset
        length, pitch, rate = SAMPLE_HEADER.unpack_from(self.data, start)
        return pitch, rate, self.data[start + SAMPLE_HEADER.size:start + SAMPLE_HEADER.size + length]

    def envelope(self, envelope_offset):
        start = self.envelope_table + envelope_offset
        return self.data[start:start + ENVELOPE_SIZE]


def parse(data):
    """All banks of the chain, in file order."""
    banks, offset = [], 0
    while offset < len(data):
        bank = Bank(data, offset)
        banks.append(bank)
        offset += bank.size
    return banks


def riff_chunks(riff):
    """{chunk id: bytes} of a RIFF/WAVE file."""
    if riff[:4] != b"RIFF" or riff[8:12] != b"WAVE":
        raise ValueError("not a RIFF/WAVE file")
    chunks, position = {}, 12
    while position + 8 <= len(riff):
        chunk_id, length = struct.unpack_from("<4sI", riff, position)
        chunks[chunk_id.decode("ascii", "replace")] = riff[position + 8:position + 8 + length]
        position += 8 + length + (length & 1)
    return chunks


def wave_info(riff):
    """Codec name, channels, sample rate and sample count (from 'fact', or None)."""
    chunks = riff_chunks(riff)
    tag, channels, rate = struct.unpack_from("<HHI", chunks["fmt "], 0)
    samples = struct.unpack_from("<I", chunks["fact"], 0)[0] if "fact" in chunks else None
    return {"codec": WAVE_FORMATS.get(tag, f"0x{tag:04x}"), "channels": channels, "rate": rate, "samples": samples}


def decode_adpcm(blob):
    """PS-ADPCM -> list of int16 samples. Stops after the first frame with the end bit (flag bit 0)."""
    out, s1, s2 = [], 0, 0
    for position in range(0, len(blob) - ADPCM_FRAME + 1, ADPCM_FRAME):
        shift, predictor, flags = blob[position] & 0xF, blob[position] >> 4, blob[position + 1]
        f0, f1 = FILTERS[predictor] if predictor < len(FILTERS) else (0, 0)
        for byte in blob[position + 2:position + ADPCM_FRAME]:
            for nibble in (byte & 0xF, byte >> 4):
                value = ((nibble ^ 8) - 8) << 12 >> shift if shift <= 12 else 0
                value += (s1 * f0 + s2 * f1 + 32) >> 6
                value = max(-32768, min(32767, value))
                out.append(value)
                s1, s2 = value, s1
        if flags & 1:
            break
    return out


def pcm_wav(samples, rate):
    pcm = struct.pack(f"<{len(samples)}h", *samples)
    fmt = struct.pack("<HHIIHH", 1, 1, rate, rate * 2, 2, 16)
    return (b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVE" + b"fmt " + struct.pack("<I", 16) + fmt
            + b"data" + struct.pack("<I", len(pcm)) + pcm)


# ---------------------------------------------------------------------- checks

def check_bank(bank, number):
    problems = []
    say = problems.append
    where = f"bank {number} (serial {bank.serial}, {bank.offset:#x})"
    if bank.serial != number:
        say(f"{where}: serial out of sequence")
    if bank.data[-4:] != FOOTER + struct.pack("<H", bank.serial):
        say(f"{where}: no 'EP' footer with the bank's serial")
    if bank.cue_table != 0x30 or (min(x for x in (bank.layer_table, bank.adpcm_area, bank.wave_area) if x)
                                  - bank.cue_table) % CUE_SIZE:
        say(f"{where}: cue table does not start at 0x30 or is not a whole number of cues")
    spans = bank.wave_spans()
    position = 0
    for start, end in spans:
        if start != position:
            say(f"{where}: wave at {start:#x} does not follow the previous one ({position:#x})")
        position = end
    wave_end = bank.wave_area + position
    used_end = bank.end if bank.end else wave_end
    if bank.envelope_table and bank.envelope_table != wave_end:
        say(f"{where}: envelope table {bank.envelope_table:#x} is not right after the waves ({wave_end:#x})")
    if any(bank.data[used_end:bank.size - 4]):
        say(f"{where}: non-zero bytes between the used data and the footer")
    for cue in bank.cues:
        name = f"{where} cue {cue.index}"
        try:
            if cue.kind == "riff":
                riff = bank.wave(cue)
                if struct.unpack_from("<I", riff, 4)[0] + 8 != len(riff):
                    say(f"{name}: RIFF size disagrees with the length prefix")
                info = wave_info(riff)
                if info["codec"] not in WAVE_FORMATS.values():
                    say(f"{name}: unexpected codec {info['codec']}")
                if info["samples"] is not None and \
                        abs(info["samples"] * 1000 / info["rate"] - cue.duration_ms) > DURATION_TOLERANCE_MS:
                    say(f"{name}: duration {cue.duration_ms} ms disagrees with the fact chunk")
                continue
            for sample_offset, envelope_offset in bank.layer_list(cue):
                pitch, rate, blob = bank.sample(sample_offset)
                if bank.adpcm_area + sample_offset + SAMPLE_HEADER.size + len(blob) > bank.wave_area:
                    say(f"{name}: ADPCM sample runs into the wave area")
                if len(blob) % ADPCM_FRAME or not blob or not blob[-ADPCM_FRAME + 1] & 1:
                    say(f"{name}: ADPCM sample is not whole frames ending with the end flag")
                if pitch != rate * 4096 // 44100:
                    say(f"{name}: pitch {pitch} does not match rate {rate}")
                if envelope_offset % ENVELOPE_SIZE or \
                        bank.envelope_table + envelope_offset + ENVELOPE_SIZE > bank.end:
                    say(f"{name}: envelope offset {envelope_offset:#x} outside the envelope table")
        except (ValueError, KeyError, struct.error) as error:
            say(f"{name}: {error}")
    return problems


def check(banks):
    problems = []
    for number, bank in enumerate(banks):
        problems += check_bank(bank, number)
    return problems


# ---------------------------------------------------------------------- command line

def summary(bank):
    channels = set()
    for start, _ in bank.wave_spans():
        tag, count = struct.unpack_from("<HH", bank.data, bank.wave_area + start + 4 + 20)
        channels.add(count)
    adpcm = sum(1 for cue in bank.cues if cue.kind == "adpcm")
    return (f"{bank.serial:4d}  {bank.offset:#010x}  {bank.size:8d}  cues {len(bank.cues):3d}  "
            f"waves {len(bank.wave_spans()):3d}  adpcm {adpcm:2d}  ch {'/'.join(map(str, sorted(channels))) or '-':3s}  "
            f"{bank.label}")


def cue_line(bank, cue):
    head = (f"  {cue.index:3d}  vol {cue.volume:3d}  pan {cue.pan:3d}  flags {cue.flags:#x}  "
            f"{cue.duration_ms:7d} ms  ")
    if cue.kind == "riff":
        info = wave_info(bank.wave(cue))
        return head + f"riff @{cue.target:#x}  {info['codec']} {info['channels']}ch {info['rate']} Hz"
    layers = ", ".join(f"adpcm @{s:#x} {bank.sample(s)[1]} Hz env @{e:#x}" for s, e in bank.layer_list(cue))
    return head + f"{cue.layers} layer(s): {layers}"


def main(argv=None):
    parser = argparse.ArgumentParser(description="List, check and export the SP sound banks of psp_snddat.bin.")
    parser.add_argument("file", type=Path, help="snd/psp_snddat.bin")
    parser.add_argument("--bank", type=int, help="list the cues of this bank (by serial)")
    parser.add_argument("--check", action="store_true", help="run the structural checks over every bank")
    parser.add_argument("--export", metavar="BANK:CUE", help="export one cue (.at3 for RIFF, .wav for ADPCM)")
    parser.add_argument("-o", "--output", type=Path, help="export target file or directory (keep it out of git)")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    banks = parse(args.file.read_bytes())
    if args.check:
        problems = check(banks)
        if problems:
            print("\n".join(problems[:20]))
            return 1
        cues = sum(len(b.cues) for b in banks)
        waves = sum(len(b.wave_spans()) for b in banks)
        adpcm = sum(1 for b in banks for c in b.cues if c.kind == "adpcm")
        print(f"ok: {len(banks)} banks, {cues} cues, {waves} distinct RIFF waves, {adpcm} ADPCM cues")
        return 0
    if args.export:
        serial, index = (int(x) for x in args.export.split(":"))
        bank = banks[serial]
        cue = bank.cues[index]
        if cue.kind == "riff":
            blob, suffix = bank.wave(cue), ".at3"
        else:
            pitch, rate, adpcm = bank.sample(bank.layer_list(cue)[0][0])
            blob, suffix = pcm_wav(decode_adpcm(adpcm), rate), ".wav"
        target = args.output or Path(".")
        if target.is_dir() or not target.suffix:
            target.mkdir(parents=True, exist_ok=True)
            target = target / f"snd_{serial:03d}_{index:03d}{suffix}"
        target.write_bytes(blob)
        print(f"wrote {target} ({len(blob)} bytes)")
        return 0
    if args.bank is not None:
        bank = banks[args.bank]
        print(summary(bank))
        for cue in bank.cues:
            print(cue_line(bank, cue))
        return 0
    for bank in banks:
        print(summary(bank))
    return 0


if __name__ == "__main__":
    sys.exit(main())
