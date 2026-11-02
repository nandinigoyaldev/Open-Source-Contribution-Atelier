import {
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ActivityTimelinePage } from "../pages/ActivityTimelinePage";
import {
  buildActivityQuery,
  formatDayHeading,
  groupActivityByDay,
  mergeActivityPages,
  activityLink,
  type ActivityItem,
  type ActivityPage,
} from "../lib/activityTimeline";

vi.mock("../features/auth/AuthContext", () => ({
  useAuth: () => ({ user: { id: 7, username: "learner" } }),
}));

const fetchApi = vi.fn();
vi.mock("../lib/api", () => ({
  fetchApi: (...args: unknown[]) => fetchApi(...args),
}));

function item(n: number, over: Partial<ActivityItem> = {}): ActivityItem {
  return {
    id: `lesson_completed:${n}`,
    type: "lesson_completed",
    occurred_at: new Date(2026, 9, 27, 12, 0 - n).toISOString(),
    title: `Lesson ${n}`,
    description: "",
    metadata: { lesson_slug: `lesson-${n}` },
    ...over,
  };
}

function page(
  items: ActivityItem[],
  extra: Partial<ActivityPage> = {},
): ActivityPage {
  return {
    results: items,
    next_cursor: null,
    has_more: false,
    limit: 20,
    types: [
      "lesson_completed",
      "quiz_attempt",
      "certificate_issued",
      "badge_earned",
    ],
    ...extra,
  };
}

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ActivityTimelinePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const calledUrls = () => fetchApi.mock.calls.map((c) => String(c[0]));

