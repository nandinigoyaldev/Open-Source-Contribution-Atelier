import logging
from typing import Dict, Any, Type

logger = logging.getLogger(__name__)


class LessonPlugin:
    """
    Abstract base class for all lesson plugins.
    Defines the standardized interface that new lesson types must implement.
    """

    identifier: str = ""
    version: str = "1.0"
    name: str = ""
    description: str = ""

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Return plugin metadata for frontend rendering and configuration."""
        return {
            "identifier": cls.identifier,
            "version": cls.version,
            "name": cls.name,
            "description": cls.description,
        }

    @classmethod
    def validate_submission(cls, data: Dict[str, Any]) -> bool:
        """
        Validation rules for this specific lesson type.
        """
        return True

    @classmethod
    def evaluate_progress(cls, user, data: Dict[str, Any]) -> float:
        """
        Progress evaluation logic, returning completion percentage (0.0 to 100.0).
        """
        return 100.0


class LessonPluginRegistry:
    """
    Registry for dynamically discovering and loading lesson plugins.
    Implements the Factory and Strategy patterns for lesson execution.
    """

    def __init__(self):
        self._plugins: Dict[str, Type[LessonPlugin]] = {}

    def register(self, plugin_class: Type[LessonPlugin]):
        if not issubclass(plugin_class, LessonPlugin):
            logger.error(
                f"Failed to load plugin: {plugin_class} must inherit from LessonPlugin"
            )
            return

        identifier = plugin_class.identifier
        if not identifier:
            logger.error(
                f"Failed to load plugin: {plugin_class} is missing an identifier"
            )
            return

        self._plugins[identifier] = plugin_class
        logger.info(
            f"Successfully registered lesson plugin: {identifier} (v{plugin_class.version})"
        )

    def get_plugin(self, identifier: str) -> Type[LessonPlugin]:
        """Retrieve a specific plugin with graceful fallback behavior."""
        plugin = self._plugins.get(identifier)
        if not plugin:
            logger.warning(f"Plugin '{identifier}' is not supported or not loaded.")
        return plugin

    def get_all_plugins(self) -> Dict[str, Type[LessonPlugin]]:
        return self._plugins


# Global registry instance
registry = LessonPluginRegistry()
