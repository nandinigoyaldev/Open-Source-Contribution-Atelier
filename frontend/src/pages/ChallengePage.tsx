import { useRef, useState } from "react";
import { Search, Upload, Trophy, HelpCircle, ArrowUpRight } from "lucide-react";
import { challengeCards, type Difficulty } from "../lib/data";
import { useNavigate } from "react-router-dom";
import clsx from "clsx";
import { useAuth } from "../features/auth/AuthContext";
import { fetchApi } from "../lib/api";
import toast from "react-hot-toast";

const difficulties: Difficulty[] = ["beginner", "intermediate", "advanced"];

export function ChallengePage() {
  const { user } = useAuth();
  const navigate = useNavigate();
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
      toast.success("Challenges uploaded successfully!");
    } catch (error: unknown) {
      const errMsg = (error as Error).message || "Failed to upload";
      setUploadMessage("❌ Error: " + errMsg);
      toast.error("Upload failed: " + errMsg);
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
    <div className="max-w-6xl mx-auto p-4 space-y-10 animate-fade-in select-none">
      {/* Title Header Card */}
      <div className="border-4 border-black bg-white p-6 rounded-2xl shadow-card dark:bg-[#1a191f] dark:border-white/10 dark:shadow-none">
        <h1 className="text-3xl sm:text-4xl font-black text-slate-900 dark:text-white uppercase tracking-tight flex items-center gap-3">
          <Trophy size={36} className="text-[#ffd166]" /> Contribution
          Challenges
        </h1>
        <p className="text-sm font-bold text-slate-500 dark:text-slate-400 mt-2 leading-relaxed max-w-2xl">
          Complete interactive git exercises and sandbox contribution drills.
          Improve your open source workflow by triaging issues, rebasing messy
          branches, and resolving merge conflicts.
        </p>
      </div>

      {/* Admin Upload Section */}
      {user?.is_staff && (
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 rounded-2xl border-4 border-black bg-[#ffebc2] p-5 shadow-card dark:bg-yellow-900/20 dark:border-yellow-700/50">
          <div>
            <h3 className="font-black text-sm uppercase flex items-center gap-2 text-slate-900 dark:text-white">
              <span>🛠️</span> Admin Tools
            </h3>
            <p className="text-xs text-slate-700 dark:text-slate-400 mt-1 font-bold">
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
              className="flex-1 sm:flex-none flex items-center justify-center gap-2 rounded-xl border-2 border-black bg-white px-4 py-2.5 text-xs font-black shadow-card-sm hover:-translate-y-0.5 disabled:opacity-50 transition-all cursor-pointer text-slate-900"
            >
              <Upload size={16} />
              {isUploading ? "Uploading..." : "Upload JSON File"}
            </button>
          </div>
          {uploadMessage && (
            <div className="w-full sm:w-auto text-xs font-black border-2 border-black bg-white px-3 py-2 rounded-lg text-slate-900">
              {uploadMessage}
            </div>
          )}
        </div>
      )}

      {/* Search and Filters */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-slate-50 dark:bg-slate-900/50 p-4 border-2 border-black dark:border-white/10 rounded-2xl">
        <div className="relative w-full sm:w-80">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search challenges..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-xl border-2 border-black bg-white py-2 pl-10 pr-4 text-xs font-bold text-slate-900 focus:outline-none dark:bg-[#121216] dark:text-white dark:border-white/15 placeholder-slate-400"
          />
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-black uppercase text-slate-400 tracking-wider mr-2">
            Difficulty:
          </span>
          <button
            onClick={() => setDifficulty(null)}
            className={clsx(
              "px-3 py-1.5 rounded-xl text-xs font-black uppercase border-2 border-black transition-all hover:-translate-y-0.5 cursor-pointer shadow-card-xs",
              difficulty === null
                ? "bg-black text-white dark:bg-white dark:text-black"
                : "bg-white text-slate-800 dark:bg-slate-800 dark:text-white dark:border-slate-700",
            )}
          >
            All
          </button>
          {difficulties.map((d) => (
            <button
              key={d}
              onClick={() => setDifficulty(d)}
              className={clsx(
                "px-3 py-1.5 rounded-xl text-xs font-black uppercase border-2 border-black transition-all hover:-translate-y-0.5 cursor-pointer shadow-card-xs",
                difficulty === d
                  ? d === "beginner"
                    ? "bg-green-400 text-black border-black"
                    : d === "intermediate"
                      ? "bg-amber-400 text-black border-black"
                      : "bg-red-400 text-black border-black"
                  : "bg-white text-slate-800 dark:bg-slate-800 dark:text-white dark:border-slate-700",
              )}
            >
              {d}
            </button>
          ))}
        </div>
      </div>

      {/* Challenges Grid */}
      <div className="grid gap-6 md:grid-cols-2">
        {filtered.map((item) => (
          <div
            key={item.title}
            className="border-4 border-black bg-white rounded-2xl shadow-card dark:bg-[#1a191f] dark:border-white/10 dark:shadow-none flex flex-col justify-between overflow-hidden"
          >
            {/* Header portion */}
            <div className="p-6 border-b-2 border-black/5 dark:border-white/5 space-y-3 flex-1">
              <div className="flex items-center justify-between">
                <span
                  className={clsx(
                    "text-[9px] font-black uppercase tracking-widest px-2.5 py-1 rounded-full border-2 border-black shadow-card-xs",
                    item.difficulty === "beginner" &&
                      "bg-green-100 text-green-800",
                    item.difficulty === "intermediate" &&
                      "bg-amber-100 text-amber-850",
                    item.difficulty === "advanced" && "bg-red-100 text-red-800",
                  )}
                >
                  {item.difficulty}
                </span>
                <span className="text-[10px] font-black uppercase text-slate-400 tracking-wider">
                  {item.badge}
                </span>
              </div>
              <h3 className="text-lg font-black text-slate-900 dark:text-white">
                {item.title}
              </h3>
              <p className="text-xs font-medium text-slate-500 dark:text-slate-400 leading-relaxed">
                {item.summary}
              </p>
            </div>

            {/* Bottom button strip */}
            <div className="bg-slate-50 dark:bg-slate-900/40 p-4 flex items-center justify-between">
              <span className="text-[10px] font-black text-[#8884d8] uppercase tracking-wider flex items-center gap-1">
                <span>⚡</span> +50 XP Reward
              </span>
              <button
                onClick={() => navigate("/sandbox")}
                className="px-4 py-2 border-2 border-black bg-[#ffd166] text-black text-xs font-black uppercase tracking-wider rounded-xl shadow-card-sm hover:-translate-y-0.5 hover:shadow-card active:translate-y-0 active:shadow-none transition-all flex items-center gap-1 cursor-pointer"
              >
                Launch Drill <ArrowUpRight size={14} />
              </button>
            </div>
          </div>
        ))}
        {filtered.length === 0 && (
          <div className="col-span-full border-4 border-dashed border-black/10 dark:border-white/10 rounded-2xl py-16 text-center">
            <HelpCircle size={40} className="mx-auto text-slate-300 mb-3" />
            <p className="text-sm font-bold text-slate-400">
              No matching drills found. Try loosening your search or difficulty
              filters!
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export default ChallengePage;
