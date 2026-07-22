import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("backup.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class DatabaseBackup:
    """
    PostgreSQL database backup utility with S3 upload and retention management.
    """

    # Default values
    DEFAULT_PORT = "5432"
    DEFAULT_RETENTION_DAYS = 30
    DEFAULT_S3_REGION = "us-east-1"
    PG_DUMP_TIMEOUT = 300  # 5 minutes
    S3_RETRY_COUNT = 3
    S3_RETRY_DELAY = 2  # seconds
    COMPRESS_LEVEL = 6  # gzip compression level (1-9)

    def __init__(self) -> None:
        """Initialize backup configuration from environment variables."""
        # Database configuration
        self.db_name = self._get_env_or_raise("DB_NAME")
        self.db_user = self._get_env_or_raise("DB_USER")
        self.db_password = self._get_env_or_raise("DB_PASSWORD")
        self.db_host = self._get_env_or_raise("DB_HOST")
        self.db_port = os.getenv("DB_PORT", self.DEFAULT_PORT)

        # S3 configuration
        self.s3_bucket = os.getenv("S3_BUCKET_NAME")
        self.s3_region = os.getenv("AWS_REGION", self.DEFAULT_S3_REGION)
        self.s3_access_key = os.getenv("S3_ACCESS_KEY")
        self.s3_secret_key = os.getenv("S3_SECRET_KEY")

        # Backup directory
        self.backup_dir = Path(__file__).resolve().parent.parent / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Retention
        self.retention_days = int(
            os.getenv("BACKUP_RETENTION_DAYS", self.DEFAULT_RETENTION_DAYS)
        )

        # Validate S3 configuration if bucket is set
        if self.s3_bucket and (not self.s3_access_key or not self.s3_secret_key):
            logger.warning(
                "S3 bucket configured but AWS credentials missing. Uploads will be skipped."
            )

    @staticmethod
    def _get_env_or_raise(key: str) -> str:
        """Get environment variable or raise ValueError if missing."""
        value = os.getenv(key)
        if value is None:
            raise ValueError(f"Missing required environment variable: {key}")
        return value

    def create_backup(self) -> Optional[Path]:
        """
        Create a PostgreSQL backup using pg_dump.

        Returns:
            Path to the backup file on success, None on failure.
        """
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
            "p",  # plain text (customizable)
            "--no-owner",
            "--no-privileges",
        ]

        logger.info(f"Starting backup: {filepath}")

        try:
            # Use subprocess with timeout and capture stderr for diagnostics
            with open(filepath, "w") as f:
                result = subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    env=env,
                    timeout=self.PG_DUMP_TIMEOUT,
                    check=False,
                )

            if result.returncode != 0:
                error_msg = result.stderr.decode("utf-8", errors="replace")
                logger.error(f"pg_dump failed with code {result.returncode}: {error_msg}")
                self._cleanup_partial_file(filepath)
                return None

            logger.info(f"✅ Backup created: {filepath} ({filepath.stat().st_size / 1024:.2f} KB)")
            return filepath

        except subprocess.TimeoutExpired:
            logger.error(f"pg_dump timed out after {self.PG_DUMP_TIMEOUT} seconds")
            self._cleanup_partial_file(filepath)
            return None
        except FileNotFoundError:
            logger.error("pg_dump command not found. Is PostgreSQL installed?")
            return None
        except OSError as e:
            logger.error(f"OS error during backup: {e}")
            self._cleanup_partial_file(filepath)
            return None

    def _cleanup_partial_file(self, filepath: Path) -> None:
        """Remove a partial/empty backup file left behind by a failed run."""
        try:
            if filepath.exists():
                filepath.unlink()
                logger.info(f"🧹 Removed partial backup: {filepath}")
        except OSError as e:
            logger.warning(f"Could not remove partial backup {filepath}: {e}")

    def compress_backup(self, filepath: Path) -> Optional[Path]:
        """
        Compress the backup file using gzip.

        Args:
            filepath: Path to the uncompressed SQL file.

        Returns:
            Path to compressed file on success, None on failure.
        """
        compressed_path = filepath.with_suffix(".sql.gz")

        try:
            import gzip
            import shutil

            with open(filepath, "rb") as f_in:
                with gzip.open(compressed_path, "wb", compresslevel=self.COMPRESS_LEVEL) as f_out:
                    shutil.copyfileobj(f_in, f_out)

            # Remove original file after successful compression
            filepath.unlink()
            logger.info(f"✅ Backup compressed: {compressed_path} ({compressed_path.stat().st_size / 1024:.2f} KB)")
            return compressed_path

        except (OSError, gzip.error) as e:
            logger.error(f"Compression failed: {e}")
            # Keep original file if compression fails
            return filepath

    def upload_to_s3(self, filepath: Path) -> bool:
        """
        Upload the backup file to S3 with retry logic.

        Args:
            filepath: Path to the file to upload.

        Returns:
            True if upload succeeded, False otherwise.
        """
        if not self.s3_bucket:
            logger.info("S3 bucket not configured, skipping upload.")
            return False

        if not self.s3_access_key or not self.s3_secret_key:
            logger.warning("AWS credentials missing, skipping upload.")
            return False

        try:
            s3 = boto3.client(
                "s3",
                region_name=self.s3_region,
                aws_access_key_id=self.s3_access_key,
                aws_secret_access_key=self.s3_secret_key,
            )

            s3_key = f"backups/{filepath.name}"
            logger.info(f"Uploading {filepath} to s3://{self.s3_bucket}/{s3_key}")

            # Retry logic
            for attempt in range(1, self.S3_RETRY_COUNT + 1):
                try:
                    s3.upload_file(str(filepath), self.s3_bucket, s3_key)
                    logger.info(f"✅ Uploaded to S3: s3://{self.s3_bucket}/{s3_key}")
                    return True
                except ClientError as e:
                    if attempt < self.S3_RETRY_COUNT:
                        wait = self.S3_RETRY_DELAY * attempt
                        logger.warning(
                            f"S3 upload attempt {attempt} failed: {e}. Retrying in {wait}s..."
                        )
                        time.sleep(wait)
                    else:
                        raise

        except ClientError as e:
            logger.error(f"S3 upload failed after {self.S3_RETRY_COUNT} attempts: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during S3 upload: {e}")
            return False

        return False

    def cleanup_old_backups(self) -> None:
        """
        Delete backup files older than retention_days from local backup directory.
        """
        cutoff = time.time() - (self.retention_days * 24 * 60 * 60)
        deleted_count = 0

        for pattern in ("*.sql.gz", "*.sql"):
            for file in self.backup_dir.glob(pattern):
                if file.is_file() and file.stat().st_mtime < cutoff:
                    try:
                        file.unlink()
                        deleted_count += 1
                        logger.info(f"🧹 Deleted old backup: {file}")
                    except OSError as e:
                        logger.warning(f"Could not delete {file}: {e}")

        if deleted_count == 0:
            logger.info("No old backups to clean up.")

    def run(self) -> bool:
        """
        Execute the full backup workflow: create, compress, upload, cleanup.

        Returns:
            True if all steps succeeded, False otherwise.
        """
        logger.info(f"📦 Starting database backup at {datetime.now()}")

        # Step 1: Create backup
        backup_file = self.create_backup()
        if not backup_file:
            logger.error("Backup creation failed. Aborting.")
            return False

        # Step 2: Compress
        compressed_file = self.compress_backup(backup_file)
        if compressed_file is None:
            logger.error("Compression failed. Aborting.")
            return False

        # Step 3: Upload to S3 (if configured)
        upload_success = self.upload_to_s3(compressed_file)
        if not upload_success and self.s3_bucket:
            logger.warning("S3 upload failed, but local backup is preserved.")

        # Step 4: Cleanup old backups
        self.cleanup_old_backups()

        logger.info(f"✅ Backup completed at {datetime.now()}")
        return True


if __name__ == "__main__":
    try:
        backup = DatabaseBackup()
        success = backup.run()
        if not success:
            logger.error("Backup process finished with errors.")
            exit(1)
        exit(0)
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        exit(1)
    except KeyboardInterrupt:
        logger.info("Backup interrupted by user.")
        exit(130)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        exit(1)