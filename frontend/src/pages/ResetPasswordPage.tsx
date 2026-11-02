import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, KeyRound } from "lucide-react";
import { toast } from "react-hot-toast";
import { PasswordInput } from "../components/PasswordInput";
import { fetchApi } from "../lib/api";

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") || "";
  const [email, setEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setMessage("");

    if (token && newPassword !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setIsLoading(true);
    try {
      const response = token
        ? await fetchApi<{ message: string }>("/auth/password-reset/confirm/", {
            method: "POST",
            requireAuth: false,
            body: JSON.stringify({ token, new_password: newPassword }),
          })
        : await fetchApi<{ message: string }>("/auth/password-reset/", {
            method: "POST",
            requireAuth: false,
            body: JSON.stringify({ email: email.trim() }),
          });
      setMessage(response.message);
      if (token) toast.success("Password updated. You can sign in now.");
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "We could not process that request. Please try again.",
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#f2f1ec] px-5 py-8 text-slate-900 dark:bg-[#11131a] dark:text-slate-100 sm:px-8">
      <div className="mx-auto max-w-md">
        <Link
          to="/login"
          className="mb-6 inline-flex items-center gap-2 text-sm font-medium text-slate-600 transition hover:text-indigo-600 dark:text-slate-300 dark:hover:text-indigo-300"
        >
          <ArrowLeft size={16} aria-hidden="true" /> Back to sign in
        </Link>
        <section className="rounded-3xl border border-slate-900/10 bg-white p-6 shadow-[0_18px_50px_rgba(15,23,42,0.12)] dark:border-white/10 dark:bg-[#20232f] sm:p-8">
          <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-100 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300">
            {message && token ? (
              <CheckCircle2 aria-hidden="true" />
            ) : (
              <KeyRound aria-hidden="true" />
            )}
          </div>
          <h1 className="text-2xl font-bold">
            {token ? "Choose a new password" : "Reset your password"}
          </h1>
          <p className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-300">
            {token
              ? "Use a strong password you have not used here before."
              : "Enter your account email and we will send a reset link if it matches an account."}
          </p>
          {error && (
            <p role="alert" className="mt-5 rounded-xl bg-red-50 p-3 text-sm text-red-700 dark:bg-red-500/10 dark:text-red-300">
              {error}
            </p>
          )}
          {message && (
            <p role="status" className="mt-5 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300">
              {message}
            </p>
          )}
          {!message || !token ? (
            <form onSubmit={handleSubmit} className="mt-6 space-y-4">
              {!token ? (
                <label className="block text-sm font-medium">
                  Email address
                  <input
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    className="mt-2 w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-slate-950 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 dark:border-slate-700 dark:bg-slate-950 dark:text-white"
                    required
                  />
                </label>
              ) : (
                <>
                  <label className="block text-sm font-medium">
                    New password
                    <PasswordInput
                      value={newPassword}
                      onChange={(event) => setNewPassword(event.target.value)}
                      autoComplete="new-password"
                      className="mt-2 rounded-xl border-slate-300 bg-white text-slate-950 dark:border-slate-700 dark:bg-slate-950 dark:text-white"
                      required
                    />
                  </label>
                  <label className="block text-sm font-medium">
                    Confirm password
                    <PasswordInput
                      value={confirmPassword}
                      onChange={(event) => setConfirmPassword(event.target.value)}
                      autoComplete="new-password"
                      className="mt-2 rounded-xl border-slate-300 bg-white text-slate-950 dark:border-slate-700 dark:bg-slate-950 dark:text-white"
                      required
                    />
                  </label>
                </>
              )}
              <button
                type="submit"
                disabled={isLoading}
                className="w-full rounded-xl bg-indigo-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isLoading
                  ? "Working…"
                  : token
                    ? "Update password"
                    : "Send reset link"}
              </button>
            </form>
          ) : null}
        </section>
      </div>
    </main>
  );
}

export default ResetPasswordPage;
