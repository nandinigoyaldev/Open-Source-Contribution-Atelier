"""
Adversarial tests for webhook signature verification: replay, timestamp
tricks, canonicalization, key rotation and what ends up in the audit log.

The unit tests pass a fixed ``now`` so nothing depends on the wall clock.
"""

import json
import logging
import time
import unicodedata
from typing import Any, Optional

import pytest
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.test import Client, RequestFactory

from apps.webhooks import security
from apps.webhooks.models import WebhookDelivery, WebhookEndpoint
from apps.webhooks.security import (
    build_signature_headers,
    check_signature,
    compute_signature,
    require_webhook_signature,
    serialize_payload,
    verify_signature,
)
from apps.webhooks.tasks import deliver_webhook

SECRET = "s3cret-for-tests"
BODY = b'{"event":"lesson.completed","id":7}'
NOW = 1_800_000_000.0
TS = str(int(NOW))


def sig(
    ts: Optional[str] = TS,
    secret: Any = SECRET,
    body: bytes = BODY,
    prefix: bool = True,
) -> str:
    return ("sha256=" if prefix else "") + compute_signature(secret, body, ts)


def check(
    signature: Optional[str],
    ts: Optional[str] = TS,
    secret: Any = SECRET,
    body: bytes = BODY,
    **kw: Any,
):
    kw.setdefault("now", NOW)
    kw.setdefault("tolerance", 300)
    return check_signature(secret, body, signature, timestamp=ts, **kw)


# --- the happy path -----------------------------------------------------------


def test_fresh_timestamp_bound_signature_is_accepted():
    result = check(sig())
    assert result.ok and not result.legacy
    assert result.reason == "ok"


def test_signature_works_without_the_prefix():
    assert check(sig(prefix=False)).ok


def test_timestamp_is_part_of_the_signed_material():
    assert compute_signature(SECRET, BODY, TS) != compute_signature(SECRET, BODY)
    assert compute_signature(SECRET, BODY, TS) == compute_signature(
        SECRET, BODY, int(TS)
    )


# --- replay and clock skew ----------------------------------------------------


def test_captured_request_replayed_later_is_stale():
    captured = sig()
    later = NOW + 3600
    result = check(captured, now=later)
    assert not result.ok
    assert result.reason == "stale_timestamp"


@pytest.mark.parametrize("age,ok", [(0, True), (299, True), (300, True), (301, False)])
def test_window_edge_in_the_past(age, ok):
    assert check(sig(), now=NOW + age).ok is ok


@pytest.mark.parametrize("ahead,ok", [(299, True), (300, True), (301, False)])
def test_window_edge_in_the_future(ahead, ok):
    ts = str(int(NOW + ahead))
    result = check(sig(ts), ts=ts)
    assert result.ok is ok
    if not ok:
        assert result.reason == "future_timestamp"


def test_tolerance_comes_from_settings(settings):
    settings.WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS = 10
    result = check_signature(SECRET, BODY, sig(), timestamp=TS, now=NOW + 11)
    assert result.reason == "stale_timestamp"
    settings.WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS = 600
    assert check_signature(SECRET, BODY, sig(), timestamp=TS, now=NOW + 599).ok


def test_old_window_setting_name_still_works(settings):
    settings.WEBHOOK_TIMESTAMP_WINDOW_SECONDS = 5
    assert security.get_timestamp_tolerance() == 5


def test_swapping_the_timestamp_breaks_the_signature():
    """Attacker keeps the old signature but sends a fresh timestamp."""
    old_sig = sig(str(int(NOW - 3600)))
    result = check(old_sig, ts=TS)
    assert not result.ok
    assert result.reason == "signature_mismatch"


def test_legacy_signature_with_fresh_timestamp_rejected_when_legacy_is_off():
    legacy = compute_signature(SECRET, BODY)
    result = check(legacy, allow_legacy=False)
    assert not result.ok
    assert result.reason == "legacy_signature_rejected"


def test_legacy_signature_is_accepted_and_flagged_when_allowed():
    result = check(compute_signature(SECRET, BODY), allow_legacy=True)
    assert result.ok and result.legacy


