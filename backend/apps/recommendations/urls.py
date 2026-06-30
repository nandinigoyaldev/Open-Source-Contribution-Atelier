from django.urls import path
from . import views

app_name = "recommendations"

urlpatterns = [
    path("", views.RecommendationListView.as_view(), name="list"),
    path("generate/", views.GenerateRecommendationsView.as_view(), name="generate"),
    path("<int:pk>/dismiss/", views.DismissRecommendationView.as_view(), name="dismiss"),
]
