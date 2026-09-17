import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  BookOpen,
  Bot,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  Code2,
  HelpCircle,
  Lightbulb,
  Loader2,
  MessageSquare,
  Play,
  RotateCcw,
  Send,
  Sparkles,
  Target,
  Terminal,
  Zap,
} from "lucide-react";
import { fetchLessonsApi, fallbackLessons, SEVEN_LEVELS, Lesson } from "../lib/lessons";
import { fetchApi, fetchStreamApi } from "../lib/api";
import { useAuth } from "../features/auth/AuthContext";
import toast from "react-hot-toast";

interface TutorMessage {
  role: "user" | "assistant";
  content: string;
}

export function LearnPage() {
  const { slug } = useParams<{ slug?: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [lessonsList, setLessonsList] = useState<Lesson[]>(fallbackLessons);
  const [activeLesson, setActiveLesson] = useState<Lesson>(fallbackLessons[0]);
  const [completedSlugs, setCompletedSlugs] = useState<Set<string>>(new Set());

  // Interactive exercise state
  const [userInput, setUserInput] = useState("");
  const [evaluationResult, setEvaluationResult] = useState<{
    is_correct?: boolean;
    feedback?: string;
    hint?: string;
    mistake_detected?: string | null;
  } | null>(null);
  const [isEvaluating, setIsEvaluating] = useState(false);

  // AI Tutor state
  const [tutorMessages, setTutorMessages] = useState<TutorMessage[]>([]);
  const [tutorInput, setTutorInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [hintLevel, setHintLevel] = useState(1);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  // Load completed lessons from localStorage
  useEffect(() => {
    const saved = localStorage.getItem("completed_lesson_slugs");
    if (saved) {
      try {
        setCompletedSlugs(new Set(JSON.parse(saved)));
      } catch {}
    }
  }, []);

  // Fetch lessons from backend or use fallback
  useEffect(() => {
    fetchLessonsApi().then((data) => {
      if (data && data.length > 0) {
        setLessonsList(data);
      }
    });
  }, []);

  // Sync active lesson with URL slug
  useEffect(() => {
    const found = lessonsList.find((l) => l.slug === slug) || lessonsList[0];
    if (found) {
      setActiveLesson(found);
      setUserInput("");
      setEvaluationResult(null);
      setHintLevel(1);

      // Set initial greeting for the active lesson
      setTutorMessages([
        {
          role: "assistant",
          content: `👋 Hi! I'm your open-source mentor for **${found.title}** (${found.category}).\n\nI won't just hand you answers — my goal is to guide you step-by-step so you gain real confidence.\n\nWhat would you like to explore or practice in this lesson?`,
        },
      ]);
    }
  }, [slug, lessonsList]);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [tutorMessages]);

  const currentIndex = lessonsList.findIndex((l) => l.slug === activeLesson.slug);
  const prevLesson = currentIndex > 0 ? lessonsList[currentIndex - 1] : null;
  const nextLesson = currentIndex < lessonsList.length - 1 ? lessonsList[currentIndex + 1] : null;

  // Handle interactive exercise submission & Socratic evaluation
  const handleCheckAnswer = async () => {
    const input = userInput.trim();
    if (!input) {
      toast.error("Please enter a command or answer before submitting.");
      return;
    }

    setIsEvaluating(true);
    setEvaluationResult(null);

    try {
      const resp = await fetchApi<any>("/ai/tutor/evaluate/", {
        method: "POST",
        body: JSON.stringify({
          user_input: input,
          expected: activeLesson.expected,
          lesson_slug: activeLesson.slug,
        }),
      });

      setEvaluationResult(resp);

      if (resp.is_correct) {
        toast.success("🎉 Correct! Lesson concept mastered.");
        const nextSet = new Set(completedSlugs);
        nextSet.add(activeLesson.slug);
        setCompletedSlugs(nextSet);
        localStorage.setItem("completed_lesson_slugs", JSON.stringify(Array.from(nextSet)));

        // Reward XP in backend if authenticated
        fetchApi("/progress/xp/add/", {
          method: "POST",
          body: JSON.stringify({ points: 20, source_type: "lesson" }),
        }).catch(() => {});
      } else {
        toast.error("Not quite! Let's check the mentor hint.");
      }
    } catch {
      // Fallback local evaluation
      const isCorrect = input.toLowerCase() === activeLesson.expected.toLowerCase();
      setEvaluationResult({
        is_correct: isCorrect,
        feedback: isCorrect
          ? "🎯 Perfect! You entered the exact expected command."
          : `You entered \`${input}\`. Review the lesson objectives and try again!`,
        hint: isCorrect ? "" : activeLesson.hint,
      });

      if (isCorrect) {
        toast.success("🎉 Correct! Lesson concept mastered.");
        const nextSet = new Set(completedSlugs);
        nextSet.add(activeLesson.slug);
        setCompletedSlugs(nextSet);
        localStorage.setItem("completed_lesson_slugs", JSON.stringify(Array.from(nextSet)));
      }
    } finally {
      setIsEvaluating(false);
    }
  };

  // Handle asking questions to the AI Tutor
  const handleSendTutorMessage = async (textToSend?: string) => {
    const q = (textToSend || tutorInput).trim();
    if (!q || isStreaming) return;

    const historyPairs: { question: string; answer: string }[] = [];
    for (let i = 0; i < tutorMessages.length - 1; i++) {
      if (tutorMessages[i].role === "user" && tutorMessages[i + 1]?.role === "assistant") {
        historyPairs.push({
          question: tutorMessages[i].content,
          answer: tutorMessages[i + 1].content,
        });
      }
    }

    setTutorMessages((prev) => [
      ...prev,
      { role: "user", content: q },
      { role: "assistant", content: "" },
    ]);
    setTutorInput("");
    setIsStreaming(true);

    try {
      await fetchStreamApi("/ai/tutor/ask/", {
        method: "POST",
        body: JSON.stringify({
          question: q,
          lesson_slug: activeLesson.slug,
          history: historyPairs,
          expected_command: activeLesson.expected,
          action: "ask",
        }),
        onChunk: (chunkText) => {
          setTutorMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last && last.role === "assistant") {
              next[next.length - 1] = {
                ...last,
                content: last.content + chunkText,
              };
            }
            return next;
          });
        },
      });
    } catch {
      setTutorMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last && last.role === "assistant" && !last.content) {
          next[next.length - 1] = {
            ...last,
            content: `In **${activeLesson.title}**, remember: ${activeLesson.hint}\n\nTry running the practical exercise on the left!`,
          };
        }
        return next;
      });
    } finally {
      setIsStreaming(false);
    }
  };

  // Request progressive hint from the AI Tutor
  const handleRequestHint = async () => {
    const currentLvl = hintLevel;
    try {
      const resp = await fetchApi<any>("/ai/tutor/ask/", {
        method: "POST",
        body: JSON.stringify({
          action: "hint",
          hint_level: currentLvl,
          expected_command: activeLesson.expected,
          lesson_slug: activeLesson.slug,
        }),
      });

      if (resp?.hint) {
        setTutorMessages((prev) => [
          ...prev,
          { role: "assistant", content: resp.hint },
        ]);
        setHintLevel((lvl) => (lvl < 3 ? lvl + 1 : 1));
      }
    } catch {
      setTutorMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `💡 **Hint ${currentLvl}**: ${activeLesson.hint}`,
        },
      ]);
      setHintLevel((lvl) => (lvl < 3 ? lvl + 1 : 1));
    }
  };

  return (
    <div className="min-h-screen bg-[#FDFBF7] dark:bg-[#0E0D0B] text-slate-900 dark:text-[#F0EBE2] flex flex-col font-sans">
      {/* Top Breadcrumb & Progress Header */}
      <header className="border-b-2 border-black/10 dark:border-[#2E2924] bg-white dark:bg-[#151411] px-4 sm:px-6 py-3 sticky top-0 z-30 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            to="/dashboard"
            className="flex items-center gap-1.5 text-xs font-bold text-slate-600 dark:text-slate-400 hover:text-black dark:hover:text-white transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
            Dashboard
          </Link>
          <span className="text-slate-300 dark:text-slate-700">/</span>
          <span className="text-xs font-black uppercase tracking-wider text-amber-600 dark:text-amber-400">
            {activeLesson.category}
          </span>
          <span className="text-slate-300 dark:text-slate-700">/</span>
          <span className="text-xs font-bold truncate max-w-[200px] sm:max-w-none">
            {activeLesson.title}
          </span>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-2 text-xs font-mono bg-slate-100 dark:bg-[#1E1C18] px-3 py-1.5 rounded-full border border-black/10 dark:border-[#2E2924]">
            <Clock className="w-3.5 h-3.5 text-amber-500" />
            <span>{activeLesson.estimatedMinutes} mins</span>
          </div>
          <div className="flex items-center gap-1.5 text-xs font-bold bg-amber-100 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 px-3 py-1.5 rounded-full border border-amber-300 dark:border-amber-800/60">
            <Zap className="w-3.5 h-3.5 fill-amber-500 text-amber-500" />
            <span>{completedSlugs.size} / {lessonsList.length} Completed</span>
          </div>
        </div>
      </header>

      {/* 3-Column Learning Interface */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-0">
        {/* LEFT COLUMN: 7-Level Syllabus Navigation (3 cols) */}
        <aside className="lg:col-span-3 border-r-2 border-black/10 dark:border-[#2E2924] bg-white/70 dark:bg-[#12110E] p-4 overflow-y-auto max-h-[calc(100vh-53px)] hidden md:block">
          <div className="mb-4">
            <h2 className="text-xs font-black uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1">
              Curriculum Roadmap
            </h2>
            <p className="text-[13px] font-bold text-slate-800 dark:text-slate-200">
              7 Levels of Open Source Mastery
            </p>
          </div>

          <div className="space-y-6">
            {SEVEN_LEVELS.map((lvl) => {
              const levelLessons = lessonsList.filter(
                (l) => l.category.toLowerCase().includes(lvl.id) || l.category.toLowerCase().includes(lvl.title.toLowerCase().split("—")[0].trim().toLowerCase())
              );
              const isCurrentLevel = activeLesson.category.toLowerCase().includes(lvl.id);

              return (
                <div key={lvl.id} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-black uppercase tracking-wide text-slate-700 dark:text-slate-300">
                      {lvl.badge}
                    </span>
                    <span className="text-[10px] font-mono text-slate-400">
                      {levelLessons.filter((l) => completedSlugs.has(l.slug)).length}/{levelLessons.length}
                    </span>
                  </div>
                  <div className="space-y-1">
                    {levelLessons.map((l) => {
                      const isCompleted = completedSlugs.has(l.slug);
                      const isActive = l.slug === activeLesson.slug;

                      return (
                        <button
                          key={l.slug}
                          onClick={() => navigate(`/learn/${l.slug}`)}
                          className={`w-full text-left px-3 py-2 rounded-xl text-xs font-medium transition-all flex items-center justify-between ${
                            isActive
                              ? "bg-amber-400 text-black font-bold shadow-sm border border-black/20"
                              : "hover:bg-black/5 dark:hover:bg-white/5 text-slate-700 dark:text-slate-300"
                          }`}
                        >
                          <div className="flex items-center gap-2 truncate">
                            {isCompleted ? (
                              <CheckCircle2 className={`w-3.5 h-3.5 flex-shrink-0 ${isActive ? "text-black" : "text-emerald-500"}`} />
                            ) : (
                              <div className={`w-2 h-2 rounded-full flex-shrink-0 ${isActive ? "bg-black" : "bg-slate-300 dark:bg-slate-700"}`} />
                            )}
                            <span className="truncate">{l.title}</span>
                          </div>
                          <span className="text-[10px] opacity-70 font-mono flex-shrink-0 ml-1">
                            {l.estimatedMinutes}m
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </aside>

        {/* CENTER COLUMN: Main Lesson Workspace (5 cols on lg, full on mobile) */}
        <main className="lg:col-span-5 p-4 sm:p-8 overflow-y-auto max-h-[calc(100vh-53px)] space-y-6">
          {/* Lesson Header Card */}
          <div className="bg-white dark:bg-[#151411] border-2 border-black/10 dark:border-[#2E2924] rounded-2xl p-6 shadow-sm">
            <div className="flex items-center gap-2 mb-3">
              <span className="bg-amber-300 dark:bg-amber-500/20 text-amber-900 dark:text-amber-300 border border-amber-400/40 text-[11px] font-black uppercase px-2.5 py-1 rounded-md">
                {activeLesson.difficulty}
              </span>
              <span className="text-xs font-mono text-slate-500">
                {activeLesson.category}
              </span>
            </div>

            <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-slate-950 dark:text-white mb-3">
              {activeLesson.title}
            </h1>
            <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
              {activeLesson.description}
            </p>

            {/* Learning Objectives */}
            {activeLesson.learningObjectives?.length > 0 && (
              <div className="mt-5 pt-4 border-t border-black/10 dark:border-[#2E2924]">
                <h3 className="text-xs font-black uppercase tracking-wider text-slate-500 mb-2 flex items-center gap-1.5">
                  <Target className="w-3.5 h-3.5 text-amber-500" />
                  Learning Objectives
                </h3>
                <ul className="space-y-1.5">
                  {activeLesson.learningObjectives.map((obj, i) => (
                    <li key={i} className="text-xs text-slate-700 dark:text-slate-300 flex items-start gap-2">
                      <span className="text-amber-500 font-bold">•</span>
                      <span>{obj}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Lesson Markdown Content */}
          <article className="bg-white dark:bg-[#151411] border-2 border-black/10 dark:border-[#2E2924] rounded-2xl p-6 shadow-sm prose dark:prose-invert max-w-none text-sm leading-relaxed">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                h3({ children }) {
                  return <h3 className="text-base font-black text-slate-900 dark:text-white mt-4 mb-2">{children}</h3>;
                },
                code({ children }) {
                  return (
                    <code className="bg-slate-100 dark:bg-[#1E1C18] text-amber-600 dark:text-amber-400 px-1.5 py-0.5 rounded font-mono text-xs border border-black/10 dark:border-[#2E2924]">
                      {children}
                    </code>
                  );
                },
                pre({ children }) {
                  return (
                    <pre className="bg-[#12110E] text-[#F0EBE2] p-4 rounded-xl font-mono text-xs overflow-x-auto border border-[#2E2924] my-3">
                      {children}
                    </pre>
                  );
                },
                blockquote({ children }) {
                  return (
                    <blockquote className="border-l-4 border-amber-400 bg-amber-50/50 dark:bg-amber-950/20 p-3 rounded-r-xl my-3 text-xs italic">
                      {children}
                    </blockquote>
                  );
                },
              }}
            >
              {activeLesson.explanation}
            </ReactMarkdown>
          </article>

          {/* Interactive Practical Task & Socratic Evaluation */}
          <div className="bg-white dark:bg-[#151411] border-2 border-black dark:border-[#2E2924] rounded-2xl p-6 shadow-card-sm space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Terminal className="w-5 h-5 text-amber-500" />
                <h3 className="font-black text-sm uppercase tracking-wide">
                  Interactive Practice Task
                </h3>
              </div>
              <span className="text-[11px] font-mono bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 px-2 py-0.5 rounded-full border border-emerald-300">
                +20 XP
              </span>
            </div>

            <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed font-medium">
              {activeLesson.exercises?.[0]?.prompt || `Run the command or provide the concept for: ${activeLesson.title}`}
            </p>

            {/* Input & Execution Bar */}
            <div className="space-y-3">
              <div className="relative flex items-center">
                <input
                  type="text"
                  value={userInput}
                  onChange={(e) => setUserInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleCheckAnswer();
                  }}
                  placeholder="Type your command or answer here..."
                  className="w-full pl-4 pr-24 py-2.5 text-xs font-mono bg-slate-50 dark:bg-[#0F0E0C] border-2 border-black/20 dark:border-[#2E2924] rounded-xl focus:outline-none focus:border-amber-500 dark:focus:border-amber-400"
                  disabled={isEvaluating}
                />
                <button
                  onClick={handleCheckAnswer}
                  disabled={!userInput.trim() || isEvaluating}
                  className="absolute right-1.5 px-3 py-1.5 bg-amber-400 hover:bg-amber-300 text-black font-black text-xs rounded-lg border border-black/30 transition-all flex items-center gap-1.5 disabled:opacity-50"
                >
                  {isEvaluating ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Play className="w-3 h-3 fill-black" />
                  )}
                  <span>Check</span>
                </button>
              </div>

              {/* Evaluation Result & Socratic Mistake Feedback */}
              {evaluationResult && (
                <div
                  className={`p-4 rounded-xl border-2 text-xs leading-relaxed space-y-2 animate-in fade-in duration-200 ${
                    evaluationResult.is_correct
                      ? "bg-emerald-50 dark:bg-emerald-950/30 border-emerald-500 text-emerald-900 dark:text-emerald-200"
                      : "bg-rose-50 dark:bg-rose-950/30 border-rose-400 text-rose-900 dark:text-rose-200"
                  }`}
                >
                  <p className="font-bold">{evaluationResult.feedback}</p>
                  {evaluationResult.mistake_detected && (
                    <p className="text-[11px] font-mono text-rose-600 dark:text-rose-400">
                      ⚠️ Identified Mistake: {evaluationResult.mistake_detected}
                    </p>
                  )}
                  {evaluationResult.hint && (
                    <p className="text-[11px] italic bg-white/60 dark:bg-black/40 p-2 rounded-lg border border-black/10">
                      💡 Mentor Hint: {evaluationResult.hint}
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* Quick action buttons */}
            <div className="flex items-center justify-between pt-2">
              <button
                onClick={handleRequestHint}
                className="text-xs font-bold text-amber-600 dark:text-amber-400 hover:underline flex items-center gap-1"
              >
                <Lightbulb className="w-3.5 h-3.5" />
                <span>Ask Tutor for Hint {hintLevel}</span>
              </button>

              <button
                onClick={() => handleSendTutorMessage(`Can you explain why the correct approach for this task is "${activeLesson.expected}"?`)}
                className="text-xs font-bold text-slate-500 hover:text-black dark:hover:text-white flex items-center gap-1"
              >
                <HelpCircle className="w-3.5 h-3.5" />
                <span>Why does this work?</span>
              </button>
            </div>
          </div>

          {/* Navigation Controls: Previous / Next Lesson */}
          <div className="flex items-center justify-between pt-4 border-t border-black/10 dark:border-[#2E2924]">
            {prevLesson ? (
              <button
                onClick={() => navigate(`/learn/${prevLesson.slug}`)}
                className="px-4 py-2 bg-slate-100 dark:bg-[#1E1C18] border border-black/20 dark:border-[#2E2924] rounded-xl text-xs font-bold hover:bg-slate-200 transition-colors flex items-center gap-1.5"
              >
                <ChevronLeft className="w-4 h-4" />
                <span>{prevLesson.title}</span>
              </button>
            ) : <div />}

            {nextLesson && (
              <button
                onClick={() => navigate(`/learn/${nextLesson.slug}`)}
                className="px-5 py-2.5 bg-amber-400 hover:bg-amber-300 text-black border-2 border-black font-black text-xs rounded-xl shadow-card-sm transition-all flex items-center gap-1.5"
              >
                <span>Next: {nextLesson.title}</span>
                <ChevronRight className="w-4 h-4" />
              </button>
            )}
          </div>
        </main>

        {/* RIGHT COLUMN: Context-Aware Socratic AI Tutor (4 cols) */}
        <aside className="lg:col-span-4 border-l-2 border-black/10 dark:border-[#2E2924] bg-white dark:bg-[#151411] flex flex-col h-[calc(100vh-53px)] sticky top-[53px]">
          {/* Tutor Header */}
          <div className="p-4 border-b-2 border-black/10 dark:border-[#2E2924] flex items-center justify-between bg-amber-50/50 dark:bg-[#1A1815]">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-amber-400 text-black flex items-center justify-center font-black text-xs border border-black/20">
                <Bot className="w-4 h-4" />
              </div>
              <div>
                <h3 className="font-black text-xs uppercase tracking-wider text-slate-900 dark:text-white flex items-center gap-1.5">
                  <span>AI Mentor</span>
                  <Sparkles className="w-3.5 h-3.5 text-amber-500" />
                </h3>
                <p className="text-[10px] font-mono text-slate-500">
                  Grounded in: {activeLesson.title}
                </p>
              </div>
            </div>

            <button
              onClick={() => {
                setTutorMessages([
                  {
                    role: "assistant",
                    content: `Restarted session for **${activeLesson.title}**. What concept would you like to explore?`,
                  },
                ]);
              }}
              title="Reset conversation"
              className="p-1.5 hover:bg-black/5 dark:hover:bg-white/5 rounded-lg text-slate-400 hover:text-slate-600 transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Tutor Conversation Feed */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3.5">
            {tutorMessages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[90%] rounded-2xl px-3.5 py-2.5 text-xs leading-relaxed ${
                    msg.role === "user"
                      ? "bg-amber-400 text-black font-medium border border-black/20"
                      : "bg-slate-100 dark:bg-[#1E1C18] border border-black/10 dark:border-[#2E2924] text-slate-800 dark:text-[#E8E2D8]"
                  }`}
                >
                  {msg.role === "user" ? (
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  ) : (
                    <div className="prose dark:prose-invert max-w-none text-xs leading-relaxed">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          p({ children }) {
                            return <p className="mb-1.5 last:mb-0">{children}</p>;
                          },
                          code({ children }) {
                            return (
                              <code className="bg-black/10 dark:bg-white/10 px-1 py-0.5 rounded font-mono text-[11px]">
                                {children}
                              </code>
                            );
                          },
                        }}
                      >
                        {msg.content}
                      </ReactMarkdown>
                    </div>
                  )}
                </div>
              </div>
            ))}

            {isStreaming && (
              <div className="flex justify-start">
                <div className="bg-slate-100 dark:bg-[#1E1C18] border border-black/10 dark:border-[#2E2924] rounded-2xl px-3.5 py-2 flex items-center gap-2">
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-amber-500" />
                  <span className="text-xs text-slate-500 font-mono">
                    Formulating Socratic guidance...
                  </span>
                </div>
              </div>
            )}
            <div ref={chatBottomRef} />
          </div>

          {/* Socratic Starter Prompt Chips */}
          <div className="px-4 py-2 border-t border-black/10 dark:border-[#2E2924] bg-slate-50 dark:bg-[#12110E]">
            <p className="text-[10px] font-mono uppercase tracking-wider text-slate-400 mb-1.5">
              Quick Inquiries:
            </p>
            <div className="flex flex-wrap gap-1.5">
              <button
                onClick={() => handleSendTutorMessage("Can you give me an analogy for this concept?")}
                className="text-[11px] bg-white dark:bg-[#1A1815] border border-black/15 dark:border-[#2E2924] hover:border-amber-400 px-2 py-1 rounded-lg transition-colors"
              >
                🎨 Analogy
              </button>
              <button
                onClick={() => handleSendTutorMessage("What is a common mistake beginners make here?")}
                className="text-[11px] bg-white dark:bg-[#1A1815] border border-black/15 dark:border-[#2E2924] hover:border-amber-400 px-2 py-1 rounded-lg transition-colors"
              >
                ⚠️ Common Pitfalls
              </button>
              <button
                onClick={handleRequestHint}
                className="text-[11px] bg-amber-100 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 border border-amber-300 px-2 py-1 rounded-lg font-bold transition-colors"
              >
                💡 Hint {hintLevel}
              </button>
            </div>
          </div>

          {/* Tutor Input Bar */}
          <div className="p-3 border-t-2 border-black/10 dark:border-[#2E2924] bg-white dark:bg-[#151411]">
            <div className="flex gap-2">
              <input
                type="text"
                value={tutorInput}
                onChange={(e) => setTutorInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSendTutorMessage();
                  }
                }}
                placeholder="Ask the mentor a question..."
                className="flex-1 px-3 py-2 text-xs border border-black/20 dark:border-[#2E2924] rounded-xl bg-slate-50 dark:bg-[#0F0E0C] focus:outline-none focus:border-amber-500"
                disabled={isStreaming}
              />
              <button
                onClick={() => handleSendTutorMessage()}
                disabled={!tutorInput.trim() || isStreaming}
                className="p-2 bg-amber-400 text-black font-bold rounded-xl hover:bg-amber-300 disabled:opacity-50 transition-colors border border-black/20"
                aria-label="Send message"
              >
                <Send className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
