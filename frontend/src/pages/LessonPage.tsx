import React, { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams, Link } from "react-router-dom";
import {
  ChevronLeft,
  ChevronRight,
  Menu,
  X,
  BookOpen,
  CheckCircle2,
  Lock,
  Bookmark,
} from "lucide-react";

import SkeletonLesson from "../components/ui/skeletons/SkeletonLesson";
import { useUserProgress } from "../hooks/useUserProgress";
import { useBookmarks } from "../hooks/useBookmarks";
import { fetchApi } from "../lib/api";
import { Lesson, fetchLessonsApi, fetchLessonContent } from "../lib/lessons";
import { RichTextEditor } from "../components/ui/RichTextEditor";

const MarkdownRenderer = React.lazy(() =>
  import("../components/ui/MarkdownRenderer").then((module) => ({
    default: module.MarkdownRenderer,
  })),
);
import { GitGraph } from "../components/ui/GitGraph";
import { NotePanel } from "../components/ui/NotePanel";
import { PythonSandbox } from "../components/ui/PythonSandbox";
import { CollabPythonSandbox } from "../components/ui/CollabPythonSandbox";
import { JSSandbox } from "../components/ui/JSSandbox";
import { InteractiveDebugger } from "../components/ui/InteractiveDebugger";
import { TextToSpeechControls } from "../components/ui/TextToSpeechControls";

import {
  createInitialRepo,
  parseGitCommand,
  RepoState,
} from "../lib/gitSimulator";

function normalizeCommand(value: string) {
  return value.trim().replace(/\s+/g, " ").toLowerCase();
}

