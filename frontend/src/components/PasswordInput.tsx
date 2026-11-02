import React, { useState } from "react";

interface PasswordInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  id: string;
  label?: string;
}

export const PasswordInput: React.FC<PasswordInputProps> = ({
  id,
  label,
  className = "",
  ...props
}) => {
  const [showPassword, setShowPassword] = useState(false);

  // Extract margin classes so they apply to the container rather than causing vertical
  // misalignment between the input element and the absolutely positioned toggle button.
  const marginClasses =
    className.match(/\b([a-z0-9_-]+:)*m[tbyx]?-\S+\b/g)?.join(" ") || "";
  const inputClasses = className
    .replace(/\b([a-z0-9_-]+:)*m[tbyx]?-\S+\b/g, "")
    .replace(/\s+/g, " ")
    .trim();

  return (
    <div className={`flex flex-col gap-1 w-full ${marginClasses}`}>
      {label && (
        <label htmlFor={id} className="text-sm font-medium text-gray-700">
          {label}
        </label>
      )}

      <div className="relative w-full">
        <input
          {...props}
          id={id}
          type={showPassword ? "text" : "password"}
          className={`box-border w-full !pr-12 pl-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${inputClasses}`}
        />

        <button
          type="button"
          onClick={() => setShowPassword((prev) => !prev)}
          aria-label={showPassword ? "Hide password" : "Show password"}
          aria-pressed={showPassword}
          className="password-toggle absolute right-3.5 top-1/2 -translate-y-1/2 z-20 flex h-8 w-8 items-center justify-center rounded-md text-gray-500 hover:text-gray-700 dark:text-slate-400 dark:hover:text-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 cursor-pointer"
          style={{ margin: 0 }}
        >
          {showPassword ? (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
              <line x1="1" y1="1" x2="23" y2="23" />
            </svg>
          ) : (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
              <circle cx="12" cy="12" r="3" />
            </svg>
          )}
        </button>
      </div>
    </div>
  );
};
