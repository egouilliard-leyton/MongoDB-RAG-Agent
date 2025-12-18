import React, { useState, useEffect } from 'react';
import { format } from 'date-fns';
import { useSession } from '../contexts/SessionContext';
import { Button } from './Button';
import { LoadingSpinner } from './LoadingSpinner';
import { ErrorAlert } from './ErrorAlert';
import type { QASession } from '../api/types';

interface SessionSelectorProps {
  onCreateNew?: () => void;
}

export const SessionSelector: React.FC<SessionSelectorProps> = ({
  onCreateNew,
}) => {
  const { currentSession, loadSession, listSessions, isLoading, error, clearError } =
    useSession();
  const [sessions, setSessions] = useState<QASession[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string>('');
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);

  useEffect(() => {
    loadSessions();
  }, []);

  useEffect(() => {
    if (currentSession) {
      setSelectedSessionId(currentSession._id);
    }
  }, [currentSession]);

  const loadSessions = async () => {
    setIsLoadingSessions(true);
    try {
      const sessionList = await listSessions(50, 0);
      setSessions(sessionList);
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

  const formatSessionDisplay = (session: QASession) => {
    const date = format(new Date(session.created_at), 'MMM d, yyyy');
    return `${session.session_name} - ${date}`;
  };

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Select Session
        </label>
        {isLoadingSessions ? (
          <LoadingSpinner size="sm" />
        ) : (
          <select
            value={selectedSessionId}
            onChange={(e) => setSelectedSessionId(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            disabled={isLoading}
          >
            <option value="">-- Select a session --</option>
            {sessions.map((session) => (
              <option key={session._id} value={session._id}>
                {formatSessionDisplay(session)}
              </option>
            ))}
          </select>
        )}
      </div>
      {currentSession && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
          <p className="text-sm font-medium text-blue-900">
            Current Session:
          </p>
          <p className="text-sm text-blue-700 mt-1">
            {currentSession.session_name}
          </p>
          <p className="text-xs text-blue-600 mt-1">
            Created: {format(new Date(currentSession.created_at), 'PPp')}
          </p>
        </div>
      )}
      <div className="flex space-x-2">
        <Button
          onClick={handleLoadSession}
          disabled={!selectedSessionId || isLoading}
          isLoading={isLoading}
          className="flex-1"
        >
          Load Session
        </Button>
        {onCreateNew && (
          <Button
            onClick={onCreateNew}
            variant="outline"
            disabled={isLoading}
            className="flex-1"
          >
            New Session
          </Button>
        )}
      </div>
      {error && <ErrorAlert message={error} onDismiss={clearError} />}
    </div>
  );
};

