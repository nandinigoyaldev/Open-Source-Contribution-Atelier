from django.contrib import admin

from .models import Badge, ExerciseAttempt, LessonProgress, UserBadge

admin.site.register(Badge)
admin.site.register(UserBadge)
admin.site.register(LessonProgress)
admin.site.register(ExerciseAttempt)
