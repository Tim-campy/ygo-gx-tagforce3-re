#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Documentation-quality audit: seeded stratified sample of documented functions and the rate statistics.

docs/verification/documentation-quality-audit.md explains the method. The instruction-level scans are in
tools/doc_audit_scan.py. Nothing here reads game data; `sample` only needs the registries.

    doc_audit.py population                 # stratum sizes
    doc_audit.py sample -o sample.csv       # draw the sample (seed recorded in the file)
    doc_audit.py stats sample.csv verdicts.csv
"""
import argparse
import csv
import glob
import math
import os
import random
import re
import subprocess
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = 20261104
ROUND6_BASELINE = "5436e3a"  # commit that documented the 28 modules imported in round 6
EARLY_PROGRAMS = {"BOOT.BIN", "rel_duel_eng.prx", "rel_duel_draw.prx", "rel_duel_mgr.prx", "rel_story.prx",
                  "rel_field.prx", "rel_shop.prx", "rel_deck.prx", "rel_title.prx"}
# (stratum, groups, sample size); the last stratum is the round-6 rows, selected by program and not by group.
STRATA = [
    ("duel_core", {"duel_core"}, 80),
    ("duel_effects", {"duel_effects"}, 80),
    ("ai", {"ai"}, 50),
    ("tag_save_card_deck", {"tag_duel", "save", "card_db", "deck"}, 40),
    ("world_dialogue_shop", {"world", "dialogue", "shop"}, 40),
    ("ui_field3d", {"ui", "field_3d"}, 50),
    ("audio_system", {"audio", "system"}, 30),
    ("round6_high", None, 30),
]
BANDS = [("tiny", 0, 32), ("small", 33, 128), ("medium", 129, 512), ("large", 513, 2048), ("huge", 2049, 1 << 40)]
HEDGE = re.compile(r"hypothes|confidence|medium\b|probably|likely|\bunclear\b|unknown purpose", re.I)


def tsv_program(path):
    """Program name and registry prefix of a documented*.tsv file."""
    base = os.path.basename(path)[len("documented"):-len(".tsv")].lstrip("-")
    if base == "":
        return "BOOT.BIN", ""
    if base == "duel_eng":
        return "rel_duel_eng.prx", ""
    if base == "rel_duel_draw":
        return "rel_duel_draw.prx", ""
    return base + ".prx", base + ":"


def read_tsv(text):
    """(address, prototype, summary, document) rows of a documented*.tsv text."""
    for line in text.splitlines():
        if not line.strip() or line.startswith("#") or line.startswith("address\t"):
            continue
        parts = line.split("\t")
        if len(parts) == 4:
            yield parts


def load_documented(root=ROOT):
    """{registry id: dict(program, addr, proto, summary, doc, file)} for every documented row."""
    rows = {}
    for path in sorted(glob.glob(os.path.join(root, "re", "documented*.tsv"))):
        program, prefix = tsv_program(path)
        with open(path, encoding="utf-8") as handle:
            for addr, proto, summary, doc in read_tsv(handle.read()):
                rid = prefix + addr
                rows[rid] = dict(id=rid, program=program, addr=addr, proto=proto, summary=summary, doc=doc,
                                 file=os.path.basename(path))
    return rows


def load_registry(root=ROOT):
    with open(os.path.join(root, "re", "functions.csv"), encoding="utf-8") as handle:
        return {r["id"]: r for r in csv.DictReader(line for line in handle if not line.startswith("#"))}


def baseline_rows(commit, file, root=ROOT):
    out = subprocess.run(["git", "-C", root, "show", f"{commit}:re/{file}"], capture_output=True)
    if out.returncode:
        return {}
    return {r[0]: r for r in read_tsv(out.stdout.decode("utf-8"))}


def is_stub(row, registry_row):
    return registry_row["name"].startswith("thunk_") or row["proto"].split("(")[0].split()[-1].lstrip("*").startswith("thunk_")


def population(root=ROOT):
    """{stratum: [row]} of the documented, non-stub rows. Rows of the 28 round-6 modules are only eligible for
    the round-6 stratum, and only if the audit of 2026-11-04 left them as they were and they carry no hedge."""
    documented, registry = load_documented(root), load_registry(root)
    strata = {name: [] for name, _, _ in STRATA}
    by_group = {g: name for name, groups, _ in STRATA if groups for g in groups}
    base_cache, skipped = {}, Counter()
    for rid, row in documented.items():
        reg = registry.get(rid)
        if reg is None or reg["status"] not in ("documented", "verified") or is_stub(row, reg):
            skipped["stub or not in the registry"] += 1
            continue
        item = dict(row, name=reg["name"], group=reg["group"], size=int(reg["size"] or 0, 0) if reg["size"] else 0)
        if row["program"] in EARLY_PROGRAMS:
            if reg["group"] in by_group:
                strata[by_group[reg["group"]]].append(item)
            else:
                skipped["other group " + reg["group"]] += 1
            continue
        if row["file"] not in base_cache:
            base_cache[row["file"]] = baseline_rows(ROUND6_BASELINE, row["file"], root)
        old = base_cache[row["file"]].get(row["addr"])
        if old and old[1] == row["proto"] and old[2] == row["summary"] and not HEDGE.search(row["summary"]):
            strata["round6_high"].append(item)
        else:
            skipped["round 6, audited or hedged"] += 1
    return strata, skipped


def band_of(size):
    return next(name for name, low, high in BANDS if low <= size <= high)


def allocate(rows, total):
    """Sample size per size band: proportional to the sum of sqrt(size) in the band (a lean towards large
    functions), at least 2 per band that has 2 rows, never more than the band holds."""
    groups = defaultdict(list)
    for row in rows:
        groups[band_of(row["size"])].append(row)
    weights = {b: sum(math.sqrt(max(r["size"], 4)) for r in g) for b, g in groups.items()}
    whole = sum(weights.values())
    alloc = {b: min(len(g), max(2, round(total * weights[b] / whole))) for b, g in groups.items()}
    while sum(alloc.values()) != total:
        step = 1 if sum(alloc.values()) < total else -1
        order = sorted(groups, key=lambda b: alloc[b] / weights[b], reverse=step < 0)
        for b in order:
            if (step > 0 and alloc[b] < len(groups[b])) or (step < 0 and alloc[b] > 2):
                alloc[b] += step
                break
        else:
            break
    return groups, alloc


def draw(strata, seed=SEED):
    """The seeded sample: one rng per stratum, so a change in one stratum cannot move another's rows."""
    picked = []
    for name, _, total in STRATA:
        rng = random.Random(f"{seed}:{name}")
        groups, alloc = allocate(strata[name], total)
        for band, _, _ in BANDS:
            rows = sorted(groups.get(band, []), key=lambda r: r["id"])
            for row in sorted(rng.sample(rows, alloc[band]) if rows else [], key=lambda r: r["id"]):
                picked.append(dict(stratum=name, band=band, band_population=len(rows), band_sample=alloc[band],
                                   id=row["id"], name=row["name"], group=row["group"], size=row["size"]))
    return picked


