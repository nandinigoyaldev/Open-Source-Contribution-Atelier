import { useState, useEffect, useRef } from "react";
import { fetchApi } from "../lib/api";
import { Flame, GitPullRequest, BookOpen, Star, Zap, Trophy, ArrowUp } from "lucide-react";

// ─── Types ───────────────────────────────────────────────────────────────────

interface TickerEvent {
  id: string;
  username: string;
  avatar_url: string;
  type: "pr_merge" | "lesson" | "streak" | "xp_gain" | "tier_upgrade" | "joined";
  text: string;
  xp?: number;
  timestamp: Date;
  exiting?: boolean;
}

interface TickerProps {
  /** Pass live leaderboard rows so the generator uses real usernames */
  contributorNames: string[];
}

// ─── Constants ───────────────────────────────────────────────────────────────

const EVENT_ICONS: Record<TickerEvent["type"], React.ReactNode> = {
  pr_merge:     <GitPullRequest className="w-3.5 h-3.5 flex-shrink-0" />,
  lesson:       <BookOpen       className="w-3.5 h-3.5 flex-shrink-0" />,
  streak:       <Flame          className="w-3.5 h-3.5 flex-shrink-0" />,
  xp_gain:      <Zap           className="w-3.5 h-3.5 flex-shrink-0" />,
  tier_upgrade: <Trophy        className="w-3.5 h-3.5 flex-shrink-0" />,
  joined:       <Star          className="w-3.5 h-3.5 flex-shrink-0" />,
};

const EVENT_COLORS: Record<TickerEvent["type"], string> = {
  pr_merge:     "bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300 border-green-300 dark:border-green-700",
  lesson:       "bg-blue-100  dark:bg-blue-900/40  text-blue-700  dark:text-blue-300  border-blue-300  dark:border-blue-700",
  streak:       "bg-orange-100 dark:bg-orange-900/40 text-orange-700 dark:text-orange-300 border-orange-300 dark:border-orange-700",
  xp_gain:      "bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 border-amber-300 dark:border-amber-700",
  tier_upgrade: "bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300 border-purple-300 dark:border-purple-700",
  joined:       "bg-pink-100  dark:bg-pink-900/40  text-pink-700  dark:text-pink-300  border-pink-300  dark:border-pink-700",
};

const FALLBACK_NAMES = [
  "devhero", "codestar", "gitwhiz", "prmaster", "bugfixer",
  "opensrc", "patchpro", "commitking", "mergebot", "linuxlad",
];

// ─── Fake event generator (uses real names when provided) ────────────────────

function makeFakeEvent(names: string[]): TickerEvent {
  const pool = names.length > 0 ? names : FALLBACK_NAMES;
  const username = pool[Math.floor(Math.random() * pool.length)];
  const avatar_url = `https://github.com/${username}.png`;

  const templates: Array<{ type: TickerEvent["type"]; text: string; xp?: number }> = [
    { type: "pr_merge",     text: "just merged a PR! 🚀",       xp: Math.floor(Math.random() * 60) + 30 },
    { type: "pr_merge",     text: "got a PR merged — nice! 🎉",  xp: Math.floor(Math.random() * 50) + 25 },
    { type: "lesson",       text: "completed a lesson 📚",        xp: Math.floor(Math.random() * 20) + 10 },
    { type: "lesson",       text: "aced a quiz! ✅",              xp: Math.floor(Math.random() * 30) + 15 },
    { type: "streak",       text: `hit a ${Math.floor(Math.random() * 20) + 5}-day streak! 🔥`, xp: undefined },
    { type: "streak",       text: "is on fire — streak extended! 🔥", xp: undefined },
    { type: "xp_gain",      text: "is climbing the XP charts! ⚡", xp: Math.floor(Math.random() * 100) + 50 },
    { type: "tier_upgrade", text: "just reached Gold tier! 🥇",   xp: undefined },
    { type: "tier_upgrade", text: "earned Diamond status! 💎",    xp: undefined },
    { type: "joined",       text: "joined the leaderboard! 👋",    xp: 10 },
  ];

  const tpl = templates[Math.floor(Math.random() * templates.length)];

  return {
    id: `${username}-${Date.now()}-${Math.random()}`,
    username,
    avatar_url,
    type: tpl.type,
    text: tpl.text,
    xp: tpl.xp,
    timestamp: new Date(),
  };
}

// ─── Map API community feed events → TickerEvent format ─────────────────────

function mapFeedEvent(raw: any, idx: number): TickerEvent | null {
  try {
    const username = raw.user?.username || raw.username || `user${idx}`;
    const avatar_url = raw.user?.avatar_url || `https://github.com/${username}.png`;
    const eventType: string = raw.event_type || raw.type || "";

    let type: TickerEvent["type"] = "xp_gain";
    let text = "was active on the platform ⚡";
    let xp: number | undefined;

    if (eventType.includes("pr") || eventType.includes("merge")) {
      type = "pr_merge";
      text = "just merged a PR! 🚀";
      xp = raw.xp_earned || 50;
    } else if (eventType.includes("lesson") || eventType.includes("quiz")) {
      type = "lesson";
      text = "completed a lesson 📚";
      xp = raw.xp_earned || 15;
    } else if (eventType.includes("streak")) {
      type = "streak";
      text = `is on a ${raw.streak_days || ""}day streak! 🔥`;
    } else if (eventType.includes("tier")) {
      type = "tier_upgrade";
      text = `reached ${raw.tier || "a new"} tier! 🏆`;
    } else if (eventType.includes("join") || eventType.includes("signup")) {
      type = "joined";
      text = "joined the platform! 👋";
      xp = 10;
    }

    return {
      id: raw.id?.toString() || `feed-${idx}`,
      username,
      avatar_url,
      type,
      text,
      xp,
      timestamp: raw.created_at ? new Date(raw.created_at) : new Date(),
    };
  } catch {
    return null;
  }
}

