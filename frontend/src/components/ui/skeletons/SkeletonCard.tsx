export default function SkeletonCard() {
  return (
    <div
      aria-hidden="true"
      className="border-4 border-black rounded-[2rem] shadow-card bg-surface-low motion-safe:animate-pulse p-6 space-y-4"
    >
      <div className="h-6 w-1/2 rounded bg-surface-high"></div>
      <div className="h-4 w-full rounded bg-surface-high"></div>
      <div className="h-4 w-3/4 rounded bg-surface-high"></div>
    </div>
  );
}
