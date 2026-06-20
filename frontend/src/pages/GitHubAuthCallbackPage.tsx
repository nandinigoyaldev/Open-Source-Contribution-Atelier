import { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../features/auth/AuthContext";

export function GitHubAuthCallbackPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { login } = useAuth();

  useEffect(() => {
    const access = searchParams.get("access");
    const refresh = searchParams.get("refresh");

    if (!access || !refresh) {
      navigate("/?auth_error=GitHub authentication failed.", { replace: true });
      return;
    }

    login({ access, refresh });
    window.location.replace("/dashboard");
  }, [login, navigate, searchParams]);

  return (
    <div className="min-h-[85vh] flex items-center justify-center p-4">
      <div className="rounded-2xl border-4 border-black bg-white px-8 py-6 text-center shadow-card-lg">
        <p className="text-lg font-black uppercase text-black">
          Finishing GitHub sign in...
        </p>
      </div>
    </div>
  );
}
