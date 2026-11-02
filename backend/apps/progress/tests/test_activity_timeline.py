"""Personal learning activity timeline (issue #3184)."""

from datetime import datetime, timedelta, timezone

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.content.models import Lesson
from apps.progress.models import (
    Badge,
    Certificate,
    LessonProgress,
    QuizAttempt,
    UserBadge,
)
from apps.progress.services.activity_timeline import (
    ACTIVITY_TYPES,
    Cursor,
    TimelineError,
    get_activity_timeline,
    parse_limit,
    parse_types,
)

User = get_user_model()
URL = "/api/progress/activity/"
BASE = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def at(minutes: int) -> datetime:
    return BASE + timedelta(minutes=minutes)


class TimelineTestBase(TestCase):
    def setUp(self):
        cache.clear()  # the API is rate limited per user; each test starts fresh
        self.addCleanup(cache.clear)
        self.user = User.objects.create_user(
            username="learner", password="Password123!", email="learner@example.com"
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self._lesson_n = 0

    # -- builders: the model timestamps are automatic, so they are set after creation --

    def lesson_done(
        self, minutes, title="A lesson", score=80, user=None, completed=True
    ):
        self._lesson_n += 1
        lesson = Lesson.objects.create(
            title=title,
            slug=f"lesson-{self._lesson_n}",
            difficulty="beginner",
            summary="s",
            content="c",
        )
        row = LessonProgress.objects.create(
            user=user or self.user, lesson=lesson, completed=completed, score=score
        )
        LessonProgress.objects.filter(pk=row.pk).update(updated_at=at(minutes))
        return row

    def quiz(self, minutes, correct=True, text="What is a fork?", user=None):
        row = QuizAttempt.objects.create(
            user=user or self.user,
            question_id=f"q{minutes}",
            question_text=text,
            selected_answer="a",
            correct_answer="a" if correct else "b",
            is_correct=correct,
            time_taken_seconds=12,
        )
        QuizAttempt.objects.filter(pk=row.pk).update(created_at=at(minutes))
        return row

    def certificate(self, minutes, active=True, user=None):
        row = Certificate.objects.create(
            user=user or self.user, course_name="Open Source Course", is_active=active
        )
        Certificate.objects.filter(pk=row.pk).update(issued_at=at(minutes))
        return row

    def badge(self, minutes, name="First steps", user=None):
        badge, _ = Badge.objects.get_or_create(
            slug=name.lower().replace(" ", "-"),
            defaults={"name": name, "description": f"{name} badge", "category": "git"},
        )
        row = UserBadge.objects.create(user=user or self.user, badge=badge)
        UserBadge.objects.filter(pk=row.pk).update(earned_at=at(minutes))
        return row

    def get(self, **params):
        return self.client.get(URL, params)

    def ids(self, response):
        return [item["id"] for item in response.data["results"]]


class ResponseShapeTests(TimelineTestBase):
    def test_every_item_has_the_documented_fields(self):
        self.lesson_done(1, title="Git basics")
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            sorted(response.data),
            ["has_more", "limit", "next_cursor", "results", "types"],
        )
        [item] = response.data["results"]
        self.assertEqual(
            sorted(item),
            ["description", "id", "metadata", "occurred_at", "title", "type"],
        )
        self.assertEqual(item["type"], "lesson_completed")
        self.assertEqual(item["title"], "Git basics")
        self.assertEqual(item["description"], "Score 80")
        self.assertEqual(item["metadata"]["score"], 80)
        self.assertTrue(item["id"].startswith("lesson_completed:"))
        self.assertEqual(item["occurred_at"], at(1).isoformat())

    def test_each_type_describes_itself(self):
        self.lesson_done(1)
        self.quiz(2, correct=False, text="  What   is\ta fork? ")
        self.certificate(3)
        self.badge(4, name="First steps")
        by_type = {i["type"]: i for i in self.get().data["results"]}
        self.assertEqual(by_type["quiz_attempt"]["title"], "What is a fork?")
        self.assertEqual(by_type["quiz_attempt"]["description"], "Incorrect")
        self.assertFalse(by_type["quiz_attempt"]["metadata"]["is_correct"])
        self.assertEqual(by_type["certificate_issued"]["title"], "Open Source Course")
        self.assertIn("verification_hash", by_type["certificate_issued"]["metadata"])
        self.assertEqual(by_type["badge_earned"]["title"], "First steps")
        self.assertEqual(
            by_type["badge_earned"]["metadata"]["badge_slug"], "first-steps"
        )

    def test_long_titles_are_shortened(self):
        self.quiz(1, text="x" * 500)
        title = self.get().data["results"][0]["title"]
        self.assertLessEqual(len(title), 140)
        self.assertTrue(title.endswith("…"))

    def test_ids_are_unique_across_types_with_the_same_primary_key(self):
        self.lesson_done(1)
        self.quiz(2)
        ids = self.ids(self.get())
        self.assertEqual(len(ids), len(set(ids)))

    def test_empty_history_returns_an_empty_page_not_an_error(self):
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])
        self.assertFalse(response.data["has_more"])
        self.assertIsNone(response.data["next_cursor"])
        self.assertEqual(response.data["types"], list(ACTIVITY_TYPES))


