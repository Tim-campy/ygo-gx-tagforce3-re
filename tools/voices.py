#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Character voices: which sound bank and cue a (character, voice id) plays. See docs/formats/sound.md.

Reads the character table and the sound-id table in BOOT.BIN, the voice-test table in
gmodule/rel_charalist.prx, the per-character voice tables (*_voiceidchgtbl.bin) and caption tables
(chr_wordstbl_<l>.bin), and the bank chain in snd/psp_snddat.bin:

  voices.py <PSP_GAME> --check                      # cross-check every table against the banks
  voices.py <PSP_GAME> -o extracted/voices.csv      # one row per (character, voice-test item, voice)

The CSV holds game text (captions); keep it under extracted/, never in git.
"""

import argparse
import bisect
import csv
import importlib.util
import struct
import sys
from pathlib import Path


def _load(name):
    spec = importlib.util.spec_from_file_location(f"re_{name}", Path(__file__).resolve().parent / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ehp = _load("ehp")
sound = _load("sound")
prx_imports = _load("prx_imports")

BOOT_BASE = 0x08804000
BANK_OFFSET_TABLE = 0x0889CF20  # u32 per bank: byte offset of the bank in psp_snddat.bin
SOUND_ID_TABLE = 0x0889DA80  # u16 per bank: global sound id of the bank's cue 0
CHARACTER_TABLE = 0x088AA510  # 174 records of 148 bytes, sorted by (character, variant); bsearch in 0x0885adb0
CHARACTER_COUNT = 174
CHARACTER_SIZE = 148
SMALL_VOICES = 5  # voice ids 0-4 live in the 4 small banks (2 + 1 + 1 + 1 cues)
FULL_SET = 145  # cues in a named character's full voice bank (149 for one); generic students have 52
VOICE_SETS = 3  # a voice set is 3 banks with the same cue layout (full, reduced, more reduced)
# rel_charalist.prx (module-relative): the voice-test menu.
VOICE_TEST_STRINGS = 0xD82C  # u16 per item: entry of the module's strTbl_<l>.bin (event name)
VOICE_TEST_VOICES = 0xD938  # (s16, s16) per item: voice id played first, then a second one or -1
VOICE_TEST_COUNT = 134
LANGUAGES = "efgijs"


class Character:
    """One 148-byte record of the character table."""

    def __init__(self, boot, record):
        data = boot.data[boot.offset(record - BOOT_BASE):]
        self.character, self.variant = data[0], data[1]
        words = struct.unpack_from("<37I", data, 0)
        self.name = self._string(boot, words[1])
        self.cutin = self._string(boot, words[9])  # +0x24, for example "cutin_aska01.ehp"
        self.key = self._string(boot, words[14])  # +0x38, voice/profile key such as "ASUKA"
        self.voice_bank = words[12]  # +0x30: first bank of the voice set (0 = no voices)
        self.extra_bank = words[13]  # +0x34: first of the four small banks (3 when there are no voices)

    @staticmethod
    def _string(boot, pointer):
        return boot.string(pointer) if pointer else ""

    @property
    def table_name(self):
        """Voice-table member name in database/charalist.ehp, as rel_charalist builds it ("chr" + cut-in)."""
        if not self.cutin:
            return None
        return "chr" + self.cutin[:-len(".ehp")] + "_voiceidchgtbl.bin"


def characters(boot):
    return [Character(boot, CHARACTER_TABLE + CHARACTER_SIZE * i) for i in range(CHARACTER_COUNT)]


def boot_tables(boot, bank_count):
    offsets = boot.u32(BANK_OFFSET_TABLE - BOOT_BASE, bank_count)
    start = boot.offset(SOUND_ID_TABLE - BOOT_BASE)
    first_ids = struct.unpack_from(f"<{bank_count}H", boot.data, start)
    return offsets, first_ids


def expected_first_ids(cue_counts, music_banks=48):
    """Sound ids as BOOT.BIN numbers them: bank n < 48 (music) is id n; the cues of the other banks
    follow each other from id 728 (the number of banks) on."""
    ids, next_id = [], len(cue_counts)
    for serial, count in enumerate(cue_counts):
        if serial < music_banks:
            ids.append(serial)
        else:
            ids.append(next_id)
            next_id += count
    return ids


def locate(first_ids, cue_counts, sound_id):
    """(bank, cue) of a global sound id, or None."""
    order = sorted(range(len(first_ids)), key=lambda serial: first_ids[serial])
    starts = [first_ids[serial] for serial in order]
    position = bisect.bisect_right(starts, sound_id) - 1
    if position < 0:
        return None
    serial = order[position]
    cue = sound_id - first_ids[serial]
    return (serial, cue) if cue < cue_counts[serial] else None


def voice_sound_id(character, voice_id, first_ids):
    """Global sound id of a character's voice id (rel_charalist 0x5780): ids 0-4 count from the first
    small bank, ids from 5 on from the voice bank."""
    if voice_id < SMALL_VOICES:
        return first_ids[character.extra_bank] + voice_id
    return first_ids[character.voice_bank] + voice_id - SMALL_VOICES


def parse_change_table(blob):
    """Sub-tables of a *_voiceidchgtbl.bin: 16 u32 byte offsets, each to a u16 array that runs to the
    next offset. Sub-tables 0-2 follow the voice set's three banks and 3-6 the four small banks, one
    entry per cue; each entry is a line of the character's chr_wordstbl (the caption)."""
    heads = struct.unpack_from("<16I", blob, 0)
    tables = []
    for index, start in enumerate(heads):
        end = heads[index + 1] if index + 1 < len(heads) else len(blob)
        tables.append(list(struct.unpack_from(f"<{(end - start) // 2}H", blob, start)) if end > start else [])
    return tables


