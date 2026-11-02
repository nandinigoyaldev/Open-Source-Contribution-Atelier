import json

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from rest_framework.exceptions import ErrorDetail, ValidationError

from apps.accounts.exceptions import (
    _flatten_validation_detail,
    throttle_exception_handler,
)

User = get_user_model()

GOOD_PASSWORD = "Str0ng!Passw0rd"
URL = "/api/auth/signup/"


class SignupValidationErrorSchemaTests(TestCase):
    """Every way signup can fail answers with the same envelope and stable codes."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        User.objects.create_user(
            username="Existing", email="existing@example.com", password=GOOD_PASSWORD
        )

    def post(self, **body):
        cache.clear()  # the signup throttle would otherwise answer 429 after a few attempts
        return self.client.post(
            URL, data=json.dumps(body), content_type="application/json"
        )

    def assertEnvelope(self, response, field, code):
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIs(data["error"], True)
        self.assertEqual(data["code"], "validation_error")
        self.assertIsInstance(data["message"], str)
        self.assertTrue(data["message"])
        self.assertIn(field, data["errors"])
        self.assertIsInstance(data["errors"][field], list)
        self.assertEqual(data["message"], next(iter(data["errors"].values()))[0])
        self.assertIn(code, data["error_codes"][field])
        # messages and codes line up one to one
        for name, texts in data["errors"].items():
            self.assertEqual(len(texts), len(data["error_codes"][name]))
        self.assertEqual(
            set(data), {"error", "code", "message", "errors", "error_codes"}
        )
        return data

    def test_invalid_email(self):
        self.assertEnvelope(
            self.post(username="newbie", email="nope", password=GOOD_PASSWORD),
            "email",
            "invalid",
        )

    def test_duplicate_email_is_case_insensitive(self):
        data = self.assertEnvelope(
            self.post(
                username="newbie", email="EXISTING@Example.com", password=GOOD_PASSWORD
            ),
            "email",
            "email_taken",
        )
        self.assertEqual(
            data["errors"]["email"],
            ["An account with this email address already exists."],
        )

    def test_duplicate_username_is_case_insensitive(self):
        self.assertEnvelope(
            self.post(
                username="EXISTING", email="fresh@example.com", password=GOOD_PASSWORD
            ),
            "username",
            "username_taken",
        )

    def test_each_weak_password_rule_has_its_own_code(self):
        cases = {
            "Password!": "password_no_number",
            "Passw0rdNoSpecial": "password_no_special",
            "passw0rd!lower": "password_no_uppercase",
            "PASSW0RD!UPPER": "password_no_lowercase",
        }
        for password, code in cases.items():
            self.assertEnvelope(
                self.post(username="newbie", email="n@example.com", password=password),
                "password",
                code,
            )

    def test_all_failed_password_rules_are_reported_together(self):
        data = self.post(
            username="newbie", email="n@example.com", password="alllowercase"
        ).json()
        self.assertEqual(
            data["error_codes"]["password"],
            ["password_no_number", "password_no_special", "password_no_uppercase"],
        )
        self.assertEqual(len(data["errors"]["password"]), 3)

    def test_password_length_rules_use_the_same_schema(self):
        self.assertEnvelope(
            self.post(username="newbie", email="n@example.com", password="Ab1!"),
            "password",
            "min_length",
        )
        self.assertEnvelope(
            self.post(
                username="newbie", email="n@example.com", password="Aa1!" + "x" * 200
            ),
            "password",
            "max_length",
        )

    def test_missing_and_blank_fields_use_the_same_schema(self):
        data = self.assertEnvelope(self.post(), "username", "required")
        self.assertIn("required", data["error_codes"]["password"])
        blank = self.post(username="", email="a@example.com", password=GOOD_PASSWORD)
        self.assertEnvelope(blank, "username", "blank")

    def test_wrong_types_and_oversized_values_do_not_crash(self):
        for body in (
            {"username": ["a"], "email": {"x": 1}, "password": 5},
            {
                "username": "u" * 500,
                "email": "a@example.com",
                "password": GOOD_PASSWORD,
            },
            {"username": None, "email": None, "password": None},
        ):
            response = self.post(**body)
            self.assertEqual(response.status_code, 400, body)
            self.assertEqual(response.json()["code"], "validation_error")

    def test_a_body_that_is_not_an_object_uses_the_envelope(self):
        cache.clear()
        response = self.client.post(
            URL, data=json.dumps(["a"]), content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["code"], "validation_error")
        self.assertEqual(data["error_codes"], {"non_field_errors": ["invalid"]})
        self.assertEqual(data["message"], data["errors"]["non_field_errors"][0])

    def test_errors_do_not_leak_account_details(self):
        replies = [
            self.post(
                username="newbie", email="existing@example.com", password=GOOD_PASSWORD
            ),
            self.post(
                username="existing", email="fresh@example.com", password=GOOD_PASSWORD
            ),
            self.post(username="newbie", email="n@example.com", password="weak"),
        ]
        for response in replies:
            text = response.content.decode()
            self.assertNotIn(GOOD_PASSWORD, text)
            self.assertNotIn("pbkdf2", text)
            self.assertNotIn("password_hash", text)
            self.assertNotIn("last_login", text)
            self.assertNotIn("is_staff", text)
            # the existing account's stored values are not echoed back
            self.assertNotIn("Existing", text)
            self.assertNotIn("existing@example.com", text)
        self.assertNotIn(
            "weak", replies[2].content.decode().replace("weak password", "")
        )

    def test_a_failed_signup_creates_nothing(self):
        before = User.objects.count()
        self.post(
            username="newbie", email="existing@example.com", password=GOOD_PASSWORD
        )
        self.post(username="newbie2", email="n2@example.com", password="weak")
        self.assertEqual(User.objects.count(), before)

    def test_successful_signup_is_unchanged(self):
        response = self.post(
            username="Fresh", email="Fresh@Example.com", password=GOOD_PASSWORD
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(set(data), {"id", "username", "email"})
        self.assertEqual(data["username"], "Fresh")
        self.assertEqual(data["email"], "fresh@example.com")
        user = User.objects.get(pk=data["id"])
        self.assertTrue(user.check_password(GOOD_PASSWORD))


class FlattenValidationDetailTests(SimpleTestCase):
    def test_dict_of_lists(self):
        messages, codes = _flatten_validation_detail(
            {
                "email": [ErrorDetail("Bad.", code="invalid")],
                "name": [ErrorDetail("Req.", code="required")],
            }
        )
        self.assertEqual(messages, {"email": ["Bad."], "name": ["Req."]})
        self.assertEqual(codes, {"email": ["invalid"], "name": ["required"]})

    def test_plain_list_and_string_have_no_field(self):
        self.assertEqual(
            _flatten_validation_detail([ErrorDetail("One.", code="x")])[0],
            {"": ["One."]},
        )
        self.assertEqual(
            _flatten_validation_detail(ErrorDetail("Only.", code="y"))[1], {"": ["y"]}
        )

    def test_nested_serializer_and_list_errors_get_dotted_paths(self):
        detail = {
            "profile": {"timezone": [ErrorDetail("Unknown timezone.", code="invalid")]},
            "items": [{}, {"name": [ErrorDetail("Required.", code="required")]}],
        }
        messages, codes = _flatten_validation_detail(detail)
        self.assertEqual(messages["profile.timezone"], ["Unknown timezone."])
        self.assertEqual(messages["items.1.name"], ["Required."])
        self.assertEqual(codes["items.1.name"], ["required"])

    def test_plain_strings_without_a_code_default_to_invalid(self):
        self.assertEqual(
            _flatten_validation_detail({"a": ["text"]})[1], {"a": ["invalid"]}
        )


class ExceptionHandlerValidationTests(SimpleTestCase):
    def handle(self, detail):
        response = throttle_exception_handler(ValidationError(detail), {})
        return response.status_code, response.data

    def test_nested_details_no_longer_crash_the_handler(self):
        status, data = self.handle({"profile": {"timezone": ["Unknown timezone."]}})
        self.assertEqual(status, 400)
        self.assertEqual(data["errors"], {"profile.timezone": ["Unknown timezone."]})
        self.assertEqual(data["message"], "Unknown timezone.")

    def test_an_empty_detail_still_answers(self):
        status, data = self.handle({})
        self.assertEqual(status, 400)
        self.assertEqual(data["message"], "Validation error")
        self.assertNotIn("errors", data)

    def test_non_field_errors_keep_their_message_and_name(self):
        status, data = self.handle({"non_field_errors": ["Passwords do not match."]})
        self.assertEqual(data["message"], "Passwords do not match.")
        self.assertEqual(
            data["errors"], {"non_field_errors": ["Passwords do not match."]}
        )

    def test_list_detail(self):
        status, data = self.handle(["Something is wrong."])
        self.assertEqual(data["message"], "Something is wrong.")
        self.assertNotIn("errors", data)
