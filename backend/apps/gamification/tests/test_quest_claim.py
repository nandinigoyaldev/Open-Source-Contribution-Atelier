import pytest
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.utils import timezone
from rest_framework.test import APIClient

from apps.gamification.models import Quest, UserQuest
from apps.progress.models import XPEvent

User = get_user_model()
URL = "/api/gamification/my-quests/"


def _completed_quest(user, xp_reward=100, expires_in_days=1):
    quest = Quest.objects.create(
        title="Weekly",
        description="d",
        quest_type="complete_lessons",
        requirement_count=1,
        xp_reward=xp_reward,
    )
    return UserQuest.objects.create(
        user=user,
        quest=quest,
        progress=1,
        completed=True,
        expires_at=timezone.now() + timezone.timedelta(days=expires_in_days),
    )


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _milestone_events(user):
    return XPEvent.objects.filter(user=user, source_type="milestone")


@pytest.mark.django_db
def test_claim_awards_xp_once_and_rejects_repeat():
    user = User.objects.create_user(username="claimer", password="pw")
    uq = _completed_quest(user, xp_reward=100)
    client = _client(user)

    first = client.post(URL, {"quest_id": uq.id}, format="json")
    second = client.post(URL, {"quest_id": uq.id}, format="json")

    assert first.status_code == 200
    assert first.data == {"xp_awarded": 100}
    assert second.status_code == 404
    assert _milestone_events(user).count() == 1
    uq.refresh_from_db()
    assert uq.reward_claimed is True


@pytest.mark.django_db
def test_second_claim_arriving_mid_request_does_not_double_award():
    """Simulates two overlapping requests on one connection.

    The first request is still inside its claim when the XPEvent is saved; the
    post_save hook fires the "second request" at exactly that point. On the old
    code the flag was only written after the XPEvent, so both requests passed
    the reward_claimed=False lookup and the quest paid twice.
    """
    user = User.objects.create_user(username="racer", password="pw")
    uq = _completed_quest(user, xp_reward=100)
    client = _client(user)
    inner = []

    def fire_second_claim(sender, instance, created, **kwargs):
        if created and instance.source_type == "milestone" and not inner:
            inner.append(client.post(URL, {"quest_id": uq.id}, format="json"))

    post_save.connect(fire_second_claim, sender=XPEvent, dispatch_uid="race_sim")
    try:
        outer = client.post(URL, {"quest_id": uq.id}, format="json")
    finally:
        post_save.disconnect(sender=XPEvent, dispatch_uid="race_sim")

    assert outer.status_code == 200
    assert [r.status_code for r in inner] == [404]
    assert _milestone_events(user).count() == 1


@pytest.mark.django_db
def test_expired_completed_quest_cannot_be_claimed():
    user = User.objects.create_user(username="late", password="pw")
    uq = _completed_quest(user, expires_in_days=-1)

    res = _client(user).post(URL, {"quest_id": uq.id}, format="json")

    assert res.status_code == 404
    assert _milestone_events(user).count() == 0
    uq.refresh_from_db()
    assert uq.reward_claimed is False


@pytest.mark.django_db
def test_reward_above_base_points_cap_is_still_paid():
    user = User.objects.create_user(username="bigreward", password="pw")
    uq = _completed_quest(user, xp_reward=1500)

    res = _client(user).post(URL, {"quest_id": uq.id}, format="json")

    assert res.status_code == 200
    event = _milestone_events(user).get()
    assert event.xp_delta == 1500
    assert event.base_points == 1000
