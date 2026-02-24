import React, { useCallback, useEffect, useState } from 'react';
import { StageCard } from './StageCard';
import { StageEditor } from './StageEditor';
import * as api from '../../api/client';
import type { WorkflowListItem, WorkflowTemplate, WorkflowStage } from '../../api/types';

const STAGE_COLORS = ['#3B82F6', '#8B5CF6', '#F59E0B', '#10B981', '#EF4444', '#06B6D4', '#EC4899', '#F97316'];

export const WorkflowBuilder: React.FC = () => {
  const [workflows, setWorkflows] = useState<WorkflowListItem[]>([]);
  const [activeTemplate, setActiveTemplate] = useState<WorkflowTemplate | null>(null);
  const [editingStage, setEditingStage] = useState<WorkflowStage | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isDirty, setIsDirty] = useState(false);

  const loadWorkflows = useCallback(async () => {
    setIsLoading(true);
    try {
      const list = await api.listWorkflows();
      setWorkflows(list);
      // Load the default template, or the first one
      const defaultItem = list.find((w) => w.is_default) || list[0];
      if (defaultItem) {
        const template = await api.getWorkflow(defaultItem.id);
        setActiveTemplate(template);
      }
    } catch {
      // error handled by api client
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadWorkflows();
  }, [loadWorkflows]);

  const handleSelectWorkflow = async (id: string) => {
    try {
      const template = await api.getWorkflow(id);
      setActiveTemplate(template);
      setEditingStage(null);
      setIsDirty(false);
    } catch {
      // error handled by api client
    }
  };

  const handleCreateNew = async () => {
    try {
      const newTemplate = await api.createWorkflow({
        name: 'New Workflow',
        description: '',
        is_default: false,
        stages: [],
      });
      setWorkflows((prev) => [...prev, {
        id: newTemplate.id,
        name: newTemplate.name,
        description: newTemplate.description,
        is_default: newTemplate.is_default,
        stage_count: newTemplate.stages.length,
        created_at: newTemplate.created_at,
        updated_at: newTemplate.updated_at,
      }]);
      setActiveTemplate(newTemplate);
      setIsDirty(false);
    } catch {
      // error handled by api client
    }
  };

  const handleSave = async () => {
    if (!activeTemplate) return;
    setIsSaving(true);
    try {
      const updated = await api.updateWorkflow(activeTemplate.id, {
        name: activeTemplate.name,
        description: activeTemplate.description,
        is_default: activeTemplate.is_default,
        stages: activeTemplate.stages,
      });
      setActiveTemplate(updated);
      setIsDirty(false);
      // Update list item
      setWorkflows((prev) =>
        prev.map((w) =>
          w.id === updated.id
            ? { ...w, name: updated.name, description: updated.description, stage_count: updated.stages.length, updated_at: updated.updated_at }
            : w
        )
      );
    } catch {
      // error handled by api client
    } finally {
      setIsSaving(false);
    }
  };

  const handleDuplicate = async () => {
    if (!activeTemplate) return;
    try {
      const dup = await api.duplicateWorkflow(activeTemplate.id);
      setWorkflows((prev) => [...prev, {
        id: dup.id,
        name: dup.name,
        description: dup.description,
        is_default: dup.is_default,
        stage_count: dup.stages.length,
        created_at: dup.created_at,
        updated_at: dup.updated_at,
      }]);
      setActiveTemplate(dup);
      setIsDirty(false);
    } catch {
      // error handled by api client
    }
  };

  const handleAddStage = () => {
    if (!activeTemplate) return;
    const order = activeTemplate.stages.length;
    const newStage: WorkflowStage = {
      id: `stage-${Date.now()}`,
      label: `Stage ${order + 1}`,
      description: '',
      order,
      color: STAGE_COLORS[order % STAGE_COLORS.length],
      config: {
        system_prompt_append: null,
        search_params: { match_count: null, rrf_k: null, qa_history_match_count: null },
        metadata_fields: [],
        auto_advance: false,
      },
      transitions: [],
    };
    setActiveTemplate({
      ...activeTemplate,
      stages: [...activeTemplate.stages, newStage],
    });
    setIsDirty(true);
    setEditingStage(newStage);
  };

  const handleEditStage = (stage: WorkflowStage) => {
    setEditingStage(stage);
  };

  const handleDeleteStage = (stageId: string) => {
    if (!activeTemplate) return;
    const stages = activeTemplate.stages
      .filter((s) => s.id !== stageId)
      .map((s, i) => ({ ...s, order: i }));
    setActiveTemplate({ ...activeTemplate, stages });
    setIsDirty(true);
    if (editingStage?.id === stageId) setEditingStage(null);
  };

  const handleMoveStage = (stageId: string, direction: 'up' | 'down') => {
    if (!activeTemplate) return;
    const stages = [...activeTemplate.stages];
    const idx = stages.findIndex((s) => s.id === stageId);
    if (idx < 0) return;
    const swapIdx = direction === 'up' ? idx - 1 : idx + 1;
    if (swapIdx < 0 || swapIdx >= stages.length) return;
    [stages[idx], stages[swapIdx]] = [stages[swapIdx], stages[idx]];
    const reordered = stages.map((s, i) => ({ ...s, order: i }));
    setActiveTemplate({ ...activeTemplate, stages: reordered });
    setIsDirty(true);
  };

  const handleStageChange = (updated: WorkflowStage) => {
    if (!activeTemplate) return;
    const stages = activeTemplate.stages.map((s) => (s.id === updated.id ? updated : s));
    setActiveTemplate({ ...activeTemplate, stages });
    setEditingStage(updated);
    setIsDirty(true);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12 text-gray-500 text-sm">
        <svg className="animate-spin h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
        Loading workflows...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <select
            value={activeTemplate?.id ?? ''}
            onChange={(e) => handleSelectWorkflow(e.target.value)}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {workflows.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name} {w.is_default ? '(default)' : ''}
              </option>
            ))}
          </select>
          <button
            onClick={handleCreateNew}
            className="px-3 py-1.5 text-sm text-blue-600 border border-blue-300 rounded-md hover:bg-blue-50"
          >
            New Template
          </button>
        </div>
        <div className="flex items-center space-x-2">
          {isDirty && <span className="text-amber-500 text-xs">Unsaved</span>}
          <button
            onClick={handleDuplicate}
            disabled={!activeTemplate}
            className="px-3 py-1.5 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
          >
            Duplicate
          </button>
          <button
            onClick={handleSave}
            disabled={!activeTemplate || isSaving || !isDirty}
            className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {isSaving ? 'Saving...' : 'Save Template'}
          </button>
        </div>
      </div>

      {/* Template name/description edit */}
      {activeTemplate && (
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Template Name</label>
            <input
              type="text"
              value={activeTemplate.name}
              onChange={(e) => {
                setActiveTemplate({ ...activeTemplate, name: e.target.value });
                setIsDirty(true);
              }}
              className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Description</label>
            <input
              type="text"
              value={activeTemplate.description}
              onChange={(e) => {
                setActiveTemplate({ ...activeTemplate, description: e.target.value });
                setIsDirty(true);
              }}
              className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
      )}

      {/* Stage list + editor */}
      <div className="flex gap-4">
        {/* Stage list */}
        <div className="flex-1 space-y-2">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-semibold text-gray-900">Stages</h4>
            <button
              onClick={handleAddStage}
              disabled={!activeTemplate}
              className="text-xs text-blue-600 hover:text-blue-800 disabled:opacity-50"
            >
              + Add Stage
            </button>
          </div>
          {activeTemplate?.stages.length === 0 && (
            <p className="text-sm text-gray-500 text-center py-4">
              No stages yet. Click "Add Stage" to begin.
            </p>
          )}
          {activeTemplate?.stages.map((stage, i) => (
            <StageCard
              key={stage.id}
              stage={stage}
              onEdit={handleEditStage}
              onDelete={handleDeleteStage}
              onMoveUp={(id) => handleMoveStage(id, 'up')}
              onMoveDown={(id) => handleMoveStage(id, 'down')}
              isFirst={i === 0}
              isLast={i === (activeTemplate?.stages.length ?? 0) - 1}
            />
          ))}
        </div>

        {/* Stage editor panel */}
        {editingStage && activeTemplate && (
          <div className="w-96 flex-shrink-0">
            <StageEditor
              stage={editingStage}
              allStages={activeTemplate.stages}
              onChange={handleStageChange}
              onClose={() => setEditingStage(null)}
            />
          </div>
        )}
      </div>
    </div>
  );
};
