import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { NotFoundPage } from "./NotFoundPage";

describe("NotFoundPage edge cases and rendering", () => {
  beforeEach(() => {
    // Reset any state if necessary
  });

  afterEach(() => {
    cleanup();
  });

  it("should render the missing route indicator", () => {
    render(
      <MemoryRouter>
        <NotFoundPage />
      </MemoryRouter>
    );

    const indicator = screen.getByText("ROUTE MISSING");
    expect(indicator).toBeInTheDocument();
  });

  it("should render the 404 main message", () => {
    render(
      <MemoryRouter>
        <NotFoundPage />
      </MemoryRouter>
    );

    const heading = screen.getByText("This corridor doesn't exist.");
    expect(heading).toBeInTheDocument();
  });

  it("should provide a link back to the home page", () => {
    render(
      <MemoryRouter>
        <NotFoundPage />
      </MemoryRouter>
    );

    const link = screen.getByRole("link", { name: /Back to Home/i });
    expect(link).toBeInTheDocument();
    expect(link.getAttribute("href")).toBe("/");
  });
});
