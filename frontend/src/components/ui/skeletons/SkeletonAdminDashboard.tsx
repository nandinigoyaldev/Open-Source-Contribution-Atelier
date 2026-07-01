export default function SkeletonAdminDashboard() {
  return (
    <div className="max-w-7xl mx-auto px-4 pt-24 pb-12 space-y-10">
      {/* Header Banner */}
      <div className="rounded-[2rem] border-4 border-black bg-surface-low shadow-card p-8 sm:p-10 relative overflow-hidden h-[200px]">
        <div className="h-6 w-48 rounded-full bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer mb-4" />
        <div className="h-10 w-96 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer mb-4 max-w-full" />
        <div className="h-16 w-80 rounded-lg bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer max-w-full" />
      </div>

      {/* 3 Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {Array.from({ length: 3 }).map((_, i) => (
          <div
            key={i}
            className="rounded-[2rem] border-4 border-black bg-surface-low shadow-card p-6 h-[140px]"
          >
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer" />
              <div className="space-y-2">
                <div className="h-3 w-20 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer" />
                <div className="h-8 w-16 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer" />
              </div>
            </div>
            <div className="mt-4 pt-4 border-t border-dashed border-black/20">
              <div className="h-3 w-48 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer" />
            </div>
          </div>
        ))}
      </div>

      {/* Charts & Analytics */}
      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-2xl border-4 border-black bg-surface-low shadow-card p-6 h-[400px]">
          <div className="h-6 w-64 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer mb-6" />
          <div className="h-[300px] rounded-xl bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer opacity-60" />
        </div>
        <div className="rounded-2xl border-4 border-black bg-surface-low shadow-card p-6 h-[400px]">
          <div className="h-6 w-48 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer mb-6" />
          <div className="h-[200px] w-[200px] rounded-full bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer mx-auto" />
          <div className="grid grid-cols-3 gap-2 mt-6">
            {Array.from({ length: 3 }).map((_, j) => (
              <div
                key={j}
                className="h-12 rounded-lg bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer"
              />
            ))}
          </div>
        </div>
      </div>

      {/* PR Queue */}
      <div className="rounded-2xl border-4 border-black bg-surface-low shadow-card p-6">
        <div className="h-8 w-80 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer mb-6 max-w-full" />
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="rounded-2xl border-4 border-black bg-white p-5 flex flex-col md:flex-row justify-between items-start md:items-center gap-4"
            >
              <div className="space-y-2 flex-1">
                <div className="h-4 w-32 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer" />
                <div className="h-6 w-3/4 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer" />
                <div className="h-4 w-48 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer" />
              </div>
              <div className="flex gap-2 w-full md:w-auto">
                <div className="h-8 w-20 rounded-lg bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer" />
                <div className="h-8 w-28 rounded-lg bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
