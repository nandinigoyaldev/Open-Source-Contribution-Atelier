# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportOperatorIssue=false, reportReturnType=false, reportGeneralTypeIssues=false, reportOptionalSubscript=false, reportOptionalMemberAccess=false
# (Django model/field types are unresolved without stubs; these rules are noise here.)
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from rest_framework.test import APIClient

from apps.accounts.models import UserProfile
from apps.progress.models import AdaptiveAttempt, ChallengeRating
from apps.progress.services import adaptive_difficulty as adaptive
from apps.progress.services.adaptive_difficulty import Rating
from apps.sandbox.models import ConflictAttempt, ConflictScenario

User = get_user_model()

NOW = datetime(2026, 9, 9, 12, 0, tzinfo=dt_timezone.utc)
KIND = "merge_conflict"
SETTINGS_URL = "/api/progress/adaptive-difficulty/"


@pytest.fixture
def learner(db):
    return User.objects.create_user(username="adaptive", password="pw123456!")


@pytest.fixture
def opted_in(learner):
    adaptive.set_enabled(learner, True)
    return learner


@pytest.fixture
def client(learner):
    api = APIClient()
    api.force_authenticate(user=learner)
    return api


@pytest.fixture
def clock():
    with patch("django.utils.timezone.now", return_value=NOW) as mocked:
        yield mocked


def scenario(name="one", difficulty="intermediate"):
    return ConflictScenario.objects.create(
        title=name,
        description="resolve it",
        difficulty=difficulty,
        base_code="a\nb\nc",
        current_code="a\nours\nc",
        incoming_code="a\ntheirs\nc",
        expected_resolution="a\nboth\nc",
        hint="Keep both changes.",
    )


def url(item, action=""):
    base = f"/api/sandbox/conflict-scenarios/{item.pk}/"
    return f"{base}{action}/" if action else base


def profile(user):
    return UserProfile.objects.get(user=user)


def submit(user, item, solved=True):
    return adaptive.record_submission(
        user, KIND, item.pk, solved=solved, difficulty=item.difficulty
    )


# -- rating maths -------------------------------------------------------------


def test_glicko2_matches_the_worked_example_in_the_paper():
    player = Rating(1500, 200, 0.06)
    games = [
        (Rating(1400, 30, 0.06), 1.0),
        (Rating(1550, 100, 0.06), 0.0),
        (Rating(1700, 300, 0.06), 0.0),
    ]

    result = adaptive.glicko2_update(player, games, tau=0.5)

    assert result.rating == pytest.approx(1464.06, abs=0.01)
    assert result.deviation == pytest.approx(151.52, abs=0.01)
    assert result.volatility == pytest.approx(0.05999, abs=0.00001)


def test_glicko2_without_games_only_grows_the_deviation():
    result = adaptive.glicko2_update(Rating(1600, 100, 0.06), [])

    assert result.rating == 1600
    assert 100 < result.deviation < 101


def test_glicko2_handles_a_very_surprising_result():
    underdog = Rating(800, 60, 0.06)

    result = adaptive.glicko2_update(underdog, [(Rating(2400, 60, 0.06), 1.0)])

    assert result.rating > 800
    assert result.volatility > 0


@pytest.mark.parametrize(
    "kwargs,expected",
    [
        ({"solved": False}, 0.0),
        ({"solved": True}, 1.0),
        ({"solved": True, "time_spent": 600, "target_seconds": 600}, 1.0),
        ({"solved": True, "time_spent": 900, "target_seconds": 600}, 0.875),
        ({"solved": True, "time_spent": 9000, "target_seconds": 600}, 0.75),
        ({"solved": True, "hints_used": 1}, 0.25),
        ({"solved": True, "hints_used": 3}, 0.1),
    ],
)
def test_performance_score(kwargs, expected):
    assert adaptive.performance_score(**kwargs) == pytest.approx(expected)


# -- parameters ---------------------------------------------------------------


@pytest.mark.parametrize(
    "rating,level",
    [(1000, "guided"), (1399, "guided"), (1400, "standard"), (1650, "expert")],
)
def test_scaffolding_level(rating, level):
    assert adaptive.scaffolding_level(rating) == level


