import React, { useEffect, useState, useCallback } from 'react';
import { useSettings } from '../contexts/SettingsContext';
import { PromptEditor } from '../components/settings/PromptEditor';
import { PromptVersionHistory } from '../components/settings/PromptVersionHistory';
import { RAGParametersPanel } from '../components/settings/RAGParametersPanel';
import { ModelConfigPanel } from '../components/settings/ModelConfigPanel';
import { StageDefaultsPanel } from '../components/settings/StageDefaultsPanel';
import { ParameterSuggestions } from '../components/settings/ParameterSuggestions';
import { PromptPlayground } from '../components/prompt-playground/PromptPlayground';
import { WorkflowBuilder } from '../components/workflow-builder/WorkflowBuilder';
import type { SettingsUpdateRequest, GlobalSettings, StageDefaultConfig } from '../api/types';

type SettingsTab = 'prompts' | 'rag' | 'model' | 'stage-defaults' | 'workflows' | 'playground';

const TABS: { key: SettingsTab; label: string }[] = [
  { key: 'prompts', label: 'Prompts' },
  { key: 'rag', label: 'RAG Parameters' },
  { key: 'model', label: 'Model Config' },
  { key: 'stage-defaults', label: 'Stage Defaults' },
  { key: 'workflows', label: 'Workflow Builder' },
  { key: 'playground', label: 'Playground' },
];