SAMPLE_FIELDS = ["stratum", "band", "band_population", "band_sample", "id", "name", "group", "size"]


def wilson(x, n, z=1.96):
    """95% Wilson interval of a proportion."""
    if n <= 0:
        return 0.0, 1.0
    p = x / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def weighted_rate(rows, hit):
    """Population-weighted estimate (each row counts for band_population / band_sample rows) and a Wilson
    interval on the Kish effective sample size."""
    weights = [int(r["band_population"]) / int(r["band_sample"]) for r in rows]
    if not weights:
        return 0.0, 0.0, 1.0, 0.0
    total = sum(weights)
    p = sum(w for w, r in zip(weights, rows) if hit(r)) / total
    n_eff = total * total / sum(w * w for w in weights)
    low, high = wilson(p * n_eff, n_eff)
    return p, low, high, n_eff


def stats(sample_path, verdict_path):
    """Rates per stratum from sample.csv and verdicts.csv (id, verdict, port_impact, ...)."""
    with open(verdict_path, encoding="utf-8") as handle:
        verdicts = {r["id"]: r for r in csv.DictReader(handle)}
    with open(sample_path, encoding="utf-8") as handle:
        rows = [r for r in csv.DictReader(line for line in handle if not line.startswith("#"))]
    missing = [r["id"] for r in rows if r["id"] not in verdicts]
    if missing:
        print(f"warning: {len(missing)} rows without a verdict", file=sys.stderr)
    for row in rows:
        row.update(verdicts.get(row["id"], {}))
    tests = [("any error", lambda r: r.get("verdict") in ("minor", "material", "name")),
             ("material or name", lambda r: r.get("verdict") in ("material", "name")),
             ("port-affecting", lambda r: r.get("port_impact") == "yes")]
    out = []
    for name in [s[0] for s in STRATA] + ["ALL"]:
        part = [r for r in rows if name == "ALL" or r["stratum"] == name]
        cells = {"stratum": name, "n": len(part), "population": sum(
            int(v) for v in {(r["stratum"], r["band"]): r["band_population"] for r in part}.values())}
        cells.update(Counter(r.get("verdict", "?") for r in part))
        for label, test in tests:
            x = sum(1 for r in part if test(r))
            low, high = wilson(x, len(part))
            cells[label] = f"{x}/{len(part)} = {100 * x / max(len(part), 1):.1f}% [{100 * low:.1f}, {100 * high:.1f}]"
            if name == "ALL":
                # Strata have different sampling fractions, so every row weighs band_population / band_sample.
                pass
            p, wl, wh, n_eff = weighted_rate(part, test)
            cells[label + " (weighted)"] = f"{100 * p:.1f}% [{100 * wl:.1f}, {100 * wh:.1f}] n_eff {n_eff:.0f}"
        out.append(cells)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["population", "sample", "stats"])
    parser.add_argument("files", nargs="*")
    parser.add_argument("-o", "--output")
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args(argv)
    if args.command == "stats":
        for cells in stats(args.files[0], args.files[1]):
            print(cells)
        return 0
    strata, skipped = population()
    if args.command == "population":
        for name, rows in strata.items():
            bands = Counter(band_of(r["size"]) for r in rows)
            print(f"{name:22s} {len(rows):6d}  " + " ".join(f"{b}={bands[b]}" for b, _, _ in BANDS))
        print(dict(skipped))
        return 0
    picked = draw(strata, args.seed)
    with open(args.output, "w", encoding="utf-8", newline="") as handle:
        handle.write(f"# seed {args.seed}; see docs/verification/documentation-quality-audit.md\n")
        writer = csv.DictWriter(handle, fieldnames=SAMPLE_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(picked)
    print(f"{len(picked)} rows written to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