def test_legacy_default_follows_setting(settings):
    legacy = compute_signature(SECRET, BODY)
    settings.WEBHOOK_ALLOW_LEGACY_SIGNATURES = False
    assert not verify_signature(SECRET, BODY, legacy)
    settings.WEBHOOK_ALLOW_LEGACY_SIGNATURES = True
    assert verify_signature(SECRET, BODY, legacy)


def test_stale_timestamp_is_rejected_even_for_a_legacy_signature():
    stale = str(int(NOW - 3600))
    result = check(compute_signature(SECRET, BODY), ts=stale, allow_legacy=True)
    assert result.reason == "stale_timestamp"


def test_missing_timestamp_when_required():
    result = check(sig(), ts=None, require_timestamp=True)
    assert result.reason == "missing_timestamp"
    assert check(sig(), ts="", require_timestamp=True).reason == "missing_timestamp"


@pytest.mark.parametrize(
    "bad",
    [
        "abc",
        "-5",
        "-1800000000",
        "+1800000000",
        "nan",
        "NaN",
        "inf",
        "-inf",
        "Infinity",
        "1e10",
        "1_800_000_000",
        "0x10",
        " 1800000000",
        "1800000000 ",
        "1800000000\n",
        "1800000000.",
        ".5",
        "1800000000.1234567891",
        "9" * 30,
        "1" * 13,
        "１８００００００００",
        "1800000000\x00",
    ],
)
def test_malformed_timestamps_are_rejected(bad):
    result = check(sig(bad), ts=bad)
    assert not result.ok
    assert result.reason == "bad_timestamp"


def test_nan_timestamp_cannot_skip_the_window_check():
    # float("nan") parses and abs(now - nan) > window is False, so a naive
    # float() + comparison lets it through.
    assert not check(compute_signature(SECRET, BODY), ts="nan", allow_legacy=True).ok


def test_zero_and_huge_but_valid_timestamps_are_just_stale_or_future():
    assert check(sig("0"), ts="0").reason == "stale_timestamp"
    big = "9" * 12
    assert check(sig(big), ts=big).reason == "future_timestamp"


def test_fractional_timestamp_is_signed_as_sent():
    ts = f"{NOW}"  # "1800000000.0"
    assert check(sig(ts), ts=ts).ok
    # the receiver must not re-format it: signing "1800000000" does not cover it
    assert not check(sig(TS), ts=ts).ok


# --- tampering and canonicalization -------------------------------------------


def test_tampered_body():
    assert check(sig(), body=BODY.replace(b"7", b"8")).reason == "signature_mismatch"


def test_body_whitespace_changes_break_the_signature():
    pretty = json.dumps(json.loads(BODY), indent=2).encode()
    assert not check(sig(), body=pretty).ok
    assert not check(sig(), body=BODY + b"\n").ok


@pytest.mark.parametrize(
    "variant",
    [
        lambda s: s.upper(),
        lambda s: " " + s,
        lambda s: s + " ",
        lambda s: s + "\n",
        lambda s: s[:-1],
        lambda s: s[:-32],
        lambda s: s + "0",
        lambda s: "sha256=",
        lambda s: "sha256=" + s.removeprefix("sha256=")[:63],
        lambda s: "sha256=" + "g" * 64,
        lambda s: "SHA256=" + s.removeprefix("sha256="),
        lambda s: "sha256=sha256=" + s.removeprefix("sha256="),
        lambda s: "sha1=" + s.removeprefix("sha256="),
        lambda s: "sha256:" + s.removeprefix("sha256="),
        lambda s: s.removeprefix("sha256=") + ",",
        lambda s: s + ", " + s,
        lambda s: s.removeprefix("sha256=")[:62] + "éé",
        lambda s: s.removeprefix("sha256=")[:63] + "١",
        lambda s: s + "\x00",
    ],
)
def test_signature_format_variants_are_rejected_without_crashing(variant):
    # compare_digest raises TypeError on non-ASCII str; none of these may 500.
    result = check(variant(sig()))
    assert not result.ok
    assert result.reason in {"bad_signature_format", "missing_signature"}


def test_missing_signature():
    assert check("").reason == "missing_signature"
    assert check(None).reason == "missing_signature"


