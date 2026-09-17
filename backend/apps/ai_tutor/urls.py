from django.urls import path

from .views import TutorAskView, TutorEvaluateView

urlpatterns = [
    path("ask/", TutorAskView.as_view(), name="tutor-ask"),
    path("evaluate/", TutorEvaluateView.as_view(), name="tutor-evaluate"),
]
