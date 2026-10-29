import React, { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useGoogleLogin } from "@react-oauth/google";
import { ArrowRight, GitBranch, Moon, Sparkles, Sun, X } from "lucide-react";
import { toast } from "react-hot-toast";
import { PasswordInput } from "../components/PasswordInput";
import { useAuth } from "../features/auth/AuthContext";
import { DemoLoginButton } from "../features/auth/DemoLoginButton";
import { useTheme } from "../hooks/useTheme";
import { fetchApi } from "../lib/api";
import {
  buildGoogleLoginPayload,
  checkBackendReachable,
  formatGoogleOAuthError,
  googleLoginOptions,
  googlePopupErrorMessage,
  hasGoogleCredential,
} from "../lib/googleOAuth";

const workspaceSteps = [
  {
    label: "Fork",
    command: "gh repo fork atelier/starter --clone",
    detail:
      "Take a safe copy. Every good contribution starts with a little curiosity.",
    position: { left: "18%", top: "27%" },
    tone: "indigo",
  },
  {
    label: "Build",
    command: 'git commit -m "improve onboarding"',
    detail:
      "Make one small, thoughtful change. Tiny commits have main-character energy.",
    position: { left: "53%", top: "45%" },
    tone: "violet",
  },
  {
    label: "Share",
    command: "git push origin first-contribution",
    detail: "Send it out and open the conversation with a pull request.",
    position: { left: "42%", top: "54%" },
    tone: "emerald",
  },
] as const;

const contributionSparks = [
  {
    label: "Fix a tiny bug",
    reply: "Tiny fix, deliciously satisfying.",
  },
  {
    label: "Polish some docs",
    reply: "Making the next person’s path softer.",
  },
  {
    label: "Ship a first PR",
    reply: "Okayyy, future open-source icon.",
  },
] as const;

function getErrorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

function GoogleMark() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 24 24" aria-hidden="true">
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
  );
}

