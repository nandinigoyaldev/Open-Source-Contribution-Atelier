import os
import json
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from .models import Plugin
from .registry import registry
from .manifest import validate_manifest


class PluginSystemTests(APITestCase):
    def setUp(self):
        # Ensure discovery syncs the database
        registry.discover_and_sync()

    def test_manifest_validation(self):
        valid_data = {
            "name": "test_plugin",
            "display_name": "Test Plugin",
            "version": "1.0.0",
            "api_version": "1.0.0",
            "description": "A simple test plugin.",
            "author": "Tester",
            "entry_point": "test_plugin",
        }
        manifest = validate_manifest(valid_data)
        self.assertEqual(manifest.name, "test_plugin")

        # Invalid name validation
        invalid_data = valid_data.copy()
        invalid_data["name"] = "Invalid Plugin!"
        with self.assertRaises(Exception):
            validate_manifest(invalid_data)

    def test_discovery_and_sync(self):
        plugin_exists = Plugin.objects.filter(name="github_stats").exists()
        self.assertTrue(plugin_exists)

        # Test registry loads it
        plugin = Plugin.objects.get(name="github_stats")
        self.assertEqual(plugin.display_name, "GitHub Stats")

    def test_plugin_activation_and_hooks(self):
        plugin = Plugin.objects.get(name="github_stats")
        plugin.is_active = True
        plugin.save()

        # Load active plugins
        registry.load_active_plugins()
        self.assertIn("github_stats", registry.active_plugins)

        # Test hook execution
        results = registry.execute_hook("on_activate")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], "github_stats")
        self.assertEqual(results[0][1], True)

    def test_dynamic_routing(self):
        # Initially inactive
        response = self.client.get("/api/plugins/github_stats/info/")
        self.assertEqual(response.status_code, 404)

        # Activate it
        plugin = Plugin.objects.get(name="github_stats")
        plugin.is_active = True
        plugin.save()
        registry.load_active_plugins()

        # Active request should route successfully
        response = self.client.get("/api/plugins/github_stats/info/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["stars"], 42)
