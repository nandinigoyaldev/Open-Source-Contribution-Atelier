import pytest
from rest_framework.test import APIClient

from apps.content.models import Lesson, LessonFeedback


@pytest.mark.django_db
def test_lesson_pdf_returns_pdf_for_existing_lesson():
    lesson = Lesson.objects.create(
        title="PDF Test Lesson",
        slug="pdf-test",
        summary="Testing PDF export",
        content="This is sample lesson content.",
        difficulty="beginner",
        estimated_minutes=12,
    )

    client = APIClient()
    response = client.get(f"/api/content/lessons/{lesson.id}/pdf/")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert (
        response["Content-Disposition"] == f'attachment; filename="{lesson.slug}.pdf"'
    )
    assert response.content.startswith(b"%PDF")


@pytest.mark.django_db
def test_lesson_pdf_returns_404_for_missing_lesson():
    client = APIClient()
    response = client.get("/api/content/lessons/999999/pdf/")

    assert response.status_code == 404
    assert response.json() == {"error": "Lesson not found"}


from django.contrib.auth import get_user_model


@pytest.mark.django_db
def test_comment_soft_delete_instance():
    from apps.content.models import Comment

    User = get_user_model()
    user = User.objects.create(username="softdelete_user")
    comment = Comment.objects.create(user=user, content="This is a test comment")

    # Ensure it's in standard objects
    assert Comment.objects.count() == 1
    assert Comment.all_objects.count() == 1

    # Soft delete via instance
    comment.delete()

    # Should disappear from standard objects
    assert Comment.objects.count() == 0
    # Should still exist in all_objects
    assert Comment.all_objects.count() == 1

    # Verify is_deleted flag
    comment.refresh_from_db()
    assert comment.is_deleted is True


@pytest.mark.django_db
def test_comment_soft_delete_queryset():
    from apps.content.models import Comment

    User = get_user_model()
    user = User.objects.create(username="softdelete_user2")
    Comment.objects.create(user=user, content="Comment 1")
    Comment.objects.create(user=user, content="Comment 2")

    assert Comment.objects.count() == 2

    # Bulk soft delete
    Comment.objects.all().delete()

    assert Comment.objects.count() == 0
    assert Comment.all_objects.count() == 2

    for c in Comment.all_objects.all():
        assert c.is_deleted is True


@pytest.mark.django_db
def test_comment_restore():
    from apps.content.models import Comment

    User = get_user_model()
    user = User.objects.create(username="softdelete_user3")
    comment = Comment.objects.create(user=user, content="Comment to restore")

    comment.delete()
    assert Comment.objects.count() == 0

    # Restore
    comment.restore()
    assert Comment.objects.count() == 1
    assert Comment.objects.first().is_deleted is False


@pytest.mark.django_db
def test_comment_hard_delete():
    from apps.content.models import Comment

    User = get_user_model()
    user = User.objects.create(username="harddelete_user")
    comment = Comment.objects.create(user=user, content="Comment to hard delete")

    # Instance hard delete
    comment.delete(hard=True)
    assert Comment.objects.count() == 0
    assert Comment.all_objects.count() == 0


@pytest.mark.django_db
def test_comment_queryset_hard_delete():
    from apps.content.models import Comment

    User = get_user_model()
    user = User.objects.create(username="harddelete_user_qs")
    Comment.objects.create(user=user, content="1")
    Comment.objects.create(user=user, content="2")

    # Bulk hard delete (via all_objects standard manager)
    Comment.all_objects.all().delete()
    assert Comment.all_objects.count() == 0


@pytest.mark.django_db
def test_comment_related_manager_excludes_deleted():
    from apps.content.models import Comment

    User = get_user_model()
    user = User.objects.create(username="related_user")
    c1 = Comment.objects.create(user=user, content="Keep")
    c2 = Comment.objects.create(user=user, content="Delete me")

    c2.delete()

    # The reverse relation user.comments should use the default manager (SoftDeleteManager)
    assert user.comments.count() == 1
    assert user.comments.first() == c1


@pytest.mark.django_db
def test_cascade_user_deletion_hard_deletes_comments():
    from apps.content.models import Comment

    User = get_user_model()
    user = User.objects.create(username="cascade_user")
    Comment.objects.create(user=user, content="Cascade me")

    assert Comment.all_objects.count() == 1

    # Hard delete user
    user.delete()

    # By default, Django's cascade deletion uses the model's base manager,
    # which is the default manager unless specified. If it used the default manager (SoftDelete),
    # it would update and hit IntegrityError due to missing user.
    # We must ensure it's deleted.
    assert Comment.all_objects.count() == 0


from apps.content.utils import calculate_reading_time, strip_markdown


