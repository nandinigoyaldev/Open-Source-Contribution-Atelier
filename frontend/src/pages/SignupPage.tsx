import React, { useState } from "react";
import { AuthPageShell } from "../features/auth/AuthPageShell";
import { fetchApi } from "../lib/api";
import { useAuth } from "../features/auth/AuthContext";

export function SignupPage() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const { login } = useAuth();

  const isFormValid =
    username.trim() !== "" && email.trim() !== "" && password.trim() !== "";

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
    } catch (err: any) {
      setError(err.message || "Failed to create account");
    }
  };

  return (
    <AuthPageShell
      title="Join the Club."
      subtitle="Say goodbye to your free time. Create an account to start suffering... I mean, studying."
      mode="signup"
    >
      <form className="space-y-6 pt-2" onSubmit={handleSubmit}>
        {error && (
          <div className="text-black font-bold text-sm bg-primary p-4 rounded-xl border-4 border-black shadow-card-sm">
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
          />
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
            href="/login"
            className="text-primary underline decoration-2 hover:text-black"
          >
            Log in here
          </a>
        </p>
      </form>
    </AuthPageShell>
  );
}