class OrderingAndScopeTests(TimelineTestBase):
    def test_newest_first_across_all_types(self):
        a = self.lesson_done(10)
        b = self.quiz(30)
        c = self.certificate(20)
        d = self.badge(40)
        self.assertEqual(
            self.ids(self.get()),
            [
                f"badge_earned:{d.pk}",
                f"quiz_attempt:{b.pk}",
                f"certificate_issued:{c.pk}",
                f"lesson_completed:{a.pk}",
            ],
        )

    def test_only_completed_lessons_and_active_certificates_count(self):
        self.lesson_done(1, completed=False)
        self.certificate(2, active=False)
        done = self.lesson_done(3)
        self.assertEqual(self.ids(self.get()), [f"lesson_completed:{done.pk}"])

    def test_other_users_activity_is_never_shown(self):
        other = User.objects.create_user(username="other", password="Password123!")
        self.lesson_done(1, user=other)
        self.quiz(2, user=other)
        self.certificate(3, user=other)
        self.badge(4, user=other)
        mine = self.quiz(5)
        self.assertEqual(self.ids(self.get()), [f"quiz_attempt:{mine.pk}"])

    def test_requires_authentication(self):
        response = APIClient().get(URL)
        self.assertEqual(response.status_code, 401)

    def test_it_only_reads(self):
        for method in ("post", "put", "patch", "delete"):
            response = getattr(self.client, method)(URL, {})
            self.assertEqual(response.status_code, 405, method)


class FilterTests(TimelineTestBase):
    def setUp(self):
        super().setUp()
        self.lesson = self.lesson_done(1)
        self.quizzes = [self.quiz(2), self.quiz(3)]
        self.cert = self.certificate(4)
        self.badge_row = self.badge(5)

    def test_one_type(self):
        response = self.get(type="quiz_attempt")
        self.assertEqual(response.data["types"], ["quiz_attempt"])
        self.assertEqual(
            self.ids(response), [f"quiz_attempt:{q.pk}" for q in reversed(self.quizzes)]
        )

    def test_several_types_repeated_or_comma_separated(self):
        expected = [
            f"certificate_issued:{self.cert.pk}",
            f"lesson_completed:{self.lesson.pk}",
        ]
        repeated = self.client.get(
            URL + "?type=lesson_completed&type=certificate_issued"
        )
        comma = self.get(type="certificate_issued, lesson_completed")
        self.assertEqual(self.ids(repeated), expected)
        self.assertEqual(self.ids(comma), expected)

    def test_the_order_of_the_filter_does_not_change_the_result(self):
        a = self.get(type="badge_earned,lesson_completed")
        b = self.get(type="lesson_completed,badge_earned")
        self.assertEqual(a.data, b.data)

    def test_a_type_with_no_activity_is_an_empty_page(self):
        QuizAttempt.objects.all().delete()
        response = self.get(type="quiz_attempt")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])

    def test_an_unknown_type_is_rejected_and_names_the_valid_ones(self):
        response = self.get(type="lesson_completed,lessons")
        self.assertEqual(response.status_code, 400)
        self.assertIn("lessons", response.data["error"])
        self.assertIn("badge_earned", response.data["error"])

    def test_empty_type_means_everything(self):
        self.assertEqual(len(self.get(type="").data["results"]), 5)


