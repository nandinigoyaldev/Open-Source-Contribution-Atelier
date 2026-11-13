"""
Bulk curriculum import from a zip archive (format: docs/CURRICULUM_IMPORT.md).

Usage:
  python manage.py import_curriculum start path/to/curriculum.zip
  python manage.py import_curriculum preview <import_id>
  python manage.py import_curriculum publish <import_id>
  python manage.py import_curriculum start path/to/curriculum.zip --publish

``start`` validates the archive and stores a report; nothing is published until
``publish`` (or ``--publish`` on a clean archive). Publishing is atomic: if it
fails the existing curriculum is untouched.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.content.models import CurriculumImport
from apps.content.services import curriculum_import as ci
from apps.content.services import curriculum_import_jobs as jobs


class Command(BaseCommand):
    help = "Validate, preview and publish a curriculum archive (zip)."

    def add_arguments(self, parser):
        parser.add_argument("--format", choices=("text", "json"), default="text")
        sub = parser.add_subparsers(dest="action", required=True)
        start = sub.add_parser("start", help="Upload an archive and validate it")
        start.add_argument("archive", type=str)
        start.add_argument(
            "--publish",
            action="store_true",
            help="Publish straight away when validation finds no problems",
        )
        preview = sub.add_parser("preview", help="Show an import's status and report")
        preview.add_argument("import_id", type=int)
        publish = sub.add_parser("publish", help="Publish a previewed import")
        publish.add_argument("import_id", type=int)

    def handle(self, *args, **options):
        action = options["action"]
        if action == "start":
            path = Path(options["archive"])
            if not path.is_file():
                raise CommandError(f"archive not found: {path}")
            try:
                imp = jobs.create_import(path.read_bytes(), name=path.name)
            except ci.ArchiveError as exc:
                raise CommandError(str(exc)) from exc
            imp = jobs.run_validation(imp.pk)
            self._show(imp, options["format"])
            if imp.status == CurriculumImport.FAILED:
                raise CommandError("validation failed; nothing was published")
            if options["publish"]:
                self._publish(imp.pk, options["format"])
            return
        imp = self._get(options["import_id"])
        if action == "preview":
            self._show(imp, options["format"])
        else:
            self._publish(imp.pk, options["format"])

    def _get(self, import_id: int) -> CurriculumImport:
        try:
            return CurriculumImport.objects.get(pk=import_id)
        except CurriculumImport.DoesNotExist as exc:
            raise CommandError(f"no import with id {import_id}") from exc

    def _publish(self, import_id: int, fmt: str) -> None:
        try:
            imp = jobs.run_publish(import_id)
        except jobs.ImportStateError as exc:
            raise CommandError(str(exc)) from exc
        self._show(imp, fmt)
        if imp.status == CurriculumImport.FAILED:
            raise CommandError("publish failed; the existing curriculum is unchanged")

    def _show(self, imp: CurriculumImport, fmt: str) -> None:
        if fmt == "json":
            self.stdout.write(
                json.dumps(
                    {
                        "id": imp.pk,
                        "status": imp.status,
                        "error": imp.error,
                        "report": imp.report,
                    },
                    indent=2,
                )
            )
            return
        report = imp.report or {}
        counts = report.get("counts", {})
        self.stdout.write(self.style.NOTICE(f"Import #{imp.pk}: {imp.status}"))
        if counts:
            self.stdout.write(
                f"  modules {counts.get('modules')}, lessons {counts.get('lessons')}, "
                f"quizzes {counts.get('quizzes')}"
            )
        plan = report.get("plan")
        if plan and not report.get("problem_count"):
            self.stdout.write(
                f"  plan: {len(plan['create'])} to create, "
                f"{len(plan['update'])} to update, {len(plan['unchanged'])} unchanged"
            )
        for item in report.get("problems", []):
            self.stdout.write(self.style.ERROR(f"  {item['file']}: {item['message']}"))
        if report.get("problems_truncated"):
            self.stdout.write(
                f"  ... {report['problem_count']} problems in total (list truncated)"
            )
        if "published" in report:
            done = report["published"]
            self.stdout.write(
                self.style.SUCCESS(
                    f"  published: {done['created']} created, {done['updated']} "
                    f"updated, {done['unchanged']} unchanged"
                )
            )
        if report.get("publish_error"):
            self.stdout.write(self.style.ERROR(f"  {report['publish_error']}"))
