from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Badge(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    icon_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class UserAchievement(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="achievements"
    )
    badge = models.ForeignKey(
        Badge, on_delete=models.CASCADE, related_name="awarded_to"
    )
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "badge")

    def __str__(self):
        return f"{self.user} - {self.badge.name}"


class Streak(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="streak"
    )
    current_streak = models.IntegerField(default=0)
    longest_streak = models.IntegerField(default=0)
    last_activity_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} - {self.current_streak} days"


class Quest(models.Model):
    FREQUENCY_CHOICES = [
        ("daily", "Daily"),
        ("weekly", "Weekly"),
    ]

    QUEST_TYPE_CHOICES = [
        ("complete_lessons", "Complete Lessons"),
        ("earn_xp", "Earn XP"),
        ("maintain_streak", "Maintain Streak"),
        ("complete_quiz", "Complete Quiz"),
        ("review_pr", "Review Pull Request"),
        ("earn_badge", "Earn Badge"),
        ("complete_challenge", "Complete Challenge"),
        ("use_sandbox", "Use Sandbox"),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField()
    quest_type = models.CharField(max_length=50, choices=QUEST_TYPE_CHOICES)
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default="daily")
    requirement_count = models.PositiveIntegerField(
        default=1,
        help_text="How many actions needed to complete (e.g. 3 lessons)",
    )
    xp_reward = models.PositiveIntegerField(default=50)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["frequency", "xp_reward"]

    def __str__(self):
        return f"[{self.frequency}] {self.title} ({self.xp_reward} XP)"


class UserQuest(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="quests"
    )
    quest = models.ForeignKey(
        Quest, on_delete=models.CASCADE, related_name="user_quests"
    )
    progress = models.PositiveIntegerField(default=0)
    completed = models.BooleanField(default=False)
    reward_claimed = models.BooleanField(default=False)
    assigned_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        unique_together = ("user", "quest", "assigned_at")
        ordering = ["-assigned_at"]

    def __str__(self):
        return f"{self.user} - {self.quest.title} ({self.progress}/{self.quest.requirement_count})"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    def add_progress(self, amount=1):
        self.progress += amount
        if self.progress >= self.quest.requirement_count and not self.completed:
            self.completed = True
        self.save(update_fields=["progress", "completed"])


class ShopItem(models.Model):
    ITEM_TYPE_CHOICES = [
        ("streak_freeze", "Streak Freeze"),
        ("profile_theme", "Profile Theme"),
        ("badge_unlock", "Badge Unlock"),
        ("xp_boost", "XP Boost"),
        ("custom_title", "Custom Title"),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField()
    item_type = models.CharField(max_length=50, choices=ITEM_TYPE_CHOICES)
    cost = models.PositiveIntegerField(help_text="XP cost")
    icon_emoji = models.CharField(max_length=10, default="🎁")
    is_limited = models.BooleanField(default=False, help_text="One purchase per user")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["cost"]

    def __str__(self):
        return f"{self.name} ({self.cost} XP)"


class Purchase(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="purchases"
    )
    item = models.ForeignKey(
        ShopItem, on_delete=models.CASCADE, related_name="purchases"
    )
    xp_spent = models.PositiveIntegerField()
    purchased_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-purchased_at"]
        unique_together = ("user", "item")

    def __str__(self):
        return f"{self.user} bought {self.item.name} ({self.xp_spent} XP)"
