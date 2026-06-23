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
            className="w-full rounded-lg border border-outline bg-surface-high/60 py-2.5 pl-10 pr-4 text-sm text-text placeholder-muted backdrop-blur-xl focus:outline-none focus:ring-2 focus:ring-primary/40"
          />
        </div>

        <div className="flex gap-2">
          {difficulties.map((d) => (
            <button
              key={d}
              onClick={() => setDifficulty(difficulty === d ? null : d)}
              className={clsx(
                "rounded-lg px-3 py-1.5 text-xs font-black capitalize transition-all border-2 border-black shadow-card-sm hover:-translate-y-0.5",
                difficulty === d
                  ? "bg-primary text-black"
                  : "bg-white text-muted hover:bg-surface-low hover:text-text",
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
            <button className="mt-5 rounded-lg bg-surface-low border-2 border-black px-4 py-2 text-sm font-black text-black shadow-card-sm hover:-translate-y-0.5 active:translate-y-0 transition-all cursor-pointer">
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
