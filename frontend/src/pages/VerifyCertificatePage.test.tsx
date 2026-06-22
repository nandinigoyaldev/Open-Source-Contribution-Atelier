import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { VerifyCertificatePage } from "./VerifyCertificatePage";
import { fetchApi } from "../lib/api";
import { vi, describe, it, expect } from "vitest";

vi.mock("../lib/api", () => ({
  fetchApi: vi.fn(),
}));

describe("VerifyCertificatePage", () => {
  it("renders loading state initially", () => {
    (fetchApi as ReturnType<typeof vi.fn>).mockReturnValue(
      new Promise(() => {}),
    );
    render(
      <MemoryRouter initialEntries={["/verify/123"]}>
        <Routes>
          <Route path="/verify/:hash" element={<VerifyCertificatePage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText("Verifying Certificate...")).toBeInTheDocument();
  });

  it("renders verified certificate data", async () => {
    (fetchApi as ReturnType<typeof vi.fn>).mockResolvedValue({
      is_valid: true,
      certificate: {
        verification_hash: "123",
        course_name: "React Mastery",
        issued_at: "2026-06-08T00:00:00Z",
        learner_name: "John Doe",
      },
    });

    render(
      <MemoryRouter initialEntries={["/verify/123"]}>
        <Routes>
          <Route path="/verify/:hash" element={<VerifyCertificatePage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Verified Certificate")).toBeInTheDocument();
    });
    expect(screen.getByText("John Doe")).toBeInTheDocument();
    expect(screen.getByText("React Mastery")).toBeInTheDocument();
  });

  it("renders invalid certificate error", async () => {
    (fetchApi as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error("Invalid Hash"),
    );

    render(
      <MemoryRouter initialEntries={["/verify/invalid"]}>
        <Routes>
          <Route path="/verify/:hash" element={<VerifyCertificatePage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Invalid Certificate")).toBeInTheDocument();
    });
  });
});
