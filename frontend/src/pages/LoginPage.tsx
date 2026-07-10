import React, { useState } from "react";
import { GitBranch, LogIn, ArrowRight } from "lucide-react";
import { AuthPageShell } from "../features/auth/AuthPageShell";
import { fetchApi } from "../lib/api";
import { useAuth } from "../features/auth/AuthContext";

const githubAuthUrl =
  import.meta.env?.VITE_GITHUB_OAUTH_URL ||
  `${import.meta.env?.VITE_API_BASE_URL || "http://localhost:8000/api"}/auth/github/`;

function getErrorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const { login } = useAuth();

  const handleGithubSignIn = () => {
    window.location.href = githubAuthUrl;
  };

  const handleGoogleSignIn = () => {
    window.location.href = "/api/auth/google/";
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const tokens = await fetchApi("/auth/login/", {
        method: "POST",
        requireAuth: false,
        body: JSON.stringify({ username, password }),
      });
      login(tokens);
      sessionStorage.setItem("justLoggedIn", "true");
      window.location.href = "/dashboard";
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Failed to login"));
    }
  };

  return (
    <AuthPageShell
      mode="login"
      title="Welcome Back"
      subtitle="Sign in to access your dashboard, complete challenges, and track your progress."
    >
      <form className="space-y-5" onSubmit={handleSubmit}>
        {error && (
          <div
            role="alert"
            className="text-red-700 bg-red-50 dark:bg-red-950/20 dark:text-red-400 p-4 rounded-xl border border-red-200 dark:border-red-900/30 text-sm font-semibold"
          >
            {error}
          </div>
        )}

        {/* Google Login Button */}
        <button
          type="button"
          onClick={handleGoogleSignIn}
          className="flex items-center justify-center gap-3 w-full px-4 py-3 border border-slate-200 dark:border-slate-800 rounded-xl font-semibold shadow-sm hover:bg-slate-50 dark:hover:bg-slate-800/50 hover:scale-[1.01] active:scale-[0.99] transition-all text-sm text-slate-700 dark:text-slate-200 bg-white dark:bg-[#12121a]"
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24">
            <path
              fill="#4285F4"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
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

        {/* GitHub Login Button */}
        <button
          type="button"
          onClick={handleGithubSignIn}
          className="flex items-center justify-center gap-3 w-full px-4 py-3 border border-transparent bg-slate-900 text-white rounded-xl font-semibold shadow-sm hover:bg-slate-800 hover:scale-[1.01] active:scale-[0.99] transition-all text-sm dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
          aria-label="Sign in with GitHub"
        >
          <GitBranch
            className="transition-transform duration-300 rotate-[-8deg]"
            size={18}
            strokeWidth={2.25}
            aria-hidden="true"
          />
          <span>Sign in with GitHub</span>
        </button>

        <div className="flex items-center gap-3 py-2">
          <div className="h-[1px] flex-1 bg-slate-200 dark:bg-slate-800"></div>
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
            OR
          </span>
          <div className="h-[1px] flex-1 bg-slate-200 dark:bg-slate-800"></div>
        </div>

        <div className="space-y-1.5">
          <label className="font-bold text-slate-500 dark:text-slate-400 ml-1 text-xs uppercase tracking-wider">
            Username or Email
          </label>
          <input
            className="w-full rounded-xl border border-slate-200 bg-white dark:bg-[#12121a] dark:border-slate-800 px-4 py-3 text-slate-900 dark:text-white font-medium outline-none placeholder:text-slate-400 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all text-sm"
            placeholder="username or email"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </div>

        <div className="space-y-1.5">
          <label className="font-bold text-slate-500 dark:text-slate-400 ml-1 text-xs uppercase tracking-wider">
            Password
          </label>
          <input
            className="w-full rounded-xl border border-slate-200 bg-white dark:bg-[#12121a] dark:border-slate-800 px-4 py-3 text-slate-900 dark:text-white font-medium outline-none placeholder:text-slate-400 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all text-sm"
            type="password"
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>

        <button className="w-full rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-4 py-3.5 font-bold text-sm hover:scale-[1.01] active:scale-[0.99] transition-all cursor-pointer mt-4 uppercase flex items-center justify-center gap-2 shadow-md hover:shadow-lg">
          <LogIn size={16} />
          <span>Sign In</span>
          <ArrowRight size={16} />
        </button>

        <p className="text-center text-xs font-bold mt-4 text-slate-500 dark:text-slate-400">
          New here?{" "}
          <a
            href="/signup"
            className="text-blue-600 hover:text-blue-500 dark:text-blue-400 dark:hover:text-blue-300 underline font-black ml-1"
          >
            Create an account
          </a>
        </p>
      </form>
    </AuthPageShell>
  );
}

export default LoginPage;
