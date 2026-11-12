"""Unit tests for track_todo_annotations.py."""

import datetime
import tempfile
import unittest
from pathlib import Path

from scripts.track_todo_annotations import (
    TodoTracker,
    parse_line_annotation,
    parse_metadata,
)


class TestTodoTracker(unittest.TestCase):
    def setUp(self):
        self.ref_date = datetime.date(2026, 6, 1)
        self.tracker = TodoTracker(reference_date=self.ref_date)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_parse_metadata_combinations(self):
        author, date, issue = parse_metadata("harshit, 2026-04-15, #100")
        self.assertEqual(author, "harshit")
        self.assertEqual(date, datetime.date(2026, 4, 15))
        self.assertEqual(issue, "#100")

        author, date, issue = parse_metadata("#456")
        self.assertIsNone(author)
        self.assertIsNone(date)
        self.assertEqual(issue, "#456")

        author, date, issue = parse_metadata(None)
        self.assertIsNone(author)
        self.assertIsNone(date)
        self.assertIsNone(issue)

    def test_parse_line_annotation_simple(self):
        line = "    // TODO: implement graceful retry mechanism"
        res = parse_line_annotation(line, 42, "src/api.ts", self.ref_date)
        self.assertIsNotNone(res)
        self.assertEqual(res["tag"], "TODO")
        self.assertEqual(res["line"], 42)
        self.assertEqual(res["message"], "implement graceful retry mechanism")
        self.assertFalse(res["is_expired"])

    def test_parse_line_annotation_expired(self):
        line = "# FIXME(team, 2026-01-01): resolve memory leak"
        res = parse_line_annotation(line, 10, "server.py", self.ref_date)
        self.assertIsNotNone(res)
        self.assertEqual(res["tag"], "FIXME")
        self.assertEqual(res["author"], "team")
        self.assertTrue(res["is_expired"])
        self.assertGreater(res["days_overdue"], 0)

    def test_parse_line_annotation_future_not_expired(self):
        line = "/* HACK(dev, 2026-12-31): temporary fallback */"
        res = parse_line_annotation(line, 88, "client.js", self.ref_date)
        self.assertIsNotNone(res)
        self.assertEqual(res["tag"], "HACK")
        self.assertFalse(res["is_expired"])
        self.assertEqual(res["days_overdue"], 0)

    def test_scan_directory(self):
        test_file = self.base_path / "service.py"
        test_file.write_text(
            "# Normal comment\n"
            "# TODO(#99): optimize database query\n"
            "def run():\n"
            "    # FIXME(alice, 2025-10-10): remove workaround\n"
            "    pass\n"
        )

        findings = self.tracker.scan_directory(self.base_path)
        self.assertEqual(len(findings), 2)

        todo_item = [f for f in findings if f["tag"] == "TODO"][0]
        self.assertEqual(todo_item["issue"], "#99")
        self.assertFalse(todo_item["is_expired"])

        fixme_item = [f for f in findings if f["tag"] == "FIXME"][0]
        self.assertEqual(fixme_item["author"], "alice")
        self.assertTrue(fixme_item["is_expired"])


if __name__ == "__main__":
    unittest.main()
