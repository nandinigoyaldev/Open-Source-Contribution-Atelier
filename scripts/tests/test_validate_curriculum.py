#!/usr/bin/env python3
"""Unit tests for scripts/validate_curriculum.py."""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from validate_curriculum import main, validate

GOOD_QUIZ = {"question": "Q?", "options": ["a", "b"], "answer": 1}


def lesson(slug="intro", **overrides):
    data = {"slug": slug, "title": "Intro", "filePath": f"m1/{slug}.md"}
    data.update(overrides)
    return data


class ValidateCurriculumTests(unittest.TestCase):
    def build(self, lessons, files=None, quizzes=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "m1").mkdir()
        (root / "curriculum.json").write_text(
            json.dumps({"modules": [{"id": "m1", "lessons": lessons}]})
        )
        if quizzes is not None:
            (root / "quizzes.json").write_text(json.dumps(quizzes))
        for name, text in (files or {"intro": "## Hello\n"}).items():
            (root / "m1" / f"{name}.md").write_text(text, encoding="utf-8")
        return root

    def messages(self, root):
        return [f"{f}: {m}" for f, m in validate(root)]

    def test_valid_content_passes_and_exits_zero(self):
        root = self.build([lesson(quizzes=[GOOD_QUIZ])])
        self.assertEqual(validate(root), [])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--content-dir", str(root)]), 0)

    def test_missing_slug(self):
        root = self.build([lesson(slug="")], files={})
        self.assertTrue(any("missing slug" in m for m in self.messages(root)))

    def test_duplicate_slug(self):
        root = self.build([lesson(), lesson()])
        self.assertTrue(any("duplicate slug 'intro'" in m for m in self.messages(root)))

    def test_missing_lesson_file(self):
        root = self.build([lesson()], files={"other": "x"})
        self.assertIn(
            "curriculum.json: intro: file not found: m1/intro.md", self.messages(root)
        )

    def test_unclosed_front_matter(self):
        root = self.build([lesson()], files={"intro": "---\ntitle: Hi\n\n## Body\n"})
        self.assertTrue(
            any(
                "m1/intro.md: front matter is not closed" in m
                for m in self.messages(root)
            )
        )

    def test_malformed_front_matter_line(self):
        root = self.build([lesson()], files={"intro": "---\ntitle Hi!\n---\nBody\n"})
        self.assertTrue(
            any("malformed front matter on line 2" in m for m in self.messages(root))
        )

    def test_broken_internal_links(self):
        text = "[a](missing.md) [b](/lessons/nope) [c](https://x.dev) `[d](gone.md)`"
        root = self.build([lesson()], files={"intro": text})
        found = self.messages(root)
        self.assertTrue(any("missing.md (file not found)" in m for m in found))
        self.assertTrue(any("/lessons/nope (unknown lesson)" in m for m in found))
        self.assertFalse(any("gone.md" in m or "x.dev" in m for m in found))

    def test_valid_internal_links_pass(self):
        root = self.build(
            [lesson(), lesson("next")],
            files={"intro": "[n](next.md#top) [l](/lessons/next)", "next": "ok"},
        )
        self.assertEqual(validate(root), [])

    def test_quiz_answer_out_of_range_and_bad_options(self):
        bad = [
            {"question": "Q", "options": ["a", "b"], "answer": 5},
            {"question": "Q", "options": ["only"], "answer": 0},
        ]
        found = self.messages(self.build([lesson(quizzes=bad)]))
        self.assertTrue(any("answer index 5 out of range" in m for m in found))
        self.assertTrue(any("at least 2 entries" in m for m in found))

    def test_unknown_quiz_reference(self):
        root = self.build(
            [lesson(quizzes=["quiz-1", "quiz-9"])], quizzes={"quiz-1": GOOD_QUIZ}
        )
        found = self.messages(root)
        self.assertEqual(len(found), 1)
        self.assertIn("unknown quiz id 'quiz-9'", found[0])

    def test_invalid_json_exits_non_zero_and_names_file(self):
        root = self.build([lesson()])
        (root / "curriculum.json").write_text("{bad")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["--content-dir", str(root)]), 1)
        self.assertIn("curriculum.json: invalid JSON", out.getvalue())


if __name__ == "__main__":
    unittest.main()
