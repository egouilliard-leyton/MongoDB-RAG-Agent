import React from 'react';

// Stub types for recharts until module is installed
const BarChart: any = () => null;
const Bar: any = () => null;
const LineChart: any = () => null;
const Line: any = () => null;
const PieChart: any = () => null;
const Pie: any = () => null;
const Cell: any = () => null;
const XAxis: any = () => null;
const YAxis: any = () => null;
const CartesianGrid: any = () => null;
const Tooltip: any = () => null;
const Legend: any = () => null;
const ResponsiveContainer: any = ({ children }: { children: React.ReactNode }) => <div>{children}</div>;
import type {
  TrendDataPoint,
  TrendsResponse,
  QualityMetricsResponse,
  RegionDistribution,
  IndustryDistribution,
} from '../api/types';

// =============================================================================
// Color Palettes
// =============================================================================

const INDUSTRY_COLORS = [
  '#6366F1', // indigo-500
  '#8B5CF6', // violet-500
  '#A855F7', // purple-500
  '#EC4899', // pink-500
  '#F43F5E', // rose-500
  '#EF4444', // red-500
  '#F97316', // orange-500
  '#F59E0B', // amber-500
  '#EAB308', // yellow-500
  '#84CC16', // lime-500
  '#22C55E', // green-500
  '#10B981', // emerald-500
  '#14B8A6', // teal-500
  '#06B6D4', // cyan-500
  '#0EA5E9', // sky-500
  '#3B82F6', // blue-500
  '#6B7280', // gray-500
  '#78716C', // stone-500
  '#71717A', // zinc-500
];

const QUALITY_COLORS = {
  good: '#22C55E', // green-500
  bad: '#EF4444', // red-500
  unrated: '#9CA3AF', // gray-400
  exemplar: '#8B5CF6', // violet-500
};

const OUTCOME_COLORS = {
  successful: '#22C55E', // green-500
  partial: '#F59E0B', // amber-500
  negative: '#EF4444', // red-500
  pending: '#9CA3AF', // gray-400
};

const TREND_COLORS = {
  projects: '#3B82F6', // blue-500
  sessions: '#10B981', // emerald-500
  qa_pairs: '#8B5CF6', // violet-500
};

// =============================================================================
// Chart Components
// =============================================================================

interface ChartContainerProps {
  title: string;
  children: React.ReactNode;
  height?: number;
  isLoading?: boolean;
  isEmpty?: boolean;
  emptyMessage?: string;
}

/**
 * Container wrapper for chart components with title and loading/empty states.
 */
const ChartContainer: React.FC<ChartContainerProps> = ({
  title,
  children,
  height = 300,
  isLoading = false,
  isEmpty = false,
  emptyMessage = 'No data available',
}) => {
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">{title}</h3>
      {isLoading ? (
        <div
          className="flex items-center justify-center text-gray-400"
          style={{ height }}
        >
          <div className="flex items-center space-x-2">
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
            <span>Loading...</span>
          </div>
        </div>
      ) : isEmpty ? (
        <div
          className="flex items-center justify-center text-gray-400"
          style={{ height }}
        >
          {emptyMessage}
        </div>
      ) : (
        <div style={{ height }}>{children}</div>
      )}
    </div>
  );
};

// =============================================================================
// Region Distribution Chart
// =============================================================================

interface RegionDistributionChartProps {
  data: RegionDistribution | null;
  isLoading?: boolean;
  showProjects?: boolean;
  showSessions?: boolean;
}

/**
 * Bar chart showing distribution of projects and/or sessions by region.
 */
