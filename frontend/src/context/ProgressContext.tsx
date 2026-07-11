import React, { createContext, useContext, ReactNode } from "react";
import { useLocalSyncGeneric } from "../hooks/useLocalSyncGeneric";

interface Progress {
  lessons: string[];
  xp: number;
  streak: number;
}

const ProgressContext = createContext<any>(null);

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

export const useProgress = () => useContext(ProgressContext);
