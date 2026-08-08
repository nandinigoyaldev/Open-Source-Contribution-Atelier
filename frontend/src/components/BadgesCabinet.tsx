import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search,
  X,
  ChevronLeft,
  ChevronRight,
  Layers,
  Sparkles,
  CheckCircle2,
  Lock,
  RotateCcw,
} from 'lucide-react';
import BadgeTooltip from './BadgeTooltip';

// Types
export interface Badge {
  id: string | number;
  name: string;
  description: string;
  icon: string;
  unlockCriteria: string;
  earned: boolean;
  earnedAt?: string;
  module?: string;
  category?: string;
}

export interface BadgesCabinetProps {
  badges: Badge[];
  loading?: boolean;
  className?: string;
  pageSize?: number;
  initialGroupByModule?: boolean;
}

const BadgesCabinet: React.FC<BadgesCabinetProps> = ({
  badges = [],
  loading = false,
  className = '',
  pageSize = 12,
  initialGroupByModule = false,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedFilter, setSelectedFilter] = useState<'all' | 'earned' | 'locked'>('all');
  const [selectedModule, setSelectedModule] = useState<string>('all');
  const [groupByModule, setGroupByModule] = useState<boolean>(initialGroupByModule);
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState<number>(pageSize);

  // Extract unique modules/categories
  const modulesList = useMemo(() => {
    const mods = new Set<string>();
    badges.forEach((b) => {
      const mod = b.module || b.category;
      if (mod) mods.add(mod);
    });
    return Array.from(mods).sort();
  }, [badges]);

  // Overall Stats
  const earnedCount = badges.filter((b) => b.earned).length;
  const totalCount = badges.length;

  // Filtered badges computation
  const filteredBadges = useMemo(() => {
    return badges.filter((badge) => {
      // 1. Status Filter
      if (selectedFilter === 'earned' && !badge.earned) return false;
      if (selectedFilter === 'locked' && badge.earned) return false;

      // 2. Module Filter
      const badgeMod = badge.module || badge.category || 'General';
      if (selectedModule !== 'all' && badgeMod !== selectedModule) return false;

      // 3. Search Query Filter
      if (searchQuery.trim() !== '') {
        const query = searchQuery.toLowerCase().trim();
        const matchesName = badge.name.toLowerCase().includes(query);
        const matchesDesc = badge.description.toLowerCase().includes(query);
        const matchesCriteria = badge.unlockCriteria.toLowerCase().includes(query);
        const matchesModule = badgeMod.toLowerCase().includes(query);
        if (!matchesName && !matchesDesc && !matchesCriteria && !matchesModule) {
          return false;
        }
      }

      return true;
    });
  }, [badges, selectedFilter, selectedModule, searchQuery]);

  // Reset pagination when filters change
  const handleFilterChange = (filter: 'all' | 'earned' | 'locked') => {
    setSelectedFilter(filter);
    setCurrentPage(1);
  };

  const handleSearchChange = (query: string) => {
    setSearchQuery(query);
    setCurrentPage(1);
  };

  const handleModuleChange = (mod: string) => {
    setSelectedModule(mod);
    setCurrentPage(1);
  };

  const handleGroupByModuleToggle = () => {
    setGroupByModule((prev) => !prev);
    setCurrentPage(1);
  };

  const handleItemsPerPageChange = (size: number) => {
    setItemsPerPage(size);
    setCurrentPage(1);
  };

  const resetFilters = () => {
    setSearchQuery('');
    setSelectedFilter('all');
    setSelectedModule('all');
    setCurrentPage(1);
  };

  // Pagination bounds
  const totalFiltered = filteredBadges.length;
  const totalPages = Math.ceil(totalFiltered / itemsPerPage) || 1;
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = Math.min(startIndex + itemsPerPage, totalFiltered);
  const currentBadges = filteredBadges.slice(startIndex, endIndex);

  // Grouped badges map for rendering
  const groupedCurrentBadges = useMemo(() => {
    if (!groupByModule) return null;
    const map: Record<string, Badge[]> = {};
    currentBadges.forEach((badge) => {
      const groupName = badge.module || badge.category || 'General';
      if (!map[groupName]) map[groupName] = [];
      map[groupName].push(badge);
    });
    return map;
  }, [currentBadges, groupByModule]);

  // Loading state
  if (loading) {
    return (
      <div
        className={`p-6 rounded-2xl border border-black/10 dark:border-white/10 bg-white dark:bg-[#111] ${className}`}
      >
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-xl font-black dark:text-white flex items-center gap-2">
            🏅 Badges Cabinet
          </h3>
          <span className="text-sm font-bold text-muted dark:text-[#8a8377] animate-pulse">
            Loading...
          </span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {[...Array(6)].map((_, i) => (
            <div
              key={i}
              className="aspect-square rounded-2xl bg-slate-200 dark:bg-slate-800 animate-pulse"
            />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div
      className={`p-6 rounded-2xl border border-black/10 dark:border-white/10 bg-white dark:bg-[#111] ${className}`}
    >
      {/* Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-5">
        <div>
          <h3 className="text-xl font-black dark:text-white flex items-center gap-2">
            🏅 Badges Cabinet
            <span className="text-sm font-bold text-muted dark:text-[#8a8377] bg-black/5 dark:bg-white/5 px-3 py-1 rounded-full">
              {earnedCount}/{totalCount}
            </span>
          </h3>
          <p className="text-xs font-medium text-muted dark:text-[#8a8377] mt-0.5">
            Search, filter, and track earned achievements across learning modules
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
              onClick={() => handleFilterChange(filter.id as any)}
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

      {/* Control Bar: Search Input, Module Filter & Group Toggle */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        {/* Search Field */}
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Search badges by name, description, or unlock criteria..."
            className="w-full pl-9 pr-8 py-2 text-xs font-medium rounded-xl border border-black/10 dark:border-white/10 bg-black/5 dark:bg-white/5 text-black dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
          />
          {searchQuery && (
            <button
              onClick={() => handleSearchChange('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 text-slate-400 hover:text-black dark:hover:text-white"
              aria-label="Clear search query"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Module Selector & Grouping Controls */}
        <div className="flex items-center gap-2 flex-wrap">
          {modulesList.length > 0 && (
            <select
              value={selectedModule}
              onChange={(e) => handleModuleChange(e.target.value)}
              aria-label="Filter by module"
              className="px-3 py-2 text-xs font-bold rounded-xl border border-black/10 dark:border-white/10 bg-black/5 dark:bg-white/5 text-black dark:text-white cursor-pointer focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
            >
              <option value="all">All Modules ({modulesList.length})</option>
              {modulesList.map((mod) => (
                <option key={mod} value={mod}>
                  {mod}
                </option>
              ))}
            </select>
          )}

          <button
            onClick={handleGroupByModuleToggle}
            className={`px-3 py-2 text-xs font-bold rounded-xl flex items-center gap-1.5 transition-all ${
              groupByModule
                ? 'bg-indigo-500 text-white shadow-md'
                : 'bg-black/5 dark:bg-white/5 text-slate-600 dark:text-slate-300 hover:bg-black/10 dark:hover:bg-white/10'
            }`}
            title="Toggle grouping by module"
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Group by Module</span>
          </button>
        </div>
      </div>

      {/* Subtle Legend */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 mb-5 rounded-xl bg-slate-50 dark:bg-[#181614] border border-black/5 dark:border-white/5 text-xs">
        <div className="flex flex-wrap items-center gap-4">
          <span className="font-bold text-slate-500 dark:text-[#8a8377] flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
            Legend:
          </span>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold text-[11px] border border-emerald-500/20">
              <CheckCircle2 className="w-3 h-3" />
              Earned
            </span>
            <span className="text-slate-500 dark:text-[#8a8377] text-[11px]">
              Criteria completed
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400 font-semibold text-[11px] border border-slate-300 dark:border-slate-700">
              <Lock className="w-3 h-3" />
              Locked
            </span>
            <span className="text-slate-500 dark:text-[#8a8377] text-[11px]">
              Unlock criteria pending
            </span>
          </div>
        </div>

        {filteredBadges.length > 0 && (
          <span className="text-[11px] font-medium text-slate-400">
            Hover or tap badge for details
          </span>
        )}
      </div>

      {/* Badges Content (Grouped vs Flat Grid) */}
      <AnimatePresence mode="wait">
        <motion.div
          key={`${selectedFilter}-${selectedModule}-${groupByModule}-${currentPage}-${searchQuery}`}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.2 }}
        >
          {groupByModule && groupedCurrentBadges ? (
            /* Grouped View */
            <div className="space-y-6">
              {Object.entries(groupedCurrentBadges).map(([modName, modBadges]) => {
                const modEarned = modBadges.filter((b) => b.earned).length;
                return (
                  <div
                    key={modName}
                    className="p-4 rounded-xl bg-black/[0.02] dark:bg-white/[0.02] border border-black/5 dark:border-white/5"
                  >
                    <div className="flex items-center justify-between mb-3 border-b border-black/5 dark:border-white/5 pb-2">
                      <h4 className="text-xs font-black uppercase tracking-wider text-black dark:text-white flex items-center gap-2">
                        <span>📌</span>
                        <span>{modName}</span>
                      </h4>
                      <span className="text-[11px] font-bold text-slate-500 dark:text-[#8a8377]">
                        {modEarned}/{modBadges.length} earned
                      </span>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
                      {modBadges.map((badge) => (
                        <BadgeCard key={badge.id} badge={badge} />
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            /* Flat Grid View */
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
              {currentBadges.map((badge) => (
                <BadgeCard key={badge.id} badge={badge} />
              ))}
            </div>
          )}
        </motion.div>
      </AnimatePresence>

      {/* Empty State */}
      {totalFiltered === 0 && (
        <div className="py-12 text-center border-2 border-dashed border-black/10 dark:border-white/10 rounded-2xl">
          <div className="text-4xl mb-2">🔍</div>
          <p className="text-sm font-bold text-black dark:text-white mb-1">
            No badges match your criteria
          </p>
          <p className="text-xs text-slate-500 dark:text-[#8a8377] mb-4">
            Try adjusting your search terms or status filters.
          </p>
          <button
            onClick={resetFilters}
            className="px-4 py-2 text-xs font-bold rounded-xl bg-indigo-500 text-white hover:bg-indigo-600 transition-all inline-flex items-center gap-1.5 shadow-md shadow-indigo-500/20"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Reset All Filters
          </button>
        </div>
      )}

      {/* Pagination Footer Controls */}
      {totalFiltered > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-4 mt-6 pt-4 border-t border-black/10 dark:border-white/10">
          <div className="text-xs font-medium text-slate-500 dark:text-[#8a8377]">
            Showing <span className="font-bold text-black dark:text-white">{startIndex + 1}</span> to{' '}
            <span className="font-bold text-black dark:text-white">{endIndex}</span> of{' '}
            <span className="font-bold text-black dark:text-white">{totalFiltered}</span> badges
          </div>

          <div className="flex items-center gap-3">
            {/* Page Size Selector */}
            <select
              value={itemsPerPage === Number.MAX_SAFE_INTEGER ? 'all' : itemsPerPage}
              onChange={(e) =>
                handleItemsPerPageChange(
                  e.target.value === 'all' ? Number.MAX_SAFE_INTEGER : Number(e.target.value)
                )
              }
              aria-label="Items per page"
              className="px-2 py-1 text-xs font-bold rounded-lg border border-black/10 dark:border-white/10 bg-black/5 dark:bg-white/5 text-black dark:text-white cursor-pointer focus:outline-none"
            >
              <option value={8}>8 per page</option>
              <option value={12}>12 per page</option>
              <option value={24}>24 per page</option>
              <option value="all">Show All</option>
            </select>

            {/* Pagination buttons */}
            {totalPages > 1 && (
              <div className="flex items-center gap-1">
                <button
                  disabled={currentPage === 1}
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  className="p-1.5 rounded-lg border border-black/10 dark:border-white/10 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-black/5 dark:hover:bg-white/5 text-black dark:text-white"
                  aria-label="Previous page"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>

                {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                  <button
                    key={page}
                    onClick={() => setCurrentPage(page)}
                    className={`w-7 h-7 text-xs font-bold rounded-lg transition-all ${
                      currentPage === page
                        ? 'bg-indigo-500 text-white shadow-md shadow-indigo-500/30'
                        : 'hover:bg-black/5 dark:hover:bg-white/5 text-slate-600 dark:text-slate-400'
                    }`}
                  >
                    {page}
                  </button>
                ))}

                <button
                  disabled={currentPage === totalPages}
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  className="p-1.5 rounded-lg border border-black/10 dark:border-white/10 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-black/5 dark:hover:bg-white/5 text-black dark:text-white"
                  aria-label="Next page"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

// Helper Badge Item Card
const BadgeCard: React.FC<{ badge: Badge }> = ({ badge }) => (
  <motion.div
    initial={{ scale: 0.9, opacity: 0 }}
    animate={{ scale: 1, opacity: 1 }}
    transition={{ delay: 0.03 }}
    className="relative group"
  >
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
          aspect-square rounded-2xl flex flex-col items-center justify-center p-2
          border-2 transition-all duration-300 cursor-help relative
          ${
            badge.earned
              ? 'bg-gradient-to-br from-emerald-50 to-teal-50 dark:from-emerald-900/20 dark:to-teal-900/20 border-emerald-200 dark:border-emerald-800 hover:shadow-[0_0_20px_rgba(16,185,129,0.25)]'
              : 'bg-slate-50 dark:bg-slate-900/50 border-slate-200 dark:border-slate-700 opacity-60 grayscale hover:grayscale-0 hover:opacity-80'
          }
          group-hover:scale-105 active:scale-95
        `}
      >
        <span className="text-3xl sm:text-4xl mb-1 select-none">{badge.icon}</span>
        <span className="text-[10px] font-bold text-center leading-tight dark:text-white line-clamp-2">
          {badge.name}
        </span>
        {badge.module && (
          <span className="text-[8px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-tighter mt-0.5 truncate max-w-full">
            {badge.module}
          </span>
        )}
        {badge.earned && (
          <span className="absolute -top-1 -right-1 w-5 h-5 bg-emerald-500 rounded-full flex items-center justify-center text-[10px] text-white shadow-lg">
            ✓
          </span>
        )}
      </div>
    </BadgeTooltip>
  </motion.div>
);

export default BadgesCabinet;