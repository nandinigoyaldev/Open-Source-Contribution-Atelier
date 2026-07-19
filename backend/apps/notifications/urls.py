from django.urls import path

from .views import (
    MarkAllReadView,
    MarkOneReadView,
    NotificationListView,
    NotificationPrefsView,
    SubscribePushView,
    UnsubscribePushView,
    NotificationPrefsView,
)

urlpatterns = [
    path("", NotificationListView.as_view(), name="notification-list"),
    path("prefs/", NotificationPrefsView.as_view(), name="notification-prefs"),
    path("mark-all-read/", MarkAllReadView.as_view(), name="notification-mark-all"),
    path("<int:pk>/read/", MarkOneReadView.as_view(), name="notification-mark-one"),
    path("<int:pk>/mark-read/", MarkOneReadView.as_view(), name="notification-mark-read"),
    path("channel-preferences/", NotificationPrefsView.as_view(), name="notification-preferences"),
    path("push/subscribe/", SubscribePushView.as_view(), name="push-subscribe"),
    path("push/unsubscribe/", UnsubscribePushView.as_view(), name="push-unsubscribe"),
]
