import React from "react";
import { Route, Routes, Navigate } from "react-router-dom";
import { AppLayout } from "../components/layout/AppLayout";
import { PublicLayout } from "../components/layout/PublicLayout";
import { ChallengePage } from "../pages/ChallengePage";
import { ChatPage } from "../pages/ChatPage";
import { CommunityPage } from "../pages/CommunityPage";
import { DashboardPage } from "../pages/DashboardPage";
import { GitHubAuthCallbackPage } from "../pages/GitHubAuthCallbackPage";
import { LandingPage } from "../pages/LandingPage";
import { LoginPage } from "../pages/LoginPage";
import { SignupPage } from "../pages/SignupPage";
import { LessonPage } from "../pages/LessonPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { ServerErrorPage } from "../pages/ServerErrorPage";
import { SandboxPage } from "../pages/SandboxPage";
import { ProfileSettingsPage } from "../pages/ProfileSettingsPage";
import { LeaderboardPage } from "../pages/LeaderboardPage";
import { VerifyCertificatePage } from "../pages/VerifyCertificatePage";
import { PeerReviewPage } from "../pages/PeerReviewPage";
import { useAuth } from "../features/auth/AuthContext";
import SkeletonLesson from "../components/ui/skeletons/SkeletonLesson";
import { PathwayPage } from "../pages/PathwayPage";
import { LearningPathPage } from "../pages/LearningPathPage";
import AnalyticsDashboardPage from "../pages/AnalyticsDashboardPage";
import TemplateMarketplacePage from "../pages/TemplateMarketplacePage";
import { GitTerminal } from "../components/ui/GitTerminal";
import { TerminalReplay } from "../components/ui/TerminalReplay";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

function PublicOnlyRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div
        className="h-screen w-full flex items-center justify-center"
        aria-busy="true"
        role="status"
      >
        <div className="w-full max-w-3xl">
          <SkeletonLesson />
        </div>
      </div>
    );
  }

  if (isAuthenticated) return <Navigate to="/dashboard" replace />;

  return <>{children}</>;
}

export function AppRouter() {
  return (
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
        <Route path="/verify/:hash" element={<VerifyCertificatePage />} />

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
        <Route
          path="/sandbox"
          element={<SandboxPage />}
        />
        <Route
          path="/test-terminal"
          element={
            <div className="p-10 h-screen bg-[#0a0a0a] flex gap-8">
              <div className="flex-1 flex flex-col h-[600px]">
                <h2 className="text-white mb-4 font-bold text-xl">Interactive Git Terminal</h2>
                <GitTerminal />
              </div>
              <div className="flex-1 flex flex-col h-[600px]">
                <h2 className="text-white mb-4 font-bold text-xl">Interactive Terminal Replay</h2>
                <TerminalReplay
                  sessionName="Git Tutorial Replay"
                  commands={[
                    { command: "git init", output: "Initialized empty Git repository in /workspace/.git/", typingDelayMs: 60, executionDelayMs: 400 },
                    { command: "git add .", output: "", typingDelayMs: 50, executionDelayMs: 300 },
                    { command: "git commit -m 'Initial commit'", output: "[main (root-commit) 1a2b3c4] Initial commit\n 3 files changed, 120 insertions(+)\n create mode 100644 index.js\n create mode 100644 package.json", typingDelayMs: 60, executionDelayMs: 800 },
                    { command: "npm run test", output: "Running tests...\nPASS  src/test/app.test.js\nTest Suites: 1 passed, 1 total\nTests:       3 passed, 3 total\nSnapshots:   0 total\nTime:        1.2s", typingDelayMs: 50, executionDelayMs: 1200 },
                    { command: "git status", output: "On branch main\nnothing to commit, working tree clean", typingDelayMs: 60, executionDelayMs: 500 }
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
          path="/profile"
          element={
            <ProtectedRoute>
              <ProfileSettingsPage />
            </ProtectedRoute>
          }
        />
      </Route>

      {/* Public auth routes */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/verify" element={<VerifyCertificatePage />} />
      <Route path="/verify/:hash" element={<VerifyCertificatePage />} />
      <Route path="/500" element={<ServerErrorPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
