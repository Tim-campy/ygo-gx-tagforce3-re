# Card ids tested in engine code (`tools/card_refs.py`)

Not every card effect goes through the effect tables (`effect-tables.md`). On the disc, 273 released effect cards have no effect-table record, no list entry and no parameter: Goddess with the Third Eye, Marshmallon and Summon Priest are examples. The engine implements these cards by testing their id inside shared code:

- compare chains (`if (id == A || id == B ...)`);
- `switch (id)` jump tables and range tests;
- calls to helpers that take a card id, such as "count the copies of card K in the Graveyard".

`tools/card_refs.py` finds those tests. It scans every function of the module for card-id immediates and records the ones that the code uses as card ids. `tools/card_effects.py` joins the result as `engine_refs` (see `card-effect-spec.md`).

```
python3 -I tools/card_refs.py <USRDIR>/gmodule/rel_duel_eng.prx list -o extracted/card_refs \
        [--cardinfo <USRDIR>/duelsys/cardinfo_eng.ehp] [--boot <SYSDIR>/BOOT.BIN] \
        [--draw <USRDIR>/gmodule/rel_duel_draw.prx] [--functions re/functions.csv]
python3 -I tools/card_refs.py <prx> --check [--cardinfo ...] [--boot ...] [--draw ...]
python3 -I tools/tests/test_card_refs.py
```

Library: `card_refs(prx_bytes, functions=None, names=None, base=0x09be1400, module="rel_duel_eng", cards=None)` returns `{card id: [reference dict]}`, and `all_refs(prx, functions, names, boot=None, draw=None)` merges the three modules. Pure Python, about 2 s for `rel_duel_eng` alone and 9 s with `BOOT.BIN` and `rel_duel_draw`. Ghidra is not needed.

## Modules and function bounds

| Module | Base | `.text` |
| --- | --- | --- |
| `rel_duel_eng.prx` | `0x09be1400` | `0x09be1400`–`0x09de415c` |
| `BOOT.BIN` | `0x08804000` | `0x08804000`–`0x0887234c` |
| `rel_duel_draw.prx` | `0x0983fb00` | `0x0983fb00`–`0x098b98a4` |

The `.text` bounds come from the section headers. Section addresses are module offsets, as in every PRX of the disc. Without section headers the tool uses the first `PT_LOAD` segment.

Function bounds and names come from the bare-hex ids of `re/functions.csv` that fall inside the module's `.text`, the same way `effect_classify.Registry` gets them. If fewer than two ids fall inside, the tool uses heuristic entry points instead: `jal` targets, and prologues after `jr ra`. The registry group of a reference is the prefix of the function name (`duel_core`, `duel_effects`, `card_db`, `ai`, ...). It is empty for a default `FUN_…` name.

## Heuristic

Card ids are 14-bit values. The scan uses the id range of `effect_params` (`FIRST_CARD`–`LAST_CARD`, `0x0e88`–`0x1f39`). An immediate in that range becomes a reference only when one of these patterns uses it:

| Kind | Pattern | Ids recorded |
| --- | --- | --- |
| `eq` | `li rX, K` (`addiu`/`ori` from `zero`) whose first reader is `beq`/`bne`/`beql`/`bnel`, `xor` or `subu`; or `xori rY, rX, K` | K |
| `switch` | `addiu rY, rX, -K; sltiu rZ, rY, N; beq rZ, zero, default; ... lw; jr` with a jump table of N module offsets | Each id of `[K, K+N)` whose case target is not the default |
| `range` | The same `addiu -K; sltiu N` (N ≤ 128) without a jump table | Every id of `[K, K+N)` |
| `lt` | `li rX, K` read by `slt`/`sltu` | K (one bound) |
| `bound` | `slti`/`sltiu rY, rX, K` | K (one bound) |
| `arg` | `li a0`–`t3, K` before a `jal`/`j`, or in the delay slot of a `jal` | K; `detail` holds the callee name |
| `store` | `li rX, K` stored with `sb`/`sh`/`sw` | K (an id written into a duel structure) |
| `return` | `li v0, K` that reaches `jr ra` | K |

The scan looks for the first reader on the straight line after the `li`, up to 24 instructions. Rules for the scan:

- It follows one unconditional branch and one `move`.
- It stops when the register is overwritten, and at a call that clobbers it.
- An `li` in a branch delay slot is followed on the taken path first, as the compiler's `beql …; li a0, K` idiom requires.

An immediate with any other first reader is dropped, for example arithmetic, a multiplication or no reader at all.

Each reference also carries these fields:

| Field | Content |
| --- | --- |
| `operand` | For `eq`, `range` and `switch`, where the compared value comes from. The scan traces it back on the straight line to the function start (2,048 instructions at most): `u16 load`, `masked id` (`andi 0x3fff`), `result of <callee>`, `argument` (an argument register that is never written), `word load`, `computed`, `clobbered`, ... |
| `value` | For `eq`, the constant that the taken branch returns, evaluated with `effect_params.evaluate`. For `switch`, the value its case returns. |
| `constants` | Up to 6 small non-card immediates near the reference. |

`eq` references are a superset of the `li; beq` cases of `effect_params.chain_cases`.

`switch`, `eq` and `arg` name one card. `card_effects.py` counts only these three kinds (`STRONG`). `range`, `lt`, `bound`, `store` and `return` are listed but do not explain a card on their own.

## Precision and recall (disc, registry of this commit)

