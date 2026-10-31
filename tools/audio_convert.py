#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Install-time audio conversion of snd/psp_snddat.bin to WAV / OGG / FLAC. See docs/formats/sound.md.

  audio_convert.py <psp_snddat.bin> --survey                 codec census of every stored stream
  audio_convert.py <psp_snddat.bin> --check [--jobs N]       decode every stream (nothing written), report
  audio_convert.py <psp_snddat.bin> -o DIR [--bank N ...] [--format wav|ogg|flac]

ATRAC3 and ATRAC3plus waves are stored as complete RIFF/WAVE (.at3) files, which FFmpeg's `wav` demuxer
and `atrac3` / `atrac3p` decoders read as they are; the tool pipes each one through `ffmpeg` (which must be
on PATH, or given with --ffmpeg), then trims the decoder output with the `fact` chunk: skip
`first_sample_offset + decoder delay` samples, keep `sample_count`. PS-ADPCM layers are decoded natively
(tools/sound.py). Loop points (RIFF `smpl` chunks, PS-ADPCM loop flags) are converted to output sample
indices and written, with the cue metadata, to one JSON file per bank.

This is the conversion a port runs once on the user's own disc. The output is game content: write it
outside the repository (for example a scratch directory) and never commit it.
"""

import argparse
import collections
import importlib.util
import json
import math
import shutil
import struct
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def _load(name):
    spec = importlib.util.spec_from_file_location(f"re_{name}", Path(__file__).resolve().parent / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sound = _load("sound")

TAG_ATRAC3, TAG_EXTENSIBLE = 0x0270, 0xFFFE
# KSDATAFORMAT_SUBTYPE for ATRAC3plus in WAVE_FORMAT_EXTENSIBLE, as stored in the disc's waves:
# E923AABF-CB58-4471-A119-FFFA01E4CE62.
ATRAC3PLUS_GUID = bytes.fromhex("bfaa23e958cb7144a119fffa01e4ce62")
SAMPLES_PER_FRAME = {"ATRAC3": 1024, "ATRAC3plus": 2048}
# Samples the decoder emits before sample 0 of a stream, on top of the fact chunk's first-sample offset.
# Basis: for all 18,608 waves, data frames == ceil((offset + delay + sample_count) / frame size) with these
# values (and not with 0); PPSSPP's sceAtrac emulation uses the same constants (0x45 / 0x170).
DECODER_DELAY = {"ATRAC3": 69, "ATRAC3plus": 368}
ATRAC3PLUS_RATES = (32000, 44100, 48000, 88200, 96000)  # rate index of the 16-bit codec parameter word
CHANNEL_MASKS = {1: 0x1, 2: 0x3}  # as in the disc waves (front left; front left + right)
ADPCM_LOOP_START, ADPCM_LOOP_END = 0x04, 0x02  # PS-ADPCM frame flag bits (bit 0 = end of sample)
DURATION_TOLERANCE_MS = 2


# ---------------------------------------------------------------------- RIFF helpers

def pcm_wav(pcm, channels, rate):
    """A 16-bit PCM RIFF/WAVE file around interleaved little-endian samples (bytes)."""
    fmt = struct.pack("<HHIIHH", 1, channels, rate, rate * 2 * channels, 2 * channels, 16)
    return (b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVE" + b"fmt " + struct.pack("<I", 16) + fmt
            + b"data" + struct.pack("<I", len(pcm)) + pcm)


def atrac3plus_params(frame_bytes, channels, rate=44100):
    """The 16-bit ATRAC3plus codec parameter word (as in OMA headers and PSMF frame headers)."""
    if frame_bytes % 8 or not 8 <= frame_bytes <= 0x2000:
        raise ValueError(f"ATRAC3plus frame size {frame_bytes} is not a multiple of 8 in 8..8192")
    return (ATRAC3PLUS_RATES.index(rate) << 13) | (channels << 10) | (frame_bytes // 8 - 1)


def parse_atrac3plus_params(word):
    """(frame bytes, channels, sample rate) of a 16-bit ATRAC3plus codec parameter word."""
    return ((word & 0x3FF) + 1) * 8, (word >> 10) & 7, ATRAC3PLUS_RATES[(word >> 13) & 7]


def atrac3plus_riff(frames, frame_bytes, channels, rate=44100, sample_count=None, first_sample_offset=0):
    """Wrap raw ATRAC3plus frames (no per-frame headers) in a RIFF/WAVE (.at3) file.

    The layout copies the disc's own ATRAC3plus waves: a 52-byte WAVE_FORMAT_EXTENSIBLE `fmt ` chunk
    (cbSize 34, 2048 samples per block, channel mask, the ATRAC3plus GUID, then u16 1, the big-endian
    codec parameter word and 8 zero bytes), an 8-byte `fact` chunk (sample count, first-sample offset) and
    the `data` chunk.
    """
    if len(frames) % frame_bytes:
        raise ValueError("data is not a whole number of frames")
    params = atrac3plus_params(frame_bytes, channels, rate)
    average = (frame_bytes * rate + 1024) // 2048
    fmt = (struct.pack("<HHIIHHHHI", TAG_EXTENSIBLE, channels, rate, average, frame_bytes, 0, 34, 2048,
                       CHANNEL_MASKS.get(channels, 0)) + ATRAC3PLUS_GUID
           + struct.pack("<H", 1) + struct.pack(">H", params) + bytes(8))
    if sample_count is None:
        sample_count = len(frames) // frame_bytes * 2048 - first_sample_offset - DECODER_DELAY["ATRAC3plus"]
    fact = struct.pack("<II", max(sample_count, 0), first_sample_offset)
    body = (b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"fact" + struct.pack("<I", len(fact)) + fact
            + b"data" + struct.pack("<I", len(frames)) + frames)
    return b"RIFF" + struct.pack("<I", len(body)) + body


def atrac_info(riff):
    """Codec facts of a stored ATRAC wave: codec, channels, rate, block_align, bitrate, sample count,
    first-sample offset, frame count and loops [(start, end)] in raw `smpl` units."""
    chunks = sound.riff_chunks(riff)
    fmt = chunks["fmt "]
    tag, channels, rate, average, block_align = struct.unpack_from("<HHIIH", fmt)
    if tag == TAG_ATRAC3:
        codec = "ATRAC3"
    elif tag == TAG_EXTENSIBLE and fmt[24:40] == ATRAC3PLUS_GUID:
        codec = "ATRAC3plus"
    else:
        raise ValueError(f"unsupported fmt tag {tag:#06x}")
    fact = chunks.get("fact", b"")
    sample_count, first_offset = struct.unpack_from("<II", fact) if len(fact) >= 8 else (None, 0)
    loops = []
    smpl = chunks.get("smpl")
    if smpl and len(smpl) >= 36:
        count = struct.unpack_from("<I", smpl, 28)[0]
        for i in range(count):
            if 36 + 24 * (i + 1) <= len(smpl):
                _, _, start, end, _, _ = struct.unpack_from("<6I", smpl, 36 + 24 * i)
                loops.append((start, end))
    return {"codec": codec, "channels": channels, "rate": rate, "block_align": block_align,
            "bitrate": round(block_align * 8 * rate / SAMPLES_PER_FRAME[codec]),
            "samples": sample_count, "first_offset": first_offset,
            "frames": len(chunks["data"]) // block_align, "frame_remainder": len(chunks["data"]) % block_align,
            "loops": loops}


def skip_samples(info):
    """Decoder output samples (per channel) that precede output sample 0."""
    return info["first_offset"] + DECODER_DELAY[info["codec"]]


def output_loop(info, loop):
    """A `smpl` loop (start, end) in output sample indices: the stored values count from the fact chunk's
    first-sample offset (music loops start at it and end at offset + sample_count - 1), end inclusive."""
    start, end = loop
    return {"start": start - info["first_offset"], "end": end - info["first_offset"]}


def trim(pcm, info):
    """Trim interleaved 16-bit decoder output to the stream's own samples (fact chunk)."""
    frame = 2 * info["channels"]
    start = skip_samples(info) * frame
    return pcm[start:start + info["samples"] * frame] if info["samples"] is not None else pcm[start:]


