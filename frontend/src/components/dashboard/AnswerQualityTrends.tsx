import React, { useMemo } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import type { QualityTrendResponse } from '../../api/types';

interface AnswerQualityTrendsProps {
  data: QualityTrendResponse | null;
  isLoading: boolean;
  onParamsChange: (days: number, granularity: 'day' | 'week' | 'month') => void;
}

const PERIOD_OPTIONS = [
  { label: '7d', days: 7 },
  { label: '14d', days: 14 },
  { label: '30d', days: 30 },
  { label: '90d', days: 90 },
] as const;

const GRANULARITY_OPTIONS = [
  { label: 'Daily', value: 'day' },
  { label: 'Weekly', value: 'week' },
] as const;

const formatDate = (dateStr: string) => {
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
};

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-gray-200 rounded-lg px-3 py-2 shadow-sm text-xs">
      <p className="font-medium text-gray-900 mb-1">{formatDate(label)}</p>
      {payload.map((entry: any) => (
        <p key={entry.dataKey} style={{ color: entry.color }}>
          {entry.name}: {entry.value}
        </p>
      ))}
    </div>
  );
};

export const AnswerQualityTrends: React.FC<AnswerQualityTrendsProps> = ({
  data,
  isLoading,
  onParamsChange,
}) => {
  const activeDays = data?.period_days ?? 30;
  const activeGranularity = data?.granularity ?? 'day';

  const summaryPct = useMemo(() => {
    if (!data?.trend.length) return null;
    const totalGood = data.trend.reduce((sum, p) => sum + p.good_count, 0);
    const totalRated = data.trend.reduce((sum, p) => sum + p.total_rated, 0);
    if (totalRated === 0) return null;
    return ((totalGood / totalRated) * 100).toFixed(1);
  }, [data]);

  const isEmpty = !data || data.trend.length === 0;

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Answer Quality Trends</h3>
          {summaryPct !== null && (
            <p className="text-sm text-gray-500">{summaryPct}% good answers over this period</p>
          )}
        </div>
        <div className="flex items-center space-x-2 mt-2 sm:mt-0">
          {/* Period selector */}
          <div className="flex rounded-md shadow-sm">
            {PERIOD_OPTIONS.map(({ label, days }) => (
              <button
                key={days}
                onClick={() => onParamsChange(days, activeGranularity)}
                className={`px-2.5 py-1 text-xs font-medium border first:rounded-l-md last:rounded-r-md -ml-px first:ml-0 ${
                  activeDays === days
                    ? 'bg-blue-50 text-blue-700 border-blue-300 z-10'
                    : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          {/* Granularity toggle */}
          <div className="flex rounded-md shadow-sm">
            {GRANULARITY_OPTIONS.map(({ label, value }) => (
              <button
                key={value}
                onClick={() => onParamsChange(activeDays, value as 'day' | 'week' | 'month')}
                className={`px-2.5 py-1 text-xs font-medium border first:rounded-l-md last:rounded-r-md -ml-px first:ml-0 ${
                  activeGranularity === value
                    ? 'bg-blue-50 text-blue-700 border-blue-300 z-10'
                    : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {isLoading ? (
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
      ) : isEmpty ? (
        <div className="flex items-center justify-center h-[250px] text-gray-400">
          No rated answers in this period
        </div>
      ) : (
        <div style={{ height: 250 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data!.trend} margin={{ left: 10, right: 20, top: 10, bottom: 5 }}>
              <defs>
                <linearGradient id="colorGood" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22C55E" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#22C55E" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorBad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#EF4444" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#EF4444" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11 }}
                tickFormatter={formatDate}
                interval="preserveStartEnd"
              />
              <YAxis tick={{ fontSize: 12 }} allowDecimals={false} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: '12px' }} />
              <Area
                type="monotone"
                dataKey="good_count"
                name="Good"
                stroke="#22C55E"
                fill="url(#colorGood)"
                strokeWidth={2}
              />
              <Area
                type="monotone"
                dataKey="bad_count"
                name="Bad"
                stroke="#EF4444"
                fill="url(#colorBad)"
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
};
