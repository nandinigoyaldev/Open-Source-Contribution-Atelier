from django.contrib import admin

from .models import Badge, ExerciseAttempt, LessonProgress, UserBadge, UserNote

admin.site.register(Badge)
admin.site.register(UserBadge)
admin.site.register(LessonProgress)
admin.site.register(ExerciseAttempt)
admin.site.register(UserNote)