# ---------------------------------------------------------------------- PS-ADPCM loops

def adpcm_loop(blob):
    """(start, end) output sample indices (end inclusive) of a looping PS-ADPCM sample, or None."""
    start = end = None
    for index, position in enumerate(range(0, len(blob) - 15, 16)):
        flags = blob[position + 1]
        if flags & ADPCM_LOOP_START and start is None:
            start = index * sound.SAMPLES_PER_FRAME
        if flags & 1:
            if flags & ADPCM_LOOP_END and start is not None:
                end = (index + 1) * sound.SAMPLES_PER_FRAME - 1
            break
    return {"start": start, "end": end} if start is not None and end is not None else None


# ---------------------------------------------------------------------- ffmpeg

class FfmpegError(RuntimeError):
    pass


def find_ffmpeg(explicit=None):
    path = explicit or shutil.which("ffmpeg")
    if not path:
        raise FfmpegError("ffmpeg not found: install FFmpeg (with the atrac3/atrac3p decoders) or pass --ffmpeg")
    return path


def ffmpeg_decode(ffmpeg, riff, input_format="wav"):
    """Decode a whole input file (bytes) to interleaved s16le PCM with ffmpeg (stdin -> stdout)."""
    result = subprocess.run([ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "fatal", "-f", input_format,
                             "-i", "pipe:0", "-f", "s16le", "-acodec", "pcm_s16le", "pipe:1"],
                            input=riff, capture_output=True)
    if result.returncode:
        raise FfmpegError(result.stderr.decode("utf-8", "replace").strip()[-300:] or f"exit {result.returncode}")
    return result.stdout


