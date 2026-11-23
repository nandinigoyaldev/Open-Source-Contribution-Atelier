import {
  render,
  screen,
  fireEvent,
  cleanup,
  within,
} from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { FeatureFlagsPage } from "../pages/admin/FeatureFlagsPage";
import { describeRollout, type FeatureFlagSummary } from "../lib/featureFlags";
import * as authContextModule from "../features/auth/AuthContext";
import * as apiModule from "../lib/api";

vi.mock("react-hot-toast", () => {
  const toastMock = { success: vi.fn(), error: vi.fn() };
  return { default: toastMock, toast: toastMock };
});

const flag = (overrides: Partial<FeatureFlagSummary>): FeatureFlagSummary => ({
  id: 1,
  name: "new_editor",
  description: "",
  flag_type: "boolean",
  is_active: true,
  kill_switch: false,
  default_value: false,
  rollout_percentage: 0,
  environments: [],
  applies_in_current_environment: true,
  target_users_count: 0,
  target_organizations_count: 0,
  updated_at: "2026-11-20T10:00:00Z",
  ...overrides,
});

const flags = [
  flag({
    id: 1,
    name: "checkout_v2",
    flag_type: "percentage",
    rollout_percentage: 25,
    environments: ["staging", "production"],
    target_users_count: 2,
  }),
  flag({
    id: 2,
    name: "beta_search",
    flag_type: "organization",
    target_organizations_count: 3,
    environments: ["staging"],
    applies_in_current_environment: false,
  }),
];

const mockAuth = (isStaff: boolean) =>
  vi.spyOn(authContextModule, "useAuth").mockReturnValue({
    user: {
      id: 1,
      username: "admin",
      email: "a@example.com",
      is_staff: isStaff,
    },
    isAuthenticated: true,
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
    checkUser: vi.fn().mockResolvedValue(undefined),
  } as any);

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.restoreAllMocks();
  fetchMock = vi.fn(async (endpoint: string, options?: RequestInit) => {
    if (endpoint === "/feature-flags/") return flags;
    if (endpoint === "/feature-flags/1/kill-switch/") {
      const body = JSON.parse(String(options?.body));
      return {
        status: "updated",
        flag: { ...flags[0], kill_switch: body.engaged },
      };
    }
    throw new Error(`unexpected ${endpoint}`);
  });
  vi.spyOn(apiModule, "fetchApi").mockImplementation(fetchMock as any);
});

afterEach(() => {
  cleanup();
});

describe("FeatureFlagsPage", () => {
  it("shows scope and rollout % for each flag", async () => {
    mockAuth(true);
    render(<FeatureFlagsPage />);

    const checkout = await screen.findByTestId("flag-row-checkout_v2");
    expect(
      within(checkout).getByText("staging, production"),
    ).toBeInTheDocument();
    expect(within(checkout).getByText("2 users")).toBeInTheDocument();
    expect(
      within(checkout).getByText("25% of signed-in users, plus 2 users"),
    ).toBeInTheDocument();
    expect(within(checkout).getByRole("progressbar")).toHaveAttribute(
      "aria-valuenow",
      "25",
    );

    const search = screen.getByTestId("flag-row-beta_search");
    expect(
      within(search).getByText("Not this environment"),
    ).toBeInTheDocument();
    expect(
      within(search).getByText("Not enabled in this environment"),
    ).toBeInTheDocument();
    expect(within(search).getByText("3 organizations")).toBeInTheDocument();
  });

  it("engages the kill switch with a reason and shows the flag as killed", async () => {
    mockAuth(true);
    vi.spyOn(window, "prompt").mockReturnValue("incident 42");
    render(<FeatureFlagsPage />);

    const row = await screen.findByTestId("flag-row-checkout_v2");
    fireEvent.click(within(row).getByRole("button", { name: /kill switch/i }));

    expect(
      await within(row).findByRole("button", { name: /release kill switch/i }),
    ).toBeInTheDocument();
    expect(within(row).getByText("Killed")).toBeInTheDocument();
    expect(
      within(row).getByText("Off everywhere (kill switch engaged)"),
    ).toBeInTheDocument();
    const [, options] = fetchMock.mock.calls.find(
      ([endpoint]) => endpoint === "/feature-flags/1/kill-switch/",
    )!;
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body)).toEqual({
      engaged: true,
      reason: "incident 42",
    });
  });

  it("does nothing when the reason prompt is cancelled", async () => {
    mockAuth(true);
    vi.spyOn(window, "prompt").mockReturnValue(null);
    render(<FeatureFlagsPage />);

    const row = await screen.findByTestId("flag-row-checkout_v2");
    fireEvent.click(within(row).getByRole("button", { name: /kill switch/i }));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(within(row).getByText("Active")).toBeInTheDocument();
  });

  it("does not request flags for non-staff users", async () => {
    mockAuth(false);
    render(<FeatureFlagsPage />);

    expect(await screen.findByText("Administrators only")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("describeRollout", () => {
  it("follows the backend order: kill switch, inactive, environment, targets, percentage", () => {
    expect(
      describeRollout(flag({ kill_switch: true, rollout_percentage: 80 })),
    ).toEqual({
      percent: 0,
      label: "Off everywhere (kill switch engaged)",
    });
    expect(
      describeRollout(flag({ is_active: false, default_value: true })),
    ).toEqual({
      percent: 100,
      label: "Inactive, default is on",
    });
    expect(
      describeRollout(
        flag({
          flag_type: "user",
          target_users_count: 1,
          rollout_percentage: 50,
        }),
      ),
    ).toEqual({ percent: null, label: "Only 1 targeted user" });
    expect(describeRollout(flag({}))).toEqual({
      percent: 100,
      label: "Everyone",
    });
  });
});
