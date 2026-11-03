import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.gamification.models import Quest, ShopItem, UserQuest
from apps.progress.models import XPEvent

User = get_user_model()


def _xp(user, delta, source_type="bonus"):
    return XPEvent.objects.create(
        user=user,
        source_type=source_type,
        source_id=1,
        base_points=abs(delta),
        multiplier=1.0,
        xp_delta=delta,
    )


def _earn_xp_quest(user, requirement=500):
    quest = Quest.objects.create(
        title="Earn XP",
        description="d",
        quest_type="earn_xp",
        requirement_count=requirement,
    )
    return UserQuest.objects.create(
        user=user, quest=quest, expires_at=timezone.now() + timezone.timedelta(days=1)
    )


def _buy(user, cost):
    item = ShopItem.objects.create(name="Thing", cost=cost, is_active=True)
    client = APIClient()
    client.force_authenticate(user=user)
    return client.post(
        "/api/gamification/shop/purchase/", {"item_id": item.id}, format="json"
    )


@pytest.mark.django_db
def test_purchase_with_open_earn_xp_quest_at_zero_progress_succeeds():
    user = User.objects.create_user(username="shopper0", password="pw")
    _xp(user, 500)  # balance exists before the quest is assigned, so progress is 0
    uq = _earn_xp_quest(user)

    res = _buy(user, 150)

    assert res.status_code == 200
    uq.refresh_from_db()
    assert uq.progress == 0
    assert uq.completed is False


@pytest.mark.django_db
def test_purchase_does_not_lower_earn_xp_quest_progress():
    user = User.objects.create_user(username="shopper1", password="pw")
    uq = _earn_xp_quest(user, requirement=1000)
    _xp(user, 400)
    uq.refresh_from_db()
    assert uq.progress == 400

    res = _buy(user, 150)

    assert res.status_code == 200
    uq.refresh_from_db()
    assert uq.progress == 400


@pytest.mark.django_db
def test_positive_xp_still_advances_and_completes_earn_xp_quest():
    user = User.objects.create_user(username="earner", password="pw")
    uq = _earn_xp_quest(user, requirement=100)

    _xp(user, 60)
    uq.refresh_from_db()
    assert (uq.progress, uq.completed) == (60, False)

    _xp(user, 60)
    uq.refresh_from_db()
    assert (uq.progress, uq.completed) == (120, True)


@pytest.mark.django_db
def test_add_progress_on_stale_instance_does_not_lose_updates():
    user = User.objects.create_user(username="stale", password="pw")
    uq = _earn_xp_quest(user, requirement=1000)
    stale = UserQuest.objects.get(pk=uq.pk)

    uq.add_progress(10)
    stale.add_progress(5)

    assert UserQuest.objects.get(pk=uq.pk).progress == 15
