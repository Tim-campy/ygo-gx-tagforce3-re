# Effect classification by callee signature (work package 4)

`tools/effect_classify.py` sorts the 2,600 records of the four 24-byte effect tables (`docs/formats/effect-tables.md`) into effect categories (destroy, draw, banish, special summon, damage, …) without Ghidra, from the maintainer's own `rel_duel_eng.prx`. It does not read card text. The categories come from **what the handlers call**, so they depend on the function names in `re/functions.csv`. Each run uses the names current at that moment, and the classification gets better as other work names more helpers. The tool also writes a ranked list of the unnamed helpers that most effect records reach, which is the naming worklist that raises coverage fastest.

```
python3 -I tools/effect_classify.py <USRDIR>/gmodule/rel_duel_eng.prx --check
python3 -I tools/effect_classify.py <USRDIR>/gmodule/rel_duel_eng.prx -o extracted/effect_classify \
        [--cardinfo <USRDIR>/duelsys/cardinfo_eng.ehp] [--boot <SYSDIR>/BOOT.BIN] [--depth 3] [--ai-depth 1] \
        [--no-root-names]
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

   **The handler itself (root).** A slot handler that a `name`/`addr` row matches, for example a named generic resolver such as `duel_effects_resolve_search_deck` (`0x09c7b510`, Reinforcement of the Army) or `duel_effects_resolve_place_tokens`, gets that row's category too, and it is still scanned like any other handler (a root is never a leaf). `--no-root-names` (`Classifier(root_names=False)`) turns this off for comparison. On the registry of this commit the rule adds categories to 52 records and no coverage: `token` 36 (Scapegoat, Multiply, Ojama Trio: their handlers call the summon routine directly), `change_effect` 7, `send_to_graveyard` 5 (Foolish Burial, Armageddon Knight), `change_target` 3, `destroy` 1. The rule also makes loose regexes visible: `add_.*to_hand|resolve_add_` gave `add_to_hand` to the 31 records of `duel_effects_resolve_add_player_marker` (Waboku, Cost Down, Super Rejuvenation) and to `duel_effects_resolve_add_spell_counter`; the row is now `add_.*(to_hand|from_deck)`.

   **Callbacks.** When a descended (unmatched) callee is passed a function pointer, that is an argument register holding a fully known value >= `0x10000` whose runtime address (module base + value; the PRX relocates the `lui`/`addiu` pair) is a registry function start, the pointed function is visited one level deeper as if that callee called it. Example: Life Absorbing Machine's resolve handler `0x09c8ca84` calls the player-marker iterator `0x09be9bd4` with the callback `0x09c8ca28`, which calls `duel_core_gain_lp`. Callbacks handed to leaves (the filter predicates of the zone scanners and of `duel_core_begin_select_*`, about 470 call sites) are not followed: they are tests, not actions. Six call sites in the scanned code pass a callback to a descended callee.
7. **Mapping rows.** The mapping file is CSV with `#` comments and seven kinds of row:
   - `name`: a regex searched in the callee's name, with a leading `thunk_` removed. The first matching `name`/`addr` row decides.
   - `addr`: an exact address.
   - `queue`: the role given to `duel_core_push_command`. At each call, the low 12 bits of `a0`, when known, are the command code.
   - `cmd`: command code → category.
   - `arg`: a callee regex plus one or more space-separated conditions on the argument registers `a0`-`a7` at the call: `a3&0x1000` (the mask bits are known and set), `a3!&0x1002` (known and clear) or `a2=0xe` (the whole register is known and equal). The generic send requests `duel_core_request_send_mask(ctx, mask, dest, flags)` and its `by_card` forms are read this way (destination in `a2`, flags in `a3`; `duel_core_request_send_slot_to_side` has the destination in `t0` = `a4`), with the meanings of the `store` rows below. Icarus Attack, Mobius the Frost Monarch, Nobleman-Eater Bug and Celestia (all through `0x09c74548`: destination `0x0e`, flags `0x10000002`) get `destroy`; Rivalry of Warlords and Gozen Match (destination `0x0e`, flags `0x10000`) get `send_to_graveyard`. The single-condition form is also how the target-filter flag word, already decoded in `effect-tables.md`, is reused: `0x1000` destroy, `0x2000` banish, `0x4000` send to graveyard, `0x10000` take control, `0x40000` change position, `0x80000` return, `0x400` targets.
   - `store`: conditions such as `0x09e2d2b8=0x0f` or `0x09e2d2bc&0x2` that must all hold for the constant stores of one scanned function. Besides the send batch below, store rows read the **pending-action request** (`0x09e2d2e0 = 1` active, kind in `0x09e2d2e8`; `effect-helpers-deck.md`, `-values.md`): kinds 1-3 `discard`, 4 `send_from_hand`, 5 `banish`, `0x0b` `control_change`, `0x11` `battle`. The named setters are leaves already; the rows catch unnamed ones such as `0x09c0f18c` (kind 2: Worm Hope, Criosphinx, Arcana Force III - The Empress).
   - `dispatch`: a callee regex and, in the category column, the address of an 8-byte `(card id, handler)` list. When a slot's closure reaches a matching callee, the record's own handler in that list is classified as well and its categories are added to the slot. The row for `duel_effects_build_candidate_list` and its relatives points at the candidate-builder list `0x09dec554`. Together with the five scanner `name` rows, it gives the categories `search_deck`, `search_extra`, `search_hand`, `search_graveyard` and `search_banished`. With these rows, 435 records have a `search_*` category in the resolve slot and 601 in any slot. Resolve coverage rises from 2,498 to 2,500 of 2,600 (`docs/formats/search-filters.md`).

   `cmd`, `arg` and `store` rows add to whatever the `name`/`addr` row decided and never change whether a callee is a leaf. Roles:
   - `effect`: counts for coverage;
   - `meta`: recorded but not counted (`once_per_turn`, `optional`, `choose_targets`, `timing_event`, `set_flag`, `select_ui`, `detach_effect`, `targets`, `reveal`, `set_value`).

