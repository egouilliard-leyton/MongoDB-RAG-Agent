import React, { useEffect, useState } from 'react';
import { useDashboard } from '../contexts/DashboardContext';
import {
  RegionDistributionChart,
  IndustryDistributionChart,
  TrendsChart,
  QualityMetricsChart,
} from '../components/DashboardCharts';

/**
 * Dashboard page component displaying key analytics and metrics.
 * Shows summary cards with project count, session count, and success rates,
 * plus distribution charts for regions, industries, trends, and quality metrics.
 */
export const Dashboard: React.FC = () => {
  const {
    summary,
    regionDistribution,
    industryDistribution,
    trends,
    qualityMetrics,
    isLoading,
    error,
    loadAllData,
  } = useDashboard();

  // Granularity selection for trends chart
  const [trendDays, setTrendDays] = useState<number>(30);
  const [trendGranularity, setTrendGranularity] = useState<'day' | 'week' | 'month'>('day');

  useEffect(() => {
    loadAllData().catch(console.error);
  }, [loadAllData]);

  if (isLoading && !summary) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <div className="flex items-center justify-center py-12">
          <div className="flex items-center space-x-3 text-gray-500">
            <svg
              className="animate-spin h-5 w-5"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            <span>Loading dashboard...</span>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-start">
            <svg
              className="h-5 w-5 text-red-500 mt-0.5"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                clipRule="evenodd"
              />
            </svg>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">
                Failed to load dashboard
              </h3>
              <p className="text-sm text-red-700 mt-1">{error}</p>
              <button
                onClick={() => loadAllData().catch(console.error)}
                className="mt-2 text-sm font-medium text-red-600 hover:text-red-500"
              >
                Try again
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <button
          onClick={() => loadAllData().catch(console.error)}
          disabled={isLoading}
          className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-gray-600 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isLoading ? (
            <svg
              className="animate-spin h-4 w-4 mr-1.5"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
          ) : (
            <svg
              className="h-4 w-4 mr-1.5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
          )}
          Refresh
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <SummaryCard
          title="Total Projects"
          value={summary?.project_count ?? 0}
          icon={
            <svg
              className="h-6 w-6 text-blue-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
              />
            </svg>
          }
          bgColor="bg-blue-50"
        />
        <SummaryCard
          title="Total Sessions"
          value={summary?.session_count ?? 0}
          icon={
            <svg
              className="h-6 w-6 text-green-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
              />
            </svg>
          }
          bgColor="bg-green-50"
        />
        <SummaryCard
          title="Total Q&A Pairs"
          value={summary?.qa_pair_count ?? 0}
          icon={
            <svg
              className="h-6 w-6 text-purple-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
          }
          bgColor="bg-purple-50"
        />
        <SummaryCard
          title="Success Rate"
          value={`${((summary?.success_rate ?? 0) * 100).toFixed(1)}%`}
          icon={
            <svg
              className="h-6 w-6 text-amber-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z"
              />
            </svg>
          }
          bgColor="bg-amber-50"
        />
      </div>

      {/* Trends Chart with Controls */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Activity Trends</h3>
          <div className="flex items-center space-x-3 mt-2 sm:mt-0">
            <select
              value={trendDays}
              onChange={(e) => setTrendDays(Number(e.target.value))}
              className="text-sm border-gray-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500"
            >
              <option value={7}>Last 7 days</option>
              <option value={14}>Last 14 days</option>
              <option value={30}>Last 30 days</option>
              <option value={60}>Last 60 days</option>
              <option value={90}>Last 90 days</option>
            </select>
            <select
              value={trendGranularity}
              onChange={(e) => setTrendGranularity(e.target.value as 'day' | 'week' | 'month')}
              className="text-sm border-gray-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500"
            >
              <option value="day">Daily</option>
              <option value="week">Weekly</option>
              <option value="month">Monthly</option>
            </select>
          </div>
        </div>
        <div className="h-[300px]">
          <TrendsChart data={trends} isLoading={isLoading} />
        </div>
      </div>

      {/* Distribution Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Region Distribution */}
        <RegionDistributionChart data={regionDistribution} isLoading={isLoading} />

        {/* Industry Distribution */}
        <IndustryDistributionChart data={industryDistribution} isLoading={isLoading} />
      </div>

      {/* Quality Metrics Chart */}
      <QualityMetricsChart data={qualityMetrics} isLoading={isLoading} variant="pie" />

      {/* Q&A Quality Section (detailed metrics) */}
      {summary?.qa_quality && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Q&A Quality Details</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <QualityMetric
              label="Rated"
              value={summary.qa_quality.rated}
              total={summary.qa_quality.total}
              color="blue"
            />
            <QualityMetric
              label="Good Ratings"
              value={summary.qa_quality.good}
              total={summary.qa_quality.rated}
              color="green"
            />
            <QualityMetric
              label="Exemplars"
              value={summary.qa_quality.exemplar_count}
              total={summary.qa_quality.total}
              color="purple"
            />
          </div>

          {/* Rating Breakdown */}
          <div className="mt-6 pt-6 border-t border-gray-200">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-600">Good/Bad Ratio</span>
              <span className="font-medium">
                {summary.qa_quality.good} / {summary.qa_quality.bad}
                {summary.qa_quality.rated > 0 && (
                  <span className="text-gray-500 ml-2">
                    ({((summary.qa_quality.good_ratio ?? 0) * 100).toFixed(1)}% good)
                  </span>
                )}
              </span>
            </div>
            {summary.qa_quality.rated > 0 && (
              <div className="mt-2 h-2 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-green-500 transition-all duration-300"
                  style={{ width: `${(summary.qa_quality.good_ratio ?? 0) * 100}%` }}
                />
              </div>
            )}
          </div>
        </div>
      )}

      {/* Last Updated */}
      {summary?.timestamp && (
        <p className="text-xs text-gray-500 text-right">
          Last updated: {new Date(summary.timestamp).toLocaleString()}
        </p>
      )}
    </div>
  );
};

// =============================================================================
// Sub-components
// =============================================================================

interface SummaryCardProps {
  title: string;
  value: number | string;
  icon: React.ReactNode;
  bgColor: string;
}

/**
 * Summary card displaying a single metric.
 */
const SummaryCard: React.FC<SummaryCardProps> = ({ title, value, icon, bgColor }) => {
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-5">
      <div className="flex items-center">
        <div className={`${bgColor} rounded-lg p-3`}>{icon}</div>
        <div className="ml-4">
          <p className="text-sm font-medium text-gray-600">{title}</p>
          <p className="text-2xl font-bold text-gray-900">
            {typeof value === 'number' ? value.toLocaleString() : value}
          </p>
        </div>
      </div>
    </div>
  );
};

interface QualityMetricProps {
  label: string;
  value: number;
  total: number;
  color: 'blue' | 'green' | 'purple';
}

/**
 * Quality metric display with progress indicator.
 */
const QualityMetric: React.FC<QualityMetricProps> = ({ label, value, total, color }) => {
  const percentage = total > 0 ? (value / total) * 100 : 0;

  const colorClasses = {
    blue: 'text-blue-600 bg-blue-500',
    green: 'text-green-600 bg-green-500',
    purple: 'text-purple-600 bg-purple-500',
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm text-gray-600">{label}</span>
        <span className={`text-sm font-semibold ${colorClasses[color].split(' ')[0]}`}>
          {value.toLocaleString()}
        </span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full ${colorClasses[color].split(' ')[1]} transition-all duration-300`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <p className="text-xs text-gray-500 mt-1">
        {percentage.toFixed(1)}% of {total.toLocaleString()}
      </p>
    </div>
  );
};