| Measure | Value |
| --- | --- |
| References, all three modules | 22,158 to 2,971 ids in 1,716 functions: `eq` 18,013, `arg` 3,717, `store` 238, `return` 61, `range` 54, `bound` 50, `switch` 21, `lt` 4 |
| References per module | `rel_duel_eng` 19,961, `BOOT.BIN` 2,119, `rel_duel_draw` 78 |
| Released cards referenced | 2,901 of 3,553. Of the other 70 ids, 59 are unreleased ids that other sources also know (46 have effect records). Eleven occur only here: `0x0f00`, `0x0fa0`, `0x0fa1`, `0x1240`, `0x1447`, `0x15e5`, `0x1b6c`, `0x1f00`, `0x1f0d`, `0x1f1c` and `0x1f3a`. Some of these, such as `0x0fa0` (4000) and `0x0f00`, are likely numeric constants |
| Recall on documented tests (`KNOWN`) | 9 of 9: Pot of Greed in the draw-count chain; Dark Deal and the `0x1b61` marker in `duel_effects_link_should_resolve`; the two `duel_effects_get_spell_speed` cases; the `0xfb6` used-this-turn marker; the Forbidden One pieces passed by `duel_core_check_win` |
| `eq` operands that are card-id shaped | 77.4 % (78.4 % in `rel_duel_eng`): a u16 load, the `0x3fff` id mask, the result of a call (mostly `duel_core_get_slot_card_id`, `ai_get_visible_card_id`, `ai_mask_hidden_card_id`, `duel_core_get_slot_name_id`) or an argument. Word loads 6.0 %, computed values 7.7 %, values clobbered on the straight line 5.3 % |
| Trace error floor | 1.6 % of `eq` operands are byte loads, which can never hold a 14-bit id. These are path-insensitive back-traces that picked a definition on another path |
| Round-number control | Ids that are multiples of 100 could be ATK or LP constants instead of ids. Their `eq` references have the same operand profile (79.5 % card-id shaped) as all references, so the scan shows no excess of false positives there. Of the multiples of 100 that are not cards, only `0xfa0` (4000) and `0x1e78` remain. `0xfa0` occurs only as `lt`, `bound` and `store` (an LP or ATK value, so not a card id). `0x1e78` has an effect record and is an unreleased card id |
| Normal and token cards referenced | 142. Expected for fusion materials, tokens and cards named by other effects. Not checked one by one |

Precision of `eq`/`switch`/`arg`: 77 % of the `eq` references are confirmed by a card-id-shaped operand. The rest are unverified rather than wrong: the trace-error floor is small, and there is no round-number excess. A precision of at least 0.9 is a hypothesis (confidence medium); a PPSSPP trace of a sample would settle it. Not every `eq` reference implements the referenced card's own effect: a card that names another card ("if you control Dark Magician") tests the other card's id. The function name, the operand and the reference kind help to tell these apart.

## Missing cards explained

The 273 effect cards that had no data in `card_effects.py` (188 effect monsters, 30 traps, 26 spells, 15 effect fusions, 6 Gemini, 4 effect tuners, 2 Toons, 2 effect synchros) all have at least one `eq`/`switch`/`arg` reference:

| Basis | Cards |
| --- | --- |
| `eq`/`switch` in a named `rel_duel_eng` function | 185 |
| `eq`/`switch` only in unnamed `rel_duel_eng` functions | 30 |
| Only as a call argument in `rel_duel_eng` (another card or helper names them) | 52 |
| Only in `BOOT.BIN` | 6 |

The functions that test the most of these cards are battle and summon rules:

- `duel_core_get_direct_attack_mode` (23)
- `card_db_can_be_special_summoned` (21, `BOOT.BIN`)
- `duel_core_check_attack_restrictions` (21)
- `duel_core_is_valid_attack_target` (19)
- `duel_core_has_piercing` (18)
- `duel_effects_is_activation_locked` (16)
- `duel_core_chain_step` (15)
- `duel_core_battle_is_destroyed` (14)

The six `BOOT.BIN`-only cards include the four fusion substitutes: Goddess with the Third Eye, Beastking of the Swamps, Versago the Destroyer and Mystical Sheep #1. They form one compare chain in `FUN_08866870`. Hypothesis (M): that function is the "can substitute for a fusion material" test; it is not yet in the registry.

## Outputs

`card_refs.csv` (one row per reference): `card_id name kind detail module address use function function_name group operand value constants`. `address` is the instruction with the immediate. `use` is its reader (the branch, `sltiu`, call or store).

`card_ref_functions.csv` (one row per function): `module function function_name group ids kinds`.

Both are game data: keep them in `extracted/`.

## `--check`

`--check` prints the counts, the operand profile and the recall on `KNOWN`. With `--cardinfo` it also prints the released-card share, the precision proxies, and the effect cards without an effect-table record or list entry (369 on the disc, all referenced). It fails in two cases:

- a documented test of `KNOWN` is not found (checked only on the full `rel_duel_eng` module);
- fewer than half of the referenced ids are released cards.

## Limits and open questions

- The scan is straight-line and path-insensitive. An id that is loaded into a register and compared after a loop or join is not seen. Some operands are attributed to a definition on another path.
- Ids built arithmetically (`base + k`) or read from data tables are not found. The known data tables have their own tools: effect tables, lists, AI tables, token, fusion and ritual tables.
- `range` and `bound` keep every id of the interval; they are not used to explain cards.
- Whether a reference implements the card's own effect or names it from another card's effect needs the function's meaning. This improves as functions are named in `re/functions.csv`.