### Categories and rows added in the precision round

Each new category rests on a command whose handler was located in the jump table of `duel_core_execute_command` (`0x09e00944`; the entry for code *c* leads to a case that calls the handler), or on a named helper:

| Category | Source | Basis | Records (resolve) | Examples |
| --- | --- | --- | --- | --- |
| `declare_attack` | commands `0x17`/`0x18` | `duel_core_cmd_declare_attack` / `_declare_direct_attack` (`battle.md`): an effect starts, forces or redirects an attack | 19 | Jam Defender, Defense Maiden, Dreamsprite, Mirror Gate, Super Junior Confrontation, Confusion Chaff |
| `battle` (existing) | `duel_core_request_effect_battle`, pending kind `0x11` | `battle.md` | 14 | as above |
| `change_phase` | command `0x1a` | `duel_core_set_phase` (`duel-phases.md`) | 11 | Negate Attack, The Unhappy Maiden, Cyber Valley, D - Fortune (all end the Battle Phase) |
| `negate_attack` | command `0x1f` | `duel_core_cmd_negate_attack` (`battle.md`) | 14 | Magic Cylinder, Draining Shield, Necro Gardna, Kid Guard |
| `move_zone` | command `0x3c` | a slot moved to an empty slot (`duel_core.md`); control changes go through leaves named `take_control` | 4 | Rampaging Rhynos, Senet Switch, Alien Infiltrator |
| `control_change` (existing) | command `0x3d`, `duel_effects_swap_control` | two occupied slots swapped (`duel_core.md`) | +7 | Creature Swap, Creature Seizure, Mirror Gate |
| `place_on_field` | command `0x40`, `duel_core_post_place_list_card_on_field` | a list card put in a field slot without a summon (`duel_core.md`) | 42 | Dimensionhole, Different Dimension Gate, Destiny Board, Crystal Blessing |
| `shuffle_field` | command `0x48` | handler `0x09dbea78` permutes field slots with `duel_core_random` and moves their markers (`0x09be7908`); M | 6 | Shifting Shadows, Magical Hats, Wandering Mummy |
| `deck_order` | command `0x58` | a Deck card put on top (`effect-helpers-deck.md`) | 19 | Big Eye, Pigeonholing Books of Spell, A Cat of Ill Omen, Blizzard Warrior |
| `normal_summon` | `duel_core_begin/init_summon_from_hand`, `duel_core_action/init_gemini_summon` | the player's summon routine run by an effect (`summon.md`) | 6 | Ultimate Offering, Mausoleum of the Emperor, Cry Havoc!, Gemini Summoner |
| `change_effect` | `addr` row `0x09ca2924` | sets bit 0 of byte `+6` of the other link, the copied-effect flag (`chain.md`): the chained effect resolves as another card's; M | 7 | Mystical Refpanel, Spell of Pain, Ring of Defense, Dark Deal, Energy-Absorbing Monolith |
| `state_effect:<kind>` (schema 7) | root `addr` rows of five slot handlers | the handler's whole effect is a state it writes (declared Type or Attribute, turn countdown, skip-draw flag, hand-public state) whose reader in a named rule function was traced; kinds and readers in `card-effect-spec.md`, "State-effect categories"; H (hand reveal M) | 11 | Declaration of Rebirth, DNA Surgery, Time Seal, Hourglass of Courage, The Eye of Truth |
| `change_target` | `addr` row `0x09c821b8` | copies the own link's target word `+8` into the other link; M | 4 | Fairy's Hand Mirror, Fiend's Hand Mirror, Remote Revenge, Shift |
| `set_value` (meta) | command `0x39` | `duel_core_cmd_set_slot_value` (`effect-helpers-values.md`) | 64 | Hourglass of Courage, Metalmorph, Snatch Steal |
| `reveal` (meta) | command `0x53`, `duel_core_post_set_hand_reveal` | hand reveal state | +14 | The Eye of Truth, Crush Card Virus |

