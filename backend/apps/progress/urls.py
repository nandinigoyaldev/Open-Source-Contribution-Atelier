from django.urls import path

from .views import ExportNotesView  # ✅ ADDED
from .views import QuizNonceView  # NEW: Imported the Nonce View
from .views import (
    ActivityTimelineView,
    BadgeListView,
    BufferMetricsView,
    BulkProgressUpdateView,
    BulkSyncProgressView,
    CertificateVerificationView,
    ClaimMultiTierRewardView,
    CodeSubmissionView,
    CommunityFeedView,
    CommunityStatsView,
    ContributorTimelineView,
    DailyLessonStatsView,
    GitHubLeaderboardView,
    HeatmapCSVExportView,
    HeatmapView,
    HelpRequestListCreateView,
    LeaderboardView,
    LessonBookmarkView,
    MentorHelpRequestListView,
    MyCertificateView,
    MyProgressView,
    PeerReviewView,
    QuizAttemptView,
    ReadingProgressView,
    RecommendationsView,
    StreakRecoveryView,
    StreakStatusView,
    UserProgressPDFExportView,
    WeeklyGoalView,
    XPBreakdownView,
)

urlpatterns = [
    path("activity/", ActivityTimelineView.as_view(), name="activity-timeline"),
    # Badges
    path("leaderboard/", LeaderboardView.as_view(), name="leaderboard"),
    path(
        "leaderboard/github/",
        GitHubLeaderboardView.as_view(),
        name="github-leaderboard",
    ),
    path("weekly-goal/", WeeklyGoalView.as_view(), name="weekly-goal"),
    path("buffer-metrics/", BufferMetricsView.as_view(), name="buffer-metrics"),
    path("heatmap/", HeatmapView.as_view(), name="heatmap"),
    path("heatmap/export/", HeatmapCSVExportView.as_view(), name="heatmap-export-csv"),
    path("xp-breakdown/", XPBreakdownView.as_view(), name="xp-breakdown"),
    path("streak/", StreakStatusView.as_view(), name="streak-status"),
    path("streak/recovery/", StreakRecoveryView.as_view(), name="streak-recovery"),
    path("export/pdf/", UserProgressPDFExportView.as_view(), name="export-pdf"),
    path("badges/", BadgeListView.as_view(), name="badges"),
    # Progress
    path("me/", MyProgressView.as_view(), name="my-progress"),
    path("bulk-sync/", BulkSyncProgressView.as_view(), name="bulk-sync"),
    path("bulk-update/", BulkProgressUpdateView.as_view(), name="bulk-update"),
    path(
        "rewards/claim/",
        ClaimMultiTierRewardView.as_view(),
        name="claim-multi-tier-reward",
    ),  # Recommendations
    path("recommendations/", RecommendationsView.as_view(), name="recommendations"),
    path(
        "certificate/verify/<str:hash>/",
        CertificateVerificationView.as_view(),
        name="certificate-verify",
    ),
    path("daily-stats/", DailyLessonStatsView.as_view(), name="daily-stats"),
    path("feed/", CommunityFeedView.as_view(), name="community-feed"),
    path("community-feed/", CommunityFeedView.as_view(), name="community-feed-alias"),
    path("community-stats/", CommunityStatsView.as_view(), name="community-stats"),
    # Help Requests
    path("help-requests/", HelpRequestListCreateView.as_view(), name="help-requests"),
    path(
        "mentor/help-requests/",
        MentorHelpRequestListView.as_view(),
        name="mentor-help-requests",
    ),
    # Timeline
    path("timeline/", ContributorTimelineView.as_view(), name="contributor-timeline"),
    path(
        "contributor-timeline/",
        ContributorTimelineView.as_view(),
        name="contributor-timeline-alias",
    ),
    # Quizzes
    path(
        "quiz-nonce/", QuizNonceView.as_view(), name="quiz-nonce"
    ),  # NEW: Routing for the Nonce API
    path("quiz-attempts/", QuizAttemptView.as_view(), name="quiz-attempts"),
    # Certificates
    path("certificate/", MyCertificateView.as_view(), name="my-certificate"),
    path(
        "verify/<str:hash>/",
        CertificateVerificationView.as_view(),
        name="verify-certificate",
    ),
    # Bookmarks
    path("bookmarks/", LessonBookmarkView.as_view(), name="lesson-bookmarks"),
    path(
        "bookmarks/<str:slug>/",
        LessonBookmarkView.as_view(),
        name="lesson-bookmark-detail",
    ),
    # Code Submissions & Reviews
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
    # ✅ ADDED: Notes Export
    path("notes/export/", ExportNotesView.as_view(), name="notes-export"),
    path("reading-position/", ReadingProgressView.as_view(), name="reading-position"),
]
