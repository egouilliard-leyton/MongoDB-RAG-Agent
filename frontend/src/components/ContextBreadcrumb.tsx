import React from 'react';
import { useSession } from '../contexts/SessionContext';
import { useProject } from '../contexts/ProjectContext';
import { getStageLabel } from '../utils/stageLabels';

interface BreadcrumbSegment {
  label: string;
  onClick?: () => void;
  isActive?: boolean;
}

export const ContextBreadcrumb: React.FC = () => {
  const { currentSession, refreshCurrentSession } = useSession();
  const { currentProject, loadProject } = useProject();

  const segments: BreadcrumbSegment[] = [];

  // Company name: from session metadata or project company_info
  const companyName = 
    currentSession?.metadata?.company_info?.company_name ||
    currentProject?.company_info?.company_name ||
    null;

  if (companyName) {
    segments.push({
      label: companyName,
      isActive: false,
    });
  }

  // Project name
  if (currentProject) {
    segments.push({
      label: currentProject.name,
      onClick: () => {
        // Could trigger project selector or highlight project in sidebar
        // For now, just reload the project to ensure it's selected
        if (currentProject._id) {
          loadProject(currentProject._id);
        }
      },
      isActive: false,
    });
  }

  // Stage label
  if (currentProject?.stage?.key) {
    const stageLabel = getStageLabel(currentProject.stage.key);
    segments.push({
      label: stageLabel,
      isActive: true, // Current stage is always active
    });
  }

  // Session name
  if (currentSession) {
    segments.push({
      label: currentSession.session_name,
      onClick: () => {
        // Refresh the current session to ensure it's up to date
        refreshCurrentSession();
      },
      isActive: false,
    });
  }

  // Don't render if no segments
  if (segments.length === 0) {
    return null;
  }

  return (
    <div className="bg-white border-b border-gray-200">
      <div className="container mx-auto px-4 py-3">
        <nav className="flex items-center flex-wrap gap-x-2 gap-y-1 text-sm" aria-label="Breadcrumb">
          {segments.map((segment, index) => (
            <React.Fragment key={index}>
              {index > 0 && (
                <span className="text-gray-400 mx-1" aria-hidden="true">
                  →
                </span>
              )}
              {segment.onClick ? (
                <button
                  onClick={segment.onClick}
                  className={`font-medium transition-colors ${
                    segment.isActive
                      ? 'text-blue-600 hover:text-blue-800'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                  title={segment.isActive ? 'Current stage' : `Click to select ${segment.label}`}
                >
                  {segment.label}
                </button>
              ) : (
                <span
                  className={`${
                    segment.isActive
                      ? 'text-blue-600 font-semibold'
                      : 'text-gray-600'
                  }`}
                  title={segment.isActive ? 'Current stage' : undefined}
                >
                  {segment.label}
                </span>
              )}
            </React.Fragment>
          ))}
        </nav>
      </div>
    </div>
  );
};

