import pytest
from rest_framework.test import APIClient

from apps.content.models import Lesson


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
    assert response["Content-Disposition"] == f'attachment; filename="{lesson.slug}.pdf"'
    assert response.content.startswith(b"%PDF")


@pytest.mark.django_db
def test_lesson_pdf_returns_404_for_missing_lesson():
    client = APIClient()
    response = client.get("/api/content/lessons/999999/pdf/")

    assert response.status_code == 404
    assert response.json() == {"error": "Lesson not found"}
