import React, { useState, useCallback } from 'react';
import { useSession } from '../contexts/SessionContext';
import { Button } from './Button';
import { FollowUpSessionCreator } from './FollowUpSessionCreator';
import type { QASession } from '../api/types';

interface OutcomeStatusProps {
  className?: string;
}

export const OutcomeStatus: React.FC<OutcomeStatusProps> = ({ className = '' }) => {
  const { currentSession, markOutcome, loadSession, isLoading } = useSession();
  const [isUpdating, setIsUpdating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showFollowUpCreator, setShowFollowUpCreator] = useState(false);

  if (!currentSession) {
    return null;
  }

  const outcomeStatus = currentSession.outcome_status;
  const isPending = !outcomeStatus || outcomeStatus === 'pending';
  const isSuccessful = outcomeStatus === 'successful';
  const isUnsuccessful = outcomeStatus === 'unsuccessful';

  const handleMarkSuccessful = useCallback(async () => {
    setIsUpdating(true);
    setError(null);
    try {
      await markOutcome('successful');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to mark as successful';
      setError(message);
    } finally {
      setIsUpdating(false);
    }
  }, [markOutcome]);

  const handleMarkUnsuccessful = useCallback(async () => {
    // Show confirmation for marking as unsuccessful
    const confirmed = window.confirm(
      'Are you sure you want to mark this session as unsuccessful? ' +
      'This will indicate that the answers did not work as expected.'
    );
    
    if (!confirmed) {
      return;
    }

    setIsUpdating(true);
    setError(null);
    try {
      await markOutcome('unsuccessful');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to mark as unsuccessful';
      setError(message);
    } finally {
      setIsUpdating(false);
    }
  }, [markOutcome]);

  const handleCreateFollowUp = useCallback(() => {
    setShowFollowUpCreator(true);
  }, []);

  const handleFollowUpSuccess = useCallback(async (newSession: QASession) => {
    setShowFollowUpCreator(false);
    // Load the new follow-up session
    await loadSession(newSession._id);
  }, [loadSession]);

  const handleFollowUpCancel = useCallback(() => {
    setShowFollowUpCreator(false);
  }, []);

  const getStatusBadge = () => {
    if (isSuccessful) {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
          <svg
            className="w-4 h-4 mr-1"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 13l4 4L19 7"
            />
          </svg>
          Successful
        </span>
      );
    }
    if (isUnsuccessful) {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
          <svg
            className="w-4 h-4 mr-1"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
          Unsuccessful
        </span>
      );
    }
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
        <svg
          className="w-4 h-4 mr-1 animate-spin"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        Pending
      </span>
    );
  };

  return (
    <div className={`space-y-3 ${className}`}>
      <div>
        <h3 className="text-sm font-medium text-gray-700 mb-2">
          Outcome Status
        </h3>
        <div className="flex items-center space-x-2">
          {getStatusBadge()}
        </div>
      </div>

      <div className="flex flex-col space-y-2">
        {!isSuccessful && (
          <Button
            onClick={handleMarkSuccessful}
            disabled={isUpdating || isLoading}
            isLoading={isUpdating && !isUnsuccessful}
            size="sm"
            variant="primary"
          >
            Mark as Successful
          </Button>
        )}
        
        {!isUnsuccessful && (
          <Button
            onClick={handleMarkUnsuccessful}
            disabled={isUpdating || isLoading}
            isLoading={isUpdating && !isSuccessful}
            size="sm"
            variant="danger"
          >
            It didn't work
          </Button>
        )}

        {(isUnsuccessful || isPending) && (
          <Button
            onClick={handleCreateFollowUp}
            disabled={isUpdating || isLoading}
            size="sm"
            variant="secondary"
          >
            Create Follow-Up Session
          </Button>
        )}
      </div>

      {error && (
        <p className="text-sm text-red-600">{error}</p>
      )}

      {showFollowUpCreator && currentSession && (
        <FollowUpSessionCreator
          parentSessionId={currentSession._id}
          onSuccess={handleFollowUpSuccess}
          onCancel={handleFollowUpCancel}
        />
      )}
    </div>
  );
};

