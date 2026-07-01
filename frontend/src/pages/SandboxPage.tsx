import React from "react";
import { CodeSandbox } from "../components/ui/CodeSandbox";

export function SandboxPage() {
  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-black text-text dark:text-[#f0ebe2]">
          Interactive Sandbox
        </h1>
        <p className="mt-2 text-muted dark:text-[#c4bbae]">
          Write and execute code safely in the browser. Test logic before
          integrating it into your workflow.
        </p>
      </div>
      <div className="h-[600px]">
        <CodeSandbox />
      </div>
    </div>
  );
}
