"""
Compare frontend curriculum.json lesson slugs with seeded DB Lesson rows.

Usage:
  python manage.py check_curriculum_slugs
  python manage.py check_curriculum_slugs --format json
  python manage.py check_curriculum_slugs --fail-on-drift
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Set

from django.core.management.base import BaseCommand, CommandError

from apps.content.models import Lesson


def default_curriculum_path() -> Path:
    # backend/apps/content/management/commands/this_file.py → repo root
    return (
        Path(__file__).resolve().parents[5]
        / "frontend"
        / "public"
        / "content"
        / "curriculum.json"
    )


def extract_curriculum_slugs(curriculum: Dict[str, Any]) -> List[str]:
    slugs: Set[str] = set()
    for module in curriculum.get("modules") or []:
        for lesson in module.get("lessons") or []:
            slug = (lesson.get("slug") or "").strip()
            if slug:
                slugs.add(slug)
    return sorted(slugs)


def diff_slugs(
    curriculum_slugs: List[str], db_slugs: List[str]
) -> Dict[str, List[str]]:
    curriculum_set = set(curriculum_slugs)
    db_set = set(db_slugs)
    return {
        "missing_in_api": sorted(curriculum_set - db_set),
        "missing_in_curriculum": sorted(db_set - curriculum_set),
    }


class Command(BaseCommand):
    help = (
        "Detect lesson slug drift between frontend/public/content/curriculum.json "
        "and seeded Lesson rows in the database."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--curriculum",
            type=str,
            default=str(default_curriculum_path()),
            help="Path to curriculum.json",
        )
        parser.add_argument(
            "--format",
            choices=("text", "json"),
            default="text",
            help="Output format",
        )
        parser.add_argument(
            "--fail-on-drift",
            action="store_true",
            help="Exit with code 1 when any slug mismatch is found",
        )

    def handle(self, *args, **options):
        path = Path(options["curriculum"])
        if not path.is_file():
            raise CommandError(f"curriculum.json not found: {path}")

        try:
            curriculum = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON in {path}: {exc}") from exc

        curriculum_slugs = extract_curriculum_slugs(curriculum)
        db_slugs = sorted(
            Lesson.objects.exclude(slug="").values_list("slug", flat=True).distinct()
        )
        diff = diff_slugs(curriculum_slugs, db_slugs)
        has_drift = bool(diff["missing_in_api"] or diff["missing_in_curriculum"])

        payload = {
            "curriculum_path": str(path),
            "curriculum_count": len(curriculum_slugs),
            "db_count": len(db_slugs),
            "missing_in_api": diff["missing_in_api"],
            "missing_in_curriculum": diff["missing_in_curriculum"],
            "has_drift": has_drift,
        }

        if options["format"] == "json":
            self.stdout.write(json.dumps(payload, indent=2))
        else:
            self.stdout.write(self.style.NOTICE(f"Curriculum: {path}"))
            self.stdout.write(
                f"curriculum slugs: {payload['curriculum_count']} | "
                f"DB lessons: {payload['db_count']}"
            )
            if not has_drift:
                self.stdout.write(self.style.SUCCESS("No slug drift detected."))
            else:
                self.stdout.write(self.style.WARNING("Slug drift detected:"))
                if diff["missing_in_api"]:
                    self.stdout.write(
                        "  Missing in API/DB (present in curriculum.json):"
                    )
                    for slug in diff["missing_in_api"]:
                        self.stdout.write(f"    - {slug}")
                if diff["missing_in_curriculum"]:
                    self.stdout.write("  Missing in curriculum.json (present in DB):")
                    for slug in diff["missing_in_curriculum"]:
                        self.stdout.write(f"    - {slug}")
                self.stdout.write(
                    self.style.NOTICE(
                        "Hint: update seed_lessons / curriculum.json, then "
                        "re-run seed_lessons."
                    )
                )

        if has_drift and options["fail_on_drift"]:
            raise CommandError("Curriculum slug drift detected.")
