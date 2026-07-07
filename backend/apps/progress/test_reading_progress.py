import pytest
from django.urls import reverse
from rest_framework import status
from django.core.cache import cache

@pytest.fixture
def reading_progress_url():
    return reverse("reading-position")

@pytest.mark.django_db
class TestReadingProgressView:
    def test_get_reading_progress_success(self, api_client, user):
        api_client.force_authenticate(user=user)
        lesson_slug = "test-lesson"
        cache_key = f"reading_progress_{user.id}_{lesson_slug}"
        
        # Set initial value in cache
        cache.set(cache_key, 45, timeout=60)
        
        response = api_client.get(reverse("reading-position"), {"lesson": lesson_slug})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["progress"] == 45

    def test_get_reading_progress_no_lesson(self, api_client, user):
        api_client.force_authenticate(user=user)
        response = api_client.get(reverse("reading-position"))
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_post_reading_progress_success(self, api_client, user):
        api_client.force_authenticate(user=user)
        lesson_slug = "test-lesson"
        cache_key = f"reading_progress_{user.id}_{lesson_slug}"
        
        response = api_client.post(
            reverse("reading-position"),
            {"lesson": lesson_slug, "progress": 80},
            format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["progress"] == 80
        
        # Verify it was saved to cache
        saved_progress = cache.get(cache_key)
        assert saved_progress == 80

    def test_post_reading_progress_missing_fields(self, api_client, user):
        api_client.force_authenticate(user=user)
        response = api_client.post(
            reverse("reading-position"),
            {"lesson": "test-lesson"}, # Missing progress
            format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unauthenticated_access(self, api_client):
        response = api_client.get(reverse("reading-position"), {"lesson": "test-lesson"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
