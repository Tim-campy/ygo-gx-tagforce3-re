# `rel_cutin_viewer`

Module document of the 2026-11-04 round 6 (all game modules imported; `../modules.md`). English, evidence-based: the sections below come from reading every function of the module in the Ghidra decompilation; hypotheses carry a confidence.

| | |
| --- | --- |
| File | `PSP_GAME/USRDIR/gmodule/rel_cutin_viewer.prx`, 365,760 bytes, plain ELF (relocatable PRX) |
| Slot | scene 0x0b, id 0x0f |
| Exports → importers | (`libtemplate_rel`, 0) |
| Role (catalogue) | Cut-in viewer (module info `modtemplate`): same cut-in/duel-disk assets as `duel_draw`. |
| Runtime base | unknown; imported at image base 0x0, so addresses are module offsets |
| Registry ids | `rel_cutin_viewer:0x…` |
| Functions | 673 own functions, 673 documented in this round (field_3d 545, ui 113, audio 10, system 4, world 1); tables in `../functions/<group>.md`, section `rel_cutin_viewer` |

## Key functions (largest)

| Address | Prototype | Summary (first sentence) |
| --- | --- | --- |
| `0x00005c4c` | `int field_3d_cutin_tbl098cd2c0_map_node(int *cutin, int node)` | Map-node callback (descriptor +0x24) of the tbl098cd2c0 cut-in family (the default generic player models: character byte 9 not 5 and model id byte 1 not 3): reads the character's model ids (world_get_character_model_ids(cutin +0x00, cutin +0x04)) and picks one of fifteen node switches by model id byte 1 (2, 1 or 0) and byte 0 (4, 3, 2, 1 or 0), each mapping the generic node index node (0..0x25) to the model's node index (e.g. |
| `0x0000701c` | `int field_3d_cutin_tbl098cd360_map_node(int *cutin, int node)` | Map-node callback (descriptor +0x24) of the tbl098cd360 cut-in family (generic player characters whose model id byte 1 is 3): characters 0x78, 0x77, 0x76, 0x75, 0x74 and 0x6f have their own node switches (e.g. |
| `0x00012ffc` | `int field_3d_update_cutin_fx_anim18_31(int phase, void *data)` | Per-frame callback of the cut-in trail effect (0x7f70 bytes; +0 delay timer, +4 delay, +8 effect timer, +0xc length, +0x10 call counter, +0x14 fx slot, +0x18 alternate flag, +0x1c sound flags, +0x20/+0x24 sounds, +0x28 sound frame, +0x2c-+0x38 colour, +0x3c trail point count, +0x40 vertex count). |
| `0x000144e0` | `int field_3d_update_cutin_fx_anim55_71(int phase, void *data)` | Per-frame callback of the cut-in beam effect for animations 0x55-0x71 (0x1d200 bytes; +0 delay timer, +4 delay, +8 charge length, +0xc effect timer, +0x10 total length, +0x14 call counter, +0x18 fx slot, +0x1c alternate flag (anim 0x57), +0x20 sound flags, +0x24/+0x28 sounds, +0x2c sound frame, +0x30 burst position, +0x3c depth-test flag, +0x40 fade counter). |
| `0x000186d4` | `int field_3d_update_cutin_fx_anim3e_54_v1(int state, int *task)` | Draw-task callback of variant 1 of the cut-in effect for animation ids 0x3e-0x54. |
| `0x0001ab10` | `int field_3d_update_cutin_fx_anim3e_54_v4(int state, int *task)` | Draw-task callback of variant 4 of the cut-in effect for animation ids 0x3e-0x54. |
| `0x0001ba68` | `int field_3d_update_cutin_fx_anim3e_54_v5(int state, int *task)` | Draw-task callback of variant 5 of the cut-in effect for animation ids 0x3e-0x54. |
| `0x0001e908` | `int field_3d_update_cutin_fx_anima3_b5(int state, int *task)` | Draw-task callback of the cut-in effect for animation ids 0x72-0x80, 0x8e, 0x8f, 0xa3-0xb5 (an aura of flames and rising sparks at an attach point). |
| `0x0001f714` | `int field_3d_update_cutin_fx_animb1_v0(int state, int *task)` | Draw-task callback of variant 0 of the cut-in effect for animation ids 0xb1-0xb9 (a pale-blue burst at an attach point). |
| `0x000203f4` | `int field_3d_update_cutin_fx_animb1_v1(int state, int *task)` | Draw-task callback of variant 1 of the cut-in effect for animation ids 0xb1-0xb9 (an orange-red burst at an attach point). |
| `0x00021570` | `int field_3d_update_cutin_fx_anim107_114(int state, int *task)` | Draw-task callback of the cut-in effect for animation ids 0xba-0xc3, 0x104-0x114 (a card summoned out of a flame aura). |
| `0x0002351c` | `int field_3d_update_cutin_fx_animd5_e6(int state, int *task)` | Draw-task callback of the cut-in effect for animation ids 0xd5-0xe6 (a screen-space warm burst). |
| `0x00024b60` | `int field_3d_update_cutin_extra_a_fx(int state, int *task)` | Draw-task callback of the per-character extra cut-in effect A: a flickering glow traced along the bones of the duelist model in the main scene. |
| `0x000291bc` | `void audio_play_anim_sound_cues(int character, int variant, int anim, int frame, uint *done_flags)` | Hard-coded sound cues of the duel cut-in/character animations: a long if-chain on the animation id anim (values from 0 to about 0x2a9) that calls audio_play_se_once_at_frame(sound, frame, trigger frame, done_flags, bit) for one to three sound effects per animation, with bits 1, 2, 4 (once 8) so each fires once; the sounds are mostly ids 0x7a24, 0x7a25, 0x7a26 and 0x7a2e, plus 0x7a17, 0x7a1a, 0x7a21, 0x7a27, 0x7a2a, 0x7a2c and 0x7a47. |
| `0x0002d604` | `int field_3d_cutin_shared_map_node(int *cutin, uint node)` | Map-node callback (descriptor +0x24) of the shared cut-in block: selects a switch by the key cutin[0] << 3 \| cutin[1] (character << 3 \| variant: 0x4c0, 0x4b8, 0x4b0 for characters 0x98, 0x97, 0x96; 0x160, 0x168, 0x169, 0x158 for 0x2c, 0x2d (variants 0, 1) and 0x2b; 0x28 (5/0); 0x60/0x61 (0xc); 0x88, 0x70, 0x68, 0x80/0x81, 0x90, 0x78 (0x11, 0xe, 0xd, 0x10, 0x12, 0xf); 0x30/0x31 (6); 0x48, 0x58, 0x50 (9, 0xb, 0xa)) and translates the generic node id 0..0x25 into that model's node index (for key 0x4c0: 0 -> 0x2a, 4 -> 0x13, 5 -> 0x16, ...); unlisted ids and keys give 0. |

Batch A1: the first 337 own functions of `rel_cutin_viewer` (module offsets `0x00000000`-`0x0000c2cc`). All addresses below are module offsets (image base 0). All 337 were named and documented; none skipped.

## Purpose and flow

A developer-style viewer for the duel cut-ins (module info `modtemplate`, scene 0x0b). It has two browsers:

1. **Character browser** (the normal path): a list of 0x8d characters (list item i = character i + 2, drawn as number plus name from `world_get_character_name_string_first`), left/right choose the variant 0..3, the character's cut-in archive is loaded and every non-empty entry of its `all-ptrs.txt` can be played as a direct animation index (motion id = index + 0x1000) through a copy of the full `rel_duel_draw` cut-in system (slot 0 only).
2. **Raw file browser** (states 1-4, reached only if something sets state 1; the scene starts in state 6, hypothesis that it is a leftover debug path, confidence medium): scans `root 3 + duel folder` recursively (sceIoDopen/Dread) for files named `cutin_*` except `cutin_cmn.ehp`, up to 100 paths of 0x100 bytes, loads the chosen EHP, pairs every `*-etc.tmt.gz` scene member with its `*.tmt.gz` animation member, builds a model from the largest mesh member and plays scene n with left/right.

Entry point `ui_cutin_viewer_register_scene` (0x00000000) registers `ui_cutin_viewer_scene_main` (0x3c) / `ui_cutin_viewer_scene_end_noop` (0x2e4). The main loop runs on the state word `0x00043674`; `ui_cutin_viewer_set_state` (0x2ec) runs leave/enter handlers:

| State | Per-frame handler | Enter / leave | Meaning |
| --- | --- | --- | --- |
| 1 | scan files, then state 2 | loading overlay on / off | raw file scan |
| 2 | `ui_cutin_viewer_update_file_list` | `ui_cutin_viewer_open_file_list` / no-op | file list (cancel -> 5, choice -> 3) |
| 3 | `ui_cutin_viewer_load_file` | overlay on / off | read + bind the EHP, -> 4 |
| 4 | `ui_cutin_viewer_update_file_preview` (own frame loop) | `..._enter_file_preview` / `..._leave_file_preview` | raw scene preview (cross -> 2) |
| 5 | leave the loop | | exit: `system_scene_return(0xb, 0)` |
| 6 | `ui_cutin_viewer_open_card_view` | | initial state: card resources, `ui_card_view_open`, -> 8 |
| 7 | `ui_cutin_viewer_close_card_view` | | -> 5 |
| 8 | `ui_cutin_viewer_update_character_list` | `ui_cutin_viewer_open_character_list` / no-op | character list (cancel -> 7, choice -> 9) |
| 9 | `ui_cutin_viewer_wait_cutin_archive` | `..._request_cutin_archive` / no-op | wait for archives 0x80001, 0x80002 and the character archive |
| 10 | `ui_cutin_viewer_update_cutin_preview` (own frame loop) | `..._start_cutin_preview` / `..._stop_cutin_preview` | cut-in playback (cross -> 8) |

Controls in state 10: left/right (pad repeat word +0xc bits 0x80/0x20) step to the previous/next non-empty animation; circle (+4 bit 0x2000) or any step also advances the card id shown on the `4006.iff` prop texture and in ATK/DEF panels (`0x0004bd48`, next valid id between 0xe88 and 0x1f39, wrapping); cross (0x4000) returns to the list.

Frame callback `ui_cutin_viewer_draw_frame` (0x1130): state 10 runs the duel_draw order (dispatch motion start, `field_3d_draw_cutin_layer` on layers 8/9, frame hook, 0x10618, then 0x106c0 and `field_3d_update_current_cutin` with dt = 1 / frame rate); state 4 draws/updates the preview slot on layer 1; states 2/8 draw the list window; other states print a status string.

## Key structures (module offsets)

- Work block `0x00043670`, cleared over 0x86e0 bytes by `ui_cutin_viewer_init`: `+0x00` heap handle, `+0x04` state word (`0x00043674`), file paths `0x00043678` (100 x 0x100), archive handle `0x00043660` (before the block), file count `0x00049a78`, list window record `0x00049a7c` (0x120 bytes: `+0xc4` heap, `+0xcc` item count, `+0xe9` result byte, 6 = closed, `+0xf0` width, `+0xfc` item draw callback), chosen file `0x00049b9c`, raw preview slot `0x00049ba0` (a 0x190-byte cut-in slot), preview model `0x00049d30`, animation list `0x00049d34` (0x2b4 words: `all-ptrs.txt` copy or the `.tmt.gz` members), scene list `0x0004ad34`, entry count `0x0004bd34`, current entry `0x0004bd38`, last list item `0x0004bd3c`, character `0x0004bd40`, variant `0x0004bd44`, card id `0x0004bd48`.
- Heap: `system_heap_create(0x0004bd50, 0xb00000)`; the cut-in block starts right after it at `0x00b4bd50` (= 0x0004bd50 + 0xb00000), so the module's uninitialised data appears to include an 11 MB arena (hypothesis, confidence medium; the module file is only 365,760 bytes).
- Cut-in block `0x00b4bd50` (copy of `rel_duel_draw` 0x098d4d40, same layout): `+0x08` current slot `0x00b4bd58`, `+0x0c` index `0x00b4bd5c`, `+0x10` skip flag `0x00b4bd60`, slots `0x00b4bd70` (4 x 0x190). Following words: speed-lines pair `0x00b4c3b0/b4`, word `0x00b4c3b8` (duel_draw 0x098d53a8), level/start/target/counter `0x00b4c3bc..0x00b4c3c8`, fallback model `0x00b4c3d0` (duel_draw 0x098d53c0), per-family "table sorted" flags `0x00b4c3d4` upwards, current motion record `0x00b4c3dc`. Rule: viewer address = duel_draw address - 0x098d4d40 + 0x00b4bd50 inside this block.
- Static tables: voice sequence table `0x0003958c` (0x266 x 0x24), event tables `0x0003ebe4` (0x20 x 12) and `0x0003ed64` (0x1f x 12), default voice sequence `0x0003eedc`, default attach table `0x0003f0a4` (6 pairs), face-node ids `0x0003f290` (9), motion records `0x0003f2b4` (12 bytes each), fixed voice-bank indices `0x0003f410`, per-family attach-offset tables from `0x0003f150` (5 x 0x20 each; two tables for the tbl098cd540 and tbl098cdd10 families; 6 entries for tbl098ce0d0).

## Files loaded

- Character cut-in archives through `0x2c8f8(character, variant)` (copy of `field_3d_get_cutin_archive`), plus duel archives 0x80001 and 0x80002 and the card CIP; members as in `field_3d.md` (`all-ptrs.txt`, `alletc-ptrs.txt`, `info-ptrs.txt` / `cutin_chara_base.tms`, `voice01/02.vtmt.gz`, `voice/10000.txt`, `chr_voiceidchgtbl.bin`, language word tables, `texture/10500.txt`, `duel_disc.gim`, `ryusen01.ehf`).
- Raw browser: any `cutin_*` file (except `cutin_cmn.ehp`) under root 3 + the duel folder; members ending in the `-etc` scene suffix (11 characters, `.tmt.gz`), their plain `.tmt.gz` partners, and the largest member with the 4-character mesh suffix at `0x00039584` (presumably `.tms`).
- Sound bank 0x2ca is loaded for the whole scene.

## Relation to rel_duel_draw (twins and differences)

The cut-in code from 0x17b8 to 0xc2cc is a copy of `rel_duel_draw` 0x0983fb00 onwards, in the same order. The `twin:` lines were checked against an order/size alignment with the rel_duel_draw function list; the names follow the aligned function, not always the twin line (see below). Differences found in the copy:

- `field_3d_cutin_is_motion_finished` does not test the LP panel; `field_3d_cutin_pose_node_hook` has no voice-level test (the lip-sync track always runs on the voice time).
- Motion 0xe7 builds a demo card list of 1..39 consecutive valid ids after 0xfa6 (`field_3d_cutin_viewer_collect_demo_card_ids`) instead of reading the deck.
- `ui_test_set_draw_flags(0x20, 1)` is replaced by a stub returning 0 (`ui_cutin_viewer_stub_set_draw_flags`, 0x34).
- New: `field_3d_cutin_set_fallback_model` (0x2ae4) sets the fallback instance used by `field_3d_cutin_get_model_instance`, which the raw preview relies on (its slot has character -1).
- Some rel_duel_draw functions have no copy in this range (e.g. `audio_build_cutin_voice_queue`, `audio_stop_cutin_voice`, `audio_select_cutin_voices_*`, `field_3d_cutin_is_current_finished`, `field_3d_cutin_stop_current`, `field_3d_cutin_skip_current`, `field_3d_cutin_find_bustup_gim`, `field_3d_cutin_get_slot_character/variant`).

Per-character families: 32 set-up routines in this range (set-up routine immediately before its block, as in rel_duel_draw). Each family has `*_setup_desc`, `*_on_motion_start`, `*_on_motion_end`, `*_map_node` (descriptor +0x24: generic node index 0..0x25 to model node index), `*_lookup_attach_offset`, `*_find_offset_entry`, `*_sort_offset_table`; tbl098cd9b0 and tbl098cda70 also have frame hooks that drive the extra effect, and tbl098cd860 / tbl098cdb30 have resolve-motion callbacks (motion 0x1a -> 0xf9/0xfa or 0xf6 by duel set-up byte +0x194). The family names reuse the rel_duel_draw family prefixes (`tbl098ccc60`, `chr1e`, ...), which name rel_duel_draw table addresses, not this module's. Character per set-up routine (from `field_3d_cutin_get_chara_setup`, 0x1f20): 0x3bd8 = 0x28, 0x3edc = 0x24 variant != 0, 0x4e20 = 7, 0x50c8 = 0x1e, 0x5384 = 0x18, 0x5640 = 0x1f, 0x58fc = 0x1c, 0x5bb8 / 0x6f88 / 0x7e88 = generic player models, 0x8144 = 0x24 variant 0, 0x8400 = 0x14 variants 0-1, 0x8824 = 0x90 and 0x14 variant 2, 0x8ae0 = 0x2a and 2/3 with variant > 2, 0x8d9c = 0x16, 0x9058 = 2 variant 1, 0x9368 / 0x9680 = 0x29 (variant != 0 / 0), 0x9a10 = 0x25 and 0x14 variant > 2, 0x9d94 = 0x13, 0xa09c = 0x23, 0xa358 = 0x22, 0xa614 = 8, 0xaa34 = 0x94, 0xace8 = 0x17, 0xafa4 = 0x19, 0xb2d4 = 6 variant >= 2, 0xb590 = 5 variant != 0, 0xb84c = 0x95, 0xbb8c = 0x20, 0xbe48 = 0x1a, 0xc104 = 3 variant 2. The rel_duel_draw set-up routines and map-node routines are still default-named (`FUN_09842f74`, `FUN_09843014`, ...); the names given here (`field_3d_cutin_<family>_setup_desc`, `..._map_node`) can be reused for them.

## Name mismatches (twin lines that are false matches)

Identical code after relocation masking made several `twin:` lines point at the wrong function; the names here follow the aligned rel_duel_draw function instead:

- 0x0000 `deck_editor_register_scene` -> `ui_cutin_viewer_register_scene`; 0x0f30 `system_wait_frame` -> `ui_cutin_viewer_stop_cutin_preview` (it calls 0x105ac and `field_3d_cutin_term_system`).
- 0x1ea0 / 0x1eb4 `audio_build_current_cutin_voice_queue` -> `field_3d_cutin_get_node_matrix_current` / `field_3d_cutin_get_attach_matrix_current` (their tail-call targets are `field_3d_cutin_get_node_matrix` / `get_attach_matrix`).
- 0x1f04 `audio_heap_free` -> `field_3d_cutin_set_current_disc_flag`; 0x267c `system_movie_set_work_memory` -> `ui_set_speed_lines_source`.
- 0x3ac8 `ui_ehf_get_frame_rate` -> `field_3d_cutin_get_frame_rate`; 0x3e40 / 0x3e68 `system_vector4_copy` -> `field_3d_copy_rotation` / `field_3d_copy_vec4`; 0x4a08 `system_matrix4_copy` -> `field_3d_copy_matrix4`; 0x0c1c keeps the BOOT name `ui_list_window_draw_text` (it is a module-local copy).
- All 32-byte per-character wrappers (twin `system_movie_call_umd_io_term`) -> `field_3d_cutin_<family>_on_motion_start` / `_on_motion_end`; all per-family find/sort/lookup routines whose twin line names `tbl098ccc60` (or `tbl098cd9b0` for the tbl098cda70 callbacks) -> their own family name.

## Open questions

- State 1 (raw file scan) is never entered by any code in this batch; is it reachable (another caller of `ui_cutin_viewer_set_state`, or a debug patch)?
- `container_read_file_from_start(3, path, 0x00043660, 10)` in `ui_cutin_viewer_load_file`: the destination 0x00043660 and size 10 do not fit a whole file; the documented prototype may be wrong for this call or 0x00043660 is a 10-byte handle record.
- Exact strings at 0x000394f4 (duel folder), 0x00039570 / 0x0003957c / 0x00039584 (member suffixes) were inferred from their use and lengths, not read.
- Helpers outside this batch that the code relies on: 0x2c38c / 0x2c590 / 0x2c750 / 0x2c8f8 (cut-in archive request, wait and look-up), 0x2bba0 / 0x2bc24 / 0x2bf28 / 0x2be5c / 0x2bfb0 / 0x2c0bc / 0x2c174 (card resources), 0x10518 / 0x105ac / 0x10618 / 0x106c0 (paired with the cut-in system; likely the effect-task manager), 0x2d18c-0x2d1c4 (module allocator).
Batch A2 covers module offsets 0x0000c374-0x000307d4 of `rel_cutin_viewer` (the second half). Almost all of
this range is a copy of `rel_duel_draw` code: the per-character cut-in descriptor blocks, the LP and number-pair
panels, the duel UI object list and draw-task pool, the display-list helpers, the cut-in effect tasks, the duel
resource/archive loaders and the shared-character cut-in block. The scene logic of the viewer itself lies in the
first half (batch A1).

## Per-character cut-in descriptor blocks

`field_3d_cutin_get_chara_setup` (0x00001f20, batch A1) maps a character id (and for some characters a variant) to
a set-up routine. In this module the switch names the routines directly, so each block can be tied to its
character with high confidence (no address-adjacency guess is needed, unlike in `rel_duel_draw`):

| Set-up routine | Character | Block name used |
| --- | --- | --- |
| 0x0000c104 (batch A1) | 3, variant 2 | `chr03v2` |
| 0x0000c3c0 | 0x1d | `chr1d` |
| 0x0000c67c | 0x15 | `chr15` |
| 0x0000c938 | 0x26 | `chr26` |
| 0x0000cbd8 | 4, variant != 0 | `chr04v1` |
| 0x0000ce94 | 4, variant 0 | `chr04v0` |
| 0x0000d150 | 0x21 | `tbl098ce740` (name of the identical `rel_duel_draw` block) |
| 0x0000d41c | 0x1b | `chr1b` |
| 0x0000d6d8 | 0x27 | `chr27` |
| 0x0002d3e4 | 9..0x12, 0x2b..0x2d, 0x96..0x98, 5 (variant 0), 6 (variants 0-1) | `shared` |
| 0x0002f7e0 | 2, variant 2 | `chr02v2` |
| 0x0002fd24 | 2, variant 0 | `chr02v0` |
| 0x00030274 | 3, variant 1 | `chr03v1` |
| 0x00030530 | 3, variant 0 (also character 2 with variant > 2) | `chr03v0` |

Other set-up routines of the switch lie in batch A1 (0x00003bd8 for 0x28, 0x00003edc for 0x24 variant != 0,
0x00004e20 for 7, 0x000050c8 for 0x1e, 0x00005384 for 0x18, 0x00005640 for 0x1f, 0x000058fc for 0x1c, 0x00008144,
0x00008400, 0x00008824, 0x00008ae0, 0x00008d9c, 0x00009058, 0x00009368, 0x00009680, 0x00009a10, 0x00009d94,
0x0000a09c, 0x0000a358, 0x0000a614, 0x0000aa34, 0x0000ace8, 0x0000afa4, 0x0000b2d4, 0x0000b590, 0x0000b84c,
0x0000bb8c, 0x0000be48, and the generic-model fall-backs 0x00005bb8, 0x00006f88, 0x00007e88).

A set-up routine patches the 0x38-byte descriptor filled by the default initialiser:

| Offset | Callback | Notes |
| --- | --- | --- |
| +0x14 | on-motion-start | usually a 32-byte wrapper around `field_3d_cutin_default_on_motion_start` (0x00004230) |
| +0x18 | on-motion-end | usually a wrapper around `field_3d_cutin_default_on_motion_end` (0x000042a4) |
| +0x1c | frame hook | thunk to `field_3d_cutin_default_frame_hook` (0x00004340), or a hook that also advances the extra effect (`shared`, `chr02v2`, `chr02v0`) |
| +0x20 | resolve-motion | only `shared` overrides it (0x0002f4e0) |
| +0x24 | map-node | per-block switch from the generic node id 0..0x25 to a node index of that character's model |
| +0x28 | attach-offset lookup | sorted 0x20-byte table: +0x00 attach id, +0x04 position, +0x10 rotation quaternion |
| +0x2c | voice-node callback | thunk to `field_3d_cutin_default_apply_voice_nodes` (0x000043f8) |
| +0x30 | voice-motion picker | `shared`, `chr02v2`, `chr02v0` only |
| +0x34 | table pointer | set by 0x0000d150 (0x00040c20) and by `shared` per character/variant key; its consumer is not in this batch |

The map-node switch and the attach tables are the per-character data the port needs for the cut-in models
(node ids 0x1b, 0x1c, 0x21..0x24 map to node 0 in every block read, so these logical nodes are absent from those
models). Several blocks first fold node 0x1d onto another id (0x15, 0x1a, 1, ...).

The pack headers paired the 32-byte on-motion-start/end wrappers with BOOT.BIN `system_movie_call_umd_io_term`
and many blocks' lookup/find/sort routines with the single `rel_duel_draw` block `tbl098ccc60`: the masked
relocations make every "call one function and return 0" body, and every block's lookup, look identical. Those
twin names would collide inside the module, so each block got its own names, keyed by character (`chrNN[vN]`),
or the `rel_duel_draw` name where the block is the same one (`tbl098ce740`, and the `field_3d_lookup_attach_offsets_a..e`
/ `field_3d_search_attach_offsets_*` / `field_3d_sort_attach_offsets_*` names of the shared, chr02v2, chr02v0,
chr03v1 and chr03v0 blocks, which sit in the same order and with the same sizes as in `rel_duel_draw`).
The `rel_duel_draw` blocks named `tbl0...` could be tied to characters with this module's switch: the identical
on-motion-start of 0x0000d1a8 shows that `rel_duel_draw` `tbl098ce740` is character 0x21, as that document already
guessed by adjacency.

## LP and number-pair panels

Identical to `rel_duel_draw`. Module addresses: LP panel state 0x00b4c484 (0x30 bytes: +0x00 duel object of the
open panel, +0x04..+0x10 saved perspective, +0x14..+0x20 Japanese textures lp_pnl01_j, lp_pnl02_j,
lp_pnl_nmb01_j, lp_pnl_nmb02_j, +0x24 lp_pnl_a01, +0x28 lp_pnl_nmb01_a, +0x2c pnl_a00.ehf), all members of duel
archive 0x80001. The 0x90-byte LP roll panel record and the 0x34-byte number-pair record have the layouts given in
the rows (same as `rel_duel_draw`).

## Duel UI objects and draw tasks

This module carries a reduced duel UI object system: `ui_cutin_viewer_init_duel_objects` (0x00010518),
`ui_cutin_viewer_term_duel_objects` (0x000105ac) and `ui_cutin_viewer_draw_duel_objects` (0x00010618) keep the
object list (sentinel 0x00b4c4b4, delete flag 0x00b4c4d0, 0x8a4-byte area) and the draw-task pool (serial
0x00b4cdb0, 254 slots of 0x1c bytes from 0x00b4cdb4, card quad 0x00b4cd58) but drop the attack markers, attack
pointer and zone highlights of `rel_duel_draw`. The other object/task routines are byte-identical copies.

## Name mismatches

- 0x00011814: twin header `deck_get_owner_current_recipe` (BOOT.BIN) is a false match; the body is
  `field_3d_get_main_camera_rotation_matrix`.
- 0x00011888: twin header `field_3d_scale_matrix_xyz` is a false match; it calls `system_gum_translate`
  (`field_3d_translate_matrix_xyz`).
- 0x0000d9a0: twin header `ui_init_cutin_subtitle`; it is the term-time copy (`ui_term_cutin_subtitle`).
- On-motion-start/end wrappers of the plain blocks: twin header `system_movie_call_umd_io_term` is a false match.
- 0x0002d1b4 / 0x0002d1c4: twin header `audio_heap_free` (BOOT.BIN); they are the module's heap allocate/free
  wrappers (`system_duel_draw_heap_alloc` / `system_duel_draw_heap_free`): every allocation of the module goes
  through 0x0002d1b4 and the module start 0x00000190 registers the pair as the field_3d allocator.
- 0x0002d18c / 0x0002d1a0: twin headers `system_movie_set_work_memory` and `system_adhoc_clear_ctl_events` are false
  matches; they set and clear the heap words 0x00e42198/0x00e4219c (`system_duel_draw_set_heaps` /
  `system_duel_draw_clear_heaps`).
- 0x00012010 / 0x00012058 / 0x000142c4 / 0x00016d18: twin headers `system_lcg_rand` / `system_effect_rand_float`;
  they are the two module LCG pairs `field_3d_fx_rand_int/unit` and `field_3d_cutin_fx_rand_int/unit`.
- 0x00012190: twin header `field_3d_get_main_scene_node_position`; it reads the attach matrix
  (`field_3d_cutin_get_attach_position`).
- 0x000122b8: twin header `audio_play_se_ex_once_at_frame`; it calls `audio_stop_sound`
  (`audio_stop_track_once_at_frame`).
- For batch A1 (not renamed here): the auto names of 0x00001ea0 and 0x00001eb4 (`audio_build_current_cutin_voice_queue`
  twice) look wrong. Their callers use them as `field_3d_cutin_get_node_matrix_current` (0x00001ea0, called by
  `field_3d_get_main_scene_node_position` and `field_3d_transform_point_by_main_scene_node`) and
  `field_3d_cutin_get_attach_matrix_current` (0x00001eb4, called by `field_3d_cutin_get_attach_position`), as in
  `rel_duel_draw` (confidence medium: based on the callers only).

## Cut-in effect tasks

The effect code (0x00011a80-0x0002b998) is a byte-identical copy of `rel_duel_draw`'s cut-in effect set; rows
reuse the `rel_duel_draw` names and descriptions with this module's addresses. Module data: cut-in fx block
0x00b4eaa0 (0x124 bytes: +0 variant word for `field_3d_create_cutin_fx_anim3e_54_by_variant`, +4 mode word set by
`field_3d_set_cutin_fx_word_04`, +8 animd5_e6 enable flag set by `field_3d_set_cutin_fx_word_08`, four 0x18-byte fx
slots from 0x00b4eaac; the aux layer-hook counters 0x00b4eb0c-0x00b4eb1c; the deck card list count 0x00b4eb20 and
up to 0x28 ids from 0x00b4eb24); saved GU matrices 0x00b4e990-0x00b4ea9c (projection, view, mode 3, model,
perspective) and the perspective restore record 0x00b4e97c; saved view matrices 0x00b4ebd0 + i * 0x40.
The fx texture name table is 0x00041184 (`field_3d_dl_bind_fx_texture`), which can pull textures from the
field-spell backdrop archives of cards 0x1346, 0x1349, 0x169f, 0x1323, 0x1345 and 0x1bfc.

## Files and archives (for the extractor)

- Duel resource tables (rodata, sorted once by `ui_sort_duel_resource_tables` with `ui_compare_resource_id`):
  models 0x0004179c (0x28 records x 0x18, instance cache +0x14), archives 0x00041c0c (4 records x 0xcc: +0 id,
  +4 default path stem, +0x34 + language * 4 per-language stems, +0xc4 buffer, +0xc8 loading flag; suffix
  string 0x00042620), textures 0x000421bc (0x23 x 0x10: id, archive id, member name, cache), layouts 0x0004251c
  (0xd x 0x14: id, archive id, .ehf name, .tmf name or NULL, cache). Same layouts as `rel_duel_draw`; files are
  loaded from root 4 with `container_load_file`. The viewer start (0x00000994, batch A1) waits for duel archive
  0x80001 and opens the card viewer with textures 0x40004, 0x40006, 0x40019, 0x40018, 0x40001 and layout 0x20001.
- Field-spell backdrops: `duel/bg/fmagic%04d.ehp` (format 0x00042628) loaded from root 3 into two 0x80000-byte
  buffers at 0x00d420e0 (slots 0x00d420b0, 0x18 bytes each); fallback `duel/bg/fmagic0000.ehp` (0x00042654) when the
  file is missing, larger than 0x7ffff bytes, or lacks a valid `filelist-ptrs.txt` member.
- Cut-in loading slots: `field_3d_cutin_viewer_setup_slots` (0x0002c38c) allocates one 0x483000-byte block
  (0x00e42194) and fills 0x2c-byte slots at 0x00e420e4 (count 0x00e420e0): +0 character, +4 variant, +8 cut-in
  archive buffer (0x17b000 bytes loaded), +0xc base (mini bust-up) archive buffer (0x20c00 for generic characters,
  else 0x4800 reserved; 0x20c00 bytes loaded), +0x10/+0x14 loading flags, +0x18/+0x1c loaded flags, +0x20 face/voice
  pending, +0x24 face loading, +0x28 voice loading. Base archive path: prefix 0x0004270c +
  `world_get_character_mini_bup_name` + suffix 0x00042620. Cut-in archive name: `world_get_character_cutin_name`,
  with fixed names for character 0x29 variant 0 (0x00038720) and 0x27 (0x00038708). Generic characters get a face
  texture from `cutin/da_faces/` + body folder (DA_girl, DA_boy_B, DA_boy_Y, DA_boy_R) + number (0x10500 bytes into
  the placeholder member at 0x0004266c) and a voice archive (`zakov%02d.ehp` with 0x32 + voice set index, or the
  fixed name 0x000426e4 for character 0x29; 0x10000 bytes into the placeholder 0x000426d0).
- Card art: `ui_create_card_art_readers` opens cardh.cip (reader at 0x00b500a0, 0x149000 bytes, pointer
  0x00b50098) and cardm.cip (0x00c990a0, 0xa9000 bytes, pointer 0x00b5009c); the card art list at 0x00b4ec90
  (count 0x00b50090) holds entry 0 and every token id 0xe88-0x1f39.

## Module heap

The module start (0x00000190, batch A1) creates a 0xb00000-byte heap at 0x0004bd50 (pointer 0x00043670), passes
it to `system_duel_draw_set_heaps` (0x00e42198; movie heap 0x00e4219c = 0) and registers
`system_duel_draw_heap_alloc/free` as the field_3d allocator. The module end (0x00000280) clears them and frees
the heap.

## Differences from rel_duel_draw found in this half

- `ui_cutin_viewer_is_cutin_display_enabled` (0x0002f7d8) returns 1 where `rel_duel_draw` asks the duel option
  `ui_is_cutin_display_enabled`: the viewer always loads cut-in archives.
- `field_3d_cutin_viewer_setup_slots` always reserves 0x483000 bytes (no 0x2ff000 setup-mode-2 case).
- The duel UI object init/term/draw routines drop the attack markers, attack pointer and zone highlights.

## Open questions

- The consumer of descriptor +0x34 (set to 0x00040c20 by the character 0x21 block and to per-character tables
  0x00042740-0x000427a0 by the shared block) is not in this batch; its record format (0x18 bytes apart) is unknown.
- 0x0002d1b4/0x0002d1c4 show empty bodies (unresolved tail jumps); the heap word 0x00e42198 is inferred from
  `system_duel_draw_set_heaps` and the `rel_duel_draw` twins (medium). A disassembly read would settle it.
- The node meaning of the generic map-node ids 0..0x25 (which bone each id is) is not established; only the
  per-character translation tables are recorded.
- The `rel_duel_draw` blocks named `tbl0...` could be mapped to characters by comparing their map-node switches
  with this module's character-keyed blocks (chr15, chr26, chr27, chr04v0/v1 have no `chrNN` counterpart in
  `rel_duel_draw` yet).
