from django.contrib import admin

from .models import Exercise, Lesson

admin.site.register(Lesson)
admin.site.register(Exercise)
