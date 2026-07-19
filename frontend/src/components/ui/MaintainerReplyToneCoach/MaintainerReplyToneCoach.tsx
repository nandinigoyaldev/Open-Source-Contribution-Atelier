import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Copy,
  Check,
  MessageSquareHeart,
  Sparkles,
  BookOpen,
} from "lucide-react";
import { Link } from "react-router-dom";
import {
  analyzeMaintainerReply,
  suggestReplyRewrite,
  scoreLabel,
  ETIQUETTE_EXAMPLES,
  EtiquetteExample,
  TONE_COACH_LESSON_SLUG,
  TONE_COACH_XP,
} from "../../../lib/maintainerReplyToneCoach";
import { useUserProgress } from "../../../hooks/useUserProgress";
import toast from "react-hot-toast";

export type MaintainerReplyToneCoachProps = {
  className?: string;
  /** Award XP once when the learner applies a polite rewrite */
  enableXp?: boolean;
};

export function MaintainerReplyToneCoach({
  className = "",
  enableXp = true,
}: MaintainerReplyToneCoachProps) {
  const [draft, setDraft] = useState("");
  const [examples, setExamples] =
    useState<EtiquetteExample[]>(ETIQUETTE_EXAMPLES);
  const [copied, setCopied] = useState(false);
  const [xpClaimed, setXpClaimed] = useState(false);
  const { syncProgress, isLessonCompleted } = useUserProgress();

  useEffect(() => {
    let cancelled = false;
    fetch("/content/module-4/reply-tone-examples.json")
      .then((r) => (r.ok ? r.json() : null))
      .then((data: { examples?: EtiquetteExample[] } | null) => {
        if (!cancelled && data?.examples?.length) {
          setExamples(data.examples);
        }
      })
      .catch(() => {
        /* keep built-in examples */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (isLessonCompleted(TONE_COACH_LESSON_SLUG)) {
      setXpClaimed(true);
    }
  }, [isLessonCompleted]);

  const analysis = useMemo(() => analyzeMaintainerReply(draft), [draft]);
  const suggestion = useMemo(() => suggestReplyRewrite(draft), [draft]);
  const showSuggestion =
    draft.trim().length > 0 &&
    (!analysis.ok || analysis.flags.some((f) => f.severity !== "info"));

  const applySuggestion = async () => {
    setDraft(suggestion);
    if (enableXp && !xpClaimed) {
      try {
        await syncProgress({
          lesson_slug: TONE_COACH_LESSON_SLUG,
          score: TONE_COACH_XP,
          completed: true,
        });
        setXpClaimed(true);
        toast.success(`+${TONE_COACH_XP} XP for polite reply practice`);
      } catch {
        /* progress API optional — ignore failures */
      }
    }
  };

  const copySuggestion = async () => {
    try {
      await navigator.clipboard.writeText(suggestion);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard unavailable */
    }
  };

  return (
    <div
      className={`space-y-6 ${className}`}
      data-testid="maintainer-reply-tone-coach"
    >
      <div className="rounded-[2rem] border-4 border-black bg-white p-5 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924]">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="flex items-center gap-2 text-xl font-black dark:text-[#f0ebe2]">
              <MessageSquareHeart
                className="h-5 w-5 text-primary"
                aria-hidden
              />
              Draft your issue / PR reply
            </h2>
            <p className="mt-1 text-xs font-bold text-muted dark:text-[#c4bbae]">
              Rule-based coach from{" "}
              <Link
                to="/lessons/respect-and-communication"
                className="underline underline-offset-2"
              >
                Module 4 etiquette
              </Link>
              . No AI required.
            </p>
          </div>
          {draft.trim() && (
            <div
              className={`rounded-full border-2 border-black px-3 py-1 text-[11px] font-black ${
                analysis.ok
                  ? "bg-green-200"
                  : analysis.score >= 45
                    ? "bg-amber-200"
                    : "bg-red-200"
              }`}
              aria-live="polite"
            >
              {analysis.score}/100 · {scoreLabel(analysis.score)}
            </div>
          )}
        </div>

        <label className="sr-only" htmlFor="tone-coach-draft">
          Reply draft
        </label>
        <textarea
          id="tone-coach-draft"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={6}
          placeholder='e.g. "any update???" or a real comment you almost posted…'
          className="w-full resize-y rounded-2xl border-4 border-black bg-surface-low p-4 text-sm font-bold leading-relaxed outline-none focus:ring-2 focus:ring-primary dark:bg-[#151411] dark:border-[#2e2924] dark:text-[#f0ebe2]"
        />

        <ul className="mt-4 space-y-2" aria-live="polite">
          {analysis.flags.map((flag) => (
            <li
              key={flag.code}
              className={`flex gap-2 rounded-xl border-2 p-3 text-sm ${
                flag.severity === "error"
                  ? "border-red-500 bg-red-50 dark:bg-red-950/30"
                  : flag.severity === "warning"
                    ? "border-amber-500 bg-amber-50 dark:bg-amber-950/20"
                    : "border-black/20 bg-surface-low dark:bg-[#151411] dark:border-[#2e2924]"
              }`}
            >
              {flag.severity === "error" || flag.severity === "warning" ? (
                <AlertCircle
                  className="mt-0.5 h-4 w-4 shrink-0 text-red-600 dark:text-amber-400"
                  aria-hidden
                />
              ) : (
                <Sparkles
                  className="mt-0.5 h-4 w-4 shrink-0 text-primary"
                  aria-hidden
                />
              )}
              <div>
                <p className="font-black dark:text-[#f0ebe2]">{flag.title}</p>
                <p className="text-xs font-bold text-muted dark:text-[#c4bbae]">
                  {flag.message}
                </p>
              </div>
            </li>
          ))}
          {analysis.ok && draft.trim() && (
            <li className="flex gap-2 rounded-xl border-2 border-green-600 bg-green-50 p-3 text-sm dark:bg-green-950/20">
              <CheckCircle2
                className="mt-0.5 h-4 w-4 shrink-0 text-green-700"
                aria-hidden
              />
              <p className="font-black text-green-900 dark:text-green-200">
                Looks maintainer-friendly — clear, patient, and kind.
              </p>
            </li>
          )}
        </ul>

        {showSuggestion && (
          <div className="mt-4 rounded-2xl border-4 border-dashed border-black/40 bg-teal-50 p-4 dark:bg-teal-950/20 dark:border-[#2e2924]">
            <p className="mb-2 text-[10px] font-black uppercase tracking-wider text-teal-800 dark:text-teal-200">
              Suggested rewrite
            </p>
            <p className="mb-3 text-sm font-bold leading-relaxed dark:text-[#f0ebe2]">
              {suggestion}
            </p>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => void applySuggestion()}
                className="rounded-xl border-2 border-black bg-primary px-4 py-2 text-xs font-black shadow-card-sm hover:-translate-y-0.5 transition"
              >
                Apply rewrite
                {enableXp && !xpClaimed ? ` (+${TONE_COACH_XP} XP)` : ""}
              </button>
              <button
                type="button"
                onClick={() => void copySuggestion()}
                className="inline-flex items-center gap-1 rounded-xl border-2 border-black bg-white px-4 py-2 text-xs font-black dark:bg-[#151411] dark:border-[#2e2924]"
              >
                {copied ? (
                  <Check className="h-3.5 w-3.5" />
                ) : (
                  <Copy className="h-3.5 w-3.5" />
                )}
                {copied ? "Copied" : "Copy"}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Examples panel */}
      <section className="rounded-[2rem] border-4 border-black bg-amber-50 p-5 shadow-card dark:bg-[#1c1915] dark:border-[#2e2924]">
        <div className="mb-4 flex items-center gap-2">
          <BookOpen className="h-5 w-5" aria-hidden />
          <h2 className="text-lg font-black dark:text-[#f0ebe2]">
            Examples from Module 4
          </h2>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          {examples.map((ex) => (
            <article
              key={ex.id}
              className="rounded-2xl border-2 border-black bg-white p-4 dark:bg-[#151411] dark:border-[#2e2924]"
            >
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-sm font-black dark:text-[#f0ebe2]">
                  {ex.label}
                </h3>
                <Link
                  to={`/lessons/${ex.lessonSlug}`}
                  className="text-[10px] font-black uppercase underline underline-offset-2"
                >
                  Lesson
                </Link>
              </div>
              <p className="mb-2 text-[10px] font-bold text-muted dark:text-[#c4bbae]">
                {ex.tip}
              </p>
              <p className="mb-1 text-[10px] font-black uppercase text-red-700">
                Avoid
              </p>
              <pre className="mb-2 overflow-x-auto rounded-lg border border-red-300 bg-red-50 p-2 text-xs font-bold dark:bg-red-950/30">
                {ex.bad}
              </pre>
              <p className="mb-1 text-[10px] font-black uppercase text-green-700">
                Prefer
              </p>
              <pre className="mb-3 overflow-x-auto rounded-lg border border-green-300 bg-green-50 p-2 text-xs font-bold dark:bg-green-950/30">
                {ex.good}
              </pre>
              <button
                type="button"
                className="text-xs font-black text-primary underline underline-offset-2"
                onClick={() => setDraft(ex.bad)}
              >
                Try the “avoid” example
              </button>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

export default MaintainerReplyToneCoach;
