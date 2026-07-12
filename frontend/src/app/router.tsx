import React, { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "../components/layout/AppLayout";
import { PublicLayout } from "../components/layout/PublicLayout";
import { GitTerminal } from "../components/ui/GitTerminal";
import SkeletonLesson from "../components/ui/skeletons/SkeletonLesson";
import { TerminalReplay } from "../components/ui/TerminalReplay";
import { useAuth } from "../features/auth/AuthContext";

/*
 * Route components are loaded only when their route is visited.
 * Most pages in this project use named exports, so their imports
 * are mapped to the default export shape required by React.lazy().
 */

const ChallengePage = lazy(() =>
  import("../pages/ChallengePage").then((module) => ({
    default: module.ChallengePage,
  })),
);

const ChatPage = lazy(() =>
  import("../pages/ChatPage").then((module) => ({
    default: module.ChatPage,
  })),
);

const CommunityPage = lazy(() =>
  import("../pages/CommunityPage").then((module) => ({
    default: module.CommunityPage,
  })),
);

const DashboardPage = lazy(() =>
  import("../pages/DashboardPage").then((module) => ({
    default: module.DashboardPage,
  })),
);

const GitHubAuthCallbackPage = lazy(() =>
  import("../pages/GitHubAuthCallbackPage").then((module) => ({
    default: module.GitHubAuthCallbackPage,
  })),
);

const LandingPage = lazy(() =>
  import("../pages/LandingPage").then((module) => ({
    default: module.LandingPage,
  })),
);

const LoginPage = lazy(() =>
  import("../pages/LoginPage").then((module) => ({
    default: module.LoginPage,
  })),
);

const SignupPage = lazy(() =>
  import("../pages/SignupPage").then((module) => ({
    default: module.SignupPage,
  })),
);

const LessonPage = lazy(() =>
  import("../pages/LessonPage").then((module) => ({
    default: module.LessonPage,
  })),
);

const NotFoundPage = lazy(() =>
  import("../pages/NotFoundPage").then((module) => ({
    default: module.NotFoundPage,
  })),
);

const ServerErrorPage = lazy(() =>
  import("../pages/ServerErrorPage").then((module) => ({
    default: module.ServerErrorPage,
  })),
);

const ModerationDashboard = lazy(() =>
  import("../pages/ModerationDashboard").then((module) => ({
    default: module.ModerationDashboard,
  })),
);

const SandboxPage = lazy(() =>
  import("../pages/SandboxPage").then((module) => ({
    default: module.SandboxPage,
  })),
);

const ContributorSandboxPage = lazy(() =>
  import("../pages/ContributorSandboxPage").then((module) => ({
    default: module.ContributorSandboxPage,
  })),
);

const ProfileSettingsPage = lazy(() =>
  import("../pages/ProfileSettingsPage").then((module) => ({
    default: module.ProfileSettingsPage,
  })),
);

const LeaderboardPage = lazy(() =>
  import("../pages/LeaderboardPage").then((module) => ({
    default: module.LeaderboardPage,
  })),
);

const VerifyCertificatePage = lazy(() =>
  import("../pages/VerifyCertificatePage").then((module) => ({
    default: module.VerifyCertificatePage,
  })),
);

const PeerReviewPage = lazy(() =>
  import("../pages/PeerReviewPage").then((module) => ({
    default: module.PeerReviewPage,
  })),
);

const PathwayPage = lazy(() =>
  import("../pages/PathwayPage").then((module) => ({
    default: module.PathwayPage,
  })),
);

const LearningPathPage = lazy(() =>
  import("../pages/LearningPathPage").then((module) => ({
    default: module.LearningPathPage,
  })),
);

/*
 * These pages use default exports, so they can be passed directly
 * to React.lazy().
 */
const AnalyticsDashboardPage = lazy(
  () => import("../pages/AnalyticsDashboardPage"),
);

const TemplateMarketplacePage = lazy(
  () => import("../pages/TemplateMarketplacePage"),
);

function RouteLoadingFallback() {
  return (
    <div
      className="flex min-h-screen w-full items-center justify-center"
      aria-busy="true"
      aria-label="Loading page"
      role="status"
    >
      <div className="w-full max-w-3xl px-4">
        <SkeletonLesson />
      </div>
    </div>
  );
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

function PublicOnlyRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <RouteLoadingFallback />;
  }

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}

