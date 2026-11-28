import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  cleanup,
  act,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { DocSearchModal } from "../components/docs/DocSearchModal";
import { fetchApi } from "../lib/api";

const navigate = vi.fn();

vi.mock("react-router-dom", async (importOriginal) => ({
  ...(await importOriginal<typeof import("react-router-dom")>()),
  useNavigate: () => navigate,
}));
vi.mock("../lib/api", () => ({ fetchApi: vi.fn() }));

const entry = (slug: string, title: string, content: string) => ({
  id: `idx-${slug}`,
  slug,
  title,
  subtitle: "Introduction",
  content,
  type: "lesson",
  hash: "",
});

const INDEX = [
  entry("pull-requests", "Pull Requests", "Propose your changes."),
  entry("branches", "Branches", "Isolate work. Some people type pul reqest."),
];

const SUGGESTION = {
  slug: "pull-requests",
  title: "Pull Requests",
  kind: "suggestion",
};

async function wait(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

function type(text: string) {
  fireEvent.change(
    screen.getByPlaceholderText("Search documentation, topics, commands..."),
    { target: { value: text } },
  );
}

async function openAndType(text: string) {
  render(
    <MemoryRouter>
      <DocSearchModal />
    </MemoryRouter>,
  );
  fireEvent.keyDown(window, { key: "k", ctrlKey: true });
  await wait(100);
  type(text);
  await wait(300);
}

const titles = () =>
  screen.getAllByRole("listitem").map((li) => li.textContent ?? "");

describe("DocSearchModal title suggestions", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ json: () => Promise.resolve(INDEX) }),
    );
    Element.prototype.scrollIntoView = vi.fn();
    vi.mocked(fetchApi).mockResolvedValue({ suggestions: [SUGGESTION] });
  });

  afterEach(() => {
    cleanup();
    vi.mocked(fetchApi).mockReset();
    navigate.mockReset();
    vi.unstubAllGlobals();
  });

  it("labels a suggestion for a misspelled title and opens it", async () => {
    await openAndType("pull reqests");

    expect(screen.getByText("Did you mean")).toBeInTheDocument();
    expect(fetchApi).toHaveBeenCalledWith(
      "/content/search/suggestions/?q=pull%20reqests",
      expect.objectContaining({ requireAuth: false, maxRetries: 0 }),
    );

    fireEvent.click(screen.getByText("Pull Requests"));

    expect(navigate).toHaveBeenCalledWith("/lessons/pull-requests");
  });

  it("keeps text that contains the query above the suggestion", async () => {
    await openAndType("pul reqest");

    expect(titles()).toHaveLength(2);
    expect(titles()[0]).toContain("Branches");
    expect(titles()[1]).toContain("Did you mean");

    fireEvent.keyDown(window, { key: "ArrowDown" });
    fireEvent.keyDown(window, { key: "Enter" });

    expect(navigate).toHaveBeenCalledWith("/lessons/pull-requests");
  });

  it("does not ask for guesses when a title matches directly", async () => {
    await openAndType("pull requests");

    expect(titles()[0]).toContain("Pull Requests");
    expect(screen.queryByText("Did you mean")).not.toBeInTheDocument();
    expect(fetchApi).not.toHaveBeenCalled();
  });

  it("does not ask for very short or very long queries", async () => {
    await openAndType("zq");
    type("z".repeat(81));
    await wait(300);

    expect(fetchApi).not.toHaveBeenCalled();
  });

  it("sends one request after typing pauses", async () => {
    await openAndType("zz");
    type("pull req");
    type("pull reqe");
    await wait(100);
    type("pull reqests");
    await wait(300);

    expect(fetchApi).toHaveBeenCalledTimes(1);
  });

  it("drops an old suggestion as soon as the query changes", async () => {
    await openAndType("pull reqests");
    vi.mocked(fetchApi).mockResolvedValue({ suggestions: [] });

    type("qwerty");

    expect(screen.queryByText("Did you mean")).not.toBeInTheDocument();
  });

  it("stays quiet when the suggestion request fails", async () => {
    vi.mocked(fetchApi).mockRejectedValue(new Error("offline"));

    await openAndType("zzzzzz");

    expect(screen.queryByText("Did you mean")).not.toBeInTheDocument();
    expect(screen.getByText(/No results found/)).toBeInTheDocument();
  });
});
