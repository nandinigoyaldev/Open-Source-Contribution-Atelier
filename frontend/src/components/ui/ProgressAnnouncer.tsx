import type { ProgressAnnouncement } from "../../hooks/useUserProgress";

/**
 * Visually hidden live regions that announce the result of a lesson
 * completion sync. Both regions stay mounted so screen readers pick up
 * text changes.
 */
export function ProgressAnnouncer({
  announcement,
}: {
  announcement: ProgressAnnouncement;
}) {
  return (
    <>
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {announcement?.type === "success" ? announcement.message : ""}
      </div>
      <div
        role="alert"
        aria-live="assertive"
        aria-atomic="true"
        className="sr-only"
      >
        {announcement?.type === "error" ? announcement.message : ""}
      </div>
    </>
  );
}
