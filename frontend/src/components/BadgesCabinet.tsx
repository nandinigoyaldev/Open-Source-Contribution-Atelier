import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import BadgeTooltip from './BadgeTooltip';

// Types
interface Badge {
  id: string;
  name: string;
  description: string;
  icon: string;
  unlockCriteria: string;
  earned: boolean;
  earnedAt?: string;
}

interface BadgesCabinetProps {
  badges: Badge[];
  loading?: boolean;
  className?: string;
}

const BadgesCabinet: React.FC<BadgesCabinetProps> = ({
  badges = [],
  loading = false,
  className = '',
}) => {
  const [selectedFilter, setSelectedFilter] = useState<'all' | 'earned' | 'locked'>('all');

  // Filter badges
  const filteredBadges = badges.filter((badge) => {
    if (selectedFilter === 'earned') return badge.earned;
    if (selectedFilter === 'locked') return !badge.earned;
    return true;
  });

  // Stats
  const earnedCount = badges.filter((b) => b.earned).length;
  const totalCount = badges.length;

  // Loading state
  if (loading) {
    return (
      <div className={`p-6 rounded-2xl border border-black/10 dark:border-white/10 bg-white dark:bg-[#111] ${className}`}>
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-xl font-black dark:text-white">🏅 Badges Cabinet</h3>
          <span className="text-sm font-bold text-muted dark:text-[#8a8377] animate-pulse">Loading...</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="aspect-square rounded-2xl bg-slate-200 dark:bg-slate-800 animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className={`p-6 rounded-2xl border border-black/10 dark:border-white/10 bg-white dark:bg-[#111] ${className}`}>
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div>
          <h3 className="text-xl font-black dark:text-white flex items-center gap-2">
            🏅 Badges Cabinet
            <span className="text-sm font-bold text-muted dark:text-[#8a8377] bg-black/5 dark:bg-white/5 px-3 py-1 rounded-full">
              {earnedCount}/{totalCount}
            </span>
          </h3>
          <p className="text-xs font-medium text-muted dark:text-[#8a8377] mt-0.5">
            Hover or tap on any badge to learn more
          </p>
        </div>

        {/* Filter Buttons */}
        <div className="flex gap-1.5 p-1 bg-black/5 dark:bg-white/5 rounded-xl">
          {[
            { id: 'all', label: 'All' },
            { id: 'earned', label: `✅ Earned (${earnedCount})` },
            { id: 'locked', label: `🔒 Locked (${totalCount - earnedCount})` },
          ].map((filter) => (
            <button
              key={filter.id}
              onClick={() => setSelectedFilter(filter.id as any)}
              className={`px-3 py-1.5 text-xs font-black rounded-lg transition-all ${
                selectedFilter === filter.id
                  ? 'bg-indigo-500 text-white shadow-lg shadow-indigo-500/30'
                  : 'text-muted dark:text-[#8a8377] hover:bg-black/5 dark:hover:bg-white/5'
              }`}
            >
              {filter.label}
            </button>
          ))}
        </div>
      </div>

      {/* Badges Grid */}
      <AnimatePresence mode="wait">
        <motion.div
          key={selectedFilter}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.2 }}
          className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4"
        >
          {filteredBadges.map((badge) => (
            <motion.div
              key={badge.id}
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ delay: 0.05 }}
              className="relative group"
            >
              {/* Tooltip Wrapper */}
              <BadgeTooltip
                name={badge.name}
                description={badge.description}
                unlockCriteria={badge.unlockCriteria}
                isEarned={badge.earned}
                icon={badge.icon}
                side="top"
                delayDuration={300}
              >
                <div
                  className={`
                    aspect-square rounded-2xl flex flex-col items-center justify-center
                    border-2 transition-all duration-300 cursor-help
                    ${
                      badge.earned
                        ? 'bg-gradient-to-br from-emerald-50 to-teal-50 dark:from-emerald-900/20 dark:to-teal-900/20 border-emerald-200 dark:border-emerald-800 hover:shadow-[0_0_20px_rgba(16,185,129,0.2)]'
                        : 'bg-slate-50 dark:bg-slate-900/50 border-slate-200 dark:border-slate-700 opacity-60 grayscale hover:grayscale-0 hover:opacity-80'
                    }
                    group-hover:scale-105 active:scale-95
                  `}
                >
                  <span className="text-4xl mb-1">{badge.icon}</span>
                  <span className="text-[10px] font-bold text-center px-1 leading-tight dark:text-white line-clamp-2">
                    {badge.name}
                  </span>
                  {badge.earned && (
                    <span className="absolute -top-1 -right-1 w-5 h-5 bg-emerald-500 rounded-full flex items-center justify-center text-[10px] text-white shadow-lg">
                      ✓
                    </span>
                  )}
                </div>
              </BadgeTooltip>
            </motion.div>
          ))}
        </motion.div>
      </AnimatePresence>

      {/* Empty State */}
      {filteredBadges.length === 0 && (
        <div className="py-12 text-center">
          <p className="text-sm font-bold text-muted dark:text-[#8a8377]">
            {selectedFilter === 'earned'
              ? "You haven't earned any badges yet. Keep contributing!"
              : 'All badges have been earned! 🎉'}
          </p>
        </div>
      )}
    </div>
  );
};

export default BadgesCabinet;