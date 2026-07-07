import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import ReportIssueModal from "../../../components/ui/ReportIssueModal";
import api from "../../../api";
import toast from "react-hot-toast";

// Mock the API
vi.mock("../../../api", () => ({
  default: {
    post: vi.fn(),
  },
}));

// Mock toast
vi.mock("react-hot-toast", () => ({
  default: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

describe("ReportIssueModal", () => {
  const mockOnClose = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("does not render when open is false", () => {
    render(<ReportIssueModal open={false} onClose={mockOnClose} />);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("renders when open is true", () => {
    render(<ReportIssueModal open={true} onClose={mockOnClose} />);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Report an Issue")).toBeInTheDocument();
  });

  it("calls onClose when Cancel button is clicked", () => {
    render(<ReportIssueModal open={true} onClose={mockOnClose} />);
    fireEvent.click(screen.getByText("Cancel"));
    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it("submits the form with provided data", async () => {
    (api.post as any).mockResolvedValueOnce({ data: {} });
    render(<ReportIssueModal open={true} onClose={mockOnClose} urlPath="/test-url" />);

    // Find inputs by placeholder or role/label since our component uses `label` but the connection isn't explicit via `htmlFor`. 
    // We can find them by placeholder or text.
    fireEvent.change(screen.getByPlaceholderText("Brief summary of the issue"), { target: { value: "Test Title" } });
    fireEvent.change(screen.getByPlaceholderText("Detailed steps to reproduce the issue..."), { target: { value: "Test Description" } });
    
    // Select Issue Type
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "UI" } });

    fireEvent.click(screen.getByText("Submit Report"));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledTimes(1);
      const formData = (api.post as any).mock.calls[0][1];
      expect(formData.get("title")).toBe("Test Title");
      expect(formData.get("description")).toBe("Test Description");
      expect(formData.get("issue_type")).toBe("UI");
      expect(formData.get("url_path")).toBe("/test-url");
    });
  });

  it("shows an error message if the submission fails", async () => {
    (api.post as any).mockRejectedValueOnce(new Error("Network Error"));
    render(<ReportIssueModal open={true} onClose={mockOnClose} />);

    fireEvent.change(screen.getByPlaceholderText("Brief summary of the issue"), { target: { value: "Test Title" } });
    fireEvent.change(screen.getByPlaceholderText("Detailed steps to reproduce the issue..."), { target: { value: "Test Description" } });

    fireEvent.click(screen.getByText("Submit Report"));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Failed to submit issue. Please try again.");
    });
  });

  it("prevents submission if required fields are missing", async () => {
    render(<ReportIssueModal open={true} onClose={mockOnClose} />);

    fireEvent.click(screen.getByText("Submit Report"));

    await waitFor(() => {
      expect(api.post).not.toHaveBeenCalled();
    });
  });
});
