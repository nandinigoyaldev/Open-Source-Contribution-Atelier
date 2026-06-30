from django.urls import path
from .views import NotificationListView, MarkAllReadView, MarkOneReadView

urlpatterns = [
    path("", NotificationListView.as_view(), name="notification-list"),
    path("mark-all-read/", MarkAllReadView.as_view(), name="notification-mark-all"),
    path("<int:pk>/read/", MarkOneReadView.as_view(), name="notification-mark-one"),
]
