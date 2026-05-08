'use client';

import { useEffect, useState } from 'react';
import { DashboardLayout } from '@/components/dashboard-layout';
import { MetricCard } from '@/components/metric-card';
import { ChartCard } from '@/components/chart-card';
import { DataTable } from '@/components/data-table';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import api from '@/lib/api';

const COLORS = ['#ef4444', '#f59e0b', '#3b82f6', '#8b5cf6', '#10b981', '#6b7280', '#ec4899', '#14b8a6', '#f43f5e', '#84cc16'];

export default function PainPointsPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchPainPoints = async () => {
      try {
        const response = await api.get('/dashboard/pain-points');
        setData(response.data);
      } catch (error) {
        console.error('Failed to fetch dashboard pain points:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchPainPoints();
  }, []);

  if (loading || !data) {
    return (
      <DashboardLayout>
        <div className="flex h-full min-h-[60vh] items-center justify-center">
          <p className="text-muted-foreground animate-pulse font-medium">Loading pain points...</p>
        </div>
      </DashboardLayout>
    );
  }

  const { kpis, pain_by_category, pain_trend, top_pain_points } = data;

  // Assign colors to the category data
  const chartDataWithColors = pain_by_category.map((item: any, index: number) => ({
    ...item,
    fill: COLORS[index % COLORS.length]
  }));

  // Extract unique theme keys for the trend chart
  const trendKeys = new Set<string>();
  if (pain_trend && pain_trend.length > 0) {
    pain_trend.forEach((item: any) => {
      Object.keys(item).forEach(key => {
        if (key !== 'week') {
          trendKeys.add(key);
        }
      });
    });
  }
  const trendBars = Array.from(trendKeys);

  return (
    <DashboardLayout>
      <div className="space-y-8">
        {/* Executive Metrics */}
        <div>
          <p className="text-xs uppercase tracking-widest font-semibold text-muted-foreground mb-6">Customer Pain Point Analysis</p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <MetricCard label="Total Pain Points" value={kpis.total_pain_points} />
            <MetricCard label="Critical Issues" value={kpis.critical_issues} />
            <MetricCard label="Avg Resolution Time" value={kpis.avg_resolution_time || 'N/A'} />
            <MetricCard label="Customer Impact" value={`${kpis.customer_impact_pct}%`} />
          </div>
        </div>

        {/* Analysis Section */}
        <div>
          <p className="text-xs uppercase tracking-widest font-semibold text-muted-foreground mb-6">Distribution & Trends</p>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <ChartCard title="Pain Points by Category" className="lg:col-span-2">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chartDataWithColors}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2d3748" />
                <XAxis dataKey="category" stroke="#9ca3af" />
                <YAxis stroke="#9ca3af" />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#1a1f2e', border: '1px solid #2d3748' }}
                  labelStyle={{ color: '#e4e7eb' }}
                />
                <Bar dataKey="count" fill="#ef4444" radius={[8, 8, 0, 0]}>
                  {chartDataWithColors.map((entry: any, index: number) => (
                    <Cell key={`cell-${index}`} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Top Categories">
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={chartDataWithColors}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={90}
                  paddingAngle={2}
                  dataKey="count"
                >
                  {chartDataWithColors.map((entry: any, index: number) => (
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

        {/* Trend */}
        <ChartCard title="Pain Points Trend">
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={pain_trend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2d3748" />
              <XAxis dataKey="week" stroke="#9ca3af" />
              <YAxis stroke="#9ca3af" />
              <Tooltip 
                contentStyle={{ backgroundColor: '#1a1f2e', border: '1px solid #2d3748' }}
                labelStyle={{ color: '#e4e7eb' }}
              />
              <Legend />
              {trendBars.map((key, index) => (
                <Bar key={key} dataKey={key} fill={COLORS[index % COLORS.length]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
        </div>

        {/* Detailed Analysis */}
        <div>
          <p className="text-xs uppercase tracking-widest font-semibold text-muted-foreground mb-6">Issue Inventory</p>
          <ChartCard title="Top Pain Points Details">
          <DataTable
            columns={[
              { key: 'issue', label: 'Issue' },
              { key: 'category', label: 'Category' },
              { key: 'priority', label: 'Priority' },
              { key: 'mentions', label: 'Mentions' },
              { key: 'arr_at_risk', label: 'ARR at Risk' },
              { key: 'raw_text', label: 'Raw Text' },
            ]}
            data={top_pain_points}
          />
          </ChartCard>
        </div>
      </div>
    </DashboardLayout>
  );
}
