import React, { useState, useEffect } from "react";
import {
  GitBranch,
  Sparkles,
  Award,
  Search,
  CheckCircle2,
  Lock,
  Layers,
  Filter,
  Zap,
  RefreshCw,
  Compass,
  ArrowUpRight,
} from "lucide-react";
import {
  SkillGraphCanvas,
  SkillEdge,
} from "../components/skills/SkillGraphCanvas";
import {
  SkillNodeDetailModal,
  SkillNode,
} from "../components/skills/SkillNodeDetailModal";

const DEFAULT_NODES: SkillNode[] = [
  {
    id: "git-basics",
    title: "Git Basics & CLI Setup",
    domain: "open_source",
    category: "Version Control",
    description:
      "Master essential git commands: init, clone, add, commit, status, push, and pull.",
    prerequisites: [],
    status: "completed",
    xp_reward: 100,
    difficulty: "Beginner",
    position: { x: 80, y: 280 },
    recommended_lessons: [
      {
        id: "git-101",
        title: "Introduction to Git Version Control",
        duration: "15 min",
      },
      {
        id: "git-102",
        title: "Configuring SSH Keys and User Credentials",
        duration: "10 min",
      },
    ],
    related_challenges: [
      { id: "c-git-01", title: "First Commit Sandbox", xp: 50 },
    ],
    badge_reward: { name: "Git Initiate", icon: "GitBranch", color: "#4ECDC4" },
    progress_percent: 100,
  },
  {
    id: "branching-strategies",
    title: "Branching & Feature Workflows",
    domain: "open_source",
    category: "Version Control",
    description:
      "Learn feature branching, Gitflow, trunk-based development, and HEAD pointers.",
    prerequisites: ["git-basics"],
    status: "unlocked",
    xp_reward: 150,
    difficulty: "Beginner",
    position: { x: 280, y: 280 },
    recommended_lessons: [
      {
        id: "git-201",
        title: "Creating & Managing Feature Branches",
        duration: "20 min",
      },
    ],
    related_challenges: [
      {
        id: "c-git-02",
        title: "Branch Switching & Fast-Forward Merges",
        xp: 75,
      },
    ],
    badge_reward: { name: "Branch Master", icon: "GitFork", color: "#45B7D1" },
    progress_percent: 60,
  },
  {
    id: "conflict-resolution",
    title: "Merge Conflict Resolution",
    domain: "open_source",
    category: "Collaboration",
    description:
      "Resolve complex merge conflicts, perform interactive rebase, and cherry-pick commits.",
    prerequisites: ["branching-strategies"],
    status: "unlocked",
    xp_reward: 250,
    difficulty: "Intermediate",
    position: { x: 490, y: 280 },
    recommended_lessons: [
      {
        id: "git-301",
        title: "Handling Merge Conflicts step-by-step",
        duration: "25 min",
      },
    ],
    related_challenges: [
      { id: "c-git-03", title: "3-Way Merge Conflict Challenge", xp: 150 },
    ],
    badge_reward: {
      name: "Conflict Tamer",
      icon: "GitPullRequest",
      color: "#FF6B6B",
    },
    progress_percent: 20,
  },
  {
    id: "ci-cd-pipelines",
    title: "CI/CD & GitHub Actions",
    domain: "devops",
    category: "Automation",
    description:
      "Automate testing, linting, and releases using GitHub Actions and Docker pipelines.",
    prerequisites: ["conflict-resolution"],
    status: "locked",
    xp_reward: 350,
    difficulty: "Advanced",
    position: { x: 700, y: 280 },
    recommended_lessons: [
      {
        id: "cicd-101",
        title: "Writing GitHub Actions Workflows",
        duration: "30 min",
      },
    ],
    related_challenges: [
      { id: "c-cicd-01", title: "Automated Matrix Build Runner", xp: 200 },
    ],
    badge_reward: { name: "Automation Wizard", icon: "Cpu", color: "#A78BFA" },
    progress_percent: 0,
  },
  {
    id: "open-source-maintainer",
    title: "Open Source Maintainer Mastery",
    domain: "open_source",
    category: "Leadership",
    description:
      "Triage issues, review pull requests, enforce CODEOWNERS, publish releases, and build communities.",
    prerequisites: ["ci-cd-pipelines", "pr-review-mastery"],
    status: "locked",
    xp_reward: 500,
    difficulty: "Expert",
    position: { x: 920, y: 280 },
    recommended_lessons: [
      {
        id: "os-401",
        title: "Maintainer Playbook & Community Triage",
        duration: "45 min",
      },
    ],
    related_challenges: [
      { id: "c-os-01", title: "Project Release Governance", xp: 300 },
    ],
    badge_reward: {
      name: "Maintainer Vanguard",
      icon: "Award",
      color: "#F59E0B",
    },
    progress_percent: 0,
  },
  {
    id: "react-basics",
    title: "React 19 & Component Design",
    domain: "frontend",
    category: "Frontend Frameworks",
    description:
      "Build modern UI components using React 19 hooks, state, and props.",
    prerequisites: ["git-basics"],
    status: "completed",
    xp_reward: 150,
    difficulty: "Beginner",
    position: { x: 280, y: 120 },
    recommended_lessons: [
      { id: "react-101", title: "React 19 Core Concepts", duration: "20 min" },
    ],
    related_challenges: [
      { id: "c-react-01", title: "Interactive Counter & State", xp: 80 },
    ],
    badge_reward: { name: "React Novice", icon: "Code", color: "#61DAFB" },
    progress_percent: 100,
  },
  {
    id: "typescript-mastery",
    title: "TypeScript & Type Safety",
    domain: "frontend",
    category: "Language",
    description:
      "Master strict TypeScript types, interfaces, generics, and utility types.",
    prerequisites: ["react-basics"],
    status: "unlocked",
    xp_reward: 200,
    difficulty: "Intermediate",
    position: { x: 490, y: 120 },
    recommended_lessons: [
      {
        id: "ts-101",
        title: "Generics & Advanced TS Patterns",
        duration: "25 min",
      },
    ],
    related_challenges: [
      { id: "c-ts-01", title: "Strongly Typed API Adapter", xp: 120 },
    ],
    badge_reward: {
      name: "Type Guardian",
      icon: "ShieldCheck",
      color: "#3178C6",
    },
    progress_percent: 40,
  },
  {
    id: "state-management",
    title: "Redux Toolkit & React Query",
    domain: "frontend",
    category: "Architecture",
    description:
      "Handle complex asynchronous server state and global app store cleanly.",
    prerequisites: ["typescript-mastery"],
    status: "locked",
    xp_reward: 280,
    difficulty: "Intermediate",
    position: { x: 700, y: 120 },
    recommended_lessons: [
      {
        id: "state-101",
        title: "TanStack Query & Redux RTK Query",
        duration: "30 min",
      },
    ],
    related_challenges: [
      { id: "c-state-01", title: "Optimistic Cache Updates", xp: 160 },
    ],
    badge_reward: { name: "State Architect", icon: "Layers", color: "#764ABC" },
    progress_percent: 0,
  },
  {
    id: "django-rest",
    title: "Django 5 & DRF APIs",
    domain: "backend",
    category: "Backend Frameworks",
    description:
      "Design secure REST APIs with Django REST Framework, ORM, and JWT authentication.",
    prerequisites: ["git-basics"],
    status: "completed",
    xp_reward: 180,
    difficulty: "Beginner",
    position: { x: 280, y: 440 },
    recommended_lessons: [
      {
        id: "django-101",
        title: "Django ORM & DRF ViewSets",
        duration: "25 min",
      },
    ],
    related_challenges: [
      { id: "c-django-01", title: "CRUD API Serializer Challenge", xp: 100 },
    ],
    badge_reward: {
      name: "Python Craftsman",
      icon: "Server",
      color: "#092E20",
    },
    progress_percent: 100,
  },
  {
    id: "async-workers",
    title: "Celery & Redis Workers",
    domain: "backend",
    category: "Distributed Systems",
    description:
      "Offload long-running tasks, email queues, and background jobs asynchronously.",
    prerequisites: ["django-rest"],
    status: "unlocked",
    xp_reward: 260,
    difficulty: "Intermediate",
    position: { x: 490, y: 440 },
    recommended_lessons: [
      {
        id: "celery-101",
        title: "Task Queue Architecture with Redis",
        duration: "25 min",
      },
    ],
    related_challenges: [
      { id: "c-celery-01", title: "Background Mailer & Retry Policy", xp: 140 },
    ],
    badge_reward: { name: "Queue Master", icon: "Zap", color: "#DC2626" },
    progress_percent: 50,
  },
  {
    id: "pr-review-mastery",
    title: "Code Review & Quality CI",
    domain: "open_source",
    category: "Code Quality",
    description:
      "Conduct thorough code reviews, enforce unit tests, linting, and security static analysis.",
    prerequisites: ["conflict-resolution"],
    status: "unlocked",
    xp_reward: 300,
    difficulty: "Advanced",
    position: { x: 700, y: 440 },
    recommended_lessons: [
      {
        id: "review-101",
        title: "Constructive Peer Review Etiquette",
        duration: "20 min",
      },
    ],
    related_challenges: [
      {
        id: "c-review-01",
        title: "Find the Security Vulnerability PR",
        xp: 180,
      },
    ],
    badge_reward: {
      name: "Sentinel Inspector",
      icon: "CheckCircle2",
      color: "#10B981",
    },
    progress_percent: 30,
  },
];

