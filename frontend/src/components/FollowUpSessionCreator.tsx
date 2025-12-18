import React, { useState, useRef, useEffect } from 'react';
import { Button } from './Button';
import { Textarea } from './Textarea';
import { ErrorAlert } from './ErrorAlert';
import * as api from '../api/client';
import type { QASession } from '../api/types';

interface FollowUpSessionCreatorProps {
  parentSessionId: string;
  onSuccess: (newSession: QASession) => void;
  onCancel: () => void;
}

export const FollowUpSessionCreator: React.FC<FollowUpSessionCreatorProps> = ({
  parentSessionId,
  onSuccess,
  onCancel,
}) => {
  const [questionText, setQuestionText] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    // Auto-resize textarea
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [questionText]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!questionText.trim()) {
      setError('Please enter at least one question');
      return;
    }

    // Extract questions from text (simple extraction - can be enhanced)
    const questions = questionText
      .split('\n')
      .map(q => q.trim())
      .filter(q => q.length > 0)
      .map(q => {
        // Remove numbering patterns (1., 2., etc.)
        const cleaned = q.replace(/^\d+[\.\)]\s*/, '').replace(/^[-•*]\s*/, '');
        return cleaned.endsWith('?') ? cleaned : cleaned + '?';
      });

    if (questions.length === 0) {
      setError('Please enter at least one valid question');
      return;
    }

    setIsCreating(true);
    try {
      const newSession = await api.createFollowUpSession(parentSessionId, {
        new_questions: questions,
      });
      setQuestionText('');
      onSuccess(newSession);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create follow-up session';
      setError(message);
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-900">
              Create Follow-Up Session
            </h2>
            <button
              onClick={onCancel}
              className="text-gray-400 hover:text-gray-600 transition-colors"
              aria-label="Close"
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

          <p className="text-sm text-gray-600 mb-4">
            Enter new questions for the follow-up session. The previous session will be marked as unsuccessful,
            and this new session will build upon it with improved answers.
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <Textarea
              ref={textareaRef}
              label="New Questions *"
              value={questionText}
              onChange={(e) => {
                setQuestionText(e.target.value);
                setError(null);
              }}
              placeholder="Enter your questions here (one per line or numbered list)...&#10;&#10;Example:&#10;1. Can you provide more details about the tax calculation?&#10;2. What are the specific requirements for documentation?&#10;3. Are there any exceptions to this rule?"
              rows={8}
              disabled={isCreating}
              showCharCount
              className="font-mono text-sm"
            />

            {error && (
              <ErrorAlert
                message={error}
                onDismiss={() => setError(null)}
              />
            )}

            <div className="flex justify-end space-x-3 pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={onCancel}
                disabled={isCreating}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                isLoading={isCreating}
                disabled={!questionText.trim() || isCreating}
              >
                Create Follow-Up Session
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

