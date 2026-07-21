import React from "react";
import { Bell } from "lucide-react";

interface NotificationBellProps {
  unreadCount: number;
  onClick: () => void;
}

export function NotificationBell({
  unreadCount,
  onClick,
}: NotificationBellProps) {
  return (
    <button
      onClick={onClick}
      aria-label="Notifications"
      className="relative rounded-lg bg-surface-low p-2 text-muted hover:text-text dark:bg-[#151411] dark:text-[#c4bbae] dark:hover:text-[#f0ebe2] transition-colors border-2 border-black dark:border-[#2e2924] shadow-card-sm hover:-translate-y-0.5 active:translate-y-0 transition-all"
    >
      <Bell size={16} />
      {unreadCount > 0 && (
        <span className="absolute right-1.5 top-1.5 flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-75"></span>
          <span className="relative inline-flex h-2 w-2 rounded-full bg-accent"></span>
        </span>
      )}
    </button>
  );
}

export default NotificationBell;
