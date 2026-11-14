import json
import os
import tempfile
import unittest
from scripts.validate_i18n_deep_coverage import (
    compare_locale,
    extract_placeholders,
    flatten_keys,
    load_locale_translations,
    validate_all_locales,
)


class TestValidateI18nDeepCoverage(unittest.TestCase):
    def test_flatten_keys(self):
        nested = {
            "auth": {
                "login": {
                    "title": "Log In",
                    "attempts": 3,
                },
                "logout": "Log Out",
            }
        }
        flat = flatten_keys(nested)
        self.assertEqual(
            flat,
            {
                "auth.login.title": "Log In",
                "auth.login.attempts": "3",
                "auth.logout": "Log Out",
            },
        )

    def test_extract_placeholders(self):
        text = "Hello, {{username}}! You have {count} unread notifications."
        placeholders = extract_placeholders(text)
        self.assertEqual(placeholders, {"username", "count"})

        no_tokens = "Simple sentence with no variables."
        self.assertEqual(extract_placeholders(no_tokens), set())

    def test_compare_locale_parity_and_discrepancies(self):
        base = {
            "app.title": "Atelier",
            "app.welcome": "Welcome, {{name}}!",
            "app.legacy": "Old Feature",
        }
        target = {
            "app.title": "Atelier",
            "app.welcome": "Bienvenido, {{wrong_token}}!",
            "app.empty": "   ",
        }

        missing, extra, empty, mismatches = compare_locale(base, target, "es")

        # app.legacy is missing from target
        self.assertEqual(len(missing), 1)
        self.assertIn("app.legacy", missing[0])

        # app.empty is extra in target, plus empty string
        self.assertEqual(len(extra), 1)
        self.assertIn("app.empty", extra[0])
        self.assertEqual(len(empty), 1)
        self.assertIn("app.empty", empty[0])

        # app.welcome has placeholder mismatch
        self.assertEqual(len(mismatches), 1)
        self.assertIn("app.welcome", mismatches[0])

    def test_load_and_validate_temp_locales(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            en_dir = os.path.join(tmpdir, "en")
            es_dir = os.path.join(tmpdir, "es")
            os.makedirs(en_dir)
            os.makedirs(es_dir)

            with open(os.path.join(en_dir, "common.json"), "w", encoding="utf-8") as f:
                json.dump({"nav": {"home": "Home"}}, f)

            with open(os.path.join(es_dir, "common.json"), "w", encoding="utf-8") as f:
                json.dump({"nav": {"home": "Inicio"}}, f)

            total_issues, results = validate_all_locales(tmpdir, base_locale="en")
            self.assertEqual(total_issues, 0)
            self.assertIn("es", results)


if __name__ == "__main__":
    unittest.main()