def string_table(blob):
    """Entries of a strTbl-format table: u32 count, u32 table offset, u32 string base, u32 offsets."""
    count, table, base = struct.unpack_from("<III", blob, 0)
    out = []
    for index in range(count):
        start = base + struct.unpack_from("<I", blob, table + 4 * index)[0]
        end = start
        while end + 1 < len(blob) and blob[end:end + 2] != b"\0\0":
            end += 2
        out.append(blob[start:end].decode("utf-16-le"))
    return out


def voice_test_items(charalist):
    """[(string index, (voice ids))] of the voice-test menu in rel_charalist.prx."""
    strings = struct.unpack_from(f"<{VOICE_TEST_COUNT}H", charalist.data, charalist.offset(VOICE_TEST_STRINGS))
    pairs = struct.unpack_from(f"<{2 * VOICE_TEST_COUNT}h", charalist.data, charalist.offset(VOICE_TEST_VOICES))
    return [(strings[i], tuple(v for v in pairs[2 * i:2 * i + 2] if v >= 0)) for i in range(VOICE_TEST_COUNT)]


def bank_layout(bank):
    """Per cue, the index of the first cue that plays the same wave."""
    first, layout = {}, []
    for cue in bank.cues:
        first.setdefault((cue.kind, cue.target), cue.index)
        layout.append(first[(cue.kind, cue.target)])
    return layout


def set_banks(character):
    return ([character.voice_bank + k for k in range(VOICE_SETS)]
            + [character.extra_bank + k for k in range(4)])


def zako_banks(number):
    """Voice set of chrzakov<number>_voiceidchgtbl.bin (50-82): banks 478 + 7 (number - 50) onwards.
    Hypothesis (medium): matched by layout only; the code that picks these tables was not traced."""
    first = ZAKO_FIRST_BANK + 7 * (number - ZAKO_FIRST_TABLE)
    return [first + k for k in range(7)]


ZAKO_FIRST_TABLE, ZAKO_FIRST_BANK = 50, 478


