import React, { useEffect, useState, useMemo } from 'react';
import { useProject } from '../contexts/ProjectContext';
import * as api from '../api/client';
import { Button } from './Button';
import { LoadingSpinner } from './LoadingSpinner';
import { ErrorAlert } from './ErrorAlert';

// Stage definitions matching project_stages.py
interface Stage {
  key: string;
  label: string;
  is_terminal: boolean;
}

const STAGES: Record<string, Stage> = {
  prep_docs: { key: 'prep_docs', label: 'Prepare documents', is_terminal: false },
  submit_first_instance: { key: 'submit_first_instance', label: 'Submit (1st instance)', is_terminal: false },
  await_response: { key: 'await_response', label: 'Await response', is_terminal: false },
  inquiry_check: { key: 'inquiry_check', label: 'Inquiry check', is_terminal: false },
  prepare_answers: { key: 'prepare_answers', label: 'Prepare answers', is_terminal: false },
  first_instance_outcome: { key: 'first_instance_outcome', label: '1st instance outcome', is_terminal: false },
  appeal_second_instance: { key: 'appeal_second_instance', label: 'Appeal (2nd instance)', is_terminal: false },
  second_instance_decision: { key: 'second_instance_decision', label: '2nd instance decision', is_terminal: false },
  complaint_wsa: { key: 'complaint_wsa', label: 'Complaint to WSA', is_terminal: false },
  wsa_decision: { key: 'wsa_decision', label: 'WSA decision', is_terminal: false },
  complaint_nsa: { key: 'complaint_nsa', label: 'Complaint to NSA', is_terminal: false },
  nsa_decision: { key: 'nsa_decision', label: 'NSA decision', is_terminal: false },
  end_refund: { key: 'end_refund', label: 'End: refund', is_terminal: true },
  end_no_appeal: { key: 'end_no_appeal', label: 'End: no appeal', is_terminal: true },
  return_reconsideration: { key: 'return_reconsideration', label: 'Return for reconsideration', is_terminal: false },
};

type StageStatus = 'completed' | 'current' | 'available' | 'terminal' | 'inactive';

interface StageNode {
  stage: Stage;
  status: StageStatus;
  isRollbackTarget: boolean;
  transitionEvent?: string;
}

