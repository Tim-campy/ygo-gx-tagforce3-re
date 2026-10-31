# Audio engine (`audio`, work package 9)

The sound formats are in `docs/formats/sound.md`. This document records the function families of the resident sound driver in `BOOT.BIN` and the voice and BGM code of the modules. Addresses are runtime addresses.

## Function families named in the 2026-10-31 round

Basis and method: `system.md`, same section (Ghidra decompilation read in packs; each name with confidence and basis in `re/names*.csv`; nothing traced in PPSSPP).

### `BOOT.BIN` (227 names)

| Family | Count | Range / evidence |
| --- | --- | --- |
| `audio_sas` | 18 | `0x08818778`–`0x08818e2c`: the engine layer over sceSas. One core at `0x0891f900`, init flag `0x0891f8e4`, 32 voices at 44,100 Hz (`audio_sas_init`, `0x08818834`); `audio_sas_set_voice` (`0x08818b04`), `audio_sas_set_key_on` (`0x08818934`). |
| sound engine (`sound_header`, `audio_lists`, `audio_voices`, `sound_cue_fields`, `audio_tables`) | 47 | `0x08866b30`–`0x0886826c`: the "SHDS" header check (`0x08867938`), intrusive lists, voice lookup. |
| sound driver (`bank_loading`, `bank_table`, `sound_play`, `sound_stop`, `sound_handles`, `sound_lists`, `sound_streams`, `sound_scripts`, `sound_3d`, `faders`, `sas_voices`, `voice_mixer`, `output_effect`, `level_meter`, `volume`, `bgm`) | 136 | `0x08868554`–`0x088722f4`. Banks are loaded from `psp_snddat.bin` with heap callbacks; the "SP"/"EP" bank header and footer are checked by `0x08868814`. Bits `0x300000` of the sound key (object `+0x1c`) give the category: 0 BGM, `0x100000` sound effect, `0x300000` voice. Each sound object has 10-byte faders at `+0x50 + 10·i` (0 category volume, 1 fade-out, 3 volume, 6 pan, 7 pitch) whose times convert as ms × 10 / 58 (ticks of 256 samples at 44.1 kHz). Story commands confirm `0x0886c164` (stop), `0x0886c5c4` (release bank), `0x0886da0c` (play effect), `0x0886d8ec` (play BGM). |
| `duel_voice`, `sound_heap`, `audio_channels`, `atrac_config`, `audio_init`, `audio_random` | 37 | Duel voice queue and bank choice (below), sound heap, channel volumes, ATRAC set-up. |

Duel voice bank: `0x088419d4` returns 2 when the duel set-up byte `+0x192` is 2 (tag duel), else 0 when duelist 0 or 1 is the player (character < 2), else 1; the value is added to the first bank of the voice set. `0x08841a6c` converts a voice id into a global sound id (consistent with `sound.md`). `0x08841724` applies the three option volumes; channel 2 only when the language is 0.

### Modules

- `rel_duel_mgr` (54): `duel_voice_lines` (cut-in lines on UI events: LP and dominance mood, the character's key cards, LP damage, summons, consecutive attacks; M, because it assumes `rel_duel_draw` `0x0989d434(slot, line, card)` plays a line), `duel_voice_queue` (16 entries of 16 bytes at `0x08eba068`, H), `duel_mgr_audio` (duelist voice banks at `+0x1b4`/`+0x1b8`).
- `rel_duel_draw` (15): cut-in voice tables and queue; `0x0987a2b0` plays a sound effect once when a counter reaches the requested frame (53 callers).
- `rel_story` (12): story BGM.

## Round 2 of the 2026-10-31 naming

Method as in the first round (`system.md`): the still-unnamed functions were re-dumped from Ghidra with the current names, read in packs with full bodies (up to 160 lines), and named H/M with a basis in `re/names*.csv` under "round 2". 87 new `audio` names (75 in `BOOT.BIN`). The stop selectors are now read: `audio_stop_sounds_by_selector` (`0x0886c31c`) takes `0xfdfb` all sounds, `0xfdfa` BGM, `0xfdf9` sound effects, `0xfdf8` voices, `0xfdf7` effects and voices, and the wrappers `0x08841908`–`0x08841974` are `audio_stop_sounds_{all,bgm,se,voice,se_and_voice}[_arg]`. Other families: banks (10), streams (8), sound 3D (5), BGM (5), mix presets (5), cues and notes (8). `rel_duel_mgr`: eight `duel_voice_lines` handlers matched to UI events through the jump table of `audio_voice_dispatch_ui_event` (5 phase banner, 26 card moved, 34 activation shown, 67 draw, 76 end of turn; 39 unknown).

## Open questions

- Stream flags `+0xe0`–`+0xe3` (`0x08869ae8`–`0x08869d20`, set through `0x0886804c`) and the pause/resume candidates `0x0886a03c`, `0x0886a1c4`, `0x0886a454`, `0x0886a488`, `0x0886a5a4` are unnamed.
- ~~`0x088418f8` "stop the current track"~~: settled 2026-10-31. Its body is `audio_stop_sound(id, 0)`: it stops one sound id at once (no fade). The list window passes sound-effect ids and `audio_stop_duellist_voices` voice ids; it is now `audio_stop_sound_now` (H). The story `bgm_stop` path (`story.md`) uses it with a track id, which is the same call.
- ~~`0x090dbc60` tests 15 sounds~~: settled 2026-10-31, no conflict. `shop_is_clerk_voice_playing` checks whether any of the current clerk's 15 voice lines is playing (`0x79f1`–`0x79ff`, or `0x79de`–`0x79ec` for the other clerk, bit 0 of `0x0973ad50`; status bits `0x21`). The per-pack voices of `packs.md` are lines 3–7 of that bank (`0x79f4 + v`, `0x79e1 + v`); the other ten lines are the clerk's general speech.
