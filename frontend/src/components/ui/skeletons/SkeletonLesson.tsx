export default function SkeletonLesson() {
  return (
    <div
      aria-hidden="true"
      className="max-w-3xl mx-auto p-6 space-y-6 border-4 border-black rounded-[2rem] shadow-card bg-surface-low motion-safe:animate-pulse"
    >
      <div className="h-8 w-1/3 rounded bg-surface-high"></div>
      <div className="space-y-2">
        <div className="h-4 w-full rounded bg-surface-high"></div>
        <div className="h-4 w-3/4 rounded bg-surface-high"></div>
      </div>
      <div className="h-10 w-full rounded bg-surface-high"></div>
    </div>
  );
}
