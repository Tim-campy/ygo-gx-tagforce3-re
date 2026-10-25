# Effect classification by callee signature (work package 4)

`tools/effect_classify.py` sorts the 2,600 records of the four 24-byte effect tables (`docs/formats/effect-tables.md`) into effect categories (destroy, draw, banish, special summon, damage, …) without Ghidra, from the maintainer's own `rel_duel_eng.prx`. It does not read card text. The categories come from **what the handlers call**, so they depend on the function names in `re/functions.csv`. Each run uses the names current at that moment, and the classification gets better as other work names more helpers. The tool also writes a ranked list of the unnamed helpers that most effect records reach, which is the naming worklist that raises coverage fastest.

```
python3 -I tools/effect_classify.py <USRDIR>/gmodule/rel_duel_eng.prx --check
python3 -I tools/effect_classify.py <USRDIR>/gmodule/rel_duel_eng.prx -o extracted/effect_classify \
        [--cardinfo <USRDIR>/duelsys/cardinfo_eng.ehp] [--boot <SYSDIR>/BOOT.BIN] [--depth 3] [--ai-depth 1]
python3 -I tools/tests/test_effect_classify.py
```

Outputs, all game data that stays in `extracted/`:

- `effect_classes.csv`: one row per record, with the card id and name, table and index, the categories reached from each of the five slots (`resolve`, `target_filter`, `condition`, `activation`, `target_choice`), the engine command codes reached from the resolve slot, the unnamed callees, and the handler addresses.
- `worklist.csv`: the unnamed callees, ranked.
- `ai_clusters.csv`: the AI handler groups.
- `summary.txt`: the figures quoted below.

`--boot` names the import stubs after their current `BOOT.BIN` names (through `tools/prx_imports.py`) instead of the `thunk_` names stored in the registry.

## Method

1. **Function bounds.** Every bare-hex id of `re/functions.csv` inside `.text` (`0x09be1400`–`0x09de415b`) starts a function, and the function ends at the next registry start. With no registry for the module, the tool falls back to the heuristic entry points of `effect_params.function_starts`.
2. **Call scan.** The tool decodes each function's words and records three kinds of call:
   - `jal`, and `bltzal`/`bgezal`;
   - tail calls: a `j`, or an unconditional `beq zero,zero` / `b`, whose target lies outside the function;
   - indirect calls (`jalr`), which are only counted.

   `jr` to a register other than `ra` (a switch) ends the path. Code that no path from the entry reaches, such as switch cases, is scanned afterwards from an all-unknown state, so no call is lost.
