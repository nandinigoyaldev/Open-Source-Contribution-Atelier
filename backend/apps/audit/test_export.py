import csv
import io
import json
from datetime import datetime, timezone
from unittest import mock

from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.audit import export
from apps.audit.models import AuditEvent

User = get_user_model()

URL = "/api/admin/audit/"


def body(response):
    return b"".join(response.streaming_content).decode("utf-8")


def parse_csv(response):
    return list(csv.reader(io.StringIO(body(response))))


# The per-IP request counter is shared by the whole test process; these tests
# send a lot of requests and are about the export, not about throttling.
@override_settings(DISABLE_RATE_LIMITING=True)
class AuditExportTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="exportadmin", password="pw12345!", is_staff=True
        )
        self.member = User.objects.create_user(username="member", password="pw12345!")
        # creating the users above already wrote audit rows; start from a known set
        AuditEvent.objects.all().delete()
        self.event1 = AuditEvent.objects.create(
            actor=self.admin,
            action="created",
            resource_type="content.lesson",
            resource_id="1001",
            after={"title": "Lesson 1"},
            correlation_id="corr-111",
            ip_address="127.0.0.1",
        )
        self.event2 = AuditEvent.objects.create(
            actor=self.member,
            action="updated",
            resource_type="content.module",
            resource_id="2002",
            before={"title": "Old"},
            after={"title": "New"},
            correlation_id="corr-222",
            ip_address="10.0.0.2",
        )
        self.event3 = AuditEvent.objects.create(
            actor=self.admin,
            action="deleted",
            resource_type="content.lesson",
            resource_id="1001",
            before={"title": "Lesson 1"},
            correlation_id="corr-333",
        )
        self.client.force_authenticate(user=self.admin)

    # permissions

    def test_export_requires_admin(self):
        for fmt in ("csv", "json"):
            with self.subTest(fmt=fmt):
                member_client = APIClient()
                member_client.force_authenticate(user=self.member)
                res = member_client.get(f"{URL}?export={fmt}")
                self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

                res = APIClient().get(f"{URL}?export={fmt}")
                self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    # content type and download headers

    def test_csv_content_type_and_filename(self):
        res = self.client.get(f"{URL}?export=csv")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["Content-Type"], "text/csv")
        self.assertRegex(
            res["Content-Disposition"],
            r'^attachment; filename="audit_logs_\d{4}-\d{2}-\d{2}\.csv"$',
        )

    def test_json_content_type_and_filename(self):
        res = self.client.get(f"{URL}?export=json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["Content-Type"], "application/json")
        self.assertRegex(
            res["Content-Disposition"],
            r'^attachment; filename="audit_logs_\d{4}-\d{2}-\d{2}\.json"$',
        )

    def test_export_is_streamed(self):
        for fmt in ("csv", "json"):
            res = self.client.get(f"{URL}?export={fmt}")
            self.assertTrue(res.streaming, fmt)

    def test_export_reads_with_iterator_not_all_at_once(self):
        with (
            mock.patch.object(export, "EXPORT_CHUNK_SIZE", 2),
            mock.patch.object(
                QuerySet,
                "iterator",
                autospec=True,
                side_effect=lambda qs, chunk_size=2000: iter(list(qs)),
            ) as spy,
        ):
            res = self.client.get(f"{URL}?export=csv")
            body(res)
        self.assertTrue(spy.called)
        self.assertEqual(spy.call_args.kwargs["chunk_size"], 2)

    # content

    def test_csv_rows_and_header(self):
        rows = parse_csv(self.client.get(f"{URL}?export=csv"))
        self.assertEqual(rows[0], export.CSV_HEADER)
        self.assertEqual(len(rows) - 1, 3)
        by_id = {row[0]: row for row in rows[1:]}
        row = by_id[str(self.event2.id)]
        self.assertEqual(row[2], "member")
        self.assertEqual(row[3], "updated")
        self.assertEqual(row[4], "content.module")
        self.assertEqual(row[5], "2002")
        self.assertEqual(row[7], "corr-222")
        self.assertEqual(row[8], "10.0.0.2")

    def test_json_is_a_valid_array_with_full_events(self):
        data = json.loads(body(self.client.get(f"{URL}?export=json")))
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 3)
        item = next(d for d in data if d["id"] == self.event2.id)
        self.assertEqual(item["before"], {"title": "Old"})
        self.assertEqual(item["after"], {"title": "New"})
        self.assertEqual(item["actor_username"], "member")
        self.assertIn("summary", item)

    def test_export_ignores_pagination(self):
        res = self.client.get(f"{URL}?export=json&page=2&page_size=1")
        self.assertEqual(len(json.loads(body(res))), 3)

    def test_more_rows_than_one_chunk(self):
        AuditEvent.objects.bulk_create(
            AuditEvent(
                action="created",
                resource_type="bulk.thing",
                resource_id=str(i),
            )
            for i in range(export.EXPORT_CHUNK_SIZE + 120)
        )
        total = AuditEvent.objects.count()
        rows = parse_csv(self.client.get(f"{URL}?export=csv"))
        self.assertEqual(len(rows) - 1, total)
        data = json.loads(body(self.client.get(f"{URL}?export=json")))
        self.assertEqual(len(data), total)

    def test_csv_cells_cannot_start_a_formula(self):
        AuditEvent.objects.create(
            action="created",
            resource_type="=HYPERLINK(1)",
            resource_id="1",
            user_agent="@evil",
        )
        rows = parse_csv(self.client.get(f"{URL}?export=csv&search=evil"))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][4], "'=HYPERLINK(1)")

    # filters

    def test_filters_are_applied_to_both_formats(self):
        cases = {
            "action=created": {self.event1.id},
            "action=deleted": {self.event3.id},
            "actor=member": {self.event2.id},
            "model_type=module": {self.event2.id},
            "search=corr-333": {self.event3.id},
            "resource_id=1001": {self.event1.id, self.event3.id},
            "action=created&model_type=lesson": {self.event1.id},
        }
        for query, expected in cases.items():
            with self.subTest(query=query):
                csv_ids = {
                    int(r[0])
                    for r in parse_csv(self.client.get(f"{URL}?export=csv&{query}"))[1:]
                }
                json_ids = {
                    d["id"]
                    for d in json.loads(
                        body(self.client.get(f"{URL}?export=json&{query}"))
                    )
                }
                list_ids = {
                    d["id"] for d in self.client.get(f"{URL}?{query}").data["results"]
                }
                self.assertEqual(csv_ids, expected)
                self.assertEqual(json_ids, expected)
                self.assertEqual(list_ids, expected)

    def test_date_range_filter(self):
        old = AuditEvent.objects.create(
            action="created",
            resource_type="old.thing",
            resource_id="9",
            created_at=datetime(2020, 1, 1, 12, 0, tzinfo=timezone.utc),
        )
        res = self.client.get(
            f"{URL}?export=json&start_date=2019-12-31T00:00:00Z"
            "&end_date=2020-01-02T00:00:00Z"
        )
        self.assertEqual([d["id"] for d in json.loads(body(res))], [old.id])

    # empty result

    def test_empty_csv_has_only_the_header(self):
        res = self.client.get(f"{URL}?export=csv&search=no-such-thing")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(parse_csv(res), [export.CSV_HEADER])

    def test_empty_json_is_an_empty_array(self):
        res = self.client.get(f"{URL}?export=json&search=no-such-thing")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["Content-Type"], "application/json")
        self.assertEqual(json.loads(body(res)), [])

    # format handling

    def test_unknown_export_format_is_a_400(self):
        res = self.client.get(f"{URL}?export=xml")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("csv", res.json()["detail"])

    def test_format_is_case_insensitive(self):
        res = self.client.get(f"{URL}?export=CSV")
        self.assertEqual(res["Content-Type"], "text/csv")

    def test_plain_list_is_still_json_pages(self):
        res = self.client.get(URL)
        self.assertFalse(getattr(res, "streaming", False))
        self.assertIn("results", res.data)
