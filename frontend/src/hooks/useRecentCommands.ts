import { useState, useEffect } from "react";

export interface RecentCommand {
  id: string; // A unique identifier for the command (e.g., path, action type)
  title: string;
  type: "navigation" | "lesson" | "heading" | "content" | "action";
  to?: string;
  timestamp: number;
}

const STORAGE_KEY = "ca_recent_commands";
const MAX_RECENT = 5;

export function useRecentCommands() {
  const [recentCommands, setRecentCommands] = useState<RecentCommand[]>([]);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        setRecentCommands(JSON.parse(stored));
      }
    } catch (err) {
      console.error("Failed to load recent commands:", err);
    }
  }, []);

  const addRecentCommand = (command: Omit<RecentCommand, "timestamp">) => {
    setRecentCommands((prev) => {
      // Remove if it already exists to avoid duplicates
      const filtered = prev.filter((c) => c.id !== command.id);

      const newCommand: RecentCommand = {
        ...command,
        timestamp: Date.now(),
      };

      const updated = [newCommand, ...filtered].slice(0, MAX_RECENT);

      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      } catch (err) {
        console.error("Failed to save recent commands:", err);
      }

      return updated;
    });
  };

  const clearRecentCommands = () => {
    setRecentCommands([]);
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (err) {
      console.error("Failed to clear recent commands:", err);
    }
  };

  return { recentCommands, addRecentCommand, clearRecentCommands };
}
