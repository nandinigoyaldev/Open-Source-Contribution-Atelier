import { useRef, useState } from "react";
import { Search, Upload } from "lucide-react";
import { SectionCard } from "../components/ui/SectionCard";
import { challengeCards, type Difficulty } from "../lib/data";
import clsx from "clsx";
import { useAuth } from "../features/auth/AuthContext";
import { fetchApi } from "../lib/api";

const difficulties: Difficulty[] = ["beginner", "intermediate", "advanced"];

export function ChallengePage() {
  const { user } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState("");

  const [search, setSearch] = useState("");
  const [difficulty, setDifficulty] = useState<Difficulty | null>(null);

  const handleFileUpload = async (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadMessage("");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetchApi("/challenges/bulk-upload/", {
        method: "POST",
        body: formData,
      });
      setUploadMessage("✅ " + (response.message || "Upload successful"));
    } catch (error: unknown) {
      setUploadMessage("❌ Error: " + (error.message || "Failed to upload"));
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

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
      {user?.is_staff && (
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 rounded-2xl border-4 border-black bg-[#ffebc2] p-5 shadow-card dark:bg-yellow-900/20 dark:border-yellow-700/50">
          <div>
            <h3 className="font-black text-sm uppercase flex items-center gap-2">
              <span className="text-lg">🛠️</span> Admin Tools
            </h3>
            <p className="text-xs text-muted dark:text-[#c4bbae] mt-1 font-bold">
              Bulk import new challenges via JSON. Format: Array of objects.
            </p>
          </div>
          <div className="flex items-center gap-3 w-full sm:w-auto">
            <input
              type="file"
              accept=".json"
              className="hidden"
              ref={fileInputRef}
              onChange={handleFileUpload}
              disabled={isUploading}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              className="flex-1 sm:flex-none flex items-center justify-center gap-2 rounded-xl border-4 border-black bg-white px-4 py-2.5 text-xs font-black shadow-card-sm hover:-translate-y-0.5 disabled:opacity-50 transition-all cursor-pointer dark:bg-[#151411] dark:border-[#2e2924] dark:text-[#f0ebe2]"
            >
              <Upload size={16} />
              {isUploading ? "Uploading..." : "Upload JSON File"}
            </button>
          </div>
          {uploadMessage && (
            <div className="w-full sm:w-auto text-xs font-black border-2 border-black bg-white px-3 py-2 rounded-lg dark:bg-[#151411]">
              {uploadMessage}
            </div>
          )}
        </div>
      )}

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
