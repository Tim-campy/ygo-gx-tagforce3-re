#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Regenerate every asset class the port needs from the maintainer's own extracted disc, in one command.

  extract_all.py <PSP_GAME> -o <OUT> [--only STEP[,STEP...]] [--skip STEP[,...]] [--ffmpeg PATH] [--no-ffmpeg]
                 [--dry-run] [--list]

<PSP_GAME> is the extracted UMD tree (tools/iso9660.py -x); <OUT> must lie outside the repository or under an
extracted/ directory (everything written is game data, CLAUDE.md legal boundary). Each step runs one existing
tool in its own process (python -I), so this script holds no format knowledge of its own: the table STEPS below
is the asset-class list of docs/PORT-READINESS.md and docs/extractor-spec.md, with the neutral output each tool
writes. Steps that need FFmpeg (ATRAC audio, movies) are skipped with --no-ffmpeg. A step that fails is reported
and the run continues; the exit code is 1 when any step failed.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
LANGS3 = ("eng", "fra", "ger", "ita", "spa")
LANGS1 = ("e", "f", "g", "i", "s")


def steps(game, out):
    """[(step id, asset class, needs ffmpeg, [tool argv after 'python -I tools/'], output path)]."""
    u, s = game / "USRDIR", game / "SYSDIR"
    boot, eng = s / "BOOT.BIN", u / "duelsys" / "cardinfo_eng.ehp"
    duel_eng, gm = u / "gmodule" / "rel_duel_eng.prx", u / "gmodule"
    plan = []

    def add(step, asset, argv, target, ffmpeg=False):
        plan.append((step, asset, ffmpeg, [str(a) for a in argv], target))

    for l3 in LANGS3:
        add(f"cards_{l3}", "card database", ["cardinfo.py", u / "duelsys" / f"cardinfo_{l3}.ehp", "--format", "json",
                                             "-o", out / "cards" / f"cards_{l3}.json"], out / "cards" / f"cards_{l3}.json")
        add(f"duel_prompts_{l3}", "duel prompt strings", ["cardinfo.py", u / "duelsys" / f"cardinfo_{l3}.ehp",
                                                          "--dialog", "--format", "json", "-o",
                                                          out / "cards" / f"dlg_{l3}.json"], out / "cards" / f"dlg_{l3}.json")
    add("card_art", "card art (512x512 JPEG)", ["cip.py", "jpeg", u / "card" / "cardj_a.cip", out / "card_art",
                                                "--boot", boot], out / "card_art")
    for name in [f"cardh_{l}" for l in LANGS1] + [f"cardm_{l}" for l in LANGS1] + ["card8_a"]:
        add(f"card_small_{name}", "card art (small renditions, PNG)",
            ["cip.py", "pngs", u / "card" / f"{name}.cip", out / "card_small" / name], out / "card_small" / name)
    add("packs", "booster packs", ["tables.py", "packs", gm / "rel_shop.prx", "--cardinfo", eng, "-o",
                                   out / "tables" / "packs.csv"], out / "tables" / "packs.csv")
    add("pack_odds", "booster packs", ["tables.py", "odds", gm / "rel_shop.prx", "--cardinfo", eng, "-o",
                                       out / "tables" / "pack_odds.csv"], out / "tables" / "pack_odds.csv")
    add("limit_list", "forbidden/limited list", ["tables.py", "limits", boot, "--cardinfo", eng, "-o",
                                                 out / "tables" / "limits.csv"], out / "tables" / "limits.csv")
    add("fusions", "fusion recipes", ["fusion.py", duel_eng, "recipes", "--cardinfo", eng, "-o",
                                      out / "tables" / "fusions.csv"], out / "tables" / "fusions.csv")
    add("rituals", "ritual table", ["fusion.py", duel_eng, "rituals", "--cardinfo", eng, "-o",
                                    out / "tables" / "rituals.csv"], out / "tables" / "rituals.csv")
    add("card_effects", "card effect specification", ["card_effects.py", duel_eng, eng, "--boot", boot, "--draw",
                                                      gm / "rel_duel_draw.prx", "-o", out / "card_effects"],
        out / "card_effects")
    add("ai_tables", "AI priority tables", ["ai_tables.py", duel_eng, "handlers", "--cardinfo", eng, "-o",
                                            out / "tables" / "ai_handlers.csv"], out / "tables" / "ai_handlers.csv")
    add("deck_recipes", "opponent decks", ["decks.py", "recipes", boot, "--cardinfo", eng, "-o",
                                           out / "decks" / "recipes.csv"], out / "decks" / "recipes.csv")
    add("deck_owners", "opponent decks", ["decks.py", "owners", boot, "--story", u / "script" / "story_scr_b.ehp",
                                          "-o", out / "decks" / "owners.json"], out / "decks" / "owners.json")
    add("characters", "character table", ["exe_tables.py", "dump", game, "boot_character_table", "-o",
                                          out / "tables" / "characters.json"], out / "tables" / "characters.json")
    for l1 in LANGS1:
        add(f"story_text_{l1}", "story and dialogue text", ["story.py", "text", u / "script" / f"story_scr_{l1}.ehp",
                                                            "-o", out / "story" / f"lines_{l1}.csv"],
            out / "story" / f"lines_{l1}.csv")
    add("story_events", "story event scripts", ["story.py", "events", u / "script" / "story_scr_b.ehp", "--text",
                                                u / "script" / "story_scr_e.ehp", "-o", out / "story" / "events.csv"],
        out / "story" / "events.csv")
    add("strings", "UI and system string tables", ["strtbl.py", "dump", u, boot, "-o", out / "strtbl"], out / "strtbl")
    add("textures", "textures (GIM to PNG)", ["gim.py", "batch", u, boot, "-o", out / "gim"], out / "gim")
    add("layouts", "2D layouts (EHF to JSON)", ["ehf.py", "json", u, boot, "-o", out / "ehf", "--no-frames",
                                                "--compact"], out / "ehf")
    add("scenes", "scene map (layouts and tables per screen)", ["scenes.py", "map", game, "-o",
                                                                 out / "scenes.json"], out / "scenes.json")
    add("models", "3D models, animations, field backdrops (glTF)", ["tgm.py", "gltf", "--all", u, "-o",
                                                                     out / "gltf"], out / "gltf")
    add("world_tables", "world and field tables", ["world.py", "tables", u, "-o", out / "world" / "tables.json"],
        out / "world" / "tables.json")
    add("world_maps", "free-roam maps", ["world.py", "locations", u, "-o", out / "world" / "maps"], out / "world" / "maps")
    add("world_chapters", "partner chapters", ["world.py", "chapters", u, "-o", out / "world" / "chapters.json"],
        out / "world" / "chapters.json")
    add("tutorial", "duel tutorials", ["tutorial.py", u / "d_tutorial" / "tutorial.ehp", "--json", "-o",
                                       out / "tutorial" / "d_tutorial.json"], out / "tutorial" / "d_tutorial.json")
    add("voices", "voice tables", ["voices.py", game, "-o", out / "audio" / "voices.csv"], out / "audio" / "voices.csv")
    add("sound_attributes", "sound attributes (SHDS)", ["exe_tables.py", "sound-attributes", game, "-o",
                                                        out / "audio" / "sound_attributes.csv"],
        out / "audio" / "sound_attributes.csv")
    add("audio", "music, effects and voices (OGG)", ["audio_convert.py", u / "snd" / "psp_snddat.bin", "-o",
                                                     out / "audio" / "snd", "--format", "ogg"],
        out / "audio" / "snd", ffmpeg=True)
    add("movies", "movies (MP4)", ["psmf.py", u / "movie", "--convert", "-o", out / "movie"], out / "movie",
        ffmpeg=True)
    return plan


