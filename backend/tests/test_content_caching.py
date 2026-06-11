import pytest
from django.core.cache import cache
from apps.content.models import Lesson
from apps.content.views import get_active_lessons

@pytest.fixture(autouse=True)
def clear_cache_before_tests():
    cache.clear()
    yield
    cache.clear()

@pytest.mark.django_db(transaction=True)
def test_active_lessons_caching():
    assert cache.get("active_lessons_list") is None
    
    # First call should populate the cache
    lessons = get_active_lessons()
    assert isinstance(lessons, list)
    assert len(lessons) == 0
    assert cache.get("active_lessons_list") is not None
    
    # Create a new lesson
    lesson = Lesson.objects.create(
        difficulty="beginner",
        title="Cache Test",
        slug="cache-test",
        summary="Cache summary",
        content="Cache content",
        estimated_minutes=10,
        order=1,
    )
    
    # transaction.on_commit requires actual commits to fire.
    # In transaction=True tests, .create() commits immediately.
    assert cache.get("active_lessons_list") is None
    
    # Fetch again to populate cache with 1 lesson
    lessons = get_active_lessons()
    assert len(lessons) == 1
    assert cache.get("active_lessons_list") is not None
    
    # Update lesson
    lesson.title = "Updated Title"
    lesson.save()
    
    # Cache should be cleared
    assert cache.get("active_lessons_list") is None
    
    # Fetch again to populate cache
    get_active_lessons()
    assert cache.get("active_lessons_list") is not None
    
    # Delete lesson
    lesson.delete()
    
    # Cache should be cleared
    assert cache.get("active_lessons_list") is None
