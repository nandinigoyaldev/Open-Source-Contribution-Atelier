import React, { useState } from "react";
import ReactDiffViewer, { DiffMethod } from "react-diff-viewer-continued";
import { Columns, List, FileCode2 } from "lucide-react";
import { useTheme } from "../../hooks/useTheme";

interface CodeDiffViewerProps {
  originalCode: string;
  modifiedCode: string;
  title?: string;
  fileName?: string;
}

export function CodeDiffViewer({
  originalCode,
  modifiedCode,
  title = "Source Code Changes",
  fileName = "submission.code",
}: CodeDiffViewerProps) {
  const { theme } = useTheme();
  const isDark = theme === "dark";
  const [splitView, setSplitView] = useState(true);

  return (
    <div className="flex flex-col gap-2 w-full border-2 border-black dark:border-[#2e2924] rounded-xl overflow-hidden bg-surface dark:bg-[#151411]">
      <div className="flex items-center justify-between p-3 border-b-2 border-black dark:border-[#2e2924] bg-surface-low dark:bg-[#1f1c18]">
        <div className="flex items-center gap-2">
          <FileCode2 size={16} className="text-primary" />
          <h3 className="font-bold text-sm text-text dark:text-[#f0ebe2]">
            {title}{" "}
            <span className="opacity-50 text-xs ml-2 font-mono">
              {fileName}
            </span>
          </h3>
        </div>

        <div className="flex bg-black/10 dark:bg-white/10 p-1 rounded-lg">
          <button
            onClick={() => setSplitView(true)}
            className={`p-1 rounded ${
              splitView
                ? "bg-white dark:bg-[#2e2924] shadow-sm text-primary"
                : "text-muted hover:text-text"
            }`}
            title="Split View"
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
            title="Unified View"
          >
            <List size={16} />
          </button>
        </div>
      </div>
      <div className="overflow-x-auto text-sm">
        <ReactDiffViewer
          oldValue={originalCode}
          newValue={modifiedCode}
          splitView={splitView}
          useDarkTheme={isDark}
          compareMethod={DiffMethod.WORDS}
          leftTitle="Original Code"
          rightTitle="Modified Code"
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
              fontFamily:
                "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
            },
            marker: {
              width: "25px",
            },
          }}
        />
      </div>
    </div>
  );
}
