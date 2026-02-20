import React, { useState } from 'react';
import type { DocumentUploadResponse, IngestionJob } from '../api/types';
import { Button } from './Button';

// =============================================================================
// Types
// =============================================================================

interface IngestionResultProps {
  result: DocumentUploadResponse | IngestionJob;
  onUploadAnother?: () => void;
  onViewDocument?: (documentId: string) => void;
  className?: string;
}

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Format metadata key for display (snake_case to Title Case).
 */
const formatMetadataKey = (key: string): string => {
  return key
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
};

/**
 * Format metadata value for display.
 */
const formatMetadataValue = (value: unknown): string => {
  if (value === null || value === undefined) return '-';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'object') {
    if (Array.isArray(value)) {
      return value.length > 0 ? value.join(', ') : '-';
    }
    return JSON.stringify(value);
  }
  return String(value);
};

/**
 * Format file size for display.
 * @unused - Kept for potential future use
 */
// const formatFileSize = (bytes: number): string => {
//   if (bytes < 1024) return `${bytes} B`;
//   if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
//   return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
// };

/**
 * Format duration in milliseconds for display.
 */
const formatDuration = (ms: number): string => {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`;
};

/**
 * Determine if the result is a DocumentUploadResponse or IngestionJob.
 */
const isUploadResponse = (
  result: DocumentUploadResponse | IngestionJob
): result is DocumentUploadResponse => {
  return 'chunks_created' in result && 'total_tokens' in result;
};

// =============================================================================
// Component
// =============================================================================

/**
 * IngestionResult displays a comprehensive summary after document ingestion.
 *
 * Features:
 * - Success/partial/failed status indication
 * - Statistics: chunks, tokens, processing time
 * - Extracted metadata display with expandable view
 * - Warnings and errors lists
 * - Action buttons: View Document, Upload Another
 */
export const IngestionResult: React.FC<IngestionResultProps> = ({
  result,
  onUploadAnother,
  onViewDocument,
  className = '',
}) => {
  const [showAllMetadata, setShowAllMetadata] = useState(false);

  // Normalize data from either response type
  const isUpload = isUploadResponse(result);
  const status = isUpload ? result.status : result.status;
  const documentId = isUpload ? result.document_id : result.document_id;
  const title = isUpload ? result.title : result.filename;
  const filename = isUpload ? result.filename : result.filename;
  const chunksCreated = isUpload ? result.chunks_created : result.statistics.chunks_created;
  const totalTokens = isUpload ? result.total_tokens : result.statistics.total_tokens;
  const processingTime = isUpload ? result.processing_time_ms : result.duration_ms || 0;
  const metadata = isUpload ? result.metadata_extracted : result.metadata_extracted;
  const warnings = result.warnings;
  const errors = result.errors;

  // Status styling - keeping for potential future use
  // const isSuccess = status === 'success';
  // const isPartial = status === 'partial';
  // const isFailed = status === 'failed';

  const statusConfig = {
    success: {
      bg: 'bg-green-50',
      border: 'border-green-200',
      title: 'text-green-900',
      icon: 'text-green-600',
      label: 'Document Ingested Successfully',
    },
    partial: {
      bg: 'bg-yellow-50',
      border: 'border-yellow-200',
      title: 'text-yellow-900',
      icon: 'text-yellow-600',
      label: 'Document Partially Ingested',
    },
    failed: {
      bg: 'bg-red-50',
      border: 'border-red-200',
      title: 'text-red-900',
      icon: 'text-red-600',
      label: 'Ingestion Failed',
    },
  };

  const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.failed;

  // Filter metadata for display
  const metadataEntries = Object.entries(metadata || {}).filter(
    ([key, value]) =>
      value !== null &&
      value !== undefined &&
      value !== '' &&
      !key.startsWith('_') &&
      key !== 'file_path' // Often too long
  );

  const visibleMetadata = showAllMetadata
    ? metadataEntries
    : metadataEntries.slice(0, 6);

  return (
    <div
      className={`rounded-lg border ${config.bg} ${config.border} ${className}`}
    >
      {/* Header */}
      <div className="p-6 border-b border-inherit">
        <div className="flex items-start space-x-4">
          {/* Status Icon */}
          <div className="flex-shrink-0">
            <StatusIcon status={status} className={config.icon} />
          </div>

          {/* Title and Subtitle */}
          <div className="flex-1 min-w-0">
            <h3 className={`text-lg font-semibold ${config.title}`}>
              {config.label}
            </h3>
            <p className="text-sm text-gray-600 mt-1 truncate" title={title}>
              {title || filename}
            </p>
            {title !== filename && (
              <p className="text-xs text-gray-500 truncate" title={filename}>
                {filename}
              </p>
            )}
          </div>

          {/* Document ID Badge */}
          {documentId && (
            <div className="flex-shrink-0">
              <span className="text-xs text-gray-500 font-mono bg-gray-100 px-2 py-1 rounded">
                {documentId.slice(-8)}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Statistics */}
      <div className="p-6 border-b border-inherit">
        <h4 className="text-sm font-medium text-gray-700 mb-3">Statistics</h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            label="Chunks Created"
            value={chunksCreated}
            icon={<ChunksIcon />}
          />
          <StatCard
            label="Total Tokens"
            value={totalTokens.toLocaleString()}
            icon={<TokensIcon />}
          />
          <StatCard
            label="Avg Tokens/Chunk"
            value={chunksCreated > 0 ? Math.round(totalTokens / chunksCreated) : 0}
            icon={<AverageIcon />}
          />
          <StatCard
            label="Processing Time"
            value={formatDuration(processingTime)}
            icon={<TimeIcon />}
          />
        </div>
      </div>

      {/* Metadata */}
      {metadataEntries.length > 0 && (
        <div className="p-6 border-b border-inherit">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium text-gray-700">
              Extracted Metadata
            </h4>
            {metadataEntries.length > 6 && (
              <button
                onClick={() => setShowAllMetadata(!showAllMetadata)}
                className="text-xs text-blue-600 hover:text-blue-800"
              >
                {showAllMetadata
                  ? 'Show less'
                  : `Show all (${metadataEntries.length})`}
              </button>
            )}
          </div>
          <div className="bg-white rounded-lg border border-gray-100 overflow-hidden">
            <dl className="divide-y divide-gray-100">
              {visibleMetadata.map(([key, value]) => (
                <div
                  key={key}
                  className="px-4 py-2 grid grid-cols-3 gap-4"
                >
                  <dt className="text-sm text-gray-500 truncate">
                    {formatMetadataKey(key)}
                  </dt>
                  <dd className="text-sm text-gray-900 col-span-2 truncate" title={formatMetadataValue(value)}>
                    {formatMetadataValue(value)}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      )}

      {/* Warnings */}
      {warnings.length > 0 && (
        <div className="p-6 border-b border-inherit">
          <h4 className="text-sm font-medium text-yellow-700 mb-2 flex items-center">
            <WarningIcon className="w-4 h-4 mr-1" />
            Warnings ({warnings.length})
          </h4>
          <ul className="space-y-1">
            {warnings.map((warning, i) => (
              <li
                key={i}
                className="text-sm text-yellow-600 flex items-start"
              >
                <span className="mr-2">-</span>
                <span>{warning}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Errors */}
      {errors.length > 0 && (
        <div className="p-6 border-b border-inherit">
          <h4 className="text-sm font-medium text-red-700 mb-2 flex items-center">
            <ErrorIcon className="w-4 h-4 mr-1" />
            Errors ({errors.length})
          </h4>
          <ul className="space-y-1">
            {errors.map((error, i) => (
              <li key={i} className="text-sm text-red-600 flex items-start">
                <span className="mr-2">-</span>
                <span>{error}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Actions */}
      <div className="p-6 flex justify-end space-x-3">
        {documentId && onViewDocument && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => onViewDocument(documentId)}
          >
            View Document
          </Button>
        )}
        {onUploadAnother && (
          <Button variant="primary" size="sm" onClick={onUploadAnother}>
            Upload Another
          </Button>
        )}
      </div>
    </div>
  );
};

// =============================================================================
// Sub-components
// =============================================================================

interface StatCardProps {
  label: string;
  value: string | number;
  icon: React.ReactNode;
}

/**
 * Statistics card with icon, value, and label.
 */
const StatCard: React.FC<StatCardProps> = ({ label, value, icon }) => (
  <div className="text-center p-3 bg-white rounded-lg border border-gray-100">
    <div className="flex justify-center mb-2 text-gray-400">{icon}</div>
    <p className="text-xl font-bold text-gray-900">{value}</p>
    <p className="text-xs text-gray-500">{label}</p>
  </div>
);

// =============================================================================
// Icons
// =============================================================================

interface IconProps {
  className?: string;
}

const StatusIcon: React.FC<{ status: string; className: string }> = ({
  status,
  className,
}) => {
  if (status === 'success') {
    return (
      <svg
        className={`w-8 h-8 ${className}`}
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
    );
  }
  if (status === 'partial') {
    return (
      <svg
        className={`w-8 h-8 ${className}`}
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
        />
      </svg>
    );
  }
  return (
    <svg
      className={`w-8 h-8 ${className}`}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  );
};

const ChunksIcon: React.FC = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z"
    />
  </svg>
);

const TokensIcon: React.FC = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
    />
  </svg>
);

const AverageIcon: React.FC = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
    />
  </svg>
);

const TimeIcon: React.FC = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
    />
  </svg>
);

const WarningIcon: React.FC<IconProps> = ({ className = '' }) => (
  <svg
    className={className}
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
    />
  </svg>
);

const ErrorIcon: React.FC<IconProps> = ({ className = '' }) => (
  <svg
    className={className}
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"
    />
  </svg>
);

export default IngestionResult;
