"""API contract tests for authentication error responses.

Every auth failure goes through ``throttle_exception_handler`` and must expose
the same envelope: ``error`` (True), a stable machine-readable ``code`` and a
human ``message``. These tests assert status codes and the envelope shape, never
the wording of ``message``. They need no database: credential checks and the
user model are mocked or never reached.
"""

from datetime import timedelta
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

User = get_user_model()

LOGIN_URL = "/api/auth/login/"
REFRESH_URL = "/api/auth/refresh/"
ME_URL = "/api/auth/me/"
USERS_URL = "/api/auth/users/"


@pytest.fixture(autouse=True)
def _no_throttle_state():
    """Keep throttle counters from leaking between tests."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


from apps.accounts.views import LoginView, MeView, RefreshView, UserListView

VIEWS = {
    LOGIN_URL: LoginView,
    REFRESH_URL: RefreshView,
    ME_URL: MeView,
    USERS_URL: UserListView,
}


class ViewClient:
    """Calls the auth views directly through the DRF stack (auth, permissions,
    throttles, exception handler) without the Django middleware chain, so no
    database is needed."""

    def __init__(self):
        self.factory = APIRequestFactory()
        self.extra = {}
        self.user = None

    def credentials(self, **extra):
        self.extra = extra

    def force_authenticate(self, user):
        self.user = user

    def _call(self, method, url, data=None):
        request = (
            getattr(self.factory, method)(url, data, format="json", **self.extra)
            if method == "post"
            else getattr(self.factory, method)(url, **self.extra)
        )
        if self.user is not None:
            force_authenticate(request, user=self.user)
        response = VIEWS[url].as_view()(request)
        response.render()
        return response

    def get(self, url):
        return self._call("get", url)

    def post(self, url, data=None, format=None):
        return self._call("post", url, data)


@pytest.fixture
def client():
    return ViewClient()


def assert_error_envelope(response, status_code, code=None):
    assert response.status_code == status_code
    data = response.data
    assert data["error"] is True
    assert isinstance(data["code"], str) and data["code"]
    assert isinstance(data["message"], str) and data["message"]
    if code is not None:
        assert data["code"] == code
    return data


def expired_token(token_class):
    token = token_class()
    token.set_exp(from_time=token.current_time, lifetime=timedelta(minutes=-5))
    token["user_id"] = 1
    return str(token)


class TestLoginErrors:
    def test_invalid_credentials(self, client):
        with mock.patch(
            "rest_framework_simplejwt.serializers.authenticate", return_value=None
        ):
            response = client.post(
                LOGIN_URL, {"username": "nobody", "password": "wrong"}, format="json"
            )
        assert_error_envelope(response, 401, "no_active_account")

    @pytest.mark.parametrize(
        "payload", [{}, {"username": "someone"}, {"password": "x"}]
    )
    def test_missing_fields_is_validation_error(self, client, payload):
        response = client.post(LOGIN_URL, payload, format="json")
        data = assert_error_envelope(response, 400, "validation_error")
        assert isinstance(data["errors"], dict) and data["errors"]
        missing = {"username", "password"} - set(payload)
        assert missing <= set(data["errors"])

    def test_overlong_password_is_validation_error(self, client):
        response = client.post(
            LOGIN_URL, {"username": "someone", "password": "x" * 500}, format="json"
        )
        data = assert_error_envelope(response, 400, "validation_error")
        assert "password" in data["errors"]


class TestRefreshErrors:
    def test_missing_refresh_token(self, client):
        response = client.post(REFRESH_URL, {}, format="json")
        data = assert_error_envelope(response, 400, "validation_error")
        assert "refresh" in data["errors"]

    def test_malformed_refresh_token(self, client):
        response = client.post(REFRESH_URL, {"refresh": "not.a.jwt"}, format="json")
        assert_error_envelope(response, 401, "token_not_valid")

    def test_expired_refresh_token(self, client):
        response = client.post(
            REFRESH_URL, {"refresh": expired_token(RefreshToken)}, format="json"
        )
        assert_error_envelope(response, 401, "token_not_valid")


class TestProtectedEndpointErrors:
    def test_missing_credentials(self, client):
        response = client.get(ME_URL)
        assert_error_envelope(response, 401, "not_authenticated")

    @pytest.mark.parametrize("header", ["Bearer not.a.jwt", "Bearer ", "Bearer a b c"])
    def test_malformed_access_token(self, client, header):
        client.credentials(HTTP_AUTHORIZATION=header)
        response = client.get(ME_URL)
        assert response.status_code == 401
        data = response.data
        assert data["error"] is True
        assert isinstance(data["code"], str) and data["code"]

    def test_expired_access_token(self, client):
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {expired_token(AccessToken)}")
        response = client.get(ME_URL)
        assert_error_envelope(response, 401, "token_not_valid")

    def test_refresh_token_is_not_accepted_as_access_token(self, client):
        token = RefreshToken()
        token["user_id"] = 1
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = client.get(ME_URL)
        assert_error_envelope(response, 401, "token_not_valid")

    def test_insufficient_role_is_forbidden(self, client):
        client.force_authenticate(user=User(id=1, username="learner"))
        # HasRole looks up groups in the database; a user with no role is denied.
        with mock.patch(
            "apps.core.permissions.HasRole.has_permission", return_value=False
        ):
            response = client.get(USERS_URL)
        assert_error_envelope(response, 403, "permission_denied")


def test_all_auth_failures_share_the_same_envelope_keys(client):
    """401 responses from different endpoints expose the same key set."""
    unauthenticated = client.get(ME_URL).data
    bad_refresh = client.post(REFRESH_URL, {"refresh": "x"}, format="json").data
    for body in (unauthenticated, bad_refresh):
        assert {"error", "code", "message"} <= set(body)