def test_strip_markdown():
    # Headers and basics
    assert strip_markdown("# Header 1\n## Header 2\nBody text").split() == [
        "Header",
        "1",
        "Header",
        "2",
        "Body",
        "text",
    ]

    # Links and images
    assert strip_markdown(
        "Check out [Google](https://google.com) and ![alt](img.jpg)"
    ).split() == ["Check", "out", "Google", "and", "alt"]

    # Code blocks and inline code
    assert strip_markdown(
        "Here is `inline code` and:\n```python\nprint('hello')\n```"
    ).split() == ["Here", "is", "inline", "code", "and:", "print('hello')"]


@pytest.mark.django_db
def test_reading_time_calculation():
    # Empty content
    lesson_empty = Lesson.objects.create(
        title="Empty", slug="empty", content="", difficulty="beginner"
    )
    assert lesson_empty.reading_time == 1

    # None content check (safeguard)
    assert calculate_reading_time(None) == 1

    # Short content (< 200 words)
    lesson_short = Lesson.objects.create(
        title="Short", slug="short", content="Word " * 100, difficulty="beginner"
    )
    assert lesson_short.reading_time == 1

    # Exactly 200 words
    lesson_200 = Lesson.objects.create(
        title="200 Words", slug="w-200", content="Word " * 200, difficulty="beginner"
    )
    assert lesson_200.reading_time == 1

    # 201 words
    lesson_201 = Lesson.objects.create(
        title="201 Words", slug="w-201", content="Word " * 201, difficulty="beginner"
    )
    assert lesson_201.reading_time == 2

    # Long content (e.g. 500 words)
    lesson_long = Lesson.objects.create(
        title="Long", slug="long", content="Word " * 500, difficulty="beginner"
    )
    assert lesson_long.reading_time == 3  # ceil(500/200) = 3


@pytest.mark.django_db
def test_lesson_api_includes_reading_time():
    lesson = Lesson.objects.create(
        title="API Test Lesson",
        slug="api-test",
        content="Word " * 250,  # 250 words -> 2 mins
        difficulty="beginner",
        estimated_minutes=10,
    )
    client = APIClient()

    # Verify GET lesson detail contains readingTime (due to CamelCaseModelSerializer)
    response = client.get(f"/api/content/lessons/{lesson.id}/")
    assert response.status_code == 200
    assert "readingTime" in response.data
    assert response.data["readingTime"] == 2

    # Verify GET lesson list contains readingTime
    response_list = client.get("/api/content/lessons/")
    assert response_list.status_code == 200
    assert len(response_list.data) > 0
    # Find our lesson in list response
    found = False
    for l in response_list.data:
        if l["slug"] == "api-test":
            assert l["readingTime"] == 2
            found = True
    assert found


# ---------------------- Lesson Feedback Tests ----------------------


@pytest.mark.django_db
def test_feedback_soft_delete():
    from apps.content.models import LessonFeedback

    User = get_user_model()
    user = User.objects.create(username="feedback_user")
    lesson = Lesson.objects.create(
        title="Feedback Test",
        slug="feedback-test",
        content="Content",
        difficulty="beginner",
    )
    feedback = LessonFeedback.objects.create(
        user=user,
        lesson=lesson,
        rating=5,
        comment="Great lesson!",
    )

    # Soft delete
    feedback.delete()

    # Should disappear from standard objects
    assert LessonFeedback.objects.count() == 0
    # Should still exist in all_objects
    assert LessonFeedback.all_objects.count() == 1

    # Verify is_deleted flag
    feedback.refresh_from_db()
    assert feedback.is_deleted is True


@pytest.mark.django_db
def test_feedback_restore():
    from apps.content.models import LessonFeedback

    User = get_user_model()
    user = User.objects.create(username="feedback_restore_user")
    lesson = Lesson.objects.create(
        title="Restore Test",
        slug="restore-test",
        content="Content",
        difficulty="beginner",
    )
    feedback = LessonFeedback.objects.create(
        user=user,
        lesson=lesson,
        rating=4,
    )

    feedback.delete()
    assert LessonFeedback.objects.count() == 0

    # Restore
    feedback.restore()
    assert LessonFeedback.objects.count() == 1
    assert LessonFeedback.objects.first().is_deleted is False


@pytest.mark.django_db
def test_feedback_api_create():
    from apps.content.models import LessonFeedback

    User = get_user_model()
    user = User.objects.create(username="feedback_api_user")
    lesson = Lesson.objects.create(
        title="API Create Test",
        slug="api-create-test",
        content="Content",
        difficulty="beginner",
    )

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        f"/api/content/lessons/{lesson.slug}/feedback/",
        {"rating": 5, "comment": "Excellent!"},
        format="json",
    )

    assert response.status_code == 201
    assert LessonFeedback.objects.count() == 1
    assert LessonFeedback.objects.first().rating == 5
    assert LessonFeedback.objects.first().comment == "Excellent!"


