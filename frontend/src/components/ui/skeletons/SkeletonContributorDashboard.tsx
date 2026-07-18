import { Skeleton } from "../Skeleton";
export default function SkeletonContributorDashboard() {
  return (
    <div className="max-w-7xl mx-auto px-4 pt-24 pb-12 space-y-10">
      {/* Header + Stat Grid */}
      <section className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
        <div className="rounded-[2.5rem] border-4 border-black bg-surface-low shadow-card p-8 sm:p-10 h-[260px]">
          <Skeleton className="h-6 w-36 rounded-full mb-4" />
          <Skeleton className="h-10 w-3/4 rounded mb-4 max-w-full" />
          <Skeleton className="h-16 w-5/6 rounded-lg max-w-full" />
        </div>
        <div className="grid grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="rounded-[2rem] border-4 border-black bg-surface-low shadow-card p-6 h-[120px] flex flex-col items-center justify-center"
            >
              <Skeleton className="w-10 h-10 rounded mb-2" />
              <Skeleton className="h-8 w-12 rounded mb-1" />
              <Skeleton className="h-3 w-16 rounded " />
            </div>
          ))}
        </div>
      </section>

      {/* Fact + Certificate */}
      <section className="grid gap-6 md:grid-cols-[1.3fr_0.7fr]">
        <div className="rounded-2xl border-4 border-black bg-surface-low shadow-card p-6 h-[100px] flex items-start gap-4">
          <Skeleton className="w-12 h-12 rounded-2xl flex-shrink-0" />
          <div className="space-y-2 flex-1">
            <Skeleton className="h-4 w-48 rounded " />
            <Skeleton className="h-4 w-full rounded " />
          </div>
        </div>
        <div className="rounded-2xl border-4 border-black bg-surface-low shadow-card p-6 h-[100px] flex flex-col justify-between">
          <div className="flex items-center gap-2">
            <Skeleton className="w-8 h-8 rounded " />
            <div className="space-y-1">
              <Skeleton className="h-4 w-32 rounded " />
              <Skeleton className="h-3 w-40 rounded " />
            </div>
          </div>
          <Skeleton className="h-10 w-full rounded-lg " />
        </div>
      </section>

      {/* Learning Queue + Progress */}
      <section className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
        <div className="rounded-2xl border-4 border-black bg-surface-low shadow-card p-6">
          <div className="flex items-center gap-3 mb-6">
            <Skeleton className="w-10 h-10 rounded-full " />
            <Skeleton className="h-8 w-56 rounded " />
          </div>
          <div className="space-y-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="p-5 rounded-lg border-4 border-black bg-surface-lowest"
              >
                <div className="flex justify-between mb-2">
                  <Skeleton className="h-6 w-3/4 rounded " />
                  <Skeleton className="h-5 w-20 rounded-full " />
                </div>
                <Skeleton className="h-4 w-full rounded mb-2" />
                <Skeleton className="h-3 w-40 rounded " />
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-2xl border-4 border-black bg-surface-low shadow-card p-6">
          <Skeleton className="h-6 w-48 rounded mb-4" />
          <Skeleton className="h-[200px] w-[200px] rounded-full mx-auto" />
          <Skeleton className="h-4 w-56 rounded mx-auto mt-6" />
        </div>
      </section>

      {/* Bookmarks */}
      <div className="rounded-[2.5rem] border-4 border-black bg-surface-low shadow-card p-6 sm:p-8">
        <div className="flex items-center gap-3 mb-6">
          <Skeleton className="w-10 h-10 rounded-full " />
          <Skeleton className="h-8 w-40 rounded " />
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="p-5 rounded-lg border-4 border-black bg-surface-lowest"
            >
              <Skeleton className="h-5 w-3/4 rounded mb-3" />
              <Skeleton className="h-5 w-20 rounded-full " />
            </div>
          ))}
        </div>
      </div>

      {/* Badges */}
      <div className="rounded-[2.5rem] border-4 border-black bg-surface-low shadow-card p-6 sm:p-8">
        <div className="flex items-center gap-3 mb-6">
          <Skeleton className="w-8 h-8 rounded " />
          <Skeleton className="h-8 w-64 rounded " />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
          {Array.from({ length: 8 }).map((_, i) => (
            <div
              key={i}
              className="rounded-2xl border-4 border-black bg-surface-lowest p-5 flex flex-col items-center"
            >
              <Skeleton className="w-14 h-14 rounded-full mb-3" />
              <Skeleton className="h-4 w-24 rounded mb-1" />
              <Skeleton className="h-3 w-32 rounded " />
            </div>
          ))}
        </div>
      </div>

      {/* Contributors + Issues */}
      <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-2xl border-4 border-black bg-surface-low shadow-card p-6">
          <Skeleton className="h-6 w-64 rounded mb-4" />
          <Skeleton className="h-4 w-3/4 rounded mb-6" />
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="p-3 rounded-lg border-2 border-black bg-surface flex items-center gap-2"
              >
                <Skeleton className="w-8 h-8 rounded-full " />
                <Skeleton className="h-4 w-16 rounded " />
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-2xl border-4 border-black bg-surface-low shadow-card p-6">
          <Skeleton className="h-6 w-48 rounded mb-3" />
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="p-3 rounded-lg border-2 border-black bg-white"
              >
                <Skeleton className="h-3 w-20 rounded mb-1" />
                <Skeleton className="h-4 w-full rounded " />
              </div>
            ))}
          </div>
          <Skeleton className="h-10 w-full rounded-lg mt-4" />
        </div>
      </section>
    </div>
  );
}
