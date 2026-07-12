import json
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import UserProfile
from apps.progress.models import HelpRequest
from apps.content.models import Lesson

User = get_user_model()


class DumpAnonymizedDBTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username="real_johndoe",
            email="johndoe@example.com",
            password="realpassword123",
            first_name="John",
            last_name="Doe",
        )
        self.profile1 = UserProfile.objects.create(
            user=self.user1,
            twitter_url="https://twitter.com/johndoe",
            github_url="https://github.com/johndoe",
        )

        self.lesson = Lesson.objects.create(
            title="Test Lesson",
            slug="test-lesson",
            summary="A test lesson summary",
            content="This is the content.",
        )

        self.help_request = HelpRequest.objects.create(
            user=self.user1,
            lesson=self.lesson,
            message="This is my real, sensitive message that might contain PII.",
            status="open",
        )

        # Second user for deterministic test comparison
        self.user2 = User.objects.create_user(
            username="real_janedoe",
            email="jane@example.com",
            password="realpassword123",
            first_name="Jane",
            last_name="Doe",
        )

    def _run_command(self, *args, **kwargs):
        out = StringIO()
        call_command("dump_anonymized_db", stdout=out, *args, **kwargs)
        return out.getvalue()

    def test_anonymization_engine_replaces_pii(self):
        output = self._run_command(
            "auth.user", "accounts.userprofile", "progress.helprequest"
        )
        data = json.loads(output)

        # Verify user PII
        user_data = next(
            item
            for item in data
            if item["model"] == "auth.user" and item["pk"] == self.user1.pk
        )
        fields = user_data["fields"]

        self.assertNotEqual(fields["username"], "real_johndoe")
        self.assertTrue(fields["username"].startswith("anon_"))
        self.assertNotEqual(fields["email"], "johndoe@example.com")
        self.assertNotEqual(fields["first_name"], "John")
        self.assertNotEqual(fields["last_name"], "Doe")
        self.assertEqual(fields["password"], "pbkdf2_sha256$600000$dummy$dummy")

        # Verify UserProfile clear strategy
        profile_data = next(
            item
            for item in data
            if item["model"] == "accounts.userprofile"
            and item["pk"] == self.profile1.pk
        )
        self.assertEqual(profile_data["fields"]["twitter_url"], "")
        self.assertEqual(profile_data["fields"]["github_url"], "")
        self.assertEqual(profile_data["fields"]["user"], self.user1.pk)  # FK preserved

        # Verify HelpRequest
        hr_data = next(
            item
            for item in data
            if item["model"] == "progress.helprequest"
            and item["pk"] == self.help_request.pk
        )
        self.assertNotEqual(hr_data["fields"]["message"], self.help_request.message)
        self.assertTrue(len(hr_data["fields"]["message"]) > 0)
        self.assertEqual(hr_data["fields"]["status"], "open")  # Non-PII preserved

    def test_deterministic_anonymization(self):
        output1 = self._run_command("auth.user", "--deterministic")
        output2 = self._run_command("auth.user", "--deterministic")

        self.assertEqual(output1, output2)

        # Non-deterministic should be different
        output_non1 = self._run_command("auth.user")
        output_non2 = self._run_command("auth.user")
        self.assertNotEqual(output_non1, output_non2)

    def test_exclude_works(self):
        output = self._run_command(exclude=["auth.user"])
        data = json.loads(output)

        has_user = any(item["model"] == "auth.user" for item in data)
        self.assertFalse(has_user)

    def test_model_without_rules_is_untouched(self):
        output = self._run_command("content.lesson")
        data = json.loads(output)

        lesson_data = next(
            item
            for item in data
            if item["model"] == "content.lesson" and item["pk"] == self.lesson.pk
        )
        self.assertEqual(lesson_data["fields"]["title"], "Test Lesson")
        self.assertEqual(lesson_data["fields"]["content"], "This is the content.")
