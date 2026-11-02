import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, it, expect } from "vitest";
import { ProgressAnnouncer } from "./ProgressAnnouncer";

describe("ProgressAnnouncer", () => {
  afterEach(cleanup);

  it("keeps empty polite and assertive live regions mounted", () => {
    render(<ProgressAnnouncer announcement={null} />);
    const status = screen.getByRole("status");
    const alert = screen.getByRole("alert");
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(alert).toHaveAttribute("aria-live", "assertive");
    expect(status).toBeEmptyDOMElement();
    expect(alert).toBeEmptyDOMElement();
  });

  it("announces success politely and only once", () => {
    render(
      <ProgressAnnouncer
        announcement={{ type: "success", message: "Lesson completion saved." }}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "Lesson completion saved.",
    );
    expect(screen.getByRole("alert")).toBeEmptyDOMElement();
    expect(screen.getAllByText("Lesson completion saved.")).toHaveLength(1);
  });

  it("announces failure assertively without a success message", () => {
    render(
      <ProgressAnnouncer
        announcement={{ type: "error", message: "Could not save." }}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Could not save.");
    expect(screen.getByRole("status")).toBeEmptyDOMElement();
  });
});
