from copy import deepcopy
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from apps.content.management.commands.seed_lessons import CURRICULUM_LESSONS
from apps.content.management.commands.verify_seed_data import DASHBOARD_LESSONS
from apps.content.models import Exercise, Lesson
from apps.dashboard.models import PullRequest

pytestmark = pytest.mark.django_db


def verify(scope="all"):
    stdout, stderr = StringIO(), StringIO()
    call_command("verify_seed_data", scope=scope, stdout=stdout, stderr=stderr)
    return stdout.getvalue(), stderr.getvalue()


@pytest.fixture
def curriculum():
    before = deepcopy(CURRICULUM_LESSONS)
    call_command("seed_lessons", stdout=StringIO())
    assert CURRICULUM_LESSONS == before


@pytest.fixture
def dashboard():
    call_command("seed_dashboard", stdout=StringIO())


def test_real_seed_commands_pass_together_and_verification_is_read_only(
    curriculum, dashboard
):
    def read_only(execute, sql, params, many, context):
        assert sql.lstrip().upper().startswith("SELECT"), sql
        return execute(sql, params, many, context)

    with connection.execute_wrapper(read_only):
        for _ in range(2):
            out, err = verify()
            assert "passed (all)" in out
            assert not err


def test_empty_database_lists_missing_invariants_and_fails():
    err = StringIO()
    with pytest.raises(CommandError, match="No records were changed"):
        call_command("verify_seed_data", stdout=StringIO(), stderr=err)
    assert (
        f"lesson {CURRICULUM_LESSONS[0]['slug']}: expected 1, found 0" in err.getvalue()
    )
    assert "dashboard user alice" in err.getvalue()


def test_curriculum_scope_does_not_require_dashboard(curriculum):
    assert "passed (curriculum)" in verify("curriculum")[0]


def test_dashboard_scope_does_not_require_curriculum(dashboard):
    assert "passed (dashboard)" in verify("dashboard")[0]


@pytest.mark.parametrize("copies", [0, 2])
def test_missing_or_duplicate_exercise_is_reported(curriculum, copies):
    slug = CURRICULUM_LESSONS[0]["slug"]
    exercise = Exercise.objects.get(lesson__slug=slug)
    title = exercise.title
    if copies == 0:
        exercise.delete()
    else:
        exercise.pk = None
        exercise.save()
    err = StringIO()
    with pytest.raises(CommandError):
        call_command("verify_seed_data", scope="curriculum", stderr=err)
    assert f"exercise {slug}/{title}: expected 1, found {copies}" in err.getvalue()


def test_missing_lesson_is_not_silently_recreated(curriculum):
    slug = CURRICULUM_LESSONS[0]["slug"]
    Lesson.objects.filter(slug=slug).delete()
    with pytest.raises(CommandError):
        verify("curriculum")
    assert not Lesson.objects.filter(slug=slug).exists()


def test_dashboard_invalid_relationship_is_reported(dashboard):
    PullRequest.objects.filter(title="feat: solve dark mode contrast issues").update(
        issue=None
    )
    err = StringIO()
    with pytest.raises(CommandError):
        call_command("verify_seed_data", scope="dashboard", stderr=err)
    assert "merged demo PR" in err.getvalue()


def test_extra_unrelated_lesson_is_allowed(curriculum):
    Lesson.objects.create(slug="contributor-extra", title="Extra")
    assert "passed" in verify("curriculum")[0]


def test_dashboard_missing_exercise_is_reported(dashboard):
    slug = DASHBOARD_LESSONS[0][0]
    Exercise.objects.filter(lesson__slug=slug).delete()
    with pytest.raises(CommandError):
        verify("dashboard")


def test_seeding_twice_preserves_curriculum_definitions(curriculum):
    before = deepcopy(CURRICULUM_LESSONS)
    call_command("seed_lessons", stdout=StringIO())
    assert CURRICULUM_LESSONS == before
    assert "passed" in verify("curriculum")[0]
