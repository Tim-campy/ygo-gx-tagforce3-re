# Duel AI priority tables (`gmodule/rel_duel_eng.prx`)

Status: `documented` (layout, lengths, consumers, order semantics). The per-card handlers themselves are not documented here; see `docs/subsystems/ai.md`. Addresses are runtime addresses with the module loaded at `0x09be1400`; file offset = address − `0x09be1400` + `0x54` (single `PT_LOAD` segment). Pointers stored in the file are module offsets (add the base).

Tool: `tools/ai_tables.py` lists the tables (`list`), gives per card the tables that know it (`cards`), sorts the handlers into behaviour classes by name (`classes`) and checks the layout against the code (`--check`). Its output is game data: keep it under `extracted/`.

Basis: Ghidra decompilation of every function that references the range `0x09dfd200`–`0x09e00900` (reference listing over the range, then reading each referencing function), plus a byte-level scan of the data. Nothing here was traced in PPSSPP yet.

## Entry layout

Pair tables (H):

| Offset | Size | Field |
| --- | --- | --- |
| `0x00` | 4 | `u32` card id (always in 3720–7993; the high half-word is 0). |
| `0x04` | 4 | `u32` module offset of the AI handler `int handler(ctx, arg)`. The entry is accepted when the handler returns ≥ 1 (see `ai_evaluate_activation`). |

The pointer to an entry (not just the card id) is passed down to `ai_evaluate_activation(entry, ctx, arg, commit)`, which calls `entry +4`.

**No terminator and no count field (H).** Every length is an immediate in the code (`ai_table_length`, `ai_chain_table_length`, and loops with hard-coded bounds), and the tables are packed back to back, so the pair after the last entry of a table is the first entry of the next one. The tool verifies that each length constant occurs in its consumer and that each consumer builds the table's address.

## Table list

All eleven pair tables are contiguous from `0x09dfd448` to `0x09e00800` except for a 56-byte gap at `0x09dfe4c8`–`0x09dfe500`, which holds two 7-word switch jump tables (of `0x09d3ecf0` and `0x09d440d8`). `0x09e00800` starts the jump table of `ai_main_state_open`. Total 1,648 entries, 1,548 distinct card ids, 674 distinct handlers; `ai_cond_always` (`0x09d6b6b8`) is used by 187 entries.

| Key | Address | Entries | Length set by | Consumers | Situation |
| --- | --- | --- | --- | --- | --- |
| T1 | `0x09dfd448` | 345 | `ai_chain_table_length` (`0x159`), loop bound in `ai_try_chain_tables` | `ai_try_chain_tables`; `ai_table_entry` (prefix of F); `ai_evaluate_card_all_tables` | Chain response: tried in every response window (only 8 hard-coded ids of it while the chain state byte `0x09e28fa0` is 2). |
| T2 | `0x09dfdf10` | 2 | loop bound 2 in `ai_choose_chain_response`; `ai_chain_table_length` 2 when its flag ≠ 0, else 0 | `ai_choose_chain_response` | Chain response, tried first when there is a chain link to answer. |
| T3 | `0x09dfdf20` | 181 | loop bound `0xb5`; `ai_chain_table_length` `0xb5` when its flag ≠ 0, else 0 | `ai_choose_chain_response` | Chain response, only when the response mode `0x09e0307c` ≠ 0 or `0x09ccb534(link, side, 1)` accepts the link. |
| A | `0x09dfe500` | 105 | `ai_table_length` `0x69`, loop bound in `ai_main_state_open` | `ai_main_state_open` (sub-state 2); `ai_table_entry` (filtered prefix of B) | Opening of the main phase. |
| B | `0x09dfe848` | 681 | `ai_table_length` `0x2a9`, or `0x312` = 105 + 681 when `0x09e03078` ≠ 0 | `ai_try_main_cards`, `0x09d8c420` (response window, cards passing `BOOT 0x0885fef0`), `ai_try_card_from_table` (calls from effect code with a fixed card id), `0x09d7c9a8` | Main phase spells and monster effects. |
| C | `0x09dffd90` | 7 | `ai_table_length` 7, loop bound in `ai_try_summon_enablers` | `ai_try_summon_enablers` | Before summoning (main step 1). |
| D | `0x09dffdc8` | 199 | `ai_table_length`: 199 when `ai_get_battle_dominance(side) < 0`, else 0 | `ai_try_comeback_cards`, `ai_main_state_end`, `ai_try_card_from_table` | Recovery when behind. |
| E | `0x09e00400` | 16 | `ai_table_length` `0x10` | `ai_try_battle_cards` | Battle check / attacker choice. |
| F | `0x09e00480` | 12 | `ai_table_length`: 345 + 12 when the phase word `0x09e2d1e8` is 3 (battle), else 0 | `ai_try_battle_cards` (unless its second argument is set), `0x09cfcf5c` | Battle traps; in the battle phase the list seen through `ai_table_entry` is **T1 first, then F** (indexes 0–344 return T1 entries). |
| G | `0x09e004e0` | 94 | `ai_table_length` `0x5e`, loop bound in `ai_main_state_end` | `ai_main_state_end` (sub-state 2) | End of the main phase. |
| H | `0x09e007d0` | 6 | `ai_table_length` 6, loop bound in `ai_main_state_end` | `ai_main_state_end` (sub-state 5, last) | Last resort before ending the turn. |

