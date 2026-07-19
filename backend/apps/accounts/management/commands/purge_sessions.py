import logging
from datetime import timedelta

from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

from apps.accounts.models import MagicLinkToken, OTPToken, PasswordResetToken

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Purge expired/stale user sessions, JWT refresh tokens, and transient auth tokens."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview the records that would be deleted without actually deleting them.",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        now = timezone.now()
        cutoff_30_days = now - timedelta(days=30)

        if dry_run:
            self.stdout.write(
                self.style.WARNING("--- DRY RUN MODE (No changes will be saved) ---")
            )

        # 1. SimpleJWT Expired Blacklist/Outstanding Tokens
        expired_tokens = OutstandingToken.objects.filter(expires_at__lt=now)
        expired_tokens_count = expired_tokens.count()

        # 2. Django Expired Sessions
        expired_sessions = Session.objects.filter(expire_date__lt=now)
        expired_sessions_count = expired_sessions.count()

        # 3. Stale Accounts transient tokens older than 30 days
        stale_password_reset = PasswordResetToken.objects.filter(
            created_at__lt=cutoff_30_days
        )
        stale_password_reset_count = stale_password_reset.count()

        stale_otp = OTPToken.objects.filter(created_at__lt=cutoff_30_days)
        stale_otp_count = stale_otp.count()

        stale_magic_link = MagicLinkToken.objects.filter(created_at__lt=cutoff_30_days)
        stale_magic_link_count = stale_magic_link.count()

        if not dry_run:
            # Perform deletions
            if expired_tokens_count > 0:
                expired_tokens.delete()
            if expired_sessions_count > 0:
                expired_sessions.delete()
            if stale_password_reset_count > 0:
                stale_password_reset.delete()
            if stale_otp_count > 0:
                stale_otp.delete()
            if stale_magic_link_count > 0:
                stale_magic_link.delete()

        # Print summary
        self.stdout.write(self.style.SUCCESS("\nPurge Summary:"))
        self.stdout.write(f"  Expired JWT refresh tokens: {expired_tokens_count}")
        self.stdout.write(f"  Expired database sessions: {expired_sessions_count}")
        self.stdout.write(
            f"  Stale password reset tokens (>30 days): {stale_password_reset_count}"
        )
        self.stdout.write(f"  Stale OTP tokens (>30 days): {stale_otp_count}")
        self.stdout.write(
            f"  Stale magic link tokens (>30 days): {stale_magic_link_count}"
        )

        total_purged = (
            expired_tokens_count
            + expired_sessions_count
            + stale_password_reset_count
            + stale_otp_count
            + stale_magic_link_count
        )

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nDry-run complete. Total records to purge: {total_purged}"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nPurge complete. Total records purged: {total_purged}"
                )
            )
