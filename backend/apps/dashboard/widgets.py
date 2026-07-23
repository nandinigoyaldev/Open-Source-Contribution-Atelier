from dataclasses import dataclass
from typing import List, Callable


@dataclass
class WidgetDefinition:
    id: str
    title: str
    description: str
    default_width: int = 4
    default_height: int = 3
    icon: str = "📊"
    permissions: List[str] = None


class WidgetRegistry:
    """Registry for dashboard widgets."""

    _widgets = {}

    @classmethod
    def register(cls, widget_def: WidgetDefinition):
        cls._widgets[widget_def.id] = widget_def

    @classmethod
    def get_all(cls):
        return list(cls._widgets.values())

    @classmethod
    def get(cls, widget_id: str):
        return cls._widgets.get(widget_id)


# Register default widgets
WidgetRegistry.register(
    WidgetDefinition(
        id="streak-calendar",
        title="Streak Calendar",
        description="Track your daily learning streak",
        default_width=4,
        default_height=3,
        icon="🔥",
    )
)

WidgetRegistry.register(
    WidgetDefinition(
        id="xp-breakdown",
        title="XP Breakdown",
        description="See where your XP comes from",
        default_width=4,
        default_height=3,
        icon="⭐",
    )
)

WidgetRegistry.register(
    WidgetDefinition(
        id="recent-activity",
        title="Recent Activity",
        description="Your latest actions on the platform",
        default_width=4,
        default_height=3,
        icon="📋",
    )
)

WidgetRegistry.register(
    WidgetDefinition(
        id="lesson-recommendations",
        title="Lesson Recommendations",
        description="Personalized lesson suggestions",
        default_width=4,
        default_height=3,
        icon="📚",
    )
)

WidgetRegistry.register(
    WidgetDefinition(
        id="leaderboard-position",
        title="Leaderboard Position",
        description="Your rank among contributors",
        default_width=3,
        default_height=2,
        icon="🏆",
    )
)

WidgetRegistry.register(
    WidgetDefinition(
        id="badge-showcase",
        title="Badge Showcase",
        description="Your earned badges",
        default_width=4,
        default_height=3,
        icon="🏅",
    )
)

WidgetRegistry.register(
    WidgetDefinition(
        id="quick-actions",
        title="Quick Actions",
        description="Continue learning, start challenge",
        default_width=3,
        default_height=2,
        icon="⚡",
    )
)
