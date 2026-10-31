# Movies: the opening and the cut-ins

Question asked: is the opening sequence pre-rendered, and could it be redone? Short answers: **yes, it is a pre-rendered video**, and **replaying it is cheap, rebuilding it is not**. The file format is in `docs/formats/psmf-movies.md`.

## Is the opening pre-rendered? Yes

| Evidence | Result | Confidence |
| --- | --- | --- |
| `rel_title.prx` holds exactly one movie path, `movie/TF3_opening_a.pmf` | The title scene plays a file | H for the string, M for what it does with it (call site not traced) |
| The file is a PSMF movie: 66.8 s, 480 x 272, H.264 Main profile at 29.97 fps, ATRAC3plus audio, 18,049,024 bytes | A finished, encoded video | H |
| The player in BOOT.BIN is the generic `sceMpeg` pipeline (ring buffer feed, AVC decode, ATRAC decode); no drawing code is involved in the playback itself | The game only decodes and shows the frames | M (grouped by call set, not decompiled) |
| Frames sampled every 5.5 s (12 frames, kept under `extracted/`, not in the repository) show 2D anime-style character art with effects, a 3D-CG dragon sequence, and the game logo near the end (about 60 s) | Produced animation and CG, not in-game rendering | H (visual inspection) |

The title screen is different. `title/titlelogo.ehp` holds a single texture (`gx_psp_logo_e3.gim`), and `title_menu/title_menu_<l>.ehp` (244 members) holds GIM textures and EHF timelines (`docs/formats/ehf.md`), so the menu is drawn by the game from assets; only the opening is video (M: the menu code was not traced).

## Region variants: the `_a` files

The code names more movies than the disc contains. Eight names have no file on this European disc: `TF3_opening`, `TF3_staffroll`, `TF3_staffroll2`, `cyb_attack`, `cyb_summon`, `rampart_attack`, `rampart_summon` and `ouijaboard_death`. The disc has exactly the seven `_a` counterparts of the first seven (`TF3_opening_a`, `TF3_staffroll_a`, `TF3_staffroll2_a`, `cyb_attack_a`, `cyb_summon_a`, `rampart_attack_a`, `rampart_summon_a`), and no file at all for `ouijaboard_death`.

| Module | Movie paths it contains |
| --- | --- |
| `rel_title` | only `TF3_opening_a` |
| `rel_story` | only the two `_a` staff rolls |
| `rel_duel_draw` | 75 paths: 70 files that exist, plus the base names of `cyb` and `rampart` and `ouijaboard_death` |
| `rel_gallery` | 81 movie-like names: the 73 files plus the 8 missing ones |

Reading (M for the facts, L for the reason): the `_a` files are the alternate versions used by this release, and the base names belong to another release of the game; the opening and the staff rolls are the shots that carry the logo and credits text. The selection logic (a region flag, or the module build) was not traced. For the port this means: support the `_a` set found on the disc, and do not assume the base names exist.

## The other movies

The same pipeline plays 72 more files: two staff rolls (`rel_story`), 68 monster summon and attack cut-ins and two win scenes (`rel_duel_draw`), and the Gallery and Movie Viewer replay any of them. The cut-ins are short (4.5 - 20 s) CG clips and are the bulk of the 243 MiB. A port needs one answer for all 73 files, not only for the opening.

## Could it be redone?

"Redone" can mean three things; the cost and the legal position differ.

| Option | What it takes | Verdict |
| --- | --- | --- |
| **A. Replay the original** | Read the `.pmf` from the maintainer's own disc image at run time or at install time (the port never ships it). Skip the 0x800-byte header, demux the MPEG program stream, decode H.264 Main 480 x 272 at 30 fps and ATRAC3plus audio. The picture is 16:9, so it fits the 3DS top screen (400 x 240) at 400 x 225. | **Feasible, recommended.** The install-time conversion from the user's disc is specified and tested: `tools/psmf.py --convert` writes MP4 (H.264 copied, AAC audio aligned to the first frame) for all 73 files (`docs/formats/psmf-movies.md`, "Conversion"). Still open: the 3DS playback format that the installer re-encodes to; no 3DS code is written in this phase. |
| **B. Replace with a new, original sequence** | Build a new intro from assets the game already has: logo and menu art (EHF), character portraits and card art (`.cip`, GIM), monster models (TGM) rendered by the port, music from the sound banks. | **Feasible as a new work**, with the 3DS second screen as an extra. It would not be the original opening, and any use of the characters' artwork follows the same rights as the rest of the game's art. |
| **C. Re-create the original frame by frame** | Redraw or re-render every shot. The source animation (character drawings, effects, the CG dragon shots) exists only inside the encoded video: no layered art, models or timelines for it are on the disc. The in-game monster models are low-polygon PSP models and do not match the cut-in CG. | **Not a reverse-engineering task and not recommended.** It would be a hand-made copy of someone else's animation and music, and the project's legal boundary keeps the video itself out of the repository. |

What this means for the port plan: treat the 73 movies as **disc data to be converted from the user's own copy**, exactly like card art and audio, and keep a "skip movie" path so that the title screen does not depend on the decoder. Whether the original opening can be skipped by a button press is not known yet (open question).

## Registry additions

`tools/psmf.py` (list, check, and the FFmpeg conversion `--convert` / `--convert-check`), format rows `psmf_movie` and `psmf_audio_stream` (both `reimplemented` since the conversion), and seven player functions in BOOT.BIN (`system_movie_*`, named from their `sceMpeg` call sets).

## Open questions

- Which 3DS decode path plays the converted movies with enough margin (needs a measurement on hardware). The install-time conversion itself is done (`psmf.py --convert`); what remains is the target codec and resolution of the port-side re-encode.
- Call sites of `system_movie_play` in `rel_title`, `rel_story` and `rel_duel_draw`: when the opening starts (boot, after an idle timeout on the title screen), whether a button skips it, and what the game does if the file is missing.
- What selects between the base and the `_a` movie names, why `ouijaboard_death` has no file on this disc, and whether a localised variant per language exists (the opening has no language suffix).
- A PPSSPP check of the playback timing (`docs/verification/ppsspp-plan.md` has no movie check yet).