def test_unicode_body_roundtrip_and_normalization():
    body = "naïve café – 日本語 🚀".encode("utf-8")
    assert check(sig(body=body), body=body).ok
    nfd = unicodedata.normalize("NFD", "naïve café – 日本語 🚀").encode("utf-8")
    assert nfd != body
    assert not check(sig(body=body), body=nfd).ok


def test_empty_body_is_signed_like_any_other():
    assert check(sig(body=b""), body=b"").ok
    assert not check(sig(body=b""), body=b"x").ok


def test_comparison_goes_through_compare_digest_on_bytes(monkeypatch):
    seen = []
    real = security.hmac.compare_digest

    def spy(a, b):
        seen.append((type(a), type(b)))
        return real(a, b)

    monkeypatch.setattr(security.hmac, "compare_digest", spy)
    check(sig())
    assert seen and all(t == (bytes, bytes) for t in seen)


def test_every_key_is_compared_even_after_a_match(monkeypatch):
    calls = []
    real = security.hmac.compare_digest
    monkeypatch.setattr(
        security.hmac,
        "compare_digest",
        lambda a, b: calls.append(1) or real(a, b),
    )
    keys = [("k1", SECRET), ("k2", "other"), ("k3", "another")]
    assert check(sig(), secret=keys).ok
    assert len(calls) == 2 * len(keys)  # bound + legacy per key


# --- key rotation -------------------------------------------------------------


def test_rotation_accepts_old_and_new_key():
    ring = [("v2", "new-secret"), ("v1", "old-secret")]
    new = check(sig(secret="new-secret"), secret=ring)
    old = check(sig(secret="old-secret"), secret=ring)
    assert new.ok and new.key_id == "v2"
    assert old.ok and old.key_id == "v1"


def test_retired_key_is_rejected_once_removed():
    assert not check(sig(secret="old-secret"), secret=[("v2", "new-secret")]).ok


def test_unknown_key_id_is_rejected():
    ring = [("v2", "new-secret"), ("v1", "old-secret")]
    result = check(sig(secret="new-secret"), secret=ring, key_id="v9")
    assert result.reason == "unknown_key_id"


def test_claimed_key_id_restricts_verification_to_that_key():
    ring = [("v2", "new-secret"), ("v1", "old-secret")]
    # signed with v1's secret but claims v2
    result = check(sig(secret="old-secret"), secret=ring, key_id="v2")
    assert result.reason == "signature_mismatch"
    assert check(sig(secret="old-secret"), secret=ring, key_id="v1").ok


def test_plain_string_keys_have_no_id_to_claim():
    assert check(sig(), key_id="v1").reason == "unknown_key_id"


def test_empty_secrets_are_ignored():
    assert not check(sig(secret=""), secret="").ok
    assert not check(sig(secret=""), secret=[("v1", ""), None, 5]).ok
    assert check(sig(), secret=[("v1", ""), ("v2", SECRET)]).ok


# --- audit log ----------------------------------------------------------------


def _audit_entries(caplog):
    return [json.loads(r.getMessage()) for r in caplog.records if r.name == "audit"]


def test_reject_writes_one_structured_event_without_secrets(caplog):
    caplog.set_level(logging.INFO, logger="audit")
    body = b'{"card":"4111-1111-1111-1111"}'
    stale_ts = str(int(time.time()) - 3600)
    signature = "sha256=" + compute_signature(SECRET, body, stale_ts)
    result = check_signature(SECRET, body, signature, timestamp=stale_ts)
    security.audit_verification(result, source="test")

    (entry,) = _audit_entries(caplog)
    assert entry["event"] == "webhook.signature_rejected"
    assert entry["reason"] == "stale_timestamp"
    assert entry["source"] == "test"
    assert entry["skew_seconds"] > 3000
    raw = caplog.text
    assert SECRET not in raw
    assert signature.removeprefix("sha256=") not in raw
    assert "4111" not in raw


