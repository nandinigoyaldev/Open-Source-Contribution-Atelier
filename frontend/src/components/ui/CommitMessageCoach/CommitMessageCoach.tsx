import React, { useMemo, useState } from "react";
import {
  CheckCircle2,
  AlertCircle,
  Copy,
  Check,
  Sparkles,
  ClipboardList,
} from "lucide-react";
import {
  validateCommitMessage,
  suggestCommitRewrite,
  buildPrChecklistTemplate,
  COMMIT_TYPE_HINTS,
  ALLOWED_TYPES,
} from "../../../lib/conventionalCommitCoach";

export type CommitMessageCoachProps = {
  /** Controlled value — when provided, parent owns the message */
  value?: string;
  /** Called whenever the message changes */
  onChange?: (message: string) => void;
  /** Compact layout for embedding inside simulators */
  compact?: boolean;
  className?: string;
  defaultValue?: string;
};

export function CommitMessageCoach({
  value,
  onChange,
  compact = false,
  className = "",
  defaultValue = "",
}: CommitMessageCoachProps) {
  const [internal, setInternal] = useState(defaultValue);
  const [copiedKey, setCopiedKey] = useState<"message" | "pr" | null>(null);

  const message = value !== undefined ? value : internal;

  const setMessage = (next: string) => {
    if (value === undefined) setInternal(next);
    onChange?.(next);
  };

  const result = useMemo(() => validateCommitMessage(message), [message]);
  const suggestion = useMemo(() => suggestCommitRewrite(message), [message]);
  const showSuggestion = message.trim().length > 0 && !result.valid;

  const copyText = async (text: string, key: "message" | "pr") => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 2000);
    } catch {
      // Clipboard may be unavailable in insecure contexts
    }
  };

  return (
    <div
      className={`rounded-2xl border-4 border-black bg-white p-4 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none ${className}`}
      data-testid="commit-message-coach"
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <h3 className="text-lg font-black text-text dark:text-[#f0ebe2] flex items-center gap-2">
            <Sparkles size={18} className="text-accent" aria-hidden />
            Commit Message Coach
          </h3>
          {!compact && (
            <p className="text-xs font-bold text-muted mt-1 dark:text-[#c4bbae]">
              Practice Conventional Commits:{" "}
              <code className="bg-surface-low dark:bg-black px-1 rounded font-mono">
                type(scope): subject
              </code>
            </p>
          )}
        </div>
        {message.trim() && (
          <span
            className={`shrink-0 text-[10px] font-black uppercase tracking-widest px-2 py-1 rounded-lg border-2 ${
              result.valid
                ? "bg-green-500/15 text-green-700 border-green-600 dark:text-green-400 dark:border-green-500"
                : "bg-amber-500/15 text-amber-800 border-amber-600 dark:text-amber-300 dark:border-amber-500"
            }`}
            aria-live="polite"
          >
            {result.valid ? "Valid" : "Needs fixes"}
          </span>
        )}
      </div>

      <label className="block text-sm font-black mb-2 text-text dark:text-[#f0ebe2]">
        Commit message
        <input
          type="text"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="e.g. feat(auth): add password reset flow"
          className="mt-2 w-full border-4 border-black px-4 py-3 rounded-xl font-mono text-sm bg-white text-black shadow-card-sm dark:bg-[#151411] dark:border-[#2e2924] dark:text-[#f0ebe2] focus:outline-none focus:ring-2 focus:ring-accent"
          aria-invalid={message.trim().length > 0 && !result.valid}
          aria-describedby="commit-coach-feedback"
        />
      </label>

      <div id="commit-coach-feedback" className="space-y-2 min-h-[1.5rem]">
        {message.trim().length === 0 && (
          <p className="text-xs text-muted font-bold dark:text-[#c4bbae]">
            Tip: allowed types — {ALLOWED_TYPES.join(", ")}
          </p>
        )}

        {result.valid && message.trim() && (
          <div className="flex items-start gap-2 rounded-xl border-2 border-green-500 bg-green-500/10 p-3 text-sm font-bold text-green-700 dark:text-green-400">
            <CheckCircle2 size={18} className="shrink-0 mt-0.5" aria-hidden />
            <span>Looks great! This follows Conventional Commits.</span>
          </div>
        )}

        {!result.valid &&
          result.issues.map((issue) => (
            <div
              key={issue.code + issue.message}
              className="flex items-start gap-2 rounded-xl border-2 border-amber-500 bg-amber-500/10 p-3 text-sm font-bold text-amber-900 dark:text-amber-200"
              role="alert"
            >
              <AlertCircle size={18} className="shrink-0 mt-0.5" aria-hidden />
              <span>{issue.message}</span>
            </div>
          ))}
      </div>

      {showSuggestion && (
        <div className="mt-4 space-y-2 rounded-xl border-2 border-black/20 dark:border-[#2e2924] bg-surface-low dark:bg-[#151411] p-3">
          <p className="text-[10px] font-black uppercase tracking-widest text-muted dark:text-[#c4bbae]">
            Suggested rewrite
          </p>
          <code className="block font-mono text-sm break-all text-text dark:text-[#f0ebe2]">
            {suggestion}
          </code>
          <div className="flex flex-wrap gap-2 pt-1">
            <button
              type="button"
              onClick={() => setMessage(suggestion)}
              className="px-3 py-1.5 text-xs font-black rounded-lg border-2 border-black bg-accent text-black shadow-card-sm hover:-translate-y-0.5 transition-all"
            >
              Apply fix
            </button>
            <button
              type="button"
              onClick={() => copyText(suggestion, "message")}
              className="px-3 py-1.5 text-xs font-black rounded-lg border-2 border-black bg-white dark:bg-[#1f1c18] dark:text-[#f0ebe2] shadow-card-sm hover:-translate-y-0.5 transition-all inline-flex items-center gap-1"
            >
              {copiedKey === "message" ? (
                <>
                  <Check size={14} /> Copied
                </>
              ) : (
                <>
                  <Copy size={14} /> Copy rewrite
                </>
              )}
            </button>
          </div>
        </div>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        {result.valid && message.trim() && (
          <button
            type="button"
            onClick={() => copyText(message.trim(), "message")}
            className="px-3 py-1.5 text-xs font-black rounded-lg border-2 border-black bg-white dark:bg-[#151411] dark:text-[#f0ebe2] shadow-card-sm hover:-translate-y-0.5 transition-all inline-flex items-center gap-1"
          >
            {copiedKey === "message" ? (
              <>
                <Check size={14} /> Copied
              </>
            ) : (
              <>
                <Copy size={14} /> Copy message
              </>
            )}
          </button>
        )}
        <button
          type="button"
          onClick={() =>
            copyText(
              buildPrChecklistTemplate(
                result.valid ? message.trim() : suggestion,
              ),
              "pr",
            )
          }
          className="px-3 py-1.5 text-xs font-black rounded-lg border-2 border-black bg-white dark:bg-[#151411] dark:text-[#f0ebe2] shadow-card-sm hover:-translate-y-0.5 transition-all inline-flex items-center gap-1"
        >
          {copiedKey === "pr" ? (
            <>
              <Check size={14} /> Copied
            </>
          ) : (
            <>
              <ClipboardList size={14} /> Copy PR template
            </>
          )}
        </button>
      </div>

      {!compact && (
        <details className="mt-4 group">
          <summary className="cursor-pointer text-xs font-black uppercase tracking-widest text-muted dark:text-[#c4bbae] list-none flex items-center gap-1">
            <span className="group-open:rotate-90 transition-transform">▸</span>
            Type cheat sheet
          </summary>
          <ul className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-1.5">
            {COMMIT_TYPE_HINTS.map(({ type, hint }) => (
              <li key={type}>
                <button
                  type="button"
                  onClick={() =>
                    setMessage(
                      message.trim()
                        ? suggestCommitRewrite(
                            `${type}: ${result.parsed.subject ?? message}`,
                          )
                        : `${type}: `,
                    )
                  }
                  className="w-full text-left px-2 py-1.5 rounded-lg border-2 border-black/10 dark:border-[#2e2924] hover:border-black dark:hover:border-[#c4bbae] text-xs transition-colors"
                >
                  <span className="font-mono font-black text-accent">
                    {type}
                  </span>
                  <span className="text-muted dark:text-[#c4bbae]">
                    {" "}
                    — {hint}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

export default CommitMessageCoach;
