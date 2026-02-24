import React from 'react';
import type { WorkflowStage } from '../../api/types';

interface StageCardProps {
  stage: WorkflowStage;
  onEdit: (stage: WorkflowStage) => void;
  onDelete: (stageId: string) => void;
  onMoveUp: (stageId: string) => void;
  onMoveDown: (stageId: string) => void;
  isFirst: boolean;
  isLast: boolean;
}

export const StageCard: React.FC<StageCardProps> = ({
  stage,
  onEdit,
  onDelete,
  onMoveUp,
  onMoveDown,
  isFirst,
  isLast,
}) => {
  return (
    <div className="flex items-center p-3 border border-gray-200 rounded-lg hover:border-gray-300 transition-colors">
      {/* Color dot */}
      <div
        className="w-3 h-3 rounded-full flex-shrink-0 mr-3"
        style={{ backgroundColor: stage.color }}
      />

      {/* Stage info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center space-x-2">
          <p className="text-sm font-medium text-gray-900 truncate">{stage.label}</p>
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-gray-100 text-gray-600">
            {stage.transitions.length} transition{stage.transitions.length !== 1 ? 's' : ''}
          </span>
        </div>
        {stage.description && (
          <p className="text-xs text-gray-500 truncate mt-0.5">{stage.description}</p>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center space-x-1 ml-3 flex-shrink-0">
        <button
          onClick={() => onMoveUp(stage.id)}
          disabled={isFirst}
          className="p-1 text-gray-400 hover:text-gray-600 disabled:opacity-30 disabled:cursor-not-allowed"
          title="Move up"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
          </svg>
        </button>
        <button
          onClick={() => onMoveDown(stage.id)}
          disabled={isLast}
          className="p-1 text-gray-400 hover:text-gray-600 disabled:opacity-30 disabled:cursor-not-allowed"
          title="Move down"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
        <button
          onClick={() => onEdit(stage)}
          className="p-1 text-gray-400 hover:text-blue-600"
          title="Edit stage"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
          </svg>
        </button>
        <button
          onClick={() => onDelete(stage.id)}
          className="p-1 text-gray-400 hover:text-red-600"
          title="Delete stage"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  );
};
