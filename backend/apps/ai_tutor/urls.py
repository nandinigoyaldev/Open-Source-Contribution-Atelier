from django.urls import path

from .views import TutorAskView

urlpatterns = [
    path("ask/", TutorAskView.as_view(), name="tutor-ask"),
]
