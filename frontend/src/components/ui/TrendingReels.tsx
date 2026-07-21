import React, { useState, useEffect, useRef } from "react";
import {
  Heart,
  Share2,
  MessageSquare,
  Play,
  Pause,
  Plus,
  Check,
  ChevronLeft,
  ChevronRight,
  Sparkles,
} from "lucide-react";
import { toast } from "react-hot-toast";

interface Comment {
  username: string;
  avatar: string;
  text: string;
  time: string;
}

interface Reel {
  id: number;
  title: string;
  description: string;
  tags: string[];
  likes: number;
  commentsCount: number;
  creator: {
    username: string;
    role: string;
    avatar: string;
  };
  audio: string;
  commentsList: Comment[];
}

const REELS_DATA: Reel[] = [
  {
    id: 1,
    title: "How to Undo Your Last Commit 🤫",
    description:
      "Accidentally committed secret keys or bugged code? Here is the cleanest way to undo it without losing your changes!",
    tags: ["#git", "#programming", "#hacks", "#dev"],
    likes: 4239,
    commentsCount: 84,
    creator: {
      username: "merge_wizard",
      role: "Atelier Maintainer",
      avatar: "🧙‍♂️",
    },
    audio: "Git Beats - Original Audio",
    commentsList: [
      {
        username: "code_novice",
        avatar: "🧑‍💻",
        text: "This literally saved me 10 minutes ago, thank you!",
        time: "2h ago",
      },
      {
        username: "git_guru",
        avatar: "🛡️",
        text: "Make sure you use --soft, otherwise --hard deletes everything!",
        time: "5h ago",
      },
      {
        username: "stack_tracer",
        avatar: "🐛",
        text: "Great animation, super simple to understand.",
        time: "1d ago",
      },
    ],
  },
  {
    id: 2,
    title: "Git Stash: Save it for Later! 📦",
    description:
      "Need to switch branches but not ready to commit your half-baked features? Stash them in the Git Vault and pop them back later!",
    tags: ["#coding", "#productivity", "#gitstash", "#tips"],
    likes: 2841,
    commentsCount: 42,
    creator: {
      username: "stash_collector",
      role: "Git Architect",
      avatar: "🦊",
    },
    audio: "Stash & Dash - Synthwave Remix",
    commentsList: [
      {
        username: "git_newbie",
        avatar: "🐱",
        text: "Is there a stash limit? I have like 20 stashes lol.",
        time: "1h ago",
      },
      {
        username: "senior_dev",
        avatar: "🧓",
        text: 'Pro tip: use `git stash save "name"` to keep them organized!',
        time: "3h ago",
      },
    ],
  },
  {
    id: 3,
    title: "Merge Conflicts: Accepted Both! ⚔️",
    description:
      "Stop sweating when merge conflicts hit. Here is how conflict markers look and how to easily merge conflicting code paths.",
    tags: ["#gitmerge", "#teamwork", "#programming", "#conflict"],
    likes: 5122,
    commentsCount: 156,
    creator: {
      username: "conflict_resolver",
      role: "Open Source Advocate",
      avatar: "🦄",
    },
    audio: "Harmony & Git - Instrumental",
    commentsList: [
      {
        username: "dev_dilemma",
        avatar: "🤯",
        text: "Merge conflicts give me trust issues, accept both is the safest path!",
        time: "30m ago",
      },
      {
        username: "pr_reviewer",
        avatar: "🕵️",
        text: "Or just rebase and clean it up commit by commit. 😉",
        time: "2h ago",
      },
      {
        username: "junior_101",
        avatar: "🐣",
        text: "I deleted the <<< and === manually, is that normal?",
        time: "4h ago",
      },
    ],
  },
  {
    id: 4,
    title: "Git Reflog: The Ultimate Time Machine 🕰️",
    description:
      "Did you use git reset --hard and lose a branch? Git Reflog records every single action. Never lose code again!",
    tags: ["#gitreflog", "#timetravel", "#sysadmin", "#database"],
    likes: 3904,
    commentsCount: 92,
    creator: {
      username: "time_traveler",
      role: "Atelier Mentor",
      avatar: "🤖",
    },
    audio: "Interstellar Git - Lofi",
    commentsList: [
      {
        username: "reflog_fan",
        avatar: "🕶️",
        text: "Reflog is the absolute best safety net in development.",
        time: "4h ago",
      },
      {
        username: "dev_ops",
        avatar: "🐳",
        text: "Saved my production hotfix yesterday. A must-know command.",
        time: "8h ago",
      },
    ],
  },
];

