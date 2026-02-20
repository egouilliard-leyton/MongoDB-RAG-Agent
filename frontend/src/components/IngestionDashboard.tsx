import React, { useEffect, useState, useCallback } from 'react';
import { useIngestion } from '../contexts/IngestionContext';
import type {
  IngestionJob,
  IngestionJobFilter,
  IngestionStatus,
  IngestionAggregateStats,
} from '../api/types';
import { Button } from './Button';
import { LoadingSpinner } from './LoadingSpinner';
import { ErrorAlert } from './ErrorAlert';

// =============================================================================
// Types
// =============================================================================

interface IngestionDashboardProps {
  projectId?: string;
  onJobClick?: (job: IngestionJob) => void;
  onUploadClick?: () => void;
  className?: string;
}

// =============================================================================
// Constants
// =============================================================================

const STATUS_OPTIONS: { value: IngestionStatus | ''; label: string }[] = [
  { value: '', label: 'All Statuses' },
  { value: 'success', label: 'Success' },
  { value: 'partial', label: 'Partial' },
  { value: 'failed', label: 'Failed' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'pending', label: 'Pending' },
];

// =============================================================================
// Component
// =============================================================================

/**
 * IngestionDashboard provides a comprehensive view of ingestion history
 * with filtering, statistics, and job list.
 *
 * Features:
 * - Aggregate statistics cards
 * - Filters: status, date range, filename search
 * - Paginated job list with click-through
 * - Refresh and load more functionality
 */
export const IngestionDashboard: React.FC<IngestionDashboardProps> = ({
  projectId,
  onJobClick,
  onUploadClick,
  className = '',
}) => {
  const {
    jobs,
    jobsTotal,
    hasMoreJobs,
    stats,
    isLoadingJobs,
    isLoadingStats,
    error,
    loadJobs,
    loadMoreJobs,
    loadStats,
    clearError,
  } = useIngestion();

  // Filter state
  const [filters, setFilters] = useState<IngestionJobFilter>({
    project_id: projectId,
  });
  const [statusFilter, setStatusFilter] = useState<IngestionStatus | ''>('');
  const [filenameSearch, setFilenameSearch] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  // Initial load
  useEffect(() => {
    loadJobs({ project_id: projectId });
    loadStats(projectId);
  }, [projectId, loadJobs, loadStats]);

  /**
   * Apply filters and reload jobs.
   */
  const applyFilters = useCallback(() => {
    const newFilters: IngestionJobFilter = {
      project_id: projectId,
    };

    if (statusFilter) {
      newFilters.status = statusFilter;
    }
    if (filenameSearch.trim()) {
      newFilters.filename_contains = filenameSearch.trim();
    }
    if (dateFrom) {
      newFilters.created_after = new Date(dateFrom).toISOString();
    }
    if (dateTo) {
      // Add a day to include the full end date
      const endDate = new Date(dateTo);
      endDate.setDate(endDate.getDate() + 1);
      newFilters.created_before = endDate.toISOString();
    }

    setFilters(newFilters);
    loadJobs(newFilters);
  }, [projectId, statusFilter, filenameSearch, dateFrom, dateTo, loadJobs]);

  /**
   * Clear all filters and reload.
   */
  const clearFilters = useCallback(() => {
    setStatusFilter('');
    setFilenameSearch('');
    setDateFrom('');
    setDateTo('');
    const newFilters = { project_id: projectId };
    setFilters(newFilters);
    loadJobs(newFilters);
  }, [projectId, loadJobs]);

  /**
   * Handle refresh button click.
   */
  const handleRefresh = useCallback(() => {
    loadJobs(filters);
    loadStats(projectId);
  }, [filters, projectId, loadJobs, loadStats]);

  /**
   * Handle load more button click.
   */
  const handleLoadMore = useCallback(() => {
    loadMoreJobs(filters);
  }, [filters, loadMoreJobs]);

  // Check if any filters are active
  const hasActiveFilters =
    statusFilter !== '' ||
    filenameSearch.trim() !== '' ||
    dateFrom !== '' ||
    dateTo !== '';

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">
            Ingestion History
          </h2>
          <p className="text-sm text-gray-500">
            {jobsTotal} total ingestion jobs
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={isLoadingJobs}
          >
            Refresh
          </Button>
          {onUploadClick && (
            <Button variant="primary" size="sm" onClick={onUploadClick}>
              Upload Document
            </Button>
          )}
        </div>
      </div>

      {/* Error */}
      {error && <ErrorAlert message={error} onDismiss={clearError} />}

      {/* Statistics */}
      {stats && <StatsSection stats={stats} isLoading={isLoadingStats} />}

      {/* Filters */}
      <FiltersSection
        statusFilter={statusFilter}
        filenameSearch={filenameSearch}
        dateFrom={dateFrom}
        dateTo={dateTo}
        onStatusChange={setStatusFilter}
        onFilenameChange={setFilenameSearch}
        onDateFromChange={setDateFrom}
        onDateToChange={setDateTo}
        onApply={applyFilters}
        onClear={clearFilters}
        hasActiveFilters={hasActiveFilters}
      />

      {/* Job List */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        {isLoadingJobs && jobs.length === 0 ? (
          <div className="p-12">
            <LoadingSpinner size="lg" />
          </div>
        ) : jobs.length === 0 ? (
          <EmptyState
            hasFilters={hasActiveFilters}
            onClearFilters={clearFilters}
            onUpload={onUploadClick}
          />
        ) : (
          <>
            <JobList jobs={jobs} onJobClick={onJobClick} />
            {hasMoreJobs && (
              <div className="p-4 border-t border-gray-200 text-center">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleLoadMore}
                  disabled={isLoadingJobs}
                  isLoading={isLoadingJobs}
                >
                  Load More
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

// =============================================================================
// Sub-components
// =============================================================================

interface StatsSectionProps {
  stats: IngestionAggregateStats;
  isLoading: boolean;
}

/**
 * Aggregate statistics cards.
 */
const StatsSection: React.FC<StatsSectionProps> = ({ stats, isLoading }) => {
  if (isLoading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-gray-100 rounded-lg p-4 animate-pulse h-20" />
        ))}
      </div>
    );
  }

  const successRate =
    stats.total_jobs > 0
      ? ((stats.by_status.success || 0) / stats.total_jobs) * 100
      : 0;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <StatCard
        label="Total Jobs"
        value={stats.total_jobs}
        color="blue"
      />
      <StatCard
        label="Success Rate"
        value={`${successRate.toFixed(0)}%`}
        color={successRate >= 90 ? 'green' : successRate >= 70 ? 'yellow' : 'red'}
      />
      <StatCard
        label="Chunks Created"
        value={stats.total_chunks_created.toLocaleString()}
        color="purple"
      />
      <StatCard
        label="Avg Duration"
        value={formatDuration(stats.avg_duration_ms || 0)}
        color="gray"
      />
    </div>
  );
};

