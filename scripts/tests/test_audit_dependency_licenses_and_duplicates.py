"""Unit tests for audit_dependency_licenses_and_duplicates.py."""

import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_dependency_licenses_and_duplicates import (
    DEFAULT_APPROVED_LICENSES,
    DependencyAuditor,
    normalize_pkg_name,
    parse_package_json,
    parse_requirements_txt,
)


class TestDependencyAuditor(unittest.TestCase):
    def setUp(self):
        self.auditor = DependencyAuditor()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_normalize_pkg_name(self):
        self.assertEqual(normalize_pkg_name("React-Dom"), "react-dom")
        self.assertEqual(normalize_pkg_name("some_package.name"), "some-package-name")

    def test_check_license_approved(self):
        finding = self.auditor.check_license("MIT", "package.json")
        self.assertIsNone(finding)

        finding = self.auditor.check_license("Apache-2.0", "package.json")
        self.assertIsNone(finding)

    def test_check_license_disallowed(self):
        finding = self.auditor.check_license("AGPL-3.0-or-later", "package.json")
        self.assertIsNotNone(finding)
        self.assertEqual(finding["type"], "LICENSE_DISALLOWED")
        self.assertEqual(finding["severity"], "ERROR")

    def test_check_license_missing(self):
        finding = self.auditor.check_license("", "package.json")
        self.assertIsNotNone(finding)
        self.assertEqual(finding["type"], "LICENSE_MISSING")
        self.assertEqual(finding["severity"], "WARNING")

    def test_single_package_json_internal_version_conflict(self):
        pkg_data = {
            "file": "frontend/package.json",
            "name": "frontend",
            "license": "MIT",
            "dependencies": {"lodash": "^4.17.21"},
            "devDependencies": {"lodash": "^4.17.15"},
        }
        findings = self.auditor.check_single_package_json(pkg_data)
        conflict = [f for f in findings if f["type"] == "INTERNAL_VERSION_CONFLICT"]
        self.assertEqual(len(conflict), 1)
        self.assertEqual(conflict[0]["severity"], "ERROR")

    def test_cross_package_json_divergence(self):
        manifest1 = {
            "file": "frontend/package.json",
            "dependencies": {"axios": "^1.6.0"},
            "devDependencies": {},
        }
        manifest2 = {
            "file": "client/package.json",
            "dependencies": {"axios": "^0.27.2"},
            "devDependencies": {},
        }
        findings = self.auditor.check_cross_package_json([manifest1, manifest2])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["type"], "CROSS_PACKAGE_VERSION_DIVERGENCE")

    def test_requirements_txt_duplicate_conflict(self):
        req_file = self.base_path / "requirements.txt"
        req_file.write_text("requests==2.31.0\npytest>=7.0.0\nrequests==2.28.1\n")

        parsed = parse_requirements_txt(req_file)
        findings = self.auditor.check_requirements_txt([(req_file, parsed)])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["type"], "REQUIREMENTS_DUPLICATE_CONFLICT")
        self.assertEqual(findings[0]["severity"], "ERROR")

    def test_audit_directory_end_to_end(self):
        sub_dir = self.base_path / "app"
        sub_dir.mkdir()
        pkg_path = sub_dir / "package.json"
        pkg_path.write_text(json.dumps({
            "name": "sample",
            "license": "MIT",
            "dependencies": {"express": "4.18.2"},
        }))

        findings = self.auditor.audit_directory(self.base_path)
        # Should be completely clean with 0 findings
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
