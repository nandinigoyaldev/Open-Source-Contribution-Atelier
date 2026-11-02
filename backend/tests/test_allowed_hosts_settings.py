from unittest.mock import patch

from django.conf import settings as django_settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config import settings


class AllowedHostsSettingsTests(SimpleTestCase):
    """ALLOWED_HOSTS must come from the environment and never be a wildcard in production."""

    def test_comma_list_is_parsed_and_trimmed(self):
        self.assertEqual(
            settings._parse_allowed_hosts(" example.com, ,api.example.com ,"),
            ["example.com", "api.example.com"],
        )

    def test_default_hosts_are_local_only(self):
        default = settings._parse_allowed_hosts("localhost,127.0.0.1")
        self.assertEqual(default, ["localhost", "127.0.0.1"])
        self.assertNotIn("*", default)

    def test_wildcard_is_rejected_when_debug_is_disabled(self):
        with patch.object(settings, "DEBUG", False):
            with self.assertRaises(ImproperlyConfigured):
                settings._validate_allowed_hosts(["*"])

    def test_explicit_hosts_are_allowed_when_debug_is_disabled(self):
        with patch.object(settings, "DEBUG", False):
            hosts = ["api.example.com"]
            self.assertEqual(settings._validate_allowed_hosts(hosts), hosts)

    def test_wildcard_is_allowed_for_local_debug(self):
        with patch.object(settings, "DEBUG", True):
            self.assertEqual(settings._validate_allowed_hosts(["*"]), ["*"])

    def test_loaded_settings_have_no_wildcard_and_keep_testserver(self):
        if not settings.DEBUG:
            self.assertNotIn("*", django_settings.ALLOWED_HOSTS)
        hosts = django_settings.ALLOWED_HOSTS
        self.assertTrue("testserver" in hosts or "*" in hosts)

    def test_hostnames_are_extracted_from_hosts_and_urls(self):
        self.assertEqual(
            settings._hostnames_from_values(
                "atelier-backend.onrender.com",
                "https://atelier.vercel.app/",
                "",
                "https://atelier.example.com:8443/some/path",
                None,
            ),
            [
                "atelier-backend.onrender.com",
                "atelier.vercel.app",
                "atelier.example.com",
            ],
        )

    def test_platform_hosts_are_added_without_duplicates(self):
        hosts = settings._add_platform_hosts(
            ["localhost", "atelier.vercel.app"],
            "atelier-backend.onrender.com",
            "atelier.vercel.app",
            "https://user-atelier.hf.space",
        )
        self.assertEqual(
            hosts,
            [
                "localhost",
                "atelier.vercel.app",
                "atelier-backend.onrender.com",
                "user-atelier.hf.space",
            ],
        )

    def test_platform_values_are_optional(self):
        self.assertEqual(
            settings._add_platform_hosts(["localhost"], "", ""), ["localhost"]
        )
