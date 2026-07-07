import { Skeleton } from "../Skeleton";
export default function SkeletonAdminDashboard() {
  return (
    <div className="max-w-7xl mx-auto px-4 pt-24 pb-12 space-y-10">
      {/* Header Banner */}
      <div className="rounded-[2rem] border-4 border-black bg-surface-low shadow-card p-8 sm:p-10 relative overflow-hidden h-[200px]">
        <Skeleton className="h-6 w-48 rounded-full mb-4" />
        <Skeleton className="h-10 w-96 rounded mb-4 max-w-full" />
        <Skeleton className="h-16 w-80 rounded-lg max-w-full" />
      </div>

      {/* 3 Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {Array.from({ length: 3 }).map((_, i) => (
          <div
            key={i}
            className="rounded-[2rem] border-4 border-black bg-surface-low shadow-card p-6 h-[140px]"
          >
            <div className="flex items-center gap-3">
              <Skeleton className="w-12 h-12 rounded-xl " />
              <div className="space-y-2">
                <Skeleton className="h-3 w-20 rounded " />
                <Skeleton className="h-8 w-16 rounded " />
              </div>
            </div>
            <div className="mt-4 pt-4 border-t border-dashed border-black/20">
              <Skeleton className="h-3 w-48 rounded " />
            </div>
          </div>
        ))}
      </div>

      {/* Charts & Analytics */}
      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-2xl border-4 border-black bg-surface-low shadow-card p-6 h-[400px]">
          <Skeleton className="h-6 w-64 rounded mb-6" />
          <Skeleton className="h-[300px] rounded-xl opacity-60" />
        </div>
        <div className="rounded-2xl border-4 border-black bg-surface-low shadow-card p-6 h-[400px]">
          <Skeleton className="h-6 w-48 rounded mb-6" />
          <Skeleton className="h-[200px] w-[200px] rounded-full mx-auto" />
          <div className="grid grid-cols-3 gap-2 mt-6">
            {Array.from({ length: 3 }).map((_, j) => (
              <Skeleton
                key={j}
                className="h-12 rounded-lg "
              />
            ))}
          </div>
        </div>
      </div>

      {/* PR Queue */}
      <div className="rounded-2xl border-4 border-black bg-surface-low shadow-card p-6">
        <Skeleton className="h-8 w-80 rounded mb-6 max-w-full" />
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="rounded-2xl border-4 border-black bg-white p-5 flex flex-col md:flex-row justify-between items-start md:items-center gap-4"
            >
              <div className="space-y-2 flex-1">
                <Skeleton className="h-4 w-32 rounded " />
                <Skeleton className="h-6 w-3/4 rounded " />
                <Skeleton className="h-4 w-48 rounded " />
              </div>
              <div className="flex gap-2 w-full md:w-auto">
                <Skeleton className="h-8 w-20 rounded-lg " />
                <Skeleton className="h-8 w-28 rounded-lg " />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
