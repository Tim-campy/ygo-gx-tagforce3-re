# Progress measurement

`tools/progress.py` turns two CSV registries into numbers, an SVG treemap, an HTML page and badges, so you can see how much of the game has been reverse engineered.

## Origin and licence

The snapshot format, the base/head comparison and the treemap and badge rendering are adapted from `tools/progress.py` of [AnyPS5](https://github.com/boykopovar/AnyPS5), which is GPL-2.0. AnyPS5's script counts implemented system-library functions and shader opcodes by scanning its own C++ tree, so it cannot be reused as-is for a decompilation project. This version keeps the useful parts and replaces the measurement: instead of scanning source, it reads `re/functions.csv` and `re/formats.csv`. The files under `tools/` therefore stay under GPL-2.0-only (see the SPDX header), and the repository as a whole is GPL-2.0-only (`LICENSE`).

## Registries

`re/functions.csv` and `re/formats.csv` share the same columns:

| Column | Meaning |
| --- | --- |
| `id` | Functions: hex address (`0x08804000`). Formats: a short stable key. Must be unique (case-insensitive). |
| `name` | Current name in Ghidra, or the format's name. |
| `group` | Subsystem (`container`, `card_db`, `duel_core`, ...). Blank becomes `unassigned`. |
| `status` | `unknown`, `named`, `documented`, `reimplemented` or `verified`. Blank is inferred. |
| `size` | Optional, bytes, decimal or `0x` hex. Enables the byte-weighted percentage. |

Lines starting with `#` and blank lines are ignored. A missing file counts as an empty registry.

### Stages

| Stage | Functions | Formats and structures |
| --- | --- | --- |
| `unknown` | Tool default name (`FUN_…`, `sub_…`), not analysed. | Seen but not identified. |
| `named` | Meaningful name backed by evidence. | Located and named. |
| `documented` | Signature, purpose, side effects and callers recorded in Ghidra and `docs/`. | Layout written down in `docs/formats/`. |
| `reimplemented` | A clean reimplementation exists. | A parser or extractor handles it. |
| `verified` | Checked against the original's behaviour in PPSSPP. | Round-trips or matches the original on real data. |

When `status` is blank, a function whose name matches a tool default is `unknown` and anything else is `named`. This is the only automatic inference; every higher stage must be set by hand.

### Counting rules

- A function or format is **done** when its stage is at or above `--stage` (default `documented`).
- The headline percentage counts entries. When sizes are present, a second figure weights by bytes, because a handful of large functions can hide most of the code.
- `reached` lists the cumulative percentage at every stage from `named` upward.
- The total only includes entries already in the registries, not every function in the binary. Import the full function list from Ghidra early so the denominator is honest, and re-import when analysis discovers more.

## Commands

```
python3 -I tools/progress.py --check
python3 -I tools/progress.py
python3 -I tools/progress.py build/progress --log
python3 -I tools/progress.py --stage named --group card_db
python3 -I tools/progress.py --json
python3 -I tools/progress.py --compare old/progress.json new/progress.json
python3 -I tools/tests/test_progress.py
```

- With an output directory, it writes `progress.json`, `progress.svg`, `progress.html`, `badge-functions.svg` and `badge-formats.svg`.
- `--log` keeps one row per UTC day in `re/progress-log.csv` (replacing the same day's row), which you can chart over time. It records whole-project numbers and does not combine with `--group`.
- `--compare` prints a markdown report (advanced, added, regressed, removed). Both files must use the same `--stage`.
- `--group` limits function counts to the named groups; format counts stay complete.

## Filling the registry from Ghidra

Export the function list (address, name, size) from Ghidra, or ask the agent to produce it through REA, and turn it into `re/functions.csv`. Names that still look like `FUN_08804000` start as `unknown`. From then on, update the rows as part of the same work that renames or documents each function.

In this project the registry is regenerated from Ghidra rather than edited by hand:

- `re/names.csv` and `re/names-ppsspp.csv` name functions (`tools/ghidra/ApplyNames.java`).
- `re/documented.tsv` lists the functions that meet the `documented` stage: prototype, a summary of purpose and side effects, and the document that records them and their callers. `tools/ghidra/ApplySignatures.java` applies the prototype and a plate comment and tags the function `DOCUMENTED`.
- `tools/ghidra/ExportFunctions.java` writes `re/functions.csv`, setting `status` to `documented` only for tagged functions.

A function therefore reaches `documented` only when Ghidra holds its signature and comment, as the stage definition requires.

Function ids are runtime addresses. Game modules that the game loads into a shared slot (for example `rel_story`, `rel_field` and `rel_shop`, see `docs/subsystems/modules.md`) can have functions at the same address, so their ids carry the module name: `rel_story:0x08ea63f4`.

## Reaching `verified`

`verified` needs a runtime check in PPSSPP. [`docs/verification/ppsspp-plan.md`](verification/ppsspp-plan.md) lists the checks that matter most for the port. They are grouped into play sessions (one single duel, one tag duel, one in-game day of free roam), and each has its addresses, breakpoints, expected values and a results table. The plan also explains how a filled-in results table turns into status changes. It does not change the counting rules above.
