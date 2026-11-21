import React from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ValidationSummary } from "./ValidationSummary";

describe("ValidationSummary", () => {
  afterEach(cleanup);

  it("renders nothing when errors array is empty", () => {
    const { container } = render(<ValidationSummary errors={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders container with role='alert', tabIndex={-1}, and aria-labelledby", () => {
    render(
      <ValidationSummary
        id="test-summary"
        errors={[{ fieldId: "email", message: "Email is invalid" }]}
      />,
    );

    const alert = screen.getByRole("alert");
    expect(alert).toHaveAttribute("id", "test-summary");
    expect(alert).toHaveAttribute("tabindex", "-1");
    expect(alert).toHaveAttribute("aria-labelledby", "test-summary-title");

    const heading = screen.getByRole("heading", { level: 2 });
    expect(heading).toHaveAttribute("id", "test-summary-title");
    expect(heading).toHaveTextContent("There is 1 error with your submission");
  });

  it("displays plural message when multiple errors exist", () => {
    render(
      <ValidationSummary
        errors={[
          { fieldId: "username", message: "Username is required" },
          { fieldId: "email", message: "Email is invalid" },
        ]}
      />,
    );

    expect(
      screen.getByText("There are 2 errors with your submission"),
    ).toBeInTheDocument();
  });

  it("supports custom title", () => {
    render(
      <ValidationSummary
        title="Please fix these mistakes"
        errors={[{ fieldId: "email", message: "Email is invalid" }]}
      />,
    );

    expect(screen.getByText("Please fix these mistakes")).toBeInTheDocument();
  });

  it("renders links to invalid fields with labels and messages", () => {
    render(
      <ValidationSummary
        errors={[
          {
            fieldId: "first_name",
            label: "Display Name",
            message: "Cannot be empty",
          },
          { fieldId: "email", label: "Email Address", message: "Invalid email" },
        ]}
      />,
    );

    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(2);
    expect(links[0]).toHaveAttribute("href", "#first_name");
    expect(links[0]).toHaveTextContent("Display Name: Cannot be empty");
    expect(links[1]).toHaveAttribute("href", "#email");
    expect(links[1]).toHaveTextContent("Email Address: Invalid email");
  });

  it("moves focus to the invalid field when link is clicked", async () => {
    const user = userEvent.setup();

    render(
      <div>
        <ValidationSummary
          errors={[{ fieldId: "test-input", message: "Required field" }]}
        />
        <form>
          <label htmlFor="test-input">Test Field</label>
          <input id="test-input" type="text" />
        </form>
      </div>,
    );

    const input = screen.getByLabelText("Test Field");
    expect(document.activeElement).not.toBe(input);

    const link = screen.getByRole("link", { name: /Required field/i });
    await user.click(link);

    expect(document.activeElement).toBe(input);
  });

  it("calls onLinkClick callback when error link is clicked", async () => {
    const user = userEvent.setup();
    const handleClick = vi.fn();

    render(
      <div>
        <ValidationSummary
          onLinkClick={handleClick}
          errors={[{ fieldId: "field-a", message: "Field A is wrong" }]}
        />
        <input id="field-a" type="text" />
      </div>,
    );

    await user.click(screen.getByRole("link", { name: /Field A is wrong/i }));
    expect(handleClick).toHaveBeenCalledWith("field-a");
  });

  it("focuses summary automatically when autoFocus is set", () => {
    render(
      <ValidationSummary
        autoFocus
        errors={[{ fieldId: "field-b", message: "Field B error" }]}
      />,
    );

    const summary = screen.getByRole("alert");
    expect(document.activeElement).toBe(summary);
  });
});
