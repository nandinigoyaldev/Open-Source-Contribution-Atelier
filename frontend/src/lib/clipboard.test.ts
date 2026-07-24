import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { copyText } from "./clipboard";

function mockExecCommand(result: boolean) {
  const mock = vi.fn().mockReturnValue(result);
  Object.defineProperty(document, "execCommand", {
    configurable: true,
    writable: true,
    value: mock,
  });
  return mock;
}

describe("copyText", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    Reflect.deleteProperty(document, "execCommand");
  });

  it("uses the Clipboard API when available", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    await expect(copyText("git status")).resolves.toEqual({
      ok: true,
      method: "clipboard-api",
    });
    expect(writeText).toHaveBeenCalledWith("git status");
  });

  it("falls back when Clipboard API is unavailable", async () => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: undefined,
    });
    const execCommand = mockExecCommand(true);

    await expect(copyText("line one\nline two")).resolves.toEqual({
      ok: true,
      method: "exec-command",
    });
    expect(execCommand).toHaveBeenCalledWith("copy");
    expect(document.querySelector('textarea[aria-hidden="true"]')).toBeNull();
  });

  it("falls back after Clipboard API permission failure", async () => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: vi
          .fn()
          .mockRejectedValue(new DOMException("Denied", "NotAllowedError")),
      },
    });
    mockExecCommand(true);

    await expect(copyText("safe value")).resolves.toEqual({
      ok: true,
      method: "exec-command",
    });
  });

  it("returns a typed failure when both methods fail", async () => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: vi
          .fn()
          .mockRejectedValue(new DOMException("Denied", "NotAllowedError")),
      },
    });
    mockExecCommand(false);

    const result = await copyText("safe value");
    expect(result.ok).toBe(false);

    if (!result.ok) {
      expect(result.error.code).toBe("PERMISSION_DENIED");
    }
  });

  it("rejects empty text", async () => {
    const result = await copyText("");
    expect(result.ok).toBe(false);

    if (!result.ok) {
      expect(result.error.code).toBe("EMPTY_TEXT");
    }
  });
});
