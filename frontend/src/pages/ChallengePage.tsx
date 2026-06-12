import { useState } from "react";
import { Search } from "lucide-react";
import { SectionCard } from "../components/ui/SectionCard";
import { challengeCards, type Difficulty } from "../lib/data";
import clsx from "clsx";

const difficulties: Difficulty[] = ["beginner", "intermediate", "advanced"];

export function ChallengePage() {
  const [search, setSearch] = useState("");
  const [difficulty, setDifficulty] = useState<Difficulty | null>(null);

  const filtered = challengeCards.filter((c) => {
    const matchesSearch =
      !search ||
      c.title.toLowerCase().includes(search.toLowerCase()) ||
      c.summary.toLowerCase().includes(search.toLowerCase());
    const matchesDifficulty = !difficulty || c.difficulty === difficulty;
    return matchesSearch && matchesDifficulty;
  });

  return (
    <div className="space-y-6">
      <SectionCard eyebrow="Challenges" title="Recommended contribution drills">
        <p className="max-w-2xl text-sm leading-6 text-muted">
          Practice branching, clean commits, pull request preparation, and
          review-response workflows. Recommendation logic can adapt to progress,
          badges, and recent learner friction points.
        </p>
      </SectionCard>

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <input
            type="text"
            placeholder="Search challenges…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-xl border border-outline bg-surface-high/60 py-2.5 pl-10 pr-4 text-sm text-text placeholder-muted backdrop-blur-xl focus:outline-none focus:ring-2 focus:ring-primary/40"
          />
        </div>

        <div className="flex gap-1.5">
          {difficulties.map((d) => (
            <button
              key={d}
              onClick={() => setDifficulty(difficulty === d ? null : d)}
              className={clsx(
                "rounded-lg px-3 py-1.5 text-xs font-medium capitalize transition-colors",
                difficulty === d
                  ? "bg-primary text-white"
                  : "bg-surface-low text-muted hover:bg-surface-low/80 hover:text-text",
              )}
            >
              {d}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {filtered.map((item) => (
          <SectionCard key={item.title} eyebrow={item.badge} title={item.title}>
            <p className="text-sm leading-6 text-muted">{item.summary}</p>
            <button className="mt-5 rounded-xl bg-surface-low px-4 py-2 text-sm font-semibold text-primary">
              Open challenge
            </button>
          </SectionCard>
        ))}
        {filtered.length === 0 && (
          <p className="col-span-full py-10 text-center text-sm text-muted">
            No challenges match your filters.
          </p>
        )}
      </div>
    </div>
  );
}
