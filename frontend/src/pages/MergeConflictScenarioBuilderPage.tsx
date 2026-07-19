import { useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  AlertCircle,
  CheckCircle2,
  Copy,
  Check,
  Download,
  GitMerge,
  ArrowLeft,
} from "lucide-react";
import {
  DEFAULT_SCENARIO_DRAFT,
  ScenarioDraft,
  buildScenarioDocument,
  curriculumConflictSnippet,
  scenarioToPrettyJson,
  slugifyScenarioId,
  suggestedContentPath,
  validateScenarioDraft,
} from "../lib/mergeConflictScenarioBuilder";
import { ConflictSandbox } from "../components/ui/ConflictSandbox";

function FieldLabel({
  htmlFor,
  children,
  hint,
}: {
  htmlFor: string;
  children: ReactNode;
  hint?: string;
}) {
  return (
    <label
      htmlFor={htmlFor}
      className="flex flex-col gap-1 text-xs font-black uppercase tracking-wide"
    >
      <span>{children}</span>
      {hint ? (
        <span className="font-bold normal-case text-muted dark:text-[#c4bbae]">
          {hint}
        </span>
      ) : null}
    </label>
  );
}

export function MergeConflictScenarioBuilderPage() {
  const [draft, setDraft] = useState<ScenarioDraft>(DEFAULT_SCENARIO_DRAFT);
  const [copied, setCopied] = useState<"full" | "curriculum" | null>(null);

  const issues = useMemo(() => validateScenarioDraft(draft), [draft]);
  const isValid = issues.length === 0;
  const document = useMemo(
    () => (isValid ? buildScenarioDocument(draft) : null),
    [draft, isValid],
  );

  const update = <K extends keyof ScenarioDraft>(
    key: K,
    value: ScenarioDraft[K],
  ) => {
    setDraft((prev) => ({ ...prev, [key]: value }));
  };

  const downloadJson = () => {
    if (!document) return;
    const blob = new Blob([scenarioToPrettyJson(document)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = window.document.createElement("a");
    a.href = url;
    a.download = `${document.id || "conflict-scenario"}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const copyText = async (text: string, key: "full" | "curriculum") => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(key);
      setTimeout(() => setCopied(null), 2000);
    } catch {
      /* clipboard unavailable */
    }
  };

  return (
    <div className="container mx-auto max-w-6xl px-4 py-8 space-y-8">
      <div>
        <Link
          to="/contributor-sandbox"
          className="mb-4 inline-flex items-center gap-2 text-xs font-black uppercase tracking-wide text-muted hover:text-primary dark:text-[#c4bbae]"
        >
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
          Practice
        </Link>
        <p className="mb-2 inline-flex items-center gap-2 rounded-full border-2 border-black bg-orange-100 px-3 py-1 text-[10px] font-black uppercase tracking-wider dark:bg-orange-900/40 dark:border-[#2e2924]">
          <GitMerge className="h-3.5 w-3.5" aria-hidden />
          Content authoring
        </p>
        <h1 className="text-3xl font-black tracking-tight dark:text-[#fff8ef]">
          Merge Conflict Scenario Builder
        </h1>
        <p className="mt-2 max-w-2xl text-sm font-bold text-muted dark:text-[#d7cec0]">
          Define base / ours / theirs, preview the Conflict Sandbox, then export
          JSON into{" "}
          <code className="rounded bg-surface-low px-1 dark:bg-[#151411]">
            frontend/public/content/conflict-scenarios/
          </code>
          . See{" "}
          <a
            href="https://github.com/nandinigoyaldev/Open-Source-Contribution-Atelier/blob/main/docs/CONTENT_GUIDE.md"
            className="underline underline-offset-2"
            target="_blank"
            rel="noreferrer"
          >
            CONTENT_GUIDE.md
          </a>
          .
        </p>
      </div>

      <div className="grid gap-8 lg:grid-cols-2">
        {/* Form */}
        <section className="space-y-4 rounded-[2rem] border-4 border-black bg-white p-5 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924]">
          <h2 className="text-lg font-black dark:text-[#f0ebe2]">
            Scenario form
          </h2>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <FieldLabel htmlFor="scenario-title">Title</FieldLabel>
              <input
                id="scenario-title"
                value={draft.title}
                onChange={(e) => {
                  const title = e.target.value;
                  setDraft((prev) => ({
                    ...prev,
                    title,
                    id:
                      prev.id === slugifyScenarioId(prev.title) || !prev.id
                        ? slugifyScenarioId(title)
                        : prev.id,
                  }));
                }}
                className="w-full rounded-xl border-2 border-black bg-surface-low px-3 py-2 text-sm font-bold dark:bg-[#151411] dark:border-[#2e2924]"
              />
            </div>
            <div className="space-y-1.5">
              <FieldLabel htmlFor="scenario-id" hint="kebab-case filename stem">
                Id
              </FieldLabel>
              <input
                id="scenario-id"
                value={draft.id}
                onChange={(e) => update("id", e.target.value)}
                className="w-full rounded-xl border-2 border-black bg-surface-low px-3 py-2 text-sm font-bold font-mono dark:bg-[#151411] dark:border-[#2e2924]"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <FieldLabel htmlFor="scenario-desc">Description</FieldLabel>
            <textarea
              id="scenario-desc"
              rows={2}
              value={draft.description}
              onChange={(e) => update("description", e.target.value)}
              className="w-full rounded-xl border-2 border-black bg-surface-low px-3 py-2 text-sm font-bold dark:bg-[#151411] dark:border-[#2e2924]"
            />
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-1.5">
              <FieldLabel htmlFor="base-branch">Base branch</FieldLabel>
              <input
                id="base-branch"
                value={draft.baseBranchName}
                onChange={(e) => update("baseBranchName", e.target.value)}
                className="w-full rounded-xl border-2 border-black bg-surface-low px-3 py-2 text-sm font-bold font-mono dark:bg-[#151411] dark:border-[#2e2924]"
              />
            </div>
            <div className="space-y-1.5">
              <FieldLabel htmlFor="feature-branch">Feature branch</FieldLabel>
              <input
                id="feature-branch"
                value={draft.featureBranchName}
                onChange={(e) => update("featureBranchName", e.target.value)}
                className="w-full rounded-xl border-2 border-black bg-surface-low px-3 py-2 text-sm font-bold font-mono dark:bg-[#151411] dark:border-[#2e2924]"
              />
            </div>
            <div className="space-y-1.5">
              <FieldLabel htmlFor="file-path">File path</FieldLabel>
              <input
                id="file-path"
                value={draft.filePath}
                onChange={(e) => update("filePath", e.target.value)}
                className="w-full rounded-xl border-2 border-black bg-surface-low px-3 py-2 text-sm font-bold font-mono dark:bg-[#151411] dark:border-[#2e2924]"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <FieldLabel
              htmlFor="base-content"
              hint="Shared lines before the conflict hunk"
            >
              Base (shared prefix)
            </FieldLabel>
            <textarea
              id="base-content"
              rows={3}
              value={draft.base}
              onChange={(e) => update("base", e.target.value)}
              className="w-full rounded-xl border-2 border-black bg-[#1e1e1e] px-3 py-2 font-mono text-sm text-green-300 dark:border-[#2e2924]"
              spellCheck={false}
            />
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <FieldLabel htmlFor="ours-content" hint="HEAD / current change">
                Ours
              </FieldLabel>
              <textarea
                id="ours-content"
                rows={5}
                value={draft.ours}
                onChange={(e) => update("ours", e.target.value)}
                className="w-full rounded-xl border-2 border-blue-500 bg-[#1e1e1e] px-3 py-2 font-mono text-sm text-blue-300"
                spellCheck={false}
              />
            </div>
            <div className="space-y-1.5">
              <FieldLabel htmlFor="theirs-content" hint="Incoming change">
                Theirs
              </FieldLabel>
              <textarea
                id="theirs-content"
                rows={5}
                value={draft.theirs}
                onChange={(e) => update("theirs", e.target.value)}
                className="w-full rounded-xl border-2 border-green-500 bg-[#1e1e1e] px-3 py-2 font-mono text-sm text-green-300"
                spellCheck={false}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <FieldLabel
              htmlFor="after-content"
              hint="Shared lines after the conflict hunk"
            >
              After (shared suffix)
            </FieldLabel>
            <textarea
              id="after-content"
              rows={2}
              value={draft.after}
              onChange={(e) => update("after", e.target.value)}
              className="w-full rounded-xl border-2 border-black bg-[#1e1e1e] px-3 py-2 font-mono text-sm text-green-300 dark:border-[#2e2924]"
              spellCheck={false}
            />
          </div>

          {!isValid ? (
            <div
              role="status"
              className="rounded-2xl border-2 border-dashed border-amber-500 bg-amber-50 p-4 dark:bg-amber-950/20"
            >
              <p className="mb-2 flex items-center gap-2 text-sm font-black text-amber-900 dark:text-amber-200">
                <AlertCircle className="h-4 w-4" aria-hidden />
                Complete the scenario to export
              </p>
              <ul className="list-disc space-y-1 pl-5 text-xs font-bold text-amber-800 dark:text-amber-300">
                {issues.map((issue) => (
                  <li key={`${issue.field}-${issue.message}`}>
                    {issue.message}
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <div className="rounded-2xl border-2 border-green-600 bg-green-50 p-4 dark:bg-green-950/20">
              <p className="flex items-center gap-2 text-sm font-black text-green-900 dark:text-green-200">
                <CheckCircle2 className="h-4 w-4" aria-hidden />
                Ready to export →{" "}
                <code className="font-mono text-[11px]">
                  {suggestedContentPath(draft.id)}
                </code>
              </p>
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={!document}
              onClick={downloadJson}
              className="inline-flex items-center gap-2 rounded-xl border-2 border-black bg-primary px-4 py-2 text-xs font-black shadow-card-sm disabled:opacity-50"
            >
              <Download className="h-3.5 w-3.5" aria-hidden />
              Download JSON
            </button>
            <button
              type="button"
              disabled={!document}
              onClick={() =>
                document &&
                void copyText(scenarioToPrettyJson(document), "full")
              }
              className="inline-flex items-center gap-2 rounded-xl border-2 border-black bg-white px-4 py-2 text-xs font-black dark:bg-[#151411] dark:border-[#2e2924] disabled:opacity-50"
            >
              {copied === "full" ? (
                <Check className="h-3.5 w-3.5" />
              ) : (
                <Copy className="h-3.5 w-3.5" />
              )}
              Copy full JSON
            </button>
            <button
              type="button"
              disabled={!document}
              onClick={() =>
                document &&
                void copyText(curriculumConflictSnippet(document), "curriculum")
              }
              className="inline-flex items-center gap-2 rounded-xl border-2 border-black bg-white px-4 py-2 text-xs font-black dark:bg-[#151411] dark:border-[#2e2924] disabled:opacity-50"
            >
              {copied === "curriculum" ? (
                <Check className="h-3.5 w-3.5" />
              ) : (
                <Copy className="h-3.5 w-3.5" />
              )}
              Copy curriculum snippet
            </button>
          </div>
        </section>

        {/* Preview + JSON */}
        <section className="space-y-4">
          <div className="rounded-[2rem] border-4 border-black bg-white p-5 shadow-card dark:bg-[#1f1c18] dark:border-[#2e2924]">
            <h2 className="mb-3 text-lg font-black dark:text-[#f0ebe2]">
              Live ConflictSandbox preview
            </h2>
            {document ? (
              <ConflictSandbox
                key={document.conflictScenario.fileContent}
                baseBranchName={document.conflictScenario.baseBranchName}
                featureBranchName={document.conflictScenario.featureBranchName}
                initialContent={document.conflictScenario.fileContent}
              />
            ) : (
              <div className="rounded-2xl border-4 border-dashed border-black/30 bg-surface-low p-10 text-center dark:bg-[#151411] dark:border-[#2e2924]">
                <AlertCircle className="mx-auto mb-3 h-8 w-8 text-muted" />
                <p className="font-black dark:text-[#f0ebe2]">
                  Preview unavailable
                </p>
                <p className="mt-1 text-sm font-bold text-muted dark:text-[#c4bbae]">
                  Fill ours, theirs, and shared context to preview the sandbox.
                </p>
              </div>
            )}
          </div>

          {document && (
            <div className="rounded-[2rem] border-4 border-black bg-[#1e1e1e] p-5 shadow-card">
              <h2 className="mb-3 text-sm font-black uppercase tracking-wider text-white/70">
                Export preview
              </h2>
              <pre className="max-h-80 overflow-auto text-xs font-bold text-green-300 whitespace-pre-wrap">
                {scenarioToPrettyJson(document)}
              </pre>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
