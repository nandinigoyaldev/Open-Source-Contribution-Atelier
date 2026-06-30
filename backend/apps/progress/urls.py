from django.urls import path
from .views import (
    BadgeListView,
    CommunityStatsView,
    HelpRequestListCreateView,
    MyProgressView,
    ContributorTimelineView,
)

urlpatterns = [
    path("badges/", BadgeListView.as_view(), name="badges"),
    path("me/", MyProgressView.as_view(), name="my-progress"),
    path(
        "contributor-timeline/",
        ContributorTimelineView.as_view(),
        name="contributor-timeline",
    ),
    path("community-stats/", CommunityStatsView.as_view(), name="community-stats"),
    path("help-requests/", HelpRequestListCreateView.as_view(), name="help-requests"),
    path("timeline/", ContributorTimelineView.as_view(), name="contributor-timeline"),
]
