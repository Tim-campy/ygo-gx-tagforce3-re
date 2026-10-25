# Story text and event bytecode (`script/story_scr_*.ehp`)

Status:
- Text tables: `verified`. `tools/story.py text` exports all five languages, and its 59,985 lines are identical to ygotfToolkit's dump (see "Cross-check").
- Bytecode container: `reimplemented`. Records, instruction size and the text references are checked on the whole file.
- Opcode meanings: hypotheses (see the opcode table).

Exports go under `extracted/` and are never committed.

## Files

`PSP_GAME/USRDIR/script/` holds six EHP archives (`ehp.md`):

| Archive | Members |
| --- | --- |
| `story_scr_<l>.ehp`, `<l>` ∈ `e f g i s` (English, French, German, Italian, Spanish) | `EveI<l>.bin`, `EveL<l>.bin`, `SysMsgI<l>.bin`, `SysMsgL<l>.bin` |
| `story_scr_b.ehp` (language-independent) | `EveB.bin` (390,950 bytes), `EveBI.bin` (29,872 bytes) |

`gmodule/rel_story.prx` builds these names. At file offset `0x1a880` it has the language letters `j e g f i s` as a `u32` table. At `0x1a8b0` it has the strings `script/story_scr_`, `b.ehp`, `.ehp`, `EveB.bin`, `EveBI.bin`, `EveL`, `EveI`, `SysMsgL`, `SysMsgI`, `.bin`. So the story module loads one text archive per language plus the shared bytecode. `j` (Japanese) has no archive on the European disc.

All integers are little-endian.

## Text tables: `<T>I<l>.bin` + `<T>L<l>.bin`

`T` is `Eve` (event dialogue) or `SysMsg` (21 system messages).

- **`I` (index)**: `u32` offsets in **UTF-16 code units** (not bytes) into the `L` member, one per line plus a final sentinel. The first offset is 0. The offsets are strictly ascending. The sentinel equals the length of `L` in code units.
- **`L` (text)**: UTF-16LE strings, each terminated by one NUL code unit. Line `n` occupies `[2·I[n], 2·I[n+1])` bytes, NUL included. No padding, and no other NUL inside a line.

Line `n` has the same meaning in every language (same counts; the event bytecode refers to lines by number, see below). Counts, identical in all five languages: `Eve` 11,976 lines (158 empty, 159 in Italian), `SysMsg` 21. That gives 11,997 per language and 59,985 in total. `Eve` text sizes range from 528,850 (English) to 558,904 (German) code units. The longest line is 194 code units (French), with up to 10 rows (Spanish).

### Markup kept in the text

`tools/story.py` keeps all markup as stored. In CSV it writes newline as `\n` and backslash as `\\`.

| Markup | Meaning | Per language (Eve) |
| --- | --- | --- |
| `U+000A` | Line break inside the text box. | — |
| `《PLAYER》`, `《PARTNER》`, `《TEAM》` | Placeholders for the player's name, the partner's name and (presumably) the tag team's name. The brackets are `U+300A`/`U+300B`. | about 740 / 26–44 / 3 |
| `《Cnnn_k》` | `nnn` is a three-digit character number (53 distinct in English, 001–151), `k` is 1–5. Hypothesis, medium: a character's name in one of several forms (for example given name, family name, nickname). The same numbers appear as speaker ids in the bytecode. | about 1,440 |
| `《M025_1》`, `《TEST》`, `《BREAD》` | Rare tokens (2, 1 and 2 uses). In the Spanish `SysMsg`, `《BREAD》` and `《PARTNER》` are translated (`《PAN》`, `《COMPAÑERO》`), so there the brackets may be literal text. | — |
| `$M` + 4 digits | A card name by card id (for example `$M4766`). These are the same ids as `CARD_Prop` (3720–7993; `cardinfo.md`). | 96 |
| `$C` + digit | Text colour; `$C0` resets. The same escape as the duel prompts in `cardinfo.md`. | 16–20 |

No `$R` (furigana) occurs in the European text.

## Event bytecode: `EveB.bin` + `EveBI.bin`