3. **Constant tracking (known bits).** A forward dataflow pass runs over each function. Every register holds a pair `(mask, value)`: the bits set in `mask` are known. The pass models:
   - `lui`, `addiu`, `ori`, `andi`, `xori`, `addu`, `subu`, `or`, `and`, `xor`, `nor`, `sll`, `srl`, `sra`, `ext`, `movz`, `movn`, and `slt`/`sltu` (whose upper 31 bits are known to be 0);
   - every other write (loads, `mfc1`, VFPU `mfv`, `lwl`/`lwr`, …), which makes the register unknown.

   States meet at branch targets: a bit stays known only if every path agrees on it. The pass iterates to a fixed point, and a target is always processed with its current merged state, never a stale one. The delay slot of a branch or call runs before the transfer; the delay slot of a likely branch runs only on the taken path. After a call, `at`, `v0`, `v1`, `a0`–`t7`, `t8`, `t9` and `ra` are unknown, and the `s` registers survive. At each call the tool keeps the known bits of the eight argument registers `a0`–`a3` and `t0`–`t3` (`a4`–`a7` in the PSP's EABI). This handles the compiler's usual way of building the side bit of a command:

   ```
   beql a0,zero,L ; addu v0,zero,zero   # side 0 (delay slot, taken path only)
   ori  v0,zero,0x8000                  # side 1
   L: ori v0,v0,0x24 ; andi a0,v0,0xffff ; jal duel_core_push_command
   ```

   Here `a0` comes out as code `0x24` with bit 15 unknown. This example is `duel_core_lose_lp`, and the result matches `battle.md`: command `0x24`, reason 3 in `a2`.
4. **Thunks.** A callee whose entry is `j X` is followed to `X`, up to four hops. Up to two ALU instructions may come before the `j`; those and the delay slot are applied to the argument state. So a call through `thunk_duel_core_push_command` (`0x09be14bc`) counts as a call to `0x09dc07f8`. The same rule reads the slot `+08` stubs (`j duel_effects_target_filter; addiu a3,zero,K`) as filter calls with a constant flag word.
5. **Constant stores.** The tool records every `sb`/`sh`/`sw` of a known value to a known address, that is a base register built with `lui`/`addiu`, as runtime address = `0x09be1400` + module offset.
6. **Closure.** From each handler, the scan goes breadth-first for `--depth` levels (3 by default; the handler itself is level 1). Each callee is matched against `tools/effect_categories.csv`:
   - a callee matched by a `name` or `addr` row is a **leaf**. Its category is recorded and its body is not scanned: the helper's own internals, such as the many commands that `duel_core_send_field_card` can post, must not leak into every caller;
   - rows with role `stop` mark infrastructure and predicates (`duel_core_get_*`, `ai_*`, `card_db_*`, the handler-dispatch wrappers, …), which are leaves with no category;
   - unmatched callees inside the module are descended into.
7. **Mapping rows.** The mapping file is CSV with `#` comments and six kinds of row:
   - `name`: a regex searched in the callee's name, with a leading `thunk_` removed. The first matching `name`/`addr` row decides.
   - `addr`: an exact address.
   - `queue`: the role given to `duel_core_push_command`. At each call, the low 12 bits of `a0`, when known, are the command code.
   - `cmd`: command code → category.
   - `arg`: a callee regex plus `register&mask`. It matches when the register's mask bits are all known and set. This is how the target-filter flag word, already decoded in `effect-tables.md`, is reused: `0x1000` destroy, `0x2000` banish, `0x4000` send to graveyard, `0x10000` take control, `0x40000` change position, `0x80000` return, `0x400` targets.
   - `store`: conditions such as `0x09e2d2b8=0x0f` or `0x09e2d2bc&0x2` that must all hold for the constant stores of one scanned function.

   `cmd`, `arg` and `store` rows add to whatever the `name`/`addr` row decided and never change whether a callee is a leaf. Roles:
   - `effect`: counts for coverage;
   - `meta`: recorded but not counted (`once_per_turn`, `optional`, `choose_targets`, `timing_event`, `set_flag`, `select_ui`, `detach_effect`, `targets`).

### The field-card send batch (new finding)

Destruction, banishment and returns to the hand or Deck are **not** commands posted by the handlers. A handler calls one of the small request functions at `0x09c22a98`–`0x09c274a4` (31 functions in the module store `0x09e2d298 = 1`). These fill a batch: a slot mask at `0x09e2bba4`, the destination location at `0x09e2d2b8`, a mode word at `0x09e2d2bc`, and `0x09e2d298 = 1` to start it. The batch processor `0x09c232bc` (`duel_core.md`) then moves the cards over the following frames.

The constant-store scan of the whole module gives the following. Confidence H for the stores, M for the meaning of the mode bits:

| Global | Values stored by the request family |
| --- | --- |
| `0x09e2d2b8` destination | `0x0e` graveyard in 14 functions, `0x0f` banished in 4, `0x0d` deck in 4, `0x0b` hand in 3 (location ids from `duel_core.md`) |
| `0x09e2d2bc` mode | `2` in 5 functions, among them `0x09c24790`, the resolve helper of Dark Hole, Raigeki and Mirror Force. `0x10000002` in 1. `0x1000` in 3, among them `duel_core_tribute_monsters` (`0x09c268d0`). `0x20000` in 2, `0x4000000` in 1, `0xa` in 1, `0` in 11 (among them `duel_core_request_send_field_card_to_graveyard`). `4` is stored by `duel_core_request_battle_destruction` (`battle.md`). |

Mode bit 1 (`2`) agrees with bit 1 "destroy" of `duel_core_send_field_card`'s `flags`, and `0x1000` agrees with Tribute. The `store` rows therefore map these modes and destinations to categories:

| Store | Category |
| --- | --- |
| mode `&2` | destroy |
| mode `&0x1000` | tribute |
| destination `0x0b` | return_to_hand |
| destination `0x0d` | return_to_deck |
| destination `0x0f` | banish |
| destination `0x0e` with mode `0` | send_to_graveyard |

These rows lifted resolve coverage from 81 % to 92 %. The other mode bits (`0x20000`, `0x4000000`, `0x10000000`, `8`) are not yet explained.

## Validation

- **Scanner against Ghidra.** Ghidra's `getCalledFunctions` ran on a read-only copy of the project for 60 randomly chosen handlers.
  - 56 call sets are identical.
  - The 4 that differ are cases where the scanner finds more calls, and both reasons are expected: tail calls to `duel_effects_target_filter` (`j`), which Ghidra does not count as calls; and functions that Ghidra has with a 1-byte body (registry size 1, e.g. `0x09c3b658`, `0x09c3fd74`), so Ghidra lists no callees for them.
- **Command codes.** Of the 388 call sites of `duel_core_push_command` in the module, including those through the thunk, the code in `a0` is recovered at 385 (99.2 %). The three exceptions are the thunk's own `j` and two other sites, `0x09dc99f8` and `0x09de0b64`.
- **Spot checks against the card texts.** Pot of Greed → draw. Dark Hole, Raigeki, Mirror Force, Heavy Storm, Torrential Tribute, Trap Hole, Sakuretsu Armor, Mystical Space Typhoon → destroy. Giant Trunade, Compulsory Evacuation Device → return_to_hand. Dimensional Prison, Nobleman of Crossout → banish. Monster Reborn → special_summon. Card Destruction → draw + send_from_hand. Sangan and Witch of the Black Forest → move_list_card (commands `0x3e`, `0x52`, `0x55`). Swords of Revealing Light, Book of Moon → position_change + attach_effect. Solemn Judgment → negate, with pay_lp in its activation slot.

## Current numbers (depth 3, registry of this commit)

| Measure | Value |
| --- | --- |
| Records (S/T 938, M1 869, M2 365, M3 428) | 2,600; 2,562 have a resolve handler |
| **Coverage**: resolve slot has at least one `effect` category | **2,391 = 92.0 %** of all records (93.3 % of those with a resolve handler) |
| Per table | S/T 826/938, M1 801/869, M2 350/365, M3 414/428 |
| Any slot has an `effect` category | 2,454 (94.4 %) |
| Coverage at other depths (resolve) | depth 1: 44.3 %, depth 2: 84.3 %, depth 4: 92.3 % |
| Functions scanned | about 3,300 |

Resolve-slot categories, as the number of records reaching each: attach_effect 735, special_summon 532, destroy 523, timing_event 490 (meta), select_ui 394 (meta), damage 348, move_list_card 293, gain_lp 282, set_flag 236 (meta), detach_effect 195 (meta), draw 172, position_change 163, banish 159, send_to_graveyard 95, negate 89, return_to_hand 85, return_to_deck 79, optional 76 (meta), send_from_hand 66, tribute 12, set_lp 5, pay_lp 4, place_spell_trap 1.

These figures measure reach, not precision. A category means that some path from the handler, up to the depth, reaches a helper of that kind. A family handler that branches on the card id therefore carries the categories of every card in its family: the LP handler shared by Hinotama-type cards reports both damage and gain_lp. attach_effect is the broadest category, because the attach command `0x35` also carries markers.

### Naming worklist: top 30 unnamed callees

These are ranked by the number of effect records, over any slot, whose closure reaches them. "Resolve" counts the records that reach the callee from the resolve slot. "Depth" is the shallowest level at which the callee appears. Stub addresses (`0x09de4…`) are import stubs, and the name in brackets is the `BOOT.BIN` target.

| Address | Records | Resolve | Depth | | Address | Records | Resolve | Depth |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `0x09de4a24` (`BOOT 0x0885fef0`) | 1493 | 813 | 1 | | `0x09cbf1ac` | 748 | 685 | 1 |
| `0x09bf0afc` | 1197 | 572 | 1 | | `0x09be53bc` | 686 | 661 | 3 |
| `0x09cdcb34` | 995 | 983 | 2 | | `0x09bf0cb4` | 599 | 309 | 1 |
| `0x09cc0dd0` | 995 | 738 | 1 | | `0x09beff3c` | 552 | 320 | 1 |
| `0x09dc6f98` | 981 | 453 | 1 | | `0x09de4d2c` (`BOOT 0x088664fc`) | 549 | 296 | 1 |
| `0x09c02c30` | 953 | 860 | 1 | | `0x09de4a14` (`BOOT 0x0885fb5c`) | 528 | 247 | 1 |
| `0x09bfd3fc` | 925 | 319 | 1 | | `0x09de4d1c` (`BOOT 0x08866398`) | 524 | 296 | 1 |
| `0x09c02d48` | 902 | 856 | 2 | | `0x09bee688` | 522 | 406 | 1 |
| `0x09be8228` | 867 | 595 | 1 | | `0x09c0b8f4` | 489 | 299 | 1 |
| `0x09dcc884` | 858 | 770 | 2 | | `0x09c2bf4c` | 450 | 383 | 1 |
| `0x09be957c` | 848 | 234 | 1 | | `0x09dc9cc8` | 448 | 265 | 1 |
| `0x09de4d84` (`BOOT 0x08866af8`) | 825 | 291 | 1 | | `0x09ce3728` | 446 | 288 | 1 |
| `0x09be83b0` | 809 | 481 | 1 | | `0x09bf8cc8` | 433 | 382 | 1 |
| `0x09de4bfc` (`BOOT 0x088621c4`) | 789 | 217 | 1 | | `0x09c2b6a0` | 431 | 294 | 1 |
| `0x09bef810` | 761 | 700 | 1 | | `0x09bf9c8c` | 425 | 344 | 1 |

In all, 751 unnamed functions are reached. The list measures how widely a helper is used, not how informative its name would be. The top entries are probably shared predicates and getters, which would mostly become `stop` rows. The request functions of the send batch (`0x09c22a98`–`0x09c274a4`) are the most informative to name next: each name adds a precise category, for example "destroy one slot" against "destroy all monsters".

## AI handlers

The same scan grouped the 677 distinct handlers of the AI priority tables: the 674 of the pair tables plus the 3 of the u16 lists in `tools/ai_tables.py`. A cluster is a set of handlers whose closures have the same set of callee names:

- At depth 1, the direct callees: **579 clusters, 540 of them singletons**. The largest are 21 handlers that call nothing (constant predicates such as `ai_cond_always`; 211 table entries), 8 that call only `0x09ce9ad0`, 8 that call only `0x09d6b93c`, 6 that call only `0x09d6d994`, and 5 with an identical set of five calls.
- At depth 2: 574 clusters (531 singletons). At depth 3: 565 (518).

So the AI handlers are **mostly bespoke**: exact callee-set grouping does not reduce the 674 handlers to a few families. Most of them combine a handful of shared queries:

| Callee | Handlers |
| --- | --- |
| `0x09ce96bc` | 140 |
| `ai_get_battle_dominance` | 86 |
| `0x09d8d218` | 71 |
| `ai_choose_target_as_controller` | 64 |
| `0x09bf9c8c` | 61 |
| `duel_core_can_enter_battle_phase` | 61 |
| `0x09ce47a0` | 55 |
| `duel_core_get_atk` | 49 |
| `duel_core_count_active_card_on_side` | 41 |
| `0x09d6b93c` | 41 |

Naming these callees is the useful next step for the AI. A grouping by overlap of the callee sets (Jaccard) rather than identity could follow later.

## Limits

- **Static reach, not behaviour.** The tool neither evaluates branches nor follows per-card compare chains, so a family handler gets the union of its family's categories. Indirect calls (`jalr`, the handler slots themselves) are not followed. The tool only counts them.
- **Depth is a trade-off.** Depth 1 sees only the handler's own calls and stores (44 %). Depth 3 is the default. Deeper levels add little (92.3 % at depth 4) and add noise from shared helpers.
- **Names drive everything.** A wrongly named or wrongly mapped helper propagates to every record that reaches it. The `name` rows are regexes, so a new name that happens to contain `destroy`, `banish`, `search`, … gets that category automatically, which is the intended behaviour but should be checked when names are added. `addr` rows are for hypotheses only and should be removed once the function is named.
- **Bounds come from the registry.** A function ends at the next registry start, so an unregistered function that follows is scanned as part of its predecessor. Ghidra functions with broken 1-byte bodies are scanned correctly, since the size column is ignored.
- **Known-bits limits.** The tool does not model the stack, so values spilled and reloaded are lost, and it does not track memory, so values loaded from globals are unknown. `addiu` and `addu` keep only the contiguous known low bits. A store is recognised only when its base register holds a fully known address.
- **`BOOT.BIN` is not scanned.** Import stubs are named (with `--boot`) but treated as leaves. The AI gates `BOOT 0x0885fef0` and `0x0885fb5c` lead the worklist.
- The VFPU is not modelled: VFPU instructions write no general registers, apart from `mfv`/`mfvc`, which make their target unknown.

## Open questions

- The meaning of the batch mode bits `0x20000`, `0x4000000`, `0x10000000` and `8`, and of the slot-mask global `0x09e2bba4`.
- Commands `0x52`, `0x55` and `0x39`–`0x3a`/`0x41`, which effect handlers reach often (Sangan; Snatch Steal, Premature Burial), are not yet documented.
- Precision per category: a sample of records per category should be checked against the card text to estimate false positives at depth 3.