def ffmpeg_encode(ffmpeg, pcm, channels, rate, target, metadata=()):
    """Encode interleaved s16le PCM to `target` (codec chosen by its suffix: .ogg Vorbis, .flac FLAC)."""
    codec = {".ogg": ["-c:a", "libvorbis", "-q:a", "6"], ".flac": ["-c:a", "flac"]}[target.suffix]
    tags = [arg for key, value in metadata for arg in ("-metadata", f"{key}={value}")]
    result = subprocess.run([ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error", "-y", "-f", "s16le",
                             "-ar", str(rate), "-ac", str(channels), "-i", "pipe:0", *codec, *tags, str(target)],
                            input=pcm, capture_output=True)
    if result.returncode:
        raise FfmpegError(result.stderr.decode("utf-8", "replace").strip()[-300:])


# ---------------------------------------------------------------------- per-bank work

def bank_streams(bank):
    """Distinct streams of a bank: ('riff', wave offset, first cue) and ('adpcm', sample offset, cue, layer)."""
    streams, seen = [], set()
    for cue in bank.cues:
        if cue.kind == "riff":
            if ("riff", cue.target) not in seen:
                seen.add(("riff", cue.target))
                streams.append(("riff", cue.target, cue.index, 0))
        else:
            for layer, (sample_offset, _) in enumerate(bank.layer_list(cue)):
                if ("adpcm", sample_offset) not in seen:
                    seen.add(("adpcm", sample_offset))
                    streams.append(("adpcm", sample_offset, cue.index, layer))
    return streams


def stream_name(bank, kind, cue_index, layer):
    return f"snd_{bank.serial:03d}_{cue_index:03d}" + (f"_{layer}" if kind == "adpcm" and layer else "")


