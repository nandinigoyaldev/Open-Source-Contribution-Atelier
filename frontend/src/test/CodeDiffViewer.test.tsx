import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { CodeDiffViewer } from "../components/ui/CodeDiffViewer";
import * as useThemeHook from "../hooks/useTheme";

// Mock the useTheme hook
vi.mock("../hooks/useTheme", () => ({
  useTheme: vi.fn(),
}));

// Mock react-diff-viewer-continued
vi.mock("react-diff-viewer-continued", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-diff-viewer-continued")>();
  const MockDiffViewer = ({ oldValue, newValue, splitView, useDarkTheme }: any) => (
    <div data-testid="mock-diff-viewer">
      <div data-testid="old-value">{oldValue}</div>
      <div data-testid="new-value">{newValue}</div>
      <div data-testid="is-split-view">{splitView ? "true" : "false"}</div>
      <div data-testid="is-dark-theme">{useDarkTheme ? "true" : "false"}</div>
    </div>
  );
  return {
    ...actual,
    default: MockDiffViewer,
  };
});

describe("CodeDiffViewer", () => {
  beforeEach(() => {
    vi.mocked(useThemeHook.useTheme).mockReturnValue({ theme: "light" } as any);
  });

  afterEach(() => {
    vi.clearAllMocks();
    cleanup();
  });

  it("should render successfully with original and modified code", () => {
    render(
      <CodeDiffViewer
        originalCode="const a = 1;"
        modifiedCode="const a = 2;"
      />
    );

    expect(screen.getByText("Source Code Changes")).toBeInTheDocument();
    expect(screen.getByText("submission.code")).toBeInTheDocument();
    expect(screen.getByTestId("old-value")).toHaveTextContent("const a = 1;");
    expect(screen.getByTestId("new-value")).toHaveTextContent("const a = 2;");
  });

  it("should toggle between split and unified views correctly", () => {
    render(
      <CodeDiffViewer
        originalCode="code A"
        modifiedCode="code B"
      />
    );

    const splitViewElement = screen.getByTestId("is-split-view");
    expect(splitViewElement).toHaveTextContent("true"); // Default is true

    // Click Unified View
    const unifiedBtn = screen.getByTitle("Unified View");
    fireEvent.click(unifiedBtn);
    expect(splitViewElement).toHaveTextContent("false");

    // Click Split View
    const splitBtn = screen.getByTitle("Split View");
    fireEvent.click(splitBtn);
    expect(splitViewElement).toHaveTextContent("true");
  });

  it("should correctly handle dark theme from useTheme", () => {
    vi.mocked(useThemeHook.useTheme).mockReturnValue({ theme: "dark" } as any);

    render(
      <CodeDiffViewer
        originalCode="dark1"
        modifiedCode="dark2"
      />
    );

    expect(screen.getByTestId("is-dark-theme")).toHaveTextContent("true");
  });

  it("should render with custom title and filename", () => {
    render(
      <CodeDiffViewer
        originalCode="x"
        modifiedCode="y"
        title="Custom Title"
        fileName="custom.js"
      />
    );

    expect(screen.getByText("Custom Title")).toBeInTheDocument();
    expect(screen.getByText("custom.js")).toBeInTheDocument();
  });
});
