'use client';

import { useEffect, useState } from 'react';
import { DashboardLayout } from '@/components/dashboard-layout';
import { MetricCard } from '@/components/metric-card';
import { ChartCard } from '@/components/chart-card';
import { DataTable } from '@/components/data-table';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, BarChart, Bar, Cell } from 'recharts';
import api from '@/lib/api';

const severityColors: { [key: string]: string } = {
  Critical: '#ef4444',
  High: '#f59e0b',
  Medium: '#3b82f6',
  Low: '#10b981',
};

export default function BugsPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchBugs = async () => {
      try {
        const response = await api.get('/dashboard/bugs');
        setData(response.data);
      } catch (error) {
        console.error('Failed to fetch dashboard bugs:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchBugs();
  }, []);

  if (loading || !data) {
    return (
      <DashboardLayout>
        <div className="flex h-full min-h-[60vh] items-center justify-center">
          <p className="text-muted-foreground animate-pulse font-medium">Loading bugs...</p>
        </div>
      </DashboardLayout>
    );
  }

  const { kpis, bugs_by_severity, bug_resolution_trend, open_bugs } = data;

  const severityDataWithColors = bugs_by_severity.map((item: any) => ({
    ...item,
    fill: severityColors[item.severity] || '#6b7280'
  }));

  return (
    <DashboardLayout>
      <div className="space-y-8">
        {/* Executive Metrics */}
        <div>
          <p className="text-xs uppercase tracking-widest font-semibold text-muted-foreground mb-6">Issue Management Dashboard</p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <MetricCard label="Total Bugs Reported" value={kpis.total_bugs} />
            <MetricCard label="Open Issues" value={kpis.open_issues} />
            <MetricCard label="Resolved This Month" value={kpis.resolved_this_month} />
            <MetricCard label="Avg Resolution Time" value={kpis.avg_resolution_time || 'N/A'} />
          </div>
        </div>

        {/* Analysis Section */}
        <div>
          <p className="text-xs uppercase tracking-widest font-semibold text-muted-foreground mb-6">Bug Lifecycle Analysis</p>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <ChartCard title="Bug Resolution Trend">
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={bug_resolution_trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2d3748" />
                <XAxis dataKey="week" stroke="#9ca3af" />
                <YAxis stroke="#9ca3af" />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#1a1f2e', border: '1px solid #2d3748' }}
                  labelStyle={{ color: '#e4e7eb' }}
                />
                <Legend />
                <Line type="monotone" dataKey="open" stroke="#ef4444" strokeWidth={2} name="Open" />
                <Line type="monotone" dataKey="resolved" stroke="#10b981" strokeWidth={2} name="Resolved" />
                <Line type="monotone" dataKey="in_progress" stroke="#f59e0b" strokeWidth={2} name="In Progress" />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

            <ChartCard title="Bugs by Severity">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={severityDataWithColors}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2d3748" />
                <XAxis dataKey="severity" stroke="#9ca3af" />
                <YAxis stroke="#9ca3af" />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#1a1f2e', border: '1px solid #2d3748' }}
                  labelStyle={{ color: '#e4e7eb' }}
                />
                <Bar dataKey="count" radius={[8, 8, 0, 0]}>
                  {severityDataWithColors.map((entry: any, index: number) => (
                    <Cell key={`cell-${index}`} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            </ChartCard>
          </div>
        </div>

        {/* Detailed Analysis */}
        <div>
          <p className="text-xs uppercase tracking-widest font-semibold text-muted-foreground mb-6">Issue Inventory</p>
          <ChartCard title="Open & In Progress Issues">
          <DataTable
            columns={[
              { key: 'id', label: 'ID' },
              { key: 'title', label: 'Title' },
              { key: 'severity', label: 'Severity' },
              { key: 'status', label: 'Status' },
              { key: 'reports', label: 'Reports' },
              { key: 'arr_at_risk', label: 'ARR at Risk' },
              { key: 'raw_text', label: 'Raw Text' },
            ]}
            data={open_bugs}
          />
          </ChartCard>
        </div>
      </div>
    </DashboardLayout>
  );
}
