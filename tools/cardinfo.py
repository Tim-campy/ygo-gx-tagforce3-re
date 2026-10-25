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
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_ehp", Path(__file__).resolve().parent / "ehp.py")
ehp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ehp)

FIRST_ID = 0xE88  # card ids below this have no entry (CARD_IntID starts here)
LANG_SUFFIX = {"eng": "E", "fra": "F", "ger": "G", "ita": "I", "spa": "S"}


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