Hygiene rows: the UI text, link-duel transport, timing-batch and statistics helpers (`duel_core_show_hint`, `duel_core_net_send_*`, `duel_core_timing_batch_*`, `duel_core_append_*`, `duel_core_format_text_*`, `duel_core_add_statistic`) and the link bookkeeping (`duel_effects_link_refresh_location`, `_collect_target_mask`, `_collect_slot_mask`, `_record_link_slot`) are `stop` leaves. `duel_effects_add_link_target` is a `choose_targets` meta leaf: it posts a Spirit Reaper marker (`0x35`), which put `attach_effect` into the target-choice slot of 223 records. `duel_effects_link_target_is_valid` and `duel_effects_target_still_matches_filter` are deliberately **not** stopped: they re-run the zone scanner of the target, and stopping them removed 83 correct `search_graveyard` hits (Gravedigger Ghoul, Backup Soldier, Salvage) and 12 correct `search_deck` hits (Gladiator Beasts, Test Tiger).

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

**After the helper-naming round** (names from `effect-helpers-movement.md`, `effect-helpers-deck.md`, `effect-helpers-values.md`, plus their mapping rows in `tools/effect_categories.csv`): resolve coverage **2,498 = 96.1 %** of all records (97.5 % of those with a resolve handler); any slot 97.3 %. The figures above are the first run, kept for comparison. Known imprecisions found by spot checks: Scapegoat reaches `special_summon` but not `token` (its handler calls the summon routine directly); searches implemented as a list move (Reinforcement of the Army, Foolish Burial) only got `move_list_card`, because the search builders of `0x09dec554` are data driven and their filter word is not yet mapped to a category.
(Both were fixed later: the dispatch rows give the searches, the root-name rule gives Scapegoat `token`.)

**After the precision round** (the rows and rules of "Categories and rows added in the precision round", the callback rule and the tightened `add_to_hand` row): resolve coverage **2,550 = 98.1 %** of all records (99.5 % of the 2,562 with a resolve handler; before: 2,500 = 96.2 %); any slot **2,559 = 98.4 %** (before 2,530). Per table S/T 896/938, M1 861/869, M2 365/365, M3 428/428. In `tools/card_effects.py` the records with no effect category in any slot fell from 71 to 41 and the released cards whose spec is `full` rose from 1,677 to 1,754.

### Records without a resolve category (50)

