"""Unit tests for scripts/release_license_report.py and consolidated allowlist integration."""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.scripts.check_dependency_allowlist import (  # noqa: E402
    main as allowlist_main,
)
from scripts.release_license_report import (  # noqa: E402
    generate_release_license_report,
    main as license_main,
)


class ReleaseLicenseReportTests(unittest.TestCase):
    def build_workspace(
        self,
        *,
        npm_packages=None,
        requirements_lines=None,
        external_py_json=None,
    ) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "frontend").mkdir()
        (root / "backend").mkdir()

        lock_payload = {
            "name": "frontend",
            "lockfileVersion": 3,
            "packages": {
                "": {"name": "frontend", "version": "0.1.0"},
                **(
                    npm_packages
                    if npm_packages is not None
                    else {
                        "node_modules/react": {
                            "version": "19.0.0",
                            "license": "MIT",
                        },
                        "node_modules/@scope/pkg": {
                            "version": "1.2.3",
                            "license": "Apache-2.0",
                            "dev": True,
                        },
                    }
                ),
            },
        }
        (root / "frontend" / "package-lock.json").write_text(
            json.dumps(lock_payload), encoding="utf-8"
        )
        (root / "backend" / "requirements.txt").write_text(
            "\n".join(
                requirements_lines
                if requirements_lines is not None
                else ["Django>=5.0,<5.1", "pytest>=7.4.0"]
            )
            + "\n",
            encoding="utf-8",
        )
        if external_py_json is not None:
            (root / "py-licenses.json").write_text(
                json.dumps(external_py_json), encoding="utf-8"
            )
        return root

    def test_covers_frontend_and_backend_and_is_reproducible(self):
        root = self.build_workspace(
            external_py_json=[
                {"Name": "Django", "Version": "5.0.8", "License": "BSD-3-Clause"},
                {"Name": "pytest", "Version": "8.3.0", "License": "MIT"},
            ]
        )
        first = generate_release_license_report(
            root, external_python_metadata=root / "py-licenses.json"
        )
        second = generate_release_license_report(
            root, external_python_metadata=root / "py-licenses.json"
        )
        self.assertEqual(json.dumps(first, indent=2), json.dumps(second, indent=2))
        self.assertEqual(first["summary"]["frontend_packages"], 2)
        self.assertEqual(first["summary"]["backend_packages"], 2)
        self.assertEqual(first["summary"]["approved_count"], 4)
        self.assertEqual(first["summary"]["unknown_count"], 0)
        self.assertTrue(first["summary"]["passed"])
        self.assertEqual(first["by_ecosystem"]["npm"]["total"], 2)
        self.assertEqual(first["by_ecosystem"]["pypi"]["total"], 2)

    def test_unknown_and_disallowed_licenses_flagged_and_fail_strictly(self):
        root = self.build_workspace(
            npm_packages={
                "node_modules/missing-lic": {"version": "1.0.0"},
                "node_modules/lgpl-pkg": {
                    "version": "1.5.0",
                    "license": "LGPL-3.0-only",
                },
                "node_modules/copyleft-pkg": {
                    "version": "2.0.0",
                    "license": "AGPL-3.0",
                },
            },
            requirements_lines=["uninstalled-secret-lib==1.0.0"],
            external_py_json=[],
        )
        out_path = root / "license-report.json"
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = license_main(
                [
                    "--root",
                    str(root),
                    "--python-licenses-json",
                    str(root / "py-licenses.json"),
                    "--output",
                    str(out_path),
                    "--strict",
                ]
            )
        self.assertEqual(code, 1)
        written = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(written["summary"]["unknown_count"], 2)
        self.assertEqual(written["summary"]["unapproved_count"], 1)
        self.assertEqual(written["summary"]["disallowed_count"], 1)
        self.assertFalse(written["summary"]["passed"])
        self.assertIn(
            "[DISALLOWED] npm copyleft-pkg@2.0.0 (AGPL-3.0)", stdout.getvalue()
        )
        self.assertNotIn("lgpl-pkg", stdout.getvalue())
        self.assertIn("[UNKNOWN] npm missing-lic@1.0.0", stdout.getvalue())

    def test_consolidated_allowlist_report_embeds_dependency_licenses(self):
        root = self.build_workspace(
            npm_packages={
                "node_modules/unknown-pkg": {"version": "0.1.0", "license": "NONE"},
            },
            requirements_lines=["requests==2.32.0"],
            external_py_json=[
                {"Name": "requests", "Version": "2.32.0", "License": "Apache-2.0"}
            ],
        )
        reports_dir = root / "reports"
        reports_dir.mkdir()
        allowlist = root / "allowlist.json"
        allowlist.write_text(
            json.dumps({"allowed_cves": [], "allowed_packages": []}),
            encoding="utf-8",
        )
        output_file = root / "vuln-report-consolidated.json"

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            ok_code = allowlist_main(
                [
                    "--reports-dir",
                    str(reports_dir),
                    "--allowlist",
                    str(allowlist),
                    "--root",
                    str(root),
                    "--python-licenses-json",
                    str(root / "py-licenses.json"),
                    "--output",
                    str(output_file),
                ]
            )
        self.assertEqual(ok_code, 0)
        consolidated = json.loads(output_file.read_text(encoding="utf-8"))
        self.assertEqual(consolidated["summary"]["license_total_packages"], 2)
        self.assertEqual(consolidated["summary"]["license_unknown_count"], 1)
        self.assertIn("dependency_licenses", consolidated)
        self.assertEqual(
            consolidated["dependency_licenses"]["unknown_packages"][0]["name"],
            "unknown-pkg",
        )

        # Strict mode fails clearly on UNKNOWN licenses.
        with contextlib.redirect_stdout(io.StringIO()):
            fail_code = allowlist_main(
                [
                    "--reports-dir",
                    str(reports_dir),
                    "--allowlist",
                    str(allowlist),
                    "--root",
                    str(root),
                    "--python-licenses-json",
                    str(root / "py-licenses.json"),
                    "--output",
                    str(output_file),
                    "--fail-on-unknown-licenses",
                ]
            )
        self.assertEqual(fail_code, 1)

    def test_real_repository_license_report_covers_both_ecosystems(self):
        if not (_REPO_ROOT / "frontend" / "package-lock.json").is_file():
            self.skipTest("Repository lockfiles not found")
        report = generate_release_license_report(_REPO_ROOT)
        self.assertGreater(report["summary"]["frontend_packages"], 100)
        self.assertGreater(report["summary"]["backend_packages"], 10)
        # Verify repo's missing lockfile license metadata is surfaced for review.
        unknown_names = {
            p["name"] for p in report["unknown_packages"] if p["ecosystem"] == "npm"
        }
        self.assertIn("khroma", unknown_names)


if __name__ == "__main__":
    unittest.main()
