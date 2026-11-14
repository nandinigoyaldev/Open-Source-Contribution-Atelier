import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { InvoiceHistoryPage } from "../pages/settings/InvoiceHistoryPage";
import { fetchApi } from "../lib/api";

vi.mock("../lib/api", () => ({ fetchApi: vi.fn() }));
vi.mock("react-hot-toast", () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));
vi.mock("../lib/authToken", () => ({ getAccessToken: () => "test-token" }));
const api = vi.mocked(fetchApi);
const invoice = {
  id: 1,
  stripe_invoice_id: "in_123",
  amount: "12.50",
  status: "paid",
  pdf_url: null,
  created_at: "2026-10-01T00:00:00Z",
};
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}
async function openPage() {
  await act(async () => {
    render(<InvoiceHistoryPage />);
  });
}
beforeEach(() => {
  api.mockReset();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Invoice history recovery", () => {
  it("announces a pending request separately from empty history", async () => {
    const request = deferred<unknown>();
    api.mockReturnValue(request.promise);
    render(<InvoiceHistoryPage />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading billing statement history",
    );
    expect(screen.queryByText(/No billing statements/)).not.toBeInTheDocument();
    await act(async () => {
      request.resolve([]);
    });
    expect(screen.getByRole("status")).toHaveTextContent(
      "No billing statements",
    );
  });
  it("renders invoice details after successful loading", async () => {
    api.mockResolvedValue([invoice]);
    await openPage();
    expect(screen.getByText("in_123")).toBeInTheDocument();
    expect(screen.getByText("$12.50")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Download invoice in_123 PDF" }),
    ).toBeInTheDocument();
    expect(api).toHaveBeenCalledWith(
      "/billing/invoices/",
      expect.objectContaining({
        maxRetries: 0,
        suppressErrorToast: true,
        signal: expect.any(AbortSignal),
      }),
    );
  });
  it("shows an error rather than claiming there are no invoices", async () => {
    api.mockRejectedValue(new Error("503"));
    await openPage();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "couldn’t load your invoices",
    );
    expect(screen.queryByText(/No billing statements/)).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Back to Billing" }),
    ).toHaveAttribute("href", "/settings/billing");
  });
  it("recovers on retry and rejects duplicate clicks while pending", async () => {
    const retry = deferred<unknown>();
    api
      .mockRejectedValueOnce(new Error("offline"))
      .mockReturnValueOnce(retry.promise);
    await openPage();
    const button = screen.getByRole("button", {
      name: "Retry loading invoices",
    });
    await act(async () => {
      button.click();
      button.click();
    });
    expect(api).toHaveBeenCalledTimes(2);
    expect(screen.getByRole("status")).toHaveTextContent("Loading");
    expect(
      screen.queryByRole("button", { name: "Retry loading invoices" }),
    ).not.toBeInTheDocument();
    await act(async () => {
      retry.resolve([invoice]);
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByText("in_123")).toBeInTheDocument();
  });
  it("can retry again after another failure", async () => {
    api.mockRejectedValue(new Error("offline"));
    await openPage();
    await act(async () => {
      fireEvent.click(
        screen.getByRole("button", { name: "Retry loading invoices" }),
      );
    });
    expect(api).toHaveBeenCalledTimes(2);
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
  it("preserves paginated responses and uses the authenticated API path for the next page", async () => {
    api
      .mockResolvedValueOnce({
        results: [invoice],
        next: "https://api.example.test/api/billing/invoices/?page=2",
        previous: null,
      })
      .mockResolvedValueOnce({
        results: [{ ...invoice, id: 2, stripe_invoice_id: "in_456" }],
        next: null,
        previous: "?page=1",
      });
    await openPage();
    expect(
      screen.getByRole("button", { name: "Previous invoices" }),
    ).toBeDisabled();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Next invoices" }));
    });
    expect(api).toHaveBeenLastCalledWith(
      "/billing/invoices/?page=2",
      expect.any(Object),
    );
    expect(screen.getByText("in_456")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Next invoices" }),
    ).toBeDisabled();
  });
  it("handles an invalid successful response as a retryable error", async () => {
    api.mockResolvedValue({ message: "unexpected" });
    await openPage();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
  it("aborts the request when the page unmounts", () => {
    api.mockReturnValue(new Promise(() => {}));
    const page = render(<InvoiceHistoryPage />);
    const signal = api.mock.calls[0][1]?.signal;
    page.unmount();
    expect(signal?.aborted).toBe(true);
  });
});
