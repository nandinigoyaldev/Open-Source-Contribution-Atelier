import React, { useState, useCallback, useMemo, useRef } from "react";
import { Zap, Shuffle, BookmarkPlus } from "lucide-react";

import { RegexInput } from "./regex/RegexInput";
import { MatchHighlighter } from "./regex/MatchHighlighter";
import { CheatSheet } from "./regex/CheatSheet";
import type { RegexFlags, RegexMatch } from "./regex/types";
import { formatFlags, PRESETS, GROUP_COLORS } from "./regex/patternLibrary";

export function RegexPlayground() {
  const [pattern, setPattern] = useState("");
  const [flags, setFlags] = useState<RegexFlags>({ g: true, i: false, m: false, s: false });
  const [testString, setTestString] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null);
  const patternRef = useRef<HTMLInputElement | null>(null);

  const matches = useMemo(() => {
    if (!pattern) {
      setError(null);
      return [];
    }

    try {
      const flagStr = formatFlags(flags);
      const regex = new RegExp(pattern, flagStr);
      setError(null);

      const results: RegexMatch[] = [];
      if (flags.g) {
        let m: RegExpExecArray | null;
        let safety = 0;
        while ((m = regex.exec(testString)) !== null && safety < 5000) {
          results.push({
            text: m[0],
            start: m.index,
            end: m.index + m[0].length,
            groups: m.slice(1),
          });
          if (m[0].length === 0) regex.lastIndex++;
          safety++;
        }
      } else {
        const m = regex.exec(testString);
        if (m) {
          results.push({
            text: m[0],
            start: m.index,
            end: m.index + m[0].length,
            groups: m.slice(1),
          });
        }
      }

      return results;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid regex");
      return [];
    }
  }, [pattern, flags, testString]);

  const toggleFlag = useCallback((flag: keyof RegexFlags) => {
    setFlags((prev) => ({ ...prev, [flag]: !prev[flag] }));
  }, []);

  const loadPreset = useCallback((preset: typeof PRESETS[number]) => {
    setPattern(preset.pattern);
    setTestString(preset.testString);
    setSelectedPreset(preset.name);
    const newFlags: RegexFlags = { g: false, i: false, m: false, s: false };
    for (const f of preset.flags) {
      if (f in newFlags) newFlags[f as keyof RegexFlags] = true;
    }
    setFlags(newFlags);
  }, []);

  const handleInsertToken = useCallback((token: string) => {
    setPattern((prev) => prev + token);
    setSelectedPreset(null);
  }, []);

  const randomPreset = useCallback(() => {
    const idx = Math.floor(Math.random() * PRESETS.length);
    loadPreset(PRESETS[idx]);
  }, [loadPreset]);

  const flagStr = formatFlags(flags);
  const regexPreview = pattern ? `/${pattern}/${flagStr || ""}` : "/.../";

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-12">
      {/* Header */}
      <div className="bg-surface-low dark:bg-[#151411] border-4 border-black dark:border-[#2e2924] rounded-2xl p-6 shadow-card flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="bg-primary text-black text-xs font-black px-2.5 py-1 rounded-md border border-black uppercase tracking-wider flex items-center gap-1">
              <Zap className="w-3.5 h-3.5" /> Developer Tool
            </span>
            <span className="bg-accent/20 text-accent text-xs font-bold px-2.5 py-1 rounded-md border border-accent/40">
              Atelier Studio
            </span>
          </div>
          <h1 className="text-2xl md:text-3xl font-black text-text dark:text-[#f0ebe2]">
            Regex Playground
          </h1>
          <p className="mt-1 text-sm font-bold text-muted dark:text-[#c4bbae] max-w-xl">
            Test regular expressions in real time with match highlighting,
            group extraction, a searchable cheat sheet, and curated presets.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={randomPreset}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-black uppercase bg-primary text-black border-2 border-black rounded-xl shadow-card-sm hover:-translate-y-0.5 transition-all"
          >
            <Shuffle className="w-4 h-4" /> Random Preset
          </button>
        </div>
      </div>

      {/* Presets */}
      <div className="bg-surface-low dark:bg-[#151411] border-4 border-black dark:border-[#2e2924] rounded-2xl overflow-hidden shadow-card">
        <div className="flex items-center gap-2 px-4 py-3 border-b-4 border-black dark:border-[#2e2924]">
          <BookmarkPlus className="w-4 h-4 text-primary" />
          <span className="font-black text-xs uppercase tracking-wider text-text dark:text-[#f0ebe2]">
            Common Patterns
          </span>
        </div>
        <div className="p-3 overflow-x-auto">
          <div className="flex gap-2 min-w-max">
            {PRESETS.map((p) => (
              <button
                key={p.name}
                onClick={() => loadPreset(p)}
                className={`flex flex-col items-start px-3 py-2 rounded-xl border-2 transition-all min-w-[140px] text-left ${
                  selectedPreset === p.name
                    ? "border-primary bg-primary/10 shadow-card-sm"
                    : "border-black/10 dark:border-[#2e2924] hover:border-black dark:hover:border-[#c4bbae] bg-white dark:bg-[#0f0e0c]"
                }`}
              >
                <span className="font-black text-[11px] text-text dark:text-[#f0ebe2]">{p.name}</span>
                <span className="text-[10px] font-bold text-muted dark:text-[#9b8f80] mt-0.5 line-clamp-1">
                  {p.description}
                </span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Regex Input */}
      <RegexInput
        pattern={pattern}
        flags={flags}
        error={error}
        onPatternChange={(p) => { setPattern(p); setSelectedPreset(null); }}
        onFlagToggle={toggleFlag}
      />

      {/* Live preview */}
      {pattern && !error && (
        <div className="flex items-center gap-3 px-4 py-2 bg-white dark:bg-[#0f0e0c] border-2 border-black/10 dark:border-[#2e2924] rounded-xl">
          <span className="text-[10px] font-black uppercase text-muted dark:text-[#9b8f80]">Preview:</span>
          <code className="font-mono text-xs font-bold text-primary">{regexPreview}</code>
          <span className="text-[10px] font-bold text-muted/60 dark:text-[#9b8f80]/60">•</span>
          <span className="text-[10px] font-mono font-bold text-muted dark:text-[#9b8f80]">
            {matches.length} match{matches.length !== 1 ? "es" : ""}
          </span>
        </div>
      )}

      {/* Main content area */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-7">
          <MatchHighlighter
            testString={testString}
            onTestStringChange={setTestString}
            matches={matches}
          />
        </div>
        <div className="lg:col-span-5">
          <CheatSheet onInsertToken={handleInsertToken} />
        </div>
      </div>

      {/* Group reference legend */}
      {matches.length > 0 && matches.some((m) => m.groups.some((g) => g !== undefined)) && (
        <div className="bg-surface-low dark:bg-[#151411] border-4 border-black dark:border-[#2e2924] rounded-2xl p-4 shadow-card">
          <div className="flex items-center gap-2 mb-3">
            <span className="font-black text-xs uppercase tracking-wider text-text dark:text-[#f0ebe2]">
              Captured Groups Legend
            </span>
          </div>
          <div className="flex flex-wrap gap-3">
            {(() => {
              const maxGroups = Math.max(
                ...matches.map((m) => m.groups.length)
              );
              return Array.from({ length: maxGroups }, (_, i) => (
                <div key={i} className="flex items-center gap-1.5">
                  <div
                    className="w-3 h-3 rounded-full border-2 border-black/20"
                    style={{ backgroundColor: GROUP_COLORS[i % GROUP_COLORS.length] }}
                  />
                  <span className="text-[11px] font-mono font-bold text-text dark:text-[#f0ebe2]">
                    ${i + 1}
                  </span>
                </div>
              ));
            })()}
          </div>
        </div>
      )}
    </div>
  );
}

export default RegexPlayground;
