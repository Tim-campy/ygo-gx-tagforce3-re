# Forbidden/limited list (`BOOT.BIN`)

Status: `reimplemented` (reader and writer, round trip below). The built-in restriction list is a static table in `BOOT.BIN`'s `.data` at `0x08878cb8`: 114 entries of `(u16 card id, u16 status)`. Tool: `tools/tables.py limits` (CSV export, `--check`).

| Status | Meaning | Entries |
| --- | --- | --- |
| 0 | Forbidden | 43 |
| 1 | Limited (1 copy) | 59 |
| 2 | Semi-limited (2 copies) | 12 |
| 3 | Unlimited; never stored, it is the default | — |

Entries are grouped by status (all forbidden cards first), not sorted by id.

## Evidence

- Code: `deck_get_default_limit(id)` (`0x08835e70`) walks the 114 pairs (loop bound `0xe4` half-words) and returns the stored status, or 3 when the card is not listed. `deck_reset_limits` (`0x08835df4`) sets every id from `0xe88` to `0x1f39` (3720–7993, the card-id range) to 3 with `deck_set_limit` (`0x088566a4`), then applies the 114 pairs.
- Content: status 0 holds Pot of Greed, Graceful Charity, Raigeki, Change of Heart and Harpie's Feather Duster, all forbidden in the real lists of the time; Cyber Dragon has status 2. This list has Heavy Storm and Monster Reborn as limited, which is the game's own choice.

## Writer and round trip

`tables.write_limits(boot, limits)` writes the 114 `(card id, status)` pairs back into a copy of `BOOT.BIN`; with `tables.limit_span()` the round trip blanks the table, writes the list read by `read_limits()` and compares the whole file: byte-identical (`limit_list` is `reimplemented`):

```
python3 -I tools/roundtrip.py --check <PSP_GAME> --only limit_list
```

## Open questions

- `deck_set_limit` writes the status into a per-card table; is that table part of save data (does the game support editing or updating the list)? **Answered elsewhere** (port-readiness audit, 2026-11-04): yes: per-card status in the save collection record, byte 2 bits 0–1 (`save.md` "Card collection").
- Header bytes before the table (`0x7073`, `0x61`) and the data after it (`(0x2b28, 3)`, `(0x2b40, 3)`, …) are unrelated or unexplained.
