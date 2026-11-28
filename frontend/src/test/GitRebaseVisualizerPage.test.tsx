import { describe, it, expect, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import GitRebaseVisualizerPage from "../pages/GitRebaseVisualizerPage";
import React from "react";
import { suspendShortcuts } from "../features/shortcuts/store";

afterEach(cleanup);

describe("GitRebaseVisualizerPage Undo/Redo History", () => {
  it("renders visualizer page with Undo and Redo buttons initially disabled", () => {
    render(<GitRebaseVisualizerPage />);

    expect(screen.getByText(/Git Interactive Rebase Studio/i)).toBeInTheDocument();

    const undoButtons = screen.getAllByRole("button", { name: /undo/i });
    const redoButtons = screen.getAllByRole("button", { name: /redo/i });

    expect(undoButtons.length).toBeGreaterThan(0);
    expect(redoButtons.length).toBeGreaterThan(0);

    undoButtons.forEach((btn) => expect(btn).toBeDisabled());
    redoButtons.forEach((btn) => expect(btn).toBeDisabled());
  });

  it("enables Undo when commit action changes and reverts state on Undo click", () => {
    render(<GitRebaseVisualizerPage />);

    const dropButtons = screen.getAllByRole("button", { name: /^drop$/i });
    expect(dropButtons.length).toBeGreaterThan(0);

    // Change commit action to drop
    fireEvent.click(dropButtons[0]);

    const undoButtons = screen.getAllByRole("button", { name: /undo/i });
    const redoButtons = screen.getAllByRole("button", { name: /redo/i });

    // Undo should now be enabled, Redo disabled
    expect(undoButtons[0]).not.toBeDisabled();
    expect(redoButtons[0]).toBeDisabled();

    // Click Undo
    fireEvent.click(undoButtons[0]);

    // Redo should now be enabled
    expect(redoButtons[0]).not.toBeDisabled();
  });

  it("handles keyboard shortcuts (Ctrl+Z and Ctrl+Y) for undo and redo", () => {
    render(<GitRebaseVisualizerPage />);

    const dropButtons = screen.getAllByRole("button", { name: /^drop$/i });
    expect(dropButtons.length).toBeGreaterThan(0);

    fireEvent.click(dropButtons[0]);

    const undoButtons = screen.getAllByRole("button", { name: /undo/i });
    const redoButtons = screen.getAllByRole("button", { name: /redo/i });

    expect(undoButtons[0]).not.toBeDisabled();

    // Trigger Ctrl+Z
    fireEvent.keyDown(window, { key: "z", ctrlKey: true });

    expect(redoButtons[0]).not.toBeDisabled();

    // Trigger Ctrl+Y
    fireEvent.keyDown(window, { key: "y", ctrlKey: true });

    expect(undoButtons[0]).not.toBeDisabled();
  });

  it("ignores Ctrl+Z and Ctrl+Y while the shortcut editor is open", () => {
    render(<GitRebaseVisualizerPage />);
    fireEvent.click(screen.getAllByRole("button", { name: /^drop$/i })[0]);
    const redo = screen.getAllByRole("button", { name: /redo/i })[0];

    const release = suspendShortcuts();
    fireEvent.keyDown(window, { key: "z", ctrlKey: true });
    expect(redo).toBeDisabled();

    release();
    fireEvent.keyDown(window, { key: "z", ctrlKey: true });
    expect(redo).not.toBeDisabled();
  });
});