export function LessonPage() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const { isLessonCompleted, syncProgress } = useUserProgress();
  const { isBookmarked, toggleBookmark } = useBookmarks();
  const queryClient = useQueryClient();

  const [lesson, setLesson] = useState<Lesson | undefined>(undefined);
  const [lessonsList, setLessonsList] = useState<Lesson[]>([]);
  const [markdownContent, setMarkdownContent] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  // Curriculum modules list for sidebar
  const [modules, setModules] = useState<
    {
      id: string;
      title: string;
      lessons: { slug: string; title: string; difficulty?: string }[];
    }[]
  >([]);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const sidebarRef = useRef<HTMLElement>(null);

  const closeSidebar = useCallback(() => setIsSidebarOpen(false), []);

  // Close sidebar on click-outside (mobile drawer)
  useEffect(() => {
    if (!isSidebarOpen) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (
        sidebarRef.current &&
        !sidebarRef.current.contains(e.target as Node)
      ) {
        closeSidebar();
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isSidebarOpen, closeSidebar]);

  // Command-based exercises
  const [isExecuting, setIsExecuting] = useState(false);
  const [input, setInput] = useState("");
  const [feedback, setFeedback] = useState<string>("");
  const [showHint, setShowHint] = useState(false);
  const [terminalOutput, setTerminalOutput] = useState("");
  const [repoState, setRepoState] = useState<RepoState>(createInitialRepo());

  // Quiz-based exercises
  const [currentQuizIndex, setCurrentQuizIndex] = useState(0);
  const [selectedOption, setSelectedOption] = useState<number | null>(null);
  const [quizFeedback, setQuizFeedback] = useState<
    "correct" | "incorrect" | null
  >(null);

  // Help Request panel
  const [isHelpPanelOpen, setIsHelpPanelOpen] = useState(false);
  const [helpMessage, setHelpMessage] = useState("");
  const [helpSuccessMessage, setHelpSuccessMessage] = useState("");
  const MAX_HELP_CHARS = 500;

  // Note Panel
  const [isNotePanelOpen, setIsNotePanelOpen] = useState(false);

  // Reading progress scroll ref
  const mainContentRef = useRef<HTMLDivElement>(null);
  const [scrollProgress, setScrollProgress] = useState(0);

  const helpRequestMutation = useMutation({
    mutationFn: (message: string) => {
      if (!lesson) {
        throw new Error("No lesson context available");
      }
      return fetchApi("/progress/help-requests/", {
        method: "POST",
        body: JSON.stringify({
          lesson_slug: lesson.slug,
          message,
        }),
      });
    },
    onSuccess: () => {
      setHelpSuccessMessage("Help request sent. A mentor will review it soon.");
      setHelpMessage("");
      queryClient.invalidateQueries({ queryKey: ["communityStats"] });
    },
  });

  // 1. Fetch modules catalog & lessons
  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    setIsLoading(true);
    fetch("/content/curriculum.json")
      .then((res) => res.json())
      .then((data) => {
        if (data && data.modules) {
          setModules(data.modules);
        }
      })
      .catch((err) => console.error("Error fetching curriculum catalog:", err));

    fetchLessonsApi()
      .then((data) => {
        setLessonsList(data);
        const found = data.find((l) => l.slug === slug);
        if (!found) {
          navigate("/dashboard", { replace: true });
          return;
        }
        setLesson(found);
      })
      .catch(() => {
        navigate("/dashboard", { replace: true });
      })
      .finally(() => {
        setIsLoading(false);
      });
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [slug, navigate]);

  // 2. Fetch markdown content and reset interactive state when lesson changes
  useEffect(() => {
    if (!lesson) return;

    /* eslint-disable react-hooks/set-state-in-effect */
    setFeedback("");
    setInput("");
    setShowHint(false);
    setTerminalOutput("");
    setRepoState(createInitialRepo());
    /* eslint-enable react-hooks/set-state-in-effect */

    // Reset Quiz state
    setCurrentQuizIndex(0);
    setSelectedOption(null);
    setQuizFeedback(null);

    if (lesson.filePath) {
      fetchLessonContent(lesson.filePath).then((content) => {
        setMarkdownContent(content);
      });
    } else {
      setMarkdownContent(`# ${lesson.title}\n\n${lesson.explanation}`);
    }
  }, [lesson]);

  // 3. Scroll tracking for reading progress
  useEffect(() => {
    const handleScroll = () => {
      if (!mainContentRef.current) return;
      const element = mainContentRef.current;
      const totalHeight = element.scrollHeight - element.clientHeight;
      if (totalHeight <= 0) {
        setScrollProgress(100);
        return;
      }
      const scrollPercent = (element.scrollTop / totalHeight) * 100;
      setScrollProgress(Math.min(100, Math.max(0, Math.round(scrollPercent))));
    };

    const container = mainContentRef.current;
    if (container) {
      container.addEventListener("scroll", handleScroll);
    }
    return () => {
      if (container) {
        container.removeEventListener("scroll", handleScroll);
      }
    };
  }, [markdownContent]);

  // Command submission handler
  const handleCommandSubmit = async (
    e: React.FormEvent | React.KeyboardEvent,
  ) => {
    e.preventDefault();
    if (!lesson || isExecuting) return;

    setIsExecuting(true);
    await new Promise((resolve) => setTimeout(resolve, 800));

    const result = parseGitCommand(input, repoState);
    if (result.error) {
      setTerminalOutput(result.error);
      setFeedback("error");
      setShowHint(true);
      return; // Stop processing further for invalid commands
    } else {
      setTerminalOutput(result.output || "");
      setRepoState(result.newState);
    }

    const expected = lesson.expected;
    let isCorrect;

    if (typeof expected === "string") {
      isCorrect = normalizeCommand(input) === normalizeCommand(expected);
    } else {
      try {
        isCorrect = expected.test(input.trim());
      } catch {
        isCorrect = input.trim() === String(expected);
      }
    }

    if (isCorrect) {
      setFeedback("correct");
      syncProgress({
        lesson_slug: lesson.slug,
        score: lesson.points || 20,
        completed: true,
      });
    } else {
      setFeedback("error");
      setShowHint(true);
    }

    setInput(""); // Clear input after running
    setIsExecuting(false);
  };

  // Quiz submission handler
  const handleQuizOptionCheck = () => {
    if (selectedOption === null || !lesson || !lesson.quizzes) return;
    const currentQuiz = lesson.quizzes[currentQuizIndex];

    if (selectedOption === currentQuiz.answer) {
      setQuizFeedback("correct");
      if (currentQuizIndex === lesson.quizzes.length - 1) {
        setFeedback("correct");
        syncProgress({
          lesson_slug: lesson.slug,
          score: lesson.points || 15,
          completed: true,
        });
      }
    } else {
      setQuizFeedback("incorrect");
    }
  };

  const handleNextQuizQuestion = () => {
    setSelectedOption(null);
    setQuizFeedback(null);
    setCurrentQuizIndex((prev) => prev + 1);
  };

  const handleHelpRequestSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!lesson || !helpMessage.trim()) return;
    helpRequestMutation.mutate(helpMessage.trim());
  };

  if (isLoading) {
    return (
      <div
        className="pt-20 h-screen w-full flex items-center justify-center"
        aria-busy="true"
        role="status"
      >
        <div className="w-full max-w-3xl">
          <SkeletonLesson />
        </div>
      </div>
    );
  }

  if (!lesson) return null;

  const currentLessonIndex = lessonsList.findIndex(
    (l) => l.slug === lesson.slug,
  );
  const previousLesson = lessonsList[currentLessonIndex - 1];
  const nextLesson = lessonsList[currentLessonIndex + 1];

  const hasQuiz = lesson.quizzes && lesson.quizzes.length > 0;
  const hasConflict = !!lesson.conflictScenario;
  const isCompleted = isLessonCompleted(lesson.slug);
  const activeModuleId = modules.find((mod) =>
    mod.lessons.some((les) => les.slug === lesson.slug),
  )?.id;

  return (
    <div className="min-h-screen pt-20 flex flex-col lg:flex-row relative">
      {/* 1. Mobile Sidebar Toggle */}
      <div className="lg:hidden bg-white border-b-4 border-black dark:bg-[#151411] dark:border-[#2e2924] p-4 flex items-center justify-between z-[80]">
        <button
          onClick={() => setIsSidebarOpen((prev) => !prev)}
          aria-expanded={isSidebarOpen}
          aria-controls="course-sidebar"
          className="flex items-center gap-2 font-black text-sm uppercase px-3 py-2 bg-surface-low border-2 border-black rounded-lg text-black"
        >
          {isSidebarOpen ? <X size={16} /> : <Menu size={16} />}
          {isSidebarOpen ? "Close Outline" : "Course Directory"}
        </button>
        <span className="font-mono text-xs font-black bg-black text-white px-3 py-1 rounded-full dark:bg-[#2e2924]">
          XP Bounties: {lesson.points || 15}
        </span>
      </div>

      {/* Backdrop overlay — closes drawer on click-outside on mobile */}
      {isSidebarOpen && (
        <div
          className="fixed inset-0 z-[90] bg-black/40 lg:hidden"
          aria-hidden="true"
          onClick={closeSidebar}
        />
      )}

      {/* 2. Side Course Directory Menu */}
      <aside
        id="course-sidebar"
        ref={sidebarRef}
        className={`fixed top-0 left-0 h-full w-[300px] border-r-4 border-black bg-white dark:bg-[#151411] dark:border-[#2e2924] overflow-y-auto p-6 transition-transform duration-300 ease-in-out z-[100] pt-20
          ${isSidebarOpen ? "translate-x-0" : "-translate-x-full"}
          lg:relative lg:top-auto lg:left-auto lg:h-auto lg:w-[320px] lg:flex-shrink-0 lg:translate-x-0 lg:block lg:max-h-[calc(100vh-80px)]`}
      >
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-black uppercase flex items-center gap-2">
            <BookOpen size={18} className="text-primary" />
            Curriculum
          </h2>
          {isSidebarOpen && (
            <button
              onClick={closeSidebar}
              aria-label="Close course outline"
              className="lg:hidden border-2 border-black p-1 rounded-lg"
            >
              <X size={16} />
            </button>
          )}
        </div>

        <div className="space-y-6">
          {modules.map((mod, modIdx) => (
            <div key={mod.id} className="space-y-2">
              <h3
                className={`font-mono text-[10px] uppercase tracking-wider font-bold px-2 py-1.5 rounded-lg border-2 transition-all
                         ${
                           mod.id === activeModuleId
                             ? "bg-yellow-300 text-black border-black shadow-[2px_2px_0px_#000]"
                             : "text-muted dark:text-[#c4bbae] border-transparent"
                         }`}
              >
                Module {modIdx + 1}: {mod.title}
              </h3>
              <div className="space-y-1">
                {mod.lessons.map(
                  (les: {
                    slug: string;
                    title: string;
                    difficulty?: string;
                  }) => {
                    const active = les.slug === lesson.slug;
                    const completed = isLessonCompleted(les.slug);
                    return (
                      <Link
                        key={les.slug}
                        to={`/lessons/${les.slug}`}
                        onClick={closeSidebar}
                        className={`w-full flex items-center justify-between p-2.5 rounded-lg border-2 transition-all text-xs font-bold ${
                          active
                            ? "bg-surface-low border-black shadow-card-sm text-text"
                            : "border-transparent hover:bg-surface-lowest hover:border-black/10 dark:text-[#c4bbae]"
                        }`}
                      >
                        <div className="flex items-center gap-2 truncate">
                          {completed ? (
                            <CheckCircle2
                              size={14}
                              className="text-green-600 flex-shrink-0"
                            />
                          ) : (
                            <div className="w-3.5 h-3.5 rounded-full border-2 border-black/35 flex-shrink-0" />
                          )}
                          <span className="truncate">{les.title}</span>
                        </div>
                        {les.difficulty === "advanced" && (
                          <span className="text-[8px] bg-red-100 text-red-700 px-1 py-0.5 rounded border border-red-700">
                            ADV
                          </span>
                        )}
                      </Link>
                    );
                  },
                )}
              </div>
            </div>
          ))}
        </div>
      </aside>

      {/* 3. Main Reading Panel */}
      <div className="flex-1 flex flex-col max-h-[calc(100vh-80px)] overflow-hidden">
        {/* Top scroll reading progress indicator */}
        <div className="h-2 w-full bg-surface-low border-b-2 border-black dark:bg-[#151411] dark:border-[#2e2924] relative flex-shrink-0">
          <div
            className="h-full bg-primary transition-all duration-150"
            style={{ width: `${scrollProgress}%` }}
          />
        </div>

        <div
          ref={mainContentRef}
          className="flex-1 overflow-y-auto p-6 sm:p-10 space-y-8"
        >
          <div className="max-w-3xl mx-auto space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <span className="text-[10px] font-mono font-black bg-accent text-black px-3 py-1 rounded-full border-2 border-black rotate-[-1deg] inline-block shadow-card-sm uppercase">
                  {lesson.difficulty || "beginner"}
                </span>
                <h1 className="text-4xl sm:text-5xl font-black text-text dark:text-[#f0ebe2] drop-shadow-[2.5px_2.5px_0_#FF3B30] mt-3">
                  {lesson.title}
                </h1>
              </div>
              {isCompleted && (
                <div className="self-start sm:self-center bg-green-100 text-green-700 px-4 py-1.5 rounded-2xl text-xs font-black border-4 border-black shadow-card-sm">
                  COMPLETED ✅
                </div>
              )}
              <button
                onClick={() =>
                  toggleBookmark.mutate({
                    slug: lesson.slug,
                    isBookmarked: isBookmarked(lesson.slug),
                  })
                }
                disabled={toggleBookmark.isPending}
                className="self-start sm:self-center ml-auto flex items-center justify-center p-2 rounded-xl border-4 border-black bg-surface-low hover:-translate-y-1 hover:shadow-card-sm transition-all"
                title={
                  isBookmarked(lesson.slug)
                    ? "Remove from Read Later"
                    : "Save for later"
                }
              >
                <Bookmark
                  className={
                    isBookmarked(lesson.slug)
                      ? "fill-primary text-primary"
                      : "text-black dark:text-[#f0ebe2]"
                  }
                  size={24}
                />
              </button>
            </div>

            <p className="text-xl font-bold text-muted dark:text-[#c4bbae]">
              {lesson.description}
            </p>

            <hr className="border-2 border-black/10 dark:border-[#2e2924]/40" />

            <TextToSpeechControls content={markdownContent} />

            {/* Markdown rendering logic */}
            <article className="prose max-w-none">
              <React.Suspense
                fallback={
                  <div className="w-full h-64 animate-pulse rounded-2xl border-4 border-black/20 bg-surface-low dark:border-[#2e2924]/50 dark:bg-[#151411]" />
                }
              >
                <MarkdownRenderer content={markdownContent} />
              </React.Suspense>
            </article>

            {/* Exercises & validation section */}
            <div className="pt-8 space-y-6">
              {lesson.pythonExercise ? (
                <div className="mt-8">
                  {new URLSearchParams(window.location.search).get("session") ? (
                    <CollabPythonSandbox
                      exercise={lesson.pythonExercise}
                      roomId={new URLSearchParams(window.location.search).get("session")!}
                      onSuccess={() => {
                        syncProgress({
                          lesson_slug: lesson.slug,
                          score: lesson.points || 20,
                          completed: true,
                        });
                      }}
                    />
                  ) : (
                    <PythonSandbox
                      exercise={lesson.pythonExercise}
                      onSuccess={() => {
                        syncProgress({
                          lesson_slug: lesson.slug,
                          score: lesson.points || 20,
                          completed: true,
                        });
                      }}
                    />
                  )}
                </div>
              ) : lesson.jsExercise ? (
                <div className="mt-8">
                  <JSSandbox
                    exercise={lesson.jsExercise}
                    onSuccess={() => {
                      syncProgress({
                        lesson_slug: lesson.slug,
                        score: lesson.points || 20,
                        completed: true,
                      });
                    }}
                  />
                </div>
              ) : lesson.debugExercise ? (
                <div className="mt-8">
                  <InteractiveDebugger
                    exercise={lesson.debugExercise}
                    onSuccess={() => {
                      syncProgress({
                        lesson_slug: lesson.slug,
                        score: lesson.points || 30,
                        completed: true,
                      });
                    }}
                  />
                </div>
              ) : hasQuiz ? (
                // QUIZ MODE RENDER
                <div className="rounded-2xl border-4 border-black bg-white p-6 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924]">
                  <div className="flex items-center justify-between mb-4">
                    <span className="font-mono text-xs text-primary uppercase tracking-widest font-black">
                      Knowledge Check: Question {currentQuizIndex + 1} of{" "}
                      {lesson.quizzes!.length}
                    </span>
                    <span className="text-xs font-black text-accent bg-black text-white px-2 py-0.5 rounded-full dark:bg-[#2e2924]">
                      {lesson.points || 15} XP
                    </span>
                  </div>

                  <h3 className="text-lg font-black mb-4 text-text dark:text-[#f0ebe2]">
                    {lesson.quizzes![currentQuizIndex].question}
                  </h3>

                  <div className="space-y-3">
                    {lesson.quizzes![currentQuizIndex].options.map(
                      (option, idx) => {
                        const isSelected = selectedOption === idx;
                        const currentQuiz = lesson.quizzes![currentQuizIndex];
                        const isCorrectOption = idx === currentQuiz.answer;

                        // Determine background color based on quiz state
                        let bgColor = "";
                        if (quizFeedback !== null) {
                          // After answer submitted: show green for correct, red for incorrect
                          if (isCorrectOption) {
                            bgColor =
                              "bg-green-600 border-green-800 text-white";
                          } else if (
                            isSelected &&
                            quizFeedback === "incorrect"
                          ) {
                            bgColor = "bg-red-600 border-red-800 text-white";
                          }
                        }

                        // Fallback to original styling when no feedback is present
                        if (!bgColor) {
                          bgColor = isSelected
                            ? "bg-accent shadow-card-sm -translate-y-0.5"
                            : "bg-surface hover:bg-surface-low dark:bg-[#151411]";
                        }

                        return (
                          <button
                            key={idx}
                            onClick={() => {
                              if (quizFeedback !== null) return; // Already submitted — lock selection
                              setSelectedOption(idx);
                            }}
                            disabled={quizFeedback !== null}
                            className={`w-full text-left p-4 rounded-lg border-4 border-black font-bold text-sm transition-all flex items-center justify-between ${bgColor}`}
                          >
                            <span>{option}</span>
                            <div
                              className={`w-4 h-4 rounded-full border-2 border-black flex items-center justify-center ${
                                isSelected ? "bg-black" : ""
                              }`}
                            />
                          </button>
                        );
                      },
                    )}
                  </div>

                  {quizFeedback === "correct" && (
                    <div
                      role="alert"
                      aria-live="assertive"
                      className="mt-4 p-4 bg-green-50 text-green-800 border-4 border-green-600 rounded-lg font-bold text-sm"
                    >
                      🎉 Correct!{" "}
                      {lesson.quizzes![currentQuizIndex].explanation}
                    </div>
                  )}

                  {quizFeedback === "incorrect" && (
                    <div
                      role="alert"
                      aria-live="assertive"
                      className="mt-4 p-4 bg-red-50 text-red-800 border-4 border-red-600 rounded-lg font-bold text-sm"
                    >
                      ❌ Not quite. Try reviewing the lesson text or options
                      again.
                    </div>
                  )}

                  <div className="mt-6 flex justify-end">
                    {quizFeedback === "correct" ? (
                      currentQuizIndex < lesson.quizzes!.length - 1 ? (
                        <button
                          onClick={handleNextQuizQuestion}
                          className="px-5 py-2.5 bg-accent text-black font-black text-sm rounded-lg border-4 border-black shadow-card-sm hover:-translate-y-0.5 transition-all cursor-pointer"
                        >
                          Next Question
                        </button>
                      ) : (
                        <button
                          onClick={() => {
                            syncProgress({
                              lesson_slug: lesson.slug,
                              score: lesson.points || 15,
                              completed: true,
                            });
                          }}
                          className="px-6 py-2 bg-black text-white font-bold rounded-lg border-2 border-black shadow-brutal transition-transform active:translate-y-0.5"
                        >
                          Finish Lesson
                        </button>
                      )
                    ) : (
                      <button
                        onClick={handleQuizOptionCheck}
                        disabled={selectedOption === null}
                        className="px-5 py-2.5 bg-primary text-black font-black text-sm rounded-lg border-4 border-black shadow-card-sm hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-card-sm disabled:opacity-50 transition-all cursor-pointer"
                      >
                        Submit Answer
                      </button>
                    )}
                  </div>
                </div>
              ) : hasConflict ? (
                // CONFLICT SANDBOX MODE
                <div className="mt-8">
                  {feedback === "correct" && (
                    <div
                      role="status"
                      className="mt-6 text-green-700 font-bold bg-green-50 p-4 rounded-lg border-4 border-green-600 animate-bounce"
                    >
                      ✅ Correct! You successfully resolved the merge conflict.
                    </div>
                  )}
                  {feedback === "error" && (
                    <div
                      role="alert"
                      className="mt-6 text-red-700 font-bold bg-red-50 p-4 rounded-lg border-4 border-red-600"
                    >
                      ❌ The resolved output doesn't quite match what was
                      expected. Try reviewing your selections.
                    </div>
                  )}
                </div>
              ) : (
                // TERMINAL INTERACTIVE COMMAND MODE
                <div
                  className={`rounded-2xl border-4 bg-surface-low p-6 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924]
                    ${
                      feedback === "error"
                        ? "border-red-600 shake-error"
                        : "border-black"
                    }`}
                >
                  <h3 className="text-xl font-black mb-4 flex items-center gap-2 text-text dark:text-[#f0ebe2]">
                    <span>💻</span> Sandbox terminal check
                  </h3>

                  <GitGraph state={repoState} />

                  <p className="text-xs text-muted mb-4 dark:text-[#c4bbae]">
                    Solve the drill by executing the appropriate git command
                    below:
                  </p>

                  <form onSubmit={handleCommandSubmit} className="space-y-4">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-primary font-black">
                        $
                      </span>
                      <input
                        className="flex-1 min-w-0 rounded-lg border-4 border-black bg-surface-lowest px-4 py-2.5 text-text font-bold outline-none placeholder:text-muted/40 dark:bg-[#151411] dark:border-[#2e2924]"
                        placeholder={
                          lesson.hint || "Type your git command here"
                        }
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => {
                          if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                            e.preventDefault();
                            handleCommandSubmit(
                              e as unknown as React.FormEvent,
                            );
                          }
                        }}
                        disabled={feedback === "correct" || isExecuting}
                        autoFocus
                      />
                      <button
                        type="submit"
                        className="px-5 py-2.5 bg-primary text-black font-black text-sm rounded-lg border-4 border-black shadow-card-sm hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-card-sm disabled:opacity-50 transition-all cursor-pointer flex items-center justify-center gap-2 min-w-[72px]"
                        disabled={
                          feedback === "correct" || !input.trim() || isExecuting
                        }
                      >
                        {isExecuting ? (
                          <span
                            className="flex items-center gap-1 inline-flex"
                            aria-hidden="true"
                          >
                            <span className="w-1.5 h-1.5 bg-current rounded-full animate-bounce [animation-delay:-0.3s]" />
                            <span className="w-1.5 h-1.5 bg-current rounded-full animate-bounce [animation-delay:-0.15s]" />
                            <span className="w-1.5 h-1.5 bg-current rounded-full animate-bounce" />
                          </span>
                        ) : (
                          "Run"
                        )}
                      </button>
                    </div>

                    {terminalOutput && (
                      <pre className="p-4 bg-[#151411] text-[#f0ebe2] font-mono text-xs rounded-lg border-4 border-black whitespace-pre-wrap overflow-x-auto shadow-inner">
                        {terminalOutput}
                      </pre>
                    )}

                    {feedback === "correct" && (
                      <div
                        role="status"
                        className="text-green-700 font-bold bg-green-50 p-4 rounded-lg border-4 border-green-600 animate-bounce"
                      >
                        ✅ Correct! Progress synchronized to the Atelier server.
                      </div>
                    )}

                    {feedback === "error" && (
                      <div
                        role="alert"
                        className="text-red-700 font-bold bg-red-50 p-4 rounded-lg border-4 border-red-600"
                      >
                        ❌ Not quite. Command output did not match sandbox
                        expectations.
                      </div>
                    )}

                    <button
                      type="button"
                      onClick={() => setShowHint(!showHint)}
                      className="text-xs underline text-muted font-black dark:text-[#c4bbae] block"
                    >
                      {showHint ? "Hide Hints" : "Need a hint?"}
                    </button>

                    {showHint && (
                      <div className="p-4 bg-white rounded-lg border-4 border-black italic text-xs font-bold dark:bg-[#151411] dark:border-[#2e2924] shadow-card-sm">
                        💡 {lesson.hint}
                      </div>
                    )}
                  </form>
                </div>
              )}
            </div>

            {/* Course Navigation Footer */}
            <div className="flex flex-col items-center gap-4 sm:flex-row sm:justify-between sm:gap-0 pt-10 pb-12">
              {previousLesson ? (
                <Link
                  to={`/lessons/${previousLesson.slug}`}
                  className="flex items-center gap-1 font-black text-sm uppercase px-4 py-2 bg-white border-4 border-black rounded-lg shadow-card-sm hover:-translate-y-0.5 transition-all"
                >
                  <ChevronLeft size={16} />
                  Prev: {previousLesson.title}
                </Link>
              ) : (
                <div className="hidden sm:block" />
              )}

              {nextLesson ? (
                <Link
                  to={`/lessons/${nextLesson.slug}`}
                  className={`flex items-center gap-1 font-black text-sm uppercase px-4 py-2 border-4 border-black rounded-lg shadow-card-sm hover:-translate-y-0.5 transition-all ${
                    isCompleted
                      ? "bg-accent text-black"
                      : "bg-[#e2e8f0] text-black/50 border-black/35 cursor-not-allowed opacity-75"
                  }`}
                  onClick={(e) => {
                    if (!isCompleted) {
                      e.preventDefault();
                      alert(
                        "Complete the current lesson first to unlock the next module!",
                      );
                    }
                  }}
                >
                  Next: {nextLesson.title}
                  {isCompleted ? (
                    <ChevronRight size={16} />
                  ) : (
                    <Lock size={14} className="ml-1" />
                  )}
                </Link>
              ) : (
                <Link
                  to="/dashboard"
                  className="flex items-center gap-1 font-black text-sm uppercase px-4 py-2 bg-green-500 text-white border-4 border-black rounded-lg shadow-card-sm hover:-translate-y-0.5 transition-all"
                >
                  Graduate to Dashboard 🎓
                </Link>
              )}
            </div>
          </div>
        </div>

        {/* Mentor Help Trigger Row */}
        <div className="border-t-4 border-black p-4 bg-white dark:bg-[#151411] dark:border-[#2e2924] flex justify-end gap-4 flex-shrink-0">
          <button
            onClick={() => setIsNotePanelOpen(!isNotePanelOpen)}
            className="px-4 py-2 bg-white text-text dark:bg-[#151411] dark:text-[#f0ebe2] font-black text-xs rounded-lg border-4 border-black shadow-card-sm hover:-translate-y-0.5 cursor-pointer"
          >
            {isNotePanelOpen ? "Close Notes 📝" : "Notes 📝"}
          </button>
          <button
            onClick={() => {
              setIsHelpPanelOpen(true);
              setHelpSuccessMessage("");
            }}
            className="px-4 py-2 bg-white text-text dark:bg-[#151411] dark:text-[#f0ebe2] font-black text-xs rounded-lg border-4 border-black shadow-card-sm hover:-translate-y-0.5 cursor-pointer"
          >
            Request Mentor Support 📬
          </button>
        </div>
      </div>

      {/* Note Panel */}
      {isNotePanelOpen && lesson && (
        <NotePanel
          lessonSlug={lesson.slug}
          onClose={() => setIsNotePanelOpen(false)}
        />
      )}

      {/* Help support request Panel */}
      {isHelpPanelOpen && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/40">
          <button
            type="button"
            aria-label="Close help request panel"
            className="flex-1 cursor-default"
            onClick={() => setIsHelpPanelOpen(false)}
          />
          <aside className="h-full w-full max-w-md bg-surface-lowest border-l-4 border-black p-6 shadow-card space-y-4 dark:bg-[#0f0e0c] dark:border-[#2e2924]">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-2xl font-black">
                  Need assistance on this issue?
                </h2>
                <p className="text-xs text-muted mt-1 dark:text-[#c4bbae]">
                  Submit details to core maintainers, and we&apos;ll look at
                  your local repo staging problems.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setIsHelpPanelOpen(false)}
                className="text-xs font-black underline"
              >
                Close
              </button>
            </div>

            <form className="space-y-3" onSubmit={handleHelpRequestSubmit}>
              <label
                htmlFor="help-message"
                className="block text-xs font-black"
              >
                Describe the conflict or checkout issue:
              </label>
              <RichTextEditor
                id="help-message"
                className="w-full rounded-lg border-4 border-black bg-white px-3 py-2 text-xs outline-none min-h-36 dark:bg-[#151411] dark:border-[#2e2924]"
                placeholder="Example: I'm stuck trying to stage feat/add-readme-badges, git status throws pathspec errors."
                value={helpMessage}
                onChange={setHelpMessage}
                disabled={helpRequestMutation.isPending}
                maxLength={MAX_HELP_CHARS}
              />

              {helpRequestMutation.isError && (
                <div
                  role="alert"
                  className="text-red-700 text-xs font-black bg-red-50 p-2 rounded-lg border-2 border-red-700"
                >
                  Couldn&apos;t submit request. Re-run backend server checks.
                </div>
              )}

              {helpSuccessMessage && (
                <div
                  role="status"
                  className="text-green-700 text-xs font-black bg-green-50 p-2 rounded-lg border-2 border-green-700"
                >
                  {helpSuccessMessage}
                </div>
              )}

              <button
                type="submit"
                className="w-full px-4 py-2 bg-primary text-black font-bold rounded-lg border-4 border-black shadow-card hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-card-sm transition-all disabled:opacity-60"
                disabled={!helpMessage.trim() || helpRequestMutation.isPending}
              >
                {helpRequestMutation.isPending
                  ? "Connecting..."
                  : "Submit to cohort queue"}
              </button>
            </form>
          </aside>
        </div>
      )}
    </div>
  );
}
