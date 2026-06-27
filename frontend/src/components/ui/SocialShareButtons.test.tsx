import React from "react";
import { render, screen, cleanup } from "@testing-library/react";
import { describe, it, expect, afterEach } from "vitest";
import { SocialShareButtons } from "./SocialShareButtons";

describe("SocialShareButtons", () => {
  const defaultProps = {
    url: "https://example.com/verify/12345",
    title: "Look at my certificate!",
  };

  afterEach(() => {
    cleanup();
  });

  it("renders Twitter and LinkedIn share buttons", () => {
    render(<SocialShareButtons {...defaultProps} />);

    const twitterBtn = screen.getByLabelText("Share to Twitter/X");
    const linkedinBtn = screen.getByLabelText("Share to LinkedIn");

    expect(twitterBtn).toBeInTheDocument();
    expect(linkedinBtn).toBeInTheDocument();
  });

  it("generates correct Twitter intent URL", () => {
    render(<SocialShareButtons {...defaultProps} />);

    const twitterBtn = screen.getByLabelText("Share to Twitter/X");
    const expectedUrl = `https://twitter.com/intent/tweet?url=${encodeURIComponent(
      defaultProps.url,
    )}&text=${encodeURIComponent(defaultProps.title)}&hashtags=${encodeURIComponent(
      "OpenSource,ContributionAtelier",
    )}`;

    expect(twitterBtn).toHaveAttribute("href", expectedUrl);
    expect(twitterBtn).toHaveAttribute("target", "_blank");
    expect(twitterBtn).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("generates correct LinkedIn share URL", () => {
    render(<SocialShareButtons {...defaultProps} />);

    const linkedinBtn = screen.getByLabelText("Share to LinkedIn");
    const expectedUrl = `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(
      defaultProps.url,
    )}`;

    expect(linkedinBtn).toHaveAttribute("href", expectedUrl);
    expect(linkedinBtn).toHaveAttribute("target", "_blank");
    expect(linkedinBtn).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("allows overriding default hashtags", () => {
    const customHashtags = "CustomTag,Test";
    render(<SocialShareButtons {...defaultProps} hashtags={customHashtags} />);

    const twitterBtn = screen.getByLabelText("Share to Twitter/X");
    const expectedUrl = `https://twitter.com/intent/tweet?url=${encodeURIComponent(
      defaultProps.url,
    )}&text=${encodeURIComponent(defaultProps.title)}&hashtags=${encodeURIComponent(
      customHashtags,
    )}`;

    expect(twitterBtn).toHaveAttribute("href", expectedUrl);
  });
});
