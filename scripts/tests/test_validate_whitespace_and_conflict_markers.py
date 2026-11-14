#!/usr/bin/env python3
"""
Unit tests for validate_whitespace_and_conflict_markers.py
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.validate_whitespace_and_conflict_markers import (
    collect_target_files,
    fix_trailing_whitespace,
    inspect_file,
    run_validation,
)


class TestValidateWhitespaceAndConflictMarkers(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_clean_file_produces_no_violations(self):
        clean_file = self.root / "clean.py"
        clean_file.write_text("def hello():\n    return 'world'\n", encoding="utf-8")

        violation = inspect_file(clean_file)
        self.assertEqual(len(violation.conflict_markers), 0)
        self.assertEqual(len(violation.trailing_whitespace), 0)

    def test_detects_git_conflict_markers(self):
        conflict_file = self.root / "conflict.ts"
        conflict_file.write_text(
            "const x = 1;\n<<<<<<< HEAD\nconst a = 2;\n=======\nconst a = 3;\n>>>>>>> main\n",
            encoding="utf-8",
        )

        violation = inspect_file(conflict_file)
        self.assertEqual(len(violation.conflict_markers), 3)
        markers = [line_no for line_no, _ in violation.conflict_markers]
        self.assertEqual(markers, [2, 4, 6])

    def test_detects_and_fixes_trailing_whitespace(self):
        whitespace_file = self.root / "dirty.js"
        whitespace_file.write_text("let x = 10;   \nlet y = 20;\t\n", encoding="utf-8")

        violation = inspect_file(whitespace_file)
        self.assertEqual(violation.trailing_whitespace, [1, 2])

        remediated = fix_trailing_whitespace(whitespace_file)
        self.assertTrue(remediated)

        re_inspected = inspect_file(whitespace_file)
        self.assertEqual(len(re_inspected.trailing_whitespace), 0)
        self.assertEqual(whitespace_file.read_text(encoding="utf-8"), "let x = 10;\nlet y = 20;\n")

    def test_collects_target_files_respecting_excludes(self):
        (self.root / "src").mkdir()
        (self.root / "node_modules").mkdir()

        f1 = self.root / "src" / "index.ts"
        f1.write_text("console.log('hi');\n", encoding="utf-8")

        f2 = self.root / "node_modules" / "dep.js"
        f2.write_text("module.exports = {};\n", encoding="utf-8")

        files = collect_target_files(self.root)
        self.assertIn(f1, files)
        self.assertNotIn(f2, files)

    def test_run_validation_aggregates_violations(self):
        dirty = self.root / "sample.py"
        dirty.write_text("print('hello')   \n<<<<<<< HEAD\nprint('bye')\n>>>>>>> dev\n", encoding="utf-8")

        violations, fixed_count = run_validation(self.root, fix=False)
        self.assertEqual(len(violations), 1)
        self.assertEqual(len(violations[0].conflict_markers), 2)
        self.assertEqual(len(violations[0].trailing_whitespace), 1)
        self.assertEqual(fixed_count, 0)


if __name__ == "__main__":
    unittest.main()
