import { Link, useLocation } from "react-router-dom";

export function Breadcrumbs() {
  const location = useLocation();
  // URL ko '/' se tod kar array banayenge, aur empty strings ko filter kar denge
  const pathnames = location.pathname.split("/").filter((x) => x);

  // Agar user root ("/") par hai, toh breadcrumbs hide kar do
  if (pathnames.length === 0) return null;

  return (
    <nav aria-label="Breadcrumb" className="mb-6 flex">
      <ol className="flex items-center space-x-2 text-sm text-gray-500 dark:text-gray-400">
        {/* Home Icon Link */}
        <li>
          <Link
            to="/dashboard"
            className="hover:text-gray-900 dark:hover:text-white transition-colors flex items-center"
          >
            <svg
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"
              />
            </svg>
            <span className="sr-only">Dashboard</span>
          </Link>
        </li>

        {/* Dynamic Path Links */}
        {pathnames.map((value, index) => {
          const isLast = index === pathnames.length - 1;
          const to = `/${pathnames.slice(0, index + 1).join("/")}`;
          
          // Dash '-' ko space mein convert karo aur Title Case banao (e.g., 'learning-path' -> 'Learning Path')
          const title = value
            .replace(/-/g, " ")
            .replace(/\b\w/g, (l) => l.toUpperCase());

          return (
            <li key={to} className="flex items-center space-x-2">
              <svg
                className="h-4 w-4 text-gray-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 5l7 7-7 7"
                />
              </svg>
              {isLast ? (
                <span
                  className="text-gray-900 dark:text-white font-medium"
                  aria-current="page"
                >
                  {title}
                </span>
              ) : (
                <Link
                  to={to}
                  className="hover:text-gray-900 dark:hover:text-white transition-colors"
                >
                  {title}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}