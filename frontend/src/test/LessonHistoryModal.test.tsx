import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  LessonHistoryModal,
  type LessonRevision,
} from "../components/LessonHistoryModal";
import * as apiModule from "../lib/api";

vi.mock("react-diff-viewer-continued", () => ({
  default: ({ oldValue, newValue, leftTitle, rightTitle }: any) => (
    <div data-testid="diff">
      <div data-testid="left-title">{leftTitle}</div>
      <div data-testid="right-title">{rightTitle}</div>
      <pre data-testid="old-value">{oldValue}</pre>
      <pre data-testid="new-value">{newValue}</pre>
    </div>
  ),
}));

const revision = (
  number: number,
  overrides: Partial<LessonRevision> = {},
): LessonRevision => ({
  id: number * 10,
  number,
  status: "archived",
  title: "Branches",
  summary: "What a branch is",
  content: `body ${number}`,
  note: "",
  authorName: "editor",
  restoredFromNumber: null,
  publishedAt: "2026-11-20T10:00:00Z",
  publishedByName: "publisher",
  createdAt: "2026-11-20T10:00:00Z",
  ...overrides,
});

// Newest first, as the API returns them. v3 is live and restores v1.
const history = [
  revision(3, {
    status: "published",
    content: "body 1",
    note: "Rollback to v1",
    restoredFromNumber: 1,
  }),
  revision(2),
  revision(1),
];

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.restoreAllMocks();
  fetchMock = vi.fn(async () => history);
  vi.spyOn(apiModule, "fetchApi").mockImplementation(fetchMock as any);
});

afterEach(() => {
  cleanup();
});

const renderModal = (onClose = vi.fn()) =>
  render(
    <LessonHistoryModal
      lessonSlug="branches"
      currentContent="body 1"
      onClose={onClose}
    />,
  );

describe("LessonHistoryModal", () => {
  it("loads the published-lessons history by slug", async () => {
    renderModal();

    await screen.findByText("v3");
    expect(fetchMock).toHaveBeenCalledWith(
      "/content/published-lessons/branches/versions/",
      expect.objectContaining({ suppressErrorToast: true }),
    );
    expect(screen.getByText("published")).toBeInTheDocument();
    expect(screen.getByText("Rollback to v1")).toBeInTheDocument();
  });

  it("starts on the newest revision that differs from the live lesson", async () => {
    renderModal();

    expect(await screen.findByTestId("left-title")).toHaveTextContent(
      "v2 (archived)",
    );
    expect(screen.getByTestId("right-title")).toHaveTextContent(
      "Current lesson",
    );
    expect(screen.getByTestId("old-value")).toHaveTextContent("body 2");
    expect(screen.getByTestId("new-value")).toHaveTextContent("body 1");
  });

  it("compares two revisions with each other", async () => {
    renderModal();
    await screen.findByText("v3");

    fireEvent.click(screen.getByRole("button", { name: /^v1/ }));
    fireEvent.change(screen.getByLabelText("Compare with"), {
      target: { value: "2" },
    });

    expect(screen.getByTestId("left-title")).toHaveTextContent("v1 (archived)");
    expect(screen.getByTestId("right-title")).toHaveTextContent(
      "v2 (archived)",
    );
    expect(screen.getByTestId("old-value")).toHaveTextContent("body 1");
    expect(screen.getByTestId("new-value")).toHaveTextContent("body 2");
    // A revision is never offered as its own comparison target.
    const options = Array.from(
      (screen.getByLabelText("Compare with") as HTMLSelectElement).options,
    ).map((o) => o.textContent);
    expect(options).toEqual([
      "Current lesson",
      "v3 (published)",
      "v2 (archived)",
    ]);
  });

  it("shows which revision a rollback restored", async () => {
    renderModal();
    await screen.findByText("v3");

    fireEvent.click(screen.getByRole("button", { name: /^v3/ }));

    expect(screen.getByText("v3 restored v1")).toBeInTheDocument();
  });

  it("says so when the history cannot be loaded", async () => {
    fetchMock.mockRejectedValueOnce(new Error("offline"));
    renderModal();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Could not load the version history.",
    );
  });

  it("closes on Escape", async () => {
    const onClose = vi.fn();
    renderModal(onClose);
    await screen.findByText("v3");

    fireEvent.keyDown(window, { key: "Escape" });

    expect(onClose).toHaveBeenCalled();
  });
});
