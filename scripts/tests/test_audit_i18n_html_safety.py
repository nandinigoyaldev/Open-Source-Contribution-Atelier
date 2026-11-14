"""Unit tests for audit_i18n_html_safety.py."""

import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_i18n_html_safety import (
    I18nSafetyAuditor,
    audit_translation_string,
    walk_json_strings,
)


class TestI18nSafetyAuditor(unittest.TestCase):
    def setUp(self):
        self.auditor = I18nSafetyAuditor()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_walk_json_strings(self):
        data = {
            "auth": {
                "welcome": "Welcome back!",
                "errors": ["Error 1", "Error 2"],
            }
        }
        res = walk_json_strings(data)
        self.assertEqual(len(res), 3)
        self.assertEqual(res[0], ("auth.welcome", "Welcome back!"))
        self.assertEqual(res[1], ("auth.errors[0]", "Error 1"))

    def test_audit_safe_html_formatting(self):
        text = "Hello <b>world</b>! Please click <i>here</i> or read the <a href='https://example.com'>docs</a>."
        findings = audit_translation_string(text, "home.greeting", "en.json", self.auditor.safe_tags)
        self.assertEqual(findings, [])

    def test_audit_dangerous_script_tag(self):
        text = "Welcome <script>alert(1)</script>"
        findings = audit_translation_string(text, "welcome", "en.json", self.auditor.safe_tags)
        self.assertTrue(any(f["type"] == "DANGEROUS_HTML_TAG" for f in findings))
        self.assertTrue(any(f["severity"] == "ERROR" for f in findings))

    def test_audit_unsafe_event_handler(self):
        text = "Image: <img src='avatar.png' onerror='alert(document.cookie)'>"
        findings = audit_translation_string(text, "user.avatar", "en.json", self.auditor.safe_tags)
        self.assertTrue(any(f["type"] == "UNSAFE_EVENT_HANDLER" for f in findings))

    def test_audit_unsafe_javascript_uri(self):
        text = "Click <a href='javascript:stealTokens()'>here</a>"
        findings = audit_translation_string(text, "nav.link", "en.json", self.auditor.safe_tags)
        self.assertTrue(any(f["type"] == "UNSAFE_JAVASCRIPT_URI" for f in findings))

    def test_scan_directory_with_nested_locales(self):
        locales_dir = self.base_path / "frontend" / "locales"
        locales_dir.mkdir(parents=True)
        en_file = locales_dir / "en.json"
        en_file.write_text(json.dumps({
            "header": {
                "title": "Clean Title",
                "malicious": "Click <iframe src='http://evil.com'></iframe>",
            }
        }))

        findings = self.auditor.scan_directory(self.base_path)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["type"], "DANGEROUS_HTML_TAG")
        self.assertEqual(findings[0]["key"], "header.malicious")


if __name__ == "__main__":
    unittest.main()
