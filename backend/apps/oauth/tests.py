import base64
import hashlib
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.oauth.backends import OAuth2TokenAuthentication
from apps.oauth.models import OAuthAuthorizationCode, OAuthClient, OAuthToken

User = get_user_model()


@pytest.fixture
def test_user(db):
    return User.objects.create_user(
        username="oauth_user", email="user@example.com", password="password123"
    )


@pytest.fixture
def oauth_client_obj(db, test_user):
    client = OAuthClient(
        user=test_user,
        name="Test Integration App",
        client_id="client_test123",
        client_type=OAuthClient.ClientType.CONFIDENTIAL,
        redirect_uris=["http://localhost:3000/callback"],
        allowed_scopes=["openid", "profile", "email", "lesson:read"],
    )
    client.set_client_secret("secret123")
    client.save()
    return client


@pytest.fixture
def public_oauth_client(db, test_user):
    client = OAuthClient(
        user=test_user,
        name="Public SPA Client",
        client_id="client_public456",
        client_type=OAuthClient.ClientType.PUBLIC,
        redirect_uris=["http://localhost:3000/callback"],
        allowed_scopes=["openid", "profile"],
    )
    client.save()  # no client_secret for public clients
    return client


@pytest.mark.django_db
def test_openid_discovery_and_jwks():
    api_client = APIClient()

    res_config = api_client.get("/.well-known/openid-configuration")
    assert res_config.status_code == 200
    config = res_config.json()
    assert "issuer" in config
    assert config["authorization_endpoint"].endswith("/oauth/authorize/")
    assert config["token_endpoint"].endswith("/oauth/token/")

    res_jwks = api_client.get("/.well-known/jwks.json")
    assert res_jwks.status_code == 200
    jwks = res_jwks.json()
    assert "keys" in jwks
    assert len(jwks["keys"]) >= 1
    assert jwks["keys"][0]["kty"] == "RSA"
    assert jwks["keys"][0]["alg"] == "RS256"


@pytest.mark.django_db
def test_authorization_code_pkce_flow(test_user, oauth_client_obj):
    api_client = APIClient()
    api_client.force_authenticate(user=test_user)

    # 1. GET consent info
    res_get = api_client.get(
        "/oauth/authorize/",
        {
            "client_id": oauth_client_obj.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "response_type": "code",
            "scope": "openid profile email",
            "state": "random_state_123",
        },
    )
    assert res_get.status_code == 200
    assert res_get.json()["client_name"] == "Test Integration App"

    # 2. PKCE Setup
    code_verifier = "high_entropy_code_verifier_1234567890_pkce"
    hashed = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    code_challenge = base64.urlsafe_b64encode(hashed).rstrip(b"=").decode("utf-8")

    # 3. POST consent grant -> issue code
    res_grant = api_client.post(
        "/oauth/authorize/",
        {
            "client_id": oauth_client_obj.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "response_type": "code",
            "scope": "openid profile email",
            "state": "random_state_123",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "nonce": "test_nonce_val",
            "action": "grant",
        },
        format="json",
    )
    assert res_grant.status_code == 201
    code = res_grant.json()["code"]
    assert code.startswith("authcode_")

    # 4. Exchange code for tokens at /oauth/token/
    api_client.logout()
    res_token = api_client.post(
        "/oauth/token/",
        {
            "grant_type": "authorization_code",
            "client_id": oauth_client_obj.client_id,
            "client_secret": "secret123",
            "code": code,
            "redirect_uri": "http://localhost:3000/callback",
            "code_verifier": code_verifier,
        },
        format="json",
    )
    assert res_token.status_code == 200
    token_data = res_token.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data
    assert "id_token" in token_data
    assert token_data["token_type"] == "Bearer"


@pytest.mark.django_db
def test_authorization_code_cannot_be_replayed(test_user, oauth_client_obj):
    api_client = APIClient()
    api_client.force_authenticate(user=test_user)

    res_grant = api_client.post(
        "/oauth/authorize/",
        {
            "client_id": oauth_client_obj.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "response_type": "code",
            "scope": "openid",
            "action": "grant",
        },
        format="json",
    )
    code = res_grant.json()["code"]

    token_kwargs = {
        "grant_type": "authorization_code",
        "client_id": oauth_client_obj.client_id,
        "client_secret": "secret123",
        "code": code,
        "redirect_uri": "http://localhost:3000/callback",
    }

    res_first = api_client.post("/oauth/token/", token_kwargs, format="json")
    assert res_first.status_code == 200

    # Replaying the same code must fail
    res_second = api_client.post("/oauth/token/", token_kwargs, format="json")
    assert res_second.status_code == 400