def output_allowed(path):
    resolved = Path(path).resolve()
    if "extracted" in (part.lower() for part in resolved.parts):
        return True
    try:
        resolved.relative_to(TOOLS.parent.resolve())
    except ValueError:
        return True
    return False


def select(plan, only=None, skip=None, ffmpeg=True):
    chosen = []
    for item in plan:
        step = item[0]
        if only and not any(step == o or step.startswith(o + "_") for o in only):
            continue
        if skip and any(step == s or step.startswith(s + "_") for s in skip):
            continue
        if item[2] and not ffmpeg:
            continue
        chosen.append(item)
    return chosen


def main(argv=None, runner=subprocess.run):
    parser = argparse.ArgumentParser(description="Regenerate every asset class the port needs (game data: keep "
                                                 "the output out of git).")
    parser.add_argument("game", type=Path, nargs="?", help="extracted PSP_GAME directory")
    parser.add_argument("-o", "--output", type=Path, help="output directory (under extracted/ or outside the repo)")
    parser.add_argument("--only", help="comma-separated step ids or prefixes (see --list)")
    parser.add_argument("--skip", help="comma-separated step ids or prefixes to leave out")
    parser.add_argument("--ffmpeg", help="ffmpeg executable for the audio and movie steps (default: PATH)")
    parser.add_argument("--no-ffmpeg", action="store_true", help="leave out the steps that need FFmpeg")
    parser.add_argument("--dry-run", action="store_true", help="print the commands without running them")
    parser.add_argument("--list", action="store_true", help="list the steps and asset classes")
    args = parser.parse_args(argv)
    game = args.game or Path("<PSP_GAME>")
    out = args.output or Path("<OUT>")
    plan = steps(game, out)
    if args.list:
        for step, asset, ffmpeg, _, target in plan:
            print(f"{step:28} {asset}{' (FFmpeg)' if ffmpeg else ''}")
        return 0
    if args.game is None or args.output is None:
        parser.error("PSP_GAME and -o are required")
    if not output_allowed(args.output):
        print("error: write the output outside the repository or under an extracted/ directory", file=sys.stderr)
        return 2
    if not args.dry_run and not (args.game / "USRDIR").is_dir():
        print(f"error: {args.game} has no USRDIR (pass the extracted PSP_GAME directory)", file=sys.stderr)
        return 2
    chosen = select(plan, args.only.split(",") if args.only else None,
                    args.skip.split(",") if args.skip else None, not args.no_ffmpeg)
    failed = []
    for step, asset, ffmpeg, tool_argv, target in chosen:
        argv_full = [sys.executable, "-I", str(TOOLS / tool_argv[0])] + tool_argv[1:]
        if ffmpeg and args.ffmpeg:
            argv_full += ["--ffmpeg", args.ffmpeg]
        if args.dry_run:
            print(" ".join(f'"{a}"' if " " in a else a for a in argv_full))
            continue
        Path(target if target.suffix == "" else target.parent).mkdir(parents=True, exist_ok=True)
        start = time.time()
        result = runner(argv_full, capture_output=True, text=True, encoding="utf-8", errors="replace")
        status = "ok" if result.returncode == 0 else f"FAILED ({result.returncode})"
        tail = (result.stdout or "").strip().splitlines()[-1:] if result.returncode == 0 else \
            ((result.stderr or "") + (result.stdout or "")).strip().splitlines()[-3:]
        print(f"{status:12} {step:28} {time.time() - start:7.1f}s  {' | '.join(tail)}")
        if result.returncode:
            failed.append(step)
    if not args.dry_run:
        print(f"{len(chosen) - len(failed)} of {len(chosen)} steps ok" + (f"; failed: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
