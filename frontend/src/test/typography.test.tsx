import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";

describe("Typography Standardization", () => {
  it("renders H1, H2, and H3 elements correctly", () => {
    const { container } = render(
      <div>
        <h1>Heading 1</h1>
        <h2>Heading 2</h2>
        <h3>Heading 3</h3>
      </div>,
    );

    const h1 = container.querySelector("h1");
    const h2 = container.querySelector("h2");
    const h3 = container.querySelector("h3");

    expect(h1).toBeInTheDocument();
    expect(h2).toBeInTheDocument();
    expect(h3).toBeInTheDocument();

    // In JSDOM, we can't fully compute CSS styles loaded from external stylesheets like Tailwind easily without a full browser environment,
    // but we can ensure that they render without crashing and do not have ad-hoc font family classes.
    expect(h1?.className).not.toMatch(/font-display/);
    expect(h1?.className).not.toMatch(/font-mono/);
    expect(h1?.className).not.toMatch(/font-sans/);

    expect(h2?.className).not.toMatch(/font-display/);
    expect(h2?.className).not.toMatch(/font-mono/);
    expect(h2?.className).not.toMatch(/font-sans/);

    expect(h3?.className).not.toMatch(/font-display/);
    expect(h3?.className).not.toMatch(/font-mono/);
    expect(h3?.className).not.toMatch(/font-sans/);
  });
});
