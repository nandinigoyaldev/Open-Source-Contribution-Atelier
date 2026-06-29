import { render, screen, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { DashboardPage } from "../pages/DashboardPage";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

// Mock Recharts library to prevent JSDOM layout measuring issues
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="responsive-container">{children}</div>
  ),
  BarChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="bar-chart">{children}</div>
  ),
  Bar: () => <div data-testid="bar" />,
  XAxis: () => <div data-testid="xaxis" />,
  YAxis: () => <div data-testid="yaxis" />,
  CartesianGrid: () => <div data-testid="cartesian-grid" />,
  Tooltip: () => <div data-testid="tooltip" />,
  Legend: () => <div data-testid="legend" />,
  PieChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="pie-chart">{children}</div>
  ),
  Pie: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="pie">{children}</div>
  ),
  Cell: () => <div data-testid="cell" />,
  AreaChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="area-chart">{children}</div>
  ),
  Area: () => <div data-testid="area" />,
}));

// Mock react-router-dom Link component
vi.mock("react-router-dom", () => ({
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
}));

// Mock useAuth context hook
const mockUseAuth = vi.fn();
vi.mock("../features/auth/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

// Mock useBookmarks hook
vi.mock("../hooks/useBookmarks", () => ({
  useBookmarks: () => ({
    bookmarks: [],
    isLoading: false,
    toggleBookmark: { mutate: vi.fn(), isPending: false },
    isBookmarked: vi.fn(),
  }),
}));

// Helper function to render component with fresh React Query Client
function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("DashboardPage Dual-Role Views", () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders Admin Dashboard when user.is_staff is true", async () => {
    // Stub user is staff
    mockUseAuth.mockReturnValue({
      user: {
        id: 1,
        username: "maintainer_jane",
        email: "jane@atelier.com",
        is_staff: true,
      },
    });

    // MSW handlers in src/mocks/handlers.ts already provide the default mock responses
    // for admin analytics and leaderboard.

    renderWithQueryClient(<DashboardPage />);

    // Assert that the Admin View specific sections render
    expect(
      await screen.findByText("MAINTAINER CONTROL PANEL 🛠️"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Project Health & Cohort Monitor"),
    ).toBeInTheDocument();

    // Assert stats blocks
    expect(screen.getByText("System Issues")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument(); // total issues count
    expect(screen.getByText("Solved: 4")).toBeInTheDocument();

    // Assert pending PRs
    expect(screen.getByText("Pending Pull Requests (1)")).toBeInTheDocument();
    expect(screen.getByText("Feature request review")).toBeInTheDocument();
    expect(screen.getByText("@bob_coder")).toBeInTheDocument();
  });

  it("renders Contributor Dashboard when user.is_staff is false", async () => {
    // Stub user is a regular contributor
    mockUseAuth.mockReturnValue({
      user: {
        id: 2,
        username: "bob_coder",
        email: "bob@atelier.com",
        is_staff: false,
      },
    });

    // MSW handlers in src/mocks/handlers.ts already provide the default mock responses
    // for contributor analytics and lessons list.

    renderWithQueryClient(<DashboardPage />);

    expect(await screen.findByText(/LEVEL/)).toBeInTheDocument();
    expect(
      screen.getByText("Welcome to the Atelier, bob_coder."),
    ).toBeInTheDocument();
    expect(screen.getByText(/completed.*course modules/)).toBeInTheDocument();

    // Assert streak, xp, rank, and merged PR cards
    expect(screen.getByText("Streak Days")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("#1")).toBeInTheDocument(); // Rank

    // Assert assigned issues
    expect(screen.getByText("Assigned Issues")).toBeInTheDocument();
    expect(screen.getByText("Fix git conflicts")).toBeInTheDocument();

    // Assert lesson queue
    expect(screen.getByText("Resume Learning Queue")).toBeInTheDocument();
    expect(screen.getByText("Open Source Mindset")).toBeInTheDocument();
  });
});
