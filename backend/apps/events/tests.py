"""
Authorization boundary tests for the events app.

@file tests.py
@location backend/apps/events/tests.py
"""

from django.contrib.auth import get_user_model

User = get_user_model()
from django.contrib.contenttypes.models import ContentType
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.events.models import DomainEvent

NO_THROTTLE_SETTINGS = {
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {},
}


@override_settings(REST_FRAMEWORK=NO_THROTTLE_SETTINGS)
class EventListViewAuthorizationTests(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(username="user_a", password="pw12345")
        self.user_b = User.objects.create_user(username="user_b", password="pw12345")
        self.staff = User.objects.create_user(
            username="staff_user", password="pw12345", is_staff=True
        )

        self.event_by_a = DomainEvent.objects.create(
            event_type="progress",
            event_name="lesson_completed",
            actor=self.user_a,
            metadata={"ip_address": "10.0.0.1"},
        )
        self.event_by_b = DomainEvent.objects.create(
            event_type="progress",
            event_name="lesson_completed",
            actor=self.user_b,
            metadata={"ip_address": "10.0.0.2"},
        )

        # An event targeting user_a (e.g. "user_a was awarded a badge")
        user_ct = ContentType.objects.get_for_model(User)
        self.event_targeting_a = DomainEvent.objects.create(
            event_type="moderation",
            event_name="badge_awarded",
            actor=self.user_b,
            content_type=user_ct,
            object_id=self.user_a.id,
        )

        self.list_url = "/api/events/events/"

    def test_unauthenticated_rejected(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_only_sees_own_events_and_events_targeting_them(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = response.data.get("results", response.data)
        returned_ids = {item["id"] for item in results}

        self.assertIn(str(self.event_by_a.id), returned_ids)
        self.assertIn(str(self.event_targeting_a.id), returned_ids)
        self.assertNotIn(str(self.event_by_b.id), returned_ids)

    def test_user_id_query_param_is_ignored_no_leak(self):
        """
        Previously `?user_id=<victim>` let any user filter to another
        user's events. That parameter must now have no effect at all —
        user_a should never see user_b's events regardless of what they
        pass in the query string.
        """
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(self.list_url, {"user_id": self.user_b.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = response.data.get("results", response.data)
        returned_ids = {item["id"] for item in results}
        self.assertNotIn(str(self.event_by_b.id), returned_ids)

    def test_sensitive_metadata_hidden_from_non_owner(self):
        # user_b requests the list; event_targeting_a is visible to them
        # only because they are its actor, not its target — but let's
        # directly check event_by_a is invisible, and for a field-leak
        # test, check event_targeting_a's metadata as seen by user_b
        # (the actor) is exposed, while user_a (the target, not actor)
        # sees it redacted since they aren't staff and aren't the actor.
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/api/events/events/{self.event_targeting_a.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # user_a is the target but not the actor -> metadata redacted
        self.assertEqual(response.data["metadata"], {})

    def test_actor_sees_own_sensitive_metadata(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/api/events/events/{self.event_by_a.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["metadata"], {"ip_address": "10.0.0.1"})

    def test_staff_without_org_does_not_see_others_events(self):
        self.client.force_authenticate(user=self.staff)
        response = self.client.get(self.list_url)
        results = response.data.get("results", response.data)
        returned_ids = {item["id"] for item in results}
        # Staff status alone (no shared org) grants no extra visibility
        self.assertNotIn(str(self.event_by_a.id), returned_ids)
        self.assertNotIn(str(self.event_by_b.id), returned_ids)


@override_settings(REST_FRAMEWORK=NO_THROTTLE_SETTINGS)
class EventDetailViewAuthorizationTests(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(username="detail_a", password="pw12345")
        self.user_b = User.objects.create_user(username="detail_b", password="pw12345")
        self.event = DomainEvent.objects.create(
            event_type="progress", event_name="lesson_completed", actor=self.user_a
        )

    def test_non_owner_cannot_retrieve_event_detail(self):
        self.client.force_authenticate(user=self.user_b)
        response = self.client.get(f"/api/events/events/{self.event.id}/")
        # 404, not 403 — avoids confirming the event's existence to a
        # user who isn't authorized to see it.
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_can_retrieve_own_event_detail(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/api/events/events/{self.event.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