def decode_stream(bank, kind, offset, ffmpeg):
    """(pcm bytes, channels, rate, facts dict) of one stream."""
    if kind == "adpcm":
        pitch, rate, blob = bank.sample(offset)
        samples = sound.decode_adpcm(blob)
        facts = {"codec": "PS-ADPCM", "channels": 1, "rate": rate, "pitch": pitch, "samples": len(samples),
                 "loop": adpcm_loop(blob)}
        return struct.pack(f"<{len(samples)}h", *samples), 1, rate, facts
    length = struct.unpack_from("<I", bank.data, bank.wave_area + offset)[0]
    riff = bank.data[bank.wave_area + offset + 4:bank.wave_area + offset + 4 + length]
    info = atrac_info(riff)
    raw = ffmpeg_decode(ffmpeg, riff)
    decoded = len(raw) // (2 * info["channels"])
    expected = info["frames"] * SAMPLES_PER_FRAME[info["codec"]]
    if decoded != expected:
        raise FfmpegError(f"decoded {decoded} samples, expected {expected} ({info['frames']} frames)")
    if info["samples"] is not None and skip_samples(info) + info["samples"] > decoded:
        raise FfmpegError(f"fact chunk wants {skip_samples(info) + info['samples']} samples, decoded {decoded}")
    loops = [output_loop(info, loop) for loop in info["loops"]]
    facts = {"codec": info["codec"], "channels": info["channels"], "rate": info["rate"],
             "bitrate": info["bitrate"], "block_align": info["block_align"],
             "samples": info["samples"], "loop": loops[0] if loops else None}
    return trim(raw, info), info["channels"], info["rate"], facts


def process_bank(bank, ffmpeg, output=None, suffix=".wav"):
    """Decode every stream of a bank; write files and the bank JSON when `output` is a directory.
    Returns (problems, {stream name: facts})."""
    problems, results = [], {}
    for kind, offset, cue_index, layer in bank_streams(bank):
        name = stream_name(bank, kind, cue_index, layer)
        try:
            pcm, channels, rate, facts = decode_stream(bank, kind, offset, ffmpeg)
            frames = len(pcm) // (2 * channels)
            loop = facts["loop"]
            if loop and not 0 <= loop["start"] <= loop["end"] < frames:
                problems.append(f"{name}: loop {loop} outside 0..{frames - 1}")
            facts["seconds"] = frames / rate
            if output is not None:
                target = output / (name + suffix)
                if suffix == ".wav":
                    target.write_bytes(pcm_wav(pcm, channels, rate))
                else:
                    tags = [("LOOPSTART", loop["start"]), ("LOOPLENGTH", loop["end"] - loop["start"] + 1)] if loop else []
                    ffmpeg_encode(ffmpeg, pcm, channels, rate, target, tags)
                facts["file"] = target.name
            results[(kind, offset)] = facts
        except (FfmpegError, ValueError, KeyError, struct.error) as error:
            problems.append(f"{name}: {error}")
    for cue in bank.cues:
        if cue.kind == "riff" and ("riff", cue.target) in results:
            seconds = results[("riff", cue.target)]["seconds"]
            if abs(seconds * 1000 - cue.duration_ms) > DURATION_TOLERANCE_MS:
                problems.append(f"bank {bank.serial} cue {cue.index}: decoded {seconds * 1000:.0f} ms, "
                                f"cue says {cue.duration_ms} ms")
    if output is not None:
        (output / f"snd_{bank.serial:03d}.json").write_text(json.dumps(bank_json(bank, results), indent=1) + "\n")
    return problems, results


def bank_json(bank, results):
    cues = []
    for cue in bank.cues:
        entry = {"cue": cue.index, "volume": cue.volume, "pan": cue.pan, "flags": cue.flags,
                 "duration_ms": cue.duration_ms}
        if cue.kind == "riff":
            keys = [("riff", cue.target)]
        else:
            layers = bank.layer_list(cue)
            keys = [("adpcm", s) for s, _ in layers]
            entry["envelopes"] = [bank.envelope(e).hex() for _, e in layers]
        entry["streams"] = [{k: v for k, v in results[key].items() if k != "seconds"}
                            for key in keys if key in results]
        cues.append(entry)
    return {"bank": bank.serial, "label": bank.label, "cues": cues}


# ---------------------------------------------------------------------- survey