const DEFAULT_EDGES: SkillEdge[] = [
  {
    id: "e1",
    source: "git-basics",
    target: "branching-strategies",
    status: "completed",
  },
  {
    id: "e2",
    source: "branching-strategies",
    target: "conflict-resolution",
    status: "active",
  },
  {
    id: "e3",
    source: "conflict-resolution",
    target: "ci-cd-pipelines",
    status: "locked",
  },
  {
    id: "e4",
    source: "ci-cd-pipelines",
    target: "open-source-maintainer",
    status: "locked",
  },
  {
    id: "e5",
    source: "git-basics",
    target: "react-basics",
    status: "completed",
  },
  {
    id: "e6",
    source: "react-basics",
    target: "typescript-mastery",
    status: "active",
  },
  {
    id: "e7",
    source: "typescript-mastery",
    target: "state-management",
    status: "locked",
  },
  {
    id: "e8",
    source: "git-basics",
    target: "django-rest",
    status: "completed",
  },
  {
    id: "e9",
    source: "django-rest",
    target: "async-workers",
    status: "active",
  },
  {
    id: "e10",
    source: "conflict-resolution",
    target: "pr-review-mastery",
    status: "active",
  },
  {
    id: "e11",
    source: "pr-review-mastery",
    target: "open-source-maintainer",
    status: "locked",
  },
];

