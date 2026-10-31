# Duel engine runtime structures

Layouts of the global data structures of the duel engine `gmodule/rel_duel_eng.prx` (runtime base `0x09be1400`; a module offset is `address − 0x09be1400`). These are runtime state and module tables, not files; the port needs them to reproduce the engine's state model. The prose that explains how the engine uses them is in [`duel_core.md`](../subsystems/duel_core.md), [`chain.md`](../subsystems/chain.md), [`battle.md`](../subsystems/battle.md), [`duel-phases.md`](../subsystems/duel-phases.md), [`summon.md`](../subsystems/summon.md), [`stat-modifiers.md`](../subsystems/stat-modifiers.md), [`effect-helpers-movement.md`](../subsystems/effect-helpers-movement.md) and [`tag_duel.md`](../subsystems/tag_duel.md). The player block and the field slot (`0x09e2a528 + side × 0xb3c`) are in `duel_core.md`, "Player state"; the chain link in `chain.md`.

All values are little-endian. Sizes are in bytes.

**Basis.** The function summaries of `re/documented-duel_eng.tsv` (decompiled in Ghidra during the 2026-10-31 documentation round), the subsystem documents above, and, for the gaps closed in this document, a capstone disassembly of `rel_duel_eng.prx` and `BOOT.BIN` (access widths and offsets of every `lui`/`lw`/`sw` pair that addresses a structure; table contents read from the module's data, pointers relocated by adding the base). Confidence per field: **H** high (the code that reads and writes the field was read), **M** medium (inferred from a consistent pattern or one reader), **L** low.

Row keys refer to `re/formats.csv`.

## Contents

| Row | Address | Size | Section |
| --- | --- | --- | --- |
| `duel_setup_params` | `0x09e02990`–`0x09e02cb7` | 0x328 | [Duel set-up parameters](#duel-set-up-parameters-duel_setup_params) |
| `tag_waiting_area` | `0x09e02cb8`–`0x09e02f1f` | 0x268 | [Tag partner waiting area](#tag-partner-waiting-area-tag_waiting_area) |
| `phase_override_stack` | `0x09e27fe4`–`0x09e27fed` | 10 | [Phase override stack](#phase-override-stack-phase_override_stack) |
| `battle_damage_record` | `0x09e286e0`–`0x09e28707` | 2 × 20 | [Battle damage records](#battle-damage-records-battle_damage_record) |
| `chain_extra_targets` | `0x09e28e50`–`0x09e28f4f` | 256 | [Chain extra-target ring](#chain-extra-target-ring-chain_extra_targets) |
| `timing_event_queue` | `0x09e28f90`–`0x09e2903f` | 160 + 16 | [Timing event queue](#timing-event-queue-timing_event_queue) |
| `summon_material_state` | `0x09e29050`–`0x09e2907f` | 48 | [Fusion and Synchro material state](#fusion-and-synchro-material-state-summon_material_state) |
| `duel_command_queue` | `0x09e290f8`–`0x09e2990b` | 0x814 | [Engine command queue](#engine-command-queue-duel_command_queue) |
| `duel_card_instance` | `0x09e2bbcc`–`0x09e2c7cb` | 0xc00 | [Card instance table](#card-instance-table-duel_card_instance) |
| `duel_card_list_entry` | player block lists | 4 | [Card list entry](#card-list-entry-duel_card_list_entry) |
| `duel_effect_records`, `effect_marker` | `0x09e2c7cc`–`0x09e2cdcb` | 256 × 10 | [Effect records and markers](#effect-records-and-markers-duel_effect_records-effect_marker) |
| `player_input_state` | `0x09e2d248`–`0x09e2d297` | 80 | [Player input state](#player-input-state-player_input_state) |
| `send_batch_request` | `0x09e2d298`–`0x09e2d2bf` (+ masks `0x09e2bba4`–`0x09e2bbc3`) | 40 | [Send-batch request](#send-batch-request-send_batch_request) |
| `prompt_request_block` | `0x09e2d2c0`–`0x09e2d2db` | 28 | [Prompt request block](#prompt-request-block-prompt_request_block) |
| `duel_command_dispatch` | `0x09e00944` (module `+0x21f544`) | 420 | [Engine command jump table](#engine-command-jump-table-duel_command_dispatch) |
| `list_activation_table` | `0x09e00dbc` (`+0x21f9bc`) | 23 × 16 | [List activation table](#list-activation-table-list_activation_table) |
| `battle_end_checks` | `0x09e00f5c` (`+0x21fb5c`) | 31 × 8 | [Check tables](#end-phase-and-battle-end-check-tables-end_phase_checks-battle_end_checks) |
| `end_phase_checks` | `0x09e014f4` (`+0x2200f4`) | 8 × 8 | [Check tables](#end-phase-and-battle-end-check-tables-end_phase_checks-battle_end_checks) |
| `zone_preference_tables` | `0x09deba0c`, `0x09deba20` (`+0x20a60c`, `+0x20a620`) | 2 × 20 | [Free-zone preference tables](#free-zone-preference-tables-zone_preference_tables) |

`duel_core_reset` (`0x09dc7cb0`) zeroes `0x09e2a528` × `0x2de4` (player blocks, card instance table, effect pool, input state, send batch and prompt block, up to `0x09e2d30c`), `0x09e02ff8` × `0x25628` (AI state up to `0x09e28620`, including the phase override stack) and nine smaller regions (not itemised here). The set-up parameters, the tag waiting area and the module tables are not cleared by it.

---

## Duel set-up parameters (`duel_setup_params`)

Written by the duel manager (`rel_duel_mgr`, `duel_core_setup_engine_for_duel`) and the tutorial's `.ydq` loader through the exported setters at `0x09be14e4`–`0x09be19bc`, before one of the start functions (`duel_core_start_plain`, `_mode2`, `_mode3`, `tag_duel_start_with_partner_decks`) runs. Read by the common start `0x09dc7dc4`. Not cleared by `duel_core_reset`.

| Address | Size | Type | Field | Evidence | Conf. |
| --- | --- | --- | --- | --- | --- |
| `0x09e02990` | 4 | `u32` | Duel RNG seed; copied to the generator state `0x09e2d1cc` at duel start | `duel_core_set_rng_seed`/`_get_rng_seed`; `0x09dc7dc4`; `ai.md` | H |
| `0x09e02994` | 4 | `u32` | Local side (this console's side); bit 0 used | `duel_core_set_local_side`, `duel_core_is_local_side` | H |
| `0x09e02998` | 8 | `u32[2]` | Active duelist kind per side: 0 human, 1 CPU, 2 remote; the value 3 in side 0's word = replay/demo (no command is queued) | `duel_core_set_duelist_kind`, `duel_core_is_duelist_*`, `duel_core_push_command`; PPSSPP session B | H (0/1), M (2/3) |
| `0x09e029a0` | 8 | `u32[2]` | Kind of the waiting tag partner per side; swapped with the active word at each tag swap | `tag_duel_swap_active_duelist`; PPSSPP session B | H |
| `0x09e029a8` | 4 | `u32` | First player (side that takes turn 1); copied to `0x09e2d1d8` | `duel_core_set_first_player`; `0x09dc7dc4` | H |
| `0x09e029ac` | 0x300 | deck`[4]` | Four in-memory deck structures of 0xc0 bytes (`deck.md`), indexed by duelist 0–3; a tag duel loads 2 and 3 into the sides | `duel_core_get_duelist_deck`/`_set_duelist_deck`, `tag_duel_start_with_partner_decks` | H |
| `0x09e02cac` | 4 | `u32` | Duel rule/LP mode: 1 → 1,000 LP, 2 → 2,000, 3 → 4,000, other → 8,000; 6 forbids setting cards, 7 forbids Tributes, 8 forbids position changes, 9 forbids attacks | `0x09dc7dc4`; `duel_core_can_set_face_down`, `duel_core_is_tribute_allowed`, `duel_core_can_change_position`, `duel_core_can_monster_attack` | H (LP values), M (6–9 as special rule duels) |
| `0x09e02cb0` | 4 | `u32` | Extra duel result word (set by the duel manager and the end-of-duel driver) | `duel_core_set_duel_result_extra`/`_get`; `duel-phases.md` | M (meaning unknown) |
| `0x09e02cb4` | 4 | `u32` | Duel result copied out at the end of the duel | `duel_core_set_duel_result`/`_get`, command 5 handler `0x09dbbf38` | H |

## Tag partner waiting area (`tag_waiting_area`)

Base `0x09e02cb8`: a 16-byte header followed by one 300-byte area per side at `0x09e02cc8 + side × 300`. Filled by `duel_core_load_deck` (`0x09bf1f74`) and the `.ydq` loader (`tutorial.md`), exchanged with the side's hand, deck and Extra Deck lists by `tag_duel_swap_active_duelist` (`0x09bf21e4`) at every turn change of a tag duel (`tag_duel.md`).

| Offset | Size | Type | Field | Evidence | Conf. |
| --- | --- | --- | --- | --- | --- |
| `+0x00` | 8 | `u32[2]` | Swap toggle per side: 0 = duelist `side` active, 1 = duelist `side + 2` active | `tag_duel_swap_active_duelist`, `tag_duel_get_active_duelist`, `tag_duel_is_duelist_active` | H |
| `+0x08` | 8 | `u32[2]` | First card-instance serial of the waiting partner's cards, per side (player block `+0x08` + 1 at load time); used to tell which duelist owns a card | `duel_core_load_deck`; `tag_duel_get_card_owner_duelist` | M |
| `+0x10 + s × 300` | 300 | area | Waiting area of side `s`: | | |
| area `+0x00` | 2 | `u16` | Hand count (5 after loading) | `duel_core_load_deck`; PPSSPP session B (low half of the logged word) | H |
| area `+0x02` | 2 | `u16` | Deck count (main count − 5 after loading) | same | H |
| area `+0x04` | 2 | `u16` | Extra Deck count (15 or 0 in session B) | same | H |
| area `+0x06` | 294 | `u16[147]` | Card references (instance numbers, 9 bits) in list order: hand, then deck, then Extra Deck. The deck part is shuffled by `duel_core_load_deck` (Fisher–Yates with `duel_core_random`) | `duel_core_load_deck`, `tag_duel_swap_active_duelist` | H |

The `.ydq` loader writes bare card ids instead of references here (`tutorial.md`, "Tag partners"); no shipped file uses it. The changing value that session B saw in the high half of the word at area `+0x04` is the first reference at area `+0x06` (the first hand card), consistent with the layout (M).

## Phase override stack (`phase_override_stack`)

Lets AI look-ahead code evaluate a position "as if" in another phase. Users: `ai_build_battle_plan` (`0x09d1586c`), `ai_sim_prepare_battle_stats`, `ai_sim_apply_summon_effect`, `ai_should_summon_in_defense` (capstone: every `0x09e27fe4`/`0x09e27fec` access is in these four).

| Address | Size | Type | Field | Evidence | Conf. |
| --- | --- | --- | --- | --- | --- |
| `0x09e27fe4` | 8 | `s16[4]` | Saved phase words. Push (only when depth < 4): `stack[depth] = phase 0x09e2d1e8; depth += 1; phase = forced value` (3 Battle or 2 Main). Pop (when depth > 0): `depth −= 1; phase = stack[depth]` | `ai_build_battle_plan` `0x09d15a88`–`0x09d15b14`, `ai_should_summon_in_defense` `0x09d1a8c0` | H |
| `0x09e27fec` | 2 | `s16` | Depth (0–4) | same; read with `lh` | H |

While the depth is non-zero, the AI's "real phase" reads `stack[0]` (the phase before the first override) instead of `0x09e2d1e8` (`0x09d158cc`–`0x09d158e8`). The two bytes after the depth are not accessed (padding). Other AI functions force the phase without the stack (`duel-phases.md`).

## Battle damage records (`battle_damage_record`)

Two 20-byte records at `0x09e286e0 + i × 0x14`, filled by `duel_core_battle_add_damage(src, dst, amount)` (`0x09dc4330`) during damage calculation and consumed when the damage is applied (`battle.md`).

| Offset | Size | Type | Field | Evidence | Conf. |
| --- | --- | --- | --- | --- | --- |
| `+0x00` | 4 | `s32` | Amount; 0 = record free. `add_damage` uses record 1 when record 0's amount is non-zero | `0x09dc4358`–`0x09dc437c` | H |
| `+0x04` | 4 | `u32` | Source side (`src[0]`) | `0x09dc4394` | H |
| `+0x08` | 4 | `u32` | Source slot (`src[1]`) | `0x09dc43b0` | H |
| `+0x0c` | 4 | `u32` | Damaged side: `dst[0]`, or `1 − source side` when `dst` is NULL | `0x09dc43b4`–`0x09dc4404` | H |
| `+0x10` | 4 | `u32` | Damaged slot: `dst[1]`, or 5 (= the player) when `dst` is NULL | same | H |

`duel_core_cmd_clear_battle_damage_to_side` (`0x09dc0774`) clears the amount of the record whose `+0x0c` equals the side of the current command. Other readers: `duel_core_battle_resolve`, `duel_core_battle_step_damage_calc`, `duel_core_battle_step_attack_end`, `duel_effects_get_lp_change_amounts`, `ai_eval_attack`.

## Chain extra-target ring (`chain_extra_targets`)

`u16[128]` at `0x09e28e50`, write position `u32 0x09e28e4c`. A chain link stores its first five targets in the link (`+0x08`, count `+0x07`); from the sixth on, `duel_effects_add_link_target` stores the ring position in link `+0x12` once and appends further targets with command `0x28` (`a = 0xffff`). The Fusion and Synchro material pickers reuse the ring for their material references (`duel_effects_add_fusion_material`: index `(0x09e28e4c + count) & 0x7f`).

| Offset | Size | Type | Field | Evidence | Conf. |
| --- | --- | --- | --- | --- | --- |
| `+2i` | 2 | `u16` | Target entry: bit 0 side, bits 1–4 slot, bits 5–13 card instance, bits 14–15 instance generation (the 2-bit counter of the instance table); for material use a bare instance reference | `duel_effects_add_link_target`, `duel_effects_get_link_target_ref`, `duel_effects_add_fusion_material` | H (target layout), M (material use) |

Indices wrap modulo 128. Readers: `duel_effects_get_link_target_ref`, `duel_effects_get_link_target_raw`, `duel_effects_level_subset_sum_exact`.

## Timing event queue (`timing_event_queue`)

Written by `duel_core_raise_timing_event(code, arg)` (`0x09ccaae4`); consumed by `duel_core_run_timing_windows` (`0x09ccc494`), about 45 activation conditions and the AI (`battle.md`, `duel-phases.md`).

| Address | Size | Type | Field | Evidence | Conf. |
| --- | --- | --- | --- | --- | --- |
| `0x09e28f90` | 4 | `u32` | Batch nesting counter (`duel_core_timing_batch_begin`/`_end`); while non-zero new events are appended, otherwise the queue restarts | `battle.md` | H |
| `0x09e28f94` | 4 | `u32` | Event serial | `battle.md` | M |
| `0x09e28f98` | 4 | `u32` | Event count (0–32) | `battle.md`, `ai-tables.md` | H |
| `0x09e28f9c` | 4 | `u32` | Chain-resolving flag: nothing is queued while set | `battle.md` | H |
| `0x09e28fa0` | 32 | `u8[32]` | Event codes (1 Draw Phase … `0x25`; list in `duel-phases.md`); an empty queue is read as one event with code 0 by the list-activation conditions, which write 0 here | `duel_core_raise_timing_event`, `duel_core_list_cond_can_activate_in_timing` | H |
| `0x09e28fc0` | 128 | `u32[32]` | Event arguments (for card events the low 9 bits are a card instance, bit 9 / bit 16 a side; per-code layout in the readers) | same; `chain.md` link `+0x14` | H (array), M (argument packing) |

Neighbouring response-window words `0x09e29044` (window state), `0x09e29048` (window pending), `0x09e2904c` (activation made) belong to the window driver (`battle.md`, `chain.md`), not to the queue.

## Fusion and Synchro material state (`summon_material_state`)

Globals of the Fusion, contact-fusion and Synchro procedures (`summon.md`, `fusion-recipes.md`). Access widths from a capstone scan of the module.

| Address | Size | Type | Field | Evidence | Conf. |
| --- | --- | --- | --- | --- | --- |
| `0x09e29050` | 4 | `u32` | Card id of the Fusion/Synchro monster being summoned | `duel_effects_can_fusion_with_materials`, `duel_core_can_synchro_summon_card` | H |
| `0x09e29054` | 4 | `u32` | Its card reference (instance) | same | H |
| `0x09e29058` | 4 | `u32` | Material count required (recipe count; Synchro minimum 2, or 3 for `0x1d7d`/`0x1f25`) | `duel_core_get_synchro_min_materials`, the recipe table | H |
| `0x09e2905c` | 4 | `u32` | Fusion variant by spell (0 default, 1 Miracle Fusion type, 2 Future Fusion, 3 Dark Calling, 4 contact fusion, 5 Miracle Contact, 6 Cyberdark Impact!, 7 Super Polymerization, 8 Chain Material) | `summon.md` | H |
| `0x09e29060` | 4 | `u32` | Ambiguous-match counter of the material matcher; reused as the materials' ATK sum for UFOroid Fighter and Evil Hero Dark Gaia | `duel_effects_match_fusion_material`; `fusion-recipes.md` | M |
| `0x09e29064` | 4 | `u32` | Number of materials picked so far (also the offset into the extra-target ring) | `duel_effects_add_fusion_material`, `duel_core_try_synchro_material` (64 reads) | H |
| `0x09e29068` | 4 | `u32` | Substitute flag: set when a fusion substitute has been used or the Fusion forbids substitutes | `duel_effects_can_fusion_with_materials`, `fusion-recipes.md` | M |
| `0x09e2906c` | 20 | `u32[5]` | Material codes still to be matched (copied from the recipe; a matched slot is cleared) | `duel_effects_can_fusion_with_materials` ("matching globals `0x09e29050`–`0x09e2907c`") | H |

The Level still to cover during a Synchro Summon is outside this block, at `0x09e28f64`.

## Engine command queue (`duel_command_queue`)

The single path by which the engine changes duel state (`duel_core.md`, "The command queue"; `duel-phases.md`).

| Address | Size | Type | Field | Evidence | Conf. |
| --- | --- | --- | --- | --- | --- |
| `0x09e290f8` | 8 | command | Current command, copied from the queue head by `duel_core_process_command_queue` (`0x09dc1050`); the handlers read `a`, `b`, `c` at `0x09e290fa`/`fc`/`fe` | `duel-phases.md` | H |
| `0x09e29100` | 2048 | command`[256]` | Queue, FIFO; the rest shifts down when the head is taken | `duel_core_push_command` (`0x09dc07f8`) | H |
| `0x09e29900` | 4 | `u32` | Number of queued commands (0–256; a push to a full queue is dropped) | same | H |
| `0x09e29904` | 4 | `u32` | Set while the current command runs; the handler clears it when finished | `duel_core_next_turn` and other handlers | H |
| `0x09e29908` | 4 | `u32` | Sub-step of the running command (handlers that wait for a UI event) | `duel-phases.md` | H |

Command record (8 bytes):

| Offset | Size | Type | Field | Conf. |
| --- | --- | --- | --- | --- |
| `+0x00` | 2 | `u16` | `op`: bits 0–11 command code (1–`0x68`), bit 15 side; bits 12–14 not used by the dispatcher (masked off with `0xfff`) | H |
| `+0x02` | 2 | `u16` | `a` | H |
| `+0x04` | 2 | `u16` | `b` | H |
| `+0x06` | 2 | `u16` | `c` | H |

The argument packing is per command (`duel_core.md`, `chain.md`, `summon.md`, `effect-helpers-misc.md`, `tutorial.md`). The tutorial scripts and the legacy `NN_duel_command.bin` files store the same 8-byte record (`tutorial.md`).

**Verified in PPSSPP** (sessions A, B and D, [`2026-10-26-sessionA-part1.md`](../verification/results/2026-10-26-sessionA-part1.md), [`2026-10-27-sessionB.md`](../verification/results/2026-10-27-sessionB.md), [`2026-10-27-sessionD.md`](../verification/results/2026-10-27-sessionD.md)): execute logs at `duel_core_push_command` recorded `(op, a, b, c)` for whole duels; bit 15 was the CPU's side and every command took effect in posting order.

## Engine command jump table (`duel_command_dispatch`)

`u32[105]` at `0x09e00944` (module `+0x21f544`), 420 bytes. `duel_core_execute_command` (`0x09dc0974`) masks the code with `0xfff`, rejects codes ≥ `0x69` (`sltiu 0x69`) to the default case `0x09dc103c`, and jumps through `table[code]`. Entry 0 is the default case itself (code 0 is not a command); entries 1–`0x68` point at 104 distinct case stubs, each of which calls one handler and branches to the common epilogue (for example entry 4 → stub `0x09dc09ec` → `duel_core_next_turn`). The pointers are module-relative in the file and relocated at load. (H, capstone.) The registry size of 416 counts only codes 1–`0x68`.

| Offset | Size | Type | Field | Conf. |
| --- | --- | --- | --- | --- |
| `+4 × code` | 4 | code pointer | Case stub of command `code` (0 = default / out-of-range) | H |

The handler of each code is named in `re/functions.csv` (`duel_core_cmd_*`); the codes the documents use are listed in `duel_core.md` (card movement), `chain.md` (`0x10`–`0x12`, `0x35`–`0x38`), `summon.md`, `battle.md` and `duel-phases.md` (phase commands).

## Card instance table (`duel_card_instance`)

512 entries of 6 bytes at `0x09e2bbcc`, indexed by the 9-bit **card instance** (reference) number. Instance `side + 2n` belongs to side `side`, `n` being the per-side serial (player block `+0x04` next free, `+0x08` last used). Entries 0 and 1 are unused (serials start at 1: side 0's first card is instance 2, side 1's instance 3).

| Offset | Size | Type | Field | Evidence | Conf. |
| --- | --- | --- | --- | --- | --- |
| `+0x00` | 2 | `u16` | Bits 0–13 card id; bits 14–15 flags copied from the deck entry's id bits 14–15 (also readable as byte `+1` bits 6–7) | `duel_core_alloc_card_instance`, `duel_core_init_deck_lists`, `duel_core_load_deck`, `duel_core_get_card_id_by_ref` | H (id), M (flags: meaning unknown) |
| `+0x02` | 1 | `u8` | Bits 0–1 generation counter, incremented when the card enters a monster zone, the Graveyard or the banished zone (a mismatch with a stored copy means the card left and came back); bits 2–7 not seen used | `duel_core_place_in_monster_zone`, `duel_core_is_attack_target`, `chain.md` link `+0x05` | H (counter), M (meaning) |
| `+0x03` | 1 | — | Unknown; not accessed by the readers listed here | — | unknown |
| `+0x04` | 2 | `u16` | Head of the instance's own effect-record list (index into the pool below; 0 = empty) for effects that follow a card off the field | `duel_core_alloc_card_instance`, `duel_core_attach_instance_effect`, `duel_core_clear_slot_effects_on_face_change` | H |

A bitmap at `0x09e02f24` (one bit per instance) records the cards used during the duel (`duel_core_was_card_used_in_duel`).

## Card list entry (`duel_card_list_entry`)

The 4-byte entry of the hand (`+0x124`), deck (`+0x304`), Extra Deck (`+0x4e4`), Graveyard (`+0x55c`) and banished (`+0x7b4`) lists of a player block, and the first 4 bytes of a field slot (`duel_core.md`). Read through `duel_core_get_location_entry` (`0x09dca4ec`).

| Offset | Size | Type | Field | Evidence | Conf. |
| --- | --- | --- | --- | --- | --- |
| `+0x00` | 2 | `u16` | Bits 0–13 card id; bit 14 instance bit 0 (= owner side); bit 15 a flag carried over by the movement commands (`0x30` keeps it in `b` bits 12+) | every list reader; `duel_core_init_deck_lists` | H (id, bit 14), M (bit 15) |
| `+0x02` | 2 | `u16` | Bits 7–14 instance bits 1–8 (the serial `n`); bits 0–6 per-entry flags set by the movement commands (`0x30` copies "by opponent" to an entry bit 3; `0x3f`/`0x32` copy `c` bits 4–5 to entry bits 0–1; the documents call them entry bits, and since bits 0–13 of `u16 +0` hold the card id they are placed here); bit 15 unknown | `duel_core_init_deck_lists`, command handlers `0x30`, `0x32`, `0x3f` | H (instance), M (flag positions), unknown (bits 2, 4–6, 15) |

Instance number = `((u16 +2 & 0x7fff) >> 7) << 1 | (u16 +0 >> 14 & 1)`; the same expression appears in every reader (H).

## Effect records and markers (`duel_effect_records`, `effect_marker`)

One pool of 256 ten-byte records at `0x09e2c7cc` (index 0 = "none"; records 1–255 usable). `effect_marker` is the record format; `duel_effect_records` the pool. Each field slot has a singly linked list (head `u16` slot `+0x0a`; slot 11 of the player array, player `+0x11a`, is the player-wide list) and each card instance one more (instance `+0x04`). Full semantics of the kinds: [`stat-modifiers.md`](../subsystems/stat-modifiers.md), "Effect attachments"; markers in [`chain.md`](../subsystems/chain.md).

| Offset | Size | Type | Field | Evidence | Conf. |
| --- | --- | --- | --- | --- | --- |
| `+0x00` | 2 | `u16` | Key: kinds 0–5 the source card id (or a pseudo-key such as `0xfb6`, once per turn); kinds 6–12 the source location `side | slot << 8` | `duel_core_attach_effect`, the lookups | H |
| `+0x02` | 1 | `u8` | Bits 0–3 kind (0 free, 1–2 temporary, 3–5 lasting, 6–9 source links, 10–11 equip links, 12 equipped monster card); bits 4–7 turn counter | `duel_core_expire_turn_effects` | H (layout), M (some kinds) |
| `+0x03` | 1 | — | Unknown; not written by `duel_core_attach_effect` (which stores `+0`, `+2`, `+4`, `+6`, `+8` only; capstone `0x09be5974`–`0x09be599c`), probably padding | — | unknown |
| `+0x04` | 2 | `u16` | Value (amount, option, instance number, zone mask …; per key) | `duel_core_attach_effect`, `duel_core_has_marker_value` | H |
| `+0x06` | 2 | `u16` | Timestamp: placement serial `0x09e2d1d0` at creation | `duel_core_attach_effect` | H |
| `+0x08` | 2 | `u16` | Next record index (0 ends the list) | every list walker | H |

Allocation: `duel_core_attach_effect(side, slot, kind, key, value)` (`0x09be5894`) and `duel_core_attach_instance_effect` (`0x09be59a8`) take the first record with kind 0 (−1 when full) and append it; `duel_core_detach_effect` / `_detach_effect_list` / the `duel_core_detach_list_effects_by_*` family free them; `duel_core_expire_turn_effects` (`0x09be6864`) runs the turn-change expiry; `duel_core_normalize_effect_records` (`0x09be75f8`) after command `0x35`. Commands `0x35`–`0x37` (`chain.md`) are the only posted changes.

**Verified in PPSSPP** (2026-10-26, [`2026-10-26-sessionA-part1.md`](../verification/results/2026-10-26-sessionA-part1.md), A8): record 0 read all zero (index 0 = none) and the once-per-turn marker `0xfb6` (kind byte 2, counter 0) was attached by command `0x35` and freed at the turn change.

## Player input state (`player_input_state`)

Words used by `duel_core_begin_player_input`, the selection openers (`duel_core_begin_select_cards`/`_zone`/`_target`/`_monster_to_summon`/`_tributes`), `duel_core_submit_player_action` and the prompt helpers (`summon.md`, "The action menu"; `duel-phases.md`, "Player input"). All are `u32` (capstone access widths; a few readers take the low half with `lhu`).

| Address | Field | Evidence | Conf. |
| --- | --- | --- | --- |
| `0x09e2d248` | Dialog/decision result: the yes/no, option, coin or number answer of a prompt, and the CPU's next-phase decision; written by the human UI or by the AI wrapper | `duel_core_ask_yes_no*`, `duel_core_ask_option`, `ai.md` (209 accesses) | H |
| `0x09e2d24c` | Input mode: 1 Draw confirmation, 2 Main Phase control, 3 Battle Phase, 4 open window, 5 chain response, 6 monster to summon, 7 zone, 8 card selection, 9 target | `duel_core_begin_player_input` and the openers; `duel_core_get_card_action_mask` | H |
| `0x09e2d250` | Selection argument (count or parameter; −1 for mode 1 and mode 7) | `duel_core_begin_select_cards` (`arg`), `_select_zone` | M |
| `0x09e2d254` | Input open (the action-mask query returns 0 while clear) | `duel_core_get_card_action_mask` | M |
| `0x09e2d258` | Answer ready | `duel_core_submit_player_action` | H |
| `0x09e2d25c` | Cleared with the answer flag when a selection opens; meaning unknown | the openers | unknown |
| `0x09e2d260` | Card id of the selection's source (or the zone argument in mode 7) | `duel_core_begin_select_cards`, `_select_zone` | M |
| `0x09e2d264` | Chosen card id | `duel_core_submit_player_action` | H |
| `0x09e2d268` | Chosen card reference (field slot, hand or list entry; list index 1-based, ≥ 3000 = a card id) | same; `duel_core_list_activate_summon_procedure` | H |
| `0x09e2d26c` | Action code of the answer (`summon.md`, "Action codes"; `0x0d + phase` for the phase menu) | same | H |
| `0x09e2d270` | Step of `duel_core_action_use_card_list` | `effect-helpers` summary of `0x09dcd9cc` | M |
| `0x09e2d274` | Side the input is asked of | the openers | H |
| `0x09e2d278` | Side that answered | `duel_core_submit_player_action` | H |
| `0x09e2d27c` | Location of the chosen card | same | H |
| `0x09e2d280` | Index of the chosen card | same | H |
| `0x09e2d284` | Chosen zone (mode 7: `location + index`) | same | H |
| `0x09e2d288` | Reason code of a refused action for the local player (2 Normal Summon used … `0x14` activation locked) | `summon.md`, `effect-helpers-values.md` | M (codes), L (texts) |
| `0x09e2d28c` | Filter / validator callback of the open selection | the openers | H |
| `0x09e2d290` | Secondary filter (`duel_core_begin_select_target_ex`, `_select_tributes`) | `effect-helpers-predicates.md` | H |
| `0x09e2d294` | Unknown (3 reads, 3 writes) | capstone scan | unknown |

**Verified in PPSSPP** (D1, [`2026-10-27-sessionD.md`](../verification/results/2026-10-27-sessionD.md)): `duel_core_begin_player_input` was logged with modes 5 and 2 at the expected moments.

## Send-batch request (`send_batch_request`)

The single-entry request through which effect handlers destroy, banish, return or Tribute field cards; executed over later frames by `duel_core_send_batch_step` (`0x09c232bc`). Full flag and state tables: [`effect-helpers-movement.md`](../subsystems/effect-helpers-movement.md).

| Address | Size | Type | Field | Evidence | Conf. |
| --- | --- | --- | --- | --- | --- |
| `0x09e2d298` | 4 | `u32` | Executor state (0 idle, 1 start, 2–3, 10–12, 100, `0x65`–`0x70`, `0xc9`, `0xca`) | the 31 request functions store 1; executor | H |
| `0x09e2d29c` | 4 | `u32` | Per-side loop index of the executor (0, 1) | `duel_core_send_batch_step` `0x09c23424`–`0x09c2343c` | M |
| `0x09e2d2a0` | 24 | link | Cause: a copy of the 24-byte chain link of the effect (or a synthetic link built from a card id); `+0x14` (`0x09e2d2b4`) its event argument | request functions | H |
| `0x09e2d2b8` | 4 | `u32` | Destination location (`0x0b`–`0x0f`) | `effect-classification.md` | H |
| `0x09e2d2bc` | 4 | `u32` | Flags (`0x1` by opponent, `0x2` destroy, `0x4` battle, `0x1000` Tribute, `0x20000` other side, `0x4000000` Deck bottom, `0x8000000` in a timing batch …) | `effect-helpers-movement.md` | H/M per bit |
| `0x09e2bba4` | 4 | `u32` | Slot mask: bit `slot + 16 × side`, slots 0–10 | request functions | H |
| `0x09e2bba8`–`0x09e2bbc3` | 28 | `u32[7]` | Executor bookkeeping masks (`0x09e2bbb4` follow-up prompts, `0x09e2bbbc` slots handled, `0x09e2bbc0` slots that reached the destination; the others unknown) | executor | M |

## Prompt request block (`prompt_request_block`)

Single-entry request for a player prompt, run by `duel_core_run_prompt_request` (`0x09c14580`) from the turn flow (`effect-helpers-misc.md`).

| Address | Size | Type | Field | Evidence | Conf. |
| --- | --- | --- | --- | --- | --- |
| `0x09e2d2c0` | 4 | `u32` | Link-duel state: 2 send the request to the peer, 1 waiting for the answer, 0 local | `duel_core_run_prompt_request` | H |
| `0x09e2d2c4` | 4 | `u32` | Pending flag | same; requesters | H |
| `0x09e2d2c8` | 4 | `u32` | Side asked | same | H |
| `0x09e2d2cc` | 4 | `u32` | Kind 1–8 (1 hint, 2 yes/no or option, 3 zone from mask, 5 Type, 6 Attribute; 4, 7, 8 not read) | same | H (dispatch), M (kinds) |
| `0x09e2d2d0` | 4 | `u32` | Worker step | workers | H |
| `0x09e2d2d4` | 2 | `s16` | Argument 0 | same | H |
| `0x09e2d2d6` | 2 | `s16` | Argument 1 | same | H |
| `0x09e2d2d8` | 4 | `u16[2]` | Answer (low half read by the callers; the whole word is sent to a link peer as a 4-byte answer) | same (49 `lhu` at `+0x2d8`, 3 writes at `+0x2da`) | H (low half), M (high half) |

The block is 28 bytes (the registry's 26 stops before the answer's high half). Worker table `0x09debad4` (module `+0x20a6d4`): `u32[9]`, indexed by kind; entry 0 (`0x09c10f64`) is outside the kind range and is not called by the runner, entries 1–8 are the workers `0x09c13994`, `0x09c139e0`, `0x09c13c80`, `0x09c13d40`, `0x09c13f2c`, `0x09c140e8`, `0x09c14284`, `0x09c14480` (H, data read).

## List activation table (`list_activation_table`)

23 records of 16 bytes at `0x09e00dbc` (module `+0x21f9bc`) for card effects used from a card list (Deck, Graveyard) and for player-marker effects. Read by `duel_core_collect_list_activations` (`0x09dd0290`, which offers them in the list menu; loop bound `sltiu 0x17`) and `duel_core_activate_from_list` (`0x09dd08b8`, which calls the activation function of the matching card). (H for the layout, capstone at `0x09dd0330`–`0x09dd04bc` and `0x09dd0990`–`0x09dd09cc`.)

| Offset | Size | Type | Field | Conf. |
| --- | --- | --- | --- | --- |
| `+0x00` | 4 | `u32` | Card id | H |
| `+0x04` | 4 | `u32` | Location id of the list the card must be in (the shipped table uses `0x0d` Deck for 6 records and `0x0e` Graveyard for 17) | H (comparison), M (reading) |
| `+0x08` | 4 | code pointer | Condition `(side, card_id, ref) → mask`; the collector calls it for each copy of the card in the list (newest first) and keeps the copies for which it is non-zero | H |
| `+0x0c` | 4 | code pointer | Activation `(side, card_id, ref) → done` | H |

When `+0x0c` is `duel_core_list_activate_player_effect` (`0x09dcffac`) the collector does not scan the list: it calls the condition once with `ref = 0` (the effect is recorded as a marker on the player). Functions in the shipped table: conditions `duel_core_list_cond_main_phase_special_summon`, `duel_core_list_cond_can_activate_player_effect`, `duel_core_list_cond_can_activate_in_timing`; activations `duel_core_list_activate_summon_procedure`, `duel_core_list_activate_player_effect`, `duel_core_list_activate_graveyard_effect`. The collector also skips a card when `0x09de4d0c(card)` returns less than 2 (not read). The card ids are game data and are not listed here.

## End Phase and Battle-end check tables (`end_phase_checks`, `battle_end_checks`)

Two tables of `(function, argument)` pairs, 8 bytes each. `duel_core_step_end_phase` (`0x09ddf4dc`) walks the End Phase table; `duel_core_battle_step_end` (`0x09ddaa20`) walks the Battle Phase table twice (with `0x09e2d21c` = 0, then 1) and retries the step as soon as one function returns 0 (`duel-phases.md`).

| Table | Address | Module offset | Records |
| --- | --- | --- | --- |
| `end_phase_checks` | `0x09e014f4` | `+0x2200f4` | 8 |
| `battle_end_checks` | `0x09e00f5c` | `+0x21fb5c` | 31 |

| Offset | Size | Type | Field | Conf. |
| --- | --- | --- | --- | --- |
| `+0x00` | 4 | code pointer | Check `int f(int side, int arg)`: 0 = not finished (retry next frame), non-zero = done | H |
| `+0x04` | 4 | `u32` | Argument, normally the card id the check handles (0 for the first Battle-end entry) | H |

The End Phase functions are `duel_core_end_phase_post_turn_counters` (×5), `_update_final_countdown`, `_divide_lp_by_ten` and `_clear_hand_reveal`; the Battle-end functions are the `duel_core_battle_end_*` family (`queue_*_trigger`, `remove_effect_marker`, `remove_counters`, `destroy_*_marked_monsters`) and `duel_core_apply_post_attack_defense_change`. The two words after the last Battle-end pair (`0x09e01054`) are code pointers that the loop (bound 31) does not reach; they are not part of the table. (H, data read and function names from the registry.)

## Free-zone preference tables (`zone_preference_tables`)

| Address | Module offset | Size | Type | Content | Reader | Conf. |
| --- | --- | --- | --- | --- | --- | --- |
| `0x09deba0c` | `+0x20a60c` | 20 | `u32[5]` | Monster-zone order 2, 3, 1, 4, 0 (centre first, then alternating right/left) | `duel_core_find_free_monster_zone` (`0x09bfaf70`) | H |
| `0x09deba20` | `+0x20a620` | 20 | `u32[5]` | Spell/trap-zone order 2, 3, 1, 4, 0, used as `5 + value` | `duel_core_find_free_spell_trap_zone` (`0x09bfc7a4`) | H |

The finders return the first zone of the order that is empty and usable (`duel_core_is_zone_usable`, `effect-helpers-predicates.md`), or −1.

## Open questions

- Meaning of the instance-table bits 14–15 and byte `+0x03`, of list-entry bits 2, 4–6 and 15 of `u16 +2`, and whether effect-record byte `+0x03` is ever used.
- Input-state words `0x09e2d25c` and `0x09e2d294`; four of the seven executor masks at `0x09e2bba8`–`0x09e2bbc3`.
- `0x09e02cb0` (extra duel result) and the gate `0x09de4d0c` of the list-activation collector.
- Prompt kinds 4, 7 and 8 (workers not read).
- Confirm in PPSSPP: the battle damage records for one attack with piercing (`battle.md`), the phase override stack during an AI turn, and the material state during a Fusion.
