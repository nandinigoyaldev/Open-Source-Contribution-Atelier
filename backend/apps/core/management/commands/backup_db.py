import os
import subprocess
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = "Backup the PostgreSQL database using pg_dump"

    def handle(self, *args, **options):
        db_settings = settings.DATABASES["default"]
        engine = db_settings.get("ENGINE", "")

        if "postgresql" not in engine:
            raise CommandError("This command only supports PostgreSQL databases.")

        db_name = db_settings["NAME"]
        db_user = db_settings["USER"]
        db_password = db_settings.get("PASSWORD", "")
        db_host = db_settings.get("HOST", "localhost")
        db_port = db_settings.get("PORT", "5432")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"backup_{db_name}_{timestamp}.dump"

        env = os.environ.copy()
        if db_password:
            env["PGPASSWORD"] = str(db_password)

        command = [
            "pg_dump",
            "-h",
            str(db_host),
            "-p",
            str(db_port),
            "-U",
            str(db_user),
            "-F",
            "c",
            "-f",
            backup_file,
            str(db_name),
        ]

        self.stdout.write(
            self.style.NOTICE(
                f"Starting backup of database {db_name} to {backup_file}..."
            )
        )
        try:
            subprocess.run(command, env=env, check=True)
            self.stdout.write(
                self.style.SUCCESS(f"Successfully backed up database to {backup_file}")
            )
        except subprocess.CalledProcessError as e:
            raise CommandError(f"Backup failed: {e}")