export function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [totpCode, setTotpCode] = useState("");
  const [requires2FA, setRequires2FA] = useState(false);
  const [useBackupCode, setUseBackupCode] = useState(false);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isGoogleLoading, setIsGoogleLoading] = useState(false);
  const googleInFlight = useRef(false);
  const [activeWorkspaceStep, setActiveWorkspaceStep] = useState(0);
  const [activeSpark, setActiveSpark] = useState(0);
  const navigate = useNavigate();
  const { login } = useAuth();
  const { theme, toggleTheme } = useTheme();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("expired") === "true")
      toast.error("Your session expired. Please sign in again.");
    const redirect = params.get("redirect");
    if (redirect) sessionStorage.setItem("login_redirect", redirect);
  }, []);

  const finishLogin = (
    tokens: { access?: string; refresh?: string } | null,
  ) => {
    login(tokens);
    sessionStorage.setItem("justLoggedIn", "true");
    const redirect = sessionStorage.getItem("login_redirect") || "/dashboard";
    sessionStorage.removeItem("login_redirect");
    navigate(redirect);
  };

  const handleGoogleLogin = async () => {
    setError("");
    // Guard against rapid double-clicks / multiple popups.
    if (googleInFlight.current) return;
    googleInFlight.current = true;
    setIsGoogleLoading(true);

    let googleStarted = false;
    try {
      // Fail fast with a clear message before opening the Google popup if the
      // backend cannot be reached at all. Otherwise users go through the popup
      // flow only to hit a network error at the very end.
      const reachable = await checkBackendReachable();
      if (!reachable) {
        const message =
          "Could not reach the API to finish Google login. " +
          "Is the backend running, and is VITE_API_BASE_URL correct?";
        setError(message);
        toast.error(message);
        return;
      }
      googleStarted = true;
      googleLogin();
    } finally {
      // Only reset if the popup was never opened; the OAuth handlers below
      // reset loading once the popup flow actually completes.
      if (!googleStarted) {
        googleInFlight.current = false;
        setIsGoogleLoading(false);
      }
    }
  };

  const googleLogin = useGoogleLogin(
    googleLoginOptions({
      onSuccess: async (tokenResponse: any) => {
        try {
          const payload = buildGoogleLoginPayload(tokenResponse);
          if (!hasGoogleCredential(payload))
            throw new Error(
              "Google returned no token to exchange. Check VITE_GOOGLE_OAUTH_FLOW.",
            );
          const tokens = await fetchApi("/auth/google/", {
            method: "POST",
            requireAuth: false,
            // Auth endpoints must bypass any service-worker cache.
            cache: "no-store",
            // Errors are surfaced by this page; avoid duplicate toasts.
            suppressErrorToast: true,
            body: JSON.stringify(payload),
          });
          finishLogin(tokens);
        } catch (err: unknown) {
          const message = formatGoogleOAuthError(err, "backend");
          setError(message);
          toast.error(message);
        } finally {
          googleInFlight.current = false;
          setIsGoogleLoading(false);
        }
      },
      onError: (errorResponse) => {
        const message = formatGoogleOAuthError(errorResponse, "popup");
        setError(message);
        toast.error(message);
        googleInFlight.current = false;
        setIsGoogleLoading(false);
      },
      onNonOAuthError: (oauthError) => {
        const message = googlePopupErrorMessage(oauthError);
        setError(message);
        toast.error(message);
        googleInFlight.current = false;
        setIsGoogleLoading(false);
      },
    }),
  );

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setIsLoading(true);
    try {
      const payload: Record<string, string | boolean> = {
        username: username.trim(),
        password,
        remember: rememberMe,
      };
      if (requires2FA && totpCode) payload.totp_code = totpCode.trim();
      const tokens = await fetchApi("/auth/login/", {
        method: "POST",
        requireAuth: false,
        body: JSON.stringify(payload),
      });
      finishLogin(tokens);
    } catch (err: any) {
      const code = err?.code as string | undefined;
      if (
        code === "2fa_required" ||
        code === "requires_2fa" ||
        err?.requires_2fa ||
        err?.message?.includes("Two-factor")
      ) {
        setRequires2FA(true);
        toast.error("Enter the code from your authenticator app.");
      } else {
        const message = getErrorMessage(err, "Failed to login");
        setError(message);
        toast.error(requires2FA ? "Invalid verification code." : message);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const activeStep = workspaceSteps[activeWorkspaceStep];

  return (
    <div className="min-h-[100dvh] bg-[#f2f1ec] text-slate-900 dark:bg-[#11131a] dark:text-slate-100">
      <header className="relative mx-auto flex h-[60px] w-full max-w-6xl items-center justify-between px-5 sm:px-8">
        <Link
          to="/"
          className="flex items-center gap-2.5 font-semibold tracking-tight"
        >
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-indigo-600 text-white shadow-sm">
            <GitBranch size={18} strokeWidth={2.5} aria-hidden="true" />
          </span>
          <span>Open Source Atelier</span>
        </Link>
        <button
          type="button"
          onClick={toggleTheme}
          className="grid h-9 w-9 place-items-center rounded-lg border border-slate-300/80 bg-white/70 text-slate-600 transition hover:border-slate-400 hover:text-slate-950 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-600 dark:hover:text-white"
          aria-label={
            theme === "dark" ? "Switch to light mode" : "Switch to dark mode"
          }
        >
          {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
        </button>
      </header>
      <main className="mx-auto min-h-[calc(100dvh-60px)] w-full max-w-6xl px-5 py-2 sm:px-8">
        <div className="relative min-h-full w-full overflow-hidden rounded-[28px] border border-slate-900/10 bg-[#171923] shadow-[0_28px_80px_rgba(15,23,42,0.18)] dark:border-white/10">
          <div className="absolute inset-0 opacity-[0.13] [background-image:linear-gradient(rgba(255,255,255,.38)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,.38)_1px,transparent_1px)] [background-size:32px_32px]" />
          <div className="relative flex items-center justify-between border-b border-white/10 px-5 py-3 font-mono text-[11px] text-slate-400 sm:px-6">
            <span className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              atelier / workspace
            </span>
            <span className="hidden sm:block">main · clean</span>
          </div>
          <aside
            aria-label="Contribution workflow preview"
            className="absolute bottom-0 left-0 top-[45px] hidden w-[42%] border-r border-white/10 lg:block"
          >
            <div className="pointer-events-none absolute inset-0">
              <div className="absolute left-[18%] top-[18%] h-[54%] w-px bg-gradient-to-b from-transparent via-indigo-400/70 to-transparent" />
              <div className="absolute left-[18%] top-[27%] h-px w-[35%] bg-indigo-400/70" />
              <div className="absolute left-[53%] top-[27%] h-[18%] w-px bg-indigo-400/70" />
              <div className="absolute left-[18%] top-[54%] h-px w-[24%] bg-emerald-400/70" />
            </div>
            <div className="absolute left-7 top-7">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-slate-500">
                contribution flow
              </p>
              <p className="mt-1 text-sm font-medium text-slate-200">
                Pick a move. See the flow.
              </p>
            </div>
            <div className="absolute right-7 top-10 rounded-full border border-indigo-300/20 bg-indigo-400/10 px-3 py-1 font-mono text-[10px] text-indigo-200">
              HEAD → main
            </div>
            {workspaceSteps.map((step, index) => {
              const isActive = activeWorkspaceStep === index;
              const nodeColor =
                step.tone === "emerald"
                  ? "bg-emerald-400 ring-emerald-300/30"
                  : step.tone === "violet"
                    ? "bg-violet-400 ring-violet-300/30"
                    : "bg-indigo-400 ring-indigo-300/30";

              return (
                <button
                  key={step.label}
                  type="button"
                  onClick={() => setActiveWorkspaceStep(index)}
                  aria-pressed={isActive}
                  style={step.position}
                  className="group absolute z-10 -translate-x-1/2 -translate-y-1/2 text-left"
                >
                  <span
                    className={`block h-3 w-3 rounded-full border-2 border-[#171923] ${nodeColor} ${isActive ? "ring-4" : "group-hover:ring-4"} transition`}
                  />
                  <span
                    className={`mt-2 block whitespace-nowrap font-mono text-xs transition ${isActive ? "text-white" : "text-slate-400 group-hover:text-slate-200"}`}
                  >
                    {step.label}
                  </span>
                </button>
              );
            })}
            <div className="absolute bottom-8 left-7 right-7 rounded-xl border border-white/10 bg-black/20 p-4 backdrop-blur-sm">
              <div className="flex items-center justify-between gap-3">
                <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-emerald-300">
                  live preview
                </p>
                <span className="text-[10px] text-slate-500">
                  {activeWorkspaceStep + 1} / {workspaceSteps.length}
                </span>
              </div>
              <code className="mt-2 block overflow-hidden text-ellipsis whitespace-nowrap font-mono text-xs text-slate-100">
                <span className="mr-2 text-emerald-400">$</span>
                {activeStep.command}
              </code>
              <p className="mt-2 text-xs leading-5 text-slate-400">
                {activeStep.detail}
              </p>
              <button
                type="button"
                onClick={() =>
                  setActiveWorkspaceStep(
                    (activeWorkspaceStep + 1) % workspaceSteps.length,
                  )
                }
                className="mt-3 text-xs font-medium text-indigo-300 transition hover:text-indigo-100"
              >
                Show next step →
              </button>
            </div>
          </aside>
          <section className="relative ml-auto min-h-[calc(100dvh-105px)] w-full max-w-[29rem] border-white/10 bg-white p-5 sm:p-6 lg:border-l dark:bg-[#20232f]">
            <span className="absolute left-0 top-9 hidden -translate-x-1/2 rounded-full border border-white/20 bg-[#171923] px-2 py-1 font-mono text-[9px] text-emerald-300 lg:block">
              HEAD
            </span>
            <div className="mb-7">
              <p className="font-mono text-xs text-indigo-600 dark:text-indigo-300">
                $ your next contribution starts here
              </p>
              <h1 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950 dark:text-white">
                Tiny commits. Big contributor energy.
              </h1>
              <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
                Bring the idea—we&apos;ll help you turn it into a contribution.
              </p>
            </div>
            {error && (
              <div
                role="alert"
                className="mb-5 flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800 dark:border-rose-500/25 dark:bg-rose-500/10 dark:text-rose-200"
              >
                <span className="min-w-0 flex-1">{error}</span>
                <button
                  type="button"
                  onClick={() => setError("")}
                  className="rounded p-0.5 hover:bg-rose-100 dark:hover:bg-rose-500/10"
                  aria-label="Dismiss error"
                >
                  <X size={15} />
                </button>
              </div>
            )}
            <form onSubmit={handleSubmit} className="space-y-5">
              {requires2FA ? (
                <>
                  <div>
                    <label
                      htmlFor="totp_code"
                      className="text-sm font-medium text-slate-700 dark:text-slate-200"
                    >
                      Verification code
                    </label>
                    <p className="mt-1 text-xs leading-5 text-slate-500 dark:text-slate-400">
                      Enter the six-digit code from your authenticator app.
                    </p>
                    <input
                      id="totp_code"
                      name="totp_code"
                      autoFocus
                      autoComplete={useBackupCode ? "off" : "one-time-code"}
                      inputMode={useBackupCode ? "text" : "numeric"}
                      maxLength={useBackupCode ? 10 : 6}
                      placeholder={useBackupCode ? "a1b2-c3d4" : "123456"}
                      value={totpCode}
                      onChange={(event) => setTotpCode(event.target.value)}
                      className="mt-3 w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-center font-mono tracking-[0.25em] text-slate-950 outline-none transition placeholder:tracking-normal focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 dark:border-slate-700 dark:bg-slate-950 dark:text-white"
                      required
                    />
                    <button
                      type="button"
                      onClick={() => {
                        setUseBackupCode(!useBackupCode);
                        setTotpCode("");
                      }}
                      className="mt-3 text-xs font-medium text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300"
                    >
                      {useBackupCode
                        ? "Use an authenticator code"
                        : "Use a backup code"}
                    </button>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setRequires2FA(false);
                      setTotpCode("");
                    }}
                    className="text-sm text-slate-500 underline-offset-4 hover:text-slate-800 hover:underline dark:hover:text-slate-200"
                  >
                    Back to sign in
                  </button>
                </>
              ) : (
                <>
                  <div>
                    <label
                      htmlFor="username"
                      className="text-sm font-medium text-slate-700 dark:text-slate-200"
                    >
                      Username or email
                    </label>
                    <input
                      id="username"
                      name="username"
                      autoComplete="username"
                      spellCheck={false}
                      placeholder="the_smartest@kid.com"
                      value={username}
                      onChange={(event) => setUsername(event.target.value)}
                      className="mt-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-950 outline-none transition placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 dark:border-slate-700 dark:bg-slate-950 dark:text-white dark:placeholder:text-slate-500"
                      required
                    />
                  </div>
                  <div>
                    <label
                      htmlFor="login-password"
                      className="text-sm font-medium text-slate-700 dark:text-slate-200"
                    >
                      Password
                    </label>
                    <PasswordInput
                      id="login-password"
                      name="password"
                      autoComplete="current-password"
                      placeholder="••••••••"
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                      className="mt-2 rounded-lg border-slate-300 bg-white py-2.5 text-sm text-slate-950 placeholder:text-slate-400 focus:border-indigo-500 focus:ring-indigo-500/20 dark:border-slate-700 dark:bg-slate-950 dark:text-white dark:placeholder:text-slate-500"
                      required
                    />
                  </div>
                  <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                    <input
                      type="checkbox"
                      checked={rememberMe}
                      onChange={(event) => setRememberMe(event.target.checked)}
                      className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 dark:border-slate-700 dark:bg-slate-950"
                    />
                    Remember me for 30 days
                  </label>
                </>
              )}
              <button
                type="submit"
                disabled={isLoading}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60 dark:focus:ring-offset-slate-900"
              >
                {isLoading
                  ? requires2FA
                    ? "Verifying…"
                    : "Signing in…"
                  : requires2FA
                    ? "Verify and continue"
                    : "Let Me In!"}
                {!isLoading && <ArrowRight size={16} aria-hidden="true" />}
              </button>
            </form>
            {!requires2FA && (
              <>
                <div className="my-5 flex items-center gap-3 text-xs text-slate-400 dark:text-slate-500">
                  <span className="h-px flex-1 bg-slate-200 dark:bg-slate-800" />
                  or continue with
                  <span className="h-px flex-1 bg-slate-200 dark:bg-slate-800" />
                </div>
                <button
                  type="button"
                  onClick={handleGoogleLogin}
                  disabled={isGoogleLoading}
                  className="flex w-full items-center justify-center gap-2 rounded-lg border border-slate-300 px-3 py-2.5 text-sm font-medium text-slate-700 transition hover:-translate-y-0.5 hover:border-indigo-300 hover:bg-indigo-50 hover:shadow-sm active:translate-y-0 dark:border-slate-700 dark:text-slate-200 dark:hover:border-indigo-500/50 dark:hover:bg-indigo-500/10"
                >
                  {isGoogleLoading ? (
                    <span className="flex items-center gap-2">
                      <GoogleMark />
                      Signing in with Google…
                    </span>
                  ) : (
                    <>
                      <GoogleMark />
                      Continue with Google
                    </>
                  )}
                </button>
                <div className="mt-4 hidden rounded-xl border border-indigo-100 bg-indigo-50/70 p-3 dark:border-indigo-400/15 dark:bg-indigo-500/[0.07] lg:block">
                  <div className="flex items-center gap-2 text-xs font-medium text-indigo-900 dark:text-indigo-200">
                    <Sparkles
                      size={14}
                      className="text-indigo-500"
                      aria-hidden="true"
                    />
                    Pick today&apos;s contribution spark
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {contributionSparks.map((spark, index) => {
                      const isActive = activeSpark === index;
                      return (
                        <button
                          key={spark.label}
                          type="button"
                          onClick={() => setActiveSpark(index)}
                          aria-pressed={isActive}
                          className={`rounded-full px-2.5 py-1 text-[11px] font-medium transition ${isActive ? "bg-indigo-600 text-white shadow-sm" : "bg-white text-indigo-700 hover:-translate-y-0.5 hover:bg-indigo-100 dark:bg-slate-900 dark:text-indigo-200 dark:hover:bg-indigo-500/20"}`}
                        >
                          {spark.label}
                        </button>
                      );
                    })}
                  </div>
                  <p
                    aria-live="polite"
                    className="mt-2 text-xs text-indigo-700/80 dark:text-indigo-200/70"
                  >
                    {contributionSparks[activeSpark].reply}
                  </p>
                </div>
                <DemoLoginButton
                  label="Explore a demo workspace"
                  className="mt-3 w-full rounded-lg border border-dashed border-slate-300 px-4 py-2.5 text-sm font-medium text-slate-600 transition hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700 dark:border-slate-700 dark:text-slate-300 dark:hover:border-indigo-500/60 dark:hover:bg-indigo-500/10 dark:hover:text-indigo-300"
                />
                <div className="mt-6 flex items-center justify-between text-sm">
                  <Link
                    to="/reset-password"
                    className="text-slate-500 underline-offset-4 hover:text-slate-900 hover:underline dark:text-slate-400 dark:hover:text-white"
                  >
                    Forgot password?
                  </Link>
                  <span className="text-slate-500 dark:text-slate-400">
                    New here?{" "}
                    <Link
                      to="/signup"
                      className="font-medium text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300"
                    >
                      Create an account
                    </Link>
                  </span>
                </div>
              </>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}

export default LoginPage;
