import { describe, expect, it } from "vitest";
import {
  buildReplayPayload,
  buildReplayShareUrl,
  encodeReplayHash,
  parseReplayHash,
  replayCommandsFromTerminalLines,
  sanitizeReplayCommands,
} from "../lib/terminalReplayShare";

describe("terminalReplayShare", () => {
  const sample = [
    { command: "git init", output: "Initialized empty repo" },
    { command: "git status", output: "On branch main", isError: false },
  ];

  it("encodes and decodes a round-trip hash payload", () => {
    const hash = encodeReplayHash(sample, "Demo");
    expect(hash.startsWith("replay=")).toBe(true);

    const parsed = parseReplayHash(`#${hash}`);
    expect(parsed.ok).toBe(true);
    if (!parsed.ok) return;
    expect(parsed.payload.name).toBe("Demo");
    expect(parsed.commands).toHaveLength(2);
    expect(parsed.commands[0]?.command).toBe("git init");
    expect(parsed.commands[0]?.output).toContain("Initialized");
  });

  it("returns a graceful error for empty / missing hashes", () => {
    expect(parseReplayHash("").ok).toBe(false);
    expect(parseReplayHash("#").ok).toBe(false);
    expect(parseReplayHash("#replay=").ok).toBe(false);
    expect((parseReplayHash("#other=1") as any).error).toMatch(
      /No replay hash/i,
    );
  });

  it("rejects corrupted base64 payloads", () => {
    const result = parseReplayHash("#replay=%%%not-valid%%%");
    expect(result.ok).toBe(false);
    expect((result as any).error).toMatch(/decode|corrupt/i);
  });

  it("sanitizes blank commands and caps length", () => {
    const cleaned = sanitizeReplayCommands([
      { command: "   ", output: "" },
      { command: "git add .", output: "x".repeat(5000) },
    ]);
    expect(cleaned).toHaveLength(1);
    expect(cleaned[0]?.output.length).toBeLessThanOrEqual(800);
  });

  it("builds a shareable URL for /sandbox", () => {
    const url = buildReplayShareUrl({
      commands: sample,
      sessionName: "PR demo",
      pathname: "/sandbox",
      origin: "https://atelier.example",
    });
    expect(url).toMatch(/^https:\/\/atelier\.example\/sandbox#replay=/);
    const parsed = parseReplayHash(url!.slice(url!.indexOf("#")));
    expect(parsed.ok).toBe(true);
  });

  it("returns null share URL when there are no commands", () => {
    expect(
      buildReplayShareUrl({ commands: [], pathname: "/sandbox" }),
    ).toBeNull();
  });

  it("extracts replay commands from terminal lines", () => {
    const cmds = replayCommandsFromTerminalLines([
      { kind: "command", text: "git init" },
      { kind: "output", text: "ok" },
      { kind: "command", text: "git status" },
      { kind: "error", text: "fatal" },
    ]);
    expect(cmds).toHaveLength(2);
    expect(cmds[0]?.output).toBe("ok");
    expect(cmds[1]?.isError).toBe(true);
    expect(cmds[1]?.output).toBe("fatal");
  });

  it("buildReplayPayload sets version 1", () => {
    expect(buildReplayPayload(sample).v).toBe(1);
  });
});
