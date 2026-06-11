import React from "react";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, beforeEach, vi } from "vitest";
import LogoutConfirmModal from "./LogoutConfirmModal";

describe("LogoutConfirmModal", () => {
  beforeEach(() => {
    cleanup();
    document.body.innerHTML = "";
  });

  it("does not render when open is false", () => {
    render(
      <LogoutConfirmModal
        open={false}
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    );
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("renders and calls handlers on click", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    const onCancel = vi.fn();

    render(
      <LogoutConfirmModal
        open={true}
        onConfirm={onConfirm}
        onCancel={onCancel}
      />,
    );

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await user.click(screen.getByTestId("cancel-button"));
    expect(onCancel).toHaveBeenCalledTimes(1);

    await user.click(screen.getByTestId("confirm-button"));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});
