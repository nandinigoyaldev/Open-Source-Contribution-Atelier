import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useGoogleLogin } from "@react-oauth/google";
import { Moon, Sun, ShieldCheck, Sparkles } from "lucide-react";
import { fetchApi } from "../lib/api";
import { useAuth } from "../features/auth/AuthContext";
import { useTheme } from "../hooks/useTheme";
import { DraggableSticker } from "../components/ui/DraggableSticker";
import { DemoLoginButton } from "../features/auth/DemoLoginButton";
import {
  buildGoogleLoginPayload,
  checkBackendReachable,
  formatGoogleOAuthError,
  googleLoginOptions,
  googlePopupErrorMessage,
  hasGoogleCredential,
} from "../lib/googleOAuth";
import { PasswordInput } from "../components/PasswordInput";
import { toast } from "react-hot-toast";

function getErrorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

interface VibeOption {
  id: string;
  label: string;
  emoji: string;
  color: string;
  textColor: string;
}

const VIBE_OPTIONS: VibeOption[] = [
  {
    id: "bughunter",
    label: "Bug Hunter",
    emoji: "🐛",
    color: "bg-[#FF6B6B]",
    textColor: "text-white",
  },
  {
    id: "shipped",
    label: "Shipped it!",
    emoji: "🚀",
    color: "bg-[#6BCB77]",
    textColor: "text-black",
  },
  {
    id: "coffee",
    label: "Coffee Powered",
    emoji: "☕",
    color: "bg-[#FFD93D]",
    textColor: "text-black",
  },
  {
    id: "wizard",
    label: "Git Master",
    emoji: "👑",
    color: "bg-[#4D96FF]",
    textColor: "text-white",
  },
];

