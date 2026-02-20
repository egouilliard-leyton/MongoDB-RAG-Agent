import React from 'react';
import type { IngestionStage, IngestionProgress as IngestionProgressType } from '../api/types';

// =============================================================================
// Types
// =============================================================================

interface IngestionProgressProps {
  filename: string;
  progress?: IngestionProgressType | null;
  className?: string;
}

interface StageInfo {
  key: IngestionStage;
  label: string;
  description: string;
}

// =============================================================================
// Constants
// =============================================================================

/**
 * Ordered list of ingestion stages with labels and descriptions.
 */
const STAGES: StageInfo[] = [
  {
    key: 'uploading',
    label: 'Uploading',
    description: 'Transferring file to server',
  },
  {
    key: 'converting',
    label: 'Converting',
    description: 'Converting document to markdown',
  },
  {
    key: 'extracting_metadata',
    label: 'Extracting Metadata',
    description: 'Analyzing document structure',
  },
  {
    key: 'chunking',
    label: 'Chunking',
    description: 'Splitting into searchable segments',
  },
  {
    key: 'embedding',
    label: 'Generating Embeddings',
    description: 'Creating vector representations',
  },
  {
    key: 'storing',
    label: 'Storing',
    description: 'Saving to database',
  },
  {
    key: 'verifying',
    label: 'Verifying',
    description: 'Confirming index sync',
  },
  {
    key: 'complete',
    label: 'Complete',
    description: 'Document ready for search',
  },
];

/**
 * Get stage index for ordering.
 */
const getStageIndex = (stage: IngestionStage): number => {
  const index = STAGES.findIndex((s) => s.key === stage);
  return index >= 0 ? index : 0;
};

// =============================================================================
// Component
// =============================================================================

/**
 * IngestionProgress displays real-time progress of document ingestion.
 *
 * Features:
 * - Progress bar with percentage
 * - Current stage indicator with icon
 * - List of completed stages with checkmarks
 * - Pending stages grayed out
 * - Optional SSE integration via progress prop
 */
export const IngestionProgress: React.FC<IngestionProgressProps> = ({
  filename,
  progress,
  className = '',
}) => {
  // Default to uploading stage if no progress provided
  const currentStage = progress?.stage || 'uploading';
  const progressPct = progress?.progress_pct || 0;
  const message = progress?.message || 'Starting...';
  const currentStageIndex = getStageIndex(currentStage);

  // Handle failed state
  if (currentStage === 'failed') {
    return (
      <div className={`bg-red-50 rounded-lg p-6 ${className}`}>
        <div className="flex items-center space-x-3 mb-4">
          <div className="flex-shrink-0">
            <svg
              className="w-8 h-8 text-red-500"
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
          </div>
          <div>
            <h3 className="text-lg font-medium text-red-900">Ingestion Failed</h3>
            <p className="text-sm text-red-700">{message}</p>
          </div>
        </div>
        <p className="text-xs text-red-600 truncate">{filename}</p>
      </div>
    );
  }

  return (
    <div className={`bg-blue-50 rounded-lg p-6 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-medium text-blue-900">Processing Document</h3>
          <p className="text-sm text-blue-700 truncate max-w-xs">{filename}</p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-bold text-blue-600">{progressPct}%</p>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="mb-6">
        <div className="w-full bg-blue-200 rounded-full h-2.5">
          <div
            className="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
            style={{ width: `${progressPct}%` }}
          />
        </div>
        <p className="text-xs text-blue-600 mt-1">{message}</p>
      </div>

      {/* Stage List */}
      <div className="space-y-3">
        {STAGES.filter((s) => s.key !== 'complete').map((stage, index) => {
          const isComplete = index < currentStageIndex;
          const isCurrent = stage.key === currentStage;
          const isPending = index > currentStageIndex;

          return (
            <StageRow
              key={stage.key}
              stage={stage}
              isComplete={isComplete}
              isCurrent={isCurrent}
              isPending={isPending}
            />
          );
        })}
      </div>
    </div>
  );
};

// =============================================================================
// Sub-components
// =============================================================================

interface StageRowProps {
  stage: StageInfo;
  isComplete: boolean;
  isCurrent: boolean;
  isPending: boolean;
}

/**
 * Individual stage row with status indicator.
 */
const StageRow: React.FC<StageRowProps> = ({
  stage,
  isComplete,
  isCurrent,
  isPending,
}) => {
  return (
    <div
      className={`flex items-center space-x-3 ${
        isPending ? 'opacity-40' : ''
      }`}
    >
      {/* Status Icon */}
      <div className="flex-shrink-0">
        {isComplete ? (
          <CheckIcon />
        ) : isCurrent ? (
          <SpinnerIcon />
        ) : (
          <PendingIcon />
        )}
      </div>

      {/* Stage Info */}
      <div className="flex-1 min-w-0">
        <p
          className={`text-sm font-medium ${
            isComplete
              ? 'text-green-700'
              : isCurrent
              ? 'text-blue-700'
              : 'text-gray-500'
          }`}
        >
          {stage.label}
        </p>
        <p className="text-xs text-gray-500 truncate">{stage.description}</p>
      </div>

      {/* Status Label */}
      <div className="flex-shrink-0">
        {isComplete && (
          <span className="text-xs text-green-600 font-medium">Done</span>
        )}
        {isCurrent && (
          <span className="text-xs text-blue-600 font-medium">In Progress</span>
        )}
      </div>
    </div>
  );
};

// =============================================================================
// Icons
// =============================================================================

/**
 * Checkmark icon for completed stages.
 */
const CheckIcon: React.FC = () => (
  <svg className="w-5 h-5 text-green-500" fill="currentColor" viewBox="0 0 20 20">
    <path
      fillRule="evenodd"
      d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
      clipRule="evenodd"
    />
  </svg>
);

/**
 * Spinning loader icon for current stage.
 */
const SpinnerIcon: React.FC = () => (
  <div className="w-5 h-5 border-2 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
);

/**
 * Empty circle icon for pending stages.
 */
const PendingIcon: React.FC = () => (
  <svg className="w-5 h-5 text-gray-300" fill="currentColor" viewBox="0 0 20 20">
    <path
      fillRule="evenodd"
      d="M10 18a8 8 0 100-16 8 8 0 000 16zm0-2a6 6 0 100-12 6 6 0 000 12z"
      clipRule="evenodd"
    />
  </svg>
);

export default IngestionProgress;
