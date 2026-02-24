import React from 'react';
import { PromptEditor } from './PromptEditor';
import type { GlobalSettings } from '../../api/types';

interface StageDefaultsPanelProps {
  settings: GlobalSettings;
  onChange: (field: string, value: unknown) => void;
}

interface NullableNumberInputProps {
  label: string;
  description: string;
  value: number | null;
  onChange: (value: number | null) => void;
}

const NullableNumberInput: React.FC<NullableNumberInputProps> = ({
  label,
  description,
  value,
  onChange,
}) => (
  <div className="py-2">
    <div className="flex items-center justify-between mb-1">
      <div>
        <p className="text-sm font-medium text-gray-900">{label}</p>
        <p className="text-xs text-gray-500">{description}</p>
      </div>
      <div className="flex items-center space-x-2">
        <input
          type="number"
          value={value ?? ''}
          onChange={(e) => {
            const raw = e.target.value;
            if (raw === '') {
              onChange(null);
            } else {
              const v = parseInt(raw, 10);
              if (!isNaN(v)) onChange(v);
            }
          }}
          placeholder="null"
          className="w-20 px-2 py-1 text-sm border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
      </div>
    </div>
  </div>
);

export const StageDefaultsPanel: React.FC<StageDefaultsPanelProps> = ({ settings, onChange }) => {
  const stageDefaults = settings.stage_defaults;

  return (
    <div className="space-y-6">
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
        <p className="text-sm text-blue-800">
          These defaults apply to every stage. Individual stages can override them in the Workflow Builder.
        </p>
      </div>

      <PromptEditor
        value={stageDefaults.system_prompt_append ?? ''}
        onChange={(v) => onChange('stage_defaults.system_prompt_append', v || null)}
        label="Default Stage Prompt Addition"
        placeholder="Additional prompt text appended for all stages..."
        rows={4}
      />

      <div>
        <h4 className="text-sm font-semibold text-gray-900 mb-2">Default Search Parameters</h4>
        <p className="text-xs text-gray-500 mb-3">
          <code className="bg-gray-100 px-1 rounded">null</code> = use global defaults
        </p>
        <div className="divide-y divide-gray-100">
          <NullableNumberInput
            label="Match Count"
            description="Number of search results for stages"
            value={stageDefaults.search_params.match_count}
            onChange={(v) => onChange('stage_defaults.search_params.match_count', v)}
          />
          <NullableNumberInput
            label="RRF K"
            description="Reciprocal Rank Fusion constant for stages"
            value={stageDefaults.search_params.rrf_k}
            onChange={(v) => onChange('stage_defaults.search_params.rrf_k', v)}
          />
          <NullableNumberInput
            label="Q&A History Match Count"
            description="Historical Q&A pairs to include per stage"
            value={stageDefaults.search_params.qa_history_match_count}
            onChange={(v) => onChange('stage_defaults.search_params.qa_history_match_count', v)}
          />
        </div>
      </div>
    </div>
  );
};
