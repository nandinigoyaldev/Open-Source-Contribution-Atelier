import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { DeleteAccountModal } from "../components/ui/DeleteAccountModal";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fetchApi } from "../lib/api";
import { MemoryRouter } from "react-router-dom";

// Mock the API and auth hooks
vi.mock("../lib/api", () => ({
  fetchApi: vi.fn(),
}));

const mockLogout = vi.fn();
vi.mock("../features/auth/AuthContext", () => ({
  useAuth: () => ({ logout: mockLogout }),
}));

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
    </MemoryRouter>,
  );
}

import { cleanup } from "@testing-library/react";

describe("DeleteAccountModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("does not render when isOpen is false", () => {
    renderWithProviders(
      <DeleteAccountModal isOpen={false} onClose={() => {}} />,
    );
    expect(screen.queryByText(/Delete Account\?/i)).not.toBeInTheDocument();
  });

  it("renders when isOpen is true", () => {
    renderWithProviders(
      <DeleteAccountModal isOpen={true} onClose={() => {}} />,
    );
    expect(screen.getByText(/Delete Account\?/i)).toBeInTheDocument();
    expect(
      screen.getByText(/This action is permanent and cannot be undone./i),
    ).toBeInTheDocument();
  });

  it("disables delete button until 'DELETE' is typed", () => {
    renderWithProviders(
      <DeleteAccountModal isOpen={true} onClose={() => {}} />,
    );

    const deleteButton = screen.getByRole("button", { name: "Delete" });
    expect(deleteButton).toBeDisabled();

    const input = screen.getByPlaceholderText("DELETE");
    fireEvent.change(input, { target: { value: "DEL" } });
    expect(deleteButton).toBeDisabled();

    fireEvent.change(input, { target: { value: "DELETE" } });
    expect(deleteButton).not.toBeDisabled();
  });

  it("calls the API and logout on successful deletion", async () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (fetchApi as any).mockResolvedValueOnce({});

    renderWithProviders(
      <DeleteAccountModal isOpen={true} onClose={() => {}} />,
    );

    const input = screen.getByPlaceholderText("DELETE");
    fireEvent.change(input, { target: { value: "DELETE" } });

    const deleteButton = screen.getByRole("button", { name: "Delete" });
    fireEvent.click(deleteButton);

    await waitFor(() => {
      expect(fetchApi).toHaveBeenCalledWith("/auth/users/me/delete/", {
        method: "DELETE",
      });
      expect(mockLogout).toHaveBeenCalled();
    });
  });
});
