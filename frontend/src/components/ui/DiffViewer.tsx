import React, { useState } from "react";
import ReactDiffViewer, { DiffMethod } from "react-diff-viewer-continued";
import { Columns, List, CheckCircle } from "lucide-react";
import { useTheme } from "../../../hooks/useTheme";

interface DiffViewerProps {
  expected: string;
  actual: string;
  title?: string;
}

export function DiffViewer({
  expected,
  actual,
  title = "Output Comparison",
}: DiffViewerProps) {
  const { theme } = useTheme();
  const isDark = theme === "dark";
  const [splitView, setSplitView] = useState(true);

  if (expected.trim() === actual.trim()) {
    return (
      <div className="flex flex-col items-center justify-center p-8 bg-green-50 dark:bg-green-900/20 border-2 border-green-200 dark:border-green-800 rounded-xl">
        <CheckCircle className="w-12 h-12 text-green-500 mb-2" />
        <h3 className="font-bold text-green-700 dark:text-green-300">
          Outputs match perfectly!
        </h3>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 w-full border-2 border-black dark:border-[#2e2924] rounded-xl overflow-hidden bg-surface dark:bg-[#151411]">
      <div className="flex items-center justify-between p-3 border-b-2 border-black dark:border-[#2e2924] bg-surface-low dark:bg-[#1f1c18]">
        <h3 className="font-bold text-sm text-text dark:text-[#f0ebe2]">
          {title}
        </h3>
        <div className="flex bg-black/10 dark:bg-white/10 p-1 rounded-lg">
          <button
            onClick={() => setSplitView(true)}
            className={`p-1 rounded ${
              splitView
                ? "bg-white dark:bg-[#2e2924] shadow-sm text-primary"
                : "text-muted hover:text-text"
            }`}
            title="Side by Side"
          >
            <Columns size={16} />
          </button>
          <button
            onClick={() => setSplitView(false)}
            className={`p-1 rounded ${
              !splitView
                ? "bg-white dark:bg-[#2e2924] shadow-sm text-primary"
                : "text-muted hover:text-text"
            }`}
            title="Inline"
          >
            <List size={16} />
          </button>
        </div>
      </div>
      <div className="overflow-x-auto text-sm">
        <ReactDiffViewer
          oldValue={expected}
          newValue={actual}
          splitView={splitView}
          useDarkTheme={isDark}
          compareMethod={DiffMethod.CHARS}
          leftTitle="Expected Output"
          rightTitle="Your Output"
          styles={{
            variables: {
              light: {
                diffViewerBackground: "#ffffff",
                diffViewerColor: "#2e2924",
                addedBackground: "#e6ffed",
                addedColor: "#24292e",
                removedBackground: "#ffeef0",
                removedColor: "#24292e",
                wordAddedBackground: "#acf2bd",
                wordRemovedBackground: "#fdb8c0",
                addedGutterBackground: "#cdffd8",
                removedGutterBackground: "#ffdce0",
                gutterBackground: "#f7f7f7",
                gutterBackgroundDark: "#f3f1f1",
                highlightBackground: "#fffbdd",
                highlightGutterBackground: "#fff5b1",
                emptyLineBackground: "#fafbfc",
              },
              dark: {
                diffViewerBackground: "#151411",
                diffViewerColor: "#f0ebe2",
                addedBackground: "#044B53",
                addedColor: "#c4bbae",
                removedBackground: "#632F34",
                removedColor: "#c4bbae",
                wordAddedBackground: "#055d67",
                wordRemovedBackground: "#7d3840",
                addedGutterBackground: "#034148",
                removedGutterBackground: "#482025",
                gutterBackground: "#1f1c18",
                gutterBackgroundDark: "#1a1815",
                highlightBackground: "#2a3967",
                highlightGutterBackground: "#2d4077",
                emptyLineBackground: "#11100e",
              },
            },
            diffContainer: {
              fontFamily: "monospace",
            },
          }}
        />
      </div>
    </div>
  );
}
