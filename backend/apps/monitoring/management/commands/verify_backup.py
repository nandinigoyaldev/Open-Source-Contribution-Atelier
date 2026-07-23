import os
import subprocess
from datetime import datetime
from pathlib import Path

import boto3
from django.core.management.base import BaseCommand
from django.core.mail import mail_admins
from django.conf import settings
from django.utils import timezone

from apps.monitoring.models import BackupVerification


class Command(BaseCommand):
    help = (
        "Verifies the latest database backup by restoring it to a temporary database."
    )

    def handle(self, *args, **options):
        db_settings = settings.DATABASES["default"]
        db_user = db_settings.get("USER", os.getenv("DB_USER"))
        db_password = db_settings.get("PASSWORD", os.getenv("DB_PASSWORD"))
        db_host = db_settings.get("HOST", os.getenv("DB_HOST", "localhost"))
        db_port = str(db_settings.get("PORT", os.getenv("DB_PORT", "5432")))

        s3_bucket = os.getenv("S3_BUCKET_NAME")
        s3_region = os.getenv("AWS_REGION", "us-east-1")
        s3_access_key = os.getenv("S3_ACCESS_KEY")
        s3_secret_key = os.getenv("S3_SECRET_KEY")

        if not s3_bucket or not s3_access_key or not s3_secret_key:
            self.stderr.write("S3 credentials missing.")
            return

        s3 = boto3.client(
            "s3",
            region_name=s3_region,
            aws_access_key_id=s3_access_key,
            aws_secret_access_key=s3_secret_key,
        )

        try:
            response = s3.list_objects_v2(Bucket=s3_bucket, Prefix="backups/")
            if "Contents" not in response:
                self.stderr.write("No backups found.")
                return

            latest_obj = sorted(
                response["Contents"], key=lambda obj: obj["LastModified"], reverse=True
            )[0]
            backup_key = latest_obj["Key"]
            size_bytes = latest_obj["Size"]
            backup_timestamp = latest_obj["LastModified"]

            self.stdout.write(f"Downloading {backup_key}...")

            download_dir = Path(settings.BASE_DIR) / "tmp"
            download_dir.mkdir(exist_ok=True)

            local_file = download_dir / Path(backup_key).name
            s3.download_file(s3_bucket, backup_key, str(local_file))

            temp_db_name = f"backup_verify_{datetime.now().strftime('%Y%m%d%H%M%S')}"

            env = os.environ.copy()
            if db_password:
                env["PGPASSWORD"] = str(db_password)

            # Cleanup any existing temp DBs if possible (not done here for safety)
            # Create DB
            subprocess.run(
                ["createdb", "-h", db_host, "-p", db_port, "-U", db_user, temp_db_name],
                env=env,
                check=True,
            )

            status = "failed"
            logs = ""

            try:
                if str(local_file).endswith(".gz"):
                    # The script uses pg_dump with -F p (plain sql).
                    unzipped = local_file.with_suffix("")
                    subprocess.run(["gzip", "-d", "-f", str(local_file)], check=True)
                    with open(unzipped, "r") as f:
                        subprocess.run(
                            [
                                "psql",
                                "-h",
                                db_host,
                                "-p",
                                db_port,
                                "-U",
                                db_user,
                                "-d",
                                temp_db_name,
                            ],
                            stdin=f,
                            env=env,
                            check=True,
                        )
                    unzipped.unlink()
                else:
                    # Older backups or different format (-F c)
                    subprocess.run(
                        [
                            "pg_restore",
                            "-h",
                            db_host,
                            "-p",
                            db_port,
                            "-U",
                            db_user,
                            "-d",
                            temp_db_name,
                            "-1",
                            str(local_file),
                        ],
                        env=env,
                        check=True,
                    )

                # Sanity query
                res = subprocess.run(
                    [
                        "psql",
                        "-h",
                        db_host,
                        "-p",
                        db_port,
                        "-U",
                        db_user,
                        "-d",
                        temp_db_name,
                        "-t",
                        "-c",
                        "SELECT count(*) FROM django_migrations;",
                    ],
                    env=env,
                    capture_output=True,
                    text=True,
                    check=True,
                )

                count = int(res.stdout.strip())
                if count < 1:
                    raise Exception("django_migrations table is empty or missing.")

                status = "success"
                logs = "Verification completed successfully."
            except subprocess.CalledProcessError as e:
                logs = f"Subprocess failed: {e}\n{e.stderr}"
                mail_admins(subject="Database Backup Verification Failed", message=logs)
            except Exception as e:
                logs = str(e)
                mail_admins(subject="Database Backup Verification Failed", message=logs)
            finally:
                subprocess.run(
                    [
                        "dropdb",
                        "-h",
                        db_host,
                        "-p",
                        db_port,
                        "-U",
                        db_user,
                        temp_db_name,
                        "--if-exists",
                    ],
                    env=env,
                )
                if local_file.exists():
                    local_file.unlink()

            BackupVerification.objects.create(
                backup_timestamp=backup_timestamp,
                size_bytes=size_bytes,
                status=status,
                logs=logs,
            )

            if status == "success":
                self.stdout.write(self.style.SUCCESS(f"Verification successful."))
            else:
                self.stderr.write(f"Verification failed: {logs}")

        except Exception as e:
            self.stderr.write(f"Verification process failed completely: {e}")
            mail_admins(
                subject="Database Backup Verification Error",
                message=f"Process failed completely: {e}",
            )