`ai_evaluate_card_all_tables` (`0x09d30af8`) looks a given chain context's card up in A, C, D, E, F, B, G, H, T1, T2, T3 (in that order) and runs `ai_evaluate_activation` on the first matching entry whose evaluation accepts. `0x09d8b38c` (3,676 bytes) and `0x09d440d8` (14,528 bytes) also scan the tables for a specific card with inlined loops (they pick per-phase tables: G when `0x09e2d1e8` = 4, A when it is 2, and so on).

### Order and filtering

- **Order is priority (H).** Every walker stops at the first entry whose `ai_try_table_entry` / `ai_try_chain_table_entry` succeeds and returns 1 (the main-phase steps then reset their sub-state and are called again), so an earlier entry is always tried before a later one.
- **A prefixed to B (H).** While the deferred-category mask `0x09e03078` is non-zero, `ai_table_entry(side, B, i)` returns `A[i]` for `i < 105`, but only when `BOOT 0x0885ff3c(card)` is non-zero and bit `card_db_get_icon(card)` of `0x09e03078` is set; otherwise it returns 0 (the walker skips the slot). Indexes ≥ 105 return `B[i − 105]`.
- **T1 prefixed to F (H)**, see the table.
- **Conditional lengths (H):** D is empty unless the AI is behind; F (and with it the T1 prefix) is empty outside the battle phase; T2/T3 have length 0 when `ai_chain_table_length` is called with flag 0.
- `0x09d7c9a8` walks a sub-range of B: from the first entry whose handler is `0x09d7c780` until card `0x1d2a` (M).

## u16 card-id lists before the tables

Three lists of `u16` card ids sit right before T1. They have no handler column; the walker `ai_try_chain_tables` (`0x09d2f908`) pairs each id with one fixed handler, chosen by the byte `0x09e28fa0` (only while `0x09e28f98` ≠ 0). `0x09e28fa0`/`0x09e28f98` are the first code and the count of the timing-event queue (`battle.md`), and the handlers test the same event code in the link (`ai_handler_on_attack_declared_event` R1, `ai_handler_on_damage_step_event` R2; see `docs/subsystems/ai-helpers.md`), so the lists are per-event response lists (M). The list is tried before T1; when no id of it is accepted, the whole of T1 is walked as usual. Meaning of the states: open (M for the mechanism, L for the reading as "special chain situations").

| Key | Address | Entries | State `0x09e28fa0` | Handler | Notes |
| --- | --- | --- | --- | --- | --- |
| R1 | `0x09dfd2dc` | 143 | `0x12`, `0x13` | `0x09d22924` | Loop bound `0x8f`. The last entry is `0x1935`; `0x09d261c4` walks the list until it meets its own card id (`0x1935`), so that card also acts as a sentinel. A zero half-word follows. |
| R2 | `0x09dfd3fc` | 36 | `0x14` | `0x09d262c8` | Loop bound `0x24`; runs straight into R3. |
| R3 | `0x09dfd444` | 1 | `0x1b` | `0x09d27348` | A single id; followed by a zero half-word (padding to `0x09dfd448`). |

## Consumers (functions)