@pytest.mark.django_db
def test_redirect_uri_mismatch_rejected(test_user, oauth_client_obj):
    api_client = APIClient()
    api_client.force_authenticate(user=test_user)

    res = api_client.post(
        "/oauth/authorize/",
        {
            "client_id": oauth_client_obj.client_id,
            "redirect_uri": "http://evil.example.com/callback",
            "response_type": "code",
            "scope": "openid",
            "action": "grant",
        },
        format="json",
    )
    assert res.status_code == 400


@pytest.mark.django_db
def test_public_client_pkce_flow_without_secret(test_user, public_oauth_client):
    api_client = APIClient()
    api_client.force_authenticate(user=test_user)

    code_verifier = "public_client_code_verifier_1234567890"
    hashed = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    code_challenge = base64.urlsafe_b64encode(hashed).rstrip(b"=").decode("utf-8")

    res_grant = api_client.post(
        "/oauth/authorize/",
        {
            "client_id": public_oauth_client.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "response_type": "code",
            "scope": "openid",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "action": "grant",
        },
        format="json",
    )
    code = res_grant.json()["code"]

    res_token = api_client.post(
        "/oauth/token/",
        {
            "grant_type": "authorization_code",
            "client_id": public_oauth_client.client_id,
            "code": code,
            "redirect_uri": "http://localhost:3000/callback",
            "code_verifier": code_verifier,
        },
        format="json",
    )
    assert res_token.status_code == 200
    assert "access_token" in res_token.json()


@pytest.mark.django_db
def test_client_credentials_flow(oauth_client_obj):
    api_client = APIClient()

    res_token = api_client.post(
        "/oauth/token/",
        {
            "grant_type": "client_credentials",
            "client_id": oauth_client_obj.client_id,
            "client_secret": "secret123",
            "scope": "lesson:read",
        },
        format="json",
    )
    assert res_token.status_code == 200
    data = res_token.json()
    assert "access_token" in data
    assert data["scope"] == "lesson:read"


@pytest.mark.django_db
def test_refresh_token_rotation(test_user, oauth_client_obj):
    api_client = APIClient()
    api_client.force_authenticate(user=test_user)

    res_grant = api_client.post(
        "/oauth/authorize/",
        {
            "client_id": oauth_client_obj.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "response_type": "code",
            "scope": "openid profile",
            "action": "grant",
        },
        format="json",
    )
    code = res_grant.json()["code"]

    res_token1 = api_client.post(
        "/oauth/token/",
        {
            "grant_type": "authorization_code",
            "client_id": oauth_client_obj.client_id,
            "client_secret": "secret123",
            "code": code,
        },
        format="json",
    )
    rt1 = res_token1.json()["refresh_token"]

    # Refresh token
    res_token2 = api_client.post(
        "/oauth/token/",
        {
            "grant_type": "refresh_token",
            "refresh_token": rt1,
        },
        format="json",
    )
    assert res_token2.status_code == 200
    rt2 = res_token2.json()["refresh_token"]
    assert rt2 != rt1

    # Verify old refresh token is now invalid (rotation)
    res_fail = api_client.post(
        "/oauth/token/",
        {
            "grant_type": "refresh_token",
            "refresh_token": rt1,
        },
        format="json",
    )
    assert res_fail.status_code == 400


@pytest.mark.django_db
def test_token_introspection_and_revocation(test_user, oauth_client_obj):
    api_client = APIClient()
    api_client.force_authenticate(user=test_user)

    res_grant = api_client.post(
        "/oauth/authorize/",
        {
            "client_id": oauth_client_obj.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "response_type": "code",
            "scope": "email",
            "action": "grant",
        },
        format="json",
    )
    code = res_grant.json()["code"]

    res_token = api_client.post(
        "/oauth/token/",
        {
            "grant_type": "authorization_code",
            "client_id": oauth_client_obj.client_id,
            "client_secret": "secret123",
            "code": code,
        },
        format="json",
    )
    at = res_token.json()["access_token"]

    # Introspect
    res_intro = api_client.post("/oauth/introspect/", {"token": at}, format="json")
    assert res_intro.status_code == 200
    assert res_intro.json()["active"] is True

    # Revoke
    res_rev = api_client.post("/oauth/revoke/", {"token": at}, format="json")
    assert res_rev.status_code == 200

    # Introspect again -> active should be False
    res_intro2 = api_client.post("/oauth/introspect/", {"token": at}, format="json")
    assert res_intro2.status_code == 200
    assert res_intro2.json()["active"] is False


