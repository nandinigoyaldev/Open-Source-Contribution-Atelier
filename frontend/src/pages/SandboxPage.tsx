import React, { useState } from "react";
import { ProjectWorkspace } from "../components/ui/ProjectWorkspace";
import { OnboardingTour } from "../components/ui/OnboardingTour";
import { TerminalReplay } from "../components/ui/TerminalReplay";
import { Map, Link2, AlertCircle, X } from "lucide-react";
import { Step } from "react-joyride";
import { useTerminalReplayFromHash } from "../hooks/useTerminalReplayFromHash";
import {
  DEFAULT_SHARE_DEMO_COMMANDS,
  buildReplayShareUrl,
  encodeReplayHash,
} from "../lib/terminalReplayShare";

export function SandboxPage() {
  const [runTour, setRunTour] = useState(false);
  const [demoCopied, setDemoCopied] = useState(false);
  const { commands, sessionName, hasReplayHash, error, reloadFromHash } =
    useTerminalReplayFromHash();

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

  const loadDemoReplay = () => {
    const hash = encodeReplayHash(
      DEFAULT_SHARE_DEMO_COMMANDS,
      "Mentor demo replay",
    );
    if (hash) {
      window.location.hash = hash;
    }
  };

  const copyDemoLink = async () => {
    const url = buildReplayShareUrl({
      commands: DEFAULT_SHARE_DEMO_COMMANDS,
      sessionName: "Mentor demo replay",
      pathname: "/sandbox",
    });
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      setDemoCopied(true);
      setTimeout(() => setDemoCopied(false), 2000);
    } catch {
      window.location.hash = url.slice(url.indexOf("#") + 1);
    }
  };

  const clearReplayHash = () => {
    const { pathname, search } = window.location;
    window.history.replaceState(null, "", `${pathname}${search}`);
    reloadFromHash();
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6 flex flex-col h-[calc(100vh-64px)]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-black text-text dark:text-[#f0ebe2]">
            Interactive Workspace
          </h1>
          <p className="mt-2 text-muted dark:text-[#c4bbae]">
            Write and organize multi-file projects safely in the browser. Share
            terminal replays via URL hash for mentors and PR demos.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => void copyDemoLink()}
            className="flex items-center gap-2 px-4 py-2 font-bold text-sm bg-primary border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:-translate-y-0.5 transition-all"
          >
            <Link2 className="w-4 h-4" />
            {demoCopied ? "Link copied" : "Copy demo replay link"}
          </button>
          <button
            type="button"
            onClick={loadDemoReplay}
            className="flex items-center gap-2 px-4 py-2 font-bold text-sm bg-surface dark:bg-[#1a1a1a] border-2 border-black dark:border-[#2e2924] rounded-xl shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:-translate-y-0.5 transition-all"
          >
            Load demo replay
          </button>
          <button
            onClick={() => setRunTour(true)}
            className="flex items-center gap-2 px-4 py-2 font-bold text-sm bg-surface dark:bg-[#1a1a1a] border-2 border-black dark:border-[#2e2924] rounded-xl shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:-translate-y-0.5 transition-all"
          >
            <Map className="w-4 h-4 text-primary" />
            Take a Tour
          </button>
        </div>
      </div>

      {hasReplayHash && error && (
        <div
          role="alert"
          className="flex items-start gap-3 rounded-2xl border-4 border-dashed border-amber-500 bg-amber-50 p-4 dark:bg-amber-950/20"
        >
          <AlertCircle
            className="h-5 w-5 shrink-0 text-amber-700"
            aria-hidden
          />
          <div className="flex-1">
            <p className="font-black text-amber-900 dark:text-amber-200">
              Couldn’t load shared replay
            </p>
            <p className="text-sm font-bold text-amber-800/90 dark:text-amber-300">
              {error}
            </p>
          </div>
          <button
            type="button"
            onClick={clearReplayHash}
            className="rounded-lg border-2 border-black p-1"
            aria-label="Dismiss replay error"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {hasReplayHash && !error && commands.length > 0 && (
        <section
          className="h-[320px] shrink-0"
          data-testid="sandbox-shared-replay"
        >
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-black uppercase tracking-wide dark:text-[#f0ebe2]">
              Shared terminal replay
            </h2>
            <button
              type="button"
              onClick={clearReplayHash}
              className="text-xs font-bold underline underline-offset-2 text-muted"
            >
              Close replay
            </button>
          </div>
          <TerminalReplay
            key={sessionName + commands.map((c) => c.command).join("|")}
            sessionName={sessionName}
            commands={commands}
            sharePathname="/sandbox"
          />
        </section>
      )}

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
