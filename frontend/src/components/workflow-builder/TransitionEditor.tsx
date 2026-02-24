import React from 'react';
import type { StageTransition, WorkflowStage } from '../../api/types';

interface TransitionEditorProps {
  transition: StageTransition;
  allStages: WorkflowStage[];
  onChange: (updated: StageTransition) => void;
  onDelete: () => void;
}

export const TransitionEditor: React.FC<TransitionEditorProps> = ({
  transition,
  allStages,
  onChange,
  onDelete,
}) => {
  return (
    <div className="flex items-center space-x-3 py-2">
      <select
        value={transition.to_stage_id}
        onChange={(e) => onChange({ ...transition, to_stage_id: e.target.value })}
        className="flex-1 px-2 py-1 text-sm border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
      >
        <option value="">Select stage...</option>
        {allStages.map((s) => (
          <option key={s.id} value={s.id}>
            {s.label}
          </option>
        ))}
      </select>
      <input
        type="text"
        value={transition.label}
        onChange={(e) => onChange({ ...transition, label: e.target.value })}
        placeholder="Transition label"
        className="flex-1 px-2 py-1 text-sm border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
      />
      <button
        onClick={onDelete}
        className="text-red-500 hover:text-red-700 p-1"
        title="Remove transition"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
};