- **`EveB.bin`**: a flat array of 39,095 **instructions of 10 bytes**, each `u16 opcode` followed by four `u16` arguments `a1..a4`. The file size is an exact multiple of 10.
- **`EveBI.bin`**: 7,468 `u32` values. Each is the index (in instructions, not bytes) of the first instruction of one **record** (event script). They are strictly ascending and start at 0. There is no sentinel: the last record ends at the end of `EveB`.
- **Record shape**, checked on all 7,468 records:
  - The first instruction is opcode 1 (header) with `a4 = 0`.
  - The last instruction is all zero (end).
  - Neither opcode 1 nor opcode 0 occurs in between.
  - The header triple `(a1, a2, a3)` is unique per record: `a1` 1–501 (175 distinct values), `a2` 1–121, `a3` 1–51. Hypothesis, low: `a1` selects a character or place and `a3` numbers the events within it.
  - 3,394 records are empty (header and end only). The longest has 373 instructions.
- **Opcode numbering**: apart from 0 and 1, all 78 opcodes used lie between 50,001 and 50,176 (`0xC351`–`0xC400`), that is 50,000 + n.

### How the bytecode refers to text

Five opcodes carry an `Eve` line number in **`a4`**. Together they reference all 11,976 lines **exactly once**, and **in ascending order** through the file. So line `n` is the `n`-th text instruction of `EveB`. This holds for each of the five languages, because the line counts are equal. `SysMsg` is not referenced by the bytecode.

The names below are the ones `tools/story.py` prints. They are hypotheses based on argument patterns and on which lines each opcode picks (checked locally on the English text).

| Opcode | Count | `a1` | `a2` | `a3` | Hypothesis |
| --- | --- | --- | --- | --- | --- |
| 50001 `talk` | 9,234 | speaker, 2–141 | 0–16 | 0/1 | A character speaks a line; `a2` is probably the portrait or expression. Medium. |
| 50002 `talk_alt` | 1,324 | speaker | 0–16 | 0/1 | Same arguments as 50001, but a different presentation (for example the other box position, or a thought). Low. |
| 50008 `narrate` | 651 | 0 | 0 | 0 | A line without a speaker (narration, off-screen voice). Medium. |
| 50009 `talk_intro` | 563 | speaker | 0 | 0 | A speaker's line, usually right after 50166/50167 (which look like scene or character setup). Low. |
| 50011 `choice` | 204 | 0 | 0 | 0 | A menu: the line holds the options separated by newlines, with a trailing newline. The rest of the record contains 50012 with `a1` = 1, 2, …, n (one per option) and then 50012 with `a1` = 11 (for example 1, 2, 11 in 148 of the 150 two-option menus). This reads as case labels and an end-of-switch marker. High for "menu", medium for the role of 50012. |

Other frequent opcodes have no text: 50007 (607, all arguments 0; often after a line), 50012/50013 (`a1` 1–11; choice branches), 50090, 50111, 50166–50171 (1,000 each, usually together: per-character scene setup).

In 50028, 50097 and 50100, `a1` holds card ids (4007–6397).

In 50098, 50099 and 50103, `a1` is 60,000.

Full semantics, branch targets and conditions are not decoded.

## Cross-check with ygotfToolkit

Its `story --dump`, run read-only on the maintainer's image (2026-10-25) with the CSV written to `extracted/`, gives the same 59,985 (archive, table, language, line) keys and identical text for every line. Both tools write newline as `\n`. Its notes give the same `I`/`L` structure and the 59,985 total.

The bytecode findings (10-byte instructions, `EveBI` record starts, text references in `a4`) were established here and are not in the toolkit's output.

## Open questions

- Opcode semantics beyond the text-bearing ones: control flow (how 50012/50013 branch, what the jump targets are), conditions and flags, and scene and camera commands. Trace the interpreter in `rel_story.prx`.
- The meaning of the header triple, and how the game picks a record (by triple, or by `EveBI` index).
- The `《Cnnn_k》` forms 1–5, and whether `nnn` equals the speaker id in `a1` of 50001/50002/50009. The ranges overlap (2–141 vs 001–151), but this is not proven.
- Where `《…》` placeholders and `$M`/`$C` are expanded in code, and whether the bracketed tokens in `SysMsg` are placeholders at all.
- Whether the empty lines (158 per language) are ever displayed.
