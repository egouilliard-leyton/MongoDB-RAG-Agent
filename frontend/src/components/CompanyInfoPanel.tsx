import React from 'react';
import { useSession } from '../contexts/SessionContext';
import { useProject } from '../contexts/ProjectContext';

interface CompanyInfoPanelProps {
  className?: string;
}

export const CompanyInfoPanel: React.FC<CompanyInfoPanelProps> = ({ className = '' }) => {
  const { currentSession } = useSession();
  const { currentProject } = useProject();

  // Get company info from session metadata or project
  const companyInfo = currentSession?.metadata?.company_info || currentProject?.company_info;

  // Don't render if no company info available
  if (!companyInfo || Object.keys(companyInfo).length === 0) {
    return null;
  }

  const hasAnyInfo = 
    companyInfo.company_name || 
    companyInfo.industry || 
    companyInfo.activities || 
    companyInfo.context;

  if (!hasAnyInfo) {
    return null;
  }

  return (
    <div className={`space-y-3 ${className}`}>
      <div>
        <h3 className="text-sm font-medium text-gray-700 mb-2 flex items-center">
          <svg
            className="w-4 h-4 mr-2 text-gray-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
            />
          </svg>
          Company Information
        </h3>
        <div className="space-y-2 text-sm">
          {companyInfo.company_name && (
            <div>
              <span className="text-gray-600 font-medium">Company:</span>
              <p className="text-gray-900 mt-0.5">{companyInfo.company_name}</p>
            </div>
          )}
          
          {companyInfo.industry && (
            <div>
              <span className="text-gray-600 font-medium">Industry:</span>
              <p className="text-gray-900 mt-0.5">{companyInfo.industry}</p>
            </div>
          )}
          
          {companyInfo.activities && (
            <div>
              <span className="text-gray-600 font-medium">Activities:</span>
              <p className="text-gray-900 mt-0.5 whitespace-pre-wrap break-words">
                {companyInfo.activities}
              </p>
            </div>
          )}
          
          {companyInfo.context && (
            <div>
              <span className="text-gray-600 font-medium">Context:</span>
              <p className="text-gray-900 mt-0.5 whitespace-pre-wrap break-words">
                {companyInfo.context}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Show source indicator if company info comes from project */}
      {currentProject && currentProject.company_info && (
        <div className="pt-2 border-t border-gray-200">
          <p className="text-xs text-gray-500">
            Company info linked to project
          </p>
        </div>
      )}
    </div>
  );
};

