import os
import tempfile
import unittest
from scripts.audit_docker_compose_config import (
    audit_compose_file,
    find_missing_healthchecks,
    find_port_collisions,
    find_undeclared_named_volumes,
    parse_compose_file,
    parse_port_entry,
)


class TestAuditDockerComposeConfig(unittest.TestCase):
    def test_parse_port_entry(self):
        self.assertEqual(parse_port_entry(' - "8000:80"'), ("0.0.0.0", 8000, 80))
        self.assertEqual(parse_port_entry("- 5432:5432"), ("0.0.0.0", 5432, 5432))
        self.assertEqual(parse_port_entry('- "127.0.0.1:6379:6379"'), ("127.0.0.1", 6379, 6379))
        self.assertIsNone(parse_port_entry('- "80"'))  # Internal only

    def test_find_port_collisions(self):
        services = {
            "web": {"ports": [("0.0.0.0", 8000, 80)]},
            "api": {"ports": [("0.0.0.0", 8000, 8000)]},
        }
        collisions = find_port_collisions(services)
        self.assertEqual(len(collisions), 1)
        self.assertIn("8000", collisions[0])
        self.assertIn("web", collisions[0])
        self.assertIn("api", collisions[0])

    def test_find_undeclared_named_volumes(self):
        services = {
            "db": {"volumes": ["db_data:/var/lib/postgresql/data", "./local:/app"]},
            "app": {"volumes": ["missing_vol:/opt/data"]},
        }
        declared_volumes = {"db_data"}
        undeclared = find_undeclared_named_volumes(services, declared_volumes)
        self.assertEqual(len(undeclared), 1)
        self.assertIn("missing_vol", undeclared[0])

    def test_find_missing_healthchecks(self):
        services = {
            "db": {"image": "postgres:15-alpine", "has_healthcheck": False},
            "cache": {"image": "redis:7-alpine", "has_healthcheck": True},
        }
        warnings = find_missing_healthchecks(services)
        self.assertEqual(len(warnings), 1)
        self.assertIn("db", warnings[0])

    def test_audit_compose_file_with_temp_file(self):
        compose_content = """services:
  web:
    image: nginx:alpine
    ports:
      - "80:80"
  db:
    image: postgres:15
    volumes:
      - pgdata:/data
    healthcheck:
      test: ["CMD", "pg_isready"]

volumes:
  pgdata:
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "docker-compose.yml")
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(compose_content)

            collisions, undeclared, missing_health = audit_compose_file(fpath)
            self.assertEqual(len(collisions), 0)
            self.assertEqual(len(undeclared), 0)
            self.assertEqual(len(missing_health), 0)


if __name__ == "__main__":
    unittest.main()
