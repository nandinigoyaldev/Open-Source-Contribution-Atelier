import json

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.sandbox.models import CodeSnippet, SnippetCollection

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    return User.objects.create(username="snippet_tester")


@pytest.fixture
def other_user():
    return User.objects.create(username="other_user")


@pytest.mark.django_db
def test_snippet_collection_crud(api_client, user, other_user):
    api_client.force_authenticate(user=user)

    # Create Collection
    res = api_client.post(
        "/api/sandbox/snippet-collections/",
        {"name": "Algorithms", "description": "Sorting"},
    )
    assert res.status_code == 201
    collection_id = res.data["id"]

    # Fetch Collection
    res = api_client.get("/api/sandbox/snippet-collections/")
    assert len(res.data) == 1

    # Try fetching as other user (should be isolated)
    api_client.force_authenticate(user=other_user)
    res = api_client.get("/api/sandbox/snippet-collections/")
    assert len(res.data) == 0


@pytest.mark.django_db
def test_code_snippet_crud(api_client, user):
    api_client.force_authenticate(user=user)

    # Create Snippet
    data = {
        "title": "Bubble Sort",
        "code": "def sort(): pass",
        "language": "python",
        "tags": ["algorithm", "sorting"],
        "is_favorite": True,
    }
    res = api_client.post("/api/sandbox/snippets/", data, format="json")
    assert res.status_code == 201
    snippet_id = res.data["id"]

    # Fetch all
    res = api_client.get("/api/sandbox/snippets/")
    assert len(res.data) == 1
    assert res.data[0]["tags"] == ["algorithm", "sorting"]

    # Fetch by favorite
    res = api_client.get("/api/sandbox/snippets/?is_favorite=true")
    assert len(res.data) == 1

    # Fetch by search
    res = api_client.get("/api/sandbox/snippets/?search=Bubble")
    assert len(res.data) == 1

    # Fetch by miss search
    res = api_client.get("/api/sandbox/snippets/?search=Quick")
    assert len(res.data) == 0


@pytest.mark.django_db
def test_snippet_isolation(api_client, user, other_user):
    # User 1 creates a snippet
    api_client.force_authenticate(user=user)
    data = {
        "title": "Private Snippet",
        "code": "print('secret')",
    }
    res = api_client.post("/api/sandbox/snippets/", data, format="json")
    snippet_id = res.data["id"]

    # User 2 tries to fetch it
    api_client.force_authenticate(user=other_user)
    res = api_client.get(f"/api/sandbox/snippets/{snippet_id}/")
    assert res.status_code == 404

    # User 2 tries to update it
    res = api_client.patch(
        f"/api/sandbox/snippets/{snippet_id}/", {"title": "Hacked"}, format="json"
    )
    assert res.status_code == 404

    # User 2 tries to delete it
    res = api_client.delete(f"/api/sandbox/snippets/{snippet_id}/")
    assert res.status_code == 404


@pytest.mark.django_db
def test_snippet_collection_isolation(api_client, user, other_user):
    # User 1 creates collection
    api_client.force_authenticate(user=user)
    res = api_client.post("/api/sandbox/snippet-collections/", {"name": "My Coll"})
    coll_id = res.data["id"]

    # User 2 tries to fetch
    api_client.force_authenticate(user=other_user)
    res = api_client.get(f"/api/sandbox/snippet-collections/{coll_id}/")
    assert res.status_code == 404


@pytest.mark.django_db
def test_snippet_cascade_set_null_on_collection_delete(api_client, user):
    api_client.force_authenticate(user=user)

    # Create Collection
    res = api_client.post(
        "/api/sandbox/snippet-collections/", {"name": "Temp Collection"}
    )
    collection_id = res.data["id"]

    # Create Snippet inside collection
    res = api_client.post(
        "/api/sandbox/snippets/",
        {"title": "Test Snip", "code": "pass", "collection": collection_id},
        format="json",
    )
    snippet_id = res.data["id"]

    # Verify snippet has collection
    res = api_client.get(f"/api/sandbox/snippets/{snippet_id}/")
    assert str(res.data["collection"]) == str(collection_id)

    # Delete Collection
    api_client.delete(f"/api/sandbox/snippet-collections/{collection_id}/")

    # Verify snippet collection is null
    res = api_client.get(f"/api/sandbox/snippets/{snippet_id}/")
    assert res.data["collection"] is None


@pytest.mark.django_db
def test_snippet_filters_combined(api_client, user):
    api_client.force_authenticate(user=user)

    col1_res = api_client.post("/api/sandbox/snippet-collections/", {"name": "Python"})
    col1_id = col1_res.data["id"]

    col2_res = api_client.post("/api/sandbox/snippet-collections/", {"name": "JS"})
    col2_id = col2_res.data["id"]

    api_client.post(
        "/api/sandbox/snippets/",
        {
            "title": "Bubble Sort",
            "code": "def",
            "collection": col1_id,
            "is_favorite": True,
        },
        format="json",
    )
    api_client.post(
        "/api/sandbox/snippets/",
        {
            "title": "Merge Sort",
            "code": "def",
            "collection": col1_id,
            "is_favorite": False,
        },
        format="json",
    )
    api_client.post(
        "/api/sandbox/snippets/",
        {
            "title": "Quick Sort",
            "code": "def",
            "collection": col2_id,
            "is_favorite": True,
        },
        format="json",
    )

    # Combine collection and is_favorite
    res = api_client.get(
        f"/api/sandbox/snippets/?collection={col1_id}&is_favorite=true"
    )
    assert len(res.data) == 1
    assert res.data[0]["title"] == "Bubble Sort"

    # Combine search and collection
    res = api_client.get(f"/api/sandbox/snippets/?search=Sort&collection={col2_id}")
    assert len(res.data) == 1
    assert res.data[0]["title"] == "Quick Sort"


@pytest.mark.django_db
def test_snippet_creation_missing_required_fields(api_client, user):
    api_client.force_authenticate(user=user)

    # Code is required, missing title
    res = api_client.post("/api/sandbox/snippets/", {"code": "print(1)"}, format="json")
    assert res.status_code == 400
    assert "title" in res.data.get("errors", res.data)

    # Title is required, missing code
    res = api_client.post(
        "/api/sandbox/snippets/", {"title": "No Code Snippet"}, format="json"
    )
    assert res.status_code == 400
    assert "code" in res.data.get("errors", res.data)
