export interface BadgeDefinition {
  id: string;
  name: string;
  icon: string;
  desc: string;
  moduleIndex?: number;
  isGraduation?: boolean;
}

export const BADGES: BadgeDefinition[] = [
  {
    id: "mod-1",
    name: "Open Source Explorer",
    desc: "Understand open source mindset and history.",
    icon: "🧭",
    moduleIndex: 0,
  },
  {
    id: "mod-2",
    name: "Git Cadet",
    desc: "Initialize repos, commit, and manage local branches.",
    icon: "🌿",
    moduleIndex: 1,
  },
  {
    id: "mod-3",
    name: "GitHub Knight",
    desc: "Master forks, issues, PRs, and team organizations.",
    icon: "🛡️",
    moduleIndex: 2,
  },
  {
    id: "mod-4",
    name: "Etiquette Master",
    desc: "Practice professional communication and PR workflows.",
    icon: "🤝",
    moduleIndex: 3,
  },
  {
    id: "mod-5",
    name: "First Merge",
    desc: "Practice local-upstream commit pushing.",
    icon: "🚀",
    moduleIndex: 4,
  },
  {
    id: "mod-6",
    name: "Workflow Champion",
    desc: "Understand issue life-cycle management.",
    icon: "🔄",
    moduleIndex: 5,
  },
  {
    id: "mod-7",
    name: "Rebase Sensei",
    desc: "Rebase, resolve conflicts, and parse CI/CD checks.",
    icon: "🧠",
    moduleIndex: 6,
  },
  {
    id: "mod-8",
    name: "Hacktoberfest Ready",
    desc: "Find beginner-friendly repositories and issues.",
    icon: "🎃",
    moduleIndex: 7,
  },
  {
    id: "grad",
    name: "Atelier Graduate",
    desc: "Complete 100% of the learning program.",
    icon: "🎓",
    isGraduation: true,
  },
];
