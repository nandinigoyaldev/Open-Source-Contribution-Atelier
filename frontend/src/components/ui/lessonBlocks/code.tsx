import React from "react";
import CopyButton from "../CopyButton";
import { ArchitectureViewer } from "../../docs/ArchitectureViewer";
import type { LessonBlockHandler } from "./types";

/** Fenced code: ```lang ... ```. `mermaid` fences render as a diagram. */
export const codeFenceBlock: LessonBlockHandler = {
  id: "code-fence",
  priority: 200,
  render: ({ lines, line, index }) => {
    if (!line.trim().startsWith("```")) return null;

    const langMatch = line.trim().match(/^```([a-zA-Z0-9_-]+)/);
    const lang = langMatch ? langMatch[1].toLowerCase() : "";

    let codeContent = "";
    let next = index + 1;
    while (next < lines.length && !lines[next].trim().startsWith("```")) {
      codeContent += lines[next] + "\n";
      next++;
    }
    next++; // skip closing ```

    if (lang === "mermaid") {
      return {
        node: <ArchitectureViewer chart={codeContent.trim()} />,
        next,
      };
    }

    const displayLang = lang ? lang.toUpperCase() : "CODE";
    return {
      node: (
        <div className="relative my-4 group rounded-2xl border-4 border-black dark:border-[#2e2924] bg-[#1a1510] overflow-hidden shadow-card-sm transition-all hover:shadow-card">
          {/* Header bar with language badge and Copy code button */}
          <div className="flex items-center justify-between px-4 py-2.5 bg-[#120f0b] border-b-2 border-black/40 dark:border-[#2e2924]">
            <div className="flex items-center gap-2">
              <span className="inline-block w-2.5 h-2.5 rounded-full bg-[#ffcc00]/80 border border-black/40" />
              <span className="font-mono text-[11px] font-black tracking-wider text-[#ffebc2]/90 bg-black/50 px-2.5 py-0.5 rounded border border-white/10">
                {displayLang}
              </span>
            </div>
            <div data-testid="code-block-copy-wrapper">
              <CopyButton
                text={codeContent.trim()}
                label="Copy code"
                copiedLabel="Copied code!"
              />
            </div>
          </div>

          <pre className="w-full overflow-x-auto p-4 text-[#ffebc2] font-mono text-sm leading-relaxed">
            <code className="block whitespace-pre">{codeContent.trim()}</code>
          </pre>
        </div>
      ),
      next,
    };
  },
};
