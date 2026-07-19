import React from "react";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
  act,
} from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { CodeSandbox } from "../components/ui/CodeSandbox";
import { useWebSocket } from "../hooks/useWebSocket";
import { fetchSandboxSnapshots, saveSandboxSnapshot } from "../lib/api";

// Mock Monaco editor to avoid pulling in the real editor in jsdom
vi.mock("@monaco-editor/react", () => ({
  __esModule: true,
  default: () => <div data-testid="monaco-editor" />,
}));

// Mock the collaborative websocket hook, we don't need real sockets here
vi.mock("../hooks/useWebSocket", () => ({
  useWebSocket: vi.fn(),
}));

// Mock the API calls used for snapshot history
vi.mock("../lib/api", () => ({
  fetchSandboxSnapshots: vi.fn(),
  saveSandboxSnapshot: vi.fn(),
}));

describe("CodeSandbox output capture", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (useWebSocket as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      send: vi.fn(),
      isConnected: false,
    });
    (
      fetchSandboxSnapshots as unknown as ReturnType<typeof vi.fn>
    ).mockResolvedValue([]);
    (
      saveSandboxSnapshot as unknown as ReturnType<typeof vi.fn>
    ).mockResolvedValue({
      id: 1,
      code: "",
      label: "",
      is_auto: true,
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("renders console.log output posted back from the sandbox iframe", async () => {
    render(<CodeSandbox />);

    expect(screen.getByText("Output will appear here...")).toBeInTheDocument();

    const iframe = document.querySelector("iframe") as HTMLIFrameElement;
    expect(iframe).toBeTruthy();

    fireEvent.click(screen.getByText("Run"));

    await act(async () => {
      window.dispatchEvent(
        new MessageEvent("message", {
          data: { type: "log", message: "Hello, World!" },
          source: iframe.contentWindow,
        }),
      );
    });

    await waitFor(() => {
      expect(screen.getByText(/Hello, World!/)).toBeInTheDocument();
    });
  });

  it("ignores postMessage events that do not originate from its own sandbox iframe", async () => {
    render(<CodeSandbox />);

    fireEvent.click(screen.getByText("Run"));

    await act(async () => {
      window.dispatchEvent(
        new MessageEvent("message", {
          data: { type: "log", message: "should not appear" },
        }),
      );
    });

    expect(screen.queryByText(/should not appear/)).not.toBeInTheDocument();
  });
});
