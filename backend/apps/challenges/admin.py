from django.contrib import admin

from .models import Challenge, ChallengeCompletion, ChallengeOfTheDay

admin.site.register(Challenge)
admin.site.register(ChallengeOfTheDay)
admin.site.register(ChallengeCompletion)
