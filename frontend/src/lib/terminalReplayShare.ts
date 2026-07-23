/**
 * Shareable terminal replay deep links via URL hash.
 * Format: #replay=<base64url(JSON payload v1)>
 */
import type { ReplayCommand } from "../components/ui/TerminalReplay";

export const REPLAY_HASH_PREFIX = "replay=";
export const REPLAY_PAYLOAD_VERSION = 1 as const;

export type ReplaySharePayload = {
  v: typeof REPLAY_PAYLOAD_VERSION;
  name?: string;
  commands: Array<{
    command: string;
    output?: string;
    isError?: boolean;
  }>;
};

export type ParseReplayHashResult =
  | { ok: true; payload: ReplaySharePayload; commands: ReplayCommand[] }
  | { ok: false; error: string; commands: ReplayCommand[] };

const MAX_COMMANDS = 40;
const MAX_OUTPUT_CHARS = 800;
const MAX_COMMAND_CHARS = 200;

function toBase64Url(bytes: string): string {
  const b64 =
    typeof btoa === "function"
      ? btoa(bytes)
      : Buffer.from(bytes, "binary").toString("base64");
  return b64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function fromBase64Url(b64url: string): string {
  const padded = b64url.replace(/-/g, "+").replace(/_/g, "/");
  const pad =
    padded.length % 4 === 0 ? "" : "=".repeat(4 - (padded.length % 4));
  const b64 = padded + pad;
  if (typeof atob === "function") {
    return atob(b64);
  }
  return Buffer.from(b64, "base64").toString("binary");
}

/** UTF-8 safe encode for Unicode command/output text. */
export function encodeUtf8ToBase64Url(text: string): string {
  const bytes = new TextEncoder().encode(text);
  let binary = "";
  bytes.forEach((b) => {
    binary += String.fromCharCode(b);
  });
  return toBase64Url(binary);
}

export function decodeBase64UrlToUtf8(b64url: string): string {
  const binary = fromBase64Url(b64url);
  const bytes = Uint8Array.from(binary, (c) => c.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

export function sanitizeReplayCommands(
  commands: ReplayCommand[],
): ReplayCommand[] {
  return commands
    .filter((c) => typeof c.command === "string" && c.command.trim().length > 0)
    .slice(0, MAX_COMMANDS)
    .map((c) => ({
      command: c.command.trim().slice(0, MAX_COMMAND_CHARS),
      output: (c.output ?? "").slice(0, MAX_OUTPUT_CHARS),
      isError: !!c.isError,
      typingDelayMs: c.typingDelayMs,
      executionDelayMs: c.executionDelayMs,
    }));
}

export function buildReplayPayload(
  commands: ReplayCommand[],
  sessionName?: string,
): ReplaySharePayload {
  const cleaned = sanitizeReplayCommands(commands);
  return {
    v: REPLAY_PAYLOAD_VERSION,
    ...(sessionName?.trim() ? { name: sessionName.trim().slice(0, 80) } : {}),
    commands: cleaned.map((c) => ({
      command: c.command,
      ...(c.output ? { output: c.output } : {}),
      ...(c.isError ? { isError: true } : {}),
    })),
  };
}

export function encodeReplayHash(
  commands: ReplayCommand[],
  sessionName?: string,
): string {
  const payload = buildReplayPayload(commands, sessionName);
  if (payload.commands.length === 0) return "";
  return `${REPLAY_HASH_PREFIX}${encodeUtf8ToBase64Url(JSON.stringify(payload))}`;
}

/** Extract #replay=… segment from a hash string (with or without leading #). */
export function extractReplayHashSegment(hash: string): string | null {
  const raw = hash.startsWith("#") ? hash.slice(1) : hash;
  if (!raw) return null;

  // Support lone #replay=… or mixed hashes like #foo&replay=…
  const parts = raw.split("&");
  for (const part of parts) {
    if (part.startsWith(REPLAY_HASH_PREFIX)) {
      return part.slice(REPLAY_HASH_PREFIX.length);
    }
  }
  if (raw.startsWith(REPLAY_HASH_PREFIX)) {
    return raw.slice(REPLAY_HASH_PREFIX.length);
  }
  return null;
}

export function parseReplayHash(hash: string): ParseReplayHashResult {
  const empty: ReplayCommand[] = [];
  const segment = extractReplayHashSegment(hash);
  if (segment === null) {
    return { ok: false, error: "No replay hash present.", commands: empty };
  }
  if (!segment.trim()) {
    return { ok: false, error: "Replay hash is empty.", commands: empty };
  }

  try {
    const json = decodeBase64UrlToUtf8(segment);
    const data = JSON.parse(json) as Partial<ReplaySharePayload>;

    if (!data || data.v !== REPLAY_PAYLOAD_VERSION) {
      return {
        ok: false,
        error: "Unsupported or missing replay payload version.",
        commands: empty,
      };
    }
    if (!Array.isArray(data.commands) || data.commands.length === 0) {
      return {
        ok: false,
        error: "Replay payload has no commands.",
        commands: empty,
      };
    }

    const commands = sanitizeReplayCommands(
      data.commands.map((c) => ({
        command: String(c?.command ?? ""),
        output: typeof c?.output === "string" ? c.output : "",
        isError: !!c?.isError,
      })),
    );

    if (commands.length === 0) {
      return {
        ok: false,
        error: "Replay commands were invalid after sanitizing.",
        commands: empty,
      };
    }

    return {
      ok: true,
      payload: {
        v: REPLAY_PAYLOAD_VERSION,
        name: typeof data.name === "string" ? data.name : undefined,
        commands: commands.map((c) => ({
          command: c.command,
          output: c.output,
          isError: c.isError,
        })),
      },
      commands,
    };
  } catch {
    return {
      ok: false,
      error: "Could not decode replay hash. Link may be corrupted.",
      commands: empty,
    };
  }
}

export function buildReplayShareUrl(options: {
  commands: ReplayCommand[];
  sessionName?: string;
  /** Pathname only, e.g. /sandbox or /test-terminal */
  pathname?: string;
  origin?: string;
}): string | null {
  const hashBody = encodeReplayHash(options.commands, options.sessionName);
  if (!hashBody) return null;

  const origin =
    options.origin ??
    (typeof window !== "undefined" ? window.location.origin : "");
  const pathname =
    options.pathname ??
    (typeof window !== "undefined" ? window.location.pathname : "/sandbox");

  return `${origin}${pathname}#${hashBody}`;
}

/** Build ReplayCommand list from interactive GitTerminal line buffer. */
export function replayCommandsFromTerminalLines(
  lines: Array<{ kind: string; text: string }>,
): ReplayCommand[] {
  const result: ReplayCommand[] = [];
  let current: ReplayCommand | null = null;

  for (const line of lines) {
    if (line.kind === "command") {
      if (current) result.push(current);
      current = { command: line.text, output: "", isError: false };
      continue;
    }
    if (!current) continue;
    if (line.kind === "error") {
      current.isError = true;
    }
    current.output = current.output
      ? `${current.output}\n${line.text}`
      : line.text;
  }
  if (current) result.push(current);
  return sanitizeReplayCommands(result);
}

export const DEFAULT_SHARE_DEMO_COMMANDS: ReplayCommand[] = [
  {
    command: "git init",
    output: "Initialized empty Git repository in /workspace/.git/",
  },
  {
    command: "git status",
    output: "On branch main\n\nNo commits yet\n\nnothing to commit",
  },
  {
    command: "git add README.md",
    output: "",
  },
  {
    command: 'git commit -m "docs: add readme"',
    output: "[main (root-commit) a1b2c3d] docs: add readme\n 1 file changed",
  },
];
