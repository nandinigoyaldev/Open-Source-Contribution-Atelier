import { render, screen, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { DashboardPage } from "../pages/DashboardPage";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

// Mock Recharts library to prevent JSDOM layout measuring issues
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: any) => (
    <div data-testid="responsive-container">{children}</div>
  ),
  BarChart: ({ children }: any) => (
    <div data-testid="bar-chart">{children}</div>
  ),
  Bar: () => <div data-testid="bar" />,
  XAxis: () => <div data-testid="xaxis" />,
  YAxis: () => <div data-testid="yaxis" />,
  CartesianGrid: () => <div data-testid="cartesian-grid" />,
  Tooltip: () => <div data-testid="tooltip" />,
  Legend: () => <div data-testid="legend" />,
  PieChart: ({ children }: any) => (
    <div data-testid="pie-chart">{children}</div>
  ),
  Pie: ({ children }: any) => <div data-testid="pie">{children}</div>,
  Cell: () => <div data-testid="cell" />,
  AreaChart: ({ children }: any) => (
    <div data-testid="area-chart">{children}</div>
  ),
  Area: () => <div data-testid="area" />,
}));

// Mock react-router-dom Link component
vi.mock("react-router-dom", () => ({
  Link: ({ children, to }: any) => <a href={to}>{children}</a>,
}));

// Mock useAuth context hook
const mockUseAuth = vi.fn();
vi.mock("../features/auth/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

// Mock fetchApi module
const mockFetchApi = vi.fn();
vi.mock("../lib/api", () => ({
  fetchApi: (endpoint: string) => mockFetchApi(endpoint),
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

    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes("curriculum.json")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              modules: [
                {
                  lessons: [
                    {
                      slug: "intro",
                      title: "Open Source Mindset",
                      description:
                        "Understand how open source collaboration works.",
                    },
                  ],
                },
              ],
            }),
        });
      }
      if (url.includes("contributors")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([]),
        });
      }
      return Promise.reject(new Error(`Unknown fetch URL: ${url}`));
    });
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

    // Mock API response for admin analytics and leaderboard
    mockFetchApi.mockImplementation((endpoint: string) => {
      if (endpoint === "/dashboard/admin/") {
        return Promise.resolve({
          system_stats: {
            total_issues: 10,
            solved_issues: 4,
            open_issues: 4,
            in_progress_issues: 2,
            total_prs: 5,
            merged_prs: 3,
            pending_prs: 1,
            closed_prs: 1,
            active_contributors: 2,
          },
          pending_prs: [
            {
              id: 9,
              title: "Feature request review",
              contributor: "bob_coder",
              issue_title: "Add dark mode toggle",
              created_at: "2026-06-01T12:00:00Z",
            },
          ],
        });
      }
      if (endpoint === "/leaderboard/") {
        return Promise.resolve({
          count: 2,
          next: null,
          previous: null,
          results: [
            {
              id: 2,
              username: "bob_coder",
              prs_merged: 2,
              issues_solved: 3,
              xp: 250,
            },
            {
              id: 3,
              username: "alice_dev",
              prs_merged: 1,
              issues_solved: 1,
              xp: 100,
            },
          ],
        });
      }
      return Promise.reject(new Error("Unknown Endpoint"));
    });

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

    // Mock API response for contributor analytics & lessons list
    mockFetchApi.mockImplementation((endpoint: string) => {
      if (endpoint === "/dashboard/contributor/") {
        return Promise.resolve({
          personal_stats: {
            issues_solved: 3,
            prs_merged: 2,
            total_xp: 250,
            streak_days: 4,
            rank: 1,
          },
          assigned_issues: [
            {
              id: 11,
              title: "Fix git conflicts",
              description: "Practice conflict resolution",
              status: "in_progress",
              points: 50,
              created_at: "2026-06-01T10:00:00Z",
            },
          ],
          recent_prs: [
            {
              id: 22,
              title: "Mock PR submission",
              status: "merged",
              issue_title: "Fix git conflicts",
              created_at: "2026-06-01T11:00:00Z",
              merged_at: "2026-06-01T12:00:00Z",
            },
          ],
          progress_tracker: {
            completed_lessons: 2,
            total_lessons: 5,
            completion_percentage: 40,
          },
        });
      }
      if (endpoint === "/content/lessons/") {
        return Promise.resolve([
          {
            slug: "intro",
            title: "Introduction to Atelier",
            summary: "Welcome lesson",
            difficulty: "beginner",
            estimated_minutes: 5,
          },
        ]);
      }
      return Promise.reject(new Error("Unknown Endpoint"));
    });

    renderWithQueryClient(<DashboardPage />);

    expect(await screen.findByText(/LEVEL/)).toBeInTheDocument();
    expect(
      screen.getByText("Welcome to the Atelier, bob_coder."),
    ).toBeInTheDocument();
    expect(screen.getByText(/completed.*lessons/)).toBeInTheDocument();

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
