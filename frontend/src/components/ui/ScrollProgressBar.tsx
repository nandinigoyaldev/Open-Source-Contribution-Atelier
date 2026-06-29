export function ScrollProgressBar({ progress = 0 }: { progress?: number }) {
  return (
    <div
      className="fixed top-0 left-0 right-0 h-1 z-[60] pointer-events-none"
      role="progressbar"
      aria-valuenow={Math.round(progress)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label="Reading progress"
    >
      <div
        className="h-full bg-primary transition-all duration-150 ease-out"
        style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
      />
    </div>
  );
}
