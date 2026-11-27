import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AdaptiveDifficultyToggle } from "../features/auth/AdaptiveDifficultyToggle";
import { fetchApi } from "../lib/api";

vi.mock("../lib/api", () => ({ fetchApi: vi.fn() }));

const off = {
  enabled: false,
  skill_rating: 1500,
  rating_deviation: 350,
  level: "standard",
};

function renderToggle() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <AdaptiveDifficultyToggle />
    </QueryClientProvider>,
  );
  return screen.getByRole("checkbox", {
    name: /adaptive challenge difficulty/i,
  });
}

describe("AdaptiveDifficultyToggle", () => {
  beforeEach(() => {
    vi.mocked(fetchApi).mockReset();
  });

  afterEach(cleanup);

  it("starts unchecked and hides the rating", async () => {
    vi.mocked(fetchApi).mockResolvedValue(off);
    const box = renderToggle();

    await waitFor(() => expect(box).toBeEnabled());
    expect(box).not.toBeChecked();
    expect(screen.queryByText(/Rating 1500/)).not.toBeInTheDocument();
  });

  it("opts in and shows the rating", async () => {
    vi.mocked(fetchApi).mockImplementation(async (_url, options) =>
      options?.method === "PUT" ? { ...off, enabled: true } : off,
    );
    const box = renderToggle();
    await waitFor(() => expect(box).toBeEnabled());

    fireEvent.click(box);

    expect(await screen.findByText(/Rating 1500/)).toBeInTheDocument();
    expect(box).toBeChecked();
    expect(fetchApi).toHaveBeenCalledWith("/progress/adaptive-difficulty/", {
      method: "PUT",
      body: JSON.stringify({ enabled: true }),
      suppressErrorToast: true,
    });
  });

  it("reports a failed save", async () => {
    vi.mocked(fetchApi).mockImplementation(async (_url, options) => {
      if (options?.method === "PUT") throw new Error("nope");
      return off;
    });
    const box = renderToggle();
    await waitFor(() => expect(box).toBeEnabled());

    fireEvent.click(box);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Could not save this setting.",
    );
    expect(box).not.toBeChecked();
  });
});
