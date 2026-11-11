"""Unit tests for validate_api_rest_conventions.py."""

import tempfile
import unittest
from pathlib import Path

from scripts.validate_api_rest_conventions import (
    RestConventionValidator,
    is_parameter_segment,
    validate_path_conventions,
)


class TestRestConventionValidator(unittest.TestCase):
    def setUp(self):
        self.validator = RestConventionValidator()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_is_parameter_segment(self):
        self.assertTrue(is_parameter_segment(":id"))
        self.assertTrue(is_parameter_segment(":userId"))
        self.assertTrue(is_parameter_segment("{id}"))
        self.assertTrue(is_parameter_segment("{project_id}"))
        self.assertFalse(is_parameter_segment("users"))
        self.assertFalse(is_parameter_segment(":"))

    def test_trailing_slash_detection(self):
        findings = validate_path_conventions(
            "/api/users/", "GET", "routes/users.js", 10, self.validator.forbidden_verbs
        )
        slash_findings = [f for f in findings if f["type"] == "TRAILING_SLASH"]
        self.assertEqual(len(slash_findings), 1)

    def test_camelcase_path_segment(self):
        findings = validate_path_conventions(
            "/api/userProfiles", "GET", "routes/users.js", 15, self.validator.forbidden_verbs
        )
        casing = [f for f in findings if f["type"] == "CAMELCASE_PATH_SEGMENT"]
        self.assertEqual(len(casing), 1)

    def test_forbidden_crud_verbs_in_path(self):
        findings = validate_path_conventions(
            "/api/deleteUser", "POST", "routes/users.js", 20, self.validator.forbidden_verbs
        )
        verbs = [f for f in findings if f["type"] == "VERB_IN_ENDPOINT_PATH"]
        self.assertEqual(len(verbs), 1)

    def test_clean_rest_endpoint(self):
        findings = validate_path_conventions(
            "/api/v1/organizations/:orgId/members",
            "GET",
            "routes/orgs.ts",
            25,
            self.validator.forbidden_verbs,
        )
        # Should not flag clean kebab-case endpoint with valid parameter
        self.assertEqual(findings, [])

    def test_scan_directory_express_and_python(self):
        js_file = self.base_path / "routes.js"
        js_file.write_text(
            'router.get("/api/get-items", handler);\n'
            'app.post("/api/items/", createHandler);\n'
        )

        py_file = self.base_path / "server.py"
        py_file.write_text(
            '@app.get("/api/v1/projects/{projectId}")\n'
            'def get_project():\n'
            '    pass\n'
        )

        findings = self.validator.scan_directory(self.base_path)
        # 1 from verb 'get-items', 1 from trailing slash '/api/items/'
        self.assertEqual(len(findings), 2)


if __name__ == "__main__":
    unittest.main()