| Class | Records | Why no category | Examples |
| --- | --- | --- | --- |
| No resolve handler | 38 | The record has only a condition or activation handler. 14 of them use the condition `0x09ce28dc` (`return 0`: never activatable by the player); the card works through rule code that tests its id elsewhere (destruction triggers, Destiny Board's placement, continuous effects). The others are continuous cards whose effect lives in rule checks (Toon World, Toon Kingdom, Appropriate, Narrow Pass, Talisman of Spell/Trap Sealing, Field Barrier, DNA Surgery) | Spirit Message "I", The Second Sarcophagus, Statue of the Wicked, Kozaky's Self-Destruct Button, The Sky Lord |
| Empty handler | 3 | `0x09c7eb14` is `jr ra; move v0,zero`: the negation is a rule check keyed by card id | Royal Decree, Imperial Order, The Emperor's Holiday |
| Flag only | 3 | Only `duel_core_post_set_player_flag(side, 0, 1)` or `duel_core_post_set_slot_flag(.., 8, ..)` (`set_flag` meta); the flag's consumer is elsewhere | Time Seal, Fenrir, Skill Drain |
| Information only | 5 | Only `reveal`/`select_ui` (look at cards; `0x53` hand reveal, card-list display `0x07`) | The Inexperienced Spy, Ancient Telescope, Senri Eye, The Eye of Truth, Cyber Esper |
| Value only | 1 | Only `duel_core_post_set_slot_value` (`set_value` meta): the stat change is computed elsewhere from the slot value | Hourglass of Courage |

### Precision spot check (depth 3, this commit)

44 resolve records were drawn at random, two from each of the 22 most frequent effect categories (seed 7), and every effect category of each record was compared with the card's effect as known from public card knowledge (two records with an uncertain reading were left out). Results as correct / assigned labels:

| Category | Precision | Category | Precision |
| --- | --- | --- | --- |
| special_summon | 12/12 | attach_effect | 9/9 |
| damage | 5/5 | equip | 5/5 |
| search_deck | 8/9 | shuffle | 8/9 |
| destroy | 6/8 | banish | 4/5 |
| search_hand | 3/3 | negate | 3/3 |
| draw | 3/4 | mill | 3/4 |
| add_to_hand | 2/2 | atk_change | 2/2 |
| discard | 2/3 | place_on_field | 2/2 |
| search_graveyard | 3/5 | return_to_deck | 1/2 |
| send_to_graveyard | 2/5 | return_to_hand | 1/2 |
| position_change | 1/4 | gain_lp | 0/4 |
| control_change | 0/5 | | |

Overall 86 of 113 labels are correct (76 %); 25 of 42 records carry no wrong label, and every record has at least one correct label. The false positives have three causes, none of them depth:

1. **Family-shared handlers (most of them).** `duel_effects_resolve_lp_change` (217 records) calls both `duel_core_inflict_damage` and `duel_core_gain_lp` at depth 1, so every burn card also gets `gain_lp` and every heal card `damage`; per-card sign data exists in `duel_effects_get_lp_change_amounts`. `duel_effects_resolve_equip_to_target` (19 records) reaches `duel_core_request_take_control` for Snatch Steal, so every equip spell gets `control_change`; the union handler `0x09c91cd0` (17 records) likewise. The fusion-spell handler (11 records: Dark Fusion with Miracle Fusion, De-Fusion …) carries `banish`, `mill`, `return_to_deck`, `search_graveyard`. The flip-effect families add `position_change` (Reaper of the Cards).
2. **Loose name rows**, made visible by the root-name rule (the old `resolve_add_` row, fixed in this round).
3. **Implementation detail versus card text**: Seal of the Ancients shows face-down cards with the face command `0x34` (`position_change`); the union "destroy instead" substitution reads as `destroy`.

Because the wrong categories of the families appear at depth 1, a per-category depth limit (`--depth-per-category`) would not remove them and was not added. The useful next step was per-card branch reading inside the family handlers, which `tools/family_split.py` now does (next section).

**After the family split.** The 44 records of the sample above were not recorded, so the 76 % cannot be re-measured exactly. Two figures replace it:

- A new sample of family records: 50 records drawn at random (seed 7) from the 915 records that `tools/family_split.py` examines, 47 of them judged (three uncertain readings left out; one card has two records with the same handler, so 48 records count). Same leniency as above for implementation labels. Before the split **113 of 136 labels are correct (83 %)**; after it **111 of 116 (96 %)**. The split removed 22 wrong labels and 2 labels judged correct (Gadget Hauler and Fiend Roar Deity Raven share a handler whose two branches call the discard and the send-from-hand helpers respectively; the judgment counted both labels for both cards). The judged sample is built into the tool (`family_split.SAMPLE`, card ids and categories only) and `--check` prints the figure.
- An estimate for the whole-table sample: its family false positives were `gain_lp` 4, `control_change` 5 and about 3 of the `position_change`, fusion and union labels, all of the kinds the split removes. Without them the 86 correct labels of 113 become about 86 of 101, **about 85 %** (estimate, not a measurement).

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

## Per-card split of family handlers (`tools/family_split.py`)

```
python3 -I tools/family_split.py <USRDIR>/gmodule/rel_duel_eng.prx --check
python3 -I tools/family_split.py <USRDIR>/gmodule/rel_duel_eng.prx -o extracted/family_split [--cardinfo <cardinfo_eng.ehp>]
python3 -I tools/tests/test_family_split.py
```

A family handler chooses the per-card behaviour by testing the card id, the `u16` at `+0` of the chain link it receives in `a0` (`chain.md`). Ghidra shows the pattern in every family read for this round: `duel_effects_resolve_equip_to_target` calls `duel_core_request_take_control` only when `*link` is Snatch Steal, Falling Down or `0x1edf`; `duel_effects_resolve_union_equip` only for `0x1877`; `duel_effects_resolve_fusion_summon` picks the material destination (Deck `0x0d`, banished `0x0f`, Graveyard `0x0e`) from an `if` chain on the id. The tool therefore re-runs the closure of `effect_classify` once per card, with the card id known. It imports `effect_classify` and `effect_params` and changes neither.

Method (pure Python on the module bytes, no Ghidra):

1. **Specialised scan.** The known-bits dataflow of `effect_classify` (same transfer functions) runs path-sensitively: up to 8 distinct register states per address before they are merged. It also tracks the registers and stack slots that hold the link pointer (`a0` at entry, register moves, `sw`/`lw` to the stack). `lhu`/`lh r, 0(link)` gives the constant card id. A branch that the known bits decide (`beq`/`bne` with a known differing bit or equal constants, sign tests, `slt`-family results of constants) keeps one side only. `duel_core_get_effective_card_id(link)` returns 0: it returns the copying card only when the copied-effect flag (byte `+6` bit 0) is set, and that is not the normal case.
2. **Jump tables.** `sltiu; lui; addu; lw; jr` sequences are followed to the case of a known index, else to all cases. An unrecognised computed jump falls back to `effect_classify`'s scan of the unreached code (flag `fallback`; it did not occur on the disc).
3. **Callees.** A callee receives the known bits of its arguments and the link registers, so a card-id test inside a callee also selects (`effect_classify` scans every callee from an all-unknown state).
4. **Temporary reveal.** When one scanned function calls `duel_core_post_set_face` with `a2 = 1` and with `a2 = 0`, the pair turns a face-down card up and down again to test it. Those calls give the meta label `reveal` instead of `position_change` (`duel_effects_resolve_reveal_and_destroy_target`: Reaper of the Cards, Trap Master, Armed Ninja, Crimson Ninja, De-Spell).
5. **LP chain decode.** `duel_effects_resolve_lp_change` is replaced by a decode of `duel_effects_get_lp_change_amounts(link, out[2])` for the card. A small abstract interpreter follows the card's case with these values: intervals; `a·C + b`, with C the controller (link byte `+2` bit 0, XORed with the switched-control bit); linear forms `a·X + b` of one unknown, so that multiplication by shifts and adds stays exact (`count × −200`); pointers into `out`. Call results and loaded words are taken as non-negative (counts, Levels, ATK/DEF, stored amounts). Every store to `out[]` gives a side (`self` = `out[C]`, `opponent` = `out[1 − C]`, `player0`/`player1`, `either` for a target's controller) and a sign: negative → `damage`, positive → `gain_lp`, unknown sign → both. The amounts are constant for 142 records (confidence high), and computed for the other 100 (medium).

