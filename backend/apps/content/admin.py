from django.contrib import admin

from .models import Exercise, Lesson, LessonFeedback

admin.site.register(Lesson)
admin.site.register(Exercise)
admin.site.register(LessonFeedback)