export const SkillTreePage: React.FC = () => {
  const [nodes, setNodes] = useState<SkillNode[]>(DEFAULT_NODES);
  const [edges, setEdges] = useState<SkillEdge[]>(DEFAULT_EDGES);
  const [selectedDomain, setSelectedDomain] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [selectedNode, setSelectedNode] = useState<SkillNode | null>(null);
  const [isCompleting, setIsCompleting] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [userXP, setUserXP] = useState<number>(0);

  const fetchSkillTree = async (signal?: AbortSignal) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/skills-matching/skill-tree/", { signal });
      if (!res.ok) {
        throw new Error(`Failed to load skill tree: ${res.statusText}`);
      }
      const data = await res.json();
      if (data && data.nodes) {
        setNodes(data.nodes);
        if (data.edges) setEdges(data.edges);
        if (typeof data.user_xp === "number") {
          setUserXP(data.user_xp);
        }
      }
    } catch (err: any) {
      if (err?.name === "AbortError") return;
      // Fallback to default nodes if offline / dev mode
      setNodes(DEFAULT_NODES);
      setEdges(DEFAULT_EDGES);
      setUserXP(1250);
      setError(err?.message || "Failed to fetch live skill tree.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    const controller = new AbortController();
    fetchSkillTree(controller.signal);
    return () => {
      controller.abort();
    };
  }, []);

  const masteredCount = nodes.filter((n) => n.status === "completed").length;
  const totalNodes = nodes.length;
  const progressPercent = Math.round((masteredCount / totalNodes) * 100);

  const handleCompleteNode = async (nodeId: string) => {
    setIsCompleting(true);
    try {
      const res = await fetch(
        "/api/skills-matching/skill-tree/complete-node/",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ node_id: nodeId }),
        },
      );

      if (res.ok) {
        const result = await res.json();
        // Update local state
        setNodes((prevNodes) =>
          prevNodes.map((n) => {
            if (n.id === nodeId) {
              return { ...n, status: "completed", progress_percent: 100 };
            }
            if (result.newly_unlocked?.includes(n.id)) {
              return { ...n, status: "unlocked" };
            }
            return n;
          }),
        );
        setUserXP((prev) => prev + (result.xp_gained || 150));
        setSelectedNode(null);
      } else {
        // Optimistic local update fallback
        setNodes((prevNodes) =>
          prevNodes.map((n) =>
            n.id === nodeId ? { ...n, status: "completed" } : n,
          ),
        );
        setUserXP((prev) => prev + 150);
        setSelectedNode(null);
      }
    } catch {
      // Local optimistic update
      setNodes((prevNodes) =>
        prevNodes.map((n) =>
          n.id === nodeId ? { ...n, status: "completed" } : n,
        ),
      );
      setUserXP((prev) => prev + 150);
      setSelectedNode(null);
    } finally {
      setIsCompleting(false);
    }
  };

  return (
    <main
      id="main-content"
      className="min-h-screen bg-slate-900 text-slate-100 p-4 sm:p-6 lg:p-8"
    >
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Top Header Banner */}
        <div className="relative p-6 sm:p-8 bg-gradient-to-r from-indigo-950 via-slate-900 to-purple-950 border border-slate-800 rounded-3xl overflow-hidden shadow-2xl">
          <div className="absolute -right-12 -bottom-12 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

          <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <span className="px-3 py-1 bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-xs font-bold rounded-full uppercase tracking-wider flex items-center gap-1.5">
                  <Compass className="w-3.5 h-3.5 text-indigo-400" /> RPG
                  Contributor Pathway
                </span>
                <span className="text-xs text-slate-400">
                  Open Source Mastery Edition
                </span>
              </div>
              <h1 className="text-3xl sm:text-4xl font-black text-white tracking-tight">
                Interactive Skill Tree & Mastery Graph
              </h1>
              <p className="mt-2 text-sm sm:text-base text-slate-300 max-w-2xl">
                Explore your open-source contributor roadmap. Master
                prerequisite nodes, unlock advanced tracks, and gain XP as you
                progress.
              </p>
            </div>

            {/* User Mastery Stats Dashboard Pills */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 shrink-0">
              <div className="p-3 bg-slate-900/80 border border-slate-800 rounded-2xl flex flex-col justify-center">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                  Total XP Earned
                </span>
                <p className="text-xl font-black text-amber-400 flex items-center gap-1">
                  <Sparkles className="w-5 h-5 text-amber-400" /> {userXP}
                </p>
              </div>

              <div className="p-3 bg-slate-900/80 border border-slate-800 rounded-2xl flex flex-col justify-center">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                  Mastered Skills
                </span>
                <p className="text-xl font-black text-emerald-400 flex items-center gap-1">
                  <CheckCircle2 className="w-5 h-5 text-emerald-400" />{" "}
                  {masteredCount}/{totalNodes}
                </p>
              </div>

              <div className="col-span-2 sm:col-span-1 p-3 bg-slate-900/80 border border-slate-800 rounded-2xl flex flex-col justify-center">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                  Overall Completion
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-xl font-black text-indigo-400">
                    {progressPercent}%
                  </span>
                  <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                    <div
                      className="bg-indigo-500 h-full rounded-full transition-all duration-500"
                      style={{ width: `${progressPercent}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Toolbar & Filters */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4 p-4 bg-slate-900/80 border border-slate-800 rounded-2xl backdrop-blur-md">
          {/* Domain Track Tabs */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0 custom-scrollbar">
            {[
              { id: "all", label: "All Skill Paths" },
              { id: "open_source", label: "Open Source Workflow" },
              { id: "frontend", label: "Frontend Track" },
              { id: "backend", label: "Backend Track" },
              { id: "devops", label: "DevOps & CI/CD" },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setSelectedDomain(tab.id)}
                className={`px-3.5 py-2 text-xs font-bold rounded-xl whitespace-nowrap transition-all ${
                  selectedDomain === tab.id
                    ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/30"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/80"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Search Box & Refresh Button */}
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <div className="relative flex-1 sm:w-64">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type="text"
                placeholder="Search skill nodes..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-4 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
              />
            </div>
            <button
              onClick={() => fetchSkillTree()}
              disabled={isLoading}
              title="Refresh skill tree data"
              aria-label="Refresh skill tree data"
              className="p-2 bg-slate-950 border border-slate-800 hover:border-slate-700 rounded-xl text-slate-400 hover:text-slate-200 transition-colors disabled:opacity-50"
            >
              <RefreshCw
                className={`w-4 h-4 ${isLoading ? "animate-spin text-indigo-400" : ""}`}
              />
            </button>
          </div>
        </div>

        {/* Node Graph Canvas */}
        <SkillGraphCanvas
          nodes={nodes}
          edges={edges}
          selectedDomain={selectedDomain}
          searchQuery={searchQuery}
          onNodeSelect={(node) => setSelectedNode(node)}
        />

        {/* Modal for Selected Node Details */}
        <SkillNodeDetailModal
          node={selectedNode}
          allNodes={nodes}
          onClose={() => setSelectedNode(null)}
          onCompleteNode={handleCompleteNode}
          isLoading={isCompleting}
        />
      </div>
    </main>
  );
};

export default SkillTreePage;
