from typing import Any

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.content.models import Lesson, Organization
from apps.content.title_suggestions import (
    MAX_QUERY_LENGTH,
    MAX_SUGGESTIONS,
    edit_distance,
    rank_title_suggestions,
)

URL = "/api/content/search/suggestions/"

TITLES = [
    ("merge-conflicts", "Resolving Merge Conflicts"),
    ("pull-requests", "Opening a Pull Request"),
    ("rebase", "Interactive Rebase"),
]


def slugs(results):
    return [item["slug"] for item in results]


def search(query) -> Any:
    return APIClient().get(URL, {"q": query})


def make_lesson(slug, title, **extra):
    return Lesson.objects.create(
        slug=slug,
        title=title,
        summary="summary",
        content="content",
        difficulty="beginner",
        **extra,
    )


@pytest.mark.parametrize(
    "a, b, expected",
    [
        ("rebase", "rebase", 0),
        ("rebsae", "rebase", 1),
        ("rebas", "rebase", 1),
        ("rebasee", "rebase", 1),
        ("robose", "rebase", 2),
        ("merge", "rebase", 3),
    ],
)
def test_edit_distance_is_capped_at_limit_plus_one(a, b, expected):
    assert edit_distance(a, b, 2) == expected


@pytest.mark.parametrize(
    "query, slug",
    [
        ("merge conflcit", "merge-conflicts"),
        ("pul reqest", "pull-requests"),
        ("Interactve rebsae", "rebase"),
    ],
)
def test_misspelled_title_is_suggested(query, slug):
    results = rank_title_suggestions(query, TITLES)

    assert slugs(results) == [slug]
    assert results[0]["kind"] == "suggestion"


@pytest.mark.parametrize("query", ["Interactive Rebase", "rebase", "merge conf"])
def test_no_suggestions_when_a_title_matches_directly(query):
    assert rank_title_suggestions(query, TITLES) == []


def test_exact_title_suppresses_look_alike_guesses():
    titles = [("rebate", "Rebate"), ("rebase", "Rebase")]

    assert rank_title_suggestions("rebase", titles) == []


def test_fewer_typos_rank_first():
    titles = [("two", "Rebase Basics"), ("one", "Rebased Basics")]

    results = rank_title_suggestions("rebasedd basics", titles)

    assert slugs(results) == ["one", "two"]


def test_suggestions_are_capped():
    titles = [(f"lesson-{n}", f"Rebase part {n}") for n in range(20)]

    assert len(rank_title_suggestions("rebsae", titles)) == MAX_SUGGESTIONS
    assert len(rank_title_suggestions("rebsae", titles, limit=50)) == MAX_SUGGESTIONS


@pytest.mark.parametrize(
    "query",
    [
        "",
        "re",
        "!!!",
        "x" * (MAX_QUERY_LENGTH + 1),
        "one two three four five six seven eight nine",
        "kubernetes",
    ],
)
def test_out_of_bounds_or_unrelated_query_gives_nothing(query):
    assert rank_title_suggestions(query, TITLES) == []


@pytest.mark.django_db
def test_endpoint_returns_marked_suggestions_to_anonymous_users():
    make_lesson("merge-conflicts", "Resolving Merge Conflicts")

    response = search("merge conflcit")

    assert response.status_code == 200
    assert response.json() == {
        "suggestions": [
            {
                "slug": "merge-conflicts",
                "title": "Resolving Merge Conflicts",
                "kind": "suggestion",
            }
        ]
    }


@pytest.mark.django_db
def test_endpoint_hides_organization_lessons():
    org = Organization.objects.create(  # type: ignore[attr-defined]
        name="Private", slug="private"
    )
    make_lesson("secret-rebase", "Secret Rebase", organization=org)

    response = search("secret rebsae")

    assert response.json() == {"suggestions": []}


@pytest.mark.django_db
def test_endpoint_skips_the_database_for_an_overlong_query():
    with CaptureQueriesContext(connection) as queries:
        response = search("x" * 5000)

    assert response.json() == {"suggestions": []}
    assert not [q for q in queries if "content_lesson" in q["sql"]]


@pytest.mark.django_db
def test_endpoint_reads_titles_with_a_single_query():
    for n in range(10):
        make_lesson(f"rebase-{n}", f"Rebase part {n}")

    with CaptureQueriesContext(connection) as queries:
        search("rebsae")

    assert len([q for q in queries if "content_lesson" in q["sql"]]) == 1
