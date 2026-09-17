import { useState, useMemo, useCallback, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ChevronRight,
  ChevronDown,
  Copy,
  Check,
  Search,
  Webhook,
  GitBranch,
  GitPullRequest,
  CircleDot,
  Star,
  X,
  Info,
  Shield,
  Hash,
  FileJson,
} from "lucide-react";

/* ------------------------------------------------------------------ */
/* Sample Payloads                                                      */
/* ------------------------------------------------------------------ */

const PUSH_EVENT_PAYLOAD = {
  ref: "refs/heads/main",
  before: "6113728f27ae82c7b1a177c8d03f9e96e0adf246",
  after: "a10867b14bb761a232cd80139fbd4c0d33264240",
  repository: {
    id: 123456789,
    name: "open-source-contribution-atelier",
    full_name: "octocat/open-source-contribution-atelier",
    private: false,
    owner: {
      login: "octocat",
      id: 1,
      avatar_url: "https://avatars.githubusercontent.com/u/1?v=4",
      type: "User",
    },
    html_url: "https://github.com/octocat/open-source-contribution-atelier",
    description: "An interactive open-source learning platform",
    fork: false,
    created_at: "2024-01-15T08:30:00Z",
    updated_at: "2026-07-27T10:15:00Z",
    default_branch: "main",
    stargazers_count: 1542,
    language: "TypeScript",
  },
  pusher: {
    name: "octocat",
    email: "octocat@github.com",
  },
  sender: {
    login: "octocat",
    id: 1,
    avatar_url: "https://avatars.githubusercontent.com/u/1?v=4",
    type: "User",
  },
  commits: [
    {
      id: "a10867b14bb761a232cd80139fbd4c0d33264240",
      message: "fix: resolve webhook payload validation edge case",
      timestamp: "2026-07-27T10:14:50Z",
      author: {
        name: "The Octocat",
        email: "octocat@github.com",
        username: "octocat",
      },
      added: ["src/utils/webhook-validator.ts"],
      removed: [],
      modified: ["src/handlers/push.ts", "tests/push.test.ts"],
    },
  ],
  head_commit: {
    id: "a10867b14bb761a232cd80139fbd4c0d33264240",
    message: "fix: resolve webhook payload validation edge case",
    timestamp: "2026-07-27T10:14:50Z",
    author: {
      name: "The Octocat",
      email: "octocat@github.com",
      username: "octocat",
    },
  },
};

const PULL_REQUEST_EVENT_PAYLOAD = {
  action: "opened",
  number: 42,
  pull_request: {
    id: 987654321,
    number: 42,
    state: "open",
    title: "feat: add interactive webhook payload inspector",
    body: "This PR adds a new interactive component for viewing webhook payloads with syntax highlighting and collapsible JSON trees.",
    user: {
      login: "contributor-dev",
      id: 42,
      avatar_url: "https://avatars.githubusercontent.com/u/42?v=4",
      type: "User",
    },
    created_at: "2026-07-27T09:00:00Z",
    updated_at: "2026-07-27T09:30:00Z",
    head: {
      ref: "feat/webhook-inspector",
      sha: "abc123def456789",
      repo: {
        full_name: "contributor-dev/open-source-contribution-atelier",
      },
    },
    base: {
      ref: "main",
      sha: "def789abc123456",
      repo: {
        full_name: "octocat/open-source-contribution-atelier",
      },
    },
    merged: false,
    mergeable: true,
    draft: false,
    additions: 350,
    deletions: 12,
    changed_files: 4,
    labels: [
      { id: 1, name: "enhancement", color: "a2eeef" },
      { id: 2, name: "documentation", color: "0075ca" },
    ],
    requested_reviewers: [
      {
        login: "maintainer-one",
        id: 100,
        type: "User",
      },
    ],
  },
  repository: {
    id: 123456789,
    name: "open-source-contribution-atelier",
    full_name: "octocat/open-source-contribution-atelier",
    private: false,
    owner: {
      login: "octocat",
      id: 1,
      type: "User",
    },
  },
  sender: {
    login: "contributor-dev",
    id: 42,
    type: "User",
  },
};

