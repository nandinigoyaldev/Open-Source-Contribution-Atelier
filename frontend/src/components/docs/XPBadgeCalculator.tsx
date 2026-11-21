import React, { useState, useMemo } from "react";
import { motion, useReducedMotion } from "framer-motion";

interface Module {
  id: string;
  title: string;
  xp: number;
}

const MODULES: Module[] = [
  { id: "module-1", title: "Introduction to Open Source", xp: 90 },
  { id: "module-2", title: "Git Fundamentals", xp: 100 },
  { id: "module-3", title: "GitHub Fundamentals", xp: 90 },
  { id: "module-4", title: "Open Source Etiquette", xp: 60 },
  { id: "module-5", title: "First Contribution Walkthrough", xp: 25 },
  { id: "module-6", title: "Real Contribution Workflow", xp: 20 },
  { id: "module-7", title: "Advanced Open Source", xp: 60 },
  { id: "module-8", title: "Finding Projects", xp: 15 },
];

const BADGES = [
  { id: "bronze", name: "Bronze Level", xpThreshold: 100, icon: "🥉" },
  { id: "silver", name: "Silver Level", xpThreshold: 250, icon: "🥈" },
  { id: "gold", name: "Gold Level", xpThreshold: 400, icon: "🥇" },
];

const MAX_XP = MODULES.reduce((sum, m) => sum + m.xp, 0);

const XPBadgeCalculator: React.FC = () => {
  const reduceMotion = useReducedMotion() === true;
  const [selectedModules, setSelectedModules] = useState<Set<string>>(
    new Set(),
  );

  const handleToggle = (id: string) => {
    setSelectedModules((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const currentXP = useMemo(() => {
    return MODULES.filter((m) => selectedModules.has(m.id)).reduce(
      (total, m) => total + m.xp,
      0,
    );
  }, [selectedModules]);

  const progressPercentage = Math.min((currentXP / MAX_XP) * 100, 100);

  return (
    <div className="p-6 rounded-2xl border border-black/10 dark:border-white/10 bg-white dark:bg-[#111] my-8 font-sans">
      <div className="mb-6">
        <h3 className="text-xl font-black dark:text-white mb-2">
          XP & Badge Simulator
        </h3>
        <p className="text-sm font-medium text-muted dark:text-[#8a8377]">
          Select modules to simulate XP gains and watch badges unlock!
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-8">
        {/* Module Selection */}
        <div className="space-y-3">
          <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wider mb-4">
            Curriculum Modules
          </h4>
          {MODULES.map((module) => (
            <label
              key={module.id}
              className="flex items-center gap-3 p-3 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-900/50 cursor-pointer transition-colors"
            >
              <input
                type="checkbox"
                checked={selectedModules.has(module.id)}
                onChange={() => handleToggle(module.id)}
                className="w-5 h-5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                aria-label={`Toggle ${module.title}`}
              />
              <div className="flex-1">
                <span className="block text-sm font-bold dark:text-white">
                  {module.title}
                </span>
              </div>
              <span className="text-xs font-black text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-900/30 px-2 py-1 rounded-md">
                +{module.xp} XP
              </span>
            </label>
          ))}
        </div>

        {/* Progress & Badges */}
        <div className="flex flex-col">
          <div className="bg-slate-50 dark:bg-slate-900/50 p-6 rounded-xl border border-slate-200 dark:border-slate-800 flex-1 flex flex-col justify-center">
            {/* XP Counter */}
            <div className="text-center mb-8">
              <span className="text-5xl font-black text-indigo-600 dark:text-indigo-400 tabular-nums">
                {currentXP}
              </span>
              <span className="text-lg font-bold text-slate-500 dark:text-slate-400 ml-2">
                / {MAX_XP} XP
              </span>
            </div>

            {/* Progress Bar */}
            <div className="relative h-4 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden mb-10">
              <motion.div
                className="absolute top-0 left-0 h-full bg-gradient-to-r from-indigo-500 to-purple-500"
                initial={reduceMotion ? false : { width: 0 }}
                animate={{ width: `${progressPercentage}%` }}
                transition={reduceMotion ? { duration: 0 } : { type: "spring", stiffness: 50, damping: 15 }}
              />
            </div>

            {/* Badges */}
            <div className="flex justify-between items-end gap-2">
              {BADGES.map((badge) => {
                const isUnlocked = currentXP >= badge.xpThreshold;
                return (
                  <div
                    key={badge.id}
                    className="flex flex-col items-center flex-1 relative group"
                  >
                    <motion.div
                      className={`
                        w-16 h-16 sm:w-20 sm:h-20 rounded-2xl flex items-center justify-center text-4xl sm:text-5xl border-2 mb-3
                        transition-all duration-500 relative
                        ${
                          isUnlocked
                            ? "bg-gradient-to-br from-emerald-50 to-teal-50 dark:from-emerald-900/20 dark:to-teal-900/20 border-emerald-200 dark:border-emerald-800 shadow-[0_0_20px_rgba(16,185,129,0.3)]"
                            : "bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-slate-700 opacity-50 grayscale"
                        }
                      `}
                      animate={
                        isUnlocked && !reduceMotion
                          ? { scale: [1, 1.1, 1], rotate: [0, -5, 5, 0] }
                          : { scale: 1, rotate: 0 }
                      }
                      transition={{ duration: reduceMotion ? 0 : 0.5 }}
                    >
                      {badge.icon}
                      {isUnlocked && (
                        <motion.span
                          initial={reduceMotion ? false : { scale: 0 }}
                          animate={{ scale: 1 }}
                          transition={reduceMotion ? { duration: 0 } : undefined}
                          className="absolute -top-2 -right-2 w-6 h-6 bg-emerald-500 rounded-full flex items-center justify-center text-xs text-white shadow-lg"
                        >
                          ✓
                        </motion.span>
                      )}
                    </motion.div>
                    <span className="text-xs font-bold text-center dark:text-white leading-tight">
                      {badge.name}
                    </span>
                    <span className="text-[10px] font-medium text-slate-500 dark:text-slate-400 mt-1">
                      {badge.xpThreshold} XP
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default XPBadgeCalculator;
