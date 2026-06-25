import csv
import io
import json
import zipfile

from apps.accounts.models import MentorProfile
from apps.dashboard.models import Issue, PullRequest, StreakFreeze
from apps.notifications.models import Notification
from apps.progress.models import (Certificate, HelpRequest, LessonProgress,
                                  QuizAttempt, UserBadge, ExerciseAttempt,
                                  CodeSubmission, PeerReview)
from apps.sandbox.models import SandboxExecutionLog
from apps.content.models import Comment
from apps.chat.models import Message
from apps.webhooks.models import WebhookEndpoint
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import QuerySet


class DataExportService:
    def __init__(self, user):
        self.user = user

    def gather_data(self):
        """
        Gather all personal data for the user into a structured dictionary.
        """
        data = {
            "user_profile": self._get_user_base_data(),
            "mentor_profile": self._get_mentor_profile(),
            "lesson_progress": self._queryset_to_list(
                LessonProgress.objects.filter(user=self.user)
            ),
            "help_requests": self._queryset_to_list(
                HelpRequest.objects.filter(user=self.user)
            ),
            "certificates": self._queryset_to_list(
                Certificate.objects.filter(user=self.user)
            ),
            "earned_badges": self._queryset_to_list(
                UserBadge.objects.filter(user=self.user)
            ),
            "quiz_attempts": self._queryset_to_list(
                QuizAttempt.objects.filter(user=self.user)
            ),
            "sandbox_logs": self._queryset_to_list(
                SandboxExecutionLog.objects.filter(user=self.user)
            ),
            "notifications": self._queryset_to_list(
                Notification.objects.filter(recipient=self.user)
            ),
            "pull_requests": self._queryset_to_list(
                PullRequest.objects.filter(user=self.user)
            ),
            "assigned_issues": self._queryset_to_list(
                Issue.objects.filter(assigned_to=self.user)
            ),
            "streak_freezes": self._queryset_to_list(
                StreakFreeze.objects.filter(user=self.user)
            ),
            "webhooks": self._queryset_to_list(
                WebhookEndpoint.objects.filter(user=self.user)
            ),
            "exercise_attempts": self._queryset_to_list(
                ExerciseAttempt.objects.filter(user=self.user)
            ),
            "code_submissions": self._queryset_to_list(
                CodeSubmission.objects.filter(user=self.user)
            ),
            "peer_reviews": self._queryset_to_list(
                PeerReview.objects.filter(reviewer=self.user)
            ),
            "comments": self._queryset_to_list(
                Comment.all_objects.filter(user=self.user)
            ),
            "messages": self._queryset_to_list(
                Message.objects.filter(user=self.user)
            ),
        }
        return data

    def _get_user_base_data(self):
        return [
            {
                "id": self.user.id,
                "username": self.user.username,
                "email": self.user.email,
                "first_name": self.user.first_name,
                "last_name": self.user.last_name,
                "date_joined": self.user.date_joined,
                "last_login": self.user.last_login,
                "is_active": self.user.is_active,
            }
        ]

    def _get_mentor_profile(self):
        try:
            profile = self.user.mentor_profile
            return [
                {
                    "id": profile.id,
                    "assigned_lessons": list(
                        profile.assigned_lessons.values_list("slug", flat=True)
                    ),
                }
            ]
        except MentorProfile.DoesNotExist:
            return []

    def _queryset_to_list(self, qs: QuerySet):
        """
        Convert a QuerySet to a list of dicts, keeping basic serializable fields.
        We exclude foreign keys like user_id as it's implicit, but keep explicit relations.
        """
        if not qs.exists():
            return []

        data = []
        for obj in qs:
            obj_dict = {}
            for field in obj._meta.fields:
                if field.name in ["user", "recipient", "assigned_to", "password"]:
                    continue
                val = getattr(obj, field.attname)
                obj_dict[field.name] = val
            data.append(obj_dict)
        return data

    def generate_json(self):
        data = self.gather_data()
        return json.dumps(data, cls=DjangoJSONEncoder, indent=2)

    def generate_csv_zip(self):
        """
        Generates a ZIP archive in memory containing one CSV file per data entity.
        """
        data = self.gather_data()
        mem_zip = io.BytesIO()

        with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for entity_name, records in data.items():
                if not records:
                    continue

                # Write CSV to a string buffer
                csv_buffer = io.StringIO()
                writer = csv.DictWriter(csv_buffer, fieldnames=records[0].keys())
                writer.writeheader()
                for row in records:
                    writer.writerow(row)

                zf.writestr(f"{entity_name}.csv", csv_buffer.getvalue())

        mem_zip.seek(0)
        return mem_zip.read()
