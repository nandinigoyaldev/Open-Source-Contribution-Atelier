import React, { useMemo, useState } from "react";
import { Copy, Check, FileDiff, Sparkles } from "lucide-react";
import {
  summarizeDiff,
  buildPrDescription,
  buildChecklist,
  AREA_LABELS,
  type ChangeArea,
} from "../../../lib/prDiffSummarizer";

const SAMPLE_INPUT = `frontend/src/components/ui/PrDiffSummarizer/PrDiffSummarizer.tsx
frontend/src/lib/prDiffSummarizer.ts
frontend/src/test/prDiffSummarizer.test.ts
backend/apps/progress/migrations/0012_example.py
docs/CONTENT_GUIDE.md
.github/pull_request_template.md`;

export type PrDiffSummarizerProps = {
  compact?: boolean;
  className?: string;
  defaultIssueNumber?: string;
};

export function PrDiffSummarizer({
  compact = false,
  className = "",
  defaultIssueNumber = "",
}: PrDiffSummarizerProps) {
  const [raw, setRaw] = useState("");
  const [issueNumber, setIssueNumber] = useState(defaultIssueNumber);
  const [titleHint, setTitleHint] = useState("");
  const [copied, setCopied] = useState(false);

  const summary = useMemo(() => summarizeDiff(raw), [raw]);
  const checklist = useMemo(() => buildChecklist(summary), [summary]);
  const prBody = useMemo(
    () =>
      buildPrDescription(raw, {
        issueNumber,
        titleHint,
        summary,
      }),
    [raw, issueNumber, titleHint, summary],
  );

  const hasFiles = summary.files.length > 0;

  const copyBody = async () => {
    try {
      await navigator.clipboard.writeText(prBody);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard may be unavailable
    }
  };

  return (
    <div
      className={`rounded-2xl border-4 border-black bg-white p-4 md:p-6 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none space-y-4 ${className}`}
      data-testid="pr-diff-summarizer"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-black text-text dark:text-[#f0ebe2] flex items-center gap-2">
            <FileDiff size={18} className="text-accent" aria-hidden />
            PR Description Diff Summarizer
          </h3>
          {!compact && (
            <p className="text-xs font-bold text-muted mt-1 dark:text-[#c4bbae]">
              Paste file paths or{" "}
              <code className="bg-surface-low dark:bg-black px-1 rounded font-mono">
                git diff --name-only
              </code>{" "}
              output — get a checklist-ready PR body.
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={() => setRaw(SAMPLE_INPUT)}
          className="shrink-0 px-3 py-1.5 text-xs font-black rounded-lg border-2 border-black bg-surface-low dark:bg-[#151411] dark:text-[#f0ebe2] shadow-card-sm hover:-translate-y-0.5 transition-all inline-flex items-center gap-1"
        >
          <Sparkles size={14} /> Try sample
        </button>
      </div>

      <label className="block text-sm font-black text-text dark:text-[#f0ebe2]">
        Changed files
        <textarea
          value={raw}
          onChange={(e) => setRaw(e.target.value)}
          rows={compact ? 5 : 8}
          placeholder={`Paste paths, one per line…\nfrontend/src/App.tsx\nbackend/apps/content/models.py\ndocs/CONTENT_GUIDE.md`}
          className="mt-2 w-full border-4 border-black px-4 py-3 rounded-xl font-mono text-xs bg-white text-black shadow-card-sm dark:bg-[#151411] dark:border-[#2e2924] dark:text-[#f0ebe2] focus:outline-none focus:ring-2 focus:ring-accent resize-y"
          aria-describedby="pr-diff-hint"
        />
      </label>
      <p
        id="pr-diff-hint"
        className="text-[11px] text-muted font-bold dark:text-[#c4bbae] -mt-2"
      >
        Accepts plain paths, <code className="font-mono">git status</code>, or{" "}
        <code className="font-mono">git diff --name-only</code>.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <label className="block text-sm font-black text-text dark:text-[#f0ebe2]">
          Issue number
          <input
            type="text"
            value={issueNumber}
            onChange={(e) =>
              setIssueNumber(e.target.value.replace(/[^\d]/g, ""))
            }
            placeholder="1822"
            className="mt-2 w-full border-4 border-black px-3 py-2 rounded-xl font-mono text-sm bg-white text-black dark:bg-[#151411] dark:border-[#2e2924] dark:text-[#f0ebe2] focus:outline-none focus:ring-2 focus:ring-accent"
          />
        </label>
        <label className="block text-sm font-black text-text dark:text-[#f0ebe2]">
          Short summary (optional)
          <input
            type="text"
            value={titleHint}
            onChange={(e) => setTitleHint(e.target.value)}
            placeholder="Add PR diff summarizer tool"
            className="mt-2 w-full border-4 border-black px-3 py-2 rounded-xl text-sm bg-white text-black dark:bg-[#151411] dark:border-[#2e2924] dark:text-[#f0ebe2] focus:outline-none focus:ring-2 focus:ring-accent"
          />
        </label>
      </div>

      {!hasFiles && raw.trim() && (
        <div
          className="rounded-xl border-2 border-amber-500 bg-amber-500/10 p-3 text-sm font-bold text-amber-900 dark:text-amber-200"
          role="alert"
        >
          No file paths detected. Paste one path per line (e.g.{" "}
          <code className="font-mono">frontend/src/App.tsx</code>).
        </div>
      )}

      {!raw.trim() && (
        <p className="text-xs text-muted font-bold dark:text-[#c4bbae]">
          Waiting for file paths… Detection covers <strong>backend/</strong>,{" "}
          <strong>frontend/</strong>, <strong>docs/</strong>,{" "}
          <strong>*.md</strong>, and migrations.
        </p>
      )}

      {hasFiles && (
        <>
          <div
            className="flex flex-wrap gap-2"
            aria-label="Detected change areas"
          >
            {(Object.keys(summary.counts) as ChangeArea[]).map((area) => (
              <span
                key={area}
                className="text-[10px] font-black uppercase tracking-widest px-2 py-1 rounded-lg border-2 border-black bg-accent/30 text-black dark:bg-accent/20 dark:text-[#f0ebe2] dark:border-[#2e2924]"
              >
                {AREA_LABELS[area]} ×{summary.counts[area]}
              </span>
            ))}
          </div>

          {!compact && (
            <ul className="text-xs font-mono space-y-1 max-h-32 overflow-y-auto border-2 border-black/10 dark:border-[#2e2924] rounded-xl p-3 bg-surface-low dark:bg-[#151411]">
              {summary.files.map((f) => (
                <li key={f.path} className="text-text dark:text-[#f0ebe2]">
                  <span className="text-muted dark:text-[#c4bbae]">
                    [{f.areas.join(", ")}]
                  </span>{" "}
                  {f.path}
                </li>
              ))}
            </ul>
          )}

          <div>
            <p className="text-[10px] font-black uppercase tracking-widest text-muted dark:text-[#c4bbae] mb-2">
              Suggested checklist ({checklist.length})
            </p>
            <ul className="space-y-1.5 text-sm font-bold text-text dark:text-[#f0ebe2]">
              {checklist.slice(0, compact ? 5 : undefined).map((item) => (
                <li key={item.id} className="flex gap-2">
                  <span aria-hidden>☐</span>
                  <span>{item.label}</span>
                </li>
              ))}
              {compact && checklist.length > 5 && (
                <li className="text-xs text-muted dark:text-[#c4bbae]">
                  +{checklist.length - 5} more in the copied PR body
                </li>
              )}
            </ul>
          </div>
        </>
      )}

      <div>
        <div className="flex items-center justify-between gap-2 mb-2">
          <p className="text-[10px] font-black uppercase tracking-widest text-muted dark:text-[#c4bbae]">
            Generated PR body
          </p>
          <button
            type="button"
            onClick={copyBody}
            disabled={!hasFiles}
            className="px-3 py-1.5 text-xs font-black rounded-lg border-2 border-black bg-accent text-black shadow-card-sm hover:-translate-y-0.5 transition-all inline-flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0"
          >
            {copied ? (
              <>
                <Check size={14} /> Copied
              </>
            ) : (
              <>
                <Copy size={14} /> Copy PR description
              </>
            )}
          </button>
        </div>
        <pre className="w-full max-h-64 overflow-auto border-4 border-black rounded-xl p-3 font-mono text-[11px] leading-relaxed bg-surface-low text-black dark:bg-[#0f0e0c] dark:border-[#2e2924] dark:text-[#f0ebe2] whitespace-pre-wrap">
          {hasFiles
            ? prBody
            : "Paste changed files to generate a PR description…"}
        </pre>
      </div>
    </div>
  );
}

export default PrDiffSummarizer;