const ISSUES_EVENT_PAYLOAD = {
  action: "opened",
  issue: {
    id: 111222333,
    number: 2182,
    title: "[DOCS-FEATURE] Build Interactive WebHook Event Payload Inspector",
    state: "open",
    body: "Build an interactive webhook payload viewer for the developer documentation page that simulates GitHub webhook events with syntax-highlighted JSON trees.",
    user: {
      login: "issue-reporter",
      id: 55,
      avatar_url: "https://avatars.githubusercontent.com/u/55?v=4",
      type: "User",
    },
    labels: [
      { id: 10, name: "enhancement", color: "a2eeef" },
      { id: 11, name: "good first issue", color: "7057ff" },
      { id: 12, name: "documentation", color: "0075ca" },
      { id: 13, name: "frontend", color: "d4c5f9" },
    ],
    assignees: [],
    milestone: null,
    created_at: "2026-07-27T08:00:00Z",
    updated_at: "2026-07-27T08:00:00Z",
    comments: 0,
    reactions: {
      "+1": 3,
      "-1": 0,
      laugh: 0,
      hooray: 1,
      heart: 2,
      rocket: 1,
      eyes: 0,
    },
  },
  repository: {
    id: 123456789,
    name: "open-source-contribution-atelier",
    full_name: "octocat/open-source-contribution-atelier",
    private: false,
  },
  sender: {
    login: "issue-reporter",
    id: 55,
    type: "User",
  },
};

const STAR_EVENT_PAYLOAD = {
  action: "created",
  starred_at: "2026-07-27T12:00:00Z",
  repository: {
    id: 123456789,
    name: "open-source-contribution-atelier",
    full_name: "octocat/open-source-contribution-atelier",
    private: false,
    owner: {
      login: "octocat",
      id: 1,
      type: "User",
    },
    stargazers_count: 1543,
    description: "An interactive open-source learning platform",
  },
  sender: {
    login: "star-gazer",
    id: 999,
    avatar_url: "https://avatars.githubusercontent.com/u/999?v=4",
    type: "User",
  },
};

/* ------------------------------------------------------------------ */
/* Event Registry                                                       */
/* ------------------------------------------------------------------ */

type WebhookEvent = {
  id: string;
  name: string;
  icon: React.ReactNode;
  description: string;
  headerEvent: string;
  payload: Record<string, unknown>;
  deliveryId: string;
  signature: string;
};

const WEBHOOK_EVENTS: WebhookEvent[] = [
  {
    id: "push",
    name: "PushEvent",
    icon: <GitBranch size={16} />,
    description: "Triggered when a push is made to a repository branch.",
    headerEvent: "push",
    payload: PUSH_EVENT_PAYLOAD,
    deliveryId: "d6fbc8a0-1e2f-11ee-be56-0242ac120002",
    signature:
      "sha256=4c1a03aba4db4ee6e2f8c1b2f27e1c5d8a7f3e9b2d4a6c8e0f1a3b5c7d9e1f2a",
  },
  {
    id: "pull_request",
    name: "PullRequestEvent",
    icon: <GitPullRequest size={16} />,
    description:
      "Triggered when a pull request is opened, closed, or synchronized.",
    headerEvent: "pull_request",
    payload: PULL_REQUEST_EVENT_PAYLOAD,
    deliveryId: "e7a8b9c0-2f3a-22ff-cf67-1353bd231113",
    signature:
      "sha256=5d2b14bcb5ec5ff7f3a9d2c3a38f2d6e9b8a4f0c3e5b7d9f1a3c5e7b9d1f3a5c",
  },
  {
    id: "issues",
    name: "IssuesEvent",
    icon: <CircleDot size={16} />,
    description:
      "Triggered when an issue is opened, edited, closed, or labeled.",
    headerEvent: "issues",
    payload: ISSUES_EVENT_PAYLOAD,
    deliveryId: "f8b9c0d1-3a4b-33aa-da78-2464ce342224",
    signature:
      "sha256=6e3c25cdc6fd6aa8a4ba0e3d4b4a3e7fab9b5a1d4f6c8e0a2b4d6f8a0c2e4a6d",
  },
  {
    id: "star",
    name: "StarEvent",
    icon: <Star size={16} />,
    description: "Triggered when a repository is starred or unstarred.",
    headerEvent: "star",
    payload: STAR_EVENT_PAYLOAD,
    deliveryId: "a9c0d1e2-4b5c-44bb-eb89-3575df453335",
    signature:
      "sha256=7f4d36ded7ae7bb9b5cb1f4e5c5b4f8abc0c6b2e5a7d9f1b3c5e7a9b1d3f5b7e",
  },
];

