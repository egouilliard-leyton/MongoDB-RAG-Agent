import { useState } from 'react';
import { SessionProvider } from './contexts/SessionContext';
import { QABlocksProvider } from './contexts/QABlocksContext';
import { ProjectProvider } from './contexts/ProjectContext';
import { IngestionProvider } from './contexts/IngestionContext';
import { DocumentProvider } from './contexts/DocumentContext';
import { DashboardProvider } from './contexts/DashboardContext';
import { SettingsProvider } from './contexts/SettingsContext';
import { Layout } from './components/Layout';
import { QuestionInput } from './components/QuestionInput';
import { QABlockList } from './components/QABlockList';
import { DocumentUploader } from './components/DocumentUploader';
import { DocumentList } from './components/DocumentList';
import { IngestionDashboard } from './components/IngestionDashboard';
import { IngestionResult } from './components/IngestionResult';
import { Dashboard } from './pages/Dashboard';
import { SettingsPage } from './pages/SettingsPage';

// =============================================================================
// Types
// =============================================================================

type AppView = 'qa' | 'documents' | 'ingestion' | 'dashboard' | 'settings';

// =============================================================================
// Main App
// =============================================================================

function App() {
  const [currentView, setCurrentView] = useState<AppView>('qa');

  return (
    <ProjectProvider>
      <SessionProvider>
        <QABlocksProvider>
          <IngestionProvider>
            <DocumentProvider>
              <DashboardProvider>
                <SettingsProvider>
                  <Layout
                    currentView={currentView}
                    onViewChange={setCurrentView}
                  >
                    {currentView === 'qa' && (
                      <div className="space-y-6">
                        <QuestionInput />
                        <QABlockList />
                      </div>
                    )}

                    {currentView === 'documents' && (
                      <DocumentsPage onNavigateToIngestion={() => setCurrentView('ingestion')} />
                    )}

                    {currentView === 'ingestion' && (
                      <IngestionPage onNavigateToDocuments={() => setCurrentView('documents')} />
                    )}

                    {currentView === 'dashboard' && <Dashboard />}

                    {currentView === 'settings' && <SettingsPage />}
                  </Layout>
                </SettingsProvider>
              </DashboardProvider>
            </DocumentProvider>
          </IngestionProvider>
        </QABlocksProvider>
      </SessionProvider>
    </ProjectProvider>
  );
}

// =============================================================================
// Page Components
// =============================================================================

interface DocumentsPageProps {
  onNavigateToIngestion: () => void;
}

/**
 * Documents page with document list and upload functionality.
 */
function DocumentsPage({ onNavigateToIngestion }: DocumentsPageProps) {
  return (
    <div className="space-y-6">
      {/* Document List Section */}
      <DocumentList />

      {/* Upload Section */}
      <div className="border-t border-gray-200 pt-6">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">Upload Documents</h2>
          <p className="text-sm text-gray-600 mt-1">
            Upload documents to add them to the knowledge base. No project required.
          </p>
        </div>

        <div className="mt-4">
          <DocumentUploader
            onUploadComplete={onNavigateToIngestion}
          />
        </div>

        <div className="mt-6">
          <button
            onClick={onNavigateToIngestion}
            className="text-sm text-blue-600 hover:text-blue-800"
          >
            View Ingestion History →
          </button>
        </div>
      </div>
    </div>
  );
}

interface IngestionPageProps {
  onNavigateToDocuments: () => void;
}

/**
 * Ingestion history page with dashboard.
 */
function IngestionPage({ onNavigateToDocuments }: IngestionPageProps) {
  const [selectedJob, setSelectedJob] = useState<any | null>(null);

  if (selectedJob) {
    return (
      <div className="space-y-4">
        <button
          onClick={() => setSelectedJob(null)}
          className="text-sm text-blue-600 hover:text-blue-800 flex items-center"
        >
          <svg className="w-4 h-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back to Dashboard
        </button>
        <IngestionResult
          result={selectedJob}
          onUploadAnother={onNavigateToDocuments}
        />
      </div>
    );
  }

  return (
    <IngestionDashboard
      onJobClick={setSelectedJob}
      onUploadClick={onNavigateToDocuments}
    />
  );
}

export default App;

