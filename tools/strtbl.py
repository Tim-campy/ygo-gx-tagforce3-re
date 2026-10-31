#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read the UI/system string tables (strTbl*.bin, *_strtbl*.bin, *_msg_<l>.bin, pack_*_str_<l>.bin, ...).
See docs/formats/string-tables.md.

  strtbl.py show  <file> [member] [-o out.tsv]    one table: index<TAB>string (escapes \\n, \\t, \\\\)
  strtbl.py dump  <files or dirs…> -o DIR          every table found, one JSON file per table
  strtbl.py check <files or dirs…>                 parse every .bin member, count tables per layout and family

<file> is an .ehp (an .ehp.gz is accepted), a loose .bin or an ELF such as BOOT.BIN (embedded archives are
searched). Dumps are game text: write them outside the repository or under extracted/, never into git.
"""

import argparse
import importlib.util
import json
import re
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent


def _load(name):
    spec = importlib.util.spec_from_file_location(f"re_{name}", TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ehp = _load("ehp")

HEADED = "strtbl"  # u32 count, u32 table offset (12), u32 string base, count x u32 offsets from the base
LISTED = "offset_list"  # u32 string base (= 4 + 4 * count), count x u32 offsets from the base
# .bin families that hold text in another layout, and the document that describes them.
OTHER_LAYOUTS = {
    "CARD_Name": "cardinfo.md", "CARD_Desc": "cardinfo.md", "DLG_Text": "cardinfo.md", "DLG_Indx": "cardinfo.md",
    "CARD_Indx": "cardinfo.md", "CARD_Huff": "cardinfo.md", "EveI": "story.md", "EveL": "story.md",
    "SysMsgI": "story.md", "SysMsgL": "story.md", "tuto_text": "tutorial.md",
}
TEXT_HINT = re.compile(r"str|msg|tbl|name|text|word|explain|result|dict", re.I)


class TableError(ValueError):
    pass


def _strings(blob, base, offsets):
    """Decode the strings; returns (strings, has_end_offset, contiguous)."""
    end = len(blob) - base
    has_end = len(offsets) > 0 and offsets[-1] == end
    entries = offsets[:-1] if has_end else offsets
    strings, contiguous = [], True
    for index, offset in enumerate(entries):
        start = base + offset
        stop = start
        while stop + 1 < len(blob) and blob[stop:stop + 2] != b"\0\0":
            stop += 2
        if stop + 1 >= len(blob):
            raise TableError(f"string {index} is not NUL-terminated")
        try:
            strings.append(blob[start:stop].decode("utf-16-le"))
        except UnicodeDecodeError as error:
            raise TableError(f"string {index} is not UTF-16LE: {error}") from None
        following = base + (offsets[index + 1] if index + 1 < len(offsets) else end)
        contiguous = contiguous and stop + 2 == following
    return strings, has_end, contiguous


def parse(blob):
    """Parse a string table. Returns a dict: layout, base, offsets (as stored), strings (without the end
    offset), has_end_offset, contiguous. Raises TableError when the bytes are not a string table."""
    if len(blob) < 8:
        raise TableError("too short")
    first, second = struct.unpack_from("<II", blob, 0)
    if second == 12 and len(blob) >= 12:
        layout, count, base, table = HEADED, first, struct.unpack_from("<I", blob, 8)[0], 12
    elif second == 0 and first % 4 == 0 and first >= 8:
        layout, count, base, table = LISTED, first // 4 - 1, first, 4
    else:
        raise TableError("no string-table header")
    if count == 0 or table + 4 * count > len(blob) or not table + 4 * count <= base <= len(blob) or base % 2:
        raise TableError(f"inconsistent header (count {count}, base {base:#x}, size {len(blob):#x})")
    offsets = list(struct.unpack_from(f"<{count}I", blob, table))
    if offsets != sorted(offsets) or offsets[-1] > len(blob) - base or any(o % 2 for o in offsets):
        raise TableError("offsets are not ascending even values inside the file")
    strings, has_end, contiguous = _strings(blob, base, offsets)
    return {"layout": layout, "base": base, "offsets": offsets, "strings": strings,
            "has_end_offset": has_end, "contiguous": contiguous}


def build(strings, layout=HEADED, end_offset=True):
    """Inverse of parse() for contiguous tables (used by the tests; the disc tables rebuild byte for byte)."""
    body, offsets = bytearray(), []
    for text in strings:
        offsets.append(len(body))
        body += text.encode("utf-16-le") + b"\0\0"
    if end_offset:
        offsets.append(len(body))
    if layout == HEADED:
        base = 12 + 4 * len(offsets)
        head = struct.pack("<3I", len(offsets), 12, base)
    else:
        base = 4 + 4 * len(offsets)
        head = struct.pack("<I", base)
    return head + struct.pack(f"<{len(offsets)}I", *offsets) + bytes(body)


def family(label):
    """Member name with digits and the language suffix normalised: `chrzakov003_wordstbl_e.bin` ->
    `chrzakovN_wordstbl_<l>.bin`."""
    name = label.replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"_(e|f|g|i|j|s|eng|fra|ger|ita|spa|jpn)(?=\.bin$)", "_<l>", name, flags=re.I)
    name = re.sub(r"(?<=SysMsg[IL])[efgijs](?=\.bin$)", "<l>", name)
    return re.sub(r"\d+", "N", name)


def other_layout(name):
    for prefix, doc in OTHER_LAYOUTS.items():
        if name.startswith(prefix):
            return doc
    return None


def bins(paths):
    for label, blob in ehp.walk_paths(paths):
        if label.lower().endswith(".bin"):
            yield label, blob


def output_allowed(path):
    resolved = Path(path).resolve()
    if "extracted" in (part.lower() for part in resolved.parts):
        return True
    try:
        resolved.relative_to(REPO.resolve())
    except ValueError:
        return True
    return False


def escape(text):
    return text.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")


def cmd_show(args):
    if args.member is None:
        label, blob = str(args.file), ehp.read_file(args.file)
    else:
        label, blob = ehp.find_leaf(args.file, args.member)
    table = parse(blob)
    lines = [f"{index}\t{escape(text)}" for index, text in enumerate(table["strings"])]
    if args.output:
        if not output_allowed(args.output):
            print("error: write game text outside the repository or under extracted/", file=sys.stderr)
            return 1
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {args.output}: {len(lines)} strings ({table['layout']})")
    else:
        print("\n".join(lines))
    return 0


def cmd_dump(args):
    if not output_allowed(args.output):
        print("error: write game text outside the repository or under extracted/", file=sys.stderr)
        return 1
    written = 0
    for label, blob in bins(args.paths):
        try:
            table = parse(blob)
        except (TableError, struct.error):
            continue
        parts = [p.replace(":", "_").replace("@", "_at_") for p in label.split("/") if p not in ("", ".", "..")]
        target = args.output.joinpath(*parts).with_suffix(".json")
        target.parent.mkdir(parents=True, exist_ok=True)
        record = {"source": label, "layout": table["layout"], "has_end_offset": table["has_end_offset"],
                  "strings": table["strings"]}
        target.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        written += 1
    print(f"wrote {written} tables to {args.output}")
    return 0


def cmd_check(args):
    layouts, families, unmatched, other = Counter(), defaultdict(list), Counter(), Counter()
    strings = failures = rebuilt = members = 0
    for label, blob in bins(args.paths):
        members += 1
        name = label.rsplit("/", 1)[-1]
        try:
            table = parse(blob)
        except (TableError, struct.error) as error:
            if TEXT_HINT.search(name):
                doc = other_layout(name)
                if doc:
                    other[(family(label), doc)] += 1
                elif not name.lower().endswith("voiceidchgtbl.bin"):  # voice-id maps, not text (sound.md)
                    unmatched[(family(label), str(error))] += 1
            continue
        key = f"{table['layout']}, {'with' if table['has_end_offset'] else 'without'} end offset"
        layouts[key] += 1
        families[family(label)].append(len(table["strings"]))
        strings += len(table["strings"])
        if not table["contiguous"]:
            print(f"note {label}: strings are not packed back to back")
        same = build(table["strings"], table["layout"], table["has_end_offset"]) == blob
        rebuilt += same
        if args.verbose and not same:
            print(f"note {label}: does not rebuild byte for byte")
    print("tables by layout:")
    for key, value in sorted(layouts.items()):
        print(f"  {value:>6}  {key}")
    print("tables by family (files, strings min-max):")
    for key, counts in sorted(families.items(), key=lambda kv: kv[0].lower()):
        print(f"  {len(counts):>6}  {key}  {min(counts)}-{max(counts)}")
    if other:
        print("text members in another documented layout (not read by this tool):")
        for (key, doc), value in sorted(other.items()):
            print(f"  {value:>6}  {key}  ({doc})")
    for (key, reason), value in sorted(unmatched.items()):
        failures += value
        print(f"UNMATCHED {value} x {key}: {reason}")
    total = sum(layouts.values())
    print(f".bin files {members}: string tables {total} ({strings} strings, {rebuilt} rebuilt byte for byte), "
          f"text in other layouts {sum(other.values())}, other data {members - total - sum(other.values()) - failures}")
    print("OK" if not failures else f"{failures} text-like .bin members FAILED to parse")
    return 1 if failures else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read the game's UTF-16 string tables.")
    sub = parser.add_subparsers(dest="command", required=True)
    show = sub.add_parser("show", help="print one table")
    show.add_argument("file", type=Path)
    show.add_argument("member", nargs="?")
    show.add_argument("-o", "--output", type=Path)
    dump = sub.add_parser("dump", help="write every table as JSON")
    dump.add_argument("paths", type=Path, nargs="+")
    dump.add_argument("-o", "--output", type=Path, required=True)
    check = sub.add_parser("check", help="parse every .bin member and report counts")
    check.add_argument("paths", type=Path, nargs="+")
    check.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        return {"show": cmd_show, "dump": cmd_dump, "check": cmd_check}[args.command](args)
    except (OSError, TableError, KeyError, struct.error) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
