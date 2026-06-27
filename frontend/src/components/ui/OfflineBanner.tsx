/**
 * OfflineBanner.tsx
 * Full-width informational banner displayed when:
 *  - User is offline AND the lesson has never been cached, OR
 *  - User is online but an error occurred fetching the lesson.
 */
import React from "react";
import { WifiOff, BookOpen } from "lucide-react";

interface OfflineBannerProps {
  lessonTitle?: string;
  /** When true, the lesson is cached and we show a softer "you're offline" message */
  isCached?: boolean;
}

export function OfflineBanner({ lessonTitle, isCached = false }: OfflineBannerProps) {
  if (isCached) {
    // Soft banner — user is offline but can still read
    return (
      <div className="flex items-start gap-3 p-4 mb-4 rounded-xl border border-amber-300 bg-amber-50 dark:bg-amber-900/20 dark:border-amber-700 text-amber-800 dark:text-amber-200 text-sm">
        <WifiOff className="w-4 h-4 mt-0.5 flex-shrink-0" />
        <div>
          <span className="font-semibold">You&apos;re offline. </span>
          Showing cached version of{" "}
          {lessonTitle ? (
            <span className="font-semibold">{lessonTitle}</span>
          ) : (
            "this lesson"
          )}
          . Reconnect to get the latest content.
        </div>
      </div>
    );
  }

  // Hard banner — lesson not in cache
  return (
    <div className="flex flex-col items-center justify-center gap-4 p-10 rounded-2xl border-2 border-dashed border-gray-300 dark:border-gray-600 text-center bg-gray-50 dark:bg-gray-800/40">
      <div className="w-16 h-16 rounded-full bg-gray-200 dark:bg-gray-700 flex items-center justify-center">
        <WifiOff className="w-8 h-8 text-gray-400" />
      </div>
      <div>
        <h3 className="text-lg font-bold text-gray-700 dark:text-gray-200 mb-1">
          You&apos;re offline
        </h3>
        <p className="text-sm text-gray-500 dark:text-gray-400 max-w-sm">
          {lessonTitle ? (
            <>
              <span className="font-semibold text-gray-700 dark:text-gray-200">
                {lessonTitle}
              </span>{" "}
              hasn&apos;t been cached yet.
            </>
          ) : (
            "This lesson hasn't been cached yet."
          )}{" "}
          Open this lesson while online first so it&apos;s available offline.
        </p>
      </div>
      <div className="flex items-center gap-2 text-xs text-gray-400 dark:text-gray-500">
        <BookOpen className="w-3.5 h-3.5" />
        <span>Previously viewed lessons are automatically cached</span>
      </div>
    </div>
  );
}
