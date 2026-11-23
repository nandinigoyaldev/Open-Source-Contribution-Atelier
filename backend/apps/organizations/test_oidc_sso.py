# pyright: reportAttributeAccessIssue=false, reportIndexIssue=false, reportOperatorIssue=false, reportArgumentType=false, reportReturnType=false, reportGeneralTypeIssues=false, reportOptionalMemberAccess=false, reportCallIssue=false
"""
Integration tests for organization OIDC single sign-on.

The identity provider is a fake: ``FakeIdP`` signs real ID tokens with a real RSA
key and answers discovery, JWKS and token requests through ``oidc_client._send``,
so nothing touches the network. Its token endpoint checks the PKCE verifier and
the client authentication the same way a real provider would.
"""

import base64
import hashlib
import json
import logging
import time
from unittest import mock
from urllib.parse import parse_qs, quote, urlsplit

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import override_settings
from rest_framework import serializers
from rest_framework.test import APIClient, APITestCase

from apps.accounts.throttles import OAuthThrottle
from apps.audit.models import AuditEvent

from . import oidc_client
from .models import (
    Organization,
    OrganizationAuditLog,
    OrganizationMembership,
    OrganizationOIDCProvider,
    OrganizationSSODomain,
    OrganizationSSOIdentity,
)
from .sso_views import safe_next_path

User = get_user_model()

ISSUER = "https://idp.acme.test/realm"
CLIENT_ID = "atelier-acme"
CLIENT_SECRET = "s3cr3t-client-value-DO-NOT-LEAK"
CALLBACK = "/api/auth/sso/oidc/callback/"
START = "/api/auth/sso/oidc/start/"


