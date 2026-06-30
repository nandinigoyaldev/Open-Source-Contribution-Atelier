export const mockAdminDashboardStats = {
  system_stats: {
    total_issues: 10,
    solved_issues: 4,
    open_issues: 4,
    in_progress_issues: 2,
    total_prs: 5,
    merged_prs: 3,
    pending_prs: 1,
    closed_prs: 1,
    active_contributors: 2,
  },
  pending_prs: [
    {
      id: 9,
      title: "Feature request review",
      contributor: "bob_coder",
      issue_title: "Add dark mode toggle",
      created_at: "2026-06-01T12:00:00Z",
    },
  ],
};

export const mockLeaderboard = {
  count: 2,
  next: null,
  previous: null,
  results: [
    {
      id: 2,
      username: "bob_coder",
      prs_merged: 2,
      issues_solved: 3,
      xp: 250,
    },
    {
      id: 3,
      username: "alice_dev",
      prs_merged: 1,
      issues_solved: 1,
      xp: 100,
    },
  ],
};

export const mockContributorDashboardStats = {
  personal_stats: {
    issues_solved: 3,
    prs_merged: 2,
    total_xp: 250,
    streak_days: 4,
    rank: 1,
  },
  assigned_issues: [
    {
      id: 11,
      title: "Fix git conflicts",
      description: "Practice conflict resolution",
      status: "in_progress",
      points: 50,
      created_at: "2026-06-01T10:00:00Z",
    },
  ],
  recent_prs: [
    {
      id: 22,
      title: "Mock PR submission",
      status: "merged",
      issue_title: "Fix git conflicts",
      created_at: "2026-06-01T11:00:00Z",
      merged_at: "2026-06-01T12:00:00Z",
    },
  ],
  progress_tracker: {
    completed_lessons: 2,
    total_lessons: 5,
    completion_percentage: 40,
  },
};

export const mockCurriculum = {
  modules: [
    {
      lessons: [
        {
          slug: "intro",
          title: "Open Source Mindset",
          description: "Understand how open source collaboration works.",
        },
      ],
    },
  ],
};

export const mockLessonsList = [
  {
    slug: "intro",
    title: "Introduction to Atelier",
    summary: "Welcome lesson",
    difficulty: "beginner",
    estimated_minutes: 5,
  },
];
