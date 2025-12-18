import { useCallback } from 'react';
import { useQABlocks } from '../contexts/QABlocksContext';

export const useQuestionProcessing = () => {
  const { processQuestions, isProcessing, error } = useQABlocks();

  const extractQuestions = useCallback((text: string): string[] => {
    if (!text.trim()) return [];

    // Split by newlines and filter empty lines
    const lines = text
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line.length > 0);

    // Handle numbered lists (e.g., "1. Question", "2. Question")
    const questions = lines.map((line) => {
      // Remove leading numbers and dots/brackets (e.g., "1. ", "1) ", "[1] ")
      const cleaned = line.replace(/^(\d+[\.\)\]])?\s*/, '');
      return cleaned;
    });

    return questions.filter((q) => q.length > 0);
  }, []);

  const processQuestionsText = useCallback(
    async (text: string) => {
      console.log('[useQuestionProcessing] processQuestionsText called', {
        text,
        textLength: text.length,
      });
      
      const questions = extractQuestions(text);
      console.log('[useQuestionProcessing] Extracted questions', {
        questionCount: questions.length,
        questions,
      });
      
      if (questions.length === 0) {
        console.error('[useQuestionProcessing] No valid questions extracted');
        throw new Error('No valid questions found. Please enter at least one question.');
      }
      
      console.log('[useQuestionProcessing] Calling processQuestions', {
        questionCount: questions.length,
      });
      
      await processQuestions(questions);
      
      console.log('[useQuestionProcessing] processQuestions completed');
      return questions;
    },
    [extractQuestions, processQuestions]
  );

  return {
    processQuestionsText,
    extractQuestions,
    isProcessing,
    error,
  };
};