export function AppRouter() {
  return (
    <Suspense fallback={<RouteLoadingFallback />}>
      <Routes>
        {/* Public Routes with Animation Layout */}
        <Route element={<PublicLayout />}>
          {/* Standalone Route without AppLayout (No Navbar) */}
          <Route
            path="/"
            element={
              <PublicOnlyRoute>
                <LandingPage />
              </PublicOnlyRoute>
            }
          />

          <Route
            path="/auth/github/callback"
            element={<GitHubAuthCallbackPage />}
          />

          {/* Public auth routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/verify" element={<VerifyCertificatePage />} />
          <Route
            path="/verify/:hash"
            element={<VerifyCertificatePage />}
          />
          
          <Route path="/500" element={<ServerErrorPage />} />

          <Route path="*" element={<NotFoundPage />} />
        </Route>

        {/* Authenticated Routes with Navbar Layout */}
        <Route element={<AppLayout />}>
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <DashboardPage />
              </ProtectedRoute>
            }
          />

          <Route
            path="/leaderboard"
            element={
              <ProtectedRoute>
                <LeaderboardPage />
              </ProtectedRoute>
            }
          />

          <Route
            path="/analytics"
            element={
              <ProtectedRoute>
                <AnalyticsDashboardPage />
              </ProtectedRoute>
            }
          />

          <Route
            path="/pathway"
            element={
              <ProtectedRoute>
                <PathwayPage />
              </ProtectedRoute>
            }
          />

          <Route
            path="/learning-path"
            element={
              <ProtectedRoute>
                <LearningPathPage />
              </ProtectedRoute>
            }
          />

          <Route
            path="/lessons/:slug"
            element={
              <ProtectedRoute>
                <LessonPage />
              </ProtectedRoute>
            }
          />

          <Route
            path="/chat"
            element={
              <ProtectedRoute>
                <ChatPage />
              </ProtectedRoute>
            }
          />

          <Route
            path="/challenges"
            element={
              <ProtectedRoute>
                <ChallengePage />
              </ProtectedRoute>
            }
          />

          <Route
            path="/community"
            element={
              <ProtectedRoute>
                <CommunityPage />
              </ProtectedRoute>
            }
          />

          <Route path="/sandbox" element={<SandboxPage />} />

          <Route
            path="/contributor-sandbox"
            element={
              <ProtectedRoute>
                <ContributorSandboxPage />
              </ProtectedRoute>
            }
          />

          <Route
            path="/test-terminal"
            element={
              <div className="flex h-screen gap-8 bg-[#0a0a0a] p-10">
                <div className="flex h-[600px] flex-1 flex-col">
                  <h2 className="mb-4 text-xl font-bold text-white">
                    Interactive Git Terminal
                  </h2>

                  <GitTerminal />
                </div>

                <div className="flex h-[600px] flex-1 flex-col">
                  <h2 className="mb-4 text-xl font-bold text-white">
                    Interactive Terminal Replay
                  </h2>

                  <TerminalReplay
                    sessionName="Git Tutorial Replay"
                    commands={[
                      {
                        command: "git init",
                        output:
                          "Initialized empty Git repository in /workspace/.git/",
                        typingDelayMs: 60,
                        executionDelayMs: 400,
                      },
                      {
                        command: "git add .",
                        output: "",
                        typingDelayMs: 50,
                        executionDelayMs: 300,
                      },
                      {
                        command: "git commit -m 'Initial commit'",
                        output:
                          "[main (root-commit) 1a2b3c4] Initial commit\n" +
                          " 3 files changed, 120 insertions(+)\n" +
                          " create mode 100644 index.js\n" +
                          " create mode 100644 package.json",
                        typingDelayMs: 60,
                        executionDelayMs: 800,
                      },
                      {
                        command: "npm run test",
                        output:
                          "Running tests...\n" +
                          "PASS  src/test/app.test.js\n" +
                          "Test Suites: 1 passed, 1 total\n" +
                          "Tests:       3 passed, 3 total\n" +
                          "Snapshots:   0 total\n" +
                          "Time:        1.2s",
                        typingDelayMs: 50,
                        executionDelayMs: 1200,
                      },
                      {
                        command: "git status",
                        output:
                          "On branch main\n" +
                          "nothing to commit, working tree clean",
                        typingDelayMs: 60,
                        executionDelayMs: 500,
                      },
                    ]}
                  />
                </div>
              </div>
            }
          />

          <Route
            path="/templates"
            element={
              <ProtectedRoute>
                <TemplateMarketplacePage />
              </ProtectedRoute>
            }
          />

          <Route
            path="/peer-review"
            element={
              <ProtectedRoute>
                <PeerReviewPage />
              </ProtectedRoute>
            }
          />

          <Route
            path="/moderation"
            element={
              <ProtectedRoute>
                <ModerationDashboard />
              </ProtectedRoute>
            }
          />

          <Route
            path="/profile"
            element={
              <ProtectedRoute>
                <ProfileSettingsPage />
              </ProtectedRoute>
            }
          />
        </Route>

        {/* Existing standalone routes preserved */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/verify" element={<VerifyCertificatePage />} />
        <Route
          path="/verify/:hash"
          element={<VerifyCertificatePage />}
        />
        <Route path="/500" element={<ServerErrorPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Suspense>
  );
}