# `.vtmt`: cut-in lip-sync animation (registry key `tgm_vtmt`)

A `.vtmt` file is a `TGMT` node animation (layout in [`tgm.md`](tgm.md), "TGMT") whose nine nodes drive the face bones of a duellist's cut-in model while that duellist's voice plays. It is not a separate binary format: the extractor reads it with the TGMT reader; this page records what is specific to it (members, header values, node mapping, playback) so that the port can play it. Little-endian like every TGM file.

Status: `documented` (2026-11-04). Basis: the loader `field_3d_cutin_load_voice_anim` (`rel_duel_draw` `0x098421e0`), the slot update `field_3d_update_cutin` (`0x09841ee4`), the pose hook `field_3d_cutin_pose_node_hook` (`0x09842c20`), the default voice-node callback `field_3d_cutin_default_apply_voice_nodes` (`0x09843794`) and `field_3d_cutin_apply_voice_tracks` (`0x09843b74`), all read in Ghidra and checked against capstone; the member survey with `tools/tgm.py list` over the maintainer's `duel/` directory.

## Members

| Member | Archives | Notes |
| --- | --- | --- |
| `voice01.vtmt.gz` | 86 of the 100 `duel/cutin_*.ehp` | gzip-wrapped (`ehp.md`, unnamed `.gz` member convention), inflated by the game into a `0x10000`-byte buffer. |
| `voice02.vtmt.gz` | 2 (`cutin_rei03.ehp`, `cutin_rei04.ehp`) | Alternative for motions `0x15`–`0x1c` and `0x88`–`0x90` (below). Both archives also carry `voice01`. |

The 14 cut-in archives without a `.vtmt` play their cut-ins without lip sync (the slot's lip-sync pointer stays 0).

## Header values seen (88 files)

| Field (TGMT header) | Value |
| --- | --- |
| `0x1C` node count | 9 in every file |
| `0x20` scalar track count | 54 (9 nodes × translation 3 + scale 3) |
| `0x24` scalar key count | 54 in 86 files (one key per track: constant translation and scale); 2,229 and 2,397 in two files whose translation/scale tracks are animated too |
| `0x28` rotation track count | 9 (one per node) |
| `0x2C` rotation key count | 112–1,731 |
| `0x30` frame count | 301 (56 files), 375 (23), 246 (9); about 10 s, 12.5 s and 8.2 s at 30 frames per second |
| `0x34` flags | 2 (nodes ignore their parents; rotations stored as 4 × f32) |

Node *i* uses translation track `6i`, rotation track `i` and scale track `6i + 3` in every file (`tools/tgm.py inspect`). There are no leading scene tracks (unlike the `-etc.tmt` camera files).

## How the game uses it

1. **Load** (`field_3d_cutin_load_voice_anim`, called by `field_3d_cutin_start_motion` for every cut-in motion): looks up `voice01.vtmt.gz` in the character's cut-in archive; when the requested motion (slot `+0x6c`) is in `0x15`–`0x1c` or `0x88`–`0x90` and `voice02.vtmt.gz` exists, that one is used instead. The member is inflated into the slot's buffer (`+0x64`, `0x10000` bytes from the duel draw heap, allocated once), bound with `field_3d_bind_tmt`, stored at slot `+0x60` (0 when missing) and its time `+0x68` is reset to 0.
2. **Clock** (`field_3d_update_cutin`): every frame `dt` (seconds) is added to `+0x68` while `+0x60` is set, independently of the body animation.
3. **Pose** (`field_3d_cutin_pose_node_hook`, the per-node hook of the cut-in model): needs the character descriptor's voice-node callback (`+0x2c`) and a loaded `.vtmt`. For non-generic characters nothing is applied during motions 1, `0x12`, `0x13`, `0x14`, and during `0x1a` unless the character is 9 or `0x13`. Otherwise the sample time is `+0x68 × frame rate` when the duellist (slot `+0x38`) has a queued voice whose level (`audio_get_sound_level(id, 1)`) is at least 10, and **0 (the rest pose, mouth closed) when the voice is silent or quieter**. So the mouth moves only while the voice is audible; the `.vtmt` is a generic talking loop, not a per-line lip-sync track.
4. **Apply** (`field_3d_cutin_default_apply_voice_nodes`): the nine logical face-node ids of the table `0x098ccda0` (4, 5, … 12) are mapped to mesh bones through the descriptor's map-node callback (`+0x24`, `field_3d_cutin_call_map_node`; per-character blocks supply it, the default returns 0); when the bone being posed matches id *i*, `field_3d_cutin_apply_voice_tracks` replaces its matrix: parent matrix (flag 2 is not used here: the hook passes the real parent), then translation from tracks `6i..6i+2`, rotation from track `i` (quaternion, slerp between keys), scale from tracks `6i+3..6i+5`, each skipped when its track index is `0xFFFF`.

Sampling beyond the last key holds the last value (TGMT rotation sampling, `tgm.md`), so a voice longer than the file keeps the final face pose; whether the game wraps the time could not be seen in the code (no wrap is applied to `+0x68`; medium).

## For the port

- Extract: inflate the member and read it as a TGMT (`tools/tgm.py`); keep the nine node records, their tracks and the frame count.
- Play: per cut-in slot keep a clock in seconds; when the duellist's voice level is >= 10 sample frame `clock × 30`, else frame 0; overwrite the bones selected by the character's node map. VFPU parts of the pose path (quaternion to matrix, scaling) were read from pseudo-ops and the TGMT conventions in `tgm.md` (lower confidence for the exact matrix order, high for the data flow).

## Open questions

- The per-character node maps (descriptor `+0x24` callbacks in the `cutin_chara_blocks` family): which mesh bones the ids 4–12 select for each character.
- Whether the voice level threshold 10 is on the same scale as the SHDS level meter of `audio.md` (it comes from `audio_get_sound_level(id, 1)`).
