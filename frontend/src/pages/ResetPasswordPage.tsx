import React, { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CheckCircle2, Clock, Loader2, XCircle } from "lucide-react";
import { AuthPageShell } from "../features/auth/AuthPageShell";
import { PasswordInput } from "../components/PasswordInput";
import PasswordStrengthMeter from "../components/PasswordStrengthMeter";
import { fetchApi } from "../lib/api";
import { ApiError } from "../lib/apiErrors";

const labelClass =
  "font-bold text-black dark:text-white ml-2 uppercase tracking-wide text-sm";
const inputClass =
  "w-full rounded-2xl border-4 border-black bg-white px-5 py-3 text-black font-bold outline-none placeholder:text-muted/60 focus:bg-accent shadow-card-sm transition-all focus:-translate-y-1 focus:shadow-card";
const passwordInputClass =
  "w-full rounded-2xl border-4 border-black bg-white pl-5 pr-12 py-3 text-black font-bold outline-none placeholder:text-muted/60 focus:bg-tertiary shadow-card-sm transition-all focus:-translate-y-1 focus:shadow-card";
const submitClass =
  "w-full rounded-2xl border-4 border-black bg-accent px-5 py-3 font-black text-black shadow-card-sm transition-all hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-none disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:translate-y-0 cursor-pointer uppercase";
const linkButton =
  "inline-block w-full rounded-2xl border-4 border-black bg-primary px-5 py-3 font-black text-black shadow-card-sm hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-none transition-all text-center uppercase";
const textLink =
  "inline-block text-sm font-black text-black dark:text-white underline underline-offset-4";
const fieldErrorClass = "mt-1 ml-2 text-sm font-bold text-red-700";

/** The API reports a bad token as `{ error: "invalid_token" | "expired_token" }`. */
function tokenProblem(err: unknown): "expired" | "invalid" | null {
  const body = err instanceof ApiError ? err.body : null;
  const code =
    body && typeof body === "object"
      ? (body as Record<string, unknown>).error
      : null;
  if (code === "expired_token") return "expired";
  if (code === "invalid_token") return "invalid";
  return null;
}

/** Step 1: ask for the email address the reset link should go to. */
function RequestResetForm() {
  const [email, setEmail] = useState("");
  const [sending, setSending] = useState(false);
  const [sentMessage, setSentMessage] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSending(true);
    try {
      const data = await fetchApi("/auth/password-reset/", {
        method: "POST",
        requireAuth: false,
        suppressErrorToast: true,
        body: JSON.stringify({ email: email.trim() }),
      });
      setSentMessage(
        data?.message ||
          "If an account with that email exists, a password reset link has been sent.",
      );
    } catch (err: unknown) {
      setError(
        err instanceof ApiError && err.fieldErrors?.email
          ? err.fieldErrors.email[0]
          : err instanceof Error
            ? err.message
            : "Could not send the reset link. Please try again.",
      );
    } finally {
      setSending(false);
    }
  };

  if (sentMessage) {
    return (
      <div className="text-center space-y-5 pt-2">
        <div role="status" aria-live="polite" className="space-y-3">
          <div className="flex justify-center">
            <CheckCircle2 className="text-emerald-500" size={40} />
          </div>
          <h2 className="text-2xl font-black text-black dark:text-white">
            Check your inbox
          </h2>
          <p className="font-bold text-slate-700 dark:text-slate-300">
            {sentMessage}
          </p>
        </div>
        <button
          type="button"
          className={`${submitClass} bg-white`}
          onClick={() => setSentMessage("")}
        >
          Use a different email
        </button>
        <Link to="/login" className={textLink}>
          Back to login
        </Link>
      </div>
    );
  }

  return (
    <form className="space-y-5 pt-2" onSubmit={handleSubmit}>
      <p className="font-bold text-slate-700 dark:text-slate-300">
        Enter the email you signed up with and we will send you a link to choose
        a new password.
      </p>

      <div className="space-y-2">
        <label htmlFor="reset-password-email" className={labelClass}>
          Email Address
        </label>
        <input
          id="reset-password-email"
          className={inputClass}
          type="email"
          autoComplete="email"
          placeholder="nerd@homework.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          disabled={sending}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? "reset-password-email-error" : undefined}
        />
      </div>

      <p
        id="reset-password-email-error"
        role="alert"
        className="min-h-5 text-sm font-bold text-red-600 dark:text-red-400"
      >
        {error}
      </p>

      <button type="submit" disabled={sending} className={submitClass}>
        {sending ? "Sending..." : "Send reset link"}
      </button>

      <div className="text-center">
        <Link to="/login" className={textLink}>
          Back to login
        </Link>
      </div>
    </form>
  );
}

type TokenStatus = "checking" | "valid" | "expired" | "invalid" | "error";

