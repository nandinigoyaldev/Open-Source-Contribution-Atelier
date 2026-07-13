import React, { useState, useEffect } from "react";
import { GitBranch, LogIn, ArrowRight } from "lucide-react";
import { useGoogleLogin } from "@react-oauth/google";
import { AuthPageShell } from "../features/auth/AuthPageShell";
import { fetchApi } from "../lib/api";
import { useAuth } from "../features/auth/AuthContext";
import { toast } from "react-hot-toast";

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
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();

  // ✅ Check for session expired parameter
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const expired = params.get('expired');
    const redirect = params.get('redirect');
    
    if (expired === 'true') {
      toast.error('Your session has expired. Please log in again.', {
        duration: 4000,
        position: 'bottom-center',
        icon: '🔒',
      });
    }
    
    // If there's a redirect parameter, store it for after login
    if (redirect) {
      sessionStorage.setItem('login_redirect', redirect);
    }
  }, []);

  const handleGithubSignIn = () => {
    window.location.href = githubAuthUrl;
  };

  const googleLogin = useGoogleLogin({
    onSuccess: async (tokenResponse) => {
      try {
        const tokens = await fetchApi("/auth/google/", {
          method: "POST",
          requireAuth: false,
          body: JSON.stringify({ access_token: tokenResponse.access_token }),
        });
        login(tokens);
        sessionStorage.setItem("justLoggedIn", "true");
        window.location.href = "/dashboard";
      } catch (err: unknown) {
        setError(getErrorMessage(err, "Google Auth Failed. Check Backend."));
      }
    },
    onError: () => {
      setError("Google Login Failed / Cancelled.");
    },
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);
    
    try {
      const tokens = await fetchApi("/auth/login/", {
        method: "POST",
        requireAuth: false,
        body: JSON.stringify({ username, password }),
      });
      
      login(tokens);
      
      // ✅ Show success toast
      toast.success('Welcome back! 🎉', {
        duration: 3000,
        position: 'bottom-center',
      });
      
      sessionStorage.setItem("justLoggedIn", "true");
      const redirect = sessionStorage.getItem('login_redirect') || '/dashboard';
      sessionStorage.removeItem('login_redirect');
      window.location.href = redirect;

    } catch (err: unknown) {
      setError(getErrorMessage(err, "Failed to login"));
      toast.error('Login failed. Please try again.');
    } finally {
      setIsLoading(false);
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
          onClick={() => googleLogin()}
          className="flex items-center justify-center gap-3 w-full px-4 py-3 border-2 border-black rounded-xl font-bold hover:-translate-y-0.5 hover:shadow-card-sm active:translate-y-0 active:shadow-none transition-all text-xs uppercase tracking-wider text-slate-700 dark:text-slate-200 bg-white dark:bg-[#12121a] cursor-pointer"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24">
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
          className="flex items-center justify-center gap-3 w-full px-4 py-3 border-2 border-black bg-slate-900 text-white rounded-xl font-bold hover:-translate-y-0.5 hover:shadow-card-sm active:translate-y-0 active:shadow-none transition-all text-xs uppercase tracking-wider dark:bg-[#C3C0FF] dark:text-black cursor-pointer"
          aria-label="Sign in with GitHub"
        >
          <GitBranch
            className="transition-transform duration-300 rotate-[-8deg]"
            size={14}
            strokeWidth={2.5}
            aria-hidden="true"
          />
          <span>Sign in with GitHub</span>
        </button>

        <div className="flex items-center gap-3 py-1">
          <div className="h-[2px] flex-1 bg-black/10 dark:bg-white/10"></div>
          <span className="text-[10px] font-black uppercase tracking-wider text-slate-400">
            OR
          </span>
          <div className="h-[2px] flex-1 bg-black/10 dark:bg-white/10"></div>
        </div>

        <div className="space-y-1.5">
          <label className="font-black text-slate-500 dark:text-slate-400 ml-1 text-[10px] uppercase tracking-wider">
            Username or Email
          </label>
          <input
            className="w-full rounded-xl border-2 border-black bg-white dark:bg-[#12121a] px-4 py-2.5 text-slate-900 dark:text-white font-bold outline-none placeholder:text-slate-400 focus:shadow-[2px_2px_0px_0px_#000000] transition-all text-sm"
            placeholder="username or email"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </div>

        <div className="space-y-1.5">
          <label className="font-black text-slate-500 dark:text-slate-400 ml-1 text-[10px] uppercase tracking-wider">
            Password
          </label>
          <input
            className="w-full rounded-xl border-2 border-black bg-white dark:bg-[#12121a] px-4 py-2.5 text-slate-900 dark:text-white font-bold outline-none placeholder:text-slate-400 focus:shadow-[2px_2px_0px_0px_#000000] transition-all text-sm"
            type="password"
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="w-full rounded-xl border-2 border-black bg-[#C3C0FF] px-4 py-3.5 font-black text-black text-sm shadow-card-sm hover:-translate-y-0.5 active:translate-y-0 active:shadow-none transition-all cursor-pointer mt-4 uppercase disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isLoading ? 'Logging in...' : 'Let Me In!'}
        </button>

        <p className="text-center text-xs font-bold mt-5 text-slate-500 dark:text-slate-400">
          New here?{" "}
          <a
            href="/signup"
            className="text-primary hover:opacity-80 underline font-black ml-1"
          >
            Create an account
          </a>
        </p>
      </form>
    </AuthPageShell>
  );
}

export default LoginPage;

