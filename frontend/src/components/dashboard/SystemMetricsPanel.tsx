import React, { useEffect, useRef } from 'react';
import type { SystemMetricsData } from '../../api/types';

interface SystemMetricsPanelProps {
  data: SystemMetricsData | null;
  isLoading: boolean;
  onRefresh?: () => void;
}

const formatUptime = (seconds: number): string => {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
};

const getResponseTimeColor = (ms: number): string => {
  if (ms < 500) return 'text-green-600';
  if (ms <= 2000) return 'text-yellow-600';
  return 'text-red-600';
};

const getResponseTimeBg = (ms: number): string => {
  if (ms < 500) return 'bg-green-50';
  if (ms <= 2000) return 'bg-yellow-50';
  return 'bg-red-50';
};

const getErrorRateColor = (rate: number): string => {
  if (rate < 0.01) return 'text-green-600';
  if (rate <= 0.05) return 'text-yellow-600';
  return 'text-red-600';
};

const getErrorRateBg = (rate: number): string => {
  if (rate < 0.01) return 'bg-green-50';
  if (rate <= 0.05) return 'bg-yellow-50';
  return 'bg-red-50';
};

export const SystemMetricsPanel: React.FC<SystemMetricsPanelProps> = ({
  data,
  isLoading,
  onRefresh,
}) => {
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!onRefresh) return;

    intervalRef.current = setInterval(() => {
      onRefresh();
    }, 60_000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [onRefresh]);

  if (isLoading && !data) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <div className="h-5 w-40 bg-gray-200 rounded animate-pulse mb-4" />
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-16 bg-gray-100 rounded animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">System Metrics</h3>
        <div className="flex items-center justify-center h-[100px] text-gray-400">
          No data available
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">System Metrics</h3>
        {isLoading && (
          <svg
            className="animate-spin h-4 w-4 text-gray-400"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {/* Avg Response Time */}
        <div className={`${getResponseTimeBg(data.avg_response_time_ms)} rounded-lg p-3`}>
          <p className="text-xs font-medium text-gray-600">Avg Response</p>
          <p className={`text-xl font-bold ${getResponseTimeColor(data.avg_response_time_ms)}`}>
            {data.avg_response_time_ms}ms
          </p>
        </div>

        {/* Queries (24h) */}
        <div className="bg-blue-50 rounded-lg p-3">
          <p className="text-xs font-medium text-blue-600">Queries (24h)</p>
          <p className="text-xl font-bold text-gray-900">{data.total_queries_24h.toLocaleString()}</p>
        </div>

        {/* Queries (7d) */}
        <div className="bg-indigo-50 rounded-lg p-3">
          <p className="text-xs font-medium text-indigo-600">Queries (7d)</p>
          <p className="text-xl font-bold text-gray-900">{data.total_queries_7d.toLocaleString()}</p>
        </div>

        {/* Error Rate */}
        <div className={`${getErrorRateBg(data.error_rate_24h)} rounded-lg p-3`}>
          <p className="text-xs font-medium text-gray-600">Error Rate</p>
          <p className={`text-xl font-bold ${getErrorRateColor(data.error_rate_24h)}`}>
            {(data.error_rate_24h * 100).toFixed(1)}%
          </p>
        </div>

        {/* Uptime */}
        <div className="bg-gray-50 rounded-lg p-3">
          <p className="text-xs font-medium text-gray-600">Uptime</p>
          <p className="text-xl font-bold text-gray-900">{formatUptime(data.uptime_seconds)}</p>
        </div>
      </div>
    </div>
  );
};
