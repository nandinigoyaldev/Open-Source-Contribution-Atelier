import React, { useState, useEffect } from "react";

type ConnectionStatusIndicatorProps = {
  state: 'CONNECTING' | 'OPEN' | 'CLOSING' | 'CLOSED' | 'RECONNECTING' | string;
  getMetrics?: () => any;
};

export const ConnectionStatusIndicator: React.FC<ConnectionStatusIndicatorProps> = ({ state, getMetrics }) => {
  const [showTooltip, setShowTooltip] = useState(false);
  const [metrics, setMetrics] = useState<any>(null);

  useEffect(() => {
    if (showTooltip && getMetrics) {
      const interval = setInterval(() => {
        setMetrics(getMetrics());
      }, 1000);
      setMetrics(getMetrics());
      return () => clearInterval(interval);
    }
  }, [showTooltip, getMetrics]);

  let colorClass = "bg-red-500";
  let statusText = "Disconnected";

  if (state === 'OPEN') {
    colorClass = "bg-green-500";
    statusText = "Connected";
  } else if (state === 'CONNECTING' || state === 'RECONNECTING' || state === 'connecting') {
    colorClass = "bg-yellow-500 animate-pulse";
    statusText = state === 'RECONNECTING' ? "Reconnecting" : "Connecting";
  } else if (state === 'CLOSING') {
    colorClass = "bg-orange-500";
    statusText = "Closing";
  }

  return (
    <div 
      className="relative flex items-center gap-1.5 cursor-pointer select-none"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <span className={`h-2.5 w-2.5 rounded-full ${colorClass}`} />
      <span className="text-[11px] font-bold text-slate-400 dark:text-[#a0a0ab] uppercase tracking-wider">
        {statusText}
      </span>

      {showTooltip && metrics && (
        <div className="absolute right-0 top-full mt-2 w-64 bg-slate-900 text-white text-xs p-3 rounded-lg shadow-xl z-50 border border-slate-700 space-y-1.5">
          <div className="font-semibold border-b border-slate-700 pb-1 mb-1">WS Connection Metrics</div>
          <div className="flex justify-between">
            <span className="text-slate-400">State:</span>
            <span className="font-mono uppercase">{metrics.state}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Uptime:</span>
            <span className="font-mono">{metrics.uptime}s</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Reconnections:</span>
            <span className="font-mono">{metrics.reconnectionCount}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Sent / Received:</span>
            <span className="font-mono">{metrics.messagesSent} / {metrics.messagesReceived}</span>
          </div>
          {metrics.lastError && (
            <div className="text-red-400 mt-1 pt-1 border-t border-slate-800 text-[10px] break-words">
              <strong>Last Error:</strong> {metrics.lastError}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
