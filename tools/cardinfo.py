#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read the card database in duelsys/cardinfo_<lang>.ehp. See docs/formats/cardinfo.md.

Decodes card properties (CARD_Prop), passcodes (CARD_Pass), the id -> index map (CARD_IntID),
names (CARD_Indx + CARD_Name) and Huffman-coded descriptions (CARD_Desc + CARD_Huff) with their
dictionary references (DICT). Output goes to stdout or a file; keep it under extracted/, never in git.
"""

import argparse
import csv
import importlib.util
import json
import struct
import sys
import unicodedata
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_ehp", Path(__file__).resolve().parent / "ehp.py")
ehp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ehp)

FIRST_ID = 0xE88  # card ids below this have no entry (CARD_IntID starts here)
LANG_SUFFIX = {"eng": "E", "fra": "F", "ger": "G", "ita": "I", "spa": "S"}
GENRE_FIRST_DLG = 701  # genre n is named by DLG entry 701 + n (0x08833064, n = 0..39)
GENRE_COUNT = 40
# Characters CARD_Sort ignores; other punctuation and spaces sort before digits, digits before letters.
SORT_IGNORED = "-'"
SORT_EXPANSIONS = {"œ": "oe"}  # oe ligature; casefold already turns sharp s into "ss"


def collation_key(name):
    """Sort key that reproduces CARD_Sort in all five languages (ties are broken by record index).

    Case-insensitive; '-' and apostrophes are ignored; accents are dropped (e -> e, u-umlaut -> u);
    then each character is weighed as (class, character) with class 0 for spaces and punctuation,
    1 for digits and 2 for letters. See docs/formats/cardinfo.md for which parts the data constrain.
    """
    key = []
    for char in name.casefold():
        if char in SORT_IGNORED:
            continue
        for c in SORT_EXPANSIONS.get(char, char):
            base = unicodedata.normalize("NFD", c)[0]
            c = base if base.isascii() else c
            key.append((1 if c.isdigit() else 2 if c.isalpha() else 0, c))
    return tuple(key)


def unpack_prop(w0, w1):
    """Fields of one 8-byte CARD_Prop record. Enumerations are listed in docs/formats/cardinfo.md."""
    return {
        "id": w0 & 0x3FFF,
        "atk": ((w0 >> 14) & 0x1FF) * 10,
        "def": (w0 >> 23) * 10,
        "kind": w1 & 0x3F,
        "attribute": (w1 >> 6) & 0xF,
        "level": (w1 >> 10) & 0xF,
        "icon": (w1 >> 14) & 0x7,
        "race": (w1 >> 17) & 0x1F,
        "unknown_22": w1 >> 22,
    }


def utf16z(data, offset):
    """Read a NUL-terminated UTF-16LE string."""
    end = offset
    while data[end:end + 2] != b"\0\0":
        end += 2
    return data[offset:end].decode("utf-16-le")


class CardInfo:
    def __init__(self, archive_bytes, suffix):
        members = dict(ehp.parse(archive_bytes))

        def member(name):
            return members[name]

        self.prop = member("CARD_Prop.bin")
        self.count = len(self.prop) // 8
        self.passes = struct.unpack(f"<{self.count}I", member("CARD_Pass.bin"))
        intid = member("CARD_IntID.bin")
        self.intid = struct.unpack(f"<{len(intid) // 2}H", intid)
        self.indx = member(f"CARD_Indx_{suffix}.bin")
        self.names = member(f"CARD_Name_{suffix}.bin")
        self.desc = member(f"CARD_Desc_{suffix}.bin")
        self.huff = member(f"CARD_Huff_{suffix}.bin")
        self.dict = member(f"DICT_{suffix}.bin")
        # Optional members (a hand-built test archive may leave them out).
        self.genre = members.get("CARD_Genre.bin")
        self.sort = members.get(f"CARD_Sort_{suffix}.bin")
        self.top = members.get(f"CARD_Top_{suffix}.bin")
        dlg_indx, dlg_text = members.get(f"DLG_Indx_{suffix}.bin"), members.get(f"DLG_Text_{suffix}.bin")
        self.dialog = ([utf16z(dlg_text, offset) for offset in struct.unpack(f"<{len(dlg_indx) // 4}I", dlg_indx)]
                       if dlg_indx and dlg_text else [])

    # ------------------------------------------------------------------ genres and sorting

    def genre_mask(self, index):
        """The 48 CARD_Genre bits of a record as an int (three u16, bit n = u16[n >> 4] bit n & 15,
        as 0x08833004 tests them)."""
        if not self.genre:
            return 0
        low, mid, high = struct.unpack_from("<3H", self.genre, 6 * index)
        return low | mid << 16 | high << 32

    def genre_name(self, bit):
        """Name of genre bit n: DLG entry 701 + n in the archive's language (0x08833064)."""
        number = GENRE_FIRST_DLG + bit
        if bit < GENRE_COUNT and number < len(self.dialog) and self.dialog[number]:
            return self.dialog[number]
        return f"genre{bit}"

    def genres(self, index):
        mask = self.genre_mask(index)
        return [self.genre_name(bit) for bit in range(48) if mask >> bit & 1]

    def sort_positions(self):
        """CARD_Sort as a list (record -> position in the alphabetical list), or None."""
        return list(struct.unpack(f"<{self.count}H", self.sort)) if self.sort else None

    def collated_positions(self):
        """Positions computed with collation_key; equal to CARD_Sort on the disc in all languages."""
        order = sorted(range(1, self.count), key=lambda index: (collation_key(self.name(index)), index))
        positions = [0] * self.count
        for position, index in enumerate(order, 1):
            positions[index] = position
        return positions

    def top_entries(self):
        """CARD_Top: [(character, card id)]."""
        if not self.top:
            return []
        count = struct.unpack_from("<H", self.top, 0)[0]
        return [(chr(c), card_id) for c, card_id in
                (struct.unpack_from("<HH", self.top, 2 + 4 * k) for k in range(count))]

    # ------------------------------------------------------------------ lookups

    def index_of(self, card_id):
        """Same as the game's 0x08832a1c: 0 (the empty record) for unknown ids."""
        position = card_id - FIRST_ID
        if position < 0 or position >= len(self.intid):
            return 0
        return self.intid[position]

    def entry(self, index):
        return struct.unpack_from("<II", self.indx, 8 * index)

    def name(self, index):
        return utf16z(self.names, self.entry(index)[0])

    def properties(self, index):
        return unpack_prop(*struct.unpack_from("<II", self.prop, 8 * index))

    # ------------------------------------------------------------------ descriptions

    def huffman(self, bit):
        """Decode one description starting at a bit offset; returns (text, end bit)."""
        out = []
        while True:
            node = 0
            while True:
                # At the very end the game peeks one byte past the stream; a leaf ignores the bit anyway.
                byte = self.desc[bit >> 3] if bit >> 3 < len(self.desc) else 0
                child = struct.unpack_from("<H", self.huff, 2 * (node + ((byte >> (7 - (bit & 7))) & 1)))[0]
                if child == 0:
                    break
                node = child >> 1
                bit += 1
            symbol = struct.unpack_from("<H", self.huff, 2 * (node + 2))[0]
            if symbol == 0:
                return "".join(out), bit
            out.append(chr(symbol))

    def dictionary(self, number):
        count, table, base = struct.unpack_from("<III", self.dict, 0)
        if number >= count:
            raise ValueError(f"dictionary entry {number} out of range ({count})")
        word = utf16z(self.dict, struct.unpack_from("<I", self.dict, table + 4 * number)[0] + base)
        return self.expand_card_names(word)

    def expand_card_names(self, text):
        """'%c' + four digits -> that card's name (game: 0x08836ed0)."""
        out, i = [], 0
        while i < len(text):
            if text.startswith("%c", i) and text[i + 2:i + 3].isdigit():
                out.append(self.name(self.index_of(int(text[i + 2:i + 6]))))
                i += 6
            else:
                out.append(text[i])
                i += 1
        return "".join(out)

    def expand(self, text):
        """'$d' + three digits -> dictionary word; other '$x' escapes are kept (game: 0x08833390)."""
        out, i = [], 0
        while i < len(text):
            if text.startswith("$d", i):
                # The game copies three characters, converts them with atoi (which stops at the first
                # non-digit) and always skips five; one Italian text relies on this ("$d02$").
                digits = text[i + 2:i + 5]
                number = int(digits[:len(digits) - len(digits.lstrip("0123456789"))] or 0)
                out.append(self.dictionary(number))
                i += 5
            elif text[i] == "$":
                out.append(text[i:i + 2])
                i += 2
            else:
                out.append(text[i])
                i += 1
        return "".join(out)

    def description(self, index):
        return self.expand(self.huffman(self.entry(index)[1])[0])

    # ------------------------------------------------------------------ export and checks

    def records(self):
        for index in range(1, self.count):
            row = {"index": index, **self.properties(index), "passcode": self.passes[index],
                   "genre": f"{self.genre_mask(index):#014x}", "genres": "; ".join(self.genres(index)),
                   "name": self.name(index), "description": self.description(index)}
            yield row

    def check(self):
        """Structural checks over every record; returns a list of problems."""
        problems = []
        for index in range(1, self.count):
            card_id = self.properties(index)["id"]
            if self.index_of(card_id) != index:
                problems.append(f"index {index}: CARD_IntID does not map id {card_id} back")
            text, end = self.huffman(self.entry(index)[1])
            if end > self.entry(index + 1)[1]:
                problems.append(f"index {index}: description runs past the next one")
            try:
                self.expand(text)
            except (ValueError, IndexError, struct.error) as error:
                problems.append(f"index {index}: {error}")
        # The sentinel entry holds the name pool size and the exact bit length of the description
        # stream, which is padded to a whole byte.
        last_name, last_desc = self.entry(self.count)
        if last_name != len(self.names) or not 8 * (len(self.desc) - 1) < last_desc <= 8 * len(self.desc):
            problems.append("sentinel index entry does not mark the end of CARD_Name/CARD_Desc")
        problems += self.check_sorting()
        return problems

    def check_sorting(self):
        """CARD_Sort must equal the collation rule; each CARD_Top letter must point to the first card
        whose sort key starts with that letter, and '*' to the first card of the whole list."""
        stored = self.sort_positions()
        if stored is None:
            return []
        problems = []
        computed = self.collated_positions()
        wrong = [index for index in range(1, self.count) if stored[index] != computed[index]]
        if wrong:
            problems.append(f"CARD_Sort differs from the collation rule at {len(wrong)} records, "
                            f"first {wrong[0]} ({self.name(wrong[0])!r})")
        order = sorted(range(1, self.count), key=lambda index: stored[index])
        for char, card_id in self.top_entries():
            if char == "*":
                expected = order[0]
            else:
                expected = next((index for index in order
                                 if collation_key(self.name(index))[:1] == ((2, char.lower()),)), None)
            if self.index_of(card_id) != expected:
                problems.append(f"CARD_Top {char!r} points to id {card_id}, not to the first card of its letter")
        return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description="Decode the card database of cardinfo_<lang>.ehp.")
    parser.add_argument("archive", type=Path, help="duelsys/cardinfo_<lang>.ehp")
    parser.add_argument("--format", choices=("csv", "json"), default="csv")
    parser.add_argument("-o", "--output", type=Path, help="write here instead of stdout (keep it out of git)")
    parser.add_argument("--check", action="store_true", help="only run the structural checks")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    language = args.archive.stem.rsplit("_", 1)[-1]
    if language not in LANG_SUFFIX:
        parser.error(f"cannot tell the language from {args.archive.name}")
    info = CardInfo(args.archive.read_bytes(), LANG_SUFFIX[language])
    if args.check:
        problems = info.check()
        print("\n".join(problems[:20]) if problems else f"ok: {info.count - 1} cards")
        return 1 if problems else 0
    rows = list(info.records())
    out = open(args.output, "w", encoding="utf-8", newline="") if args.output else sys.stdout
    try:
        if args.format == "json":
            json.dump(rows, out, ensure_ascii=False, indent=1)
        else:
            writer = csv.DictWriter(out, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    finally:
        if args.output:
            out.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
