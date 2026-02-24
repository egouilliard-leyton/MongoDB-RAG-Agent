import React from 'react';
import type { GlobalSettings } from '../../api/types';

interface RAGParametersPanelProps {
  settings: GlobalSettings;
  onChange: (field: keyof GlobalSettings, value: unknown) => void;
  isDirty: boolean;
}

interface ToggleFieldProps {
  label: string;
  description: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}

const ToggleField: React.FC<ToggleFieldProps> = ({ label, description, checked, onChange }) => (
  <div className="flex items-start justify-between py-3">
    <div className="flex-1 min-w-0 mr-4">
      <p className="text-sm font-medium text-gray-900">{label}</p>
      <p className="text-xs text-gray-500 mt-0.5">{description}</p>
    </div>
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
        checked ? 'bg-blue-600' : 'bg-gray-200'
      }`}
    >
      <span
        className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ${
          checked ? 'translate-x-5' : 'translate-x-0'
        }`}
      />
    </button>
  </div>
);

interface NumberFieldProps {
  label: string;
  description: string;
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
}

const NumberField: React.FC<NumberFieldProps> = ({ label, description, value, onChange, min, max }) => (
  <div className="py-3">
    <div className="flex items-center justify-between mb-1">
      <div>
        <p className="text-sm font-medium text-gray-900">{label}</p>
        <p className="text-xs text-gray-500 mt-0.5">{description}</p>
      </div>
      <input
        type="number"
        value={value}
        onChange={(e) => {
          const v = parseInt(e.target.value, 10);
          if (!isNaN(v) && v >= min && v <= max) onChange(v);
        }}
        min={min}
        max={max}
        className="w-20 px-2 py-1 text-sm border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
      />
    </div>
    <p className="text-xs text-gray-400">Range: {min} - {max}</p>
  </div>
);

export const RAGParametersPanel: React.FC<RAGParametersPanelProps> = ({
  settings,
  onChange,
  isDirty,
}) => {
  return (
    <div className="space-y-1">
      {isDirty && <span className="text-amber-500 text-sm">Unsaved changes</span>}

      <div className="divide-y divide-gray-200">
        <ToggleField
          label="Question Decomposition"
          description="Break complex questions into sub-questions for more thorough answers"
          checked={settings.enable_question_decomposition}
          onChange={(v) => onChange('enable_question_decomposition', v)}
        />
        <ToggleField
          label="Iterative Refinement"
          description="Refine answers through multiple search passes for better accuracy"
          checked={settings.enable_iterative_refinement}
          onChange={(v) => onChange('enable_iterative_refinement', v)}
        />
        <ToggleField
          label="Q&A History Search"
          description="Search previous Q&A pairs for relevant context when answering"
          checked={settings.enable_qa_history_search}
          onChange={(v) => onChange('enable_qa_history_search', v)}
        />
        <ToggleField
          label="Show Full Citations"
          description="Display complete citation details including chunk content in answers"
          checked={settings.show_full_citations}
          onChange={(v) => onChange('show_full_citations', v)}
        />
      </div>

      <div className="border-t border-gray-200 pt-4 mt-4">
        <h4 className="text-sm font-semibold text-gray-900 mb-2">Search Parameters</h4>
        <div className="divide-y divide-gray-100">
          <NumberField
            label="Default Match Count"
            description="Number of search results returned by default"
            value={settings.default_match_count}
            onChange={(v) => onChange('default_match_count', v)}
            min={1}
            max={50}
          />
          <NumberField
            label="Max Match Count"
            description="Maximum number of search results allowed"
            value={settings.max_match_count}
            onChange={(v) => onChange('max_match_count', v)}
            min={1}
            max={100}
          />
          <NumberField
            label="RRF K Constant"
            description="Reciprocal Rank Fusion constant for hybrid search scoring"
            value={settings.rrf_k_constant}
            onChange={(v) => onChange('rrf_k_constant', v)}
            min={10}
            max={120}
          />
          <NumberField
            label="Q&A History Match Count"
            description="Number of historical Q&A pairs to include as context"
            value={settings.qa_history_match_count}
            onChange={(v) => onChange('qa_history_match_count', v)}
            min={1}
            max={10}
          />
        </div>
      </div>
    </div>
  );
};
