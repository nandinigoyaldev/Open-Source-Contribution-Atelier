import waffle
from django.contrib.auth.models import AnonymousUser, User
from django.test import RequestFactory, TestCase
from waffle.models import Flag, Switch

from .context_processors import feature_flags
from .middleware import FeatureFlags, FeatureFlagsMiddleware


class FeatureFlagContextProcessorTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()

    def test_feature_flags_in_context_with_switches(self):
        Switch.objects.create(name="beta_search", active=True)
        Switch.objects.create(name="dark_mode", active=False)

        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        context = feature_flags(request)

        self.assertIn("feature_flags", context)
        self.assertTrue(context["feature_flags"]["switches"]["beta_search"]["enabled"])
        self.assertFalse(context["feature_flags"]["switches"]["dark_mode"]["enabled"])

    def test_feature_flags_in_context_with_flags(self):
        user = User.objects.create_user("testuser")
        flag = Flag.objects.create(name="new_ui", everyone=True)
        flag.users.add(user)

        request = RequestFactory().get("/")
        request.user = user
        context = feature_flags(request)

        self.assertIn("feature_flags", context)
        self.assertTrue(context["feature_flags"]["flags"]["new_ui"]["enabled"])


class FeatureFlagsMiddlewareTests(TestCase):
    """`request.feature_flags` must be usable on guest requests (issue #2653)."""

    def setUp(self):
        from django.core.cache import cache

        # waffle caches flags outside the test transaction; clear between tests.
        cache.clear()
        self.factory = RequestFactory()
        self.middleware = FeatureFlagsMiddleware(lambda request: "response")

    def _guest_request(self, path="/"):
        request = self.factory.get(path)
        request.user = AnonymousUser()
        return request

    def test_guest_request_gets_feature_flags_accessor(self):
        request = self._guest_request()

        self.middleware(request)

        self.assertIsInstance(request.feature_flags, FeatureFlags)

    def test_guest_unknown_flag_is_false_not_attribute_error(self):
        request = self._guest_request()

        self.middleware(request)

        # The scenario from the issue: a guest hits a view that reads a flag.
        self.assertIs(request.feature_flags.is_enabled("new_landing"), False)

    def test_guest_request_evaluates_everyone_flag(self):
        Flag.objects.create(name="new_landing", everyone=True)
        request = self._guest_request()

        self.middleware(request)

        self.assertIs(request.feature_flags.is_enabled("new_landing"), True)

    def test_guest_request_respects_everyone_false(self):
        Flag.objects.create(name="new_landing", everyone=False)
        request = self._guest_request()

        self.middleware(request)

        self.assertIs(request.feature_flags.is_enabled("new_landing"), False)

    def test_authenticated_request_also_gets_accessor(self):
        Flag.objects.create(name="new_landing", everyone=True)
        request = self.factory.get("/")
        request.user = User.objects.create_user("member")

        self.middleware(request)

        self.assertIsInstance(request.feature_flags, FeatureFlags)
        self.assertIs(request.feature_flags.is_enabled("new_landing"), True)

    def test_middleware_returns_downstream_response(self):
        request = self._guest_request()

        self.assertEqual(self.middleware(request), "response")
