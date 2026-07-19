import React, { useEffect } from "react";
import { X, Check, Bell, Trophy, MessageSquare, AlertCircle, Info } from "lucide-react";
import { Link } from "react-router-dom";
import { AppNotification } from "../../features/notifications/notificationSlice";

interface NotificationDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  notifications: AppNotification[];
  unreadCount: number;
  isLoading: boolean;
  hasMore: boolean;
  loadMore: () => void;
  markAsRead: (id: number) => void;
  markAllAsRead: () => void;
}

export function NotificationDrawer({
  isOpen,
  onClose,
  notifications,
  unreadCount,
  isLoading,
  hasMore,
  loadMore,
  markAsRead,
  markAllAsRead,
}: NotificationDrawerProps) {
  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    if (isOpen) {
      document.addEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "hidden"; // Prevent background scroll
    }
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const getIcon = (notif: AppNotification) => {
    switch (notif.notif_type) {
      case "badge":
      case "achievement":
        return <Trophy className="text-[#F1C40F]" size={18} />;
      case "comment":
        return <MessageSquare className="text-[#4f46e5]" size={18} />;
      case "alert":
      case "system":
        return <AlertCircle className="text-red-500" size={18} />;
      default:
        return <Info className="text-gray-500" size={18} />;
    }
  };

  const getLink = (notif: AppNotification) => {
    if (notif.notif_type === "badge" || notif.notif_type === "achievement")
      return "/profile";
    if (notif.meta?.contribution_id)
      return `/contributions/${notif.meta.contribution_id}`;
    return "#";
  };

  return (
    <div className="fixed inset-0 z-[100] flex justify-end">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      {/* Drawer */}
      <div className="relative w-full max-w-md h-full bg-white dark:bg-[#151411] border-l-4 border-black dark:border-[#2e2924] shadow-2xl flex flex-col z-10 transition-transform duration-300 transform translate-x-0">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b-4 border-black dark:border-[#2e2924]">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-black uppercase text-black dark:text-white">Notifications</h2>
            {unreadCount > 0 && (
              <span className="bg-accent text-black font-black text-xs px-2 py-0.5 rounded-full border border-black">
                {unreadCount} new
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            {unreadCount > 0 && (
              <button
                onClick={markAllAsRead}
                className="text-xs font-bold text-black dark:text-white hover:text-black/80 flex items-center gap-1 transition-colors uppercase border-2 border-black bg-white dark:bg-[#1f1c18] px-2 py-1 rounded shadow-card-sm active:translate-y-0 hover:-translate-y-0.5 transition-all"
              >
                <Check size={14} /> Mark all read
              </button>
            )}
            <button
              onClick={onClose}
              className="p-1 rounded-lg border-2 border-black hover:bg-gray-100 dark:hover:bg-[#1f1c18] transition-colors"
              aria-label="Close drawer"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {notifications.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center p-8 text-center text-gray-500 dark:text-[#c4bbae]">
              <Bell size={48} className="opacity-20 mb-4 animate-bounce" />
              <p className="font-bold text-lg text-black dark:text-white">No notifications yet</p>
              <p className="text-sm mt-1">We'll alert you when something important happens.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {notifications.map((notif) => (
                <Link
                  key={notif.id}
                  to={getLink(notif)}
                  onClick={() => {
                    if (!notif.is_read) markAsRead(notif.id);
                    onClose();
                  }}
                  className={`block p-4 rounded-xl border-2 border-black dark:border-[#2e2924] shadow-card-sm transition-all hover:-translate-y-0.5 hover:shadow-card hover:bg-surface-low dark:hover:bg-[#1f1c18] ${
                    !notif.is_read
                      ? "bg-[#C3C0FF]/10 border-l-8 border-l-[#4f46e5] dark:bg-[#C3C0FF]/5"
                      : "bg-white dark:bg-[#151411]"
                  }`}
                >
                  <div className="flex gap-3">
                    <div className="mt-1 flex-shrink-0">{getIcon(notif)}</div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <p className={`text-sm ${!notif.is_read ? "font-black text-black dark:text-white" : "font-bold text-gray-500 dark:text-[#c4bbae]"}`}>
                          {notif.title}
                        </p>
                        {!notif.is_read && (
                          <span className="w-2.5 h-2.5 rounded-full bg-accent border border-black flex-shrink-0 mt-1" />
                        )}
                      </div>
                      <p className="text-xs text-gray-500 dark:text-[#c4bbae]/80 mt-1">
                        {notif.message}
                      </p>
                      <p className="text-[9px] text-gray-500/60 dark:text-[#c4bbae]/50 mt-3 font-mono uppercase">
                        {new Date(notif.created_at).toLocaleDateString(undefined, {
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </p>
                    </div>
                  </div>
                </Link>
              ))}

              {/* Load More Button */}
              {hasMore && (
                <button
                  onClick={loadMore}
                  disabled={isLoading}
                  className="w-full py-3 rounded-xl border-2 border-black bg-white dark:bg-[#1f1c18] font-bold text-sm text-black dark:text-white shadow-card-sm hover:-translate-y-0.5 hover:shadow-card active:translate-y-0 transition-all uppercase disabled:opacity-50"
                >
                  {isLoading ? "Loading..." : "Load More"}
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
