import React, { useState, useRef, useEffect } from "react";
import {
  Bell,
  Check,
  Info,
  MessageSquare,
  Trophy,
  AlertCircle,
  Wifi,
  WifiOff,
} from "lucide-react";
import {
  useNotifications,
  AppNotification,
} from "../../features/notifications/NotificationContext";
import { Link } from "react-router-dom";

export function NotificationMenu() {
  const {
    notifications,
    unreadCount,
    markAsRead,
    markAllAsRead,
    isWsConnected,
    isPollingFallback,
  } = useNotifications();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen]);

  const getIcon = (notif: AppNotification) => {
    switch (notif.notif_type) {
      case "badge":
      case "achievement":
        return <Trophy className="text-accent" size={18} />;
      case "comment":
        return <MessageSquare className="text-primary" size={18} />;
      case "alert":
      case "system":
        return <AlertCircle className="text-red-500" size={18} />;
      default:
        return <Info className="text-muted" size={18} />;
    }
  };

  const getLink = (notif: AppNotification) => {
    if (notif.notif_type === "badge" || notif.notif_type === "achievement")
      return "/profile";
    if (notif.meta?.contribution_id)
      return `/contributions/${notif.meta.contribution_id}`;
    return "#";
  };

  const handleNotificationClick = (notif: AppNotification) => {
    if (!notif.is_read) {
      void markAsRead(notif.id);
    }
    setIsOpen(false);
  };

  const badgeLabel =
    unreadCount > 99 ? "99+" : unreadCount > 0 ? String(unreadCount) : "";

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        aria-label={
          unreadCount > 0
            ? `Notifications, ${unreadCount} unread`
            : "Notifications"
        }
        aria-expanded={isOpen}
        className="relative rounded-lg bg-surface-low p-2 text-muted hover:text-text dark:bg-[#151411] dark:text-[#c4bbae] dark:hover:text-[#f0ebe2] transition-colors"
      >
        <Bell size={16} />
        {unreadCount > 0 && (
          <span
            className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full border border-black bg-accent px-1 text-[9px] font-black text-black"
            data-testid="notification-unread-badge"
          >
            {badgeLabel}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 sm:w-96 rounded-2xl bg-white dark:bg-[#151411] border-4 border-black dark:border-[#2e2924] shadow-card overflow-hidden z-50 flex flex-col">
          <div className="flex items-center justify-between gap-2 p-4 border-b-2 border-dashed border-black/10 dark:border-white/10">
            <div>
              <h3 className="font-bold text-sm text-text dark:text-[#f0ebe2]">
                Notifications
              </h3>
              <p className="mt-0.5 flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide text-muted dark:text-[#c4bbae]">
                {isWsConnected ? (
                  <>
                    <Wifi className="h-3 w-3 text-green-600" aria-hidden />
                    Live
                  </>
                ) : (
                  <>
                    <WifiOff className="h-3 w-3 text-amber-600" aria-hidden />
                    {isPollingFallback ? "Polling fallback" : "Connecting…"}
                  </>
                )}
              </p>
            </div>
            {unreadCount > 0 && (
              <button
                onClick={() => {
                  void markAllAsRead();
                  setIsOpen(false);
                }}
                className="text-xs font-bold text-primary hover:text-primary/80 flex items-center gap-1 transition-colors"
              >
                <Check size={14} /> Mark all read
              </button>
            )}
          </div>

          <div className="overflow-y-auto max-h-[400px]">
            {notifications.length === 0 ? (
              <div className="p-8 text-center text-muted dark:text-[#c4bbae] flex flex-col items-center">
                <Bell size={32} className="opacity-20 mb-3" />
                <p className="text-sm">You&apos;re all caught up!</p>
              </div>
            ) : (
              <div className="flex flex-col">
                {notifications.map((notif) => (
                  <Link
                    key={notif.id}
                    to={getLink(notif)}
                    onClick={() => handleNotificationClick(notif)}
                    className={`flex items-start gap-3 p-4 border-b border-black/5 dark:border-white/5 last:border-b-0 hover:bg-surface-low dark:hover:bg-[#1f1c18] transition-colors ${
                      !notif.is_read
                        ? "bg-[linear-gradient(135deg,rgba(79,70,229,0.05),rgba(195,192,255,0.05))] dark:bg-[linear-gradient(135deg,rgba(79,70,229,0.1),rgba(195,192,255,0.1))]"
                        : ""
                    }`}
                  >
                    <div className="mt-1 flex-shrink-0">{getIcon(notif)}</div>
                    <div className="flex-1 min-w-0">
                      <p
                        className={`text-sm ${!notif.is_read ? "font-bold text-text dark:text-[#f0ebe2]" : "font-medium text-muted dark:text-[#c4bbae]"}`}
                      >
                        {notif.title}
                      </p>
                      <p className="text-xs text-muted dark:text-[#c4bbae]/80 mt-1 line-clamp-2">
                        {notif.message}
                      </p>
                      <p className="text-[10px] text-muted/60 dark:text-[#c4bbae]/50 mt-2 font-mono uppercase">
                        {new Date(notif.created_at).toLocaleDateString(
                          undefined,
                          {
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          },
                        )}
                      </p>
                    </div>
                    {!notif.is_read && (
                      <div className="w-2 h-2 rounded-full bg-accent flex-shrink-0 mt-2" />
                    )}
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
