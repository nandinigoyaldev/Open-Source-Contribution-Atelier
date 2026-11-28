import csv
import io
import json
import zipfile
from itertools import chain

from asgiref.sync import sync_to_async
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import QuerySet

from apps.accounts.models import MentorProfile
from apps.chat.models import Message
from apps.content.models import Comment
from apps.dashboard.models import Issue, PullRequest
from apps.notifications.models import Notification
from apps.progress.models import (
    Certificate,
    CodeSubmission,
    ExerciseAttempt,
    HelpRequest,
    LessonProgress,
    PeerReview,
    QuizAttempt,
    UserBadge,
)
from apps.sandbox.models import SandboxExecutionLog
from apps.webhooks.models import WebhookEndpoint

# Rows fetched from the database, and written, between two chunks of a CSV export.
CHUNK_ROWS = 500


class _ZipBuffer:
    """Write-only sink for ZipFile that hands over whatever has been written."""

    def __init__(self):
        self._parts = []

    def write(self, data):
        self._parts.append(bytes(data))
        return len(data)

    def flush(self):
        pass

    def drain(self):
        data = b"".join(self._parts)
        self._parts.clear()
        return data


async def iterate_async(chunks):
    """
    Serve a synchronous generator under ASGI. Handed a sync iterator, Django
    would read all of it into memory before sending the first byte.
    """
    done = object()
    pull = sync_to_async(next, thread_sensitive=True)
    while (chunk := await pull(chunks, done)) is not done:
        yield chunk


class DataExportService:
    def __init__(self, user):
        self.user = user

    def _sources(self):
        """
        Map each exported entity to a lazy queryset, or to a list for the small
        profile records. The order here is the order of the export.
        """
        return {
            "user_profile": self._get_user_base_data(),
            "mentor_profile": self._get_mentor_profile(),
            "lesson_progress": LessonProgress.objects.filter(user=self.user),
            "help_requests": HelpRequest.objects.filter(user=self.user),
            "certificates": Certificate.objects.filter(user=self.user),
            "earned_badges": UserBadge.objects.filter(user=self.user),
            "quiz_attempts": QuizAttempt.objects.filter(user=self.user),
            "sandbox_logs": SandboxExecutionLog.objects.filter(user=self.user),
            "notifications": Notification.objects.filter(recipient=self.user),
            "pull_requests": PullRequest.objects.filter(user=self.user),
            "assigned_issues": Issue.objects.filter(assigned_to=self.user),
            "webhooks": WebhookEndpoint.objects.filter(user=self.user),
            "exercise_attempts": ExerciseAttempt.objects.filter(user=self.user),
            "code_submissions": CodeSubmission.objects.filter(user=self.user),
            "peer_reviews": PeerReview.objects.filter(reviewer=self.user),
            "comments": Comment.all_objects.filter(user=self.user),
            "messages": Message.objects.filter(user=self.user),
        }

    def gather_data(self):
        """
        Gather all personal data for the user into a structured dictionary.
        """
        return {
            name: (
                self._queryset_to_list(source)
                if isinstance(source, QuerySet)
                else source
            )
            for name, source in self._sources().items()
        }

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

    def _to_dict(self, obj):
        """
        Convert a model instance to a dict, keeping basic serializable fields.
        We exclude foreign keys like user_id as it's implicit, but keep explicit relations.
        """
        return {
            field.name: getattr(obj, field.attname)
            for field in obj._meta.fields
            if field.name not in ["user", "recipient", "assigned_to", "password"]
        }

    def _queryset_to_list(self, qs: QuerySet):
        return [self._to_dict(obj) for obj in qs]

    def _rows(self, source):
        if isinstance(source, QuerySet):
            for obj in source.iterator(chunk_size=CHUNK_ROWS):
                yield self._to_dict(obj)
        else:
            yield from source

    def generate_json(self):
        data = self.gather_data()
        return json.dumps(data, cls=DjangoJSONEncoder, indent=2)

    def stream_csv_zip(self):
        """
        Yield a ZIP archive with one CSV file per data entity, piece by piece, so
        memory use does not grow with the number of rows.
        """
        buffer = _ZipBuffer()

        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for entity_name, source in self._sources().items():
                rows = self._rows(source)
                first = next(rows, None)
                if first is None:
                    continue

                # The size is unknown up front, so allow entries beyond 2 GiB.
                with zf.open(f"{entity_name}.csv", "w", force_zip64=True) as entry:
                    with io.TextIOWrapper(entry, "utf-8", newline="") as text:
                        writer = csv.DictWriter(text, fieldnames=first.keys())
                        writer.writeheader()
                        for count, row in enumerate(chain([first], rows), start=1):
                            writer.writerow(row)
                            if count % CHUNK_ROWS == 0:
                                text.flush()
                                if chunk := buffer.drain():
                                    yield chunk

                if chunk := buffer.drain():
                    yield chunk

        # Closing the archive writes its central directory.
        yield buffer.drain()
