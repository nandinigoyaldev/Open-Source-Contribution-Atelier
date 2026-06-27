from django.test import RequestFactory, TestCase

from .context_processors import feature_flags
from .models import FeatureFlag


class FeatureFlagModelTests(TestCase):
    def test_is_enabled_returns_default_when_flag_does_not_exist(self):
        self.assertFalse(FeatureFlag.objects.is_enabled("nonexistent"))
        self.assertTrue(FeatureFlag.objects.is_enabled("nonexistent", True))

    def test_is_enabled_returns_flag_value(self):
        FeatureFlag.objects.create(name="dark_mode", enabled=True)
        FeatureFlag.objects.create(name="beta_search", enabled=False)

        self.assertTrue(FeatureFlag.objects.is_enabled("dark_mode"))
        self.assertFalse(FeatureFlag.objects.is_enabled("beta_search"))

    def test_save_invalidates_cache(self):
        flag = FeatureFlag.objects.create(name="flag_a", enabled=False)
        self.assertFalse(FeatureFlag.objects.is_enabled("flag_a"))

        flag.enabled = True
        flag.save()
        self.assertTrue(FeatureFlag.objects.is_enabled("flag_a"))

    def test_delete_invalidates_cache(self):
        flag = FeatureFlag.objects.create(name="flag_b", enabled=True)
        self.assertTrue(FeatureFlag.objects.is_enabled("flag_b"))

        flag.delete()
        self.assertFalse(FeatureFlag.objects.is_enabled("flag_b"))

    def test_all_flags_returns_all_flags(self):
        FeatureFlag.objects.create(name="aa", enabled=True)
        FeatureFlag.objects.create(name="bb", enabled=False)

        result = FeatureFlag.objects.all_flags()
        self.assertIn("aa", result)
        self.assertIn("bb", result)
        self.assertTrue(result["aa"]["enabled"])
        self.assertFalse(result["bb"]["enabled"])

    def test_str_representation(self):
        flag = FeatureFlag(name="test_flag", enabled=True)
        self.assertEqual(str(flag), "test_flag: ON")

        flag.enabled = False
        self.assertEqual(str(flag), "test_flag: OFF")


class FeatureFlagContextProcessorTests(TestCase):
    def test_feature_flags_in_context(self):
        FeatureFlag.objects.create(name="dark_mode", enabled=True)
        FeatureFlag.objects.create(name="beta_search", enabled=False)

        request = RequestFactory().get("/")
        context = feature_flags(request)

        self.assertIn("feature_flags", context)
        self.assertTrue(context["feature_flags"]["dark_mode"]["enabled"])
        self.assertFalse(context["feature_flags"]["beta_search"]["enabled"])
