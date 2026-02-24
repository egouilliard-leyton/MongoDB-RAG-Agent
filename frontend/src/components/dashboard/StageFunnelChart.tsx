import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import type { StageFunnelResponse } from '../../api/types';

interface StageFunnelChartProps {
  data: StageFunnelResponse | null;
  isLoading: boolean;
}

const CustomTooltip = ({ active, payload }: any) => {
  if (!active || !payload?.[0]) return null;
  const item = payload[0].payload;
  return (
    <div className="bg-white border border-gray-200 rounded-lg px-3 py-2 shadow-sm text-xs">
      <p className="font-medium text-gray-900">{item.label}</p>
      <p className="text-gray-600">
        {item.count} projects ({item.percentage.toFixed(1)}%)
      </p>
    </div>
  );
};

export const StageFunnelChart: React.FC<StageFunnelChartProps> = ({ data, isLoading }) => {
  if (isLoading) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <div className="h-5 w-40 bg-gray-200 rounded animate-pulse mb-4" />
        <div className="flex items-center justify-center h-[250px] text-gray-400">
          <div className="flex items-center space-x-2">
            <svg
              className="animate-spin h-5 w-5"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            <span>Loading...</span>
          </div>
        </div>
      </div>
    );
  }

  const isEmpty = !data || data.funnel.length === 0;

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Pipeline Status</h3>
          {data && (
            <p className="text-sm text-gray-500">{data.total_projects} total projects</p>
          )}
        </div>
        {data && data.funnel.some((s) => s.count > 0 && s.stage_id !== 'complete') && (
          <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-amber-100 text-amber-800 border border-amber-300">
            Active
          </span>
        )}
      </div>

      {isEmpty ? (
        <div className="flex items-center justify-center h-[250px] text-gray-400">
          No projects in pipeline
        </div>
      ) : (
        <div style={{ height: Math.max(200, data!.funnel.length * 50) }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={data!.funnel}
              layout="vertical"
              margin={{ left: 10, right: 20, top: 5, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
              <XAxis type="number" tick={{ fontSize: 12 }} allowDecimals={false} />
              <YAxis
                type="category"
                dataKey="label"
                tick={{ fontSize: 12 }}
                width={90}
              />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="count" name="Projects" radius={[0, 4, 4, 0]}>
                {data!.funnel.map((item, index) => (
                  <Cell key={`cell-${index}`} fill={item.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
};