@pytest.mark.django_db
def test_drf_oauth2_bearer_authentication(test_user, oauth_client_obj):
    from rest_framework.request import Request
    from rest_framework.test import APIRequestFactory

    token_obj = OAuthToken.objects.create(
        client=oauth_client_obj,
        user=test_user,
        access_token="at_valid_bearer_123",
        scope="openid profile",
        access_token_expires_at=timezone.now() + timedelta(hours=1),
    )

    factory = APIRequestFactory()
    req = factory.get(
        "/api/users/me/", HTTP_AUTHORIZATION=f"Bearer {token_obj.access_token}"
    )
    drf_req = Request(req)

    auth = OAuth2TokenAuthentication()
    user, token = auth.authenticate(drf_req)
    assert user == test_user
    assert token == token_obj
    assert "openid" in token.scopes


@pytest.mark.django_db
def test_pkce_verify_helper():
    from apps.oauth.views import _verify_pkce

    verifier = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    # SHA-256 hash of the above verifier
    hashed = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(hashed).decode("ascii").rstrip("=")

    # Valid S256 verification
    assert _verify_pkce(verifier, challenge, "S256") is True

    # Padded challenge also matches
    padded_challenge = challenge + "="
    assert _verify_pkce(verifier, padded_challenge, "S256") is True

    # Mismatched verifier fails
    assert (
        _verify_pkce("wrong_verifier_123456789012345678901234567890", challenge, "S256")
        is False
    )

    # Plain method is rejected
    assert _verify_pkce(verifier, verifier, "plain") is False
    assert _verify_pkce(verifier, challenge, "plain") is False

    # Unknown method is rejected
    assert _verify_pkce(verifier, challenge, "S512") is False

    # Empty verifier fails
    assert _verify_pkce("", challenge, "S256") is False

    # Non-ascii verifier fails safely
    assert _verify_pkce("verifier_with_unicode_\u2603", challenge, "S256") is False


@pytest.mark.django_db
def test_public_client_requires_code_challenge_at_authorization(
    test_user, public_oauth_client
):
    api_client = APIClient()
    api_client.force_authenticate(user=test_user)

    # GET consent without code_challenge must fail for public clients
    res_get = api_client.get(
        "/oauth/authorize/",
        {
            "client_id": public_oauth_client.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "response_type": "code",
            "scope": "openid",
        },
    )
    assert res_get.status_code == 400
    assert res_get.json()["error"] == "invalid_request"
    assert "code_challenge is required" in res_get.json()["error_description"]

    # POST grant without code_challenge must fail for public clients
    res_post = api_client.post(
        "/oauth/authorize/",
        {
            "client_id": public_oauth_client.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "response_type": "code",
            "scope": "openid",
            "action": "grant",
        },
        format="json",
    )
    assert res_post.status_code == 400
    assert res_post.json()["error"] == "invalid_request"
    assert "code_challenge is required" in res_post.json()["error_description"]


@pytest.mark.django_db
def test_authorization_rejects_plain_code_challenge_method(
    test_user, public_oauth_client
):
    api_client = APIClient()
    api_client.force_authenticate(user=test_user)

    res = api_client.post(
        "/oauth/authorize/",
        {
            "client_id": public_oauth_client.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "response_type": "code",
            "scope": "openid",
            "code_challenge": "my_plain_challenge_string_12345",
            "code_challenge_method": "plain",
            "action": "grant",
        },
        format="json",
    )
    assert res.status_code == 400
    assert res.json()["error"] == "invalid_request"
    assert "code_challenge_method" in res.json()


@pytest.mark.django_db
def test_authorization_rejects_unsupported_code_challenge_method(
    test_user, public_oauth_client
):
    api_client = APIClient()
    api_client.force_authenticate(user=test_user)

    res = api_client.post(
        "/oauth/authorize/",
        {
            "client_id": public_oauth_client.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "response_type": "code",
            "scope": "openid",
            "code_challenge": "challenge_12345",
            "code_challenge_method": "S512",
            "action": "grant",
        },
        format="json",
    )
    assert res.status_code == 400
    assert res.json()["error"] == "invalid_request"


