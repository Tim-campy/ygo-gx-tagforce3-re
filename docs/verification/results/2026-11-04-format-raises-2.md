# Format rows raised to `reimplemented`, second round (2026-11-04)

Rule (`docs/PROGRESS.md`): a tool reads and writes the format, writing the parsed model reproduces every instance on the disc (or every save) byte for byte through `tools/roundtrip.py --check`, and synthetic unit tests exist. Tables inside `BOOT.BIN` or a game module count when the writer reproduces the table's bytes in place: the round trip overwrites every byte the table owns with `0xA5`, writes the model and compares the whole executable.

Inputs: the maintainer's extracted disc (`extracted/umd/PSP_GAME`) and the seven plaintext saves in `external/ppsspp/saves` (`E5-a/b`, `E7-a/b/c`, `E16-a/b`), read only. No game data is committed. Command:

```
python3 -I tools/roundtrip.py --check <PSP_GAME> --saves external/ppsspp/saves
```

Result: 87 checks, all byte-identical (31 of them new in this round). Synthetic tests: `tools/tests/test_roundtrip.py` (`ExecutableTableTest`, `MoreFileWriterTest`, `SaveRegionCodecTest`) and `tools/tests/test_ehf.py` (`EhfAddChannelTest`, `EhfWriterTest`); all 34 test files pass.

Formats at `reimplemented` or above: 96 of 182 (52.75 %) before, 125 of 182 (68.68 %) after.

## Raised rows (29)

| Row | Reader → writer | Instances checked |
| --- | --- | --- |
| `gmodule_prx` | `modules.elf_decode` → `elf_build` (headers, sections, decoded PSP relocations) | 36 modules |
| `tuto_legacy_cmd` | `tutorial.legacy_decode` → `legacy_build` | 20 files (4 lessons × 5 archives) |
| `chr_wordstbl` | `strtbl.parse` → `strtbl.build` | 1,134 files (570 in `duel/`, 564 in `labo/voicetest.ehp`) |
| `snd_shds_header` | `exe_tables.read_shds` → `write_shds` | 1 (`BOOT.BIN`, 141,904 bytes; bank offsets also equal the `boot_sound_tables` reader) |
| `boot_character_table` | `exe_tables` (174 records, 655 strings, 126 card lists) | 1 |
| `field_marker_hidden_cells` | `exe_tables` | 2 tables (`rel_field`) |
| `duel_flow_steps`, `turn_steps`, `battle_steps` | `exe_tables` | 1 table each (`rel_duel_eng`) |
| `duel_command_dispatch` | `exe_tables` | 1 (105 entries) |
| `end_phase_checks`, `battle_end_checks` | `exe_tables` | 1 each (8 and 31 pairs) |
| `list_activation_table` | `exe_tables` | 1 (23 records) |
| `zone_preference_tables` | `exe_tables` | 2 tables |
| `ai_main_steps` | `exe_tables` | 1 (8 entries) |
| `field_request_table` | `exe_tables` | 1 (33 records, `rel_field`) |
| `story_calendar_tables` | `exe_tables` | 3 tables (`rel_story`) |
| `shop_opponent_list` | `exe_tables` | 1 (104 entries, `rel_shop`) |
| `ui_resource_table` | `exe_tables` (records and format strings) | 11 tables, 234 records, in 6 modules |
| `root_path_table` | `exe_tables` (pointers and paths) | 1 |
| `card_language_suffixes` | `exe_tables` | 1 |
| `tgm_etc_scene` | `tgm.read_scene` → `write_scene` | 4,533 flag-2 TGMT (92 × 84 tracks, 4,353 × 42 tracks, 88 `.vtmt` with none) |
| `save_character_flags`, `save_record_table`, `save_flag_bytes`, `save_progress_bytes` | `save.to_model` → `from_model` (JSON) | 7 saves each; real (non-zero) data in at least one save |
| `story_block`, `story_field_save_block` | `save.to_model` → `from_model` (new sub-block codecs, model schema 2) | 7 saves |
| `deck_struct` | `save._decode_deck_struct` → `_encode_deck_struct` | 882 non-empty deck structs in the 7 saves |

