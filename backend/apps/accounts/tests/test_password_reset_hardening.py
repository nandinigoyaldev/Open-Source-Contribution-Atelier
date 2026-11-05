"""
Password reset hardening: account enumeration, token storage, single use, rate
limits and the audit trail.

SQLite has no row locks, so the concurrent test here shows the single-use guarantee
holds with threads on whichever engine runs it. On SQLite that mostly exercises the
conditional UPDATE, not ``select_for_update``.
"""

import re
import threading
import time
import uuid
from datetime import timedelta
from typing import Any
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import pytest
from django.contrib.auth import get_user_model
from django.core import mail as django_mail
from django.core.cache import cache
from django.db import OperationalError, connection, connections
from django.db.migrations.executor import MigrationExecutor
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.utils.module_loading import import_string
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import MagicLinkToken, PasswordResetToken
from apps.accounts.services import (
    PASSWORD_RESET_COMPLETED,
    PASSWORD_RESET_FAILED,
    PASSWORD_RESET_RATE_LIMITED,
    PASSWORD_RESET_REQUESTED,
    PASSWORD_RESET_SUPPRESSED,
    create_password_reset_token,
    redeem_password_reset_token,
    validate_password_reset_token,
)
from apps.accounts.tasks import process_password_reset_request
from apps.audit.models import AuditEvent

mail: Any = django_mail
User: Any = get_user_model()
Tokens: Any = PasswordResetToken._default_manager
Events: Any = AuditEvent._default_manager

REQUEST_URL = "/api/auth/password-reset/"
CONFIRM_URL = "/api/auth/password-reset/confirm/"
VALIDATE_URL = "/api/auth/password-reset/validate-token/"
NEW_PASSWORD = "BrandNewPassword789!"


@pytest.fixture(autouse=True)
def clean_throttle_state():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def user(db) -> Any:
    return User._default_manager.create_user(
        username="reset_user",
        email="reset_user@example.com",
        password="OldSecurePassword123!",
    )


@pytest.fixture
def run_queue(monkeypatch) -> None:
    """Run queued tasks on the spot, the way a worker would pick them up."""

    def run_now(path, *args, **kwargs):
        import_string(path)(*args, **kwargs)

    monkeypatch.setattr("apps.accounts.views.async_task", run_now)


def client_from(ip: str = "203.0.113.10") -> APIClient:
    client = APIClient()
    client.defaults["REMOTE_ADDR"] = ip
    return client


def post(client: APIClient, url: str, data: dict) -> Any:
    return client.post(url, data, format="json")


def token_from_email(message: Any) -> str:
    link = re.search(r"https?://\S+", message.body).group(0)  # type: ignore[union-attr]
    return parse_qs(urlsplit(link).query)["token"][0]


def events(operation: str) -> Any:
    return Events.filter(extra__operation=operation)


def age_token(reset_token: Any, **delta: Any) -> None:
    Tokens.filter(pk=reset_token.pk).update(
        created_at=timezone.now() - timedelta(**delta)
    )


@pytest.mark.django_db
class TestRequestDoesNotRevealAccounts:
    def request_with_queue_mocked(self, email: str, ip: str) -> Any:
        with (
            patch("apps.accounts.views.async_task") as queue,
            CaptureQueriesContext(connection) as queries,
        ):
            response = post(client_from(ip), REQUEST_URL, {"email": email})
        # Middleware also runs queries here (sessions, sampled perf rows), so compare
        # only what could depend on the account.
        account_sql = [
            query["sql"]
            for query in queries
            if "auth_user" in query["sql"]
            or "accounts_passwordresettoken" in query["sql"]
        ]
        return response, queue, account_sql

    def test_known_and_unknown_addresses_take_the_same_path(self, user):
        known, known_queue, known_sql = self.request_with_queue_mocked(
            user.email, "203.0.113.11"
        )
        unknown, unknown_queue, unknown_sql = self.request_with_queue_mocked(
            "nobody@example.com", "203.0.113.12"
        )

        assert known.status_code == unknown.status_code == status.HTTP_200_OK
        assert known.content == unknown.content
        assert sorted(known.headers) == sorted(unknown.headers)

        # Neither request touches the account, and each queues one task of the same shape.
        assert known_sql == unknown_sql == []
        assert known_queue.call_count == unknown_queue.call_count == 1
        assert known_queue.call_args.args == unknown_queue.call_args.args
        assert set(known_queue.call_args.kwargs) == set(unknown_queue.call_args.kwargs)

    def test_the_request_itself_creates_nothing(self, user):
        response, queue, _ = self.request_with_queue_mocked(user.email, "203.0.113.13")

        assert response.status_code == status.HTTP_200_OK
        assert Tokens.count() == 0
        assert mail.outbox == []
        assert queue.call_args.kwargs["email"] == user.email

    def test_mixed_case_address_still_finds_the_account(self, user, run_queue):
        post(client_from(), REQUEST_URL, {"email": "Reset_User@Example.com"})

        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [user.email]

    def test_unknown_address_gets_no_email_or_token(self, db, run_queue):
        response = post(client_from(), REQUEST_URL, {"email": "nobody@example.com"})

        assert response.status_code == status.HTTP_200_OK
        assert mail.outbox == []
        assert Tokens.count() == 0


