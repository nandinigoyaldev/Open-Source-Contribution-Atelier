import type { BookmarkAnnouncement } from "../../hooks/useBookmarks";

/**
 * Visually hidden live regions that announce the result of a bookmark
 * addition or removal. Both regions stay mounted so screen readers pick up
 * text changes.
 */
export function BookmarkAnnouncer({
  announcement,
}: {
  announcement: BookmarkAnnouncement;
}) {
  return (
    <>
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
        data-testid="bookmark-announcer-status"
      >
        {announcement?.type === "success" ? announcement.message : ""}
      </div>
      <div
        role="alert"
        aria-live="assertive"
        aria-atomic="true"
        className="sr-only"
        data-testid="bookmark-announcer-alert"
      >
        {announcement?.type === "error" ? announcement.message : ""}
      </div>
    </>
  );
}
