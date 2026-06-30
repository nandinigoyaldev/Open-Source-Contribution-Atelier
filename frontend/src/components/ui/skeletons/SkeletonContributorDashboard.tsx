export default function SkeletonContributorDashboard() {
  return (
    <div className="max-w-7xl mx-auto px-4 pt-24 pb-12 space-y-10">
      {/* Header + Stat Grid */}
      <section className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
        <div className="rounded-[2.5rem] border-4 border-black bg-surface-low shadow-card p-8 sm:p-10 h-[260px]">
          <div className="h-6 w-36 rounded-full bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer mb-4" />
          <div className="h-10 w-3/4 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer mb-4 max-w-full" />
          <div className="h-16 w-5/6 rounded-lg bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer max-w-full" />
        </div>
        <div className="grid grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="rounded-[2rem] border-4 border-black bg-surface-low shadow-card p-6 h-[120px] flex flex-col items-center justify-center"
            >
              <div className="w-10 h-10 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer mb-2" />
              <div className="h-8 w-12 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer mb-1" />
              <div className="h-3 w-16 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer" />
            </div>
          ))}
        </div>
      </section>

      {/* Fact + Certificate */}
      <section className="grid gap-6 md:grid-cols-[1.3fr_0.7fr]">
        <div className="rounded-2xl border-4 border-black bg-surface-low shadow-card p-6 h-[100px] flex items-start gap-4">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer flex-shrink-0" />
          <div className="space-y-2 flex-1">
            <div className="h-4 w-48 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer" />
            <div className="h-4 w-full rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer" />
          </div>
        </div>
        <div className="rounded-2xl border-4 border-black bg-surface-low shadow-card p-6 h-[100px] flex flex-col justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer" />
            <div className="space-y-1">
              <div className="h-4 w-32 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer" />
              <div className="h-3 w-40 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer" />
            </div>
          </div>
          <div className="h-10 w-full rounded-lg bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer" />
        </div>
      </section>

      {/* Learning Queue + Progress */}
      <section className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
        <div className="rounded-2xl border-4 border-black bg-surface-low shadow-card p-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-full bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer" />
            <div className="h-8 w-56 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer" />
          </div>
          <div className="space-y-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="p-5 rounded-lg border-4 border-black bg-surface-lowest"
              >
                <div className="flex justify-between mb-2">
                  <div className="h-6 w-3/4 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer" />
                  <div className="h-5 w-20 rounded-full bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer" />
                </div>
                <div className="h-4 w-full rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer mb-2" />
                <div className="h-3 w-40 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer" />
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-2xl border-4 border-black bg-surface-low shadow-card p-6">
          <div className="h-6 w-48 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer mb-4" />
          <div className="h-[200px] w-[200px] rounded-full bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer mx-auto" />
          <div className="h-4 w-56 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer mx-auto mt-6" />
        </div>
      </section>

      {/* Bookmarks */}
      <div className="rounded-[2.5rem] border-4 border-black bg-surface-low shadow-card p-6 sm:p-8">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-full bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer" />
          <div className="h-8 w-40 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer" />
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="p-5 rounded-lg border-4 border-black bg-surface-lowest"
            >
              <div className="h-5 w-3/4 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer mb-3" />
              <div className="h-5 w-20 rounded-full bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer" />
            </div>
          ))}
        </div>
      </div>

      {/* Badges */}
      <div className="rounded-[2.5rem] border-4 border-black bg-surface-low shadow-card p-6 sm:p-8">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-8 h-8 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer" />
          <div className="h-8 w-64 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer" />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
          {Array.from({ length: 8 }).map((_, i) => (
            <div
              key={i}
              className="rounded-2xl border-4 border-black bg-surface-lowest p-5 flex flex-col items-center"
            >
              <div className="w-14 h-14 rounded-full bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer mb-3" />
              <div className="h-4 w-24 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer mb-1" />
              <div className="h-3 w-32 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer" />
            </div>
          ))}
        </div>
      </div>

      {/* Contributors + Issues */}
      <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-2xl border-4 border-black bg-surface-low shadow-card p-6">
          <div className="h-6 w-64 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer mb-4" />
          <div className="h-4 w-3/4 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer mb-6" />
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="p-3 rounded-lg border-2 border-black bg-surface flex items-center gap-2"
              >
                <div className="w-8 h-8 rounded-full bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer" />
                <div className="h-4 w-16 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer" />
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-2xl border-4 border-black bg-surface-low shadow-card p-6">
          <div className="h-6 w-48 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer mb-3" />
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="p-3 rounded-lg border-2 border-black bg-white"
              >
                <div className="h-3 w-20 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer mb-1" />
                <div className="h-4 w-full rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer" />
              </div>
            ))}
          </div>
          <div className="h-10 w-full rounded-lg bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer mt-4" />
        </div>
      </section>
    </div>
  );
}