@pytest.mark.django_db
class TestTokenStorage:
    def test_only_a_hash_is_stored(self, user):
        reset_token = create_password_reset_token(user)
        raw = str(reset_token.token)

        row = Tokens.filter(pk=reset_token.pk).values().get()
        assert raw not in {str(value) for value in row.values()}
        assert row["token_hash"] == PasswordResetToken.hash_token(raw)
        assert len(row["token_hash"]) == 64

    def test_raw_token_cannot_be_read_back(self, user):
        reset_token = create_password_reset_token(user)

        assert reset_token.token is not None
        assert Tokens.get(pk=reset_token.pk).token is None

    def test_saving_again_keeps_the_same_token(self, user):
        reset_token: Any = create_password_reset_token(user)
        token_hash = reset_token.token_hash

        reset_token.is_used = True
        reset_token.save()

        assert Tokens.get(pk=reset_token.pk).token_hash == token_hash

    def test_raw_token_stays_out_of_the_queue(self, user):
        with patch("apps.accounts.views.async_task") as queue:
            post(client_from(), REQUEST_URL, {"email": user.email})

        assert set(queue.call_args.kwargs) == {
            "email",
            "ip_address",
            "user_agent",
            "request_id",
        }

    def test_emailed_link_keeps_its_format_and_works(self, user, run_queue):
        post(client_from(), REQUEST_URL, {"email": user.email})

        message = mail.outbox[0]
        assert "/reset-password?token=" in message.body
        raw = token_from_email(message)
        assert str(uuid.UUID(raw)) == raw

        response = post(client_from(), VALIDATE_URL, {"token": raw})
        assert response.status_code == status.HTTP_200_OK

        response = post(
            client_from(), CONFIRM_URL, {"token": raw, "new_password": NEW_PASSWORD}
        )
        assert response.status_code == status.HTTP_200_OK

        user.refresh_from_db()
        assert user.check_password(NEW_PASSWORD)

    def test_malformed_token_is_invalid_not_an_error(self, db):
        assert validate_password_reset_token("not-a-uuid") == (
            False,
            None,
            "invalid_token",
        )


