import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '../../lib/api';

interface Milestone {
  days: number;
  multiplier: number;
  label: string;
}

interface StreakData {
  current_streak: number;
  longest_streak: number;
  current_multiplier: number;
  next_milestone: Milestone | null;
  days_to_next_milestone: number | null;
  milestone_progress_pct: number;
}

export const StreakMultiplierWidget: React.FC = () => {
  const { data, isLoading, error } = useQuery<StreakData>(
    ['streak-status'],
    () => fetchApi('/progress/streak/')
  );

  if (isLoading) {
    return (
      <div className="rounded-[2rem] border-4 border-black bg-white p-6 shadow-card flex flex-col justify-center items-center text-center dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none animate-pulse">
        <div className="w-12 h-12 bg-gray-200 rounded-full mb-4" />
        <div className="h-4 bg-gray-200 w-24 mb-2" />
        <div className="h-4 bg-gray-200 w-32" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-[2rem] border-4 border-black bg-white p-6 shadow-card text-center dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none">
        <p className="text-red-600">Failed to load streak data.</p>
      </div>
    );
  }

  const {
    current_streak,
    longest_streak,
    current_multiplier,
    next_milestone,
    days_to_next_milestone,
    milestone_progress_pct,
  } = data;

  // Simple progress ring using SVG
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (milestone_progress_pct / 100) * circumference;

  return (
    <div className="rounded-[2rem] border-4 border-black bg-white p-6 shadow-card flex flex-col justify-center items-center text-center dark:bg-[#1f1c18] dark:border-[#2e2924] dark:shadow-none">
      <div className="mb-4 relative flex items-center justify-center">
        <svg width="100" height="100" className="transform -rotate-90">
          <circle
            cx="50"
            cy="50"
            r={radius}
            stroke="#e5e7eb"
            strokeWidth="8"
            fill="none"
          />
          <circle
            cx="50"
            cy="50"
            r={radius}
            stroke="#f59e0b"
            strokeWidth="8"
            fill="none"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className="transition-all duration-500 ease-out"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-bold text-primary">{current_multiplier.toFixed(2)}×</span>
          <span className="text-sm text-gray-600">Multiplier</span>
        </div>
      </div>
      <div className="text-lg font-black text-primary drop-shadow-[2px_2px_0_#000] dark:drop-shadow-none">
        {current_streak} Day Streak
      </div>
      <div className="text-sm text-gray-600 mt-1">
        Longest: {longest_streak} Days
      </div>
      {next_milestone && (
        <div className="mt-3 text-xs text-gray-700">
          Next: {next_milestone.label} in {days_to_next_milestone} days
        </div>
      )}
    </div>
  );
};
