import React, { ReactNode, useState } from 'react';
import { useSession } from '../contexts/SessionContext';
import { UserRoleToggle } from './UserRoleToggle';
import { SessionSelector } from './SessionSelector';
import { SessionCreator } from './SessionCreator';
import { ExportButton } from './ExportButton';
import { OutcomeStatus } from './OutcomeStatus';

interface LayoutProps {
  children: ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { currentSession, loadParentSession } = useSession();
  const [showSessionCreator, setShowSessionCreator] = useState(false);
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
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
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
        </div>
      </header>

      <div className="container mx-auto px-4 py-6">
        <div className="flex flex-col lg:flex-row gap-6">
          {/* Sidebar */}
          <aside
            className={`${
              showSidebar ? 'block' : 'hidden'
            } lg:block w-full lg:w-80 flex-shrink-0`}
          >
            <div className="bg-white rounded-lg shadow-md p-6 space-y-6 sticky top-6">
              <div>
                <h2 className="text-lg font-semibold text-gray-900 mb-4">
                  Session Management
                </h2>
                {showSessionCreator ? (
                  <SessionCreator
                    onSuccess={() => setShowSessionCreator(false)}
                    onCancel={() => setShowSessionCreator(false)}
                  />
                ) : (
                  <SessionSelector
                    onCreateNew={() => setShowSessionCreator(true)}
                  />
                )}
              </div>
              <div className="lg:hidden border-t border-gray-200 pt-4">
                <UserRoleToggle />
              </div>
              {currentSession && (
                <>
                  <div className="border-t border-gray-200 pt-4">
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
                  <div className="border-t border-gray-200 pt-4">
                    <OutcomeStatus />
                  </div>
                  <div className="border-t border-gray-200 pt-4">
                    <ExportButton />
                  </div>
                </>
              )}
            </div>
          </aside>

          {/* Main Content */}
          <main className="flex-1 min-w-0">
            {children}
          </main>
        </div>
      </div>
    </div>
  );
};

