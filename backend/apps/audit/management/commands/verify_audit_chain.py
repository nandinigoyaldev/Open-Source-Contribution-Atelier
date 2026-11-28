from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.audit.chain import verify_chain
from apps.audit.models import AuditEvent
from apps.moderation.models import ModerationAuditEvent

CHAINED_MODELS = {
    model.chain.name: model for model in (AuditEvent, ModerationAuditEvent)
}


class Command(BaseCommand):
    help = "Check the audit hash chains for edited, missing or inserted records."

    def add_arguments(self, parser):
        parser.add_argument(
            "--chain",
            choices=sorted(CHAINED_MODELS),
            help="Check one chain only. Default: all of them.",
        )
        parser.add_argument(
            "--expect",
            action="append",
            default=[],
            metavar="CHAIN:SEQUENCE:HASH",
            help="A checkpoint printed by an earlier run. Can be repeated.",
        )
        parser.add_argument("--database", help="Database alias to read from.")
        parser.add_argument(
            "--max-errors",
            type=int,
            default=50,
            help="Most problems to print per chain (default 50).",
        )

    def handle(self, *args, **options):
        names = [options["chain"]] if options["chain"] else sorted(CHAINED_MODELS)
        checkpoints = {name: [] for name in CHAINED_MODELS}
        for value in options["expect"]:
            name, sequence, row_hash = self._parse_checkpoint(value)
            if name not in names:
                raise CommandError(f"--expect {name}: that chain is not being checked")
            checkpoints[name].append((sequence, row_hash))

        style: Any = self.style
        failed = []
        for name in names:
            report = verify_chain(
                CHAINED_MODELS[name],
                using=options["database"],
                expected=checkpoints[name],
            )
            summary = f"{report.rows} records, {report.anchors} pruned ranges"
            if report.ok:
                self.stdout.write(style.SUCCESS(f"{name}: OK, {summary}"))
                self.stdout.write(
                    f"checkpoint {name}:{report.head_sequence}:{report.head_hash}"
                )
                continue
            failed.append(name)
            self.stderr.write(
                f"{name}: FAILED, {len(report.errors)} problems, {summary}"
            )
            shown = report.errors[: max(options["max_errors"], 1)]
            for error in shown:
                self.stderr.write(f"  {error}")
            if len(report.errors) > len(shown):
                self.stderr.write(f"  and {len(report.errors) - len(shown)} more")

        if failed:
            raise CommandError(f"Audit chain verification failed: {', '.join(failed)}")

    def _parse_checkpoint(self, value):
        try:
            name, sequence, row_hash = value.split(":")
            if name not in CHAINED_MODELS or len(row_hash) != 64:
                raise ValueError
            return name, int(sequence), row_hash.lower()
        except ValueError:
            raise CommandError(
                f"--expect needs CHAIN:SEQUENCE:HASH, got {value!r}"
            ) from None