interface StatCardProps {
  label: string;
  value: string | number;
  color: 'blue' | 'green' | 'yellow' | 'red' | 'purple' | 'gray';
}

const StatCard: React.FC<StatCardProps> = ({ label, value, color }) => {
  const colorClasses = {
    blue: 'bg-blue-50 text-blue-700',
    green: 'bg-green-50 text-green-700',
    yellow: 'bg-yellow-50 text-yellow-700',
    red: 'bg-red-50 text-red-700',
    purple: 'bg-purple-50 text-purple-700',
    gray: 'bg-gray-50 text-gray-700',
  };

  return (
    <div className={`rounded-lg p-4 ${colorClasses[color]}`}>
      <p className="text-2xl font-bold">{value}</p>
      <p className="text-sm opacity-80">{label}</p>
    </div>
  );
};

interface FiltersSectionProps {
  statusFilter: IngestionStatus | '';
  filenameSearch: string;
  dateFrom: string;
  dateTo: string;
  onStatusChange: (value: IngestionStatus | '') => void;
  onFilenameChange: (value: string) => void;
  onDateFromChange: (value: string) => void;
  onDateToChange: (value: string) => void;
  onApply: () => void;
  onClear: () => void;
  hasActiveFilters: boolean;
}

/**
 * Filters section with status, search, and date range.
 */
const FiltersSection: React.FC<FiltersSectionProps> = ({
  statusFilter,
  filenameSearch,
  dateFrom,
  dateTo,
  onStatusChange,
  onFilenameChange,
  onDateFromChange,
  onDateToChange,
  onApply,
  onClear,
  hasActiveFilters,
}) => {
  return (
    <div className="bg-gray-50 rounded-lg p-4">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Status Filter */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Status
          </label>
          <select
            value={statusFilter}
            onChange={(e) => onStatusChange(e.target.value as IngestionStatus | '')}
            className="w-full rounded-md border-gray-300 shadow-sm text-sm focus:border-blue-500 focus:ring-blue-500"
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* Filename Search */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Filename
          </label>
          <input
            type="text"
            value={filenameSearch}
            onChange={(e) => onFilenameChange(e.target.value)}
            placeholder="Search filename..."
            className="w-full rounded-md border-gray-300 shadow-sm text-sm focus:border-blue-500 focus:ring-blue-500"
          />
        </div>

        {/* Date From */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            From Date
          </label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => onDateFromChange(e.target.value)}
            className="w-full rounded-md border-gray-300 shadow-sm text-sm focus:border-blue-500 focus:ring-blue-500"
          />
        </div>

        {/* Date To */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            To Date
          </label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => onDateToChange(e.target.value)}
            className="w-full rounded-md border-gray-300 shadow-sm text-sm focus:border-blue-500 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* Filter Actions */}
      <div className="flex justify-end space-x-2 mt-4">
        {hasActiveFilters && (
          <Button variant="outline" size="sm" onClick={onClear}>
            Clear Filters
          </Button>
        )}
        <Button variant="primary" size="sm" onClick={onApply}>
          Apply Filters
        </Button>
      </div>
    </div>
  );
};

