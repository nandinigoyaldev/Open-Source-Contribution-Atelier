"""
Generate dependency graphs for Django apps.
"""

import os
import re
import ast
import json
from pathlib import Path
from typing import Dict, List, Set, Any, Optional
from django.apps import apps
from django.conf import settings
import importlib


class DependencyGraphGenerator:
    """
    Generate dependency graphs showing relationships between Django components.
    """

    def __init__(self):
        self.nodes = []
        self.edges = []
        self.apps_data = {}

    def scan_all_apps(self):
        """Scan all Django apps and their components."""
        for app_config in apps.get_app_configs():
            app_name = app_config.name
            if app_name.startswith("django.") or app_name.startswith("apps."):
                continue

            self.apps_data[app_name] = {
                "name": app_name,
                "label": app_config.verbose_name or app_name,
                "path": str(app_config.path),
                "models": [],
                "serializers": [],
                "views": [],
                "signals": [],
                "tasks": [],
                "urls": [],
                "dependencies": set(),
            }

            # Scan components
            self._scan_models(app_name)
            self._scan_serializers(app_name)
            self._scan_views(app_name)
            self._scan_signals(app_name)
            self._scan_tasks(app_name)
            self._scan_urls(app_name)

    def _scan_models(self, app_name: str):
        """Scan models in an app."""
        try:
            module = importlib.import_module(f"{app_name}.models")
            for name, obj in module.__dict__.items():
                if (
                    hasattr(obj, "__module__")
                    and obj.__module__ == f"{app_name}.models"
                ):
                    if hasattr(obj, "_meta") and hasattr(obj._meta, "model_name"):
                        self.apps_data[app_name]["models"].append(name)

                        # Find foreign key dependencies
                        for field in obj._meta.get_fields():
                            if field.is_relation and field.related_model:
                                if hasattr(field.related_model, "_meta"):
                                    related_app = field.related_model._meta.app_label
                                    if related_app != app_name:
                                        self.apps_data[app_name]["dependencies"].add(
                                            related_app
                                        )
        except (ImportError, AttributeError):
            pass

    def _scan_serializers(self, app_name: str):
        """Scan serializers in an app."""
        try:
            module = importlib.import_module(f"{app_name}.serializers")
            for name, obj in module.__dict__.items():
                if (
                    hasattr(obj, "__module__")
                    and obj.__module__ == f"{app_name}.serializers"
                ):
                    if hasattr(obj, "Meta") and hasattr(obj.Meta, "model"):
                        self.apps_data[app_name]["serializers"].append(name)
        except (ImportError, AttributeError):
            pass

    def _scan_views(self, app_name: str):
        """Scan views in an app."""
        try:
            module = importlib.import_module(f"{app_name}.views")
            for name, obj in module.__dict__.items():
                if hasattr(obj, "__module__") and obj.__module__ == f"{app_name}.views":
                    if hasattr(obj, "as_view") or hasattr(obj, "get"):
                        self.apps_data[app_name]["views"].append(name)
        except (ImportError, AttributeError):
            pass

    def _scan_signals(self, app_name: str):
        """Scan signals in an app."""
        try:
            module = importlib.import_module(f"{app_name}.signals")
            for name, obj in module.__dict__.items():
                if (
                    hasattr(obj, "__module__")
                    and obj.__module__ == f"{app_name}.signals"
                ):
                    self.apps_data[app_name]["signals"].append(name)
        except (ImportError, AttributeError):
            pass

    def _scan_tasks(self, app_name: str):
        """Scan Celery tasks in an app."""
        try:
            module = importlib.import_module(f"{app_name}.tasks")
            for name, obj in module.__dict__.items():
                if hasattr(obj, "__module__") and obj.__module__ == f"{app_name}.tasks":
                    if hasattr(obj, "delay") or hasattr(obj, "apply_async"):
                        self.apps_data[app_name]["tasks"].append(name)
        except (ImportError, AttributeError):
            pass

    def _scan_urls(self, app_name: str):
        """Scan URLs in an app."""
        try:
            module = importlib.import_module(f"{app_name}.urls")
            if hasattr(module, "urlpatterns"):
                self.apps_data[app_name]["urls"].append("urlpatterns")
        except (ImportError, AttributeError):
            pass

    def build_graph(self) -> Dict[str, Any]:
        """Build the dependency graph."""
        self.scan_all_apps()

        # Build nodes
        nodes = []
        for app_name, data in self.apps_data.items():
            nodes.append(
                {
                    "id": app_name,
                    "label": data["label"],
                    "models": len(data["models"]),
                    "serializers": len(data["serializers"]),
                    "views": len(data["views"]),
                    "signals": len(data["signals"]),
                    "tasks": len(data["tasks"]),
                    "urls": len(data["urls"]),
                }
            )

        # Build edges
        edges = []
        for app_name, data in self.apps_data.items():
            for dep in data["dependencies"]:
                if dep in self.apps_data:
                    edges.append(
                        {
                            "source": app_name,
                            "target": dep,
                        }
                    )

        return {
            "nodes": nodes,
            "edges": edges,
            "total_apps": len(nodes),
            "total_edges": len(edges),
        }
