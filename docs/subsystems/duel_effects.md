# Card effects (work package 4)

Not started. This file records the first architectural evidence, before any function-level work, as CLAUDE.md asks.

## Effect architecture: first evidence

**Hypothesis (medium-high): card effects are implemented as code in the duel-engine module `gmodule/rel_duel_eng.prx`, selected by comparing card ids, not as data tables or scripts.**

Basis: counting MIPS instructions that load a card id as an immediate (`addiu rt, $zero, id` or `ori rt, $zero, id`, with `id` an existing card id):

| Module | Instructions | Distinct card ids | Of which normal monsters |
| --- | --- | --- | --- |
| `rel_duel_eng.prx` | 19,597 | 2,861 | 82 |
| `BOOT.BIN` | 1,996 | 840 | 47 |
| `rel_title.prx` | 103 | 5 | 1 |
| ten other modules | 21–66 each | 3–40 each | — |

2,797 of the 2,940 cards that are not normal monsters (that is, cards with effects) appear as an immediate somewhere, almost all in `rel_duel_eng.prx`; normal monsters, which have no effect, almost never do. A random 16-bit value hits a valid id with about 5% probability, so these counts are not noise. A sample at file offset `0x1100a0` shows the pattern `li v0, <id>; beq s1, v0, <target>` repeated for Monster Reborn, Mirror Force, Pot of Greed, Harpie's Feather Duster and others, which is a compare chain on a card id held in `s1`.

What this does not settle: part of the comparisons may belong to the AI (which also needs per-card knowledge) rather than to effect resolution; whether the module dispatches through jump tables, handler tables or compare chains; and whether a generic layer (shared effect primitives) sits underneath.

## Next steps

1. Import `rel_duel_eng.prx` into the Ghidra project with the ghidra-allegrex loader at its runtime address (from the PPSSPP symbol export, which lists functions in the module ranges loaded at the time).
2. Classify the functions that contain card-id immediates: compare chains vs. table lookups, and AI vs. resolution.
3. Document the dispatch mechanism before any individual effect.
