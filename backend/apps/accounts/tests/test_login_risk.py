"""Suspicious login detection: scoring, recording and the emailed code."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone as django_timezone
from rest_framework.test import APIClient

from apps.accounts.export import DataExportService
from apps.accounts.models import TOTPDevice, UserLoginHistory, UserSession
from apps.accounts.services.ip_intelligence import (
    IPInfo,
    OfflineIPIntelligence,
    get_ip_provider,
)
from apps.accounts.services.risk_engine import (
    IMPOSSIBLE_TRAVEL,
    NEW_DEVICE,
    NEW_PROXY_NETWORK,
    LoginRiskAnalyzer,
    device_fingerprint,
    distance_km,
)
from apps.accounts.totp import generate_totp_code
from apps.accounts.views import LoginView

User = get_user_model()

PASSWORD = "Str0ng-Passw0rd!"
LAPTOP = "Mozilla/5.0 (X11; Linux x86_64) Firefox/140.0"
PHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Safari/604.1"

HOME_IP = "203.0.113.10"
FAR_IP = "198.51.100.20"
PROXY_IP = "192.0.2.30"
UNKNOWN_IP = "192.0.2.99"
DELHI = IPInfo(latitude=28.61, longitude=77.21, country="IN", asn=64500)
LONDON = IPInfo(latitude=51.51, longitude=-0.13, country="GB", asn=64501)
PROXY = IPInfo(asn=64999, is_proxy=True)
PLACES = {HOME_IP: DELHI, FAR_IP: LONDON, PROXY_IP: PROXY}
HISTORY = UserLoginHistory._default_manager

NOW = datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc)
FAKE_PROVIDER = "apps.accounts.tests.test_login_risk.FakeProvider"


class FakeProvider:
    def lookup(self, ip_address):
        return PLACES.get(ip_address)


class BrokenProvider:
    def lookup(self, ip_address):
        raise RuntimeError("lookup is down")


def past(hours_ago=1.0, place=DELHI, user_agent=LAPTOP):
    return SimpleNamespace(
        created_at=NOW - timedelta(hours=hours_ago),
        latitude=place.latitude,
        longitude=place.longitude,
        asn=place.asn,
        device_fingerprint=device_fingerprint(user_agent),
    )


def analyze(ip, history, user_agent=LAPTOP, provider=None):
    analyzer = LoginRiskAnalyzer(provider or FakeProvider())
    return analyzer.analyze(ip, user_agent, NOW, history)


# ── Scoring ──────────────────────────────────────────────────────────────────


def test_distance_between_delhi_and_london():
    distance = distance_km(28.61, 77.21, 51.51, -0.13)

    assert distance == pytest.approx(6710, rel=0.01)


def test_delhi_to_london_in_an_hour_is_impossible_travel():
    result = analyze(FAR_IP, [past(hours_ago=1)])

    assert result.reasons == [IMPOSSIBLE_TRAVEL]
    assert result.score == 60


def test_delhi_to_london_in_twelve_hours_is_fine():
    assert analyze(FAR_IP, [past(hours_ago=12)]).score == 0


@pytest.mark.parametrize("speed, flagged", [(790, False), (810, True)])
def test_travel_limit_is_800_km_per_hour(speed, flagged):
    hours = distance_km(28.61, 77.21, 51.51, -0.13) / speed

    result = analyze(FAR_IP, [past(hours_ago=hours)])

    assert (IMPOSSIBLE_TRAVEL in result.reasons) is flagged


def test_short_hop_is_not_travel_even_when_instant():
    nearby = IPInfo(latitude=28.90, longitude=77.40, asn=64500)

    assert analyze(HOME_IP, [past(hours_ago=0, place=nearby)]).score == 0


def test_travel_uses_the_newest_login_that_has_a_position():
    history = [
        past(hours_ago=0.5, place=IPInfo()),
        past(hours_ago=1, place=LONDON),
        past(hours_ago=2, place=DELHI),
    ]

    assert IMPOSSIBLE_TRAVEL not in analyze(FAR_IP, history).reasons


def test_first_login_scores_nothing():
    assert analyze(PROXY_IP, [], user_agent=PHONE).score == 0


def test_unknown_address_scores_nothing_on_a_known_device():
    assert analyze(UNKNOWN_IP, [past(hours_ago=0)]).score == 0


@pytest.mark.parametrize(
    "history_place, flagged",
    [(DELHI, True), (PROXY, False), (IPInfo(), False)],
)
def test_proxy_network_counts_only_when_it_is_a_change(history_place, flagged):
    result = analyze(PROXY_IP, [past(place=history_place)])

    assert (NEW_PROXY_NETWORK in result.reasons) is flagged


def test_ordinary_network_change_is_not_flagged():
    assert analyze(FAR_IP, [past(hours_ago=48)]).score == 0


def test_new_device_alone_stays_under_the_threshold():
    result = analyze(HOME_IP, [past()], user_agent=PHONE)

    assert result.reasons == [NEW_DEVICE]
    assert result.score == 20


def test_browser_update_is_the_same_device():
    updated = LAPTOP.replace("140.0", "141.0.2")

    assert analyze(HOME_IP, [past()], user_agent=updated).score == 0


def test_proxy_plus_new_device_adds_up():
    result = analyze(PROXY_IP, [past()], user_agent=PHONE)

    assert result.score == 60


def test_default_provider_is_offline():
    provider = get_ip_provider()

    assert isinstance(provider, OfflineIPIntelligence)
    assert provider.lookup(FAR_IP) is None


def test_broken_provider_is_treated_as_unknown():
    result = analyze(FAR_IP, [past()], provider=BrokenProvider())

    assert result.score == 0
    assert result.ip_info == IPInfo()


# ── Login endpoint ───────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def no_login_throttle(monkeypatch):
    monkeypatch.setattr(LoginView, "throttle_classes", [])


@pytest.fixture
def places(settings):
    settings.LOGIN_RISK_IP_PROVIDER = FAKE_PROVIDER


@pytest.fixture
def enforced(settings, places):
    settings.LOGIN_RISK_CONFIRMATION_ENABLED = True


@pytest.fixture
def mailer():
    with patch("apps.accounts.services.login_risk.async_task") as task:
        yield task


@pytest.fixture
def member(db):
    return User.objects.create_user(
        username="risk-user", email="risk@example.com", password=PASSWORD
    )


def login(ip=HOME_IP, user_agent=LAPTOP, **extra) -> Any:
    return APIClient().post(
        "/api/auth/login/",
        {"username": "risk-user", "password": PASSWORD, **extra},
        format="json",
        REMOTE_ADDR=ip,
        HTTP_USER_AGENT=user_agent,
    )


def sent_code(mailer):
    return mailer.call_args.kwargs["code"]


def latest():
    return HISTORY.first()


def test_login_is_recorded(member, places):
    response = login()

    assert response.status_code == 200
    entry = latest()
    assert (entry.user, entry.outcome, entry.risk_score) == (member, "allowed", 0)
    assert (entry.ip_address, entry.country, entry.asn) == (HOME_IP, "IN", 64500)
    assert (entry.latitude, entry.longitude) == (28.61, 77.21)
    assert entry.user_agent == LAPTOP


def test_wrong_password_is_not_scored(member):
    response: Any = APIClient().post(
        "/api/auth/login/",
        {"username": "risk-user", "password": "nope"},
        format="json",
    )

    assert response.status_code == 401
    assert not HISTORY.exists()


def test_risky_login_is_only_flagged_by_default(member, places, mailer):
    login()
    response = login(ip=FAR_IP)

    assert response.status_code == 200
    assert "access" in response.data
    assert latest().outcome == "flagged"
    assert latest().reasons == [IMPOSSIBLE_TRAVEL]
    mailer.assert_not_called()


def test_risky_login_needs_the_emailed_code(member, enforced, mailer):
    login()
    sessions = UserSession._default_manager.count()

    response = login(ip=FAR_IP)

    assert response.status_code == 401
    assert response.data["code"] == "login_confirmation_required"
    assert "access" not in response.data and "refresh" not in response.data
    assert UserSession._default_manager.count() == sessions
    assert mailer.call_args.kwargs["user_email"] == member.email
    entry = latest()
    assert entry.outcome == "challenged"
    assert sent_code(mailer) not in entry.code_hash

    confirmed = login(ip=FAR_IP, email_code=sent_code(mailer))

    assert confirmed.status_code == 200
    assert "access" in confirmed.data
    assert latest().outcome == "confirmed"


def test_unconfirmed_attempt_does_not_become_normal(member, enforced, mailer):
    login()

    assert login(ip=FAR_IP).status_code == 401
    assert login(ip=FAR_IP).status_code == 401


def test_code_works_only_once(member, enforced, mailer):
    login()
    login(ip=FAR_IP)
    code = sent_code(mailer)
    assert login(ip=FAR_IP, email_code=code).status_code == 200

    # Straight back home is impossible travel again.
    response = login(ip=HOME_IP, email_code=code)

    assert response.status_code == 401
    assert response.data["code"] == "invalid_login_confirmation_code"
    assert latest().outcome == "rejected"


def test_wrong_guesses_use_up_the_code(member, enforced, mailer, settings):
    settings.LOGIN_RISK_MAX_CODE_ATTEMPTS = 2
    login()
    login(ip=FAR_IP)
    code = sent_code(mailer)
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(2):
        assert login(ip=FAR_IP, email_code=wrong).status_code == 401

    assert login(ip=FAR_IP, email_code=code).status_code == 401


def test_expired_code_is_refused(member, enforced, mailer):
    login()
    login(ip=FAR_IP)
    HISTORY.filter(outcome="challenged").update(
        created_at=django_timezone.now() - timedelta(minutes=11)
    )

    response = login(ip=FAR_IP, email_code=sent_code(mailer))

    assert response.status_code == 401


def test_code_is_tied_to_the_device_that_asked(member, enforced, mailer):
    login()
    login(ip=FAR_IP)

    response = login(ip=FAR_IP, user_agent=PHONE, email_code=sent_code(mailer))

    assert response.status_code == 401


def test_emails_are_capped_per_hour(member, enforced, mailer, settings):
    settings.LOGIN_RISK_MAX_CODES_PER_HOUR = 2
    login()
    for _ in range(3):
        assert login(ip=FAR_IP).status_code == 401

    assert mailer.call_count == 2
    # The last code that was sent still works.
    assert login(ip=FAR_IP, email_code=sent_code(mailer)).status_code == 200


def test_new_device_without_lookup_data_is_not_challenged(member, settings, mailer):
    settings.LOGIN_RISK_CONFIRMATION_ENABLED = True
    login()

    response = login(ip=FAR_IP, user_agent=PHONE)

    assert response.status_code == 200
    assert (latest().risk_score, latest().outcome) == (20, "allowed")
    mailer.assert_not_called()


@pytest.mark.parametrize(
    "target",
    [
        "apps.accounts.services.login_risk.LoginRiskAnalyzer.analyze",
        "apps.accounts.services.login_risk.UserLoginHistory.save",
    ],
)
def test_failure_while_scoring_never_blocks_login(member, enforced, target):
    with patch(target, side_effect=RuntimeError("boom")):
        response = login()

    assert response.status_code == 200


def test_mail_queue_failure_lets_the_login_through(member, enforced, mailer):
    login()
    mailer.side_effect = RuntimeError("queue is down")

    response = login(ip=FAR_IP)

    assert response.status_code == 200
    assert latest().outcome == "flagged"


def test_account_without_email_is_not_challenged(member, enforced, mailer):
    User.objects.filter(pk=member.pk).update(email="")
    login()

    assert login(ip=FAR_IP).status_code == 200
    mailer.assert_not_called()


def test_authenticator_users_are_not_asked_for_a_second_code(member, enforced, mailer):
    secret = "JBSWY3DPEHPK3PXP"
    TOTPDevice._default_manager.create(user=member, secret=secret, is_enabled=True)
    login(totp_code=generate_totp_code(secret))

    response = login(ip=FAR_IP, totp_code=generate_totp_code(secret))

    assert response.status_code == 200
    assert latest().outcome == "flagged"
    mailer.assert_not_called()


def test_data_export_includes_history_without_the_code_hash(member, enforced, mailer):
    login()
    login(ip=FAR_IP)

    rows = DataExportService(member).gather_data()["login_history"]

    assert len(rows) == 2
    assert "code_hash" not in rows[0]
    assert rows[0]["risk_score"] == 60


def test_confirmation_email_contains_the_code(mailoutbox):
    from apps.accounts.tasks import send_login_confirmation_email_task

    send_login_confirmation_email_task("risk@example.com", "risk-user", "123456", 10)

    assert mailoutbox[0].to == ["risk@example.com"]
    assert "123456" in mailoutbox[0].body
