"""Stable response snapshots for public lessons and signed-in notifications.

When an API change intentionally updates a contract, run this file with
`pytest -vv --showlocals`, review the reported normalized response against
frontend callers, and edit the matching scenario in pagination_contracts.json.
Keep generated identifiers, timestamps, hosts and opaque cursors out of fixtures.
"""

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import pytest
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from rest_framework.test import APIClient

from apps.content.models import Lesson
from apps.core.pagination import SecureCursorPagination
from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db
SNAPSHOTS = Path(__file__).with_name("pagination_contracts.json")


def link_contract(url):
    parts = urlsplit(url)
    query = parse_qs(parts.query, keep_blank_values=True)
    if "cursor" in query:
        assert len(query["cursor"]) == 1 and query["cursor"][0]
        query["cursor"] = ["<cursor>"]
    return {"path": parts.path, "query": query}


def item_contract(item):
    data = dict(item)
    if "id" in data:
        assert type(data["id"]) is int
        data["id"] = "<integer>"
    for key in ("created_at", "createdAt", "updated_at", "updatedAt"):
        if key in data:
            assert parse_datetime(data[key]) is not None
            data[key] = "<timestamp>"
    return data


def response_contract(response: HttpResponse):
    body = json.loads(response.content)
    if "correlation_id" in body:
        UUID(body["correlation_id"])
        body["correlation_id"] = "<uuid>"
    for key in ("next", "previous"):
        if key in body and body[key] is not None:
            body[key] = link_contract(body[key])
    for key in ("remaining", "total_estimate"):
        if key in body:
            # SQLite counts exactly, while PostgreSQL plans provide estimates.
            assert type(body[key]) is int and body[key] >= 0
            body[key] = "<non-negative integer>"
    if "results" in body:
        body["results"] = [item_contract(item) for item in body["results"]]
    return {"status": response.status_code, "body": body}


def get_page(client: APIClient, url: str, params=None) -> HttpResponse:
    response = client.get(url, params)
    assert isinstance(response, HttpResponse)
    return response


def follow(client: APIClient, link: str):
    parts = urlsplit(link)
    return get_page(
        client, f"{parts.path}?{parts.query}" if parts.query else parts.path
    )


def test_lesson_cursor_response_contract(monkeypatch):
    client = APIClient()
    url = reverse("lesson-list")
    monkeypatch.setattr(SecureCursorPagination, "page_size", 2)
    empty = get_page(client, url)
    for slug, title in (
        ("intro", "Introduction"),
        ("commit", "Commit"),
        ("push", "Push"),
    ):
        Lesson.objects.create(slug=slug, title=title, content="Sample lesson")
    first = get_page(client, url)
    last = follow(client, json.loads(first.content)["next"])
    invalid = get_page(client, url, {"cursor": "invalid"})
    actual = {
        key: response_contract(result)
        for key, result in (
            ("empty", empty),
            ("first", first),
            ("last", last),
            ("invalid", invalid),
        )
    }
    assert actual == json.loads(SNAPSHOTS.read_text(encoding="utf-8"))["lessons"]


def test_notification_page_response_contract():
    user = get_user_model().objects.create_user(username="contract-reader")
    client = APIClient()
    client.force_authenticate(user)
    url = reverse("notification-list")
    empty = get_page(client, url)
    for title in ("New badge", "Lesson completed", "New comment"):
        Notification.objects.create(recipient=user, notif_type="badge", title=title)
    first = get_page(client, url, {"page_size": 2})
    last = follow(client, json.loads(first.content)["next"])
    invalid = get_page(client, url, {"page": 99})
    actual = {
        key: response_contract(result)
        for key, result in (
            ("empty", empty),
            ("first", first),
            ("last", last),
            ("invalid", invalid),
        )
    }
    assert actual == json.loads(SNAPSHOTS.read_text(encoding="utf-8"))["notifications"]
