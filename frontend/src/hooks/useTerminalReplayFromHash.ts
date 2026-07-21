import { useEffect, useState } from "react";
import type { ReplayCommand } from "../components/ui/TerminalReplay";
import {
  parseReplayHash,
  type ParseReplayHashResult,
} from "../lib/terminalReplayShare";

export type UseTerminalReplayFromHashResult = {
  commands: ReplayCommand[];
  sessionName: string;
  hasReplayHash: boolean;
  error: string | null;
  reloadFromHash: () => void;
};

function readHashState(): {
  commands: ReplayCommand[];
  sessionName: string;
  hasReplayHash: boolean;
  error: string | null;
} {
  if (typeof window === "undefined") {
    return {
      commands: [],
      sessionName: "Shared Replay",
      hasReplayHash: false,
      error: null,
    };
  }

  const hash = window.location.hash;
  const hasReplayHash = hash.includes("replay=");
  if (!hasReplayHash) {
    return {
      commands: [],
      sessionName: "Shared Replay",
      hasReplayHash: false,
      error: null,
    };
  }

  const parsed: ParseReplayHashResult = parseReplayHash(hash);
  if (!parsed.ok) {
    return {
      commands: [],
      sessionName: "Shared Replay",
      hasReplayHash: true,
      error: parsed.error,
    };
  }

  return {
    commands: parsed.commands,
    sessionName: parsed.payload.name || "Shared Replay",
    hasReplayHash: true,
    error: null,
  };
}

/** Subscribe to URL hash and expose decoded replay commands. */
export function useTerminalReplayFromHash(): UseTerminalReplayFromHashResult {
  const [state, setState] = useState(readHashState);

  const reloadFromHash = () => setState(readHashState());

  useEffect(() => {
    const onHash = () => setState(readHashState());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  return { ...state, reloadFromHash };
}