interface JobListProps {
  jobs: IngestionJob[];
  onJobClick?: (job: IngestionJob) => void;
}

/**
 * List of ingestion jobs.
 */
const JobList: React.FC<JobListProps> = ({ jobs, onJobClick }) => {
  return (
    <div className="divide-y divide-gray-200">
      {jobs.map((job) => (
        <JobRow key={job._id} job={job} onClick={onJobClick} />
      ))}
    </div>
  );
};

interface JobRowProps {
  job: IngestionJob;
  onClick?: (job: IngestionJob) => void;
}

/**
 * Individual job row in the list.
 */
const JobRow: React.FC<JobRowProps> = ({ job, onClick }) => {
  const handleClick = () => onClick?.(job);

  return (
    <div
      className={`p-4 hover:bg-gray-50 transition-colors ${
        onClick ? 'cursor-pointer' : ''
      }`}
      onClick={onClick ? handleClick : undefined}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4 min-w-0">
          {/* Status Badge */}
          <StatusBadge status={job.status} />

          {/* File Info */}
          <div className="min-w-0">
            <p className="text-sm font-medium text-gray-900 truncate">
              {job.filename}
            </p>
            <p className="text-xs text-gray-500">
              {formatDate(job.created_at)}
              {job.duration_ms && ` • ${formatDuration(job.duration_ms)}`}
            </p>
          </div>
        </div>

        {/* Stats */}
        <div className="flex items-center space-x-6 text-sm text-gray-500">
          <div className="text-center">
            <p className="font-medium text-gray-900">
              {job.statistics.chunks_created}
            </p>
            <p className="text-xs">chunks</p>
          </div>
          <div className="text-center">
            <p className="font-medium text-gray-900">
              {job.statistics.total_tokens.toLocaleString()}
            </p>
            <p className="text-xs">tokens</p>
          </div>
          {onClick && (
            <svg
              className="w-5 h-5 text-gray-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 5l7 7-7 7"
              />
            </svg>
          )}
        </div>
      </div>

      {/* Warnings/Errors Indicators */}
      {(job.warnings.length > 0 || job.errors.length > 0) && (
        <div className="mt-2 flex items-center space-x-3">
          {job.warnings.length > 0 && (
            <span className="text-xs text-yellow-600">
              {job.warnings.length} warning{job.warnings.length > 1 ? 's' : ''}
            </span>
          )}
          {job.errors.length > 0 && (
            <span className="text-xs text-red-600">
              {job.errors.length} error{job.errors.length > 1 ? 's' : ''}
            </span>
          )}
        </div>
      )}
    </div>
  );
};

interface StatusBadgeProps {
  status: IngestionStatus;
}

/**
 * Status badge component.
 */
const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const config = {
    success: { bg: 'bg-green-100', text: 'text-green-800', label: 'Success' },
    partial: { bg: 'bg-yellow-100', text: 'text-yellow-800', label: 'Partial' },
    failed: { bg: 'bg-red-100', text: 'text-red-800', label: 'Failed' },
    in_progress: { bg: 'bg-blue-100', text: 'text-blue-800', label: 'Processing' },
    pending: { bg: 'bg-gray-100', text: 'text-gray-800', label: 'Pending' },
  };

  const { bg, text, label } = config[status] || config.pending;

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${bg} ${text}`}
    >
      {label}
    </span>
  );
};

interface EmptyStateProps {
  hasFilters: boolean;
  onClearFilters: () => void;
  onUpload?: () => void;
}

/**
 * Empty state when no jobs found.
 */
const EmptyState: React.FC<EmptyStateProps> = ({
  hasFilters,
  onClearFilters,
  onUpload,
}) => {
  return (
    <div className="p-12 text-center">
      <svg
        className="mx-auto h-12 w-12 text-gray-400"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
        />
      </svg>
      <h3 className="mt-4 text-sm font-medium text-gray-900">
        {hasFilters ? 'No matching jobs' : 'No ingestion jobs'}
      </h3>
      <p className="mt-1 text-sm text-gray-500">
        {hasFilters
          ? 'Try adjusting your filters or clear them to see all jobs.'
          : 'Upload a document to get started.'}
      </p>
      <div className="mt-6 space-x-2">
        {hasFilters && (
          <Button variant="outline" size="sm" onClick={onClearFilters}>
            Clear Filters
          </Button>
        )}
        {onUpload && !hasFilters && (
          <Button variant="primary" size="sm" onClick={onUpload}>
            Upload Document
          </Button>
        )}
      </div>
    </div>
  );
};

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Format duration in milliseconds for display.
 */
const formatDuration = (ms: number): string => {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`;
};

/**
 * Format date for display.
 */
const formatDate = (dateStr: string): string => {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) {
    return `Today at ${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
  }
  if (diffDays === 1) {
    return `Yesterday at ${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
  }
  if (diffDays < 7) {
    return `${diffDays} days ago`;
  }
  return date.toLocaleDateString();
};

export default IngestionDashboard;