Thin coverage, stated plainly: `save_flag_bytes` has one non-zero byte in the seven saves (pack 17 bought once, `E16-b`), and `save_progress_bytes` one (entry 2, `E16-a/b`); the rest of both regions is zero on the saves and covered only by the synthetic tests.

## Rows checked but not raised (all-zero in every save)

`save_stored_decks`, `save_recipe_table` and `save_picture_bits` were left alone (maintainer decision of 2026-11-03: they stay `documented` until a save with real data in them round-trips); their checks still pass.

| Row | Why it stays `documented` |
| --- | --- |
| `save_card_list` | Count, ids and states are zero in all seven saves; same treatment as the maintainer's 2026-11-03 decision for `save_stored_decks`, `save_recipe_table`, `save_picture_bits` (left alone). The check is registered and passes. |
| `story_flag_block` | Zero in all seven saves (no story flag 129–192 or system flag 65–128 set). Check registered and passing. |

## Rows that cannot meet the rule (no instance in a file or a save)

| Row(s) | Reason |
| --- | --- |
| `duel_setup_duellist` | Built at run time by each set-up routine (`rel_story`, `rel_title`, …) on the stack or heap; no static instance. |
| `target_filter_flags`, `search_filter_word` | Flag words passed as immediates in code (target-filter stubs, builder calls); not a table. The builder list itself is `effect_lists` (L1), already `reimplemented`. |
| `card_action_mask` | A value computed by `duel_core_get_card_action_mask`; no storage. |
| `shop_unlock_rules` | The rules are code (`shop_update_pack_unlocks`), not data. |
| `card_effect_spec`, `card_refs`, `family_split` | Output formats of our own tools (JSON Lines / CSV derived from the code), not game data. |
| `module_registry_entry`, `scene_stack`, `scene_slot`, `file_request_ring`, `heap_header`, `cardinfo_globals` | `BOOT.BIN` `.bss` or heap structures (`.data` ends at `0x08916dd0`). |
| `duel_stat_block`, `duel_effect_records`, `effect_marker`, `duel_player_block`, `duel_field_slot`, `duel_card_list_entry`, `duel_card_instance`, `duel_command_queue`, `phase_override_stack`, `attack_state`, `battle_replay_snapshot`, `battle_record`, `battle_damage_record`, `timing_event_queue`, `trigger_queue`, `chain_extra_targets`, `summon_record`, `player_input_state`, `summon_material_state`, `send_batch_request`, `card_request_block`, `prompt_request_block`, `duel_setup_params`, `tag_waiting_area`, `candidate_list` | Duel-engine runtime state in `rel_duel_eng`'s `.bss` (after `0x09e01e10`) or engine pools; cleared or filled during a duel; not saved. |
| `ai_snapshot_slot`, `ai_stat_snapshot`, `ai_battle_plan`, `ai_board_view`, `ai_context`, `ai_summon_choice`, `ai_candidate_stack`, `ai_combat_tricks`, `ai_attack_result` | AI runtime state (the `0x25628`-byte area from `0x09e02ff8` cleared each turn, stack records). |
| `story_vm_state` | `rel_story` `.bss` (`+0x33b30`). |
| `tgm_model_instance` | Heap object created by `field_3d_create_model_instance`. |

## Fix in this round: `.ehf` add channel

`tools/ehf.py` read the colour-add channel as `s8 × 2`; the player reads four unsigned bytes added to the colour, for flag bit 4 or bit 5 (`docs/subsystems/ui.md`). Parser, evaluation (no doubling; nesting `add = own.add + own.mul × parent.add`), JSON export and the new writer use the unsigned bytes; the one bit-5 track on the disc (`ryusen01.ehf`, flags `0x39`) also has bit 4, so strides are unchanged. With a new `.ehf` writer (`ehf.decode` → `ehf.build`), all 1,225 `.ehf` round-trip byte for byte (`roundtrip.py --only ehf`); `ehf` was already `reimplemented`.

## Corrections found on the way

- Voice-test caption and change tables are in `labo/voicetest.ehp`, not `database/charalist.ehp`; the `voiceidchgtbl` check now covers those 94 copies too (283 in all, still byte-identical).
- Character table `+0x90`: list counts are 3–29 when non-zero, not 8–12.
- List activation table: 7 Deck records and 16 Graveyard records (not 6 and 17).
- UI resource tables: 11 tables in 6 modules (not one per module).