@pytest.mark.django_db
def test_public_client_token_exchange_validation(test_user, public_oauth_client):
    api_client = APIClient()
    api_client.force_authenticate(user=test_user)

    code_verifier = "public_client_secure_random_verifier_string_12345678"
    hashed = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(hashed).rstrip(b"=").decode("ascii")

    res_grant = api_client.post(
        "/oauth/authorize/",
        {
            "client_id": public_oauth_client.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "response_type": "code",
            "scope": "openid",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "action": "grant",
        },
        format="json",
    )
    assert res_grant.status_code == 201
    code = res_grant.json()["code"]

    api_client.logout()

    # 1. Missing code_verifier must fail
    res_no_verifier = api_client.post(
        "/oauth/token/",
        {
            "grant_type": "authorization_code",
            "client_id": public_oauth_client.client_id,
            "code": code,
            "redirect_uri": "http://localhost:3000/callback",
        },
        format="json",
    )
    assert res_no_verifier.status_code == 400
    assert res_no_verifier.json()["error"] == "invalid_grant"

    # 2. Invalid code_verifier must fail
    res_wrong_verifier = api_client.post(
        "/oauth/token/",
        {
            "grant_type": "authorization_code",
            "client_id": public_oauth_client.client_id,
            "code": code,
            "redirect_uri": "http://localhost:3000/callback",
            "code_verifier": "wrong_verifier_mismatching_challenge_12345",
        },
        format="json",
    )
    assert res_wrong_verifier.status_code == 400
    assert res_wrong_verifier.json()["error"] == "invalid_grant"

    # 3. Correct code_verifier succeeds
    res_valid = api_client.post(
        "/oauth/token/",
        {
            "grant_type": "authorization_code",
            "client_id": public_oauth_client.client_id,
            "code": code,
            "redirect_uri": "http://localhost:3000/callback",
            "code_verifier": code_verifier,
        },
        format="json",
    )
    assert res_valid.status_code == 200
    assert "access_token" in res_valid.json()


@pytest.mark.django_db
def test_public_client_token_exchange_rejects_code_without_challenge(
    test_user, public_oauth_client
):
    api_client = APIClient()

    # Manually created auth code for public client without challenge
    auth_code = OAuthAuthorizationCode.objects.create(
        client=public_oauth_client,
        user=test_user,
        code="authcode_unprotected_public_test",
        redirect_uri="http://localhost:3000/callback",
        scope="openid",
        code_challenge="",
        expires_at=timezone.now() + timedelta(minutes=10),
    )

    res = api_client.post(
        "/oauth/token/",
        {
            "grant_type": "authorization_code",
            "client_id": public_oauth_client.client_id,
            "code": auth_code.code,
            "redirect_uri": "http://localhost:3000/callback",
            "code_verifier": "some_verifier_string_12345678901234567890",
        },
        format="json",
    )
    assert res.status_code == 400
    assert res.json()["error"] == "invalid_grant"


@pytest.mark.django_db
def test_confidential_client_pkce_rejects_invalid_verifier(test_user, oauth_client_obj):
    api_client = APIClient()
    api_client.force_authenticate(user=test_user)

    code_verifier = "confidential_client_pkce_verifier_secret_12345"
    hashed = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(hashed).rstrip(b"=").decode("ascii")

    res_grant = api_client.post(
        "/oauth/authorize/",
        {
            "client_id": oauth_client_obj.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "response_type": "code",
            "scope": "openid",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "action": "grant",
        },
        format="json",
    )
    assert res_grant.status_code == 201
    code = res_grant.json()["code"]

    api_client.logout()

    # Wrong verifier rejected
    res_fail = api_client.post(
        "/oauth/token/",
        {
            "grant_type": "authorization_code",
            "client_id": oauth_client_obj.client_id,
            "client_secret": "secret123",
            "code": code,
            "redirect_uri": "http://localhost:3000/callback",
            "code_verifier": "completely_wrong_verifier_token",
        },
        format="json",
    )
    assert res_fail.status_code == 400
    assert res_fail.json()["error"] == "invalid_grant"


@pytest.mark.django_db
def test_openid_discovery_has_pkce_methods():
    api_client = APIClient()
    res = api_client.get("/.well-known/openid-configuration")
    assert res.status_code == 200
    config = res.json()
    assert "code_challenge_methods_supported" in config
    assert config["code_challenge_methods_supported"] == ["S256"]