// ─── Component ───────────────────────────────────────────────────────────────

const MAX_VISIBLE = 6;
const GEN_INTERVAL_MS = 3800;
const EXIT_DELAY_MS   = 350;

export function LeaderboardActivityTicker({ contributorNames }: TickerProps) {
  const [events, setEvents] = useState<TickerEvent[]>([]);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const hasFetchedRef = useRef(false);

  // Try to seed initial events from the community feed API
  useEffect(() => {
    if (hasFetchedRef.current) return;
    hasFetchedRef.current = true;

    fetchApi("/progress/feed/?limit=8", { suppressErrorToast: true })
      .then((res: any) => {
        const items: any[] = Array.isArray(res?.results)
          ? res.results
          : Array.isArray(res)
          ? res
          : [];

        const mapped = items
          .map((r, i) => mapFeedEvent(r, i))
          .filter(Boolean) as TickerEvent[];

        if (mapped.length > 0) {
          setEvents(mapped.slice(0, MAX_VISIBLE));
        }
      })
      .catch(() => {
        // silently ignore — we'll use the fake generator
      });
  }, []);

  // Generate new events on a timed interval
  useEffect(() => {
    intervalRef.current = setInterval(() => {
      const newEvent = makeFakeEvent(contributorNames);

      setEvents((prev) => {
        // If at limit, mark the oldest for exit
        if (prev.length >= MAX_VISIBLE) {
          const [oldest, ...rest] = prev;
          const exiting = { ...oldest, exiting: true };

          // Remove after animation
          setTimeout(() => {
            setEvents((cur) => cur.filter((e) => e.id !== oldest.id));
          }, EXIT_DELAY_MS);

          return [exiting, ...rest, newEvent];
        }
        return [...prev, newEvent];
      });
    }, GEN_INTERVAL_MS);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [contributorNames]);

  const formatTime = (d: Date) =>
    d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

  return (
    <div className="rounded-[2rem] border-4 border-black bg-white dark:bg-[#1f1c18] dark:border-[#2e2924] shadow-card overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3.5 border-b-4 border-black dark:border-[#2e2924] bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500">
        <div className="flex items-center gap-2">
          {/* Pulse dot */}
          <span className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-white opacity-75" />
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-white" />
          </span>
          <span className="font-black text-xs uppercase tracking-widest text-white">
            Live Activity Feed
          </span>
        </div>
        <ArrowUp className="w-3 h-3 text-white/70 animate-bounce" />
      </div>

      {/* Events list */}
      <div className="flex flex-col-reverse gap-2 p-4 min-h-[280px] max-h-[360px] overflow-hidden">
        {events.length === 0 && (
          <div className="flex items-center justify-center h-full text-xs font-bold text-gray-400 dark:text-[#6b6460] py-8">
            Waiting for activity…
          </div>
        )}

        {events.map((evt) => (
          <div
            key={evt.id}
            className={`
              ticker-event
              flex items-start gap-2.5 px-3 py-2.5 rounded-2xl border-2 text-xs font-bold
              transition-all duration-300 select-none
              ${EVENT_COLORS[evt.type]}
              ${evt.exiting ? "ticker-event-exit" : ""}
            `}
          >
            {/* Avatar */}
            <img
              src={evt.avatar_url}
              alt={evt.username}
              className="w-7 h-7 rounded-full border-2 border-current object-cover flex-shrink-0 mt-0.5"
              onError={(e) => {
                (e.target as HTMLImageElement).src = "https://github.com/github.png";
              }}
            />

            {/* Text */}
            <div className="flex-1 min-w-0">
              <span className="flex items-center gap-1 flex-wrap leading-snug">
                {EVENT_ICONS[evt.type]}
                <span className="font-black truncate max-w-[80px]">@{evt.username}</span>
                <span className="font-bold opacity-90">{evt.text}</span>
                {evt.xp !== undefined && (
                  <span className="ml-auto font-black text-green-600 dark:text-green-400 whitespace-nowrap">
                    +{evt.xp} XP
                  </span>
                )}
              </span>
              <p className="text-[10px] opacity-60 mt-0.5 font-mono">
                {formatTime(evt.timestamp)}
              </p>
            </div>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="px-5 py-2 border-t-2 border-black/10 dark:border-[#2e2924] text-[10px] font-black text-gray-400 dark:text-[#6b6460] flex items-center gap-1">
        <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
        Updates every few seconds
      </div>
    </div>
  );
}

export default LeaderboardActivityTicker;
