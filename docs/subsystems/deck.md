# Decks and deck rules

## Key functions

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x08835e70` | `deck_get_default_limit(id) → status` | H | Linear search of the 114 `(id, status)` pairs at `0x08878cb8`; 3 when absent. Caller `0x08832fa4`. |
| `0x08835df4` | `deck_reset_limits()` | H | `deck_set_limit(id, 3)` for ids `0xe88`–`0x1f39`, then `deck_set_limit` for each listed pair; then `0x08836aec(5)` and `0x0885660c`. Caller `0x08853e80`. |
| `0x088566a4` | `deck_set_limit(id, status)` | M | Called only as above; body not read. |

## Data

- Restriction list: `docs/formats/limit-list.md`.
- `deck/all_<lang>.ehp` holds `fileTbl.dat` (a `u16` count, 3,502, followed by card ids; presumably the card shown at each image slot of the `card/*.cip` files), `sameCardTbl.dat` (count 49, then pairs starting with id 4007, Blue-Eyes White Dragon; cards with alternative artworks), deck-editor strings and help text. Not decoded.
- `deck/tutorial.ehp` holds `deck_tutorial00.bin`–`04.bin`, likely a deck format; not decoded.

## Open questions

- Deck format (tutorial decks, opponent decks, the player's decks in save data).
- `fileTbl.dat` and `sameCardTbl.dat` layouts and their relation to `CARD_SamePict`.
