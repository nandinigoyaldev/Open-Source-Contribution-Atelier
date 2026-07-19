import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CopyButton } from "./CopyButton";

describe("CopyButton", () => {
  afterEach(() => vi.restoreAllMocks());

  it("announces successful copies", async () => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });

    render(<CopyButton text="git status" />);
    fireEvent.click(screen.getByRole("button", { name: "Copy" }));

    expect(
      await screen.findByRole("button", { name: "Copied" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Copied.");
  });

  it("shows accessible failure feedback", async () => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: vi.fn().mockRejectedValue(
          new DOMException("Denied", "NotAllowedError"),
        ),
      },
    });
    vi.spyOn(document, "execCommand").mockReturnValue(false);

    render(<CopyButton text="git status" />);
    fireEvent.click(screen.getByRole("button", { name: "Copy" }));

    expect(
      await screen.findByRole("button", { name: "Copy failed" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Clipboard permission was denied.",
    );
  });
});
