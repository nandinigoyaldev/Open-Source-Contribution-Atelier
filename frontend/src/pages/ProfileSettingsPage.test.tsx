import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProfileSettingsPage } from "./ProfileSettingsPage";

vi.mock("../features/auth/ProfileSettingsForm", () => ({
  ProfileSettingsForm: () => <form aria-label="profile form" />,
}));

describe("ProfileSettingsPage", () => {
  it("renders the heading and the settings form", () => {
    render(<ProfileSettingsPage />);
    expect(
      screen.getByRole("heading", { name: /profile settings/i }),
    ).toBeTruthy();
    expect(screen.getByRole("form", { name: "profile form" })).toBeTruthy();
  });
});
