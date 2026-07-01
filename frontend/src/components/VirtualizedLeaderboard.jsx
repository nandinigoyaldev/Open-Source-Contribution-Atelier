import React from 'react';
import { FixedSizeList as List } from 'react-window';

const VirtualizedLeaderboard = ({ data, darkMode }) => {
  // Each row renderer
  const Row = ({ index, style }) => {
    const item = data[index];
    const rank = index + 1;
    const isTop3 = rank <= 3;

    return (
      <div 
        style={style} 
        className={`flex items-center px-4 py-2 border-b ${
          darkMode ? 'border-slate-700' : 'border-slate-200'
        } ${isTop3 ? (darkMode ? 'bg-yellow-900/20' : 'bg-yellow-50') : ''}`}
      >
        <span className={`w-12 font-bold text-center ${
          rank === 1 ? 'text-yellow-500' : 
          rank === 2 ? 'text-slate-400' : 
          rank === 3 ? 'text-orange-400' : 
          (darkMode ? 'text-slate-400' : 'text-slate-600')
        }`}>
          {rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : `#${rank}`}
        </span>
        <span className={`flex-1 ${darkMode ? 'text-white' : 'text-slate-800'}`}>
          {item.username || item.name || 'Unknown User'}
        </span>
        <span className={`w-20 text-right font-semibold ${darkMode ? 'text-blue-400' : 'text-blue-600'}`}>
          {item.points || item.score || 0}
        </span>
        <span className={`w-24 text-right text-sm ${darkMode ? 'text-slate-400' : 'text-slate-600'}`}>
          {item.contributions || item.count || 0}
        </span>
      </div>
    );
  };

  if (!data || data.length === 0) {
    return (
      <div className="text-center py-8 opacity-60">
        No leaderboard data available
      </div>
    );
  }

  return (
    <div className="w-full">
      {/* Header */}
      <div className={`flex items-center px-4 py-2 rounded-t-lg font-semibold ${
        darkMode ? 'bg-slate-800 text-slate-200' : 'bg-slate-100 text-slate-700'
      }`}>
        <span className="w-12 text-center">#</span>
        <span className="flex-1">User</span>
        <span className="w-20 text-right">Points</span>
        <span className="w-24 text-right">Contributions</span>
      </div>

      {/* Virtualized List */}
      <List
        height={450}
        itemCount={data.length}
        itemSize={50}
        width="100%"
        className="scrollbar-thin scrollbar-thumb-slate-300 dark:scrollbar-thumb-slate-600"
      >
        {Row}
      </List>

      {/* Footer */}
      <div className={`text-center text-xs py-2 ${
        darkMode ? 'text-slate-500' : 'text-slate-400'
      }`}>
        Showing {data.length} contributors
      </div>
    </div>
  );
};

export default VirtualizedLeaderboard;