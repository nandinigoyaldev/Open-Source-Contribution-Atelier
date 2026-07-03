import pytest
from django.contrib.auth import get_user_model
from apps.sandbox.models import CollabSession, CodeReviewThread, CodeReviewComment

User = get_user_model()

@pytest.mark.django_db
def test_code_review_models():
    import uuid
    user = User.objects.create(username="reviewer")
    session = CollabSession.objects.create(id=uuid.uuid4())
    
    thread = CodeReviewThread.objects.create(session=session, line_number=5)
    comment = CodeReviewComment.objects.create(thread=thread, user=user, content="LGTM!")
    
    assert thread.line_number == 5
    assert not thread.is_resolved
    assert thread.comments.count() == 1
    assert thread.comments.first().content == "LGTM!"
    
    thread.is_resolved = True
    thread.save()
    assert thread.is_resolved

@pytest.mark.django_db
def test_code_review_edge_cases():
    import uuid
    user = User.objects.create(username="reviewer2")
    session = CollabSession.objects.create(id=uuid.uuid4())
    
    # 1. Thread without comments
    empty_thread = CodeReviewThread.objects.create(session=session, line_number=10)
    assert empty_thread.comments.count() == 0
    
    # 2. Deleting a session cascades to threads
    session.delete()
    assert CodeReviewThread.objects.filter(id=empty_thread.id).count() == 0
