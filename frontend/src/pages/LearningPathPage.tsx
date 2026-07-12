import React from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ArrowLeft, Sparkles } from "lucide-react";
import { fetchApi } from "../lib/api";

interface ModuleData {
  id: string;
  title: string;
  description: string;
  status: "completed" | "in progress" | "not started";
  score: number;
  explanation: string;
  lessons_count: number;
  completed_lessons_count: number;
}

interface LearningPathResponse {
  modules: ModuleData[];
  next_step: ModuleData | null;
}

export const LearningPathPage: React.FC = () => {
  const { data, isLoading, error } = useQuery<LearningPathResponse>({
    queryKey: ["learningPath"],
    queryFn: () => fetchApi("/users/me/learning-path/"),
  });

  if (isLoading) {
    return (
      <div className="pt-24 max-w-7xl mx-auto px-4 flex justify-center items-center h-screen">
        <div className="font-black text-2xl animate-pulse text-primary">
          Analyzing your progress & quiz performance... 🧠
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="pt-24 max-w-7xl mx-auto px-4">
        <div className="p-8 text-center bg-red-100 rounded-2xl border-4 border-black font-bold text-red-800 shadow-card">
          Failed to load your Personalized Learning Path. Please make sure the
          backend is running.
        </div>
      </div>
    );
  }

  const { modules, next_step } = data;

  return (
    <div className="max-w-7xl mx-auto px-4 pt-24 pb-12 space-y-10">
      {/* Header Navigation */}
      <div className="flex items-center gap-4">
        <Link
          to="/dashboard"
          className="p-2 border-2 border-black rounded-full hover:bg-gray-100 dark:border-[#2e2924] dark:hover:bg-[#1f1c18] transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <h1 className="text-3xl font-black">Personalized Learning Path</h1>
      </div>

      {/* Description Banner */}
      <section className="rounded-[2rem] border-4 border-black bg-[#c3c0ff] p-8 sm:p-10 shadow-card relative overflow-hidden dark:border-[#2e2924]">
        <div className="relative z-10 max-w-3xl">
          <span className="font-black text-xs bg-white text-black px-3 py-1 rounded-full border-2 border-black inline-block shadow-card-sm mb-4 dark:bg-[#151411] dark:text-[#f0ebe2] dark:border-[#2e2924]">
            SMART CURRICULUM RECOMMENDATION ✨
          </span>
          <h2 className="text-3xl sm:text-4xl font-black text-black drop-shadow-[2px_2px_0_#fff] mb-4 dark:text-[#f0ebe2] dark:drop-shadow-none">
            Your Tailored Route to Contribution Mastery
          </h2>
          <p className="text-base font-bold text-black bg-white/95 p-4 rounded-lg border-4 border-black shadow-card-sm leading-relaxed dark:bg-[#151411] dark:border-[#2e2924] dark:text-[#f0ebe2]">
            Our rule-based recommendation algorithm analyzes your lesson
            completions, quiz attempts, and badge milestones. It identifies weak
            quiz areas, prioritize in-progress modules, and keeps you moving
            forward efficiently.
          </p>
        </div>
        <div className="absolute -right-6 -bottom-6 text-[10rem] opacity-20 rotate-12 pointer-events-none">
          🗺️
        </div>
      </section>

      {/* Recommended Next Step Section */}
      {next_step && (
        <section className="rounded-[2rem] border-4 border-black bg-white p-6 sm:p-8 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none space-y-6">
          <div className="flex items-center gap-3">
            <span className="text-3xl">🎯</span>
            <div>
              <h3 className="font-black text-2xl uppercase tracking-tight">
                Recommended Next Step
              </h3>
              <p className="text-xs text-muted dark:text-[#c4bbae] font-bold">
                Highest recommendation score: {next_step.score} pts
              </p>
            </div>
          </div>

          <div className="grid gap-6 md:grid-cols-[1.5fr_1fr]">
            {/* Module Overview */}
            <div className="border-4 border-black p-6 rounded-2xl bg-surface-low dark:bg-[#151411] dark:border-[#2e2924] flex flex-col justify-between space-y-4">
              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="font-black text-xs uppercase tracking-widest bg-black text-white px-2.5 py-1 rounded-full dark:bg-[#2e2924]">
                    {next_step.id}
                  </span>
                  <span
                    className={`font-black text-xs uppercase px-2.5 py-1 rounded-full border-2 border-black ${
                      next_step.status === "completed"
                        ? "bg-green-400"
                        : next_step.status === "in progress"
                          ? "bg-blue-300"
                          : "bg-amber-300"
                    }`}
                  >
                    {next_step.status}
                  </span>
                </div>
                <h4 className="text-2xl font-black mb-2">{next_step.title}</h4>
                <p className="font-bold text-sm text-muted dark:text-[#c4bbae]">
                  {next_step.description}
                </p>
              </div>

              {/* Progress bar */}
              <div className="space-y-2">
                <div className="flex justify-between text-xs font-black">
                  <span>MODULE COMPLETION</span>
                  <span>
                    {next_step.completed_lessons_count} /{" "}
                    {next_step.lessons_count} LESSONS
                  </span>
                </div>
                <div className="w-full h-5 bg-white border-2 border-black rounded-full overflow-hidden dark:bg-[#151411] dark:border-[#2e2924]">
                  <div
                    className="h-full bg-green-500 border-r-2 border-black transition-all duration-500"
                    style={{
                      width: `${
                        next_step.lessons_count > 0
                          ? (next_step.completed_lessons_count /
                              next_step.lessons_count) *
                            100
                          : 0
                      }%`,
                    }}
                  />
                </div>
              </div>
            </div>

            {/* Explanation panel */}
            <div className="border-4 border-black p-6 rounded-2xl bg-amber-50 dark:bg-[#1c1915] dark:border-[#2e2924] flex flex-col justify-between space-y-4">
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
                  <Sparkles className="w-6 h-6 animate-pulse" />
                  <h4 className="font-black text-lg">Why this next?</h4>
                </div>
                <p className="font-bold text-sm text-black/90 dark:text-[#f0ebe2] leading-relaxed">
                  {next_step.explanation}
                </p>
              </div>

              <Link
                to="/dashboard"
                className="w-full flex items-center justify-center gap-2 rounded-lg bg-black text-white hover:bg-black/90 dark:bg-white dark:text-black font-black py-3 border-2 border-black shadow-card-sm hover:-translate-y-0.5 transition-all text-sm uppercase tracking-wide cursor-pointer text-center"
              >
                Go to Dashboard & Resume 🚀
              </Link>
            </div>
          </div>
        </section>
      )}

      {/* Curriculum Module Cards Grid */}
      <section className="space-y-6">
        <h3 className="text-2xl font-black flex items-center gap-2">
          <span>📚</span> All Curriculum Modules ({modules.length})
        </h3>

        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {modules.map((mod) => (
            <div
              key={mod.id}
              className="flex flex-col justify-between p-6 bg-white border-4 border-black rounded-2xl shadow-card-sm hover:shadow-card hover:-translate-y-1 transition-all dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none"
            >
              <div>
                <div className="flex justify-between items-center mb-4">
                  <span className="font-black text-[10px] uppercase tracking-widest bg-black text-white px-2 py-0.5 rounded-full dark:bg-[#2e2924]">
                    {mod.id}
                  </span>
                  <span
                    className={`font-black text-[10px] uppercase px-2 py-0.5 rounded-full border-2 border-black ${
                      mod.status === "completed"
                        ? "bg-green-400 text-black"
                        : mod.status === "in progress"
                          ? "bg-blue-300 text-black"
                          : "bg-gray-200 text-black dark:bg-gray-700 dark:text-white"
                    }`}
                  >
                    {mod.status}
                  </span>
                </div>
                <h4 className="text-xl font-black mb-2 dark:text-[#f0ebe2]">
                  {mod.title}
                </h4>
                <p className="text-xs font-bold text-muted mb-4 dark:text-[#c4bbae]">
                  {mod.description}
                </p>
              </div>

              <div className="space-y-4 pt-4 border-t-2 border-dashed border-black/10 dark:border-white/10">
                <div className="flex justify-between items-center text-[10px] font-black">
                  <span>PROGRESS</span>
                  <span>
                    {mod.completed_lessons_count} / {mod.lessons_count} LESSONS
                  </span>
                </div>
                <div className="w-full h-3 bg-surface-low border-2 border-black rounded-full overflow-hidden dark:bg-[#151411] dark:border-[#2e2924]">
                  <div
                    className="h-full bg-green-500 transition-all duration-300"
                    style={{
                      width: `${
                        mod.lessons_count > 0
                          ? (mod.completed_lessons_count / mod.lessons_count) *
                            100
                          : 0
                      }%`,
                    }}
                  />
                </div>
                {mod.status !== "completed" && mod.score > 0 && (
                  <div className="text-[10px] font-bold text-primary dark:text-[#f0ebe2] bg-primary/10 dark:bg-primary/5 p-2 rounded border border-primary/20 dark:border-primary/10">
                    💡 recommendation score: {mod.score} pts
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
};

export default LearningPathPage;
