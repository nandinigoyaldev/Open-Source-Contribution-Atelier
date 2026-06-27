/**
 * OfflineStatusBadge.tsx
 * Small pill/badge that shows whether lesson content is served from network or cache.
 */
import React from "react";
import { Wifi, WifiOff, HardDrive, RefreshCw } from "lucide-react";
import { useNetworkStatus } from "../../context/NetworkStatusContext";

type ContentSource = "network" | "cache" | "fallback";

interface OfflineStatusBadgeProps {
  source: ContentSource;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export function OfflineStatusBadge({
  source,
  onRefresh,
  isRefreshing = false,
}: OfflineStatusBadgeProps) {
  const { isOnline } = useNetworkStatus();

  const config: Record<
    ContentSource,
    { label: string; icon: React.ReactNode; className: string; title: string }
  > = {
    network: {
      label: "Live",
      icon: <Wifi className="w-3 h-3" />,
      className:
        "bg-green-100 text-green-800 border-green-300 dark:bg-green-900/30 dark:text-green-300 dark:border-green-700",
      title: "Content is live from the server",
    },
    cache: {
      label: "Cached",
      icon: <HardDrive className="w-3 h-3" />,
      className:
        "bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-700",
      title: isOnline
        ? "Serving from local cache — click refresh to update"
        : "Offline — serving from local cache",
    },
    fallback: {
      label: "Offline",
      icon: <WifiOff className="w-3 h-3" />,
      className:
        "bg-red-100 text-red-800 border-red-300 dark:bg-red-900/30 dark:text-red-300 dark:border-red-700",
      title: "You are offline and this lesson is not cached",
    },
  };

  const { label, icon, className, title } = config[source];

  return (
    <div className="flex items-center gap-1.5">
      <span
        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[11px] font-semibold select-none ${className}`}
        title={title}
      >
        {icon}
        {label}
      </span>

      {/* Refresh button — shown when online and content can be refreshed */}
      {onRefresh && isOnline && source !== "fallback" && (
        <button
          onClick={onRefresh}
          title="Refresh lesson content"
          disabled={isRefreshing}
          className="p-1 rounded-full text-gray-500 hover:text-primary hover:bg-gray-100 dark:hover:bg-white/10 transition-colors disabled:opacity-50"
          aria-label="Refresh lesson"
        >
          <RefreshCw
            className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin" : ""}`}
          />
        </button>
      )}
    </div>
  );
}