def test_sender_controlled_values_cannot_forge_log_lines(caplog):
    caplog.set_level(logging.INFO, logger="audit")
    evil = 'v1"}\n{"event":"webhook.ok","reason":"forged'
    result = check(sig(), secret=[("v1", SECRET)], key_id=evil)
    security.audit_verification(result, source="test")
    (entry,) = _audit_entries(caplog)  # still exactly one parseable line
    assert "\n" not in caplog.text.strip()
    assert entry["reason"] == "unknown_key_id"
    assert len(entry["key_id"]) <= 64 and '"' not in entry["key_id"]


def test_accepted_requests_are_not_logged_but_legacy_ones_are(caplog):
    caplog.set_level(logging.INFO, logger="audit")
    security.audit_verification(check(sig()), source="test")
    assert _audit_entries(caplog) == []
    security.audit_verification(
        check(compute_signature(SECRET, BODY), allow_legacy=True), source="test"
    )
    (entry,) = _audit_entries(caplog)
    assert entry["event"] == "webhook.legacy_signature_accepted"


# --- outgoing deliveries ------------------------------------------------------


def test_build_signature_headers_verifies_and_keeps_legacy_header(settings):
    settings.WEBHOOK_SEND_LEGACY_SIGNATURE = True
    headers = build_signature_headers(SECRET, BODY, now=NOW)
    assert headers["X-Webhook-Timestamp"] == TS
    assert verify_signature(
        SECRET,
        BODY,
        headers["X-Webhook-Signature-V2"],
        timestamp=headers["X-Webhook-Timestamp"],
        now=NOW,
        allow_legacy=False,
    )
    assert headers["X-Webhook-Signature"] == compute_signature(SECRET, BODY)


def test_legacy_header_can_be_switched_off(settings):
    settings.WEBHOOK_SEND_LEGACY_SIGNATURE = False
    assert "X-Webhook-Signature" not in build_signature_headers(SECRET, BODY)


def test_each_attempt_gets_its_own_timestamp():
    first = build_signature_headers(SECRET, BODY, now=NOW)
    retry = build_signature_headers(SECRET, BODY, now=NOW + 960)
    assert first["X-Webhook-Timestamp"] != retry["X-Webhook-Timestamp"]
    assert first["X-Webhook-Signature-V2"] != retry["X-Webhook-Signature-V2"]


@pytest.mark.django_db
def test_delivery_signs_the_exact_bytes_it_sends(monkeypatch):
    user = get_user_model().objects.create_user(username="hookowner", password="x")
    endpoint = (
        WebhookEndpoint.objects.create(  # pyright: ignore[reportAttributeAccessIssue]
            user=user, target_url="https://example.com/hook", events=["*"]
        )
    )
    delivery = (
        WebhookDelivery.objects.create(  # pyright: ignore[reportAttributeAccessIssue]
            endpoint=endpoint,
            event_type="lesson.completed",
            payload={"name": "Zoë", "n": [1, 2], "nested": {"a": 1}},
        )
    )
    sent = {}

    class FakeResponse:
        status_code = 200
        text = "ok"

    def fake_post(url, **kwargs):
        sent.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("requests.post", fake_post)
    deliver_webhook(delivery.id)

    body = sent["data"]
    assert isinstance(body, bytes) and "json" not in sent
    # compact separators, no space after the colon: this is what is signed
    assert body == b'{"name":"Zo\\u00eb","n":[1,2],"nested":{"a":1}}'
    headers = sent["headers"]
    result = check_signature(
        endpoint.secret,
        body,
        headers["X-Webhook-Signature-V2"],
        timestamp=headers["X-Webhook-Timestamp"],
        allow_legacy=False,
    )
    assert result.ok
    # the old header still verifies against the same bytes
    assert headers["X-Webhook-Signature"] == compute_signature(endpoint.secret, body)
    assert body == serialize_payload(delivery.payload)


# --- decorator ----------------------------------------------------------------


def _view(request):
    return JsonResponse({"status": "ok"})


def _post(headers, body=BODY):
    return RequestFactory().post(
        "/webhook/", data=body, content_type="application/json", **headers
    )


def test_decorator_accepts_fresh_bound_signature():
    ts = str(int(time.time()))
    request = _post(
        {"HTTP_X_SIGNATURE": sig(ts), "HTTP_X_WEBHOOK_TIMESTAMP": ts},
    )
    assert require_webhook_signature(SECRET)(_view)(request).status_code == 200


