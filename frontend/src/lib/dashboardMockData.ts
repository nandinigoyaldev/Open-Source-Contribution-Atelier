interface CurrentModule {
  number: number;
  title: string;
  lessonsCompleted: number;
  totalLessons: number;
}

interface StudentStats {
  xp: number;
  streakDays: number;
  longestStreak: number;
  modulesCompleted: number;
  totalModules: number;
  totalLessonsCompleted: number;
  totalLessons: number;
  currentModule: CurrentModule;
  earnedBadges: string[];
}

interface LessonItem {
  number: number;
  title: string;
  description: string;
  slug: string;
}

interface TipOfTheDay {
  title: string;
  explanation: string;
}

const tips: TipOfTheDay[] = [
  {
    title: "What does git add do?",
    explanation:
      "Think of git add like packing a suitcase. You put your changed files (clothes) into the staging area (suitcase) before you commit (zip it up and label it). Until you git add, Git won't track your changes — they're just lying around your room!",
  },
  {
    title: "What is a commit?",
    explanation:
      "A commit is like saving a checkpoint in a video game. After you make changes and git add them, you commit to save that moment forever. If something breaks later, you can always go back to this checkpoint.",
  },
  {
    title: "What is a branch?",
    explanation:
      "A branch is like a separate timeline in a story. The main timeline (main branch) is the official story. When you want to try something new, you create a new branch — it's like writing an alternate version without messing up the original.",
  },
  {
    title: "What is a pull request?",
    explanation:
      "A pull request is like raising your hand to suggest a change. You've written some code on your branch, and now you're asking the project owner: 'Hey, I made this cool improvement — do you want to add it to the main story?'",
  },
  {
    title: "What is an open source license?",
    explanation:
      "A license is like a permission slip from the creator. It tells everyone: 'Yes, you can use my code, share it, and even improve it — as long as you follow these rules.' Without a license, it's legally unclear if anyone can use it.",
  },
  {
    title: "What does 'fork' mean?",
    explanation:
      "Forking is like making a photocopy of someone's recipe book. You now have your own copy that you can scribble in, try new recipes, and cook whatever you want. If you make something delicious, you can share it back with the original cook!",
  },
];

export function getTipOfTheDay(): TipOfTheDay {
  const dayIndex = new Date().getDate() % tips.length;
  return tips[dayIndex];
}

export const mockStudentStats: StudentStats = {
  xp: 2840,
  streakDays: 14,
  longestStreak: 21,
  modulesCompleted: 1,
  totalModules: 8,
  totalLessonsCompleted: 3,
  totalLessons: 48,
  currentModule: {
    number: 2,
    title: "Git Basics — Version Control for Beginners",
    lessonsCompleted: 3,
    totalLessons: 6,
  },
  earnedBadges: ["first-commit", "streak-7", "streak-14", "module-1"],
};

export const mockLessonQueue: LessonItem[] = [
  {
    number: 4,
    title: "What is a commit?",
    description: "Learn how to save your work with meaningful checkpoints",
    slug: "what-is-a-commit",
  },
  {
    number: 5,
    title: "Your first git add + commit",
    description: "Practice staging and committing changes like a pro",
    slug: "first-commit",
  },
  {
    number: 6,
    title: "Reading git status",
    description: "Understand what Git tells you about your files",
    slug: "git-status",
  },
];

interface ModuleData {
  id: string;
  title: string;
  description: string;
  status: "completed" | "in progress" | "not started";
  score: number;
  explanation: string;
  lessons_count: number;
  completed_lessons_count: number;
  firstLessonSlug: string;
}

interface LearningPathResponse {
  modules: ModuleData[];
  next_step: ModuleData | null;
}

const mockModules: ModuleData[] = [
  {
    id: "module-1",
    title: "Why Open Source?",
    description:
      "Understand the philosophy, history, and community behind open source software.",
    status: "completed",
    score: 95,
    explanation:
      "You aced this module! Great foundation in open source principles.",
    lessons_count: 6,
    completed_lessons_count: 6,
    firstLessonSlug: "what-is-open-source",
  },
  {
    id: "module-2",
    title: "Git Basics — Version Control for Beginners",
    description:
      "Learn how Git tracks changes, what commits are, and how to save your work.",
    status: "in progress",
    score: 72,
    explanation:
      "You're making great progress! Focus on understanding git add vs commit to strengthen your foundation.",
    lessons_count: 6,
    completed_lessons_count: 3,
    firstLessonSlug: "repositories-and-commits",
  },
  {
    id: "module-3",
    title: "GitHub — Your Open Source Playground",
    description:
      "Work with branches, understand merging, and collaborate without conflicts.",
    status: "not started",
    score: 0,
    explanation:
      "Complete Git Basics first — branches build directly on commit concepts.",
    lessons_count: 6,
    completed_lessons_count: 0,
    firstLessonSlug: "github-repositories",
  },
  {
    id: "module-4",
    title: "Open Source Etiquette",
    description:
      "Learn how to open PRs, review code, and contribute to any project.",
    status: "not started",
    score: 0,
    explanation:
      "Once you're comfortable with branches, PRs are the next natural step.",
    lessons_count: 4,
    completed_lessons_count: 0,
    firstLessonSlug: "respect-and-communication",
  },
  {
    id: "module-5",
    title: "Your First Contribution",
    description:
      "How to communicate, follow conventions, and be a welcome community member.",
    status: "not started",
    score: 0,
    explanation: "Essential skills before contributing to real projects.",
    lessons_count: 1,
    completed_lessons_count: 0,
    firstLessonSlug: "first-contribution-walkthrough",
  },
  {
    id: "module-6",
    title: "The Full Contribution Lifecycle",
    description:
      "Find beginner-friendly issues and make your first open source contribution.",
    status: "not started",
    score: 0,
    explanation:
      "This is where theory meets practice — exciting milestone ahead!",
    lessons_count: 1,
    completed_lessons_count: 0,
    firstLessonSlug: "contribution-lifecycle",
  },
  {
    id: "module-7",
    title: "Leveling Up: Advanced Git",
    description: "Rebasing, cherry-picking, and professional Git workflows.",
    status: "not started",
    score: 0,
    explanation: "Advanced topics for when you're contributing regularly.",
    lessons_count: 3,
    completed_lessons_count: 0,
    firstLessonSlug: "rebasing-and-squashing",
  },
  {
    id: "module-8",
    title: "Finding the Right Project",
    description:
      "Review PRs, manage issues, and grow your own open source project.",
    status: "not started",
    score: 0,
    explanation: "The final step — you'll be ready to lead your own project!",
    lessons_count: 1,
    completed_lessons_count: 0,
    firstLessonSlug: "finding-projects",
  },
];

export const mockLearningPath: LearningPathResponse = {
  modules: mockModules,
  next_step: mockModules[1],
};
