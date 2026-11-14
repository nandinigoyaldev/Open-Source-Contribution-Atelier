"""Bounded overlap for verification keys; all secrets and times are synthetic."""

import json
from unittest.mock import Mock, patch

from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from apps.webhooks.middleware import WebhookSignatureMiddleware
from apps.webhooks.security import (
    audit_verification,
    check_signature,
    compute_signature,
)


@override_settings(
    WEBHOOK_SIGNING_KEYS=[
        ("current", "synthetic-new-key"),
        ("previous", "synthetic-old-key"),
    ],
    WEBHOOK_SIGNING_KEY_EXPIRATIONS={"previous": 2000},
    WEBHOOK_ALLOW_LEGACY_SIGNATURES=False,
)
class KeyRotationTests(SimpleTestCase):
    body = b'{"event":"ping"}'

    def verify(self, secret, now, key_id=None, legacy=False):
        timestamp = str(int(now))
        signature = compute_signature(secret, self.body, None if legacy else timestamp)
        return check_signature(
            [("current", "synthetic-new-key"), ("previous", "synthetic-old-key")],
            self.body,
            signature,
            timestamp=timestamp,
            key_id=key_id,
            now=now,
            allow_legacy=legacy,
        )

    def test_both_keys_work_before_deadline(self):
        self.assertEqual(self.verify("synthetic-new-key", 1999).key_id, "current")
        self.assertEqual(self.verify("synthetic-old-key", 1999).key_id, "previous")

    def test_old_key_expires_at_boundary_with_or_without_hint(self):
        for now in (2000, 2001):
            for hint in (None, "previous"):
                with self.subTest(now=now, hint=hint):
                    self.assertFalse(self.verify("synthetic-old-key", now, hint).ok)
                    self.assertTrue(self.verify("synthetic-new-key", now).ok)

    def test_legacy_format_cannot_bypass_expiry(self):
        self.assertTrue(self.verify("synthetic-old-key", 1999, legacy=True).ok)
        self.assertFalse(self.verify("synthetic-old-key", 2000, legacy=True).ok)

    def test_forged_or_wrong_key_id_is_rejected(self):
        self.assertFalse(self.verify("forged-key", 1999).ok)
        self.assertFalse(self.verify("synthetic-old-key", 1999, "current").ok)
        self.assertFalse(self.verify("synthetic-new-key", 1999, "unknown").ok)

    def test_invalid_deadlines_fail_closed_for_affected_key(self):
        for deadline in (None, "2000", True, float("nan"), float("inf")):
            with (
                self.subTest(deadline=deadline),
                override_settings(
                    WEBHOOK_SIGNING_KEY_EXPIRATIONS={"previous": deadline}
                ),
            ):
                self.assertFalse(self.verify("synthetic-old-key", 1999).ok)
                self.assertTrue(self.verify("synthetic-new-key", 1999).ok)

    def test_audit_identifies_actual_key_without_sensitive_material(self):
        result = self.verify("synthetic-old-key", 1999)
        with self.assertLogs("audit", level="INFO") as captured:
            audit_verification(result, source="test")
        entry = json.loads(captured.records[0].getMessage())
        self.assertEqual(entry["event"], "webhook.signature_accepted")
        self.assertEqual(entry["key_id"], "previous")
        self.assertNotIn("synthetic-old-key", captured.output[0])
        self.assertNotIn(self.body.decode(), captured.output[0])
        self.assertNotIn(
            compute_signature("synthetic-old-key", self.body, "1999"),
            captured.output[0],
        )

    def test_middleware_expires_key_without_restarting(self):
        view = Mock(return_value=JsonResponse({"ok": True}))
        middleware = WebhookSignatureMiddleware(view)
        factory = RequestFactory()
        for now, expected in ((1999, 200), (2000, 403)):
            request = factory.post(
                "/api/webhooks/incoming/",
                data=self.body,
                content_type="application/json",
                HTTP_X_WEBHOOK_TIMESTAMP=str(now),
                HTTP_X_WEBHOOK_SIGNATURE_V2=compute_signature(
                    "synthetic-old-key", self.body, str(now)
                ),
            )
            with patch("apps.webhooks.security.time.time", return_value=now):
                self.assertEqual(middleware(request).status_code, expected)
        self.assertEqual(view.call_count, 1)

    @override_settings(WEBHOOK_SIGNING_KEY_EXPIRATIONS={})
    def test_existing_configuration_remains_compatible(self):
        self.assertTrue(self.verify("synthetic-old-key", 3000).ok)
