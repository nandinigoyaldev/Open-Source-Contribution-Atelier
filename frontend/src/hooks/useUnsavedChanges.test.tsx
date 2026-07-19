import { fireEvent, render, screen } from "@testing-library/react";
import { createMemoryRouter, Link, RouterProvider } from "react-router-dom";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { UnsavedChangesDialog } from "../components/ui/UnsavedChangesDialog";
import { useUnsavedChanges } from "./useUnsavedChanges";

function DirtyPage() {
  const [dirty, setDirty] = useState(false);
  const guard = useUnsavedChanges({ isDirty: dirty });

  return (
    <>
      <label>
        Name
        <input
          aria-label="Name"
          onChange={(event) => setDirty(event.target.value.length > 0)}
        />
      </label>
      <Link to="/next">Continue</Link>
      <UnsavedChangesDialog
        open={guard.isBlocked}
        message={guard.message}
        onStay={guard.stay}
        onDiscard={guard.discard}
      />
    </>
  );
}

function renderRouter() {
  const router = createMemoryRouter(
    [
      { path: "/", element: <DirtyPage /> },
      { path: "/next", element: <h1>Next page</h1> },
    ],
    { initialEntries: ["/"] },
  );

  render(<RouterProvider router={router} />);
  return router;
}

describe("useUnsavedChanges", () => {
  it("allows navigation when the form is clean", async () => {
    renderRouter();
    fireEvent.click(screen.getByRole("link", { name: "Continue" }));
    expect(
      await screen.findByRole("heading", { name: "Next page" }),
    ).toBeInTheDocument();
  });

  it("blocks dirty navigation and lets the user stay", () => {
    renderRouter();
    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Ada" },
    });
    fireEvent.click(screen.getByRole("link", { name: "Continue" }));

    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Stay here" }));
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Name")).toHaveValue("Ada");
  });

  it("continues navigation after discard", async () => {
    renderRouter();
    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Ada" },
    });
    fireEvent.click(screen.getByRole("link", { name: "Continue" }));
    fireEvent.click(screen.getByRole("button", { name: "Discard changes" }));

    expect(
      await screen.findByRole("heading", { name: "Next page" }),
    ).toBeInTheDocument();
  });

  it("registers and removes beforeunload for dirty state", () => {
    const addSpy = vi.spyOn(window, "addEventListener");
    const removeSpy = vi.spyOn(window, "removeEventListener");

    const { unmount } = render(
      <RouterProvider
        router={createMemoryRouter([{ path: "/", element: <DirtyPage /> }], {
          initialEntries: ["/"],
        })}
      />,
    );

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Ada" },
    });

    expect(addSpy).toHaveBeenCalledWith("beforeunload", expect.any(Function));
    unmount();
    expect(removeSpy).toHaveBeenCalledWith(
      "beforeunload",
      expect.any(Function),
    );
  });
});
