import React, { useEffect } from 'react';
import { useSession } from '../contexts/SessionContext';
import { useQABlocks } from '../contexts/QABlocksContext';
import { QABlock } from './QABlock';
import { LoadingSpinner } from './LoadingSpinner';
import { EmptyState } from './EmptyState';

export const QABlockList: React.FC = () => {
  const { currentSession } = useSession();
  const { qaPairs, loadQAPairs, isProcessing } = useQABlocks();

  useEffect(() => {
    if (currentSession) {
      loadQAPairs();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentSession?._id]);

  if (!currentSession) {
    return (
      <EmptyState
        title="No Session Selected"
        message="Please create or load a session to view Q&A pairs."
      />
    );
  }

  if (isProcessing && qaPairs.length === 0) {
    return (
      <div className="flex justify-center items-center py-12">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (qaPairs.length === 0) {
    return (
      <EmptyState
        title="No Questions Yet"
        message="Enter questions above to get started. Your Q&A pairs will appear here."
      />
    );
  }

  return (
    <div className="space-y-6">
      {currentSession.metadata?.review_summary?.missing_info?.length ? (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm font-medium text-yellow-900">
                Review summary: what’s missing
              </p>
              <ul className="mt-2 text-sm text-yellow-800 list-disc pl-5 space-y-1">
                {currentSession.metadata.review_summary.missing_info.slice(0, 8).map((item, idx) => (
                  <li key={idx}>{item}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      ) : null}
      {qaPairs.map((qaPair) => (
        <QABlock key={qaPair._id} qaPair={qaPair} />
      ))}
    </div>
  );
};

