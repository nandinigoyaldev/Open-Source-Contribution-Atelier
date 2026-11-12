"""Unit tests for validate_openapi_route_coverage.py."""

import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_openapi_route_coverage import (
    OpenApiCoverageValidator,
    extract_path_template,
    normalize_route_path,
    parse_openapi_spec,
    scan_codebase_routes,
)


class TestOpenApiCoverageValidator(unittest.TestCase):
    def setUp(self):
        self.validator = OpenApiCoverageValidator()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_normalize_route_path(self):
        self.assertEqual(normalize_route_path("/api/users/:id"), "/api/users/{id}")
        self.assertEqual(normalize_route_path("/api/items/"), "/api/items")
        self.assertEqual(normalize_route_path("/"), "/")

    def test_extract_path_template(self):
        template, params = extract_path_template("/api/users/{id}/orders/{orderId}")
        self.assertEqual(template, "/api/users/{}/orders/{}")
        self.assertEqual(params, ["id", "orderId"])

    def test_parse_openapi_spec_json(self):
        spec_content = {
            "openapi": "3.0.0",
            "paths": {
                "/api/v1/users": {
                    "get": {"summary": "List users"},
                    "post": {"summary": "Create user"},
                },
                "/api/v1/users/{id}": {
                    "get": {"summary": "Get user"},
                },
            },
        }
        spec_file = self.base_path / "openapi.json"
        spec_file.write_text(json.dumps(spec_content))

        endpoints = parse_openapi_spec(spec_file)
        self.assertEqual(len(endpoints), 3)
        self.assertIn("GET /api/v1/users", endpoints)
        self.assertIn("POST /api/v1/users", endpoints)
        self.assertIn("GET /api/v1/users/{id}", endpoints)

    def test_scan_codebase_routes(self):
        code_file = self.base_path / "routes.js"
        code_file.write_text(
            'router.get("/api/v1/users", listUsers);\n'
            'router.get("/api/v1/users/:userId", getUser);\n'
        )

        routes = scan_codebase_routes(self.base_path)
        self.assertEqual(len(routes), 2)
        self.assertIn("GET /api/v1/users", routes)
        self.assertIn("GET /api/v1/users/{userId}", routes)

    def test_compare_parity_and_coverage(self):
        spec_endpoints = {
            "GET /api/v1/users": {"method": "GET", "path": "/api/v1/users", "template": "/api/v1/users", "params": []},
            "GET /api/v1/users/{id}": {"method": "GET", "path": "/api/v1/users/{id}", "template": "/api/v1/users/{}", "params": ["id"]},
            "DELETE /api/v1/users/{id}": {"method": "DELETE", "path": "/api/v1/users/{id}", "template": "/api/v1/users/{}", "params": ["id"]},
        }

        code_routes = {
            "GET /api/v1/users": {"method": "GET", "path": "/api/v1/users", "template": "/api/v1/users", "params": []},
            "GET /api/v1/users/{userId}": {"method": "GET", "path": "/api/v1/users/{userId}", "template": "/api/v1/users/{}", "params": ["userId"]},
            "POST /api/v1/auth/login": {"method": "POST", "path": "/api/v1/auth/login", "template": "/api/v1/auth/login", "params": []},
        }

        report = self.validator.compare(spec_endpoints, code_routes)
        self.assertEqual(report["total_implemented_routes"], 3)
        self.assertEqual(report["matched_count"], 1)  # exact match
        self.assertEqual(report["template_matched_count"], 1)  # template match on {id} vs {userId}
        self.assertEqual(len(report["undocumented_routes"]), 1)  # POST /api/v1/auth/login
        self.assertEqual(report["undocumented_routes"][0]["path"], "/api/v1/auth/login")
        self.assertEqual(len(report["orphaned_specs"]), 1)  # DELETE /api/v1/users/{id}
        self.assertEqual(report["coverage_percentage"], 66.67)


if __name__ == "__main__":
    unittest.main()
