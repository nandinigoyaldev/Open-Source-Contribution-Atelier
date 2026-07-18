import os
import json
import importlib
import logging
import sys
from django.conf import settings
from .manifest import validate_manifest
from .models import Plugin

logger = logging.getLogger(__name__)

class PluginRegistry:
    def __init__(self):
        self.active_plugins = {}  # name -> manifest (PluginManifest)
        self.loaded_modules = {}  # name -> imported entrypoint module object

    def discover_and_sync(self):
        """Scans the PLUGINS_DIR and synchronizes database records."""
        from django.db import connection
        if "plugins_plugin" not in connection.introspection.table_names():
            logger.warning("Plugin database table does not exist yet. Skipping DB sync.")
            return

        plugins_dir = getattr(settings, "PLUGINS_DIR", os.path.join(settings.BASE_DIR, "plugins"))
        if not os.path.exists(plugins_dir):
            os.makedirs(plugins_dir, exist_ok=True)
            return

        discovered_names = []
        for item in os.listdir(plugins_dir):
            item_path = os.path.join(plugins_dir, item)
            if os.path.isdir(item_path):
                manifest_path = os.path.join(item_path, "plugin.json")
                if os.path.exists(manifest_path):
                    try:
                        with open(manifest_path, "r", encoding="utf-8") as f:
                            raw_manifest = json.load(f)
                        manifest = validate_manifest(raw_manifest)
                        discovered_names.append(manifest.name)

                        # Sync with DB
                        plugin_record, created = Plugin.objects.get_or_create(
                            name=manifest.name,
                            defaults={
                                "display_name": manifest.display_name,
                                "version": manifest.version,
                                "api_version": manifest.api_version,
                                "description": manifest.description,
                                "author": manifest.author,
                                "is_active": False,
                                "manifest": raw_manifest,
                            }
                        )

                        if not created:
                            # Update metadata if changed
                            plugin_record.display_name = manifest.display_name
                            plugin_record.version = manifest.version
                            plugin_record.api_version = manifest.api_version
                            plugin_record.description = manifest.description
                            plugin_record.author = manifest.author
                            plugin_record.manifest = raw_manifest
                            plugin_record.save()

                    except Exception as e:
                        logger.error(f"Failed to load plugin manifest from {item_path}: {e}")

        # Deactivate plugins in DB if they are missing from disk.
        Plugin.objects.exclude(name__in=discovered_names).update(is_active=False)

    def load_active_plugins(self):
        """Loads and imports entrypoints of active plugins."""
        self.active_plugins.clear()
        self.loaded_modules.clear()
        
        from django.db import connection
        if "plugins_plugin" not in connection.introspection.table_names():
            return

        # Ensure PLUGINS_DIR is in sys.path
        plugins_dir = getattr(settings, "PLUGINS_DIR", os.path.join(settings.BASE_DIR, "plugins"))
        if plugins_dir not in sys.path:
            sys.path.insert(0, plugins_dir)

        active_records = Plugin.objects.filter(is_active=True)

        for record in active_records:
            try:
                manifest = validate_manifest(record.manifest)
                self.active_plugins[manifest.name] = manifest
                
                # Dynamic import of entry point if specified
                if manifest.entry_point:
                    module = importlib.import_module(manifest.entry_point)
                    self.loaded_modules[manifest.name] = module
                    logger.info(f"Loaded plugin: {manifest.name} ({manifest.version})")
            except Exception as e:
                logger.error(f"Failed to load active plugin {record.name}: {e}")

    def execute_hook(self, hook_name: str, *args, **kwargs):
        """Executes a registered hook handler in all active plugins."""
        results = []
        for name, manifest in self.active_plugins.items():
            if hook_name in manifest.hooks:
                handler_path = manifest.hooks[hook_name]
                try:
                    # Import the handler function dynamically
                    module_path, func_name = handler_path.rsplit(".", 1)
                    # Prepend entry point module name if relative
                    if manifest.entry_point and not module_path.startswith(manifest.entry_point):
                        module_path = f"{manifest.entry_point}.{module_path}"
                    module = importlib.import_module(module_path)
                    handler = getattr(module, func_name)
                    res = handler(*args, **kwargs)
                    results.append((name, res))
                except Exception as e:
                    logger.error(f"Error executing hook '{hook_name}' in plugin '{name}': {e}")
        return results

# Global registry instance
registry = PluginRegistry()