describe("ActivityTimelinePage", () => {
  beforeEach(() => {
    fetchApi.mockReset();
    // The shared setup installs fake timers; waitFor and user-event need real ones here.
    // eslint-disable-next-line no-restricted-syntax
    vi.useRealTimers();
  });
  afterEach(() => {
    cleanup(); // this project does not clean up the DOM between tests automatically
    vi.clearAllMocks();
  });

  it("shows a loading state first", async () => {
    fetchApi.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(
      screen.getByRole("status", { name: /loading your activity/i }),
    ).toBeInTheDocument();
  });

  it("lists activity newest first, grouped by day, with the type and time", async () => {
    fetchApi.mockResolvedValue(
      page([
        item(1, { title: "Git basics", description: "Score 80" }),
        item(2, {
          id: "quiz_attempt:5",
          type: "quiz_attempt",
          title: "What is a fork?",
          description: "Incorrect",
          metadata: { is_correct: false },
        }),
        item(3, {
          id: "certificate_issued:1",
          type: "certificate_issued",
          title: "Open Source Course",
          metadata: { verification_hash: "abc" },
        }),
      ]),
    );
    renderPage();

    const rows = await screen.findAllByTestId("activity-item");
    expect(rows).toHaveLength(3);
    expect(within(rows[0]).getByText("Git basics")).toBeInTheDocument();
    expect(within(rows[0]).getByText("Score 80")).toBeInTheDocument();
    expect(within(rows[0]).getByText("Completed a lesson")).toBeInTheDocument();
    expect(
      within(rows[1]).getByText("Answered a quiz question"),
    ).toBeInTheDocument();
    expect(within(rows[1]).getByText("Incorrect")).toBeInTheDocument();
    expect(
      within(rows[2]).getByText("Earned a certificate"),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 2 })).toHaveLength(1); // one day
    expect(document.querySelectorAll("time[datetime]")).toHaveLength(3);
  });

  it("links lessons and certificates, and leaves other items as plain text", async () => {
    fetchApi.mockResolvedValue(
      page([
        item(1, { title: "Git basics" }),
        item(2, {
          id: "certificate_issued:1",
          type: "certificate_issued",
          title: "Course",
          metadata: { verification_hash: "abc123" },
        }),
        item(3, {
          id: "quiz_attempt:1",
          type: "quiz_attempt",
          title: "Question",
          metadata: {},
        }),
      ]),
    );
    renderPage();
    expect(
      await screen.findByRole("link", { name: "Git basics" }),
    ).toHaveAttribute("href", "/lessons/lesson-1");
    expect(screen.getByRole("link", { name: "Course" })).toHaveAttribute(
      "href",
      "/verify/abc123",
    );
    expect(screen.queryByRole("link", { name: "Question" })).toBeNull();
  });

  it("shows a useful empty state when there is no activity", async () => {
    fetchApi.mockResolvedValue(page([]));
    renderPage();
    expect(await screen.findByText("No activity yet")).toBeInTheDocument();
    expect(
      screen.getByText(/finish a lesson or answer a quiz question/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /start learning/i }),
    ).toHaveAttribute("href", "/dashboard");
  });

  it("shows an error state with a retry that loads the list", async () => {
    const user = userEvent.setup();
    fetchApi.mockRejectedValueOnce(new Error("network"));
    fetchApi.mockResolvedValueOnce(page([item(1)]));
    renderPage();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/could not load your activity/i);
    await user.click(screen.getByRole("button", { name: /try again/i }));
    expect(await screen.findByText("Lesson 1")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  describe("filtering", () => {
    it("filters by type, marks the chip as pressed and asks the server", async () => {
      const user = userEvent.setup();
      fetchApi.mockImplementation((url: string) =>
        Promise.resolve(
          url.includes("type=quiz_attempt")
            ? page([
                item(9, {
                  id: "quiz_attempt:9",
                  type: "quiz_attempt",
                  title: "A quiz",
                  metadata: {},
                }),
              ])
            : page([item(1), item(2)]),
        ),
      );
      renderPage();
      await screen.findByText("Lesson 1");
      expect(screen.getByRole("button", { name: "All" })).toHaveAttribute(
        "aria-pressed",
        "true",
      );

      await user.click(screen.getByRole("button", { name: "Quizzes" }));
      expect(await screen.findByText("A quiz")).toBeInTheDocument();
      expect(screen.queryByText("Lesson 1")).toBeNull();
      expect(screen.getByRole("button", { name: "Quizzes" })).toHaveAttribute(
        "aria-pressed",
        "true",
      );
      expect(screen.getByRole("button", { name: "All" })).toHaveAttribute(
        "aria-pressed",
        "false",
      );
      expect(calledUrls().some((u) => u.includes("type=quiz_attempt"))).toBe(
        true,
      );
    });

    it("combines several types and 'All' clears them", async () => {
      const user = userEvent.setup();
      fetchApi.mockResolvedValue(page([item(1)]));
      renderPage();
      await screen.findByText("Lesson 1");

      await user.click(screen.getByRole("button", { name: "Badges" }));
      await user.click(screen.getByRole("button", { name: "Lessons" }));
      await waitFor(() =>
        expect(
          calledUrls().some((u) =>
            u.includes("type=lesson_completed%2Cbadge_earned"),
          ),
        ).toBe(true),
      );

      await user.click(screen.getByRole("button", { name: "All" }));
      expect(screen.getByRole("button", { name: "Badges" })).toHaveAttribute(
        "aria-pressed",
        "false",
      );
      expect(calledUrls().at(-1)).not.toContain("type=");
    });

    it("shows a filter-specific empty state with a way back", async () => {
      const user = userEvent.setup();
      fetchApi.mockImplementation((url: string) =>
        Promise.resolve(
          url.includes("type=badge_earned") ? page([]) : page([item(1)]),
        ),
      );
      renderPage();
      await screen.findByText("Lesson 1");

      await user.click(screen.getByRole("button", { name: "Badges" }));
      expect(
        await screen.findByText("No badges activity yet"),
      ).toBeInTheDocument();
      await user.click(
        screen.getByRole("button", { name: /show all activity/i }),
      );
      expect(await screen.findByText("Lesson 1")).toBeInTheDocument();
    });
  });

  describe("pagination", () => {
    it("loads the next page with the cursor and appends it", async () => {
      const user = userEvent.setup();
      fetchApi.mockImplementation((url: string) =>
        Promise.resolve(
          url.includes("cursor=C1")
            ? page([item(3)])
            : page([item(1), item(2)], { has_more: true, next_cursor: "C1" }),
        ),
      );
      renderPage();
      await screen.findByText("Lesson 1");
      expect(screen.queryByText(/that is all of your activity/i)).toBeNull();

      await user.click(screen.getByRole("button", { name: /load more/i }));
      expect(await screen.findByText("Lesson 3")).toBeInTheDocument();
      expect(screen.getAllByTestId("activity-item")).toHaveLength(3);
      expect(screen.queryByRole("button", { name: /load more/i })).toBeNull();
      expect(
        screen.getByText(/that is all of your activity/i),
      ).toBeInTheDocument();
    });

    it("keeps earlier items and offers a retry when a later page fails", async () => {
      const user = userEvent.setup();
      let failed = false;
      fetchApi.mockImplementation((url: string) => {
        if (url.includes("cursor=C1")) {
          if (!failed) {
            failed = true;
            return Promise.reject(new Error("boom"));
          }
          return Promise.resolve(page([item(3)]));
        }
        return Promise.resolve(
          page([item(1), item(2)], { has_more: true, next_cursor: "C1" }),
        );
      });
      renderPage();
      await screen.findByText("Lesson 1");

      await user.click(screen.getByRole("button", { name: /load more/i }));
      expect(await screen.findByRole("alert")).toHaveTextContent(
        /could not load more/i,
      );
      expect(screen.getByText("Lesson 1")).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: /try again/i }));
      expect(await screen.findByText("Lesson 3")).toBeInTheDocument();
    });

    it("does not show the same item twice if pages overlap", async () => {
      const user = userEvent.setup();
      fetchApi.mockImplementation((url: string) =>
        Promise.resolve(
          url.includes("cursor=C1")
            ? page([item(2), item(3)])
            : page([item(1), item(2)], { has_more: true, next_cursor: "C1" }),
        ),
      );
      renderPage();
      await screen.findByText("Lesson 1");
      await user.click(screen.getByRole("button", { name: /load more/i }));
      await screen.findByText("Lesson 3");
      expect(screen.getAllByText("Lesson 2")).toHaveLength(1);
    });
  });
});

