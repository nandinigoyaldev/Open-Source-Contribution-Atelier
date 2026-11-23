import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { AlertCircle, Lock, ArrowLeft, RefreshCw, CheckCircle2 } from 'lucide-react';
import { useChallengeTabLock } from '../lib/tabLock';

export const ChallengeRunnerPage: React.FC = () => {
  const { challengeId = 'default-challenge' } = useParams<{ challengeId: string }>();
  const navigate = useNavigate();
  const { isLockedByOtherTab, conflictInfo, isOwner, acquire } = useChallengeTabLock(challengeId);
  const [timeLeft, setTimeLeft] = useState(600); // 10 minute timed quiz
  const [isRetrying, setIsRetrying] = useState(false);

  useEffect(() => {
    if (!isOwner || isLockedByOtherTab) return;
    const interval = setInterval(() => {
      setTimeLeft((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(interval);
  }, [isOwner, isLockedByOtherTab]);

  const handleRetry = async () => {
    setIsRetrying(true);
    await acquire();
    setIsRetrying(false);
  };

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  if (isLockedByOtherTab) {
    return (
      <div className="min-h-screen bg-slate-900 text-white flex items-center justify-center p-6">
        <div
          data-testid="tab-lock-overlay"
          className="max-w-md w-full bg-slate-800 border border-amber-500/50 rounded-xl p-8 text-center shadow-2xl relative"
        >
          <div className="w-16 h-16 bg-amber-500/20 text-amber-400 rounded-full flex items-center justify-center mx-auto mb-4">
            <Lock className="w-8 h-8" />
          </div>
          <h2 className="text-2xl font-bold text-white mb-2">Assessment Active in Another Tab</h2>
          <p className="text-slate-300 mb-6">
            Assessment active in another tab. Please continue in your open session.
          </p>
          {conflictInfo && (
            <div className="text-xs text-slate-400 mb-6 bg-slate-900/60 p-3 rounded-lg border border-slate-700/50">
              Active Session Tab ID: <span className="font-mono text-amber-300">{conflictInfo.holderTabId}</span>
            </div>
          )}
          <div className="flex flex-col gap-3">
            <button
              onClick={handleRetry}
              disabled={isRetrying}
              className="w-full py-2.5 px-4 bg-amber-500 hover:bg-amber-600 text-slate-950 font-semibold rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${isRetrying ? 'animate-spin' : ''}`} />
              Retry Lock Acquisition
            </button>
            <button
              onClick={() => navigate('/challenges')}
              className="w-full py-2.5 px-4 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              <ArrowLeft className="w-4 h-4" />
              Return to Challenges
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-900 text-white p-6">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-8 pb-4 border-b border-slate-800">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/challenges')}
              className="p-2 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-white transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-2xl font-bold">Timed Challenge: {challengeId}</h1>
              <p className="text-xs text-emerald-400 flex items-center gap-1.5 mt-1">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Single-session active & synchronized
              </p>
            </div>
          </div>
          <div className="bg-slate-800 px-4 py-2 rounded-xl border border-slate-700 font-mono text-lg font-bold text-amber-400">
            ⏱️ {formatTime(timeLeft)}
          </div>
        </div>

        <div className="bg-slate-800/80 border border-slate-700 rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-2">Instructions</h2>
          <p className="text-slate-300 text-sm leading-relaxed mb-6">
            Complete the challenge steps within the allocated timer. Navigating away or closing this tab
            will cleanly release your session lock.
          </p>
        </div>
      </div>
    </div>
  );
};

export default ChallengeRunnerPage;
