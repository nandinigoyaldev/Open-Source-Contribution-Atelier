import React, { useState } from "react";
import { ProjectWorkspace } from "../components/ui/ProjectWorkspace";
import { OnboardingTour } from "../components/ui/OnboardingTour";
import { Map } from "lucide-react";
import { Step } from "react-joyride";

export function SandboxPage() {
  const [runTour, setRunTour] = useState(false);

  const sandboxSteps: Step[] = [
    {
      target: "#tour-sandbox-explorer",
      title: "Project Explorer 📁",
      content:
        "Create, rename, and organize your files and folders here. Navigate through your project seamlessly.",
      placement: "right",
      skipBeacon: true,
    },
    {
      target: "#tour-sandbox-search",
      title: "Search Panel 🔍",
      content:
        "Quickly search for keywords and find exactly what you need across all your files.",
      placement: "right",
    },
    {
      target: "#tour-sandbox-editor",
      title: "Code Editor ✍️",
      content:
        "Write your code with full syntax highlighting, error checking, and auto-completion built right in.",
      placement: "left",
    },
    {
      target: "#tour-sandbox-tools",
      title: "Workspace Tools 🛠️",
      content:
        "Export your project, save snippets for later, or manage snapshots to revert changes easily.",
      placement: "bottom",
    },
    {
      target: "#tour-sandbox-terminal",
      title: "Interactive Terminal 💻",
      content:
        "Run bash commands, compile code, test applications, or interact with Git right from the browser.",
      placement: "top",
    },
  ];

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6 flex flex-col h-[calc(100vh-64px)]">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-black text-text dark:text-[#f0ebe2]">
            Interactive Workspace
          </h1>
          <p className="mt-2 text-muted dark:text-[#c4bbae]">
            Write and organize multi-file projects safely in the browser.
          </p>
        </div>
        <button
          onClick={() => setRunTour(true)}
          className="flex items-center gap-2 px-4 py-2 font-bold text-sm bg-surface dark:bg-[#1a1a1a] border-2 border-black dark:border-[#2e2924] rounded-xl shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:-translate-y-0.5 transition-all"
        >
          <Map className="w-4 h-4 text-primary" />
          Take a Tour
        </button>
      </div>
      <div className="flex-1 min-h-[500px]">
        <ProjectWorkspace />
      </div>

      <OnboardingTour
        run={runTour}
        onFinish={() => setRunTour(false)}
        steps={sandboxSteps}
      />
    </div>
  );
}

export default SandboxPage;