def test_higher_levels_get_less_help_and_a_tighter_bonus():
    guided, standard, expert = (
        adaptive.challenge_parameters(level, "intermediate")
        for level in ("guided", "standard", "expert")
    )

    assert guided["hint_auto_reveal_after_seconds"] == 60
    assert standard["hint_auto_reveal_after_seconds"] == 240
    assert expert["hint_auto_reveal_after_seconds"] is None
    assert [p["bonus_criteria"]["max_seconds"] for p in (guided, standard, expert)] == [
        600,
        450,
        300,
    ]


def test_starter_code_by_level():
    current, incoming = "a\nours\nc", "a\ntheirs\nc"

    assert adaptive.starter_code("guided", current, incoming) == (
        "a\n<<<<<<< HEAD\nours\n=======\ntheirs\n>>>>>>> incoming\nc"
    )
    assert adaptive.starter_code("standard", current, incoming) == current
    assert adaptive.starter_code("expert", current, incoming) == ""


# -- rating updates -----------------------------------------------------------


def test_three_quick_successes_raise_the_rating_each_time(opted_in, clock):
    ratings = [1500.0]
    for index in range(3):
        item = scenario(f"s{index}")
        clock.return_value = NOW
        adaptive.start_challenge(opted_in, KIND, item.pk)
        clock.return_value = NOW + timedelta(seconds=60)
        result = submit(opted_in, item)
        assert result["rated"] and result["bonus_met"]
        ratings.append(result["skill_rating"])

    assert ratings == sorted(ratings)
    assert len(set(ratings)) == 4
    saved = profile(opted_in)
    assert saved.skill_rating == pytest.approx(ratings[-1])
    assert saved.rating_deviation < 350
    assert adaptive.scaffolding_level(saved.skill_rating) == "expert"


def test_repeated_hints_lower_the_rating_and_add_scaffolding(opted_in):
    ratings = [1500.0]
    for index in range(3):
        item = scenario(f"h{index}")
        adaptive.start_challenge(opted_in, KIND, item.pk)
        adaptive.record_hint(opted_in, KIND, item.pk)
        ratings.append(submit(opted_in, item)["skill_rating"])

    assert ratings == sorted(ratings, reverse=True)
    assert ratings[-1] < 1400
    following = adaptive.start_challenge(opted_in, KIND, scenario("next").pk)
    assert following.level == "guided"


def test_failed_attempts_lower_the_rating_and_harden_the_challenge(opted_in):
    item = scenario()

    result = submit(opted_in, item, solved=False)

    assert result["rated"] and result["skill_rating"] < 1500
    assert ChallengeRating.objects.get(challenge_id=str(item.pk)).rating > 1500


def test_only_the_first_failures_are_rated(opted_in):
    item = scenario()
    results = [submit(opted_in, item, solved=False) for _ in range(5)]

    assert [r["rated"] for r in results] == [True, True, True, False, False]
    assert profile(opted_in).skill_rating == pytest.approx(results[2]["skill_rating"])
    assert AdaptiveAttempt.objects.get(user=opted_in).failed_attempts == 5
    # Solving after that still counts.
    assert submit(opted_in, item)["rated"]


def test_a_solved_challenge_cannot_be_farmed(opted_in):
    item = scenario()
    first = submit(opted_in, item)

    again = submit(opted_in, item)

    assert not again["rated"]
    assert profile(opted_in).skill_rating == pytest.approx(first["skill_rating"])
    assert ChallengeRating.objects.get().games == 1


def test_slow_solve_gains_less_than_a_quick_one(clock, db):
    gains = []
    for name, seconds in (("quick", 60), ("slow", 5000)):
        user = User.objects.create_user(username=name, password="pw123456!")
        adaptive.set_enabled(user, True)
        item = scenario(name)
        clock.return_value = NOW
        adaptive.start_challenge(user, KIND, item.pk)
        clock.return_value = NOW + timedelta(seconds=seconds)
        gains.append(submit(user, item)["skill_rating"])

    assert gains[0] > gains[1]


def test_reopening_does_not_reset_the_clock(opted_in, clock):
    item = scenario()
    adaptive.start_challenge(opted_in, KIND, item.pk)
    clock.return_value = NOW + timedelta(hours=1)

    attempt = adaptive.start_challenge(opted_in, KIND, item.pk)

    assert attempt.started_at == NOW


def test_clock_cannot_be_started_after_a_submission(opted_in):
    item = scenario()
    submit(opted_in, item, solved=False)

    assert adaptive.start_challenge(opted_in, KIND, item.pk).started_at is None
    assert not submit(opted_in, item)["bonus_met"]


