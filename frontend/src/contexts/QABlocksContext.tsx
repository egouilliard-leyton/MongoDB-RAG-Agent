import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import type { QAPair } from '../api/types';
import * as api from '../api/client';
import { useSession } from './SessionContext';

interface QABlocksContextType {
  qaPairs: QAPair[];
  isProcessing: boolean;
  error: string | null;
  processQuestions: (questions: string[]) => Promise<void>;
  updateAnswer: (qaPairId: string, editedAnswer: string) => Promise<void>;
  loadQAPairs: () => Promise<void>;
  clearError: () => void;
}

const QABlocksContext = createContext<QABlocksContextType | undefined>(undefined);

export const useQABlocks = () => {
  const context = useContext(QABlocksContext);
  if (!context) {
    throw new Error('useQABlocks must be used within a QABlocksProvider');
  }
  return context;
};

interface QABlocksProviderProps {
  children: ReactNode;
}

export const QABlocksProvider: React.FC<QABlocksProviderProps> = ({ children }) => {
  const { currentSession, userRole } = useSession();
  const [qaPairs, setQAPairs] = useState<QAPair[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const processQuestions = useCallback(async (questions: string[]) => {
    const startTime = Date.now();
    console.log('[QABlocksContext] processQuestions called', {
      sessionId: currentSession?._id,
      userRole,
      questionCount: questions.length,
      questions,
    });
    
    if (!currentSession) {
      const error = 'No session loaded';
      console.error('[QABlocksContext] processQuestions failed:', error);
      throw new Error(error);
    }
    
    setIsProcessing(true);
    setError(null);
    
    try {
      console.log('[QABlocksContext] Calling API to process questions', {
        sessionId: currentSession._id,
        questionCount: questions.length,
      });
      
      const response = await api.processQuestions(currentSession._id, { 
        questions,
        user_role: userRole,
        include_history: true
      });
      
      const duration = Date.now() - startTime;
      console.log('[QABlocksContext] API response received', {
        sessionId: currentSession._id,
        questionsProcessed: response.questions_processed,
        qaPairsCount: response.qa_pairs?.length || 0,
        duration: `${duration}ms`,
      });
      
      setQAPairs((prev) => {
        const existingIds = new Set(prev.map((p) => p._id));
        const newPairs = response.qa_pairs.filter((p) => !existingIds.has(p._id));
        const updated = [...prev, ...newPairs].sort((a, b) => a.question_index - b.question_index);
        
        console.log('[QABlocksContext] Q&A pairs state updated', {
          previousCount: prev.length,
          newPairsCount: newPairs.length,
          totalCount: updated.length,
        });
        
        return updated;
      });
    } catch (err) {
      const duration = Date.now() - startTime;
      const message = err instanceof Error ? err.message : 'Failed to process questions';
      
      console.error('[QABlocksContext] processQuestions failed', {
        sessionId: currentSession._id,
        duration: `${duration}ms`,
        error: message,
        errorDetails: err,
      });
      
      setError(message);
      throw err;
    } finally {
      setIsProcessing(false);
      const duration = Date.now() - startTime;
      console.log('[QABlocksContext] processQuestions completed', {
        sessionId: currentSession._id,
        duration: `${duration}ms`,
      });
    }
  }, [currentSession, userRole]);

  const updateAnswer = useCallback(async (qaPairId: string, editedAnswer: string) => {
    setIsProcessing(true);
    setError(null);
    try {
      await api.updateAnswer(qaPairId, { edited_answer: editedAnswer });
      setQAPairs((prev) =>
        prev.map((pair) =>
          pair._id === qaPairId
            ? { ...pair, edited_answer: editedAnswer, final_answer: editedAnswer }
            : pair
        )
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update answer';
      setError(message);
      throw err;
    } finally {
      setIsProcessing(false);
    }
  }, []);

  const loadQAPairs = useCallback(async () => {
    if (!currentSession) {
      setQAPairs([]);
      return;
    }
    setIsProcessing(true);
    setError(null);
    try {
      const pairs = await api.getQAPairs(currentSession._id);
      setQAPairs(pairs.sort((a, b) => a.question_index - b.question_index));
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load Q&A pairs';
      setError(message);
    } finally {
      setIsProcessing(false);
    }
  }, [currentSession]);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const value: QABlocksContextType = {
    qaPairs,
    isProcessing,
    error,
    processQuestions,
    updateAnswer,
    loadQAPairs,
    clearError,
  };

  return <QABlocksContext.Provider value={value}>{children}</QABlocksContext.Provider>;
};

