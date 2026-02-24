import React from 'react';
import { PromptEditor } from '../settings/PromptEditor';
import { TransitionEditor } from './TransitionEditor';
import type { WorkflowStage, MetadataFieldDef, StageTransition } from '../../api/types';

interface StageEditorProps {
  stage: WorkflowStage;
  allStages: WorkflowStage[];
  onChange: (updated: WorkflowStage) => void;
  onClose: () => void;
}

export const StageEditor: React.FC<StageEditorProps> = ({
  stage,
  allStages,
  onChange,
  onClose,
}) => {
  const otherStages = allStages.filter((s) => s.id !== stage.id);

  const updateField = <K extends keyof WorkflowStage>(field: K, value: WorkflowStage[K]) => {
    onChange({ ...stage, [field]: value });
  };

  const updateConfig = (field: string, value: unknown) => {
    if (field.startsWith('search_params.')) {
      const paramKey = field.replace('search_params.', '');
      onChange({
        ...stage,
        config: {
          ...stage.config,
          search_params: {
            ...stage.config.search_params,
            [paramKey]: value,
          },
        },
      });
    } else {
      onChange({
        ...stage,
        config: { ...stage.config, [field]: value },
      });
    }
  };

  const updateMetadataField = (index: number, updated: MetadataFieldDef) => {
    const fields = [...stage.config.metadata_fields];
    fields[index] = updated;
    onChange({ ...stage, config: { ...stage.config, metadata_fields: fields } });
  };

  const addMetadataField = () => {
    const newField: MetadataFieldDef = {
      key: '',
      label: '',
      field_type: 'text',
      required: false,
      options: null,
    };
    onChange({
      ...stage,
      config: { ...stage.config, metadata_fields: [...stage.config.metadata_fields, newField] },
    });
  };

  const removeMetadataField = (index: number) => {
    const fields = stage.config.metadata_fields.filter((_, i) => i !== index);
    onChange({ ...stage, config: { ...stage.config, metadata_fields: fields } });
  };

  const updateTransition = (index: number, updated: StageTransition) => {
    const transitions = [...stage.transitions];
    transitions[index] = updated;
    updateField('transitions', transitions);
  };

  const addTransition = () => {
    const newTransition: StageTransition = {
      to_stage_id: '',
      label: '',
      condition: null,
    };
    updateField('transitions', [...stage.transitions, newTransition]);
  };

  const removeTransition = (index: number) => {
    updateField('transitions', stage.transitions.filter((_, i) => i !== index));
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm">
      <div className="flex items-center justify-between p-4 border-b border-gray-200">
        <h3 className="text-lg font-semibold text-gray-900">Edit Stage</h3>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="p-4 space-y-5 max-h-[70vh] overflow-y-auto">
        {/* Basic fields */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Label</label>
            <input
              type="text"
              value={stage.label}
              onChange={(e) => updateField('label', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Color</label>
            <div className="flex items-center space-x-2">
              <input
                type="color"
                value={stage.color}
                onChange={(e) => updateField('color', e.target.value)}
                className="w-10 h-10 border border-gray-300 rounded cursor-pointer"
              />
              <input
                type="text"
                value={stage.color}
                onChange={(e) => updateField('color', e.target.value)}
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm font-mono"
                placeholder="#3B82F6"
              />
            </div>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
          <textarea
            value={stage.description}
            onChange={(e) => updateField('description', e.target.value)}
            rows={2}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
          />
        </div>

        {/* Prompt append */}
        <PromptEditor
          value={stage.config.system_prompt_append ?? ''}
          onChange={(v) => updateConfig('system_prompt_append', v || null)}
          label="Stage Prompt Addition"
          placeholder="Additional prompt text for this stage..."
          rows={3}
        />

        {/* Search params */}
        <div>
          <h4 className="text-sm font-semibold text-gray-900 mb-2">Search Parameters</h4>
          <p className="text-xs text-gray-500 mb-2">Leave empty to use stage defaults or global defaults</p>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs text-gray-600 mb-1">Match Count</label>
              <input
                type="number"
                value={stage.config.search_params.match_count ?? ''}
                onChange={(e) => {
                  const raw = e.target.value;
                  updateConfig('search_params.match_count', raw === '' ? null : parseInt(raw, 10));
                }}
                placeholder="null"
                className="w-full px-2 py-1 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">RRF K</label>
              <input
                type="number"
                value={stage.config.search_params.rrf_k ?? ''}
                onChange={(e) => {
                  const raw = e.target.value;
                  updateConfig('search_params.rrf_k', raw === '' ? null : parseInt(raw, 10));
                }}
                placeholder="null"
                className="w-full px-2 py-1 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">QA History</label>
              <input
                type="number"
                value={stage.config.search_params.qa_history_match_count ?? ''}
                onChange={(e) => {
                  const raw = e.target.value;
                  updateConfig('search_params.qa_history_match_count', raw === '' ? null : parseInt(raw, 10));
                }}
                placeholder="null"
                className="w-full px-2 py-1 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        </div>

        {/* Metadata fields */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-sm font-semibold text-gray-900">Metadata Fields</h4>
            <button
              onClick={addMetadataField}
              className="text-xs text-blue-600 hover:text-blue-800"
            >
              + Add Field
            </button>
          </div>
          {stage.config.metadata_fields.length === 0 && (
            <p className="text-xs text-gray-500">No metadata fields defined.</p>
          )}
          {stage.config.metadata_fields.map((field, i) => (
            <div key={i} className="flex items-center space-x-2 mb-2">
              <input
                type="text"
                value={field.key}
                onChange={(e) => updateMetadataField(i, { ...field, key: e.target.value })}
                placeholder="key"
                className="w-24 px-2 py-1 text-xs border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <input
                type="text"
                value={field.label}
                onChange={(e) => updateMetadataField(i, { ...field, label: e.target.value })}
                placeholder="Label"
                className="flex-1 px-2 py-1 text-xs border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <select
                value={field.field_type}
                onChange={(e) =>
                  updateMetadataField(i, {
                    ...field,
                    field_type: e.target.value as MetadataFieldDef['field_type'],
                  })
                }
                className="w-20 px-1 py-1 text-xs border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="text">text</option>
                <option value="number">number</option>
                <option value="date">date</option>
                <option value="select">select</option>
              </select>
              <label className="flex items-center space-x-1 text-xs">
                <input
                  type="checkbox"
                  checked={field.required}
                  onChange={(e) => updateMetadataField(i, { ...field, required: e.target.checked })}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span>Req</span>
              </label>
              <button
                onClick={() => removeMetadataField(i)}
                className="text-red-500 hover:text-red-700 p-1"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          ))}
        </div>

        {/* Transitions */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-sm font-semibold text-gray-900">Transitions</h4>
            <button
              onClick={addTransition}
              className="text-xs text-blue-600 hover:text-blue-800"
            >
              + Add Transition
            </button>
          </div>
          {stage.transitions.length === 0 && (
            <p className="text-xs text-gray-500">No transitions defined (terminal stage).</p>
          )}
          {stage.transitions.map((t, i) => (
            <TransitionEditor
              key={i}
              transition={t}
              allStages={otherStages}
              onChange={(updated) => updateTransition(i, updated)}
              onDelete={() => removeTransition(i)}
            />
          ))}
        </div>
      </div>
    </div>
  );
};
