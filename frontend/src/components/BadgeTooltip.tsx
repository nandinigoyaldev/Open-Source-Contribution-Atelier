import React from 'react';
import * as Tooltip from '@radix-ui/react-tooltip';
import { Info, Award, Lock, Unlock } from 'lucide-react';

interface BadgeTooltipProps {
  /** Child element to wrap with tooltip */
  children: React.ReactNode;
  /** Badge name/title */
  name: string;
  /** Badge description */
  description: string;
  /** How to unlock the badge */
  unlockCriteria: string;
  /** Whether the badge is earned */
  isEarned?: boolean;
  /** Icon for the badge */
  icon?: string;
  /** Position of tooltip */
  side?: 'top' | 'bottom' | 'left' | 'right';
  /** Delay before showing tooltip (ms) */
  delayDuration?: number;
}

const BadgeTooltip: React.FC<BadgeTooltipProps> = ({
  children,
  name,
  description,
  unlockCriteria,
  isEarned = false,
  icon = '🏅',
  side = 'top',
  delayDuration = 300,
}) => {
  return (
    <Tooltip.Provider delayDuration={delayDuration}>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          {children}
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content
            side={side}
            sideOffset={8}
            className="
              z-[999] max-w-xs p-4 rounded-2xl
              bg-white dark:bg-[#1f1c18]
              border-2 border-black dark:border-[#2e2924]
              shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] dark:shadow-[4px_4px_0px_0px_rgba(46,41,36,1)]
              animate-in fade-in-0 zoom-in-95 duration-200
              data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95
            "
          >
            {/* Tooltip Arrow */}
            <Tooltip.Arrow className="fill-black dark:fill-[#2e2924]" />

            {/* Badge Icon */}
            <div className="flex items-start gap-3 mb-3">
              <div className="text-4xl flex-shrink-0">{icon}</div>
              <div className="flex-1">
                <h4 className="text-sm font-black text-black dark:text-[#f0ebe2] flex items-center gap-2">
                  {name}
                  {isEarned ? (
                    <span className="text-[10px] bg-emerald-500 text-white px-2 py-0.5 rounded-full font-bold">
                      Earned ✅
                    </span>
                  ) : (
                    <span className="text-[10px] bg-slate-300 dark:bg-slate-700 text-slate-700 dark:text-slate-300 px-2 py-0.5 rounded-full font-bold">
                      Locked 🔒
                    </span>
                  )}
                </h4>
              </div>
            </div>

            {/* Description */}
            <div className="mb-3">
              <p className="text-xs font-medium text-slate-600 dark:text-[#c4bbae] leading-relaxed">
                {description}
              </p>
            </div>

            {/* Divider */}
            <div className="border-t border-black/10 dark:border-white/10 my-2" />

            {/* Unlock Criteria */}
            <div className="mt-2">
              <div className="flex items-center gap-1.5 mb-1">
                {isEarned ? (
                  <Unlock className="w-3.5 h-3.5 text-emerald-500" />
                ) : (
                  <Lock className="w-3.5 h-3.5 text-slate-400" />
                )}
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-[#8a8377]">
                  {isEarned ? 'Earned by' : 'How to Unlock'}
                </span>
              </div>
              <p className="text-xs font-medium text-black dark:text-[#e8e0d6] leading-relaxed">
                {unlockCriteria}
              </p>
            </div>

            {/* Earned Date (if applicable) */}
            {isEarned && (
              <div className="mt-2 pt-2 border-t border-black/5 dark:border-white/5">
                <p className="text-[10px] font-bold text-slate-400 dark:text-[#6b655a]">
                  ✨ Achievement unlocked
                </p>
              </div>
            )}
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  );
};

// ============================================
// SIMPLIFIED VERSION (Native Tooltip)
// ============================================

export const SimpleBadgeTooltip: React.FC<BadgeTooltipProps> = ({
  children,
  name,
  description,
  unlockCriteria,
  isEarned = false,
}) => {
  const tooltipText = `
${name}
${isEarned ? '✅ Earned' : '🔒 Locked'}
${description}
Unlock: ${unlockCriteria}
  `.trim();

  return (
    <div title={tooltipText} className="inline-block">
      {children}
    </div>
  );
};

export default BadgeTooltip;