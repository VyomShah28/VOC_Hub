'use client';

import { useEffect, useState } from 'react';
import { DashboardLayout } from '@/components/dashboard-layout';
import { MetricCard } from '@/components/metric-card';
import { ChartCard } from '@/components/chart-card';
import { DataTable } from '@/components/data-table';
import { LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import api from '@/lib/api';

export default function OverviewPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchOverview = async () => {
      try {
        const response = await api.get('/dashboard/overview');
        setData(response.data);
      } catch (error) {
        console.error('Failed to fetch dashboard overview:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchOverview();
  }, []);

  if (loading || !data) {
    return (
      <DashboardLayout>
        <div className="flex h-full min-h-[60vh] items-center justify-center">
          <p className="text-muted-foreground animate-pulse font-medium">Loading dashboard...</p>
        </div>
      </DashboardLayout>
    );
  }

  const { kpis, monthly_trend, sentiment_distribution, categorical_breakdown } = data;

  const sentimentData = [
    { name: 'Positive', value: sentiment_distribution.positive, fill: '#10b981' },
    { name: 'Neutral', value: sentiment_distribution.neutral, fill: '#6b7280' },
    { name: 'Negative', value: sentiment_distribution.negative, fill: '#ef4444' },
  ];

  return (
    <DashboardLayout>
      <div className="space-y-8">
        {/* Executive Summary Section */}
        <div>
          <p className="text-xs uppercase tracking-widest font-semibold text-muted-foreground mb-6">Key Performance Indicators</p>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-6">
            <MetricCard label="Total Feedback" value={kpis.total_feedback} />
            <MetricCard label="Active Issues" value={kpis.active_issues} />
            <MetricCard label="Feature Requests" value={kpis.feature_requests} />
            <MetricCard label="Pain Points" value={kpis.pain_points} />
            <MetricCard label="Others" value={kpis.others} />
          </div>
        </div>

        {/* Analytics Section */}
        <div>
          <p className="text-xs uppercase tracking-widest font-semibold text-muted-foreground mb-6">Trend Analysis</p>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <ChartCard title="Feedback Trend" className="lg:col-span-2">
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={monthly_trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2d3748" />
                <XAxis dataKey="month" stroke="#9ca3af" />
                <YAxis stroke="#9ca3af" />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#1a1f2e', border: '1px solid #2d3748' }}
                  labelStyle={{ color: '#e4e7eb' }}
                />
                <Legend />
                <Line type="monotone" dataKey="feedback" stroke="#3b82f6" strokeWidth={2} />
                <Line type="monotone" dataKey="sentiment" stroke="#10b981" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Sentiment Distribution">
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={sentimentData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={2}
                  dataKey="value"
                >
                  {sentimentData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={{ backgroundColor: '#1a1f2e', border: '1px solid #2d3748' }}
                  labelStyle={{ color: '#e4e7eb' }}
                />
              </PieChart>
            </ResponsiveContainer>
          </ChartCard>
          </div>
        </div>

        {/* Detailed Analysis Section */}
        <div>
          <p className="text-xs uppercase tracking-widest font-semibold text-muted-foreground mb-6">Categorical Breakdown</p>
          <ChartCard title="Feedback by Category">
          <DataTable
            columns={[
              { key: 'category', label: 'Category' },
              { key: 'sentiment', label: 'Sentiment' },
              { key: 'count', label: 'Count' },
            ]}
            data={categorical_breakdown}
          />
          </ChartCard>
        </div>
      </div>
    </DashboardLayout>
  );
}
