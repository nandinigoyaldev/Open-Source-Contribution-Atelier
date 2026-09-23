import { Skeleton } from "../Skeleton";

const SKELETON_ROW_COUNT = 8;

function LeaderboardSkeletonRow() {
  return (
    <tr className="h-16">
      <td className="w-16 px-4 py-4 text-center">
        <Skeleton className="mx-auto h-4 w-8 rounded" />
      </td>
      <td className="px-3 py-4 text-center">
        <Skeleton className="mx-auto h-3 w-6 rounded" />
      </td>
      <td className="px-4 py-4">
        <div className="flex items-center gap-3">
          <Skeleton className="h-9 w-9 shrink-0 rounded-full" />
          <Skeleton className="h-4 w-28 rounded" />
        </div>
      </td>
      <td className="px-4 py-4">
        <Skeleton className="h-6 w-36 rounded-full" />
      </td>
      <td className="px-4 py-4 text-center">
        <Skeleton className="mx-auto h-4 w-12 rounded" />
      </td>
      <td className="px-4 py-4 text-center">
        <Skeleton className="mx-auto h-4 w-10 rounded" />
      </td>
      <td className="px-4 py-4 text-right">
        <Skeleton className="ml-auto h-4 w-16 rounded" />
      </td>
      <td className="px-4 py-4 text-center">
        <Skeleton className="mx-auto h-8 w-20 rounded-xl" />
      </td>
    </tr>
  );
}

export function LeaderboardSkeleton() {
  return (
    <tbody
      className="divide-y-2 divide-black dark:divide-[#2e2924]"
      data-testid="leaderboard-skeleton"
      aria-busy="true"
      aria-label="Loading leaderboard"
    >
      {Array.from({ length: SKELETON_ROW_COUNT }).map((_, index) => (
        <LeaderboardSkeletonRow key={index} />
      ))}
    </tbody>
  );
}

export default LeaderboardSkeleton;
