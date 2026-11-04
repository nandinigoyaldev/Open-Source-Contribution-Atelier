from django.core.management.base import BaseCommand, CommandError

from apps.core import tenant_crypto


class Command(BaseCommand):
    help = (
        "Re-encrypt tenant-encrypted columns under the primary master key "
        "(TENANT_ENCRYPTION_PRIMARY_KEY). Safe to repeat and to stop at any time."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true", help="Count what would change."
        )
        parser.add_argument("--batch-size", type=int, default=500)
        parser.add_argument("--tenant", help="Only rotate rows of this tenant id.")
        parser.add_argument(
            "--target",
            action="append",
            help="Only this column, as app.Model.field (can be repeated).",
        )
        parser.add_argument(
            "--include-plaintext",
            action="store_true",
            help="Also encrypt values that are still plaintext (migration backfill).",
        )

    def handle(self, *args, **options):
        # a broken key configuration stops everything, rather than failing row by row
        config = tenant_crypto.load_master_keys()
        targets = tenant_crypto.rotation_targets()
        if options["target"]:
            wanted = set(options["target"])
            targets = [t for t in targets if f"{t.model}.{t.field}" in wanted]
        if not targets:
            self.stdout.write(
                "No tenant-encrypted columns are registered; nothing to rotate."
            )
            return

        self.stdout.write(
            f"Primary key: {config.primary}; keys available: {', '.join(sorted(config.keys))}"
        )
        failures = 0
        for target in targets:
            stats = tenant_crypto.rotate_target(
                target,
                batch_size=options["batch_size"],
                dry_run=options["dry_run"],
                tenant_id=options["tenant"],
                allow_plaintext=options["include_plaintext"],
            )
            verb = "would rotate" if options["dry_run"] else "rotated"
            self.stdout.write(
                f"{target.model}.{target.field}: scanned {stats['scanned']}, {verb} "
                f"{stats['rotated']}, already current {stats['skipped_current']}, "
                f"changed meanwhile {stats['conflicts']}, errors {stats['errors']}"
            )
            if stats["errors"]:
                failures += stats["errors"]
                self.stdout.write(
                    f"  could not decrypt rows (first ids): {stats['error_ids']}"
                )
        if failures:
            raise CommandError(
                f"{failures} value(s) could not be decrypted and were left unchanged; "
                "is a retired key missing from TENANT_ENCRYPTION_KEYS?"
            )
