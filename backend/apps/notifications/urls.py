from django.urls import path

from .views import (MarkAllReadView, MarkOneReadView, NotificationListView,
                    SubscribePushView, UnsubscribePushView)

urlpatterns = [
    path("", NotificationListView.as_view(), name="notification-list"),
    path("mark-all-read/", MarkAllReadView.as_view(), name="notification-mark-all"),
    path("<int:pk>/read/", MarkOneReadView.as_view(), name="notification-mark-one"),
    path("push/subscribe/", SubscribePushView.as_view(), name="push-subscribe"),
    path("push/unsubscribe/", UnsubscribePushView.as_view(), name="push-unsubscribe"),
]