/** Step 2: the emailed link brings us here with ?token=, check it then take a new password. */
function ChoosePasswordForm({ token }: { token: string }) {
  const [status, setStatus] = useState<TokenStatus>("checking");
  const [attempt, setAttempt] = useState(0);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [saving, setSaving] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [passwordErrors, setPasswordErrors] = useState<string[]>([]);
  // StrictMode runs effects twice in development; without this the same token
  // would be checked twice.
  const checked = useRef<string | null>(null);

  useEffect(() => {
    const requestId = `${token}:${attempt}`;
    if (checked.current === requestId) return;
    checked.current = requestId;

    fetchApi("/auth/password-reset/validate-token/", {
      method: "POST",
      requireAuth: false,
      suppressErrorToast: true,
      body: JSON.stringify({ token }),
    })
      .then(() => setStatus("valid"))
      .catch((err: unknown) => {
        const problem = tokenProblem(err);
        if (problem) setStatus(problem);
        // A token that is not even a UUID is refused by the serializer.
        else if (err instanceof ApiError && err.fieldErrors?.token)
          setStatus("invalid");
        else setStatus("error");
      });
  }, [token, attempt]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setPasswordErrors([]);
    if (password !== confirm) {
      setError("The two passwords do not match.");
      return;
    }
    setSaving(true);
    try {
      await fetchApi("/auth/password-reset/confirm/", {
        method: "POST",
        requireAuth: false,
        suppressErrorToast: true,
        body: JSON.stringify({ token, new_password: password }),
      });
      setDone(true);
    } catch (err: unknown) {
      const problem = tokenProblem(err);
      if (problem) {
        setStatus(problem);
      } else if (err instanceof ApiError && err.fieldErrors?.new_password) {
        setPasswordErrors(err.fieldErrors.new_password);
      } else {
        setError(
          err instanceof Error
            ? err.message
            : "Could not reset your password. Please try again.",
        );
      }
    } finally {
      setSaving(false);
    }
  };

  if (done) {
    return (
      <div className="text-center space-y-5 pt-2">
        <div role="status" aria-live="polite" className="space-y-3">
          <div className="flex justify-center">
            <CheckCircle2 className="text-emerald-500" size={40} />
          </div>
          <h2 className="text-2xl font-black text-black dark:text-white">
            Password updated
          </h2>
          <p className="font-bold text-slate-700 dark:text-slate-300">
            Your password has been reset. You can log in with it now.
          </p>
        </div>
        <Link to="/login" replace className={linkButton}>
          Continue to login
        </Link>
      </div>
    );
  }

  if (status !== "valid") {
    const content = {
      checking: {
        icon: <Loader2 className="animate-spin text-indigo-600" size={40} />,
        heading: "Checking your link...",
        body: "Hang tight, this only takes a second.",
      },
      expired: {
        icon: <Clock className="text-amber-500" size={40} />,
        heading: "This link has expired",
        body: "Reset links only last a little while. Request a fresh one and we will email it right away.",
      },
      invalid: {
        icon: <XCircle className="text-red-500" size={40} />,
        heading: "This link doesn't work",
        body: "It may have been copied incompletely, or it has already been used. Request a new link to try again.",
      },
      error: {
        icon: <XCircle className="text-red-500" size={40} />,
        heading: "We couldn't reach the server",
        body: "Your link may be fine. Check your connection and try again.",
      },
    }[status];

    return (
      <div className="text-center space-y-5 pt-2">
        <div role="status" aria-live="polite" className="space-y-3">
          <div className="flex justify-center">{content.icon}</div>
          <h2 className="text-2xl font-black text-black dark:text-white">
            {content.heading}
          </h2>
          <p className="font-bold text-slate-700 dark:text-slate-300">
            {content.body}
          </p>
        </div>

        {status === "error" && (
          <button
            type="button"
            onClick={() => {
              setStatus("checking");
              setAttempt((n) => n + 1);
            }}
            className={`${linkButton} cursor-pointer`}
          >
            Try again
          </button>
        )}

        {(status === "expired" || status === "invalid") && (
          <Link to="/reset-password" replace className={linkButton}>
            Request a new link
          </Link>
        )}

        {status !== "checking" && (
          <Link to="/login" className={textLink}>
            Back to login
          </Link>
        )}
      </div>
    );
  }

  const describedBy = passwordErrors.length
    ? "reset-password-new-errors"
    : "reset-password-hint";

  return (
    <form className="space-y-5 pt-2" onSubmit={handleSubmit}>
      <div className="space-y-2">
        <label htmlFor="reset-password-new" className={labelClass}>
          New Password
        </label>
        <PasswordInput
          id="reset-password-new"
          className={passwordInputClass}
          placeholder="••••••••"
          autoComplete="new-password"
          value={password}
          onChange={(e) => {
            setPassword(e.target.value);
            setPasswordErrors([]);
          }}
          required
          disabled={saving}
          aria-invalid={passwordErrors.length ? true : undefined}
          aria-describedby={describedBy}
        />
        <p
          id="reset-password-hint"
          className="ml-2 text-xs font-bold text-slate-600 dark:text-slate-400"
        >
          At least 8 characters, with an uppercase letter, a lowercase letter, a
          number and a special character.
        </p>
        {passwordErrors.length > 0 && (
          <ul id="reset-password-new-errors" className={fieldErrorClass}>
            {passwordErrors.map((message) => (
              <li key={message}>{message}</li>
            ))}
          </ul>
        )}
        <PasswordStrengthMeter password={password} />
      </div>

      <div className="space-y-2">
        <label htmlFor="reset-password-confirm" className={labelClass}>
          Confirm New Password
        </label>
        <PasswordInput
          id="reset-password-confirm"
          className={passwordInputClass}
          placeholder="••••••••"
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          required
          disabled={saving}
        />
      </div>

      <p
        role="alert"
        className="min-h-5 text-sm font-bold text-red-600 dark:text-red-400"
      >
        {error}
      </p>

      <button type="submit" disabled={saving} className={submitClass}>
        {saving ? "Saving..." : "Set new password"}
      </button>
    </form>
  );
}

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token")?.trim() || "";

  return (
    <AuthPageShell
      title="Reset your password."
      subtitle={
        token
          ? "Pick a new password and get back to shipping."
          : "Forgot it? It happens to the best of us."
      }
      mode="info"
    >
      {token ? <ChoosePasswordForm token={token} /> : <RequestResetForm />}
    </AuthPageShell>
  );
}

export default ResetPasswordPage;
