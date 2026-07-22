from django.db.models import F
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender="progress.LessonProgress")
def track_lesson_quest(sender, instance, created, **kwargs):
    if created and instance.completed:
        from .models import UserQuest

        UserQuest.objects.filter(
            user=instance.user,
            quest__quest_type="complete_lessons",
            completed=False,
        ).update(progress=F("progress") + 1)


@receiver(post_save, sender="progress.XPEvent")
def track_xp_quest(sender, instance, created, **kwargs):
    if created:
        from .models import UserQuest

        qs = UserQuest.objects.filter(
            user=instance.user,
            quest__quest_type="earn_xp",
            completed=False,
        )
        for uq in qs:
            uq.add_progress(instance.xp_delta)


@receiver(post_save, sender="gamification.UserAchievement")
def track_badge_quest(sender, instance, created, **kwargs):
    if created:
        from .models import UserQuest

        qs = UserQuest.objects.filter(
            user=instance.user,
            quest__quest_type="earn_badge",
            completed=False,
        )
        for uq in qs:
            uq.add_progress(1)


@receiver(post_save, sender="gamification.Streak")
def track_streak_quest(sender, instance, **kwargs):
    from .models import UserQuest

    UserQuest.objects.filter(
        user=instance.user,
        quest__quest_type="maintain_streak",
        completed=False,
    ).update(progress=F("progress") + 1)


@receiver(post_save, sender="challenges.ChallengeCompletion")
def track_challenge_quest(sender, instance, created, **kwargs):
    if created:
        from .models import UserQuest

        UserQuest.objects.filter(
            user=instance.user,
            quest__quest_type="complete_challenge",
            completed=False,
        ).update(progress=F("progress") + 1)
