import React, { useState, useMemo, useCallback } from "react";
import {
  Braces,
  Search,
  Copy,
  Check,
  Download,
  Wand2,
  FileText,
  FileCode,
  BarChart3,
} from "lucide-react";

import { JsonTreeView } from "./json/JsonTreeView";
import type { JsonStats, JsonViewMode } from "./json/types";
import {
  analyzeJson,
  formatJson,
  minifyJson,
  parseJsonSafe,
  isValidJson,
  SAMPLE_PRESETS,
} from "./json/jsonUtils";

function StatBadge({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className={`flex items-center gap-2 px-3 py-2 rounded-xl border-2 ${color}`}>
      <span className="text-lg font-black">{value}</span>
      <span className="text-[10px] font-black uppercase text-muted dark:text-[#9b8f80]">{label}</span>
    </div>
  );
}

export function JsonTreeViewer() {
  const [rawInput, setRawInput] = useState("");
  const [viewMode, setViewMode] = useState<JsonViewMode>("tree");
  const [indent, setIndent] = useState(2);
  const [searchQuery, setSearchQuery] = useState("");
  const [copied, setCopied] = useState(false);

  const { value, error } = useMemo(() => parseJsonSafe(rawInput), [rawInput]);

  const stats: JsonStats | null = useMemo(
    () => (value !== null ? analyzeJson(value) : null),
    [value],
  );

  const formatted = useMemo(
    () => (value !== null ? formatJson(value, indent) : ""),
    [value, indent],
  );

  const minified = useMemo(
    () => (value !== null ? minifyJson(value) : ""),
    [value],
  );

  const displayCode = viewMode === "raw" ? (rawInput ? (isValidJson(rawInput) ? formatJson(JSON.parse(rawInput), indent) : rawInput) : "") : "";

  const loadPreset = useCallback((data: unknown) => {
    setRawInput(formatJson(data, indent));
    setViewMode("tree");
  }, [indent]);

  const handleFormat = useCallback(() => {
    if (value !== null) {
      setRawInput(formatJson(value, indent));
      setViewMode("raw");
    }
  }, [value, indent]);

  const handleMinify = useCallback(() => {
    if (value !== null) {
      setRawInput(minifyJson(value));
      setViewMode("raw");
    }
  }, [value]);

  const handleCopy = useCallback(async () => {
    const text = viewMode === "raw" ? rawInput : formatted;
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }, [viewMode, rawInput, formatted]);

  const handleDownload = useCallback(() => {
    const text = viewMode === "raw" ? rawInput : formatted;
    const blob = new Blob([text], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "data.json";
    a.click();
    URL.revokeObjectURL(url);
  }, [viewMode, rawInput, formatted]);

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-12">
      {/* Header */}
      <div className="bg-surface-low dark:bg-[#151411] border-4 border-black dark:border-[#2e2924] rounded-2xl p-6 shadow-card flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="bg-primary text-black text-xs font-black px-2.5 py-1 rounded-md border border-black uppercase tracking-wider flex items-center gap-1">
              <Braces className="w-3.5 h-3.5" /> Developer Tool
            </span>
            <span className="bg-accent/20 text-accent text-xs font-bold px-2.5 py-1 rounded-md border border-accent/40">
              Atelier Studio
            </span>
          </div>
          <h1 className="text-2xl md:text-3xl font-black text-text dark:text-[#f0ebe2]">
            JSON Tree Viewer & Formatter
          </h1>
          <p className="mt-1 text-sm font-bold text-muted dark:text-[#c4bbae] max-w-xl">
            Visualize, format, minify, and search JSON data with an interactive
            collapsible tree view and detailed statistics.
          </p>
        </div>
      </div>

      {/* Presets */}
      <div className="bg-surface-low dark:bg-[#151411] border-4 border-black dark:border-[#2e2924] rounded-2xl overflow-hidden shadow-card">
        <div className="flex items-center gap-2 px-4 py-3 border-b-4 border-black dark:border-[#2e2924]">
          <FileCode className="w-4 h-4 text-primary" />
          <span className="font-black text-xs uppercase tracking-wider text-text dark:text-[#f0ebe2]">
            Sample Data
          </span>
        </div>
        <div className="p-3 overflow-x-auto">
          <div className="flex gap-2 min-w-max">
            {SAMPLE_PRESETS.map((p) => (
              <button
                key={p.name}
                onClick={() => loadPreset(p.data)}
                className="px-3 py-2 rounded-xl border-2 border-black/10 dark:border-[#2e2924] bg-white dark:bg-[#0f0e0c] hover:border-primary hover:bg-primary/5 transition-all text-left min-w-[110px]"
              >
                <span className="font-black text-[11px] text-text dark:text-[#f0ebe2] block">
                  {p.name}
                </span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Input / Raw view */}
        <div className="space-y-4">
          <div className="bg-surface-low dark:bg-[#151411] border-4 border-black dark:border-[#2e2924] rounded-2xl overflow-hidden shadow-card">
            <div className="flex items-center justify-between px-4 py-3 border-b-4 border-black dark:border-[#2e2924]">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-primary" />
                <span className="font-black text-xs uppercase tracking-wider text-text dark:text-[#f0ebe2]">
                  JSON Input
                </span>
                {error && (
                  <span className="text-[10px] font-black text-red-500 bg-red-100 dark:bg-red-950/30 px-2 py-0.5 rounded-full border border-red-300 dark:border-red-800">
                    Error
                  </span>
                )}
                {!error && rawInput && (
                  <span className="text-[10px] font-black text-green-600 bg-green-100 dark:bg-green-950/30 px-2 py-0.5 rounded-full border border-green-300 dark:border-green-800">
                    Valid
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1.5">
                <button
                  onClick={handleFormat}
                  disabled={!value}
                  className="flex items-center gap-1 px-2 py-1 text-[10px] font-black uppercase bg-primary text-black border-2 border-black rounded-lg hover:-translate-y-0.5 transition-all disabled:opacity-40"
                >
                  <Wand2 className="w-3 h-3" /> Pretty
                </button>
                <button
                  onClick={handleMinify}
                  disabled={!value}
                  className="flex items-center gap-1 px-2 py-1 text-[10px] font-black uppercase bg-surface dark:bg-[#1f1c18] text-muted dark:text-[#c4bbae] border-2 border-black dark:border-[#2e2924] rounded-lg hover:-translate-y-0.5 transition-all disabled:opacity-40"
                >
                  Minify
                </button>
              </div>
            </div>

            <textarea
              value={rawInput}
              onChange={(e) => setRawInput(e.target.value)}
              className="w-full h-80 p-4 font-mono text-xs leading-relaxed text-text dark:text-[#f0ebe2] bg-white dark:bg-[#0f0e0c] outline-none resize-none placeholder-[#9b8f80] focus:border-primary"
              placeholder='{"paste": "your JSON here"}'
              spellCheck={false}
            />

            {error && (
              <div className="px-4 py-2 border-t-2 border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/20">
                <span className="text-[11px] font-mono font-bold text-red-600 dark:text-red-400">
                  {error}
                </span>
              </div>
            )}
          </div>

          {/* Stats */}
          {stats && (
            <div className="bg-surface-low dark:bg-[#151411] border-4 border-black dark:border-[#2e2924] rounded-2xl overflow-hidden shadow-card">
              <div className="flex items-center gap-2 px-4 py-3 border-b-4 border-black dark:border-[#2e2924]">
                <BarChart3 className="w-4 h-4 text-primary" />
                <span className="font-black text-xs uppercase tracking-wider text-text dark:text-[#f0ebe2]">
                  Statistics
                </span>
              </div>
              <div className="p-3 grid grid-cols-4 gap-2">
                <StatBadge label="Nodes" value={stats.nodeCount} color="bg-primary/10 border-primary/30" />
                <StatBadge label="Depth" value={stats.maxDepth} color="bg-purple-100 dark:bg-purple-950/30 border-purple-300 dark:border-purple-800" />
                <StatBadge label="Strings" value={stats.stringCount} color="bg-green-100 dark:bg-green-950/30 border-green-300 dark:border-green-800" />
                <StatBadge label="Numbers" value={stats.numberCount} color="bg-blue-100 dark:bg-blue-950/30 border-blue-300 dark:border-blue-800" />
                <StatBadge label="Booleans" value={stats.booleanCount} color="bg-amber-100 dark:bg-amber-950/30 border-amber-300 dark:border-amber-800" />
                <StatBadge label="Nulls" value={stats.nullCount} color="bg-gray-100 dark:bg-gray-800/30 border-gray-300 dark:border-gray-700" />
                <StatBadge label="Objects" value={stats.objectCount} color="bg-purple-100 dark:bg-purple-950/30 border-purple-300 dark:border-purple-800" />
                <StatBadge label="Arrays" value={stats.arrayCount} color="bg-cyan-100 dark:bg-cyan-950/30 border-cyan-300 dark:border-cyan-800" />
              </div>
            </div>
          )}
        </div>

        {/* Right: Tree / Raw view */}
        <div className="bg-surface-low dark:bg-[#151411] border-4 border-black dark:border-[#2e2924] rounded-2xl overflow-hidden shadow-card flex flex-col">
          <div className="flex items-center justify-between px-4 py-3 border-b-4 border-black dark:border-[#2e2924]">
            <div className="flex items-center gap-1">
              <button
                onClick={() => setViewMode("tree")}
                className={`px-3 py-1.5 text-[10px] font-black uppercase rounded-lg border-2 transition-all ${
                  viewMode === "tree"
                    ? "bg-primary text-black border-black shadow-card-sm"
                    : "bg-white dark:bg-[#1f1c18] text-muted dark:text-[#9b8f80] border-black/15 dark:border-[#2e2924]"
                }`}
              >
                Tree
              </button>
              <button
                onClick={() => setViewMode("raw")}
                className={`px-3 py-1.5 text-[10px] font-black uppercase rounded-lg border-2 transition-all ${
                  viewMode === "raw"
                    ? "bg-primary text-black border-black shadow-card-sm"
                    : "bg-white dark:bg-[#1f1c18] text-muted dark:text-[#9b8f80] border-black/15 dark:border-[#2e2924]"
                }`}
              >
                Raw
              </button>
            </div>

            <div className="flex items-center gap-1.5">
              {viewMode === "raw" && (
                <select
                  value={indent}
                  onChange={(e) => setIndent(Number(e.target.value))}
                  className="px-2 py-1 text-[10px] font-mono font-bold text-text dark:text-[#f0ebe2] bg-white dark:bg-[#0f0e0c] border-2 border-black dark:border-[#2e2924] rounded-lg"
                >
                  <option value={2}>2 spaces</option>
                  <option value={4}>4 spaces</option>
                  <option value={8}>8 spaces</option>
                </select>
              )}
              <button
                onClick={handleCopy}
                className="flex items-center gap-1 px-2 py-1 text-[10px] font-black uppercase bg-surface dark:bg-[#1f1c18] text-muted dark:text-[#c4bbae] border-2 border-black dark:border-[#2e2924] rounded-lg hover:-translate-y-0.5 transition-all"
              >
                {copied ? <Check className="w-3 h-3 text-green-500" /> : <Copy className="w-3 h-3" />}
                {copied ? "Copied!" : "Copy"}
              </button>
              <button
                onClick={handleDownload}
                className="flex items-center gap-1 px-2 py-1 text-[10px] font-black uppercase bg-surface dark:bg-[#1f1c18] text-muted dark:text-[#c4bbae] border-2 border-black dark:border-[#2e2924] rounded-lg hover:-translate-y-0.5 transition-all"
              >
                <Download className="w-3 h-3" /> JSON
              </button>
            </div>
          </div>

          {/* Search */}
          {viewMode === "tree" && value !== null && (
            <div className="px-4 py-2 border-b-2 border-black/10 dark:border-[#2e2924]">
              <div className="flex items-center gap-2 bg-white dark:bg-[#0f0e0c] border-2 border-black dark:border-[#2e2924] rounded-lg px-3 py-1.5">
                <Search className="w-3.5 h-3.5 text-muted" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search keys or values..."
                  className="flex-1 bg-transparent font-mono text-xs font-bold text-text dark:text-[#f0ebe2] outline-none placeholder-[#9b8f80]"
                />
              </div>
            </div>
          )}

          {/* Content */}
          <div className="flex-1 overflow-auto p-3 min-h-[400px]">
            {!rawInput ? (
              <div className="flex flex-col items-center justify-center h-full text-center py-12">
                <Braces className="w-12 h-12 text-muted/30 dark:text-[#4a4540] mb-3" />
                <span className="text-sm font-bold text-muted dark:text-[#9b8f80]">
                  Paste JSON on the left or load a sample
                </span>
              </div>
            ) : error ? (
              <div className="flex flex-col items-center justify-center h-full text-center py-12">
                <span className="text-sm font-bold text-red-500">Fix JSON errors to view tree</span>
              </div>
            ) : viewMode === "tree" ? (
              <JsonTreeView data={value!} searchQuery={searchQuery} />
            ) : (
              <pre className="font-mono text-xs leading-relaxed text-text dark:text-[#f0ebe2] whitespace-pre-wrap break-all">
                {displayCode || rawInput}
              </pre>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default JsonTreeViewer;
