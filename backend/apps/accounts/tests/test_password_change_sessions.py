"""
Sessions after a password change or reset (issue #3191).

Policy under test:
  * Every access token and every refresh token issued before the change stops working.
  * Refresh tokens are also blacklisted on the server, and the device list (UserSession) is cleared.
  * When the user changes their password while signed in, the device they are using stays signed in:
    the response carries a fresh access/refresh pair bound to the same session.
  * A password reset (done signed out) revokes everything; the user signs in again.
"""

from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

from apps.accounts.models import PasswordResetToken, UserSession

User = get_user_model()

OLD = "OldPassword123!"
NEW = "NewPassword456!"


def login(username="alice", password=OLD, user_agent="Browser A"):
    client = APIClient()
    response = client.post(
        "/api/auth/login/",
        {"username": username, "password": password},
        HTTP_USER_AGENT=user_agent,
    )
    assert response.status_code == 200, response.data
    return response.data["access"], response.data["refresh"]


def bearer(access):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


class PasswordChangeSessionsTest(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(
            cache.clear
        )  # logins here must not count against other tests' throttles
        self.user = User.objects.create_user(
            username="alice", password=OLD, email="alice@example.com"
        )
        self.access_a, self.refresh_a = login(user_agent="Laptop")
        self.access_b, self.refresh_b = login(user_agent="Phone")

    def change_password(self, access=None, new=NEW):
        client = bearer(access or self.access_a)
        return client.post(
            "/api/auth/change-password/", {"old_password": OLD, "new_password": new}
        )

    # -- baseline ------------------------------------------------------------

    def test_both_sessions_work_before_the_change(self):
        self.assertEqual(bearer(self.access_a).get("/api/auth/me/").status_code, 200)
        self.assertEqual(bearer(self.access_b).get("/api/auth/me/").status_code, 200)
        self.assertEqual(UserSession.objects.filter(user=self.user).count(), 2)

    # -- old tokens are rejected ---------------------------------------------

    def test_the_other_device_access_token_is_rejected(self):
        self.assertEqual(self.change_password().status_code, status.HTTP_200_OK)
        response = bearer(self.access_b).get("/api/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_the_other_device_refresh_token_is_rejected(self):
        self.change_password()
        response = APIClient().post("/api/auth/refresh/", {"refresh": self.refresh_b})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_the_old_token_of_the_current_device_is_rejected_too(self):
        self.change_password()
        self.assertEqual(
            bearer(self.access_a).get("/api/auth/me/").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        response = APIClient().post("/api/auth/refresh/", {"refresh": self.refresh_a})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_every_outstanding_refresh_token_is_blacklisted_on_the_server(self):
        outstanding = OutstandingToken.objects.filter(user=self.user)
        self.assertGreaterEqual(outstanding.count(), 2)
        self.change_password()
        blacklisted_ids = set(
            BlacklistedToken.objects.filter(token__user=self.user).values_list(
                "token_id", flat=True
            )
        )
        old_ids = set(
            OutstandingToken.objects.filter(
                user=self.user, jti__in=self._jtis(self.refresh_a, self.refresh_b)
            ).values_list("id", flat=True)
        )
        self.assertTrue(old_ids)
        self.assertTrue(old_ids.issubset(blacklisted_ids))

    @staticmethod
    def _jtis(*refresh_tokens):
        from rest_framework_simplejwt.tokens import UntypedToken

        out = []
        for raw in refresh_tokens:
            out.append(UntypedToken(raw, verify=False)["jti"])
        return out

    # -- the user keeps the session they are using ---------------------------

    def test_the_response_carries_a_fresh_pair_for_the_current_device(self):
        response = self.change_password()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertNotEqual(response.data["access"], self.access_a)
        self.assertNotEqual(response.data["refresh"], self.refresh_a)

    def test_the_fresh_access_token_works_and_the_fresh_refresh_token_refreshes(self):
        response = self.change_password()
        me = bearer(response.data["access"]).get("/api/auth/me/")
        self.assertEqual(me.status_code, status.HTTP_200_OK)
        refreshed = APIClient().post(
            "/api/auth/refresh/", {"refresh": response.data["refresh"]}
        )
        self.assertEqual(refreshed.status_code, status.HTTP_200_OK)
        self.assertIn("access", refreshed.data)

    def test_the_fresh_pair_stays_bound_to_the_same_device_session(self):
        from rest_framework_simplejwt.tokens import UntypedToken

        before = UntypedToken(self.access_a, verify=False)["session_id"]
        response = self.change_password()
        after = UntypedToken(response.data["access"], verify=False)["session_id"]
        self.assertEqual(before, after)
        self.assertTrue(
            UserSession.objects.filter(user=self.user, session_id=before).exists()
        )

    def test_only_the_current_device_remains_in_the_session_list(self):
        from rest_framework_simplejwt.tokens import UntypedToken

        current = UntypedToken(self.access_a, verify=False)["session_id"]
        self.change_password()
        remaining = [
            str(s)
            for s in UserSession.objects.filter(user=self.user).values_list(
                "session_id", flat=True
            )
        ]
        self.assertEqual(remaining, [current])

    def test_a_token_without_a_session_id_still_gets_a_working_fresh_session(self):
        from apps.accounts.jwt import DynamicSaltRefreshToken

        UserSession.objects.filter(user=self.user).delete()
        token = DynamicSaltRefreshToken.for_user(self.user)
        response = self.change_password(access=str(token.access_token))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            bearer(response.data["access"]).get("/api/auth/me/").status_code, 200
        )
        self.assertEqual(UserSession.objects.filter(user=self.user).count(), 1)

    # -- normal re-login -----------------------------------------------------

    def test_signing_in_again_with_the_new_password_works_and_the_old_one_does_not(
        self,
    ):
        self.change_password()
        old = APIClient().post(
            "/api/auth/login/", {"username": "alice", "password": OLD}
        )
        self.assertEqual(old.status_code, status.HTTP_401_UNAUTHORIZED)
        access, refresh = login(password=NEW, user_agent="Tablet")
        self.assertEqual(bearer(access).get("/api/auth/me/").status_code, 200)
        self.assertEqual(
            APIClient().post("/api/auth/refresh/", {"refresh": refresh}).status_code,
            200,
        )

    def test_a_login_after_the_change_is_not_caught_by_the_revocation(self):
        self.change_password()
        access, _ = login(password=NEW, user_agent="Tablet")
        # And a second change later revokes that one in turn.
        client = bearer(access)
        again = client.post(
            "/api/auth/change-password/",
            {"old_password": NEW, "new_password": "ThirdPass789!"},
        )
        self.assertEqual(again.status_code, status.HTTP_200_OK)
        self.assertEqual(bearer(access).get("/api/auth/me/").status_code, 401)

    # -- what must not change ------------------------------------------------

    def test_a_wrong_current_password_revokes_nothing(self):
        client = bearer(self.access_a)
        response = client.post(
            "/api/auth/change-password/",
            {"old_password": "Wrong123!", "new_password": NEW},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(bearer(self.access_a).get("/api/auth/me/").status_code, 200)
        self.assertEqual(bearer(self.access_b).get("/api/auth/me/").status_code, 200)
        self.assertEqual(UserSession.objects.filter(user=self.user).count(), 2)
        self.assertFalse(
            BlacklistedToken.objects.filter(token__user=self.user).exists()
        )

    def test_a_weak_new_password_revokes_nothing(self):
        response = self.change_password(new="short")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(bearer(self.access_b).get("/api/auth/me/").status_code, 200)

    def test_changing_the_password_requires_authentication(self):
        response = APIClient().post(
            "/api/auth/change-password/", {"old_password": OLD, "new_password": NEW}
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_other_users_are_not_affected(self):
        other = User.objects.create_user(
            username="bob", password=OLD, email="bob@example.com"
        )
        other_access, other_refresh = login(username="bob")
        self.change_password()
        self.assertEqual(UserSession.objects.filter(user=other).count(), 1)
        self.assertFalse(BlacklistedToken.objects.filter(token__user=other).exists())
        self.assertEqual(bearer(other_access).get("/api/auth/me/").status_code, 200)
        self.assertEqual(
            APIClient()
            .post("/api/auth/refresh/", {"refresh": other_refresh})
            .status_code,
            200,
        )

    def test_websocket_clients_are_told_the_tokens_were_revoked(self):
        with mock.patch("apps.accounts.services.publish_token_revoked") as publish:
            self.change_password()
        publish.assert_called_once_with(self.user.pk)

    def test_an_unreachable_redis_does_not_break_the_password_change(self):
        # Point the publisher at a port nothing listens on.
        with mock.patch(
            "apps.accounts.token_rotation._redis_url",
            return_value="redis://127.0.0.1:1/0",
        ):
            response = self.change_password()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(bearer(self.access_b).get("/api/auth/me/").status_code, 401)

    def test_the_password_change_is_all_or_nothing(self):
        with mock.patch(
            "apps.accounts.views.revoke_user_sessions", side_effect=RuntimeError("boom")
        ):
            with self.assertRaises(RuntimeError):
                self.change_password()
        self.user.refresh_from_db()
        self.assertTrue(
            self.user.check_password(OLD), "the old password must still work"
        )
        self.assertEqual(bearer(self.access_b).get("/api/auth/me/").status_code, 200)


class PasswordResetSessionsTest(TestCase):
    def setUp(self):
        cache.clear()  # the confirm endpoint is rate limited per address
        self.addCleanup(cache.clear)
        self.user = User.objects.create_user(
            username="alice", password=OLD, email="alice@example.com"
        )
        self.access_a, self.refresh_a = login(user_agent="Laptop")
        self.access_b, self.refresh_b = login(user_agent="Phone")
        self.reset = PasswordResetToken.objects.create(user=self.user)

    def confirm(self, password=NEW):
        return APIClient().post(
            "/api/auth/password-reset/confirm/",
            {"token": str(self.reset.token), "new_password": password},
        )

    def test_reset_revokes_every_device(self):
        response = self.confirm()
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        for access in (self.access_a, self.access_b):
            self.assertEqual(bearer(access).get("/api/auth/me/").status_code, 401)
        for refresh in (self.refresh_a, self.refresh_b):
            self.assertEqual(
                APIClient()
                .post("/api/auth/refresh/", {"refresh": refresh})
                .status_code,
                401,
            )

    def test_reset_clears_the_device_list_and_blacklists_refresh_tokens(self):
        self.confirm()
        self.assertEqual(UserSession.objects.filter(user=self.user).count(), 0)
        self.assertTrue(BlacklistedToken.objects.filter(token__user=self.user).exists())

    def test_after_a_reset_the_user_signs_in_again_normally(self):
        self.confirm()
        access, _ = login(password=NEW, user_agent="Laptop")
        self.assertEqual(bearer(access).get("/api/auth/me/").status_code, 200)

    def test_a_failed_reset_revokes_nothing(self):
        response = APIClient().post(
            "/api/auth/password-reset/confirm/",
            {"token": "00000000-0000-0000-0000-000000000000", "new_password": NEW},
        )
        self.assertGreaterEqual(response.status_code, 400)
        self.assertEqual(bearer(self.access_b).get("/api/auth/me/").status_code, 200)
