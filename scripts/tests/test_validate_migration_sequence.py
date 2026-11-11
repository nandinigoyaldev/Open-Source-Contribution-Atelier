"""Unit tests for validate_migration_sequence.py."""

import tempfile
import unittest
from pathlib import Path

from scripts.validate_migration_sequence import (
    MigrationSequenceValidator,
    parse_migration_filename,
)


class TestMigrationSequenceValidator(unittest.TestCase):
    def setUp(self):
        self.validator = MigrationSequenceValidator(strict_monotonic=True)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_parse_migration_filename(self):
        p1 = parse_migration_filename("0001_create_users_table.sql")
        self.assertEqual(p1, ("numeric", "0001", "create_users_table"))

        p2 = parse_migration_filename("20260101153000_add_roles.sql")
        self.assertEqual(p2, ("timestamp", "20260101153000", "add_roles"))

        p3 = parse_migration_filename("__init__.py")
        self.assertIsNone(p3)

    def test_prefix_collision_detection(self):
        mig_dir = self.base_path / "migrations"
        mig_dir.mkdir()
        (mig_dir / "0001_initial_schema.sql").write_text("-- init")
        (mig_dir / "0001_add_roles_collision.sql").write_text("-- collision")

        findings = self.validator.validate_directory(mig_dir)
        collisions = [f for f in findings if f["type"] == "MIGRATION_PREFIX_COLLISION"]
        self.assertEqual(len(collisions), 1)
        self.assertEqual(collisions[0]["prefix"], "0001")
        self.assertEqual(collisions[0]["severity"], "ERROR")

    def test_sequence_gap_detection_with_strict_monotonic(self):
        mig_dir = self.base_path / "migrations"
        mig_dir.mkdir()
        (mig_dir / "0001_initial.sql").write_text("-- init")
        (mig_dir / "0002_users.sql").write_text("-- users")
        (mig_dir / "0004_missing_three.sql").write_text("-- missing 3")

        findings = self.validator.validate_directory(mig_dir)
        gaps = [f for f in findings if f["type"] == "SEQUENCE_GAP"]
        self.assertEqual(len(gaps), 1)

    def test_clean_monotonic_sequence(self):
        mig_dir = self.base_path / "migrations"
        mig_dir.mkdir()
        (mig_dir / "0001_initial.sql").write_text("-- init")
        (mig_dir / "0002_users.sql").write_text("-- users")
        (mig_dir / "0003_tokens.sql").write_text("-- tokens")

        findings = self.validator.validate_directory(mig_dir)
        self.assertEqual(findings, [])

    def test_scan_workspace_discovery(self):
        sub_mig = self.base_path / "backend" / "src" / "migrations"
        sub_mig.mkdir(parents=True)
        (sub_mig / "01_init.sql").write_text("-- init")
        (sub_mig / "02_data.sql").write_text("-- data")

        findings = self.validator.scan_workspace(self.base_path)
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
