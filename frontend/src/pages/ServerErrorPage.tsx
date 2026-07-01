import { Link } from "react-router-dom";

export function ServerErrorPage() {
  return (
    <div className="min-h-[85vh] flex items-center justify-center p-4">
      <div className="w-full max-w-2xl mx-auto">
        <div className="text-center mb-6">
          <span className="font-black text-xs bg-red-400 text-black px-4 py-2 rounded-full border-2 border-black rotate-[2deg] inline-block shadow-sm">
            SYSTEM FAULT
          </span>
        </div>

        <div className="bg-white rounded-[2rem] border-4 border-black shadow-card-lg p-8 sm:p-12 relative overflow-hidden">
          <div className="absolute -top-10 -right-10 h-40 w-40 rounded-full bg-surface-high opacity-40 border-4 border-black"></div>
          <div className="absolute -bottom-12 -left-12 h-44 w-44 rounded-full bg-red-200 opacity-60 border-4 border-black"></div>

          <div className="relative">
            <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-muted">
              Error 500
            </p>
            <h1 className="text-5xl sm:text-6xl font-black tracking-tight mt-3">
              The server dropped the ball.
            </h1>
            <p className="mt-4 text-muted text-lg">
              We are experiencing internal technical difficulties. Our
              maintainers have been notified. Let us get you back to safety.
            </p>

            <div className="mt-8 flex flex-wrap items-center gap-4">
              <Link
                to="/"
                className="inline-flex items-center justify-center rounded-2xl border-4 border-black bg-primary px-6 py-4 font-black text-black text-lg shadow-gel hover:bg-[#E62814] active:translate-y-2 transition-all uppercase tracking-wide"
              >
                Return Home
              </Link>
              <div className="text-sm font-semibold text-muted">
                Tip: Try refreshing in a minute.
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