export const RegionDistributionChart: React.FC<RegionDistributionChartProps> = ({
  data,
  isLoading = false,
  showProjects = true,
  showSessions = true,
}) => {
  // Merge projects and sessions data by region name
  const chartData = React.useMemo(() => {
    if (!data) return [];

    const regionMap = new Map<string, { name: string; projects: number; sessions: number }>();

    if (showProjects && data.projects) {
      data.projects.forEach((item) => {
        const existing = regionMap.get(item.name) || { name: item.name, projects: 0, sessions: 0 };
        existing.projects = item.count;
        regionMap.set(item.name, existing);
      });
    }

    if (showSessions && data.sessions) {
      data.sessions.forEach((item) => {
        const existing = regionMap.get(item.name) || { name: item.name, projects: 0, sessions: 0 };
        existing.sessions = item.count;
        regionMap.set(item.name, existing);
      });
    }

    // Sort by total count (projects + sessions) descending
    return Array.from(regionMap.values()).sort(
      (a, b) => b.projects + b.sessions - (a.projects + a.sessions)
    );
  }, [data, showProjects, showSessions]);

  const isEmpty = chartData.length === 0;

  return (
    <ChartContainer
      title="Distribution by Region"
      isLoading={isLoading}
      isEmpty={isEmpty}
      emptyMessage="No regional data available"
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} layout="vertical" margin={{ left: 20, right: 20, top: 5, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
          <XAxis type="number" tick={{ fontSize: 12 }} />
          <YAxis
            type="category"
            dataKey="name"
            tick={{ fontSize: 11 }}
            width={100}
            tickFormatter={(value: string) =>
              value.length > 15 ? value.substring(0, 15) + '...' : value
            }
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'white',
              border: '1px solid #E5E7EB',
              borderRadius: '0.5rem',
              fontSize: '12px',
            }}
          />
          <Legend wrapperStyle={{ fontSize: '12px' }} />
          {showProjects && (
            <Bar dataKey="projects" name="Projects" fill={TREND_COLORS.projects} radius={[0, 4, 4, 0]} />
          )}
          {showSessions && (
            <Bar dataKey="sessions" name="Sessions" fill={TREND_COLORS.sessions} radius={[0, 4, 4, 0]} />
          )}
        </BarChart>
      </ResponsiveContainer>
    </ChartContainer>
  );
};

// =============================================================================
// Industry Distribution Chart
// =============================================================================

interface IndustryDistributionChartProps {
  data: IndustryDistribution | null;
  isLoading?: boolean;
}

/**
 * Horizontal bar chart showing distribution of projects by industry.
 */
