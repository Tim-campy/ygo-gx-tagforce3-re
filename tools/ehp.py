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


def is_archive(data):
    return data[:4] == MAGIC and data[8:12] == TAG


def embedded_archives(elf):
    """Yield (file offset, bytes) for every EHP archive embedded in an ELF image (BOOT.BIN, modules).
    Archives nested inside a found archive are not reported again (walk_blob reaches them as members)."""
    pos = elf.find(MAGIC)
    while pos >= 0:
        step = 4
        if elf[pos + 8:pos + 12] == TAG:
            size = struct.unpack_from("<I", elf, pos + 4)[0]
            if 0 < size and pos + size <= len(elf):
                yield pos, elf[pos:pos + size]
                step = size
        pos = elf.find(MAGIC, pos + step)


def is_elf(data):
    return data[:4] == b"\x7fELF"


def elf_module_offset(elf, file_offset):
    """Module-relative address of a file offset, from the PT_LOAD segment that holds it (BOOT.BIN and the
    gmodules have one segment at p_vaddr 0, so this is file offset - p_offset); None if no segment does."""
    phoff, = struct.unpack_from("<I", elf, 0x1C)
    entsize, count = struct.unpack_from("<HH", elf, 0x2A)
    for k in range(count):
        p_type, p_offset, p_vaddr, _, p_filesz = struct.unpack_from("<5I", elf, phoff + k * entsize)
        if p_type == 1 and p_offset <= file_offset < p_offset + p_filesz:
            return file_offset - p_offset + p_vaddr
    return None


def embedded_report(elf):
    """[(file offset, module offset, archive bytes, members)] for every archive embedded in an ELF."""
    return [(offset, elf_module_offset(elf, offset), archive, parse(archive))
            for offset, archive in embedded_archives(elf)]


def walk_blob(label, data):
    """Yield (label, bytes) for every leaf file of `data`: archive members recursively (`.gz` members
    decompressed, names without `.gz`), archives embedded in an ELF (`label@0xOFFSET/...`), or `data` itself.
    Member labels are `label/member` (nested: `label/inner.ehp/member`)."""
    if data[:4] == b"\x7fELF":
        found = False
        for offset, archive in embedded_archives(data):
            found = True
            yield from walk_blob(f"{label}@{offset:#x}", archive)
        if not found:
            yield label, data
    elif is_archive(data):
        for name, blob in parse(data):
            name, blob = unwrap(name, blob)
            yield from walk_blob(f"{label}/{name}", blob)
    else:
        yield label, data


def read_file(path):
    """File bytes, gunzipped when the file is gzip-wrapped (field/bustup/*.ehp.gz)."""
    data = Path(path).read_bytes()
    if data[:2] == b"\x1f\x8b":
        try:
            return gzip.decompress(data)
        except (OSError, EOFError):
            pass
    return data


def walk_paths(paths):
    """walk_blob() over files and directories (walked recursively, labels relative to the directory)."""
    for path in map(Path, paths):
        if path.is_dir():
            for sub in sorted(p for p in path.rglob("*") if p.is_file()):
                yield from walk_blob(sub.relative_to(path).as_posix(), read_file(sub))
        else:
            yield from walk_blob(path.name, read_file(path))


def find_leaf(path, member, accept=lambda blob: True):
    """Return (label, bytes) of the first leaf of `path` whose label ends with `/member` (case-insensitive;
    `member` may name nested archives, `inner.ehp/x.gim`, with `/` or `:` as separator)."""
    want = "/" + member.replace(":", "/").lower()
    for label, blob in walk_blob(Path(path).name, read_file(path)):
        if label.lower().endswith(want) and accept(blob):
            return label, blob
    raise KeyError(f"{member} not found in {path}")


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


def handle_elf(path, data, args):
    """List, extract, verify or check the archives embedded in an ELF image; returns the failure count."""
    found = embedded_report(data)
    if not found:
        print(f"error: {path}: no embedded EHP archive", file=sys.stderr)
        return 1
    failures = 0
    rebuilt = [build(members) == archive for _, _, archive, members in found]
    if args.check:
        failures = rebuilt.count(False)
        if failures:
            for (offset, _, _, _), same in zip(found, rebuilt):
                if not same:
                    print(f"DIFF {path}@{offset:#x}")
        else:
            print(f"ok: {path.name}: {len(found)} embedded archives, {sum(len(m) for *_, m in found)} members, "
                  f"all rebuild byte for byte")
        return failures
    for (offset, module, archive, members), same in zip(found, rebuilt):
        where = f"{path}@{offset:#x}"
        if module is not None:
            where += f" (+{module:#x}" + (f", {args.base + module:#010x})" if args.base else ")")
        if args.verify:
            failures += not same
            print(f"{'ok  ' if same else 'DIFF'} {where}")
        elif args.extract:
            count = extract(members, args.extract / f"{path.name}@{offset:#x}.d", args.recursive, args.gunzip)
            print(f"{where}: {count} files")
        else:
            print(f"{where}: {len(archive)} bytes, {len(members)} members")
            for name, blob in members:
                print(f"  {len(blob):>10}  {blob[:4].hex()}  {name}")
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description="List, extract or verify EHP archives.")
    parser.add_argument("archives", type=Path, nargs="+",
                        help=".ehp files (a .gz-wrapped EHP is accepted), or ELF images (BOOT.BIN, gmodule/*.prx) "
                             "whose embedded archives are handled one by one")
    parser.add_argument("-x", "--extract", type=Path, metavar="DIR",
                        help="extract each archive into DIR/<name>.d (embedded: DIR/<elf>@0x<offset>.d)")
    parser.add_argument("-r", "--recursive", action="store_true", help="also unpack nested EHP members")
    parser.add_argument("-z", "--gunzip", action="store_true", help="decompress .gz members while extracting")
    parser.add_argument("--verify", action="store_true", help="rebuild each archive and compare it byte for byte")
    parser.add_argument("--check", action="store_true", help="like --verify, one summary line per file")
    parser.add_argument("--base", type=lambda text: int(text, 16), default=0,
                        help="runtime base of an ELF input, hex, to print archive addresses (BOOT.BIN: 08804000)")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    failures = 0
    for path in args.archives:
        try:
            data = path.read_bytes()
            if data[:2] == b"\x1f\x8b":
                data = gzip.decompress(data)
            if is_elf(data):
                failures += handle_elf(path, data, args)
                continue
            members = parse(data)
            if args.check:
                same = build(members) == data
                failures += not same
                print(f"ok: {path.name}: {len(members)} members, rebuilds byte for byte" if same else f"DIFF {path}")
            elif args.verify:
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
