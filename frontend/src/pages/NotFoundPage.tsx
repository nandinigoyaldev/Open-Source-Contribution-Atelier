import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="min-h-[85vh] flex items-center justify-center p-4">
      <div className="w-full max-w-2xl mx-auto">
        <div className="text-center mb-6">
          <span className="font-black text-xs bg-accent text-black px-4 py-2 rounded-full border-2 border-black rotate-[-2deg] inline-block shadow-sm">
            ROUTE MISSING
          </span>
        </div>

        <div className="bg-white rounded-[2rem] border-4 border-black shadow-card-lg p-8 sm:p-12 relative overflow-hidden">
          <div className="absolute -top-10 -right-10 h-40 w-40 rounded-full bg-surface-high opacity-40 border-4 border-black"></div>
          <div className="absolute -bottom-12 -left-12 h-44 w-44 rounded-full bg-primary-container opacity-60 border-4 border-black"></div>

          <div className="relative">
            <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-muted">
              Error 404
            </p>
            <h1 className="text-5xl sm:text-6xl font-black tracking-tight mt-3">
              This corridor doesn&apos;t exist.
            </h1>
            <p className="mt-4 text-muted text-lg">
              The page you requested isn&apos;t in the atelier. Let&apos;s get
              you back to the home base.
            </p>

            <div className="mt-8 flex flex-wrap items-center gap-4">
              <Link
                to="/"
                className="inline-flex items-center justify-center rounded-2xl border-4 border-black bg-primary px-6 py-4 font-black text-white text-lg shadow-gel hover:bg-[#E62814] active:translate-y-2 transition-all uppercase tracking-wide"
              >
                Back to Home
              </Link>
              <div className="text-sm font-semibold text-muted">
                Tip: check your URL spelling.
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