/* ------------------------------------------------------------------ */
/* Utility: syntax-highlight a JSON value for inline rendering          */
/* ------------------------------------------------------------------ */

function getValueColor(value: unknown): string {
  if (value === null) return "text-orange-400";
  if (typeof value === "boolean") return "text-purple-400";
  if (typeof value === "number") return "text-cyan-400";
  if (typeof value === "string") return "text-emerald-400";
  return "text-slate-300";
}

function formatValue(value: unknown): string {
  if (value === null) return "null";
  if (typeof value === "string") return `"${value}"`;
  return String(value);
}

/* ------------------------------------------------------------------ */
/* Collapsible JSON Tree Node                                           */
/* ------------------------------------------------------------------ */

type JsonNodeProps = {
  keyName: string | null;
  value: unknown;
  depth: number;
  searchTerm: string;
  defaultExpanded?: boolean;
  isLast?: boolean;
  expandAllSignal?: number;
  collapseAllSignal?: number;
};

function matchesSearch(
  key: string | null,
  value: unknown,
  term: string,
): boolean {
  if (!term) return false;
  const lower = term.toLowerCase();
  if (key && key.toLowerCase().includes(lower)) return true;
  if (
    value !== null &&
    typeof value !== "object" &&
    String(value).toLowerCase().includes(lower)
  )
    return true;
  return false;
}

function hasDescendantMatch(value: unknown, term: string): boolean {
  if (!term) return false;
  if (value === null || typeof value !== "object") return false;
  const entries = Array.isArray(value)
    ? value.map((v, i) => [String(i), v] as const)
    : Object.entries(value as Record<string, unknown>);
  return entries.some(
    ([k, v]) => matchesSearch(k, v, term) || hasDescendantMatch(v, term),
  );
}

