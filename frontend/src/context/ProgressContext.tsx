import React, { createContext, useContext, ReactNode } from "react";

import { useLocalSyncGeneric } from "../hooks/useLocalSyncGeneric";

export interface Progress {
  lessons: string[];
  xp: number;
  streak: number;
}

export interface ProgressContextType {
  data: Progress;
  setData: (newData: Progress) => void;
  sync: () => Promise<void>;
  isSyncing: boolean;
  error: string | null;
}

const ProgressContext = createContext<ProgressContextType | null>(null);

export function ProgressProvider({ children }: { children: ReactNode }) {
  const progress = useLocalSyncGeneric<Progress>("user_progress", {
    lessons: [],
    xp: 0,
    streak: 0,
  });

  return (
    <ProgressContext.Provider value={progress}>
      {children}
    </ProgressContext.Provider>
  );
}

export function useProgress(): ProgressContextType {
  const context = useContext(ProgressContext);

  if (!context) {
    throw new Error("useProgress must be used within a ProgressProvider");
  }

  return context;
}
