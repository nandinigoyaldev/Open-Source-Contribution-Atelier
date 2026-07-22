import os
import subprocess
from datetime import datetime
from pathlib import Path

import boto3
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class DatabaseBackup:
    def __init__(self):
        # Database config
        self.db_name = os.getenv("DB_NAME")
        self.db_user = os.getenv("DB_USER")
        self.db_password = os.getenv("DB_PASSWORD")
        self.db_host = os.getenv("DB_HOST")
        self.db_port = os.getenv("DB_PORT")

        # S3 configuration - FIXED
        self.s3_bucket = os.getenv("S3_BUCKET_NAME")  # Changed from s3_bucket_name
        self.s3_region = os.getenv("AWS_REGION", "us-east-1")  # Added
        self.s3_access_key = os.getenv("S3_ACCESS_KEY")
        self.s3_secret_key = os.getenv("S3_SECRET_KEY")

        # Backup config
        self.backup_dir = Path(__file__).resolve().parent.parent / "backups"
        self.backup_dir.mkdir(exist_ok=True)
        self.retention_days = int(os.getenv("BACKUP_RETENTION_DAYS", 30))

    def create_backup(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"backup_{self.db_name}_{timestamp}.sql"
        filepath = self.backup_dir / filename

        env = os.environ.copy()
        if self.db_password:
            env["PGPASSWORD"] = self.db_password

        cmd = [
            "pg_dump",
            "-h",
            self.db_host,
            "-p",
            self.db_port,
            "-U",
            self.db_user,
            "-d",
            self.db_name,
            "--clean",
            "--if-exists",
            "-F",
            "p",
        ]

        try:
            with open(filepath, "w") as f:
                subprocess.run(cmd, stdout=f, env=env, check=True)
            print(f"✅ Backup created: {filepath}")
            return filepath
        except subprocess.CalledProcessError as e:
            print(f"❌ Backup failed: {e}")
            self._cleanup_partial_file(filepath)
            return None

    def _cleanup_partial_file(self, filepath):
        """Remove a partial/empty backup file left behind by a failed pg_dump run."""
        try:
            if filepath.exists():
                filepath.unlink()
                print(f"🧹 Removed partial backup after failure: {filepath}")
        except OSError as e:
            print(f"⚠️ Could not remove partial backup {filepath}: {e}")

    def compress_backup(self, filepath):
        compressed_path = filepath.with_suffix(".sql.gz")
        subprocess.run(["gzip", str(filepath)], check=True)
        print(f"✅ Backup compressed: {compressed_path}")
        return compressed_path

    def upload_to_s3(self, filepath):
        if not self.s3_bucket:
            print("⚠️ S3 bucket not configured, skipping upload")
            return False

        if not self.s3_access_key or not self.s3_secret_key:
            print("⚠️ AWS credentials not configured, skipping upload")
            return False

        try:
            s3 = boto3.client(
                "s3",
                region_name=self.s3_region,
                aws_access_key_id=self.s3_access_key,
                aws_secret_access_key=self.s3_secret_key,
            )

            s3_key = f"backups/{filepath.name}"
            sse_algorithm = os.getenv("S3_BACKUP_SSE_ALGORITHM", "AES256")
            s3.upload_file(
                str(filepath),
                self.s3_bucket,
                s3_key,
                ExtraArgs={"ServerSideEncryption": sse_algorithm},
            )
            print(
                f"✅ Uploaded to S3 (encrypted, {sse_algorithm}): s3://{self.s3_bucket}/{s3_key}"
            )
            return True
        except Exception as e:
            print(f"❌ S3 upload failed: {e}")
            return False

    def cleanup_old_backups(self):
        import time

        cutoff = time.time() - (self.retention_days * 24 * 60 * 60)

        # *.sql.gz = normal successful backups under retention policy.
        # *.sql (uncompressed) = orphaned leftovers from failed/interrupted
        # runs that predate this fix, or from a race where compression
        # never ran. Sweep both so nothing lingers past retention_days.
        for pattern in ("*.sql.gz", "*.sql"):
            for file in self.backup_dir.glob(pattern):
                if file.stat().st_mtime < cutoff:
                    file.unlink()
                    print(f"🧹 Deleted old backup: {file}")

    def run(self):
        print(f"📦 Starting database backup at {datetime.now()}")

        backup_file = self.create_backup()
        if not backup_file:
            return False

        compressed_file = self.compress_backup(backup_file)
        self.upload_to_s3(compressed_file)
        self.cleanup_old_backups()

        print(f"✅ Backup completed at {datetime.now()}")
        return True


if __name__ == "__main__":
    backup = DatabaseBackup()
    backup.run()
