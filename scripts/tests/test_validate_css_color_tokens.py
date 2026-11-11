"""Unit tests for validate_css_color_tokens.py."""

import tempfile
import unittest
from pathlib import Path

from scripts.validate_css_color_tokens import (
    CssColorTokenValidator,
    is_valid_hex_color,
)


class TestCssColorTokenValidator(unittest.TestCase):
    def setUp(self):
        self.validator = CssColorTokenValidator(allow_css_var_definitions=True)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_is_valid_hex_color(self):
        self.assertTrue(is_valid_hex_color("fff"))
        self.assertTrue(is_valid_hex_color("ffffff"))
        self.assertTrue(is_valid_hex_color("12345678"))
        self.assertFalse(is_valid_hex_color("zzzz"))
        self.assertFalse(is_valid_hex_color("12"))

    def test_scan_line_detected_hex(self):
        line = "    color: #ff5733;"
        findings = self.validator.scan_line(line, 10, "styles.css")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["hex"], "#ff5733")

    def test_scan_line_allowed_css_variable(self):
        line = "    --primary-color: #0070f3;"
        findings = self.validator.scan_line(line, 5, "styles.css")
        self.assertEqual(findings, [])

    def test_scan_line_ignore_pragma(self):
        line = "    background: #112233; /* allow-hex */"
        findings = self.validator.scan_line(line, 12, "styles.css")
        self.assertEqual(findings, [])

    def test_scan_directory(self):
        css_file = self.base_path / "main.css"
        css_file.write_text(
            ":root {\n"
            "    --bg: #000000;\n"
            "}\n"
            ".btn {\n"
            "    background-color: #3b82f6;\n"
            "    border: 1px solid var(--border);\n"
            "}\n"
        )

        findings = self.validator.scan_directory(self.base_path)
        # Only the .btn line should be flagged, not the --bg definition
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["hex"], "#3b82f6")


if __name__ == "__main__":
    unittest.main()
