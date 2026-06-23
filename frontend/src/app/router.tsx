import React from "react";
import { Route, Routes, Navigate } from "react-router-dom";
import { AppLayout } from "../components/layout/AppLayout";
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
import { SandboxPage } from "../pages/SandboxPage";
import { ProfileSettingsPage } from "../pages/ProfileSettingsPage";
import { VerifyCertificatePage } from "../pages/VerifyCertificatePage";
import { useAuth } from "../features/auth/AuthContext";
import SkeletonLesson from "../components/ui/skeletons/SkeletonLesson";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
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

  if (!isAuthenticated) return <Navigate to="/" replace />;

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
          element={
            <ProtectedRoute>
              <SandboxPage />
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

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
