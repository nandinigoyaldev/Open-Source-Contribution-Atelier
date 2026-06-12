import { FormEvent, useState } from "react";
import CopyButton from "./CopyButton";

type TerminalPanelProps = {
  expectedCommand?: string;
};

export function TerminalPanel({
  expectedCommand = "git status",
}: TerminalPanelProps) {
  const [command, setCommand] = useState("");
  const [feedback, setFeedback] = useState(
    "Try the safe Git practice sandbox.",
  );

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (command.trim() === expectedCommand) {
      setFeedback(
        "Correct command. Your submission would be verified by the backend sandbox.",
      );
      return;
    }
    setFeedback("That command does not match this exercise yet.");
  };

  return (
    <div className="rounded-[24px] border border-outline bg-surface-lowest/85 p-5 text-text shadow-card backdrop-blur-xl">
      <div className="mb-5 flex items-center justify-between border-b border-outline pb-3">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-primary">
            Terminal sandbox
          </p>
          <p className="mt-2 text-sm text-muted">
            Safe verifier for guided Git command practice.
          </p>
        </div>
        <div className="flex gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-tertiary/80" />
          <span className="h-2.5 w-2.5 rounded-full bg-primary-container/80" />
          <span className="h-2.5 w-2.5 rounded-full bg-primary/80" />
        </div>
      </div>
      <div className="rounded-2xl border-t border-primary/30 bg-surface px-4 py-4 font-mono text-sm text-muted">
        <div className="flex items-center justify-between">
          <p className="text-primary">atelier-admin:~$ {expectedCommand}</p>
          <CopyButton text={expectedCommand} />
        </div>

        <p className="mt-2">
          Sandbox ready. Type the expected Git command for this lesson.
        </p>
      </div>
      <form onSubmit={handleSubmit}>
        <label className="mt-4 flex items-center gap-3 rounded-2xl border border-primary/20 bg-surface px-4 py-3 shadow-inner">
          <span className="font-mono text-tertiary">$</span>
          <input
            aria-label="Terminal input"
            className="w-full bg-transparent font-mono text-text outline-none placeholder:text-muted"
            value={command}
            onChange={(event) => setCommand(event.target.value)}
            placeholder="type a git command"
          />
        </label>
        <div className="mt-4 flex gap-3">
          <button
            type="submit"
            className="rounded-xl bg-[linear-gradient(135deg,#4f46e5,#7c72ff)] px-4 py-2 text-sm font-semibold text-white shadow-card"
          >
            Verify Command
          </button>
          <button
            type="button"
            onClick={() => setCommand("git status")}
            className="rounded-xl border border-outline bg-surface-low px-4 py-2 text-sm font-semibold text-muted"
          >
            Autofill hint
          </button>
        </div>
      </form>
      <p className="mt-4 text-sm text-muted">{feedback}</p>
    </div>
  );
}