| Address | Name | Role (confidence) |
| --- | --- | --- |
| `0x09d8f0c4` | `ai_table_length(side, table)` | Lengths of A–H (H). |
| `0x09d8efc0` | `ai_table_entry(side, table, i)` | Entry `i`, with the A→B and T1→F prefixes (H). |
| `0x09d3023c` | `ai_chain_table_length(side, table, flag)` | Lengths of T1–T3; T2/T3 only when `flag` ≠ 0 (H). No side effects; callers `ai_table_length`, `ai_table_entry`, `ai_evaluate_card_in_table`, `ai_try_card_from_table`. |
| `0x09d30230` | `ai_chain_table_entry(side, table, i)` | `table + 8 × i` (H). |
| `0x09d2fd80` | `ai_choose_chain_response(side, link)` | Sets the response mode, walks T2 then (conditionally) T3, then calls `ai_try_chain_tables` (H for the walks). |
| `0x09d2f908` | `ai_try_chain_tables(side, link)` | while `0x09e28f98` ≠ 0, first R3, R2 or R1 depending on `0x09e28fa0` (state 2 instead walks only 8 hard-coded ids of T1 and stops there); otherwise, and after an R list, all of T1; then `0x09d8c420` (B in a response window) when there is no link; then, while card `0x19a3` is active for the side, its set traps of icon 4 in slots 5–9 (M). |
| `0x09d2f5a8` | `ai_try_chain_table_entry(side, entry, link, mode)` | Response-window counterpart of `ai_try_table_entry`: skips a trap already in the chain, then tries field slots 0–10 of both sides and the hand, building a context at the chain top and calling `ai_activate_from_table` (M). |
| `0x09d307c4` | `ai_evaluate_card_in_table(ctx, arg, table)` | Finds `ctx`'s card in one table and returns 1 when `ai_evaluate_activation` accepts (M). |
| `0x09d30af8` | `ai_evaluate_card_all_tables(ctx, arg)` | `ai_evaluate_card_in_table` over all eleven tables (M). |
| `0x09d309b0` | `ai_try_card_from_table(side, card, table, arg)` | Tries only the entries of `card` in one table; used by effect and battle code to ask "would the AI use this card now" (M). |
| `0x09d8b184`, `0x09d8cfbc`, `0x09d8c1e8`, `0x09d8c280`, `0x09d8c300`, `0x09d8c508` | `ai_main_state_open`, `ai_main_state_end`, `ai_try_summon_enablers`, `ai_try_comeback_cards`, `ai_try_battle_cards`, `ai_try_main_cards` | Main-phase walkers (see `docs/subsystems/ai.md`). |

## Card ids without a cardinfo record

18 entries (18 distinct ids, for example `0x1303` and `0x1f24`) name card ids for which the European `cardinfo_eng.ehp` has no record (`CARD_IntID` maps them to 0). All of them also have records in the effect tables (`docs/formats/effect-tables.md`), so the engine supports cards that the released card list does not contain (H for the fact; why they are missing is open). They explain the "valid" counts 523/528 and 1,107/1,120 reported for `0x09dfd448` and `0x09dfe500` in `effect-tables.md`. `--check --cardinfo` lists them and does not count them as problems.

## Checks done by the tool

- The tables are contiguous apart from the documented gap and end at `0x09e00800`; the gap and the four words after the end are code pointers (jump tables).
- Every entry has a card id in 3720–7993 and a handler inside `.text`.
- Each length constant occurs as an immediate in its consumer, and each consumer builds the addresses of the tables it uses (`lui`/`addiu` pairs).
- The u16 lists have in-range ids, R1 ends with `0x1935`, R1 and R3 are followed by a zero half-word.

## Open questions

- What `BOOT 0x0885ff3c` and `BOOT 0x0885fef0` test (gates for A-in-B and for B in response windows); probably card-kind predicates.
- Meaning of the timing-event codes 2, `0x12` and `0x1b` that select the T1 subset, R1 (with `0x13` attack declared) and R3 (`0x14` is the start of the Damage Step).
- Why 18 engine-supported card ids have no cardinfo record (cut cards, Japanese-only cards).
- Handler semantics: the 77 handlers shared by ≥ 3 entries are named and classified (`docs/subsystems/ai-helpers.md`, `ai_tables.py classes`); the 600 single-use handlers remain.