export const StageWorkflowVisualization: React.FC = () => {
  const { currentProject, updateStage, isLoading, error, clearError } = useProject();
  const [options, setOptions] = useState<{
    next_actions: Array<{ event: string; to: string; to_label: string }>;
    rollback_targets: string[];
  } | null>(null);
  const [isLoadingOptions, setIsLoadingOptions] = useState(false);

  useEffect(() => {
    void loadOptions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentProject?._id, currentProject?.stage?.key]);

  const loadOptions = async () => {
    if (!currentProject?._id) {
      setOptions(null);
      return;
    }
    setIsLoadingOptions(true);
    try {
      const data = await api.getProjectStageOptions(currentProject._id);
      setOptions(data);
    } catch {
      // errors are surfaced via global API interceptor; keep panel resilient
      setOptions(null);
    } finally {
      setIsLoadingOptions(false);
    }
  };

  // Determine which stages have been completed based on stage_history
  const completedStages = useMemo(() => {
    if (!currentProject?.stage_history) return new Set<string>();
    const completed = new Set<string>();
    currentProject.stage_history.forEach((entry) => {
      if (entry.to) {
        completed.add(entry.to);
      }
    });
    return completed;
  }, [currentProject?.stage_history]);

  // Get available next stages
  const availableNextStages = useMemo(() => {
    if (!options?.next_actions) return new Set<string>();
    return new Set(options.next_actions.map((a) => a.to));
  }, [options?.next_actions]);

  // Get rollback targets
  const rollbackTargets = useMemo(() => {
    if (!options?.rollback_targets) return new Set<string>();
    return new Set(options.rollback_targets);
  }, [options?.rollback_targets]);

  // Build stage nodes with status
  const stageNodes = useMemo(() => {
    if (!currentProject) return [];

    const currentStageKey = currentProject.stage?.key || 'prep_docs';
    const nodes: StageNode[] = [];

    Object.values(STAGES).forEach((stage) => {
      let status: StageStatus = 'inactive';
      const isCurrent = stage.key === currentStageKey;
      const isCompleted = completedStages.has(stage.key);
      const isAvailable = availableNextStages.has(stage.key);
      const isRollbackTarget = rollbackTargets.has(stage.key);

      if (isCurrent) {
        status = 'current';
      } else if (stage.is_terminal && isCompleted) {
        status = 'terminal';
      } else if (isCompleted) {
        status = 'completed';
      } else if (isAvailable) {
        status = 'available';
      } else if (stage.is_terminal) {
        status = 'terminal';
      }

      // Find transition event for available stages
      const transitionEvent = options?.next_actions?.find((a) => a.to === stage.key)?.event;

      nodes.push({
        stage,
        status,
        isRollbackTarget,
        transitionEvent,
      });
    });

    return nodes;
  }, [currentProject, completedStages, availableNextStages, rollbackTargets, options]);

  if (!currentProject) return null;

  const getStageColorClasses = (status: StageStatus, _isRollbackTarget: boolean) => {
    const baseClasses = 'border-l-4 pl-4 py-2 rounded-r transition-all';
    
    switch (status) {
      case 'current':
        return `${baseClasses} border-blue-500 bg-blue-50 text-blue-900 font-semibold`;
      case 'completed':
        return `${baseClasses} border-gray-400 bg-gray-50 text-gray-700`;
      case 'available':
        return `${baseClasses} border-green-500 bg-green-50 text-green-900 hover:bg-green-100 cursor-pointer`;
      case 'terminal':
        return `${baseClasses} border-red-500 bg-red-50 text-red-900`;
      default:
        return `${baseClasses} border-gray-300 bg-white text-gray-500`;
    }
  };

  const handleStageClick = (node: StageNode) => {
    if (node.status === 'available' && node.transitionEvent) {
      updateStage(currentProject._id, 'transition', node.transitionEvent, node.stage.key);
    } else if (node.isRollbackTarget) {
      updateStage(currentProject._id, 'rollback', 'to', node.stage.key, 'Rollback');
    }
  };

  return (
    <div className="border-t border-gray-200 pt-4 space-y-4">
      <h3 className="text-sm font-medium text-gray-700">Stage Workflow</h3>

      {isLoadingOptions ? (
        <LoadingSpinner size="sm" />
      ) : (
        <div className="space-y-0 max-h-96 overflow-y-auto">
          {stageNodes.map((node, index) => {
            const canInteract = node.status === 'available' || node.isRollbackTarget;
            const isLast = index === stageNodes.length - 1;
            
            return (
              <div key={node.stage.key} className="relative">
                {/* Timeline connector line */}
                {!isLast && (
                  <div
                    className={`absolute left-2 top-8 w-0.5 h-full ${
                      node.status === 'current'
                        ? 'bg-blue-300'
                        : node.status === 'completed'
                        ? 'bg-gray-300'
                        : 'bg-gray-200'
                    }`}
                    style={{ height: 'calc(100% - 0.5rem)' }}
                  />
                )}
                
                {/* Stage node */}
                <div
                  className={`relative ml-6 ${getStageColorClasses(node.status, node.isRollbackTarget)} ${
                    canInteract ? 'hover:shadow-md' : ''
                  }`}
                  onClick={canInteract ? () => handleStageClick(node) : undefined}
                  title={node.stage.is_terminal ? 'Terminal stage' : node.stage.label}
                >
                  {/* Timeline dot */}
                  <div
                    className={`absolute -left-7 top-3 w-3 h-3 rounded-full border-2 ${
                      node.status === 'current'
                        ? 'bg-blue-500 border-blue-600 ring-2 ring-blue-200'
                        : node.status === 'completed'
                        ? 'bg-gray-400 border-gray-500'
                        : node.status === 'available'
                        ? 'bg-green-500 border-green-600'
                        : node.status === 'terminal'
                        ? 'bg-red-500 border-red-600'
                        : 'bg-white border-gray-300'
                    }`}
                  />
                  
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="text-sm font-medium">{node.stage.label}</div>
                      {node.status === 'current' && (
                        <div className="text-xs text-blue-600 mt-0.5 font-medium">● Current</div>
                      )}
                      {node.status === 'completed' && node.stage.key !== currentProject.stage?.key && (
                        <div className="text-xs text-gray-500 mt-0.5">✓ Completed</div>
                      )}
                      {node.status === 'available' && (
                        <div className="text-xs text-green-600 mt-0.5 font-medium">
                          → Available • Click to transition
                        </div>
                      )}
                      {node.isRollbackTarget && node.status !== 'available' && (
                        <div className="text-xs text-orange-600 mt-0.5">
                          ↶ Rollback available
                        </div>
                      )}
                      {node.status === 'terminal' && node.stage.key !== currentProject.stage?.key && (
                        <div className="text-xs text-red-600 mt-0.5">● Terminal</div>
                      )}
                    </div>
                    {canInteract && (
                      <div className="ml-2">
                        {node.status === 'available' ? (
                          <svg
                            className="w-4 h-4 text-green-600"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M9 5l7 7-7 7"
                            />
                          </svg>
                        ) : node.isRollbackTarget ? (
                          <svg
                            className="w-4 h-4 text-orange-600"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M15 19l-7-7 7-7"
                            />
                          </svg>
                        ) : null}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {options?.next_actions?.length ? (
        <div className="pt-2 border-t border-gray-200">
          <p className="text-xs text-gray-500 mb-2">Quick actions:</p>
          <div className="flex flex-wrap gap-2">
            {options.next_actions.map((action) => (
              <Button
                key={`${action.event}:${action.to}`}
                size="sm"
                variant="outline"
                disabled={isLoading}
                onClick={() => updateStage(currentProject._id, 'transition', action.event, action.to)}
                title={`Event: ${action.event}`}
                className="text-xs"
              >
                {action.to_label}
              </Button>
            ))}
          </div>
        </div>
      ) : null}

      {options?.rollback_targets?.length ? (
        <div className="pt-2 border-t border-gray-200">
          <p className="text-xs text-gray-500 mb-2">Rollback options:</p>
          <div className="flex flex-wrap gap-2">
            {options.rollback_targets.slice(0, 6).map((stageKey) => {
              const stage = STAGES[stageKey];
              return (
                <Button
                  key={`rb:${stageKey}`}
                  size="sm"
                  variant="outline"
                  disabled={isLoading}
                  onClick={() => updateStage(currentProject._id, 'rollback', 'to', stageKey, 'Rollback')}
                  title="Rollback to previous stage"
                  className="text-xs border-orange-300 text-orange-700 hover:bg-orange-50"
                >
                  {stage?.label || stageKey}
                </Button>
              );
            })}
          </div>
        </div>
      ) : null}

      {error && <ErrorAlert message={error} onDismiss={clearError} />}
    </div>
  );
};

