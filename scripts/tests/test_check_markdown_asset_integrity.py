import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from check_markdown_asset_integrity import (
    check_file,
    extract_relative_links,
    is_external_or_anchor,
)


class TestMarkdownAssetIntegrity(unittest.TestCase):
    def test_is_external_or_anchor(self):
        self.assertTrue(is_external_or_anchor("https://github.com/example"))
        self.assertTrue(is_external_or_anchor("http://example.com/asset.png"))
        self.assertTrue(is_external_or_anchor("mailto:user@example.com"))
        self.assertTrue(is_external_or_anchor("#section-header"))
        self.assertTrue(is_external_or_anchor(""))
        self.assertFalse(is_external_or_anchor("./relative/path.md"))
        self.assertFalse(is_external_or_anchor("../images/diagram.png"))

    def test_extract_links_filters_external(self):
        content = """# Sample
[GitHub](https://github.com)
[Local Doc](./guide.md)
![Diagram](../assets/diag.png#anchor)
[Same page](#top)
"""
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            links = extract_relative_links(temp_path, content)
            self.assertEqual(len(links), 2)
            targets = [l.raw_target for l in links]
            self.assertIn("./guide.md", targets)
            self.assertIn("../assets/diag.png#anchor", targets)
        finally:
            os.unlink(temp_path)

    def test_check_file_finds_missing_target(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            md_file = os.path.join(tmpdir, "doc.md")
            with open(md_file, "w", encoding="utf-8") as f:
                f.write("[Missing Link](./nonexistent_file.md)\n")

            errors = check_file(md_file)
            self.assertEqual(len(errors), 1)
            self.assertIn("nonexistent_file.md", errors[0])

    def test_check_file_passes_when_target_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = os.path.join(tmpdir, "target.md")
            with open(target_file, "w", encoding="utf-8") as f:
                f.write("# Target\n")

            md_file = os.path.join(tmpdir, "doc.md")
            with open(md_file, "w", encoding="utf-8") as f:
                f.write("[Good Link](./target.md)\n")

            errors = check_file(md_file)
            self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