export function LandingPage() {
  const navigate = useNavigate();
  const auth = useAuth();
  const login = auth.login;

  const { theme, toggleTheme } = useTheme();
  const [authRole, setAuthRole] = useState<"student" | "admin">("student");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isGoogleLoading, setIsGoogleLoading] = useState(false);
  const googleInFlight = useRef(false);

  const [activeVibe, setActiveVibe] = useState<VibeOption>(VIBE_OPTIONS[0]);
  const [bursts, setBursts] = useState<
    { id: number; emoji: string; x: number; y: number }[]
  >([]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const authError = new URLSearchParams(window.location.search).get(
        "auth_error",
      );
      if (authError) {
        setError(authError);
        window.history.replaceState({}, "", window.location.pathname);
      }
    }
  }, []);

  const handleStandardLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const tokens = await fetchApi("/auth/login/", {
        method: "POST",
        requireAuth: false,
        body: JSON.stringify({ username: email.trim(), password }),
      });
      login(tokens);
      navigate("/dashboard");
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Login failed. Check your credentials."));
    }
  };

  const handleGoogleLogin = async () => {
    setError("");
    if (googleInFlight.current) return;
    googleInFlight.current = true;
    setIsGoogleLoading(true);

    let googleStarted = false;
    try {
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
      googleLoginHandler();
    } finally {
      if (!googleStarted) {
        googleInFlight.current = false;
        setIsGoogleLoading(false);
      }
    }
  };

  const googleLoginHandler = useGoogleLogin(
    googleLoginOptions({
      onSuccess: async (tokenResponse) => {
        try {
          const payload = buildGoogleLoginPayload(tokenResponse);
          if (!hasGoogleCredential(payload)) {
            throw new Error(
              "Google returned no token to exchange. Check VITE_GOOGLE_OAUTH_FLOW.",
            );
          }
          const tokens = await fetchApi("/auth/google/", {
            method: "POST",
            requireAuth: false,
            cache: "no-store",
            suppressErrorToast: true,
            body: JSON.stringify(payload),
          });
          login(tokens);
          sessionStorage.setItem("justLoggedIn", "true");
          navigate("/dashboard");
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
      onNonOAuthError: (error) => {
        const message = googlePopupErrorMessage(error);
        setError(message);
        toast.error(message);
        googleInFlight.current = false;
        setIsGoogleLoading(false);
      },
    }),
  );

  const handleVibeClick = (vibe: VibeOption, e: React.MouseEvent) => {
    setActiveVibe(vibe);
    const rect = e.currentTarget.getBoundingClientRect();
    const newBursts = Array.from({ length: 4 }).map((_, i) => ({
      id: Date.now() + i,
      emoji: vibe.emoji,
      x: rect.left + rect.width / 2 + (Math.random() * 60 - 30),
      y: rect.top - 15 - Math.random() * 30,
    }));
    setBursts((prev) => [...prev, ...newBursts]);
    setTimeout(() => {
      setBursts((prev) =>
        prev.filter((b) => !newBursts.some((nb) => nb.id === b.id)),
      );
    }, 800);
  };

  return (
    <div className="min-h-screen w-full bg-surface-lowest dark:bg-[#0a0a0f] text-text transition-colors duration-300 relative flex flex-col justify-between p-4 sm:p-8 lg:p-12 overflow-x-hidden">
      {/* EMOJI BURSTS */}
      {bursts.map((b) => (
        <div
          key={b.id}
          className="fixed text-2xl select-none pointer-events-none animate-bounce z-50 transition-all"
          style={{ left: b.x, top: b.y }}
        >
          {b.emoji}
        </div>
      ))}

      {/* FLOATING CORNER STICKERS - DESKTOP ONLY */}
      <div className="hidden xl:block select-none pointer-events-auto">
        <DraggableSticker
          initialX={40}
          initialY={40}
          className="bg-[#FF6B6B] text-white rotate-[-6deg]"
        >
          Bug Hunter 🐛
        </DraggableSticker>

        <DraggableSticker
          initialX={520}
          initialY={30}
          className="bg-[#6BCB77] text-black rotate-[6deg]"
        >
          100% Merged ✅
        </DraggableSticker>
      </div>

      {/* MAIN CONTAINER */}
      <div className="w-full max-w-6xl mx-auto my-auto grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-20 items-center z-10 py-8 lg:py-16">
        {/* LEFT COLUMN: Spacious, Clean Hero */}
        <div className="lg:col-span-7 space-y-6 text-center lg:text-left">
          {/* Top Tag & Theme Toggle */}
          <div className="flex flex-wrap items-center justify-center lg:justify-start gap-3">
            <span className="font-black text-xs bg-accent text-black px-4 py-1.5 rounded-full border-2 border-black rotate-[-1deg] inline-flex items-center gap-1.5 shadow-card-sm">
              <ShieldCheck size={14} /> AUTHORIZED ACCESS ONLY
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
              className="rounded-xl bg-surface-low p-2 text-muted hover:text-text border-2 border-black dark:border-[#4a4238] shadow-card-sm hover:-translate-y-0.5 active:translate-y-0 transition-all dark:bg-[#151411] dark:text-[#c4bbae] dark:hover:text-[#f0ebe2] toggle-theme cursor-pointer"
            >
              {theme === "light" ? <Moon size={18} /> : <Sun size={18} />}
            </button>
          </div>

          {/* Headline & Subtitle */}
          <div className="space-y-4">
            <h1 className="text-4xl sm:text-5xl lg:text-6xl xl:text-7xl font-black text-black dark:text-white tracking-tight leading-[1.05] uppercase">
              Contribution <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-amber-500 via-rose-500 to-indigo-500">
                Atelier
              </span>
            </h1>
            <p className="text-muted dark:text-[#9b8f80] text-base sm:text-lg font-bold max-w-lg mx-auto lg:mx-0 leading-relaxed">
              Make your first open source contribution with guided mentorship,
              interactive tools, and real-world projects.
            </p>
          </div>

          {/* PLAYFUL ELEMENT: Sleek Interactive Mood Pill Row */}
          <div className="pt-2 max-w-lg mx-auto lg:mx-0 space-y-2.5">
            <div className="flex items-center gap-1.5 text-xs font-black uppercase text-black dark:text-[#f0ebe2] justify-center lg:justify-start">
              <Sparkles size={14} className="text-amber-500 animate-spin" />{" "}
              Select Dev Mood:
            </div>

            <div className="flex flex-wrap items-center justify-center lg:justify-start gap-2">
              {VIBE_OPTIONS.map((vibe) => {
                const isActive = activeVibe.id === vibe.id;
                return (
                  <button
                    key={vibe.id}
                    type="button"
                    onClick={(e) => handleVibeClick(vibe, e)}
                    className={`py-1.5 px-3 rounded-xl border-2 font-black text-xs flex items-center gap-1.5 transition-all cursor-pointer ${
                      isActive
                        ? `${vibe.color} ${vibe.textColor} border-black shadow-card-sm -translate-y-0.5`
                        : "bg-white dark:bg-[#151411] border-black/20 dark:border-white/20 text-black dark:text-white hover:border-black hover:-translate-y-0.5"
                    }`}
                  >
                    <span>{vibe.emoji}</span>
                    <span>{vibe.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: Clean, Elevated Login Card */}
        <div className="lg:col-span-5 w-full max-w-md mx-auto bg-white dark:bg-[#151411] rounded-[2.5rem] border-4 border-black dark:border-[#4a4238] shadow-card p-6 sm:p-8 relative z-20">
          {/* Contributor / Maintainer Role Tabs */}
          <div className="flex p-1 bg-surface-low dark:bg-[#0f0e0c] rounded-2xl border-2 border-black dark:border-[#4a4238] mb-6">
            <button
              type="button"
              onClick={() => setAuthRole("student")}
              className={`flex-1 py-3 px-4 text-center font-black rounded-xl transition-all text-sm border-2 menu-tab cursor-pointer ${
                authRole === "student"
                  ? "bg-white dark:bg-[#1f1c18] border-black dark:border-[#4a4238] shadow-card-sm -translate-y-0.5 text-black dark:text-[#f0ebe2]"
                  : "border-transparent text-muted dark:text-[#9b8f80] hover:text-text dark:hover:text-[#f0ebe2]"
              }`}
            >
              Contributor
            </button>
            <button
              type="button"
              onClick={() => setAuthRole("admin")}
              className={`flex-1 py-3 px-4 text-center font-black rounded-xl transition-all text-sm border-2 menu-tab cursor-pointer ${
                authRole === "admin"
                  ? "bg-white dark:bg-[#1f1c18] border-black dark:border-[#4a4238] shadow-card-sm -translate-y-0.5 text-black dark:text-[#f0ebe2]"
                  : "border-transparent text-muted dark:text-[#9b8f80] hover:text-text dark:hover:text-[#f0ebe2]"
              }`}
            >
              Maintainer
            </button>
          </div>

          <h2 className="text-xl font-black mb-4 text-center text-text dark:text-[#f0ebe2]">
            {authRole === "student"
              ? "Start Your First Contribution"
              : "Maintainer Login"}
          </h2>

          {error && (
            <div className="text-black font-bold text-sm bg-primary p-3 rounded-xl border-4 border-black shadow-card-sm mb-4">
              {error}
            </div>
          )}

          <div className="space-y-3">
            <button
              type="button"
              onClick={handleGoogleLogin}
              disabled={isGoogleLoading}
              className="w-full bg-white border-4 border-black rounded-2xl py-3 px-4 flex items-center justify-center gap-3 font-black text-black hover:bg-surface-low transition-all shadow-card-sm active:translate-y-1 active:shadow-none text-sm cursor-pointer toggle-google"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24">
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
              {isGoogleLoading
                ? "Signing in with Google…"
                : "Continue with Google"}
            </button>

            <DemoLoginButton
              label="🚀 Demo Mode (explicit local demo)"
              className="w-full bg-green-200 border-4 border-black rounded-2xl py-3 px-4 flex items-center justify-center gap-3 font-black text-black hover:bg-green-300 transition-all shadow-card-sm active:translate-y-1 active:shadow-none text-sm cursor-pointer"
            />
          </div>

          <div className="flex items-center gap-4 my-5">
            <div className="flex-1 h-[2px] bg-black dark:bg-[#4a4238]" />
            <span className="font-black text-muted dark:text-[#9b8f80] text-xs uppercase tracking-wider">
              or
            </span>
            <div className="flex-1 h-[2px] bg-black dark:bg-[#4a4238]" />
          </div>

          <form onSubmit={handleStandardLogin} className="space-y-3">
            <input
              className="w-full rounded-xl border-4 border-black dark:border-[#4a4238] bg-surface-lowest dark:bg-[#0f0e0c] px-4 py-3 text-text dark:text-[#f0ebe2] font-black outline-none placeholder:text-muted/60 dark:placeholder:text-[#9b8f80]/70 focus:bg-surface-low dark:focus:bg-[#1f1c18] focus:ring-0 transition-colors shadow-sm text-sm"
              placeholder="Email or username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <PasswordInput
              id="landing-password"
              className="w-full rounded-xl border-4 border-black dark:border-[#4a4238] bg-surface-lowest dark:bg-[#0f0e0c] px-4 py-3 text-text dark:text-[#f0ebe2] font-black outline-none placeholder:text-muted/60 dark:placeholder:text-[#9b8f80]/70 focus:bg-surface-low dark:focus:bg-[#1f1c18] focus:ring-0 transition-colors shadow-sm text-sm"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />

            <button
              type="submit"
              className="w-full rounded-2xl border-4 border-black bg-primary px-5 py-3.5 font-black text-black text-base shadow-card hover:-translate-y-1 hover:shadow-card-lg active:translate-y-0 active:shadow-none transition-all uppercase tracking-wide mt-2 cursor-pointer toggle-signin"
            >
              Sign In
            </button>
          </form>

          <div className="flex items-center gap-4 my-5">
            <div className="flex-1 h-[2px] bg-black dark:bg-[#4a4238]" />
            <span className="font-black text-muted dark:text-[#9b8f80] text-[10px] uppercase tracking-wider">
              New Contributors
            </span>
            <div className="flex-1 h-[2px] bg-black dark:bg-[#4a4238]" />
          </div>

          <a
            href="/signup"
            className="flex items-center justify-center w-full rounded-2xl border-4 border-black bg-[#C3C0FF] px-5 py-3.5 font-black text-black text-base shadow-card-sm hover:-translate-y-1 hover:shadow-card active:translate-y-0 active:shadow-none transition-all uppercase tracking-wide cursor-pointer"
          >
            Create an account
          </a>
        </div>
      </div>
    </div>
  );
}

export default LandingPage;
