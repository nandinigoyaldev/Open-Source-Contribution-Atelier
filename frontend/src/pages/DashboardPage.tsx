import { usePageMeta } from "../hooks/usePageMeta";
import { AdminDashboard } from "../components/dashboard/AdminDashboard";
import { ContributorDashboard } from "../components/dashboard/ContributorDashboard";
import { useAuth } from "../features/auth/AuthContext";

export function DashboardPage() {
  usePageMeta(
    "Your Atelier dashboard: track learning progress, XP, streaks and recent activity in one place.",
  );
  const { user } = useAuth();

  return user?.is_staff ? <AdminDashboard /> : <ContributorDashboard />;
}
