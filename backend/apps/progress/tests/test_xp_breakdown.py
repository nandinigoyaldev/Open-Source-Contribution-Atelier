from unittest.mock import MagicMock, patch

from rest_framework.test import APIRequestFactory, force_authenticate

from apps.progress.views import XPBreakdownView


def _get(rows):
    request = APIRequestFactory().get("/api/progress/xp-breakdown/")
    force_authenticate(request, user=MagicMock(is_authenticated=True))
    with patch("apps.progress.views.XPEvent") as event:
        qs = event.objects.filter.return_value.values_list.return_value
        qs.annotate.return_value = rows
        return XPBreakdownView.as_view()(request)


def test_groups_sources_into_categories():
    response = _get([("lesson", 100), ("exercise", 30), ("bounty", 20), ("pr", 50)])
    assert response.status_code == 200
    xp = {c["key"]: c["xp"] for c in response.data["categories"]}
    assert xp == {
        "lessons": 100,
        "quizzes": 0,
        "challenges": 50,
        "streaks": 0,
        "community": 50,
    }
    assert response.data["total_xp"] == 200


def test_other_sources_keep_total_consistent():
    response = _get([("lesson", 10), ("badge", 25)])
    keys = [c["key"] for c in response.data["categories"]]
    assert keys[-1] == "other"
    assert response.data["total_xp"] == 35


def test_empty_user_has_zero_total():
    response = _get([])
    assert response.data["total_xp"] == 0
    assert all(c["xp"] == 0 for c in response.data["categories"])


def test_requires_authentication():
    request = APIRequestFactory().get("/api/progress/xp-breakdown/")
    assert XPBreakdownView.as_view()(request).status_code in (401, 403)