def check_banks(label, serials, tables, banks, captions=None, layout=True):
    """Problems of one voice table against its seven banks (voice set, then the small banks).
    With layout=False only the entry counts are compared."""
    problems = []
    for k, serial in enumerate(serials):
        bank, table = banks[serial], tables[k]
        if len(table) != len(bank.cues):
            problems.append(f"{label}: sub-table {k} has {len(table)} entries, bank {serial} "
                            f"has {len(bank.cues)} cues")
            continue
        if layout:
            for cue, first in enumerate(bank_layout(bank)):
                if table[cue] != table[first]:
                    problems.append(f"{label}: bank {serial} cues {first} and {cue} share a wave "
                                    f"but have captions {table[first]} and {table[cue]}")
        if captions is not None and table and max(table) >= len(captions):
            problems.append(f"{label}: sub-table {k} names caption {max(table)} of {len(captions)}")
    if any(tables[7:]):
        problems.append(f"{label}: sub-tables 7-15 are not empty")
    return problems


def check_character(character, tables, banks, captions=None, layout=True):
    return check_banks(character.name, set_banks(character), tables, banks, captions, layout)


# ---------------------------------------------------------------------- whole-disc checks and export

class Disc:
    def __init__(self, root):
        root = Path(root)
        usr = root / "USRDIR"
        self.boot = prx_imports.Elf((root / "SYSDIR" / "BOOT.BIN").read_bytes(), BOOT_BASE)
        self.charalist = prx_imports.Elf((usr / "gmodule" / "rel_charalist.prx").read_bytes(), 0)
        self.archive = dict(ehp.parse((usr / "database" / "charalist.ehp").read_bytes()))
        self.duel = usr / "duel"
        self.bank_data = (usr / "snd" / "psp_snddat.bin").read_bytes()
        self.banks = sound.parse(self.bank_data)
        self.characters = characters(self.boot)
        self.offsets, self.first_ids = boot_tables(self.boot, len(self.banks))

    def duel_archive(self, table):
        """The duel/ archive that carries the same voice table and its captions (chr_wordstbl_<l>):
        cutin_<name>.ehp for chrcutin_<name>, zakov<n>.ehp for chrzakov<n>."""
        stem = table[len("chr"):-len("_voiceidchgtbl.bin")]
        path = self.duel / f"{stem.lower()}.ehp"
        return dict(ehp.parse(path.read_bytes())) if path.exists() else None

    def check(self):
        problems = []
        if list(self.offsets) != [bank.offset for bank in self.banks]:
            problems.append("BOOT.BIN bank offset table does not match the bank chain")
        counts = [len(bank.cues) for bank in self.banks]
        if list(self.first_ids) != expected_first_ids(counts):
            problems.append("BOOT.BIN sound-id table does not number the cues as expected")
        checked, notes, owner = 0, [], {}
        for character in self.characters:
            blob = self.archive.get(character.table_name) if character.table_name else None
            if not character.voice_bank or blob is None:
                if character.voice_bank and character.voice_bank < ZAKO_FIRST_BANK:
                    notes.append(f"{character.name}: voice bank {character.voice_bank} but no voice table")
                continue
            cutin = self.duel_archive(character.table_name)
            captions = string_table(cutin["chr_wordstbl_e.bin"]) if cutin else None
            if cutin and cutin.get("chr_voiceidchgtbl.bin") != blob:
                problems.append(f"{character.name}: duel/{character.cutin} has a different voice table")
            # A table belongs to a cut-in; a second variant that shares the cut-in but has its own voice
            # set (KAMYURA_1, TANIYA_1) gets the first variant's captions: compare entry counts only.
            first = owner.setdefault(character.table_name, character.voice_bank)
            if first != character.voice_bank:
                notes.append(f"{character.name}: shares {character.table_name} with voice set {first}")
            problems += check_character(character, parse_change_table(blob), self.banks, captions,
                                        layout=first == character.voice_bank)
            checked += 1
        for name in sorted(self.archive):
            if name.startswith("chrzakov") and name.endswith("_voiceidchgtbl.bin"):
                number = int(name[len("chrzakov"):-len("_voiceidchgtbl.bin")])
                blob = self.archive[name]
                duel = self.duel_archive(name)
                if duel is None or duel.get("chr_voiceidchgtbl.bin") != blob:
                    problems.append(f"{name}: duel/zakov{number}.ehp is missing or has a different table")
                captions = string_table(duel["chr_wordstbl_e.bin"]) if duel else None
                problems += check_banks(name, zako_banks(number), parse_change_table(blob), self.banks, captions)
                checked += 1
        voices = {v for _, ids in voice_test_items(self.charalist) for v in ids}
        if voices != set(range(max(voices) + 1)):
            problems.append("the voice-test items do not cover voice ids 0..n without gaps")
        self.notes = notes
        return problems, checked

    def rows(self, language="e"):
        names = string_table(self.archive[f"strTbl_{language}.bin"])
        items = voice_test_items(self.charalist)
        counts = [len(b.cues) for b in self.banks]
        for character in self.characters:
            if not character.voice_bank:
                continue
            table = self.table_name(character)
            tables = parse_change_table(self.archive[table]) if table else None
            cutin = self.duel_archive(table) if table else None
            words = cutin.get(f"chr_wordstbl_{language}.bin") if cutin else None
            captions = string_table(words) if words else []
            sets = set_banks(character)
            if counts[character.voice_bank] < FULL_SET:
                # Generic students (52-cue sets): the voice-test layout does not apply; list the cues.
                listing = [(None, "", SMALL_VOICES + cue) for cue in range(counts[character.voice_bank])]
            else:
                listing = [(number, names[string], voice) for number, (string, ids) in enumerate(items)
                           for voice in ids]
            listing = [(None, "", voice) for voice in range(SMALL_VOICES)] * (listing[0][0] is None) + listing
            for number, event, voice in listing:
                if voice >= SMALL_VOICES and voice - SMALL_VOICES >= counts[character.voice_bank]:
                    continue  # this character has no such voice (shorter bank, e.g. ids 150-153)
                serial, cue = locate(self.first_ids, counts, voice_sound_id(character, voice, self.first_ids))
                word = tables[sets.index(serial)][cue] if tables else ""
                yield {"character": character.character, "variant": character.variant,
                       "name": character.name, "table": table or "", "item": "" if number is None else number,
                       "event": event, "voice": voice, "bank": serial, "cue": cue,
                       "ms": self.banks[serial].cues[cue].duration_ms, "word": word,
                       "caption": captions[word] if tables and word < len(captions) else ""}

    def table_name(self, character):
        """The voice table of a character: by cut-in name, else (generic students) by voice set."""
        if character.table_name in self.archive:
            return character.table_name
        number = ZAKO_FIRST_TABLE + (character.voice_bank - ZAKO_FIRST_BANK) // 7
        name = f"chrzakov{number}_voiceidchgtbl.bin"
        if character.voice_bank >= ZAKO_FIRST_BANK and zako_banks(number)[0] == character.voice_bank \
                and name in self.archive:
            return name
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Map character voices to sound banks and captions.")
    parser.add_argument("root", type=Path, help="the extracted PSP_GAME directory")
    parser.add_argument("--check", action="store_true", help="only run the cross-checks")
    parser.add_argument("--language", choices=list(LANGUAGES), default="e", help="caption/event language")
    parser.add_argument("-o", "--output", type=Path, help="CSV target (keep it out of git); default stdout")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    disc = Disc(args.root)
    if args.check:
        problems, checked = disc.check()
        for note in disc.notes:
            print("note:", note)
        print("\n".join(problems[:20]) if problems else f"ok: {checked} voice tables, "
              f"{len(disc.banks)} banks, {VOICE_TEST_COUNT} voice-test items")
        return 1 if problems else 0
    rows = list(disc.rows(args.language))
    out = open(args.output, "w", encoding="utf-8", newline="") if args.output else sys.stdout
    try:
        writer = csv.DictWriter(out, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    finally:
        if args.output:
            out.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