describe("activity timeline helpers", () => {
  it("builds a stable query: sorted filter, no filter for 'everything', limit and cursor", () => {
    expect(buildActivityQuery({})).toBe("limit=20");
    expect(buildActivityQuery({ types: [] })).toBe("limit=20");
    expect(
      buildActivityQuery({ types: ["badge_earned", "lesson_completed"] }),
    ).toBe("type=lesson_completed%2Cbadge_earned&limit=20");
    expect(
      buildActivityQuery({
        types: [
          "lesson_completed",
          "quiz_attempt",
          "certificate_issued",
          "badge_earned",
        ],
      }),
    ).toBe("limit=20");
    expect(
      buildActivityQuery({ types: ["quiz_attempt"], cursor: "a b", limit: 5 }),
    ).toBe("type=quiz_attempt&limit=5&cursor=a+b");
  });

  it("groups by local day without reordering", () => {
    const items = [
      item(0, { occurred_at: new Date(2026, 9, 27, 23, 30).toISOString() }),
      item(1, { occurred_at: new Date(2026, 9, 27, 0, 5).toISOString() }),
      item(2, { occurred_at: new Date(2026, 9, 26, 23, 59).toISOString() }),
    ];
    const groups = groupActivityByDay(items);
    expect(groups.map((g) => g.dayKey)).toEqual(["2026-10-27", "2026-10-26"]);
    expect(groups[0].items.map((i) => i.id)).toEqual([
      items[0].id,
      items[1].id,
    ]);
  });

  it("ignores items with an unreadable time instead of crashing", () => {
    expect(groupActivityByDay([item(1, { occurred_at: "nope" })])).toEqual([]);
  });

  it("names today and yesterday", () => {
    const now = new Date(2026, 9, 27, 15, 0);
    expect(formatDayHeading("2026-10-27", now)).toBe("Today");
    expect(formatDayHeading("2026-10-26", now)).toBe("Yesterday");
    expect(formatDayHeading("2026-10-20", now)).toMatch(/2026/);
  });

  it("merges pages and drops repeats, keeping the first", () => {
    const merged = mergeActivityPages([
      page([item(1), item(2)]),
      page([item(2), item(3)]),
    ]);
    expect(merged.map((i) => i.id)).toEqual([
      "lesson_completed:1",
      "lesson_completed:2",
      "lesson_completed:3",
    ]);
  });

  it("only links what has somewhere to go", () => {
    expect(activityLink(item(1))).toBe("/lessons/lesson-1");
    expect(activityLink(item(1, { metadata: {} }))).toBeNull();
    expect(
      activityLink(
        item(1, {
          type: "certificate_issued",
          metadata: { verification_hash: "h" },
        }),
      ),
    ).toBe("/verify/h");
    expect(
      activityLink(item(1, { type: "badge_earned", metadata: {} })),
    ).toBeNull();
  });
});
