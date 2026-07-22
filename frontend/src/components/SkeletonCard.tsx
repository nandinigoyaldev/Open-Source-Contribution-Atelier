import React from 'react';

interface SkeletonCardProps {
  variant?: 'stats' | 'chart' | 'badge' | 'activity';
  count?: number;
  className?: string;
}

const SkeletonCard: React.FC<SkeletonCardProps> = ({ 
  variant = 'stats', 
  count = 1,
  className = '' 
}) => {
  const renderSkeleton = () => {
    switch (variant) {
      case 'stats':
        return (
          <div className={`bg-white dark:bg-slate-800 rounded-xl p-6 shadow-sm border border-slate-200 dark:border-slate-700 animate-pulse ${className}`}>
            <div className="flex items-center justify-between">
              <div className="space-y-3 flex-1">
                <div className="h-4 w-20 bg-slate-200 dark:bg-slate-700 rounded"></div>
                <div className="h-8 w-16 bg-slate-200 dark:bg-slate-700 rounded"></div>
              </div>
              <div className="h-12 w-12 bg-slate-200 dark:bg-slate-700 rounded-full"></div>
            </div>
            <div className="mt-4 h-3 w-32 bg-slate-200 dark:bg-slate-700 rounded"></div>
          </div>
        );

      case 'badge':
        return (
          <div className={`bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm border border-slate-200 dark:border-slate-700 animate-pulse ${className}`}>
            <div className="flex items-center gap-4">
              <div className="h-14 w-14 bg-slate-200 dark:bg-slate-700 rounded-full"></div>
              <div className="flex-1 space-y-2">
                <div className="h-4 w-24 bg-slate-200 dark:bg-slate-700 rounded"></div>
                <div className="h-3 w-16 bg-slate-200 dark:bg-slate-700 rounded"></div>
              </div>
            </div>
          </div>
        );

      case 'activity':
        return (
          <div className={`bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm border border-slate-200 dark:border-slate-700 animate-pulse ${className}`}>
            <div className="flex items-center gap-4">
              <div className="h-10 w-10 bg-slate-200 dark:bg-slate-700 rounded-full"></div>
              <div className="flex-1 space-y-2">
                <div className="h-4 w-32 bg-slate-200 dark:bg-slate-700 rounded"></div>
                <div className="h-3 w-24 bg-slate-200 dark:bg-slate-700 rounded"></div>
              </div>
              <div className="h-6 w-16 bg-slate-200 dark:bg-slate-700 rounded-full"></div>
            </div>
          </div>
        );

      case 'chart':
        return (
          <div className={`bg-white dark:bg-slate-800 rounded-xl p-6 shadow-sm border border-slate-200 dark:border-slate-700 animate-pulse ${className}`}>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="h-5 w-32 bg-slate-200 dark:bg-slate-700 rounded"></div>
                <div className="h-4 w-20 bg-slate-200 dark:bg-slate-700 rounded"></div>
              </div>
              <div className="h-48 bg-slate-200 dark:bg-slate-700 rounded-lg"></div>
              <div className="flex justify-between">
                {[...Array(6)].map((_, i) => (
                  <div key={i} className="h-3 w-8 bg-slate-200 dark:bg-slate-700 rounded"></div>
                ))}
              </div>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  if (count > 1) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(count)].map((_, i) => (
          <div key={i}>{renderSkeleton()}</div>
        ))}
      </div>
    );
  }

  return renderSkeleton();
};

export default SkeletonCard;