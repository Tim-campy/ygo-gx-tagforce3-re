# Session E, block E-P results (2026-10-31)

Plan: [`ppsspp-plan.md`](../ppsspp-plan.md), Session E, block E-P. Same boot as block E-W (`S = 0x08aa57c8`). E0: inside the purchase screen `0x090d9678` holds `addiu sp, sp, -0x80` (`rel_shop` at `0x090ced00`); on the shop's field map the same address holds `rel_field` code (`li v0, 0x16`), the two modules share the base. Log-only breakpoints, no memory edits.

## E16. One pack purchase: pass

Log (purchase screen):

```
dp_add 0xffffff9c          ra 0x090e0ddc (rel_shop)
pack_bought p=0x11
packs_bought +1
draw p=0x11 out=0x09fff55c
pack_entry p=0x11 n=0 r=1
commit                     (once, leaving through the results screen)
```

The many other `commit` lines were logged while `rel_field` occupied the address (before entering and after leaving the purchase screen) and are not `shop_commit_results`.

Cards shown, in order: Nex, Chrysalis Pinny, Space Gift, Neo-Spacian Aqua Dolphin, Neo-Spacian Flare Scarab.

Diff `E16-a` → `E16-b` (differential save 10):

| Offset | Before → after | Meaning |
| --- | --- | --- |
| `0x0fdfc` | 2,881 → 2,781 | DP − 100 (the pack price) |
| `0x1543b` = `0x1542a + 17` | 0 → 1 | pack 17 bought (`save_set_pack_bought`) |
| `0x16602` | 0 → 1 | packs bought (`save_add_packs_bought`) |
| `0x168ce` = `0x16604 + 0x2a × 17`, byte 0 | `0xaa` → `0xa9` | shelf stock nibble − 1 |
| `0x168d0`, entry 0 | 0 → 1 | rarity box entry `n = 0` written with `r = 1` |
| 5 collection records (`0x143c4`, `0x143d8`, `0x148a0`, `0x148b4`, `0x14f08`) | `00 00` → `02 01` | the 5 drawn cards: count byte 1 = 1, byte 0 = `0x02` (new: probably a "new card" flag) |
| `0x1a0e8`–`0x1a0f0` | changed | player position and direction (the player walked) |
| story block runtime records `0x17060`–`0x19714` | small changes | NPC positions (game running) |
| `+0x0c` | changed | frame counter |

Every expected change is present and nothing else changed: price, bought flag, purchase counter, stock nibble, exactly one rarity-box entry (`n` = 0 used entries before, `r` = 1), the five cards entering the collection only at `commit`. New: collection record byte 0 becomes `0x02` for a newly obtained card (meaning of the bit: medium, "new").

E17 (a box of 20) was not run.