class PaginationTests(TimelineTestBase):
    def walk(self, limit, **params):
        seen, cursor, pages = [], None, 0
        while True:
            query = dict(params, limit=limit)
            if cursor:
                query["cursor"] = cursor
            response = self.get(**query)
            self.assertEqual(response.status_code, 200)
            seen.extend(self.ids(response))
            pages += 1
            if not response.data["has_more"]:
                self.assertIsNone(response.data["next_cursor"])
                return seen, pages
            cursor = response.data["next_cursor"]
            self.assertTrue(cursor)
            self.assertLess(pages, 100, "pagination did not terminate")

    def test_pages_cover_everything_exactly_once_in_order(self):
        for i in range(7):
            self.lesson_done(i * 4)
            self.quiz(i * 4 + 1)
            self.certificate(i * 4 + 2)
            self.badge(i * 4 + 3, name=f"Badge {i}")
        full = self.ids(self.get(limit=100))
        self.assertEqual(len(full), 28)
        for limit in (7, 14, 28):
            seen, _ = self.walk(limit)
            self.assertEqual(seen, full, f"limit={limit}")

    def test_items_with_the_same_timestamp_are_not_skipped_or_repeated(self):
        for _ in range(4):
            self.lesson_done(5)
            self.quiz(5)
            self.certificate(5)
            self.badge(5, name=f"B{_}")
        full = self.ids(self.get(limit=100))
        self.assertEqual(len(full), 16)
        for limit in (3, 5):
            seen, _ = self.walk(limit)
            self.assertEqual(seen, full, f"limit={limit}")

    def test_filtered_pagination(self):
        for i in range(9):
            self.quiz(i)
            self.lesson_done(i)
        seen, _ = self.walk(4, type="quiz_attempt")
        self.assertEqual(len(seen), 9)
        self.assertTrue(all(i.startswith("quiz_attempt:") for i in seen))

    def test_has_more_is_exact_on_the_boundary(self):
        for i in range(5):
            self.quiz(i)
        exact = self.get(limit=5)
        self.assertFalse(exact.data["has_more"])
        short = self.get(limit=4)
        self.assertTrue(short.data["has_more"])
        last = self.get(limit=4, cursor=short.data["next_cursor"])
        self.assertEqual(len(last.data["results"]), 1)
        self.assertFalse(last.data["has_more"])

    def test_new_activity_does_not_shift_the_next_page(self):
        for i in range(6):
            self.quiz(i)
        first = self.get(limit=3)
        self.quiz(100)  # something new arrives after page one was loaded
        second = self.get(limit=3, cursor=first.data["next_cursor"])
        self.assertEqual(
            self.ids(first) + self.ids(second), self.ids(self.get(limit=100))[1:]
        )

    def test_the_cursor_is_opaque_and_url_safe(self):
        for i in range(3):
            self.quiz(i)
        cursor = self.get(limit=1).data["next_cursor"]
        self.assertRegex(cursor, r"^[A-Za-z0-9_-]+$")

    def test_limit_rules(self):
        self.assertEqual(self.get().data["limit"], 20)
        self.assertEqual(self.get(limit=500).data["limit"], 100)
        for bad in ("0", "-1", "abc", "1.5"):
            self.assertEqual(self.get(limit=bad).status_code, 400, bad)

    def test_bad_cursors_are_rejected(self):
        for bad in ("garbage", "e30", "W10", "!!!", "a" * 400):
            response = self.get(cursor=bad)
            self.assertEqual(response.status_code, 400, bad)
            self.assertIn("cursor", response.data["error"].lower())

    def test_a_cursor_cannot_be_used_to_read_someone_elses_activity(self):
        other = User.objects.create_user(username="other", password="Password123!")
        theirs = self.quiz(50, user=other)
        forged = Cursor(at(60), "quiz_attempt", theirs.pk + 1).encode()
        self.assertEqual(self.ids(self.get(cursor=forged)), [])

    def test_the_cost_does_not_grow_with_the_amount_of_history(self):
        def timeline_queries(**params):
            with CaptureQueriesContext(connection) as captured:
                self.assertEqual(self.get(**params).status_code, 200)
            # Middleware adds its own queries (session, billing); count only the timeline's.
            return [q for q in captured.captured_queries if '"progress_' in q["sql"]]

        for i in range(5):
            self.lesson_done(i)
            self.quiz(i)
            self.certificate(i)
            self.badge(i, name=f"B{i}")
        small = len(timeline_queries(limit=10))

        for i in range(5, 40):
            self.lesson_done(i)
            self.quiz(i)
            self.certificate(i)
            self.badge(i, name=f"B{i}")
        large_page = len(timeline_queries(limit=100))
        later_page = len(
            timeline_queries(limit=10, cursor=self.get(limit=10).data["next_cursor"])
        )

        self.assertEqual(small, 4, "one query per source, joined to what it displays")
        self.assertEqual(large_page, 4)
        self.assertEqual(later_page, 4)


class ServiceUnitTests(TestCase):
    def test_parse_types(self):
        self.assertEqual(parse_types(None), ACTIVITY_TYPES)
        self.assertEqual(parse_types([]), ACTIVITY_TYPES)
        self.assertEqual(parse_types(["quiz_attempt, quiz_attempt"]), ("quiz_attempt",))
        with self.assertRaises(TimelineError):
            parse_types(["nope"])

    def test_parse_limit(self):
        self.assertEqual(parse_limit(None), 20)
        self.assertEqual(parse_limit(""), 20)
        self.assertEqual(parse_limit("7"), 7)
        self.assertEqual(parse_limit("1000"), 100)
        with self.assertRaises(TimelineError):
            parse_limit("0")

    def test_cursor_round_trip(self):
        cursor = Cursor(at(5), "badge_earned", 42)
        self.assertEqual(Cursor.decode(cursor.encode()), cursor)

    def test_cursor_rejects_unknown_types_and_bad_keys(self):
        import base64
        import json

        def enc(value):
            return base64.urlsafe_b64encode(json.dumps(value).encode()).decode()

        for bad in (
            ["2026-10-01T12:00:00+00:00", "nope", 1],
            ["2026-10-01T12:00:00+00:00", "quiz_attempt", "1"],
            ["2026-10-01T12:00:00+00:00", "quiz_attempt", True],
            ["not a date", "quiz_attempt", 1],
            ["2026-10-01T12:00:00+00:00", "quiz_attempt"],
            {"a": 1},
        ):
            with self.assertRaises(TimelineError):
                Cursor.decode(enc(bad))

    def test_service_returns_the_same_shape_without_http(self):
        user = User.objects.create_user(username="svc", password="Password123!")
        page = get_activity_timeline(user)
        self.assertEqual(page["results"], [])
        self.assertEqual(page["limit"], 20)
