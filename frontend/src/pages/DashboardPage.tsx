import { AdminDashboard } from "../components/dashboard/AdminDashboard";
import { ContributorDashboard } from "../components/dashboard/ContributorDashboard";
import { useAuth } from "../features/auth/AuthContext";

export function DashboardPage() {
  const { user } = useAuth();

  if (user?.is_staff) {
    return <AdminDashboard />;
  }

  return <ContributorDashboard />;
}

export default DashboardPage;
