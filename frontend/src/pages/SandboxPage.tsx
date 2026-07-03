import React from "react";
import { ProjectWorkspace } from "../components/ui/ProjectWorkspace";

export function SandboxPage() {
  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6 flex flex-col h-[calc(100vh-64px)]">
      <div>
        <h1 className="text-3xl font-black text-text dark:text-[#f0ebe2]">
          Interactive Workspace
        </h1>
        <p className="mt-2 text-muted dark:text-[#c4bbae]">
          Write and organize multi-file projects safely in the browser.
        </p>
      </div>
      <div className="flex-1 min-h-[500px]">
        <ProjectWorkspace />
      </div>
    </div>
  );
}
