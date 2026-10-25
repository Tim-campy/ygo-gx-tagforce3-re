# Opponent and partner AI (work package 6)

Started. The AI lives in the duel engine `gmodule/rel_duel_eng.prx` (runtime base `0x09be1400`); this file records the first entry points.

## Where human and CPU paths split

Effect handlers that need a choice branch on the duelist kind. The most shared slot `+14` handler (`duel_effects_choose_targets`, `0x09cc0cdc`, 315 cards) reads the per-duelist value at `0x09e02998[controller]` (see `tag_duel.md`): value 1 takes the CPU path, anything else the interactive path.

- **Interactive** (`duel_effects_choose_targets_ui`, `0x09cc0bd8`): a two-step state machine on `0x09e28f70`. Step 0 checks that a valid target exists and opens the target-selection UI (`0x09dcea6c(side, card id, 0, duel_effects_call_handler_08)`), passing the card's target-filter wrapper as the callback that decides which slots can be picked; step 1, once the selection is done (`0x09dcedec`), applies it (`0x09cbed3c`).
- **CPU** (`ai_choose_targets`, `0x09d9ddfc`): prepares the AI for the controller (`0x09d9da30(side, side, 1)`), asks `0x09d649ec(ctx, arg, card id)` for the choice, then pops one level of an AI decision stack (`0x09e03026` entries of 8 bytes at `0x09e03028`) and replays a pending action when the stacked values differ (`0x09d91fe8`, `0x09d16afc`).

## AI memory

`duel_core_reset` clears `0x09e02ff8`, `0x25628` bytes (about 150 KiB), the largest region of duel state; the AI decision stack sits at its start (`0x09e02ff8`, `0x09e03026`, `0x09e03028`). Presumably the AI's working memory (hypothesis, medium).

## Key functions

| Address | Name | Conf. | Evidence |
| --- | --- | --- | --- |
| `0x09cc0cdc` | `duel_effects_choose_targets(ctx, arg)` | H | Slot `+14` handler of 315 cards; splits on the duelist kind. |
| `0x09cc0bd8` | `duel_effects_choose_targets_ui(ctx, arg)` | H | Target-selection UI driven by the target filter, as above. |
| `0x09d9ddfc` | `ai_choose_targets(ctx, arg, card)` | M | CPU branch of the same handler; nine callers, all choice handlers. |
| `0x09d649ec` | `ai_decide(ctx, arg, card)` | L | Returns the CPU's choice; body not read. |

## Open questions

- How `ai_decide` scores options; whether per-card AI knowledge is in the compare chains of `BOOT.BIN` (840 card ids used as constants there) or in this module.
- Partner AI in tag duels: same code with the partner's side, or a separate path?
- Layout of the 150 KiB AI memory.
