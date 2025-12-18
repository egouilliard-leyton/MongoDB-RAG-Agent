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
      {qaPairs.map((qaPair) => (
        <QABlock key={qaPair._id} qaPair={qaPair} />
      ))}
    </div>
  );
};

