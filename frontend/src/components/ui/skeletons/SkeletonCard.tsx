export default function SkeletonCard() {
  return (
    <div
      aria-hidden="true"
      className="border-4 border-black rounded-[2rem] shadow-card bg-surface-low p-6 space-y-4"
    >
      <div className="h-6 w-1/2 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer"></div>
      <div className="h-4 w-full rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer"></div>
      <div className="h-4 w-3/4 rounded bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer"></div>
    </div>
  );
}