def _b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _jwk(public_key, kid):
    numbers = public_key.public_numbers()
    return {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": kid,
        "n": _b64u(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")),
        "e": _b64u(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")),
    }


class FakeIdP:
    def __init__(self, issuer=ISSUER):
        self.issuer = issuer
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.kid = "k1"
        self.published_keys = {self.kid: self.key}
        self.requests = []
        self.discovery_issuer = issuer
        self.token_status = 200
        # filled in per login by ``expect``
        self.code = "auth-code-1"
        self.nonce = None
        self.challenge = None
        self.redirect_uri = None
        self.claims = {}
        self.token_overrides = {}
        self.sign_with = None
        self.sign_alg = "RS256"
        self.sign_kid = None

    # -------------------------------------------------------------- network
    def send(self, method, url, **kwargs):
        self.requests.append((method, url, kwargs))
        base = self.issuer
        if url == base + "/.well-known/openid-configuration":
            return (
                200,
                json.dumps(
                    {
                        "issuer": self.discovery_issuer,
                        "authorization_endpoint": base + "/auth",
                        "token_endpoint": base + "/token",
                        "jwks_uri": base + "/certs",
                    }
                ).encode(),
            )
        if url == base + "/certs":
            keys = [_jwk(k.public_key(), kid) for kid, k in self.published_keys.items()]
            return 200, json.dumps({"keys": keys}).encode()
        if url == base + "/token":
            return self._token(kwargs)
        return 404, b"{}"

    def _token(self, kwargs):
        if self.token_status != 200:
            return self.token_status, b"{}"
        data = kwargs["data"]
        headers = kwargs.get("headers", {})
        assert data["grant_type"] == "authorization_code"
        assert data["code"] == self.code, "wrong authorization code"
        assert data["redirect_uri"] == self.redirect_uri
        digest = hashlib.sha256(data["code_verifier"].encode()).digest()
        assert _b64u(digest) == self.challenge, "PKCE verifier mismatch"
        if CLIENT_SECRET:
            basic = headers["Authorization"].split(" ", 1)[1]
            assert base64.b64decode(basic).decode() == f"{CLIENT_ID}:{CLIENT_SECRET}"
            assert "client_secret" not in data
        return 200, json.dumps({"id_token": self.mint(), "access_token": "x"}).encode()

    # ---------------------------------------------------------------- tokens
    def mint(self):
        now = int(time.time())
        claims = {
            "iss": self.issuer,
            "sub": "sub-123",
            "aud": CLIENT_ID,
            "iat": now,
            "exp": now + 300,
            "nonce": self.nonce,
            "email": "ada@acme.test",
            "email_verified": True,
            **self.claims,
        }
        for key, value in self.token_overrides.items():
            if value is None:
                claims.pop(key, None)
            else:
                claims[key] = value
        key = self.sign_with or self.key
        return jwt.encode(
            claims,
            key,
            algorithm=self.sign_alg,
            headers={"kid": self.sign_kid or self.kid},
        )


def field_errors(response):
    """Validation errors, whether or not the project's error envelope wraps them."""
    data = response.data
    return data.get("errors", data) if hasattr(data, "get") else data


@override_settings(DISABLE_RATE_LIMITING=True)
class SSOTestCase(APITestCase):
    def setUp(self):
        cache.clear()
        self.idp = FakeIdP()
        patches = [
            mock.patch.object(oidc_client, "_send", side_effect=self.idp.send),
            mock.patch.object(
                oidc_client, "_resolve_host", return_value=["93.184.216.34"]
            ),
        ]
        # The DRF throttle has its own test (SSOThrottleTests); the others do many logins.
        patches.append(
            mock.patch.object(OAuthThrottle, "allow_request", return_value=True)
        )
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

        self.org = Organization.objects.create(name="Acme")
        self.owner = User.objects.create_user(
            "acme-owner", "owner@acme.test", "pw12345678"
        )
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.owner,
            role=OrganizationMembership.ROLE_OWNER,
        )
        self.provider = OrganizationOIDCProvider.objects.create(
            organization=self.org,
            issuer=ISSUER,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            is_enabled=True,
        )
        OrganizationSSODomain.objects.create(provider=self.provider, domain="acme.test")

    # ------------------------------------------------------------- helpers
    def begin(self, client, query=None):
        """Hit /start/ and return the parsed authorization request."""
        response = client.get(START, {"organization": self.org.id, **(query or {})})
        self.assertEqual(response.status_code, 302, response.content)
        location = response["Location"]
        self.assertTrue(location.startswith(ISSUER + "/auth?"), location)
        params = {k: v[0] for k, v in parse_qs(urlsplit(location).query).items()}
        self.idp.nonce = params["nonce"]
        self.idp.challenge = params["code_challenge"]
        self.idp.redirect_uri = params["redirect_uri"]
        return params

    def callback(self, client, params, **extra):
        query = {"code": self.idp.code, "state": params["state"], **extra}
        query = {k: v for k, v in query.items() if v is not None}
        return client.get(CALLBACK, query)

    def sso_login(self, client=None, **extra):
        client = client or APIClient()
        params = self.begin(client)
        return client, self.callback(client, params, **extra)

    def assert_error(self, response, code):
        self.assertEqual(response.status_code, 302)
        parts = urlsplit(response["Location"])
        self.assertEqual(parts.path, "/login", response["Location"])
        self.assertEqual(parse_qs(parts.query), {"sso_error": [code]})

    def assert_no_login(self):
        keys = [k for k in cache._cache.keys() if "org-sso-login" in str(k)]
        self.assertEqual(keys, [])

    def exchange(self, response):
        query = parse_qs(urlsplit(response["Location"]).query)
        self.assertIn("code", query, response["Location"])
        return APIClient().post(
            "/api/auth/sso/exchange/", {"code": query["code"][0]}, format="json"
        )


# --------------------------------------------------------------- admin config


class SSOConfigTests(SSOTestCase):
    def setUp(self):
        super().setUp()
        self.url = f"/api/organizations/{self.org.id}/sso/"
        self.other_org = Organization.objects.create(name="Other")
        self.other_owner = User.objects.create_user("oo", "oo@other.test", "pw12345678")
        OrganizationMembership.objects.create(
            organization=self.other_org,
            user=self.other_owner,
            role=OrganizationMembership.ROLE_OWNER,
        )
        self.other_url = f"/api/organizations/{self.other_org.id}/sso/"

    def test_owner_creates_provider_and_secret_is_never_returned(self):
        self.client.force_authenticate(self.other_owner)
        response = self.client.put(
            self.other_url,
            {
                "issuer": "https://login.other.test",
                "client_id": "other",
                "client_secret": "topsecret-value-123",
                "domains": ["Other.test", "@mail.other.test"],
                "is_enabled": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertNotIn("client_secret", response.data)
        self.assertNotIn("topsecret", json.dumps(response.data))
        self.assertTrue(response.data["has_client_secret"])
        self.assertEqual(response.data["domains"], ["mail.other.test", "other.test"])

        again = self.client.get(self.other_url)
        self.assertNotIn("topsecret", json.dumps(again.data))

    def test_secret_does_not_reach_application_logs(self):
        self.client.force_authenticate(self.other_owner)
        with self.assertLogs(level="DEBUG") as logs:
            logging.getLogger("probe").debug("probe")
            self.client.put(
                self.other_url,
                {
                    "issuer": "https://login.other.test",
                    "client_id": "other",
                    "client_secret": "topsecret-value-123",
                    "domains": ["other.test"],
                },
                format="json",
            )
        self.assertFalse([line for line in logs.output if "topsecret" in line])

    def test_secret_is_encrypted_at_rest(self):
        provider = OrganizationOIDCProvider.objects.get(pk=self.provider.pk)
        self.assertEqual(provider.client_secret, CLIENT_SECRET)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT client_secret FROM organizations_organizationoidcprovider WHERE id=%s",
                [self.provider.pk],
            )
            raw = cursor.fetchone()[0]
        self.assertTrue(raw.startswith("enc:"))
        self.assertNotIn(CLIENT_SECRET, raw)

    def test_patch_without_secret_keeps_it_and_audit_log_has_no_secret(self):
        self.client.force_authenticate(self.owner)
        response = self.client.patch(self.url, {"auto_provision": False}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.provider.refresh_from_db()
        self.assertEqual(self.provider.client_secret, CLIENT_SECRET)
        self.assertFalse(self.provider.auto_provision)
        log = OrganizationAuditLog.objects.filter(organization_id=self.org.id).latest(
            "id"
        )
        self.assertNotIn(CLIENT_SECRET, json.dumps(log.changes))
        self.assertEqual(log.changes["sso"]["fields"], ["auto_provision"])

    def test_client_secret_is_stored_exactly_as_submitted(self):
        self.client.force_authenticate(self.owner)
        response = self.client.patch(
            self.url, {"client_secret": "  pad+secret \t"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.provider.refresh_from_db()
        self.assertEqual(self.provider.client_secret, "  pad+secret \t")
        # "" is still the explicit clear, and leaving it out keeps the value
        self.client.patch(self.url, {"auto_provision": True}, format="json")
        self.provider.refresh_from_db()
        self.assertEqual(self.provider.client_secret, "  pad+secret \t")
        self.client.patch(self.url, {"client_secret": ""}, format="json")
        self.provider.refresh_from_db()
        self.assertEqual(self.provider.client_secret, "")

    def test_enabled_without_domains_is_rechecked_under_the_row_lock(self):
        from .sso_serializers import OIDCProviderSerializer

        self.provider.is_enabled = False
        self.provider.save()
        serializer = OIDCProviderSerializer(
            self.provider, data={"is_enabled": True}, partial=True
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        # a concurrent request removes every domain after validate() but before save()
        self.provider.domains.all().delete()
        with mock.patch(
            "django.db.models.query.QuerySet.select_for_update",
            autospec=True,
            side_effect=lambda qs, *a, **kw: qs,
        ) as lock:
            with self.assertRaises(serializers.ValidationError) as ctx:
                serializer.save(organization=self.org)
        lock.assert_called()
        self.assertIn("domains", ctx.exception.detail)
        self.provider.refresh_from_db()
        self.assertFalse(self.provider.is_enabled)

    def test_member_is_forbidden_outsider_and_anonymous_are_refused(self):
        member = User.objects.create_user("m", "m@acme.test", "pw12345678")
        OrganizationMembership.objects.create(organization=self.org, user=member)
        self.client.force_authenticate(member)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.put(self.url, {}, format="json").status_code, 403)
        self.client.force_authenticate(self.other_owner)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_bad_issuers_are_rejected(self):
        self.client.force_authenticate(self.other_owner)
        for issuer in (
            "http://login.other.test",
            "https://127.0.0.1",
            "https://169.254.169.254",
            "https://10.0.0.5/realm",
            "https://localhost",
            "https://user:pw@login.other.test",
            "https://login.other.test/?x=1",
            "ftp://login.other.test",
        ):
            response = self.client.put(
                self.other_url,
                {"issuer": issuer, "client_id": "c", "domains": ["other.test"]},
                format="json",
            )
            self.assertEqual(response.status_code, 400, issuer)
            self.assertIn("issuer", field_errors(response), issuer)

    def test_domain_rules(self):
        self.client.force_authenticate(self.other_owner)
        base = {"issuer": "https://login.other.test", "client_id": "c"}
        for domains in (["gmail.com"], ["acme.test"], ["not a domain"], ["localhost"]):
            response = self.client.put(
                self.other_url, {**base, "domains": domains}, format="json"
            )
            self.assertEqual(response.status_code, 400, domains)
            self.assertIn("domains", field_errors(response))
        self.assertFalse(
            OrganizationOIDCProvider.objects.filter(
                organization=self.other_org
            ).exists()
        )

    def test_cannot_enable_without_domains(self):
        self.client.force_authenticate(self.other_owner)
        response = self.client.put(
            self.other_url,
            {
                "issuer": "https://login.other.test",
                "client_id": "c",
                "is_enabled": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_delete_removes_provider(self):
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.delete(self.url).status_code, 204)
        self.assertFalse(
            OrganizationOIDCProvider.objects.filter(organization=self.org).exists()
        )
        self.assertEqual(self.client.get(self.url).status_code, 404)


# -------------------------------------------------------------- domain routing


class SSODiscoveryTests(SSOTestCase):
    url = "/api/auth/sso/discover/"

    def test_routes_by_email_domain_case_insensitively(self):
        response = self.client.post(
            self.url, {"email": "Someone@ACME.test"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["sso_enabled"])
        self.assertEqual(response.data["organization_id"], self.org.id)
        self.assertIn(f"organization={self.org.id}", response.data["start_url"])

    def test_unknown_domain_and_lookalike_are_not_routed(self):
        for email in ("x@other.test", "x@acme.test.evil.test", "x@sub.acme.test"):
            response = self.client.post(self.url, {"email": email}, format="json")
            self.assertEqual(response.data, {"sso_enabled": False}, email)

    def test_disabled_provider_is_not_routed(self):
        self.provider.is_enabled = False
        self.provider.save()
        response = self.client.post(self.url, {"email": "x@acme.test"}, format="json")
        self.assertEqual(response.data, {"sso_enabled": False})

    def test_invalid_email_is_400(self):
        self.assertEqual(
            self.client.post(self.url, {"email": "nope"}, format="json").status_code,
            400,
        )
        self.assertEqual(self.client.post(self.url, {}, format="json").status_code, 400)

    def test_non_string_email_is_400_not_a_server_error(self):
        for value in (123, ["a@acme.test"], {"a": 1}, True, None):
            response = self.client.post(self.url, {"email": value}, format="json")
            self.assertEqual(response.status_code, 400, value)

    def test_start_with_an_organization_selector_that_is_not_a_plain_id(self):
        for value in ("\u00b2", "\u0663", "9" * 40, "1.5", "-1"):
            response = self.client.get(START, {"organization": value})
            self.assert_error(response, "sso_not_available")

    def test_start_by_email_routes_to_the_organization_provider(self):
        response = self.client.get(START, {"email": "ada@acme.test"})
        self.assertEqual(response.status_code, 302)
        params = parse_qs(urlsplit(response["Location"]).query)
        self.assertEqual(params["login_hint"], ["ada@acme.test"])

    def test_start_for_unknown_org_or_email_redirects_with_error(self):
        self.assert_error(
            self.client.get(START, {"organization": 99999}), "sso_not_available"
        )
        self.assert_error(
            self.client.get(START, {"email": "x@nowhere.test"}), "sso_not_available"
        )
        self.assert_error(self.client.get(START), "sso_not_available")


# ----------------------------------------------------------------- happy path


class SSOLoginFlowTests(SSOTestCase):
    def test_authorization_request_has_state_nonce_and_pkce(self):
        params = self.begin(self.client)
        self.assertEqual(params["response_type"], "code")
        self.assertEqual(params["client_id"], CLIENT_ID)
        self.assertIn("openid", params["scope"].split())
        self.assertEqual(params["code_challenge_method"], "S256")
        self.assertTrue(params["redirect_uri"].endswith(CALLBACK))
        self.assertGreaterEqual(len(params["state"]), 32)
        self.assertGreaterEqual(len(params["nonce"]), 32)
        self.assertNotEqual(params["state"], params["nonce"])
        # the verifier is not in the URL
        self.assertNotIn("code_verifier", params)

    def test_new_user_is_provisioned_and_gets_tokens(self):
        with self.assertLogs("apps.organizations", level="DEBUG") as logs:
            logging.getLogger("apps.organizations").debug("start")
            client, response = self.sso_login()
        self.assertEqual(response.status_code, 302, response.content)
        parts = urlsplit(response["Location"])
        self.assertEqual(parts.path, "/auth/sso/callback")
        tokens = self.exchange(response)
        self.assertEqual(tokens.status_code, 200)
        self.assertIn("access", tokens.data)
        self.assertIn("refresh", tokens.data)

        user = User.objects.get(email="ada@acme.test")
        self.assertFalse(user.has_usable_password())
        self.assertTrue(
            OrganizationMembership.objects.filter(
                organization=self.org, user=user, role="member"
            ).exists()
        )
        identity = OrganizationSSOIdentity.objects.get(user=user)
        self.assertEqual((identity.issuer, identity.subject), (ISSUER, "sub-123"))
        self.assertEqual(user.user_profile.organization_id, self.org.id)
        for line in logs.output:
            self.assertNotIn(CLIENT_SECRET, line)
        self.assertTrue(
            AuditEvent.objects.filter(extra__operation="sso.login_succeeded").exists()
        )

    def test_login_code_works_once(self):
        _, response = self.sso_login()
        code = parse_qs(urlsplit(response["Location"]).query)["code"][0]
        client = APIClient()
        first = client.post("/api/auth/sso/exchange/", {"code": code}, format="json")
        second = client.post("/api/auth/sso/exchange/", {"code": code}, format="json")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 400)
        self.assertEqual(
            client.post(
                "/api/auth/sso/exchange/", {"code": "nope"}, format="json"
            ).status_code,
            400,
        )

    def test_returning_user_matched_by_subject(self):
        self.sso_login()
        before = User.objects.count()
        _, response = self.sso_login()
        self.assertEqual(urlsplit(response["Location"]).path, "/auth/sso/callback")
        self.assertEqual(User.objects.count(), before)
        self.assertEqual(OrganizationSSOIdentity.objects.count(), 1)

    def test_client_secret_never_appears_in_any_redirect(self):
        client = APIClient()
        params = self.begin(client)
        response = self.callback(client, params)
        self.assertNotIn(CLIENT_SECRET, response["Location"])
        self.assertNotIn(CLIENT_SECRET, params["state"])

    def test_public_client_without_secret_sends_client_id_in_body(self):
        self.provider.client_secret = ""
        self.provider.save()
        sent = {}

        def send(method, url, **kwargs):
            if url.endswith("/token"):
                sent.update(kwargs)
                data = kwargs["data"]
                self.idp.requests.append((method, url, kwargs))
                self.assertEqual(data["client_id"], CLIENT_ID)
                self.assertNotIn("Authorization", kwargs["headers"])
                return 200, json.dumps({"id_token": self.idp.mint()}).encode()
            return self.idp.send(method, url, **kwargs)

        with mock.patch.object(oidc_client, "_send", side_effect=send):
            _, response = self.sso_login()
        self.assertEqual(urlsplit(response["Location"]).path, "/auth/sso/callback")
        self.assertTrue(sent)

    def test_next_path_is_carried_only_when_safe(self):
        client = APIClient()
        params = self.begin(client, {"next": "/dashboard?tab=1"})
        response = self.callback(client, params)
        self.assertEqual(
            parse_qs(urlsplit(response["Location"]).query)["next"], ["/dashboard?tab=1"]
        )

        for evil in (
            "//evil.test",
            "https://evil.test/x",
            "/\\evil.test",
            "javascript:alert(1)",
            "evil",
        ):
            self.assertEqual(safe_next_path(evil), "/", evil)
        client = APIClient()
        params = self.begin(client, {"next": "//evil.test"})
        response = self.callback(client, params)
        location = urlsplit(response["Location"])
        self.assertNotIn("next", parse_qs(location.query))
        self.assertEqual(location.netloc, urlsplit("http://localhost:5173").netloc)


# --------------------------------------------------------------- state / nonce


class SSOStateTests(SSOTestCase):
    def test_missing_or_unknown_state(self):
        self.begin(self.client)
        self.assert_error(self.client.get(CALLBACK, {"code": "x"}), "invalid_state")
        self.assert_error(
            self.client.get(CALLBACK, {"code": "x", "state": "bogus"}), "invalid_state"
        )
        self.assert_no_login()

    def test_state_can_not_be_replayed(self):
        client = APIClient()
        params = self.begin(client)
        first = self.callback(client, params)
        self.assertEqual(urlsplit(first["Location"]).path, "/auth/sso/callback")
        self.assert_error(self.callback(client, params), "invalid_state")

    def test_state_from_another_browser_is_refused(self):
        # login CSRF: attacker starts a flow, victim's browser finishes it
        attacker = APIClient()
        params = self.begin(attacker)
        victim = APIClient()
        self.assert_error(self.callback(victim, params), "invalid_state")
        self.assertFalse(User.objects.filter(email="ada@acme.test").exists())

    def test_expired_state(self):
        client = APIClient()
        params = self.begin(client)
        with mock.patch(
            "apps.organizations.sso_views.time.time", return_value=time.time() + 700
        ):
            self.assert_error(self.callback(client, params), "invalid_state")

    def test_nonce_mismatch(self):
        client = APIClient()
        params = self.begin(client)
        self.idp.nonce = "a-different-nonce"
        self.assert_error(self.callback(client, params), "nonce_mismatch")
        self.assertFalse(User.objects.filter(email="ada@acme.test").exists())

    def test_missing_nonce_claim(self):
        self.idp.token_overrides = {"nonce": None}
        _, response = self.sso_login()
        self.assert_error(response, "nonce_mismatch")

    def test_provider_error_param_is_not_echoed(self):
        client = APIClient()
        params = self.begin(client)
        response = self.callback(
            client,
            params,
            error="access_denied",
            error_description="<script>boom</script>",
            code=None,
        )
        self.assert_error(response, "provider_denied")
        self.assertNotIn("boom", response["Location"])

    def test_state_is_claimed_before_the_provider_is_called(self):
        # Two overlapping callbacks can both read the attempt from the session. The
        # cache marker is what only one of them gets, and it is taken before any
        # call to the provider.
        client = APIClient()
        params = self.begin(client)
        cache.delete(f"org-sso-state:{params['state']}")  # the other callback won
        self.idp.requests.clear()
        self.assert_error(self.callback(client, params), "invalid_state")
        self.assertEqual(self.idp.requests, [])

    def test_failure_to_store_the_login_code_is_a_clean_error(self):
        client = APIClient()
        params = self.begin(client)
        real_set = cache.set

        def broken_set(key, *args, **kwargs):
            if str(key).startswith("org-sso-login:"):
                raise ConnectionError("cache down")
            return real_set(key, *args, **kwargs)

        with mock.patch.object(cache, "set", side_effect=broken_set):
            response = self.callback(client, params)
        self.assert_error(response, "sso_failed")
        self.assert_no_login()
        # the first login still created the account, but nothing says it succeeded
        self.assertTrue(User.objects.filter(email="ada@acme.test").exists())
        self.assertFalse(
            AuditEvent.objects.filter(extra__operation="sso.login_succeeded").exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(extra__operation="sso.login_failed").exists()
        )
        # trying again reuses that account
        _, retry = self.sso_login()
        self.assertEqual(urlsplit(retry["Location"]).path, "/auth/sso/callback")
        self.assertEqual(User.objects.filter(email="ada@acme.test").count(), 1)

    def test_missing_code(self):
        client = APIClient()
        params = self.begin(client)
        self.assert_error(self.callback(client, params, code=None), "invalid_request")


# ----------------------------------------------------------- id token checks


class SSOIdTokenTests(SSOTestCase):
    def failing_login(self, code, **idp_changes):
        for key, value in idp_changes.items():
            setattr(self.idp, key, value)
        _, response = self.sso_login()
        self.assert_error(response, code)
        self.assertFalse(User.objects.filter(email="ada@acme.test").exists())
        self.assertEqual(OrganizationSSOIdentity.objects.count(), 0)
        self.assert_no_login()

    def test_wrong_audience(self):
        self.failing_login("id_token_invalid", token_overrides={"aud": "someone-else"})

    def test_audience_list_requires_matching_azp(self):
        self.failing_login(
            "id_token_invalid",
            token_overrides={"aud": [CLIENT_ID, "other"], "azp": "other"},
        )

    def test_audience_list_with_an_untrusted_extra_audience_is_refused(self):
        # OIDC Core 3.1.3.7 step 3. There is no setting for trusted extra audiences,
        # so even a matching azp does not make "other" acceptable.
        self.failing_login(
            "id_token_invalid",
            token_overrides={"aud": [CLIENT_ID, "other"], "azp": CLIENT_ID},
        )

    def test_audience_list_with_only_our_client_id_is_fine(self):
        self.idp.token_overrides = {"aud": [CLIENT_ID], "azp": CLIENT_ID}
        _, response = self.sso_login()
        self.assertEqual(urlsplit(response["Location"]).path, "/auth/sso/callback")

    def test_non_string_alg_in_the_header_is_a_clean_error(self):
        for alg in (["RS256"], 5, {"a": 1}, None):
            header = _b64u(json.dumps({"alg": alg, "typ": "JWT"}).encode())
            token = f"{header}.{_b64u(b'{}')}.{_b64u(b'sig')}"
            client = APIClient()
            params = self.begin(client)
            with mock.patch.object(self.idp, "mint", return_value=token):
                response = self.callback(client, params)
            self.assert_error(response, "id_token_invalid")

    def test_wrong_issuer(self):
        self.failing_login(
            "id_token_invalid", token_overrides={"iss": "https://evil.test"}
        )

    def test_expired_token(self):
        self.failing_login(
            "id_token_invalid", token_overrides={"exp": int(time.time()) - 3600}
        )

    def test_token_issued_in_the_future(self):
        now = int(time.time())
        self.failing_login(
            "id_token_invalid", token_overrides={"iat": now + 3600, "exp": now + 7200}
        )

    def test_missing_required_claims(self):
        for claim in ("exp", "iat", "sub", "aud", "iss"):
            self.idp.token_overrides = {claim: None}
            _, response = self.sso_login()
            self.assert_error(response, "id_token_invalid")

    def test_signature_from_unknown_key(self):
        other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.failing_login("id_token_invalid", sign_with=other)

    def test_unknown_kid(self):
        self.failing_login("id_token_invalid", sign_kid="nope")

    def test_hs256_with_public_key_is_refused(self):
        # classic algorithm confusion: HMAC signed with the published key
        self.idp.sign_alg = "HS256"
        self.idp.sign_with = "shared-secret-shared-secret-1234"
        self.failing_login("id_token_invalid")

    def test_unsigned_token_is_refused(self):
        client = APIClient()
        params = self.begin(client)
        now = int(time.time())
        unsigned = jwt.encode(
            {
                "iss": ISSUER,
                "sub": "s",
                "aud": CLIENT_ID,
                "iat": now,
                "exp": now + 60,
                "nonce": params["nonce"],
                "email": "ada@acme.test",
                "email_verified": True,
            },
            key=None,
            algorithm="none",
        )
        with mock.patch.object(self.idp, "mint", return_value=unsigned):
            response = self.callback(client, params)
        self.assert_error(response, "id_token_invalid")

    def test_key_rotation_refreshes_jwks_once(self):
        self.sso_login()  # warms the JWKS cache with k1
        new_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.idp.published_keys = {"k2": new_key}
        self.idp.kid = "k2"
        self.idp.key = new_key
        OrganizationSSOIdentity.objects.all().delete()
        User.objects.filter(email="ada@acme.test").delete()
        _, response = self.sso_login()
        self.assertEqual(urlsplit(response["Location"]).path, "/auth/sso/callback")

    def test_forged_kid_does_not_refetch_jwks_repeatedly(self):
        self.sso_login()
        fetches = lambda: len([r for r in self.idp.requests if r[1].endswith("/certs")])
        start = fetches()
        for _ in range(3):
            self.idp.sign_kid = "forged"
            self.sso_login()
        self.assertLessEqual(fetches() - start, 1)

    def test_discovery_issuer_mismatch(self):
        self.idp.discovery_issuer = "https://evil.test"
        response = self.client.get(START, {"organization": self.org.id})
        self.assert_error(response, "provider_misconfigured")

    def test_token_endpoint_failure(self):
        self.failing_login("token_exchange_failed", token_status=500)

    def test_provider_unreachable_on_start(self):
        with mock.patch.object(
            oidc_client,
            "_send",
            side_effect=oidc_client.OIDCError("provider_unavailable", "x"),
        ):
            response = self.client.get(START, {"organization": self.org.id})
        self.assert_error(response, "provider_unavailable")

    def test_unexpected_exception_is_a_generic_error(self):
        client = APIClient()
        params = self.begin(client)
        with mock.patch(
            "apps.organizations.sso_views.oidc_client.exchange_code",
            side_effect=RuntimeError("secret detail"),
        ):
            response = self.callback(client, params)
        self.assert_error(response, "sso_failed")
        self.assertNotIn("secret", response["Location"])

    def test_failures_are_audited_without_tokens(self):
        self.failing_login("id_token_invalid", token_overrides={"aud": "x"})
        event = AuditEvent.objects.filter(extra__operation="sso.login_failed").latest(
            "id"
        )
        self.assertEqual(event.extra["payload"]["code"], "id_token_invalid")


# ------------------------------------------------------------------ ssrf guard


class OIDCClientSafetyTests(SSOTestCase):
    def test_hosts_resolving_to_private_addresses_are_refused(self):
        for addr in ("127.0.0.1", "10.1.2.3", "169.254.169.254", "192.168.0.1", "::1"):
            with mock.patch.object(oidc_client, "_resolve_host", return_value=[addr]):
                with self.assertRaises(oidc_client.OIDCError, msg=addr) as ctx:
                    oidc_client.assert_public_url("https://idp.acme.test/x")
            self.assertEqual(ctx.exception.code, "provider_misconfigured")

    def test_one_private_answer_among_public_ones_is_refused(self):
        with mock.patch.object(
            oidc_client, "_resolve_host", return_value=["93.184.216.34", "10.0.0.1"]
        ):
            with self.assertRaises(oidc_client.OIDCError):
                oidc_client.assert_public_url("https://idp.acme.test/x")

    def test_plain_http_and_literal_private_ips_are_refused(self):
        for url in (
            "http://idp.acme.test",
            "https://127.0.0.1/",
            "https://[::1]/",
            "https://localhost/",
        ):
            with self.assertRaises(oidc_client.OIDCError, msg=url):
                oidc_client.assert_public_url(url)

    def test_discovered_endpoints_must_be_https(self):
        original = self.idp.send

        def send(method, url, **kw):
            status, body = original(method, url, **kw)
            if url.endswith("openid-configuration"):
                doc = json.loads(body)
                doc["token_endpoint"] = "http://idp.acme.test/token"
                body = json.dumps(doc).encode()
            return status, body

        with mock.patch.object(oidc_client, "_send", side_effect=send):
            response = self.client.get(START, {"organization": self.org.id})
        self.assert_error(response, "provider_misconfigured")

    def test_local_providers_allowed_only_with_the_dev_setting(self):
        with self.settings(OIDC_SSO_ALLOW_LOCAL_PROVIDERS=True):
            oidc_client.assert_public_url("http://localhost:8080/realms/dev")

    def test_connection_is_pinned_to_the_checked_address(self):
        sock = mock.Mock()
        conn = oidc_client._PinnedHTTPSConnection("idp.acme.test", 443)
        with mock.patch(
            "urllib3.util.connection.create_connection", return_value=sock
        ) as create:
            self.assertIs(conn._new_conn(), sock)
        self.assertEqual(create.call_args.args[0], ("93.184.216.34", 443))
        # only the socket is pinned: SNI and certificate checks keep the hostname
        self.assertEqual(conn.host, "idp.acme.test")
        self.assertEqual(conn._dns_host, "idp.acme.test")

    def test_connection_time_lookup_that_turns_private_is_refused(self):
        # DNS rebinding: public for the pre-check, internal when the socket opens
        conn = oidc_client._PinnedHTTPSConnection("idp.acme.test", 443)
        with (
            mock.patch.object(
                oidc_client, "_resolve_host", return_value=["169.254.169.254"]
            ),
            mock.patch("urllib3.util.connection.create_connection") as create,
        ):
            with self.assertRaises(oidc_client.OIDCError) as ctx:
                conn._new_conn()
        self.assertEqual(ctx.exception.code, "provider_misconfigured")
        create.assert_not_called()

    def test_https_requests_use_the_pinned_connection_class(self):
        adapter = oidc_client._PinnedAdapter()
        pool = adapter.poolmanager.connection_from_url("https://idp.acme.test/x")
        self.assertIs(pool.ConnectionCls, oidc_client._PinnedHTTPSConnection)

    def test_provider_endpoints_may_carry_a_query_but_issuers_may_not(self):
        oidc_client.check_url_syntax(
            "https://idp.acme.test/authorize?tenant=acme",
            what="authorization_endpoint",
            allow_query=True,
        )
        with self.assertRaises(ValueError):
            oidc_client.check_url_syntax("https://idp.acme.test/authorize?tenant=acme")
        with self.assertRaises(ValueError):
            oidc_client.check_url_syntax(
                "https://idp.acme.test/x#frag", allow_query=True
            )

    def test_discovery_keeps_the_query_of_the_authorization_endpoint(self):
        original = self.idp.send

        def send(method, url, **kw):
            status, body = original(method, url, **kw)
            if url.endswith("openid-configuration"):
                doc = json.loads(body)
                doc["authorization_endpoint"] += "?tenant=acme"
                body = json.dumps(doc).encode()
            return status, body

        with mock.patch.object(oidc_client, "_send", side_effect=send):
            response = self.client.get(START, {"organization": self.org.id})
        self.assertEqual(response.status_code, 302, response.content)
        location = urlsplit(response["Location"])
        self.assertEqual(location.path, "/realm/auth")
        query = parse_qs(location.query)
        self.assertEqual(query["tenant"], ["acme"])
        self.assertEqual(query["client_id"], [CLIENT_ID])

    def test_request_json_accepts_endpoint_urls_with_a_query(self):
        with mock.patch.object(
            oidc_client, "_send", return_value=(200, b'{"keys": []}')
        ) as send:
            data = oidc_client._request_json("GET", "https://idp.acme.test/certs?t=1")
        self.assertEqual(data, {"keys": []})
        self.assertEqual(send.call_args.args[1], "https://idp.acme.test/certs?t=1")

    def test_basic_credentials_are_form_encoded_before_base64(self):
        # RFC 6749 2.3.1: a ":" in the id or a "+" in the secret must be escaped
        captured = {}

        def send(method, url, **kwargs):
            captured.update(kwargs)
            return 200, b'{"id_token": "x.y.z"}'

        with mock.patch.object(oidc_client, "_send", side_effect=send):
            oidc_client.exchange_code(
                {"token_endpoint": "https://idp.acme.test/token"},
                client_id="app:one two",
                client_secret="p+q/r=s",
                code="c",
                redirect_uri="https://api.test/cb",
                code_verifier="v",
            )
        basic = captured["headers"]["Authorization"].split(" ", 1)[1]
        self.assertEqual(
            base64.b64decode(basic).decode(), "app%3Aone%20two:p%2Bq%2Fr%3Ds"
        )

    def test_pkce_pair_is_s256(self):
        verifier, challenge = oidc_client.pkce_pair()
        digest = hashlib.sha256(verifier.encode()).digest()
        self.assertEqual(challenge, _b64u(digest))
        self.assertGreaterEqual(len(verifier), 43)


# ---------------------------------------------------------------- linking


class SSOAccountLinkingTests(SSOTestCase):
    def make_user(self, username="ada", email="ada@acme.test", **kwargs):
        return User.objects.create_user(username, email, "pw12345678", **kwargs)

    def test_existing_account_with_same_email_is_not_taken_over(self):
        existing = self.make_user()
        _, response = self.sso_login()
        self.assert_error(response, "account_exists")
        self.assertEqual(OrganizationSSOIdentity.objects.count(), 0)
        self.assertFalse(
            OrganizationMembership.objects.filter(
                organization=self.org, user=existing
            ).exists()
        )
        self.assert_no_login()

    def test_same_email_with_different_case_is_still_an_existing_account(self):
        self.make_user(email="Ada@Acme.test")
        _, response = self.sso_login()
        self.assert_error(response, "account_exists")

    def test_unverified_email_is_refused(self):
        for value in (False, None, "false", 1):
            self.idp.token_overrides = {"email_verified": value}
            _, response = self.sso_login()
            self.assert_error(response, "email_not_verified")
        self.idp.token_overrides = {"email": None, "email_verified": True}
        _, response = self.sso_login()
        self.assert_error(response, "email_not_verified")
        self.assertFalse(User.objects.filter(email="ada@acme.test").exists())

    def test_email_outside_claimed_domains_is_refused(self):
        self.idp.token_overrides = {"email": "ada@evil.test"}
        _, response = self.sso_login()
        self.assert_error(response, "domain_not_allowed")
        self.idp.token_overrides = {"email": "ada@acme.test.evil.test"}
        _, response = self.sso_login()
        self.assert_error(response, "domain_not_allowed")

    def test_auto_provision_off(self):
        self.provider.auto_provision = False
        self.provider.save()
        _, response = self.sso_login()
        self.assert_error(response, "provisioning_disabled")
        self.assertFalse(User.objects.filter(email="ada@acme.test").exists())

    def test_returning_login_ignores_a_changed_email_claim(self):
        ada = self.make_user()
        victim = self.make_user("victim", "victim@acme.test")
        OrganizationMembership.objects.create(organization=self.org, user=ada)
        OrganizationSSOIdentity.objects.create(
            provider=self.provider, issuer=ISSUER, subject="sub-123", user=ada
        )
        self.idp.token_overrides = {"email": "victim@acme.test"}
        _, response = self.sso_login()
        tokens = self.exchange(response)
        self.assertEqual(tokens.status_code, 200)
        access = jwt.decode(tokens.data["access"], options={"verify_signature": False})
        self.assertEqual(int(access["user_id"]), ada.id)
        self.assertNotEqual(int(access["user_id"]), victim.id)

    def test_new_subject_with_taken_email_does_not_hijack_a_linked_account(self):
        ada = self.make_user()
        OrganizationMembership.objects.create(organization=self.org, user=ada)
        OrganizationSSOIdentity.objects.create(
            provider=self.provider, issuer=ISSUER, subject="old-sub", user=ada
        )
        self.idp.token_overrides = {"sub": "new-sub"}
        _, response = self.sso_login()
        self.assert_error(response, "account_exists")

    def test_changing_the_issuer_does_not_reuse_old_links(self):
        ada = self.make_user()
        OrganizationMembership.objects.create(organization=self.org, user=ada)
        OrganizationSSOIdentity.objects.create(
            provider=self.provider,
            issuer="https://old-idp.acme.test",
            subject="sub-123",
            user=ada,
        )
        _, response = self.sso_login()
        self.assert_error(response, "account_exists")

    def test_staff_and_superusers_can_not_use_tenant_sso(self):
        for flags in ({"is_staff": True}, {"is_superuser": True}):
            OrganizationSSOIdentity.objects.all().delete()
            User.objects.filter(username="boss").delete()
            boss = self.make_user("boss", "boss@acme.test", **flags)
            OrganizationMembership.objects.create(organization=self.org, user=boss)
            OrganizationSSOIdentity.objects.create(
                provider=self.provider, issuer=ISSUER, subject="sub-123", user=boss
            )
            _, response = self.sso_login()
            self.assert_error(response, "privileged_account")

    def test_inactive_user_and_removed_member_are_refused(self):
        ada = self.make_user()
        membership = OrganizationMembership.objects.create(
            organization=self.org, user=ada
        )
        OrganizationSSOIdentity.objects.create(
            provider=self.provider, issuer=ISSUER, subject="sub-123", user=ada
        )
        membership.delete()
        _, response = self.sso_login()
        self.assert_error(response, "not_a_member")
        OrganizationMembership.objects.create(organization=self.org, user=ada)
        ada.is_active = False
        ada.save()
        _, response = self.sso_login()
        self.assert_error(response, "account_disabled")

    # ---- explicit linking from a signed-in session

    def link_start(self, user, org=None):
        client = APIClient()
        client.force_authenticate(user)
        response = client.post(f"/api/organizations/{(org or self.org).id}/sso/link/")
        return response

    def confirm_link(self, user, callback_response, org=None):
        """What the signed-in frontend does with ``?sso_link=<code>``."""
        query = parse_qs(urlsplit(callback_response["Location"]).query)
        self.assertIn("sso_link", query, callback_response["Location"])
        client = APIClient()
        client.force_authenticate(user)
        return client.post(
            f"/api/organizations/{(org or self.org).id}/sso/link/confirm/",
            {"code": query["sso_link"][0]},
            format="json",
        )

    def run_link(self, user, next_path=None, **idp_overrides):
        response = self.link_start(user)
        self.assertEqual(response.status_code, 200, response.content)
        start = urlsplit(response.data["start_url"])
        browser = APIClient()
        query = start.query + (f"&next={quote(next_path)}" if next_path else "")
        started = browser.get(start.path + "?" + query)
        self.assertEqual(started.status_code, 302, started.content)
        params = {
            k: v[0] for k, v in parse_qs(urlsplit(started["Location"]).query).items()
        }
        self.idp.nonce = params["nonce"]
        self.idp.challenge = params["code_challenge"]
        self.idp.redirect_uri = params["redirect_uri"]
        self.idp.token_overrides = idp_overrides
        return browser, self.callback(browser, params)

    def test_signed_in_member_can_link_and_then_sign_in(self):
        ada = self.make_user()
        OrganizationMembership.objects.create(organization=self.org, user=ada)
        # the IdP email differs on purpose: linking does not depend on it
        browser, response = self.run_link(ada, email="ada.work@acme.test")
        # the callback only stages the link, the signed-in account makes it
        self.assertEqual(urlsplit(response["Location"]).path, "/")
        self.assertEqual(
            list(parse_qs(urlsplit(response["Location"]).query)), ["sso_link"]
        )
        self.assertEqual(OrganizationSSOIdentity.objects.count(), 0)
        confirmed = self.confirm_link(ada, response)
        self.assertEqual(confirmed.status_code, 200, confirmed.content)
        self.assertEqual(confirmed.data, {"linked": True})
        identity = OrganizationSSOIdentity.objects.get()
        self.assertEqual(identity.user_id, ada.id)
        self.assertTrue(
            AuditEvent.objects.filter(extra__operation="sso.identity_linked").exists()
        )

        self.idp.token_overrides = {"email": "ada.work@acme.test"}
        _, login = self.sso_login()
        tokens = self.exchange(login)
        access = jwt.decode(tokens.data["access"], options={"verify_signature": False})
        self.assertEqual(int(access["user_id"]), ada.id)
        self.assertEqual(
            User.objects.filter(email__iexact="ada.work@acme.test").count(), 0
        )

    def test_link_is_not_made_by_whoever_holds_the_start_url(self):
        # A leaked start URL finished in another browser must not attach that
        # browser's provider identity to the account. Only the signed-in account
        # can confirm, and an unrelated account's confirm attempt changes nothing.
        ada = self.make_user()
        OrganizationMembership.objects.create(organization=self.org, user=ada)
        mallory = self.make_user("mallory", "mallory@acme.test")
        OrganizationMembership.objects.create(organization=self.org, user=mallory)
        _, response = self.run_link(ada, sub="mallory-at-the-idp")
        self.assertEqual(OrganizationSSOIdentity.objects.count(), 0)

        wrong = self.confirm_link(mallory, response)
        self.assertEqual(wrong.status_code, 400)
        self.assertEqual(wrong.data["code"], "invalid_code")
        anonymous = APIClient().post(
            f"/api/organizations/{self.org.id}/sso/link/confirm/",
            {"code": parse_qs(urlsplit(response["Location"]).query)["sso_link"][0]},
            format="json",
        )
        self.assertEqual(anonymous.status_code, 401)
        self.assertEqual(OrganizationSSOIdentity.objects.count(), 0)

        # the refused attempt did not burn the code for its real owner
        right = self.confirm_link(ada, response)
        self.assertEqual(right.status_code, 200)
        self.assertEqual(OrganizationSSOIdentity.objects.get().user_id, ada.id)

    def test_link_confirmation_is_single_use(self):
        ada = self.make_user()
        OrganizationMembership.objects.create(organization=self.org, user=ada)
        _, response = self.run_link(ada)
        self.assertEqual(self.confirm_link(ada, response).status_code, 200)
        self.assertEqual(self.confirm_link(ada, response).status_code, 400)

    def test_link_confirmation_repeats_the_membership_and_ownership_checks(self):
        ada = self.make_user()
        membership = OrganizationMembership.objects.create(
            organization=self.org, user=ada
        )
        _, response = self.run_link(ada)
        membership.delete()
        refused = self.confirm_link(ada, response)
        # no longer a member: the organization is not even visible to this account
        self.assertEqual(refused.status_code, 404)
        self.assertEqual(OrganizationSSOIdentity.objects.count(), 0)

        membership = OrganizationMembership.objects.create(
            organization=self.org, user=ada
        )
        _, response = self.run_link(ada)
        OrganizationSSOIdentity.objects.create(
            provider=self.provider,
            issuer=ISSUER,
            subject="sub-123",
            user=self.make_user("bob", "bob@acme.test"),
        )
        taken = self.confirm_link(ada, response)
        self.assertEqual(taken.status_code, 400)
        self.assertEqual(taken.data["code"], "identity_already_linked")

    def test_link_confirmation_is_scoped_to_its_organization(self):
        ada = self.make_user()
        OrganizationMembership.objects.create(organization=self.org, user=ada)
        other_org = Organization.objects.create(name="Other")
        OrganizationMembership.objects.create(organization=other_org, user=ada)
        _, response = self.run_link(ada)
        wrong_org = self.confirm_link(ada, response, org=other_org)
        self.assertEqual(wrong_org.status_code, 400)
        self.assertEqual(OrganizationSSOIdentity.objects.count(), 0)

    def test_link_result_keeps_the_query_and_fragment_of_next(self):
        ada = self.make_user()
        OrganizationMembership.objects.create(organization=self.org, user=ada)
        _, response = self.run_link(ada, next_path="/settings?tab=security#sso")
        parts = urlsplit(response["Location"])
        self.assertEqual(parts.path, "/settings")
        self.assertEqual(parts.fragment, "sso")
        query = parse_qs(parts.query)
        self.assertEqual(query["tab"], ["security"])
        self.assertEqual(list(query), ["tab", "sso_link"])
        self.assertNotIn("?", parts.query)

    def test_relinking_after_an_issuer_change_replaces_the_stale_link(self):
        ada = self.make_user()
        OrganizationMembership.objects.create(organization=self.org, user=ada)
        OrganizationSSOIdentity.objects.create(
            provider=self.provider,
            issuer="https://old-idp.acme.test",
            subject="old-sub",
            user=ada,
        )
        _, response = self.run_link(ada)
        self.assertEqual(self.confirm_link(ada, response).status_code, 200)
        identity = OrganizationSSOIdentity.objects.get()
        self.assertEqual((identity.issuer, identity.subject), (ISSUER, "sub-123"))
        self.assertEqual(identity.user_id, ada.id)

        # and the normal login works again
        self.idp.token_overrides = {}
        _, login = self.sso_login()
        self.assertEqual(urlsplit(login["Location"]).path, "/auth/sso/callback")

    def test_provisioning_rechecks_the_email_inside_the_lock(self):
        # Two first logins pass the unlocked check together. The one that waits on
        # the provider row must see the account the other one committed.
        calls = []
        real = OrganizationOIDCProvider.objects.select_for_update

        def lock_then_other_login_commits():
            calls.append(1)
            User.objects.create_user("ada-race", "ada@acme.test", "pw12345678")
            return real()

        with mock.patch.object(
            OrganizationOIDCProvider.objects,
            "select_for_update",
            side_effect=lock_then_other_login_commits,
        ):
            _, response = self.sso_login()
        self.assertEqual(calls, [1])
        self.assert_error(response, "account_exists")
        # nothing was provisioned (the stand-in for the other login's user sits in
        # the rolled-back block, as the test runs in one connection)
        self.assertEqual(OrganizationSSOIdentity.objects.count(), 0)
        self.assertEqual(OrganizationMembership.objects.count(), 1)  # just the owner

    def test_link_url_needs_authentication_and_membership(self):
        self.assertEqual(
            self.client.post(f"/api/organizations/{self.org.id}/sso/link/").status_code,
            401,
        )
        outsider = self.make_user("out", "out@acme.test")
        self.assertEqual(self.link_start(outsider).status_code, 404)

    def test_link_token_is_single_use_and_bound_to_the_organization(self):
        ada = self.make_user()
        OrganizationMembership.objects.create(organization=self.org, user=ada)
        url = urlsplit(self.link_start(ada).data["start_url"])
        first = APIClient().get(url.path + "?" + url.query)
        second = APIClient().get(url.path + "?" + url.query)
        self.assertEqual(first.status_code, 302)
        self.assertTrue(first["Location"].startswith(ISSUER))
        self.assert_error(second, "link_expired")

        other_org = Organization.objects.create(name="Other")
        other_provider = OrganizationOIDCProvider.objects.create(
            organization=other_org,
            issuer="https://idp.other.test",
            client_id="o",
            is_enabled=True,
        )
        OrganizationSSODomain.objects.create(
            provider=other_provider, domain="other.test"
        )
        token = parse_qs(url.query)["link_token"][0]
        cache.set(
            f"org-sso-link:{token}",
            {"user_id": ada.id, "organization_id": self.org.id},
            60,
        )
        replay = APIClient().get(
            START, {"organization": other_org.id, "link_token": token}
        )
        self.assert_error(replay, "link_expired")

    def test_subject_already_linked_to_someone_else(self):
        bob = self.make_user("bob", "bob@acme.test")
        OrganizationMembership.objects.create(organization=self.org, user=bob)
        OrganizationSSOIdentity.objects.create(
            provider=self.provider, issuer=ISSUER, subject="sub-123", user=bob
        )
        ada = self.make_user()
        OrganizationMembership.objects.create(organization=self.org, user=ada)
        _, response = self.run_link(ada)
        self.assert_error(response, "identity_already_linked")
        self.assertEqual(OrganizationSSOIdentity.objects.filter(user=ada).count(), 0)

    def test_user_can_only_hold_one_link_per_provider(self):
        ada = self.make_user()
        OrganizationMembership.objects.create(organization=self.org, user=ada)
        OrganizationSSOIdentity.objects.create(
            provider=self.provider, issuer=ISSUER, subject="first", user=ada
        )
        _, response = self.run_link(ada, sub="second")
        self.assert_error(response, "user_already_linked")

    def test_member_removed_between_start_and_callback_can_not_link(self):
        ada = self.make_user()
        membership = OrganizationMembership.objects.create(
            organization=self.org, user=ada
        )
        response = self.link_start(ada)
        start = urlsplit(response.data["start_url"])
        browser = APIClient()
        started = browser.get(start.path + "?" + start.query)
        params = {
            k: v[0] for k, v in parse_qs(urlsplit(started["Location"]).query).items()
        }
        self.idp.nonce, self.idp.challenge = params["nonce"], params["code_challenge"]
        self.idp.redirect_uri = params["redirect_uri"]
        membership.delete()
        self.assert_error(self.callback(browser, params), "not_a_member")


@override_settings(DISABLE_RATE_LIMITING=True)
class SSOThrottleTests(APITestCase):
    def test_public_endpoints_are_rate_limited(self):
        cache.clear()
        statuses = [
            self.client.post(
                "/api/auth/sso/discover/", {"email": "a@nowhere.test"}, format="json"
            ).status_code
            for _ in range(25)
        ]
        self.assertEqual(statuses[0], 200)
        self.assertIn(429, statuses)
