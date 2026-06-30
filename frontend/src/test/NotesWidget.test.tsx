import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { NotesWidget } from "../components/ui/NotesWidget";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fetchApi } from "../lib/api";

vi.mock("../lib/api", () => ({
  fetchApi: vi.fn(),
}));

// Mock the crypto lib so we don't need real IndexedDB/CryptoKey in tests
vi.mock("../lib/notesCrypto", () => ({
  encryptNoteContent: vi.fn((text) =>
    Promise.resolve({ ciphertext: `encrypted_${text}`, iv: "mock_iv" }),
  ),
  decryptNoteContent: vi.fn((ciphertext) =>
    Promise.resolve(ciphertext.replace("encrypted_", "")),
  ),
}));

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("NotesWidget", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the widget toggle button initially", () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (fetchApi as any).mockResolvedValueOnce([]);
    renderWithProviders(<NotesWidget />);
    expect(
      screen.getByRole("button", { name: /Private Notes/i }),
    ).toBeInTheDocument();
  });

  it("opens the widget and shows empty state", async () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (fetchApi as any).mockResolvedValueOnce([]);
    renderWithProviders(<NotesWidget />);

    fireEvent.click(screen.getByRole("button", { name: /Private Notes/i }));

    expect(await screen.findByText("E2E Notes")).toBeInTheDocument();
    expect(screen.getByText("No notes yet.")).toBeInTheDocument();
  });

  it("displays decrypted notes correctly", async () => {
    const mockNotes = [
      {
        id: 1,
        title: "Secret 1",
        encrypted_content: "encrypted_Hello World",
        iv: "123",
        created_at: "",
        updated_at: "",
      },
    ];
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (fetchApi as any).mockResolvedValueOnce(mockNotes);

    renderWithProviders(<NotesWidget />);
    fireEvent.click(screen.getByRole("button", { name: /Private Notes/i }));

    expect(await screen.findByText("Secret 1")).toBeInTheDocument();
    // Verify it was decrypted
    expect(await screen.findByText("Hello World")).toBeInTheDocument();
  });

  it("saves a new encrypted note", async () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (fetchApi as any).mockResolvedValueOnce([]); // initial load
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (fetchApi as any).mockResolvedValueOnce({ id: 2 }); // save response

    renderWithProviders(<NotesWidget />);
    fireEvent.click(screen.getByRole("button", { name: /Private Notes/i }));

    // Click plus
    const plusButtons = screen.getAllByRole("button");
    fireEvent.click(plusButtons[1]); // The + button

    const titleInput = screen.getByPlaceholderText("Note Title");
    const contentInput = screen.getByPlaceholderText(
      /Write your secret notes/i,
    );

    fireEvent.change(titleInput, { target: { value: "New Secret" } });
    fireEvent.change(contentInput, { target: { value: "My private text" } });

    const saveButton = screen.getByRole("button", { name: /Save Securely/i });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(fetchApi).toHaveBeenCalledWith(
        "/notes/",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining("encrypted_My private text"),
        }),
      );
    });
  });
});
