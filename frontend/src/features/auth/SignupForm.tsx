import React, { useState, useRef, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { fetchApi } from "../../lib/api";
import { ApiError } from "../../lib/apiErrors";
import {
  ValidationSummary,
  ValidationErrorItem,
} from "../../components/ui/ValidationSummary";

type FieldName = "username" | "email" | "password";

const FIELD_ERROR_CLASS = "mt-1 ml-2 text-sm font-bold text-red-700";

const SIGNUP_FIELD_LABELS: Record<FieldName, string> = {
  username: "Username",
  email: "Email Address",
  password: "Password",
};

const SIGNUP_FIELD_DOM_IDS: Record<FieldName, string> = {
  username: "signup-username",
  email: "signup-email",
  password: "signup-password",
};

export function SignupForm() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<
    Partial<Record<FieldName, string[]>>
  >({});
  const [loading, setLoading] = useState(false);
  const [submitAttempt, setSubmitAttempt] = useState(0);
  const summaryRef = useRef<HTMLDivElement>(null);
  const prevSubmitAttemptRef = useRef(0);

  const summaryErrors = useMemo(() => {
    const list: ValidationErrorItem[] = [];
    (Object.keys(fieldErrors) as FieldName[]).forEach((field) => {
      const messages = fieldErrors[field];
      if (messages && messages.length > 0) {
        messages.forEach((msg) => {
          list.push({
            fieldId: SIGNUP_FIELD_DOM_IDS[field],
            label: SIGNUP_FIELD_LABELS[field],
            message: msg,
          });
        });
      }
    });
    return list;
  }, [fieldErrors]);

  useEffect(() => {
    if (submitAttempt > prevSubmitAttemptRef.current) {
      prevSubmitAttemptRef.current = submitAttempt;
      if (summaryErrors.length > 0) {
        summaryRef.current?.focus();
      }
    }
  }, [submitAttempt, summaryErrors.length]);

  // Forget a field's server message as soon as the person edits that field.
  const clearFieldError = (field: FieldName) =>
    setFieldErrors((current) => {
      if (!current[field]) return current;
      const next = { ...current };
      delete next[field];
      return next;
    });

  const getPasswordStrength = (password: string) => {
    let score = 0;

    if (password.length >= 8) score++;
    if (/[a-z]/.test(password)) score++;
    if (/[A-Z]/.test(password)) score++;
    if (/\d/.test(password)) score++;
    if (/[^A-Za-z0-9]/.test(password)) score++;

    if (password.length === 0) {
      return { label: "", color: "", width: "0%" };
    }

    if (score <= 2) {
      return {
        label: "Weak",
        color: "bg-red-500",
        width: "33%",
      };
    }

    if (score <= 4) {
      return {
        label: "Medium",
        color: "bg-yellow-400",
        width: "66%",
      };
    }

    return {
      label: "Strong",
      color: "bg-green-500",
      width: "100%",
    };
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setFieldErrors({});
    setLoading(true);

    try {
      await fetchApi("/auth/signup/", {
        method: "POST",
        requireAuth: false,
        body: JSON.stringify({ username, email, password }),
      });
      navigate("/verify-notice");
    } catch (err: unknown) {
      const fields: Partial<Record<FieldName, string[]>> = {};
      if (err instanceof ApiError && err.fieldErrors) {
        for (const name of ["username", "email", "password"] as const) {
          if (err.fieldErrors[name]) fields[name] = err.fieldErrors[name];
        }
      }
      if (Object.keys(fields).length > 0) {
        // Show each message next to its field and in the accessible validation summary.
        setFieldErrors(fields);
        setSubmitAttempt((prev) => prev + 1);
      } else {
        setError(
          err instanceof Error ? err.message : "Failed to create account.",
        );
      }
    } finally {
      setLoading(false);
    }
  };

  const strength = getPasswordStrength(password);

  return (
    <form className="space-y-6 pt-2" onSubmit={handleSubmit}>
      {error && (
        <div
          role="alert"
          data-testid="general-error-banner"
          className="text-black font-bold text-sm bg-primary p-4 rounded-lg border-4 border-black shadow-card-sm"
        >
          {error}
        </div>
      )}

      <ValidationSummary
        ref={summaryRef}
        id="signup-validation-summary"
        errors={summaryErrors}
      />

      <div className="space-y-2">
        <label
          htmlFor="signup-username"
          className="font-bold text-black ml-2 uppercase tracking-wide text-sm"
        >
          Username
        </label>
        <input
          id="signup-username"
          className="w-full rounded-2xl border-4 border-black bg-white px-5 py-4 text-black font-bold outline-none placeholder:text-muted/60 focus:bg-[#ffb5e8] shadow-card-sm transition-all focus:-translate-y-1 focus:shadow-card"
          placeholder="study_master_99"
          value={username}
          onChange={(e) => {
            setUsername(e.target.value);
            clearFieldError("username");
          }}
          required
          disabled={loading}
          aria-invalid={fieldErrors.username ? true : undefined}
          aria-describedby={
            fieldErrors.username ? "signup-username-error" : undefined
          }
        />
        {fieldErrors.username && (
          <ul id="signup-username-error" className={FIELD_ERROR_CLASS}>
            {fieldErrors.username.map((message) => (
              <li key={message}>{message}</li>
            ))}
          </ul>
        )}
      </div>

      <div className="space-y-2">
        <label
          htmlFor="signup-email"
          className="font-bold text-black ml-2 uppercase tracking-wide text-sm"
        >
          Email Address
        </label>
        <input
          id="signup-email"
          className="w-full rounded-2xl border-4 border-black bg-white px-5 py-4 text-black font-bold outline-none placeholder:text-muted/60 focus:bg-accent shadow-card-sm transition-all focus:-translate-y-1 focus:shadow-card"
          type="email"
          placeholder="nerd@homework.com"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            clearFieldError("email");
          }}
          required
          disabled={loading}
          aria-invalid={fieldErrors.email ? true : undefined}
          aria-describedby={
            fieldErrors.email ? "signup-email-error" : undefined
          }
        />
        {fieldErrors.email && (
          <ul id="signup-email-error" className={FIELD_ERROR_CLASS}>
            {fieldErrors.email.map((message) => (
              <li key={message}>{message}</li>
            ))}
          </ul>
        )}
      </div>

      <div className="space-y-2">
        <label
          htmlFor="signup-password"
          className="font-bold text-black ml-2 uppercase tracking-wide text-sm"
        >
          Password
        </label>
        <input
          id="signup-password"
          className="w-full rounded-2xl border-4 border-black bg-white px-5 py-4 text-black font-bold outline-none placeholder:text-muted/60 focus:bg-tertiary shadow-card-sm transition-all focus:-translate-y-1 focus:shadow-card"
          type="password"
          placeholder="••••••••"
          value={password}
          onChange={(e) => {
            setPassword(e.target.value);
            clearFieldError("password");
          }}
          required
          disabled={loading}
          aria-invalid={fieldErrors.password ? true : undefined}
          aria-describedby={
            fieldErrors.password ? "signup-password-error" : undefined
          }
        />
        {fieldErrors.password && (
          <ul id="signup-password-error" className={FIELD_ERROR_CLASS}>
            {fieldErrors.password.map((message) => (
              <li key={message}>{message}</li>
            ))}
          </ul>
        )}
        {password && (
          <div className="mt-2">
            <div className="w-full h-2 bg-gray-200 rounded-full">
              <div
                className={`h-2 rounded-full transition-all ${strength.color}`}
                style={{ width: strength.width }}
              />
            </div>

            <p className="mt-1 text-sm font-bold text-black">
              Password Strength: {strength.label}
            </p>
          </div>
        )}
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
