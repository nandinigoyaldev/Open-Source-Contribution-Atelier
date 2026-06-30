import React, { useState } from "react";
import { AuthPageShell } from "../features/auth/AuthPageShell";
import { fetchApi } from "../lib/api";
import { useAuth } from "../features/auth/AuthContext";
import { useGoogleLogin } from "@react-oauth/google";
import { GitBranch } from "lucide-react";
import PasswordStrengthMeter from "../components/PasswordStrengthMeter";

const githubAuthUrl =
  import.meta.env.VITE_GITHUB_OAUTH_URL ||
  `${import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api"}/auth/github/`;

function getErrorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export function SignupPage() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const { login } = useAuth();

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

  // ── END HELPER BLOCK ───────────────────────────────────────────────────────

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      // 1. Create the account
      await fetchApi("/auth/signup/", {
        method: "POST",
        requireAuth: false,
        body: JSON.stringify({ username, email, password }),
      });
      // 2. Fetch token to login
      const tokens = await fetchApi("/auth/login/", {
        method: "POST",
        requireAuth: false,
        body: JSON.stringify({ username, password }),
      });
      login(tokens);
      window.location.href = "/dashboard";
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Failed to create account"));
    }
  };

  const isFormValid =
    username.length > 0 && email.length > 0 && password.length > 0;

  return (
    <AuthPageShell
      title="Join the Club."
      subtitle="Say goodbye to your free time. Create an account to start suffering... I mean, studying."
      mode="signup"
    >
      <form className="space-y-6 pt-2" onSubmit={handleSubmit}>
        {error && (
          <div
            role="alert"
            className="text-black font-bold text-sm bg-primary p-4 rounded-lg border-4 border-black shadow-card-sm"
          >
            {error}
          </div>
        )}

        {/* ── OAUTH BUTTONS ── */}
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
          Sign up with Google
        </button>

        <button
          type="button"
          onClick={handleGithubSignIn}
          className="group relative w-full overflow-hidden bg-black text-white border-4 border-black rounded-lg p-4 flex items-center justify-center gap-3 font-black shadow-card-sm transition-all duration-300 hover:-translate-y-1 hover:bg-text hover:shadow-card-lg active:translate-y-1 active:shadow-none uppercase before:absolute before:inset-0 before:-translate-x-full before:bg-gradient-to-r before:from-transparent before:via-white/25 before:to-transparent before:transition-transform before:duration-500 hover:before:translate-x-full"
          aria-label="Sign up with GitHub"
        >
          <GitBranch
            className="mr-2 inline-block relative transition-transform duration-300 group-hover:rotate-[-8deg] group-hover:scale-110"
            size={20}
            strokeWidth={2.75}
            aria-hidden="true"
          />
          <span className="relative">Sign up with GitHub</span>
        </button>

        <div className="flex items-center gap-4 my-6">
          <div className="flex-1 h-1 bg-black"></div>
          <span className="font-black text-muted text-sm uppercase">OR</span>
          <div className="flex-1 h-1 bg-black"></div>
        </div>

        {/* ── USERNAME ── */}
        <div className="space-y-2">
          <label className="font-bold text-black ml-2 uppercase tracking-wide text-sm">
            Username
          </label>
          <input
            className="w-full rounded-2xl border-4 border-black bg-white px-5 py-4 text-black font-bold outline-none placeholder:text-muted/60 focus:bg-[#ffb5e8] shadow-card-sm transition-all focus:-translate-y-1 focus:shadow-card"
            placeholder="study_master_99"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </div>

        {/* ── EMAIL ── */}
        <div className="space-y-2">
          <label className="font-bold text-black ml-2 uppercase tracking-wide text-sm">
            Email Address
          </label>
          <input
            className="w-full rounded-2xl border-4 border-black bg-white px-5 py-4 text-black font-bold outline-none placeholder:text-muted/60 focus:bg-accent shadow-card-sm transition-all focus:-translate-y-1 focus:shadow-card"
            type="email"
            placeholder="nerd@homework.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>

        {/* ── PASSWORD ── */}
        <div className="space-y-2">
          <label className="font-bold text-black ml-2 uppercase tracking-wide text-sm">
            Password
          </label>
          <input
            className="w-full rounded-2xl border-4 border-black bg-white px-5 py-4 text-black font-bold outline-none placeholder:text-muted/60 focus:bg-tertiary shadow-card-sm transition-all focus:-translate-y-1 focus:shadow-card"
            type="password"
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />

          <PasswordStrengthMeter password={password} />
        </div>

        <button
          type="submit"
          disabled={!isFormValid}
          className={`w-full rounded-2xl border-4 border-black px-5 py-5 font-black text-black text-xl shadow-card transition-colors mt-4 uppercase
    ${
      isFormValid
        ? "bg-accent hover:bg-tertiary cursor-pointer"
        : "bg-gray-300 text-gray-500 cursor-not-allowed opacity-70"
    }`}
        >
          Sign Me Up!
        </button>

        <p className="text-center text-sm font-bold text-black mt-6">
          Already stuck with us?{" "}
          <a
            href="/"
            className="text-primary underline decoration-2 hover:text-black"
          >
            Log in here
          </a>
        </p>
      </form>
    </AuthPageShell>
  );
}