export const SettingsPage: React.FC = () => {
  const {
    currentSettings,
    versionHistory,
    isLoading,
    isSaving,
    error,
    saveSettings,
    loadHistory,
    restoreVersion,
    clearError,
  } = useSettings();

  const [activeTab, setActiveTab] = useState<SettingsTab>('prompts');
  const [dirty, setDirty] = useState<SettingsUpdateRequest>({});
  const [showHistory, setShowHistory] = useState(false);

  const isDirty = Object.keys(dirty).length > 0;

  // Merge current settings with dirty overrides for display
  const mergedSettings: GlobalSettings | null = currentSettings
    ? {
        ...currentSettings,
        ...dirty,
        stage_defaults: dirty.stage_defaults
          ? {
              system_prompt_append:
                dirty.stage_defaults.system_prompt_append !== undefined
                  ? dirty.stage_defaults.system_prompt_append ?? null
                  : currentSettings.stage_defaults.system_prompt_append,
              search_params: {
                ...currentSettings.stage_defaults.search_params,
                ...(dirty.stage_defaults.search_params ?? {}),
              },
            }
          : currentSettings.stage_defaults,
      }
    : null;

  const handleFieldChange = useCallback((field: string, value: unknown) => {
    if (field.startsWith('stage_defaults.')) {
      const subField = field.replace('stage_defaults.', '');
      setDirty((prev): SettingsUpdateRequest => {
        const prevSD = prev.stage_defaults ?? {};
        if (subField.startsWith('search_params.')) {
          const paramKey = subField.replace('search_params.', '') as keyof import('../api/types').SearchParamsOverride;
          const prevSP: Partial<import('../api/types').SearchParamsOverride> = prevSD.search_params ?? {};
          return {
            ...prev,
            stage_defaults: {
              ...prevSD,
              search_params: {
                match_count: prevSP.match_count ?? null,
                rrf_k: prevSP.rrf_k ?? null,
                qa_history_match_count: prevSP.qa_history_match_count ?? null,
                [paramKey]: value as number | null,
              },
            },
          };
        }
        return {
          ...prev,
          stage_defaults: {
            ...prevSD,
            [subField]: value,
          } as Partial<StageDefaultConfig>,
        };
      });
    } else {
      setDirty((prev) => ({ ...prev, [field]: value }));
    }
  }, []);

  const handleSave = async () => {
    if (!isDirty) return;
    try {
      await saveSettings(dirty);
      setDirty({});
    } catch {
      // error displayed via context
    }
  };

  const handleTabChange = (tab: SettingsTab) => {
    if (isDirty) {
      const confirmed = window.confirm('You have unsaved changes. Switch tab anyway?');
      if (!confirmed) return;
    }
    setActiveTab(tab);
  };

  const handleShowHistory = async () => {
    await loadHistory();
    setShowHistory(true);
  };

  // Clear dirty state after settings reload (e.g. version restore)
  useEffect(() => {
    setDirty({});
  }, [currentSettings?.version]);

  if (isLoading && !currentSettings) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <div className="flex items-center justify-center py-12">
          <div className="flex items-center space-x-3 text-gray-500">
            <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            <span>Loading settings...</span>
          </div>
        </div>
      </div>
    );
  }

  if (error && !currentSettings) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-sm text-red-800">{error}</p>
          <button
            onClick={clearError}
            className="mt-2 text-sm text-red-600 hover:text-red-500 font-medium"
          >
            Dismiss
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
          {currentSettings && (
            <p className="text-xs text-gray-500 mt-1">
              Version {currentSettings.version} &middot; Last updated{' '}
              {new Date(currentSettings.updated_at).toLocaleString()}
            </p>
          )}
        </div>
        <div className="flex items-center space-x-3">
          {isDirty && <span className="text-amber-500 text-sm font-medium">Unsaved changes</span>}
          {error && (
            <span className="text-red-500 text-sm">{error}</span>
          )}
          <button
            onClick={handleSave}
            disabled={!isDirty || isSaving}
            className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSaving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>

      {/* Tab navigation */}
      <div className="border-b border-gray-200">
        <nav className="flex space-x-1 -mb-px">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => handleTabChange(tab.key)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.key
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        {activeTab === 'prompts' && mergedSettings && (
          <div className="space-y-6">
            <PromptEditor
              value={mergedSettings.main_system_prompt}
              onChange={(v) => handleFieldChange('main_system_prompt', v)}
              label="Main System Prompt"
              placeholder="The primary system prompt used for all queries..."
              rows={8}
            />
            <PromptEditor
              value={mergedSettings.follow_up_context_prompt}
              onChange={(v) => handleFieldChange('follow_up_context_prompt', v)}
              label="Follow-up Context Prompt"
              placeholder="Prompt template for follow-up questions with history..."
              rows={6}
            />
            <PromptEditor
              value={mergedSettings.qa_history_prompt}
              onChange={(v) => handleFieldChange('qa_history_prompt', v)}
              label="Q&A History Prompt"
              placeholder="Prompt template for including Q&A history context..."
              rows={6}
            />
            <div className="flex items-center justify-between pt-4 border-t border-gray-200">
              <button
                onClick={handleShowHistory}
                className="text-sm text-blue-600 hover:text-blue-800 font-medium"
              >
                Version History
              </button>
            </div>
            <ParameterSuggestions />
          </div>
        )}

        {activeTab === 'rag' && mergedSettings && (
          <RAGParametersPanel
            settings={mergedSettings}
            onChange={(field, value) => handleFieldChange(field as string, value)}
            isDirty={isDirty}
          />
        )}

        {activeTab === 'model' && mergedSettings && (
          <ModelConfigPanel
            settings={mergedSettings}
            onChange={(field, value) => handleFieldChange(field as string, value)}
          />
        )}

        {activeTab === 'stage-defaults' && mergedSettings && (
          <StageDefaultsPanel
            settings={mergedSettings}
            onChange={handleFieldChange}
          />
        )}

        {activeTab === 'workflows' && <WorkflowBuilder />}

        {activeTab === 'playground' && (
          <PromptPlayground initialPrompt={currentSettings?.main_system_prompt} />
        )}
      </div>

      {/* Version History Modal */}
      {showHistory && currentSettings && (
        <PromptVersionHistory
          versions={versionHistory}
          currentVersion={currentSettings.version}
          onRestore={restoreVersion}
          onClose={() => setShowHistory(false)}
        />
      )}
    </div>
  );
};