Rules for the result: the refined set is a subset of the original one, except that the LP decode may add the LP category that the depth limit hid (12 records, for example Spirit of the Breeze, Dancing Fairy, Cure Mermaid, Marie the Fallen One, Chain Healing and Brain Jacker's gift of LP to the opponent: their wrappers reach `duel_core_inflict_damage` within the depth but not `duel_core_gain_lp`). A record never ends with no category. Confidence of a refinement: high for an exact LP decode, or for a handler whose closure reads the card id without falling back on an unresolved jump; medium otherwise (`unchanged`: the closure never reads the card id through the link, so its categories depend on run-time state, not on the card).

Scope: every resolve handler shared by at least two cards with at least two effect categories, plus every resolve handler whose closure reaches `duel_effects_resolve_lp_change` (12 single-card wrappers). On the disc, registry of this commit:

| Measure | Value |
| --- | --- |
| Resolve handlers examined | 119 (107 shared with ≥ 2 categories, 12 single-card LP wrappers) |
| Records examined | 915: `branch` 547, `lp_chain` 242, `unchanged` 126 |
| Records refined | 398; 431 labels removed, 12 LP labels added (2,523 → 2,104 labels on these records) |
| Labels removed by category | `gain_lp` 172, `damage` 74, `position_change` 37, `attach_effect` 35, `control_change` 34, `return_to_deck` 16, `atk_change` 16, `draw` 9, `send_to_graveyard` 7, `return_to_hand` 7, `add_to_hand` 6, `shuffle` 5, `destroy` 4, others 10 |
| LP family (`duel_effects_resolve_lp_change`, 217 records) | 201 refined. Over the 242 records that reach the LP handler: `damage` only 157 (opponent: Ookazi −800, Hinotama −500; self: Ameba −2000, Lava Golem −1000), `gain_lp` only 58 (Dian Keto, Nutrient Z; to the opponent: Snatch Steal, Griggle, Gift Card, The Eye of Truth), both 18 (Goblin Thief, Jenis, Poison of the Old Man, Neos Wiseman, Granadora: both are real; Chain Strike, Restructer Revolution, Balloon Lizard: sign of a computed amount not determined) |
| Equip family (`duel_effects_resolve_equip_to_target`, 20) | 17 lose `control_change`; Snatch Steal, Falling Down and Mark of the Rose keep it |
| Union family (`duel_effects_resolve_union_equip`, 18) | 17 lose `control_change`; Brain Jacker keeps it |
| Fusion family (`duel_effects_resolve_fusion_summon`, 12) | 12 refined. `position_change` and `return_to_deck` remain only for Cyberdark Impact! (`0x1c31`, materials shuffled into the Deck), which loses `send_to_graveyard`; the banishing spells (Fusion Gate, Miracle Fusion, Dragon's Mirror, Overload Fusion, Dark Calling) lose `send_to_graveyard`, `position_change` and `return_to_deck`; Polymerization, Power Bond, Dark Fusion, Super Polymerization and Vehicroid Connection Zone lose `position_change` and `return_to_deck` |
| Others | Neos family `duel_effects_resolve_return_self_to_extra_deck`: 8 of 9 lose `position_change` (Chaos Neos keeps it); `duel_effects_resolve_change_position_all`: 12 of 13 lose `atk_change`; `duel_effects_resolve_destroy_all_lp_per_card`: gain or damage per card; `duel_effects_resolve_negate_then_per_card`: draw or destroy per card |
| Run time | about 3 s |

Remaining unions, with their cause:

- **State set in another step.** The fusion handler is a step machine. Its material destination is banished whenever the step-0x7f code has set `0x09e2905c = 8`, which happens when a field effect `0x1d2a` is active. The specialised scan does not track memory, so every fusion spell keeps `banish` and `mill`. The same holds for the union handler's steps: equip, Special Summon back, and the destroy substitution all stay, which is correct for every union card.
- **Run-time branches.** Branches on targets, zones or choices are not decided. A choice between two outcomes therefore keeps both (Poison of the Old Man; the `if` of a card that may either gain or inflict).
- **Link read elsewhere.** 126 records read the card id through no link register that the scan sees (or not at all): `duel_effects_resolve_search_deck`, `_special_summon_from_deck`, `_summon_tokens` and the attach families are data driven (lists, tables) and stay unchanged.
- **Sign of computed LP amounts** for 12 LP records (unknown products and differences, values loaded as signed halfwords): they keep both `damage` and `gain_lp`.

`tools/card_effects.py` uses the result (schema 3, `docs/formats/card-effect-spec.md`): `categories_refined` and `refinement` on the resolve slot, and a shared resolve handler no longer lowers a record's confidence when its split is high. Effect records with confidence high rose from 604 to 1,289.

### Family handlers named in this round

Named from Ghidra decompilations of a read-only project copy (`FuncAt`: all six start a function), appended to `re/names-duel_eng.csv`:

| Address | Name | Evidence | Conf. |
| --- | --- | --- | --- |
| `0x09c7b97c` | `duel_effects_resolve_reveal_and_destroy_target` | Turns a face-down target face-up (`duel_core_post_set_face(side, slot, 1)`), runs its slot `+08` filter, destroys it on success (`duel_core_request_destroy_target_slot`), turns it face-down again. 5 records (Reaper of the Cards, Trap Master, Armed Ninja, Crimson Ninja, De-Spell) | H |
| `0x09c8bf74` | `duel_effects_resolve_destroy_all_lp_per_card` | Step `0x80`: builds the destroy mask per card id (every card, spells only, monsters only, non-monsters) and destroys it. Step `0x7f`: counts the destroyed cards, then gains 800 or 500 per card, or inflicts 500, 300 or 100 per card on the opponent | H |
| `0x09c85c90` | `duel_effects_resolve_destroy_target_burn` | Destroys the target (`duel_effects_resolve_destroy_target_b`), then inflicts 1000, or the target's ATK, on the opponent and/or the controller; `0x1e51` gains instead (Ring of Destruction, Destruction Ring, Detonator Circle "A", Telepathic Power) | H |
| `0x09c81240` | `duel_effects_resolve_negate_then_per_card` | Unless the chained link cannot be negated, sets its negated bit (link `+4`) and then per card: draws 1 (`0x162a`), destroys the targets or a fixed mask (`0x131c`, `0x12f7`, `0x12f5`), or only shows the negation | H |
| `0x09c89840` | `duel_effects_resolve_return_graveyard_card` | Builds the candidate list, then sends the selected Graveyard card to the hand (The Forgiving Maiden) or back to the Deck (`0x1452`, `0x144c`, `0x1449` with a top/bottom flag); outside selector 2 it only adds a player marker | M |
| `0x09c82b70` | `duel_effects_resolve_special_summon_named_from_deck` | Asks yes/no, then Special Summons a copy of the card itself from the Deck (`duel_core_find_deck_card_by_name`), possibly to the opponent's field (`0x1dee`). Step `0x80` gains 1000 (`0x133a`) or inflicts 500 (`0x1dee`, `0x1339`) | H |

`re/functions.csv` is owned by another work package in this round. These names reach `effect_classify` once that registry picks them up from `names-duel_eng.csv`.

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

- **Static reach, not behaviour.** The tool neither evaluates branches nor follows per-card compare chains, so a family handler gets the union of its family's categories. `tools/family_split.py` refines the resolve slot of the family records per card (section above); `effect_classes.csv` itself stays the union. Indirect calls (`jalr`, the handler slots themselves) are not followed. The tool only counts them.
- **Depth is a trade-off.** Depth 1 sees only the handler's own calls and stores (44 %). Depth 3 is the default. Deeper levels add little (92.3 % at depth 4) and add noise from shared helpers.
- **Names drive everything.** A wrongly named or wrongly mapped helper propagates to every record that reaches it. The `name` rows are regexes, so a new name that happens to contain `destroy`, `banish`, `search`, … gets that category automatically, which is the intended behaviour but should be checked when names are added. `addr` rows are for hypotheses only and should be removed once the function is named.
- **Bounds come from the registry.** A function ends at the next registry start, so an unregistered function that follows is scanned as part of its predecessor. Ghidra functions with broken 1-byte bodies are scanned correctly, since the size column is ignored.
- **Known-bits limits.** The tool does not model the stack, so values spilled and reloaded are lost, and it does not track memory, so values loaded from globals are unknown. `addiu` and `addu` keep only the contiguous known low bits. A store is recognised only when its base register holds a fully known address.
- **`BOOT.BIN` is not scanned.** Import stubs are named (with `--boot`) but treated as leaves. The AI gates `BOOT 0x0885fef0` and `0x0885fb5c` lead the worklist.
- The VFPU is not modelled: VFPU instructions write no general registers, apart from `mfv`/`mfvc`, which make their target unknown.

## Open questions

- The meaning of the batch mode bits `0x20000`, `0x4000000`, `0x10000000` and `8`, and of the slot-mask global `0x09e2bba4`.
- Commands `0x52`, `0x55` and `0x39`–`0x3a`/`0x41`, which effect handlers reach often (Sangan; Snatch Steal, Premature Burial), are not yet documented.
- Per-card resolution inside family handlers is done by `tools/family_split.py` for the resolve slot. Left open: state carried between the steps of a step-machine handler (the fusion mode `0x09e2905c`), the other four slots, and the sign of 12 computed LP amounts.
- Player flag bit 0 (Time Seal, Fenrir) and slot flag 8 (Skill Drain): their meanings would turn these flag-only records into categories.
- Commands `0x07` and `0x08` (UI-only handlers `0x09dbc66c`, `0x09dbc6d8`) are reached by 15 and 42 records (Crush Card Virus, Painful Choice); they look like card-list displays and are left unmapped.
