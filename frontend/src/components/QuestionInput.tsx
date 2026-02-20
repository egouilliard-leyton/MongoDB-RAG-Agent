import React, { useState, useRef, useEffect } from 'react';
import { useSession } from '../contexts/SessionContext';
import { useQuestionProcessing } from '../hooks/useQuestionProcessing';
import { Button } from './Button';
import { Textarea } from './Textarea';
import { ErrorAlert } from './ErrorAlert';

export const QuestionInput: React.FC = () => {
  const { currentSession } = useSession();
  const { processQuestionsText, isProcessing, error } = useQuestionProcessing();
  const [questionText, setQuestionText] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    // Auto-resize textarea with max-height constraint
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const scrollHeight = textareaRef.current.scrollHeight;
      const maxHeight = 300; // 300px max height
      textareaRef.current.style.height = `${Math.min(scrollHeight, maxHeight)}px`;
    }
  }, [questionText]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    console.log('[QuestionInput] Form submitted', {
      hasSession: !!currentSession,
      sessionId: currentSession?._id,
      questionText: questionText,
      questionTextLength: questionText.length,
      isProcessing,
    });
    
    setLocalError(null);

    if (!currentSession) {
      console.warn('[QuestionInput] No session available');
      setLocalError('Please create or load a session first');
      return;
    }

    if (!questionText.trim()) {
      console.warn('[QuestionInput] Empty question text');
      setLocalError('Please enter at least one question');
      return;
    }

    console.log('[QuestionInput] Calling processQuestionsText', {
      questionText,
      sessionId: currentSession._id,
    });

    try {
      await processQuestionsText(questionText);
      console.log('[QuestionInput] processQuestionsText completed successfully');
      setQuestionText(''); // Clear input on success
    } catch (err) {
      console.error('[QuestionInput] processQuestionsText failed', {
        error: err,
        errorMessage: err instanceof Error ? err.message : String(err),
      });
      const message = err instanceof Error ? err.message : 'Failed to process questions';
      setLocalError(message);
    }
  };

  const displayError = localError || error;

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h2 className="text-xl font-semibold text-gray-900 mb-4">
        Enter Your Questions
      </h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Textarea
          ref={textareaRef}
          value={questionText}
          onChange={(e) => {
            setQuestionText(e.target.value);
            setLocalError(null);
          }}
          placeholder="Enter your questions here (one per line or numbered list)...&#10;&#10;Example:&#10;1. What is the tax rate for corporations?&#10;2. How do I file quarterly returns?&#10;3. What deductions are available?"
          rows={4}
          maxHeight="300px"
          disabled={isProcessing || !currentSession}
          showCharCount
          className="font-mono text-sm"
        />
        {displayError && (
          <ErrorAlert
            message={displayError}
            onDismiss={() => {
              setLocalError(null);
            }}
          />
        )}
        <div className="flex justify-end">
          <Button
            type="submit"
            isLoading={isProcessing}
            disabled={!currentSession || !questionText.trim() || isProcessing}
          >
            Generate Answers
          </Button>
        </div>
        {!currentSession && (
          <p className="text-sm text-gray-500 text-center">
            Please create or load a session to start asking questions.
          </p>
        )}
      </form>
    </div>
  );
};