function JsonNode({
  keyName,
  value,
  depth,
  searchTerm,
  defaultExpanded = true,
  isLast = true,
  expandAllSignal = 0,
  collapseAllSignal = 0,
}: JsonNodeProps) {
  const isObject =
    value !== null && typeof value === "object" && !Array.isArray(value);
  const isArray = Array.isArray(value);
  const isExpandable = isObject || isArray;

  const descendantMatches =
    isExpandable && hasDescendantMatch(value, searchTerm);
  const shouldAutoExpand =
    defaultExpanded || (searchTerm !== "" && descendantMatches);

  const [isExpanded, setIsExpanded] = useState(shouldAutoExpand);

  useEffect(() => {
    if (searchTerm && descendantMatches) {
      setIsExpanded(true);
    }
  }, [searchTerm, descendantMatches]);

  useEffect(() => {
    if (expandAllSignal > 0) {
      setIsExpanded(true);
    }
  }, [expandAllSignal]);

  useEffect(() => {
    if (collapseAllSignal > 0) {
      setIsExpanded(false);
    }
  }, [collapseAllSignal]);

  const highlighted = matchesSearch(keyName, value, searchTerm);

  if (!isExpandable) {
    return (
      <div
        className={`flex items-baseline gap-1 py-0.5 font-mono text-[13px] leading-relaxed transition-colors ${
          highlighted ? "rounded bg-amber-400/20 ring-1 ring-amber-400/40" : ""
        }`}
        style={{ paddingLeft: `${depth * 20}px` }}
      >
        {keyName !== null && (
          <>
            <span className="text-violet-300">&quot;{keyName}&quot;</span>
            <span className="text-slate-500">:</span>{" "}
          </>
        )}
        <span className={getValueColor(value)}>{formatValue(value)}</span>
        {!isLast && <span className="text-slate-500">,</span>}
      </div>
    );
  }

  const entries = isArray
    ? (value as unknown[]).map((v, i) => [String(i), v] as const)
    : Object.entries(value as Record<string, unknown>);

  const bracketOpen = isArray ? "[" : "{";
  const bracketClose = isArray ? "]" : "}";

  return (
    <div>
      <button
        type="button"
        onClick={() => setIsExpanded((prev) => !prev)}
        className={`flex w-full cursor-pointer items-baseline gap-1 rounded py-0.5 text-left font-mono text-[13px] leading-relaxed transition-all hover:bg-white/5 ${
          highlighted ? "bg-amber-400/20 ring-1 ring-amber-400/40" : ""
        }`}
        style={{ paddingLeft: `${depth * 20}px` }}
        aria-expanded={isExpanded}
        aria-label={`${isExpanded ? "Collapse" : "Expand"} ${keyName ?? (isArray ? "array" : "object")}`}
      >
        <span className="inline-flex w-4 shrink-0 items-center justify-center text-slate-400">
          {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        </span>
        {keyName !== null && (
          <>
            <span className="text-violet-300">&quot;{keyName}&quot;</span>
            <span className="text-slate-500">:</span>{" "}
          </>
        )}
        <span className="text-slate-400">{bracketOpen}</span>
        {!isExpanded && (
          <>
            <span className="text-slate-500">
              {" "}
              {entries.length} {entries.length === 1 ? "item" : "items"}{" "}
            </span>
            <span className="text-slate-400">{bracketClose}</span>
            {!isLast && <span className="text-slate-500">,</span>}
          </>
        )}
      </button>

      <AnimatePresence initial={false}>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            {entries.map(([k, v], idx) => (
              <JsonNode
                key={k}
                keyName={isArray ? null : k}
                value={v}
                depth={depth + 1}
                searchTerm={searchTerm}
                defaultExpanded={depth < 1}
                isLast={idx === entries.length - 1}
                expandAllSignal={expandAllSignal}
                collapseAllSignal={collapseAllSignal}
              />
            ))}
            <div
              className="py-0.5 font-mono text-[13px] text-slate-400"
              style={{ paddingLeft: `${depth * 20}px` }}
            >
              {bracketClose}
              {!isLast && <span className="text-slate-500">,</span>}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Header Validation Panel                                              */
/* ------------------------------------------------------------------ */

function HeaderValidation({ event }: { event: WebhookEvent }) {
  const headers = [
    {
      name: "X-GitHub-Event",
      value: event.headerEvent,
      valid: true,
      description: "Name of the event that triggered the delivery.",
    },
    {
      name: "X-GitHub-Delivery",
      value: event.deliveryId,
      valid: true,
      description: "A GUID to identify the delivery.",
    },
    {
      name: "X-Hub-Signature-256",
      value: event.signature,
      valid: true,
      description: "HMAC hex digest of the payload (SHA-256).",
    },
    {
      name: "Content-Type",
      value: "application/json",
      valid: true,
      description: "The media type of the payload body.",
    },
    {
      name: "User-Agent",
      value: "GitHub-Hookshot/abc1234",
      valid: true,
      description: "Identifies the request as coming from GitHub.",
    },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: 0.1 }}
      className="space-y-2"
    >
      <div className="flex items-center gap-2 text-sm font-semibold text-slate-300">
        <Shield size={14} className="text-emerald-400" />
        <span>Request Headers</span>
      </div>
      <div className="space-y-1.5">
        {headers.map((header) => (
          <div
            key={header.name}
            className="group flex items-start gap-2 rounded-lg bg-white/[0.03] px-3 py-2 transition-colors hover:bg-white/[0.06]"
          >
            <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center">
              {header.valid ? (
                <Check size={12} className="text-emerald-400" />
              ) : (
                <X size={12} className="text-red-400" />
              )}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline gap-x-2 font-mono text-xs">
                <span className="font-semibold text-violet-300">
                  {header.name}
                </span>
                <span className="text-slate-500">:</span>
                <span className="break-all text-emerald-300/80">
                  {header.value}
                </span>
              </div>
              <p className="mt-0.5 text-[11px] text-slate-500 opacity-0 transition-opacity group-hover:opacity-100">
                {header.description}
              </p>
            </div>
          </div>
        ))}
      </div>
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/* Main Component                                                       */
/* ------------------------------------------------------------------ */

export function WebhookInspector() {
  const [selectedEventId, setSelectedEventId] = useState(WEBHOOK_EVENTS[0].id);
  const [searchTerm, setSearchTerm] = useState("");
  const [copied, setCopied] = useState(false);
  const [showHeaders, setShowHeaders] = useState(true);
  const [expandAllSignal, setExpandAllSignal] = useState(0);
  const [collapseAllSignal, setCollapseAllSignal] = useState(0);
  const searchRef = useRef<HTMLInputElement>(null);

  const selectedEvent = useMemo(
    () => WEBHOOK_EVENTS.find((e) => e.id === selectedEventId)!,
    [selectedEventId],
  );

  const payloadString = useMemo(
    () => JSON.stringify(selectedEvent.payload, null, 2),
    [selectedEvent],
  );

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(payloadString);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for browsers without clipboard API
      const textarea = document.createElement("textarea");
      textarea.value = payloadString;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [payloadString]);

  const handleEventChange = useCallback((eventId: string) => {
    setSelectedEventId(eventId);
    setSearchTerm("");
    setCopied(false);
  }, []);

  return (
    <section
      id="webhook-inspector"
      className="mx-auto w-full max-w-5xl space-y-6"
    >
      {/* ---- Header ---- */}
      <motion.div
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="space-y-2"
      >
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-500 shadow-lg shadow-violet-500/25">
            <Webhook size={20} className="text-white" />
          </div>
          <div>
            <h2 className="text-2xl font-bold tracking-tight text-slate-100">
              Webhook Event Payload Inspector
            </h2>
            <p className="text-sm text-slate-400">
              Explore simulated GitHub webhook payloads with an interactive JSON
              tree viewer.
            </p>
          </div>
        </div>
      </motion.div>

      {/* ---- Controls Bar ---- */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.1 }}
        className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
      >
        {/* Event Selector (Dropdown & Tabs) */}
        <div className="flex flex-col gap-2.5 sm:flex-row sm:items-center">
          <div className="flex items-center gap-2">
            <label
              htmlFor="webhook-event-select"
              className="text-xs font-semibold text-slate-400"
            >
              Event Type:
            </label>
            <select
              id="webhook-event-select"
              aria-label="Select event type"
              value={selectedEventId}
              onChange={(e) => handleEventChange(e.target.value)}
              className="rounded-lg border border-white/10 bg-slate-900/90 px-3 py-1.5 text-xs font-semibold text-violet-300 shadow-sm outline-none transition-colors focus:border-violet-500 focus:ring-1 focus:ring-violet-500"
            >
              {WEBHOOK_EVENTS.map((event) => (
                <option
                  key={event.id}
                  value={event.id}
                  className="bg-slate-900 text-slate-200"
                >
                  {event.name}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-wrap items-center gap-1.5">
            {WEBHOOK_EVENTS.map((event) => {
              const isActive = event.id === selectedEventId;
              return (
                <button
                  key={event.id}
                  type="button"
                  onClick={() => handleEventChange(event.id)}
                  className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
                    isActive
                      ? "bg-violet-500/20 text-violet-300 shadow-inner shadow-violet-500/10 ring-1 ring-violet-500/30"
                      : "text-slate-400 hover:bg-white/5 hover:text-slate-300"
                  }`}
                  aria-pressed={isActive}
                  title={event.description}
                >
                  {event.icon}
                  <span className="hidden sm:inline">{event.name}</span>
                  <span className="sm:hidden">{event.id}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowHeaders((prev) => !prev)}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium transition-all ${
              showHeaders
                ? "bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/30"
                : "text-slate-400 hover:bg-white/5 hover:text-slate-300"
            }`}
            aria-pressed={showHeaders}
          >
            <Info size={14} />
            Headers
          </button>

          <button
            type="button"
            onClick={handleCopy}
            className="inline-flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-violet-600 to-fuchsia-600 px-4 py-2 text-xs font-semibold text-white shadow-md shadow-violet-500/20 transition-all hover:shadow-lg hover:shadow-violet-500/30 active:scale-[0.97]"
            aria-label="Copy sample payload to clipboard"
          >
            <AnimatePresence mode="wait">
              {copied ? (
                <motion.span
                  key="check"
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  exit={{ scale: 0 }}
                  className="inline-flex items-center gap-1.5"
                >
                  <Check size={14} />
                  Copied!
                </motion.span>
              ) : (
                <motion.span
                  key="copy"
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  exit={{ scale: 0 }}
                  className="inline-flex items-center gap-1.5"
                >
                  <Copy size={14} />
                  Copy Payload
                </motion.span>
              )}
            </AnimatePresence>
          </button>
        </div>
      </motion.div>

      {/* ---- Event Description ---- */}
      <motion.div
        key={selectedEvent.id}
        initial={{ opacity: 0, x: -8 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.25 }}
        className="flex items-start gap-2 rounded-lg border border-violet-500/10 bg-violet-500/5 px-4 py-3"
      >
        <Info size={14} className="mt-0.5 shrink-0 text-violet-400" />
        <div className="text-sm">
          <span className="font-semibold text-violet-300">
            {selectedEvent.name}
          </span>
          <span className="text-slate-400"> — {selectedEvent.description}</span>
        </div>
      </motion.div>

      {/* ---- Main Panel ---- */}
      <div className="overflow-hidden rounded-2xl border border-white/[0.08] bg-[#0d1117] shadow-2xl shadow-black/40">
        {/* Panel Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/[0.06] bg-white/[0.02] px-4 py-2.5">
          <div className="flex items-center gap-2">
            <div className="flex gap-1.5">
              <div className="h-3 w-3 rounded-full bg-red-500/60" />
              <div className="h-3 w-3 rounded-full bg-amber-500/60" />
              <div className="h-3 w-3 rounded-full bg-emerald-500/60" />
            </div>
            <div className="ml-2 flex items-center gap-1.5 text-xs text-slate-500">
              <FileJson size={12} />
              <span>{selectedEvent.headerEvent}.json</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Expansion Controls */}
            <div className="flex items-center gap-1.5 text-xs text-slate-400">
              <button
                type="button"
                onClick={() => setExpandAllSignal((prev) => prev + 1)}
                className="rounded px-2 py-0.5 hover:bg-white/5 hover:text-slate-200 transition-colors"
                title="Expand all JSON nodes"
                aria-label="Expand all nodes"
              >
                Expand All
              </button>
              <span className="text-slate-600">|</span>
              <button
                type="button"
                onClick={() => setCollapseAllSignal((prev) => prev + 1)}
                className="rounded px-2 py-0.5 hover:bg-white/5 hover:text-slate-200 transition-colors"
                title="Collapse all JSON nodes"
                aria-label="Collapse all nodes"
              >
                Collapse All
              </button>
            </div>

            {/* Search */}
            <div className="relative">
              <Search
                size={14}
                className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500"
              />
              <input
                ref={searchRef}
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Filter fields…"
                className="w-40 rounded-lg border border-white/[0.08] bg-white/[0.04] py-1.5 pl-8 pr-8 text-xs text-slate-300 placeholder-slate-600 outline-none transition-all focus:w-56 focus:border-violet-500/40 focus:ring-1 focus:ring-violet-500/20 sm:w-48"
                aria-label="Search within payload fields"
              />
              {searchTerm && (
                <button
                  type="button"
                  onClick={() => {
                    setSearchTerm("");
                    searchRef.current?.focus();
                  }}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                  aria-label="Clear search"
                >
                  <X size={12} />
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Header Validation (conditionally shown) */}
        <AnimatePresence>
          {showHeaders && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.3 }}
              className="overflow-hidden border-b border-white/[0.06]"
            >
              <div className="px-4 py-3">
                <HeaderValidation event={selectedEvent} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* JSON Tree */}
        <div className="relative">
          {/* Line numbers gutter */}
          <div className="pointer-events-none absolute inset-y-0 left-0 w-10 border-r border-white/[0.04] bg-white/[0.015]" />

          <div className="overflow-x-auto px-4 py-4 pl-12">
            <div className="flex items-center gap-1 pb-2 text-[10px] text-slate-600">
              <Hash size={10} />
              <span>
                {Object.keys(selectedEvent.payload).length} top-level fields
              </span>
            </div>
            <AnimatePresence mode="wait">
              <motion.div
                key={selectedEvent.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
              >
                <JsonNode
                  keyName={null}
                  value={selectedEvent.payload}
                  depth={0}
                  searchTerm={searchTerm}
                  defaultExpanded
                  expandAllSignal={expandAllSignal}
                  collapseAllSignal={collapseAllSignal}
                />
              </motion.div>
            </AnimatePresence>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-white/[0.06] bg-white/[0.02] px-4 py-2 text-[11px] text-slate-600">
          <span>
            Payload size: {new Intl.NumberFormat().format(payloadString.length)}{" "}
            bytes
          </span>
          <span className="flex items-center gap-1">
            <Webhook size={10} />
            Simulated webhook delivery
          </span>
        </div>
      </div>
    </section>
  );
}

export default WebhookInspector;
