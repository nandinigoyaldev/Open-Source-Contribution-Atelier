import os
import tempfile
import unittest
from scripts.audit_module_boundaries import (
    build_dependency_graph,
    check_boundary_violations,
    file_to_module_name,
    find_cycles,
    parse_module_imports,
)


class TestAuditModuleBoundaries(unittest.TestCase):
    def test_file_to_module_name(self):
        self.assertEqual(file_to_module_name("backend/apps/user/models.py", "backend"), "apps.user.models")
        self.assertEqual(file_to_module_name("backend/apps/user/__init__.py", "backend"), "apps.user")

    def test_find_cycles_acyclic(self):
        graph = {
            "a": {"b", "c"},
            "b": {"c"},
            "c": set(),
        }
        cycles = find_cycles(graph)
        self.assertEqual(cycles, [])

    def test_find_cycles_simple(self):
        graph = {
            "a": {"b"},
            "b": {"a"},
        }
        cycles = find_cycles(graph)
        self.assertEqual(len(cycles), 1)
        self.assertEqual(cycles[0], ["a", "b", "a"])

    def test_find_cycles_three_node(self):
        graph = {
            "a": {"b"},
            "b": {"c"},
            "c": {"a"},
        }
        cycles = find_cycles(graph)
        self.assertEqual(len(cycles), 1)
        self.assertEqual(cycles[0], ["a", "b", "c", "a"])

    def test_check_boundary_violations(self):
        graph = {
            "apps.auth.views": {"apps.auth.models", "utils.helpers"},
            "utils.helpers": {"apps.auth.models"},  # illegal: utils importing apps
        }
        violations = check_boundary_violations(graph, [("utils", "apps")])
        self.assertEqual(len(violations), 1)
        self.assertIn("utils.helpers", violations[0])
        self.assertIn("apps.auth.models", violations[0])

    def test_parse_module_imports_with_tmp(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "service.py")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("import os\nfrom backend.apps import core\nfrom . import local_mod\n")

            imports = parse_module_imports(file_path, "backend.apps.service")
            self.assertIn("os", imports)
            self.assertIn("backend.apps", imports)


if __name__ == "__main__":
    unittest.main()
