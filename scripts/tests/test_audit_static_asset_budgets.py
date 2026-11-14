"""Unit tests for audit_static_asset_budgets.py."""

import tempfile
import unittest
from pathlib import Path

from scripts.audit_static_asset_budgets import (
    StaticAssetBudgetAuditor,
    compute_sha256,
    format_bytes,
)


class TestStaticAssetBudgetAuditor(unittest.TestCase):
    def setUp(self):
        self.limits = {
            "image": 1024,  # 1 KB for testing
            "svg": 512,     # 512 B
            "video": 2048,
            "font": 1024,
        }
        self.auditor = StaticAssetBudgetAuditor(limits=self.limits, max_total_bytes=10000)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_format_bytes(self):
        self.assertEqual(format_bytes(500), "500 B")
        self.assertEqual(format_bytes(2048), "2.00 KB")
        self.assertEqual(format_bytes(1048576 * 2), "2.00 MB")

    def test_oversized_image_detected(self):
        img_file = self.base_path / "banner.png"
        img_file.write_bytes(b"A" * 2000)  # 2000 bytes > 1024 limit

        report = self.auditor.audit_directory(self.base_path)
        oversized = [f for f in report["findings"] if f["type"] == "ASSET_SIZE_BUDGET_EXCEEDED"]
        self.assertEqual(len(oversized), 1)
        self.assertEqual(oversized[0]["file"], str(img_file))

    def test_duplicate_static_assets_detected(self):
        img1 = self.base_path / "logo.png"
        img2 = self.base_path / "copy_logo.png"
        content = b"exact-same-content"
        img1.write_bytes(content)
        img2.write_bytes(content)

        report = self.auditor.audit_directory(self.base_path)
        duplicates = [f for f in report["findings"] if f["type"] == "DUPLICATE_STATIC_ASSET"]
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(len(duplicates[0]["files"]), 2)

    def test_discouraged_uncompressed_format(self):
        bmp_file = self.base_path / "icon.bmp"
        bmp_file.write_bytes(b"bmp-content")

        report = self.auditor.audit_directory(self.base_path)
        discouraged = [f for f in report["findings"] if f["type"] == "DISCOURAGED_IMAGE_FORMAT"]
        self.assertEqual(len(discouraged), 1)

    def test_total_payload_budget_exceeded(self):
        auditor_strict = StaticAssetBudgetAuditor(
            limits={"image": 10000}, max_total_bytes=500
        )
        img_file = self.base_path / "photo.jpg"
        img_file.write_bytes(b"X" * 1000)

        report = auditor_strict.audit_directory(self.base_path)
        total_exceeded = [
            f for f in report["findings"] if f["type"] == "TOTAL_PAYLOAD_BUDGET_EXCEEDED"
        ]
        self.assertEqual(len(total_exceeded), 1)


if __name__ == "__main__":
    unittest.main()