def test_decorator_rejects_replay_outside_window():
    ts = str(int(time.time()) - 1000)
    request = _post({"HTTP_X_SIGNATURE": sig(ts), "HTTP_X_WEBHOOK_TIMESTAMP": ts})
    response = require_webhook_signature(SECRET)(_view)(request)
    assert response.status_code == 400
    assert "expired" in json.loads(response.content)["error"]


def test_decorator_require_timestamp(settings):
    request = _post({"HTTP_X_SIGNATURE": sig(None)})
    response = require_webhook_signature(SECRET, require_timestamp=True)(_view)(request)
    assert response.status_code == 400


def test_decorator_hides_the_reason_behind_one_message(settings):
    settings.WEBHOOK_ALLOW_LEGACY_SIGNATURES = False
    ts = str(int(time.time()))
    legacy = compute_signature(SECRET, BODY)
    for headers in (
        {"HTTP_X_SIGNATURE": legacy, "HTTP_X_WEBHOOK_TIMESTAMP": ts},  # legacy refused
        {"HTTP_X_SIGNATURE": sig(ts, secret="nope"), "HTTP_X_WEBHOOK_TIMESTAMP": ts},
        {"HTTP_X_SIGNATURE": "zz", "HTTP_X_WEBHOOK_TIMESTAMP": ts},
        {
            "HTTP_X_SIGNATURE": sig(ts),
            "HTTP_X_WEBHOOK_TIMESTAMP": ts,
            "HTTP_X_WEBHOOK_KEY_ID": "nope",
        },
    ):
        response = require_webhook_signature(SECRET)(_view)(_post(headers))
        assert response.status_code == 403
        assert json.loads(response.content) == {"error": "Invalid signature"}


# --- GitHub endpoint and middleware, through the real URL stack ---------------


@pytest.fixture
def keyring(settings):
    settings.GITHUB_WEBHOOK_SECRET = None
    settings.WEBHOOK_SECRET = None
    settings.WEBHOOK_SIGNING_KEYS = [("v2", "new-secret"), ("v1", "old-secret")]
    settings.WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS = 300


@pytest.mark.django_db
class TestGitHubEndpoint:
    url = "/api/webhooks/github/"

    def post(self, headers: dict, body: bytes = BODY) -> Any:
        return Client().post(
            self.url, data=body, content_type="application/json", **headers
        )

    def test_github_style_payload_only_signature_still_works(self, keyring):
        legacy = "sha256=" + compute_signature("old-secret", BODY)
        assert self.post({"HTTP_X_HUB_SIGNATURE_256": legacy}).status_code == 200

    def test_bound_signature_is_accepted_and_replay_is_not(self, keyring):
        ts = str(int(time.time()))
        good = {
            "HTTP_X_WEBHOOK_SIGNATURE_V2": sig(ts, "new-secret"),
            "HTTP_X_WEBHOOK_TIMESTAMP": ts,
        }
        assert self.post(good).status_code == 200
        old = str(int(time.time()) - 900)
        replay = {
            "HTTP_X_WEBHOOK_SIGNATURE_V2": sig(old, "new-secret"),
            "HTTP_X_WEBHOOK_TIMESTAMP": old,
        }
        response = self.post(replay)
        assert response.status_code == 400
        assert response.json()["error"] == "Webhook timestamp expired / out of window"

    @pytest.mark.parametrize("bad", ["nan", "inf", "-1", "1e9", "abc", "9" * 30])
    def test_odd_timestamps_do_not_get_through(self, keyring, bad):
        legacy = "sha256=" + compute_signature("old-secret", BODY)
        response = self.post(
            {"HTTP_X_HUB_SIGNATURE_256": legacy, "HTTP_X_WEBHOOK_TIMESTAMP": bad}
        )
        assert response.status_code == 400

    def test_non_ascii_signature_is_a_clean_403(self, keyring):
        response = self.post({"HTTP_X_HUB_SIGNATURE_256": "sha256=é" * 3})
        assert response.status_code == 403

    def test_the_old_public_default_secret_no_longer_forges(self, settings):
        settings.GITHUB_WEBHOOK_SECRET = None
        settings.WEBHOOK_SECRET = None
        settings.WEBHOOK_SIGNING_KEYS = []
        settings.DEBUG = False
        forged = compute_signature(security.DEV_FALLBACK_SECRET, BODY)
        response = self.post({"HTTP_X_HUB_SIGNATURE_256": forged})
        assert response.status_code == 500


