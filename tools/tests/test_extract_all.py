#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/extract_all.py (no game data: the tools are replaced by a fake runner).

Run with: python3 -I tools/tests/test_extract_all.py
"""

import contextlib
import importlib.util
import io
import tempfile
import types
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("re_extract_all", TOOLS / "extract_all.py")
extract_all = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(extract_all)


def run(argv, runner=None):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = extract_all.main(argv, runner=runner) if runner else extract_all.main(argv)
    return code, out.getvalue()


class PlanTest(unittest.TestCase):
    def test_every_step_names_an_existing_tool(self):
        plan = extract_all.steps(Path("G"), Path("O"))
        ids = [p[0] for p in plan]
        self.assertEqual(len(ids), len(set(ids)))
        for step, asset, ffmpeg, argv, target in plan:
            self.assertTrue((TOOLS / argv[0]).is_file(), argv[0])
            self.assertTrue(str(target).startswith("O"), step)
        self.assertEqual({p[0] for p in plan if p[2]}, {"audio", "movies"})
        for wanted in ("cards_eng", "card_art", "card_effects", "textures", "layouts", "models", "story_events",
                       "world_maps", "tutorial", "sound_attributes", "audio", "movies"):
            self.assertIn(wanted, ids)

    def test_select(self):
        plan = extract_all.steps(Path("G"), Path("O"))
        self.assertEqual([p[0] for p in extract_all.select(plan, only=["cards"])],
                         [f"cards_{l}" for l in extract_all.LANGS3])
        self.assertNotIn("audio", [p[0] for p in extract_all.select(plan, ffmpeg=False)])
        self.assertNotIn("card_art", [p[0] for p in extract_all.select(plan, skip=["card_art"])])

    def test_list_and_dry_run(self):
        code, out = run(["--list"])
        self.assertEqual(code, 0)
        self.assertIn("models", out)
        with tempfile.TemporaryDirectory() as tmp:
            code, out = run([str(Path(tmp) / "PSP_GAME"), "-o", str(Path(tmp) / "extracted" / "port"),
                             "--dry-run", "--only", "tutorial"])
            self.assertEqual(code, 0)
            self.assertIn("tutorial.py", out)
            self.assertIn("--json", out)

    def test_refuses_output_inside_repository(self):
        code, _ = run(["G", "-o", str(TOOLS / "out"), "--dry-run"])
        self.assertEqual(code, 2)

    def test_runs_steps_and_reports_failures(self):
        calls = []

        def fake(argv, **kwargs):
            calls.append(argv)
            failing = argv[2].endswith("voices.py")
            return types.SimpleNamespace(returncode=1 if failing else 0, stdout="done\n", stderr="boom\n")

        with tempfile.TemporaryDirectory() as tmp:
            game = Path(tmp) / "PSP_GAME"
            (game / "USRDIR").mkdir(parents=True)
            out = Path(tmp) / "extracted" / "port"
            code, text = run([str(game), "-o", str(out), "--only", "voices,tutorial", "--no-ffmpeg"], runner=fake)
            self.assertEqual(code, 1)
            self.assertEqual(len(calls), 2)
            self.assertIn("1 of 2 steps ok; failed: voices", text)
            self.assertTrue((out / "tutorial").is_dir())
            code, text = run([str(Path(tmp) / "missing"), "-o", str(out)], runner=fake)
            self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
