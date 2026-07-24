import { useEffect, useState, useRef } from "react";

interface Violation {
  id: string;
  description: string;
  impact: string;
  nodes: Array<{ target: string[] }>;
}

// Only renders in development mode to show accessibility warnings on the current page
export default function A11yDevOverlay() {
  const [violations, setViolations] = useState<Violation[]>([]);
  const [open, setOpen] = useState(false);
  const runRef = useRef(false);

  useEffect(() => {
    // Only run in development
    if (import.meta.env.PROD || runRef.current) return;
    runRef.current = true;

    // Dynamically import axe-core to avoid production bundle impact
    import("axe-core")
      .then((axe) => {
        axe.default
          .run(document, { runOnly: ["wcag2a", "wcag2aa"] })
          .then((results) => {
            if (results.violations.length > 0) {
              setViolations(results.violations as Violation[]);
              console.warn(
                `[A11y] ${results.violations.length} accessibility violation(s) found. Open the A11y overlay to review.`,
              );
            }
          });
      })
      .catch(() => {
        // axe-core not installed — silently fail
      });
  }, []);

  if (import.meta.env.PROD || violations.length === 0) return null;

  const criticalCount = violations.filter(
    (v) => v.impact === "critical" || v.impact === "serious",
  ).length;

  return (
    <div style={{ zIndex: 9999 }} className="fixed bottom-4 right-4">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white font-bold rounded-full shadow-xl border-2 border-red-800 hover:bg-red-700 transition-colors"
        aria-label={`Toggle accessibility overlay — ${violations.length} violation(s)`}
      >
        ♿
        <span className="bg-white text-red-600 rounded-full px-2 py-0.5 text-xs font-black">
          {violations.length}
        </span>
        A11y Issues
        {criticalCount > 0 && (
          <span className="bg-yellow-300 text-black rounded-full px-2 py-0.5 text-xs font-black">
            {criticalCount} critical/serious
          </span>
        )}
      </button>

      {open && (
        <div className="absolute bottom-14 right-0 w-96 max-h-[70vh] overflow-y-auto bg-white dark:bg-gray-900 border-2 border-red-400 rounded-2xl shadow-2xl p-4">
          <h2 className="text-lg font-black mb-3 text-red-600">
            ♿ Accessibility Violations ({violations.length})
          </h2>
          <ul className="space-y-3">
            {violations.map((v, i) => (
              <li
                key={i}
                className="border border-gray-200 dark:border-gray-700 rounded-lg p-3"
              >
                <div className="flex items-center gap-2 mb-1">
                  <span
                    className={`text-xs font-bold uppercase px-2 py-0.5 rounded-full ${
                      v.impact === "critical"
                        ? "bg-red-100 text-red-700"
                        : v.impact === "serious"
                          ? "bg-orange-100 text-orange-700"
                          : v.impact === "moderate"
                            ? "bg-yellow-100 text-yellow-700"
                            : "bg-blue-100 text-blue-700"
                    }`}
                  >
                    {v.impact}
                  </span>
                  <code className="text-xs text-gray-500">{v.id}</code>
                </div>
                <p className="text-sm text-gray-700 dark:text-gray-300">
                  {v.description}
                </p>
                {v.nodes.length > 0 && (
                  <p className="text-xs text-gray-500 mt-1 font-mono truncate">
                    {v.nodes[0].target.join(", ")}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
