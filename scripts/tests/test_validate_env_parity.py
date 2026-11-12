import os
import tempfile
import unittest
from scripts.validate_env_parity import (
    compare_env_parity,
    extract_env_keys_from_code,
    parse_env_file,
    run_checks,
)


class TestValidateEnvParity(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.test_dir.cleanup()

    def test_parse_env_file(self):
        env_path = os.path.join(self.test_dir.name, ".env.example")
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(
                "# Sample comment\n"
                "\n"
                "API_KEY=sample_secret\n"
                'DATABASE_URL="postgres://localhost:5432/db"\n'
                "DEBUG=True\n"
            )

        parsed = parse_env_file(env_path)
        self.assertEqual(
            parsed,
            {
                "API_KEY": "sample_secret",
                "DATABASE_URL": "postgres://localhost:5432/db",
                "DEBUG": "True",
            },
        )

    def test_parse_nonexistent_env_file(self):
        parsed = parse_env_file(os.path.join(self.test_dir.name, "missing.env"))
        self.assertEqual(parsed, {})

    def test_extract_env_keys_from_code(self):
        py_file = os.path.join(self.test_dir.name, "settings.py")
        with open(py_file, "w", encoding="utf-8") as f:
            f.write(
                "import os\n"
                "key = os.getenv('SECRET_KEY')\n"
                "db = os.environ.get('DATABASE_URL')\n"
                "path = os.environ['PATH'] # should be ignored\n"
            )

        ts_file = os.path.join(self.test_dir.name, "config.ts")
        with open(ts_file, "w", encoding="utf-8") as f:
            f.write(
                "const api = import.meta.env.VITE_API_BASE_URL;\n"
                "const mode = import.meta.env.MODE;\n"
            )

        found_py = extract_env_keys_from_code(self.test_dir.name, (".py",))
        self.assertIn("SECRET_KEY", found_py)
        self.assertIn("DATABASE_URL", found_py)
        self.assertNotIn("PATH", found_py)

        found_ts = extract_env_keys_from_code(self.test_dir.name, (".ts",))
        self.assertIn("VITE_API_BASE_URL", found_ts)
        self.assertNotIn("MODE", found_ts)

    def test_compare_env_parity(self):
        example_keys = {"SECRET_KEY", "DATABASE_URL", "LEGACY_OPTION"}
        code_keys = {"SECRET_KEY", "DATABASE_URL", "NEW_FEATURE_FLAG"}

        undocumented, unused = compare_env_parity(example_keys, code_keys)
        self.assertEqual(undocumented, {"NEW_FEATURE_FLAG"})
        self.assertEqual(unused, {"LEGACY_OPTION"})

    def test_run_checks_on_repo(self):
        # Ensure run_checks executes against repository without crashing
        errors = run_checks(".")
        self.assertIsInstance(errors, list)


if __name__ == "__main__":
    unittest.main()