@pytest.mark.django_db
def test_feedback_api_requires_authentication():
    User = get_user_model()
    user = User.objects.create(username="anon_feedback_user")
    lesson = Lesson.objects.create(
        title="Auth Test",
        slug="auth-test",
        content="Content",
        difficulty="beginner",
    )

    client = APIClient()
    response = client.post(
        f"/api/content/lessons/{lesson.slug}/feedback/",
        {"rating": 3},
        format="json",
    )

    assert response.status_code == 401 or response.status_code == 403


@pytest.mark.django_db
def test_feedback_api_validation_rating_range():
    User = get_user_model()
    user = User.objects.create(username="rating_validation_user")
    lesson = Lesson.objects.create(
        title="Validation Test",
        slug="validation-test",
        content="Content",
        difficulty="beginner",
    )

    client = APIClient()
    client.force_authenticate(user=user)

    # Test rating too low
    response = client.post(
        f"/api/content/lessons/{lesson.slug}/feedback/",
        {"rating": 0},
        format="json",
    )
    assert response.status_code == 400

    # Test rating too high
    response = client.post(
        f"/api/content/lessons/{lesson.slug}/feedback/",
        {"rating": 6},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_feedback_api_duplicate_prevention():
    User = get_user_model()
    user = User.objects.create(username="duplicate_user")
    lesson = Lesson.objects.create(
        title="Duplicate Test",
        slug="duplicate-test",
        content="Content",
        difficulty="beginner",
    )

    LessonFeedback.objects.create(
        user=user,
        lesson=lesson,
        rating=4,
    )

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        f"/api/content/lessons/{lesson.slug}/feedback/",
        {"rating": 5},
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_feedback_metrics_api():
    User = get_user_model()
    user1 = User.objects.create(username="metrics_user1")
    user2 = User.objects.create(username="metrics_user2")
    lesson = Lesson.objects.create(
        title="Metrics Test",
        slug="metrics-test",
        content="Content",
        difficulty="beginner",
    )

    LessonFeedback.objects.create(user=user1, lesson=lesson, rating=5)
    LessonFeedback.objects.create(user=user2, lesson=lesson, rating=3)

    client = APIClient()
    response = client.get(f"/api/content/lessons/{lesson.slug}/feedback/metrics/")

    assert response.status_code == 200
    assert response.data["totalCount"] == 2
    assert response.data["averageRating"] == 4.0
    assert response.data["ratingDistribution"]["5"] == 1
    assert response.data["ratingDistribution"]["3"] == 1


@pytest.mark.django_db
def test_feedback_metrics_empty_lesson():
    lesson = Lesson.objects.create(
        title="Empty Metrics",
        slug="empty-metrics",
        content="Content",
        difficulty="beginner",
    )

    client = APIClient()
    response = client.get(f"/api/content/lessons/{lesson.slug}/feedback/metrics/")

    assert response.status_code == 200
    assert response.data["totalCount"] == 0
    assert response.data["averageRating"] == 0.0


@pytest.mark.django_db
def test_feedback_user_own_feedback():
    User = get_user_model()
    user = User.objects.create(username="own_feedback_user")
    lesson = Lesson.objects.create(
        title="Own Feedback Test",
        slug="own-feedback-test",
        content="Content",
        difficulty="beginner",
    )

    LessonFeedback.objects.create(user=user, lesson=lesson, rating=5, comment="Loved it!")

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get(f"/api/content/lessons/{lesson.slug}/feedback/my/")

    assert response.status_code == 200
    assert response.data["rating"] == 5
    assert response.data["comment"] == "Loved it!"


@pytest.mark.django_db
def test_feedback_list_api():
    User = get_user_model()
    user = User.objects.create(username="list_user")
    lesson = Lesson.objects.create(
        title="List Test",
        slug="list-test",
        content="Content",
        difficulty="beginner",
    )

    LessonFeedback.objects.create(user=user, lesson=lesson, rating=5)

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get(f"/api/content/lessons/{lesson.slug}/feedback/")

    assert response.status_code == 200
    assert len(response.data) == 1

@pytest.mark.django_db
def test_user_cannot_update_another_users_feedback():
    User = get_user_model()

    owner = User.objects.create(username="feedback_owner")
    attacker = User.objects.create(username="other_user")

    lesson = Lesson.objects.create(
        title="Ownership Test",
        slug="ownership-test",
        content="Content",
        difficulty="beginner",
    )

    feedback = LessonFeedback.objects.create(
        user=owner,
        lesson=lesson,
        rating=4,
        comment="Original comment",
    )

    client = APIClient()
    client.force_authenticate(user=attacker)

    response = client.patch(
        f"/api/content/feedback/{feedback.id}/",
        {
            "rating": 1,
            "comment": "Unauthorized update",
        },
        format="json",
    )

    assert response.status_code == 404

    feedback.refresh_from_db()

    assert feedback.rating == 4
    assert feedback.comment == "Original comment"