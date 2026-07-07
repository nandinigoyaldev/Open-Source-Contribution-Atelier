import React, { useState, useRef, useEffect } from "react";
import { Bell, Check, Info, MessageSquare, Trophy, AlertCircle } from "lucide-react";
import { useNotifications, AppNotification } from "../../features/notifications/NotificationContext";
import { Link } from "react-router-dom";

export function NotificationMenu() {
  const { notifications, unreadCount, markAsRead, markAllAsRead } = useNotifications();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
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
    if (notif.notif_type === "badge" || notif.notif_type === "achievement") return "/profile";
    if (notif.meta?.contribution_id) return `/contributions/${notif.meta.contribution_id}`;
    return "#";
  };

  const handleNotificationClick = (notif: AppNotification) => {
    if (!notif.is_read) {
      markAsRead(notif.id);
    }
    setIsOpen(false);
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        aria-label="Notifications"
        aria-expanded={isOpen}
        className="relative rounded-lg bg-surface-low p-2 text-muted hover:text-text dark:bg-[#151411] dark:text-[#c4bbae] dark:hover:text-[#f0ebe2] transition-colors"
      >
        <Bell size={16} />
        {unreadCount > 0 && (
          <span className="absolute right-1.5 top-1.5 flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-75"></span>
            <span className="relative inline-flex h-2 w-2 rounded-full bg-accent"></span>
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 sm:w-96 rounded-2xl bg-white dark:bg-[#151411] border-4 border-black dark:border-[#2e2924] shadow-card overflow-hidden z-50 flex flex-col">
          <div className="flex items-center justify-between p-4 border-b-2 border-dashed border-black/10 dark:border-white/10">
            <h3 className="font-bold text-sm text-text dark:text-[#f0ebe2]">Notifications</h3>
            {unreadCount > 0 && (
              <button
                onClick={() => {
                  markAllAsRead();
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
                <p className="text-sm">You're all caught up!</p>
              </div>
            ) : (
              <div className="flex flex-col">
                {notifications.map((notif) => (
                  <Link
                    key={notif.id}
                    to={getLink(notif)}
                    onClick={() => handleNotificationClick(notif)}
                    className={`flex items-start gap-3 p-4 border-b border-black/5 dark:border-white/5 last:border-b-0 hover:bg-surface-low dark:hover:bg-[#1f1c18] transition-colors ${
                      !notif.is_read ? "bg-[linear-gradient(135deg,rgba(79,70,229,0.05),rgba(195,192,255,0.05))] dark:bg-[linear-gradient(135deg,rgba(79,70,229,0.1),rgba(195,192,255,0.1))]" : ""
                    }`}
                  >
                    <div className="mt-1 flex-shrink-0">
                      {getIcon(notif)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className={`text-sm ${!notif.is_read ? 'font-bold text-text dark:text-[#f0ebe2]' : 'font-medium text-muted dark:text-[#c4bbae]'}`}>
                        {notif.title}
                      </p>
                      <p className="text-xs text-muted dark:text-[#c4bbae]/80 mt-1 line-clamp-2">
                        {notif.message}
                      </p>
                      <p className="text-[10px] text-muted/60 dark:text-[#c4bbae]/50 mt-2 font-mono uppercase">
                        {new Date(notif.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
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
