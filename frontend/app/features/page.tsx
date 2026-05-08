'use client';

import { useEffect, useState } from 'react';
import { DashboardLayout } from '@/components/dashboard-layout';
import { MetricCard } from '@/components/metric-card';
import { ChartCard } from '@/components/chart-card';
import { DataTable } from '@/components/data-table';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import api from '@/lib/api';

export default function FeaturesPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchFeatures = async () => {
      try {
        const response = await api.get('/dashboard/features');
        setData(response.data);
      } catch (error) {
        console.error('Failed to fetch dashboard features:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchFeatures();
  }, []);

  if (loading || !data) {
    return (
      <DashboardLayout>
        <div className="flex h-full min-h-[60vh] items-center justify-center">
          <p className="text-muted-foreground animate-pulse font-medium">Loading features...</p>
        </div>
      </DashboardLayout>
    );
  }

  const { kpis, feature_trend, top_feature_requests } = data;

  return (
    <DashboardLayout>
      <div className="space-y-8">
        {/* Executive Metrics */}
        <div>
          <p className="text-xs uppercase tracking-widest font-semibold text-muted-foreground mb-6">Feature Request Pipeline</p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <MetricCard label="Feature Requests" value={kpis.feature_requests} />
            <MetricCard label="High Priority" value={kpis.high_priority} />
            <MetricCard label="In Development" value={kpis.in_development} />
            <MetricCard label="Community Votes" value={kpis.community_votes} />
          </div>
        </div>

        {/* Trend Analysis */}
        <div>
          <p className="text-xs uppercase tracking-widest font-semibold text-muted-foreground mb-6">Growth Metrics</p>
          <ChartCard title="Feature Request Trend">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={feature_trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2d3748" />
                <XAxis dataKey="month" stroke="#9ca3af" />
                <YAxis stroke="#9ca3af" />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1a1f2e', border: '1px solid #2d3748' }}
                  labelStyle={{ color: '#e4e7eb' }}
                />
                <Legend />
                <Bar dataKey="requests" fill="#3b82f6" />
                <Bar dataKey="priority" fill="#f59e0b" />
                <Bar dataKey="planned" fill="#10b981" />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>

          {/* Feature Requests Table */}
          <div className="mt-8">
            <ChartCard title="Top Feature Requests">
              <DataTable
                columns={[
                  { key: 'feature', label: 'Feature' },
                  { key: 'category', label: 'Category' },
                  { key: 'priority', label: 'Priority' },
                  { key: 'status', label: 'Status' },
                  { key: 'votes', label: 'Votes' },
                  { key: 'arr_demand', label: 'ARR Demand' },
                  { key: 'raw_text', label: 'Raw Text' },
                ]}
                data={top_feature_requests}
              />
            </ChartCard>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
