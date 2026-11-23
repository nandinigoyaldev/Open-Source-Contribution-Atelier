import React, { useEffect, useRef } from "react";

export interface ValidationErrorItem {
  fieldId: string;
  message: string;
  label?: string;
}

export interface ValidationSummaryProps {
  id?: string;
  title?: string;
  errors: ValidationErrorItem[];
  autoFocus?: boolean;
  className?: string;
  onLinkClick?: (fieldId: string) => void;
}

export const ValidationSummary = React.forwardRef<
  HTMLDivElement,
  ValidationSummaryProps
>(function ValidationSummary(
  {
    id = "validation-summary",
    title,
    errors,
    autoFocus = false,
    className = "",
    onLinkClick,
  },
  ref,
) {
  const localRef = useRef<HTMLDivElement>(null);
  const summaryRef = (ref as React.RefObject<HTMLDivElement>) || localRef;

  useEffect(() => {
    if (autoFocus && errors.length > 0) {
      summaryRef.current?.focus();
    }
  }, [autoFocus, errors]);

  if (!errors || errors.length === 0) {
    return null;
  }

  const titleId = `${id}-title`;
  const defaultTitle =
    errors.length === 1
      ? "There is 1 error with your submission"
      : `There are ${errors.length} errors with your submission`;
  const headingText = title || defaultTitle;

  const handleLinkClick =
    (fieldId: string) => (e: React.MouseEvent<HTMLAnchorElement>) => {
      e.preventDefault();
      onLinkClick?.(fieldId);
      const target = document.getElementById(fieldId);
      if (target) {
        target.focus();
        target.scrollIntoView?.({ behavior: "smooth", block: "center" });
      }
    };

  return (
    <div
      ref={summaryRef}
      id={id}
      tabIndex={-1}
      role="alert"
      aria-labelledby={titleId}
      className={`rounded-2xl border-4 border-red-600 bg-red-50 dark:bg-red-950/40 dark:border-red-500 p-5 text-black dark:text-white shadow-card-sm outline-none focus:ring-4 focus:ring-red-500/50 ${className}`}
    >
      <h2
        id={titleId}
        className="text-lg font-black uppercase tracking-wide text-red-700 dark:text-red-400 mb-3 flex items-center gap-2"
      >
        <span aria-hidden="true">⚠️</span>
        <span>{headingText}</span>
      </h2>
      <ul className="space-y-1.5 list-disc list-inside">
        {errors.map((err, index) => (
          <li key={`${err.fieldId}-${index}`} className="text-sm font-bold">
            <a
              href={`#${err.fieldId}`}
              onClick={handleLinkClick(err.fieldId)}
              className="text-red-700 dark:text-red-300 underline underline-offset-2 hover:text-black dark:hover:text-white focus:outline-none focus:ring-2 focus:ring-red-500 rounded px-1 -mx-1"
            >
              {err.label ? (
                <>
                  <span className="font-extrabold">{err.label}:</span>{" "}
                  {err.message}
                </>
              ) : (
                err.message
              )}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
});
