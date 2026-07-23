/**
 * Notes export button component.
 *
 * @file NotesExportButton.tsx
 * @location frontend/src/components/Notes/NotesExportButton.tsx
 */

import React, { useState } from "react";
import { useAuth } from "../../features/auth/AuthContext";

interface NotesExportButtonProps {
  className?: string;
  variant?: "primary" | "secondary" | "outline";
  size?: "sm" | "md" | "lg";
  format?: "md" | "json";
}

export const NotesExportButton: React.FC<NotesExportButtonProps> = ({
  className = "",
  variant = "primary",
  size = "md",
  format = "md",
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { user } = useAuth();

  const handleExport = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const token = "";
      const response = await fetch(
        `${import.meta.env.VITE_API_URL}/api/progress/notes/export/?format=${format}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        },
      );

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || "Failed to export notes");
      }

      // Get filename from Content-Disposition header
      const contentDisposition = response.headers.get("Content-Disposition");
      let filename = `notes_export.${format === "md" ? "md" : "json"}`;
      if (contentDisposition) {
        const match = contentDisposition.match(/filename="(.+)"/);
        if (match) {
          filename = match[1];
        }
      }

      // Download file
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
      console.error("Export error:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const getVariantClasses = () => {
    const variants = {
      primary: "bg-blue-600 hover:bg-blue-700 text-white",
      secondary: "bg-gray-700 hover:bg-gray-600 text-white",
      outline:
        "border border-blue-600 text-blue-600 hover:bg-blue-600 hover:text-white",
    };
    return variants[variant] || variants.primary;
  };

  const getSizeClasses = () => {
    const sizes = {
      sm: "px-3 py-1.5 text-sm",
      md: "px-4 py-2 text-base",
      lg: "px-6 py-3 text-lg",
    };
    return sizes[size] || sizes.md;
  };

  return (
    <div className="inline-flex flex-col items-center gap-2">
      <button
        onClick={handleExport}
        disabled={isLoading}
        className={`
          ${getVariantClasses()}
          ${getSizeClasses()}
          rounded-lg font-medium transition-all duration-200
          focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
          disabled:opacity-50 disabled:cursor-not-allowed
          flex items-center gap-2
          ${className}
        `}
        aria-label="Export notes"
      >
        {isLoading ? (
          <>
            <svg
              className="animate-spin h-4 w-4"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            Exporting...
          </>
        ) : (
          <>
            <span aria-hidden="true">📥</span>
            Export Notes
          </>
        )}
      </button>

      {error && <span className="text-red-400 text-sm">{error}</span>}
    </div>
  );
};

export default NotesExportButton;
