import { useEffect, useState } from "react";
import { useGoogleLogin } from "@react-oauth/google";
import { Github } from "lucide-react";
import { fetchApi } from "../lib/api";
import { useAuth } from "../features/auth/AuthContext";
import OrganizationsGrid from "../components/OrganizationsGrid";

const githubAuthUrl =
  import.meta.env.VITE_GITHUB_OAUTH_URL ||
  `${import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api"}/auth/github/`;

function getErrorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export function LandingPage() {
  const { login } = useAuth();
  const [authRole, setAuthRole] = useState<"student" | "admin">("student");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const authError = new URLSearchParams(window.location.search).get(
      "auth_error",
    );
    if (authError) {
      setError(authError);
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, []);

  const handleStandardLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const tokens = await fetchApi("/auth/login/", {
        method: "POST",
        requireAuth: false,
        body: JSON.stringify({ username: email, password }), // Using email field as username logic for backend ease
      });
      login(tokens);
      window.location.href = "/dashboard";
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Failed to login"));
    }
  };

  const handleGithubSignIn = () => {
    window.location.href = githubAuthUrl;
  };

  const googleLoginHandler = useGoogleLogin({
    onSuccess: async (tokenResponse) => {
      try {
        const tokens = await fetchApi("/auth/google/", {
          method: "POST",
          requireAuth: false,
          body: JSON.stringify({ access_token: tokenResponse.access_token }),
        });
        login(tokens);
        window.location.href = "/dashboard";
      } catch (err: unknown) {
        setError(getErrorMessage(err, "Google Auth Failed. Check Backend."));
      }
    },
    onError: () => {
      setError("Google Login Failed / Cancelled.");
    },
  });

  return (
    <div className="min-h-[85vh] flex items-center justify-center p-4">
      <div className="w-full max-w-lg mx-auto">
        <div className="text-center mb-8">
          <span className="font-black text-sm bg-accent text-black px-4 py-2 rounded-full border-2 border-black rotate-[-2deg] inline-block shadow-sm">
            AUTHORIZED ACCESS ONLY 🔒
          </span>
        </div>

        <div className="bg-white rounded-[2rem] border-4 border-black shadow-card-lg p-6 sm:p-10 relative">
          <div className="flex gap-2 p-1 bg-surface-low rounded-lg border-2 border-black mb-6">
            <button
              onClick={() => setAuthRole("student")}
              className={`flex-1 py-2 font-bold rounded-lg transition-all border-2 ${
                authRole === "student"
                  ? "bg-white border-black shadow-card-sm -translate-y-0.5"
                  : "border-transparent text-muted hover:text-text"
              }`}
            >
              Contributor
            </button>
            <button
              onClick={() => setAuthRole("admin")}
              className={`flex-1 py-2 font-bold rounded-lg transition-all border-2 ${
                authRole === "admin"
                  ? "bg-white border-black shadow-card-sm -translate-y-0.5"
                  : "border-transparent text-muted hover:text-text"
              }`}
            >
              Maintainer
            </button>
          </div>

          <h2 className="text-3xl font-black mb-6 text-center">
            {authRole === "student"
              ? "Enter the Sandbox."
              : "Maintainer Login."}
          </h2>

          {error && (
            <div className="text-black font-bold text-sm bg-primary p-3 rounded-lg border-4 border-black shadow-card-sm mb-4">
              {error}
            </div>
          )}
          <OrganizationsGrid />
          <form onSubmit={handleStandardLogin} className="space-y-4">
            <button
              type="button"
              onClick={() => googleLoginHandler()}
              className="w-full bg-white border-4 border-black rounded-2xl p-4 flex items-center justify-center gap-3 font-bold hover:bg-surface-low transition-colors shadow-card-sm active:translate-y-1 active:shadow-none"
            >
              <svg className="w-6 h-6" viewBox="0 0 24 24" aria-hidden="true">
                <path
                  fill="#4285F4"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="#34A853"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="#FBBC05"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                />
                <path
                  fill="#EA4335"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                />
              </svg>
              Sign in with Google
            </button>

            <button
              type="button"
              onClick={handleGithubSignIn}
              className="group relative w-full overflow-hidden bg-black text-white border-4 border-black rounded-lg p-4 flex items-center justify-center gap-3 font-black shadow-card-sm transition-all duration-300 hover:-translate-y-1 hover:bg-text hover:shadow-card-lg active:translate-y-1 active:shadow-none uppercase before:absolute before:inset-0 before:-translate-x-full before:bg-gradient-to-r before:from-transparent before:via-white/25 before:to-transparent before:transition-transform before:duration-500 hover:before:translate-x-full"
              aria-label="Sign in with GitHub"
            >
              <Github
                className="relative h-6 w-6 transition-transform duration-300 group-hover:rotate-[-8deg] group-hover:scale-110"
                strokeWidth={2.75}
                aria-hidden="true"
              />
              <span className="relative">Sign in with GitHub</span>
            </button>

            <div className="flex items-center gap-4 my-6">
              <div className="flex-1 h-1 bg-black"></div>
              <span className="font-black text-muted text-sm uppercase">
                OR
              </span>
              <div className="flex-1 h-1 bg-black"></div>
            </div>

            <div>
              <input
                className="w-full rounded-lg border-4 border-black bg-surface-lowest px-4 py-4 text-text font-bold outline-none placeholder:text-muted/60 focus:bg-surface-low focus:ring-0 transition-colors shadow-sm"
                placeholder="Username or Email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div>
              <input
                className="w-full rounded-lg border-4 border-black bg-surface-lowest px-4 py-4 text-text font-bold outline-none placeholder:text-muted/60 focus:bg-surface-low focus:ring-0 transition-colors shadow-sm"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            <button
              type="submit"
              className="w-full rounded-2xl border-4 border-black bg-primary px-5 py-4 font-black text-black text-xl shadow-card hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-card-sm transition-all uppercase tracking-wide mt-4 cursor-pointer"
            >
              Assemble & Run!
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
