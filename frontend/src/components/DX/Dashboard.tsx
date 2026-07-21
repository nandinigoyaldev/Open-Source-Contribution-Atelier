/**
 * DX Dashboard component.
 * 
 * @file Dashboard.tsx
 * @location frontend/src/components/DX/Dashboard.tsx
 */

import React, { useState, useEffect } from 'react';
import { useDXData } from '../../hooks/useDXData';
import { DXScoreCard } from './DXScoreCard';
import { DXTimeline } from './DXTimeline';
import { DXRecommendations } from './DXRecommendations';
import { DXMetrics } from './DXMetrics';

export const DXDashboard: React.FC = () => {
  const { data, loading, error } = useDXData();
  const [timeRange, setTimeRange] = useState('week');

  if (loading) {
    return <div className="text-center py-12">Loading DX data...</div>;
  }

  if (error) {
    return <div className="text-red-400 text-center py-12">Error: {error.message}</div>;
  }

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-3xl font-bold text-white">⚡ Developer Experience Dashboard</h1>
      
      {/* Score Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <DXScoreCard
          title="DX Score"
          value={data?.currentScore || 0}
          trend={data?.trend || 0}
          maxValue={100}
        />
        <DXScoreCard
          title="Setup Time"
          value={data?.avgSetupTime || 0}
          unit="min"
          trend={data?.setupTrend || 0}
        />
        <DXScoreCard
          title="Build Success Rate"
          value={data?.buildSuccessRate || 0}
          unit="%"
          trend={data?.buildTrend || 0}
        />
        <DXScoreCard
          title="Test Pass Rate"
          value={data?.testPassRate || 0}
          unit="%"
          trend={data?.testTrend || 0}
        />
      </div>

      {/* Timeline */}
      <div className="bg-dark-800 p-6 rounded-xl border border-dark-700">
        <h2 className="text-xl font-semibold text-white mb-4">DX Trend</h2>
        <DXTimeline data={data?.timeline || []} />
      </div>

      {/* Recommendations */}
      <div className="bg-dark-800 p-6 rounded-xl border border-dark-700">
        <h2 className="text-xl font-semibold text-white mb-4">💡 Recommendations</h2>
        <DXRecommendations recommendations={data?.recommendations || []} />
      </div>

      {/* Detailed Metrics */}
      <div className="bg-dark-800 p-6 rounded-xl border border-dark-700">
        <h2 className="text-xl font-semibold text-white mb-4">📊 Detailed Metrics</h2>
        <DXMetrics metrics={data?.metrics || {}} />
      </div>
    </div>
  );
};