def test_a_new_challenge_rating_starts_from_its_difficulty(opted_in):
    for difficulty in ("beginner", "advanced"):
        submit(opted_in, scenario(difficulty, difficulty))

    rows = {row.challenge_id: row.rating for row in ChallengeRating.objects.all()}
    easy = ConflictScenario.objects.get(title="beginner")
    hard = ConflictScenario.objects.get(title="advanced")
    # Both lost to the learner, so each sits a bit under its starting value.
    assert rows[str(easy.pk)] < 1300 < 1400 < rows[str(hard.pk)] < 1700


def test_opted_out_learners_are_not_tracked(learner):
    item = scenario()

    assert adaptive.start_challenge(learner, KIND, item.pk) is None
    adaptive.record_hint(learner, KIND, item.pk)
    assert submit(learner, item) is None

    assert not AdaptiveAttempt.objects.exists()
    assert not ChallengeRating.objects.exists()
    assert profile(learner).skill_rating == 1500


def test_submission_locks_the_rows_it_rates(opted_in):
    # SQLite ignores FOR UPDATE, so check that the lock is asked for.
    item = scenario()
    locked = []
    original = QuerySet.select_for_update

    def record(queryset, *args, **kwargs):
        locked.append(queryset.model)
        return original(queryset, *args, **kwargs)

    with patch.object(QuerySet, "select_for_update", record):
        submit(opted_in, item)

    assert locked == [UserProfile, AdaptiveAttempt, ChallengeRating]


# -- API ----------------------------------------------------------------------


def test_setting_is_off_by_default_and_can_be_toggled(client, learner):
    assert client.get(SETTINGS_URL).data == {
        "enabled": False,
        "skill_rating": 1500.0,
        "rating_deviation": 350.0,
        "level": "standard",
    }

    response = client.put(
        SETTINGS_URL, {"enabled": True, "skill_rating": 3000}, format="json"
    )

    assert response.status_code == 200 and response.data["enabled"] is True
    saved = profile(learner)
    assert saved.adaptive_difficulty_enabled
    assert saved.skill_rating == 1500  # read only


def test_setting_needs_a_boolean_and_a_login(client):
    assert client.put(SETTINGS_URL, {}, format="json").status_code == 400
    assert APIClient().get(SETTINGS_URL).status_code in (401, 403)


def test_profile_update_cannot_write_the_rating(client, learner):
    client.patch("/api/auth/me/", {"skill_rating": 3000, "bio": "hi"}, format="json")

    assert profile(learner).skill_rating == 1500


def test_opted_out_scenario_api_is_unchanged(client):
    item = scenario()

    assert client.get(url(item)).data["hint"] == "Keep both changes."
    started = client.post(url(item, "start")).data
    assert started == {"adaptive": None, "starter_code": item.current_code}
    response = client.post(
        url(item, "resolve_conflict"),
        {"submitted_code": item.expected_resolution},
        format="json",
    )
    assert response.status_code == 200
    assert "adaptive" not in response.data


def test_hint_is_hidden_until_asked_for(client, opted_in):
    item = scenario()
    assert client.get(url(item)).data["hint"] == ""

    assert client.post(url(item, "hint")).data == {"hint": "Keep both changes."}
    client.post(url(item, "hint"))

    assert client.get(url(item)).data["hint"] == "Keep both changes."
    assert AdaptiveAttempt.objects.get(user=opted_in).hints_used == 1


def test_full_flow_through_the_conflict_arena(client, opted_in):
    item = scenario()
    started = client.post(url(item, "start")).data
    assert started["adaptive"]["level"] == "standard"

    unresolved = client.post(
        url(item, "resolve_conflict"),
        {"submitted_code": "<<<<<<< HEAD\nours\n=======\ntheirs\n>>>>>>> x"},
        format="json",
    )
    assert unresolved.status_code == 400
    assert unresolved.data["adaptive"]["skill_rating"] < 1500

    solved = client.post(
        url(item, "resolve_conflict"),
        {"submitted_code": item.expected_resolution},
        format="json",
    )
    assert solved.status_code == 200
    assert solved.data["adaptive"]["rated"] is True
    assert solved.data["adaptive"]["bonus_met"] is True
    assert (
        solved.data["adaptive"]["skill_rating"]
        > unresolved.data["adaptive"]["skill_rating"]
    )
    assert ConflictAttempt.objects.filter(user=opted_in).count() == 2
    assert ChallengeRating.objects.get().games == 2
