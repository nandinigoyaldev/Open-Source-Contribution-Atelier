import os
import unittest
from datetime import timedelta

import django
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.chat.consumers import ChatConsumer
from apps.chat.models import Message


class ChatHistorySyncTestCase(unittest.TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username=f"chatuser_{os.urandom(4).hex()}",
            email="chatuser@example.com",
            password="password123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.room_id = f"room_{os.urandom(4).hex()}"

        # Seed sequential messages
        self.m1 = Message.objects.create(
            room_id=self.room_id, user=self.user, content="Message 1"
        )
        self.m2 = Message.objects.create(
            room_id=self.room_id, user=self.user, content="Message 2"
        )
        self.m3 = Message.objects.create(
            room_id=self.room_id, user=self.user, content="Message 3"
        )
        self.m4 = Message.objects.create(
            room_id=self.room_id, user=self.user, content="Message 4"
        )
        self.m5 = Message.objects.create(
            room_id=self.room_id, user=self.user, content="Message 5"
        )

    def test_message_list_since_id_filtering(self):
        """Verify GET /api/chat/rooms/<room_id>/messages/?since_id=X filters properly."""
        response = self.client.get(
            f"/api/chat/rooms/{self.room_id}/messages/?since_id={self.m3.id}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        results = data.get("results", data)
        self.assertEqual(len(results), 2)
        ids = [msg["id"] for msg in results]
        self.assertEqual(ids, [self.m4.id, self.m5.id])

    def test_message_sync_endpoint(self):
        """Verify GET /api/chat/rooms/<room_id>/messages/sync/?since_id=X returns missed messages and latest_id."""
        response = self.client.get(
            f"/api/chat/rooms/{self.room_id}/messages/sync/?since_id={self.m2.id}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["room_id"], self.room_id)
        self.assertEqual(data["since_id"], self.m2.id)
        self.assertEqual(data["latest_id"], self.m5.id)
        self.assertFalse(data["resync_required"])
        messages = data["messages"]
        self.assertEqual(len(messages), 3)
        self.assertEqual(
            [m["id"] for m in messages], [self.m3.id, self.m4.id, self.m5.id]
        )

    def test_message_sync_retention_gap_detection(self):
        """Verify retention gap flag is returned when client since_id is older than oldest message."""
        # Delete first 2 messages to simulate message retention purge
        Message.objects.filter(id__in=[self.m1.id, self.m2.id]).delete()

        # Client requests with an ID that has been purged (older than oldest existing message m3)
        purged_id = self.m1.id - 10
        response = self.client.get(
            f"/api/chat/rooms/{self.room_id}/messages/sync/?since_id={purged_id}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data["resync_required"])

    def test_consumer_sync_helpers(self):
        """Verify get_messages_since async helper method on ChatConsumer."""
        import asyncio

        consumer = ChatConsumer()
        consumer.room_id = self.room_id

        async def run_checks():
            msgs = await consumer.get_messages_since(self.m3.id)
            self.assertEqual(len(msgs), 2)
            self.assertEqual([m["id"] for m in msgs], [self.m4.id, self.m5.id])

            gap = await consumer.check_retention_gap(self.m1.id)
            self.assertFalse(gap)

            # Purge m1, m2
            await Message.objects.filter(id__in=[self.m1.id, self.m2.id]).adelete()
            gap_purged = await consumer.check_retention_gap(self.m1.id - 5)
            self.assertTrue(gap_purged)

        asyncio.run(run_checks())