@pytest.mark.django_db
class TestMiddleware:
    # No route lives under /webhook/, so 404 means the middleware let it through.
    url = "/webhook/anything"

    def post(self, headers: dict, body: bytes = BODY) -> Any:
        return Client().post(
            self.url, data=body, content_type="application/json", **headers
        )

    def test_fresh_bound_signature_passes(self, keyring):
        ts = str(int(time.time()))
        response = self.post(
            {"HTTP_X_WEBHOOK_SIGNATURE": sig(ts, "old-secret"), "HTTP_X_TIMESTAMP": ts}
        )
        assert response.status_code == 404

    def test_replay_is_rejected(self, keyring):
        ts = str(int(time.time()) - 1000)
        response = self.post(
            {"HTTP_X_WEBHOOK_SIGNATURE": sig(ts, "old-secret"), "HTTP_X_TIMESTAMP": ts}
        )
        assert response.status_code == 400

    def test_nan_timestamp_is_rejected(self, keyring):
        legacy = compute_signature("old-secret", BODY)
        response = self.post(
            {"HTTP_X_WEBHOOK_SIGNATURE": legacy, "HTTP_X_WEBHOOK_TIMESTAMP": "nan"}
        )
        assert response.status_code == 400

    def test_future_timestamp_is_rejected(self, keyring):
        ts = str(int(time.time()) + 1000)
        response = self.post(
            {"HTTP_X_WEBHOOK_SIGNATURE": sig(ts, "new-secret"), "HTTP_X_TIMESTAMP": ts}
        )
        assert response.status_code == 400

    def test_missing_timestamp_is_rejected(self, keyring):
        response = self.post({"HTTP_X_WEBHOOK_SIGNATURE": sig(None, "new-secret")})
        assert response.status_code == 400

    def test_legacy_signature_with_a_made_up_timestamp(self, keyring, settings):
        """The old behaviour: any captured payload-only signature plus a fresh
        timestamp header was accepted. Closed once legacy is switched off."""
        legacy = compute_signature("old-secret", BODY)
        headers = {
            "HTTP_X_WEBHOOK_SIGNATURE": legacy,
            "HTTP_X_WEBHOOK_TIMESTAMP": str(int(time.time())),
        }
        settings.WEBHOOK_ALLOW_LEGACY_SIGNATURES = False
        assert self.post(headers).status_code == 403
        settings.WEBHOOK_ALLOW_LEGACY_SIGNATURES = True
        assert self.post(headers).status_code == 404

    def test_retired_key_is_rejected(self, keyring, settings):
        settings.WEBHOOK_SIGNING_KEYS = [("v2", "new-secret")]
        ts = str(int(time.time()))
        response = self.post(
            {"HTTP_X_WEBHOOK_SIGNATURE": sig(ts, "old-secret"), "HTTP_X_TIMESTAMP": ts}
        )
        assert response.status_code == 403

    def test_unknown_key_id_is_rejected(self, keyring):
        ts = str(int(time.time()))
        response = self.post(
            {
                "HTTP_X_WEBHOOK_SIGNATURE": sig(ts, "new-secret"),
                "HTTP_X_TIMESTAMP": ts,
                "HTTP_X_WEBHOOK_KEY_ID": "v0",
            }
        )
        assert response.status_code == 403

    def test_no_configured_key_fails_closed(self, settings):
        settings.WEBHOOK_SIGNING_KEYS = []
        settings.DEBUG = False
        ts = str(int(time.time()))
        forged = sig(ts, security.DEV_FALLBACK_SECRET)
        response = self.post(
            {"HTTP_X_WEBHOOK_SIGNATURE": forged, "HTTP_X_TIMESTAMP": ts}
        )
        assert response.status_code == 500
