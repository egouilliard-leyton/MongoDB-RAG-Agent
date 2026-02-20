import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import type { QASession } from '../api/types';
import * as api from '../api/client';

interface CreateSessionOptions {
  companyInfo?: string;
  projectId?: string | null;
  taxOfficeId?: number | null;
  region?: string | null;
}

interface SessionContextType {
  currentSession: QASession | null;
  userRole: 'junior' | 'senior';
  isLoading: boolean;
  error: string | null;
  createSession: (sessionName: string, options?: CreateSessionOptions) => Promise<void>;
  loadSession: (sessionId: string) => Promise<void>;
  refreshCurrentSession: () => Promise<void>;
  loadParentSession: () => Promise<void>;
  listSessions: (limit?: number, skip?: number) => Promise<QASession[]>;
  updateUserRole: (role: 'junior' | 'senior') => void;
  markOutcome: (outcome: 'successful' | 'unsuccessful') => Promise<void>;
  clearError: () => void;
}

const SessionContext = createContext<SessionContextType | undefined>(undefined);

export const useSession = () => {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error('useSession must be used within a SessionProvider');
  }
  return context;
};

interface SessionProviderProps {
  children: ReactNode;
}

export const SessionProvider: React.FC<SessionProviderProps> = ({ children }) => {
  const [currentSession, setCurrentSession] = useState<QASession | null>(null);
  const [userRole, setUserRole] = useState<'junior' | 'senior'>('junior');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const createSession = useCallback(async (sessionName: string, options?: CreateSessionOptions) => {
    setIsLoading(true);
    setError(null);
    try {
      const session = await api.createSession({
        name: sessionName,
        user_role: userRole,
        company_info: options?.companyInfo,
        project_id: options?.projectId ?? null,
        tax_office_id: options?.taxOfficeId ?? null,
        region: options?.region ?? null,
      });
      setCurrentSession(session);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create session';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [userRole]);

  const loadSession = useCallback(async (sessionId: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const session = await api.getSession(sessionId);
      setCurrentSession(session);
      setUserRole(session.user_role);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load session';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const refreshCurrentSession = useCallback(async () => {
    if (!currentSession?._id) return;
    // Keep this lightweight: no loading spinner, just a silent refresh of metadata.
    try {
      const session = await api.getSession(currentSession._id);
      setCurrentSession(session);
    } catch (err) {
      // Non-fatal: the main Q&A flow should not fail because a refresh failed.
      console.warn('[SessionContext] Failed to refresh current session', err);
    }
  }, [currentSession?._id]);

  const loadParentSession = useCallback(async () => {
    if (!currentSession?.metadata?.parent_session_id) {
      throw new Error('Current session has no parent session');
    }
    await loadSession(currentSession.metadata.parent_session_id);
  }, [currentSession, loadSession]);

  const listSessions = useCallback(async (limit?: number, skip?: number) => {
    setIsLoading(true);
    setError(null);
    try {
      return await api.listSessions(limit, skip);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to list sessions';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const updateUserRole = useCallback((role: 'junior' | 'senior') => {
    setUserRole(role);
  }, []);

  const markOutcome = useCallback(async (outcome: 'successful' | 'unsuccessful') => {
    if (!currentSession) {
      throw new Error('No session loaded');
    }
    setIsLoading(true);
    setError(null);
    try {
      await api.markSessionOutcome(currentSession._id, outcome);
      const updatedSession = await api.getSession(currentSession._id);
      setCurrentSession(updatedSession);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to mark outcome';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [currentSession]);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const value: SessionContextType = {
    currentSession,
    userRole,
    isLoading,
    error,
    createSession,
    loadSession,
    refreshCurrentSession,
    loadParentSession,
    listSessions,
    updateUserRole,
    markOutcome,
    clearError,
  };

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
};

