import React, { useEffect, useState } from 'react';
import { useProject } from '../contexts/ProjectContext';
import { Button } from './Button';
import { LoadingSpinner } from './LoadingSpinner';
import { ErrorAlert } from './ErrorAlert';
import type { Project } from '../api/types';

interface ProjectSelectorProps {
  onCreateNew?: () => void;
}

export const ProjectSelector: React.FC<ProjectSelectorProps> = ({ onCreateNew }) => {
  const { currentProject, listProjects, loadProject, isLoading, error, clearError } = useProject();
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [isLoadingProjects, setIsLoadingProjects] = useState(false);

  useEffect(() => {
    void refresh();
  }, []);

  useEffect(() => {
    if (currentProject) setSelectedProjectId(currentProject._id);
  }, [currentProject?._id]);

  const refresh = async () => {
    setIsLoadingProjects(true);
    try {
      const list = await listProjects();
      setProjects(list);
    } catch {
      // handled in context
    } finally {
      setIsLoadingProjects(false);
    }
  };

  const handleLoad = async () => {
    if (!selectedProjectId) return;
    clearError();
    try {
      await loadProject(selectedProjectId);
    } catch {
      // handled in context
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Select Project</label>
        {isLoadingProjects ? (
          <LoadingSpinner size="sm" />
        ) : (
          <select
            value={selectedProjectId}
            onChange={(e) => setSelectedProjectId(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            disabled={isLoading}
          >
            <option value="">-- Select a project --</option>
            {projects.map((p) => (
              <option key={p._id} value={p._id}>
                {p.name}
              </option>
            ))}
          </select>
        )}
      </div>

      {currentProject && (
        <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-3">
          <p className="text-sm font-medium text-indigo-900">Current Project:</p>
          <p className="text-sm text-indigo-700 mt-1">{currentProject.name}</p>
          <p className="text-xs text-indigo-600 mt-1">
            Stage: {currentProject.stage?.key}
          </p>
        </div>
      )}

      <div className="flex flex-col space-y-2">
        <Button onClick={handleLoad} disabled={!selectedProjectId || isLoading} isLoading={isLoading}>
          Load Project
        </Button>
        {onCreateNew && (
          <Button onClick={onCreateNew} variant="outline" disabled={isLoading}>
            New Project
          </Button>
        )}
      </div>

      {error && <ErrorAlert message={error} onDismiss={clearError} />}
    </div>
  );
};


