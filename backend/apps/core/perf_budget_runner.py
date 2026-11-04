"""Fixed dataset and request loop for the API latency performance budget.

``seed_dataset`` builds the same rows every time (no randomness, no clock in
the data), ``measure`` calls each route through the Django test client. Both
need a database, so the comparison logic lives in ``perf_budget`` instead.
"""

from __future__ import annotations

import gc
import time
from dataclasses import dataclass
from typing import Dict, List, Sequence

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from rest_framework.test import APIClient

from apps.content.models import Lesson
from apps.progress.models import LessonProgress, XPEvent

from .perf_budget import RouteResult, summarize

USER_COUNT = 50
LESSON_COUNT = 60
COMPLETED_PER_USER = 3
XP_EVENTS_PER_USER = 5
PREFIX = "perf-budget"

DATASET_DESCRIPTION = (
    f"{USER_COUNT} users, {LESSON_COUNT} lessons, "
    f"{USER_COUNT * COMPLETED_PER_USER} completed lesson progress rows, "
    f"{USER_COUNT * XP_EVENTS_PER_USER} XP events"
)

_DIFFICULTIES = ("beginner", "intermediate", "advanced")
_CATEGORIES = ("git", "github", "collaboration", "workflow")


@dataclass(frozen=True)
class Route:
    """A representative GET route. ``{lesson_id}`` is filled in from the dataset."""

    name: str
    path: str


# Short on purpose: each route is hit (warmup + runs) times. Add a route here
# and run `perf_budget_report --update-budget --reason "..."` to give it a budget.
ROUTES: Sequence[Route] = (
    Route("health-legacy", "/health/legacy/"),
    Route("lessons-list", "/api/content/published-lessons/"),
    Route("lesson-detail", "/api/content/published-lessons/{lesson_id}/"),
    Route("leaderboard", "/api/leaderboard/"),
    Route("content-search", "/api/content/search/?q=lesson"),
    Route("learning-paths", "/api/content/learning-paths/"),
    Route("progress-badges", "/api/progress/badges/"),
)


def seed_dataset() -> Dict[str, int]:
    """Create the fixed dataset and return ``{"lesson_id": ..., "user_id": ...}``.

    Everything is derived from the loop index, so two runs build identical rows.
    If this dataset is already in the database (``--current-db`` run twice) it is
    reused instead of being created again.
    """
    user_model = get_user_model()
    if Lesson.objects.filter(slug__startswith=PREFIX).exists():
        return {
            "lesson_id": Lesson.objects.filter(slug__startswith=PREFIX)
            .order_by("order")
            .values_list("pk", flat=True)[0],
            "user_id": user_model.objects.filter(username__startswith=PREFIX)
            .order_by("id")
            .values_list("pk", flat=True)[0],
        }

    user_model.objects.bulk_create(
        [
            user_model(
                username=f"{PREFIX}-user-{i:03d}",
                email=f"{PREFIX}-user-{i:03d}@perf.test",
            )
            for i in range(USER_COUNT)
        ]
    )
    users = list(user_model.objects.filter(username__startswith=PREFIX).order_by("id"))

    Lesson.objects.bulk_create(
        [
            Lesson(
                title=f"Perf lesson {i:03d}",
                slug=f"{PREFIX}-lesson-{i:03d}",
                summary=f"Summary for perf lesson {i:03d}",
                content=(f"Body of perf lesson {i:03d}. " * 40).strip(),
                difficulty=_DIFFICULTIES[i % len(_DIFFICULTIES)],
                category=_CATEGORIES[i % len(_CATEGORIES)],
                estimated_minutes=5 + i % 20,
                order=i,
                learning_objectives=[f"Objective {i}.1", f"Objective {i}.2"],
            )
            for i in range(LESSON_COUNT)
        ]
    )
    lessons = list(Lesson.objects.filter(slug__startswith=PREFIX).order_by("order"))

    progress: List[LessonProgress] = []
    events: List[XPEvent] = []
    for u, user in enumerate(users):
        for k in range(COMPLETED_PER_USER):
            lesson = lessons[(u + k) % LESSON_COUNT]
            score = 10 * (1 + (u * 7 + k * 3) % 10)
            progress.append(
                LessonProgress(
                    user=user,
                    lesson=lesson,
                    completed=True,
                    score=score,
                    base_score=score,
                    attempt_count=1,
                )
            )
        for k in range(XP_EVENTS_PER_USER):
            points = 10 * (1 + (u + k) % 5)
            events.append(
                XPEvent(
                    user=user,
                    source_type="lesson",
                    base_points=points,
                    xp_delta=points,
                )
            )
    LessonProgress.objects.bulk_create(progress)
    XPEvent._default_manager.bulk_create(events)
    return {"lesson_id": lessons[0].pk, "user_id": users[0].pk}


def measure(
    context: Dict[str, int],
    runs: int,
    warmup: int,
    routes: Sequence[Route] = ROUTES,
) -> List[RouteResult]:
    """Hit every route ``warmup + runs`` times and summarize the last ``runs``.

    Requests go round robin (route A, B, C, A, B, C, ...) so a slow moment on
    the machine hits every route about equally instead of landing on one. The
    cache is cleared before each request so every sample is the cold path, and
    the garbage collector is paused while the clock is running.
    """
    user = get_user_model().objects.get(pk=context["user_id"])
    client = APIClient(raise_request_exception=False)
    client.force_authenticate(user=user)

    paths = [route.path.format(**context) for route in routes]
    timings: List[List[float]] = [[] for _ in routes]
    queries: List[List[int]] = [[] for _ in routes]
    status: List[int] = [0 for _ in routes]

    counter = _QueryCounter()
    gc.collect()
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        for i in range(warmup + runs):
            for idx, path in enumerate(paths):
                cache.clear()
                counter.count = 0
                with connection.execute_wrapper(counter):
                    start = time.perf_counter()
                    response = client.get(path, HTTP_HOST="localhost")
                    elapsed_ms = (time.perf_counter() - start) * 1000
                status[idx] = int(getattr(response, "status_code", 0))
                if i >= warmup:
                    timings[idx].append(elapsed_ms)
                    queries[idx].append(counter.count)
    finally:
        if gc_was_enabled:
            gc.enable()

    return [
        summarize(route.name, path, status[idx], timings[idx], queries[idx])
        for idx, (route, path) in enumerate(zip(routes, paths))
    ]


class _QueryCounter:
    """``connection.execute_wrapper`` hook that only counts statements."""

    def __init__(self) -> None:
        self.count = 0

    def __call__(self, execute, sql, params, many, context):
        self.count += 1
        return execute(sql, params, many, context)
