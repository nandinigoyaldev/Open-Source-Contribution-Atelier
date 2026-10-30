"""Filters and pagination of GET /api/admin/audit/ (issue #3248)."""

import csv
import io
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.http import QueryDict
from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.audit.filters import DATE_HELP, parse_audit_filters
from apps.audit.models import AuditEvent

User = get_user_model()
URL = "/api/admin/audit/"


def local(year, month, day, hour=0, minute=0, second=0, microsecond=0):
    """A moment in the server's configured time zone, which is how plain dates are read."""
    return timezone.make_aware(
        datetime(year, month, day, hour, minute, second, microsecond)
    )


def parse(query: str):
    return parse_audit_filters(QueryDict(query))


class ParseAuditFiltersTests(SimpleTestCase):
    def test_no_parameters_means_no_filters(self):
        filters, errors = parse("")
        self.assertEqual(errors, {})
        self.assertIsNone(filters.start)
        self.assertIsNone(filters.end)
        self.assertEqual(filters.action, "")

    def test_a_plain_start_date_begins_at_midnight(self):
        filters, errors = parse("start_date=2026-01-10")
        self.assertEqual(errors, {})
        self.assertEqual(filters.start, local(2026, 1, 10))

    def test_a_plain_end_date_covers_the_whole_day(self):
        filters, errors = parse("end_date=2026-01-31")
        self.assertEqual(errors, {})
        self.assertEqual(filters.end, local(2026, 2, 1))
        self.assertFalse(filters.end_inclusive)

    def test_a_datetime_bound_is_used_exactly(self):
        filters, errors = parse(
            "start_date=2026-01-10T08:30:00Z&end_date=2026-01-10T15:00:00%2B05:30"
        )
        self.assertEqual(errors, {})
        self.assertEqual(
            filters.start, datetime(2026, 1, 10, 8, 30, tzinfo=dt_timezone.utc)
        )
        self.assertEqual(filters.end - filters.start, timedelta(hours=1))
        self.assertTrue(filters.end_inclusive)

    def test_impossible_and_malformed_dates_are_errors_not_exceptions(self):
        for bad in [
            "not-a-date",
            "2026-02-30",
            "2026-13-01",
            "01/02/2026",
            "2026-01-01T25:00:00",
            "9" * 30,
        ]:
            for name in ("start_date", "end_date"):
                _filters, errors = parse(f"{name}={bad}")
                self.assertEqual(errors, {name: [DATE_HELP]}, f"{name}={bad}")

    def test_both_bad_dates_are_reported_together(self):
        _filters, errors = parse("start_date=x&end_date=y")
        self.assertEqual(set(errors), {"start_date", "end_date"})

    def test_a_blank_date_is_ignored(self):
        filters, errors = parse("start_date=&end_date=%20")
        self.assertEqual(errors, {})
        self.assertIsNone(filters.start)
        self.assertIsNone(filters.end)

    def test_start_after_end_is_an_error(self):
        _filters, errors = parse("start_date=2026-02-01&end_date=2026-01-31")
        self.assertEqual(
            errors, {"end_date": ["End date must not be before the start date."]}
        )

    def test_a_one_day_range_is_valid(self):
        _filters, errors = parse("start_date=2026-02-01&end_date=2026-02-01")
        self.assertEqual(errors, {})

    def test_action_must_be_one_of_the_known_actions(self):
        filters, errors = parse("action=Created")
        self.assertEqual((filters.action, errors), ("created", {}))
        _filters, errors = parse("action=exploded")
        self.assertIn("created, updated, deleted", errors["action"][0])

    def test_old_and_new_names_for_the_same_filter_both_work(self):
        self.assertEqual(parse("model_type=lesson")[0].resource_type, "lesson")
        self.assertEqual(parse("resource_type=module")[0].resource_type, "module")
        self.assertEqual(parse("q=abc")[0].search, "abc")
        self.assertEqual(parse("search=xyz")[0].search, "xyz")

    def test_text_filters_are_trimmed_and_length_limited(self):
        self.assertEqual(parse("actor=%20ann%20")[0].actor, "ann")
        _filters, errors = parse("actor=" + "a" * 101)
        self.assertIn("actor", errors)


class AuditListFilterApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            "admin1", "admin1@example.com", "pw", is_staff=True
        )
        cls.ann = User.objects.create_user("ann", "ann@example.com", "pw")
        cls.raj = User.objects.create_user("raj", "raj@example.com", "pw")
        # creating users already wrote audit events through the signals; start from an empty log
        AuditEvent.objects.all().delete()

        def make(actor, action, resource_type, resource_id, when, operation=None):
            extra = {"operation": operation} if operation else {}
            return AuditEvent.objects.create(
                actor=actor,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                created_at=when,
                extra=extra,
            )

        cls.jan01_morning = make(
            cls.ann, "created", "content.lesson", "1", local(2026, 1, 1, 9)
        )
        cls.jan15_noon = make(
            cls.ann,
            "updated",
            "content.lesson",
            "2",
            local(2026, 1, 15, 12),
            "issue.updated",
        )
        cls.jan31_late = make(
            cls.raj,
            "updated",
            "content.module",
            "3",
            local(2026, 1, 31, 23, 59, 59, 500000),
            "issue.updated",
        )
        cls.feb01_early = make(
            cls.raj,
            "deleted",
            "content.lesson",
            "4",
            local(2026, 2, 1, 0, 0, 0),
            "issue.deleted",
        )
        cls.feb10 = make(
            cls.ann, "created", "content.module", "5", local(2026, 2, 10, 8)
        )

    def setUp(self):
        self.client.force_authenticate(user=self.admin)

    def ids(self, query=""):
        response = self.client.get(f"{URL}?{query}")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        return {row["id"] for row in response.data["results"]}, response.data["count"]

    def test_date_range_is_inclusive_of_both_whole_days(self):
        ids, count = self.ids("start_date=2026-01-01&end_date=2026-01-31")
        self.assertEqual(
            ids, {self.jan01_morning.id, self.jan15_noon.id, self.jan31_late.id}
        )
        self.assertEqual(count, 3)

    def test_end_date_alone_includes_everything_up_to_the_end_of_that_day(self):
        ids, _ = self.ids("end_date=2026-01-31")
        self.assertIn(self.jan31_late.id, ids)
        self.assertNotIn(self.feb01_early.id, ids)

    def test_start_date_alone_excludes_the_day_before(self):
        ids, _ = self.ids("start_date=2026-02-01")
        self.assertEqual(ids, {self.feb01_early.id, self.feb10.id})

    def test_a_datetime_range_cuts_inside_a_day(self):
        iso = local(2026, 1, 15, 11).isoformat().replace("+", "%2B")
        iso_end = local(2026, 1, 15, 13).isoformat().replace("+", "%2B")
        ids, _ = self.ids(f"start_date={iso}&end_date={iso_end}")
        self.assertEqual(ids, {self.jan15_noon.id})

    def test_combined_filters_are_anded(self):
        ids, count = self.ids(
            "start_date=2026-01-01&end_date=2026-01-31&actor=ann&action=updated&resource_type=lesson"
        )
        self.assertEqual((ids, count), ({self.jan15_noon.id}, 1))

    def test_combining_actor_and_operation_and_dates(self):
        ids, _ = self.ids(
            "actor=raj&operation=issue.updated&start_date=2026-01-01&end_date=2026-02-28"
        )
        self.assertEqual(ids, {self.jan31_late.id})

    def test_operation_alone_is_an_exact_match(self):
        ids, _ = self.ids("operation=issue.updated")
        self.assertEqual(ids, {self.jan15_noon.id, self.jan31_late.id})
        self.assertEqual(self.ids("operation=issue")[0], set())

    def test_actor_by_id_and_by_name(self):
        self.assertEqual(
            self.ids(f"actor={self.raj.id}")[0],
            {self.jan31_late.id, self.feb01_early.id},
        )
        self.assertEqual(
            self.ids("actor=RA")[0], {self.jan31_late.id, self.feb01_early.id}
        )

    def test_filters_that_match_nothing_give_an_empty_page_not_an_error(self):
        response = self.client.get(f"{URL}?actor=ann&action=deleted")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual((response.data["count"], response.data["results"]), (0, []))

    def test_unfiltered_list_is_newest_first(self):
        response = self.client.get(URL)
        stamps = [row["created_at"] for row in response.data["results"]]
        self.assertEqual(stamps, sorted(stamps, reverse=True))
        self.assertEqual(response.data["count"], 5)

    # ---- invalid input ----------------------------------------------------

    def test_invalid_dates_are_a_400_naming_the_field(self):
        for bad in ["not-a-date", "2026-02-30", "2026-13-01"]:
            for name in ("start_date", "end_date"):
                response = self.client.get(f"{URL}?{name}={bad}")
                self.assertEqual(
                    response.status_code, status.HTTP_400_BAD_REQUEST, f"{name}={bad}"
                )
                self.assertEqual(response.data["errors"], {name: [DATE_HELP]})

    def test_start_after_end_is_a_400(self):
        response = self.client.get(f"{URL}?start_date=2026-02-01&end_date=2026-01-01")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("end_date", response.data["errors"])

    def test_unknown_action_is_a_400_not_an_empty_list(self):
        response = self.client.get(f"{URL}?action=exploded")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("action", response.data["errors"])

    def test_several_bad_values_are_all_reported(self):
        response = self.client.get(f"{URL}?start_date=x&action=y")
        self.assertEqual(set(response.data["errors"]), {"start_date", "action"})

    def test_an_invalid_filter_never_returns_unfiltered_data(self):
        response = self.client.get(f"{URL}?start_date=garbage")
        self.assertNotIn("results", response.data)

    # ---- pagination -------------------------------------------------------

    def test_result_count_is_the_total_not_the_page_size(self):
        response = self.client.get(f"{URL}?page_size=2")
        self.assertEqual(response.data["count"], 5)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertIsNotNone(response.data["next"])
        self.assertIsNone(response.data["previous"])

    def test_pages_are_disjoint_and_the_last_one_is_partial(self):
        seen = []
        for page, expected_len in [(1, 2), (2, 2), (3, 1)]:
            response = self.client.get(f"{URL}?page_size=2&page={page}")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data["results"]), expected_len)
            seen.extend(row["id"] for row in response.data["results"])
        self.assertEqual(len(seen), 5)
        self.assertEqual(len(set(seen)), 5)
        last = self.client.get(f"{URL}?page_size=2&page=3")
        self.assertIsNone(last.data["next"])
        self.assertIsNotNone(last.data["previous"])

    def test_an_exact_multiple_has_no_extra_empty_page(self):
        response = self.client.get(f"{URL}?page_size=5")
        self.assertEqual(len(response.data["results"]), 5)
        self.assertIsNone(response.data["next"])
        self.assertEqual(
            self.client.get(f"{URL}?page_size=5&page=2").status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_a_page_past_the_end_is_a_404(self):
        for page in ("4", "99"):
            response = self.client.get(f"{URL}?page_size=2&page={page}")
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_page_zero_negative_and_garbage_are_rejected(self):
        for page in ("0", "-1", "abc"):
            response = self.client.get(f"{URL}?page={page}")
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND, page)

    def test_page_size_is_capped_and_bad_sizes_fall_back_to_the_default(self):
        for i in range(120):
            AuditEvent.objects.create(
                actor=self.ann,
                action="created",
                resource_type="bulk.item",
                resource_id=str(i),
            )
        self.assertEqual(
            len(self.client.get(f"{URL}?page_size=1000").data["results"]), 100
        )
        for size in ("0", "-5", "abc", ""):
            self.assertEqual(
                len(self.client.get(f"{URL}?page_size={size}").data["results"]),
                20,
                size,
            )

    def test_pagination_keeps_the_filters(self):
        response = self.client.get(f"{URL}?actor=ann&page_size=1")
        self.assertEqual(response.data["count"], 3)
        self.assertIn("actor=ann", response.data["next"])
        second = self.client.get(f"{URL}?actor=ann&page_size=1&page=2")
        self.assertEqual(second.data["count"], 3)

    # ---- export -----------------------------------------------------------

    def test_export_uses_the_same_filters_and_not_the_page(self):
        response = self.client.get(f"{URL}?export=csv&action=updated&page_size=1")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = list(csv.reader(io.StringIO(response.content.decode())))
        self.assertEqual(len(rows) - 1, 2)

    def test_export_rejects_invalid_filters(self):
        response = self.client.get(f"{URL}?export=csv&end_date=nope")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class AuditListAccessTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            "admin2", "admin2@example.com", "pw", is_staff=True
        )
        cls.member = User.objects.create_user("member", "member@example.com", "pw")
        cls.event = AuditEvent.objects.create(
            actor=cls.admin, action="created", resource_type="x.y", resource_id="1"
        )

    def test_non_admins_are_refused_whatever_the_filters(self):
        self.client.force_authenticate(user=self.member)
        for query in [
            "",
            "action=created",
            "start_date=2026-01-01&end_date=2026-12-31",
            "start_date=garbage",
            "export=csv",
            "page=9",
        ]:
            response = self.client.get(f"{URL}?{query}")
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, query)
            self.assertNotIn("results", response.data)

    def test_anonymous_requests_are_refused(self):
        anonymous = APIClient()
        for query in ["", "actor=admin2", "start_date=garbage", "export=json"]:
            self.assertEqual(
                anonymous.get(f"{URL}?{query}").status_code,
                status.HTTP_401_UNAUTHORIZED,
                query,
            )

    def test_the_detail_view_stays_admin_only(self):
        self.client.force_authenticate(user=self.member)
        self.assertEqual(
            self.client.get(f"{URL}{self.event.id}/").status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.client.force_authenticate(user=self.admin)
        self.assertEqual(
            self.client.get(f"{URL}{self.event.id}/").status_code, status.HTTP_200_OK
        )

    def test_an_admin_can_use_every_filter_together(self):
        self.client.force_authenticate(user=self.admin)
        today = timezone.localdate().isoformat()
        response = self.client.get(
            f"{URL}?actor=admin2&action=created&resource_type=x.y&start_date={today}&end_date={today}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
