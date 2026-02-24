import React from 'react';
import type { GlobalSettings } from '../../api/types';

interface ModelConfigPanelProps {
  settings: GlobalSettings;
  onChange: (field: keyof GlobalSettings, value: string) => void;
}

export const ModelConfigPanel: React.FC<ModelConfigPanelProps> = ({ settings, onChange }) => {
  const isOpenAI = settings.llm_base_url.includes('api.openai.com');

  return (
    <div className="space-y-6">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">LLM Model</label>
        <input
          type="text"
          value={settings.llm_model}
          onChange={(e) => onChange('llm_model', e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
          placeholder="e.g. anthropic/claude-haiku-4.5"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">LLM Base URL</label>
        <input
          type="text"
          value={settings.llm_base_url}
          onChange={(e) => onChange('llm_base_url', e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
          placeholder="https://openrouter.ai/api/v1"
        />
        {isOpenAI && (
          <p className="mt-1 text-xs text-amber-600">
            Consider using OpenRouter for better model access and cost management.
          </p>
        )}
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Embedding Model</label>
        <input
          type="text"
          value={settings.embedding_model}
          readOnly
          className="w-full px-3 py-2 border border-gray-200 rounded-lg bg-gray-50 text-sm text-gray-600 cursor-not-allowed"
        />
        <p className="mt-1 text-xs text-gray-500">
          Embedding model is read-only. Changing it requires re-indexing all documents.
        </p>
      </div>

      <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
        <p className="text-sm text-amber-800">
          API keys are managed in <code className="bg-amber-100 px-1 rounded">.env</code> and are not shown here for security.
        </p>
      </div>
    </div>
  );
};
