import { AdminDashboard } from "../components/dashboard/AdminDashboard";
import { ContributorDashboard } from "../components/dashboard/ContributorDashboard";
import { useAuth } from "../features/auth/AuthContext";

export function DashboardPage() {
  const { user } = useAuth();

  return user?.is_staff
    ? <AdminDashboard />
    : <ContributorDashboard />;
}

export default DashboardPage;