import React, { useState } from "react";
import { fetchApi } from "../../lib/api";

export function SignupForm() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await fetchApi("/auth/signup/", {
        method: "POST",
        requireAuth: false,
        body: JSON.stringify({ username, email, password }),
      });
      window.location.href = "/verify-notice";
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to create account.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <form className="space-y-6 pt-2" onSubmit={handleSubmit}>
      {error && (
        <div
          role="alert"
          className="text-black font-bold text-sm bg-primary p-4 rounded-lg border-4 border-black shadow-card-sm"
        >
          {error}
        </div>
      )}

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
          disabled={loading}
        />
      </div>

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
          disabled={loading}
        />
      </div>

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
          disabled={loading}
        />
      </div>

      <button
        className="w-full rounded-2xl border-4 border-black bg-accent px-5 py-5 font-black text-black text-xl shadow-card hover:bg-tertiary transition-colors cursor-pointer mt-4 uppercase disabled:opacity-50"
        disabled={loading}
      >
        {loading ? "Creating Account..." : "Sign Me Up!"}
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
  );
}