interface HeartPop {
  id: number;
  x: number;
  y: number;
}

export function TrendingReels() {
  const [activeIdx, setActiveIdx] = useState(0);
  const [isPlaying, setIsPlaying] = useState(true);
  const [progress, setProgress] = useState(0);
  const [likesState, setLikesState] = useState<
    Record<number, { count: number; liked: boolean }>
  >(
    REELS_DATA.reduce(
      (acc, r) => ({ ...acc, [r.id]: { count: r.likes, liked: false } }),
      {},
    ),
  );
  const [isFollowing, setIsFollowing] = useState<Record<number, boolean>>({});
  const [showComments, setShowComments] = useState(false);
  const [newComment, setNewComment] = useState("");
  const [comments, setComments] = useState<Record<number, Comment[]>>(
    REELS_DATA.reduce((acc, r) => ({ ...acc, [r.id]: r.commentsList }), {}),
  );
  const [heartPops, setHeartPops] = useState<HeartPop[]>([]);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const activeReel = REELS_DATA[activeIdx];
  const activeLikes = likesState[activeReel.id] || {
    count: activeReel.likes,
    liked: false,
  };

  // Autoplay / Progress bar logic
  useEffect(() => {
    if (!isPlaying || showComments) return;

    const interval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) {
          setActiveIdx((current) => (current + 1) % REELS_DATA.length);
          return 0;
        }
        return prev + 1.25; // complete in ~8 seconds
      });
    }, 100);

    return () => clearInterval(interval);
  }, [isPlaying, showComments, activeIdx]);

  // Reset progress on active reel change
  useEffect(() => {
    setProgress(0);
  }, [activeIdx]);

  const handleNext = () => {
    setActiveIdx((current) => (current + 1) % REELS_DATA.length);
  };

  const handlePrev = () => {
    setActiveIdx(
      (current) => (current - 1 + REELS_DATA.length) % REELS_DATA.length,
    );
  };

  const handleTogglePlay = () => {
    setIsPlaying((prev) => !prev);
  };

  const handleLike = (e: React.MouseEvent) => {
    const reelId = activeReel.id;
    const currentState = likesState[reelId];

    // Spawn floating heart burst animation
    const rect = e.currentTarget.getBoundingClientRect();
    const newPop = {
      id: Date.now(),
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    };
    setHeartPops((prev) => [...prev, newPop]);
    setTimeout(() => {
      setHeartPops((prev) => prev.filter((p) => p.id !== newPop.id));
    }, 1000);

    if (currentState.liked) {
      setLikesState((prev) => ({
        ...prev,
        [reelId]: { count: currentState.count - 1, liked: false },
      }));
    } else {
      setLikesState((prev) => ({
        ...prev,
        [reelId]: { count: currentState.count + 1, liked: true },
      }));
    }
  };

  const handleToggleFollow = () => {
    setIsFollowing((prev) => ({
      ...prev,
      [activeReel.id]: !prev[activeReel.id],
    }));
  };

  const handleShare = () => {
    const tipText = `💡 Atelier Git Tip: ${activeReel.title}\n\n${activeReel.description}\n\nJoin the Atelier community to practice!`;
    void navigator.clipboard.writeText(tipText);
    toast.success("Tip copied to clipboard! 📋", {
      position: "bottom-center",
      style: {
        border: "3px border-black",
        fontWeight: "bold",
      },
    });
  };

  const handleAddComment = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newComment.trim()) return;

    const added: Comment = {
      username: "you",
      avatar: "🤓",
      text: newComment.trim(),
      time: "Just now",
    };

    setComments((prev) => ({
      ...prev,
      [activeReel.id]: [added, ...(prev[activeReel.id] || [])],
    }));
    setNewComment("");
  };

  // Rendering inner animation screens for each reel ID
  const renderReelVisual = () => {
    switch (activeReel.id) {
      case 1:
        // Undo Commit Animation (Typed Terminal)
        return (
          <div className="absolute inset-0 bg-[#0F172A] dark:bg-[#070b14] flex flex-col p-4 text-xs font-mono text-[#38BDF8]">
            <div className="flex items-center gap-1.5 pb-2 mb-4 border-b border-white/10 text-white/50 text-[10px]">
              <span className="h-2.5 w-2.5 rounded-full bg-[#EF4444]"></span>
              <span className="h-2.5 w-2.5 rounded-full bg-[#F59E0B]"></span>
              <span className="h-2.5 w-2.5 rounded-full bg-[#10B981]"></span>
              <span className="ml-2 font-bold select-none text-white/40">
                git-terminal-tip
              </span>
            </div>

            <div className="space-y-3">
              <div>
                <span className="text-[#34D399] select-none">
                  ~/atelier-project $
                </span>
                <span className="text-white ml-2 animate-pulse">
                  git commit -m "add key"
                </span>
              </div>
              <div className="text-white/60">
                [main 8f19da2] add key
                <br /> 1 file changed, 2 insertions(+)
              </div>

              <div className="pt-2">
                <span className="text-[#34D399] select-none">
                  ~/atelier-project $
                </span>
                <span className="text-white ml-2 border-r-2 border-white animate-typing inline-block overflow-hidden whitespace-nowrap">
                  git reset HEAD~1 --soft
                </span>
              </div>

              <div className="pt-2 text-[#EF4444] border-2 border-dashed border-[#EF4444]/30 rounded-xl p-2.5 bg-[#EF4444]/5">
                <p className="font-bold text-center text-[10px] uppercase text-[#F87171] mb-1">
                  ✨ Magic Results ✨
                </p>
                <div className="text-[#FCA5A5] text-[10px] leading-relaxed">
                  ✓ Commit deleted from history!
                  <br />
                  ✓ All files safe & kept in Staged area!
                  <br />✓ Secrets removed from Git index!
                </div>
              </div>
            </div>
          </div>
        );

      case 2:
        // Git Stash vault animation
        return (
          <div className="absolute inset-0 bg-[#0A0E1A] flex flex-col items-center justify-center p-6 text-xs text-white">
            <h4 className="text-sm font-black uppercase text-[#60A5FA] mb-6 tracking-wide">
              The Git Stash Vault
            </h4>
            <div className="w-full flex items-center justify-around relative">
              {/* Workspace File */}
              <div className="flex flex-col items-center gap-2">
                <div className="h-16 w-12 border-2 border-dashed border-[#60A5FA] rounded-lg bg-[#1E293B] flex items-center justify-center relative shadow-lg">
                  <div className="h-1.5 w-7 bg-white/20 rounded"></div>
                  <div className="h-1.5 w-6 bg-white/20 rounded mt-1"></div>
                  <div className="h-1.5 w-8 bg-[#60A5FA] rounded mt-1 animate-pulse"></div>
                </div>
                <span className="text-[10px] text-white/50 font-bold uppercase tracking-wider">
                  Workspace
                </span>
              </div>

              {/* Transfer Arrow Line */}
              <div className="absolute left-1/4 right-1/4 h-1 border-t-2 border-dashed border-[#818CF8]/40 flex items-center justify-center top-8">
                <div className="h-2 w-2 rounded-full bg-[#818CF8] animate-ping"></div>
              </div>

              {/* Stash Drawer Vault */}
              <div className="flex flex-col items-center gap-2">
                <div className="h-16 w-16 rounded-xl border-4 border-black bg-gradient-to-br from-[#818CF8] to-[#4F46E5] flex items-center justify-center relative shadow-[0_6px_0_#000000]">
                  <div className="h-2 w-6 bg-yellow-300 rounded border border-black shadow"></div>
                  <div className="absolute -top-1 right-1 h-3.5 w-3.5 rounded-full bg-red-500 text-[8px] font-black flex items-center justify-center border border-black">
                    1
                  </div>
                </div>
                <span className="text-[10px] text-white/50 font-bold uppercase tracking-wider">
                  Stash Stack
                </span>
              </div>
            </div>

            <div className="mt-8 space-y-2 w-full">
              <div className="flex items-center gap-2 px-3 py-2 border-2 border-black bg-[#1E1B4B] rounded-xl">
                <span className="font-mono text-[#818CF8] font-bold">
                  git stash
                </span>
                <span className="text-[10px] text-white/70">
                  → Slides files into vault
                </span>
              </div>
              <div className="flex items-center gap-2 px-3 py-2 border-2 border-black bg-[#1E1B4B] rounded-xl">
                <span className="font-mono text-[#818CF8] font-bold">
                  git stash pop
                </span>
                <span className="text-[10px] text-white/70">
                  → Restores back to workspace
                </span>
              </div>
            </div>
          </div>
        );

      case 3:
        // Merge Conflicts Editor Resolving
        return (
          <div className="absolute inset-0 bg-[#1E1E1E] flex flex-col p-4 text-xs font-mono text-gray-300">
            <div className="flex justify-between items-center pb-2 mb-4 border-b border-gray-800 text-[10px] text-gray-500">
              <span>📄 app/index.js</span>
              <span className="text-yellow-500 font-bold">
                ⚠️ CONFLICT (content)
              </span>
            </div>

            <div className="space-y-1.5 leading-relaxed text-[11px]">
              <div className="text-red-400 bg-red-950/20 border-l-2 border-red-500 px-2 py-0.5">
                {"<<<<<<< HEAD (Current Change)"}
                <div className="text-white font-bold ml-2">
                  const mode = "light_mode";
                </div>
              </div>

              <div className="text-gray-500 border-l-2 border-gray-600 px-2 py-0.5 select-none">
                {"======="}
              </div>

              <div className="text-blue-400 bg-blue-950/20 border-l-2 border-blue-500 px-2 py-0.5">
                <div className="text-white font-bold ml-2">
                  const mode = "dark_mode";
                </div>
                {">>>>>>> master (Incoming Change)"}
              </div>
            </div>

            <div className="mt-6 flex flex-col gap-2">
              <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">
                Resolution Actions:
              </div>
              <div className="flex gap-2">
                <button className="flex-1 py-1.5 px-2 bg-red-900/30 hover:bg-red-900/50 border border-red-600 text-red-200 rounded text-[10px] transition-colors font-bold">
                  Accept Head
                </button>
                <button className="flex-1 py-1.5 px-2 bg-blue-900/30 hover:bg-blue-900/50 border border-blue-600 text-blue-200 rounded text-[10px] transition-colors font-bold">
                  Accept Master
                </button>
              </div>
              <button className="w-full py-2 bg-green-600 hover:bg-green-700 border-2 border-black text-black font-black uppercase text-[10px] rounded-lg shadow-[2px_2px_0_#000] hover:translate-y-[-1px] active:translate-y-0 active:shadow-none transition-all flex items-center justify-center gap-1.5">
                <Sparkles size={12} /> Accept Both Changes
              </button>
            </div>
          </div>
        );

      case 4:
      default:
        // Git Reflog Timeline
        return (
          <div className="absolute inset-0 bg-[#0F172A] flex flex-col p-4 text-xs font-mono text-[#38BDF8]">
            <h4 className="text-xs font-black uppercase text-[#38BDF8] border-b border-[#38BDF8]/20 pb-2 mb-4 tracking-wide flex items-center gap-1.5">
              <span>🕰️</span> Git Action Logs (Reflog)
            </h4>

            <div className="space-y-3 relative before:absolute before:left-3 before:top-2 before:bottom-2 before:w-0.5 before:bg-white/10">
              <div className="flex gap-3 items-start relative z-10">
                <div className="h-6 w-6 rounded-full bg-[#10B981] border border-black flex items-center justify-center text-[10px] text-black font-black">
                  C1
                </div>
                <div>
                  <div className="text-white font-bold text-[10px]">
                    HEAD@{0}: commit: Add Login Page
                  </div>
                  <div className="text-white/40 text-[9px]">Hash: 7a5f93</div>
                </div>
              </div>

              <div className="flex gap-3 items-start relative z-10">
                <div className="h-6 w-6 rounded-full bg-[#EF4444] border border-black flex items-center justify-center text-[10px] text-white font-black">
                  RM
                </div>
                <div>
                  <div className="text-red-400 font-bold text-[10px]">
                    HEAD@{1}: checkout: moving from main to dev
                  </div>
                  <div className="text-white/40 text-[9px]">
                    Branch checkout triggered
                  </div>
                </div>
              </div>

              <div className="flex gap-3 items-start relative z-10 opacity-70">
                <div className="h-6 w-6 rounded-full bg-white/20 border border-black flex items-center justify-center text-[10px] text-white/50 font-bold">
                  C2
                </div>
                <div>
                  <div className="text-white/60 text-[10px]">
                    HEAD@{2}: commit: fix settings layout
                  </div>
                  <div className="text-white/40 text-[9px]">Hash: b51ad8</div>
                </div>
              </div>
            </div>

            <div className="mt-5 p-2 bg-[#1E293B] border-2 border-black rounded-lg">
              <div className="text-[#34D399] font-bold text-[10px]">
                ~/project $ git checkout b51ad8
              </div>
              <div className="text-white/50 text-[9px] mt-1 leading-relaxed">
                ✓ Checkout back to lost commit!
                <br />✓ Branch fully restored!
              </div>
            </div>
          </div>
        );
    }
  };

  return (
    <section className="w-full bg-[#EBEBEB] dark:bg-[#0E0E12] border-t-4 border-b-4 border-black py-16 px-6 font-sans relative overflow-hidden select-none">
      {/* Background Decorative Grid */}
      <div className="absolute inset-0 bg-grid-pattern opacity-5 pointer-events-none"></div>

      <div className="max-w-6xl mx-auto flex flex-col lg:flex-row items-center gap-12 relative z-10">
        {/* LEFT COLUMN: Section Info */}
        <div className="flex-1 text-center lg:text-left space-y-6">
          <div className="inline-block">
            <span className="bg-[#FF6B6B] border-2 border-black px-4 py-2 rounded-full font-black text-xs uppercase tracking-widest text-white shadow-card-sm flex items-center gap-2 w-fit mx-auto lg:mx-0">
              <Sparkles size={14} className="animate-spin" /> Playful Learning
            </span>
          </div>

          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-black text-black dark:text-white uppercase leading-none tracking-tight">
            Trending Git Reels
          </h2>

          <p className="text-lg font-bold text-[#4B5563] dark:text-[#A1A1AA] max-w-xl mx-auto lg:mx-0">
            Swipe through short-form, bite-sized visual animations to master
            complex Git workflows under 10 seconds!
          </p>

          {/* Interactive Navigation Widgets */}
          <div className="flex items-center justify-center lg:justify-start gap-4 pt-4">
            <button
              onClick={handlePrev}
              className="p-3 bg-white dark:bg-[#1E1E24] border-4 border-black text-black dark:text-white rounded-xl shadow-card-sm hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-none transition-all cursor-pointer"
              aria-label="Previous Reel"
            >
              <ChevronLeft size={24} />
            </button>

            <button
              onClick={handleTogglePlay}
              className="px-6 py-3 bg-[#FFD93D] border-4 border-black text-black font-black uppercase text-sm rounded-xl shadow-card-sm hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-none transition-all flex items-center gap-2 cursor-pointer"
            >
              {isPlaying ? (
                <>
                  <Pause size={18} /> Pause Autoplay
                </>
              ) : (
                <>
                  <Play size={18} /> Play Autoplay
                </>
              )}
            </button>

            <button
              onClick={handleNext}
              className="p-3 bg-white dark:bg-[#1E1E24] border-4 border-black text-black dark:text-white rounded-xl shadow-card-sm hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-none transition-all cursor-pointer"
              aria-label="Next Reel"
            >
              <ChevronRight size={24} />
            </button>
          </div>
        </div>

        {/* RIGHT COLUMN: Smartphone Reel Card Mockup */}
        <div
          className="w-full max-w-[340px] aspect-[9/16] relative mx-auto"
          ref={containerRef}
        >
          {/* External Phone Shell Frame */}
          <div className="absolute inset-0 rounded-[3rem] border-8 border-black bg-black shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] overflow-hidden flex flex-col justify-between relative select-none">
            {/* Upper camera notch */}
            <div className="absolute top-2.5 left-1/2 -translate-x-1/2 w-24 h-5 rounded-full bg-black z-50 flex items-center justify-center">
              <div className="h-1.5 w-1.5 rounded-full bg-[#1e293b]"></div>
            </div>

            {/* Content Display Area */}
            <div className="flex-1 w-full relative overflow-hidden bg-slate-950 flex flex-col justify-end">
              {/* Dynamic Animated Interactive View */}
              {renderReelVisual()}

              {/* Glassmorphism Details Overlay at the bottom */}
              <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/90 via-black/40 to-transparent p-4 pb-6 pt-12 flex flex-col text-white z-20">
                {/* Creator Header */}
                <div className="flex items-center gap-2.5 mb-2">
                  <div className="h-8 w-8 rounded-full border border-white/20 bg-slate-800 flex items-center justify-center text-sm shadow">
                    {activeReel.creator.avatar}
                  </div>
                  <div>
                    <span className="font-black text-xs">
                      @{activeReel.creator.username}
                    </span>
                    <span className="block text-[8px] font-bold text-white/50">
                      {activeReel.creator.role}
                    </span>
                  </div>

                  {/* Follow Button */}
                  <button
                    onClick={handleToggleFollow}
                    className={`ml-auto px-2 py-1 text-[9px] font-black border border-white rounded-lg flex items-center gap-1 transition-all ${
                      isFollowing[activeReel.id]
                        ? "bg-white text-black"
                        : "bg-transparent text-white hover:bg-white/10"
                    }`}
                  >
                    {isFollowing[activeReel.id] ? (
                      <>
                        <Check size={8} /> Following
                      </>
                    ) : (
                      <>
                        <Plus size={8} /> Follow
                      </>
                    )}
                  </button>
                </div>

                {/* Reel Caption details */}
                <p className="text-[11px] font-semibold leading-relaxed text-white/90">
                  {activeReel.description}
                </p>

                {/* Tags */}
                <div className="flex gap-1.5 mt-2 flex-wrap text-[9px] font-bold text-sky-400">
                  {activeReel.tags.map((t) => (
                    <span key={t}>{t}</span>
                  ))}
                </div>

                {/* Music rotating audio tag */}
                <div className="flex items-center gap-1.5 mt-3 text-[9px] font-bold text-white/50 italic overflow-hidden">
                  <span className="inline-block animate-marquee whitespace-nowrap">
                    🎵 {activeReel.audio}
                  </span>
                </div>
              </div>
            </div>

            {/* Top segmented progress bars */}
            <div className="absolute top-9 left-4 right-4 z-40 flex gap-1.5">
              {REELS_DATA.map((r, i) => (
                <div
                  key={r.id}
                  className="flex-1 h-1 bg-white/30 rounded overflow-hidden"
                >
                  <div
                    className="h-full bg-[#FFD93D] transition-all"
                    style={{
                      width:
                        i === activeIdx
                          ? `${progress}%`
                          : i < activeIdx
                            ? "100%"
                            : "0%",
                    }}
                  ></div>
                </div>
              ))}
            </div>

            {/* Floating Heart Pops */}
            {heartPops.map((pop) => (
              <div
                key={pop.id}
                className="absolute text-red-500 font-bold text-2xl select-none animate-float-heart z-50 pointer-events-none"
                style={{ left: pop.x, top: pop.y }}
              >
                ❤️
              </div>
            ))}
          </div>

          {/* RIGHT FLOATING BUTTONS LAYOUT (Engagement toolbar) */}
          <div className="absolute right-[-48px] bottom-12 flex flex-col gap-4 items-center z-30 select-none">
            {/* Heart Button */}
            <div className="flex flex-col items-center">
              <button
                onClick={handleLike}
                className={`p-3 rounded-full border-2 border-black shadow-[2px_2px_0_#000] transition-all hover:translate-y-[-1px] active:translate-y-0 active:shadow-none flex items-center justify-center relative cursor-pointer ${
                  activeLikes.liked
                    ? "bg-[#FF6B6B] text-white"
                    : "bg-white text-black dark:bg-[#1E1E24] dark:text-white"
                }`}
              >
                <Heart
                  size={20}
                  fill={activeLikes.liked ? "currentColor" : "none"}
                />
              </button>
              <span className="text-[10px] font-black text-black dark:text-white mt-1">
                {activeLikes.count}
              </span>
            </div>

            {/* Comment Button */}
            <div className="flex flex-col items-center">
              <button
                onClick={() => setShowComments(true)}
                className="p-3 rounded-full border-2 border-black bg-white dark:bg-[#1E1E24] text-black dark:text-white shadow-[2px_2px_0_#000] hover:translate-y-[-1px] active:translate-y-0 active:shadow-none flex items-center justify-center cursor-pointer"
              >
                <MessageSquare size={20} />
              </button>
              <span className="text-[10px] font-black text-black dark:text-white mt-1">
                {activeReel.commentsCount}
              </span>
            </div>

            {/* Share Button */}
            <button
              onClick={handleShare}
              className="p-3 rounded-full border-2 border-black bg-white dark:bg-[#1E1E24] text-black dark:text-white shadow-[2px_2px_0_#000] hover:translate-y-[-1px] active:translate-y-0 active:shadow-none flex items-center justify-center cursor-pointer"
            >
              <Share2 size={20} />
            </button>
          </div>
        </div>
      </div>

      {/* COMMENTS SIDE DRAWER DIALOG MOCKUP */}
      {showComments && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[999] flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-white dark:bg-[#1C1C24] border-4 border-black rounded-2xl p-6 shadow-[8px_8px_0_#000] relative">
            <button
              onClick={() => setShowComments(false)}
              className="absolute top-4 right-4 text-xs font-black border-2 border-black px-2.5 py-1 hover:bg-slate-50 dark:text-white dark:border-white/20 dark:hover:bg-white/10 rounded-lg cursor-pointer"
            >
              Close
            </button>

            <h3 className="text-lg font-black uppercase text-black dark:text-white mb-4 pb-2 border-b-2 border-dashed border-slate-200 dark:border-slate-800">
              💬 Comments ({comments[activeReel.id]?.length || 0})
            </h3>

            {/* Comments List */}
            <div className="max-h-[300px] overflow-y-auto space-y-4 mb-4 pr-1 text-slate-800 dark:text-slate-100">
              {(comments[activeReel.id] || []).map((c, i) => (
                <div
                  key={i}
                  className="flex gap-3 items-start text-xs border-b border-slate-100 dark:border-slate-800 pb-3"
                >
                  <div className="h-8 w-8 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-sm">
                    {c.avatar}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-1.5">
                      <span className="font-black">@{c.username}</span>
                      <span className="text-[10px] text-slate-400 font-bold">
                        {c.time}
                      </span>
                    </div>
                    <p className="mt-1 text-slate-600 dark:text-slate-350 font-semibold leading-relaxed">
                      {c.text}
                    </p>
                  </div>
                </div>
              ))}
            </div>

            {/* Comment Form */}
            <form onSubmit={handleAddComment} className="flex gap-2">
              <input
                type="text"
                placeholder="Type your comment..."
                value={newComment}
                onChange={(e) => setNewComment(e.target.value)}
                className="flex-1 px-3 py-2 border-2 border-black rounded-xl text-xs font-bold outline-none dark:bg-[#121218] dark:border-white/10 dark:text-white"
              />
              <button
                type="submit"
                className="px-4 py-2 bg-[#FF6B6B] text-white border-2 border-black rounded-xl text-xs font-black uppercase shadow-card-sm hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-none cursor-pointer"
              >
                Post
              </button>
            </form>
          </div>
        </div>
      )}
    </section>
  );
}

export default TrendingReels;
