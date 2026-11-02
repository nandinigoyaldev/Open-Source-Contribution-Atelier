import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import SkeletonCard from "./SkeletonCard";
import UiSkeletonCard from "./ui/skeletons/SkeletonCard";

describe("SkeletonCard shimmer", () => {
  it.each(["stats", "chart", "badge", "activity"] as const)(
    "uses the transform-based shimmer for the %s variant",
    (variant) => {
      const { container } = render(<SkeletonCard variant={variant} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass("skeleton-shimmer");
      expect(card).not.toHaveClass("animate-pulse");
    },
  );

  it("renders every card in a multi-card grid with the shimmer", () => {
    const { container } = render(<SkeletonCard count={8} />);
    expect(container.querySelectorAll(".skeleton-shimmer")).toHaveLength(8);
  });

  it("uses the transform-based shimmer in the ui skeleton card", () => {
    const { container } = render(<UiSkeletonCard />);
    const card = container.firstChild as HTMLElement;
    expect(card).toHaveClass("skeleton-shimmer");
    expect(card).not.toHaveClass("animate-pulse");
  });
});
