import React from "react";
import { render, screen, cleanup } from "@testing-library/react";
import { describe, it, expect, afterEach } from "vitest";
import { BookmarkAnnouncer } from "./BookmarkAnnouncer";

describe("BookmarkAnnouncer", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders live regions that are empty when announcement is null", () => {
    render(<BookmarkAnnouncer announcement={null} />);
    const status = screen.getByTestId("bookmark-announcer-status");
    const alert = screen.getByTestId("bookmark-announcer-alert");

    expect(status).toHaveAttribute("aria-live", "polite");
    expect(alert).toHaveAttribute("aria-live", "assertive");
    expect(status).toHaveTextContent("");
    expect(alert).toHaveTextContent("");
  });

  it("announces success politely to screen readers", () => {
    render(
      <BookmarkAnnouncer
        announcement={{ type: "success", message: "Saved to Read Later" }}
      />,
    );
    expect(screen.getByTestId("bookmark-announcer-status")).toHaveTextContent(
      "Saved to Read Later",
    );
    expect(screen.getByTestId("bookmark-announcer-alert")).toHaveTextContent(
      "",
    );
  });

  it("announces error assertively to screen readers", () => {
    render(
      <BookmarkAnnouncer
        announcement={{
          type: "error",
          message:
            "Could not update bookmark. Your bookmark was restored. Please try again.",
        }}
      />,
    );
    expect(screen.getByTestId("bookmark-announcer-alert")).toHaveTextContent(
      "Could not update bookmark. Your bookmark was restored. Please try again.",
    );
    expect(screen.getByTestId("bookmark-announcer-status")).toHaveTextContent(
      "",
    );
  });
});
