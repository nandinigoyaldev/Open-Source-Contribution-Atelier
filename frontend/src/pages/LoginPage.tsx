import React, { useState } from "react";
import { GitBranch, LogIn, ArrowRight } from "lucide-react";
import { AuthPageShell } from "../features/auth/AuthPageShell";
import { fetchApi } from "../lib/api";
import { useAuth } from "../features/auth/AuthContext";

const githubAuthUrl =
  import.meta.env.VITE_GITHUB_OAUTH_URL ||
  `${import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api"}/auth/github/`;

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
    window.location.href = '/api/auth/google/';
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
      window.location.href = "/dashboard";
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Failed to login"));
    }
  };

  return (
    <AuthPageShell
      mode="login"
      title="Oh, you again?"
      subtitle="Welcome back to your favorite distraction-free zone. Drop your details below."
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

        {/* Google Login Button */}
        <button
          type="button"
          onClick={handleGoogleSignIn}
          className="group relative flex items-center justify-center gap-2 w-full px-4 py-3 border-4 border-black rounded-2xl font-bold shadow-card-sm hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-none transition-all text-sm bg-gradient-to-r from-[#4285F4]/10 to-white hover:from-[#4285F4]/20"
        >
          <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-[#4285F4] rounded-l-[14px]" />
          <svg className="w-5 h-5" viewBox="0 0 24 24">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/>
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
          </svg>
          Sign in with Google
        </button>

        {/* GitHub Login Button */}
        <button
          type="button"
          onClick={handleGithubSignIn}
          className="group relative w-full overflow-hidden rounded-lg border-4 border-black bg-black px-5 py-4 font-black text-white text-lg shadow-card transition-all duration-300 hover:-translate-y-1 hover:shadow-card-lg cursor-pointer uppercase flex items-center justify-center gap-3"
          aria-label="Sign in with GitHub"
        >
          <div className="absolute inset-0 bg-gradient-to-r from-[#333] via-[#555] to-[#333] opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
          <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-[#f0f0f0] rounded-l-[6px]" />
          <GitBranch
            className="inline-block relative transition-transform duration-300 group-hover:rotate-[-8deg] group-hover:scale-110 z-10"
            size={20}
            strokeWidth={2.75}
            aria-hidden="true"
          />
          <span className="relative z-10">Sign in with GitHub</span>
        </button>

        <div className="flex items-center gap-4">
          <div className="h-1 flex-1 bg-tertiary"></div>
          <span className="text-sm font-black uppercase text-tertiary">OR</span>
          <div className="h-1 flex-1 bg-accent"></div>
        </div>

        <div className="space-y-2">
          <label className="font-bold text-tertiary ml-2 uppercase tracking-wide text-sm flex items-center gap-2">
            <span className="w-2 h-2 bg-tertiary rounded-full inline-block" />
            Username / Email
          </label>
          <input
            className="w-full rounded-2xl border-4 border-black bg-white px-5 py-4 text-black font-bold outline-none placeholder:text-muted/60 focus:bg-tertiary/20 focus:border-tertiary shadow-card-sm transition-all focus:-translate-y-1 focus:shadow-card"
            placeholder="the_smartest@kid.com"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </div>

        <div className="space-y-2">
          <label className="font-bold text-accent ml-2 uppercase tracking-wide text-sm flex items-center gap-2">
            <span className="w-2 h-2 bg-accent rounded-full inline-block" />
            Password
          </label>
          <input
            className="w-full rounded-2xl border-4 border-black bg-white px-5 py-4 text-black font-bold outline-none placeholder:text-muted/60 focus:bg-accent/20 focus:border-accent shadow-card-sm transition-all focus:-translate-y-1 focus:shadow-card"
            type="password"
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>

        <button className="group w-full rounded-2xl border-4 border-black bg-gradient-to-r from-primary to-[#ff6b62] px-5 py-5 font-black text-black text-xl shadow-card hover:-translate-y-1 hover:shadow-card-lg active:translate-y-0.5 active:shadow-card-sm transition-all cursor-pointer mt-4 uppercase flex items-center justify-center gap-3">
          <LogIn size={22} className="group-hover:translate-x-1 transition-transform" />
          <span>Let Me In!</span>
          <ArrowRight size={22} className="group-hover:translate-x-1 transition-transform" />
        </button>

        <p className="text-center text-sm font-bold mt-6">
          <span className="text-black dark:text-[#94a3b8]">New here? </span>
          <a
            href="/signup"
            className="text-primary underline decoration-2 hover:text-black dark:hover:text-[#eef2f6] bg-primary/10 px-3 py-1 rounded-lg border-2 border-transparent hover:border-black dark:hover:border-[#3a3a45] transition-all font-black"
          >
            Join the chaos →
          </a>
        </p>
      </form>
    </AuthPageShell>
  );
}
