import React, { useState } from 'react';

interface PredictionResult {
  predicted_delay_hours: number;
  confidence_interval_hours: number;
  min_predicted_delay_hours: number;
  max_predicted_delay_hours: number;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  recommendation: string;
}

export const PRReviewPredictionWidget: React.FC = () => {
  const [prNumber, setPrNumber] = useState<number>(1848);
  const [additions, setAdditions] = useState<number>(350);
  const [deletions, setDeletions] = useState<number>(85);
  const [changedFiles, setChangedFiles] = useState<number>(6);
  const [currentWorkload, setCurrentWorkload] = useState<number>(3);
  const [reviewerName, setReviewerName] = useState<string>('alex_maintainer');
  const [prediction, setPrediction] = useState<PredictionResult | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handlePredict = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await fetch('/api/predictions/predict/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pr_number: prNumber,
          additions,
          deletions,
          changed_files: changedFiles,
          current_workload: currentWorkload,
          assigned_reviewer: reviewerName,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setPrediction(data);
      } else {
        const errData = await res.json().catch(() => ({}));
        setError(errData.error || `Prediction API returned status ${res.status}. Could not compute prediction.`);
        setPrediction(null);
      }
    } catch (err: any) {
      setError('Network error: Unable to connect to PR Delay Prediction service.');
      setPrediction(null);
    } finally {
      setLoading(false);
    }
  };

  const getRiskBadgeColor = (risk: string) => {
    switch (risk) {
      case 'LOW':
        return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
      case 'MEDIUM':
        return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
      case 'HIGH':
        return 'bg-orange-500/20 text-orange-400 border-orange-500/30';
      case 'CRITICAL':
        return 'bg-rose-500/20 text-rose-400 border-rose-500/30';
      default:
        return 'bg-slate-500/20 text-slate-400 border-slate-500/30';
    }
  };

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6 shadow-xl backdrop-blur-md">
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div>
          <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <span className="text-indigo-400">⚡</span> PR Review Delay Predictor
          </h2>
          <p className="text-xs text-slate-400">
            ML-Powered Review Stagnation Prevention &amp; Availability Optimizer
          </p>
        </div>
        <span className="rounded-full bg-indigo-500/10 px-3 py-1 text-xs font-semibold text-indigo-400 border border-indigo-500/20">
          Target: 30% Faster Turnaround
        </span>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Form Inputs */}
        <form onSubmit={handlePredict} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-400">PR Number</label>
              <input
                type="number"
                value={prNumber}
                onChange={(e) => setPrNumber(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400">Assigned Reviewer</label>
              <input
                type="text"
                value={reviewerName}
                onChange={(e) => setReviewerName(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none"
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-400">Additions (+)</label>
              <input
                type="number"
                value={additions}
                onChange={(e) => setAdditions(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-emerald-400 focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400">Deletions (-)</label>
              <input
                type="number"
                value={deletions}
                onChange={(e) => setDeletions(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-rose-400 focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400">Files Changed</label>
              <input
                type="number"
                value={changedFiles}
                onChange={(e) => setChangedFiles(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-400">
              Reviewer Open Workload (Active PRs assigned)
            </label>
            <input
              type="number"
              value={currentWorkload}
              onChange={(e) => setCurrentWorkload(Number(e.target.value))}
              className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-indigo-600 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-600/30 hover:bg-indigo-500 transition-colors disabled:opacity-50"
          >
            {loading ? 'Analyzing PR Complexity & Availability...' : 'Predict Review Delay'}
          </button>
        </form>

        {/* Prediction Results or Error or Initial Prompt */}
        <div className="flex flex-col justify-between rounded-xl border border-slate-800 bg-slate-950/60 p-5">
          {error && (
            <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-300">
              <span className="font-bold">Error: </span> {error}
            </div>
          )}

          {!prediction && !error && (
            <div className="flex h-full flex-col items-center justify-center text-center p-6">
              <span className="text-4xl mb-3">📊</span>
              <h3 className="text-sm font-bold text-slate-200">No Active Prediction</h3>
              <p className="mt-1 text-xs text-slate-400 max-w-xs">
                Submit PR details to calculate predicted review turnaround time and stagnation risk.
              </p>
            </div>
          )}

          {prediction && (
            <>
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
                    Predicted Review Delay
                  </span>
                  <span
                    className={`rounded-md border px-2.5 py-0.5 text-xs font-bold ${getRiskBadgeColor(
                      prediction.risk_level
                    )}`}
                  >
                    {prediction.risk_level} RISK
                  </span>
                </div>

                <div className="mt-3 flex items-baseline gap-2">
                  <span className="text-4xl font-extrabold text-white">
                    {prediction.predicted_delay_hours}h
                  </span>
                  <span className="text-sm font-medium text-slate-400">
                    (±{prediction.confidence_interval_hours}h confidence margin)
                  </span>
                </div>

                <p className="mt-1 text-xs text-slate-400">
                  Range: {prediction.min_predicted_delay_hours}h – {prediction.max_predicted_delay_hours}h
                </p>

                <div className="mt-4 rounded-lg border border-slate-800 bg-slate-900/90 p-3 text-xs text-slate-300">
                  <span className="font-semibold text-indigo-400">Actionable Insight: </span>
                  {prediction.recommendation}
                </div>
              </div>

              <div className="mt-4 pt-4 border-t border-slate-800 grid grid-cols-2 gap-4 text-center">
                <div className="rounded-lg bg-slate-900/60 p-2">
                  <span className="text-[10px] text-slate-400 uppercase tracking-wider">Complexity Score</span>
                  <p className="text-sm font-bold text-slate-200">
                    {additions + deletions > 500 ? 'High' : 'Moderate'} ({additions + deletions} lines)
                  </p>
                </div>
                <div className="rounded-lg bg-slate-900/60 p-2">
                  <span className="text-[10px] text-slate-400 uppercase tracking-wider">Workload Level</span>
                  <p className="text-sm font-bold text-slate-200">{currentWorkload} PRs assigned</p>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