@pytest.mark.django_db
class TestTokenIsBoundToItsAction:
    def test_hash_depends_on_the_purpose(self, user):
        reset_token = create_password_reset_token(user)
        raw = str(reset_token.token)

        assert reset_token.token_hash != (
            salted_hmac("another.purpose", raw, algorithm="sha256").hexdigest()
        )

    def test_magic_link_token_cannot_reset_a_password(self, user):
        magic: Any = MagicLinkToken._default_manager.create(user=user)

        response = post(
            client_from(),
            CONFIRM_URL,
            {"token": str(magic.token), "new_password": NEW_PASSWORD},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["error"] == "invalid_token"
        user.refresh_from_db()
        assert not user.check_password(NEW_PASSWORD)


@pytest.mark.django_db
class TestSingleUse:
    def test_replay_is_rejected(self, user):
        raw = str(create_password_reset_token(user).token)

        assert redeem_password_reset_token(raw, NEW_PASSWORD) == (True, None)
        assert redeem_password_reset_token(raw, "AnotherPassword456!") == (
            False,
            "invalid_token",
        )

        user.refresh_from_db()
        assert user.check_password(NEW_PASSWORD)

    def test_a_new_request_kills_the_previous_link(self, user):
        first = str(create_password_reset_token(user).token)
        second = str(create_password_reset_token(user).token)

        assert validate_password_reset_token(first)[2] == "invalid_token"
        assert validate_password_reset_token(second)[0] is True

    def test_expired_token_cannot_be_redeemed(self, user):
        reset_token = create_password_reset_token(user)
        age_token(reset_token, seconds=901)

        assert redeem_password_reset_token(str(reset_token.token), NEW_PASSWORD) == (
            False,
            "expired_token",
        )
        user.refresh_from_db()
        assert not user.check_password(NEW_PASSWORD)

    def test_changing_the_password_kills_the_link(self, user):
        raw = str(create_password_reset_token(user).token)

        client = client_from()
        client.force_authenticate(user=user)
        response = post(
            client,
            "/api/auth/change-password/",
            {"old_password": "OldSecurePassword123!", "new_password": NEW_PASSWORD},
        )
        assert response.status_code == status.HTTP_200_OK, response.content

        response = post(client_from(), VALIDATE_URL, {"token": raw})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["error"] == "invalid_token"

    def test_losing_a_race_changes_nothing(self, user):
        """
        The second request read the token as unused before the first one committed.
        The read is pinned to that moment so the outcome does not depend on timing.
        """
        raw = str(create_password_reset_token(user).token)
        read_before_the_winner_committed = validate_password_reset_token(raw)

        assert redeem_password_reset_token(raw, NEW_PASSWORD) == (True, None)

        with patch(
            "apps.accounts.services.validate_password_reset_token",
            return_value=read_before_the_winner_committed,
        ):
            outcome = redeem_password_reset_token(raw, "SecondPassword456!")

        assert outcome == (False, "invalid_token")
        user.refresh_from_db()
        assert user.check_password(NEW_PASSWORD)
        assert events(PASSWORD_RESET_COMPLETED).count() == 1
        assert (
            events(PASSWORD_RESET_FAILED).get().extra["payload"]["reason"]
            == "used_token"
        )

    def test_token_survives_when_the_reset_fails_halfway(self, user):
        reset_token = create_password_reset_token(user)
        raw = str(reset_token.token)

        with patch(
            "apps.accounts.services.revoke_user_sessions",
            side_effect=RuntimeError("boom"),
        ):
            with pytest.raises(RuntimeError):
                redeem_password_reset_token(raw, NEW_PASSWORD)

        assert Tokens.get(pk=reset_token.pk).is_used is False
        user.refresh_from_db()
        assert not user.check_password(NEW_PASSWORD)
        assert redeem_password_reset_token(raw, NEW_PASSWORD) == (True, None)


@pytest.mark.django_db(transaction=True)
def test_concurrent_confirms_have_exactly_one_winner(user):
    raw = str(create_password_reset_token(user).token)
    attempts = 6
    start = threading.Barrier(attempts)
    outcomes: list = []

    def confirm(number: int) -> None:
        password = f"ConcurrentPassword{number}!"
        try:
            start.wait(timeout=10)
            for _ in range(200):
                try:
                    outcomes.append(
                        (redeem_password_reset_token(raw, password), password)
                    )
                    return
                except OperationalError:
                    # SQLite reports lock contention as an error instead of waiting.
                    time.sleep(0.01)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=confirm, args=(n,)) for n in range(attempts)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert len(outcomes) == attempts
    winners = [password for (success, _), password in outcomes if success]
    losers = [error for (success, error), _ in outcomes if not success]
    assert len(winners) == 1
    assert set(losers) == {"invalid_token"}

    user.refresh_from_db()
    assert user.check_password(winners[0])


@pytest.mark.django_db(transaction=True)
def test_migration_drops_rows_with_raw_tokens_and_can_go_back(user):
    before = [("accounts", "0030_webauthncredential")]
    after = [("accounts", "0031_passwordresettoken_token_hash")]
    # Two rows, because going back re-adds a unique column to this table.
    create_password_reset_token(user)
    create_password_reset_token(user)

    try:
        MigrationExecutor(connection).migrate(before)
        with connection.cursor() as cursor:
            columns = connection.introspection.get_table_description(
                cursor, "accounts_passwordresettoken"
            )
        assert "token_hash" not in [column.name for column in columns]

        executor = MigrationExecutor(connection)
        old_state: Any = executor.loader.project_state(before)
        old_state.apps.get_model("accounts", "PasswordResetToken").objects.create(
            user_id=user.pk
        )
        executor.migrate(after)
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    assert Tokens.count() == 0
    assert validate_password_reset_token(uuid.uuid4())[0] is False
    assert create_password_reset_token(user).token is not None


