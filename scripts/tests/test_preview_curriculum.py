#!/usr/bin/env python3
"""Unit tests for scripts/preview_curriculum.py."""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from preview_curriculum import (  # noqa: E402
    DEFAULT_CONTENT_DIR,
    calculate_reading_time,
    main,
    split_table_row,
)


def _lesson(slug="intro-git", **overrides):
    data = {
        "slug": slug,
        "title": "Intro to Git",
        "description": "Learn commits and branches.",
        "difficulty": "beginner",
        "points": 15,
        "filePath": f"module-1/{slug}.md",
    }
    data.update(overrides)
    return data


class PreviewCurriculumTests(unittest.TestCase):
    def build_content(
        self,
        lessons,
        files=None,
        quizzes=None,
        glossary=None,
    ) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "module-1").mkdir()
        (root / "curriculum.json").write_text(
            json.dumps(
                {
                    "modules": [
                        {
                            "id": "module-1",
                            "title": "Getting Started",
                            "lessons": lessons,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        if quizzes is not None:
            (root / "quizzes.json").write_text(json.dumps(quizzes), encoding="utf-8")
        if glossary is not None:
            (root / "glossary.json").write_text(json.dumps(glossary), encoding="utf-8")
        for rel_name, content in (files or {"intro-git": "## Overview\n"}).items():
            target = root / "module-1" / f"{rel_name}.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        return root

    def run_cli(self, *args: str):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def test_valid_slug_renders_metadata_quizzes_and_markdown(self):
        root = self.build_content(
            [_lesson(estimatedMinutes=8)],
            files={
                "intro-git": (
                    "---\n"
                    "title: Intro to Git\n"
                    "slug: intro-git\n"
                    "difficulty: beginner\n"
                    "---\n\n"
                    "# Welcome\n\n"
                    "> [!TIP]\n"
                    "> Keep commits focused.\n\n"
                    '[interactive-quiz id="q1"]\n'
                )
            },
            quizzes={
                "q1": {
                    "question": "What makes a good commit?",
                    "options": ["Everything at once", "One logical change"],
                    "answer": 1,
                }
            },
        )
        code, out, err = self.run_cli("intro-git", "--content-dir", str(root))
        self.assertEqual(code, 0, err)
        self.assertIn("=== Lesson Preview: Intro to Git ===", out)
        self.assertIn("Slug:       intro-git", out)
        self.assertIn("Module:     Getting Started (module-1)", out)
        self.assertIn("8 min (curriculum estimatedMinutes", out)
        self.assertIn("Frontmatter: title=Intro to Git", out)
        self.assertIn("[TIP] Keep commits focused.", out)
        self.assertIn("[QUIZ: q1] What makes a good commit?", out)
        self.assertIn("[*] 2. One logical change", out)

    def test_missing_estimated_minutes_uses_reading_time_calculation(self):
        words = " ".join(["word"] * 250)
        self.assertEqual(calculate_reading_time(words), 2)
        root = self.build_content(
            [_lesson()],
            files={"intro-git": f"## Long Lesson\n\n{words}\n"},
        )
        code, out, err = self.run_cli("intro-git", "--content-dir", str(root))
        self.assertEqual(code, 0, err)
        self.assertIn("2 min (calculated @ 200 wpm; body read time: 2 min)", out)

    def test_unknown_slug_fails_with_actionable_suggestions_and_content_dir(self):
        root = self.build_content(
            [_lesson("what-is-open-source"), _lesson("git-branching")],
            files={
                "what-is-open-source": "## Open Source\n",
                "git-branching": "## Branching\n",
            },
        )
        code, out, err = self.run_cli("what-is-open-sourc", "--content-dir", str(root))
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("Unknown lesson slug: 'what-is-open-sourc'", err)
        self.assertIn("Did you mean: what-is-open-source?", err)
        self.assertIn(f"--list-slugs --content-dir {root}", err)

    def test_malformed_slug_mentions_kebab_case_and_missing_arg_exits_two(self):
        root = self.build_content([_lesson("intro-git")])
        code_empty, _, err_empty = self.run_cli("--content-dir", str(root))
        self.assertEqual(code_empty, 2)
        self.assertIn("--list-slugs", err_empty)

        code_bad, _, err_bad = self.run_cli("Bad_Slug!", "--content-dir", str(root))
        self.assertEqual(code_bad, 1)
        self.assertIn("kebab-case", err_bad)

    def test_validation_failure_blocks_preview_with_diagnostics(self):
        root = self.build_content(
            [_lesson()],
            files={"intro-git": "[missing](does-not-exist.md)\n"},
        )
        code, out, err = self.run_cli("intro-git", "--content-dir", str(root))
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("Validation failed for lesson 'intro-git'", err)
        self.assertIn("does-not-exist.md", err)

    def test_shortcode_referencing_quiz_without_question_fails_cleanly(self):
        root = self.build_content(
            [_lesson()],
            files={"intro-git": '[interactive-quiz id="q1"]\n'},
            quizzes={"q1": {"options": ["yes", "no"], "answer": 0}},
        )
        code, out, err = self.run_cli("intro-git", "--content-dir", str(root))
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("quizzes.json", err)
        self.assertIn("missing question", err)

    def test_relative_image_paths_preserved_and_unsafe_schemes_stripped(self):
        root = self.build_content(
            [_lesson()],
            files={
                "intro-git": (
                    "![Diagram](./diagram.png)\n"
                    '<img src="./inline.png" alt="inline" />\n'
                    "![Bad](javascript:alert(1))\n"
                    '<img src="data:text/html,<script>1</script>" alt="xss" />\n'
                )
            },
        )
        (root / "module-1" / "diagram.png").write_bytes(b"png")
        (root / "module-1" / "inline.png").write_bytes(b"png")

        code_txt, out_txt, err_txt = self.run_cli(
            "intro-git", "--content-dir", str(root)
        )
        self.assertEqual(code_txt, 0, err_txt)
        self.assertIn("[IMAGE alt='Diagram' src='./diagram.png']", out_txt)
        self.assertIn("[IMAGE alt='inline' src='./inline.png']", out_txt)
        self.assertIn("[IMAGE alt='Bad' src='']", out_txt)
        self.assertIn("[IMAGE alt='xss' src='']", out_txt)

        code_html, out_html, err_html = self.run_cli(
            "intro-git", "--content-dir", str(root), "--format", "html"
        )
        self.assertEqual(code_html, 0, err_html)
        self.assertIn('<img src="./diagram.png" alt="Diagram" />', out_html)
        self.assertIn('<img src="./inline.png" alt="inline" />', out_html)
        self.assertNotIn("javascript:alert", out_html)
        self.assertNotIn("data:text/html", out_html)

    def test_indented_frontmatter_syntax_error_is_reported(self):
        root = self.build_content(
            [_lesson()],
            files={"intro-git": "---\ntitle: Intro\n  stray text\n---\n\n## Body\n"},
        )
        code, out, err = self.run_cli("intro-git", "--content-dir", str(root))
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("module-1/intro-git.md", err)
        self.assertIn("Invalid key-value syntax", err)

    def test_explicit_unresolved_shortcode_id_does_not_fallback_and_canonical_id_wins(
        self,
    ):
        manifest_quiz = {
            "question": "Manifest question?",
            "options": ["a", "b"],
            "answer": 0,
        }
        root = self.build_content(
            [_lesson(quizzes=[manifest_quiz])],
            files={
                "intro-git": (
                    '[interactive-quiz id="q1"]\n' '[interactive-quiz id="q11"]\n'
                )
            },
            quizzes={
                "q1": {
                    "id": "wrong-internal-id",
                    "question": "Bank question?",
                    "options": ["x", "y"],
                    "answer": 1,
                }
            },
        )
        code_txt, out_txt, err_txt = self.run_cli(
            "intro-git", "--content-dir", str(root)
        )
        self.assertEqual(code_txt, 0, err_txt)
        self.assertIn("[QUIZ: q1] Bank question?", out_txt)
        self.assertNotIn("wrong-internal-id", out_txt)
        self.assertIn("interactive-quiz 'q11' not found", out_txt)

        code_html, out_html, err_html = self.run_cli(
            "intro-git", "--content-dir", str(root), "--format", "html"
        )
        self.assertEqual(code_html, 0, err_html)
        self.assertIn("Unknown interactive-quiz id: q11", out_html)
        self.assertIn('<section class="lesson-quizzes">', out_html)
        self.assertIn("Manifest question?", out_html)

    def test_malformed_collections_and_invalid_utf8_fail_cleanly(self):
        # Non-list glossary terms / aliases skip cleanly rather than crashing.
        root_gloss = self.build_content(
            [_lesson()],
            glossary={"terms": 1},
        )
        code_g, _, err_g = self.run_cli("intro-git", "--content-dir", str(root_gloss))
        self.assertEqual(code_g, 0, err_g)

        root_aliases = self.build_content(
            [_lesson()],
            glossary={"terms": [{"id": "git", "term": "git", "aliases": 1}]},
        )
        code_a, _, err_a = self.run_cli("intro-git", "--content-dir", str(root_aliases))
        self.assertEqual(code_a, 0, err_a)

        # Non-list lessons in module reports diagnostic.
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        bad_mod_root = Path(tmp.name)
        (bad_mod_root / "curriculum.json").write_text(
            json.dumps({"modules": [{"id": "m1", "lessons": 1}]}), encoding="utf-8"
        )
        code_l, _, err_l = self.run_cli(
            "--list-slugs", "--content-dir", str(bad_mod_root)
        )
        self.assertEqual(code_l, 1)
        self.assertIn("m1", err_l)
        self.assertIn("'lessons' must be a list", err_l)

        # Non-list quizzes in lesson reports diagnostic.
        root_q = self.build_content([_lesson(quizzes=1)])
        code_q, _, err_q = self.run_cli("intro-git", "--content-dir", str(root_q))
        self.assertEqual(code_q, 1)
        self.assertIn("intro-git: 'quizzes' must be a list", err_q)

        # Invalid UTF-8 lesson file reports file path diagnostic.
        root_utf8 = self.build_content([_lesson()])
        (root_utf8 / "module-1" / "intro-git.md").write_bytes(b"\xff\xfe\xfd")
        code_u, _, err_u = self.run_cli("intro-git", "--content-dir", str(root_utf8))
        self.assertEqual(code_u, 1)
        self.assertIn("module-1/intro-git.md", err_u)

    def test_app_parsing_rules_tables_glossary_sanitization_and_shortcodes(self):
        self.assertEqual(
            split_table_row("| `git log | head` | Show recent commits |"),
            ["`git log | head`", "Show recent commits"],
        )
        root = self.build_content(
            [_lesson()],
            files={
                "intro-git": (
                    "## Table and Safety\n\n"
                    "<script>alert(1)</script>\n"
                    "[Click](javascript:alert(1)) a commit and `commit` once more.\n\n"
                    "| Command | Meaning |\n"
                    "|---|---|\n"
                    "| `git log \\| head` | First commit |\n\n"
                    "```mermaid\n"
                    "graph TD;\n"
                    "  A-->B;\n"
                    "```\n\n"
                    '[unknown-widget foo="bar"]\n'
                )
            },
            glossary={
                "terms": [
                    {
                        "id": "commit",
                        "term": "commit",
                        "aliases": ["commits"],
                        "short": "Saved snapshot",
                        "definition": "A saved snapshot.",
                    }
                ]
            },
        )
        code_txt, out_txt, err_txt = self.run_cli(
            "intro-git", "--content-dir", str(root)
        )
        self.assertEqual(code_txt, 0, err_txt)
        self.assertIn("Click (#)", out_txt)
        self.assertNotIn("javascript:alert", out_txt)
        self.assertIn("[MERMAID DIAGRAM]", out_txt)
        self.assertIn("Unsupported interactive component: unknown-widget", out_txt)
        self.assertIn("- commit (commit): Saved snapshot", out_txt)

        code_html, out_html, err_html = self.run_cli(
            "intro-git", "--content-dir", str(root), "--format", "html"
        )
        self.assertEqual(code_html, 0, err_html)
        self.assertNotIn("<script>", out_html)
        self.assertIn('href="#"', out_html)
        self.assertIn('data-glossary-id="commit"', out_html)
        self.assertEqual(out_html.count('data-glossary-id="commit"'), 1)
        self.assertIn("<code>commit</code>", out_html)

    def test_list_slugs_prints_catalog(self):
        root = self.build_content([_lesson("alpha"), _lesson("beta")])
        code, out, err = self.run_cli("--list-slugs", "--content-dir", str(root))
        self.assertEqual(code, 0, err)
        self.assertIn("alpha  [module-1]", out)
        self.assertIn("beta  [module-1]", out)

    def test_real_repository_curriculum_lesson_preview(self):
        if not (DEFAULT_CONTENT_DIR / "curriculum.json").is_file():
            self.skipTest("Repository curriculum.json not found")
        code, out, err = self.run_cli("what-is-open-source")
        self.assertEqual(code, 0, err)
        self.assertIn("=== Lesson Preview: What is Open Source? ===", out)
        self.assertIn("[QUIZ: quiz-1]", out)
        self.assertIn("Glossary Terms Highlighted", out)


if __name__ == "__main__":
    unittest.main()
