export default function SkeletonLesson() {
  return (
    <div
      aria-hidden="true"
      className="max-w-3xl mx-auto p-6 space-y-6 border-4 border-black rounded-[2rem] shadow-card bg-surface-low"
    >
      <div className="h-8 w-1/3 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer"></div>
      <div className="space-y-2">
        <div className="h-4 w-full rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer"></div>
        <div className="h-4 w-3/4 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer"></div>
      </div>
      <div className="h-10 w-full rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer"></div>
    </div>
  );
}