@pytest.mark.django_db
class TestRateLimits:
    def test_repeated_requests_for_one_address_are_limited_across_addresses(self, user):
        for last_octet in (21, 22, 23):
            response = post(
                client_from(f"203.0.113.{last_octet}"),
                REQUEST_URL,
                {"email": user.email},
            )
            assert response.status_code == status.HTTP_200_OK

        response = post(client_from("203.0.113.24"), REQUEST_URL, {"email": user.email})
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_address_variants_share_one_limit(self, user):
        for variant in ("reset_user@example.com", "RESET_USER@example.com"):
            post(client_from("203.0.113.25"), REQUEST_URL, {"email": variant})
        post(
            client_from("203.0.113.26"),
            REQUEST_URL,
            {"email": " Reset_User@EXAMPLE.com "},
        )

        response = post(client_from("203.0.113.27"), REQUEST_URL, {"email": user.email})
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_being_signed_in_does_not_skip_the_limit(self, user, run_queue):
        client = client_from("203.0.113.28")
        client.force_authenticate(user=user)

        for _ in range(3):
            assert (
                post(client, REQUEST_URL, {"email": "victim@example.com"}).status_code
                == status.HTTP_200_OK
            )

        response = post(client, REQUEST_URL, {"email": "victim@example.com"})
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_confirm_is_limited_for_guessing(self, db):
        client = client_from("203.0.113.29")
        payload = {"token": str(uuid.uuid4()), "new_password": NEW_PASSWORD}

        for _ in range(3):
            assert post(client, CONFIRM_URL, payload).status_code == 400

        response = post(client, CONFIRM_URL, payload)
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_validate_is_limited_for_guessing(self, db, settings):
        # The per-minute limit on all of /api/auth/ would otherwise answer first.
        settings.DISABLE_RATE_LIMITING = True
        client = client_from("203.0.113.30")
        payload = {"token": str(uuid.uuid4())}

        for _ in range(10):
            assert post(client, VALIDATE_URL, payload).status_code == 400

        response = post(client, VALIDATE_URL, payload)
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert response.json()["code"] == "rate_limited"
        assert "reset link" in response.json()["message"]

    def test_validate_has_its_own_budget(self, db):
        client = client_from("203.0.113.31")

        for _ in range(4):
            post(client, VALIDATE_URL, {"token": str(uuid.uuid4())})

        response = post(client, REQUEST_URL, {"email": "someone@example.com"})
        assert response.status_code == status.HTTP_200_OK

    def test_account_cap_holds_when_the_request_throttles_do_not(self, user, settings):
        settings.PASSWORD_RESET_MAX_PER_HOUR = 2

        for _ in range(4):
            process_password_reset_request(user.email)

        assert len(mail.outbox) == 2
        assert Tokens.filter(user=user).count() == 2
        suppressed = events(PASSWORD_RESET_SUPPRESSED)
        assert suppressed.count() == 2
        assert suppressed.first().resource_id == str(user.pk)

    def test_account_cap_leaves_the_last_link_working(self, user, settings):
        settings.PASSWORD_RESET_MAX_PER_HOUR = 1
        process_password_reset_request(user.email)
        raw = token_from_email(mail.outbox[0])

        process_password_reset_request(user.email)

        assert len(mail.outbox) == 1
        assert validate_password_reset_token(raw)[0] is True

    def test_account_cap_is_a_rolling_hour(self, user, settings):
        settings.PASSWORD_RESET_MAX_PER_HOUR = 1
        age_token(create_password_reset_token(user), minutes=61)

        process_password_reset_request(user.email)

        assert len(mail.outbox) == 1


