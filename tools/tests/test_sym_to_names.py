#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Tests for tools/sym_to_names.py. Run with: python3 -I tools/tests/test_sym_to_names.py"""

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("re_sym", Path(__file__).resolve().parents[1] / "sym_to_names.py")
sym = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sym)

SAMPLE = """08804000 z_un_08804000,0098
08804f70 dl_write_framebuffer_ptr,0040
08809f0c sinf,00e0
0880d3f0 _malloc_r,0300
08819a1c vadd_q,001c
0881c550 matrix_mogrify,0080
088115e4 strcpy,0088
0887239C zz_sceIoRead,0008
09800000 zz_sceIoOpen,0008
garbage line
"""


class SymToNamesTest(unittest.TestCase):
    def test_classify(self):
        self.assertIsNone(sym.classify("z_un_08804000"))
        self.assertIsNone(sym.classify("zz_[UNK: 0xb4471b5e]"))
        self.assertEqual(sym.classify("zz_sceIoRead"), ("sdk", "sceIoRead"))
        self.assertEqual(sym.classify("sceGuFog"), ("sdk", "sceGuFog"))
        self.assertEqual(sym.classify("_sceGuUpdateStallAddr"), ("sdk", "_sceGuUpdateStallAddr"))
        self.assertEqual(sym.classify("dl_write_light_color"), ("sdk", "dl_write_light_color"))
        self.assertEqual(sym.classify("vadd_q"), ("system", "system_vfpu_vadd_q"))
        self.assertEqual(sym.classify("vector_length_t"), ("system", "system_vfpu_vector_length_t"))
        self.assertEqual(sym.classify("_malloc_r"), ("system", "system_malloc_r"))
        self.assertEqual(sym.classify("memcpy"), ("system", "system_memcpy"))

    def run_tool(self, *extra):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "game.sym"
            path.write_text(SAMPLE, encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(sym.main([str(path), "--range", "08804000-08872bfc", *extra]), 0)
        return [line for line in out.getvalue().splitlines() if not line.startswith("#")]

    def test_range_and_order(self):
        rows = self.run_tool()
        self.assertEqual(rows[0], "address,group,name")
        self.assertEqual(rows[1:], [
            "0x08804f70,sdk,dl_write_framebuffer_ptr", "0x08809f0c,system,system_sinf",
            "0x0880d3f0,system,system_malloc_r", "0x088115e4,system,system_strcpy",
            "0x08819a1c,system,system_vfpu_vadd_q", "0x0881c550,system,system_vfpu_matrix_mogrify",
            "0x0887239c,sdk,sceIoRead"])

    def test_create_unnamed(self):
        self.assertIn("0x08804000,,", self.run_tool("--create-unnamed"))


if __name__ == "__main__":
    unittest.main()
