import { useState, useEffect } from "react";
import { Timer } from "lucide-react";

export function SessionTracker() {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      // Only increment if the tab is active
      if (document.visibilityState === "visible") {
        setSeconds((s) => s + 1);
      }
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const formatTime = (totalSeconds: number) => {
    const h = Math.floor(totalSeconds / 3600);
    const m = Math.floor((totalSeconds % 3600) / 60);
    const s = totalSeconds % 60;

    if (h > 0) {
      return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
    }
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  return (
    <div
      className="fixed bottom-6 right-6 z-50 flex items-center gap-2 bg-white px-4 py-2 rounded-full border-4 border-black shadow-card text-sm font-black uppercase tracking-wider text-text dark:bg-[#151411] dark:border-[#2e2924] dark:text-[#f0ebe2] dark:shadow-none hover:-translate-y-1 transition-transform"
      title="Time Spent Coding this session"
    >
      <Timer size={16} className="text-primary animate-pulse" />
      <span>{formatTime(seconds)}</span>
    </div>
  );
}