def survey(banks):
    """Census lines of every distinct stored stream (no decoding)."""
    census = collections.Counter()
    delays = collections.Counter()
    loops = collections.Counter()
    padding = collections.Counter()
    for bank in banks:
        for kind, offset, cue_index, _ in bank_streams(bank):
            if kind == "adpcm":
                pitch, rate, blob = bank.sample(offset)
                census[("PS-ADPCM", 1, rate, "-", "-")] += 1
                loops["PS-ADPCM"] += adpcm_loop(blob) is not None
                continue
            length = struct.unpack_from("<I", bank.data, bank.wave_area + offset)[0]
            info = atrac_info(bank.data[bank.wave_area + offset + 4:bank.wave_area + offset + 4 + length])
            census[(info["codec"], info["channels"], info["rate"], info["block_align"], info["bitrate"])] += 1
            delays[(info["codec"], "default" if info["first_offset"] in (1024, 2048) else "other")] += 1
            loops[info["codec"]] += bool(info["loops"])
            need = math.ceil((skip_samples(info) + (info["samples"] or 0)) / SAMPLES_PER_FRAME[info["codec"]])
            padding[(info["codec"], need == info["frames"] and not info["frame_remainder"])] += 1
    lines = ["codec        ch  rate   block  bitrate  streams"]
    for (codec, channels, rate, block, bitrate), count in sorted(census.items(), key=str):
        lines.append(f"{codec:12} {channels:2d}  {rate:5d}  {block!s:>5}  {bitrate!s:>7}  {count:7d}")
    lines.append("first-sample offset (fact): " + ", ".join(f"{c} {k}: {n}" for (c, k), n in sorted(delays.items())))
    lines.append("streams with loop points: " + ", ".join(f"{c}: {n}" for c, n in sorted(loops.items())))
    lines.append("frame count == ceil((offset + decoder delay + samples) / frame): "
                 + ", ".join(f"{c} {'yes' if ok else 'NO'}: {n}" for (c, ok), n in sorted(padding.items())))
    return lines


# ---------------------------------------------------------------------- command line

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("file", type=Path, help="snd/psp_snddat.bin")
    parser.add_argument("--survey", action="store_true", help="codec census of every stored stream (no decoding)")
    parser.add_argument("--check", action="store_true", help="decode every stream with ffmpeg, write nothing")
    parser.add_argument("-o", "--output", type=Path, help="output directory (outside the repository)")
    parser.add_argument("--bank", type=int, action="append", help="limit to this bank serial (repeatable)")
    parser.add_argument("--format", choices=("wav", "ogg", "flac"), default="wav")
    parser.add_argument("--ffmpeg", help="path of the ffmpeg executable (default: from PATH)")
    parser.add_argument("--jobs", type=int, default=8, help="banks processed in parallel")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    banks = sound.parse(args.file.read_bytes())
    if args.bank:
        banks = [b for b in banks if b.serial in set(args.bank)]
    if args.survey:
        print("\n".join(survey(banks)))
        return 0
    if not args.check and args.output is None:
        parser.error("give --survey, --check or -o DIR")
    try:
        ffmpeg = find_ffmpeg(args.ffmpeg)
    except FfmpegError as error:
        print(error)
        return 2
    if args.output is not None:
        args.output.mkdir(parents=True, exist_ok=True)
    output = None if args.check else args.output
    with ThreadPoolExecutor(max(1, args.jobs)) as pool:
        results = list(pool.map(lambda b: process_bank(b, ffmpeg, output, "." + args.format), banks))
    problems = [p for found, _ in results for p in found]
    totals = collections.Counter()
    seconds = collections.Counter()
    for _, streams in results:
        for facts in streams.values():
            totals[facts["codec"]] += 1
            seconds[facts["codec"]] += facts["seconds"]
    if problems:
        print("\n".join(problems[:40]))
        if len(problems) > 40:
            print(f"... {len(problems) - 40} more")
    summary = ", ".join(f"{c} {totals[c]} ({seconds[c] / 60:.1f} min)" for c in sorted(totals))
    print(f"{'FAILED' if problems else 'ok'}: {len(banks)} banks, {sum(totals.values())} streams decoded: {summary}"
          + (f"; {len(problems)} problems" if problems else ""))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
