import React, { useState } from "react";
import { Github } from "lucide-react";
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
      // Optional: Redirect to dashboard
      window.location.href = "/dashboard";
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Failed to login"));
    }
  };

  return (
    <AuthPageShell
      title="Oh, you again?"
      subtitle="Welcome back to your favorite distraction-free zone. Drop your details below."
      mode="login"
    >
      <form className="space-y-6 pt-2" onSubmit={handleSubmit}>
        {error && (
          <div role="alert" className="text-black font-bold text-sm bg-primary p-4 rounded-lg border-4 border-black shadow-card-sm">
            {error}
          </div>
        )}

        <button
          type="button"
          onClick={handleGithubSignIn}
          className="group relative w-full overflow-hidden rounded-lg border-4 border-black bg-black px-5 py-4 font-black text-white text-lg shadow-card transition-all duration-300 hover:-translate-y-1 hover:bg-text hover:shadow-card-lg cursor-pointer uppercase flex items-center justify-center gap-3 before:absolute before:inset-0 before:-translate-x-full before:bg-gradient-to-r before:from-transparent before:via-white/25 before:to-transparent before:transition-transform before:duration-500 hover:before:translate-x-full"
          aria-label="Sign in with GitHub"
        >
          <Github
            className="relative h-6 w-6 transition-transform duration-300 group-hover:rotate-[-8deg] group-hover:scale-110"
            strokeWidth={2.75}
            aria-hidden="true"
          />
          <span className="relative">Sign in with GitHub</span>
        </button>

        <div className="flex items-center gap-4">
          <div className="h-1 flex-1 bg-black"></div>
          <span className="text-sm font-black uppercase text-muted">OR</span>
          <div className="h-1 flex-1 bg-black"></div>
        </div>

        <div className="space-y-2">
          <label className="font-bold text-black ml-2 uppercase tracking-wide text-sm">
            Username / Email
          </label>
          <input
            className="w-full rounded-2xl border-4 border-black bg-white px-5 py-4 text-black font-bold outline-none placeholder:text-muted/60 focus:bg-tertiary shadow-card-sm transition-all focus:-translate-y-1 focus:shadow-card"
            placeholder="the_smartest@kid.com"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </div>

        <div className="space-y-2">
          <label className="font-bold text-black ml-2 uppercase tracking-wide text-sm">
            Password
          </label>
          <input
            className="w-full rounded-2xl border-4 border-black bg-white px-5 py-4 text-black font-bold outline-none placeholder:text-muted/60 focus:bg-accent shadow-card-sm transition-all focus:-translate-y-1 focus:shadow-card"
            type="password"
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>

        <button className="w-full rounded-2xl border-4 border-black bg-primary px-5 py-5 font-black text-black text-xl shadow-card hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-card-sm transition-all cursor-pointer mt-4 uppercase">
          Let Me In!
        </button>

        <p className="text-center text-sm font-bold text-black mt-6">
          New here?{" "}
          <a
            href="/signup"
            className="text-primary underline decoration-2 hover:text-black"
          >
            Join the chaos
          </a>
        </p>
      </form>
    </AuthPageShell>
  );
}
