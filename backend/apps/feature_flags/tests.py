from django.test import RequestFactory, TestCase
from django.contrib.auth.models import AnonymousUser, User
import waffle
from waffle.models import Flag, Switch

from .context_processors import feature_flags

class FeatureFlagContextProcessorTests(TestCase):
    def test_feature_flags_in_context_with_switches(self):
        Switch.objects.create(name="beta_search", active=True)
        Switch.objects.create(name="dark_mode", active=False)

        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        context = feature_flags(request)

        self.assertIn("feature_flags", context)
        self.assertTrue(context["feature_flags"]["beta_search"]["enabled"])
        self.assertFalse(context["feature_flags"]["dark_mode"]["enabled"])

    def test_feature_flags_in_context_with_flags(self):
        user = User.objects.create_user("testuser")
        flag = Flag.objects.create(name="new_ui", everyone=False)
        flag.users.add(user)
        
        request = RequestFactory().get("/")
        request.user = user
        context = feature_flags(request)

        self.assertIn("feature_flags", context)
        self.assertTrue(context["feature_flags"]["new_ui"]["enabled"])
