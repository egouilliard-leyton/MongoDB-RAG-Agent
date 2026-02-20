import React, { useState, useEffect, useMemo } from 'react';
import { format } from 'date-fns';
import { useSession } from '../contexts/SessionContext';
import { useProject } from '../contexts/ProjectContext';
import { Button } from './Button';
import { LoadingSpinner } from './LoadingSpinner';
import { ErrorAlert } from './ErrorAlert';
import { StatusBadge } from './StatusBadge';
import type { QASession, Project } from '../api/types';
import * as api from '../api/client';

interface SessionSelectorProps {
  onCreateNew?: () => void;
}

interface GroupedSessions {
  projectName: string | null;
  projectId: string | null;
  sessions: QASession[];
}

export const SessionSelector: React.FC<SessionSelectorProps> = ({
  onCreateNew,
}) => {
  const { currentSession, loadSession, listSessions, isLoading, error, clearError } =
    useSession();
  const { currentProject } = useProject();
  const [sessions, setSessions] = useState<QASession[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string>('');
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);
  const [isLoadingProjects, setIsLoadingProjects] = useState(false);

  useEffect(() => {
    loadSessions();
    loadProjects();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentProject?._id]);

  useEffect(() => {
    if (currentSession) {
      setSelectedSessionId(currentSession._id);
    }
  }, [currentSession]);

  const loadProjects = async () => {
    setIsLoadingProjects(true);
    try {
      const projectList = await api.listProjects();
      setProjects(projectList);
    } catch (err) {
      console.error('Failed to load projects:', err);
    } finally {
      setIsLoadingProjects(false);
    }
  };

  const loadSessions = async () => {
    setIsLoadingSessions(true);
    try {
      const sessionList = await listSessions(100, 0);
      const filtered = currentProject?._id
        ? sessionList.filter((s) => (s.project_id ?? null) === currentProject._id)
        : sessionList;
      setSessions(filtered);
    } catch (err) {
      // Error handled by context
    } finally {
      setIsLoadingSessions(false);
    }
  };

  const handleLoadSession = async () => {
    if (!selectedSessionId) return;
    clearError();
    try {
      await loadSession(selectedSessionId);
    } catch (err) {
      // Error handled by context
    }
  };

  // Create project ID to name mapping
  const projectMap = useMemo(() => {
    const map = new Map<string, string>();
    projects.forEach((p) => {
      map.set(p._id, p.name);
    });
    return map;
  }, [projects]);

  // Group sessions by project
  const groupedSessions = useMemo(() => {
    const groups = new Map<string | null, GroupedSessions>();
    
    sessions.forEach((session) => {
      const projectId = session.project_id ?? null;
      const projectName = projectId ? projectMap.get(projectId) ?? 'Unknown Project' : null;
      
      if (!groups.has(projectId)) {
        groups.set(projectId, {
          projectName,
          projectId,
          sessions: [],
        });
      }
      groups.get(projectId)!.sessions.push(session);
    });

    // Sort sessions within each group by created_at (newest first)
    groups.forEach((group) => {
      group.sessions.sort((a, b) => 
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
    });

    // Convert to array and sort: null (no project) last, then by project name
    return Array.from(groups.values()).sort((a, b) => {
      if (a.projectId === null && b.projectId !== null) return 1;
      if (a.projectId !== null && b.projectId === null) return -1;
      if (a.projectId === null && b.projectId === null) return 0;
      return (a.projectName ?? '').localeCompare(b.projectName ?? '');
    });
  }, [sessions, projectMap]);

  const getCompanyName = (session: QASession): string | null => {
    return session.metadata?.company_info?.company_name ?? null;
  };

  const getRoundNumber = (session: QASession): number | null => {
    return session.metadata?.round_number ?? null;
  };

  const hasParentSession = (session: QASession): boolean => {
    return !!session.metadata?.parent_session_id;
  };

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Select Session
        </label>
        {isLoadingSessions || isLoadingProjects ? (
          <LoadingSpinner size="sm" />
        ) : (
          <select
            value={selectedSessionId}
            onChange={(e) => setSelectedSessionId(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
            disabled={isLoading}
          >
            <option value="">-- Select a session --</option>
            {groupedSessions.map((group) => (
              <optgroup
                key={group.projectId ?? 'no-project'}
                label={group.projectName ?? 'No Project'}
              >
                {group.sessions.map((session) => {
                  const companyName = getCompanyName(session);
                  const roundNumber = getRoundNumber(session);
                  const date = format(new Date(session.created_at), 'MMM d, yyyy');
                  
                  let displayText = session.session_name;
                  const parts: string[] = [];
                  
                  if (roundNumber) {
                    parts.push(`Round ${roundNumber}`);
                  }
                  if (companyName) {
                    parts.push(companyName);
                  }
                  if (hasParentSession(session)) {
                    parts.push('(Follow-up)');
                  }
                  
                  if (parts.length > 0) {
                    displayText += ` - ${parts.join(', ')}`;
                  }
                  displayText += ` - ${date}`;
                  
                  return (
                    <option key={session._id} value={session._id}>
                      {displayText}
                    </option>
                  );
                })}
              </optgroup>
            ))}
          </select>
        )}
      </div>
      
      {currentSession && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 space-y-3">
          <div>
            <p className="text-sm font-medium text-blue-900 mb-2">
              Current Session
            </p>
            <p className="text-sm font-semibold text-blue-800">
              {currentSession.session_name}
            </p>
          </div>
          
          <div className="space-y-2 text-xs">
            {currentProject && (
              <div className="flex items-center justify-between">
                <span className="text-blue-600">Project:</span>
                <span className="font-medium text-blue-800">{currentProject.name}</span>
              </div>
            )}
            
            {getCompanyName(currentSession) && (
              <div className="flex items-center justify-between">
                <span className="text-blue-600">Company:</span>
                <span className="font-medium text-blue-800">
                  {getCompanyName(currentSession)}
                </span>
              </div>
            )}
            
            {getRoundNumber(currentSession) && (
              <div className="flex items-center justify-between">
                <span className="text-blue-600">Round:</span>
                <span className="font-medium text-blue-800">
                  {getRoundNumber(currentSession)}
                </span>
              </div>
            )}
            
            {hasParentSession(currentSession) && (
              <div className="flex items-center justify-between">
                <span className="text-blue-600">Type:</span>
                <span className="font-medium text-blue-800">Follow-up Session</span>
              </div>
            )}
            
            <div className="flex items-center justify-between">
              <span className="text-blue-600">Created:</span>
              <span className="font-medium text-blue-800">
                {format(new Date(currentSession.created_at), 'PPp')}
              </span>
            </div>
          </div>
          
          <div className="flex flex-wrap gap-2 pt-2 border-t border-blue-200">
            {currentSession.status && (
              <StatusBadge status={currentSession.status} type="session" />
            )}
            {currentSession.outcome_status && (
              <StatusBadge status={currentSession.outcome_status} type="outcome" />
            )}
          </div>
        </div>
      )}
      
      <div className="flex flex-col space-y-2">
        <Button
          onClick={handleLoadSession}
          disabled={!selectedSessionId || isLoading}
          isLoading={isLoading}
        >
          Load Session
        </Button>
        {onCreateNew && (
          <Button
            onClick={onCreateNew}
            variant="outline"
            disabled={isLoading}
          >
            New Session
          </Button>
        )}
      </div>
      {error && <ErrorAlert message={error} onDismiss={clearError} />}
    </div>
  );
};

