import { useEffect, useState } from "react";
import { useGoogleLogin } from "@react-oauth/google";
import { GitBranch, Moon, Sun } from "lucide-react";
import { fetchApi } from "../lib/api";
import { useAuth } from "../features/auth/AuthContext";
import { useTheme } from "../hooks/useTheme";

const getEnvVar = (key: string): string => {
  if (typeof process !== "undefined" && process.env && process.env[key])
    return process.env[key] as string;
  if (
    typeof import.meta !== "undefined" &&
    import.meta.env &&
    import.meta.env[key]
  )
    return import.meta.env[key] as string;
  return "";
};

function getErrorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export function LandingPage() {
  let login: (tokens: { access: string; refresh: string }) => void = () => {};
  try {
    const auth = useAuth();
    login = auth.login;
  } catch {}

  const { theme, toggleTheme } = useTheme();
  const [authRole, setAuthRole] = useState<"student" | "admin">("student");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [githubUrl, setGithubUrl] = useState("");

  useEffect(() => {
    if (typeof window !== "undefined") {
      const authError = new URLSearchParams(window.location.search).get(
        "auth_error",
      );
      if (authError) {
        setError(authError);
        window.history.replaceState({}, "", window.location.pathname);
      }
      const baseGithub =
        getEnvVar("VITE_GITHUB_OAUTH_URL") ||
        `${getEnvVar("VITE_API_BASE_URL") || "http://localhost:8000/api"}/auth/github/`;
      setGithubUrl(baseGithub);
    }
  }, []);

  const handleStandardLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const tokens = await fetchApi("/auth/login/", {
        method: "POST",
        requireAuth: false,
        body: JSON.stringify({ username: email, password }),
      });
      login(tokens);
      if (typeof window !== "undefined") window.location.href = "/dashboard";
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Login failed. Check your credentials."));
    }
  };

  const handleGithubSignIn = () => {
    if (typeof window !== "undefined" && githubUrl)
      window.location.href = githubUrl;
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
        if (typeof window !== "undefined") window.location.href = "/dashboard";
      } catch {
        setError("Google authentication failed.");
      }
    },
    onError: () => setError("Google login failed"),
  });

  return (
    <div className="min-h-screen md:h-screen md:overflow-hidden bg-surface-lowest dark:bg-[#0a0a0f] text-text transition-colors duration-300 relative flex items-center justify-center p-3 sm:p-6">
      <div className="w-full max-w-5xl grid grid-cols-1 md:grid-cols-2 gap-6 lg:gap-12 items-center">
        {/* Left Side: Headline & Copy with integrated Theme Switcher */}
        <div className="text-center md:text-left space-y-4">
          <div className="flex flex-row items-center justify-center md:justify-start space-x-4 mb-2">
            <span className="font-black text-xs bg-accent text-black px-4 py-2 rounded-full border-2 border-black rotate-[-2deg] inline-block shadow-sm">
              AUTHORIZED ACCESS ONLY
            </span>
            <button
              onClick={toggleTheme}
              aria-label={
                theme === "light"
                  ? "Switch to dark mode"
                  : "Switch to light mode"
              }
              title={
                theme === "light"
                  ? "Switch to dark mode"
                  : "Switch to light mode"
              }
              className="rounded-lg bg-surface-low p-2 text-muted hover:text-text border-2 border-black dark:border-[#4a4238] shadow-card-sm hover:-translate-y-0.5 active:translate-y-0 transition-all dark:bg-[#151411] dark:text-[#c4bbae] dark:hover:text-[#f0ebe2] w-fit toggle-theme"
            >
              {theme === "light" ? <Moon size={16} /> : <Sun size={16} />}
            </button>
          </div>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black text-black dark:text-white tracking-tight leading-none uppercase">
            Contribution
            <br className="hidden md:block" /> Atelier
          </h1>
          <p className="text-muted dark:text-[#9b8f80] text-sm sm:text-base font-bold max-w-md mx-auto md:mx-0">
            Make your first open source contribution with guided mentorship and
            real-world projects.
          </p>
        </div>

        {/* Right Side: Login Card */}
        <div className="w-full max-w-md mx-auto bg-white dark:bg-[#151411] rounded-[2rem] border-4 border-black dark:border-[#4a4238] shadow-card p-4 sm:p-5">
          {/* Contributor / Maintainer Tabs */}
          <div className="flex p-1 bg-surface-low dark:bg-[#0f0e0c] rounded-xl border-2 border-black dark:border-[#4a4238] mb-3">
            <button
              onClick={() => setAuthRole("student")}
              className={`flex-1 py-2 px-4 text-center font-black rounded-lg transition-all text-sm border-2 menu-tab ${
                authRole === "student"
                  ? "bg-white dark:bg-[#1f1c18] border-black dark:border-[#4a4238] shadow-card-sm -translate-y-0.5 text-black dark:text-[#f0ebe2]"
                  : "border-transparent text-muted dark:text-[#9b8f80] hover:text-text dark:hover:text-[#f0ebe2]"
              }`}
            >
              Contributor
            </button>
            <button
              onClick={() => setAuthRole("admin")}
              className={`flex-1 py-2 px-4 text-center font-black rounded-lg transition-all text-sm border-2 menu-tab ${
                authRole === "admin"
                  ? "bg-white dark:bg-[#1f1c18] border-black dark:border-[#4a4238] shadow-card-sm -translate-y-0.5 text-black dark:text-[#f0ebe2]"
                  : "border-transparent text-muted dark:text-[#9b8f80] hover:text-text dark:hover:text-[#f0ebe2]"
              }`}
            >
              Maintainer
            </button>
          </div>

          <h2 className="text-lg font-black mb-3 text-center text-text dark:text-[#f0ebe2]">
            {authRole === "student"
              ? "Start Your First Contribution"
              : "Maintainer Login"}
          </h2>

          {error && (
            <div className="text-black font-bold text-sm bg-primary p-2.5 rounded-lg border-4 border-black shadow-card-sm mb-3">
              {error}
            </div>
          )}

          <div className="space-y-2">
            <button
              type="button"
              onClick={() => googleLoginHandler()}
              className="w-full bg-white border-4 border-black rounded-2xl p-2 flex items-center justify-center gap-3 font-bold text-black hover:bg-surface-low transition-colors shadow-card-sm active:translate-y-1 active:shadow-none text-sm toggle-google"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24">
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
              Continue with Google
            </button>

            <button
              type="button"
              onClick={handleGithubSignIn}
              className="group relative w-full overflow-hidden bg-black text-white border-4 border-black rounded-lg p-2 flex items-center justify-center gap-3 font-black shadow-card-sm transition-all duration-300 hover:-translate-y-1 hover:bg-text hover:shadow-card-lg active:translate-y-1 active:shadow-none uppercase text-sm toggle-github"
            >
              <GitBranch
                className="h-4 w-4 transition-transform duration-300 group-hover:rotate-[-8deg] group-hover:scale-110"
                strokeWidth={2.75}
              />
              Continue with GitHub
            </button>
          </div>

          <div className="flex items-center gap-4 my-3">
            <div className="flex-1 h-1 bg-black dark:bg-[#4a4238]" />
            <span className="font-black text-muted dark:text-[#9b8f80] text-xs uppercase">
              or
            </span>
            <div className="flex-1 h-1 bg-black dark:bg-[#4a4238]" />
          </div>

          <form onSubmit={handleStandardLogin} className="space-y-2">
            <input
              className="w-full rounded-lg border-4 border-black dark:border-[#4a4238] bg-surface-lowest dark:bg-[#0f0e0c] px-4 py-2 text-text dark:text-[#f0ebe2] font-bold outline-none placeholder:text-muted/60 dark:placeholder:text-[#9b8f80]/70 focus:bg-surface-low dark:focus:bg-[#1f1c18] focus:ring-0 transition-colors shadow-sm text-sm"
              placeholder="Email or username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <input
              className="w-full rounded-lg border-4 border-black dark:border-[#4a4238] bg-surface-lowest dark:bg-[#0f0e0c] px-4 py-2 text-text dark:text-[#f0ebe2] font-bold outline-none placeholder:text-muted/60 dark:placeholder:text-[#9b8f80]/70 focus:bg-surface-low dark:focus:bg-[#1f1c18] focus:ring-0 transition-colors shadow-sm text-sm"
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />

            <button
              type="submit"
              className="w-full rounded-2xl border-4 border-black bg-primary px-5 py-2 font-black text-black text-base shadow-card hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-card-sm transition-all uppercase tracking-wide mt-1 cursor-pointer toggle-signin"
            >
              Sign In
            </button>
          </form>

          <div className="flex items-center gap-4 my-3">
            <div className="flex-1 h-1 bg-black dark:bg-[#4a4238]" />
            <span className="font-black text-muted dark:text-[#9b8f80] text-[10px] uppercase">
              New Contributors
            </span>
            <div className="flex-1 h-1 bg-black dark:bg-[#4a4238]" />
          </div>

          <a
            href="/signup"
            className="flex items-center justify-center w-full rounded-2xl border-4 border-black bg-[#C3C0FF] px-5 py-2 font-black text-black text-base shadow-card-sm hover:-translate-y-0.5 active:translate-y-0.5 transition-all uppercase tracking-wide cursor-pointer"
          >
            Create an account
          </a>
        </div>
      </div>
    </div>
  );
}

export default LandingPage;
