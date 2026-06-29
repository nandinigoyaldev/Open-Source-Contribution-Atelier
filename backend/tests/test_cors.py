import pytest
from django.test import override_settings
from rest_framework.test import APIClient


@pytest.mark.django_db
@override_settings(
    CORS_ALLOWED_ORIGINS=["http://localhost:5173"],
    CORS_ALLOW_CREDENTIALS=True,
)
def test_cors_headers():
    client = APIClient()

    response = client.options(
        "/api/schema/",
        HTTP_ORIGIN="http://localhost:5173",
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
    )

    assert response.status_code == 200
    assert response["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert response["Access-Control-Allow-Credentials"] == "true"
