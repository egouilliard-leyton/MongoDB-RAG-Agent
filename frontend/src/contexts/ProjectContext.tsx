import React, { createContext, useCallback, useContext, useState, ReactNode } from 'react';
import type { Project, CreateProjectRequest } from '../api/types';
import * as api from '../api/client';

interface ProjectContextType {
  currentProject: Project | null;
  isLoading: boolean;
  error: string | null;
  listProjects: () => Promise<Project[]>;
  loadProject: (projectId: string) => Promise<void>;
  createProject: (request: CreateProjectRequest) => Promise<Project>;
  updateStage: (projectId: string, mode: 'transition' | 'rollback' | 'force', event: string, toStage: string, note?: string) => Promise<Project>;
  uploadDocument: (projectId: string, file: File) => Promise<void>;
  clearError: () => void;
}

const ProjectContext = createContext<ProjectContextType | undefined>(undefined);

export const useProject = () => {
  const ctx = useContext(ProjectContext);
  if (!ctx) throw new Error('useProject must be used within a ProjectProvider');
  return ctx;
};

interface ProjectProviderProps {
  children: ReactNode;
}

export const ProjectProvider: React.FC<ProjectProviderProps> = ({ children }) => {
  const [currentProject, setCurrentProject] = useState<Project | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const listProjects = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      return await api.listProjects();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to list projects';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loadProject = useCallback(async (projectId: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const p = await api.getProject(projectId);
      setCurrentProject(p);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load project';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const createProject = useCallback(async (request: CreateProjectRequest) => {
    setIsLoading(true);
    setError(null);
    try {
      const p = await api.createProject(request);
      setCurrentProject(p);
      return p;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create project';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const updateStage = useCallback(
    async (projectId: string, mode: 'transition' | 'rollback' | 'force', event: string, toStage: string, note?: string) => {
      setIsLoading(true);
      setError(null);
      try {
        const p = await api.updateProjectStage(projectId, {
          mode,
          event,
          to_stage: toStage,
          note: note ?? null,
        });
        setCurrentProject(p);
        return p;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to update stage';
        setError(message);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const uploadDocument = useCallback(async (projectId: string, file: File) => {
    setIsLoading(true);
    setError(null);
    try {
      await api.uploadProjectDocument(projectId, file);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to upload document';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const clearError = useCallback(() => setError(null), []);

  const value: ProjectContextType = {
    currentProject,
    isLoading,
    error,
    listProjects,
    loadProject,
    createProject,
    updateStage,
    uploadDocument,
    clearError,
  };

  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
};


