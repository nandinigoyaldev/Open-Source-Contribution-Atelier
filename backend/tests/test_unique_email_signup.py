"""
Tests for: [Backend] Validate Unique Emails in Signup API
===========================================================
Acceptance Criteria:
  1. Add a unique check to email field validation in SignupSerializer.
  2. Return a 400 Bad Request if the email is already registered.

All tests go through the real /api/auth/signup/ endpoint so that the full
serializer validation pipeline (SignupSerializer.validate_email) is exercised.
"""

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SIGNUP_URL = "/api/auth/signup/"

# A valid password that satisfies all existing password rules:
#   - min 8 chars, uppercase, lowercase, digit, special char
VALID_PASSWORD = "Secure@123"


def signup(client, username, email, password=VALID_PASSWORD):
    """POST to the signup endpoint and return the response."""
    return client.post(
        SIGNUP_URL,
        {"username": username, "email": email, "password": password},
        format="json",
    )


# ---------------------------------------------------------------------------
# Acceptance Criteria 1 — unique check in SignupSerializer
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestEmailUniquenessValidation:
    """
    The serializer must reject duplicate emails *before* the database ever
    tries to insert a row.  This is verified by checking that the error is
    surfaced under the 'email' key in the response.
    """

    def test_first_signup_with_new_email_succeeds(self):
        """A brand-new email must be accepted (HTTP 201)."""
        client = APIClient()
        response = signup(client, "alice", "alice@example.com")
        assert response.status_code == 201, response.data

    def test_second_signup_with_same_email_is_rejected(self):
        """Re-using an already-registered email must be rejected (HTTP 400)."""
        client = APIClient()
        # Register alice first
        signup(client, "alice", "alice@example.com")

        # Try to register bob with alice's email
        response = signup(client, "bob", "alice@example.com")
        assert response.status_code == 400

    def test_error_is_on_email_field(self):
        """
        The validation error must be keyed under 'email' so the frontend
        can display it next to the correct input field.
        """
        client = APIClient()
        signup(client, "alice", "alice@example.com")

        response = signup(client, "bob", "alice@example.com")
        assert "errors" in response.data
        assert "email" in response.data["errors"]

    def test_error_message_mentions_already_exists(self):
        """The error message must clearly state the email is already taken."""
        client = APIClient()
        signup(client, "alice", "alice@example.com")

        response = signup(client, "bob", "alice@example.com")
        error_text = str(response.data["errors"]["email"]).lower()
        assert "already exists" in error_text

    def test_unique_username_different_email_still_succeeds(self):
        """
        Different emails must never interfere — two users can share a username
        only if the backend allows it, but two different email addresses should
        both be accepted independently.
        """
        client = APIClient()
        r1 = signup(client, "user1", "user1@example.com")
        r2 = signup(client, "user2", "user2@example.com")
        assert r1.status_code == 201
        assert r2.status_code == 201


# ---------------------------------------------------------------------------
# Acceptance Criteria 2 — HTTP 400 Bad Request
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDuplicateEmailReturns400:
    """
    Every variant of a duplicate email must produce exactly HTTP 400.
    """

    def test_exact_duplicate_returns_400(self):
        client = APIClient()
        signup(client, "alice", "alice@example.com")

        response = signup(client, "bob", "alice@example.com")
        assert response.status_code == 400

    def test_case_insensitive_duplicate_returns_400(self):
        """
        ALICE@EXAMPLE.COM is the same address as alice@example.com.
        The check must be case-insensitive.
        """
        client = APIClient()
        signup(client, "alice", "alice@example.com")

        response = signup(client, "bob", "ALICE@EXAMPLE.COM")
        assert response.status_code == 400

    def test_mixed_case_duplicate_returns_400(self):
        """Any mixed-case variant of a registered email must also be blocked."""
        client = APIClient()
        signup(client, "alice", "alice@example.com")

        response = signup(client, "bob", "Alice@Example.Com")
        assert response.status_code == 400

    def test_whitespace_trimmed_duplicate_returns_400(self):
        """Leading/trailing whitespace around the email must be stripped before checking."""
        client = APIClient()
        signup(client, "alice", "alice@example.com")

        response = signup(client, "bob", "  alice@example.com  ")
        assert response.status_code == 400

    def test_duplicate_does_not_create_second_user(self):
        """
        On a 400 response the duplicate user must not be persisted in the DB.
        """
        client = APIClient()
        signup(client, "alice", "alice@example.com")

        signup(client, "bob", "alice@example.com")  # should fail

        # Only alice should exist with this email
        assert User.objects.filter(email="alice@example.com").count() == 1

    def test_response_is_not_500(self):
        """
        A duplicate email must never bubble up as an unhandled server error.
        The serializer validation must catch it cleanly.
        """
        client = APIClient()
        signup(client, "alice", "alice@example.com")

        response = signup(client, "bob", "alice@example.com")
        assert response.status_code != 500

    def test_response_structure_is_json(self):
        """
        The 400 response must be a JSON object (not an HTML error page).
        DRF returns errors as a dict keyed by field name.
        """
        client = APIClient()
        signup(client, "alice", "alice@example.com")

        response = signup(client, "bob", "alice@example.com")
        # DRF sets content_type to application/json
        assert "application/json" in response.get("Content-Type", "")
        assert isinstance(response.data, dict)


# ---------------------------------------------------------------------------
# Email normalisation side-effects
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestEmailNormalisation:
    """
    SignupSerializer.validate_email normalises the value to lowercase before
    storing it. These tests verify normalisation works alongside the uniqueness
    check.
    """

    def test_email_stored_as_lowercase(self):
        """Regardless of the input casing the stored email must be lowercase."""
        client = APIClient()
        signup(client, "alice", "ALICE@EXAMPLE.COM")

        user = User.objects.get(username="alice")
        assert user.email == "alice@example.com"

    def test_uppercase_input_registered_then_lowercase_duplicate_blocked(self):
        """
        If alice registered with ALICE@EXAMPLE.COM (stored as lowercase),
        a subsequent signup with alice@example.com must still be blocked.
        """
        client = APIClient()
        signup(client, "alice", "ALICE@EXAMPLE.COM")

        response = signup(client, "bob", "alice@example.com")
        assert response.status_code == 400

    def test_lowercase_input_registered_then_uppercase_duplicate_blocked(self):
        """
        If alice registered with alice@example.com,
        a subsequent signup with ALICE@EXAMPLE.COM must still be blocked.
        """
        client = APIClient()
        signup(client, "alice", "alice@example.com")

        response = signup(client, "bob", "ALICE@EXAMPLE.COM")
        assert response.status_code == 400
