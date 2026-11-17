"""
The strict per-identity throttles read the email/username out of the request
body before any serializer runs. A JSON body that is not an object (a list, a
string, a number, null) used to blow up there with AttributeError and the
caller got a 500 instead of a normal 400.
"""

from typing import Any

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.throttles import body_field

ENDPOINTS = [
    "/api/auth/login/",
    "/api/auth/password-reset/",
    "/api/auth/magic-link/request/",
    "/api/auth/resend-verification/",
]

# One body per JSON type that is not an object.
NON_DICT_BODIES = [
    pytest.param([], id="empty-list"),
    pytest.param(["a@example.com"], id="list-with-email"),
    pytest.param("a@example.com", id="string"),
    pytest.param(42, id="number"),
]


@pytest.fixture(autouse=True)
def _clean_cache():
    cache.clear()
    yield
    cache.clear()


def _post(url, body, ip="203.0.113.77") -> Any:
    client = APIClient()
    client.defaults["REMOTE_ADDR"] = ip
    return client.post(url, body, format="json")


@pytest.mark.django_db
@pytest.mark.parametrize("url", ENDPOINTS)
@pytest.mark.parametrize("body", NON_DICT_BODIES)
def test_non_dict_body_is_a_400_not_a_500(url, body):
    response = _post(url, body)
    assert response.status_code == 400, response.content


@pytest.mark.django_db
def test_password_reset_rate_limited_non_dict_body_is_not_a_500():
    """The view's own throttled() hook also read the email from the body."""
    url = "/api/auth/password-reset/"
    codes = [_post(url, []).status_code for _ in range(6)]
    # 400 from the serializer while there is quota left, 429 once it is used up.
    assert 500 not in codes, codes
    assert codes[0] == 400, codes
    assert 429 in codes, codes


@pytest.mark.django_db
def test_normal_object_body_still_works():
    response = _post("/api/auth/password-reset/", {"email": "someone@example.com"})
    assert response.status_code == 200


@pytest.mark.django_db
def test_identity_is_still_taken_from_object_body():
    """Same address, different case: the 4th request is throttled per identity."""
    url = "/api/auth/password-reset/"
    codes = []
    for i in range(4):
        # different IP each time so only the per-identity throttle can trip
        response = _post(
            url, {"email": "  Same@Example.com "}, ip=f"203.0.113.{100 + i}"
        )
        codes.append(response.status_code)
    assert codes[:3] == [200, 200, 200]
    assert codes[3] == 429


@pytest.mark.parametrize(
    "data, expected",
    [
        ({"email": "a@b.c"}, "a@b.c"),
        ({}, None),
        ([], None),
        (["email"], None),
        ("email", None),
        (None, None),
        (5, None),
    ],
)
def test_body_field_only_reads_from_a_mapping(data, expected):
    assert body_field(data, "email") == expected
