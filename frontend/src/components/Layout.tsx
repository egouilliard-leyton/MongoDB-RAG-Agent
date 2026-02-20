import React, { ReactNode, useState } from 'react';
import { useSession } from '../contexts/SessionContext';
import { useProject } from '../contexts/ProjectContext';
import { UserRoleToggle } from './UserRoleToggle';
import { SessionSelector } from './SessionSelector';
import { SessionCreator } from './SessionCreator';
import { ProjectSelector } from './ProjectSelector';
import { ProjectCreator } from './ProjectCreator';
import { StageWorkflowVisualization } from './StageWorkflowVisualization';
import { ProjectUploads } from './ProjectUploads';
import { ExportButton } from './ExportButton';
import { OutcomeStatus } from './OutcomeStatus';
import { ContextBreadcrumb } from './ContextBreadcrumb';
import { CompanyInfoPanel } from './CompanyInfoPanel';
import { CollapsibleSection } from './CollapsibleSection';
import { Modal } from './Modal';
import { getStageLabel } from '../utils/stageLabels';

type AppView = 'qa' | 'documents' | 'ingestion' | 'dashboard';

interface LayoutProps {
  children: ReactNode;
  currentView?: AppView;
  onViewChange?: (view: AppView) => void;
}

export const Layout: React.FC<LayoutProps> = ({
  children,
  currentView = 'qa',
  onViewChange,
}) => {
  const { currentSession, loadParentSession } = useSession();
  const { currentProject } = useProject();
  const [showSessionCreator, setShowSessionCreator] = useState(false);
  const [showProjectCreator, setShowProjectCreator] = useState(false);
  const [showSidebar, setShowSidebar] = useState(true);

  const handleLoadParentSession = async () => {
    try {
      await loadParentSession();
    } catch (err) {
      console.error('Failed to load parent session:', err);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="container mx-auto px-4">
          <div className="flex items-center justify-between py-4">
            <div className="flex items-center space-x-4">
              <button
                onClick={() => setShowSidebar(!showSidebar)}
                className="lg:hidden p-2 rounded-md text-gray-600 hover:bg-gray-100"
                aria-label="Toggle sidebar"
              >
                <svg
                  className="w-6 h-6"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 6h16M4 12h16M4 18h16"
                  />
                </svg>
              </button>
              <h1 className="text-2xl font-bold text-gray-900">
                Q&A System
              </h1>
            </div>
            <div className="hidden md:block">
              <UserRoleToggle />
            </div>
          </div>

          {/* Navigation Tabs */}
          {onViewChange && (
            <nav className="flex space-x-1 -mb-px">
              <NavTab
                label="Q&A"
                icon={
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                  </svg>
                }
                isActive={currentView === 'qa'}
                onClick={() => onViewChange('qa')}
              />
              <NavTab
                label="Documents"
                icon={
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                }
                isActive={currentView === 'documents'}
                onClick={() => onViewChange('documents')}
              />
              <NavTab
                label="Ingestion"
                icon={
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
                  </svg>
                }
                isActive={currentView === 'ingestion'}
                onClick={() => onViewChange('ingestion')}
              />
              <NavTab
                label="Dashboard"
                icon={
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                }
                isActive={currentView === 'dashboard'}
                onClick={() => onViewChange('dashboard')}
              />
            </nav>
          )}
        </div>
      </header>

      <div className="container mx-auto px-4 md:px-6 lg:px-8 py-6">
        {/* Context Breadcrumb - Top of main content area */}
        <div className="mb-6">
          <ContextBreadcrumb />
        </div>

        <div className="flex flex-col lg:flex-row gap-8">
          {/* Mobile backdrop overlay */}
          {showSidebar && (
            <div
              className="fixed inset-0 bg-black bg-opacity-50 z-40 lg:hidden"
              onClick={() => setShowSidebar(false)}
              aria-hidden="true"
            />
          )}

          {/* Sidebar */}
          <aside
            className={`${
              showSidebar ? 'block' : 'hidden'
            } lg:block w-full lg:w-96 flex-shrink-0 fixed lg:relative top-0 left-0 h-full lg:h-auto z-50 lg:z-auto transform transition-transform duration-300 ease-in-out ${
              showSidebar ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
            }`}
          >
            <div className="bg-white rounded-lg shadow-md p-6 space-y-4 h-full lg:h-auto overflow-y-auto lg:sticky lg:top-6">
              {/* Sidebar header with close button (mobile only) */}
              <div className="flex items-center justify-between mb-4 lg:hidden border-b border-gray-200 pb-4">
                <h2 className="text-lg font-semibold text-gray-900">Menu</h2>
                <button
                  onClick={() => setShowSidebar(false)}
                  className="p-2 rounded-md text-gray-600 hover:bg-gray-100"
                  aria-label="Close sidebar"
                >
                  <svg
                    className="w-6 h-6"
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
                </button>
              </div>

              {/* 1. Context Section (top, always visible, sticky) */}
              <div className="sticky top-0 z-10 bg-white pb-4 border-b border-gray-200">
                <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
                  Context
                </h2>
                <div className="space-y-2 text-sm">
                  {/* Company name */}
                  {(currentSession?.metadata?.company_info?.company_name ||
                    currentProject?.company_info?.company_name) && (
                    <div>
                      <span className="text-gray-500 text-xs">Company:</span>
                      <p className="text-gray-900 font-medium mt-0.5">
                        {currentSession?.metadata?.company_info?.company_name ||
                          currentProject?.company_info?.company_name}
                      </p>
                    </div>
                  )}
                  
                  {/* Project name */}
                  {currentProject && (
                    <div>
                      <span className="text-gray-500 text-xs">Project:</span>
                      <p className="text-gray-900 font-medium mt-0.5">
                        {currentProject.name}
                      </p>
                    </div>
                  )}
                  
                  {/* Current stage indicator */}
                  {currentProject?.stage?.key && (
                    <div>
                      <span className="text-gray-500 text-xs">Stage:</span>
                      <div className="flex items-center mt-0.5">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                          {getStageLabel(currentProject.stage.key)}
                        </span>
                      </div>
                    </div>
                  )}
                  
                  {!currentProject && (
                    <p className="text-gray-400 text-xs italic">
                      No project selected
                    </p>
                  )}
                </div>
              </div>

              {/* 2. Stage Workflow (when project selected) */}
              {currentProject && (
                <div className="pb-4 border-b border-gray-200">
                  <StageWorkflowVisualization />
                </div>
              )}

              {/* 3. Project Management (collapsible) */}
              <CollapsibleSection
                title="Project Management"
                defaultOpen={false}
                icon={
                  <svg
                    className="w-4 h-4 text-gray-500"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
                    />
                  </svg>
                }
              >
                <div className="space-y-4">
                  <ProjectSelector onCreateNew={() => setShowProjectCreator(true)} />
                  {currentProject && <ProjectUploads />}
                </div>
              </CollapsibleSection>

              {/* 4. Session Management (collapsible) */}
              <CollapsibleSection
                title="Session Management"
                defaultOpen={false}
                icon={
                  <svg
                    className="w-4 h-4 text-gray-500"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                    />
                  </svg>
                }
              >
                <div className="space-y-4">
                  <SessionSelector
                    onCreateNew={() => setShowSessionCreator(true)}
                  />
                </div>
              </CollapsibleSection>

              {/* 5. Session Details (when session active) */}
              {currentSession && (
                <CollapsibleSection
                  title="Session Details"
                  defaultOpen={false}
                  icon={
                    <svg
                      className="w-4 h-4 text-gray-500"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                      />
                    </svg>
                  }
                >
                  <div className="space-y-4">
                    {/* Company Info Panel */}
                    <CompanyInfoPanel />

                    {/* Session Status */}
                    <div>
                      <h3 className="text-sm font-medium text-gray-700 mb-2">
                        Session Status
                      </h3>
                      <div className="space-y-2 text-sm">
                        <div className="flex justify-between">
                          <span className="text-gray-600">Status:</span>
                          <span className="font-medium capitalize">
                            {currentSession.status}
                          </span>
                        </div>
                        {currentSession.metadata?.round_number && (
                          <div className="flex justify-between">
                            <span className="text-gray-600">Round:</span>
                            <span className="font-medium">
                              {currentSession.metadata.round_number}
                            </span>
                          </div>
                        )}
                        {currentSession.metadata?.parent_session_id && (
                          <div className="flex justify-between items-center">
                            <span className="text-gray-600">Parent Session:</span>
                            <button
                              onClick={handleLoadParentSession}
                              className="text-blue-600 hover:text-blue-800 underline text-xs font-medium"
                              title="Load parent session"
                            >
                              View Parent
                            </button>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Outcome Status */}
                    <OutcomeStatus />

                    {/* Export Button */}
                    <ExportButton />
                  </div>
                </CollapsibleSection>
              )}

              {/* User Role Toggle (mobile) */}
              <div className="lg:hidden border-t border-gray-200 pt-4">
                <UserRoleToggle />
              </div>
            </div>
          </aside>

          {/* Main Content */}
          <main className="flex-1 min-w-0">
            <div className="max-w-4xl mx-auto">
              {children}
            </div>
          </main>
        </div>
      </div>

      {/* Project Creator Modal */}
      <Modal
        isOpen={showProjectCreator}
        onClose={() => setShowProjectCreator(false)}
        title="Create New Project"
        size="md"
      >
        <ProjectCreator
          onSuccess={() => setShowProjectCreator(false)}
          onCancel={() => setShowProjectCreator(false)}
        />
      </Modal>

      {/* Session Creator Modal */}
      <Modal
        isOpen={showSessionCreator}
        onClose={() => setShowSessionCreator(false)}
        title="Create New Session"
        size="md"
      >
        <SessionCreator
          onSuccess={() => setShowSessionCreator(false)}
          onCancel={() => setShowSessionCreator(false)}
        />
      </Modal>
    </div>
  );
};

// =============================================================================
// Sub-components
// =============================================================================

interface NavTabProps {
  label: string;
  icon: React.ReactNode;
  isActive: boolean;
  onClick: () => void;
}

/**
 * Navigation tab in the header.
 */
const NavTab: React.FC<NavTabProps> = ({ label, icon, isActive, onClick }) => {
  return (
    <button
      onClick={onClick}
      className={`
        flex items-center space-x-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors
        ${isActive
          ? 'border-blue-600 text-blue-600'
          : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
        }
      `}
    >
      {icon}
      <span>{label}</span>
    </button>
  );
};

