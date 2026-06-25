import pytest
from apps.content.models import Lesson
from rest_framework.test import APIClient


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
