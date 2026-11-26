from django.contrib import admin

from .models import (
    Badge,
    ExerciseAttempt,
    FinancialReward,
    LessonProgress,
    ProgressBufferDeadLetter,
    RewardTransactionSaga,
    UserBadge,
    UserNote,
)

admin.site.register(Badge)
admin.site.register(UserBadge)
admin.site.register(LessonProgress)
admin.site.register(ExerciseAttempt)
admin.site.register(UserNote)


@admin.register(ProgressBufferDeadLetter)
class ProgressBufferDeadLetterAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "activity_type", "source_id", "status", "replayed")
    list_filter = ("status", "replayed", "activity_type")
    actions = ["replay_selected", "discard_selected"]

    @admin.action(description="Replay selected")
    def replay_selected(self, request, qs):
        for i in qs:
            try:
                i.replay(request.user.username)
            except Exception:
                pass

    @admin.action(description="Discard selected")
    def discard_selected(self, request, qs):
        qs.update(status="discarded", replayed_by=request.user.username)


@admin.register(RewardTransactionSaga)
class RewardTransactionSagaAdmin(admin.ModelAdmin):
    list_display = ("saga_id", "user", "status", "action_type", "created_at")
    list_filter = ("status", "action_type", "created_at")
    search_fields = ("saga_id", "user__username")
    readonly_fields = ("created_at", "updated_at")


@admin.register(FinancialReward)
class FinancialRewardAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "amount",
        "currency",
        "status",
        "source_type",
        "created_at",
    )
    list_filter = ("status", "currency", "source_type", "created_at")
    search_fields = ("saga_id", "user__username")
    readonly_fields = ("created_at", "updated_at")
