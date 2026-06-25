import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RichTextEditor } from "../components/ui/RichTextEditor";

// Mock the SimpleMdeReact component to avoid loading actual CodeMirror in JSDOM,
// which can sometimes cause layout measurement errors in simple test environments.
vi.mock("react-simplemde-editor", () => ({
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  default: ({ value, onChange, options }: any) => (
    <div data-testid="mock-mde">
      <textarea
        data-testid="mock-mde-textarea"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={options.placeholder}
      />
      <div data-testid="mock-mde-options">{JSON.stringify(options)}</div>
    </div>
  ),
}));

describe("RichTextEditor Component", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders correctly with given value and placeholder", () => {
    const handleChange = vi.fn();
    render(
      <RichTextEditor
        value="Hello **World**"
        onChange={handleChange}
        placeholder="Enter markdown..."
      />,
    );

    expect(screen.getByTestId("mock-mde")).toBeInTheDocument();

    const textarea = screen.getByTestId("mock-mde-textarea");
    expect(textarea).toHaveValue("Hello **World**");
    expect(textarea).toHaveAttribute("placeholder", "Enter markdown...");
  });

  it("calls onChange when typing", async () => {
    const handleChange = vi.fn();
    render(<RichTextEditor value="" onChange={handleChange} />);

    const textarea = screen.getByTestId("mock-mde-textarea");
    fireEvent.change(textarea, { target: { value: "Testing 123" } });

    // Check if the mock onChange was called correctly (each character triggers a change in our mock)
    expect(handleChange).toHaveBeenCalled();
  });

  it("renders character count when maxLength is provided", () => {
    render(<RichTextEditor value="Test" onChange={() => {}} maxLength={10} />);
    expect(screen.getByText("4 / 10 characters")).toBeInTheDocument();
  });

  it("highlights character count in red when exceeding maxLength", () => {
    render(
      <RichTextEditor
        value="This is too long"
        onChange={() => {}}
        maxLength={10}
      />,
    );
    const countText = screen.getByText("16 / 10 characters");
    expect(countText).toHaveClass("text-red-600");
  });

  it("applies disabled styles when disabled prop is true", () => {
    render(<RichTextEditor value="" onChange={() => {}} disabled={true} />);
    const wrapper = screen.getByTestId("rich-text-editor");
    expect(wrapper).toHaveClass("opacity-60 pointer-events-none");
  });

  it("configures toolbar options correctly", () => {
    render(<RichTextEditor value="" onChange={() => {}} />);
    const optionsBlock = screen.getByTestId("mock-mde-options");
    const optionsJSON = JSON.parse(optionsBlock.textContent || "{}");

    expect(optionsJSON.spellChecker).toBe(false);
    expect(optionsJSON.toolbar).toContain("bold");
    expect(optionsJSON.toolbar).toContain("heading");
    expect(optionsJSON.toolbar).toContain("preview");
  });
});
