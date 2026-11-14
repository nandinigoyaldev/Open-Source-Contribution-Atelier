from django.core.management.base import BaseCommand, CommandError
from django.db import models

from apps.progress.models import ProgressBufferDeadLetter


class Command(BaseCommand):
    help = "Inspect, replay, or discard dead-lettered progress updates."

    def add_arguments(self, parser):
        parser.add_argument("--id", type=int, dest="record_id")
        parser.add_argument("--user", type=str, dest="user_identifier")
        parser.add_argument("--all", action="store_true")
        parser.add_argument("--discard", action="store_true")
        parser.add_argument("--reason", type=str, default="")
        parser.add_argument("--operator", type=str, default="")
        parser.add_argument("--status", type=str, default="pending")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        operator = options.get("operator")
        if not operator:
            raise CommandError("Guarded replay requires --operator.")

        qs = ProgressBufferDeadLetter.objects.select_related("user")
        if options.get("record_id"):
            qs = qs.filter(pk=options["record_id"])
        elif options.get("user_identifier"):
            u = options["user_identifier"]
            qs = (
                qs.filter(models.Q(user__id=int(u)) | models.Q(user__username=u))
                if u.isdigit()
                else qs.filter(user__username=u)
            )
        elif not options.get("all"):
            raise CommandError("Must specify --id, --user, or --all.")

        sf = options.get("status")
        if sf and sf.lower() != "all":
            qs = qs.filter(status=sf.lower())

        records = list(qs)
        if options.get("dry_run") or options.get("dry-run"):
            for r in records:
                self.stdout.write(
                    f"  [DRY-RUN] Record #{r.id}: user={r.user.username}, status={r.status}"
                )
            self.stdout.write(self.style.SUCCESS("Dry run completed."))
            return

        discard, reason = options.get("discard"), options.get("reason", "")
        success_count = 0
        for r in records:
            try:
                (
                    r.discard(operator=operator, reason=reason)
                    if discard
                    else r.replay(operator=operator)
                )
                success_count += 1
            except Exception as e:
                self.stderr.write(f"Failed #{r.id}: {e}")

        self.stdout.write(
            self.style.SUCCESS(f"Processed {success_count}/{len(records)} records.")
        )
