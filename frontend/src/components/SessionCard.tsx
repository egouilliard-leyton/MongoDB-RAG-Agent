import React from 'react';
import { format } from 'date-fns';
import { QASession } from '../api/types';
import { StatusBadge } from './StatusBadge';

interface SessionCardProps {
  session: QASession;
  projectName?: string | null;
  isSelected?: boolean;
  onClick?: () => void;
  className?: string;
}

export const SessionCard: React.FC<SessionCardProps> = ({
  session,
  projectName,
  isSelected = false,
  onClick,
  className = '',
}) => {
  const companyName = session.metadata?.company_info?.company_name ?? null;
  const roundNumber = session.metadata?.round_number ?? null;
  const hasParentSession = !!session.metadata?.parent_session_id;

  const cardClasses = `
    bg-white border-2 rounded-lg p-4 transition-all cursor-pointer
    ${isSelected 
      ? 'border-blue-500 shadow-md bg-blue-50' 
      : 'border-gray-200 hover:border-gray-300 hover:shadow-sm'
    }
    ${className}
  `;

  return (
    <div
      className={cardClasses}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick?.();
        }
      }}
      aria-label={`Session: ${session.session_name}`}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-semibold text-gray-900 truncate">
            {session.session_name}
          </h4>
          {roundNumber && (
            <p className="text-xs text-gray-500 mt-0.5">
              Round {roundNumber}
            </p>
          )}
        </div>
        {hasParentSession && (
          <span
            className="ml-2 flex-shrink-0 text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded"
            title="Follow-up session"
          >
            Follow-up
          </span>
        )}
      </div>

      {/* Metadata */}
      <div className="space-y-2 text-xs mb-3">
        {projectName && (
          <div className="flex items-center justify-between">
            <span className="text-gray-600">Project:</span>
            <span className="font-medium text-gray-900 truncate ml-2" title={projectName}>
              {projectName}
            </span>
          </div>
        )}
        
        {companyName && (
          <div className="flex items-center justify-between">
            <span className="text-gray-600">Company:</span>
            <span className="font-medium text-gray-900 truncate ml-2" title={companyName}>
              {companyName}
            </span>
          </div>
        )}
        
        <div className="flex items-center justify-between">
          <span className="text-gray-600">Created:</span>
          <span className="font-medium text-gray-900">
            {format(new Date(session.created_at), 'MMM d, yyyy')}
          </span>
        </div>
      </div>

      {/* Status Badges */}
      <div className="flex flex-wrap gap-2 pt-2 border-t border-gray-200">
        {session.status && (
          <StatusBadge status={session.status} type="session" />
        )}
        {session.outcome_status && (
          <StatusBadge status={session.outcome_status} type="outcome" />
        )}
      </div>
    </div>
  );
};

