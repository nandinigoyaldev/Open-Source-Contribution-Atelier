export default function SkeletonCard() {
  return (
    <div
      aria-hidden="true"
      className="border-2 border-black rounded-lg p-2.5 flex items-center gap-2 bg-white animate-pulse"
    >
      {/* Logo placeholder */}
      <div className="w-8 h-8 rounded-lg bg-surface-high flex-shrink-0" />

      {/* Text placeholder */}
      <div className="flex flex-col gap-1.5 flex-1 min-w-0">
        <div className="h-3 w-3/4 rounded bg-surface-high" />
        <div className="h-2.5 w-1/3 rounded bg-surface-high" />
      </div>
    </div>
  );
}