from django.urls import path

from .views import (
    DigestAPIView,
    DigestReadView,
    MarkAllReadView,
    MarkOneReadView,
    NotificationListView,
    NotificationPrefsView,
    SubscribePushView,
    UnsubscribePushView,
)

urlpatterns = [
    path("", NotificationListView.as_view(), name="notification-list"),
    path("digest/", DigestAPIView.as_view(), name="notification-digest"),
    path("digest/read/", DigestReadView.as_view(), name="notification-digest-read"),
    path("prefs/", NotificationPrefsView.as_view(), name="notification-prefs"),
    path("mark-all-read/", MarkAllReadView.as_view(), name="notification-mark-all"),
    path("<int:pk>/read/", MarkOneReadView.as_view(), name="notification-mark-one"),
    path(
        "<int:pk>/mark-read/", MarkOneReadView.as_view(), name="notification-mark-read"
    ),
    path(
        "channel-preferences/",
        NotificationPrefsView.as_view(),
        name="notification-preferences",
    ),
    path("push/subscribe/", SubscribePushView.as_view(), name="push-subscribe"),
    path("push/unsubscribe/", UnsubscribePushView.as_view(), name="push-unsubscribe"),
]
