#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""List, extract and rebuild EHP archives (magic "EHP\\x03"). See docs/formats/ehp.md."""

import argparse
import gzip
import struct
import sys
from pathlib import Path

MAGIC = b"EHP\x03"
TAG = b"NOT "
HEADER = struct.Struct("<4sI4sI")  # magic, total size, tag, member count
ENTRY = struct.Struct("<II")  # name offset, data offset
TABLE = HEADER.size  # the entry table follows the header
TABLE_PAD = 8  # zero bytes between the entry table and the name block
DATA_ALIGN = 16


def align(value, boundary=DATA_ALIGN):
    return (value + boundary - 1) // boundary * boundary


def parse(data):
    """Return [(name, bytes)] for an EHP archive, in on-disk order."""
    magic, total, tag, count = HEADER.unpack_from(data, 0)
    if magic != MAGIC or tag != TAG:
        raise ValueError("not an EHP archive")
    if total != len(data):
        raise ValueError(f"header size {total:#x} does not match file size {len(data):#x}")
    members = []
    for index in range(count):
        name_offset, data_offset = ENTRY.unpack_from(data, TABLE + ENTRY.size * index)
        end = data.index(b"\0", name_offset)
        size = struct.unpack_from("<I", data, end + 1)[0]
        if data_offset + size > len(data):
            raise ValueError(f"member {index} ends past the end of the archive")
        members.append((data[name_offset:end].decode("cp932"), data[data_offset:data_offset + size]))
    return members


def build(members):
    """Inverse of parse(): byte-identical to the game's archives (checked on the whole disc)."""
    names = bytearray()
    name_offsets = []
    base = TABLE + ENTRY.size * len(members) + TABLE_PAD
    for name, blob in members:
        name_offsets.append(base + len(names))
        names += name.encode("cp932") + b"\0" + struct.pack("<I", len(blob))
    body = bytearray()
    data_offsets = []
    position = align(base + len(names))
    for _, blob in members:
        data_offsets.append(position)
        body += bytes(position - (base + len(names)) - len(body)) + blob
        position = align(position + len(blob))
    total = align(base + len(names) + len(body))
    out = bytearray(HEADER.pack(MAGIC, total, TAG, len(members)))
    for pair in zip(name_offsets, data_offsets):
        out += ENTRY.pack(*pair)
    out += bytes(TABLE_PAD) + names + body
    return bytes(out.ljust(total, b"\0"))


def unwrap(name, blob):
    """Decompress a gzip member; returns (name, bytes) with '.gz' dropped."""
    if name.lower().endswith(".gz") and blob[:2] == b"\x1f\x8b":
        return name[:-3], gzip.decompress(blob)
    return name, blob


def extract(members, target, recursive, gunzip, depth=0):
    count = 0
    for name, blob in members:
        if gunzip:
            name, blob = unwrap(name, blob)
        path = target / name
        if recursive and blob[:4] == MAGIC:
            count += extract(parse(blob), path.with_name(path.name + ".d"), recursive, gunzip, depth + 1)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
        count += 1
    return count


def main(argv=None):
    parser = argparse.ArgumentParser(description="List, extract or verify EHP archives.")
    parser.add_argument("archives", type=Path, nargs="+", help=".ehp files (a .gz-wrapped EHP is accepted)")
    parser.add_argument("-x", "--extract", type=Path, metavar="DIR", help="extract each archive into DIR/<name>.d")
    parser.add_argument("-r", "--recursive", action="store_true", help="also unpack nested EHP members")
    parser.add_argument("-z", "--gunzip", action="store_true", help="decompress .gz members while extracting")
    parser.add_argument("--verify", action="store_true", help="rebuild each archive and compare it byte for byte")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    failures = 0
    for path in args.archives:
        try:
            data = path.read_bytes()
            if data[:2] == b"\x1f\x8b":
                data = gzip.decompress(data)
            members = parse(data)
            if args.verify:
                same = build(members) == data
                failures += not same
                print(f"{'ok  ' if same else 'DIFF'} {path}")
            elif args.extract:
                count = extract(members, args.extract / (path.name + ".d"), args.recursive, args.gunzip)
                print(f"{path}: {count} files")
            else:
                print(f"{path}: {len(members)} members")
                for name, blob in members:
                    print(f"  {len(blob):>10}  {blob[:4].hex()}  {name}")
        except (OSError, ValueError, EOFError, UnicodeDecodeError) as error:
            print(f"error: {path}: {error}", file=sys.stderr)
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
