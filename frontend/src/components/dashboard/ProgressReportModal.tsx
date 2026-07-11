import { Printer, X } from "lucide-react";
import { SocialShareButtons } from "../ui/SocialShareButtons";
import { BADGES } from "../../constants/badges";
import { ModuleProgressList } from "./ModuleProgressList";
import type { ModuleData, PersonalStats } from "./types";

interface ProgressReportModalProps {
  isOpen: boolean;
  onClose: () => void;
  username?: string;
  completionPercentage: number;
  completedLessonsCount: number;
  totalLessonsCount: number;
  personalStats: PersonalStats;
  earnedBadges: string[];
  modules: ModuleData[];
  isLessonCompleted: (slug: string) => boolean;
}

export function ProgressReportModal({
  isOpen,
  onClose,
  username,
  completionPercentage,
  completedLessonsCount,
  totalLessonsCount,
  personalStats,
  earnedBadges,
  modules,
  isLessonCompleted,
}: ProgressReportModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/75 z-50 flex items-center justify-center p-4 overflow-y-auto">
      <div className="certificate-printable w-full max-w-2xl bg-white rounded-[2rem] border-8 border-black p-8 sm:p-10 relative shadow-card print:border-none print:shadow-none print:p-0 print:bg-white print:text-black dark:bg-[#1f1c18] dark:border-[#2e2924]">
        <button
          onClick={onClose}
          className="no-print absolute top-4 right-4 bg-white border-2 border-black p-2 rounded-full hover:bg-surface-low transition-colors print:hidden"
          aria-label="Close progress report"
        >
          <X size={16} />
        </button>

        <div className="space-y-6">
          <div className="text-center">
            <div className="text-5xl mb-2">📊</div>
            <h2 className="text-3xl font-black uppercase tracking-tight text-text dark:text-[#f0ebe2]">
              Progress Report
            </h2>
            <p className="font-mono text-xs text-primary uppercase tracking-widest font-black mt-1">
              The Open Source Contribution Atelier
            </p>
            <h3 className="text-xl font-black text-text mt-3 dark:text-[#f0ebe2]">
              {username}
            </h3>
            <p className="text-xs text-muted dark:text-[#c4bbae] mt-1">
              Generated on {new Date().toLocaleDateString()}
            </p>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 border-t border-b border-black/10 py-4">
            <div className="text-center">
              <span className="block text-2xl font-black text-text dark:text-[#f0ebe2]">
                {completionPercentage}%
              </span>
              <span className="block text-[10px] uppercase font-bold text-muted dark:text-[#c4bbae]">
                Curriculum
              </span>
            </div>
            <div className="text-center">
              <span className="block text-2xl font-black text-text dark:text-[#f0ebe2]">
                {completedLessonsCount}/{totalLessonsCount}
              </span>
              <span className="block text-[10px] uppercase font-bold text-muted dark:text-[#c4bbae]">
                Lessons
              </span>
            </div>
            <div className="text-center">
              <span className="block text-2xl font-black text-text dark:text-[#f0ebe2]">
                {personalStats.total_xp ?? 0}
              </span>
              <span className="block text-[10px] uppercase font-bold text-muted dark:text-[#c4bbae]">
                XP
              </span>
            </div>
            <div className="text-center">
              <span className="block text-2xl font-black text-text dark:text-[#f0ebe2]">
                {personalStats.streak_days ?? 0}
              </span>
              <span className="block text-[10px] uppercase font-bold text-muted dark:text-[#c4bbae]">
                Day Streak
              </span>
            </div>
          </div>

          <ModuleProgressList
            modules={modules}
            isLessonCompleted={isLessonCompleted}
          />

          <div>
            <h4 className="font-black text-xs uppercase tracking-wider text-muted dark:text-[#c4bbae] mb-3">
              Badges Earned ({earnedBadges.length}/{BADGES.length})
            </h4>
            {earnedBadges.length > 0 ? (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {BADGES.filter((badge) => earnedBadges.includes(badge.id)).map(
                  (badge) => (
                    <div
                      key={badge.id}
                      className="flex items-center gap-2 rounded-lg border-2 border-black bg-surface-low p-2 dark:bg-[#151411] dark:border-[#2e2924]"
                    >
                      <span className="text-lg">{badge.icon}</span>
                      <span className="text-xs font-bold text-text dark:text-[#f0ebe2] leading-tight">
                        {badge.name}
                      </span>
                    </div>
                  ),
                )}
              </div>
            ) : (
              <p className="text-xs text-muted dark:text-[#c4bbae]">
                No badges earned yet — keep going!
              </p>
            )}
          </div>
        </div>

        <div className="no-print mt-8 flex gap-3 print:hidden items-center">
          <button
            onClick={() => window.print()}
            className="flex items-center gap-2 rounded-lg bg-primary text-black border-4 border-black px-6 py-3 font-black text-sm shadow-card-sm hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-card-sm cursor-pointer"
          >
            <Printer size={16} /> Export as PDF
          </button>
          <SocialShareButtons
            url="https://github.com/nandinigoyaldev/Open-Source-Contribution-Atelier"
            title={`I just hit ${personalStats.total_xp ?? 0} XP on the Open Source Contribution Atelier!`}
            hashtags="OpenSource,ContributionAtelier"
          />
          <button
            onClick={onClose}
            className="rounded-lg bg-white border-4 border-black px-6 py-3 font-black text-sm shadow-card-sm hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-card-sm cursor-pointer"
          >
            Return to Dashboard
          </button>
        </div>
      </div>
    </div>
  );
}
