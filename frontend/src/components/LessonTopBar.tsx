import { ArrowLeft, Menu, X } from "lucide-react";
import { Link } from "react-router-dom";

interface LessonTopBarProps {
  points: number;
  isSidebarOpen: boolean;
  isZenMode: boolean;
  onToggleSidebar: () => void;
}

export function LessonTopBar({
  points,
  isSidebarOpen,
  isZenMode,
  onToggleSidebar,
}: LessonTopBarProps) {
  return (
    <header
      className={`h-[72px] border-b-4 border-black dark:border-[#2e2924] bg-white dark:bg-[#0f0e0c] flex items-center justify-between gap-2 px-3 sm:px-6 flex-shrink-0 z-40 transition-all duration-300 transform ${
        isZenMode
          ? "-translate-y-full h-0 p-0 overflow-hidden opacity-0"
          : "translate-y-0"
      }`}
    >
      <div className="flex items-center gap-2 sm:gap-3 min-w-0">
        <button
          onClick={onToggleSidebar}
          aria-label={
            isSidebarOpen ? "Close lesson outline" : "Open lesson outline"
          }
          className="lg:hidden flex items-center gap-2 font-black text-xs uppercase px-3 py-2 bg-surface-low border-2 border-black rounded-lg text-black"
        >
          {isSidebarOpen ? <X size={14} /> : <Menu size={14} />}
          Outline
        </button>
        <Link
          to="/dashboard"
          aria-label="Back to Dashboard"
          className="flex items-center gap-2 font-black text-xs uppercase px-3 py-2 bg-surface-low border-2 border-black rounded-lg text-black dark:bg-[#151411] dark:border-[#2e2924] dark:text-[#f0ebe2] hover:-translate-y-0.5 shadow-card-sm transition-all"
        >
          <ArrowLeft size={14} />
          <span className="hidden sm:inline">Back to Dashboard</span>
          <span className="sm:hidden">Exit</span>
        </Link>
      </div>

      <div className="flex items-center gap-2 sm:gap-4 flex-shrink-0">
        <span className="hidden md:inline-block font-mono text-[10px] uppercase font-bold text-muted dark:text-[#9b8f80]">
          Lesson Workspace
        </span>
        <span
          aria-label={`XP Bounties: ${points}`}
          className="font-mono text-xs font-black bg-black text-white px-3 py-1.5 rounded-full whitespace-nowrap dark:bg-[#2e2924]"
        >
          💰 <span className="hidden sm:inline">XP Bounties: </span>
          {points}
        </span>
      </div>
    </header>
  );
}
