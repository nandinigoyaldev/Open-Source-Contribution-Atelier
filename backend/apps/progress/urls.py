from django.urls import path

from .views import (
    BadgeListView,
    BulkProgressUpdateView,
    BulkSyncProgressView,
    CertificateVerificationView,
    CodeSubmissionView,
    CommunityFeedView,
    CommunityStatsView,
    ContributorTimelineView,
    HelpRequestListCreateView,
    LessonBookmarkView,
    MentorHelpRequestListView,
    MyCertificateView,
    MyProgressView,
    PeerReviewView,
    QuizAttemptView,
    RecommendationsView,
    UserProgressPDFExportView,
    ReadingProgressView,
    QuizNonceView, # NEW: Imported the Nonce View
)

urlpatterns = [
    path("export/pdf/", UserProgressPDFExportView.as_view(), name="export-pdf"),
    path("badges/", BadgeListView.as_view(), name="badges"),
    path("me/", MyProgressView.as_view(), name="my-progress"),
    path("bulk-sync/", BulkSyncProgressView.as_view(), name="bulk-sync"),
    path("bulk-update/", BulkProgressUpdateView.as_view(), name="bulk-update"),
    path("recommendations/", RecommendationsView.as_view(), name="recommendations"),
    path("feed/", CommunityFeedView.as_view(), name="community-feed"),
    path("community-stats/", CommunityStatsView.as_view(), name="community-stats"),
    path("help-requests/", HelpRequestListCreateView.as_view(), name="help-requests"),
    path("timeline/", ContributorTimelineView.as_view(), name="contributor-timeline"),
    path(
        "contributor-timeline/",
        ContributorTimelineView.as_view(),
        name="contributor-timeline-alias",
    ),
    path("quiz-nonce/", QuizNonceView.as_view(), name="quiz-nonce"), # NEW: Routing for the Nonce API
    path("quiz-attempts/", QuizAttemptView.as_view(), name="quiz-attempts"),
    path(
        "mentor/help-requests/",
        MentorHelpRequestListView.as_view(),
        name="mentor-help-requests",
    ),
    path("certificate/", MyCertificateView.as_view(), name="my-certificate"),
    path(
        "verify/<str:hash>/",
        CertificateVerificationView.as_view(),
        name="verify-certificate",
    ),
    path("bookmarks/", LessonBookmarkView.as_view(), name="lesson-bookmarks"),
    path(
        "bookmarks/<str:slug>/",
        LessonBookmarkView.as_view(),
        name="lesson-bookmark-detail",
    ),
    path("code-submissions/", CodeSubmissionView.as_view(), name="code-submissions"),
    path(
        "code-submissions/<int:submission_id>/reviews/",
        PeerReviewView.as_view(),
        name="peer-reviews",
    ),
    path("reading-position/", ReadingProgressView.as_view(), name="reading-position"),
]