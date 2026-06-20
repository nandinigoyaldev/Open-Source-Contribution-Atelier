export const lessonPreview = {
  title: "Open Source Basics",
  summary:
    "Learn how to navigate issues, branches, pull requests, and contribution etiquette.",
  expectedCommand: "git status",
};

export const dashboardStats = [
  {
    label: "Total contributors mentored",
    value: "142",
    meta: "+18 this month",
  },
  {
    label: "Merged practice submissions",
    value: "481",
    meta: "31 pending review",
  },
  {
    label: "Curriculum completion rate",
    value: "84%",
    meta: "Advanced cohort",
  },
];

export const learningQueue = [
  {
    title: "First PR Readiness",
    subtitle: "Module 2 · Branching, commits, and review etiquette",
    cta: "Resume track",
    meta: "18 learners active",
  },
  {
    title: "Maintainer Communication",
    subtitle: "Module 5 · Comments, revisions, and async collaboration",
    cta: "Open lesson",
    meta: "12 learners blocked",
  },
];

export type Difficulty = "beginner" | "intermediate" | "advanced";

export type ChallengeCard = {
  title: string;
  summary: string;
  badge: string;
  difficulty: Difficulty;
};

export const challengeCards: ChallengeCard[] = [
  {
    title: "Hacktoberfest Warmup",
    summary:
      "Guide contributors through issue triage, branch naming, and clean commits.",
    badge: "Featured sprint",
    difficulty: "beginner",
  },
  {
    title: "Git Recovery Lab",
    summary:
      "Practice safe undo flows, rebases, and fixing a messy working tree.",
    badge: "Advanced",
    difficulty: "advanced",
  },
  {
    title: "PR Etiquette Essentials",
    summary:
      "Learn how to write descriptive PR titles, link issues, and respond to reviews.",
    badge: "Beginner",
    difficulty: "beginner",
  },
  {
    title: "Rebase & Merge Strategies",
    summary:
      "Compare merge commits, squash merges, and rebase workflows on real scenarios.",
    badge: "Intermediate",
    difficulty: "intermediate",
  },
  {
    title: "Conflict Resolution Drills",
    summary:
      "Simulate merge conflicts and practice resolving them step by step.",
    badge: "Intermediate",
    difficulty: "intermediate",
  },
  {
    title: "CI/CD Pipeline Setup",
    summary:
      "Configure GitHub Actions to lint, test, and deploy on every push.",
    badge: "Advanced",
    difficulty: "advanced",
  },
];

export const communityStats = [
  { label: "Weekly active contributors", value: "128" },
  { label: "Merged learning PRs", value: "342" },
  { label: "Mentor response SLA", value: "3.2h" },
  { label: "Open help requests", value: "19" },
];