@pytest.mark.django_db
class TestAuditTrail:
    def test_request_for_a_real_account(self, user, run_queue):
        client = client_from("203.0.113.40")
        response: Any = client.post(
            REQUEST_URL,
            {"email": user.email},
            format="json",
            HTTP_USER_AGENT="pytest-agent",
        )

        event = events(PASSWORD_RESET_REQUESTED).get()
        assert event.extra["source"] == "security"
        assert event.extra["payload"] == {"account_found": True}
        assert event.resource_type == "auth.user"
        assert event.resource_id == str(user.pk)
        assert event.actor is None
        assert event.ip_address == "203.0.113.40"
        assert event.user_agent == "pytest-agent"
        assert event.correlation_id == response.headers["X-Request-ID"]

    def test_request_for_an_unknown_address_keeps_no_address(self, db, run_queue):
        post(client_from(), REQUEST_URL, {"email": "nobody@example.com"})

        event = events(PASSWORD_RESET_REQUESTED).get()
        assert event.resource_id == "unknown"
        assert event.extra["payload"]["account_found"] is False
        fingerprint = event.extra["payload"]["email_fingerprint"]
        assert re.fullmatch(r"[0-9a-f]{16}", fingerprint)
        assert "nobody" not in str(event.extra)

    def test_repeats_for_one_address_can_be_grouped(self, db, run_queue):
        post(client_from("203.0.113.41"), REQUEST_URL, {"email": "nobody@example.com"})
        post(client_from("203.0.113.42"), REQUEST_URL, {"email": "NOBODY@example.com"})
        post(client_from("203.0.113.43"), REQUEST_URL, {"email": "other@example.com"})

        fingerprints = [
            event.extra["payload"]["email_fingerprint"]
            for event in events(PASSWORD_RESET_REQUESTED).order_by("pk")
        ]
        assert fingerprints[0] == fingerprints[1] != fingerprints[2]

    def test_completed_reset(self, user):
        raw = str(create_password_reset_token(user).token)

        post(
            client_from("203.0.113.44"),
            CONFIRM_URL,
            {"token": raw, "new_password": NEW_PASSWORD},
        )

        event = events(PASSWORD_RESET_COMPLETED).get()
        assert event.action == AuditEvent.ACTION_UPDATED
        assert event.resource_id == str(user.pk)
        assert event.ip_address == "203.0.113.44"
        assert raw not in str(event.extra)
        assert NEW_PASSWORD not in str(event.extra)

    @pytest.mark.parametrize(
        "url, stage", [(CONFIRM_URL, "confirm"), (VALIDATE_URL, "validate")]
    )
    def test_failed_attempts_say_why_but_the_caller_does_not_see_it(
        self, user, url, stage
    ):
        used = create_password_reset_token(user)
        Tokens.filter(pk=used.pk).update(is_used=True)
        expired = create_password_reset_token(user)
        age_token(expired, minutes=20)

        cases = [
            (uuid.uuid4(), "unknown_token", "invalid_token", "unknown"),
            (used.token, "used_token", "invalid_token", str(user.pk)),
            (expired.token, "expired_token", "expired_token", str(user.pk)),
        ]
        for token, reason, error, resource_id in cases:
            cache.clear()
            response = post(
                client_from(),
                url,
                {"token": str(token), "new_password": NEW_PASSWORD},
            )
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert response.json()["error"] == error

            event = events(PASSWORD_RESET_FAILED).first()
            assert event.extra["payload"] == {"stage": stage, "reason": reason}
            assert event.resource_id == resource_id
            assert str(token) not in str(event.extra)

    def test_rate_limited_caller_is_recorded_once(self, user):
        client = client_from("203.0.113.45")
        for _ in range(8):
            post(client, REQUEST_URL, {"email": "target@example.com"})

        event = events(PASSWORD_RESET_RATE_LIMITED).get()
        assert event.ip_address == "203.0.113.45"
        assert event.extra["payload"]["stage"] == "request"
        assert "target" not in str(event.extra)
        assert event.extra["payload"]["email_fingerprint"]

    def test_forwarded_header_does_not_decide_the_recorded_address(
        self, user, settings
    ):
        settings.TRUSTED_PROXY_COUNT = 0
        client = client_from("203.0.113.46")
        client.post(
            VALIDATE_URL,
            {"token": str(uuid.uuid4())},
            format="json",
            HTTP_X_FORWARDED_FOR="198.51.100.1",
        )

        assert events(PASSWORD_RESET_FAILED).get().ip_address == "203.0.113.46"

    def test_an_audit_problem_does_not_block_the_reset(self, user):
        raw = str(create_password_reset_token(user).token)

        with patch(
            "apps.audit.security_events.AuditEvent._default_manager.create",
            side_effect=RuntimeError("audit table unavailable"),
        ):
            outcome = redeem_password_reset_token(raw, NEW_PASSWORD)

        assert outcome == (True, None)
        user.refresh_from_db()
        assert user.check_password(NEW_PASSWORD)
