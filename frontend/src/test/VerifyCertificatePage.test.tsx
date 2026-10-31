import {
  cleanup,
  fireEvent,
  render,
  screen,
  act,
} from "@testing-library/react";
import { Link, MemoryRouter, Route, Routes } from "react-router-dom";
import { VerifyCertificatePage } from "../pages/VerifyCertificatePage";
import { fetchApi } from "../lib/api";
import { ApiError } from "../lib/apiErrors";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../lib/api", () => ({ fetchApi: vi.fn() }));
const fetchCertificate = vi.mocked(fetchApi);
const valid = (hash = "123") => ({
  is_valid: true,
  certificate: {
    verification_hash: hash,
    course_name: "React Mastery",
    issued_at: "2026-06-08T00:00:00Z",
    learner_name: "John Doe",
    is_active: true,
  },
});
function page(path = "/verify/123") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Link to="/verify/456">Next certificate</Link>
      <Routes>
        <Route path="/verify/:hash?" element={<VerifyCertificatePage />} />
      </Routes>
    </MemoryRouter>,
  );
}
beforeEach(() => {
  fetchCertificate.mockReset();
});

afterEach(cleanup);

// Settle mocked API promises inside React's act; the shared setup owns the fake clock.
async function findText(value: string | RegExp) {
  await act(async () => {});
  return screen.getByText(value);
}

describe("certificate verification", () => {
  it("renders loading during a pending request", () => {
    fetchCertificate.mockReturnValue(new Promise(() => {}));
    page("/verify/123");
    expect(screen.getByTestId("loading-skeleton")).toBeInTheDocument();
  });
  it("renders typed API certificate fields", async () => {
    fetchCertificate.mockResolvedValue(valid());
    page("/verify/123");
    expect(await findText("John Doe")).toBeInTheDocument();
    expect(screen.getByText("React Mastery")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(fetchCertificate).toHaveBeenCalledWith(
      "/progress/verify/123/",
      expect.objectContaining({
        requireAuth: false,
        suppressErrorToast: true,
      }),
    );
  });
  it("distinguishes a 404 from a service outage", async () => {
    fetchCertificate.mockRejectedValue(
      new ApiError("Not found", { status: 404 }),
    );
    page("/verify/123");
    expect(await findText("Certificate Not Found")).toBeInTheDocument();
    expect(screen.getByText(/Check the copied link/)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Retry verification" }),
    ).not.toBeInTheDocument();
  });
  it("retries a 503 and recovers on success", async () => {
    fetchCertificate
      .mockRejectedValueOnce(new ApiError("Server error", { status: 503 }))
      .mockResolvedValueOnce(valid());
    page("/verify/123");
    expect(
      await findText("Verification Temporarily Unavailable"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/does not mean the certificate is invalid/),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry verification" }));
    expect(await findText("John Doe")).toBeInTheDocument();
    expect(fetchCertificate).toHaveBeenCalledTimes(2);
  });
  it("rejects malformed input without calling the API", async () => {
    page("/verify/bad%3Fhash");
    expect(await findText("Invalid Certificate Link")).toBeInTheDocument();
    expect(fetchCertificate).not.toHaveBeenCalled();
  });
  it("never presents a revoked certificate as valid", async () => {
    fetchCertificate.mockResolvedValue({ ...valid(), is_valid: false });
    page("/verify/123");
    expect(await findText("Revoked Certificate")).toBeInTheDocument();
    expect(screen.queryByText("Verified Certificate")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Certificate of Completion"),
    ).not.toBeInTheDocument();
  });
  it("handles a malformed successful API response", async () => {
    fetchCertificate.mockResolvedValue({
      is_valid: true,
      certificate: { broken: "payload" },
    });
    page("/verify/123");
    expect(
      await findText("Verification Temporarily Unavailable"),
    ).toBeInTheDocument();
  });
  it("does not fetch a missing hash", async () => {
    page("/verify");
    expect(await findText("Certificate Verification")).toBeInTheDocument();
    expect(fetchCertificate).not.toHaveBeenCalled();
  });
});
it("validates the lookup form and trims a copied hash", async () => {
  fetchCertificate.mockResolvedValue(valid());
  page("/verify");
  fireEvent.change(
    screen.getByRole("textbox", { name: "Certificate verification hash" }),
    { target: { value: "   " } },
  );
  fireEvent.click(screen.getByRole("button", { name: "Verify" }));
  expect(screen.getByRole("alert")).toHaveTextContent(
    "Please enter a valid certificate hash",
  );
  expect(fetchCertificate).not.toHaveBeenCalled();
  fireEvent.change(screen.getByRole("textbox"), { target: { value: " 123 " } });
  fireEvent.click(screen.getByRole("button", { name: "Verify" }));
  expect(await findText("John Doe")).toBeInTheDocument();
});
it("ignores late data for the previous route hash", async () => {
  let resolveOld!: (value: unknown) => void;
  fetchCertificate
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveOld = resolve;
        }),
    )
    .mockResolvedValueOnce(valid("456"));
  page();
  fireEvent.click(screen.getByRole("link", { name: "Next certificate" }));
  expect(await findText("John Doe")).toBeInTheDocument();
  await act(async () => {
    resolveOld({
      ...valid(),
      certificate: { ...valid().certificate, learner_name: "Stale user" },
    });
  });
  expect(screen.queryByText("Stale user")).not.toBeInTheDocument();
  expect(screen.getByText("John Doe")).toBeInTheDocument();
});
