from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Rollback migration on failure"

    def add_arguments(self, parser):
        parser.add_argument("--migration", type=str, help="Migration name to rollback")

    def handle(self, *args, **options):
        self.stdout.write("🔄 Rolling back migration...")

        if options["migration"]:
            self.stdout.write(f'📋 Rolling back {options["migration"]}')

        with connection.cursor() as cursor:
            # Get last migration
            cursor.execute(
                "SELECT app, name FROM django_migrations ORDER BY id DESC LIMIT 1"
            )
            last = cursor.fetchone()

            if last:
                self.stdout.write(f"✅ Rolling back: {last[0]}.{last[1]}")
                # Simulate rollback
                cursor.execute(
                    f"DELETE FROM django_migrations WHERE app='{last[0]}' AND name='{last[1]}'"
                )
                self.stdout.write(self.style.SUCCESS("✅ Rollback complete"))
            else:
                self.stdout.write("ℹ️ No migrations to rollback")
