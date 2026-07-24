import React, { useState, useEffect } from 'react';
import { fetchApi } from '../lib/api';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export function AdminDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchApi('/admin/productivity/')
      .then(setData)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div>Loading...</div>;

  return (
    <div className="admin-dashboard">
      <h1>📊 Developer Productivity Dashboard</h1>
      
      <div className="stats-grid">
        <div className="stat-card">
          <span>👥 Active Today</span>
          <span className="value">{data.total_active}</span>
        </div>
        <div className="stat-card">
          <span>🚫 Stalled PRs</span>
          <span className="value">{data.stalled_prs?.length || 0}</span>
        </div>
        <div className="stat-card">
          <span>⏳ Review Bottlenecks</span>
          <span className="value">{data.review_bottlenecks?.length || 0}</span>
        </div>
      </div>

      <div className="chart-section">
        <h3>📈 Daily Activity</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data.daily_trend}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey="opened" stroke="#4CAF50" name="PRs Opened" />
            <Line type="monotone" dataKey="closed" stroke="#f44336" name="PRs Closed" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="table-section">
        <h3>🏆 Contributor Leaderboard</h3>
        <table className="leaderboard">
          <thead>
            <tr>
              <th>#</th>
              <th>Contributor</th>
              <th>PRs Opened</th>
              <th>PRs Closed</th>
              <th>Merge Rate</th>
              <th>Avg Review Time</th>
            </tr>
          </thead>
          <tbody>
            {data.metrics?.map((m, i) => (
              <tr key={i}>
                <td>{i + 1}</td>
                <td>{m.username}</td>
                <td>{m.prs_opened}</td>
                <td>{m.prs_closed}</td>
                <td>{m.pr_merge_rate}%</td>
                <td>{m.avg_review_time.toFixed(1)}h</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}