from django.urls import path

from .views import MyBadgesView


urlpatterns = [
    path("me/badges/", MyBadgesView.as_view(), name="my-badges"),
]
