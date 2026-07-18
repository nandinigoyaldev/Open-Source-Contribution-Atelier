import importlib
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, AllowAny
from .models import Plugin
from .registry import registry

logger = logging.getLogger(__name__)

class PluginListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        registry.discover_and_sync()
        plugins = Plugin.objects.all()
        data = []
        for p in plugins:
            data.append({
                "name": p.name,
                "display_name": p.display_name,
                "version": p.version,
                "api_version": p.api_version,
                "description": p.description,
                "author": p.author,
                "is_active": p.is_active,
                "manifest": p.manifest,
            })
        return Response(data)

class PluginToggleView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, plugin_name):
        try:
            plugin = Plugin.objects.get(name=plugin_name)
        except Plugin.DoesNotExist:
            return Response({"error": "Plugin not found"}, status=404)

        plugin.is_active = not plugin.is_active
        plugin.save()
        
        # Reload active plugins in registry
        registry.load_active_plugins()
        
        return Response({
            "name": plugin.name,
            "is_active": plugin.is_active,
            "message": f"Plugin '{plugin.display_name}' has been {'enabled' if plugin.is_active else 'disabled'}."
        })

class DynamicPluginRouterView(APIView):
    permission_classes = [AllowAny]

    def dispatch(self, request, plugin_name, subpath="", *args, **kwargs):
        manifest = registry.active_plugins.get(plugin_name)
        if not manifest:
            return Response({"error": f"Plugin '{plugin_name}' is not installed or active."}, status=404)

        matched_view_path = None
        subpath_norm = subpath.strip("/")
        for pattern, path in manifest.views.items():
            if pattern.strip("/") == subpath_norm:
                matched_view_path = path
                break

        if not matched_view_path:
            return Response({"error": f"Endpoint '{subpath}' not found in plugin '{plugin_name}'."}, status=404)

        try:
            module_path, view_name = matched_view_path.rsplit(".", 1)
            if manifest.entry_point and not module_path.startswith(manifest.entry_point):
                module_path = f"{manifest.entry_point}.{module_path}"
            module = importlib.import_module(module_path)
            view_cls = getattr(module, view_name)
            
            if hasattr(view_cls, "as_view"):
                return view_cls.as_view()(request, *args, **kwargs)
            else:
                return view_cls(request, *args, **kwargs)
        except Exception as e:
            logger.exception(f"Error executing plugin view '{matched_view_path}': {e}")
            return Response({"error": f"Plugin view execution error: {str(e)}"}, status=500)
