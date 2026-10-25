#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""List and extract files from an ISO 9660 image such as a PSP UMD dump.

Only what a UMD image needs is supported: 2048-byte sectors, the primary volume
descriptor and single-extent files. Names are decoded as cp932 (Shift-JIS):
some Konami discs carry Japanese file names. See docs/formats/disc-layout.md.
"""

import argparse
import struct
import sys
from pathlib import Path

SECTOR = 2048
PVD_SECTOR = 16
ROOT_RECORD = 156  # offset of the root directory record inside the PVD
FLAG_DIRECTORY = 0x02


class Entry:
    __slots__ = ("path", "lba", "size", "is_dir")

    def __init__(self, path, lba, size, is_dir):
        self.path, self.lba, self.size, self.is_dir = path, lba, size, is_dir


def parse_record(record):
    """Return (name, lba, size, is_dir) for one directory record, or None for '.' and '..'."""
    lba = struct.unpack_from("<I", record, 2)[0]
    size = struct.unpack_from("<I", record, 10)[0]
    name = record[33:33 + record[32]]
    if name in (b"\x00", b"\x01"):
        return None
    return name.decode("cp932").split(";")[0], lba, size, bool(record[25] & FLAG_DIRECTORY)


class Image:
    def __init__(self, path):
        self.file = open(path, "rb")
        pvd = self.read(PVD_SECTOR, SECTOR)
        if pvd[0] != 1 or pvd[1:6] != b"CD001":
            self.close()
            raise ValueError(f"{path}: no ISO 9660 primary volume descriptor at sector {PVD_SECTOR}")
        self.root_lba = struct.unpack_from("<I", pvd, ROOT_RECORD + 2)[0]
        self.root_size = struct.unpack_from("<I", pvd, ROOT_RECORD + 10)[0]

    def close(self):
        self.file.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def read(self, lba, size, offset=0):
        self.file.seek(lba * SECTOR + offset)
        return self.file.read(size)

    def children(self, lba, size):
        data = self.read(lba, size)
        position = 0
        while position < len(data):
            length = data[position]
            if length == 0:  # records never cross a sector boundary; skip the padding
                position = (position // SECTOR + 1) * SECTOR
                continue
            parsed = parse_record(data[position:position + length])
            if parsed:
                yield parsed
            position += length

    def walk(self, lba=None, size=None, prefix=""):
        """Yield every Entry below a directory, depth first, in on-disc order."""
        for name, child_lba, child_size, is_dir in self.children(lba or self.root_lba, size or self.root_size):
            path = f"{prefix}{name}"
            yield Entry(path, child_lba, child_size, is_dir)
            if is_dir:
                yield from self.walk(child_lba, child_size, path + "/")

    def extract(self, entry, target, chunk=1 << 20):
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "wb") as out:
            done = 0
            while done < entry.size:
                block = self.read(entry.lba, min(chunk, entry.size - done), done)
                if not block:
                    raise ValueError(f"{entry.path}: image ends before the file does")
                out.write(block)
                done += len(block)


def selected(entries, prefixes):
    if not prefixes:
        return entries
    wanted = [p.strip("/").upper() for p in prefixes]
    return [e for e in entries if any(e.path.upper() == p or e.path.upper().startswith(p + "/") for p in wanted)]


def main(argv=None):
    parser = argparse.ArgumentParser(description="List or extract files from an ISO 9660 (UMD) image.")
    parser.add_argument("image", type=Path)
    parser.add_argument("paths", nargs="*", help="limit to these files or directories (case-insensitive)")
    parser.add_argument("-x", "--extract", type=Path, metavar="DIR", help="extract into DIR instead of listing")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):  # Japanese names must survive a cp1252 console
        sys.stdout.reconfigure(encoding="utf-8")

    try:
        with Image(args.image) as image:
            entries = selected(list(image.walk()), args.paths)
            if args.paths and not entries:
                parser.error("no entry matches " + ", ".join(args.paths))
            for entry in entries:
                if args.extract:
                    if not entry.is_dir:
                        image.extract(entry, args.extract.joinpath(*entry.path.split("/")))
                else:
                    kind = "dir " if entry.is_dir else "file"
                    print(f"{kind} {entry.lba:#010x} {entry.size:>10} {entry.path}")
            if args.extract:
                count = sum(1 for e in entries if not e.is_dir)
                print(f"extracted {count} files into {args.extract}")
    except (OSError, ValueError, UnicodeDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
