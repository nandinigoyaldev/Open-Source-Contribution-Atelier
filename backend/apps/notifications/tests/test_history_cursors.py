from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db


@pytest.fixture
def history():
    user = get_user_model().objects.create_user(username="cursor-owner")
    other = get_user_model().objects.create_user(username="cursor-other")
    client = APIClient()
    client.force_authenticate(user)
    rows = [
        Notification.objects.create(recipient=user, notif_type="badge", title=str(i))
        for i in range(7)
    ]
    # Equal timestamps force the second ordering key to do real pagination work.
    instant = timezone.now() - timedelta(days=1)
    Notification.objects.filter(pk__in=[row.pk for row in rows]).update(
        created_at=instant
    )
    Notification.objects.create(recipient=other, notif_type="badge", title="private")
    return client, user, other, rows, instant


def follow(client, url):
    parsed = urlsplit(url)
    return client.get(parsed.path + "?" + parsed.query)


def test_legacy_page_number_envelope_is_unchanged(history):
    client, _, _, rows, _ = history
    response = client.get(reverse("notification-list"), {"page_size": 3})
    assert response.status_code == 200
    assert set(response.data) == {"count", "next", "previous", "results"}
    assert response.data["count"] == 7
    assert [r["id"] for r in response.data["results"]] == [r.pk for r in rows[-3:]][
        ::-1
    ]
    assert follow(client, response.data["next"]).status_code == 200


def test_cursor_walk_does_not_repeat_or_skip_ties_after_new_insert(history):
    client, user, _, rows, instant = history
    response = client.get(
        reverse("notification-list"), {"pagination": "cursor", "page_size": 3}
    )
    assert response.status_code == 200
    assert response.data["next_cursor"]
    assert parse_qs(urlsplit(response.data["next"]).query)["cursor"] == [
        response.data["next_cursor"]
    ]
    seen = [r["id"] for r in response.data["results"]]
    newer = Notification.objects.create(recipient=user, notif_type="badge", title="new")
    tied = Notification.objects.create(recipient=user, notif_type="badge", title="tie")
    Notification.objects.filter(pk=tied.pk).update(created_at=instant)
    while response.data["next"]:
        response = follow(client, response.data["next"])
        assert response.status_code == 200
        seen.extend(r["id"] for r in response.data["results"])
    assert seen == [r.pk for r in reversed(rows)]
    assert newer.pk not in seen and tied.pk not in seen
    assert response.data["next_cursor"] is None
    assert response.data["previous"] is None


def test_deleting_boundary_row_does_not_invalidate_continuation(history):
    client, _, _, rows, _ = history
    response = client.get(
        reverse("notification-list"), {"pagination": "cursor", "page_size": 3}
    )
    Notification.objects.filter(pk=rows[-3].pk).delete()
    response = follow(client, response.data["next"])
    assert response.status_code == 200
    assert [r["id"] for r in response.data["results"]] == [r.pk for r in rows[1:4]][
        ::-1
    ]


@pytest.mark.parametrize("cursor", ["", "not-a-cursor", "a" * 2049])
def test_invalid_cursor_is_clear_validation_error(history, cursor):
    client, *_ = history
    response = client.get(reverse("notification-list"), {"cursor": cursor})
    assert response.status_code == 400
    assert "cursor" in response.data["errors"]


def test_tampered_and_other_user_cursors_are_rejected(history):
    client, _, other, _, _ = history
    response = client.get(
        reverse("notification-list"), {"pagination": "cursor", "page_size": 3}
    )
    cursor = response.data["next_cursor"]
    assert (
        client.get(reverse("notification-list"), {"cursor": cursor + "x"}).status_code
        == 400
    )
    client.force_authenticate(other)
    assert (
        client.get(reverse("notification-list"), {"cursor": cursor}).status_code == 400
    )


@pytest.mark.parametrize("page_size", ["0", "-1", "many", "1.5"])
def test_cursor_page_size_validation(history, page_size):
    client, *_ = history
    response = client.get(
        reverse("notification-list"), {"pagination": "cursor", "page_size": page_size}
    )
    assert response.status_code == 400
    assert "page_size" in response.data["errors"]


def test_cursor_queries_are_bounded_without_count_or_offset(history):
    client, *_ = history
    with CaptureQueriesContext(connection) as captured:
        response = client.get(
            reverse("notification-list"), {"pagination": "cursor", "page_size": 3}
        )
    assert response.status_code == 200
    queries = [
        q["sql"] for q in captured if 'FROM "notifications_notification"' in q["sql"]
    ]
    assert len(queries) == 1
    assert "LIMIT 4" in queries[0]
    assert "COUNT(" not in queries[0] and "OFFSET" not in queries[0]


def test_cursor_caps_client_page_size(history):
    client, user, *_ = history
    Notification.objects.bulk_create(
        [
            Notification(recipient=user, notif_type="badge", title=str(i))
            for i in range(105)
        ]
    )
    response = client.get(
        reverse("notification-list"), {"pagination": "cursor", "page_size": 1000000}
    )
    assert response.status_code == 200
    assert len(response.data["results"]) == 100
    assert response.data["next_cursor"]


def test_cursor_empty_history_and_authentication(history):
    client, user, *_ = history
    Notification.objects.filter(recipient=user).delete()
    response = client.get(reverse("notification-list"), {"pagination": "cursor"})
    assert response.status_code == 200
    assert response.data == {
        "next": None,
        "previous": None,
        "next_cursor": None,
        "results": [],
    }
    assert (
        APIClient()
        .get(reverse("notification-list"), {"pagination": "cursor"})
        .status_code
        == 401
    )
