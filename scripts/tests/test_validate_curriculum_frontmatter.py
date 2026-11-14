import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from validate_curriculum_frontmatter import (
    parse_frontmatter,
    validate_metadata,
)


class TestCurriculumFrontmatterValidator(unittest.TestCase):
    def test_parse_valid_frontmatter(self):
        content = """---
title: "Git Rebase Fundamentals"
slug: git-rebase-fundamentals
difficulty: intermediate
estimated_time_minutes: 25
prerequisites: ["git-basics", "branching"]
---
# Lesson Content Here
"""
        meta, err = parse_frontmatter(content)
        self.assertEqual(err, "")
        self.assertIsNotNone(meta)
        self.assertEqual(meta["title"], "Git Rebase Fundamentals")
        self.assertEqual(meta["slug"], "git-rebase-fundamentals")
        self.assertEqual(meta["difficulty"], "intermediate")
        self.assertEqual(meta["estimated_time_minutes"], 25)
        self.assertEqual(meta["prerequisites"], ["git-basics", "branching"])

    def test_missing_frontmatter_delimiters(self):
        content = "# Just a markdown header without frontmatter"
        meta, err = parse_frontmatter(content)
        self.assertIsNone(meta)
        self.assertIn("delimiter", err.lower())

    def test_validate_valid_metadata(self):
        meta = {
            "title": "Resolving Merge Conflicts",
            "slug": "resolving-merge-conflicts",
            "difficulty": "advanced",
            "estimated_time_minutes": 30,
        }
        errors = validate_metadata(meta, "lesson.md")
        self.assertEqual(errors, [])

    def test_missing_required_fields(self):
        meta = {
            "title": "Incomplete Lesson",
        }
        errors = validate_metadata(meta, "lesson.md")
        self.assertTrue(any("slug" in e for e in errors))
        self.assertTrue(any("difficulty" in e for e in errors))

    def test_invalid_difficulty(self):
        meta = {
            "title": "Invalid Difficulty Lesson",
            "slug": "invalid-difficulty",
            "difficulty": "super-hard",
        }
        errors = validate_metadata(meta, "lesson.md")
        self.assertTrue(any("difficulty" in e for e in errors))

    def test_invalid_slug_format(self):
        meta = {
            "title": "Bad Slug Lesson",
            "slug": "Invalid_Slug!",
            "difficulty": "beginner",
        }
        errors = validate_metadata(meta, "lesson.md")
        self.assertTrue(any("slug" in e for e in errors))

    def test_strict_mode_enforces_estimated_time(self):
        meta = {
            "title": "No Time Lesson",
            "slug": "no-time-lesson",
            "difficulty": "beginner",
        }
        # Non-strict allows missing estimated_time_minutes
        self.assertEqual(validate_metadata(meta, "lesson.md", strict=False), [])
        # Strict requires estimated_time_minutes
        strict_errors = validate_metadata(meta, "lesson.md", strict=True)
        self.assertTrue(any("estimated_time_minutes" in e for e in strict_errors))


if __name__ == "__main__":
    unittest.main()