export const IndustryDistributionChart: React.FC<IndustryDistributionChartProps> = ({
  data,
  isLoading = false,
}) => {
  const chartData = React.useMemo(() => {
    if (!data?.industries) return [];
    // Sort by count descending
    return [...data.industries].sort((a, b) => b.count - a.count);
  }, [data]);

  const isEmpty = chartData.length === 0;

  return (
    <ChartContainer
      title="Distribution by Industry"
      height={Math.max(300, chartData.length * 30)}
      isLoading={isLoading}
      isEmpty={isEmpty}
      emptyMessage="No industry data available"
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} layout="vertical" margin={{ left: 20, right: 20, top: 5, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
          <XAxis type="number" tick={{ fontSize: 12 }} />
          <YAxis
            type="category"
            dataKey="name"
            tick={{ fontSize: 10 }}
            width={180}
            tickFormatter={(value: string) =>
              value.length > 25 ? value.substring(0, 25) + '...' : value
            }
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'white',
              border: '1px solid #E5E7EB',
              borderRadius: '0.5rem',
              fontSize: '12px',
            }}
            formatter={(value: number) => [value, 'Projects']}
          />
          <Bar dataKey="count" name="Projects" radius={[0, 4, 4, 0]}>
            {chartData.map((_, index) => (
              <Cell key={`cell-${index}`} fill={INDUSTRY_COLORS[index % INDUSTRY_COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartContainer>
  );
};

// =============================================================================
// Trends Chart (Line Chart)
// =============================================================================

interface TrendsChartProps {
  data: TrendsResponse | null;
  isLoading?: boolean;
  showProjects?: boolean;
  showSessions?: boolean;
  showQAPairs?: boolean;
}

/**
 * Line chart showing trends of projects, sessions, and Q&A pairs over time.
 */
export const TrendsChart: React.FC<TrendsChartProps> = ({
  data,
  isLoading = false,
  showProjects = true,
  showSessions = true,
  showQAPairs = true,
}) => {
  // Merge all time series into a single dataset
  const chartData = React.useMemo(() => {
    if (!data) return [];

    const dateMap = new Map<string, { date: string; projects: number; sessions: number; qa_pairs: number }>();

    const addToMap = (series: TrendDataPoint[] | undefined, key: 'projects' | 'sessions' | 'qa_pairs') => {
      if (!series) return;
      series.forEach((point) => {
        const existing = dateMap.get(point.date) || {
          date: point.date,
          projects: 0,
          sessions: 0,
          qa_pairs: 0,
        };
        existing[key] = point.count;
        dateMap.set(point.date, existing);
      });
    };

    if (showProjects) addToMap(data.projects, 'projects');
    if (showSessions) addToMap(data.sessions, 'sessions');
    if (showQAPairs) addToMap(data.qa_pairs, 'qa_pairs');

    // Sort by date
    return Array.from(dateMap.values()).sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
    );
  }, [data, showProjects, showSessions, showQAPairs]);

  const isEmpty = chartData.length === 0;

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  return (
    <ChartContainer
      title="Activity Trends"
      isLoading={isLoading}
      isEmpty={isEmpty}
      emptyMessage="No trend data available"
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ left: 10, right: 20, top: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11 }}
            tickFormatter={formatDate}
            interval="preserveStartEnd"
          />
          <YAxis tick={{ fontSize: 12 }} allowDecimals={false} />
          <Tooltip
            contentStyle={{
              backgroundColor: 'white',
              border: '1px solid #E5E7EB',
              borderRadius: '0.5rem',
              fontSize: '12px',
            }}
            labelFormatter={(label: any) => formatDate(label as string)}
          />
          <Legend wrapperStyle={{ fontSize: '12px' }} />
          {showProjects && (
            <Line
              type="monotone"
              dataKey="projects"
              name="Projects"
              stroke={TREND_COLORS.projects}
              strokeWidth={2}
              dot={{ r: 3 }}
              activeDot={{ r: 5 }}
            />
          )}
          {showSessions && (
            <Line
              type="monotone"
              dataKey="sessions"
              name="Sessions"
              stroke={TREND_COLORS.sessions}
              strokeWidth={2}
              dot={{ r: 3 }}
              activeDot={{ r: 5 }}
            />
          )}
          {showQAPairs && (
            <Line
              type="monotone"
              dataKey="qa_pairs"
              name="Q&A Pairs"
              stroke={TREND_COLORS.qa_pairs}
              strokeWidth={2}
              dot={{ r: 3 }}
              activeDot={{ r: 5 }}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </ChartContainer>
  );
};

// =============================================================================
// Quality Metrics Chart
// =============================================================================

interface QualityMetricsChartProps {
  data: QualityMetricsResponse | null;
  isLoading?: boolean;
  variant?: 'pie' | 'bar';
}

/**
 * Chart showing Q&A quality metrics (good/bad ratings) and outcome distribution.
 * Supports both pie chart and bar chart variants.
 */
export const QualityMetricsChart: React.FC<QualityMetricsChartProps> = ({
  data,
  isLoading = false,
  variant = 'pie',
}) => {
  const ratingData = React.useMemo(() => {
    if (!data?.quality_metrics) return [];
    const { good, bad, unrated } = data.quality_metrics;
    return [
      { name: 'Good', value: good, color: QUALITY_COLORS.good },
      { name: 'Bad', value: bad, color: QUALITY_COLORS.bad },
      { name: 'Unrated', value: unrated, color: QUALITY_COLORS.unrated },
    ].filter((item) => item.value > 0);
  }, [data]);

  const outcomeData = React.useMemo(() => {
    if (!data?.outcome_distribution) return [];
    return data.outcome_distribution.map((item) => ({
      name: item.label || item.name,
      value: item.count,
      color:
        OUTCOME_COLORS[item.name as keyof typeof OUTCOME_COLORS] || OUTCOME_COLORS.pending,
    }));
  }, [data]);

  const isEmpty = ratingData.length === 0 && outcomeData.length === 0;

  const renderPieLabel = ({
    cx,
    cy,
    midAngle,
    innerRadius,
    outerRadius,
    percent,
  }: {
    cx: number;
    cy: number;
    midAngle: number;
    innerRadius: number;
    outerRadius: number;
    percent: number;
  }) => {
    const RADIAN = Math.PI / 180;
    const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
    const x = cx + radius * Math.cos(-midAngle * RADIAN);
    const y = cy + radius * Math.sin(-midAngle * RADIAN);

    if (percent < 0.05) return null; // Don't render label for small slices

    return (
      <text
        x={x}
        y={y}
        fill="white"
        textAnchor="middle"
        dominantBaseline="central"
        fontSize={12}
        fontWeight={500}
      >
        {`${(percent * 100).toFixed(0)}%`}
      </text>
    );
  };

  if (variant === 'bar') {
    return (
      <ChartContainer
        title="Q&A Quality Metrics"
        isLoading={isLoading}
        isEmpty={isEmpty}
        emptyMessage="No quality data available"
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={ratingData} margin={{ left: 10, right: 20, top: 10, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
            <XAxis dataKey="name" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} allowDecimals={false} />
            <Tooltip
              contentStyle={{
                backgroundColor: 'white',
                border: '1px solid #E5E7EB',
                borderRadius: '0.5rem',
                fontSize: '12px',
              }}
              formatter={(value: number) => [value, 'Q&A Pairs']}
            />
            <Bar dataKey="value" name="Count" radius={[4, 4, 0, 0]}>
              {ratingData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </ChartContainer>
    );
  }

  return (
    <ChartContainer
      title="Q&A Quality Metrics"
      isLoading={isLoading}
      isEmpty={isEmpty}
      emptyMessage="No quality data available"
    >
      <div className="flex flex-col md:flex-row items-center justify-around h-full">
        {ratingData.length > 0 && (
          <div className="flex flex-col items-center">
            <h4 className="text-sm font-medium text-gray-600 mb-2">Rating Distribution</h4>
            <ResponsiveContainer width={200} height={200}>
              <PieChart>
                <Pie
                  data={ratingData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={renderPieLabel}
                  outerRadius={80}
                  dataKey="value"
                >
                  {ratingData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'white',
                    border: '1px solid #E5E7EB',
                    borderRadius: '0.5rem',
                    fontSize: '12px',
                  }}
                  formatter={(value: number, name: string) => [value, name]}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex flex-wrap justify-center gap-3 mt-2">
              {ratingData.map((item) => (
                <div key={item.name} className="flex items-center gap-1.5">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: item.color }}
                  />
                  <span className="text-xs text-gray-600">
                    {item.name} ({item.value})
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {outcomeData.length > 0 && (
          <div className="flex flex-col items-center mt-4 md:mt-0">
            <h4 className="text-sm font-medium text-gray-600 mb-2">Outcome Distribution</h4>
            <ResponsiveContainer width={200} height={200}>
              <PieChart>
                <Pie
                  data={outcomeData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={renderPieLabel}
                  outerRadius={80}
                  dataKey="value"
                >
                  {outcomeData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'white',
                    border: '1px solid #E5E7EB',
                    borderRadius: '0.5rem',
                    fontSize: '12px',
                  }}
                  formatter={(value: number, name: string) => [value, name]}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex flex-wrap justify-center gap-3 mt-2">
              {outcomeData.map((item) => (
                <div key={item.name} className="flex items-center gap-1.5">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: item.color }}
                  />
                  <span className="text-xs text-gray-600">
                    {item.name} ({item.value})
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </ChartContainer>
  );
};

// =============================================================================
// Compact Summary Stats Component
// =============================================================================

interface SummaryStatsProps {
  total: number;
  rated: number;
  good: number;
  bad: number;
  exemplarCount: number;
}

/**
 * Compact summary statistics display for quality metrics.
 */
export const QualitySummaryStats: React.FC<SummaryStatsProps> = ({
  total,
  rated,
  good,
  bad,
  exemplarCount,
}) => {
  const goodRatio = rated > 0 ? ((good / rated) * 100).toFixed(1) : '0.0';

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Quality Summary</h3>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <StatItem label="Total Q&A" value={total} />
        <StatItem label="Rated" value={rated} subtext={`${((rated / total) * 100 || 0).toFixed(0)}%`} />
        <StatItem label="Good" value={good} color="text-green-600" />
        <StatItem label="Bad" value={bad} color="text-red-600" />
        <StatItem label="Exemplars" value={exemplarCount} color="text-violet-600" />
      </div>
      <div className="mt-4 pt-4 border-t border-gray-200">
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-600">Good/Bad Ratio</span>
          <span className="font-medium">
            {good} / {bad}
            <span className="text-gray-500 ml-2">({goodRatio}% good)</span>
          </span>
        </div>
        {rated > 0 && (
          <div className="mt-2 h-2 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-green-500 transition-all duration-300"
              style={{ width: `${goodRatio}%` }}
            />
          </div>
        )}
      </div>
    </div>
  );
};

interface StatItemProps {
  label: string;
  value: number;
  subtext?: string;
  color?: string;
}

const StatItem: React.FC<StatItemProps> = ({ label, value, subtext, color = 'text-gray-900' }) => (
  <div className="text-center">
    <p className={`text-2xl font-bold ${color}`}>{value.toLocaleString()}</p>
    <p className="text-xs text-gray-600">{label}</p>
    {subtext && <p className="text-xs text-gray-400">{subtext}</p>}
  </div>
);
