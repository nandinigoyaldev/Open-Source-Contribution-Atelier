import { Skeleton } from "../Skeleton";
export default function SkeletonLesson() {
  return (
    <div
      aria-hidden="true"
      className="max-w-3xl mx-auto p-6 space-y-6 border-4 border-black rounded-[2rem] shadow-card bg-surface-low"
    >
      <Skeleton className="h-8 w-1/3 rounded "></Skeleton>
      <div className="space-y-2">
        <Skeleton className="h-4 w-full rounded "></Skeleton>
        <Skeleton className="h-4 w-3/4 rounded "></Skeleton>
      </div>
      <Skeleton className="h-10 w-full rounded "></Skeleton>
    </div>
  );
}
