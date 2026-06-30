import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '../lib/api';
import { 
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Legend,
  PieChart, Pie, Cell,
  LineChart, Line
} from 'recharts';
import { Activity, Users, BookOpen, Code, AlertTriangle } from 'lucide-react';

interface AnalyticsData {
  registrations: { date: string; count: number }[];
  progress_stats: { date: string; enrolled: number; completed: number }[];
  quiz_stats: { is_correct: boolean; count: number }[];
  challenge_stats: { status: string; count: number }[];
}

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042'];

export default function AnalyticsDashboardPage() {
  const { data, isLoading, isError } = useQuery<AnalyticsData>({
    queryKey: ['moderator_analytics'],
    queryFn: () => fetchApi('/dashboard/analytics/'),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-xl font-bold animate-pulse flex items-center gap-2">
          <Activity className="animate-spin" /> Loading Analytics Data...
        </div>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-red-500">
        <AlertTriangle size={48} className="mb-4" />
        <h2 className="text-2xl font-black">Error loading analytics</h2>
        <p className="font-bold">Please check your permissions or try again later.</p>
      </div>
    );
  }

  // Format quiz data for Pie Chart
  const quizData = data.quiz_stats.map(item => ({
    name: item.is_correct ? 'Correct' : 'Incorrect',
    value: item.count
  }));

  return (
    <div className="max-w-7xl mx-auto space-y-8 pb-12">
      <div className="flex items-center gap-4">
        <div className="bg-primary text-white p-3 rounded-xl border-4 border-black">
          <Activity size={32} />
        </div>
        <div>
          <h1 className="text-4xl font-black tracking-tight">Platform Analytics</h1>
          <p className="text-muted font-bold">Real-time insights for moderators (Last 30 Days)</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        
        {/* Registration Trends */}
        <div className="bg-white p-6 rounded-2xl border-4 border-black shadow-card dark:bg-[#151411] dark:border-[#2e2924] dark:shadow-none">
          <h2 className="text-2xl font-black mb-6 flex items-center gap-2">
            <Users className="text-accent" /> New Registrations
          </h2>
          <div className="h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.registrations} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorUsers" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#4f46e5" stopOpacity={0.8}/>
                    <stop offset="95%" stopColor="#4f46e5" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" stroke="#888888" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#888888" fontSize={12} tickLine={false} axisLine={false} />
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e0e0e0" />
                <Tooltip contentStyle={{ borderRadius: '8px', border: '2px solid black', fontWeight: 'bold' }} />
                <Area type="monotone" dataKey="count" stroke="#4f46e5" fillOpacity={1} fill="url(#colorUsers)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Course Progress */}
        <div className="bg-white p-6 rounded-2xl border-4 border-black shadow-card dark:bg-[#151411] dark:border-[#2e2924] dark:shadow-none">
          <h2 className="text-2xl font-black mb-6 flex items-center gap-2">
            <BookOpen className="text-primary" /> Course Engagement
          </h2>
          <div className="h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.progress_stats} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e0e0e0" />
                <XAxis dataKey="date" stroke="#888888" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#888888" fontSize={12} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ borderRadius: '8px', border: '2px solid black', fontWeight: 'bold' }} />
                <Legend iconType="circle" wrapperStyle={{ fontWeight: 'bold' }} />
                <Bar dataKey="enrolled" name="Enrolled" fill="#FFBB28" radius={[4, 4, 0, 0]} />
                <Bar dataKey="completed" name="Completed" fill="#00C49F" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Quiz Performance */}
        <div className="bg-white p-6 rounded-2xl border-4 border-black shadow-card dark:bg-[#151411] dark:border-[#2e2924] dark:shadow-none">
          <h2 className="text-2xl font-black mb-6 flex items-center gap-2">
            <Code className="text-purple-500" /> Quiz Accuracy
          </h2>
          <div className="h-80 w-full flex items-center justify-center">
            {quizData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={quizData}
                    cx="50%"
                    cy="50%"
                    innerRadius={80}
                    outerRadius={120}
                    paddingAngle={5}
                    dataKey="value"
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                    labelLine={false}
                  >
                    {quizData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} stroke="black" strokeWidth={2} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ borderRadius: '8px', border: '2px solid black', fontWeight: 'bold' }} />
                  <Legend iconType="circle" wrapperStyle={{ fontWeight: 'bold' }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <p className="font-bold text-muted">No quiz data available.</p>
            )}
          </div>
        </div>

        {/* Coding Challenges */}
        <div className="bg-white p-6 rounded-2xl border-4 border-black shadow-card dark:bg-[#151411] dark:border-[#2e2924] dark:shadow-none">
          <h2 className="text-2xl font-black mb-6 flex items-center gap-2">
            <Code className="text-pink-500" /> Challenge Submissions Status
          </h2>
          <div className="h-80 w-full flex items-center justify-center">
            {data.challenge_stats.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={data.challenge_stats}
                    cx="50%"
                    cy="50%"
                    outerRadius={120}
                    dataKey="count"
                    nameKey="status"
                    label={({ status, percent }) => `${status} ${(percent * 100).toFixed(0)}%`}
                  >
                    {data.challenge_stats.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[(index + 2) % COLORS.length]} stroke="black" strokeWidth={2} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ borderRadius: '8px', border: '2px solid black', fontWeight: 'bold' }} />
                  <Legend iconType="circle" wrapperStyle={{ fontWeight: 'bold', textTransform: 'capitalize' }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <p className="font-bold text-muted">No challenge data available.</p>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
