import pytest
from datetime import timedelta
from django.utils import timezone
from django.core.management import call_command
from django.contrib.sessions.models import Session
from rest_framework_simplejwt.token_blacklist.models import (
    OutstandingToken,
    BlacklistedToken,
)
from apps.accounts.models import PasswordResetToken, OTPToken, MagicLinkToken
from django.contrib.auth import get_user_model
from io import StringIO

User = get_user_model()


@pytest.mark.django_db
def test_purge_sessions_command():
    # Create test user
    user = User.objects.create_user(
        username="testpurgeuser", email="testpurge@example.com", password="password123"
    )

    now = timezone.now()
    older_than_30_days = now - timedelta(days=31)
    within_30_days = now - timedelta(days=10)

    # 1. Setup simple_jwt tokens
    # Expired token
    t1 = OutstandingToken.objects.create(
        user=user,
        jti="jti1",
        token="token1",
        created_at=older_than_30_days,
        expires_at=older_than_30_days,
    )
    BlacklistedToken.objects.create(token=t1)

    # Valid token
    t2 = OutstandingToken.objects.create(
        user=user,
        jti="jti2",
        token="token2",
        created_at=within_30_days,
        expires_at=now + timedelta(days=1),
    )

    # 2. Setup Django Sessions
    # Expired session
    s1 = Session.objects.create(
        session_key="session1", session_data="data1", expire_date=older_than_30_days
    )
    # Valid session
    s2 = Session.objects.create(
        session_key="session2",
        session_data="data2",
        expire_date=now + timedelta(days=1),
    )

    # 3. Setup transient user tokens
    # Expired transient tokens
    pr1 = PasswordResetToken.objects.create(user=user)
    pr1.created_at = older_than_30_days
    pr1.save()

    otp1 = OTPToken.objects.create(user=user)
    otp1.created_at = older_than_30_days
    otp1.save()

    ml1 = MagicLinkToken.objects.create(user=user)
    ml1.created_at = older_than_30_days
    ml1.save()

    # Valid transient tokens
    pr2 = PasswordResetToken.objects.create(user=user)
    pr2.created_at = within_30_days
    pr2.save()

    otp2 = OTPToken.objects.create(user=user)
    otp2.created_at = within_30_days
    otp2.save()

    ml2 = MagicLinkToken.objects.create(user=user)
    ml2.created_at = within_30_days
    ml2.save()

    # Verify counts before dry-run
    assert OutstandingToken.objects.count() == 2
    assert BlacklistedToken.objects.count() == 1
    assert Session.objects.count() == 2
    assert PasswordResetToken.objects.count() == 2
    assert OTPToken.objects.count() == 2
    assert MagicLinkToken.objects.count() == 2

    # Run dry-run
    out_dry = StringIO()
    call_command("purge_sessions", "--dry-run", stdout=out_dry)
    output_dry = out_dry.getvalue()

    # Dry-run should not delete anything
    assert OutstandingToken.objects.count() == 2
    assert BlacklistedToken.objects.count() == 1
    assert Session.objects.count() == 2
    assert PasswordResetToken.objects.count() == 2
    assert OTPToken.objects.count() == 2
    assert MagicLinkToken.objects.count() == 2

    assert "Expired JWT refresh tokens: 1" in output_dry
    assert "Expired database sessions: 1" in output_dry
    assert "Stale password reset tokens (>30 days): 1" in output_dry
    assert "Stale OTP tokens (>30 days): 1" in output_dry
    assert "Stale magic link tokens (>30 days): 1" in output_dry

    # Run real purge
    out_real = StringIO()
    call_command("purge_sessions", stdout=out_real)
    output_real = out_real.getvalue()

    # Should purge expired and keep valid ones
    assert OutstandingToken.objects.count() == 1
    assert OutstandingToken.objects.filter(token="token2").exists()
    assert BlacklistedToken.objects.count() == 0  # Blacklist token was cascades deleted

    assert Session.objects.count() == 1
    assert Session.objects.filter(session_key="session2").exists()

    assert PasswordResetToken.objects.count() == 1
    assert PasswordResetToken.objects.filter(pk=pr2.pk).exists()

    assert OTPToken.objects.count() == 1
    assert OTPToken.objects.filter(pk=otp2.pk).exists()

    assert MagicLinkToken.objects.count() == 1
    assert MagicLinkToken.objects.filter(pk=ml2.pk).exists()

    assert "Expired JWT refresh tokens: 1" in output_real
    assert "Expired database sessions: 1" in output_real
    assert "Stale password reset tokens (>30 days): 1" in output_real
    assert "Stale OTP tokens (>30 days): 1" in output_real
    assert "Stale magic link tokens (>30 days): 1" in output_real
    assert "Purge complete. Total records purged: 5" in output_real
